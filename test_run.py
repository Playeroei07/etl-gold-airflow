"""
Script uji coba cepat tanpa harus menyalakan Airflow Webserver.
Jalankan di WSL: python test_run.py
"""
import pandas as pd
from dags.gold_price_etl import extract, transform, load

class DummyTaskInstance:
    """Simulasi XCom milik Airflow untuk pengujian lokal"""
    def __init__(self, data_dict):
        self.data_dict = data_dict

    def xcom_pull(self, task_ids):
        return self.data_dict.get(task_ids)

print("=" * 60)
print("1. MENGETES TAHAP EXTRACT (Download Emas + Kurs Rupiah)")
print("=" * 60)
paths = extract()
print("Hasil extract paths:", paths)

print("\n" + "=" * 60)
print("2. MENGETES TAHAP TRANSFORM (Merge & Hitung IDR per gram)")
print("=" * 60)
ti = DummyTaskInstance({"extract": paths})
clean_path = transform(ti)

print("\n" + "=" * 60)
print("3. MENGETES TAHAP LOAD (Simpan Final)")
print("=" * 60)
ti_load = DummyTaskInstance({"transform": clean_path})
load(ti_load)

print("\n" + "=" * 60)
print("HASIL DATASET FINAL (5 Baris Terakhir):")
print("=" * 60)
df_final = pd.read_csv("data/gold_final.csv")
print(df_final[["date", "close", "usd_idr", "close_idr", "harga_per_gram_idr"]].tail(5))

print("\n" + "🎉 SEMUA TEST BERHASIL TANPA ERROR! 🎉")
