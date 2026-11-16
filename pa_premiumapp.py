import io
import math
from pathlib import Path

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

# =========================================================
# PAGE CONFIG
# =========================================================
try:
    st.set_page_config(
        page_title="PA Premium Calculator",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    # Allows this module to be called from a parent Streamlit app that already set page config.
    pass

# =========================================================
# BACKEND CONSTANTS - INTERNAL ONLY
# =========================================================
CORRELATION = 0.75
LOWER_RATE = 0.80
UPPER_RATE = 0.95
OPEX = 0.15
PROFIT = 0.05
DECREMENT_FILE = "decrement pa umum.xlsx"
DECREMENT_COLS = ["Meninggal", "Luka Berat", "Luka Ringan"]

# =========================================================
# ENTERPRISE THEME
# =========================================================
def inject_enterprise_css():
    """Enterprise styling scoped to the main app only.

    Important: this module is often called from a parent SuperApp that owns
    the sidebar navigation. Therefore no selector below targets the sidebar,
    and every Streamlit widget selector is scoped to the main section.
    """
    st.markdown(
        """
<style>
:root {
  --pa-bg-0: #F3F6FA;
  --pa-bg-1: #EAF0F7;
  --pa-navy: #0B1F35;
  --pa-navy-2: #123A5D;
  --pa-blue: #1C5DAA;
  --pa-gold: #B68A35;
  --pa-ink: #182230;
  --pa-muted: #667085;
  --pa-line: #D7DFEA;
  --pa-card: rgba(255,255,255,0.96);
}

/* MAIN AREA ONLY — never touch the sidebar navigation */
section.main,
section[data-testid="stMain"] {
  background:
    radial-gradient(circle at 8% 0%, rgba(28, 93, 170, 0.13), transparent 30%),
    radial-gradient(circle at 96% 6%, rgba(182, 138, 53, 0.12), transparent 26%),
    linear-gradient(180deg, var(--pa-bg-0) 0%, var(--pa-bg-1) 100%);
  color: var(--pa-ink);
  font-family: Inter, "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif;
}

section.main .block-container,
section[data-testid="stMain"] .block-container {
  max-width: 1220px;
  padding-top: 1.55rem;
  padding-bottom: 3rem;
}

section.main h1,
section[data-testid="stMain"] h1 {
  display: none !important;
}

section.main h1,
section.main h2,
section.main h3,
section.main p,
section.main label,
section[data-testid="stMain"] h1,
section[data-testid="stMain"] h2,
section[data-testid="stMain"] h3,
section[data-testid="stMain"] p,
section[data-testid="stMain"] label {
  font-family: Inter, "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif;
}

.pa-hero {
  background: linear-gradient(135deg, #0B1F35 0%, #123A5D 57%, #1B5A90 100%);
  border: 1px solid rgba(255,255,255,0.16);
  border-radius: 24px;
  padding: 28px 32px;
  margin: 0 0 22px 0;
  box-shadow: 0 22px 48px rgba(11,31,53,0.18);
  position: relative;
  overflow: hidden;
}
.pa-hero:before {
  content: "";
  position: absolute;
  right: -90px;
  top: -120px;
  width: 330px;
  height: 330px;
  border-radius: 50%;
  background: rgba(182,138,53,0.18);
}
.pa-hero-kicker {
  color: #D7B36A;
  font-size: 0.76rem;
  line-height: 1;
  font-weight: 850;
  letter-spacing: 0.17em;
  text-transform: uppercase;
  margin-bottom: 10px;
}
.pa-hero-title {
  color: #FFFFFF;
  font-size: 2.05rem;
  line-height: 1.14;
  font-weight: 860;
  letter-spacing: -0.035em;
  margin-bottom: 9px;
  max-width: 780px;
}
.pa-hero-subtitle {
  color: rgba(255,255,255,0.78);
  font-size: 1rem;
  line-height: 1.55;
  font-weight: 450;
  max-width: 790px;
}
.pa-hero-badges {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 18px;
}
.pa-badge {
  background: rgba(255,255,255,0.10);
  border: 1px solid rgba(255,255,255,0.16);
  color: #FFFFFF;
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 0.82rem;
  font-weight: 700;
}

/* Bordered containers in MAIN only */
section.main [data-testid="stVerticalBlockBorderWrapper"],
section[data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--pa-card) !important;
  border: 1px solid var(--pa-line) !important;
  border-radius: 20px !important;
  box-shadow: 0 14px 34px rgba(11,31,53,0.085) !important;
}

.pa-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #E6ECF3;
  padding-bottom: 10px;
  margin-bottom: 16px;
}
.pa-section-kicker {
  color: var(--pa-gold);
  font-size: 0.72rem;
  font-weight: 900;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  margin-bottom: 4px;
}
.pa-section-title {
  color: var(--pa-navy);
  font-size: 1.12rem;
  font-weight: 840;
  letter-spacing: -0.02em;
}
.pa-section-note {
  color: var(--pa-muted);
  font-size: 0.84rem;
  font-weight: 600;
}

/* Inputs/buttons in MAIN only. Sidebar buttons and menus are intentionally untouched. */
section.main .stTextInput label,
section.main .stNumberInput label,
section[data-testid="stMain"] .stTextInput label,
section[data-testid="stMain"] .stNumberInput label {
  color: #344054 !important;
  font-size: 0.88rem !important;
  font-weight: 780 !important;
}
section.main .stTextInput input,
section.main .stNumberInput input,
section[data-testid="stMain"] .stTextInput input,
section[data-testid="stMain"] .stNumberInput input {
  border-radius: 12px !important;
  border: 1px solid #C9D4E2 !important;
  background: #FFFFFF !important;
  min-height: 43px !important;
  font-weight: 700 !important;
  color: #101828 !important;
  box-shadow: inset 0 1px 0 rgba(16,24,40,0.03) !important;
}
section.main .stTextInput input:focus,
section.main .stNumberInput input:focus,
section[data-testid="stMain"] .stTextInput input:focus,
section[data-testid="stMain"] .stNumberInput input:focus {
  border-color: #1C5DAA !important;
  box-shadow: 0 0 0 3px rgba(28,93,170,0.10) !important;
}

section.main .stButton > button,
section.main .stDownloadButton > button,
section[data-testid="stMain"] .stButton > button,
section[data-testid="stMain"] .stDownloadButton > button {
  background: linear-gradient(135deg, #1C5DAA 0%, #0B1F35 100%) !important;
  color: #FFFFFF !important;
  border: 0 !important;
  border-radius: 13px !important;
  padding: 0.82rem 1.45rem !important;
  min-height: 46px !important;
  font-weight: 840 !important;
  letter-spacing: -0.01em !important;
  box-shadow: 0 13px 26px rgba(28,93,170,0.24) !important;
}
section.main .stButton > button:hover,
section.main .stDownloadButton > button:hover,
section[data-testid="stMain"] .stButton > button:hover,
section[data-testid="stMain"] .stDownloadButton > button:hover {
  filter: brightness(1.045) !important;
  transform: translateY(-1px);
}

.pa-result-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 4px;
}
.pa-metric-card {
  background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFD 100%);
  border: 1px solid #DDE5EF;
  border-radius: 18px;
  padding: 18px 18px 16px 18px;
  box-shadow: 0 10px 24px rgba(11,31,53,0.07);
}
.pa-metric-card.primary {
  background: linear-gradient(135deg, #0B1F35 0%, #174E7A 100%);
  border-color: rgba(255,255,255,0.12);
}
.pa-metric-label {
  color: #667085;
  font-size: 0.78rem;
  font-weight: 850;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.pa-metric-value {
  color: #0B1F35;
  font-size: 1.72rem;
  line-height: 1.05;
  font-weight: 900;
  letter-spacing: -0.04em;
}
.pa-metric-card.primary .pa-metric-label { color: rgba(255,255,255,0.70); }
.pa-metric-card.primary .pa-metric-value { color: #FFFFFF; }
.pa-total-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  background: #F7F9FC;
  border: 1px solid #E2E8F0;
  border-radius: 17px;
  padding: 12px;
  margin-top: 16px;
}
.pa-mini-label { color: #667085; font-size: 0.76rem; font-weight: 800; margin-bottom: 4px; }
.pa-mini-value { color: #0B1F35; font-size: 1.1rem; font-weight: 880; }

.pa-download-wrap {
  background: linear-gradient(180deg, #FFFFFF 0%, #F9FBFD 100%);
  border: 1px solid #DCE4EF;
  border-radius: 18px;
  padding: 18px;
  margin-top: 14px;
  box-shadow: 0 12px 28px rgba(11,31,53,0.06);
}

section.main div[data-testid="stAlert"],
section[data-testid="stMain"] div[data-testid="stAlert"] {
  border-radius: 14px !important;
  border: 1px solid #D7DFEA !important;
}

@media (max-width: 860px) {
  .pa-result-grid, .pa-total-strip { grid-template-columns: 1fr; }
  .pa-hero-title { font-size: 1.55rem; }
}
</style>
""",
        unsafe_allow_html=True,
    )


# =========================================================
# HELPERS
# =========================================================
def format_idr(value) -> str:
    try:
        return f"{float(value):,.0f}".replace(",", ".")
    except Exception:
        return "0"


def parse_int_text(value) -> int:
    cleaned = str(value).replace(".", "").replace(",", "").strip()
    if cleaned == "":
        return 0
    try:
        return int(float(cleaned))
    except Exception:
        return 0


def money_input(label: str, default: int, key: str, help_text: str | None = None) -> int:
    raw = st.text_input(label, value=format_idr(default), key=key, help=help_text)
    return parse_int_text(raw)


@st.cache_data(show_spinner=False, ttl=900, max_entries=3)
def load_decrement_table() -> pd.DataFrame:
    candidates = [
        Path(DECREMENT_FILE),
        Path(__file__).resolve().parent / DECREMENT_FILE,
        Path.cwd() / DECREMENT_FILE,
        Path("/mnt/data") / DECREMENT_FILE,
    ]
    for path in candidates:
        if path.exists():
            return pd.read_excel(path)
    raise FileNotFoundError(
        "File data tarif tidak ditemukan. Pastikan file Excel pendukung berada di folder yang sama dengan app."
    )


def adjusted_probability(q_annual, days: int) -> float:
    """Internal duration adjustment using annual probabilities."""
    try:
        q = float(q_annual)
    except Exception:
        return 0.0

    if pd.isna(q) or q <= 0:
        return 0.0

    q = min(max(q, 0.0), 1.0)
    days = max(int(days), 1)

    if days == 365:
        return q

    full_years = days // 365
    remainder_days = days % 365

    if days < 365:
        return 1 - ((1 - q) ** (days / 365))

    remainder_q = 0.0 if remainder_days == 0 else 1 - ((1 - q) ** (remainder_days / 365))
    return min(full_years * q + remainder_q, 1.0)


def diversification_factor(number_of_people: int, rho: float = CORRELATION) -> float:
    n = max(int(number_of_people), 1)
    return math.sqrt(rho + (1 - rho) / n)


def pure_premium(death_pr, lkberat_pr, lk_ringan_pr,
                 kematian, pemakaman, pendidikan,
                 biaya_perawatan, supir_meninggal):
    return (
        death_pr * (kematian + pemakaman + pendidikan + supir_meninggal)
        + lkberat_pr * (kematian + biaya_perawatan)
        + lk_ringan_pr * biaya_perawatan
    )


def gross_premium(pure, komisi, ovr, opex=OPEX, profit=PROFIT):
    denominator = 1 - komisi / 100 - ovr / 100 - opex - profit
    if denominator <= 0:
        return float("nan")
    return pure / denominator


def calculate_premium_table(df: pd.DataFrame, days: int, number_of_people: int,
                            santunan_mati: int, manfaat_makam: int, manfaat_pendidikan: int,
                            biaya_perawatan: int, sopir_meninggal: int,
                            comm: float, ovr: float) -> pd.DataFrame:
    out = df.copy()

    for col in DECREMENT_COLS:
        if col not in out.columns:
            raise KeyError(f"Kolom '{col}' tidak ditemukan di file Excel.")
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
        out[f"{col} Adjusted"] = out[col].apply(lambda q: adjusted_probability(q, days))

    factor = diversification_factor(number_of_people, CORRELATION)

    out["Pure Premium"] = out.apply(
        lambda x: pure_premium(
            x["Meninggal Adjusted"],
            x["Luka Berat Adjusted"],
            x["Luka Ringan Adjusted"],
            santunan_mati,
            manfaat_makam,
            manfaat_pendidikan,
            biaya_perawatan,
            sopir_meninggal,
        ),
        axis=1,
    )
    out["Gross Premium Individual"] = out["Pure Premium"].apply(lambda p: gross_premium(p, comm, ovr))
    out["Gross Premium"] = out["Gross Premium Individual"] * factor
    out["Total Group Premium"] = out["Gross Premium"] * max(int(number_of_people), 1)
    return out


def _pdf_table_style(header_bg="#0B1F35"):
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8.6),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (1, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D9E6")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#B8C4D2")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ])


def generate_pdf(manfaats, premi_minimum, premi_rekomendasi, premi_maksimum,
                 comm, ovr, days, number_of_people):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=38, leftMargin=38, topMargin=34, bottomMargin=30)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="DocTitle", parent=styles["Title"], fontSize=18, textColor=colors.HexColor("#0B1F35"), leading=22, alignment=0))
    styles.add(ParagraphStyle(name="SmallMuted", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#64748B"), leading=11))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontSize=12, textColor=colors.HexColor("#0B1F35"), spaceBefore=10, spaceAfter=8))

    story = [
        Paragraph("<b>PERSONAL ACCIDENT PREMIUM SUMMARY</b>", styles["DocTitle"]),
        Paragraph("Ringkasan manfaat, periode perlindungan, dan rekomendasi premi.", styles["SmallMuted"]),
        Spacer(1, 14),
    ]

    story.append(Paragraph("<b>Informasi Polis</b>", styles["Section"]))
    info_table = Table([
        ["Deskripsi", "Nilai"],
        ["Durasi Perlindungan", f"{format_idr(days)} hari"],
        ["Jumlah Peserta", f"{format_idr(number_of_people)} orang"],
    ], colWidths=[220, 160], hAlign="LEFT")
    info_table.setStyle(_pdf_table_style())
    story.append(info_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Manfaat</b>", styles["Section"]))
    manfaat_table = Table(
        [["Jenis Manfaat", "Nilai"]] + [[k, format_idr(v)] for k, v in manfaats.items()],
        colWidths=[220, 160],
        hAlign="LEFT",
    )
    manfaat_table.setStyle(_pdf_table_style())
    story.append(manfaat_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Biaya</b>", styles["Section"]))
    biaya_table = Table([
        ["Deskripsi", "Nilai"],
        ["Komisi", f"{comm:.0f}%"],
        ["Biaya Lainnya / OVR", f"{ovr:.0f}%"],
    ], colWidths=[220, 160], hAlign="LEFT")
    biaya_table.setStyle(_pdf_table_style())
    story.append(biaya_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Rekomendasi Premi Per Orang</b>", styles["Section"]))
    premi_table = Table([
        ["Deskripsi", "Nilai"],
        ["Premi Minimum", format_idr(premi_minimum)],
        ["Premi Rekomendasi", format_idr(premi_rekomendasi)],
        ["Premi Maksimum", format_idr(premi_maksimum)],
    ], colWidths=[220, 160], hAlign="LEFT")
    premi_table.setStyle(_pdf_table_style(header_bg="#123A5D"))
    story.append(premi_table)

    doc.build(story)
    buffer.seek(0)
    return buffer


def section_header(kicker: str, title: str, note: str = ""):
    note_html = f'<div class="pa-section-note">{note}</div>' if note else ""
    st.markdown(
        f"""
<div class="pa-section-head">
  <div>
    <div class="pa-section-kicker">{kicker}</div>
    <div class="pa-section-title">{title}</div>
  </div>
  {note_html}
</div>
""",
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: str, primary: bool = False) -> str:
    cls = "pa-metric-card primary" if primary else "pa-metric-card"
    return f"""
<div class="{cls}">
  <div class="pa-metric-label">{label}</div>
  <div class="pa-metric-value">{value}</div>
</div>
"""


# =========================================================
# APP MAIN
# =========================================================
def pa_main():
    inject_enterprise_css()

    st.markdown(
        """
<div class="pa-hero">
  <div class="pa-hero-kicker">Enterprise Pricing Workspace</div>
  <div class="pa-hero-title">Premium Calculator — Personal Accident Insurance</div>
  <div class="pa-hero-subtitle">Rancang premi Personal Accident secara rapi untuk kebutuhan quotation, proposal, dan ringkasan manajemen.</div>
  <div class="pa-hero-badges">
    <div class="pa-badge">Clean quotation view</div>
    <div class="pa-badge">PDF-ready summary</div>
    <div class="pa-badge">Group pricing support</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        section_header("Policy Setup", "Informasi Polis", "Data dasar quotation")
        c1, c2 = st.columns(2)
        with c1:
            jumlah_hari = st.number_input("Jumlah Hari", min_value=1, value=365, step=1, key="jumlah_hari")
        with c2:
            jumlah_orang = st.number_input("Jumlah Orang", min_value=1, value=1, step=1, key="jumlah_orang")

    with st.container(border=True):
        section_header("Benefit Structure", "Manfaat Santunan", "Nilai manfaat per peserta")
        c1, c2, c3 = st.columns(3)
        with c1:
            santunan_mati = money_input("Santunan Kematian", 10_000_000, "sm")
        with c2:
            manfaat_makam = money_input("Santunan Pemakaman", 5_000_000, "mp")
        with c3:
            manfaat_pendidikan = money_input("Manfaat Pendidikan Anak", 10_000_000, "pend")

        c4, c5 = st.columns(2)
        with c4:
            biaya_perawatan = money_input("Manfaat Rawat Inap", 5_000_000, "ri")
        with c5:
            sopir_meninggal = money_input("Santunan Kematian Supir", 10_000_000, "sm_sopir")

    with st.container(border=True):
        section_header("Commercial Loading", "Biaya dan Komponen", "Masukkan komponen biaya quotation")
        c1, c2 = st.columns(2)
        with c1:
            comm = st.number_input("Komisi (%)", min_value=0.0, max_value=100.0, value=10.0, step=1.0, key="comm")
        with c2:
            ovr = st.number_input("Biaya Lainnya / OVR (%)", min_value=0.0, max_value=100.0, value=10.0, step=1.0, key="ovr")

        hitung = st.button("Generate Premium Recommendation", use_container_width=True)

    if not hitung:
        st.info("Isi parameter quotation di atas, lalu klik **Generate Premium Recommendation**.")
        return

    try:
        df = load_decrement_table()
        result_df = calculate_premium_table(
            df=df,
            days=jumlah_hari,
            number_of_people=jumlah_orang,
            santunan_mati=santunan_mati,
            manfaat_makam=manfaat_makam,
            manfaat_pendidikan=manfaat_pendidikan,
            biaya_perawatan=biaya_perawatan,
            sopir_meninggal=sopir_meninggal,
            comm=comm,
            ovr=ovr,
        )
    except Exception as exc:
        st.error(str(exc))
        return

    premi_minimum = result_df["Gross Premium"].quantile(LOWER_RATE)
    premi_maksimum = result_df["Gross Premium"].quantile(UPPER_RATE)
    premi_rekomendasi = (premi_minimum + premi_maksimum) / 2
    total_group = premi_rekomendasi * int(jumlah_orang)

    with st.container(border=True):
        section_header("Output", "Rekomendasi Premi", "Nilai premi per orang")
        st.markdown(
            f"""
<div class="pa-result-grid">
  {render_metric_card("Premi Minimum", format_idr(premi_minimum))}
  {render_metric_card("Premi Rekomendasi", format_idr(premi_rekomendasi), primary=True)}
  {render_metric_card("Premi Maksimum", format_idr(premi_maksimum))}
</div>
<div class="pa-total-strip">
  <div><div class="pa-mini-label">Durasi Perlindungan</div><div class="pa-mini-value">{format_idr(jumlah_hari)} hari</div></div>
  <div><div class="pa-mini-label">Jumlah Peserta</div><div class="pa-mini-value">{format_idr(jumlah_orang)} orang</div></div>
  <div><div class="pa-mini-label">Estimasi Total Premi</div><div class="pa-mini-value">{format_idr(total_group)}</div></div>
</div>
""",
            unsafe_allow_html=True,
        )

    manfaat_dict = {
        "Santunan Kematian": santunan_mati,
        "Santunan Pemakaman": manfaat_makam,
        "Manfaat Pendidikan Anak": manfaat_pendidikan,
        "Manfaat Rawat Inap": biaya_perawatan,
        "Santunan Kematian Supir": sopir_meninggal,
    }

    pdf_buf = generate_pdf(
        manfaat_dict,
        premi_minimum,
        premi_rekomendasi,
        premi_maksimum,
        comm,
        ovr,
        jumlah_hari,
        jumlah_orang,
    )

    with st.container(border=True):
        section_header("Document", "Executive PDF", "Ringkasan siap dibagikan")
        st.download_button(
            "Download Executive PDF",
            data=pdf_buf,
            file_name="personal_accident_premium_summary.pdf",
            mime="application/pdf",
            use_container_width=True,
        )


if __name__ == "__main__":
    pa_main()
