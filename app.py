from pathlib import Path
import pandas as pd
import streamlit as st
from demo_data import demo_tables
from refund_ops import ComplaintAI, draft_reply, load_and_reconcile, reference

st.set_page_config(page_title="Refund review | BharatTrip", layout="wide")
st.title("Refund review")
st.caption("BharatTrip  /  Operations  /  30 June 2026")
upload = st.sidebar.file_uploader("Analyse assessment workbook", type=["xlsx"])
local = next(Path(__file__).parent.glob("*.xlsx"), None)
identity = ("upload", upload.file_id) if upload else (("local", str(local), local.stat().st_mtime_ns) if local else ("demo",))
if st.session_state.get("source_identity") != identity:
    try:
        with st.spinner("Matching Support, Finance and escalation records…"):
            if local or upload:
                with pd.ExcelFile(upload or local) as book:
                    raw = {sheet: book.parse(sheet) for sheet in ["Support_Tracker", "Finance_Tracker", "Escalations"]}
            else:
                raw = demo_tables()
            cases, complaints, monthly, summary = load_and_reconcile(raw, brief_intakes=bool(upload or local))
            cases = cases.sort_values(["priority","open_escalations","age_days"], ascending=[True,False,False]).set_index("case_id", drop=False)
            evidence = {}
            for sheet, field in [("Support_Tracker","Ticket ID"),("Finance_Tracker","Ref No")]:
                evidence[sheet] = dict(tuple(raw[sheet].groupby(raw[sheet][field].map(reference))))
            st.session_state["snapshot"] = cases, complaints, monthly, summary, evidence
            st.session_state["source_identity"] = identity
    except (KeyError, ValueError, OSError) as exc:
        st.error(f"Could not read the required tracker sheets. {exc}")
        st.stop()
cases, complaints, monthly, summary, evidence = st.session_state["snapshot"]
st.sidebar.caption("Generated sample · 10 cases" if identity == ("demo",) else "Using supplied workbook")
page = st.sidebar.radio("Workspace", ["Review queue", "Trends", "Complaint triage"])
labels = {"P1":"Urgent","P2":"Review","P3":"Routine"}
def readable(value):
    return value.replace("_"," ").capitalize()
if page == "Review queue":
    a,b,c = st.columns(3)
    a.metric("Support cases",summary["support_cases"],border=True)
    b.metric("Closed without recorded payout",summary["issue_counts"].get("support_closed_without_finance_paid",0),border=True)
    c.metric("Open complaints",summary["open_escalations"],border=True)
    st.subheader("Case queue")
    @st.fragment
    def inspect_queue():
        left,right = st.columns([1,2])
        priority = left.selectbox("Priority",["All","P1","P2","P3"],format_func=lambda x: labels.get(x,"All priorities"))
        issue = right.selectbox("Issue",["All issues",*sorted(summary["issue_counts"])],format_func=readable)
        rows = cases if priority == "All" else cases[cases.priority.eq(priority)]
        if issue != "All issues":
            rows = rows[rows.issues.str.split("; ").map(lambda flags: issue in flags)]
        st.caption(f"{len(rows):,} matching cases · Select a row to inspect its evidence")
        if rows.empty:
            st.info("No cases match these filters.")
            return
        visible = rows[["case_id","priority","agent","support_status","finance_status","open_escalations"]].copy()
        visible.columns = ["Reference","Priority","Agency","Support","Finance","Open complaints"]
        event = st.dataframe(visible,hide_index=True,on_select="rerun",selection_mode="single-row",
                             key=f"queue_{identity}_{priority}_{issue}",height=270,use_container_width=True)
        idx = event.selection.rows
        case = rows.iloc[idx[0] if idx and idx[0]<len(rows) else 0]
        ref = case.case_id
        st.subheader(ref)
        st.write(case.next_action)
        if case.issues:
            st.caption(" · ".join(readable(x) for x in case.issues.split("; ")))
        with st.expander("Support and Finance evidence"):
            for sheet, records in evidence.items():
                st.write(readable(sheet))
                if ref in records:
                    st.dataframe(records[ref],hide_index=True)
                else:
                    st.caption("No matching record")
            linked = complaints[complaints.case_id.eq(ref)]
            if len(linked):
                st.write("Linked complaints")
                st.dataframe(linked[["Escalation ID","Complaint","Status","Days Open"]],hide_index=True)
        with st.expander("Suggested reply for human review"):
            st.write(draft_reply(case))
        st.download_button("Export matching cases",rows.to_csv(index=False),"review_queue.csv","text/csv",on_click="ignore")
    inspect_queue()
elif page == "Trends":
    st.subheader("Requests and escalations by month")
    counts = monthly.iloc[:,:2].copy()
    counts.columns = ["Requests","Escalations"]
    st.bar_chart(counts,stack=False,color=["#087f8c","#d47836"])
    st.dataframe(monthly)
    st.caption("Complaint logging started in March. Monthly workload includes complaints about earlier requests.")
    with st.expander("Reconciliation checks"):
        st.json(summary["quality"])
else:
    st.subheader("Triage a complaint")
    with st.form("triage"):
        message = st.text_area("Complaint text",placeholder="Paste the agent’s message")
        submit = st.form_submit_button("Suggest category")
    if submit and message.strip():
        result = ComplaintAI().classify(message)
        st.write("Suggested category",readable(result["suggested_category"]))
        st.caption(f"Text similarity {result['similarity']:.2f} · Compare the example before routing")
        st.write(result["matched_example"])
        if result["review_required"]:
            st.warning("Ambiguous wording. Route manually.")
    st.subheader("Complaints awaiting a reference")
    st.dataframe(complaints[complaints.case_id.isna()][["Escalation ID","Complaint","Status","Days Open"]],hide_index=True)

