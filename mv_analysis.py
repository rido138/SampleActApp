import pandas as pd
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
import io
import base64
import json
import html
import altair as alt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import grey
from datetime import datetime
import pytz

# =========================
# DISPLAY ALIASES
# =========================
FIELD_DISPLAY_ALIAS = {
    "FUNCTION": "USAGE",
}

def field_display_name(col) -> str:
    return FIELD_DISPLAY_ALIAS.get(str(col), str(col).replace("_", " "))

# =========================
# PAGE CONFIG
# =========================
#st.set_page_config(page_title="SuperApp Actuary MNC Insurance", page_icon = "logo superapp.png", layout="wide")

# =========================
# GLOBAL THEME
# =========================
st.markdown("""
<style>
  .hero{
    background: linear-gradient(135deg, #003366 0%, #1E5C8A 100%);
    color: white;
    padding: 28px 32px;
    border-radius: 24px;
    box-shadow: 0 18px 46px rgba(0,51,102,0.18);
    margin-bottom: 18px;
    border: 1px solid rgba(255,255,255,0.10);
  }
  .hero h1{margin:0 0 8px 0!important;color:white!important;font-size:34px;font-weight:820;letter-spacing:-0.02em;}
  .hero p{margin:0;color:rgba(255,255,255,0.90);font-size:14.5px;line-height:1.55;}

  .section-card-header{
    margin: 14px 0 8px 0;
    padding: 12px 15px;
    border-radius: 16px;
    background: #F8FAFC;
    border: 1px solid rgba(0,51,102,0.10);
    box-shadow: 0 8px 22px rgba(15,23,42,0.035);
  }
  .section-card-title{font-size:18px;font-weight:800;color:#003366;line-height:1.15;letter-spacing:-0.01em;}
  .section-card-subtitle{font-size:12.5px;color:#64748B;line-height:1.25;margin-top:3px;}

  .kpi-card.kpi-compact3{
    box-sizing:border-box!important;height:122px!important;padding:14px 18px!important;border-radius:22px!important;
    display:flex!important;flex-direction:column!important;justify-content:flex-start!important;align-items:flex-start!important;
    gap:6px!important;overflow:hidden!important;background:rgba(255,255,255,0.94);border:1px solid rgba(0,51,102,0.10);
    box-shadow:0 10px 26px rgba(15,23,42,0.06);
  }
  .kpi-card.kpi-compact3 h4{margin:0!important;font-size:13px!important;line-height:1.15!important;font-weight:650!important;color:#475569!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;max-width:100%!important;}
  .kpi-card.kpi-compact3 h2{margin:0!important;font-size:32px!important;line-height:1!important;font-weight:800!important;color:#003366!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;max-width:100%!important;}
  .kpi-card.kpi-compact3.kpi-gwp h4{white-space:normal!important;display:-webkit-box!important;-webkit-line-clamp:2!important;-webkit-box-orient:vertical!important;}
  @keyframes corFlashTight{0%,100%{transform:translateY(0);box-shadow:0 10px 26px rgba(0,0,0,0.12),0 0 0 2px rgba(190,0,40,.45) inset;}50%{transform:translateY(-3px);box-shadow:0 22px 55px rgba(190,0,40,.34),0 0 0 8px rgba(220,0,50,.92) inset,0 0 28px rgba(255,0,60,.55);}}
  .kpi-card.kpi-compact3.kpi-danger{background:linear-gradient(135deg,#7a0015 0%,#b00020 100%)!important;animation:corFlashTight 1.2s ease-in-out infinite!important;}
  .kpi-card.kpi-compact3.kpi-danger h4,.kpi-card.kpi-compact3.kpi-danger h2{color:white!important;}

  @keyframes toastInOut{0%{transform:translateX(18px);opacity:0;}10%{transform:translateX(0);opacity:1;}85%{transform:translateX(0);opacity:1;}100%{transform:translateX(18px);opacity:0;}}
  .cor-toast{position:fixed;top:84px;right:22px;z-index:9999;width:min(460px,calc(100vw - 44px));padding:14px 16px;border-radius:14px;background:rgba(176,0,32,.96);color:#fff;box-shadow:0 18px 40px rgba(0,0,0,.22);border:1px solid rgba(255,255,255,.20);display:flex;gap:10px;align-items:flex-start;animation:toastInOut 6.2s ease-in-out forwards;}
  .cor-toast .icon{width:22px;height:22px;border-radius:999px;background:rgba(255,255,255,.18);display:flex;align-items:center;justify-content:center;font-weight:900;flex:0 0 auto;margin-top:1px;}
  .cor-toast .txt{font-size:13.5px;line-height:1.25;font-weight:650;}
  .claim-breakdown-toast{top:118px!important;background:linear-gradient(135deg,rgba(12,110,106,.98),rgba(19,141,117,.98))!important;border-left:5px solid #B8FFF1!important;box-shadow:0 22px 50px rgba(8,77,74,.34)!important;animation:toastInOut 5s ease-in-out forwards!important;}

  .direct-download-btn{display:inline-block;width:auto;box-sizing:border-box;text-align:left;padding:0;border-radius:0;background:transparent;color:#003366!important;border:none;text-decoration:underline!important;text-underline-offset:3px;font-weight:700;font-size:13px;}
  .direct-download-btn:hover{color:#E39A5B!important;background:transparent;border:none;}
</style>
""", unsafe_allow_html=True)

# =========================
# CACHING HELPERS
# =========================
def _optimize_mv_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Reduce RAM without changing displayed values or calculations."""
    if df is None or df.empty:
        return df
    out = df.copy()

    # Normalize column names so sidebar widgets are not silently skipped because
    # of leading/trailing spaces in a parquet schema.
    out.columns = [str(col).strip() for col in out.columns]

    # Restore common aliases to the canonical filter field used by the UI.
    if "IS_ELECTRIC" not in out.columns:
        for col in list(out.columns):
            normalized = str(col).strip().upper().replace(" ", "_").replace("-", "_")
            if normalized in {"IS_ELECTRIC", "ISELECTRIC", "ELECTRIC_STATUS", "EV_STATUS"}:
                out = out.rename(columns={col: "IS_ELECTRIC"})
                break

    # Canonicalize Usage into FUNCTION because the uploaded MV files use FUNCTION
    # as the source column, while the dashboard should display it as USAGE.
    if "FUNCTION" not in out.columns:
        for col in list(out.columns):
            normalized = str(col).strip().upper().replace(" ", "_").replace("-", "_")
            if normalized in {"FUNCTION", "USAGE", "USAGE_TYPE", "VEHICLE_USAGE"}:
                out = out.rename(columns={col: "FUNCTION"})
                break

    # Downcast numeric columns where safe. This keeps calculations numeric but lowers RAM.
    for col in out.select_dtypes(include=["int", "int64", "int32"]).columns:
        out[col] = pd.to_numeric(out[col], downcast="integer")
    for col in out.select_dtypes(include=["float", "float64", "float32"]).columns:
        out[col] = pd.to_numeric(out[col], downcast="float")

    # Convert repeated text dimensions to category, but avoid high-cardinality identifiers.
    protected = {"POLICY_NO", "PLAT NO"}
    n_rows = max(len(out), 1)
    for col in out.select_dtypes(include=["object", "string"]).columns:
        if col in protected:
            continue
        nunique = out[col].nunique(dropna=True)
        if nunique and (nunique / n_rows) <= 0.55:
            out[col] = out[col].astype("category")
    return out

@st.cache_data(show_spinner=False, ttl=900, max_entries=3)
def load_parquet(path):
    return _optimize_mv_dtypes(pd.read_parquet(path))

@st.cache_data(show_spinner=False, ttl=900, max_entries=2)
def load_claim_data(path: str):
    return pd.read_parquet(path)

@st.cache_data(show_spinner=False, ttl=900, max_entries=64)
def get_unique_vals(df, col):
    return sorted(df[col].dropna().unique())

@st.cache_data(show_spinner=False, ttl=300, max_entries=32)
def cached_pivot(df, index_cols, row_limit=500):
    return make_pivot(df, list(index_cols), row_limit=row_limit)

def cached_export_pdf(df, name, filters, as_of_date, username):
    return export_pdf(df, name, filters, as_of_date, username)

@st.cache_data(show_spinner=False, ttl=300, max_entries=64)
def cached_export_excel(df, name, filters, as_of_date):
    return export_excel(df, name, filters, as_of_date)

def _download_click_kwargs():
    try:
        parts = st.__version__.split('.')
        major = int(parts[0])
        minor = int(parts[1])
        if (major, minor) >= (1, 43):
            return {"on_click": "ignore"}
    except Exception:
        pass
    return {}

def _sync_multiselect_state(key, options):
    """Return only valid selected values without mutating session_state before widget creation."""
    return [v for v in st.session_state.get(key, []) if v in options]

def _safe_sum(df, col):
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0).sum()
    return 0.0

def _existing_cols(df, cols):
    return [c for c in cols if c in df.columns]

def no_data_warning():
    st.markdown(
    "<div style='text-align:center; color:gray; font-size:16px; padding:40px;'>"
    "No data on this filter"
    "</div>",
    unsafe_allow_html=True
)


def _render_html_block(html_content: str, height: int = 300, scrolling: bool = False) -> None:
    """Render custom HTML with the supported Streamlit components API."""
    components.html(
        html_content,
        height=int(height),
        scrolling=bool(scrolling),
    )

import hashlib
import gc

def short_hash(text, length=12):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length].upper()

def draw_footer(canvas, doc, user):
    canvas.saveState()

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(grey)

    # Waktu download (WIB)
    tz = pytz.timezone("Asia/Jakarta")
    now = datetime.now(tz).strftime("%d %b %Y %H:%M WIB")

    # =========================
    # FOOTER
    # =========================

    # Kiri bawah
    canvas.drawString(
        1.0 * cm,
        0.7 * cm,
        "Prepared by Actuarial Department | Confidential"
    )

    # Kanan bawah
    text_right = f"Downloaded by: {user} | At: {now}"
    canvas.drawRightString(
        doc.pagesize[0] - 1.0 * cm,
        0.7 * cm,
        text_right
    )

    # =========================
    # HEADER (KANAN ATAS)
    # =========================
    hash_value = short_hash(text_right)

    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(
        doc.pagesize[0] - 1.0 * cm,
        doc.pagesize[1] - 0.8 * cm,
        f"Document ID: {hash_value}"
    )

    canvas.restoreState()



def compute_kpis(df):
    gwp = _safe_sum(df, "GWP_AMT")
    gep = _safe_sum(df, "GEP_AMT")
    claim = _safe_sum(df, "GROSS_CLAIM")
    comm = _safe_sum(df, "COMMISSIONS")
    ri_cost = _safe_sum(df, "ERC_AMT")
    ri_rec = _safe_sum(df, "RI_RECOVERY")

    loss_ratio = claim / gep if gep else np.nan
    comm_ratio = comm / gwp if gwp else np.nan
    ri_cost_ratio = ri_cost / gep if gep else np.nan
    ri_rec_ratio = ri_rec / gep if gep else np.nan

    cor = loss_ratio + comm_ratio + ri_cost_ratio - ri_rec_ratio + 0.15

    return {
        "GWP": gwp,
        "Loss Ratio": loss_ratio * 100,
        "COMM Ratio": comm_ratio * 100,
        "RI Cost Ratio": ri_cost_ratio * 100,
        "RI Recovery Ratio": ri_rec_ratio * 100,
        "CoR": cor * 100
    }

def render_kpi_cards(kpis):
    """
    KPI cards using app-level CSS (.kpi-card / .kpi-danger) but with local overrides
    so the cards are landscape (not tall), left-aligned, and never overflow.
    """
    # Local overrides (do NOT touch app.py)
    st.markdown("""
    <style>
      /* Compact KPI layout: landscape, tight title-to-value spacing, left aligned */
      .kpi-card.kpi-compact3{
        box-sizing: border-box !important;
        height: 122px !important;
        padding: 14px 18px !important;
        border-radius: 22px !important;

        display: flex !important;
        flex-direction: column !important;
        justify-content: flex-start !important;
        align-items: flex-start !important;
        text-align: left !important;

        gap: 6px !important;
        overflow: hidden !important;
      }

      .kpi-card.kpi-compact3 h4{
        margin: 0 !important;
        font-size: 13px !important;
        line-height: 1.15 !important;
        font-weight: 600 !important;
        text-align: left !important;

        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        max-width: 100% !important;
        opacity: 0.9 !important;
      }

      /* allow only GWP title to wrap nicely (2 lines max) */
      .kpi-card.kpi-compact3.kpi-gwp h4{
        white-space: normal !important;
        display: -webkit-box !important;
        -webkit-line-clamp: 2 !important;
        -webkit-box-orient: vertical !important;
      }

      .kpi-card.kpi-compact3 h2{
        margin: 0 !important;
        font-size: 34px !important;
        line-height: 1.0 !important;
        font-weight: 800 !important;
        text-align: left !important;

        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        max-width: 100% !important;
      }

      /* Make danger noticeable WITHOUT the huge outer pulse (override app corPulse shadow) */
      @keyframes corBlinkTight {
        0%, 100% { filter: brightness(1); }
        50% { filter: brightness(1.10); }
      }
      .kpi-card.kpi-compact3.kpi-danger{
        animation: corBlinkTight 1.2s infinite !important;
        box-shadow:
          0 10px 26px rgba(0,0,0,0.10),
          0 0 0 2px rgba(255, 204, 213, 0.55) inset !important;
      }

      /* Elegant toast */
      @keyframes toastInOut {
        0%   { transform: translateX(18px); opacity: 0; }
        10%  { transform: translateX(0); opacity: 1; }
        85%  { transform: translateX(0); opacity: 1; }
        100% { transform: translateX(18px); opacity: 0; }
      }
      .cor-toast {
        position: fixed;
        top: 84px;
        right: 22px;
        z-index: 9999;

        width: min(440px, calc(100vw - 44px));
        padding: 14px 16px;
        border-radius: 14px;

        background: rgba(176,0,32,0.95);
        color: #fff;

        box-shadow: 0 18px 40px rgba(0,0,0,0.22);
        border: 1px solid rgba(255,255,255,0.18);

        display: flex;
        gap: 10px;
        align-items: flex-start;

        animation: toastInOut 20.0s ease-in-out forwards;
      }
      .cor-toast .icon{
        width: 22px; height: 22px;
        border-radius: 999px;
        background: rgba(255,255,255,0.18);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 900;
        flex: 0 0 auto;
        margin-top: 1px;
      }
      .cor-toast .txt{
        font-size: 13.5px;
        line-height: 1.25;
        font-weight: 600;
      }}
    </style>
    """, unsafe_allow_html=True)

    def fmt_money(x):
        return f"{int(round(x/1_000_000)):,}".replace(",", ".")

    def fmt_pct(x):
        return f"{round(x):.0f}%" if pd.notna(x) else "-"

    cols = st.columns(6)

    def kpi_box(title, value, extra_cls=""):
        html = f"""
        <div class="kpi-card kpi-compact3 {extra_cls}">
          <h4>{title}</h4>
          <h2>{value}</h2>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)

    with cols[0]:
        kpi_box("Total GWP (Mio)", fmt_money(kpis["GWP"]), "kpi-gwp")

    with cols[1]:
        kpi_box("Loss Ratio", fmt_pct(kpis["Loss Ratio"]))

    with cols[2]:
        kpi_box("Comm Ratio", fmt_pct(kpis["COMM Ratio"]))

    with cols[3]:
        kpi_box("RI Cost Ratio", fmt_pct(kpis["RI Cost Ratio"]))

    with cols[4]:
        kpi_box("RI Recovery", fmt_pct(kpis["RI Recovery Ratio"]))

    cor_value = float(kpis.get("CoR", np.nan)) if pd.notna(kpis.get("CoR", np.nan)) else np.nan
    cor_text = fmt_pct(cor_value)

    with cols[5]:
        danger_cls = "kpi-danger" if pd.notna(cor_value) and cor_value > 100 else ""
        kpi_box("CoR", cor_text, danger_cls)

    # Pop-up (show once per CoR value in this session)
    if pd.notna(cor_value) and cor_value > 100:
        msg = "Bisnis ini mencatatkan rugi (CoR > 100%)."
        # Keying by rounded cor to avoid spamming on each rerun
        key = f"cor_toast_shown_{int(round(cor_value))}"
        if not st.session_state.get(key, False):
            st.session_state[key] = True
            st.markdown(
                f'<div class="cor-toast"><div class="icon">!</div><div class="txt">{msg}</div></div>',
                unsafe_allow_html=True
            )


# =========================
# FUNGSI PIVOT
# =========================
def make_pivot(df, index_cols, row_limit=500):
    index_cols = _existing_cols(df, index_cols)
    if not index_cols:
        return pd.DataFrame()

    values_list = _existing_cols(df, [
        "OUR TSI", "NUMBER OF RISKS", "NUMBER OF CLAIMS", "GWP_AMT", "GEP_AMT", "GROSS_CLAIM",
        "COMMISSIONS", "RI_COST", "ERC_AMT", "RI_RECOVERY"
    ])
    if not values_list:
        return pd.DataFrame()

    pivot = df.pivot_table(
        index=index_cols,
        values=values_list,
        aggfunc="sum",
        fill_value=0,
        observed=True,
    )

    if {"GROSS_CLAIM", "GEP_AMT"}.issubset(pivot.columns):
        pivot["Loss Ratio"] = pivot["GROSS_CLAIM"] / pivot["GEP_AMT"]
    if {"COMMISSIONS", "GWP_AMT"}.issubset(pivot.columns):
        pivot["COMM Ratio"] = pivot["COMMISSIONS"] / pivot["GWP_AMT"]
    if {"ERC_AMT", "GEP_AMT"}.issubset(pivot.columns):
        pivot["RI Cost Ratio"] = pivot["ERC_AMT"] / pivot["GEP_AMT"]
    if {"RI_RECOVERY", "GEP_AMT"}.issubset(pivot.columns):
        pivot["RI Recovery Ratio"] = pivot["RI_RECOVERY"] / pivot["GEP_AMT"]

    for c in ["Loss Ratio", "COMM Ratio", "RI Cost Ratio", "RI Recovery Ratio"]:
        if c not in pivot.columns:
            pivot[c] = np.nan

    pivot["CoR (before OVR)"] = (
        pivot["Loss Ratio"] + pivot["COMM Ratio"] + pivot["RI Cost Ratio"] - pivot["RI Recovery Ratio"] + 0.15
    )

    ratio_cols = ["Loss Ratio", "COMM Ratio", "RI Cost Ratio", "RI Recovery Ratio", "CoR (before OVR)"]
    ratio_cols = [c for c in ratio_cols if c in pivot.columns]
    pivot[ratio_cols] *= 100

    if row_limit is not None and len(pivot) > row_limit:
        pivot = pivot.head(row_limit)

    return pivot

# =========================
# DISPLAY
# =========================
def format_and_display(df, table_key=None):
    """
    Risk Profile-style native HTML table for MV.
    Includes client-side sorting, horizontal scroll, sticky grouping columns,
    and the same visual treatment as Risk Profile while preserving MV column names.
    """
    df = df.copy()

    if isinstance(df.index, pd.MultiIndex):
        df = df.reset_index()
    elif df.index.name is not None:
        df = df.reset_index()

    if "ERC_AMT" in df.columns:
        df = df.drop(columns=["ERC_AMT"])

    metric_order = [
        "OUR TSI", "NUMBER OF RISKS", "NUMBER OF CLAIMS",
        "GWP_AMT", "GEP_AMT", "GROSS_CLAIM",
        "COMMISSIONS", "RI_COST", "RI_RECOVERY",
        "Loss Ratio", "COMM Ratio", "RI Cost Ratio", "RI Recovery Ratio", "CoR (before OVR)"
    ]
    metric_cols = [c for c in metric_order if c in df.columns]
    group_cols = [c for c in df.columns if c not in metric_order]
    final_cols = group_cols + metric_cols
    df = df[final_cols]
    df.replace([np.inf, -np.inf], np.nan, inplace=True)

    if table_key is None:
        table_key = hashlib.sha1(("|".join(map(str, final_cols)) + str(len(df))).encode("utf-8")).hexdigest()[:10]
    table_key = str(table_key).replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_")
    table_dom_id = f"rp_table_{table_key}"

    raw_df = df.copy()
    display_df = df.copy()

    money_cols = ["OUR TSI", "GWP_AMT", "GEP_AMT", "GROSS_CLAIM", "COMMISSIONS", "RI_COST", "RI_RECOVERY"]
    count_cols = ["NUMBER OF RISKS", "NUMBER OF CLAIMS"]
    ratio_cols = [c for c in display_df.columns if ("Ratio" in c or "CoR" in c)]

    for col in money_cols:
        if col in display_df.columns:
            display_df[col] = pd.to_numeric(display_df[col], errors="coerce") / 1_000_000

    def fmt_number(x):
        return "" if pd.isna(x) else f"{int(round(float(x))):,}".replace(",", ".")

    def fmt_percent(x):
        return "" if pd.isna(x) else f"{round(float(x)):.0f}%"

    for col in display_df.columns:
        if col in money_cols or col in count_cols:
            display_df[col] = display_df[col].apply(fmt_number)
        elif col in ratio_cols:
            display_df[col] = display_df[col].apply(fmt_percent)
        else:
            display_df[col] = display_df[col].astype("string").fillna("").astype(str)

    col_alias = {
        "UW_YEAR": "UW YEAR",
        "OUR TSI": "OUR TSI<br><span>IDR Mio</span>",
        "GWP_AMT": "GWP<br><span>IDR Mio</span>",
        "GEP_AMT": "GEP<br><span>IDR Mio</span>",
        "GROSS_CLAIM": "GROSS CLAIM<br><span>IDR Mio</span>",
        "COMMISSIONS": "COMM<br><span>IDR Mio</span>",
        "RI_COST": "RI COST<br><span>IDR Mio</span>",
        "RI_RECOVERY": "RI REC<br><span>IDR Mio</span>",
        "NUMBER OF RISKS": "NO. OF RISKS",
        "NUMBER OF CLAIMS": "NO. OF CLAIMS",
        "Loss Ratio": "LOSS RATIO",
        "COMM Ratio": "COMM RATIO",
        "RI Cost Ratio": "RI COST RATIO",
        "RI Recovery Ratio": "RI REC RATIO",
        "CoR (before OVR)": "CoR",
        "FUNCTION": "USAGE",
    }

    def width_for(col):
        if col in group_cols:
            short_group_widths = {
                "UW_YEAR": 110,
                "AGE": 90,
                "TOB": 90,
                # LOB values are usually longer descriptions/codes, so keep this wider.
                "LOB": 170,
                "IS_ELECTRIC": 120,
                "BRANCH": 130,
                "CATEGORY": 135,
                "FUNCTION": 165,
            }
            if col in short_group_widths:
                return short_group_widths[col]
            return 220
        if col in ["NUMBER OF RISKS", "NUMBER OF CLAIMS"]:
            return 120
        if col in ratio_cols:
            return 115
        if col in money_cols:
            return 135
        return 140

    col_widths = {col: width_for(col) for col in display_df.columns}
    min_table_width = sum(col_widths.values())
    table_height = max(220, min(460, 96 + 34 * len(display_df)))

    css_colgroup = "".join([f"<col style='width:{col_widths[c]}px; min-width:{col_widths[c]}px;'>" for c in display_df.columns])

    sticky_left = {}
    running_left = 0
    for c in display_df.columns:
        if c in group_cols:
            sticky_left[c] = running_left
            running_left += col_widths[c]
        else:
            break

    sort_options_html = "<option value=''>None</option>" + "".join(
        [f"<option value='{i}'>{html.escape(str(c).replace('_', ' '))}</option>" for i, c in enumerate(display_df.columns)]
    )

    header_cells = []
    for c in display_df.columns:
        classes = []
        style = ""
        if c in sticky_left:
            classes.append("sticky-col")
            style = f"left:{sticky_left[c]}px;"
        class_attr = f" class='{' '.join(classes)}'" if classes else ""
        style_attr = f" style='{style}'" if style else ""
        header_cells.append(f"<th{class_attr}{style_attr}>{col_alias.get(c, html.escape(str(c).replace('_', ' ')))}</th>")
    header_cells = "".join(header_cells)

    body_rows = []
    for r in range(len(display_df)):
        row_cells = []
        for col in display_df.columns:
            raw_val = pd.to_numeric(pd.Series([raw_df.iloc[r][col]]), errors="coerce").iloc[0]
            classes = ["text-cell" if col in group_cols else "num-cell"]
            style = ""

            if col in sticky_left:
                classes.append("sticky-col")
                style = f"left:{sticky_left[col]}px;"

            if col == "CoR (before OVR)" and pd.notna(raw_val) and raw_val > 100:
                classes.append("cor-danger")
            elif col == "Loss Ratio" and pd.notna(raw_val) and raw_val > 50:
                classes.append("loss-warning")

            val = html.escape(str(display_df.iloc[r][col]))
            raw_for_sort = raw_df.iloc[r][col]
            sort_val_num = pd.to_numeric(pd.Series([raw_for_sort]), errors="coerce").iloc[0]
            if pd.notna(sort_val_num):
                sort_attr = str(float(sort_val_num))
                sort_type = "num"
            else:
                sort_attr = html.escape(str(raw_for_sort if pd.notna(raw_for_sort) else "").lower())
                sort_type = "text"
            style_attr = f" style='{style}'" if style else ""
            row_cells.append(
                f"<td class='{ ' '.join(classes) }'{style_attr} data-sort='{sort_attr}' data-sort-type='{sort_type}'>{val}</td>"
            )
        body_rows.append(f"<tr>{''.join(row_cells)}</tr>")

    html_table = f"""
    <style>
      html, body {{ margin:0; padding:0; overflow:hidden; background:transparent; }}
      .rp-table-controls {{ display:flex; gap:12px; align-items:center; margin:0 0 14px 0; padding:2px 0 0 0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; flex-wrap:wrap; }}
      .rp-table-controls label {{ font-size:12px; font-weight:650; color:#475569; }}
      .rp-table-controls select, .rp-table-controls button {{ height:34px; border:1px solid rgba(0,51,102,0.16); border-radius:10px; background:#FFFFFF; color:#1F2937; font-size:12px; padding:0 10px; outline:none; }}
      .rp-table-controls select:focus {{ border-color:rgba(0,51,102,0.45); box-shadow:0 0 0 3px rgba(0,51,102,0.08); }}
      .rp-table-controls button {{ cursor:pointer; font-weight:650; color:#003366; }}
      .rp-table-wrap {{ width:100%; max-height:{table_height}px; overflow:auto; border:1px solid rgba(0,51,102,0.12); border-radius:16px; background:#ffffff; box-shadow:0 10px 28px rgba(15,23,42,0.06); }}
      .rp-table {{ border-collapse:separate; border-spacing:0; table-layout:fixed; width:{min_table_width}px; min-width:{min_table_width}px; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Arial,sans-serif; color:#334155; -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility; }}
      .rp-table thead th {{ position:sticky; top:0; z-index:30; background:#003366; color:#ffffff; text-align:center!important; vertical-align:middle; font-size:10.8px; line-height:1.18; font-weight:720; height:46px; padding:8px 8px; border-right:1px solid rgba(255,255,255,0.18); border-bottom:1px solid rgba(0,0,0,0.10); white-space:normal; box-sizing:border-box; }}
      .rp-table thead th span {{ display:block; margin-top:2px; font-size:8.8px; line-height:1.0; font-weight:500; opacity:0.78; }}
      .rp-table tbody td {{ font-size:11.2px; line-height:1.28; height:34px; padding:8px 10px; border-right:1px solid rgba(15,23,42,0.045); border-bottom:1px solid rgba(15,23,42,0.055); background:#ffffff; color:#334155; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; box-sizing:border-box; font-weight:600; }}
      .rp-table tbody tr:nth-child(even) td {{ background:#F8FAFC; }}
      .rp-table tbody tr:hover td {{ background:#EEF6FF; }}
      .rp-table .text-cell {{ text-align:left; font-weight:650; color:#1E3A5F; }}
      .rp-table .num-cell {{ text-align:right; font-variant-numeric:tabular-nums; font-weight:620; color:#334155; }}
      .rp-table .sticky-col {{ position:sticky; z-index:20; box-shadow:2px 0 0 rgba(0,51,102,0.08); }}
      .rp-table thead th.sticky-col {{ z-index:40; background:#002B57; }}
      .rp-table tbody td.sticky-col {{ background:#ffffff; }}
      .rp-table tbody tr:nth-child(even) td.sticky-col {{ background:#F8FAFC; }}
      .rp-table tbody tr:hover td.sticky-col {{ background:#EEF6FF; }}
      .rp-table tbody td.cor-danger {{ background:#FFE7E7!important; color:#9F1239; font-weight:760; }}
      .rp-table tbody td.loss-warning {{ background:#FFF6D8!important; color:#7C4A03; font-weight:740; }}
    </style>
    <div class="rp-table-controls">
      <label for="sort_by_{table_dom_id}">Sort by</label>
      <select id="sort_by_{table_dom_id}">{sort_options_html}</select>
      <select id="sort_order_{table_dom_id}"><option value="desc">Descending</option><option value="asc">Ascending</option></select>
      <button type="button" id="reset_sort_{table_dom_id}">Reset</button>
    </div>
    <div class="rp-table-wrap"><table class="rp-table" id="{table_dom_id}"><colgroup>{css_colgroup}</colgroup><thead><tr>{header_cells}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>
    <script>
      (function() {{
        const table=document.getElementById("{table_dom_id}");
        const sortBy=document.getElementById("sort_by_{table_dom_id}");
        const sortOrder=document.getElementById("sort_order_{table_dom_id}");
        const resetBtn=document.getElementById("reset_sort_{table_dom_id}");
        if(!table||!sortBy||!sortOrder||!resetBtn) return;
        const tbody=table.querySelector("tbody");
        const originalRows=Array.from(tbody.querySelectorAll("tr"));
        function applySort() {{
          const colIndex=sortBy.value;
          if(colIndex==="") {{ tbody.replaceChildren(...originalRows); return; }}
          const idx=parseInt(colIndex,10);
          const asc=sortOrder.value==="asc";
          const rows=Array.from(tbody.querySelectorAll("tr"));
          rows.sort(function(a,b) {{
            const acell=a.children[idx]; const bcell=b.children[idx];
            const atype=acell.getAttribute("data-sort-type"); const btype=bcell.getAttribute("data-sort-type");
            let av=acell.getAttribute("data-sort")||""; let bv=bcell.getAttribute("data-sort")||""; let result=0;
            if(atype==="num"&&btype==="num") {{ result=(parseFloat(av)||0)-(parseFloat(bv)||0); }}
            else {{ result=av.localeCompare(bv, undefined, {{numeric:true, sensitivity:"base"}}); }}
            return asc ? result : -result;
          }});
          tbody.replaceChildren(...rows);
        }}
        sortBy.addEventListener("change", applySort);
        sortOrder.addEventListener("change", applySort);
        resetBtn.addEventListener("click", function() {{ sortBy.value=""; sortOrder.value="desc"; tbody.replaceChildren(...originalRows); }});
      }})();
    </script>
    """
    _render_html_block(html_table, height=table_height + 86, scrolling=False)

# =========================
# PDF EXPORT
# =========================
def get_filtered_claim_detail(risk_detail_df: pd.DataFrame, claim_df: pd.DataFrame) -> pd.DataFrame:
    if risk_detail_df is None or claim_df is None:
        return pd.DataFrame()
    if not isinstance(risk_detail_df, pd.DataFrame) or not isinstance(claim_df, pd.DataFrame):
        return pd.DataFrame()
    if risk_detail_df.empty or claim_df.empty:
        return pd.DataFrame()

    required_cols = {"POLICY_NO", "UW_YEAR"}
    if not required_cols.issubset(risk_detail_df.columns) or not required_cols.issubset(claim_df.columns):
        return pd.DataFrame()

    risk_keys = (
        risk_detail_df[["POLICY_NO", "UW_YEAR"]]
        .dropna()
        .drop_duplicates()
    )
    if risk_keys.empty:
        return pd.DataFrame()

    claim_detail = claim_df.merge(risk_keys, on=["POLICY_NO", "UW_YEAR"], how="inner")
    return claim_detail.reset_index(drop=True)


@st.cache_data(show_spinner=False, ttl=900, max_entries=24)
def cached_filtered_claim_detail(risk_detail_df: pd.DataFrame, claim_path: str = "CLAIM260331.parquet") -> pd.DataFrame:
    claim_df = load_claim_data(claim_path)
    return get_filtered_claim_detail(risk_detail_df, claim_df)


def build_claim_summary_df(claim_df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if claim_df is None or claim_df.empty or group_col not in claim_df.columns:
        return pd.DataFrame(columns=[group_col, "NUMBER OF CLAIMS", "NUMBER OF CLAIMS %", "GROSS CLAIM", "GROSS CLAIM %"])

    tmp = claim_df.copy()
    tmp[group_col] = tmp[group_col].fillna("(Blank)").astype(str)

    if "GROSS CLAIM" in tmp.columns:
        tmp["GROSS CLAIM"] = pd.to_numeric(tmp["GROSS CLAIM"], errors="coerce").fillna(0.0)
    else:
        tmp["GROSS CLAIM"] = 0.0

    if "NUMBER OF CLAIMS" in tmp.columns:
        tmp["NUMBER OF CLAIMS"] = pd.to_numeric(tmp["NUMBER OF CLAIMS"], errors="coerce").fillna(0.0)
    else:
        tmp["NUMBER OF CLAIMS"] = 1.0

    summary = (
        tmp.groupby(group_col, dropna=False, as_index=False)
           .agg(**{
               "NUMBER OF CLAIMS": ("NUMBER OF CLAIMS", "sum"),
               "GROSS CLAIM": ("GROSS CLAIM", "sum"),
           })
           .sort_values(["GROSS CLAIM", "NUMBER OF CLAIMS"], ascending=[False, False], kind="stable")
           .reset_index(drop=True)
    )

    total_claims = float(summary["NUMBER OF CLAIMS"].sum())
    total_gross = float(summary["GROSS CLAIM"].sum())

    summary["NUMBER OF CLAIMS %"] = np.where(total_claims > 0, summary["NUMBER OF CLAIMS"] / total_claims * 100.0, 0.0)
    summary["GROSS CLAIM %"] = np.where(total_gross > 0, summary["GROSS CLAIM"] / total_gross * 100.0, 0.0)
    return summary

def _truncate_claim_label(value, limit: int = 42) -> str:
    text = str(value) if value is not None else ""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def build_claim_breakdown_display_df(claim_df: pd.DataFrame, group_col: str, top_n: int = 9) -> pd.DataFrame:
    summary = build_claim_summary_df(claim_df, group_col)
    if summary is None or summary.empty or group_col not in summary.columns:
        return pd.DataFrame(columns=[group_col, "NUMBER OF CLAIMS %", "GROSS CLAIM %", "LABEL_DISPLAY"])

    out = summary[[group_col, "NUMBER OF CLAIMS %", "GROSS CLAIM %"]].copy()
    out[group_col] = out[group_col].fillna("(Blank)").astype(str)

    if len(out) > top_n:
        top = out.head(top_n).copy()
        others_claim_pct = float(out.iloc[top_n:]["NUMBER OF CLAIMS %"].sum())
        others_gross_pct = float(out.iloc[top_n:]["GROSS CLAIM %"].sum())
        if (others_claim_pct > 0) or (others_gross_pct > 0):
            top = pd.concat([
                top,
                pd.DataFrame({
                    group_col: ["Others"],
                    "NUMBER OF CLAIMS %": [others_claim_pct],
                    "GROSS CLAIM %": [others_gross_pct],
                })
            ], ignore_index=True)
        out = top

    out = out.sort_values(["GROSS CLAIM %", "NUMBER OF CLAIMS %"], ascending=[False, False], kind="stable").reset_index(drop=True)
    out["LABEL_DISPLAY"] = out[group_col].apply(_truncate_claim_label)
    return out


def build_claim_chart_df(claim_df: pd.DataFrame, group_col: str, top_n: int = 9) -> pd.DataFrame:
    display_df = build_claim_breakdown_display_df(claim_df, group_col, top_n=top_n)
    if display_df is None or display_df.empty:
        return pd.DataFrame(columns=[group_col, "LABEL_DISPLAY", "Metric", "Percentage", "PCT_LABEL"])

    plot_df = display_df.melt(
        id_vars=[group_col, "LABEL_DISPLAY"],
        value_vars=["GROSS CLAIM %", "NUMBER OF CLAIMS %"],
        var_name="Metric",
        value_name="Percentage",
    )
    metric_map = {
        "GROSS CLAIM %": "Gross Claim %",
        "NUMBER OF CLAIMS %": "No. of Claims %",
    }
    plot_df["Metric"] = plot_df["Metric"].map(metric_map).fillna(plot_df["Metric"])
    plot_df["PCT_LABEL"] = plot_df["Percentage"].map(lambda x: f"{float(x):.1f}%")
    return plot_df


@st.cache_data(show_spinner=False, ttl=900, max_entries=64)
def cached_claim_chart_df(claim_detail_df: pd.DataFrame, group_col: str, top_n: int = 9) -> pd.DataFrame:
    """Cache chart-ready claim breakdown data by risk-key-filtered claim details."""
    return build_claim_chart_df(claim_detail_df, group_col, top_n=top_n)


def _filter_claim_chart_metrics(
    chart_df: pd.DataFrame,
    show_gross_claim_pct: bool = True,
    show_number_of_claims_pct: bool = False,
) -> pd.DataFrame:
    if chart_df is None or chart_df.empty:
        return pd.DataFrame(columns=["Metric", "Percentage", "LABEL_DISPLAY", "PCT_LABEL"])

    metric_keep = []
    if show_gross_claim_pct:
        metric_keep.append("Gross Claim %")
    if show_number_of_claims_pct:
        metric_keep.append("No. of Claims %")

    if not metric_keep:
        metric_keep = ["Gross Claim %"]

    return chart_df[chart_df["Metric"].isin(metric_keep)].copy()


def render_claim_breakdown_chart(
    chart_df: pd.DataFrame,
    title: str,
    label_col: str,
    show_gross_claim_pct: bool = True,
    show_number_of_claims_pct: bool = False,
) -> None:
    """
    Client-side claim chart.

    The metric toggles are pure HTML/JS inside an iframe, so checking/unchecking
    Gross Claim % or No. of Claims % no longer triggers a Streamlit/Python rerun.
    """
    if chart_df is None or chart_df.empty:
        st.markdown(
            f"<div style='font-size:14px;font-weight:800;color:#003366;margin:4px 0 6px 0;'>{html.escape(title)}</div>",
            unsafe_allow_html=True,
        )
        st.info("No matched claim data for this section.")
        return

    plot_df = chart_df.copy()
    required_cols = {"Metric", "Percentage", "LABEL_DISPLAY"}
    if not required_cols.issubset(plot_df.columns):
        st.info("Claim chart data is not available.")
        return

    order_df = (
        plot_df.pivot_table(
            index=[label_col, "LABEL_DISPLAY"],
            columns="Metric",
            values="Percentage",
            aggfunc="sum",
            fill_value=0,
            observed=True,
        )
        .reset_index()
    )
    for c in ["Gross Claim %", "No. of Claims %"]:
        if c not in order_df.columns:
            order_df[c] = 0.0
    order_df = order_df.sort_values(["Gross Claim %", "No. of Claims %"], ascending=[False, False], kind="stable")

    rows_html = []
    max_pct = max(1.0, float(plot_df["Percentage"].max() or 1.0))
    for _, row in order_df.iterrows():
        label_display = html.escape(str(row.get("LABEL_DISPLAY", "")))
        full_label = html.escape(str(row.get(label_col, row.get("LABEL_DISPLAY", ""))))
        gross = float(row.get("Gross Claim %", 0.0) or 0.0)
        count = float(row.get("No. of Claims %", 0.0) or 0.0)
        gross_w = max(1.0, gross / max_pct * 100.0) if gross > 0 else 0.0
        count_w = max(1.0, count / max_pct * 100.0) if count > 0 else 0.0
        rows_html.append(f'''
          <div class="claim-row" title="{full_label}">
            <div class="claim-label">{label_display}</div>
            <div class="bar-stack">
              <div class="bar-line metric-gross">
                <div class="bar-track"><div class="bar-fill gross" style="width:{gross_w:.4f}%"></div></div>
                <div class="bar-value">{gross:.1f}%</div>
              </div>
              <div class="bar-line metric-count">
                <div class="bar-track"><div class="bar-fill count" style="width:{count_w:.4f}%"></div></div>
                <div class="bar-value">{count:.1f}%</div>
              </div>
            </div>
          </div>
        ''')

    dom_id = "claim_chart_" + hashlib.sha1((title + label_col + str(len(plot_df))).encode("utf-8")).hexdigest()[:10]
    chart_height = max(330, min(660, 132 + 46 * len(order_df)))

    html_chart = f'''
    <style>
      html, body {{
        margin: 0;
        padding: 0;
        background: transparent;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, Arial, sans-serif;
        color: #1E293B;
      }}
      .claim-card {{
        border: 1px solid rgba(0, 51, 102, 0.10);
        border-radius: 16px;
        padding: 14px 14px 12px 14px;
        background: #FFFFFF;
        box-shadow: 0 8px 22px rgba(15,23,42,0.045);
        box-sizing: border-box;
      }}
      .claim-head {{
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
        margin-bottom: 12px;
      }}
      .claim-title {{
        font-size: 14px;
        font-weight: 800;
        color: #003366;
        line-height: 1.15;
      }}
      .claim-controls {{
        display: flex;
        gap: 9px;
        flex-wrap: wrap;
        justify-content: flex-start;
        align-items: center;
        width: 100%;
      }}
      .claim-control-title {{
        font-size: 12px;
        font-weight: 800;
        color: #64748B;
        margin-right: 2px;
      }}
      .claim-controls label {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border: 1px solid rgba(0,51,102,0.16);
        background: #F8FAFC;
        border-radius: 999px;
        padding: 7px 12px;
        font-size: 12.5px;
        font-weight: 800;
        color: #334155;
        cursor: pointer;
        user-select: none;
        box-shadow: 0 4px 12px rgba(15,23,42,0.035);
      }}
      .claim-controls input {{
        width: 16px;
        height: 16px;
        margin: 0;
        accent-color: #003366;
        cursor: pointer;
      }}
      .claim-controls label:has(input:checked) {{
        background: #EEF6FF;
        border-color: rgba(0,51,102,0.34);
        color: #003366;
      }}
      .claim-row {{
        display: grid;
        grid-template-columns: minmax(130px, 28%) minmax(0, 1fr);
        gap: 12px;
        align-items: center;
        padding: 7px 0;
        border-bottom: 1px solid rgba(15,23,42,0.055);
      }}
      .claim-row:last-child {{ border-bottom: none; }}
      .claim-label {{
        font-size: 12px;
        font-weight: 700;
        color: #475569;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      .bar-stack {{ display: grid; gap: 5px; }}
      .bar-line {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) 48px;
        gap: 8px;
        align-items: center;
      }}
      .bar-track {{
        height: 14px;
        border-radius: 999px;
        background: #EEF2F7;
        overflow: hidden;
      }}
      .bar-fill {{
        height: 100%;
        border-radius: 999px;
        min-width: 0;
      }}
      .bar-fill.gross {{ background: linear-gradient(90deg, #003366, #2E5F93); }}
      .bar-fill.count {{ background: linear-gradient(90deg, #E39A5B, #F0B77F); }}
      .bar-value {{
        font-size: 11px;
        font-weight: 800;
        color: #1E293B;
        text-align: right;
        font-variant-numeric: tabular-nums;
      }}
      #{dom_id}.hide-gross .metric-gross {{ display: none; }}
      #{dom_id}.hide-count .metric-count {{ display: none; }}
      @media (max-width: 640px) {{
        .claim-head {{ align-items: flex-start; flex-direction: column; }}
        .claim-controls {{ justify-content: flex-start; }}
        .claim-row {{ grid-template-columns: 1fr; gap: 5px; }}
      }}
    </style>
    <div id="{dom_id}" class="claim-card hide-count">
      <div class="claim-head">
        <div class="claim-title">{html.escape(title)}</div>
        <div class="claim-controls">
          <span class="claim-control-title">Chart display:</span>
          <label><input id="{dom_id}_gross" type="checkbox" checked> Gross Claim %</label>
          <label><input id="{dom_id}_count" type="checkbox"> No. of Claims %</label>
        </div>
      </div>
      <div class="claim-body">
        {''.join(rows_html)}
      </div>
    </div>
    <script>
      (function() {{
        const root = document.getElementById("{dom_id}");
        const gross = document.getElementById("{dom_id}_gross");
        const count = document.getElementById("{dom_id}_count");
        if (!root || !gross || !count) return;
        function sync() {{
          if (!gross.checked && !count.checked) gross.checked = true;
          root.classList.toggle("hide-gross", !gross.checked);
          root.classList.toggle("hide-count", !count.checked);
        }}
        gross.addEventListener("change", sync);
        count.addEventListener("change", sync);
        sync();
      }})();
    </script>
    '''
    _render_html_block(html_chart, height=chart_height, scrolling=False)

def _show_claim_breakdown_hint_once(claim_detail_df: pd.DataFrame) -> None:
    if claim_detail_df is None or claim_detail_df.empty:
        return

    hint_payload = {
        "rows": int(len(claim_detail_df)),
    }
    if {"POLICY_NO", "UW_YEAR"}.issubset(claim_detail_df.columns):
        hint_payload["policy_keys"] = int(
            claim_detail_df[["POLICY_NO", "UW_YEAR"]].drop_duplicates().shape[0]
        )

    hint_sig = hashlib.sha1(
        json.dumps(hint_payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    state_key = f"claim_breakdown_hint_shown__{hint_sig}"

    if st.session_state.get(state_key, False):
        return

    st.session_state[state_key] = True
    st.markdown(
        '''
        <div class="claim-detail-toast"
             style="position: fixed; top: 154px; right: 22px; z-index: 9998; width: min(430px, calc(100vw - 44px)); padding: 14px 16px; border-radius: 14px; background: linear-gradient(135deg, rgba(12,110,106,0.98), rgba(19,141,117,0.98)); color: #FFFFFF; border: 1px solid rgba(184,255,241,0.55); border-left: 5px solid #B8FFF1; box-shadow: 0 22px 50px rgba(8,77,74,0.34); display: flex; gap: 10px; align-items: flex-start; animation: toastInOut 5.5s ease-in-out forwards;">
          <div style="width:22px; height:22px; border-radius:999px; background:rgba(255,255,255,0.22); color:#F4FFFD; display:flex; align-items:center; justify-content:center; font-weight:900; flex:0 0 auto; margin-top:1px;">↓</div>
          <div style="font-size:13.5px; line-height:1.3; font-weight:650; color:#FFFFFF;"><b>Scroll down</b> to see Claim Breakdown details below.</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )


# =========================
# CLAIM BREAKDOWN SNAPSHOT HELPERS
# =========================
def _claim_keys_signature(risk_detail_df: pd.DataFrame) -> str:
    """Signature based only on risk keys that affect Claim Breakdown."""
    try:
        if risk_detail_df is None or risk_detail_df.empty:
            return "empty"
        cols = [c for c in ["POLICY_NO", "UW_YEAR"] if c in risk_detail_df.columns]
        if not cols:
            return "missing_keys"
        tmp = risk_detail_df[cols].dropna().drop_duplicates().copy()
        for c in cols:
            tmp[c] = tmp[c].astype("string").fillna("")
        tmp = tmp.sort_values(cols).reset_index(drop=True)
        payload = tmp.to_json(orient="split", index=False)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()
    except Exception:
        return hashlib.sha1(str(len(risk_detail_df) if risk_detail_df is not None else 0).encode("utf-8")).hexdigest()


def _set_claim_snapshot_once(reason: str = "") -> None:
    """
    Mark the next full-app rerun as non-impacting for Claim Breakdown.
    Used by OVR/export/detailed-only controls so Claim Breakdown can keep its
    last rendered data instead of recomputing/reloading claim details.
    """
    st.session_state["claim_breakdown_snapshot_once"] = True
    st.session_state["claim_breakdown_snapshot_reason"] = reason


def _get_claim_metric_state() -> tuple[bool, bool]:
    show_gross = bool(st.session_state.get("claim_breakdown_show_gross_pct", True))
    show_count = bool(st.session_state.get("claim_breakdown_show_number_of_claims_pct", False))
    if not show_gross and not show_count:
        show_gross = True
    return show_gross, show_count


def _store_claim_breakdown_snapshot(
    risk_detail_df: pd.DataFrame,
    chart_snapshots: dict,
    show_gross_claim_pct: bool,
    show_number_of_claims_pct: bool,
) -> None:
    st.session_state["claim_breakdown_snapshot"] = {
        "sig": _claim_keys_signature(risk_detail_df),
        "chart_snapshots": chart_snapshots,
        "show_gross_claim_pct": bool(show_gross_claim_pct),
        "show_number_of_claims_pct": bool(show_number_of_claims_pct),
    }


def _render_claim_breakdown_from_snapshot(risk_detail_df: pd.DataFrame) -> bool:
    """Render last Claim Breakdown snapshot if the current action does not affect claims."""
    snapshot = st.session_state.get("claim_breakdown_snapshot")
    if not isinstance(snapshot, dict):
        return False

    current_sig = _claim_keys_signature(risk_detail_df)
    if snapshot.get("sig") != current_sig:
        return False

    chart_snapshots = snapshot.get("chart_snapshots") or {}
    if not chart_snapshots:
        return False

    render_section_card_header("Claim Breakdown (%)")

    show_gross_claim_pct, show_number_of_claims_pct = _get_claim_metric_state()
    if not show_gross_claim_pct and not show_number_of_claims_pct:
        show_gross_claim_pct = bool(snapshot.get("show_gross_claim_pct", True))
        show_number_of_claims_pct = bool(snapshot.get("show_number_of_claims_pct", False))

    tabs = st.tabs(["Claim Type", "Cause Code", "Internal Reason"])
    sections = [
        (tabs[0], "By Claim Type", "KODE_KLAIM"),
        (tabs[1], "By Cause Code", "KODE_PENYEBAB"),
        (tabs[2], "By Internal Reason", "INTERNAL_REASON"),
    ]

    for tab, title, label_col in sections:
        with tab:
            chart_df = chart_snapshots.get(label_col)
            if isinstance(chart_df, pd.DataFrame):
                render_claim_breakdown_chart(
                    chart_df,
                    title,
                    label_col,
                    show_gross_claim_pct=show_gross_claim_pct,
                    show_number_of_claims_pct=show_number_of_claims_pct,
                )
            else:
                st.info("Claim Breakdown snapshot is not available for this section.")
    return True


def render_claim_breakdown_stable(risk_detail_df: pd.DataFrame) -> None:
    """
    Render Claim Breakdown with affected-only behavior:
    - if current action is OVR/export/detailed-only, reuse last snapshot;
    - otherwise render the interactive Claim Breakdown fragment.
    """
    snapshot_once = bool(st.session_state.pop("claim_breakdown_snapshot_once", False))
    if snapshot_once:
        if _render_claim_breakdown_from_snapshot(risk_detail_df):
            return
    render_claim_breakdown_section(risk_detail_df)


# Claim Breakdown is the only section intentionally kept as a fragment.
# Its own controls rerun only this section, while its data is cached by risk keys
# so OVR/export actions do not recompute claim breakdown.
def _claim_fragment_if_available(func):
    return st.fragment(func) if hasattr(st, "fragment") else func



@_claim_fragment_if_available
def render_claim_breakdown_section(risk_detail_df: pd.DataFrame) -> None:
    render_section_card_header("Claim Breakdown (%)")

    try:
        claim_detail_df = cached_filtered_claim_detail(risk_detail_df)
    except Exception as e:
        st.warning(f"Claim breakdown is unavailable: {e}")
        return

    if claim_detail_df.empty:
        st.info("No matched claim data for the selected filters.")
        return

    _show_claim_breakdown_hint_once(claim_detail_df)

    # Metric toggles are handled client-side inside each chart iframe.
    # This avoids a full Streamlit rerun when users switch between Gross Claim %
    # and No. of Claims %.
    show_gross_claim_pct = True
    show_number_of_claims_pct = True
    tabs = st.tabs(["Claim Type", "Cause Code", "Internal Reason"])
    sections = [
        (tabs[0], "By Claim Type", "KODE_KLAIM"),
        (tabs[1], "By Cause Code", "KODE_PENYEBAB"),
        (tabs[2], "By Internal Reason", "INTERNAL_REASON"),
    ]

    chart_snapshots = {}
    for tab, title, label_col in sections:
        chart_df = cached_claim_chart_df(claim_detail_df, label_col, top_n=9)
        chart_snapshots[label_col] = chart_df.copy() if isinstance(chart_df, pd.DataFrame) else chart_df
        with tab:
            render_claim_breakdown_chart(
                chart_df,
                title,
                label_col,
                show_gross_claim_pct=show_gross_claim_pct,
                show_number_of_claims_pct=show_number_of_claims_pct,
            )

    _store_claim_breakdown_snapshot(
        risk_detail_df,
        chart_snapshots,
        show_gross_claim_pct,
        show_number_of_claims_pct,
    )

def build_claim_summary_table_pdf(summary_df: pd.DataFrame, title: str, label_col: str, styles):
    elements = [Paragraph(f"<b>{title}</b>", styles["Title"])]

    if summary_df is None or summary_df.empty:
        elements.append(Paragraph("No matched claim data for this section.", styles["Normal"]))
        return elements

    df_fmt = summary_df.copy()
    for col in ["NUMBER OF CLAIMS %", "GROSS CLAIM %"]:
        if col in df_fmt.columns:
            df_fmt[col] = df_fmt[col].apply(lambda x: f"{float(x):.1f}%" if pd.notna(x) else "")

    display_cols = [label_col, "NUMBER OF CLAIMS %", "GROSS CLAIM %"]
    display_cols = [c for c in display_cols if c in df_fmt.columns]
    df_fmt = df_fmt[display_cols]

    alias = {
        "KODE_KLAIM": "CLAIM TYPE",
        "KODE_PENYEBAB": "CAUSE CODE",
        "INTERNAL_REASON": "INTERNAL REASON",
        "NUMBER OF CLAIMS %": "NO. OF CLAIMS %",
        "GROSS CLAIM %": "GROSS CLAIM %",
    }

    header_style = ParagraphStyle(
        "ClaimSummaryHeaderWrap",
        parent=styles["Normal"],
        alignment=1,
        textColor=colors.white,
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=9,
    )
    cell_style = ParagraphStyle(
        "ClaimSummaryCell",
        parent=styles["Normal"],
        fontSize=8,
        leading=9,
    )

    note_style = ParagraphStyle(
        "ClaimSummaryNote",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#555555"),
        spaceAfter=8,
    )

    elements.append(Paragraph(
        "Each category shows percentage of Gross Claim and percentage of Number of Claims. Top 9 categories are shown individually, while the rest are grouped into Others.",
        note_style,
    ))

    data = [[Paragraph(alias.get(col, col), header_style) for col in df_fmt.columns]]
    table_style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]

    for r in range(len(df_fmt)):
        row_color = colors.HexColor("#F6F8FB") if r % 2 == 1 else colors.white
        table_style_cmds.append(("BACKGROUND", (0, r + 1), (-1, r + 1), row_color))
        row = []
        for c, col in enumerate(df_fmt.columns):
            align = 0 if col == label_col else 2
            row.append(Paragraph(str(df_fmt.iloc[r, c]) if pd.notna(df_fmt.iloc[r, c]) else "", ParagraphStyle(
                f"ClaimSummaryCell_{r}_{c}",
                parent=cell_style,
                alignment=align,
                fontName="Helvetica",
            )))
        data.append(row)

    avail_w = landscape(A4)[0] - (0.8 * cm) - (0.8 * cm)
    raw_widths = []
    for col in df_fmt.columns:
        if col == label_col:
            raw_widths.append(15.5 * cm if label_col != "INTERNAL_REASON" else 19.0 * cm)
        elif col == "NUMBER OF CLAIMS %":
            raw_widths.append(4.0 * cm)
        elif col == "GROSS CLAIM %":
            raw_widths.append(4.0 * cm)
        else:
            raw_widths.append(3.0 * cm)
    total = sum(raw_widths)
    if total > avail_w and total > 0:
        factor = avail_w / total
        raw_widths = [w * factor for w in raw_widths]

    tbl = Table(data, repeatRows=1, colWidths=raw_widths)
    tbl.setStyle(TableStyle(table_style_cmds))
    elements.extend([tbl, Spacer(1, 0.2 * cm)])
    return elements


def build_kpi_cards_pdf(kpis, styles):
    def fmt_money(x):
        return f"{int(round(x/1_000_000)):,}".replace(",", ".")

    def fmt_pct(x):
        return f"{round(x):.0f}%" if pd.notna(x) else "-"

    # --- STYLE REFINEMENT ---
    zurich_blue = colors.HexColor("#003366")
    
    # Style Header (Teks Putih)
    label_style = ParagraphStyle(
        "KPILabel",
        parent=styles["Normal"],
        alignment=1,
        fontSize=8,
        textColor=colors.white, # Font Putih
        fontName="Helvetica-Bold",
        textTransform='uppercase'
    )
    
    # Style Value (Teks Biru Zurich agar senada dengan header)
    value_style = ParagraphStyle(
        "KPIValue",
        parent=styles["Normal"],
        alignment=1,
        fontSize=10,
        textColor=zurich_blue, 
        fontName="Helvetica-Bold",
        allowMarkup=True
    )

    # Logika Status Dot untuk Combined Ratio
    status_dot = ""
    if pd.notna(kpis["CoR"]):
        dot_color = "#28A745" if kpis["CoR"] <= 100 else "#DC3545"
        status_dot = f" <font color='{dot_color}' size='10'>●</font>"

    data = [
        [
            Paragraph("TOTAL GWP*", label_style),
            Paragraph("LOSS RATIO", label_style),
            Paragraph("COMM RATIO", label_style),
            Paragraph("RI COST RATIO", label_style),
            Paragraph("RI RECOVERY", label_style),
            Paragraph("COMBINED RATIO", label_style)
        ],
        [
            Paragraph(fmt_money(kpis["GWP"]), value_style),
            Paragraph(fmt_pct(kpis["Loss Ratio"]), value_style),
            Paragraph(fmt_pct(kpis["COMM Ratio"]), value_style),
            Paragraph(fmt_pct(kpis["RI Cost Ratio"]), value_style),
            Paragraph(fmt_pct(kpis["RI Recovery Ratio"]), value_style),
            Paragraph(f"{fmt_pct(kpis['CoR'])}{status_dot}", value_style)
        ]
    ]

    table = Table(data, colWidths=[3 * cm] * 6, rowHeights=[0.75 * cm, 0.75 * cm])

    table.setStyle(TableStyle([
        # Header Row: Background Biru Tua, Teks Putih
        ("BACKGROUND", (0, 0), (-1, 0), zurich_blue),
        
        # Body Row: Background Putih
        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        
        # Grid & Border (Gunakan warna biru yang sama agar elegan)
        ("GRID", (0, 0), (-1, -1), 0.5, zurich_blue),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        
        # Padding
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))

    return table

def export_pdf(df, name, filters, as_of_date, username, risk_detail_df=None, include_claim_breakdown=False, claim_df=None):
    # =========================
    # COLUMN ALIAS (PDF ONLY)
    # =========================
    col_alias = {
        "POLICY_NO": "POLIS",
        "UW_YEAR": "UW YEAR",
        "IS_ELECTRIC": "EV STATUS",
        "OUR TSI": "TSI*",
        "GWP_AMT": "GWP*",
        "GEP_AMT": "GEP*",
        "GROSS_CLAIM": "GROSS CLAIM*",
        "COMMISSIONS": "COMM*",
        "RI_COST": "RI COST*",
        "RI_RECOVERY": "RI REC*",
        "NUMBER OF CLAIMS": "NO. OF CLAIM",
        "NUMBER OF RISKS": "NO. OF RISKS",
        "Loss Ratio": "LOSS RATIO",
        "COMM Ratio": "COMM RATIO",
        "RI Cost Ratio": "RI COST RATIO",
        "RI Recovery Ratio": "RI REC RATIO",
        "CoR (before OVR)": "CoR",
        "FUNCTION": "USAGE"
    }

    buffer = io.BytesIO()

    # =========================
    # DEFINISI KOLOM
    # =========================
    money_cols = [
        "OUR TSI", "GWP_AMT", "GEP_AMT", "GROSS_CLAIM",
        "COMMISSIONS", "RI_COST", "RI_RECOVERY"
    ]

    count_cols = [
        "NUMBER OF CLAIMS", "NUMBER OF RISKS"
    ]

    metric_cols = money_cols + count_cols + [
        "Loss Ratio", "COMM Ratio", "RI Cost Ratio",
        "RI Recovery Ratio", "CoR (before OVR)"
    ]

    # =========================
    # PREP DATA
    # =========================
    df_numeric = df.copy()
    df_formatted = df.copy()

    # Pastikan index jadi kolom (untuk grouping seperti UW_YEAR, COB, dll)
    if isinstance(df_numeric.index, pd.MultiIndex):
        df_numeric = df_numeric.reset_index()
        df_formatted = df_formatted.reset_index()
    elif df_numeric.index.name is not None:
        df_numeric = df_numeric.reset_index()
        df_formatted = df_formatted.reset_index()


    # Hilangkan ERC_AMT
    if "ERC_AMT" in df_numeric.columns:
        df_numeric.drop(columns=["ERC_AMT"], inplace=True)
        df_formatted.drop(columns=["ERC_AMT"], inplace=True)

    # Tentukan grouping columns
    group_cols = [c for c in df_numeric.columns if c not in metric_cols]

    final_cols = group_cols + [c for c in metric_cols if c in df_numeric.columns]

    df_numeric = df_numeric[final_cols].reset_index(drop=True)
    df_formatted = df_formatted[final_cols].reset_index(drop=True)

    df_formatted = df_formatted.replace([np.inf, -np.inf], np.nan)

    # =========================
    # FORMATTING (BUG FIX AREA)
    # =========================
    for col in df_formatted.columns:

        # RATIO
        if "Ratio" in col or "CoR" in col:
            df_formatted[col] = df_formatted[col].apply(
                lambda x: f"{round(float(x)):.0f}%" if pd.notna(x) else ""
            )

        # MONEY
        elif col in money_cols:
            df_formatted[col] = df_formatted[col].apply(
                lambda x: f"{int(round(float(x) / 1_000_000)):,}".replace(",", ".")
                if pd.notna(x) else ""
            )

        # COUNT
        elif col in count_cols:
            df_formatted[col] = df_formatted[col].apply(
                lambda x: f"{int(x):,}".replace(",", ".") if pd.notna(x) else ""
            )

        # GROUPING / TEXT
        else:
            df_formatted[col] = df_formatted[col].astype(str)

    # =========================
    # PDF STYLING
    # =========================
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        "HeaderWrap",
        parent=styles["Normal"],
        alignment=1,
        textColor=colors.white,
        fontName="Helvetica-Bold",
        fontSize=7
    )

    cell_style = ParagraphStyle(
        "CellText",
        parent=styles["Normal"],
        alignment=2,
        fontSize=7
    )

    wrapped_headers = [
    Paragraph(col_alias.get(col, col), header_style)
    for col in df_formatted.columns]

    data = [wrapped_headers]

    table_style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]


    # =========================
    # TABLE BODY
    # =========================
    for r in range(len(df_formatted)):
        row_cells = []
        
        # 1. Tentukan warna dasar zebra (misal: abu-abu sangat muda untuk baris genap)
        # r+1 karena index 0 adalah Header
        row_color = colors.HexColor("#F2F2F2") if r % 2 == 1 else colors.white
        
        # Tambahkan background baris ke style commands
        table_style_cmds.append(("BACKGROUND", (0, r + 1), (-1, r + 1), row_color))

        for c, col_name in enumerate(df_formatted.columns):
            val = df_formatted.iloc[r, c]
            raw_val = df_numeric.iloc[r, c]

            # 2. Logika Highlight (Loss Ratio & CoR) akan menimpa warna zebra
            cell_bg = row_color # Default mengikuti warna baris

            if col_name == "CoR (before OVR)" and pd.notna(raw_val) and raw_val > 100:
                cell_bg = colors.HexColor("#FFD966") # Kuning/Oranye

            if col_name == "Loss Ratio" and pd.notna(raw_val) and raw_val > 50:
                cell_bg = colors.HexColor("#FFA07A") # Merah muda

            # Terapkan background ke sel spesifik (supaya highlight tetap muncul)
            if cell_bg != row_color:
                table_style_cmds.append(("BACKGROUND", (c, r + 1), (c, r + 1), cell_bg))

            style = ParagraphStyle(
                "Cell",
                parent=cell_style,
                alignment=0 if c < len(group_cols) else 2,
                fontSize=9 if c >= len(group_cols) else 8,
                fontName="Helvetica",
            )

            row_cells.append(Paragraph(str(val), style))

        data.append(row_cells)

    # =========================
    # BUILD PDF
    # =========================
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=0.8 * cm,
        rightMargin=0.8 * cm,
        topMargin=0.8 * cm,
        bottomMargin=0.8 * cm
    )
    kpis = compute_kpis(df)
    # Dynamic PDF column widths.
    # Previously every non-metric/grouping column received 4.0 cm, so short
    # fields such as TOB or IS_ELECTRIC used too much horizontal space.
    def _pdf_col_width(col: str, is_group_col: bool):
        if col == "COB":
            return 1.0 * cm
        if col == "UW_YEAR":
            return 1.35 * cm
        if col in ["NUMBER OF CLAIMS", "NUMBER OF RISKS"]:
            return 1.6 * cm
        if col == "OUR TSI":
            return 2.25 * cm
        if col == "GWP_AMT":
            return 1.70 * cm
        if col == "GEP_AMT":
            return 1.65 * cm
        if col == "GROSS_CLAIM":
            return 1.70 * cm
        if col == "COMMISSIONS":
            return 1.70 * cm
        if col == "RI_RECOVERY":
            return 1.65 * cm
        if col == "RI_COST":
            return 1.65 * cm
        if "Ratio" in col or "CoR" in col:
            return 1.50 * cm

        if is_group_col:
            group_widths = {
                "AGE": 1.05 * cm,
                "TOB": 1.05 * cm,
                # LOB needs more room than TOB because the values are usually longer.
                "LOB": 2.20 * cm,
                "IS_ELECTRIC": 1.45 * cm,
                "BRANCH": 1.70 * cm,
                "CATEGORY": 1.80 * cm,
                "MAIN_COVERAGE": 2.10 * cm,
                "BRAND": 2.10 * cm,
                "MODEL": 2.40 * cm,
                "SUBMODEL": 2.60 * cm,
                "PCKG_DESC": 2.60 * cm,
                "TSI RANGE": 2.60 * cm,
                "POLICY_NO": 2.60 * cm,
                "MARKETING_GROUP": 2.80 * cm,
                "MARKETING_NAME": 3.00 * cm,
                "INTERMEDIARY_NAME": 3.20 * cm,
                "INSURED_NAME": 3.40 * cm,
                "FUNCTION": 2.20 * cm,
            }
            return group_widths.get(col, 2.40 * cm)

        return 2.10 * cm

    raw_col_widths = [
        _pdf_col_width(col, i < len(group_cols))
        for i, col in enumerate(df_formatted.columns)
    ]

    # Scale down proportionally if the selected breakdown has many columns, so
    # the table stays inside the landscape A4 page instead of wasting/overflowing.
    available_width = landscape(A4)[0] - (0.8 * cm) - (0.8 * cm)
    total_width = sum(raw_col_widths)
    if total_width > available_width and total_width > 0:
        scale = available_width / total_width
        raw_col_widths = [w * scale for w in raw_col_widths]

    table = Table(
        data,
        repeatRows=1,
        colWidths=raw_col_widths
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=11,
        leading=13,
        textColor=colors.grey,
        alignment=1,          # center
        spaceBefore=2,
        spaceAfter=10)

    filter_style = ParagraphStyle(
        "FilterText",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#555555"),
        spaceAfter=2)
    
    table.setStyle(TableStyle(table_style_cmds))

    elements = [
    Paragraph("<b>MNC Insurance Portfolio Analysis Report</b>", styles["Title"])]
    elements.append(
    Paragraph("This Report Was Downloaded from SuperApp Actuary on behalf of Actuary Department", subtitle_style))
    elements.append(Spacer(1, 0.15 * cm))
    if filters:
        elements.append(Spacer(1, 0.15 * cm))
        elements.append(Paragraph("<b>Portfolio Report for:</b>", styles["Normal"]))
        elements.append(Paragraph("Motor Vehicle on UW Years 2021 - 2026", styles["Normal"]))
    
        for col, info in filters.items():
            vals = info.get("values", [])
            mode = info.get("mode", "").lower()
    
            # Normalisasi values → string lower
            vals_norm = [str(v).strip().lower() for v in vals]
    
            # RULE KILLER:
            # 1. mode all
            # 2. values kosong
            # 3. values = ["all"]
            if (
                "all" in mode
                or not vals_norm
                or (len(vals_norm) == 1 and vals_norm[0] == "all")
            ):
                continue
    
            text = (
                f"{field_display_name(col)} ({info.get('mode')}): {len(vals)} selected"
                if len(vals) > 10
                else f"{field_display_name(col)} ({info.get('mode')}): {', '.join(map(str, vals))}"
            )
            elements.append(Paragraph(text, styles["Normal"]))


    if as_of_date:
        elements.append(Spacer(1, 0.3 * cm))
        elements.append(Paragraph(f"<b>As of Date:</b> {as_of_date[7:]}", styles["Normal"]))
        elements.append(Paragraph(f"*Data shown in IDR Mio", styles["Normal"]))
        elements.append(Spacer(1, 0.5 * cm))
    
    elements.append(Paragraph("<b>Key Performance:</b>", styles["Normal"]))
    elements.append(build_kpi_cards_pdf(kpis, styles))
    elements.append(Spacer(1, 0.6 * cm))
    elements.append(Paragraph("<b>Detailed Portfolio Performance:</b>", styles["Normal"]))
    elements.append(table)

    if include_claim_breakdown:
        claim_detail_df = get_filtered_claim_detail(risk_detail_df, claim_df)
        sections = [
            ("Claim Breakdown Details by Claim Type", "KODE_KLAIM"),
            ("Claim Breakdown Details by Cause Code", "KODE_PENYEBAB"),
            ("Claim Breakdown Details by Internal Reason", "INTERNAL_REASON"),
        ]

        for title, label_col in sections:
            elements.append(PageBreak())
            if claim_detail_df.empty:
                elements.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
                elements.append(Paragraph("No matched claim data for the selected filters.", styles["Normal"]))
            else:
                summary_df = build_claim_breakdown_display_df(claim_detail_df, label_col, top_n=9)
                elements.extend(build_claim_summary_table_pdf(summary_df, title, label_col, styles))

    pdf.build(
    elements,
    onFirstPage=lambda canvas, doc: draw_footer(canvas, doc, username),
    onLaterPages=lambda canvas, doc: draw_footer(canvas, doc, username),)


    return buffer.getvalue()



# =========================
# EXCEL EXPORT
# =========================
def export_excel(df, name, filters=None, as_of_date=None, risk_detail_df=None, include_claim_breakdown=False, claim_df=None):
    buffer = io.BytesIO()
    df_to_export = df.copy()

    if isinstance(df_to_export.index, pd.MultiIndex):
        df_to_export = df_to_export.reset_index()
    else:
        df_to_export.index.name = df_to_export.index.name or "Index"
        df_to_export = df_to_export.reset_index()

    if "ERC_AMT" in df_to_export.columns:
        df_to_export.drop(columns=["ERC_AMT"], inplace=True)

    for col in df_to_export.columns:
        if "Ratio" in col or "CoR" in col:
            df_to_export[col] = df_to_export[col].apply(lambda x: float(x)/100 if pd.notna(x) else None)

    def _write_filter_block(worksheet):
        if as_of_date:
            worksheet.write(0, 0, f"As of Date: {as_of_date}")
        row_offset = 1
        if filters:
            worksheet.write(row_offset, 0, "Portfolio Report for:")
            row_offset += 1
            for col, info in filters.items():
                vals = info.get("values", [])
                mode = info.get("mode", "")
                if not vals or "All" in mode:
                    text = f"{field_display_name(col)} ({mode}): All selected"
                elif len(vals) > 10:
                    text = f"{field_display_name(col)} ({mode}): {len(vals)} selected"
                else:
                    text = f"{field_display_name(col)} ({mode}): {', '.join(map(str, vals))}"
                worksheet.write(row_offset, 0, text)
                row_offset += 1

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        startrow = 2 + (len(filters) if filters else 0)
        main_sheet_name = "Sheet1"
        df_to_export.to_excel(writer, index=False, startrow=startrow, sheet_name=main_sheet_name)
        workbook = writer.book
        worksheet = writer.sheets[main_sheet_name]

        money_fmt = workbook.add_format({'num_format': '#,##0'})
        pct_fmt = workbook.add_format({'num_format': '0%'})
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#003366', 'font_color': 'white'})
        note_fmt = workbook.add_format({'italic': True, 'font_color': '#555555'})

        for i, col in enumerate(df_to_export.columns):
            if col in ["OUR TSI", "GWP_AMT", "GEP_AMT", "GROSS_CLAIM", "COMMISSIONS", "RI_COST", "RI_RECOVERY"]:
                worksheet.set_column(i, i, 15, money_fmt)
            elif "Ratio" in col or "CoR" in col:
                worksheet.set_column(i, i, 12, pct_fmt)
            else:
                worksheet.set_column(i, i, 20)

        _write_filter_block(worksheet)

        if include_claim_breakdown:
            claim_detail_df = get_filtered_claim_detail(risk_detail_df, claim_df)
            claim_sheet_defs = [
                ("Claim Type Breakdown", "Claim Type", "KODE_KLAIM"),
                ("Cause Code Breakdown", "Cause Code", "KODE_PENYEBAB"),
                ("Internal Reason Breakdown", "Internal Reason", "INTERNAL_REASON"),
            ]

            for sheet_full_name, title_name, label_col in claim_sheet_defs:
                summary_df = build_claim_breakdown_display_df(claim_detail_df, label_col, top_n=9)
                sheet_name = sheet_full_name[:31]
                ws = workbook.add_worksheet(sheet_name)
                writer.sheets[sheet_name] = ws

                ws.write(0, 0, f"Claim Breakdown Details by {title_name}")
                _write_filter_block(ws)
                note_row = max(1, startrow - 1)
                ws.write(note_row, 0, "Each category shows percentage of Gross Claim and percentage of Number of Claims. Top 9 categories are shown individually, while the rest are grouped into Others.", note_fmt)

                if summary_df is None or summary_df.empty:
                    ws.write(startrow, 0, "No matched claim data for the selected filters.")
                    ws.set_column(0, 0, 50)
                    continue

                excel_df = summary_df[[label_col, "NUMBER OF CLAIMS %", "GROSS CLAIM %"]].copy()
                excel_df.rename(columns={
                    label_col: title_name.upper(),
                    "NUMBER OF CLAIMS %": "NO. OF CLAIMS %",
                    "GROSS CLAIM %": "GROSS CLAIM %",
                }, inplace=True)
                for pct_col in ["NO. OF CLAIMS %", "GROSS CLAIM %"]:
                    excel_df[pct_col] = excel_df[pct_col].apply(lambda x: float(x) / 100 if pd.notna(x) else None)

                excel_df.to_excel(writer, index=False, startrow=startrow, sheet_name=sheet_name)
                for col_idx, col_name in enumerate(excel_df.columns):
                    ws.write(startrow, col_idx, col_name, header_fmt)
                    if col_idx == 0:
                        ws.set_column(col_idx, col_idx, 34)
                    else:
                        ws.set_column(col_idx, col_idx, 18, pct_fmt)

    return buffer.getvalue()

def _clear_export_state(prefix: str):
    for suffix in ("sig", "bytes", "href", "name", "error"):
        st.session_state.pop(f"{prefix}__{suffix}", None)


def _compute_export_signature(payload: dict) -> str:
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha1(payload_json.encode("utf-8")).hexdigest()


def _make_data_uri(data_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(data_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _render_direct_download_link(label: str, href: str, file_name: str, ready: bool = True):
    css_class = "direct-download-btn is-ready" if ready else "direct-download-btn"
    st.markdown(
        f'<a class="{css_class}" download="{html.escape(file_name, quote=True)}" href="{href}">{html.escape(label)}</a>',
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False, ttl=900, max_entries=8)
def cached_export_pdf_bytes(df, name, filters, as_of_date, username, risk_detail_df, include_claim_breakdown_pdf):
    claim_df_pdf = None
    if include_claim_breakdown_pdf:
        claim_df_pdf = load_claim_data("CLAIM260331.parquet")
    return export_pdf(df, name, filters, as_of_date, username, risk_detail_df=risk_detail_df, include_claim_breakdown=include_claim_breakdown_pdf, claim_df=claim_df_pdf)


@st.cache_data(show_spinner=False, ttl=900, max_entries=8)
def cached_export_excel_bytes(df, name, filters, as_of_date, risk_detail_df, include_claim_breakdown_excel):
    claim_df_excel = None
    if include_claim_breakdown_excel:
        claim_df_excel = load_claim_data("CLAIM260331.parquet")
    return export_excel(df, name, filters, as_of_date, risk_detail_df=risk_detail_df, include_claim_breakdown=include_claim_breakdown_excel, claim_df=claim_df_excel)


@_claim_fragment_if_available
def render_export_controls_fragment(
    safe_tab_name,
    tab_name,
    group_cols,
    df_source,
    active_filters,
    tanggal_pilihan,
    username,
    risk_detail_for_claim,
    include_claim_breakdown,
):
    """
    Export controls isolated in a Streamlit fragment.
    Clicking Prepare PDF/Excel reruns only this export block, so KPI, projection,
    detailed table, and claim breakdown keep their existing UI state.
    """
    pdf_prefix = f"export_pdf__{safe_tab_name}"
    xlsx_prefix = f"export_xlsx__{safe_tab_name}"

    include_key = f"include_claim_summary__{safe_tab_name}"
    if include_key not in st.session_state:
        st.session_state[include_key] = bool(include_claim_breakdown)

    include_claim_breakdown = st.checkbox(
        "Include claim breakdown",
        key=include_key,
        on_change=lambda: _set_claim_snapshot_once("export_include_claim_toggle"),
    )

    if include_claim_breakdown:
        st.caption("PDF/Excel will include percentage-only claim breakdown by Claim Type, Cause Code, and Internal Reason.")

    pdf_signature = _compute_export_signature({
        "tab_name": tab_name,
        "group_cols": list(group_cols),
        "filters": active_filters,
        "as_of": tanggal_pilihan,
        "include_claim_breakdown": bool(include_claim_breakdown),
    })
    xlsx_signature = _compute_export_signature({
        "tab_name": tab_name,
        "group_cols": list(group_cols),
        "filters": active_filters,
        "as_of": tanggal_pilihan,
        "include_claim_breakdown_excel": bool(include_claim_breakdown),
    })

    if st.session_state.get(f"{pdf_prefix}__sig") != pdf_signature:
        _clear_export_state(pdf_prefix)
    if st.session_state.get(f"{xlsx_prefix}__sig") != xlsx_signature:
        _clear_export_state(xlsx_prefix)

    prep_col1, prep_col2 = st.columns(2, gap="small")

    with prep_col1:
        if st.button("Prepare PDF", key=f"prepare_pdf__{safe_tab_name}", width="content"):
            _set_claim_snapshot_once("prepare_pdf")
            try:
                with st.spinner("Preparing PDF..."):
                    pivot_for_pdf = cached_pivot(df_source, tuple(group_cols), row_limit=500)
                    pdf_bytes = cached_export_pdf_bytes(
                        pivot_for_pdf,
                        tab_name,
                        active_filters,
                        tanggal_pilihan,
                        username,
                        risk_detail_for_claim,
                        include_claim_breakdown,
                    )
                st.session_state[f"{pdf_prefix}__href"] = _make_data_uri(pdf_bytes, "application/pdf")
                del pdf_bytes
                gc.collect()
                st.session_state[f"{pdf_prefix}__name"] = f"{safe_tab_name}.pdf"
                st.session_state[f"{pdf_prefix}__sig"] = pdf_signature
                st.session_state.pop(f"{pdf_prefix}__error", None)
            except Exception as e:
                _clear_export_state(pdf_prefix)
                st.session_state[f"{pdf_prefix}__error"] = str(e)

        pdf_error = st.session_state.get(f"{pdf_prefix}__error")
        pdf_href = st.session_state.get(f"{pdf_prefix}__href")
        if pdf_error:
            st.error(f"PDF export failed: {pdf_error}")
        elif pdf_href:
            _render_direct_download_link(
                "Download PDF",
                pdf_href,
                st.session_state.get(f"{pdf_prefix}__name", f"{safe_tab_name}.pdf"),
            )
            st.caption("PDF ready. PDF uses top 500 rows. Regenerate jika filter berubah.")
        else:
            st.caption("Prepare PDF dulu sebelum download.")

    with prep_col2:
        if st.button("Prepare Excel", key=f"prepare_xlsx__{safe_tab_name}", width="content"):
            _set_claim_snapshot_once("prepare_excel")
            try:
                with st.spinner("Preparing Excel..."):
                    full_pivot_for_excel = cached_pivot(df_source, tuple(group_cols), row_limit=2000)
                    xlsx_bytes = cached_export_excel_bytes(
                        full_pivot_for_excel,
                        tab_name,
                        active_filters,
                        tanggal_pilihan,
                        risk_detail_for_claim,
                        include_claim_breakdown,
                    )
                st.session_state[f"{xlsx_prefix}__href"] = _make_data_uri(
                    xlsx_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                del xlsx_bytes
                gc.collect()
                st.session_state[f"{xlsx_prefix}__name"] = f"{safe_tab_name}.xlsx"
                st.session_state[f"{xlsx_prefix}__sig"] = xlsx_signature
                st.session_state.pop(f"{xlsx_prefix}__error", None)
            except Exception as e:
                _clear_export_state(xlsx_prefix)
                st.session_state[f"{xlsx_prefix}__error"] = str(e)

        xlsx_error = st.session_state.get(f"{xlsx_prefix}__error")
        xlsx_href = st.session_state.get(f"{xlsx_prefix}__href")
        if xlsx_error:
            st.error(f"Excel export failed: {xlsx_error}")
        elif xlsx_href:
            _render_direct_download_link(
                "Download Excel",
                xlsx_href,
                st.session_state.get(f"{xlsx_prefix}__name", f"{safe_tab_name}.xlsx"),
            )
            st.caption("Excel ready. Excel uses top 2,000 rows. Regenerate jika filter berubah.")
        else:
            st.caption("Prepare Excel dulu sebelum download.")


# =========================
# SECTION / PROJECTION HELPERS
# =========================
def render_section_card_header(title: str, subtitle: str = ""):
    """Render section header with self-contained CSS so it stays styled even when this file is imported as a sub-app."""
    subtitle_html = f'<div class="section-card-subtitle">{html.escape(subtitle)}</div>' if subtitle else ""
    st.markdown(f"""
    <style>
      .section-card-header{{
        margin: 14px 0 8px 0 !important;
        padding: 12px 15px !important;
        border-radius: 16px !important;
        background: #F8FAFC !important;
        border: 1px solid rgba(0,51,102,0.10) !important;
        box-shadow: 0 8px 22px rgba(15,23,42,0.035) !important;
      }}
      .section-card-title{{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
        font-size: 18px !important;
        font-weight: 800 !important;
        color: #003366 !important;
        line-height: 1.15 !important;
        letter-spacing: -0.01em !important;
      }}
      .section-card-subtitle{{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
        font-size: 12.5px !important;
        color: #64748B !important;
        line-height: 1.25 !important;
        margin-top: 3px !important;
      }}
      .mv-detail-controls-card{{
        margin: 12px 0 14px 0 !important;
        padding: 14px 16px 10px 16px !important;
        border-radius: 16px !important;
        background: #FFFFFF !important;
        border: 1px solid rgba(0,51,102,0.12) !important;
        box-shadow: 0 8px 22px rgba(15,23,42,0.04) !important;
      }}
      .mv-detail-controls-title{{
        margin: 0 0 10px 0;
        font-size: 12px;
        font-weight: 800;
        color: #003366;
        letter-spacing: 0.01em;
      }}
      .mv-detail-tabs-spacer{{
        margin-top: 10px !important;
      }}
    </style>
    <div class="section-card-header">
      <div class="section-card-title">{html.escape(title)}</div>
      {subtitle_html}
    </div>
    """, unsafe_allow_html=True)


def render_projection_section(source_df: pd.DataFrame):
    """Automatic moving-average projection for the next incomplete UW year."""
    render_section_card_header("Trend & Projection")
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

    if source_df is None or source_df.empty:
        st.info("No data.")
        return

    required = {"UW_YEAR", "GWP_AMT", "GEP_AMT", "GROSS_CLAIM"}
    missing = [c for c in required if c not in source_df.columns]
    if missing:
        st.info("Trend unavailable. Missing: " + ", ".join(missing))
        return

    tmp = source_df.copy()
    tmp["UW_YEAR"] = pd.to_numeric(tmp["UW_YEAR"], errors="coerce")
    tmp = tmp[tmp["UW_YEAR"].notna()].copy()
    if tmp.empty:
        st.info("Trend unavailable. UW_YEAR is empty.")
        return

    for col in ["GWP_AMT", "GEP_AMT", "GROSS_CLAIM"]:
        tmp[col] = pd.to_numeric(tmp[col], errors="coerce").fillna(0.0)

    yearly = (
        tmp.groupby("UW_YEAR", as_index=False)
        .agg(
            GWP_AMT=("GWP_AMT", "sum"),
            GEP_AMT=("GEP_AMT", "sum"),
            GROSS_CLAIM=("GROSS_CLAIM", "sum"),
        )
        .sort_values("UW_YEAR")
        .reset_index(drop=True)
    )
    yearly["UW_YEAR"] = yearly["UW_YEAR"].astype(int)
    yearly["GWP Mio"] = yearly["GWP_AMT"] / 1_000_000
    yearly["Loss Ratio %"] = np.where(
        yearly["GEP_AMT"] > 0,
        yearly["GROSS_CLAIM"] / yearly["GEP_AMT"] * 100.0,
        np.nan,
    )

    # The latest UW year is treated as incomplete. Projection is always the
    # year after the latest completed year, e.g. completed 2025 => projection 2026.
    latest_year = int(yearly["UW_YEAR"].max())
    complete_yearly = yearly[yearly["UW_YEAR"] < latest_year].copy()

    if len(complete_yearly) < 2:
        st.info("Need at least 2 completed UW years for projection.")
        return

    ma_window = min(3, len(complete_yearly))
    project_year = int(complete_yearly["UW_YEAR"].max()) + 1

    gwp_forecast = float(complete_yearly["GWP Mio"].tail(ma_window).mean())
    lr_forecast = float(complete_yearly["Loss Ratio %"].dropna().tail(ma_window).mean())

    projection = pd.DataFrame({
        "UW_YEAR": [project_year],
        "GWP Mio": [gwp_forecast],
        "Loss Ratio %": [lr_forecast],
        "Type": ["Projection"],
    })

    actual = complete_yearly[["UW_YEAR", "GWP Mio", "Loss Ratio %"]].copy()
    actual["Type"] = "Actual"
    chart_df = pd.concat([actual, projection], ignore_index=True)
    chart_df["UW_YEAR_LABEL"] = chart_df["UW_YEAR"].astype(str)
    chart_df["GWP_LABEL"] = chart_df["GWP Mio"].map(lambda x: f"{x:,.0f}".replace(",", ".") if pd.notna(x) else "")
    chart_df["LR_LABEL"] = chart_df["Loss Ratio %"].map(lambda x: f"{x:.0f}%" if pd.notna(x) else "")

    color_scale = alt.Scale(domain=["Actual", "Projection"], range=["#003366", "#E39A5B"])

    def _bar_chart(value_col: str, label_col: str, title: str, y_title: str):
        base = alt.Chart(chart_df).encode(
            x=alt.X(
                "UW_YEAR_LABEL:N",
                title=None,
                axis=alt.Axis(
                    labelAngle=0,
                    labelOverlap=False,
                    labelColor="#475569",
                    labelFontSize=12,
                    labelPadding=8,
                    tickSize=0,
                    domain=True,
                    domainColor="#CBD5E1",
                ),
                sort=None,
            ),
            y=alt.Y(
                f"{value_col}:Q",
                title=None,
                axis=alt.Axis(
                    labels=False,
                    ticks=False,
                    grid=False,
                    domain=False,
                ),
            ),
            color=alt.Color(
                "Type:N",
                title=None,
                scale=color_scale,
                legend=alt.Legend(orient="top", labelFontSize=12, symbolSize=120),
            ),
            tooltip=[
                alt.Tooltip("UW_YEAR_LABEL:N", title="UW Year"),
                alt.Tooltip("Type:N", title="Type"),
                alt.Tooltip(f"{value_col}:Q", title=y_title, format=",.1f"),
            ],
        )
        bars = base.mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8, size=36)
        labels = base.mark_text(
            align="center",
            baseline="bottom",
            dy=-7,
            fontSize=12,
            color="#1E293B",
            fontWeight="bold",
        ).encode(text=alt.Text(f"{label_col}:N"))
        return (
            bars + labels
        ).properties(
            height=300,
            title=alt.TitleParams(
                text=title,
                fontSize=15,
                fontWeight="bold",
                color="#003366",
                anchor="middle",
                offset=18,
                dy=-6,
            ),
            background="transparent",
        ).configure_view(
            strokeWidth=0,
            fill="transparent",
        ).configure_axis(
            domainColor="#CBD5E1",
            grid=False,
        )

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.altair_chart(_bar_chart("GWP Mio", "GWP_LABEL", "GWP Trend & Projection", "IDR Mio"), width="stretch")
    with c2:
        st.altair_chart(_bar_chart("Loss Ratio %", "LR_LABEL", "Loss Ratio Trend & Projection", "%"), width="stretch")

    # Forecast Summary table removed per UI request. Projection charts above remain unchanged.

@_claim_fragment_if_available
def render_detailed_data_fragment(
    df: pd.DataFrame,
    active_filters: dict,
    tanggal_pilihan: str,
    username: str,
    risk_detail_for_claim: pd.DataFrame,
) -> None:
    """
    Detailed Data is isolated in a fragment.
    Changing Additional columns reruns only this table/export area, while KPI,
    projection, and Claim Breakdown stay stable.
    """
    render_section_card_header("Detailed Data")

    tab_defs = [
        ("UW YEAR", "Portfolio Analysis - Detailed by UW Year", "UW_YEAR", "UW Year"),
        ("CVRG", "Portfolio Analysis - Detailed by Coverage", "MAIN_COVERAGE", "Coverage"),
        ("BRANCH", "Portfolio Analysis - Detailed by BRANCH", "BRANCH", "Branch"),
        ("MKT NAME", "Portfolio Analysis - Detailed by MKT NAME", "MARKETING_NAME", "Marketing Name"),
        ("MKT GROUP", "Portfolio Analysis - Detailed by MKT GROUP", "MARKETING_GROUP", "Marketing Group"),
        ("AGE", "Portfolio Analysis - Detailed by AGE", "AGE", "Age"),
        ("BRAND", "Portfolio Analysis - Detailed by BRAND", "BRAND", "Brand"),
        ("CATEGORY", "Portfolio Analysis - Detailed by CATEGORY", "CATEGORY", "Category"),
        ("SUB MODEL", "Portfolio Analysis - Detailed by SUBMODEL", "SUBMODEL", "Sub Model"),
        ("MODEL", "Portfolio Analysis - Detailed by MODEL", "MODEL", "Model"),
        ("TOB", "Portfolio Analysis - Detailed by TOB", "TOB", "TOB"),
        ("USAGE", "Portfolio Analysis - Detailed by Usage", "FUNCTION", "Usage"),
        ("ELECTRIC", "Portfolio Analysis - Detailed by IS_ELECTRIC", "IS_ELECTRIC", "Electric Status"),
        ("INT NAME", "Portfolio Analysis - Detailed by INTERMEDIARY_NAME", "INTERMEDIARY_NAME", "Intermediary Name"),
        ("INSURED NAME", "Portfolio Analysis - Detailed by INSURED NAME", "INSURED_NAME", "Insured Name"),
        ("PCKG DESC", "Portfolio Analysis - Detailed by PCKG DESC", "PCKG_DESC", "Package Desc"),
        ("TSI", "Portfolio Analysis - Detailed by TSI RANGE", "TSI RANGE", "TSI Range"),
        ("OCCUPATION", "Portfolio Analysis - Detailed by OCCUPATION", "OCCUPATION", "OCCUPATION"),
        ("POL NO", "Portfolio Analysis - Detailed by POLICY NUMBER", "POLICY_NO", "Policy No"),
    ]

    available_extra_dim_map = {
        label: col for _, _, col, label in tab_defs if col in df.columns
    }

    extra_key = "mv_detailed_table_extra_columns"
    extra_options = list(available_extra_dim_map.keys())
    if extra_key in st.session_state:
        st.session_state[extra_key] = [v for v in st.session_state.get(extra_key, []) if v in extra_options]

    def _reset_mv_extra_columns():
        st.session_state[extra_key] = []

    # Compact inline controls only; no separate card/title.
    # Do not pass default when using a session_state-backed key, otherwise
    # Streamlit warns: widget created with default value and set via Session State API.
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
    ctrl_col1, ctrl_col2 = st.columns([5.2, 1.1], gap="small")
    with ctrl_col2:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        st.button(
            "Reset",
            key="mv_reset_extra_columns_btn",
            width="stretch",
            on_click=_reset_mv_extra_columns,
        )
    with ctrl_col1:
        selected_extra_labels = st.multiselect(
            "Additional columns",
            options=extra_options,
            max_selections=5,
            key=extra_key,
            help="Tambahan breakdown untuk detailed table",
        )
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    selected_extra_cols = [available_extra_dim_map[x] for x in selected_extra_labels]

    def build_group_cols(primary_col):
        cols = [primary_col]
        for c in selected_extra_cols:
            if c != primary_col and c not in cols:
                cols.append(c)
        return _existing_cols(df, cols)

    tab_labels = [tab_label for tab_label, _, _, _ in tab_defs]
    active_detail_tab_key = "mv_active_detail_tab"
    if active_detail_tab_key not in st.session_state or st.session_state[active_detail_tab_key] not in tab_labels:
        st.session_state[active_detail_tab_key] = tab_labels[0]

    # Scoped styling for the Detailed Data tab strip only.
    # Uses the radio aria-label (Detailed view), so sidebar radios are untouched.
    st.markdown("""
    <style>
      div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Detailed view"]) {
        width: 100% !important;
        max-width: 100% !important;
        margin-top: 2px !important;
        margin-bottom: 0 !important;
        overflow: hidden !important;
      }
      div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Detailed view"]) > div {
        width: 100% !important;
        max-width: 100% !important;
        overflow-x: auto !important;
        overflow-y: hidden !important;
        padding: 0 0 5px 0 !important;
        scrollbar-width: thin !important;
      }
      div[role="radiogroup"][aria-label="Detailed view"] {
        display: inline-flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        width: fit-content !important;
        min-width: 100% !important;
        max-width: none !important;
        gap: 8px !important;
        padding: 4px 4px 7px 4px !important;
        border-bottom: 1px solid rgba(0, 51, 102, 0.14) !important;
        box-sizing: border-box !important;
      }
      div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Detailed view"]) > div::-webkit-scrollbar { height: 7px !important; }
      div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Detailed view"]) > div::-webkit-scrollbar-thumb {
        background: rgba(0,51,102,0.24) !important;
        border-radius: 999px !important;
      }
      div[role="radiogroup"][aria-label="Detailed view"] label {
        flex: 0 0 auto !important;
        width: auto !important;
        min-width: auto !important;
        white-space: nowrap !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 9px 16px !important;
        margin: 0 !important;
        border-radius: 999px !important;
        border: 1px solid rgba(0,51,102,0.14) !important;
        background: linear-gradient(180deg, #FFFFFF 0%, #F4F7FB 100%) !important;
        color: #334155 !important;
        font-size: 12.5px !important;
        line-height: 1 !important;
        font-weight: 760 !important;
        letter-spacing: -0.01em !important;
        box-shadow: 0 5px 14px rgba(15,23,42,0.045) !important;
        transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease !important;
      }
      div[role="radiogroup"][aria-label="Detailed view"] label:hover {
        background: #EEF6FF !important;
        color: #003366 !important;
        border-color: rgba(0,51,102,0.28) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 8px 18px rgba(0,51,102,0.09) !important;
      }
      div[role="radiogroup"][aria-label="Detailed view"] label:has(input:checked) {
        background: linear-gradient(135deg, #003366 0%, #1F5A91 100%) !important;
        color: #FFFFFF !important;
        border-color: rgba(0,51,102,0.72) !important;
        box-shadow: 0 10px 22px rgba(0,51,102,0.20) !important;
      }
      div[role="radiogroup"][aria-label="Detailed view"] label:has(input:checked) *,
      div[role="radiogroup"][aria-label="Detailed view"] label:has(input:checked) p,
      div[role="radiogroup"][aria-label="Detailed view"] label:has(input:checked) span,
      div[role="radiogroup"][aria-label="Detailed view"] label:has(input:checked) div {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
      }
      div[role="radiogroup"][aria-label="Detailed view"] label p,
      div[role="radiogroup"][aria-label="Detailed view"] label span {
        color: inherit !important;
        font-weight: inherit !important;
        white-space: nowrap !important;
      }
      div[role="radiogroup"][aria-label="Detailed view"] input,
      div[role="radiogroup"][aria-label="Detailed view"] svg {
        display: none !important;
      }
      .detail-tab-content-card {
        background: #ffffff;
        border: 1px solid rgba(0,51,102,0.12);
        border-radius: 18px;
        padding: 18px 18px 20px 18px;
        box-shadow: 0 10px 25px rgba(15,23,42,0.045);
        margin-top: 2px;
      }
    </style>
    """, unsafe_allow_html=True)

    active_tab_label = st.radio(
        "Detailed view",
        options=tab_labels,
        key=active_detail_tab_key,
        horizontal=True,
        label_visibility="collapsed",
    )

    st.markdown('<div class="detail-tab-content-card">', unsafe_allow_html=True)

    def pivot_tab(group_cols, tab_name):
        group_cols = _existing_cols(df, group_cols)
        if not group_cols:
            st.info("This breakdown is unavailable because the required column is not present in the MV dataset.")
            return

        safe_tab_name = (
            tab_name.replace(" ", "_")
            .replace("/", "_")
            .replace("\\", "_")
            .replace(":", "_")
        )

        pivot = cached_pivot(df, tuple(group_cols), row_limit=200)
        if pivot is None or pivot.empty:
            st.info("No data available for this breakdown.")
            return
        format_and_display(pivot, table_key=safe_tab_name)

        include_claim_breakdown = bool(
            st.session_state.get(f"include_claim_summary__{safe_tab_name}", True)
        )

        render_export_controls_fragment(
            safe_tab_name,
            tab_name,
            tuple(group_cols),
            df,
            active_filters,
            tanggal_pilihan,
            username,
            risk_detail_for_claim,
            bool(include_claim_breakdown),
        )

    active_config = next((cfg for cfg in tab_defs if cfg[0] == active_tab_label), tab_defs[0])
    tab_label, tab_name, primary_col, subheader_label = active_config
    display_title = subheader_label if subheader_label.startswith("Portfolio Analysis") else f"Portfolio Analysis - Detailed by {subheader_label}"
    st.markdown(f"<div style='font-size:14px;font-weight:800;color:#003366;margin:4px 0 6px 0;'>{html.escape(display_title)}</div>", unsafe_allow_html=True)
    if primary_col not in df.columns:
        st.info(f"This breakdown is unavailable because {primary_col} is not present in the MV dataset.")
    else:
        group_cols = build_group_cols(primary_col)
        pivot_tab(group_cols, tab_name)
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# DASHBOARD UTAMA
# =========================
# DASHBOARD UTAMA
# =========================
# =========================
# DASHBOARD UTAMA OPTIMIZED
# =========================
def dashboard(username):
    st.markdown("""
    <div class="hero">
      <h1>Combined Ratio Dashboard</h1>
    </div>
    """, unsafe_allow_html=True)

    tanggal_opsi = ["260123_20 Februari 2026", "260410_10 April 2026", "260626_26 Juni 2026", "260724_24 Juli 2026", "260904_4 September 2026", "261002_2 Oktober 2026", "261023_23 Oktober 2026"]
    tanggal_pilihan = st.selectbox("Pilih tanggal:", tanggal_opsi, index=6)

    st.header(f"As at {tanggal_pilihan[7:]}")
    #st.subheader("in IDR Mio")

    if tanggal_pilihan == "260410_10 April 2026":
        df = load_parquet("MV260410v2.parquet")
    elif tanggal_pilihan == "260123_20 Februari 2026":
        df = load_parquet("MV260220.parquet")
    elif tanggal_pilihan == "260626_26 Juni 2026":
        df = load_parquet("MV260626 v2.parquet")
    elif tanggal_pilihan == "260724_24 Juli 2026":
        df = load_parquet("MV260724.parquet")
    elif tanggal_pilihan == "260904_4 September 2026":
        df = load_parquet("MV260904.parquet")
    elif tanggal_pilihan == "261002_2 Oktober 2026":
        df = load_parquet("MV261002.parquet")
    elif tanggal_pilihan == "261023_23 Oktober 2026":
        df = load_parquet("MV261023.parquet")
        
    st.sidebar.header("Filters")
    filter_cols = [
        "UW_YEAR", "BRANCH", "MAIN_COVERAGE", "INTERMEDIARY_NAME", "INSURED_NAME", "MARKETING_NAME", "MARKETING_GROUP", "BRAND", "CATEGORY", "MODEL", "SUBMODEL", "TOB", "LOB", "TSI RANGE", 
        "PROVINCE", "PLAT NO", "PCKG_DESC", "FUNCTION"]

    # =========================
    # PERSISTENT FILTERS
    # =========================
    active_filters = {}
    filtered_df = df

    for col in filter_cols:
        if col not in filtered_df.columns:
            continue

        mode_key = f"{col}_mode"
        sel_key = f"{col}_selected"

        if mode_key not in st.session_state:
            st.session_state[mode_key] = "Include Selected"

        with st.sidebar.expander(field_display_name(col), expanded=False):
            mode = st.selectbox(
                "Mode & Selection",
                ["Include Selected", "Include All", "Exclude Selected", "Exclude All"],
                key=mode_key,
            )

            show_multiselect = mode in ["Include Selected", "Exclude Selected"]
            current_options = sorted(filtered_df[col].dropna().unique())

            existing_selected = st.session_state.get(sel_key, [])
            valid_selected = [v for v in existing_selected if v in current_options]

            if not show_multiselect:
                st.session_state.pop(sel_key, None)
                selected_vals = []
                st.multiselect(
                    "Choose items",
                    current_options,
                    key=f"{sel_key}__disabled",
                    disabled=True,
                )
            else:
                if sel_key not in st.session_state:
                    st.session_state[sel_key] = valid_selected
                elif st.session_state[sel_key] != valid_selected:
                    st.session_state[sel_key] = valid_selected

                selected_vals = st.multiselect(
                    "Choose items",
                    current_options,
                    key=sel_key,
                )

            if mode.startswith("Include") and selected_vals:
                filtered_df = filtered_df[filtered_df[col].isin(selected_vals)]
            elif mode.startswith("Exclude") and selected_vals:
                filtered_df = filtered_df[~filtered_df[col].isin(selected_vals)]

            active_filters[col] = {"mode": mode, "values": list(selected_vals)}

    # Dedicated electric-vehicle filter. It is rendered explicitly so the UI
    # object cannot disappear silently when a parquet column has a minor alias.
    electric_col = "IS_ELECTRIC" if "IS_ELECTRIC" in filtered_df.columns else None
    electric_mode_key = "IS_ELECTRIC_mode"
    electric_sel_key = "IS_ELECTRIC_selected"

    if electric_mode_key not in st.session_state:
        st.session_state[electric_mode_key] = "Include Selected"

    with st.sidebar.expander("IS_ELECTRIC", expanded=False):
        electric_mode = st.selectbox(
            "Mode & Selection",
            ["Include Selected", "Include All", "Exclude Selected", "Exclude All"],
            key=electric_mode_key,
        )

        show_electric_multiselect = electric_mode in ["Include Selected", "Exclude Selected"]

        if electric_col is not None:
            available_electric = [
                str(v).strip()
                for v in filtered_df[electric_col].dropna().unique()
                if str(v).strip()
            ]
            preferred_order = ["EV", "NON EV"]
            electric_options = [v for v in preferred_order if v in available_electric]
            electric_options += sorted(v for v in set(available_electric) if v not in preferred_order)
        else:
            electric_options = ["EV", "NON EV"]

        existing_electric = st.session_state.get(electric_sel_key, [])
        valid_electric = [v for v in existing_electric if v in electric_options]

        if not show_electric_multiselect:
            st.session_state.pop(electric_sel_key, None)
            electric_selected = []
            st.multiselect(
                "Choose items",
                electric_options,
                key=f"{electric_sel_key}__disabled",
                disabled=True,
            )
        else:
            if electric_sel_key not in st.session_state:
                st.session_state[electric_sel_key] = valid_electric
            elif st.session_state[electric_sel_key] != valid_electric:
                st.session_state[electric_sel_key] = valid_electric

            electric_selected = st.multiselect(
                "Choose items",
                electric_options,
                key=electric_sel_key,
                disabled=electric_col is None,
            )

        if electric_col is None:
            st.caption("Kolom IS_ELECTRIC tidak ditemukan pada dataset tanggal ini.")
        elif electric_mode.startswith("Include") and electric_selected:
            normalized_electric = filtered_df[electric_col].astype("string").str.strip()
            filtered_df = filtered_df[normalized_electric.isin(electric_selected)]
        elif electric_mode.startswith("Exclude") and electric_selected:
            normalized_electric = filtered_df[electric_col].astype("string").str.strip()
            filtered_df = filtered_df[~normalized_electric.isin(electric_selected)]

        active_filters["IS_ELECTRIC"] = {
            "mode": electric_mode,
            "values": list(electric_selected),
        }

    df = filtered_df  # update df setelah semua filter diterapkan
    if df.empty:
        st.warning("No data on this filter")
    
        # Tetap render tabs kosong (biar UI konsisten)
        tabs = st.tabs([
            "UW YEAR", "CVRG", "BRANCH", "MKT NAME", "MKT GROUP",
            "AGE", "BRAND", "CAT", "SUB MODEL",
            "MODEL", "TOB", "USAGE", "INT NAME", "INS NAME", "PCKG", "TSI", "OCCUPATION", "POL NO"
        ])
    
        for t in tabs:
            with t:
                st.info("No data on this filter")
    
        return  # STOP dashboard di sini

    kpis = compute_kpis(df)
    render_section_card_header("Key Performance Indicators")
    render_kpi_cards(kpis)
    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

    render_projection_section(df)
    
    risk_detail_for_claim = pd.DataFrame()
    if {"POLICY_NO", "UW_YEAR"}.issubset(df.columns):
        risk_detail_for_claim = (
            df[["POLICY_NO", "UW_YEAR"]]
            .dropna()
            .drop_duplicates()
            .reset_index(drop=True)
        )

    render_detailed_data_fragment(
        df,
        active_filters,
        tanggal_pilihan,
        username,
        risk_detail_for_claim,
    )

    render_claim_breakdown_stable(risk_detail_for_claim)

# =========================
# MAIN
# =========================
def dashboard1(username):
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = True
    if not st.session_state["logged_in"]:
        st.write("Please login from main SuperApp.")
    else:
        try:
            dashboard(username)
        except Exception as e:
            st.error("Under Reconstruction\n#BakalJadiKeren")
            with st.expander("Technical details", expanded=False):
                st.code(str(e))
        if st.sidebar.button("Logout", key="logout_btn"):
            st.session_state["logged_in"] = False
            st.rerun()

def main(username="guest"):
    dashboard1(username)

if __name__ == "__main__":
    main()
