"""
dashboard.py
=============================================================================
Aplikasi Web Monitoring & Peramalan Harga Emas Dunia serta Kurs USD/IDR.
Bagian dari proyek: Gold Price Monitoring (etl-gold-airflow).

Teknologi:
- Streamlit (Kerangka UI Web Interaktif)
- Plotly (Grafik & Visualisasi Finansial Interaktif)
- Pandas & NumPy (Manipulasi Data)
- Modul forecast.py (Model ARIMA & Estimasi IDR/Gram)

Ketentuan:
1. Data bersumber langsung dari data/gold_final.csv (TIDAK memanggil Yahoo Finance).
2. Menampilkan status "Harga Terakhir Tersedia" berdasarkan tanggal observasi terbaru
   (bukan data live/real-time).
3. Terdiri dari 3 Tab Utama:
   - Overview
   - Historical Monitoring
   - Forecasting ARIMA
=============================================================================
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# Import fungsi dari modul forecast yang sudah kita bangun
try:
    from forecast import run_forecasting_pipeline, TROY_OUNCE_TO_GRAM
except ImportError:
    # Fallback path jika dieksekusi dari direktori berbeda
    sys.path.append(str(Path(__file__).resolve().parent))
    from forecast import run_forecasting_pipeline, TROY_OUNCE_TO_GRAM

# ---------------------------------------------------------------------------
# Konfigurasi Halaman Streamlit
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Gold Price & USD/IDR Monitoring",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Path file dataset lokal
DATA_PATH = Path(__file__).resolve().parent / "data" / "gold_final.csv"


# ---------------------------------------------------------------------------
# Fungsi Pembantu Pemuatan Data (Cached untuk efisiensi)
# ---------------------------------------------------------------------------
@st.cache_data
def load_gold_data(csv_path: str, file_signature: tuple | None = None) -> pd.DataFrame:
    """Membaca data/gold_final.csv tanpa request ke Yahoo Finance.

    file_signature menjadi bagian dari cache key agar data terbaru hasil ETL
    dibaca ulang ketika file CSV berubah.
    """
    path = Path(csv_path)
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


@st.cache_data
def get_forecasting_results(csv_path: str, horizon: int, file_signature: tuple | None = None):
    """Menjalankan pipeline ARIMA; signature membatalkan cache saat CSV berubah."""
    return run_forecasting_pipeline(filepath=csv_path, horizon=horizon)


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------
def main():
    # 1. Pemuatan Data & Validasi
    # Ukuran dan waktu modifikasi file menjadi cache key agar hasil ETL terbaru
    # tidak tertahan oleh cache Streamlit dari eksekusi sebelumnya.
    if DATA_PATH.exists():
        stat = DATA_PATH.stat()
        data_file_signature = (stat.st_mtime_ns, stat.st_size)
    else:
        data_file_signature = None
    df_raw = load_gold_data(str(DATA_PATH), data_file_signature)

    if df_raw.empty:
        st.error(
            "⚠️ File data `data/gold_final.csv` tidak ditemukan atau kosong!\n\n"
            "Pastikan Anda telah menjalankan pipeline ETL Airflow terlebih dahulu "
            "(misal dengan perintah `python test_run.py` atau `airflow standalone`)."
        )
        st.stop()

    # Informasi Tanggal Observasi Terakhir
    latest_row = df_raw.iloc[-1]
    prev_row = df_raw.iloc[-2] if len(df_raw) > 1 else latest_row
    latest_date_str = latest_row["date"].strftime("%d %B %Y")
    total_records = len(df_raw)

    # -----------------------------------------------------------------------
    # Sidebar: Kontrol & Informasi Sistem
    # -----------------------------------------------------------------------
    with st.sidebar:
        st.title("⚙️ Kontrol & Filter")
        st.caption("Proyek: Gold Price Monitoring (Airflow ETL)")

        st.info(
            f"📌 **Status Data**: Disimpan dari ETL\n\n"
            f"📅 **Observasi Terakhir**:\n{latest_date_str}\n\n"
            f"📦 **Total Baris Data**: {total_records} hari",
            icon="ℹ️",
        )
        st.markdown("---")
        with st.expander("Filter Rentang Tanggal & Pengaturan Peramalan", expanded=False):
            min_date = df_raw["date"].min().date()
            max_date = df_raw["date"].max().date()
            date_range = st.date_input(
                "Pilih Rentang Analisis Historis:",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key="sidebar_date_range",
            )
            st.markdown("---")
            horizon = 3
            st.info("🗓️ Horizon peramalan: **3 hari kerja** ke depan.")

    # Filter data historis berdasarkan input tanggal di sidebar
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_d, end_d = date_range
        df_filtered = df_raw[
            (df_raw["date"].dt.date >= start_d) & (df_raw["date"].dt.date <= end_d)
        ].copy()
    else:
        df_filtered = df_raw.copy()

    if df_filtered.empty:
        st.warning("Tidak ada data pada rentang tanggal yang dipilih.")
        st.stop()

    # -----------------------------------------------------------------------
    # Header Utama
    # -----------------------------------------------------------------------
    st.title("🪙 Dashboard Monitoring & Peramalan Harga Emas")
    st.markdown(
        f"**Harga Terakhir Tersedia: {latest_date_str}** | "
        f"*Data bersumber dari `data/gold_final.csv` (Pipeline Airflow). Bukan data live/real-time.*"
    )
    st.markdown("---")

    # -----------------------------------------------------------------------
    # Tiga Tab Utama Dashboard
    # -----------------------------------------------------------------------
    tab1, tab2, tab3 = st.tabs([
        "📊 Overview",
        "📈 Historical Monitoring",
        "🔮 Forecasting ARIMA",
    ])

    # =======================================================================
    # TAB 1: OVERVIEW
    # =======================================================================
    with tab1:
        st.subheader("Ringkasan Pasar (Harga Terakhir Tersedia)")

        # Perhitungan delta perubahan harian (nominal & persentase)
        gold_curr = latest_row["close"]
        gold_prev = prev_row["close"]
        gold_delta = gold_curr - gold_prev
        gold_delta_pct = (gold_delta / gold_prev) * 100 if gold_prev != 0 else 0

        kurs_curr = latest_row["usd_idr"]
        kurs_prev = prev_row["usd_idr"]
        kurs_delta = kurs_curr - kurs_prev
        kurs_delta_pct = (kurs_delta / kurs_prev) * 100 if kurs_prev != 0 else 0

        gram_curr = latest_row["harga_per_gram_idr"]
        gram_prev = prev_row["harga_per_gram_idr"]
        gram_delta = gram_curr - gram_prev
        gram_delta_pct = (gram_delta / gram_prev) * 100 if gram_prev != 0 else 0

        oz_idr_curr = latest_row["close_idr"]
        oz_idr_prev = prev_row["close_idr"]
        oz_idr_delta = oz_idr_curr - oz_idr_prev
        oz_idr_delta_pct = (oz_idr_delta / oz_idr_prev) * 100 if oz_idr_prev != 0 else 0

        # Menampilkan 4 Metric Cards
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="Harga Emas (USD/oz)",
                value=f"${gold_curr:,.2f}",
                delta=f"{gold_delta:+,.2f} ({gold_delta_pct:+.2f}%)",
                help="Harga penutupan emas dunia (GC=F) per troy ounce dalam USD.",
            )

        with col2:
            st.metric(
                label="Kurs USD/IDR",
                value=f"Rp{kurs_curr:,.2f}",
                delta=f"{kurs_delta:+,.2f} ({kurs_delta_pct:+.2f}%)",
                delta_color="inverse",  # Kenaikan kurs dolar biasanya dianggap depresiasi rupiah
                help="Kurs pertukaran US Dollar terhadap Rupiah Indonesia.",
            )

        with col3:
            st.metric(
                label="Estimasi Emas (IDR/gram)",
                value=f"Rp{gram_curr:,.0f}",
                delta=f"{gram_delta:+,.0f} ({gram_delta_pct:+.2f}%)",
                help="Harga emas dalam Rupiah per gram (Close IDR / 31.1035).",
            )

        with col4:
            st.metric(
                label="Emas per Troy Oz (IDR)",
                value=f"Rp{oz_idr_curr:,.0f}",
                delta=f"{oz_idr_delta:+,.0f} ({oz_idr_delta_pct:+.2f}%)",
                help="Total nilai 1 troy ounce emas dalam Rupiah (Close USD * USD/IDR).",
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # Kartu Ringkasan Statistik Rentang Data Terpilih
        st.subheader("Statistik Ringkas Periode Terpilih")
        col_s1, col_s2, col_s3 = st.columns(3)

        with col_s1:
            st.markdown(
                f"""
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #d4af37;">
                    <h5 style="margin:0; color: #333;">Emas Dunia (USD/oz)</h5>
                    <p style="margin:5px 0 0 0; color: #666; font-size: 14px;">
                        • Tertinggi: <b>${df_filtered['high'].max():,.2f}</b><br>
                        • Terendah: <b>${df_filtered['low'].min():,.2f}</b><br>
                        • Rata-rata: <b>${df_filtered['close'].mean():,.2f}</b>
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_s2:
            st.markdown(
                f"""
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #28a745;">
                    <h5 style="margin:0; color: #333;">Kurs USD/IDR</h5>
                    <p style="margin:5px 0 0 0; color: #666; font-size: 14px;">
                        • Tertinggi: <b>Rp{df_filtered['usd_idr'].max():,.2f}</b><br>
                        • Terendah: <b>Rp{df_filtered['usd_idr'].min():,.2f}</b><br>
                        • Rata-rata: <b>Rp{df_filtered['usd_idr'].mean():,.2f}</b>
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_s3:
            st.markdown(
                f"""
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #17a2b8;">
                    <h5 style="margin:0; color: #333;">Estimasi IDR/gram</h5>
                    <p style="margin:5px 0 0 0; color: #666; font-size: 14px;">
                        • Tertinggi: <b>Rp{df_filtered['harga_per_gram_idr'].max():,.0f}</b><br>
                        • Terendah: <b>Rp{df_filtered['harga_per_gram_idr'].min():,.0f}</b><br>
                        • Rata-rata: <b>Rp{df_filtered['harga_per_gram_idr'].mean():,.0f}</b>
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # Highlight Perbandingan Tren Terakhir
        st.subheader("Ikhtisar Pergerakan Emas Dunia & Nilai Tukar Rupiah")
        fig_overview = make_subplots(specs=[[{"secondary_y": True}]])
        fig_overview.add_trace(
            go.Scatter(
                x=df_filtered["date"],
                y=df_filtered["close"],
                name="Emas Dunia (USD/oz)",
                line=dict(color="#d4af37", width=2.5),
            ),
            secondary_y=False,
        )
        fig_overview.add_trace(
            go.Scatter(
                x=df_filtered["date"],
                y=df_filtered["usd_idr"],
                name="Kurs USD/IDR",
                line=dict(color="#007bff", width=2, dash="dot"),
            ),
            secondary_y=True,
        )
        fig_overview.update_layout(
            title_text="Perbandingan Historis: Emas Dunia vs Kurs USD/IDR",
            hovermode="x unified",
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=40, t=60, b=40),
            height=420,
        )
        fig_overview.update_yaxes(title_text="Harga Emas (USD)", secondary_y=False)
        fig_overview.update_yaxes(title_text="Kurs USD/IDR (Rp)", secondary_y=True)
        st.plotly_chart(fig_overview, use_container_width=True)

    # =======================================================================
    # TAB 2: HISTORICAL MONITORING
    # =======================================================================
    with tab2:
        st.subheader("Pemantauan Data Historis & Indikator Teknikal")

        # Pilihan Tipe Tampilan Grafik Emas
        chart_mode = st.radio(
            "Mode Tampilan Grafik Emas Dunia:",
            options=["Candlestick + Volume", "Line Chart + Moving Averages"],
            horizontal=True,
        )

        # 1. Grafik Emas USD
        if chart_mode == "Candlestick + Volume":
            fig_gold = make_subplots(
                rows=2,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.08,
                subplot_titles=("Pergerakan Candlestick Emas Dunia (USD/oz)", "Volume Transaksi"),
                row_width=[0.25, 0.75],
            )
            # Candlestick
            fig_gold.add_trace(
                go.Candlestick(
                    x=df_filtered["date"],
                    open=df_filtered["open"],
                    high=df_filtered["high"],
                    low=df_filtered["low"],
                    close=df_filtered["close"],
                    name="OHLC Emas",
                ),
                row=1,
                col=1,
            )
            # MA7 & MA30
            fig_gold.add_trace(
                go.Scatter(
                    x=df_filtered["date"],
                    y=df_filtered["ma_7"],
                    name="MA 7 Hari",
                    line=dict(color="#ff9900", width=1.5),
                ),
                row=1,
                col=1,
            )
            fig_gold.add_trace(
                go.Scatter(
                    x=df_filtered["date"],
                    y=df_filtered["ma_30"],
                    name="MA 30 Hari",
                    line=dict(color="#dc3545", width=1.5),
                ),
                row=1,
                col=1,
            )
            # Volume
            fig_gold.add_trace(
                go.Bar(
                    x=df_filtered["date"],
                    y=df_filtered["volume"],
                    name="Volume",
                    marker_color="#6c757d",
                ),
                row=2,
                col=1,
            )
            fig_gold.update_layout(
                xaxis_rangeslider_visible=False,
                template="plotly_white",
                height=520,
                margin=dict(l=40, r=40, t=50, b=40),
            )
            st.plotly_chart(fig_gold, use_container_width=True)
        else:
            fig_gold_line = go.Figure()
            fig_gold_line.add_trace(
                go.Scatter(
                    x=df_filtered["date"],
                    y=df_filtered["close"],
                    name="Close (USD)",
                    line=dict(color="#d4af37", width=2.5),
                )
            )
            fig_gold_line.add_trace(
                go.Scatter(
                    x=df_filtered["date"],
                    y=df_filtered["ma_7"],
                    name="MA 7 Hari",
                    line=dict(color="#ff9900", width=1.5, dash="dash"),
                )
            )
            fig_gold_line.add_trace(
                go.Scatter(
                    x=df_filtered["date"],
                    y=df_filtered["ma_30"],
                    name="MA 30 Hari",
                    line=dict(color="#dc3545", width=1.5, dash="dot"),
                )
            )
            fig_gold_line.update_layout(
                title="Harga Penutupan Emas Dunia dengan MA 7 & MA 30",
                xaxis_title="Tanggal",
                yaxis_title="Harga (USD/troy ounce)",
                template="plotly_white",
                hovermode="x unified",
                height=450,
            )
            st.plotly_chart(fig_gold_line, use_container_width=True)

        st.markdown("---")

        # 2. Grafik Emas IDR/gram & Kurs USD/IDR dalam 2 kolom berdampingan
        c_left, c_right = st.columns(2)

        with c_left:
            st.markdown("##### 🪙 Tren Harga Emas (IDR/gram)")
            fig_idr = go.Figure()
            fig_idr.add_trace(
                go.Scatter(
                    x=df_filtered["date"],
                    y=df_filtered["harga_per_gram_idr"],
                    name="IDR/gram",
                    line=dict(color="#17a2b8", width=2),
                )
            )
            if "ma_7_idr" in df_filtered.columns:
                fig_idr.add_trace(
                    go.Scatter(
                        x=df_filtered["date"],
                        y=df_filtered["ma_7_idr"],
                        name="MA 7 IDR",
                        line=dict(color="#fd7e14", width=1.2, dash="dash"),
                    )
                )
            if "ma_30_idr" in df_filtered.columns:
                fig_idr.add_trace(
                    go.Scatter(
                        x=df_filtered["date"],
                        y=df_filtered["ma_30_idr"],
                        name="MA 30 IDR",
                        line=dict(color="#6f42c1", width=1.2, dash="dot"),
                    )
                )
            fig_idr.update_layout(
                template="plotly_white",
                height=380,
                yaxis_title="Rupiah per Gram (Rp)",
                hovermode="x unified",
                margin=dict(l=30, r=30, t=40, b=30),
            )
            st.plotly_chart(fig_idr, use_container_width=True)

        with c_right:
            st.markdown("##### 💵 Tren Kurs USD/IDR")
            fig_kurs = go.Figure()
            fig_kurs.add_trace(
                go.Scatter(
                    x=df_filtered["date"],
                    y=df_filtered["usd_idr"],
                    name="Kurs USD/IDR",
                    line=dict(color="#28a745", width=2),
                )
            )
            fig_kurs.update_layout(
                template="plotly_white",
                height=380,
                yaxis_title="Nilai Tukar (Rp)",
                hovermode="x unified",
                margin=dict(l=30, r=30, t=40, b=30),
            )
            st.plotly_chart(fig_kurs, use_container_width=True)

        st.markdown("---")

        # 3. Grafik Daily Return
        st.markdown("##### 📈 Volatilitas: Daily Return (%)")
        fig_ret = go.Figure()
        # Daily return dikali 100 agar dalam persentase
        fig_ret.add_trace(
            go.Scatter(
                x=df_filtered["date"],
                y=df_filtered["daily_return"] * 100,
                name="Daily Return Emas (USD) %",
                line=dict(color="#d4af37", width=1),
                opacity=0.8,
            )
        )
        if "daily_return_idr" in df_filtered.columns:
            fig_ret.add_trace(
                go.Scatter(
                    x=df_filtered["date"],
                    y=df_filtered["daily_return_idr"] * 100,
                    name="Daily Return Emas (IDR/gram) %",
                    line=dict(color="#17a2b8", width=1),
                    opacity=0.8,
                )
            )
        fig_ret.update_layout(
            template="plotly_white",
            height=320,
            yaxis_title="Perubahan Harian (%)",
            hovermode="x unified",
            margin=dict(l=30, r=30, t=40, b=30),
        )
        st.plotly_chart(fig_ret, use_container_width=True)

        # 4. Tabel Data Historis
        with st.expander("📄 Tampilkan Tabel Data Historis Lengkap", expanded=False):
            st.dataframe(
                df_filtered.style.format({
                    "close": "${:,.2f}",
                    "high": "${:,.2f}",
                    "low": "${:,.2f}",
                    "open": "${:,.2f}",
                    "volume": "{:,.0f}",
                    "usd_idr": "Rp{:,.2f}",
                    "close_idr": "Rp{:,.0f}",
                    "harga_per_gram_idr": "Rp{:,.2f}",
                    "daily_return": "{:+.2%}",
                    "daily_return_idr": "{:+.2%}",
                }),
                use_container_width=True,
                height=350,
            )
            csv_data = df_filtered.to_csv(index=False).encode("utf-8")
            download_start = df_filtered["date"].min().date().isoformat()
            download_end = df_filtered["date"].max().date().isoformat()
            st.download_button(
                label="📥 Unduh Data Historis (CSV)",
                data=csv_data,
                file_name=f"gold_history_{download_start}_{download_end}.csv",
                mime="text/csv",
            )

    # =======================================================================
    # TAB 3: FORECASTING ARIMA
    # =======================================================================
    with tab3:
        st.subheader("Peramalan Runtun Waktu Menggunakan Model ARIMA")

        st.markdown(
            """
            > **Metodologi Pemodelan**:
            > - **Model 1**: ARIMA pada kolom `close` untuk memprediksi harga emas dunia (USD/troy oz).
            > - **Model 2**: ARIMA pada kolom `usd_idr` untuk memprediksi nilai tukar Rupiah.
            > - **Estimasi IDR/gram**: Dihitung dari hasil kedua model: 
            >   $$\\text{Prediksi IDR/gram} = \\frac{\\text{Prediksi Close USD} \\times \\text{Prediksi Kurs USD/IDR}}{31.1035}$$
            > - **Validasi Model**: Pembagian data kronologis **80% Training : 20% Testing** (tanpa shuffle) untuk mencegah *data leakage*.
            > - **Fit Ulang**: Model terbaik di-fit ulang menggunakan 100% data historis untuk menghasilkan proyeksi masa depan.
            """
        )

        with st.spinner(f"Menjalankan peramalan ARIMA untuk horizon {horizon} hari kerja..."):
            try:
                fc_results = get_forecasting_results(
                    str(DATA_PATH), horizon, data_file_signature
                )
            except Exception as e:
                st.error(f"Gagal mengeksekusi model forecasting: {e}")
                st.stop()

        fc_table = fc_results["forecast_table"]
        m_gold = fc_results["models"]["gold"]
        m_kurs = fc_results["models"]["kurs"]
        df_hist = fc_results["df_historical"]

        # Kartu Ringkasan Diagnostik & Metrik Evaluasi Model — tampilan kompak
        st.markdown("##### 🎯 Hasil Evaluasi Model (Data Testing 20% Out-of-Sample)")

        def _fmt(val, prefix="", suffix="", decimals=2):
            try:
                return f"{prefix}{val:,.{decimals}f}{suffix}"
            except Exception:
                return "N/A"

        ev_col1, ev_col2 = st.columns(2)
        with ev_col1:
            st.markdown(
                f"""<div style="background:#fdfaf3;padding:10px 14px;border-radius:8px;
                border:1px solid #d4af37;font-size:13px;line-height:1.6;">
                <b style="color:#b8860b;">Model 1 · Harga Emas (USD/oz)</b><br>
                Ordo: <code>ARIMA{m_gold.get('order','?')}</code> &nbsp;|&nbsp;
                AIC: {_fmt(m_gold.get('train_aic'), decimals=1)}<br>
                MAE: {_fmt(m_gold.get('mae'), prefix='$')} &nbsp;|&nbsp;
                RMSE: {_fmt(m_gold.get('rmse'), prefix='$')} &nbsp;|&nbsp;
                MAPE: {_fmt(m_gold.get('mape'), suffix='%')}
                </div>""",
                unsafe_allow_html=True,
            )
        with ev_col2:
            st.markdown(
                f"""<div style="background:#f3fcf4;padding:10px 14px;border-radius:8px;
                border:1px solid #28a745;font-size:13px;line-height:1.6;">
                <b style="color:#2e7d32;">Model 2 · Kurs USD/IDR</b><br>
                Ordo: <code>ARIMA{m_kurs.get('order','?')}</code> &nbsp;|&nbsp;
                AIC: {_fmt(m_kurs.get('train_aic'), decimals=1)}<br>
                MAE: {_fmt(m_kurs.get('mae'), prefix='Rp')} &nbsp;|&nbsp;
                RMSE: {_fmt(m_kurs.get('rmse'), prefix='Rp')} &nbsp;|&nbsp;
                MAPE: {_fmt(m_kurs.get('mape'), suffix='%')}
                </div>""",
                unsafe_allow_html=True,
            )

        # -------------------------------------------------------------------
        # Visualisasi Hasil Peramalan dengan Plotly
        # -------------------------------------------------------------------
        st.markdown("##### 📈 Visualisasi Proyeksi & Rentang Prediksi 95%")
        st.caption(
            "Rentang IDR/gram merupakan estimasi Monte Carlo dengan asumsi "
            "independensi galat prediksi emas dan kurs."
        )

        # Subset 60 observasi terakhir data historis untuk konteks grafik yang jelas
        df_hist_tail = df_hist.tail(60).copy()

        # Pilihan metrik yang ingin divisualisasikan
        view_forecast = st.selectbox(
            "Pilih Visualisasi Proyeksi:",
            options=[
                "1. Emas Dunia (USD/oz) - Model 1",
                "2. Kurs USD/IDR - Model 2",
                "3. Estimasi Emas IDR/gram - Hasil Gabungan",
            ],
            index=0,
        )

        if "1. Emas Dunia" in view_forecast:
            fig_fc = go.Figure()
            # Data Historis
            fig_fc.add_trace(
                go.Scatter(
                    x=df_hist_tail["date"],
                    y=df_hist_tail["close"],
                    name="Data Historis Aktual",
                    line=dict(color="#333333", width=2),
                )
            )
            # Prediksi Garis Titik
            fig_fc.add_trace(
                go.Scatter(
                    x=fc_table["date"],
                    y=fc_table["pred_gold_usd"],
                    name=f"Proyeksi ARIMA{m_gold['order']}",
                    line=dict(color="#d4af37", width=2.5, dash="dash"),
                    mode="lines+markers",
                )
            )
            # Confidence Interval Band (Upper)
            fig_fc.add_trace(
                go.Scatter(
                    x=fc_table["date"],
                    y=fc_table["gold_usd_upper"],
                    name="Batas Atas Prediksi 95%",
                    line=dict(color="rgba(212,175,55,0.2)"),
                    showlegend=False,
                )
            )
            # Confidence Interval Band (Lower)
            fig_fc.add_trace(
                go.Scatter(
                    x=fc_table["date"],
                    y=fc_table["gold_usd_lower"],
                    name="Rentang Prediksi 95%",
                    fill="tonexty",
                    fillcolor="rgba(212,175,55,0.2)",
                    line=dict(color="rgba(212,175,55,0.2)"),
                )
            )
            fig_fc.update_layout(
                title=f"Proyeksi Harga Emas Dunia (USD/oz) - Horizon {horizon} Hari Kerja",
                xaxis_title="Tanggal",
                yaxis_title="Harga (USD)",
                template="plotly_white",
                hovermode="x unified",
                height=450,
            )
            st.plotly_chart(fig_fc, use_container_width=True)

        elif "2. Kurs USD/IDR" in view_forecast:
            fig_fc = go.Figure()
            # Data Historis
            fig_fc.add_trace(
                go.Scatter(
                    x=df_hist_tail["date"],
                    y=df_hist_tail["usd_idr"],
                    name="Data Historis Aktual",
                    line=dict(color="#333333", width=2),
                )
            )
            # Prediksi Garis Titik
            fig_fc.add_trace(
                go.Scatter(
                    x=fc_table["date"],
                    y=fc_table["pred_usd_idr"],
                    name=f"Proyeksi ARIMA{m_kurs['order']}",
                    line=dict(color="#28a745", width=2.5, dash="dash"),
                    mode="lines+markers",
                )
            )
            # Confidence Interval
            fig_fc.add_trace(
                go.Scatter(
                    x=fc_table["date"],
                    y=fc_table["usd_idr_upper"],
                    name="Batas Atas Prediksi 95%",
                    line=dict(color="rgba(40,167,69,0.2)"),
                    showlegend=False,
                )
            )
            fig_fc.add_trace(
                go.Scatter(
                    x=fc_table["date"],
                    y=fc_table["usd_idr_lower"],
                    name="Rentang Prediksi 95%",
                    fill="tonexty",
                    fillcolor="rgba(40,167,69,0.2)",
                    line=dict(color="rgba(40,167,69,0.2)"),
                )
            )
            fig_fc.update_layout(
                title=f"Proyeksi Kurs USD/IDR - Horizon {horizon} Hari Kerja",
                xaxis_title="Tanggal",
                yaxis_title="Nilai Tukar Rupiah (Rp)",
                template="plotly_white",
                hovermode="x unified",
                height=450,
            )
            st.plotly_chart(fig_fc, use_container_width=True)

        else:
            fig_fc = go.Figure()
            # Data Historis IDR/gram
            fig_fc.add_trace(
                go.Scatter(
                    x=df_hist_tail["date"],
                    y=df_hist_tail["harga_per_gram_idr"],
                    name="Data Historis Aktual",
                    line=dict(color="#333333", width=2),
                )
            )
            # Prediksi Estimasi IDR/gram
            fig_fc.add_trace(
                go.Scatter(
                    x=fc_table["date"],
                    y=fc_table["est_idr_gram"],
                    name="Estimasi Gabungan (IDR/gram)",
                    line=dict(color="#17a2b8", width=2.5, dash="dash"),
                    mode="lines+markers",
                )
            )
            # Confidence Interval
            fig_fc.add_trace(
                go.Scatter(
                    x=fc_table["date"],
                    y=fc_table["idr_gram_upper"],
                    name="Batas Atas Estimasi 95%",
                    line=dict(color="rgba(23,162,184,0.2)"),
                    showlegend=False,
                )
            )
            fig_fc.add_trace(
                go.Scatter(
                    x=fc_table["date"],
                    y=fc_table["idr_gram_lower"],
                    name="Rentang Estimasi 95% (asumsi independensi)",
                    fill="tonexty",
                    fillcolor="rgba(23,162,184,0.2)",
                    line=dict(color="rgba(23,162,184,0.2)"),
                )
            )
            fig_fc.update_layout(
                title=f"Proyeksi Estimasi Harga Emas IDR/gram - Horizon {horizon} Hari Kerja",
                xaxis_title="Tanggal",
                yaxis_title="Harga per Gram (Rp)",
                template="plotly_white",
                hovermode="x unified",
                height=450,
            )
            st.plotly_chart(fig_fc, use_container_width=True)

        st.markdown("---")

        # -------------------------------------------------------------------
        # Tabel Detail Nilai Peramalan Masa Depan
        # -------------------------------------------------------------------
        st.markdown(f"##### 📋 Tabel Rincian Peramalan {horizon} Hari Kerja ke Depan")

        # Tampilkan tabel yang diformat dengan rapi
        display_fc_table = fc_table.copy()
        display_fc_table["date"] = display_fc_table["date"].dt.strftime("%Y-%m-%d (%A)")

        st.dataframe(
            display_fc_table[[
                "step",
                "date",
                "pred_gold_usd",
                "gold_usd_lower",
                "gold_usd_upper",
                "pred_usd_idr",
                "usd_idr_lower",
                "usd_idr_upper",
                "est_idr_gram",
                "idr_gram_lower",
                "idr_gram_upper",
            ]].rename(columns={
                "step": "Hari Ke-",
                "date": "Estimasi Tanggal",
                "pred_gold_usd": "Prediksi Emas (USD)",
                "gold_usd_lower": "Batas Bawah Emas (95%)",
                "gold_usd_upper": "Batas Atas Emas (95%)",
                "pred_usd_idr": "Prediksi Kurs (Rp/USD)",
                "usd_idr_lower": "Batas Bawah Kurs (95%)",
                "usd_idr_upper": "Batas Atas Kurs (95%)",
                "est_idr_gram": "Estimasi IDR/gram",
                "idr_gram_lower": "Batas Bawah IDR/gr (estimasi 95%)",
                "idr_gram_upper": "Batas Atas IDR/gr (estimasi 95%)",
            }).style.format({
                "Prediksi Emas (USD)": "${:,.2f}",
                "Batas Bawah Emas (95%)": "${:,.2f}",
                "Batas Atas Emas (95%)": "${:,.2f}",
                "Prediksi Kurs (Rp/USD)": "Rp{:,.2f}",
                "Batas Bawah Kurs (95%)": "Rp{:,.2f}",
                "Batas Atas Kurs (95%)": "Rp{:,.2f}",
                "Estimasi IDR/gram": "Rp{:,.0f}",
                "Batas Bawah IDR/gr (estimasi 95%)": "Rp{:,.0f}",
                "Batas Atas IDR/gr (estimasi 95%)": "Rp{:,.0f}",
            }),
            use_container_width=True,
            height=300,
        )

        # Download CSV hasil peramalan
        csv_forecast = fc_table.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Unduh Hasil Peramalan (CSV)",
            data=csv_forecast,
            file_name=f"gold_arima_forecast_h{horizon}_{latest_date_str.replace(' ', '_')}.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
