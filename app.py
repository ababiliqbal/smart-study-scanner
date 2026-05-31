import streamlit as st
from modules.ocr_engine import extract_text_from_image
from modules.nlp_engine import summarize_text

# --- 1. KONFIGURASI DASAR UI MOBILE ---
st.set_page_config(
    page_title="Smart Study Scanner",
    page_icon="📱",
    layout="centered"
)

# --- 2. INISIALISASI BRANKAS MEMORI (SESSION STATE) ---
if 'uploaded_image' not in st.session_state:
    st.session_state.uploaded_image = None

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

# --- 6. FASE 1: INGESTION (PEMILIHAN METODE INPUT) ---
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
    if st.button("Ekstrak Teks & Buat Ringkasan", type="primary", use_container_width=True):
        
        # Tampilkan efek animasi loading professional
        with st.spinner("⏳ Menghubungi mesin OCR... Sedang membaca teks pada gambar..."):
            
            # Panggil fungsi dari ruang mesin ocr_engine.py
            raw_text_result = extract_text_from_image(st.session_state.uploaded_image)
            
        # Tampilkan hasil ekstraksi teks mentah di layar
        st.write("### 📝 Hasil Ekstraksi Teks Mentah:")
        st.text_area(label="Teks Terdeteksi", value=raw_text_result, height=250)
        
        if not raw_text_result.startswith("Sistem tidak mendeteksi") and not raw_text_result.startswith("Terjadi kesalahan"):

         with st.spinner("🧠 Mengirim teks ke AI untuk diringkas..."):
             # Kirim teks mentah dari OCR ke mesin NLP
             summary_result = summarize_text(raw_text_result)

         st.write("### 🎯 Ringkasan Cerdas:")
         st.success(summary_result)