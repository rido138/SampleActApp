import base64
import hashlib
import html
import io
import json
import os
import re
import unicodedata
import uuid
import smtplib
import time
import tempfile
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from urllib.parse import urlencode
from datetime import datetime, date
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import grey
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None
    Credentials = None







EXGRATIA_RISK_DATASET_FILES = (
    "RP261002_part1.xlsx",
    "RP261002_part2.xlsx",
)
DEFAULT_RISK_PATHS = EXGRATIA_RISK_DATASET_FILES
EXGRATIA_LOOKUP_PATCH = "fixed-manual-claim-email-routing-v7"
EXGRATIA_PDF_TEXT_PATCH = "red-workflow-notes-v14"
EXGRATIA_CREATOR_EDIT_PATCH = "creator-edit-unresolved-sendback-v3-20260904"
EXGRATIA_RATIO_SCENARIO_PATCH = "existing-vs-exgratia-lr-cor-v1-20260904"
EXGRATIA_MAX_NARRATIVE_CHARS = 500

NAVY = "#003366"
NAVY_2 = "#002B57"
SOFT_BLUE = "#EEF6FF"
SOFT_GRID = "#AEB7C2"
SOFT_ZEBRA = "#F6F8FB"
WARN_RED = "#FFE7E7"
WARN_ORANGE = "#FFF3D6"
TEXT_DARK = "#111827"

MONEY_COLUMNS = [
    "GWP_AMT", "GEP_AMT", "GROSS_CLAIM", "COMMISSIONS",
    "RI_COST", "ERC_AMT", "RI_RECOVERY", "OVR_AMT",
]

DISPLAY_UNIT_OPTIONS = ["in IDR Mio", "Original Number"]
DISPLAY_UNIT_CONFIG = {
    "in IDR Mio": {"factor": 1_000_000, "label": "IDR Mio", "short": "Mio", "note": "Data shown in IDR Mio"},
    "Original Number": {"factor": 1, "label": "IDR", "short": "IDR", "note": "Data shown in original IDR amount"},
}

EXGRATIA_PERFORMANCE_COLUMNS = [
    "UW YEARS",
    "GWP",
    "GROSS CLAIM",
    "LOSS RATIO EXISTING",
    "LOSS RATIO + EX-GRATIA",
    "COMBINED RATIO EXISTING",
    "COMBINED RATIO + EX-GRATIA",
]

GSHEET_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
EXGRATIA_RECORD_SHEET = "ex_gratia_records"
EXGRATIA_RECORD_HEADERS = [
    "DOC_ID", "CREATED_AT", "CREATED_BY", "STATUS", "CURRENT_STAGE",
    "CLAIM_NO", "POLICY_NO", "POLICY_UW_YEAR", "COB", "SOURCE_BUSINESS", "INSURED_NAME",
    "LOSS_DATE", "CLAIM_AMOUNT", "EXGRATIA_AMOUNT", "MNC_SHARE",
    "LOSS_CAUSE", "EXGRATIA_REASON", "FUTURE_BUSINESS", "CORRESPONDING_EMAIL",
    "RI_COST", "NEEDS_REINSURANCE",
    "OVR_MODE", "OVR_CATEGORY", "OVR_UNIFORM_PCT", "OVR_RULES_GT_0",
    "DISPLAY_UNIT", "INTERMEDIARY_SUMMARY_JSON", "INSURED_SUMMARY_JSON", "OVR_CONTEXT_JSON",
    "MARKETING_MANAGER_EMAIL", "MARKETING_MANAGER_NOTE", "MARKETING_MANAGER_CONFIRMED_BY", "MARKETING_MANAGER_CONFIRMED_AT",
    "CLAIM_NOTE", "CLAIM_CONFIRMED_BY", "CLAIM_CONFIRMED_AT",
    "REINSURANCE_NOTE", "REINSURANCE_CONFIRMED_BY", "REINSURANCE_CONFIRMED_AT",
    "DIR_MARKETING_NOTE", "DIR_MARKETING_CONFIRMED_BY", "DIR_MARKETING_CONFIRMED_AT",
    "DIR_TEKNIK_NOTE", "DIR_TEKNIK_CONFIRMED_BY", "DIR_TEKNIK_CONFIRMED_AT",
    "DIR_UTAMA_CONFIRMED_BY", "DIR_UTAMA_CONFIRMED_AT",
    "SEND_BACK_BY", "SEND_BACK_AT", "SEND_BACK_NOTE", "SEND_BACK_STAGE", "SEND_BACK_RETURN_STATUS", "SEND_BACK_TO",
    "SEND_BACK_RESOLVED_BY", "SEND_BACK_RESOLVED_AT",
    "WORKFLOW_NOTES_JSON",
    "DECLINED_BY", "DECLINED_AT", "DECLINE_NOTE",
    "CANCELED_BY", "CANCELED_AT", "CANCEL_NOTE",
    "LAST_UPDATED_AT", "LAST_UPDATED_BY", "PDF_FILE_NAME",
]

BOD_MARKETING_EMAIL = "meindy.sihombing@mnc-insurance.com"
BOD_TEKNIK_EMAIL = "david.jaya@mnc-insurance.com"
BOD_UTAMA_EMAIL = ""

CLAIM_MV_EMAIL = "trian.siswanto@mnc-insurance.com"
CLAIM_NONMV_EMAIL = "yauri.prasetio@mnc-insurance.com"

EXGRATIA_ALWAYS_CC_EMAILS = ["henry.sihombing@mnc-insurance.com"]







EG_VERIFY_HASH_FIELDS = [
    "DOC_ID", "CREATED_AT", "CREATED_BY", "STATUS", "CLAIM_NO", "POLICY_NO", "COB",
    "SOURCE_BUSINESS", "INSURED_NAME", "LOSS_DATE", "CLAIM_AMOUNT", "EXGRATIA_AMOUNT", "MNC_SHARE",
    "MARKETING_MANAGER_CONFIRMED_BY", "MARKETING_MANAGER_CONFIRMED_AT",
    "CLAIM_CONFIRMED_BY", "CLAIM_CONFIRMED_AT",
    "DIR_MARKETING_CONFIRMED_BY", "DIR_MARKETING_CONFIRMED_AT",
    "DIR_TEKNIK_CONFIRMED_BY", "DIR_TEKNIK_CONFIRMED_AT",
    "DECLINED_BY", "DECLINED_AT", "CANCELED_BY", "CANCELED_AT",
]


def _eg_verify_norm(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def compute_eg_verification_hash(record: dict | None) -> str:
    record = dict(record or {})
    if not _eg_verify_norm(record.get("DOC_ID")):
        record["DOC_ID"] = _eg_verify_norm(record.get("doc_id"))
    payload = {field: _eg_verify_norm(record.get(field, "")) for field in EG_VERIFY_HASH_FIELDS}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(("EXGRATIA-V1|" + raw).encode("utf-8")).hexdigest()[:12].upper()


def _get_app_base_url() -> str:


    for group, key in (("app", "base_url"), ("auth", "app_base_url"), ("auth", "base_url")):
        try:
            value = str(st.secrets[group].get(key, "") or "").strip()
            if value:
                return value.rstrip("/")
        except Exception:
            pass


    try:
        headers = st.context.headers
        host = headers.get("x-forwarded-host") or headers.get("host")
        proto = headers.get("x-forwarded-proto") or "https"
        if host:
            return f"{proto}://{host}".rstrip("/")
    except Exception:
        pass


    return "https://superapp-actuary-mncai.streamlit.app"


def _build_eg_verification_url(doc_id: str, verification_code: str) -> str:
    query = urlencode({"verify_eg": _sanitize_doc_id(doc_id), "code": str(verification_code or "").strip().upper()})
    return f"{_get_app_base_url()}/?{query}"


EXGRATIA_PAGE_NAME = "ex-Gratia"


def _get_exgratia_query_param(name: str, default: str = "") -> str:

    try:
        value = st.query_params.get(name, default)
        if isinstance(value, list):
            value = value[0] if value else default
        return str(value or default).strip()
    except Exception:
        return str(default or "").strip()


def _set_exgratia_url_state(view: str = "list", doc_id: str = "") -> None:

    view = str(view or "list").strip().lower()
    doc_id = _sanitize_doc_id(doc_id)

    try:
        st.query_params["page"] = EXGRATIA_PAGE_NAME
        st.query_params["eg_view"] = view

        if doc_id:
            st.query_params["eg_doc"] = doc_id
        else:
            try:
                del st.query_params["eg_doc"]
            except Exception:
                pass
    except Exception:
        pass


def _build_exgratia_detail_url(doc_id: str) -> str:

    query = urlencode({
        "page": EXGRATIA_PAGE_NAME,
        "eg_view": "detail",
        "eg_doc": _sanitize_doc_id(doc_id),
    })
    return f"{_get_app_base_url()}/?{query}"


def _qr_drawing(value: str, size: float = 1.38 * cm) -> Drawing:
    qr = QrCodeWidget(str(value or ""))
    bounds = qr.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    drawing = Drawing(size, size, transform=[size / width, 0, 0, size / height, 0, 0])
    drawing.add(qr)
    return drawing


def _build_pdf_verification_block(doc_id: str, workflow_context: dict | None, styles):





    rec = dict(workflow_context or {})
    rec.setdefault("DOC_ID", _sanitize_doc_id(doc_id))
    verification_code = compute_eg_verification_hash(rec)
    verification_url = _build_eg_verification_url(doc_id, verification_code)

    doc_style = ParagraphStyle(
        "EGVerifyDoc",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=8.6,
        textColor=colors.HexColor(NAVY),
    )
    label_style = ParagraphStyle(
        "EGVerifyLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.8,
        leading=7.8,
        alignment=1,
        textColor=colors.HexColor(NAVY),
    )
    code_style = ParagraphStyle(
        "EGVerifyCode",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.1,
        leading=7.0,
        alignment=1,
        textColor=colors.HexColor("#475569"),
    )
    small_style = ParagraphStyle(
        "EGVerifySmall",
        parent=styles["Normal"],
        fontSize=6.2,
        leading=7.2,
        textColor=colors.HexColor("#64748B"),
    )

    qr_cell = [
        _qr_drawing(verification_url, 1.48 * cm),
        Paragraph("Scan to verify", label_style),
        Paragraph(f"Code: {html.escape(verification_code)}", code_style),
    ]
    left_cell = [
        Paragraph(f"Document ID: {_sanitize_doc_id(doc_id)}", doc_style),
        Paragraph("Digital confirmation can be verified from the SuperApp workflow record.", small_style),
    ]
    tbl = Table([[left_cell, qr_cell]], colWidths=[13.7 * cm, 3.25 * cm], rowHeights=[2.25 * cm])
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.24, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    return tbl


def _draw_eg_verification_qr(canvas, doc, doc_id: str, workflow_context: dict | None = None):

    if not doc_id:
        return
    canvas.saveState()
    try:
        rec = dict(workflow_context or {})
        rec.setdefault("DOC_ID", _sanitize_doc_id(doc_id))
        verification_code = compute_eg_verification_hash(rec)
        verification_url = _build_eg_verification_url(doc_id, verification_code)

        qr_size = 1.30 * cm
        box_w = 1.72 * cm
        box_h = 1.86 * cm
        x = doc.pagesize[0] - doc.rightMargin - box_w - 0.05 * cm
        y = doc.pagesize[1] - doc.topMargin - box_h - 0.18 * cm

        canvas.setFillColor(colors.white)
        canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas.roundRect(x, y, box_w, box_h, 0.10 * cm, stroke=1, fill=1)

        drawing = _qr_drawing(verification_url, qr_size)
        renderPDF.draw(drawing, canvas, x + (box_w - qr_size) / 2, y + 0.43 * cm)

        canvas.setFont("Helvetica-Bold", 5.4)
        canvas.setFillColor(colors.HexColor(NAVY))
        canvas.drawCentredString(x + box_w / 2, y + 0.25 * cm, "Scan to verify")
        canvas.setFont("Helvetica", 4.5)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawCentredString(x + box_w / 2, y + 0.09 * cm, str(verification_code or "")[:12])
    except Exception:
        pass
    finally:
        canvas.restoreState()


def _draw_footer_with_eg_verification(canvas, doc, username: str, doc_id: str, workflow_context: dict | None = None):
    _draw_footer(canvas, doc, username, doc_id)
    if doc.page == 1:
        _draw_eg_verification_qr(canvas, doc, doc_id, workflow_context)


COLUMN_ALIASES = {
    "POLICY_NO": ["POLICY_NO", "POLICY NO", "POLICY_NUMBER", "POLICY NUMBER", "NO_POLIS", "NO POLIS"],
    "UW_YEAR": ["UW_YEAR", "UW YEAR", "UW_YEARS", "UW YEARS", "TAHUN UNDERWRITING"],
    "INTERMEDIARY_NAME": ["INTERMEDIARY_NAME", "INTERMEDIARY NAME", "SOURCE BUSINESS", "SUMBER BISNIS", "BROKER", "AGENT"],
    "INSURED_NAME": ["INSURED_NAME", "INSURED NAME", "INSURED_NAME_2", "INSURED NAME 2", "NAMA TERTANGGUNG"],
    "GWP_AMT": ["GWP_AMT", "GWP", "GROSS WRITTEN PREMIUM", "PREMI", "NETT PREMI", "NET PREMIUM"],
    "GEP_AMT": ["GEP_AMT", "GEP", "GROSS EARNED PREMIUM", "EARNED PREMIUM"],
    "GROSS_CLAIM": ["GROSS_CLAIM", "GROSS CLAIM", "CLAIM", "KLAIM", "NILAI KLAIM"],
    "COMMISSIONS": ["COMMISSIONS", "COMMISSION", "COMM", "KOMISI"],
    "RI_COST": ["RI_COST", "RI COST"],
    "ERC_AMT": ["ERC_AMT", "ERC", "RI COST", "RI_COST"],
    "RI_RECOVERY": ["RI_RECOVERY", "RI RECOVERY", "RI_REC", "RI REC"],
    "COB": ["COB", "CLASS OF BUSINESS", "CLASS BUSINESS"],
    "LOB": ["LOB", "LINE OF BUSINESS"],
    "TOB": ["TOB", "TYPE OF BUSINESS"],
    "BRANCH": ["BRANCH", "CABANG"],
    "MARKETING_NAME": ["MARKETING_NAME", "MARKETING NAME", "MKT NAME"],
    "MARKETING_GROUP": ["MARKETING_GROUP", "MARKETING GROUP", "MKT GROUP"],
}




def _get_gcp_credentials_info() -> dict:
    try:
        return {k: v for k, v in st.secrets["gcp"].items()}
    except Exception:
        return {}


def _get_exgratia_gspread_client():
    if gspread is None or Credentials is None:
        return None
    info = _get_gcp_credentials_info()
    if not info:
        return None
    creds = Credentials.from_service_account_info(info, scopes=GSHEET_SCOPES)
    return gspread.Client(auth=creds)


def _get_exgratia_spreadsheet():
    client = _get_exgratia_gspread_client()
    if client is None:
        return None
    return client.open("Login Log")


def _excel_col(n: int) -> str:

    out = ""
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out or "A"


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, (np.integer, np.floating)):
        return float(value)
    return str(value)


def _record_text(value) -> str:






    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return str(int(value))
    if isinstance(value, (np.floating, float)):
        try:

            if value.is_integer():
                return str(int(value))
        except Exception:
            pass
        return str(value)
    return str(value)


def _group_digit_string(text: str) -> str:

    text = str(text or "").strip()
    sign = ""
    if text.startswith(("+", "-")):
        sign, text = text[0], text[1:]
    if not text.isdigit():
        return (sign + text).strip()
    parts = []
    while text:
        parts.append(text[-3:])
        text = text[:-3]
    return sign + ".".join(reversed(parts))


def _df_to_json(df: pd.DataFrame) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return "[]"
    return json.dumps(df.to_dict(orient="records"), ensure_ascii=False, default=_json_default)


def _json_to_df(text: str) -> pd.DataFrame:
    try:
        data = json.loads(str(text or "[]"))
        return pd.DataFrame(data if isinstance(data, list) else [])
    except Exception:
        return pd.DataFrame()


def _clean_ovr_context_for_json(ctx: dict | None) -> dict:
    ctx = dict(ctx or {})
    if isinstance(ctx.get("rules_df"), pd.DataFrame):
        ctx["rules_df"] = ctx["rules_df"].to_dict(orient="records")
    return ctx


def _ovr_context_from_json(text: str) -> dict:
    try:
        ctx = json.loads(str(text or "{}"))
        if isinstance(ctx, dict) and isinstance(ctx.get("rules_df"), list):
            ctx["rules_df"] = pd.DataFrame(ctx["rules_df"])
        return ctx if isinstance(ctx, dict) else {}
    except Exception:
        return {}


def _get_user_role(username: str) -> str:

    username = str(username or "").strip()
    for key in ("role", "user_role", "current_role"):
        if st.session_state.get(key):
            return str(st.session_state.get(key)).strip().lower()
    try:
        u_hash = hashlib.md5(username.encode()).hexdigest()
        for path in ("users_hashed.xlsx", "/mnt/data/users_hashed (4).xlsx"):
            try:
                df = pd.read_excel(path, sheet_name="users")
                if {"user_id", "role_name"}.issubset(df.columns):
                    hit = df[df["user_id"].astype(str) == u_hash]
                    if not hit.empty:
                        return str(hit.iloc[0]["role_name"]).strip().lower()
            except Exception:
                continue
    except Exception:
        pass
    return ""




def _read_users_hashed_df() -> pd.DataFrame:

    for path in ("users_hashed.xlsx", "/mnt/data/users_hashed (5).xlsx", "/mnt/data/users_hashed (4).xlsx"):
        try:
            df = pd.read_excel(path, sheet_name="users")
            if "user_id" in df.columns:
                return df
        except Exception:
            continue
    return pd.DataFrame()


def _get_user_report_to(username: str) -> str:

    username = str(username or "").strip()
    if not username:
        return ""
    try:
        u_hash = hashlib.md5(username.encode()).hexdigest()
        df = _read_users_hashed_df()
        if {"user_id", "report_to"}.issubset(df.columns):
            hit = df[df["user_id"].astype(str) == str(u_hash)]
            if not hit.empty:
                value = str(hit.iloc[0].get("report_to", "") or "").strip().lower()
                if value and value not in {"no one", "none", "nan", "-", "n/a"}:
                    return value
    except Exception:
        pass
    return ""


def _initial_claim_reinsurance_status(ri_cost: float = 0.0) -> tuple[str, str, bool]:

    return "pending klaim", "claim", False


def _route_to_claim_or_reinsurance_status(rec: dict) -> tuple[str, str]:

    return "pending klaim", "claim"


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def _identity_tokens(value) -> set[str]:







    text = str(value or "").strip().lower()
    if not text:
        return set()
    tokens = {text}
    if "@" in text:
        local = text.split("@", 1)[0].strip()
        if local:
            tokens.add(local)
    return tokens


def _same_user_identity(left, right) -> bool:
    left_tokens = _identity_tokens(left)
    right_tokens = _identity_tokens(right)
    return bool(left_tokens and right_tokens and left_tokens.intersection(right_tokens))


def _is_record_creator(rec: dict, username: str) -> bool:






    created_by = str((rec or {}).get("CREATED_BY", "") or "").strip().lower()
    login = str(username or "").strip().lower()
    return bool(created_by and login and created_by == login)


def _creator_email_from_created_by(value) -> list[str]:

    text = str(value or "").strip().lower()
    if not text:
        return []
    if "@" in text:
        return _split_email_values(text)
    if re.fullmatch(r"[a-z0-9._%+\-]+", text, flags=re.IGNORECASE):
        return [f"{text}@mnc-insurance.com"]
    return []


def _validate_corresponding_email(value: str) -> tuple[bool, str, str]:

    email = _normalize_email(value)

    if not email:
        return False, "", "Masukkan satu corresponding email."

    if any(separator in email for separator in [",", ";", " "]):
        return False, "", "Hanya boleh memasukkan satu alamat email."

    pattern = r"^[a-z0-9._%+\-]+@mnc-insurance\.com$"
    if not re.fullmatch(pattern, email, flags=re.IGNORECASE):
        return False, "", "Email harus valid dan berakhiran @mnc-insurance.com."

    return True, email, ""


def _split_email_values(value) -> list[str]:

    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_items = []
        for item in value:
            raw_items.extend(_split_email_values(item))
        return raw_items
    text = str(value or "").replace(";", ",")
    out = []
    for part in text.split(","):
        email = _normalize_email(part)
        if email and "@" in email and "." in email.split("@")[-1] and email not in out:
            out.append(email)
    return out


def _get_secret_email_list(key: str) -> list[str]:

    try:
        value = st.secrets["auth"].get(key, "")
    except Exception:
        value = ""
    return _split_email_values(value)


def _get_emails_for_role(role_name: str) -> list[str]:

    role = str(role_name or "").strip().lower()

    if role == "claim-mv":
        return [CLAIM_MV_EMAIL]
    if role == "claim-nonmv":
        return [CLAIM_NONMV_EMAIL]



    if role in {"direktur marketing", "dirmkt", "director marketing"}:
        return _split_email_values(BOD_MARKETING_EMAIL)
    if role in {"direktur teknik", "dirtek", "director teknik", "technical director"}:
        return _split_email_values(BOD_TEKNIK_EMAIL)

    out = []
    try:
        df = _read_users_hashed_df()
        if not df.empty and "role_name" in df.columns:
            email_cols = [
                c for c in df.columns
                if str(c).strip().lower() in {
                    "username", "user", "email", "user_email", "mail", "account", "account_email"
                }
            ]
            if email_cols:
                hits = df[df["role_name"].astype(str).str.strip().str.lower() == role]
                for _, row in hits.iterrows():
                    for c in email_cols:
                        out.extend(_split_email_values(row.get(c, "")))
    except Exception:
        pass

    deduped = []
    for email in out:
        email = _normalize_email(email)
        if email and email not in deduped:
            deduped.append(email)
    return deduped

def _claim_role_for_cob(cob: str) -> str:
    cob_text = str(cob or "").strip().lower()
    return "claim-mv" if cob_text == "mv" else "claim-nonmv"


def _pending_recipients_for_record(rec: dict, status_override: str | None = None) -> list[str]:

    status_l = str(status_override if status_override is not None else rec.get("STATUS", "")).strip().lower()
    recipients = []

    if _is_terminal_status(status_l):
        return []

    if "pending corresponding edit" in status_l or "pending creator edit" in status_l or "send back" in status_l:
        creator_recipients = _creator_email_from_created_by(rec.get("CREATED_BY", ""))
        if creator_recipients:
            recipients.extend(creator_recipients)
        else:
            recipients.extend(_split_email_values(rec.get("CORRESPONDING_EMAIL", "")))
    elif "pending marketing manager" in status_l:
        recipients.extend(_split_email_values(rec.get("MARKETING_MANAGER_EMAIL", "")))
    elif "pending klaim" in status_l or "pending claim" in status_l:
        recipients.extend(_get_emails_for_role(_claim_role_for_cob(rec.get("COB", ""))))
    elif "pending dirmkt" in status_l or "pending direktur marketing" in status_l:
        recipients.extend(_get_emails_for_role("direktur marketing"))
    elif "pending dirtek" in status_l or "pending direktur teknik" in status_l:
        recipients.extend(_get_emails_for_role("direktur teknik"))

    deduped = []
    for email in recipients:
        email = _normalize_email(email)
        if email and email not in deduped:
            deduped.append(email)
    return deduped

def _approved_by_summary(rec: dict) -> str:
    approvers = []
    approval_fields = [
        ("Marketing Manager", "MARKETING_MANAGER_CONFIRMED_BY", "MARKETING_MANAGER_CONFIRMED_AT"),
        ("Klaim", "CLAIM_CONFIRMED_BY", "CLAIM_CONFIRMED_AT"),
        ("Direktur Marketing", "DIR_MARKETING_CONFIRMED_BY", "DIR_MARKETING_CONFIRMED_AT"),
        ("Direktur Teknik", "DIR_TEKNIK_CONFIRMED_BY", "DIR_TEKNIK_CONFIRMED_AT"),
    ]
    for label, by_col, at_col in approval_fields:
        by = str(rec.get(by_col, "") or "").strip()
        at = str(rec.get(at_col, "") or "").strip()
        if by:
            approvers.append(f"{label}: {by}" + (f" at {at}" if at else ""))
    return "; ".join(approvers) if approvers else "-"


def _send_exgratia_pending_email(recipients: list[str], rec: dict, email_kind: str = "pending") -> tuple[bool, str]:

    recipients = [e for e in _split_email_values(recipients) if e]
    if not recipients:
        return False, "Tidak ada recipient email yang valid."

    try:
        sender_email = st.secrets["auth"].get("smtp_user", "")
        app_password = st.secrets["auth"].get("smtp_pass", "")
    except Exception:
        sender_email = ""
        app_password = ""
    if not sender_email or not app_password:
        return False, "SMTP credential belum tersedia di Streamlit secrets."

    doc_id = _sanitize_doc_id(rec.get("DOC_ID", ""))
    approval_url = _build_exgratia_detail_url(doc_id)
    status = str(rec.get("STATUS", "") or "-").strip() or "-"
    proposed_by = str(rec.get("CREATED_BY", "") or "-").strip() or "-"
    approved_by = _approved_by_summary(rec)
    corresponding_email = _normalize_email(rec.get("CORRESPONDING_EMAIL", ""))
    kind = str(email_kind or "pending").strip().lower()
    status_l = status.lower()

    if kind == "approved":
        subject = 'Klaim Approved'
        intro = "Pengajuan Ex-Gratia telah disetujui oleh approver terakhir. Tim klaim dapat menindaklanjuti sesuai prosedur yang berlaku."
        button_text = "Lihat Klaim Approved"
    elif kind == "resubmitted":
        subject = 'Pengajuan Ex-Gratia telah diedit.'
        intro = (
            "Pengajuan Ex-Gratia sudah diperbaiki dan siap ditinjau kembali. "
            "Approval sebelumnya tetap berlaku. Buka pengajuan untuk review."
        )
        button_text = "Tinjau Perbaikan"
    elif kind == "edit_notice":
        subject = 'Pengajuan Ex-Gratia telah diedit.'
        intro = (
            "Pengajuan Ex-Gratia telah diperbarui. Ringkasan perubahan ada di bawah. "
            "Approval sebelumnya tetap berlaku; tidak perlu approval ulang."
        )
        button_text = "Lihat Pembaruan"
    elif "pending corresponding edit" in status_l or "pending creator edit" in status_l or "send back" in status_l:
        subject = 'Action (Revision) Needed'
        intro = "Perbaiki pengajuan sesuai catatan reviewer di bawah, lalu kirim kembali."
        button_text = "Perbaiki Pengajuan"
    else:
        subject = 'Action (Approval) Needed'
        intro = "Pengajuan Ex-Gratia menunggu review. Periksa detail dan berikan keputusan melalui tombol di bawah."
        button_text = "Tinjau Pengajuan"

    detail_rows = [
        ("Document ID", doc_id or "-"),
        ("Status", status),
        ("Diajukan oleh", proposed_by),
        ("Telah disetujui oleh", approved_by),
        ("No. Klaim", rec.get("CLAIM_NO", "-")),
        ("No. Polis", rec.get("POLICY_NO", "-")),
        ("COB", rec.get("COB", "-")),
        ("Tertanggung", rec.get("INSURED_NAME", "-")),
        ("Nilai Ex-Gratia", _format_money_original(rec.get("EXGRATIA_AMOUNT", ""))),
    ]
    insured_group = _ovr_context_from_json(rec.get("OVR_CONTEXT_JSON", "{}")).get("insured_group", [])
    if insured_group:
        detail_rows.append(("Insured Group", "; ".join(_intermediary_names(rec.get("INSURED_NAME", ""), insured_group))))
    send_back_note = str(rec.get("SEND_BACK_NOTE", "") or "").strip()
    if send_back_note and ("pending corresponding edit" in status_l or "pending creator edit" in status_l or kind in {"resubmitted", "edit_notice"}):
        detail_rows.append(("Catatan perbaikan", send_back_note))

    edit_summary = str(rec.get("_EDIT_SUMMARY", "") or "").strip()
    if edit_summary and kind in {"resubmitted", "edit_notice"}:
        detail_rows.append(("Informasi yang diperbarui", edit_summary))
    rows_html = "".join(
        f"<tr><td style='padding:6px 10px;color:#64748b;font-weight:700;border-bottom:1px solid #e5e7eb;width:150px;'>{html.escape(str(k))}</td>"
        f"<td style='padding:6px 10px;color:#0f172a;border-bottom:1px solid #e5e7eb;'>{html.escape(str(v if v is not None else '-'))}</td></tr>"
        for k, v in detail_rows
    )
    body = f"""
<html>
  <body style="font-family:Arial, sans-serif; color:#0f172a; line-height:1.45;">
    <p>{html.escape(intro)}</p>
    <table style="border-collapse:collapse;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;min-width:520px;">
      {rows_html}
    </table>
    <p style="margin-top:18px;">
      <a href="{html.escape(approval_url, quote=True)}" target="_blank"
         style="display:inline-block;padding:11px 18px;border-radius:10px;background:#003366;color:#ffffff;text-decoration:none;font-weight:700;">
        {html.escape(button_text)}
      </a>
    </p>
    <p style="margin-top:14px;color:#64748b;font-size:12px;">Email ini dikirim otomatis dari SuperApp Actuary.</p>
  </body>
</html>
"""
    msg = MIMEMultipart("mixed")
    msg["From"] = sender_email
    msg["To"] = ", ".join(recipients)

    cc_candidates = list(EXGRATIA_ALWAYS_CC_EMAILS)


    if corresponding_email and corresponding_email not in recipients:
        cc_candidates.append(corresponding_email)

    cc_recipients = []
    for email in _split_email_values(cc_candidates):
        if email not in recipients and email not in cc_recipients:
            cc_recipients.append(email)
    if cc_recipients:
        msg["Cc"] = ", ".join(cc_recipients)

    msg["Subject"] = subject
    msg["Reply-To"] = sender_email
    content_part = MIMEMultipart("alternative")
    content_part.attach(MIMEText(body, "html", "utf-8"))
    msg.attach(content_part)

    try:
        pdf_bytes = _build_record_pdf_bytes(rec)
        if pdf_bytes:
            pdf_name = str(rec.get("PDF_FILE_NAME", "") or "").strip()
            if not pdf_name.lower().endswith(".pdf"):
                pdf_name = f"ex_gratia_{doc_id or 'proposal'}.pdf"
            attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
            attachment.add_header("Content-Disposition", "attachment", filename=pdf_name)
            msg.attach(attachment)
    except Exception:
        pass

    last_error = ""
    for attempt in range(1, 4):
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
                server.login(sender_email, app_password)
                refused = server.send_message(
                    msg,
                    from_addr=sender_email,
                    to_addrs=recipients + cc_recipients,
                )
                if refused:
                    raise RuntimeError(f"SMTP refused recipient(s): {refused}")
            return True, f"Email sent to {', '.join(recipients)}."
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < 3:
                time.sleep(0.8 * attempt)

    return False, f"Email gagal setelah 3 percobaan. {last_error}"

def _notify_pending_exgratia_if_needed(rec: dict, status_override: str | None = None) -> tuple[bool, str]:

    try:
        rec = dict(rec or {})
        if status_override is not None:
            rec["STATUS"] = status_override
        if str(rec.get("STATUS", "")).strip().lower() == "approved":
            recipients = _get_emails_for_role(_claim_role_for_cob(rec.get("COB", "")))
            return _send_exgratia_pending_email(recipients, rec, email_kind="approved")
        recipients = _pending_recipients_for_record(rec, rec.get("STATUS", ""))
        if not recipients:
            return False, "Status ini tidak memiliki pending recipient."
        return _send_exgratia_pending_email(recipients, rec)
    except Exception as exc:
        return False, f"Notification error: {type(exc).__name__}: {exc}"


def _reviewer_email_for_stage(rec: dict, stage: str, reviewer_actor: str = "") -> list[str]:

    actor_emails = _split_email_values(reviewer_actor)
    if actor_emails:
        return actor_emails

    stage_l = str(stage or "").strip().lower()
    if stage_l == "marketing_manager":
        return _split_email_values(rec.get("MARKETING_MANAGER_EMAIL", ""))
    if stage_l == "claim":
        return _get_emails_for_role(_claim_role_for_cob(rec.get("COB", "")))
    if stage_l == "dirmkt":
        return _get_emails_for_role("direktur marketing")
    if stage_l == "dirtek":
        return _get_emails_for_role("direktur teknik")
    return []


def _previous_approved_reviewer_emails(rec: dict, exclude: list[str] | None = None) -> list[str]:

    exclude_set = {_normalize_email(x) for x in (exclude or []) if _normalize_email(x)}
    recipients = []

    def add(values):
        for email in _split_email_values(values):
            email = _normalize_email(email)
            if email and email not in exclude_set and email not in recipients:
                recipients.append(email)

    for field in ("MARKETING_MANAGER_CONFIRMED_BY", "CLAIM_CONFIRMED_BY", "DIR_MARKETING_CONFIRMED_BY", "DIR_TEKNIK_CONFIRMED_BY"):
        actor = str(rec.get(field, "") or "").strip()
        if actor:
            add(_creator_email_from_created_by(actor))

    return recipients


def _edit_change_summary(rec: dict, updates: dict) -> tuple[list[str], str]:

    labels = {
        "CLAIM_NO": "No. Klaim",
        "LOSS_DATE": "Tanggal Kejadian",
        "CLAIM_AMOUNT": "Nilai Klaim",
        "EXGRATIA_AMOUNT": "Nilai Ex-Gratia",
        "MNC_SHARE": "Share MNC",
        "LOSS_CAUSE": "Penyebab Kerugian",
        "EXGRATIA_REASON": "Alasan Ex-Gratia",
        "FUTURE_BUSINESS": "Potensi Bisnis",
        "OVR_CONTEXT_JSON": "OVR / Proxy Intermediaries / Insured Group",
    }
    changed = []
    for key, label in labels.items():
        if key not in updates:
            continue
        before = _record_text(rec.get(key, "")).strip()
        after = _record_text(updates.get(key, "")).strip()
        if before != after:
            changed.append(label)
    return changed, ", ".join(changed)

def _is_terminal_status(status: str) -> bool:
    low = str(status or "").strip().lower()
    return any(x in low for x in ["approved", "declined", "canceled", "cancelled", "dibatalkan"])

def _policy_ri_cost(df: pd.DataFrame, policy_no: str) -> float:
    rows = _find_policy_rows(df, policy_no)
    if rows.empty:
        return 0.0
    ri_col = _resolve_col(rows, "RI_COST") or _resolve_col(rows, "ERC_AMT")
    if not ri_col:
        return 0.0
    return float(pd.to_numeric(rows[ri_col], errors="coerce").fillna(0).sum())


def _workflow_initial_status(ri_cost: float) -> tuple[str, str, bool]:
    status, stage, needs_ri = _initial_claim_reinsurance_status(ri_cost)
    return status, stage, needs_ri



def _get_or_create_exgratia_record_sheet():
    spreadsheet = _get_exgratia_spreadsheet()
    if spreadsheet is None:
        return None
    try:
        sheet = spreadsheet.worksheet(EXGRATIA_RECORD_SHEET)
    except Exception:
        sheet = spreadsheet.add_worksheet(
            title=EXGRATIA_RECORD_SHEET,
            rows=1000,
            cols=len(EXGRATIA_RECORD_HEADERS),
        )
    try:
        current_header = [str(x).strip() for x in sheet.row_values(1)]
        if not current_header:
            sheet.update(f"A1:{_excel_col(len(EXGRATIA_RECORD_HEADERS))}1", [EXGRATIA_RECORD_HEADERS])
        else:


            merged_header = list(current_header)
            changed = False
            for h in EXGRATIA_RECORD_HEADERS:
                if h not in merged_header:
                    merged_header.append(h)
                    changed = True
            if changed:
                sheet.update(f"A1:{_excel_col(len(merged_header))}1", [merged_header])
    except Exception:
        pass
    return sheet


def _count_ovr_rules_gt_zero(ovr_context: dict | None) -> int:
    if not ovr_context:
        return 0
    if ovr_context.get("mode") == "uniform":
        return 1 if _safe_to_float(ovr_context.get("uniform_pct", 0), 0) > 0 else 0
    rules_df = ovr_context.get("rules_df")
    if isinstance(rules_df, pd.DataFrame) and "OVR_PCT_INPUT" in rules_df.columns:
        return int((pd.to_numeric(rules_df["OVR_PCT_INPUT"], errors="coerce").fillna(0) > 0).sum())
    return 0


def _records_to_frame(values: list[list[str]]) -> pd.DataFrame:
    if not values or len(values) <= 1:
        return pd.DataFrame(columns=EXGRATIA_RECORD_HEADERS)
    header = [str(x).strip() for x in values[0]]
    rows = values[1:]
    data = []
    for row in rows:
        if not any(str(x).strip() for x in row):
            continue
        rec = {h: (row[i] if i < len(row) else "") for i, h in enumerate(header)}
        for h in EXGRATIA_RECORD_HEADERS:
            rec.setdefault(h, "")
        data.append(rec)
    return pd.DataFrame(data)


def _normalize_legacy_reinsurance_workflow(df: pd.DataFrame) -> pd.DataFrame:

    if not isinstance(df, pd.DataFrame) or df.empty or "STATUS" not in df.columns:
        return df

    out = df.copy()
    status = out["STATUS"].astype("string").fillna("").str.strip().str.lower()
    claim_done = (
        out.get("CLAIM_CONFIRMED_BY", pd.Series([""] * len(out), index=out.index))
        .astype("string")
        .fillna("")
        .str.strip()
        .ne("")
    )

    combined_mask = status.str.contains("pending klaim and reinsurance", regex=False, na=False)
    reinsurance_mask = status.str.contains("pending reinsurance", regex=False, na=False)

    out.loc[combined_mask, "STATUS"] = "pending klaim"
    if "CURRENT_STAGE" in out.columns:
        out.loc[combined_mask, "CURRENT_STAGE"] = "claim"

    out.loc[reinsurance_mask & claim_done, "STATUS"] = "pending dirmkt"
    out.loc[reinsurance_mask & ~claim_done, "STATUS"] = "pending klaim"
    if "CURRENT_STAGE" in out.columns:
        out.loc[reinsurance_mask & claim_done, "CURRENT_STAGE"] = "dirmkt"
        out.loc[reinsurance_mask & ~claim_done, "CURRENT_STAGE"] = "claim"

    if "NEEDS_REINSURANCE" in out.columns:
        out["NEEDS_REINSURANCE"] = "FALSE"

    return out


def load_exgratia_records() -> pd.DataFrame:
    try:
        sheet = _get_or_create_exgratia_record_sheet()
        if sheet is None:
            return pd.DataFrame(columns=EXGRATIA_RECORD_HEADERS)
        return _normalize_legacy_reinsurance_workflow(
            _records_to_frame(sheet.get_all_values())
        )
    except Exception:
        return pd.DataFrame(columns=EXGRATIA_RECORD_HEADERS)




def _find_record_row_number(sheet, doc_id: str) -> int | None:
    values = sheet.get_all_values()
    if not values:
        return None
    header = [str(x).strip() for x in values[0]]
    try:
        doc_idx = header.index("DOC_ID")
    except ValueError:
        return None
    target = _sanitize_doc_id(doc_id)
    for row_no, row in enumerate(values[1:], start=2):
        if doc_idx < len(row) and _sanitize_doc_id(row[doc_idx]) == target:
            return row_no
    return None


def _update_exgratia_record(doc_id: str, updates: dict) -> tuple[bool, str]:
    try:
        sheet = _get_or_create_exgratia_record_sheet()
        if sheet is None:
            return False, "Google Sheet client tidak tersedia."
        row_no = _find_record_row_number(sheet, doc_id)
        if not row_no:
            return False, "Record tidak ditemukan."
        header = sheet.row_values(1)
        header_map = {str(h).strip(): i + 1 for i, h in enumerate(header)}
        now = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")
        updates = dict(updates or {})
        updates.setdefault("LAST_UPDATED_AT", now)
        batch = []
        for key, val in updates.items():
            if key not in header_map:
                continue
            batch.append({"range": f"{_excel_col(header_map[key])}{row_no}", "values": [[_record_text(val)]]})
        if batch:


            sheet.batch_update(batch, value_input_option="RAW")
        return True, "Updated."
    except Exception as e:
        return False, str(e)


def record_exgratia_workflow_submission(
    form_data: dict,
    doc_id: str,
    username: str,
    ovr_context: dict | None,
    pdf_file_name: str,
    intermediary_summary: pd.DataFrame,
    insured_summary: pd.DataFrame,
    display_unit: str,
    ri_cost: float,
) -> tuple[bool, str]:

    try:
        corr_ok, corr_email, corr_error = _validate_corresponding_email(form_data.get("corresponding_email", ""))
        if not corr_ok:
            return False, f"Corresponding Email wajib diisi. {corr_error}"

        sheet = _get_or_create_exgratia_record_sheet()
        if sheet is None:
            return False, "Google Sheet client tidak tersedia."
        loss_date = form_data.get("loss_date", "")
        if isinstance(loss_date, (datetime, date)):
            loss_date = loss_date.strftime("Y-%m-%d") if False else loss_date.strftime("%Y-%m-%d")
        ovr_context = ovr_context or {}
        status, current_stage, needs_ri = _workflow_initial_status(0.0)
        marketing_manager_email = _get_user_report_to(username)
        if marketing_manager_email:
            status, current_stage = "pending marketing manager", "marketing_manager"
        now = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")
        row_dict = {
            "DOC_ID": _sanitize_doc_id(doc_id),
            "CREATED_AT": now,
            "CREATED_BY": str(username or ""),
            "STATUS": status,
            "CURRENT_STAGE": current_stage,
            "CLAIM_NO": str(form_data.get("claim_no", "")),
            "POLICY_NO": str(form_data.get("policy_no", "")),
            "POLICY_UW_YEAR": _record_text(form_data.get("policy_uw_year", "")),
            "COB": str(form_data.get("cob", "")),
            "SOURCE_BUSINESS": str(form_data.get("source_business", "")),
            "INSURED_NAME": str(form_data.get("insured_name", "")),
            "LOSS_DATE": str(loss_date or ""),
            "CLAIM_AMOUNT": _record_text(form_data.get("claim_amount", "")),
            "EXGRATIA_AMOUNT": _record_text(form_data.get("exgratia_amount", "")),
            "MNC_SHARE": str(form_data.get("mnc_share", "")),
            "LOSS_CAUSE": _limit_narrative_text(form_data.get("loss_cause", "")),
            "EXGRATIA_REASON": _limit_narrative_text(form_data.get("exgratia_reason", "")),
            "FUTURE_BUSINESS": _limit_narrative_text(form_data.get("future_business", "")),
            "CORRESPONDING_EMAIL": corr_email,
            "RI_COST": "0",
            "NEEDS_REINSURANCE": "FALSE",
            "OVR_MODE": str(ovr_context.get("mode_label") or ovr_context.get("mode") or ""),
            "OVR_CATEGORY": ", ".join(ovr_context.get("dims") or []),
            "OVR_UNIFORM_PCT": _record_text(ovr_context.get("uniform_pct", "")),
            "OVR_RULES_GT_0": _record_text(_count_ovr_rules_gt_zero(ovr_context)),
            "DISPLAY_UNIT": display_unit,
            "INTERMEDIARY_SUMMARY_JSON": _df_to_json(intermediary_summary),
            "INSURED_SUMMARY_JSON": _df_to_json(insured_summary),
            "OVR_CONTEXT_JSON": json.dumps(_clean_ovr_context_for_json(ovr_context), ensure_ascii=False, default=_json_default),
            "CLAIM_NOTE": "",
            "CLAIM_CONFIRMED_BY": "",
            "CLAIM_CONFIRMED_AT": "",
            "REINSURANCE_NOTE": "",
            "REINSURANCE_CONFIRMED_BY": "",
            "REINSURANCE_CONFIRMED_AT": "",
            "MARKETING_MANAGER_EMAIL": marketing_manager_email,
            "MARKETING_MANAGER_NOTE": "",
            "MARKETING_MANAGER_CONFIRMED_BY": "",
            "MARKETING_MANAGER_CONFIRMED_AT": "",
            "DIR_MARKETING_NOTE": "",
            "DIR_MARKETING_CONFIRMED_BY": "",
            "DIR_MARKETING_CONFIRMED_AT": "",
            "DIR_TEKNIK_NOTE": "",
            "DIR_TEKNIK_CONFIRMED_BY": "",
            "DIR_TEKNIK_CONFIRMED_AT": "",
            "DIR_UTAMA_CONFIRMED_BY": "",
            "DIR_UTAMA_CONFIRMED_AT": "",
            "SEND_BACK_BY": "",
            "SEND_BACK_AT": "",
            "SEND_BACK_NOTE": "",
            "SEND_BACK_STAGE": "",
            "SEND_BACK_RETURN_STATUS": "",
            "SEND_BACK_TO": "",
            "SEND_BACK_RESOLVED_BY": "",
            "SEND_BACK_RESOLVED_AT": "",
            "WORKFLOW_NOTES_JSON": _append_workflow_note("[]", username, "Submitted", "marketing", "", now),
            "DECLINED_BY": "",
            "DECLINED_AT": "",
            "DECLINE_NOTE": "",
            "CANCELED_BY": "",
            "CANCELED_AT": "",
            "CANCEL_NOTE": "",
            "LAST_UPDATED_AT": now,
            "LAST_UPDATED_BY": str(username or ""),
            "PDF_FILE_NAME": str(pdf_file_name or ""),
        }
        sheet_header = [str(h).strip() for h in sheet.row_values(1)] or EXGRATIA_RECORD_HEADERS
        row = [_record_text(row_dict.get(h, "")) for h in sheet_header]


        sheet.append_row(row, value_input_option="RAW")
        email_ok, email_msg = _notify_pending_exgratia_if_needed(row_dict)
        st.session_state["eg_last_notification"] = {"ok": email_ok, "message": email_msg}
        return True, status
    except Exception as e:
        return False, str(e)


def record_exgratia_submission(form_data: dict, doc_id: str, username: str, ovr_context: dict | None, pdf_file_name: str) -> tuple[bool, str]:

    return record_exgratia_workflow_submission(
        form_data, doc_id, username, ovr_context, pdf_file_name,
        pd.DataFrame(), pd.DataFrame(), form_data.get("display_unit", "in IDR Mio"),
        _safe_to_float(form_data.get("ri_cost", 0), 0),
    )





def _norm_text(x) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass
    return str(x).strip()


def _norm_key(x) -> str:

    text = _norm_text(x)
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text).replace("\u00A0", " ").strip()


    if re.fullmatch(r"[+-]?\d+\.0+", text):
        text = text.split(".", 1)[0]


    return "".join(ch for ch in text.upper() if ch.isalnum())


def _resolve_col(df: pd.DataFrame, canonical: str) -> str | None:
    if df is None or df.empty:
        return None
    cols_by_upper = {str(c).strip().upper(): c for c in df.columns}
    for alias in COLUMN_ALIASES.get(canonical, [canonical]):
        key = str(alias).strip().upper()
        if key in cols_by_upper:
            return cols_by_upper[key]

    cols_by_key = {_norm_key(c): c for c in df.columns}
    for alias in COLUMN_ALIASES.get(canonical, [canonical]):
        key = _norm_key(alias)
        if key in cols_by_key:
            return cols_by_key[key]
    return None


def _safe_to_float(x, default=0.0) -> float:












    try:
        if x is None:
            return default


        if isinstance(x, (int, float, np.integer, np.floating)):
            if pd.isna(x):
                return default
            return float(x)

        if pd.isna(x):
            return default

        text = unicodedata.normalize("NFKC", str(x))
        text = text.replace("\u00a0", " ").strip()
        if not text:
            return default

        negative = text.startswith("(") and text.endswith(")")
        text = re.sub(r"(?i)\b(?:rp|idr)\b", "", text)
        text = text.replace("%", "").replace(" ", "")
        text = text.strip("()")


        text = re.sub(r"[^0-9,.(\)+\-]", "", text)
        if not text or text in {"+", "-", ".", ","}:
            return default

        comma_count = text.count(",")
        dot_count = text.count(".")

        if comma_count and dot_count:


            decimal_sep = "," if text.rfind(",") > text.rfind(".") else "."
            thousands_sep = "." if decimal_sep == "," else ","
            text = text.replace(thousands_sep, "")
            if decimal_sep == ",":
                text = text.replace(",", ".")
        elif comma_count:
            parts = text.split(",")
            if comma_count > 1 or (len(parts) == 2 and len(parts[1]) == 3):
                text = "".join(parts)
            else:
                text = text.replace(",", ".")
        elif dot_count:
            parts = text.split(".")
            if dot_count > 1 or (len(parts) == 2 and len(parts[1]) == 3):
                text = "".join(parts)

        value = float(text)
        return -abs(value) if negative else value
    except Exception:
        return default


def load_risk_profile_data(paths: tuple[str, ...]) -> pd.DataFrame:

    loaded = []
    errors = []

    for path in tuple(paths):
        if not os.path.exists(path):
            errors.append(f"{path}: file tidak ditemukan")
            continue

        try:
            if str(path).lower().endswith(".xlsx"):
                part = pd.read_excel(path)
            else:
                errors.append(f"{path}: format tidak didukung")
                continue
            loaded.append(part)
        except Exception as exc:
            errors.append(f"{path}: {exc}")



    if len(loaded) != len(tuple(paths)):
        raise FileNotFoundError(
            f"Risk Profile tidak termuat lengkap ({len(loaded)}/{len(tuple(paths))} file). "
            + " | ".join(errors)
        )

    df = pd.concat(loaded, ignore_index=True, copy=False)
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = _optimize_df_memory(df)

    policy_col = _resolve_col(df, "POLICY_NO")
    if policy_col:
        keys = df[policy_col].astype("string").map(_norm_key)
        try:
            df["__EG_POLICY_KEY__"] = keys.astype("category")
        except Exception:
            df["__EG_POLICY_KEY__"] = keys

    return df


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
            if nunique and nunique <= 5000 and (nunique / n) <= 0.45:
                out[col] = out[col].astype("category")
        except Exception:
            pass
    return out


def _find_policy_rows(df: pd.DataFrame, policy_no: str) -> pd.DataFrame:
    policy_col = _resolve_col(df, "POLICY_NO")
    if not policy_col:
        return pd.DataFrame()

    key = _norm_key(policy_no)
    if not key:
        return pd.DataFrame()

    if "__EG_POLICY_KEY__" in df.columns:
        normalized = df["__EG_POLICY_KEY__"]
    else:
        normalized = df[policy_col].astype("string").map(_norm_key)

    exact = df.loc[normalized.eq(key)]
    if not exact.empty:
        return exact.copy()


    contains = normalized.astype("string").str.contains(key, regex=False, na=False)
    candidate_keys = normalized[contains].astype("string").dropna().drop_duplicates()
    if len(candidate_keys) == 1:
        return df.loc[normalized.eq(candidate_keys.iloc[0])].copy()

    return pd.DataFrame(columns=df.columns)


def _first_nonblank(series: pd.Series, default="") -> str:
    try:
        for v in series.dropna().astype(str).tolist():
            if v.strip() and v.strip().lower() not in ("nan", "none", "(blank)"):
                return v.strip()
    except Exception:
        pass
    return default


def _policy_uw_year(df: pd.DataFrame, policy_no: str) -> int | None:






    rows = _find_policy_rows(df, policy_no)
    if rows.empty:
        return None
    uw_col = _resolve_col(rows, "UW_YEAR")
    if not uw_col:
        return None
    years = (
        pd.to_numeric(rows[uw_col], errors="coerce")
        .dropna()
        .astype(int)
        .drop_duplicates()
        .tolist()
    )
    return int(max(years)) if years else None


def _policy_metadata(df: pd.DataFrame, policy_no: str) -> dict:
    rows = _find_policy_rows(df, policy_no)
    if rows.empty:
        return {"found": False, "source_business": "", "insured_name": "", "cob": "", "uw_year": None}
    int_col = _resolve_col(rows, "INTERMEDIARY_NAME")
    ins_col = _resolve_col(rows, "INSURED_NAME")
    cob_col = _resolve_col(rows, "COB")
    return {
        "found": True,
        "source_business": _first_nonblank(rows[int_col]) if int_col else "",
        "insured_name": _first_nonblank(rows[ins_col]) if ins_col else "",
        "cob": _first_nonblank(rows[cob_col]) if cob_col else "",
        "uw_year": _policy_uw_year(df, policy_no),
        "rows": rows,
    }


def _make_ovr_key(frame: pd.DataFrame, dims: list[str]) -> pd.Series:
    key = None
    for col in dims:
        part = frame[col].astype("string").fillna("<NA>").str.strip()
        key = part if key is None else key.str.cat(part, sep="\x1f")
    return key if key is not None else pd.Series([], dtype="string")


def apply_ovr_to_df(df: pd.DataFrame, mode: str, uniform_pct: float = 0.0, dims: list[str] | None = None, rules_df: pd.DataFrame | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    gwp_col = _resolve_col(df, "GWP_AMT")
    if not gwp_col:
        out = df.copy()
        out["OVR_AMT"] = 0.0
        out["OVR_PCT"] = 0.0
        return out
    out = df.copy()
    gwp = pd.to_numeric(out[gwp_col], errors="coerce").fillna(0.0)

    if mode == "rules" and dims and rules_df is not None and not rules_df.empty and "OVR_PCT_INPUT" in rules_df.columns:
        valid_dims = [d for d in dims if d in out.columns and d in rules_df.columns]
        if valid_dims:
            rules = rules_df[valid_dims + ["OVR_PCT_INPUT"]].copy()
            rules["OVR_PCT_INPUT"] = pd.to_numeric(rules["OVR_PCT_INPUT"], errors="coerce")
            rules = rules.dropna(subset=["OVR_PCT_INPUT"]).drop_duplicates(subset=valid_dims, keep="last")
            if not rules.empty:
                rules["__ovr_key"] = _make_ovr_key(rules, valid_dims)
                rule_map = pd.Series((rules["OVR_PCT_INPUT"] / 100.0).to_numpy(), index=rules["__ovr_key"])
                out_key = _make_ovr_key(out, valid_dims)
                out["OVR_PCT"] = out_key.map(rule_map).fillna(0.0).astype(float)
                out["OVR_AMT"] = gwp.to_numpy() * out["OVR_PCT"].to_numpy()
                return out
    pct = _safe_to_float(uniform_pct, 0.0) / 100.0
    out["OVR_PCT"] = pct
    out["OVR_AMT"] = gwp.to_numpy() * pct
    return out


def _intermediary_names(primary: str, proxies=None) -> list[str]:

    if not isinstance(proxies, (list, tuple, set)):
        proxies = []
    names, seen = [], set()
    for value in [primary, *proxies]:
        if value is None or pd.isna(value):
            continue
        name = str(value).strip()
        key = name.lower()
        if name and key not in seen:
            names.append(name)
            seen.add(key)
    return names


def _entity_members_mask(values: pd.Series, primary: str, proxies=None) -> pd.Series:
    members = {name.lower() for name in _intermediary_names(primary, proxies)}
    return values.astype("string").str.strip().str.lower().isin(members)


def make_entity_performance_summary(
    df: pd.DataFrame,
    entity_col: str,
    entity_value: str,
    last_n_years: int | None = None,
    display_unit: str = "in IDR Mio",
    start_year: int = 2023,
    target_uw_year: int | None = None,
    exgratia_amount: float = 0.0,
    proxy_entities: list[str] | None = None,
) -> pd.DataFrame:





    empty = pd.DataFrame(columns=EXGRATIA_PERFORMANCE_COLUMNS)
    if df is None or df.empty or not entity_col or entity_col not in df.columns:
        return empty

    uw_col = _resolve_col(df, "UW_YEAR")
    gwp_col = _resolve_col(df, "GWP_AMT")
    gep_col = _resolve_col(df, "GEP_AMT")
    claim_col = _resolve_col(df, "GROSS_CLAIM")
    comm_col = _resolve_col(df, "COMMISSIONS")
    ri_cost_col = _resolve_col(df, "ERC_AMT") or _resolve_col(df, "RI_COST")
    ri_rec_col = _resolve_col(df, "RI_RECOVERY")
    if not uw_col or not gwp_col or not claim_col:
        return empty



    tmp = df[_entity_members_mask(df[entity_col], entity_value, proxy_entities)].copy()
    if tmp.empty:
        return empty

    tmp[uw_col] = pd.to_numeric(tmp[uw_col], errors="coerce")
    tmp = tmp[tmp[uw_col].notna()].copy()
    if tmp.empty:
        return empty

    if start_year is not None:
        tmp = tmp[tmp[uw_col].astype(int) >= int(start_year)].copy()
        if tmp.empty:
            return empty

    for c in [gwp_col, gep_col, claim_col, comm_col, ri_cost_col, ri_rec_col, "OVR_AMT"]:
        if c and c in tmp.columns:
            tmp[c] = pd.to_numeric(tmp[c], errors="coerce").fillna(0.0)

    if gep_col is None or gep_col not in tmp.columns:
        tmp["__GEP_FALLBACK__"] = pd.to_numeric(tmp[gwp_col], errors="coerce").fillna(0.0)
        gep_col = "__GEP_FALLBACK__"
    if not comm_col:
        tmp["__COMM__"] = 0.0
        comm_col = "__COMM__"
    if not ri_cost_col:
        tmp["__RI_COST__"] = 0.0
        ri_cost_col = "__RI_COST__"
    if not ri_rec_col:
        tmp["__RI_REC__"] = 0.0
        ri_rec_col = "__RI_REC__"
    if "OVR_AMT" not in tmp.columns:
        tmp["OVR_AMT"] = 0.0

    years_sorted = sorted(
        pd.to_numeric(tmp[uw_col], errors="coerce")
        .dropna().astype(int).unique().tolist()
    )
    if last_n_years and len(years_sorted) > last_n_years:
        keep_years = years_sorted[-last_n_years:]
        tmp = tmp[tmp[uw_col].astype(int).isin(keep_years)]

    grouped = tmp.groupby(uw_col, as_index=False).agg(
        GWP=(gwp_col, "sum"),
        GEP=(gep_col, "sum"),
        GROSS_CLAIM=(claim_col, "sum"),
        COMM=(comm_col, "sum"),
        RI_COST=(ri_cost_col, "sum"),
        RI_REC=(ri_rec_col, "sum"),
        OVR_AMT=("OVR_AMT", "sum"),
    )
    grouped[uw_col] = grouped[uw_col].astype(int)
    grouped = grouped.sort_values(uw_col).reset_index(drop=True)

    gep = grouped["GEP"].replace(0, np.nan)
    gwp = grouped["GWP"].replace(0, np.nan)

    gross_claim_existing = grouped["GROSS_CLAIM"].astype(float)
    gross_claim_exgratia = gross_claim_existing.copy()
    target_year = int(target_uw_year) if target_uw_year is not None else None
    exg = max(0.0, _safe_to_float(exgratia_amount, 0.0))
    if target_year is not None and exg:
        target_mask = grouped[uw_col].astype(int).eq(target_year)
        gross_claim_exgratia.loc[target_mask] = (
            gross_claim_exgratia.loc[target_mask] + exg
        )

    lr_existing = (gross_claim_existing / gep).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    lr_exgratia = (gross_claim_exgratia / gep).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    comm_ratio = (grouped["COMM"] / gwp).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    ri_cost_ratio = (grouped["RI_COST"] / gep).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    ri_rec_ratio = (grouped["RI_REC"] / gep).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    ovr_ratio = (grouped["OVR_AMT"] / gwp).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    non_claim_cor = comm_ratio + ri_cost_ratio - ri_rec_ratio + 0.15 + ovr_ratio

    cor_existing = lr_existing + non_claim_cor
    cor_exgratia = lr_exgratia + non_claim_cor

    factor = DISPLAY_UNIT_CONFIG.get(
        display_unit, DISPLAY_UNIT_CONFIG["in IDR Mio"]
    )["factor"]
    out = pd.DataFrame({
        "UW YEARS": grouped[uw_col].astype(int),
        "GWP": grouped["GWP"] / factor,
        "GROSS CLAIM": gross_claim_existing / factor,
        "LOSS RATIO EXISTING": lr_existing * 100,
        "LOSS RATIO + EX-GRATIA": lr_exgratia * 100,
        "COMBINED RATIO EXISTING": cor_existing * 100,
        "COMBINED RATIO + EX-GRATIA": cor_exgratia * 100,
    })
    return out[EXGRATIA_PERFORMANCE_COLUMNS].reset_index(drop=True)


def _normalise_performance_summary_schema(summary_df: pd.DataFrame) -> pd.DataFrame:

    df = summary_df.copy() if isinstance(summary_df, pd.DataFrame) else pd.DataFrame()
    if df.empty:
        return pd.DataFrame(columns=EXGRATIA_PERFORMANCE_COLUMNS)

    if "LOSS RATIO EXISTING" not in df.columns and "LOSS RATIO" in df.columns:
        df["LOSS RATIO EXISTING"] = df["LOSS RATIO"]
    if "LOSS RATIO + EX-GRATIA" not in df.columns and "LOSS RATIO EXISTING" in df.columns:
        df["LOSS RATIO + EX-GRATIA"] = df["LOSS RATIO EXISTING"]
    if "COMBINED RATIO EXISTING" not in df.columns and "COMBINED RATIO" in df.columns:
        df["COMBINED RATIO EXISTING"] = df["COMBINED RATIO"]
    if "COMBINED RATIO + EX-GRATIA" not in df.columns and "COMBINED RATIO EXISTING" in df.columns:
        df["COMBINED RATIO + EX-GRATIA"] = df["COMBINED RATIO EXISTING"]

    for c in EXGRATIA_PERFORMANCE_COLUMNS:
        if c not in df.columns:
            df[c] = np.nan
    return df[EXGRATIA_PERFORMANCE_COLUMNS].copy()





def _format_money(x, display_unit: str) -> str:
    if pd.isna(x):
        return ""
    if display_unit == "Original Number":
        return "Rp. " + f"{int(round(float(x))):,}".replace(",", ".")
    return f"{int(round(float(x))):,}".replace(",", ".")


def _format_money_original(x) -> str:





    text = _record_text(x).strip()
    if not text:
        return ""

    if re.match(r"(?i)^(rp\.?|idr)\s*", text):
        return text



    m = re.fullmatch(r"([+-]?\d+)\.0+", text)
    if m:
        text = m.group(1)

    if re.fullmatch(r"[+-]?\d+", text):
        text = _group_digit_string(text)

    return "Rp. " + text


def _format_pct(x) -> str:
    if x is None or pd.isna(x):
        return ""
    return f"{float(x):.1f}%"


def _sanitize_doc_id(doc_id: str) -> str:
    return str(doc_id or "").strip().upper().replace(" ", "")


def generate_unique_document_id(prefix: str = "EG") -> str:
    date_part = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%y%m%d")
    return f"{prefix}-{date_part}-{uuid.uuid4().hex[:8].upper()}"


def _list_to_lines(text: str) -> str:





    clean_text = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not clean_text:
        return ""
    return html.escape(clean_text).replace("\n", "<br/>")


def _p(text, style):
    return Paragraph(str(text or ""), style)


def _limit_narrative_text(value, max_chars: int = EXGRATIA_MAX_NARRATIVE_CHARS) -> str:

    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return text[: max(0, int(max_chars or 0))]


def _parse_workflow_notes_json(value) -> list[dict]:
    try:
        data = json.loads(str(value or "[]"))
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
    except Exception:
        return []


def _append_workflow_note(existing, actor: str, action: str, stage: str, note: str, at: str, is_red: bool = False) -> str:
    items = _parse_workflow_notes_json(existing)
    items.append({
        "at": str(at or ""),
        "actor": str(actor or ""),
        "action": str(action or ""),
        "is_red": bool(is_red),
        "stage": str(stage or ""),
        "note": str(note or "").replace("\r\n", "\n").replace("\r", "\n").strip(),
    })
    return json.dumps(items, ensure_ascii=False, default=_json_default)


def _workflow_notes_for_display(rec: dict) -> list[dict]:

    items = [dict(item) for item in _parse_workflow_notes_json(rec.get("WORKFLOW_NOTES_JSON", "[]"))]
    def add_legacy(action, stage, note_key, actor_key, at_key):
        note = str(rec.get(note_key, "") or "").strip()
        actor = str(rec.get(actor_key, "") or "").strip()
        at = str(rec.get(at_key, "") or "").strip()
        if not note:
            return

        if any(str(i.get("note", "") or "").strip() == note
               and str(i.get("actor", "") or "").strip() == actor
               and str(i.get("at", "") or "").strip() == at for i in items):
            return
        items.append(dict(action=action, stage=stage, note=note, actor=actor, at=at))

    for stage, prefix in (
        ("Marketing Manager", "MARKETING_MANAGER"), ("Claim", "CLAIM"),
        ("Reinsurance", "REINSURANCE"), ("Direktur Marketing", "DIR_MARKETING"),
        ("Direktur Teknik", "DIR_TEKNIK"), ("Direktur Utama", "DIR_UTAMA"),
    ):
        add_legacy("Review", stage, prefix + "_NOTE", prefix + "_CONFIRMED_BY", prefix + "_CONFIRMED_AT")
    add_legacy("Send Back", str(rec.get("SEND_BACK_STAGE", "") or ""), "SEND_BACK_NOTE", "SEND_BACK_BY", "SEND_BACK_AT")
    add_legacy("Decline", "", "DECLINE_NOTE", "DECLINED_BY", "DECLINED_AT")
    add_legacy("Cancel", "", "CANCEL_NOTE", "CANCELED_BY", "CANCELED_AT")

    return sorted(items, key=lambda item: str(item.get("at", "") or ""))


def _build_workflow_notes_pdf_elements(rec: dict, styles) -> list:

    items = _workflow_notes_for_display(rec)
    if not items:
        return []
    heading = ParagraphStyle("EGNoteMetadata", parent=styles["Normal"], fontName="Helvetica-Bold",
                             fontSize=8.5, leading=11, spaceBefore=9, spaceAfter=4, keepWithNext=True)
    body = ParagraphStyle("EGNoteBody", parent=styles["Normal"], fontSize=8.5, leading=12, spaceAfter=5)
    red_heading = ParagraphStyle("EGRedNoteMetadata", parent=heading, textColor=colors.HexColor("#B91C1C"), backColor=colors.HexColor("#FEE2E2"), borderPadding=5)
    red_body = ParagraphStyle("EGRedNoteBody", parent=body, textColor=colors.HexColor("#991B1B"), backColor=colors.HexColor("#FFF1F2"), borderPadding=5)
    elements = [PageBreak(), _build_pdf_section_title("Notes & Activity History", styles),
                Paragraph("Waktu mengikuti pencatatan sistem (WIB / Asia/Jakarta). Metadata lama yang tidak tersedia ditandai secara eksplisit.", body)]
    for index, item in enumerate(items, 1):
        action = str(item.get("action") or "Review")
        stage = str(item.get("stage") or "-")
        actor = str(item.get("actor") or "Tidak tercatat")
        at = str(item.get("at") or "Tidak tercatat")
        metadata = f"{index}. {action} | {stage} | Penulis: {actor} | Tanggal/Jam: {at}"
        is_red = item.get("is_red") is True
        if is_red:
            metadata = "[RED NOTE] " + metadata
        elements.append(Paragraph(html.escape(metadata), red_heading if is_red else heading))
        note = str(item.get("note") or "").replace("\r\n", "\n").replace("\r", "\n")
        elements.append(Paragraph(html.escape(note).replace("\n", "<br/>") if note.strip() else "(Tanpa catatan)", red_body if is_red else body))
    return elements


def _render_workflow_notes(rec: dict) -> None:
    items = _workflow_notes_for_display(rec)
    st.markdown("### Notes & Activity")
    if not items:
        st.write("No notes yet.")
        return
    for item in reversed(items):
        actor = str(item.get("actor", "") or "-")
        action = str(item.get("action", "") or "Review")
        stage = str(item.get("stage", "") or "")
        at = str(item.get("at", "") or "")
        note = str(item.get("note", "") or "").strip()
        title = f"**{html.escape(action)}** — {html.escape(actor)}"
        if stage:
            title += f" · {html.escape(stage)}"
        if at:
            title += f" · {html.escape(at)}"
        st.markdown(title)
        if item.get("is_red") is True:
            st.error("🔴 RED NOTE\n\n" + (note or "(Tanpa catatan)"))
        elif note:
            st.write(note)


def _set_eg_flash(kind: str, text: str) -> None:
    st.session_state["eg_flash"] = {"kind": str(kind or "info"), "text": str(text or "")}


def _render_eg_flash() -> None:
    flash = st.session_state.pop("eg_flash", None)
    if not isinstance(flash, dict) or not flash.get("text"):
        return
    kind = flash.get("kind", "info")
    if kind == "success":
        st.success(flash["text"])
    elif kind == "warning":
        st.warning(flash["text"])
    elif kind == "error":
        st.error(flash["text"])
    else:
        st.info(flash["text"])


def _paragraph_height(paragraph: Paragraph, available_width: float) -> float:

    try:
        _, required_height = paragraph.wrap(max(1.0, float(available_width)), 1000 * cm)
        return float(required_height)
    except Exception:
        return 0.0


def _dynamic_pdf_row_height(
    cells,
    col_widths,
    minimum_height: float,
    left_padding: float,
    right_padding: float,
    top_padding: float,
    bottom_padding: float,
) -> float:






    required = float(minimum_height or 0.0)
    for cell, width in zip(list(cells), list(col_widths)):
        printable_width = max(1.0, float(width) - float(left_padding) - float(right_padding))
        if isinstance(cell, Paragraph):
            cell_height = _paragraph_height(cell, printable_width)
        else:
            cell_height = 0.0
        required = max(
            required,
            cell_height + float(top_padding) + float(bottom_padding),
        )
    return required





def inject_exgratia_css() -> None:
    st.markdown(f"""
    <style>
      .eg-section-card{{
        margin:14px 0 8px 0; padding:12px 16px; border-radius:16px;
        background:linear-gradient(180deg,#FFFFFF 0%,#F8FAFC 100%);
        border:1px solid rgba(0,51,102,0.12);
        box-shadow:0 8px 22px rgba(15,23,42,0.035);
      }}
      .eg-section-title{{
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
        font-size:18px; font-weight:850; line-height:1.15; color:{NAVY}; letter-spacing:-0.01em;
      }}
      .eg-info-card{{
        padding:14px 16px; border-radius:18px; background:#FFFFFF;
        border:1px solid rgba(0,51,102,0.12); box-shadow:0 10px 26px rgba(15,23,42,0.055);
      }}
      .eg-chip{{
        display:inline-flex; align-items:center; gap:6px; padding:6px 10px; border-radius:999px;
        background:#EEF6FF; border:1px solid rgba(0,51,102,0.14); color:{NAVY};
        font-size:12px; font-weight:850;
      }}
      .eg-help-text{{font-size:12.6px;color:#64748B;line-height:1.35;}}
      div[class*="st-key-eg_prepare_pdf"] button{{
        min-height:36px !important; height:36px !important; padding:0 14px !important;
        border-radius:11px !important; font-size:12.5px !important; font-weight:800 !important;
        background:linear-gradient(135deg,#003366 0%,#1F5A91 100%) !important; color:#FFFFFF !important;
        border:1px solid rgba(0,51,102,0.72) !important;
      }}
      .eg-download-link{{
        color:{NAVY} !important; font-weight:800; text-decoration:underline !important; text-underline-offset:3px;
      }}
      /* Scope module form styling to the main page only, not the sidebar. */
      main div[data-testid="stForm"],
      section.main div[data-testid="stForm"]{{
        border:1px solid rgba(0,51,102,0.10) !important; border-radius:18px !important;
        background:#FFFFFF !important; box-shadow:0 8px 22px rgba(15,23,42,0.035) !important;
        padding:14px 16px 16px 16px !important;
      }}

      /* Full Ex-Gratia preparation overlay.
         It covers the app viewport while keeping the sidebar visible above it. */
      section[data-testid="stSidebar"]{{
        position:relative !important;
        z-index:1000002 !important;
      }}
      .eg-fullscreen-loading-overlay{{
        position:fixed;
        inset:0;
        z-index:1000001;
        display:flex;
        align-items:center;
        justify-content:center;
        background:
          radial-gradient(circle at 50% 42%, rgba(238,246,255,0.96) 0%, rgba(248,250,252,0.99) 34%, #FFFFFF 72%);
        backdrop-filter:blur(4px);
        -webkit-backdrop-filter:blur(4px);
        cursor:wait;
        overflow:hidden;
      }}
      .eg-fullscreen-loading-overlay::before{{
        content:"";
        position:absolute;
        width:440px;
        height:440px;
        border-radius:999px;
        background:rgba(31,90,145,0.055);
        filter:blur(4px);
        animation:eg-loader-pulse 2.2s ease-in-out infinite;
      }}
      .eg-fullscreen-loading-content{{
        position:relative;
        z-index:2;
        display:flex;
        flex-direction:column;
        align-items:center;
        justify-content:center;
        gap:18px;
        padding:28px 34px;
        text-align:center;
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
      }}
      .eg-fullscreen-loading-spinner{{
        width:48px;
        height:48px;
        border-radius:999px;
        border:4px solid rgba(0,51,102,0.13);
        border-top-color:#003366;
        border-right-color:#1F5A91;
        box-shadow:0 8px 22px rgba(0,51,102,0.12);
        animation:eg-loader-spin .82s linear infinite;
      }}
      .eg-fullscreen-loading-title{{
        color:#003366;
        font-size:18px;
        line-height:1.2;
        font-weight:850;
        letter-spacing:-0.01em;
      }}
      .eg-fullscreen-loading-dots::after{{
        content:"";
        display:inline-block;
        width:18px;
        text-align:left;
        animation:eg-loader-dots 1.3s steps(4,end) infinite;
      }}
      @keyframes eg-loader-spin{{
        to{{transform:rotate(360deg);}}
      }}
      @keyframes eg-loader-pulse{{
        0%,100%{{transform:scale(.88);opacity:.45;}}
        50%{{transform:scale(1.08);opacity:.82;}}
      }}
      @keyframes eg-loader-dots{{
        0%{{content:"";}}
        25%{{content:".";}}
        50%{{content:"..";}}
        75%,100%{{content:"...";}}
      }}
    </style>
    """, unsafe_allow_html=True)


def section_header(title: str) -> None:
    st.markdown(f"<div class='eg-section-card'><div class='eg-section-title'>{html.escape(title)}</div></div>", unsafe_allow_html=True)


def _download_link(label: str, data: bytes, file_name: str, mime: str) -> None:
    b64 = base64.b64encode(data).decode("ascii")
    st.markdown(
        f'<a class="eg-download-link" download="{html.escape(file_name)}" href="data:{mime};base64,{b64}">{html.escape(label)}</a>',
        unsafe_allow_html=True,
    )


def _render_html_block(html_content: str, height: int = 260) -> None:
    components.html(
        html_content,
        height=height,
        scrolling=False,
    )


def render_performance_html_table(summary_df: pd.DataFrame, table_key: str, display_unit: str = "in IDR Mio") -> None:

    df = _normalise_performance_summary_schema(summary_df)
    raw_df = df.copy()
    display_df = df.copy()
    unit_label = DISPLAY_UNIT_CONFIG.get(
        display_unit, DISPLAY_UNIT_CONFIG["in IDR Mio"]
    )["label"]

    ratio_cols = [
        "LOSS RATIO EXISTING",
        "LOSS RATIO + EX-GRATIA",
        "COMBINED RATIO EXISTING",
        "COMBINED RATIO + EX-GRATIA",
    ]

    if display_df.empty:
        body_rows = "<tr><td class='text-cell' colspan='7'>No data</td></tr>"
    else:
        for col in ["GWP", "GROSS CLAIM"]:
            display_df[col] = pd.to_numeric(display_df[col], errors="coerce").map(
                lambda x: _format_money(x, display_unit) if pd.notna(x) else ""
            )
        for col in ratio_cols:
            display_df[col] = pd.to_numeric(display_df[col], errors="coerce").map(
                lambda x: f"{float(x):.1f}%" if pd.notna(x) else ""
            )
        display_df["UW YEARS"] = display_df["UW YEARS"].map(
            lambda x: "" if pd.isna(x) else str(int(float(x)))
        )

        rows = []
        for r in range(len(display_df)):
            cells = []
            lr_existing = _safe_to_float(raw_df.iloc[r].get("LOSS RATIO EXISTING"), 0.0)
            lr_after = _safe_to_float(raw_df.iloc[r].get("LOSS RATIO + EX-GRATIA"), 0.0)
            cor_existing = _safe_to_float(raw_df.iloc[r].get("COMBINED RATIO EXISTING"), 0.0)
            cor_after = _safe_to_float(raw_df.iloc[r].get("COMBINED RATIO + EX-GRATIA"), 0.0)
            scenario_changed = (
                abs(lr_after - lr_existing) > 1e-9
                or abs(cor_after - cor_existing) > 1e-9
            )

            for c in EXGRATIA_PERFORMANCE_COLUMNS:
                raw = raw_df.iloc[r][c]
                sort_num = pd.to_numeric(pd.Series([raw]), errors="coerce").iloc[0]
                if pd.notna(sort_num):
                    sort_value = str(float(sort_num)); sort_type = "num"
                else:
                    sort_value = html.escape(str(raw).lower()); sort_type = "text"

                cls = ["text-cell" if c == "UW YEARS" else "num-cell"]
                if scenario_changed and c in {"LOSS RATIO + EX-GRATIA", "COMBINED RATIO + EX-GRATIA"}:
                    cls.append("scenario-cell")
                if c.startswith("LOSS RATIO") and pd.notna(sort_num) and float(sort_num) > 50:
                    cls.append("loss-warning")
                if c.startswith("COMBINED RATIO") and pd.notna(sort_num) and float(sort_num) > 100:
                    cls.append("cor-danger")

                cells.append(
                    f"<td class='{' '.join(cls)}' data-sort='{sort_value}' "
                    f"data-sort-type='{sort_type}'>{html.escape(str(display_df.iloc[r][c]))}</td>"
                )
            rows.append(f"<tr>{''.join(cells)}</tr>")
        body_rows = "".join(rows)

    cols = [
        "UW YEARS",
        f"GWP<br><span>{unit_label}</span>",
        f"GROSS CLAIM<br><span>{unit_label}</span>",
        "LOSS RATIO<br><span>Existing</span>",
        "LOSS RATIO<br><span>+ Ex-Gratia</span>",
        "COMBINED RATIO<br><span>Existing</span>",
        "COMBINED RATIO<br><span>+ Ex-Gratia</span>",
    ]
    headers = "".join([f"<th>{h}</th>" for h in cols])
    dom_id = "eg_perf_" + hashlib.sha1((table_key + str(len(df))).encode()).hexdigest()[:10]
    height = max(205, min(340, 96 + 36 * max(1, len(df))))

    sort_options = "".join([
        "<option value=''>None</option>",
        "<option value='0'>UW Years</option>",
        "<option value='1'>GWP</option>",
        "<option value='2'>Gross Claim</option>",
        "<option value='3'>LR Existing</option>",
        "<option value='4'>LR + Ex-Gratia</option>",
        "<option value='5'>CoR Existing</option>",
        "<option value='6'>CoR + Ex-Gratia</option>",
    ])

    html_table = f"""
    <style>
      html, body {{ margin:0; background:transparent; }}
      .eg-table-controls {{ display:flex; gap:10px; align-items:center; margin:0 0 10px 0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
      .eg-table-controls label {{ font-size:11.5px; font-weight:700; color:#475569; }}
      .eg-table-controls select, .eg-table-controls button {{ height:34px; border:1px solid rgba(0,51,102,0.16); border-radius:10px; background:#FFFFFF; color:#1F2937; font-size:11.5px; padding:0 10px; outline:none; }}
      .eg-table-controls button {{ cursor:pointer; font-weight:700; color:#003366; }}
      .eg-table-wrap {{ width:100%; max-height:{height}px; overflow:auto; border:1px solid rgba(0,51,102,0.12); border-radius:16px; background:#FFFFFF; box-shadow:0 10px 28px rgba(15,23,42,0.06); }}
      .eg-table {{ border-collapse:separate; border-spacing:0; table-layout:fixed; width:100%; min-width:1020px; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Arial,sans-serif; color:#334155; }}
      .eg-table thead th {{ position:sticky; top:0; z-index:30; background:#003366; color:#FFFFFF; text-align:center; vertical-align:middle; font-size:10.3px; line-height:1.15; font-weight:780; height:50px; padding:8px 7px; border-right:1px solid rgba(255,255,255,0.18); }}
      .eg-table thead th span {{ display:block; margin-top:2px; font-size:8.5px; font-weight:500; opacity:.82; }}
      .eg-table tbody td {{ font-size:11.1px; line-height:1.25; height:34px; padding:8px 9px; border-right:1px solid rgba(15,23,42,0.045); border-bottom:1px solid rgba(15,23,42,0.055); background:#FFFFFF; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-weight:620; }}
      .eg-table tbody tr:nth-child(even) td {{ background:#F4F7FB; }}
      .eg-table tbody tr:hover td {{ background:#EEF6FF; }}
      .eg-table .text-cell {{ text-align:center; font-weight:760; color:#1E3A5F; }}
      .eg-table .num-cell {{ text-align:right; font-variant-numeric:tabular-nums; color:#334155; }}
      .eg-table tbody td.scenario-cell {{ background:#EEF6FF !important; color:#003366; font-weight:850; }}
      .eg-table tbody td.cor-danger {{ background:#FFE7E7 !important; color:#9F1239; font-weight:850; }}
      .eg-table tbody td.loss-warning {{ background:#FFF3D6 !important; color:#7C4A03; font-weight:850; }}
    </style>
    <div class="eg-table-controls">
      <label for="sort_by_{dom_id}">Sort by</label>
      <select id="sort_by_{dom_id}">{sort_options}</select>
      <select id="sort_order_{dom_id}"><option value="desc">Descending</option><option value="asc">Ascending</option></select>
      <button type="button" id="reset_{dom_id}">Reset</button>
    </div>
    <div class="eg-table-wrap"><table class="eg-table" id="{dom_id}"><thead><tr>{headers}</tr></thead><tbody>{body_rows}</tbody></table></div>
    <script>
      (function(){{
        const table=document.getElementById("{dom_id}"), sortBy=document.getElementById("sort_by_{dom_id}"), sortOrder=document.getElementById("sort_order_{dom_id}"), reset=document.getElementById("reset_{dom_id}");
        if(!table||!sortBy||!sortOrder||!reset) return;
        const tbody=table.querySelector("tbody"); const original=Array.from(tbody.querySelectorAll("tr"));
        function applySort(){{
          const colIndex=sortBy.value; if(colIndex===""){{ tbody.replaceChildren(...original); return; }}
          const idx=parseInt(colIndex,10), asc=sortOrder.value==="asc";
          const rows=Array.from(tbody.querySelectorAll("tr"));
          rows.sort(function(a,b){{ const ac=a.children[idx], bc=b.children[idx]; const at=ac.getAttribute("data-sort-type"), bt=bc.getAttribute("data-sort-type"); const av=ac.getAttribute("data-sort")||"", bv=bc.getAttribute("data-sort")||""; let res=0; if(at==="num"&&bt==="num") res=(parseFloat(av)||0)-(parseFloat(bv)||0); else res=av.localeCompare(bv,undefined,{{numeric:true,sensitivity:"base"}}); return asc?res:-res; }});
          tbody.replaceChildren(...rows);
        }}
        sortBy.addEventListener("change", applySort); sortOrder.addEventListener("change", applySort); reset.addEventListener("click", function(){{ sortBy.value=""; sortOrder.value="desc"; tbody.replaceChildren(...original); }});
      }})();
    </script>
    """
    _render_html_block(html_table, height=height + 46)





def _draw_footer(canvas, doc, username: str, doc_id: str):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(grey)
    now = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d %b %Y %H:%M WIB")
    canvas.drawString(0.8 * cm, 0.55 * cm, "Prepared by Actuarial Department | Confidential")
    canvas.drawRightString(doc.pagesize[0] - 0.8 * cm, 0.55 * cm, f"Downloaded by: {username or '-'} | At: {now}")
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(doc.pagesize[0] - 0.8 * cm, doc.pagesize[1] - 0.55 * cm, f"Document ID: {_sanitize_doc_id(doc_id)}")
    canvas.restoreState()


def _build_pdf_section_title(title: str, styles):
    return Paragraph(
        html.escape(title),
        ParagraphStyle(
            "EGSectionTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.2,
            leading=12.0,
            textColor=colors.HexColor(NAVY),
            spaceBefore=8,
            spaceAfter=4,
        ),
    )


def _build_value_table(rows, styles, value_col_width=12.8 * cm):

    no_style = ParagraphStyle(
        "NoCell",
        parent=styles["Normal"],
        fontSize=8.1,
        leading=9.3,
        alignment=1,
        textColor=colors.HexColor(TEXT_DARK),
    )
    label_style = ParagraphStyle(
        "LabelCell",
        parent=styles["Normal"],
        fontSize=8.2,
        leading=9.5,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor(NAVY),
    )
    value_style = ParagraphStyle(
        "ValueCell",
        parent=styles["Normal"],
        fontSize=8.2,
        leading=9.6,
        textColor=colors.HexColor(TEXT_DARK),
        splitLongWords=True,
    )

    col_widths = [0.75 * cm, 4.35 * cm, value_col_width]
    left_padding = 5
    right_padding = 5
    top_padding = 4
    bottom_padding = 4

    data = []
    row_heights = []
    for idx, label, value, minimum_height in rows:
        cells = [
            _p(idx, no_style),
            _p(html.escape(label), label_style),
            _p(value, value_style),
        ]
        data.append(cells)
        row_heights.append(
            _dynamic_pdf_row_height(
                cells,
                col_widths,
                minimum_height,
                left_padding,
                right_padding,
                top_padding,
                bottom_padding,
            )
        )

    tbl = Table(
        data,
        colWidths=col_widths,
        rowHeights=row_heights,
        splitByRow=1,
    )
    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.28, colors.HexColor("#8FA3B8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), left_padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), right_padding),
        ("TOPPADDING", (0, 0), (-1, -1), top_padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), bottom_padding),
    ]
    for rr in range(len(data)):
        if rr % 2 == 1:
            style_cmds.append(
                ("BACKGROUND", (0, rr), (-1, rr), colors.HexColor("#F8FAFC"))
            )
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def _build_claim_information_table(rows, styles):

    no_style = ParagraphStyle(
        "ClaimNoCell",
        parent=styles["Normal"],
        fontSize=7.0,
        leading=7.9,
        alignment=1,
        textColor=colors.HexColor(TEXT_DARK),
    )
    label_style = ParagraphStyle(
        "ClaimLabelCell",
        parent=styles["Normal"],
        fontSize=7.1,
        leading=8.0,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor(NAVY),
    )
    value_style = ParagraphStyle(
        "ClaimValueCell",
        parent=styles["Normal"],
        fontSize=7.1,
        leading=8.1,
        textColor=colors.HexColor(TEXT_DARK),
        splitLongWords=True,
    )

    col_widths = [0.65 * cm, 4.0 * cm, 13.05 * cm]
    left_padding = 4
    right_padding = 4
    top_padding = 3
    bottom_padding = 3

    data = []
    row_heights = []
    for idx, label, value, minimum_height in rows:
        cells = [
            _p(idx, no_style),
            _p(html.escape(label), label_style),
            _p(value, value_style),
        ]
        data.append(cells)
        row_heights.append(
            _dynamic_pdf_row_height(
                cells,
                col_widths,
                minimum_height,
                left_padding,
                right_padding,
                top_padding,
                bottom_padding,
            )
        )

    tbl = Table(
        data,
        colWidths=col_widths,
        rowHeights=row_heights,
        splitByRow=1,
    )
    cmds = [
        ("GRID", (0, 0), (-1, -1), 0.24, colors.HexColor("#8FA3B8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), left_padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), right_padding),
        ("TOPPADDING", (0, 0), (-1, -1), top_padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), bottom_padding),
    ]
    for rr in range(len(data)):
        if rr % 2 == 1:
            cmds.append(
                ("BACKGROUND", (0, rr), (-1, rr), colors.HexColor("#F8FAFC"))
            )
    tbl.setStyle(TableStyle(cmds))
    return tbl


def _build_note_box(title: str, styles, height: float = 1.0 * cm, text: str = ""):

    title_style = ParagraphStyle(
        "NoteBoxTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.0,
        leading=9.1,
        textColor=colors.HexColor(NAVY),
    )
    normal = ParagraphStyle(
        "NoteBoxNormal",
        parent=styles["Normal"],
        fontSize=7.6,
        leading=8.7,
        textColor=colors.HexColor(TEXT_DARK),
        splitLongWords=True,
    )



    clean_text = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    body = html.escape(clean_text).replace("\n", "<br/>") or "<br/>"

    col_widths = [4.35 * cm, 12.95 * cm]
    left_padding = 6
    right_padding = 6
    top_padding = 4.5
    bottom_padding = 4.5

    cells = [_p(title, title_style), _p(body, normal)]
    dynamic_height = _dynamic_pdf_row_height(
        cells,
        col_widths,
        height,
        left_padding,
        right_padding,
        top_padding,
        bottom_padding,
    )

    tbl = Table(
        [cells],
        colWidths=col_widths,
        rowHeights=[dynamic_height],
        splitByRow=1,
    )
    tbl.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.28, colors.HexColor("#8FA3B8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), left_padding),
            ("RIGHTPADDING", (0, 0), (-1, -1), right_padding),
            ("TOPPADDING", (0, 0), (-1, -1), top_padding),
            ("BOTTOMPADDING", (0, 0), (-1, -1), bottom_padding),
        ])
    )
    return tbl


def _build_performance_table(title: str, summary_df: pd.DataFrame, styles, display_unit: str):
    section_style = ParagraphStyle(
        "PerfTitle", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=9.0, leading=10.3, textColor=colors.HexColor(NAVY),
        spaceBefore=7, spaceAfter=4,
    )
    header_style = ParagraphStyle(
        "PerfHeader", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=6.2, leading=7.0, alignment=1, textColor=colors.white,
    )
    cell_num = ParagraphStyle(
        "PerfCellNum", parent=styles["Normal"], fontSize=6.7,
        leading=7.5, alignment=2, textColor=colors.HexColor(TEXT_DARK),
    )
    cell_year = ParagraphStyle(
        "PerfYear", parent=cell_num, alignment=1, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0F2742"),
    )

    df = _normalise_performance_summary_schema(summary_df)
    elements = [Paragraph(html.escape(title), section_style)]
    unit = DISPLAY_UNIT_CONFIG[display_unit]["label"]
    headers = [
        "UW", f"GWP<br/>({unit})", f"GROSS CLAIM<br/>({unit})",
        "LR<br/>Existing", "LR<br/>+ Ex-Gratia",
        "CoR<br/>Existing", "CoR<br/>+ Ex-Gratia",
    ]
    data = [[_p(h, header_style) for h in headers]]

    if df.empty:
        data.append([_p("No data", cell_year)] + [_p("", cell_num) for _ in range(6)])
    else:
        for _, r in df.iterrows():
            data.append([
                _p(str(int(r["UW YEARS"])), cell_year),
                _p(_format_money(r["GWP"], display_unit), cell_num),
                _p(_format_money(r["GROSS CLAIM"], display_unit), cell_num),
                _p(_format_pct(r["LOSS RATIO EXISTING"]), cell_num),
                _p(_format_pct(r["LOSS RATIO + EX-GRATIA"]), cell_num),
                _p(_format_pct(r["COMBINED RATIO EXISTING"]), cell_num),
                _p(_format_pct(r["COMBINED RATIO + EX-GRATIA"]), cell_num),
            ])


    tbl = Table(
        data,
        colWidths=[1.25 * cm, 2.45 * cm, 2.75 * cm, 2.35 * cm, 2.65 * cm, 2.55 * cm, 3.30 * cm],
        repeatRows=1,
    )
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.22, colors.HexColor("#8FA3B8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.0),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
    ]

    for row in range(1, len(data)):
        if row % 2 == 0:
            cmds.append(("BACKGROUND", (0, row), (-1, row), colors.HexColor(SOFT_ZEBRA)))
        try:
            lr_existing = float(df.iloc[row - 1]["LOSS RATIO EXISTING"])
            lr_after = float(df.iloc[row - 1]["LOSS RATIO + EX-GRATIA"])
            cor_existing = float(df.iloc[row - 1]["COMBINED RATIO EXISTING"])
            cor_after = float(df.iloc[row - 1]["COMBINED RATIO + EX-GRATIA"])
            if abs(lr_after - lr_existing) > 1e-9:
                cmds.append(("BACKGROUND", (4, row), (4, row), colors.HexColor(SOFT_BLUE)))
            if abs(cor_after - cor_existing) > 1e-9:
                cmds.append(("BACKGROUND", (6, row), (6, row), colors.HexColor(SOFT_BLUE)))
            if lr_existing > 50:
                cmds.append(("BACKGROUND", (3, row), (3, row), colors.HexColor(WARN_ORANGE)))
            if lr_after > 50:
                cmds.append(("BACKGROUND", (4, row), (4, row), colors.HexColor(WARN_ORANGE)))
            if cor_existing > 100:
                cmds.append(("BACKGROUND", (5, row), (5, row), colors.HexColor(WARN_RED)))
            if cor_after > 100:
                cmds.append(("BACKGROUND", (6, row), (6, row), colors.HexColor(WARN_RED)))
        except Exception:
            pass

    tbl.setStyle(TableStyle(cmds))
    elements.append(tbl)
    return elements




def _stringify_ovr_value(x) -> str:
    try:
        if x is None or pd.isna(x):
            return ""
    except Exception:
        pass
    return str(x)


def _ovr_rules_for_pdf(ovr_context: dict | None) -> pd.DataFrame:

    if not ovr_context:
        return pd.DataFrame()
    mode = ovr_context.get("mode", "uniform")
    if mode == "uniform":
        pct = _safe_to_float(ovr_context.get("uniform_pct", 0.0), 0.0)
        return pd.DataFrame([{"OVR Scope": "All portfolio rows", "OVR (%)": pct}])

    rules_df = ovr_context.get("rules_df")
    dims = [d for d in (ovr_context.get("dims") or []) if d]
    if not isinstance(rules_df, pd.DataFrame) or rules_df.empty or not dims:
        return pd.DataFrame(columns=dims + ["OVR (%)"])

    cols = [c for c in dims if c in rules_df.columns]
    if "OVR_PCT_INPUT" not in rules_df.columns or not cols:
        return pd.DataFrame(columns=cols + ["OVR (%)"])

    out = rules_df[cols + ["OVR_PCT_INPUT"]].copy()
    out["OVR_PCT_INPUT"] = pd.to_numeric(out["OVR_PCT_INPUT"], errors="coerce").fillna(0.0)
    out = out[out["OVR_PCT_INPUT"] > 0].copy()
    if out.empty:
        out = rules_df[cols + ["OVR_PCT_INPUT"]].copy().head(1)
        out["OVR_PCT_INPUT"] = pd.to_numeric(out["OVR_PCT_INPUT"], errors="coerce").fillna(0.0)

    out = out.rename(columns={"OVR_PCT_INPUT": "OVR (%)"})
    for c in cols:
        out[c] = out[c].map(_stringify_ovr_value)
    return out.reset_index(drop=True)


def _build_ovr_attachment_elements(styles, ovr_context: dict | None):
    title_style = ParagraphStyle(
        "OVRAttachTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=13.0,
        leading=15.5,
        alignment=1,
        textColor=colors.HexColor(NAVY),
        spaceAfter=7,
    )
    meta_label = ParagraphStyle(
        "OVRMetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.0,
        leading=9.5,
        textColor=colors.HexColor(NAVY),
    )
    meta_value = ParagraphStyle(
        "OVRMetaValue",
        parent=styles["Normal"],
        fontSize=8.0,
        leading=9.5,
        textColor=colors.HexColor(TEXT_DARK),
    )
    header_style = ParagraphStyle(
        "OVRHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=8.2,
        alignment=1,
        textColor=colors.white,
    )
    cell_style = ParagraphStyle(
        "OVRCell",
        parent=styles["Normal"],
        fontSize=7.0,
        leading=8.2,
        textColor=colors.HexColor(TEXT_DARK),
    )
    num_style = ParagraphStyle(
        "OVRCellNum",
        parent=cell_style,
        alignment=2,
    )

    ctx = ovr_context or {}
    mode_label = "Sama untuk semua" if ctx.get("mode") == "uniform" else "Berdasarkan kategori"
    processed_at = ctx.get("processed_at", "")
    dims_text = ", ".join(ctx.get("dims") or []) if ctx.get("dims") else "-"
    ovr_df = _ovr_rules_for_pdf(ctx)
    non_zero_rules = 0
    if not ovr_df.empty and "OVR (%)" in ovr_df.columns:
        non_zero_rules = int((pd.to_numeric(ovr_df["OVR (%)"], errors="coerce").fillna(0) > 0).sum())

    elements = [Paragraph("Lampiran OVR", title_style)]
    meta_rows = [
        [_p("OVR Status", meta_label), _p("Processed / Included in calculation", meta_value)],
        [_p("Mode OVR", meta_label), _p(html.escape(mode_label), meta_value)],
        [_p("Kategori", meta_label), _p(html.escape(dims_text), meta_value)],
        [_p("Waktu Proses", meta_label), _p(html.escape(str(processed_at or "-")), meta_value)],
        [_p("Rule OVR > 0%", meta_label), _p(html.escape(str(non_zero_rules)), meta_value)],
    ]
    meta_tbl = Table(meta_rows, colWidths=[4.4 * cm, 12.8 * cm])
    meta_tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.24, colors.HexColor("#8FA3B8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F4F7FB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(meta_tbl)
    elements.append(Spacer(1, 0.18 * cm))

    if ovr_df.empty:
        elements.append(Paragraph("Tidak ada detail OVR yang tersimpan.", meta_value))
        return elements

    max_rows = 120
    truncated = len(ovr_df) > max_rows
    pdf_df = ovr_df.head(max_rows).copy()

    headers = list(pdf_df.columns)
    data = [[_p(html.escape(str(h)), header_style) for h in headers]]
    for _, row in pdf_df.iterrows():
        row_cells = []
        for h in headers:
            value = row[h]
            if h == "OVR (%)":
                row_cells.append(_p(f"{_safe_to_float(value, 0.0):.6f}%", num_style))
            else:
                row_cells.append(_p(html.escape(_stringify_ovr_value(value)), cell_style))
        data.append(row_cells)

    if len(headers) == 1:
        col_widths = [17.2 * cm]
    else:
        pct_w = 2.4 * cm if "OVR (%)" in headers else 0
        other_count = len(headers) - (1 if "OVR (%)" in headers else 0)
        other_w = (17.2 * cm - pct_w) / max(other_count, 1)
        col_widths = [pct_w if h == "OVR (%)" else other_w for h in headers]

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
        ("GRID", (0, 0), (-1, -1), 0.22, colors.HexColor("#8FA3B8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for rr in range(1, len(data)):
        if rr % 2 == 0:
            cmds.append(("BACKGROUND", (0, rr), (-1, rr), colors.HexColor(SOFT_ZEBRA)))
    tbl.setStyle(TableStyle(cmds))
    elements.append(tbl)
    if truncated:
        elements.append(Spacer(1, 0.12 * cm))
        elements.append(Paragraph(f"Catatan: lampiran PDF menampilkan {max_rows} dari {len(ovr_df)} rule OVR pertama.", meta_value))
    return elements


def _signature_confirm_text(by: str = "", at: str = "") -> str:

    by = str(by or "").strip()
    at = str(at or "").strip()
    if not by:
        return ""
    return f"confirmed by:<br/><b>{html.escape(by)}</b><br/>at: {html.escape(at or '-')}"



def _build_signature_table(styles, workflow_context: dict | None = None):




    workflow_context = workflow_context or {}

    header_style = ParagraphStyle(
        "SigHeader",
        parent=styles["Normal"],
        fontSize=7.0,
        leading=8.0,
        fontName="Helvetica-Bold",
        alignment=1,
        textColor=colors.white,
    )
    role_style = ParagraphStyle(
        "SigRole",
        parent=styles["Normal"],
        fontSize=6.6,
        leading=7.5,
        fontName="Helvetica-Bold",
        alignment=1,
        textColor=colors.HexColor(TEXT_DARK),
    )
    confirm_style = ParagraphStyle(
        "SigConfirmInBox",
        parent=styles["Normal"],
        fontSize=5.7,
        leading=6.7,
        alignment=1,
        textColor=colors.HexColor("#334155"),
    )

    def sig(by_col: str, at_col: str):
        return _p(_signature_confirm_text(workflow_context.get(by_col, ""), workflow_context.get(at_col, "")), confirm_style)

    review_roles = [
        ("Manager Klaim", "CLAIM_CONFIRMED_BY", "CLAIM_CONFIRMED_AT"),
    ]

    approve_roles = [
        ("Direktur Marketing", "DIR_MARKETING_CONFIRMED_BY", "DIR_MARKETING_CONFIRMED_AT"),
        ("Direktur Teknik", "DIR_TEKNIK_CONFIRMED_BY", "DIR_TEKNIK_CONFIRMED_AT"),
    ]

    submitted_roles = [
        ("Marketing", "CREATED_BY", "CREATED_AT"),
        ("Manager<br/>Marketing", "MARKETING_MANAGER_CONFIRMED_BY", "MARKETING_MANAGER_CONFIRMED_AT"),
    ]

    all_roles = submitted_roles + review_roles + approve_roles
    n_cols = len(all_roles)
    available_w = 17.3 * cm
    col_w = available_w / max(n_cols, 1)


    group_row = []
    for i in range(n_cols):
        if i == 0:
            group_row.append(_p("Diajukan Oleh", header_style))
        elif i == len(submitted_roles):
            group_row.append(_p("Direview", header_style))
        elif i == len(submitted_roles) + len(review_roles):
            group_row.append(_p("Menyetujui", header_style))
        else:
            group_row.append("")

    confirm_row = [sig(by_col, at_col) for _, by_col, at_col in all_roles]
    role_row = [_p(role_label, role_style) for role_label, _, _ in all_roles]
    data = [group_row, confirm_row, role_row]

    tbl = Table(
        data,
        colWidths=[col_w] * n_cols,
        rowHeights=[0.48 * cm, 1.52 * cm, 0.52 * cm],
    )

    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.28, colors.HexColor("#8FA3B8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#F6F8FB")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
    ]

    style_cmds.append(("SPAN", (0, 0), (len(submitted_roles) - 1, 0)))

    review_start = len(submitted_roles)
    review_end = review_start + len(review_roles) - 1
    style_cmds.append(("SPAN", (review_start, 0), (review_end, 0)))

    approve_start = review_end + 1
    approve_end = n_cols - 1
    style_cmds.append(("SPAN", (approve_start, 0), (approve_end, 0)))

    tbl.setStyle(TableStyle(style_cmds))
    return tbl

def build_exgratia_pdf(
    form_data: dict,
    intermediary_summary: pd.DataFrame,
    insured_summary: pd.DataFrame,
    display_unit: str,
    username: str,
    doc_id: str,
    ovr_context: dict | None = None,
    workflow_context: dict | None = None,
) -> bytes:
    workflow_context = workflow_context or {}
    buffer = io.BytesIO()
    page_size = A4
    doc = SimpleDocTemplate(buffer, pagesize=page_size, leftMargin=0.62 * cm, rightMargin=0.62 * cm, topMargin=0.58 * cm, bottomMargin=0.72 * cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleEG", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=13.8, leading=15.8, alignment=1, textColor=colors.HexColor(NAVY), spaceAfter=2)
    subtitle_pdf_style = ParagraphStyle("SubtitleEG", parent=styles["Normal"], fontName="Helvetica", fontSize=7.5, leading=8.8, alignment=1, textColor=colors.HexColor("#8A94A3"), spaceAfter=7)
    normal = ParagraphStyle("NormalEG", parent=styles["Normal"], fontSize=8.2, leading=9.8, textColor=colors.HexColor(TEXT_DARK))
    note_style = ParagraphStyle("NoteEG", parent=normal, fontSize=7.8, leading=9.2, textColor=colors.HexColor("#555555"))

    elements = [Paragraph("EX-GRATIA CLAIM PROPOSAL", title_style)]
    elements.append(Paragraph("This Proposal was Generated from SuperApp Actuary", subtitle_pdf_style))
    elements.append(Spacer(1, 0.05 * cm))

    date_text = ""
    tgl = form_data.get("loss_date")
    if isinstance(tgl, (datetime, date)):
        date_text = tgl.strftime("%d %b %Y")
    else:
        date_text = str(tgl or "")

    policy_uw_year = str(form_data.get("policy_uw_year", "") or "").strip()
    policy_cob_value = f"{html.escape(form_data.get('policy_no', ''))} / {html.escape(form_data.get('cob', ''))}"
    if policy_uw_year:
        policy_cob_value += f" / UW {html.escape(policy_uw_year)}"

    claim_rows = [
        ("1", "No. Klaim", html.escape(form_data.get("claim_no", "")), 0.42 * cm),
        ("2", "No. Polis / COB / UW Year", policy_cob_value, 0.42 * cm),
        ("3", "Sumber Bisnis / Tertanggung", f"{html.escape(form_data.get('source_business', ''))} / {html.escape(form_data.get('insured_name', ''))}", 0.42 * cm),
        ("4", "Tanggal Kejadian", html.escape(date_text), 0.42 * cm),
        ("5", "Nilai Klaim yang Diajukan", html.escape(_format_money_original(form_data.get("claim_amount", 0))), 0.42 * cm),
        ("6", "Nilai Ex-Gratia", html.escape(_format_money_original(form_data.get("exgratia_amount", 0))), 0.42 * cm),
        ("7", "Share MNC", html.escape(str(form_data.get("mnc_share", ""))), 0.42 * cm),
    ]
    consideration_rows = [
        ("1", "Penyebab Kerugian", _list_to_lines(form_data.get("loss_cause", "")), 0.55 * cm),
        ("2", "Alasan Ex-Gratia", _list_to_lines(form_data.get("exgratia_reason", "")), 0.55 * cm),
        ("3", "Potensi Bisnis yang Akan Datang", _list_to_lines(form_data.get("future_business", "")), 0.55 * cm),
    ]


    elements.append(_build_pdf_section_title("Claim Information", styles))
    elements.append(_build_claim_information_table(claim_rows, styles))
    elements.append(Spacer(1, 0.10 * cm))

    proxy_names = _intermediary_names("", (ovr_context or {}).get("proxy_intermediaries", []))
    if proxy_names:
        elements.append(_build_value_table(
            [("", "Proxy Intermediaries", html.escape("; ".join(proxy_names)), 0.42 * cm)],
            styles, value_col_width=12.8 * cm,
        ))
    elements.extend(_build_performance_table("Portfolio of Intermediary", intermediary_summary, styles, display_unit))
    insured_members = _intermediary_names(form_data.get("insured_name", ""), (ovr_context or {}).get("insured_group", []))
    if (ovr_context or {}).get("insured_group"):
        elements.append(_build_value_table([("", "Insured Group", html.escape("; ".join(insured_members)), 0.42 * cm)], styles, value_col_width=12.8 * cm))
    elements.extend(_build_performance_table("Portfolio of Insured / Policy Holder", insured_summary, styles, display_unit))
    elements.append(Spacer(1, 0.10 * cm))

    elements.append(_build_pdf_section_title("Consideration", styles))
    elements.append(_build_value_table(consideration_rows, styles, value_col_width=12.8 * cm))
    elements.append(Spacer(1, 0.10 * cm))
    elements.append(_build_note_box("Catatan Tim Klaim", styles, height=0.82 * cm, text=workflow_context.get("CLAIM_NOTE", "")))
    elements.append(Spacer(1, 0.12 * cm))
    elements.append(_build_signature_table(styles, workflow_context))

    elements.extend(_build_workflow_notes_pdf_elements(workflow_context, styles))

    if ovr_context:
        elements.append(PageBreak())
        elements.extend(_build_ovr_attachment_elements(styles, ovr_context))

    doc.build(
        elements,
        onFirstPage=lambda c, d: _draw_footer_with_eg_verification(c, d, username, doc_id, workflow_context),
        onLaterPages=lambda c, d: _draw_footer(c, d, username, doc_id),
    )
    return buffer.getvalue()







def _clear_generated_pdf() -> None:
    st.session_state.pop("eg_pdf_bytes", None)
    st.session_state.pop("eg_pdf_doc_id", None)
    st.session_state.pop("eg_pdf_name", None)


def _mark_ovr_dirty() -> None:

    st.session_state["eg_ovr_processed"] = False
    _clear_generated_pdf()
    st.session_state.pop("eg_intermediary_summary", None)
    st.session_state.pop("eg_insured_summary", None)


def _store_processed_ovr_outputs(
    risk_df: pd.DataFrame,
    processed_cfg: dict,
    source_business: str,
    insured_name: str,
    display_unit: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:

    processed_df = apply_ovr_to_df(
        risk_df,
        processed_cfg.get("mode", "uniform"),
        processed_cfg.get("uniform_pct", 0.0),
        processed_cfg.get("dims", []) or [],
        processed_cfg.get("rules_df") if isinstance(processed_cfg.get("rules_df"), pd.DataFrame) else pd.DataFrame(),
    )
    policy_no = str(processed_cfg.get("policy_no", "") or "").strip()
    target_uw_year = processed_cfg.get("policy_uw_year")
    if target_uw_year in (None, ""):
        target_uw_year = _policy_uw_year(risk_df, policy_no)
    exgratia_amount = _safe_to_float(processed_cfg.get("exgratia_amount", 0.0), 0.0)

    int_col = _resolve_col(risk_df, "INTERMEDIARY_NAME")
    ins_col = _resolve_col(risk_df, "INSURED_NAME")
    intermediary_summary = (
        make_entity_performance_summary(
            processed_df, int_col, source_business, last_n_years=None,
            display_unit=display_unit, start_year=2023,
            target_uw_year=target_uw_year, exgratia_amount=exgratia_amount,
            proxy_entities=processed_cfg.get("proxy_intermediaries", []),
        ) if source_business and int_col else pd.DataFrame(columns=EXGRATIA_PERFORMANCE_COLUMNS)
    )
    insured_summary = (
        make_entity_performance_summary(
            processed_df, ins_col, insured_name, last_n_years=None,
            display_unit=display_unit, start_year=2023,
            target_uw_year=target_uw_year, exgratia_amount=exgratia_amount,
            proxy_entities=processed_cfg.get("insured_group", []),
        ) if insured_name and ins_col else pd.DataFrame(columns=EXGRATIA_PERFORMANCE_COLUMNS)
    )
    st.session_state["eg_intermediary_summary"] = intermediary_summary
    st.session_state["eg_insured_summary"] = insured_summary
    return intermediary_summary, insured_summary


def _build_ovr_rules_editor(df: pd.DataFrame, available_dims: list[str]) -> tuple[list[str], pd.DataFrame]:
    dims = st.multiselect(
        "Kategori OVR",
        options=available_dims,
        max_selections=3,
        key="eg_ovr_dims",
        help="Pilih kategori OVR. Kombinasi unik dari data Risk Profile akan dibuat sebagai tabel input.",
        on_change=_mark_ovr_dirty,
    )
    if not dims:
        return [], pd.DataFrame()
    combos = df[dims].copy()
    for c in dims:
        combos[c] = combos[c].astype("string").fillna("(Blank)").astype(str)
    combos = combos.drop_duplicates().sort_values(dims).head(500).reset_index(drop=True)
    if "OVR_PCT_INPUT" not in combos.columns:
        combos["OVR_PCT_INPUT"] = 0.0
    st.caption(f"Menampilkan maksimal 500 kombinasi OVR. Kombinasi yang tidak ada di tabel akan dianggap 0%.")
    edited = st.data_editor(
        combos,
        key="eg_ovr_rules_editor",
        width="stretch",
        hide_index=True,
        column_config={"OVR_PCT_INPUT": st.column_config.NumberColumn("OVR (%)", min_value=0.0, max_value=100.0, step=0.000001, format="%.6f")},
    )
    return dims, edited



def _eg_render_progress_header(active_step: int = 1) -> None:
    steps = [(1, "Policy"), (2, "Form"), (3, "OVR"), (4, "Preview"), (5, "Submit")]
    items = []
    for no, title in steps:
        state = "is-active" if no == active_step else ("is-done" if no < active_step else "")
        items.append(
            f"<div class='eg-step {state}'><div class='eg-step-no'>{no}</div>"
            f"<div class='eg-step-title'>{html.escape(title)}</div></div>"
        )
    st.markdown(f"<div class='eg-progress'>{''.join(items)}</div>", unsafe_allow_html=True)

def _eg_html_notice(title: str, body: str, kind: str = "info") -> None:
    icon = {"info": "i", "ok": "✓", "warn": "!"}.get(kind, "i")
    st.markdown(
        f"""
        <div class='eg-notice eg-notice-{kind}'>
          <div class='eg-notice-icon'>{html.escape(icon)}</div>
          <div>
            <div class='eg-notice-title'>{html.escape(title)}</div>
            <div class='eg-notice-body'>{html.escape(body)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _eg_render_identity_card(policy_no: str, claim_no: str, source_business: str, insured_name: str, found: bool) -> None:
    status_cls = "found" if found else "missing"
    status_text = "Data Risk Profile found" if found else "Waiting for valid policy"
    st.markdown(
        f"""
        <div class='eg-identity-card'>
          <div class='eg-identity-top'>
            <div>
              <div class='eg-overline'>Auto-filled from Risk Profile</div>
              <div class='eg-identity-title'>{html.escape(insured_name or 'Nama Tertanggung belum tersedia')}</div>
              <div class='eg-identity-sub'>Policy No: <b>{html.escape(policy_no or '-')}</b> &nbsp; | &nbsp; Claim No: <b>{html.escape(claim_no or '-')}</b></div>
            </div>
            <div class='eg-status-pill {status_cls}'>{html.escape(status_text)}</div>
          </div>
          <div class='eg-identity-grid'>
            <div class='eg-mini-card'><span>Sumber Bisnis</span><b>{html.escape(source_business or '-')}</b></div>
            <div class='eg-mini-card'><span>Nama Tertanggung</span><b>{html.escape(insured_name or '-')}</b></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def _record_to_form_data(rec: dict) -> dict:
    return {
        "claim_no": rec.get("CLAIM_NO", ""),
        "policy_no": rec.get("POLICY_NO", ""),
        "policy_uw_year": rec.get("POLICY_UW_YEAR", ""),
        "cob": rec.get("COB", ""),
        "source_business": rec.get("SOURCE_BUSINESS", ""),
        "insured_name": rec.get("INSURED_NAME", ""),
        "loss_date": rec.get("LOSS_DATE", ""),
        "claim_amount": _safe_to_float(rec.get("CLAIM_AMOUNT", 0), 0),
        "loss_cause": rec.get("LOSS_CAUSE", ""),
        "exgratia_reason": rec.get("EXGRATIA_REASON", ""),
        "exgratia_amount": _safe_to_float(rec.get("EXGRATIA_AMOUNT", 0), 0),
        "mnc_share": rec.get("MNC_SHARE", ""),
        "future_business": rec.get("FUTURE_BUSINESS", ""),
    }


def _scenario_summary_updates_for_record(rec: dict) -> dict:

    rec = dict(rec or {})
    risk_df = load_risk_profile_data(tuple(EXGRATIA_RISK_DATASET_FILES))
    policy_no = str(rec.get("POLICY_NO", "") or "").strip()
    target_uw_year = rec.get("POLICY_UW_YEAR")
    if target_uw_year in (None, ""):
        target_uw_year = _policy_uw_year(risk_df, policy_no)
    if target_uw_year is None:
        raise RuntimeError(f"UW Year untuk polis {policy_no or '-'} tidak ditemukan.")

    ovr_context = _ovr_context_from_json(rec.get("OVR_CONTEXT_JSON", "{}"))
    processed_df = apply_ovr_to_df(
        risk_df,
        ovr_context.get("mode", "uniform"),
        ovr_context.get("uniform_pct", 0.0),
        ovr_context.get("dims", []) or [],
        ovr_context.get("rules_df") if isinstance(ovr_context.get("rules_df"), pd.DataFrame) else pd.DataFrame(),
    )
    display_unit = rec.get("DISPLAY_UNIT", "in IDR Mio") or "in IDR Mio"
    exg = _safe_to_float(rec.get("EXGRATIA_AMOUNT", 0), 0.0)
    source_business = str(rec.get("SOURCE_BUSINESS", "") or "").strip()
    insured_name = str(rec.get("INSURED_NAME", "") or "").strip()
    int_col = _resolve_col(risk_df, "INTERMEDIARY_NAME")
    ins_col = _resolve_col(risk_df, "INSURED_NAME")

    intermediary_summary = make_entity_performance_summary(
        processed_df, int_col, source_business, last_n_years=None,
        display_unit=display_unit, start_year=2023,
        target_uw_year=target_uw_year, exgratia_amount=exg,
        proxy_entities=ovr_context.get("proxy_intermediaries", []),
    ) if source_business and int_col else pd.DataFrame(columns=EXGRATIA_PERFORMANCE_COLUMNS)
    insured_summary = make_entity_performance_summary(
        processed_df, ins_col, insured_name, last_n_years=None,
        display_unit=display_unit, start_year=2023,
        target_uw_year=target_uw_year, exgratia_amount=exg,
        proxy_entities=ovr_context.get("insured_group", []),
    ) if insured_name and ins_col else pd.DataFrame(columns=EXGRATIA_PERFORMANCE_COLUMNS)

    return {
        "POLICY_UW_YEAR": _record_text(target_uw_year),
        "INTERMEDIARY_SUMMARY_JSON": _df_to_json(intermediary_summary),
        "INSURED_SUMMARY_JSON": _df_to_json(insured_summary),
    }


def _summary_has_exgratia_scenario(df: pd.DataFrame) -> bool:
    return isinstance(df, pd.DataFrame) and {
        "LOSS RATIO EXISTING", "LOSS RATIO + EX-GRATIA",
        "COMBINED RATIO EXISTING", "COMBINED RATIO + EX-GRATIA",
    }.issubset(df.columns)


def _record_required_bod_fields() -> list[tuple[str, str, str]]:
    fields = []
    if BOD_MARKETING_EMAIL:
        fields.append((BOD_MARKETING_EMAIL, "DIR_MARKETING_CONFIRMED_BY", "DIR_MARKETING_CONFIRMED_AT"))
    if BOD_TEKNIK_EMAIL:
        fields.append((BOD_TEKNIK_EMAIL, "DIR_TEKNIK_CONFIRMED_BY", "DIR_TEKNIK_CONFIRMED_AT"))
    if BOD_UTAMA_EMAIL:
        fields.append((BOD_UTAMA_EMAIL, "DIR_UTAMA_CONFIRMED_BY", "DIR_UTAMA_CONFIRMED_AT"))
    return fields


def _is_all_required_bod_confirmed(rec: dict) -> bool:
    required = _record_required_bod_fields()
    if not required:
        return False
    return all(str(rec.get(by_col, "")).strip() for _, by_col, _ in required)


def _build_record_pdf_bytes(rec: dict) -> bytes:

    rec = dict(rec or {})
    doc_id = _sanitize_doc_id(rec.get("DOC_ID", ""))
    display_unit = rec.get("DISPLAY_UNIT", "in IDR Mio") or "in IDR Mio"
    username = str(rec.get("LAST_UPDATED_BY") or rec.get("CREATED_BY") or "")

    intermediary_summary = _json_to_df(rec.get("INTERMEDIARY_SUMMARY_JSON", "[]"))
    insured_summary = _json_to_df(rec.get("INSURED_SUMMARY_JSON", "[]"))



    if not _summary_has_exgratia_scenario(intermediary_summary) or not _summary_has_exgratia_scenario(insured_summary):
        try:
            scenario_updates = _scenario_summary_updates_for_record(rec)
            rec.update(scenario_updates)
            intermediary_summary = _json_to_df(rec.get("INTERMEDIARY_SUMMARY_JSON", "[]"))
            insured_summary = _json_to_df(rec.get("INSURED_SUMMARY_JSON", "[]"))
        except Exception:
            intermediary_summary = _normalise_performance_summary_schema(intermediary_summary)
            insured_summary = _normalise_performance_summary_schema(insured_summary)


    if not str(rec.get("POLICY_UW_YEAR", "") or "").strip():
        try:
            risk_df = load_risk_profile_data(tuple(EXGRATIA_RISK_DATASET_FILES))
            rec["POLICY_UW_YEAR"] = _record_text(_policy_uw_year(risk_df, rec.get("POLICY_NO", "")))
        except Exception:
            pass

    form_data = _record_to_form_data(rec)
    ovr_context = _ovr_context_from_json(rec.get("OVR_CONTEXT_JSON", "{}"))
    return build_exgratia_pdf(
        form_data,
        intermediary_summary,
        insured_summary,
        display_unit,
        username,
        doc_id,
        ovr_context,
        rec,
    )


def _render_record_pdf_download(rec: dict, username: str, pdf_bytes: bytes | None = None) -> None:

    doc_id = _sanitize_doc_id(rec.get("DOC_ID", ""))
    try:
        pdf = pdf_bytes if pdf_bytes is not None else _build_record_pdf_bytes(rec)
        _download_link(
            f"Download PDF - {doc_id}",
            pdf,
            f"ex_gratia_{doc_id}.pdf",
            "application/pdf",
        )
    except Exception as e:
        st.error(f"Gagal membuat PDF: {e}")


def _render_record_pdf_preview(
    rec: dict,
    selected_doc: str,
    username: str,
    height: int = 900,
) -> bytes | None:












    try:
        pdf_bytes = _build_record_pdf_bytes(rec)
    except Exception as exc:
        st.error(f"Gagal membuat preview PDF: {exc}")
        return None

    if not pdf_bytes:
        st.error("PDF preview kosong: tidak ada PDF bytes yang berhasil dibuat.")
        return None

    st.markdown("### Document Preview")

    native_error = ""


    if hasattr(st, "pdf"):
        try:
            st.pdf(
                io.BytesIO(pdf_bytes),
                height=int(height),
                key=f"eg_pdf_preview_{_sanitize_doc_id(selected_doc)}",
            )
            return pdf_bytes
        except Exception as exc:
            native_error = f"{type(exc).__name__}: {exc}"




    try:
        safe_doc_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", _sanitize_doc_id(selected_doc) or "document")
        preview_path = Path(tempfile.gettempdir()) / f"ex_gratia_preview_{safe_doc_id}.pdf"
        preview_path.write_bytes(pdf_bytes)

        if hasattr(st, "iframe"):
            st.iframe(
                preview_path,
                height=int(height),
                width="stretch",
            )
            return pdf_bytes



        st.warning(
            "PDF viewer belum tersedia pada versi Streamlit ini. "
            + (f"Native viewer error: {native_error}" if native_error else "")
        )
    except Exception as exc:
        fallback_error = f"{type(exc).__name__}: {exc}"
        details = []
        if native_error:
            details.append(f"st.pdf: {native_error}")
        details.append(f"fallback viewer: {fallback_error}")
        st.error(
            "PDF berhasil dibuat, tetapi viewer tidak bisa menampilkannya. "
            + " | ".join(details)
        )

    return pdf_bytes



def _workflow_visible_records(df: pd.DataFrame, role: str, username: str) -> pd.DataFrame:

    if df is None or df.empty:
        return pd.DataFrame(columns=EXGRATIA_RECORD_HEADERS)

    out = df.copy()
    role = str(role or "").strip().lower()
    username_l = _normalize_email(username)
    status = out.get("STATUS", pd.Series([""] * len(out), index=out.index)).astype(str).str.lower()
    cob = out.get("COB", pd.Series([""] * len(out), index=out.index)).astype(str).str.upper().str.strip()

    def eq_col(col: str) -> pd.Series:
        series = out.get(col, pd.Series([""] * len(out), index=out.index))
        return series.map(lambda value: _same_user_identity(username, value))

    creator_history = eq_col("CREATED_BY")
    corresponding_history = eq_col("CORRESPONDING_EMAIL") | eq_col("SEND_BACK_TO")
    manager_history = eq_col("MARKETING_MANAGER_EMAIL")
    send_back_by_me = eq_col("SEND_BACK_BY")
    declined_by_me = eq_col("DECLINED_BY")




    if role == "marketing":
        return out[creator_history | manager_history | corresponding_history].copy()

    if role == "claim-mv":
        relevant = cob.eq("MV") & (
            status.str.contains("pending klaim", na=False)
            | eq_col("CLAIM_CONFIRMED_BY")
            | send_back_by_me
            | declined_by_me
        )
        return out[creator_history | relevant | manager_history | corresponding_history].copy()

    if role == "claim-nonmv":
        relevant = ~cob.eq("MV") & (
            status.str.contains("pending klaim", na=False)
            | eq_col("CLAIM_CONFIRMED_BY")
            | send_back_by_me
            | declined_by_me
        )
        return out[creator_history | relevant | manager_history | corresponding_history].copy()

    is_dirmkt = username_l == BOD_MARKETING_EMAIL.lower() or role in {"direktur marketing", "dirmkt", "director marketing"}
    is_dirtek = username_l == BOD_TEKNIK_EMAIL.lower() or role in {"direktur teknik", "dirtek", "director teknik", "technical director"}

    if is_dirmkt:
        relevant = (
            status.str.contains("pending dirmkt", na=False)
            | eq_col("DIR_MARKETING_CONFIRMED_BY")
            | send_back_by_me
            | declined_by_me
        )
        return out[creator_history | relevant | manager_history | corresponding_history].copy()

    if is_dirtek:
        relevant = (
            status.str.contains("pending dirtek", na=False)
            | eq_col("DIR_TEKNIK_CONFIRMED_BY")
            | send_back_by_me
            | declined_by_me
        )
        return out[creator_history | relevant | manager_history | corresponding_history].copy()

    if role == "bod":
        if username_l == BOD_MARKETING_EMAIL.lower():
            return out[
                creator_history
                | status.str.contains("pending dirmkt", na=False)
                | eq_col("DIR_MARKETING_CONFIRMED_BY")
                | send_back_by_me
                | declined_by_me
                | corresponding_history
            ].copy()
        if username_l == BOD_TEKNIK_EMAIL.lower():
            return out[
                creator_history
                | status.str.contains("pending dirtek", na=False)
                | eq_col("DIR_TEKNIK_CONFIRMED_BY")
                | send_back_by_me
                | declined_by_me
                | corresponding_history
            ].copy()



    return out[creator_history | manager_history | corresponding_history].copy()

def _workflow_display_dataframe(visible: pd.DataFrame) -> pd.DataFrame:

    if visible is None or visible.empty:
        return pd.DataFrame()
    cols = [
        "DOC_ID", "STATUS", "CLAIM_NO", "POLICY_NO", "COB", "INSURED_NAME",
        "CREATED_BY", "CREATED_AT", "LAST_UPDATED_BY",
    ]


    cols = [c for c in cols if c in visible.columns]
    out = visible[cols].copy()
    rename = {
        "DOC_ID": "Document ID",
        "STATUS": "Status",
        "CLAIM_NO": "No. Klaim",
        "POLICY_NO": "No. Polis",
        "COB": "COB",
        "INSURED_NAME": "Tertanggung",
        "CREATED_BY": "Created By",
        "CREATED_AT": "Created At",
        "LAST_UPDATED_BY": "Last Updated By",
    }
    return out.rename(columns=rename)


def _render_exgratia_table_css() -> None:
    st.markdown(f"""
    <style>
      .eg-workflow-title{{
        margin: 8px 0 6px 0;
        color:{NAVY};
        font-size:26px;
        font-weight:950;
        letter-spacing:-0.04em;
      }}
      .eg-workflow-sub{{
        margin:0 0 14px 0;
        color:#64748B;
        font-size:13px;
        line-height:1.45;
      }}
      .eg-workflow-toolbar{{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:12px;
        padding:13px 15px;
        border-radius:20px;
        background:
          radial-gradient(circle at 94% 20%, rgba(31,90,145,0.10) 0, rgba(31,90,145,0.00) 30%),
          linear-gradient(135deg,#FFFFFF 0%,#F5F8FD 100%);
        border:1px solid rgba(0,51,102,0.13);
        box-shadow:0 12px 28px rgba(15,23,42,0.055);
        margin:10px 0 12px 0;
      }}
      .eg-workflow-chip{{
        display:inline-flex;
        align-items:center;
        gap:7px;
        padding:7px 12px;
        border-radius:999px;
        background:#EEF6FF;
        color:{NAVY};
        border:1px solid rgba(0,51,102,0.14);
        font-size:12px;
        font-weight:900;
      }}
      .eg-exec-table-wrap{{
        position:relative;
        overflow:hidden;
        border-radius:24px;
        border:1px solid rgba(0,51,102,0.13);
        background:linear-gradient(180deg,#FFFFFF 0%,#F7FAFD 100%);
        box-shadow:0 18px 42px rgba(15,23,42,0.075);
        margin: 12px 0 14px 0;
      }}
      .eg-exec-table-wrap::before{{
        content:"";
        display:block;
        height:5px;
        background:linear-gradient(90deg,#003366 0%,#1F5A91 52%,#66AAD1 100%);
      }}
      .eg-exec-scroll{{
        overflow-x:auto;
        padding:14px;
      }}
      .eg-exec-table{{
        min-width:1180px;
      }}
      .eg-exec-header,
      .eg-exec-row{{
        display:grid;
        grid-template-columns: 92px 1.18fr 1.05fr .58fr 1.1fr 2.35fr 1.35fr 1.15fr;
        gap:0;
        align-items:center;
      }}
      .eg-exec-header{{
        border-radius:16px 16px 0 0;
        overflow:hidden;
        background:linear-gradient(180deg,#003366 0%,#002B57 100%);
        color:white;
        box-shadow:0 8px 20px rgba(0,51,102,0.16);
      }}
      .eg-exec-th{{
        color:white;
        font-size:11px;
        font-weight:950;
        letter-spacing:.045em;
        text-transform:uppercase;
        line-height:1.15;
        padding:13px 14px;
        border-right:1px solid rgba(255,255,255,0.12);
        white-space:nowrap;
        overflow:hidden;
        text-overflow:ellipsis;
      }}
      .eg-exec-row{{
        min-height:56px;
        background:#FFFFFF;
        border-left:1px solid rgba(0,51,102,0.08);
        border-right:1px solid rgba(0,51,102,0.08);
        border-bottom:1px solid rgba(0,51,102,0.08);
      }}
      .eg-exec-row:nth-child(odd){{background:#F8FBFF;}}
      .eg-exec-row:last-child{{border-radius:0 0 16px 16px; overflow:hidden;}}
      .eg-exec-row:hover{{background:#EEF6FF;}}
      .eg-exec-td{{
        padding:11px 14px;
        font-size:12.3px;
        color:#253858;
        font-weight:730;
        line-height:1.22;
        overflow:hidden;
        text-overflow:ellipsis;
        white-space:nowrap;
        border-right:1px solid rgba(15,23,42,0.045);
      }}
      .eg-exec-td .muted{{color:#64748B;font-weight:650;}}
      .eg-doc-code{{
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        color:#0F2742;
        font-weight:950;
        letter-spacing:-.02em;
      }}
      .eg-open-link{{
        display:inline-flex;
        align-items:center;
        justify-content:center;
        height:32px;
        padding:0 14px;
        border-radius:999px;
        background:linear-gradient(135deg,#003366 0%,#1F5A91 100%);
        color:#FFFFFF !important;
        text-decoration:none !important;
        font-size:12px;
        font-weight:950;
        box-shadow:0 8px 18px rgba(0,51,102,0.16);
      }}
      .eg-open-link:hover{{filter:brightness(1.05); transform:translateY(-1px);}}
      .eg-status-badge{{
        display:flex;
        align-items:center;
        justify-content:center;
        width:100%;
        max-width:100%;
        min-height:30px;
        padding:5px 8px;
        border-radius:12px;
        font-size:10.5px;
        font-weight:950;
        line-height:1.15;
        text-align:center;
        white-space:normal;
        overflow-wrap:anywhere;
        box-sizing:border-box;
      }}
      .eg-status-claim{{background:#FFF3D6;color:#7C4A03;border:1px solid rgba(124,74,3,.18);}}
      .eg-status-reinsurance{{background:#EAF1FB;color:#1F5A91;border:1px solid rgba(31,90,145,.18);}}
      .eg-status-bod{{background:#F3E8FF;color:#6B21A8;border:1px solid rgba(107,33,168,.16);}}
      .eg-status-approved{{background:#E8F7EF;color:#166534;border:1px solid rgba(22,101,52,.18);}}
      .eg-status-default{{background:#EEF2F7;color:#475569;border:1px solid rgba(71,85,105,.16);}}
      .eg-exec-native-wrap{{
        position:relative;
        overflow:hidden;
        border-radius:24px;
        border:1px solid rgba(0,51,102,0.13);
        background:linear-gradient(180deg,#FFFFFF 0%,#F7FAFD 100%);
        box-shadow:0 18px 42px rgba(15,23,42,0.075);
        margin:12px 0 14px 0;
        padding:14px;
      }}
      .eg-exec-native-topbar{{
        height:5px;
        margin:-14px -14px 14px -14px;
        background:linear-gradient(90deg,#003366 0%,#1F5A91 52%,#66AAD1 100%);
      }}
      /* Header and body use identical native containers and column geometry. */
      div[class*="st-key-eg_exec_header"],
      div[class*="st-key-eg_exec_row_"]{{
        padding:10px 12px !important;
        border:1px solid rgba(0,51,102,0.10) !important;
        border-radius:12px !important;
        box-sizing:border-box !important;
      }}
      div[class*="st-key-eg_exec_header"]{{
        background:linear-gradient(180deg,#003366 0%,#002B57 100%) !important;
        border-color:#003366 !important;
        height:auto !important;
        min-height:48px !important;
        max-height:none !important;
        flex-shrink:0 !important;
        overflow:visible !important;
      }}
      /* Streamlit measures nested blocks independently. Keep the header's
         content in normal flow so padding cannot clip its measured height. */
      div[class*="st-key-eg_exec_header"] [data-testid="stVerticalBlock"],
      div[class*="st-key-eg_exec_header"] [data-testid="stHorizontalBlock"],
      div[class*="st-key-eg_exec_header"] [data-testid="stColumn"],
      div[class*="st-key-eg_exec_header"] [data-testid="stElementContainer"],
      div[class*="st-key-eg_exec_header"] [data-testid="stMarkdownContainer"]{{
        height:auto !important;
        max-height:none !important;
        min-height:0 !important;
        overflow:visible !important;
        flex-shrink:0 !important;
      }}
      div[class*="st-key-eg_exec_header"] [data-testid="stHorizontalBlock"]{{
        align-items:center !important;
      }}
      div[class*="st-key-eg_exec_header"] [data-testid="stMarkdownContainer"] p{{
        margin:0 !important;
      }}
      .eg-native-heading{{
        color:#FFFFFF;
        font-size:11px;
        font-weight:950;
        letter-spacing:.045em;
        text-transform:uppercase;
        white-space:normal;
        overflow:visible;
        overflow-wrap:normal;
        line-height:1.4;
        min-height:20px;
        margin:0;
        padding:2px 0;
        box-sizing:border-box;
      }}
      div[class*="st-key-eg_exec_table_shell"] > div[data-testid="stVerticalBlockBorderWrapper"]{{
        position:relative;
        overflow:hidden;
        border-radius:24px !important;
        border:1px solid rgba(0,51,102,0.13) !important;
        background:linear-gradient(180deg,#FFFFFF 0%,#F7FAFD 100%) !important;
        box-shadow:0 18px 42px rgba(15,23,42,0.075) !important;
        padding:14px !important;
        margin:12px 0 14px 0 !important;
      }}
      div[class*="st-key-eg_exec_row_"]:hover{{
        background:#EEF6FF !important;
        border-color:rgba(0,51,102,0.18) !important;
      }}
      .eg-native-cell{{
        color:#253858;
        font-size:12.3px;
        font-weight:730;
        line-height:1.25;
        white-space:nowrap;
        overflow:hidden;
        text-overflow:ellipsis;
      }}
      .eg-native-cell.strong{{font-weight:850;color:#0F2742;}}
      .eg-native-cell.muted{{color:#64748B;font-weight:650;}}
      .eg-native-doc{{
        font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;
        color:#0F2742;
        font-size:12.3px;
        font-weight:950;
        white-space:nowrap;
        overflow:hidden;
        text-overflow:ellipsis;
      }}
      .eg-table-footnote{{
        margin:8px 2px 0 2px;
        color:#7A8494;
        font-size:12px;
        line-height:1.4;
      }}
      div[class*="st-key-eg_open_doc_"] button{{
        min-height:32px !important;
        height:32px !important;
        padding:0 10px !important;
        border-radius:999px !important;
        font-size:11.5px !important;
        font-weight:900 !important;
        white-space:nowrap !important;
        word-break:keep-all !important;
        line-height:1 !important;
        background:linear-gradient(135deg,#003366 0%,#1F5A91 100%) !important;
        color:#FFFFFF !important;
        border:1px solid rgba(0,51,102,0.55) !important;
        box-shadow:0 8px 18px rgba(0,51,102,0.16) !important;
      }}
      div[class*="st-key-eg_create_proposal_btn"] button{{
        min-height:40px !important;
        height:40px !important;
        padding:0 16px !important;
        border-radius:12px !important;
        font-size:13px !important;
        font-weight:850 !important;
        background:linear-gradient(135deg,#003366 0%,#1F5A91 100%) !important;
        color:white !important;
      }}
      div[class*="st-key-eg_back_to_inbox_btn"] button{{
        min-height:36px !important;
        height:36px !important;
        padding:0 14px !important;
        border-radius:11px !important;
        font-size:12.5px !important;
        font-weight:800 !important;
        background:#EEF6FF !important;
        color:{NAVY} !important;
        border:1px solid rgba(0,51,102,0.14) !important;
      }}
    </style>
    """, unsafe_allow_html=True)


def _status_badge_html(status: str) -> str:
    txt = str(status or "-").strip()
    low = txt.lower()
    if "approved" in low:
        cls = "eg-status-approved"
    elif "bod" in low:
        cls = "eg-status-bod"
    elif "reinsurance" in low:
        cls = "eg-status-reinsurance"
    elif "klaim" in low or "claim" in low:
        cls = "eg-status-claim"
    else:
        cls = "eg-status-default"
    return f"<span class='eg-status-badge {cls}'>{html.escape(txt)}</span>"


def _short_cell(value, max_len: int = 34) -> str:
    txt = str(value or "-").strip() or "-"
    return txt if len(txt) <= max_len else txt[:max_len - 1] + "…"


def _render_exec_workflow_row(rec: dict, row_no: int, page_name: str = "ex-Gratia") -> str:






    from urllib.parse import quote

    doc_id = str(rec.get("DOC_ID", "")).strip()
    if not doc_id:
        return ""

    href = f"?page={quote(page_name)}&eg_doc={quote(doc_id)}"
    cells = [
        f"<a class='eg-open-link' href='{html.escape(href)}'>Open</a>",
        f"<span class='eg-doc-code' title='{html.escape(doc_id)}'>{html.escape(_short_cell(doc_id, 20))}</span>",
        _status_badge_html(rec.get("STATUS", "-")),
        html.escape(_short_cell(rec.get("COB", "-"), 10)),
        f"<span title='{html.escape(str(rec.get('POLICY_NO', '-')))}'>{html.escape(_short_cell(rec.get('POLICY_NO', '-'), 26))}</span>",
        f"<span title='{html.escape(str(rec.get('INSURED_NAME', '-')))}'>{html.escape(_short_cell(rec.get('INSURED_NAME', '-'), 48))}</span>",
        f"<span class='muted' title='{html.escape(str(rec.get('CREATED_BY', '-')))}'>{html.escape(_short_cell(rec.get('CREATED_BY', '-'), 26))}</span>",
        f"<span class='muted' title='{html.escape(str(rec.get('CREATED_AT', '-')))}'>{html.escape(_short_cell(rec.get('CREATED_AT', '-'), 20))}</span>",
    ]
    return "<div class='eg-exec-row'>" + "".join(f"<div class='eg-exec-td'>{c}</div>" for c in cells) + "</div>"

def _select_exgratia_doc(doc_id: str) -> None:

    doc_id = _sanitize_doc_id(doc_id)
    st.session_state["eg_selected_doc_id"] = doc_id
    st.session_state["eg_create_mode"] = False
    st.session_state["eg_preparing_create"] = False
    _set_exgratia_url_state("detail", doc_id)


def _return_to_exgratia_list() -> None:

    st.session_state.pop("eg_selected_doc_id", None)
    st.session_state["eg_create_mode"] = False
    st.session_state["eg_preparing_create"] = False
    st.session_state["eg_add_corresponding_email"] = False
    st.session_state.pop("eg_corresponding_email", None)
    _clear_generated_pdf()
    _set_exgratia_url_state("list")


def _enter_exgratia_create_mode() -> None:

    st.session_state.pop("eg_selected_doc_id", None)
    st.session_state["eg_create_mode"] = True
    st.session_state["eg_preparing_create"] = True
    st.session_state["eg_add_corresponding_email"] = False
    st.session_state.pop("eg_corresponding_email", None)
    _clear_generated_pdf()
    _set_exgratia_url_state("create")


def _exit_exgratia_create_mode() -> None:

    _return_to_exgratia_list()



def _install_exgratia_splitter(default_width: int) -> None:






    script = r"""
    <script>
    (() => {
      let attempts = 0;
      const timer = setInterval(() => {
        if (++attempts > 40) { clearInterval(timer); return; }
        try {
          const doc = window.parent.document;
          const marker = doc.getElementById('eg-pdf-pane-marker');
          const left = marker && marker.closest('[data-testid="stColumn"]');
          const row = left && left.parentElement;
          const cols = row && Array.from(row.children).filter(e => e.matches('[data-testid="stColumn"]'));
          if (!cols || cols.length !== 2) return;
          clearInterval(timer);
          if (row._egSplitCleanup) row._egSplitCleanup();
          const right = cols[1];
          let pct = DEFAULT_WIDTH;
          try {
            const saved = JSON.parse(window.parent.sessionStorage.getItem('eg-panel-split') || 'null');
            if (saved && saved.base === DEFAULT_WIDTH && Number.isFinite(saved.pct)) pct = saved.pct;
          } catch (_) {}
          pct = Math.max(25, Math.min(75, pct));
          const handle = doc.createElement('div');
          handle.setAttribute('role', 'separator');
          handle.setAttribute('aria-label', 'Resize PDF and Notes');
          handle.setAttribute('aria-orientation', 'vertical');
          handle.setAttribute('aria-valuemin', '25');
          handle.setAttribute('aria-valuemax', '75');
          handle.tabIndex = 0;
          handle.title = 'Drag to resize PDF / Notes';
          handle.style.cssText = 'position:absolute;top:0;bottom:0;width:12px;cursor:col-resize;touch-action:none;z-index:20;border-left:2px solid #94a3b8;';
          row.style.position = 'relative';
          row.appendChild(handle);
          const apply = () => {
            if (window.parent.innerWidth < 768) {
              handle.style.display = 'none';
              left.style.removeProperty('flex'); right.style.removeProperty('flex');
              left.style.removeProperty('min-width'); right.style.removeProperty('min-width');
              return;
            }
            handle.style.display = 'block';
            const gap = parseFloat(window.parent.getComputedStyle(row).columnGap) || 0;
            const available = row.clientWidth - gap;
            left.style.setProperty('flex', `0 0 ${available*pct/100}px`, 'important');
            right.style.setProperty('flex', `0 0 ${available*(100-pct)/100}px`, 'important');
            left.style.setProperty('min-width', '0', 'important');
            right.style.setProperty('min-width', '0', 'important');
            handle.style.left = `${available*pct/100 + gap/2 - 6}px`;
            handle.setAttribute('aria-valuenow', String(Math.round(pct)));
          };
          const save = () => { try { window.parent.sessionStorage.setItem('eg-panel-split', JSON.stringify({base: DEFAULT_WIDTH, pct})); } catch (_) {} };
          let shield = null;
          const stop = () => {
            if (shield) { shield.remove(); shield = null; }
            doc.removeEventListener('pointermove', move);
            doc.removeEventListener('pointerup', stop);
            doc.removeEventListener('pointercancel', stop);
            window.parent.removeEventListener('blur', stop);
            save();
          };
          const move = e => {
            const rect = row.getBoundingClientRect();
            pct = Math.max(25, Math.min(75, (e.clientX-rect.left)/rect.width*100));
            apply();
          };
          handle.addEventListener('pointerdown', e => {
            e.preventDefault();
            shield = doc.createElement('div');
            shield.style.cssText = 'position:fixed;inset:0;z-index:2147483647;cursor:col-resize;touch-action:none;';
            doc.body.appendChild(shield);
            doc.addEventListener('pointermove', move);
            doc.addEventListener('pointerup', stop);
            doc.addEventListener('pointercancel', stop);
            window.parent.addEventListener('blur', stop);
          });
          handle.addEventListener('keydown', e => {
            if (!['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
            e.preventDefault(); pct = Math.max(25, Math.min(75, pct + (e.key === 'ArrowLeft' ? -2 : 2))); apply(); save();
          });
          const observer = new window.parent.ResizeObserver(apply);
          observer.observe(row);
          window.parent.addEventListener('resize', apply);
          row._egSplitCleanup = () => { stop(); observer.disconnect(); window.parent.removeEventListener('resize', apply); handle.remove(); };
          const detach = new window.parent.MutationObserver(() => {
            if (!row.isConnected) { row._egSplitCleanup(); detach.disconnect(); }
          });
          detach.observe(doc.body, {childList:true, subtree:true});
          const cleanup = row._egSplitCleanup;
          row._egSplitCleanup = () => { cleanup(); detach.disconnect(); };
          apply();
        } catch (_) { clearInterval(timer); }
      }, 100);
    })();
    </script>
    """
    components.html(script.replace("DEFAULT_WIDTH", str(int(default_width))), height=0)

def _render_exgratia_record_detail(
    rec: dict,
    selected_doc: str,
    username: str,
    role: str,
) -> None:





    _render_eg_flash()

    now = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")
    status_l = str(rec.get("STATUS", "")).strip().lower()
    username_l = _normalize_email(username)
    terminal = _is_terminal_status(status_l)
    corresponding_email = _normalize_email(rec.get("CORRESPONDING_EMAIL", ""))
    created_by_identity = str(rec.get("CREATED_BY", "") or "").strip()



    created_by_me = _is_record_creator(rec, username)




    current_stage_l = str(rec.get("CURRENT_STAGE", "") or "").strip().lower()
    send_back_at = str(rec.get("SEND_BACK_AT", "") or "").strip()
    send_back_resolved_at = str(rec.get("SEND_BACK_RESOLVED_AT", "") or "").strip()
    unresolved_send_back = bool(send_back_at and not send_back_resolved_at)
    pending_edit = (
        current_stage_l == "corresponding_edit"
        or "pending corresponding edit" in status_l
        or "pending creator edit" in status_l
        or ("send back" in status_l and not terminal)
        or unresolved_send_back
    )
    can_creator_edit = created_by_me and (not terminal or "approved" in status_l)
    edit_mode_key = f"eg_direct_edit_{selected_doc}"
    is_creator_editor = can_creator_edit and (pending_edit or st.session_state.get(edit_mode_key, False))
    manager_assigned = (
        _normalize_email(rec.get("MARKETING_MANAGER_EMAIL", "")) == username_l
        and "pending marketing manager" in status_l
    )
    is_dirmkt = username_l == BOD_MARKETING_EMAIL.lower() or role in {"direktur marketing", "dirmkt", "director marketing"}
    is_dirtek = username_l == BOD_TEKNIK_EMAIL.lower() or role in {"direktur teknik", "dirtek", "director teknik", "technical director"}
    is_claim_role = role in {"claim-mv", "claim-nonmv"} or role.startswith("claim")

    red_note = False
    with st.expander("Atur lebar PDF / Notes", expanded=False):
        pdf_width = st.slider("Lebar PDF (%)", 25, 75, 61, key="eg_pdf_width_pct")
    st.caption("Geser garis pembatas PDF dan Notes untuk mengatur lebar panel.")



    preview_col, action_col = st.columns(
        [pdf_width, 100 - pdf_width],
        gap="large",
        vertical_alignment="top",
    )

    with preview_col:
        st.markdown('<span id="eg-pdf-pane-marker"></span>', unsafe_allow_html=True)
        preview_pdf_bytes = _render_record_pdf_preview(
            rec,
            selected_doc,
            username,
            height=980,
        )

    def _notes_json(action: str, stage: str, note: str) -> str:
        return _append_workflow_note(
            json.dumps(_workflow_notes_for_display(rec), ensure_ascii=False),
            username,
            action,
            stage,
            note,
            now,
            is_red=red_note,
        )

    def _decline_updates(note: str, actor_label: str, stage: str) -> dict:
        return {
            "STATUS": f"declined by {actor_label}",
            "CURRENT_STAGE": "declined",
            "DECLINED_BY": username,
            "DECLINED_AT": now,
            "DECLINE_NOTE": _limit_narrative_text(note),
            "WORKFLOW_NOTES_JSON": _notes_json("Decline", stage, note),
            "LAST_UPDATED_BY": username,
        }

    def _send_back_updates(note: str, stage_label: str) -> tuple[dict | None, str]:
        if not created_by_identity:
            return None, "CREATED_BY tidak tersedia pada record ini."
        clean_note = _limit_narrative_text(note)
        if not clean_note:
            return None, "Notes wajib diisi untuk Send Back."
        return {
            "STATUS": "pending creator edit",
            "CURRENT_STAGE": "corresponding_edit",
            "SEND_BACK_BY": username,
            "SEND_BACK_AT": now,
            "SEND_BACK_NOTE": clean_note,
            "SEND_BACK_STAGE": str(rec.get("CURRENT_STAGE", "") or ""),
            "SEND_BACK_RETURN_STATUS": str(rec.get("STATUS", "") or ""),
            "SEND_BACK_TO": created_by_identity,
            "SEND_BACK_RESOLVED_BY": "",
            "SEND_BACK_RESOLVED_AT": "",
            "WORKFLOW_NOTES_JSON": _notes_json("Send Back", stage_label, clean_note),
            "LAST_UPDATED_BY": username,
        }, ""

    def _apply_send_back(note: str, stage_label: str) -> None:
        updates, err = _send_back_updates(note, stage_label)
        if not updates:
            st.error(err)
            return
        ok2, msg = _update_exgratia_record(selected_doc, updates)
        if not ok2:
            st.error(msg)
            return
        rec_after = dict(rec)
        rec_after.update(updates)
        mail_ok, mail_msg = _notify_pending_exgratia_if_needed(rec_after)
        if mail_ok:
            _set_eg_flash("success", f"Dokumen dikirim kembali ke pembuat pengajuan ({created_by_identity}). {mail_msg}")
        else:
            _set_eg_flash("warning", f"Send Back tersimpan, tetapi email gagal: {mail_msg}")
        st.rerun()

    def _notify_after_approve(rec_after: dict, success_text: str) -> None:
        mail_ok, mail_msg = _notify_pending_exgratia_if_needed(rec_after)
        if mail_ok:
            _set_eg_flash("success", f"{success_text} {mail_msg}")
        else:
            _set_eg_flash("warning", f"{success_text} Email berikutnya gagal: {mail_msg}")
        st.rerun()

    with action_col:
        st.markdown(
            f"""
            <div style="
                padding:16px 17px;
                border-radius:18px;
                border:1px solid rgba(0,51,102,0.12);
                background:linear-gradient(180deg,#FFFFFF 0%,#F7FAFD 100%);
                box-shadow:0 10px 28px rgba(15,23,42,0.055);
                margin-bottom:12px;
            ">
              <div style="
                  font-size:11px;
                  text-transform:uppercase;
                  letter-spacing:.08em;
                  font-weight:850;
                  color:#64748B;
                  margin-bottom:5px;
              ">Document</div>
              <div style="
                  font-size:18px;
                  line-height:1.2;
                  font-weight:900;
                  color:#003366;
                  word-break:break-word;
              ">{html.escape(selected_doc)}</div>
              <div style="margin-top:10px;">
                {_status_badge_html(rec.get("STATUS", "-"))}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        _render_record_pdf_download(
            rec,
            username,
            pdf_bytes=preview_pdf_bytes,
        )





        can_manual_notify = created_by_me or is_claim_role
        if can_manual_notify and not terminal and "pending" in status_l:
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            if st.button(
                "Notify",
                key=f"eg_notify_{selected_doc}",
                width="stretch",
            ):
                ok_mail, mail_msg = _notify_pending_exgratia_if_needed(rec)
                if ok_mail:
                    st.success(mail_msg)
                else:
                    st.error(mail_msg)

        _render_workflow_notes(rec)
        if can_creator_edit and not pending_edit:
            if st.button("Tutup Edit" if is_creator_editor else "Edit Pengajuan", key=f"eg_toggle_edit_{selected_doc}", width="stretch"):
                st.session_state[edit_mode_key] = not is_creator_editor
                st.rerun()

        if terminal and not is_creator_editor:
            if "approved" in status_l:
                st.success("Approved")
            elif "decline" in status_l:
                st.warning("Declined")
            elif "cancel" in status_l:
                st.warning("Canceled")

        elif is_creator_editor:
            st.markdown("### Edit & Resubmit" if pending_edit else "### Edit Pengajuan")
            st.caption(f"Edit owner: {created_by_identity}")
            st.info(
                "Perubahan akan disimpan dan diinformasikan kepada approver yang sudah menyetujui. "
                "Approval sebelumnya tetap berlaku. Jika ada Send Back, dokumen kembali ke approver yang meminta perbaikan."
            )
            try:
                initial_loss_date = pd.to_datetime(rec.get("LOSS_DATE", ""), errors="coerce")
                initial_loss_date = initial_loss_date.date() if pd.notna(initial_loss_date) else date.today()
            except Exception:
                initial_loss_date = date.today()

            edit_ovr_context = _ovr_context_from_json(rec.get("OVR_CONTEXT_JSON", "{}"))
            edit_primary = str(rec.get("SOURCE_BUSINESS", "") or "").strip()
            initial_proxies = [
                name for name in _intermediary_names("", edit_ovr_context.get("proxy_intermediaries", []))
                if name.lower() != edit_primary.lower()
            ]

            edit_proxy_options = list(initial_proxies)
            edit_proxy_available = True
            insured_primary = str(rec.get("INSURED_NAME", "") or "").strip()
            initial_group = [n for n in _intermediary_names("", edit_ovr_context.get("insured_group", [])) if n.lower() != insured_primary.lower()]
            edit_group_options = list(initial_group)
            edit_group_available = False
            try:
                edit_risk_df = load_risk_profile_data(tuple(EXGRATIA_RISK_DATASET_FILES))
                edit_insured_col = _resolve_col(edit_risk_df, "INSURED_NAME")
                if edit_insured_col:
                    edit_group_options = sorted([n for n in _intermediary_names("", initial_group + edit_risk_df[edit_insured_col].dropna().tolist()) if n.lower() != insured_primary.lower()], key=str.lower)
                    edit_group_available = True
                edit_proxy_col = _resolve_col(edit_risk_df, "INTERMEDIARY_NAME")
                if not edit_proxy_col:
                    raise ValueError("Kolom INTERMEDIARY_NAME tidak ditemukan.")
                edit_proxy_options = sorted(
                    [name for name in _intermediary_names(
                        "", initial_proxies + edit_risk_df[edit_proxy_col].dropna().tolist()
                    ) if name.lower() != edit_primary.lower()],
                    key=str.lower,
                )
            except Exception as exc:
                edit_proxy_available = False
                st.warning(f"Pilihan proxy belum dapat dimuat; proxy tersimpan tetap dipertahankan. {exc}")

            with st.form(f"eg_corresponding_edit_{selected_doc}"):
                c1, c2 = st.columns(2)
                with c1:
                    edit_claim_no = st.text_input("No. Klaim", value=str(rec.get("CLAIM_NO", "") or ""))
                    edit_loss_date = st.date_input("Tanggal Kejadian", value=initial_loss_date)
                    edit_claim_amount = st.text_input(
                        "Nilai Klaim yang Diajukan",
                        value=_record_text(rec.get("CLAIM_AMOUNT", "")),
                        help="Disimpan sebagai text agar format seperti 12.258.000 tetap aman.",
                    )
                with c2:
                    edit_exgratia_amount = st.text_input(
                        "Nilai Ex-Gratia",
                        value=_record_text(rec.get("EXGRATIA_AMOUNT", "")),
                        help="Disimpan sebagai text agar format seperti 12.258.000 tetap aman.",
                    )
                    edit_mnc_share = st.text_input("Share MNC", value=str(rec.get("MNC_SHARE", "") or ""))
                    st.text_input("No. Polis", value=str(rec.get("POLICY_NO", "") or ""), disabled=True)

                edit_proxies = st.multiselect(
                    "Add a proxy — Intermediary",
                    options=edit_proxy_options,
                    default=initial_proxies,
                    key=f"eg_edit_proxy_intermediaries_{selected_doc}",
                    disabled=not edit_proxy_available,
                    help="Pilih satu atau beberapa intermediary. Hapus pilihan untuk melepas proxy. Portfolio dan PDF dihitung ulang saat perubahan disimpan.",
                )

                edit_group = st.multiselect("Add insured group", options=edit_group_options,
                                            default=initial_group, key=f"eg_edit_insured_group_{selected_doc}",
                                            disabled=not edit_group_available)
                st.markdown("**OVR (%)**")
                edit_ovr_mode = edit_ovr_context.get("mode", "uniform")
                edit_ovr_rules = edit_ovr_context.get("rules_df")
                edit_ovr_uniform = _safe_to_float(edit_ovr_context.get("uniform_pct", rec.get("OVR_UNIFORM_PCT", 0)), 0)
                if edit_ovr_mode == "rules":
                    st.caption("Edit persentase OVR per kategori. CoR dan PDF dihitung ulang saat disimpan.")
                    if isinstance(edit_ovr_rules, pd.DataFrame) and not edit_ovr_rules.empty:
                        edit_ovr_rules = st.data_editor(
                            edit_ovr_rules.copy(), key=f"eg_edit_ovr_rules_{selected_doc}",
                            hide_index=True, width="stretch",
                            disabled=[c for c in edit_ovr_rules.columns if c != "OVR_PCT_INPUT"],
                            column_config={"OVR_PCT_INPUT": st.column_config.NumberColumn(
                                "OVR (%)", min_value=0.0, max_value=100.0,
                                step=0.000001, format="%.6f", required=True)},
                        )
                    else:
                        st.warning("Detail kategori OVR tidak tersedia pada pengajuan ini.")
                else:
                    edit_ovr_uniform = st.number_input(
                        "OVR untuk semua (%)", value=float(edit_ovr_uniform),
                        min_value=0.0, max_value=100.0, step=0.000001, format="%.6f",
                        key=f"eg_edit_ovr_uniform_{selected_doc}",
                    )

                edit_loss_cause = st.text_area(
                    "Penyebab Kerugian",
                    value=str(rec.get("LOSS_CAUSE", "") or ""),
                    height=95,
                    max_chars=EXGRATIA_MAX_NARRATIVE_CHARS,
                )
                edit_reason = st.text_area(
                    "Alasan Ex-Gratia",
                    value=str(rec.get("EXGRATIA_REASON", "") or ""),
                    height=105,
                    max_chars=EXGRATIA_MAX_NARRATIVE_CHARS,
                )
                edit_future = st.text_area(
                    "Potensi Bisnis yang Akan Datang",
                    value=str(rec.get("FUTURE_BUSINESS", "") or ""),
                    height=120,
                    max_chars=EXGRATIA_MAX_NARRATIVE_CHARS,
                )
                resubmit_note = st.text_area(
                    "Catatan perubahan",
                    height=80,
                    max_chars=EXGRATIA_MAX_NARRATIVE_CHARS,
                )
                revision_red_note = st.checkbox("This is a red notes", key=f"eg_red_revision_{selected_doc}")
                resubmit = st.form_submit_button("Save & Resubmit" if pending_edit else "Simpan Perubahan", type="primary", width="stretch")

            if resubmit:
                return_status = str(rec.get("SEND_BACK_RETURN_STATUS", "") or "").strip()
                return_stage = str(rec.get("SEND_BACK_STAGE", "") or "").strip()



                if not pending_edit:
                    return_status = rec.get("STATUS", "")
                    return_stage = rec.get("CURRENT_STAGE", "") or "edit"

                if pending_edit and not return_stage:
                    sb_by = _normalize_email(rec.get("SEND_BACK_BY", ""))
                    if sb_by == _normalize_email(rec.get("MARKETING_MANAGER_EMAIL", "")):
                        return_stage = "marketing_manager"
                        return_status = return_status or "pending marketing manager"
                    elif sb_by in _get_emails_for_role(_claim_role_for_cob(rec.get("COB", ""))):
                        return_stage = "claim"
                        return_status = return_status or "pending klaim"
                    elif sb_by == BOD_MARKETING_EMAIL.lower():
                        return_stage = "dirmkt"
                        return_status = return_status or "pending dirmkt"
                    elif sb_by == BOD_TEKNIK_EMAIL.lower():
                        return_stage = "dirtek"
                        return_status = return_status or "pending dirtek"

                if not return_status or not return_stage:
                    st.error(
                        "Tahap reviewer yang melakukan Send Back tidak dapat ditentukan. "
                        "Record lama ini perlu dicek sekali oleh administrator."
                    )
                else:
                    edit_updates = {
                        "CLAIM_NO": str(edit_claim_no or "").strip(),
                        "LOSS_DATE": edit_loss_date.strftime("%Y-%m-%d") if isinstance(edit_loss_date, date) else str(edit_loss_date),
                        "CLAIM_AMOUNT": _record_text(edit_claim_amount).strip(),
                        "EXGRATIA_AMOUNT": _record_text(edit_exgratia_amount).strip(),
                        "MNC_SHARE": str(edit_mnc_share or "").strip(),
                        "LOSS_CAUSE": _limit_narrative_text(edit_loss_cause),
                        "EXGRATIA_REASON": _limit_narrative_text(edit_reason),
                        "FUTURE_BUSINESS": _limit_narrative_text(edit_future),
                    }
                    updated_ovr_context = dict(edit_ovr_context)
                    updated_ovr_context["uniform_pct"] = float(edit_ovr_uniform)
                    if edit_ovr_mode == "rules" and isinstance(edit_ovr_rules, pd.DataFrame):
                        updated_ovr_context["rules_df"] = edit_ovr_rules.copy()
                    updated_ovr_context["proxy_intermediaries"] = _intermediary_names("", edit_proxies)
                    updated_ovr_context["insured_group"] = _intermediary_names("", edit_group)
                    edit_updates["OVR_CONTEXT_JSON"] = json.dumps(
                        _clean_ovr_context_for_json(updated_ovr_context),
                        ensure_ascii=False, default=_json_default,
                    )
                    edit_updates["OVR_UNIFORM_PCT"] = _record_text(edit_ovr_uniform)
                    edit_updates["OVR_RULES_GT_0"] = _record_text(_count_ovr_rules_gt_zero(updated_ovr_context))
                    changed_fields, changed_summary = _edit_change_summary(rec, edit_updates)

                    if not changed_fields:
                        st.warning("Belum ada data yang berubah. Ubah minimal satu informasi sebelum menyimpan.")
                    else:
                        note_parts = []
                        if str(resubmit_note or "").strip():
                            note_parts.append(_limit_narrative_text(resubmit_note))
                        note_parts.append(f"Edited fields: {changed_summary}")
                        audit_note = " | ".join(note_parts)



                        scenario_updates = _scenario_summary_updates_for_record({**rec, **edit_updates})

                        updates = {
                            **edit_updates,
                            **scenario_updates,


                            "STATUS": return_status,
                            "CURRENT_STAGE": return_stage,
                            "SEND_BACK_RESOLVED_BY": username if pending_edit else rec.get("SEND_BACK_RESOLVED_BY", ""),
                            "SEND_BACK_RESOLVED_AT": now if pending_edit else rec.get("SEND_BACK_RESOLVED_AT", ""),
                            "WORKFLOW_NOTES_JSON": _append_workflow_note(
                                json.dumps(_workflow_notes_for_display(rec), ensure_ascii=False),
                                username,
                                "Edited & Resubmitted" if pending_edit else "Edited",
                                return_stage,
                                audit_note,
                                now,
                                is_red=revision_red_note,
                            ),
                            "LAST_UPDATED_BY": username,
                        }

                        ok2, msg = _update_exgratia_record(selected_doc, updates)
                        if not ok2:
                            st.error(msg)
                        else:
                            rec_after = dict(rec)
                            rec_after.update(updates)
                            rec_after["_EDIT_SUMMARY"] = changed_summary



                            requester_recipients = _reviewer_email_for_stage(
                                rec_after,
                                return_stage,
                                rec.get("SEND_BACK_BY", ""),
                            )
                            if not pending_edit:
                                requester_recipients = []
                                reviewer_ok, reviewer_msg = True, "Status pengajuan tetap."
                            elif requester_recipients:
                                reviewer_ok, reviewer_msg = _send_exgratia_pending_email(
                                    requester_recipients,
                                    rec_after,
                                    email_kind="resubmitted",
                                )
                            else:
                                reviewer_ok, reviewer_msg = _notify_pending_exgratia_if_needed(rec_after)




                            previous_recipients = _previous_approved_reviewer_emails(
                                rec_after,
                                exclude=requester_recipients,
                            )
                            prior_ok = True
                            prior_msg = "Tidak ada approver sebelumnya yang perlu dinotifikasi."
                            if previous_recipients:
                                prior_ok, prior_msg = _send_exgratia_pending_email(
                                    previous_recipients,
                                    rec_after,
                                    email_kind="edit_notice",
                                )

                            if reviewer_ok and prior_ok:
                                _set_eg_flash(
                                    "success",
                                    "Perubahan tersimpan. "
                                    "approval sebelumnya tetap berlaku. "
                                    f"{reviewer_msg} {prior_msg}",
                                )
                            elif reviewer_ok:
                                _set_eg_flash(
                                    "warning",
                                    "Perubahan tersimpan. "
                                    "Approval sebelumnya tetap berlaku, tetapi sebagian notifikasi reviewer lama gagal: "
                                    f"{prior_msg}",
                                )
                            else:
                                _set_eg_flash(
                                    "warning",
                                    "Perubahan tersimpan dan status sudah kembali ke tahap reviewer yang meminta edit, "
                                    f"tetapi email reviewer gagal: {reviewer_msg}. Notifikasi reviewer lama: {prior_msg}",
                                )
                            st.rerun()

        elif pending_edit:
            st.warning(
                "Dokumen sedang menunggu edit. Hak edit hanya diberikan kepada CREATED_BY. "
                f"CREATED_BY: {created_by_identity or '-'} | Login: {str(username or '').strip() or '-'}"
            )

        elif manager_assigned:
            with st.form(f"eg_manager_review_{selected_doc}"):
                note = st.text_area("Notes", value=_limit_narrative_text(rec.get("MARKETING_MANAGER_NOTE", "")), height=110, max_chars=EXGRATIA_MAX_NARRATIVE_CHARS)
                red_note = st.checkbox("This is a red notes", key=f"eg_red_marketing_manager_{selected_doc}")
                c1, c2, c3 = st.columns(3)
                approve = c1.form_submit_button("Approve", type="primary", width="stretch")
                decline = c2.form_submit_button("Decline", width="stretch")
                send_back = c3.form_submit_button("Send Back", width="stretch")
            if approve:
                next_status, next_stage = _route_to_claim_or_reinsurance_status(rec)
                updates = {
                    "MARKETING_MANAGER_NOTE": _limit_narrative_text(note),
                    "MARKETING_MANAGER_CONFIRMED_BY": username,
                    "MARKETING_MANAGER_CONFIRMED_AT": now,
                    "STATUS": next_status,
                    "CURRENT_STAGE": next_stage,
                    "WORKFLOW_NOTES_JSON": _notes_json("Approve", "Marketing Manager", note),
                    "LAST_UPDATED_BY": username,
                }
                ok2, msg = _update_exgratia_record(selected_doc, updates)
                if ok2:
                    rec_after = dict(rec); rec_after.update(updates)
                    _notify_after_approve(rec_after, "Marketing Manager approval tersimpan.")
                else:
                    st.error(msg)
            if decline:
                updates = _decline_updates(note, "marketing manager", "Marketing Manager")
                updates["MARKETING_MANAGER_NOTE"] = _limit_narrative_text(note)
                ok2, msg = _update_exgratia_record(selected_doc, updates)
                if ok2:
                    _set_eg_flash("warning", "Dokumen declined oleh Marketing Manager."); st.rerun()
                else: st.error(msg)
            if send_back:
                _apply_send_back(note, "Marketing Manager")

        elif is_claim_role and ("pending klaim" in status_l or "pending claim" in status_l):
            with st.form(f"eg_claim_review_{selected_doc}"):
                note = st.text_area("Notes", value=_limit_narrative_text(rec.get("CLAIM_NOTE", "")), height=120, max_chars=EXGRATIA_MAX_NARRATIVE_CHARS)
                red_note = st.checkbox("This is a red notes", key=f"eg_red_claim_{selected_doc}")
                c1, c2, c3 = st.columns(3)
                approve = c1.form_submit_button("Approve", type="primary", width="stretch")
                decline = c2.form_submit_button("Decline", width="stretch")
                send_back = c3.form_submit_button("Send Back", width="stretch")
            if approve:
                updates = {
                    "CLAIM_NOTE": _limit_narrative_text(note),
                    "CLAIM_CONFIRMED_BY": username,
                    "CLAIM_CONFIRMED_AT": now,
                    "STATUS": "pending dirmkt",
                    "CURRENT_STAGE": "dirmkt",
                    "WORKFLOW_NOTES_JSON": _notes_json("Approve", "Claim", note),
                    "LAST_UPDATED_BY": username,
                }
                ok2, msg = _update_exgratia_record(selected_doc, updates)
                if ok2:
                    rec_after = dict(rec); rec_after.update(updates)
                    _notify_after_approve(rec_after, "Klaim approved.")
                else: st.error(msg)
            if decline:
                updates = _decline_updates(note, "claim", "Claim")
                updates["CLAIM_NOTE"] = _limit_narrative_text(note)
                ok2, msg = _update_exgratia_record(selected_doc, updates)
                if ok2:
                    _set_eg_flash("warning", "Dokumen declined oleh Klaim."); st.rerun()
                else: st.error(msg)
            if send_back:
                _apply_send_back(note, "Claim")

        elif is_dirmkt and "pending dirmkt" in status_l:
            with st.form(f"eg_dirmkt_review_{selected_doc}"):
                note = st.text_area("Notes", value=_limit_narrative_text(rec.get("DIR_MARKETING_NOTE", "")), height=100, max_chars=EXGRATIA_MAX_NARRATIVE_CHARS)
                red_note = st.checkbox("This is a red notes", key=f"eg_red_dir_marketing_{selected_doc}")
                c1, c2, c3 = st.columns(3)
                approve = c1.form_submit_button("Approve", type="primary", width="stretch")
                decline = c2.form_submit_button("Decline", width="stretch")
                send_back = c3.form_submit_button("Send Back", width="stretch")
            if approve:
                updates = {
                    "DIR_MARKETING_NOTE": _limit_narrative_text(note),
                    "DIR_MARKETING_CONFIRMED_BY": username,
                    "DIR_MARKETING_CONFIRMED_AT": now,
                    "STATUS": "pending dirtek",
                    "CURRENT_STAGE": "dirtek",
                    "WORKFLOW_NOTES_JSON": _notes_json("Approve", "Direktur Marketing", note),
                    "LAST_UPDATED_BY": username,
                }
                ok2, msg = _update_exgratia_record(selected_doc, updates)
                if ok2:
                    rec_after = dict(rec); rec_after.update(updates)
                    _notify_after_approve(rec_after, "Direktur Marketing approval tersimpan.")
                else: st.error(msg)
            if decline:
                updates = _decline_updates(note, "direktur marketing", "Direktur Marketing")
                updates["DIR_MARKETING_NOTE"] = _limit_narrative_text(note)
                ok2, msg = _update_exgratia_record(selected_doc, updates)
                if ok2:
                    _set_eg_flash("warning", "Dokumen declined oleh Direktur Marketing."); st.rerun()
                else: st.error(msg)
            if send_back:
                _apply_send_back(note, "Direktur Marketing")

        elif is_dirtek and "pending dirtek" in status_l:
            with st.form(f"eg_dirtek_review_{selected_doc}"):
                note = st.text_area("Notes", value=_limit_narrative_text(rec.get("DIR_TEKNIK_NOTE", "")), height=100, max_chars=EXGRATIA_MAX_NARRATIVE_CHARS)
                red_note = st.checkbox("This is a red notes", key=f"eg_red_dir_teknik_{selected_doc}")
                c1, c2, c3 = st.columns(3)
                approve = c1.form_submit_button("Approve", type="primary", width="stretch")
                decline = c2.form_submit_button("Decline", width="stretch")
                send_back = c3.form_submit_button("Send Back", width="stretch")
            if approve:
                updates = {
                    "DIR_TEKNIK_NOTE": _limit_narrative_text(note),
                    "DIR_TEKNIK_CONFIRMED_BY": username,
                    "DIR_TEKNIK_CONFIRMED_AT": now,
                    "STATUS": "approved",
                    "CURRENT_STAGE": "approved",
                    "WORKFLOW_NOTES_JSON": _notes_json("Approve", "Direktur Teknik", note),
                    "LAST_UPDATED_BY": username,
                }
                ok2, msg = _update_exgratia_record(selected_doc, updates)
                if ok2:
                    rec_after = dict(rec)
                    rec_after.update(updates)
                    _notify_after_approve(rec_after, "Direktur Teknik approval tersimpan. Dokumen approved.")
                else: st.error(msg)
            if decline:
                updates = _decline_updates(note, "direktur teknik", "Direktur Teknik")
                updates["DIR_TEKNIK_NOTE"] = _limit_narrative_text(note)
                ok2, msg = _update_exgratia_record(selected_doc, updates)
                if ok2:
                    _set_eg_flash("warning", "Dokumen declined oleh Direktur Teknik."); st.rerun()
                else: st.error(msg)
            if send_back:
                _apply_send_back(note, "Direktur Teknik")

        if created_by_me and not terminal and not is_creator_editor:
            with st.expander("Cancel submission", expanded=False):
                with st.form(f"eg_cancel_submission_{selected_doc}"):
                    cancel_note = st.text_area("Alasan cancel", height=90, max_chars=EXGRATIA_MAX_NARRATIVE_CHARS)
                    cancel_red_note = st.checkbox("This is a red notes", key=f"eg_red_cancel_{selected_doc}")
                    cancel = st.form_submit_button("Cancel", width="stretch")
                if cancel:
                    red_note = cancel_red_note
                    updates = {
                        "STATUS": "canceled by marketing",
                        "CURRENT_STAGE": "canceled",
                        "CANCELED_BY": username,
                        "CANCELED_AT": now,
                        "CANCEL_NOTE": _limit_narrative_text(cancel_note),
                        "WORKFLOW_NOTES_JSON": _notes_json("Cancel", "Marketing", cancel_note),
                        "LAST_UPDATED_BY": username,
                    }
                    ok2, msg = _update_exgratia_record(selected_doc, updates)
                    if ok2:
                        _set_eg_flash("warning", "Pengajuan dibatalkan."); st.rerun()
                    else:
                        st.error(msg)

    _install_exgratia_splitter(pdf_width)


def _filter_exgratia_search(records: pd.DataFrame, query: str) -> pd.DataFrame:

    terms = str(query or "").casefold().split()
    if records.empty or not terms:
        return records
    columns = [c for c in (
        "DOC_ID", "POLICY_NO", "CLAIM_NO", "INSURED_NAME", "SOURCE_BUSINESS",
        "STATUS", "COB", "CREATED_BY", "CREATED_AT",
    ) if c in records.columns]
    if not columns:
        return records.iloc[:0]
    values = [records[c].astype("string").fillna("").str.casefold() for c in columns]
    matches = pd.Series(True, index=records.index)
    for term in terms:
        term_matches = pd.Series(False, index=records.index)
        for value in values:
            term_matches |= value.str.contains(term, regex=False, na=False)
        matches &= term_matches
    return records.loc[matches].copy()


def _update_exgratia_search() -> None:

    st.session_state["eg_workflow_search_query"] = st.session_state.get("eg_workflow_search_input", "")
    st.session_state["eg_workflow_page"] = 1


def _exgratia_list_status_label(status) -> str:

    text = str(status or "-").strip()
    return "Pending Manager" if text.casefold() == "pending marketing manager" else text


def _update_exgratia_status_filter() -> None:
    st.session_state["eg_workflow_status_value"] = st.session_state.get("eg_workflow_status_input", "")
    st.session_state["eg_workflow_page"] = 1


def _clear_exgratia_search() -> None:
    st.session_state["eg_workflow_search_input"] = ""
    st.session_state["eg_workflow_search_query"] = ""
    st.session_state["eg_workflow_status_input"] = ""
    st.session_state["eg_workflow_status_value"] = ""
    st.session_state["eg_workflow_page"] = 1


def render_exgratia_workflow_dashboard(username: str, role: str, show_create_button: bool = False) -> None:

    _render_exgratia_table_css()
    role = str(role or "").lower().strip()

    records = load_exgratia_records()
    visible = _workflow_visible_records(records, role, username)

    route_view = _get_exgratia_query_param("eg_view", "")
    route_doc = _sanitize_doc_id(_get_exgratia_query_param("eg_doc", ""))

    if route_doc:
        st.session_state["eg_selected_doc_id"] = route_doc
    elif route_view == "list":
        st.session_state.pop("eg_selected_doc_id", None)

    selected_doc = _sanitize_doc_id(route_doc or st.session_state.get("eg_selected_doc_id", ""))

    if selected_doc:
        st.button(
            "← Back",
            key="eg_back_to_inbox_btn_detail",
            width="content",
            on_click=_return_to_exgratia_list,
        )
        if visible.empty or "DOC_ID" not in visible.columns:
            st.error("Dokumen tidak tersedia untuk account ini.")
            return
        doc_keys = visible["DOC_ID"].astype(str).map(_sanitize_doc_id)
        rec_match = visible.loc[doc_keys.eq(selected_doc)]
        if rec_match.empty:
            st.error("Dokumen tidak ditemukan atau account ini tidak memiliki akses.")
            return
        rec = rec_match.iloc[0].to_dict()
        _render_exgratia_record_detail(rec, selected_doc, username, role)
        return

    st.markdown("<div class='eg-workflow-title'>Ex-Gratia Workflow</div>", unsafe_allow_html=True)
    _render_eg_flash()

    if show_create_button:
        st.button(
            "＋ Create Ex-Gratia Proposal",
            key="eg_create_proposal_btn",
            width="content",
            on_click=_enter_exgratia_create_mode,
        )

    total_visible = len(visible)
    st.session_state.setdefault(
        "eg_workflow_search_input", st.session_state.get("eg_workflow_search_query", "")
    )
    status_values = (
        visible["STATUS"].fillna("").astype(str).str.strip().str.casefold()
        if "STATUS" in visible.columns else pd.Series("", index=visible.index)
    )
    status_options = [""] + sorted(value for value in status_values.unique() if value)
    saved_status = st.session_state.get(
        "eg_workflow_status_input", st.session_state.get("eg_workflow_status_value", "")
    )
    st.session_state["eg_workflow_status_input"] = saved_status if saved_status in status_options else ""
    search_col, status_col, clear_col = st.columns([5, 2, 1], vertical_alignment="bottom")
    with search_col:
        search_query = st.text_input(
            "Search Ex-Gratia",
            key="eg_workflow_search_input",
            placeholder="No. polis, no. klaim, tertanggung, intermediary, atau Document ID...",
            help="Ketik lalu tekan Enter. Bisa juga mencari status, COB, pembuat, atau tanggal. Beberapa kata akan dicocokkan bersama, tanpa membedakan huruf besar/kecil.",
            on_change=_update_exgratia_search,
        )
    with status_col:
        selected_status = st.selectbox(
            "Filter Status",
            options=status_options,
            format_func=lambda value: value if value else "Semua status",
            key="eg_workflow_status_input",
            on_change=_update_exgratia_status_filter,
        )
    with clear_col:
        st.button("Clear", key="eg_workflow_search_clear", width="stretch", on_click=_clear_exgratia_search)
    if selected_status:
        visible = visible.loc[status_values.eq(selected_status)].copy()
    visible = _filter_exgratia_search(visible, search_query)
    if str(search_query).strip() or selected_status:
        st.caption(f"{len(visible):,} hasil dari {total_visible:,} dokumen yang dapat diakses.")

    count_text = f"{len(visible):,}".replace(",", ".")
    st.markdown(
        f"<div class='eg-workflow-toolbar'>"
        f"<div class='eg-workflow-chip'>{html.escape(role or '-')}</div>"
        f"<div class='eg-workflow-chip'>{count_text} document(s)</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if visible.empty:
        if total_visible and (str(search_query).strip() or selected_status):
            st.info("Tidak ada dokumen yang cocok. Ubah kata pencarian/filter status atau klik Clear untuk menampilkan semua dokumen.")
        else:
            st.info("Belum ada dokumen Ex-Gratia untuk account ini.")
        return

    visible = visible.copy()
    created_ts = pd.to_datetime(visible.get("CREATED_AT", ""), errors="coerce")
    visible["__EG_SORT_TS__"] = created_ts
    visible = visible.sort_values("__EG_SORT_TS__", ascending=False, kind="stable")

    status_groups = visible.groupby(visible["STATUS"].fillna("").astype(str).str.strip().str.lower(), sort=False)
    groups = list(status_groups)
    def group_priority(item):
        status, frame = item
        own = False
        if role in {"direktur teknik", "dirtek", "director teknik", "technical director"} or _normalize_email(username) == BOD_TEKNIK_EMAIL.lower():
            own = status in {"pending dirtek", "pending direktur teknik"}
        elif role in {"direktur marketing", "dirmkt", "director marketing"} or _normalize_email(username) == BOD_MARKETING_EMAIL.lower():
            own = status in {"pending dirmkt", "pending direktur marketing"}
        elif role.startswith("claim"):
            own = status in {"pending klaim", "pending claim"}
        if status == "pending marketing manager":
            own = own or any(_same_user_identity(username, r.get("MARKETING_MANAGER_EMAIL", "")) for r in frame.to_dict("records"))
        if "edit" in status or "send back" in status:
            own = own or any(_is_record_creator(r, username) for r in frame.to_dict("records"))
        return (0 if own else 2 if _is_terminal_status(status) else 1, status)
    for group_status, group_df in sorted(groups, key=group_priority):
        group_key = hashlib.sha256(group_status.encode()).hexdigest()[:12]
        st.subheader(f"{_exgratia_list_status_label(group_status).title()} ({len(group_df)})")
        page_size = 5
        total_pages = max(1, int(np.ceil(len(group_df) / page_size)))
        page_key = f"eg_workflow_page_{group_key}"
        current_page = int(st.session_state.get(page_key, 1) or 1)
        current_page = min(max(current_page, 1), total_pages)
        st.session_state[page_key] = current_page

        nav1, nav2, nav3 = st.columns([1, 1.4, 1], vertical_alignment="center")
        with nav1:
            if st.button("Previous", key=f"eg_page_prev_{group_key}", disabled=current_page <= 1, width="stretch"):
                st.session_state[page_key] = max(1, current_page - 1)
                st.rerun()
        with nav2:
            st.markdown(f"<div style='text-align:center;font-weight:850;color:#003366;'>Page {current_page} of {total_pages}</div>", unsafe_allow_html=True)
        with nav3:
            if st.button("Next", key=f"eg_page_next_{group_key}", disabled=current_page >= total_pages, width="stretch"):
                st.session_state[page_key] = min(total_pages, current_page + 1)
                st.rerun()

        start = (current_page - 1) * page_size
        page_df = group_df.iloc[start:start + page_size].drop(columns=["__EG_SORT_TS__"], errors="ignore")


        table_widths = [0.82, 1.26, 1.48, 0.56, 1.25, 2.25, 1.30, 1.30]
        table_headings = [
            "Action", "Document ID", "Status", "COB",
            "No. Polis", "Tertanggung", "Created By", "Created At",
        ]
        with st.container(border=True, key=f"eg_exec_table_shell_{group_key}"):
            st.markdown("<div class='eg-exec-native-topbar'></div>", unsafe_allow_html=True)
            with st.container(border=True, key=f"eg_exec_header_{group_key}"):
                header_columns = st.columns(table_widths, gap="small", vertical_alignment="center")
                for column, heading in zip(header_columns, table_headings):
                    with column:
                        st.markdown(
                            f"<div class='eg-native-heading' title='{html.escape(heading)}'>{html.escape(heading)}</div>",
                            unsafe_allow_html=True,
                        )

            for row_idx, (_, rec_row) in enumerate(page_df.iterrows(), start=start + 1):
                rec_dict = rec_row.to_dict()
                doc_id_row = _sanitize_doc_id(rec_dict.get("DOC_ID", ""))
                row_key = f"eg_exec_row_{row_idx}_{doc_id_row}"
                with st.container(border=True, key=row_key):
                    c_action, c_doc, c_status, c_cob, c_policy, c_insured, c_by, c_at = st.columns(
                        table_widths,
                        gap="small",
                        vertical_alignment="center",
                    )
                    with c_action:
                        st.button(
                            "Open",
                            key=f"eg_open_doc_{row_idx}_{doc_id_row}",
                            width="stretch",
                            on_click=_select_exgratia_doc,
                            args=(doc_id_row,),
                        )
                    with c_doc:
                        st.markdown(
                            f"<div class='eg-native-doc' title='{html.escape(doc_id_row)}'>{html.escape(_short_cell(doc_id_row, 20))}</div>",
                            unsafe_allow_html=True,
                        )
                    with c_status:
                        st.markdown(_status_badge_html(_exgratia_list_status_label(rec_dict.get("STATUS", "-"))), unsafe_allow_html=True)
                    with c_cob:
                        st.markdown(f"<div class='eg-native-cell'>{html.escape(_short_cell(rec_dict.get('COB', '-'), 10))}</div>", unsafe_allow_html=True)
                    with c_policy:
                        policy_value = str(rec_dict.get("POLICY_NO", "-"))
                        st.markdown(f"<div class='eg-native-cell' title='{html.escape(policy_value)}'>{html.escape(_short_cell(policy_value, 26))}</div>", unsafe_allow_html=True)
                    with c_insured:
                        insured_value = str(rec_dict.get("INSURED_NAME", "-"))
                        st.markdown(f"<div class='eg-native-cell strong' title='{html.escape(insured_value)}'>{html.escape(_short_cell(insured_value, 48))}</div>", unsafe_allow_html=True)
                    with c_by:
                        created_by = str(rec_dict.get("CREATED_BY", "-"))
                        st.markdown(f"<div class='eg-native-cell muted' title='{html.escape(created_by)}'>{html.escape(_short_cell(created_by, 26))}</div>", unsafe_allow_html=True)
                    with c_at:
                        created_at = str(rec_dict.get("CREATED_AT", "-"))
                        st.markdown(f"<div class='eg-native-cell muted' title='{html.escape(created_at)}'>{html.escape(_short_cell(created_at, 20))}</div>", unsafe_allow_html=True)


def _processed_ovr_matches_context(config: dict, policy_no: str, display_unit: str) -> bool:

    if not st.session_state.get("eg_ovr_processed", False) or not config:
        return False
    if _norm_key(config.get("policy_no", "")) != _norm_key(policy_no):
        return False
    if config.get("display_unit") != display_unit:
        return False
    for key, widget_key in (("proxy_intermediaries", "eg_proxy_intermediaries"),
                            ("insured_group", "eg_insured_group")):
        if set(config.get(key) or []) != set(st.session_state.get(widget_key) or []):
            return False
    return True


def _submit_exgratia_from_current_state(risk_df: pd.DataFrame, username: str, meta_current: dict) -> tuple[bool, str, str]:

    claim_no = str(st.session_state.get("eg_claim_no", "") or "").strip()
    policy_no = str(st.session_state.get("eg_policy_no", "") or "").strip()
    source_business = str(meta_current.get("source_business", "") or "").strip()
    insured_name = str(meta_current.get("insured_name", "") or "").strip()
    cob = str(meta_current.get("cob", "") or "").strip()
    display_unit = st.session_state.get("eg_display_unit", "in IDR Mio")

    corr_ok, corresponding_email, corr_error = _validate_corresponding_email(
        st.session_state.get("eg_corresponding_email", "")
    )

    processed_cfg = st.session_state.get("eg_ovr_processed_config") or {}
    ovr_processed = _processed_ovr_matches_context(processed_cfg, policy_no, display_unit)

    intermediary_summary = st.session_state.get("eg_intermediary_summary") if ovr_processed else pd.DataFrame()
    insured_summary = st.session_state.get("eg_insured_summary") if ovr_processed else pd.DataFrame()
    if not isinstance(intermediary_summary, pd.DataFrame):
        intermediary_summary = pd.DataFrame()
    if not isinstance(insured_summary, pd.DataFrame):
        insured_summary = pd.DataFrame()



    if ovr_processed:
        processed_cfg = dict(processed_cfg)
        processed_cfg["policy_no"] = policy_no
        processed_cfg["policy_uw_year"] = meta_current.get("uw_year") or _policy_uw_year(risk_df, policy_no)
        processed_cfg["exgratia_amount"] = _safe_to_float(st.session_state.get("eg_exgratia_amount", 0.0), 0.0)
        processed_cfg["display_unit"] = display_unit
        st.session_state["eg_ovr_processed_config"] = processed_cfg
        intermediary_summary, insured_summary = _store_processed_ovr_outputs(
            risk_df, processed_cfg, source_business, insured_name, display_unit
        )

    missing = []
    if not claim_no:
        missing.append("No. Klaim")
    if not policy_no:
        missing.append("No. Polis")
    if not source_business:
        missing.append("Sumber Bisnis")
    if not insured_name:
        missing.append("Nama Tertanggung")
    if not corr_ok:
        missing.append("Corresponding Email @mnc-insurance.com")
    if not ovr_processed:
        missing.append("OVR yang sudah diproses")
    if ovr_processed and intermediary_summary.empty and insured_summary.empty:
        missing.append("Portfolio Preview")
    if missing:
        extra = f" ({corr_error})" if not corr_ok and corr_error else ""
        return False, "", "Lengkapi: " + ", ".join(missing) + extra

    form_data = {
        "claim_no": claim_no,
        "policy_no": policy_no,
        "policy_uw_year": meta_current.get("uw_year") or _policy_uw_year(risk_df, policy_no),
        "cob": cob,
        "source_business": source_business,
        "insured_name": insured_name,
        "loss_date": st.session_state.get("eg_loss_date", date.today()),
        "claim_amount": st.session_state.get("eg_claim_amount", 0.0),
        "loss_cause": _limit_narrative_text(st.session_state.get("eg_loss_cause", "")),
        "exgratia_reason": _limit_narrative_text(st.session_state.get("eg_exgratia_reason", "")),
        "exgratia_amount": st.session_state.get("eg_exgratia_amount", 0.0),
        "mnc_share": st.session_state.get("eg_mnc_share", ""),
        "future_business": _limit_narrative_text(st.session_state.get("eg_future_business", "")),
        "corresponding_email": corresponding_email,
    }
    doc_id = generate_unique_document_id("EG")
    pdf_name = f"ex_gratia_{doc_id}.pdf"
    recorded, record_msg = record_exgratia_workflow_submission(
        form_data,
        doc_id,
        username,
        processed_cfg,
        pdf_name,
        intermediary_summary,
        insured_summary,
        display_unit,
        0.0,
    )
    if not recorded:
        return False, "", record_msg

    st.session_state["eg_pdf_doc_id"] = doc_id
    st.session_state["eg_pdf_name"] = pdf_name
    return True, doc_id, record_msg


def render_exgratia_generator(
    risk_df: pd.DataFrame | None = None,
    risk_paths: tuple[str, ...] | list[str] | None = None,
    username: str = "",
    user_role: str = "",
) -> None:









    inject_exgratia_css()
    role = str(user_role or "").strip().lower() or _get_user_role(username)

    route_view = _get_exgratia_query_param("eg_view", "").lower()
    route_doc = _sanitize_doc_id(_get_exgratia_query_param("eg_doc", ""))

    if route_doc:
        st.session_state["eg_selected_doc_id"] = route_doc
        st.session_state["eg_create_mode"] = False
        st.session_state["eg_preparing_create"] = False
    elif route_view == "create" and role == "marketing":
        st.session_state.pop("eg_selected_doc_id", None)
        st.session_state["eg_create_mode"] = True
    elif route_view == "list":
        st.session_state.pop("eg_selected_doc_id", None)
        st.session_state["eg_create_mode"] = False
        st.session_state["eg_preparing_create"] = False

    if role != "marketing":


        render_exgratia_workflow_dashboard(username, role or "user")
        return




    if st.session_state.get("eg_preparing_create", False):
        st.markdown(
            """
            <div class="eg-fullscreen-loading-overlay" role="status" aria-live="polite">
              <div class="eg-fullscreen-loading-content">
                <div class="eg-fullscreen-loading-spinner" aria-hidden="true"></div>
                <div class="eg-fullscreen-loading-title">
                  Preparing Ex Gratia<span class="eg-fullscreen-loading-dots"></span>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        try:
            load_risk_profile_data(tuple(EXGRATIA_RISK_DATASET_FILES))
            st.session_state["eg_preparing_create"] = False
            st.rerun()
        except Exception as e:
            st.session_state["eg_preparing_create"] = False
            st.error(f"Risk Profile dataset gagal dimuat: {e}")
        return




    if not st.session_state.get("eg_create_mode", False):
        render_exgratia_workflow_dashboard(username, "marketing", show_create_button=True)
        return

    st.button(
        "← Back to Ex-Gratia List",
        key="eg_back_to_inbox_btn",
        width="content",
        on_click=_exit_exgratia_create_mode,
    )

    st.markdown(f"""
    <style>
      .eg-hero{{
        margin: 4px 0 16px 0;
        padding: 20px 22px;
        border-radius: 24px;
        background: linear-gradient(135deg, #002B57 0%, #003366 52%, #1F5A91 100%);
        color: #FFFFFF;
        box-shadow: 0 18px 42px rgba(0,51,102,0.22);
        border: 1px solid rgba(255,255,255,0.18);
      }}
      .eg-hero-title{{font-size: 26px; font-weight: 900; letter-spacing: -0.03em; line-height: 1.05;}}
      .eg-hero-sub{{margin-top: 8px; max-width: 820px; font-size: 13.5px; line-height: 1.45; color: rgba(255,255,255,0.82);}}
      .eg-hero-badges{{display:flex; gap:8px; flex-wrap:wrap; margin-top:14px;}}
      .eg-hero-badge{{padding:6px 10px; border-radius:999px; background:rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.20); font-size:11.5px; font-weight:800;}}
      .eg-progress{{
        display:grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap:8px;
        margin: 8px 0 16px 0;
      }}
      .eg-step{{
        display:flex; align-items:center; gap:10px; padding:10px 12px;
        border:1px solid rgba(0,51,102,0.10); border-radius:16px; background:#FFFFFF;
        box-shadow: 0 8px 22px rgba(15,23,42,0.035); min-height:58px;
      }}
      .eg-step-no{{
        width:28px; height:28px; border-radius:999px; display:flex; align-items:center; justify-content:center;
        background:#EEF6FF; color:#003366; font-size:12px; font-weight:900; flex:0 0 auto;
      }}
      .eg-step-title{{font-size:13px; font-weight:900; color:#0F2742; line-height:1.05;}}
      .eg-step-sub{{font-size:10.5px; color:#64748B; font-weight:650; margin-top:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}}
      .eg-step.is-active{{border-color:rgba(0,51,102,0.36); background:linear-gradient(180deg,#FFFFFF 0%,#EEF6FF 100%);}}
      .eg-step.is-active .eg-step-no{{background:linear-gradient(135deg,#003366 0%,#1F5A91 100%); color:#FFFFFF;}}
      .eg-step.is-done .eg-step-no{{background:#E8F7EF; color:#166534;}}
      .eg-panel-intro{{
        margin: 2px 0 12px 0; padding:12px 14px; border-radius:16px;
        background:#F8FAFC; border:1px solid rgba(0,51,102,0.10); color:#475569;
        font-size:12.6px; line-height:1.38;
      }}
      .eg-identity-card{{
        margin: 12px 0 14px 0; padding:16px; border-radius:22px; background:#FFFFFF;
        border:1px solid rgba(0,51,102,0.12); box-shadow:0 12px 30px rgba(15,23,42,0.055);
      }}
      .eg-identity-top{{display:flex; justify-content:space-between; gap:12px; align-items:flex-start;}}
      .eg-overline{{font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:#64748B; font-weight:900;}}
      .eg-identity-title{{margin-top:4px; font-size:19px; font-weight:900; color:#003366; letter-spacing:-0.02em; line-height:1.15;}}
      .eg-identity-sub{{margin-top:5px; font-size:12.5px; color:#475569;}}
      .eg-status-pill{{padding:7px 10px; border-radius:999px; font-size:11.5px; font-weight:900; white-space:nowrap;}}
      .eg-status-pill.found{{background:#E8F7EF; color:#166534; border:1px solid rgba(22,101,52,.18);}}
      .eg-status-pill.missing{{background:#FFF3D6; color:#7C4A03; border:1px solid rgba(124,74,3,.18);}}
      .eg-identity-grid{{display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; margin-top:14px;}}
      .eg-mini-card{{border-radius:16px; background:#F8FAFC; border:1px solid rgba(0,51,102,0.08); padding:11px 12px;}}
      .eg-mini-card span{{display:block; font-size:11px; color:#64748B; font-weight:850; text-transform:uppercase; letter-spacing:.04em;}}
      .eg-mini-card b{{display:block; margin-top:4px; color:#0F2742; font-size:13px; line-height:1.25;}}
      .eg-notice{{
        display:flex; gap:10px; align-items:flex-start; padding:12px 14px; border-radius:16px; margin:10px 0;
        border:1px solid rgba(0,51,102,0.12); background:#FFFFFF; box-shadow:0 8px 22px rgba(15,23,42,0.035);
      }}
      .eg-notice-icon{{width:23px; height:23px; border-radius:999px; display:flex; align-items:center; justify-content:center; font-weight:900; flex:0 0 auto;}}
      .eg-notice-info .eg-notice-icon{{background:#EEF6FF;color:#003366;}}
      .eg-notice-ok .eg-notice-icon{{background:#E8F7EF;color:#166534;}}
      .eg-notice-warn .eg-notice-icon{{background:#FFF3D6;color:#7C4A03;}}
      .eg-notice-title{{font-size:13px; font-weight:900; color:#0F2742;}}
      .eg-notice-body{{font-size:12.5px; color:#64748B; line-height:1.35; margin-top:2px;}}
      /* Scope Ex-Gratia expander styling to main content only.
         Do not touch sidebar expanders/menu groups. */
      main div[data-testid="stExpander"] details,
      section.main div[data-testid="stExpander"] details{{
        border:1px solid rgba(0,51,102,0.12) !important; border-radius:20px !important;
        background:#FFFFFF !important; box-shadow:0 10px 26px rgba(15,23,42,0.045) !important;
      }}
      main div[data-testid="stExpander"] summary,
      section.main div[data-testid="stExpander"] summary{{
        font-weight:900 !important; color:#003366 !important; padding:12px 14px !important;
      }}
      main div[data-testid="stExpander"] details div[data-testid="stExpanderDetails"],
      section.main div[data-testid="stExpander"] details div[data-testid="stExpanderDetails"]{{padding:0 14px 16px 14px !important;}}
      @media (max-width: 900px){{
        .eg-progress{{grid-template-columns:1fr 1fr;}}
        .eg-identity-top{{flex-direction:column;}}
        .eg-identity-grid{{grid-template-columns:1fr;}}
      }}
    </style>
    <div class='eg-hero'>
      <div class='eg-hero-title'>Ex-Gratia Workflow</div>
    </div>
    """, unsafe_allow_html=True)

    try:

        paths = tuple(EXGRATIA_RISK_DATASET_FILES)
        risk_df = load_risk_profile_data(paths)
    except Exception as e:
        st.error(f"Risk Profile dataset gagal dimuat: {e}")
        return

    policy_col = _resolve_col(risk_df, "POLICY_NO")
    if not policy_col:
        st.error("Kolom Policy No tidak ditemukan di dataset Risk Profile.")
        return


    claim_no_current = st.session_state.get("eg_claim_no", "")
    policy_no_current = st.session_state.get("eg_policy_no", "")
    meta_current = _policy_metadata(risk_df, policy_no_current) if policy_no_current else {"found": False, "source_business": "", "insured_name": ""}
    active_step = 1
    if meta_current.get("found"):
        active_step = 2
    if st.session_state.get("eg_ovr_processed"):
        active_step = 4
    if st.session_state.get("eg_pdf_bytes"):
        active_step = 5
    _eg_render_progress_header(active_step)


    st.session_state.setdefault("eg_corresponding_email", "")
    top_email, top_generate = st.columns([2.2, 0.9], vertical_alignment="bottom")
    with top_email:
        st.text_input(
            "Corresponding Email *",
            key="eg_corresponding_email",
            placeholder="nama@mnc-insurance.com",
        )
    with top_generate:
        generate_top = st.button(
            "Generate & Submit",
            key="eg_prepare_pdf_top",
            type="primary",
            width="stretch",
        )

    with st.expander("1. Claim & Policy Lookup", expanded=True):
        st.markdown("<div class='eg-panel-intro'>Lengkapi Data Pengajuan</div>", unsafe_allow_html=True)
        with st.form("eg_policy_form", clear_on_submit=False):
            c1, c2, c3 = st.columns([1.15, 1.15, 0.55], vertical_alignment="bottom")
            with c1:
                claim_no = st.text_input("No. Klaim", key="eg_claim_no", placeholder="Contoh: CLM-...")
            with c2:
                policy_no = st.text_input("No. Polis", key="eg_policy_no", placeholder="Input nomor polis")
            with c3:
                submitted_lookup = st.form_submit_button("Load", width="stretch")

        meta = _policy_metadata(risk_df, policy_no) if (submitted_lookup or policy_no) else {"found": False, "source_business": "", "insured_name": ""}
        if policy_no and not meta.get("found"):
            typed_key = _norm_key(policy_no)
            normalized_source = (
                risk_df["__EG_POLICY_KEY__"].astype("string")
                if "__EG_POLICY_KEY__" in risk_df.columns
                else risk_df[policy_col].astype("string").map(_norm_key)
            )
            candidate_mask = normalized_source.str.contains(typed_key, regex=False, na=False) if typed_key else pd.Series(False, index=risk_df.index)
            candidates = (
                risk_df.loc[candidate_mask, policy_col]
                .astype("string")
                .dropna()
                .drop_duplicates()
                .head(8)
                .tolist()
            )
            candidate_text = ", ".join(map(str, candidates)) if candidates else "Tidak ada kandidat parsial."
            _eg_html_notice(
                "Policy belum ditemukan",
                "No. Polis tidak ditemukan pada snapshot 17 Juli 2026. "
                f"Normalized input: {typed_key or '-'}; kandidat: {candidate_text}",
                "warn",
            )

        source_business = meta.get("source_business", "")
        insured_name = meta.get("insured_name", "")
        _eg_render_identity_card(policy_no, claim_no, source_business, insured_name, bool(meta.get("found")))


        proxy_scope = (_norm_key(policy_no), str(source_business).strip().lower())
        if st.session_state.get("eg_proxy_scope") != proxy_scope:
            st.session_state["eg_proxy_scope"] = proxy_scope
            st.session_state["eg_proxy_intermediaries"] = []
            st.session_state["eg_insured_group"] = []
            _mark_ovr_dirty()
        proxy_col = _resolve_col(risk_df, "INTERMEDIARY_NAME")
        proxy_options = []
        if proxy_col:
            proxy_options = sorted(
                _intermediary_names("", risk_df[proxy_col].dropna().tolist()),
                key=str.lower,
            )
            proxy_options = [n for n in proxy_options if n.lower() != str(source_business).strip().lower()]
        selected_proxies = st.session_state.get("eg_proxy_intermediaries", [])
        valid_proxies = [n for n in selected_proxies if n in proxy_options]
        if valid_proxies != selected_proxies:
            st.session_state["eg_proxy_intermediaries"] = valid_proxies
            _mark_ovr_dirty()
        st.multiselect(
            "Add a proxy — Intermediary",
            options=proxy_options,
            key="eg_proxy_intermediaries",
            disabled=not bool(meta.get("found") and source_business),
            on_change=_mark_ovr_dirty,
            help="Pilih satu atau lebih intermediary untuk digabung dengan intermediary utama. Setelah mengubah pilihan, klik Proses OVR kembali.",
        )
        if source_business:
            st.caption("Portfolio intermediary: " + " + ".join(
                _intermediary_names(source_business, st.session_state.get("eg_proxy_intermediaries", []))
            ))
        insured_col = _resolve_col(risk_df, "INSURED_NAME")
        insured_options = sorted(_intermediary_names("", risk_df[insured_col].dropna().tolist()), key=str.lower) if insured_col else []
        insured_options = [n for n in insured_options if n.lower() != str(insured_name).strip().lower()]
        saved_group = st.session_state.get("eg_insured_group", [])
        valid_group = [n for n in saved_group if n in insured_options]
        if valid_group != saved_group:
            st.session_state["eg_insured_group"] = valid_group
            _mark_ovr_dirty()
        st.multiselect("Add insured group", options=insured_options, key="eg_insured_group",
                       disabled=not bool(meta.get("found") and insured_name), on_change=_mark_ovr_dirty,
                       help="Tambahkan INSURED_NAME lain ke portofolio tertanggung, lalu klik Proses OVR kembali.")
        st.caption("Portfolio tertanggung: " + " + ".join(_intermediary_names(insured_name, st.session_state.get("eg_insured_group", []))))



    source_business = meta.get("source_business", "") if 'meta' in locals() else meta_current.get("source_business", "")
    insured_name = meta.get("insured_name", "") if 'meta' in locals() else meta_current.get("insured_name", "")
    cob = meta.get("cob", "") if 'meta' in locals() else meta_current.get("cob", "")
    policy_no = st.session_state.get("eg_policy_no", "")
    claim_no = st.session_state.get("eg_claim_no", "")

    with st.expander("2. Claim Details", expanded=bool(source_business and insured_name and not st.session_state.get("eg_ovr_processed"))):
        st.session_state.setdefault("eg_loss_date", date.today())
        st.session_state.setdefault("eg_claim_amount", 0.0)
        st.session_state.setdefault("eg_exgratia_amount", 0.0)
        st.session_state.setdefault("eg_mnc_share", "")
        st.session_state.setdefault("eg_display_unit", "in IDR Mio")
        st.session_state.setdefault("eg_loss_cause", "")
        st.session_state.setdefault("eg_exgratia_reason", "")
        st.session_state.setdefault("eg_future_business", "")

        with st.form("eg_claim_details_form", clear_on_submit=False):
            c1, c2, c3 = st.columns(3)
            with c1:
                loss_date = st.date_input("Tanggal Kejadian", key="eg_loss_date")
            with c2:
                claim_amount = st.number_input("Nilai Klaim yang Diajukan", key="eg_claim_amount", min_value=0.0, step=1_000_000.0, format="%.0f")
            with c3:
                exgratia_amount = st.number_input("Jumlah Nilai Ex-Gratia yang Diajukan", key="eg_exgratia_amount", min_value=0.0, step=1_000_000.0, format="%.0f")

            c4, c5 = st.columns([1, 1])
            with c4:
                mnc_share = st.text_input("Share MNC Insurance", key="eg_mnc_share", placeholder="Contoh: 100% / Rp ...")
            with c5:
                display_unit = st.selectbox("Unit tabel histori", options=DISPLAY_UNIT_OPTIONS, key="eg_display_unit")

            loss_cause = st.text_area(
                "Penyebab Kerugian",
                key="eg_loss_cause",
                height=95,
                max_chars=EXGRATIA_MAX_NARRATIVE_CHARS,
                placeholder="Tulis sesuai kebutuhan.",
                help=f"Maksimal {EXGRATIA_MAX_NARRATIVE_CHARS} karakter.",
            )
            exgratia_reason = st.text_area(
                "Alasan Ex-Gratia",
                key="eg_exgratia_reason",
                height=105,
                max_chars=EXGRATIA_MAX_NARRATIVE_CHARS,
                placeholder="Tulis sesuai kebutuhan.",
                help=f"Maksimal {EXGRATIA_MAX_NARRATIVE_CHARS} karakter.",
            )
            future_business = st.text_area(
                "Potensi Bisnis yang Akan Datang",
                key="eg_future_business",
                height=150,
                max_chars=EXGRATIA_MAX_NARRATIVE_CHARS,
                placeholder="Tulis sesuai kebutuhan.",
                help=f"Maksimal {EXGRATIA_MAX_NARRATIVE_CHARS} karakter.",
            )
            saved_claim_details = st.form_submit_button("Save Claim Details", width="content")
            if saved_claim_details:
                _clear_generated_pdf()
                processed_cfg_for_unit = st.session_state.get("eg_ovr_processed_config") or {}
                if st.session_state.get("eg_ovr_processed") and processed_cfg_for_unit.get("display_unit") != display_unit:
                    _mark_ovr_dirty()
                    _eg_html_notice("Unit tabel berubah", "Klik Proses OVR lagi agar preview dan PDF memakai unit terbaru.", "warn")
                elif st.session_state.get("eg_ovr_processed"):

                    refreshed_cfg = dict(processed_cfg_for_unit)
                    refreshed_cfg["policy_no"] = policy_no
                    refreshed_cfg["policy_uw_year"] = _policy_uw_year(risk_df, policy_no)
                    refreshed_cfg["exgratia_amount"] = _safe_to_float(exgratia_amount, 0.0)
                    refreshed_cfg["display_unit"] = display_unit
                    st.session_state["eg_ovr_processed_config"] = refreshed_cfg
                    _store_processed_ovr_outputs(
                        risk_df, refreshed_cfg, source_business, insured_name, display_unit
                    )
                    _eg_html_notice(
                        "Claim details saved",
                        "Portfolio preview diperbarui dengan Loss Ratio dan Combined Ratio setelah Ex-Gratia.",
                        "ok",
                    )
                else:
                    _eg_html_notice("Claim details saved", "Input terbaru sudah tersimpan.", "ok")


    loss_date = st.session_state.get("eg_loss_date", date.today())
    claim_amount = st.session_state.get("eg_claim_amount", 0.0)
    exgratia_amount = st.session_state.get("eg_exgratia_amount", 0.0)
    mnc_share = st.session_state.get("eg_mnc_share", "")
    display_unit = st.session_state.get("eg_display_unit", "in IDR Mio")
    loss_cause = st.session_state.get("eg_loss_cause", "")
    exgratia_reason = st.session_state.get("eg_exgratia_reason", "")
    future_business = st.session_state.get("eg_future_business", "")

    with st.expander("3. OVR Setup", expanded=bool(source_business and insured_name and not st.session_state.get("eg_ovr_processed"))):
        ovr_mode_label = st.radio(
            "Mode OVR",
            options=["Sama untuk semua", "Berdasarkan kategori"],
            horizontal=True,
            key="eg_ovr_mode_label",
            on_change=_mark_ovr_dirty,
        )
        ovr_mode = "uniform" if ovr_mode_label == "Sama untuk semua" else "rules"
        uniform_pct = 0.0
        ovr_dims = []
        ovr_rules_df = pd.DataFrame()

        relevant_df = risk_df
        int_col = _resolve_col(risk_df, "INTERMEDIARY_NAME")
        ins_col = _resolve_col(risk_df, "INSURED_NAME")
        relevant_mask = pd.Series(False, index=risk_df.index)
        if source_business and int_col:
            relevant_mask |= _entity_members_mask(risk_df[int_col], source_business, st.session_state.get("eg_proxy_intermediaries", []))
        if insured_name and ins_col:
            relevant_mask |= _entity_members_mask(risk_df[ins_col], insured_name, st.session_state.get("eg_insured_group", []))
        relevant_df = risk_df[relevant_mask].copy()
        if relevant_df.empty:
            relevant_df = risk_df

        preferred_dims = ["UW_YEAR", "COB", "LOB", "TOB", "BRANCH", "MARKETING_GROUP", "MARKETING_NAME", "INTERMEDIARY_NAME", "INSURED_NAME"]
        available_dims = []
        for canonical in preferred_dims:
            col = _resolve_col(risk_df, canonical)
            if col and col not in available_dims:
                available_dims.append(col)

        if ovr_mode == "rules":
            ovr_dims = st.multiselect(
                "Kategori OVR",
                options=available_dims,
                max_selections=3,
                key="eg_ovr_dims",
                help="Pilih kategori OVR. Kombinasi unik dari data Risk Profile akan dibuat sebagai tabel input.",
                on_change=_mark_ovr_dirty,
            )
        else:
            ovr_dims = []

        with st.form("eg_ovr_process_form", clear_on_submit=False):
            if ovr_mode == "uniform":
                uniform_pct = st.number_input(
                    "OVR (%)",
                    key="eg_uniform_ovr_pct",
                    min_value=0.0,
                    max_value=100.0,
                    step=0.000001,
                    format="%.6f",
                )
            else:
                if not ovr_dims:
                    st.info("Pilih kategori OVR terlebih dahulu.")
                    ovr_rules_df = pd.DataFrame()
                else:
                    combos = relevant_df[ovr_dims].copy()
                    for c in ovr_dims:
                        combos[c] = combos[c].astype("string").fillna("(Blank)").astype(str)
                    combos = combos.drop_duplicates().sort_values(ovr_dims).head(500).reset_index(drop=True)
                    if "OVR_PCT_INPUT" not in combos.columns:
                        combos["OVR_PCT_INPUT"] = 0.0
                    st.caption("Maksimal 500 kombinasi OVR. Kombinasi yang tidak ada di tabel dianggap 0%.")
                    ovr_rules_df = st.data_editor(
                        combos,
                        key="eg_ovr_rules_editor",
                        disabled=ovr_dims,
                        width="stretch",
                        hide_index=True,
                        column_config={
                            "OVR_PCT_INPUT": st.column_config.NumberColumn(
                                "OVR (%)",
                                min_value=0.0,
                                max_value=100.0,
                                step=0.000001,
                                format="%.6f",
                            )
                        },
                    )

            confirm_ovr_process = st.checkbox(
                "Saya menyatakan telah menginput OVR yang benar dan bertanggung jawab",
                key="eg_confirm_ovr_process",
            )




            process_ovr_clicked = st.form_submit_button(
                "Proses OVR",
                type="primary",
            )

        if process_ovr_clicked:
            _mark_ovr_dirty()
            rules_clean = ovr_rules_df.copy() if isinstance(ovr_rules_df, pd.DataFrame) else pd.DataFrame()
            if not confirm_ovr_process:
                st.session_state["eg_ovr_processed"] = False
                _eg_html_notice("OVR belum bisa diproses", "Centang pernyataan tanggung jawab terlebih dahulu, lalu klik Proses OVR.", "warn")
            elif ovr_mode == "rules" and (not ovr_dims or rules_clean.empty):
                st.session_state["eg_ovr_processed"] = False
                _eg_html_notice("OVR belum bisa diproses", "Pilih minimal satu kategori OVR dan isi tabel OVR terlebih dahulu.", "warn")
            else:
                st.session_state["eg_ovr_processed"] = True
                processed_cfg_new = {
                    "mode": ovr_mode,
                    "mode_label": ovr_mode_label,
                    "uniform_pct": float(_safe_to_float(uniform_pct, 0.0)),
                    "dims": list(ovr_dims or []),
                    "rules_df": rules_clean,
                    "policy_no": policy_no,
                    "policy_uw_year": _policy_uw_year(risk_df, policy_no),
                    "exgratia_amount": _safe_to_float(exgratia_amount, 0.0),
                    "claim_no": claim_no,
                    "source_business": source_business,
                    "proxy_intermediaries": list(st.session_state.get("eg_proxy_intermediaries", [])),
                    "insured_group": list(st.session_state.get("eg_insured_group", [])),
                    "insured_name": insured_name,
                    "display_unit": display_unit,
                    "processed_at": datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d %b %Y %H:%M WIB"),
                }
                st.session_state["eg_ovr_processed_config"] = processed_cfg_new
                _clear_generated_pdf()
                _store_processed_ovr_outputs(risk_df, processed_cfg_new, source_business, insured_name, display_unit)
                _eg_html_notice("OVR processed", "Preview dan PDF sudah memakai OVR yang diproses.", "ok")

        processed_cfg_preview = st.session_state.get("eg_ovr_processed_config") or {}
        if st.session_state.get("eg_ovr_processed"):
            processed_mode = processed_cfg_preview.get("mode_label", "-")
            processed_time = processed_cfg_preview.get("processed_at", "-")
            _eg_html_notice("OVR terakhir sudah diproses", f"Mode: {processed_mode}. Diproses: {processed_time}.", "info")
        else:
            _eg_html_notice("OVR belum diproses", "Preview dan PDF masih terkunci sampai OVR diproses.", "warn")


    processed_cfg = st.session_state.get("eg_ovr_processed_config") or {}
    ovr_processed = _processed_ovr_matches_context(processed_cfg, policy_no, display_unit)

    intermediary_summary = st.session_state.get("eg_intermediary_summary") if ovr_processed else pd.DataFrame()
    insured_summary = st.session_state.get("eg_insured_summary") if ovr_processed else pd.DataFrame()
    if not isinstance(intermediary_summary, pd.DataFrame):
        intermediary_summary = pd.DataFrame()
    if not isinstance(insured_summary, pd.DataFrame):
        insured_summary = pd.DataFrame()

    with st.expander("4. Portfolio History Preview", expanded=bool(ovr_processed)):
        if not ovr_processed:
            _eg_html_notice("Preview terkunci", "Proses OVR terlebih dahulu agar preview histori tampil final.", "info")
        else:
            cprev1, cprev2 = st.columns(2, gap="large")
            with cprev1:
                st.markdown("**By Sumber Bisnis / Intermediary**")
                st.caption("Digabung: " + " + ".join(_intermediary_names(
                    source_business, processed_cfg.get("proxy_intermediaries", [])
                )))
                st.caption("Existing vs scenario Gross Claim + nilai Ex-Gratia pada UW Year polis.")
                render_performance_html_table(intermediary_summary, "intermediary", display_unit)
            with cprev2:
                st.markdown("**By Nama Tertanggung / Insured Name**")
                st.caption("Digabung: " + " + ".join(_intermediary_names(insured_name, processed_cfg.get("insured_group", []))))
                st.caption("Existing vs scenario Gross Claim + nilai Ex-Gratia pada UW Year polis.")
                render_performance_html_table(insured_summary, "insured", display_unit)

    if generate_top:
        latest_policy = str(st.session_state.get("eg_policy_no", "") or "").strip()
        latest_meta = _policy_metadata(risk_df, latest_policy) if latest_policy else {"found": False, "source_business": "", "insured_name": "", "cob": ""}
        with st.spinner("Memproses Ex-Gratia..."):
            submit_ok, submitted_doc_id, submit_msg = _submit_exgratia_from_current_state(risk_df, username, latest_meta)
        if submit_ok:
            notification = st.session_state.pop("eg_last_notification", {})
            if isinstance(notification, dict) and not notification.get("ok", True):
                _set_eg_flash("warning", f"{submitted_doc_id} tersimpan. Email otomatis gagal: {notification.get('message', '-')}")
            else:
                notify_text = notification.get("message", "") if isinstance(notification, dict) else ""
                _set_eg_flash("success", f"{submitted_doc_id} tersimpan. {notify_text}".strip())
            _return_to_exgratia_list()
            st.rerun()
        else:
            st.error(submit_msg)


    st.markdown("---")
    if st.button("Back to Ex-Gratia List", key="eg_back_to_inbox_bottom_btn", width="content"):
        st.session_state["eg_create_mode"] = False
        _clear_generated_pdf()
        st.rerun()




def preload_workbooks():
    load_risk_profile_data(tuple(EXGRATIA_RISK_DATASET_FILES))


if __name__ == "__main__":

    render_exgratia_generator()
