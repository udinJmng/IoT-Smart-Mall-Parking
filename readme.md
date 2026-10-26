# 🚗 Smart Park API

> **Not a final product**  
> *1 fork dan pull req = orang baik sedunia* 🙏

API backend buat sistem parkir pintar (FastAPI + MySQL). Buat yang mau nembak endpoint dari frontend web, mobile app, modul IoT, atau skrip kamera CV, nih contekan dokumentasi API-nya pake bahasa manusia biar ga pusing.

---

## 🛠️ Base URL
Biasanya jalan di lokal:
```text
http://127.0.0.1:8000
```
*(Atau cek port di file `.env` lu kalau diubah).*

Mau tes langsung lewat browser sambil klik-klik? Buka Swagger UI bawaan FastAPI di:  
👉 `http://127.0.0.1:8000/docs`

---

## 📡 Daftar Endpoint

### 1. `GET /api/parking`
> *"Woy, slot mana aja yang lagi kosong sama yang udah keisi?"*

Dipake buat narik semua data slot parkir dari database. Pas banget buat nampilin layout denah parkiran secara realtime di frontend.

- **Method:** `GET`
- **URL:** `/api/parking`
- **Response Sukses (200 OK):**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "slot_name": "A1",
      "status": "terisi",
      "warna": "hitam",
      "plat": "B 1234 ABC"
    },
    {
      "id": 2,
      "slot_name": "A2",
      "status": "kosong",
      "warna": "-",
      "plat": "-"
    }
  ]
}
```

---

### 2. `GET /api/parking/plate/{plat_query}`
> *"Mobil si bos platnya '1234' parkir di slot mana dah?"*

Dipake buat nyari posisi mobil berdasarkan plat nomor. Pencariannya udah fleksibel (pake `LIKE %plat%`), jadi ngetik sebagian angka/huruf platnya aja tetep bakal ketemu.

- **Method:** `GET`
- **URL:** `/api/parking/plate/{plat_query}`
  - Contoh: `/api/parking/plate/1234` atau `/api/parking/plate/B 1234 ABC`
- **Response Kalau Ketemu:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "slot_name": "A1",
      "status": "terisi",
      "warna": "hitam",
      "plat": "B 1234 ABC"
    }
  ]
}
```
- **Response Kalau Ga Ketemu:**
```json
{
  "success": false,
  "message": "Kendaraan dengan plat 'D 9999 XX' tidak ditemukan di slot manapun."
}
```

---

### 3. `PUT /api/parking/{slot_name}`
> *"Eh kamera/sensor ngeliat ada mobil baru masuk (atau baru cabut), tolong update slot ini!"*

Dipake buat ngubah status slot tertentu. Biasanya endpoint ini yang ditembak otomatis sama program kamera CV atau sensor pas ada perubahan kendaraan.

- **Method:** `PUT`
- **URL:** `/api/parking/{slot_name}`
  - Contoh: `/api/parking/A1`
- **Headers:** `Content-Type: application/json`
- **Request Body (Contoh mobil masuk / terisi):**
```json
{
  "status": "terisi",
  "warna": "putih",
  "plat": "DK 5678 XY"
}
```
*(Catatan: field `warna` dan `plat` itu opsional, kalau ga dikirim default-nya bakal jadi `"-"`)*

- **Request Body (Contoh mobil keluar / kosongin slot):**
```json
{
  "status": "kosong",
  "warna": "-",
  "plat": "-"
}
```

- **Response Sukses:**
```json
{
  "success": true,
  "message": "Slot A1 berhasil di-update!",
  "updated_data": {
    "status": "terisi",
    "warna": "putih",
    "plat": "DK 5678 XY"
  }
}
```

- **Response Kalau Slot Ga Ada di DB (404 Not Found):**
```json
{
  "detail": "Slot Z99 tidak ditemukan di database!"
}
```

---

## 🚀 Cara Jalanin Backend API

1. Bikin & aktifin virtual environment:
   ```bash
   py -m venv .venv
   .venv\Scripts\activate
   ```
2. Pastiin dependencies udah keinstall (`fastapi`, `uvicorn`, `mysql-connector-python`, `python-dotenv`, dll).
3. Buat file `.env` di dalam folder `backend/api/`:
   ```env
   DB_HOST=localhost
   DB_USER=root
   DB_PASSWORD=
   DB_NAME=smart_parking
   PORT=8000
   ```
4. Gas jalanin server:
   ```bash
   cd backend/api
   py -m uvicorn main:app --reload
   ```