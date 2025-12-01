import tweepy
import feedparser
import requests
import time
import schedule
import datetime
import os
import re
import google.generativeai as genai
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from time import mktime
from flask import Flask
import threading

# =============================================================================
# 🌍 PUBLIKSPOR V27 - FINAL EDITION (ALL FEATURES UNLOCKED)
# =============================================================================

# --- 1. AYARLAR VE ŞİFRELER ---
GEMINI_API_KEY = "AIzaSyAD0mlTGn5tA5gQBBcgjwPqQeVDcx4fcjk"

# Twitter (Senin Yeni Şifrelerin)
API_KEY = "Ds6HnkJCLvIrHf2ChXgwy47GZ"
API_SECRET = "2ITh94OlZ1OYhsnG5XkU9Ot2fEIE4pZVXwF6opp2fl9SnJ8Mmo"
ACCESS_TOKEN = "1989860228150788096-k2XifKyI27cbSKKWmCZsNJH1Ypg4wW"
ACCESS_SECRET = "oeRrU4nUR9xfDmR3Sbn26qdcdhjF3uu1xyeMIRmCoZTtb"

# Ntfy (Bildirim) Ayarı
NTFY_TOPIC = "publikspor_admin"

# Renkler
DARK_BG = (10, 15, 30)
TEXT_WHITE = (255, 255, 255)
TEXT_GREY = (170, 170, 170)
ACCENT_ORANGE = (255, 140, 0)
ACCENT_BLUE = (0, 180, 255)

LOG_DOSYASI = "paylasilanlar.txt"
SKOR_HAFIZASI = {} 

RSS_KAYNAKLARI = [
    "https://www.ntv.com.tr/spor.rss",
    "https://www.cumhuriyet.com.tr/rss/spor",
    "https://rss.haberler.com/rss.asp?kategori=spor",
    "https://www.eurohoops.net/tr/feed/",
    "https://tr.motorsport.com/rss/f1/news/"
]

VIP_ANAHTARLAR = [
    "Fenerbahçe", "Galatasaray", "Beşiktaş", "Trabzonspor", "Milli Takım", 
    "Arda Güler", "Kenan Yıldız", "Icardi", "Osimhen", "Mourinho", 
    "Voleybol", "Filenin Sultanları", "Ebrar Karakurt", "Vargas",
    "Basketbol", "Anadolu Efes", "Fenerbahçe Beko", "Ergin Ataman",
    "F1", "Hamilton", "Verstappen"
]

LIGLER = {
    "SUPER_LIG": "http://site.api.espn.com/apis/site/v2/sports/soccer/tur.1/scoreboard",
    "UCL": "http://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard",
}

# --- BAŞLATMALAR ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

try:
    auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
    api = tweepy.API(auth, wait_on_rate_limit=True)
    client = tweepy.Client(
        consumer_key=API_KEY, consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN, access_token_secret=ACCESS_SECRET,
        wait_on_rate_limit=True
    )
    print("✅ Twitter Bağlantısı Başarılı.")
except Exception as e:
    print(f"❌ Twitter Bağlantı Hatası: {e}")

# --- 2. BİLDİRİM SİSTEMİ (NTFY) ---
def bildirim_gonder(baslik, mesaj, oncelik="default"):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=mesaj.encode('utf-8'),
            headers={"Title": baslik.encode('utf-8'), "Priority": oncelik}
        )
    except: pass

# --- 3. YARDIMCI ARAÇLAR ---
def log_kontrol(link):
    if not os.path.exists(LOG_DOSYASI): return False
    with open(LOG_DOSYASI, "r", encoding="utf-8") as f: return link in f.read()

def log_kaydet(link):
    with open(LOG_DOSYASI, "a", encoding="utf-8") as f: f.write(link + "\n")

def clickbait_temizle(metin):
    yasakli = ["CANLI İZLE", "ŞİFRESİZ", "BEDAVA", "DONMADAN", "LİNK", "TIKLA", "İZLE", "JUSTIN TV"]
    temiz = metin
    for y in yasakli:
        pattern = re.compile(re.escape(y), re.IGNORECASE)
        temiz = pattern.sub("", temiz)
    return re.sub(r'\s+', ' ', temiz).strip()

def haber_taze_mi(haber_zamani_struct):
    try:
        if not haber_zamani_struct: return True
        fark = datetime.datetime.now() - datetime.datetime.fromtimestamp(mktime(haber_zamani_struct))
        return (fark.total_seconds() / 3600) < 24
    except: return True

def ai_tweet_yaz(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text.strip().replace('"','')
    except: return None

# --- 4. GRAFİK MOTORU ---
def get_font(size, is_bold=False):
    try: return ImageFont.truetype("font.otf", size)
    except: return ImageFont.truetype("arialbd.ttf" if is_bold else "arial.ttf", size)

def tr_karakter_cevir(metin):
    ceviri = str.maketrans("ŞşĞğÜüİıÖöÇç", "SsGgUuIiOoCc")
    temiz = metin.translate(ceviri).upper().strip()
    if "ISTANBUL BASAKSEHIR" in temiz: return "BASAKSEHIR"
    if "FATIH KARAGUMRUK" in temiz: return "KARAGUMRUK"
    if "CAYKUR RIZESPOR" in temiz: return "RIZESPOR"
    return temiz

def resim_indir(url, size):
    if not url: return None
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        img = Image.open(BytesIO(r.content)).convert("RGBA")
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        return img
    except: return None

def get_local_logo(takim_adi, size):
    temiz_ad = tr_karakter_cevir(takim_adi)
    olasi = [temiz_ad, temiz_ad.split(" ")[-1]]
    for isim in olasi:
        yollar = [f"logos/{isim}.png", f"logos/{isim}.jpg"]
        for yol in yollar:
            if os.path.exists(yol):
                try:
                    img = Image.open(yol).convert("RGBA")
                    img.thumbnail((size, size), Image.Resampling.LANCZOS)
                    return img
                except: pass
    return None

def yerel_gorsel_ekle(ana_resim, dosya_adi, hedef_yukseklik, x, y):
    if not os.path.exists(dosya_adi): return x
    try:
        img_local = Image.open(dosya_adi).convert("RGBA")
        oran = hedef_yukseklik / img_local.height
        yeni_gen = int(img_local.width * oran)
        img_resized = img_local.resize((yeni_gen, hedef_yukseklik), Image.Resampling.LANCZOS)
        ana_resim.paste(img_resized, (x, y), img_resized)
        return x + yeni_gen + 20
    except: return x

def hesapla_ortak_font(draw, text_list, max_width, start_size):
    current = start_size
    while current > 10:
        font = get_font(current, True)
        if all(draw.textlength(t, font=font) < max_width for t in text_list): return font
        current -= 1
    return get_font(12, True)

def mac_sonucu_gorseli_olustur(ev, dep, skor, ev_web_logo, dep_web_logo):
    print(f"🎨 MAÇ SONUCU Çiziliyor: {ev} vs {dep}...")
    W, H = 1080, 1080 
    img = Image.new('RGB', (W, H), color=DARK_BG)
    draw = ImageDraw.Draw(img)
    f_baslik = get_font(90, True); f_skor = get_font(200, True)
    f_takim = get_font(40, True); f_publik = get_font(60, True)

    draw.text((W//2, 120), "MAÇ SONUCU", font=f_baslik, fill=TEXT_WHITE, anchor="mm")
    draw.line([(W//2 - 200, 180), (W//2 + 200, 180)], fill=ACCENT_ORANGE, width=6)
    CENTER_Y = H // 2 - 50; LOGO_SIZE = 225; OFFSET_X = 320
    draw.text((W//2, CENTER_Y), skor, font=f_skor, fill=TEXT_WHITE, anchor="mm")
    
    ev_img = get_local_logo(ev, LOGO_SIZE)
    if not ev_img and ev_web_logo: ev_img = resim_indir(ev_web_logo, LOGO_SIZE)
    dep_img = get_local_logo(dep, LOGO_SIZE)
    if not dep_img and dep_web_logo: dep_img = resim_indir(dep_web_logo, LOGO_SIZE)

    if ev_img: img.paste(ev_img, ((W//2 - OFFSET_X) - (ev_img.width // 2), CENTER_Y - (ev_img.height // 2)), ev_img)
    if dep_img: img.paste(dep_img, ((W//2 + OFFSET_X) - (dep_img.width // 2), CENTER_Y - (dep_img.height // 2)), dep_img)

    draw.text((W//2 - OFFSET_X, CENTER_Y + 160), tr_karakter_cevir(ev), font=f_takim, fill=TEXT_GREY, anchor="mm")
    draw.text((W//2 + OFFSET_X, CENTER_Y + 160), tr_karakter_cevir(dep), font=f_takim, fill=TEXT_GREY, anchor="mm")
    draw.text((W//2, H - 80), "publik.", font=f_publik, fill=ACCENT_ORANGE, anchor="mm")
    draw.polygon([(0, H), (0, H-150), (150, H)], fill=ACCENT_ORANGE)
    
    dosya = f"ms_{tr_karakter_cevir(ev)}_{tr_karakter_cevir(dep)}.png"
    img.save(dosya)
    return dosya

def fikstur_gorseli_olustur(maclar):
    print("🎨 FİKSTÜR Çiziliyor...")
    W, H = 1080, 1500 
    img = Image.new('RGB', (W, H), color=DARK_BG)
    draw = ImageDraw.Draw(img)
    f_baslik = get_font(100, True); f_alt = get_font(50, False)
    f_tarih = get_font(28, False); f_saat = get_font(32, True); f_publik = get_font(80, True)

    draw.text((60, 80), "BU HAFTA", font=f_baslik, fill=TEXT_WHITE)
    draw.text((60, 180), "FIKSTUR", font=f_alt, fill=ACCENT_ORANGE)
    yerel_gorsel_ekle(img, "trendyol.png", 130, 650, 80)

    Y_START = 320; ROW_HEIGHT = 110; LOGO_SIZE = 55; CENTER_X = 600
    LOGO_X_EV = 280; LOGO_X_DEP = 920
    TEXT_X_EV_END = 570; TEXT_X_DEP_START = 630; MAX_TEXT_W = 250

    tum_takimlar = [tr_karakter_cevir(m['ev']) for m in maclar[:10]] + [tr_karakter_cevir(m['dep']) for m in maclar[:10]]
    f_takim = hesapla_ortak_font(draw, tum_takimlar, MAX_TEXT_W, 40)
    f_tire = get_font(36, True)

    for i, mac in enumerate(maclar[:10]): 
        y = Y_START + (i * ROW_HEIGHT)
        Y_CENTER = y + (ROW_HEIGHT / 2)
        if i % 2 == 0: draw.rectangle([(20, y), (1060, y + ROW_HEIGHT)], fill=(20, 25, 45))
        
        draw.rectangle([(30, y + 15), (40, y + ROW_HEIGHT - 15)], fill=ACCENT_BLUE)
        draw.text((60, y + 25), mac['tarih_str'], font=f_tarih, fill=TEXT_GREY)
        draw.text((60, y + 60), mac['saat'], font=f_saat, fill=TEXT_WHITE)
        draw.text((CENTER_X, Y_CENTER), "-", font=f_tire, fill=ACCENT_ORANGE, anchor="mm")
        
        ev_logo = get_local_logo(mac['ev'], LOGO_SIZE)
        if ev_logo: img.paste(ev_logo, (int(LOGO_X_EV - ev_logo.width / 2), int(Y_CENTER - ev_logo.height / 2)), ev_logo)
        draw.text((TEXT_X_EV_END, Y_CENTER), tr_karakter_cevir(mac['ev']), font=f_takim, fill=TEXT_WHITE, anchor="rm")

        dep_logo = get_local_logo(mac['dep'], LOGO_SIZE)
        if dep_logo: img.paste(dep_logo, (int(LOGO_X_DEP - dep_logo.width / 2), int(Y_CENTER - dep_logo.height / 2)), dep_logo)
        draw.text((TEXT_X_DEP_START, Y_CENTER), tr_karakter_cevir(mac['dep']), font=f_takim, fill=TEXT_WHITE, anchor="lm")

    draw.text((W//2, H - 80), "publik.", font=f_publik, fill=ACCENT_ORANGE, anchor="mm")
    img.save("fikstur.png")
    return "fikstur.png"

# --- 5. GÖREV YÖNETİCİLERİ ---

def siteyi_analiz_et(url):
    print("🕵️‍♂️ Site Analizi...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    media_id = None; sayfa_metni = ""
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        img_tag = soup.find("meta", property="og:image")
        if img_tag and img_tag.get("content"):
            try:
                img_data = requests.get(img_tag["content"], headers=headers).content
                with open("temp.jpg", "wb") as f: f.write(img_data)
                media = api.media_upload("temp.jpg")
                media_id = media.media_id
                os.remove("temp.jpg")
            except: pass
            
        tags = soup.find_all(['p', 'h2', 'strong'])
        sayfa_metni = " ".join([t.text.strip() for t in tags])[:2500]
    except: pass
    return media_id, sayfa_metni

def spor_kategorisi_bul(metin):
    m = metin.lower()
    if any(x in m for x in ["voleybol", "sultanlar", "vargas"]): return "#Voleybol"
    if any(x in m for x in ["basketbol", "nba", "euroleague"]): return "#Basketbol"
    if any(x in m for x in ["f1", "formula", "yarış"]): return "#F1"
    return "#Futbol"

# --- GÜNCELLENMİŞ VE ZIRHLI HABER FONKSİYONU ---
def gorev_haber_taramasi():
    print(f"📰 [{datetime.datetime.now().strftime('%H:%M')}] Haberler Taranıyor...")
    for url in RSS_KAYNAKLARI:
        try:
            feed = feedparser.parse(requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).content)
            for haber in feed.entries[:2]:
                if hasattr(haber, 'published_parsed') and not haber_taze_mi(haber.published_parsed): continue
                
                baslik = haber.title
                link = haber.link
                
                if not log_kontrol(link):
                    if any(x.lower() in baslik.lower() for x in VIP_ANAHTARLAR):
                        print(f"🆕 Haber: {baslik}")
                        baslik_temiz = clickbait_temizle(baslik)
                        
                        # --- GÜVENLİ RESİM İNDİRME ---
                        media_id = None
                        site_icerigi = ""
                        try:
                            # Önce siteye git, metni al
                            media_id, site_icerigi = siteyi_analiz_et(link)
                        except Exception as e:
                            print(f"⚠️ Site Analiz Hatası: {e} (Devam ediliyor...)")

                        kategori = spor_kategorisi_bul(baslik_temiz + site_icerigi)
                        
                        prompt = f"""
                        Sen profesyonel spor spikerisin. Bu haberi Twitter için TEK CÜMLEDE, akıcı yaz.
                        Haber: {baslik_temiz}
                        Detay: {site_icerigi}
                        KURALLAR: Robot gibi olma. Soru sorma. Emoji abartma. Şifresiz/Link yazma.
                        """
                        metin = ai_tweet_yaz(prompt)
                        if not metin: metin = baslik_temiz
                        
                        zaman = datetime.datetime.now().strftime('%H:%M')
                        tweet = f"{metin}\n\n🔗 Kaynak: Basın\n#PublikSpor {kategori}\n⏱ {zaman}"
                        
                        try:
                            # --- TWEET ATMA DENEMESİ ---
                            if media_id: 
                                client.create_tweet(text=tweet, media_ids=[media_id])
                            else: 
                                client.create_tweet(text=tweet)
                                
                            print("🐦 Tweet BAŞARIYLA Atıldı!")
                            log_kaydet(link) # Başarılıysa kaydet
                            
                            # Anti-Ban Beklemesi
                            print("⏳ Spam olmaması için 60 saniye bekleniyor...")
                            time.sleep(60)
                            
                        except Exception as e: 
                            print(f"🔴 TWEET HATASI: {e}")
                            
                            # --- KRİTİK DEĞİŞİKLİK BURASI ---
                            # Eğer bağlantı hatası veya 429 varsa, bu haberi LANETLİ say ve geç.
                            # Bir daha denememek için loga kaydediyoruz.
                            print("⚠️ Bu haber sorunlu, atlanıyor ve loga işleniyor...")
                            log_kaydet(link) 
                            
                            if "429" in str(e):
                                print("⏳ 429 Hatası! 15 Dakika Zorunlu Mola...")
                                time.sleep(900)
        except Exception as e:
            print(f"Genel Döngü Hatası: {e}")

def gorev_fikstur_paylas():
    print("📅 Fikstür Verisi Alınıyor...")
    today = datetime.datetime.now()
    end_date = today + datetime.timedelta(days=7)
    date_str = f"{today.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"
    url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/tur.1/scoreboard?dates={date_str}"
    
    try:
        r = requests.get(url, timeout=10).json()
        events = r.get('events', [])
        if not events: return
        
        maclar = []
        for e in events:
            tarih_obj = datetime.datetime.strptime(e['date'], "%Y-%m-%dT%H:%MZ") + datetime.timedelta(hours=3)
            tarih_str = tarih_obj.strftime("%d.%m")
            gun_ing = tarih_obj.strftime("%a")
            gun_str = {"Mon":"Pzt", "Tue":"Sal", "Wed":"Çar", "Thu":"Per", "Fri":"Cum", "Sat":"Cmt", "Sun":"Paz"}.get(gun_ing, gun_ing)
            saat_str = tarih_obj.strftime("%H:%M")
            ev = e['competitions'][0]['competitors'][0]['team']['displayName'].upper()
            dep = e['competitions'][0]['competitors'][1]['team']['displayName'].upper()
            maclar.append({'tarih_str': f"{tarih_str} {gun_str}", 'saat': saat_str, 'ev': ev, 'dep': dep, 'tarih_obj': tarih_obj})
        
        maclar = sorted(maclar, key=lambda x: x['tarih_obj'])
        dosya = fikstur_gorseli_olustur(maclar)
        
        if dosya:
            metin = "📅 Süper Lig'de Bu Hafta!\n\nZorlu karşılaşmalar bizleri bekliyor. İşte haftanın programı. 👇\n\n#SüperLig #Fikstür #PublikSpor"
            try:
                media = api.media_upload(dosya)
                client.create_tweet(text=metin, media_ids=[media.media_id])
                print("✅ Fikstür Tweeti Atıldı!")
                bildirim_gonder("Fikstür", "Haftalık Program Paylaşıldı")
                os.remove(dosya)
            except Exception as e: print(f"Fikstür Hatası: {e}")
    except: pass

def gorev_canli_skor():
    print(f"⚽ [{datetime.datetime.now().strftime('%H:%M')}] Skorlar Kontrol Ediliyor...")
    for lig, url in LIGLER.items():
        try:
            r = requests.get(url, timeout=10).json()
            for mac in r.get('events', []):
                mac_id = mac['id']; durum = mac['status']['type']['state']
                ev = mac['competitions'][0]['competitors'][0]
                dep = mac['competitions'][0]['competitors'][1]
                ev_ad = ev['team']['displayName'].upper()
                dep_ad = dep['team']['displayName'].upper()
                skor = f"{ev['score']}-{dep['score']}"
                
                if mac_id not in SKOR_HAFIZASI: SKOR_HAFIZASI[mac_id] = skor
                eski = SKOR_HAFIZASI[mac_id]

                onemli = False
                if lig == "SUPER_LIG": onemli = True
                elif lig == "UCL" and ("GALATASARAY" in ev_ad or "GALATASARAY" in dep_ad): onemli = True

                if onemli:
                    if durum == 'in' and eski != skor:
                        tweet = f"⚽ GOL! {ev_ad} {skor} {dep_ad} #PublikSpor"
                        try: 
                            client.create_tweet(text=tweet)
                            print(f"🚨 GOL: {skor}")
                            bildirim_gonder("GOL!", f"{ev_ad} {skor} {dep_ad}")
                        except: pass
                    
                    if durum == 'post':
                        ms_key = f"MS_{mac_id}"
                        if not log_kontrol(ms_key):
                            try:
                                ev_web_logo = ev['team']['logos'][0]['href'] if ev['team'].get('logos') else None
                                dep_web_logo = dep['team']['logos'][0]['href'] if dep['team'].get('logos') else None
                                
                                img_dosya = mac_sonucu_gorseli_olustur(ev_ad, dep_ad, skor, ev_web_logo, dep_web_logo)
                                media = api.media_upload(img_dosya)
                                
                                yorum = ai_tweet_yaz(f"Maç bitti: {ev_ad} {skor} {dep_ad}. Kazananı öv.")
                                if not yorum: yorum = "Maç sona erdi."
                                
                                text = f"🏁 MAÇ SONUCU\n\n{ev_ad} {skor} {dep_ad}\n\n🗣️ {yorum}\n#PublikSpor"
                                client.create_tweet(text=text, media_ids=[media.media_id])
                                log_kaydet(ms_key)
                                print(f"🏁 MS Görseli Paylaşıldı: {skor}")
                                bildirim_gonder("Maç Bitti", f"{ev_ad} {skor} {dep_ad}")
                                os.remove(img_dosya)
                            except Exception as e: print(f"MS Hatası: {e}")
                
                SKOR_HAFIZASI[mac_id] = skor
        except Exception as e: print(f"⚠️ Skor Hatası: {e}")

# --- WEB SERVER (RENDER İÇİN) ---
app = Flask(__name__)
@app.route('/')
def home(): return "PublikSpor Botu Calisiyor! 🚀"
def run_flask(): app.run(host='0.0.0.0', port=10000)

# --- BAŞLAT ---
def programi_baslat():
    print("🌍 PUBLIKSPOR V27 (FINAL) Başlatıldı...")
    
    bildirim_gonder("Sistem Başladı", "Bot başarıyla aktif oldu.", "high")
    
    t = threading.Thread(target=run_flask)
    t.daemon = True; t.start()
    
    # İlk Taramalar
    gorev_haber_taramasi()
    
    schedule.every(5).minutes.do(gorev_haber_taramasi)
    schedule.every(1).minutes.do(gorev_canli_skor)
    schedule.every().friday.at("09:00").do(gorev_fikstur_paylas)
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Bot durduruldu.")
            break
        except Exception as e:
            print(f"Ana Döngü Hatası: {e}")
            time.sleep(60)

if __name__ == "__main__":
    programi_baslat()