import base64
import hashlib
import html
import io
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except Exception:  # app can still run without Google Sheet dependencies
    gspread = None
    ServiceAccountCredentials = None

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
except Exception:
    colors = None


DEFAULT_PRODUCTION_PATH = "Produksi - 260519 v2.parquet"
MODULE_NAME = "Super Production"
THEME_BLUE = "#003366"
THEME_ORANGE = "#E39A5B"
JKT = ZoneInfo("Asia/Jakarta")

DISPLAY_UNIT_OPTIONS = ["in IDR Mio", "in IDR Thousand", "Original Number"]
DISPLAY_UNIT_FACTOR = {"in IDR Mio": 1_000_000, "in IDR Thousand": 1_000, "Original Number": 1}
DISPLAY_UNIT_SHORT = {"in IDR Mio": "Mio", "in IDR Thousand": "Thousand", "Original Number": "Original"}

VALUE_COLS = ["GWP", "COMM_IDR", "RI Premium", "RI COM", "CLAIM_PAID", "Klaim Bruto", "OS", "RI Claim"]
BASE_FILTER_COLS = [
    "IS_FRONTING", "ACCT_YEAR", "ACCT_MONTH", "UW_YEAR", "COB_CODE", "TOB_CODE", "SOB_CODE", "LOB_CODE",
    "BRANCH", "MARKETING_GROUP", "MARKETING_NAME", "INTERMEDIARY_GROUPED", "IS NEW"
]
DETAIL_OPTIONS = {
    "Acct Year": "ACCT_YEAR",
    "Acct Month": "ACCT_MONTH",
    "UW Year": "UW_YEAR",
    "COB": "COB_CODE",
    "TOB": "TOB_CODE",
    "SOB": "SOB_CODE",
    "LOB": "LOB_CODE",
    "Branch": "BRANCH",
    "Intermediary": "INTERMEDIARY_GROUPED",
    "Original Intermediary": "INTERMEDIARY_NAME",
    "Marketing Group": "MARKETING_GROUP",
    "Marketing Name": "MARKETING_NAME",
    "Insured Name": "INSURED_NAME",
    "Policy No": "POLICY_NO",
    "Fronting Status": "IS_FRONTING",
}
YOY_METRICS = {
    "GWP": "GWP",
    "Jumlah Risiko": "NUMBER_OF_RISKS",
    "Net Premium": "NET_PREMIUM",
    "Commission": "COMM_IDR",
    "Commission Ratio": "COMM_RATIO",
    "RI Premium": "RI Premium",
    "RI Ratio": "RI_RATIO",
    "Klaim Bruto": "Klaim Bruto",
    "Paid Claim": "CLAIM_PAID",
    "Outstanding Claim": "OS",
}

DOC_SHEET = "production_document_filter_log"
REPORT_SHEET = "production_saved_reports"
DOC_HEADERS = ["DOC_ID", "CREATED_AT", "USERNAME", "MODULE", "EXPORT_TYPE", "ACTIVE_DETAIL_TAB", "DETAIL_EXTRA_COLUMNS_JSON", "GROUP_COLS_JSON", "FILTERS_JSON", "DISPLAY_UNIT", "PROXY_MAPPING_JSON", "YOY_METRICS_JSON", "TOTAL_ROWS", "FILE_NAME"]
REPORT_HEADERS = ["REPORT_ID", "CREATED_AT", "UPDATED_AT", "OWNER", "LABEL", "DESCRIPTION", "LAST_UPDATED_BY", "MODULE", "IS_ACTIVE"]


# ==========================================================
# Theme / helpers
# ==========================================================
def inject_theme_css() -> None:
    st.markdown("""
    <style>
      .block-container { padding-top: 1.1rem !important; }
      .prod-hero{border:1px solid rgba(0,51,102,.12);border-radius:24px;padding:18px 20px;background:linear-gradient(135deg,#fff 0%,#F8FAFC 62%,#EEF6FF 100%);box-shadow:0 14px 34px rgba(15,23,42,.06);margin-bottom:12px;}
      .prod-title{font-size:26px;line-height:1.1;font-weight:900;letter-spacing:-.025em;color:#003366;margin-bottom:4px;}
      .prod-subtitle{font-size:13px;color:#64748B;font-weight:650;line-height:1.35;}
      .asof-chip{display:inline-flex;gap:6px;align-items:center;margin-top:9px;padding:6px 10px;border-radius:999px;background:#EEF6FF;border:1px solid rgba(0,51,102,.12);color:#003366;font-size:12px;font-weight:800;}
      .section-card-header{margin:14px 0 8px 0;padding:12px 15px;border-radius:16px;background:#F8FAFC;border:1px solid rgba(0,51,102,.10);box-shadow:0 8px 22px rgba(15,23,42,.035);}
      .section-card-title{font-size:18px;font-weight:850;line-height:1.15;color:#003366;letter-spacing:-.01em;}
      .kpi-card-prod{height:112px;padding:14px 16px;border-radius:22px;background:#fff;border:1px solid rgba(0,51,102,.12);box-shadow:0 10px 26px rgba(15,23,42,.055);overflow:hidden;}
      .kpi-card-prod h4{margin:0;color:#64748B;font-size:12.5px;line-height:1.15;font-weight:750;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
      .kpi-card-prod h2{margin:5px 0 0 0;color:#003366;font-size:30px;line-height:1;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
      .kpi-card-prod .foot{margin-top:8px;color:#94A3B8;font-size:11px;font-weight:650;}
      .prod-card{background:#fff;border:1px solid rgba(0,51,102,.12);border-radius:18px;padding:16px;box-shadow:0 10px 25px rgba(15,23,42,.045);}
      .saved-report-preview-card{margin:10px 0 4px 0;padding:12px 14px;border-radius:15px;background:linear-gradient(180deg,#F8FAFC 0%,#fff 100%);border:1px solid rgba(0,51,102,.11);box-shadow:0 7px 18px rgba(15,23,42,.035);}
      .saved-report-card-title{font-size:14px;font-weight:850;color:#003366;line-height:1.2;}.saved-report-card-id{display:inline-flex;margin-top:6px;padding:4px 8px;border-radius:999px;background:#EEF6FF;color:#003366;font-size:11.5px;font-weight:800;border:1px solid rgba(0,51,102,.10);}.saved-report-card-desc{margin-top:8px;font-size:12.2px;line-height:1.35;color:#475569;}.saved-report-card-meta{margin-top:8px;font-size:11.5px;color:#64748B;font-weight:650;}
      section[data-testid="stSidebar"] .stButton button,
      section[data-testid="stSidebar"] div[data-testid="stFormSubmitButton"] button,
      section[data-testid="stSidebar"] button[kind="secondary"],
      section[data-testid="stSidebar"] button[kind="primary"]{
        background:linear-gradient(135deg,#003366,#1F5A91)!important;
        color:#fff!important;
        -webkit-text-fill-color:#fff!important;
        border:1px solid rgba(0,51,102,.55)!important;
        border-radius:11px!important;
        font-weight:850!important;
        box-shadow:0 8px 18px rgba(0,51,102,.16)!important;
      }
      section[data-testid="stSidebar"] .stButton button *,
      section[data-testid="stSidebar"] div[data-testid="stFormSubmitButton"] button *,
      section[data-testid="stSidebar"] button[kind="secondary"] *,
      section[data-testid="stSidebar"] button[kind="primary"] *{
        color:#fff!important;
        -webkit-text-fill-color:#fff!important;
      }
      section[data-testid="stSidebar"] button:hover{filter:brightness(1.06)!important;}
      .prod-sidebar-asof{margin:0 0 10px 0;padding:9px 10px;border-radius:14px;background:#EEF6FF;border:1px solid rgba(0,51,102,.13);color:#003366;font-size:12px;font-weight:850;line-height:1.2;}
      div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Production workspace"]) > div{overflow-x:auto!important;padding-bottom:4px!important;}

      /* Detailed Data tab strip: copied from Risk Profile behavior */
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
      div[role="radiogroup"][aria-label="Production workspace"],
      div[role="radiogroup"][aria-label="Saved report workspace"]{
        display:inline-flex!important;flex-direction:row!important;flex-wrap:nowrap!important;gap:8px!important;min-width:100%!important;padding:4px 4px 8px 4px!important;border-bottom:1px solid rgba(0,51,102,.12)!important;
      }
      div[role="radiogroup"][aria-label="Production workspace"] label,
      div[role="radiogroup"][aria-label="Saved report workspace"] label,
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
      div[role="radiogroup"][aria-label="Detailed view"] label:hover,
      div[role="radiogroup"][aria-label="Production workspace"] label:hover,
      div[role="radiogroup"][aria-label="Saved report workspace"] label:hover {
        background: #EEF6FF !important;
        color: #003366 !important;
        border-color: rgba(0,51,102,0.28) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 8px 18px rgba(0,51,102,0.09) !important;
      }
      div[role="radiogroup"][aria-label="Detailed view"] label:has(input:checked),
      div[role="radiogroup"][aria-label="Production workspace"] label:has(input:checked),
      div[role="radiogroup"][aria-label="Saved report workspace"] label:has(input:checked) {
        background: linear-gradient(135deg, #003366 0%, #1F5A91 100%) !important;
        color: #FFFFFF !important;
        border-color: rgba(0,51,102,0.72) !important;
        box-shadow: 0 10px 22px rgba(0,51,102,0.20) !important;
      }
      div[role="radiogroup"][aria-label="Detailed view"] label:has(input:checked) *,
      div[role="radiogroup"][aria-label="Production workspace"] label:has(input:checked) *,
      div[role="radiogroup"][aria-label="Saved report workspace"] label:has(input:checked) * {
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
      div[role="radiogroup"][aria-label="Detailed view"] svg,
      div[role="radiogroup"][aria-label="Production workspace"] input,
      div[role="radiogroup"][aria-label="Production workspace"] svg,
      div[role="radiogroup"][aria-label="Saved report workspace"] input,
      div[role="radiogroup"][aria-label="Saved report workspace"] svg {
        display: none !important;
      }
      .direct-download-btn{display:inline-block;padding:0;background:transparent;color:#003366!important;border:none;text-decoration:underline!important;text-underline-offset:3px;font-weight:800;font-size:13px;}
    </style>
    """, unsafe_allow_html=True)


def section_header(title: str) -> None:
    st.markdown(f"<div class='section-card-header'><div class='section-card-title'>{html.escape(title)}</div></div>", unsafe_allow_html=True)


def _safe_json(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _safe_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_json(v) for v in value]
    if isinstance(value, pd.DataFrame):
        return [_safe_json(r) for r in value.to_dict(orient="records")]
    return value


def _to_json(value) -> str:
    return json.dumps(_safe_json(value), ensure_ascii=False, default=str)


def _from_json(value, default=None):
    if default is None:
        default = {}
    try:
        if value is None or str(value).strip() == "":
            return default
        return json.loads(str(value))
    except Exception:
        return default


def _sanitize_id(x: str) -> str:
    return str(x or "").strip().upper().replace(" ", "")


def _hash_payload(payload) -> str:
    return hashlib.sha1(json.dumps(_safe_json(payload), sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _data_uri(data: bytes, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def _download_link(label: str, href: str, file_name: str):
    st.markdown(f'<a class="direct-download-btn" download="{html.escape(file_name, quote=True)}" href="{href}">{html.escape(label)}</a>', unsafe_allow_html=True)


# ==========================================================
# Data
# ==========================================================
def _find_default_path(path: str | None = None) -> str:
    candidates = [path, DEFAULT_PRODUCTION_PATH, f"/mnt/data/{DEFAULT_PRODUCTION_PATH}"]
    for p in candidates:
        if p and Path(p).exists():
            return str(p)
    return str(path or DEFAULT_PRODUCTION_PATH)


def _optimize_df_memory(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.select_dtypes(include=["int", "int64", "int32"]).columns:
        out[col] = pd.to_numeric(out[col], downcast="integer")
    for col in out.select_dtypes(include=["float", "float64", "float32"]).columns:
        out[col] = pd.to_numeric(out[col], downcast="float")
    n = max(len(out), 1)
    for col in out.select_dtypes(include=["object"]).columns:
        try:
            nunique = out[col].nunique(dropna=True)
            if nunique <= 8000 and nunique / n <= 0.45:
                out[col] = out[col].astype("category")
        except Exception:
            pass
    return out


@st.cache_data(show_spinner=False, ttl=900, max_entries=2)
def load_production_data(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path)
    return _optimize_df_memory(prepare_production_df(df))


def _acct_month_sort_key(value) -> int:
    """Sort ACCT_MONTH labels such as '01. Januari' without converting the column to numeric."""
    import re
    txt = str(value or "").strip()
    m = re.match(r"\s*(\d{1,2})", txt)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    month_map = {
        "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
        "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
        "january": 1, "february": 2, "march": 3, "may": 5, "june": 6, "july": 7,
        "august": 8, "october": 10, "december": 12,
    }
    low = txt.lower()
    for name, num in month_map.items():
        if name in low:
            return num
    return 99


def prepare_production_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["EFF_DATE", "EXP_DATE"]:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce")

    # Keep ACCT_MONTH as a label because the new production file uses values like
    # '01. Januari'. Converting it to numeric turns the whole column into NaN and
    # makes the sidebar filter empty. Use ACCT_MONTH_NO only for internal sorting.
    for col in ["ACCT_YEAR", "ACCT_PERIOD", "UW_YEAR"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "ACCT_MONTH" in out.columns:
        out["ACCT_MONTH"] = out["ACCT_MONTH"].astype("string").fillna("(Blank)").str.strip().replace("", "(Blank)")
        out["ACCT_MONTH_NO"] = out["ACCT_MONTH"].apply(_acct_month_sort_key).astype("int16")
    elif "ACCT_MONTH.1" in out.columns:
        out["ACCT_MONTH"] = out["ACCT_MONTH.1"].astype("string").fillna("(Blank)").str.strip().replace("", "(Blank)")
        out["ACCT_MONTH_NO"] = out["ACCT_MONTH"].apply(_acct_month_sort_key).astype("int16")

    for col in VALUE_COLS:
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
    out["NET_PREMIUM"] = out["GWP"] - out["RI Premium"]
    out["NET_COMM"] = out["COMM_IDR"] - out["RI COM"]
    out["NET_CLAIM"] = out["Klaim Bruto"] - out["RI Claim"]
    out["INTERMEDIARY_GROUPED"] = out.get("INTERMEDIARY_NAME", pd.Series([""] * len(out))).astype("string").fillna("(Blank)").str.strip().replace("", "(Blank)")
    if "IS_FRONTING" in out.columns:
        out["IS_FRONTING"] = out["IS_FRONTING"].astype("string").fillna("(Blank)").str.strip()
    return out


def get_as_of_text(df: pd.DataFrame, source_path: str | None = None) -> str:
    """Return display-friendly As of Date.

    Production files are usually named with YYMMDD, for example
    `Produksi - 260519.parquet`, so show it as `19 May 2026`.
    This is clearer than displaying only ACCT_PERIOD such as 2026-05.
    """
    import re

    # Prefer the date embedded in the production file name when available.
    if source_path:
        name = Path(str(source_path)).name
        m = re.search(r"(\d{6})(?=\D*$)", name)
        if m:
            token = m.group(1)
            try:
                dt = datetime.strptime(token, "%y%m%d")
                return dt.strftime("%d %b %Y").lstrip("0")
            except Exception:
                pass

    if df is None or df.empty:
        return "-"
    if "ACCT_PERIOD" in df.columns:
        s = pd.to_numeric(df["ACCT_PERIOD"], errors="coerce").dropna()
        if not s.empty:
            period = str(int(s.max()))
            if len(period) == 6:
                try:
                    dt = datetime.strptime(period + "01", "%Y%m%d")
                    return dt.strftime("%b %Y")
                except Exception:
                    return f"{period[:4]}-{period[4:]}"
            return period
    if "ACCT_YEAR" in df.columns and ("ACCT_MONTH_NO" in df.columns or "ACCT_MONTH" in df.columns):
        y = pd.to_numeric(df["ACCT_YEAR"], errors="coerce").max()
        if "ACCT_MONTH_NO" in df.columns:
            m = pd.to_numeric(df["ACCT_MONTH_NO"], errors="coerce").max()
        else:
            m = pd.to_numeric(df["ACCT_MONTH"], errors="coerce").max()
        if pd.notna(y) and pd.notna(m) and int(m) <= 12:
            try:
                dt = datetime(int(y), int(m), 1)
                return dt.strftime("%b %Y")
            except Exception:
                return f"{int(y)}-{int(m):02d}"
    return datetime.now(JKT).strftime("%d %b %Y").lstrip("0")


@st.cache_data(show_spinner=False, ttl=900, max_entries=128)
def unique_options(df: pd.DataFrame, col: str, limit: int = 20000) -> list:
    """Cached distinct values for sidebar filters.

    This prevents recalculating option lists on every rerun. ACCT_MONTH is kept
    as a text label and sorted by the leading month number, e.g. 01, 02, 03.
    """
    if col not in df.columns:
        return []
    vals = df[col].dropna().astype(str).unique().tolist()
    vals = [v for v in vals if v.strip() != ""]
    if col == "ACCT_MONTH":
        vals = sorted(vals, key=lambda v: (_acct_month_sort_key(v), str(v)))
    else:
        vals = sorted(vals)
    return vals[:limit]


@st.cache_data(show_spinner=False, ttl=900, max_entries=16)
def cached_filter_options_map(df: pd.DataFrame, filter_cols: tuple[str, ...]) -> dict:
    """Cache all sidebar option lists in one object.

    The filter fragments receive only these small lists, not the full dataframe,
    which helps avoid Streamlit Cloud memory spikes.
    """
    return {col: unique_options(df, col) for col in filter_cols if col in df.columns}


def apply_proxy_mapping(df: pd.DataFrame) -> pd.DataFrame:
    mapping = st.session_state.get("prod_proxy_mapping", {}) or {}
    if not mapping or "INTERMEDIARY_NAME" not in df.columns:
        return df
    reverse = {}
    for group, members in mapping.items():
        for m in members or []:
            reverse[str(m).strip()] = str(group).strip()
    if not reverse:
        return df
    out = df.copy()
    base = out["INTERMEDIARY_NAME"].astype("string").fillna("(Blank)").str.strip()
    out["INTERMEDIARY_GROUPED"] = base.map(reverse).fillna(base).replace("", "(Blank)")
    return out


def default_filter_state(df: pd.DataFrame) -> dict:
    state = {}
    for col in BASE_FILTER_COLS:
        if col not in df.columns:
            continue
        opts = unique_options(df, col)
        if col == "IS_FRONTING":
            # Default production dashboard mengikuti kebutuhan user:
            # hanya Non Fronting yang ditampilkan saat pertama kali dibuka/reset.
            non_fronting_vals = [
                v for v in opts
                if "NON" in str(v).upper().replace("-", "_").replace(" ", "_")
                and "FRONTING" in str(v).upper().replace("-", "_").replace(" ", "_")
            ]
            if non_fronting_vals:
                state[col] = {"mode": "Include Selected", "values": non_fronting_vals}
            else:
                state[col] = {"mode": "Include All", "values": []}
        else:
            state[col] = {"mode": "Include All", "values": []}
    return state


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    out = df
    for col, info in (filters or {}).items():
        if col not in out.columns or not isinstance(info, dict):
            continue
        mode = info.get("mode", "Include All")
        vals = info.get("values", []) or []
        if mode == "Include All":
            continue
        if mode == "Exclude All":
            out = out.iloc[0:0]
        elif mode == "Include Selected" and vals:
            out = out[out[col].astype(str).isin([str(v) for v in vals])]
        elif mode == "Exclude Selected" and vals:
            out = out[~out[col].astype(str).isin([str(v) for v in vals])]
    return out


# ==========================================================
# Google Sheet saved reports
# ==========================================================
def _gsheet_client():
    if gspread is None or ServiceAccountCredentials is None:
        return None
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp"], scope)
        return gspread.authorize(creds)
    except Exception:
        return None


def _get_sheet(sheet_name: str, headers: list[str]):
    client = _gsheet_client()
    if client is None:
        return None
    spreadsheet = client.open("Login Log")
    try:
        sheet = spreadsheet.worksheet(sheet_name)
    except Exception:
        sheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=len(headers))
    try:
        if sheet.row_values(1)[:len(headers)] != headers:
            sheet.update("A1", [headers])
    except Exception:
        pass
    return sheet


def generate_report_id(prefix: str = "SP") -> str:
    return f"{prefix}-{datetime.now(JKT).strftime('%y%m%d')}-{hashlib.sha1(str(datetime.now(JKT).timestamp()).encode()).hexdigest()[:8].upper()}"


def save_document_log(report_id: str, username: str, export_type: str, active_detail_tab: str, extra_cols: list, group_cols: list, filters: dict, display_unit: str, proxy_mapping: dict, yoy_metrics: list, total_rows=None, file_name=""):
    sheet = _get_sheet(DOC_SHEET, DOC_HEADERS)
    row = {
        "DOC_ID": _sanitize_id(report_id),
        "CREATED_AT": datetime.now(JKT).strftime("%Y-%m-%d %H:%M:%S"),
        "USERNAME": username or "",
        "MODULE": MODULE_NAME,
        "EXPORT_TYPE": export_type,
        "ACTIVE_DETAIL_TAB": active_detail_tab or "",
        "DETAIL_EXTRA_COLUMNS_JSON": _to_json(extra_cols or []),
        "GROUP_COLS_JSON": _to_json(group_cols or []),
        "FILTERS_JSON": _to_json(filters or {}),
        "DISPLAY_UNIT": display_unit or "in IDR Mio",
        "PROXY_MAPPING_JSON": _to_json(proxy_mapping or {}),
        "YOY_METRICS_JSON": _to_json(yoy_metrics or []),
        "TOTAL_ROWS": "" if total_rows is None else int(total_rows),
        "FILE_NAME": file_name or "",
    }
    if sheet is not None:
        try:
            sheet.append_row([row.get(h, "") for h in DOC_HEADERS], value_input_option="USER_ENTERED")
            return
        except Exception:
            pass
    # fallback local session, useful if gsheet unavailable
    st.session_state.setdefault("prod_local_saved_logs", []).append(row)


def upsert_saved_report_metadata(report_id: str, username: str, label: str, description: str):
    report_id = _sanitize_id(report_id)
    now = datetime.now(JKT).strftime("%Y-%m-%d %H:%M:%S")
    sheet = _get_sheet(REPORT_SHEET, REPORT_HEADERS)
    row_vals = [report_id, now, now, username or "", label or report_id, description or "", username or "", MODULE_NAME, "TRUE"]
    if sheet is not None:
        try:
            values = sheet.get_all_values()
            headers = values[0] if values else REPORT_HEADERS
            target = None
            created_at = now
            owner = username or ""
            for idx, row in enumerate(values[1:], start=2):
                rec = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
                if _sanitize_id(rec.get("REPORT_ID")) == report_id:
                    target = idx
                    created_at = rec.get("CREATED_AT") or now
                    owner = rec.get("OWNER") or owner
                    break
            row_vals = [report_id, created_at, now, owner, label or report_id, description or "", username or "", MODULE_NAME, "TRUE"]
            if target:
                end_col = chr(ord("A") + len(REPORT_HEADERS) - 1)
                sheet.update(f"A{target}:{end_col}{target}", [row_vals])
            else:
                sheet.append_row(row_vals, value_input_option="USER_ENTERED")
            return
        except Exception:
            pass
    st.session_state.setdefault("prod_local_saved_meta", {})[report_id] = dict(zip(REPORT_HEADERS, row_vals))


def list_saved_reports(limit: int = 120) -> list[dict]:
    out = []
    sheet = _get_sheet(REPORT_SHEET, REPORT_HEADERS)
    if sheet is not None:
        try:
            vals = sheet.get_all_values()
            headers = vals[0] if vals else REPORT_HEADERS
            for row in vals[1:]:
                rec = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
                if _sanitize_id(rec.get("REPORT_ID")) and str(rec.get("IS_ACTIVE", "TRUE")).lower() not in ("false", "0", "deleted", "inactive"):
                    out.append(rec)
        except Exception:
            out = []
    if not out:
        out = list((st.session_state.get("prod_local_saved_meta", {}) or {}).values())
    out.sort(key=lambda r: str(r.get("UPDATED_AT") or r.get("CREATED_AT") or ""), reverse=True)
    return out[:limit]


def get_document_record(report_id: str) -> dict | None:
    report_id = _sanitize_id(report_id)
    sheet = _get_sheet(DOC_SHEET, DOC_HEADERS)
    records = []
    if sheet is not None:
        try:
            records = sheet.get_all_records()
        except Exception:
            records = []
    if not records:
        records = st.session_state.get("prod_local_saved_logs", []) or []
    for rec in reversed(records):
        if _sanitize_id(rec.get("DOC_ID")) == report_id:
            return rec
    return None


def apply_document_record(rec: dict):
    st.session_state["prod_committed_filters"] = _from_json(rec.get("FILTERS_JSON"), {})
    # Clear filter widget keys so the next sidebar render initializes from the loaded report.
    for k in list(st.session_state.keys()):
        if str(k).startswith("prod_filter_mode_") or str(k).startswith("prod_filter_values_"):
            st.session_state.pop(k, None)
    _clear_production_pagination_state()
    st.session_state["prod_display_unit"] = rec.get("DISPLAY_UNIT") or "in IDR Mio"
    st.session_state["prod_proxy_mapping"] = _from_json(rec.get("PROXY_MAPPING_JSON"), {})
    st.session_state["prod_detail_extra_cols"] = _from_json(rec.get("DETAIL_EXTRA_COLUMNS_JSON"), [])
    tab = str(rec.get("ACTIVE_DETAIL_TAB") or "")
    if tab:
        st.session_state["prod_detail_active"] = tab
    yoy = _from_json(rec.get("YOY_METRICS_JSON"), [])
    if yoy:
        st.session_state["prod_yoy_metrics"] = [x for x in yoy if x in YOY_METRICS]
    st.session_state["prod_saved_notice"] = "Report loaded successfully."


def apply_pending_saved_if_any():
    pending = _sanitize_id(st.session_state.pop("prod_pending_open_report", ""))
    if not pending:
        return
    rec = get_document_record(pending)
    if rec:
        apply_document_record(rec)
        st.session_state["prod_current_report_id"] = pending
    else:
        st.session_state["prod_saved_notice"] = "Report not found."


# ==========================================================
# Metrics / tables
# ==========================================================
def fmt_money(x, unit="in IDR Mio") -> str:
    try:
        return f"{int(round(float(x) / DISPLAY_UNIT_FACTOR.get(unit, 1))):,}".replace(",", ".")
    except Exception:
        return "-"


def fmt_num(x) -> str:
    try:
        return f"{int(round(float(x))):,}".replace(",", ".")
    except Exception:
        return "-"


def fmt_pct(x, decimals=1) -> str:
    try:
        if pd.isna(x):
            return "-"
        return f"{float(x):.{decimals}f}%"
    except Exception:
        return "-"


def compute_kpis(df: pd.DataFrame) -> dict:
    gwp = float(df["GWP"].sum()) if "GWP" in df.columns else 0.0
    comm = float(df["COMM_IDR"].sum()) if "COMM_IDR" in df.columns else 0.0
    ri_prem = float(df["RI Premium"].sum()) if "RI Premium" in df.columns else 0.0
    claim = float(df["Klaim Bruto"].sum()) if "Klaim Bruto" in df.columns else 0.0
    net_prem = gwp - ri_prem
    risk_count = int(df["POLICY_NO"].nunique()) if "POLICY_NO" in df.columns else int(len(df))
    avg_prem = gwp / risk_count if risk_count else np.nan
    return {
        "GWP": gwp,
        "NUMBER_OF_RISKS": risk_count,
        "AVG_PREMIUM": avg_prem,
        "COMM_RATIO": comm / gwp * 100 if gwp else np.nan,
        "RI_RATIO": ri_prem / gwp * 100 if gwp else np.nan,
        "NET_PREMIUM": net_prem,
        "CLAIM_RATIO_TO_GWP": claim / gwp * 100 if gwp else np.nan,
    }


@st.cache_data(show_spinner=False, ttl=600, max_entries=64)
def grouped_summary(df: pd.DataFrame, group_cols: tuple[str, ...]) -> pd.DataFrame:
    """Build grouped Super Production summary safely.

    Fix:
    - avoid duplicated column labels in the working dataframe
    - avoid adding POLICY_NO twice when Policy No is also the selected grouping
    - protect pandas groupby from "Grouper for 'POLICY_NO' not 1-dimensional"
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # Some production files can carry duplicated headers after upstream export.
    # Pandas groupby fails if a grouping label resolves to multiple columns.
    source = df.loc[:, ~pd.Index(df.columns).duplicated(keep="first")].copy()

    group_cols = [c for c in list(group_cols or []) if c in source.columns]
    # Preserve order while removing duplicate grouping labels.
    group_cols = list(dict.fromkeys(group_cols))
    if not group_cols:
        return pd.DataFrame()

    needed_cols = group_cols + [
        c for c in VALUE_COLS + ["NET_PREMIUM", "NET_COMM", "NET_CLAIM", "POLICY_NO"]
        if c in source.columns
    ]
    # Critical: remove duplicates from the selected working columns.
    needed_cols = list(dict.fromkeys(needed_cols))
    work = source.loc[:, needed_cols].copy()

    # Extra safety in case the source dataframe itself contains duplicated labels
    # that survived through an unusual pandas path.
    work = work.loc[:, ~pd.Index(work.columns).duplicated(keep="first")].copy()

    for col in group_cols:
        if col not in work.columns:
            continue
        if pd.api.types.is_categorical_dtype(work[col]):
            if "(Blank)" not in work[col].cat.categories:
                work[col] = work[col].cat.add_categories(["(Blank)"])
            work[col] = work[col].fillna("(Blank)")
        else:
            work[col] = work[col].astype("string").fillna("(Blank)")

    agg = {
        c: (c, "sum")
        for c in VALUE_COLS + ["NET_PREMIUM", "NET_COMM", "NET_CLAIM"]
        if c in work.columns
    }
    if "POLICY_NO" in work.columns:
        agg["NUMBER_OF_RISKS"] = ("POLICY_NO", "nunique")

    out = work.groupby(group_cols, dropna=False, observed=True, as_index=False).agg(**agg)
    if "NUMBER_OF_RISKS" not in out.columns:
        out["NUMBER_OF_RISKS"] = 0

    # Make expected numeric columns exist even if the source file is missing one.
    for col in ["GWP", "COMM_IDR", "RI Premium", "Klaim Bruto"]:
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

    out["AVG_PREMIUM"] = np.where(out["NUMBER_OF_RISKS"] > 0, out["GWP"] / out["NUMBER_OF_RISKS"], np.nan)
    out["COMM_RATIO"] = np.where(out["GWP"] != 0, out["COMM_IDR"] / out["GWP"] * 100, np.nan)
    out["RI_RATIO"] = np.where(out["GWP"] != 0, out["RI Premium"] / out["GWP"] * 100, np.nan)
    out["CLAIM_RATIO_TO_GWP"] = np.where(out["GWP"] != 0, out["Klaim Bruto"] / out["GWP"] * 100, np.nan)
    try:
        out = out.sort_values(group_cols, kind="stable")
    except Exception:
        pass
    return out


def final_metric_order(df: pd.DataFrame) -> list:
    metrics = ["NUMBER_OF_RISKS", "GWP", "AVG_PREMIUM", "COMM_IDR", "COMM_RATIO", "RI Premium", "RI_RATIO", "NET_PREMIUM", "Klaim Bruto", "CLAIM_PAID", "OS", "RI Claim", "CLAIM_RATIO_TO_GWP"]
    groups = [c for c in df.columns if c not in metrics + ["RI COM", "NET_COMM", "NET_CLAIM"]]
    return groups + [c for c in metrics if c in df.columns]


# ==========================================================
# Sidebar filters / proxy
# ==========================================================
def render_proxy_manager(raw_df: pd.DataFrame) -> None:
    with st.sidebar.expander("Gabungkan Agen Proxy", expanded=False):
        st.caption("Gabungkan intermediary proxy ke satu nama group. Mapping ini ikut tersimpan dalam Saved Report.")
        mapping = st.session_state.setdefault("prod_proxy_mapping", {})
        names = unique_options(raw_df, "INTERMEDIARY_NAME") if "INTERMEDIARY_NAME" in raw_df.columns else []
        with st.form("prod_proxy_form", clear_on_submit=False):
            group_name = st.text_input("Nama group proxy", key="prod_proxy_group_name", placeholder="Contoh: MNC Finance Group")
            members = st.multiselect("Intermediary members", options=names, key="prod_proxy_members")
            add_clicked = st.form_submit_button("Save Proxy Group")
        if add_clicked:
            clean = str(group_name or "").strip()
            if not clean or not members:
                st.warning("Isi nama group dan pilih minimal satu intermediary.")
            else:
                mapping[clean] = list(members)
                st.session_state["prod_proxy_mapping"] = mapping
                st.success(f"Saved proxy: {clean}")
                st.rerun()
        if mapping:
            st.markdown("**Current proxy mapping**")
            for group, mems in list(mapping.items()):
                c1, c2 = st.columns([0.75, 0.25])
                with c1:
                    st.caption(f"{group}: {len(mems)} intermediary")
                with c2:
                    if st.button("Remove", key=f"remove_proxy_{hashlib.sha1(group.encode()).hexdigest()[:6]}"):
                        mapping.pop(group, None)
                        st.session_state["prod_proxy_mapping"] = mapping
                        st.rerun()
            b64 = base64.b64encode(json.dumps(mapping, ensure_ascii=False, indent=2).encode()).decode()
            st.markdown(f'<a class="direct-download-btn" download="production_proxy_mapping.json" href="data:application/json;base64,{b64}">Download proxy JSON</a>', unsafe_allow_html=True)
        upload = st.file_uploader("Upload proxy mapping JSON", type=["json"], key="prod_proxy_upload")
        if upload is not None:
            try:
                st.session_state["prod_proxy_mapping"] = json.load(upload)
                st.success("Proxy mapping loaded.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to load mapping: {e}")


def _match_filter_values_to_options(values, options):
    """Return actual option objects that match saved values by normalized text.

    This avoids Streamlit multiselect issues when Google Sheet / JSON changes
    values such as 2026 into "2026" or 2026.0.
    """
    values = values or []
    options = list(options or [])

    def _norm(x):
        txt = str(x).strip()
        try:
            f = float(txt.replace(",", ""))
            if f.is_integer():
                txt = str(int(f))
        except Exception:
            pass
        return txt.lower()

    opt_map = {}
    for opt in options:
        opt_map.setdefault(_norm(opt), opt)

    matched = []
    for v in values:
        key = _norm(v)
        if key in opt_map and opt_map[key] not in matched:
            matched.append(opt_map[key])
    return matched


def _clear_production_pagination_state() -> None:
    for k in list(st.session_state.keys()):
        key = str(k)
        if key.startswith("prod_yoy_combined_page") or key.startswith("prod_yoy_page") or key.startswith("prod_detail_page"):
            st.session_state.pop(k, None)


def _reset_production_sidebar_filters(filter_cols: list[str], df: pd.DataFrame) -> None:
    st.session_state["prod_committed_filters"] = default_filter_state(df)
    for col in filter_cols:
        st.session_state.pop(f"prod_filter_mode_{col}", None)
        st.session_state.pop(f"prod_filter_values_{col}", None)
    _clear_production_pagination_state()


def _sync_filter_widget_defaults(df: pd.DataFrame, filter_cols: list[str]) -> None:
    """Initialize sidebar filter widgets from the saved/loaded filter state before rendering."""
    filters = st.session_state.get("prod_committed_filters", default_filter_state(df)) or {}
    modes = ["Include All", "Include Selected", "Exclude Selected", "Exclude All"]
    for col in filter_cols:
        info = filters.get(col, {"mode": "Include All", "values": []}) if isinstance(filters, dict) else {"mode": "Include All", "values": []}
        mode_key = f"prod_filter_mode_{col}"
        values_key = f"prod_filter_values_{col}"
        opts = unique_options(df, col)
        mode = info.get("mode", "Include All") if isinstance(info, dict) else "Include All"
        if mode not in modes:
            mode = "Include All"
        if mode_key not in st.session_state:
            st.session_state[mode_key] = mode
        if values_key not in st.session_state:
            st.session_state[values_key] = _match_filter_values_to_options(info.get("values", []) if isinstance(info, dict) else [], opts)



def _safe_app_rerun() -> None:
    """Full app rerun only when the visible report must actually refresh."""
    try:
        st.rerun(scope="app")
    except TypeError:
        st.rerun()


def _filter_info_from_widget_state(col: str, options: list | None = None) -> dict:
    """Build one saved filter record from widget state without mutating widget keys.

    Streamlit does not allow assigning to st.session_state for a widget key
    after that widget has been instantiated in the same run. This helper is
    called after the filter widgets are rendered, so it must only READ state.
    Any cleanup/normalization needed before a widget is created should happen
    before the corresponding st.multiselect/st.selectbox call.
    """
    mode_key = f"prod_filter_mode_{col}"
    values_key = f"prod_filter_values_{col}"
    mode = st.session_state.get(mode_key, "Include All")
    if mode not in ["Include All", "Include Selected", "Exclude Selected", "Exclude All"]:
        mode = "Include All"

    if mode in ["Include Selected", "Exclude Selected"]:
        values = _match_filter_values_to_options(st.session_state.get(values_key, []) or [], options or [])
        return {"mode": mode, "values": list(values)}
    return {"mode": mode, "values": []}


def _filter_record_signature(info: dict | None) -> tuple:
    info = info or {"mode": "Include All", "values": []}
    vals = tuple(str(v) for v in (info.get("values", []) or []))
    return (str(info.get("mode", "Include All")), vals)


def _persist_one_filter(col: str, info: dict) -> None:
    current = st.session_state.get("prod_committed_filters", {}) or {}
    current[col] = info
    st.session_state["prod_committed_filters"] = current
    _clear_production_pagination_state()


def _should_rerun_report_for_filter_change(old_info: dict, new_info: dict) -> bool:
    """Return True only when the filter result can change.

    A pure switch from Include All to Include Selected/Exclude Selected with no
    selected values is treated as a UI-only action so the value picker appears
    without rerendering the whole report. Value changes and Include/Exclude All
    changes still refresh the report.
    """
    old_sig = _filter_record_signature(old_info)
    new_sig = _filter_record_signature(new_info)
    if old_sig == new_sig:
        return False

    old_mode, old_vals = old_sig
    new_mode, new_vals = new_sig
    if old_mode == "Include All" and new_mode in ("Include Selected", "Exclude Selected") and not new_vals:
        return False
    return True


def _fragment_filter_control_if_available(func):
    return st.fragment(func) if hasattr(st, "fragment") else func


@_fragment_filter_control_if_available
def _render_one_filter_expander(col: str, opts: list, modes: list[str]) -> None:
    """One filter expander isolated as a fragment.

    No widget callbacks are used here. Streamlit warns when a fragment rerun is
    triggered with a callback that writes elements, and that warning can spam the
    logs. Instead, this function reads widget state after rendering, persists the
    filter, and only calls an app rerun when the actual report data must refresh.
    """
    opts = list(opts or [])
    mode_key = f"prod_filter_mode_{col}"
    values_key = f"prod_filter_values_{col}"

    current_mode = st.session_state.get(mode_key, "Include All")
    if current_mode not in modes:
        current_mode = "Include All"
        st.session_state[mode_key] = current_mode

    committed = st.session_state.get("prod_committed_filters", {}) or {}
    old_info = committed.get(col, {"mode": "Include All", "values": []})

    selected_count = len(st.session_state.get(values_key, []) or [])
    label = col.replace("_", " ")
    suffix = ""
    if current_mode in ["Include Selected", "Exclude Selected"] and selected_count:
        suffix = f" · {selected_count} selected"
    elif current_mode == "Exclude All":
        suffix = " · excluded"

    with st.expander(f"{label}{suffix}", expanded=False):
        st.selectbox(
            "Mode",
            modes,
            key=mode_key,
            help="Changing mode only refreshes this filter box. Selecting values refreshes the report.",
        )
        mode = st.session_state.get(mode_key, "Include All")
        if mode in ["Include Selected", "Exclude Selected"]:
            st.session_state[values_key] = _match_filter_values_to_options(st.session_state.get(values_key, []), opts)
            st.multiselect(
                "Values",
                options=opts,
                key=values_key,
                placeholder="Choose values",
            )
        else:
            st.caption("No value selection needed for this mode.")

    new_info = _filter_info_from_widget_state(col, opts)
    if _filter_record_signature(old_info) != _filter_record_signature(new_info):
        _persist_one_filter(col, new_info)
        if _should_rerun_report_for_filter_change(old_info, new_info):
            _safe_app_rerun()

def render_filter_sidebar(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, str]:
    st.sidebar.markdown("### Production Filters")
    if "prod_committed_filters" not in st.session_state:
        st.session_state["prod_committed_filters"] = default_filter_state(df)
    if "prod_display_unit" not in st.session_state:
        st.session_state["prod_display_unit"] = "in IDR Mio"

    render_proxy_manager(df)

    # Display unit affects all money values, so this one legitimately refreshes the report.
    st.sidebar.selectbox("Display unit", DISPLAY_UNIT_OPTIONS, key="prod_display_unit")
    display_unit = st.session_state.get("prod_display_unit", "in IDR Mio")

    filter_cols = [c for c in BASE_FILTER_COLS if c in df.columns]
    _sync_filter_widget_defaults(df, filter_cols)
    modes = ["Include All", "Include Selected", "Exclude Selected", "Exclude All"]

    # Cached option lists: computed once per data snapshot/filter columns, then
    # reused by the per-filter fragments. Do not pass the full dataframe into
    # each fragment.
    filter_options_map = cached_filter_options_map(df, tuple(filter_cols))

    # Each filter expander is isolated and is CALLED from inside the sidebar root.
    # Important: the fragment itself must use st.expander(), not st.sidebar.expander(),
    # otherwise Streamlit raises FragmentWidgetsNotAllowedOutsideError.
    with st.sidebar:
        for col in filter_cols:
            _render_one_filter_expander(col, filter_options_map.get(col, []), modes)

    st.sidebar.button(
        "Reset Filters",
        key="prod_reset_filters_btn",
        width="stretch",
        on_click=lambda: (_reset_production_sidebar_filters(filter_cols, df), _safe_app_rerun()),
    )

    active_filters = st.session_state.get("prod_committed_filters", {}) or {}
    filtered = apply_filters(df, active_filters)
    st.sidebar.caption(f"Rows: {len(filtered):,} / {len(df):,}")
    return filtered, active_filters, display_unit

# ==========================================================
# Rendering components
# ==========================================================
def render_kpis(kpis: dict, unit: str) -> None:
    cards = [
        (f"Total GWP ({DISPLAY_UNIT_SHORT[unit]})", fmt_money(kpis["GWP"], unit), "Selected production"),
        ("Jumlah Risiko", fmt_num(kpis["NUMBER_OF_RISKS"]), "Unique policy number"),
        (f"Avg Premium ({DISPLAY_UNIT_SHORT[unit]})", fmt_money(kpis["AVG_PREMIUM"], unit), "GWP / risk"),
        ("Commission Ratio", fmt_pct(kpis["COMM_RATIO"]), "COMM / GWP"),
        ("RI Ratio", fmt_pct(kpis["RI_RATIO"]), "RI Premium / GWP"),
        (f"Net Premium ({DISPLAY_UNIT_SHORT[unit]})", fmt_money(kpis["NET_PREMIUM"], unit), "GWP - RI Premium"),
    ]
    cols = st.columns(6)
    for col, (title, value, foot) in zip(cols, cards):
        with col:
            st.markdown(f"<div class='kpi-card-prod'><h4>{html.escape(title)}</h4><h2>{html.escape(value)}</h2><div class='foot'>{html.escape(foot)}</div></div>", unsafe_allow_html=True)


def render_plain_prod_table(df: pd.DataFrame, table_key: str = "plain") -> None:
    """Static clean table matching the first Production table visual."""
    if df is None or df.empty:
        st.info("No data on this filter.")
        return
    show = df.copy()
    headers = "".join(f"<th>{html.escape(str(c).replace('_', ' '))}</th>" for c in show.columns)
    rows = []
    for _, row in show.iterrows():
        cells = []
        for col in show.columns:
            val = "" if pd.isna(row[col]) else str(row[col])
            # formatted YoY values are strings already; use right alignment for number-like columns
            num_like = str(col).isdigit() or str(col).endswith("Change") or str(col).endswith("%") or str(col).upper() in {"GWP", "JUMLAH RISIKO"}
            cls = "num-cell" if num_like else "text-cell"
            cells.append(f"<td class='{cls}'>{html.escape(val)}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    table_html = f"""
    <div class='prod-table-wrap'>
      <table class='prod-table'>
        <thead><tr>{headers}</tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)


def render_html_table(df: pd.DataFrame, unit: str, table_key: str = "prod", page_rows: int = 200, format_overrides: dict | None = None) -> None:
    """Clean production table with client-side sort and frozen basis columns.

    Basis/group columns (non-numeric/non-metric columns) are frozen on the left so
    users can scroll horizontally across YoY metric columns without losing context.
    """
    if df is None or df.empty:
        st.info("No data on this filter.")
        return

    raw = df.copy()[final_metric_order(df)]
    disp = raw.copy()
    format_overrides = format_overrides or {}

    money_cols = [c for c in ["GWP", "AVG_PREMIUM", "COMM_IDR", "RI Premium", "NET_PREMIUM", "Klaim Bruto", "CLAIM_PAID", "OS", "RI Claim"] if c in disp.columns]
    count_cols = [c for c in ["NUMBER_OF_RISKS"] if c in disp.columns]
    pct_cols = [c for c in ["COMM_RATIO", "RI_RATIO", "CLAIM_RATIO_TO_GWP"] if c in disp.columns]

    for c, kind in format_overrides.items():
        if c not in disp.columns:
            continue
        if kind == "money" and c not in money_cols:
            money_cols.append(c)
        elif kind == "count" and c not in count_cols:
            count_cols.append(c)
        elif kind == "pct" and c not in pct_cols:
            pct_cols.append(c)
        elif kind == "number" and c not in count_cols:
            count_cols.append(c)

    metric_cols = money_cols + count_cols + pct_cols
    basis_cols = [c for c in disp.columns if c not in metric_cols]

    for c in disp.columns:
        if c in money_cols:
            disp[c] = disp[c].apply(lambda x: fmt_money(x, unit))
        elif c in count_cols:
            disp[c] = disp[c].apply(fmt_num)
        elif c in pct_cols:
            disp[c] = disp[c].apply(fmt_pct)
        else:
            disp[c] = disp[c].astype("object").where(disp[c].notna(), "").astype(str)

    alias = {
        "ACCT_YEAR": "ACCT YEAR", "ACCT_MONTH": "ACCT MONTH", "UW_YEAR": "UW YEAR",
        "COB_CODE": "COB", "TOB_CODE": "TOB", "SOB_CODE": "SOB", "LOB_CODE": "LOB",
        "INTERMEDIARY_GROUPED": "INTERMEDIARY", "INTERMEDIARY_NAME": "ORIGINAL INTERMEDIARY",
        "NUMBER_OF_RISKS": "JUMLAH RISIKO", "AVG_PREMIUM": "AVG PREMIUM",
        "COMM_IDR": "COMM", "COMM_RATIO": "COMM RATIO", "RI Premium": "RI PREMIUM",
        "RI_RATIO": "RI RATIO", "NET_PREMIUM": "NET PREMIUM", "Klaim Bruto": "GROSS CLAIM",
        "CLAIM_PAID": "PAID CLAIM", "RI Claim": "RI CLAIM", "CLAIM_RATIO_TO_GWP": "CLAIM / GWP",
        "IS NEW": "IS NEW",
    }

    widths = {}
    for c in disp.columns:
        if c in metric_cols:
            widths[c] = 142 if "YoY" in str(c) else 132
        elif c in ["ACCT_YEAR", "ACCT_MONTH", "UW_YEAR", "COB_CODE", "TOB_CODE", "SOB_CODE", "LOB_CODE", "IS_FRONTING", "IS NEW"]:
            widths[c] = 115
        elif c in ["INTERMEDIARY_GROUPED", "INTERMEDIARY_NAME", "INSURED_NAME"]:
            widths[c] = 240
        else:
            widths[c] = 170
    min_w = max(980, sum(widths.values()))
    height = max(250, min(520, 96 + 34 * len(disp)))
    dom = "prod_table_" + hashlib.sha1((table_key + str(len(disp)) + "|".join(map(str, disp.columns))).encode()).hexdigest()[:10]

    # Freeze every basis column on the left. Limit to a sensible count so very wide
    # ad-hoc groupings remain usable.
    sticky_left = {}
    running_left = 0
    max_sticky_cols = min(len(basis_cols), 6)
    for c in disp.columns[:max_sticky_cols]:
        if c in basis_cols:
            sticky_left[c] = running_left
            running_left += widths[c]
        else:
            break

    opts = "<option value=''>None</option>" + "".join(
        [f"<option value='{i}'>{html.escape(alias.get(c, str(c).replace('_',' ')))}</option>" for i, c in enumerate(disp.columns)]
    )
    colgroup = "".join([f"<col style='width:{widths[c]}px;min-width:{widths[c]}px;'>" for c in disp.columns])

    header_cells = []
    for c in disp.columns:
        classes = []
        style = ""
        if c in sticky_left:
            classes.append("sticky-col")
            style = f"left:{sticky_left[c]}px;"
        class_attr = f" class='{' '.join(classes)}'" if classes else ""
        style_attr = f" style='{style}'" if style else ""
        header_cells.append(f"<th{class_attr}{style_attr}>{html.escape(alias.get(c, str(c).replace('_',' ')))}</th>")
    headers = "".join(header_cells)

    rows = []
    for r in range(len(disp)):
        tds = []
        for c in disp.columns:
            val = html.escape(str(disp.iloc[r][c]))
            raw_val = raw.iloc[r][c]
            num = pd.to_numeric(pd.Series([raw_val]), errors="coerce").iloc[0]
            sort_type = "num" if pd.notna(num) else "text"
            sort_val = str(float(num)) if pd.notna(num) else html.escape(str(raw_val if pd.notna(raw_val) else "").lower())
            cls = "num-cell" if c in metric_cols else "text-cell"
            style = ""
            if c in sticky_left:
                cls += " sticky-col"
                style = f"left:{sticky_left[c]}px;"
            col_text = str(c).lower()
            if ("yoy change" in col_text or "yoy %" in col_text or "growth" in col_text) and pd.notna(num):
                if float(num) > 0:
                    cls += " pos-cell"
                elif float(num) < 0:
                    cls += " neg-cell"
            style_attr = f" style='{style}'" if style else ""
            tds.append(f"<td class='{cls}'{style_attr} data-sort='{sort_val}' data-sort-type='{sort_type}'>{val}</td>")
        rows.append("<tr>" + "".join(tds) + "</tr>")

    html_table = f"""
    <style>
      html, body {{ margin:0; padding:0; background:transparent; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Arial,sans-serif; }}
      .prod-table-controls {{ display:flex; gap:10px; align-items:center; margin:0 0 8px 0; padding:0; }}
      .prod-table-controls label {{ font-size:11.5px; font-weight:750; color:#475569; }}
      .prod-table-controls select, .prod-table-controls button {{
        height:32px; border:1px solid rgba(0,51,102,0.16); border-radius:10px;
        background:#FFFFFF; color:#1F2937; font-size:11.5px; padding:0 10px; outline:none;
      }}
      .prod-table-controls button {{ cursor:pointer; font-weight:800; color:#003366; }}
      .prod-table-controls select:focus {{ border-color:rgba(0,51,102,0.42); box-shadow:0 0 0 3px rgba(0,51,102,0.08); }}
      .prod-table-wrap{{ width:100%; max-height:{height}px; overflow:auto; border:1px solid rgba(0,51,102,0.12); border-radius:16px; background:#FFFFFF; box-shadow:0 10px 28px rgba(15,23,42,0.055); }}
      .prod-table{{ border-collapse:separate; border-spacing:0; width:100%; min-width:{min_w}px; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
      .prod-table th{{ position:sticky; top:0; z-index:3; background:#003366; color:white; font-size:11px; font-weight:850; text-align:center; padding:10px 10px; border-right:1px solid rgba(255,255,255,0.18); white-space:nowrap; }}
      .prod-table td{{ font-size:11.5px; color:#334155; padding:8px 10px; border-bottom:1px solid rgba(15,23,42,0.055); border-right:1px solid rgba(15,23,42,0.045); font-weight:620; white-space:nowrap; background:#FFFFFF; }}
      .prod-table tr:nth-child(even) td{{ background:#F8FAFC; }}
      .prod-table tr:hover td{{ background:#EEF6FF; }}
      .num-cell{{ text-align:right; font-variant-numeric:tabular-nums; }}
      .text-cell{{ text-align:left; color:#1E3A5F !important; font-weight:750 !important; }}
      .sticky-col{{ position:sticky !important; z-index:2; box-shadow:2px 0 0 rgba(0,51,102,0.08); }}
      th.sticky-col{{ z-index:5 !important; background:#002B57 !important; }}
      td.sticky-col{{ background:#FFFFFF !important; }}
      tr:nth-child(even) td.sticky-col{{ background:#F8FAFC !important; }}
      tr:hover td.sticky-col{{ background:#EEF6FF !important; }}
      .pos-cell{{ color:#047857 !important; font-weight:850 !important; background:#ECFDF5 !important; }}
      .neg-cell{{ color:#BE123C !important; font-weight:850 !important; background:#FFF1F2 !important; }}
      td.sticky-col.pos-cell{{ background:#ECFDF5 !important; }}
      td.sticky-col.neg-cell{{ background:#FFF1F2 !important; }}
    </style>
    <div class='prod-table-controls'>
      <label for='sort_by_{dom}'>Sort by</label>
      <select id='sort_by_{dom}'>{opts}</select>
      <select id='sort_order_{dom}'><option value='desc'>Descending</option><option value='asc'>Ascending</option></select>
      <button id='reset_sort_{dom}' type='button'>Reset</button>
    </div>
    <div class='prod-table-wrap'>
      <table class='prod-table' id='{dom}'>
        <colgroup>{colgroup}</colgroup>
        <thead><tr>{headers}</tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    <script>
      (function(){{
        const table=document.getElementById('{dom}');
        const sortBy=document.getElementById('sort_by_{dom}');
        const sortOrder=document.getElementById('sort_order_{dom}');
        const resetBtn=document.getElementById('reset_sort_{dom}');
        if(!table || !sortBy || !sortOrder || !resetBtn) return;
        const tbody=table.querySelector('tbody');
        const originalRows=Array.from(tbody.querySelectorAll('tr'));
        function applySort(){{
          const colIndex=sortBy.value;
          if(colIndex===''){{ tbody.replaceChildren(...originalRows); return; }}
          const idx=parseInt(colIndex,10); const asc=sortOrder.value==='asc';
          const rows=Array.from(tbody.querySelectorAll('tr'));
          rows.sort(function(a,b){{
            const acell=a.children[idx]; const bcell=b.children[idx];
            const atype=acell.getAttribute('data-sort-type'); const btype=bcell.getAttribute('data-sort-type');
            let av=acell.getAttribute('data-sort')||''; let bv=bcell.getAttribute('data-sort')||'';
            let result=0;
            if(atype==='num' && btype==='num'){{ result=(parseFloat(av)||0)-(parseFloat(bv)||0); }}
            else{{ result=av.localeCompare(bv,undefined,{{numeric:true,sensitivity:'base'}}); }}
            return asc ? result : -result;
          }});
          tbody.replaceChildren(...rows);
        }}
        sortBy.addEventListener('change',applySort);
        sortOrder.addEventListener('change',applySort);
        resetBtn.addEventListener('click',function(){{ sortBy.value=''; sortOrder.value='desc'; tbody.replaceChildren(...originalRows); }});
      }})();
    </script>
    """
    components.iframe("data:text/html;charset=utf-8;base64," + base64.b64encode(html_table.encode("utf-8")).decode(), height=height + 50, scrolling=False)

def bar_chart(df: pd.DataFrame, x: str, y: str, title: str, unit: str, top_n=12):
    if df.empty or x not in df.columns or y not in df.columns:
        st.info("No data.")
        return
    plot = df[[x, y]].copy().sort_values(y, ascending=False).head(top_n)
    plot["DISPLAY"] = plot[y] / DISPLAY_UNIT_FACTOR.get(unit, 1)
    plot["LABEL"] = plot["DISPLAY"].map(lambda v: f"{v:,.0f}".replace(",", "."))
    chart = alt.Chart(plot).mark_bar(cornerRadiusEnd=6).encode(
        y=alt.Y(f"{x}:N", sort="-x", title=None, axis=alt.Axis(labelLimit=190)),
        x=alt.X("DISPLAY:Q", title=None, axis=alt.Axis(labels=False, ticks=False, grid=False)),
        tooltip=[alt.Tooltip(f"{x}:N"), alt.Tooltip("DISPLAY:Q", title=f"{y} ({DISPLAY_UNIT_SHORT[unit]})", format=",.0f")],
    ).properties(
        height=max(260, 26 * len(plot)),
        title=alt.TitleParams(text=title, anchor="middle", color=THEME_BLUE, fontWeight="bold"),
    )
    labels = alt.Chart(plot).mark_text(align="left", dx=5, fontSize=11, color="#1E293B", fontWeight="bold").encode(
        y=alt.Y(f"{x}:N", sort="-x"),
        x="DISPLAY:Q",
        text="LABEL:N",
    )
    layered = (chart + labels).configure_view(strokeWidth=0)
    st.altair_chart(layered, width="stretch")


def render_overview(df: pd.DataFrame, unit: str) -> None:
    section_header("Production Overview")
    render_kpis(compute_kpis(df), unit)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        summary = grouped_summary(df, ("INTERMEDIARY_GROUPED",))
        bar_chart(summary, "INTERMEDIARY_GROUPED", "GWP", "Top Intermediary by GWP", unit)
    with c2:
        summary = grouped_summary(df, ("COB_CODE",))
        bar_chart(summary, "COB_CODE", "GWP", "GWP by COB", unit)




def _normalize_year_key(value) -> str:
    """Normalize pivoted year columns so 2026, 2026.0, and '2026' match."""
    try:
        if value is None:
            return ""
        if isinstance(value, str):
            txt = value.strip()
            if txt.endswith('.0'):
                txt = txt[:-2]
            try:
                f = float(txt.replace(',', ''))
                if f.is_integer():
                    return str(int(f))
            except Exception:
                return txt
            return txt
        f = float(value)
        if f.is_integer():
            return str(int(f))
        return str(value)
    except Exception:
        return str(value).strip()


def _ensure_yoy_year_columns(pivot_df: pd.DataFrame, years) -> dict:
    """Return actual pivot column keys for requested years, creating zero columns when absent."""
    year_map = {}
    existing = {_normalize_year_key(c): c for c in pivot_df.columns}
    for y in years:
        key = _normalize_year_key(y)
        actual = existing.get(key)
        if actual is None:
            actual = f"__YEAR_{key}__"
            pivot_df[actual] = 0.0
        year_map[int(float(y)) if str(y).replace('.', '', 1).isdigit() else y] = actual
    return year_map


def _fragment_yoy_if_available(func):
    """Keep YoY controls local. Widget changes inside YoY rerun only this section when Streamlit supports fragments."""
    return st.fragment(func) if hasattr(st, "fragment") else func


def render_yoy_top10_visual(top10_df: pd.DataFrame, label_col: str, value_col: str, current_year: int, unit: str) -> None:
    """Render Top 10 YoY visual with Altair so it appears reliably in Streamlit."""
    if top10_df is None or top10_df.empty or label_col not in top10_df.columns or value_col not in top10_df.columns:
        st.info("Top 10 YoY visual unavailable.")
        return

    plot = top10_df[[label_col, value_col]].copy()
    plot[value_col] = pd.to_numeric(plot[value_col], errors="coerce").fillna(0.0)
    plot[label_col] = plot[label_col].fillna("(Blank)").astype(str)
    plot = plot.sort_values(value_col, ascending=False, kind="stable").head(10).reset_index(drop=True)
    if plot.empty or float(plot[value_col].sum()) <= 0:
        st.info("Top 10 YoY visual unavailable because current-year GWP is zero.")
        return

    factor = DISPLAY_UNIT_FACTOR.get(unit, 1_000_000)
    unit_short = DISPLAY_UNIT_SHORT.get(unit, "Mio")
    plot["DISPLAY"] = plot[value_col] / factor
    plot["LABEL"] = plot["DISPLAY"].map(lambda v: f"{v:,.0f}".replace(",", "."))
    plot["ORDER"] = np.arange(len(plot), 0, -1)

    base = alt.Chart(plot).encode(
        y=alt.Y(
            f"{label_col}:N",
            sort=alt.EncodingSortField(field="DISPLAY", order="descending"),
            title=None,
            axis=alt.Axis(labelLimit=260, labelFontSize=11, labelColor="#334155"),
        ),
        x=alt.X(
            "DISPLAY:Q",
            title=None,
            axis=alt.Axis(labels=False, ticks=False, grid=False, domain=False),
        ),
        tooltip=[
            alt.Tooltip(f"{label_col}:N", title=label_col),
            alt.Tooltip("DISPLAY:Q", title=f"GWP {current_year} ({unit_short})", format=",.1f"),
        ],
    )
    bars = base.mark_bar(cornerRadiusTopRight=7, cornerRadiusBottomRight=7, color=THEME_BLUE)
    labels = base.mark_text(align="left", dx=6, fontSize=11, fontWeight="bold", color="#1E293B").encode(text="LABEL:N")
    chart = (bars + labels).properties(
        height=max(280, 30 * len(plot)),
        title=alt.TitleParams(
            text=f"Top 10 by GWP {current_year}",
            subtitle=f"Visual remains based on primary compare dimension only - values in {unit_short}",
            anchor="middle",
            color=THEME_BLUE,
            fontWeight="bold",
            fontSize=15,
            subtitleFontSize=11,
            subtitleColor="#64748B",
        ),
    ).configure_view(strokeWidth=0)
    st.altair_chart(chart, width="stretch")

def _safe_yoy_pct(prev_vals, cur_vals):
    """Vectorized YoY percentage without divide-by-zero warnings."""
    prev_arr = pd.to_numeric(pd.Series(prev_vals), errors="coerce").fillna(0.0).to_numpy(dtype="float64")
    cur_arr = pd.to_numeric(pd.Series(cur_vals), errors="coerce").fillna(0.0).to_numpy(dtype="float64")
    out = np.full(len(prev_arr), np.nan, dtype="float64")
    mask = np.abs(prev_arr) > 1e-12
    out[mask] = (cur_arr[mask] - prev_arr[mask]) / prev_arr[mask] * 100.0
    return out


def _normalize_is_new_label(value) -> str:
    text = str(value if value is not None else "").strip()
    low = text.lower().replace("_", " ").replace("-", " ")

    # Important: check Renewal first because "renewal" contains the substring
    # "new". If New is checked first, every Renewal row is incorrectly mapped
    # to New and the split YoY table looks as if Renewal disappeared.
    if low in ("0", "0.0", "false", "no", "renewal", "renew", "r") or "renew" in low:
        return "Renewal"
    if low in ("1", "1.0", "true", "yes", "y", "new", "new business", "n/b", "nb") or "new business" in low or low == "new":
        return "New"
    return text or "(Blank)"


def _ordered_split_labels(labels) -> list[str]:
    """Return split labels in a friendly order.

    For the New/Renewal YoY view we always show both New and Renewal columns,
    even if one side is zero for the current filter. This prevents the table
    from looking as if only New exists.
    """
    labels = [str(x) for x in labels if str(x).strip()]
    normalized = []
    for x in labels:
        nx = _normalize_is_new_label(x)
        if nx and nx not in normalized:
            normalized.append(nx)
    preferred = [x for x in ["New", "Renewal"] if x not in normalized or x in normalized]
    others = sorted([x for x in normalized if x not in preferred], key=lambda x: x.lower())
    return preferred + others


def _metric_format_kind(metric: str) -> str:
    if metric == "NUMBER_OF_RISKS":
        return "count"
    if metric in ["COMM_RATIO", "RI_RATIO", "CLAIM_RATIO_TO_GWP"]:
        return "pct"
    return "money"


def _empty_yoy_metric_table(base_keys: pd.DataFrame, merge_keys: list[str], prev_col: str, cur_col: str, change_col: str, pct_col: str) -> pd.DataFrame:
    out = base_keys.copy()
    out[prev_col] = 0.0
    out[cur_col] = 0.0
    out[change_col] = 0.0
    out[pct_col] = np.nan
    return out[merge_keys + [prev_col, cur_col, change_col, pct_col]]


def _as_1d_series(frame: pd.DataFrame, col: str, default=np.nan) -> pd.Series:
    """Return a single Series even when a dataframe temporarily has duplicate column labels.

    Pandas returns a DataFrame instead of a Series when duplicate column names
    exist. YoY tables can hit that path after repeated merges, causing
    pd.to_numeric(...) to fail with "arg must be 1-d". Keep the rightmost
    duplicate because it is the newest merge result.
    """
    if frame is None or col not in frame.columns:
        return pd.Series(default, index=frame.index if frame is not None else None)
    value = frame.loc[:, col]
    if isinstance(value, pd.DataFrame):
        value = value.iloc[:, -1]
    return value


def _build_yoy_combined_table(
    selected_df: pd.DataFrame,
    group_cols: list[str],
    year_col: str,
    previous: int,
    current: int,
    metric_build_list: list[tuple[str, str]],
    split_col: str | None = None,
) -> tuple[pd.DataFrame, dict, int]:
    """Build one YoY table.

    Normal mode:
      Dimension | GWP 2025 | GWP 2026 | GWP YoY Change | GWP YoY %

    New/Renewal mode:
      Dimension | GWP 2025 - New | GWP 2025 - Renewal | GWP 2026 - New | ...

    The split columns are interleaved by year/change so New and Renewal are
    visible next to each other instead of Renewal being pushed far to the right.
    """
    fmt_map: dict[str, str] = {}
    group_cols = [c for c in list(group_cols or []) if c in selected_df.columns]
    if not group_cols or year_col not in selected_df.columns:
        return pd.DataFrame(), fmt_map, 0

    use_split = bool(split_col and split_col in selected_df.columns)
    work_group_cols = list(group_cols) + ([split_col] if use_split else []) + [year_col]
    group_table = grouped_summary(selected_df, tuple(work_group_cols))
    if group_table.empty:
        return pd.DataFrame(), fmt_map, 0

    merge_keys = list(group_cols)
    base_keys = group_table[merge_keys].drop_duplicates().reset_index(drop=True)

    if use_split:
        group_table = group_table.copy()
        group_table["__SPLIT_LABEL__"] = group_table[split_col].apply(_normalize_is_new_label)
        split_labels = _ordered_split_labels(group_table["__SPLIT_LABEL__"].dropna().unique().tolist())
    else:
        split_labels = [None]

    combined = base_keys.copy()
    final_metric_cols: list[str] = []

    for metric_label, metric in metric_build_list:
        if metric not in group_table.columns:
            continue

        metric_piece = base_keys.copy()
        prev_cols: list[str] = []
        cur_cols: list[str] = []
        change_cols: list[str] = []
        pct_cols: list[str] = []

        for split_label in split_labels:
            if use_split:
                source = group_table[group_table["__SPLIT_LABEL__"] == split_label]
                suffix = f" - {split_label}"
            else:
                source = group_table
                suffix = ""

            prev_col = f"{metric_label} {previous}{suffix}"
            cur_col = f"{metric_label} {current}{suffix}"
            change_col = f"{metric_label} YoY Change{suffix}"
            pct_col = f"{metric_label} YoY %{suffix}"

            if source.empty:
                metric_table = _empty_yoy_metric_table(base_keys, merge_keys, prev_col, cur_col, change_col, pct_col)
            else:
                pivot = source.pivot_table(
                    index=merge_keys,
                    columns=year_col,
                    values=metric,
                    aggfunc="sum",
                    fill_value=0,
                    observed=True,
                ).reset_index()
                year_cols = _ensure_yoy_year_columns(pivot, [previous, current])
                prev_key = year_cols[previous]
                cur_key = year_cols[current]
                pivot[prev_key] = pd.to_numeric(_as_1d_series(pivot, prev_key, 0.0), errors="coerce").fillna(0.0)
                pivot[cur_key] = pd.to_numeric(_as_1d_series(pivot, cur_key, 0.0), errors="coerce").fillna(0.0)
                pivot[change_col] = _as_1d_series(pivot, cur_key, 0.0) - _as_1d_series(pivot, prev_key, 0.0)
                pivot[pct_col] = _safe_yoy_pct(_as_1d_series(pivot, prev_key, 0.0), _as_1d_series(pivot, cur_key, 0.0))
                metric_table = pivot[merge_keys + [prev_key, cur_key, change_col, pct_col]].rename(columns={
                    prev_key: prev_col,
                    cur_key: cur_col,
                })

            metric_piece = metric_piece.merge(metric_table, on=merge_keys, how="left")
            if metric_piece.columns.duplicated().any():
                metric_piece = metric_piece.loc[:, ~metric_piece.columns.duplicated(keep="last")].copy()
            for col in [prev_col, cur_col, change_col]:
                metric_piece[col] = pd.to_numeric(_as_1d_series(metric_piece, col, 0.0), errors="coerce").fillna(0.0)
            metric_piece[pct_col] = pd.to_numeric(_as_1d_series(metric_piece, pct_col, np.nan), errors="coerce")

            kind = _metric_format_kind(metric)
            fmt_map.update({prev_col: kind, cur_col: kind, change_col: kind, pct_col: "pct"})
            prev_cols.append(prev_col)
            cur_cols.append(cur_col)
            change_cols.append(change_col)
            pct_cols.append(pct_col)

        # User-friendly order: all previous-year New/Renewal side-by-side,
        # then current-year New/Renewal, then movement, then percentage.
        ordered_cols = list(dict.fromkeys(prev_cols + cur_cols + change_cols + pct_cols))
        final_metric_cols.extend(ordered_cols)
        metric_piece_for_merge = metric_piece.loc[:, ~metric_piece.columns.duplicated(keep="last")].copy()
        combined = combined.merge(metric_piece_for_merge[merge_keys + ordered_cols], on=merge_keys, how="left")
        if combined.columns.duplicated().any():
            combined = combined.loc[:, ~combined.columns.duplicated(keep="last")].copy()

    if combined.empty or not final_metric_cols:
        return pd.DataFrame(), fmt_map, 0

    # Sort and filter by total GWP across New/Renewal, not by split columns.
    excluded = 0
    if "GWP" in group_table.columns:
        sort_base = grouped_summary(selected_df, tuple(merge_keys + [year_col]))
        if not sort_base.empty and "GWP" in sort_base.columns:
            sort_pivot = sort_base.pivot_table(index=merge_keys, columns=year_col, values="GWP", aggfunc="sum", fill_value=0, observed=True).reset_index()
            year_cols = _ensure_yoy_year_columns(sort_pivot, [previous, current])
            prev_key = year_cols[previous]
            cur_key = year_cols[current]
            sort_helper = sort_pivot[merge_keys + [prev_key, cur_key]].rename(columns={
                prev_key: "__FILTER_GWP_PREVIOUS__",
                cur_key: "__SORT_GWP_CURRENT__",
            })
            sort_helper["__FILTER_GWP_PREVIOUS__"] = pd.to_numeric(_as_1d_series(sort_helper, "__FILTER_GWP_PREVIOUS__", 0.0), errors="coerce").fillna(0.0)
            sort_helper["__SORT_GWP_CURRENT__"] = pd.to_numeric(_as_1d_series(sort_helper, "__SORT_GWP_CURRENT__", 0.0), errors="coerce").fillna(0.0)
            combined = combined.merge(sort_helper.drop_duplicates(subset=merge_keys), on=merge_keys, how="left")
            combined["__FILTER_GWP_PREVIOUS__"] = pd.to_numeric(combined["__FILTER_GWP_PREVIOUS__"], errors="coerce").fillna(0.0)
            combined["__SORT_GWP_CURRENT__"] = pd.to_numeric(combined["__SORT_GWP_CURRENT__"], errors="coerce").fillna(0.0)
            before = len(combined)
            combined = combined[(combined["__FILTER_GWP_PREVIOUS__"].abs() + combined["__SORT_GWP_CURRENT__"].abs()) > 1e-9].copy()
            excluded = before - len(combined)
            combined = combined.sort_values("__SORT_GWP_CURRENT__", ascending=False, kind="stable").drop(columns=["__FILTER_GWP_PREVIOUS__", "__SORT_GWP_CURRENT__"])
    else:
        first_metric_label = metric_build_list[0][0]
        fallback_col = f"{first_metric_label} {current}"
        if fallback_col in combined.columns:
            combined[fallback_col] = pd.to_numeric(combined[fallback_col], errors="coerce").fillna(0)
            combined = combined.sort_values(fallback_col, ascending=False, kind="stable")

    return combined.reset_index(drop=True), fmt_map, excluded


def _apply_growth_conditional_formats(ws, wb, df: pd.DataFrame, startrow: int, kinds: dict[str, str]) -> None:
    """Color YoY/growth cells in Excel: green for positive, red for negative."""
    if df is None or df.empty:
        return
    green_fmt = wb.add_format({"font_color": "#047857", "bold": True})
    red_fmt = wb.add_format({"font_color": "#BE123C", "bold": True})
    first_data_row = startrow + 1
    last_data_row = startrow + len(df)
    if last_data_row < first_data_row:
        return
    for idx, col in enumerate(df.columns):
        low = str(col).lower()
        if "yoy change" in low or "yoy %" in low or "growth" in low:
            ws.conditional_format(first_data_row, idx, last_data_row, idx, {"type": "cell", "criteria": ">", "value": 0, "format": green_fmt})
            ws.conditional_format(first_data_row, idx, last_data_row, idx, {"type": "cell", "criteria": "<", "value": 0, "format": red_fmt})


def _freeze_excel_basis_columns(ws, df: pd.DataFrame, startrow: int, kinds: dict[str, str]) -> None:
    freeze_cols = 0
    for c in df.columns:
        if kinds.get(c) in ["money", "count", "pct", "number"]:
            break
        freeze_cols += 1
    ws.freeze_panes(startrow + 1, min(freeze_cols, 6))


def build_yoy_excel_bytes(
    overall_df: pd.DataFrame,
    split_df: pd.DataFrame | None,
    previous: int,
    current: int,
    as_of_text: str,
    unit: str,
    filters: dict,
    extra_lines: list[str] | None = None,
) -> bytes:
    """Export YoY as two sheets: Overall and separated by IS NEW."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        wb = writer.book
        title_fmt = wb.add_format({"bold": True, "font_color": THEME_BLUE, "font_size": 12})
        header_fmt = wb.add_format({"bold": True, "bg_color": THEME_BLUE, "font_color": "white"})
        money_fmt = wb.add_format({"num_format": "#,##0"})
        count_fmt = wb.add_format({"num_format": "#,##0"})
        number_fmt = wb.add_format({"num_format": "#,##0.00"})
        pct_fmt = wb.add_format({"num_format": "0.0%"})
        text_fmt = wb.add_format({})

        def write_sheet(df_sheet: pd.DataFrame, sheet_name: str, sheet_note: str):
            out, kinds = _prepare_excel_df(df_sheet.copy())
            ws_name = sheet_name[:31]
            ws = wb.add_worksheet(ws_name)
            writer.sheets[ws_name] = ws
            ws.write(0, 0, "Super Production YoY Export", title_fmt)
            lines = list(extra_lines or []) + [sheet_note]
            startrow = _write_export_filter_block(ws, 1, as_of_text=as_of_text, unit=unit, filters=filters or {}, extra_lines=lines) + 1
            out.to_excel(writer, index=False, startrow=startrow, sheet_name=ws_name)
            ws = writer.sheets[ws_name]
            for i, c in enumerate(out.columns):
                ws.write(startrow, i, c, header_fmt)
                kind = kinds.get(c, "text")
                width = max(14, min(40, len(str(c)) + 4))
                if kind == "money":
                    ws.set_column(i, i, max(16, width), money_fmt)
                elif kind == "count":
                    ws.set_column(i, i, max(14, width), count_fmt)
                elif kind == "pct":
                    ws.set_column(i, i, max(13, width), pct_fmt)
                elif kind == "number":
                    ws.set_column(i, i, max(14, width), number_fmt)
                else:
                    ws.set_column(i, i, width, text_fmt)
            if len(out.columns) > 0:
                ws.autofilter(startrow, 0, startrow + len(out), len(out.columns) - 1)
                _freeze_excel_basis_columns(ws, out, startrow, kinds)
                _apply_growth_conditional_formats(ws, wb, out, startrow, kinds)

        write_sheet(overall_df, "YoY Overall", "Sheet: Overall YoY movement")
        if split_df is not None and not split_df.empty:
            write_sheet(split_df, "YoY by IS NEW", "Sheet: YoY movement separated by IS NEW / New-Renewal")
        else:
            write_sheet(pd.DataFrame({"Note": ["IS NEW column is not available or has no data for this selection."]}), "YoY by IS NEW", "Sheet: YoY movement separated by IS NEW / New-Renewal")
    return buffer.getvalue()


@_fragment_yoy_if_available
def render_yoy(df: pd.DataFrame, unit: str) -> None:
    section_header("Year on Year Comparison")

    valid_yoy_metrics = list(YOY_METRICS.keys())
    default_yoy_metrics = ["GWP"]
    if "prod_yoy_metrics" not in st.session_state:
        st.session_state["prod_yoy_metrics"] = default_yoy_metrics
    else:
        st.session_state["prod_yoy_metrics"] = [m for m in st.session_state.get("prod_yoy_metrics", []) if m in valid_yoy_metrics] or default_yoy_metrics

    c1, c2, c3 = st.columns([1.15, 1.15, 2.7])
    year_options = [c for c in ["ACCT_YEAR", "UW_YEAR"] if c in df.columns]
    if not year_options:
        st.info("Year column is not available.")
        return
    year_col = c1.selectbox("Year basis", year_options, key="prod_yoy_year_col")

    dim_options = [label for label, col in DETAIL_OPTIONS.items() if col in df.columns and col != year_col]
    if not dim_options:
        st.info("No comparison dimension is available.")
        return
    if "prod_yoy_dimension" not in st.session_state or st.session_state.get("prod_yoy_dimension") not in dim_options:
        st.session_state["prod_yoy_dimension"] = "Intermediary" if "Intermediary" in dim_options else dim_options[0]
    dimension_label = c2.selectbox("Compare by", dim_options, key="prod_yoy_dimension")
    metrics = c3.multiselect("Metrics to compare", options=valid_yoy_metrics, key="prod_yoy_metrics") or default_yoy_metrics

    split_available = "IS NEW" in df.columns
    split_newrenewal = st.checkbox(
        "Pisahkan New dan Renewal",
        key="prod_yoy_split_is_new",
        value=False if "prod_yoy_split_is_new" not in st.session_state else st.session_state.get("prod_yoy_split_is_new", False),
        disabled=not split_available,
        help="Jika aktif, tabel YoY memecah kolom metric menjadi New dan Renewal berdasarkan kolom IS NEW. Visual tetap berdasarkan total GWP.",
    )
    if not split_available:
        st.caption("Kolom IS NEW tidak tersedia, jadi split New/Renewal tidak bisa digunakan.")

    extra_options = [label for label in dim_options if label != dimension_label]
    extra_key = "prod_yoy_extra_cols"
    if extra_key not in st.session_state:
        st.session_state[extra_key] = []
    st.session_state[extra_key] = [x for x in st.session_state.get(extra_key, []) if x in extra_options]
    extra_cols_selected = st.multiselect(
        "Additional table columns",
        options=extra_options,
        key=extra_key,
        max_selections=4,
        help="Tambahan breakdown untuk tabel YoY saja. Visual tetap Top 10 berdasarkan Compare by utama.",
    )

    years = sorted(pd.to_numeric(df[year_col], errors="coerce").dropna().astype(int).unique().tolist())
    if len(years) < 2:
        st.info("Need at least two years for YoY.")
        return

    y1, y2 = st.columns([1, 1])
    if "prod_yoy_current" not in st.session_state or st.session_state.get("prod_yoy_current") not in years:
        st.session_state["prod_yoy_current"] = years[-1]
    current = y1.selectbox("Current year", years, key="prod_yoy_current")
    prev_candidates = [y for y in years if y < current]
    prev_options = prev_candidates or years
    if "prod_yoy_previous" not in st.session_state or st.session_state.get("prod_yoy_previous") not in prev_options:
        st.session_state["prod_yoy_previous"] = prev_options[-1] if prev_options else years[0]
    previous = y2.selectbox("Previous year", prev_options, key="prod_yoy_previous")

    dim_col = DETAIL_OPTIONS[dimension_label]
    extra_dim_cols = []
    for label in extra_cols_selected:
        c = DETAIL_OPTIONS.get(label)
        if c and c in df.columns and c not in [dim_col, year_col] and c not in extra_dim_cols:
            extra_dim_cols.append(c)
    table_group_cols = [dim_col] + extra_dim_cols

    selected_df = df[df[year_col].isin([previous, current])].copy()
    metric_build_list = []
    for metric_label in metrics:
        metric = YOY_METRICS.get(metric_label)
        if metric and metric in grouped_summary(selected_df, tuple(table_group_cols + [year_col])).columns:
            metric_build_list.append((metric_label, metric))
    if not metric_build_list:
        st.info("Selected metrics are not available in the current data.")
        return

    # Visual is always total current-year GWP by primary dimension, unaffected by extra columns or New/Renewal split.
    group_visual = grouped_summary(selected_df, (dim_col, year_col))
    if not group_visual.empty and "GWP" in group_visual.columns:
        top10_gwp = group_visual.pivot_table(index=dim_col, columns=year_col, values="GWP", aggfunc="sum", fill_value=0, observed=True).reset_index()
        year_cols = _ensure_yoy_year_columns(top10_gwp, [previous, current])
        prev_key = year_cols[previous]
        cur_key = year_cols[current]
        top10_gwp[prev_key] = pd.to_numeric(_as_1d_series(top10_gwp, prev_key, 0.0), errors="coerce").fillna(0.0)
        top10_gwp[cur_key] = pd.to_numeric(_as_1d_series(top10_gwp, cur_key, 0.0), errors="coerce").fillna(0.0)
        top10_gwp = top10_gwp[(top10_gwp[prev_key].abs() + top10_gwp[cur_key].abs()) > 1e-9].copy()
        top10_gwp = top10_gwp[[dim_col, cur_key]].rename(columns={dim_col: dimension_label, cur_key: "GWP_CURRENT"})
        if not top10_gwp.empty:
            render_yoy_top10_visual(top10_gwp, dimension_label, "GWP_CURRENT", int(current), unit)
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    combined, fmt_map, excluded_zero_gwp_rows = _build_yoy_combined_table(
        selected_df, table_group_cols, year_col, int(previous), int(current), metric_build_list,
        split_col="IS NEW" if (split_newrenewal and split_available) else None,
    )
    if combined.empty:
        st.info(f"No YoY rows after excluding categories where GWP is 0 in both {previous} and {current}.")
        return

    # Build overall and split versions for Excel regardless of current split toggle.
    overall_export, overall_fmt, _ = _build_yoy_combined_table(
        selected_df, table_group_cols, year_col, int(previous), int(current), metric_build_list, split_col=None
    )
    split_export = pd.DataFrame()
    if split_available:
        split_export, split_fmt, _ = _build_yoy_combined_table(
            selected_df, table_group_cols, year_col, int(previous), int(current), metric_build_list, split_col="IS NEW"
        )

    rename_map = {dim_col: dimension_label}
    for label in extra_cols_selected:
        c = DETAIL_OPTIONS.get(label)
        if c in combined.columns:
            rename_map[c] = label
        if c in overall_export.columns:
            overall_export = overall_export.rename(columns={c: label})
        if c in split_export.columns:
            split_export = split_export.rename(columns={c: label})
    combined = combined.rename(columns=rename_map).reset_index(drop=True)
    overall_export = overall_export.rename(columns={dim_col: dimension_label}).reset_index(drop=True) if not overall_export.empty else overall_export
    split_export = split_export.rename(columns={dim_col: dimension_label}).reset_index(drop=True) if not split_export.empty else split_export
    combined.columns = [str(c) for c in combined.columns]
    overall_export.columns = [str(c) for c in overall_export.columns] if not overall_export.empty else overall_export.columns
    split_export.columns = [str(c) for c in split_export.columns] if not split_export.empty else split_export.columns

    # Format map must follow displayed column names after renaming keys.
    fmt_map = {str(k): v for k, v in fmt_map.items()}

    total = len(combined)
    rows_per_page = 200
    total_pages = max(1, int(np.ceil(total / rows_per_page)))
    page_key = "prod_yoy_combined_page__" + hashlib.sha1(
        f"{year_col}|{dimension_label}|{previous}|{current}|{'|'.join(metrics)}|{'|'.join(extra_cols_selected)}|{split_newrenewal}".encode()
    ).hexdigest()[:8]
    st.session_state.setdefault(page_key, 1)
    st.session_state[page_key] = max(1, min(int(st.session_state.get(page_key, 1) or 1), total_pages))
    page = int(st.session_state[page_key])
    start = (page - 1) * rows_per_page
    end = min(start + rows_per_page, total)

    split_note = " | Split: New/Renewal" if split_newrenewal and split_available else ""
    zero_note = f" | Excluded {excluded_zero_gwp_rows:,} rows with GWP 0 vs 0" if excluded_zero_gwp_rows else ""
    st.caption(
        f"Default order: highest current-year GWP first. Showing rows {start + 1:,}–{end:,} "
        f"of {total:,} | Page {page:,} of {total_pages:,} | 200 rows per page{split_note}{zero_note}"
    )
    render_html_table(combined.iloc[start:end].copy(), unit, table_key=f"yoy_combined_{previous}_{current}_{page}", format_overrides=fmt_map)

    p1, p2, p3, p4 = st.columns([0.35, 0.35, 0.7, 6.5], vertical_alignment="bottom")

    def _prod_yoy_prev_page():
        st.session_state[page_key] = max(1, int(st.session_state.get(page_key, page) or page) - 1)

    def _prod_yoy_next_page():
        st.session_state[page_key] = min(total_pages, int(st.session_state.get(page_key, page) or page) + 1)

    p1.button("‹", key=f"prod_yoy_prev_{page_key}", disabled=page <= 1, on_click=_prod_yoy_prev_page)
    p2.button("›", key=f"prod_yoy_next_{page_key}", disabled=page >= total_pages, on_click=_prod_yoy_next_page)
    p3.number_input("Page", min_value=1, max_value=total_pages, step=1, key=page_key, label_visibility="collapsed")
    p4.caption("Basis columns are frozen. Additional table columns and New/Renewal split do not change the Top 10 visual.")

    xlsx = build_yoy_excel_bytes(
        overall_export,
        split_export,
        int(previous),
        int(current),
        as_of_text=st.session_state.get("prod_as_of_text", ""),
        unit=unit,
        filters=st.session_state.get("prod_committed_filters", {}),
        extra_lines=[
            f"Year Basis: {year_col}",
            f"Previous Year: {previous}",
            f"Current Year: {current}",
            f"Compare By: {dimension_label}",
            f"Metrics: {', '.join(metrics)}",
        ],
    )
    st.download_button(
        "Download YoY Excel",
        data=xlsx,
        file_name=f"production_yoy_overall_and_isnew_{previous}_{current}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"download_yoy_excel_{page_key}",
        width="content",
    )

def _filter_rows_for_export(filters: dict) -> list[str]:
    rows = []
    for col, info in (filters or {}).items():
        if not isinstance(info, dict):
            continue
        mode = str(info.get("mode", "Include All"))
        vals = info.get("values", []) or []
        vals = [str(v) for v in vals if str(v).strip()]
        if mode == "Include All":
            continue
        if mode == "Exclude All":
            rows.append(f"{col} ({mode})")
        elif vals:
            shown = ", ".join(vals[:10])
            if len(vals) > 10:
                shown += f", +{len(vals) - 10} more"
            rows.append(f"{col} ({mode}): {shown}")
        else:
            rows.append(f"{col} ({mode}): no values selected")
    return rows


def _excel_kind_for_col(col: str, series: pd.Series | None = None) -> str:
    name = str(col)
    low = name.lower()
    if "yoy %" in low or "ratio" in low or low in {"comm_ratio", "ri_ratio", "claim_ratio_to_gwp"}:
        return "pct"
    if "jumlah risiko" in low or name == "NUMBER_OF_RISKS" or "number_of_risks" in low:
        return "count"
    money_tokens = [
        "gwp", "premium", "comm", "commission", "klaim", "claim", "outstanding",
        "net premium", "paid claim", "gross claim", "os", "avg_premium"
    ]
    if any(tok in low for tok in money_tokens):
        return "money"
    if "yoy change" in low and series is not None and pd.api.types.is_numeric_dtype(series):
        return "number"
    if series is not None and pd.api.types.is_numeric_dtype(series):
        return "number"
    return "text"


def _prepare_excel_df(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    out = df.copy()
    out.columns = [str(c) for c in out.columns]
    kinds = {}
    for col in out.columns:
        kinds[col] = _excel_kind_for_col(col, out[col])
        if kinds[col] == "pct":
            out[col] = pd.to_numeric(out[col], errors="coerce") / 100.0
        elif kinds[col] in ["money", "count", "number"]:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out, kinds


def _write_export_filter_block(ws, start_row: int, as_of_text: str = "", unit: str = "", filters: dict | None = None, extra_lines: list[str] | None = None) -> int:
    row = start_row
    if as_of_text:
        ws.write(row, 0, f"As of Date: {as_of_text}")
        row += 1
    if unit:
        ws.write(row, 0, f"Display Unit: {unit}")
        row += 1
    filter_lines = _filter_rows_for_export(filters or {})
    if filter_lines:
        ws.write(row, 0, "Production Report for:")
        row += 1
        for line in filter_lines:
            ws.write(row, 0, line)
            row += 1
    if extra_lines:
        for line in extra_lines:
            if line:
                ws.write(row, 0, line)
                row += 1
    return row

def build_simple_excel_bytes(
    df: pd.DataFrame,
    sheet_name: str = "Export",
    as_of_text: str = "",
    unit: str = "",
    filters: dict | None = None,
    extra_lines: list[str] | None = None,
) -> bytes:
    buffer = io.BytesIO()
    out, kinds = _prepare_excel_df(df)
    meta_rows = _write_export_filter_block.__name__  # keep helper referenced for static analyzers
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        wb = writer.book
        ws_name = sheet_name[:31]
        # Leave room for metadata/filter list exactly like Risk Profile exports.
        dummy_ws = wb.add_worksheet(ws_name)
        writer.sheets[ws_name] = dummy_ws
        ws = dummy_ws
        title_fmt = wb.add_format({"bold": True, "font_color": THEME_BLUE, "font_size": 12})
        header_fmt = wb.add_format({"bold": True, "bg_color": THEME_BLUE, "font_color": "white"})
        money_fmt = wb.add_format({"num_format": "#,##0"})
        count_fmt = wb.add_format({"num_format": "#,##0"})
        number_fmt = wb.add_format({"num_format": "#,##0.00"})
        pct_fmt = wb.add_format({"num_format": "0.0%"})
        text_fmt = wb.add_format({})

        ws.write(0, 0, "Super Production Export", title_fmt)
        next_row = _write_export_filter_block(ws, 1, as_of_text=as_of_text, unit=unit, filters=filters or {}, extra_lines=extra_lines or [])
        startrow = next_row + 1
        out.to_excel(writer, index=False, startrow=startrow, sheet_name=ws_name)
        ws = writer.sheets[ws_name]
        for i, c in enumerate(out.columns):
            ws.write(startrow, i, c, header_fmt)
            kind = kinds.get(c, "text")
            width = max(14, min(38, len(str(c)) + 4))
            if kind == "money":
                ws.set_column(i, i, max(16, width), money_fmt)
            elif kind == "count":
                ws.set_column(i, i, max(14, width), count_fmt)
            elif kind == "pct":
                ws.set_column(i, i, max(13, width), pct_fmt)
            elif kind == "number":
                ws.set_column(i, i, max(14, width), number_fmt)
            else:
                ws.set_column(i, i, width, text_fmt)
        if len(out.columns) > 0:
            ws.autofilter(startrow, 0, startrow + len(out), len(out.columns) - 1)
            _freeze_excel_basis_columns(ws, out, startrow, kinds)
            _apply_growth_conditional_formats(ws, wb, out, startrow, kinds)
    return buffer.getvalue()

def current_detail_group_cols(df: pd.DataFrame) -> list[str]:
    active_label = st.session_state.get("prod_detail_active", "Acct Year")
    primary = DETAIL_OPTIONS.get(active_label, "ACCT_YEAR")
    extras = st.session_state.get("prod_detail_extra_cols", []) or []
    cols = [primary] if primary in df.columns else []
    for label in extras:
        col = DETAIL_OPTIONS.get(label)
        if col and col in df.columns and col not in cols:
            cols.append(col)
    return cols


def render_detailed_data(df: pd.DataFrame, unit: str, active_filters: dict, username: str, as_of_text: str) -> None:
    section_header("Detailed Production Data")
    options = [label for label, col in DETAIL_OPTIONS.items() if col in df.columns]
    if "prod_detail_active" not in st.session_state or st.session_state["prod_detail_active"] not in options:
        st.session_state["prod_detail_active"] = options[0]
    with st.container(key="prod_detail_scroller_scope"):
        active = st.radio("Detailed view", options=options, key="prod_detail_active", horizontal=True, label_visibility="collapsed")
    extra_options = [o for o in options if o != active]
    if "prod_detail_extra_cols" not in st.session_state:
        st.session_state["prod_detail_extra_cols"] = []
    def _reset_prod_detail_extra_cols():
        st.session_state["prod_detail_extra_cols"] = []
        _clear_production_pagination_state()

    c1, c2 = st.columns([6, 1], vertical_alignment="bottom")
    with c1:
        st.multiselect("Additional columns", options=extra_options, max_selections=5, key="prod_detail_extra_cols", help="Tambahkan breakdown tambahan. Maksimal 5 kolom agar tabel tetap ringan.")
    with c2:
        st.button("Reset", key="prod_detail_reset_extra", width="stretch", on_click=_reset_prod_detail_extra_cols)
    group_cols = current_detail_group_cols(df)
    pivot = grouped_summary(df, tuple(group_cols))
    if pivot.empty:
        st.info("No data on this filter.")
        return
    total = len(pivot)
    page_key = "prod_detail_page__" + hashlib.sha1("|".join(group_cols).encode()).hexdigest()[:8]
    st.session_state.setdefault(page_key, 1)
    rows_per_page = 200
    total_pages = max(1, int(np.ceil(total / rows_per_page)))
    st.session_state[page_key] = max(1, min(int(st.session_state.get(page_key, 1) or 1), total_pages))
    page = int(st.session_state[page_key])
    start = (page - 1) * rows_per_page
    end = min(start + rows_per_page, total)
    st.caption(f"Showing rows {start+1:,}–{end:,} of {total:,} | Page {page:,} of {total_pages:,} | As of {as_of_text}")
    render_html_table(pivot.iloc[start:end].copy(), unit, table_key=f"{'_'.join(group_cols)}_{page}")
    p1, p2, p3, p4 = st.columns([0.35, 0.35, 0.7, 6.5], vertical_alignment="bottom")
    if p1.button("‹", key="prod_prev_page", disabled=page <= 1):
        st.session_state[page_key] = max(1, page - 1); st.rerun()
    if p2.button("›", key="prod_next_page", disabled=page >= total_pages):
        st.session_state[page_key] = min(total_pages, page + 1); st.rerun()
    p3.number_input("Page", min_value=1, max_value=total_pages, step=1, key=page_key, label_visibility="collapsed")
    p4.caption(f"200 rows per page · Sort by control is client-side seperti Risk Profile")
    render_export_controls(pivot, group_cols, active_filters, unit, username, as_of_text)


# ==========================================================
# Export
# ==========================================================
def build_excel_bytes(df: pd.DataFrame, unit: str, as_of_text: str, filters: dict, proxy_mapping: dict) -> bytes:
    buffer = io.BytesIO()
    ordered = df.copy()[final_metric_order(df)]
    out, kinds = _prepare_excel_df(ordered)
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        wb = writer.book
        ws_name = "Production Summary"
        ws = wb.add_worksheet(ws_name)
        writer.sheets[ws_name] = ws
        title_fmt = wb.add_format({"bold": True, "font_color": THEME_BLUE, "font_size": 12})
        header_fmt = wb.add_format({"bold": True, "bg_color": THEME_BLUE, "font_color": "white"})
        money_fmt = wb.add_format({"num_format": "#,##0"})
        count_fmt = wb.add_format({"num_format": "#,##0"})
        number_fmt = wb.add_format({"num_format": "#,##0.00"})
        pct_fmt = wb.add_format({"num_format": "0.0%"})
        text_fmt = wb.add_format({})

        ws.write(0, 0, "Super Production Export", title_fmt)
        extra_lines = [f"Proxy groups saved: {len(proxy_mapping or {})}"]
        startrow = _write_export_filter_block(ws, 1, as_of_text=as_of_text, unit=unit, filters=filters or {}, extra_lines=extra_lines) + 1
        out.to_excel(writer, index=False, startrow=startrow, sheet_name=ws_name)
        ws = writer.sheets[ws_name]

        for i, c in enumerate(out.columns):
            ws.write(startrow, i, c, header_fmt)
            kind = kinds.get(c, "text")
            width = max(14, min(38, len(str(c)) + 4))
            if kind == "money":
                ws.set_column(i, i, max(16, width), money_fmt)
            elif kind == "count":
                ws.set_column(i, i, max(14, width), count_fmt)
            elif kind == "pct":
                ws.set_column(i, i, max(13, width), pct_fmt)
            elif kind == "number":
                ws.set_column(i, i, max(14, width), number_fmt)
            else:
                ws.set_column(i, i, width, text_fmt)
        if len(out.columns) > 0:
            ws.autofilter(startrow, 0, startrow + len(out), len(out.columns) - 1)
            _freeze_excel_basis_columns(ws, out, startrow, kinds)
            _apply_growth_conditional_formats(ws, wb, out, startrow, kinds)

        if proxy_mapping:
            proxy_df = pd.DataFrame([{"PROXY_GROUP": g, "INTERMEDIARY_NAME": m} for g, ms in proxy_mapping.items() for m in ms])
            proxy_df.to_excel(writer, index=False, sheet_name="Proxy Mapping")
            ws_proxy = writer.sheets["Proxy Mapping"]
            for i, c in enumerate(proxy_df.columns):
                ws_proxy.write(0, i, c, header_fmt)
                ws_proxy.set_column(i, i, 32, text_fmt)
            ws_proxy.autofilter(0, 0, len(proxy_df), max(0, len(proxy_df.columns)-1))
            ws_proxy.freeze_panes(1, 0)
    return buffer.getvalue()

def build_pdf_bytes(df: pd.DataFrame, unit: str, as_of_text: str, username: str) -> bytes:
    if colors is None:
        raise RuntimeError("reportlab is not installed")
    buffer = io.BytesIO()
    out = df.copy()[final_metric_order(df)].head(500)
    display = out.copy()
    money = [c for c in ["GWP", "AVG_PREMIUM", "COMM_IDR", "RI Premium", "NET_PREMIUM", "Klaim Bruto", "CLAIM_PAID", "OS", "RI Claim"] if c in display.columns]
    pcts = [c for c in ["COMM_RATIO", "RI_RATIO", "CLAIM_RATIO_TO_GWP"] if c in display.columns]
    for c in display.columns:
        if c in money:
            display[c] = display[c].apply(lambda x: fmt_money(x, unit))
        elif c in pcts:
            display[c] = display[c].apply(fmt_pct)
        elif c == "NUMBER_OF_RISKS":
            display[c] = display[c].apply(fmt_num)
        else:
            display[c] = display[c].astype(str)
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=.8*cm, rightMargin=.8*cm, topMargin=.8*cm, bottomMargin=.8*cm)
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle("H", parent=styles["Normal"], textColor=colors.white, fontName="Helvetica-Bold", fontSize=7, alignment=1)
    cell_style = ParagraphStyle("C", parent=styles["Normal"], fontSize=7, leading=8)
    data = [[Paragraph(str(c).replace("_", " "), header_style) for c in display.columns]]
    for _, row in display.iterrows():
        data.append([Paragraph(html.escape(str(row[c])), cell_style) for c in display.columns])
    avail = landscape(A4)[0] - 1.6*cm
    colw = [max(1.25*cm, min(4.0*cm, avail / max(1, len(display.columns))))] * len(display.columns)
    tbl = Table(data, repeatRows=1, colWidths=colw)
    tbl.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor(THEME_BLUE)), ("GRID", (0,0), (-1,-1), .25, colors.grey), ("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
    elems = [Paragraph("<b>Super Production Report</b>", styles["Title"]), Paragraph(f"As of: {as_of_text}", styles["Normal"]), Paragraph(f"Downloaded by: {html.escape(username or '-')}", styles["Normal"]), Spacer(1, .25*cm), tbl]
    doc.build(elems)
    return buffer.getvalue()




def _fragment_export_if_available(func):
    """Isolate export controls so Prepare PDF/Excel reruns only this block, like Risk Profile."""
    return st.fragment(func) if hasattr(st, "fragment") else func


@_fragment_export_if_available
def render_export_controls(pivot: pd.DataFrame, group_cols: list, active_filters: dict, unit: str, username: str, as_of_text: str) -> None:
    """Lazy export controls. In Streamlit versions with st.fragment, Prepare only reruns this block."""
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    section_header("Export")
    total = len(pivot)
    excel_ranges = []
    chunk = 50000
    for s0 in range(0, max(total, 1), chunk):
        e0 = min(s0 + chunk, total)
        excel_ranges.append(f"Rows {s0+1:,} - {e0:,}" if total else "Rows 0 - 0")

    range_key = "prod_excel_range__" + hashlib.sha1(("|".join(group_cols) + str(total)).encode()).hexdigest()[:8]
    if total > chunk:
        if range_key not in st.session_state or st.session_state.get(range_key) not in excel_ranges:
            st.session_state[range_key] = excel_ranges[0]
        selected_range = st.selectbox("Excel export rows", options=excel_ranges, key=range_key)
    else:
        selected_range = excel_ranges[0]

    s, e = 0, total
    if total > chunk:
        cleaned = selected_range.replace("Rows", "").replace(",", "").strip()
        left, right = cleaned.split("-")
        s, e = int(left.strip()) - 1, int(right.strip())

    # Clear stale prepared files when the export-relevant state changes.
    export_sig = _hash_payload({
        "group_cols": group_cols,
        "filters": active_filters,
        "unit": unit,
        "as_of": as_of_text,
        "rows": total,
        "range": [s, e],
        "proxy_sig": st.session_state.get("prod_proxy_mapping", {}),
    })
    if st.session_state.get("prod_export_sig") != export_sig:
        for k in ["prod_pdf_href", "prod_pdf_name", "prod_xlsx_href", "prod_xlsx_name"]:
            st.session_state.pop(k, None)
        st.session_state["prod_export_sig"] = export_sig

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Prepare PDF", key="prod_prepare_pdf", width="content"):
            try:
                with st.spinner("Preparing PDF..."):
                    doc_id = generate_report_id("SP")
                    pdf = build_pdf_bytes(pivot, unit, as_of_text, username)
                    file_name = f"super_production_{doc_id}.pdf"
                    st.session_state["prod_pdf_href"] = _data_uri(pdf, "application/pdf")
                    st.session_state["prod_pdf_name"] = file_name
                    save_document_log(
                        doc_id, username, "PDF",
                        st.session_state.get("prod_detail_active", ""),
                        st.session_state.get("prod_detail_extra_cols", []),
                        group_cols, active_filters, unit,
                        st.session_state.get("prod_proxy_mapping", {}),
                        st.session_state.get("prod_yoy_metrics", []),
                        total, file_name,
                    )
            except Exception as ex:
                st.error(f"PDF export failed: {ex}")
        if st.session_state.get("prod_pdf_href"):
            _download_link("Download PDF", st.session_state["prod_pdf_href"], st.session_state.get("prod_pdf_name", "super_production.pdf"))
            st.caption("PDF ready. Uses top 500 rows. Regenerate jika filter berubah.")
        else:
            st.caption("Prepare PDF dulu sebelum download.")
    with c2:
        if st.button("Prepare Excel", key="prod_prepare_excel", width="content"):
            try:
                with st.spinner("Preparing Excel..."):
                    doc_id = generate_report_id("SP")
                    xlsx = build_excel_bytes(pivot.iloc[s:e].copy(), unit, as_of_text, active_filters, st.session_state.get("prod_proxy_mapping", {}))
                    file_name = f"super_production_{doc_id}.xlsx"
                    st.session_state["prod_xlsx_href"] = _data_uri(xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    st.session_state["prod_xlsx_name"] = file_name
                    save_document_log(
                        doc_id, username, "Excel",
                        st.session_state.get("prod_detail_active", ""),
                        st.session_state.get("prod_detail_extra_cols", []),
                        group_cols, active_filters, unit,
                        st.session_state.get("prod_proxy_mapping", {}),
                        st.session_state.get("prod_yoy_metrics", []),
                        total, file_name,
                    )
            except Exception as ex:
                st.error(f"Excel export failed: {ex}")
        if st.session_state.get("prod_xlsx_href"):
            _download_link("Download Excel", st.session_state["prod_xlsx_href"], st.session_state.get("prod_xlsx_name", "super_production.xlsx"))
            st.caption(f"Excel ready. Rows {s+1:,}–{e:,} of {total:,} included. Regenerate jika filter/range berubah.")
        else:
            st.caption("Prepare Excel dulu sebelum download.")


# ==========================================================
# Saved reports UI
# ==========================================================
def render_saved_reports(active_filters: dict, unit: str, username: str, df: pd.DataFrame) -> None:
    section_header("Saved Reports")
    notice = st.session_state.pop("prod_saved_notice", None)
    if notice:
        st.success(notice)
    mode = st.radio("Saved report workspace", ["Open Saved", "Save Current"], horizontal=True, label_visibility="collapsed", key="prod_saved_workspace")
    if mode == "Open Saved":
        records = list_saved_reports()
        q = st.text_input("Search", placeholder="Type label, note, or report ID", key="prod_saved_search")
        if q:
            records = [r for r in records if q.lower() in " ".join([str(r.get('REPORT_ID','')), str(r.get('LABEL','')), str(r.get('DESCRIPTION',''))]).lower()]
        if not records:
            st.caption("No saved report found.")
            return
        ids = [""] + [_sanitize_id(r.get("REPORT_ID")) for r in records]
        label_map = {_sanitize_id(r.get("REPORT_ID")): f"📄 {r.get('LABEL') or r.get('REPORT_ID')} · {(r.get('UPDATED_AT') or r.get('CREATED_AT') or '')[:16]}" for r in records}
        with st.form("prod_open_saved_form"):
            selected = st.selectbox("Saved list", options=ids, format_func=lambda x: "Choose saved report" if not x else label_map.get(x, x))
            rec = next((r for r in records if _sanitize_id(r.get("REPORT_ID")) == selected), None)
            if rec:
                st.markdown(f"<div class='saved-report-preview-card'><div class='saved-report-card-title'>{html.escape(rec.get('LABEL') or selected)}</div><div class='saved-report-card-id'>{html.escape(selected)}</div><div class='saved-report-card-desc'>{html.escape(rec.get('DESCRIPTION') or '')}</div><div class='saved-report-card-meta'>Updated {(rec.get('UPDATED_AT') or rec.get('CREATED_AT') or '')[:16]}</div></div>", unsafe_allow_html=True)
            clicked = st.form_submit_button("Open")
        if clicked:
            if not selected:
                st.warning("Choose a saved report first.")
            else:
                st.session_state["prod_pending_open_report"] = selected
                st.rerun()
    else:
        current_id = _sanitize_id(st.session_state.get("prod_current_report_id", ""))
        with st.form("prod_save_current_form"):
            label = st.text_input("Label", placeholder="Example: Non-fronting production review")
            desc = st.text_area("Keterangan", placeholder="Optional note", height=90)
            c1, c2 = st.columns(2)
            save_new = c1.form_submit_button("Save New")
            update_current = c2.form_submit_button("Update Current", disabled=not bool(current_id))
        if save_new or update_current:
            final_label = str(label or "").strip()
            if not final_label:
                st.warning("Isi label terlebih dahulu.")
                return
            report_id = current_id if update_current else generate_report_id("SP")
            group_cols = current_detail_group_cols(df)
            save_document_log(report_id, username, "Saved Report", st.session_state.get("prod_detail_active", ""), st.session_state.get("prod_detail_extra_cols", []), group_cols, active_filters, unit, st.session_state.get("prod_proxy_mapping", {}), st.session_state.get("prod_yoy_metrics", []), len(df), f"Saved Report - {final_label}")
            upsert_saved_report_metadata(report_id, username, final_label, desc)
            st.session_state["prod_current_report_id"] = report_id
            st.success(f"Saved: {final_label}")
            st.markdown(f"<span class='asof-chip'>Report ID: {html.escape(report_id)}</span>", unsafe_allow_html=True)


# ==========================================================
# Main entrypoint
# ==========================================================
def render_production_dashboard(username: str = "", data_path: str | None = None) -> None:
    inject_theme_css()
    apply_pending_saved_if_any()
    path = _find_default_path(data_path)
    try:
        raw_df = load_production_data(path)
    except Exception as e:
        st.error(f"Failed to load production data: {e}")
        return

    df = apply_proxy_mapping(raw_df)
    as_of_text = get_as_of_text(raw_df, path)
    st.session_state["prod_as_of_text"] = as_of_text

    # Render the static page shell before sidebar filtering. Previously the
    # workspace tabs were created only after all filter widgets/options were
    # processed, so a filter change left the main canvas looking empty before
    # the same header/tabs appeared again. Stable keyed containers make these
    # unchanged objects reconcile instead of visually disappearing.
    with st.container(key="prod_hero_stable_container"):
        st.markdown(f"""
        <div class='prod-hero'>
          <div class='prod-title'>Super Production</div>
          <div class='prod-subtitle'>Monitoring produksi, YoY comparison, intermediary proxy grouping, export, dan saved report seperti Risk Profile.</div>
          <div class='asof-chip'>As of Date: {html.escape(as_of_text)}</div>
        </div>
        """, unsafe_allow_html=True)

    workspace_options = ["Overview", "YoY Comparison", "Detailed Data", "Save / Load Report"]
    if st.session_state.get("prod_workspace") not in workspace_options:
        st.session_state["prod_workspace"] = workspace_options[0]
    with st.container(key="prod_workspace_nav_stable_container"):
        workspace = st.radio(
            "Production workspace",
            options=workspace_options,
            horizontal=True,
            label_visibility="collapsed",
            key="prod_workspace",
        )

    filtered_df, active_filters, unit = render_filter_sidebar(df)

    with st.container(key=f"prod_workspace_body_stable_{hashlib.sha1(str(workspace).encode()).hexdigest()[:8]}"):
        if filtered_df.empty:
            st.info("No data on this filter.")
            return
        if workspace == "Overview":
            render_overview(filtered_df, unit)
        elif workspace == "YoY Comparison":
            render_yoy(filtered_df, unit)
        elif workspace == "Detailed Data":
            render_detailed_data(filtered_df, unit, active_filters, username, as_of_text)
        else:
            render_saved_reports(active_filters, unit, username, filtered_df)


def dashboard(username: str | None = None, data_path: str | None = None) -> None:
    if username is None:
        username = st.session_state.get("username", "")
    render_production_dashboard(username=username, data_path=data_path)


if __name__ == "__main__":
    dashboard()
