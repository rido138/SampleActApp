from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import streamlit as st


DATASET_FILENAME = "DATASET Calculator CoR.xlsx"

COLUMN_ALIASES = {
    "LOB": ["LOB", "LoB", "LINE_OF_BUSINESS", "LINE OF BUSINESS"],
    "COB": ["COB", "CoB", "CLASS_OF_BUSINESS", "CLASS OF BUSINESS"],
    "ACCOUNT_NAME": ["ACCOUNT_NAME", "ACCOUNT NAME", "ACCOUNT", "POLICY_HOLDER"],
    "INSURED_NAME": ["INSURED_NAME", "INSURED NAME", "INSURED", "INSURED_NAME_2"],
    "INFO_1": ["INFO_1", "INFO 1", "AUXILIARY_INFORMATION", "AUXILIARY INFORMATION"],
    "TSI": ["TSI", "TSI_AMT", "TOTAL_SUM_INSURED", "TOTAL SUM INSURED"],
    "GWP_AMT": ["GWP_AMT", "GWP", "GROSS_WRITTEN_PREMIUM"],
    "GEP_AMT": ["GEP_AMT", "GEP", "GROSS_EARNED_PREMIUM"],
    "GROSS_CLAIM": ["GROSS_CLAIM", "GROSS CLAIM", "GROSS_CLAIM_AMT"],
    "RI_COST": ["RI_COST", "RI COST", "REINSURANCE_COST"],
    "RI_RECOVERY": ["RI_RECOVERY", "RI RECOVERY", "REINSURANCE_RECOVERY"],
}

TEXT_COLUMNS = ["LOB", "COB", "ACCOUNT_NAME", "INSURED_NAME", "INFO_1"]
NUMERIC_COLUMNS = ["TSI", "GWP_AMT", "GEP_AMT", "GROSS_CLAIM", "RI_COST", "RI_RECOVERY"]

FIXED_EXPENSE_RATIO_PCT = 15.0
MV_RI_COST_ADDITION_PCT = 3.0


def _first_existing_column(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    existing = {str(col).strip(): col for col in columns}
    existing_upper = {str(col).strip().upper(): col for col in columns}

    for candidate in candidates:
        if candidate in existing:
            return existing[candidate]
        candidate_upper = str(candidate).strip().upper()
        if candidate_upper in existing_upper:
            return existing_upper[candidate_upper]
    return None


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: dict[str, str] = {}

    for canonical_name, aliases in COLUMN_ALIASES.items():
        matched = _first_existing_column(df.columns, aliases)
        if matched is not None and matched != canonical_name:
            rename_map[matched] = canonical_name

    if rename_map:
        df = df.rename(columns=rename_map)

    return df


def _optimize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()

    for column in TEXT_COLUMNS:
        if column not in data.columns:
            continue
        fallback = "" if column == "COB" else "Unspecified"
        data[column] = data[column].fillna(fallback).astype(str).str.strip()

    if "COB" in data.columns:
        data["COB"] = data["COB"].str.upper()

    for column in NUMERIC_COLUMNS:
        if column not in data.columns:
            continue
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
        data[column] = pd.to_numeric(data[column], downcast="float")

    row_count = max(len(data), 1)
    for column in TEXT_COLUMNS:
        if column not in data.columns:
            continue
        try:
            unique_ratio = data[column].nunique(dropna=False) / row_count
            if unique_ratio <= 0.50:
                data[column] = data[column].astype("category")
        except Exception:
            pass

    return data


def _load_combined_ratio_dataset(dataset_path: str, modified_ns: int) -> pd.DataFrame:

    _ = modified_ns
    raw = pd.read_excel(dataset_path)
    standardized = _standardize_columns(raw)
    return _optimize_dataframe(standardized)


def _safe_ratio_pct(numerator: float, denominator: float) -> float:
    try:
        numerator = float(numerator)
        denominator = float(denominator)
    except (TypeError, ValueError):
        return 0.0

    if denominator == 0 or not np.isfinite(denominator):
        return 0.0
    if not np.isfinite(numerator):
        return 0.0
    return numerator / denominator * 100.0


def _sorted_text_options(series: pd.Series) -> list[str]:
    values = series.dropna().astype(str).str.strip()
    return sorted(value for value in values.unique().tolist() if value)


def _filter_multi_text(df: pd.DataFrame, column: str, selected_values) -> pd.DataFrame:

    selected = [str(value) for value in (selected_values or []) if str(value).strip()]
    if not selected:
        return df
    return df[df[column].astype(str).isin(selected)]


def _sanitize_multiselect_state(key: str, options: list[str], default=None) -> None:

    valid_options = set(options)
    if key in st.session_state:
        st.session_state[key] = [
            value for value in (st.session_state.get(key) or [])
            if value in valid_options
        ]
    elif default is not None:
        st.session_state[key] = [value for value in default if value in valid_options]


def _selection_signature(*values: object) -> tuple[str, ...]:
    normalized = []
    for value in values:
        if isinstance(value, (list, tuple, set)):
            normalized.append("|".join(sorted(str(item) for item in value)))
        else:
            normalized.append(str(value))
    return tuple(normalized)


def _inject_combined_ratio_css() -> None:
    st.markdown(
        """
        <style>
          .cor-subapp-wrap {
            --navy: #0B2748;
            --blue: #155EEF;
            --muted: #64748B;
            --line: #E3EAF2;
          }

          .cor-subapp-wrap .cor-hero {
            padding: .45rem 0 1rem 0;
            border-bottom: 1px solid var(--line);
            margin-bottom: 1.2rem;
          }

          .cor-subapp-wrap .cor-kicker {
            color: var(--blue);
            font-size: .72rem;
            font-weight: 800;
            letter-spacing: .12em;
            text-transform: uppercase;
            margin-bottom: .3rem;
          }

          .cor-subapp-wrap .cor-title {
            color: var(--navy);
            font-size: clamp(1.9rem, 3vw, 2.8rem);
            font-weight: 850;
            letter-spacing: -.04em;
            line-height: 1.05;
            margin: 0;
          }

          .cor-subapp-wrap .cor-subtitle {
            color: var(--muted);
            font-size: .93rem;
            margin-top: .45rem;
          }

          .cor-section-label {
            color: #0B2748;
            font-size: .76rem;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: .09em;
            margin: .1rem 0 .62rem 0;
          }

          div[data-testid="stMetric"] {
            background: rgba(255,255,255,.96);
            border: 1px solid #E3EAF2;
            border-radius: 18px;
            padding: 1rem 1.05rem;
            min-height: 118px;
            box-shadow: 0 10px 26px rgba(11,39,72,.045);
          }

          div[data-testid="stMetricLabel"] {
            color: #64748B;
            font-size: .82rem;
            font-weight: 750;
          }

          div[data-testid="stMetricValue"] {
            color: #0B2748;
            font-size: 1.8rem;
            font-weight: 850;
            letter-spacing: -.035em;
          }

          div[data-testid="stForm"] {
            border: 0;
            padding: 0;
          }

          div[data-testid="stFormSubmitButton"] button {
            min-height: 44px;
            border: 0;
            border-radius: 12px;
            background: #0B2748;
            color: #FFFFFF;
            font-weight: 850;
          }

          div[data-testid="stFormSubmitButton"] button:hover {
            background: #155EEF;
            color: #FFFFFF;
          }

          .cor-result-panel {
            padding: 1.25rem 1.4rem;
            border-radius: 20px;
            color: white;
            box-shadow: 0 16px 36px rgba(11,39,72,.12);
          }

          .cor-result-panel.good {
            background: linear-gradient(135deg, #075C46 0%, #0C8A65 100%);
          }

          .cor-result-panel.bad {
            background: linear-gradient(135deg, #8E1B2A 0%, #C92A3A 100%);
          }

          .cor-result-panel.neutral {
            background: linear-gradient(135deg, #173A65 0%, #155EEF 100%);
          }

          .cor-result-label {
            font-size: .76rem;
            font-weight: 800;
            letter-spacing: .1em;
            text-transform: uppercase;
            opacity: .84;
          }

          .cor-result-value {
            font-size: clamp(2.5rem, 4.5vw, 4.2rem);
            line-height: 1;
            font-weight: 900;
            letter-spacing: -.055em;
            margin-top: .32rem;
          }

          .cor-result-status {
            margin-top: .5rem;
            font-size: .92rem;
            font-weight: 700;
            opacity: .94;
          }

          .cor-formula-row {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: .65rem;
            margin-top: 1rem;
          }

          .cor-formula-item {
            background: rgba(255,255,255,.94);
            border: 1px solid #E3EAF2;
            border-radius: 14px;
            padding: .76rem .82rem;
          }

          .cor-formula-name {
            color: #64748B;
            font-size: .67rem;
            font-weight: 800;
            letter-spacing: .04em;
            text-transform: uppercase;
          }

          .cor-formula-value {
            color: #0B2748;
            font-size: 1.05rem;
            font-weight: 850;
            margin-top: .16rem;
          }

          @media (max-width: 1000px) {
            .cor-formula-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_combined_ratio_simulator() -> None:


    dataset_path = Path(__file__).resolve().parent / DATASET_FILENAME
    if not dataset_path.exists():
        st.error(f"Dataset not found: {DATASET_FILENAME}")
        return

    try:
        data = _load_combined_ratio_dataset(
            str(dataset_path),
            dataset_path.stat().st_mtime_ns,
        )
    except Exception as exc:
        st.error(f"Unable to load dataset: {exc}")
        return

    required_columns = set(TEXT_COLUMNS + NUMERIC_COLUMNS)
    missing_columns = sorted(required_columns.difference(data.columns))
    if missing_columns:
        st.error("Missing required columns: " + ", ".join(missing_columns))
        return

    _inject_combined_ratio_css()

    st.markdown(
        """
        <div class="cor-subapp-wrap">
          <div class="cor-hero">
            <div class="cor-kicker">Portfolio Analytics</div>
            <h1 class="cor-title">Combined Ratio Simulator</h1>
            <div class="cor-subtitle">Select a portfolio segment and test revised premium-rate assumptions.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="cor-section-label">Portfolio Selection</div>', unsafe_allow_html=True)

    lob_options = _sorted_text_options(data["LOB"])
    if not lob_options:
        st.error("No Line of Business data is available.")
        return

    row_1_col_1, row_1_col_2 = st.columns(2, gap="medium")

    _sanitize_multiselect_state(
        "cor_simulator_lob",
        lob_options,
        default=lob_options[:1],
    )
    with row_1_col_1:
        selected_lob = st.multiselect(
            "Line of Business",
            lob_options,
            key="cor_simulator_lob",
            placeholder="Select one or more LoB",
        )

    if not selected_lob:
        st.info("Select at least one Line of Business.")
        return

    lob_df = _filter_multi_text(data, "LOB", selected_lob)

    account_options = _sorted_text_options(lob_df["ACCOUNT_NAME"])
    _sanitize_multiselect_state("cor_simulator_account_name", account_options)
    with row_1_col_2:
        selected_account = st.multiselect(
            "Account Name",
            account_options,
            key="cor_simulator_account_name",
            placeholder="All account names",
        )

    account_df = _filter_multi_text(lob_df, "ACCOUNT_NAME", selected_account)

    row_2_col_1, row_2_col_2 = st.columns(2, gap="medium")

    insured_options = _sorted_text_options(account_df["INSURED_NAME"])
    _sanitize_multiselect_state("cor_simulator_insured_name", insured_options)
    with row_2_col_1:
        selected_insured = st.multiselect(
            "Insured Name",
            insured_options,
            key="cor_simulator_insured_name",
            placeholder="All insured names",
        )

    insured_df = _filter_multi_text(account_df, "INSURED_NAME", selected_insured)

    info_options = _sorted_text_options(insured_df["INFO_1"])
    _sanitize_multiselect_state("cor_simulator_info_1", info_options)
    with row_2_col_2:
        selected_info = st.multiselect(
            "Auxiliary Information",
            info_options,
            key="cor_simulator_info_1",
            placeholder="All auxiliary information",
        )

    portfolio = _filter_multi_text(insured_df, "INFO_1", selected_info)
    if portfolio.empty:
        st.error("No portfolio data is available for the selected combination.")
        return

    totals = portfolio[NUMERIC_COLUMNS].sum(numeric_only=True)

    old_loss_ratio = _safe_ratio_pct(totals["GROSS_CLAIM"], totals["GEP_AMT"])
    current_premium_rate = _safe_ratio_pct(totals["GWP_AMT"], totals["TSI"])
    ri_cost_ratio_base = _safe_ratio_pct(totals["RI_COST"], totals["GWP_AMT"])
    ri_recovery_ratio = _safe_ratio_pct(totals["RI_RECOVERY"], totals["GEP_AMT"])

    cob_values = set(portfolio["COB"].dropna().astype(str).str.strip().str.upper())
    is_mv_portfolio = cob_values == {"MV"}
    ri_cost_ratio = ri_cost_ratio_base + (MV_RI_COST_ADDITION_PCT if is_mv_portfolio else 0.0)

    st.markdown(
        '<div class="cor-section-label" style="margin-top:1.2rem">Current Portfolio Ratios</div>',
        unsafe_allow_html=True,
    )

    metric_1, metric_2, metric_3, metric_4 = st.columns(4, gap="medium")
    metric_1.metric("Current Loss Ratio", f"{old_loss_ratio:,.2f}%")
    metric_2.metric("Current Premium Rate", f"{current_premium_rate:,.4f}%")
    metric_3.metric("RI Cost Ratio", f"{ri_cost_ratio:,.2f}%")
    metric_4.metric("RI Recovery Ratio", f"{ri_recovery_ratio:,.2f}%")

    st.markdown(
        '<div class="cor-section-label" style="margin-top:1.3rem">Simulation Inputs</div>',
        unsafe_allow_html=True,
    )

    form_signature = _selection_signature(
        selected_lob,
        selected_account,
        selected_insured,
        selected_info,
    )

    default_rate = max(round(current_premium_rate, 4), 0.0001)




    rate_signature_key = "cor_simulator_rate_selection_signature"
    rate_input_key = "cor_simulator_new_rate_pct"
    previous_rate_signature = st.session_state.get(rate_signature_key)
    if previous_rate_signature != form_signature:
        st.session_state[rate_input_key] = default_rate
        st.session_state[rate_signature_key] = form_signature
        st.session_state.pop("cor_simulation_result", None)

    with st.form("cor_simulation_form", clear_on_submit=False):
        input_col_1, input_col_2, input_col_3 = st.columns(3, gap="medium")

        with input_col_1:
            new_premium_rate = st.number_input(
                "New Premium Rate (%)",
                min_value=0.0001,
                max_value=100.0,
                step=0.0001,
                format="%.4f",
                key=rate_input_key,
            )

        with input_col_2:
            commission_pct = st.number_input(
                "Commission (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.25,
                format="%.2f",
                key="cor_simulator_commission_pct",
            )

        with input_col_3:
            ovr_pct = st.number_input(
                "OVR (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.25,
                format="%.2f",
                key="cor_simulator_ovr_pct",
            )

        button_col, button_spacer = st.columns([0.18, 0.82], gap="small")
        with button_col:
            simulate_clicked = st.form_submit_button(
                "Simulate",
                use_container_width=True,
            )

    if simulate_clicked:
        revised_loss_ratio = (
            old_loss_ratio * current_premium_rate / new_premium_rate
            if current_premium_rate > 0 and new_premium_rate > 0
            else 0.0
        )

        combined_ratio = (
            revised_loss_ratio
            + commission_pct
            + ovr_pct
            + FIXED_EXPENSE_RATIO_PCT
            + ri_cost_ratio
            - ri_recovery_ratio
        )

        st.session_state["cor_simulation_result"] = {
            "selection_signature": form_signature,
            "old_loss_ratio": old_loss_ratio,
            "current_premium_rate": current_premium_rate,
            "new_premium_rate": float(new_premium_rate),
            "revised_loss_ratio": revised_loss_ratio,
            "commission_pct": float(commission_pct),
            "ovr_pct": float(ovr_pct),
            "expense_ratio": FIXED_EXPENSE_RATIO_PCT,
            "ri_cost_ratio": ri_cost_ratio,
            "ri_recovery_ratio": ri_recovery_ratio,
            "combined_ratio": combined_ratio,
        }

    result = st.session_state.get("cor_simulation_result")
    if not isinstance(result, dict):
        return
    if tuple(result.get("selection_signature", ())) != form_signature:
        return

    combined_ratio = float(result["combined_ratio"])
    if combined_ratio < 100.0:
        panel_class = "good"
        status_text = f"Underwriting margin: {100.0 - combined_ratio:,.2f}%"
    elif combined_ratio > 100.0:
        panel_class = "bad"
        status_text = f"Underwriting deficit: {combined_ratio - 100.0:,.2f}%"
    else:
        panel_class = "neutral"
        status_text = "Break-even portfolio"

    st.markdown(
        '<div class="cor-section-label" style="margin-top:1.35rem">Simulation Result</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="cor-result-panel {panel_class}">
          <div class="cor-result-label">Simulated Combined Ratio</div>
          <div class="cor-result-value">{combined_ratio:,.2f}%</div>
          <div class="cor-result-status">{status_text}</div>
        </div>

        <div class="cor-formula-row">
          <div class="cor-formula-item">
            <div class="cor-formula-name">Old Loss Ratio</div>
            <div class="cor-formula-value">{result['old_loss_ratio']:,.2f}%</div>
          </div>
          <div class="cor-formula-item">
            <div class="cor-formula-name">Old Premium Rate</div>
            <div class="cor-formula-value">{result['current_premium_rate']:,.4f}%</div>
          </div>
          <div class="cor-formula-item">
            <div class="cor-formula-name">New Premium Rate</div>
            <div class="cor-formula-value">{result['new_premium_rate']:,.4f}%</div>
          </div>
          <div class="cor-formula-item">
            <div class="cor-formula-name">Revised Loss Ratio</div>
            <div class="cor-formula-value">{result['revised_loss_ratio']:,.2f}%</div>
          </div>
          <div class="cor-formula-item">
            <div class="cor-formula-name">Commission</div>
            <div class="cor-formula-value">{result['commission_pct']:,.2f}%</div>
          </div>
          <div class="cor-formula-item">
            <div class="cor-formula-name">OVR</div>
            <div class="cor-formula-value">{result['ovr_pct']:,.2f}%</div>
          </div>
          <div class="cor-formula-item">
            <div class="cor-formula-name">Expense Ratio</div>
            <div class="cor-formula-value">{result['expense_ratio']:,.2f}%</div>
          </div>
          <div class="cor-formula-item">
            <div class="cor-formula-name">RI Cost Ratio</div>
            <div class="cor-formula-value">{result['ri_cost_ratio']:,.2f}%</div>
          </div>
          <div class="cor-formula-item">
            <div class="cor-formula-name">RI Recovery Ratio</div>
            <div class="cor-formula-value">−{result['ri_recovery_ratio']:,.2f}%</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def preload_workbooks():
    path = Path(__file__).resolve().parent / DATASET_FILENAME
    _load_combined_ratio_dataset(str(path), path.stat().st_mtime_ns)


