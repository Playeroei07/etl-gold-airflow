#!/usr/bin/env bash
# ==============================================================================
# Script Otomatis: Menjalankan Dashboard Monitoring & Forecasting Harga Emas
# Bagian dari proyek: Gold Price Monitoring (etl-gold-airflow)
#
# Alur:
# 1. Mengarahkan working directory ke root repository.
# 2. Memeriksa keberadaan venv.
# 3. Mengaktifkan venv yang sudah ada.
# 4. Memeriksa/memasang dependensi dari dashboard-requirements.txt tanpa merusak Airflow.
# 5. Memeriksa keberadaan data/gold_final.csv.
# 6. Menjalankan aplikasi Streamlit pada port 8501.
# ==============================================================================

set -e

# 1. Arahkan working directory ke root repositori
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "=========================================================="
echo "🪙 MENYIAPKAN & MENJALANKAN DASHBOARD HARGA EMAS"
echo "=========================================================="
echo "📁 Direktori Proyek: $PROJECT_DIR"

# 2. Periksa Virtual Environment di dalam repository (tanpa path akun yang hard-coded)
if [ -d "$PROJECT_DIR/venv" ]; then
    VENV_PATH="$PROJECT_DIR/venv"
else
    echo "❌ ERROR: Virtual environment 'venv' tidak ditemukan!"
    echo "   Pastikan environment tersedia di: $PROJECT_DIR/venv"
    exit 1
fi

# 3. Aktifkan Virtual Environment yang Sudah Ada
echo "⚙️  Mengaktifkan Virtual Environment di $VENV_PATH..."
source "$VENV_PATH/bin/activate"

# 4. Periksa dan pasang dependensi dashboard di venv bersama.
# --no-deps mencegah pip mengubah paket transitif yang juga dipakai Airflow.
echo "📦 Memeriksa dependensi dari dashboard-requirements.txt..."
if [ ! -f "dashboard-requirements.txt" ]; then
    echo "❌ ERROR: dashboard-requirements.txt tidak ditemukan!"
    exit 1
fi

# Pastikan kondisi dependency environment saat ini konsisten sebelum instalasi.
if ! python -m pip check; then
    echo "❌ ERROR: Environment memiliki konflik dependensi sebelum instalasi."
    echo "   Periksa konflik tersebut sebelum menjalankan dashboard."
    exit 1
fi

python -m pip install --no-deps -r dashboard-requirements.txt --quiet

# Verifikasi ulang; hentikan script jika ada konflik atau dependensi transitif hilang.
if ! python -m pip check; then
    echo "❌ ERROR: Dependensi dashboard menimbulkan konflik atau ada paket transitif yang hilang."
    echo "   Karena venv ini juga digunakan Airflow, jangan lanjutkan sebelum konflik dibereskan."
    exit 1
fi
echo "✅ Dependensi dashboard terpasang dan pemeriksaan pip check berhasil."

# 5. Periksa Keberadaan Dataset Hasil ETL
DATA_FILE="$PROJECT_DIR/data/gold_final.csv"
if [ ! -f "$DATA_FILE" ]; then
    echo "❌ ERROR: Dataset '$DATA_FILE' tidak ditemukan!"
    echo "   Dashboard membutuhkan data hasil pipeline ETL Airflow."
    echo "   Silakan jalankan pipeline terlebih dahulu:"
    echo "     - Opsi A: python test_run.py"
    echo "     - Opsi B: bash run_airflow.sh (lalu trigger DAG gold_price_etl)"
    exit 1
fi

echo "✅ Dataset ditemukan: $DATA_FILE ($(wc -l < "$DATA_FILE") baris)"

# 6. Jalankan Streamlit pada Port 8501
PORT=8501
echo "----------------------------------------------------------"
echo "🚀 Menjalankan Streamlit Dashboard pada port $PORT..."
echo "🌐 Akses dashboard melalui browser Anda:"
echo "   👉 http://localhost:$PORT"
WSL_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [ -n "$WSL_IP" ]; then
    echo "   👉 http://$WSL_IP:$PORT  (IP WSL, jika localhost tidak dapat diakses)"
fi
echo "   (Tekan Ctrl+C di terminal ini untuk menghentikan server)"
echo "----------------------------------------------------------"

streamlit run dashboard.py --server.port $PORT --server.address 0.0.0.0
