from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import os

# --- RENKLER ---
DARK_BG = (10, 15, 30)         # Zemin
TEXT_WHITE = (255, 255, 255)   # Yazılar
TEXT_GREY = (170, 170, 170)    # Gri Yazılar
ACCENT_ORANGE = (255, 140, 0)  # Turuncu
ACCENT_BLUE = (0, 180, 255)    # Mavi

def veri_cek_canli():
    print("📡 Veriler çekiliyor...")
    url = "http://site.api.espn.com/apis/v2/sports/soccer/tur.1/standings"
    try:
        r = requests.get(url, timeout=10).json()
        entries = r['children'][0]['standings']['entries']
        data = []
        for e in entries:
            stats = e['stats']
            def get_s(n): return next((int(s['value']) for s in stats if s['name'] == n), 0)
            
            logo = e['team']['logos'][0]['href'] if e['team'].get('logos') else None
            name = e['team']['displayName'].upper() 
            
            # Ekstra uzunları hafif kırpma
            if "ISTANBUL BASAKSEHIR" in name: name = "BASAKSEHIR"
            if "FATIH KARAGUMRUK" in name: name = "KARAGUMRUK"

            data.append({
                'name': name,
                'logo': logo,
                'O': get_s('gamesPlayed'),
                'G': get_s('wins'),
                'B': get_s('ties'),
                'M': get_s('losses'),
                'A': get_s('pointsFor'),
                'Y': get_s('pointsAgainst'),
                'AV': get_s('pointDifferential'),
                'P': get_s('points')
            })
            
        data = sorted(data, key=lambda x: (x['P'], x['AV']), reverse=True)
        for i, d in enumerate(data): d['rank'] = i + 1
        return data[:20]
    except Exception as e:
        print(f"Hata: {e}")
        return []

def resim_indir(url, size):
    if not url: return None
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        img = Image.open(BytesIO(r.content)).convert("RGBA")
        return img.resize((size, size), Image.Resampling.LANCZOS)
    except: return None

# --- ORTAK FONT HESAPLAYICI ---
def hesapla_ortak_font(draw, takim_listesi, max_genislik, baslangic_boyutu):
    current_size = baslangic_boyutu
    while current_size > 15: 
        font = ImageFont.truetype("arialbd.ttf", current_size)
        hepsi_sigiyor = True
        for takim in takim_listesi:
            w = draw.textlength(takim['name'], font=font)
            if w > max_genislik:
                hepsi_sigiyor = False
                break
        if hepsi_sigiyor:
            print(f"✅ Ortak font boyutu bulundu: {current_size}px")
            return font, current_size
        current_size -= 1
    return ImageFont.load_default(), 20

# --- YEREL GÖRSEL EKLEME (REVİZE EDİLDİ) ---
def yerel_gorsel_ekle(ana_resim, dosya_adi, hedef_yukseklik, x, y):
    """Bilgisayardaki dosyayı açar, HEDEF YÜKSEKLİĞE göre orantılı boyutlandırır ve yapıştırır."""
    if not os.path.exists(dosya_adi):
        print(f"⚠️ UYARI: '{dosya_adi}' bulunamadı!")
        return x
        
    try:
        img_local = Image.open(dosya_adi).convert("RGBA")
        # Orantılı yeniden boyutlandırma: (Hedef Yükseklik / Mevcut Yükseklik) oranıyla genişliği çarp
        oran = hedef_yukseklik / img_local.height
        yeni_genislik = int(img_local.width * oran)
        
        img_resized = img_local.resize((yeni_genislik, hedef_yukseklik), Image.Resampling.LANCZOS)
        ana_resim.paste(img_resized, (x, y), img_resized)
        
        return x + yeni_genislik + 20 # Bir sonraki resim için x konumunu güncelle (20px boşluk)
    except Exception as e:
        print(f"Hata ({dosya_adi}): {e}")
        return x

def create_equal_font_style(veriler):
    print("🎨 Tasarım işleniyor (Logolu Header Düzeltildi)...")
    
    W, H = 1080, 1500
    img = Image.new('RGB', (W, H), color=DARK_BG)
    draw = ImageDraw.Draw(img)

    # Standart Fontlar
    try:
        f_rank = ImageFont.truetype("arialbd.ttf", 32)
        f_head = ImageFont.truetype("arial.ttf", 26)
        f_stat = ImageFont.truetype("arial.ttf", 32)
        f_pts = ImageFont.truetype("arialbd.ttf", 38)
        f_title = ImageFont.truetype("arialbd.ttf", 80)
        f_publik = ImageFont.truetype("arialbd.ttf", 180) 
    except:
        f_rank = ImageFont.load_default()

    # --- ÖNCE ORTAK FONTU HESAPLA ---
    MAX_NAME_WIDTH = 290 
    f_takim_ortak, font_size = hesapla_ortak_font(draw, veriler, MAX_NAME_WIDTH, 36)

    # --- SAĞ TARAF: DİKEY "publik." ---
    txt_img = Image.new('RGBA', (1000, 300), (0,0,0,0))
    d_txt = ImageDraw.Draw(txt_img)
    d_txt.text((0,0), "publik.", font=f_publik, fill=ACCENT_ORANGE)
    txt_rot = txt_img.rotate(90, expand=True)
    img.paste(txt_rot, (W - 220, H//2 - 500), txt_rot)

    # --- HEADER DÜZENLEMESİ (LOGOLAR SAĞDA VE HİZALI) ---
    # Başlık Yazıları
    draw.text((60, 80), "PUAN", font=f_title, fill=TEXT_WHITE)
    draw.text((60, 170), "DURUMU", font=f_title, fill=ACCENT_ORANGE)
    
    # LOGOLARIN EKLENMESİ
    # Hedef Yükseklik: PUAN DURUMU yazısının toplam yüksekliği kadar (yaklaşık 140px)
    hedef_logo_h = 140
    # Başlangıç X konumu: "DURUMU" yazısının bittiği yerin sağı (yaklaşık 450px)
    logo_start_x = 450 
    # Y Konumu: "PUAN" yazısının üst hizası
    logo_y = 80 
    
    # 1. Trendyol Süper Lig Logosu
    next_x = yerel_gorsel_ekle(img, "trendyol.png", hedef_logo_h, logo_start_x, logo_y)
    
    # 2. Sezon Logosu (25-26.png)
    yerel_gorsel_ekle(img, "25-26.png", hedef_logo_h, next_x, logo_y)

    # --- TABLO BAŞLIKLARI ---
    Y_HEAD = 280
    X_START_STATS = 470 
    X_STEP = 52
    
    cols = ["O", "G", "B", "M", "A", "Y", "AV"]
    
    draw.text((180, Y_HEAD), "TAKIMLAR", font=f_head, fill=TEXT_GREY, anchor="lm")
    
    for i, c in enumerate(cols):
        draw.text((X_START_STATS + (i*X_STEP), Y_HEAD), c, font=f_head, fill=TEXT_GREY, anchor="mm")
    
    draw.text((X_START_STATS + (7*X_STEP) + 10, Y_HEAD), "P", font=ImageFont.truetype("arialbd.ttf", 28), fill=ACCENT_ORANGE, anchor="mm")
    draw.line([(40, Y_HEAD + 40), (880, Y_HEAD + 40)], fill=(50, 60, 80), width=2)

    # --- SATIRLAR ---
    Y_ROW = 340
    ROW_H = 58
    
    for i, t in enumerate(veriler):
        y = Y_ROW + (i * ROW_H)
        
        # 1. Sıra No
        draw.text((60, y+25), str(t['rank']), font=f_rank, fill=TEXT_WHITE, anchor="mm")
        
        # 2. Logo
        if t['logo']:
            logo = resim_indir(t['logo'], 40)
            if logo: img.paste(logo, (90, y+5), logo)
            
        # 3. Takım İsmi (HESAPLANAN ORTAK FONT İLE)
        draw.text((150, y+25), t['name'], font=f_takim_ortak, fill=TEXT_WHITE, anchor="lm")
        
        # 4. İstatistikler
        stats = [t['O'], t['G'], t['B'], t['M'], t['A'], t['Y'], t['AV']]
        for j, val in enumerate(stats):
            color = TEXT_GREY
            if j == 6 and val < 0: color = (200, 80, 80)
            elif j == 6 and val > 0: color = (80, 200, 100)
            
            draw.text((X_START_STATS + (j*X_STEP), y+25), str(val), font=f_stat, fill=color, anchor="mm")
            
        # 5. PUAN
        draw.text((X_START_STATS + (7*X_STEP) + 10, y+25), str(t['P']), font=f_pts, fill=TEXT_WHITE, anchor="mm")

        if i < 19:
            draw.line([(50, y+ROW_H), (870, y+ROW_H)], fill=(30, 35, 50), width=1)

    draw.text((60, H - 60), "twitter: @publikspor", font=f_head, fill=TEXT_GREY)
    draw.polygon([(W-80, 0), (W, 0), (W, 80)], fill=ACCENT_ORANGE)

    img.save("publik_equal_font.png")
    img.show()
    print(f"✅ Görsel hazır! Logolar başlığın sağında ve eşit boyda.")

if __name__ == "__main__":
    veriler = veri_cek_canli()
    if veriler:
        create_equal_font_style(veriler)