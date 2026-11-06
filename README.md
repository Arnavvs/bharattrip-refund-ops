# BharatTrip refund operations

A working reconciliation pipeline and review dashboard for the BharatTrip assessment. The operational question is: **which refunds need attention, who should act, and what can we truthfully tell the agent?** The public app starts with a small, separately generated illustrative dataset. The supplied assessment workbook is excluded from this repository. Upload it in the dashboard or place it beside `app.py` to run the actual analysis.

## Run

```sh
pip install -r requirements.txt
streamlit run app.py
```

Run the repeatable batch pipeline with `python refund_ops.py`. It writes a review queue, complaint triage, monthly metrics and a summary to `outputs/`. Run verification with `python -m unittest -v`.

## How it works

1. Read Support, Finance and escalation records. Parse day-first dates and normalise RF references. Unknown reference placeholders remain unlinked.
2. Remove exact pasted duplicates after normalisation. Keep different records with the same reference in a review quarantine. Never multiply joins or silently add repeated Finance payments together.
3. Join by exact canonical reference. Identify missing handoffs, closed-but-unconfirmed cases, pending payouts, unexplained amount gaps and escalation history. Agent names alone cannot establish a match.
4. Use local TF-IDF text retrieval to suggest one of eight complaint categories. Show the matching example and similarity. Weak/ambiguous matches require review. This is a lightweight NLP baseline, not an LLM, and no held-out accuracy claim is made.
5. Produce a prioritised queue with suggested team actions and evidence-grounded reply templates. The templates are deterministic, not AI-generated. All messages require human review. The app does not execute payments or edit source trackers.

## Data and assumptions

- The source brief describes its data as synthetic and anonymised, but the source workbook is not published here. Public demo records are independently authored illustrations. Snapshot: **30 June 2026**, regardless of today's date.
- The supplied workbook stays unchanged. Uploaded replacements are processed in memory and are not deliberately persisted by the application.
- A tracker marked `Refund Done` is a recorded payout, not independent proof of bank credit. Bank reference and credit confirmation are unavailable.
- Seven days is a proposed aged-case review threshold, not an existing policy. Eligibility and permitted deductions are unknown.
- Distinct rows sharing a reference are ambiguous. The queue quarantines them. Source row totals and unique case counts differ.
- Monthly request counts deduplicate references within each month. Escalations raised in a month can concern earlier requests. Their ratio is a workload indicator, not a cohort risk estimate.
- Escalations were not logged before March. February must not be interpreted as zero complaints.
- RF-1098 and RF-1099 are included as provisional untracked intakes from the brief. No amount, cancellation date or booking identity is invented.
- Unlinked escalations stay separate. Do not treat every complaint as a new refund or combine all unknown references into one case.
- The dashboard is a read-only snapshot prototype. Production needs authentication, an audit log, case ownership, payment evidence, daily reconciliation and one durable shared case register.

## Proposed operating process

All channels create an intake reference before acknowledgement. Support owns the case until Finance explicitly accepts its handoff. Finance owns approval and payout, retaining the payment reference, amount and authorised deduction reason. Support closes the case only after evidence and communication checks. Declined cases close through an explained rejection path. A daily exception queue replaces manual comparison of entire sheets.

Use the existing team: one rotating queue owner, named case owners, and ten minutes of joint exception review each day. Automate extraction, joining, reminders and draft preparation. Keep eligibility, deduction approval, ambiguous identity matches, payments and final replies manual.

## Deployment

`render.yaml` describes a free Render Python service. Build: `pip install -r requirements.txt`. Start: `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT`. Health check: `/_stcore/health`. Free instances may sleep when idle. Streamlit uses a long-lived Python process and WebSockets, so Render is the direct hosting fit. Vercel is unnecessary for this single-service prototype.

GitHub Actions checks the data pipeline on each push. This is CI for the prototype, not a scheduled connection to live business systems.

## AI disclosure and prompt history

Built with ChatGPT/Codex assistance. See `PROMPT_HISTORY.md` for the actual user task prompts available in this session and the development decisions. No invented historical prompts or invented model-evaluation results are included.
