"""BharatTrip refund reconciliation and local AI-assisted complaint triage."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

SNAPSHOT = pd.Timestamp('2026-06-30')
# Proposed review thresholds, not a supplied company SLA.
STALE_DAYS = 7
EXAMPLES = [
    ('communication', 'Agent chasing for a status update, no response. Repeated follow-ups on refund status with no reply.'),
    ('handoff', 'Ticket shows closed, Finance has no record of this refund. Finance never received refunds Support closed last month.'),
    ('payment_confirmation', 'Marked complete on Support side, nothing received by agent. Support says refund done but money not credited.'),
    ('intake', 'Email WhatsApp request ignored entirely. No reference number given. Sent refund request never got a ticket number. BLR-MAA ignored for two weeks.'),
    ('amount', 'Two different refund figures quoted. Refund amount received less than promised. Short payment full amount expected no deduction explained.'),
    ('approval', 'Refund promised weeks ago still sitting unpaid. No update payout stuck in approval queue.'),
    ('decline', 'Told refund rejected but no reason given. Decline communicated without policy explanation.'),
    ('ownership', 'Refund stuck no one owns it.'),
]

def reference(value):
    if pd.isna(value) or not str(value).strip():
        return None
    match = re.fullmatch(r'RF[\s-]*(\d+)(?:\s*\(revised\))?', str(value).strip(), re.I)
    return f'RF-{match.group(1)}' if match else None

def date(value):
    if pd.isna(value):
        return pd.NaT
    if isinstance(value, (pd.Timestamp, __import__('datetime').datetime)):
        return pd.Timestamp(value)
    value = str(value).strip()
    for fmt in ('%d-%m-%Y', '%d/%m/%y', '%d/%m/%Y', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
        try:
            return pd.to_datetime(value, format=fmt)
        except ValueError:
            pass
    return pd.NaT

def text(value):
    return '' if pd.isna(value) else str(value).strip()

def name(value):
    return re.sub(r'[^a-z0-9]', '', text(value).lower())

class ComplaintAI:
    """Transparent local text-retrieval baseline. Scores are NOT probabilities."""
    def __init__(self):
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform([v for _, v in EXAMPLES])

    def classify(self, complaint):
        scores = cosine_similarity(self.vectorizer.transform([complaint]), self.matrix)[0]
        idx = scores.argsort()[::-1]
        best, second = float(scores[idx[0]]), float(scores[idx[1]])
        return {'suggested_category': EXAMPLES[idx[0]][0], 'similarity': round(best, 3),
                'review_required': best < .18 or best - second < .05,
                'matched_example': EXAMPLES[idx[0]][1],
                'method': 'TF-IDF nearest-example retrieval; not an LLM or validated classifier'}

def clean(frame, id_col, date_cols):
    frame = frame.copy()
    raw_count = len(frame)
    # Preserve distinct records. Strip strings before finding pasted duplicates.
    for col in frame.select_dtypes(include='object'):
        frame[col] = frame[col].map(lambda v: v.strip() if isinstance(v, str) else v)
    frame['case_id'] = frame[id_col].map(reference)
    for col in date_cols:
        frame[col] = frame[col].map(date)
    compare = [c for c in frame.columns if c != id_col]
    frame = frame.drop_duplicates(subset=compare).copy()
    return frame, {'raw_rows': raw_count, 'retained_rows': len(frame),
                   'pasted_duplicates_removed': raw_count - len(frame),
                   'repeated_ids_for_review': sorted(frame.loc[frame.case_id.duplicated(False), 'case_id'].dropna().unique().tolist())}

def load_and_reconcile(path, *, brief_intakes=None):
    x = path if isinstance(path, dict) else pd.ExcelFile(path)
    def sheet(key):
        return x[key].copy() if isinstance(x, dict) else pd.read_excel(x,key)
    s, sq = clean(sheet('Support_Tracker'), 'Ticket ID', ['Request Date', 'Last Updated'])
    f, fq = clean(sheet('Finance_Tracker'), 'Ref No', ['Received On', 'Processed On'])
    e, eq = clean(sheet('Escalations'), 'Related Ticket / Ref', ['Raised On', 'Resolved On'])
    ai = ComplaintAI()
    e = pd.concat([e.reset_index(drop=True), pd.DataFrame([ai.classify(text(v)) for v in e.Complaint])], axis=1)
    conflicts = set(sq['repeated_ids_for_review']) | set(fq['repeated_ids_for_review'])
    # Conflicting IDs are quarantined instead of arbitrarily selecting a row or multiplying joins.
    # The two provisional intakes are from the real brief, not generated demo records.
    if brief_intakes is None:
        brief_intakes = not isinstance(path, dict)
    provisional = {'RF-1098','RF-1099'} if brief_intakes else set()
    ids = sorted(set(s.case_id.dropna()) | set(f.case_id.dropna()) | set(e.case_id.dropna()) | provisional)
    cases = []
    for case_id in ids:
        sr, fr, er = s[s.case_id == case_id], f[f.case_id == case_id], e[e.case_id == case_id]
        a = sr.iloc[0] if len(sr) == 1 else None
        b = fr.iloc[0] if len(fr) == 1 else None
        issues = []
        support_status, finance_status = (text(a['Status']) if a is not None else ''), (text(b['Payout Status']) if b is not None else '')
        if case_id in conflicts:
            issues.append('conflicting_duplicate_id')
        if sr.empty and fr.empty:
            issues.append('absent_from_both_trackers')
        elif sr.empty:
            issues.append('missing_support_record')
        elif fr.empty:
            issues.append('missing_finance_record')
        closed = support_status == 'Closed'
        paid = finance_status == 'Refund Done'
        if closed and not paid and case_id not in conflicts:
            issues.append('support_closed_without_finance_paid')
        if paid and support_status in ('Working', 'Escalated'):
            issues.append('paid_support_not_updated')
        if a is not None and b is not None:
            if name(a.Agent) != name(b['Agent Name']):
                issues.append('agent_name_review')
            if text(a.Route).upper() != text(b.Sector).upper():
                issues.append('route_mismatch')
            if b['Received On'] < a['Request Date']:
                issues.append('received_before_request')
            if pd.notna(b['Processed On']) and b['Processed On'] < b['Received On']:
                issues.append('paid_before_received')
            if support_status == 'Not Eligible' and paid:
                issues.append('support_ineligible_finance_paid')
            if closed and finance_status == 'Declined':
                issues.append('closed_but_declined')
        amount = a['Refund Amount (INR)'] if a is not None else None
        actual = b['Amount Paid (INR)'] if b is not None else None
        deduction = b['Deduction (INR)'] if b is not None else None
        gap, unexplained = None, None
        if paid and pd.notna(amount) and pd.notna(actual):
            gap = float(amount - actual)
            if pd.notna(deduction):
                unexplained = float(gap - deduction)
                if abs(unexplained) > 1:
                    issues.append('unexplained_amount_difference')
                elif gap > 1:
                    issues.append('deduction_needs_communication_check')
            elif abs(gap) > 1:
                issues.append('amount_difference_missing_deduction')
        if a is not None and pd.isna(amount):
            issues.append('missing_requested_amount')
        if paid and (pd.isna(actual) or pd.isna(b['Processed On'])):
            issues.append('paid_record_missing_evidence_fields')
        if a is not None and not text(a['Handled By']):
            issues.append('missing_support_owner')
        # Declined cases may be legitimately closed; status alone cannot resolve eligibility.
        if finance_status == 'Pending Payout':
            issues.append('pending_payout')
        request_date = a['Request Date'] if a is not None else pd.NaT
        age = int((SNAPSHOT - request_date).days) if pd.notna(request_date) else None
        if case_id not in conflicts and age is not None and age > STALE_DAYS and not paid and finance_status != 'Declined' and support_status != 'Not Eligible':
            issues.append('aged_unpaid_review')
        open_e = er[er.Status.str.strip().eq('Open')]
        if not open_e.empty:
            issues.append('open_escalation')
        priority = 'P1' if (case_id in conflicts or 'open_escalation' in issues or (closed and not paid) or 'absent_from_both_trackers' in issues) else ('P2' if issues else 'P3')
        if 'conflicting_duplicate_id' in issues:
            action = 'Resolve conflicting source rows before changing state or matching.'
        elif a is None and b is None:
            action = 'Support: register provisional intake; verify booking and identity; acknowledge with reference.'
        elif a is None:
            action = 'Support: backfill linked case and verify agent communication.'
        elif b is None:
            action = 'Support: verify eligibility and Finance handoff; obtain acknowledgement. Do not repay blindly.'
        elif finance_status == 'Declined':
            action = 'Finance: document eligibility decision; Support: explain reason and correct status.'
        elif finance_status == 'Pending Payout':
            action = 'Finance: confirm blocker, approval owner and next update date; Support: acknowledge delay.'
        elif any('amount' in v or 'deduction' in v for v in issues):
            action = 'Finance: reconcile request, paid amount and authorised deductions; Support: explain verified result.'
        elif paid:
            action = 'Finance: obtain payment reference; Support: verify credit/communication and align status.'
        else:
            action = 'Support: review case and assign next action and update date.'
        cases.append(dict(case_id=case_id, agent=text(a.Agent) if a is not None else (text(b['Agent Name']) if b is not None else ''),
                          support_present=not sr.empty, finance_present=not fr.empty,
                          support_status=support_status, finance_status=finance_status,
                          requested_amount=amount, amount_paid=actual, deduction=deduction,
                          amount_gap=gap, unexplained_gap=unexplained, age_days=age,
                          support_owner=text(a['Handled By']) if a is not None else '',
                          escalation_count=len(er), open_escalations=len(open_e), priority=priority,
                          issues='; '.join(issues), next_action=action))
    c = pd.DataFrame(cases)
    e['month'] = e['Raised On'].dt.strftime('%Y-%m')
    s['month'] = s['Request Date'].dt.strftime('%Y-%m')
    monthly = pd.concat([s.drop_duplicates(['case_id','month']).groupby('month').size().rename('requests_logged'), e.groupby('month').size().rename('escalations_raised')], axis=1).fillna(0).astype(int)
    monthly['escalations_per_100_monthly_requests'] = (100 * monthly.escalations_raised / monthly.requests_logged).round(1)
    monthly.loc[monthly.index < '2026-03', ['escalations_raised', 'escalations_per_100_monthly_requests']] = float('nan')
    counts = c.issues.str.split('; ').explode().value_counts()
    counts = {k: int(v) for k, v in counts.items() if k}
    summary = {'snapshot': str(SNAPSHOT.date()), 'quality': {'support': sq, 'finance': fq, 'escalations': eq},
               'unique_cases': len(c), 'support_cases': s.case_id.nunique(), 'finance_cases': f.case_id.nunique(),
               'matched_cases': int((c.support_present & c.finance_present).sum()),
               'escalations': len(e), 'open_escalations': int(e.Status.eq('Open').sum()),
               'escalations_without_reference': int(e.case_id.isna().sum()), 'issue_counts': counts,
               'monthly': monthly.reset_index().to_dict(orient='records'),
               'ai_category_counts': {k: int(v) for k,v in e.suggested_category.value_counts().items()},
               'invalid_dates': {f'{label}.{col}': int(df[col].isna().sum()) for label,df,cols in [('support',s,['Request Date','Last Updated']),('finance',f,['Received On']),('escalations',e,['Raised On'])] for col in cols}}
    return c, e, monthly, summary

def draft_reply(case):
    """Evidence-only template; requires human approval and adds no payment promise."""
    ref = case['case_id']
    if 'conflicting_duplicate_id' in case.get('issues',''):
        state = 'We found multiple records under this reference and are checking them before confirming payment status or amount.'
    elif not case['finance_present']:
        state = 'We are checking the Finance handoff. We do not yet have a matched Finance payment record.'
    elif case['finance_status'] == 'Refund Done':
        state = 'Our Finance tracker records a completed refund. We are verifying the payment reference and any amount difference.'
    elif case['finance_status'] == 'Declined':
        state = 'Our Finance tracker records a declined request. We are checking the decision and explanation before confirming the outcome.'
    else:
        state = 'Our Finance tracker shows the payout is pending. We are checking the blocker and responsible owner.'
    return f'Reference {ref}. {state} Your case is under review. We will share a confirmed update after these checks. [Reviewer: add owner and agreed next update time before sending.]'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=next(Path(__file__).parent.glob('*.xlsx'), None))
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'outputs')
    args = parser.parse_args()
    if args.input is None:
        from demo_data import demo_tables
        args.input = demo_tables()
    c,e,m,summary = load_and_reconcile(args.input)
    args.output.mkdir(parents=True, exist_ok=True)
    c.sort_values(['priority','open_escalations','age_days'], ascending=[True,False,False]).to_csv(args.output/'review_queue.csv', index=False)
    e.to_csv(args.output/'escalation_triage.csv', index=False)
    m.to_csv(args.output/'monthly_metrics.csv')
    summary = json.loads(json.dumps(summary, default=str), parse_constant=lambda _: None)
    (args.output/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(summary, indent=2, default=str))

if __name__ == '__main__':
    main()
