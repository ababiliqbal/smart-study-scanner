import os
import re
import json
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
        return {
            "status": "error",
            "message": "Catatan terlalu pendek untuk diringkas (kurang dari 10 kata).",
            "data": None
        }
    # Sanitasi teks OCR
    clean_text = re.sub(r'\[.*?\]', '', raw_text)  
    clean_text = re.sub(r'[#&_]+', '', clean_text) 
    safe_text = clean_text[:4000].strip()

    system_prompt = """
    Anda adalah mesin pemroses teks akademik otomatis untuk sistem Smart-Study-Scanner. 
    Tugas utama Anda adalah mengekstrak informasi dan membuat alat uji pemahaman berdasarkan teks yang diberikan.

    [ATURAN OUTPUT MUTLAK]
    1. Anda WAJIB merespons HANYA dalam format JSON mentah (Raw JSON). 
    2. DILARANG menambahkan teks pengantar, penutup, atau penjelasan di luar objek JSON.
    3. DILARANG menggunakan pembungkus markdown seperti ```json atau ```. Output harus langsung dimulai dengan '{' dan diakhiri dengan '}'.
    4. Hindari penggunaan tanda kutip ganda (") di dalam teks jawaban, ringkasan, atau penjelasan agar tidak merusak validitas sintaks JSON. Gunakan tanda kutip tunggal (') jika sangat diperlukan.

    [ATURAN KONTEN & BATASAN]
    1. Gunakan HANYA informasi yang ada pada teks yang disediakan. DILARANG memakai pengetahuan luar atau berasumsi.
    2. Buat MAKSIMAL 5 flashcard dan MAKSIMAL 3 soal kuis. Jika teks pendek, sesuaikan jumlahnya menjadi lebih sedikit. DILARANG mengarang informasi demi memenuhi kuota.
    3. Opsi pengecoh (distractor) pada kuis harus sangat masuk akal, mengecoh, kompetitif, dan relevan dengan konteks teks, bukan pilihan yang jelas-jelas salah.

    [STRUKTUR JSON YANG DIWAJIBKAN]
    {
        "ringkasan": [
            "Poin ringkasan padat gagasan utama.",
            "Poin ringkasan detail penting berikutnya."
        ],
        "flashcards": [
            {
            "istilah": "Istilah kunci dari teks",
            "definisi": "Definisi padat berdasarkan teks"
            }
        ],
        "kuis": [
            {
            "pertanyaan": "Pertanyaan evaluasi mendalam?",
            "opsi": [
                "Pilihan Benar",
                "Pengecoh Masuk Akal A",
                "Pengecoh Masuk Akal B",
                "Pengecoh Masuk Akal C"
            ],
            "jawaban_benar": "Pilihan Benar",
            "penjelasan": "Alasan singkat mengapa jawaban benar berdasarkan teks."
            }
        ]
    }
    """
    
    try:
        # Eksekusi ke API
        completion = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": safe_text}
            ],
            max_tokens=1500,  # Ditingkatkan drastis karena struktur JSON butuh banyak memori karakter
            temperature=0.2   # Suhu rendah agar AI tetap patuh pada format JSON
        )
        
        result_text = completion.choices[0].message.content
        
        # Validasi Silent Failure
        if not result_text or result_text.strip() == "":
             return {
                 "status": "error", 
                 "message": "Silent Failure: AI mengembalikan data kosong.", 
                 "data": None
             }

        # --- 4. JSON SANITIZATION (Pertahanan Ekstrim) ---
        # Jika AI bandel menyelipkan teks di luar kurung kurawal, kita potong paksa menggunakan Regex
        # re.DOTALL memastikan Regex mencari kurung kurawal melewati enter/baris baru
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        
        if json_match:
            clean_json_string = json_match.group(0)
        else:
            # Fallback jika Regex tidak menemukan struktur objek
            clean_json_string = result_text

        # --- 5. PARSING & STRUCTURAL VALIDATION ---
        # Mengubah string menjadi Dictionary Python (Titik paling rawan crash)
        parsed_data = json.loads(clean_json_string)
        
        # Validasi apakah kunci utamanya dikembalikan secara lengkap oleh AI
        required_keys = ["ringkasan", "flashcards", "kuis"]
        if all(key in parsed_data for key in required_keys):
            return {
                "status": "success",
                "message": "Pemrosesan JSON berhasil.",
                "data": parsed_data
            }
        else:
            return {
                "status": "error",
                "message": "Struktur JSON tidak lengkap (Kehilangan kunci ringkasan/flashcards/kuis).",
                "data": None
            }

    # --- 6. PENANGANAN ERROR JSON & JARINGAN ---
    except json.JSONDecodeError as e:
        # Jika AI mengembalikan struktur koma atau kutip yang salah (Malformed JSON)
        return {
            "status": "error",
            "message": "Gagal membaca format JSON dari AI. Model mungkin memotong hasil di tengah jalan.",
            "data": None
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Terjadi kesalahan sistem/jaringan: {str(e)}",
            "data": None
        }