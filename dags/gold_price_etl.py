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
TICKER = "GC=F"          # emas futures (USD/troy ounce); alternatif: "GLD"
PERIOD = "1y"
INTERVAL = "1d"

# Folder data relatif terhadap repo: <repo>/data  (dags/ ada di <repo>/dags)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# EXTRACT: ambil data mentah dari yfinance, simpan ke CSV
# ---------------------------------------------------------------------------
def extract(**context):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    df = yf.download(
        TICKER, period=PERIOD, interval=INTERVAL,
        auto_adjust=True, progress=False,
    )
    if df.empty:
        raise ValueError(f"Data yfinance kosong untuk ticker {TICKER}")

    # yfinance versi baru kadang menghasilkan kolom MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    path = DATA_DIR / "gold_raw.csv"
    df.to_csv(path)
    print(f"[extract] {len(df)} baris -> {path}")
    return str(path)


# ---------------------------------------------------------------------------
# TRANSFORM: bersihkan data dan tambah fitur sederhana
# ---------------------------------------------------------------------------
def transform(ti, **context):
    raw_path = ti.xcom_pull(task_ids="extract")
    df = pd.read_csv(raw_path, parse_dates=["Date"])

    df.columns = [c.lower() for c in df.columns]
    df = (
        df.dropna()
          .drop_duplicates(subset="date")
          .sort_values("date")
          .reset_index(drop=True)
    )

    df["daily_return"] = df["close"].pct_change()
    df["ma_7"] = df["close"].rolling(7).mean()
    df["ma_30"] = df["close"].rolling(30).mean()

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
