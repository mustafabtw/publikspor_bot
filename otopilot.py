import tweepy
import feedparser
import requests
import time
import schedule
import datetime
import os
import re
import html
import google.generativeai as genai
import trafilatura
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from time import mktime
from flask import Flask
import threading

# =============================================================================
# 🌍 PUBLIKSPOR V41 - NET GAZETECİ MODU (FİKSTÜR EKLENDİ + TAM KADRO)
# =============================================================================

# --- 1. AYARLAR VE ŞİFRELER ---
GEMINI_API_KEY = "AIzaSyAD0mlTGn5tA5gQBBcgjwPqQeVDcx4fcjk"

# Twitter
API_KEY = "Ds6HnkJCLvIrHf2ChXgwy47GZ"
API_SECRET = "2ITh94OlZ1OYhsnG5XkU9Ot2fEIE4pZVXwF6opp2fl9SnJ8Mmo"
ACCESS_TOKEN = "1989860228150788096-k2XifKyI27cbSKKWmCZsNJH1Ypg4wW"
ACCESS_SECRET = "oeRrU4nUR9xfDmR3Sbn26qdcdhjF3uu1xyeMIRmCoZTtb"

# Ntfy (Bildirim Kanalın)
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
    "F1", "Hamilton", "Verstappen", "Nihat Kahveci", "Rıdvan Dilmen", "Sergen Yalçın",
    "Fethiyespor", "Amedspor"
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
    api = tweepy.API(auth, wait_on_rate_limit=False) 
    client = tweepy.Client(
        consumer_key=API_KEY, consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN, access_token_secret=ACCESS_SECRET,
        wait_on_rate_limit=False
    )
    print("✅ Twitter Bağlantısı Başarılı.")
except Exception as e:
    print(f"❌ Twitter Bağlantı Hatası: {e}")

# --- 2. BİLDİRİM SİSTEMİ ---
def bildirim_gonder(baslik, mesaj, oncelik="default"):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=mesaj.encode('utf-8'),
            headers={"Title": baslik.encode('utf-8'), "Priority": oncelik, "Tags": "robot"}
        )
    except: pass

# --- 3. YARDIMCI ARAÇLAR ---
def log_kontrol(link):
    if not os.path.exists(LOG_DOSYASI): return False
    with open(LOG_DOSYASI, "r", encoding="utf-8") as f: return link in f.read()

def log_kaydet(link):
    with open(LOG_DOSYASI, "a", encoding="utf-8") as f: f.write(link + "\n")

def turkiye_saati():
    utc_now = datetime.datetime.utcnow()
    tr_now = utc_now + datetime.timedelta(hours=3)
    return tr_now.strftime('%H:%M')

def clickbait_temizle(metin):
    metin = html.unescape(metin)
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
        text = response.text.strip().replace('"','')
        if text and text[-1] not in ['.', '!', '?']:
            if '.' in text:
                text = text.rsplit('.', 1)[0] + "."
            else:
                text += "."
        return text
    except: return None

# --- HASHTAG DÜZELTME ---
def kisaltma_bul(takim):
    t = tr_karakter_cevir(takim)
    if "FENER" in t: return "FB"
    if "GALATA" in t: return "GS"
    if "BESIKTAS" in t: return "BJK"
    if "TRABZON" in t: return "TS"
    if "SAMSUN" in t: return "SAM"
    if "GOZTEPE" in t: return "GOZ"
    if "ANTALYA" in t: return "ANT"
    return t[:3].replace(" ", "").upper()

def mac_hashtag(ev, dep):
    return f"#{kisaltma_bul(ev)}v{kisaltma_bul(dep)}"

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
    print("🕵️‍♂️ Site Analizi (Trafilatura)...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    media_id = None; sayfa_metni = ""
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # 1. Görseli Al
        img_tag = soup.find("meta", property="og:image")
        if img_tag and img_tag.get("content"):
            try:
                img_data = requests.get(img_tag["content"], headers=headers, timeout=5).content
                with open("temp.jpg", "wb") as f: f.write(img_data)
                media = api.media_upload("temp.jpg")
                media_id = media.media_id
                os.remove("temp.jpg")
                print("📸 Görsel yüklendi.")
            except: print("⚠️ Görsel alınamadı.")

        # 2. Metni Trafilatura ile Al
        try:
            downloaded = trafilatura.fetch_url(url)
            sayfa_metni = trafilatura.extract(downloaded)
        except: sayfa_metni = None

        # 3. Trafilatura Başarısızsa Manuel Devam Et
        if not sayfa_metni or len(sayfa_metni) < 50:
            if "ntv.com.tr" in url: target = soup.find("div", class_="category-detail")
            elif "cumhuriyet.com.tr" in url: target = soup.find("div", class_="article-body")
            elif "haberler.com" in url: target = soup.find("main")
            elif "eurohoops" in url: target = soup.find("div", class_="post-content")
            else: target = None
            
            if target: sayfa_metni = target.get_text(separator=" ", strip=True)
            else:
                ps = soup.find_all('p')
                sayfa_metni = " ".join([p.text.strip() for p in ps if len(p.text.strip()) > 30])

        sayfa_metni = sayfa_metni[:4000] if sayfa_metni else ""
        print(f"📄 Okunan Metin: {len(sayfa_metni)} karakter")
    except Exception as e: print(f"Site Hatası: {e}")
    return media_id, sayfa_metni

def spor_kategorisi_bul(metin):
    m = metin.lower()
    if any(x in m for x in ["voleybol", "sultanlar", "filenin"]): return "#Voleybol"
    if any(x in m for x in ["basketbol", "nba", "euroleague"]): return "#Basketbol"
    if any(x in m for x in ["f1", "formula", "yarış"]): return "#F1"
    return "#Futbol"

# --- ÖZELLİK 1: TARİHTE BUGÜN ---
def gorev_tarihte_bugun():
    print("📜 Tarihte Bugün Hazırlanıyor...")
    try:
        simdi = datetime.datetime.now()
        aylar = {
            1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
            7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
        }
        tarih_str = f"{simdi.day} {aylar[simdi.month]}"
        
        prompt = f"""
        Bugün günlerden {tarih_str}.
        Spor tarihinde bugün yaşanmış (geçmiş yıllarda) Türk futbolu (GS, FB, BJK) veya dünya futboluyla ilgili EFSANEVİ, DUYGUSAL veya REKOR içeren tek bir olayı seç.
        
        Bunu Twitter için 'Tarihte Bugün' konseptiyle anlat.
        - Duygusal ve etkileyici bir dil kullan.
        - Asla yarım cümle bırakma.
        - #TarihteBugün ve #PublikSpor hashtaglerini kullan.
        - Link verme.
        """
        
        tweet = ai_tweet_yaz(prompt)
        
        if tweet:
            client.create_tweet(text=tweet)
            print(f"📜 Tarihte Bugün Atıldı: {tarih_str}")
            bildirim_gonder("Tarihte Bugün", tweet)
    except Exception as e:
        print(f"Tarihte Bugün Hatası: {e}")

# --- ÖZELLİK 2: DERBİ GÜNÜ MODU ---
def gorev_derbi_kontrol():
    print("🔥 Derbi Kontrolü Yapılıyor...")
    try:
        today = datetime.datetime.now().strftime('%Y%m%d')
        # Sadece Süper Lig'e bakmak yeterli
        url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/tur.1/scoreboard?dates={today}"
        r = requests.get(url, timeout=10).json()
        
        buyukler = ["FENERBAHÇE", "GALATASARAY", "BEŞİKTAŞ", "TRABZONSPOR"]
        events = r.get('events', [])
        
        if not events: return

        for mac in events:
            ev = mac['competitions'][0]['competitors'][0]['team']['displayName'].upper()
            dep = mac['competitions'][0]['competitors'][1]['team']['displayName'].upper()
            
            # Eğer iki takım da "Büyükler" listesindeyse, bu bir derbidir.
            if any(b in ev for b in buyukler) and any(b in dep for b in buyukler):
                print(f"🚨 DERBİ TESPİT EDİLDİ: {ev} vs {dep}")
                
                prompt = f"""
                Bugün Türkiye Süper Ligi'nde dev bir derbi var: {ev} vs {dep}.
                Bu maç için Twitter'da paylaşılacak, taraftarları heyecanlandıracak bir metin hazırla.
                
                İÇERİK KURALLARI:
                1. Bu iki takımın rekabet tarihine kısaca değin (Yaklaşık kaç kez karşılaştılar, kim daha çok kazandı? Bilmiyorsan genel rekabetten bahset).
                2. Geçmişten UNUTULMAZ bir anıyı veya efsane bir oyuncuyu (Hagi, Alex, Sergen, Şota vb.) hatırlat.
                3. Takipçilere etkileşim sorusu sor (Örn: "Sizin unutamadığınız o maç hangisi?", "Skor tahmininiz ne?").
                4. Asla yarım cümle bırakma.
                5. Link verme.
                6. Hashtagler: #Derbi #{ev.replace(' ','')}v{dep.replace(' ','')} #SüperLig #PublikSpor
                """
                
                tweet = ai_tweet_yaz(prompt)
                
                if tweet:
                    client.create_tweet(text=tweet)
                    print("🔥 Derbi Tweeti Atıldı!")
                    bildirim_gonder("DERBİ GÜNÜ!", f"{ev} vs {dep}")
                    
    except Exception as e:
        print(f"Derbi Modu Hatası: {e}")

# --- HABER TARAMASI (PROMPT GÜNCELLENDİ) ---
def gorev_haber_taramasi():
    print(f"📰 [{turkiye_saati()}] Haberler Taranıyor...")
    for url in RSS_KAYNAKLARI:
        try:
            feed = feedparser.parse(requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).content)
            for haber in feed.entries[:2]:
                if hasattr(haber, 'published_parsed') and not haber_taze_mi(haber.published_parsed): continue
                
                baslik = haber.title; link = haber.link
                if not log_kontrol(link):
                    if any(x.lower() in baslik.lower() for x in VIP_ANAHTARLAR):
                        print(f"🆕 Haber: {baslik}")
                        baslik_temiz = clickbait_temizle(baslik)
                        media_id, site_icerigi = siteyi_analiz_et(link)
                        kategori = spor_kategorisi_bul(baslik_temiz + site_icerigi)
                        
                        # --- YENİLENMİŞ NET GAZETECİ PROMPTU ---
                        prompt = f"""
                        Sen araştırmacı bir spor gazetecisisin.
                        Aşağıdaki haberi Twitter için yazacaksın.
                        
                        BAŞLIK: {baslik_temiz}
                        İÇERİK: {site_icerigi}
                        
                        GÖREVLERİN (KESİN UYULACAK):
                        1. Eğer başlık bir soru soruyorsa (Örn: "Icardi'ye kim talip?", "O isim geliyor mu?") cevabı metnin içinden bul ve TWEETİN İLK CÜMLESİNE yaz.
                        2. Asla okuyucuyu merakta bırakma. "İşte o isim", "Detaylar haberde" gibi ifadeler KULLANMA.
                        3. İsimleri, rakamları ve takımları net ver. (Örn: "Beşiktaş, Trabzonspor'u yendi" yerine "Beşiktaş, Trabzonspor'u 2-0 yendi.")
                        4. Başlıkta 'Kötü haber', 'Sürpriz' gibi ifadeler varsa, bunun ne olduğunu açıkla.
                        5. Resmi, ciddi ama akıcı ol. Asla yarım cümle bırakma.
                        """
                        # ------------------------------------
                        
                        metin = ai_tweet_yaz(prompt)
                        
                        if not metin: 
                            print("⚠️ AI yanıt vermedi, başlık kullanılıyor.")
                            metin = baslik_temiz
                        
                        zaman = turkiye_saati()
                        hashtag = "#PublikSpor" 
                        if "voleybol" in kategori.lower(): hashtag += " #Voleybol"
                        elif "basketbol" in kategori.lower(): hashtag += " #Basketbol"
                        elif "f1" in kategori.lower(): hashtag += " #F1"
                        else: hashtag += " #Futbol"

                        # Link YOK
                        tweet = f"{metin}\n\n{hashtag}\n⏱ {zaman}"
                        
                        try:
                            if media_id: client.create_tweet(text=tweet, media_ids=[media_id])
                            else: client.create_tweet(text=tweet)
                            print(f"🐦 Tweet Atıldı: {metin[:30]}...")
                            bildirim_gonder("Haber", f"{metin}")
                            log_kaydet(link)
                            time.sleep(60)
                        except Exception as e: 
                            print(f"🔴 Hata: {e}")
                            log_kaydet(link)
                            if "429" in str(e): time.sleep(900)
        except: pass

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
    print(f"⚽ [{turkiye_saati()}] Skorlar...")
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
                        tag = mac_hashtag(ev_ad, dep_ad)
                        tweet = f"⚽ GOL! {ev_ad} {skor} {dep_ad} #PublikSpor {tag}"
                        try: 
                            client.create_tweet(text=tweet)
                            print(f"🚨 GOL: {skor}")
                            bildirim_gonder("GOL!", f"{ev_ad} {skor} {dep_ad}", "high")
                        except: pass
                    
                    if durum == 'post':
                        ms_key = f"MS_{mac_id}"
                        if not log_kontrol(ms_key):
                            try:
                                ev_wl = ev['team']['logos'][0]['href'] if ev['team'].get('logos') else None
                                dep_wl = dep['team']['logos'][0]['href'] if dep['team'].get('logos') else None
                                img_dosya = mac_sonucu_gorseli_olustur(ev_ad, dep_ad, skor, ev_wl, dep_wl)
                                media = api.media_upload(img_dosya)
                                yorum = ai_tweet_yaz(f"Maç bitti: {ev_ad} {skor} {dep_ad}. Kazananı öv.")
                                if not yorum: yorum = "Maç sona erdi."
                                tag = mac_hashtag(ev_ad, dep_ad)
                                text = f"🏁 MAÇ SONUCU\n\n{ev_ad} {skor} {dep_ad}\n\n🗣️ {yorum}\n#PublikSpor {tag}"
                                client.create_tweet(text=text, media_ids=[media.media_id])
                                log_kaydet(ms_key)
                                print(f"🏁 MS Görseli Paylaşıldı: {skor}")
                                bildirim_gonder("Maç Bitti", f"{ev_ad} {skor} {dep_ad}")
                                os.remove(img_dosya)
                            except Exception as e: print(f"MS Hatası: {e}")
                SKOR_HAFIZASI[mac_id] = skor
        except: pass

# --- WEB SERVER (RENDER İÇİN) ---
app = Flask(__name__)
@app.route('/')
def home(): return "PublikSpor V41 Online 🚀"
def run_flask(): app.run(host='0.0.0.0', port=10000)

# --- BAŞLAT ---
def programi_baslat():
    print("🌍 PUBLIKSPOR V41 (NET GAZETECİ MODU) Başlatıldı...")
    bildirim_gonder("Sistem Başladı", "Bot başarıyla aktif oldu.", "high")
    t = threading.Thread(target=run_flask)
    t.daemon = True; t.start()
    
    gorev_haber_taramasi()
    
    schedule.every(5).minutes.do(gorev_haber_taramasi)
    schedule.every(1).minutes.do(gorev_canli_skor)
    schedule.every().friday.at("09:00").do(gorev_fikstur_paylas)
    schedule.every().day.at("12:00").do(gorev_tarihte_bugun) # Her gün 12:00
    schedule.every().day.at("10:00").do(gorev_derbi_kontrol) # Her gün 10:00
    
    while True:
        try: schedule.run_pending(); time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Bot durduruldu.")
            break
        except Exception as e:
            print(f"Ana Döngü Hatası: {e}")
            time.sleep(60)

if __name__ == "__main__":
    programi_baslat()