"""
DAG dasar: ETL harga emas dari yfinance.

Alur: extract -> transform -> load
Letakkan file ini di folder dags/ pada repo, lalu arahkan Airflow ke folder itu.
Antar-task hanya mengirim PATH file lewat XCom, bukan DataFrame.
"""

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
from airflow import DAG

# Airflow 3 memindahkan PythonOperator; Airflow 2 memakai path lama
try:
    from airflow.providers.standard.operators.python import PythonOperator
except ImportError:
    from airflow.operators.python import PythonOperator

# ---------------------------------------------------------------------------
# Konfigurasi (ubah di sini saja)
# ---------------------------------------------------------------------------
TICKER_GOLD = "GC=F"         # emas futures (USD/troy ounce); alternatif: "GLD"
TICKER_USD_IDR = "IDR=X"     # kurs USD ke IDR
PERIOD = "1y"
INTERVAL = "1d"
TROY_OUNCE_TO_GRAM = 31.1035 # konversi 1 troy ounce ke gram

# Folder data relatif terhadap repo: <repo>/data  (dags/ ada di <repo>/dags)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# EXTRACT: ambil data mentah dari yfinance, simpan ke CSV
# ---------------------------------------------------------------------------
def extract(**context):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Download data harga emas
    df_gold = yf.download(
        TICKER_GOLD, period=PERIOD, interval=INTERVAL,
        auto_adjust=True, progress=False,
    )
    if df_gold.empty:
        raise ValueError(f"Data yfinance kosong untuk ticker {TICKER_GOLD}")
    if isinstance(df_gold.columns, pd.MultiIndex):
        df_gold.columns = df_gold.columns.get_level_values(0)

    # 2. Download data kurs USD ke IDR
    df_kurs = yf.download(
        TICKER_USD_IDR, period=PERIOD, interval=INTERVAL,
        auto_adjust=True, progress=False,
    )
    if df_kurs.empty:
        raise ValueError(f"Data yfinance kosong untuk ticker {TICKER_USD_IDR}")
    if isinstance(df_kurs.columns, pd.MultiIndex):
        df_kurs.columns = df_kurs.columns.get_level_values(0)

    gold_path = DATA_DIR / "gold_raw.csv"
    kurs_path = DATA_DIR / "kurs_raw.csv"

    df_gold.to_csv(gold_path)
    df_kurs.to_csv(kurs_path)

    print(f"[extract] gold {len(df_gold)} baris -> {gold_path}")
    print(f"[extract] kurs {len(df_kurs)} baris -> {kurs_path}")

    return {
        "gold": str(gold_path),
        "kurs": str(kurs_path),
    }


# ---------------------------------------------------------------------------
# TRANSFORM: bersihkan data, gabungkan, dan hitung harga dalam Rupiah
# ---------------------------------------------------------------------------
def transform(ti, **context):
    paths = ti.xcom_pull(task_ids="extract")
    
    # Baca data emas dan kurs
    df_gold = pd.read_csv(paths["gold"], parse_dates=["Date"])
    df_kurs = pd.read_csv(paths["kurs"], parse_dates=["Date"])

    # Standarisasi nama kolom ke huruf kecil
    df_gold.columns = [c.lower() for c in df_gold.columns]
    df_kurs.columns = [c.lower() for c in df_kurs.columns]

    # Bersihkan data emas
    df_gold = (
        df_gold.dropna(subset=["date", "close"])
               .drop_duplicates(subset="date")
               .sort_values("date")
               .reset_index(drop=True)
    )

    # Bersihkan data kurs (ambil kolom date dan close kurs)
    df_kurs = (
        df_kurs.dropna(subset=["date", "close"])
               .drop_duplicates(subset="date")
               .sort_values("date")
               .reset_index(drop=True)
    )
    df_kurs = df_kurs[["date", "close"]].rename(columns={"close": "usd_idr"})

    # Gabungkan (merge) data emas dan kurs berdasarkan tanggal
    # Gunakan left join & ffill agar jika ada perbedaan hari libur bursa, kurs tetap terisi
    df = pd.merge(df_gold, df_kurs, on="date", how="left")
    df["usd_idr"] = df["usd_idr"].ffill().bfill()

    # Perhitungan Emas dalam Rupiah (IDR)
    df["close_idr"] = df["close"] * df["usd_idr"]                           # IDR per troy ounce
    df["harga_per_gram_idr"] = df["close_idr"] / TROY_OUNCE_TO_GRAM          # IDR per gram

    # Indikator teknikal (USD)
    df["daily_return"] = df["close"].pct_change()
    df["ma_7"] = df["close"].rolling(7).mean()
    df["ma_30"] = df["close"].rolling(30).mean()

    # Indikator teknikal (Rupiah per gram)
    df["daily_return_idr"] = df["harga_per_gram_idr"].pct_change()
    df["ma_7_idr"] = df["harga_per_gram_idr"].rolling(7).mean()
    df["ma_30_idr"] = df["harga_per_gram_idr"].rolling(30).mean()

    path = DATA_DIR / "gold_clean.csv"
    df.to_csv(path, index=False)
    print(f"[transform] {len(df)} baris -> {path}")
    return str(path)


# ---------------------------------------------------------------------------
# LOAD: simpan hasil akhir (versi sederhana: CSV)
# ---------------------------------------------------------------------------
def load(ti, **context):
    clean_path = ti.xcom_pull(task_ids="transform")
    df = pd.read_csv(clean_path)

    out = DATA_DIR / "gold_final.csv"
    df.to_csv(out, index=False)
    print(f"[load] {len(df)} baris -> {out}")


# ---------------------------------------------------------------------------
# DAG
# ---------------------------------------------------------------------------
default_args = {
    "owner": "kelompok-x",            # ganti dengan nama kelompok
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="gold_price_etl",
    description="ETL harga emas dari yfinance",
    start_date=datetime(2026, 11, 1),
    schedule="@daily",               # Airflow < 2.4: schedule_interval="@daily"
    catchup=False,
    default_args=default_args,
    tags=["etl", "gold", "tugas-akhir"],
) as dag:

    t_extract = PythonOperator(task_id="extract", python_callable=extract)
    t_transform = PythonOperator(task_id="transform", python_callable=transform)
    t_load = PythonOperator(task_id="load", python_callable=load)

    t_extract >> t_transform >> t_load
