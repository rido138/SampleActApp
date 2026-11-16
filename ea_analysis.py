import io
import base64
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import altair as alt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle










def load_workbook(path: str) -> pd.DataFrame:
    return pd.read_excel(path)


def cached_pivot(df: pd.DataFrame, index_cols: tuple[str, ...]) -> pd.DataFrame:
    return make_pivot(df, list(index_cols))


def cached_export_pdf(df: pd.DataFrame, name: str, filters: dict, as_of_date: str) -> bytes:
    return export_pdf(df, name, filters, as_of_date)


def cached_export_excel(df: pd.DataFrame, name: str, filters: dict, as_of_date: str) -> bytes:
    return export_excel(df, name, filters, as_of_date)


def _sync_multiselect_state(key: str, options: list) -> list:
    valid = [v for v in st.session_state.get(key, []) if v in options]
    st.session_state[key] = valid
    return valid


def _download_click_kwargs() -> dict:
    try:
        major, minor, *_ = [int(x) for x in st.__version__.split(".")]
        if (major, minor) >= (1, 43):
            return {"on_click": "ignore"}
    except Exception:
        pass
    return {}


def _clear_export_state(prefix: str) -> None:
    for suffix in ("sig", "bytes", "href", "name", "error"):
        st.session_state.pop(f"{prefix}__{suffix}", None)


def _compute_export_signature(payload: dict) -> str:
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    return __import__("hashlib").sha1(payload_json.encode("utf-8")).hexdigest()


def _make_data_uri(data_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(data_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _render_direct_download_link(label: str, href: str, file_name: str, ready: bool = True) -> None:
    css_class = "direct-download-btn is-ready" if ready else "direct-download-btn"
    st.markdown(
        f'<a class="{css_class}" download="{html.escape(file_name, quote=True)}" href="{href}">{html.escape(label)}</a>',
        unsafe_allow_html=True,
    )


def _render_safe_error(exc: Exception) -> None:
    st.error("Under Reconstruction\n#BakalJadiKeren")
    with st.expander("Technical details", expanded=False):
        st.code(str(exc))





def make_pivot(df: pd.DataFrame, index_cols: list[str]) -> pd.DataFrame:
    pivot = df.pivot_table(
        index=index_cols,
        values=[
            "NUMBER OF RISKS",
            "NUMBER OF CLAIMS",
            "GWP",
            "GEP",
            "GROSS CLAIMS",
            "COMMISSION",
            "RI COST",
            "ERC",
            "RI RECOVERY",
        ],
        aggfunc="sum",
        fill_value=0,
    )

    pivot["Loss Ratio"] = pivot["GROSS CLAIMS"] / pivot["GEP"]
    pivot["COMM Ratio"] = pivot["COMMISSION"] / pivot["GWP"]
    pivot["RI Cost Ratio"] = pivot["ERC"] / pivot["GEP"]
    pivot["RI Recovery Ratio"] = pivot["RI RECOVERY"] / pivot["GEP"]
    pivot["CoR (before OVR)"] = (
        pivot["Loss Ratio"] + pivot["COMM Ratio"] + pivot["RI Cost Ratio"] - pivot["RI Recovery Ratio"] + 0.15
    )

    ratio_cols = ["Loss Ratio", "COMM Ratio", "RI Cost Ratio", "RI Recovery Ratio", "CoR (before OVR)"]
    pivot[ratio_cols] *= 100

    if len(pivot) > 500:
        pivot = pivot.head(500)

    return pivot







def compute_kpis(df: pd.DataFrame) -> dict:
    gwp = df["GWP"].sum() if "GWP" in df.columns else 0.0
    gep = df["GEP"].sum() if "GEP" in df.columns else 0.0
    claim = df["GROSS CLAIMS"].sum() if "GROSS CLAIMS" in df.columns else 0.0
    comm = df["COMMISSION"].sum() if "COMMISSION" in df.columns else 0.0
    ri_cost = df["ERC"].sum() if "ERC" in df.columns else 0.0
    ri_rec = df["RI RECOVERY"].sum() if "RI RECOVERY" in df.columns else 0.0

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
        "CoR": cor * 100,
    }


def render_kpi_cards(kpis: dict) -> None:
    st.markdown("""
    <style>
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

    if pd.notna(cor_value) and cor_value > 100:
        msg = "Bisnis ini mencatatkan rugi (CoR > 100%)."
        key = f"cor_toast_shown_{int(round(cor_value))}"
        if not st.session_state.get(key, False):
            st.session_state[key] = True
            st.markdown(
                f'<div class="cor-toast"><div class="icon">!</div><div class="txt">{msg}</div></div>',
                unsafe_allow_html=True
            )




def _render_html_block(html_content: str, height: int = 300, scrolling: bool = False) -> None:

    components.html(html_content, height=height, scrolling=scrolling)


def format_and_display(df: pd.DataFrame, table_key: str | None = None) -> None:

    df = df.copy()

    if isinstance(df.index, pd.MultiIndex):
        df = df.reset_index()
    elif df.index.name is not None:
        df = df.reset_index()

    if "ERC" in df.columns:
        df = df.drop(columns=["ERC"])

    metric_order = [
        "NUMBER OF RISKS", "NUMBER OF CLAIMS",
        "GWP", "GEP", "GROSS CLAIMS",
        "COMMISSION", "RI COST", "RI RECOVERY",
        "Loss Ratio", "COMM Ratio", "RI Cost Ratio",
        "RI Recovery Ratio", "CoR (before OVR)",
    ]
    metric_cols = [c for c in metric_order if c in df.columns]
    group_cols = [c for c in df.columns if c not in metric_order]
    final_cols = group_cols + metric_cols
    df = df[final_cols]
    df.replace([np.inf, -np.inf], np.nan, inplace=True)

    if table_key is None:
        table_key = __import__("hashlib").sha1(("|".join(map(str, final_cols)) + str(len(df))).encode("utf-8")).hexdigest()[:10]
    table_key = str(table_key).replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_")
    table_dom_id = f"ea_table_{table_key}"

    raw_df = df.copy()
    display_df = df.copy()

    money_cols = ["GWP", "GEP", "GROSS CLAIMS", "COMMISSION", "RI COST", "RI RECOVERY"]
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
            display_df[col] = display_df[col].fillna("").astype(str)

    col_alias = {
        "UW YEAR": "UW YEAR",
        "GWP": "GWP<br><span>IDR Mio</span>",
        "GEP": "GEP<br><span>IDR Mio</span>",
        "GROSS CLAIMS": "GROSS CLAIMS<br><span>IDR Mio</span>",
        "COMMISSION": "COMM<br><span>IDR Mio</span>",
        "RI COST": "RI COST<br><span>IDR Mio</span>",
        "RI RECOVERY": "RI REC<br><span>IDR Mio</span>",
        "NUMBER OF RISKS": "NO. OF RISKS",
        "NUMBER OF CLAIMS": "NO. OF CLAIMS",
        "Loss Ratio": "LOSS RATIO",
        "COMM Ratio": "COMM RATIO",
        "RI Cost Ratio": "RI COST RATIO",
        "RI Recovery Ratio": "RI REC RATIO",
        "CoR (before OVR)": "CoR",
    }

    def width_for(col):


        if col in group_cols:
            wide_text_cols = {
                "INTERMEDIARY", "INSURED NAME", "MARKETING GROUP",
                "PCKG DESC", "COVERAGE", "TSI RANGE", "SUB-TYPE",
            }
            medium_text_cols = {"LOB", "TOB", "TYPE", "BRAND", "BRANCH"}
            compact_cols = {"UW YEAR", "AGE", "IS_HE", "IS_FRONTING"}

            if col in wide_text_cols:
                return 300
            if col in medium_text_cols:
                return 210
            if col in compact_cols:
                return 130
            return 240

        if col in count_cols:
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





def export_pdf(df: pd.DataFrame, name: str, filters: dict, as_of_date: str) -> bytes:
    buffer = io.BytesIO()

    df_numeric = df.copy()
    df_formatted = df.copy()

    star_cols = {"GWP", "GEP", "GROSS CLAIMS", "COMMISSION", "RI COST", "RI RECOVERY"}

    desired_order = [
        "GWP",
        "GEP",
        "GROSS CLAIMS",
        "COMMISSION",
        "RI COST",
        "RI RECOVERY",
        "Loss Ratio",
        "COMM Ratio",
        "RI Cost Ratio",
        "RI Recovery Ratio",
        "CoR (before OVR)",
    ]

    existing_cols = [c for c in desired_order if c in df.columns]
    df_numeric = df_numeric[existing_cols]
    df_formatted = df_formatted[existing_cols]
    df_formatted = df_formatted.replace([np.inf, -np.inf], np.nan).fillna(0)

    for col in df_formatted.columns:
        if "Ratio" in col or "CoR" in col:
            df_formatted[col] = df_formatted[col].apply(lambda x: f"{round(float(x)):.0f}%" if pd.notna(x) else "")
        else:
            df_formatted[col] = df_formatted[col].apply(
                lambda x: f"{int(round(float(x) / 1_000_000)):,}".replace(",", ".") if pd.notna(x) else ""
            )

    df_formatted.insert(0, df_formatted.index.name or "Index", df_formatted.index)
    df_numeric.insert(0, df_numeric.index.name or "Index", df_numeric.index)

    def add_star(col: str) -> str:
        return f"{col}*" if col in star_cols else col

    df_formatted = df_formatted.rename(columns=add_star)
    df_numeric = df_numeric.rename(columns=add_star)

    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        "HeaderWrap",
        parent=styles["Normal"],
        alignment=1,
        textColor=colors.white,
        fontName="Helvetica-Bold",
        fontSize=7,
    )
    cell_style = ParagraphStyle("CellText", parent=styles["Normal"], alignment=2, fontSize=7)

    wrapped_headers = [Paragraph(str(col), header_style) for col in df_formatted.columns]
    data = [wrapped_headers]

    table_style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
    ]

    for r in range(len(df_formatted)):
        row_cells = []
        for c, col_name in enumerate(df_formatted.columns):
            val = df_formatted.iloc[r, c]
            raw_val = df_numeric.iloc[r, c] if col_name in df_numeric.columns else None

            cell_bg = colors.white
            if col_name == "CoR (before OVR)" and pd.notna(raw_val) and raw_val > 100:
                cell_bg = colors.HexColor("#FFD966")
            if col_name == "Loss Ratio" and pd.notna(raw_val) and raw_val > 50:
                cell_bg = colors.HexColor("#FFA07A")

            style = ParagraphStyle(
                "Cell",
                parent=cell_style,
                alignment=0 if c == 0 else 2,
                fontSize=9 if c != 0 else 8,
                fontName="Helvetica-Bold" if c == 0 else "Helvetica",
            )

            row_cells.append(Paragraph(str(val), style))
            table_style_cmds.append(("BACKGROUND", (c, r + 1), (c, r + 1), cell_bg))

        data.append(row_cells)

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=0.8 * cm,
        rightMargin=0.8 * cm,
        topMargin=0.8 * cm,
        bottomMargin=0.8 * cm,
    )

    table = Table(
        data,
        repeatRows=1,
        colWidths=[4 * cm if i == 0 else 1.6 * cm if ("Ratio" in col or "CoR" in col) else 2.5 * cm for i, col in enumerate(df_formatted.columns)],
    )
    table.setStyle(TableStyle(table_style_cmds))

    elements = [Paragraph("<b>MNC Insurance Portfolio Analysis Report</b>", styles["Title"]), Spacer(1, 0.2 * cm)]

    if filters:
        elements.append(Paragraph("<b>Portfolio Report for:</b>", styles["Normal"]))
        elements.append(Paragraph("<b>COB: Engineering</b>", styles["Normal"]))
        for col, info in filters.items():
            mode = str(info.get("mode", ""))
            vals = info.get("values", [])
            vals_norm = [str(v).strip().lower() for v in vals]
            if "all" in mode.lower() or not vals_norm or (len(vals_norm) == 1 and vals_norm[0] == "all"):
                continue
            text = f"{col} ({mode}): {len(vals)} selected" if len(vals) > 10 else f"{col} ({mode}): {', '.join(map(str, vals))}"
            elements.append(Paragraph(text, styles["Normal"]))

    if as_of_date:
        elements.append(Spacer(1, 0.2 * cm))
        elements.append(Paragraph(f"<b>Reporting Date/As At:</b> {as_of_date}", styles["Normal"]))
        elements.append(Paragraph("<i>* Amount in IDR Million</i>", styles["Normal"]))

    elements.append(table)
    pdf.build(elements)

    return buffer.getvalue()





def export_excel(df: pd.DataFrame, name: str, filters: dict | None = None, as_of_date: str | None = None) -> bytes:
    buffer = io.BytesIO()
    df_to_export = df.copy()

    if isinstance(df_to_export.index, pd.MultiIndex):
        df_to_export = df_to_export.reset_index()
    else:
        df_to_export.index.name = df_to_export.index.name or "Index"
        df_to_export = df_to_export.reset_index()

    if "ERC" in df_to_export.columns:
        df_to_export.drop(columns=["ERC"], inplace=True)

    for col in df_to_export.columns:
        if "Ratio" in col or "CoR" in col:
            df_to_export[col] = df_to_export[col].apply(lambda x: float(x) / 100 if pd.notna(x) else None)

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        startrow = 2 + (len(filters) if filters else 0)
        df_to_export.to_excel(writer, index=False, startrow=startrow, sheet_name="Sheet1")
        workbook = writer.book
        worksheet = writer.sheets["Sheet1"]

        money_fmt = workbook.add_format({"num_format": "#,##0"})
        pct_fmt = workbook.add_format({"num_format": "0%"})

        for i, col in enumerate(df_to_export.columns):
            if col in ["GWP", "GEP", "GROSS CLAIMS", "COMMISSION", "RI COST", "RI RECOVERY"]:
                worksheet.set_column(i, i, 15, money_fmt)
            elif "Ratio" in col or "CoR" in col:
                worksheet.set_column(i, i, 12, pct_fmt)
            else:
                worksheet.set_column(i, i, 20)

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
                    text = f"{col} ({mode}): All selected"
                elif len(vals) > 10:
                    text = f"{col} ({mode}): {len(vals)} selected"
                else:
                    text = f"{col} ({mode}): {', '.join(map(str, vals))}"
                worksheet.write(row_offset, 0, text)
                row_offset += 1

    return buffer.getvalue()



def render_section_card_header(title: str, subtitle: str = "") -> None:
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
    </style>
    <div class="section-card-header">
      <div class="section-card-title">{html.escape(title)}</div>
      {subtitle_html}
    </div>
    """, unsafe_allow_html=True)


def _inject_ea_detail_radio_css() -> None:

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
      div.stButton > button[kind="secondary"] {
        height: 34px !important;
        min-height: 34px !important;
        padding: 0 12px !important;
        border-radius: 10px !important;
        font-size: 12px !important;
        font-weight: 750 !important;
      }
    </style>
    """, unsafe_allow_html=True)




def _cached_ea_yearly_trend(source_df: pd.DataFrame) -> pd.DataFrame:

    required = {"UW YEAR", "GWP", "GEP", "GROSS CLAIMS"}
    if source_df is None or source_df.empty or not required.issubset(source_df.columns):
        return pd.DataFrame()

    tmp = source_df[["UW YEAR", "GWP", "GEP", "GROSS CLAIMS"]].copy()
    tmp["UW YEAR"] = pd.to_numeric(tmp["UW YEAR"], errors="coerce")
    tmp = tmp[tmp["UW YEAR"].notna()].copy()
    if tmp.empty:
        return pd.DataFrame()

    for col in ["GWP", "GEP", "GROSS CLAIMS"]:
        tmp[col] = pd.to_numeric(tmp[col], errors="coerce").fillna(0.0)

    yearly = (
        tmp.groupby("UW YEAR", as_index=False)
        .agg(
            GWP=("GWP", "sum"),
            GEP=("GEP", "sum"),
            GROSS_CLAIMS=("GROSS CLAIMS", "sum"),
        )
        .sort_values("UW YEAR")
        .reset_index(drop=True)
    )
    yearly["UW YEAR"] = yearly["UW YEAR"].astype(int)
    yearly["GWP Mio"] = yearly["GWP"] / 1_000_000
    yearly["Loss Ratio %"] = np.where(
        yearly["GEP"] > 0,
        yearly["GROSS_CLAIMS"] / yearly["GEP"] * 100.0,
        np.nan,
    )
    return yearly


def render_trend_projection_section(source_df: pd.DataFrame) -> None:

    render_section_card_header("Trend & Projection")
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

    missing = [c for c in ["UW YEAR", "GWP", "GEP", "GROSS CLAIMS"] if c not in source_df.columns]
    if missing:
        st.info("Trend unavailable. Missing: " + ", ".join(missing))
        return

    yearly = _cached_ea_yearly_trend(source_df)
    if yearly.empty:
        st.info("Trend unavailable for the selected filters.")
        return

    latest_year = int(yearly["UW YEAR"].max())
    complete_yearly = yearly[yearly["UW YEAR"] < latest_year].copy()

    if len(complete_yearly) < 2:
        st.info("Need at least 2 completed UW years for projection.")
        return

    ma_window = min(3, len(complete_yearly))
    project_year = int(complete_yearly["UW YEAR"].max()) + 1

    gwp_forecast = float(complete_yearly["GWP Mio"].tail(ma_window).mean())
    lr_forecast = float(complete_yearly["Loss Ratio %"].dropna().tail(ma_window).mean())

    actual = complete_yearly[["UW YEAR", "GWP Mio", "Loss Ratio %"]].copy()
    actual["Type"] = "Actual"
    projection = pd.DataFrame({
        "UW YEAR": [project_year],
        "GWP Mio": [gwp_forecast],
        "Loss Ratio %": [lr_forecast],
        "Type": ["Projection"],
    })

    chart_df = pd.concat([actual, projection], ignore_index=True)
    chart_df["UW_YEAR_LABEL"] = chart_df["UW YEAR"].astype(str)
    chart_df["GWP_LABEL"] = chart_df["GWP Mio"].map(lambda x: f"{x:,.0f}".replace(",", ".") if pd.notna(x) else "")
    chart_df["LR_LABEL"] = chart_df["Loss Ratio %"].map(lambda x: f"{x:.0f}%" if pd.notna(x) else "")

    color_scale = alt.Scale(domain=["Actual", "Projection"], range=["#003366", "#E39A5B"])

    def _bar_chart(value_col: str, label_col: str, title: str, tooltip_title: str):
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
                axis=alt.Axis(labels=False, ticks=False, grid=False, domain=False),
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
                alt.Tooltip(f"{value_col}:Q", title=tooltip_title, format=",.1f"),
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
        ).configure_view(strokeWidth=0, fill="transparent").configure_axis(domainColor="#CBD5E1", grid=False)

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.altair_chart(_bar_chart("GWP Mio", "GWP_LABEL", "GWP Trend & Projection", "IDR Mio"), width="stretch")
    with c2:
        st.altair_chart(_bar_chart("Loss Ratio %", "LR_LABEL", "Loss Ratio Trend & Projection", "%"), width="stretch")



def _ea_fragment_if_available(func):
    return st.fragment(func) if hasattr(st, "fragment") else func


@_ea_fragment_if_available
def render_detailed_data_fragment(
    df: pd.DataFrame,
    active_filters: dict,
    tanggal_pilihan: str,
) -> None:






    render_section_card_header("Detailed Data")

    tab_defs = [
        ("UW YEAR", "Portfolio Analysis - Detailed by UW Year", "UW YEAR"),
        ("INTERMEDIARY", "Portfolio Analysis - Detailed by INTERMEDIARY", "INTERMEDIARY"),
        ("INSURED NAME", "Portfolio Analysis - Detailed by INSURED NAME", "INSURED NAME"),
        ("TOB", "Portfolio Analysis - Detailed by TOB", "TOB"),
        ("LOB", "Portfolio Analysis - Detailed by LOB", "LOB"),
        ("BRANCH", "Portfolio Analysis - Detailed by BRANCH", "BRANCH"),
        ("PROVINCE", "Portfolio Analysis - Detailed by PROVINCE", "PROVINCE"),
        ("COVERAGE", "Portfolio Analysis - Detailed by COVERAGE", "COVERAGE"),
        ("MARKETING GROUP", "Portfolio Analysis - Detailed by MARKETING GROUP", "MARKETING GROUP"),
        ("PCKG DESC", "Portfolio Analysis - Detailed by PCKG DESC", "PCKG DESC"),
        ("TYPE", "Portfolio Analysis - Detailed by TYPE", "TYPE"),
        ("BRAND", "Portfolio Analysis - Detailed by BRAND", "BRAND"),
        ("SUB-TYPE", "Portfolio Analysis - Detailed by SUB-TYPE", "SUB-TYPE"),
        ("AGE", "Portfolio Analysis - Detailed by AGE", "AGE"),
        ("TSI RANGE", "Portfolio Analysis - Detailed by TSI RANGE", "TSI RANGE"),
    ]

    available_extra_dim_map = {label: col for label, _, col in tab_defs if col in df.columns}
    extra_key = "ea_detailed_table_extra_columns"
    extra_options = list(available_extra_dim_map.keys())
    if extra_key not in st.session_state:
        st.session_state[extra_key] = []
    _sync_multiselect_state(extra_key, extra_options)

    def _reset_ea_extra_columns():
        st.session_state[extra_key] = []

    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
    ctrl_col1, ctrl_col2 = st.columns([5.2, 1.1], gap="small")
    with ctrl_col2:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        st.button(
            "Reset",
            key="ea_reset_extra_columns_btn",
            width="stretch",
            on_click=_reset_ea_extra_columns,
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

    selected_extra_cols = [available_extra_dim_map[x] for x in selected_extra_labels if x in available_extra_dim_map]

    def build_group_cols(primary_col: str) -> list[str]:
        cols = [primary_col]
        for c in selected_extra_cols:
            if c != primary_col and c not in cols:
                cols.append(c)
        return [c for c in cols if c in df.columns]

    _inject_ea_detail_radio_css()
    tab_labels = [label for label, _, col in tab_defs if col in df.columns]
    active_detail_tab_key = "ea_active_detail_tab"
    if active_detail_tab_key not in st.session_state or st.session_state[active_detail_tab_key] not in tab_labels:
        st.session_state[active_detail_tab_key] = tab_labels[0]

    active_tab_label = st.radio(
        "Detailed view",
        options=tab_labels,
        key=active_detail_tab_key,
        horizontal=True,
        label_visibility="collapsed",
    )

    st.markdown('<div class="detail-tab-content-card">', unsafe_allow_html=True)

    def pivot_tab(group_cols: list[str], tab_name: str) -> None:
        group_cols = [c for c in group_cols if c in df.columns]
        if not group_cols:
            st.info("This breakdown is unavailable because the required column is not present in the Engineering dataset.")
            return

        pivot = cached_pivot(df, tuple(group_cols))
        if pivot is None or pivot.empty:
            st.info("No data available for this breakdown.")
            return

        safe_tab_name = (
            tab_name.replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_")
        )

        format_and_display(pivot, table_key=safe_tab_name)

        render_export_controls_fragment(
            safe_tab_name,
            tab_name,
            tuple(group_cols),
            df,
            active_filters,
            tanggal_pilihan,
        )

    active_config = next((cfg for cfg in tab_defs if cfg[0] == active_tab_label), tab_defs[0])
    _, tab_name, primary_col = active_config
    st.markdown(
        f"<div style='font-size:14px;font-weight:800;color:#003366;margin:4px 0 6px 0;'>{html.escape(tab_name)}</div>",
        unsafe_allow_html=True,
    )
    pivot_tab(build_group_cols(primary_col), tab_name)
    st.markdown("</div>", unsafe_allow_html=True)


ENGINEERING_WORKBOOKS = {'20 Februari 2026': 'EA260220.xlsx', '22 Mei 2026': 'SumEA260522.xlsx', '26 Juni 2026': 'EA260626.xlsx', '7 Agustus 2026': 'EA260807.xlsx', '11 September 2026': 'EA260911.xlsx', '23 Januari 2026': 'EA260123.xlsx'}


def _dashboard_body() -> None:
    st.markdown("""<style> ... (css sama seperti sebelumnya) ... </style>""", unsafe_allow_html=True)
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
    st.markdown(
        """
        <div class="hero">
          <h1>Super Engineering Dashboard</h1>
          <p>Portfolio-level view of loss, commission, and combined ratios across segments.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tanggal_opsi = ["23 Januari 2026", "20 Februari 2026", "22 Mei 2026", "26 Juni 2026", "7 Agustus 2026", "11 September 2026"]
    tanggal_pilihan = st.selectbox("Pilih tanggal:", tanggal_opsi, index=5)

    st.header(f"As at {tanggal_pilihan}")
    st.subheader("in IDR Mio")

    df = load_workbook(ENGINEERING_WORKBOOKS[tanggal_pilihan])

    st.sidebar.header("Filters")
    filter_cols = [
        "UW YEAR",
        "IS_FRONTING",
        "INTERMEDIARY",
        "INSURED NAME",
        "TOB",
        "LOB",
        "BRANCH",
        "PROVINCE",
        "COVERAGE",
        "MARKETING GROUP",
        "PCKG DESC",
        "TYPE",
        "BRAND",
        "SUB-TYPE",
        "AGE",
        "TSI RANGE",
        "IS_HE",
    ]

    active_filters: dict[str, dict] = {}
    filtered_df = df.copy()

    default_modes = {"IS_FRONTING": "Include Selected"}
    default_selected = {"IS_FRONTING": ["NON_FRONTING"]}

    for col in filter_cols:
        if col not in filtered_df.columns:
            continue

        mode_key = f"{col}_mode"
        sel_key = f"{col}_selected"

        if mode_key not in st.session_state:
            st.session_state[mode_key] = default_modes.get(col, "Include Selected")
        if sel_key not in st.session_state:
            st.session_state[sel_key] = default_selected.get(col, [])

        with st.sidebar.expander(f"{col}", expanded=False):
            mode = st.selectbox(
                "Mode & Selection",
                ["Include Selected", "Include All", "Exclude Selected", "Exclude All"],
                key=mode_key,
            )

            show_multiselect = mode in ["Include Selected", "Exclude Selected"]
            current_options = sorted(filtered_df[col].dropna().unique())

            if show_multiselect:
                _sync_multiselect_state(sel_key, current_options)
                selected_vals = st.multiselect("Choose items", current_options, key=sel_key)
            else:
                if st.session_state.get(sel_key):
                    st.session_state[sel_key] = []
                st.multiselect("Choose items", current_options, key=f"{sel_key}__disabled", disabled=True)
                selected_vals = []

            if mode.startswith("Include") and selected_vals:
                filtered_df = filtered_df[filtered_df[col].isin(selected_vals)]
            elif mode.startswith("Exclude") and selected_vals:
                filtered_df = filtered_df[~filtered_df[col].isin(selected_vals)]

            active_filters[col] = {"mode": mode, "values": list(selected_vals)}

    df = filtered_df

    if df.empty:
        st.warning("No data on this filter")
        return

    kpis = compute_kpis(df)
    render_kpi_cards(kpis)

    render_trend_projection_section(df)

    render_detailed_data_fragment(df, active_filters, tanggal_pilihan)








@_ea_fragment_if_available
def render_export_controls_fragment(
    safe_tab_name: str,
    tab_name: str,
    group_cols: tuple[str, ...],
    df_for_export: pd.DataFrame,
    active_filters: dict,
    tanggal_pilihan: str,
) -> None:





    pdf_prefix = f"export_pdf__{safe_tab_name}"
    xlsx_prefix = f"export_xlsx__{safe_tab_name}"

    pdf_signature = _compute_export_signature({
        "tab_name": tab_name,
        "group_cols": list(group_cols),
        "filters": active_filters,
        "as_of": tanggal_pilihan,
    })
    xlsx_signature = _compute_export_signature({
        "tab_name": tab_name,
        "group_cols": list(group_cols),
        "filters": active_filters,
        "as_of": tanggal_pilihan,
    })

    if st.session_state.get(f"{pdf_prefix}__sig") != pdf_signature:
        _clear_export_state(pdf_prefix)
    if st.session_state.get(f"{xlsx_prefix}__sig") != xlsx_signature:
        _clear_export_state(xlsx_prefix)

    prep_col1, prep_col2 = st.columns(2, gap="small")

    with prep_col1:
        if st.button("Prepare PDF", key=f"prepare_pdf__{safe_tab_name}", width="content"):
            try:
                with st.spinner("Preparing PDF..."):
                    pivot_for_pdf = cached_pivot(df_for_export, tuple(group_cols))
                    pdf_bytes = cached_export_pdf(pivot_for_pdf, tab_name, active_filters, tanggal_pilihan)
                st.session_state[f"{pdf_prefix}__bytes"] = pdf_bytes
                st.session_state[f"{pdf_prefix}__href"] = _make_data_uri(pdf_bytes, "application/pdf")
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
            st.caption("PDF ready. Regenerate jika filter berubah.")
        else:
            st.caption("Prepare PDF dulu sebelum download.")

    with prep_col2:
        if st.button("Prepare Excel", key=f"prepare_xlsx__{safe_tab_name}", width="content"):
            try:
                with st.spinner("Preparing Excel..."):
                    pivot_for_excel = cached_pivot(df_for_export, tuple(group_cols))
                    xlsx_bytes = cached_export_excel(pivot_for_excel, tab_name, active_filters, tanggal_pilihan)
                st.session_state[f"{xlsx_prefix}__bytes"] = xlsx_bytes
                st.session_state[f"{xlsx_prefix}__href"] = _make_data_uri(
                    xlsx_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
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
            st.caption("Excel ready. Regenerate jika filter berubah.")
        else:
            st.caption("Prepare Excel dulu sebelum download.")


def dashboard() -> None:





    _dashboard_body()

def risk_main2() -> None:
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = True

    if not st.session_state["logged_in"]:
        st.write("Please login from main SuperApp.")
    else:
        try:
            _dashboard_body()
        except Exception as e:
            _render_safe_error(e)
        if st.sidebar.button("Logout", key="logout_btn"):
            st.session_state["logged_in"] = False
            st.rerun()




def preload_workbooks():
    for path in ENGINEERING_WORKBOOKS.values():
        load_workbook(path)


if __name__ == "__main__":
    risk_main2()
