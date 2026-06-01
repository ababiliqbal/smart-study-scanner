import io
import csv
from PIL import Image
import time 
import streamlit as st
from modules.vision_utils import compress_image, image_to_base64
from modules.vlm_engine import run_map_reduce_pipeline

# --- 1. KONFIGURASI DASAR UI MOBILE ---
st.set_page_config(
    page_title="Smart Study Scanner",
    page_icon="📱",
    layout="centered"
)

# --- HELPER FUNCTION: IN-MEMORY CSV GENERATOR ---
def generate_csv_from_flashcards(flashcards_data: list) -> bytes:
    # Membuat buffer memori teks
    output = io.StringIO()
    
    # Konfigurasi penulis CSV (mengamankan koma di dalam teks definisi)
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    
    # Menulis baris Header (Standar format Anki/Quizlet)
    writer.writerow(['Istilah', 'Definisi'])
    
    # Menulis isi data
    for card in flashcards_data:
        istilah = card.get('istilah', '')
        definisi = card.get('definisi', '')
        writer.writerow([istilah, definisi])
        
    # Mengambil nilai string dari memori dan mengubahnya menjadi format bita (bytes) utf-8
    return output.getvalue().encode('utf-8')


# --- 2. INISIALISASI BRANKAS MEMORI (SESSION STATE) ---
if "uploaded_image" not in st.session_state:
    st.session_state.uploaded_images = []                
if "processed_data" not in st.session_state:
    st.session_state.processed_data = None  
if "quiz_submitted" not in st.session_state:
    st.session_state.quiz_submitted = False 
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}      

# --- 3. KONSTANTA KEAMANAN SISTEM ---
MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_TYPES = ["jpg", "jpeg", "png"]

# --- 4. HEADER ANTARMUKA ---
st.title("Smart Study Scanner 📱")
st.markdown("Unggah foto catatanmu, dan biarkan sistem merangkum poin pentingnya.")
st.write("---")

# --- 5. LOGIKA VALIDASI (ERROR HANDLING) ---
def validate_and_save_images(input_data):
    if input_data:
        # 1. NORMALISASI TIPE DATA
        if not isinstance(input_data, list):
            files = [input_data]
        else:
            files = input_data
            
        # 2. MITIGASI SKENARIO EKSTRIM #2 (Batas Token / Amnesia AI)
        if len(files) > 5:
            st.error("🛑 Akses Ditolak: Maksimal 5 gambar dalam satu sesi untuk menjaga kestabilan ingatan AI.")
            st.session_state.uploaded_images = []
            return False
            
        # 3. MITIGASI SKENARIO EKSTRIM #1 (Batas Memori / OOM)
        total_size_bytes = sum(f.size for f in files)
        total_size_mb = total_size_bytes / (1024 * 1024)
        MAX_TOTAL_SIZE_MB = 20 # Batas aman yang baru
        
        if total_size_mb > MAX_TOTAL_SIZE_MB:
            st.error(f"🛑 Akses Ditolak: Total ukuran {total_size_mb:.2f} MB. Maksimal akumulasi unggahan adalah {MAX_TOTAL_SIZE_MB} MB.")
            st.session_state.uploaded_images = []
            return False
            
        # 4. SKENARIO BAIK (Lolos Validasi)
        st.success(f"✅ {len(files)} Gambar lolos validasi ukuran dan format!")
        
        # Kunci gambar di dalam brankas memori sebagai LIST
        st.session_state.uploaded_images = files
        return True
        
    return False

# --- 6. INGESTION (PEMILIHAN METODE INPUT) ---
st.write("### Langkah 1: Unggah Catatan")

# Memberikan edukasi UX kepada pengguna HP bahwa mereka tetap bisa memotret langsung
st.info("💡 **Tips Pengguna HP:** Saat menekan tombol 'Browse files' di bawah, Anda dapat memilih opsi **'Kamera'** dari sistem HP Anda untuk langsung memotret catatan dengan hasil yang jauh lebih tajam.")

# Kita hanya menggunakan satu pintu masuk utama
uploaded_files = st.file_uploader(
    "Pilih foto dari memori perangkat atau potret langsung (Maks. 5 Halaman)", 
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

if uploaded_files:
    validate_and_save_images(uploaded_files)

# --- 7. PRESENTASI HASIL INPUT & TOMBOL LANJUTAN ---
if st.session_state.uploaded_images:
    st.write("---")
    st.write("### Pratinjau Catatan")
    st.success(f"Terdapat {len(st.session_state.uploaded_images)} halaman catatan di memori.")
    
    # Menggunakan expander agar UI tidak penuh oleh gambar-gambar besar
    with st.expander("📸 Lihat Pratinjau Dokumen", expanded=False):
        # Melakukan perulangan untuk menggambar setiap foto di dalam List
        for idx, img in enumerate(st.session_state.uploaded_images):
            st.image(img, caption=f"Halaman {idx + 1}", use_container_width=True)
    
    # Ketika tombol ini diklik oleh pengguna
    if st.button("Proses Catatan", type="primary", use_container_width=True):
            
            if not st.session_state.uploaded_images:
                st.warning("⚠️ Tidak ada gambar di memori. Silakan unggah catatan terlebih dahulu.")
            else:
                # --- UI ASINKRON (Mitigasi Skenario #4) ---
                # Membuat elemen kosong (placeholder) yang bisa diubah teksnya secara dinamis
                status_text = st.empty()
                progress_bar = st.progress(0)
                
                try:
                    daftar_base64 = []
                    total_gambar = len(st.session_state.uploaded_images)
                    
                    status_text.info("Mempersiapkan ruang kerja memori...")
                    
                    # --- FASE 1: PRA-PEMROSESAN LOKAL (ITERASI) ---
                    for i, file_gambar in enumerate(st.session_state.uploaded_images):
                        
                        # Mengubah teks indikator agar UI terasa 'hidup'
                        status_text.info(f"⚙️ Memampatkan dan mengenkode gambar {i+1} dari {total_gambar}...")
                        
                        # Transformasi Tipe Data
                        if isinstance(file_gambar, Image.Image):
                            img_pil = file_gambar
                        else:
                            img_pil = Image.open(file_gambar)
                            
                        # Kompresi & Encoding
                        gambar_kompresi = compress_image(img_pil)
                        base64_str = image_to_base64(gambar_kompresi)
                        
                        daftar_base64.append(base64_str)
                        
                        # Update Progress Bar (Kita alokasikan 30% perjalanan untuk fase lokal ini)
                        persentase = int(((i + 1) / total_gambar) * 30)
                        progress_bar.progress(persentase)
                        
                    # --- PERSIAPAN MENUJU FASE MAP-REDUCE ---
                    status_text.warning("🚀 Mengirim data ke otak AI. Proses sintesis Map-Reduce sedang berlangsung (Bisa memakan waktu 30-60 detik)...")
                    
                    # 3. EKSEKUSI ORKESTRATOR (Mengirim daftar Base64 ke vlm_engine.py)
                    response = run_map_reduce_pipeline(daftar_base64)
                    
                    # 4. PENYELESAIAN VISUAL
                    # Mengisi progress bar menjadi 100% karena proses API telah selesai
                    progress_bar.progress(100)
                    
                    # 5. PENANGANAN RESPON
                    if response["status"] == "success":
                        # Menyimpan hasil akhir (1 JSON Terpadu) ke memori
                        st.session_state.processed_data = response["data"]
                        st.session_state.quiz_submitted = False
                        st.session_state.user_answers = {}
                        
                        status_text.success("✅ Pemrosesan Multi-Halaman berhasil! Merender antarmuka...")
                        time.sleep(1.5) # Memberi jeda agar pengguna sempat membaca pesan sukses
                        st.rerun() 
                    else:
                        st.error(f"🛑 Gagal memproses AI: {response['message']}")
                        status_text.empty()
                        progress_bar.empty()
                            
                except Exception as e:
                    st.error(f"⚙️ Terjadi kesalahan sistem internal: {str(e)}")
                    progress_bar.empty() # Sembunyikan progress bar jika error


if st.session_state.processed_data:
    data = st.session_state.processed_data
    
    st.markdown("---")
    st.subheader("🎯 Hasil Analisis Cerdas")
    
    # Membuat 3 Tab navigasi
    tab_ringkasan, tab_kuis, tab_flashcard = st.tabs([
        "📄 Ringkasan Materi", 
        "🧠 Uji Pemahaman (Kuis)", 
        "🗂️ Flashcards"
    ])
    
    # TAB 1: RINGKASAN MATERI
    with tab_ringkasan:
        st.subheader("📝 Intisari Catatan")
        
        # Memberikan feedback visual bahwa ini adalah hasil VLM
        st.caption("✨ *Dianalisis secara visual menggunakan Vision-Language Model.*")
        st.write("---")
        
        # Mengambil string markdown dari JSON (default ke string kosong jika tidak ada)
        ringkasan_markdown = data.get("ringkasan", "Tidak ada ringkasan yang tersedia.")
        
        # Merender string tersebut sebagai elemen HTML/Markdown kaya
        st.markdown(ringkasan_markdown)
            
    
    # TAB 2: KUIS & AUTOMATED GRADING
    with tab_kuis:
        kuis_data = data.get("kuis", [])
        
        if not kuis_data:
            st.info("Kuis tidak dapat dihasilkan dari catatan ini.")
        else:
            # Gunakan Form agar aplikasi tidak me-refresh saat memilih jawaban
            with st.form("quiz_form"):
                user_selections = {}
                
                for idx, soal in enumerate(kuis_data):
                    st.markdown(f"**Soal {idx + 1}: {soal['pertanyaan']}**")
                    # Radio button dengan key unik untuk setiap pertanyaan
                    user_selections[idx] = st.radio(
                        "Pilih jawaban:", 
                        soal['opsi'], 
                        key=f"q_{idx}", 
                        label_visibility="collapsed"
                    )
                    st.write("") # Spasi antar soal
                
                # Tombol kumpul di dalam form
                submitted = st.form_submit_button("Kumpulkan Jawaban", type="primary")
                
                if submitted:
                    # Simpan status dan jawaban ke memori
                    st.session_state.quiz_submitted = True
                    st.session_state.user_answers = user_selections
                    st.rerun() # Refresh untuk memunculkan kunci jawaban
            
            # --- LOGIKA PENILAIAN (GRADING LOGIC) ---
            if st.session_state.quiz_submitted:
                st.markdown("### 📊 Hasil Evaluasi")
                skor_benar = 0
                
                for idx, soal in enumerate(kuis_data):
                    jawaban_user = st.session_state.user_answers.get(idx)
                    kunci_jawaban = soal['jawaban_benar']
                    
                    if jawaban_user == kunci_jawaban:
                        skor_benar += 1
                        st.success(f"**Soal {idx + 1}**: Benar! 🎉 (Jawaban: {kunci_jawaban})")
                    else:
                        st.error(f"**Soal {idx + 1}**: Salah. Jawabanmu: {jawaban_user} | Kunci: {kunci_jawaban}")
                    
                    # Tampilkan penjelasan AI dengan gaya kutipan (blockquote)
                    st.info(f"💡 **Penjelasan:** {soal['penjelasan']}")
                
                # Kalkulasi dan Tampilan Metrik Nilai
                total_soal = len(kuis_data)
                nilai_akhir = int((skor_benar / total_soal) * 100)
                
                col1, col2 = st.columns(2)
                col1.metric("Skor Anda", f"{nilai_akhir} / 100")
                col2.metric("Jawaban Benar", f"{skor_benar} dari {total_soal}")

    # TAB 3: FLASHCARDS & EKSPOR
    with tab_flashcard:
        st.subheader("🗂️ Kartu Hafalan (Active Recall)")
        
        # Ekstraksi data secara aman
        flashcards_data = data.get("flashcards", [])
        
        # Penanganan Kondisi Ekstrim: Jika AI gagal membuat flashcard
        if not flashcards_data:
            st.info("Tidak ada istilah penting yang ditemukan untuk dibuatkan flashcard pada catatan ini.")
        else:
            st.write("Klik pada istilah di bawah ini untuk melihat definisinya secara interaktif.")
            
            # --- RENDER UI FLASHCARD ---
            for idx, card in enumerate(flashcards_data):
                istilah = card.get("istilah", f"Istilah {idx+1}")
                definisi = card.get("definisi", "Definisi tidak tersedia.")
                
                # Menggunakan expander sebagai efek "balik kartu"
                with st.expander(f"🔖 **{istilah}**"):
                    st.write(definisi)
            
            st.write("---")
            
            # --- FITUR EKSPOR (PORTABILITAS DATA) ---
            st.subheader("💾 Ekspor ke Aplikasi Belajar")
            st.write("Unduh data flashcard ini dalam format `.csv` untuk diimpor ke aplikasi seperti **Anki** atau **Quizlet**.")
            
            # Merakit file CSV di dalam memori
            csv_bytes = generate_csv_from_flashcards(flashcards_data)
            
            # Tombol Unduh Bawaan Streamlit
            st.download_button(
                label="📥 Unduh Flashcards (.csv)",
                data=csv_bytes,
                file_name="smart_study_flashcards.csv",
                mime="text/csv",
                type="primary",
                use_container_width=True
            )

    # --- SIKLUS UX BERULANG (RESET) ---
    st.write("---")
    if st.button("🔄 Pindai Catatan Baru", type="secondary", use_container_width=True):
        st.session_state.uploaded_images = []  # Kembalikan ke List kosong
        st.session_state.processed_data = None
        st.session_state.quiz_submitted = False
        st.session_state.user_answers = {}
        st.rerun()