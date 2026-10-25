import cv2
import numpy as np
import easyocr
import re
import threading
import time

print("[INFO] Memuat model EasyOCR...")
reader = easyocr.Reader(['en'], gpu=False)
print("[INFO] Model siap! Membuka kamera...")

CAMERA_INDEX = 1

cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

class VideoStream:
    def __init__(self, src=CAMERA_INDEX):
        self.stream = cv2.VideoCapture(src)
        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.grabbed, self.frame = self.stream.read()
        self.stopped = False

    def start(self):
        threading.Thread(target=self.update, daemon=True).start()
        return self

    def update(self):
        while not self.stopped:
            if not self.grabbed:
                self.stop()
            else:
                self.grabbed, self.frame = self.stream.read()

    def read(self):
        return self.frame

    def stop(self):
        self.stopped = True
        self.stream.release()

vs = VideoStream(CAMERA_INDEX).start()
time.sleep(1.0)

def cek_warna(roi_bgr):
    small_roi = cv2.resize(roi_bgr, (50, 50))
    hsv = cv2.cvtColor(small_roi, cv2.COLOR_BGR2HSV)
    
    daftar_warna = {
        "MERAH": [
            (np.array([0, 100, 100]), np.array([10, 255, 255])),
            (np.array([160, 100, 100]), np.array([179, 255, 255]))
        ],
        "BIRU": [(np.array([95, 100, 100]), np.array([135, 255, 255]))],
        "HIJAU": [(np.array([35, 80, 80]), np.array([85, 255, 255]))],
        "KUNING": [(np.array([20, 100, 100]), np.array([34, 255, 255]))],
    }

    skor_tertinggi = 0
    warna_terdeteksi = "-"

    for nama_warna, rentang_list in daftar_warna.items():
        mask_total = np.zeros(hsv.shape[:2], dtype="uint8")
        for (bawah, atas) in rentang_list:
            mask = cv2.inRange(hsv, bawah, atas)
            mask_total = cv2.bitwise_or(mask_total, mask)
        
        jumlah_piksel = cv2.countNonZero(mask_total)
        if jumlah_piksel > skor_tertinggi and jumlah_piksel > (50 * 50 * 0.12):
            skor_tertinggi = jumlah_piksel
            warna_terdeteksi = nama_warna

    if warna_terdeteksi == "-" and np.mean(hsv[:, :, 2]) < 75:
        warna_terdeteksi = "HITAM"

    return warna_terdeteksi

frame_count = 0

slot_status = {
    "A1 (Kiri)": {"status": "KOSONG", "warna": "-", "plat": "-", "last_seen": 0},
    "A2 (Tengah)": {"status": "KOSONG", "warna": "-", "plat": "-", "last_seen": 0},
    "A3 (Kanan)": {"status": "KOSONG", "warna": "-", "plat": "-", "last_seen": 0}
}

while True:
    frame = vs.read()
    if frame is None:
        break

    h, w, _ = frame.shape
    lebar_kolom = w // 3
    y1, y2 = int(h * 0.25), int(h * 0.75)
    
    grids = {
        "A1 (Kiri)": (0, lebar_kolom),
        "A2 (Tengah)": (lebar_kolom, lebar_kolom * 2),
        "A3 (Kanan)": (lebar_kolom * 2, w)
    }

    for nama_slot, (x_start, x_end) in grids.items():
        roi = frame[y1:y2, x_start:x_end]
        
        plat_ditemukan = False
        teks_plat_baru = slot_status[nama_slot]["plat"]
        
        # OCR dijalankan berkala. Gambar DIUPGRADE (perbesar & grayscale) agar teks plat terbaca tajam
# OCR dijalankan berkala atau saat slot kosong
        if frame_count % 20 == 0 or slot_status[nama_slot]["status"] == "KOSONG":
            # Potong lagi bagian tengah ROI (ambil tinggi 40% sampai 80% dari ROI) 
            # supaya tulisan kecil masa berlaku di bawah plat terbuang
            rh, rw, _ = roi.shape
            roi_plat_saja = roi[int(rh * 0.4):int(rh * 0.8), int(rw * 0.2):int(rw * 0.8)]
            
            # Upscale & Grayscale khusus area plat
            roi_besar = cv2.resize(roi_plat_saja, (0, 0), fx=2.0, fy=2.0)
            gray_ocr = cv2.cvtColor(roi_besar, cv2.COLOR_BGR2GRAY)
            
            hasil_ocr = reader.readtext(gray_ocr, detail=0)
            if hasil_ocr:
                teks = " ".join(hasil_ocr).upper()
                teks_bersih = re.sub(r'[^A-Z0-9 ]', '', teks).strip()
                
                # Batasi panjang string maksimal (misal plat biasa cuma sekitar 5-9 karakter)
                if 3 <= len(teks_bersih) <= 10:
                    teks_plat_baru = teks_bersih
                    plat_ditemukan = True

        if plat_ditemukan or slot_status[nama_slot]["status"] == "TERISI":
            if plat_ditemukan:
                slot_status[nama_slot]["plat"] = teks_plat_baru
                slot_status[nama_slot]["last_seen"] = frame_count
            
            if frame_count - slot_status[nama_slot]["last_seen"] < 45:
                slot_status[nama_slot]["status"] = "TERISI"
                slot_status[nama_slot]["warna"] = cek_warna(roi)
            else:
                slot_status[nama_slot]["status"] = "KOSONG"
                slot_status[nama_slot]["warna"] = "-"
                slot_status[nama_slot]["plat"] = "-"
        else:
            slot_status[nama_slot]["status"] = "KOSONG"
            slot_status[nama_slot]["warna"] = "-"
            slot_status[nama_slot]["plat"] = "-"

        is_terisi = slot_status[nama_slot]["status"] == "TERISI"
        warna_box = (0, 0, 255) if is_terisi else (0, 255, 0)

        cv2.rectangle(frame, (x_start + 10, y1), (x_end - 10, y2), warna_box, 2)
        cv2.putText(frame, f"Slot {nama_slot}", (x_start + 15, y1 - 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2)
        cv2.putText(frame, f"Status: {slot_status[nama_slot]['status']}", (x_start + 15, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, warna_box, 2)
        
        if is_terisi:
            cv2.putText(frame, f"Warna: {slot_status[nama_slot]['warna']}", (x_start + 15, y2 + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 215, 255), 1)
            cv2.putText(frame, f"Plat: {slot_status[nama_slot]['plat']}", (x_start + 15, y2 + 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 215, 255), 1)

    frame_count += 1
    
    cv2.putText(frame, "SMART PARKING - HIGH ACCURACY OCR", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    cv2.imshow("Grid Parking Vision - High Accuracy", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

vs.stop()
cv2.destroyAllWindows()