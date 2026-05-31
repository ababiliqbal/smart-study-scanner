import os
import re  # Library untuk manipulasi teks (Data Sanitization)
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

# --- 1. INISIALISASI KEAMANAN ---
load_dotenv()
HF_API_TOKEN = os.getenv("HUGGINGFACE_API_KEY")

if not HF_API_TOKEN:
    raise ValueError("KRITIS: HUGGINGFACE_API_KEY tidak ditemukan di file .env.")

client = InferenceClient(api_key=HF_API_TOKEN)

MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"

# --- 2. KONTRAK FUNGSI UTAMA ---
def summarize_text(raw_text: str) -> str:
    # Mitigasi teks terlalu pendek
    if len(raw_text.split()) < 10:
        return f"Catatan terlalu pendek untuk diringkas. Berikut teks aslinya:\n\n{raw_text}"
    
    # --- 3. DATA SANITIZATION (Pembersihan Teks OCR) ---
    # Menghapus karakter aneh (#, &, [, ]) yang memicu Silent Failure pada AI
    clean_text = re.sub(r'\[.*?\]', '', raw_text)  # Menghapus semua referensi dalam kurung siku
    clean_text = re.sub(r'[#&_]+', '', clean_text) # Menghapus karakter simbol menggantung
    
    # Batasi karakter
    safe_text = clean_text[:4000].strip()

    try:
        completion = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Anda adalah asisten akademik. Rangkum teks berikut ke dalam "
                        "poin-poin penting menggunakan bahasa Indonesia baku. "
                        "Jangan membuat percakapan pengantar, langsung berikan poin ringkasannya."
                    )
                },
                {
                    "role": "user",
                    "content": safe_text
                }
            ],
            max_tokens=500,   # Dinaikkan menjadi 500 agar AI leluasa menyusun poin
            temperature=0.2
        )
        
        # --- 4. EKSTRAKSI & VALIDASI SILENT FAILURE ---
        result_text = completion.choices[0].message.content
        
        # Pengecekan ketat: Jika AI merespons tapi isinya kosong
        if not result_text or result_text.strip() == "":
             return "Sistem AI berhasil dihubungi, namun mengembalikan teks kosong. Kemungkinan ada kalimat yang diblokir oleh filter keamanan AI."
             
        return result_text.strip()

    except Exception as e:
        return f"Gagal memproses data melalui API: {str(e)}"