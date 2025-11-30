import requests
import datetime

LIGLER = {
    "SUPER_LIG": "http://site.api.espn.com/apis/site/v2/sports/soccer/tur.1/scoreboard",
    "UCL": "http://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard",
}

LOG_DOSYASI = "paylasilanlar.txt"

def temizlik_yap():
    print("🧹 Geçmiş maçlar temizleniyor...")
    count = 0
    
    # Dosya yoksa oluştur
    if not os.path.exists(LOG_DOSYASI):
        with open(LOG_DOSYASI, "w") as f: pass

    # Mevcut logları oku
    with open(LOG_DOSYASI, "r", encoding="utf-8") as f:
        mevcut_loglar = f.read()

    for lig, url in LIGLER.items():
        try:
            r = requests.get(url).json()
            for mac in r.get('events', []):
                durum = mac['status']['type']['state']
                
                # Sadece BİTMİŞ (post) maçları bul
                if durum == 'post':
                    mac_id = mac['id']
                    ms_key = f"MS_{mac_id}"
                    
                    # Eğer log dosyasında yoksa ekle (Tweet atmadan!)
                    if ms_key not in mevcut_loglar:
                        ev = mac['competitions'][0]['competitors'][0]['team']['displayName']
                        dep = mac['competitions'][0]['competitors'][1]['team']['displayName']
                        
                        with open(LOG_DOSYASI, "a", encoding="utf-8") as f:
                            f.write(ms_key + "\n")
                        
                        print(f"✅ İşaretlendi (Atlanacak): {ev} vs {dep}")
                        count += 1
        except: pass
    
    if count == 0:
        print("🎉 Zaten her şey güncel. Temizlenecek bir şey yok.")
    else:
        print(f"🏁 Toplam {count} eski maç temizlendi.")

import os
if __name__ == "__main__":
    temizlik_yap()