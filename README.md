# Tiktok Crawl

Project ini berisi beberapa metode scraping TikTok dan sebuah antarmuka web Flask untuk demo penggunaan semuanya dalam satu tempat.

## Fitur

### Script CLI

- `1 - scraping komen.py`
  - Ambil komentar dari link TikTok atau `video ID`
  - Mendukung komentar utama saja atau komentar + reply
  - Bisa simpan hasil ke Excel

- `2 - scraping video.py`
  - Cari video TikTok berdasarkan keyword
  - Via TikTok Signature Server (tanpa browser lokal)
  - Menyimpan hasil ke JSON

- `3 - crawl komen.py`
  - Workflow gabungan: `keyword -> video -> komentar`
  - Input jumlah video dan jumlah komentar per video
  - Menyimpan hasil gabungan ke Excel

### Website Flask

Folder `WEBSITE` menyediakan UI demo untuk tiga metode:

- `Komentar`
  - Input link TikTok atau `video ID`
  - Pilih jumlah komentar
  - Opsional ambil reply

- `Video`
  - Input keyword pencarian
  - Tentukan jumlah video yang ingin diambil

- `Crawl`
  - Input keyword
  - Tentukan jumlah video
  - Tentukan jumlah komentar per video

UI juga menyediakan:

- preview hasil langsung di halaman
- file download hasil scrape
- loading overlay saat proses berjalan

## Struktur Project

```text
.
|-- 1 - scraping komen.py
|-- 2 - scraping video.py
|-- 3 - crawl komen.py
`-- WEBSITE
    |-- app.py
    |-- requirements.txt
    |-- outputs
    |-- services
    |-- static
    `-- templates
```

## Signature Server (wajib untuk pencarian video)

Semua pencarian video (CLI & website) memakai signature server
[tiktok-signature-python](https://github.com/afrzlfaiz/tiktok-signature-python).
`main.py` di server menandatangani URL API TikTok (X-Bogus, msToken, dll.)
dengan browser Playwright di sisi server; skrip di project ini tinggal
memanggil `GET /health` dan `POST /fetch` lewat `requests` — tidak butuh
Playwright/browser sendiri.

> `1 - scraping komen.py` tidak butuh server ini; endpoint komentar masih
> dipanggil langsung ke TikTok.

Jalankan server dulu di terminal terpisah:

```bash
git clone https://github.com/afrzlfaiz/tiktok-signature-python.git
cd tiktok-signature-python
pip install -r requirements.txt
python -m playwright install chromium   # sekali saja, untuk browser server
python main.py                          # uvicorn di http://localhost:8080
```

Verifikasi: `curl localhost:8080/health` → `{"status":"ok",...}`.
URL server bisa di-override via env `TIKTOK_SIGNATURE_URL`.

## Menjalankan Website

Masuk ke folder `WEBSITE`, lalu install dependency:

```bash
pip install -r requirements.txt
```

Jalankan Flask app:

```bash
python app.py
```

Lalu buka:

```text
http://127.0.0.1:5000
```

## Dependency

Dependency utama website:

- Flask
- requests
- pandas
- openpyxl

Skrip CLI cukup: `requests`, `pandas`, `openpyxl`.

## Catatan Penting

- Pencarian video memakai signature server (`POST /fetch` di
  tiktok-signature-python). Playwright hanya dijalankan di sisi server —
  skrip crawl & website tidak perlu browser sendiri.
- Endpoint komentar masih dipanggil langsung via `requests`; bila TikTok mulai
  memblokirnya, komentar bisa dialihkan lewat `/fetch` server yang sama.
- Hasil scrape bisa berubah tergantung response TikTok, challenge anti-bot, dan kondisi jaringan.
- Folder `WEBSITE/outputs` dipakai untuk file hasil download.

