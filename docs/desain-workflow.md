# Desain DAG dan Workflow ETL Harga Emas

## 1. Pendahuluan

Workflow ETL (Extract, Transform, Load) merupakan proses pengolahan data yang terdiri dari tiga tahapan utama, yaitu pengambilan data, pengolahan data, dan penyimpanan hasil pengolahan.

Pada proyek ini, workflow ETL diterapkan untuk mengolah data harga emas yang diperoleh dari Yahoo Finance menggunakan library yfinance. Proses ETL diatur dan dijalankan secara otomatis menggunakan Apache Airflow melalui sebuah DAG (Directed Acyclic Graph).

## 2. Tujuan DAG

DAG yang digunakan dalam proyek ini bernama `gold_price_etl`. DAG ini bertujuan untuk mengatur urutan proses ETL harga emas agar berjalan secara terstruktur, mulai dari pengambilan data hingga penyimpanan hasil akhir.

Data yang digunakan berasal dari instrumen Gold Futures dengan ticker `GC=F`, menggunakan data harian selama satu tahun terakhir.

## 3. Desain Workflow ETL

Workflow terdiri dari tiga task utama:

### A. Extract

Tahap Extract bertugas mengambil data harga emas dari Yahoo Finance menggunakan library yfinance.

Data yang diperoleh kemudian disimpan dalam format CSV dengan nama `gold_raw.csv` sebagai data mentah yang akan diproses pada tahap berikutnya.

### B. Transform

Tahap Transform bertugas membersihkan dan mengolah data mentah. Proses yang dilakukan meliputi:

- Mengubah nama kolom menjadi huruf kecil.
- Menghapus data kosong.
- Menghapus data duplikat berdasarkan tanggal.
- Mengurutkan data berdasarkan tanggal.
- Membuat fitur tambahan berupa daily_return, moving average 7 hari (MA 7), dan moving average 30 hari (MA 30).

Hasil pengolahan disimpan dalam file `gold_clean.csv`.

### C. Load

Tahap Load bertugas membaca hasil transformasi dan menyimpannya sebagai file `gold_final.csv`.

Pada implementasi ini, penyimpanan akhir masih menggunakan format CSV.

## 4. Diagram Alur DAG

Urutan hubungan antar-task dalam DAG adalah sebagai berikut:

```text
          START
            |
            v
       +---------+
       | EXTRACT |
       +---------+
            |
            v
      +-----------+
      | TRANSFORM |
      +-----------+
            |
            v
       +---------+
       |  LOAD   |
       +---------+
            |
            v
           END
```

Dependency antar-task ditentukan menggunakan operator `>>` pada Apache Airflow:

```python
t_extract >> t_transform >> t_load
```

Operator tersebut memastikan bahwa Transform hanya dijalankan setelah Extract berhasil, sedangkan Load dijalankan setelah Transform berhasil.

## 5. Komunikasi Antar-Task (XCom)

Apache Airflow menggunakan mekanisme XCom (Cross Communication) untuk mengirimkan informasi antar-task.

Pada workflow ini, informasi yang dikirim melalui XCom berupa lokasi file (file path), bukan seluruh isi DataFrame.

Task Extract mengembalikan lokasi file `gold_raw.csv`, kemudian Task Transform mengambil lokasi tersebut menggunakan `xcom_pull()`.

Mekanisme yang sama digunakan antara Task Transform dan Task Load. Dengan demikian, setiap task dapat bekerja secara terpisah dan lebih modular.

## 6. Alasan Pemilihan Workflow

Workflow Extract, Transform, dan Load dipilih karena memiliki tahapan yang berurutan dan sesuai dengan kebutuhan pengolahan data harga emas.

Beberapa alasan pemilihannya adalah:

1. **Alur proses terstruktur:** Setiap tahapan memiliki urutan kerja yang jelas.
2. **Modularitas:** Setiap task memiliki tanggung jawab masing-masing sehingga lebih mudah dikelola.
3. **Mudah dipantau:** Apache Airflow menyediakan pemantauan status setiap task.
4. **Mendukung retry:** Task dapat dicoba kembali ketika mengalami kegagalan.
5. **Komunikasi antar-task lebih efisien:** XCom digunakan untuk mengirimkan lokasi file tanpa memindahkan seluruh DataFrame.

## 7. Konfigurasi DAG

DAG menggunakan beberapa konfigurasi berikut:

- `dag_id`: gold_price_etl
- `schedule`: @daily
- `catchup`: False
- `retries`: 2 kali percobaan ulang.
- `retry_delay`: 2 menit.

Konfigurasi tersebut digunakan agar workflow dapat dijadwalkan secara harian serta memiliki mekanisme percobaan ulang ketika terjadi kegagalan pada task.
