from __future__ import annotations

import html
from typing import Iterable

import pandas as pd
import streamlit as st








MAPPING_COLS = ["COB", "Type", "Method", "Branch", "Segment", "TOC", "Currency", "Onerous"]
POLICY_REQUIRED_COLS = ["No Polis", "Tanggal Eff", "Tanggal Exp", "Premi", "Comm"]
POLICY_TEMPLATE_COLS = POLICY_REQUIRED_COLS + MAPPING_COLS
ASSUMPTION_COLS = ["inflation rate", "NPR", "Discount"]

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]





def inject_paa_gmm_css() -> None:
    st.markdown(
        """
        <style>
          :root{
            --sa-blue:#003366;
            --sa-blue-2:#1F5A91;
            --sa-gold:#E39A5B;
            --sa-bg:#F8FAFC;
            --sa-ink:#0F172A;
            --sa-muted:#64748B;
            --sa-border:rgba(0,51,102,.12);
          }
          .paa-hero{
            margin: 0 0 14px 0;
            padding: 18px 20px;
            border-radius: 24px;
            background: linear-gradient(135deg, #003366 0%, #0B3F73 54%, #1F5A91 100%);
            color: #FFFFFF;
            box-shadow: 0 18px 44px rgba(0, 51, 102, .18);
            border: 1px solid rgba(255,255,255,.18);
          }
          .paa-hero h1{
            margin:0;
            font-size: 26px;
            line-height:1.05;
            letter-spacing:-.03em;
            font-weight: 850;
          }
          .paa-hero p{
            margin:6px 0 0 0;
            color: rgba(255,255,255,.82);
            font-size: 13.5px;
            line-height:1.35;
            max-width: 880px;
          }
          .paa-card{
            border: 1px solid var(--sa-border);
            border-radius: 20px;
            background: linear-gradient(180deg, rgba(255,255,255,.98), rgba(248,250,252,.98));
            box-shadow: 0 10px 28px rgba(15,23,42,.055);
            padding: 14px 16px;
            margin: 10px 0 12px 0;
          }
          .paa-section-title{
            color: var(--sa-blue);
            font-size: 18px;
            font-weight: 850;
            letter-spacing:-.02em;
            margin-bottom: 2px;
          }
          .paa-muted{
            color: var(--sa-muted);
            font-size: 12.5px;
            line-height:1.35;
            margin-bottom: 2px;
          }
          .paa-kpi-grid{
            display:grid;
            grid-template-columns: repeat(4, minmax(0,1fr));
            gap:10px;
            margin: 8px 0 8px 0;
          }
          .paa-kpi{
            min-height: 86px;
            padding: 12px 14px;
            border-radius: 18px;
            border: 1px solid rgba(0,51,102,.12);
            background:#FFFFFF;
            box-shadow: 0 8px 20px rgba(15,23,42,.045);
            overflow:hidden;
          }
          .paa-kpi .label{
            color:#64748B;
            font-size: 11.5px;
            font-weight: 760;
            text-transform: uppercase;
            letter-spacing:.02em;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
          }
          .paa-kpi .value{
            margin-top: 5px;
            color:#003366;
            font-size: 25px;
            font-weight: 850;
            line-height:1.05;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
            font-variant-numeric: tabular-nums;
          }
          .paa-pill-strip{
            display:flex;
            flex-wrap:wrap;
            gap:8px;
            margin-top:4px;
          }
          .paa-pill{
            padding:6px 10px;
            border-radius:999px;
            border:1px solid rgba(0,51,102,.14);
            background:#FFFFFF;
            color:#1E3A5F;
            font-weight:760;
            font-size:11.5px;
          }
          .paa-recon{
            text-align:center;
            padding: 52px 18px;
            border-radius: 24px;
            border: 1px dashed rgba(0,51,102,.22);
            background: linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%);
            box-shadow: 0 12px 32px rgba(15,23,42,.05);
          }
          .paa-recon h2{margin:0;color:#003366;font-size:32px;letter-spacing:-.04em;font-weight:900;}
          .paa-recon p{margin:8px 0 0 0;color:#E39A5B;font-weight:900;font-size:20px;}
          .paa-table-wrap{
            width:100%;
            max-height: 430px;
            overflow:auto;
            border:1px solid rgba(0,51,102,.12);
            border-radius:16px;
            background:#FFFFFF;
            box-shadow:0 8px 22px rgba(15,23,42,.04);
            margin-top:8px;
          }
          .paa-table{
            border-collapse:separate;
            border-spacing:0;
            width:100%;
            min-width:900px;
            font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Arial,sans-serif;
          }
          .paa-table th{
            position:sticky;
            top:0;
            z-index:2;
            background:#003366;
            color:#FFFFFF;
            font-size:11px;
            font-weight:820;
            text-align:center;
            padding:10px 9px;
            border-right:1px solid rgba(255,255,255,.16);
            white-space:nowrap;
          }
          .paa-table td{
            font-size:11.4px;
            padding:8px 10px;
            border-bottom:1px solid rgba(15,23,42,.055);
            border-right:1px solid rgba(15,23,42,.045);
            color:#334155;
            background:#FFFFFF;
            white-space:nowrap;
            font-weight:620;
          }
          .paa-table tr:nth-child(even) td{background:#F8FAFC;}
          .paa-table tr:hover td{background:#EEF6FF;}
          .paa-table .num{text-align:right;font-variant-numeric:tabular-nums;}
          .paa-table .txt{text-align:left;color:#1E3A5F;font-weight:720;}
          div[role="radiogroup"][aria-label="Measurement model"]{
            display:inline-flex !important;
            gap:8px !important;
            padding:4px !important;
            background:#F1F5F9 !important;
            border:1px solid rgba(0,51,102,.10) !important;
            border-radius:999px !important;
          }
          div[role="radiogroup"][aria-label="Measurement model"] label{
            border-radius:999px !important;
            padding:8px 18px !important;
            margin:0 !important;
            border:1px solid transparent !important;
            background:transparent !important;
            font-weight:800 !important;
            color:#334155 !important;
          }
          div[role="radiogroup"][aria-label="Measurement model"] label:has(input:checked){
            background:linear-gradient(135deg,#003366,#1F5A91) !important;
            color:#FFFFFF !important;
            box-shadow:0 8px 18px rgba(0,51,102,.18) !important;
          }
          div[role="radiogroup"][aria-label="Measurement model"] label:has(input:checked) *{color:#FFFFFF !important;-webkit-text-fill-color:#FFFFFF !important;}
          div[role="radiogroup"][aria-label="Measurement model"] input, div[role="radiogroup"][aria-label="Measurement model"] svg{display:none !important;}
          @media(max-width:900px){.paa-kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr));}}
        </style>
        """,
        unsafe_allow_html=True,
    )





def _safe_download_button(label: str, data: bytes, file_name: str, mime: str) -> None:
    pass


def _fmt_amount(x: float, decimals: int = 0) -> str:
    pass


def _fmt_pct(x: float) -> str:
    pass


def _month_label(ts: pd.Timestamp) -> str:
    pass


def _month_diff_exclusive(start: pd.Timestamp, end: pd.Timestamp) -> int:
    pass


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    pass






def build_policy_template_bytes() -> bytes:
    pass



def build_assumption_template_bytes() -> bytes:
    pass






def read_excel_from_bytes(file_bytes: bytes, sheet_name: str | int = 0) -> pd.DataFrame:
    pass


def validate_policy_df(raw_df: pd.DataFrame) -> pd.DataFrame:
    pass


def read_assumption_df(file_bytes: bytes | None) -> pd.DataFrame:
    pass



def build_monthly_paa_release(validated_policy_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    pass



def build_result_excel_bytes(policy_df: pd.DataFrame, assumption_df: pd.DataFrame, monthly_df: pd.DataFrame, detail_df: pd.DataFrame) -> bytes:
    pass





def render_hero() -> None:
    st.markdown(
        """
        <div class="paa-hero">
          <h1>PAA / GMM Beta</h1>
          
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_model_selector() -> str:

    return st.radio(
        "Measurement model",
        options=["PAA", "GMM"],
        index=0,
        horizontal=True,
        label_visibility="collapsed",
        key="paa_gmm_beta_model",
    )


def render_card(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div class="paa-card">
          <div class="paa-section-title">{html.escape(title)}</div>
          <div class="paa-muted">{html.escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(policy_df: pd.DataFrame, monthly_df: pd.DataFrame) -> None:
    pass


def render_html_table(df: pd.DataFrame, amount_cols: Iterable[str] = (), pct_cols: Iterable[str] = (), max_rows: int = 300) -> None:
    pass


def render_release_charts(monthly_df: pd.DataFrame) -> None:
    pass


def apply_mapping_filters(policy_df: pd.DataFrame) -> pd.DataFrame:
    pass





def render_gmm_placeholder() -> None:
    st.markdown(
        """
        <div class="paa-recon">
          <h2>Under Reconstruction</h2>
          
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_paa_screen(username: str = "guest") -> None:
    st.info("PAA sedang dalam pengembangan.")


def render_paa_gmm_app(username: str = "guest") -> None:
    inject_paa_gmm_css()
    render_hero()
    model = render_model_selector()
    if model == "GMM":
        render_gmm_placeholder()
    else:
        render_paa_screen(username=username)


def dashboard1(username: str = "guest") -> None:

    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = True
    if not st.session_state.get("logged_in", True):
        st.write("Please login from main SuperApp.")
        return
    try:
        render_paa_gmm_app(username=username)
    except Exception as e:
        st.error("Under Reconstruction")
        with st.expander("Technical details", expanded=False):
            st.code(str(e))


def main(username: str = "guest") -> None:
    dashboard1(username)


if __name__ == "__main__":

    main()
