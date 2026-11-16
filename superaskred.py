import base64
import hashlib
import html
import io

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

# =====================================================
# PAGE CONFIG
# =====================================================
# st.set_page_config(page_title="Credit Insurance Dashboard", page_icon="📊", layout="wide")


# =====================================================
# THEME / CSS
# =====================================================
def inject_superaskred_theme() -> None:
    """Premium theme aligned with Risk Profile style."""
    st.markdown(
        """
        <style>
          :root{
            --askred-blue:#003366;
            --askred-blue-2:#1F5A91;
            --askred-gold:#E39A5B;
            --askred-text:#1E293B;
            --askred-muted:#64748B;
            --askred-line:rgba(0,51,102,0.12);
            --askred-soft:#F8FAFC;
          }

          .askred-hero{
            padding:18px 22px;
            border-radius:20px;
            background:linear-gradient(135deg,#003366 0%,#1F5A91 100%);
            color:#FFFFFF;
            margin:4px 0 14px 0;
            box-shadow:0 16px 36px rgba(0,51,102,0.16);
            border:1px solid rgba(255,255,255,0.14);
          }
          .askred-hero h1{
            margin:0;
            font-size:24px;
            line-height:1.15;
            font-weight:820;
            letter-spacing:-0.02em;
          }
          .askred-hero p{
            margin:6px 0 0 0;
            font-size:13.5px;
            line-height:1.35;
            opacity:0.86;
            font-weight:520;
          }

          .askred-section-card-header{
            margin:16px 0 10px 0;
            padding:12px 15px;
            border-radius:16px;
            background:#F8FAFC;
            border:1px solid rgba(0,51,102,0.10);
            box-shadow:0 8px 22px rgba(15,23,42,0.035);
          }
          .askred-section-title{
            font-size:18px;
            font-weight:800;
            line-height:1.15;
            color:#003366;
            letter-spacing:-0.01em;
          }
          .askred-section-subtitle{
            font-size:12.5px;
            color:#64748B;
            line-height:1.25;
            margin-top:3px;
          }

          .askred-kpi-card{
            box-sizing:border-box!important;
            height:112px!important;
            padding:14px 16px!important;
            border-radius:22px!important;
            background:linear-gradient(180deg,#FFFFFF 0%,#F8FAFC 100%);
            border:1px solid rgba(0,51,102,0.12);
            box-shadow:0 10px 26px rgba(15,23,42,0.06);
            display:flex!important;
            flex-direction:column!important;
            justify-content:flex-start!important;
            align-items:flex-start!important;
            gap:5px!important;
            overflow:hidden!important;
          }
          .askred-kpi-card h4{
            margin:0!important;
            font-size:12.3px!important;
            line-height:1.16!important;
            font-weight:700!important;
            color:#64748B!important;
            white-space:nowrap!important;
            overflow:hidden!important;
            text-overflow:ellipsis!important;
            max-width:100%!important;
          }
          .askred-kpi-card h2{
            margin:0!important;
            font-size:29px!important;
            line-height:1.02!important;
            font-weight:850!important;
            color:#003366!important;
            white-space:nowrap!important;
            overflow:hidden!important;
            text-overflow:ellipsis!important;
            max-width:100%!important;
            font-variant-numeric:tabular-nums;
          }
          .askred-kpi-card .hint{
            margin-top:auto;
            font-size:11px;
            color:#94A3B8;
            font-weight:650;
          }
          @keyframes askredBlink{
            0%,100%{filter:brightness(1);box-shadow:0 10px 26px rgba(15,23,42,0.06),0 0 0 1px rgba(190,0,40,0.10) inset;}
            50%{filter:brightness(1.05);box-shadow:0 16px 38px rgba(190,0,40,0.18),0 0 0 2px rgba(220,0,50,0.35) inset;}
          }
          .askred-kpi-danger{
            animation:askredBlink 1.4s ease-in-out infinite!important;
          }
          .askred-kpi-danger h2{color:#B00020!important;}

          .askred-chart-card{
            background:#FFFFFF;
            border:1px solid rgba(0,51,102,0.10);
            border-radius:18px;
            padding:12px 14px 8px 14px;
            box-shadow:0 10px 25px rgba(15,23,42,0.045);
            margin-bottom:12px;
          }

          @keyframes askredToastInOut{
            0%{transform:translateX(18px);opacity:0;}
            10%{transform:translateX(0);opacity:1;}
            86%{transform:translateX(0);opacity:1;}
            100%{transform:translateX(18px);opacity:0;}
          }
          .askred-toast{
            position:fixed;
            top:84px;
            right:22px;
            z-index:9999;
            width:min(440px,calc(100vw - 44px));
            padding:14px 16px;
            border-radius:14px;
            background:rgba(176,0,32,0.96);
            color:#FFFFFF;
            box-shadow:0 18px 40px rgba(0,0,0,0.22);
            border:1px solid rgba(255,255,255,0.18);
            display:flex;
            gap:10px;
            align-items:flex-start;
            animation:askredToastInOut 6s ease-in-out forwards;
          }
          .askred-toast .icon{
            width:22px;height:22px;border-radius:999px;
            background:rgba(255,255,255,0.18);
            display:flex;align-items:center;justify-content:center;
            font-weight:900;flex:0 0 auto;margin-top:1px;
          }
          .askred-toast .txt{
            font-size:13.5px;line-height:1.25;font-weight:650;
          }

          .askred-sidebar-note{
            padding:10px 12px;
            border-radius:14px;
            background:#F8FAFC;
            border:1px solid rgba(0,51,102,0.10);
            color:#64748B;
            font-size:12px;
            line-height:1.35;
            margin-bottom:10px;
          }

          .askred-filter-badge{
            display:inline-flex;
            align-items:center;
            gap:6px;
            border:1px solid rgba(0,51,102,0.14);
            background:#F8FAFC;
            color:#003366;
            border-radius:999px;
            padding:6px 10px;
            font-size:12px;
            font-weight:760;
            margin:2px 6px 2px 0;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =====================================================
# DATA LOADER / HELPERS
# =====================================================
@st.cache_data(show_spinner=False, ttl=900, max_entries=4)
def load_credit_data(path: str = "askred 260306.parquet") -> pd.DataFrame:
    return pd.read_parquet(path)


@st.cache_data(show_spinner=False, ttl=900, max_entries=64)
def get_unique_options(df: pd.DataFrame, col: str) -> list:
    if col not in df.columns:
        return []
    return sorted(df[col].dropna().astype(str).unique())


@st.cache_data(show_spinner=False, ttl=900, max_entries=64)
def make_filtered_df(
    df: pd.DataFrame,
    account_selected: tuple,
    insured_selected: tuple,
    policy_selected: tuple,
) -> pd.DataFrame:
    out = df.copy()
    for col, selected in [
        ("ACCOUNT_NAME", account_selected),
        ("INSURED_NAME", insured_selected),
        ("POLICY_NO", policy_selected),
    ]:
        if selected and col in out.columns:
            out = out[out[col].astype(str).isin(selected)]
    return out


@st.cache_data(show_spinner=False, ttl=900, max_entries=64)
def build_top_insured_chart_df(df: pd.DataFrame, top_n: int = 12) -> pd.DataFrame:
    if df is None or df.empty or "INSURED_NAME" not in df.columns:
        return pd.DataFrame()

    work = df.copy()
    work["INSURED_NAME"] = work["INSURED_NAME"].fillna("(Blank)").astype(str)
    for col in ["GWP_AMT", "GROSS_CLAIMS", "STOP_LOSS"]:
        if col not in work.columns:
            work[col] = 0.0
        work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)

    grouped = (
        work.groupby("INSURED_NAME", as_index=False)[["GWP_AMT", "GROSS_CLAIMS", "STOP_LOSS"]]
        .sum()
        .sort_values("GWP_AMT", ascending=False, kind="stable")
        .head(top_n)
    )
    grouped[["GWP_AMT", "GROSS_CLAIMS", "STOP_LOSS"]] = grouped[["GWP_AMT", "GROSS_CLAIMS", "STOP_LOSS"]] / 1_000_000
    grouped["INSURED_LABEL"] = grouped["INSURED_NAME"].apply(lambda x: x if len(x) <= 36 else x[:33].rstrip() + "...")
    return grouped


def fmt_mio(x) -> str:
    try:
        return f"{float(x):,.0f}".replace(",", ".")
    except Exception:
        return "-"


def fmt_pct(x) -> str:
    try:
        return f"{float(x):.0%}"
    except Exception:
        return "-"


def section_header(title: str, subtitle: str = "") -> None:
    subtitle_html = f'<div class="askred-section-subtitle">{html.escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="askred-section-card-header">
          <div class="askred-section-title">{html.escape(title)}</div>
          {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_card(title: str, value: str, hint: str = "", danger: bool = False) -> None:
    danger_cls = "askred-kpi-danger" if danger else ""
    hint_html = f'<div class="hint">{html.escape(hint)}</div>' if hint else ""
    st.markdown(
        f"""
        <div class="askred-kpi-card {danger_cls}">
          <h4>{html.escape(title)}</h4>
          <h2>{html.escape(value)}</h2>
          {hint_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_loss_ratio_toast(loss_ratio: float) -> None:
    if loss_ratio <= 1:
        return
    key = f"askred_lr_toast_{int(round(loss_ratio * 100))}"
    if st.session_state.get(key):
        return
    st.session_state[key] = True
    st.markdown(
        """
        <div class="askred-toast">
          <div class="icon">!</div>
          <div class="txt">Portfolio ini mencatatkan Loss Ratio di atas 100%.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_filter_badges(account_selected, insured_selected, policy_selected) -> None:
    items = [
        ("Account", len(account_selected)),
        ("Insured", len(insured_selected)),
        ("Policy", len(policy_selected)),
    ]
    badges = []
    for label, count in items:
        text = "All" if count == 0 else f"{count} selected"
        badges.append(f'<span class="askred-filter-badge">{html.escape(label)}: {html.escape(text)}</span>')
    st.markdown("".join(badges), unsafe_allow_html=True)


def make_bar_chart(chart_df: pd.DataFrame):
    plot_df = chart_df.melt(
        id_vars=["INSURED_NAME", "INSURED_LABEL"],
        value_vars=["GWP_AMT", "GROSS_CLAIMS", "STOP_LOSS"],
        var_name="Metric",
        value_name="Amount Mio",
    )
    metric_map = {
        "GWP_AMT": "GWP",
        "GROSS_CLAIMS": "Gross Claims",
        "STOP_LOSS": "Stop Loss",
    }
    plot_df["Metric"] = plot_df["Metric"].map(metric_map).fillna(plot_df["Metric"])

    fig = px.bar(
        plot_df,
        y="INSURED_LABEL",
        x="Amount Mio",
        color="Metric",
        barmode="group",
        orientation="h",
        text="Amount Mio",
        color_discrete_map={
            "GWP": "#003366",
            "Gross Claims": "#E39A5B",
            "Stop Loss": "#7A96B8",
        },
        hover_data={"INSURED_NAME": True, "INSURED_LABEL": False, "Amount Mio": ":,.0f"},
    )
    fig.update_traces(texttemplate="%{x:.0f}", textposition="outside", cliponaxis=False)
    fig.update_layout(
        title={"text": "Top Insured: GWP vs Claims vs Stop Loss", "x": 0.5, "xanchor": "center"},
        height=max(430, 95 + 31 * max(1, chart_df["INSURED_LABEL"].nunique())),
        margin=dict(l=10, r=36, t=58, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#1E293B"),
        title_font=dict(size=15, color="#003366"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, title=None),
        xaxis=dict(title=None, showgrid=False, zeroline=False, ticksuffix=" Mio"),
        yaxis=dict(title=None, autorange="reversed"),
    )
    return fig


def make_donut_chart(total_stoploss: float, total_remain: float):
    donut_df = pd.DataFrame({
        "Type": ["Stop Loss", "Remaining Premium"],
        "Amount": [total_stoploss, total_remain],
    })
    fig = px.pie(
        donut_df,
        names="Type",
        values="Amount",
        hole=0.62,
        color="Type",
        color_discrete_map={"Stop Loss": "#003366", "Remaining Premium": "#E39A5B"},
    )
    fig.update_traces(textinfo="percent+label", textposition="inside", hovertemplate="%{label}<br>%{value:,.0f} Mio<extra></extra>")
    fig.update_layout(
        title={"text": "Stop Loss vs Remaining Premium", "x": 0.5, "xanchor": "center"},
        height=430,
        margin=dict(l=10, r=10, t=58, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        title_font=dict(size=15, color="#003366"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.12, xanchor="center", x=0.5, title=None),
    )
    return fig


def render_policy_table(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        st.info("No policy detail to display.")
        return

    display_cols = [
        c for c in [
            "POLICY_NO", "ACCOUNT_NAME", "INSURED_NAME", "OUR_TSI", "GWP_AMT",
            "GROSS_CLAIMS", "STOP_LOSS", "UPR ", "REMAIN_PREM"
        ] if c in df.columns
    ]
    if not display_cols:
        display_cols = list(df.columns)

    raw = df[display_cols].copy().reset_index(drop=True)
    display = raw.copy()

    money_cols = [c for c in ["OUR_TSI", "GWP_AMT", "GROSS_CLAIMS", "STOP_LOSS", "UPR ", "REMAIN_PREM"] if c in display.columns]
    for col in money_cols:
        display[col] = pd.to_numeric(display[col], errors="coerce") / 1_000_000
        display[col] = display[col].map(lambda x: "" if pd.isna(x) else fmt_mio(x))

    for col in display.columns:
        if col not in money_cols:
            display[col] = display[col].fillna("").astype(str)

    alias = {
        "POLICY_NO": "POLICY NO",
        "ACCOUNT_NAME": "ACCOUNT NAME",
        "INSURED_NAME": "INSURED NAME",
        "OUR_TSI": "OUR TSI<br><span>IDR Mio</span>",
        "GWP_AMT": "GWP<br><span>IDR Mio</span>",
        "GROSS_CLAIMS": "GROSS CLAIMS<br><span>IDR Mio</span>",
        "STOP_LOSS": "STOP LOSS<br><span>IDR Mio</span>",
        "UPR ": "UPR<br><span>IDR Mio</span>",
        "REMAIN_PREM": "REMAIN PREM<br><span>IDR Mio</span>",
    }

    def width_for(col: str) -> int:
        if col in ["POLICY_NO"]:
            return 170
        if col in ["ACCOUNT_NAME", "INSURED_NAME"]:
            return 250
        if col in money_cols:
            return 135
        return 150

    col_widths = {col: width_for(col) for col in display.columns}
    min_table_width = sum(col_widths.values())
    table_height = max(260, min(560, 92 + 34 * len(display)))

    sticky_cols = [c for c in ["POLICY_NO"] if c in display.columns]
    sticky_left = {}
    running_left = 0
    for c in display.columns:
        if c in sticky_cols:
            sticky_left[c] = running_left
            running_left += col_widths[c]

    colgroup = "".join([f"<col style='width:{col_widths[c]}px;min-width:{col_widths[c]}px;'>" for c in display.columns])
    header = "".join([
        f"<th class='{'sticky-col' if c in sticky_left else ''}' style='{f'left:{sticky_left[c]}px;' if c in sticky_left else ''}'>{alias.get(c, html.escape(str(c).replace('_', ' ')))}</th>"
        for c in display.columns
    ])

    rows = []
    for r in range(len(display)):
        cells = []
        for col in display.columns:
            cls = "num-cell" if col in money_cols else "text-cell"
            sticky = " sticky-col" if col in sticky_left else ""
            style = f"left:{sticky_left[col]}px;" if col in sticky_left else ""
            cells.append(f"<td class='{cls}{sticky}' style='{style}'>{html.escape(str(display.iloc[r][col]))}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")

    table_id = "askred_table_" + hashlib.sha1(str(display.shape).encode("utf-8")).hexdigest()[:10]
    html_table = f"""
    <style>
      body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Arial,sans-serif;background:transparent;}}
      .askred-table-wrap{{
        width:100%;max-height:{table_height}px;overflow:auto;
        border:1px solid rgba(0,51,102,0.12);border-radius:16px;background:#FFFFFF;
        box-shadow:0 10px 28px rgba(15,23,42,0.06);
      }}
      .askred-table{{border-collapse:separate;border-spacing:0;table-layout:fixed;width:{min_table_width}px;min-width:{min_table_width}px;color:#334155;}}
      .askred-table thead th{{
        position:sticky;top:0;z-index:30;background:#003366;color:#FFFFFF;text-align:center;
        vertical-align:middle;font-size:10.8px;line-height:1.18;font-weight:760;height:46px;
        padding:8px 8px;border-right:1px solid rgba(255,255,255,0.18);white-space:normal;box-sizing:border-box;
      }}
      .askred-table thead th span{{display:block;margin-top:2px;font-size:8.8px;font-weight:500;opacity:.78;}}
      .askred-table tbody td{{
        font-size:11.2px;line-height:1.28;height:34px;padding:8px 10px;
        border-right:1px solid rgba(15,23,42,0.045);border-bottom:1px solid rgba(15,23,42,0.055);
        background:#FFFFFF;color:#334155;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;box-sizing:border-box;font-weight:620;
      }}
      .askred-table tbody tr:nth-child(even) td{{background:#F8FAFC;}}
      .askred-table tbody tr:hover td{{background:#EEF6FF;}}
      .askred-table .text-cell{{text-align:left;font-weight:650;color:#1E3A5F;}}
      .askred-table .num-cell{{text-align:right;font-variant-numeric:tabular-nums;}}
      .askred-table .sticky-col{{position:sticky;z-index:20;box-shadow:2px 0 0 rgba(0,51,102,0.08);}}
      .askred-table thead th.sticky-col{{z-index:40;background:#002B57;}}
      .askred-table tbody td.sticky-col{{background:#FFFFFF;}}
      .askred-table tbody tr:nth-child(even) td.sticky-col{{background:#F8FAFC;}}
      .askred-table tbody tr:hover td.sticky-col{{background:#EEF6FF;}}
    </style>
    <div class="askred-table-wrap">
      <table class="askred-table" id="{table_id}">
        <colgroup>{colgroup}</colgroup>
        <thead><tr>{header}</tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """
    components.html(html_table, height=table_height + 8, scrolling=False)


# =====================================================
# DASHBOARD FUNCTION
# =====================================================
def credit_insurance_dashboard():
    inject_superaskred_theme()

    try:
        df = load_credit_data("askred 260306.parquet")
    except Exception as exc:
        st.error("Credit Insurance data could not be loaded.")
        with st.expander("Technical details", expanded=False):
            st.code(str(exc))
        return

    st.markdown(
        """
        <div class="askred-hero">
          <h1>Credit Insurance Portfolio Dashboard</h1>
          <p>Premium, claims, stop loss, and remaining premium view as at 6 Maret 2026.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---------- SIDEBAR FILTER ----------
    st.sidebar.markdown("<h3 style='color:#003366;margin-bottom:4px;'>Filters</h3>", unsafe_allow_html=True)
    st.sidebar.markdown(
        "<div class='askred-sidebar-note'>Kosong berarti filter tidak aktif / semua data ditampilkan.</div>",
        unsafe_allow_html=True,
    )

    account_options = get_unique_options(df, "ACCOUNT_NAME")
    insured_options = get_unique_options(df, "INSURED_NAME")
    policy_options = get_unique_options(df, "POLICY_NO")

    with st.sidebar.expander("Account Name", expanded=False):
        account_selected = st.multiselect("Choose account", account_options, default=[], key="askred_account_filter")

    with st.sidebar.expander("Insured Name", expanded=False):
        insured_selected = st.multiselect("Choose insured", insured_options, default=[], key="askred_insured_filter")

    with st.sidebar.expander("Policy No", expanded=False):
        policy_selected = st.multiselect("Choose policy", policy_options, default=[], key="askred_policy_filter")

    df_f = make_filtered_df(
        df,
        tuple(account_selected),
        tuple(insured_selected),
        tuple(policy_selected),
    )

    render_filter_badges(account_selected, insured_selected, policy_selected)

    if df_f.empty:
        st.warning("No data on this filter")
        return

    # ---------- KPI ----------
    section_header("Portfolio Overview", "All amounts are shown in IDR Mio.")

    total_gwp = pd.to_numeric(df_f.get("GWP_AMT", 0), errors="coerce").fillna(0).sum() / 1_000_000
    total_claim = pd.to_numeric(df_f.get("GROSS_CLAIMS", 0), errors="coerce").fillna(0).sum() / 1_000_000
    total_stoploss = pd.to_numeric(df_f.get("STOP_LOSS", 0), errors="coerce").fillna(0).sum() / 1_000_000
    total_remain = pd.to_numeric(df_f.get("REMAIN_PREM", 0), errors="coerce").fillna(0).sum() / 1_000_000
    loss_ratio = total_claim / total_gwp if total_gwp > 0 else 0

    kpi_cols = st.columns(5)
    with kpi_cols[0]:
        render_kpi_card("Total GWP", fmt_mio(total_gwp), "IDR Mio")
    with kpi_cols[1]:
        render_kpi_card("Gross Claims", fmt_mio(total_claim), "IDR Mio")
    with kpi_cols[2]:
        render_kpi_card("Stop Loss", fmt_mio(total_stoploss), "IDR Mio")
    with kpi_cols[3]:
        render_kpi_card("Remaining Premium", fmt_mio(total_remain), "IDR Mio")
    with kpi_cols[4]:
        render_kpi_card("Loss Ratio", fmt_pct(loss_ratio), "Claim / GWP", danger=loss_ratio > 1)

    render_loss_ratio_toast(loss_ratio)

    # ---------- CHARTS ----------
    section_header("Portfolio Visualization", "Top insured view and premium allocation.")
    chart_df = build_top_insured_chart_df(df_f, top_n=12)

    chart_col1, chart_col2 = st.columns([1.45, 1], gap="large")
    with chart_col1:
        st.markdown('<div class="askred-chart-card">', unsafe_allow_html=True)
        if chart_df.empty:
            st.info("Chart unavailable for current filter.")
        else:
            st.plotly_chart(make_bar_chart(chart_df), width="stretch", config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    with chart_col2:
        st.markdown('<div class="askred-chart-card">', unsafe_allow_html=True)
        st.plotly_chart(make_donut_chart(total_stoploss, total_remain), width="stretch", config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    # ---------- DETAIL TABLE ----------
    section_header("Policy Detail", "Filtered policy-level details with premium, claims, and stop loss values.")
    render_policy_table(df_f)


# Optional direct run support
if __name__ == "__main__":
    credit_insurance_dashboard()
