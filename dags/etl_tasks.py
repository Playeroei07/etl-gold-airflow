"""
etl_tasks.py
=============================================================================
Modul Logika ETL (Extract, Transform, Load) Harga Emas dan Kurs USD/IDR.
Dipisahkan dari definisi DAG agar modular dan mudah diuji secara independen.
=============================================================================
"""

from pathlib import Path
import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------
TICKER_GOLD = "GC=F"         # Emas futures (USD/troy ounce); alternatif: "GLD"
TICKER_USD_IDR = "IDR=X"     # Kurs USD ke IDR
PERIOD = "1y"
INTERVAL = "1d"
TROY_OUNCE_TO_GRAM = 31.1035 # Konversi 1 troy ounce ke gram

# Folder data relatif terhadap repo: <repo>/data (dags/ ada di <repo>/dags)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# 1. EXTRACT: ambil data mentah dari yfinance, simpan ke CSV
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
# 2. TRANSFORM: bersihkan data, gabungkan, dan hitung harga dalam Rupiah
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
# 3. LOAD: simpan hasil akhir ke dataset final
# ---------------------------------------------------------------------------
def load(ti, **context):
    clean_path = ti.xcom_pull(task_ids="transform")
    df = pd.read_csv(clean_path)

    out = DATA_DIR / "gold_final.csv"
    df.to_csv(out, index=False)
    print(f"[load] {len(df)} baris -> {out}")

