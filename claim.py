import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import plotly.express as px
import io
import base64
import json
import html
import hashlib
import gc
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle








def load_data(path: str) -> pd.DataFrame:
    return pd.read_excel(path)

def cached_claim_pivot(df: pd.DataFrame, group_cols: tuple[str, ...], top_by: str, top_n: int) -> pd.DataFrame:
    return build_claim_pivot(df, list(group_cols), top_by=top_by, top_n=top_n)

def cached_claim_chart_df(df: pd.DataFrame, group_col: str, top_by: str, top_n: int) -> pd.DataFrame:
    return build_claim_chart_df(df, group_col, top_by=top_by, top_n=top_n)

def cached_export_excel_bytes(export_df: pd.DataFrame, filter_lines: tuple[str, ...]) -> bytes:
    return export_excel(export_df, list(filter_lines))

def cached_export_pdf_bytes(export_df: pd.DataFrame, filter_lines: tuple[str, ...]) -> bytes:
    return export_pdf(export_df, list(filter_lines))




def format_id_int(x):
    if pd.isna(x):
        return ""
    try:
        x = int(round(float(x)))
        return f"{x:,}".replace(",", ".")
    except Exception:
        return str(x)


def _safe_to_number(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)
    return out


def _existing_cols(df: pd.DataFrame, cols: list[str]) -> list[str]:
    return [c for c in cols if c in df.columns]


def _sync_multiselect_state(key: str, options: list) -> list:
    valid = [v for v in st.session_state.get(key, []) if v in options]
    st.session_state[key] = valid
    return valid


def _compute_signature(payload: dict) -> str:
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha1(payload_json.encode("utf-8")).hexdigest()


def _make_data_uri(data_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(data_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _clear_export_state(prefix: str):
    for suffix in ("sig", "href", "name", "error"):
        st.session_state.pop(f"{prefix}__{suffix}", None)


def _render_direct_download_link(label: str, href: str, file_name: str):
    st.markdown(
        f'<a class="direct-download-btn is-ready" download="{html.escape(file_name, quote=True)}" href="{href}">{html.escape(label)}</a>',
        unsafe_allow_html=True,
    )


def render_section_card_header(title: str, subtitle: str = ""):
    subtitle_html = f'<div class="section-card-subtitle">{html.escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f'<div class="section-card-header"><div class="section-card-title">{html.escape(title)}</div>{subtitle_html}</div>',
        unsafe_allow_html=True,
    )


def render_risk_profile_tab_selector(options: list[str], state_key: str, aria_label: str = "Detailed view") -> str:





    options = list(options or [])
    if not options:
        return ""
    if state_key not in st.session_state or st.session_state[state_key] not in options:
        st.session_state[state_key] = options[0]

    st.markdown(f"""
    <style>
      div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="{aria_label}"]) {{
        width: 100% !important;
        max-width: 100% !important;
        margin-top: 2px !important;
        margin-bottom: 0 !important;
        overflow: hidden !important;
      }}
      div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="{aria_label}"]) > div {{
        width: 100% !important;
        max-width: 100% !important;
        overflow-x: auto !important;
        overflow-y: hidden !important;
        padding: 0 0 5px 0 !important;
        scrollbar-width: thin !important;
      }}
      div[role="radiogroup"][aria-label="{aria_label}"] {{
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
      }}
      div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="{aria_label}"]) > div::-webkit-scrollbar {{ height: 7px !important; }}
      div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="{aria_label}"]) > div::-webkit-scrollbar-thumb {{
        background: rgba(0,51,102,0.24) !important;
        border-radius: 999px !important;
      }}
      div[role="radiogroup"][aria-label="{aria_label}"] label {{
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
      }}
      div[role="radiogroup"][aria-label="{aria_label}"] label:hover {{
        background: #EEF6FF !important;
        color: #003366 !important;
        border-color: rgba(0,51,102,0.28) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 8px 18px rgba(0,51,102,0.09) !important;
      }}
      div[role="radiogroup"][aria-label="{aria_label}"] label:has(input:checked) {{
        background: linear-gradient(135deg, #003366 0%, #1F5A91 100%) !important;
        color: #FFFFFF !important;
        border-color: rgba(0,51,102,0.72) !important;
        box-shadow: 0 10px 22px rgba(0,51,102,0.20) !important;
      }}
      div[role="radiogroup"][aria-label="{aria_label}"] label:has(input:checked) *,
      div[role="radiogroup"][aria-label="{aria_label}"] label:has(input:checked) p,
      div[role="radiogroup"][aria-label="{aria_label}"] label:has(input:checked) span,
      div[role="radiogroup"][aria-label="{aria_label}"] label:has(input:checked) div {{
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
      }}
      div[role="radiogroup"][aria-label="{aria_label}"] label p,
      div[role="radiogroup"][aria-label="{aria_label}"] label span {{
        color: inherit !important;
        font-weight: inherit !important;
        white-space: nowrap !important;
      }}
      div[role="radiogroup"][aria-label="{aria_label}"] input,
      div[role="radiogroup"][aria-label="{aria_label}"] svg {{
        display: none !important;
      }}
    </style>
    """, unsafe_allow_html=True)

    return st.radio(
        aria_label,
        options=options,
        key=state_key,
        horizontal=True,
        label_visibility="collapsed",
    )


def shorten_label(x, n=25):
    x = str(x)
    return x if len(x) <= n else x[:n].rstrip() + "..."

def _render_html_block(html_content: str, height: int = 300, scrolling: bool = False) -> None:

    src = "data:text/html;base64," + base64.b64encode(html_content.encode("utf-8")).decode("ascii")
    components.iframe(src, height=height, scrolling=scrolling)




def compute_kpis(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {"GROSS": 0, "NET": 0, "REINSURANCE": 0, "NUMBER OF CLAIMS": 0, "AVG SEVERITY": 0}
    tmp = _safe_to_number(df, ["GROSS", "NET", "REINSURANCE", "NUMBER OF CLAIMS"])
    gross = tmp["GROSS"].sum() if "GROSS" in tmp.columns else 0.0
    net = tmp["NET"].sum() if "NET" in tmp.columns else 0.0
    ri = tmp["REINSURANCE"].sum() if "REINSURANCE" in tmp.columns else 0.0
    claims = tmp["NUMBER OF CLAIMS"].sum() if "NUMBER OF CLAIMS" in tmp.columns else 0.0
    avg = gross / claims if claims else 0.0
    net_pct = net / gross * 100 if gross else 0.0
    return {"GROSS": gross, "NET": net, "REINSURANCE": ri, "NUMBER OF CLAIMS": claims, "AVG SEVERITY": avg, "NET %": net_pct}


def render_kpi_cards(kpis: dict) -> None:








    st.markdown("""
<style>
  .claim-kpi-card-fixed{
    box-sizing:border-box!important;
    height:112px!important;
    min-height:112px!important;
    padding:14px 16px!important;
    border-radius:22px!important;
    display:flex!important;
    flex-direction:column!important;
    justify-content:flex-start!important;
    align-items:flex-start!important;
    gap:7px!important;
    overflow:hidden!important;
    background:linear-gradient(180deg,#FFFFFF 0%,#F8FAFC 100%)!important;
    border:1px solid rgba(0,51,102,0.11)!important;
    box-shadow:0 10px 26px rgba(15,23,42,0.055)!important;
  }
  .claim-kpi-card-fixed h4{
    margin:0!important;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Arial,sans-serif!important;
    font-size:12.5px!important;
    line-height:1.15!important;
    font-weight:720!important;
    color:#475569!important;
    white-space:nowrap!important;
    overflow:hidden!important;
    text-overflow:ellipsis!important;
    max-width:100%!important;
  }
  .claim-kpi-card-fixed h4 span{
    color:#64748B!important;
    font-weight:650!important;
  }
  .claim-kpi-card-fixed h2{
    margin:0!important;
    margin-top:1px!important;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Arial,sans-serif!important;
    font-size:clamp(22px,2.35vw,31px)!important;
    line-height:1.0!important;
    font-weight:850!important;
    color:#003366!important;
    letter-spacing:-0.02em!important;
    white-space:nowrap!important;
    overflow:hidden!important;
    text-overflow:ellipsis!important;
    max-width:100%!important;
    font-variant-numeric:tabular-nums!important;
  }
</style>
""", unsafe_allow_html=True)

    items = [
        ("Gross Claim", format_id_int(kpis.get("GROSS", 0) / 1_000_000), "Mio"),
        ("Net Claim", format_id_int(kpis.get("NET", 0) / 1_000_000), "Mio"),
        ("RI Recovery", format_id_int(kpis.get("REINSURANCE", 0) / 1_000_000), "Mio"),
        ("No. of Claims", format_id_int(kpis.get("NUMBER OF CLAIMS", 0)), ""),
        ("Avg Severity", format_id_int(kpis.get("AVG SEVERITY", 0) / 1_000_000), "Mio"),
        ("Net / Gross", f"{kpis.get('NET %', 0):.0f}%", ""),
    ]

    cols = st.columns(6, gap="small")
    for col, (title, value, unit) in zip(cols, items):
        safe_title = html.escape(str(title))
        safe_value = html.escape(str(value))
        unit_html = f" <span>{html.escape(str(unit))}</span>" if unit else ""
        card_html = f'<div class="claim-kpi-card-fixed"><h4>{safe_title}{unit_html}</h4><h2>{safe_value}</h2></div>'
        with col:
            st.markdown(card_html, unsafe_allow_html=True)





def build_claim_pivot(df: pd.DataFrame, group_cols: list[str], top_by: str = "GROSS", top_n=None) -> pd.DataFrame:
    amount_cols = _existing_cols(df, ["GROSS", "REINSURANCE", "NET"])
    freq_cols = _existing_cols(df, ["NUMBER OF CLAIMS"])
    pivot_cols = amount_cols + freq_cols
    group_cols = _existing_cols(df, group_cols)
    if not group_cols or not pivot_cols:
        return pd.DataFrame()

    tmp = df[group_cols + pivot_cols].copy()
    for col in group_cols:
        try:
            if pd.api.types.is_categorical_dtype(tmp[col]):
                if "(Blank)" not in tmp[col].cat.categories:
                    tmp[col] = tmp[col].cat.add_categories(["(Blank)"])
                tmp[col] = tmp[col].fillna("(Blank)")
            else:
                tmp[col] = tmp[col].where(tmp[col].notna(), "(Blank)")
        except Exception:
            tmp[col] = tmp[col].astype(object).where(tmp[col].notna(), "(Blank)")

    tmp = _safe_to_number(tmp, pivot_cols)
    pivot = tmp.groupby(group_cols, dropna=False, observed=True, as_index=False, sort=False)[pivot_cols].sum()
    for c in ["GROSS", "REINSURANCE", "NET"]:
        if c not in pivot.columns:
            pivot[c] = 0.0
    if "NUMBER OF CLAIMS" not in pivot.columns:
        pivot["NUMBER OF CLAIMS"] = 0.0

    pivot["AVG SEVERITY"] = (pivot["GROSS"] / pivot["NUMBER OF CLAIMS"].replace(0, pd.NA)).fillna(0.0)
    sort_col = top_by if top_by in pivot.columns else "GROSS"
    pivot = pivot.sort_values(sort_col, ascending=False, kind="stable").reset_index(drop=True)
    if top_n is not None:
        pivot = pivot.head(int(top_n)).reset_index(drop=True)
    return pivot


def build_claim_chart_df(df: pd.DataFrame, group_col: str, top_by: str = "GROSS", top_n: int = 10) -> pd.DataFrame:
    pivot = build_claim_pivot(df, [group_col], top_by=top_by, top_n=top_n)
    if pivot.empty or group_col not in pivot.columns:
        return pd.DataFrame()
    pivot["label"] = pivot[group_col].map(lambda x: shorten_label(x, 34))
    pivot["GROSS_JUTA"] = pivot["GROSS"] / 1_000_000
    pivot["NET_JUTA"] = pivot["NET"] / 1_000_000
    pivot["RI_JUTA"] = pivot["REINSURANCE"] / 1_000_000
    pivot["AVG_SEV_JUTA"] = pivot["AVG SEVERITY"] / 1_000_000
    pivot["NET_PCT"] = (pivot["NET"] / pivot["GROSS"].replace(0, pd.NA) * 100).fillna(0.0)
    pivot["RI_PCT"] = (pivot["REINSURANCE"] / pivot["GROSS"].replace(0, pd.NA) * 100).fillna(0.0)
    return pivot


def _safe_fragment_rerun() -> None:





    st.rerun()


def render_claim_table(pivot: pd.DataFrame, group_cols: list[str], table_key: str | None = None) -> None:

    if pivot is None or pivot.empty:
        st.info("No data available for selected filter(s).")
        return

    metric_order = ["GROSS", "REINSURANCE", "NET", "NUMBER OF CLAIMS", "AVG SEVERITY"]
    group_cols = [c for c in group_cols if c in pivot.columns]
    metric_cols = [c for c in metric_order if c in pivot.columns]
    final_cols = group_cols + metric_cols
    if not final_cols:
        st.info("No table columns available.")
        return

    if table_key is None:
        table_key = hashlib.sha1(("|".join(map(str, final_cols)) + str(len(pivot))).encode("utf-8")).hexdigest()[:10]
    table_key = str(table_key).replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_")

    page_key = f"claim_table_page__{table_key}"
    rows_per_page = 200
    total_rows = len(pivot)
    total_pages = max(1, int(np.ceil(total_rows / rows_per_page)))
    st.session_state.setdefault(page_key, 1)
    if int(st.session_state.get(page_key, 1) or 1) > total_pages:
        st.session_state[page_key] = total_pages
    if int(st.session_state.get(page_key, 1) or 1) < 1:
        st.session_state[page_key] = 1

    current_page = int(st.session_state.get(page_key, 1) or 1)
    start_idx = (current_page - 1) * rows_per_page
    end_idx = min(start_idx + rows_per_page, total_rows)
    page_df = pivot.iloc[start_idx:end_idx].copy()

    raw_df = page_df[final_cols].copy().replace([np.inf, -np.inf], np.nan)
    display_df = raw_df.copy()

    money_cols = [c for c in ["GROSS", "REINSURANCE", "NET", "AVG SEVERITY"] if c in display_df.columns]
    count_cols = [c for c in ["NUMBER OF CLAIMS"] if c in display_df.columns]

    for col in money_cols + count_cols:
        display_df[col] = pd.to_numeric(display_df[col], errors="coerce")


    display_money_df = display_df.copy()
    for col in money_cols:
        display_money_df[col] = pd.to_numeric(display_money_df[col], errors="coerce") / 1_000_000

    for col in display_df.columns:
        if col in money_cols:
            display_df[col] = display_money_df[col].apply(format_id_int)
        elif col in count_cols:
            display_df[col] = display_df[col].apply(format_id_int)
        else:
            display_df[col] = display_df[col].fillna("(Blank)").astype(str)

    table_dom_id = f"claim_table_{table_key}_{current_page}"

    col_alias = {
        "GROSS": "GROSS<br><span>IDR Mio</span>",
        "REINSURANCE": "REINSURANCE<br><span>IDR Mio</span>",
        "NET": "NET<br><span>IDR Mio</span>",
        "NUMBER OF CLAIMS": "NO. OF CLAIMS",
        "AVG SEVERITY": "AVG SEVERITY<br><span>IDR Mio</span>",
    }

    def width_for(col: str) -> int:
        if col in group_cols:
            if col in ["UW_YEAR", "UW YEAR", "STATUS", "COB_CODE", "LOB_NAME", "TOB_NAME"]:
                return 130
            if col in ["POLICY_NO", "CLAIM NO", "INSURED_NAME", "INTERMEDIARY_NAME", "INTERNAL_REASON", "WORKSHOP_NAME"]:
                return 240
            return 190
        if col == "NUMBER OF CLAIMS":
            return 135
        if col == "AVG SEVERITY":
            return 150
        if col in money_cols:
            return 150
        return 140

    col_widths = {col: width_for(str(col)) for col in display_df.columns}
    min_table_width = sum(col_widths.values())
    table_height = max(260, min(520, 96 + 34 * len(display_df)))
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
            raw_val = raw_df.iloc[r][col]
            sort_val_num = pd.to_numeric(pd.Series([raw_val]), errors="coerce").iloc[0]
            classes = ["text-cell" if col in group_cols else "num-cell"]
            style = ""
            if col in sticky_left:
                classes.append("sticky-col")
                style = f"left:{sticky_left[col]}px;"
            if col == "NET" and pd.notna(sort_val_num) and float(sort_val_num) > 0:
                classes.append("net-emphasis")
            val = html.escape(str(display_df.iloc[r][col]))
            if pd.notna(sort_val_num):
                sort_attr = str(float(sort_val_num))
                sort_type = "num"
            else:
                sort_attr = html.escape(str(raw_val if pd.notna(raw_val) else "").lower())
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
      .rp-table-controls label {{ font-size: 11.5px; font-weight: 650; color: #475569; }}
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
      .rp-table-controls select:focus {{ border-color: rgba(0,51,102,0.45); box-shadow: 0 0 0 3px rgba(0,51,102,0.08); }}
      .rp-table-controls button {{ cursor: pointer; font-weight: 650; color: #003366; }}
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
      .rp-table thead th span {{ display:block; margin-top:2px; font-size:8.8px; line-height:1.0; font-weight:500; opacity:0.78; }}
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
      .rp-table tbody tr:nth-child(even) td {{ background: #F8FAFC; }}
      .rp-table tbody tr:hover td {{ background: #EEF6FF; }}
      .rp-table .text-cell {{ text-align:left; font-weight:650; color:#1E3A5F; }}
      .rp-table .num-cell {{ text-align:right; font-variant-numeric:tabular-nums; font-weight:620; color:#334155; }}
      .rp-table .sticky-col {{ position:sticky; z-index:20; box-shadow:2px 0 0 rgba(0, 51, 102, 0.08); }}
      .rp-table thead th.sticky-col {{ z-index:40; background:#002B57; }}
      .rp-table tbody td.sticky-col {{ background:#ffffff; }}
      .rp-table tbody tr:nth-child(even) td.sticky-col {{ background:#F8FAFC; }}
      .rp-table tbody tr:hover td.sticky-col {{ background:#EEF6FF; }}
      .rp-table tbody td.net-emphasis {{ color:#003366; font-weight:760; }}
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
        const table = document.getElementById("{table_dom_id}");
        const sortBy = document.getElementById("sort_by_{table_dom_id}");
        const sortOrder = document.getElementById("sort_order_{table_dom_id}");
        const resetBtn = document.getElementById("reset_sort_{table_dom_id}");
        if (!table || !sortBy || !sortOrder || !resetBtn) return;
        const tbody = table.querySelector("tbody");
        const originalRows = Array.from(tbody.querySelectorAll("tr"));
        function applySort() {{
          const colIndex = sortBy.value;
          if (colIndex === "") {{ tbody.replaceChildren(...originalRows); return; }}
          const idx = parseInt(colIndex, 10);
          const asc = sortOrder.value === "asc";
          const rows = Array.from(tbody.querySelectorAll("tr"));
          rows.sort(function(a, b) {{
            const acell = a.children[idx]; const bcell = b.children[idx];
            const atype = acell.getAttribute("data-sort-type"); const btype = bcell.getAttribute("data-sort-type");
            let av = acell.getAttribute("data-sort") || ""; let bv = bcell.getAttribute("data-sort") || ""; let result = 0;
            if (atype === "num" && btype === "num") {{ result = (parseFloat(av) || 0) - (parseFloat(bv) || 0); }}
            else {{ result = av.localeCompare(bv, undefined, {{numeric:true, sensitivity:"base"}}); }}
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
    _render_html_block(html_table, height=table_height + 44, scrolling=False)

    st.markdown("""
    <style>
      .claim-pagination-caption {
        font-size: 10.5px;
        color: #64748B;
        font-weight: 650;
        padding-top: 7px;
        line-height: 1.1;
        white-space: nowrap;
      }
      div[class*="st-key-claim_pagination_nav__"] button[kind="secondary"],
      div[class*="st-key-claim_pagination_nav__"] button {
        min-height: 28px !important;
        height: 28px !important;
        padding: 0 10px !important;
        font-size: 13px !important;
        line-height: 1 !important;
        border-radius: 9px !important;
        border: 1px solid rgba(0,51,102,0.22) !important;
        color: #003366 !important;
        background: #FFFFFF !important;
      }
      div[class*="st-key-claim_pagination_nav__"] div[data-testid="stNumberInput"] input {
        min-height: 28px !important;
        height: 28px !important;
        font-size: 11px !important;
        padding: 1px 6px !important;
        border-radius: 9px !important;
      }
      div[class*="st-key-claim_pagination_nav__"] {
        margin-top: -12px !important;
        padding-top: 0 !important;
      }
    </style>
    <div style='height:0;margin-top:-10px;'></div>
    """, unsafe_allow_html=True)

    def _go_prev():
        st.session_state[page_key] = max(1, int(st.session_state.get(page_key, 1) or 1) - 1)

    def _go_next():
        st.session_state[page_key] = min(total_pages, int(st.session_state.get(page_key, 1) or 1) + 1)

    with st.container(key=f"claim_pagination_nav__{table_key}"):
        pg_col1, pg_col2, pg_col3, pg_col4 = st.columns([0.34, 0.34, 0.62, 7.2], gap="small", vertical_alignment="bottom")
        with pg_col1:
            st.button("‹", key=f"claim_prev_page__{table_key}", width="content", disabled=current_page <= 1, on_click=_go_prev)
        with pg_col2:
            st.button("›", key=f"claim_next_page__{table_key}", width="content", disabled=current_page >= total_pages, on_click=_go_next)
        with pg_col3:
            st.number_input(
                "Page",
                min_value=1,
                max_value=total_pages,
                step=1,
                key=page_key,
                label_visibility="collapsed",
            )
        with pg_col4:
            st.markdown(f"<div class='claim-pagination-caption'>Page {current_page:,} / {total_pages:,} · 200 rows per page</div>", unsafe_allow_html=True)


def render_claim_charts(chart_df: pd.DataFrame, label: str, top_by: str, top_n_chart: int = 10) -> None:

    if chart_df is None or chart_df.empty:
        st.info("No chart data available.")
        return

    plot_df = chart_df.head(10).copy().reset_index(drop=True)
    max_gross = max(1.0, float(plot_df["GROSS_JUTA"].max() or 1.0))
    max_sev = max(1.0, float(plot_df["AVG_SEV_JUTA"].max() or 1.0))

    rows_amount = []
    rows_severity = []
    for _, r in plot_df.iterrows():
        lbl = html.escape(str(r.get("label", "")))
        gross = float(r.get("GROSS_JUTA", 0.0) or 0.0)
        net = float(r.get("NET_JUTA", 0.0) or 0.0)
        ri = float(r.get("RI_JUTA", 0.0) or 0.0)
        sev = float(r.get("AVG_SEV_JUTA", 0.0) or 0.0)
        net_w = max(0.0, min(100.0, net / max_gross * 100.0))
        ri_w = max(0.0, min(100.0, ri / max_gross * 100.0))
        sev_w = max(0.0, min(100.0, sev / max_sev * 100.0))
        rows_amount.append(f"""
          <div class="exec-row" title="{lbl}">
            <div class="exec-label">{lbl}</div>
            <div class="exec-bars">
              <div class="stack-track">
                <div class="stack-net" style="width:{net_w:.4f}%"></div>
                <div class="stack-ri" style="width:{ri_w:.4f}%"></div>
              </div>
              <div class="exec-value">{format_id_int(gross)} Mio</div>
            </div>
          </div>
        """)
        rows_severity.append(f"""
          <div class="sev-row" title="{lbl}">
            <div class="sev-label">{lbl}</div>
            <div class="sev-track"><div class="sev-fill" style="width:{sev_w:.4f}%"></div></div>
            <div class="sev-value">{format_id_int(sev)} Mio</div>
          </div>
        """)

    dom_id = "claim_exec_chart_" + hashlib.sha1((str(label) + str(top_by) + str(len(plot_df))).encode("utf-8")).hexdigest()[:10]
    height = max(420, min(620, 150 + 38 * len(plot_df)))
    chart_html = f"""
    <style>
      .exec-visual-grid {{
        display: grid;
        grid-template-columns: minmax(0, 1.25fr) minmax(280px, 0.75fr);
        gap: 14px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, Arial, sans-serif;
      }}
      .exec-card {{
        border: 1px solid rgba(0, 51, 102, 0.10);
        border-radius: 16px;
        background: #FFFFFF;
        box-shadow: 0 10px 28px rgba(15,23,42,0.055);
        padding: 13px 14px 14px 14px;
        box-sizing: border-box;
      }}
      .exec-title {{
        font-size: 13px;
        font-weight: 850;
        color: #003366;
        letter-spacing: -0.01em;
        margin-bottom: 5px;
      }}
      .exec-sub {{
        font-size: 11.2px;
        color: #64748B;
        font-weight: 650;
        margin-bottom: 12px;
      }}
      .legend {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:8px; }}
      .legend-item {{ display:inline-flex; gap:6px; align-items:center; font-size:11px; font-weight:800; color:#475569; }}
      .dot {{ width:10px; height:10px; border-radius:999px; display:inline-block; }}
      .dot.net {{ background:#003366; }}
      .dot.ri {{ background:#9FBAD5; }}
      .exec-row {{
        display:grid;
        grid-template-columns: minmax(125px, 28%) minmax(0, 1fr);
        gap: 12px;
        align-items:center;
        padding: 6px 0;
        border-bottom: 1px solid rgba(15,23,42,0.055);
      }}
      .exec-row:last-child, .sev-row:last-child {{ border-bottom:none; }}
      .exec-label, .sev-label {{
        font-size:11.5px;
        font-weight:750;
        color:#475569;
        overflow:hidden;
        text-overflow:ellipsis;
        white-space:nowrap;
      }}
      .exec-bars {{ display:grid; grid-template-columns:minmax(0, 1fr) 88px; gap:10px; align-items:center; }}
      .stack-track {{
        height:13px;
        border-radius:999px;
        background:#EEF2F7;
        overflow:hidden;
        display:flex;
        box-shadow: inset 0 0 0 1px rgba(0,51,102,0.035);
      }}
      .stack-net {{ height:100%; background:linear-gradient(90deg, #003366, #245C91); }}
      .stack-ri {{ height:100%; background:linear-gradient(90deg, #9FBAD5, #C2D3E5); }}
      .exec-value, .sev-value {{
        font-size:10.8px;
        font-weight:850;
        color:#1E293B;
        text-align:right;
        font-variant-numeric:tabular-nums;
      }}
      .sev-row {{
        display:grid;
        grid-template-columns:minmax(90px, 32%) minmax(0, 1fr) 78px;
        gap:9px;
        align-items:center;
        padding:6px 0;
        border-bottom:1px solid rgba(15,23,42,0.055);
      }}
      .sev-track {{ height:12px; border-radius:999px; background:#EEF2F7; overflow:hidden; }}
      .sev-fill {{ height:100%; border-radius:999px; background:linear-gradient(90deg, #E39A5B, #F0B77F); }}
      @media (max-width: 900px) {{ .exec-visual-grid {{ grid-template-columns:1fr; }} }}
      @media (max-width: 640px) {{
        .exec-row {{ grid-template-columns:1fr; gap:5px; }}
        .sev-row {{ grid-template-columns:1fr; gap:5px; }}
        .exec-bars {{ grid-template-columns:minmax(0,1fr) 78px; }}
      }}
    </style>
    <div id="{dom_id}" class="exec-visual-grid">
      <div class="exec-card">
        <div class="exec-title">Claim Composition by {html.escape(str(label))}</div>
        <div class="exec-sub">Net claim and reinsurance recovery, ranked by {html.escape(str(top_by))}.</div>
        <div class="legend"><span class="legend-item"><span class="dot net"></span>Net Claim</span><span class="legend-item"><span class="dot ri"></span>RI Recovery</span></div>
        {''.join(rows_amount)}
      </div>
      <div class="exec-card">
        <div class="exec-title">Average Severity</div>
        <div class="exec-sub">Average gross claim per claim.</div>
        {''.join(rows_severity)}
      </div>
    </div>
    """
    _render_html_block(chart_html, height=height, scrolling=False)





def export_excel(export_df: pd.DataFrame, filter_lines: list[str]) -> bytes:
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
        startrow = 2 + len(filter_lines)
        export_df.to_excel(writer, index=False, sheet_name="Claim Pivot", startrow=startrow)
        workbook = writer.book
        worksheet = writer.sheets["Claim Pivot"]
        worksheet.write(0, 0, "MNC Insurance - Claim Breakdown")
        for i, line in enumerate(filter_lines):
            worksheet.write(1 + i, 0, line)
        header_format = workbook.add_format({"bold": True, "bg_color": "#003366", "font_color": "white", "align": "center"})
        num_fmt = workbook.add_format({"num_format": "#,##0", "align": "right"})
        for i, col in enumerate(export_df.columns):
            worksheet.write(startrow, i, col, header_format)
            if col in ["GROSS", "NET", "REINSURANCE", "AVG SEVERITY", "NUMBER OF CLAIMS"]:
                worksheet.set_column(i, i, 18, num_fmt)
            else:
                worksheet.set_column(i, i, 25)
    excel_buffer.seek(0)
    return excel_buffer.getvalue()


def export_pdf(export_df: pd.DataFrame, filter_lines: list[str]) -> bytes:
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("MNC Insurance - Report of Claim Breakdown", styles["Title"]),
        Spacer(1, 8),
        Paragraph("For UW Years 2021 - 2026", styles["Normal"]),
        Paragraph("This report was downloaded from SuperApp Actuary", styles["Normal"]),
        Spacer(1, 8),
    ]
    for line in filter_lines:
        elements.append(Paragraph(html.escape(str(line)), styles["Normal"]))
    elements.append(Spacer(1, 12))

    table_df = export_df.copy().head(500)
    table_data = [table_df.columns.tolist()] + table_df.apply(lambda col: col.map(format_id_int) if pd.api.types.is_numeric_dtype(col) else col.astype(str)).values.tolist()
    col_count = max(1, len(table_df.columns))
    avail_w = landscape(A4)[0] - 40
    col_widths = [avail_w / col_count] * col_count
    tbl = Table(table_data, repeatRows=1, colWidths=col_widths)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
    ]))
    elements.append(tbl)
    doc.build(elements)
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()


def render_export_controls(export_df: pd.DataFrame, tab_name: str, filter_lines: list[str], signature_payload: dict) -> None:
    safe_tab_name = tab_name.replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_")
    pdf_prefix = f"claim_export_pdf__{safe_tab_name}"
    xlsx_prefix = f"claim_export_xlsx__{safe_tab_name}"
    sig = _compute_signature(signature_payload)

    if st.session_state.get(f"{pdf_prefix}__sig") != sig:
        _clear_export_state(pdf_prefix)
    if st.session_state.get(f"{xlsx_prefix}__sig") != sig:
        _clear_export_state(xlsx_prefix)

    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:14px;font-weight:800;color:#003366;margin:4px 0 6px 0;'>Download Table</div>", unsafe_allow_html=True)
    col1, col2 = st.columns(2, gap="small")

    with col1:
        if st.button("Prepare Excel", key=f"prepare_claim_xlsx__{safe_tab_name}", width="content"):
            try:
                with st.spinner("Preparing Excel..."):
                    xlsx_bytes = cached_export_excel_bytes(export_df, tuple(filter_lines))
                st.session_state[f"{xlsx_prefix}__href"] = _make_data_uri(xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                st.session_state[f"{xlsx_prefix}__name"] = f"Claim_Pivot_{safe_tab_name}.xlsx"
                st.session_state[f"{xlsx_prefix}__sig"] = sig
                st.session_state.pop(f"{xlsx_prefix}__error", None)
                del xlsx_bytes
                gc.collect()
            except Exception as e:
                _clear_export_state(xlsx_prefix)
                st.session_state[f"{xlsx_prefix}__error"] = str(e)
        if st.session_state.get(f"{xlsx_prefix}__error"):
            st.error(f"Excel export failed: {st.session_state[f'{xlsx_prefix}__error']}")
        elif st.session_state.get(f"{xlsx_prefix}__href"):
            _render_direct_download_link("Download Excel", st.session_state[f"{xlsx_prefix}__href"], st.session_state[f"{xlsx_prefix}__name"])
            st.caption("Excel ready. Regenerate jika filter berubah.")
        else:
            st.caption("Prepare Excel dulu sebelum download.")

    with col2:
        if st.button("Prepare PDF", key=f"prepare_claim_pdf__{safe_tab_name}", width="content"):
            try:
                with st.spinner("Preparing PDF..."):
                    pdf_bytes = cached_export_pdf_bytes(export_df, tuple(filter_lines))
                st.session_state[f"{pdf_prefix}__href"] = _make_data_uri(pdf_bytes, "application/pdf")
                st.session_state[f"{pdf_prefix}__name"] = f"Claim_Pivot_{safe_tab_name}.pdf"
                st.session_state[f"{pdf_prefix}__sig"] = sig
                st.session_state.pop(f"{pdf_prefix}__error", None)
                del pdf_bytes
                gc.collect()
            except Exception as e:
                _clear_export_state(pdf_prefix)
                st.session_state[f"{pdf_prefix}__error"] = str(e)
        if st.session_state.get(f"{pdf_prefix}__error"):
            st.error(f"PDF export failed: {st.session_state[f'{pdf_prefix}__error']}")
        elif st.session_state.get(f"{pdf_prefix}__href"):
            _render_direct_download_link("Download PDF", st.session_state[f"{pdf_prefix}__href"], st.session_state[f"{pdf_prefix}__name"])
            st.caption("PDF ready. PDF uses first 500 rows. Regenerate jika filter berubah.")
        else:
            st.caption("Prepare PDF dulu sebelum download.")




def _fragment_if_available(func):

    return func


@_fragment_if_available
def render_lazy_breakdown_section(
    filtered_df: pd.DataFrame,
    tab_label_map: dict,
    filter_cols: list[str],
    top_by: str,
    filter_lines: list[str],
) -> None:
    render_section_card_header("Claim Breakdown", "Lazy view: only the selected breakdown is calculated and rendered.")

    if filtered_df is None or filtered_df.empty:
        st.info("No data available for selected filter(s).")
        return

    tab_names = [c for c in tab_label_map.keys() if c in filtered_df.columns]
    if not tab_names:
        st.info("No available breakdown column in this dataset.")
        return

    label_to_col = {tab_label_map[c]: c for c in tab_names}
    active_label_key = "claim_active_breakdown_tab"
    active_labels = list(label_to_col.keys())
    if active_label_key not in st.session_state or st.session_state[active_label_key] not in active_labels:
        st.session_state[active_label_key] = active_labels[0]

    active_label = render_risk_profile_tab_selector(
        active_labels,
        state_key=active_label_key,
        aria_label="Detailed view",
    )
    orig_name = label_to_col[active_label]

    st.markdown('<div class="detail-tab-content-card">', unsafe_allow_html=True)
    st.markdown(
        f"<div style='font-size:14px;font-weight:800;color:#003366;margin:4px 0 12px 0;'>Claim Breakdown by {html.escape(active_label)}</div>",
        unsafe_allow_html=True,
    )

    amount_cols = ["GROSS", "REINSURANCE", "NET"]
    freq_cols = ["NUMBER OF CLAIMS"]
    pivot_cols = amount_cols + freq_cols

    extra_options = [c for c in filter_cols if c in filtered_df.columns and c != orig_name and c not in pivot_cols]
    extra_key = "claim_extra_grouping_columns"
    if extra_key not in st.session_state:
        st.session_state[extra_key] = []
    _sync_multiselect_state(extra_key, extra_options)

    def _reset_extra_grouping():
        st.session_state[extra_key] = []

    ctrl_col1, ctrl_col2 = st.columns([5.2, 1.1], gap="small")
    with ctrl_col2:
        st.button("Reset", key="claim_reset_extra_grouping", width="stretch", on_click=_reset_extra_grouping)
    with ctrl_col1:
        extra_cols = st.multiselect(
            "Additional columns",
            options=extra_options,
            max_selections=5,
            key=extra_key,
            help="Tambahan breakdown untuk tabel claim. Maksimal 5 kolom agar tetap ringan.",
        )

    group_cols = [orig_name] + [c for c in extra_cols if c != orig_name]
    pivot_table = cached_claim_pivot(filtered_df, tuple(group_cols), top_by, None)
    render_claim_table(pivot_table, group_cols, table_key=orig_name)

    chart_df = cached_claim_chart_df(filtered_df, orig_name, top_by, 10)
    render_claim_charts(chart_df, active_label, top_by, 10)

    export_df = pivot_table[_existing_cols(pivot_table, group_cols + ["GROSS", "REINSURANCE", "NET", "NUMBER OF CLAIMS", "AVG SEVERITY"])].copy()
    render_export_controls(
        export_df,
        orig_name,
        filter_lines,
        {
            "active_breakdown": orig_name,
            "group_cols": group_cols,
            "top_by": top_by,
            "page_size": 200,
            "filter_lines": filter_lines,
            "rows": int(len(filtered_df)),
        },
    )
    st.markdown("</div>", unsafe_allow_html=True)


CLAIM_DATA_PATH = "CLAIM Agustus 2026.xlsx"


def main_claim():
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

  .claim-kpi-card{
    box-sizing:border-box!important;height:112px!important;padding:14px 18px!important;border-radius:22px!important;
    display:flex!important;flex-direction:column!important;justify-content:flex-start!important;align-items:flex-start!important;
    gap:6px!important;overflow:hidden!important;background:rgba(255,255,255,0.94);border:1px solid rgba(0,51,102,0.10);
    box-shadow:0 10px 26px rgba(15,23,42,0.06);
  }
  .claim-kpi-card h4{margin:0!important;font-size:13px!important;line-height:1.15!important;font-weight:650!important;color:#475569!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;max-width:100%!important;}
  .claim-kpi-card h2{margin:0!important;font-size:30px!important;line-height:1!important;font-weight:820!important;color:#003366!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;max-width:100%!important;}

  .direct-download-btn{
    display:inline-block;width:auto;box-sizing:border-box;text-align:left;padding:0;border-radius:0;background:transparent;
    color:#003366!important;border:none;text-decoration:underline!important;text-underline-offset:3px;font-weight:700;font-size:13px;
  }
  .direct-download-btn:hover{color:#E39A5B!important;background:transparent;border:none;}

  /* Browser-safe lightweight controls. Avoid :has() for laptop/browser compatibility. */
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
    st.markdown(
        """
        <div class="hero">
          <h1>Claim Breakdown Report</h1>
          <p>Portfolio-level claim view by status, policy, claim type, cause, branch, LOB, TOB, and workshop. For UW Years 2021 - 2026.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df = load_data(CLAIM_DATA_PATH)

    st.header("As at 31 Agustus 2026")
    st.caption("Amounts are shown in IDR, with charts displayed in IDR juta.")

    st.sidebar.header("Filters & Settings")
    top_by = st.sidebar.selectbox("Top By?", ["GROSS", "NET"])

    filter_cols = [
        "UW_YEAR", "STATUS", "POLICY_NO", "CLAIM NO", "COB_CODE",
        "INTERMEDIARY_NAME", "INSURED_NAME", "KODE_KLAIM", "KODE_PENYEBAB",
        "INTERNAL_REASON", "MARKETING_GROUP", "BRANCH_NAME", "LOB_NAME",
        "TOB_NAME", "WORKSHOP_NAME",
    ]

    tab_label_map = {
        "STATUS": "Status",
        "POLICY_NO": "Policy",
        "CLAIM NO": "Claim",
        "COB_CODE": "COB",
        "INTERMEDIARY_NAME": "Intermediary",
        "INSURED_NAME": "Insured",
        "KODE_KLAIM": "Claim Code",
        "KODE_PENYEBAB": "Reason",
        "INTERNAL_REASON": "Internal Reason",
        "MARKETING_GROUP": "MKT Group",
        "BRANCH_NAME": "Branch",
        "LOB_NAME": "LOB",
        "TOB_NAME": "TOB",
        "WORKSHOP_NAME": "Workshop",
    }

    filtered_df = df.copy()
    active_filters = []

    for col in filter_cols:
        if col not in filtered_df.columns:
            continue
        options = sorted(filtered_df[col].dropna().unique().tolist())
        mode_key = f"claim_mode_{col}"
        sel_key = f"claim_select_{col}"
        if mode_key not in st.session_state:
            st.session_state[mode_key] = "Include Selected"
        if sel_key not in st.session_state:
            st.session_state[sel_key] = []

        with st.sidebar.expander(f"{col}", expanded=False):
            mode = st.selectbox("Mode & Selection", ["Include Selected", "Include All", "Exclude Selected", "Exclude All"], key=mode_key)
            show_multiselect = mode in ["Include Selected", "Exclude Selected"]
            if show_multiselect:
                _sync_multiselect_state(sel_key, options)
                selected = st.multiselect("Pilih value:", options, key=sel_key)
            else:
                if st.session_state.get(sel_key):
                    st.session_state[sel_key] = []
                selected = []
                st.multiselect("Pilih value:", options, key=f"{sel_key}__disabled", disabled=True)

            if mode.startswith("Include") and selected:
                filtered_df = filtered_df[filtered_df[col].isin(selected)]
            elif mode.startswith("Exclude") and selected:
                filtered_df = filtered_df[~filtered_df[col].isin(selected)]

            if selected:
                active_filters.append(f"{col} ({mode}): {', '.join(map(str, selected))}")

    filter_lines = ["Filters Applied:"] + (active_filters if active_filters else ["No Filter (All Data were Selected)"])

    if filtered_df.empty:
        st.warning("No data available for selected filter(s).")
        return

    render_section_card_header("Key Claim Metrics")
    render_kpi_cards(compute_kpis(filtered_df))
    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    render_lazy_breakdown_section(
        filtered_df,
        tab_label_map,
        filter_cols,
        top_by,
        filter_lines,
    )




def preload_workbooks():
    load_data(CLAIM_DATA_PATH)


if __name__ == "__main__":
    main_claim()
