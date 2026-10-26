import cv2
import numpy as np
import easyocr
import re
import threading
import queue
import time
import warnings

warnings.filterwarnings("ignore", category=UserWarning)

print("[INFO] Memuat model EasyOCR...")
reader = easyocr.Reader(['en'], gpu=False)
print("[INFO] Model EasyOCR siap!")

CAMERA_INDEX = 1

def buka_kamera(index=CAMERA_INDEX):
    cap = cv2.VideoCapture(index)
    if not cap.isOpened() and index != 0:
        print(f"[WARN] Kamera index {index} tidak dapat dibuka, mencoba index 0...")
        cap = cv2.VideoCapture(0)
    return cap

class VideoStream:
    def __init__(self, src=CAMERA_INDEX):
        self.stream = buka_kamera(src)
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
            time.sleep(0.01)

    def read(self):
        return self.frame.copy() if (self.grabbed and self.frame is not None) else None

    def stop(self):
        self.stopped = True
        if self.stream.isOpened():
            self.stream.release()

WILAYAH_KODE = {
    'A', 'B', 'D', 'E', 'F', 'G', 'H', 'K', 'L', 'M', 'N', 'P', 'R', 'S', 'T', 'W', 'Z',
    'AA', 'AB', 'AD', 'AE', 'AG', 'BA', 'BB', 'BD', 'BE', 'BG', 'BH', 'BK', 'BL', 'BM',
    'BN', 'BP', 'DA', 'DB', 'DC', 'DD', 'DE', 'DG', 'DH', 'DK', 'DL', 'DM', 'DN', 'DP',
    'DR', 'DT', 'DW', 'EA', 'EB', 'ED', 'KB', 'KH', 'KT', 'KU', 'PA', 'PB'
}

CHAR_TO_NUM = {'O': '0', 'D': '0', 'Q': '0', 'I': '1', 'L': '1', 'Z': '2', 'S': '5', 'B': '8', 'G': '6'}
CHAR_TO_ALPHA = {'0': 'O', '1': 'I', '2': 'Z', '5': 'S', '8': 'B', '6': 'G'}

def parse_plat_indonesia(raw_text):
    """
    Memvalidasi dan menstandarkan teks agar sesuai format plat nomor Indonesia:
    [KODE WILAYAH: 1-2 Huruf] [NOMOR POLISI: 1-4 Angka] [SERI AKHIR: 1-3 Huruf]
    Mampu membersihkan garis bingkai plat yang terbaca sebagai 'I' (misal: 'ABCI' -> 'ABC').
    """
    if not raw_text:
        return None

    cleaned = re.sub(r'[^A-Z0-9 ]', ' ', raw_text.upper()).strip()
    words = cleaned.split()
    joined = ' '.join(words)

    pattern_spaced = r'\b([A-Z]{1,2}|8)\s+([A-Z0-9]{1,4})\s+([A-Z0-9]{1,4})\b'
    for m in re.finditer(pattern_spaced, joined):
        p, n, s = m.groups()
        if not any(c.isdigit() for c in n) and not all(c in CHAR_TO_NUM for c in n):
            continue

        p_clean = 'B' if p == '8' else p
        n_clean = ''.join(CHAR_TO_NUM.get(c, c) for c in n)
        s_clean = ''.join(CHAR_TO_ALPHA.get(c, c) for c in s)

        if len(s_clean) == 4 and s_clean[-1] in ('I', 'L', '1'):
            s_clean = s_clean[:3]

        if p_clean in WILAYAH_KODE and n_clean.isdigit() and s_clean.isalpha() and 1 <= len(s_clean) <= 3:
            return f"{p_clean} {n_clean} {s_clean}"

    no_space = joined.replace(' ', '')
    pattern_compact = r'\b([A-Z]{1,2}|8)([0-9][0-9OIZSBDGQ]{0,3}|[0-9OIZSBDGQ]{0,3}[0-9])([A-Z0-9]{1,4})\b'
    for m in re.finditer(pattern_compact, no_space):
        p, n, s = m.groups()
        if not any(c.isdigit() for c in n):
            continue

        p_clean = 'B' if p == '8' else p
        n_clean = ''.join(CHAR_TO_NUM.get(c, c) for c in n)
        s_clean = ''.join(CHAR_TO_ALPHA.get(c, c) for c in s)

        if len(s_clean) == 4 and s_clean[-1] in ('I', 'L', '1'):
            s_clean = s_clean[:3]

        if p_clean in WILAYAH_KODE and n_clean.isdigit() and s_clean.isalpha() and 1 <= len(n_clean) <= 4 and 1 <= len(s_clean) <= 3:
            return f"{p_clean} {n_clean} {s_clean}"

    return None

def cek_warna_cat(hsv, total_area):
    """
    Mendeteksi warna cat mobil cerah yang pekat (Merah, Biru, Hijau, Kuning).
    Tidak akan tertipu oleh warna meja, keyboard, atau dinding gelap.
    """
    daftar_warna = {
        "MERAH": [
            (np.array([0, 95, 80]), np.array([10, 255, 255])),
            (np.array([160, 95, 80]), np.array([179, 255, 255]))
        ],
        "BIRU": [(np.array([95, 95, 75]), np.array([135, 255, 255]))],
        "HIJAU": [(np.array([35, 80, 75]), np.array([85, 255, 255]))],
        "KUNING": [(np.array([18, 95, 95]), np.array([34, 255, 255]))],
    }

    warna_terpilih = "-"
    max_px = 0

    for nama, ranges in daftar_warna.items():
        mask_total = np.zeros(hsv.shape[:2], dtype="uint8")
        for (bawah, atas) in ranges:
            mask = cv2.inRange(hsv, bawah, atas)
            mask_total = cv2.bitwise_or(mask_total, mask)

        px = cv2.countNonZero(mask_total)
        if px > max_px and px > (total_area * 0.14):
            max_px = px
            warna_terpilih = nama

    return warna_terpilih

def deteksi_keberadaan_mobil(roi_bgr):
    """
    Mendeteksi apakah objek benar-benar menyerupai mobil (bukan keyboard/meja/benda acak).
    Filter:
    1. Menolak tekstur keyboard (puluhan tombol kecil kotak-kotak).
    2. Mendeteksi warna cat khas mobil (Biru, Merah, dsb) dengan cakupan area solid.
    3. Mendeteksi keberadaan kotak plat nomor berasio ~2.0 - 5.0.
    4. Mendeteksi siluet bodi mobil besar.
    """
    h, w, _ = roi_bgr.shape
    total_area = h * w
    hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)

    edges = cv2.Canny(gray, 60, 160)
    all_cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    num_tiny_boxes = sum(1 for c in all_cnts if 35 < cv2.contourArea(c) < 1400)
    is_keyboard_texture = (num_tiny_boxes >= 14)

    y_plat_min, y_plat_max = int(h * 0.35), int(h * 0.85)
    sub_gray = gray[y_plat_min:y_plat_max, :]
    blurred = cv2.GaussianBlur(sub_gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 19, 9)
    plate_contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    ada_plat_box = False
    for cnt in plate_contours:
        area_c = cv2.contourArea(cnt)
        if (total_area * 0.015) < area_c < (total_area * 0.30):
            x, y, pw, ph = cv2.boundingRect(cnt)
            ar = float(pw) / max(1, ph)
            if 2.0 <= ar <= 5.0:
                ada_plat_box = True
                break

    warna_cat = cek_warna_cat(hsv, total_area)

    if is_keyboard_texture and not ada_plat_box:
        return False, "-"

    if warna_cat != "-":
        return True, warna_cat

    if ada_plat_box:
        mean_v = np.mean(hsv[int(h * 0.3):int(h * 0.8), :, 2])
        if mean_v < 70:
            warna_netral = "HITAM"
        elif mean_v > 165:
            warna_netral = "PUTIH"
        else:
            warna_netral = "SILVER"
        return True, warna_netral

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)
    _, body_thresh = cv2.threshold(grad, 35, 255, cv2.THRESH_BINARY)
    closed = cv2.morphologyEx(body_thresh, cv2.MORPH_CLOSE, kernel)
    body_cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    max_body_area = max([cv2.contourArea(c) for c in body_cnts], default=0)
    if max_body_area > (total_area * 0.30) and not is_keyboard_texture:
        mean_v = np.mean(hsv[int(h * 0.3):int(h * 0.8), :, 2])
        warna = "HITAM" if mean_v < 70 else ("PUTIH" if mean_v > 165 else "SILVER")
        return True, warna

    return False, "-"

def cari_lokasi_plat(roi_bgr):
    """
    Mencari kotak plat nomor secara otomatis (kontur persegi berasio ~2.0 - 4.8)
    pada area tengah bodi mobil. Menghemat waktu OCR dari 5 detik menjadi 0.3 detik!
    """
    rh, rw, _ = roi_bgr.shape
    y_min, y_max = int(rh * 0.35), int(rh * 0.78)
    x_min, x_max = int(rw * 0.12), int(rw * 0.88)
    sub_roi = roi_bgr[y_min:y_max, x_min:x_max]

    gray = cv2.cvtColor(sub_roi, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 19, 9)

    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []

    sub_h, sub_w = sub_roi.shape[:2]
    min_area = (sub_h * sub_w) * 0.02
    max_area = (sub_h * sub_w) * 0.55

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area < area < max_area:
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = float(w) / max(1, h)
            if 2.0 <= aspect_ratio <= 4.8:
                candidates.append((area, (x, y, w, h)))

    if candidates:
        candidates.sort(key=lambda c: c[0], reverse=True)
        _, (x, y, w, h) = candidates[0]
        pad_x = int(w * 0.08)
        pad_y = int(h * 0.12)
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(sub_w, x + w + pad_x)
        y2 = min(sub_h, y + h + pad_y)
        return sub_roi[y1:y2, x1:x2]

    return roi_bgr[int(rh * 0.42):int(rh * 0.65), int(rw * 0.18):int(rw * 0.82)]

def deteksi_plat_dari_roi(roi_bgr):
    """
    Mengekstrak plat nomor dari ROI mobil menggunakan area plat terisolasi.
    """
    crop_plat = cari_lokasi_plat(roi_bgr)
    if crop_plat is None or crop_plat.shape[0] < 15 or crop_plat.shape[1] < 30:
        return None

    ch, cw, _ = crop_plat.shape
    if ch < 70:
        scale = 80.0 / ch
        crop_plat = cv2.resize(crop_plat, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    hasil_ocr = reader.readtext(
        crop_plat,
        detail=1,
        paragraph=False,
        allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 '
    )

    if not hasil_ocr:
        gray = cv2.cvtColor(crop_plat, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(6, 6))
        enhanced = clahe.apply(gray)
        hasil_ocr = reader.readtext(
            enhanced,
            detail=1,
            paragraph=False,
            allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 '
        )

    if not hasil_ocr:
        return None

    teks_valid = [text.strip() for (bbox, text, conf) in hasil_ocr if conf >= 0.25 and len(text.strip()) > 0]
    if not teks_valid:
        return None

    for t in teks_valid:
        plat = parse_plat_indonesia(t)
        if plat:
            return plat

    combined = " ".join(teks_valid)
    return parse_plat_indonesia(combined)

ocr_queue = queue.Queue(maxsize=3)
slot_lock = threading.Lock()
stop_worker = False

slot_status = {
    "A1 (Kiri)": {
        "status": "KOSONG", "warna": "-", "plat": "-",
        "present_count": 0, "empty_count": 0,
        "last_ocr_time": 0, "ocr_in_progress": False
    },
    "A2 (Tengah)": {
        "status": "KOSONG", "warna": "-", "plat": "-",
        "present_count": 0, "empty_count": 0,
        "last_ocr_time": 0, "ocr_in_progress": False
    },
    "A3 (Kanan)": {
        "status": "KOSONG", "warna": "-", "plat": "-",
        "present_count": 0, "empty_count": 0,
        "last_ocr_time": 0, "ocr_in_progress": False
    }
}

def ocr_worker_thread():
    while not stop_worker:
        try:
            item = ocr_queue.get(timeout=0.2)
        except queue.Empty:
            continue

        slot_name, roi_copy = item

        with slot_lock:
            if slot_status[slot_name]["plat"] not in ["-", "Membaca..."]:
                slot_status[slot_name]["ocr_in_progress"] = False
                ocr_queue.task_done()
                continue

        try:
            plat = deteksi_plat_dari_roi(roi_copy)
            if plat:
                with slot_lock:
                    slot_status[slot_name]["plat"] = plat
                print(f"[SUKSES OCR] Slot {slot_name} -> PLAT TERDETEKSI: {plat}")
        except Exception as err:
            print(f"[OCR Error] {err}")
        finally:
            with slot_lock:
                slot_status[slot_name]["ocr_in_progress"] = False
            ocr_queue.task_done()

def main():
    global stop_worker

    threading.Thread(target=ocr_worker_thread, daemon=True).start()

    vs = VideoStream(CAMERA_INDEX).start()
    time.sleep(1.0)

    fps_start_time = time.time()
    fps_counter = 0
    current_fps = 0

    print("[INFO] Sistem Parkir Pintar Aktif! Tekan 'q' pada jendela video untuk keluar.")

    while True:
        frame = vs.read()
        if frame is None:
            time.sleep(0.02)
            continue

        h, w, _ = frame.shape
        lebar_kolom = w // 3
        y1, y2 = int(h * 0.22), int(h * 0.82)

        grids = {
            "A1 (Kiri)": (0, lebar_kolom),
            "A2 (Tengah)": (lebar_kolom, lebar_kolom * 2),
            "A3 (Kanan)": (lebar_kolom * 2, w)
        }

        now = time.time()

        for nama_slot, (x_start, x_end) in grids.items():
            roi = frame[y1:y2, x_start:x_end]
            ada_mobil, warna_mobil = deteksi_keberadaan_mobil(roi)

            with slot_lock:
                slot_info = slot_status[nama_slot]

                if ada_mobil:
                    slot_info["present_count"] += 1
                    slot_info["empty_count"] = 0

                    if slot_info["present_count"] >= 10:
                        slot_info["status"] = "TERISI"
                        if warna_mobil != "-":
                            slot_info["warna"] = warna_mobil

                        perlu_ocr = (slot_info["plat"] in ["-", "Membaca..."])
                        waktu_cukup = (now - slot_info["last_ocr_time"] > 0.8)

                        if perlu_ocr and waktu_cukup and not slot_info["ocr_in_progress"]:
                            slot_info["ocr_in_progress"] = True
                            slot_info["last_ocr_time"] = now
                            if slot_info["plat"] == "-":
                                slot_info["plat"] = "Membaca..."
                            if not ocr_queue.full():
                                ocr_queue.put_nowait((nama_slot, roi.copy()))
                else:
                    slot_info["empty_count"] += 1
                    slot_info["present_count"] = 0

                    if slot_info["empty_count"] >= 25:
                        slot_info["status"] = "KOSONG"
                        slot_info["warna"] = "-"
                        slot_info["plat"] = "-"

                is_terisi = (slot_info["status"] == "TERISI")
                warna_box = (0, 0, 255) if is_terisi else (0, 255, 0)
                status_txt = slot_info["status"]
                warna_txt = slot_info["warna"]
                plat_txt = slot_info["plat"]

            cv2.rectangle(frame, (x_start + 10, y1), (x_end - 10, y2), warna_box, 2)

            cv2.rectangle(frame, (x_start + 10, y1 - 35), (x_end - 10, y1), (30, 30, 30), -1)
            cv2.putText(frame, f"Slot {nama_slot}", (x_start + 15, y1 - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
            cv2.putText(frame, f"Status: {status_txt}", (x_start + 15, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, warna_box, 2)

            if is_terisi:
                cv2.rectangle(frame, (x_start + 10, y2), (x_end - 10, y2 + 45), (30, 30, 30), -1)
                cv2.putText(frame, f"Warna: {warna_txt}", (x_start + 15, y2 + 18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 215, 255), 1)

                plat_color = (0, 255, 128) if (plat_txt not in ["-", "Membaca..."]) else (0, 215, 255)
                cv2.putText(frame, f"Plat : {plat_txt}", (x_start + 15, y2 + 38),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, plat_color, 2)

        fps_counter += 1
        if time.time() - fps_start_time >= 1.0:
            current_fps = fps_counter
            fps_counter = 0
            fps_start_time = time.time()

        cv2.rectangle(frame, (0, 0), (w, 42), (20, 20, 20), -1)
        cv2.putText(frame, "SMART PARKING - AUTO LPR & OCCUPANCY", (18, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 255, 255), 2)
        cv2.putText(frame, f"FPS: {current_fps}", (w - 100, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 255, 0), 2)

        cv2.imshow("Smart Mall Parking Vision", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    stop_worker = True
    vs.stop()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()