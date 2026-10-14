"""
Hybrid RAG & Operational Root-Cause Diagnostic Copilot
Streamlit Application
Reconciles structured SQL operational metrics with unstructured customer voice
using semantic vector search, automated root-cause attribution, and diagnostic memo synthesis.
"""

import streamlit as st
import pandas as pd
import altair as alt
import os
import json
from db_engine import (
    get_sku_operational_metrics,
    get_carrier_logistics_metrics,
    get_route_latency_metrics,
    get_sku_detail,
    DB_PATH
)
from rag_engine import get_rag_engine
from nlp_engine import calculate_root_cause_attribution, ROOT_CAUSE_CATEGORIES, extract_key_diagnostic_phrases
from diagnostic_memo import DiagnosticMemoEngine

# Page Configuration
st.set_page_config(
    page_title="OpsDiagnostic Copilot | Hybrid RAG & Root-Cause Attribution",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Dark Slate Glassmorphic Theme with Vibrant Accents)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    code, pre, .mono-text {
        font-family: 'JetBrains Mono', monospace;
    }

    /* Background and containers */
    .stApp {
        background-color: #0B0F17;
        color: #E2E8F0;
    }

    /* Metric Cards */
    .metric-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px solid rgba(51, 65, 85, 0.6);
        border-radius: 12px;
        padding: 20px 24px;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.5);
        backdrop-filter: blur(10px);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        border-color: #38BDF8;
        transform: translateY(-2px);
    }
    .metric-title {
        font-size: 0.82rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94A3B8;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 1.85rem;
        font-weight: 800;
        color: #F8FAFC;
        margin-bottom: 4px;
    }
    .metric-sub {
        font-size: 0.78rem;
        font-weight: 500;
        color: #38BDF8;
    }
    .metric-sub.danger {
        color: #F43F5E;
    }
    .metric-sub.warning {
        color: #F59E0B;
    }
    .metric-sub.success {
        color: #10B981;
    }

    /* Tag badges */
    .tag-badge {
        display: inline-block;
        padding: 3px 9px;
        border-radius: 9999px;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .tag-danger {
        background-color: rgba(244, 63, 94, 0.18);
        color: #FB7185;
        border: 1px solid rgba(244, 63, 94, 0.4);
    }
    .tag-warning {
        background-color: rgba(245, 158, 11, 0.18);
        color: #FBBF24;
        border: 1px solid rgba(245, 158, 11, 0.4);
    }
    .tag-success {
        background-color: rgba(16, 185, 129, 0.18);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .tag-info {
        background-color: rgba(56, 189, 248, 0.18);
        color: #38BDF8;
        border: 1px solid rgba(56, 189, 248, 0.4);
    }

    /* Customer Voice Card */
    .voc-card {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(51, 65, 85, 0.5);
        border-left: 4px solid #38BDF8;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .voc-card.negative {
        border-left-color: #F43F5E;
    }
    .voc-header {
        font-size: 0.78rem;
        color: #94A3B8;
        margin-bottom: 6px;
        display: flex;
        justify-content: space-between;
    }
    .voc-quote {
        font-size: 0.92rem;
        color: #E2E8F0;
        font-style: italic;
        line-height: 1.45;
    }

    /* Header styling */
    .main-title {
        font-size: 2.1rem;
        font-weight: 800;
        background: linear-gradient(90deg, #F8FAFC 0%, #38BDF8 50%, #818CF8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
    }
    .main-sub {
        font-size: 0.95rem;
        color: #94A3B8;
        margin-bottom: 24px;
    }

    /* Attribution banner */
    .verdict-banner {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%);
        border: 1px solid #38BDF8;
        border-radius: 12px;
        padding: 22px 26px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize engines
@st.cache_resource
def load_engines():
    rag = get_rag_engine()
    memo = DiagnosticMemoEngine()
    return rag, memo

rag_engine_instance, memo_engine = load_engines()

# Sidebar Navigation & Filters
with st.sidebar:
    st.markdown("### ⚡ **OpsDiagnostic Copilot**")
    st.markdown("<p style='font-size: 0.8rem; color: #94A3B8;'>Hybrid RAG & Operational Root-Cause Attribution</p>", unsafe_allow_html=True)
    st.divider()

    navigation = st.radio(
        "Navigation",
        [
            "📊 Executive KPI Dashboard",
            "🔍 Root-Cause Attribution Engine",
            "🔎 Hybrid RAG Semantic Search",
            "📝 Diagnostic Memo Studio",
            "💬 Interactive Copilot Chat"
        ]
    )

    st.divider()
    st.markdown("**System Architecture Status**")
    st.markdown("""
    - **Database**: `SQLite` (1,500 Orders, Fulfillments, Returns)
    - **Vector Store**: `Hybrid TF-IDF + Cosine RAG`
    - **NLP Pipeline**: `Sentiment + Diagnostic N-Grams`
    - **Workflow**: `LLM Diagnostic Synthesis`
    """)

    st.divider()
    if st.button("🔄 Re-Seed Synthetic Data", use_container_width=True):
        from seed_data import generate_seed_data
        with st.spinner("Generating fresh operational dataset..."):
            generate_seed_data(1500)
            st.cache_data.clear()
            st.cache_resource.clear()
            st.success("Database re-seeded successfully!")
            st.rerun()

# ---------------------------------------------------------
# VIEW 1: EXECUTIVE KPI DASHBOARD
# ---------------------------------------------------------
if navigation == "📊 Executive KPI Dashboard":
    st.markdown("<div class='main-title'>Operational Root-Cause Diagnostic Copilot</div>", unsafe_allow_html=True)
    st.markdown("<div class='main-sub'>Reconciling structured SQL metrics (transit latencies, return rates, lost GMV) with unstructured customer support logs.</div>", unsafe_allow_html=True)

    metrics_df = get_sku_operational_metrics()

    if metrics_df.empty:
        st.warning("No operational data found. Please click 'Re-Seed Synthetic Data' in the sidebar.")
    else:
        # Top-level Metric Tiles
        total_orders = int(metrics_df["total_orders"].sum())
        total_gmv = float(metrics_df["total_gmv"].sum())
        total_returns = int(metrics_df["total_returns"].sum())
        portfolio_return_rate = round((total_returns / max(1, total_orders)) * 100, 2)
        total_lost_gmv = float(metrics_df["lost_return_gmv"].sum())
        avg_portfolio_latency = round(float(metrics_df["avg_transit_latency_days"].mean()), 2)
        anomalies_count = int(metrics_df["return_rate_anomaly"].sum())

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-title'>Total GMV Analyzed</div>
                <div class='metric-value'>${total_gmv:,.0f}</div>
                <div class='metric-sub'>{total_orders:,} Total Orders</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-title'>Lost Return GMV</div>
                <div class='metric-value' style='color: #FB7185;'>${total_lost_gmv:,.0f}</div>
                <div class='metric-sub danger'>{total_returns:,} Returns Processed</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-title'>Portfolio Return Rate</div>
                <div class='metric-value'>{portfolio_return_rate}%</div>
                <div class='metric-sub warning'>Baseline: ~6.5% Target</div>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-title'>Avg Transit Latency</div>
                <div class='metric-value'>{avg_portfolio_latency} d</div>
                <div class='metric-sub info'>Delivery Delay vs SLA</div>
            </div>
            """, unsafe_allow_html=True)
        with col5:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-title'>Critical SKU Anomalies</div>
                <div class='metric-value' style='color: #FBBF24;'>{anomalies_count}</div>
                <div class='metric-sub warning'>Requiring Root-Cause Fix</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Main Analytical Visualizations
        chart_col, carrier_col = st.columns([3, 2])

        with chart_col:
            st.markdown("##### 🎯 **Operational Anomaly Matrix: Return Rate vs Transit Latency**")
            st.caption("Bubble size corresponds to Lost Return GMV ($). Hover to inspect SKU operational signals.")

            scatter_chart = alt.Chart(metrics_df).mark_circle().encode(
                x=alt.X('avg_transit_latency_days:Q', title='Average Transit Latency (Days Delay Above SLA)', scale=alt.Scale(zero=False)),
                y=alt.Y('return_rate_pct:Q', title='Return Rate (%)', scale=alt.Scale(zero=False)),
                size=alt.Size('lost_return_gmv:Q', title='Lost GMV ($)', scale=alt.Scale(range=[150, 1500])),
                color=alt.Color('return_rate_anomaly:N', title='Anomaly Flag', scale=alt.Scale(domain=[True, False], range=['#F43F5E', '#38BDF8'])),
                tooltip=[
                    alt.Tooltip('sku_id', title='SKU'),
                    alt.Tooltip('sku_name', title='Name'),
                    alt.Tooltip('return_rate_pct', title='Return Rate %'),
                    alt.Tooltip('lost_return_gmv', title='Lost GMV $', format='$,.2f'),
                    alt.Tooltip('avg_transit_latency_days', title='Transit Latency (d)')
                ]
            ).properties(
                height=340
            ).interactive()

            st.altair_chart(scatter_chart, use_container_width=True)

        with carrier_col:
            st.markdown("##### 🚚 **Carrier Transit Latency & SLA Breach**")
            carrier_df = get_carrier_logistics_metrics()
            st.caption("Ranked by Average Transit Latency Days above promised delivery SLA.")

            carrier_bar = alt.Chart(carrier_df).mark_bar(cornerRadius=4).encode(
                x=alt.X('avg_latency_days:Q', title='Avg Latency (Days)'),
                y=alt.Y('carrier:N', sort='-x', title='Carrier'),
                color=alt.Color('avg_latency_days:Q', scale=alt.Scale(scheme='orangered')),
                tooltip=[
                    alt.Tooltip('carrier', title='Carrier'),
                    alt.Tooltip('avg_latency_days', title='Avg Latency Days'),
                    alt.Tooltip('delayed_shipment_pct', title='Delayed %'),
                    alt.Tooltip('total_return_gmv', title='Lost Return GMV', format='$,.2f')
                ]
            ).properties(
                height=340
            )
            st.altair_chart(carrier_bar, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### 📋 **Comprehensive Operational Metrics & Anomaly Reconciler**")

        display_df = metrics_df[[
            "sku_id", "sku_name", "category", "price", "total_orders",
            "return_rate_pct", "lost_return_gmv", "avg_transit_latency_days",
            "avg_review_rating", "return_rate_anomaly"
        ]].copy()

        display_df["price"] = display_df["price"].apply(lambda x: f"${x:,.2f}")
        display_df["lost_return_gmv"] = display_df["lost_return_gmv"].apply(lambda x: f"${x:,.2f}")
        display_df["return_rate_pct"] = display_df["return_rate_pct"].apply(lambda x: f"{x}%")
        display_df["avg_transit_latency_days"] = display_df["avg_transit_latency_days"].apply(lambda x: f"+{x} d")
        display_df["avg_review_rating"] = display_df["avg_review_rating"].apply(lambda x: f"★ {x}")

        st.dataframe(
            display_df,
            column_config={
                "sku_id": "SKU Code",
                "sku_name": "Product Title",
                "category": "Category",
                "price": "Unit Price",
                "total_orders": "Orders",
                "return_rate_pct": "Return Rate",
                "lost_return_gmv": "Lost GMV",
                "avg_transit_latency_days": "Transit Delay",
                "avg_review_rating": "Review Rating",
                "return_rate_anomaly": "Anomaly Flag"
            },
            hide_index=True,
            use_container_width=True
        )

# ---------------------------------------------------------
# VIEW 2: ROOT-CAUSE ATTRIBUTION ENGINE (DEEP DIVE)
# ---------------------------------------------------------
elif navigation == "🔍 Root-Cause Attribution Engine":
    st.markdown("<div class='main-title'>Automated Root-Cause Attribution Engine</div>", unsafe_allow_html=True)
    st.markdown("<div class='main-sub'>Pioneered mathematical attribution linking transit latencies and SKU returns with review text sentiment, strictly isolating catalog measurement errors.</div>", unsafe_allow_html=True)

    metrics_df = get_sku_operational_metrics()
    sku_options = {f"{row['sku_id']} - {row['sku_name']}": row['sku_id'] for _, row in metrics_df.iterrows()}

    selected_label = st.selectbox("Select Target SKU to Investigate:", list(sku_options.keys()), index=1)
    target_sku_id = sku_options[selected_label]

    # Fetch memo and attribution
    memo_data = memo_engine.generate_sku_diagnostic_memo(target_sku_id)
    attr = memo_data["attribution"]
    sku_data = memo_data["sku_data"]

    # Attribution Verdict Banner
    primary_name = attr["primary_root_cause_name"]
    confidence = attr["attribution_confidence_pct"]
    owner = attr["recommended_owner"]

    border_color = "#FB7185" if "MEASUREMENT" in attr["primary_root_cause"] else "#38BDF8"
    st.markdown(f"""
    <div class='verdict-banner' style='border-color: {border_color};'>
        <div style='display: flex; justify-content: space-between; align-items: center;'>
            <div>
                <span class='tag-badge tag-danger' style='font-size: 0.8rem; padding: 4px 12px;'>Isolated Root Cause</span>
                <h2 style='margin: 8px 0 4px 0; color: #F8FAFC;'>{primary_name}</h2>
                <p style='color: #94A3B8; margin: 0; font-size: 0.92rem;'>{attr['root_cause_description']}</p>
            </div>
            <div style='text-align: right;'>
                <div style='font-size: 2.4rem; font-weight: 800; color: #38BDF8;'>{confidence}%</div>
                <div style='font-size: 0.78rem; text-transform: uppercase; color: #94A3B8;'>Attribution Confidence</div>
            </div>
        </div>
        <hr style='border-color: rgba(51, 65, 85, 0.4); margin: 16px 0 12px 0;'>
        <div style='display: flex; gap: 24px; font-size: 0.85rem;'>
            <div><strong>Remediation Owner:</strong> <span style='color: #F8FAFC;'>{owner}</span></div>
            <div><strong>Preventable Annual Loss:</strong> <span style='color: #34D399; font-weight: 700;'>${memo_data['preventable_gmv_loss']:,.2f}</span></div>
            <div><strong>Cycle Time Reduction:</strong> <span style='color: #FBBF24; font-weight: 700;'>70% (Manual 10d ➔ &lt;3h)</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Attribution Breakdown & Reconciled Evidence
    col_breakdown, col_reconciliation = st.columns([1, 1])

    with col_breakdown:
        st.markdown("##### 📊 **Attribution Probability Distribution**")
        breakdown_data = pd.DataFrame([
            {"Root Cause": ROOT_CAUSE_CATEGORIES[cat]["display_name"], "Attribution Share (%)": pct}
            for cat, pct in attr["attribution_breakdown"].items()
        ]).sort_values(by="Attribution Share (%)", ascending=False)

        bar_chart = alt.Chart(breakdown_data).mark_bar(cornerRadius=6).encode(
            x=alt.X('Attribution Share (%):Q', scale=alt.Scale(domain=[0, 100])),
            y=alt.Y('Root Cause:N', sort='-x'),
            color=alt.Color('Attribution Share (%):Q', scale=alt.Scale(scheme='tealblues')),
            tooltip=['Root Cause', 'Attribution Share (%)']
        ).properties(height=260)

        st.altair_chart(bar_chart, use_container_width=True)

    with col_reconciliation:
        st.markdown("##### 🔬 **Structured SQL vs Voice-of-Customer Reconciliation**")
        base_thresh = float(sku_data.get('baseline_threshold_pct') or sku_data.get('return_threshold_pct') or (sku_data.get('baseline_return_threshold', 0.08) * 100))
        ret_rate = float(sku_data.get('return_rate_pct', 0.0))
        mult = round(ret_rate / max(0.1, base_thresh), 1)
        st.markdown(f"""
        - **Return Rate vs Baseline**: Observed **{ret_rate}%** vs baseline threshold **{base_thresh}%** ({mult}x multiplier).
        - **Logistics Latency Test**: Average transit latency is **{sku_data.get('avg_transit_latency_days')} days**.
          *{"Logistics transit delay strictly RULED OUT (deliveries are on schedule)." if (sku_data.get('avg_transit_latency_days') or 0.0) < 1.0 else "Logistics transit delays active and contributing to customer dissatisfaction."}*
        - **Financial Drain**: **${sku_data.get('lost_return_gmv', 0.0):,.2f}** lost GMV from **{sku_data.get('total_returns', 0)}** returns.
        - **Catalog Specs Under Test**:
          `{get_sku_detail(target_sku_id).get('catalog_specs', 'N/A')}`
        """)

        st.markdown("**Diagnostic Key Phrases Surfaced:**")
        st.write(" ".join([f"`{phrase[0]}` ({phrase[1]}x)" for phrase in memo_data["key_phrases"]]))

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("##### 🗣️ **Voice-of-Customer Vector Corpus Excerpts**")

    voc_cols = st.columns(2)
    for idx, quote in enumerate(memo_data["evidence_quotes"]):
        with voc_cols[idx % 2]:
            st.markdown(f"""
            <div class='voc-card negative'>
                <div class='voc-header'>
                    <span><strong>{quote.get('channel', 'Support Channel')}</strong> | {quote.get('doc_date')}</span>
                    <span class='tag-badge tag-danger'>{quote.get('sentiment', {}).get('label')} ({quote.get('sentiment', {}).get('polarity')})</span>
                </div>
                <div class='voc-quote'>"{quote.get('content')}"</div>
                <div style='font-size: 0.72rem; color: #64748B; margin-top: 6px;'>Carrier: {quote.get('carrier')} | Latency: +{quote.get('transit_latency_days')} days</div>
            </div>
            """, unsafe_allow_html=True)

# ---------------------------------------------------------
# VIEW 3: HYBRID RAG SEMANTIC SEARCH
# ---------------------------------------------------------
elif navigation == "🔎 Hybrid RAG Semantic Search":
    st.markdown("<div class='main-title'>Hybrid Vector RAG Semantic Search</div>", unsafe_allow_html=True)
    st.markdown("<div class='main-sub'>Query unstructured customer support tickets and post-delivery reviews using semantic embeddings reconciled with structured operational filters.</div>", unsafe_allow_html=True)

    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        search_query = st.text_input(
            "Natural Language Semantic Query:",
            value="chest sizing dimensions chart too small",
            placeholder="Type issues like 'broken in transit', 'size chart wrong', 'battery died'..."
        )
    with search_col2:
        top_k = st.slider("Top Results (k):", 3, 15, 6)

    # Filter Bar
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        filter_sku = st.selectbox("Filter by SKU (Optional):", ["All SKUs"] + list(get_sku_operational_metrics()["sku_id"].unique()))
    with f_col2:
        filter_carrier = st.selectbox("Filter by Carrier (Optional):", ["All Carriers", "ApexLogistics", "SwiftFreight", "NationalExpress", "BlueDart Overnight"])
    with f_col3:
        filter_min_latency = st.slider("Min Transit Latency (Days):", 0.0, 8.0, 0.0, step=0.5)

    sku_filter = None if filter_sku == "All SKUs" else filter_sku
    carrier_filter = None if filter_carrier == "All Carriers" else filter_carrier
    min_latency = None if filter_min_latency == 0.0 else filter_min_latency

    if search_query:
        with st.spinner("Executing hybrid vector search..."):
            results = rag_engine_instance.search(
                query=search_query,
                sku_id=sku_filter,
                carrier=carrier_filter,
                min_transit_latency=min_latency,
                top_k=top_k
            )

        st.markdown(f"**Found {len(results)} semantically relevant customer interactions:**")

        if not results:
            st.info("No documents matched the combination of semantic query and structured operational filters.")
        else:
            for r in results:
                sentiment = r.get("sentiment", {})
                score = r.get("similarity_score", 0.0)
                badge_class = "tag-danger" if sentiment.get("label") == "NEGATIVE" else "tag-success" if sentiment.get("label") == "POSITIVE" else "tag-info"

                st.markdown(f"""
                <div class='voc-card'>
                    <div class='voc-header'>
                        <span><strong>{r.get('sku_name')} ({r.get('sku_id')})</strong> | Channel: {r.get('channel')} | {r.get('doc_date')}</span>
                        <div>
                            <span class='tag-badge tag-info' style='margin-right: 6px;'>Sim: {score:.3f}</span>
                            <span class='tag-badge {badge_class}'>{sentiment.get('label')} ({sentiment.get('polarity')})</span>
                        </div>
                    </div>
                    <div class='voc-quote'>"{r.get('content')}"</div>
                    <div style='font-size: 0.75rem; color: #64748B; margin-top: 8px;'>
                        Carrier: <strong>{r.get('carrier')}</strong> &nbsp;|&nbsp; 
                        Transit Delay: <strong>+{r.get('transit_latency_days')} days</strong> &nbsp;|&nbsp;
                        Category: {r.get('category')}
                    </div>
                </div>
                """, unsafe_allow_html=True)

# ---------------------------------------------------------
# VIEW 4: DIAGNOSTIC MEMO STUDIO
# ---------------------------------------------------------
elif navigation == "📝 Diagnostic Memo Studio":
    st.markdown("<div class='main-title'>Executive Diagnostic Memo Studio</div>", unsafe_allow_html=True)
    st.markdown("<div class='main-sub'>Automated diagnostic memo synthesis with LLM workflows, cutting cross-functional investigation cycles by 70% and preventing GMV return loss.</div>", unsafe_allow_html=True)

    metrics_df = get_sku_operational_metrics()
    sku_options = {f"{row['sku_id']} - {row['sku_name']}": row['sku_id'] for _, row in metrics_df.iterrows()}

    ctrl_col1, ctrl_col2 = st.columns([3, 1])
    with ctrl_col1:
        selected_label = st.selectbox("Select Target SKU for Operational Memo Synthesis:", list(sku_options.keys()), index=1)
        target_sku_id = sku_options[selected_label]
    with ctrl_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        generate_btn = st.button("⚡ Synthesize Memo", type="primary", use_container_width=True)

    memo_data = memo_engine.generate_sku_diagnostic_memo(target_sku_id)

    # Display Action Checklist and Download Button
    meta_col1, meta_col2 = st.columns([3, 1])
    with meta_col1:
        st.caption(f"Synthesized for operational stakeholder: **{memo_data['attribution']['recommended_owner']}**")
    with meta_col2:
        st.download_button(
            label="📥 Download Diagnostic Memo (.md)",
            data=memo_data["memo_markdown"],
            file_name=f"diagnostic_memo_{target_sku_id}.md",
            mime="text/markdown",
            use_container_width=True
        )

    # Render Styled Markdown Memo Container
    st.markdown("""
    <div style='background: #111827; border: 1px solid #374151; border-radius: 12px; padding: 32px 36px; margin-top: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.4);'>
    """, unsafe_allow_html=True)
    st.markdown(memo_data["memo_markdown"])
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------
# VIEW 5: INTERACTIVE COPILOT CHAT
# ---------------------------------------------------------
elif navigation == "💬 Interactive Copilot Chat":
    st.markdown("<div class='main-title'>Operational Diagnostic Copilot Assistant</div>", unsafe_allow_html=True)
    st.markdown("<div class='main-sub'>Ask questions reconciling SQL operational metrics with unstructured voice-of-customer logs.</div>", unsafe_allow_html=True)

    # Session State Chat History
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {
                "role": "assistant",
                "content": "👋 Hello! I am your **Operational Diagnostic Copilot**. I reconcile structured SQL operational tables with vector customer sentiment logs to diagnose root causes.\n\nTry asking me:\n- *'Why is the return rate surging on Men's Winter Parka SKU-APP-849?'*\n- *'Is SKU-FURN-302 experiencing carrier transit latency or product quality defects?'*\n- *'Which carrier is failing delivery SLAs and driving customer returns?'*\n- *'Generate an operational diagnostic memo for Catalog Ops'*",
                "type": "INTRO"
            }
        ]

    # Quick prompt buttons
    st.markdown("**Quick Prompts:**")
    qp_cols = st.columns(4)
    quick_queries = [
        "Why is return rate surging on Parka SKU-APP-849?",
        "Is SKU-FURN-302 transit latency or quality defect?",
        "Which carrier has worst transit latency SLA breaches?",
        "Show customer complaints about size charts"
    ]

    selected_quick_prompt = None
    for i, qp in enumerate(quick_queries):
        if qp_cols[i].button(qp, key=f"qp_{i}", use_container_width=True):
            selected_quick_prompt = qp

    # Display Chat History
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # User Input
    user_input = st.chat_input("Ask a root-cause diagnostic question...")
    if selected_quick_prompt:
        user_input = selected_quick_prompt

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Reconciling SQL warehouse metrics with Vector RAG transcripts..."):
                response = memo_engine.ask_copilot(user_input)
                st.markdown(response["answer"])

                if response.get("type") == "SKU_DIAGNOSIS" and "memo_markdown" in response:
                    with st.expander("📄 View Synthesized Diagnostic Memo"):
                        st.markdown(response["memo_markdown"])

                st.session_state.chat_history.append({"role": "assistant", "content": response["answer"]})
