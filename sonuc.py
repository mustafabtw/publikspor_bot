from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import os
import datetime

# --- RENKLER ---
DARK_BG = (10, 15, 30)
TEXT_WHITE = (255, 255, 255)
TEXT_GREY = (180, 180, 180)
ACCENT_ORANGE = (255, 140, 0)
ACCENT_BLUE = (0, 180, 255)

# --- YARDIMCI FONKSİYONLAR ---

def get_font(size, is_bold=False):
    try: return ImageFont.truetype("font.otf", size)
    except: return ImageFont.truetype("arialbd.ttf" if is_bold else "arial.ttf", size)

def tr_karakter_cevir(metin):
    """Dosya isimleri ve ekrandaki yazılar için standartlaştırma"""
    ceviri = str.maketrans("ŞşĞğÜüİıÖöÇç", "SsGgUuIiOoCc")
    temiz = metin.translate(ceviri).upper().strip()
    
    # Özel Düzeltmeler
    if "ISTANBUL BASAKSEHIR" in temiz: return "BASAKSEHIR"
    if "FATIH KARAGUMRUK" in temiz or "KARAGUMRUK" in temiz: return "KARAGUMRUK"
    if "CAYKUR RIZESPOR" in temiz: return "RIZESPOR"
    if "GAZIANTEP" in temiz and "FK" not in temiz: return "GAZIANTEP FK"
    if "ADANA DEMIRSPOR" in temiz: return "ADANA DEMIR"
    return temiz

def get_local_logo(takim_adi, size):
    temiz_ad = tr_karakter_cevir(takim_adi)
    olasi_isimler = [temiz_ad, temiz_ad.replace(" FK", ""), temiz_ad.replace(" SK", ""), temiz_ad.split(" ")[-1] if " " in temiz_ad else temiz_ad]
    
    for isim in olasi_isimler:
        yollar = [f"logos/{isim}.png", f"logos/{isim}.jpg"]
        for yol in yollar:
            if os.path.exists(yol):
                try:
                    img = Image.open(yol).convert("RGBA")
                    img.thumbnail((size, size), Image.Resampling.LANCZOS)
                    return img
                except: continue
    
    print(f"❌ LOGO YOK: {temiz_ad}")
    return None

def yerel_gorsel_ekle(ana_resim, dosya_adi, hedef_yukseklik, x, y):
    if not os.path.exists(dosya_adi): return x
    try:
        img_local = Image.open(dosya_adi).convert("RGBA")
        oran = hedef_yukseklik / img_local.height
        yeni_genislik = int(img_local.width * oran)
        img_resized = img_local.resize((yeni_genislik, hedef_yukseklik), Image.Resampling.LANCZOS)
        ana_resim.paste(img_resized, (x, y), img_resized)
        return x + yeni_genislik + 20
    except: return x

def hesapla_ortak_font(draw, text_list, max_width, start_size):
    """Tüm takımların belirtilen kutuya sığacağı ortak font büyüklüğünü bulur."""
    current_size = start_size
    while current_size > 10:
        font = get_font(current_size, True)
        hepsi_sigiyor = True
        for text in text_list:
            if draw.textlength(text, font=font) > max_width:
                hepsi_sigiyor = False
                break
        if hepsi_sigiyor: return font
        current_size -= 1
    return get_font(12, True)

def resim_indir(url, size):
    if not url: return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5)
        img = Image.open(BytesIO(r.content)).convert("RGBA")
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        return img
    except: return None

# =============================================================================
# 1. MAÇ SONUCU TASARIMI (EKSİKSİZ)
# =============================================================================
def mac_sonucu_gorseli_olustur(ev, dep, skor):
    print(f"🎨 MAÇ SONUCU Çiziliyor: {ev} vs {dep}...")
    W, H = 1080, 1080 
    img = Image.new('RGB', (W, H), color=DARK_BG)
    draw = ImageDraw.Draw(img)

    f_baslik = get_font(90, True)
    f_skor = get_font(200, True)
    f_takim = get_font(40, True)
    f_publik = get_font(60, True)

    # Header
    draw.text((W//2, 120), "MAÇ SONUCU", font=f_baslik, fill=TEXT_WHITE, anchor="mm")
    draw.line([(W//2 - 200, 180), (W//2 + 200, 180)], fill=ACCENT_ORANGE, width=6)

    CENTER_Y = H // 2 - 50
    LOGO_SIZE = 225
    OFFSET_X = 320
    
    # Skor
    draw.text((W//2, CENTER_Y), skor, font=f_skor, fill=TEXT_WHITE, anchor="mm")
    
    # Logolar
    ev_img = get_local_logo(ev, LOGO_SIZE)
    if ev_img:
        pos_x = (W//2 - OFFSET_X) - (ev_img.width // 2)
        pos_y = CENTER_Y - (ev_img.height // 2)
        img.paste(ev_img, (pos_x, pos_y), ev_img)
    
    dep_img = get_local_logo(dep, LOGO_SIZE)
    if dep_img:
        pos_x = (W//2 + OFFSET_X) - (dep_img.width // 2)
        pos_y = CENTER_Y - (dep_img.height // 2)
        img.paste(dep_img, (pos_x, pos_y), dep_img)

    # İsimler
    ev_gos = tr_karakter_cevir(ev)
    dep_gos = tr_karakter_cevir(dep)

    draw.text((W//2 - OFFSET_X, CENTER_Y + 160), ev_gos, font=f_takim, fill=TEXT_GREY, anchor="mm")
    draw.text((W//2 + OFFSET_X, CENTER_Y + 160), dep_gos, font=f_takim, fill=TEXT_GREY, anchor="mm")

    # Footer
    draw.text((W//2, H - 80), "publik.", font=f_publik, fill=ACCENT_ORANGE, anchor="mm")
    draw.polygon([(0, H), (0, H-150), (150, H)], fill=ACCENT_ORANGE)
    
    img.save("test_mac_sonucu.png")
    print("✅ 'test_mac_sonucu.png' hazır.")

# =============================================================================
# 2. FİKSTÜR VERİSİ
# =============================================================================
def fikstur_verisi_cek():
    print("📡 Fikstür verisi çekiliyor...")
    today = datetime.datetime.now()
    end_date = today + datetime.timedelta(days=7)
    date_str = f"{today.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"
    url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/tur.1/scoreboard?dates={date_str}"
    
    try:
        r = requests.get(url, timeout=10).json()
        events = r.get('events', [])
        maclar = []
        for e in events:
            tarih_obj = datetime.datetime.strptime(e['date'], "%Y-%m-%dT%H:%MZ") + datetime.timedelta(hours=3)
            tarih_str = tarih_obj.strftime("%d.%m")
            gun_ing = tarih_obj.strftime("%a")
            gunler = {"Mon":"Pzt", "Tue":"Sal", "Wed":"Çar", "Thu":"Per", "Fri":"Cum", "Sat":"Cmt", "Sun":"Paz"}
            gun_str = gunler.get(gun_ing, gun_ing)
            saat_str = tarih_obj.strftime("%H:%M")

            ev_ad = e['competitions'][0]['competitors'][0]['team']['displayName'].upper()
            dep_ad = e['competitions'][0]['competitors'][1]['team']['displayName'].upper()
            
            maclar.append({
                'tarih_obj': tarih_obj,
                'tarih_str': f"{tarih_str} {gun_str}",
                'saat': saat_str,
                'ev': ev_ad,
                'dep': dep_ad
            })
        
        return sorted(maclar, key=lambda x: x['tarih_obj'])
    except: return []

# =============================================================================
# 3. FİKSTÜR TASARIMI (ORTALAMA VE FONT DÜZELTİLDİ)
# =============================================================================
def fikstur_gorseli_olustur(maclar):
    print("🎨 FİKSTÜR Çiziliyor (Simetrik Hizalama)...")
    W, H = 1080, 1500 
    img = Image.new('RGB', (W, H), color=DARK_BG)
    draw = ImageDraw.Draw(img)

    f_baslik = get_font(100, True)
    f_alt = get_font(50, False)
    f_tarih = get_font(28, False)
    f_saat = get_font(32, True)
    f_publik = get_font(80, True)

    # Header
    draw.text((60, 80), "BU HAFTA", font=f_baslik, fill=TEXT_WHITE)
    draw.text((60, 180), "FIKSTUR", font=f_alt, fill=ACCENT_ORANGE)

    x_pos = yerel_gorsel_ekle(img, "trendyol.png", 130, 650, 80)
    yerel_gorsel_ekle(img, "25-26.png", 130, x_pos, 80)

    # Koordinatlar
    Y_START = 320
    ROW_HEIGHT = 110 
    LOGO_SIZE = 55
    CENTER_X = 600 # Tam orta nokta
    
    # Sabit Logo Konumları (İp gibi dizilmesi için)
    LOGO_X_EV = 280 
    LOGO_X_DEP = 920
    
    # Metin Yaslama Noktaları (Ortadaki tireye eşit uzaklıkta)
    # Tire X=600. Boşluk 30px verelim.
    # Ev ismi 570'de biter (Sağa yaslı)
    # Dep ismi 630'da başlar (Sola yaslı)
    TEXT_X_EV_END = 570
    TEXT_X_DEP_START = 630
    
    # İsim alanı genişliği (Logo ile Tire arasındaki mesafe)
    # 570 (Tire) - 280 (Logo Merkezi) - 30 (Logo payı) ≈ 260px
    MAX_TEXT_W = 250

    # 1. ADIM: Ortak Font Hesapla
    tum_takimlar = []
    for m in maclar[:10]:
        tum_takimlar.append(tr_karakter_cevir(m['ev']))
        tum_takimlar.append(tr_karakter_cevir(m['dep']))
    
    # Başlangıç boyutu 40px, sığmazsa küçülecek
    f_takim = hesapla_ortak_font(draw, tum_takimlar, MAX_TEXT_W, 40)
    f_tire = get_font(36, True)

    for i, mac in enumerate(maclar[:10]): 
        y = Y_START + (i * ROW_HEIGHT)
        Y_CENTER = y + (ROW_HEIGHT / 2) # Satırın dikey ortası
        
        if i % 2 == 0: draw.rectangle([(20, y), (1060, y + ROW_HEIGHT)], fill=(20, 25, 45))
        
        # Tarih/Saat
        draw.rectangle([(30, y + 15), (40, y + ROW_HEIGHT - 15)], fill=ACCENT_BLUE)
        draw.text((60, y + 25), mac['tarih_str'], font=f_tarih, fill=TEXT_GREY)
        draw.text((60, y + 60), mac['saat'], font=f_saat, fill=TEXT_WHITE)

        # Tire (Tam Ortada)
        draw.text((CENTER_X, Y_CENTER), "-", font=f_tire, fill=ACCENT_ORANGE, anchor="mm")
        
        # --- EV SAHİBİ (SOL) ---
        ev_adi = tr_karakter_cevir(mac['ev'])
        
        # Logo (Sabit Konum, Dikey Ortalı)
        ev_logo = get_local_logo(mac['ev'], LOGO_SIZE)
        if ev_logo:
            l_x = int(LOGO_X_EV - ev_logo.width / 2)
            l_y = int(Y_CENTER - ev_logo.height / 2)
            img.paste(ev_logo, (l_x, l_y), ev_logo)
            
        # İsim (Tire'ye Yaslı)
        # anchor="rm" (Right Middle) -> X koordinatı metnin sağ ucu olur
        draw.text((TEXT_X_EV_END, Y_CENTER), ev_adi, font=f_takim, fill=TEXT_WHITE, anchor="rm")

        # --- DEPLASMAN (SAĞ) ---
        dep_adi = tr_karakter_cevir(mac['dep'])
        
        # İsim (Tire'ye Yaslı)
        # anchor="lm" (Left Middle) -> X koordinatı metnin sol başı olur
        draw.text((TEXT_X_DEP_START, Y_CENTER), dep_adi, font=f_takim, fill=TEXT_WHITE, anchor="lm")
        
        # Logo (Sabit Konum, Dikey Ortalı)
        dep_logo = get_local_logo(mac['dep'], LOGO_SIZE)
        if dep_logo:
            l_x = int(LOGO_X_DEP - dep_logo.width / 2)
            l_y = int(Y_CENTER - dep_logo.height / 2)
            img.paste(dep_logo, (l_x, l_y), dep_logo)

    # Footer
    draw.text((W//2, H - 80), "publik.", font=f_publik, fill=ACCENT_ORANGE, anchor="mm")
    
    img.save("test_fikstur.png")
    print("✅ 'test_fikstur.png' hazır.")

if __name__ == "__main__":
    # 1. TEST: MAÇ SONUCU
    # Logolar logos klasöründen çekilecek (BESIKTAS.png ve TRABZONSPOR.png olmalı)
    mac_sonucu_gorseli_olustur("BESIKTAS", "TRABZONSPOR", "1 - 1")

    # 2. TEST: FİKSTÜR
    maclar = fikstur_verisi_cek()
    if maclar:
        fikstur_gorseli_olustur(maclar)
    else:
        print("⚠️ Fikstür verisi bulunamadı.")