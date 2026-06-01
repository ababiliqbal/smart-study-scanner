import os
import re
import json
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
MODEL_ID = "google/gemma-3-12b-it-qat-q4_0-unquantized:featherless-ai" 

# --- 2. KONTRAK FUNGSI UTAMA ---
def analyze_document(base64_image: str) -> dict:
    
    # --- 3. SYSTEM PROMPT (Mitigasi Skenario #3: Halusinasi) ---
    system_prompt = """
    Anda adalah AI Instructional Designer dan Vision-Language Engine tingkat lanjut. Tugas utama Anda adalah memproses gambar dokumen akademik, mengekstrak informasi faktual, dan secara otomatis merancang instrumen pembelajaran (ringkasan, flashcard, dan kuis) ke dalam format JSON terstruktur.
    KONTEKS:
    Output Anda akan dikonsumsi langsung secara terprogram oleh aplikasi 'Smart Study Scanner'. Kepatuhan terhadap skema JSON dan akurasi ekstraksi (tanpa halusinasi) adalah prioritas mutlak agar sistem tidak mengalami crash.

    LANGKAH KERJA INTERNAL (Terapkan sebelum menghasilkan output):
    1. Pindai dan analisis gambar yang diberikan.
    2. Identifikasi apakah gambar memuat teks edukasi/akademik. Jika tidak (misal: foto pemandangan, objek acak, atau teks tidak terbaca), Anda harus langsung mengembalikan JSON error.
    3. Jika teks valid, ekstrak konsep utama tanpa menambahkan opini atau pengetahuan eksternal.
    4. Sintesis data menjadi poin ringkasan, pasangan istilah-definisi (flashcard), dan kuis dengan pengecoh (distractor) yang masuk akal.

    ATURAN MUTLAK (MITIGASI HALUSINASI & FORMATTING):
    1. KUANTITAS WAJIB: Anda WAJIB menghasilkan MINIMAL 3 soal kuis yang berbeda dan 3-5 flashcard. Jika teks terlalu pendek, pecah satu informasi menjadi beberapa sudut pandang pertanyaan agar kuota 3 soal kuis TETAP TERPENUHI.
    2. ZERO-HALLUCINATION: Anda DILARANG KERAS menggunakan data latih atau pengetahuan dari luar. Seluruh isi ringkasan, flashcard, dan kuis WAJIB 100% bersumber dari teks yang terdeteksi pada gambar.
    3. STRICT OUTPUT: Anda HANYA diizinkan merespons dengan struktur JSON mentah yang valid. DILARANG menyertakan teks pengantar, penutup, pemikiran (thought process), atau bahkan *markdown code blocks* (seperti ```json).
    4. ERROR HANDLING: Jika gambar TIDAK berisi dokumen/teks edukasi, Anda WAJIB mengembalikan JSON ini secara persis:
    {"error": "Teks edukasi tidak ditemukan pada gambar."}

    SKEMA JSON YANG DIWAJIBKAN:
    {
        "ringkasan": [
            "Poin ringkasan 1 yang padat dan komprehensif.",
            "Poin ringkasan 2 yang berfokus pada konsep inti."
        ],
        "flashcards": [
            {
                "istilah": "Kata kunci spesifik dari teks",
                "definisi": "Definisi yang diekstrak langsung dari teks"
            }
        ],
        "kuis": [
            {
                "pertanyaan": "Pertanyaan evaluasi 1 yang menguji pemahaman dari teks",
                "opsi": [
                    "Jawaban Benar",
                    "Pengecoh Logis A",
                    "Pengecoh Logis B",
                    "Pengecoh Logis C"
                ],
                "jawaban_benar": "Jawaban Benar (harus sama persis dengan salah satu string di dalam array opsi)",
                "penjelasan": "Alasan mengapa jawaban benar berdasarkan informasi spesifik pada gambar."
            },
            {
                "pertanyaan": "Pertanyaan evaluasi 2 yang menguji pemahaman dari teks",
                "opsi": [
                    "Jawaban Benar",
                    "Pengecoh Logis A",
                    "Pengecoh Logis B",
                    "Pengecoh Logis C"
                ],
                "jawaban_benar": "Jawaban Benar (harus sama persis dengan salah satu string di dalam array opsi)",
                "penjelasan": "Alasan mengapa jawaban benar berdasarkan informasi spesifik pada gambar."
            },
            {
                "pertanyaan": "Pertanyaan evaluasi 3 yang menguji pemahaman dari teks",
                "opsi": [
                    "Jawaban Benar",
                    "Pengecoh Logis A",
                    "Pengecoh Logis B",
                    "Pengecoh Logis C"
                ],
                "jawaban_benar": "Jawaban Benar (harus sama persis dengan salah satu string di dalam array opsi)",
                "penjelasan": "Alasan mengapa jawaban benar berdasarkan informasi spesifik pada gambar."
            }
        ]
    }
    
    """

    # --- 4. MULTIMODAL PAYLOAD ARCHITECTURE ---
    # Memformat pesan agar AI tahu ada gambar dan instruksi yang dikirim bersamaan
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                },
                {
                    "type": "text",
                    "text": "Analisis gambar ini dengan cermat dan kembalikan output dalam format JSON sesuai aturan sistem."
                }
            ]
        }
    ]

    try:
        # --- 5. EKSEKUSI API & MITIGASI TOKEN ---
        # Di dalam fungsi analyze_document, blok try:
        
        # Daftar model yang akan dicoba berurutan jika salah satu mati/tidak didukung
        model_fallbacks = [
            "google/gemma-3-12b-it-qat-q4_0-unquantized:featherless-ai",
            "Qwen/Qwen3.5-9B:together",
            "Qwen/Qwen3-VL-8B-Instruct:novita",
        ]
        
        completion = None
        last_error = ""

        # Loop percobaan ke berbagai model
        for model in model_fallbacks:
            try:
                completion = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=2500,  
                    temperature=0.1
                )
                break # Jika berhasil, keluar dari loop
            except Exception as e:
                last_error = str(e)
                print(f"Model {model} gagal: {last_error}. Mencoba model berikutnya...")
                continue # Lanjut ke model berikutnya di daftar

        if not completion:
            return {"status": "error", "message": f"Seluruh server AI sedang sibuk atau tidak mendukung model VLM saat ini. Error terakhir: {last_error}", "data": None}
        
        result_text = completion.choices[0].message.content
        
        if not result_text or result_text.strip() == "":
             return {"status": "error", "message": "Silent Failure: AI mengembalikan data kosong.", "data": None}

        # --- 6. JSON SANITIZATION (Pertahanan Lapis 2) ---
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        clean_json_string = json_match.group(0) if json_match else result_text

        # --- 7. PARSING & VALIDASI STRUKTURAL ---
        parsed_data = json.loads(clean_json_string)
        
        # Validasi Skenario #3 (Deteksi Gambar Kosong/Bukan Dokumen dari AI)
        if "error" in parsed_data:
            return {"status": "error", "message": parsed_data["error"], "data": None}
            
        # Validasi Kunci JSON yang Wajib Ada
        required_keys = ["ringkasan", "flashcards", "kuis"]
        if all(key in parsed_data for key in required_keys):
            return {"status": "success", "message": "Pemrosesan VLM berhasil.", "data": parsed_data}
        else:
            return {"status": "error", "message": "Struktur JSON tidak lengkap.", "data": None}

    # --- 8. PENANGANAN KONDISI EKSTRIM (ERROR HANDLING) ---
    except json.JSONDecodeError:
        # Skenario #4: Menangkap error jika teks JSON terpotong
        return {"status": "error", "message": "Sistem gagal merakit JSON (kemungkinan karena teks terlalu panjang). Coba gunakan gambar dengan teks yang lebih sedikit.", "data": None}
        
    except HfHubHTTPError as e:
        # Skenario #2: Menangkap error spesifik dari Hugging Face (Rate Limit / Cold Start)
        error_msg = str(e)
        if "503" in error_msg:
             return {"status": "error", "message": "Server AI sedang pemanasan (Cold Start). Mesin VLM butuh waktu untuk bangun. Silakan tunggu 30 detik dan coba lagi.", "data": None}
        elif "429" in error_msg:
             return {"status": "error", "message": "Terlalu banyak permintaan (Rate Limit). Anda telah mencapai batas kuota server publik. Silakan coba beberapa saat lagi.", "data": None}
        else:
             return {"status": "error", "message": f"Gangguan server AI: {error_msg}", "data": None}
             
    except Exception as e:
        return {"status": "error", "message": f"Terjadi kesalahan tidak terduga: {str(e)}", "data": None}