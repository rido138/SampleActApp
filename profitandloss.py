import base64
import hashlib
import html
import io
import json
import textwrap

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# =========================
# THEME
# =========================
def _inject_theme_css() -> None:
    st.markdown("""
    <style>
      .hero{background:linear-gradient(135deg,#003366 0%,#1E5C8A 100%);color:white;padding:28px 32px;border-radius:24px;box-shadow:0 18px 46px rgba(0,51,102,.18);margin-bottom:18px;border:1px solid rgba(255,255,255,.10)}
      .hero h1{margin:0 0 8px 0!important;color:white!important;font-size:34px;font-weight:820;letter-spacing:-.02em}.hero p{margin:0;color:rgba(255,255,255,.90);font-size:14.5px;line-height:1.55}
      .section-card-header{margin:14px 0 8px 0;padding:12px 15px;border-radius:16px;background:#F8FAFC;border:1px solid rgba(0,51,102,.10);box-shadow:0 8px 22px rgba(15,23,42,.035)}
      .section-card-title{font-size:18px;font-weight:800;color:#003366;line-height:1.15;letter-spacing:-.01em}.section-card-subtitle{font-size:12.5px;color:#64748B;line-height:1.25;margin-top:3px}
      .kpi-card.kpi-compact3{box-sizing:border-box!important;height:122px!important;padding:14px 18px!important;border-radius:22px!important;display:flex!important;flex-direction:column!important;justify-content:flex-start!important;align-items:flex-start!important;text-align:left!important;gap:6px!important;overflow:hidden!important;background:rgba(255,255,255,.94);border:1px solid rgba(0,51,102,.10);box-shadow:0 10px 26px rgba(15,23,42,.06)}
      .kpi-card.kpi-compact3 h4{margin:0!important;font-size:13px!important;line-height:1.15!important;font-weight:650!important;color:#475569!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;max-width:100%!important}.kpi-card.kpi-compact3 h2{margin:0!important;font-size:31px!important;line-height:1!important;font-weight:800!important;color:#003366!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;max-width:100%!important}
      .kpi-card.kpi-compact3.kpi-danger{background:linear-gradient(135deg,#7a0015 0%,#b00020 100%)!important;box-shadow:0 14px 34px rgba(176,0,32,.22)!important}.kpi-card.kpi-compact3.kpi-danger h4,.kpi-card.kpi-compact3.kpi-danger h2{color:white!important}
      .direct-download-btn{display:inline-block;width:auto;box-sizing:border-box;text-align:left;padding:0;border-radius:0;background:transparent;color:#003366!important;border:none;text-decoration:underline!important;text-underline-offset:3px;font-weight:700;font-size:13px}.direct-download-btn:hover{color:#E39A5B!important;background:transparent;border:none}
      div[data-testid="stSidebar"] h1,div[data-testid="stSidebar"] h2,div[data-testid="stSidebar"] h3{color:#003366!important}.detail-tab-content-card{background:#fff;border:1px solid rgba(0,51,102,.12);border-radius:18px;padding:18px 18px 20px 18px;box-shadow:0 10px 25px rgba(15,23,42,.045);margin-top:2px}
    </style>
    """, unsafe_allow_html=True)


def render_section_card_header(title: str, subtitle: str = "") -> None:
    sub = f'<div class="section-card-subtitle">{html.escape(subtitle)}</div>' if subtitle else ""
    st.markdown(f'<div class="section-card-header"><div class="section-card-title">{html.escape(title)}</div>{sub}</div>', unsafe_allow_html=True)


def _render_html_block(html_content: str, height: int = 300) -> None:
    """Render an HTML string inside an iframe across Streamlit versions."""
    if hasattr(st, "iframe"):
        # Streamlit >= 1.56: native iframe accepts an HTML string directly.
        st.iframe(html_content, width="stretch", height=height)
    else:
        # Backward-compatible fallback for the Streamlit version currently deployed.
        components.html(html_content, height=height, scrolling=False)


def _make_data_uri(data_bytes: bytes, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(data_bytes).decode("ascii")


def _render_direct_download_link(label: str, href: str, file_name: str) -> None:
    st.markdown(f'<a class="direct-download-btn" download="{html.escape(file_name, quote=True)}" href="{href}">{html.escape(label)}</a>', unsafe_allow_html=True)

# =========================
# DATA / CACHE
# =========================
def _optimize_df_memory(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.select_dtypes(include=["int", "int64", "int32"]).columns:
        out[col] = pd.to_numeric(out[col], downcast="integer")
    for col in out.select_dtypes(include=["float", "float64", "float32"]).columns:
        out[col] = pd.to_numeric(out[col], downcast="float")
    n = max(len(out), 1)
    for col in out.select_dtypes(include=["object"]).columns:
        nunique = out[col].nunique(dropna=True)
        if nunique and nunique <= 1000 and (nunique / n) <= .5:
            out[col] = out[col].astype("category")
    return out


@st.cache_data(show_spinner=False, ttl=900, max_entries=3)
def load_all_data(paths: tuple) -> pd.DataFrame:
    return _optimize_df_memory(pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True))


@st.cache_data(show_spinner=False, ttl=900, max_entries=48)
def cached_pivot(df: pd.DataFrame, index_cols: tuple, row_limit: int | None = None) -> pd.DataFrame:
    pivot = make_pivot(df, list(index_cols))
    if row_limit is not None and len(pivot) > row_limit:
        pivot = pivot.head(row_limit)
    return pivot


def _filter_mode_options():
    return ["Include Selected", "Include All", "Exclude Selected", "Exclude All"]


def _sync_multiselect_state(key: str, options):
    opts = set(options)
    cur = st.session_state.get(key, [])
    if not isinstance(cur, list):
        cur = [cur] if cur not in (None, "") else []
    st.session_state[key] = [v for v in cur if v in opts]

@st.cache_resource
def _filter_dropdown():
    return st.components.v2.component(
        "pl_filter_dropdown",
        html="""
            <label><span></span><input type="search" autocomplete="off"></label>
            <div class="options" hidden></div>
        """,
        css="""
            label { display: grid; gap: .25rem; font-size: .875rem; }
            input, .options { width: 100%; border: 1px solid var(--st-border-color);
                border-radius: .5rem; background: var(--st-secondary-background-color);
                color: var(--st-text-color); }
            input { padding: .5rem .75rem; }
            .options { max-height: 14rem; overflow-y: auto; }
            button { display: block; width: 100%; border: 0; padding: .4rem .75rem;
                background: transparent; color: inherit; text-align: left; cursor: pointer; }
            button:hover, button:focus-visible { background: var(--st-background-color); }
            button:first-child { position: sticky; top: 0; font-weight: bold;
                background: var(--st-secondary-background-color); }
            button:disabled { opacity: .5; cursor: default; }
        """,
        js="""
            export default function({ parentElement, data, setTriggerValue }) {
                const input = parentElement.querySelector('input');
                const list = parentElement.querySelector('.options');
                const selected = new Set(data.selected);
                const normalize = value => value.toLowerCase();
                const options = data.options.map(value => [value, normalize(value)]);
                parentElement.querySelector('span').textContent = data.label;
                input.disabled = data.disabled;
                input.placeholder = selected.size ? selected.size + ' selected' : 'Search options';

                function render() {
                    const query = normalize(input.value.trim());
                    const matches = options.filter(([, label]) => label.includes(query));
                    list.replaceChildren();
                    list.scrollTop = 0;

                    function addRow(label, action, checked) {
                        const row = document.createElement('button');
                        row.type = 'button';
                        row.textContent = label;
                        if (checked !== undefined) row.setAttribute('aria-pressed', checked);
                        row.onclick = action;
                        list.append(row);
                        return row;
                    }

                    const all = addRow('Select all', () => {
                        for (const [value] of matches) selected.add(value);
                        setTriggerValue('selection', [...selected]);
                        render();
                    });
                    all.disabled = !matches.length || matches.every(([value]) => selected.has(value));

                    let offset = 0;
                    function appendRows() {
                        for (const [value] of matches.slice(offset, offset + 100)) {
                            const checked = selected.has(value);
                            addRow((checked ? '✓ ' : '') + value, () => {
                                if (checked) selected.delete(value);
                                else selected.add(value);
                                setTriggerValue('selection', [...selected]);
                                render();
                            }, checked);
                        }
                        offset += 100;
                    }
                    appendRows();
                    list.onscroll = () => {
                        if (offset < matches.length &&
                            list.scrollHeight - list.scrollTop - list.clientHeight < 48) appendRows();
                    };
                }

                function open() {
                    if (input.disabled) return;
                    list.hidden = false;
                    render();
                }

                input.onfocus = open;
                input.onclick = () => { if (list.hidden) open(); };
                input.oninput = open;
                input.onkeydown = list.onkeydown = event => {
                    if (event.key === 'Escape') {
                        input.focus();
                        list.hidden = true;
                    }
                    if (event.key === 'ArrowDown' && event.target === input) {
                        event.preventDefault();
                        if (list.hidden) open();
                        list.querySelector('button:not(:disabled)')?.focus();
                    }
                };
                input.onblur = list.onfocusout = event => {
                    if (event.relatedTarget && !parentElement.contains(event.relatedTarget)) {
                        list.hidden = true;
                        input.value = '';
                    }
                };
                if (input.disabled) list.hidden = true;
                else if (!list.hidden) render();
            }
        """,
    )


def _select_matching_items(label, options, key, *, disabled=False):
    _sync_multiselect_state(key, options)
    if not hasattr(st.components, "v2"):
        return st.multiselect(label, options, key=key, disabled=disabled)

    by_label = {str(value): value for value in options}
    widget_key = f"{key}_dropdown"

    def update_selection():
        labels = st.session_state[widget_key].selection
        if labels is not None:
            st.session_state[key] = [by_label[item] for item in labels if item in by_label]

    _filter_dropdown()(
        key=widget_key,
        data={
            "label": label,
            "options": list(by_label),
            "selected": [str(value) for value in st.session_state[key]],
            "disabled": disabled,
        },
        on_selection_change=update_selection,
    )
    return st.session_state[key]


# =========================
# CALCULATION
# =========================
def make_pivot(df: pd.DataFrame, index_cols: list[str]) -> pd.DataFrame:
    index_cols = [c for c in index_cols if c in df.columns]
    if not index_cols or df is None or df.empty:
        return pd.DataFrame()
    values = [
        "NUMBER OF RISKS", "NUMBER OF CLAIMS", "GWP_AMT", "GEP_AMT", "GROSS_CLAIM",
        "COMMISSIONS", "RI_COST", "ERC_AMT", "RI_RECOVERY", "GROSS RESULT", "NET RESULT"
    ]
    work_cols = index_cols + [c for c in values if c in df.columns]
    work = df[work_cols].copy()
    for c in values:
        if c not in work.columns:
            work[c] = 0.0
        elif c not in index_cols:
            work[c] = pd.to_numeric(work[c], errors="coerce").fillna(0.0)
    for c in index_cols:
        work[c] = work[c].astype("string").fillna("(Blank)")
    pivot = work.pivot_table(index=index_cols, values=values, aggfunc="sum", fill_value=0, dropna=False)
    gep = pivot["GEP_AMT"].replace(0, np.nan)
    gwp = pivot["GWP_AMT"].replace(0, np.nan)
    pivot["Loss Ratio"] = (pivot["GROSS_CLAIM"] / gep).replace([np.inf, -np.inf], np.nan).fillna(0)
    pivot["COMM Ratio"] = (pivot["COMMISSIONS"] / gwp).replace([np.inf, -np.inf], np.nan).fillna(0)
    pivot["RI Cost Ratio"] = (pivot["ERC_AMT"] / gep).replace([np.inf, -np.inf], np.nan).fillna(0)
    pivot["RI Recovery Ratio"] = (pivot["RI_RECOVERY"] / gep).replace([np.inf, -np.inf], np.nan).fillna(0)
    pivot["CoR (before OVR)"] = pivot["Loss Ratio"] + pivot["COMM Ratio"] + pivot["RI Cost Ratio"] - pivot["RI Recovery Ratio"] + 0.15
    ratio_cols = ["Loss Ratio", "COMM Ratio", "RI Cost Ratio", "RI Recovery Ratio", "CoR (before OVR)"]
    pivot[ratio_cols] = pivot[ratio_cols] * 100
    return pivot


def compute_kpis(df: pd.DataFrame) -> dict:
    def s(c): return pd.to_numeric(df[c], errors="coerce").fillna(0).sum() if c in df.columns else 0.0
    gwp, gep, claim = s("GWP_AMT"), s("GEP_AMT"), s("GROSS_CLAIM")
    gross_result, net_result = s("GROSS RESULT"), s("NET RESULT")
    loss_ratio = claim / gep * 100 if gep else np.nan
    net_margin = net_result / gwp * 100 if gwp else np.nan
    return {"GWP": gwp, "Gross Claim": claim, "Loss Ratio": loss_ratio, "Gross Result": gross_result, "Net Result": net_result, "Net Margin": net_margin}


def render_kpi_cards(kpis: dict) -> None:
    def fmt_mio(x): return f"{int(round(float(x)/1_000_000)):,}".replace(",", ".") if pd.notna(x) else "-"
    def fmt_pct(x): return f"{round(float(x)):.0f}%" if pd.notna(x) else "-"
    def box(title, value, danger=False):
        st.markdown(f'<div class="kpi-card kpi-compact3 {"kpi-danger" if danger else ""}"><h4>{html.escape(title)}</h4><h2>{html.escape(value)}</h2></div>', unsafe_allow_html=True)
    cols = st.columns(6)
    with cols[0]: box("Total GWP (Mio)", fmt_mio(kpis["GWP"]))
    with cols[1]: box("Gross Claim (Mio)", fmt_mio(kpis["Gross Claim"]))
    with cols[2]: box("Loss Ratio", fmt_pct(kpis["Loss Ratio"]), pd.notna(kpis["Loss Ratio"]) and kpis["Loss Ratio"] > 100)
    with cols[3]: box("Gross Result (Mio)", fmt_mio(kpis["Gross Result"]), kpis["Gross Result"] < 0)
    with cols[4]: box("Net Result (Mio)", fmt_mio(kpis["Net Result"]), kpis["Net Result"] < 0)
    with cols[5]: box("Net Margin", fmt_pct(kpis["Net Margin"]), pd.notna(kpis["Net Margin"]) and kpis["Net Margin"] < 0)

# =========================
# TABLE DISPLAY
# =========================
def format_and_display(df: pd.DataFrame, table_key: str | None = None) -> None:
    df = df.copy()
    if isinstance(df.index, pd.MultiIndex):
        df = df.reset_index()
    elif df.index.name is not None:
        df = df.reset_index()
    if "ERC_AMT" in df.columns:
        df = df.drop(columns=["ERC_AMT"])
    metric_order = ["NUMBER OF RISKS", "NUMBER OF CLAIMS", "GWP_AMT", "GEP_AMT", "GROSS_CLAIM", "COMMISSIONS", "RI_COST", "RI_RECOVERY", "Loss Ratio", "COMM Ratio", "RI Cost Ratio", "RI Recovery Ratio", "CoR (before OVR)", "GROSS RESULT", "NET RESULT"]
    metric_cols = [c for c in metric_order if c in df.columns]
    group_cols = [c for c in df.columns if c not in metric_order]
    df = df[group_cols + metric_cols].replace([np.inf, -np.inf], np.nan)
    raw_df = df.copy()
    display_df = df.copy()
    money_cols = [c for c in ["GWP_AMT", "GEP_AMT", "GROSS_CLAIM", "COMMISSIONS", "RI_COST", "RI_RECOVERY", "GROSS RESULT", "NET RESULT"] if c in display_df.columns]
    count_cols = [c for c in ["NUMBER OF RISKS", "NUMBER OF CLAIMS"] if c in display_df.columns]
    ratio_cols = [c for c in display_df.columns if "Ratio" in c or "CoR" in c]
    for c in money_cols:
        display_df[c] = pd.to_numeric(display_df[c], errors="coerce") / 1_000_000
    def fmt_num(x): return "" if pd.isna(x) else f"{int(round(float(x))):,}".replace(",", ".")
    def fmt_pct(x): return "" if pd.isna(x) else f"{round(float(x)):.0f}%"
    for c in display_df.columns:
        if c in money_cols or c in count_cols:
            display_df[c] = display_df[c].apply(fmt_num)
        elif c in ratio_cols:
            display_df[c] = display_df[c].apply(fmt_pct)
        else:
            display_df[c] = display_df[c].fillna("").astype(str)
    aliases = {"UW_YEAR":"UW YEAR","GWP_AMT":"GWP<br><span>IDR Mio</span>","GEP_AMT":"GEP<br><span>IDR Mio</span>","GROSS_CLAIM":"GROSS CLAIM<br><span>IDR Mio</span>","COMMISSIONS":"COMM<br><span>IDR Mio</span>","RI_COST":"RI COST<br><span>IDR Mio</span>","RI_RECOVERY":"RI REC<br><span>IDR Mio</span>","GROSS RESULT":"GROSS RESULT<br><span>IDR Mio</span>","NET RESULT":"NET RESULT<br><span>IDR Mio</span>","NUMBER OF RISKS":"NO. OF RISKS","NUMBER OF CLAIMS":"NO. OF CLAIMS","CoR (before OVR)":"CoR"}
    def width_for(c):
        if c in group_cols: return 120 if c in ["UW_YEAR", "COB"] else 235
        if c in count_cols: return 120
        if c in ratio_cols: return 115
        if c in money_cols: return 135
        return 140
    col_widths = {c: width_for(c) for c in display_df.columns}
    min_table_width = sum(col_widths.values())
    table_height = max(240, min(500, 98 + 34 * len(display_df)))
    if table_key is None:
        table_key = hashlib.sha1(("|".join(map(str, display_df.columns)) + str(len(display_df))).encode()).hexdigest()[:10]
    table_dom_id = "pl_table_" + str(table_key).replace(" ", "_").replace("/", "_")
    css_colgroup = "".join([f"<col style='width:{col_widths[c]}px; min-width:{col_widths[c]}px;'>" for c in display_df.columns])
    sticky_left, running_left = {}, 0
    for c in display_df.columns:
        if c in group_cols:
            sticky_left[c] = running_left
            running_left += col_widths[c]
        else:
            break
    sort_options_html = "<option value=''>None</option>" + "".join([f"<option value='{i}'>{html.escape(str(c).replace('_',' '))}</option>" for i,c in enumerate(display_df.columns)])
    header_cells=[]
    for c in display_df.columns:
        cls, style = [], ""
        if c in sticky_left:
            cls.append("sticky-col"); style=f"left:{sticky_left[c]}px;"
        header_cells.append(f"<th class='{' '.join(cls)}' style='{style}'>{aliases.get(c, html.escape(str(c).replace('_',' ')))}</th>")
    body_rows=[]
    for r in range(len(display_df)):
        cells=[]
        for c in display_df.columns:
            raw_val=raw_df.iloc[r][c]
            sort_num=pd.to_numeric(pd.Series([raw_val]), errors="coerce").iloc[0]
            sort_attr=str(float(sort_num)) if pd.notna(sort_num) else html.escape(str(raw_val if pd.notna(raw_val) else "").lower())
            sort_type="num" if pd.notna(sort_num) else "text"
            classes=["text-cell" if c in group_cols else "num-cell"]
            style=""
            if c in sticky_left:
                classes.append("sticky-col"); style=f"left:{sticky_left[c]}px;"
            if c=="CoR (before OVR)" and pd.notna(sort_num) and sort_num>100: classes.append("cor-danger")
            if c=="NET RESULT" and pd.notna(sort_num) and sort_num<0: classes.append("loss-danger")
            val=html.escape(str(display_df.iloc[r][c]))
            cells.append(f"<td class='{' '.join(classes)}' style='{style}' data-sort='{sort_attr}' data-sort-type='{sort_type}'>{val}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    html_table=f"""
    <style>html,body{{margin:0;padding:0;overflow:hidden;background:transparent}}.pl-controls{{display:flex;gap:10px;align-items:center;margin:0 0 10px 0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;flex-wrap:wrap}}.pl-controls label{{font-size:12px;font-weight:650;color:#475569}}.pl-controls select,.pl-controls button{{height:34px;border:1px solid rgba(0,51,102,.16);border-radius:10px;background:#fff;color:#1F2937;font-size:12px;padding:0 10px;outline:none}}.pl-controls button{{cursor:pointer;font-weight:650;color:#003366}}.pl-wrap{{width:100%;max-height:{table_height}px;overflow:auto;border:1px solid rgba(0,51,102,.12);border-radius:16px;background:#fff;box-shadow:0 10px 28px rgba(15,23,42,.06)}}.pl-table{{border-collapse:separate;border-spacing:0;table-layout:fixed;width:{min_table_width}px;min-width:{min_table_width}px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Roboto,Arial,sans-serif;color:#334155}}.pl-table thead th{{position:sticky;top:0;z-index:30;background:#003366;color:#fff;text-align:center!important;vertical-align:middle;font-size:10.8px;line-height:1.18;font-weight:760;height:46px;padding:8px 8px;border-right:1px solid rgba(255,255,255,.18);border-bottom:1px solid rgba(0,0,0,.10);white-space:normal;box-sizing:border-box}}.pl-table thead th span{{display:block;margin-top:2px;font-size:8.8px;line-height:1;font-weight:500;opacity:.78}}.pl-table tbody td{{font-size:11.2px;line-height:1.28;height:34px;padding:8px 10px;border-right:1px solid rgba(15,23,42,.045);border-bottom:1px solid rgba(15,23,42,.055);background:#fff;color:#334155;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;box-sizing:border-box;font-weight:600}}.pl-table tbody tr:nth-child(even) td{{background:#F8FAFC}}.pl-table tbody tr:hover td{{background:#EEF6FF}}.pl-table .text-cell{{text-align:left;color:#1E3A5F}}.pl-table .num-cell{{text-align:right;font-variant-numeric:tabular-nums}}.pl-table .sticky-col{{position:sticky;z-index:20;box-shadow:2px 0 0 rgba(0,51,102,.08)}}.pl-table thead th.sticky-col{{z-index:40;background:#002B57}}.pl-table tbody td.sticky-col{{background:#fff}}.pl-table tbody tr:nth-child(even) td.sticky-col{{background:#F8FAFC}}.pl-table tbody tr:hover td.sticky-col{{background:#EEF6FF}}.pl-table tbody td.cor-danger,.pl-table tbody td.loss-danger{{background:#FFE7E7!important;color:#9F1239;font-weight:780}}</style>
    <div class='pl-controls'><label for='sort_by_{table_dom_id}'>Sort by</label><select id='sort_by_{table_dom_id}'>{sort_options_html}</select><select id='sort_order_{table_dom_id}'><option value='desc'>Descending</option><option value='asc'>Ascending</option></select><button type='button' id='reset_sort_{table_dom_id}'>Reset</button></div><div class='pl-wrap'><table class='pl-table' id='{table_dom_id}'><colgroup>{css_colgroup}</colgroup><thead><tr>{''.join(header_cells)}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>
    <script>(function(){{const table=document.getElementById('{table_dom_id}');const sortBy=document.getElementById('sort_by_{table_dom_id}');const sortOrder=document.getElementById('sort_order_{table_dom_id}');const resetBtn=document.getElementById('reset_sort_{table_dom_id}');if(!table||!sortBy||!sortOrder||!resetBtn)return;const tbody=table.querySelector('tbody');const originalRows=Array.from(tbody.querySelectorAll('tr'));function applySort(){{const colIndex=sortBy.value;if(colIndex===''){{tbody.replaceChildren(...originalRows);return;}}const idx=parseInt(colIndex,10);const asc=sortOrder.value==='asc';const rows=Array.from(tbody.querySelectorAll('tr'));rows.sort(function(a,b){{const acell=a.children[idx];const bcell=b.children[idx];const atype=acell.getAttribute('data-sort-type');const btype=bcell.getAttribute('data-sort-type');let av=acell.getAttribute('data-sort')||'';let bv=bcell.getAttribute('data-sort')||'';let result=0;if(atype==='num'&&btype==='num'){{result=(parseFloat(av)||0)-(parseFloat(bv)||0);}}else{{result=av.localeCompare(bv,undefined,{{numeric:true,sensitivity:'base'}});}}return asc?result:-result;}});tbody.replaceChildren(...rows);}}sortBy.addEventListener('change',applySort);sortOrder.addEventListener('change',applySort);resetBtn.addEventListener('click',function(){{sortBy.value='';sortOrder.value='desc';tbody.replaceChildren(...originalRows);}});}})();</script>
    """
    _render_html_block(html_table, height=table_height+86)

# =========================
# EXPORTS
# =========================
def export_excel(df: pd.DataFrame, name: str, filters=None, as_of_date=None) -> bytes:
    buffer = io.BytesIO(); out = df.copy()
    out = out.reset_index() if isinstance(out.index, pd.MultiIndex) or out.index.name is not None else out.reset_index(drop=False)
    if "ERC_AMT" in out.columns: out = out.drop(columns=["ERC_AMT"])
    for c in out.columns:
        if "Ratio" in c or "CoR" in c: out[c] = out[c].apply(lambda x: float(x)/100 if pd.notna(x) else None)
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        startrow = 3 + (len(filters) if filters else 0)
        out.to_excel(writer, index=False, startrow=startrow, sheet_name="P&L Summary")
        wb, ws = writer.book, writer.sheets["P&L Summary"]
        money_fmt = wb.add_format({"num_format":"#,##0"}); pct_fmt = wb.add_format({"num_format":"0%"})
        header_fmt = wb.add_format({"bold":True,"bg_color":"#003366","font_color":"white"})
        if as_of_date: ws.write(0,0,f"As of Date: {as_of_date}")
        row=1
        if filters:
            ws.write(row,0,"P&L Report for:"); row+=1
            for col,info in filters.items():
                vals=info.get("values",[]); mode=info.get("mode","")
                if not vals or "All" in mode: continue
                ws.write(row,0, f"{col} ({mode}): {len(vals)} selected" if len(vals)>10 else f"{col} ({mode}): {', '.join(map(str, vals))}"); row+=1
        for i,c in enumerate(out.columns):
            ws.write(startrow, i, c, header_fmt)
            if c in ["GWP_AMT","GEP_AMT","GROSS_CLAIM","COMMISSIONS","RI_COST","RI_RECOVERY","GROSS RESULT","NET RESULT"]: ws.set_column(i,i,15,money_fmt)
            elif "Ratio" in c or "CoR" in c: ws.set_column(i,i,12,pct_fmt)
            else: ws.set_column(i,i,22)
    return buffer.getvalue()


def export_pdf(df: pd.DataFrame, name: str, filters, as_of_date, sort_mode, sort_basis, num_show) -> bytes:
    buffer=io.BytesIO(); styles=getSampleStyleSheet()
    work=df.copy()
    if isinstance(work.index,pd.MultiIndex) or work.index.name is not None: work=work.reset_index()
    metric_cols=["GWP_AMT","GEP_AMT","GROSS_CLAIM","COMMISSIONS","RI_COST","RI_RECOVERY","Loss Ratio","COMM Ratio","RI Cost Ratio","RI Recovery Ratio","CoR (before OVR)","GROSS RESULT","NET RESULT"]
    group_cols=[c for c in work.columns if c not in metric_cols and c!="ERC_AMT"]
    final_cols=group_cols+[c for c in metric_cols if c in work.columns]
    work=work[final_cols].replace([np.inf,-np.inf],np.nan)
    fmt=work.copy()
    for c in fmt.columns:
        if c in ["GWP_AMT","GEP_AMT","GROSS_CLAIM","COMMISSIONS","RI_COST","RI_RECOVERY","GROSS RESULT","NET RESULT"]:
            fmt[c]=pd.to_numeric(fmt[c],errors="coerce").apply(lambda x:"" if pd.isna(x) else f"{int(round(x/1_000_000)):,}".replace(",","."))
        elif "Ratio" in c or "CoR" in c:
            fmt[c]=pd.to_numeric(fmt[c],errors="coerce").apply(lambda x:"" if pd.isna(x) else f"{round(x):.0f}%")
        else: fmt[c]=fmt[c].astype(str)
    header_style=ParagraphStyle("Header",parent=styles["Normal"],alignment=1,textColor=colors.white,fontName="Helvetica-Bold",fontSize=7)
    cell_style=ParagraphStyle("Cell",parent=styles["Normal"],fontSize=7)
    data=[[Paragraph(str(c),header_style) for c in fmt.columns]]
    style=[("BACKGROUND",(0,0),(-1,0),colors.HexColor("#003366")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.25,colors.grey),("VALIGN",(0,0),(-1,-1),"MIDDLE")]
    for r in range(len(fmt)):
        row_color=colors.HexColor("#F6F8FB") if r%2 else colors.white; style.append(("BACKGROUND",(0,r+1),(-1,r+1),row_color))
        row=[]
        for c,col in enumerate(fmt.columns):
            align=0 if col in group_cols else 2
            row.append(Paragraph(str(fmt.iloc[r,c]), ParagraphStyle(f"Cell_{r}_{c}",parent=cell_style,alignment=align)))
        data.append(row)
    pdf=SimpleDocTemplate(buffer,pagesize=landscape(A4),leftMargin=.8*cm,rightMargin=.8*cm,topMargin=.8*cm,bottomMargin=.8*cm)
    avail_w=landscape(A4)[0]-1.6*cm
    widths=[3.8*cm if c in group_cols else 1.55*cm if ("Ratio" in c or "CoR" in c) else 2.15*cm for c in fmt.columns]
    total=sum(widths)
    if total>avail_w: widths=[w*avail_w/total for w in widths]
    table=Table(data,repeatRows=1,colWidths=widths); table.setStyle(TableStyle(style))
    elements=[Paragraph("<b>MNC Insurance Profit and Loss Report</b>",styles["Title"]),Spacer(1,.25*cm),Paragraph(f"<b>As of Date:</b> {as_of_date[7:] if as_of_date else ''}",styles["Normal"]),Spacer(1,.25*cm),Paragraph(f"<b>View:</b> Top {num_show} - {sort_mode} / {sort_basis}",styles["Normal"]),Spacer(1,.35*cm),table]
    pdf.build(elements); return buffer.getvalue()

# =========================
# FRAGMENTS
# =========================
def _fragment_if_available(func):
    return st.fragment(func) if hasattr(st, "fragment") else func


def render_export_controls_fragment(safe_name, tab_name, pivot, active_filters, tanggal_pilihan, sort_mode, sort_basis, num_show):
    pdf_prefix=f"pl_pdf__{safe_name}"; xlsx_prefix=f"pl_xlsx__{safe_name}"
    sig=_compute_signature({"tab":tab_name,"filters":active_filters,"asof":tanggal_pilihan,"sort_mode":sort_mode,"sort_basis":sort_basis,"num_show":num_show,"rows":len(pivot)})
    def clear(prefix):
        for s in ("sig","href","name","error"): st.session_state.pop(prefix+"__"+s, None)
    if st.session_state.get(pdf_prefix+"__sig") != sig: clear(pdf_prefix)
    if st.session_state.get(xlsx_prefix+"__sig") != sig: clear(xlsx_prefix)
    c1,c2=st.columns(2,gap="small")
    with c1:
        if st.button("Prepare PDF", key=f"prepare_pdf_{safe_name}", width="content"):
            try:
                with st.spinner("Preparing PDF..."):
                    b=export_pdf(pivot, tab_name, active_filters, tanggal_pilihan, sort_mode, sort_basis, num_show)
                st.session_state[pdf_prefix+"__href"]=_make_data_uri(b,"application/pdf"); st.session_state[pdf_prefix+"__name"]=f"{safe_name}.pdf"; st.session_state[pdf_prefix+"__sig"]=sig; st.session_state.pop(pdf_prefix+"__error",None)
            except Exception as e:
                clear(pdf_prefix); st.session_state[pdf_prefix+"__error"]=str(e)
        if st.session_state.get(pdf_prefix+"__error"): st.error("PDF export failed: "+st.session_state[pdf_prefix+"__error"])
        elif st.session_state.get(pdf_prefix+"__href"):
            _render_direct_download_link("Download PDF", st.session_state[pdf_prefix+"__href"], st.session_state[pdf_prefix+"__name"]); st.caption("PDF ready. Regenerate jika filter berubah.")
        else: st.caption("Prepare PDF dulu sebelum download.")
    with c2:
        if st.button("Prepare Excel", key=f"prepare_xlsx_{safe_name}", width="content"):
            try:
                with st.spinner("Preparing Excel..."):
                    b=export_excel(pivot, tab_name, active_filters, tanggal_pilihan)
                st.session_state[xlsx_prefix+"__href"]=_make_data_uri(b,"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"); st.session_state[xlsx_prefix+"__name"]=f"{safe_name}.xlsx"; st.session_state[xlsx_prefix+"__sig"]=sig; st.session_state.pop(xlsx_prefix+"__error",None)
            except Exception as e:
                clear(xlsx_prefix); st.session_state[xlsx_prefix+"__error"]=str(e)
        if st.session_state.get(xlsx_prefix+"__error"): st.error("Excel export failed: "+st.session_state[xlsx_prefix+"__error"])
        elif st.session_state.get(xlsx_prefix+"__href"):
            _render_direct_download_link("Download Excel", st.session_state[xlsx_prefix+"__href"], st.session_state[xlsx_prefix+"__name"]); st.caption("Excel ready. Regenerate jika filter berubah.")
        else: st.caption("Prepare Excel dulu sebelum download.")


def _compute_signature(payload: dict) -> str:
    return hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


@_fragment_if_available
def render_detailed_data_fragment(df, active_filters, tanggal_pilihan, sort_mode, sort_basis, num_show):
    render_section_card_header("Detailed Data", "Only the active view is calculated and rendered.")
    tab_defs=[("UW Year","Portfolio Analysis - Detailed by UW Year","UW_YEAR"),("CoB","Portfolio Analysis - Detailed by CoB","COB"),("Intermediary","Portfolio Analysis - Detailed by Intermediary","INTERMEDIARY_NAME"),("Insured Name","Portfolio Analysis - Detailed by Insured Name","INSURED_NAME"),("Marketing Name","Portfolio Analysis - Detailed by Marketing Name","MARKETING_NAME"),("Marketing Group","Portfolio Analysis - Detailed by Marketing Group","MARKETING_GROUP"),("Branch","Portfolio Analysis - Detailed by Branch","BRANCH"),("Our Share Range","Portfolio Analysis - Detailed by Our Share Range","OUR TSI RANGE"),("Policy No.","Portfolio Analysis - Detailed by Policy Number","POLICY_NO")]
    tab_defs=[x for x in tab_defs if x[2] in df.columns]
    if not tab_defs: st.info("No available grouping columns."); return
    extra_map={"CoB":"COB","UW Year":"UW_YEAR","UW Month":"UW_MONTH","TOB":"TOB","LOB":"LOB","Issue":"ISSUE"}
    extra_map={k:v for k,v in extra_map.items() if v in df.columns}
    extra_key="pl_extra_columns"
    if extra_key not in st.session_state: st.session_state[extra_key]=[]
    _sync_multiselect_state(extra_key, list(extra_map.keys()))
    def reset_extra(): st.session_state[extra_key]=[]
    c1,c2=st.columns([5.2,1.1],gap="small")
    with c1:
        extra_labels=st.multiselect("Additional columns", options=list(extra_map.keys()), max_selections=4, key=extra_key)
    with c2:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True); st.button("Reset", key="pl_reset_extra", width="stretch", on_click=reset_extra)
    extra_cols=[extra_map[x] for x in extra_labels if x in extra_map]
    labels=[x[0] for x in tab_defs]
    key="pl_active_detail_tab"
    if key not in st.session_state or st.session_state[key] not in labels: st.session_state[key]=labels[0]
    _inject_radio_css()
    active=st.radio("Detailed view", options=labels, key=key, horizontal=True, label_visibility="collapsed")
    st.markdown('<div class="detail-tab-content-card">', unsafe_allow_html=True)
    label,title,primary=next((x for x in tab_defs if x[0]==active), tab_defs[0])
    group_cols=[primary]+[c for c in extra_cols if c!=primary]
    pivot=cached_pivot(df, tuple(group_cols), row_limit=None)
    result_col="GROSS RESULT" if sort_basis=="By Gross" else "NET RESULT"
    if result_col not in pivot.columns: pivot[result_col]=0
    ascending=True if sort_mode=="Loss Driver" else False
    pivot=pivot.sort_values(result_col, ascending=ascending, kind="stable").head(int(num_show))
    st.markdown(f"<div style='font-size:14px;font-weight:800;color:#003366;margin:4px 0 6px 0;'>{html.escape(title)}</div>", unsafe_allow_html=True)
    format_and_display(pivot, table_key=title)
    safe_name=title.replace(" ","_").replace("/","_").replace(":","_")
    render_export_controls_fragment(safe_name, title, pivot, active_filters, tanggal_pilihan, sort_mode, sort_basis, num_show)
    st.markdown('</div>', unsafe_allow_html=True)


def _inject_radio_css() -> None:
    st.markdown("""
    <style>
      div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Detailed view"]){width:100%!important;max-width:100%!important;margin-top:2px!important;margin-bottom:0!important;overflow:hidden!important}
      div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Detailed view"])>div{width:100%!important;max-width:100%!important;overflow-x:auto!important;overflow-y:hidden!important;padding:0 0 5px 0!important;scrollbar-width:thin!important}
      div[role="radiogroup"][aria-label="Detailed view"]{display:inline-flex!important;flex-direction:row!important;flex-wrap:nowrap!important;width:fit-content!important;min-width:100%!important;max-width:none!important;gap:8px!important;padding:4px 4px 7px 4px!important;border-bottom:1px solid rgba(0,51,102,.14)!important;box-sizing:border-box!important}
      div[role="radiogroup"][aria-label="Detailed view"] label{flex:0 0 auto!important;white-space:nowrap!important;display:inline-flex!important;align-items:center!important;justify-content:center!important;padding:9px 16px!important;margin:0!important;border-radius:999px!important;border:1px solid rgba(0,51,102,.14)!important;background:linear-gradient(180deg,#fff 0%,#F4F7FB 100%)!important;color:#334155!important;font-size:12.5px!important;line-height:1!important;font-weight:760!important;box-shadow:0 5px 14px rgba(15,23,42,.045)!important}
      div[role="radiogroup"][aria-label="Detailed view"] label:has(input:checked){background:linear-gradient(135deg,#003366 0%,#1F5A91 100%)!important;color:#fff!important;border-color:rgba(0,51,102,.72)!important;box-shadow:0 10px 22px rgba(0,51,102,.20)!important}
      div[role="radiogroup"][aria-label="Detailed view"] label:has(input:checked) *{color:#fff!important;-webkit-text-fill-color:#fff!important}div[role="radiogroup"][aria-label="Detailed view"] input,div[role="radiogroup"][aria-label="Detailed view"] svg{display:none!important}
    </style>
    """, unsafe_allow_html=True)

# =========================
# DASHBOARD
# =========================
def dashboard():
    _inject_theme_css()
    st.markdown('<div class="hero"><h1>Profit and Loss Dashboard - Newest Report</h1><p>Portfolio-level view of cash flows, profitability, and loss drivers across segments.</p></div>', unsafe_allow_html=True)
    tanggal_opsi=["261016_16 Oktober 2026", "260327_27 Maret 2026","260209_06 Maret 2026","260220_20 Februari 2026"]
    tanggal_pilihan=st.selectbox("Pilih tanggal:", tanggal_opsi, index=0)
    st.header(f"As at {tanggal_pilihan[7:]}")
    if tanggal_pilihan=="260327_27 Maret 2026": df_base=load_all_data(("RP260327_part1.parquet","RP260327_part2.parquet"))
    elif tanggal_pilihan=="260209_06 Maret 2026": df_base=load_all_data(("RP260306_part1.parquet","RP260306_part2.parquet"))
    elif tanggal_pilihan=="261016_16 Oktober 2026": df_base=load_all_data(("RP261016_part1.parquet","RP261016_part2.parquet"))
    else: df_base=load_all_data(("RP260220_part1.parquet","RP260220_part2.parquet"))
    st.sidebar.header("Filters")
    with st.sidebar.expander("Sort & Limit Options", expanded=True):
        sort_mode=st.selectbox("Choose Mode:",["Most Profitable","Loss Driver"], key="pl_sort_mode")
        sort_basis=st.selectbox("Basis:",["By Gross","By Net"], key="pl_sort_basis")
        num_show=st.number_input("Number of Data to Show", min_value=1, value=100, step=10, key="pl_num_show")
    filter_cols=["UW_YEAR","UW_MONTH","INTERMEDIARY_NAME","INSURED_NAME","COB","TOB","LOB","MARKETING_NAME","MARKETING_GROUP","BRANCH","IS_FRONTING","ISSUE"]
    active_filters={}; filtered_df=df_base
    defaults_mode={"IS_FRONTING":"Include Selected","LOB":"Exclude Selected"}; defaults_sel={"IS_FRONTING":["NON_FRONTING"],"LOB":["CREDIT INSURANCE"]}
    for col in filter_cols:
        if col not in df_base.columns: continue
        mode_key=f"pl_{col}_mode"; sel_key=f"pl_{col}_selected"
        if mode_key not in st.session_state: st.session_state[mode_key]=defaults_mode.get(col,"Include Selected")
        if sel_key not in st.session_state: st.session_state[sel_key]=defaults_sel.get(col,[]).copy()
        with st.sidebar.expander(col, expanded=False):
            mode=st.selectbox("Mode & Selection", _filter_mode_options(), key=mode_key)
            options=sorted(filtered_df[col].dropna().unique()) if col in filtered_df.columns else []
            _sync_multiselect_state(sel_key, options)
            show=mode in ["Include Selected","Exclude Selected"]
            if not show and st.session_state.get(sel_key): st.session_state[sel_key]=[]
            selected=_select_matching_items("Choose items", options, sel_key, disabled=not show)
            if mode.startswith("Include") and selected: filtered_df=filtered_df[filtered_df[col].isin(selected)]
            elif mode.startswith("Exclude") and selected: filtered_df=filtered_df[~filtered_df[col].isin(selected)]
            active_filters[col]={"mode":mode,"values":list(selected)}
    df=filtered_df
    with st.sidebar.expander("INSURED_NAME_2 (Fuzzy Search)", expanded=False):
        mode=st.radio("Mode", ["Include Selected","Exclude Selected","All"], key="pl_mode_INSURED2")
        options = sorted(df.get("INSURED_NAME_2", pd.Series(dtype=str)).dropna().astype(str).unique())
        selected = _select_matching_items(
            "Hasil pencarian:", options, "pl_select_INSURED2"
        )
        if mode=="Include Selected" and selected and "INSURED_NAME_2" in df.columns: df=df[df["INSURED_NAME_2"].astype(str).isin(selected)]
        elif mode=="Exclude Selected" and selected and "INSURED_NAME_2" in df.columns: df=df[~df["INSURED_NAME_2"].astype(str).isin(selected)]
        active_filters["INSURED_NAME_2"]={"mode":mode,"values":selected if selected else ["All"]}
    with st.sidebar.expander("POLICY_NO (Fuzzy Search)", expanded=False):
        mode=st.radio("Mode", ["Include Selected","Exclude Selected","All"], key="pl_mode_POLNO")
        options = sorted(df.get("POLICY_NO", pd.Series(dtype=str)).dropna().astype(str).unique())
        selected = _select_matching_items(
            "Hasil pencarian:", options, "pl_select_POLNO"
        )
        if mode=="Include Selected" and selected and "POLICY_NO" in df.columns: df=df[df["POLICY_NO"].astype(str).isin(selected)]
        elif mode=="Exclude Selected" and selected and "POLICY_NO" in df.columns: df=df[~df["POLICY_NO"].astype(str).isin(selected)]
        active_filters["POLICY_NO"]={"mode":mode,"values":selected if selected else ["All"]}
    if df.empty:
        st.warning("No data on this filter"); return
    render_section_card_header("Key Performance Indicators")
    render_kpi_cards(compute_kpis(df))
    render_detailed_data_fragment(df, active_filters, tanggal_pilihan, sort_mode, sort_basis, int(num_show))


# Home reuses the P&L loader and aggregation; its controls are independent.
PL_HOME_SNAPSHOTS = {
    "16 Oktober 2026": ("RP261016_part1.parquet", "RP261016_part2.parquet"),
    "27 Maret 2026": ("RP260327_part1.parquet", "RP260327_part2.parquet"),
    "06 Maret 2026": ("RP260306_part1.parquet", "RP260306_part2.parquet"),
    "20 Februari 2026": ("RP260220_part1.parquet", "RP260220_part2.parquet"),
}


def home_loss_driver_summary(df, group_col, basis="Gross", apply_defaults=True):
    """Same default scope, result aggregation and ascending ranking as P&L."""
    if group_col not in df.columns:
        raise ValueError("Grouping column is unavailable.")
    result_col = "GROSS RESULT" if basis == "Gross" else "NET RESULT"
    if result_col not in df.columns:
        raise ValueError(f"{result_col} is unavailable.")
    scope = df
    if apply_defaults and "IS_FRONTING" in scope.columns:
        scope = scope[scope["IS_FRONTING"].isin(["NON_FRONTING"])]
    if apply_defaults and "LOB" in scope.columns:
        scope = scope[~scope["LOB"].isin(["CREDIT INSURANCE"])]
    if scope.empty:
        return pd.DataFrame(), 0.0
    pivot = make_pivot(scope, [group_col])
    # Rank all segments by result, including zero and positive results.
    ranked = pivot.sort_values(result_col, kind="stable")
    total_loss = float(-pivot.loc[pivot[result_col] < 0, result_col].sum())
    if len(ranked) > 20:
        ranked = ranked.head(10)
    return ranked.reset_index(), total_loss


def render_home_loss_table(top, result_col, basis):
    """Escaped, responsive HTML table with compact financial formatting."""
    rows = []
    for rank, (_, row) in enumerate(top.iterrows(), 1):
        def money(col):
            return f"{float(row[col]) / 1_000_000:,.1f}"
        value = float(row[result_col]) / 1_000_000
        result_text = f"({abs(value):,.1f})" if value < 0 else f"{value:,.1f}"
        result_color = "#9F2940" if value < 0 else "#1E5C8A" if value > 0 else "#64748B"
        rows.append(
            f'<tr><td class="kai-rank">{rank:02d}</td>'
            f'<td class="kai-name">{html.escape(str(row["Segment"]))}</td>'
            f'<td>{money("GWP_AMT")}</td><td>{money("GROSS_CLAIM")}</td>'
            f'<td class="kai-result" style="color:{result_color};">{result_text}</td>'
            f'<td>{float(row["Loss Ratio"]):,.1f}%</td></tr>'
        )
    return (
        '<style>.kai-table-wrap{overflow-x:auto;border:1px solid #DCE5EF;border-radius:14px;margin:12px 0 18px;}'
        '.kai-table{width:100%;border-collapse:collapse;font-size:13px;color:#334155;}'
        '.kai-table th{background:#003366;color:white;font-weight:600;padding:13px 16px;text-align:right;white-space:nowrap;}'
        '.kai-table td{padding:12px 16px;border-bottom:1px solid #EAF0F8;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;}'
        '.kai-table tr:last-child td{border-bottom:0}.kai-table tbody tr:nth-child(even){background:#F4F7FB;}'
        '.kai-table tbody tr:hover{background:#EAF0F8}.kai-table .kai-name,.kai-table th:nth-child(2){text-align:left;min-width:220px;white-space:normal;}'
        '.kai-table .kai-rank{color:#64748B}.kai-table .kai-result{color:#003366;font-weight:700;}</style>'
        '<div class="kai-table-wrap"><table class="kai-table"><thead><tr>'
        '<th>#</th><th>Account / Segment</th><th>GWP · Mio</th><th>Gross Claim · Mio</th>'
        f'<th>{html.escape(basis)} Result · Mio</th><th>Gross LR</th></tr></thead><tbody>'
        + ''.join(rows) + '</tbody></table></div>'
    )


def render_home_loss_drivers():
    """Compact authenticated landing insight, without running the P&L page."""
    st.markdown('<h3 style="color:#003366;margin-bottom:0;">Key Account Insight -- Loss Driver</h3>', unsafe_allow_html=True)
    date_col, basis_col = st.columns([2, 1])
    with date_col:
        snapshot = st.selectbox("As at", list(PL_HOME_SNAPSHOTS), key="home_loss_snapshot")
    with basis_col:
        basis = st.selectbox("Basis", ["Gross", "Net"], key="home_loss_basis")
    try:
        with st.spinner("Loading portfolio insight…"):
            df = load_all_data(PL_HOME_SNAPSHOTS[snapshot])
        groups = {label: col for label, col in [
            ("Insured Name", "INSURED_NAME"), ("CoB", "COB"),
            ("Intermediary", "INTERMEDIARY_NAME"), ("Branch", "BRANCH"),
            ("UW Year", "UW_YEAR"), ("Marketing Name", "MARKETING_NAME"),
            ("Marketing Group", "MARKETING_GROUP"), ("Policy No.", "POLICY_NO")
        ] if col in df.columns}
        if not groups:
            st.info("Kolom pengelompokan belum tersedia untuk insight ini.")
            return
    except Exception:
        st.info("Insight P&L belum tersedia. Periksa ketersediaan data snapshot pada server.")
        return

    # Filter the full snapshot before aggregating and ranking each gallery view.
    filtered = df
    with st.expander("Filter insight", expanded=False):
        filter_cols = [c for c in ["UW_YEAR", "UW_MONTH", "COB", "TOB", "LOB",
            "BRANCH", "MARKETING_NAME", "MARKETING_GROUP", "INTERMEDIARY_NAME",
            "INSURED_NAME", "IS_FRONTING", "ISSUE"] if c in df.columns]
        for i, col in enumerate(filter_cols):
            options = sorted(df[col].dropna().astype(str).unique().tolist())
            if col == "UW_MONTH":
                # Keep raw option values for exact filtering; sort numerically.
                month_values = pd.to_numeric(pd.Series(options), errors="coerce")
                month_order = dict(zip(options, month_values))
                options.sort(key=lambda value: (
                    pd.isna(month_order[value]),
                    float(month_order[value]) if pd.notna(month_order[value]) else float("inf"),
                    value,
                ))
            key = "home_insight_filter_" + col
            if key not in st.session_state:
                st.session_state[key] = ["NON_FRONTING"] if col == "IS_FRONTING" and "NON_FRONTING" in options else []
            chosen = _select_matching_items(col.replace("_", " ").title(), options, key)
            if chosen:
                filtered = filtered[filtered[col].astype(str).isin(chosen)]
        exclude_credit = st.checkbox("Exclude Credit Insurance", value=True, key="home_insight_exclude_credit")
        if exclude_credit and "LOB" in filtered.columns:
            filtered = filtered[~filtered["LOB"].isin(["CREDIT INSURANCE"])]

    render_home_loss_gallery(filtered, groups, basis)


@_fragment_if_available
def render_home_loss_gallery(filtered, groups, basis):
    """Only navigation, KPIs, chart and table rerun on Previous/Next.

    Snapshot loading, filter widgets and the rest of Home remain outside this
    fragment. Parent reruns supply fresh data when a filter or basis changes.
    """
    labels = list(groups)
    index = int(st.session_state.get("home_insight_gallery_index", 0)) % len(labels)
    prev_col, title_col, next_col = st.columns([1, 3, 1])
    with prev_col:
        if st.button("← Previous", key="home_insight_prev", use_container_width=True):
            index = (index - 1) % len(labels)
    with next_col:
        if st.button("Next →", key="home_insight_next", use_container_width=True):
            index = (index + 1) % len(labels)
    st.session_state["home_insight_gallery_index"] = index
    group = labels[index]
    with title_col:
        st.markdown(f'<div style="text-align:center;padding:8px;border:1px solid #DCE5EF;border-radius:12px;background:#F4F7FB;color:#003366;font-weight:700;">{html.escape(group)} <span style="color:#64748B;font-size:12px;margin-left:12px;">{index + 1} / {len(labels)}</span></div>', unsafe_allow_html=True)
    try:
        top, total_loss = home_loss_driver_summary(filtered, groups[group], basis, apply_defaults=False)
    except Exception:
        st.info("Insight P&L belum tersedia. Periksa ketersediaan data snapshot pada server.")
        return
    missing_filters = [c for c in ("IS_FRONTING", "LOB") if c not in filtered.columns]
    if missing_filters:
        st.warning("Filter scope tidak tersedia: " + ", ".join(missing_filters))
    if top.empty:
        st.info("Tidak ada data pada filter ini.")
        return
    result_col = "GROSS RESULT" if basis == "Gross" else "NET RESULT"
    top["Segment"] = top[groups[group]].astype(str)
    top["Result (IDR Mio)"] = top[result_col] / 1_000_000
    top["Status"] = top[result_col].map(lambda value: "Rugi" if value < 0 else "Laba" if value > 0 else "Nol")
    top_loss = float(-top.loc[top[result_col] < 0, result_col].sum())
    left, right = st.columns(2)
    left.metric(f"{basis} result for {len(top)} displayed segments · IDR Mio", f"{top[result_col].sum() / 1_000_000:,.1f}")
    right.metric("Share of total segment losses", f"{top_loss / total_loss:.1%}" if total_loss else "—")
    # A fixed plotting height and label area keep every gallery slide stable.
    # Wrap the display labels without changing segment identity or tooltips.
    label_map = {
        str(name): "\n".join(textwrap.wrap(str(name), width=42, break_long_words=True, break_on_hyphens=False))
        for name in top["Segment"]
    }
    label_expression = "split(" + json.dumps(label_map, ensure_ascii=False) + "[datum.label], '\\n')"
    st.vega_lite_chart(top[["Segment", "Result (IDR Mio)", "Loss Ratio", "Status"]], {
        "height": 440,
        "padding": {"top": 18, "bottom": 18, "left": 8, "right": 24},
        "mark": {"type": "bar", "cornerRadiusEnd": 4},
        "encoding": {
            "color": {"field": "Status", "type": "nominal",
                      "scale": {"domain": ["Rugi", "Laba", "Nol"], "range": ["#9F2940", "#1E5C8A", "#64748B"]},
                      "legend": {"title": None, "orient": "bottom"}},
            "y": {"field": "Segment", "type": "nominal", "sort": "x",
                  "axis": {"title": None, "labelLimit": 0, "labelColor": "#334155",
                           "labelOverlap": False, "labelExpr": label_expression,
                           "labelFontSize": 11, "labelLineHeight": 13,
                           "labelPadding": 12, "minExtent": 330, "maxExtent": 330}},
            "x": {"field": "Result (IDR Mio)", "type": "quantitative",
                  "axis": {"title": "Result · IDR Mio", "gridColor": "#EAF0F8"}},
            "tooltip": [{"field": "Segment", "type": "nominal"},
                        {"field": "Result (IDR Mio)", "type": "quantitative", "format": ",.2f"},
                        {"field": "Loss Ratio", "title": "Gross loss ratio (%)", "type": "quantitative", "format": ".1f"}],
        },
        "config": {"view": {"stroke": None}, "axis": {"domain": False, "ticks": False}},
    }, use_container_width=True)
    st.markdown(render_home_loss_table(top, result_col, basis), unsafe_allow_html=True)
    st.divider()


def mainpl():
    if "logged_in" not in st.session_state: st.session_state["logged_in"] = True
    if not st.session_state["logged_in"]: st.write("Please login from main SuperApp.")
    else:
        try:
            dashboard()
        except Exception as e:
            st.error("Under Reconstruction\n#BakalJadiKeren")
            with st.expander("Technical details", expanded=False): st.code(str(e))
        if st.sidebar.button("Logout", key="logout_btn"):
            st.session_state["logged_in"] = False; st.rerun()

if __name__ == "__main__":
    mainpl()
