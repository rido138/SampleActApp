import pandas as pd
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
import io
from copy import deepcopy
from pathlib import Path
import os
import re
import base64
import json
import html
import altair as alt
import plotly.graph_objects as go
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import grey
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import pytz
import hashlib
import uuid
from html.parser import HTMLParser
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from zoneinfo import ZoneInfo






PDF_FONT_REGULAR = "Helvetica"
PDF_FONT_BOLD = "Helvetica-Bold"


def _register_pdf_beamer_fonts():
    global PDF_FONT_REGULAR, PDF_FONT_BOLD

    candidates = [
        (
            "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
            "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
        ),
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ),
    ]

    for regular_path, bold_path in candidates:
        try:
            if os.path.exists(regular_path) and os.path.exists(bold_path):
                pdfmetrics.registerFont(TTFont("BeamerSans", regular_path))
                pdfmetrics.registerFont(TTFont("BeamerSans-Bold", bold_path))
                PDF_FONT_REGULAR = "BeamerSans"
                PDF_FONT_BOLD = "BeamerSans-Bold"
                return
        except Exception:
            continue


_register_pdf_beamer_fonts()





def get_gsheetchat(sheet_name="download_log"):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp"], scope
    )

    client = gspread.authorize(creds)
    spreadsheet = client.open("Login Log")

    return spreadsheet.worksheet(sheet_name)

def log_download(doc_id, username):
    scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
    ]
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp"], scope
    )
    
    client = gspread.authorize(creds)
    

    spreadsheet = client.open("Login Log")
    

    sheet_chat = spreadsheet.worksheet("download_log")
    now = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")
    
    sheet_chat.append_row([
        doc_id,
        username,
        now
    ])





DOCUMENT_FILTER_LOG_SHEET = "document_filter_log"
DOCUMENT_FILTER_HEADERS = [
    "DOC_ID",
    "CREATED_AT",
    "USERNAME",
    "MODULE",
    "EXPORT_TYPE",
    "ACTIVE_DETAIL_TAB",
    "DETAIL_EXTRA_COLUMNS_JSON",
    "GROUP_COLS_JSON",
    "FILTERS_JSON",
    "OVR_STATUS",
    "OVR_DETAIL_JSON",
    "INCLUDE_CLAIM_BREAKDOWN",
    "EXCEL_RANGE_START",
    "EXCEL_RANGE_END",
    "TOTAL_ROWS",
    "FILE_NAME",
    "OPEX_NON_FRONTING_PCT",
    "OPEX_FRONTING_PCT",
    "OPEX_ADJUST_REASON",
]




SAVED_REPORTS_SHEET = "saved_reports"
SAVED_REPORT_HEADERS = [
    "REPORT_ID",
    "CREATED_AT",
    "UPDATED_AT",
    "OWNER",
    "LABEL",
    "DESCRIPTION",
    "LAST_UPDATED_BY",
    "MODULE",
    "IS_ACTIVE",
]



def _json_safe_value(value):

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
        return {str(k): _json_safe_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe_value(v) for v in value]
    if isinstance(value, pd.DataFrame):
        return [_json_safe_value(r) for r in value.to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return [_json_safe_value(v) for v in value.tolist()]
    return value


def _to_json_text(value) -> str:
    return json.dumps(_json_safe_value(value), ensure_ascii=False, default=str)


def _from_json_text(value, default=None):
    if default is None:
        default = {}
    try:
        if value is None or str(value).strip() == "":
            return default
        return json.loads(str(value))
    except Exception:
        return default


def _normalize_saved_filter_values(values, options):







    if values is None:
        return [], []
    if not isinstance(values, (list, tuple, set)):
        values = [values]

    clean_values = [v for v in values if str(v).strip().lower() not in ("", "all", "none", "nan")]
    if not clean_values:
        return [], []

    def norm(x):
        text = str(x).strip()

        try:
            f = float(text.replace(",", ""))
            if f.is_integer():
                text = str(int(f))
        except Exception:
            pass
        return text.lower()

    option_map = {}
    for opt in list(options or []):
        option_map.setdefault(norm(opt), opt)

    matched = []
    missing = []
    for v in clean_values:
        key = norm(v)
        if key in option_map:
            matched.append(option_map[key])
        else:
            missing.append(v)

    return matched, missing



OVR_METADATA_COLS = {
    "OVR_MODE", "OVR MODE", "OVR_PCT_INPUT", "OVR (%)", "OVR_PCT", "OVR %", "OVR", "__ovr_key"
}


def _safe_ovr_pct_from_saved(value, default=0.0):

    try:
        if value is None:
            return default
        if isinstance(value, str):
            txt = value.strip().replace("%", "")

            if "," in txt and "." not in txt:
                txt = txt.replace(",", ".")
            else:
                txt = txt.replace(",", "")
            if txt == "":
                return default
            return float(txt)
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _compute_loaded_rules_ovr_sig(dims, rules_df: pd.DataFrame):

    try:
        preview_cols = [c for c in (list(dims or []) + ["OVR_PCT_INPUT"]) if c in rules_df.columns]
        preview_df = rules_df[preview_cols].copy() if preview_cols else rules_df.copy()
        preview_json = preview_df.astype("string").fillna("<NA>").to_json(orient="split")
        h = hashlib.sha1(preview_json.encode("utf-8")).hexdigest()
    except Exception:
        h = "loaded"
    return ("rules", tuple(dims or []), h)


def _reset_ovr_state_from_document() -> None:

    st.session_state["risk_profile_applied_ovr"] = None
    st.session_state["ovr_mode"] = "uniform"
    st.session_state["ovr_uniform_pct_input"] = 0.0
    st.session_state["ovr_dims"] = []
    st.session_state["ovr_rules_df"] = pd.DataFrame()
    st.session_state["ovr_applied"] = False
    st.session_state["ovr_confirmed"] = False
    st.session_state["ovr_keep_open"] = False
    st.session_state["ovr_user_touched"] = False
    st.session_state["ovr_confirm_checkbox"] = False
    st.session_state["ovr_confirm_checkbox_uniform"] = False
    st.session_state["ovr_last_dims_sig"] = ""
    st.session_state["ovr_last_sig"] = ("uniform", 0.0)
    st.session_state["ovr_rules_editor_version"] = st.session_state.get("ovr_rules_editor_version", 0) + 1


def _normalize_loaded_ovr_rule_values(rules_df: pd.DataFrame, dims, option_map: dict) -> pd.DataFrame:

    out = rules_df.copy()
    for dim in list(dims or []):
        if dim not in out.columns or dim not in option_map:
            continue

        def _match_one(v):
            matched, _ = _normalize_saved_filter_values([v], option_map.get(dim, []))
            return matched[0] if matched else v

        out[dim] = out[dim].apply(_match_one)
    return out


def _load_ovr_state_from_document_record(record: dict, available_filter_options) -> tuple[bool, str | None]:






    status = str(record.get("OVR_STATUS") or "").strip().lower()
    if status != "include ovr":
        _reset_ovr_state_from_document()
        return False, None

    if isinstance(available_filter_options, dict):
        option_map = available_filter_options
        available_cols = set(available_filter_options.keys())
    else:
        option_map = {col: [] for col in (available_filter_options or [])}
        available_cols = set(available_filter_options or [])

    raw_detail = _from_json_text(record.get("OVR_DETAIL_JSON"), default=[])
    if isinstance(raw_detail, dict):
        raw_detail = [raw_detail]
    if not isinstance(raw_detail, list) or not raw_detail:
        _reset_ovr_state_from_document()
        return False, "OVR detail missing"

    detail_df = pd.DataFrame(raw_detail)
    if detail_df.empty:
        _reset_ovr_state_from_document()
        return False, "OVR detail empty"


    rename_map = {}
    for alt in ["OVR (%)", "OVR_PCT", "OVR %", "OVR"]:
        if alt in detail_df.columns and "OVR_PCT_INPUT" not in detail_df.columns:
            rename_map[alt] = "OVR_PCT_INPUT"
    if rename_map:
        detail_df = detail_df.rename(columns=rename_map)

    if "OVR_PCT_INPUT" not in detail_df.columns:
        _reset_ovr_state_from_document()
        return False, "OVR percentage column missing"

    detail_df["OVR_PCT_INPUT"] = detail_df["OVR_PCT_INPUT"].apply(_safe_ovr_pct_from_saved)

    mode_text = ""
    if "OVR_MODE" in detail_df.columns:
        try:
            mode_text = " ".join(detail_df["OVR_MODE"].dropna().astype(str).str.lower().tolist())
        except Exception:
            mode_text = ""

    dims = [c for c in detail_df.columns if str(c).strip() not in OVR_METADATA_COLS]
    dims = [c for c in dims if not str(c).startswith("Unnamed")]


    is_uniform = (not dims) or ("sama" in mode_text) or ("uniform" in mode_text)
    if is_uniform:
        pct_series = pd.to_numeric(detail_df["OVR_PCT_INPUT"], errors="coerce").dropna()
        pct = float(pct_series.iloc[0]) if not pct_series.empty else 0.0
        st.session_state["ovr_mode"] = "uniform"
        st.session_state["ovr_uniform_pct_input"] = pct
        st.session_state["ovr_confirm_checkbox_uniform"] = True
        st.session_state["ovr_confirmed"] = True
        st.session_state["ovr_applied"] = True
        st.session_state["ovr_keep_open"] = True
        st.session_state["ovr_user_touched"] = True
        st.session_state["ovr_last_sig"] = ("uniform", pct)
        _commit_ovr_configuration()
        return True, f"OVR loaded: uniform {pct:g}%"

    missing_dims = [d for d in dims if available_cols and d not in available_cols]
    if missing_dims:
        _reset_ovr_state_from_document()
        return False, f"OVR dimensions unavailable: {', '.join(map(str, missing_dims[:3]))}"

    rules_df = detail_df[dims + ["OVR_PCT_INPUT"]].copy()
    rules_df = _normalize_loaded_ovr_rule_values(rules_df, dims, option_map)
    rules_df["OVR_PCT_INPUT"] = pd.to_numeric(rules_df["OVR_PCT_INPUT"], errors="coerce")
    rules_df = rules_df[rules_df["OVR_PCT_INPUT"].notna()].reset_index(drop=True)

    if rules_df.empty:
        _reset_ovr_state_from_document()
        return False, "OVR rules empty"

    dims_sig = "|".join(map(str, dims))
    st.session_state["ovr_mode"] = "rules"
    st.session_state["ovr_dims"] = list(dims)
    st.session_state["ovr_rules_df"] = rules_df
    st.session_state["ovr_last_dims_sig"] = dims_sig
    st.session_state["ovr_rules_editor_version"] = st.session_state.get("ovr_rules_editor_version", 0) + 1
    st.session_state["ovr_confirm_checkbox"] = True
    st.session_state["ovr_confirmed"] = True
    st.session_state["ovr_applied"] = True
    st.session_state["ovr_keep_open"] = True
    st.session_state["ovr_user_touched"] = True
    st.session_state["ovr_last_sig"] = _compute_loaded_rules_ovr_sig(dims, rules_df)
    _commit_ovr_configuration()
    return True, f"OVR loaded: {len(rules_df):,} rule(s)"


def _sanitize_doc_id(doc_id: str) -> str:
    return str(doc_id or "").strip().upper().replace(" ", "")


def _get_document_filter_sheet():

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp"], scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("Login Log")

    try:
        sheet = spreadsheet.worksheet(DOCUMENT_FILTER_LOG_SHEET)
    except Exception:
        sheet = spreadsheet.add_worksheet(
            title=DOCUMENT_FILTER_LOG_SHEET,
            rows=1000,
            cols=len(DOCUMENT_FILTER_HEADERS),
        )

    try:
        current_header = sheet.row_values(1)
        if current_header[:len(DOCUMENT_FILTER_HEADERS)] != DOCUMENT_FILTER_HEADERS:
            sheet.update("A1", [DOCUMENT_FILTER_HEADERS])
    except Exception:
        pass

    return sheet


def _document_id_exists(doc_id: str) -> bool:
    doc_id = _sanitize_doc_id(doc_id)
    if not doc_id:
        return False
    try:
        sheet = _get_document_filter_sheet()
        existing = set(_sanitize_doc_id(x) for x in sheet.col_values(1)[1:])
        return doc_id in existing
    except Exception:


        return False


def generate_unique_document_id(prefix: str = "RP") -> str:

    prefix = _sanitize_doc_id(prefix) or "RP"
    date_part = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%y%m%d")

    for _ in range(8):
        candidate = f"{prefix}-{date_part}-{uuid.uuid4().hex[:8].upper()}"
        if not _document_id_exists(candidate):
            return candidate


    return f"{prefix}-{date_part}-{uuid.uuid4().hex[:12].upper()}"


def save_document_filter_log(
    doc_id: str,
    username: str,
    export_type: str,
    active_detail_tab: str,
    detail_extra_columns,
    group_cols,
    filters: dict,
    ovr_status: str = "Exclude OVR",
    ovr_detail_df: pd.DataFrame | None = None,
    include_claim_breakdown: bool = False,
    excel_range_start=None,
    excel_range_end=None,
    total_rows=None,
    file_name: str = "",
) -> None:

    try:
        sheet = _get_document_filter_sheet()
        created_at = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")
        row = {
            "DOC_ID": _sanitize_doc_id(doc_id),
            "CREATED_AT": created_at,
            "USERNAME": str(username or ""),
            "MODULE": "Risk Profile",
            "EXPORT_TYPE": str(export_type or ""),
            "ACTIVE_DETAIL_TAB": str(active_detail_tab or ""),
            "DETAIL_EXTRA_COLUMNS_JSON": _to_json_text(detail_extra_columns or []),
            "GROUP_COLS_JSON": _to_json_text(list(group_cols or [])),
            "FILTERS_JSON": _to_json_text(filters or {}),
            "OVR_STATUS": str(ovr_status or "Exclude OVR"),
            "OVR_DETAIL_JSON": _to_json_text(ovr_detail_df if isinstance(ovr_detail_df, pd.DataFrame) else []),
            "INCLUDE_CLAIM_BREAKDOWN": bool(include_claim_breakdown),
            "EXCEL_RANGE_START": "" if excel_range_start is None else int(excel_range_start) + 1,
            "EXCEL_RANGE_END": "" if excel_range_end is None else int(excel_range_end),
            "TOTAL_ROWS": "" if total_rows is None else int(total_rows),
            "FILE_NAME": str(file_name or ""),
            "OPEX_NON_FRONTING_PCT": _get_opex_assumptions_pct()[0],
            "OPEX_FRONTING_PCT": _get_opex_assumptions_pct()[1],
            "OPEX_ADJUST_REASON": _get_opex_adjust_reason() if _opex_assumptions_are_adjusted() else "",
        }
        sheet.append_row([row.get(h, "") for h in DOCUMENT_FILTER_HEADERS], value_input_option="USER_ENTERED")
    except Exception:
        pass


def load_document_filter_record(doc_id: str) -> dict | None:

    doc_id = _sanitize_doc_id(doc_id)
    if not doc_id:
        return None

    try:
        sheet = _get_document_filter_sheet()
        records = sheet.get_all_records()
        for rec in reversed(records):
            if _sanitize_doc_id(rec.get("DOC_ID")) == doc_id:
                return rec
    except Exception:
        return None

    return None


def apply_document_filter_record(record: dict, available_filter_options) -> tuple[int, list[str]]:






    filters = _from_json_text(record.get("FILTERS_JSON"), default={})
    detail_extra_columns = _from_json_text(record.get("DETAIL_EXTRA_COLUMNS_JSON"), default=[])
    active_detail_tab = str(record.get("ACTIVE_DETAIL_TAB") or "")



    saved_opex_non = _safe_to_float(record.get("OPEX_NON_FRONTING_PCT"), DEFAULT_OPEX_NON_FRONTING_PCT)
    saved_opex_front = _safe_to_float(record.get("OPEX_FRONTING_PCT"), DEFAULT_OPEX_FRONTING_PCT)
    st.session_state[OPEX_NON_FRONTING_STATE_KEY] = saved_opex_non
    st.session_state[OPEX_FRONTING_STATE_KEY] = saved_opex_front
    saved_opex_reason = str(record.get("OPEX_ADJUST_REASON") or "").strip()
    st.session_state[OPEX_ADJUST_REASON_STATE_KEY] = saved_opex_reason if _opex_assumptions_are_adjusted(saved_opex_non, saved_opex_front) else ""

    applied = 0
    skipped = []

    if isinstance(available_filter_options, dict):
        option_map = available_filter_options
        available = set(option_map.keys())
    else:
        option_map = {col: [] for col in (available_filter_options or [])}
        available = set(available_filter_options or [])

    for col, info in (filters or {}).items():
        if not isinstance(info, dict):
            skipped.append(str(col))
            continue

        mode = str(info.get("mode", "Include Selected"))
        values = info.get("values", []) or []

        if col in available:
            mode_key = f"{col}_mode"
            sel_key = f"{col}_selected"
            allowed_modes = ["Include Selected", "Include All", "Exclude Selected", "Exclude All"]
            final_mode = mode if mode in allowed_modes else "Include Selected"
            st.session_state[mode_key] = final_mode

            if final_mode in ["Include Selected", "Exclude Selected"]:
                matched_values, missing_values = _normalize_saved_filter_values(values, option_map.get(col, []))
                st.session_state[sel_key] = matched_values
                if values and not matched_values:
                    skipped.append(f"{col} values not available")
                elif missing_values:
                    skipped.append(f"{col}: {len(missing_values)} unavailable")
            else:
                st.session_state[sel_key] = []
            applied += 1

        elif col == "INSURED_NAME_2":
            allowed_modes = ["Include Selected", "Exclude Selected", "All"]
            final_mode = mode if mode in allowed_modes else "All"
            st.session_state["mode_INSURED2"] = final_mode
            saved_values = [v for v in values if str(v).strip().lower() != "all"]
            st.session_state["select_INSURED2"] = saved_values if final_mode != "All" else []
            st.session_state["query_INSURED2"] = ""
            st.session_state["query_INSURED2__draft"] = ""
            st.session_state["query_INSURED2__committed"] = ""
            applied += 1

        elif col == "POLICY_NO":
            allowed_modes = ["Include Selected", "Exclude Selected", "All"]
            final_mode = mode if mode in allowed_modes else "All"
            st.session_state["mode_POLNO"] = final_mode
            saved_values = [v for v in values if str(v).strip().lower() != "all"]
            st.session_state["select_POLNO"] = saved_values if final_mode != "All" else []
            st.session_state["query_POLNO"] = ""
            st.session_state["query_POLNO__draft"] = ""
            st.session_state["query_POLNO__committed"] = ""
            applied += 1

        else:
            skipped.append(str(col))

    if isinstance(detail_extra_columns, list):
        st.session_state["detailed_table_extra_columns"] = detail_extra_columns

    if active_detail_tab:

        st.session_state["risk_profile_active_detail_tab"] = active_detail_tab

    ovr_loaded, ovr_note = _load_ovr_state_from_document_record(record, option_map)
    if ovr_loaded:
        applied += 1
        if ovr_note:
            st.session_state["loaded_ovr_notice"] = ovr_note
    elif ovr_note:
        skipped.append(ovr_note)

    st.session_state["loaded_document_id"] = _sanitize_doc_id(record.get("DOC_ID"))
    return applied, skipped

def render_document_filter_loader(available_filter_options) -> None:

    notice = st.session_state.pop("loaded_document_filter_notice", None)
    if notice:
        st.sidebar.success(notice)

    with st.sidebar.expander("Load Document Filter", expanded=False):
        st.caption("Input Document ID untuk menerapkan filter yang tersimpan. As of date tetap mengikuti pilihan saat ini.")
        doc_id_input = st.text_input(
            "Document ID",
            key="load_document_id_input",
            placeholder="RP-260508-XXXXXXXX",
        )
        if st.button("Apply Document Filter", key="apply_document_filter_btn", width="stretch"):
            doc_id = _sanitize_doc_id(doc_id_input)
            if not doc_id:
                st.warning("Masukkan Document ID terlebih dahulu.")
            else:
                record = load_document_filter_record(doc_id)
                if not record:
                    st.error("Document ID tidak ditemukan di Google Sheet.")
                else:
                    applied, skipped = apply_document_filter_record(record, available_filter_options)


                    st.session_state.pop("loaded_ovr_notice", None)
                    if skipped:
                        st.session_state["loaded_document_filter_notice"] = (
                            "Report loaded. Some saved selections are not available for the current data date."
                        )
                    else:
                        st.session_state["loaded_document_filter_notice"] = "Report loaded successfully."
                    try:
                        st.rerun(scope="app")
                    except TypeError:
                        st.rerun()



def _get_saved_reports_sheet():

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp"], scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("Login Log")

    try:
        sheet = spreadsheet.worksheet(SAVED_REPORTS_SHEET)
    except Exception:
        sheet = spreadsheet.add_worksheet(
            title=SAVED_REPORTS_SHEET,
            rows=1000,
            cols=len(SAVED_REPORT_HEADERS),
        )

    try:
        current_header = sheet.row_values(1)
        if current_header[:len(SAVED_REPORT_HEADERS)] != SAVED_REPORT_HEADERS:
            sheet.update("A1", [SAVED_REPORT_HEADERS])
    except Exception:
        pass

    return sheet


def _saved_report_is_active(value) -> bool:
    text = str(value if value is not None else "").strip().lower()
    return text not in ("false", "0", "no", "n", "deleted", "inactive")


def _safe_sheet_update_row(sheet, row_idx: int, values: list) -> None:
    end_col = chr(ord("A") + len(values) - 1)
    sheet.update(f"A{row_idx}:{end_col}{row_idx}", [values])


def list_saved_report_records(limit: int = 80) -> list[dict]:





    try:
        sheet = _get_saved_reports_sheet()
        values = sheet.get_all_values()
        if len(values) < 2:
            return []

        headers = values[0]
        records = []
        for row in values[1:]:
            rec = {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}
            report_id = _sanitize_doc_id(rec.get("REPORT_ID"))
            if not report_id:
                continue
            if not _saved_report_is_active(rec.get("IS_ACTIVE", "TRUE")):
                continue
            rec["REPORT_ID"] = report_id
            records.append(rec)

        records.sort(
            key=lambda r: str(r.get("UPDATED_AT") or r.get("CREATED_AT") or ""),
            reverse=True,
        )
        return records[: max(1, int(limit or 80))]
    except Exception:
        return []


def get_saved_report_record(report_id: str) -> dict | None:
    report_id = _sanitize_doc_id(report_id)
    if not report_id:
        return None
    try:
        sheet = _get_saved_reports_sheet()
        values = sheet.get_all_values()
        if len(values) < 2:
            return None
        headers = values[0]
        for row in reversed(values[1:]):
            rec = {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}
            if _sanitize_doc_id(rec.get("REPORT_ID")) == report_id and _saved_report_is_active(rec.get("IS_ACTIVE", "TRUE")):
                rec["REPORT_ID"] = report_id
                return rec
    except Exception:
        return None
    return None


def upsert_saved_report_metadata(
    report_id: str,
    username: str,
    label: str,
    description: str = "",
) -> None:

    report_id = _sanitize_doc_id(report_id)
    if not report_id:
        return

    sheet = _get_saved_reports_sheet()
    now = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")
    label = str(label or report_id).strip() or report_id
    description = str(description or "").strip()
    username = str(username or "").strip()

    try:
        values = sheet.get_all_values()
        headers = values[0] if values else SAVED_REPORT_HEADERS
        if headers[:len(SAVED_REPORT_HEADERS)] != SAVED_REPORT_HEADERS:
            sheet.update("A1", [SAVED_REPORT_HEADERS])
            headers = SAVED_REPORT_HEADERS
            values = sheet.get_all_values()

        target_row_idx = None
        existing = {}
        for idx, row in enumerate(values[1:], start=2):
            rec = {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}
            if _sanitize_doc_id(rec.get("REPORT_ID")) == report_id:
                target_row_idx = idx
                existing = rec
                break

        created_at = existing.get("CREATED_AT") or now
        owner = existing.get("OWNER") or username
        row_values = [
            report_id,
            created_at,
            now,
            owner,
            label,
            description,
            username,
            "Risk Profile",
            "TRUE",
        ]

        if target_row_idx:
            _safe_sheet_update_row(sheet, target_row_idx, row_values)
        else:
            sheet.append_row(row_values, value_input_option="USER_ENTERED")
    except Exception:

        pass


def _saved_report_label(record: dict) -> str:

    report_id = _sanitize_doc_id(record.get("REPORT_ID"))
    label = str(record.get("LABEL") or "").strip() or report_id or "Untitled report"
    updated_at = str(record.get("UPDATED_AT") or record.get("CREATED_AT") or "").strip()
    if len(label) > 56:
        label = label[:53].rstrip() + "..."
    return f"📄 {label}" + (f" · {updated_at[:16]}" if updated_at else "")


def _render_saved_report_preview(record: dict) -> None:

    if not isinstance(record, dict) or not record:
        return
    report_id = _sanitize_doc_id(record.get("REPORT_ID"))
    label = str(record.get("LABEL") or "Untitled report").strip()
    desc = str(record.get("DESCRIPTION") or "").strip()
    updated_at = str(record.get("UPDATED_AT") or record.get("CREATED_AT") or "").strip()
    owner = str(record.get("OWNER") or "").strip()
    meta_parts = []
    if updated_at:
        meta_parts.append(f"Updated {html.escape(updated_at[:16])}")
    if owner:
        meta_parts.append(f"Owner {html.escape(owner)}")
    meta = " · ".join(meta_parts)
    desc_html = f"<div class='saved-report-card-desc'>{html.escape(desc)}</div>" if desc else ""
    st.markdown(
        f"""
        <div class='saved-report-preview-card'>
          <div class='saved-report-card-title'>{html.escape(label)}</div>
          <div class='saved-report-card-id'>{html.escape(report_id)}</div>
          {desc_html}
          <div class='saved-report-card-meta'>{meta}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _filter_saved_report_records(records: list[dict], query: str) -> list[dict]:
    q = str(query or "").strip().lower()
    if not q:
        return records
    out = []
    for rec in records:
        haystack = " ".join([
            str(rec.get("REPORT_ID", "")),
            str(rec.get("LABEL", "")),
            str(rec.get("DESCRIPTION", "")),
        ]).lower()
        if q in haystack:
            out.append(rec)
    return out


def _inject_saved_report_main_css() -> None:
    st.markdown("""
    <style>
      .saved-report-panel-title{
        font-size: 18px;
        font-weight: 850;
        color: #003366;
        line-height: 1.15;
        letter-spacing: -0.01em;
        margin-bottom: 4px;
      }
      .saved-report-panel-sub{
        font-size: 12.5px;
        color: #64748B;
        line-height: 1.35;
        margin-bottom: 8px;
      }
      div[data-testid="stExpander"] details:has(.saved-report-panel-title){
        border: 1px solid rgba(0,51,102,0.12) !important;
        border-radius: 18px !important;
        background: #FFFFFF !important;
        box-shadow: 0 10px 26px rgba(15,23,42,0.045) !important;
      }
      div[data-testid="stExpander"] details:has(.saved-report-panel-title) summary{
        font-weight: 800 !important;
        color: #003366 !important;
      }
      .saved-report-id-chip{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 10px;
        border-radius: 999px;
        background: #EEF6FF;
        border: 1px solid rgba(0,51,102,0.12);
        color: #003366;
        font-size: 12px;
        font-weight: 800;
        margin-top: 4px;
      }
      .saved-report-preview-card{
        margin: 10px 0 4px 0;
        padding: 12px 14px;
        border-radius: 15px;
        background: linear-gradient(180deg, #F8FAFC 0%, #FFFFFF 100%);
        border: 1px solid rgba(0,51,102,0.11);
        box-shadow: 0 7px 18px rgba(15,23,42,0.035);
      }
      .saved-report-current-card{
        margin: 4px 0 12px 0;
        padding: 11px 13px;
        border-radius: 14px;
        background: #F8FAFC;
        border: 1px solid rgba(0,51,102,0.12);
        color: #1E293B;
        font-size: 12.6px;
        line-height: 1.25;
      }
      .saved-report-current-card span{
        display: inline-flex;
        margin-top: 6px;
        color: #003366;
        font-weight: 850;
        font-size: 11.5px;
      }
      .saved-report-card-title{
        font-size: 14px;
        font-weight: 850;
        color: #003366;
        line-height: 1.2;
      }
      .saved-report-card-id{
        display: inline-flex;
        margin-top: 6px;
        padding: 4px 8px;
        border-radius: 999px;
        background: #EEF6FF;
        color: #003366;
        font-size: 11.5px;
        font-weight: 800;
        border: 1px solid rgba(0,51,102,0.10);
      }
      .saved-report-card-desc{
        margin-top: 8px;
        font-size: 12.2px;
        line-height: 1.35;
        color: #475569;
      }
      .saved-report-card-meta{
        margin-top: 8px;
        font-size: 11.5px;
        color: #64748B;
        font-weight: 650;
      }
      div[class*="st-key-load_saved_report_btn"] button,
      div[class*="st-key-save_new_report_btn"] button,
      div[class*="st-key-update_saved_report_btn"] button{
        min-height: 36px !important;
        height: 36px !important;
        padding: 0 14px !important;
        border-radius: 11px !important;
        font-size: 12.5px !important;
        font-weight: 800 !important;
      }
    </style>
    """, unsafe_allow_html=True)


def _saved_report_fragment_if_available(func):








    return func


REPORT_WORKSPACE_TABS = ["Settings", "Open Saved", "Save Current", "OVR"]

def _keep_report_workspace_open(active_tab: str | None = None) -> None:












    st.session_state["report_workspace_expanded"] = True
    if active_tab in REPORT_WORKSPACE_TABS:


        st.session_state["report_workspace_active_panel"] = active_tab
        st.session_state["report_workspace_pending_active_tab"] = active_tab


def _close_report_workspace_after_action() -> None:

    st.session_state["report_workspace_expanded"] = False


@_saved_report_fragment_if_available
def render_saved_report_loader(available_filter_options, embedded: bool = False) -> None:





    _inject_saved_report_main_css()

    notice = st.session_state.pop("saved_report_notice", None)
    if notice:
        st.success(notice)

    panel = st.container() if embedded else st.expander("Saved Reports", expanded=False)
    with panel:
        st.markdown(
            "<div class='saved-report-panel-title'>Saved Reports</div>",
            unsafe_allow_html=True,
        )

        records = list_saved_report_records(limit=120)



        st.session_state.setdefault("saved_report_committed_search_query", "")
        with st.form("saved_report_search_form", clear_on_submit=False):
            st.text_input(
                "Search",
                key="saved_report_search_query",
                placeholder="Type label, note, or ID",
            )
            search_clicked = st.form_submit_button("Search", width="content")
        if search_clicked:
            st.session_state["saved_report_committed_search_query"] = st.session_state.get("saved_report_search_query", "")
            _keep_report_workspace_open(None)

        filtered_records = _filter_saved_report_records(
            records,
            st.session_state.get("saved_report_committed_search_query", ""),
        )[:30]

        selected_id = ""
        selected_meta = None
        load_clicked = False
        if filtered_records:
            option_ids = [""] + [_sanitize_doc_id(r.get("REPORT_ID")) for r in filtered_records]
            current_selected = _sanitize_doc_id(st.session_state.get("saved_report_selected_id", ""))
            if current_selected and current_selected not in option_ids:
                st.session_state["saved_report_selected_id"] = ""

            label_map = {_sanitize_doc_id(r.get("REPORT_ID")): _saved_report_label(r) for r in filtered_records}






            with st.form("open_saved_report_form", clear_on_submit=False):
                selected_id = st.selectbox(
                    "Saved list",
                    options=option_ids,
                    key="saved_report_selected_id",
                    format_func=lambda x: "Choose saved report" if not x else label_map.get(x, x),
                )
                selected_id = _sanitize_doc_id(selected_id)
                if selected_id:
                    selected_meta = next((r for r in filtered_records if _sanitize_doc_id(r.get("REPORT_ID")) == selected_id), None)
                    if selected_meta is None:
                        selected_meta = get_saved_report_record(selected_id)
                    if selected_meta:
                        _render_saved_report_preview(selected_meta)

                load_clicked = st.form_submit_button(
                    "Open",
                    key="load_saved_report_btn",
                    width="content",
                    on_click=lambda: _keep_report_workspace_open("Open Saved"),
                )



            if load_clicked:
                selected_id = _sanitize_doc_id(st.session_state.get("saved_report_selected_id", ""))
                selected_meta = next((r for r in filtered_records if _sanitize_doc_id(r.get("REPORT_ID")) == selected_id), None)
                if selected_id and selected_meta is None:
                    selected_meta = get_saved_report_record(selected_id)
        else:
            st.caption("No saved report found.")
            load_clicked = False

        if load_clicked:
            _keep_report_workspace_open("Open Saved")
            if not selected_id:
                st.warning("Choose a saved report first.")
            else:
                record = load_document_filter_record(selected_id)
                if not record:
                    st.error("Report not found.")
                else:
                    saved_meta = selected_meta or get_saved_report_record(selected_id)
                    title = str(saved_meta.get("LABEL") if saved_meta else "").strip()




                    st.session_state["pending_saved_report_id"] = selected_id
                    st.session_state["pending_saved_report_title"] = title
                    st.session_state.pop("loaded_ovr_notice", None)
                    try:
                        st.rerun(scope="app")
                    except TypeError:
                        st.rerun()


def _apply_pending_saved_report_if_any(available_filter_options) -> None:







    pending_id = _sanitize_doc_id(st.session_state.pop("pending_saved_report_id", ""))
    pending_title = str(st.session_state.pop("pending_saved_report_title", "") or "").strip()
    if not pending_id:
        return

    record = load_document_filter_record(pending_id)
    if not record:
        st.session_state["saved_report_notice"] = "Report not found."
        return

    applied, skipped = apply_document_filter_record(record, available_filter_options)
    st.session_state.pop("loaded_ovr_notice", None)
    st.session_state["current_saved_report_id"] = pending_id
    st.session_state["current_saved_report_baseline_pending_id"] = pending_id
    st.session_state.pop("current_saved_report_state_sig", None)
    st.session_state["ovr_keep_open"] = False
    st.session_state["ovr_user_touched"] = False
    st.session_state["ovr_collapse_after_saved_report_load"] = True

    label = pending_title or pending_id
    if skipped:
        st.session_state["saved_report_notice"] = (
            f"Opened: {label}. Some saved selections are not available for the current data date."
        )
    else:
        st.session_state["saved_report_notice"] = f"Opened: {label}."
    _keep_report_workspace_open("Open Saved")


def _get_current_detail_group_cols(df: pd.DataFrame) -> list[str]:

    tab_configs = [
        ("UW Year", "UW_YEAR"),
        ("CoB", "COB"),
        ("LoB", "LOB"),
        ("INTERMEDIARY NAME", "INTERMEDIARY_NAME"),
        ("INSURED NAME", "INSURED_NAME"),
        ("MKT NAME", "MARKETING_NAME"),
        ("MKT GROUP", "MARKETING_GROUP"),
        ("BRANCH", "BRANCH"),
        ("PCKG DESC", "PCKG_DESC"),
        ("TSI", "TSI RANGE"),
        ("POLICY NO.", "POLICY_NO"),
        ("INTERMEDIARY BRANCH", "INTERMEDIARY_BRANCH"),
    ]
    label_to_col = {label: col for label, col in tab_configs if df is not None and col in df.columns}

    additional_dim_map = {
        "TOB": "TOB",
        "UW Month": "UW_MONTH",
        "Issue": "ISSUE",
        "Occupation": "OCCUPATION",
        "TSI Range": "TSI RANGE",
        "Have FAC": "HAVE FAC",
    }
    for label, col in additional_dim_map.items():

        candidate_cols = [col]
        if col == "HAVE FAC":
            candidate_cols = ["HAVE FAC", "HAVE_FAC", "HAVEFAC"]
        matched_col = next((c for c in candidate_cols if df is not None and c in df.columns), None)
        if matched_col and label not in label_to_col:
            label_to_col[label] = matched_col

    active_label = st.session_state.get("risk_profile_active_detail_tab", "UW Year")
    primary_col = label_to_col.get(active_label)
    cols = [primary_col] if primary_col else []

    selected_extra_labels = st.session_state.get("detailed_table_extra_columns", []) or []
    for label in selected_extra_labels:
        col = label_to_col.get(label)
        if col and col not in cols:
            cols.append(col)

    return cols


def _compute_current_report_state_signature(
    active_filters: dict,
    ovr_status_for_export: str,
    ovr_detail_for_export: pd.DataFrame,
) -> str:





    payload = {
        "filters": active_filters or {},
        "active_detail_tab": st.session_state.get("risk_profile_active_detail_tab", ""),
        "detail_extra_columns": st.session_state.get("detailed_table_extra_columns", []),
        "ovr_status": str(ovr_status_for_export or "Exclude OVR"),
        "ovr_detail": ovr_detail_for_export if isinstance(ovr_detail_for_export, pd.DataFrame) else [],
        "include_claim_breakdown": _get_current_include_claim_breakdown(),
        "opex_assumptions_pct": _get_opex_assumptions_pct(),
        "opex_adjust_reason": _get_opex_adjust_reason(),
    }
    return _compute_export_signature(_json_safe_value(payload))


def _get_current_saved_report_target(current_state_sig: str | None = None) -> str:






    current_id = _sanitize_doc_id(st.session_state.get("current_saved_report_id", ""))
    if not current_id:
        return ""

    if current_state_sig:
        pending_id = _sanitize_doc_id(st.session_state.get("current_saved_report_baseline_pending_id", ""))
        if pending_id and pending_id == current_id:
            st.session_state["current_saved_report_state_sig"] = current_state_sig
            st.session_state.pop("current_saved_report_baseline_pending_id", None)

        baseline_sig = str(st.session_state.get("current_saved_report_state_sig", ""))
        if baseline_sig and baseline_sig == current_state_sig:
            return current_id
        return ""

    return current_id


def _get_current_include_claim_breakdown() -> bool:

    active_label = str(st.session_state.get("risk_profile_active_detail_tab", "UW Year"))
    title_map = {
        "UW Year": "Portfolio Analysis - Detailed by UW Year",
        "CoB": "Portfolio Analysis - Detailed by CoB",
        "LoB": "Portfolio Analysis - Detailed by LoB",
        "INTERMEDIARY NAME": "Portfolio Analysis - Detailed by Intermediary",
        "INSURED NAME": "Portfolio Analysis - Detailed by Insured Name",
        "MKT NAME": "Portfolio Analysis - Detailed by Marketing Name",
        "MKT GROUP": "Portfolio Analysis - Detailed by Marketing Group",
        "BRANCH": "Portfolio Analysis - Detailed by Branch",
        "PCKG DESC": "Portfolio Analysis - Detailed by OUR TSI Range",
        "TSI": "Portfolio Analysis - Detailed by TSI Range",
        "POLICY NO.": "Portfolio Analysis - Detailed by Policy Number",
        "INTERMEDIARY BRANCH": "Portfolio Analysis - Detailed by Intermediary Branch",
    }
    tab_name = title_map.get(active_label, "Portfolio Analysis - Detailed by UW Year")
    safe_tab_name = tab_name.replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_")
    return bool(st.session_state.get(f"include_claim_summary__{safe_tab_name}", True))


def save_current_report_snapshot(
    report_id: str,
    username: str,
    label: str,
    description: str,
    active_filters: dict,
    df_ovr: pd.DataFrame,
    ovr_status_for_export: str,
    ovr_detail_for_export: pd.DataFrame,
) -> str:

    report_id = _sanitize_doc_id(report_id) or generate_unique_document_id("RP")
    group_cols = _get_current_detail_group_cols(df_ovr)
    include_claim_breakdown = _get_current_include_claim_breakdown()

    save_document_filter_log(
        doc_id=report_id,
        username=username,
        export_type="Saved Report",
        active_detail_tab=st.session_state.get("risk_profile_active_detail_tab", ""),
        detail_extra_columns=st.session_state.get("detailed_table_extra_columns", []),
        group_cols=group_cols,
        filters=active_filters,
        ovr_status=ovr_status_for_export,
        ovr_detail_df=ovr_detail_for_export,
        include_claim_breakdown=include_claim_breakdown,
        total_rows=len(df_ovr) if isinstance(df_ovr, pd.DataFrame) else None,
        file_name=f"Saved Report - {str(label or '').strip() or report_id}",
    )
    upsert_saved_report_metadata(report_id, username, label or report_id, description)
    return report_id


@_saved_report_fragment_if_available
def render_saved_report_save_controls(
    username: str,
    active_filters: dict,
    df_ovr: pd.DataFrame,
    ovr_status_for_export: str,
    ovr_detail_for_export: pd.DataFrame,
    embedded: bool = False,
) -> None:





    _inject_saved_report_main_css()

    notice = st.session_state.pop("saved_report_save_notice", None)
    if notice:
        st.success(notice)

    panel = st.container() if embedded else st.expander("Save / Update Report", expanded=False)
    with panel:
        st.markdown(
            "<div class='saved-report-panel-title'>Save Current</div>",
            unsafe_allow_html=True,
        )

        current_state_sig = _compute_current_report_state_signature(
            active_filters,
            ovr_status_for_export,
            ovr_detail_for_export,
        )
        loaded_report_id = _sanitize_doc_id(st.session_state.get("current_saved_report_id", ""))
        target_id = _get_current_saved_report_target(current_state_sig)
        view_changed_from_loaded = bool(loaded_report_id and not target_id)

        existing = get_saved_report_record(target_id) if target_id else None
        default_label = str(existing.get("LABEL") if existing else "").strip()
        default_desc = str(existing.get("DESCRIPTION") if existing else "").strip()

        if target_id:
            current_label = html.escape(default_label or "Current saved report")
            st.markdown(
                f"<div class='saved-report-current-card'>"
                f"<div><b>{current_label}</b></div>"
                f"<span>{html.escape(target_id)}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        if view_changed_from_loaded:
            st.info("Current view has changed. Save it as a new report.")

        key_suffix = hashlib.sha1(str(target_id or "new").encode("utf-8")).hexdigest()[:8]
        if embedded:


            with st.form(f"saved_report_save_form__{key_suffix}", clear_on_submit=False):
                label = st.text_input(
                    "Label",
                    key=f"saved_report_label_input__{key_suffix}",
                    value=default_label,
                    placeholder="Example: Fire portfolio high CoR review",
                )
                description = st.text_area(
                    "Keterangan",
                    key=f"saved_report_description_input__{key_suffix}",
                    value=default_desc,
                    placeholder="Optional note, context, or follow-up action",
                    height=84,
                )
                c1, c2 = st.columns([0.26, 0.30], gap="small", vertical_alignment="center")
                with c1:
                    save_new_clicked = st.form_submit_button("Save New", width="stretch")
                with c2:
                    update_clicked = st.form_submit_button("Update Current", width="stretch", disabled=not bool(target_id))
        else:
            label = st.text_input(
                "Label",
                key=f"saved_report_label_input__{key_suffix}",
                value=default_label,
                placeholder="Example: Fire portfolio high CoR review",
                on_change=lambda: _keep_report_workspace_open("Save Current"),
            )
            description = st.text_area(
                "Keterangan",
                key=f"saved_report_description_input__{key_suffix}",
                value=default_desc,
                placeholder="Optional note, context, or follow-up action",
                height=84,
                on_change=lambda: _keep_report_workspace_open("Save Current"),
            )
            c1, c2 = st.columns([0.26, 0.30], gap="small", vertical_alignment="center")
            with c1:
                save_new_clicked = st.button("Save New", key="save_new_report_btn", width="stretch")
            with c2:
                update_clicked = st.button("Update Current", key="update_saved_report_btn", width="stretch", disabled=not bool(target_id))

        if save_new_clicked:
            _keep_report_workspace_open("Save Current")
            final_label = str(label or "").strip()
            if not final_label:
                st.warning("Isi label terlebih dahulu.")
            else:
                new_id = generate_unique_document_id("RP")
                saved_id = save_current_report_snapshot(
                    new_id,
                    username,
                    final_label,
                    description,
                    active_filters,
                    df_ovr,
                    ovr_status_for_export,
                    ovr_detail_for_export,
                )
                st.session_state["saved_report_save_notice"] = f"Saved: {final_label}"
                st.session_state["current_saved_report_id"] = saved_id
                st.session_state["current_saved_report_state_sig"] = current_state_sig
                st.session_state.pop("current_saved_report_baseline_pending_id", None)
                st.success(f"Saved: {final_label}")
                st.markdown(f"<div class='saved-report-id-chip'>Report ID: {html.escape(saved_id)}</div>", unsafe_allow_html=True)

        if update_clicked:
            _keep_report_workspace_open("Save Current")
            final_label = str(label or default_label or target_id).strip()
            saved_id = save_current_report_snapshot(
                target_id,
                username,
                final_label,
                description,
                active_filters,
                df_ovr,
                ovr_status_for_export,
                ovr_detail_for_export,
            )
            st.session_state["saved_report_save_notice"] = f"Updated: {final_label}"
            st.session_state["current_saved_report_id"] = saved_id
            st.session_state["current_saved_report_state_sig"] = current_state_sig
            st.session_state.pop("current_saved_report_baseline_pending_id", None)
            st.success(f"Updated: {final_label}")
            st.markdown(f"<div class='saved-report-id-chip'>Report ID: {html.escape(saved_id)}</div>", unsafe_allow_html=True)






st.markdown("""
    <style>
      /* ===== KPI CARDS: compact landscape + left aligned + no overflow ===== */
      .kpi-card.kpi-compact3{
        box-sizing: border-box !important;
        height: 108px !important;                 /* landscape */
        padding: 12px 16px !important;
        border-radius: 22px !important;

        display: flex !important;
        flex-direction: column !important;
        justify-content: flex-start !important;
        align-items: flex-start !important;
        text-align: left !important;

        gap: 2px !important;                      /* title closer to value */
        overflow: hidden !important;
      }

      .kpi-card.kpi-compact3 h4{
        margin: 0 !important;
        font-size: 12.5px !important;
        line-height: 1.15 !important;
        font-weight: 650 !important;
        text-align: left !important;

        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        max-width: 100% !important;
        opacity: 0.9 !important;
      }

      /* allow only GWP title to wrap max 2 lines, without pushing number out */
      .kpi-card.kpi-compact3.kpi-gwp h4{
        white-space: normal !important;
        display: -webkit-box !important;
        -webkit-line-clamp: 2 !important;
        -webkit-box-orient: vertical !important;
        margin-bottom: 2px !important;
      }

      .kpi-card.kpi-compact3 h2{
        margin: 0 !important;
        margin-top: -1px !important;              /* pull value up slightly */
        font-size: 30px !important;               /* smaller so never keluar */
        line-height: 1.05 !important;
        font-weight: 800 !important;
        text-align: left !important;

        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        max-width: 100% !important;
      }

      /* ===== CoR danger: make it NOTICEABLE without changing size ===== */
      @keyframes corFlashTight {
          0%, 100% {
            transform: translateY(0);
            box-shadow:
              0 10px 26px rgba(0,0,0,0.18),
              0 0 0 2px rgba(190, 0, 40, 0.6) inset;
          }
        
          50% {
            transform: translateY(-3px);
            box-shadow:
              0 22px 55px rgba(190, 0, 40, 0.45),
              0 0 0 10px rgba(220, 0, 50, 1) inset,
              0 0 35px rgba(255, 0, 60, 0.8);
          }
        }
        
        .kpi-card.kpi-compact3.kpi-danger{
          animation: corFlashTight 1.2s ease-in-out infinite !important;
        }
      /* ===== Elegant toast (noticeable, clean) ===== */
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

        width: min(460px, calc(100vw - 44px));
        padding: 14px 16px;
        border-radius: 14px;

        background: rgba(176,0,32,0.96);
        color: #fff;

        box-shadow: 0 18px 40px rgba(0,0,0,0.22);
        border: 1px solid rgba(255,255,255,0.20);

        display: flex;
        gap: 10px;
        align-items: flex-start;

        animation: toastInOut 6.2s ease-in-out forwards;
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
        font-weight: 650;
      }

      .claim-breakdown-toast {
        top: 118px !important;
        right: 22px !important;
        z-index: 10000 !important;
        width: min(430px, calc(100vw - 44px)) !important;
        background: linear-gradient(135deg, rgba(12, 110, 106, 0.98), rgba(19, 141, 117, 0.98)) !important;
        border-left: 5px solid #B8FFF1 !important;
        box-shadow: 0 22px 50px rgba(8, 77, 74, 0.34) !important;
        animation: toastInOut 5.0s ease-in-out forwards !important;
      }
      .claim-breakdown-toast .icon{
        width: 22px; height: 22px;
        border-radius: 999px;
        background: rgba(255,255,255,0.22);
        color: #F4FFFD;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 900;
        flex: 0 0 auto;
        margin-top: 1px;
      }
      .claim-breakdown-toast .txt{
        font-size: 13.5px;
        line-height: 1.3;
        font-weight: 650;
        color: #FFFFFF;
      }
    </style>
    """, unsafe_allow_html=True)

st.markdown("""
    <style>
      .direct-download-btn {
        display: inline-block;
        width: auto;
        box-sizing: border-box;
        text-align: left;
        padding: 0;
        border-radius: 0;
        background: transparent;
        color: #003366 !important;
        border: none;
        text-decoration: underline !important;
        text-underline-offset: 3px;
        font-weight: 700;
        font-size: 13px;
      }
      .direct-download-btn:hover {
        color: #E39A5B !important;
        background: transparent;
        border: none;
      }
      .direct-download-btn.is-ready {
        background: transparent;
        border: none;
      }
      .direct-download-btn.is-ready:hover {
        background: transparent;
        border: none;
      }
    </style>
    """, unsafe_allow_html=True)




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
            if nunique and (nunique <= 5000) and (nunique / n <= 0.45):
                out[col] = out[col].astype("category")
        except Exception:
            pass

    return out


RISK_PROFILE_SNAPSHOTS = {
    '241227_27 Desember 2024': ('RP241227_part1.xlsx', 'RP241227_part2.xlsx'),
    '260102_02 Januari 2026': ('RP260102_part1.xlsx', 'RP260102_part2.xlsx'),
    '260327_27 Maret 2026': ('RP260327_part1.xlsx', 'RP260327_part2.xlsx'),
    '260417_17 April 2026': ('RP260417_part1.xlsx', 'RP260417_part2.xlsx'),
    '260501_01 Mei 2026': ('RP260501_part1.xlsx', 'RP260501_part2.xlsx'),
    '260528_28 Mei 2026': ('RP260528_part1.xlsx', 'RP260528_part2.xlsx'),
    '260612_26 Juni 2026': ('RP260626v1_part1.xlsx', 'RP260626v1_part2.xlsx'),
    '260731_31 Juli 2026': ('RP260731_part1.xlsx', 'RP260731_part2.xlsx'),
    '260828_28 Agustus 2026': ('RP260828_part1.xlsx', 'RP260828_part2.xlsx'),
    '260911_11 September 2026': ('RP260911_part1.xlsx', 'RP260911_part2.xlsx'),
    '261002_02 Oktober 2026': ('RP261002_part1.xlsx', 'RP261002_part2.xlsx'),
    '261016_16 Oktober 2026': ('RP261016_part1.xlsx', 'RP261016_part2.xlsx'),
    '261030_30 Oktober 2026': ('RP261030_part1.xlsx', 'RP261030_part2.xlsx'),
}


RISK_PROFILE_CLAIM_PATH = "CLAIM Agustus 2026.xlsx"
RISK_PROFILE_EXCEL_DIRECTORY = Path("risk_profile_excel")


def _read_risk_profile_snapshot(paths: tuple):
    parts = [pd.read_excel(path) for path in paths]
    df = pd.concat(parts, ignore_index=True, copy=False)
    return _optimize_df_memory(df)


def load_all_data(paths: tuple):
    return _read_risk_profile_snapshot(paths)


def preload_risk_profile_sources():

    for paths in RISK_PROFILE_SNAPSHOTS.values():
        _read_risk_profile_snapshot(paths)

    pd.read_excel(RISK_PROFILE_CLAIM_PATH)

    if RISK_PROFILE_EXCEL_DIRECTORY.is_dir():
        for path in sorted(RISK_PROFILE_EXCEL_DIRECTORY.iterdir()):
            if path.is_file() and not path.name.startswith("~$") and path.suffix.lower() == ".xlsx":
                pd.read_excel(path, sheet_name=None)

def get_unique_vals(df, col):
    return sorted(df[col].dropna().unique())


EXCEL_ALWAYS_HIDDEN_METRICS = ("BASE_PREMIUM", "OUR_DISCOUNT")
EXCEL_REINSURANCE_BREAKDOWN_METRICS = ("PREM TREATY", "PREM FAC", "COMM RI", "COMM FAC")
EXCEL_METRIC_ALIASES = {
    "BASE_PREMIUM": ("BASE_PREMIUM", "BASE PREMIUM"),
    "OUR_DISCOUNT": ("OUR_DISCOUNT", "OUR DISCOUNT"),
    "PREM TREATY": ("PREM TREATY", "PREM_TREATY", "PREMIUM TREATY", "PREMIUM_TREATY"),
    "PREM FAC": ("PREM FAC", "PREM_FAC", "PREMIUM FAC", "PREMIUM_FAC"),
    "COMM RI": ("COMM RI", "COMM_RI", "COMMISSION RI", "COMMISSION_RI"),
    "COMM FAC": ("COMM FAC", "COMM_FAC", "COMMISSION FAC", "COMMISSION_FAC"),
}


def _resolve_excel_metric_source_col(df: pd.DataFrame, output_col: str) -> str | None:
    if df is None:
        return None
    cols_by_norm = {
        str(col).strip().upper().replace("_", " "): col
        for col in df.columns
    }
    for alias in EXCEL_METRIC_ALIASES.get(output_col, (output_col,)):
        hit = cols_by_norm.get(str(alias).strip().upper().replace("_", " "))
        if hit is not None:
            return hit
    return None


def _normalize_excel_reinsurance_mode(value: str) -> str:
    value = str(value or "").strip().lower()
    return "breakdown" if value in {"breakdown", "including reinsurance breakdown", "include breakdown"} else "simplified"


def _excel_reinsurance_mode_label(value: str) -> str:
    return (
        "Including Reinsurance Breakdown"
        if _normalize_excel_reinsurance_mode(value) == "breakdown"
        else "Simplify Reinsurance Items"
    )


def _set_excel_reinsurance_mode(mode_key: str, mode: str) -> None:
    st.session_state[mode_key] = _normalize_excel_reinsurance_mode(mode)


def _inject_prepare_excel_menu_css() -> None:

    return None


def cached_pivot(df, index_cols, row_limit=500, extra_value_cols=()):
    return make_pivot(
        df,
        list(index_cols),
        row_limit=row_limit,
        extra_value_cols=list(extra_value_cols or ()),
    )

def load_claim_data(path: str):

    return pd.read_excel(path)


def _sync_multiselect_state(key, options):
    valid = [v for v in st.session_state.get(key, []) if v in options]
    st.session_state[key] = valid
    return valid

def _normalize_filter_compare_value(value) -> str:

    try:
        if pd.isna(value):
            return "<NA>"
    except Exception:
        pass
    text = str(value).strip()
    try:
        num = float(text.replace(",", ""))
        if num.is_integer():
            text = str(int(num))
    except Exception:
        pass
    return text.lower()


def _selection_represents_all(selected_values, available_options) -> bool:

    selected_values = list(selected_values or [])
    available_options = list(available_options or [])
    if not selected_values or not available_options:
        return False
    selected_keys = {_normalize_filter_compare_value(v) for v in selected_values}
    option_keys = {_normalize_filter_compare_value(v) for v in available_options}
    return bool(option_keys) and selected_keys == option_keys


MAX_DIRECT_MULTISELECT_FILTER_VALUES = 1000
MAX_SELECT_ALL_MATCHED_VALUES = 1000
_SELECT_ALL_MATCHED_PREFIX = "__SELECT_ALL_MATCHED__::"


def _selection_is_too_large_for_direct_filter(selected_values, limit: int = MAX_DIRECT_MULTISELECT_FILTER_VALUES) -> bool:
    try:
        return len(list(selected_values or [])) > int(limit)
    except Exception:
        return False


def _normalize_filter_search_text(value) -> str:

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return " ".join(str(value).strip().casefold().split())


def _lazy_substring_matches(
    values,
    query: str,
    limit: int = MAX_SELECT_ALL_MATCHED_VALUES,
):






    query_norm = _normalize_filter_search_text(query)
    limit = max(1, int(limit or MAX_SELECT_ALL_MATCHED_VALUES))
    if not query_norm:
        return [], False

    try:
        series = values if isinstance(values, pd.Series) else pd.Series(values)
        text_series = series.astype("string").str.strip()
        normalized = text_series.str.casefold()
        mask = normalized.str.contains(query_norm, regex=False, na=False)
        matched = (
            text_series[mask]
            .dropna()
            .loc[lambda s: s.ne("")]
            .drop_duplicates()
            .head(limit + 1)
            .tolist()
        )
    except Exception:
        matched = []
        seen = set()
        for value in list(values):
            normalized_value = _normalize_filter_search_text(value)
            if query_norm not in normalized_value:
                continue
            key = _normalize_filter_compare_value(value)
            if key in seen:
                continue
            seen.add(key)
            matched.append(str(value))
            if len(matched) > limit:
                break

    truncated = len(matched) > limit
    return matched[:limit], truncated

def _select_all_matched_token(widget_key: str) -> str:
    return f"{_SELECT_ALL_MATCHED_PREFIX}{widget_key}"


def _dedupe_filter_values(values):
    out = []
    seen = set()
    for value in list(values):
        key = _normalize_filter_compare_value(value)
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _guard_multiselect_selection_callback(
    sel_key: str,
    available_options,
    col_name: str = "",
    select_all_token: str | None = None,
    matched_options=None,
) -> None:

    selected_values = list(st.session_state.get(sel_key, []) or [])
    available_options = list(available_options or [])

    if select_all_token and select_all_token in selected_values:
        existing = [v for v in selected_values if v != select_all_token]
        matched = list(matched_options or [])[:MAX_SELECT_ALL_MATCHED_VALUES]


        merged = _dedupe_filter_values(matched + existing)
        merged = merged[:MAX_DIRECT_MULTISELECT_FILTER_VALUES]
        st.session_state[sel_key] = merged
        st.session_state[f"{sel_key}__matched_notice"] = len(matched)
        selected_values = merged

    if (
        _selection_represents_all(selected_values, available_options)
        or _selection_is_too_large_for_direct_filter(selected_values)
    ):
        st.session_state[sel_key] = []
        st.session_state[f"{sel_key}__guard_notice"] = True


def _sanitize_multiselect_state_before_widget(sel_key: str, available_options) -> None:

    selected_values = [
        v for v in list(st.session_state.get(sel_key, []) or [])
        if not (isinstance(v, str) and v.startswith(_SELECT_ALL_MATCHED_PREFIX))
    ]
    available_options = list(available_options or [])
    if (
        _selection_represents_all(selected_values, available_options)
        or _selection_is_too_large_for_direct_filter(selected_values)
    ):
        st.session_state[sel_key] = []
        st.session_state[f"{sel_key}__guard_notice"] = True
    elif selected_values != list(st.session_state.get(sel_key, []) or []):
        st.session_state[sel_key] = selected_values


def _render_guarded_filter_multiselect(
    label: str,
    options,
    key: str,
    disabled: bool = False,
    *,
    help_text: str | None = None,
):





    options = list(options or [])
    kwargs = dict(
        label=label,
        options=options,
        key=key,
        disabled=disabled,
        on_change=_guard_multiselect_selection_callback,
        args=(key, options, label, None, None),
    )
    if help_text:
        kwargs["help"] = help_text
    if len(options) > MAX_DIRECT_MULTISELECT_FILTER_VALUES:
        kwargs["max_selections"] = MAX_DIRECT_MULTISELECT_FILTER_VALUES

    try:
        return st.multiselect(**kwargs)
    except TypeError:

        kwargs.pop("max_selections", None)
        return st.multiselect(**kwargs)


def _render_lazy_search_multiselect(
    label: str,
    value_source,
    key: str,
    disabled: bool = False,
    *,
    search_key: str,
    search_label: str = "Search items",
    search_placeholder: str = "Type, then press Enter",
    help_text: str | None = None,
):







    draft_key = f"{search_key}__draft"
    committed_key = f"{search_key}__committed"
    form_key = f"{key}__lazy_search_form"


    if draft_key not in st.session_state:
        st.session_state[draft_key] = str(st.session_state.get(search_key, "") or "")
    if committed_key not in st.session_state:
        st.session_state[committed_key] = ""

    with st.form(form_key, clear_on_submit=False, border=False):
        st.text_input(
            search_label,
            key=draft_key,
            placeholder=search_placeholder,
            disabled=disabled,
            help=help_text,
        )
        submitted = st.form_submit_button(
            "Search",
            disabled=disabled,
            width="content",
        )

    if submitted:
        committed = str(st.session_state.get(draft_key, "") or "").strip()
        st.session_state[committed_key] = committed

        st.session_state[search_key] = committed

    query = str(st.session_state.get(committed_key, "") or "").strip()
    previous = [
        v for v in list(st.session_state.get(key, []) or [])
        if not (isinstance(v, str) and v.startswith(_SELECT_ALL_MATCHED_PREFIX))
    ]


    try:
        if previous:
            source_text = (value_source if isinstance(value_source, pd.Series) else pd.Series(value_source)).astype("string").str.strip()
            existing = set(source_text[source_text.isin([str(v) for v in previous])].dropna().unique().tolist())
            previous = [v for v in previous if str(v) in existing]
    except Exception:
        pass

    matched_options = []
    truncated = False
    select_all_token = None
    if query and not disabled:
        matched_options, truncated = _lazy_substring_matches(
            value_source,
            query,
            limit=MAX_SELECT_ALL_MATCHED_VALUES,
        )
        select_all_token = _select_all_matched_token(key)

    matched_keys = {_normalize_filter_compare_value(v) for v in matched_options}
    previous_not_matched = [
        v for v in previous
        if _normalize_filter_compare_value(v) not in matched_keys
    ]

    if select_all_token is not None:
        widget_options = [select_all_token] + matched_options + previous_not_matched
    else:


        widget_options = previous

    widget_options = _dedupe_filter_values(widget_options)
    if previous != list(st.session_state.get(key, []) or []):
        st.session_state[key] = previous

    def _format_option(value):
        if value == select_all_token:
            suffix = " (first 250)" if truncated else ""
            return f"Select all matched — {len(matched_options)} item{suffix}"
        return str(value)

    kwargs = dict(
        label=label,
        options=widget_options,
        key=key,
        disabled=disabled,
        on_change=_guard_multiselect_selection_callback,
        args=(key, [], label, select_all_token, matched_options),
        format_func=_format_option,
        max_selections=MAX_DIRECT_MULTISELECT_FILTER_VALUES,
    )
    try:
        selected = st.multiselect(**kwargs)
    except TypeError:
        kwargs.pop("max_selections", None)
        selected = st.multiselect(**kwargs)

    if not disabled:
        if not query:
            st.caption("Ketik kata pencarian lalu tekan Enter. Daftar belum dimuat sebelum pencarian dijalankan.")
        elif matched_options:
            cap_note = " Hanya 250 hasil pertama yang dimuat." if truncated else ""
            st.caption(f"{len(matched_options)} hasil dimuat.{cap_note}")
        else:
            st.caption("Tidak ada hasil yang cocok.")

    matched_notice = st.session_state.pop(f"{key}__matched_notice", None)
    if matched_notice is not None:
        st.caption(f"{int(matched_notice):,} matched item(s) selected.")

    return [
        v for v in list(selected or [])
        if not (isinstance(v, str) and v.startswith(_SELECT_ALL_MATCHED_PREFIX))
    ]

def _is_filter_selection_active(mode: str, selected_values, available_options) -> bool:

    mode = str(mode or "").strip()
    selected_values = list(selected_values or [])

    if mode in ("Include All", "Exclude All"):
        return mode == "Exclude All"
    if mode not in ("Include Selected", "Exclude Selected"):
        return False
    if not selected_values:
        return False
    if _selection_represents_all(selected_values, available_options):
        return False
    if _selection_is_too_large_for_direct_filter(selected_values):
        return False
    return True


def _inject_multiselect_select_all_guard_css(has_large_filter: bool) -> None:







    if not has_large_filter:
        return
    st.markdown(
        """
        <style>
          /* Streamlit/BaseWeb multiselect dropdown Select-all guard.
             The selectors below cover multiple Streamlit versions. */
          div[data-testid="stVirtualDropdown"] [data-testid*="SelectAll"],
          div[data-testid="stVirtualDropdown"] [aria-label="Select all"],
          div[data-testid="stVirtualDropdown"] [title="Select all"],
          div[data-testid="stVirtualDropdown"] button[aria-label="Select all"],
          div[data-testid="stVirtualDropdown"] label[aria-label="Select all"],
          div[data-baseweb="popover"] [data-testid*="SelectAll"],
          div[data-baseweb="popover"] [aria-label="Select all"],
          div[data-baseweb="popover"] [title="Select all"],
          div[data-baseweb="popover"] button[aria-label="Select all"],
          div[data-baseweb="popover"] label[aria-label="Select all"] {
            display: none !important;
            visibility: hidden !important;
            pointer-events: none !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _is_filter_info_active(info: dict) -> bool:

    if not isinstance(info, dict):
        return False
    mode = str(info.get("mode", "") or "").strip()
    vals = info.get("values", []) or []
    vals_norm = [str(v).strip().lower() for v in vals]
    if mode in ("Include All", "All"):
        return False
    if mode == "Exclude All":
        return True
    if mode not in ("Include Selected", "Exclude Selected"):
        return False
    if not vals_norm or vals_norm == ["all"]:
        return False
    if len(vals_norm) > MAX_DIRECT_MULTISELECT_FILTER_VALUES:
        return False
    return True


def _active_filters_only(filters: dict) -> dict:
    return {col: info for col, info in (filters or {}).items() if _is_filter_info_active(info)}



def _can_view_memory_usage(username: str) -> bool:
    return str(username).strip().lower() == "actuary@mnc-insurance.com"


def _format_bytes(num_bytes):
    if num_bytes is None:
        return "N/A"
    num = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num) < 1024.0 or unit == "TB":
            return f"{num:,.1f} {unit}"
        num /= 1024.0


def _get_process_memory_bytes():
    try:
        import os
        import psutil
        return int(psutil.Process(os.getpid()).memory_info().rss)
    except Exception:
        return None


def _df_memory_bytes(df: pd.DataFrame):
    try:
        if df is None:
            return None
        return int(df.memory_usage(deep=True).sum())
    except Exception:
        return None


def _render_memory_usage(username, df_base=None, df_view=None, df_work=None):
    if not _can_view_memory_usage(username):
        return

    process_mem = _get_process_memory_bytes()
    base_mem = _df_memory_bytes(df_base)
    view_mem = _df_memory_bytes(df_view)
    work_mem = _df_memory_bytes(df_work)

    with st.sidebar.expander("Memory Usage", expanded=False):
        st.caption(f"App RAM: {_format_bytes(process_mem)}")
        if df_base is not None:
            st.caption(
                f"Base DF: {_format_bytes(base_mem)} "
                f"({len(df_base):,} rows × {len(df_base.columns):,} cols)"
            )
        if df_view is not None:
            st.caption(
                f"Filtered DF: {_format_bytes(view_mem)} "
                f"({len(df_view):,} rows × {len(df_view.columns):,} cols)"
            )
        if df_work is not None:
            st.caption(
                f"Working DF: {_format_bytes(work_mem)} "
                f"({len(df_work):,} rows × {len(df_work.columns):,} cols)"
            )






def _safe_to_float(x, default=0.0):
    try:
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return default
        return float(x)
    except Exception:
        return default


def _make_ovr_key(frame: pd.DataFrame, dims: list[str]) -> pd.Series:

    if frame is None or not dims:
        return pd.Series([], dtype="string")

    key = None
    for col in dims:
        part = frame[col].astype("string").fillna("<NA>").str.strip()
        key = part if key is None else key.str.cat(part, sep="\x1f")
    return key


def _commit_ovr_configuration() -> None:

    rules = st.session_state.get("ovr_rules_df")
    st.session_state["risk_profile_applied_ovr"] = {
        "mode": st.session_state.get("ovr_mode", "uniform"),
        "uniform_pct": _safe_to_float(st.session_state.get("ovr_uniform_pct_input", 0.0)),
        "dims": list(st.session_state.get("ovr_dims", []) or []),
        "rules_df": rules.copy(deep=True) if isinstance(rules, pd.DataFrame) else pd.DataFrame(),
    }


def _get_applied_ovr_configuration() -> dict | None:
    if "risk_profile_applied_ovr" not in st.session_state:

        if st.session_state.get("ovr_applied", False) and st.session_state.get("ovr_confirmed", False):
            _commit_ovr_configuration()
    return st.session_state.get("risk_profile_applied_ovr")


def _ensure_portfolio_cost_columns(df: pd.DataFrame) -> pd.DataFrame:

    if df is None or df.empty or "OPEX_AMT" in df.columns:
        return df
    return _apply_opex_assumptions_to_df(df)


def apply_ovr_to_df(df: pd.DataFrame) -> pd.DataFrame:








    if df is None or df.empty:
        return df

    if "GWP_AMT" not in df.columns:
        out = df.copy()
        out["OVR_PCT"] = 0.0
        out["OVR_AMT"] = 0.0
        return out

    df = df.drop(columns=["OVR_PCT", "OVR_AMT"], errors="ignore")
    config = _get_applied_ovr_configuration()
    if config is None:
        return df
    mode = config.get("mode", "uniform")

    if mode == "uniform":
        pct_input = _safe_to_float(config.get("uniform_pct", 0.0), 0.0)
        pct = pct_input / 100.0

        if abs(pct) < 1e-12:
            return df

        out = df.copy()
        gwp = pd.to_numeric(out["GWP_AMT"], errors="coerce").fillna(0.0)
        out["OVR_PCT"] = pct
        out["OVR_AMT"] = gwp.to_numpy() * pct
        return out

    dims = config.get("dims", []) or []
    dims = [d for d in dims if d in df.columns]



    default_pct = 0.0

    rules_df = config.get("rules_df")

    if rules_df is None or not isinstance(rules_df, pd.DataFrame) or rules_df.empty or not dims:
        if abs(default_pct) < 1e-12:
            return df

        out = df.copy()
        gwp = pd.to_numeric(out["GWP_AMT"], errors="coerce").fillna(0.0)
        out["OVR_PCT"] = default_pct
        out["OVR_AMT"] = gwp.to_numpy() * default_pct
        return out

    rules = rules_df.copy()

    if "OVR_PCT_INPUT" not in rules.columns:
        for alt in ["OVR_PCT", "OVR %", "OVR"]:
            if alt in rules.columns:
                rules.rename(columns={alt: "OVR_PCT_INPUT"}, inplace=True)
                break

    keep_cols = [c for c in dims if c in rules.columns]
    if "OVR_PCT_INPUT" in rules.columns:
        keep_cols.append("OVR_PCT_INPUT")

    if not keep_cols or "OVR_PCT_INPUT" not in keep_cols:
        if abs(default_pct) < 1e-12:
            return df

        out = df.copy()
        gwp = pd.to_numeric(out["GWP_AMT"], errors="coerce").fillna(0.0)
        out["OVR_PCT"] = default_pct
        out["OVR_AMT"] = gwp.to_numpy() * default_pct
        return out

    rules = rules[keep_cols].copy()
    rules["OVR_PCT_INPUT"] = pd.to_numeric(rules["OVR_PCT_INPUT"], errors="coerce")
    rules = rules.dropna(subset=["OVR_PCT_INPUT"])

    if rules.empty:
        if abs(default_pct) < 1e-12:
            return df

        out = df.copy()
        gwp = pd.to_numeric(out["GWP_AMT"], errors="coerce").fillna(0.0)
        out["OVR_PCT"] = default_pct
        out["OVR_AMT"] = gwp.to_numpy() * default_pct
        return out

    rules_key = _make_ovr_key(rules, dims)
    rules = rules.assign(__ovr_key=rules_key)
    rules = rules.drop_duplicates(subset=["__ovr_key"], keep="last")

    rule_map = pd.Series(
        (rules["OVR_PCT_INPUT"].astype(float) / 100.0).to_numpy(),
        index=rules["__ovr_key"],
    )

    df_key = _make_ovr_key(df, dims)
    pct_dec = df_key.map(rule_map).fillna(default_pct).astype(float)

    if float(pct_dec.abs().sum()) < 1e-12:
        return df

    out = df.copy()
    gwp = pd.to_numeric(out["GWP_AMT"], errors="coerce").fillna(0.0)
    out["OVR_PCT"] = pct_dec.to_numpy()
    out["OVR_AMT"] = gwp.to_numpy() * out["OVR_PCT"].to_numpy()

    return out


def no_data_warning():
    st.markdown(
    "<div style='text-align:center; color:gray; font-size:16px; padding:40px;'>"
    "No data on this filter"
    "</div>",
    unsafe_allow_html=True
)

import hashlib


def _render_html_block(html_content: str, height: int = 300, scrolling: bool = False) -> None:

    src = "data:text/html;base64," + base64.b64encode(html_content.encode("utf-8")).decode("ascii")
    components.iframe(src, height=height, scrolling=scrolling)
def short_hash(text, length=12):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length].upper()





def _get_app_base_url() -> str:

    try:
        configured = str(st.secrets.get("app", {}).get("base_url", "") or "").strip().rstrip("/")
        if configured:
            return configured
    except Exception:
        pass
    try:
        host = st.context.headers.get("host") or st.context.headers.get("x-forwarded-host")
        proto = st.context.headers.get("x-forwarded-proto") or "https"
        if host:
            return f"{proto}://{host}".rstrip("/")
    except Exception:
        pass
    return "https://superapp-actuary-mncai.streamlit.app"


def _rp_verification_payload(
    doc_id: str,
    username: str,
    filters: dict,
    ovr_status: str,
    ovr_detail_df: pd.DataFrame | None,
    include_claim_breakdown: bool,
    opex_non_fronting_pct=None,
    opex_fronting_pct=None,
    opex_adjust_reason=None,
) -> dict:

    active_filters = _active_filters_only(filters or {})
    ovr_detail = ovr_detail_df if isinstance(ovr_detail_df, pd.DataFrame) else pd.DataFrame()
    current_non, current_front = _get_opex_assumptions_pct()
    opex_non = _safe_to_float(opex_non_fronting_pct, current_non)
    opex_front = _safe_to_float(opex_fronting_pct, current_front)
    if opex_adjust_reason is None:
        opex_reason = _get_opex_adjust_reason()
    else:
        opex_reason = str(opex_adjust_reason or "").strip()
    if not _opex_assumptions_are_adjusted(opex_non, opex_front):
        opex_reason = ""
    return {
        "DOC_ID": _sanitize_doc_id(doc_id),
        "USERNAME": str(username or "").strip(),
        "MODULE": "Risk Profile",
        "EXPORT_TYPE": "PDF",
        "FILTERS": _json_safe_value(active_filters),
        "OVR_STATUS": str(ovr_status or "Exclude OVR").strip(),
        "OVR_DETAIL": _json_safe_value(ovr_detail),
        "INCLUDE_CLAIM_BREAKDOWN": bool(include_claim_breakdown),
        "OPEX_NON_FRONTING_PCT": opex_non,
        "OPEX_FRONTING_PCT": opex_front,
        "OPEX_ADJUST_REASON": opex_reason,
    }


def compute_rp_pdf_verification_hash(
    doc_id: str,
    username: str,
    filters: dict,
    ovr_status: str,
    ovr_detail_df: pd.DataFrame | None,
    include_claim_breakdown: bool,
    opex_non_fronting_pct=None,
    opex_fronting_pct=None,
    opex_adjust_reason=None,
) -> str:
    payload = _rp_verification_payload(
        doc_id, username, filters, ovr_status, ovr_detail_df, include_claim_breakdown,
        opex_non_fronting_pct, opex_fronting_pct, opex_adjust_reason,
    )
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(("RISKPROFILE-PDF-V1|" + raw).encode("utf-8")).hexdigest()[:12].upper()


def _build_rp_verify_url(doc_id: str, verification_code: str) -> str:
    from urllib.parse import quote
    return f"{_get_app_base_url()}/?verify_rp={quote(_sanitize_doc_id(doc_id))}&code={quote(str(verification_code or '').upper())}"


def _build_rp_open_report_url(doc_id: str) -> str:

    from urllib.parse import quote
    return f"{_get_app_base_url()}/?open_rp={quote(_sanitize_doc_id(doc_id))}"


def _get_query_param_value(name: str, default: str = "") -> str:

    try:
        value = st.query_params.get(name, default)
        if isinstance(value, list):
            return str(value[0]) if value else default
        return str(value or default)
    except Exception:
        pass
    try:
        params = st.experimental_get_query_params()
        value = params.get(name, [default])
        if isinstance(value, list):
            return str(value[0]) if value else default
        return str(value or default)
    except Exception:
        return default


def _capture_open_report_query_if_any() -> None:






    doc_id = _sanitize_doc_id(_get_query_param_value("open_rp"))
    if not doc_id:
        return


    if st.session_state.get("last_open_rp_query_applied") == doc_id:
        return

    st.session_state["pending_saved_report_id"] = doc_id
    st.session_state["pending_saved_report_title"] = doc_id
    st.session_state["report_workspace_expanded"] = True
    st.session_state["report_workspace_active_panel"] = "Open Saved"
    st.session_state["report_workspace_pending_active_tab"] = "Open Saved"
    st.session_state["last_open_rp_query_applied"] = doc_id


def _record_bool(value) -> bool:
    text = str(value if value is not None else "").strip().lower()
    return text in ("true", "1", "yes", "y", "include", "included")


def _format_verification_filters(filters: dict) -> str:

    active = _active_filters_only(filters or {})
    if not active:
        return "No active filters"

    parts = []
    for col, info in active.items():
        if not isinstance(info, dict):
            continue
        mode = str(info.get("mode", "") or "").strip()
        values = info.get("values", []) or []
        if not isinstance(values, (list, tuple, set)):
            values = [values]
        values_text = ", ".join(str(v) for v in list(values)[:8])
        if len(values) > 8:
            values_text += f", +{len(values) - 8} more"
        parts.append(f"{col}: {mode}" + (f" ({values_text})" if values_text else ""))
    return "\n".join(parts) if parts else "No active filters"


def render_rp_pdf_verification_page() -> None:





    doc_id = _sanitize_doc_id(_get_query_param_value("verify_rp"))
    code = str(_get_query_param_value("code")).strip().upper()

    st.markdown(
        """
        <style>
          .verify-wrap{max-width:860px;margin:42px auto 24px auto;padding:0 18px;}
          .verify-card{background:#fff;border:1px solid rgba(0,51,102,.12);border-radius:22px;
            box-shadow:0 18px 55px rgba(15,23,42,.08);padding:26px 28px;}
          .verify-title{font-size:26px;font-weight:900;color:#003366;margin-bottom:6px;letter-spacing:-.02em;}
          .verify-sub{font-size:14px;color:#64748B;line-height:1.45;margin-bottom:18px;}
          .verify-ok{background:#ECFDF5;color:#047857;border:1px solid rgba(4,120,87,.20);border-radius:15px;padding:12px 14px;font-weight:850;margin:12px 0 16px 0;}
          .verify-bad{background:#FEF2F2;color:#B91C1C;border:1px solid rgba(185,28,28,.20);border-radius:15px;padding:12px 14px;font-weight:850;margin:12px 0 16px 0;}
          .verify-grid{display:grid;grid-template-columns:190px 1fr;gap:8px 16px;font-size:13.5px;line-height:1.35;}
          .verify-label{color:#64748B;font-weight:750;}.verify-value{color:#0F172A;font-weight:750;word-break:break-word;}
          .verify-filter{white-space:pre-wrap;background:#F8FAFC;border:1px solid rgba(15,23,42,.08);border-radius:14px;padding:12px 13px;color:#334155;font-size:13px;line-height:1.45;margin-top:6px;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div class='verify-wrap'><div class='verify-card'>", unsafe_allow_html=True)
    st.markdown("<div class='verify-title'>Risk Profile PDF Verification</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='verify-sub'>This page verifies whether the scanned PDF matches the document record saved by the system.</div>",
        unsafe_allow_html=True,
    )

    if not doc_id or not code:
        st.markdown("<div class='verify-bad'>Verification link is incomplete.</div>", unsafe_allow_html=True)
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    record = load_document_filter_record(doc_id)
    if not record:
        st.markdown("<div class='verify-bad'>Document ID was not found.</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='verify-grid'><div class='verify-label'>Document ID</div><div class='verify-value'>{html.escape(doc_id)}</div></div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    filters = _from_json_text(record.get("FILTERS_JSON"), default={})
    ovr_detail_raw = _from_json_text(record.get("OVR_DETAIL_JSON"), default=[])
    ovr_detail_df = pd.DataFrame(ovr_detail_raw) if isinstance(ovr_detail_raw, list) else pd.DataFrame()
    include_claim_breakdown = _record_bool(record.get("INCLUDE_CLAIM_BREAKDOWN"))
    expected_code = compute_rp_pdf_verification_hash(
        doc_id=doc_id,
        username=record.get("USERNAME", ""),
        filters=filters,
        ovr_status=record.get("OVR_STATUS", "Exclude OVR"),
        ovr_detail_df=ovr_detail_df,
        include_claim_breakdown=include_claim_breakdown,
        opex_non_fronting_pct=record.get("OPEX_NON_FRONTING_PCT", DEFAULT_OPEX_NON_FRONTING_PCT),
        opex_fronting_pct=record.get("OPEX_FRONTING_PCT", DEFAULT_OPEX_FRONTING_PCT),
        opex_adjust_reason=record.get("OPEX_ADJUST_REASON", ""),
    )

    is_valid = code == expected_code
    if is_valid:
        st.markdown("<div class='verify-ok'>Verified. This PDF matches the saved Risk Profile record.</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='verify-bad'>Not verified. The verification code does not match the saved record.</div>", unsafe_allow_html=True)

    created_at = html.escape(str(record.get("CREATED_AT", "") or "-"))
    username = html.escape(str(record.get("USERNAME", "") or "-"))
    export_type = html.escape(str(record.get("EXPORT_TYPE", "") or "-"))
    file_name = html.escape(str(record.get("FILE_NAME", "") or "-"))
    ovr_status = html.escape(str(record.get("OVR_STATUS", "Exclude OVR") or "Exclude OVR"))
    claim_status = "Included" if include_claim_breakdown else "Not included"
    saved_opex_non = _safe_to_float(record.get("OPEX_NON_FRONTING_PCT"), DEFAULT_OPEX_NON_FRONTING_PCT)
    saved_opex_front = _safe_to_float(record.get("OPEX_FRONTING_PCT"), DEFAULT_OPEX_FRONTING_PCT)
    saved_opex_reason = str(record.get("OPEX_ADJUST_REASON") or "").strip()
    if not _opex_assumptions_are_adjusted(saved_opex_non, saved_opex_front):
        saved_opex_reason = ""
    saved_opex_reason_html = html.escape(saved_opex_reason) if saved_opex_reason else "-"

    st.markdown(
        f"""
        <div class='verify-grid'>
          <div class='verify-label'>Document ID</div><div class='verify-value'>{html.escape(doc_id)}</div>
          <div class='verify-label'>Created at</div><div class='verify-value'>{created_at}</div>
          <div class='verify-label'>Generated by</div><div class='verify-value'>{username}</div>
          <div class='verify-label'>Export type</div><div class='verify-value'>{export_type}</div>
          <div class='verify-label'>File name</div><div class='verify-value'>{file_name}</div>
          <div class='verify-label'>OVR status</div><div class='verify-value'>{ovr_status}</div>
          <div class='verify-label'>Claim breakdown</div><div class='verify-value'>{claim_status}</div>
          <div class='verify-label'>OPEX Non-Fronting</div><div class='verify-value'>{saved_opex_non:g}%</div>
          <div class='verify-label'>OPEX Fronting</div><div class='verify-value'>{saved_opex_front:g}%</div>
          <div class='verify-label'>OPEX adjustment reason</div><div class='verify-value'>{saved_opex_reason_html}</div>
          <div class='verify-label'>Scanned code</div><div class='verify-value'>{html.escape(code)}</div>
          <div class='verify-label'>System code</div><div class='verify-value'>{html.escape(expected_code)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:14px'></div><div class='verify-label'>Saved active filters</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='verify-filter'>{html.escape(_format_verification_filters(filters))}</div>", unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)


def _draw_rp_verification_qr(canvas, doc, doc_id: str, verification_code: str, verify_url: str, open_report_url: str = ""):

    if not doc_id:
        return
    canvas.saveState()
    try:
        from reportlab.graphics.barcode import qr
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics import renderPDF

        qr_size = 1.55 * cm
        x = doc.pagesize[0] - 2.46 * cm


        y = doc.pagesize[1] - 3.78 * cm

        canvas.setFillColor(colors.white)
        canvas.setStrokeColor(colors.HexColor("#8FA3B8"))
        canvas.roundRect(x - 0.14 * cm, y - 0.72 * cm, 1.92 * cm, 2.34 * cm, 0.12 * cm, stroke=1, fill=1)

        qrw = qr.QrCodeWidget(verify_url)
        bounds = qrw.getBounds()
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        drawing = Drawing(qr_size, qr_size, transform=[qr_size / width, 0, 0, qr_size / height, 0, 0])
        drawing.add(qrw)
        renderPDF.draw(drawing, canvas, x, y)

        canvas.setFont(PDF_FONT_BOLD, 5.7)
        canvas.setFillColor(colors.HexColor("#003366"))
        canvas.drawCentredString(x + qr_size / 2, y - 0.11 * cm, "Scan to verify")
        canvas.setFont(PDF_FONT_REGULAR, 4.9)
        canvas.setFillColor(colors.HexColor("#475569"))
        canvas.drawCentredString(x + qr_size / 2, y - 0.32 * cm, f"Code: {str(verification_code or '-')[:12]}")

        if open_report_url:
            link_text = "Open this report"
            link_y = y - 0.55 * cm
            canvas.setFont(PDF_FONT_BOLD, 5.2)
            canvas.setFillColor(colors.HexColor("#005EB8"))
            canvas.drawCentredString(x + qr_size / 2, link_y, link_text)
            text_w = canvas.stringWidth(link_text, PDF_FONT_BOLD, 5.2)
            link_x1 = x + qr_size / 2 - text_w / 2 - 1
            link_x2 = x + qr_size / 2 + text_w / 2 + 1
            canvas.linkURL(open_report_url, (link_x1, link_y - 2, link_x2, link_y + 6), relative=0)
    except Exception:

        canvas.setFont(PDF_FONT_BOLD, 7)
        canvas.setFillColor(colors.HexColor("#003366"))
        canvas.drawRightString(doc.pagesize[0] - 1.0 * cm, doc.pagesize[1] - 1.15 * cm, "Verify Document")
        canvas.setFont(PDF_FONT_REGULAR, 6)
        canvas.drawRightString(doc.pagesize[0] - 1.0 * cm, doc.pagesize[1] - 1.43 * cm, f"Code: {verification_code}")
        if open_report_url:
            link_text = "Open this report"
            lx = doc.pagesize[0] - 1.0 * cm - canvas.stringWidth(link_text, PDF_FONT_BOLD, 6)
            ly = doc.pagesize[1] - 1.68 * cm
            canvas.setFont(PDF_FONT_BOLD, 6)
            canvas.setFillColor(colors.HexColor("#005EB8"))
            canvas.drawRightString(doc.pagesize[0] - 1.0 * cm, ly, link_text)
            canvas.linkURL(open_report_url, (lx - 1, ly - 2, doc.pagesize[0] - 1.0 * cm + 1, ly + 7), relative=0)
    finally:
        canvas.restoreState()


def draw_footer_with_verification(canvas, doc, user, doc_id=None, verification_code: str = "", verify_url: str = "", open_report_url: str = ""):
    draw_footer(canvas, doc, user, doc_id)
    if doc.page == 1:
        _draw_rp_verification_qr(canvas, doc, doc_id or "", verification_code or "", verify_url or "", open_report_url or "")

def draw_footer(canvas, doc, user, doc_id=None):
    canvas.saveState()

    canvas.setFont(PDF_FONT_REGULAR, 8)
    canvas.setFillColor(grey)


    tz = pytz.timezone("Asia/Jakarta")
    now = datetime.now(tz).strftime("%d %b %Y %H:%M WIB")






    canvas.drawString(
        1.0 * cm,
        0.7 * cm,
        "Prepared by Actuarial Department | Confidential"
    )


    text_right = f"Downloaded by: {user} | At: {now}"
    canvas.drawRightString(
        doc.pagesize[0] - 1.0 * cm,
        0.7 * cm,
        text_right
    )




    display_doc_id = _sanitize_doc_id(doc_id) if doc_id else short_hash(text_right)

    canvas.setFont(PDF_FONT_REGULAR, 7)
    canvas.drawRightString(
        doc.pagesize[0] - 1.0 * cm,
        doc.pagesize[1] - 0.8 * cm,
        f"Document ID: {display_doc_id}"
    )

    canvas.restoreState()







DISPLAY_UNIT_OPTIONS = ["in IDR Mio", "in IDR Thousand", "Original Number"]
DISPLAY_UNIT_CONFIG = {
    "in IDR Mio": {"factor": 1_000_000, "label": "IDR Mio", "short": "Mio", "note": "Data shown in IDR Mio"},
    "in IDR Thousand": {"factor": 1_000, "label": "IDR Thousand", "short": "Thousand", "note": "Data shown in IDR Thousand"},
    "Original Number": {"factor": 1, "label": "Original Number", "short": "Original", "note": "Data shown as Original Number"},
}

def _normalize_display_unit(display_unit: str | None) -> str:
    return display_unit if display_unit in DISPLAY_UNIT_CONFIG else "in IDR Mio"

def _display_unit_factor(display_unit: str | None) -> float:
    return float(DISPLAY_UNIT_CONFIG[_normalize_display_unit(display_unit)]["factor"])

def _display_unit_label(display_unit: str | None) -> str:
    return DISPLAY_UNIT_CONFIG[_normalize_display_unit(display_unit)]["label"]

def _display_unit_short(display_unit: str | None) -> str:
    return DISPLAY_UNIT_CONFIG[_normalize_display_unit(display_unit)]["short"]

def _display_unit_note(display_unit: str | None) -> str:
    return DISPLAY_UNIT_CONFIG[_normalize_display_unit(display_unit)]["note"]

def _format_money_value(x, display_unit: str | None = None) -> str:
    if pd.isna(x):
        return ""
    factor = _display_unit_factor(display_unit)
    return f"{int(round(float(x) / factor)):,}".replace(",", ".")





DEFAULT_OPEX_NON_FRONTING_PCT = 15.0
DEFAULT_OPEX_FRONTING_PCT = 0.1
OPEX_NON_FRONTING_STATE_KEY = "risk_profile_opex_non_fronting_pct"
OPEX_FRONTING_STATE_KEY = "risk_profile_opex_fronting_pct"
OPEX_ADJUST_REASON_STATE_KEY = "risk_profile_opex_adjust_reason"
OPEX_NON_FRONTING_DRAFT_KEY = "risk_profile_opex_non_fronting_pct__draft"
OPEX_FRONTING_DRAFT_KEY = "risk_profile_opex_fronting_pct__draft"
OPEX_ADJUST_REASON_DRAFT_KEY = "risk_profile_opex_adjust_reason__draft"
OPEX_DRAFT_SYNC_SIG_KEY = "risk_profile_opex_draft_sync_sig"


def _get_opex_assumptions_pct() -> tuple[float, float]:

    non_fronting = _safe_to_float(
        st.session_state.get(OPEX_NON_FRONTING_STATE_KEY, DEFAULT_OPEX_NON_FRONTING_PCT),
        DEFAULT_OPEX_NON_FRONTING_PCT,
    )
    fronting = _safe_to_float(
        st.session_state.get(OPEX_FRONTING_STATE_KEY, DEFAULT_OPEX_FRONTING_PCT),
        DEFAULT_OPEX_FRONTING_PCT,
    )
    return max(0.0, non_fronting), max(0.0, fronting)


def _get_opex_adjust_reason() -> str:
    return str(st.session_state.get(OPEX_ADJUST_REASON_STATE_KEY, "") or "").strip()


def _opex_assumptions_are_adjusted(non_fronting_pct=None, fronting_pct=None) -> bool:

    if non_fronting_pct is None or fronting_pct is None:
        current_non, current_front = _get_opex_assumptions_pct()
        if non_fronting_pct is None:
            non_fronting_pct = current_non
        if fronting_pct is None:
            fronting_pct = current_front
    non_fronting_pct = _safe_to_float(non_fronting_pct, DEFAULT_OPEX_NON_FRONTING_PCT)
    fronting_pct = _safe_to_float(fronting_pct, DEFAULT_OPEX_FRONTING_PCT)
    return not (
        np.isclose(non_fronting_pct, DEFAULT_OPEX_NON_FRONTING_PCT, rtol=0.0, atol=1e-9)
        and np.isclose(fronting_pct, DEFAULT_OPEX_FRONTING_PCT, rtol=0.0, atol=1e-9)
    )


def _normalize_role_name(value) -> str:
    text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    return " ".join(text.split())


def _current_session_role(explicit_role=None) -> str:

    if str(explicit_role or "").strip():
        return _normalize_role_name(explicit_role)
    for key in (
        "role", "ROLE", "user_role", "USER_ROLE", "logged_in_role",
        "current_role", "jabatan", "position", "user_position",
    ):
        value = st.session_state.get(key)
        if str(value or "").strip():
            return _normalize_role_name(value)
    return ""


def _can_adjust_opex_assumptions(username: str, role=None) -> bool:

    allowed_roles = {
        "actuary",
        "direktur teknik", "technical director", "director technical", "director teknik",
        "direktur finance", "finance director", "director finance",
        "direktur marketing", "marketing director", "director marketing",
    }
    role = _current_session_role(role)
    if role in allowed_roles:
        return True


    user = str(username or "").strip().lower()
    known_allowed_users = {
        "actuary@mnc-insurance.com",
        "david.jaya@mnc-insurance.com",
        "meindy.sihombing@mnc-insurance.com",
    }
    return user in known_allowed_users


def _apply_opex_assumptions_to_df(df: pd.DataFrame) -> pd.DataFrame:






    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return df

    out = df.copy(deep=False)
    if "GWP_AMT" not in out.columns:
        out["OPEX_PCT"] = 0.0
        out["OPEX_AMT"] = 0.0
        return out

    non_fronting_pct, fronting_pct = _get_opex_assumptions_pct()
    non_fronting_dec = non_fronting_pct / 100.0
    fronting_dec = fronting_pct / 100.0

    if "IS_FRONTING" in out.columns:
        fronting_flag = (
            out["IS_FRONTING"]
            .astype("string")
            .fillna("")
            .str.strip()
            .str.upper()
            .eq("FRONTING")
        )
        opex_pct = np.where(fronting_flag.to_numpy(), fronting_dec, non_fronting_dec)
    else:
        opex_pct = np.full(len(out), non_fronting_dec, dtype=float)

    gwp = pd.to_numeric(out["GWP_AMT"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    out["OPEX_PCT"] = opex_pct
    out["OPEX_AMT"] = gwp * opex_pct
    return out


def _apply_portfolio_cost_adjustments(df: pd.DataFrame) -> pd.DataFrame:

    if df is None or df.empty:
        return df
    base = df.drop(columns=["OVR_PCT", "OVR_AMT"], errors="ignore")
    adjusted = _apply_opex_assumptions_to_df(base)
    if _get_applied_ovr_configuration() is not None:
        adjusted = apply_ovr_to_df(adjusted)
    return adjusted


def _opex_assumption_note(include_reason: bool = False) -> str:
    non_fronting_pct, fronting_pct = _get_opex_assumptions_pct()
    text = (
        f"OPEX assumption: Non-Fronting {non_fronting_pct:g}% | "
        f"Fronting {fronting_pct:g}%"
    )
    reason = _get_opex_adjust_reason()
    if include_reason and _opex_assumptions_are_adjusted(non_fronting_pct, fronting_pct) and reason:
        text += f" ({reason})"
    return text


def render_opex_assumption_controls(username: str, role=None) -> None:






    if not _can_adjust_opex_assumptions(username, role):
        return

    st.session_state.setdefault(OPEX_NON_FRONTING_STATE_KEY, DEFAULT_OPEX_NON_FRONTING_PCT)
    st.session_state.setdefault(OPEX_FRONTING_STATE_KEY, DEFAULT_OPEX_FRONTING_PCT)
    st.session_state.setdefault(OPEX_ADJUST_REASON_STATE_KEY, "")

    current_non, current_front = _get_opex_assumptions_pct()
    current_reason = _get_opex_adjust_reason()
    current_sig = (round(current_non, 10), round(current_front, 10), current_reason)



    if st.session_state.get(OPEX_DRAFT_SYNC_SIG_KEY) != current_sig:
        st.session_state[OPEX_NON_FRONTING_DRAFT_KEY] = current_non
        st.session_state[OPEX_FRONTING_DRAFT_KEY] = current_front
        st.session_state[OPEX_ADJUST_REASON_DRAFT_KEY] = current_reason
        st.session_state[OPEX_DRAFT_SYNC_SIG_KEY] = current_sig

    st.markdown("<div style='font-size:14px;font-weight:850;color:#003366;margin-bottom:4px;'>Adjust Assumptions</div>", unsafe_allow_html=True)
    st.caption("Default: OPEX Non-Fronting 15% | OPEX Fronting 0.1%. Alasan wajib diisi jika salah satu asumsi di-adjust.")

    with st.form("risk_profile_opex_assumption_form", clear_on_submit=False):
        st.number_input(
            "OPEX Non-Fronting (%)",
            min_value=0.0,
            max_value=100.0,
            step=0.1,
            format="%.2f",
            key=OPEX_NON_FRONTING_DRAFT_KEY,
        )
        st.number_input(
            "OPEX Fronting (%)",
            min_value=0.0,
            max_value=100.0,
            step=0.1,
            format="%.2f",
            key=OPEX_FRONTING_DRAFT_KEY,
        )
        st.text_area(
            "Alasan Adjust Asumsi",
            key=OPEX_ADJUST_REASON_DRAFT_KEY,
            placeholder="Contoh: Karena Merupakan Polis Digital",
            height=82,
            help="Wajib diisi jika OPEX Non-Fronting bukan 15% atau OPEX Fronting bukan 0.1%.",
        )
        applied = st.form_submit_button("Apply Assumptions", type="primary", width="stretch")

    if applied:
        draft_non = max(0.0, _safe_to_float(st.session_state.get(OPEX_NON_FRONTING_DRAFT_KEY), DEFAULT_OPEX_NON_FRONTING_PCT))
        draft_front = max(0.0, _safe_to_float(st.session_state.get(OPEX_FRONTING_DRAFT_KEY), DEFAULT_OPEX_FRONTING_PCT))
        draft_reason = str(st.session_state.get(OPEX_ADJUST_REASON_DRAFT_KEY, "") or "").strip()
        adjusted = _opex_assumptions_are_adjusted(draft_non, draft_front)

        if adjusted and not draft_reason:
            st.error("Alasan Adjust Asumsi wajib diisi jika asumsi OPEX berbeda dari default 15% / 0.1%.")
            return

        st.session_state[OPEX_NON_FRONTING_STATE_KEY] = draft_non
        st.session_state[OPEX_FRONTING_STATE_KEY] = draft_front
        st.session_state[OPEX_ADJUST_REASON_STATE_KEY] = draft_reason if adjusted else ""
        committed_reason = draft_reason if adjusted else ""
        st.session_state[OPEX_DRAFT_SYNC_SIG_KEY] = (round(draft_non, 10), round(draft_front, 10), committed_reason)
        if not adjusted:


            st.session_state.pop(OPEX_DRAFT_SYNC_SIG_KEY, None)



        _rerun_full_app_after_ovr()

def compute_kpis(df):
    df_calc = _ensure_portfolio_cost_columns(df)

    gwp = df_calc["GWP_AMT"].sum()
    gep = df_calc["GEP_AMT"].sum()
    claim = df_calc["GROSS_CLAIM"].sum()
    comm = df_calc["COMMISSIONS"].sum()
    ri_cost = df_calc["ERC_AMT"].sum()
    ri_rec = df_calc["RI_RECOVERY"].sum()

    loss_ratio = claim / gep if gep else np.nan
    comm_ratio = comm / gwp if gwp else np.nan
    ri_cost_ratio = ri_cost / gep if gep else np.nan
    ri_rec_ratio = ri_rec / gep if gep else np.nan

    ovr_ratio = (df_calc["OVR_AMT"].sum() / gwp) if ("OVR_AMT" in df_calc.columns and gwp) else 0.0
    opex_ratio = (df_calc["OPEX_AMT"].sum() / gwp) if ("OPEX_AMT" in df_calc.columns and gwp) else 0.0

    cor = loss_ratio + comm_ratio + ri_cost_ratio - ri_rec_ratio + opex_ratio + ovr_ratio





    gwp_series = pd.to_numeric(df_calc.get("GWP_AMT", pd.Series(index=df_calc.index, dtype=float)), errors="coerce").fillna(0.0)
    active_business = gwp_series.abs() > 1e-9

    if "IS_FRONTING" in df_calc.columns:
        fronting_mask = (
            df_calc["IS_FRONTING"]
            .astype("string")
            .fillna("")
            .str.strip()
            .str.upper()
            .eq("FRONTING")
        )
        if bool(active_business.any()):
            has_fronting_business = bool((fronting_mask & active_business).any())


            has_non_fronting_business = bool(((~fronting_mask) & active_business).any())
        else:
            has_fronting_business = bool(fronting_mask.any())
            has_non_fronting_business = bool((~fronting_mask).any())
    else:
        has_fronting_business = False
        has_non_fronting_business = bool(len(df_calc) > 0)

    return {
        "GWP": gwp,
        "Loss Ratio": loss_ratio * 100,
        "COMM Ratio": comm_ratio * 100,
        "RI Cost Ratio": ri_cost_ratio * 100,
        "RI Recovery Ratio": ri_rec_ratio * 100,
        "OPEX Ratio": opex_ratio * 100,
        "CoR": cor * 100,
        "Has Fronting Business": has_fronting_business,
        "Has Non-Fronting Business": has_non_fronting_business,
    }

def render_kpi_cards(kpis, display_unit="in IDR Mio"):





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
      }
    </style>
    """, unsafe_allow_html=True)

    def fmt_money(x):
        return _format_money_value(x, display_unit)

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
        kpi_box(f"Total GWP ({_display_unit_short(display_unit)})", fmt_money(kpis["GWP"]), "kpi-gwp")

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


    if pd.notna(cor_value) and cor_value > 100:
        msg = "Bisnis ini mencatatkan rugi (CoR > 100%)."

        key = f"cor_toast_shown_{int(round(cor_value))}"
        if not st.session_state.get(key, False):
            st.session_state[key] = True
            st.markdown(
                f'<div class="cor-toast"><div class="icon">!</div><div class="txt">{msg}</div></div>',
                unsafe_allow_html=True
            )





def make_pivot(df, index_cols, row_limit=500, extra_value_cols=None):









    if df is None or df.empty:
        return pd.DataFrame()


    df = _ensure_portfolio_cost_columns(df)

    index_cols = [c for c in list(index_cols or []) if c in df.columns]
    if not index_cols:
        return pd.DataFrame()

    base_required_value_cols = [
        "OUR TSI", "NUMBER OF RISKS", "NUMBER OF CLAIMS",
        "GWP_AMT", "GEP_AMT", "GROSS_CLAIM",
        "COMMISSIONS", "RI_COST", "ERC_AMT", "RI_RECOVERY"
    ]
    if "OVR_AMT" in df.columns:
        base_required_value_cols.append("OVR_AMT")
    if "OPEX_AMT" in df.columns:
        base_required_value_cols.append("OPEX_AMT")



    requested_extra_cols = list(dict.fromkeys(str(c) for c in (extra_value_cols or []) if str(c).strip()))
    extra_source_to_output = {}
    for output_col in requested_extra_cols:
        source_col = _resolve_excel_metric_source_col(df, output_col)
        if source_col is not None:
            extra_source_to_output[source_col] = output_col

    required_value_cols = list(base_required_value_cols)
    for source_col in extra_source_to_output:
        if source_col not in required_value_cols:
            required_value_cols.append(source_col)

    existing_value_cols = [c for c in required_value_cols if c in df.columns]
    work_cols = index_cols + existing_value_cols
    work = df.loc[:, work_cols].copy()



    for col in index_cols:
        try:
            if pd.api.types.is_categorical_dtype(work[col]):
                if "(Blank)" not in work[col].cat.categories:
                    work[col] = work[col].cat.add_categories(["(Blank)"])
                work[col] = work[col].fillna("(Blank)")
            else:
                work[col] = work[col].where(work[col].notna(), "(Blank)")
        except Exception:
            work[col] = work[col].astype(object).where(work[col].notna(), "(Blank)")

    for col in existing_value_cols:
        work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)


    grouped = (
        work.groupby(index_cols, dropna=False, observed=True, sort=False)[existing_value_cols]
        .sum(numeric_only=True)
    )

    for col in required_value_cols:
        if col not in grouped.columns:
            grouped[col] = 0.0
        grouped[col] = pd.to_numeric(grouped[col], errors="coerce").fillna(0.0)




    for source_col, output_col in extra_source_to_output.items():
        if source_col == output_col or source_col not in grouped.columns:
            continue
        if output_col in grouped.columns:
            grouped[output_col] = (
                pd.to_numeric(grouped[output_col], errors="coerce").fillna(0.0)
                + pd.to_numeric(grouped[source_col], errors="coerce").fillna(0.0)
            )
            grouped = grouped.drop(columns=[source_col])
        else:
            grouped = grouped.rename(columns={source_col: output_col})

    for output_col in requested_extra_cols:
        if output_col not in grouped.columns:
            grouped[output_col] = 0.0
        grouped[output_col] = pd.to_numeric(grouped[output_col], errors="coerce").fillna(0.0)

    gep = grouped["GEP_AMT"].replace(0, np.nan)
    gwp = grouped["GWP_AMT"].replace(0, np.nan)

    grouped["Loss Ratio"] = (grouped["GROSS_CLAIM"] / gep).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    grouped["COMM Ratio"] = (grouped["COMMISSIONS"] / gwp).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    grouped["RI Cost Ratio"] = (grouped["ERC_AMT"] / gep).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    grouped["RI Recovery Ratio"] = (grouped["RI_RECOVERY"] / gep).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    grouped["OVR Ratio"] = (grouped["OVR_AMT"] / gwp).replace([np.inf, -np.inf], np.nan).fillna(0.0) if "OVR_AMT" in grouped.columns else 0.0
    grouped["OPEX Ratio"] = (grouped["OPEX_AMT"] / gwp).replace([np.inf, -np.inf], np.nan).fillna(0.0) if "OPEX_AMT" in grouped.columns else 0.0

    grouped["CoR"] = (
        grouped["Loss Ratio"]
        + grouped["COMM Ratio"]
        + grouped["RI Cost Ratio"]
        - grouped["RI Recovery Ratio"]
        + grouped["OPEX Ratio"]
        + grouped["OVR Ratio"]
    )

    ratio_cols = ["Loss Ratio", "COMM Ratio", "RI Cost Ratio", "RI Recovery Ratio", "OPEX Ratio", "OVR Ratio", "CoR"]
    grouped[ratio_cols] = grouped[ratio_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100



    grouped = grouped.drop(columns=[c for c in ["OPEX_AMT", "OPEX Ratio"] if c in grouped.columns])



    try:
        grouped = grouped.sort_index(ascending=True, kind="stable")
    except Exception:
        pass

    if row_limit is not None and len(grouped) > row_limit:
        grouped = grouped.head(row_limit)

    return grouped





def _drop_ovr_cols_if_zero(df: pd.DataFrame) -> pd.DataFrame:

    df2 = df.copy()
    if "OVR_AMT" in df2.columns:
        s = pd.to_numeric(df2["OVR_AMT"], errors="coerce").fillna(0.0)
        if float(s.abs().sum()) < 1e-9:
            drop_cols = [c for c in ["OVR_AMT", "OVR Ratio", "OVR_PCT"] if c in df2.columns]
            if drop_cols:
                df2 = df2.drop(columns=drop_cols)
    return df2

def format_and_display(df, table_key=None, display_unit="in IDR Mio"):





    df = df.copy()
    df = _drop_ovr_cols_if_zero(df)


    if isinstance(df.index, pd.MultiIndex):
        df = df.reset_index()
    elif df.index.name is not None:
        df = df.reset_index()

    if "ERC_AMT" in df.columns:
        df = df.drop(columns=["ERC_AMT"])

    metric_order = [
        "OUR TSI", "NUMBER OF RISKS", "NUMBER OF CLAIMS",
        "GWP_AMT", "GEP_AMT", "GROSS_CLAIM",
        "COMMISSIONS", "OVR_AMT", "RI_COST", "RI_RECOVERY",
        "Loss Ratio", "COMM Ratio", "RI Cost Ratio",
        "RI Recovery Ratio", "OVR Ratio", "CoR"
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

    money_cols = [
        "OUR TSI", "GWP_AMT", "GEP_AMT", "GROSS_CLAIM",
        "COMMISSIONS", "OVR_AMT", "RI_COST", "RI_RECOVERY"
    ]
    count_cols = ["NUMBER OF RISKS", "NUMBER OF CLAIMS"]
    ratio_cols = [c for c in display_df.columns if ("Ratio" in c or c == "CoR")]

    money_unit_label = _display_unit_label(display_unit)

    def fmt_number(x):
        return "" if pd.isna(x) else f"{int(round(float(x))):,}".replace(",", ".")

    for col in money_cols:
        if col in display_df.columns:
            display_df[col] = pd.to_numeric(display_df[col], errors="coerce") / _display_unit_factor(display_unit)

    def fmt_percent(x):
        return "" if pd.isna(x) else f"{round(float(x)):.0f}%"

    for col in display_df.columns:
        if col in money_cols or col in count_cols:
            display_df[col] = display_df[col].apply(fmt_number)
        elif col in ratio_cols:
            display_df[col] = display_df[col].apply(fmt_percent)
        else:
            display_df[col] = display_df[col].astype("string").fillna("")

    col_alias = {
        "UW_YEAR": "UW YEAR",
        "OUR TSI": f"OUR TSI<br><span>{money_unit_label}</span>",
        "GWP_AMT": f"GWP<br><span>{money_unit_label}</span>",
        "GEP_AMT": f"GEP<br><span>{money_unit_label}</span>",
        "GROSS_CLAIM": f"GROSS CLAIM<br><span>{money_unit_label}</span>",
        "COMMISSIONS": f"COMM<br><span>{money_unit_label}</span>",
        "OVR_AMT": f"OVR<br><span>{money_unit_label}</span>",
        "RI_COST": f"RI COST<br><span>{money_unit_label}</span>",
        "RI_RECOVERY": f"RI REC<br><span>{money_unit_label}</span>",
        "NUMBER OF RISKS": "NO. OF RISKS",
        "NUMBER OF CLAIMS": "NO. OF CLAIMS",
        "Loss Ratio": "LOSS RATIO",
        "COMM Ratio": "COMM RATIO",
        "RI Cost Ratio": "RI COST RATIO",
        "RI Recovery Ratio": "RI REC RATIO",
        "OVR Ratio": "OVR RATIO",
        "CoR": "CoR",
    }

    def width_for(col):
        if col in group_cols:
            if col in ["UW_YEAR", "COB"]:
                return 110
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
    body_max_height = max(140, table_height - 74)

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

            if col == "CoR" and pd.notna(raw_val) and raw_val > 100:
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
      .rp-table-controls {{
        display: flex;
        gap: 10px;
        align-items: center;
        margin: 0 0 10px 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      .rp-table-controls label {{
        font-size: 11.5px;
        font-weight: 650;
        color: #475569;
      }}
      .rp-table-controls select, .rp-table-controls button {{
        height: 34px;
        border: 1px solid rgba(0,51,102,0.16);
        border-radius: 10px;
        background: #FFFFFF;
        color: #1F2937;
        font-size: 11.5px;
        padding: 0 10px;
        outline: none;
      }}
      .rp-table-controls select:focus {{
        border-color: rgba(0,51,102,0.45);
        box-shadow: 0 0 0 3px rgba(0,51,102,0.08);
      }}
      .rp-table-controls button {{
        cursor: pointer;
        font-weight: 650;
        color: #003366;
      }}
      .rp-table-wrap {{
        width: 100%;
        max-height: {table_height}px;
        overflow: auto;
        border: 1px solid rgba(0, 51, 102, 0.12);
        border-radius: 16px;
        background: #ffffff;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
      }}
      .rp-table {{
        border-collapse: separate;
        border-spacing: 0;
        table-layout: fixed;
        width: {min_table_width}px;
        min-width: {min_table_width}px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, Arial, sans-serif;
        color: #334155;
        -webkit-font-smoothing: antialiased;
        text-rendering: optimizeLegibility;
      }}
      .rp-table thead th {{
        position: sticky;
        top: 0;
        z-index: 30;
        background: #003366;
        color: #ffffff;
        text-align: center !important;
        vertical-align: middle;
        font-size: 10.8px;
        line-height: 1.18;
        font-weight: 720;
        height: 46px;
        padding: 8px 8px;
        border-right: 1px solid rgba(255,255,255,0.18);
        border-bottom: 1px solid rgba(0,0,0,0.10);
        white-space: normal;
        box-sizing: border-box;
      }}
      .rp-table thead th span {{
        display: block;
        margin-top: 2px;
        font-size: 8.8px;
        line-height: 1.0;
        font-weight: 500;
        opacity: 0.78;
      }}
      .rp-table tbody td {{
        font-size: 11.2px;
        line-height: 1.28;
        height: 34px;
        padding: 8px 10px;
        border-right: 1px solid rgba(15, 23, 42, 0.045);
        border-bottom: 1px solid rgba(15, 23, 42, 0.055);
        background: #ffffff;
        color: #334155;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        box-sizing: border-box;
        font-weight: 600;
      }}
      .rp-table tbody tr:nth-child(even) td {{
        background: #F8FAFC;
      }}
      .rp-table tbody tr:hover td {{
        background: #EEF6FF;
      }}
      .rp-table .text-cell {{
        text-align: left;
        font-weight: 650;
        color: #1E3A5F;
      }}
      .rp-table .num-cell {{
        text-align: right;
        font-variant-numeric: tabular-nums;
        font-weight: 620;
        color: #334155;
      }}
      .rp-table .sticky-col {{
        position: sticky;
        z-index: 20;
        box-shadow: 2px 0 0 rgba(0, 51, 102, 0.08);
      }}
      .rp-table thead th.sticky-col {{
        z-index: 40;
        background: #002B57;
      }}
      .rp-table tbody td.sticky-col {{
        background: #ffffff;
      }}
      .rp-table tbody tr:nth-child(even) td.sticky-col {{
        background: #F8FAFC;
      }}
      .rp-table tbody tr:hover td.sticky-col {{
        background: #EEF6FF;
      }}
      .rp-table tbody td.cor-danger {{
        background: #FFE7E7 !important;
        color: #9F1239;
        font-weight: 760;
      }}
      .rp-table tbody td.loss-warning {{
        background: #FFF6D8 !important;
        color: #7C4A03;
        font-weight: 740;
      }}
    </style>

    <div class="rp-table-controls">
      <label for="sort_by_{table_dom_id}">Sort by</label>
      <select id="sort_by_{table_dom_id}">{sort_options_html}</select>
      <select id="sort_order_{table_dom_id}">
        <option value="desc">Descending</option>
        <option value="asc">Ascending</option>
      </select>
      <button type="button" id="reset_sort_{table_dom_id}">Reset</button>
    </div>
    <div class="rp-table-wrap">
      <table class="rp-table" id="{table_dom_id}">
        <colgroup>{css_colgroup}</colgroup>
        <thead><tr>{header_cells}</tr></thead>
        <tbody>{''.join(body_rows)}</tbody>
      </table>
    </div>
    <script>
      (function() {{
        const table = document.getElementById("{table_dom_id}");
        const sortBy = document.getElementById("sort_by_{table_dom_id}");
        const sortOrder = document.getElementById("sort_order_{table_dom_id}");
        const resetBtn = document.getElementById("reset_sort_{table_dom_id}");
        if (!table || !sortBy || !sortOrder || !resetBtn) return;

        const tbody = table.querySelector("tbody");
        const originalRows = Array.from(tbody.querySelectorAll("tr"));

        function applySort() {{
          const colIndex = sortBy.value;
          if (colIndex === "") {{
            tbody.replaceChildren(...originalRows);
            return;
          }}
          const idx = parseInt(colIndex, 10);
          const asc = sortOrder.value === "asc";
          const rows = Array.from(tbody.querySelectorAll("tr"));
          rows.sort(function(a, b) {{
            const acell = a.children[idx];
            const bcell = b.children[idx];
            const atype = acell.getAttribute("data-sort-type");
            const btype = bcell.getAttribute("data-sort-type");
            let av = acell.getAttribute("data-sort") || "";
            let bv = bcell.getAttribute("data-sort") || "";
            let result = 0;
            if (atype === "num" && btype === "num") {{
              result = (parseFloat(av) || 0) - (parseFloat(bv) || 0);
            }} else {{
              result = av.localeCompare(bv, undefined, {{numeric: true, sensitivity: "base"}});
            }}
            return asc ? result : -result;
          }});
          tbody.replaceChildren(...rows);
        }}

        sortBy.addEventListener("change", applySort);
        sortOrder.addEventListener("change", applySort);
        resetBtn.addEventListener("click", function() {{
          sortBy.value = "";
          sortOrder.value = "desc";
          tbody.replaceChildren(...originalRows);
        }});
      }})();
    </script>
    """

    _render_html_block(
        html_table,
        height=table_height + 44,
        scrolling=False,
    )








def render_section_card_header(title: str, subtitle: str = ""):

    st.markdown(f"""
    <div class="section-card-header">
      <div class="section-card-title">{html.escape(title)}</div>
    </div>
    """, unsafe_allow_html=True)


def inject_compact_section_css():
    st.markdown("""
    <style>
      .section-card-header{
        margin: 10px 0 4px 0;
        padding: 10px 15px;
        border-radius: 16px;
        background: #F8FAFC;
        border: 1px solid rgba(0,51,102,0.10);
        box-shadow: 0 8px 22px rgba(15,23,42,0.035);
      }
      .section-card-title{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        font-size: 18px;
        font-weight: 800;
        line-height: 1.15;
        color: #003366;
        letter-spacing: -0.01em;
      }
      .section-card-subtitle{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        font-size: 12.5px;
        color: #64748B;
        line-height: 1.25;
        margin-top: 3px;
      }
      .block-container h3{
        margin-top: 0.4rem !important;
        margin-bottom: 0.35rem !important;
      }
      div[data-testid="stTabs"]{ margin-top: 0.1rem !important; }
      div[data-testid="stVegaLiteChart"]{
        background: transparent !important;
        box-shadow: none !important;
        border: none !important;
      }
      div[data-testid="stVegaLiteChart"] > div{
        background: transparent !important;
      }
    </style>
    """, unsafe_allow_html=True)




def _parse_gwp_as_of_date(value):





    if value is None:
        return None
    if not isinstance(value, str):
        if isinstance(value, (int, float, np.number)):
            return None
        try:
            parsed = pd.Timestamp(value)
            return None if pd.isna(parsed) else parsed
        except (TypeError, ValueError, OverflowError):
            return None

    text = value.strip()
    if not text:
        return None
    prefix, separator, label = text.partition("_")
    candidates = [label.strip(), prefix.strip()] if separator else [text]
    month_names = {
        "januari": "january", "februari": "february", "maret": "march",
        "april": "april", "mei": "may", "juni": "june", "juli": "july",
        "agustus": "august", "september": "september", "oktober": "october",
        "november": "november", "desember": "december",
    }
    for candidate in candidates:
        normalized = " ".join(month_names.get(word, word) for word in candidate.lower().split())
        if normalized.isdigit() and len(normalized) in (6, 8):
            formats = ("%y%m%d",) if len(normalized) == 6 else ("%Y%m%d",)
        else:
            formats = ("%d %B %Y", "%d %b %Y", "%Y-%m-%d", "%Y/%m/%d",
                       "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S")
        for date_format in formats:
            try:
                return pd.Timestamp(datetime.strptime(normalized, date_format))
            except (TypeError, ValueError, OverflowError):
                continue

        if len(candidate) > 10 and candidate[4:5] == "-" and candidate[7:8] == "-":
            try:
                return pd.Timestamp(datetime.fromisoformat(candidate.replace("Z", "+00:00")))
            except (TypeError, ValueError, OverflowError):
                pass
    return None


def _project_gwp_full_year(yearly: pd.DataFrame, as_of_date=None) -> dict:










    if as_of_date is None:
        try:
            as_of_date = st.session_state.get("risk_profile_as_of_date")
        except Exception:
            as_of_date = None
    cutoff = _parse_gwp_as_of_date(as_of_date)
    result = {
        "year": None, "actual": np.nan, "annualized": np.nan,
        "historical": np.nan, "projection": np.nan, "elapsed_months": None,
        "history_years": [], "as_of_date": cutoff.strftime("%Y-%m-%d") if cutoff is not None else None,
        "method": "unavailable", "floor_applied": False,
    }
    if yearly is None or yearly.empty or not {"UW_YEAR", "GWP_AMT"}.issubset(yearly.columns):
        return result

    data = yearly[["UW_YEAR", "GWP_AMT"]].copy()
    for col in data.columns:
        data[col] = pd.to_numeric(data[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    data = data.dropna(subset=["UW_YEAR"]).sort_values("UW_YEAR")
    if data.empty:
        return result

    eligible = data[data["UW_YEAR"] <= cutoff.year] if cutoff is not None else data
    target_row = (eligible if not eligible.empty else data).iloc[-1]
    year = int(target_row["UW_YEAR"])
    actual = _finite_float(target_row["GWP_AMT"])
    result.update({"year": year, "actual": actual, "projection": actual})
    if not np.isfinite(actual):
        return result

    history = data[data["UW_YEAR"] < year].dropna(subset=["GWP_AMT"]).tail(3)
    result["history_years"] = history["UW_YEAR"].astype(int).tolist()
    if not history.empty:

        result["historical"] = _finite_float((history["GWP_AMT"] / len(history)).sum())

    if cutoff is None:
        result["method"] = "actual_only_missing_date"
        return result
    if year > cutoff.year:
        result["method"] = "actual_only_future_year"
        return result
    if year < cutoff.year or (cutoff.month == 12 and cutoff.day == 31):
        result.update({"annualized": actual, "elapsed_months": 12, "method": "closed_year_actual"})
        return result

    months = int(cutoff.month)
    annualized = actual * (12.0 / months)
    result.update({"annualized": annualized, "elapsed_months": months})
    if not np.isfinite(annualized):
        result["method"] = "actual_only_invalid_run_rate"
        return result
    if np.isfinite(result["historical"]):
        blended = 0.5 * annualized + 0.5 * result["historical"]
        result["method"] = "blend_50_50"
    else:
        blended = annualized
        result["method"] = "annualized_only_no_history"
    result["projection"] = max(actual, blended)
    result["floor_applied"] = bool(blended < actual)
    return result


def _gwp_projection_note(projection: dict, display_unit="in IDR Mio") -> str:

    year = projection.get("year")
    method = projection.get("method")
    factor = _display_unit_factor(display_unit)
    unit = _display_unit_label(display_unit)

    def amount(key):
        return _pdf_compact_number(projection.get(key, np.nan) / factor)

    if method == "blend_50_50":
        years = ", ".join(str(y) for y in projection["history_years"])
        return (
            f"GWP {year} as of {projection['as_of_date']}: 50% annualized actual "
            f"(YTD x 12/{projection['elapsed_months']} = {amount('annualized')}) + "
            f"50% historical average ({years} = {amount('historical')}). "
            f"Final: {amount('projection')} {unit}; minimum = actual {amount('actual')}. "
            "The selected as-of month is counted inclusively."
        )
    if method == "annualized_only_no_history":
        return (f"GWP {year}: no previous UW-year history; use annualized actual only "
                f"(YTD x 12/{projection['elapsed_months']}, as-of month inclusive), "
                f"with a floor at actual. Final: {amount('projection')} {unit}.")
    if method == "closed_year_actual":
        return f"GWP {year}: year completed as of {projection['as_of_date']}; full-year value equals actual."
    return f"GWP {year}: annualization unavailable for this as-of date/data; keep actual without extrapolation."


def render_trend_projection_section(source_df: pd.DataFrame, display_unit="in IDR Mio", as_of_date=None):








    render_section_card_header("Trend & Projection", "GWP: 50% monthly annualization + 50% historical average, with an actual floor. Loss Ratio/CoR: moving average.")
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    if source_df is None or source_df.empty:
        st.info("No data.")
        return

    source_df = _ensure_portfolio_cost_columns(source_df)

    required = ["UW_YEAR", "GWP_AMT", "GEP_AMT", "GROSS_CLAIM"]
    missing = [c for c in required if c not in source_df.columns]
    if missing:
        st.info("Trend unavailable. Missing: " + ", ".join(missing))
        return

    optional_cols = ["COMMISSIONS", "RI_RECOVERY", "ERC_AMT", "RI_COST", "OVR_AMT", "OPEX_AMT"]
    trend_cols = required + [c for c in optional_cols if c in source_df.columns and c not in required]
    tmp = source_df.loc[:, trend_cols].copy()
    tmp["UW_YEAR"] = pd.to_numeric(tmp["UW_YEAR"], errors="coerce")
    tmp = tmp[tmp["UW_YEAR"].notna()].copy()
    if tmp.empty:
        st.info("Trend unavailable. UW_YEAR is empty.")
        return

    for col in [c for c in trend_cols if c != "UW_YEAR"]:
        tmp[col] = pd.to_numeric(tmp[col], errors="coerce").fillna(0.0)

    tmp["_RI_COST_FOR_COR"] = tmp["ERC_AMT"] if "ERC_AMT" in tmp.columns else (tmp["RI_COST"] if "RI_COST" in tmp.columns else 0.0)
    for col in ["COMMISSIONS", "RI_RECOVERY", "OVR_AMT"]:
        if col not in tmp.columns:
            tmp[col] = 0.0

    yearly = (
        tmp.groupby("UW_YEAR", as_index=False, sort=True)
        .agg(
            GWP_AMT=("GWP_AMT", "sum"),
            GEP_AMT=("GEP_AMT", "sum"),
            GROSS_CLAIM=("GROSS_CLAIM", "sum"),
            COMMISSIONS=("COMMISSIONS", "sum"),
            RI_COST_FOR_COR=("_RI_COST_FOR_COR", "sum"),
            RI_RECOVERY=("RI_RECOVERY", "sum"),
            OVR_AMT=("OVR_AMT", "sum"),
            OPEX_AMT=("OPEX_AMT", "sum"),
        )
        .sort_values("UW_YEAR")
        .reset_index(drop=True)
    )
    yearly["UW_YEAR"] = yearly["UW_YEAR"].astype(int)

    money_unit_label = _display_unit_label(display_unit)
    money_unit_short = _display_unit_short(display_unit)
    gwp_display_col = f"GWP {money_unit_short}"
    yearly[gwp_display_col] = yearly["GWP_AMT"] / _display_unit_factor(display_unit)
    yearly["Loss Ratio %"] = np.where(yearly["GEP_AMT"] > 0, yearly["GROSS_CLAIM"] / yearly["GEP_AMT"] * 100.0, np.nan)
    yearly["COMM Ratio %"] = np.where(yearly["GWP_AMT"] > 0, yearly["COMMISSIONS"] / yearly["GWP_AMT"] * 100.0, np.nan)
    yearly["RI Cost Ratio %"] = np.where(yearly["GEP_AMT"] > 0, yearly["RI_COST_FOR_COR"] / yearly["GEP_AMT"] * 100.0, np.nan)
    yearly["RI Recovery Ratio %"] = np.where(yearly["GEP_AMT"] > 0, yearly["RI_RECOVERY"] / yearly["GEP_AMT"] * 100.0, np.nan)
    yearly["OVR Ratio %"] = np.where(yearly["GWP_AMT"] > 0, yearly["OVR_AMT"] / yearly["GWP_AMT"] * 100.0, 0.0)
    yearly["OPEX Ratio %"] = np.where(yearly["GWP_AMT"] > 0, yearly["OPEX_AMT"] / yearly["GWP_AMT"] * 100.0, 0.0)
    yearly["CoR %"] = (
        yearly["Loss Ratio %"].fillna(0.0)
        + yearly["COMM Ratio %"].fillna(0.0)
        + yearly["RI Cost Ratio %"].fillna(0.0)
        - yearly["RI Recovery Ratio %"].fillna(0.0)
        + yearly["OPEX Ratio %"].fillna(0.0)
        + yearly["OVR Ratio %"].fillna(0.0)
    )

    latest_year = int(yearly["UW_YEAR"].max())
    completed_yearly = yearly[yearly["UW_YEAR"] < latest_year].copy()
    ratio_projection_available = len(completed_yearly) >= 2
    gwp_projection = _project_gwp_full_year(yearly, as_of_date)
    gwp_projection_year = gwp_projection["year"] if gwp_projection["year"] is not None else latest_year
    ma_window = min(3, len(completed_yearly))
    projection_values = {
        gwp_display_col: gwp_projection["projection"] / _display_unit_factor(display_unit),
        "Loss Ratio %": float(completed_yearly["Loss Ratio %"].dropna().tail(ma_window).mean()) if ratio_projection_available else np.nan,
        "CoR %": float(completed_yearly["CoR %"].dropna().tail(ma_window).mean()) if ratio_projection_available else np.nan,
    }

    chart_df = yearly[["UW_YEAR", gwp_display_col, "Loss Ratio %", "CoR %"]].copy()
    chart_df["UW_YEAR_LABEL"] = chart_df["UW_YEAR"].astype(str)
    chart_df["ACTUAL_TYPE"] = np.where(chart_df["UW_YEAR"].astype(int).eq(latest_year), "Latest Actual", "Actual")
    chart_df["GWP_LABEL"] = chart_df[gwp_display_col].map(lambda x: f"{x:,.0f}".replace(",", ".") if pd.notna(x) else "")
    chart_df["LR_LABEL"] = chart_df["Loss Ratio %"].map(lambda x: f"{x:.0f}%" if pd.notna(x) else "")
    chart_df["COR_LABEL"] = chart_df["CoR %"].map(lambda x: f"{x:.0f}%" if pd.notna(x) else "")

    x_axis = alt.X(
        "UW_YEAR_LABEL:N",
        title=None,
        sort=None,
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
    )


    no_axis_y = alt.Y(
        "Value:Q",
        title=None,
        scale=alt.Scale(domainMin=0, nice=True),
        axis=alt.Axis(labels=False, ticks=False, grid=False, domain=False),
    )

    def _fmt_int_pct(value):
        value = _finite_float(value)
        return f"{value:.0f}%" if np.isfinite(value) else "-"

    def _gwp_chart():
        actual = chart_df[["UW_YEAR_LABEL", "ACTUAL_TYPE", gwp_display_col, "GWP_LABEL"]].rename(columns={gwp_display_col: "Value"}).copy()
        actual["ACTUAL_TYPE"] = np.where(actual["UW_YEAR_LABEL"].eq(str(gwp_projection_year)), "Latest Actual", "Actual")
        projection = pd.DataFrame({
            "UW_YEAR_LABEL": [str(gwp_projection_year)],
            "Value": [projection_values.get(gwp_display_col, np.nan)],
        })
        projection = projection[pd.to_numeric(projection["Value"], errors="coerce").notna()].copy()
        projection["PROJ_LABEL"] = projection["Value"].map(lambda x: f"{x:,.0f}".replace(",", ".") if pd.notna(x) else "")

        bars = alt.Chart(actual).mark_bar(
            cornerRadiusTopLeft=8,
            cornerRadiusTopRight=8,
            size=34,
        ).encode(
            x=x_axis,
            y=no_axis_y,
            color=alt.Color(
                "ACTUAL_TYPE:N",
                title=None,
                scale=alt.Scale(domain=["Actual", "Latest Actual"], range=["#003366", "#E39A5B"]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("UW_YEAR_LABEL:N", title="UW Year"),
                alt.Tooltip("Value:Q", title=money_unit_label, format=",.1f"),
            ],
        )
        labels = alt.Chart(actual).mark_text(
            align="center",
            baseline="bottom",
            dy=-7,
            fontSize=12,
            color="#003366",
            fontWeight="bold",
        ).encode(x=x_axis, y=no_axis_y, text=alt.Text("GWP_LABEL:N"))

        marker = alt.Chart(projection).mark_tick(
            thickness=4,
            size=58,
            color="#C7893D",
        ).encode(
            x=x_axis,
            y=no_axis_y,
            tooltip=[
                alt.Tooltip("UW_YEAR_LABEL:N", title="UW Year"),
                alt.Tooltip("Value:Q", title=f"Projected {money_unit_label}", format=",.1f"),
            ],
        )
        marker_label = alt.Chart(projection).mark_text(
            align="center",
            baseline="bottom",
            dy=-9,
            fontSize=12,
            color="#8A5418",
            fontWeight="bold",
        ).encode(x=x_axis, y=no_axis_y, text=alt.Text("PROJ_LABEL:N"))

        return (bars + labels + marker + marker_label).properties(
            height=300,
            title=alt.TitleParams(
                text="GWP* Trend - Actual vs Projection",
                fontSize=15,
                fontWeight="bold",
                color="#003366",
                anchor="start",
                offset=14,
                dy=-4,
            ),
            background="transparent",
        ).configure_view(strokeWidth=0, fill="transparent").configure_axis(domainColor="#CBD5E1", grid=False)

    def _ratio_cor_chart():
        cor_plot = chart_df[["UW_YEAR_LABEL", "ACTUAL_TYPE", "CoR %", "COR_LABEL"]].rename(columns={"CoR %": "Value", "COR_LABEL": "VALUE_LABEL"}).copy()
        lr_plot = chart_df[["UW_YEAR_LABEL", "Loss Ratio %", "LR_LABEL"]].rename(columns={"Loss Ratio %": "Value", "LR_LABEL": "VALUE_LABEL"}).copy()
        ratio_max_for_label = pd.to_numeric(
            pd.concat([cor_plot["Value"], lr_plot["Value"]], ignore_index=True),
            errors="coerce",
        ).dropna()
        label_offset = max(4.0, float(ratio_max_for_label.max()) * 0.035) if not ratio_max_for_label.empty else 4.0
        lr_plot["LABEL_Y"] = pd.to_numeric(lr_plot["Value"], errors="coerce") + label_offset

        cor_bars = alt.Chart(cor_plot).mark_bar(
            cornerRadiusTopLeft=8,
            cornerRadiusTopRight=8,
            size=34,
        ).encode(
            x=x_axis,
            y=no_axis_y,
            color=alt.Color(
                "ACTUAL_TYPE:N",
                title=None,
                scale=alt.Scale(domain=["Actual", "Latest Actual"], range=["#003366", "#E39A5B"]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("UW_YEAR_LABEL:N", title="UW Year"),
                alt.Tooltip("Value:Q", title="CoR", format=".1f"),
            ],
        )
        cor_labels = alt.Chart(cor_plot).mark_text(
            align="center",
            baseline="bottom",
            dy=-7,
            fontSize=11,
            color="#003366",
            fontWeight="bold",
        ).encode(x=x_axis, y=no_axis_y, text=alt.Text("VALUE_LABEL:N"))

        lr_base = alt.Chart(lr_plot).encode(
            x=x_axis,
            y=no_axis_y,
            tooltip=[
                alt.Tooltip("UW_YEAR_LABEL:N", title="UW Year"),
                alt.Tooltip("Value:Q", title="Loss Ratio", format=".1f"),
            ],
        )
        lr_line = lr_base.mark_line(strokeWidth=3, point=False, color="#6F8FB1")
        lr_points = lr_base.mark_circle(size=58, stroke="#4F7092", strokeWidth=1.25, fill="#FFFFFF")



        lr_label_base = alt.Chart(lr_plot).encode(
            x=x_axis,
            y=alt.Y(
                "LABEL_Y:Q",
                title=None,
                scale=alt.Scale(domainMin=0, nice=True),
                axis=alt.Axis(labels=False, ticks=False, grid=False, domain=False),
            ),
        )
        lr_label_highlight = lr_label_base.mark_rect(
            width=34,
            height=14,
            color="#FFF3C4",
            opacity=0.86,
        )
        lr_labels = lr_label_base.mark_text(
            align="center",
            baseline="middle",
            fontSize=10.5,
            color="#173B5F",
            fontWeight="bold",
        ).encode(text=alt.Text("VALUE_LABEL:N"))

        cor_projection = pd.DataFrame({
            "UW_YEAR_LABEL": [str(latest_year)],
            "Value": [projection_values.get("CoR %", np.nan)],
        })
        cor_projection = cor_projection[pd.to_numeric(cor_projection["Value"], errors="coerce").notna()].copy()
        cor_projection["PROJ_LABEL"] = cor_projection["Value"].map(_fmt_int_pct)


        cor_proj_marker = alt.Chart(cor_projection).mark_tick(
            thickness=4,
            size=58,
            color="#C7893D",
        ).encode(
            x=x_axis,
            y=no_axis_y,
            tooltip=[
                alt.Tooltip("UW_YEAR_LABEL:N", title="UW Year"),
                alt.Tooltip("Value:Q", title="Projected CoR", format=".1f"),
            ],
        )
        cor_proj_label = alt.Chart(cor_projection).mark_text(
            align="center",
            baseline="bottom",
            dy=-9,
            fontSize=11,
            color="#8A5418",
            fontWeight="bold",
        ).encode(x=x_axis, y=no_axis_y, text=alt.Text("PROJ_LABEL:N"))

        ref_line = alt.Chart(pd.DataFrame({"Value": [100.0]})).mark_rule(color="#E2E8F0", strokeWidth=1).encode(y=alt.Y("Value:Q"))

        return alt.layer(
            ref_line,
            cor_bars,
            cor_labels,
            lr_line,
            lr_points,
            lr_label_highlight,
            lr_labels,
            cor_proj_marker,
            cor_proj_label,
        ).properties(
            height=300,
            title=alt.TitleParams(
                text="Loss Ratio & CoR",
                fontSize=15,
                fontWeight="bold",
                color="#003366",
                anchor="start",
                offset=14,
                dy=-4,
            ),
            background="transparent",
        ).configure_view(strokeWidth=0, fill="transparent").configure_axis(domainColor="#CBD5E1", grid=False)

    def _composition_chart():
        comp = _prepare_pdf_cob_composition_data(source_df, display_unit, min_share=10.0)
        if not comp.get("available"):
            st.info(comp.get("message", "No composition data available."))
            return
        rows = pd.DataFrame(comp.get("data", []) or [])
        if rows.empty:
            st.info("No composition data available.")
            return
        basis = comp.get("basis", "CoB")
        unit_short = _display_unit_short(display_unit)
        palette = ["#003366", "#2E5E8E", "#6F8FB1", "#E39A5B", "#C7893D", "#B8C7D6", "#D7E0EA"]
        if "label" in rows.columns:
            rows["_color"] = [palette[i % len(palette)] for i in range(len(rows))]
            rows.loc[rows["label"].astype(str).str.lower().eq("others"), "_color"] = "#B8C7D6"
        else:
            rows["_color"] = palette[:len(rows)]

        fig = go.Figure(data=[go.Pie(
            labels=rows["label"],
            values=rows["gwp_display"],
            hole=0.62,
            sort=False,
            direction="clockwise",
            textinfo="percent",
            textposition="inside",
            marker=dict(colors=rows["_color"].tolist(), line=dict(color="#FFFFFF", width=2)),
            hovertemplate=f"%{{label}}<br>GWP ({unit_short}): %{{value:,.1f}}<br>Share: %{{percent}}<extra></extra>",
        )])
        fig.update_layout(
            title={"text": f"GWP Portfolio Composition by {basis}", "x": 0.0, "xanchor": "left", "font": {"size": 15, "color": "#003366"}},
            height=300,
            margin=dict(l=8, r=8, t=48, b=18),
            showlegend=True,
            legend=dict(orientation="h", yanchor="top", y=-0.06, xanchor="center", x=0.5, font=dict(size=10, color="#334155")),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Arial, sans-serif", color="#334155"),
        )
        fig.add_annotation(
            text=f"GWP<br>{unit_short}",
            x=0.50,
            y=0.50,
            showarrow=False,
            font=dict(size=12, color="#003366"),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    def _legend_dot(color: str, label: str) -> str:
        return f"<span style='display:inline-flex;align-items:center;gap:6px;margin-right:12px;white-space:nowrap;'><span style='width:10px;height:10px;border-radius:999px;background:{color};display:inline-block;'></span>{html.escape(label)}</span>"

    def _legend_line(color: str, label: str) -> str:
        return f"<span style='display:inline-flex;align-items:center;gap:6px;margin-right:12px;white-space:nowrap;'><span style='width:22px;height:0;border-top:3px solid {color};display:inline-block;'></span>{html.escape(label)}</span>"

    def _legend_html(parts: list[str]) -> str:


        return "<div style='display:flex;align-items:flex-start;align-content:flex-start;gap:0;flex-wrap:wrap;min-height:42px;margin:0 0 2px 12px;color:#64748B;font-size:12px;font-weight:760;'>" + "".join(parts) + "</div>"

    projected_gwp_label = f"Projection {_pdf_compact_number(projection_values.get(gwp_display_col))}"
    projected_cor_label = f"Projected CoR {_fmt_int_pct(projection_values.get('CoR %'))}"
    projected_lr_label = f"Projected LR {_fmt_int_pct(projection_values.get('Loss Ratio %'))}"

    c1, c2, c3 = st.columns([1, 1, 1], gap="large")
    with c1:
        st.markdown(
            _legend_html([
                _legend_dot("#003366", "Actual"),
                _legend_dot("#E39A5B", "Latest Actual"),
                _legend_line("#C7893D", projected_gwp_label),
            ]),
            unsafe_allow_html=True,
        )
        st.altair_chart(_gwp_chart(), width="stretch")
    with c2:
        st.markdown(
            _legend_html([
                _legend_dot("#003366", "CoR"),
                _legend_line("#6F8FB1", "Loss Ratio"),
                _legend_line("#C7893D", projected_cor_label),
                f"<span style='display:inline-flex;align-items:center;margin-right:12px;white-space:nowrap;color:#8A5418;font-weight:850;'>{html.escape(projected_lr_label)}</span>",
            ]),
            unsafe_allow_html=True,
        )
        st.altair_chart(_ratio_cor_chart(), width="stretch")
    with c3:
        _composition_chart()

    if not ratio_projection_available:
        st.caption("Loss Ratio/CoR projection needs at least 2 completed UW years; GWP can still use its monthly run rate.")





def _sim_base_metrics(df: pd.DataFrame) -> dict:

    if df is None or df.empty:
        return {
            "GWP": 0.0, "GEP": 0.0, "CLAIM": 0.0, "CLAIM_COUNT": 0.0,
            "COMMISSIONS": 0.0, "RI_COST": 0.0, "RI_RECOVERY": 0.0,
            "OVR": 0.0, "OPEX": 0.0,
        }

    def s(col):
        return float(pd.to_numeric(df[col], errors="coerce").fillna(0.0).sum()) if col in df.columns else 0.0

    ri_cost = s("ERC_AMT") if "ERC_AMT" in df.columns else s("RI_COST")

    return {
        "GWP": s("GWP_AMT"),
        "GEP": s("GEP_AMT"),
        "CLAIM": s("GROSS_CLAIM"),
        "CLAIM_COUNT": s("NUMBER OF CLAIMS"),
        "COMMISSIONS": s("COMMISSIONS"),
        "RI_COST": ri_cost,
        "RI_RECOVERY": s("RI_RECOVERY"),
        "OVR": s("OVR_AMT"),
        "OPEX": s("OPEX_AMT"),
    }


def _sim_ratio(numerator, denominator):
    return (numerator / denominator) if denominator else np.nan


def _sim_pct_text(x) -> str:
    return f"{x:.2f}%" if pd.notna(x) else "-"


def _sim_full_scenario(gwp, gep, claim, claim_count, comm, ri_cost, ri_rec, ovr, opex) -> dict:

    lr = _sim_ratio(claim, gep)
    comm_r = _sim_ratio(comm, gwp)
    ri_cost_r = _sim_ratio(ri_cost, gep)
    ri_rec_r = _sim_ratio(ri_rec, gep)
    ovr_r = _sim_ratio(ovr, gwp)
    opex_r = _sim_ratio(opex, gwp)

    cor = (
        (lr if pd.notna(lr) else 0.0)
        + (comm_r if pd.notna(comm_r) else 0.0)
        + (ri_cost_r if pd.notna(ri_cost_r) else 0.0)
        - (ri_rec_r if pd.notna(ri_rec_r) else 0.0)
        + (opex_r if pd.notna(opex_r) else 0.0)
        + (ovr_r if pd.notna(ovr_r) else 0.0)
    )

    return {
        "GWP": gwp, "GEP": gep, "CLAIM": claim, "CLAIM_COUNT": claim_count,
        "COMMISSIONS": comm, "RI_COST": ri_cost, "RI_RECOVERY": ri_rec,
        "OVR": ovr, "OPEX": opex,
        "Loss Ratio": lr * 100 if pd.notna(lr) else np.nan,
        "COMM Ratio": comm_r * 100 if pd.notna(comm_r) else np.nan,
        "RI Cost Ratio": ri_cost_r * 100 if pd.notna(ri_cost_r) else np.nan,
        "RI Recovery Ratio": ri_rec_r * 100 if pd.notna(ri_rec_r) else np.nan,
        "OVR Ratio": ovr_r * 100 if pd.notna(ovr_r) else np.nan,
        "OPEX Ratio": opex_r * 100 if pd.notna(opex_r) else np.nan,
        "CoR": cor * 100 if pd.notna(cor) else np.nan,
    }

    
def _sim_avg_yearly_gwp(df: pd.DataFrame) -> float:





    if df is None or df.empty or "GWP_AMT" not in df.columns:
        return 0.0
    gwp = pd.to_numeric(df["GWP_AMT"], errors="coerce").fillna(0.0)
    total = float(gwp.sum())
    if "UW_YEAR" not in df.columns:
        return total
    try:
        years = int(df["UW_YEAR"].dropna().astype(int).nunique())
    except Exception:
        years = 0
    if years <= 0:
        return total
    return total / years

def _sim_run(base: dict, deductible_pct: float, premium_pct: float,
             commission_ratio_pct: float, ovr_ratio_pct: float,
             avg_yearly_gwp: float | None = None) -> tuple[dict, dict]:




















    actual = _sim_full_scenario(
        base["GWP"], base["GEP"], base["CLAIM"], base["CLAIM_COUNT"],
        base["COMMISSIONS"], base["RI_COST"], base["RI_RECOVERY"], base["OVR"], base["OPEX"],
    )

    gwp1 = base["GWP"] * (1.0 + premium_pct / 100.0)
    gep1 = base["GEP"] * (1.0 + premium_pct / 100.0)
    claim1 = base["CLAIM"] * (1.0 - deductible_pct / 100.0)
    claim_count1 = base["CLAIM_COUNT"]



    comm_ratio1 = commission_ratio_pct / 100.0
    ovr_ratio1 = ovr_ratio_pct / 100.0

    ri_cost_ratio0 = actual["RI Cost Ratio"] / 100.0 if pd.notna(actual["RI Cost Ratio"]) else 0.0
    ri_rec_ratio0 = actual["RI Recovery Ratio"] / 100.0 if pd.notna(actual["RI Recovery Ratio"]) else 0.0
    opex_ratio0 = actual["OPEX Ratio"] / 100.0 if pd.notna(actual["OPEX Ratio"]) else 0.0

    comm1 = comm_ratio1 * gwp1
    ovr1 = ovr_ratio1 * gwp1
    ri_cost1 = ri_cost_ratio0 * gep1
    ri_rec1 = ri_rec_ratio0 * gep1
    opex1 = opex_ratio0 * gwp1

    simulated = _sim_full_scenario(gwp1, gep1, claim1, claim_count1, comm1, ri_cost1, ri_rec1, ovr1, opex1)


    if avg_yearly_gwp is None or not np.isfinite(avg_yearly_gwp) or avg_yearly_gwp <= 0:
        avg_yearly_gwp = float(base["GWP"]) if base["GWP"] > 0 else 0.0

    cor_actual = actual.get("CoR", np.nan)
    cor_sim = simulated.get("CoR", np.nan)
    gwp_actual = float(base["GWP"]) if base["GWP"] is not None else 0.0

    underwriting_loss = np.nan
    expected_yearly_profit = np.nan
    bep_years = np.nan
    bep_months = 0
    bep_text = "-"

    if pd.notna(cor_actual) and pd.notna(cor_sim) and gwp_actual > 0:
        underwriting_loss = max(0.0, (float(cor_actual) - 100.0) / 100.0 * gwp_actual)
        expected_gwp_per_year = float(avg_yearly_gwp) * (1.0 + premium_pct / 100.0)
        expected_yearly_profit = (100.0 - float(cor_sim)) / 100.0 * expected_gwp_per_year

        if underwriting_loss <= 0:
            bep_text = "Immediate"
            bep_years = 0.0
            bep_months = 0
        elif expected_yearly_profit <= 0:
            bep_text = "Not achievable"
        else:
            bep_years = underwriting_loss / expected_yearly_profit
            bep_months = max(1, int(np.ceil(bep_years * 12)))
            yy = bep_months // 12
            mm = bep_months % 12
            if yy > 0 and mm > 0:
                bep_text = f"{yy} yr {mm} mo"
            elif yy > 0:
                bep_text = f"{yy} yr"
            else:
                bep_text = f"{mm} mo"

    simulated["BEP_Time_Text"] = bep_text
    simulated["BEP_Time_Years"] = bep_years
    simulated["BEP_Time_Months"] = bep_months
    simulated["Underwriting_Loss"] = underwriting_loss
    simulated["Expected_Yearly_Profit"] = expected_yearly_profit
    simulated["Avg_Yearly_GWP"] = float(avg_yearly_gwp) if np.isfinite(avg_yearly_gwp) else 0.0

    return actual, simulated


def _sim_build_comparison_df(actual: dict, simulated: dict, display_unit="in IDR Mio") -> pd.DataFrame:
    money_rows = [
        ("GWP", "GWP"), ("GEP (Earned Premium)", "GEP"), ("Gross Claim", "CLAIM"),
        ("Commission", "COMMISSIONS"), ("RI Cost", "RI_COST"), ("RI Recovery", "RI_RECOVERY"),
        ("OVR", "OVR"), ("OPEX", "OPEX"),
    ]
    pct_rows = [
        ("Loss Ratio", "Loss Ratio"), ("Commission Ratio", "COMM Ratio"),
        ("RI Cost Ratio", "RI Cost Ratio"), ("RI Recovery Ratio", "RI Recovery Ratio"),
        ("OVR Ratio", "OVR Ratio"), ("OPEX Ratio", "OPEX Ratio"), ("CoR", "CoR"),
    ]

    records = [(
        "Number of Claim Records",
        f"{int(actual['CLAIM_COUNT']):,}".replace(",", "."),
        f"{int(simulated['CLAIM_COUNT']):,}".replace(",", "."),
        "-",
    )]

    for label, key in money_rows:
        a, s = actual[key], simulated[key]
        records.append((
            label,
            _format_money_value(a, display_unit),
            _format_money_value(s, display_unit),
            _format_money_value(s - a, display_unit),
        ))

    for label, key in pct_rows:
        a, s = actual[key], simulated[key]
        a_txt = _sim_pct_text(a)
        s_txt = _sim_pct_text(s)
        d_txt = f"{(s - a):+.2f} pp" if pd.notna(a) and pd.notna(s) else "-"
        records.append((label, a_txt, s_txt, d_txt))

    return pd.DataFrame(records, columns=["Metric", "Actual", "Simulated", "\u0394 (Simulated - Actual)"])

def _sim_build_expected_table_df(simulated: dict, display_unit="in IDR Mio") -> pd.DataFrame:



    rows = [
        ("Loss Ratio",             simulated.get("Loss Ratio")),
        ("Commission Ratio",       simulated.get("COMM Ratio")),
        ("RI Cost Ratio",          simulated.get("RI Cost Ratio")),
        ("RI Recovery Ratio",      simulated.get("RI Recovery Ratio")),
        ("OPEX Ratio",             simulated.get("OPEX Ratio")),
        ("OVR Ratio",              simulated.get("OVR Ratio")),
        ("Combined Ratio (CoR)",   simulated.get("CoR")),
    ]
    records = []
    for label, val in rows:
        v = _finite_float(val)
        records.append((label, f"{v:.2f}%" if np.isfinite(v) else "-"))
    bep_text = str(simulated.get("BEP_Time_Text") or "-")
    records.append(("Expected BEP Time", bep_text))
    return pd.DataFrame(records, columns=["Metric", "Expected"])


def _render_sim_result_cards(actual: dict, simulated: dict, display_unit="in IDR Mio") -> None:
    def delta_pp(a, s):
        return f"{(s - a):+.2f} pp" if pd.notna(a) and pd.notna(s) else "-"

    unit = _display_unit_short(display_unit)
    cards = []
    for label, key, money in [
        (f"Earned Premium ({unit})", "GEP", True),
        (f"Gross Claim ({unit})", "CLAIM", True),
        ("Loss Ratio", "Loss Ratio", False),
        ("Commission Ratio", "COMM Ratio", False),
        ("OVR Ratio", "OVR Ratio", False),
        ("CoR (Simulated)", "CoR", False),
    ]:
        av, sv = actual.get(key, np.nan), simulated.get(key, np.nan)
        value = _format_money_value(sv, display_unit) if money else _sim_pct_text(sv)
        delta = _format_money_value(sv - av, display_unit) if money else delta_pp(av, sv)
        cards.append((label, value, f"Change: {delta}"))
    for label, key, help_text in [
        (f"Underwriting Loss ({unit})", "Underwriting_Loss", "(Actual CoR - 100%) x GWP"),
        (f"Expected Yearly Profit ({unit})", "Expected_Yearly_Profit", "(100% - Simulated CoR) x adjusted average yearly GWP"),
    ]:
        value = simulated.get(key, np.nan)
        cards.append((label, _format_money_value(value, display_unit) if pd.notna(value) else "-", help_text))
    cards.append(("Expected BEP Time", str(simulated.get("BEP_Time_Text") or "-"), ""))
    markup = "".join(
        "<div class='sim-compact-card' title='" + html.escape(note, quote=True) + "'>"
        "<div class='sim-card-label'>" + html.escape(label) + "</div>"
        "<div class='sim-card-value'>" + html.escape(str(value)) + "</div>"
        + ("<div class='sim-card-delta'>" + html.escape(note) + "</div>" if note.startswith("Change:") else "")
        + "</div>" for label, value, note in cards
    )
    st.markdown("""<style>
    .sim-compact-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin:6px 0 12px}
    .sim-compact-card{padding:9px 11px;border:1px solid #dbe5ef;border-radius:8px;background:#f6f8fb;min-width:0}
    .sim-card-label{font-size:11px;color:#475569;line-height:1.3}
    .sim-card-value{font-size:19px;font-weight:700;color:#003366;line-height:1.3;overflow-wrap:anywhere;margin-top:3px}
    .sim-card-delta{font-size:10px;color:#64748b;margin-top:2px}
    @media(max-width:1100px){.sim-compact-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
    @media(max-width:600px){.sim-compact-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
    </style><div class='sim-compact-grid'>""" + markup + "</div>", unsafe_allow_html=True)

    if pd.notna(simulated["CoR"]) and simulated["CoR"] > 100:
        st.warning(f"Simulated CoR is {_sim_pct_text(simulated['CoR'])} — this scenario is still loss-making (CoR > 100%).")
    elif pd.notna(actual["CoR"]) and pd.notna(simulated["CoR"]) and actual["CoR"] > 100 and simulated["CoR"] <= 100:
        st.success(f"This scenario turns the business profitable: CoR moves from {_sim_pct_text(actual['CoR'])} to {_sim_pct_text(simulated['CoR'])}.")

class _SimulationChart(Flowable):


    def __init__(self, actual, simulated, width=17.0 * cm, height=5.6 * cm):
        Flowable.__init__(self)
        self.actual = actual or {}
        self.simulated = simulated or {}
        self.width = float(width)
        self.height = float(height)

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def _val(self, d, key):
        try:
            v = float(d.get(key, np.nan))
            return v if np.isfinite(v) else np.nan
        except Exception:
            return np.nan

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        c.saveState()

        metrics = [
            ("Loss",     "Loss Ratio",          "#003366"),
            ("Comm",     "COMM Ratio",          "#2E5E8E"),
            ("RI Cost",  "RI Cost Ratio",       "#6F8FB1"),
            ("RI Rec",   "RI Recovery Ratio",   "#94A3B8"),
            ("OPEX",     "OPEX Ratio",          "#B8C7D6"),
            ("OVR",      "OVR Ratio",           "#C7893D"),
            ("CoR",      "CoR",                 "#B91C1C"),
        ]

        actual_vals = [self._val(self.actual, k) for _, k, _ in metrics]
        sim_vals = [self._val(self.simulated, k) for _, k, _ in metrics]
        all_vals = [v for v in actual_vals + sim_vals if np.isfinite(v)]
        max_val = max(all_vals + [100.0]) * 1.20 if all_vals else 120.0


        legend_x, legend_y = 1.4 * cm, h - 0.3 * cm
        for offset, label, color in [(0, "Actual", "#003366"), (1.6 * cm, "Simulated", "#E39A5B")]:
            c.setFillColor(colors.HexColor(color))
            c.rect(legend_x + offset, legend_y, 5, 5, stroke=0, fill=1)
            c.setFillColor(colors.HexColor("#475569"))
            c.setFont(PDF_FONT_REGULAR, 7)
            c.drawString(legend_x + offset + 8, legend_y, label)
        x0 = 1.35 * cm
        plot_w = w - x0 - 1.15 * cm
        plot_h = h - 0.8 * cm
        slot_h = plot_h / len(metrics)
        lower = min(all_vals + [0.0])
        upper = max(all_vals + [100.0])
        span = max(upper - lower, 1.0)
        def xpos(value):
            return x0 + (value - lower) / span * plot_w
        zero_x = xpos(0)
        c.setStrokeColor(colors.HexColor("#CBD5E1"))
        c.setLineWidth(0.4)
        c.line(zero_x, 0.15 * cm, zero_x, h - 0.6 * cm)
        c.setDash(2, 2)
        c.line(xpos(100), 0.15 * cm, xpos(100), h - 0.6 * cm)
        c.setDash()
        for i, ((label, key, _), av, sv) in enumerate(zip(metrics, actual_vals, sim_vals)):
            center_y = h - 0.7 * cm - slot_h * (i + 0.5)
            c.setFillColor(colors.HexColor("#475569"))
            c.setFont(PDF_FONT_REGULAR, 7)
            c.drawRightString(x0 - 5, center_y - 2, label)
            for value, offset, color in [(av, 2, "#003366"), (sv, -7, "#E39A5B")]:
                y = center_y + offset
                c.setFillColor(colors.HexColor(color))
                if np.isfinite(value):
                    end_x = xpos(value)
                    c.rect(min(zero_x, end_x), y, abs(end_x-zero_x), 6, stroke=0, fill=1)
                    text = f"{value:.1f}%"
                else:
                    text = "-"
                c.setFont(PDF_FONT_REGULAR, 6.5)
                c.drawRightString(w - 2, y, text)

        c.restoreState()

def _sim_pdf_context_elements(result: dict, username: str, styles) -> list:
    filter_style = ParagraphStyle(
        "SimFilterText", parent=styles["Normal"], fontSize=8.4, leading=11,
        textColor=colors.HexColor("#475569"), spaceAfter=2,
    )
    lines = [
        f"Generated by: {username} | At: {result.get('generated_at', '-')}",
        f"As of Date: {result.get('as_of_date') or '-'} | Display Unit: {_display_unit_label(result.get('display_unit'))}",
    ]
    active_filters_only = _active_filters_only(result.get("filters") or {})
    if active_filters_only:
        parts = []
        for col, info in active_filters_only.items():
            vals = info.get("values", [])
            mode = info.get("mode", "")
            parts.append(f"{col} ({mode}): {len(vals)} selected" if len(vals) > 6 else f"{col} ({mode}): {', '.join(map(str, vals))}")
        lines.append("Filters: " + " | ".join(parts))

    return [Paragraph(html.escape(line), filter_style) for line in lines] + [Spacer(1, 0.22 * cm)]


def _sim_pdf_two_columns(actual, simulated, display_unit, styles, avail_w):

    gap = 0.4 * cm
    chart_w = (avail_w - gap) * 0.54
    table_w = avail_w - gap - chart_w
    heading = ParagraphStyle("SimPanelHeading", parent=styles["Normal"],
                             fontName=PDF_FONT_BOLD, fontSize=9, leading=12, spaceAfter=6)
    header = ParagraphStyle("SimPanelHeader", parent=styles["Normal"],
                            fontName=PDF_FONT_BOLD, fontSize=8, leading=10, textColor=colors.white)
    cell = ParagraphStyle("SimPanelCell", parent=styles["Normal"],
                          fontName=PDF_FONT_REGULAR, fontSize=8, leading=10)
    right = ParagraphStyle("SimPanelRight", parent=cell, alignment=2)
    expected = _sim_build_expected_table_df(simulated, display_unit)
    data = [[Paragraph(html.escape(str(c)), header) for c in expected.columns]]
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FB")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i, (metric, value) in enumerate(expected.itertuples(index=False, name=None), 1):
        data.append([Paragraph(html.escape(str(metric)), cell), Paragraph(html.escape(str(value)), right)])
        if str(metric).startswith("Combined Ratio"):
            commands.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FFE7B8")))
    expected_table = Table(data, colWidths=[table_w * 0.60, table_w * 0.40], repeatRows=1)
    expected_table.setStyle(TableStyle(commands))
    _, table_h = expected_table.wrap(table_w, 1000)
    left = [Paragraph("Actual vs Simulated (%)", heading),
            _SimulationChart(actual, simulated, width=chart_w, height=max(6.4 * cm, table_h))]
    right_panel = [Paragraph("Expected Ratios After Adjustment", heading), expected_table]
    layout = Table([[left, "", right_panel]], colWidths=[chart_w, gap, table_w], hAlign="LEFT")
    layout.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return layout


def _sim_pdf_bottom_elements(result, styles):

    inputs = result.get("inputs", {})
    simulated = result.get("simulated", {})
    assumptions = (
        "Assumptions — Deductible: {ded:.2f}% | Adjust Premium: {prem:+.2f}% | "
        "Commission Ratio: {comm:.2f}% | OVR Ratio: {ovr:.2f}%"
    ).format(ded=inputs.get("deductible_pct", 0.0), prem=inputs.get("premium_pct", 0.0),
             comm=inputs.get("commission_ratio_pct", 0.0), ovr=inputs.get("ovr_ratio_pct", 0.0))
    recovery = str(simulated.get("BEP_Time_Text") or "-")
    if recovery == "Immediate":
        recovery_text = "recovery time is immediate (no existing underwriting loss)"
    elif recovery == "Not achievable":
        recovery_text = "recovery time is not achievable under this plan"
    elif recovery == "-":
        recovery_text = "recovery time is unavailable"
    else:
        recovery_text = f"recovery time in {recovery}"
    outcome = f"Expected long run behavior: CoR {_sim_pct_text(simulated.get('CoR', np.nan))} and {recovery_text}."
    note = ParagraphStyle("SimBottomNote", parent=styles["Normal"],
                          fontName=PDF_FONT_REGULAR, fontSize=8.4, leading=11, spaceAfter=6)
    emphasis = ParagraphStyle("SimBottomOutcome", parent=note,
                              fontName=PDF_FONT_BOLD, textColor=colors.HexColor("#003366"))
    return [Spacer(1, 0.25 * cm), Paragraph(html.escape(assumptions), note),
            Paragraph(html.escape(outcome), emphasis)]


def _sim_normalize_plans(plans):
    if isinstance(plans, dict):
        plans = [plans]
    return [p for p in (plans or []) if isinstance(p, dict) and p.get("simulated")]


def _sim_plans_for_export():

    if "sim_saved_plans" in st.session_state:
        return deepcopy(_sim_normalize_plans(st.session_state["sim_saved_plans"]))
    return deepcopy(_sim_normalize_plans(st.session_state.get("sim_last_result")))


def _sim_add_plan(result, name):
    plans = deepcopy(st.session_state.get("sim_saved_plans", []))
    plan = deepcopy(result)
    plan["plan_id"] = uuid.uuid4().hex
    plan["plan_name"] = name.strip() or f"Plan {len(plans) + 1}"
    plans.append(plan)
    st.session_state["sim_saved_plans"] = plans


def _sim_pdf_detailed_comparison(actual, simulated, display_unit, styles, avail_w):
    elements = []
    elements.append(Paragraph("<b>Detailed Comparison:</b>", styles["Normal"]))
    elements.append(Spacer(1, 0.12 * cm))
    df_cmp = _sim_build_comparison_df(actual, simulated, display_unit)

    cmp_header_style = ParagraphStyle(
        "SimCmpHeaderWrap", parent=styles["Normal"], alignment=1, textColor=colors.white,
        fontName=PDF_FONT_BOLD, fontSize=8.6, leading=10,
    )
    cmp_cell_left = ParagraphStyle(
        "SimCmpCellLeft", parent=styles["Normal"], alignment=0,
        fontName=PDF_FONT_REGULAR, fontSize=8.4, leading=10,
    )
    cmp_cell_right = ParagraphStyle(
        "SimCmpCellRight", parent=styles["Normal"], alignment=2,
        fontName=PDF_FONT_REGULAR, fontSize=8.4, leading=10,
    )

    cmp_data = [[Paragraph(col, cmp_header_style) for col in df_cmp.columns]]
    for _, row in df_cmp.iterrows():
        cmp_data.append([
            Paragraph(html.escape(str(row["Metric"])), cmp_cell_left),
            Paragraph(html.escape(str(row["Actual"])), cmp_cell_right),
            Paragraph(html.escape(str(row["Simulated"])), cmp_cell_right),
            Paragraph(html.escape(str(row["\u0394 (Simulated - Actual)"])), cmp_cell_right),
        ])

    cmp_table = Table(cmp_data, repeatRows=1, colWidths=[avail_w * 0.40, avail_w * 0.20, avail_w * 0.20, avail_w * 0.20])
    cmp_style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), PDF_FONT_BOLD),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for r in range(1, len(cmp_data)):
        row_color = colors.HexColor("#F6F8FB") if r % 2 == 0 else colors.white
        cmp_style_cmds.append(("BACKGROUND", (0, r), (-1, r), row_color))
    cor_row_idx = df_cmp.index[df_cmp["Metric"] == "CoR"].tolist()
    if cor_row_idx:
        cmp_style_cmds.append(("BACKGROUND", (0, cor_row_idx[0] + 1), (-1, cor_row_idx[0] + 1), colors.HexColor("#FFE7B8")))
        cmp_style_cmds.append(("FONTNAME", (0, cor_row_idx[0] + 1), (-1, cor_row_idx[0] + 1), PDF_FONT_BOLD))
    cmp_table.setStyle(TableStyle(cmp_style_cmds))
    elements.append(cmp_table)
    elements.append(Spacer(1, 0.3 * cm))

    return elements


def build_simulation_pdf(result, username: str = "guest") -> bytes:

    plans = _sim_normalize_plans(result)
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    pdf = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=1.4 * cm, rightMargin=1.4 * cm,
                            topMargin=1.2 * cm, bottomMargin=1.2 * cm)
    elements = []
    for index, plan in enumerate(plans, 1):
        if index > 1:
            elements.append(PageBreak())
        title = f"Run a Simulation — {plan.get('plan_name') or f'Plan {index}'}"
        elements.append(Paragraph(html.escape(title), styles["Title"]))
        elements.extend(_sim_pdf_context_elements(plan, username, styles))
        actual, simulated = plan.get("actual", {}), plan["simulated"]
        unit = plan.get("display_unit", "in IDR Mio")
        elements.append(_sim_pdf_two_columns(actual, simulated, unit, styles, pdf.width))
        elements.append(Spacer(1, 0.25 * cm))
        elements.extend(_sim_pdf_detailed_comparison(actual, simulated, unit, styles, pdf.width))
        elements.extend(_sim_pdf_bottom_elements(plan, styles))
    if not elements:
        elements.append(Paragraph("No simulation plans selected.", styles["Normal"]))
    pdf.build(elements,
              onFirstPage=lambda canvas, doc: draw_footer(canvas, doc, username),
              onLaterPages=lambda canvas, doc: draw_footer(canvas, doc, username))
    return buffer.getvalue()


def build_simulation_excel(result: dict, username: str = "guest") -> bytes:
    buffer = io.BytesIO()
    display_unit = result.get("display_unit")
    inputs = result["inputs"]
    df_cmp = _sim_build_comparison_df(result["actual"], result["simulated"], display_unit)
    expected_df = _sim_build_expected_table_df(result["simulated"], display_unit)

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        sheet_name = "Simulation"
        workbook = writer.book
        worksheet = workbook.add_worksheet(sheet_name)
        writer.sheets[sheet_name] = worksheet

        header_fmt = workbook.add_format({
            "bold": True, "bg_color": "#003366", "font_color": "white",
            "align": "center", "valign": "vcenter", "border": 1, "border_color": "#D7E0EA",
        })
        note_fmt = workbook.add_format({"italic": True, "font_color": "#555555"})
        title_fmt = workbook.add_format({"bold": True, "font_size": 13, "font_color": "#003366"})
        cor_fmt = workbook.add_format({"bold": True, "bg_color": "#FFE7B8"})

        worksheet.write(0, 0, "Run a Simulation — What-If Report", title_fmt)
        worksheet.write(1, 0, f"As of Date: {result.get('as_of_date') or '-'}", note_fmt)
        worksheet.write(2, 0, f"Display Unit: {_display_unit_label(display_unit)}", note_fmt)
        worksheet.write(3, 0, f"Generated by: {username} | At: {result.get('generated_at', '-')}", note_fmt)
        worksheet.write(
            4, 0,
            f"Assumptions - Deductible: {inputs.get('deductible_pct', 0.0):.2f}% | "
            f"Adjust Premium: {inputs.get('premium_pct', 0.0):+.2f}% | "
            f"Commission Ratio: {inputs.get('commission_ratio_pct', 0.0):.2f}% | "
            f"OVR Ratio: {inputs.get('ovr_ratio_pct', 0.0):.2f}%",
            note_fmt,
        )
        active_filters_only = _active_filters_only(result.get("filters") or {})
        if active_filters_only:
            parts = []
            for col, info in active_filters_only.items():
                vals = info.get("values", [])
                mode = info.get("mode", "")
                parts.append(f"{col} ({mode}): {len(vals)} selected" if len(vals) > 6 else f"{col} ({mode}): {', '.join(map(str, vals))}")
            worksheet.write(5, 0, "Filters: " + " | ".join(parts), note_fmt)


        worksheet.write(7, 0, "Expected Ratios After Adjustment", title_fmt)
        worksheet.write(8, 0, "Metric", header_fmt)
        worksheet.write(8, 1, "Expected", header_fmt)
        for i, (_, row) in enumerate(expected_df.iterrows()):
            excel_row = 9 + i
            is_cor = str(row["Metric"]).strip().lower().startswith("combined ratio")
            if is_cor:
                worksheet.write(excel_row, 0, row["Metric"], cor_fmt)
                worksheet.write(excel_row, 1, row["Expected"], cor_fmt)
            else:
                worksheet.write(excel_row, 0, row["Metric"])
                worksheet.write(excel_row, 1, row["Expected"])


        cmp_start = 9 + len(expected_df) + 2
        worksheet.write(cmp_start - 1, 0, "Detailed Comparison", title_fmt)
        for col_idx, col_name in enumerate(df_cmp.columns):
            worksheet.write(cmp_start, col_idx, str(col_name), header_fmt)
        for r, (_, row) in enumerate(df_cmp.iterrows()):
            for c_idx, val in enumerate(row.tolist()):
                worksheet.write(cmp_start + 1 + r, c_idx, val)
        worksheet.set_column(0, 0, 26)
        worksheet.set_column(1, 3, 20)
        worksheet.hide_gridlines(2)


        actual_sheet = "Actual Data"
        ws_actual = workbook.add_worksheet(actual_sheet)
        writer.sheets[actual_sheet] = ws_actual
        ws_actual.write(0, 0, "Actual Baseline (before simulation)", title_fmt)
        ws_actual.write(1, 0, f"As of Date: {result.get('as_of_date') or '-'}", note_fmt)
        ws_actual.set_column(0, 0, 26)
        ws_actual.set_column(1, 1, 22)

        actual_row_labels = [
            ("Number of Claim Records", int(result["actual"]["CLAIM_COUNT"])),
            ("GWP", result["actual"]["GWP"]),
            ("GEP (Earned Premium)", result["actual"]["GEP"]),
            ("Gross Claim", result["actual"]["CLAIM"]),
            ("Commission", result["actual"]["COMMISSIONS"]),
            ("RI Cost", result["actual"]["RI_COST"]),
            ("RI Recovery", result["actual"]["RI_RECOVERY"]),
            ("OVR", result["actual"]["OVR"]),
            ("OPEX", result["actual"]["OPEX"]),
            ("Loss Ratio (%)", result["actual"]["Loss Ratio"]),
            ("Commission Ratio (%)", result["actual"]["COMM Ratio"]),
            ("RI Cost Ratio (%)", result["actual"]["RI Cost Ratio"]),
            ("RI Recovery Ratio (%)", result["actual"]["RI Recovery Ratio"]),
            ("OVR Ratio (%)", result["actual"]["OVR Ratio"]),
            ("OPEX Ratio (%)", result["actual"]["OPEX Ratio"]),
            ("CoR (%)", result["actual"]["CoR"]),
        ]
        ws_actual.write(3, 0, "Metric", header_fmt)
        ws_actual.write(3, 1, "Value", header_fmt)
        for i, (label, val) in enumerate(actual_row_labels):
            ws_actual.write(4 + i, 0, label)
            ws_actual.write(4 + i, 1, val if pd.notna(val) else "")
        ws_actual.hide_gridlines(2)

    return buffer.getvalue()

def render_simulation_section(df_work: pd.DataFrame, display_unit: str = "in IDR Mio",
                               username: str = "guest", active_filters: dict | None = None,
                               as_of_date=None) -> None:

    render_section_card_header(
        "Run a Simulation",
        "What-if: adjust deductible, premium, commission dan OVR untuk melihat hasil Loss Ratio & CoR.",
    )
    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

    if df_work is None or df_work.empty:
        st.info("No data on this filter to simulate.")
        return

    base = _sim_base_metrics(df_work)
    base_lr = _sim_ratio(base["CLAIM"], base["GEP"])
    avg_yearly_gwp = _sim_avg_yearly_gwp(df_work)
    actual_comm_ratio_pct = float(base["COMMISSIONS"] / base["GWP"] * 100.0) if base["GWP"] else 0.0
    baseline_signature = _compute_export_signature({"base": base, "filters": active_filters or {}, "as_of": str(as_of_date), "avg_yearly_gwp": avg_yearly_gwp, "simulation_version": 2})
    previous_result = st.session_state.get("sim_last_result")
    if previous_result and previous_result.get("baseline_signature") != baseline_signature:
        st.session_state.pop("sim_last_result", None)
        st.info("Data atau asumsi portofolio berubah. Klik Run Simulation untuk menghitung ulang skenario dengan OPEX dan OVR terbaru.")

    st.caption(
        f"Baseline actual (current filter, {_display_unit_label(display_unit)}): "
        f"Earned Premium {_format_money_value(base['GEP'], display_unit)} | "
        f"Gross Claim {_format_money_value(base['CLAIM'], display_unit)} "
        f"({int(base['CLAIM_COUNT']):,} claim records) | "
        f"Loss Ratio {_sim_pct_text(base_lr * 100 if pd.notna(base_lr) else np.nan)}."
    )

    with st.expander("Simulation Assumptions", expanded=False):

        use_current_comm = st.checkbox(
            "Use Current Commission Ratio",
            value=True,
            key="sim_use_current_commission",
            help=f"Current actual Commission Ratio (Total Commission / GWP): {actual_comm_ratio_pct:.2f}%",
        )

        use_current_ovr = st.checkbox("Use Current OVR Ratio", value=True, key="sim_use_current_ovr",
                                      help="Gunakan OVR aktif portofolio. Nonaktifkan untuk mengganti OVR khusus skenario ini.")
        current_ovr_pct = float(base["OVR"] / base["GWP"] * 100.0) if base["GWP"] else 0.0


        manual_ratio_defaults = {}
        for use_current, saved_key, widget_key, fallback, label in (
            (use_current_comm, "sim_commission_ratio_pct", "sim_input_commission_ratio_pct", actual_comm_ratio_pct, "Commission"),
            (use_current_ovr, "sim_ovr_ratio_pct", "sim_input_ovr_ratio_pct", 0.0, "OVR"),
        ):
            if not use_current:
                raw_default = float(st.session_state.get(saved_key, fallback))
                bounded_default = min(100.0, max(0.0, raw_default)) if np.isfinite(raw_default) else 0.0
                manual_ratio_defaults[saved_key] = bounded_default
                raw_widget = float(st.session_state.get(widget_key, bounded_default))
                bounded_widget = min(100.0, max(0.0, raw_widget)) if np.isfinite(raw_widget) else 0.0
                if widget_key in st.session_state and raw_widget != bounded_widget:
                    st.session_state[widget_key] = bounded_widget
                if raw_default != bounded_default or raw_widget != bounded_widget:
                    st.info(f"{label}: manual input is limited to 0–100%. Its starting value was adjusted to this range. Select Use Current to retain the actual ratio.")
        with st.form("run_simulation_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                deductible_pct = st.number_input(
                    "Adjust Deductible (%)",
                    min_value=0.0, max_value=100.0,
                    value=float(st.session_state.get("sim_deductible_pct", 0.0)),
                    step=1.0,
                    help="Semua klaim diasumsikan menanggung deductible ini: "
                         "Adjusted Claim = (1 - deductible%) x Gross Claim.",
                    key="sim_input_deductible_pct",
                )

                if use_current_comm:
                    st.number_input(
                        "Commission Ratio (%)",
                        min_value=None, max_value=None,
                        value=float(actual_comm_ratio_pct),
                        format="%.6f",
                        step=0.5,
                        disabled=True,
                        key=f"sim_input_commission_ratio_pct__locked_{actual_comm_ratio_pct:.10g}",
                        help="Locked to current actual Commission Ratio. "
                             "Uncheck 'Use Current Commission Ratio' to edit.",
                    )
                    commission_ratio_pct = float(actual_comm_ratio_pct)
                else:
                    commission_ratio_pct = st.number_input(
                        "Commission Ratio (%)",
                        min_value=0.0, max_value=100.0,
                        value=manual_ratio_defaults["sim_commission_ratio_pct"],
                        step=0.5,
                        key="sim_input_commission_ratio_pct",
                        help="SET langsung Commission Ratio ke angka ini (bukan relative). "
                             "Contoh: input 15 -> COMM Ratio = 15%.",
                    )
            with c2:
                premium_pct = st.number_input(
                    "Adjust Premium (%)",
                    min_value=-100.0, max_value=500.0,
                    value=float(st.session_state.get("sim_premium_pct", 0.0)),
                    step=1.0,
                    help="Naikkan/turunkan premi relatif terhadap premi saat ini. "
                         "Applied ke GWP dan Earned Premium.",
                    key="sim_input_premium_pct",
                )
                ovr_ratio_pct = st.number_input(
                    "OVR Ratio (%)",
                    min_value=None if use_current_ovr else 0.0,
                    max_value=None if use_current_ovr else 100.0,
                    value=current_ovr_pct if use_current_ovr else manual_ratio_defaults["sim_ovr_ratio_pct"],
                    format="%.6f",
                    disabled=use_current_ovr,
                    step=0.5,
                    help="SET langsung OVR Ratio ke angka ini (bukan relative). "
                         "Contoh: input 2 -> OVR Ratio = 2%.",
                    key=f"sim_input_ovr_ratio_pct__current_{current_ovr_pct:.10g}" if use_current_ovr else "sim_input_ovr_ratio_pct",
                )
            if use_current_ovr:
                ovr_ratio_pct = current_ovr_pct
            run_clicked = st.form_submit_button("Run Simulation", width="content")

        if run_clicked:
            st.session_state["sim_deductible_pct"] = deductible_pct
            st.session_state["sim_premium_pct"] = premium_pct
            st.session_state["sim_commission_ratio_pct"] = commission_ratio_pct
            st.session_state["sim_ovr_ratio_pct"] = ovr_ratio_pct

            actual, simulated = _sim_run(
                base, deductible_pct, premium_pct, commission_ratio_pct, ovr_ratio_pct,
                avg_yearly_gwp=avg_yearly_gwp,
            )
            st.session_state["sim_last_result"] = {
                "baseline_signature": baseline_signature,
                "base": base,
                "actual": actual,
                "simulated": simulated,
                "inputs": {
                    "deductible_pct": deductible_pct,
                    "premium_pct": premium_pct,
                    "commission_ratio_pct": commission_ratio_pct,
                    "ovr_ratio_pct": ovr_ratio_pct,
                },
                "avg_yearly_gwp": float(avg_yearly_gwp),
                "display_unit": display_unit,
                "as_of_date": as_of_date,
                "filters": dict(active_filters or {}),
                "generated_at": datetime.now(pytz.timezone("Asia/Jakarta")).strftime("%d %b %Y %H:%M WIB"),
            }

    result = st.session_state.get("sim_last_result")
    if not result:
        st.info("Set your assumptions above and click **Run Simulation** to see the result.")
        return

    actual = result["actual"]
    simulated = result["simulated"]

    _render_sim_result_cards(actual, simulated, display_unit)
    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

    comparison = _sim_build_comparison_df(actual, simulated, display_unit)
    header = "".join("<th>" + html.escape(str(c)) + "</th>" for c in comparison.columns)
    rows = "".join(
        "<tr" + (" class='sim-cor-row'" if str(row[0]) == "CoR" else "") + ">"
        + "".join("<td>" + html.escape(str(value)) + "</td>" for value in row) + "</tr>"
        for row in comparison.itertuples(index=False, name=None)
    )
    st.markdown("""<style>
    .sim-table-scroll{overflow:auto;max-height:460px;border:1px solid #dbe5ef;border-radius:8px;margin:4px 0 10px}
    .sim-blue-table{width:100%;border-collapse:separate;border-spacing:0;font-size:12px}
    .sim-blue-table th{background:#003366;color:white;padding:9px 12px;text-align:right;position:sticky;top:0;z-index:1}
    .sim-blue-table td{padding:7px 12px;border-bottom:1px solid #e2e8f0;text-align:right;white-space:nowrap}
    .sim-blue-table th:first-child,.sim-blue-table td:first-child{text-align:left}
    .sim-blue-table tr:nth-child(even){background:#f6f8fb}
    .sim-blue-table .sim-cor-row{background:#ffe7b8;font-weight:700}
    </style><div class='sim-table-scroll'><table class='sim-blue-table'><thead><tr>"""
        + header + "</tr></thead><tbody>" + rows + "</tbody></table></div>", unsafe_allow_html=True)

    st.markdown("**Plans for PDF**")
    st.caption("Run Simulation → beri nama → Add Plan to PDF. Ulangi untuk opsi berikutnya; setiap plan menjadi halaman tersendiri.")
    name_col, add_col = st.columns([3, 1])
    with name_col:
        plan_name = st.text_input("Plan name", key="sim_plan_name", max_chars=80,
                                  placeholder="Contoh: Plan A - Premium +15%")
    with add_col:
        st.write("")
        if st.button("Add Plan to PDF", key="sim_add_plan"):
            _sim_add_plan(result, plan_name)
            st.rerun()

    plans = st.session_state.get("sim_saved_plans", [])
    for index, plan in enumerate(plans):
        summary_col, remove_col = st.columns([6, 1])
        with summary_col:
            values = plan.get("simulated", {})
            st.write(f"{index + 1}. {plan.get('plan_name', 'Plan')} | "
                     f"CoR {_sim_pct_text(values.get('CoR', np.nan))} | "
                     f"Recovery: {values.get('BEP_Time_Text', '-')}")
        with remove_col:
            if st.button("Remove", key=f"sim_remove_{plan['plan_id']}"):
                st.session_state["sim_saved_plans"] = plans[:index] + plans[index + 1:]
                st.rerun()
    if plans:
        st.caption(f"{len(plans)} plan akan dimasukkan ke Risk Profile PDF sesuai urutan di atas. Hasil terbaru perlu di-add agar ikut PDF.")
    elif "sim_saved_plans" in st.session_state:
        st.caption("Belum ada plan untuk PDF. Klik Add Plan to PDF untuk menyertakan hasil simulasi.")
    else:
        st.caption("Belum ada saved plan; PDF akan memakai hasil simulasi terbaru sampai kamu mulai menambahkan plan.")





def get_ovr_detail_df_for_export() -> pd.DataFrame:

    config = _get_applied_ovr_configuration()
    if config is None:
        return pd.DataFrame()

    mode = config.get("mode", "uniform")

    if mode == "uniform":
        pct = _safe_to_float(config.get("uniform_pct", 0.0), 0.0)
        return pd.DataFrame({
            "OVR_MODE": ["Sama untuk semua"],
            "OVR_PCT_INPUT": [pct],
        })

    dims = config.get("dims", []) or []
    rules_df = config.get("rules_df", pd.DataFrame())

    if rules_df is None or not isinstance(rules_df, pd.DataFrame) or rules_df.empty:
        return pd.DataFrame()

    detail = rules_df.copy()

    if "OVR_PCT_INPUT" not in detail.columns:
        for alt in ["OVR_PCT", "OVR %", "OVR"]:
            if alt in detail.columns:
                detail.rename(columns={alt: "OVR_PCT_INPUT"}, inplace=True)
                break

    base_cols = [c for c in dims if c in detail.columns]
    if "OVR_PCT_INPUT" in detail.columns:
        base_cols.append("OVR_PCT_INPUT")

    if "OVR_PCT_INPUT" not in base_cols:
        return pd.DataFrame()

    detail = detail[base_cols].copy()
    detail["OVR_PCT_INPUT"] = pd.to_numeric(detail["OVR_PCT_INPUT"], errors="coerce")
    detail = detail[detail["OVR_PCT_INPUT"].notna()].reset_index(drop=True)
    return detail


def _format_ovr_detail_for_export(ovr_detail_df: pd.DataFrame) -> pd.DataFrame:
    if ovr_detail_df is None or ovr_detail_df.empty:
        return pd.DataFrame()

    out = ovr_detail_df.copy()
    if "OVR_PCT_INPUT" in out.columns:
        out["OVR_PCT_INPUT"] = pd.to_numeric(out["OVR_PCT_INPUT"], errors="coerce")
    return out


def build_ovr_detail_table_pdf(ovr_detail_df: pd.DataFrame, styles, context_elements=None):
    elements = [Paragraph("<b>OVR Detail</b>", styles["Title"])]
    if context_elements:
        elements.extend(context_elements)

    detail = _format_ovr_detail_for_export(ovr_detail_df)
    if detail.empty:
        elements.append(Paragraph("No confirmed OVR input detail.", styles["Normal"]))
        return elements

    note_style = ParagraphStyle(
        "OVRDetailNote",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#555555"),
        spaceAfter=8,
    )
    elements.append(Paragraph(
        "This page shows the OVR input confirmed by the user before export.",
        note_style,
    ))

    df_fmt = detail.copy()
    if "OVR_PCT_INPUT" in df_fmt.columns:
        df_fmt["OVR_PCT_INPUT"] = df_fmt["OVR_PCT_INPUT"].apply(
            lambda x: f"{float(x):.2f}%" if pd.notna(x) else ""
        )

    alias = {"OVR_MODE": "OVR MODE", "OVR_PCT_INPUT": "OVR (%)"}

    header_style = ParagraphStyle(
        "OVRDetailHeader",
        parent=styles["Normal"],
        alignment=1,
        textColor=colors.white,
        fontName=PDF_FONT_BOLD,
        fontSize=8,
        leading=9,
    )
    cell_style = ParagraphStyle("OVRDetailCell", parent=styles["Normal"], fontSize=8, leading=9)

    data = [[Paragraph(alias.get(col, col), header_style) for col in df_fmt.columns]]
    table_style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
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
            align = 2 if col == "OVR_PCT_INPUT" else 0
            row.append(Paragraph(
                "" if pd.isna(df_fmt.iloc[r, c]) else str(df_fmt.iloc[r, c]),
                ParagraphStyle(f"OVRDetailCell_{r}_{c}", parent=cell_style, alignment=align)
            ))
        data.append(row)

    avail_w = landscape(A4)[0] - (0.8 * cm) - (0.8 * cm)
    col_count = max(1, len(df_fmt.columns))
    col_widths = [(3.5 * cm if col == "OVR_PCT_INPUT" else max(4.0 * cm, min(8.0 * cm, avail_w / col_count))) for col in df_fmt.columns]
    total_w = sum(col_widths)
    if total_w > avail_w:
        factor = avail_w / total_w
        col_widths = [w * factor for w in col_widths]

    tbl = Table(data, repeatRows=1, colWidths=col_widths)
    tbl.setStyle(TableStyle(table_style_cmds))
    elements.extend([tbl, Spacer(1, 0.2 * cm)])
    return elements





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


def cached_filtered_claim_detail(risk_detail_df: pd.DataFrame, claim_path: str = RISK_PROFILE_CLAIM_PATH) -> pd.DataFrame:





    claim_df = load_claim_data(claim_path)
    return get_filtered_claim_detail(risk_detail_df, claim_df)


def build_claim_summary_df(claim_df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if claim_df is None or claim_df.empty or group_col not in claim_df.columns:
        return pd.DataFrame(columns=[group_col, "NUMBER OF CLAIMS", "NUMBER OF CLAIMS %", "GROSS CLAIM", "GROSS CLAIM %"])

    tmp = claim_df.copy()
    tmp[group_col] = tmp[group_col].fillna("(Blank)").astype(str)

    gross_source_col = next((c for c in ["GROSS CLAIM", "GROSS_CLAIM", "GROSS"] if c in tmp.columns), None)
    if gross_source_col:
        tmp["GROSS CLAIM"] = pd.to_numeric(tmp[gross_source_col], errors="coerce").fillna(0.0)
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


def cached_claim_chart_df(claim_detail_df: pd.DataFrame, group_col: str, top_n: int = 9) -> pd.DataFrame:

    return build_claim_chart_df(claim_detail_df, group_col, top_n=top_n)


LARGE_LOSS_DISPLAY_COLUMNS = [
    "Claim No",
    "Policy No",
    "Status",
    "Intermediary Name",
    "Insured Name",
    "Claim Code",
    "GROSS CLAIM",
    "REINSURANCE",
    "NET CLAIM",
]





def _normalize_policy_match_key(series: pd.Series) -> pd.Series:






    s = series.astype("string").fillna("").str.strip()
    s = s.str.replace("\u00a0", "", regex=False).str.replace(" ", "", regex=False)
    s = s.str.replace(r"\.0$", "", regex=True)
    return s.str.upper()


def _claim_col_norm(name) -> str:
    return "".join(ch for ch in str(name or "").strip().upper() if ch.isalnum())


LARGE_LOSS_TEXT_ALIASES = {
    "Claim No": ["CLAIM NO", "CLAIM_NO", "CLAIM NUMBER", "CLAIM_NUM", "CLAIM_NBR", "CLM_NO", "CLM NUMBER", "NO KLAIM", "NOMOR KLAIM", "NO CLAIM"],
    "Policy No": ["POLICY_NO", "POLICY NUMBER", "POLICY_NUM", "POLICY_NBR", "NO POLIS", "NOMOR POLIS"],
    "Status": ["STATUS", "CLAIM_STATUS", "CLM_STATUS"],
    "Intermediary Name": ["INTERMEDIARY_NAME", "INTERMEDIARY", "ACCOUNT_NAME", "BROKER_NAME", "AGENT_NAME", "NAMA INTERMEDIARY"],
    "Insured Name": ["INSURED_NAME", "INSURED", "POLICY_HOLDER_NAME", "POLICYHOLDER_NAME", "NAMA TERTANGGUNG"],
    "Claim Code": ["KODE_KLAIM", "CLAIM_CODE", "KODE CLAIM"],
}


def _large_loss_text(series: pd.Series) -> pd.Series:
    text = series.astype("string").fillna("").str.strip()
    return text.mask(text.str.lower().isin(["nan", "none", "null", "<na>", "nat", "n/a", "-", "—"]), "")


def _coalesce_large_loss_text(df: pd.DataFrame, candidates: list[str]) -> pd.Series:

    out = pd.Series("", index=df.index, dtype="string")
    positions = []
    for candidate in candidates:
        key = _claim_col_norm(candidate)
        for idx, col in enumerate(df.columns):
            if _claim_col_norm(col) == key and idx not in positions:
                positions.append(idx)
    for candidate in candidates:
        key = _claim_col_norm(candidate)
        for idx, col in enumerate(df.columns):

            base = re.sub(r"(?:[_ .](?:x|y|\d+))+$", "", str(col), flags=re.I)
            if _claim_col_norm(base) == key and idx not in positions:
                positions.append(idx)
    for idx in positions:
        values = _large_loss_text(df.iloc[:, idx])
        out = out.mask(out.eq(""), values)
    return out


def _enrich_large_loss_names(claims: pd.DataFrame, risk: pd.DataFrame) -> pd.DataFrame:

    out = claims.copy()
    claim_keys = _normalize_policy_match_key(_coalesce_large_loss_text(out, LARGE_LOSS_TEXT_ALIASES["Policy No"]))
    risk_keys = _normalize_policy_match_key(_coalesce_large_loss_text(risk, LARGE_LOSS_TEXT_ALIASES["Policy No"]))
    for label, canonical in [("Intermediary Name", "INTERMEDIARY_NAME"), ("Insured Name", "INSURED_NAME")]:
        current = _coalesce_large_loss_text(out, LARGE_LOSS_TEXT_ALIASES[label])
        values = _coalesce_large_loss_text(risk, LARGE_LOSS_TEXT_ALIASES[label])
        pairs = pd.DataFrame({"key": risk_keys, "value": values})
        pairs = pairs[pairs["key"].ne("") & pairs["value"].ne("")].drop_duplicates()
        unique_keys = pairs.groupby("key")["value"].nunique()
        mapping = pairs[pairs["key"].isin(unique_keys[unique_keys.eq(1)].index)].drop_duplicates("key").set_index("key")["value"]
        looked_up = claim_keys.map(mapping).fillna("")
        out[canonical] = looked_up.mask(looked_up.eq(""), current)
    return out


def _nonblank_column_score(series: pd.Series) -> int:






    try:
        s = series.astype("string").fillna("").str.strip()
        return int(s.ne("").sum())
    except Exception:
        try:
            return int(series.notna().sum())
        except Exception:
            return 0


def _dedupe_claim_columns_by_best_value(df: pd.DataFrame) -> pd.DataFrame:

    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame() if df is None else df

    groups = {}
    for idx, col in enumerate(df.columns):
        groups.setdefault(_claim_col_norm(col) or f"__COL_{idx}", []).append(idx)
    out = pd.DataFrame(index=df.index)
    for positions in groups.values():
        ranked = sorted(positions, key=lambda idx: _nonblank_column_score(df.iloc[:, idx]), reverse=True)
        values = df.iloc[:, ranked[0]].copy()
        for idx in ranked[1:]:
            missing = _large_loss_text(values).eq("")
            values = values.where(~missing, df.iloc[:, idx])
        out[str(df.columns[ranked[0]])] = values
    return out


def _extract_uw_year_number(series: pd.Series) -> pd.Series:












    if series is None:
        return pd.Series(dtype="float64")

    s = series.astype("string").fillna("").str.strip()
    s = s.str.replace(r"\.0$", "", regex=True)

    direct = pd.to_numeric(s, errors="coerce")


    direct_year = direct.where(direct.between(1900, 2100, inclusive="both"))




    period_year = (direct // 100).where(direct.between(190001, 210012, inclusive="both"))

    extracted = s.str.extract(r"(19\d{2}|20\d{2}|21\d{2})", expand=False)
    extracted_year = pd.to_numeric(extracted, errors="coerce")

    return direct_year.fillna(period_year).fillna(extracted_year)


def get_filtered_large_loss_detail(risk_detail_df: pd.DataFrame, claim_df: pd.DataFrame) -> pd.DataFrame:





    if not isinstance(risk_detail_df, pd.DataFrame) or not isinstance(claim_df, pd.DataFrame):
        return pd.DataFrame()
    if risk_detail_df.empty or claim_df.empty:
        return pd.DataFrame()

    claims = claim_df.copy()
    if "CLAIM NO" in claims.index.names and "CLAIM NO" not in claims.columns:
        claims = claims.reset_index(level="CLAIM NO")
    claims = claims.reset_index(drop=True)
    claim_numbers = _coalesce_large_loss_text(claims, ["CLAIM NO", "CLAIM_NO", "CLAIM NUMBER", "CLM_NO"])
    policy_numbers = _coalesce_large_loss_text(claims, LARGE_LOSS_TEXT_ALIASES["Policy No"])
    claims = _dedupe_claim_columns_by_best_value(claims)
    claims["__SOURCE_CLAIM_NO__"] = claim_numbers.to_numpy()
    claims["__SOURCE_POLICY_NO__"] = policy_numbers.to_numpy()
    claims["__CLAIM_POLICY_KEY__"] = _normalize_policy_match_key(policy_numbers).to_numpy()

    risk = _dedupe_claim_columns_by_best_value(risk_detail_df.reset_index(drop=True))
    policy_keys = _normalize_policy_match_key(_coalesce_large_loss_text(risk, LARGE_LOSS_TEXT_ALIASES["Policy No"]))
    lookup = pd.DataFrame({"__CLAIM_POLICY_KEY__": policy_keys})
    lookup = lookup[lookup["__CLAIM_POLICY_KEY__"].ne("")].drop_duplicates()

    matched = claims.merge(lookup, on="__CLAIM_POLICY_KEY__", how="inner", validate="many_to_one", sort=False)
    matched = _enrich_large_loss_names(matched, risk)
    return matched.drop(columns=["__CLAIM_POLICY_KEY__"]).reset_index(drop=True)


def _claim_col_norm(name) -> str:
    return "".join(ch for ch in str(name or "").strip().upper() if ch.isalnum())


def _resolve_claim_column(df: pd.DataFrame, candidates: list[str]) -> str | None:

    if df is None or not isinstance(df, pd.DataFrame):
        return None
    norm_map = {}
    for col in df.columns:
        norm_map.setdefault(_claim_col_norm(col), col)
    for cand in candidates:
        key = _claim_col_norm(cand)
        if key in norm_map:
            return norm_map[key]
    return None


def _first_nonblank(series: pd.Series):
    if series is None:
        return ""
    try:
        vals = series.dropna().astype("string").str.strip()
        vals = vals[vals.ne("")]
        if not vals.empty:
            return vals.iloc[0]
    except Exception:
        try:
            vals = [str(x).strip() for x in series.tolist() if str(x).strip() and str(x).lower() != "nan"]
            return vals[0] if vals else ""
        except Exception:
            return ""
    return ""


def build_large_loss_df(claim_detail_df: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:










    if claim_detail_df is None or not isinstance(claim_detail_df, pd.DataFrame) or claim_detail_df.empty:
        return pd.DataFrame(columns=LARGE_LOSS_DISPLAY_COLUMNS)

    source = _dedupe_claim_columns_by_best_value(claim_detail_df.copy())
    if source.empty:
        return pd.DataFrame(columns=LARGE_LOSS_DISPLAY_COLUMNS)

    gross_col = _resolve_claim_column(source, ["GROSS", "GROSS CLAIM", "GROSS_CLAIM", "AMT_GROSS_CLAIM"])
    reins_col = _resolve_claim_column(source, ["REINSURANCE", "RI CLAIM", "RI_CLAIM", "RI RECOVERY", "RI_RECOVERY"])
    net_col = _resolve_claim_column(source, ["NET", "NET CLAIM", "NET_CLAIM"])

    out = pd.DataFrame(index=source.index)
    for label, aliases in LARGE_LOSS_TEXT_ALIASES.items():
        out[label] = _coalesce_large_loss_text(source, aliases).replace("", "Not available")
    if "__SOURCE_CLAIM_NO__" in source.columns:
        out["Claim No"] = _large_loss_text(source["__SOURCE_CLAIM_NO__"])
    if "__SOURCE_POLICY_NO__" in source.columns:
        out["Policy No"] = _large_loss_text(source["__SOURCE_POLICY_NO__"])
    out["GROSS CLAIM"] = pd.to_numeric(source[gross_col], errors="coerce").fillna(0.0) if gross_col else 0.0
    out["REINSURANCE"] = pd.to_numeric(source[reins_col], errors="coerce").fillna(0.0) if reins_col else 0.0
    out["NET CLAIM"] = pd.to_numeric(source[net_col], errors="coerce").fillna(0.0) if net_col else 0.0




    out = out.sort_values("GROSS CLAIM", ascending=False, kind="stable")
    out = out[out["GROSS CLAIM"].notna()].head(max(1, int(top_n or 5))).reset_index(drop=True)
    if out.empty:
        return pd.DataFrame(columns=LARGE_LOSS_DISPLAY_COLUMNS)


    out["Claim No"] = out["Claim No"].replace({"": "ID belum terbaca", "Not available": "ID belum terbaca"})
    return out[LARGE_LOSS_DISPLAY_COLUMNS]


def cached_large_loss_df(
    risk_detail_df: pd.DataFrame,
    claim_path: str = RISK_PROFILE_CLAIM_PATH,
    top_n: int = 5,
) -> pd.DataFrame:
    claim_df = load_claim_data(claim_path)


    claim_detail_df = get_filtered_large_loss_detail(risk_detail_df, claim_df)
    large_loss = build_large_loss_df(claim_detail_df, top_n=top_n)

    return large_loss


def render_large_loss_table(large_loss_df: pd.DataFrame, display_unit="in IDR Mio") -> None:
    render_section_card_header("List of Large Loss", "Top 5 largest gross claim amounts.")

    if large_loss_df is None or large_loss_df.empty:
        st.info("No large-loss claim rows found for the selected Policy No.")
        return

    df_show = large_loss_df.copy()
    money_cols = ["GROSS CLAIM", "REINSURANCE", "NET CLAIM"]
    for col in money_cols:
        if col in df_show.columns:
            df_show[col] = pd.to_numeric(df_show[col], errors="coerce").apply(lambda x: _format_money_value(x, display_unit))

    header_html = "".join(f"<th>{html.escape(str(c))}</th>" for c in LARGE_LOSS_DISPLAY_COLUMNS)
    rows_html = []
    for _, row in df_show[LARGE_LOSS_DISPLAY_COLUMNS].iterrows():
        cells = []
        for col in LARGE_LOSS_DISPLAY_COLUMNS:
            cls = "num-cell" if col in money_cols else "text-cell"
            val = "" if pd.isna(row[col]) else str(row[col])
            cells.append(f"<td class='{cls}'>{html.escape(val)}</td>")
        rows_html.append(f"<tr>{''.join(cells)}</tr>")

    unit_note = html.escape(_display_unit_note(display_unit))
    table_html = f"""
    <style>
      html, body {{ margin:0; padding:0; background:transparent; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Arial,sans-serif; }}
      .large-loss-note {{ margin:0 0 8px 0; color:#64748B; font-size:11.5px; font-weight:650; }}
      .large-loss-wrap {{ width:100%; overflow:auto; border:1px solid rgba(0,51,102,0.12); border-radius:16px; background:#FFFFFF; box-shadow:0 10px 28px rgba(15,23,42,0.055); }}
      .large-loss-table {{ border-collapse:separate; border-spacing:0; width:100%; min-width:1160px; }}
      .large-loss-table th {{ position:sticky; top:0; background:#003366; color:#FFFFFF; font-size:10.7px; line-height:1.12; font-weight:850; text-align:center; padding:10px 9px; border-right:1px solid rgba(255,255,255,0.18); white-space:nowrap; }}
      .large-loss-table td {{ font-size:11.3px; color:#334155; padding:8px 9px; border-bottom:1px solid rgba(15,23,42,0.055); border-right:1px solid rgba(15,23,42,0.045); font-weight:650; background:#FFFFFF; white-space:nowrap; }}
      .large-loss-table tr:nth-child(even) td {{ background:#F8FAFC; }}
      .large-loss-table tr:hover td {{ background:#EEF6FF; }}
      .large-loss-table .text-cell {{ text-align:left; color:#1E3A5F; }}
      .large-loss-table .num-cell {{ text-align:right; font-variant-numeric:tabular-nums; font-weight:780; color:#0F172A; }}
    </style>
    <div class="large-loss-note">{unit_note}. From selected Risk Profile Policy No, related claim rows are taken from the claim dataset and ranked by Gross Claim amount. Not available = missing or ambiguous in source data.</div>
    <div class="large-loss-wrap">
      <table class="large-loss-table">
        <thead><tr>{header_html}</tr></thead>
        <tbody>{''.join(rows_html)}</tbody>
      </table>
    </div>
    """
    _render_html_block(table_html, height=265, scrolling=False)


def render_large_loss_section(risk_detail_df: pd.DataFrame, display_unit="in IDR Mio") -> None:
    try:
        large_loss_df = cached_large_loss_df(risk_detail_df, top_n=5)
    except Exception as e:
        render_section_card_header("List of Large Loss", "Top 5 largest gross claim amounts.")
        st.warning(f"Large loss list is unavailable: {e}")
        return
    render_large_loss_table(large_loss_df, display_unit)
    if not large_loss_df.empty and large_loss_df["Claim No"].eq("ID belum terbaca").any():
        st.warning("Nomor klaim belum terbaca. Nilai kerugian tetap ditampilkan; periksa baris sumber melalui tombol di bawah.")
        if st.button("Periksa sumber CLAIM NO", key="large_loss_check_source"):
            try:
                path = RISK_PROFILE_CLAIM_PATH
                fresh = pd.read_excel(path)
                st.caption(f"File yang dibaca aplikasi: {os.path.abspath(path)}")
                st.write("Nama kolom asli:", [repr(c) for c in fresh.columns])
                fresh = fresh.reset_index(drop=True)
                policy_values = _coalesce_large_loss_text(fresh, LARGE_LOSS_TEXT_ALIASES["Policy No"])
                risk_values = _coalesce_large_loss_text(risk_detail_df, LARGE_LOSS_TEXT_ALIASES["Policy No"])
                mask = _normalize_policy_match_key(policy_values).isin(set(_normalize_policy_match_key(risk_values)))
                rows = fresh.loc[mask].copy()
                gross_col = _resolve_claim_column(rows, ["GROSS", "GROSS CLAIM", "GROSS_CLAIM", "AMT_GROSS_CLAIM"])
                if gross_col is not None:
                    order = pd.to_numeric(rows[gross_col], errors="coerce").fillna(0).sort_values(ascending=False, kind="stable").index
                    rows = rows.loc[order].head(5)
                else:
                    rows = rows.head(5)
                diagnostics = pd.DataFrame(index=rows.index)
                diagnostics["POLICY_NO sumber"] = policy_values.loc[rows.index]
                for idx, col in enumerate(rows.columns):
                    if "CLAIM" in _claim_col_norm(col) or "CLM" in _claim_col_norm(col):
                        diagnostics[f"{col!r} [kolom {idx}]"] = rows.iloc[:, idx].map(repr)
                diagnostics["CLAIM NO hasil pembacaan"] = _coalesce_large_loss_text(rows, LARGE_LOSS_TEXT_ALIASES["Claim No"])
                st.dataframe(diagnostics, hide_index=True, width="stretch")
                st.caption("Kirim tabel pemeriksaan ini untuk membedakan nilai sumber kosong, file yang berbeda, dan kesalahan pembacaan. repr menampilkan None, nan, atau string kosong secara eksplisit.")
                fresh_result = build_large_loss_df(get_filtered_large_loss_detail(risk_detail_df, fresh))
                if not fresh_result.empty and not fresh_result["Claim No"].eq("ID belum terbaca").any():
                    st.success("Nomor klaim tersedia saat file dibaca ulang. Jalankan ulang halaman dan buat ulang ekspor.")
                    for key in list(st.session_state):
                        if key.startswith(("export_pdf__", "export_xlsx__")):
                            st.session_state.pop(key, None)
            except Exception as exc:
                st.error(f"Pemeriksaan sumber gagal: {exc}")


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
    chart_height = max(230, min(430, 92 + 34 * len(order_df)))

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
        border-radius: 14px;
        padding: 10px 12px 10px 12px;
        background: #FFFFFF;
        box-shadow: 0 6px 16px rgba(15,23,42,0.035);
        box-sizing: border-box;
      }}
      .claim-head {{
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 7px;
        margin-bottom: 8px;
      }}
      .claim-title {{
        font-size: 13px;
        font-weight: 800;
        color: #003366;
        line-height: 1.12;
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
        font-size: 11.5px;
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
        padding: 5px 10px;
        font-size: 11.5px;
        font-weight: 800;
        color: #334155;
        cursor: pointer;
        user-select: none;
        box-shadow: 0 4px 12px rgba(15,23,42,0.035);
      }}
      .claim-controls input {{
        width: 13px;
        height: 13px;
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
        padding: 4px 0;
        border-bottom: 1px solid rgba(15,23,42,0.055);
      }}
      .claim-row:last-child {{ border-bottom: none; }}
      .claim-label {{
        font-size: 11.5px;
        font-weight: 700;
        color: #475569;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      .bar-stack {{ display: grid; gap: 3px; }}
      .bar-line {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) 48px;
        gap: 8px;
        align-items: center;
      }}
      .bar-track {{
        height: 10px;
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
        font-size: 10.5px;
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



    state_key = "cre_by_filter_hint_shown"
    if st.session_state.get(state_key, False):
        return

    st.session_state[state_key] = True
    st.markdown(
        '''
        <div class="claim-detail-toast"
             style="position: fixed; top: 154px; right: 22px; z-index: 9998; width: min(430px, calc(100vw - 44px)); padding: 14px 16px; border-radius: 14px; background: linear-gradient(135deg, rgba(12,110,106,0.98), rgba(19,141,117,0.98)); color: #FFFFFF; border: 1px solid rgba(184,255,241,0.55); border-left: 5px solid #B8FFF1; box-shadow: 0 22px 50px rgba(8,77,74,0.34); display: flex; gap: 10px; align-items: flex-start; animation: toastInOut 5.5s ease-in-out forwards;">
          <div style="width:22px; height:22px; border-radius:999px; background:rgba(255,255,255,0.22); color:#F4FFFD; display:flex; align-items:center; justify-content:center; font-weight:900; flex:0 0 auto; margin-top:1px;">i</div>
          <div style="font-size:13.5px; line-height:1.3; font-weight:650; color:#FFFFFF;"><b>Filter CRE_BY</b> untuk memantau polis-polis SmartUW dan Sipintar.</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )















def render_claim_breakdown_stable(risk_detail_df: pd.DataFrame) -> None:





    render_claim_breakdown_section(risk_detail_df)


def _claim_fragment_if_available(func):






    fragment = getattr(st, "fragment", None)
    if callable(fragment):
        try:
            return fragment(func)
        except Exception:
            pass
    return func


def _detailed_fragment_if_available(func):






    fragment = getattr(st, "fragment", None)
    if callable(fragment):
        try:
            return fragment(func)
        except Exception:
            pass
    return func


def _export_fragment_if_available(func):






    return func



def _render_claim_breakdown_selector_css() -> None:
    st.markdown("""
    <style>
      div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Claim breakdown view"]) {
        margin-top: 0 !important;
        margin-bottom: 4px !important;
      }
      div[role="radiogroup"][aria-label="Claim breakdown view"] {
        display: inline-flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 7px !important;
        padding: 2px 2px 4px 2px !important;
      }
      div[role="radiogroup"][aria-label="Claim breakdown view"] label {
        flex: 0 0 auto !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 7px 13px !important;
        margin: 0 !important;
        border-radius: 999px !important;
        border: 1px solid rgba(0,51,102,0.14) !important;
        background: #FFFFFF !important;
        color: #334155 !important;
        font-size: 12px !important;
        line-height: 1 !important;
        font-weight: 760 !important;
        box-shadow: 0 4px 12px rgba(15,23,42,0.035) !important;
      }
      div[role="radiogroup"][aria-label="Claim breakdown view"] label:has(input:checked) {
        background: linear-gradient(135deg, #003366 0%, #1F5A91 100%) !important;
        color: #FFFFFF !important;
        border-color: rgba(0,51,102,0.72) !important;
      }
      div[role="radiogroup"][aria-label="Claim breakdown view"] label:has(input:checked) * {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
      }
      div[role="radiogroup"][aria-label="Claim breakdown view"] input,
      div[role="radiogroup"][aria-label="Claim breakdown view"] svg {
        display: none !important;
      }
    </style>
    """, unsafe_allow_html=True)


@_claim_fragment_if_available
def render_claim_breakdown_section(risk_detail_df: pd.DataFrame) -> None:
    render_section_card_header("Claim Breakdown (%)", "Gross claim and claim count distribution by selected claim attributes.")

    try:
        claim_detail_df = cached_filtered_claim_detail(risk_detail_df)
    except Exception as e:
        st.warning(f"Claim breakdown is unavailable: {e}")
        return

    if claim_detail_df.empty:
        st.info("No matched claim data for the selected filters.")
        return

    _show_claim_breakdown_hint_once(claim_detail_df)




    show_gross_claim_pct = True
    show_number_of_claims_pct = True

    section_map = {
        "Claim Type": ("By Claim Type", "KODE_KLAIM"),
        "Cause Code": ("By Cause Code", "KODE_PENYEBAB"),
        "Internal Reason": ("By Internal Reason", "INTERNAL_REASON"),
    }
    _render_claim_breakdown_selector_css()
    master_active_key = "claim_breakdown_active_view"
    live_active_key = "claim_breakdown_active_view__live"
    if master_active_key not in st.session_state or st.session_state[master_active_key] not in section_map:
        st.session_state[master_active_key] = "Claim Type"
    st.session_state.setdefault(live_active_key, st.session_state[master_active_key])
    if st.session_state[live_active_key] not in section_map:
        st.session_state[live_active_key] = st.session_state[master_active_key]
    active_label = st.radio(
        "Claim breakdown view",
        options=list(section_map.keys()),
        key=live_active_key,
        horizontal=True,
        label_visibility="collapsed",
    )
    st.session_state[master_active_key] = active_label
    title, label_col = section_map[active_label]
    chart_df = cached_claim_chart_df(claim_detail_df, label_col, top_n=9)
    render_claim_breakdown_chart(
        chart_df,
        title,
        label_col,
        show_gross_claim_pct=show_gross_claim_pct,
        show_number_of_claims_pct=show_number_of_claims_pct,
    )



def build_large_loss_table_pdf(large_loss_df: pd.DataFrame, styles, display_unit="in IDR Mio", context_elements=None):
    elements = [Paragraph("<b>List of Large Loss</b>", styles["Title"])]
    if context_elements:
        elements.extend(context_elements)

    if large_loss_df is None or large_loss_df.empty:
        elements.append(Paragraph("No large-loss claim rows found for the selected Policy No.", styles["Normal"]))
        return elements

    df_fmt = large_loss_df.copy()
    for col in ["GROSS CLAIM", "REINSURANCE", "NET CLAIM"]:
        if col in df_fmt.columns:
            df_fmt[col] = pd.to_numeric(df_fmt[col], errors="coerce").apply(lambda x: _format_money_value(x, display_unit))

    note_style = ParagraphStyle(
        "LargeLossNote",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#555555"),
        spaceAfter=8,
    )
    elements.append(Paragraph(
        f"Top 5 largest Gross Claim rows from claim rows whose Policy No exists in the selected Risk Profile portfolio. {_display_unit_note(display_unit)}.",
        note_style,
    ))

    header_style = ParagraphStyle(
        "LargeLossHeader",
        parent=styles["Normal"],
        alignment=1,
        textColor=colors.white,
        fontName=PDF_FONT_BOLD,
        fontSize=6.6,
        leading=7.4,
    )
    cell_style = ParagraphStyle(
        "LargeLossCell",
        parent=styles["Normal"],
        fontSize=6.5,
        leading=7.2,
    )

    df_fmt = df_fmt[[c for c in LARGE_LOSS_DISPLAY_COLUMNS if c in df_fmt.columns]].copy()
    data = [[Paragraph(str(c), header_style) for c in df_fmt.columns]]
    table_style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]

    for r in range(len(df_fmt)):
        row_color = colors.HexColor("#F6F8FB") if r % 2 == 1 else colors.white
        table_style_cmds.append(("BACKGROUND", (0, r + 1), (-1, r + 1), row_color))
        row = []
        for c_idx, col in enumerate(df_fmt.columns):
            align = 2 if col in ["GROSS CLAIM", "REINSURANCE", "NET CLAIM"] else 0
            text_val = "" if pd.isna(df_fmt.iloc[r, c_idx]) else str(df_fmt.iloc[r, c_idx])
            row.append(Paragraph(html.escape(text_val), ParagraphStyle(f"LargeLossCell_{r}_{c_idx}", parent=cell_style, alignment=align)))
        data.append(row)

    avail_w = landscape(A4)[0] - (0.8 * cm) - (0.8 * cm)
    raw_widths = []
    for col in df_fmt.columns:
        if col in ["Claim No", "Policy No", "Status", "Claim Code"]:
            raw_widths.append(2.55 * cm)
        elif col in ["Intermediary Name", "Insured Name"]:
            raw_widths.append(4.6 * cm)
        else:
            raw_widths.append(2.8 * cm)
    total_w = sum(raw_widths)
    if total_w > avail_w and total_w > 0:
        factor = avail_w / total_w
        raw_widths = [w * factor for w in raw_widths]

    tbl = Table(data, repeatRows=1, colWidths=raw_widths)
    tbl.setStyle(TableStyle(table_style_cmds))
    elements.extend([tbl, Spacer(1, 0.2 * cm)])
    return elements


def build_claim_summary_table_pdf(summary_df: pd.DataFrame, title: str, label_col: str, styles, context_elements=None):
    elements = [Paragraph(f"<b>{title}</b>", styles["Title"])]
    if context_elements:
        elements.extend(context_elements)

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
        fontName=PDF_FONT_BOLD,
        fontSize=8,
        leading=9,
    )
    cell_style = ParagraphStyle(
        "ClaimSummaryCell",
        parent=styles["Normal"],
        fontSize=8,
        leading=9,
    )

    data = [[Paragraph(alias.get(col, col), header_style) for col in df_fmt.columns]]
    table_style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), PDF_FONT_BOLD),
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
                fontName=PDF_FONT_REGULAR,
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

def build_kpi_cards_pdf(kpis, styles, display_unit="in IDR Mio"):
    def fmt_money(x):
        return _format_money_value(x, display_unit)

    def fmt_pct(x):
        return f"{round(x):.0f}%" if pd.notna(x) else "-"


    zurich_blue = colors.HexColor("#003366")
    

    label_style = ParagraphStyle(
        "KPILabel",
        parent=styles["Normal"],
        alignment=1,
        fontSize=8,
        textColor=colors.white,
        fontName=PDF_FONT_BOLD,
        textTransform='uppercase'
    )
    

    value_style = ParagraphStyle(
        "KPIValue",
        parent=styles["Normal"],
        alignment=1,
        fontSize=10,
        textColor=zurich_blue, 
        fontName=PDF_FONT_BOLD,
        allowMarkup=True
    )


    status_dot = ""
    if pd.notna(kpis["CoR"]):
        dot_color = "#28A745" if kpis["CoR"] <= 100 else "#DC3545"
        status_dot = f" <font color='{dot_color}' size='10'>●</font>"

    headers = [
        Paragraph("TOTAL GWP*", label_style),
        Paragraph("LOSS RATIO", label_style),
        Paragraph("COMM RATIO", label_style),
        Paragraph("RI COST RATIO", label_style),
        Paragraph("RI RECOVERY", label_style),
        Paragraph("COMBINED RATIO", label_style)
    ]
    
    values = [
        Paragraph(fmt_money(kpis["GWP"]), value_style),
        Paragraph(fmt_pct(kpis["Loss Ratio"]), value_style),
        Paragraph(fmt_pct(kpis["COMM Ratio"]), value_style),
        Paragraph(fmt_pct(kpis["RI Cost Ratio"]), value_style),
        Paragraph(fmt_pct(kpis["RI Recovery Ratio"]), value_style),
        Paragraph(f"{fmt_pct(kpis['CoR'])}{status_dot}", value_style)
    ]
    

    if "OVR_AMT" in kpis:
        headers.append(Paragraph("OVERRIDE AMT", label_style))
        values.append(Paragraph(fmt_money(kpis["OVR_AMT"]), value_style))
    
    data = [headers, values]

    table = Table(data, colWidths=[3 * cm] * 6, rowHeights=[0.75 * cm, 0.75 * cm])

    table.setStyle(TableStyle([

        ("BACKGROUND", (0, 0), (-1, 0), zurich_blue),
        

        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        

        ("GRID", (0, 0), (-1, -1), 0.5, zurich_blue),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        

        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))

    return table





def _finite_float(value):
    try:
        value = float(value)
        return value if np.isfinite(value) else np.nan
    except Exception:
        return np.nan


def _pdf_compact_number(value, decimals: int = 0) -> str:
    value = _finite_float(value)
    if not np.isfinite(value):
        return "-"
    if decimals <= 0:
        return f"{value:,.0f}".replace(",", ".")
    return f"{value:,.{decimals}f}".replace(",", ".")


def _pdf_pct_label(value) -> str:
    value = _finite_float(value)
    return f"{value:.0f}%" if np.isfinite(value) else "-"


def _pdf_projection_hidden(actual_value, projection_value) -> bool:

    actual_value = _finite_float(actual_value)
    projection_value = _finite_float(projection_value)
    if not (np.isfinite(actual_value) and np.isfinite(projection_value)):
        return False
    return bool(projection_value > 0 and actual_value > 1.5 * projection_value)


def _prepare_pdf_trend_projection_data(source_df: pd.DataFrame, display_unit="in IDR Mio", as_of_date=None) -> dict:





    result = {
        "available": False,
        "message": "Trend projection unavailable.",
        "yearly": pd.DataFrame(),
        "projection": {},
        "hidden_projection_metrics": [],
    }

    if source_df is None or not isinstance(source_df, pd.DataFrame) or source_df.empty:
        result["message"] = "Trend projection unavailable: no data."
        return result

    required = {"UW_YEAR", "GWP_AMT", "GEP_AMT", "GROSS_CLAIM"}
    missing = [c for c in required if c not in source_df.columns]
    if missing:
        result["message"] = "Trend projection unavailable: missing " + ", ".join(missing) + "."
        return result

    tmp = _ensure_portfolio_cost_columns(source_df).copy()
    tmp["UW_YEAR"] = pd.to_numeric(tmp["UW_YEAR"], errors="coerce")
    tmp = tmp[tmp["UW_YEAR"].notna()].copy()
    if tmp.empty:
        result["message"] = "Trend projection unavailable: UW_YEAR is empty."
        return result

    ri_cost_source_col = "ERC_AMT" if "ERC_AMT" in tmp.columns else ("RI_COST" if "RI_COST" in tmp.columns else None)
    numeric_cols = ["GWP_AMT", "GEP_AMT", "GROSS_CLAIM", "COMMISSIONS", "RI_RECOVERY", "OVR_AMT", "OPEX_AMT"]
    if ri_cost_source_col:
        numeric_cols.append(ri_cost_source_col)

    for col in numeric_cols:
        if col in tmp.columns:
            tmp[col] = pd.to_numeric(tmp[col], errors="coerce").fillna(0.0)
        else:
            tmp[col] = 0.0

    tmp["_RI_COST_FOR_COR"] = tmp[ri_cost_source_col] if ri_cost_source_col else 0.0

    yearly = (
        tmp.groupby("UW_YEAR", as_index=False)
        .agg(
            GWP_AMT=("GWP_AMT", "sum"),
            GEP_AMT=("GEP_AMT", "sum"),
            GROSS_CLAIM=("GROSS_CLAIM", "sum"),
            COMMISSIONS=("COMMISSIONS", "sum"),
            RI_COST_FOR_COR=("_RI_COST_FOR_COR", "sum"),
            RI_RECOVERY=("RI_RECOVERY", "sum"),
            OVR_AMT=("OVR_AMT", "sum"),
            OPEX_AMT=("OPEX_AMT", "sum"),
        )
        .sort_values("UW_YEAR")
        .reset_index(drop=True)
    )
    yearly["UW_YEAR"] = yearly["UW_YEAR"].astype(int)

    factor = _display_unit_factor(display_unit)
    yearly["GWP_DISPLAY"] = yearly["GWP_AMT"] / factor
    yearly["Loss Ratio %"] = np.where(yearly["GEP_AMT"] > 0, yearly["GROSS_CLAIM"] / yearly["GEP_AMT"] * 100.0, np.nan)
    yearly["COMM Ratio %"] = np.where(yearly["GWP_AMT"] > 0, yearly["COMMISSIONS"] / yearly["GWP_AMT"] * 100.0, np.nan)
    yearly["RI Cost Ratio %"] = np.where(yearly["GEP_AMT"] > 0, yearly["RI_COST_FOR_COR"] / yearly["GEP_AMT"] * 100.0, np.nan)
    yearly["RI Recovery Ratio %"] = np.where(yearly["GEP_AMT"] > 0, yearly["RI_RECOVERY"] / yearly["GEP_AMT"] * 100.0, np.nan)
    yearly["OVR Ratio %"] = np.where(yearly["GWP_AMT"] > 0, yearly["OVR_AMT"] / yearly["GWP_AMT"] * 100.0, 0.0)
    yearly["OPEX Ratio %"] = np.where(yearly["GWP_AMT"] > 0, yearly["OPEX_AMT"] / yearly["GWP_AMT"] * 100.0, 0.0)
    yearly["CoR %"] = (
        yearly["Loss Ratio %"].fillna(0.0)
        + yearly["COMM Ratio %"].fillna(0.0)
        + yearly["RI Cost Ratio %"].fillna(0.0)
        - yearly["RI Recovery Ratio %"].fillna(0.0)
        + yearly["OPEX Ratio %"].fillna(0.0)
        + yearly["OVR Ratio %"].fillna(0.0)
    )

    latest_year = int(yearly["UW_YEAR"].max())
    complete_yearly = yearly[yearly["UW_YEAR"] < latest_year].copy()
    ratio_projection_available = len(complete_yearly) >= 2
    gwp_projection = _project_gwp_full_year(yearly, as_of_date)
    ma_window = min(3, len(complete_yearly))
    projection = {
        "UW_YEAR": latest_year,
        "GWP_YEAR": gwp_projection["year"] if gwp_projection["year"] is not None else latest_year,
        "GWP_DISPLAY": gwp_projection["projection"] / factor,
        "GWP_DETAILS": gwp_projection,
        "Loss Ratio %": _finite_float(complete_yearly["Loss Ratio %"].dropna().tail(ma_window).mean()) if ratio_projection_available else np.nan,
        "CoR %": _finite_float(complete_yearly["CoR %"].dropna().tail(ma_window).mean()) if ratio_projection_available else np.nan,
        "MA_WINDOW": ma_window,
    }

    latest_actual = yearly[yearly["UW_YEAR"] == latest_year].tail(1)
    hidden = []
    if not latest_actual.empty:
        latest_row = latest_actual.iloc[0]
        if _pdf_projection_hidden(latest_row.get("Loss Ratio %"), projection.get("Loss Ratio %")):
            hidden.append("Loss Ratio")
        if _pdf_projection_hidden(latest_row.get("CoR %"), projection.get("CoR %")):
            hidden.append("CoR")

    result.update({
        "available": True,
        "message": "",
        "yearly": yearly,
        "projection": projection,
        "hidden_projection_metrics": hidden,
    })
    return result


def _prepare_pdf_cob_composition_data(source_df: pd.DataFrame, display_unit="in IDR Mio", min_share: float = 10.0) -> dict:






    result = {
        "available": False,
        "message": "No GWP composition data available.",
        "data": [],
        "total_gwp_display": np.nan,
        "basis": "CoB",
        "column": None,
    }

    if source_df is None or not isinstance(source_df, pd.DataFrame) or source_df.empty or "GWP_AMT" not in source_df.columns:
        return result

    cob_col = next((c for c in ["COB", "CoB", "cob"] if c in source_df.columns), None)
    lob_col = next((c for c in ["LOB", "LoB", "lob"] if c in source_df.columns), None)

    def _clean_dim(s: pd.Series) -> pd.Series:
        return (
            s.astype("string")
            .fillna("Unspecified")
            .str.strip()
            .replace({"": "Unspecified", "nan": "Unspecified", "None": "Unspecified", "<NA>": "Unspecified"})
        )

    basis_col = cob_col
    basis_label = "CoB"
    if cob_col is not None:
        try:
            cob_values = _clean_dim(source_df[cob_col])
            nonblank_cob = [v for v in cob_values.dropna().unique().tolist() if str(v).strip() and str(v).strip() != "Unspecified"]
            if len(nonblank_cob) <= 1 and lob_col is not None:
                basis_col = lob_col
                basis_label = "LoB"
        except Exception:
            if lob_col is not None:
                basis_col = lob_col
                basis_label = "LoB"
    elif lob_col is not None:
        basis_col = lob_col
        basis_label = "LoB"

    if basis_col is None:
        result["message"] = "GWP composition unavailable: CoB/LoB column is missing."
        return result

    tmp = source_df[[basis_col, "GWP_AMT"]].copy()
    tmp["GWP_AMT"] = pd.to_numeric(tmp["GWP_AMT"], errors="coerce").fillna(0.0)
    tmp[basis_col] = _clean_dim(tmp[basis_col])
    summary = (
        tmp.groupby(basis_col, as_index=False, observed=True)["GWP_AMT"]
        .sum()
        .sort_values("GWP_AMT", ascending=False, kind="stable")
        .reset_index(drop=True)
    )
    summary = summary[summary["GWP_AMT"] > 0].copy()
    total = float(summary["GWP_AMT"].sum()) if not summary.empty else 0.0
    if total <= 0:
        result["message"] = f"No positive GWP composition data available by {basis_label}."
        result["basis"] = basis_label
        result["column"] = basis_col
        return result

    summary["Share %"] = summary["GWP_AMT"] / total * 100.0
    major = summary[summary["Share %"] >= float(min_share)].copy()
    minor = summary[summary["Share %"] < float(min_share)].copy()

    rows = []
    for _, row in major.iterrows():
        rows.append({
            "label": str(row[basis_col]),
            "gwp": float(row["GWP_AMT"]),
            "share": float(row["Share %"]),
            "gwp_display": float(row["GWP_AMT"]) / _display_unit_factor(display_unit),
        })

    if not minor.empty:
        other_gwp = float(minor["GWP_AMT"].sum())
        rows.append({
            "label": "Others",
            "gwp": other_gwp,
            "share": other_gwp / total * 100.0,
            "gwp_display": other_gwp / _display_unit_factor(display_unit),
        })

    if len(rows) > 6:
        top = rows[:5]
        rest = rows[5:]
        rest_gwp = sum(r["gwp"] for r in rest)
        rows = top + [{
            "label": "Others",
            "gwp": rest_gwp,
            "share": rest_gwp / total * 100.0 if total > 0 else 0.0,
            "gwp_display": rest_gwp / _display_unit_factor(display_unit),
        }]

    result.update({
        "available": True,
        "message": "",
        "data": rows,
        "total_gwp_display": total / _display_unit_factor(display_unit),
        "basis": basis_label,
        "column": basis_col,
    })
    return result


class _PdfExecutiveChartCard(Flowable):


    def __init__(self, title: str, chart_type: str, trend_data: dict, display_unit="in IDR Mio", width=12.8 * cm, height=6.35 * cm):
        Flowable.__init__(self)
        self.title = title
        self.chart_type = chart_type
        self.trend_data = trend_data or {}
        self.display_unit = display_unit
        self.width = float(width)
        self.height = float(height)

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def _map_y(self, value, y0, plot_h, max_value):
        value = _finite_float(value)
        if not np.isfinite(value) or max_value <= 0:
            return y0
        return y0 + max(0.0, min(value / max_value, 1.0)) * plot_h

    def _draw_card_base(self):
        c = self.canv
        w, h = self.width, self.height
        c.saveState()


        c.setFillColor(colors.HexColor("#003366"))
        title_font_size = 8.8 if len(str(self.title)) <= 28 else 7.2
        c.setFont(PDF_FONT_BOLD, title_font_size)
        c.drawString(0.18 * cm, h - 0.42 * cm, self.title)
        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont(PDF_FONT_REGULAR, 6.2)
        return c

    def _draw_empty(self, message: str):
        c = self._draw_card_base()
        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont(PDF_FONT_REGULAR, 7.4)
        c.drawCentredString(self.width / 2, self.height / 2, str(message or "No data available."))
        c.restoreState()

    def _draw_gwp(self):
        trend = self.trend_data
        if not trend.get("available"):
            self._draw_empty(trend.get("message", "No data available."))
            return

        yearly = trend.get("yearly", pd.DataFrame()).copy()
        projection = trend.get("projection", {}) or {}
        if yearly.empty or "GWP_DISPLAY" not in yearly.columns:
            self._draw_empty("No GWP trend data available.")
            return

        c = self._draw_card_base()
        w, h = self.width, self.height
        latest_year = int(projection.get("GWP_YEAR", projection.get("UW_YEAR", yearly["UW_YEAR"].max())))
        unit_short = _display_unit_short(self.display_unit)


        legend_x = w - 5.35 * cm
        c.setFillColor(colors.HexColor("#003366"))
        c.rect(legend_x, h - 0.55 * cm, 0.14 * cm, 0.14 * cm, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#475569"))
        c.setFont(PDF_FONT_REGULAR, 5.4)
        c.drawString(legend_x + 0.21 * cm, h - 0.55 * cm, "Actual")
        c.setFillColor(colors.HexColor("#E39A5B"))
        c.rect(legend_x + 1.12 * cm, h - 0.55 * cm, 0.14 * cm, 0.14 * cm, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#475569"))
        c.drawString(legend_x + 1.33 * cm, h - 0.55 * cm, "Latest")
        c.setStrokeColor(colors.HexColor("#C7893D"))
        c.setLineWidth(1.4)
        c.line(legend_x + 2.22 * cm, h - 0.48 * cm, legend_x + 2.52 * cm, h - 0.48 * cm)
        c.setFillColor(colors.HexColor("#475569"))
        c.drawString(legend_x + 2.62 * cm, h - 0.55 * cm, "Projection")

        x0, y0 = 0.68 * cm, 0.88 * cm
        plot_w, plot_h = w - 1.10 * cm, h - 1.82 * cm
        values = [_finite_float(v) for v in yearly["GWP_DISPLAY"].tolist()]
        proj_value = _finite_float(projection.get("GWP_DISPLAY"))
        max_value = max([v for v in values + [proj_value] if np.isfinite(v)] or [1.0]) * 1.18
        n = max(1, len(yearly))
        slot_w = plot_w / n
        bar_w = min(0.62 * cm, slot_w * 0.42)

        c.setStrokeColor(colors.HexColor("#CBD5E1"))
        c.setLineWidth(0.45)
        c.line(x0, y0, x0 + plot_w, y0)

        for i, (_, row) in enumerate(yearly.iterrows()):
            year = int(row["UW_YEAR"])
            value = _finite_float(row["GWP_DISPLAY"])
            center_x = x0 + slot_w * (i + 0.5)
            bar_x = center_x - bar_w / 2
            bar_y_top = self._map_y(value, y0, plot_h, max_value)
            bar_h = max(0.04 * cm, bar_y_top - y0) if np.isfinite(value) else 0
            c.setFillColor(colors.HexColor("#E39A5B") if year == latest_year else colors.HexColor("#003366"))
            c.roundRect(bar_x, y0, bar_w, bar_h, 2.2, stroke=0, fill=1)
            c.setFillColor(colors.HexColor("#1F2937"))
            c.setFont(PDF_FONT_REGULAR, 5.4)
            if np.isfinite(value):
                c.drawCentredString(center_x, min(h - 0.98 * cm, y0 + bar_h + 0.13 * cm), _pdf_compact_number(value))
            c.setFillColor(colors.HexColor("#475569"))
            c.setFont(PDF_FONT_REGULAR, 5.9 if n <= 6 else 5.2)
            c.drawCentredString(center_x, 0.43 * cm, str(year))

            if year == latest_year and np.isfinite(proj_value):
                py = self._map_y(proj_value, y0, plot_h, max_value)
                c.setStrokeColor(colors.HexColor("#C7893D"))
                c.setLineWidth(1.55)
                c.line(bar_x - 0.13 * cm, py, bar_x + bar_w + 0.13 * cm, py)
                c.setFillColor(colors.HexColor("#7A4A10"))
                c.setFont(PDF_FONT_BOLD, 5.3)
                c.drawCentredString(center_x, min(h - 0.70 * cm, py + 0.11 * cm), _pdf_compact_number(proj_value))

        c.restoreState()

    def _draw_ratio_cor(self):
        trend = self.trend_data
        if not trend.get("available"):
            self._draw_empty(trend.get("message", "No data available."))
            return

        yearly = trend.get("yearly", pd.DataFrame()).copy()
        projection = trend.get("projection", {}) or {}
        hidden_metrics = list(trend.get("hidden_projection_metrics", []) or [])
        if yearly.empty or "Loss Ratio %" not in yearly.columns or "CoR %" not in yearly.columns:
            self._draw_empty("No ratio trend data available.")
            return

        c = self._draw_card_base()
        w, h = self.width, self.height
        latest_year = int(projection.get("UW_YEAR", yearly["UW_YEAR"].max()))



        cor_proj_for_legend = _finite_float(projection.get("CoR %"))
        lr_proj_for_legend = _finite_float(projection.get("Loss Ratio %"))
        legend_x = w - 5.95 * cm
        c.setStrokeColor(colors.HexColor("#6F8FB1"))
        c.setLineWidth(1.45)
        c.line(legend_x, h - 0.45 * cm, legend_x + 0.34 * cm, h - 0.45 * cm)
        c.setFillColor(colors.HexColor("#6F8FB1"))
        c.circle(legend_x + 0.17 * cm, h - 0.45 * cm, 0.045 * cm, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#475569"))
        c.setFont(PDF_FONT_REGULAR, 5.3)
        c.drawString(legend_x + 0.44 * cm, h - 0.52 * cm, "Loss Ratio")

        c.setFillColor(colors.HexColor("#003366"))
        c.roundRect(legend_x + 1.75 * cm, h - 0.54 * cm, 0.16 * cm, 0.18 * cm, 1.2, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#475569"))
        c.drawString(legend_x + 2.00 * cm, h - 0.52 * cm, "CoR")

        c.setStrokeColor(colors.HexColor("#C7893D"))
        c.setLineWidth(1.25)
        c.line(legend_x + 2.62 * cm, h - 0.45 * cm, legend_x + 2.94 * cm, h - 0.45 * cm)
        c.setFillColor(colors.HexColor("#475569"))
        c.drawString(legend_x + 3.05 * cm, h - 0.52 * cm, f"Projected CoR {_pdf_pct_label(cor_proj_for_legend)}")
        c.setFillColor(colors.HexColor("#8A5418"))
        c.setFont(PDF_FONT_BOLD, 5.2)
        c.drawString(legend_x + 3.05 * cm, h - 0.78 * cm, f"Projected LR {_pdf_pct_label(lr_proj_for_legend)}")

        x0, y0 = 0.68 * cm, 0.98 * cm
        footer_h = 0.26 * cm if hidden_metrics else 0.0
        plot_w, plot_h = w - 1.10 * cm, h - 2.16 * cm - footer_h

        ratio_values = (
            [_finite_float(v) for v in yearly["Loss Ratio %"].tolist()]
            + [_finite_float(v) for v in yearly["CoR %"].tolist()]
        )
        proj_values = [
            _finite_float(projection.get("Loss Ratio %")),
            _finite_float(projection.get("CoR %")),
        ]
        max_value = max([v for v in ratio_values + proj_values if np.isfinite(v)] or [100.0])
        max_value = max(100.0, max_value * 1.18)

        n = max(1, len(yearly))
        slot_w = plot_w / n

        bar_w = min(0.62 * cm, slot_w * 0.42)

        c.setStrokeColor(colors.HexColor("#CBD5E1"))
        c.setLineWidth(0.45)
        c.line(x0, y0, x0 + plot_w, y0)


        ref_y = self._map_y(100.0, y0, plot_h, max_value)
        c.setStrokeColor(colors.HexColor("#E2E8F0"))
        c.setLineWidth(0.35)
        c.line(x0, ref_y, x0 + plot_w, ref_y)
        c.setFillColor(colors.HexColor("#94A3B8"))
        c.setFont(PDF_FONT_REGULAR, 5.4)
        c.drawRightString(x0 + plot_w, ref_y + 0.04 * cm, "100%")

        loss_points = []
        for i, (_, row) in enumerate(yearly.iterrows()):
            year = int(row["UW_YEAR"])
            center_x = x0 + slot_w * (i + 0.5)


            cor_value = _finite_float(row["CoR %"])
            bar_x = center_x - bar_w / 2
            cor_y = self._map_y(cor_value, y0, plot_h, max_value)
            cor_h = max(0.04 * cm, cor_y - y0) if np.isfinite(cor_value) else 0
            c.setFillColor(colors.HexColor("#E39A5B") if year == latest_year else colors.HexColor("#003366"))
            c.roundRect(bar_x, y0, bar_w, cor_h, 2.2, stroke=0, fill=1)
            if np.isfinite(cor_value):
                c.setFillColor(colors.HexColor("#1F2937"))
                c.setFont(PDF_FONT_REGULAR, 5.3)
                c.drawCentredString(
                    center_x,
                    min(h - 0.98 * cm, y0 + cor_h + 0.12 * cm),
                    _pdf_pct_label(cor_value),
                )


            lr_value = _finite_float(row["Loss Ratio %"])
            if np.isfinite(lr_value):
                loss_points.append(
                    (center_x, self._map_y(lr_value, y0, plot_h, max_value), lr_value, year)
                )


            if year == latest_year:
                if "CoR" not in hidden_metrics:
                    cor_proj = _finite_float(projection.get("CoR %"))
                    if np.isfinite(cor_proj):
                        py = self._map_y(cor_proj, y0, plot_h, max_value)
                        c.setStrokeColor(colors.HexColor("#C7893D"))
                        c.setLineWidth(1.45)
                        c.line(bar_x - 0.12 * cm, py, bar_x + bar_w + 0.12 * cm, py)



            c.setFillColor(colors.HexColor("#475569"))
            c.setFont(PDF_FONT_REGULAR, 5.9 if n <= 6 else 5.2)
            c.drawCentredString(center_x, 0.43 * cm, str(year))


        if len(loss_points) >= 2:
            c.setStrokeColor(colors.HexColor("#6F8FB1"))
            c.setLineWidth(1.55)
            path = c.beginPath()
            path.moveTo(loss_points[0][0], loss_points[0][1])
            for px, py, _, _ in loss_points[1:]:
                path.lineTo(px, py)
            c.drawPath(path, stroke=1, fill=0)

        for px, py, value, _ in loss_points:

            c.setFillColor(colors.white)
            c.setStrokeColor(colors.HexColor("#4F7092"))
            c.setLineWidth(1.15)
            c.circle(px, py, 0.076 * cm, stroke=1, fill=1)




            label_text = _pdf_pct_label(value)
            label_font_size = 5.5
            label_w = pdfmetrics.stringWidth(label_text, PDF_FONT_BOLD, label_font_size)
            label_box_w = label_w + 0.20 * cm
            label_box_h = 0.30 * cm

            label_baseline_y = py + 0.16 * cm
            label_box_y = label_baseline_y - 0.08 * cm
            top_limit = h - 0.82 * cm
            if label_box_y + label_box_h > top_limit:
                label_box_y = py - label_box_h - 0.13 * cm
                label_baseline_y = label_box_y + 0.08 * cm

            c.setFillColor(colors.HexColor("#FFFFFF"))
            c.setStrokeColor(colors.HexColor("#B8C7D6"))
            c.setLineWidth(0.55)
            c.roundRect(
                px - label_box_w / 2,
                label_box_y,
                label_box_w,
                label_box_h,
                2.4,
                stroke=1,
                fill=1,
            )
            c.setFillColor(colors.HexColor("#173B5F"))
            c.setFont(PDF_FONT_BOLD, label_font_size)
            c.drawCentredString(px, label_baseline_y, label_text)

        if hidden_metrics:
            note = "No Projection Available: " + ", ".join(hidden_metrics)
            c.setFillColor(colors.HexColor("#7F1D1D"))
            c.setFont(PDF_FONT_BOLD, 6.0)
            c.drawString(0.68 * cm, 0.20 * cm, note)

        c.restoreState()

    def _draw_cob_doughnut(self):
        comp = self.trend_data or {}
        if not comp.get("available"):
            self._draw_empty(comp.get("message", "No data available."))
            return

        rows = list(comp.get("data", []) or [])
        if not rows:
            self._draw_empty("No GWP composition data available.")
            return

        c = self._draw_card_base()
        w, h = self.width, self.height
        unit_short = _display_unit_short(self.display_unit)


        cx, cy = 2.28 * cm, 3.02 * cm
        r = min(1.62 * cm, max(1.34 * cm, h * 0.25))
        inner_r = r * 0.55
        bbox = (cx - r, cy - r, cx + r, cy + r)
        palette = ["#003366", "#2E5E8E", "#6F8FB1", "#E39A5B", "#C7893D", "#B8C7D6", "#D7E0EA"]

        start_angle = 90.0
        label_positions = []
        for i, row in enumerate(rows):
            share = max(0.0, _finite_float(row.get("share")))
            if not np.isfinite(share) or share <= 0:
                continue
            extent = share / 100.0 * 360.0
            color_hex = palette[i % len(palette)]
            c.setFillColor(colors.HexColor(color_hex))
            c.setStrokeColor(colors.white)
            c.setLineWidth(0.9)
            c.wedge(*bbox, start_angle, extent, stroke=1, fill=1)
            label_positions.append((start_angle + extent / 2.0, share, color_hex))
            start_angle += extent



        import math
        pct_r = (r + inner_r) / 2.0
        for mid_angle, share, color_hex in label_positions:
            rad = math.radians(mid_angle)
            tx = cx + pct_r * math.cos(rad)
            ty = cy + pct_r * math.sin(rad)
            text_color = colors.white if color_hex not in ("#D8B070", "#94A3B8") else colors.HexColor("#334155")
            c.setFillColor(text_color)
            c.setFont(PDF_FONT_BOLD, 5.8)
            c.drawCentredString(tx, ty - 0.06 * cm, _pdf_pct_label(share))

        c.setFillColor(colors.white)
        c.setStrokeColor(colors.white)
        c.circle(cx, cy, inner_r, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#003366"))
        c.setFont(PDF_FONT_BOLD, 7.3)
        c.drawCentredString(cx, cy + 0.10 * cm, "GWP")
        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont(PDF_FONT_REGULAR, 5.4)
        c.drawCentredString(cx, cy - 0.17 * cm, unit_short)


        legend_x = 4.18 * cm
        legend_y = h - 1.18 * cm
        line_h = 0.46 * cm
        for i, row in enumerate(rows[:6]):
            y = legend_y - i * line_h
            label = str(row.get("label", "-"))
            if len(label) > 15:
                label = label[:12].rstrip() + "..."
            c.setFillColor(colors.HexColor(palette[i % len(palette)]))
            c.roundRect(legend_x, y - 0.03 * cm, 0.16 * cm, 0.16 * cm, 1.2, stroke=0, fill=1)
            c.setFillColor(colors.HexColor("#334155"))
            c.setFont(PDF_FONT_REGULAR, 6.0)
            c.drawString(legend_x + 0.26 * cm, y - 0.02 * cm, label)

        c.restoreState()

    def draw(self):
        if self.chart_type == "gwp":
            self._draw_gwp()
        elif self.chart_type == "ratio_cor":
            self._draw_ratio_cor()
        elif self.chart_type == "cob_doughnut":
            self._draw_cob_doughnut()
        else:
            self._draw_empty("No chart available.")


def build_pdf_visual_gallery(source_df: pd.DataFrame, styles, display_unit="in IDR Mio", as_of_date=None):

    trend_data = _prepare_pdf_trend_projection_data(source_df, display_unit, as_of_date=as_of_date)
    cob_data = _prepare_pdf_cob_composition_data(source_df, display_unit, min_share=10.0)
    title_style = ParagraphStyle(
        "VisualGalleryTitle",
        parent=styles["Normal"],
        fontName=PDF_FONT_BOLD,
        fontSize=9.4,
        leading=11,
        textColor=colors.HexColor("#003366"),
        spaceAfter=5,
    )


    gwp_w = 9.22 * cm
    ratio_w = 9.22 * cm
    cob_w = 9.22 * cm
    card_h = 6.55 * cm
    gwp_chart = _PdfExecutiveChartCard(
        "GWP* Trend - Actual vs Projection",
        "gwp",
        trend_data,
        display_unit=display_unit,
        width=gwp_w,
        height=card_h,
    )
    ratio_chart = _PdfExecutiveChartCard(
        "Loss Ratio & CoR",
        "ratio_cor",
        trend_data,
        display_unit=display_unit,
        width=ratio_w,
        height=card_h,
    )
    composition_basis = cob_data.get("basis", "CoB") if isinstance(cob_data, dict) else "CoB"
    cob_chart = _PdfExecutiveChartCard(
        f"GWP Portfolio Composition by {composition_basis}",
        "cob_doughnut",
        cob_data,
        display_unit=display_unit,
        width=cob_w,
        height=card_h,
    )
    charts_table = Table(
        [[gwp_chart, ratio_chart, cob_chart]],
        colWidths=[gwp_w, ratio_w, cob_w],
        rowHeights=[card_h],
        hAlign="LEFT",
    )
    charts_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0.12 * cm),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    return [
        Paragraph("Portfolio Visualization Gallery", title_style),
        charts_table,
    ]

def _pdf_is_with_ovr_status(ovr_status: str) -> bool:

    text = str(ovr_status or "").strip().lower()
    if not text:
        return False
    if "exclude" in text or "tanpa" in text:
        return False
    return ("include" in text) or ("dengan" in text) or ("with" in text)


def build_pdf_portfolio_insight_box(kpis: dict, styles, ovr_status="Exclude OVR", avail_width=None):

    if avail_width is None:
        avail_width = landscape(A4)[0] - (1.6 * cm)

    cor_pct = _finite_float((kpis or {}).get("CoR"))
    with_ovr = _pdf_is_with_ovr_status(ovr_status)

    title_style = ParagraphStyle(
        "PortfolioInsightTitle",
        parent=styles["Normal"],
        fontName=PDF_FONT_BOLD,
        fontSize=9.4,
        leading=11,
        textColor=colors.HexColor("#003366"),
    )
    body_style = ParagraphStyle(
        "PortfolioInsightBody",
        parent=styles["Normal"],
        fontName=PDF_FONT_REGULAR,
        fontSize=8.4,
        leading=11.1,
        textColor=colors.HexColor("#263445"),
    )

    red = "#B91C1C"
    green = "#166534"

    if not np.isfinite(cor_pct):
        body = "Insight belum tersedia karena nilai CoR tidak dapat dihitung dari portfolio terpilih."
    else:
        diff_pct = int(round(abs(float(cor_pct) - 100.0)))
        if float(cor_pct) > 100.0:
            if with_ovr:
                body = (
                    "Portofolio ini secara bersih "
                    f"<font color='{red}'><b>mencatatkan kerugian sebesar {diff_pct}%</b></font>. "
                    "Diperlukan adjustment outgo dan/atau rate premi serta deductible."
                )
            else:
                body = (
                    "Portofolio ini "
                    f"<font color='{red}'><b>mencatatkan kerugian sebesar {diff_pct}% di luar OVR</b></font>. "
                    "Diperlukan adjustment outgo dan/atau rate premi serta deductible. "
                    "Sebaiknya konfirmasi OVR dan masukkan ke dalam perhitungan."
                )
        elif float(cor_pct) < 100.0:
            if with_ovr:
                body = (
                    "Portofolio ini secara bersih "
                    f"<font color='{green}'><b>mencatatkan laba sebesar {diff_pct}%</b></font>."
                )
            else:
                body = (
                    "Portofolio ini "
                    f"<font color='{green}'><b>mencatatkan laba sebesar {diff_pct}%</b></font>. "
                    "Namun, hasil ini adalah sebelum OVR, "
                    f"<font color='{red}'><b>ada kemungkinan sebenarnya kontrak ini merugi</b></font>. "
                    "Sebaiknya konfirmasi OVR dan masukkan ke dalam perhitungan."
                )
        else:
            if with_ovr:
                body = "Portofolio ini secara bersih berada pada posisi break-even berdasarkan CoR total."
            else:
                body = (
                    "Portofolio ini berada pada posisi break-even sebelum OVR. "
                    "Sebaiknya konfirmasi OVR dan masukkan ke dalam perhitungan."
                )

    non_fronting_pct, fronting_pct = _get_opex_assumptions_pct()
    opex_reason = _get_opex_adjust_reason()




    has_presence_flags = (
        "Has Fronting Business" in (kpis or {})
        or "Has Non-Fronting Business" in (kpis or {})
    )
    if has_presence_flags:
        has_fronting_business = bool((kpis or {}).get("Has Fronting Business", False))
        has_non_fronting_business = bool((kpis or {}).get("Has Non-Fronting Business", False))
    else:
        has_fronting_business = True
        has_non_fronting_business = True

    assumption_parts = []
    if has_non_fronting_business:
        assumption_parts.append(f"OPEX Non-Fronting {non_fronting_pct:g}%")
    if has_fronting_business:
        assumption_parts.append(f"OPEX Fronting {fronting_pct:g}%")

    displayed_assumption_adjusted = (
        (has_non_fronting_business and not np.isclose(non_fronting_pct, DEFAULT_OPEX_NON_FRONTING_PCT, rtol=0.0, atol=1e-9))
        or (has_fronting_business and not np.isclose(fronting_pct, DEFAULT_OPEX_FRONTING_PCT, rtol=0.0, atol=1e-9))
    )
    reason_suffix = ""
    if displayed_assumption_adjusted and opex_reason:
        reason_suffix = f" ({html.escape(opex_reason)})"

    if assumption_parts:
        assumption_text = f"<b>Assumption:</b> {' &nbsp;|&nbsp; '.join(assumption_parts)}{reason_suffix}"
        body = body + f"<br/><br/><font color='#64748B'>{assumption_text}</font>"

    box = Table(
        [[Paragraph("Portofolio Insight", title_style)], [Paragraph(body, body_style)]],
        colWidths=[avail_width],
        hAlign="LEFT",
    )
    box.setStyle(TableStyle([


        ("LEFTPADDING", (0, 0), (-1, -1), 0.05 * cm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0.05 * cm),
        ("TOPPADDING", (0, 0), (-1, 0), 0.05 * cm),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0.06 * cm),
        ("TOPPADDING", (0, 1), (-1, 1), 0.06 * cm),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 0.08 * cm),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return box




def _pdf_as_of_display(as_of_date) -> str:

    text = str(as_of_date or "").strip()
    if len(text) > 7 and text[6] == "_":
        return text[7:]
    return text or "-"


def _pdf_report_context_elements(
    filters: dict,
    as_of_date,
    display_unit: str,
    ovr_status: str,
    doc_id: str | None,
    username: str,
    ovr_detail_df=None,
    include_claim_breakdown: bool = False,
    styles=None,
    avail_width=None,
):





    if styles is None:
        styles = getSampleStyleSheet()

    active_filters_for_metadata = _active_filters_only(filters or {})
    context_lines = [
        f"<b>As of Date:</b> {html.escape(_pdf_as_of_display(as_of_date))}",
        f"<b>OVR Status:</b> {html.escape(str(ovr_status or '-'))}",
    ]

    context_lines.append("<b>Portfolio Report for:</b>")
    context_lines.append("UW Years: 2021 - 2026")
    if active_filters_for_metadata:
        for col, info in active_filters_for_metadata.items():
            vals = info.get("values", []) or []
            mode = str(info.get("mode", "") or "")
            vals = [str(v) for v in vals if str(v).strip()]
            if str(mode).lower() == "exclude all":
                context_lines.append(f"{html.escape(str(col))} ({html.escape(mode)}): all values excluded")
            elif vals:
                shown = ", ".join(html.escape(v) for v in vals[:10])
                if len(vals) > 10:
                    shown += f", +{len(vals) - 10} more"
                context_lines.append(f"{html.escape(str(col))} ({html.escape(mode)}): {shown}")
    else:
        context_lines.append("No active filter selected")

    note = html.escape(_display_unit_note(display_unit))
    context_lines.append(f"*{note}")

    meta_style = ParagraphStyle(
        "PDFSectionContextPlainText",
        parent=styles["Normal"],
        fontName=PDF_FONT_REGULAR,
        fontSize=7.35,
        leading=9.0,
        textColor=colors.HexColor("#334155"),
        spaceAfter=5,
    )
    return [Paragraph("<br/>".join(context_lines), meta_style), Spacer(1, 0.12 * cm)]

def export_pdf(df, name, filters, as_of_date, username, risk_detail_df=None, include_claim_breakdown=False, claim_df=None, ovr_status="Exclude OVR", ovr_detail_df=None, doc_id=None, visual_source_df=None, display_unit="in IDR Mio", simulation_plans=None):
    df = _drop_ovr_cols_if_zero(df)



    money_unit_label = _display_unit_label(display_unit)
    col_alias = {
        "UW_YEAR": "UW YEAR",
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
        "OVR_AMT": "OVR*",
        "OVR Ratio": "OVR RATIO",
        "CoR": "CoR"
    }

    buffer = io.BytesIO()




    money_cols = [
        "OUR TSI", "GWP_AMT", "GEP_AMT", "GROSS_CLAIM",
        "COMMISSIONS", "OVR_AMT", "RI_COST", "RI_RECOVERY"
    ]

    count_cols = [
        "NUMBER OF CLAIMS", "NUMBER OF RISKS"
    ]

    metric_cols = money_cols + count_cols + [
        "Loss Ratio", "COMM Ratio", "RI Cost Ratio",
        "RI Recovery Ratio", "OVR Ratio", "CoR"
    ]




    df_numeric = df.copy()
    df_formatted = df.copy()


    if isinstance(df_numeric.index, pd.MultiIndex):
        df_numeric = df_numeric.reset_index()
        df_formatted = df_formatted.reset_index()
    elif df_numeric.index.name is not None:
        df_numeric = df_numeric.reset_index()
        df_formatted = df_formatted.reset_index()



    if "ERC_AMT" in df_numeric.columns:
        df_numeric.drop(columns=["ERC_AMT"], inplace=True)
        df_formatted.drop(columns=["ERC_AMT"], inplace=True)



    group_cols = [c for c in df_numeric.columns if c not in metric_cols]

    final_cols = group_cols + [c for c in metric_cols if c in df_numeric.columns]

    df_numeric = df_numeric[final_cols].reset_index(drop=True)
    df_formatted = df_formatted[final_cols].reset_index(drop=True)

    df_formatted = df_formatted.replace([np.inf, -np.inf], np.nan)




    for col in df_formatted.columns:


        if "Ratio" in col or "CoR" in col:
            df_formatted[col] = df_formatted[col].apply(
                lambda x: f"{round(float(x)):.0f}%" if pd.notna(x) else ""
            )


        elif col in money_cols:
            df_formatted[col] = df_formatted[col].apply(
                lambda x: _format_money_value(x, display_unit)
                if pd.notna(x) else ""
            )


        elif col in count_cols:
            df_formatted[col] = df_formatted[col].apply(
                lambda x: f"{int(x):,}".replace(",", ".") if pd.notna(x) else ""
            )


        else:
            df_formatted[col] = df_formatted[col].astype(str)




    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        "HeaderWrap",
        parent=styles["Normal"],
        alignment=1,
        textColor=colors.white,
        fontName=PDF_FONT_BOLD,
        fontSize=7.6,
        leading=8.4,
        splitLongWords=False,
    )

    cell_style = ParagraphStyle(
        "CellText",
        parent=styles["Normal"],
        alignment=2,
        fontSize=8
    )

    wrapped_headers = [
    Paragraph(col_alias.get(col, col), header_style)
    for col in df_formatted.columns]

    data = [wrapped_headers]

    table_style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), PDF_FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), 7.6),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]





    for r in range(len(df_formatted)):
        row_cells = []
        


        row_color = colors.HexColor("#F2F2F2") if r % 2 == 1 else colors.white
        

        table_style_cmds.append(("BACKGROUND", (0, r + 1), (-1, r + 1), row_color))

        for c, col_name in enumerate(df_formatted.columns):
            val = df_formatted.iloc[r, c]
            raw_val = df_numeric.iloc[r, c]


            cell_bg = row_color

            if col_name == "CoR" and pd.notna(raw_val) and raw_val > 100:
                cell_bg = colors.HexColor("#FFD966")

            if col_name == "Loss Ratio" and pd.notna(raw_val) and raw_val > 50:
                cell_bg = colors.HexColor("#FFA07A")


            if cell_bg != row_color:
                table_style_cmds.append(("BACKGROUND", (c, r + 1), (c, r + 1), cell_bg))




            pdf_cell_font_size = 8.0
            pdf_cell_leading = 8.8

            style = ParagraphStyle(
                "Cell",
                parent=cell_style,
                alignment=0 if c < len(group_cols) else 2,
                fontSize=pdf_cell_font_size,
                leading=pdf_cell_leading,
                fontName=PDF_FONT_REGULAR,
                splitLongWords=False,
            )

            row_cells.append(Paragraph(str(val), style))

        data.append(row_cells)




    pdf = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=0.8 * cm,
        rightMargin=0.8 * cm,
        topMargin=0.8 * cm,
        bottomMargin=0.8 * cm
    )

    def _compute_pdf_col_widths(columns, group_cols, avail_w):

        columns = list(columns)
        group_cols = list(group_cols or [])
        widths = []
        for i, col in enumerate(columns):
            c = str(col)
            w = (
                1.0 * cm if c == "COB"
                else 1.35 * cm if c == "UW_YEAR"
                else 1.45 * cm if c == "NUMBER OF CLAIMS"
                else 1.45 * cm if c == "NUMBER OF RISKS"


                else 2.12 * cm if c == "OUR TSI"
                else 2.05 * cm if c == "GWP_AMT"
                else 2.05 * cm if c == "GEP_AMT"
                else 2.12 * cm if c == "GROSS_CLAIM"
                else 2.05 * cm if c == "COMMISSIONS"
                else 1.98 * cm if c == "OVR_AMT"
                else 1.98 * cm if c == "RI_RECOVERY"
                else 1.98 * cm if c == "RI_COST"
                else 1.5 * cm if c == "RI Cost Ratio"

                else 1.40 * cm if ("Ratio" in c or "CoR" in c)
                else 4.0 * cm if i < len(group_cols)
                else 2.1 * cm
            )
            widths.append(float(w))

        total = sum(widths)
        if total > 0 and total > avail_w:
            factor = avail_w / total
            widths = [w * factor for w in widths]
        return widths

    kpi_source = visual_source_df if isinstance(visual_source_df, pd.DataFrame) and not visual_source_df.empty else df
    kpis = compute_kpis(kpi_source)
    avail_w = landscape(A4)[0] - (0.8 * cm) - (0.8 * cm)
    col_widths = _compute_pdf_col_widths(df_formatted.columns, group_cols, avail_w)

    table = Table(
        data,
        repeatRows=1,
        colWidths=col_widths,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=11,
        leading=13,
        textColor=colors.grey,
        alignment=1,
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
        Paragraph("<b>MNC Insurance Portfolio Analysis Report</b>", styles["Title"])
    ]
    elements.append(
        Paragraph("This Report Was Downloaded from SuperApp Actuary on behalf of Actuary Department", subtitle_style)
    )
    elements.append(Spacer(1, 0.18 * cm))
    elements.extend(_pdf_report_context_elements(
        filters,
        as_of_date,
        display_unit,
        ovr_status,
        doc_id,
        username,
        ovr_detail_df,
        include_claim_breakdown,
        styles,
        avail_w,
    ))

    elements.append(Paragraph("<b>Key Performance:</b>", styles["Normal"]))
    elements.append(build_kpi_cards_pdf(kpis, styles, display_unit))
    elements.append(Spacer(1, 0.28 * cm))






    chart_source_df = visual_source_df if isinstance(visual_source_df, pd.DataFrame) and not visual_source_df.empty else df
    elements.extend(build_pdf_visual_gallery(chart_source_df, styles, display_unit, as_of_date=as_of_date))
    elements.append(Spacer(1, 0.36 * cm))
    elements.append(build_pdf_portfolio_insight_box(kpis, styles, ovr_status, avail_width=avail_w))
    elements.append(PageBreak())

    elements.append(Paragraph("Detailed Portfolio Performance", styles["Title"]))
    elements.extend(_pdf_report_context_elements(
        filters, as_of_date, display_unit, ovr_status, doc_id, username,
        ovr_detail_df, include_claim_breakdown, styles, avail_w
    ))
    elements.append(table)

    if str(ovr_status).strip().lower() == "include ovr" and ovr_detail_df is not None and not ovr_detail_df.empty:
        elements.append(PageBreak())
        elements.extend(build_ovr_detail_table_pdf(
            ovr_detail_df,
            styles,
            context_elements=_pdf_report_context_elements(
                filters, as_of_date, display_unit, ovr_status, doc_id, username,
                ovr_detail_df, include_claim_breakdown, styles, avail_w
            ),
        ))


    plans = _sim_plans_for_export() if simulation_plans is None else _sim_normalize_plans(simulation_plans)
    for index, plan in enumerate(plans, 1):
        elements.append(PageBreak())
        title = f"Run a Simulation — {plan.get('plan_name') or f'Plan {index}'}"
        elements.append(Paragraph(html.escape(title), styles["Title"]))
        elements.extend(_sim_pdf_context_elements(plan, username, styles))
        elements.append(_sim_pdf_two_columns(
            plan.get("actual", {}), plan["simulated"],
            plan.get("display_unit", display_unit), styles, avail_w
        ))
        elements.extend(_sim_pdf_bottom_elements(plan, styles))

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
                elements.extend(_pdf_report_context_elements(
                    filters, as_of_date, display_unit, ovr_status, doc_id, username,
                    ovr_detail_df, include_claim_breakdown, styles, avail_w
                ))
                elements.append(Paragraph("No matched claim data for the selected filters.", styles["Normal"]))
            else:
                summary_df = build_claim_breakdown_display_df(claim_detail_df, label_col, top_n=9)
                elements.extend(build_claim_summary_table_pdf(
                    summary_df,
                    title,
                    label_col,
                    styles,
                    context_elements=_pdf_report_context_elements(
                        filters, as_of_date, display_unit, ovr_status, doc_id, username,
                        ovr_detail_df, include_claim_breakdown, styles, avail_w
                    ),
                ))



    elements.append(PageBreak())

    large_loss_detail_df = get_filtered_large_loss_detail(risk_detail_df, claim_df)
    large_loss_df = build_large_loss_df(large_loss_detail_df, top_n=5)
    elements.extend(build_large_loss_table_pdf(
        large_loss_df,
        styles,
        display_unit,
        context_elements=_pdf_report_context_elements(
            filters, as_of_date, display_unit, ovr_status, doc_id, username,
            ovr_detail_df, include_claim_breakdown, styles, avail_w
        ),
    ))

    verification_code = compute_rp_pdf_verification_hash(
        doc_id or "",
        username,
        filters or {},
        ovr_status,
        ovr_detail_df,
        include_claim_breakdown,
    ) if doc_id else ""
    verify_url = _build_rp_verify_url(doc_id, verification_code) if doc_id else ""
    open_report_url = _build_rp_open_report_url(doc_id) if doc_id else ""

    pdf.build(
    elements,
    onFirstPage=lambda canvas, doc: draw_footer_with_verification(canvas, doc, username, doc_id, verification_code, verify_url, open_report_url),
    onLaterPages=lambda canvas, doc: draw_footer(canvas, doc, username, doc_id),)


    return buffer.getvalue()





def export_excel(df, name, filters=None, as_of_date=None, risk_detail_df=None, include_claim_breakdown=False, claim_df=None, ovr_status="Exclude OVR", ovr_detail_df=None, doc_id=None, excel_reinsurance_mode="simplified"):
    buffer = io.BytesIO()
    excel_reinsurance_mode = _normalize_excel_reinsurance_mode(excel_reinsurance_mode)
    df_to_export = df.copy()


    if isinstance(df_to_export.index, pd.MultiIndex):
        df_to_export = df_to_export.reset_index()
    else:
        df_to_export.index.name = df_to_export.index.name or "Index"
        df_to_export = df_to_export.reset_index()


    if "ERC_AMT" in df_to_export.columns:
        df_to_export.drop(columns=["ERC_AMT"], inplace=True)

    ordered_cols = [
    "OUR TSI", "NUMBER OF RISKS", "NUMBER OF CLAIMS",
    "GWP_AMT", "BASE_PREMIUM", "OUR_DISCOUNT", "GEP_AMT", "GROSS_CLAIM",
    "COMMISSIONS", "RI_COST",
    "PREM TREATY", "PREM FAC", "COMM RI", "COMM FAC",
    "RI_RECOVERY",
    "Loss Ratio", "COMM Ratio", "RI Cost Ratio",
    "RI Recovery Ratio", "OVR Ratio", "CoR", "OVR_AMT"
    ]


    id_cols = [c for c in df_to_export.columns if c not in ordered_cols]


    metric_cols = [c for c in ordered_cols if c in df_to_export.columns]


    df_to_export = df_to_export[id_cols + metric_cols]


    for col in df_to_export.columns:
        if "Ratio" in col or "CoR" in col:
            df_to_export[col] = df_to_export[col].apply(lambda x: float(x)/100 if pd.notna(x) else None)

    def _write_filter_block(worksheet, start_row: int = 0):





        row_offset = int(start_row or 0)
        if as_of_date:
            worksheet.write(row_offset, 0, f"As of Date: {as_of_date}")
            row_offset += 1

        active_filters_for_metadata = _active_filters_only(filters)
        if active_filters_for_metadata:
            worksheet.write(row_offset, 0, "Portfolio Report for:")
            row_offset += 1
            for col, info in active_filters_for_metadata.items():
                vals = info.get("values", [])
                mode = info.get("mode", "")
                text = (
                    f"{col} ({mode}): {len(vals)} selected"
                    if len(vals) > 10
                    else f"{col} ({mode}): {', '.join(map(str, vals))}"
                )
                worksheet.write(row_offset, 0, text)
                row_offset += 1

        if doc_id:
            worksheet.write(row_offset, 0, f"Document ID: {_sanitize_doc_id(doc_id)}")
            row_offset += 1

        worksheet.write(row_offset, 0, f"OVR Status: {ovr_status}")
        row_offset += 1
        worksheet.write(
            row_offset,
            0,
            f"Reinsurance Items: {_excel_reinsurance_mode_label(excel_reinsurance_mode)}",
        )
        row_offset += 1
        return row_offset

    def _count_filter_block_rows() -> int:
        rows = 0
        if as_of_date:
            rows += 1
        active_filters_for_metadata = _active_filters_only(filters)
        if active_filters_for_metadata:
            rows += 1 + len(active_filters_for_metadata)
        if doc_id:
            rows += 1
        rows += 1
        rows += 1
        return rows

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:


        startrow = _count_filter_block_rows() + 1
        main_sheet_name = "CoR Summary"
        df_to_export.to_excel(writer, index=False, startrow=startrow, sheet_name=main_sheet_name)
        workbook = writer.book
        worksheet = writer.sheets[main_sheet_name]

        money_fmt = workbook.add_format({'num_format': '#,##0'})
        pct_fmt = workbook.add_format({'num_format': '0%'})
        text_fmt = workbook.add_format({})
        header_fmt = workbook.add_format({
            'bold': True,
            'bg_color': '#003366',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#D7E0EA',
        })
        note_fmt = workbook.add_format({'italic': True, 'font_color': '#555555'})

        money_columns = {
            "OUR TSI", "GWP_AMT", "BASE_PREMIUM", "OUR_DISCOUNT",
            "GEP_AMT", "GROSS_CLAIM", "COMMISSIONS", "RI_COST",
            "PREM TREATY", "PREM FAC", "COMM RI", "COMM FAC",
            "RI_RECOVERY", "OVR_AMT",
        }
        hidden_excel_columns = set(EXCEL_ALWAYS_HIDDEN_METRICS)

        for i, col in enumerate(df_to_export.columns):
            options = {'hidden': True} if col in hidden_excel_columns else None
            if col in money_columns:
                worksheet.set_column(i, i, 15, money_fmt, options)
            elif "Ratio" in col or "CoR" in col:
                worksheet.set_column(i, i, 12, pct_fmt, options)
            else:
                worksheet.set_column(i, i, 20, text_fmt, options)

        _write_filter_block(worksheet)
        worksheet.hide_gridlines(2)
        if len(df_to_export.columns) > 0:
            last_col = len(df_to_export.columns) - 1
            if len(df_to_export) > 0:
                worksheet.add_table(
                    startrow,
                    0,
                    startrow + len(df_to_export),
                    last_col,
                    {
                        'name': 'CoRSummaryTable',
                        'style': 'Table Style Medium 2',
                        'columns': [{'header': str(col)} for col in df_to_export.columns],
                    },
                )
            else:
                worksheet.autofilter(startrow, 0, startrow, last_col)
            for col_idx, col_name in enumerate(df_to_export.columns):
                worksheet.write(startrow, col_idx, str(col_name), header_fmt)
            worksheet.set_row(startrow, 28)
            worksheet.freeze_panes(startrow + 1, 0)

        if str(ovr_status).strip().lower() == "include ovr" and ovr_detail_df is not None and not ovr_detail_df.empty:
            ovr_export_df = _format_ovr_detail_for_export(ovr_detail_df)
            if not ovr_export_df.empty:
                ovr_sheet_name = "OVR Detail"
                ws_ovr = workbook.add_worksheet(ovr_sheet_name)
                writer.sheets[ovr_sheet_name] = ws_ovr
                ws_ovr.write(0, 0, "OVR Detail")
                ws_ovr.write(1, 0, f"OVR Status: {ovr_status}")
                ws_ovr.write(2, 0, "This sheet shows the OVR input confirmed by the user before export.")

                ovr_excel_df = ovr_export_df.copy()
                ovr_excel_df.rename(columns={
                    "OVR_MODE": "OVR MODE",
                    "OVR_PCT_INPUT": "OVR (%)",
                }, inplace=True)
                ovr_excel_df.to_excel(writer, index=False, startrow=4, sheet_name=ovr_sheet_name)

                for col_idx, col_name in enumerate(ovr_excel_df.columns):
                    ws_ovr.write(4, col_idx, col_name, header_fmt)
                    if col_name == "OVR (%)":
                        ws_ovr.set_column(col_idx, col_idx, 14)
                    else:
                        ws_ovr.set_column(col_idx, col_idx, 24)
                if len(ovr_excel_df.columns) > 0:
                    ws_ovr.autofilter(4, 0, 4 + len(ovr_excel_df), len(ovr_excel_df.columns) - 1)
                    ws_ovr.freeze_panes(5, 0)

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
                filter_end_row = _write_filter_block(ws, start_row=1)
                claim_startrow = filter_end_row + 2

                if summary_df is None or summary_df.empty:
                    ws.write(claim_startrow, 0, "No matched claim data for the selected filters.")
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

                excel_df.to_excel(writer, index=False, startrow=claim_startrow, sheet_name=sheet_name)
                ws.hide_gridlines(2)
                for col_idx, col_name in enumerate(excel_df.columns):
                    if col_idx == 0:
                        ws.set_column(col_idx, col_idx, 34, text_fmt)
                    else:
                        ws.set_column(col_idx, col_idx, 18, pct_fmt)
                if len(excel_df.columns) > 0:
                    last_claim_col = len(excel_df.columns) - 1
                    if len(excel_df) > 0:
                        table_name = "ClaimTable_" + hashlib.sha1(sheet_name.encode("utf-8")).hexdigest()[:10]
                        ws.add_table(
                            claim_startrow,
                            0,
                            claim_startrow + len(excel_df),
                            last_claim_col,
                            {
                                'name': table_name,
                                'style': 'Table Style Medium 2',
                                'columns': [{'header': str(col)} for col in excel_df.columns],
                            },
                        )
                    else:
                        ws.autofilter(claim_startrow, 0, claim_startrow, last_claim_col)
                    for col_idx, col_name in enumerate(excel_df.columns):
                        ws.write(claim_startrow, col_idx, str(col_name), header_fmt)
                    ws.set_row(claim_startrow, 28)
                    ws.freeze_panes(claim_startrow + 1, 0)

        large_loss = build_large_loss_df(get_filtered_large_loss_detail(risk_detail_df, claim_df), top_n=5)
        sheet_name = "List of Large Loss"
        ws_loss = workbook.add_worksheet(sheet_name)
        writer.sheets[sheet_name] = ws_loss
        ws_loss.write(0, 0, "List of Large Loss - Top 5 by Gross Claim")
        ws_loss.write(1, 0, "Amounts in original IDR. Claim No is taken from the claim dataset.")
        loss_start = _write_filter_block(ws_loss, start_row=3) + 2
        large_loss.to_excel(writer, sheet_name=sheet_name, index=False, startrow=loss_start)
        for idx, col in enumerate(LARGE_LOSS_DISPLAY_COLUMNS):
            ws_loss.write(loss_start, idx, col, header_fmt)
            ws_loss.set_column(idx, idx, 22 if idx < 6 else 20, text_fmt if idx < 6 else money_fmt)
        ws_loss.freeze_panes(loss_start + 1, 0)
        ws_loss.hide_gridlines(2)
        if not large_loss.empty:
            ws_loss.autofilter(loss_start, 0, loss_start + len(large_loss), len(LARGE_LOSS_DISPLAY_COLUMNS) - 1)
        else:
            ws_loss.write(loss_start + 1, 0, "No matched claims for the selected policies.")

    return buffer.getvalue()

def _clear_export_state(prefix: str):
    for suffix in ("sig", "bytes", "href", "name", "error", "doc_id"):
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






EXCEL_EXPORT_CHUNK_SIZE = 50_000


def _build_excel_range_options(total_rows: int, chunk_size: int = EXCEL_EXPORT_CHUNK_SIZE) -> list[str]:

    total_rows = max(0, int(total_rows or 0))
    chunk_size = max(1, int(chunk_size or EXCEL_EXPORT_CHUNK_SIZE))

    if total_rows == 0:
        return ["Rows 0 - 0"]

    labels = []
    for start in range(0, total_rows, chunk_size):
        end = min(start + chunk_size, total_rows)
        labels.append(f"Rows {start + 1:,} - {end:,}")
    return labels


def _excel_range_from_label(label: str) -> tuple[int, int]:

    try:
        cleaned = str(label).replace("Rows", "").replace(",", "").strip()
        left, right = [x.strip() for x in cleaned.split("-", 1)]
        start = max(0, int(left) - 1)
        end = max(start, int(right))
        return start, end
    except Exception:
        return 0, EXCEL_EXPORT_CHUNK_SIZE


def _excel_range_suffix(start_idx: int, end_idx: int, total_rows: int) -> str:

    if int(total_rows or 0) <= EXCEL_EXPORT_CHUNK_SIZE:
        return ""
    return f"_rows_{start_idx + 1:06d}_{end_idx:06d}"


@_export_fragment_if_available
def render_export_controls_fragment(
    safe_tab_name,
    tab_name,
    group_cols,
    total_pivot_rows,
    df_ovr,
    active_filters,
    tanggal_pilihan,
    username,
    risk_detail_for_claim,
    include_claim_breakdown,
    ovr_status_for_export,
    ovr_detail_for_export,
    display_unit,
    pdf_signature,
    xlsx_signature,
):

    pdf_prefix = f"export_pdf__{safe_tab_name}"
    xlsx_prefix = f"export_xlsx__{safe_tab_name}"

    include_key = f"include_claim_summary__{safe_tab_name}"
    if include_key not in st.session_state:
        st.session_state[include_key] = bool(include_claim_breakdown)

    include_claim_breakdown = st.checkbox(
        "Include claim breakdown",
        key=include_key,
    )

    total_pivot_rows = max(0, int(total_pivot_rows or 0))
    excel_range_labels = _build_excel_range_options(total_pivot_rows)
    excel_range_key = f"excel_export_range__{safe_tab_name}"

    if excel_range_key not in st.session_state or st.session_state.get(excel_range_key) not in excel_range_labels:
        st.session_state[excel_range_key] = excel_range_labels[0]

    if total_pivot_rows > EXCEL_EXPORT_CHUNK_SIZE:
        st.selectbox(
            "Excel export rows",
            options=excel_range_labels,
            key=excel_range_key,
            help=f"Maximum {EXCEL_EXPORT_CHUNK_SIZE:,} rows per XLSX download to keep the app stable.",
        )
        selected_excel_range_label = st.session_state.get(excel_range_key, excel_range_labels[0])
        excel_start_idx, excel_end_idx = _excel_range_from_label(selected_excel_range_label)
        excel_start_idx = max(0, min(excel_start_idx, total_pivot_rows))
        excel_end_idx = max(excel_start_idx, min(excel_end_idx, total_pivot_rows))
    else:
        selected_excel_range_label = excel_range_labels[0]
        excel_start_idx, excel_end_idx = 0, total_pivot_rows

    excel_mode_key = f"excel_reinsurance_mode__{safe_tab_name}"
    if excel_mode_key not in st.session_state:
        st.session_state[excel_mode_key] = "simplified"
    excel_reinsurance_mode = _normalize_excel_reinsurance_mode(
        st.session_state.get(excel_mode_key, "simplified")
    )



    pdf_signature = _compute_export_signature({
        "tab_name": tab_name,
        "group_cols": list(group_cols),
        "filters": active_filters,
        "as_of": tanggal_pilihan,
        "include_claim_breakdown": bool(include_claim_breakdown),
        "ovr_applied": bool(st.session_state.get("ovr_applied", False)),
        "ovr_confirmed": bool(st.session_state.get("ovr_confirmed", False)),
        "ovr_status": ovr_status_for_export,
        "ovr_sig": st.session_state.get("ovr_last_sig"),
        "opex_assumptions_pct": _get_opex_assumptions_pct(),
        "opex_adjust_reason": _get_opex_adjust_reason(),
        "display_unit": _normalize_display_unit(display_unit),
        "simulation_plans": _json_safe_value(_sim_plans_for_export()),
        "pdf_header_unit_patch": "2026-05-15-clean-header-v2",
        "pdf_visual_gallery_patch": "2026-07-05-page1-3charts-ratio-wide-doughnut-compact-v7",
        "gwp_projection_patch": "2026-09-10-monthly-historical-50-50-actual-floor-v1",
        "simulation_section_patch": "2026-09-11-multi-plan-bottom-outcome-v3",
    })
    xlsx_signature = _compute_export_signature({
        "tab_name": tab_name,
        "group_cols": list(group_cols),
        "filters": active_filters,
        "as_of": tanggal_pilihan,
        "include_claim_breakdown_excel": bool(include_claim_breakdown),
        "ovr_applied": bool(st.session_state.get("ovr_applied", False)),
        "ovr_confirmed": bool(st.session_state.get("ovr_confirmed", False)),
        "ovr_status": ovr_status_for_export,
        "ovr_sig": st.session_state.get("ovr_last_sig"),
        "opex_assumptions_pct": _get_opex_assumptions_pct(),
        "opex_adjust_reason": _get_opex_adjust_reason(),
        "excel_start_idx": int(excel_start_idx),
        "excel_end_idx": int(excel_end_idx),
        "excel_chunk_size": int(EXCEL_EXPORT_CHUNK_SIZE),
        "excel_reinsurance_mode": excel_reinsurance_mode,
        "excel_only_metrics_patch": "2026-07-23-base-discount-hidden-ri-clean-menu-v3",
    })

    if st.session_state.get(f"{pdf_prefix}__sig") != pdf_signature:
        _clear_export_state(pdf_prefix)
    if st.session_state.get(f"{xlsx_prefix}__sig") != xlsx_signature:
        _clear_export_state(xlsx_prefix)

    _inject_prepare_excel_menu_css()
    prep_col1, prep_col2 = st.columns(2, gap="small")

    with prep_col1:
        if st.button("Prepare PDF", key=f"prepare_pdf__{safe_tab_name}", width="content"):
            try:
                with st.spinner("Preparing PDF..."):
                    doc_id = generate_unique_document_id("RP")
                    pdf_file_name = f"{safe_tab_name}_{doc_id}.pdf"
                    pivot_for_pdf = cached_pivot(df_ovr, tuple(group_cols), row_limit=500)
                    pdf_bytes = cached_export_pdf_bytes(
                        pivot_for_pdf,
                        tab_name,
                        active_filters,
                        tanggal_pilihan,
                        username,
                        risk_detail_for_claim,
                        df_ovr,
                        include_claim_breakdown,
                        ovr_status_for_export,
                        ovr_detail_for_export,
                        doc_id,
                        display_unit,
                        _sim_plans_for_export(),
                    )
                    save_document_filter_log(
                        doc_id=doc_id,
                        username=username,
                        export_type="PDF",
                        active_detail_tab=st.session_state.get("risk_profile_active_detail_tab", ""),
                        detail_extra_columns=st.session_state.get("detailed_table_extra_columns", []),
                        group_cols=group_cols,
                        filters=active_filters,
                        ovr_status=ovr_status_for_export,
                        ovr_detail_df=ovr_detail_for_export,
                        include_claim_breakdown=include_claim_breakdown,
                        total_rows=total_pivot_rows,
                        file_name=pdf_file_name,
                    )
                st.session_state[f"{pdf_prefix}__bytes"] = pdf_bytes
                st.session_state[f"{pdf_prefix}__href"] = _make_data_uri(pdf_bytes, "application/pdf")
                st.session_state[f"{pdf_prefix}__name"] = pdf_file_name
                st.session_state[f"{pdf_prefix}__doc_id"] = doc_id
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
        else:
            pass

    with prep_col2:
        prepare_excel_clicked = False
        selected_excel_action = None



        if hasattr(st, "menu_button"):
            selected_excel_action = st.menu_button(
                "Prepare Excel",
                options=["breakdown", "simplified"],
                key=f"prepare_xlsx_menu__{safe_tab_name}",
                format_func=_excel_reinsurance_mode_label,
                type="secondary",
                width="content",
            )
            if selected_excel_action is not None:
                excel_reinsurance_mode = _normalize_excel_reinsurance_mode(selected_excel_action)
                st.session_state[excel_mode_key] = excel_reinsurance_mode
                prepare_excel_clicked = True

        elif hasattr(st, "popover"):


            with st.popover("Prepare Excel", use_container_width=False):
                breakdown_clicked = st.button(
                    "Including Reinsurance Breakdown",
                    key=f"prepare_xlsx_breakdown__{safe_tab_name}",
                    width="stretch",
                    type="secondary",
                    on_click=_set_excel_reinsurance_mode,
                    args=(excel_mode_key, "breakdown"),
                )
                simplified_clicked = st.button(
                    "Simplify Reinsurance Items",
                    key=f"prepare_xlsx_simplified__{safe_tab_name}",
                    width="stretch",
                    type="secondary",
                    on_click=_set_excel_reinsurance_mode,
                    args=(excel_mode_key, "simplified"),
                )
                prepare_excel_clicked = bool(breakdown_clicked or simplified_clicked)
        else:

            excel_reinsurance_mode = st.selectbox(
                "Excel reinsurance view",
                options=["simplified", "breakdown"],
                key=excel_mode_key,
                format_func=_excel_reinsurance_mode_label,
            )
            prepare_excel_clicked = st.button(
                "Prepare Excel",
                key=f"prepare_xlsx__{safe_tab_name}",
                width="content",
            )

        if prepare_excel_clicked:
            excel_reinsurance_mode = _normalize_excel_reinsurance_mode(
                selected_excel_action
                if selected_excel_action is not None
                else st.session_state.get(excel_mode_key, "simplified")
            )




            xlsx_signature = _compute_export_signature({
                "tab_name": tab_name,
                "group_cols": list(group_cols),
                "filters": active_filters,
                "as_of": tanggal_pilihan,
                "include_claim_breakdown_excel": bool(include_claim_breakdown),
                "ovr_applied": bool(st.session_state.get("ovr_applied", False)),
                "ovr_confirmed": bool(st.session_state.get("ovr_confirmed", False)),
                "ovr_status": ovr_status_for_export,
                "ovr_sig": st.session_state.get("ovr_last_sig"),
                "excel_start_idx": int(excel_start_idx),
                "excel_end_idx": int(excel_end_idx),
                "excel_chunk_size": int(EXCEL_EXPORT_CHUNK_SIZE),
                "excel_reinsurance_mode": excel_reinsurance_mode,
                "excel_only_metrics_patch": "2026-07-23-base-discount-hidden-ri-clean-menu-v3",
            })
            if st.session_state.get(f"{xlsx_prefix}__sig") != xlsx_signature:
                _clear_export_state(xlsx_prefix)
            try:
                with st.spinner("Preparing Excel..."):


                    excel_extra_metrics = list(EXCEL_ALWAYS_HIDDEN_METRICS)
                    if excel_reinsurance_mode == "breakdown":
                        excel_extra_metrics.extend(EXCEL_REINSURANCE_BREAKDOWN_METRICS)

                    doc_id = generate_unique_document_id("RP")
                    full_pivot_for_excel = cached_pivot(
                        df_ovr,
                        tuple(group_cols),
                        row_limit=None,
                        extra_value_cols=tuple(excel_extra_metrics),
                    )
                    excel_chunk_df = full_pivot_for_excel.iloc[excel_start_idx:excel_end_idx].copy()
                    xlsx_bytes = cached_export_excel_bytes(
                        excel_chunk_df,
                        tab_name,
                        active_filters,
                        tanggal_pilihan,
                        risk_detail_for_claim,
                        include_claim_breakdown,
                        ovr_status_for_export,
                        ovr_detail_for_export,
                        excel_reinsurance_mode=excel_reinsurance_mode,
                        doc_id=doc_id,
                    )
                    row_suffix = _excel_range_suffix(excel_start_idx, excel_end_idx, total_pivot_rows)
                    mode_suffix = "_RI_Breakdown" if excel_reinsurance_mode == "breakdown" else "_RI_Simplified"
                    xlsx_file_name = f"{safe_tab_name}_{doc_id}{mode_suffix}{row_suffix}.xlsx"
                    save_document_filter_log(
                        doc_id=doc_id,
                        username=username,
                        export_type=f"Excel - {_excel_reinsurance_mode_label(excel_reinsurance_mode)}",
                        active_detail_tab=st.session_state.get("risk_profile_active_detail_tab", ""),
                        detail_extra_columns=st.session_state.get("detailed_table_extra_columns", []),
                        group_cols=group_cols,
                        filters=active_filters,
                        ovr_status=ovr_status_for_export,
                        ovr_detail_df=ovr_detail_for_export,
                        include_claim_breakdown=include_claim_breakdown,
                        excel_range_start=excel_start_idx,
                        excel_range_end=excel_end_idx,
                        total_rows=total_pivot_rows,
                        file_name=xlsx_file_name,
                    )
                st.session_state[f"{xlsx_prefix}__bytes"] = xlsx_bytes
                st.session_state[f"{xlsx_prefix}__href"] = _make_data_uri(
                    xlsx_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                st.session_state[f"{xlsx_prefix}__name"] = xlsx_file_name
                st.session_state[f"{xlsx_prefix}__doc_id"] = doc_id
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
        else:
            pass





def cached_export_pdf_bytes(pivot_df, tab_name, active_filters, tanggal_pilihan, username, risk_detail_df, visual_source_df, include_claim_breakdown_pdf, ovr_status, ovr_detail_df, doc_id=None, display_unit="in IDR Mio", sim_result=None):


    claim_df_pdf = load_claim_data(RISK_PROFILE_CLAIM_PATH)
    return export_pdf(
        pivot_df,
        tab_name,
        active_filters,
        tanggal_pilihan,
        username,
        risk_detail_df=risk_detail_df,
        include_claim_breakdown=include_claim_breakdown_pdf,
        claim_df=claim_df_pdf,
        ovr_status=ovr_status,
        ovr_detail_df=ovr_detail_df,
        doc_id=doc_id,
        visual_source_df=visual_source_df,
        display_unit=display_unit,
        simulation_plans=_sim_normalize_plans(sim_result),
    )


def cached_export_excel_bytes(pivot_df, tab_name, active_filters, tanggal_pilihan, risk_detail_df, include_claim_breakdown_excel, ovr_status, ovr_detail_df, excel_reinsurance_mode="simplified", doc_id=None):

    claim_df_excel = load_claim_data(RISK_PROFILE_CLAIM_PATH)
    return export_excel(
        pivot_df,
        tab_name,
        active_filters,
        tanggal_pilihan,
        risk_detail_df=risk_detail_df,
        include_claim_breakdown=include_claim_breakdown_excel,
        claim_df=claim_df_excel,
        ovr_status=ovr_status,
        ovr_detail_df=ovr_detail_df,
        doc_id=doc_id,
        excel_reinsurance_mode=excel_reinsurance_mode,
    )










@_detailed_fragment_if_available
def render_detailed_data_fragment(
    df_ovr: pd.DataFrame,
    active_filters: dict,
    tanggal_pilihan: str,
    username: str,
    risk_detail_for_claim: pd.DataFrame,
    ovr_status_for_export: str,
    ovr_detail_for_export: pd.DataFrame,
    display_unit: str = "in IDR Mio",
):

    tab_configs = [
        ("UW Year", "Portfolio Analysis - Detailed by UW Year", "UW_YEAR"),
        ("CoB", "Portfolio Analysis - Detailed by CoB", "COB"),
        ("LoB", "Portfolio Analysis - Detailed by LoB", "LOB"),
        ("INTERMEDIARY NAME", "Portfolio Analysis - Detailed by Intermediary", "INTERMEDIARY_NAME"),
        ("INSURED NAME", "Portfolio Analysis - Detailed by Insured Name", "INSURED_NAME"),
        ("MKT NAME", "Portfolio Analysis - Detailed by Marketing Name", "MARKETING_NAME"),
        ("MKT GROUP", "Portfolio Analysis - Detailed by Marketing Group", "MARKETING_GROUP"),
        ("BRANCH", "Portfolio Analysis - Detailed by Branch", "BRANCH"),
        ("PCKG DESC", "Portfolio Analysis - Detailed by OUR TSI Range", "PCKG_DESC"),
        ("TSI", "Portfolio Analysis - Detailed by TSI Range", "TSI RANGE"),
        ("POLICY NO.", "Portfolio Analysis - Detailed by Policy Number", "POLICY_NO"),
        ("INTERMEDIARY BRANCH", "Portfolio Analysis - Detailed by Intermediary Branch", "INTERMEDIARY_BRANCH"),
    ]

    extra_dim_map = {label: col for label, _, col in tab_configs if col in df_ovr.columns}

    additional_dim_map = {
        "TOB": "TOB",
        "UW Month": "UW_MONTH",
        "Issue": "ISSUE",
        "Occupation": "OCCUPATION",
        "TSI Range": "TSI RANGE",
        "Have FAC": "HAVE FAC",
    }
    for label, col in additional_dim_map.items():

        candidate_cols = [col]
        if col == "HAVE FAC":
            candidate_cols = ["HAVE FAC", "HAVE_FAC", "HAVEFAC"]
        matched_col = next((c for c in candidate_cols if c in df_ovr.columns), None)
        if matched_col and label not in extra_dim_map:
            extra_dim_map[label] = matched_col

    render_section_card_header("Detailed Data", "Portfolio performance by selected grouping.")
    st.markdown("<div style='height:2px;'></div>", unsafe_allow_html=True)

    detail_key = "detailed_table_extra_columns"
    detail_options = list(extra_dim_map.keys())
    if detail_key not in st.session_state:
        st.session_state[detail_key] = []
    _sync_multiselect_state(detail_key, detail_options)

    def _reset_detailed_extra_columns():
        st.session_state[detail_key] = []

    st.markdown("""
    <style>
      /* Additional columns control: noticeable select box, no extra card. */
      div[class*="st-key-detailed_table_extra_columns"] label p{
        font-size: 12.5px !important;
        font-weight: 900 !important;
        color: #003366 !important;
        margin-bottom: 3px !important;
      }
      div[class*="st-key-detailed_table_extra_columns"] div[data-baseweb="select"]{
        min-height: 38px !important;
        border-radius: 12px !important;
        background: #FFFFFF !important;
        border: 1.5px solid rgba(0,51,102,0.28) !important;
        box-shadow: 0 8px 22px rgba(0,51,102,0.08), 0 0 0 4px rgba(0,51,102,0.035) !important;
      }
      div[class*="st-key-detailed_table_extra_columns"] div[data-baseweb="select"]:focus-within{
        border-color: rgba(0,51,102,0.55) !important;
        box-shadow: 0 10px 26px rgba(0,51,102,0.12), 0 0 0 4px rgba(0,51,102,0.08) !important;
      }
      .detail-reset-scope button[kind="secondary"],
      div[class*="st-key-reset_detailed_table_extra_columns"] button {
        width: 92px !important;
        min-width: 92px !important;
        height: 34px !important;
        min-height: 34px !important;
        padding: 0 12px !important;
        border: 1px solid rgba(0,51,102,0.16) !important;
        border-radius: 10px !important;
        background: #FFFFFF !important;
        color: #003366 !important;
        -webkit-text-fill-color: #003366 !important;
        font-size: 12px !important;
        font-weight: 800 !important;
        white-space: nowrap !important;
        line-height: 1 !important;
        box-shadow: none !important;
      }
      .detail-reset-scope button[kind="secondary"] p,
      div[class*="st-key-reset_detailed_table_extra_columns"] button p{
        white-space: nowrap !important;
        line-height: 1 !important;
        margin: 0 !important;
      }
      .detail-reset-scope button[kind="secondary"]:hover,
      div[class*="st-key-reset_detailed_table_extra_columns"] button:hover {
        border-color: rgba(0,51,102,0.34) !important;
        background: #EEF6FF !important;
        color: #003366 !important;
      }
    </style>
    """, unsafe_allow_html=True)

    selected_extra_labels = list(st.session_state.get(detail_key, []) or [])
    extra_group_cols = [extra_dim_map[label] for label in selected_extra_labels if label in extra_dim_map]

    def render_additional_columns_control():
        ctrl_cols = st.columns([7.2, 1.15], gap="small", vertical_alignment="bottom")
        with ctrl_cols[0]:
            st.multiselect(
                "Additional columns",
                options=detail_options,
                max_selections=8,
                key=detail_key,
                placeholder="Choose options",
            )
        with ctrl_cols[1]:
            st.markdown('<div class="detail-reset-scope">', unsafe_allow_html=True)
            st.button(
                "Reset",
                key="reset_detailed_table_extra_columns",
                width="content",
                on_click=_reset_detailed_extra_columns,
            )
            st.markdown('</div>', unsafe_allow_html=True)

    def build_group_cols(primary_col):
        cols = [primary_col]
        for col in extra_group_cols:
            if col != primary_col and col not in cols:
                cols.append(col)
        return cols









    tab_labels = [label for label, _, _ in tab_configs]
    active_detail_tab_key = "risk_profile_active_detail_tab"
    if active_detail_tab_key not in st.session_state or st.session_state[active_detail_tab_key] not in tab_labels:
        st.session_state[active_detail_tab_key] = tab_labels[0]



    st.markdown("""
    <style>
      div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Detailed view"]) {
        width: 100% !important;
        max-width: 100% !important;
        margin-top: -26px !important;
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
    </style>
    """, unsafe_allow_html=True)

    active_tab_label = st.radio(
        "Detailed view",
        options=tab_labels,
        key=active_detail_tab_key,
        horizontal=True,
        label_visibility="collapsed",
    )


    def pivot_tab(group_cols, tab_name):
        safe_tab_name = (
            tab_name.replace(" ", "_")
            .replace("/", "_")
            .replace("\\", "_")
            .replace(":", "_")
        )



        pivot = cached_pivot(df_ovr, tuple(group_cols), row_limit=None)
        if pivot is None or pivot.empty:
            st.info("No data on this filter")
            return


        total_rows = len(pivot)
        page_key = f"table_page__{safe_tab_name}"
        st.session_state.setdefault(page_key, 1)


        rows_per_page = 50
        total_pages = max(1, int(np.ceil(total_rows / rows_per_page)))

        if int(st.session_state.get(page_key, 1) or 1) > total_pages:
            st.session_state[page_key] = total_pages
        if int(st.session_state.get(page_key, 1) or 1) < 1:
            st.session_state[page_key] = 1

        current_page = int(st.session_state.get(page_key, 1) or 1)
        start_idx = (current_page - 1) * rows_per_page
        end_idx = min(start_idx + rows_per_page, total_rows)
        page_pivot = pivot.iloc[start_idx:end_idx].copy()

        render_additional_columns_control()
        format_and_display(page_pivot, table_key=f"{safe_tab_name}_p{current_page}_r{rows_per_page}", display_unit=display_unit)

        st.markdown("""
        <style>
          .pagination-exec-meta {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-height: 34px;
            padding: 0 14px;
            border-radius: 999px;
            background: linear-gradient(180deg, #F8FAFC 0%, #EEF6FF 100%);
            border: 1px solid rgba(0,51,102,0.14);
            color: #003366;
            font-size: 12px;
            font-weight: 850;
            letter-spacing: -0.01em;
            white-space: nowrap;
            box-shadow: 0 6px 16px rgba(15,23,42,0.045);
          }
          .pagination-exec-meta span {
            color: #64748B;
            font-weight: 760;
            margin-left: 8px;
          }
          .pagination-exec-pagechip {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            height: 34px;
            min-width: 58px;
            padding: 0 18px;
            border-radius: 999px;
            background: #FFFFFF;
            border: 1px solid rgba(0,51,102,0.16);
            color: #003366;
            font-size: 12px;
            font-weight: 900;
            box-shadow: 0 4px 12px rgba(15,23,42,0.035);
          }
          div[class*="st-key-pagination_nav__"] {
            margin-top: 8px !important;
            padding: 10px 12px !important;
            border-radius: 16px !important;
            background: #FFFFFF !important;
            border: 1px solid rgba(0,51,102,0.10) !important;
            box-shadow: 0 8px 22px rgba(15,23,42,0.035) !important;
          }
          div[class*="st-key-pagination_nav__"] [data-testid="stHorizontalBlock"]{
            align-items: center !important;
          }
          div[class*="st-key-pagination_nav__"] button[kind="secondary"] {
            min-height: 34px !important;
            height: 34px !important;
            min-width: 42px !important;
            padding: 0 14px !important;
            font-size: 17px !important;
            line-height: 1 !important;
            border-radius: 999px !important;
            border: 1px solid rgba(0,51,102,0.18) !important;
            color: #003366 !important;
            background: linear-gradient(180deg, #FFFFFF 0%, #F4F7FB 100%) !important;
            box-shadow: 0 4px 12px rgba(15,23,42,0.035) !important;
            margin-top: 0 !important;
            margin-bottom: 0 !important;
          }
          div[class*="st-key-pagination_nav__"] button[kind="secondary"]:hover {
            background: linear-gradient(135deg, #003366 0%, #1F5A91 100%) !important;
            color: #FFFFFF !important;
            border-color: rgba(0,51,102,0.45) !important;
          }
          div[class*="st-key-pagination_nav__"] div[data-testid="column"] {
            display: flex !important;
            align-items: center !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
          }
          div[class*="st-key-pagination_nav__"] div[data-testid="stMarkdownContainer"]{
            margin: 0 !important;
          }
        </style>
        """, unsafe_allow_html=True)
        pagination_nav_key = f"pagination_nav__{safe_tab_name}"

        def _go_prev():
            st.session_state[page_key] = max(1, int(st.session_state.get(page_key, 1) or 1) - 1)

        def _go_next():
            st.session_state[page_key] = min(total_pages, int(st.session_state.get(page_key, 1) or 1) + 1)

        with st.container(key=pagination_nav_key):
            pg_col1, pg_col2, pg_col3, pg_col4 = st.columns([0.34, 0.62, 0.34, 7.2], gap="small", vertical_alignment="center")
            with pg_col1:
                st.button("‹", key=f"prev_page__{safe_tab_name}", width="content", disabled=current_page <= 1, on_click=_go_prev)
            with pg_col2:
                st.markdown(f"<div class='pagination-exec-pagechip'>{current_page:,}</div>", unsafe_allow_html=True)
            with pg_col3:
                st.button("›", key=f"next_page__{safe_tab_name}", width="content", disabled=current_page >= total_pages, on_click=_go_next)
            with pg_col4:
                st.markdown(
                    f"<div class='pagination-exec-meta'>Page {current_page:,} / {total_pages:,}"
                    f"<span>Rows {start_idx + 1:,}–{end_idx:,} of {total_rows:,} · 50 per page</span></div>",
                    unsafe_allow_html=True,
                )

        include_claim_breakdown = bool(
            st.session_state.get(f"include_claim_summary__{safe_tab_name}", True)
        )
        pdf_signature = "computed_inside_export_fragment"
        xlsx_signature = "computed_inside_export_fragment"

        render_export_controls_fragment(
            safe_tab_name,
            tab_name,
            tuple(group_cols),
            total_rows,
            df_ovr,
            active_filters,
            tanggal_pilihan,
            username,
            risk_detail_for_claim,
            bool(include_claim_breakdown),
            ovr_status_for_export,
            ovr_detail_for_export,
            display_unit,
            pdf_signature,
            xlsx_signature,
        )

    active_config = next(
        (cfg for cfg in tab_configs if cfg[0] == active_tab_label),
        tab_configs[0],
    )
    tab_label, tab_title, primary_col = active_config
    st.markdown(
        f"<div style='font-size:14px;font-weight:800;color:#003366;margin:4px 0 6px 0;'>{html.escape(tab_title)}</div>",
        unsafe_allow_html=True,
    )
    group_cols = build_group_cols(primary_col)
    pivot_tab(group_cols, tab_title)
    st.markdown("</div>", unsafe_allow_html=True)






def _rerun_full_app_after_ovr() -> None:

    try:
        st.rerun(scope="app")
    except TypeError:
        st.rerun()


def _fragment_if_available(func):



    return func




def _build_ovr_combos_from_filtered_df(
    df: pd.DataFrame,
    dims,
    limit: int = 200,
) -> pd.DataFrame:






    dims = [d for d in list(dims or []) if d in df.columns]
    if not dims or "GWP_AMT" not in df.columns:
        return pd.DataFrame(columns=dims + ["OVR_PCT_INPUT"])

    tmp = df[dims + ["GWP_AMT"]].copy()
    for dim in dims:
        if isinstance(tmp[dim].dtype, pd.CategoricalDtype):
            tmp[dim] = tmp[dim].cat.remove_unused_categories()

    tmp["GWP_AMT"] = pd.to_numeric(tmp["GWP_AMT"], errors="coerce").fillna(0.0)
    combos = (
        tmp.groupby(
            dims,
            dropna=False,
            as_index=False,
            observed=True,
        )["GWP_AMT"]
        .sum()
        .sort_values("GWP_AMT", ascending=False)
        .head(max(1, int(limit or 200)))
        .drop(columns=["GWP_AMT"])
        .reset_index(drop=True)
    )
    combos["OVR_PCT_INPUT"] = np.nan
    return combos


def _ovr_scope_signature(df: pd.DataFrame, dims) -> str:

    dims = [d for d in list(dims or []) if d in df.columns]
    if not dims:
        return ""
    combos = _build_ovr_combos_from_filtered_df(df, dims)
    keys = combos[dims].astype("string").fillna("<NA>")
    payload = keys.to_json(orient="split")
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _ovr_rules_match_current_scope(rules_df, df: pd.DataFrame, dims) -> bool:

    dims = [d for d in list(dims or []) if d in df.columns]
    if not dims or not isinstance(rules_df, pd.DataFrame):
        return False
    if any(d not in rules_df.columns for d in dims):
        return False

    current = _build_ovr_combos_from_filtered_df(df, dims)

    def _rows(frame: pd.DataFrame):
        normalized = frame[dims].astype("string").fillna("<NA>").drop_duplicates()
        return sorted(tuple(row) for row in normalized.itertuples(index=False, name=None))

    return _rows(rules_df) == _rows(current)

def _render_ovr_popover_safe(df: pd.DataFrame) -> None:







    st.markdown(
        "<div class='ovr-advanced-title'>OVR Adjustment</div>"
        "<div class='ovr-advanced-sub'>Input OVR, then click Proses OVR. Switching between options here does not rerun until you submit.</div>",
        unsafe_allow_html=True,
    )

    active_config = _get_applied_ovr_configuration()
    if active_config is not None:
        label = (f"Uniform {active_config['uniform_pct']:g}%" if active_config.get("mode") == "uniform" else "Per kategori")
        st.caption(f"OVR aktif: {label}. Input baru berlaku setelah klik Proses OVR; perubahan OPEX tidak menghapus OVR aktif.")
        if st.button("Hapus OVR aktif", key="risk_profile_clear_applied_ovr"):
            st.session_state["risk_profile_applied_ovr"] = None
            st.session_state["ovr_applied"] = False
            st.session_state["ovr_confirmed"] = False
            _rerun_full_app_after_ovr()

    eligible_dims = [c for c in [
        "UW_YEAR", "UW_MONTH", "INTERMEDIARY_NAME", "INSURED_NAME", "COB", "TOB", "LOB", "TSI RANGE",
        "MARKETING_NAME", "MARKETING_GROUP", "BRANCH", "INTERMEDIARY_BRANCH", "PCKG_DESC"
    ] if c in df.columns]

    def _gen_ovr_combos(_dims):
        return _build_ovr_combos_from_filtered_df(df, _dims, limit=200)

    def _ovr_sig_from_state():
        mode = st.session_state.get("ovr_mode", "uniform")
        if mode == "uniform":
            return ("uniform", float(st.session_state.get("ovr_uniform_pct_input", 0.0)))
        dims = tuple(st.session_state.get("ovr_dims", []))
        rules_df = st.session_state.get("ovr_rules_df")
        if isinstance(rules_df, pd.DataFrame) and not rules_df.empty:
            preview_cols = [c for c in (list(dims) + ["OVR_PCT_INPUT"]) if c in rules_df.columns]
            preview_df = rules_df[preview_cols].copy() if preview_cols else rules_df.copy()
            preview_json = preview_df.astype("string").fillna("<NA>").to_json(orient="split")
            h = hashlib.sha1(preview_json.encode("utf-8")).hexdigest()
        else:
            h = "empty"
        return ("rules", dims, h)

    st.session_state.setdefault("ovr_mode", "uniform")
    st.session_state.setdefault("ovr_uniform_pct_input", 0.0)
    st.session_state.setdefault("ovr_dims", ["COB"] if "COB" in eligible_dims else (eligible_dims[:1] if eligible_dims else []))




    current_dims = [d for d in (st.session_state.get("ovr_dims", []) or []) if d in eligible_dims]
    current_dims_sig = "|".join(current_dims)
    current_scope_sig = _ovr_scope_signature(df, current_dims)
    current_rules = st.session_state.get("ovr_rules_df")
    stored_scope_sig = st.session_state.get("ovr_last_scope_sig", "")
    rules_match_scope = _ovr_rules_match_current_scope(current_rules, df, current_dims)

    needs_scope_refresh = bool(current_dims) and (
        not isinstance(current_rules, pd.DataFrame)
        or current_rules.empty
        or st.session_state.get("ovr_last_dims_sig") != current_dims_sig
        or (stored_scope_sig and stored_scope_sig != current_scope_sig)
        or (not stored_scope_sig and not rules_match_scope)
    )

    if needs_scope_refresh:
        st.session_state["ovr_rules_df"] = _gen_ovr_combos(current_dims)
        st.session_state["ovr_rules_editor_version"] = st.session_state.get("ovr_rules_editor_version", 0) + 1

        if st.session_state.get("ovr_mode", "uniform") == "rules":
            was_applied = bool(st.session_state.get("ovr_applied", False))
            st.session_state["ovr_applied"] = False
            st.session_state["ovr_confirmed"] = False
            st.session_state["ovr_last_dims_sig"] = current_dims_sig
            st.session_state["ovr_last_scope_sig"] = current_scope_sig
            if was_applied:

                _rerun_full_app_after_ovr()

    if current_dims:
        st.session_state["ovr_last_dims_sig"] = current_dims_sig
        st.session_state["ovr_last_scope_sig"] = current_scope_sig

    st.markdown("<b>1) Uniform OVR</b>", unsafe_allow_html=True)
    with st.form("ovr_uniform_popover_form", clear_on_submit=False):
        st.number_input(
            "OVR (%)",
            min_value=0.0,
            max_value=100.0,
            step=0.1,
            key="ovr_uniform_pct_input",
            help="Contoh: 2 = 2%",
        )
        st.checkbox("Konfirmasi OVR", key="ovr_confirm_checkbox_uniform")
        process_uniform = st.form_submit_button("Proses OVR Uniform", type="primary", width="stretch")

    if process_uniform:
        if not bool(st.session_state.get("ovr_confirm_checkbox_uniform", False)):
            st.warning("Centang Konfirmasi OVR terlebih dahulu.")
        else:
            st.session_state["ovr_mode"] = "uniform"
            st.session_state["ovr_keep_open"] = True
            st.session_state["ovr_user_touched"] = True
            st.session_state["ovr_confirmed"] = True
            st.session_state["ovr_applied"] = True
            st.session_state["ovr_last_sig"] = _ovr_sig_from_state()
            _commit_ovr_configuration()
            _rerun_full_app_after_ovr()

    st.markdown("<hr style='margin:14px 0;border:none;border-top:1px solid rgba(0,51,102,.12);'>", unsafe_allow_html=True)
    st.markdown("<b>2) OVR berdasarkan kategori</b>", unsafe_allow_html=True)

    if not eligible_dims:
        st.warning("Tidak ada kolom yang eligible untuk basis OVR di data ini.")
        return

    default_dims = [d for d in (st.session_state.get("ovr_dims", []) or []) if d in eligible_dims]
    if not default_dims:
        default_dims = ["COB"] if "COB" in eligible_dims else eligible_dims[:1]
        st.session_state["ovr_dims"] = default_dims



    with st.form("ovr_category_basis_form", clear_on_submit=False):
        picked_dims = st.multiselect(
            "Basis kategori",
            options=eligible_dims,
            default=default_dims,
            key="ovr_dims_picker",
            help="Pilih basis, lalu Generate Table jika ingin mengganti kombinasi kategori.",
        )
        generate_rules = st.form_submit_button("Generate category table", width="stretch")

    if generate_rules:
        picked_dims = [d for d in (picked_dims or []) if d in eligible_dims]
        if not picked_dims:
            st.warning("Pilih minimal satu basis kategori.")
        else:
            st.session_state["ovr_mode"] = "rules"
            st.session_state["ovr_dims"] = picked_dims
            st.session_state["ovr_rules_df"] = _gen_ovr_combos(picked_dims)
            st.session_state["ovr_last_dims_sig"] = "|".join(picked_dims)
            st.session_state["ovr_last_scope_sig"] = _ovr_scope_signature(df, picked_dims)
            st.session_state["ovr_rules_editor_version"] = st.session_state.get("ovr_rules_editor_version", 0) + 1
            st.session_state["ovr_applied"] = False
            st.session_state["ovr_confirmed"] = False
            try:
                st.rerun(scope="app")
            except TypeError:
                st.rerun()

    dims = [d for d in (st.session_state.get("ovr_dims", []) or []) if d in eligible_dims]
    rules_df = st.session_state.get("ovr_rules_df", pd.DataFrame())
    if not isinstance(rules_df, pd.DataFrame) or rules_df.empty:
        rules_df = _gen_ovr_combos(dims)
        st.session_state["ovr_rules_df"] = rules_df
        st.session_state["ovr_last_scope_sig"] = _ovr_scope_signature(df, dims)

    base_cols = dims + ["OVR_PCT_INPUT"] if dims else ["OVR_PCT_INPUT"]
    for c in base_cols:
        if c not in rules_df.columns:
            rules_df[c] = np.nan
    display_df = rules_df[base_cols].copy().reset_index(drop=True)
    editor_version = st.session_state.get("ovr_rules_editor_version", 0)
    editor_sig = hashlib.sha1(("|".join(dims) + "|" + str(editor_version)).encode("utf-8")).hexdigest()[:10]

    with st.form(key=f"ovr_rules_popover_form__{editor_sig}", clear_on_submit=False):
        edited = st.data_editor(
            display_df,
            width="stretch",
            num_rows="dynamic",
            hide_index=True,
            key=f"ovr_rules_popover_editor__{editor_sig}",
            disabled=[c for c in base_cols if c != "OVR_PCT_INPUT"],
            column_config={
                "OVR_PCT_INPUT": st.column_config.NumberColumn(
                    "OVR (%)",
                    min_value=0.0,
                    max_value=100.0,
                    step=0.1,
                    help="Contoh: 2 = 2%",
                )
            },
        )
        st.checkbox("Konfirmasi OVR kategori", key="ovr_confirm_checkbox")
        process_rules_clicked = st.form_submit_button("Proses OVR Kategori", type="primary", width="stretch")

    if process_rules_clicked:
        if not bool(st.session_state.get("ovr_confirm_checkbox", False)):
            st.warning("Centang Konfirmasi OVR kategori terlebih dahulu.")
        else:
            st.session_state["ovr_mode"] = "rules"
            st.session_state["ovr_keep_open"] = True
            st.session_state["ovr_user_touched"] = True
            if isinstance(edited, pd.DataFrame):
                edited_clean = edited.copy()
                if "OVR_PCT_INPUT" in edited_clean.columns:
                    edited_clean["OVR_PCT_INPUT"] = pd.to_numeric(edited_clean["OVR_PCT_INPUT"], errors="coerce")
                st.session_state["ovr_rules_df"] = edited_clean
                st.session_state["ovr_confirmed"] = True
                st.session_state["ovr_applied"] = True
                st.session_state["ovr_last_sig"] = _ovr_sig_from_state()
                _commit_ovr_configuration()
                _rerun_full_app_after_ovr()

@_fragment_if_available
def render_ovr_input_fragment(df: pd.DataFrame, embedded: bool = False) -> None:



    if embedded:
        _render_ovr_popover_safe(df)
        return

    st.markdown("""
    <style>
      div[data-testid="stExpander"] details:has(.ovr-advanced-title){
        border:1px solid rgba(0,51,102,0.12) !important;
        border-radius:18px !important;
        background:#FFFFFF !important;
        box-shadow:0 8px 22px rgba(15,23,42,0.04) !important;
      }
      .ovr-advanced-title{font-size:15px;font-weight:850;color:#003366;margin-bottom:2px;}
      .ovr-advanced-sub{font-size:12.2px;color:#64748B;line-height:1.3;margin-bottom:8px;}
    </style>
    """, unsafe_allow_html=True)

    def _keep_ovr_open():
        st.session_state["ovr_keep_open"] = True
        st.session_state["ovr_user_touched"] = True
        st.session_state["ovr_collapse_after_saved_report_load"] = False

    collapse_after_saved_load = bool(st.session_state.get("ovr_collapse_after_saved_report_load", False))
    if collapse_after_saved_load and not st.session_state.get("ovr_keep_open", False) and not st.session_state.get("ovr_user_touched", False):
        ovr_expanded = False
    else:
        ovr_expanded = bool(
            st.session_state.get("ovr_keep_open", False)
            or st.session_state.get("ovr_user_touched", False)
            or st.session_state.get("ovr_applied", False)
            or st.session_state.get("ovr_confirmed", False)
        )
    panel = st.container() if embedded else st.expander("Advanced: OVR Adjustment", expanded=ovr_expanded)
    with panel:
        st.markdown(
            "<div class='ovr-advanced-title'>OVR Adjustment</div>"
            "<div class='ovr-advanced-sub'>Optional adjustment. It affects KPI, dashboard table, and exports only after Proses OVR.</div>",
            unsafe_allow_html=True,
        )

        st.session_state.setdefault("ovr_mode", "uniform")
        ovr_mode = st.radio(
            "Metode",
            options=["uniform", "rules"],
            key="ovr_mode",
            format_func=lambda x: "Sama" if x == "uniform" else "Per kategori",
            on_change=_keep_ovr_open,
        )


        def _ovr_sig():
            mode = st.session_state.get("ovr_mode", "uniform")
            if mode == "uniform":
                return ("uniform", float(st.session_state.get("ovr_uniform_pct_input", 0.0)))
            dims = tuple(st.session_state.get("ovr_dims", []))
            rules_df = st.session_state.get("ovr_rules_df")
            if isinstance(rules_df, pd.DataFrame) and not rules_df.empty:
                preview_cols = [c for c in (list(dims) + ["OVR_PCT_INPUT"]) if c in rules_df.columns]
                preview_df = rules_df[preview_cols].copy() if preview_cols else rules_df.copy()
                preview_json = preview_df.astype("string").fillna("<NA>").to_json(orient="split")
                h = hashlib.sha1(preview_json.encode("utf-8")).hexdigest()
            else:
                h = "empty"
            return ("rules", dims, h)

        current_sig = _ovr_sig()
        if st.session_state.get("ovr_last_sig") != current_sig:
            st.session_state["ovr_applied"] = False
            st.session_state["ovr_confirmed"] = False
            st.session_state["ovr_last_sig"] = current_sig

        if ovr_mode == "uniform":
            st.session_state.setdefault("ovr_uniform_pct_input", 0.0)
            st.number_input(
                "OVR (%)",
                min_value=0.0, max_value=100.0, step=0.1,
                key="ovr_uniform_pct_input",
                help="Contoh: 2 = 2%",
                on_change=_keep_ovr_open,
            )

        else:
            eligible_dims = [c for c in [
                "UW_YEAR","UW_MONTH","INTERMEDIARY_NAME","INSURED_NAME","COB","TOB","LOB","TSI RANGE",
                "MARKETING_NAME","MARKETING_GROUP","BRANCH","INTERMEDIARY_BRANCH","PCKG_DESC"
            ] if c in df.columns]
            if not eligible_dims:
                st.warning("Tidak ada kolom yang eligible untuk basis OVR di data ini.")
            else:
                st.session_state.setdefault("ovr_dims", ["COB"] if "COB" in eligible_dims else [])
                _sync_multiselect_state("ovr_dims", eligible_dims)
                st.multiselect(
                    "Basis",
                    options=eligible_dims,
                    key="ovr_dims",
                    on_change=_keep_ovr_open,
                )

                st.session_state.setdefault("ovr_top_n", 200)


                dims = st.session_state.get("ovr_dims", [])
                dims_sig = "|".join(dims)

                def _gen_ovr_combos(_dims):
                    return _build_ovr_combos_from_filtered_df(df, _dims, limit=200)



                if dims:
                    current_scope_sig = _ovr_scope_signature(df, dims)
                    current_rules = st.session_state.get("ovr_rules_df")
                    stored_scope_sig = st.session_state.get("ovr_last_scope_sig", "")
                    rules_match_scope = _ovr_rules_match_current_scope(current_rules, df, dims)
                    needs_scope_refresh = (
                        st.session_state.get("ovr_last_dims_sig") != dims_sig
                        or not isinstance(current_rules, pd.DataFrame)
                        or current_rules.empty
                        or (stored_scope_sig and stored_scope_sig != current_scope_sig)
                        or (not stored_scope_sig and not rules_match_scope)
                    )
                    if needs_scope_refresh:
                        st.session_state["ovr_rules_df"] = _gen_ovr_combos(dims)
                        st.session_state["ovr_rules_editor_version"] = st.session_state.get("ovr_rules_editor_version", 0) + 1
                        st.session_state["ovr_applied"] = False
                        st.session_state["ovr_confirmed"] = False
                    st.session_state["ovr_last_dims_sig"] = dims_sig
                    st.session_state["ovr_last_scope_sig"] = current_scope_sig
                else:
                    st.session_state["ovr_last_dims_sig"] = dims_sig
                    st.session_state["ovr_last_scope_sig"] = ""


                if dims:
                    if st.button("Reset", key="ovr_refresh_btn"):
                        st.session_state["ovr_keep_open"] = True
                        st.session_state["ovr_user_touched"] = True
                        st.session_state["ovr_rules_df"] = _gen_ovr_combos(dims)
                        st.session_state["ovr_last_scope_sig"] = _ovr_scope_signature(df, dims)
                        st.session_state["ovr_rules_editor_version"] = st.session_state.get("ovr_rules_editor_version", 0) + 1
                        st.session_state["ovr_applied"] = False
                        st.session_state["ovr_confirmed"] = False
                        st.rerun()



                dims = st.session_state.get("ovr_dims", [])
                rules_df = st.session_state.get("ovr_rules_df", pd.DataFrame())
                if not isinstance(rules_df, pd.DataFrame):
                    rules_df = pd.DataFrame()
                base_cols = (dims + ["OVR_PCT_INPUT"]) if dims else ["OVR_PCT_INPUT"]
                if rules_df.empty:
                    rules_df = pd.DataFrame(columns=base_cols)
                else:
                    for c in base_cols:
                        if c not in rules_df.columns:
                            rules_df[c] = np.nan

                ovr_confirmed = st.checkbox(
                    "Konfirmasi OVR",
                    key="ovr_confirm_checkbox",
                    on_change=_keep_ovr_open,
                )
                display_df = rules_df[base_cols].copy().reset_index(drop=True)
                editor_version = st.session_state.get("ovr_rules_editor_version", 0)
                editor_sig = hashlib.sha1((dims_sig + "|" + str(editor_version)).encode("utf-8")).hexdigest()[:10]

                with st.form(key=f"ovr_rules_form__{editor_sig}", clear_on_submit=False):
                    edited = st.data_editor(
                        display_df,
                        width="stretch",
                        num_rows="dynamic",
                        hide_index=True,
                        key=f"ovr_rules_editor__{editor_sig}",
                        disabled=[c for c in base_cols if c != "OVR_PCT_INPUT"],
                        column_config={
                            "OVR_PCT_INPUT": st.column_config.NumberColumn(
                                "OVR (%)",
                                min_value=0.0,
                                max_value=100.0,
                                step=0.1,
                                help="Contoh: 2 = 2%"
                            )
                        },
                    )

                    process_rules_clicked = st.form_submit_button(
                        "Proses OVR",
                        type="primary",
                        width="stretch",
                        disabled=not ovr_confirmed,
                    )

                if process_rules_clicked:
                    st.session_state["ovr_keep_open"] = True
                    st.session_state["ovr_user_touched"] = True
                    if isinstance(edited, pd.DataFrame):
                        edited_clean = edited.copy()
                        if "OVR_PCT_INPUT" in edited_clean.columns:
                            edited_clean["OVR_PCT_INPUT"] = pd.to_numeric(
                                edited_clean["OVR_PCT_INPUT"],
                                errors="coerce"
                            )
                        st.session_state["ovr_rules_df"] = edited_clean
                        st.session_state["ovr_confirmed"] = True
                        st.session_state["ovr_applied"] = True
                        st.session_state["ovr_last_sig"] = _ovr_sig()
                        _commit_ovr_configuration()
                        _rerun_full_app_after_ovr()
        st.markdown("")
        if ovr_mode == "uniform":
            ovr_confirmed_uniform = st.checkbox(
                "Konfirmasi OVR",
                key="ovr_confirm_checkbox_uniform",
                on_change=_keep_ovr_open,
            )
            process_clicked = st.button(
                "Proses OVR",
                type="primary",
                key="ovr_process_btn",
                disabled=not ovr_confirmed_uniform,
            )
            if process_clicked:
                st.session_state["ovr_keep_open"] = True
                st.session_state["ovr_user_touched"] = True
                st.session_state["ovr_confirmed"] = True
                st.session_state["ovr_applied"] = True
                st.session_state["ovr_last_sig"] = _ovr_sig()
                _commit_ovr_configuration()
                _rerun_full_app_after_ovr()
        else:
            st.caption("Untuk mode berdasarkan kategori, gunakan tombol Proses OVR di bawah tabel OVR.")



def dashboard(username, role=None):
    inject_compact_section_css()
    st.markdown("""
    <style>
      .rp-summary-strip{
        display:flex;
        flex-wrap:wrap;
        gap:10px;
        align-items:center;
        margin: 8px 0 18px 0;
      }
      .rp-summary-chip{
        display:inline-flex;
        align-items:center;
        gap:7px;
        padding:8px 12px;
        border-radius:999px;
        background:#FFFFFF;
        border:1px solid rgba(0,51,102,0.12);
        box-shadow:0 5px 14px rgba(15,23,42,0.035);
        color:#1E293B;
        font-size:12.5px;
        font-weight:750;
      }
      .rp-summary-chip span{
        color:#64748B;
        font-weight:650;
      }
      div[data-testid="stExpander"] details:has(.rp-settings-title){
        border:1px solid rgba(0,51,102,0.12) !important;
        border-radius:18px !important;
        background:#FFFFFF !important;
        box-shadow:0 8px 22px rgba(15,23,42,0.04) !important;
        margin-bottom:10px !important;
      }
      .rp-settings-title{
        font-size:16px;
        font-weight:850;
        color:#003366;
        line-height:1.15;
        margin-bottom:2px;
      }
      .rp-settings-sub{
        font-size:12.3px;
        color:#64748B;
        line-height:1.35;
        margin-bottom:8px;
      }
      .rp-hero{
        margin: 0 0 12px 0 !important;
        padding: 8px 0 0 0 !important;
        overflow: visible !important;
      }
      .rp-hero h1{
        margin: 0 0 4px 0 !important;
        padding: 0 0 2px 0 !important;
        color:#1F2937;
        font-size: clamp(34px, 3.6vw, 46px);
        line-height: 1.16;
        font-weight: 900;
        letter-spacing: -0.03em;
        overflow: visible !important;
      }
      .rp-hero p{
        margin: 0 !important;
        padding: 0 !important;
        color:#334155;
        font-size: 16px;
        line-height: 1.28;
        font-weight: 500;
      }
    </style>
    <div class="rp-hero">
      <h1>Combined Ratio Dashboard</h1>
    </div>
    """, unsafe_allow_html=True)

    tanggal_opsi = list(RISK_PROFILE_SNAPSHOTS)
    st.session_state.setdefault("risk_profile_as_of_date", tanggal_opsi[12])
    st.session_state.setdefault("risk_profile_display_unit", "in IDR Mio")
    if st.session_state.get("risk_profile_as_of_date") not in tanggal_opsi:
        st.session_state["risk_profile_as_of_date"] = tanggal_opsi[5]
    if st.session_state.get("risk_profile_display_unit") not in DISPLAY_UNIT_OPTIONS:
        st.session_state["risk_profile_display_unit"] = "in IDR Mio"

    tanggal_pilihan = st.session_state["risk_profile_as_of_date"]
    display_unit = _normalize_display_unit(st.session_state["risk_profile_display_unit"])



    summary_strip_slot = st.container(key="rp_summary_strip_stable_container")





    report_workspace_slot = st.container(key="rp_report_workspace_stable_container")

    df = load_all_data(RISK_PROFILE_SNAPSHOTS[tanggal_pilihan])

    st.sidebar.header("Filters")
    filter_cols = [
        "UW_YEAR", "UW_MONTH", "INTERMEDIARY_NAME", "INSURED_NAME",
        "COB", "TOB", "LOB", "TSI RANGE", "MARKETING_NAME", "MARKETING_GROUP",
        "BRANCH", "INTERMEDIARY_BRANCH", "PCKG_DESC", "IS_FRONTING", "ISSUE",
        "UW_PERIOD", "OCCUPATION", "CRE_BY"
    ]

    filter_cols = [col for col in filter_cols if col in df.columns]





    document_filter_options = {
        col: sorted(df[col].dropna().unique())
        for col in filter_cols
        if col in df.columns
    }
    _inject_multiselect_select_all_guard_css(
        any(len(opts) > MAX_DIRECT_MULTISELECT_FILTER_VALUES for opts in document_filter_options.values())
    )
    render_document_filter_loader(document_filter_options)
    _apply_pending_saved_report_if_any(document_filter_options)




    df_base = df
    active_filters = {}
    filtered_df = df_base

    for col in filter_cols:
        mode_key = f"{col}_mode"
        sel_key = f"{col}_selected"

        if mode_key not in st.session_state:
            st.session_state[mode_key] = "Include Selected"

        if sel_key not in st.session_state:
            if col == "IS_FRONTING":
                st.session_state[mode_key] = "Include Selected"
                st.session_state[sel_key] = ["NON_FRONTING"]
            elif col == "LOB":
                st.session_state[mode_key] = "Exclude Selected"
                st.session_state[sel_key] = ["CREDIT INSURANCE"]
            else:
                st.session_state[mode_key] = "Include Selected"
                st.session_state[sel_key] = []

        with st.sidebar.expander(f"{col}", expanded=False):
            mode = st.selectbox(
                "Mode & Selection",
                ["Include Selected", "Include All", "Exclude Selected", "Exclude All"],
                key=mode_key,
            )

            show_multiselect = mode in ["Include Selected", "Exclude Selected"]
            current_options = sorted(filtered_df[col].dropna().unique())
            _sync_multiselect_state(sel_key, current_options)
            _sanitize_multiselect_state_before_widget(sel_key, current_options)

            if not show_multiselect and st.session_state.get(sel_key):
                st.session_state[sel_key] = []

            selected_vals = _render_guarded_filter_multiselect(
                "Choose items",
                current_options,
                key=sel_key,
                disabled=not show_multiselect,
            )

            selected_vals = list(selected_vals or [])



            broad_selection_blocked = (
                _selection_represents_all(selected_vals, current_options)
                or _selection_is_too_large_for_direct_filter(selected_vals)
            )
            if broad_selection_blocked:
                selected_vals = []
                if show_multiselect:
                    st.caption("Select all / pilihan terlalu banyak dianggap filter tidak aktif.")

            if st.session_state.pop(f"{sel_key}__guard_notice", False) and show_multiselect:
                st.caption("Select all / pilihan terlalu banyak dinonaktifkan. Pilih item yang dibutuhkan secara langsung.")

            if mode == "Include Selected" and selected_vals:
                filtered_df = filtered_df[filtered_df[col].isin(selected_vals)]
                active_filters[col] = {"mode": mode, "values": list(selected_vals)}
            elif mode == "Exclude Selected" and selected_vals:
                filtered_df = filtered_df[~filtered_df[col].isin(selected_vals)]
                active_filters[col] = {"mode": mode, "values": list(selected_vals)}
            elif mode == "Exclude All":
                filtered_df = filtered_df.iloc[0:0]
                active_filters[col] = {"mode": mode, "values": ["All"]}

    df = filtered_df
    if df.empty:
        _render_memory_usage(username, df_base=df_base, df_view=df)
        st.warning("No data on this filter")
    

        tabs = st.tabs([
            "UW Year", "CoB", "LoB", "INTERMEDIARY", "INSURED NAME",
            "MKT NAME", "MKT GROUP", "BRANCH",
            "Our TSI", "TSI", "Policy No.", "INT BRANCH"
        ])
    
        for t in tabs:
            with t:
                st.info("No data on this filter")

        return

    




    with st.sidebar.expander("INSURED_NAME_2", expanded=False):


        insured2_mode = st.radio(
            "Mode",
            ["Include Selected", "Exclude Selected", "All"],
            index=0,
            key="mode_INSURED2"
        )

        insured2_selected = _render_lazy_search_multiselect(
            "Hasil pencarian:",
            df["INSURED_NAME_2"],
            key="select_INSURED2",
            disabled=insured2_mode == "All",
            search_key="query_INSURED2",
            search_label="Cari nama tertanggung",
            search_placeholder="Ketik lalu tekan Enter",
            help_text="Pencarian substring biasa. Tidak ada fuzzy search. Maksimal 250 hasil dimuat setelah Enter.",
        )

        if insured2_selected:
            st.caption(f"{len(insured2_selected)} item selected")
    

        if insured2_mode == "Include Selected" and insured2_selected:
            df = df[df["INSURED_NAME_2"].astype(str).isin(insured2_selected)]
    
        elif insured2_mode == "Exclude Selected" and insured2_selected:
            df = df[~df["INSURED_NAME_2"].astype(str).isin(insured2_selected)]
    

        active_filters["INSURED_NAME_2"] = {
            "mode": insured2_mode,
            "values": insured2_selected if insured2_selected else ["All"]
        }
       
    with st.sidebar.expander("POLICY_NO", expanded=False):
        polno_mode = st.radio(
            "Mode",
            ["Include Selected", "Exclude Selected", "All"],
            index=0,
            key="mode_POLNO"
        )

        st.markdown("""
        <style>
          /* POLICY_NO upload area: keep it readable inside the dark sidebar. */
          section[data-testid="stSidebar"] div[data-testid="stFileUploader"]{
            margin-top: 2px !important;
          }
          section[data-testid="stSidebar"] div[data-testid="stFileUploader"] section{
            background: #FFFFFF !important;
            border: 1.5px solid rgba(255,255,255,0.62) !important;
            border-radius: 14px !important;
            box-shadow: inset 0 0 0 1px rgba(0,51,102,0.06), 0 10px 22px rgba(0,0,0,0.10) !important;
          }
          section[data-testid="stSidebar"] div[data-testid="stFileUploader"] section *{
            color: #1E293B !important;
            -webkit-text-fill-color: #1E293B !important;
          }
          section[data-testid="stSidebar"] div[data-testid="stFileUploader"] button{
            background: linear-gradient(135deg, #003366 0%, #1F5A91 100%) !important;
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
            border: 1px solid rgba(255,255,255,0.38) !important;
            border-radius: 10px !important;
            font-weight: 850 !important;
            box-shadow: 0 6px 16px rgba(0,51,102,0.24) !important;
            opacity: 1 !important;
          }
          section[data-testid="stSidebar"] div[data-testid="stFileUploader"] button *{
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
          }
          section[data-testid="stSidebar"] div[data-testid="stFileUploader"] svg{
            color: #FFFFFF !important;
            fill: #FFFFFF !important;
          }
          section[data-testid="stSidebar"] div[data-testid="stFileUploader"] small,
          section[data-testid="stSidebar"] div[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"] *{
            color: #475569 !important;
            -webkit-text-fill-color: #475569 !important;
          }
        </style>
        """, unsafe_allow_html=True)

        polno_file = st.file_uploader(
            "Upload Excel",
            type=["xlsx"],
            key="upload_POLNO_excel"
        )

        uploaded_polnos = []
        if polno_file is not None:
            try:
                upload_df = pd.read_excel(polno_file)
                if not upload_df.empty:
                    possible_cols = [
                        c for c in upload_df.columns
                        if str(c).strip().upper().replace(" ", "_") in [
                            "POLICY_NO", "POLICY_NUMBER", "NO_POLIS", "NOMOR_POLIS", "POLIS"
                        ]
                    ]
                    source_col = possible_cols[0] if possible_cols else upload_df.columns[0]
                    uploaded_polnos = (
                        upload_df[source_col]
                        .dropna()
                        .astype(str)
                        .str.strip()
                        .str.replace(r"\.0$", "", regex=True)
                    )
                    uploaded_polnos = [x for x in uploaded_polnos.tolist() if x and x.lower() != "nan"]
                    uploaded_polnos = list(dict.fromkeys(uploaded_polnos))
                    st.success(f"{len(uploaded_polnos):,} policy loaded")
            except Exception:
                st.error("File tidak bisa dibaca.")

        polno_manual_selected = _render_lazy_search_multiselect(
            "Hasil pencarian",
            df["POLICY_NO"],
            key="select_POLNO",
            disabled=polno_mode == "All",
            search_key="query_POLNO",
            search_label="Cari nomor polis",
            search_placeholder="Ketik lalu tekan Enter",
            help_text="Pencarian substring biasa. Tidak ada fuzzy search. Maksimal 250 hasil dimuat setelah Enter.",
        )

        polno_selected = list(dict.fromkeys(list(uploaded_polnos) + list(polno_manual_selected or [])))

        if polno_selected:
            st.caption(f"{len(polno_selected):,} policy selected")

        if polno_mode == "Include Selected" and polno_selected:
            df = df[df["POLICY_NO"].astype(str).isin(polno_selected)]

        elif polno_mode == "Exclude Selected" and polno_selected:
            df = df[~df["POLICY_NO"].astype(str).isin(polno_selected)]

        active_filters["POLICY_NO"] = {
            "mode": polno_mode,
            "values": polno_selected if polno_selected else ["All"]
        }



    df_work = _apply_portfolio_cost_adjustments(df)

    _render_memory_usage(username, df_base=df_base, df_view=df, df_work=df_work)






    kpis = compute_kpis(df_work)
    render_section_card_header("Key Performance")
    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
    render_kpi_cards(kpis, display_unit)

    render_trend_projection_section(df_work, display_unit, as_of_date=tanggal_pilihan)

    render_simulation_section(df_work, display_unit, username, active_filters, as_of_date=tanggal_pilihan)

    
    st.sidebar.markdown("---")

    df_ovr = df_work

    ovr_include_for_export = _get_applied_ovr_configuration() is not None
    ovr_status_for_export = "Include OVR" if ovr_include_for_export else "Exclude OVR"
    ovr_detail_for_export = get_ovr_detail_df_for_export() if ovr_include_for_export else pd.DataFrame()

    with summary_strip_slot:
        st.markdown(
            f"""
            <div class="rp-summary-strip">
              <div class="rp-summary-chip"><span>OVR</span> {html.escape(ovr_status_for_export)}</div>
              <div class="rp-summary-chip"><span>OPEX</span> {html.escape(_opex_assumption_note().replace("OPEX assumption: ", ""))}</div>
              <div class="rp-summary-chip"><span>As at</span> {html.escape(tanggal_pilihan[7:])}</div>
              <div class="rp-summary-chip"><span>Display</span> {html.escape(_display_unit_label(display_unit))}</div>
              <div class="rp-summary-chip"><span>Excel</span> Original Number</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with report_workspace_slot:
        st.markdown("""
        <style>
          .workspace-shell-title{
            font-size: 15px;
            line-height: 1.15;
            font-weight: 900;
            letter-spacing: -0.01em;
            color:#003366;
            margin: 0 0 10px 0;
          }
          .saved-view-title{
            font-size: 13px;
            line-height: 1.15;
            font-weight: 850;
            color:#003366;
            margin: 0 0 8px 0;
          }
          .saved-view-shell{
            padding-top: 2px;
          }
          /* Compact icon-only executive toolbar. Scoped to popover buttons only. */
          div[data-testid="stPopover"] > button{
            width: 54px !important;
            min-width: 54px !important;
            max-width: 54px !important;
            min-height: 44px !important;
            height: 44px !important;
            padding: 0 !important;
            border-radius: 13px !important;
            border: 1px solid rgba(0,51,102,0.16) !important;
            background: linear-gradient(180deg, #FFFFFF 0%, #F5F8FB 100%) !important;
            color: #003366 !important;
            -webkit-text-fill-color: #003366 !important;
            font-size: 18px !important;
            font-weight: 900 !important;
            box-shadow: none !important;
          }
          div[data-testid="stPopover"] > button:hover{
            background: #EEF6FF !important;
            border-color: rgba(0,51,102,0.32) !important;
            transform: translateY(-1px);
            box-shadow: 0 8px 18px rgba(0,51,102,0.08) !important;
          }
          div[data-testid="stPopover"] > button p{
            color:#003366 !important;
            -webkit-text-fill-color:#003366 !important;
            font-weight:900 !important;
            font-size:18px !important;
            margin:0 !important;
          }
          div[data-testid="stFormSubmitButton"] button{
            border-radius: 11px !important;
            border: 1px solid rgba(0,51,102,0.72) !important;
            background: linear-gradient(135deg, #003366 0%, #1F5A91 100%) !important;
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
            font-size: 12.2px !important;
            font-weight: 850 !important;
            min-height: 36px !important;
            box-shadow: 0 8px 18px rgba(0,51,102,0.14) !important;
          }
          div[data-testid="stFormSubmitButton"] button p{
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
            font-weight: 850 !important;
          }
          div[class*="st-key-open_quick_saved_report_btn"] button{
            min-width: 82px !important;
            height: 38px !important;
            min-height: 38px !important;
            padding: 0 14px !important;
            border-radius: 11px !important;
            border: 1px solid rgba(0,51,102,0.22) !important;
            background: #FFFFFF !important;
            color: #003366 !important;
            -webkit-text-fill-color: #003366 !important;
            font-size: 12.2px !important;
            font-weight: 850 !important;
            box-shadow: none !important;
          }
          div[class*="st-key-open_quick_saved_report_btn"] button:hover{
            background: #EEF6FF !important;
            border-color: rgba(0,51,102,0.36) !important;
          }
          div[class*="st-key-open_quick_saved_report_btn"] button p{
            color: #003366 !important;
            -webkit-text-fill-color: #003366 !important;
            font-weight: 850 !important;
            white-space: nowrap !important;
          }
        </style>
        """, unsafe_allow_html=True)

        def _popover(label: str, key: str, tooltip: str = ""):
            if hasattr(st, "popover"):
                try:
                    return st.popover(label, help=tooltip, width="content")
                except TypeError:
                    try:
                        return st.popover(label, help=tooltip)
                    except TypeError:
                        return st.popover(label)
            return st.expander(tooltip or label, expanded=False)

        @_claim_fragment_if_available
        def _render_quick_saved_views():
            saved_notice = st.session_state.pop("saved_report_notice", None)
            if saved_notice:
                st.success(saved_notice)

            st.markdown("<div class='saved-view-title'>Saved Views</div>", unsafe_allow_html=True)
            records = list_saved_report_records(limit=120)

            search_col, list_col, open_col = st.columns([0.35, 0.47, 0.18], gap="small", vertical_alignment="bottom")
            with search_col:
                quick_query = st.text_input(
                    "Search",
                    key="saved_report_quick_query",
                    placeholder="Search",
                    label_visibility="collapsed",
                )

            filtered_records = _filter_saved_report_records(records, quick_query)[:25]
            option_ids = [""] + [_sanitize_doc_id(r.get("REPORT_ID")) for r in filtered_records]
            label_map = {_sanitize_doc_id(r.get("REPORT_ID")): _saved_report_label(r) for r in filtered_records}

            current_quick_id = _sanitize_doc_id(st.session_state.get("saved_report_quick_selected_id", ""))
            if current_quick_id and current_quick_id not in option_ids:
                st.session_state["saved_report_quick_selected_id"] = ""

            with list_col:
                selected_quick_id = st.selectbox(
                    "Saved list",
                    options=option_ids,
                    key="saved_report_quick_selected_id",
                    format_func=lambda x: "Choose saved view" if not x else label_map.get(x, x),
                    label_visibility="collapsed",
                )
            with open_col:
                open_quick_saved = st.button(
                    "Open",
                    key="open_quick_saved_report_btn",
                    width="stretch",
                    disabled=not bool(_sanitize_doc_id(selected_quick_id)),
                )

            if not filtered_records and str(quick_query or "").strip():
                st.caption("No saved view found.")

            if open_quick_saved:
                selected_quick_id = _sanitize_doc_id(st.session_state.get("saved_report_quick_selected_id", ""))
                if selected_quick_id:
                    selected_meta = next((r for r in filtered_records if _sanitize_doc_id(r.get("REPORT_ID")) == selected_quick_id), None)
                    if selected_meta is None:
                        selected_meta = get_saved_report_record(selected_quick_id)
                    title = str(selected_meta.get("LABEL") if selected_meta else "").strip()
                    st.session_state["pending_saved_report_id"] = selected_quick_id
                    st.session_state["pending_saved_report_title"] = title
                    st.session_state.pop("loaded_ovr_notice", None)
                    try:
                        st.rerun(scope="app")
                    except TypeError:
                        st.rerun()

        workspace_expanded = bool(st.session_state.get("report_workspace_expanded", False))
        with st.expander("Report Tools & Search Report", expanded=workspace_expanded):
            tools_col, saved_col = st.columns([2.3, 5.4], gap="medium", vertical_alignment="top")

            with tools_col:
                with st.container(border=True):
                    st.markdown("<div class='workspace-shell-title'>Report Tools</div>", unsafe_allow_html=True)
                    can_adjust_assumptions = _can_adjust_opex_assumptions(username, role)
                    pop_cols = st.columns(4 if can_adjust_assumptions else 3, gap="small")

                    with pop_cols[0]:
                        with _popover("⚙", "report_ws_popover_settings", "Settings"):
                            with st.form("report_workspace_settings_form", clear_on_submit=False):
                                st.selectbox(
                                    "As of date",
                                    tanggal_opsi,
                                    key="risk_profile_as_of_date",
                                )
                                st.selectbox(
                                    "Show numbers as",
                                    DISPLAY_UNIT_OPTIONS,
                                    key="risk_profile_display_unit",
                                )
                                settings_applied = st.form_submit_button("Apply", width="content")

                    with pop_cols[1]:
                        with _popover("💾", "report_ws_popover_save_current", "Save Current"):
                            render_saved_report_save_controls(
                                username,
                                active_filters,
                                df_ovr,
                                ovr_status_for_export,
                                ovr_detail_for_export,
                                embedded=True,
                            )

                    with pop_cols[2]:
                        with _popover("+", "report_ws_popover_ovr", "OVR"):
                            render_ovr_input_fragment(df, embedded=True)

                    if can_adjust_assumptions:
                        with pop_cols[3]:
                            with _popover("Σ", "report_ws_popover_assumptions", "Adjust Assumptions"):
                                render_opex_assumption_controls(username, role)

            with saved_col:
                st.markdown("<div class='saved-view-shell'>", unsafe_allow_html=True)
                _render_quick_saved_views()
                st.markdown("</div>", unsafe_allow_html=True)




    risk_detail_for_claim = pd.DataFrame()
    claim_source_df = df
    if {"POLICY_NO", "UW_YEAR"}.issubset(claim_source_df.columns):
        risk_detail_for_claim = (
            claim_source_df[[c for c in ["POLICY_NO", "UW_YEAR", "INTERMEDIARY_NAME", "INSURED_NAME"] if c in claim_source_df.columns]]
            .dropna(subset=["POLICY_NO"])
            .drop_duplicates()
            .reset_index(drop=True)
        )

    render_detailed_data_fragment(
        df_ovr,
        active_filters,
        tanggal_pilihan,
        username,
        risk_detail_for_claim,
        ovr_status_for_export,
        ovr_detail_for_export,
        display_unit,
    )

    render_claim_breakdown_stable(risk_detail_for_claim)
    render_large_loss_section(risk_detail_for_claim, display_unit)



def _render_safe_error(exc: Exception):
    st.error("Under Reconstruction\n#BakalJadiKeren")
    with st.expander("Technical details", expanded=False):
        st.code(str(exc))





def dashboard1(username, role=None):
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = True
    if not st.session_state["logged_in"]:
        st.write("Please login from main SuperApp.")
    else:
        try:
            dashboard(username, role)
        except Exception as e:
            st.error("Under Reconstruction\n#BakalJadiKeren")
            with st.expander("Technical details", expanded=False):
                st.code(str(e))
        if st.sidebar.button("Logout", key="logout_btn"):
            st.session_state["logged_in"] = False
            st.rerun()

def main(username="guest", role=None):


    if _get_query_param_value("verify_rp"):
        render_rp_pdf_verification_page()
        return




    _capture_open_report_query_if_any()

    dashboard1(username, role)


if __name__ == "__main__":
    main()
