from pathlib import Path
import pandas as pd
import streamlit as st
from demo_data import demo_tables
from refund_ops import ComplaintAI, draft_reply, load_and_reconcile

st.set_page_config(page_title='BharatTrip refund review', layout='wide')
st.title('BharatTrip refund review')
st.write('Find the handoff gaps. Give every refund an owner and a verifiable next step.')
st.caption('Snapshot: 30 June 2026. Read-only prototype. Actions and messages require human review.')
upload = st.file_uploader('Optional replacement workbook', type=['xlsx'])
source = upload or next(Path(__file__).parent.glob('*.xlsx'), None)
if source is None:
    source = demo_tables()
    st.info('GENERATED DEMO: these illustrative records are not the supplied assessment workbook. Upload your workbook to run the actual analysis. Files are processed in memory.')
else:
    st.success('Analysing supplied workbook. Snapshot fixed at 30 June 2026.')
try:
    cases, escalations, monthly, summary = load_and_reconcile(source)
except Exception as exc:
    st.error(f'Could not analyse workbook: {exc}')
    st.stop()
a,b,c,d = st.columns(4)
a.metric('Support cases', summary['support_cases'])
b.metric('Matched Finance records', summary['matched_cases'])
c.metric('Open escalations', summary['open_escalations'])
d.metric('Closed without Finance paid', summary['issue_counts'].get('support_closed_without_finance_paid',0))
st.subheader('Monthly requests and escalations')
st.caption('February complaints were not logged. Ratios mix older complaint cohorts with new requests; they are workload indicators, not cohort escalation rates.')
st.dataframe(monthly, use_container_width=True)
st.bar_chart(monthly[['requests_logged', 'escalations_raised']], color=['#087f8c','#eb9650'])
st.subheader('Review queue')
priorities = st.multiselect('Priority', ['P1','P2','P3'], default=['P1','P2'])
issue = st.selectbox('Issue', ['All'] + sorted(summary['issue_counts']))
queue = cases[cases.priority.isin(priorities)]
if issue != 'All':
    queue = queue[queue.issues.str.split('; ').map(lambda v: issue in v)]
queue = queue.sort_values(['priority','open_escalations','age_days'], ascending=[True,False,False])
st.dataframe(queue, use_container_width=True, hide_index=True)
st.download_button('Download current queue', queue.to_csv(index=False), 'refund_review_queue.csv', 'text/csv')
if not queue.empty:
    selected = st.selectbox('Inspect case', queue.case_id)
    record = cases.set_index('case_id').loc[selected].to_dict() | {'case_id': selected}
    st.write(record['next_action'])
    st.text_area('Evidence-grounded draft for human review', draft_reply(record), height=130)
    st.dataframe(escalations[escalations.case_id.eq(selected)], hide_index=True)
st.subheader('Local AI complaint triage')
st.caption('TF-IDF compares wording against eight editable example categories. Similarity is not confidence. No external API, no LLM generation, no automated decisions. All outputs are suggestions.')
complaint = st.text_area('Paste a complaint', 'Bhai refund ka kya hua? BLR-MAA wala. 2 hafte ho gaye, koi jawab nahi.')
if st.button('Suggest category'):
    result = ComplaintAI().classify(complaint)
    st.json(result)
    if result['review_required']:
        st.warning('Weak or ambiguous wording match. Human triage required. Hindi/Hinglish coverage is limited.')
st.subheader('Data checks')
st.json(summary['quality'])
st.subheader('Escalations without a usable refund reference')
st.caption('Keep these as distinct complaints until Support verifies their booking identity. They are not automatically new refunds.')
st.dataframe(escalations[escalations.case_id.isna()], hide_index=True, use_container_width=True)
