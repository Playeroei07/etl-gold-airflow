"""
forecast.py
=============================================================================
Modul Peramalan (Forecasting) Harga Emas Dunia dan Kurs USD/IDR menggunakan ARIMA.
Bagian dari proyek: Gold Price Monitoring (etl-gold-airflow).

Metodologi:
1. Membaca data historis dari data/gold_final.csv (tanpa koneksi internet/Yahoo Finance).
2. Menyiapkan 2 model ARIMA terpisah:
   - Model A: Target kolom 'close' (Harga Emas USD/troy ounce).
   - Model B: Target kolom 'usd_idr' (Kurs USD terhadap IDR).
3. Estimasi harga emas IDR/gram dihitung langsung dari kedua peramalan:
   Prediksi IDR/gram = (Prediksi Close USD * Prediksi USD/IDR) / 31.1035
4. Pembagian data Training & Testing secara kronologis (80:20) tanpa shuffle.
5. Pemilihan hyperparameter ARIMA (p, d, q) via Grid Search menggunakan HANYA data training
   (mencegah data leakage) berdasarkan nilai AIC terendah.
   - p: [0, 1, 2]
   - d: [0, 1]
   - q: [0, 1, 2]
6. Evaluasi model pada data testing menggunakan metrik MAE, RMSE, dan MAPE.
7. Diagnostik stasionaritas seri data menggunakan Augmented Dickey-Fuller (ADF) Test.
8. Model terbaik di-fit ulang menggunakan seluruh data historis untuk memproyeksikan
   horizon masa depan (7, 14, dan 30 hari perdagangan). Interval gabungan IDR/gram
   diestimasi dengan simulasi Monte Carlo berdasarkan asumsi independensi galat model.
=============================================================================
"""

import sys
from pathlib import Path
from typing import Dict, Any, Tuple

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller

# Peringatan estimasi statsmodels sengaja tidak disembunyikan agar masalah konvergensi terlihat.

# ---------------------------------------------------------------------------
# Konstanta Konversi & Path
# ---------------------------------------------------------------------------
TROY_OUNCE_TO_GRAM = 31.1035
DEFAULT_DATA_PATH = Path(__file__).resolve().parent / "data" / "gold_final.csv"


# ---------------------------------------------------------------------------
# 1. Pemuatan & Validasi Data
# ---------------------------------------------------------------------------
def load_data(filepath: Path | str = DEFAULT_DATA_PATH) -> pd.DataFrame:
    """
    Membaca dataset hasil ETL Airflow (data/gold_final.csv).
    Memvalidasi ketersediaan kolom kunci dan mengurutkan berdasarkan tanggal kronologis.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset tidak ditemukan di path: {path}. "
            f"Pastikan pipeline ETL Airflow telah dijalankan sebelumnya."
        )

    df = pd.read_csv(path)

    # Validasi kolom yang dibutuhkan
    required_cols = ["date", "close", "usd_idr", "harga_per_gram_idr"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset tidak memiliki kolom yang dibutuhkan: {missing}")

    # Konversi tanggal dan urutkan secara kronologis
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
# 2. Diagnostik Stasionaritas (Augmented Dickey-Fuller Test)
# ---------------------------------------------------------------------------
def run_adf_test(series: pd.Series, series_name: str = "Variabel") -> Dict[str, Any]:
    """
    Melakukan Augmented Dickey-Fuller (ADF) test untuk menganalisis stasionaritas data.
    Hasil digunakan sebagai diagnostik statistik (bukan penentu tunggal ordo model).
    """
    clean_series = series.dropna()
    adf_result = adfuller(clean_series, autolag="AIC")

    stat = float(adf_result[0])
    p_value = float(adf_result[1])
    critical_vals = {str(k): float(v) for k, v in adf_result[4].items()}
    # Data dianggap stasioner pada signifikansi 5% jika p-value < 0.05
    is_stationary = p_value < 0.05

    return {
        "series_name": series_name,
        "adf_statistic": stat,
        "p_value": p_value,
        "critical_values": critical_vals,
        "is_stationary": is_stationary,
        "summary": (
            f"Stasioner (p-value: {p_value:.4f} < 0.05)"
            if is_stationary
            else f"Tidak Stasioner (p-value: {p_value:.4f} >= 0.05, butuh differencing)"
        ),
    }


# ---------------------------------------------------------------------------
# 3. Pembagian Data Kronologis (Train-Test Split)
# ---------------------------------------------------------------------------
def split_train_test_chronological(
    series: pd.Series, train_ratio: float = 0.8
) -> Tuple[pd.Series, pd.Series]:
    """
    Membagi data time series secara kronologis (default 80% train, 20% test).
    Tanpa shuffle untuk mencegah data leakage pada data runtun waktu.
    """
    n_total = len(series)
    n_train = int(n_total * train_ratio)

    train_data = series.iloc[:n_train].copy()
    test_data = series.iloc[n_train:].copy()

    return train_data, test_data


# ---------------------------------------------------------------------------
# 4. Grid Search Parameter ARIMA (Hanya Menggunakan Data Training)
# ---------------------------------------------------------------------------
def grid_search_arima_train(
    train_series: pd.Series,
    p_range: range = range(0, 3),
    d_range: range = range(0, 2),
    q_range: range = range(0, 3),
) -> Tuple[Tuple[int, int, int], float, list]:
    """
    Mencari kombinasi hyperparameter ARIMA (p, d, q) terbaik dengan kriteria AIC terendah.
    Hanya dijalankan pada data training untuk menghindari data leakage.
    p in [0, 1, 2], d in [0, 1], q in [0, 1, 2] -> Total 18 kombinasi.
    """
    best_aic = float("inf")
    best_order = (1, 1, 1)  # Fallback default yang umum untuk time series finansial
    results_history = []

    for p in p_range:
        for d in d_range:
            for q in q_range:
                order = (p, d, q)
                try:
                    # Fit model pada data training saja
                    model = ARIMA(
                        train_series,
                        order=order,
                        enforce_stationarity=False,
                        enforce_invertibility=False,
                    )
                    fitted = model.fit()
                    aic = float(fitted.aic)
                    results_history.append({"order": order, "aic": aic, "status": "success"})

                    if aic < best_aic:
                        best_aic = aic
                        best_order = order
                except Exception as e:
                    results_history.append({"order": order, "aic": np.nan, "status": f"failed: {str(e)}"})

    return best_order, best_aic, results_history


# ---------------------------------------------------------------------------
# 5. Evaluasi Model pada Data Testing (Out-of-Sample Validation)
# ---------------------------------------------------------------------------
def evaluate_model_on_test(
    train_series: pd.Series,
    test_series: pd.Series,
    order: Tuple[int, int, int],
) -> Dict[str, Any]:
    """
    Melatih model dengan best_order pada data train, lalu mengevaluasi prediksinya
    pada data test menggunakan MAE, RMSE, dan MAPE.
    """
    model = ARIMA(
        train_series,
        order=order,
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    fitted = model.fit()

    steps = len(test_series)
    forecast_res = fitted.get_forecast(steps=steps)
    test_pred = forecast_res.predicted_mean.values
    test_actual = test_series.values

    # Perhitungan Metrik Evaluasi
    mae = float(np.mean(np.abs(test_actual - test_pred)))
    rmse = float(np.sqrt(np.mean((test_actual - test_pred) ** 2)))
    # MAPE valid karena harga emas dan kurs bernilai positif > 0
    mape = float(np.mean(np.abs((test_actual - test_pred) / test_actual)) * 100)

    return {
        "order": order,
        "train_aic": float(fitted.aic),
        "mae": mae,
        "rmse": rmse,
        "mape": mape,
        "test_actual": test_actual,
        "test_pred": test_pred,
    }


# ---------------------------------------------------------------------------
# 6. Fit Ulang Model pada Seluruh Data Historis & Forecasting Masa Depan
# ---------------------------------------------------------------------------
def fit_full_and_forecast(
    full_series: pd.Series,
    order: Tuple[int, int, int],
    horizon: int = 7,
) -> pd.DataFrame:
    """
    Melatih ulang model ARIMA terbaik pada SELURUH data historis (100% data),
    kemudian menghasilkan proyeksi ke depan sejumlah horizon periode beserta
    Confidence Interval 95%.
    """
    model = ARIMA(
        full_series,
        order=order,
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    fitted = model.fit()

    forecast_res = fitted.get_forecast(steps=horizon)
    predicted_mean = np.asarray(forecast_res.predicted_mean, dtype=float)
    standard_error = np.asarray(forecast_res.se_mean, dtype=float)

    # Rentang prediksi 95% untuk masing-masing seri (alpha = 0.05).
    conf_int = forecast_res.conf_int(alpha=0.05)
    lower_ci = conf_int.iloc[:, 0].to_numpy(dtype=float)
    upper_ci = conf_int.iloc[:, 1].to_numpy(dtype=float)

    forecast_df = pd.DataFrame({
        "forecast": predicted_mean,
        "se_mean": standard_error,
        "lower_ci": lower_ci,
        "upper_ci": upper_ci,
    })

    return forecast_df


# ---------------------------------------------------------------------------
# 7. Pembuatan Estimasi Tanggal Hari Kerja (Business Days)
# ---------------------------------------------------------------------------
def generate_future_trading_dates(last_date: pd.Timestamp, periods: int) -> pd.DatetimeIndex:
    """
    Menghasilkan estimasi tanggal hari perdagangan ke depan menggunakan business days
    (Senin-Jumat). Catatan: Ini adalah estimasi hari kerja, bukan kalender resmi bursa.
    """
    start_date = last_date + pd.Timedelta(days=1)
    return pd.bdate_range(start=start_date, periods=periods)


# ---------------------------------------------------------------------------
# 8. Pipeline Utama Forecasting (Emas USD, Kurs USD/IDR, & Estimasi IDR/Gram)
# ---------------------------------------------------------------------------
def run_forecasting_pipeline(
    filepath: Path | str = DEFAULT_DATA_PATH,
    horizon: int = 7,
) -> Dict[str, Any]:
    """
    Menjalankan pipeline peramalan lengkap:
    1. Membaca dataset gold_final.csv
    2. Diagnostik ADF untuk 'close' dan 'usd_idr'
    3. Train-test split (80:20) kronologis
    4. Grid search ARIMA pada data training
    5. Evaluasi out-of-sample pada data testing (MAE, RMSE, MAPE)
    6. Re-fit seluruh data dan peramalan masa depan (horizon perdagangan)
    7. Perhitungan estimasi harga emas IDR/gram dari hasil prediksi kedua model:
       Prediksi IDR/gram = (Prediksi Close * Prediksi Kurs) / 31.1035
    """
    if horizon not in (7, 14, 30):
        raise ValueError("Horizon harus salah satu dari 7, 14, atau 30 periode.")

    # 1. Pemuatan data
    df = load_data(filepath)
    last_date = df["date"].iloc[-1]
    future_dates = generate_future_trading_dates(last_date, periods=horizon)

    gold_series = df["close"]
    kurs_series = df["usd_idr"]

    # 2. Diagnostik Stasionaritas (ADF Test)
    adf_gold = run_adf_test(gold_series, "Harga Emas (USD/oz)")
    adf_kurs = run_adf_test(kurs_series, "Kurs USD/IDR")

    # 3. Train-Test Split (80:20 secara kronologis)
    gold_train, gold_test = split_train_test_chronological(gold_series, train_ratio=0.8)
    kurs_train, kurs_test = split_train_test_chronological(kurs_series, train_ratio=0.8)

    # 4. Grid Search pada data Training saja
    best_order_gold, best_aic_gold, _ = grid_search_arima_train(gold_train)
    best_order_kurs, best_aic_kurs, _ = grid_search_arima_train(kurs_train)

    # 5. Evaluasi pada data Testing
    eval_gold = evaluate_model_on_test(gold_train, gold_test, best_order_gold)
    eval_kurs = evaluate_model_on_test(kurs_train, kurs_test, best_order_kurs)

    # 6. Fit Ulang seluruh data dan Proyeksi Masa Depan (95% CI)
    fc_gold_df = fit_full_and_forecast(gold_series, best_order_gold, horizon=horizon)
    fc_kurs_df = fit_full_and_forecast(kurs_series, best_order_kurs, horizon=horizon)

    # 7. Estimasi Harga Emas IDR/gram dari Kedua Prediksi
    # Formula yang diminta: (prediksi close * prediksi usd_idr) / 31.1035
    pred_gold = fc_gold_df["forecast"].values
    pred_kurs = fc_kurs_df["forecast"].values
    est_idr_gram = (pred_gold * pred_kurs) / TROY_OUNCE_TO_GRAM

    # Estimasi rentang prediksi 95% untuk IDR/gram dengan simulasi Monte Carlo.
    # Asumsi: distribusi galat prediksi emas dan kurs independen. Karena itu,
    # interval gabungan ini merupakan estimasi bersyarat pada asumsi independensi,
    # bukan interval 95% eksak tanpa asumsi tambahan.
    n_simulations = 20_000
    rng = np.random.default_rng(seed=42)
    gold_simulations = rng.normal(
        loc=pred_gold,
        scale=fc_gold_df["se_mean"].to_numpy(dtype=float),
        size=(n_simulations, horizon),
    )
    kurs_simulations = rng.normal(
        loc=pred_kurs,
        scale=fc_kurs_df["se_mean"].to_numpy(dtype=float),
        size=(n_simulations, horizon),
    )
    idr_gram_simulations = (gold_simulations * kurs_simulations) / TROY_OUNCE_TO_GRAM
    lower_idr_gram = np.quantile(idr_gram_simulations, 0.025, axis=0)
    upper_idr_gram = np.quantile(idr_gram_simulations, 0.975, axis=0)

    # Gabungkan ke dalam satu DataFrame proyeksi masa depan
    forecast_table = pd.DataFrame({
        "date": future_dates,
        "step": list(range(1, horizon + 1)),
        # Emas USD
        "pred_gold_usd": pred_gold,
        "gold_usd_lower": fc_gold_df["lower_ci"].values,
        "gold_usd_upper": fc_gold_df["upper_ci"].values,
        # Kurs USD/IDR
        "pred_usd_idr": pred_kurs,
        "usd_idr_lower": fc_kurs_df["lower_ci"].values,
        "usd_idr_upper": fc_kurs_df["upper_ci"].values,
        # Estimasi Emas IDR/gram
        "est_idr_gram": est_idr_gram,
        "idr_gram_lower": lower_idr_gram,
        "idr_gram_upper": upper_idr_gram,
    })

    return {
        "df_historical": df,
        "last_date": last_date,
        "horizon": horizon,
        "future_dates": future_dates,
        "forecast_table": forecast_table,
        "models": {
            "gold": {
                "order": best_order_gold,
                "train_aic": eval_gold["train_aic"],
                "mae": eval_gold["mae"],
                "rmse": eval_gold["rmse"],
                "mape": eval_gold["mape"],
                "adf": adf_gold,
                "forecast_df": fc_gold_df,
            },
            "kurs": {
                "order": best_order_kurs,
                "train_aic": eval_kurs["train_aic"],
                "mae": eval_kurs["mae"],
                "rmse": eval_kurs["rmse"],
                "mape": eval_kurs["mape"],
                "adf": adf_kurs,
                "forecast_df": fc_kurs_df,
            },
        },
    }


# ---------------------------------------------------------------------------
# 9. Eksekusi Mandiri CLI (Uji Coba Langsung)
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("🪙 MODUL PERAMALAN ARIMA: HARGA EMAS DUNIA & KURS USD/IDR")
    print("=" * 70)

    try:
        results = run_forecasting_pipeline(horizon=7)
    except Exception as e:
        print(f"❌ Error saat menjalankan forecasting: {e}", file=sys.stderr)
        sys.exit(1)

    last_obs_date = results["last_date"].strftime("%Y-%m-%d")
    print(f"📅 Tanggal Observasi Terakhir: {last_obs_date}")
    print(f"📊 Total Observasi Historis : {len(results['df_historical'])} baris")

    # Diagnostik & Evaluasi Model Emas
    m_gold = results["models"]["gold"]
    print("\n" + "-" * 70)
    print("1. MODEL A: HARGA EMAS (USD/troy ounce)")
    print("-" * 70)
    print(f"   * Ordo ARIMA Terbaik  : ARIMA{m_gold['order']}")
    print(f"   * AIC (Training Set)  : {m_gold['train_aic']:.2f}")
    print(f"   * Uji ADF             : {m_gold['adf']['summary']}")
    print(f"   * Evaluasi Test MAE   : {m_gold['mae']:.2f}")
    print(f"   * Evaluasi Test RMSE  : {m_gold['rmse']:.2f}")
    print(f"   * Evaluasi Test MAPE  : {m_gold['mape']:.2f}%")

    # Diagnostik & Evaluasi Model Kurs
    m_kurs = results["models"]["kurs"]
    print("\n" + "-" * 70)
    print("2. MODEL B: KURS USD/IDR")
    print("-" * 70)
    print(f"   * Ordo ARIMA Terbaik  : ARIMA{m_kurs['order']}")
    print(f"   * AIC (Training Set)  : {m_kurs['train_aic']:.2f}")
    print(f"   * Uji ADF             : {m_kurs['adf']['summary']}")
    print(f"   * Evaluasi Test MAE   : {m_kurs['mae']:.2f}")
    print(f"   * Evaluasi Test RMSE  : {m_kurs['rmse']:.2f}")
    print(f"   * Evaluasi Test MAPE  : {m_kurs['mape']:.2f}%")

    # Tabel Proyeksi
    fc_table = results["forecast_table"]
    print("\n" + "-" * 70)
    print("3. PROYEKSI PERAMALAN 7 HARI KERJA KE DEPAN (Estimasi Business Days)")
    print("-" * 70)
    for _, row in fc_table.iterrows():
        tgl = row["date"].strftime("%Y-%m-%d")
        gold_val = row["pred_gold_usd"]
        kurs_val = row["pred_usd_idr"]
        idr_gram = row["est_idr_gram"]
        print(
            f"   [{tgl}] Emas: ${gold_val:,.2f} | Kurs: Rp{kurs_val:,.2f} | "
            f"Est. IDR/gram: Rp{idr_gram:,.2f}"
        )

    print("\n" + "=" * 70)
    print("✅ PENGUJIAN FORECASTING SELESAI DENGAN SUKSES!")
    print("=" * 70)


if __name__ == "__main__":
    main()
