import pytesseract
from PIL import Image
import io

# --- KONFIGURASI PATH TESSERACT ---
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text_from_image(image_bytes) -> str:
    try:
        # --- Kondisi Baik: Mencoba membaca gambar ---
        
        # 1. Konversi objek byte dari memori Streamlit menjadi format Image yang dikenali Pillow
        image = Image.open(image_bytes)
        
        # 2. Eksekusi OCR membaca teks dari gambar
        # Parameter lang='ind+eng' memastikan AI bisa membaca campuran bahasa Indonesia & Inggris
        extracted_text = pytesseract.image_to_string(image, lang='ind+eng')
        
        # 3. Validasi teks kosong (Jika gambar buram/tidak ada teks)
        if not extracted_text.strip():
            return "Sistem tidak mendeteksi adanya teks pada gambar ini. Pastikan foto fokus dan pencahayaan cukup."
            
        return extracted_text

    except Exception as e:
        # --- Kondisi Buruk: Terjadi kerusakan format atau mesin OCR gagal ---
        return f"Terjadi kesalahan pada mesin pembaca teks: {str(e)}"