import io
import csv
import streamlit as st
from modules.ocr_engine import extract_text_from_image
from modules.nlp_engine import summarize_text

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
    st.session_state.uploaded_image = None
if "raw_text" not in st.session_state:             
    st.session_state.raw_text = None                
if "processed_data" not in st.session_state:
    st.session_state.processed_data = None  # Menyimpan JSON utuh dari AI
if "quiz_submitted" not in st.session_state:
    st.session_state.quiz_submitted = False # Menandai apakah kuis sudah dikerjakan
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}      # Menyimpan jawaban kuis pengguna

# --- 3. KONSTANTA KEAMANAN SISTEM ---
MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_TYPES = ["jpg", "jpeg", "png"]

# --- 4. HEADER ANTARMUKA ---
st.title("Smart Study Scanner 📱")
st.markdown("Unggah foto catatanmu, dan biarkan sistem merangkum poin pentingnya.")
st.write("---")

# --- 5. LOGIKA VALIDASI (ERROR HANDLING) ---
def validate_and_save_image(image_file):
    if image_file is not None:
        # Pengecekan Kondisi Buruk: Ukuran file melebihi batas
        if image_file.size > MAX_FILE_SIZE_BYTES:
            st.error(f"❌ Akses Ditolak: Ukuran file {image_file.size / (1024*1024):.2f} MB. Maksimal {MAX_FILE_SIZE_MB} MB untuk menjaga stabilitas memori.")
            # Hapus dari memori jika file tidak valid
            st.session_state.uploaded_image = None 
            return False
        
        # Pengecekan Kondisi Baik: File valid
        else:
            st.success("✅ Gambar lolos validasi ukuran dan format!")
            # Kunci gambar di dalam brankas memori
            st.session_state.uploaded_image = image_file
            return True
    return False

# --- 6. INGESTION (PEMILIHAN METODE INPUT) ---
st.write("### Langkah 1: Pilih Sumber Catatan")

# Menggunakan Tabs (Tabulasi) adalah praktik UX terbaik untuk layar kecil/HP
tab_kamera, tab_galeri = st.tabs(["📸 Kamera", "📂 Galeri"])

# Skenario A: Input Kamera
with tab_kamera:
    st.info("Pastikan ruangan cukup terang agar teks mudah dibaca oleh AI.")
    camera_photo = st.camera_input("Ambil Foto Catatan")
    if camera_photo:
        validate_and_save_image(camera_photo)

# Skenario B: Input File dari Galeri
with tab_galeri:
    gallery_photo = st.file_uploader("Pilih foto dari memori perangkat", type=ALLOWED_TYPES)
    if gallery_photo:
         validate_and_save_image(gallery_photo)

# --- 7. PRESENTASI HASIL INPUT & TOMBOL LANJUTAN ---
if st.session_state.uploaded_image is not None:
    st.write("---")
    st.write("### Pratinjau Catatan")
    st.image(st.session_state.uploaded_image, caption="Catatan ini siap diproses", use_container_width=True)
    
    # Ketika tombol ini diklik oleh pengguna
    if st.button("Proses Catatan", type="primary", use_container_width=True):
            
            # --- PROTEKSI MEMORI: Cek apakah gambar benar-benar ada di brankas ---
            if st.session_state.uploaded_image is None:
                st.warning("⚠️ Tidak ada gambar di memori. Silakan unggah atau potret gambar terlebih dahulu.")
            else:
                with st.spinner("🧠 Membaca dan Menganalisis Catatan..."):
                    
                    # 1. Ekstrak OCR dengan mengambil gambar langsung dari session_state
                    gambar_aktif = st.session_state.uploaded_image
                    extracted_text = extract_text_from_image(gambar_aktif)
                    
                    if extracted_text.strip() == "":
                        st.error("Teks tidak terdeteksi. Pastikan gambar tidak terlalu buram.")
                    else:
                        # 2. Kirim ke NLP Engine
                        response = summarize_text(extracted_text)
                        
                        # 3. Validasi Respons Terstruktur (API-like)
                        if response["status"] == "success":
                        
                            # --- SIMPAN TEKS MENTAH DAN HASIL AI KE MEMORI ---
                            st.session_state.raw_text = extracted_text      
                            st.session_state.processed_data = response["data"]
                        
                            st.session_state.quiz_submitted = False
                            st.session_state.user_answers = {}
                            st.rerun()


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
    
    # TAB 1: RINGKASAN & TEKS ASLI
    with tab_ringkasan:
        st.subheader("📝 Intisari Catatan")
        
        # Mengambil data ringkasan (kini berupa Array/List)
        ringkasan_list = data.get("ringkasan", [])
        
        # Render bullet points secara dinamis
        if isinstance(ringkasan_list, list):
            for poin in ringkasan_list:
                st.markdown(f"- {poin}")
        else:
            # Fallback jika AI bandel dan tetap mengirim String
            st.write(ringkasan_list)
            
        st.write("---")
        
        # Mengembalikan Teks OCR Mentah dengan antarmuka Expander yang elegan
        with st.expander("🔍 Lihat Teks Asli (Hasil Pindaian OCR)"):
            st.info("Teks di bawah ini adalah hasil pembacaan mentah oleh mesin visi komputer. Gunakan untuk memverifikasi apakah ada huruf yang salah dipindai.")
            
            # Gunakan text_area agar teks panjang bisa di-scroll tanpa memakan ruang halaman
            st.text_area(
                "Teks Mentah", 
                value=st.session_state.raw_text, 
                height=250, 
                disabled=True, 
                label_visibility="collapsed"
            )
    
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
        st.session_state.uploaded_image = None
        st.session_state.raw_text = None            # <-- TAMBAHKAN BARIS INI
        st.session_state.processed_data = None
        st.session_state.quiz_submitted = False
        st.session_state.user_answers = {}
        st.rerun()