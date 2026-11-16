import base64
import hashlib
import html
import io
import re
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


DEFAULT_RENEWAL_PATH = "RENEWAL261001.parquet"
AS_OF_DATE = pd.Timestamp("2026-10-08")
AS_OF_DATE_KEY = int(AS_OF_DATE.year) * 100 + int(AS_OF_DATE.month)
RENEWAL_NO_COL = "RENEWAL POLICY NO"
POLICY_NO_COL = "POLICY NO"
PREMIUM_COL = "PREMIUM AMT"
RENEWAL_DASHBOARD_VERSION = "case-rate-v8-filters-detail-pagination"
DETAIL_PAGE_SIZE = 25
PREMIUM_DISPLAY_DIVISOR = 1_000_000.0
PREMIUM_DISPLAY_UNIT = "Juta"
PREMIUM_DISPLAY_NOTE = "* dalam juta"
EXCLUDED_COLUMNS = {RENEWAL_NO_COL, "PAYMENT_STATUS", "PAYMENT STATUS", "FAC_OBLIGATORY", "_DATE_KEY", "YEAR_MONTH"}


def _script_dir() -> Path:
    try:
        return Path(__file__).resolve().parent
    except Exception:
        return Path.cwd()


def _candidate_renewal_paths(path: str = DEFAULT_RENEWAL_PATH) -> list[Path]:
    """Return parquet candidates without adding any manual upload option.

    Streamlit is often started from a different working directory than the
    script. This makes the dashboard accidentally read an older parquet with the
    same name. We therefore check both cwd and the script folder, then choose the
    first candidate whose PREMIUM AMT total is non-zero.
    """
    candidates: list[Path] = []
    seen: set[str] = set()

    def add(candidate):
        if candidate is None:
            return
        p = Path(str(candidate)).expanduser()
        variants = [p]
        if not p.is_absolute():
            variants = [Path.cwd() / p, _script_dir() / p]
        for v in variants:
            try:
                key = str(v.resolve())
            except Exception:
                key = str(v)
            if key not in seen and v.exists() and v.is_file() and v.suffix.lower() == ".parquet":
                seen.add(key)
                candidates.append(v)

    add(path)
    #add("Renewal - 30 June 2026 Ext Aug 2026(1).parquet")
    #add("Renewal - 30 June 2026 Ext Aug 2026.parquet")
    add(DEFAULT_RENEWAL_PATH)

    for base in [Path.cwd(), _script_dir()]:
        try:
            for v in sorted(base.glob("Renewal*.parquet"), key=lambda x: x.stat().st_mtime, reverse=True):
                add(v)
        except Exception:
            pass

    return candidates


# =========================================================
# EXPORT METADATA HELPERS
# =========================================================
def _sanitize_doc_id(doc_id: str) -> str:
    return str(doc_id or "").strip().upper().replace(" ", "")


def generate_document_id(prefix: str = "RN") -> str:
    date_part = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%y%m%d")
    return f"{prefix}-{date_part}-{uuid.uuid4().hex[:8].upper()}"


def _month_to_num(value):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "(blank)"}:
        return None

    # Supports common renewal file formats:
    #   1, 01, 1.0, "01. January", "02 February", "January"
    leading_num = re.match(r"^0*([1-9]|1[0-2])(?:\D|$)", text)
    if leading_num:
        return int(leading_num.group(1))

    try:
        n = int(float(text))
        if 1 <= n <= 12:
            return n
    except Exception:
        pass

    cleaned = re.sub(r"^[0-9]{1,2}\s*[.\-/)]*\s*", "", text).strip().lower()
    key = cleaned[:3] if cleaned else text.lower()[:3]
    month_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "mei": 5, "jun": 6,
        "jul": 7, "aug": 8, "agu": 8, "sep": 9, "oct": 10, "okt": 10, "nov": 11, "dec": 12, "des": 12,
    }
    return month_map.get(key)


def _month_name_id(month_num: int) -> str:
    names = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
        7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember",
    }
    return names.get(int(month_num), str(month_num))


def _find_option_case_insensitive(options: list[str], target: str) -> str | None:
    target_norm = str(target or "").strip().upper()
    for opt in options or []:
        if str(opt).strip().upper() == target_norm:
            return opt
    return None


def _normalize_col_key(value) -> str:
    """Normalize column names for robust matching across spaces, underscores, and symbols."""
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").strip().upper())


def _find_existing_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Return the actual dataframe column matching one of the candidate names."""
    if df is None or df.empty:
        return None
    norm_map = {_normalize_col_key(c): c for c in df.columns}
    for cand in candidates or []:
        key = _normalize_col_key(cand)
        if key in norm_map:
            return norm_map[key]
    return None


def _find_premium_col(df: pd.DataFrame) -> str | None:
    """Find the premium column used for Renewal Rate.

    This intentionally checks many common premium aliases because the Renewal Rate
    will become 0% when the premium column is not detected or is parsed as NaN.
    """
    exact = _find_existing_col(df, [
        PREMIUM_COL,
        "PREMIUM", "PREMIUM_AMOUNT", "PREMIUM AMOUNT", "GROSS PREMIUM",
        "GROSS_PREMIUM", "GWP", "PREMI", "PREMIUM IDR", "PREMIUM_AMT",
        "PREMIUM AMT IDR", "PREMIUM_AMOUNT_IDR", "PREMIUM AMOUNT IDR",
        "TOTAL PREMIUM", "TOTAL_PREMIUM", "NET PREMIUM", "NET_PREMIUM",
        "WRITTEN PREMIUM", "WRITTEN_PREMIUM", "PREMIUM BEFORE DISCOUNT",
    ])
    if exact:
        return exact

    # Fallback: choose the first premium-like column with a non-zero numeric sum.
    premium_like = [
        c for c in df.columns
        if any(token in _normalize_col_key(c) for token in ["PREM", "PREMI", "GWP"])
    ]
    best_col = None
    best_sum = 0.0
    for col in premium_like:
        s = _to_numeric_amount(df[col])
        total = float(s.abs().sum()) if len(s) else 0.0
        if total > best_sum:
            best_col = col
            best_sum = total
    return best_col


def _as_month_key(year, month) -> int | None:
    try:
        y = int(float(year))
        m = _month_to_num(month)
        if m is None:
            return None
        return y * 100 + int(m)
    except Exception:
        return None


def _to_numeric_amount(series) -> pd.Series:
    """Convert premium-like values into numeric amounts.

    Handles normal numeric columns and common exported string formats such as:
    "1,234,567", "1.234.567,89", "Rp 1.234.567", blanks, and parentheses negatives.
    """
    if series is None:
        return pd.Series([], dtype="float64")
    s = pd.Series(series).copy()
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce").fillna(0.0)

    text = s.fillna("").astype(str).str.strip()
    text = text.str.replace("\u00a0", "", regex=False)
    text = text.str.replace("Rp", "", case=False, regex=False)
    text = text.str.replace("IDR", "", case=False, regex=False)
    text = text.str.replace(" ", "", regex=False)
    text = text.str.replace("(", "-", regex=False).str.replace(")", "", regex=False)
    text = text.str.replace(r"[^0-9,.-]", "", regex=True)

    # Indonesian format: 1.234.567,89 -> 1234567.89
    id_mask = text.str.contains(",", regex=False) & text.str.contains(".", regex=False)
    text = text.where(~id_mask, text.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))

    # If only comma is present, decide whether it is decimal or thousands separator.
    comma_only = text.str.contains(",", regex=False) & ~text.str.contains(".", regex=False)
    comma_decimal = comma_only & text.str.match(r"^-?\d+,\d{1,2}$")
    text = text.where(~comma_decimal, text.str.replace(",", ".", regex=False))
    text = text.where(comma_decimal | ~comma_only, text.str.replace(",", "", regex=False))

    # If only dot is present multiple times, treat dots as thousand separators.
    dot_count = text.str.count(r"\.")
    multi_dot = dot_count > 1
    text = text.where(~multi_dot, text.str.replace(".", "", regex=False))

    return pd.to_numeric(text, errors="coerce").fillna(0.0)


def _safe_premium_series(df: pd.DataFrame) -> pd.Series:
    """Return numeric premium series, re-detecting the premium column if needed.

    This avoids Renewal Rate becoming 0 when the dataframe is re-created,
    filtered, cached, or passed from another dashboard layer without attrs.
    """
    if df is None or df.empty:
        return pd.Series([], dtype="float64")

    if PREMIUM_COL in df.columns:
        return _to_numeric_amount(df[PREMIUM_COL])

    premium_col = _find_premium_col(df)
    if premium_col and premium_col in df.columns:
        return _to_numeric_amount(df[premium_col])

    return pd.Series([0.0] * len(df), index=df.index, dtype="float64")


def _ensure_premium_column(df: pd.DataFrame) -> pd.DataFrame:
    """Guarantee a numeric PREMIUM AMT column exists and preserve source info."""
    if df is None:
        return df
    out = df.copy()
    premium_col = _find_premium_col(out)

    if premium_col and premium_col in out.columns:
        out[PREMIUM_COL] = _to_numeric_amount(out[premium_col])
        out.attrs["PREMIUM_SOURCE_COL"] = str(premium_col)
        out.attrs["PREMIUM_TOTAL"] = float(out[PREMIUM_COL].sum())
    else:
        out[PREMIUM_COL] = 0.0
        out.attrs["PREMIUM_SOURCE_COL"] = "NOT FOUND"
        out.attrs["PREMIUM_TOTAL"] = 0.0

    return out


def _premium_debug_message(df: pd.DataFrame) -> str:
    """Human-readable premium detection message for troubleshooting only."""
    if df is None or df.empty:
        return "Dataset kosong."
    premium_like = [str(c) for c in df.columns if any(t in _normalize_col_key(c) for t in ["PREM", "PREMI", "GWP", "AMT"])]
    source = str(df.attrs.get("PREMIUM_SOURCE_COL") or (_find_premium_col(df) or "NOT FOUND"))
    total = float(_safe_premium_series(df).sum())
    return f"Premium source: {source}. Total premium*: {_format_amount(total)}. {PREMIUM_DISPLAY_NOTE}. Premium-like columns: {', '.join(premium_like) if premium_like else '-'}"


def _format_amount(value) -> str:
    """Format premium amount in Juta for dashboard display.

    The dataframe still keeps the original full amount for Renewal Rate
    calculation. Only the displayed value is divided by 1,000,000.
    Do not print the word "Juta" in each value; the unit is explained once
    through premium column headers and notes.
    """
    try:
        return f"{float(value) / PREMIUM_DISPLAY_DIVISOR:,.0f}".replace(",", ".")
    except Exception:
        return "0"


def _premium_display_label(col: str) -> str:
    """Mark premium-like dashboard headers with * without changing raw column names."""
    c = str(col)
    premium_names = {"Expired Premium", "Renewed Premium", "Not Renewed Premium", PREMIUM_COL}
    if c in premium_names:
        return f"{c}*"
    return c

def _add_year_month_label(df: pd.DataFrame) -> pd.DataFrame:
    """Add a stable YEAR_MONTH label for cross-year monthly grouping."""
    if df is None or df.empty or "YEARS" not in df.columns or "MONTH" not in df.columns:
        return df
    out = df.copy()
    years = pd.to_numeric(out["YEARS"], errors="coerce")
    months = out["MONTH"].apply(_month_to_num)
    labels = []
    for y, m in zip(years, months):
        if pd.isna(y) or m is None or pd.isna(m):
            labels.append("(Blank)")
        else:
            labels.append(f"{int(y)}-{int(m):02d} {_month_short_name(int(m))}")
    out["YEAR_MONTH"] = labels
    return out


def get_renewal_period_text(df: pd.DataFrame) -> str:
    if df is None or df.empty or "YEARS" not in df.columns or "MONTH" not in df.columns:
        return "-"
    tmp = df[["YEARS", "MONTH"]].copy()
    tmp["_year"] = pd.to_numeric(tmp["YEARS"], errors="coerce")
    tmp["_month"] = tmp["MONTH"].apply(_month_to_num)
    tmp = tmp[tmp["_year"].notna() & tmp["_month"].notna()].copy()
    if tmp.empty:
        return "-"
    tmp["_date_key"] = tmp["_year"].astype(int) * 100 + tmp["_month"].astype(int)
    min_row = tmp.loc[tmp["_date_key"].idxmin()]
    max_row = tmp.loc[tmp["_date_key"].idxmax()]
    start = f"{_month_name_id(int(min_row['_month']))} {int(min_row['_year'])}"
    end = f"{_month_name_id(int(max_row['_month']))} {int(max_row['_year'])}"
    return start if start == end else f"{start} - {end}"


def _active_filter_lines(active_filters: dict) -> list[str]:
    if not active_filters:
        return ["No active filter"]
    lines = []
    for col, spec in active_filters.items():
        mode = "Include Selected"
        vals = []
        if isinstance(spec, dict):
            mode = str(spec.get("mode") or mode)
            vals = list(spec.get("values") or [])
        else:
            vals = list(spec or [])

        if not vals:
            continue
        prefix = "Exclude" if mode == "Exclude Selected" else "Include"
        if len(vals) > 10:
            lines.append(f"{col}: {prefix} {len(vals)} selected")
        else:
            lines.append(f"{col}: {prefix} {', '.join(map(str, vals))}")
    return lines or ["No active filter"]


def _write_excel_metadata(worksheet, active_filters: dict, period_text: str, doc_id: str, username: str, start_row: int = 0) -> int:
    row = int(start_row or 0)
    worksheet.write(row, 0, "Renewal Report for:")
    row += 1
    for line in _active_filter_lines(active_filters):
        worksheet.write(row, 0, line)
        row += 1
    worksheet.write(row, 0, f"Period: {period_text or '-'}")
    row += 1
    worksheet.write(row, 0, f"Document ID: {_sanitize_doc_id(doc_id)}")
    row += 1
    worksheet.write(row, 0, f"Downloaded by: {username or '-'}")
    row += 1
    worksheet.write(row, 0, f"Downloaded at: {datetime.now(ZoneInfo('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S WIB')}")
    row += 1
    return row




def _renewal_ratio_band(value) -> str:
    """Return color band for renewal ratio thresholds used in PDF/Excel export."""
    try:
        v = float(value)
    except Exception:
        v = 0.0
    if v <= 25:
        return "red"
    if v <= 50:
        return "yellow"
    return "green"


def _renewal_ratio_pdf_color(value):
    """PDF summary table highlight only for weak ratios.

    0-25%  : red
    >25-50%: yellow
    >50%   : no special highlight, keep normal/zebra row background
    """
    band = _renewal_ratio_band(value)
    if band == "red":
        return colors.HexColor("#FCE7E7")
    if band == "yellow":
        return colors.HexColor("#FFF3D6")
    return None


def _renewal_ratio_dot_color(value) -> str:
    band = _renewal_ratio_band(value)
    if band == "red":
        return "#DC3545"
    if band == "yellow":
        return "#E39A5B"
    return "#28A745"


def _is_export_numeric_col(col: str, series: pd.Series | None = None) -> bool:
    c = str(col)
    if c in {"Expired Policy", "Renewed Policy", "Not Renewed", "Expired Premium", "Renewed Premium", "Not Renewed Premium"} or "Ratio" in c or "Rate" in c:
        return True
    if series is not None:
        try:
            return pd.api.types.is_numeric_dtype(series)
        except Exception:
            return False
    return False

def draw_renewal_footer(canvas, doc, username: str = "", doc_id: str | None = None):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    now = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d %b %Y %H:%M WIB")
    canvas.drawString(1.0 * cm, 0.7 * cm, "Prepared by Actuarial Department | Confidential")
    canvas.drawRightString(doc.pagesize[0] - 1.0 * cm, 0.7 * cm, f"Downloaded by: {username or '-'} | At: {now}")
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(doc.pagesize[0] - 1.0 * cm, doc.pagesize[1] - 0.8 * cm, f"Document ID: {_sanitize_doc_id(doc_id)}")
    canvas.restoreState()


# =========================================================
# DATA HELPERS
# =========================================================
def _prepare_renewal_dataframe(raw_df: pd.DataFrame, source_path: str | None = None) -> pd.DataFrame:
    df = raw_df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # Normalize common year/month column variants so cross-year data can be charted.
    year_col = _find_existing_col(df, ["YEARS", "YEAR", "UW_YEAR", "UW YEAR", "POLICY YEAR", "PERIOD_YEAR", "Years"])
    month_col = _find_existing_col(df, ["MONTH", "MONTHS", "UW_MONTH", "UW MONTH", "POLICY MONTH", "PERIOD_MONTH", "Month"])
    if year_col and "YEARS" not in df.columns:
        df["YEARS"] = df[year_col]
    if month_col and "MONTH" not in df.columns:
        df["MONTH"] = df[month_col]

    # Guarantee a numeric premium column for Renewal Rate.
    df = _ensure_premium_column(df)
    if source_path:
        df.attrs["RENEWAL_SOURCE_PATH"] = str(source_path)

    if RENEWAL_NO_COL not in df.columns:
        df[RENEWAL_NO_COL] = ""
    if POLICY_NO_COL not in df.columns:
        raise ValueError(f"Required column missing: {POLICY_NO_COL}")

    # Renewal is counted only when renewal policy number has length > 10.
    renewal_text = df[RENEWAL_NO_COL].fillna("").astype(str).str.strip()
    df["IS_RENEWED"] = renewal_text.str.len() > 10
    df["RENEWAL_STATUS"] = np.where(df["IS_RENEWED"], "Renewed", "Expired / Not Renewed")

    if "YEARS" in df.columns:
        df["YEARS"] = pd.to_numeric(df["YEARS"], errors="coerce").astype("Int64")

    # Keep blanks readable in filters/tables, but do not touch renewal policy logic
    # or PREMIUM AMT. Premium must remain numeric for Renewal Rate.
    for col in df.select_dtypes(include=["object", "string"]).columns:
        if col not in {RENEWAL_NO_COL, PREMIUM_COL}:
            df[col] = df[col].fillna("(Blank)").astype(str).str.strip().replace("", "(Blank)")

    df[PREMIUM_COL] = _to_numeric_amount(df[PREMIUM_COL])
    df.attrs["PREMIUM_TOTAL"] = float(df[PREMIUM_COL].sum())

    df = _add_year_month_label(df)
    if "YEARS" in df.columns and "MONTH" in df.columns:
        df["_DATE_KEY"] = [
            _as_month_key(y, m) for y, m in zip(df["YEARS"], df["MONTH"])
        ]
        df["PERIOD_TYPE"] = np.where(
            pd.to_numeric(pd.Series(df["_DATE_KEY"]), errors="coerce").fillna(0).astype(int) > AS_OF_DATE_KEY,
            "Early Warning",
            "Historical",
        )
    return df


def load_renewal_data(path: str = DEFAULT_RENEWAL_PATH, version: str = RENEWAL_DASHBOARD_VERSION) -> pd.DataFrame:
    """Load renewal parquet automatically from disk, without a manual upload option.

    If several Renewal*.parquet files exist, use the first candidate with a
    non-zero PREMIUM AMT total. This prevents the dashboard from accidentally
    using an older/empty-premium parquet when Streamlit is launched from a
    different working directory.
    """
    candidates = _candidate_renewal_paths(path)
    if not candidates:
        raise FileNotFoundError(
            f"Renewal parquet not found. Put the parquet beside this .py file or in the Streamlit working directory. Requested: {path}"
        )

    prepared: list[pd.DataFrame] = []
    errors: list[str] = []
    for candidate in candidates:
        try:
            candidate_df = _prepare_renewal_dataframe(pd.read_parquet(candidate), str(candidate))
            prepared.append(candidate_df)
            # Prefer a file whose premium total is clearly available.
            if float(candidate_df[PREMIUM_COL].abs().sum()) > 0:
                return candidate_df
        except Exception as e:
            errors.append(f"{candidate}: {e}")

    if prepared:
        # Return the best available dataframe, but the dashboard will show a clear diagnostic.
        return prepared[0]

    raise ValueError("Renewal parquet could not be loaded. " + " | ".join(errors[:3]))



def _safe_col(df: pd.DataFrame, col: str) -> bool:
    return col in df.columns and col not in EXCLUDED_COLUMNS and col not in {"IS_RENEWED"}


def available_filter_columns(df: pd.DataFrame) -> list[str]:
    preferred = [
        "PERIOD_TYPE", "YEAR_MONTH", "YEARS", "MONTH", "SOB", "COB", "LOB", "TOB",
        "INTERMEDIARY NAME", "INSURED NAME", "MARKETING NAME",
        "MARKETING_GROUP", "BRANCH", "RENEWAL_MKT", "RENEWAL_STATUS",
    ]
    cols = [c for c in preferred if _safe_col(df, c)]
    remaining = [c for c in df.columns if _safe_col(df, c) and c not in cols and c != POLICY_NO_COL]
    return cols + remaining


def available_group_columns(df: pd.DataFrame) -> list[str]:
    # YEAR_MONTH is intentionally kept out of the summary selector.
    # Default summary POV is YEARS with MONTH as the default additional column.
    # RENEWAL POLICY NO is intentionally excluded from grouping.
    preferred = [
        "YEARS", "MONTH", "PERIOD_TYPE", "SOB", "COB", "LOB", "TOB",
        "MARKETING_GROUP", "BRANCH", "MARKETING NAME",
        "INTERMEDIARY NAME", "INSURED NAME", "RENEWAL_MKT", "RENEWAL_STATUS",
    ]
    cols = [c for c in preferred if _safe_col(df, c) and c != POLICY_NO_COL]
    return cols


def default_group_column(df: pd.DataFrame) -> str | None:
    """Return a safe default grouping column.

    The filtered dataframe can legitimately be empty (for example when an
    active filter matches no rows). In that situation ``available_group_columns``
    may return an empty list, so indexing ``[0]`` would raise IndexError and
    crash the whole Renewal page, including the Export section.
    """
    if df is not None:
        if "YEARS" in df.columns:
            return "YEARS"
        if "MONTH" in df.columns:
            return "MONTH"

    available = available_group_columns(df) if df is not None else []
    return available[0] if available else None


DEFAULT_EXCLUDE_FILTERS = {"TOB": "MULTIFINANCE", "LOB": "TRAVEL INSURANCE"}
FILTER_MODES = ["Include Selected", "Exclude Selected"]


def _filter_all_options(df: pd.DataFrame, col: str) -> list[str]:
    if df is None or df.empty or col not in df.columns:
        return []
    return sorted(df[col].dropna().astype(str).unique().tolist())


def _selection_is_all(selected: list, options: list[str]) -> bool:
    selected_set = {str(v) for v in (selected or [])}
    option_set = {str(v) for v in (options or [])}
    return bool(option_set) and selected_set == option_set


def _normalize_filter_widget_selection(selected_key: str, all_options: list[str]) -> None:
    """Clear multiselect when every available option is selected.

    In this dashboard, no selected item means the filter is inactive / select all.
    This callback prevents the UI from showing hundreds of selected tags when
    the user accidentally chooses all values.
    """
    selected = st.session_state.get(selected_key, []) or []
    if _selection_is_all(selected, all_options):
        st.session_state[selected_key] = []


def _filter_is_active(mode: str, selected: list, options: list[str]) -> bool:
    if mode not in FILTER_MODES:
        return False
    if not selected:
        return False
    # Selecting all is the same as no filter / select all.
    if _selection_is_all(selected, options):
        return False
    return True


def apply_filters(df: pd.DataFrame, filter_state: dict) -> tuple[pd.DataFrame, dict]:
    out = df.copy()
    active = {}
    for col, spec in (filter_state or {}).items():
        if col not in out.columns or col in EXCLUDED_COLUMNS:
            continue

        mode = "Include Selected"
        vals = []
        if isinstance(spec, dict):
            mode = str(spec.get("mode") or mode)
            vals = list(spec.get("values") or [])
        else:
            vals = list(spec or [])

        all_options = _filter_all_options(df, col)
        if not _filter_is_active(mode, vals, all_options):
            continue

        compare_vals = [str(v) for v in vals]
        if mode == "Exclude Selected":
            out = out[~out[col].astype(str).isin(compare_vals)]
        else:
            out = out[out[col].astype(str).isin(compare_vals)]

        active[col] = {"mode": mode, "values": vals}
    return out, active

def compute_kpis(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {
            "Expired Policy": 0,
            "Renewed Policy": 0,
            "Not Renewed": 0,
            "Expired Premium": 0.0,
            "Renewed Premium": 0.0,
            "Not Renewed Premium": 0.0,
            "Case Ratio": 0.0,
            "Renewal Rate": 0.0,
        }

    df = _ensure_premium_column(df)

    expired = int(df[POLICY_NO_COL].nunique(dropna=True)) if POLICY_NO_COL in df.columns else int(len(df))
    renewed = int(df.loc[df["IS_RENEWED"], POLICY_NO_COL].nunique(dropna=True)) if POLICY_NO_COL in df.columns else int(df["IS_RENEWED"].sum())
    not_renewed = max(0, expired - renewed)

    premium = _safe_premium_series(df)
    expired_premium = float(premium.sum()) if len(premium) else 0.0
    renewed_premium = float(_safe_premium_series(df.loc[df["IS_RENEWED"]]).sum()) if "IS_RENEWED" in df.columns else 0.0
    not_renewed_premium = max(0.0, expired_premium - renewed_premium)

    case_ratio = renewed / expired * 100 if expired else 0.0
    renewal_rate = renewed_premium / expired_premium * 100 if expired_premium else 0.0
    return {
        "Expired Policy": expired,
        "Renewed Policy": renewed,
        "Not Renewed": not_renewed,
        "Expired Premium": expired_premium,
        "Renewed Premium": renewed_premium,
        "Not Renewed Premium": not_renewed_premium,
        "Case Ratio": case_ratio,
        "Renewal Rate": renewal_rate,
    }


def make_renewal_summary(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    df = _ensure_premium_column(df)
    if df is None or df.empty:
        return pd.DataFrame()

    group_cols = [c for c in group_cols if c in df.columns and c not in EXCLUDED_COLUMNS and c != "YEAR_MONTH"]
    if not group_cols:
        fallback_group = default_group_column(df)
        if fallback_group is None:
            # No valid grouping field exists. Return an overall one-row summary
            # instead of failing in groupby with a missing/None column.
            return pd.DataFrame([compute_kpis(df)])
        group_cols = [fallback_group]

    work_cols = group_cols + [POLICY_NO_COL, "IS_RENEWED", PREMIUM_COL]
    work = df[work_cols].copy()
    for col in group_cols:
        work[col] = work[col].fillna("(Blank)").astype(str)
    work[PREMIUM_COL] = _to_numeric_amount(work[PREMIUM_COL])

    # Case Ratio = renewed policy count / expired policy count.
    expired = work.groupby(group_cols, dropna=False, observed=True)[POLICY_NO_COL].nunique().rename("Expired Policy")
    renewed = work.loc[work["IS_RENEWED"]].groupby(group_cols, dropna=False, observed=True)[POLICY_NO_COL].nunique().rename("Renewed Policy")

    # Renewal Rate = renewed premium / expired premium.
    expired_premium = work.groupby(group_cols, dropna=False, observed=True)[PREMIUM_COL].sum().rename("Expired Premium")
    renewed_premium = work.loc[work["IS_RENEWED"]].groupby(group_cols, dropna=False, observed=True)[PREMIUM_COL].sum().rename("Renewed Premium")

    summary = pd.concat([expired, renewed, expired_premium, renewed_premium], axis=1).fillna(0).reset_index()
    summary["Expired Policy"] = summary["Expired Policy"].astype(int)
    summary["Renewed Policy"] = summary["Renewed Policy"].astype(int)
    summary["Not Renewed"] = summary["Expired Policy"] - summary["Renewed Policy"]
    summary["Not Renewed Premium"] = summary["Expired Premium"] - summary["Renewed Premium"]
    summary["Case Ratio"] = np.where(
        summary["Expired Policy"] > 0,
        summary["Renewed Policy"] / summary["Expired Policy"] * 100,
        0.0,
    )
    summary["Renewal Rate"] = np.where(
        summary["Expired Premium"] > 0,
        summary["Renewed Premium"] / summary["Expired Premium"] * 100,
        0.0,
    )

    ordered = group_cols + [
        "Expired Policy", "Renewed Policy", "Not Renewed", "Case Ratio",
        "Expired Premium", "Renewed Premium", "Not Renewed Premium", "Renewal Rate",
    ]
    summary = summary[ordered]
    summary = summary.sort_values(group_cols, ascending=True, kind="stable").reset_index(drop=True)
    return summary


# =========================================================
# STYLE
# =========================================================
def inject_renewal_css() -> None:
    st.markdown(
        """
        <style>
          .renewal-section-card{
            margin: 14px 0 8px 0;
            padding: 12px 15px;
            border-radius: 16px;
            background: #F8FAFC;
            border: 1px solid rgba(0,51,102,0.10);
            box-shadow: 0 8px 22px rgba(15,23,42,0.035);
          }
          .renewal-section-title{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size: 18px;
            font-weight: 850;
            line-height: 1.15;
            color: #003366;
            letter-spacing: -0.01em;
          }
          .renewal-kpi-card{
            box-sizing: border-box;
            height: 118px;
            padding: 14px 18px;
            border-radius: 22px;
            background: #FFFFFF;
            border: 1px solid rgba(0,51,102,0.12);
            box-shadow: 0 10px 26px rgba(15,23,42,0.055);
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            align-items: flex-start;
            gap: 6px;
            overflow: hidden;
          }
          .renewal-kpi-card.primary{
            background: linear-gradient(135deg, #003366 0%, #1F5A91 100%);
            color: #FFFFFF;
          }
          .renewal-kpi-card h4{
            margin: 0;
            font-size: 13px;
            line-height: 1.15;
            font-weight: 650;
            opacity: 0.92;
            color: inherit;
          }
          .renewal-kpi-card h2{
            margin: 0;
            font-size: 34px;
            line-height: 1.0;
            font-weight: 850;
            color: inherit;
            font-variant-numeric: tabular-nums;
          }
          .renewal-kpi-card:not(.primary) h4{ color:#64748B; }
          .renewal-kpi-card:not(.primary) h2{ color:#003366; }

          /* Renewal aggregation selector: keep buttons in one compact row, but constrain it to the app width and scroll horizontally when needed. */
          div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Renewal summary view"]){
            width: 100% !important;
            max-width: 100% !important;
            overflow: hidden !important;
            margin-top: 2px !important;
            margin-bottom: 4px !important;
          }
          div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Renewal summary view"]) > div{
            width: 100% !important;
            max-width: 100% !important;
            overflow-x: auto !important;
            overflow-y: hidden !important;
            padding: 0 0 6px 0 !important;
            scrollbar-width: thin !important;
            scrollbar-color: rgba(0,51,102,0.30) transparent !important;
          }
          div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Renewal summary view"]) > div::-webkit-scrollbar{
            height: 7px !important;
          }
          div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Renewal summary view"]) > div::-webkit-scrollbar-thumb{
            background: rgba(0,51,102,0.28) !important;
            border-radius: 999px !important;
          }
          div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Renewal summary view"]){
            display: block !important;
          }
          div[role="radiogroup"][aria-label="Renewal summary view"]{
            display: inline-flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            width: max-content !important;
            min-width: 100% !important;
            max-width: none !important;
            gap: 8px !important;
            border-bottom: 1px solid rgba(0,51,102,0.14) !important;
            padding: 4px 4px 7px 4px !important;
            box-sizing: border-box !important;
          }
          div[role="radiogroup"][aria-label="Renewal summary view"] label{
            flex: 0 0 auto !important;
            width: auto !important;
            max-width: 210px !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            padding: 8px 14px !important;
            margin: 0 !important;
            border-radius: 999px !important;
            border: 1px solid rgba(0,51,102,0.14) !important;
            background: linear-gradient(180deg, #FFFFFF 0%, #F4F7FB 100%) !important;
            color: #334155 !important;
            font-size: 12.2px !important;
            line-height: 1 !important;
            font-weight: 760 !important;
            box-shadow: 0 5px 14px rgba(15,23,42,0.045) !important;
          }
          div[role="radiogroup"][aria-label="Renewal summary view"] label p,
          div[role="radiogroup"][aria-label="Renewal summary view"] label span,
          div[role="radiogroup"][aria-label="Renewal summary view"] label div{
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            white-space: nowrap !important;
            max-width: 100% !important;
          }
          div[role="radiogroup"][aria-label="Renewal summary view"] label:has(input:checked){
            background: linear-gradient(135deg, #003366 0%, #1F5A91 100%) !important;
            color: #FFFFFF !important;
            border-color: rgba(0,51,102,0.72) !important;
          }
          div[role="radiogroup"][aria-label="Renewal summary view"] label:has(input:checked) *{
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
          }

          .renewal-ts-spacer{
            height: 24px;
          }
          .renewal-ts-card{
            margin: 12px 0 10px 0;
            padding: 14px 16px 12px 16px;
            border-radius: 22px;
            background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
            border: 1px solid rgba(0,51,102,0.12);
            box-shadow: 0 12px 30px rgba(15,23,42,0.055);
          }
          .renewal-ts-title{
            font-size: 16px;
            font-weight: 850;
            color: #003366;
            letter-spacing: -0.01em;
            margin-bottom: 2px;
          }
          .renewal-ts-subtitle{
            font-size: 12px;
            color: #64748B;
            font-weight: 620;
            margin-bottom: 8px;
          }
          .renewal-ts-pill{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 7px 11px;
            border-radius: 999px;
            background: #EEF5FB;
            color: #003366;
            font-size: 12px;
            font-weight: 820;
            border: 1px solid rgba(0,51,102,0.10);
          }
          div[role="radiogroup"][aria-label="Renewal summary view"] input,
          div[role="radiogroup"][aria-label="Renewal summary view"] svg{
            display: none !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str) -> None:
    st.markdown(
        f"<div class='renewal-section-card'><div class='renewal-section-title'>{html.escape(title)}</div></div>",
        unsafe_allow_html=True,
    )


def render_kpis(kpis: dict) -> None:
    """Dashboard KPI cards for the two POV metrics: Case Ratio and Renewal Rate."""
    c1, c2, c3, c4 = st.columns(4)

    def card(title, value, primary=False):
        cls = "renewal-kpi-card primary" if primary else "renewal-kpi-card"
        st.markdown(
            f"<div class='{cls}'><h4>{html.escape(title)}</h4><h2>{value}</h2></div>",
            unsafe_allow_html=True,
        )

    with c1:
        card("Expired Policy", f"{int(kpis.get('Expired Policy', 0)):,}".replace(",", "."), primary=True)
    with c2:
        card("Renewed Policy", f"{int(kpis.get('Renewed Policy', 0)):,}".replace(",", "."))
    with c3:
        card("Case Ratio", f"{float(kpis.get('Case Ratio', 0.0) or 0.0):.1f}%")
    with c4:
        card("Renewal Rate", f"{float(kpis.get('Renewal Rate', 0.0) or 0.0):.1f}%")


# =========================================================
# EXECUTIVE TIME SERIES
# =========================================================
def _month_short_name(month_num: int) -> str:
    names = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun",
        7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des",
    }
    return names.get(int(month_num), str(month_num))


@st.cache_data(show_spinner=False, ttl=900, max_entries=64)
def cached_renewal_time_series(df: pd.DataFrame, branch_value: str | None = None, granularity: str = "Monthly") -> pd.DataFrame:
    if df is None or df.empty or "YEARS" not in df.columns or "MONTH" not in df.columns:
        return pd.DataFrame()

    work = _ensure_premium_column(df)
    if branch_value is not None and "BRANCH" in work.columns:
        work = work[work["BRANCH"].astype(str) == str(branch_value)].copy()
    if work.empty:
        return pd.DataFrame()

    work["_year"] = pd.to_numeric(work["YEARS"], errors="coerce")
    work["_month"] = work["MONTH"].apply(_month_to_num)
    work = work[work["_year"].notna() & work["_month"].notna()].copy()
    if work.empty:
        return pd.DataFrame()

    work["_year"] = work["_year"].astype(int)
    work["_month"] = work["_month"].astype(int)
    work[PREMIUM_COL] = _to_numeric_amount(work[PREMIUM_COL])

    granularity = str(granularity or "Monthly").strip().lower()
    if granularity.startswith("year"):
        group_cols = ["_year"]
    else:
        group_cols = ["_year", "_month"]

    expired = work.groupby(group_cols, observed=True)[POLICY_NO_COL].nunique().rename("Expired Policy")
    renewed = work.loc[work["IS_RENEWED"]].groupby(group_cols, observed=True)[POLICY_NO_COL].nunique().rename("Renewed Policy")
    expired_premium = work.groupby(group_cols, observed=True)[PREMIUM_COL].sum().rename("Expired Premium")
    renewed_premium = work.loc[work["IS_RENEWED"]].groupby(group_cols, observed=True)[PREMIUM_COL].sum().rename("Renewed Premium")

    out = pd.concat([expired, renewed, expired_premium, renewed_premium], axis=1).fillna(0).reset_index()
    out["Expired Policy"] = out["Expired Policy"].astype(int)
    out["Renewed Policy"] = out["Renewed Policy"].astype(int)
    out["Case Ratio"] = np.where(out["Expired Policy"] > 0, out["Renewed Policy"] / out["Expired Policy"] * 100, 0.0)
    out["Renewal Rate"] = np.where(out["Expired Premium"] > 0, out["Renewed Premium"] / out["Expired Premium"] * 100, 0.0)

    if group_cols == ["_year"]:
        # For yearly aggregation, mark the year as future when the full-year key is beyond as_of_date.
        out["_date_key"] = out["_year"] * 100 + 12
        out["Period"] = out["_year"].astype(int).astype(str)
    else:
        out["_date_key"] = out["_year"] * 100 + out["_month"]
        out["Period"] = out.apply(lambda r: f"{_month_short_name(int(r['_month']))} {int(r['_year'])}", axis=1)

    out["Is Future"] = out["_date_key"] > AS_OF_DATE_KEY
    out["Period Type"] = np.where(out["Is Future"], "Early Warning", "Historical")
    out = out.sort_values("_date_key", kind="stable").reset_index(drop=True)
    return out[[
        "Period", "Expired Policy", "Renewed Policy", "Expired Premium", "Renewed Premium",
        "Case Ratio", "Renewal Rate", "Period Type", "Is Future", "_date_key"
    ]]

def _renewal_ts_contexts(df: pd.DataFrame) -> list[tuple[str, str | None]]:
    contexts = [("All", None)]
    if df is not None and not df.empty and "BRANCH" in df.columns:
        branches = sorted([b for b in df["BRANCH"].dropna().astype(str).unique().tolist() if b and b != "(Blank)"])
        contexts.extend([(b, b) for b in branches])
    return contexts


def _svg_polyline(points: list[tuple[float, float]]) -> str:
    return " ".join([f"{x:.2f},{y:.2f}" for x, y in points])


def _split_line_points(points: list[tuple[float, float]], future_flags: list[bool]) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    if not points:
        return [], []
    first_future_idx = next((i for i, flag in enumerate(future_flags) if flag), None)
    if first_future_idx is None:
        return points, []
    if first_future_idx == 0:
        return [], points
    # Include the last historical point in the dashed line so the transition is continuous.
    return points[:first_future_idx], points[first_future_idx - 1:]


def render_renewal_timeseries_chart(ts_df: pd.DataFrame, scope_label: str) -> None:
    if ts_df is None or ts_df.empty:
        st.info("No renewal trend data available for this view. Pastikan kolom year/month dan premium terbaca.")
        return

    case_ratios = pd.to_numeric(ts_df["Case Ratio"], errors="coerce").fillna(0).clip(lower=0, upper=100).tolist()
    renewal_rates = pd.to_numeric(ts_df["Renewal Rate"], errors="coerce").fillna(0).clip(lower=0, upper=100).tolist()
    labels = ts_df["Period"].astype(str).tolist()
    future_flags = ts_df["Is Future"].fillna(False).astype(bool).tolist()
    expired = pd.to_numeric(ts_df["Expired Policy"], errors="coerce").fillna(0).astype(int).tolist()
    renewed = pd.to_numeric(ts_df["Renewed Policy"], errors="coerce").fillna(0).astype(int).tolist()
    expired_prem = pd.to_numeric(ts_df["Expired Premium"], errors="coerce").fillna(0).tolist()
    renewed_prem = pd.to_numeric(ts_df["Renewed Premium"], errors="coerce").fillna(0).tolist()

    w, h = 920, 390
    left, right, top, bottom = 70, 36, 76, 72
    plot_w, plot_h = w - left - right, h - top - bottom
    n = len(case_ratios)
    xs = [left + (plot_w * i / max(1, n - 1)) for i in range(n)]
    case_ys = [top + plot_h - (plot_h * r / 100.0) for r in case_ratios]
    rate_ys = [top + plot_h - (plot_h * r / 100.0) for r in renewal_rates]
    case_points = list(zip(xs, case_ys))
    rate_points = list(zip(xs, rate_ys))
    case_solid, case_dash = _split_line_points(case_points, future_flags)
    rate_solid, rate_dash = _split_line_points(rate_points, future_flags)

    last_hist_idx = max([i for i, flag in enumerate(future_flags) if not flag], default=None)
    latest_case = case_ratios[last_hist_idx] if last_hist_idx is not None else case_ratios[-1]
    latest_rate = renewal_rates[last_hist_idx] if last_hist_idx is not None else renewal_rates[-1]

    label_step = max(1, int(np.ceil(n / 9)))
    x_labels = []
    for i, (x, label) in enumerate(zip(xs, labels)):
        if i % label_step == 0 or i == n - 1 or (future_flags[i] and (i == 0 or not future_flags[i-1])):
            x_labels.append(f"<text x='{x:.1f}' y='{h-30}' text-anchor='middle' class='axis-label'>{html.escape(label)}</text>")

    y_guides = []
    for val in [0, 25, 50, 75, 100]:
        y = top + plot_h - (plot_h * val / 100.0)
        y_guides.append(f"<line x1='{left}' x2='{w-right}' y1='{y:.1f}' y2='{y:.1f}' class='guide'/>")
        y_guides.append(f"<text x='{left-16}' y='{y+4:.1f}' text-anchor='end' class='axis-label'>{val}%</text>")

    asof_marker = ""
    first_future_idx = next((i for i, flag in enumerate(future_flags) if flag), None)
    if first_future_idx is not None:
        if first_future_idx == 0:
            marker_x = xs[0]
        else:
            marker_x = (xs[first_future_idx - 1] + xs[first_future_idx]) / 2
        asof_marker = f"""
        <line x1='{marker_x:.1f}' x2='{marker_x:.1f}' y1='{top}' y2='{top + plot_h}' class='asof-line'/>
        <text x='{marker_x + 8:.1f}' y='{top + 14}' class='asof-label'>Early warning</text>
        """

    dots = []
    for i, (x, cy, ry, cr, rr, exp, ren, ep, rp, is_future) in enumerate(zip(xs, case_ys, rate_ys, case_ratios, renewal_rates, expired, renewed, expired_prem, renewed_prem, future_flags)):
        dot_class = "dot future-dot" if is_future else "dot"
        dots.append(
            f"<circle cx='{x:.1f}' cy='{cy:.1f}' r='4.2' class='{dot_class} case-dot'>"
            f"<title>{labels[i]} | Case Ratio {cr:.1f}% | Renewed {ren:,} / Expired {exp:,}</title></circle>".replace(',', '.')
        )
        dots.append(
            f"<circle cx='{x:.1f}' cy='{ry:.1f}' r='4.2' class='{dot_class} rate-dot'>"
            f"<title>{labels[i]} | Renewal Rate {rr:.1f}% | Renewed Premium {_format_amount(rp)} / Expired Premium {_format_amount(ep)}</title></circle>"
        )

    def poly(points, cls):
        return f"<polyline points='{_svg_polyline(points)}' class='{cls}'/>" if len(points) >= 2 else ""

    svg = f"""
    <svg viewBox="0 0 {w} {h}" width="100%" height="390" role="img" aria-label="Case Ratio and Renewal Rate trend">
      <defs>
        <filter id="softShadow2" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="5" stdDeviation="5" flood-color="#0F172A" flood-opacity="0.10"/>
        </filter>
      </defs>
      <style>
        .title {{ font: 800 19px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; fill:#003366; letter-spacing:-0.01em; }}
        .subtitle {{ font: 650 12px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; fill:#64748B; }}
        .metric {{ font: 850 24px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; fill:#003366; }}
        .metric-alt {{ fill:#9B6A2F; }}
        .metric-label {{ font: 700 11px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; fill:#64748B; }}
        .axis-label {{ font: 650 10.5px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; fill:#64748B; }}
        .guide {{ stroke:#E2E8F0; stroke-width:1; stroke-dasharray:2 7; }}
        .case-line {{ fill:none; stroke:#003366; stroke-width:3.4; stroke-linecap:round; stroke-linejoin:round; filter:url(#softShadow2); }}
        .rate-line {{ fill:none; stroke:#C59A55; stroke-width:3.4; stroke-linecap:round; stroke-linejoin:round; filter:url(#softShadow2); }}
        .future-line {{ stroke-dasharray:8 8; opacity:0.95; }}
        .dot {{ fill:#FFFFFF; stroke-width:2.5; }}
        .case-dot {{ stroke:#003366; }}
        .rate-dot {{ stroke:#C59A55; }}
        .future-dot {{ stroke-dasharray:3 3; }}
        .target {{ stroke:#CBD5E1; stroke-width:1.6; stroke-dasharray:6 7; }}
        .asof-line {{ stroke:#94A3B8; stroke-width:1.5; stroke-dasharray:5 6; }}
        .asof-label {{ font: 720 10.5px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; fill:#64748B; }}
        .legend-text {{ font: 740 11px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; fill:#334155; }}
      </style>
      <rect x="0" y="0" width="{w}" height="{h}" rx="22" fill="#FFFFFF"/>
      <text x="24" y="30" class="title">Case Ratio &amp; Renewal Rate Trend</text>
      <text x="24" y="50" class="subtitle">{html.escape(scope_label)}</text>

      <text x="{w-235}" y="30" class="metric">{latest_case:.1f}%</text>
      <text x="{w-235}" y="49" class="metric-label">Case Ratio</text>
      <text x="{w-112}" y="30" class="metric metric-alt">{latest_rate:.1f}%</text>
      <text x="{w-112}" y="49" class="metric-label">Renewal Rate</text>

      <circle cx="{left}" cy="66" r="4.5" class="dot case-dot"/><text x="{left+12}" y="70" class="legend-text">Case Ratio</text>
      <circle cx="{left+125}" cy="66" r="4.5" class="dot rate-dot"/><text x="{left+137}" y="70" class="legend-text">Renewal Rate</text>
      <line x1="{left+270}" x2="{left+306}" y1="66" y2="66" class="case-line future-line"/><text x="{left+314}" y="70" class="legend-text">Future period</text>

      {''.join(y_guides)}
      <line x1="{left}" x2="{w-right}" y1="{top + plot_h - (plot_h * 50 / 100):.1f}" y2="{top + plot_h - (plot_h * 50 / 100):.1f}" class="target"/>
      {asof_marker}
      {poly(case_solid, 'case-line')}
      {poly(case_dash, 'case-line future-line')}
      {poly(rate_solid, 'rate-line')}
      {poly(rate_dash, 'rate-line future-line')}
      {''.join(dots)}
      {''.join(x_labels)}
    </svg>
    """
    card_html = f"""
    <div class='renewal-ts-card'>
      {svg}
    </div>
    """
    src = "data:text/html;base64," + base64.b64encode(card_html.encode("utf-8")).decode("ascii")
    components.iframe(src, height=420, scrolling=False)


# =========================================================
# PREMIUM HTML TABLE WITH CLIENT-SIDE SORT
# =========================================================
def render_html_table(df: pd.DataFrame, table_key: str = "renewal_summary", height: int | None = None) -> None:
    if df is None or df.empty:
        st.info("No data on this filter.")
        return

    display_df = df.copy().reset_index(drop=True)
    raw_df = display_df.copy()

    ratio_cols = [c for c in display_df.columns if "Ratio" in c or "Rate" in c]
    count_cols = ["Expired Policy", "Renewed Policy", "Not Renewed"]
    premium_cols = ["Expired Premium", "Renewed Premium", "Not Renewed Premium", PREMIUM_COL]
    group_cols = [c for c in display_df.columns if c not in ratio_cols + count_cols + premium_cols]

    for col in count_cols:
        if col in display_df.columns:
            display_df[col] = pd.to_numeric(display_df[col], errors="coerce").fillna(0).astype(int).map(lambda x: f"{x:,}".replace(",", "."))
    for col in ratio_cols:
        if col in display_df.columns:
            display_df[col] = pd.to_numeric(display_df[col], errors="coerce").fillna(0).map(lambda x: f"{x:.1f}%")
    for col in premium_cols:
        if col in display_df.columns:
            display_df[col] = pd.to_numeric(display_df[col], errors="coerce").fillna(0).map(_format_amount)
    for col in group_cols:
        display_df[col] = display_df[col].fillna("(Blank)").astype(str)

    def width_for(col):
        if col in group_cols:
            if col in ["YEARS", "MONTH", "SOB", "COB", "LOB", "TOB", "BRANCH", "MARKETING_GROUP", "RENEWAL_STATUS"]:
                return 150
            return 235
        if col in ratio_cols:
            return 145
        if col in premium_cols:
            return 175
        return 140

    widths = {c: width_for(c) for c in display_df.columns}
    min_table_width = sum(widths.values())
    table_height = height or max(240, min(520, 96 + 35 * len(display_df)))
    dom_id = "renewal_table_" + hashlib.sha1((table_key + str(len(display_df)) + "|".join(display_df.columns)).encode()).hexdigest()[:10]

    colgroup = "".join([f"<col style='width:{widths[c]}px; min-width:{widths[c]}px;'>" for c in display_df.columns])
    options = "<option value=''>None</option>" + "".join(
        [f"<option value='{i}'>{html.escape(_premium_display_label(c).replace('_', ' '))}</option>" for i, c in enumerate(display_df.columns)]
    )

    sticky_left = {}
    running_left = 0
    for c in display_df.columns:
        if c in group_cols[:2]:
            sticky_left[c] = running_left
            running_left += widths[c]
        else:
            break

    headers = []
    for c in display_df.columns:
        cls = "sticky-col" if c in sticky_left else ""
        style = f"left:{sticky_left[c]}px;" if c in sticky_left else ""
        headers.append(f"<th class='{cls}' style='{style}'>{html.escape(_premium_display_label(c).replace('_', ' '))}</th>")

    rows = []
    for r in range(len(display_df)):
        cells = []
        for c in display_df.columns:
            raw = raw_df.iloc[r][c]
            sort_num = pd.to_numeric(pd.Series([raw]), errors="coerce").iloc[0]
            if pd.notna(sort_num):
                sort_value = str(float(sort_num))
                sort_type = "num"
            else:
                sort_value = html.escape(str(raw).lower())
                sort_type = "text"

            cls = ["text-cell" if c in group_cols else "num-cell"]
            style = ""
            if c in sticky_left:
                cls.append("sticky-col")
                style = f"left:{sticky_left[c]}px;"
            if c in {"Case Ratio", "Renewal Rate", "Renewal Ratio"} and pd.to_numeric(pd.Series([raw]), errors="coerce").fillna(0).iloc[0] < 50:
                cls.append("ratio-warning")
            if c in {"Case Ratio", "Renewal Rate", "Renewal Ratio"} and pd.to_numeric(pd.Series([raw]), errors="coerce").fillna(0).iloc[0] >= 70:
                cls.append("ratio-good")

            cells.append(
                f"<td class='{' '.join(cls)}' style='{style}' data-sort='{sort_value}' data-sort-type='{sort_type}'>{html.escape(str(display_df.iloc[r][c]))}</td>"
            )
        rows.append(f"<tr>{''.join(cells)}</tr>")

    table_html = f"""
    <style>
      html, body {{ margin:0; background:transparent; }}
      .renewal-table-controls {{
        display:flex; gap:10px; align-items:center; margin:0 0 10px 0;
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
      }}
      .renewal-table-controls label {{ font-size:11.5px; font-weight:700; color:#475569; }}
      .renewal-table-controls select, .renewal-table-controls button {{
        height:34px; border:1px solid rgba(0,51,102,0.16); border-radius:10px;
        background:#FFFFFF; color:#1F2937; font-size:11.5px; padding:0 10px; outline:none;
      }}
      .renewal-table-controls button {{ cursor:pointer; font-weight:700; color:#003366; }}
      .renewal-table-wrap {{
        width:100%; max-height:{table_height}px; overflow:auto;
        border:1px solid rgba(0,51,102,0.12); border-radius:16px; background:#FFFFFF;
        box-shadow:0 10px 28px rgba(15,23,42,0.06);
      }}
      .renewal-table {{
        border-collapse:separate; border-spacing:0; table-layout:fixed;
        width:{min_table_width}px; min-width:{min_table_width}px;
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Arial,sans-serif;
        color:#334155; -webkit-font-smoothing:antialiased;
      }}
      .renewal-table thead th {{
        position:sticky; top:0; z-index:30; background:#003366; color:#FFFFFF;
        text-align:center; vertical-align:middle; font-size:10.8px; line-height:1.18;
        font-weight:780; height:46px; padding:8px 8px;
        border-right:1px solid rgba(255,255,255,0.18); border-bottom:1px solid rgba(0,0,0,0.10);
        white-space:normal; box-sizing:border-box;
      }}
      .renewal-table tbody td {{
        font-size:11.3px; line-height:1.28; height:34px; padding:8px 10px;
        border-right:1px solid rgba(15,23,42,0.045); border-bottom:1px solid rgba(15,23,42,0.055);
        background:#FFFFFF; color:#334155; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
        box-sizing:border-box; font-weight:620;
      }}
      .renewal-table tbody tr:nth-child(odd) td {{ background:#FFFFFF; }}
      .renewal-table tbody tr:nth-child(even) td {{ background:#F1F5F9; }}
      .renewal-table tbody tr:hover td {{ background:#E6F0FA; }}
      .renewal-table .text-cell {{ text-align:left; font-weight:680; color:#1E3A5F; }}
      .renewal-table .num-cell {{ text-align:right; font-variant-numeric:tabular-nums; }}
      .renewal-table .sticky-col {{ position:sticky; z-index:20; box-shadow:2px 0 0 rgba(0,51,102,0.08); }}
      .renewal-table thead th.sticky-col {{ z-index:40; background:#002B57; }}
      .renewal-table tbody tr:nth-child(odd) td.sticky-col {{ background:#FAFCFF; }}
      .renewal-table tbody tr:nth-child(even) td.sticky-col {{ background:#EAF1F8; }}
      .renewal-table tbody tr:hover td.sticky-col {{ background:#E6F0FA; }}
      .renewal-table tbody td.ratio-warning {{ background:#FFF3D6 !important; color:#7C4A03; font-weight:780; }}
      .renewal-table tbody td.ratio-good {{ background:#E8F7EF !important; color:#166534; font-weight:780; }}
    </style>
    <div class="renewal-table-controls">
      <label for="sort_by_{dom_id}">Sort by</label>
      <select id="sort_by_{dom_id}">{options}</select>
      <select id="sort_order_{dom_id}"><option value="desc">Descending</option><option value="asc">Ascending</option></select>
      <button type="button" id="reset_{dom_id}">Reset</button>
    </div>
    <div class="renewal-table-wrap">
      <table class="renewal-table" id="{dom_id}">
        <colgroup>{colgroup}</colgroup>
        <thead><tr>{''.join(headers)}</tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    <script>
      (function(){{
        const table=document.getElementById("{dom_id}");
        const sortBy=document.getElementById("sort_by_{dom_id}");
        const sortOrder=document.getElementById("sort_order_{dom_id}");
        const reset=document.getElementById("reset_{dom_id}");
        if(!table||!sortBy||!sortOrder||!reset) return;
        const tbody=table.querySelector("tbody");
        const original=Array.from(tbody.querySelectorAll("tr"));
        function applySort(){{
          const colIndex=sortBy.value;
          if(colIndex===""){{ tbody.replaceChildren(...original); return; }}
          const idx=parseInt(colIndex,10);
          const asc=sortOrder.value==="asc";
          const rows=Array.from(tbody.querySelectorAll("tr"));
          rows.sort(function(a,b){{
            const ac=a.children[idx], bc=b.children[idx];
            const at=ac.getAttribute("data-sort-type"), bt=bc.getAttribute("data-sort-type");
            const av=ac.getAttribute("data-sort")||"", bv=bc.getAttribute("data-sort")||"";
            let result=0;
            if(at==="num"&&bt==="num") result=(parseFloat(av)||0)-(parseFloat(bv)||0);
            else result=av.localeCompare(bv, undefined, {{numeric:true, sensitivity:"base"}});
            return asc ? result : -result;
          }});
          tbody.replaceChildren(...rows);
        }}
        sortBy.addEventListener("change", applySort);
        sortOrder.addEventListener("change", applySort);
        reset.addEventListener("click", function(){{ sortBy.value=""; sortOrder.value="desc"; tbody.replaceChildren(...original); }});
      }})();
    </script>
    """

    src = "data:text/html;base64," + base64.b64encode(table_html.encode("utf-8")).decode("ascii")
    components.iframe(src, height=table_height + 46, scrolling=False)
    if any(c in premium_cols for c in df.columns):
        st.caption(PREMIUM_DISPLAY_NOTE)


# =========================================================
# EXPORTS
# =========================================================
def export_renewal_excel(
    summary_df: pd.DataFrame,
    detail_df: pd.DataFrame,
    active_filters: dict,
    period_text: str,
    username: str,
    doc_id: str,
) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        workbook = writer.book

        # Slightly larger and cleaner export typography.
        header_fmt = workbook.add_format({
            "bold": True,
            "bg_color": "#003366",
            "font_color": "white",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
            "font_size": 11,
        })
        count_fmt = workbook.add_format({"num_format": "#,##0", "align": "right", "valign": "vcenter", "font_size": 11})
        pct_fmt = workbook.add_format({"num_format": "0.0%", "align": "right", "valign": "vcenter", "font_size": 11})
        text_fmt = workbook.add_format({"valign": "vcenter", "font_size": 11})
        note_fmt = workbook.add_format({"italic": True, "font_color": "#555555", "font_size": 10})
        zebra_fmt = workbook.add_format({"bg_color": "#F1F5F9"})
        ratio_red_fmt = workbook.add_format({"bg_color": "#FCE7E7", "font_color": "#9F1239"})
        ratio_yellow_fmt = workbook.add_format({"bg_color": "#FFF3D6", "font_color": "#7C4A03"})
        ratio_green_fmt = workbook.add_format({"bg_color": "#E8F7EF", "font_color": "#166534"})

        summary_export = summary_df.copy()
        for pct_col in ["Case Ratio", "Renewal Rate", "Renewal Ratio"]:
            if pct_col in summary_export.columns:
                summary_export[pct_col] = summary_export[pct_col] / 100

        premium_cols = ["Expired Premium", "Renewed Premium", "Not Renewed Premium"]
        premium_rename = {}
        for prem_col in premium_cols:
            if prem_col in summary_export.columns:
                summary_export[prem_col] = pd.to_numeric(summary_export[prem_col], errors="coerce").fillna(0) / PREMIUM_DISPLAY_DIVISOR
                premium_rename[prem_col] = _premium_display_label(prem_col)
        if premium_rename:
            summary_export = summary_export.rename(columns=premium_rename)

        main_sheet = "Renewal Summary"
        ws = workbook.add_worksheet(main_sheet)
        writer.sheets[main_sheet] = ws
        meta_end_row = _write_excel_metadata(ws, active_filters, period_text, doc_id, username, start_row=0)
        ws.write(meta_end_row, 0, "Case Ratio is based on policy count. Renewal Rate is based on raw PREMIUM AMT. Premium columns marked with * are in juta. Renewed is counted only when RENEWAL POLICY NO length > 10.", note_fmt)
        startrow = meta_end_row + 2
        summary_export.to_excel(writer, index=False, sheet_name=main_sheet, startrow=startrow)

        for c, col in enumerate(summary_export.columns):
            ws.write(startrow, c, col, header_fmt)
            if col in ["Case Ratio", "Renewal Rate", "Renewal Ratio"]:
                ws.set_column(c, c, 17, pct_fmt)
            elif col in ["Expired Policy", "Renewed Policy", "Not Renewed"] or "Premium" in str(col):
                ws.set_column(c, c, 18, count_fmt)
            else:
                # Grouping columns stay left-aligned; numeric columns are right-aligned.
                fmt = count_fmt if _is_export_numeric_col(col, summary_export[col]) else text_fmt
                ws.set_column(c, c, 24, fmt)

        if len(summary_export.columns) > 0:
            ws.conditional_format(
                startrow + 1, 0,
                startrow + len(summary_export), len(summary_export.columns) - 1,
                {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": zebra_fmt},
            )
            for pct_name in ["Case Ratio", "Renewal Rate"]:
                if pct_name in summary_export.columns and len(summary_export) > 0:
                    ratio_col = summary_export.columns.get_loc(pct_name)
                    ws.conditional_format(startrow + 1, ratio_col, startrow + len(summary_export), ratio_col, {
                        "type": "cell", "criteria": "<=", "value": 0.25, "format": ratio_red_fmt,
                    })
                    ws.conditional_format(startrow + 1, ratio_col, startrow + len(summary_export), ratio_col, {
                        "type": "cell", "criteria": "between", "minimum": 0.2500001, "maximum": 0.50, "format": ratio_yellow_fmt,
                    })
                    ws.conditional_format(startrow + 1, ratio_col, startrow + len(summary_export), ratio_col, {
                        "type": "cell", "criteria": ">", "value": 0.50, "format": ratio_green_fmt,
                    })
            ws.autofilter(startrow, 0, startrow + len(summary_export), len(summary_export.columns) - 1)
            ws.freeze_panes(startrow + 1, 0)

        detail_export = detail_df.copy()
        if PREMIUM_COL in detail_export.columns:
            detail_export[PREMIUM_COL] = pd.to_numeric(detail_export[PREMIUM_COL], errors="coerce").fillna(0) / PREMIUM_DISPLAY_DIVISOR
            detail_export = detail_export.rename(columns={PREMIUM_COL: _premium_display_label(PREMIUM_COL)})
        detail_sheet = "Detail Data"
        ws2 = workbook.add_worksheet(detail_sheet)
        writer.sheets[detail_sheet] = ws2
        detail_meta_end = _write_excel_metadata(ws2, active_filters, period_text, doc_id, username, start_row=0)
        ws2.write(detail_meta_end, 0, "Detail data follows the active filters. Premium columns marked with * are in juta. RENEWAL POLICY NO is used only to determine renewal status, not as a filter or grouping.", note_fmt)
        detail_startrow = detail_meta_end + 2
        detail_export.to_excel(writer, index=False, sheet_name=detail_sheet, startrow=detail_startrow)

        for c, col in enumerate(detail_export.columns):
            ws2.write(detail_startrow, c, col, header_fmt)
            if "Ratio" in str(col) or "Rate" in str(col):
                ws2.set_column(c, c, 17, pct_fmt)
            elif _is_export_numeric_col(col, detail_export[col]):
                ws2.set_column(c, c, 18, count_fmt)
            else:
                ws2.set_column(c, c, 24, text_fmt)

        if len(detail_export.columns) > 0:
            ws2.conditional_format(
                detail_startrow + 1, 0,
                detail_startrow + len(detail_export), len(detail_export.columns) - 1,
                {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": zebra_fmt},
            )
            # Apply the same renewal-ratio banding to any ratio column in detail if present.
            for ratio_name in [c for c in detail_export.columns if "Ratio" in str(c) or "Rate" in str(c)]:
                ratio_col = detail_export.columns.get_loc(ratio_name)
                ws2.conditional_format(detail_startrow + 1, ratio_col, detail_startrow + len(detail_export), ratio_col, {
                    "type": "cell", "criteria": "<=", "value": 0.25, "format": ratio_red_fmt,
                })
                ws2.conditional_format(detail_startrow + 1, ratio_col, detail_startrow + len(detail_export), ratio_col, {
                    "type": "cell", "criteria": "between", "minimum": 0.2500001, "maximum": 0.50, "format": ratio_yellow_fmt,
                })
                ws2.conditional_format(detail_startrow + 1, ratio_col, detail_startrow + len(detail_export), ratio_col, {
                    "type": "cell", "criteria": ">", "value": 0.50, "format": ratio_green_fmt,
                })
            ws2.autofilter(detail_startrow, 0, detail_startrow + len(detail_export), len(detail_export.columns) - 1)
            ws2.freeze_panes(detail_startrow + 1, 0)

    return buffer.getvalue()


def export_renewal_pdf(
    summary_df: pd.DataFrame,
    kpis: dict,
    active_filters: dict,
    period_text: str,
    username: str,
    doc_id: str,
    title: str = "MNC Insurance Renewal Dashboard Report",
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=0.8 * cm, rightMargin=0.8 * cm, topMargin=0.8 * cm, bottomMargin=0.8 * cm)
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#003366")
    soft_grid = colors.HexColor("#AEB7C2")

    title_style = ParagraphStyle("RenewalTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=18, leading=21, alignment=1, textColor=colors.black)
    subtitle_style = ParagraphStyle("RenewalSub", parent=styles["Normal"], fontSize=9.5, leading=11.2, alignment=1, textColor=colors.HexColor("#555555"))
    section_style = ParagraphStyle("RenewalSection", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=12.5, textColor=colors.black, spaceBefore=4, spaceAfter=5)
    meta_style = ParagraphStyle("RenewalMeta", parent=styles["Normal"], fontName="Helvetica", fontSize=9.6, leading=10.2, alignment=0, textColor=colors.HexColor("#333333"))
    cell_style = ParagraphStyle("RenewalCell", parent=styles["Normal"], fontSize=9, leading=9.8)
    cell_style_right = ParagraphStyle("RenewalCellRight", parent=cell_style, alignment=2)
    cell_style_left = ParagraphStyle("RenewalCellLeft", parent=cell_style, alignment=0)
    header_style = ParagraphStyle("RenewalHeader", parent=cell_style, fontName="Helvetica-Bold", alignment=1, textColor=colors.white, fontSize=8.5, leading=10.0)

    elements = [Paragraph(title, title_style)]
    elements.append(Paragraph("Prepared from SuperApp Actuary Renewal Dashboard", subtitle_style))
    elements.append(Spacer(1, 0.35 * cm))

    elements.append(Paragraph("Renewal Report for:", section_style))
    for line in _active_filter_lines(active_filters):
        elements.append(Paragraph(html.escape(line), meta_style))
    elements.append(Paragraph(f"Period: {html.escape(period_text or '-')}", meta_style))
    elements.append(Paragraph(f"Document ID: {html.escape(_sanitize_doc_id(doc_id))}", meta_style))
    elements.append(Paragraph(f"Downloaded by: {html.escape(str(username or '-'))}", meta_style))
    elements.append(Spacer(1, 0.25 * cm))

    # PDF KPI strip: intentionally more noticeable, like Risk Profile export.
    kpi_header_style = ParagraphStyle(
        "RenewalKPIHeader",
        parent=styles["Normal"],
        alignment=1,
        textColor=colors.white,
        fontName="Helvetica-Bold",
        fontSize=9.4,
        leading=11.0,
    )
    kpi_value_style = ParagraphStyle(
        "RenewalKPIValue",
        parent=styles["Normal"],
        alignment=1,
        textColor=navy,
        fontName="Helvetica-Bold",
        fontSize=14.0,
        leading=15.8,
        allowMarkup=True,
    )
    case_val = float(kpis.get("Case Ratio", 0.0) or 0.0)
    rate_val = float(kpis.get("Renewal Rate", 0.0) or 0.0)
    case_dot = _renewal_ratio_dot_color(case_val)
    rate_dot = _renewal_ratio_dot_color(rate_val)

    kpi_headers = [Paragraph(x, kpi_header_style) for x in ["EXPIRED POLICY", "RENEWED POLICY", "CASE RATIO", "RENEWAL RATE"]]
    kpi_values = [
        Paragraph(f"{int(kpis['Expired Policy']):,}".replace(",", "."), kpi_value_style),
        Paragraph(f"{int(kpis['Renewed Policy']):,}".replace(",", "."), kpi_value_style),
        Paragraph(f"{case_val:.1f}% <font color='{case_dot}' size='12'>●</font>", kpi_value_style),
        Paragraph(f"{rate_val:.1f}% <font color='{rate_dot}' size='12'>●</font>", kpi_value_style),
    ]
    kpi_table = Table([kpi_headers, kpi_values], colWidths=[4.65 * cm] * 4, rowHeights=[0.72 * cm, 0.86 * cm])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.55, navy),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#6F8CAB")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    elements.append(Paragraph("Key Performance:", section_style))
    elements.append(kpi_table)
    elements.append(Spacer(1, 0.48 * cm))

    pdf_df = summary_df.head(500).copy()
    for pct_col in ["Case Ratio", "Renewal Rate", "Renewal Ratio"]:
        if pct_col in pdf_df.columns:
            pdf_df[pct_col] = pdf_df[pct_col].map(lambda x: f"{float(x):.1f}%")
    for c in ["Expired Policy", "Renewed Policy", "Not Renewed"]:
        if c in pdf_df.columns:
            pdf_df[c] = pdf_df[c].map(lambda x: f"{float(x):,.0f}".replace(",", "."))
    pdf_premium_rename = {}
    for c in ["Expired Premium", "Renewed Premium", "Not Renewed Premium"]:
        if c in pdf_df.columns:
            pdf_df[c] = pdf_df[c].map(_format_amount)
            pdf_premium_rename[c] = _premium_display_label(c)
    if pdf_premium_rename:
        pdf_df = pdf_df.rename(columns=pdf_premium_rename)

    data = [[Paragraph(str(c), header_style) for c in pdf_df.columns]]
    pdf_numeric_cols = {"Expired Policy", "Renewed Policy", "Not Renewed", "Case Ratio", "Renewal Rate", "Renewal Ratio"} | {c for c in pdf_df.columns if "Premium" in str(c)}
    ratio_col_idx = pdf_df.columns.get_loc("Case Ratio") if "Case Ratio" in pdf_df.columns else None
    ratio_raw_values = []
    for _, row in pdf_df.iterrows():
        row_cells = []
        for col_name, value in row.items():
            p_style = cell_style_right if str(col_name) in pdf_numeric_cols else cell_style_left
            row_cells.append(Paragraph(html.escape(str(value)), p_style))
        data.append(row_cells)
        if ratio_col_idx is not None:
            try:
                ratio_raw_values.append(float(str(row.get("Case Ratio", "0")).replace("%", "")))
            except Exception:
                ratio_raw_values.append(0.0)

    avail_w = landscape(A4)[0] - 1.6 * cm
    col_w = [max(2.1 * cm, avail_w / max(1, len(pdf_df.columns)))] * len(pdf_df.columns)
    total_w = sum(col_w)
    if total_w > avail_w:
        col_w = [w * avail_w / total_w for w in col_w]

    table = Table(data, repeatRows=1, colWidths=col_w)
    table_style = [
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.12, soft_grid),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for r in range(1, len(data)):
        if r % 2 == 0:
            table_style.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#F1F5F9")))
        if ratio_col_idx is not None and (r - 1) < len(ratio_raw_values):
            ratio_bg = _renewal_ratio_pdf_color(ratio_raw_values[r - 1])
            if ratio_bg is not None:
                table_style.append(("BACKGROUND", (ratio_col_idx, r), (ratio_col_idx, r), ratio_bg))
                band = _renewal_ratio_band(ratio_raw_values[r - 1])
                text_color = "#9F1239" if band == "red" else "#7C4A03"
                table_style.append(("TEXTCOLOR", (ratio_col_idx, r), (ratio_col_idx, r), colors.HexColor(text_color)))
    table.setStyle(TableStyle(table_style))
    elements.append(Paragraph("Renewal Summary", section_style))
    elements.append(Paragraph(html.escape(PREMIUM_DISPLAY_NOTE), meta_style))
    elements.append(table)

    doc.build(
        elements,
        onFirstPage=lambda canvas, d: draw_renewal_footer(canvas, d, username, doc_id),
        onLaterPages=lambda canvas, d: draw_renewal_footer(canvas, d, username, doc_id),
    )
    return buffer.getvalue()


def _download_link(label: str, data: bytes, file_name: str, mime: str) -> None:
    b64 = base64.b64encode(data).decode("ascii")
    st.markdown(
        f'<a style="color:#003366;font-weight:800;text-decoration:underline;text-underline-offset:3px;" download="{html.escape(file_name)}" href="data:{mime};base64,{b64}">{html.escape(label)}</a>',
        unsafe_allow_html=True,
    )



# =========================================================
# LAZY RENDER HELPERS
# =========================================================
def _fragment_if_available(func):
    """Return the function unchanged.

    Streamlit fragments are deliberately disabled in this module because page
    navigation and full-app reruns can leave stale fragment requests queued in
    the browser, producing repeated "fragment ... does not exist anymore" logs.
    """
    return func


# No manual rerun helper is needed for the time-series carousel. Streamlit
# widget interactions now use the normal full-app rerun path consistently.


@st.cache_data(show_spinner=False, ttl=900, max_entries=32)
def cached_make_renewal_summary(df: pd.DataFrame, group_cols_tuple: tuple[str, ...]) -> pd.DataFrame:
    return make_renewal_summary(df, list(group_cols_tuple)) if df is not None and not df.empty else pd.DataFrame()


def _current_group_cols_from_state(group_cols_available: list[str], df_for_default: pd.DataFrame) -> list[str]:
    group_cols_available = list(group_cols_available or [])
    if not group_cols_available:
        return []
    default_group = default_group_column(df_for_default if df_for_default is not None else pd.DataFrame())
    if default_group not in group_cols_available:
        default_group = group_cols_available[0]
    active_group = st.session_state.get("renewal_active_group", default_group)
    if active_group not in group_cols_available:
        active_group = default_group
        st.session_state["renewal_active_group"] = active_group
    extras = [c for c in st.session_state.get("renewal_additional_columns", []) or [] if c in group_cols_available and c != active_group]
    return [active_group] + extras[:5]


def _current_export_signature(filtered_df: pd.DataFrame, active_filters: dict, period_text: str, group_cols: list[str], kpis: dict) -> str:
    payload = {
        "rows": 0 if filtered_df is None else int(len(filtered_df)),
        "policy_count": 0 if filtered_df is None or POLICY_NO_COL not in filtered_df.columns else int(filtered_df[POLICY_NO_COL].nunique(dropna=True)),
        "active_filters": active_filters or {},
        "period": period_text or "-",
        "group_cols": list(group_cols or []),
        "kpis": {k: round(float(v), 6) if isinstance(v, (int, float, np.integer, np.floating)) else v for k, v in (kpis or {}).items()},
    }
    return hashlib.sha1(str(payload).encode("utf-8")).hexdigest()


def _clear_renewal_export_state(prefix: str) -> None:
    for suffix in ("bytes", "name", "doc_id", "sig", "error"):
        st.session_state.pop(f"{prefix}_{suffix}", None)


@_fragment_if_available
def render_renewal_timeseries_fragment(filtered_df: pd.DataFrame) -> None:
    contexts = _renewal_ts_contexts(filtered_df)
    if not contexts:
        return

    section_header("Renewal Trend")
    granularity = st.radio(
        "Trend aggregation",
        options=["Monthly", "Yearly"],
        key="renewal_trend_granularity",
        horizontal=True,
        help="Monthly menampilkan historical sampai 30 Jun 2026 dan early warning bulan setelahnya sebagai garis putus-putus. Yearly menggabungkan bulan dalam tahun yang sama.",
    )

    idx_key = "renewal_ts_scope_idx"
    current_idx = int(st.session_state.get(idx_key, 0) or 0)
    if current_idx < 0 or current_idx >= len(contexts):
        current_idx = 0

    left, mid, right = st.columns([1, 4, 1])
    with left:
        prev_clicked = st.button("‹ Previous", key="renewal_ts_prev", width="stretch", disabled=len(contexts) <= 1)
    with right:
        next_clicked = st.button("Next ›", key="renewal_ts_next", width="stretch", disabled=len(contexts) <= 1)

    if prev_clicked:
        current_idx = (current_idx - 1) % len(contexts)
    elif next_clicked:
        current_idx = (current_idx + 1) % len(contexts)
    st.session_state[idx_key] = current_idx

    scope_label, branch_value = contexts[current_idx]
    with mid:
        st.markdown(
            f"<div style='display:flex;justify-content:center;margin:2px 0 0 0;'>"
            f"<span class='renewal-ts-pill'>{html.escape(scope_label)} &middot; {current_idx + 1}/{len(contexts)}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    ts_df = cached_renewal_time_series(filtered_df, branch_value, granularity)
    render_renewal_timeseries_chart(ts_df, "All Branch" if branch_value is None else str(scope_label))

@_fragment_if_available
def render_renewal_summary_fragment(filtered_df: pd.DataFrame, group_cols_available: list[str]) -> None:
    section_header("Renewal Summary")
    if not group_cols_available:
        st.warning("No grouping columns available.")
        return

    # Default summary POV: YEARS as the primary grouping and MONTH as the default additional column.
    # YEAR_MONTH is intentionally not shown here.
    default_group = "YEARS" if "YEARS" in group_cols_available else default_group_column(filtered_df if filtered_df is not None and not filtered_df.empty else pd.DataFrame())
    if default_group not in group_cols_available:
        default_group = group_cols_available[0]

    if "renewal_active_group" not in st.session_state or st.session_state["renewal_active_group"] not in group_cols_available or st.session_state.get("renewal_active_group") == "YEAR_MONTH":
        st.session_state["renewal_active_group"] = default_group

    active_group = st.radio(
        "Renewal summary view",
        options=group_cols_available,
        key="renewal_active_group",
        horizontal=True,
        label_visibility="collapsed",
        help="Default summary memakai YEARS. Tambahkan MONTH untuk melihat breakdown bulanan tanpa memakai YEAR_MONTH.",
    )

    extra_options = [c for c in group_cols_available if c != active_group]
    extra_key = "renewal_additional_columns"
    default_extras = ["MONTH"] if active_group == "YEARS" and "MONTH" in extra_options else []
    current_extras = [c for c in st.session_state.get(extra_key, default_extras) if c in extra_options and c != active_group and c != "YEAR_MONTH"]
    if extra_key not in st.session_state:
        st.session_state[extra_key] = current_extras
    else:
        st.session_state[extra_key] = current_extras

    extra_cols = st.multiselect(
        "Additional columns",
        options=extra_options,
        max_selections=5,
        key=extra_key,
        help="Default-nya Month supaya summary langsung tampil by Years + Month. Maksimal 5 kolom agar tabel tetap readable.",
    )
    group_cols = [active_group] + [c for c in extra_cols if c != active_group and c != "YEAR_MONTH"]
    st.session_state["renewal_current_group_cols"] = group_cols

    summary_df = cached_make_renewal_summary(filtered_df, tuple(group_cols)) if filtered_df is not None and not filtered_df.empty else pd.DataFrame()
    render_html_table(summary_df, table_key="_".join(map(str, group_cols)))

@_fragment_if_available
def render_renewal_export_fragment(
    filtered_df: pd.DataFrame,
    kpis: dict,
    active_filters: dict,
    period_text: str,
    username: str,
    group_cols_available: list[str],
) -> None:
    section_header("Export")
    group_cols = _current_group_cols_from_state(group_cols_available, filtered_df)
    summary_df = cached_make_renewal_summary(filtered_df, tuple(group_cols)) if filtered_df is not None and not filtered_df.empty else pd.DataFrame()
    sig = _current_export_signature(filtered_df, active_filters, period_text, group_cols, kpis)

    for prefix in ("renewal_pdf", "renewal_xlsx"):
        if st.session_state.get(f"{prefix}_sig") != sig:
            _clear_renewal_export_state(prefix)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Prepare PDF", width="content", key="renewal_prepare_pdf"):
            try:
                with st.spinner("Preparing PDF..."):
                    doc_id = generate_document_id("RN")
                    pdf_bytes = export_renewal_pdf(
                        summary_df,
                        kpis,
                        active_filters,
                        period_text=period_text,
                        username=username,
                        doc_id=doc_id,
                    )
                st.session_state["renewal_pdf_bytes"] = pdf_bytes
                st.session_state["renewal_pdf_doc_id"] = doc_id
                st.session_state["renewal_pdf_name"] = f"renewal_dashboard_{doc_id}.pdf"
                st.session_state["renewal_pdf_sig"] = sig
                st.session_state.pop("renewal_pdf_error", None)
            except Exception as e:
                _clear_renewal_export_state("renewal_pdf")
                st.session_state["renewal_pdf_error"] = str(e)

        if st.session_state.get("renewal_pdf_error"):
            st.error(f"PDF export failed: {st.session_state['renewal_pdf_error']}")
        elif st.session_state.get("renewal_pdf_bytes"):
            _download_link("Download PDF", st.session_state["renewal_pdf_bytes"], st.session_state["renewal_pdf_name"], "application/pdf")
            st.caption(f"PDF ready. Document ID: {st.session_state.get('renewal_pdf_doc_id', '-')}")
        else:
            st.caption("Prepare PDF dulu sebelum download.")

    with c2:
        if st.button("Prepare Excel", width="content", key="renewal_prepare_excel"):
            try:
                with st.spinner("Preparing Excel..."):
                    doc_id = generate_document_id("RN")
                    xlsx_bytes = export_renewal_excel(
                        summary_df,
                        filtered_df,
                        active_filters,
                        period_text=period_text,
                        username=username,
                        doc_id=doc_id,
                    )
                st.session_state["renewal_xlsx_bytes"] = xlsx_bytes
                st.session_state["renewal_xlsx_doc_id"] = doc_id
                st.session_state["renewal_xlsx_name"] = f"renewal_dashboard_{doc_id}.xlsx"
                st.session_state["renewal_xlsx_sig"] = sig
                st.session_state.pop("renewal_xlsx_error", None)
            except Exception as e:
                _clear_renewal_export_state("renewal_xlsx")
                st.session_state["renewal_xlsx_error"] = str(e)

        if st.session_state.get("renewal_xlsx_error"):
            st.error(f"Excel export failed: {st.session_state['renewal_xlsx_error']}")
        elif st.session_state.get("renewal_xlsx_bytes"):
            _download_link(
                "Download Excel",
                st.session_state["renewal_xlsx_bytes"],
                st.session_state["renewal_xlsx_name"],
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            st.caption(f"Excel ready. Document ID: {st.session_state.get('renewal_xlsx_doc_id', '-')}")
        else:
            st.caption("Prepare Excel dulu sebelum download.")


@_fragment_if_available
def render_renewal_detail_fragment(filtered_df: pd.DataFrame) -> None:
    with st.expander("Detail Data", expanded=False):
        st.caption("Detail mengikuti filter aktif. RENEWAL POLICY NO hanya dipakai untuk menentukan status renewal, bukan sebagai filter atau grouping.")
        show_detail = st.checkbox("Load detail data", key="renewal_load_detail_data")
        if not show_detail:
            st.caption("Centang untuk menampilkan tabel detail. Tabel akan dimuat 25 rows per page agar lebih ringan.")
            return
        if filtered_df is None or filtered_df.empty:
            st.info("No data on this filter.")
            return

        detail_cols = [
            c for c in filtered_df.columns
            if c not in {"IS_RENEWED", "YEAR_MONTH", "_DATE_KEY"}
        ]
        detail_df = filtered_df[detail_cols].copy().reset_index(drop=True)
        total_rows = len(detail_df)
        total_pages = max(1, int(np.ceil(total_rows / DETAIL_PAGE_SIZE)))

        sig_payload = f"{total_rows}|{filtered_df[POLICY_NO_COL].nunique(dropna=True) if POLICY_NO_COL in filtered_df.columns else total_rows}|{get_renewal_period_text(filtered_df)}"
        sig = hashlib.sha1(sig_payload.encode("utf-8")).hexdigest()
        sig_key = "renewal_detail_sig"
        page_key = "renewal_detail_page"
        if st.session_state.get(sig_key) != sig:
            st.session_state[sig_key] = sig
            st.session_state[page_key] = 1

        current_page = int(st.session_state.get(page_key, 1) or 1)
        current_page = min(max(current_page, 1), total_pages)
        st.session_state[page_key] = current_page

        nav_left, nav_page, nav_info, nav_right = st.columns([1, 1.4, 3, 1])
        with nav_left:
            if st.button("‹ Previous", key="renewal_detail_prev", disabled=current_page <= 1, width="stretch"):
                st.session_state[page_key] = max(1, current_page - 1)
                current_page = st.session_state[page_key]
        with nav_right:
            if st.button("Next ›", key="renewal_detail_next", disabled=current_page >= total_pages, width="stretch"):
                st.session_state[page_key] = min(total_pages, current_page + 1)
                current_page = st.session_state[page_key]
        with nav_page:
            page_input = st.number_input(
                "Page",
                min_value=1,
                max_value=total_pages,
                value=current_page,
                step=1,
                key="renewal_detail_page_input",
            )
            if int(page_input) != current_page:
                current_page = int(page_input)
                st.session_state[page_key] = current_page
        with nav_info:
            start_row = (current_page - 1) * DETAIL_PAGE_SIZE + 1
            end_row = min(current_page * DETAIL_PAGE_SIZE, total_rows)
            st.caption(f"Showing rows {start_row:,}–{end_row:,} of {total_rows:,} | 25 rows per page".replace(",", "."))

        start_idx = (current_page - 1) * DETAIL_PAGE_SIZE
        end_idx = start_idx + DETAIL_PAGE_SIZE
        detail_display_df = detail_df.iloc[start_idx:end_idx].copy()
        render_html_table(
            detail_display_df,
            table_key=f"renewal_detail_data_page_{current_page}",
            height=520,
        )

def render_renewal_dashboard(path: str = DEFAULT_RENEWAL_PATH, username: str = "") -> None:
    inject_renewal_css()
    section_header("Renewal Dashboard")

    # Force Streamlit to drop stale cached renewal data when this dashboard logic changes.
    # This is important because older versions could cache PREMIUM AMT as 0, which then
    # made Renewal Rate stay 0 even after the code was fixed.
    cache_version_key = "renewal_dashboard_cache_version"
    try:
        if st.session_state.get(cache_version_key) != RENEWAL_DASHBOARD_VERSION:
            st.cache_data.clear()
            st.session_state[cache_version_key] = RENEWAL_DASHBOARD_VERSION
    except Exception:
        pass

    try:
        df = _ensure_premium_column(load_renewal_data(path, version=RENEWAL_DASHBOARD_VERSION))
    except Exception as e:
        st.error(f"Renewal data failed to load: {e}")
        return

    filter_cols = available_filter_columns(df)
    group_cols_available = available_group_columns(df)

    st.sidebar.markdown("### Renewal Filters")
    filter_state = {}
    for col in filter_cols:
        if col == POLICY_NO_COL or col in EXCLUDED_COLUMNS:
            continue
        with st.sidebar.expander(str(col).replace("_", " "), expanded=False):
            mode_key = f"renewal_filter_mode_{col}"
            selected_key = f"renewal_filter_{col}"
            search_key = f"renewal_search_{col}"

            options = _filter_all_options(df, col)

            # Default business rules from the renewal dashboard:
            #   TOB excludes MULTIFINANCE
            #   LOB excludes TRAVEL INSURANCE
            # All other columns default to Include Selected with no selected values,
            # which means the filter is inactive / select all.
            default_value = _find_option_case_insensitive(options, DEFAULT_EXCLUDE_FILTERS.get(col, ""))
            default_mode = "Exclude Selected" if default_value else "Include Selected"
            default_selected = [default_value] if default_value else []

            if st.session_state.get(mode_key) not in FILTER_MODES:
                st.session_state[mode_key] = default_mode
            if selected_key not in st.session_state:
                st.session_state[selected_key] = default_selected

            mode = st.radio(
                "Mode",
                options=FILTER_MODES,
                key=mode_key,
                horizontal=False,
                help="No selected item means inactive / select all. If all values are selected, the dashboard clears it back to inactive.",
            )

            if len(options) > 1500:
                q = st.text_input("Search item", key=search_key, placeholder=f"Type to search {col}")
                shown = [x for x in options if q.lower() in x.lower()][:100] if q else []
                if default_selected and not q:
                    shown = sorted(set(shown + default_selected))
                selected = st.multiselect(
                    "Choose item",
                    options=shown,
                    key=selected_key,
                    on_change=_normalize_filter_widget_selection,
                    args=(selected_key, options),
                )
                if not q and not selected:
                    st.caption("No selection = filter inactive. Type to search before choosing item.")
            else:
                selected = st.multiselect(
                    "Choose item",
                    options=options,
                    key=selected_key,
                    on_change=_normalize_filter_widget_selection,
                    args=(selected_key, options),
                )

            if _selection_is_all(selected, options):
                selected = []
                st.caption("All values selected = filter inactive.")
            elif selected:
                st.caption(f"{len(selected)} selected")
            else:
                st.caption("Inactive / select all")

            if _filter_is_active(mode, selected, options):
                filter_state[col] = {"mode": mode, "values": selected}

    # Only filter/KPI recomputes on full-app events. Summary, Export and Detail
    # use the standard Streamlit rerun path for stable page navigation.
    filtered_df, active_filters = apply_filters(df, filter_state)
    filtered_df = _ensure_premium_column(filtered_df) if filtered_df is not None and not filtered_df.empty else filtered_df
    period_text = get_renewal_period_text(filtered_df)
    kpis = compute_kpis(filtered_df)

    render_kpis(kpis)
    premium_source = str(df.attrs.get("PREMIUM_SOURCE_COL") or (_find_premium_col(df) or "NOT FOUND"))
    if premium_source == "NOT FOUND":
        st.warning("Renewal Rate belum bisa dihitung karena kolom premi tidak ditemukan. Cek nama kolom premium di file parquet.")
        st.caption(_premium_debug_message(df))
    elif filtered_df is not None and not filtered_df.empty and float(kpis.get("Expired Premium", 0.0) or 0.0) == 0.0:
        st.warning("Kolom premi ditemukan, tetapi total premium pada filter aktif masih 0. Dashboard mungkin membaca parquet lama atau file dengan premium kosong.")
        st.caption(_premium_debug_message(filtered_df) + f". Loaded file: {df.attrs.get('RENEWAL_SOURCE_PATH', '-')}")
    st.markdown("<div class='renewal-ts-spacer'></div>", unsafe_allow_html=True)
    render_renewal_timeseries_fragment(filtered_df)
    render_renewal_summary_fragment(filtered_df, group_cols_available)
    render_renewal_export_fragment(filtered_df, kpis, active_filters, period_text, username, group_cols_available)
    render_renewal_detail_fragment(filtered_df)


if __name__ == "__main__":
    #st.set_page_config(page_title="Renewal Dashboard", layout="wide")
    render_renewal_dashboard()
