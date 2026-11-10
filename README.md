# ETL Harga Emas dengan Apache Airflow

Pipeline ETL sederhana: ambil harga emas (`GC=F`) dari yfinance, bersihkan, lalu simpan ke CSV.

```
extract -> transform -> load
```

## Struktur

```
etl-gold-airflow/
├── dags/
│   └── gold_price_etl.py   # definisi DAG
├── data/                   # dibuat otomatis saat DAG jalan (tidak di-commit)
├── requirements.txt
└── README.md
```

## Setup (sekali saja, di WSL)

Airflow hanya bisa jalan di Linux/WSL. Semua perintah di bawah dijalankan di terminal WSL.

**1. Clone repo di home WSL** (jangan di `/mnt/c/...`):

```bash
cd ~
git clone https://github.com/USERNAME/etl-gold-airflow.git
cd etl-gold-airflow
```

**2. Buat dan aktifkan venv:**

```bash
python3 -m venv venv
source venv/bin/activate
```

**3. Pasang Airflow dan yfinance** (butuh Python 3.12, beberapa menit):

```bash
AIRFLOW_VERSION=2.10.5
PYTHON_VERSION=3.12
CONSTRAINT="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

pip install "apache-airflow==${AIRFLOW_VERSION}" --constraint "${CONSTRAINT}"
pip install yfinance --constraint "${CONSTRAINT}"
```

**4. Cek:**

```bash
airflow version
```

Harus muncul `2.10.5`.

## Menjalankan (setiap kali mau bekerja)

```bash
cd ~/etl-gold-airflow
source venv/bin/activate
export AIRFLOW_HOME=~/etl-gold-airflow
airflow standalone
```

Tunggu sekitar 1 menit, catat **username dan password** yang muncul di layar, lalu buka
`http://localhost:8080` di browser.

Di halaman itu: cari DAG `gold_price_etl`, aktifkan (toggle), lalu klik tombol play dan pilih **Trigger DAG**.
Kalau tiga task berwarna hijau, hasilnya ada di folder `data/`.

> Tiap anggota punya Airflow sendiri di komputernya. Yang dibagikan lewat GitHub hanya kode.

## Cara kerja sama

Sebelum mulai bekerja:

```bash
git pull
```

Setelah selesai mengedit:

```bash
git add .
git commit -m "pesan singkat tentang perubahan"
git push
```

Aturan sederhana:
- Jangan dua orang mengedit file yang sama di waktu yang sama.
- Selalu `git pull` sebelum mulai.
- Jangan commit `venv/`, `logs/`, `airflow.db`, atau `data/` (sudah diabaikan lewat `.gitignore`).

## Masalah umum

| Masalah | Solusi |
|---|---|
| DAG tidak muncul | Tunggu 1-2 menit lalu refresh. Pastikan `AIRFLOW_HOME` sudah di-export. |
| `airflow: command not found` | venv belum aktif. Jalankan `source venv/bin/activate`. |
| Task `extract` gagal | Cek koneksi internet. yfinance kadang kena rate limit, coba trigger ulang. |
| Port 8080 sudah dipakai | Ada Airflow lain yang masih jalan. Tutup terminalnya dulu. |
