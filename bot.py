import webbrowser
import urllib.parse
import os

# --- GENEL AYARLAR ---
MARKA_SLOGANI = "Laf kalabalığı yok. Sadece gerçekler."
STANDART_TAGLER = "#PublikSpor"

def terminali_temizle():
    os.system('cls' if os.name == 'nt' else 'clear')

def icerik_analiz_et(metin):
    """
    Girilen metni tarar, içeriğin türünü (Gol, Transfer, Kart vb.) tespit eder.
    Buna göre Başlık, Emoji ve Ekstra Hashtagler üretir.
    """
    metin_kucuk = metin.lower()
    
    # --- MÜHENDİSLİK: DURUM TESPİT ALGORİTMASI ---
    # Öncelik sırasına göre kontrol ediyoruz:
    
    if "gol" in metin_kucuk or "goool" in metin_kucuk:
        baslik = "⚽ GOOOLL!"
        ozel_tag = "#Gol"
    
    elif any(x in metin_kucuk for x in ["kırmızı kart", "atıldı", "ihraç"]):
        baslik = "🟥 KIRMIZI KART"
        ozel_tag = "#KırmızıKart"
        
    elif "sarı kart" in metin_kucuk:
        baslik = "🟨 SARI KART"
        ozel_tag = "#SarıKart"
        
    elif any(x in metin_kucuk for x in ["transfer", "imza", "anlaştı", "kap"]):
        baslik = "✍️ TRANSFER GELİŞMESİ"
        ozel_tag = "#Transfer"
        
    elif any(x in metin_kucuk for x in ["sakatlık", "sakatlandı", "tedavi"]):
        baslik = "🚑 SAKATLIK HABERİ"
        ozel_tag = "#Sakatlık"
        
    elif any(x in metin_kucuk for x in ["bitti", "sonucu", "ms", "iy"]):
        baslik = "🏁 MAÇ SONUCU"
        ozel_tag = "#MaçSonucu"
        
    elif any(x in metin_kucuk for x in ["penaltı", "var inceleme"]):
        baslik = "VAR KARARI / PENALTI"
        ozel_tag = "#VAR"
        
    else:
        # Hiçbiri değilse genel sıcak gelişme
        baslik = "🚨 SICAK GELİŞME"
        ozel_tag = "#SporGündemi"

    return baslik, ozel_tag

def tweet_olustur(ham_metin):
    # 1. İçeriği Analiz Et
    baslik, ozel_tag = icerik_analiz_et(ham_metin)
    
    # 2. Şablonu Giydir
    tweet = f"""{baslik}

{ham_metin}

🔗 {MARKA_SLOGANI}
{STANDART_TAGLER} {ozel_tag}"""
    
    return tweet

def twitteri_ac(tweet_metni):
    encoded_text = urllib.parse.quote(tweet_metni)
    url = f"https://twitter.com/intent/tweet?text={encoded_text}"
    print("✅ Twitter açılıyor...")
    webbrowser.open(url)

# --- ANA PROGRAM ---
if __name__ == "__main__":
    terminali_temizle()
    print("📢 PUBLIKSPOR AKILLI İÇERİK MOTORU")
    print("-------------------------------------")
    print("Örnekler:")
    print("- Rizespor 2-0 yaptı (Gol algılar)")
    print("- Fred sarı kart gördü (Kart algılar)")
    print("- Osimhen Galatasaray'da (Transfer algılar)")
    print("-------------------------------------")
    
    while True:
        giris = input("\nGelişmeyi yaz (Çıkış: 'q'): ")
        
        if giris.lower() == 'q':
            break
            
        # Tweeti hazırla
        hazir_tweet = tweet_olustur(giris)
        
        print("\n--- ÖNİZLEME ---")
        print(hazir_tweet)
        print("----------------")
        
        secim = input("Yayınlansın mı? (Enter: Evet / h: Hayır): ")
        if secim.lower() != 'h':
            twitteri_ac(hazir_tweet)