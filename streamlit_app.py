"""JurisLens AI — Streamlit Web Application.

Deployable on Streamlit Community Cloud.
Powered by Google Gemini 2.5 Flash.
"""

import asyncio
import os
import streamlit as st

# Configure Streamlit page layout and metadata
st.set_page_config(
    page_title="JurisLens AI — Legal Document Intelligence",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load environment configuration and fallback
from app.core.config import settings
from app.models.schemas import QARequest, RiskLevel
from app.services.citation_engine import citation_engine
from app.services.comparison_engine import comparison_engine
from app.services.document_parser import document_parser
from app.services.gemini_service import gemini_service

# Sync Streamlit Secrets to environment if available on Streamlit Cloud
try:
    if "GEMINI_API_KEY" in st.secrets:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
        settings.GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

# Custom CSS for accessible, high-contrast legal styling
st.markdown(
    """
    <style>
    .main-title { font-size: 2.2rem; font-weight: 800; color: #38bdf8; margin-bottom: 0.2rem; }
    .sub-title { font-size: 1rem; color: #94a3b8; margin-bottom: 1.5rem; }
    .risk-card { padding: 1rem; border-radius: 8px; border-left: 5px solid #38bdf8; background-color: #1e293b; margin-bottom: 0.8rem; }
    .risk-critical { border-left-color: #ef4444; }
    .risk-high { border-left-color: #f97316; }
    .risk-medium { border-left-color: #f59e0b; }
    .risk-low { border-left-color: #10b981; }
    .citation-tag { background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 0.8rem; border: 1px solid #38bdf8; }
    .missing-card { background-color: rgba(245, 158, 11, 0.1); border: 1px solid #f59e0b; border-radius: 6px; padding: 0.8rem; margin-bottom: 0.6rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Header
col_header, col_badge = st.columns([3, 1])
with col_header:
    st.markdown('<div class="main-title">⚖️ JurisLens AI</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Grounded Legal Assistance & Interactive Document Navigation • Built for PromptWars Top 400</div>',
        unsafe_allow_html=True,
    )
with col_badge:
    st.info("✨ Powered by **Google Gemini 2.5 Flash**")

# Sample Documents Loader
def load_sample_file(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "sample_documents", filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

sample_employment = load_sample_file("employment_agreement_sample.txt")
sample_standard_nda = load_sample_file("nda_standard_mutual.txt")
sample_aggressive_nda = load_sample_file("nda_aggressive_vendor.txt")

# Sidebar Controls
with st.sidebar:
    st.header("📂 Ingest Legal Contract")
    source_type = st.radio(
        "Choose Input Method:",
        ["Sample Contracts (1-Click)", "Upload Document", "Paste Text"],
    )

    contract_text = ""
    doc_title = "Contract Document"

    if source_type == "Sample Contracts (1-Click)":
        sample_choice = st.selectbox(
            "Select Preloaded Sample:",
            [
                "Executive Employment Agreement (25 Clauses)",
                "Standard Mutual NDA",
                "Aggressive Vendor NDA & Indemnity",
            ],
        )
        if "Employment" in sample_choice:
            contract_text = sample_employment
            doc_title = "Executive Employment Agreement"
        elif "Standard" in sample_choice:
            contract_text = sample_standard_nda
            doc_title = "Standard Mutual NDA"
        else:
            contract_text = sample_aggressive_nda
            doc_title = "Aggressive Vendor NDA"

    elif source_type == "Upload Document":
        uploaded_file = st.file_uploader("Upload .txt, .md file", type=["txt", "md"])
        if uploaded_file:
            contract_text = uploaded_file.read().decode("utf-8", errors="replace")
            doc_title = uploaded_file.name

    else:
        doc_title = st.text_input("Document Title", value="Custom Legal Contract")
        contract_text = st.text_area("Paste Agreement Text Here", height=250)

    analyze_clicked = st.button("🔍 Analyze Contract with Gemini 2.5", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("### 🛡️ Why JurisLens?")
    st.caption("Unlike generic AI chatbots that hallucinate terms, JurisLens provides:")
    st.markdown("- 📍 **Side-by-side clause citations**")
    st.markdown("- 🚫 **Zero-hallucination gap detection**")
    st.markdown("- 🔄 **Contract redline comparison**")
    st.markdown("- 📑 **Attorney consultation packet**")

# Session State Initialization
if "current_doc" not in st.session_state:
    st.session_state.current_doc = None
if "current_analysis" not in st.session_state:
    st.session_state.current_analysis = None

if (analyze_clicked or st.session_state.current_analysis is None) and contract_text:
    with st.spinner("Segmenting clauses and evaluating legal risk with Gemini 2.5..."):
        parsed_doc = document_parser.parse_text(contract_text, filename=doc_title)
        analysis = asyncio.run(gemini_service.analyze_document(parsed_doc))
        st.session_state.current_doc = parsed_doc
        st.session_state.current_analysis = analysis

# Main Layout
if st.session_state.current_analysis:
    analysis = st.session_state.current_analysis
    doc = st.session_state.current_doc

    # Score Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Risk Score", f"{analysis.overall_risk_score} / 100", delta=analysis.risk_level.value, delta_color="inverse")
    m2.metric("Document Type", analysis.document_type)
    m3.metric("Segmented Clauses", f"{len(doc.clauses)} Clauses")
    m4.metric("Grounding Confidence", f"{analysis.grounding_confidence}%")

    # Split View: Document Viewer (Left) & Intelligence Findings (Right)
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.subheader(f"📄 Original Clauses: {doc.filename}")
        filter_cat = st.selectbox(
            "Filter Clauses by Category:",
            ["All Categories"] + sorted(list({c.category for c in doc.clauses})),
        )

        for clause in doc.clauses:
            if filter_cat != "All Categories" and clause.category != filter_cat:
                continue
            with st.expander(f"Clause {clause.number}: {clause.title} ({clause.category})", expanded=False):
                st.caption(f"Estimated Page {clause.page_number} • Lines {clause.line_start}-{clause.line_end}")
                st.code(clause.text, language="markdown")

    with right_col:
        st.subheader("🛡️ Grounded Legal Intelligence")
        tab_findings, tab_obligations, tab_missing, tab_brief = st.tabs(
            [
                f"🔍 Risk Findings ({len(analysis.key_findings)})",
                f"📋 Obligations ({len(analysis.obligations_checklist)})",
                f"⚠️ Omissions ({len(analysis.missing_protections)})",
                "📑 Lawyer Packet",
            ]
        )

        with tab_findings:
            st.info(f"**Executive Summary:** {analysis.executive_summary}")
            for f in analysis.key_findings:
                sev_color = (
                    "risk-critical" if f.risk_level == RiskLevel.CRITICAL
                    else "risk-high" if f.risk_level == RiskLevel.HIGH
                    else "risk-medium" if f.risk_level == RiskLevel.MEDIUM
                    else "risk-low"
                )
                st.markdown(
                    f"""
                    <div class="risk-card {sev_color}">
                        <div style="display:flex; justify-content:space-between; margin-bottom: 4px;">
                            <strong>{f.clause_title}</strong>
                            <span class="citation-tag">Clause {f.clause_number}</span>
                        </div>
                        <p style="font-size: 0.9rem; margin-bottom: 4px;"><strong>Plain English:</strong> {f.plain_summary}</p>
                        <p style="font-size: 0.85rem; color: #cbd5e1; margin-bottom: 4px;"><strong>Legal Exposure:</strong> {f.potential_risk}</p>
                        <p style="font-size: 0.85rem; color: #38bdf8;"><strong>Recommended Action:</strong> {f.action_item}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with tab_obligations:
            st.write("Actionable deadlines, duties, and breach consequences:")
            table_data = [
                {
                    "Clause": o.clause_number,
                    "Party": o.party,
                    "Action Required": o.obligation,
                    "Deadline / Trigger": o.deadline_or_trigger,
                    "Consequence": o.consequence,
                }
                for o in analysis.obligations_checklist
            ]
            st.dataframe(table_data, use_container_width=True)

        with tab_missing:
            st.warning("💡 **Critical Silences & Omissions**: What is absent from a contract is often more dangerous than what is included.")
            for m in analysis.missing_protections:
                st.markdown(
                    f"""
                    <div class="missing-card">
                        <h4 style="margin: 0; color: #f59e0b;">⚠️ Missing: {m.topic}</h4>
                        <p style="font-size: 0.85rem; margin: 4px 0;">{m.description}</p>
                        <p style="font-size: 0.8rem; color: #cbd5e1;"><strong>Risk:</strong> {m.significance}</p>
                        <div style="background: rgba(0,0,0,0.2); padding: 6px; border-radius: 4px; font-size: 0.8rem;">
                            <strong>Inquiry to Request:</strong> {m.suggested_inquiry}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with tab_brief:
            brief = gemini_service.generate_lawyer_brief(doc, analysis)
            st.markdown("### 1-Page Attorney Consultation Briefing Packet")
            st.caption("Organized briefing for your licensed legal counsel consultation.")
            st.download_button(
                "📥 Download Attorney Consultation Brief (Markdown)",
                data=brief.formatted_markdown,
                file_name=f"lawyer_brief_{doc.filename}.md",
                mime="text/markdown",
            )
            st.markdown(brief.formatted_markdown)

    # Interactive Grounded Q&A Assistant Section
    st.markdown("---")
    st.subheader("💬 Interactive Grounded Q&A Assistant (Anti-Hallucination Guardrail Active)")
    st.caption("Ask questions about the contract. If a topic is missing from the document, the system explicitly reports it.")

    # Quick test prompts from briefing
    b_col1, b_col2, b_col3 = st.columns(3)
    user_q = ""
    if b_col1.button("📌 Notice Period (Clause 8.2)", use_container_width=True):
        user_q = "What is the required notice period if I resign?"
    if b_col2.button("🚫 Stock Options (Missing Info Test)", use_container_width=True):
        user_q = "What happens to my stock options if I resign?"
    if b_col3.button("⚖️ Non-Compete Restrictions (Clause 9.1)", use_container_width=True):
        user_q = "What are the non-compete restrictions?"

    custom_q = st.text_input("Or type your own question:", value=user_q, placeholder="E.g., What happens to inventions created on personal time?")

    if custom_q:
        with st.spinner("Grounding answer against document clauses..."):
            qa_req = QARequest(document_id=doc.document_id, question=custom_q, user_role="employee")
            qa_res = asyncio.run(gemini_service.answer_question(doc, qa_req))

            if qa_res.is_found_in_document:
                st.success(f"✓ **Grounded in Document** (Confidence: {qa_res.confidence}%)")
            else:
                st.warning("⚠️ **Information Not Found in Document (Zero Hallucination)**")

            st.markdown(f"**Answer:** {qa_res.answer}")

            if qa_res.citations:
                c_links = " • ".join([f"**Clause {c.clause_number}** (Page {c.page_number})" for c in qa_res.citations])
                st.markdown(f"**Verified Sources:** {c_links}")

            if qa_res.lawyer_follow_up:
                st.info(f"⚖️ **Attorney Follow-Up Question:** {qa_res.lawyer_follow_up}")

    # Contract Redline Comparison Section
    st.markdown("---")
    st.subheader("🔄 Contract Redline & Risk Shift Comparison")
    with st.expander("Compare Two Contracts Side-by-Side (e.g. Standard NDA vs Aggressive Vendor NDA)"):
        cmp1, cmp2 = st.columns(2)
        with cmp1:
            doc1_input = st.text_area("Document A (Standard Baseline)", value=sample_standard_nda, height=200)
        with cmp2:
            doc2_input = st.text_area("Document B (Proposed Draft)", value=sample_aggressive_nda, height=200)

        if st.button("Run Side-by-Side Comparison"):
            cmp_res = comparison_engine.compare_documents(
                doc1_text=doc1_input,
                doc2_text=doc2_input,
                doc1_name="Standard Mutual NDA",
                doc2_name="Aggressive Vendor NDA",
            )
            st.error(cmp_res.verdict)
            cmp_table = [
                {
                    "Category": d.category,
                    "Document A": d.doc1_snippet,
                    "Document B": d.doc2_snippet,
                    "Risk Shift": d.risk_shift.replace("_", " "),
                    "Explanation": d.explanation,
                }
                for d in cmp_res.differences
            ]
            st.dataframe(cmp_table, use_container_width=True)

# Footer
st.markdown("---")
st.caption(
    "⚖️ **Legal Notice:** JurisLens AI is an educational document analysis and navigation platform powered by Google Gemini 2.5. "
    "It does not provide legal advice or replace professional legal counsel."
)
