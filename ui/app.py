"""qu — Streamlit Demo UI for the Linex Profiler Quant Agent.

Run: streamlit run ui/app.py (from the linexProfiler directory)
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis.feature_engine import compute_features
from analysis.preprocessor import (
    clean_transactions,
    load_test_user,
    parse_csv_transactions,
)
from cards.catalog import CardCatalog
from config import CARDS_PATH, TEST_USERS_DIR
from models.features import UserFeatures

st.set_page_config(
    page_title="qu — Linex Financial Quant",
    page_icon="📊",
    layout="wide",
)

# --- Sidebar Navigation ---
st.sidebar.title("qu")
st.sidebar.caption("Profiler Quant Agent")

page = st.sidebar.radio(
    "Navigate",
    ["User Profiler"],
)

# --- Helpers ---

def get_test_user_ids() -> list[str]:
    """List available test user IDs."""
    if not TEST_USERS_DIR.exists():
        return []
    ids = []
    for f in sorted(TEST_USERS_DIR.iterdir()):
        if f.name.startswith("test-user-") and f.name.endswith(".csv"):
            uid = f.name.replace("test-user-", "").replace(".csv", "")
            ids.append(uid)
    return ids


def render_features(features: UserFeatures):
    """Render computed features as Streamlit UI elements."""

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Spend", f"£{features.total_spend:,.2f}")
    with col2:
        st.metric("Invoices", features.total_invoices)
    with col3:
        st.metric("Unique Products", features.unique_products)
    with col4:
        st.metric("Active Months", features.active_months)

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("Avg Invoice", f"£{features.avg_transaction_value:,.2f}")
    with col6:
        st.metric("Bulk Purchase Ratio", f"{features.bulk_purchase_ratio:.1%}")
    with col7:
        st.metric("Cancellation Rate", f"{features.cancellation_rate:.1%}")
    with col8:
        st.metric("Trend", features.spending_trend.title())

    # Category breakdown chart
    if features.top_categories:
        st.subheader("Category Breakdown")
        cat_data = pd.DataFrame([
            {"Category": c.category.replace("_", " ").title(), "Spend": c.spend, "Pct": c.pct_of_total}
            for c in features.top_categories
        ])
        fig = px.pie(
            cat_data, values="Spend", names="Category",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=350)
        st.plotly_chart(fig, use_container_width=True)

    # Monthly spend distribution
    if features.monthly_spend_distribution:
        st.subheader("Monthly Spend Distribution")
        month_order = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        months_present = [m for m in month_order if m in features.monthly_spend_distribution]
        month_data = pd.DataFrame({
            "Month": months_present,
            "% of Total Spend": [features.monthly_spend_distribution[m] for m in months_present],
        })
        fig2 = px.bar(month_data, x="Month", y="% of Total Spend",
                      color_discrete_sequence=["#FFD700"])
        fig2.update_layout(margin=dict(t=10, b=0), height=300)
        st.plotly_chart(fig2, use_container_width=True)

    # Sample products
    if features.sample_descriptions:
        with st.expander("Sample Products Purchased"):
            for desc in features.sample_descriptions[:20]:
                st.text(f"  • {desc}")


def render_linex_profile_toon(profile, rec):
    """Render the unified linex_profile TOON block combining profile + card recommendations."""
    # Build profile section
    if profile.raw_toon:
        profile_toon = profile.raw_toon
    elif profile.attributes:
        attr_lines = [f"  {key}: {attr.value} [{attr.confidence}]" for key, attr in profile.attributes.items()]
        profile_toon = "linex_profile:\n profile:\n" + "\n".join(attr_lines)
    else:
        profile_toon = "linex_profile:\n profile:"

    # Build card_recommendation section
    if rec.raw_toon:
        rec_toon = rec.raw_toon
    elif rec.recommendations:
        field_names = "card_id,card_name,issuer,fit_score,match,estimated_annual_value,description"
        rec_lines = [f"  recommendations[{len(rec.recommendations)}]{{{field_names}}}:"]
        for r in rec.recommendations:
            rec_lines.append(
                f"   {r.card_id},{r.card_name},{r.issuer},{r.fit_score},"
                f"{r.why_it_matches},{r.estimated_annual_reward_value},{r.description}"
            )
        rec_toon = "linex_profile:\n card_recommendation:\n" + "\n".join(rec_lines)
    else:
        rec_toon = "linex_profile:\n card_recommendation:"

    # Merge into a single linex_profile block:
    # Take profile lines (skip the "linex_profile:" header from rec_toon)
    merged_lines = profile_toon.split("\n")
    for line in rec_toon.split("\n"):
        if line.strip() == "linex_profile:":
            continue  # skip duplicate root
        merged_lines.append(line)

    st.code("\n".join(merged_lines), language=None)


def run_async(coro):
    """Run an async coroutine from Streamlit's sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- Page: User Profiler ---

def _run_profiler_ui(features):
    """Run LLM profiling + card matching and render results."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.warning(
            "Set ANTHROPIC_API_KEY environment variable to enable AI profiling and card matching."
        )
        return

    with st.spinner("Profiling with Claude..."):
        from analysis.profiler import profile_user
        profile = run_async(profile_user(features))

    with st.spinner("Matching credit cards..."):
        from analysis.card_matcher import match_cards
        catalog = CardCatalog(str(CARDS_PATH))
        rec = run_async(match_cards(profile, features, catalog))

    render_linex_profile_toon(profile, rec)


if page == "User Profiler":
    tab1, tab2 = st.tabs(["Test Users", "Upload CSV"])

    with tab1:
        user_ids = get_test_user_ids()
        if not user_ids:
            st.error("No test users found. Check data/test-users/ directory.")
        else:
            selected_id = st.selectbox(
                "Select test user",
                user_ids[:100],
                index=0,
                format_func=lambda x: f"User {x}",
            )

            if st.button("Analyze", key="analyze_test"):
                with st.spinner("Loading transactions..."):
                    user_txns = load_test_user(selected_id)
                    clean = clean_transactions(user_txns)
                    features = compute_features(clean)

                _run_profiler_ui(features)

    with tab2:
        uploaded = st.file_uploader("Upload transaction CSV", type=["csv"])
        if uploaded:
            csv_text = uploaded.read().decode("utf-8")
            customer_id = st.text_input("Customer ID (optional)", value="uploaded")

            if st.button("Analyze Upload", key="analyze_upload"):
                with st.spinner("Processing..."):
                    user_txns = parse_csv_transactions(csv_text, customer_id)
                    clean = clean_transactions(user_txns)
                    features = compute_features(clean)

                _run_profiler_ui(features)


# --- Page: Ask qu ---

elif page == "Ask qu":
    st.title("Ask qu")
    st.write("Ask any question about a person based on their transaction history.")

    user_ids = get_test_user_ids()
    selected_id = st.selectbox("Select test user", user_ids[:100], format_func=lambda x: f"User {x}")

    question = st.text_input(
        "Your question",
        placeholder="Is this person likely a student? What's their estimated income?",
    )

    if st.button("Ask") and question:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            st.error("Set ANTHROPIC_API_KEY environment variable.")
        else:
            with st.spinner("Thinking..."):
                import anthropic
                from config import MODEL
                from utils.formatters import format_features_for_llm

                user_txns = load_test_user(selected_id)
                clean = clean_transactions(user_txns)
                features = compute_features(clean)
                features_toon = format_features_for_llm(features)

                client = anthropic.Anthropic(api_key=api_key)
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=1000,
                    system=(
                        "You are a financial analyst for the Linex loyalty platform. "
                        "Given a user's spending data (in TOON format), answer the question. "
                        "Be specific, cite evidence from the data, and state your confidence level."
                    ),
                    messages=[{
                        "role": "user",
                        "content": f"Based on this spending data:\n\n{features_toon}\n\nQuestion: {question}",
                    }],
                )

                st.markdown("### Answer")
                st.write(response.content[0].text)

            with st.expander("Spending context used"):
                render_features(features)
