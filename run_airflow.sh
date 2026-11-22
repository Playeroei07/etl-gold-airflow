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
    echo "⚠️  Folder 'venv' tidak ditemukan!"
    exit 1
fi

# 3. Tampilkan Info Akun jika file password tersedia
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

# 4. Jalankan Airflow Standalone
airflow standalone
