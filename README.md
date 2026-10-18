# 🛒 Digital Mart — Telegram Bot E-Commerce & Admin Panel

Sistem toko online produk digital otomatis 24/7 yang terintegrasi dengan **Bot Telegram**, **FastAPI Backend**, dan **Modern Web Admin Dashboard (React + Tailwind CSS)**.

Dilengkapi dengan sistem transaksi instan, webhook pembayaran (Saweria/QRIS Demo), pengiriman otomatis lisensi/akun ke pembeli via Telegram, serta fitur **Bulk Import Data menggunakan file CSV**.

---

## 🌟 Fitur Utama

1. **🤖 Bot Telegram Interaktif (aiogram 3)**
   - Perintah `/start` dengan menu interaktif.
   - Katalog produk dan ketersediaan stok real-time.
   - Tombol checkout otomatis yang menghasilkan invoice dan tautan pembayaran.
   - Pengiriman otomatis voucher/akun langsung ke chat pembeli setelah status pembayaran `PAID`.

2. **📊 Admin Dashboard Dual-Mode**
   - **Modern React SPA** (`frontend/`): Menggunakan React 19, Tailwind CSS, Lucide Icons, dan Axios.
   - **Server-Side Rendered (SSR) Panel** (`http://127.0.0.1:8000/admin`): Ringan dan langsung siap pakai via Jinja2 & Tailwind CSS CDN.
   - Ringkasan pendapatan, transaksi berhasil, dan stok siap kirim.
   - Manajemen kategori dan katalog produk (CRUD).
   - Log transaksi dengan tautan simulasi pembayaran demo.

3. **📥 Import Data Massal via CSV (Fitur Terbaru)**
   - **Upload Stok via CSV**: Memasukkan ratusan akun/voucher sekaligus ke dalam produk tertentu atau otomatis berdasarkan kolom `product_code`.
   - **Upload Katalog Produk via CSV**: Menambahkan banyak produk sekaligus beserta nama, harga, deskripsi, icon, dan kategori (kategori otomatis dibuat jika belum ada).
   - Dilengkapi tombol **Unduh Template CSV** langsung dari dashboard untuk kemudahan pengisian data.

4. **⚡ Demo & Presentation Ready**
   - Halaman simulasi bayar interaktif di `/pay/{reference}` lengkap dengan QRIS dan tombol **"Simulasi Bayar Sekarang (1-Click Demo)"**.
   - Sangat ideal untuk presentasi tanpa perlu mengeluarkan uang sungguhan.
   - Sekali klik, status langsung `PAID`, stok berkurang, dan bot langsung mengirim lisensi ke Telegram!

5. **🔒 Aman untuk GitHub**
   - Dilengkapi `.gitignore` lengkap (mencegah file `.env`, file database `*.db`, `node_modules`, dan `venv` terunggah ke repositori publik).
   - Disediakan `.env.example` sebagai panduan konfigurasi.

---

## 📂 Struktur Repositori

```text
Bot_Telegram/
├── backend/
│   ├── templates/
│   │   └── dashboard.html      # Template Jinja2 admin panel bawaan FastAPI
│   ├── samples/
│   │   ├── sample_products.csv # Contoh berkas CSV katalog produk siap pakai
│   │   └── sample_stocks.csv   # Contoh berkas CSV stok voucher/akun siap pakai
│   ├── admin_web.py            # Router admin, API dashboard, dan upload CSV
│   ├── backend.py              # Aplikasi utama FastAPI & handler pembayaran
│   ├── database.py             # Akses database SQLite aiosqlite & import CSV
│   ├── main.py                 # Bot Telegram aiogram 3 runner
│   ├── requirements.txt        # Dependensi Python
│   ├── .env.example            # Contoh variabel lingkungan
│   └── .env                    # Variabel konfigurasi lokal (jangan di-commit)
├── frontend/                   # Dashboard SPA React + Vite + Tailwind
│   ├── src/
│   │   ├── services/api.js     # Axios client & service upload CSV
│   │   ├── App.jsx             # Antarmuka dashboard React utama
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── .gitignore                  # Aturan ignore Git (aman untuk push ke GitHub)
└── README.md                   # Dokumentasi proyek
```

---

## 🚀 Panduan Menjalankan Sistem

### Cara Cepat (1-Click di Windows)
Di folder utama proyek (`Bot_Telegram`), Anda cukup klik ganda file berikut:
- **`run_all.bat`**: Menjalankan Backend dan Bot Telegram sekaligus di jendela terpisah.
- **`run_backend.bat`**: Menjalankan server backend FastAPI saja (`http://127.0.0.1:8000`).
- **`run_bot.bat`**: Menjalankan Bot Telegram aiogram 3.
- **`run_frontend.bat`**: Menjalankan Vite dev server untuk React Dashboard (`http://localhost:5173`).

---

### Cara Manual via Terminal

#### 1. Menjalankan Backend FastAPI (Python)

Bisa dijalankan langsung dari folder utama atau dari folder `backend`:

```bash
# Dari folder utama:
python backend/backend.py

# Atau masuk ke folder backend:
cd backend
python backend.py
```
*(Backend otomatis mendeteksi environment dan berjalan di `http://127.0.0.1:8000`)*

Backend akan aktif di: **`http://127.0.0.1:8000`**  
Dashboard bawaan dapat langsung dibuka di: **`http://127.0.0.1:8000/admin`** (Login: `admin` / `admin123`).
Swagger API Documentation: **`http://127.0.0.1:8000/docs`**.

---

### 2. Menjalankan Frontend React Dashboard

Buka terminal baru di folder `frontend`:

```bash
cd frontend

# Instal dependensi node (jika baru pertama kali clone):
npm install

# Jalankan server Vite:
npm run dev
```

Dashboard React modern akan aktif di: **`http://localhost:5173`**.

---

### 3. Menjalankan Bot Telegram

Buka terminal baru di folder `backend`:

```bash
cd backend
python main.py
```

Bot Telegram Anda sekarang aktif dan siap melayani pesanan 24/7!

---

## 📋 Panduan Format CSV

### 1. Template CSV Stok Akun (`template_stok.csv`)

| product_code | data |
| :--- | :--- |
| `steam-50k` | `STEAM-AAAA-BBBB-CCCC` |
| `spotify-1m` | `user1@email.com:pass123` |
| `netflix-1m` | `netflix.vip@mail.com:secret456` |

> **Catatan:** Jika Anda memilih produk target di menu dropdown saat upload, kolom `product_code` bersifat opsional dan cukup isi kolom `data`.

### 2. Template CSV Katalog Produk (`template_produk.csv`)

| code | name | price | category | description | icon_url |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `youtube-1m` | YouTube Premium 1 Bulan | 20000 | Streaming | Akun YouTube Premium Bebas Iklan | https://cdn.simpleicons.org/youtube |
| `canva-pro` | Canva Pro 1 Tahun | 25000 | Desain | Akun Canva Pro Desain Edu/Team | https://cdn.simpleicons.org/canva |

---

## 🎯 Panduan Alur Presentasi / Demo Lancar

Berikut skenario rekomendasi saat presentasi:

1. **Tunjukkan Dashboard Admin (`http://localhost:5173`)**:
   - Jelaskan metrik: Total Pendapatan, Transaksi Berhasil, dan Stok Tersedia.
   - Tunjukkan tabel **Katalog Produk & Stok** dan **Kategori Aktif**.
2. **Demonstrasikan Fitur Upload CSV**:
   - Klik tombol **"Upload CSV"**.
   - Pilih tab **"Upload Katalog Produk"**, pilih file `backend/samples/sample_products.csv`, klik **Upload**.
   - Tunjukkan produk baru langsung bertambah ke katalog!
   - Pilih tab **"Upload Stok Akun"**, pilih file `backend/samples/sample_stocks.csv`, klik **Upload**.
   - Tunjukkan angka stok ready langsung terisi otomatis!
3. **Buka Telegram dan Chat ke Bot**:
   - Ketik `/start`.
   - Klik **"📋 Lihat Katalog & Stok"**.
   - Bot akan membalas dengan daftar produk dan status stok ready.
   - Klik tombol **"Beli [Nama Produk]"**.
   - Bot mengeluarkan instruksi pembayaran dan tombol **"💳 Bayar Sekarang"**.
4. **Simulasi Pembayaran (1-Click Demo)**:
   - Klik tautan pembayaran atau klik **"Bayar Demo"** pada tabel transaksi di Dashboard.
   - Halaman checkout QRIS terbuka di browser.
   - Klik tombol hijau **"⚡ Simulasi Bayar Sekarang (1-Click Demo)"**.
   - Sistem memproses pembayaran seketika!
5. **Cek Hasil**:
   - Buka Telegram: Bot **langsung mengirimkan akun/voucher digital** secara otomatis ke chat Anda!
   - Kembali ke Dashboard Admin: Pendapatan toko otomatis bertambah, stok berkurang 1, dan status transaksi berubah menjadi **PAID**.

---

## 📤 Langkah Push ke GitHub

Pastikan berkas rahasia `.env` tidak ter-push (sudah dilindungi oleh `.gitignore`):

```bash
# 1. Inisialisasi git (jika belum)
git init

# 2. Tambahkan semua file yang aman
git add .

# 3. Buat commit pertama
git commit -m "feat: complete digital store telegram bot with react admin & csv upload"

# 4. Tambahkan remote repository github Anda
git remote add origin https://github.com/USERNAME_ANDA/NAMA_REPO.git

# 5. Push ke GitHub
git branch -M main
git push -u origin main
```

---

## 🛠️ Lisensi
Didistribusikan untuk keperluan tugas/bisnis toko digital. Bebas dikembangkan sesuai kebutuhan.
