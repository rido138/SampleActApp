import io
import html
import base64
import hashlib
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import folium
from streamlit_folium import st_folium


# =========================
# UI HELPERS
# =========================
def _inject_theme_css() -> None:
    st.markdown(
        """
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
          .hero h1{
            margin:0 0 8px 0!important;
            color:white!important;
            font-size:34px;
            font-weight:820;
            letter-spacing:-0.02em;
          }
          .hero p{
            margin:0;
            color:rgba(255,255,255,0.90);
            font-size:14.5px;
            line-height:1.55;
          }

          .section-card-header{
            margin: 14px 0 8px 0;
            padding: 12px 15px;
            border-radius: 16px;
            background: #F8FAFC;
            border: 1px solid rgba(0,51,102,0.10);
            box-shadow: 0 8px 22px rgba(15,23,42,0.035);
          }
          .section-card-title{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size:18px;
            font-weight:800;
            color:#003366;
            line-height:1.15;
            letter-spacing:-0.01em;
          }
          .section-card-subtitle{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size:12.5px;
            color:#64748B;
            line-height:1.25;
            margin-top:3px;
          }

          .kpi-card.kpi-compact3{
            box-sizing:border-box!important;
            height:122px!important;
            padding:14px 18px!important;
            border-radius:22px!important;
            display:flex!important;
            flex-direction:column!important;
            justify-content:flex-start!important;
            align-items:flex-start!important;
            text-align:left!important;
            gap:6px!important;
            overflow:hidden!important;
            background:rgba(255,255,255,0.94);
            border:1px solid rgba(0,51,102,0.10);
            box-shadow:0 10px 26px rgba(15,23,42,0.06);
          }
          .kpi-card.kpi-compact3 h4{
            margin:0!important;
            font-size:13px!important;
            line-height:1.15!important;
            font-weight:650!important;
            color:#475569!important;
            white-space:nowrap!important;
            overflow:hidden!important;
            text-overflow:ellipsis!important;
            max-width:100%!important;
          }
          .kpi-card.kpi-compact3 h2{
            margin:0!important;
            font-size:32px!important;
            line-height:1!important;
            font-weight:800!important;
            color:#003366!important;
            white-space:nowrap!important;
            overflow:hidden!important;
            text-overflow:ellipsis!important;
            max-width:100%!important;
          }
          .kpi-card.kpi-compact3.kpi-danger{
            background:linear-gradient(135deg,#7a0015 0%,#b00020 100%)!important;
            box-shadow:0 14px 34px rgba(176,0,32,0.22)!important;
          }
          .kpi-card.kpi-compact3.kpi-danger h4,
          .kpi-card.kpi-compact3.kpi-danger h2{color:white!important;}

          .map-card, .detail-card{
            background:#FFFFFF;
            border:1px solid rgba(0,51,102,0.12);
            border-radius:18px;
            padding:16px 16px 18px 16px;
            box-shadow:0 10px 25px rgba(15,23,42,0.045);
            margin-top:8px;
            margin-bottom:14px;
          }
          .map-legend{
            display:flex;
            flex-wrap:wrap;
            gap:10px;
            margin:6px 0 12px 0;
            color:#475569;
            font-size:12.5px;
            font-weight:650;
          }
          .legend-pill{
            display:inline-flex;
            align-items:center;
            gap:7px;
            padding:6px 10px;
            border-radius:999px;
            border:1px solid rgba(0,51,102,0.12);
            background:#F8FAFC;
          }
          .legend-dot{width:9px;height:9px;border-radius:999px;display:inline-block;}

          .direct-download-btn{
            display:inline-block;
            width:auto;
            box-sizing:border-box;
            text-align:left;
            padding:0;
            border-radius:0;
            background:transparent;
            color:#003366!important;
            border:none;
            text-decoration:underline!important;
            text-underline-offset:3px;
            font-weight:700;
            font-size:13px;
          }
          .direct-download-btn:hover{
            color:#E39A5B!important;
            background:transparent;
            border:none;
          }

          div[data-testid="stSidebar"] h1,
          div[data-testid="stSidebar"] h2,
          div[data-testid="stSidebar"] h3{
            color:#003366!important;
          }

          .small-muted{
            font-size:12.5px;
            color:#64748B;
            line-height:1.35;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_section_card_header(title: str, subtitle: str = "") -> None:
    subtitle_html = f'<div class="section-card-subtitle">{html.escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="section-card-header">
          <div class="section-card-title">{html.escape(title)}</div>
          {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _format_mio(x, digits: int = 0) -> str:
    if pd.isna(x):
        return "-"
    return f"{x / 1_000_000:,.{digits}f}".replace(",", ".")


def _format_pct_ratio(x) -> str:
    if pd.isna(x):
        return "-"
    return f"{x * 100:.0f}%"


def render_kpi_cards(total_policy, total_gwp, total_claim, total_tsi, loss_ratio_total) -> None:
    def kpi_box(title: str, value: str, extra_cls: str = ""):
        st.markdown(
            f"""
            <div class="kpi-card kpi-compact3 {extra_cls}">
              <h4>{html.escape(title)}</h4>
              <h2>{html.escape(value)}</h2>
            </div>
            """,
            unsafe_allow_html=True,
        )

    cols = st.columns(5)
    with cols[0]:
        kpi_box("Total Policy", f"{int(total_policy):,}".replace(",", "."))
    with cols[1]:
        kpi_box("Total GWP (Mio)", _format_mio(total_gwp))
    with cols[2]:
        kpi_box("Gross Claim (Mio)", _format_mio(total_claim))
    with cols[3]:
        kpi_box("OUR TSI (Mio)", _format_mio(total_tsi))
    with cols[4]:
        kpi_box("Loss Ratio", _format_pct_ratio(loss_ratio_total), "kpi-danger" if loss_ratio_total > 1 else "")


@st.cache_data(ttl=3600, show_spinner=False)
def load_data() -> pd.DataFrame:
    df = pd.read_parquet("Spasial FR - 12 Juni 2026.parquet")
    df.columns = df.columns.str.strip().str.upper()
    if "GEP_AMT" in df.columns and "GROSS CLAIM" in df.columns:
        gep = pd.to_numeric(df["GEP_AMT"], errors="coerce").fillna(0.0)
        gross_claim = pd.to_numeric(df["GROSS CLAIM"], errors="coerce").fillna(0.0)
        df["LOSS_RATIO"] = np.where(gep != 0, gross_claim / gep, 0.0)
    else:
        df["LOSS_RATIO"] = 0.0
    return df


@st.cache_data(ttl=900, show_spinner=False, max_entries=8)
def convert_to_excel(df_export: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name="Detail")
    return output.getvalue()




def _render_html_block(html_content: str, height: int = 300, scrolling: bool = False) -> None:
    """Render custom HTML in an iframe so client-side table sorting works without Streamlit rerun."""
    components.html(html_content, height=height, scrolling=scrolling)

def _make_data_uri(data_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(data_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _render_direct_download_link(label: str, href: str, file_name: str) -> None:
    st.markdown(
        f'<a class="direct-download-btn" download="{html.escape(file_name, quote=True)}" href="{href}">{html.escape(label)}</a>',
        unsafe_allow_html=True,
    )


def _selectbox_filter(label: str, options, key: str):
    options = [v for v in options if pd.notna(v)]
    try:
        options = sorted(options)
    except Exception:
        options = sorted([str(v) for v in options])
    return st.sidebar.selectbox(label, ["All"] + options, key=key)


def _filter_df(df: pd.DataFrame, filters: dict, min_premium: float, use_lr_filter: bool, max_lr: float) -> pd.DataFrame:
    out = df.copy()
    for col, val in filters.items():
        if col not in out.columns or val == "All":
            continue
        out = out[out[col] == val]

    if "GWP_AMT" in out.columns:
        out = out[pd.to_numeric(out["GWP_AMT"], errors="coerce").fillna(0) >= float(min_premium)]

    if use_lr_filter and "LOSS_RATIO" in out.columns:
        out = out[pd.to_numeric(out["LOSS_RATIO"], errors="coerce").fillna(0) <= float(max_lr)]

    return out


def _build_grouped_points(df_filtered: pd.DataFrame) -> pd.DataFrame:
    required = {"LOCATION_LAT", "LOCATION_LNG"}
    if not required.issubset(df_filtered.columns):
        return pd.DataFrame()

    work = df_filtered.dropna(subset=["LOCATION_LAT", "LOCATION_LNG"]).copy()
    if work.empty:
        return pd.DataFrame()

    agg_dict = {
        "GWP_AMT": "sum",
        "GROSS CLAIM": "sum",
        "LOSS_RATIO": "mean",
        "POLICY_NO": "count",
    }
    if "OUR TSI" in work.columns:
        agg_dict["OUR TSI"] = "sum"

    return (
        work.groupby(["LOCATION_LAT", "LOCATION_LNG"], dropna=False)
        .agg(agg_dict)
        .reset_index()
        .rename(columns={"POLICY_NO": "JUMLAH_POLIS"})
    )


def _render_map(grouped: pd.DataFrame):
    if grouped.empty:
        st.info("Tidak ada koordinat yang bisa ditampilkan pada filter ini.")
        return None

    center_lat = float(pd.to_numeric(grouped["LOCATION_LAT"], errors="coerce").mean())
    center_lng = float(pd.to_numeric(grouped["LOCATION_LNG"], errors="coerce").mean())

    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=6,
        tiles="CartoDB positron",
        control_scale=True,
    )

    for _, row in grouped.iterrows():
        loss_ratio = float(row.get("LOSS_RATIO", 0.0) or 0.0)
        gross_claim = float(row.get("GROSS CLAIM", 0.0) or 0.0)
        gwp = float(row.get("GWP_AMT", 0.0) or 0.0)

        color = "#138D75"
        if gross_claim > gwp and gwp > 0:
            color = "#B00020"
        elif loss_ratio > 1:
            color = "#E39A5B"

        radius = min(13, max(5, np.log1p(max(gwp, 0)) / 2.4))

        popup_lines = [
            f"<b>Jumlah Polis:</b> {int(row.get('JUMLAH_POLIS', 0)):,}".replace(",", "."),
            f"<b>GWP (Mio):</b> {_format_mio(row.get('GWP_AMT', 0))}",
            f"<b>Gross Claim (Mio):</b> {_format_mio(row.get('GROSS CLAIM', 0))}",
        ]
        if "OUR TSI" in grouped.columns:
            popup_lines.append(f"<b>OUR TSI (Mio):</b> {_format_mio(row.get('OUR TSI', 0))}")
        popup_lines.append(f"<b>Loss Ratio:</b> {loss_ratio * 100:.0f}%")

        folium.CircleMarker(
            location=[float(row["LOCATION_LAT"]), float(row["LOCATION_LNG"])],
            radius=radius,
            color=color,
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.72,
            popup=folium.Popup("<br>".join(popup_lines), max_width=280),
        ).add_to(m)

    return st_folium(m, width=1100, height=520)


def _render_detail_table(detail_df: pd.DataFrame) -> None:
    """Risk Profile-style formatted policy table for selected map point."""
    display_df = detail_df.copy()

    money_source_cols = ["GEP_AMT", "GWP_AMT", "GROSS CLAIM", "OUR TSI"]
    ratio_source_cols = ["LOSS_RATIO"]
    numeric_source_cols = ["LOCATION_LAT", "LOCATION_LNG"]

    rename_map = {}
    for col in money_source_cols:
        if col in display_df.columns:
            display_df[col] = pd.to_numeric(display_df[col], errors="coerce") / 1_000_000
            rename_map[col] = f"{col} (MIO)"

    if "LOSS_RATIO" in display_df.columns:
        display_df["LOSS_RATIO"] = pd.to_numeric(display_df["LOSS_RATIO"], errors="coerce") * 100
        rename_map["LOSS_RATIO"] = "LOSS RATIO (%)"

    display_df = display_df.rename(columns=rename_map)

    preferred_cols = [
        "POLICY_NO", "ACCOUNT_NAME", "INSURED_NAME", "PROVINCE", "DESC", "LOB", "IS_ACTIVE",
        "GWP_AMT (MIO)", "GEP_AMT (MIO)", "GROSS CLAIM (MIO)", "OUR TSI (MIO)", "LOSS RATIO (%)",
        "LOCATION_LAT", "LOCATION_LNG",
    ]
    ordered = [c for c in preferred_cols if c in display_df.columns]
    remaining = [c for c in display_df.columns if c not in ordered]
    display_df = display_df[ordered + remaining]
    raw_df = display_df.copy()

    money_cols = [c for c in ["GWP_AMT (MIO)", "GEP_AMT (MIO)", "GROSS CLAIM (MIO)", "OUR TSI (MIO)"] if c in display_df.columns]
    ratio_cols = [c for c in ["LOSS RATIO (%)"] if c in display_df.columns]
    numeric_cols = money_cols + ratio_cols + [c for c in numeric_source_cols if c in display_df.columns]

    def fmt_money(x):
        return "" if pd.isna(x) else f"{int(round(float(x))):,}".replace(",", ".")

    def fmt_pct(x):
        return "" if pd.isna(x) else f"{round(float(x)):.0f}%"

    def fmt_coord(x):
        return "" if pd.isna(x) else f"{float(x):.5f}"

    for col in display_df.columns:
        if col in money_cols:
            display_df[col] = display_df[col].apply(fmt_money)
        elif col in ratio_cols:
            display_df[col] = display_df[col].apply(fmt_pct)
        elif col in ["LOCATION_LAT", "LOCATION_LNG"]:
            display_df[col] = pd.to_numeric(display_df[col], errors="coerce").apply(fmt_coord)
        else:
            display_df[col] = display_df[col].fillna("").astype(str)

    def width_for(col: str) -> int:
        if col in ["POLICY_NO"]:
            return 165
        if col in ["ACCOUNT_NAME", "INSURED_NAME"]:
            return 260
        if col in ["DESC", "PROVINCE"]:
            return 190
        if col in ["LOB", "IS_ACTIVE"]:
            return 130
        if col in money_cols:
            return 135
        if col in ratio_cols:
            return 120
        if col in ["LOCATION_LAT", "LOCATION_LNG"]:
            return 120
        return 150

    col_widths = {col: width_for(str(col)) for col in display_df.columns}
    min_table_width = sum(col_widths.values())
    table_height = max(260, min(500, 98 + 34 * len(display_df)))
    table_dom_id = "sp_detail_" + hashlib.sha1(("|".join(map(str, display_df.columns)) + str(len(display_df))).encode("utf-8")).hexdigest()[:10]

    css_colgroup = "".join([f"<col style='width:{col_widths[c]}px; min-width:{col_widths[c]}px;'>" for c in display_df.columns])

    sticky_cols = [c for c in ["POLICY_NO", "ACCOUNT_NAME", "INSURED_NAME"] if c in display_df.columns]
    sticky_left = {}
    running_left = 0
    for c in display_df.columns:
        if c in sticky_cols:
            sticky_left[c] = running_left
            running_left += col_widths[c]
        else:
            break

    col_alias = {
        "POLICY_NO": "POLICY NO",
        "ACCOUNT_NAME": "ACCOUNT NAME",
        "INSURED_NAME": "INSURED NAME",
        "GWP_AMT (MIO)": "GWP<br><span>IDR Mio</span>",
        "GEP_AMT (MIO)": "GEP<br><span>IDR Mio</span>",
        "GROSS CLAIM (MIO)": "GROSS CLAIM<br><span>IDR Mio</span>",
        "OUR TSI (MIO)": "OUR TSI<br><span>IDR Mio</span>",
        "LOSS RATIO (%)": "LOSS RATIO",
        "LOCATION_LAT": "LAT",
        "LOCATION_LNG": "LNG",
    }

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

    body_rows = []
    for r in range(len(display_df)):
        row_cells = []
        for col in display_df.columns:
            raw_val = raw_df.iloc[r][col]
            sort_val_num = pd.to_numeric(pd.Series([raw_val]), errors="coerce").iloc[0]
            if pd.notna(sort_val_num):
                sort_attr = str(float(sort_val_num))
                sort_type = "num"
            else:
                sort_attr = html.escape(str(raw_val if pd.notna(raw_val) else "").lower())
                sort_type = "text"

            classes = ["num-cell" if col in numeric_cols else "text-cell"]
            style = ""
            if col in sticky_left:
                classes.append("sticky-col")
                style = f"left:{sticky_left[col]}px;"
            if col == "LOSS RATIO (%)" and pd.notna(sort_val_num) and sort_val_num > 100:
                classes.append("loss-danger")

            val = html.escape(str(display_df.iloc[r][col]))
            style_attr = f" style='{style}'" if style else ""
            row_cells.append(
                f"<td class='{' '.join(classes)}'{style_attr} data-sort='{sort_attr}' data-sort-type='{sort_type}'>{val}</td>"
            )
        body_rows.append(f"<tr>{''.join(row_cells)}</tr>")

    html_table = f"""
    <style>
      html, body {{ margin:0; padding:0; overflow:hidden; background:transparent; }}
      .sp-table-controls {{ display:flex; gap:10px; align-items:center; margin:0 0 10px 0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; flex-wrap:wrap; }}
      .sp-table-controls label {{ font-size:12px; font-weight:650; color:#475569; }}
      .sp-table-controls select, .sp-table-controls button {{ height:34px; border:1px solid rgba(0,51,102,0.16); border-radius:10px; background:#FFFFFF; color:#1F2937; font-size:12px; padding:0 10px; outline:none; }}
      .sp-table-controls select:focus {{ border-color:rgba(0,51,102,0.45); box-shadow:0 0 0 3px rgba(0,51,102,0.08); }}
      .sp-table-controls button {{ cursor:pointer; font-weight:650; color:#003366; }}
      .sp-table-wrap {{ width:100%; max-height:{table_height}px; overflow:auto; border:1px solid rgba(0,51,102,0.12); border-radius:16px; background:#ffffff; box-shadow:0 10px 28px rgba(15,23,42,0.06); }}
      .sp-table {{ border-collapse:separate; border-spacing:0; table-layout:fixed; width:{min_table_width}px; min-width:{min_table_width}px; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Arial,sans-serif; color:#334155; }}
      .sp-table thead th {{ position:sticky; top:0; z-index:30; background:#003366; color:#ffffff; text-align:center!important; vertical-align:middle; font-size:10.8px; line-height:1.18; font-weight:760; height:46px; padding:8px 8px; border-right:1px solid rgba(255,255,255,0.18); border-bottom:1px solid rgba(0,0,0,0.10); white-space:normal; box-sizing:border-box; }}
      .sp-table thead th span {{ display:block; margin-top:2px; font-size:8.8px; line-height:1.0; font-weight:500; opacity:0.78; }}
      .sp-table tbody td {{ font-size:11.2px; line-height:1.28; height:34px; padding:8px 10px; border-right:1px solid rgba(15,23,42,0.045); border-bottom:1px solid rgba(15,23,42,0.055); background:#ffffff; color:#334155; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; box-sizing:border-box; font-weight:600; }}
      .sp-table tbody tr:nth-child(even) td {{ background:#F8FAFC; }}
      .sp-table tbody tr:hover td {{ background:#EEF6FF; }}
      .sp-table .text-cell {{ text-align:left; color:#1E3A5F; }}
      .sp-table .num-cell {{ text-align:right; font-variant-numeric:tabular-nums; }}
      .sp-table .sticky-col {{ position:sticky; z-index:20; box-shadow:2px 0 0 rgba(0,51,102,0.08); }}
      .sp-table thead th.sticky-col {{ z-index:40; background:#002B57; }}
      .sp-table tbody td.sticky-col {{ background:#ffffff; }}
      .sp-table tbody tr:nth-child(even) td.sticky-col {{ background:#F8FAFC; }}
      .sp-table tbody tr:hover td.sticky-col {{ background:#EEF6FF; }}
      .sp-table tbody td.loss-danger {{ background:#FFE7E7!important; color:#9F1239; font-weight:780; }}
    </style>
    <div class="sp-table-controls">
      <label for="sort_by_{table_dom_id}">Sort by</label>
      <select id="sort_by_{table_dom_id}">{sort_options_html}</select>
      <select id="sort_order_{table_dom_id}"><option value="desc">Descending</option><option value="asc">Ascending</option></select>
      <button type="button" id="reset_sort_{table_dom_id}">Reset</button>
    </div>
    <div class="sp-table-wrap">
      <table class="sp-table" id="{table_dom_id}">
        <colgroup>{css_colgroup}</colgroup>
        <thead><tr>{''.join(header_cells)}</tr></thead>
        <tbody>{''.join(body_rows)}</tbody>
      </table>
    </div>
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
    _render_html_block(html_table, height=table_height + 86)

def spasial():
    _inject_theme_css()
    df = load_data()

    st.markdown(
        """
        <div class="hero">
          <h1>Geospatial Property Dashboard</h1>
          <p>Portfolio map view of property exposure, premium, claims, and loss ratio by location.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("<h3>Filters</h3>", unsafe_allow_html=True)

    filters = {}
    filter_specs = [
        ("UW_YEAR", "UW Year", "spatial_filter_uw_year"),
        ("PROVINCE", "Province", "spatial_filter_province"),
        ("ACCOUNT_NAME", "Account", "spatial_filter_account"),
        ("LOB", "LOB", "spatial_filter_lob"),
        ("DESC", "Description", "spatial_filter_desc"),
        ("IS_ACTIVE", "Active Status", "spatial_filter_active"),
    ]

    for col, label, key in filter_specs:
        if col in df.columns:
            filters[col] = _selectbox_filter(label, df[col].dropna().unique().tolist(), key)
        elif col == "LOB":
            st.sidebar.caption("Kolom LOB tidak ditemukan di data")

    st.sidebar.markdown("---")
    min_premium = st.sidebar.number_input("Min GWP", min_value=0.0, value=0.0, step=1_000_000.0, key="spatial_min_gwp")
    use_lr_filter = st.sidebar.checkbox("Aktifkan Filter Loss Ratio", value=True, key="spatial_use_lr")
    max_lr = 5.0
    if use_lr_filter:
        max_lr = st.sidebar.number_input("Max Loss Ratio", min_value=0.0, value=5.0, step=0.1, key="spatial_max_lr")
    else:
        st.sidebar.caption("Loss Ratio filter tidak aktif")

    if "selected_point" not in st.session_state:
        st.session_state.selected_point = None

    if st.sidebar.button("Reset Selection", key="spatial_reset_selection", width="stretch"):
        st.session_state.selected_point = None

    df_filtered = _filter_df(df, filters, min_premium, use_lr_filter, max_lr)

    if df_filtered.empty:
        st.warning("Tidak ada data sesuai filter")
        return

    total_policy = df_filtered["POLICY_NO"].nunique() if "POLICY_NO" in df_filtered.columns else len(df_filtered)
    total_gwp = pd.to_numeric(df_filtered.get("GWP_AMT", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    total_claim = pd.to_numeric(df_filtered.get("GROSS CLAIM", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    total_our_tsi = pd.to_numeric(df_filtered.get("OUR TSI", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    loss_ratio_total = total_claim / total_gwp if total_gwp else 0.0

    render_section_card_header("Key Performance Indicators")
    render_kpi_cards(total_policy, total_gwp, total_claim, total_our_tsi, loss_ratio_total)

    grouped = _build_grouped_points(df_filtered)

    render_section_card_header("Geospatial Map", "Click a location point to inspect policy details.")
    st.markdown(
        """
        <div class="map-legend">
          <span class="legend-pill"><span class="legend-dot" style="background:#138D75;"></span>Healthy / normal</span>
          <span class="legend-pill"><span class="legend-dot" style="background:#E39A5B;"></span>Loss Ratio &gt; 100%</span>
          <span class="legend-pill"><span class="legend-dot" style="background:#B00020;"></span>Claim &gt; GWP</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    map_data = _render_map(grouped)

    if map_data and map_data.get("last_object_clicked"):
        st.session_state.selected_point = (
            map_data["last_object_clicked"]["lat"],
            map_data["last_object_clicked"]["lng"],
        )

    render_section_card_header("Policy Detail", "Select a point on the map to show policies at that location.")

    if st.session_state.selected_point is not None:
        selected_lat, selected_lon = st.session_state.selected_point
        tolerance = 0.0001
        detail_df = df_filtered[
            (abs(pd.to_numeric(df_filtered["LOCATION_LAT"], errors="coerce") - selected_lat) < tolerance)
            & (abs(pd.to_numeric(df_filtered["LOCATION_LNG"], errors="coerce") - selected_lon) < tolerance)
        ].copy()

        if not detail_df.empty:
            st.markdown(
                f"<div class='small-muted'>{len(detail_df):,} policy rows found at selected location.</div>".replace(",", "."),
                unsafe_allow_html=True,
            )
            _render_detail_table(detail_df)
            excel_data = convert_to_excel(detail_df)
            excel_href = _make_data_uri(
                excel_data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            _render_direct_download_link("Download Excel", excel_href, "detail_polis.xlsx")
        else:
            st.info("Tidak ada data di titik ini. Kemungkinan data sudah terfilter.")
    else:
        st.info("Klik titik di map untuk lihat detail polis.")


if __name__ == "__main__":
    spasial()
