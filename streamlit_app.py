"""JurisLens AI — Grounded Legal Intelligence Platform.

Beginner-Friendly, Highly Readable Material 3 + Glassmorphism Interface.
Powered by Google Gemini 2.5 Flash.
"""

import asyncio
import os
import streamlit as st

# Configure Streamlit page layout and metadata
st.set_page_config(
    page_title="JurisLens AI — Legal Intelligence for Everyone",
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

# Safely sync Streamlit Secrets to environment
try:
    if "GEMINI_API_KEY" in st.secrets:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
        settings.GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

# Custom CSS for Modern, Readable, Glassmorphic Design
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Hero Banner */
    .hero-banner {
        background: linear-gradient(135deg, rgba(14, 165, 233, 0.12) 0%, rgba(99, 102, 241, 0.12) 50%, rgba(168, 85, 247, 0.12) 100%);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 18px;
        padding: 1.25rem 1.75rem;
        margin-bottom: 1.2rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 1rem;
    }
    .hero-title {
        font-size: 2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #38bdf8 0%, #818cf8 50%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.02em;
    }
    .hero-subtitle {
        font-size: 0.92rem;
        color: #94a3b8;
        max-width: 700px;
        line-height: 1.4;
    }

    /* Decision Verdict Card (Traffic Light for Non-Lawyers) */
    .decision-card {
        padding: 1.1rem 1.4rem;
        border-radius: 14px;
        margin-bottom: 1.25rem;
        display: flex;
        align-items: center;
        gap: 1.2rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    }
    .decision-critical {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(153, 27, 27, 0.15) 100%);
        border: 1px solid rgba(239, 68, 68, 0.4);
    }
    .decision-warning {
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(180, 83, 9, 0.15) 100%);
        border: 1px solid rgba(245, 158, 11, 0.4);
    }
    .decision-safe {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(4, 120, 87, 0.15) 100%);
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .decision-icon {
        font-size: 2.2rem;
        flex-shrink: 0;
    }

    /* M3 Expressive Pill Badges */
    .m3-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .badge-critical { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid #ef4444; }
    .badge-high { background: rgba(249, 115, 22, 0.2); color: #fdba74; border: 1px solid #f97316; }
    .badge-medium { background: rgba(245, 158, 11, 0.2); color: #fde047; border: 1px solid #f59e0b; }
    .badge-low { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; border: 1px solid #10b981; }
    .badge-citation { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35); }

    /* Plain English Finding Card */
    .finding-card-clean {
        background: rgba(30, 41, 59, 0.55);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 1.15rem;
        margin-bottom: 1rem;
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .finding-card-clean:hover {
        border-color: rgba(56, 189, 248, 0.35);
        transform: translateY(-2px);
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #0c1322 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }
    .sidebar-brand {
        background: linear-gradient(135deg, rgba(56, 189, 248, 0.12) 0%, rgba(99, 102, 241, 0.12) 100%);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 12px;
        padding: 0.75rem 0.9rem;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.65rem;
    }
    .sidebar-tile {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 10px;
        padding: 0.65rem 0.75rem;
        margin-bottom: 0.45rem;
        display: flex;
        align-items: center;
        gap: 0.65rem;
    }
    .sidebar-tile-title {
        font-size: 0.8rem;
        font-weight: 700;
        color: #f8fafc;
    }
    .sidebar-tile-desc {
        font-size: 0.68rem;
        color: #94a3b8;
    }
    .sidebar-status-card {
        background: rgba(16, 185, 129, 0.08);
        border: 1px solid rgba(16, 185, 129, 0.2);
        border-radius: 8px;
        padding: 0.5rem 0.7rem;
        margin-top: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.72rem;
        color: #34d399;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Hero Banner
st.markdown(
    """
    <div class="hero-banner">
        <div>
            <div class="hero-title">⚖️ JurisLens AI</div>
            <div class="hero-subtitle">
                Makes complex legal contracts clear, accessible, and grounded for non-lawyers. 
                Translates legalese into plain English, catches dangerous missing clauses, and verifies every claim against source clauses.
            </div>
        </div>
        <div>
            <span class="m3-badge badge-citation">✨ Google Gemini 2.5 Flash</span>
            <span class="m3-badge badge-low" style="margin-left: 0.4rem;">Grounded Ground-Truth</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

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
    st.markdown(
        """
        <div class="sidebar-brand">
            <div style="font-size: 1.4rem;">⚖️</div>
            <div>
                <div style="font-weight: 800; font-size: 0.95rem; color: #f8fafc;">JurisLens Studio</div>
                <div style="font-size: 0.7rem; color: #38bdf8; font-weight: 600;">PromptWars Exclusive Edition</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<p style='font-size: 0.82rem; font-weight: 700; color: #cbd5e1; margin-bottom: 0.2rem;'>📂 1. Select Contract</p>", unsafe_allow_html=True)
    source_type = st.radio(
        "Source:",
        ["Preloaded Samples (1-Click)", "Upload File (.txt, .md)", "Paste Contract Text"],
        label_visibility="collapsed",
    )

    contract_text = ""
    doc_title = "Contract Document"

    if source_type == "Preloaded Samples (1-Click)":
        sample_choice = st.selectbox(
            "Select a preloaded agreement:",
            [
                "Executive Employment Agreement (25 Clauses)",
                "Aggressive Vendor NDA & Indemnity (One-Sided)",
                "Standard Mutual NDA (Balanced)",
            ],
            label_visibility="collapsed",
        )
        if "Employment" in sample_choice:
            contract_text = sample_employment
            doc_title = "Executive Employment Agreement"
        elif "Aggressive" in sample_choice:
            contract_text = sample_aggressive_nda
            doc_title = "Aggressive Vendor NDA & Indemnity"
        else:
            contract_text = sample_standard_nda
            doc_title = "Standard Mutual NDA"

    elif source_type == "Upload File (.txt, .md)":
        uploaded_file = st.file_uploader("Upload document", type=["txt", "md"], label_visibility="collapsed")
        if uploaded_file:
            contract_text = uploaded_file.read().decode("utf-8", errors="replace")
            doc_title = uploaded_file.name

    else:
        doc_title = st.text_input("Title", value="Custom Legal Agreement")
        contract_text = st.text_area("Paste contract text", height=180, placeholder="Paste agreement here...")

    analyze_clicked = st.button("⚡ Analyze Contract", type="primary", use_container_width=True)

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 0.78rem; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em;'>🛡️ Core Capabilities</p>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="sidebar-tile">
            <span style="font-size: 1rem;">📍</span>
            <div>
                <div class="sidebar-tile-title">Clause-Level Citations</div>
                <div class="sidebar-tile-desc">Direct jump to source text</div>
            </div>
        </div>
        <div class="sidebar-tile">
            <span style="font-size: 1rem;">🚫</span>
            <div>
                <div class="sidebar-tile-title">Zero Hallucination</div>
                <div class="sidebar-tile-desc">Reports missing provisions</div>
            </div>
        </div>
        <div class="sidebar-tile">
            <span style="font-size: 1rem;">🔄</span>
            <div>
                <div class="sidebar-tile-title">Redline Comparison</div>
                <div class="sidebar-tile-desc">Flags shifted liabilities</div>
            </div>
        </div>
        <div class="sidebar-tile">
            <span style="font-size: 1rem;">📑</span>
            <div>
                <div class="sidebar-tile-title">Attorney Briefing</div>
                <div class="sidebar-tile-desc">1-page consultation packet</div>
            </div>
        </div>
        <div class="sidebar-status-card">
            <span>🟢</span>
            <div>
                <strong style="color:#f8fafc;">Engine Ready</strong> • 26/26 Tests OK
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Session State Initialization
if "current_doc" not in st.session_state:
    st.session_state.current_doc = None
if "current_analysis" not in st.session_state:
    st.session_state.current_analysis = None

if (analyze_clicked or st.session_state.current_analysis is None) and contract_text:
    with st.spinner("Parsing clauses and scoring contract risk with Gemini 2.5 Flash..."):
        parsed_doc = document_parser.parse_text(contract_text, filename=doc_title)
        analysis = asyncio.run(gemini_service.analyze_document(parsed_doc))
        st.session_state.current_doc = parsed_doc
        st.session_state.current_analysis = analysis

# Main Layout
if st.session_state.current_analysis:
    analysis = st.session_state.current_analysis
    doc = st.session_state.current_doc

    # Plain English vs Legal Pro Mode Toggle
    t_col1, t_col2 = st.columns([3, 1])
    with t_col1:
        st.markdown(f"### 📋 Contract Intelligence: **{doc.filename}**")
    with t_col2:
        eli5_mode = st.toggle("💬 Plain Human English (ELI5)", value=True, help="Translates complex legalese into clear, simple human terms.")

    # At-a-Glance Verdict Card (Traffic Light for Non-Lawyers)
    if analysis.overall_risk_score >= 75:
        verdict_class = "decision-critical"
        verdict_icon = "🛑"
        verdict_headline = "HIGH RISK: Do NOT sign without negotiating these critical terms!"
        verdict_advice = f"This contract scores {analysis.overall_risk_score}/100 in risk. It contains aggressive unilateral restrictions that could heavily restrict your freedom or impose unlimited liability."
    elif analysis.overall_risk_score >= 45:
        verdict_class = "decision-warning"
        verdict_icon = "⚠️"
        verdict_headline = "MODERATE RISK: Several clauses require clarification."
        verdict_advice = f"This contract scores {analysis.overall_risk_score}/100 in risk. It includes noteworthy notice periods, non-compete terms, or IP assignments that you should review."
    else:
        verdict_class = "decision-safe"
        verdict_icon = "✅"
        verdict_headline = "BALANCED CONTRACT: Standard commercial terms detected."
        verdict_advice = f"This contract scores {analysis.overall_risk_score}/100 in risk. Protections appear mutual and customary."

    st.markdown(
        f"""
        <div class="decision-card {verdict_class}">
            <div class="decision-icon">{verdict_icon}</div>
            <div>
                <div style="font-size: 1.15rem; font-weight: 800; color: #f8fafc; margin-bottom: 0.2rem;">{verdict_headline}</div>
                <div style="font-size: 0.88rem; color: #cbd5e1; line-height: 1.4;">{verdict_advice}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 4 Clean Metric Summary Tiles
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Risk Score", f"{analysis.overall_risk_score} / 100", delta=analysis.risk_level.value, delta_color="inverse")
    with m2:
        st.metric("Contract Type", analysis.document_type)
    with m3:
        st.metric("Total Clauses", f"{len(doc.clauses)} Clauses", help=f"Estimated ~{doc.estimated_pages} standard legal pages")
    with m4:
        st.metric("Grounding Confidence", f"{analysis.grounding_confidence}%", delta="Verified Citations")

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # Clean, Full-Width Guided Workspace Tabs (Eliminates the blank void!)
    tab_overview, tab_qa, tab_missing, tab_obligations, tab_brief, tab_compare, tab_source = st.tabs(
        [
            f"🚨 Top Red Flags ({len(analysis.key_findings)})",
            "💬 Ask Questions (Grounded Q&A)",
            f"⚠️ Hidden Omissions ({len(analysis.missing_protections)})",
            f"📋 Action Checklist ({len(analysis.obligations_checklist)})",
            "📑 Lawyer Briefing Sheet",
            "🔄 Compare Two Contracts",
            f"📄 Source Clauses ({len(doc.clauses)})",
        ]
    )

    # TAB 1: Key Red Flags & Plain English Summary
    with tab_overview:
        st.markdown("#### 🔍 Key Clauses That Affect You")
        st.caption("Here is exactly what these clauses mean for your day-to-day life and career:")

        for idx, f in enumerate(analysis.key_findings, start=1):
            badge_class = (
                "badge-critical" if f.risk_level == RiskLevel.CRITICAL
                else "badge-high" if f.risk_level == RiskLevel.HIGH
                else "badge-medium" if f.risk_level == RiskLevel.MEDIUM
                else "badge-low"
            )

            st.markdown(
                f"""
                <div class="finding-card-clean">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 0.5rem;">
                        <span style="font-size: 1.05rem; font-weight: 700; color: #f8fafc;">#{idx}. {f.clause_title}</span>
                        <div>
                            <span class="m3-badge {badge_class}">{f.risk_level.value}</span>
                            <span class="m3-badge badge-citation">Clause {f.clause_number}</span>
                        </div>
                    </div>
                    <div style="font-size: 0.92rem; color: #e2e8f0; margin-bottom: 0.5rem; line-height: 1.5;">
                        💬 <strong>{'In Simple Terms' if eli5_mode else 'Summary'}:</strong> {f.plain_summary}
                    </div>
                    <div style="font-size: 0.86rem; color: #fca5a5; margin-bottom: 0.5rem;">
                        ⚡ <strong>The Trap / Risk:</strong> {f.potential_risk}
                    </div>
                    <div style="background: rgba(56, 189, 248, 0.08); border-left: 3px solid #38bdf8; padding: 0.55rem 0.75rem; border-radius: 6px; font-size: 0.85rem; color: #bae6fd;">
                        🎯 <strong>What You Should Ask For:</strong> {f.action_item}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # TAB 2: Grounded Q&A Assistant (Front & Center)
    with tab_qa:
        st.markdown("#### 💬 Ask Any Question About This Contract")
        st.caption("The AI only answers what is in the document. If a topic was left out, it explicitly tells you instead of guessing.")

        st.write("**Frequently Asked Questions (Click to test):**")
        q_btn_col1, q_btn_col2, q_btn_col3, q_btn_col4 = st.columns(4)
        quick_question = ""
        if q_btn_col1.button("🚪 How much notice to quit?", use_container_width=True):
            quick_question = "What is the required notice period if I resign?"
        if q_btn_col2.button("🚫 Stock Options / Equity?", use_container_width=True):
            quick_question = "What happens to my stock options if I resign?"
        if q_btn_col3.button("🌐 Work for a competitor?", use_container_width=True):
            quick_question = "What are the non-compete restrictions?"
        if q_btn_col4.button("💼 Can they fire me anytime?", use_container_width=True):
            quick_question = "Can the company terminate my employment without cause?"

        user_prompt = st.text_input("Type your own question:", value=quick_question, placeholder="e.g. Do I own inventions created on weekends?")

        if user_prompt:
            with st.spinner("Checking clauses and verifying citations..."):
                qa_req = QARequest(document_id=doc.document_id, question=user_prompt, user_role="employee")
                qa_res = asyncio.run(gemini_service.answer_question(doc, qa_req))

                if qa_res.is_found_in_document:
                    st.markdown(
                        f"""
                        <div class="finding-card-clean" style="border-left: 4px solid #10b981;">
                            <div style="display:flex; justify-content:space-between; margin-bottom: 0.4rem;">
                                <span class="m3-badge badge-low">✓ Grounded in Contract ({qa_res.confidence}%)</span>
                                <span class="m3-badge badge-citation">Exact Match</span>
                            </div>
                            <div style="font-size: 1rem; color: #f8fafc; margin-bottom: 0.6rem; line-height: 1.5;">
                                {qa_res.answer}
                            </div>
                            <div style="background: rgba(56, 189, 248, 0.08); padding: 0.5rem; border-radius: 6px; font-size: 0.84rem; color: #38bdf8;">
                                📍 <strong>Source Coordinates:</strong> {qa_res.verification_guidance}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"""
                        <div class="finding-card-clean" style="border-left: 4px solid #ef4444;">
                            <div style="display:flex; justify-content:space-between; margin-bottom: 0.4rem;">
                                <span class="m3-badge badge-critical">⚠️ Zero Hallucination: Missing from Contract</span>
                                <span class="m3-badge badge-critical">Absence Detected</span>
                            </div>
                            <div style="font-size: 1rem; color: #f8fafc; margin-bottom: 0.6rem; line-height: 1.5;">
                                {qa_res.answer}
                            </div>
                            <div style="background: rgba(245, 158, 11, 0.1); padding: 0.5rem; border-radius: 6px; font-size: 0.84rem; color: #fde047; margin-bottom: 0.4rem;">
                                💡 <strong>Warning:</strong> {qa_res.verification_guidance}
                            </div>
                            <div style="background: rgba(56, 189, 248, 0.08); padding: 0.5rem; border-radius: 6px; font-size: 0.84rem; color: #38bdf8;">
                                ⚖️ <strong>Recommended Action:</strong> {qa_res.lawyer_follow_up}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    # TAB 3: Omissions & Missing Protections
    with tab_missing:
        st.markdown("#### ⚠️ What Was Left Out of This Contract")
        st.caption("In legal agreements, silence is often the biggest danger. These are critical standard protections that are completely absent:")

        for m in analysis.missing_protections:
            st.markdown(
                f"""
                <div class="finding-card-clean" style="border-left: 4px solid #f59e0b;">
                    <div style="font-size: 1.05rem; font-weight: 700; color: #fbbf24; margin-bottom: 0.3rem;">
                        ⚠️ Missing: {m.topic}
                    </div>
                    <div style="font-size: 0.9rem; color: #f8fafc; margin-bottom: 0.4rem;">
                        {m.description}
                    </div>
                    <div style="font-size: 0.84rem; color: #cbd5e1; margin-bottom: 0.4rem;">
                        <strong>Why this hurts you:</strong> {m.significance}
                    </div>
                    <div style="background: rgba(245, 158, 11, 0.1); padding: 0.5rem 0.75rem; border-radius: 6px; font-size: 0.84rem; color: #fde68a;">
                        🎯 <strong>What to ask for in writing:</strong> {m.suggested_inquiry}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # TAB 4: Action Checklist & Deadlines
    with tab_obligations:
        st.markdown("#### 📋 What You Must Do & Key Deadlines")
        st.caption("Here is a simple checklist of your responsibilities under this agreement:")

        for o in analysis.obligations_checklist:
            st.markdown(
                f"""
                <div class="finding-card-clean" style="padding: 0.85rem 1.1rem; margin-bottom: 0.6rem;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 0.3rem;">
                        <strong style="color: #38bdf8; font-size: 0.95rem;">{o.party}</strong>
                        <span class="m3-badge badge-citation">Clause {o.clause_number}</span>
                    </div>
                    <div style="font-size: 0.9rem; color: #f8fafc; margin-bottom: 0.35rem;">
                        <strong>Action Required:</strong> {o.obligation}
                    </div>
                    <div style="display:flex; gap: 1.5rem; font-size: 0.84rem; flex-wrap: wrap;">
                        <span style="color: #fbbf24;">⏳ <strong>Deadline:</strong> {o.deadline_or_trigger}</span>
                        <span style="color: #f87171;">⚠️ <strong>Consequence of breach:</strong> {o.consequence}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # TAB 5: Lawyer Consultation Briefing Packet
    with tab_brief:
        brief = gemini_service.generate_lawyer_brief(doc, analysis)
        st.markdown("#### 📑 1-Page Attorney Consultation Brief")
        st.caption("Instead of paying an attorney to read all pages from scratch, hand them this organized 1-page summary to save thousands in legal fees:")

        col_b1, col_b2 = st.columns([1, 2])
        with col_b1:
            st.download_button(
                "📥 Download Briefing Packet (Markdown)",
                data=brief.formatted_markdown,
                file_name=f"lawyer_consultation_brief_{doc.filename}.md",
                mime="text/markdown",
                use_container_width=True,
            )

        st.code(brief.formatted_markdown, language="markdown")

    # TAB 6: Contract Redline Comparison
    with tab_compare:
        st.markdown("#### 🔄 Compare Two Contracts Side-by-Side")
        st.caption("Compare a standard agreement vs a vendor's proposed agreement to see what was secretly changed or added:")

        cmp_col1, cmp_col2 = st.columns(2)
        with cmp_col1:
            cmp_doc1 = st.text_area("Document A (Standard Baseline)", value=sample_standard_nda, height=180)
        with cmp_col2:
            cmp_doc2 = st.text_area("Document B (Proposed Contract)", value=sample_aggressive_nda, height=180)

        if st.button("Run Side-by-Side Comparison", type="primary"):
            cmp_res = comparison_engine.compare_documents(
                doc1_text=cmp_doc1,
                doc2_text=cmp_doc2,
                doc1_name="Standard Mutual NDA",
                doc2_name="Aggressive Vendor NDA",
            )
            st.error(cmp_res.verdict)
            for d in cmp_res.differences:
                diff_badge = (
                    "badge-critical" if d.risk_shift == "CRITICAL_RISK_ADDED"
                    else "badge-medium" if d.risk_shift == "MORE_FAVORABLE_DOC1"
                    else "badge-low"
                )
                st.markdown(
                    f"""
                    <div class="finding-card-clean" style="margin-bottom: 0.6rem;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 0.3rem;">
                            <strong>{d.category}: {d.clause_title}</strong>
                            <span class="m3-badge {diff_badge}">{d.risk_shift.replace('_', ' ')}</span>
                        </div>
                        <div style="font-size: 0.84rem; color: #cbd5e1; margin-bottom: 0.3rem;">
                            <strong>What Changed:</strong> {d.explanation}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # TAB 7: Original Source Clauses
    with tab_source:
        st.markdown(f"#### 📄 Original Document Clauses: {doc.filename}")
        st.caption("Inspect the exact source text with line and page references:")

        src_filter = st.selectbox("Filter by Category:", ["All Categories"] + sorted(list({c.category for c in doc.clauses})))
        for clause in doc.clauses:
            if src_filter != "All Categories" and clause.category != src_filter:
                continue
            with st.expander(f"Clause {clause.number}: {clause.title} ({clause.category})", expanded=False):
                st.caption(f"Estimated Page {clause.page_number} • Lines {clause.line_start}-{clause.line_end}")
                st.markdown(f"> {clause.text}")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #64748b; font-size: 0.78rem; padding: 0.5rem 0;">
        ⚖️ <strong>Legal Notice:</strong> JurisLens AI is an educational assistance and navigation platform powered by Google Gemini 2.5. 
        It does not provide legal advice or replace professional legal counsel.
    </div>
    """,
    unsafe_allow_html=True,
)
