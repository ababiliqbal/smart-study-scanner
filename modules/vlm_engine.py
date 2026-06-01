import os
import re
import json
import time
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError

# --- 1. INISIALISASI KEAMANAN & KONEKSI ---
load_dotenv()
HF_API_TOKEN = os.getenv("HUGGINGFACE_API_KEY")

if not HF_API_TOKEN:
    raise ValueError("KRITIS: HUGGINGFACE_API_KEY tidak ditemukan di file .env.")

client = InferenceClient(api_key=HF_API_TOKEN)
# Menggunakan VLM tingkat atas dari Qwen
MODEL_ID1 = "Qwen/Qwen3-Coder-Next:featherless-ai" 
MODEL_ID2 = "Qwen/Qwen3.5-9B:together" 

# --- 2. FASE MAP: EKSTRAKSI VISUAL (MODEL_ID2: Qwen VLM) ---
def extract_text_map(base64_image: str) -> str:
    map_prompt = """Anda adalah mesin ekstraksi dokumen akademik presisi tinggi.
    Tugas Anda adalah membaca gambar ini dan memindahkan seluruh teks, rumus, atau konsep ke dalam bentuk digital.
    
    ATURAN MUTLAK:
    1. ZERO-SUMMARIZATION: JANGAN merangkum. Ekstrak data mentahnya secara utuh dan seakurat mungkin, pertahankan hierarki aslinya (judul, subjudul, poin-poin).
    2. ANTI-HALUSINASI: DILARANG menambahkan pengetahuan dari luar gambar.
    3. PENOLAKAN NOISE: Jika gambar ini BUKAN dokumen, catatan, atau slide presentasi akademik (misal: hanya foto wajah, pemandangan, atau benda acak), Anda WAJIB mengembalikan HANYA string ini persis: "NO_TEXT_FOUND"."""

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                {"type": "text", "text": map_prompt}
            ]
        }
    ]

    try:
        completion = client.chat.completions.create(
            model=MODEL_ID2, # Menggunakan Qwen VLM
            messages=messages,
            max_tokens=1500, # Dinaikkan agar teks tidak terpotong jika satu halaman penuh tulisan
            temperature=0.0  # Suhu 0 mutlak untuk ekstraksi faktual tanpa kreativitas
        )
        result = completion.choices[0].message.content.strip()
        
        if "NO_TEXT_FOUND" in result or not result:
            return "" 
            
        return result
    except Exception as e:
        return f"[ERROR_EKSTRAKSI: {str(e)}]"

# --- 3. FASE REDUCE: SINTESIS & FORMATTING (MODEL_ID1: Gemma LLM) ---
def synthesize_json_reduce(combined_text: str) -> dict:
    SAFE_LIMIT = 20000 
    if len(combined_text) > SAFE_LIMIT:
        combined_text = combined_text[:SAFE_LIMIT] + "... (Teks dipotong demi stabilitas AI)"

    # PROMPT ENTERPRISE UNTUK ADAPTIVE FORMATTING
    system_prompt = """Anda adalah AI Instructional Designer dan Data Synthesizer tingkat lanjut. 
    Anda akan menerima gabungan teks mentah dari beberapa halaman dokumen (ditandai dengan pembatas --- HALAMAN X ---).
    
    KONTEKS & OUTPUT:
    Output Anda akan dikonsumsi langsung secara terprogram. Kepatuhan skema JSON adalah prioritas mutlak.

    ATURAN MUTLAK (SINTESIS ADAPTIF & FORMATTING):
    1. RINGKASAN DINAMIS: 'ringkasan' WAJIB disintesis menggunakan format Markdown yang PALING COCOK dengan konteks materi. 
       - Gunakan Tabel Markdown jika materi berupa perbandingan.
       - Gunakan Daftar Berangka (1, 2, 3) jika materi berupa proses/kronologi.
       - Gunakan kombinasi Heading (###) dan Bullet points untuk konsep umum.
    2. KUANTITAS WAJIB: Hasilkan 5 hingga 7 soal kuis komprehensif dan MAKSIMAL 10 flashcard.
    3. ZERO-HALLUCINATION: Seluruh materi WAJIB 100% bersumber dari teks input.
    4. STRICT OUTPUT: HANYA respons dengan JSON mentah. DILARANG menggunakan markdown code block (```json) di luar struktur JSON.

    SKEMA JSON YANG DIWAJIBKAN:
    {
        "ringkasan": "Tuliskan seluruh sintesis materi Anda di sini dalam bentuk SATU string panjang berformat Markdown. Gunakan \\n untuk garis baru (newline) dan sintaks tabel Markdown yang valid jika diperlukan.",
        "flashcards": [
            {"istilah": "Istilah Krusial 1", "definisi": "Definisi padat"}
        ],
        "kuis": [
            {
                "pertanyaan": "Pertanyaan evaluasi analitis?",
                "opsi": ["Jawaban Benar", "Pengecoh A", "Pengecoh B", "Pengecoh C"],
                "jawaban_benar": "Jawaban Benar",
                "penjelasan": "Alasan detail."
            }
        ]
    }"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Lakukan sintesis holistik pada teks dokumen multi-halaman berikut:\n\n{combined_text}"}
    ]

    try:
        completion = client.chat.completions.create(
            model=MODEL_ID1, # Menggunakan Gemma-3 untuk logika analitis teks
            messages=messages,
            max_tokens=3500, # Kuis 5-7 soal dan 10 flashcard butuh jumlah token yang sangat besar
            temperature=0.15 # Sedikit diberikan suhu kreativitas agar bisa mencari "benang merah"
        )
        
        result_text = completion.choices[0].message.content
        
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        clean_json = json_match.group(0) if json_match else result_text
        parsed_data = json.loads(clean_json)
        
        if "error" in parsed_data:
            return {"status": "error", "message": parsed_data["error"], "data": None}
            
        return {"status": "success", "message": "Sintesis Map-Reduce berhasil.", "data": parsed_data}

    except json.JSONDecodeError:
        return {"status": "error", "message": "Gagal merakit JSON karena format AI terpotong. Coba kurangi jumlah gambar.", "data": None}
    except Exception as e:
        return {"status": "error", "message": f"Gangguan Sintesis Gemma: {str(e)}", "data": None}
    
# --- 4. ORKESTRATOR (FUNGSI UTAMA YANG DIPANGGIL app.py) ---
def run_map_reduce_pipeline(base64_images_list: list) -> dict:
    extracted_texts = []
    
    # 1. JALANKAN FASE MAP (Iterasi Gambar)
    for index, b64_img in enumerate(base64_images_list):
        try:
            teks_halaman = extract_text_map(b64_img)
            
            # Jika bukan string kosong (Lolos Skenario #3) dan bukan error, simpan.
            if teks_halaman and "[ERROR_EKSTRAKSI" not in teks_halaman:
                extracted_texts.append(f"--- HALAMAN {index + 1} ---\n{teks_halaman}\n")
                
            # Mitigasi Skenario #1: Jeda Anti-Spam Server (Throttling)
            # Kita memaksa AI bernapas 2 detik agar API Hugging Face tidak memblokir IP kita.
            time.sleep(2)
            
        except HfHubHTTPError as e:
            # MITIGASI RATE LIMIT (429) & TIMEOUT EKSKLUSIF
            if "429" in str(e):
                print(f"Peringatan: Rate limit tercapai pada gambar ke-{index+1}. Mengabaikan gambar ini.")
                time.sleep(5) # Jeda lebih lama untuk mendinginkan server
                continue # Lanjutkan ke gambar berikutnya alih-alih me-crash-kan seluruh sesi
            else:
                continue

    # 2. VALIDASI PASCA-MAP
    if not extracted_texts:
        return {"status": "error", "message": "Tidak ada teks valid yang berhasil diekstrak dari seluruh gambar.", "data": None}
        
    # 3. JALANKAN FASE REDUCE
    gabungan_teks_utuh = "\n".join(extracted_texts)
    hasil_akhir = synthesize_json_reduce(gabungan_teks_utuh)
    
    return hasil_akhir