import streamlit as st


def premium_adequacy_app():
    # ======================
    # STYLE (SAFE FOR SUB-APP)
    # ======================
    st.markdown("""
    <style>
        html, body, [class*="css"]  {
            font-family: 'Segoe UI', sans-serif;
        }
        .title {
            color: #003A8F;
            font-weight: 700;
            letter-spacing: 0.3px;
        }
        .subtitle {
            color: #6B7280;
            font-size: 14px;
            margin-bottom: 28px;
        }
    </style>
    """, unsafe_allow_html=True)

    # ======================
    # HEADER
    # ======================
    st.markdown("<h2 class='title'>Premium Adequacy Assessment</h2>", unsafe_allow_html=True)
    st.markdown(
        "<div class='subtitle'>MNC Insurance • Loss Ratio Based Pricing</div>",
        unsafe_allow_html=True
    )

    # ======================
    # INPUTS
    # ======================
    col1, col2 = st.columns(2)

    with col1:
        last_lr_pct = st.number_input(
            "Latest Loss Ratio (%)",
            min_value=0.0,
            max_value=20_000.0,
            step=1.0,
            format="%.1f",
            key="last_lr_pct"
        )

    with col2:
        target_lr_pct = st.number_input(
            "Target Loss Ratio (%)",
            min_value=1.0,
            max_value=20_000.0,
            step=1.0,
            format="%.1f",
            key="target_lr_pct"
        )

    last_gwp = st.number_input(
        "Latest Gross Written Premium",
        min_value=0.0,
        step=1_000_000.0,
        format="%.0f",
        key="last_gwp"
    )

    st.divider()

    # ======================
    # CALCULATION
    # ======================
    if last_lr_pct > 0 and target_lr_pct > 0 and last_gwp > 0:

        last_lr = last_lr_pct / 100
        target_lr = target_lr_pct / 100

        expected_claim = last_gwp * last_lr
        required_premium = expected_claim / target_lr
        rate_change = (required_premium - last_gwp) / last_gwp

        st.markdown("### Results")

        c1, c2, c3 = st.columns(3)
        c1.metric("Expected Claims", f"{expected_claim:,.0f}")
        c2.metric("Required Premium", f"{required_premium:,.0f}")
        c3.metric("Rate Change", f"{rate_change*100:.2f}%")

        st.markdown("<br>", unsafe_allow_html=True)

        if rate_change <= 0:
            st.success(
                "✅ Current premium level is sufficient to meet the target loss ratio."
            )
        else:
            st.warning(
                f"⚠️ Premium needs to be increased by "
                f"**{rate_change*100:.2f}%** to achieve the target loss ratio."
            )
    else:
        st.info("Please complete all inputs to run the assessment.")
