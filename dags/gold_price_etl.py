"""
DAG: ETL harga emas dari yfinance.
Alur: extract -> transform -> load (3 kotak sederhana)

Logika bisnis extract, transform, dan load dipisahkan ke dags/etl_tasks.py
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from airflow import DAG

# Airflow 3 memindahkan PythonOperator; Airflow 2 memakai path lama
try:
    from airflow.providers.standard.operators.python import PythonOperator
except ImportError:
    from airflow.operators.python import PythonOperator

# Import fungsi tugas ETL dari etl_tasks.py
try:
    from etl_tasks import extract, transform, load
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from etl_tasks import extract, transform, load

# ---------------------------------------------------------------------------
# Konfigurasi DAG
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

    # 1. Kotak Extract
    t_extract = PythonOperator(
        task_id="extract",
        python_callable=extract,
    )

    # 2. Kotak Transform
    t_transform = PythonOperator(
        task_id="transform",
        python_callable=transform,
    )

    # 3. Kotak Load
    t_load = PythonOperator(
        task_id="load",
        python_callable=load,
    )

    # Alur 3 kotak sederhana
    t_extract >> t_transform >> t_load
