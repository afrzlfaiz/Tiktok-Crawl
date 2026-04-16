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
  - Menggunakan Playwright
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

## Menjalankan Website

Masuk ke folder `WEBSITE`, lalu install dependency:

```bash
pip install -r requirements.txt
python -m playwright install chromium
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
- playwright

## Catatan Penting

- Project ini memakai scraping langsung ke TikTok dan browser automation Playwright.
- Hasil scrape bisa berubah tergantung response TikTok, challenge anti-bot, dan kondisi jaringan.
- Folder `WEBSITE/outputs` dipakai untuk file hasil download.
- Untuk deploy demo di Render Free, project ini masih cocok untuk penggunaan ringan, tetapi tidak ditujukan untuk traffic besar atau beban scraping berat.

## Demo Website

Link: 
