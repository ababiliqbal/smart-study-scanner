import io
import base64
from PIL import Image

def compress_image(img: Image.Image, max_dimension: int = 1500) -> Image.Image:
    # 1. Penanganan Format Ekstrim: Transparansi (Alpha Channel)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
        
    width, height = img.size
    
    # 2. Deteksi Gambar Raksasa (Resolusi 4K/8K)
    if width > max_dimension or height > max_dimension:
        # Kalkulasi rasio aspek dinamis agar gambar tidak "gepeng"
        if width > height:
            new_width = max_dimension
            new_height = int((max_dimension / width) * height)
        else:
            new_height = max_dimension
            new_width = int((max_dimension / height) * width)
            
        # 3. Resampling Kelas Atas
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
    return img

def image_to_base64(img: Image.Image, quality_level: int = 85) -> str:
    # Validasi Ekstrim: Mencegah gambar kosong/korup (ukuran 1x1 pixel)
    if img.size[0] < 10 or img.size[1] < 10:
        raise ValueError("Resolusi gambar terlalu kecil, rusak, atau tidak valid.")
        
    # Membuka buffer/laci di dalam RAM (Virtual Memory)
    buffered = io.BytesIO()
    
    # 4. Kompresi Lanjutan (Payload Optimization)
    img.save(buffered, format="JPEG", optimize=True, quality=quality_level)
    
    # Mengekstrak urutan byte mentah dari buffer
    img_bytes = buffered.getvalue()
    
    # 5. Encoding Base64 & Decoding UTF-8
    base64_str = base64.b64encode(img_bytes).decode("utf-8")
    
    return base64_str