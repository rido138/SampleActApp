import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go




def load_data():
    return pd.read_excel("Completed Net Loss Ratio by Risk Code dan TSI Range3.xlsx")

df = load_data()




tsi_pml_map = {
    "01. [0, 500 Mio]": 5e8,
    "02. (500 Mio,  1 Bio]": 1e9,
    "03. (1 Bio, 5 Bio]": 5e9,
    "04. (5 Bio, 10 Bio]": 1e10,
    "05. (10 Bio, 25 Bio]": 2.5e10,
    "06. (25 Bio, 50 Bio]": 5e10,
    "07. (50 Bio, 75 Bio]": 7.5e10,
    "08. (75 Bio, 100 Bio]": 1e11,
    "09. (100 Bio, 250 Bio]": 2.5e11,
    "10. (250 Bio, 330 Bio]": 3.3e11,
    "11. (330 Bio, 500 Bio]": 5e11,
    "12. (500 Bio, 750 Bio]": 7.5e11,
    "13. (750 Bio, 1 T]": 1e12,
    "14. (1T, 2T]": 2e12,
    "15. (2 T, 3T]": 3e12,
    "16. > 3T": 5e12
}




def inject_css():
    st.markdown("""
    <style>
      .hero{
        background: linear-gradient(135deg, #003366 0%, #1E5C8A 100%);
        color: white;
        padding: 24px 28px;
        border-radius: 24px;
        box-shadow: 0 18px 46px rgba(0,51,102,0.18);
        margin-bottom: 18px;
        border: 1px solid rgba(255,255,255,0.10);
      }
      .hero h1{
        margin:0 0 6px 0!important;
        color:white!important;
        font-size:32px;
        font-weight:820;
        letter-spacing:-0.02em;
      }
      .hero p{
        margin:0;
        color:rgba(255,255,255,0.90);
        font-size:14.5px;
        line-height:1.55;
      }
      .section-card-header{
        margin: 14px 0 8px 0;
        padding: 12px 15px;
        border-radius: 16px;
        background: #F8FAFC;
        border: 1px solid rgba(0,51,102,0.10);
        box-shadow: 0 8px 22px rgba(15,23,42,0.035);
      }
      .section-card-title{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        font-size: 18px;
        font-weight: 800;
        color: #003366;
        line-height: 1.15;
        letter-spacing: -0.01em;
      }
      .kpi-card.kpi-compact3{
        box-sizing:border-box!important;
        min-height:112px!important;
        padding:14px 18px!important;
        border-radius:22px!important;
        display:flex!important;
        flex-direction:column!important;
        justify-content:flex-start!important;
        align-items:flex-start!important;
        gap:6px!important;
        overflow:hidden!important;
        background:rgba(255,255,255,0.94);
        border:1px solid rgba(0,51,102,0.10);
        box-shadow:0 10px 26px rgba(15,23,42,0.06);
      }
      .kpi-card.kpi-compact3 h4{
        margin:0!important;
        font-size:13px!important;
        line-height:1.15!important;
        font-weight:650!important;
        color:#475569!important;
        white-space:nowrap!important;
        overflow:hidden!important;
        text-overflow:ellipsis!important;
        max-width:100%!important;
      }
      .kpi-card.kpi-compact3 h2{
        margin:0!important;
        font-size:30px!important;
        line-height:1!important;
        font-weight:800!important;
        color:#003366!important;
        white-space:nowrap!important;
        overflow:hidden!important;
        text-overflow:ellipsis!important;
        max-width:100%!important;
      }
      .decision-card{
        padding: 15px 17px;
        border-radius: 18px;
        border: 1px solid rgba(0,51,102,0.12);
        background: #FFFFFF;
        box-shadow: 0 10px 26px rgba(15,23,42,0.055);
        margin: 8px 0 14px 0;
      }
      .decision-title{
        font-size:13px;
        font-weight:800;
        color:#64748B;
        margin-bottom:4px;
      }
      .decision-value{
        font-size:28px;
        font-weight:850;
        color:#003366;
        line-height:1.05;
      }
      .decision-note{
        font-size:12.5px;
        color:#64748B;
        margin-top:5px;
        line-height:1.35;
      }
      .decision-good{
        border-left: 5px solid #138A72;
      }
      .decision-bad{
        border-left: 5px solid #B00020;
      }
      .result-pill{
        display:inline-block;
        padding:9px 14px;
        border-radius:999px;
        font-size:14px;
        font-weight:850;
        margin: 6px 0 10px 0;
      }
      .result-good{
        color:#075E4F;
        background:#E8FFF8;
        border:1px solid rgba(19,138,114,0.25);
      }
      .result-bad{
        color:#9F1239;
        background:#FFF1F2;
        border:1px solid rgba(176,0,32,0.20);
      }
      div.stButton > button[kind="secondary"]{
        border-radius: 12px !important;
        border: 1px solid rgba(0,51,102,0.18) !important;
        color: #003366 !important;
        font-weight: 800 !important;
      }
      div.stButton > button[kind="primary"]{
        border-radius: 12px !important;
        background: #003366 !important;
        border: 1px solid #003366 !important;
        font-weight: 800 !important;
      }
    </style>
    """, unsafe_allow_html=True)

def section_header(title: str):
    st.markdown(f"""
    <div class="section-card-header">
      <div class="section-card-title">{title}</div>
    </div>
    """, unsafe_allow_html=True)

def kpi_card(title, value):
    st.markdown(f"""
    <div class="kpi-card kpi-compact3">
      <h4>{title}</h4>
      <h2>{value}</h2>
    </div>
    """, unsafe_allow_html=True)

def format_bio(x):
    if pd.isna(x):
        return "-"
    return f"{x/1e9:,.2f} Bio"

def format_pct_decimal(x):
    if x is None or pd.isna(x):
        return "-"
    return f"{x*100:.2f}%"

def format_pct_number(x):
    if x is None or pd.isna(x):
        return "-"
    return f"{x:.2f}%"

def safe_float(x, default=np.nan):
    try:
        return float(x)
    except Exception:
        return default

def compute_decision(adj_net_lr, suggested_share, buffer_15, komisi_ojk, ovr, opex=15.0, target_cor=100.0):











    adj_lr_pct = safe_float(adj_net_lr, np.nan) * 100
    suggested_share = max(0.0, safe_float(suggested_share, 0.0))
    buffer_15 = max(0.0, safe_float(buffer_15, 0.0))

    if pd.isna(adj_lr_pct) or (suggested_share <= 0 and buffer_15 <= 0):
        return {
            "cor": np.nan,
            "uw_result": np.nan,
            "optimal_share": 0.0,
            "recommended": False,
            "message": "This risk code is not recommended.",
        }

    cor = adj_lr_pct + komisi_ojk + ovr + opex
    uw_result = 100 - cor

    if cor < target_cor and suggested_share > 0:
        optimal_share = suggested_share
        recommended = True
        message = "Recommended to retain based on current CoR inputs."
    else:
        optimal_share = 0.0
        recommended = False
        message = "Not recommended to retain under current CoR inputs."

    return {
        "cor": cor,
        "uw_result": uw_result,
        "optimal_share": optimal_share,
        "recommended": recommended,
        "message": message,
    }

def render_waterfall(adj_net_lr, komisi_ojk, ovr, opex=15.0):
    adj_lr_pct = safe_float(adj_net_lr, np.nan) * 100
    if pd.isna(adj_lr_pct):
        return

    base = 100.0
    values = [-adj_lr_pct, -komisi_ojk, -ovr, -opex]
    labels = ["Gross Premium", "Net Loss Ratio", "Komisi OJK", "OVR", "OPEX", "Profit/Loss"]
    measures = ["absolute", "relative", "relative", "relative", "relative", "total"]
    final_val = base + sum(values)
    total_color = "#138A72" if final_val > 0 else "#B00020"

    fig = go.Figure(go.Waterfall(
        name="UW Result",
        orientation="v",
        measure=measures,
        x=labels,
        text=[f"{base:.2f}%"] + [f"{v:.2f}%" for v in values] + [f"{final_val:.2f}%"],
        y=[base] + values + [None],
        connector={"line": {"color": "rgba(71,85,105,0.55)"}},
        decreasing={"marker": {"color": "#B00020"}},
        increasing={"marker": {"color": "#003366"}},
        totals={"marker": {"color": total_color}},
    ))

    fig.update_layout(
        height=430,
        margin=dict(l=20, r=20, t=45, b=30),
        title=dict(text="Expected UW Result", x=0.5, font=dict(size=16, color="#003366")),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(title=None, gridcolor="rgba(148,163,184,0.20)", zeroline=False),
        xaxis=dict(title=None),
        showlegend=False,
        font=dict(family="Arial", color="#334155"),
    )

    st.plotly_chart(fig, width="stretch")




def render_optimum_retention(username="guest"):
    inject_css()

    st.markdown("""
    <div class="hero">
      <h1>Retention Optimization Dashboard</h1>
      <p>Optimum share and CoR calculator with the same simple flow as the original FR retention tool.</p>
    </div>
    """, unsafe_allow_html=True)

    section_header("Optimum Share and CoR Calculator")


    risk_selected = st.selectbox("Pilih RISK CODE", options=df["RISK CODE"].dropna().unique())


    tsi_options = df[df["RISK CODE"] == risk_selected]["TSI RANGE"].dropna().unique()
    tsi_selected = st.selectbox("Pilih TSI RANGE", options=tsi_options)


    row = df[(df["RISK CODE"] == risk_selected) & (df["TSI RANGE"] == tsi_selected)]

    if row.empty:
        st.warning("No data for this selection.")
        return

    adj_net_lr = row["ADJ NET LR"].values[0]
    suggested_share = safe_float(row["Suggested Share"].values[0], 0.0)
    buffer_15 = safe_float(row["Buffer 15%"].values[0], 0.0)

    invalid_risk = suggested_share <= 0 and buffer_15 <= 0
    adj_lr_display = np.nan if invalid_risk else safe_float(adj_net_lr, np.nan)


    col1, col2, col3 = st.columns(3)
    with col1:
        kpi_card("Share to Retain", f"{suggested_share*100:.2f}%")
    with col2:
        kpi_card("Buffer 15%", f"{buffer_15*100:.2f}%")
    with col3:
        kpi_card("Net Loss Ratio", "-" if invalid_risk else format_pct_decimal(adj_lr_display))


    pml = tsi_pml_map.get(tsi_selected, None)
    if pml is not None:
        retained_amount = suggested_share * pml
        buffer_amount = buffer_15 * pml

        section_header("Retained in Amount")
        col_a, col_b = st.columns(2)
        with col_a:
            kpi_card("Retained Amount", format_bio(retained_amount))
        with col_b:
            kpi_card("Buffer 15%", format_bio(buffer_amount))

    if suggested_share <= 0:
        st.markdown("""
        <div class="decision-card decision-bad">
          <div class="decision-title">Decision</div>
          <div class="decision-value">Not Recommended</div>
          <div class="decision-note">This risk code is not recommended based on the current selected risk code and TSI range.</div>
        </div>
        """, unsafe_allow_html=True)
        return


    section_header("CoR Simulation")

    with st.form("fr_cor_simulation_form", clear_on_submit=False):
        input_col1, input_col2 = st.columns(2)
        with input_col1:
            komisi_ojk = st.number_input(
                "Masukkan Komisi OJK (%)",
                min_value=0.0,
                max_value=100.0,
                step=0.1,
                format="%.2f",
                value=float(st.session_state.get("fr_komisi_ojk_last", 0.0)),
            )
        with input_col2:
            ovr = st.number_input(
                "Masukkan OVR (%)",
                min_value=0.0,
                max_value=100.0,
                step=0.1,
                format="%.2f",
                value=float(st.session_state.get("fr_ovr_last", 0.0)),
            )

        calculate_clicked = st.form_submit_button("Calculate CoR", type="primary", width="stretch")

    if calculate_clicked:
        st.session_state["fr_komisi_ojk_last"] = float(komisi_ojk)
        st.session_state["fr_ovr_last"] = float(ovr)
        st.session_state["fr_last_result"] = {
            "risk_selected": str(risk_selected),
            "tsi_selected": str(tsi_selected),
            "komisi_ojk": float(komisi_ojk),
            "ovr": float(ovr),
        }

    last_result = st.session_state.get("fr_last_result")
    can_show_result = (
        isinstance(last_result, dict)
        and last_result.get("risk_selected") == str(risk_selected)
        and last_result.get("tsi_selected") == str(tsi_selected)
    )

    if can_show_result:
        komisi_ojk = float(last_result.get("komisi_ojk", 0.0))
        ovr = float(last_result.get("ovr", 0.0))
        decision = compute_decision(adj_net_lr, suggested_share, buffer_15, komisi_ojk, ovr)

        cor = decision["cor"]
        optimal_share = decision["optimal_share"]
        optimal_amount = (optimal_share * pml) if pml is not None else np.nan


        decision_cls = "decision-good" if decision["recommended"] else "decision-bad"
        decision_label = "Recommended" if decision["recommended"] else "Not Recommended"

        st.markdown(f"""
        <div class="decision-card {decision_cls}">
          <div class="decision-title">Optimized Retention Decision</div>
          <div class="decision-value">Optimal Share: {optimal_share*100:.2f}%</div>
          <div class="decision-note">{decision_label}. {decision["message"]}</div>
          <div class="decision-note">Optimal Retained Amount: {format_bio(optimal_amount) if pml is not None else "-"}</div>
        </div>
        """, unsafe_allow_html=True)

        if pd.notna(cor) and cor < 100:
            st.markdown(f'<span class="result-pill result-good">📊 CoR = {cor:.2f}%</span>', unsafe_allow_html=True)
        elif pd.notna(cor):
            st.markdown(f'<span class="result-pill result-bad">📊 CoR = {cor:.2f}%</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="result-pill result-bad">📊 CoR = -</span>', unsafe_allow_html=True)

        render_waterfall(adj_net_lr, komisi_ojk, ovr)




def _inject_super_fr_router_css():
    st.markdown(
        """
        <style>
          div[class*="st-key-super_fr_active_page"] div[role="radiogroup"] {
            display: flex;
            gap: 8px;
            padding: 5px;
            margin-bottom: 14px;
            border-radius: 15px;
            background: #F1F5F9;
            border: 1px solid rgba(0, 51, 102, 0.10);
            width: fit-content;
          }
          div[class*="st-key-super_fr_active_page"] label {
            padding: 7px 13px !important;
            border-radius: 11px !important;
            font-weight: 800 !important;
            color: #475569 !important;
          }
          div[class*="st-key-super_fr_active_page"] label:has(input:checked) {
            background: #003366 !important;
            color: #FFFFFF !important;
            box-shadow: 0 5px 14px rgba(0, 51, 102, 0.18);
          }
          div[class*="st-key-super_fr_active_page"] label:has(input:checked) p {
            color: #FFFFFF !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main(username="guest"):

    _inject_super_fr_router_css()

    selected_page = st.radio(
        "Super FR",
        options=["FR Risk Profile", "FR Optimum Retention"],
        horizontal=True,
        key="super_fr_active_page",
        label_visibility="collapsed",
    )

    if selected_page == "FR Risk Profile":


        from fr_risk_profileapp import dashboard as fr_risk_profile_dashboard
        fr_risk_profile_dashboard(username)
    else:
        render_optimum_retention(username)



def dashboard(username="guest"):
    main(username)


def dashboard1(username="guest"):
    main(username)




def preload_workbooks():
    load_data()


if __name__ == "__main__":
    main()
