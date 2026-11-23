#!/usr/bin/env bash
# ==============================================================================
# Script Otomatis: Menyiapkan Lingkungan & Menjalankan Apache Airflow
# Jalankan di terminal WSL: bash run_airflow.sh (atau ./run_airflow.sh)
# ==============================================================================

set -e

# Pindah ke direktori proyek
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "=========================================================="
echo "💨 MENYIAPKAN & MENJALANKAN APACHE AIRFLOW"
echo "=========================================================="

# 1. Pastikan AIRFLOW_HOME selalu mengarah ke folder tugas ini
export AIRFLOW_HOME="$PROJECT_DIR"
echo "📁 AIRFLOW_HOME diatur ke: $AIRFLOW_HOME"

# 2. Cek & Aktifkan Virtual Environment
if [ -d "venv" ]; then
    echo "⚙️  Mengaktifkan Virtual Environment (venv)..."
    source venv/bin/activate
elif [ -d "/home/oeiyo/tugas_dag_emas/venv" ]; then
    echo "⚙️  Mengaktifkan Virtual Environment di path absolut..."
    source /home/oeiyo/tugas_dag_emas/venv/bin/activate
else
    echo "📦 Virtual environment tidak ditemukan. Membuat venv baru..."
    python3 -m venv venv
    source venv/bin/activate
fi

# 3. Cek apakah Apache Airflow dan yfinance sudah terpasang
if ! command -v airflow &> /dev/null; then
    echo "📦 Apache Airflow belum terpasang di venv."
    echo "⏳ Memasang Apache Airflow 2.10.5 (proses ini membutuhkan waktu 1-3 menit)..."
    
    AIRFLOW_VERSION="2.10.5"
    PYTHON_VERSION="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    CONSTRAINT="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"
    
    python -m pip install "apache-airflow==${AIRFLOW_VERSION}" --constraint "${CONSTRAINT}"
    echo "✅ Apache Airflow berhasil dipasang."
fi

if ! python -c "import yfinance" &> /dev/null; then
    echo "📦 Memasang dependensi yfinance untuk ekstraksi data..."
    python -m pip install yfinance
    echo "✅ yfinance berhasil dipasang."
fi

# 4. Tampilkan Info Akun jika file password tersedia
if [ -f "standalone_admin_password.txt" ]; then
    PASSWORD=$(cat standalone_admin_password.txt)
    echo "----------------------------------------------------------"
    echo "🔑 INFO LOGIN AIRFLOW (Bawaan):"
    echo "   Username: admin"
    echo "   Password: $PASSWORD"
    echo "----------------------------------------------------------"
fi

echo "🚀 Menjalankan Airflow Standalone..."
echo "Buka browser Anda di: http://localhost:8080"
echo "Tekan Ctrl+C di terminal ini untuk mematikan Airflow."
echo "=========================================================="

# 5. Jalankan Airflow Standalone
airflow standalone
