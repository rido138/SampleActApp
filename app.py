import streamlit as st
import pandas as pd
import hashlib
import uuid
import ipaddress
from importlib import import_module
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import json
import base64
import html
import os
import shutil
from pathlib import Path
from textwrap import dedent
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from zoneinfo import ZoneInfo




GSHEET_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_gcp_credentials_info() -> dict:

    return {k: v for k, v in st.secrets["gcp"].items()}


def _get_gspread_client():





    creds = Credentials.from_service_account_info(
        _get_gcp_credentials_info(),
        scopes=GSHEET_SCOPES,
    )
    return gspread.Client(auth=creds)


def _get_spreadsheet():
    return _get_gspread_client().open("Login Log")






def get_gsheet():
    return _get_spreadsheet().sheet1


def log_login(username, ip="unknown"):



    try:
        sheet = get_gsheet()
        sheet.append_row([
            username,
            datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S"),
            ip
        ])
    except Exception:
        pass




CHAT_MESSAGES_SHEET = "chat_messages"
CHAT_MESSAGE_HEADERS = [
    "MSG_ID",
    "CHAT_ID",
    "SENDER",
    "RECEIVER",
    "MESSAGE",
    "CREATED_AT",
    "READ_AT",
    "IS_DELETED",
    "MODULE_CONTEXT",
    "DOC_ID",
]

CHAT_USERS_SHEET = "our_users"
CHAT_USER_HEADERS = ["USER", "NAME", "IS_ACTIVE"]


def _now_jakarta_str() -> str:
    return datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")


def _normalize_chat_user(value: str) -> str:
    return str(value or "").strip().lower()


def _is_valid_chat_user(value: str) -> bool:






    value = _normalize_chat_user(value)
    if not value:
        return False

    if "__" in value:
        return False
    return True


def _make_chat_id(user_a: str, user_b: str) -> str:
    a = _normalize_chat_user(user_a)
    b = _normalize_chat_user(user_b)
    return "__".join(sorted([a, b]))


def get_chat_sheet():

    spreadsheet = _get_spreadsheet()
    try:
        sheet = spreadsheet.worksheet(CHAT_MESSAGES_SHEET)
    except Exception:
        sheet = spreadsheet.add_worksheet(
            title=CHAT_MESSAGES_SHEET,
            rows=1000,
            cols=len(CHAT_MESSAGE_HEADERS),
        )

    try:
        current_header = sheet.row_values(1)


        if current_header[:len(CHAT_MESSAGE_HEADERS)] != CHAT_MESSAGE_HEADERS:
            sheet.update("A1:J1", [CHAT_MESSAGE_HEADERS])
    except Exception:
        pass

    return sheet


def load_chat_records() -> list[dict]:






    try:
        values = get_chat_sheet().get_all_values()
    except Exception:
        return []

    if not values or len(values) <= 1:
        return []

    raw_header = [str(h or "").strip().upper() for h in values[0]]
    idx = {}
    for i, h in enumerate(raw_header):
        if h and h not in idx:
            idx[h] = i

    if not all(h in idx for h in ["MSG_ID", "CHAT_ID", "SENDER", "RECEIVER", "MESSAGE"]):
        idx = {h: i for i, h in enumerate(CHAT_MESSAGE_HEADERS)}

    records = []
    for row in values[1:]:
        if not any(str(x).strip() for x in row):
            continue

        rec = {}
        for h in CHAT_MESSAGE_HEADERS:
            i = idx.get(h)
            rec[h] = row[i] if i is not None and i < len(row) else ""



        created_at = str(rec.get("CREATED_AT", "")).strip()
        read_at = str(rec.get("READ_AT", "")).strip()
        module_context = str(rec.get("MODULE_CONTEXT", "")).strip()
        doc_id = str(rec.get("DOC_ID", "")).strip()
        looks_like_doc_id = created_at.upper().startswith("RP-") or created_at.upper().startswith("DOC-")
        looks_like_datetime = False
        try:
            datetime.strptime(read_at, "%Y-%m-%d %H:%M:%S")
            looks_like_datetime = True
        except Exception:
            pass
        if looks_like_doc_id and looks_like_datetime and not doc_id:
            rec["DOC_ID"] = created_at.upper()
            rec["CREATED_AT"] = read_at
            rec["READ_AT"] = ""
            rec["IS_DELETED"] = module_context if module_context else "FALSE"
            rec["MODULE_CONTEXT"] = "Super Chat"

        records.append(rec)

    return records




def send_chat_message(sender: str, receiver: str, message: str, doc_id: str = "") -> tuple[bool, str]:
    sender = _normalize_chat_user(sender)
    receiver = _normalize_chat_user(receiver)
    message = str(message or "").strip()
    doc_id = str(doc_id or "").strip().upper().replace(" ", "")

    if not _is_valid_chat_user(sender):
        return False, "Sender tidak valid."
    if not _is_valid_chat_user(receiver):
        return False, "Receiver tidak valid."
    if sender == receiver:
        return False, "Receiver tidak boleh sama dengan sender."
    if not message and not doc_id:
        return False, "Tulis pesan atau isi Document ID terlebih dahulu."

    msg_id = f"MSG-{datetime.now(ZoneInfo('Asia/Jakarta')).strftime('%y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    chat_id = _make_chat_id(sender, receiver)
    row = [
        msg_id,
        chat_id,
        sender,
        receiver,
        message,
        _now_jakarta_str(),
        "",
        "FALSE",
        "Super Chat",
        doc_id,
    ]

    try:
        get_chat_sheet().append_row(row, value_input_option="USER_ENTERED")
        return True, "Message sent."
    except Exception as e:
        return False, f"Gagal mengirim pesan: {e}"


def mark_chat_read(current_user: str, chat_id: str) -> int:
    current_user = _normalize_chat_user(current_user)
    chat_id = str(chat_id or "").strip()
    if not current_user or not chat_id:
        return 0

    try:
        sheet = get_chat_sheet()
        values = sheet.get_all_values()
        if not values:
            return 0

        header = values[0]
        idx = {name: i for i, name in enumerate(header)}
        required = ["CHAT_ID", "RECEIVER", "READ_AT", "IS_DELETED"]
        if not all(c in idx for c in required):
            return 0

        read_col = idx["READ_AT"] + 1
        read_col_letter = chr(64 + read_col) if read_col <= 26 else "H"
        now_text = _now_jakarta_str()
        updates = []

        for row_number, row in enumerate(values[1:], start=2):
            def cell(name, default=""):
                i = idx.get(name)
                return row[i] if i is not None and i < len(row) else default

            if (
                str(cell("CHAT_ID")).strip() == chat_id
                and _normalize_chat_user(cell("RECEIVER")) == current_user
                and not str(cell("READ_AT")).strip()
                and str(cell("IS_DELETED")).strip().upper() != "TRUE"
            ):
                updates.append({"range": f"{read_col_letter}{row_number}", "values": [[now_text]]})

        if updates:
            sheet.batch_update(updates, value_input_option="USER_ENTERED")
        return len(updates)
    except Exception:
        return 0


def _normalize_active_flag(value) -> bool:

    text = str(value or "").strip().lower()
    if not text:
        return True
    return text not in {"false", "no", "n", "inactive", "disabled", "0"}


def get_chat_users_sheet():

    spreadsheet = _get_spreadsheet()
    try:
        sheet = spreadsheet.worksheet(CHAT_USERS_SHEET)
    except Exception:
        sheet = spreadsheet.add_worksheet(
            title=CHAT_USERS_SHEET,
            rows=300,
            cols=len(CHAT_USER_HEADERS),
        )
        try:
            sheet.update("A1", [CHAT_USER_HEADERS])
        except Exception:
            pass
        return sheet

    try:
        current_header = sheet.row_values(1)
        if not current_header:
            sheet.update("A1", [CHAT_USER_HEADERS])
    except Exception:
        pass

    return sheet


def load_chat_users_from_gsheet() -> list[str]:






    try:
        values = get_chat_users_sheet().get_all_values()
    except Exception:
        return []

    if not values:
        return []

    header = [str(h or "").strip().upper() for h in values[0]]
    email_aliases = {"USER", "USER_ID", "USERNAME", "EMAIL", "USER_EMAIL", "MAIL", "ID"}
    active_aliases = {"IS_ACTIVE", "ACTIVE", "STATUS", "ENABLED"}

    email_col = next((i for i, h in enumerate(header) if h in email_aliases), None)
    active_col = next((i for i, h in enumerate(header) if h in active_aliases), None)

    if email_col is None:

        data_rows = values
        email_col = 0
        active_col = None
    else:
        data_rows = values[1:]

    users = []
    for row in data_rows:
        user_id = row[email_col] if email_col < len(row) else ""
        user_id = _normalize_chat_user(user_id)
        active_value = row[active_col] if active_col is not None and active_col < len(row) else ""

        if _is_valid_chat_user(user_id) and _normalize_active_flag(active_value) and user_id not in users:
            users.append(user_id)

    return users




def _get_secret_chat_users() -> list[str]:

    try:
        value = st.secrets["auth"].get("chat_users", [])
    except Exception:
        value = []

    if isinstance(value, str):
        candidates = [x.strip() for x in value.split(",") if x.strip()]
    elif isinstance(value, (list, tuple)):
        candidates = [str(x).strip() for x in value if str(x).strip()]
    else:
        candidates = []

    cleaned = []
    for item in candidates:
        user = _normalize_chat_user(item)
        if _is_valid_chat_user(user) and user not in cleaned:
            cleaned.append(user)
    return cleaned


def get_available_chat_users() -> list[str]:

    users = load_chat_users_from_gsheet()
    return users if users else _get_secret_chat_users()

def _format_chat_time(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d %b %H:%M")
    except Exception:
        return text


def _chat_record_is_deleted(rec: dict) -> bool:
    return str(rec.get("IS_DELETED", "")).strip().upper() == "TRUE"


def _parse_chat_datetime(value):

    text = str(value or "").strip()
    if not text:
        return datetime.min
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d %b %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            pass
    return datetime.min


def _render_chat_css():
    st.markdown(
        """
        <style>
          .chat-hero{
            position: relative;
            overflow: hidden;
            background:
              radial-gradient(circle at 82% 18%, rgba(255,255,255,0.20) 0, rgba(255,255,255,0.00) 25%),
              linear-gradient(135deg, #1E2A3B 0%, #274875 58%, #0f1d33 100%);
            color: #fff;
            padding: 24px 28px;
            border-radius: 24px;
            margin-bottom: 16px;
            box-shadow: 0 18px 42px rgba(25,44,77,0.20);
            border: 1px solid rgba(255,255,255,0.12);
          }
          .chat-hero h1{
            margin: 0 0 6px 0 !important;
            color: #fff !important;
            letter-spacing: -0.03em;
            font-size: 34px !important;
            line-height: 1.06 !important;
          }
          .chat-hero p{
            margin: 0;
            color: rgba(255,255,255,0.84);
            font-size: 12.8px;
            line-height: 1.55;
            max-width: 780px;
          }
          .chat-mini-pill{
            display:inline-flex;
            align-items:center;
            gap:7px;
            margin-top: 12px;
            padding: 7px 11px;
            border-radius:999px;
            background: rgba(255,255,255,0.12);
            border:1px solid rgba(255,255,255,0.16);
            color: rgba(255,255,255,0.92);
            font-size: 12px;
            font-weight: 750;
          }
          .chat-side-title{
            font-size: 24px;
            font-weight: 850;
            color: #1e293b;
            letter-spacing: -0.025em;
            margin-bottom: 4px;
          }
          .chat-suggestion-title{
            margin: 10px 0 6px 0;
            color: #334155;
            font-size: 12px;
            font-weight: 820;
          }
          .chat-thread-header{
            display:flex;
            align-items:flex-start;
            justify-content:space-between;
            gap:14px;
            margin-bottom: 12px;
          }
          .chat-thread-title{
            font-size: 26px;
            font-weight: 880;
            color: #1e293b;
            letter-spacing: -0.035em;
            margin: 0;
          }
          .chat-thread-subtitle{
            color:#64748b;
            font-size: 13px;
            line-height: 1.45;
            margin-top: 4px;
          }
          div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Select conversation"]) label{
            border: 1px solid rgba(0,51,102,0.10) !important;
            border-radius: 14px !important;
            padding: 9px 11px !important;
            margin-bottom: 6px !important;
            background: #ffffff !important;
            box-shadow: 0 6px 14px rgba(15,23,42,0.035) !important;
          }
          div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Select conversation"]) label:has(input:checked){
            background: #EEF6FF !important;
            border-color: rgba(0,51,102,0.30) !important;
          }
          .chat-thread-box{
            border: 1px solid rgba(0,51,102,0.10);
            border-radius: 22px;
            padding: 16px 18px;
            background:
              radial-gradient(circle at 92% 12%, rgba(11,99,206,0.06) 0, rgba(11,99,206,0.00) 24%),
              linear-gradient(180deg, #F8FAFC 0%, #FFFFFF 100%);
            box-shadow: 0 12px 26px rgba(15,23,42,0.045);
            min-height: 440px;
            max-height: 560px;
            overflow-y: auto;
            margin-bottom: 14px;
          }
          .chat-message{
            width: fit-content;
            max-width: min(78%, 720px);
            padding: 11px 13px;
            border-radius: 18px;
            margin: 9px 0;
            border: 1px solid rgba(25,44,77,0.08);
            box-shadow: 0 7px 18px rgba(15,23,42,0.045);
          }
          .chat-message.me{
            margin-left: auto;
            background: linear-gradient(135deg, #0b63ce 0%, #1E2A3B 100%);
            border-color: rgba(11,99,206,0.20);
            color: #ffffff;
            border-bottom-right-radius: 6px;
          }
          .chat-message.them{
            margin-right: auto;
            background: #FFFFFF;
            color: #1e293b;
            border-bottom-left-radius: 6px;
          }
          .chat-meta{font-size: 11px;font-weight: 780;margin-bottom: 5px;}
          .chat-message.me .chat-meta{ color: rgba(255,255,255,0.72); }
          .chat-message.them .chat-meta{ color: #64748b; }
          .chat-text{font-size: 14px;line-height: 1.48;white-space: pre-wrap;overflow-wrap: anywhere;}
          .chat-message.me .chat-text{ color: #ffffff; }
          .chat-message.them .chat-text{ color: #1e293b; }
          .chat-doc{display: inline-flex;margin-top: 8px;padding: 6px 9px;border-radius: 999px;font-size: 12px;font-weight: 850;}
          .chat-message.me .chat-doc{background: rgba(255,255,255,0.16);color: #ffffff;}
          .chat-message.them .chat-doc{background: rgba(25,44,77,0.08);color: #1E2A3B;}
          .chat-empty-state{border: 1px dashed rgba(0,51,102,0.18);background: #F8FAFC;border-radius: 18px;padding: 18px;color:#64748b;font-size: 13px;text-align:center;}

          /* Compact Super Chat buttons only */
          div[class*="st-key-chat_refresh_all_btn"] button,
          div[class*="st-key-chat_mark_read__"] button,
          div[class*="st-key-chat_refresh_thread__"] button,
          div[class*="st-key-chat_refresh_contacts_btn"] button,
          div[class*="st-key-chat_suggest__"] button,
          div[class*="st-key-chat_start_typed_user"] button,
          div[class*="st-key-chat_send_message_form"] button,
          div[data-testid="stForm"] button[kind="secondaryFormSubmit"]{
            min-height: 36px !important;
            height: 36px !important;
            padding: 0 14px !important;
            border-radius: 11px !important;
            font-size: 12.5px !important;
            font-weight: 750 !important;
            line-height: 1 !important;
            box-shadow: 0 5px 12px rgba(15,23,42,0.08) !important;
          }
          div[class*="st-key-chat_refresh_contacts_btn"] button,
          div[class*="st-key-chat_suggest__"] button{
            width: 100% !important;
          }
          div[class*="st-key-chat_refresh_all_btn"] button,
          div[class*="st-key-chat_mark_read__"] button,
          div[class*="st-key-chat_refresh_thread__"] button{
            width: auto !important;
            min-width: 118px !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _chat_key(value: str) -> str:
    return hashlib.sha1(str(value).encode("utf-8")).hexdigest()[:12]


def _render_thread_html(thread: list[dict], current_user: str) -> str:






    rows = []
    if thread:
        for rec in thread[-80:]:
            sender = _normalize_chat_user(rec.get("SENDER"))
            is_me = sender == current_user
            css_class = "me" if is_me else "them"
            who = "You" if is_me else sender
            created = _format_chat_time(rec.get("CREATED_AT"))
            message = html.escape(str(rec.get("MESSAGE", "") or ""))
            doc_id = str(rec.get("DOC_ID", "") or "").strip().upper()
            doc_html = f'<div class="chat-doc">Document ID: {html.escape(doc_id)}</div>' if doc_id else ""
            rows.append(
                f'<div class="chat-message {css_class}">'
                f'<div class="chat-meta">{html.escape(who)} · {html.escape(created)}</div>'
                f'<div class="chat-text">{message}</div>'
                f'{doc_html}'
                f'</div>'
            )
    else:
        rows.append('<div class="chat-empty-state">Belum ada pesan di conversation ini. Kirim pesan pertama di bawah.</div>')

    return '<div class="chat-thread-box">' + ''.join(rows) + '</div>'


def _render_chat_html(markup: str) -> None:





    markup = str(markup or "").strip()
    try:
        if hasattr(st, "html"):
            st.html(markup)
        else:
            st.markdown(markup, unsafe_allow_html=True)
    except Exception:
        st.markdown(markup, unsafe_allow_html=True)


def render_superapp_chat(username: str, embedded: bool = False):





    _render_chat_css()
    current_user = _normalize_chat_user(username)

    if not embedded:
        st.markdown(
            """
            <div class="chat-hero">
              <h1>SuperApp Chat</h1>
              <p>Send review notes, follow up with teammates, and share Risk Profile Document IDs.</p>
              <div class="chat-mini-pill">💬 Internal Review Chat</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not _is_valid_chat_user(current_user):
        st.warning("Chat membutuhkan username/user ID yang valid.")
        return

    st.markdown(f"<div class='chat-current-user'>You: <b>{html.escape(current_user)}</b></div>", unsafe_allow_html=True)

    records = [r for r in load_chat_records() if isinstance(r, dict) and not _chat_record_is_deleted(r)]
    my_records = []
    conversation_contacts = set()
    all_known_users = set(get_available_chat_users())
    contact_stats = {}

    for rec in records:
        sender = _normalize_chat_user(rec.get("SENDER"))
        receiver = _normalize_chat_user(rec.get("RECEIVER"))
        if sender == current_user or receiver == current_user:
            chat_id = str(rec.get("CHAT_ID") or _make_chat_id(sender, receiver)).strip()
            rec = dict(rec)
            rec["CHAT_ID"] = chat_id
            rec["SENDER"] = sender
            rec["RECEIVER"] = receiver
            my_records.append(rec)

            other = receiver if sender == current_user else sender
            if _is_valid_chat_user(other) and other != current_user:
                conversation_contacts.add(other)
                stats = contact_stats.setdefault(other, {"unread": 0, "last_dt": datetime.min, "last_text": ""})
                created_dt = _parse_chat_datetime(rec.get("CREATED_AT"))
                if created_dt >= stats["last_dt"]:
                    stats["last_dt"] = created_dt
                    preview = str(rec.get("MESSAGE", "") or rec.get("DOC_ID", "") or "").strip()
                    stats["last_text"] = preview[:48]
                if receiver == current_user and not str(rec.get("READ_AT", "")).strip():
                    stats["unread"] += 1

    all_known_users.discard(current_user)

    def _conversation_sort_key(contact: str):
        stats = contact_stats.get(contact, {})
        unread = int(stats.get("unread", 0) or 0)
        last_dt = stats.get("last_dt", datetime.min)
        ts = last_dt.timestamp() if isinstance(last_dt, datetime) and last_dt != datetime.min else 0
        return (-1 if unread > 0 else 0, -ts, contact)

    sorted_conversation_contacts = sorted(conversation_contacts, key=_conversation_sort_key)

    left, right = st.columns([0.34, 0.66], gap="large")

    with left:
        title_col, refresh_col = st.columns([0.68, 0.32], gap="small", vertical_alignment="center")
        with title_col:
            st.markdown('<div class="chat-side-title">Conversations</div>', unsafe_allow_html=True)
        with refresh_col:
            if st.button("Refresh", key="chat_refresh_all_btn", width="content"):
                st.rerun()

        total_unread = sum(int(v.get("unread", 0) or 0) for v in contact_stats.values())
        if total_unread:
            st.caption(f"🔵 {total_unread} unread message(s)")
        else:
            st.caption("All messages read")

        new_receiver = st.text_input(
            "Search / start user",
            placeholder="type username, email, or employee ID",
            key="chat_new_receiver",
        )
        normalized_new_receiver = _normalize_chat_user(new_receiver)
        search_query = normalized_new_receiver

        directory_matches = []
        if search_query:
            directory_matches = [u for u in sorted(all_known_users) if search_query in u and u not in conversation_contacts and u != current_user][:8]

        if search_query and directory_matches:
            st.markdown('<div class="chat-suggestion-title">Suggestions</div>', unsafe_allow_html=True)
            for u in directory_matches[:6]:
                if st.button(f"＋ {u}", key=f"chat_suggest__{_chat_key(u)}", width="stretch"):



                    st.session_state["chat_selected_contact"] = u
                    st.rerun()
        elif search_query and _is_valid_chat_user(normalized_new_receiver) and normalized_new_receiver != current_user:
            if st.button(f"Start chat with {normalized_new_receiver}", key="chat_start_typed_user", width="stretch"):
                st.session_state["chat_selected_contact"] = normalized_new_receiver
                st.rerun()

        contact_options = list(sorted_conversation_contacts)
        selected_from_state = st.session_state.get("chat_selected_contact")
        if selected_from_state and selected_from_state not in contact_options and selected_from_state != current_user:
            contact_options = [selected_from_state] + contact_options
        elif _is_valid_chat_user(normalized_new_receiver) and normalized_new_receiver not in contact_options and normalized_new_receiver != current_user:
            contact_options = [normalized_new_receiver] + contact_options

        def _contact_label(contact: str) -> str:
            stats = contact_stats.get(contact, {})
            unread = int(stats.get("unread", 0) or 0)
            last_dt = stats.get("last_dt", datetime.min)
            last_text = str(stats.get("last_text", "") or "").strip()
            if unread:
                return f"🔵 {contact} · {unread} unread"
            if isinstance(last_dt, datetime) and last_dt != datetime.min:
                suffix = f" · {last_dt.strftime('%d %b %H:%M')}"
                if last_text:
                    suffix += f" · {last_text}"
                return f"{contact}{suffix}"
            return f"＋ {contact}"

        if "chat_selected_contact" in st.session_state and st.session_state.get("chat_selected_contact") not in contact_options:
            st.session_state.pop("chat_selected_contact", None)

        if contact_options:
            st.markdown('<div class="chat-suggestion-title">Recent</div>', unsafe_allow_html=True)
            selected_contact = st.radio(
                "Select conversation",
                options=contact_options,
                format_func=_contact_label,
                key="chat_selected_contact",
                label_visibility="collapsed",
            )
        else:
            selected_contact = ""
            st.info("Belum ada conversation. Ketik username/user ID untuk mulai chat.")

        st.markdown("---")

    with right:
        if not selected_contact:
            st.info("Pilih conversation atau ketik username/user ID untuk mulai chat.")
            return

        receiver = _normalize_chat_user(selected_contact)
        if not _is_valid_chat_user(receiver):
            st.warning("Receiver tidak valid.")
            return

        chat_id = _make_chat_id(current_user, receiver)
        st.markdown(
            f"""
            <div class="chat-thread-header">
              <div>
                <div class="chat-thread-title">{html.escape(receiver)}</div>
                <div class="chat-thread-subtitle">Chat, review, and share Risk Profile Document IDs.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        mark_col, _chat_action_spacer = st.columns([0.22, 0.78], gap="small")
        with mark_col:
            if st.button("Mark as read", key=f"chat_mark_read__{_chat_key(receiver)}", width="content"):
                marked = mark_chat_read(current_user, chat_id)
                st.success("Messages marked as read.")
                st.rerun()

        thread = [r for r in my_records if str(r.get("CHAT_ID")) == chat_id]
        thread = sorted(thread, key=lambda r: str(r.get("CREATED_AT", "")))
        _render_chat_html(_render_thread_html(thread, current_user))

        with st.form("chat_send_message_form", clear_on_submit=True):
            message = st.text_area("Message", height=100, placeholder="Tulis pesan...")
            doc_id = st.text_input("Attach Document ID (optional)", placeholder="RP-260513-XXXXXXXX")
            send_btn = st.form_submit_button("Send Message →", width="stretch")

        if send_btn:
            ok, msg = send_chat_message(current_user, receiver, message, doc_id)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


OTP_TRACKER_FILE = "otp_tracker.json"

if not os.path.exists(OTP_TRACKER_FILE):
    with open(OTP_TRACKER_FILE, "w") as f:
        json.dump({}, f)

def load_otp_tracker():
    with open(OTP_TRACKER_FILE, "r") as f:
        return json.load(f)

def save_otp_tracker(data):
    with open(OTP_TRACKER_FILE, "w") as f:
        json.dump(data, f, indent=2)

def should_use_otp(username):
    data = load_otp_tracker()
    today_str = datetime.now().strftime("%Y-%m-%d")
    last_date = data.get(username)
    return last_date != today_str

def update_otp_date(username):
    data = load_otp_tracker()
    today_str = datetime.now().strftime("%Y-%m-%d")
    data[username] = today_str
    save_otp_tracker(data)

use_otp = False
OTP_EXPIRY_HOURS = 8




INCOGNITO_LOGIN_ENABLED = True
INCOGNITO_EMAIL_DOMAIN = "@mnc-insurance.com"
INCOGNITO_SESSION_ROLE_KEY = "__incognito__"
DEFAULT_INCOGNITO_PAGES = ["Home", "Risk Profile"]


def _secret_list(key: str, default: list[str]) -> list[str]:

    try:
        value = st.secrets["auth"].get(key, default)
    except Exception:
        value = default

    if isinstance(value, str):
        value = [x.strip() for x in value.split(",") if x.strip()]
    elif not isinstance(value, (list, tuple)):
        value = default

    pages = []
    for item in value:
        item = str(item).strip()
        if item and item not in pages:
            pages.append(item)
    return pages or list(default)


def get_incognito_pages() -> list[str]:








    pages = _secret_list("incognito_pages", DEFAULT_INCOGNITO_PAGES)
    if "Home" not in pages:
        pages = ["Home"] + pages
    return pages


def normalize_mnc_email(email: str) -> str:
    return str(email or "").strip().lower()


def is_valid_mnc_email(email: str) -> bool:
    email = normalize_mnc_email(email)
    return email.endswith(INCOGNITO_EMAIL_DOMAIN) and "@" in email and len(email) > len(INCOGNITO_EMAIL_DOMAIN)




def prepare_static_logo():










    src_logo = Path("logo superapp.png")
    if not src_logo.exists():
        return None

    try:
        static_dir = Path("static")
        static_dir.mkdir(exist_ok=True)
        dst_logo = static_dir / "logo_superapp.png"

        should_copy = (
            not dst_logo.exists()
            or src_logo.stat().st_size != dst_logo.stat().st_size
            or int(src_logo.stat().st_mtime) > int(dst_logo.stat().st_mtime)
        )
        if should_copy:
            shutil.copyfile(src_logo, dst_logo)



        return "/app/static/logo_superapp.png"
    except Exception:
        return None


def get_safe_page_icon():




    return prepare_static_logo() or "📊"





st.set_page_config(
    page_title="SuperApp Actuary MNC Insurance",
    page_icon=get_safe_page_icon(),
    layout="wide",
)





IDLE_RESET_MINUTES = 30


def _reset_app_session(reason: str = "idle"):

    try:
        st.session_state.clear()
    except Exception:
        pass
    try:
        st.query_params.clear()
    except Exception:
        pass
    st.session_state["login_step"] = "credentials"
    st.session_state["idle_reset_reason"] = reason
    st.session_state["idle_reset_notice"] = True


def _check_idle_timeout(minutes: int = IDLE_RESET_MINUTES):

    now = datetime.now()
    last_seen = st.session_state.get("last_seen_at")

    if last_seen is not None:
        try:
            idle_seconds = (now - last_seen).total_seconds()
            if idle_seconds > minutes * 60:
                _reset_app_session("idle")
                st.rerun()
        except Exception:
            pass

    st.session_state["last_seen_at"] = now





ALLOW_ALL_IPS = True

ALLOWED_SUBNETS = [
    ipaddress.ip_network("10.2.111.0/24"),
    ipaddress.ip_network("10.2.112.0/24"),
    ipaddress.ip_network("192.168.1.0/24"),
    ipaddress.ip_network("192.168.0.0/24"),
    ipaddress.ip_network("192.168.15.0/24"),
    ipaddress.ip_network("192.168.2.45/32"),
]

def get_client_ip():
    try:
        headers = st.context.headers
        xff = headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        return headers.get("remote_addr", "127.0.0.1")
    except Exception:
        return "127.0.0.1"

def is_ip_allowed(ip_str):
    if ALLOW_ALL_IPS:
        return True
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in subnet for subnet in ALLOWED_SUBNETS)
    except Exception:
        return False

client_ip = get_client_ip()

if not is_ip_allowed(client_ip):
    st.markdown(f"""
    <div style="text-align:center; padding-top:120px;">
        <h1 style="color:#d9534f; font-size:48px;">403 Forbidden</h1>
        <p style="font-size:20px;">Akses ditolak. Hubungi Henry jika ini kesalahan.</p>
        <p style="margin-top:20px; color:#777;">Detected IP: {client_ip}</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

st.markdown("""
<style>

/* ===================================================== */
/* PREMIUM ENTERPRISE THEME – NAVY #1E2A3B */
/* ===================================================== */

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    color: #1a1a1a;
}

.stApp {
    background: linear-gradient(180deg, #f5f7fb 0%, #eef2f8 100%);
}

/* ===================================================== */
/* SIDEBAR */
/* ===================================================== */

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1E2A3B 0%, #151F2E 100%);
    padding-top: 16px;
    border-right: 1px solid rgba(255,255,255,0.06);
}

section[data-testid="stSidebar"] * {
    color: white !important;
}

section[data-testid="stSidebar"] label {
    padding: 6px 10px;
    border-radius: 8px;
    transition: all 0.2s ease;
}

section[data-testid="stSidebar"] label:hover {
    background: rgba(255,255,255,0.08);
}

section[data-testid="stSidebar"] label:hover {
    background: rgba(255,255,255,0.08);
}

/* ===================================================== */
/* FILTER PANEL */
/* ===================================================== */

section[data-testid="stSidebar"] div[data-testid="stExpander"] {
    background: #22385f !important;
    border-radius: 14px !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    overflow: hidden;
    margin-bottom: 14px;
}

/* Pastikan teks judul expander selalu putih terang */
section[data-testid="stSidebar"] summary p {
    color: #ffffff !important;
}

/* Pastikan icon panah juga putih terang */
section[data-testid="stSidebar"] summary svg {
    fill: #ffffff !important;
}

/* Menghilangkan background putih/terang bawaan saat tertutup */
section[data-testid="stSidebar"] details {
    background-color: transparent !important;
}



/* ===================================================== */
/* FILTER PANEL - ULTIMATE OVERRIDE */
/* ===================================================== */

/* 1. Paksa Header Expander selalu Navy & Teks Putih (Cegah Putih-di-atas-Putih) */
section[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    background-color: #2a4470 !important;
    color: white !important;
}

/* 2. Targetkan elemen spesifik di dalam header agar tidak berubah warna */
section[data-testid="stSidebar"] [data-testid="stExpander"] summary span,
section[data-testid="stSidebar"] [data-testid="stExpander"] summary p {
    color: white !important;
    -webkit-text-fill-color: white !important;
}

/* 3. Paksa icon panah tetap putih menyala */
section[data-testid="stSidebar"] [data-testid="stExpander"] summary svg {
    fill: white !important;
    color: white !important;
}

/* 4. Hilangkan background putih saat hover/active yang merusak kontras */
section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover,
section[data-testid="stSidebar"] [data-testid="stExpander"] summary:focus {
    background-color: #34538a !important;
}

/* 5. Bungkus luar Expander */
section[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: #22385f !important;
    border-radius: 14px !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    overflow: hidden;
    margin-bottom: 14px;
}
/* ===================================================== */
/* SELECT STYLING */
/* ===================================================== */


section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    background-color: #2f4b7c !important;
    border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    color: white !important;
    min-height: 40px;
}

/* ===================================================== */
/* HEADER CARD */
/* ===================================================== */

.custom-header {
    background: #1E2A3B;
    padding: 36px;
    border-radius: 18px;
    color: white;
    box-shadow: 0 12px 30px rgba(25,44,77,0.25);
    margin-bottom: 30px;
}

/* ===================================================== */
/* METRICS */
/* ===================================================== */

[data-testid="stMetric"] {
    background: rgba(255,255,255,0.9);
    backdrop-filter: blur(6px);
    padding: 20px;
    border-radius: 16px;
    box-shadow: 
        0 8px 24px rgba(0,0,0,0.06),
        0 1px 0 rgba(255,255,255,0.6) inset;
    border-left: 3px solid #1E2A3B;
    transition: all 0.2s ease;
}

[data-testid="stMetric"]:hover {
    transform: translateY(-4px);
}
/* ===================================================== */
/* BUTTONS */
/* ===================================================== */

.stButton > button,
div.stDownloadButton > button {
    background: #1E2A3B;
    color: white;
    border: none;
    border-radius: 14px;
    padding: 12px 24px;
    font-weight: 600;
    transition: all 0.25s ease;
}

.stButton > button:hover,
div.stDownloadButton > button:hover {
    background: #0f1d33;
    transform: translateY(-2px);
    box-shadow: 0 8px 22px rgba(25,44,77,0.35);
}

/* ===================================================== */
/* DATAFRAME */
/* ===================================================== */

thead tr th {
    background: #eef2f9 !important;
    color: #1E2A3B !important;
    font-weight: 600 !important;
}

tbody tr:hover {
    background-color: #eef2f9 !important;
}

.stDataFrame {
    background: white;
    padding: 10px;
    border-radius: 16px;
    box-shadow: 0 6px 20px rgba(0,0,0,0.05);
}

/* ===================================================== */
/* STACKED PAPER TABS – NAVY THEME */
/* ===================================================== */

/* Remove underline */
div[data-testid="stTabs"] [data-baseweb="tab-highlight"],
div[data-testid="stTabs"] div[role="tablist"]::after {
    display: none !important;
}

/* Tab container */
div[data-testid="stTabs"] div[role="tablist"] {
    display: flex !important;
    flex-wrap: nowrap !important;
    overflow-x: auto !important;
    gap: 10px;
    border-bottom: none !important;
    padding-bottom: 0px;
}

/* Base tab (paper look) */
div[data-testid="stTabs"] button[role="tab"] {
    flex: 0 0 auto !important;
    white-space: nowrap !important;
    background: #e9eef8 !important;
    color: #1E2A3B !important;
    padding: 10px 22px !important;
    border-radius: 14px 14px 0 0 !important;
    border: 1px solid #cfd8ea !important;
    border-bottom: none !important;
    font-weight: 500;
    font-size: 14px;
    position: relative;
    top: 6px;                      /* turun sedikit */
    z-index: 1;
    transition: all 0.25s ease;
}

/* Hover */
div[data-testid="stTabs"] button[role="tab"]:hover {
    background: #dde6f6 !important;
}

/* Active tab (naik ke depan) */
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    background: #1E2A3B !important;
    color: white !important;
    font-weight: 600 !important;
    top: 5px;                      /* naik */
    z-index: 5;
    box-shadow: 0 -4px 12px rgba(0,0,0,0.08);
}

/* Content area biar nyatu sama active tab */
div[data-testid="stTabs"] div[role="tabpanel"] {
    background: white;
    padding: 25px;
    border-radius: 0 16px 16px 16px;
    border: 1px solid #cfd8ea;
    box-shadow: 0 10px 25px rgba(0,0,0,0.05);
}

/* ===================================================== */
/* GLOBAL SCROLLBAR */
/* ===================================================== */

::-webkit-scrollbar {
    width: 8px;
}

::-webkit-scrollbar-thumb {
    background: rgba(0,0,0,0.15);
    border-radius: 10px;
}

/* Fix warna teks saat mengetik di Text Input agar tidak putih di atas putih */
section[data-testid="stSidebar"] input {
    color: #1a1a1a !important;
    -webkit-text-fill-color: #1a1a1a !important;
}

/* Fix warna teks pada dropdown multiselect/select agar kontras */
section[data-testid="stSidebar"] div[data-baseweb="select"] span,
section[data-testid="stSidebar"] div[data-baseweb="select"] div {
    color: white !important;
}

/* Khusus untuk teks yang sedang diketik di pencarian multiselect */
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
    color: white !important;
}

div[data-testid="stTabs"] div[role="tablist"] {
    overflow-x: scroll !important;
    scrollbar-width: thin;  /* Firefox */
}


/* ===================================================== */
/* SPACING IMPROVEMENT */
/* ===================================================== */

.block-container {
    padding-top: 1rem !important;
    padding-bottom: 1rem !important;
}

h1, h2, h3 {
    margin-bottom: 18px !important;
}

/* Animasi Berkedip (Pulse) */
@keyframes blink-red {
    0% { background-color: rgba(255, 0, 0, 0.1); box-shadow: 0 0 5px rgba(255, 0, 0, 0.2); }
    50% { background-color: rgba(255, 0, 0, 0.3); box-shadow: 0 0 20px rgba(255, 0, 0, 0.6); }
    100% { background-color: rgba(255, 0, 0, 0.1); box-shadow: 0 0 5px rgba(255, 0, 0, 0.2); }
}

/* Class khusus untuk Alert */
.cor-alert [data-testid="stMetric"] {
    border-left: 5px solid #ff4b4b !important;
    animation: blink-red 1.5s infinite;
    border: 1px solid #ff4b4b !important;
}



/* ===================================================== */
/* SPACING IMPROVEMENT */
/* ===================================================== */

.block-container {
    padding-top: 1rem !important;
    padding-bottom: 1rem !important;
}

h1, h2, h3 {
    margin-bottom: 18px !important;
}

/* ===================================================== */
/* CUSTOM KPI CARD */
/* ===================================================== */

.kpi-card {
    background: rgba(255,255,255,0.9);
    padding: 20px;
    border-radius: 16px;
    box-shadow: 
        0 8px 24px rgba(0,0,0,0.06),
        0 1px 0 rgba(255,255,255,0.6) inset;
    border-left: 3px solid #1E2A3B;
    transition: all 0.3s ease;
    text-align: center;
}

.kpi-card h4 {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    color: #555;
}

.kpi-card h2 {
    margin: 6px 0 0 0;
    font-size: 28px;
    font-weight: 700;
    color: #1E2A3B;
}

/* DANGER MODE */

@keyframes corPulse {
    0% { box-shadow: 0 0 0 0 rgba(176, 0, 32, 0.5); }
    70% { box-shadow: 0 0 0 18px rgba(176, 0, 32, 0); }
    100% { box-shadow: 0 0 0 0 rgba(176, 0, 32, 0); }
}

.kpi-danger {
    background: linear-gradient(135deg, #7a0015 0%, #b00020 100%);
    color: white !important;
    border-left: 4px solid #ffccd5;
    animation: corPulse 2.8s infinite;
}

.kpi-danger h4,
.kpi-danger h2 {
    color: white !important;
}


/* ===================================================== */
/* ICON DOWNLOAD BUTTONS (PDF/EXCEL) */
/* ===================================================== */
.icon-btn-row{display:flex;gap:12px;align-items:center;}
a.icon-btn{
    display:flex;
    align-items:center;
    justify-content:center;
    width:48px;
    height:48px;
    border-radius:14px;
    text-decoration:none !important;
    box-shadow: 0 8px 20px rgba(25,44,77,0.10);
    transition: transform .12s ease, filter .12s ease, box-shadow .12s ease;
}
a.icon-btn:hover{
    transform: translateY(-1px);
    filter: brightness(0.98);
    box-shadow: 0 10px 24px rgba(25,44,77,0.14);
}
a.icon-btn:active{
    transform: translateY(0px);
    filter: brightness(0.95);
}
a.icon-btn svg{width:22px;height:22px;fill:#ffffff;}
a.icon-btn.gray{background:#5b677a;}
a.icon-btn.excel{background:#2e7d32;}
a.icon-btn.pdf{background:#c62828;}
a.icon-btn.filter{background:#0b5ed7;}

/* === Compact Download Buttons === */
div.stDownloadButton > button {
    height: 42px !important;
    padding: 6px 18px !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    border: none !important;
    transition: all 0.2s ease-in-out !important;
}

/* Primary (PDF) */
div.stDownloadButton:nth-of-type(1) > button {
    background-color: #1F3A5F !important;
    color: white !important;
}

/* Secondary (Excel) */
div.stDownloadButton:nth-of-type(2) > button {
    background-color: #E6EEF8 !important;
    color: #1F3A5F !important;
}

/* Hover effect */
div.stDownloadButton > button:hover {
    transform: translateY(-1px);
    filter: brightness(1.08);
}

/* Cari container yang membungkus dua tombol terakhir */
div[data-testid="stHorizontalBlock"] {
    gap: 12px !important;
}

/* Paksa tombol tidak full width */
div.stDownloadButton {
    width: auto !important;
}

/* Styling tombol */
div.stDownloadButton > button {
    height: 42px !important;
    padding: 6px 18px !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
}


/* ===================================================== */
/* LIGHTWEIGHT HOME PAGE */
/* ===================================================== */

.home-hero {
    position: relative;
    overflow: hidden;
    background:
        radial-gradient(circle at 88% 18%, rgba(255,255,255,0.16) 0, rgba(255,255,255,0.00) 28%),
        linear-gradient(135deg, #1E2A3B 0%, #243e6b 62%, #151F2E 100%);
    color: white;
    border-radius: 26px;
    padding: 34px 36px 32px 36px;
    box-shadow: 0 18px 46px rgba(25,44,77,0.20);
    margin-bottom: 18px;
    border: 1px solid rgba(255,255,255,0.10);
}

.home-hero-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 7px 12px;
    border-radius: 999px;
    background: rgba(255,255,255,0.13);
    color: #eaf1fb;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 14px;
}

.home-hero h1 {
    color: white !important;
    margin: 0 0 6px 0 !important;
    font-size: clamp(30px, 3.2vw, 44px);
    line-height: 1.08;
    letter-spacing: -0.02em;
    font-weight: 780;
}

.home-tagline {
    font-size: clamp(18px, 2vw, 24px);
    font-weight: 720;
    color: #ffffff;
    margin: 8px 0 12px 0;
}

.home-desc {
    font-size: 14.5px;
    line-height: 1.65;
    color: rgba(255,255,255,0.90);
    max-width: 880px;
}

.home-hero-footer {
    margin-top: 18px;
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
}

.home-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(255,255,255,0.11);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 999px;
    padding: 8px 12px;
    font-size: 12.5px;
    color: rgba(255,255,255,0.92);
    font-weight: 650;
}

.home-section-title {
    font-size: 20px;
    font-weight: 780;
    color: #1E2A3B;
    margin: 18px 0 10px 2px;
    letter-spacing: -0.01em;
}

.home-card {
    background: rgba(255,255,255,0.94);
    border-radius: 21px;
    padding: 22px 22px 20px 22px;
    box-shadow:
        0 12px 28px rgba(20,35,61,0.06),
        0 1px 0 rgba(255,255,255,0.75) inset;
    border: 1px solid rgba(25,44,77,0.08);
    min-height: 176px;
}

.home-card-icon {
    width: 46px;
    height: 46px;
    border-radius: 15px;
    background: #eaf0fb;
    color: #1E2A3B;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 21px;
    margin-bottom: 13px;
}

.home-card h3 {
    color: #1E2A3B !important;
    font-size: 18px;
    margin: 0 0 7px 0 !important;
    line-height: 1.15;
}

.home-card p {
    color: #53637d;
    font-size: 13.5px;
    line-height: 1.58;
    margin: 0;
}

.actunova-panel {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 230px;
    gap: 22px;
    align-items: center;
    background: linear-gradient(135deg, #ffffff 0%, #f5f8fd 100%);
    border: 1px solid rgba(25,44,77,0.10);
    border-radius: 23px;
    padding: 24px 26px;
    box-shadow: 0 12px 30px rgba(20,35,61,0.055);
    margin-top: 12px;
    margin-bottom: 8px;
}

.actunova-panel h3 {
    color: #1E2A3B !important;
    margin: 0 0 7px 0 !important;
    font-size: 21px;
}

.actunova-panel p {
    color: #53637d;
    line-height: 1.62;
    font-size: 14px;
    margin: 0;
}

.actunova-badge {
    display: inline-flex;
    width: fit-content;
    align-items: center;
    gap: 7px;
    padding: 7px 11px;
    border-radius: 999px;
    background: #eaf0fb;
    color: #1E2A3B;
    font-size: 12.5px;
    font-weight: 750;
    margin-bottom: 10px;
}

.module-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
    margin-top: 8px;
}

.module-tile {
    display: block;
    text-decoration: none !important;
    background: rgba(255,255,255,0.92);
    border: 1px solid rgba(25,44,77,0.08);
    border-radius: 19px;
    padding: 18px 18px 16px 18px;
    min-height: 150px;
    box-shadow: 0 10px 24px rgba(20,35,61,0.052);
    transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease;
}

.module-tile:hover {
    transform: translateY(-3px);
    box-shadow: 0 16px 34px rgba(20,35,61,0.10);
    border-color: rgba(25,44,77,0.18);
}

.module-tile-top {
    display: flex;
    align-items: center;
    gap: 11px;
    margin-bottom: 10px;
}

.module-icon {
    width: 38px;
    height: 38px;
    border-radius: 13px;
    background: #1E2A3B;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
}

.module-title {
    color: #1E2A3B;
    font-size: 15.5px;
    font-weight: 800;
    line-height: 1.15;
}

.module-desc {
    color: #5e6e86;
    font-size: 13px;
    line-height: 1.52;
}

.home-note {
    background: rgba(25,44,77,0.055);
    border-left: 4px solid #1E2A3B;
    border-radius: 14px;
    padding: 13px 15px;
    color: #314562;
    margin-top: 18px;
    font-size: 13.5px;
}

/* Floating ActuNova nudge on Home */
.actunova-float-cta {
    position: fixed;
    right: 24px;
    top: 86px;
    z-index: 9999;
    text-decoration: none !important;
    background: linear-gradient(135deg, #1E2A3B 0%, #2b4a7d 100%);
    color: #ffffff !important;
    border: 1px solid rgba(255,255,255,0.20);
    border-radius: 999px;
    padding: 13px 17px;
    box-shadow: 0 18px 42px rgba(25,44,77,0.32);
    font-weight: 780;
    font-size: 14px;
    display: inline-flex;
    align-items: center;
    gap: 9px;
    animation: actunovaNudge 8.5s ease-in-out forwards;
}

.actunova-float-cta:hover {
    transform: translateY(-2px);
    box-shadow: 0 22px 48px rgba(25,44,77,0.38);
    color: #ffffff !important;
}

@keyframes actunovaNudge {
    0%   { opacity: 0; transform: translateY(-14px); pointer-events: none; }
    10%  { opacity: 1; transform: translateY(0); pointer-events: auto; }
    78%  { opacity: 1; transform: translateY(0); pointer-events: auto; }
    100% { opacity: 0; transform: translateY(-14px); pointer-events: none; }
}

.actunova-link-btn {
    display: inline-flex;
    width: 100%;
    align-items: center;
    justify-content: center;
    box-sizing: border-box;
    text-decoration: none !important;
    background: #1E2A3B;
    color: #ffffff !important;
    border-radius: 14px;
    padding: 12px 16px;
    font-weight: 750;
    border: none;
    box-shadow: 0 8px 22px rgba(25,44,77,0.20);
}

.actunova-link-btn:hover {
    background: #0f1d33;
    color: #ffffff !important;
    transform: translateY(-1px);
}

.anchor-target {
    scroll-margin-top: 24px;
}


@media (max-width: 980px) {
    .module-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .actunova-panel {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 640px) {
    .module-grid {
        grid-template-columns: 1fr;
    }
    .home-hero {
        padding: 28px 24px;
    }
}



/* ===================================================== */
/* PREMIUM LOGIN PAGE REDESIGN - SPLIT STORY LOGIN */
/* ===================================================== */

/* Make login feel like a real landing page, not only a form */
.login-ambient-bg {
    position: fixed;
    inset: 0;
    z-index: -5;
    background:
        radial-gradient(circle at 9% 14%, rgba(50, 88, 145, 0.30) 0, rgba(50, 88, 145, 0.00) 29%),
        radial-gradient(circle at 84% 78%, rgba(67, 113, 178, 0.18) 0, rgba(67, 113, 178, 0.00) 31%),
        radial-gradient(circle at 45% 48%, rgba(255,255,255,0.90) 0, rgba(255,255,255,0.00) 35%),
        linear-gradient(135deg, #eef3fa 0%, #fbfcfe 47%, #e9f0f8 100%);
}

.login-top-spacer {
    height: 22px;
}

/* Reduce top padding only when login is shown */
.block-container:has(.login-ambient-bg) {
    padding-top: 0.6rem !important;
    max-width: 1280px !important;
}

/* Hide sidebar before login, so login feels full-screen */
[data-testid="stSidebar"]:has(~ div .login-ambient-bg),
section[data-testid="stSidebar"]:has(.login-ambient-bg) {
    display: none !important;
}

/* Left visual storytelling area */
.login-visual-stage {
    position: relative;
    min-height: 640px;
    padding: 42px 22px 32px 10px;
    overflow: visible;
}

.login-main-copy {
    max-width: 510px;
    margin-top: 54px;
}

.login-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: 999px;
    background: rgba(25,44,77,0.08);
    color: #1E2A3B;
    font-size: 12px;
    font-weight: 850;
    letter-spacing: .08em;
    text-transform: uppercase;
    border: 1px solid rgba(25,44,77,0.08);
    margin-bottom: 18px;
}

.login-visual-title {
    font-size: clamp(42px, 5.4vw, 72px);
    line-height: 0.98;
    letter-spacing: -0.055em;
    font-weight: 900;
    color: #0f172a;
    margin: 0;
}

.login-visual-title span {
    color: #0b63ce;
}

.login-visual-subtitle {
    color: #5d6b82;
    max-width: 500px;
    line-height: 1.65;
    font-size: 15px;
    margin-top: 20px;
}

.login-visual-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 9px;
    margin-top: 22px;
}

.login-visual-pill {
    padding: 8px 11px;
    border-radius: 999px;
    background: rgba(255,255,255,0.74);
    color: #304866;
    border: 1px solid rgba(25,44,77,0.08);
    font-size: 12.5px;
    font-weight: 760;
    box-shadow: 0 9px 22px rgba(20,35,61,0.05);
}

.login-floating-canvas {
    position: absolute;
    right: 24px;
    top: 78px;
    width: min(430px, 48vw);
    height: 500px;
    pointer-events: none;
}

.float-card {
    position: absolute;
    border-radius: 24px;
    background: rgba(255,255,255,0.80);
    border: 1px solid rgba(255,255,255,0.72);
    box-shadow: 0 28px 70px rgba(20,35,61,0.18), 0 1px 0 rgba(255,255,255,0.86) inset;
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
}

.float-card.primary {
    top: 78px;
    right: 12px;
    width: 310px;
    height: 210px;
    padding: 22px;
    background: linear-gradient(145deg, rgba(25,44,77,0.96) 0%, rgba(44,74,122,0.92) 100%);
    color: white;
    animation: floatSlow 7s ease-in-out infinite;
}

.float-card.secondary {
    top: 254px;
    left: 10px;
    width: 250px;
    height: 168px;
    padding: 18px;
    animation: floatSlow 8s ease-in-out .6s infinite;
}

.float-card.micro {
    top: 10px;
    left: 84px;
    min-width: 176px;
    padding: 13px 15px;
    border-radius: 18px;
    animation: floatSlow 7.5s ease-in-out .2s infinite;
}

.float-card.claim {
    right: 0;
    bottom: 28px;
    width: 212px;
    padding: 16px;
    border-radius: 21px;
    animation: floatSlow 8.5s ease-in-out .8s infinite;
}

.card-kicker {
    font-size: 11px;
    font-weight: 800;
    letter-spacing: .08em;
    text-transform: uppercase;
    opacity: .74;
    margin-bottom: 8px;
}

.card-big-number {
    font-size: 42px;
    font-weight: 900;
    letter-spacing: -0.05em;
    line-height: 1;
}

.card-caption {
    font-size: 12.2px;
    line-height: 1.45;
    color: rgba(255,255,255,0.78);
    margin-top: 10px;
}

.card-dark-text { color: #1E2A3B; }
.card-muted-text { color: #64748b; }

.login-chart-bars {
    display: flex;
    align-items: end;
    gap: 8px;
    height: 72px;
    margin-top: 14px;
    padding: 0 2px;
}

.login-chart-bars span {
    display: block;
    width: 22px;
    border-radius: 999px 999px 6px 6px;
    background: linear-gradient(180deg, #315b93 0%, #1E2A3B 100%);
    box-shadow: 0 8px 16px rgba(25,44,77,0.16);
}

.login-micro-row {
    display: flex;
    align-items: center;
    gap: 10px;
}

.login-micro-icon {
    width: 38px;
    height: 38px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #eaf1fb;
    color: #1E2A3B;
    font-size: 18px;
    flex: 0 0 auto;
}

.login-micro-title {
    color: #1E2A3B;
    font-size: 13px;
    font-weight: 840;
    line-height: 1.1;
}

.login-micro-sub {
    color: #64748b;
    font-size: 11.5px;
    font-weight: 650;
    margin-top: 3px;
}

.actunova-orb {
    position: absolute;
    top: 244px;
    right: 274px;
    width: 86px;
    height: 86px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #0b63ce 0%, #75a7ff 100%);
    color: white;
    font-size: 36px;
    box-shadow: 0 22px 48px rgba(11,99,206,0.28);
    border: 6px solid rgba(255,255,255,0.74);
    animation: orbPulse 4.2s ease-in-out infinite;
}

.login-dot {
    position: absolute;
    width: 14px;
    height: 14px;
    border-radius: 99px;
    background: #0b63ce;
    opacity: .22;
}
.login-dot.one { left: 32px; top: 24px; width: 20px; height: 20px; }
.login-dot.two { right: 42px; top: 30px; }
.login-dot.three { left: 44%; bottom: 22px; width: 18px; height: 18px; background: #1E2A3B; }

@keyframes floatSlow {
    0%, 100% { transform: translate3d(0,0,0) rotate(0deg); }
    50% { transform: translate3d(0,-12px,0) rotate(-0.4deg); }
}

@keyframes orbPulse {
    0%, 100% { transform: scale(1); box-shadow: 0 22px 48px rgba(11,99,206,0.28); }
    50% { transform: scale(1.06); box-shadow: 0 26px 58px rgba(11,99,206,0.38); }
}

/* Right login form card */
div[data-testid="stForm"]:has(.login-form-anchor) {
    width: min(100%, 470px);
    margin: 64px auto 24px auto;
    padding: 34px 34px 28px 34px;
    border-radius: 30px;
    background: rgba(255,255,255,0.92);
    border: 1px solid rgba(25,44,77,0.10);
    box-shadow: 0 28px 76px rgba(20,35,61,0.16), 0 1px 0 rgba(255,255,255,0.86) inset;
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
}

.login-brand-row {
    display:flex;
    align-items:center;
    gap:14px;
    margin-bottom:22px;
}
.login-logo-mark {
    width:52px;
    height:52px;
    border-radius:18px;
    display:flex;
    align-items:center;
    justify-content:center;
    color:white;
    font-size:24px;
    font-weight:800;
    background: linear-gradient(135deg, #1E2A3B 0%, #2b4a7d 100%);
    box-shadow: 0 12px 26px rgba(25,44,77,0.28);
}
.login-brand-kicker {
    font-size:12px;
    color:#64748b;
    font-weight:750;
    letter-spacing:.08em;
    text-transform:uppercase;
    margin-bottom:3px;
}
.login-brand-name {
    font-size:18px;
    color:#1E2A3B;
    font-weight:820;
    line-height:1.15;
}
.login-title {
    font-size:31px !important;
    line-height:1.08 !important;
    letter-spacing:-.035em;
    color:#151F2E !important;
    margin:0 0 9px 0 !important;
    font-weight:840 !important;
}
.login-subtitle {
    color:#64748b;
    font-size:14.5px;
    line-height:1.6;
    margin:0 0 22px 0;
}
.login-trust-row {
    display:flex;
    flex-wrap:wrap;
    gap:8px;
    margin:0 0 22px 0;
}
.login-pill {
    display:inline-flex;
    align-items:center;
    gap:6px;
    padding:7px 10px;
    border-radius:999px;
    background:#eef4fb;
    color:#28466f;
    font-size:12px;
    font-weight:730;
    border:1px solid rgba(25,44,77,.07);
}

div[data-testid="stForm"]:has(.login-form-anchor) [data-testid="stTextInput"] label p {
    color:#253858 !important;
    font-weight:760 !important;
    font-size:13px !important;
}
div[data-testid="stForm"]:has(.login-form-anchor) [data-testid="stTextInput"] input {
    border-radius:15px !important;
    border:1px solid rgba(25,44,77,.14) !important;
    background:rgba(255,255,255,.96) !important;
    min-height:46px !important;
    padding-left:14px !important;
    color:#151F2E !important;
    -webkit-text-fill-color:#151F2E !important;
    box-shadow:0 1px 0 rgba(255,255,255,.9) inset;
}
div[data-testid="stForm"]:has(.login-form-anchor) [data-testid="stTextInput"] input:focus {
    border-color:rgba(25,44,77,.52) !important;
    box-shadow:0 0 0 4px rgba(25,44,77,.08) !important;
}
div[data-testid="stForm"]:has(.login-form-anchor) .stFormSubmitButton > button {
    width:100%;
    min-height:50px;
    border-radius:16px !important;
    background:linear-gradient(135deg, #0b63ce 0%, #1E2A3B 100%) !important;
    color:#ffffff !important;
    font-size:15px !important;
    font-weight:840 !important;
    box-shadow:0 14px 30px rgba(25,44,77,.26);
    margin-top:7px;
}
div[data-testid="stForm"]:has(.login-form-anchor) .stFormSubmitButton > button:hover {
    transform:translateY(-2px);
    box-shadow:0 18px 38px rgba(25,44,77,.32);
    filter:brightness(1.04);
}
.login-footer-note {
    text-align:center;
    color:#7b8798;
    font-size:12.5px;
    line-height:1.5;
    margin-top:18px;
}
.login-security-note {
    margin-top:16px;
    padding:12px 13px;
    border-radius:16px;
    background:rgba(25,44,77,.055);
    color:#44546a;
    font-size:12.8px;
    line-height:1.45;
    border:1px solid rgba(25,44,77,.07);
}

@media (max-width: 980px) {
    .login-visual-stage {
        min-height: auto;
        padding: 26px 8px 8px 8px;
        text-align: left;
    }
    .login-main-copy {
        margin: 10px auto 0 auto;
        max-width: 680px;
    }
    .login-floating-canvas {
        position: relative;
        inset: auto;
        width: 100%;
        height: 390px;
        margin-top: 18px;
    }
    .float-card.primary { right: 7%; top: 26px; }
    .float-card.secondary { left: 7%; top: 188px; }
    .float-card.micro { left: 10%; top: 0; }
    .float-card.claim { right: 8%; bottom: 8px; }
    .actunova-orb { right: auto; left: 42%; top: 180px; }
    div[data-testid="stForm"]:has(.login-form-anchor) {
        margin-top: 10px;
    }
}

@media (max-width: 640px){
    .login-top-spacer { height: 4px; }
    .login-visual-stage { padding: 18px 2px 2px 2px; }
    .login-visual-title { font-size: 42px; }
    .login-visual-subtitle { font-size: 13.5px; }
    .login-floating-canvas { display: none; }
    div[data-testid="stForm"]:has(.login-form-anchor) {
        padding:26px 22px 22px 22px;
        border-radius:24px;
        margin-top:12px;
    }
    .login-title { font-size:27px !important; }
}

</style>
""", unsafe_allow_html=True)






PAGE_META = {
    "Apolo Report": {"icon": "📄", "title": "Apolo Report", "desc": "Generate actuarial report outputs and structured analysis more efficiently."},
    "Risk Profile": {"icon": "📊", "title": "Risk Profile", "desc": "Review portfolio performance, CoR, loss ratio, commissions, RI cost, and claim behavior."},
    "Super Chat": {"icon": "💬", "title": "Super Chat", "desc": "Internal one-to-one messaging with optional Risk Profile Document ID context."},
    "Super Production": {"icon": "🏭", "title": "Super Production", "desc": "Monitor production trends and business movement across relevant portfolio dimensions."},
    "Super Askred": {"icon": "💳", "title": "Super Askred", "desc": "Analyze credit insurance portfolio performance and underwriting indicators."},
    "Super FR": {"icon": "🧾", "title": "Super FR", "desc": "Explore facultative reinsurance performance and retention-related insights."},
    "Spasial FR": {"icon": "🗺️", "title": "Spasial FR", "desc": "View spatial/geographic perspectives for facultative reinsurance analysis."},
    "Super MV": {"icon": "🚗", "title": "Super MV", "desc": "Analyze motor vehicle portfolio behavior by brand, segment, and key risk profile."},
    "Super Engineering": {"icon": "🏗️", "title": "Super Engineering", "desc": "Support engineering portfolio analysis and business monitoring."},
    "Beta Page": {"icon": "🧪", "title": "Beta Page", "desc": "Access experimental features before they are finalized."},
    "PA Premium Calculation": {"icon": "🧮", "title": "PA Premium Calculation", "desc": "Support personal accident premium calculation and pricing workflow."},
    "Claim Analysis": {"icon": "🩺", "title": "Claim Analysis", "desc": "Review claim movements, patterns, and portfolio claim behavior."},
    "Profit and Loss": {"icon": "💰", "title": "Profit and Loss", "desc": "Evaluate profitability, financial movement, and underwriting result overview."},
    "Super Renewal": {"icon": "🔁", "title": "Super Renewal", "desc": "Support renewal monitoring and portfolio follow-up workflow."},
    "Super Projection": {"icon": "🔮", "title": "Super Projection", "desc": "Explore projection and premium adequacy support for planning discussion."},
    "ex-Gratia": {"icon": "🤝", "title": "ex-Gratia", "desc": "Support ex-gratia review and related internal workflow."},
}

def open_module_page(page: str, username: str, user_role: str = ""):

    if page == "Apolo Report":
        from apolo_reportgeneratorapp import apolo_main
        apolo_main()
    elif page == "Risk Profile":
        from risk_profileapp import dashboard as risk_main
        risk_main(username)
    elif page == "Super Production":
        from superproduction import dashboard as prod_main
        prod_main()
    elif page == "Super Askred":
        from superaskred import credit_insurance_dashboard
        credit_insurance_dashboard()
    elif page == "Super FR":
        from fr_retention import main as fr_main
        fr_main(username)
    elif page == "Spasial FR":
        from spasialfr import spasial
        spasial()
    elif page == "Super MV":
        from mv_analysis import dashboard1 as mv_main
        mv_main(username)
    elif page == "Super Engineering":
        from ea_analysis import dashboard as ea_main
        ea_main()
    elif page == "Beta Page":
        from calculator_cor import render_combined_ratio_simulator
        render_combined_ratio_simulator()
    elif page == "CoR Calculator":
        from calculator_cor import render_combined_ratio_simulator
        render_combined_ratio_simulator()
    elif page == "PA Premium Calculation":
        from pa_premiumapp import pa_main
        pa_main()
    elif page == "Claim Analysis":
        from claim import main_claim
        main_claim()
    elif page == "Profit and Loss":
        from profitandloss import mainpl
        mainpl()
    elif page == "Super Renewal":
        from renewal import render_renewal_dashboard
        render_renewal_dashboard(path="Renewal as at Mei 2026.xlsx", username=username)
    elif page == "Super Projection":
        from superprojection import premium_adequacy_app
        premium_adequacy_app()
    elif page == "ex-Gratia":
        from ex_gratia import render_exgratia_generator
        render_exgratia_generator(
            risk_paths=(
                "RP260717 v2_part1.xlsx",
                "RP260717 v2_part1.xlsx",
            ),
            username=username,
            user_role=user_role,
        )
    elif page == "Treaty":
        from claim_polis import dashboard
        dashboard(username)
    elif page == "Super Chat":
        render_superapp_chat(username)
    elif page == "IFRS 17":
        from ifrs17 import dashboard1 as risk_main2
        risk_main2(username)
    else:
        st.warning("Page is not available for this account.")




def load_users_and_roles():





    try:
        df_users = pd.read_excel("users_hashed.xlsx", sheet_name="users")
        df_roles = pd.read_excel("users_hashed.xlsx", sheet_name="role_pages")

        users = {}
        user_roles = {}


        for _, r in df_users.iterrows():
            users[str(r["user_id"])] = str(r["user_password"])


        role_map = {}
        for _, r in df_roles.iterrows():
            role_map.setdefault(r["role_name"], []).append(r["page_name"])



        for _role in ["marketing", "claim-mv", "claim-nonmv", "reinsurance", "bod", "direktur marketing", "direktur teknik", "dirmkt", "dirtek"]:
            pages = role_map.setdefault(_role, ["Home"])
            if "ex-Gratia" not in pages:
                pages.append("ex-Gratia")


        for _, r in df_users.iterrows():
            u_hash = str(r["user_id"])
            role = r["role_name"]
            user_roles[u_hash] = role_map.get(role, ["Home"])

        return users, user_roles

    except Exception as e:

        return st.secrets["auth"]["users"], st.secrets["auth"]["roles"]


USERS, USER_ROLES = load_users_and_roles()


def get_current_user_role(username: str) -> str:





    try:
        u_hash = st.session_state.get("u_hash") or hashlib.md5(str(username or "").encode()).hexdigest()
        df_users = pd.read_excel("users_hashed.xlsx", sheet_name="users")
        if {"user_id", "role_name"}.issubset(df_users.columns):
            hit = df_users[df_users["user_id"].astype(str) == str(u_hash)]
            if not hit.empty:
                return str(hit.iloc[0]["role_name"]).strip().lower()
    except Exception:
        pass
    try:
        return str(st.session_state.get("user_role", "")).strip().lower()
    except Exception:
        return ""

SENDER_EMAIL = st.secrets["auth"]["smtp_user"]
APP_PASSWORD = st.secrets["auth"]["smtp_pass"]




def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp_email(receiver_email, otp):
    subject = "[MNC Insurance] OTP Login"
    body = f"""\
<html>
  <body style="font-family: Arial, sans-serif; line-height:1.5; color:#333;">
    <p>Halo {receiver_email},</p>
    <p>Ini adalah email OTP untuk login ke <b>SuperApp Actuary MNC Insurance</b>.</p>
    <p><b>OTP Anda:</b> {otp}<br>
       <b>Berlaku selama:</b> {OTP_EXPIRY_HOURS} jam
    </p>
    <p>Jika Anda tidak meminta OTP ini, harap abaikan email ini atau segera hubungi Henry.</p>
    <p>Terima kasih,<br>
       <b>Henry Immanuel Sihombing</b><br>
       Actuary at MNC Insurance
    </p>
  </body>
</html>
"""
    msg = MIMEMultipart("alternative")
    msg["From"] = SENDER_EMAIL
    msg["To"] = receiver_email
    msg["Subject"] = subject
    msg["Reply-To"] = SENDER_EMAIL
    msg.attach(MIMEText(body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)

def is_otp_expired(created_at):
    if created_at is None:
        return True
    return datetime.now() > created_at + timedelta(hours=OTP_EXPIRY_HOURS)




def enforce_auth():
    if "auth" in st.session_state:
        data = st.session_state.auth
        if is_otp_expired(data["created"]):
            st.session_state.clear()
            return None
        return data["username"]
    return None





def _render_html_block(markup: str, height: int | None = None):





    markup = dedent(markup).strip()
    try:
        if hasattr(st, "html"):
            st.html(markup)
        else:
            import streamlit.components.v1 as components
            components.html(markup, height=height or 560, scrolling=False)
    except Exception:

        st.markdown(markup, unsafe_allow_html=True)


def _render_login_visual(step_label: str = "Actuarial Intelligence"):

    brand_mark = "<div class='sa-login-wordmark'>SuperApp<span>Actuary</span></div>"
    logo_path = Path("logo superapp.png")
    if logo_path.exists():
        import base64
        logo_data = base64.b64encode(logo_path.read_bytes()).decode("ascii")
        brand_mark = (
            "<div class='sa-login-brand-lockup'>"
            f"<img src='data:image/png;base64,{logo_data}' alt='SuperApp logo'>"
            + brand_mark + "</div>"
        )
    _render_html_block("""
    <style>
      .sa-login-panel{box-sizing:border-box;min-height:650px;padding:48px 52px 32px;
        display:flex;flex-direction:column;justify-content:space-between;
        background:#1E2A3B;color:#fff;font-family:Inter,Arial,sans-serif;border-radius:0 0 0 0;}
      .sa-login-brand-lockup{display:flex;gap:14px;align-items:center;}
      .sa-login-brand-lockup img{width:44px;height:44px;object-fit:contain;background:#fff;border-radius:6px;}
      .sa-login-wordmark{font-size:25px;line-height:1.05;font-weight:750;letter-spacing:-.035em;color:#fff;}
      .sa-login-wordmark span{display:block;font-size:12px;font-weight:400;letter-spacing:.12em;margin-top:7px;}
      .sa-login-main{padding:72px 0 88px;}
      .sa-login-panel h1{font-size:clamp(34px,3.3vw,48px);line-height:1.15;font-weight:700;
        letter-spacing:-.035em;color:#fff!important;margin:0!important;padding:0!important;}
      .sa-login-panel h1 span{color:#a9ccef;}
      .sa-login-description{max-width:300px;font-size:14px;line-height:1.75;color:#dae4f1;margin:26px 0 0;}
      .sa-login-meta{font-size:11px;line-height:1.8;color:#bdcde0;border-top:1px solid rgba(255,255,255,.25);padding-top:24px;margin-top:20px;}
      .sa-login-footer{display:flex;justify-content:space-between;align-items:center;gap:20px;font-size:11px;color:#bdcde0;border-top:1px solid rgba(255,255,255,.25);padding-top:22px;margin-top:25px;}
      .sa-login-footer span{opacity:.85;}
      @media(max-width:640px){.sa-login-panel{min-height:330px;padding:28px;}
        .sa-login-main{padding:40px 0;}.sa-login-panel h1{font-size:34px;}
        .sa-login-meta{font-size:10px;}}
    </style>
    <section class="sa-login-panel">
    """ + brand_mark + """
      <div class="sa-login-main">
        <h1><span>Precision</span><br>Makes the Future.</h1>
        <p class="sa-login-description">Your workspace for actuarial analysis,<br>
        portfolio insights, and reporting.</p>
      </div>
      <div class="sa-login-footer"><span>MNC Insurance · SuperApp Actuary</span><span>Precision Makes the Future.</span></div>
    </section>
    """, height=660)


def _render_login_background():

    st.markdown("""
    <style>
      .stApp:has(.sa-login-page-marker){background:#ffffff!important;}
      body:has(.sa-login-page-marker){overflow:hidden;}
      .block-container:has(.sa-login-page-marker){
        max-width:100%!important;padding:0!important;}
      div.st-key-sa_login_split{
        min-height:calc(100vh - 20px)!important;
        background:#fff;border:none!important;border-radius:0!important;
        overflow:hidden;box-shadow:none!important;padding:0!important;}
      div.st-key-sa_login_split [data-testid="stHorizontalBlock"]{
        gap:0!important;align-items:stretch!important;}
      div.st-key-sa_login_split [data-testid="stColumn"]{
        min-width:0!important;padding:0!important;flex:1 1 0!important;}
      div.st-key-sa_login_split [data-testid="stColumn"]:first-child{background:#1E2A3B;}
      div.st-key-sa_login_split [data-testid="stColumn"] [data-testid="stVerticalBlock"]{gap:0!important;}
      div.st-key-sa_login_split [data-testid="stForm"]{
        box-sizing:border-box!important;width:100%!important;max-width:100%!important;
        margin:0!important;padding:52px 52px 32px!important;border:0!important;
        border-radius:0!important;background:#fff!important;box-shadow:none!important;
        backdrop-filter:none!important;}
      div.st-key-sa_login_split [data-testid="stForm"] [data-testid="stVerticalBlock"]{gap:18px!important;}
      .sa-form-heading{font-family:Inter,Arial,sans-serif;margin-bottom:8px;}
      .sa-form-heading h2{font-size:24px!important;color:#1E2A3B!important;font-weight:700!important;
        line-height:1.25!important;margin:0 0 10px!important;padding:0!important;letter-spacing:-.025em;}
      .sa-form-heading p{font-size:13px!important;line-height:1.6;color:#5b6573;margin:0!important;}
      div.st-key-sa_login_split [data-testid="stTextInput"] label p{
        font-size:13px!important;font-weight:500!important;color:#26364b!important;}
      div.st-key-sa_login_split [data-testid="stTextInput"] [data-baseweb="input"]{
        border:1px solid #9ba7b6!important;border-radius:4px!important;background:#fff!important;box-shadow:none!important;}
      div.st-key-sa_login_split [data-testid="stTextInput"] input{
        min-height:46px!important;background:#fff!important;border:0!important;border-radius:4px!important;
        padding-left:12px!important;color:#1E2A3B!important;box-shadow:none!important;font-size:14px!important;}
      div.st-key-sa_login_split [data-testid="stTextInput"] [data-baseweb="input"]:focus-within{
        outline:2px solid #315e91;outline-offset:2px;}
      div.st-key-sa_login_split [data-testid="stFormSubmitButton"]{width:100%!important;}
      div.st-key-sa_login_split [data-testid="stFormSubmitButton"] button{
        width:100%!important;min-height:48px!important;border-radius:999px!important;
        background:#1E2A3B!important;color:#fff!important;border:1px solid #1E2A3B!important;
        font-size:14px!important;font-weight:650!important;box-shadow:none!important;
        margin:0!important;transform:none!important;}
      div.st-key-sa_login_split [data-testid="stFormSubmitButton"] button:hover{background:#29466f!important;}
      div.st-key-sa_login_split [data-testid="stFormSubmitButton"] ~ [data-testid="stFormSubmitButton"] button,
      div.st-key-sa_login_split [data-testid="stElementContainer"]:has([data-testid="stFormSubmitButton"])
        ~ [data-testid="stElementContainer"] [data-testid="stFormSubmitButton"] button{
        background:#fff!important;color:#1E2A3B!important;border-color:#7d8999!important;}
      div.st-key-sa_login_split [data-testid="stFormSubmitButton"] button:focus-visible{
        outline:2px solid #315e91;outline-offset:3px;}
      .sa-login-form-note{font-size:11px;line-height:1.7;color:#687382;margin-top:10px;}
      @media(max-width:760px){
        .block-container:has(.sa-login-page-marker){padding:16px!important;}
        div.st-key-sa_login_split [data-testid="stHorizontalBlock"]{flex-direction:column!important;}
        div.st-key-sa_login_split [data-testid="stColumn"]{width:100%!important;flex:auto!important;}
        div.st-key-sa_login_split [data-testid="stForm"]{padding:30px 28px!important;}
      }
    </style>
    <div class="sa-login-page-marker"></div>
    """, unsafe_allow_html=True)


def _login_shell_open(title: str, subtitle: str, icon: str = "📊"):
    st.markdown(dedent(f"""
    <div class="login-page-shell">
      <div class="login-card">
        <div class="login-brand-row">
          <div class="login-logo-mark">SA</div>
          <div>
            <div class="login-brand-kicker">MNC Insurance</div>
            <div class="login-brand-name">SuperApp Actuary</div>
          </div>
        </div>
        <h1 class="login-title">{html.escape(title)}</h1>
        <p class="login-subtitle">{html.escape(subtitle)}</p>
        <div class="login-trust-row">
          <div class="login-pill">Secure access</div>
          <div class="login-pill">Confidential</div>
        </div>
    """).strip(), unsafe_allow_html=True)


def _login_shell_close(note: str = "Confidential internal platform. Authorized users only."):
    st.markdown(dedent(f"""
        <div class="login-security-note">{html.escape(note)}</div>
        <div class="login-footer-note">Precision Makes the Future.</div>
      </div>
    </div>
    """).strip(), unsafe_allow_html=True)


def _render_login_form_header(title: str, subtitle: str, icon: str = "📊"):
    st.markdown(
        "<div class='login-form-anchor'></div>"
        "<div class='sa-form-heading'>"
        f"<h2>{html.escape(title)}</h2><p>{html.escape(subtitle)}</p></div>",
        unsafe_allow_html=True,
    )


def _render_login_form_footer(note: str = "Confidential internal platform. Authorized users only."):
    st.markdown(
        f"<div class='sa-login-form-note'>{html.escape(note)}</div>"
        "<div style='margin-top:12px;color:#64748B;font-size:12px;'>Developed by "
        "<b>Henry Immanuel Sihombing</b> · MNC Insurance</div>",
        unsafe_allow_html=True,
    )


def login():
    if "login_step" not in st.session_state:
        st.session_state.login_step = "credentials"
        st.session_state.otp_sent = False

    _render_login_background()

    if st.session_state.pop("idle_reset_notice", False):
        st.info("Session lama sudah di-refresh otomatis. Silakan login kembali.")


    with st.container(key="sa_login_split"):
        left_col, right_col = st.columns([1.05, 0.95], gap="small")


    if st.session_state.login_step == "credentials":
        with left_col:
            _render_login_visual("SuperApp Actuary")

        with right_col:
            with st.form("login_credentials_form", clear_on_submit=False, border=False):
                _render_login_form_header(
                    "Sign in",
                    "Access your SuperApp Actuary workspace.",
                    "📊",
                )
                username = st.text_input("Username", placeholder="Enter your username")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                login_btn = st.form_submit_button("Sign in", use_container_width=True)

                incognito_btn = False
                if INCOGNITO_LOGIN_ENABLED:
                    st.markdown(
                        "<div style='text-align:center;color:#94A3B8;font-size:12px;font-weight:700;margin:12px 0 8px 0;'>or</div>",
                        unsafe_allow_html=True,
                    )
                    incognito_btn = st.form_submit_button("Continue with MNC Email OTP", use_container_width=True)

                _render_login_form_footer()

        if incognito_btn:
            st.session_state.login_step = "incognito_email"
            st.rerun()

        if login_btn:
            u_hash = hashlib.md5(username.encode()).hexdigest()
            p_hash = hashlib.md5(password.encode()).hexdigest()
            if u_hash in USERS and USERS[u_hash] == p_hash:
                st.session_state.username = username
                st.session_state.u_hash = u_hash
                log_login(username)
                if use_otp and should_use_otp(username):
                    st.session_state.login_step = "email_auth"
                else:
                    st.session_state.auth = {"username": username, "created": datetime.now()}



                    st.session_state["active_page"] = "Home"
                    st.session_state["force_home_once"] = True
                    try:
                        st.query_params.clear()
                    except Exception:
                        pass
                st.rerun()
            else:
                st.error("❌ Username atau password salah")


    elif st.session_state.login_step == "incognito_email":
        with left_col:
            _render_login_visual("Incognito OTP access")

        with right_col:
            with st.form("login_incognito_email_form", clear_on_submit=False, border=False):
                _render_login_form_header(
                    "Incognito Access",
                    "Enter your MNC Insurance email. We will send a one-time password to verify access.",
                    "🕶️",
                )
                incognito_email_input = st.text_input(
                    "Email @mnc-insurance.com",
                    placeholder="name@mnc-insurance.com",
                )
                send_incognito_btn = st.form_submit_button("Send OTP →", use_container_width=True)
                back_to_login_btn = st.form_submit_button("Back to Username Login", use_container_width=True)
                _render_login_form_footer("OTP-only access is limited to authorized MNC Insurance email addresses.")

        if back_to_login_btn:
            st.session_state.login_step = "credentials"
            st.rerun()

        if send_incognito_btn:
            email = normalize_mnc_email(incognito_email_input)
            if not is_valid_mnc_email(email):
                st.error("Email harus menggunakan domain @mnc-insurance.com")
            else:
                otp = generate_otp()
                st.session_state.incognito_email = email
                st.session_state[f"incognito_otp_{email}"] = otp
                st.session_state[f"incognito_otp_created_{email}"] = datetime.now()
                send_otp_email(email, otp)
                st.session_state.login_step = "incognito_otp"
                st.success("OTP terkirim. Cek email MNC Insurance Anda.")
                st.rerun()


    elif st.session_state.login_step == "incognito_otp":
        with left_col:
            _render_login_visual("Verify MNC email")

        email = normalize_mnc_email(st.session_state.get("incognito_email", ""))
        with right_col:
            with st.form("login_incognito_otp_form", clear_on_submit=False, border=False):
                _render_login_form_header(
                    "Enter OTP",
                    f"Enter the one-time password sent to {email}.",
                    "🔐",
                )
                user_otp = st.text_input("Masukkan OTP", max_chars=6, placeholder="6-digit OTP")
                verify_incognito_btn = st.form_submit_button("Verify & Enter →", use_container_width=True)
                resend_incognito_btn = st.form_submit_button("Send New OTP", use_container_width=True)
                _render_login_form_footer("This access uses email verification only and is logged as incognito access.")

        if resend_incognito_btn:
            if not is_valid_mnc_email(email):
                st.session_state.login_step = "incognito_email"
                st.rerun()
            otp = generate_otp()
            st.session_state[f"incognito_otp_{email}"] = otp
            st.session_state[f"incognito_otp_created_{email}"] = datetime.now()
            send_otp_email(email, otp)
            st.success("OTP baru terkirim. Cek email Anda.")
            st.rerun()

        if verify_incognito_btn:
            otp_key = f"incognito_otp_{email}"
            created_key = f"incognito_otp_created_{email}"
            stored_otp = st.session_state.get(otp_key)
            stored_created = st.session_state.get(created_key)

            if not is_valid_mnc_email(email):
                st.error("Email tidak valid. Silakan ulangi proses login incognito.")
                st.session_state.login_step = "incognito_email"
                st.rerun()
            elif stored_otp is None or is_otp_expired(stored_created):
                st.error("OTP expired atau tidak ditemukan. Minta OTP ulang.")
                st.session_state.pop(otp_key, None)
                st.session_state.pop(created_key, None)
                st.session_state.login_step = "incognito_email"
                st.rerun()
            elif user_otp == stored_otp:
                st.session_state.auth = {
                    "username": email,
                    "created": datetime.now(),
                    "mode": "incognito",
                }
                st.session_state.username = email
                st.session_state.u_hash = INCOGNITO_SESSION_ROLE_KEY
                st.session_state["active_page"] = "Home"
                st.session_state["force_home_once"] = True
                try:
                    st.query_params.clear()
                except Exception:
                    pass
                st.session_state.pop(otp_key, None)
                st.session_state.pop(created_key, None)
                log_login(f"[Incognito] {email}", client_ip)
                st.success("Login incognito sukses!")
                st.rerun()
            else:
                st.error("OTP salah.")


    elif st.session_state.login_step == "email_auth":
        with left_col:
            _render_login_visual("Two-step verification")

        with right_col:
            with st.form("login_email_form", clear_on_submit=False, border=False):
                _render_login_form_header(
                    "Email Authentication",
                    "Enter your corporate email to receive a one-time password.",
                    "✉️",
                )
                email_input = st.text_input("Email @mnc-insurance.com", placeholder="name@mnc-insurance.com")
                send_btn = st.form_submit_button("Send OTP →", use_container_width=True)
                _render_login_form_footer("OTP will be sent to your corporate email and is valid for this login window.")

        if send_btn:
            if not email_input.endswith("@mnc-insurance.com"):
                st.error("Email harus @mnc-insurance.com")
            else:
                otp = generate_otp()
                uname = st.session_state.username
                st.session_state[f"otp_{uname}"] = otp
                st.session_state[f"otp_created_{uname}"] = datetime.now()
                st.session_state.email_input = email_input
                send_otp_email(email_input, otp)
                st.session_state.login_step = "otp"
                st.success("OTP terkirim. Cek email Anda.")
                st.rerun()


    elif st.session_state.login_step == "otp":
        with left_col:
            _render_login_visual("Secure OTP access")

        with right_col:
            with st.form("login_otp_form", clear_on_submit=False, border=False):
                _render_login_form_header(
                    "Enter OTP",
                    "Enter the one-time password sent to your corporate email.",
                    "🔐",
                )
                user_otp = st.text_input("Masukkan OTP", max_chars=6, placeholder="6-digit OTP")
                verify_btn = st.form_submit_button("Verify →", use_container_width=True)
                _render_login_form_footer("For security, OTP access expires after the configured login window.")

        if verify_btn:
            uname = st.session_state.username
            otp_key = f"otp_{uname}"
            created_key = f"otp_created_{uname}"

            stored_otp = st.session_state.get(otp_key)
            stored_created = st.session_state.get(created_key)

            if stored_otp is None or is_otp_expired(stored_created):
                st.error("OTP expired atau tidak ditemukan. Minta OTP ulang.")
                st.session_state.pop(otp_key, None)
                st.session_state.pop(created_key, None)
                st.session_state.login_step = "email_auth"
                st.rerun()
            elif user_otp == stored_otp:
                update_otp_date(uname)
                st.session_state.auth = {
                    "username": uname,
                    "created": datetime.now()
                }

                st.session_state["active_page"] = "Home"
                st.session_state["force_home_once"] = True
                try:
                    st.query_params.clear()
                except Exception:
                    pass
                st.session_state.pop(otp_key, None)
                st.session_state.pop(created_key, None)
                st.success("Login sukses!")
                st.rerun()
            else:
                st.error("OTP salah.")




def _module_href(page_name: str) -> str:
    from urllib.parse import quote
    return f"?page={quote(str(page_name))}"


def _request_page_transition(page_name: str) -> None:





    page_name = str(page_name)
    current_page = str(st.session_state.get("active_page", ""))
    if page_name and page_name != current_page:
        st.session_state["pending_page_loading_overlay"] = page_name
        st.session_state["previous_active_page"] = current_page


def _go_to_page(page_name: str):

    page_name = str(page_name)
    _request_page_transition(page_name)
    st.session_state["active_page"] = page_name
    try:
        st.query_params.clear()
    except Exception:
        pass
    st.rerun()


def _render_module_tiles(menu_items):




    pages = [p for p in (menu_items or []) if p != "Home"]
    if not pages:
        return

    for start in range(0, len(pages), 3):
        cols = st.columns(3, gap="medium")
        for col, page_name in zip(cols, pages[start:start + 3]):
            meta = PAGE_META.get(page_name, {
                "icon": "▣",
                "title": page_name,
                "desc": "Open this module from your authorized workspace."
            })
            with col:
                with st.container(border=True):
                    st.markdown(f"### {meta['icon']} {meta['title']}")
                    st.caption(meta["desc"])
                    if st.button(
                        f"Open {meta['title']}",
                        key=f"module_open__{page_name}",
                        width="stretch",
                    ):
                        _go_to_page(page_name)



def _render_home_workspace_css() -> None:

    st.markdown("""
    <style>
      .home-workspace-shell{
        margin-top: 8px;
      }
      .home-mode-switch{
        display:flex;
        align-items:center;
        justify-content:center;
        gap:10px;
        margin: 8px 0 18px 0;
      }
      div[class*="st-key-home_mode_wall_btn"] button,
      div[class*="st-key-home_mode_chat_btn"] button,
      div[class*="st-key-home_mode_actunova_btn"] button{
        min-height: 38px !important;
        height: 38px !important;
        padding: 0 16px !important;
        border-radius: 999px !important;
        font-size: 12.5px !important;
        font-weight: 850 !important;
        width: 100% !important;
      }
      .home-active-chip{
        display:inline-flex;
        align-items:center;
        gap:7px;
        padding:7px 12px;
        border-radius:999px;
        background:#EEF6FF;
        color:#003366;
        font-size:12px;
        font-weight:850;
        border:1px solid rgba(0,51,102,0.10);
        margin-bottom: 10px;
      }
      .wall-hero{
        position:relative;
        overflow:hidden;
        border-radius:24px;
        padding:24px 26px;
        background:
          radial-gradient(circle at 88% 12%, rgba(11,99,206,0.12) 0, rgba(11,99,206,0.00) 26%),
          linear-gradient(135deg,#FFFFFF 0%,#F5F8FD 100%);
        border:1px solid rgba(25,44,77,0.10);
        box-shadow:0 14px 34px rgba(20,35,61,0.065);
        margin-bottom:14px;
      }
      .wall-hero-kicker{
        display:inline-flex;
        align-items:center;
        gap:8px;
        padding:7px 11px;
        border-radius:999px;
        background:#EAF1FB;
        color:#1E2A3B;
        font-size:12px;
        font-weight:850;
        border:1px solid rgba(25,44,77,0.08);
        margin-bottom:12px;
      }
      .wall-hero-title{
        color:#1E2A3B;
        font-size:26px;
        line-height:1.08;
        letter-spacing:-0.035em;
        font-weight:900;
        margin:0 0 6px 0;
      }
      .wall-hero-sub{
        color:#64748B;
        font-size:13.5px;
        line-height:1.55;
        max-width:780px;
      }
      .wall-info-card{
        display:flex;
        gap:14px;
        align-items:flex-start;
        border-radius:22px;
        padding:18px 20px;
        background:#FFFFFF;
        border:1px solid rgba(0,51,102,0.12);
        box-shadow:0 12px 28px rgba(15,23,42,0.055);
        margin:12px 0 10px 0;
      }
      .wall-info-icon{
        width:42px;
        height:42px;
        border-radius:15px;
        display:flex;
        align-items:center;
        justify-content:center;
        background:linear-gradient(135deg,#003366 0%,#1F5A91 100%);
        color:white;
        font-size:19px;
        flex:0 0 auto;
        box-shadow:0 10px 22px rgba(0,51,102,0.20);
      }
      .wall-info-label{
        color:#64748B;
        font-size:11.5px;
        font-weight:900;
        letter-spacing:.08em;
        text-transform:uppercase;
        margin-bottom:4px;
      }
      .wall-info-title{
        color:#0F2742;
        font-size:17px;
        font-weight:900;
        line-height:1.25;
        margin-bottom:4px;
      }
      .wall-info-text{
        color:#475569;
        font-size:13.5px;
        line-height:1.55;
      }
      .wall-coming-soon{
        border-radius:18px;
        padding:13px 15px;
        background:rgba(25,44,77,0.045);
        border:1px dashed rgba(25,44,77,0.18);
        color:#53637D;
        font-size:13px;
        line-height:1.45;
        margin-top:12px;
      }
    </style>
    """, unsafe_allow_html=True)


def render_home_wall_of_insight() -> None:

    st.markdown('<div class="home-active-chip">🧱 Wall of Insight</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="wall-hero">
      <div class="wall-hero-kicker">📌 Internal Insight Board</div>
      <div class="wall-hero-title">Wall of Insight</div>
      <div class="wall-hero-sub">
        Tempat informasi, update workflow, dan pengumuman singkat untuk pengguna SuperApp Actuary.
      </div>
    </div>
    <div class="wall-info-card">
      <div class="wall-info-icon">i</div>
      <div>
        <div class="wall-info-label">Pengumuman</div>
        <div class="wall-info-title">Struktur lokasi menu SuperApp Actuary telah diperbarui</div>
        <div class="wall-info-text">
          Sidebar sekarang menggunakan kategori menu agar navigasi lebih ringkas dan mudah ditemukan. Berikut lokasi menu terbaru:
          <div style="margin-top:10px; display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:8px 14px;">
            <div><b>Main</b><br>Home</div>
            <div><b>General Report</b><br>Risk Profile, Super Production, Super Renewal, Profit and Loss</div>
            <div><b>Portofolio Analysis</b><br>Super Askred, Super FR, Spasial FR, Super MV, Super Engineering</div>
            <div><b>Claim</b><br>Claim Analysis, ex-Gratia</div>
            <div><b>ePricing &amp; eReserving</b><br>PA Premium Calculation, IFRS 17</div>
            <div><b>Reinsurance</b><br>Treaty</div>
            <div><b>Reporting</b><br>Apolo Report</div>
            <div><b>Other</b><br>Super Projection, Beta Page</div>
          </div>
        </div>
      </div>
    </div>
    <div class="wall-info-card">
      <div class="wall-info-icon">i</div>
      <div>
        <div class="wall-info-label">Info terbaru</div>
        <div class="wall-info-title">Form pengajuan Klaim ex-gratia dapat diakses di SuperApp Actuary - menu Ex Gratia</div>
        <div class="wall-info-text">
          Gunakan menu Ex Gratia untuk membuat form pengajuan klaim ex-gratia dan menyiapkan dokumen PDF pendukung.
        </div>
      </div>
    </div>
    <div class="wall-coming-soon">
      Info lain akan ditambahkan secara bertahap di Wall of Insight.
    </div>
    """, unsafe_allow_html=True)


def render_home_superchat_lazy(username: str) -> None:

    st.markdown('<div class="home-active-chip">💬 SuperChat</div>', unsafe_allow_html=True)
    render_superapp_chat(username, embedded=True)


def home(username, menu_items=None):



    display_name = str(username).split("@")[0].replace(".", " ").title()
    st.session_state.setdefault("home_workspace_mode", "wall")

    st.markdown(f"""
    <style>
      .home-hero.precision-home {{background:radial-gradient(ellipse at 95% 90%,#315f8c,transparent 55%),linear-gradient(120deg,#101f39,#223c62); border-radius:20px;
        padding:40px; margin-bottom:20px; box-shadow:0 12px 36px #1E2A3B12; border:1px solid #3b5574;}}
      .precision-home-kicker {{font-size:11px; letter-spacing:.12em; color:#c3d3e8;
        text-transform:uppercase; margin-bottom:14px; font-weight:600;}}
      .home-hero.precision-home h1 {{font-size:clamp(28px,3vw,42px); font-weight:650;
        line-height:1.16; letter-spacing:-.035em;}}
      .precision-home-welcome {{margin-top:16px; color:#c9d7e9; font-size:14px;}}
      @media(max-width:640px) {{.home-hero.precision-home {{padding:24px;}}}}
    </style>
    <div class="home-hero precision-home">
        <div class="precision-home-kicker">SuperApp Actuary / MNC Insurance</div>
        <h1>Precision Makes the Future.</h1>
        <div class="precision-home-welcome">Welcome, {html.escape(display_name)}</div>
        <div style="margin-top:10px;color:#c3d3e8;font-size:12px;">Developed by <b>Henry Immanuel Sihombing</b> · MNC Insurance</div>
    </div>
    """, unsafe_allow_html=True)

    _render_home_workspace_css()

    if "Profit and Loss" in (menu_items or []):
        from profitandloss import render_home_loss_drivers
        render_home_loss_drivers()

    st.markdown("""
    <div class="wall-info-card" style="margin-top:0; margin-bottom:14px;">
      <div class="wall-info-icon">i</div>
      <div>
        <div class="wall-info-label">Pengumuman</div>
        <div class="wall-info-title">Struktur lokasi menu SuperApp Actuary telah diperbarui</div>
        <div class="wall-info-text">
          Navigasi atas dikelompokkan menjadi: Main, General Report, Portofolio Analysis, Claim, ePricing &amp; eReserving, Reinsurance, Reporting, dan Other.
          Detail lengkapnya tersedia di Wall of Insight.
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    switch_left, switch_mid1, switch_mid2, switch_mid3, switch_right = st.columns([1.9, 1.08, 1.0, 1.0, 1.9], gap="small")
    with switch_mid1:
        if st.button("Wall of Insight", key="home_mode_wall_btn", width="stretch"):
            st.session_state["home_workspace_mode"] = "wall"
            st.rerun()
    with switch_mid2:
        if st.button("SuperChat", key="home_mode_chat_btn", width="stretch"):
            st.session_state["home_workspace_mode"] = "chat"
            st.rerun()
    with switch_mid3:
        if st.button("ActuNova", key="home_mode_actunova_btn", width="stretch"):
            st.session_state["home_workspace_mode"] = "actunova"
            st.rerun()

    st.markdown('<div class="home-workspace-shell">', unsafe_allow_html=True)
    mode = st.session_state.get("home_workspace_mode", "wall")

    if mode == "actunova":
        st.markdown('<div id="actunova-chat-anchor" class="anchor-target"></div>', unsafe_allow_html=True)
        st.markdown('<div class="home-section-title">ActuNova</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="actunova-panel">
            <div>
                <div class="actunova-badge">✨ AI Assistant</div>
                <h3>ActuNova Assistant</h3>
                <p>
                    Ask ActuNova for actuarial explanations, report navigation, portfolio review, or workflow support.
                </p>
            </div>
            <div></div>
        </div>
        """, unsafe_allow_html=True)
        from superai import SuperAI
        SuperAI(username)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("---")
        return

    if mode == "chat":
        render_home_superchat_lazy(username)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("---")
        return


    render_home_wall_of_insight()
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")



def _show_page_loading_overlay(page_name: str):







    safe_page = html.escape(str(page_name or "module"))
    holder = st.empty()
    holder.markdown(
        f"""
        <style>
          /* Keep the loading mask independent from sidebar width.
             Earlier versions used left:21rem, so when the sidebar was resized
             there was an exposed strip of the old page. The mask now covers the
             full viewport, while the sidebar is explicitly lifted above it. */
          section[data-testid="stSidebar"] {{
            position: relative !important;
            z-index: 2147483200 !important;
          }}
          .superapp-loading-overlay {{
            position: fixed;
            inset: 0;
            z-index: 2147483000;
            display: flex;
            align-items: center;
            justify-content: center;
            background:
              radial-gradient(circle at 50% 42%, rgba(25,44,77,0.08) 0, rgba(25,44,77,0.00) 32%),
              rgba(245, 247, 251, 0.985);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            pointer-events: auto;
          }}
          .superapp-loading-card {{
            width: min(420px, calc(100vw - 42px));
            border-radius: 24px;
            padding: 26px 28px 24px 28px;
            background: rgba(255,255,255,0.96);
            border: 1px solid rgba(25,44,77,0.10);
            box-shadow: 0 22px 60px rgba(15,23,42,0.14);
            text-align: center;
            font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
          }}
          .superapp-loading-spinner {{
            width: 38px;
            height: 38px;
            margin: 0 auto 15px auto;
            border-radius: 999px;
            border: 4px solid #E6EEF8;
            border-top-color: #1E2A3B;
            animation: superappSpin 0.85s linear infinite;
          }}
          .superapp-loading-title {{
            color: #1E2A3B;
            font-size: 18px;
            font-weight: 850;
            letter-spacing: -0.02em;
            margin-bottom: 5px;
          }}
          .superapp-loading-subtitle {{
            color: #64748B;
            font-size: 13px;
            line-height: 1.45;
            margin-bottom: 16px;
          }}
          .superapp-loading-bar {{
            width: 100%;
            height: 7px;
            overflow: hidden;
            border-radius: 999px;
            background: #EAF0F8;
          }}
          .superapp-loading-bar::before {{
            content: "";
            display: block;
            width: 42%;
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, #1E2A3B 0%, #315b93 100%);
            animation: superappProgress 1.05s ease-in-out infinite;
          }}
          @keyframes superappSpin {{
            to {{ transform: rotate(360deg); }}
          }}
          @keyframes superappProgress {{
            0% {{ transform: translateX(-115%); }}
            100% {{ transform: translateX(255%); }}
          }}
        </style>
        <div class="superapp-loading-overlay" aria-live="polite" aria-busy="true">
          <div class="superapp-loading-card">
            <div class="superapp-loading-spinner"></div>
            <div class="superapp-loading-title">Preparing {safe_page}</div>
            <div class="superapp-loading-subtitle">Loading workspace objects. Please wait.</div>
            <div class="superapp-loading-bar"></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return holder

def render_global_footer():

    st.markdown(
        """
        <div class="superapp-global-footer-spacer"></div>
        <footer class="superapp-global-footer">
          <div class="superapp-global-footer-title">SuperApp Actuary · Precision Makes the Future.</div>
          <div class="superapp-global-footer-text">
            Developed by <b>Henry Immanuel Sihombing</b> · MNC Insurance
          </div>
        </footer>
        <style>
          .superapp-global-footer-spacer{
            height: 22px;
          }
          .superapp-global-footer{
            margin-top: 18px;
            padding: 24px 28px;
            border-radius: 0;
            background: #1E2A3B;
            color: #F8FAFC;
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow: none;
            text-align: left;
          }
          .superapp-global-footer-title{
            font-size: 15px;
            font-weight: 850;
            letter-spacing: -0.01em;
            margin-bottom: 4px;
          }
          .superapp-global-footer-text{
            font-size: 12.5px;
            line-height: 1.45;
            color: rgba(248,250,252,0.72);
          }
          .superapp-global-footer-text b{
            color: #FFFFFF;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )







EG_VERIFY_SHEET = "ex_gratia_records"
EG_VERIFY_HASH_FIELDS = [
    "DOC_ID", "CREATED_AT", "CREATED_BY", "STATUS", "CLAIM_NO", "POLICY_NO", "COB",
    "SOURCE_BUSINESS", "INSURED_NAME", "LOSS_DATE", "CLAIM_AMOUNT", "EXGRATIA_AMOUNT", "MNC_SHARE",
    "MARKETING_MANAGER_CONFIRMED_BY", "MARKETING_MANAGER_CONFIRMED_AT",
    "CLAIM_CONFIRMED_BY", "CLAIM_CONFIRMED_AT",
    "REINSURANCE_CONFIRMED_BY", "REINSURANCE_CONFIRMED_AT",
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
    record = record or {}
    payload = {field: _eg_verify_norm(record.get(field, "")) for field in EG_VERIFY_HASH_FIELDS}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(("EXGRATIA-V1|" + raw).encode("utf-8")).hexdigest()[:12].upper()


def _sanitize_eg_doc_id(doc_id: str) -> str:
    return str(doc_id or "").strip().upper().replace(" ", "")


def _get_query_param_first(name: str, default: str = "") -> str:

    try:
        value = st.query_params.get(name, default)
        if isinstance(value, list):
            return str(value[0] if value else default)
        return str(value if value is not None else default)
    except Exception:
        return str(default or "")


def _sanitize_rp_doc_id(doc_id: str) -> str:

    return str(doc_id or "").strip().upper().replace(" ", "")


def _capture_open_rp_query_param() -> str:





    doc_id = _sanitize_rp_doc_id(_get_query_param_first("open_rp", ""))
    if doc_id:
        st.session_state["pending_open_rp_doc_id"] = doc_id
    return doc_id


EXGRATIA_DEEP_LINK_PAGE = "ex-Gratia"
EXGRATIA_DEEP_LINK_VIEWS = {"list", "create", "detail"}


def _capture_exgratia_query_params() -> bool:





    page = _get_query_param_first("page", "").strip()
    view = _get_query_param_first("eg_view", "").strip().lower()
    doc_id = _sanitize_eg_doc_id(_get_query_param_first("eg_doc", ""))

    is_exgratia_route = (
        page == EXGRATIA_DEEP_LINK_PAGE
        and bool(doc_id or view in EXGRATIA_DEEP_LINK_VIEWS)
    )
    if not is_exgratia_route:
        return False

    if doc_id:
        view = "detail"
    elif view not in EXGRATIA_DEEP_LINK_VIEWS:
        view = "list"

    st.session_state["pending_exgratia_route"] = {
        "page": EXGRATIA_DEEP_LINK_PAGE,
        "eg_view": view,
        "eg_doc": doc_id,
    }
    return True


def _restore_exgratia_query_params(route: dict) -> None:

    route = dict(route or {})
    view = str(route.get("eg_view", "list") or "list").strip().lower()
    doc_id = _sanitize_eg_doc_id(route.get("eg_doc", ""))

    if doc_id:
        view = "detail"
    elif view not in EXGRATIA_DEEP_LINK_VIEWS:
        view = "list"

    try:
        st.query_params.clear()
        st.query_params["page"] = EXGRATIA_DEEP_LINK_PAGE
        st.query_params["eg_view"] = view
        if doc_id:
            st.query_params["eg_doc"] = doc_id
    except Exception:
        pass


def _apply_pending_exgratia_after_login(menu_items) -> bool:

    route = st.session_state.pop("pending_exgratia_route", None)
    if not isinstance(route, dict):
        return False

    if EXGRATIA_DEEP_LINK_PAGE not in list(menu_items or []):
        st.session_state.pop("eg_selected_doc_id", None)
        st.session_state["post_login_notice"] = (
            "Akses Ex-Gratia tidak tersedia untuk user ini."
        )
        return False

    view = str(route.get("eg_view", "list") or "list").strip().lower()
    doc_id = _sanitize_eg_doc_id(route.get("eg_doc", ""))

    if doc_id:
        view = "detail"
        st.session_state["eg_selected_doc_id"] = doc_id
        st.session_state["eg_create_mode"] = False
        st.session_state["eg_preparing_create"] = False
    elif view == "create":
        st.session_state.pop("eg_selected_doc_id", None)
        st.session_state["eg_create_mode"] = True
        st.session_state["eg_preparing_create"] = False
    else:
        view = "list"
        st.session_state.pop("eg_selected_doc_id", None)
        st.session_state["eg_create_mode"] = False
        st.session_state["eg_preparing_create"] = False

    route = {
        "page": EXGRATIA_DEEP_LINK_PAGE,
        "eg_view": view,
        "eg_doc": doc_id,
    }
    st.session_state["active_page"] = EXGRATIA_DEEP_LINK_PAGE
    st.session_state["force_home_once"] = False
    _restore_exgratia_query_params(route)
    return True


def _apply_pending_open_rp_after_login(menu_items) -> bool:

    doc_id = _sanitize_rp_doc_id(st.session_state.get("pending_open_rp_doc_id", ""))
    if not doc_id:
        return False

    if "Risk Profile" not in list(menu_items or []):
        st.session_state.pop("pending_open_rp_doc_id", None)
        st.session_state["post_login_notice"] = "Akses Risk Profile tidak tersedia untuk user ini."
        return False


    st.session_state["pending_saved_report_id"] = doc_id
    st.session_state["pending_saved_report_title"] = doc_id
    st.session_state["active_page"] = "Risk Profile"
    st.session_state["force_home_once"] = False
    st.session_state.pop("pending_open_rp_doc_id", None)

    try:
        st.query_params.clear()
    except Exception:
        pass

    return True


def _load_eg_verify_record(doc_id: str) -> dict | None:
    target = _sanitize_eg_doc_id(doc_id)
    if not target:
        return None
    try:
        sheet = _get_spreadsheet().worksheet(EG_VERIFY_SHEET)
        values = sheet.get_all_values()
    except Exception:
        return None
    if not values or len(values) <= 1:
        return None
    header = [str(h or "").strip() for h in values[0]]
    try:
        doc_idx = header.index("DOC_ID")
    except ValueError:
        return None
    for row in values[1:]:
        if doc_idx < len(row) and _sanitize_eg_doc_id(row[doc_idx]) == target:
            rec = {h: (row[i] if i < len(row) else "") for i, h in enumerate(header)}
            return rec
    return None


def _eg_verify_status_badge(status: str) -> str:
    low = str(status or "").lower()
    if "cancel" in low or "batal" in low:
        label, cls = "Canceled", "default"
    elif "decline" in low or "rejected" in low:
        label, cls = "Declined", "default"
    elif "approved" in low:
        label, cls = "Verified Approved", "ok"
    elif "dirtek" in low or "direktur teknik" in low:
        label, cls = "Pending Direktur Teknik", "bod"
    elif "dirmkt" in low or "direktur marketing" in low:
        label, cls = "Pending Direktur Marketing", "bod"
    elif "marketing manager" in low:
        label, cls = "Pending Marketing Manager", "claim"
    elif "bod" in low:
        label, cls = "Pending BOD", "bod"
    elif "reinsurance" in low:
        label, cls = "Pending Reinsurance", "reinsurance"
    elif "klaim" in low or "claim" in low:
        label, cls = "Pending Claim", "claim"
    else:
        label, cls = status or "Workflow Record", "default"
    return f"<span class='egv-badge egv-badge-{cls}'>{html.escape(label)}</span>"


def _eg_verify_field(label: str, value: str) -> str:
    value = str(value or "-").strip() or "-"
    return f"<div class='egv-field'><div class='egv-label'>{html.escape(label)}</div><div class='egv-value'>{html.escape(value)}</div></div>"


def _eg_verify_signer(role: str, by: str, at: str) -> str:
    by = str(by or "").strip()
    at = str(at or "").strip()
    if by:
        body = f"<b>{html.escape(by)}</b><br><span>{html.escape(at or '-')}</span>"
        cls = "done"
    else:
        body = "<span>Belum confirm</span>"
        cls = "pending"
    return f"<div class='egv-signer {cls}'><div class='egv-signer-role'>{html.escape(role)}</div><div class='egv-signer-body'>{body}</div></div>"


def render_exgratia_verification_page(doc_id: str, supplied_code: str = "") -> None:
    rec = _load_eg_verify_record(doc_id)
    supplied_code = str(supplied_code or "").strip().upper()
    st.markdown(
        """
        <style>
          .egv-shell{max-width:1040px;margin:28px auto 0 auto;}
          .egv-hero{position:relative;overflow:hidden;border-radius:28px;padding:28px 30px;background:linear-gradient(135deg,#002B57 0%,#003366 55%,#1F5A91 100%);color:white;box-shadow:0 22px 54px rgba(0,51,102,.24);border:1px solid rgba(255,255,255,.16);}
          .egv-kicker{display:inline-flex;padding:7px 11px;border-radius:999px;background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.18);font-size:12px;font-weight:850;margin-bottom:12px;}
          .egv-title{font-size:34px;font-weight:950;letter-spacing:-.045em;line-height:1.05;margin:0;}
          .egv-sub{margin-top:8px;color:rgba(255,255,255,.82);font-size:13.5px;line-height:1.5;max-width:720px;}
          .egv-card{margin-top:16px;border-radius:24px;background:#FFFFFF;border:1px solid rgba(0,51,102,.12);box-shadow:0 18px 42px rgba(15,23,42,.075);overflow:hidden;}
          .egv-card-top{height:5px;background:linear-gradient(90deg,#003366 0%,#1F5A91 52%,#66AAD1 100%);}
          .egv-card-body{padding:20px 22px;}
          .egv-row{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:14px;}
          .egv-doc{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;font-size:18px;font-weight:950;color:#0F2742;}
          .egv-badge{display:inline-flex;padding:8px 12px;border-radius:999px;font-size:12px;font-weight:950;white-space:nowrap;}
          .egv-badge-ok{background:#E8F7EF;color:#166534;border:1px solid rgba(22,101,52,.18);}
          .egv-badge-bod{background:#F3E8FF;color:#6B21A8;border:1px solid rgba(107,33,168,.16);}
          .egv-badge-reinsurance{background:#EAF1FB;color:#1F5A91;border:1px solid rgba(31,90,145,.18);}
          .egv-badge-claim{background:#FFF3D6;color:#7C4A03;border:1px solid rgba(124,74,3,.18);}
          .egv-badge-default{background:#EEF2F7;color:#475569;border:1px solid rgba(71,85,105,.16);}
          .egv-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:12px;}
          .egv-field{border-radius:16px;background:#F8FAFC;border:1px solid rgba(0,51,102,.08);padding:12px 13px;min-height:70px;}
          .egv-label{font-size:10.5px;font-weight:900;letter-spacing:.065em;text-transform:uppercase;color:#64748B;margin-bottom:5px;}
          .egv-value{font-size:13px;font-weight:800;color:#0F2742;line-height:1.28;overflow-wrap:anywhere;}
          .egv-section-title{margin:18px 0 9px 0;color:#003366;font-size:16px;font-weight:950;letter-spacing:-.02em;}
          .egv-signer-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;}
          .egv-signer{border-radius:16px;padding:12px 13px;border:1px solid rgba(0,51,102,.10);background:#FFFFFF;box-shadow:0 8px 18px rgba(15,23,42,.035);}
          .egv-signer.done{background:linear-gradient(180deg,#FFFFFF 0%,#F1FBF5 100%);border-color:rgba(22,101,52,.18);}
          .egv-signer.pending{background:#F8FAFC;}
          .egv-signer-role{font-size:11px;font-weight:950;color:#003366;text-transform:uppercase;letter-spacing:.045em;margin-bottom:6px;}
          .egv-signer-body{font-size:12.5px;color:#334155;line-height:1.4;}
          .egv-signer-body span{color:#64748B;font-weight:650;}
          .egv-alert{margin-top:14px;border-radius:16px;padding:13px 14px;font-size:13px;line-height:1.45;border:1px solid rgba(0,51,102,.12);}
          .egv-alert.ok{background:#E8F7EF;color:#166534;border-color:rgba(22,101,52,.18);}
          .egv-alert.warn{background:#FFF3D6;color:#7C4A03;border-color:rgba(124,74,3,.18);}
          .egv-alert.err{background:#FFE7E7;color:#9F1239;border-color:rgba(159,18,57,.18);}
          @media(max-width:820px){.egv-grid,.egv-signer-grid{grid-template-columns:1fr}.egv-title{font-size:28px}.egv-shell{margin-top:14px}}
        </style>
        <div class='egv-shell'>
          <div class='egv-hero'>
            <div class='egv-kicker'>Ex-Gratia Verification</div>
            <h1 class='egv-title'>Document Verification</h1>
            <div class='egv-sub'>Validasi dokumen Ex-Gratia berdasarkan record workflow di SuperApp Actuary.</div>
          </div>
        """,
        unsafe_allow_html=True,
    )
    if rec is None:
        st.markdown(
            f"<div class='egv-card'><div class='egv-card-top'></div><div class='egv-card-body'><div class='egv-alert err'><b>Document not found.</b><br>Document ID <b>{html.escape(_sanitize_eg_doc_id(doc_id))}</b> tidak ditemukan di workflow Ex-Gratia.</div></div></div></div>",
            unsafe_allow_html=True,
        )
        return

    current_hash = compute_eg_verification_hash(rec)
    stored_hash = str(rec.get("VERIFICATION_HASH", "") or "").strip().upper()
    code_match = supplied_code and supplied_code == current_hash
    record_changed = supplied_code and supplied_code != current_hash
    hash_text = current_hash

    basic_html = "".join([
        _eg_verify_field("No. Klaim", rec.get("CLAIM_NO", "")),
        _eg_verify_field("No. Polis", rec.get("POLICY_NO", "")),
        _eg_verify_field("COB", rec.get("COB", "")),
        _eg_verify_field("Tertanggung", rec.get("INSURED_NAME", "")),
        _eg_verify_field("Sumber Bisnis", rec.get("SOURCE_BUSINESS", "")),
        _eg_verify_field("Nilai Ex-Gratia", rec.get("EXGRATIA_AMOUNT", "")),
    ])
    signer_items = [
        _eg_verify_signer("Marketing", rec.get("CREATED_BY", ""), rec.get("CREATED_AT", "")),
        _eg_verify_signer("Marketing Manager", rec.get("MARKETING_MANAGER_CONFIRMED_BY", ""), rec.get("MARKETING_MANAGER_CONFIRMED_AT", "")),
        _eg_verify_signer("Klaim", rec.get("CLAIM_CONFIRMED_BY", ""), rec.get("CLAIM_CONFIRMED_AT", "")),
    ]
    if str(rec.get("NEEDS_REINSURANCE", "")).strip().upper() == "TRUE":
        signer_items.append(_eg_verify_signer("Reasuransi", rec.get("REINSURANCE_CONFIRMED_BY", ""), rec.get("REINSURANCE_CONFIRMED_AT", "")))
    signer_items.extend([
        _eg_verify_signer("Direktur Marketing", rec.get("DIR_MARKETING_CONFIRMED_BY", ""), rec.get("DIR_MARKETING_CONFIRMED_AT", "")),
        _eg_verify_signer("Direktur Teknik", rec.get("DIR_TEKNIK_CONFIRMED_BY", ""), rec.get("DIR_TEKNIK_CONFIRMED_AT", "")),
    ])
    signer_html = "".join(signer_items)
    if code_match:
        alert = "<div class='egv-alert ok'><b>Verification code matched.</b><br>QR/code cocok dengan record workflow saat ini.</div>"
    elif record_changed:
        alert = f"<div class='egv-alert warn'><b>Record found, but code differs from current record.</b><br>Kemungkinan PDF dibuat sebelum ada update approval terbaru. Current code: <b>{html.escape(current_hash)}</b></div>"
    else:
        alert = "<div class='egv-alert warn'><b>Record found.</b><br>Tidak ada verification code pada URL, sehingga halaman ini hanya menampilkan record workflow.</div>"

    stored_note = f"<br>Stored initial code: <b>{html.escape(stored_hash)}</b>" if stored_hash else ""
    st.markdown(
        f"""
        <div class='egv-card'>
          <div class='egv-card-top'></div>
          <div class='egv-card-body'>
            <div class='egv-row'>
              <div>
                <div class='egv-label'>Document ID</div>
                <div class='egv-doc'>{html.escape(_sanitize_eg_doc_id(rec.get('DOC_ID','')))}</div>
              </div>
              <div>{_eg_verify_status_badge(rec.get('STATUS',''))}</div>
            </div>
            {alert}
            <div class='egv-grid'>{basic_html}</div>
            <div class='egv-section-title'>Digital Confirmation</div>
            <div class='egv-signer-grid'>{signer_html}</div>
            <div class='egv-section-title'>Verification Code</div>
            <div class='egv-alert ok'>Current verification code: <b>{html.escape(hash_text)}</b>{stored_note}</div>
          </div>
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )




TOP_NAVIGATION_PATCH = "smaller-desktop-nav-clean-hamburger-v6"
EXGRATIA_DEEP_LINK_PATCH = "current-app33-preserve-route-v2"

SUPERAPP_PAGE_MODULES = (
    'apolo_reportgeneratorapp',
    'risk_profileapp',
    'superproduction',
    'superaskred',
    'fr_retention',
    'spasialfr',
    'mv_analysis',
    'ea_analysis',
    'calculator_cor',
    'pa_premiumapp',
    'claim',
    'profitandloss',
    'renewal',
    'superprojection',
    'ex_gratia',
    'claim_polis',
    'ifrs17',
    'superai',
)


def _preload_superapp(menu_items):

    if st.session_state.get("eager_startup_completed"):
        return

    for module_name in SUPERAPP_PAGE_MODULES:
        import_module(module_name)

    if "Risk Profile" in menu_items:
        from risk_profileapp import preload_risk_profile_sources

        preload_risk_profile_sources()

    preload_pages = (
        ("claim_polis", {"Treaty"}),
        ("claim", {"Claim Analysis"}),
        ("calculator_cor", {"Beta Page", "CoR Calculator"}),
        ("ea_analysis", {"Super Engineering"}),
        ("fr_retention", {"Super FR"}),
        ("ex_gratia", {"ex-Gratia"}),
    )
    allowed_pages = set(menu_items)
    for module_name, pages in preload_pages:
        if allowed_pages.intersection(pages):
            import_module(module_name).preload_workbooks()

    st.session_state["eager_startup_completed"] = True


def main():
    _capture_open_rp_query_param()
    _capture_exgratia_query_params()

    try:
        verify_doc_id = st.query_params.get("verify_eg", "")
        verify_code = st.query_params.get("code", "")
        if isinstance(verify_doc_id, list):
            verify_doc_id = verify_doc_id[0] if verify_doc_id else ""
        if isinstance(verify_code, list):
            verify_code = verify_code[0] if verify_code else ""
        if str(verify_doc_id or "").strip():
            render_exgratia_verification_page(str(verify_doc_id), str(verify_code or ""))
            return
    except Exception:
        pass

    _check_idle_timeout(IDLE_RESET_MINUTES)

    username = enforce_auth()
    if not username:
        login()
        return








    auth_data = st.session_state.get("auth", {})
    is_incognito = isinstance(auth_data, dict) and auth_data.get("mode") == "incognito"

    if is_incognito:
        menu_items = get_incognito_pages()
        current_user_role = "incognito"
    else:
        u_hash = st.session_state.get("u_hash")
        menu_items = USER_ROLES.get(u_hash, ["Home"])
        current_user_role = get_current_user_role(username)


    st.session_state["user_role"] = current_user_role


    menu_items = [p for p in list(menu_items) if p != "Super Chat"]

    _preload_superapp(menu_items)

    opened_rp_from_pdf = _apply_pending_open_rp_after_login(menu_items)
    opened_exgratia_from_link = _apply_pending_exgratia_after_login(menu_items)

    st.sidebar.markdown(f"<div class='sidebar-title'>Welcome,<br>{username}</div>", unsafe_allow_html=True)
    st.sidebar.caption("Main navigation is available at the top.")
    post_login_notice = st.session_state.pop("post_login_notice", "")
    if post_login_notice:
        st.warning(post_login_notice)




    query_page = _get_query_param_first("page", "").strip()


    brand_home_requested = _get_query_param_first("nav_home", "").strip() == "1"
    if brand_home_requested and "Home" in menu_items:
        if st.session_state.get("active_page") != "Home":
            _request_page_transition("Home")
        st.session_state["active_page"] = "Home"
        st.session_state["force_home_once"] = False
        query_page = ""
        try:
            st.query_params.clear()
        except Exception:
            pass




    default_page = "Home" if "Home" in menu_items else menu_items[0]

    if (
        st.session_state.pop("force_home_once", False)
        and not opened_rp_from_pdf
        and not opened_exgratia_from_link
    ):
        st.session_state["active_page"] = default_page
        try:
            st.query_params.clear()
        except Exception:
            pass
    elif query_page in menu_items and query_page != default_page:
        if st.session_state.get("active_page") != query_page:
            _request_page_transition(query_page)
            st.session_state["active_page"] = query_page
    else:
        if query_page and query_page != default_page:
            try:
                st.query_params.clear()
            except Exception:
                pass
        if "active_page" not in st.session_state or st.session_state.get("active_page") not in menu_items:
            st.session_state["active_page"] = default_page






    def _activate_page_tab(page_name: str) -> None:
        if page_name in menu_items:
            _request_page_transition(page_name)
            st.session_state["active_page"] = page_name













    def _open_top_page(target_page: str) -> None:
        _activate_page_tab(target_page)
        try:
            st.query_params.clear()
        except Exception:
            pass

    active_page = st.session_state.get("active_page", default_page)

    top_nav_groups = {
        "General Report": [
            "Risk Profile",
            "Super Production",
            "Super Renewal",
            "Profit and Loss",
        ],
        "Portfolio Analysis": [
            "Super Askred",
            "Super FR",
            "Spasial FR",
            "Super MV",
            "Super Engineering",
        ],
        "Claim": [
            "Claim Analysis",
            "ex-Gratia",
        ],
        "Pricing & Reserving": [
            "PA Premium Calculation",
            "CoR Calculator",
            "IFRS 17",
        ],
        "Reinsurance": [
            "Treaty",
        ],
        "Reporting": [
            "Apolo Report",
        ],
        "Other": [
            "Super Projection",
            "Beta Page",
        ],
    }

    visible_top_groups = {}
    assigned_pages = {"Home"}
    for group_name, group_pages in top_nav_groups.items():
        visible_pages = [p for p in group_pages if p in menu_items]
        if visible_pages:
            visible_top_groups[group_name] = visible_pages
            assigned_pages.update(visible_pages)

    remaining_pages = [
        p for p in menu_items
        if p not in assigned_pages and p != "Super Chat"
    ]
    if remaining_pages:
        visible_top_groups["More"] = remaining_pages

    brand_mark_html = "<div class='responsive-brand-fallback'>SA</div>"
    try:
        logo_path = Path("logo superapp.png")
        if logo_path.exists():
            logo_b64 = base64.b64encode(logo_path.read_bytes()).decode("ascii")
            brand_mark_html = (
                "<img class='responsive-brand-logo' "
                f"src='data:image/png;base64,{logo_b64}' alt='SuperApp logo'>"
            )
    except Exception:
        pass

    current_meta = PAGE_META.get(active_page, {})
    current_page_title = str(current_meta.get("title") or active_page)

    st.markdown(
        """
        <style>
          /*
           * Stay inside the main content width. The previous negative margins
           * made the navigation extend underneath an opened sidebar.
           */
          div[class*="st-key-responsive_enterprise_nav"] {
            position: sticky !important;
            top: calc(var(--header-height, 3.75rem) + 0.25rem) !important;
            z-index: 1000 !important;
            width: 100% !important;
            box-sizing: border-box !important;
            margin: 0 0 18px 0 !important;
            padding: 9px 11px !important;
            border-radius: 15px;
            background: rgba(255,255,255,0.992);
            border: 1px solid rgba(20,62,99,0.11);
            box-shadow: 0 10px 26px rgba(15,23,42,0.08);
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);

            /* The width of this exact main-canvas container controls the mode. */
            container-type: inline-size;
            container-name: superapp-navigation;
          }

          div[class*="st-key-responsive_enterprise_nav"] div[data-testid="stHorizontalBlock"] {
            align-items: center !important;
            gap: 4px !important;
          }

          div[class*="st-key-responsive_enterprise_nav"] div[data-testid="column"] {
            min-width: 0 !important;
          }

          div[class*="st-key-desktop_nav_variant"] {
            display: block;
          }

          div[class*="st-key-compact_nav_variant"] {
            display: none;
          }

          /*
           * Collapse only when the available main-canvas width is insufficient.
           * Opening the sidebar reduces this container width and therefore
           * automatically activates the Modules version.
           */
          @container superapp-navigation (max-width: 1040px) {
            div[class*="st-key-desktop_nav_variant"] {
              display: none !important;
            }

            div[class*="st-key-compact_nav_variant"] {
              display: block !important;
            }
          }

          /* Conservative fallback for browsers without container queries. */
          @media (max-width: 900px) {
            div[class*="st-key-desktop_nav_variant"] {
              display: none !important;
            }

            div[class*="st-key-compact_nav_variant"] {
              display: block !important;
            }
          }

          .responsive-brand-home-link {
            display: block;
            text-decoration: none !important;
            border-radius: 12px;
            padding: 2px 4px;
            cursor: pointer;
            transition: background .16s ease, transform .16s ease;
          }

          .responsive-brand-home-link:hover {
            background: #EEF5FB;
            transform: translateY(-1px);
          }

          .responsive-brand-home-link:hover .responsive-brand-title {
            color: #0B63CE;
          }

          .responsive-brand {
            display: flex;
            align-items: center;
            gap: 9px;
            min-width: 0;
          }

          .responsive-brand-logo,
          .responsive-brand-fallback {
            width: 34px;
            height: 34px;
            flex: 0 0 34px;
            border-radius: 11px;
          }

          .responsive-brand-logo {
            object-fit: contain;
            background: #FFFFFF;
          }

          .responsive-brand-fallback {
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg,#143E63 0%,#2E6495 100%);
            color: #FFFFFF;
            font-size: 11px;
            font-weight: 900;
          }

          .responsive-brand-title {
            color: #143E63;
            font-size: 14px;
            font-weight: 900;
            line-height: 1.04;
            letter-spacing: -0.025em;
            white-space: nowrap;
          }

          .responsive-brand-subtitle {
            margin-top: 3px;
            color: #64748B;
            font-size: 8.2px;
            font-weight: 820;
            line-height: 1;
            letter-spacing: 0.045em;
            text-transform: uppercase;
            white-space: nowrap;
          }

          /*
           * Use a small but still readable navigation font on the desktop row.
           * Buttons and active states have identical dimensions, so selecting
           * Home no longer shifts the row vertically or horizontally.
           */
          div[class*="st-key-desktop_nav_variant"] button,
          div[class*="st-key-compact_nav_variant"] button {
            min-height: 36px !important;
            height: 36px !important;
            padding: 0 5px !important;
            border-radius: 9px !important;
            border: 1px solid transparent !important;
            background: transparent !important;
            color: #143E63 !important;
            -webkit-text-fill-color: #143E63 !important;
            box-shadow: none !important;
            font-size: 8.2px !important;
            font-weight: 860 !important;
            line-height: 1 !important;
            letter-spacing: 0 !important;
            white-space: nowrap !important;
            text-transform: uppercase !important;
            overflow: hidden !important;
          }

          div[class*="st-key-desktop_nav_variant"] button p,
          div[class*="st-key-compact_nav_variant"] button p {
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: clip !important;
          }

          div[class*="st-key-desktop_nav_variant"] button:hover,
          div[class*="st-key-compact_nav_variant"] button:hover {
            background: #EEF5FB !important;
            border-color: rgba(20,62,99,0.12) !important;
            color: #143E63 !important;
            transform: none !important;
            box-shadow: none !important;
          }

          /* Same native button is used for Home in active and inactive states. */
          div[class*="st-key-desktop_home_active"] button,
          div[class*="st-key-compact_home_active"] button,
          div[class*="st-key-desktop_group_active__"] button {
            background: #143E63 !important;
            border-color: #143E63 !important;
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
            box-shadow: 0 6px 15px rgba(20,62,99,0.17) !important;
          }

          div[class*="st-key-desktop_home_active"] button p,
          div[class*="st-key-compact_home_active"] button p,
          div[class*="st-key-desktop_group_active__"] button p {
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
          }

          .responsive-current-page {
            min-height: 36px;
            box-sizing: border-box;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            color: #475569;
            font-size: 10.5px;
            font-weight: 760;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }

          /* Popover / mega-menu list. */
          div[data-testid="stPopoverBody"] {
            min-width: 270px !important;
            max-height: min(72vh, 680px) !important;
            overflow-y: auto !important;
            border-radius: 15px !important;
            border: 1px solid rgba(20,62,99,0.12) !important;
            box-shadow: 0 18px 45px rgba(15,23,42,0.15) !important;
            padding: 8px !important;
          }

          .responsive-menu-heading {
            padding: 8px 8px 5px 8px;
            color: #94A3B8;
            font-size: 10px;
            font-weight: 900;
            letter-spacing: 0.075em;
            text-transform: uppercase;
            text-align: left;
          }

          .responsive-menu-active {
            display: flex;
            justify-content: flex-start;
            align-items: center;
            min-height: 36px;
            box-sizing: border-box;
            padding: 8px 10px;
            margin: 1px 0;
            border-radius: 9px;
            background: #143E63;
            color: #FFFFFF;
            font-size: 12px;
            font-weight: 820;
            text-align: left;
          }

          div[class*="st-key-responsive_nav_item__"] button {
            width: 100% !important;
            min-height: 36px !important;
            height: auto !important;
            display: flex !important;
            justify-content: flex-start !important;
            align-items: center !important;
            padding: 8px 10px !important;
            border-radius: 9px !important;
            border: 1px solid transparent !important;
            background: #FFFFFF !important;
            color: #334155 !important;
            -webkit-text-fill-color: #334155 !important;
            box-shadow: none !important;
            font-size: 12px !important;
            font-weight: 720 !important;
            text-align: left !important;
            text-transform: none !important;
          }

          div[class*="st-key-responsive_nav_item__"] button > div,
          div[class*="st-key-responsive_nav_item__"] button p {
            width: 100% !important;
            justify-content: flex-start !important;
            text-align: left !important;
            overflow: visible !important;
          }

          div[class*="st-key-responsive_nav_item__"] button:hover {
            background: #EEF5FB !important;
            border-color: rgba(20,62,99,0.10) !important;
          }

          /*
           * Replace both the collapsed and expanded Streamlit sidebar controls
           * with one hamburger icon. Hide every native icon/text child first,
           * preventing the old chevrons and the hamburger from appearing
           * together.
           */
          [data-testid="stSidebarCollapsedControl"] button > *,
          [data-testid="stSidebarCollapseButton"] button > *,
          button[data-testid="stSidebarCollapsedControl"] > *,
          button[data-testid="stSidebarCollapseButton"] > *,
          button[aria-label*="sidebar" i] > *,
          button[title*="sidebar" i] > * {
            display: none !important;
          }

          [data-testid="stSidebarCollapsedControl"] svg,
          [data-testid="stSidebarCollapsedControl"] span,
          [data-testid="stSidebarCollapseButton"] svg,
          [data-testid="stSidebarCollapseButton"] span,
          button[data-testid="stSidebarCollapsedControl"] svg,
          button[data-testid="stSidebarCollapsedControl"] span,
          button[data-testid="stSidebarCollapseButton"] svg,
          button[data-testid="stSidebarCollapseButton"] span {
            display: none !important;
          }

          [data-testid="stSidebarCollapsedControl"] button,
          [data-testid="stSidebarCollapseButton"] button,
          button[data-testid="stSidebarCollapsedControl"],
          button[data-testid="stSidebarCollapseButton"],
          button[aria-label*="sidebar" i],
          button[title*="sidebar" i] {
            font-size: 0 !important;
            color: #143E63 !important;
            -webkit-text-fill-color: #143E63 !important;
          }

          [data-testid="stSidebarCollapsedControl"] button::before,
          [data-testid="stSidebarCollapseButton"] button::before,
          button[data-testid="stSidebarCollapsedControl"]::before,
          button[data-testid="stSidebarCollapseButton"]::before,
          button[aria-label*="sidebar" i]::before,
          button[title*="sidebar" i]::before {
            content: "" !important;
            display: block !important;
            width: 20px !important;
            height: 15px !important;
            flex: 0 0 20px !important;
            background:
              linear-gradient(
                to bottom,
                currentColor 0 2px,
                transparent 2px 6px,
                currentColor 6px 9px,
                transparent 9px 13px,
                currentColor 13px 15px
              ) !important;
            border-radius: 1px !important;
          }

          @media (max-width: 720px) {
            .responsive-brand-subtitle,
            .responsive-current-page {
              display: none;
            }

            .responsive-brand-title {
              font-size: 12.5px;
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="responsive_enterprise_nav"):

        with st.container(key="desktop_nav_variant"):
            desktop_widths = [1.60]
            for group_name in visible_top_groups:
                desktop_widths.append(
                    max(0.48, min(0.94, 0.26 + len(group_name) * 0.037))
                )

            desktop_cols = st.columns(
                desktop_widths,
                gap="small",
                vertical_alignment="center",
            )

            with desktop_cols[0]:
                st.markdown(
                    f"""
                    <a class="responsive-brand-home-link" href="?nav_home=1" aria-label="Go to Home">
                      <div class="responsive-brand">
                        {brand_mark_html}
                        <div>
                          <div class="responsive-brand-title">SuperApp Actuary</div>
                          <div class="responsive-brand-subtitle">MNC Insurance</div>
                        </div>
                      </div>
                    </a>
                    """,
                    unsafe_allow_html=True,
                )

            for idx, (group_name, group_pages) in enumerate(
                visible_top_groups.items(),
                start=1,
            ):
                with desktop_cols[idx]:
                    group_hash = hashlib.sha1(
                        group_name.encode("utf-8")
                    ).hexdigest()[:10]
                    group_state = (
                        "active" if active_page in group_pages else "inactive"
                    )
                    with st.container(
                        key=f"desktop_group_{group_state}__{group_hash}"
                    ):
                        with st.popover(
                            group_name,
                            use_container_width=True,
                        ):
                            st.markdown(
                                f"<div class='responsive-menu-heading'>"
                                f"{html.escape(group_name)}</div>",
                                unsafe_allow_html=True,
                            )
                            for item in group_pages:
                                if item == active_page:
                                    st.markdown(
                                        f"<div class='responsive-menu-active'>"
                                        f"{html.escape(item)}</div>",
                                        unsafe_allow_html=True,
                                    )
                                else:
                                    item_key = hashlib.sha1(
                                        f"desktop|{group_name}|{item}".encode("utf-8")
                                    ).hexdigest()[:12]
                                    st.button(
                                        item,
                                        key=f"responsive_nav_item__desktop__{item_key}",
                                        width="stretch",
                                        on_click=_open_top_page,
                                        args=(item,),
                                    )


        with st.container(key="compact_nav_variant"):
            compact_cols = st.columns(
                [1.95, 0.78, 1.18],
                gap="small",
                vertical_alignment="center",
            )

            with compact_cols[0]:
                st.markdown(
                    f"""
                    <a class="responsive-brand-home-link" href="?nav_home=1" aria-label="Go to Home">
                      <div class="responsive-brand">
                        {brand_mark_html}
                        <div>
                          <div class="responsive-brand-title">SuperApp Actuary</div>
                          <div class="responsive-brand-subtitle">MNC Insurance</div>
                        </div>
                      </div>
                    </a>
                    """,
                    unsafe_allow_html=True,
                )

            with compact_cols[1]:
                with st.popover("Modules", use_container_width=True):
                    for group_name, group_pages in visible_top_groups.items():
                        st.markdown(
                            f"<div class='responsive-menu-heading'>"
                            f"{html.escape(group_name)}</div>",
                            unsafe_allow_html=True,
                        )
                        for item in group_pages:
                            if item == active_page:
                                st.markdown(
                                    f"<div class='responsive-menu-active'>"
                                    f"{html.escape(item)}</div>",
                                    unsafe_allow_html=True,
                                )
                            else:
                                item_key = hashlib.sha1(
                                    f"compact|{group_name}|{item}".encode("utf-8")
                                ).hexdigest()[:12]
                                st.button(
                                    item,
                                    key=f"responsive_nav_item__compact__{item_key}",
                                    width="stretch",
                                    on_click=_open_top_page,
                                    args=(item,),
                                )

            with compact_cols[2]:
                st.markdown(
                    f"<div class='responsive-current-page'>"
                    f"Current: {html.escape(current_page_title)}</div>",
                    unsafe_allow_html=True,
                )

    page = st.session_state.get("active_page", default_page)




    try:
        route_page = _get_query_param_first("page", "").strip()
        route_view = _get_query_param_first("eg_view", "").strip().lower()
        route_doc = _sanitize_eg_doc_id(
            _get_query_param_first("eg_doc", "")
        )
        preserve_exgratia_route = (
            page == EXGRATIA_DEEP_LINK_PAGE
            and route_page == EXGRATIA_DEEP_LINK_PAGE
            and bool(route_doc or route_view in EXGRATIA_DEEP_LINK_VIEWS)
        )

        if route_page and not preserve_exgratia_route:
            st.query_params.clear()
    except Exception:
        pass

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        try:
            st.query_params.clear()
        except Exception:
            pass
        st.rerun()

    page = st.session_state.get("active_page", default_page)




    pending_overlay_page = str(st.session_state.pop("pending_page_loading_overlay", "") or "")
    show_page_switch_overlay = bool(pending_overlay_page and pending_overlay_page == str(page))

    if page == "Home":
        home(username, menu_items)
    else:
        loading_overlay = _show_page_loading_overlay(page) if show_page_switch_overlay else None
        try:
            open_module_page(page, username, current_user_role)
        finally:
            if loading_overlay is not None:
                loading_overlay.empty()

    st.session_state["last_rendered_page"] = page

    render_global_footer()




if __name__ == "__main__":
    main()
