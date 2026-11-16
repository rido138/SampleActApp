from __future__ import annotations

import html
from pathlib import Path
from typing import Iterable

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st







POLICY_DATA_PATH = "POLIS POLIS OR.xlsx"
CLAIM_DATA_PATH = "Klaim Klaim 10 Tahun Terakhir OR.xlsx"

POLICY_REQUIRED_COLS = ["UW_YEAR", "JJT", "COB", "LOB", "IS_ACTIVE", "OUR TSI", "TSI RANGE"]
CLAIM_REQUIRED_COLS = [
    "STATUS", "UW_YEAR", "POLICY_NO", "COB_NAME", "CLAIM NO", "KODE_KLAIM",
    "KODE_PENYEBAB", "INTERNAL_REASON", "GROSS CLAIM", "CLAIM RANGE"
]

POLICY_FILTER_COLS = ["UW_YEAR", "COB", "LOB", "IS_ACTIVE", "TSI RANGE"]
CLAIM_FILTER_COLS = ["STATUS", "UW_YEAR", "COB_NAME", "KODE_KLAIM", "KODE_PENYEBAB", "INTERNAL_REASON", "CLAIM RANGE"]





POLICY_OR_ALIASES = ["OR", "OUR OR", "OUR_RETENTION", "OUR RETENTION", "OWN_RETENTION", "OWN RETENTION", "OUR SHARE", "OUR TSI"]
CLAIM_OR_ALIASES = ["OR", "OUR OR", "OUR_RETENTION", "OUR RETENTION", "OWN_RETENTION", "OWN RETENTION", "OUR SHARE"]
CLAIM_AMOUNT_ALIASES = ["GROSS CLAIM", "GROSS_CLAIM", "CLAIM_AMOUNT", "CLAIM AMOUNT", "OR CLAIM", "CLAIM_OR"]





def inject_superapp_css() -> None:
    st.markdown(
        """
        <style>
          :root{
            --sa-blue:#003366;
            --sa-blue-2:#1F5A91;
            --sa-gold:#E39A5B;
            --sa-bg:#F8FAFC;
            --sa-ink:#0F172A;
            --sa-muted:#64748B;
            --sa-border:rgba(0,51,102,.12);
          }
          .sa-hero{
            margin:0 0 14px 0;
            padding:18px 20px;
            border-radius:24px;
            background:linear-gradient(135deg,#003366 0%,#0B3F73 54%,#1F5A91 100%);
            color:#FFFFFF;
            box-shadow:0 18px 44px rgba(0,51,102,.18);
            border:1px solid rgba(255,255,255,.18);
          }
          .sa-hero h1{
            margin:0;
            font-size:27px;
            line-height:1.05;
            letter-spacing:-.03em;
            font-weight:900;
          }
          .sa-hero p{
            margin:7px 0 0 0;
            color:rgba(255,255,255,.82);
            font-size:13.5px;
            line-height:1.35;
            max-width:980px;
          }
          .sa-card{
            border:1px solid var(--sa-border);
            border-radius:20px;
            background:linear-gradient(180deg,rgba(255,255,255,.98),rgba(248,250,252,.98));
            box-shadow:0 10px 28px rgba(15,23,42,.055);
            padding:14px 16px;
            margin:10px 0 12px 0;
          }
          .sa-section-title{
            color:var(--sa-blue);
            font-size:18px;
            font-weight:880;
            letter-spacing:-.02em;
            margin-bottom:2px;
          }
          .sa-muted{
            color:var(--sa-muted);
            font-size:12.5px;
            line-height:1.35;
          }
          .sa-kpi-grid{
            display:grid;
            grid-template-columns:repeat(4,minmax(0,1fr));
            gap:10px;
            margin:8px 0 10px 0;
          }
          .sa-kpi-grid.six{grid-template-columns:repeat(6,minmax(0,1fr));}
          .sa-kpi{
            min-height:92px;
            padding:12px 14px;
            border-radius:18px;
            border:1px solid rgba(0,51,102,.12);
            background:#FFFFFF;
            box-shadow:0 8px 20px rgba(15,23,42,.045);
            overflow:hidden;
          }
          .sa-kpi .label{
            color:#64748B;
            font-size:11.5px;
            font-weight:780;
            text-transform:uppercase;
            letter-spacing:.02em;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
          }
          .sa-kpi .value{
            margin-top:5px;
            color:#003366;
            font-size:25px;
            font-weight:900;
            line-height:1.05;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
            font-variant-numeric:tabular-nums;
          }
          .sa-table-wrap{
            width:100%;
            max-height:430px;
            overflow:auto;
            border:1px solid rgba(0,51,102,.12);
            border-radius:16px;
            background:#FFFFFF;
            box-shadow:0 8px 22px rgba(15,23,42,.04);
            margin-top:8px;
          }
          .sa-table{
            border-collapse:separate;
            border-spacing:0;
            width:100%;
            min-width:900px;
            font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Arial,sans-serif;
          }
          .sa-table th{
            position:sticky;
            top:0;
            z-index:2;
            background:#003366;
            color:#FFFFFF;
            font-size:11px;
            font-weight:840;
            text-align:center;
            padding:10px 9px;
            border-right:1px solid rgba(255,255,255,.16);
            white-space:nowrap;
          }
          .sa-table td{
            font-size:11.4px;
            padding:8px 10px;
            border-bottom:1px solid rgba(15,23,42,.055);
            border-right:1px solid rgba(15,23,42,.045);
            color:#334155;
            background:#FFFFFF;
            white-space:nowrap;
            font-weight:620;
          }
          .sa-table tr:nth-child(even) td{background:#F8FAFC;}
          .sa-table tr:hover td{background:#EEF6FF;}
          .sa-table .num{text-align:right;font-variant-numeric:tabular-nums;}
          .sa-table .txt{text-align:left;color:#1E3A5F;font-weight:720;}
          .sa-pill-strip{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 12px 0;}
          .sa-pill{padding:6px 10px;border-radius:999px;border:1px solid rgba(0,51,102,.14);background:#FFFFFF;color:#1E3A5F;font-weight:760;font-size:11.5px;}

          div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Dashboard view"]) {
            width:100% !important;
            margin:2px 0 6px 0 !important;
            overflow:hidden !important;
          }
          div[data-testid="stRadio"]:has(div[role="radiogroup"][aria-label="Dashboard view"]) > div {
            width:100% !important;
            overflow-x:auto !important;
            overflow-y:hidden !important;
            padding:0 0 5px 0 !important;
            scrollbar-width:thin !important;
          }
          div[role="radiogroup"][aria-label="Dashboard view"]{
            display:inline-flex !important;
            flex-direction:row !important;
            flex-wrap:nowrap !important;
            gap:8px !important;
            padding:4px 4px 7px 4px !important;
            border-bottom:1px solid rgba(0,51,102,.14) !important;
            min-width:100% !important;
            width:fit-content !important;
          }
          div[role="radiogroup"][aria-label="Dashboard view"] label{
            flex:0 0 auto !important;
            white-space:nowrap !important;
            display:inline-flex !important;
            align-items:center !important;
            justify-content:center !important;
            padding:9px 16px !important;
            margin:0 !important;
            border-radius:999px !important;
            border:1px solid rgba(0,51,102,.14) !important;
            background:linear-gradient(180deg,#FFFFFF 0%,#F4F7FB 100%) !important;
            color:#334155 !important;
            font-size:12.5px !important;
            line-height:1 !important;
            font-weight:760 !important;
            box-shadow:0 5px 14px rgba(15,23,42,.045) !important;
          }
          div[role="radiogroup"][aria-label="Dashboard view"] label:has(input:checked){
            background:linear-gradient(135deg,#003366 0%,#1F5A91 100%) !important;
            color:#FFFFFF !important;
            border-color:rgba(0,51,102,.72) !important;
            box-shadow:0 10px 22px rgba(0,51,102,.20) !important;
          }
          div[role="radiogroup"][aria-label="Dashboard view"] label:has(input:checked) *{
            color:#FFFFFF !important;
            -webkit-text-fill-color:#FFFFFF !important;
          }
          div[role="radiogroup"][aria-label="Dashboard view"] input,
          div[role="radiogroup"][aria-label="Dashboard view"] svg{display:none !important;}

          @media(max-width:1200px){.sa-kpi-grid.six{grid-template-columns:repeat(3,minmax(0,1fr));}}
          @media(max-width:900px){.sa-kpi-grid,.sa-kpi-grid.six{grid-template-columns:repeat(2,minmax(0,1fr));}}
        </style>
        """,
        unsafe_allow_html=True,
    )





def _fmt_int(x: float | int | None) -> str:
    if x is None or pd.isna(x):
        return ""
    return f"{int(round(float(x))):,}".replace(",", ".")


def _fmt_mio(x: float | int | None) -> str:
    if x is None or pd.isna(x):
        return ""
    return _fmt_int(float(x) / 1_000_000)


def _fmt_pct(x: float | int | None) -> str:
    if x is None or pd.isna(x):
        return ""
    return f"{float(x):.1f}%"


def _clean_text_col(s: pd.Series) -> pd.Series:
    return s.astype("string").fillna("(Blank)").replace({"": "(Blank)"})


def _safe_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def _policy_base_no(series: pd.Series) -> pd.Series:

    return series.astype(str).str.replace(r"-\d+$", "", regex=True)





def _first_existing_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols_snapshot = list(df.columns)
    exact = {str(c): c for c in cols_snapshot}
    upper = {str(c).strip().upper(): c for c in cols_snapshot}
    for c in candidates:
        if c in exact:
            return exact[c]
        cu = str(c).strip().upper()
        if cu in upper:
            return upper[cu]
    return None


def _standardize_or_policy_schema(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    or_col = _first_existing_col(out, POLICY_OR_ALIASES)
    if or_col is None:
        raise ValueError("Missing policy OR column. Expected one of: " + ", ".join(POLICY_OR_ALIASES))
    if or_col != "OR":
        out = out.rename(columns={or_col: "OR"})
    if "OUR TSI" not in out.columns:

        out["OUR TSI"] = out["OR"]
    if "TSI RANGE" not in out.columns:
        out["TSI RANGE"] = "(Blank)"
    if "IS_ACTIVE" not in out.columns:
        out["IS_ACTIVE"] = "(Blank)"
    if "COB" not in out.columns:
        out["COB"] = "(Blank)"
    if "LOB" not in out.columns:
        out["LOB"] = "(Blank)"
    return out


def _standardize_or_claim_schema(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    amt_col = _first_existing_col(out, CLAIM_AMOUNT_ALIASES)
    if amt_col is None:
        raise ValueError("Missing claim amount column. Expected one of: " + ", ".join(CLAIM_AMOUNT_ALIASES))
    if amt_col != "GROSS CLAIM":
        out = out.rename(columns={amt_col: "GROSS CLAIM"})
    or_col = _first_existing_col(out, CLAIM_OR_ALIASES)
    if or_col is not None and or_col != "OR":
        out = out.rename(columns={or_col: "OR"})
    for col in ["STATUS", "COB_NAME", "KODE_KLAIM", "KODE_PENYEBAB", "INTERNAL_REASON", "CLAIM RANGE", "POLICY_NO", "CLAIM NO"]:
        if col not in out.columns:
            out[col] = "(Blank)"
    return out


def _keep_existing_columns(df: pd.DataFrame, desired_cols: list[str]) -> pd.DataFrame:
    df_cols_snapshot = list(df.columns)
    cols = [c for c in desired_cols if c in df_cols_snapshot]
    return df[cols].copy()

def _optimize_policy_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["UW_YEAR"] = pd.to_numeric(out["UW_YEAR"], errors="coerce").astype("Int64")
    out["OR"] = _safe_numeric(out["OR"])
    out["OUR TSI"] = _safe_numeric(out["OUR TSI"])


    for col in ["JJT", "COB", "LOB", "IS_ACTIVE", "TSI RANGE"]:
        if col in out.columns:
            out[col] = _clean_text_col(out[col]).astype(object)
    out["POLICY_BASE_NO"] = _policy_base_no(out["JJT"])
    return out


def _optimize_claim_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["UW_YEAR"] = pd.to_numeric(out["UW_YEAR"], errors="coerce").astype("Int64")
    out["GROSS CLAIM"] = _safe_numeric(out["GROSS CLAIM"])
    for col in [c for c in CLAIM_REQUIRED_COLS if c != "GROSS CLAIM"]:
        if col in out.columns:
            out[col] = _clean_text_col(out[col])
    return out


def load_policy_data(path: str = POLICY_DATA_PATH) -> pd.DataFrame:
    df = pd.read_excel(path)
    df = _standardize_or_policy_schema(df)
    needed = list(dict.fromkeys(POLICY_REQUIRED_COLS + ["OR", "POLICY_NO", "CRE_BY", "UW_MONTH", "BRANCH", "INTERMEDIARY_NAME"]))
    base = _keep_existing_columns(df, needed)
    missing = [c for c in ["UW_YEAR", "JJT", "OR"] if c not in base.columns]
    if missing:
        raise ValueError("Missing policy columns: " + ", ".join(missing))
    return _optimize_policy_df(base)


def load_claim_data(path: str = CLAIM_DATA_PATH) -> pd.DataFrame:
    df = pd.read_excel(path)
    df = _standardize_or_claim_schema(df)
    needed = list(dict.fromkeys(CLAIM_REQUIRED_COLS + ["OR", "CRE_BY"]))
    base = _keep_existing_columns(df, needed)
    missing = [c for c in ["UW_YEAR", "POLICY_NO", "GROSS CLAIM"] if c not in base.columns]
    if missing:
        raise ValueError("Missing claim columns: " + ", ".join(missing))
    return _optimize_claim_df(base)





def render_hero() -> None:
    st.markdown(
        """
        <div class="sa-hero">
          <h1>Policy & Claim Monitoring</h1>
          <p>Monitoring polis, klaim, dan exposure mapping dengan visual style yang sama seperti SuperApp Actuary. Amount ditampilkan dalam IDR Mio.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_card(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div class="sa-card">
          <div class="sa-section-title">{html.escape(title)}</div>
          <div class="sa-muted">{html.escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_grid(items: list[tuple[str, str]], six: bool = False) -> None:
    cls = "sa-kpi-grid six" if six else "sa-kpi-grid"
    cards = "".join(
        f"<div class='sa-kpi'><div class='label'>{html.escape(label)}</div><div class='value'>{html.escape(value)}</div></div>"
        for label, value in items
    )
    st.markdown(f"<div class='{cls}'>{cards}</div>", unsafe_allow_html=True)


def _build_html_table_markup(df: pd.DataFrame, max_rows: int = 300) -> str:
    if df is None or df.empty:
        return ""

    show_df = df.head(max_rows).copy()
    display_cols = list(show_df.columns)
    headers = "".join(f"<th>{html.escape(str(c).replace('_', ' '))}</th>" for c in display_cols)
    amount_cols = {"Total_TSI", "Average_TSI", "Gross_Claim", "Average_Severity", "Max_Claim", "Retention", "Limit", "Layer_Ceiling", "Layer_Claim", "Average_On_Layer_Severity", "Pure_Premium", "Loaded_Premium", "Expected_Loss", "Loaded_Expected_Loss", "Total_On_Layer_Claim", "OR"}
    count_cols = {"Policy_Count", "Unit_Count", "Row_Count", "Claim_Count", "Distinct_Policy_Count", "Exposure_JJT", "Exposure_Policy", "Claim_Events"}
    pct_cols = {c for c in display_cols if str(c).endswith("_%") or c in ["Claim_Frequency_%", "Loss_to_TSI_%", "Frequency_%"]}

    rows = []
    for _, r in show_df.iterrows():
        cells = []
        for c in display_cols:
            val = r[c]
            if c in amount_cols:
                text = _fmt_mio(val)
                cls = "num"
            elif c in count_cols:
                text = _fmt_int(val)
                cls = "num"
            elif c in pct_cols:
                text = _fmt_pct(val)
                cls = "num"
            elif pd.api.types.is_numeric_dtype(show_df[c]):
                text = _fmt_int(val)
                cls = "num"
            else:
                text = "" if pd.isna(val) else str(val)
                cls = "txt"
            cells.append(f"<td class='{cls}'>{html.escape(text)}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")

    note = "" if len(df) <= max_rows else f"<div class='sa-muted' style='margin-top:6px;'>Showing first {_fmt_int(max_rows)} of {_fmt_int(len(df))} rows for lighter rendering.</div>"
    return f"<div class='sa-table-wrap'><table class='sa-table'><thead><tr>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>{note}"


def render_html_table(df: pd.DataFrame, max_rows: int = 300) -> None:
    markup = _build_html_table_markup(df, max_rows=max_rows)
    if not markup:
        st.info("No data.")
        return
    st.markdown(markup, unsafe_allow_html=True)





def _default_tsi_manual_rules() -> pd.DataFrame:

    return pd.DataFrame([
        {"TSI_RANGE_MANUAL": "<= 1 Bio", "Min_TSI": 0.0, "Max_TSI": 1_000_000_000.0},
        {"TSI_RANGE_MANUAL": "> 1 - 5 Bio", "Min_TSI": 1_000_000_000.0, "Max_TSI": 5_000_000_000.0},
        {"TSI_RANGE_MANUAL": "> 5 - 10 Bio", "Min_TSI": 5_000_000_000.0, "Max_TSI": 10_000_000_000.0},
        {"TSI_RANGE_MANUAL": "> 10 - 50 Bio", "Min_TSI": 10_000_000_000.0, "Max_TSI": 50_000_000_000.0},
        {"TSI_RANGE_MANUAL": "> 50 - 100 Bio", "Min_TSI": 50_000_000_000.0, "Max_TSI": 100_000_000_000.0},
        {"TSI_RANGE_MANUAL": "> 100 Bio", "Min_TSI": 100_000_000_000.0, "Max_TSI": np.nan},
    ])


def _normalise_tsi_manual_rules(rules: pd.DataFrame) -> pd.DataFrame:
    if rules is None or not isinstance(rules, pd.DataFrame) or rules.empty:
        return pd.DataFrame(columns=["TSI_RANGE_MANUAL", "Min_TSI", "Max_TSI"])
    out = rules.copy()
    for col in ["TSI_RANGE_MANUAL", "Min_TSI", "Max_TSI"]:
        if col not in out.columns:
            out[col] = np.nan
    out = out[["TSI_RANGE_MANUAL", "Min_TSI", "Max_TSI"]].copy()
    out["TSI_RANGE_MANUAL"] = out["TSI_RANGE_MANUAL"].astype(str).str.strip()
    out["Min_TSI"] = pd.to_numeric(out["Min_TSI"], errors="coerce")
    out["Max_TSI"] = pd.to_numeric(out["Max_TSI"], errors="coerce")
    out = out[(out["TSI_RANGE_MANUAL"] != "") & out["Min_TSI"].notna()].copy()
    out = out[(out["Max_TSI"].isna()) | (out["Max_TSI"] > out["Min_TSI"])].copy()
    out = out.sort_values("Min_TSI", kind="stable").reset_index(drop=True)
    return out


def _apply_tsi_manual_mapping(policy_df: pd.DataFrame, rules: pd.DataFrame) -> pd.DataFrame:

    if policy_df is None or policy_df.empty:
        return policy_df
    rules = _normalise_tsi_manual_rules(rules)
    if rules.empty or "OUR TSI" not in policy_df.columns:
        return policy_df

    out = policy_df.copy()
    tsi = pd.to_numeric(out["OUR TSI"], errors="coerce")
    mapped = pd.Series("(Unmapped)", index=out.index, dtype=object)
    for _, row in rules.iterrows():
        lo = float(row["Min_TSI"])
        hi = row["Max_TSI"]
        label = str(row["TSI_RANGE_MANUAL"])
        if pd.isna(hi):
            mask = tsi >= lo
        else:
            mask = (tsi >= lo) & (tsi < float(hi))
        mapped.loc[mask.fillna(False)] = label


    out["TSI RANGE"] = mapped.astype(object)
    out["TSI_MAPPING_SOURCE"] = "Manual"
    return out


def render_tsi_manual_mapping_sidebar(policy_df: pd.DataFrame) -> pd.DataFrame:

    if policy_df is None or policy_df.empty or "OUR TSI" not in policy_df.columns:
        return policy_df

    st.sidebar.markdown("---")
    with st.sidebar.expander("Manual TSI Mapping", expanded=False):
        active = bool(st.session_state.get("tsi_manual_mapping_active", False))
        if active:
            st.success("Manual TSI mapping: Active")
        else:
            st.caption("Manual mapping belum aktif. Edit rules lalu klik Proses Mapping.")

        if "tsi_manual_rules_staged" not in st.session_state:
            st.session_state["tsi_manual_rules_staged"] = _default_tsi_manual_rules()

        with st.form("tsi_manual_mapping_form", clear_on_submit=False):
            edited_rules = st.data_editor(
                st.session_state["tsi_manual_rules_staged"],
                hide_index=True,
                num_rows="dynamic",
                width='stretch',
                key="tsi_manual_rules_editor",
                column_config={
                    "TSI_RANGE_MANUAL": st.column_config.TextColumn("TSI Range"),
                    "Min_TSI": st.column_config.NumberColumn("Min TSI", min_value=0.0, step=1_000_000_000.0, format="%.0f"),
                    "Max_TSI": st.column_config.NumberColumn("Max TSI", min_value=0.0, step=1_000_000_000.0, format="%.0f", help="Kosongkan untuk open-ended layer."),
                },
            )
            process_mapping = st.form_submit_button("Proses Mapping", type="primary", width='stretch')

        col1, col2 = st.columns(2)
        with col1:
            reset_clicked = st.button("Reset Rules", key="tsi_manual_reset_rules", width='stretch')
        with col2:
            disable_clicked = st.button("Disable", key="tsi_manual_disable", width='stretch')

        if reset_clicked:
            st.session_state["tsi_manual_rules_staged"] = _default_tsi_manual_rules()
            st.session_state["tsi_manual_mapping_active"] = False
            st.session_state.pop("tsi_manual_rules_processed", None)
            st.rerun()

        if disable_clicked:
            st.session_state["tsi_manual_mapping_active"] = False
            st.session_state.pop("tsi_manual_rules_processed", None)
            st.rerun()

        if process_mapping:
            cleaned = _normalise_tsi_manual_rules(edited_rules)
            if cleaned.empty:
                st.warning("Mapping belum valid. Isi minimal 1 row dengan label dan Min TSI yang valid.")
                st.session_state["tsi_manual_mapping_active"] = False
            else:
                st.session_state["tsi_manual_rules_staged"] = cleaned.copy()
                st.session_state["tsi_manual_rules_processed"] = cleaned.copy()
                st.session_state["tsi_manual_mapping_active"] = True
                st.success("Manual TSI mapping diproses dan aktif.")

    if st.session_state.get("tsi_manual_mapping_active", False):
        rules = st.session_state.get("tsi_manual_rules_processed", pd.DataFrame())
        return _apply_tsi_manual_mapping(policy_df, rules)
    return policy_df




def _cached_filter_options(df: pd.DataFrame, col: str) -> list[str]:
    if df is None or df.empty or col not in df.columns:
        return []
    return sorted([str(x) for x in df[col].dropna().astype(str).unique() if str(x) != "(Blank)"])

def apply_multiselect_filters(df: pd.DataFrame, cols: Iterable[str], prefix: str, title: str) -> tuple[pd.DataFrame, dict]:
    filtered = df
    active_filters: dict = {}
    st.sidebar.header(title)
    for col in list(cols):
        filtered_cols_snapshot = list(filtered.columns)
        if col not in filtered_cols_snapshot:
            continue
        options = _cached_filter_options(filtered, col)
        with st.sidebar.expander(col, expanded=False):
            selected = st.multiselect(
                f"Select {col}",
                options=options,
                default=[],
                key=f"{prefix}_filter_{col}",
            )
            if selected:
                filtered = filtered[filtered[col].astype(str).isin(selected)]
            active_filters[col] = selected
    return filtered, active_filters





def aggregate_policy(df: pd.DataFrame, group_cols: tuple[str, ...]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    group_cols = tuple(c for c in group_cols if c in df.columns)
    if not group_cols:
        group_cols = ("TSI RANGE",)

    agg = (
        df.groupby(list(group_cols), dropna=False, observed=True)
        .agg(
            Policy_Count=("POLICY_BASE_NO", "nunique"),
            Unit_Count=("JJT", "nunique"),
            Row_Count=("JJT", "size"),
            Total_TSI=("OUR TSI", "sum"),
            Average_TSI=("OUR TSI", "mean"),
        )
        .reset_index()
    )
    total_policy = float(agg["Policy_Count"].sum())
    total_tsi = float(agg["Total_TSI"].sum())
    agg["Policy_Share_%"] = np.where(total_policy > 0, agg["Policy_Count"] / total_policy * 100.0, 0.0)
    agg["TSI_Share_%"] = np.where(total_tsi > 0, agg["Total_TSI"] / total_tsi * 100.0, 0.0)
    return agg.sort_values(["Total_TSI", "Policy_Count"], ascending=[False, False], kind="stable").reset_index(drop=True)


def aggregate_claim(df: pd.DataFrame, group_cols: tuple[str, ...]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    group_cols = tuple(c for c in group_cols if c in df.columns)
    if not group_cols:
        group_cols = ("CLAIM RANGE",)

    agg = (
        df.groupby(list(group_cols), dropna=False, observed=True)
        .agg(
            Claim_Count=("CLAIM NO", "nunique"),
            Distinct_Policy_Count=("POLICY_NO", "nunique"),
            Gross_Claim=("GROSS CLAIM", "sum"),
            Average_Severity=("GROSS CLAIM", "mean"),
            Max_Claim=("GROSS CLAIM", "max"),
        )
        .reset_index()
    )
    total_claim = float(agg["Claim_Count"].sum())
    total_gross = float(agg["Gross_Claim"].sum())
    agg["Claim_Share_%"] = np.where(total_claim > 0, agg["Claim_Count"] / total_claim * 100.0, 0.0)
    agg["Gross_Claim_Share_%"] = np.where(total_gross > 0, agg["Gross_Claim"] / total_gross * 100.0, 0.0)
    return agg.sort_values(["Gross_Claim", "Claim_Count"], ascending=[False, False], kind="stable").reset_index(drop=True)


def build_policy_claim_join(policy_df: pd.DataFrame, claim_df: pd.DataFrame) -> pd.DataFrame:
    if policy_df.empty or claim_df.empty:
        return pd.DataFrame()

    policy_base = (
        policy_df.groupby(["POLICY_BASE_NO", "UW_YEAR"], dropna=False, observed=True)
        .agg(
            COB=("COB", "first"),
            LOB=("LOB", "first"),
            IS_ACTIVE=("IS_ACTIVE", "first"),
            Policy_Count=("POLICY_BASE_NO", "nunique"),
            Unit_Count=("JJT", "nunique"),
            Total_TSI=("OUR TSI", "sum"),
        )
        .reset_index()
    )
    claim_base = (
        claim_df.groupby(["POLICY_NO", "UW_YEAR"], dropna=False, observed=True)
        .agg(
            Claim_Count=("CLAIM NO", "nunique"),
            Gross_Claim=("GROSS CLAIM", "sum"),
            Max_Claim=("GROSS CLAIM", "max"),
        )
        .reset_index()
    )

    joined = policy_base.merge(
        claim_base,
        left_on=["POLICY_BASE_NO", "UW_YEAR"],
        right_on=["POLICY_NO", "UW_YEAR"],
        how="left",
    )
    joined["Claim_Count"] = joined["Claim_Count"].fillna(0.0)
    joined["Gross_Claim"] = joined["Gross_Claim"].fillna(0.0)
    joined["Max_Claim"] = joined["Max_Claim"].fillna(0.0)
    joined["Claim_Frequency_%"] = np.where(joined["Policy_Count"] > 0, joined["Claim_Count"] / joined["Policy_Count"] * 100.0, 0.0)
    joined["Loss_to_TSI_%"] = np.where(joined["Total_TSI"] > 0, joined["Gross_Claim"] / joined["Total_TSI"] * 100.0, 0.0)
    return joined





def render_horizontal_pair(summary: pd.DataFrame, label_col: str, left_value: str, right_value: str, left_title: str, right_title: str) -> None:
    if summary is None or summary.empty or label_col not in summary.columns:
        st.info("No chart data.")
        return

    chart_df = summary.copy()

    chart_df[label_col] = chart_df[label_col].astype(object).where(chart_df[label_col].notna(), "(Blank)").astype(str)
    chart_df = chart_df[chart_df[label_col] != "(Blank)"]
    chart_df = chart_df.sort_values(label_col, ascending=True, kind="stable").head(30).reset_index(drop=True)
    if chart_df.empty:
        st.info("No chart data.")
        return

    label_order = chart_df[label_col].tolist()
    chart_h = max(280, min(640, 30 * len(chart_df)))
    chart_df["Left_Label"] = chart_df[left_value].map(lambda x: _fmt_int(x) if "Count" in left_value or "Policy" in left_value else _fmt_mio(x))
    chart_df["Right_Label"] = chart_df[right_value].map(lambda x: _fmt_mio(x) if "TSI" in right_value or "Claim" in right_value or "Severity" in right_value else _fmt_int(x))

    c1, c2 = st.columns(2, gap="large")
    with c1:
        base = alt.Chart(chart_df).encode(
            y=alt.Y(f"{label_col}:N", title=None, sort=label_order, axis=alt.Axis(labelLimit=260, labelColor="#475569")),
            x=alt.X(f"{left_value}:Q", title=None),
            tooltip=[alt.Tooltip(f"{label_col}:N", title=label_col), alt.Tooltip(f"{left_value}:Q", title=left_title, format=",.0f")],
        )
        bars = base.mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6, color="#003366")
        labels = base.mark_text(align="left", baseline="middle", dx=6, color="#334155", fontSize=11, fontWeight="bold").encode(text="Left_Label:N")
        st.altair_chart(
            (bars + labels).properties(height=chart_h, title=left_title).configure_title(anchor="middle", color="#003366", fontSize=15, fontWeight="bold").configure_view(strokeWidth=0),
            width='stretch',
        )
    with c2:
        base = alt.Chart(chart_df).encode(
            y=alt.Y(f"{label_col}:N", title=None, sort=label_order, axis=alt.Axis(labelLimit=260, labelColor="#475569")),
            x=alt.X(f"{right_value}:Q", title=None),
            tooltip=[alt.Tooltip(f"{label_col}:N", title=label_col), alt.Tooltip(f"{right_value}:Q", title=right_title, format=",.0f")],
        )
        bars = base.mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6, color="#E39A5B")
        labels = base.mark_text(align="left", baseline="middle", dx=6, color="#334155", fontSize=11, fontWeight="bold").encode(text="Right_Label:N")
        st.altair_chart(
            (bars + labels).properties(height=chart_h, title=right_title).configure_title(anchor="middle", color="#003366", fontSize=15, fontWeight="bold").configure_view(strokeWidth=0),
            width='stretch',
        )


def render_year_trend(policy_df: pd.DataFrame, claim_df: pd.DataFrame) -> None:
    p = aggregate_policy(policy_df, ("UW_YEAR",)).sort_values("UW_YEAR") if not policy_df.empty else pd.DataFrame()
    c = aggregate_claim(claim_df, ("UW_YEAR",)).sort_values("UW_YEAR") if not claim_df.empty else pd.DataFrame()
    c1, c2 = st.columns(2, gap="large")
    with c1:
        if not p.empty:
            chart = (
                alt.Chart(p)
                .mark_line(point=True, strokeWidth=3, color="#003366")
                .encode(
                    x=alt.X("UW_YEAR:O", title="UW Year", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("Policy_Count:Q", title="Policy Count"),
                    tooltip=["UW_YEAR:O", alt.Tooltip("Policy_Count:Q", title="Policy Count", format=",.0f")],
                )
                .properties(height=310, title="UW Year Trend - Policy Count")
                .configure_title(anchor="middle", color="#003366", fontSize=15, fontWeight="bold")
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(chart, width='stretch')
    with c2:
        if not c.empty:
            c = c.copy()
            c["Gross Claim Mio"] = c["Gross_Claim"] / 1_000_000
            chart = (
                alt.Chart(c)
                .mark_line(point=True, strokeWidth=3, color="#E39A5B")
                .encode(
                    x=alt.X("UW_YEAR:O", title="UW Year", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("Gross Claim Mio:Q", title="IDR Mio"),
                    tooltip=["UW_YEAR:O", alt.Tooltip("Gross Claim Mio:Q", title="Gross Claim Mio", format=",.0f")],
                )
                .properties(height=310, title="UW Year Trend - Gross Claim")
                .configure_title(anchor="middle", color="#003366", fontSize=15, fontWeight="bold")
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(chart, width='stretch')





def render_policy_overview(policy_df: pd.DataFrame) -> None:
    render_card("Policy Overview", "Monitoring jumlah polis, unit, status aktif, dan total TSI.")
    active_policy = policy_df[policy_df["IS_ACTIVE"].astype(str).str.upper().eq("ACTIVE")]["POLICY_BASE_NO"].nunique() if "IS_ACTIVE" in policy_df.columns else 0
    items = [
        ("Policy Count", _fmt_int(policy_df["POLICY_BASE_NO"].nunique())),
        ("Unit Count / JJT", _fmt_int(policy_df["JJT"].nunique())),
        ("Total OR / IDR Mio", _fmt_mio(policy_df["OR"].sum() if "OR" in policy_df.columns else policy_df["OUR TSI"].sum())),
        ("Average OR / IDR Mio", _fmt_mio(policy_df["OR"].mean() if "OR" in policy_df.columns else policy_df["OUR TSI"].mean())),
        ("Active Policies", _fmt_int(active_policy)),
        ("TSI Buckets", _fmt_int(policy_df["TSI RANGE"].nunique())),
    ]
    render_kpi_grid(items, six=True)

    st.markdown(
        "<div class='sa-pill-strip'>"
        + "".join([f"<span class='sa-pill'>{html.escape(c)}: {html.escape(_fmt_int(policy_df[c].nunique()))}</span>" for c in POLICY_FILTER_COLS if c in policy_df.columns])
        + "</div>",
        unsafe_allow_html=True,
    )

    render_card("Policy Distribution", "Policy count dan total TSI dipisah karena skalanya berbeda.")
    group_option = st.selectbox(
        "Policy breakdown dimension",
        options=["COB", "LOB", "IS_ACTIVE", "UW_YEAR", "TSI RANGE", "COB + TSI RANGE", "LOB + TSI RANGE"],
        index=0,
        key="policy_breakdown_dimension",
    )
    if group_option == "COB + TSI RANGE":
        group_cols = ("COB", "TSI RANGE")
        label_col = "COB_TSI_RANGE"
    elif group_option == "LOB + TSI RANGE":
        group_cols = ("LOB", "TSI RANGE")
        label_col = "LOB_TSI_RANGE"
    else:
        group_cols = (group_option,)
        label_col = group_option

    summary = aggregate_policy(policy_df, group_cols)
    if len(group_cols) > 1 and not summary.empty:
        summary[label_col] = summary[list(group_cols)].astype(str).agg(" | ".join, axis=1)
    render_horizontal_pair(summary, label_col, "Policy_Count", "Total_TSI", "Policy Count", "Total TSI / IDR Mio")
    render_html_table(summary, max_rows=300)


def render_claim_overview(claim_df: pd.DataFrame) -> None:
    render_card("Claim Overview", "Monitoring jumlah klaim, severity, status klaim, dan distribusi gross claim.")
    items = [
        ("Claim Count", _fmt_int(claim_df["CLAIM NO"].nunique())),
        ("Policy with Claim", _fmt_int(claim_df["POLICY_NO"].nunique())),
        ("Gross Claim / IDR Mio", _fmt_mio(claim_df["GROSS CLAIM"].sum())),
        ("Average Severity / IDR Mio", _fmt_mio(claim_df["GROSS CLAIM"].mean())),
        ("Largest Claim / IDR Mio", _fmt_mio(claim_df["GROSS CLAIM"].max())),
        ("Claim Ranges", _fmt_int(claim_df["CLAIM RANGE"].nunique())),
    ]
    render_kpi_grid(items, six=True)

    render_card("Claim Distribution", "Gross claim dan claim count ditampilkan terpisah supaya lebih mudah dibaca.")
    group_option = st.selectbox(
        "Claim breakdown dimension",
        options=["STATUS", "COB_NAME", "UW_YEAR", "CLAIM RANGE", "KODE_KLAIM", "KODE_PENYEBAB", "INTERNAL_REASON"],
        index=3,
        key="claim_breakdown_dimension",
    )
    summary = aggregate_claim(claim_df, (group_option,))
    render_horizontal_pair(summary, group_option, "Claim_Count", "Gross_Claim", "Claim Count", "Gross Claim / IDR Mio")
    render_html_table(summary, max_rows=300)

    render_card("Top Claim Details", "Daftar klaim terbesar untuk quick investigation.")
    top_claims = claim_df.sort_values("GROSS CLAIM", ascending=False, kind="stable").head(300).copy()
    top_claims = top_claims[["UW_YEAR", "POLICY_NO", "CLAIM NO", "STATUS", "COB_NAME", "KODE_KLAIM", "KODE_PENYEBAB", "INTERNAL_REASON", "GROSS CLAIM", "CLAIM RANGE"]]
    top_claims = top_claims.rename(columns={"GROSS CLAIM": "Gross_Claim"})
    render_html_table(top_claims, max_rows=300)


def render_policy_claim_bridge(policy_df: pd.DataFrame, claim_df: pd.DataFrame) -> None:
    render_card("Policy × Claim Bridge", "Menghubungkan data polis dan klaim berdasarkan policy number dasar + UW Year.")
    joined = build_policy_claim_join(policy_df, claim_df)
    if joined.empty:
        st.info("No joined data available.")
        return

    policies = joined["POLICY_BASE_NO"].nunique()
    claimed_policies = joined.loc[joined["Claim_Count"] > 0, "POLICY_BASE_NO"].nunique()
    gross = joined["Gross_Claim"].sum()
    tsi = joined["Total_TSI"].sum()
    items = [
        ("Joined Policies", _fmt_int(policies)),
        ("Policies with Claim", _fmt_int(claimed_policies)),
        ("Claim Frequency", _fmt_pct(claimed_policies / policies * 100 if policies else 0)),
        ("Gross Claim / IDR Mio", _fmt_mio(gross)),
        ("Total TSI / IDR Mio", _fmt_mio(tsi)),
        ("Claim / TSI", _fmt_pct(gross / tsi * 100 if tsi else 0)),
    ]
    render_kpi_grid(items, six=True)

    render_card("Loss Mapping by Segment", "Berguna untuk melihat segment mana yang tinggi secara exposure sekaligus klaim.")
    group_option = st.selectbox(
        "Bridge breakdown dimension",
        options=["COB", "LOB", "IS_ACTIVE", "UW_YEAR"],
        index=0,
        key="bridge_breakdown_dimension",
    )
    bridge_summary = (
        joined.groupby(group_option, dropna=False, observed=True)
        .agg(
            Policy_Count=("POLICY_BASE_NO", "nunique"),
            Claim_Count=("Claim_Count", "sum"),
            Gross_Claim=("Gross_Claim", "sum"),
            Total_TSI=("Total_TSI", "sum"),
            Max_Claim=("Max_Claim", "max"),
        )
        .reset_index()
    )
    bridge_summary["Claim_Frequency_%"] = np.where(bridge_summary["Policy_Count"] > 0, bridge_summary["Claim_Count"] / bridge_summary["Policy_Count"] * 100.0, 0.0)
    bridge_summary["Loss_to_TSI_%"] = np.where(bridge_summary["Total_TSI"] > 0, bridge_summary["Gross_Claim"] / bridge_summary["Total_TSI"] * 100.0, 0.0)
    bridge_summary = bridge_summary.sort_values(["Gross_Claim", "Policy_Count"], ascending=[False, False], kind="stable")
    render_horizontal_pair(bridge_summary, group_option, "Policy_Count", "Gross_Claim", "Policy Count", "Gross Claim / IDR Mio")
    render_html_table(bridge_summary, max_rows=300)

    render_card("Policy Investigation Table", "Top policy-level claim amount, termasuk TSI dan claim-to-TSI.")
    inv = joined.sort_values("Gross_Claim", ascending=False, kind="stable").head(300).copy()
    inv = inv[["UW_YEAR", "POLICY_BASE_NO", "COB", "LOB", "IS_ACTIVE", "Policy_Count", "Unit_Count", "Total_TSI", "Claim_Count", "Gross_Claim", "Max_Claim", "Claim_Frequency_%", "Loss_to_TSI_%"]]
    render_html_table(inv, max_rows=300)





def _default_xol_layers() -> pd.DataFrame:


    return pd.DataFrame({
        "Layer": ["Layer 1"],
        "Retention_Mio": ["300.000"],
        "Limit_Mio": ["600.000"],
        "Load_%": [50.0],
    })


def _parse_mio_amount_series(series: pd.Series) -> pd.Series:
    def _parse_one(x):
        if x is None or pd.isna(x):
            return np.nan
        if isinstance(x, (int, float, np.integer, np.floating)):
            return float(x)
        text = str(x).strip().replace(" ", "")
        if text in {"", "nan", "None"}:
            return np.nan


        if "." in text and "," in text:
            text = text.replace(".", "").replace(",", ".")
        elif "." in text:
            parts = text.split(".")
            if len(parts) > 1 and all(len(part) == 3 for part in parts[1:]):
                text = "".join(parts)
        elif "," in text:
            parts = text.split(",")
            if len(parts) > 1 and all(len(part) == 3 for part in parts[1:]):
                text = "".join(parts)
            else:
                text = text.replace(",", ".")
        try:
            return float(text)
        except Exception:
            return np.nan
    return series.apply(_parse_one)


def _format_xol_mio_for_editor(layers_df: pd.DataFrame) -> pd.DataFrame:
    out = layers_df.copy()
    for col in ["Retention_Mio", "Limit_Mio"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").apply(lambda x: _fmt_int(x) if pd.notna(x) else "")
    if "Load_%" in out.columns:
        out["Load_%"] = pd.to_numeric(out["Load_%"], errors="coerce").fillna(0.0)
    return out


def _normalise_xol_layers(layers_df: pd.DataFrame) -> pd.DataFrame:
    if layers_df is None or layers_df.empty:
        return pd.DataFrame(columns=["Layer", "Retention", "Limit", "Load_%", "Layer_Ceiling", "Retention_Mio", "Limit_Mio"])

    out = layers_df.copy()


    if "Retention_Mio" not in out.columns and "Retention" in out.columns:
        out["Retention_Mio"] = pd.to_numeric(out["Retention"], errors="coerce") / 1_000_000
    if "Limit_Mio" not in out.columns and "Limit" in out.columns:
        out["Limit_Mio"] = pd.to_numeric(out["Limit"], errors="coerce") / 1_000_000

    for col in ["Layer", "Retention_Mio", "Limit_Mio", "Load_%"]:
        if col not in out.columns:
            out[col] = "" if col == "Layer" else (0.0 if col == "Load_%" else np.nan)

    out = out[["Layer", "Retention_Mio", "Limit_Mio", "Load_%"]].copy()
    out["Layer"] = out["Layer"].astype("string").fillna("").str.strip()
    out["Retention_Mio"] = _parse_mio_amount_series(out["Retention_Mio"])
    out["Limit_Mio"] = _parse_mio_amount_series(out["Limit_Mio"])
    out["Load_%"] = pd.to_numeric(out["Load_%"], errors="coerce").fillna(0.0).clip(lower=0.0, upper=99.0)
    out = out[(out["Retention_Mio"].notna()) & (out["Limit_Mio"].notna()) & (out["Retention_Mio"] >= 0) & (out["Limit_Mio"] > 0)].copy()
    if out.empty:
        return pd.DataFrame(columns=["Layer", "Retention", "Limit", "Load_%", "Layer_Ceiling", "Retention_Mio", "Limit_Mio"])

    out = out.reset_index(drop=True)
    blank_layer = out["Layer"].eq("")
    if blank_layer.any():
        out.loc[blank_layer, "Layer"] = [f"Layer {i + 1}" for i in out.index[blank_layer]]


    out["Retention"] = out["Retention_Mio"] * 1_000_000
    out["Limit"] = out["Limit_Mio"] * 1_000_000
    out["Layer_Ceiling"] = out["Retention"] + out["Limit"]
    return out


def _resolve_xol_editor_df(returned_value, base_df: pd.DataFrame) -> pd.DataFrame:






    if isinstance(returned_value, pd.DataFrame):
        return returned_value.copy()

    state_value = st.session_state.get("xol_layers_editor")
    if isinstance(state_value, pd.DataFrame):
        return state_value.copy()

    base = base_df.copy() if isinstance(base_df, pd.DataFrame) else _default_xol_layers()
    if isinstance(state_value, dict):
        edited_rows = state_value.get("edited_rows", {}) or {}
        for idx, changes in list(edited_rows.items()):
            try:
                i = int(idx)
                for col, val in list(changes.items()):
                    if col in base.columns and 0 <= i < len(base):
                        base.loc[i, col] = val
            except Exception:
                pass

        deleted_rows = sorted([int(i) for i in state_value.get("deleted_rows", []) or [] if str(i).isdigit()], reverse=True)
        if deleted_rows:
            base = base.drop(index=[i for i in deleted_rows if i in base.index], errors="ignore").reset_index(drop=True)

        added_rows = state_value.get("added_rows", []) or []
        if added_rows:
            add_df = pd.DataFrame(added_rows)
            for c in list(base.columns):
                if c not in list(add_df.columns):
                    add_df[c] = np.nan
            base_cols_snapshot = list(base.columns)
            base = pd.concat([base, add_df[base_cols_snapshot]], ignore_index=True)

    return base


def calculate_xol_model(policy_df: pd.DataFrame, claim_df: pd.DataFrame, layers_df: pd.DataFrame) -> pd.DataFrame:










    layers = _normalise_xol_layers(layers_df)
    if policy_df is None or claim_df is None or policy_df.empty or claim_df.empty or layers.empty:
        return pd.DataFrame()

    p = policy_df.copy()
    c = claim_df.copy()
    p["UW_YEAR"] = pd.to_numeric(p["UW_YEAR"], errors="coerce")
    c["UW_YEAR"] = pd.to_numeric(c["UW_YEAR"], errors="coerce")
    p = p[p["UW_YEAR"].between(2021, 2026, inclusive="both")].copy()
    c = c[c["UW_YEAR"].between(2021, 2026, inclusive="both")].copy()
    if p.empty or c.empty:
        return pd.DataFrame()

    p["OR"] = pd.to_numeric(p["OR"], errors="coerce").fillna(0.0)
    c["GROSS CLAIM"] = pd.to_numeric(c["GROSS CLAIM"], errors="coerce").fillna(0.0)

    rows = []
    years = sorted(set(p["UW_YEAR"].dropna().astype(int).tolist()).union(set(c["UW_YEAR"].dropna().astype(int).tolist())))
    years = [y for y in years if 2021 <= y <= 2026]

    for _, layer in layers.iterrows():
        layer_name = str(layer["Layer"])
        retention = float(layer["Retention"])
        limit = float(layer["Limit"])
        load_pct = float(layer.get("Load_%", 0.0))
        load_dec = min(max(load_pct / 100.0, 0.0), 0.99)
        ceiling = float(layer["Layer_Ceiling"])

        for year in years:
            py = p[p["UW_YEAR"].astype("Int64") == year]
            cy = c[c["UW_YEAR"].astype("Int64") == year]


            py_eligible = py[py["OR"] > retention]
            exposure_jjt = int(py_eligible["JJT"].nunique()) if "JJT" in py_eligible.columns else int(len(py_eligible))
            exposure_policy = int(py_eligible["POLICY_BASE_NO"].nunique()) if "POLICY_BASE_NO" in py_eligible.columns else exposure_jjt

            cy = cy.copy()
            cy["Layer_Claim"] = np.minimum(np.maximum(cy["GROSS CLAIM"] - retention, 0.0), limit)
            cy_layer = cy[cy["Layer_Claim"] > 0]
            claim_events = int(cy_layer["CLAIM NO"].nunique()) if "CLAIM NO" in cy_layer.columns else int(len(cy_layer))
            total_on_layer = float(cy_layer["Layer_Claim"].sum()) if not cy_layer.empty else 0.0
            avg_on_layer = float(cy_layer["Layer_Claim"].mean()) if claim_events > 0 else 0.0
            frequency = (claim_events / exposure_jjt) if exposure_jjt > 0 else 0.0
            pure_premium = frequency * avg_on_layer
            loaded_premium = pure_premium / (1.0 - load_dec) if load_dec < 1.0 else np.nan
            expected_loss = pure_premium * exposure_jjt
            loaded_expected_loss = loaded_premium * exposure_jjt if pd.notna(loaded_premium) else np.nan

            rows.append({
                "Layer": layer_name,
                "UW_YEAR": int(year),
                "Retention": retention,
                "Limit": limit,
                "Load_%": load_pct,
                "Layer_Ceiling": ceiling,
                "Exposure_JJT": exposure_jjt,
                "Exposure_Policy": exposure_policy,
                "Claim_Events": claim_events,
                "Frequency_%": frequency * 100.0,
                "Average_On_Layer_Severity": avg_on_layer,
                "Pure_Premium": pure_premium,
                "Loaded_Premium": loaded_premium,
                "Expected_Loss": expected_loss,
                "Loaded_Expected_Loss": loaded_expected_loss,
                "Total_On_Layer_Claim": total_on_layer,
            })

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(["Layer", "UW_YEAR"], kind="stable").reset_index(drop=True)
    return result


def _summarise_xol_by_layer(xol_df: pd.DataFrame) -> pd.DataFrame:
    if xol_df is None or xol_df.empty:
        return pd.DataFrame()
    out = (
        xol_df.groupby("Layer", dropna=False, observed=True)
        .agg(**{
            "Retention": ("Retention", "first"),
            "Limit": ("Limit", "first"),
            "Load_%": ("Load_%", "first"),
            "Layer_Ceiling": ("Layer_Ceiling", "first"),
            "Exposure_JJT": ("Exposure_JJT", "sum"),
            "Exposure_Policy": ("Exposure_Policy", "sum"),
            "Claim_Events": ("Claim_Events", "sum"),
            "Total_On_Layer_Claim": ("Total_On_Layer_Claim", "sum"),
            "Expected_Loss": ("Expected_Loss", "sum"),
            "Loaded_Expected_Loss": ("Loaded_Expected_Loss", "sum"),
        })
        .reset_index()
    )
    out["Frequency_%"] = np.where(out["Exposure_JJT"] > 0, out["Claim_Events"] / out["Exposure_JJT"] * 100.0, 0.0)
    out["Average_On_Layer_Severity"] = np.where(out["Claim_Events"] > 0, out["Total_On_Layer_Claim"] / out["Claim_Events"], 0.0)
    out["Pure_Premium"] = np.where(out["Exposure_JJT"] > 0, out["Expected_Loss"] / out["Exposure_JJT"], 0.0)
    out["Loaded_Premium"] = np.where(out["Exposure_JJT"] > 0, out["Loaded_Expected_Loss"] / out["Exposure_JJT"], 0.0)
    return out


def render_xol_model(policy_df: pd.DataFrame, claim_df: pd.DataFrame) -> None:
    render_card(
        "Excess of Loss Model",
        "Layer bersifat staged/lazy: edit dan tambah layer tidak menghitung ulang sampai tombol Proses XOL diklik. Exposure dan klaim otomatis dibatasi UW Year 2021-2026.",
    )

    st.caption(
        "Formula: On-layer claim = min(max(Gross Claim - OR, 0), Limit). "
        "Pure Premium = Frequency × Average On-Layer Severity. Loaded Premium = Pure Premium / (1 - Load%). "
        "Input OR dan Limit di bawah menggunakan IDR Mio, jadi 300.000 = 300 Bio."
    )

    if "xol_layers_staged" not in st.session_state:
        st.session_state["xol_layers_staged"] = _default_xol_layers()


    st.session_state["xol_layers_staged"] = _format_xol_mio_for_editor(
        _normalise_xol_layers(st.session_state["xol_layers_staged"])[["Layer", "Retention_Mio", "Limit_Mio", "Load_%"]].copy()
    )

    with st.form("xol_layers_form", clear_on_submit=False):
        edited_layers = st.data_editor(
            st.session_state["xol_layers_staged"],
            hide_index=True,
            num_rows="dynamic",
            width='stretch',
            key="xol_layers_editor",
            column_config={
                "Layer": st.column_config.TextColumn("Layer", help="Contoh: Layer 1"),
                "Retention_Mio": st.column_config.TextColumn(
                    "OR / Retention (IDR Mio)",
                    help="Gunakan pemisah ribuan. Contoh: 300.000 = 300 Bio",
                ),
                "Limit_Mio": st.column_config.TextColumn(
                    "Limit (IDR Mio)",
                    help="Gunakan pemisah ribuan. Contoh: 600.000 = 600 Bio",
                ),
                "Load_%": st.column_config.NumberColumn("Load (%)", min_value=0.0, max_value=99.0, step=1.0, format="%.1f"),
            },
        )
        process_xol = st.form_submit_button("Proses XOL", type="primary", width='stretch')

    if process_xol:
        raw_layers = _resolve_xol_editor_df(edited_layers, st.session_state.get("xol_layers_staged", _default_xol_layers()))

        keep_cols = [c for c in ["Layer", "Retention_Mio", "Limit_Mio", "Load_%"] if c in raw_layers.columns]
        st.session_state["xol_layers_staged"] = raw_layers[keep_cols].copy() if keep_cols else _default_xol_layers()
        cleaned_layers = _normalise_xol_layers(raw_layers)
        if cleaned_layers.empty:
            st.warning("Isi minimal 1 layer dengan OR dan Limit yang valid.")
            st.session_state["xol_result"] = pd.DataFrame()
        else:
            st.session_state["xol_layers_staged"] = _format_xol_mio_for_editor(
                cleaned_layers[["Layer", "Retention_Mio", "Limit_Mio", "Load_%"]].copy()
            )
            st.session_state["xol_layers_processed"] = cleaned_layers.copy()
            st.session_state["xol_result"] = calculate_xol_model(policy_df, claim_df, cleaned_layers)
            st.session_state["xol_processed"] = True

    if not st.session_state.get("xol_processed", False):
        st.info("XOL belum diproses. Tambahkan/edit layer dulu, lalu klik Proses XOL.")
        return

    xol_result = st.session_state.get("xol_result", pd.DataFrame())
    if xol_result is None or xol_result.empty:
        st.warning("Tidak ada hasil XOL untuk filter saat ini.")
        return

    total_exposure = float(xol_result["Exposure_JJT"].sum())
    total_events = float(xol_result["Claim_Events"].sum())
    total_expected = float(xol_result["Expected_Loss"].sum())
    total_loaded_expected = float(xol_result["Loaded_Expected_Loss"].sum()) if "Loaded_Expected_Loss" in xol_result.columns else 0.0
    avg_pure_premium = total_expected / total_exposure if total_exposure else 0.0
    avg_loaded_premium = total_loaded_expected / total_exposure if total_exposure else 0.0
    avg_freq = total_events / total_exposure * 100.0 if total_exposure else 0.0
    total_on_layer = float(xol_result["Total_On_Layer_Claim"].sum())
    avg_layer_severity = total_on_layer / total_events if total_events else 0.0

    render_kpi_grid([
        ("Exposure JJT", _fmt_int(total_exposure)),
        ("Claim Events", _fmt_int(total_events)),
        ("Frequency", _fmt_pct(avg_freq)),
        ("Avg On-Layer Severity / IDR Mio", _fmt_mio(avg_layer_severity)),
        ("Pure Premium / IDR Mio", _fmt_mio(avg_pure_premium)),
        ("Loaded Premium / IDR Mio", _fmt_mio(avg_loaded_premium)),
        ("Loaded Expected / IDR Mio", _fmt_mio(total_loaded_expected)),
    ], six=True)

    layer_summary = _summarise_xol_by_layer(xol_result)
    render_card("Layer Summary", "Ringkasan XOL per layer. Amount ditampilkan dalam IDR Mio.")
    render_html_table(layer_summary, max_rows=100)

    render_card("XOL Result by UW Year", "Detail frequency, severity, dan pure premium per layer dan UW Year.")
    render_html_table(xol_result, max_rows=300)

    chart_df = xol_result.copy()
    chart_df["Pure Premium Mio"] = chart_df["Pure_Premium"] / 1_000_000
    chart_df["Loaded Premium Mio"] = chart_df["Loaded_Premium"] / 1_000_000
    chart_df["Avg Severity Mio"] = chart_df["Average_On_Layer_Severity"] / 1_000_000
    c1, c2 = st.columns(2, gap="large")
    with c1:
        chart = (
            alt.Chart(chart_df)
            .mark_line(point=True, strokeWidth=3)
            .encode(
                x=alt.X("UW_YEAR:O", title="UW Year", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Frequency_%:Q", title="Frequency %"),
                color=alt.Color("Layer:N", title=None),
                tooltip=["Layer:N", "UW_YEAR:O", alt.Tooltip("Frequency_%:Q", title="Frequency %", format=".4f")],
            )
            .properties(height=310, title="XOL Frequency by UW Year")
            .configure_title(anchor="middle", color="#003366", fontSize=15, fontWeight="bold")
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(chart, width='stretch')
    with c2:
        chart = (
            alt.Chart(chart_df)
            .mark_line(point=True, strokeWidth=3)
            .encode(
                x=alt.X("UW_YEAR:O", title="UW Year", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Loaded Premium Mio:Q", title="IDR Mio"),
                color=alt.Color("Layer:N", title=None),
                tooltip=["Layer:N", "UW_YEAR:O", alt.Tooltip("Pure Premium Mio:Q", title="Pure Premium Mio", format=",.0f"), alt.Tooltip("Loaded Premium Mio:Q", title="Loaded Premium Mio", format=",.0f")],
            )
            .properties(height=310, title="XOL Loaded Premium by UW Year")
            .configure_title(anchor="middle", color="#003366", fontSize=15, fontWeight="bold")
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(chart, width='stretch')


def render_trend_section(policy_df: pd.DataFrame, claim_df: pd.DataFrame) -> None:
    render_card("Trend by UW Year", "Policy count dan gross claim dipisah supaya skala tidak saling mengganggu.")
    render_year_trend(policy_df, claim_df)





def _resolve_data_path(default_path: str, upload_key: str, label: str, explicit_path: str | None = None) -> str | None:
    if explicit_path:
        return explicit_path
    if Path(default_path).exists():
        return default_path
    uploaded = st.file_uploader(label, type=["xlsx"], key=upload_key)
    if uploaded is None:
        return None
    temp_path = f"/tmp/{upload_key}.xlsx"
    Path(temp_path).write_bytes(uploaded.getvalue())
    return temp_path


def render_dashboard(
    username: str = "guest",
    policy_path: str | None = None,
    claim_path: str | None = None,
    show_hero: bool = True,
    default_view: str | None = None,
) -> None:
    inject_superapp_css()
    if show_hero:
        render_hero()

    policy_path = _resolve_data_path(POLICY_DATA_PATH, "policy_upload", "Upload policy Excel", explicit_path=policy_path)
    claim_path = _resolve_data_path(CLAIM_DATA_PATH, "claim_upload", "Upload claim Excel", explicit_path=claim_path)
    if policy_path is None or claim_path is None:
        st.info("Letakkan file Excel di folder repo yang sama, atau upload file untuk preview.")
        return

    try:
        policy_df = load_policy_data(policy_path)
        claim_df = load_claim_data(claim_path)
    except Exception as e:
        st.error("Dashboard failed to load data.")
        with st.expander("Technical details", expanded=False):
            st.code(str(e))
        return

    view_options = ["Overview", "Policy Monitoring", "Claim Monitoring", "Policy × Claim", "Trend", "XOL Model"]
    if default_view in view_options and "dashboard_view" not in st.session_state:
        st.session_state["dashboard_view"] = default_view
    view = st.radio(
        "Dashboard view",
        options=view_options,
        key="dashboard_view",
        horizontal=True,
        label_visibility="collapsed",
    )


    if view in ["Overview", "Policy Monitoring", "Policy × Claim", "Trend", "XOL Model"]:
        policy_df = render_tsi_manual_mapping_sidebar(policy_df)

    st.sidebar.markdown("---")
    if view in ["Overview", "Policy Monitoring", "Policy × Claim", "Trend", "XOL Model"]:
        filtered_policy, _ = apply_multiselect_filters(policy_df, POLICY_FILTER_COLS, "policy", "Policy Filters")
    else:
        filtered_policy = policy_df

    st.sidebar.markdown("---")
    if view in ["Overview", "Claim Monitoring", "Policy × Claim", "Trend", "XOL Model"]:
        filtered_claim, _ = apply_multiselect_filters(claim_df, CLAIM_FILTER_COLS, "claim", "Claim Filters")
    else:
        filtered_claim = claim_df

    if filtered_policy.empty and view in ["Overview", "Policy Monitoring", "Policy × Claim", "Trend", "XOL Model"]:
        st.warning("No policy data after filter.")
        return
    if filtered_claim.empty and view in ["Overview", "Claim Monitoring", "Policy × Claim", "Trend", "XOL Model"]:
        st.warning("No claim data after filter.")
        return

    if view == "Overview":
        render_policy_overview(filtered_policy)
        render_claim_overview(filtered_claim)
        render_trend_section(filtered_policy, filtered_claim)
    elif view == "Policy Monitoring":
        render_policy_overview(filtered_policy)
    elif view == "Claim Monitoring":
        render_claim_overview(filtered_claim)
    elif view == "Policy × Claim":
        render_policy_claim_bridge(filtered_policy, filtered_claim)
    elif view == "Trend":
        render_trend_section(filtered_policy, filtered_claim)
    elif view == "XOL Model":
        render_xol_model(filtered_policy, filtered_claim)


def dashboard1(
    username: str = "guest",
    policy_path: str | None = None,
    claim_path: str | None = None,
    show_hero: bool = True,
    default_view: str | None = None,
) -> None:
    try:
        render_dashboard(
            username=username,
            policy_path=policy_path,
            claim_path=claim_path,
            show_hero=show_hero,
            default_view=default_view,
        )
    except Exception as e:
        st.error("Under Reconstruction\n#BakalJadiKeren")
        with st.expander("Technical details", expanded=False):
            st.code(str(e))





def dashboard(
    username: str = "guest",
    policy_path: str | None = None,
    claim_path: str | None = None,
    show_hero: bool = True,
    default_view: str | None = None,
) -> None:
    dashboard1(username, policy_path=policy_path, claim_path=claim_path, show_hero=show_hero, default_view=default_view)


def main(username: str = "guest") -> None:
    dashboard1(username)




def preload_workbooks():
    if Path(POLICY_DATA_PATH).is_file():
        load_policy_data(POLICY_DATA_PATH)
    if Path(CLAIM_DATA_PATH).is_file():
        load_claim_data(CLAIM_DATA_PATH)


if __name__ == "__main__":
    main()
