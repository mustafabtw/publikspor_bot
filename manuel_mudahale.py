import tweepy

# --- AYNI ŞİFRELER (Botun Yedek Anahtarı) ---
API_KEY = "Ds6HnkJCLvIrHf2ChXgwy47GZ"
API_SECRET = "2ITh94OlZ1OYhsnG5XkU9Ot2fEIE4pZVXwF6opp2fl9SnJ8Mmo"
ACCESS_TOKEN = "1989860228150788096-k2XifKyI27cbSKKWmCZsNJH1Ypg4wW"
ACCESS_SECRET = "oeRrU4nUR9xfDmR3Sbn26qdcdhjF3uu1xyeMIRmCoZTtb"

def manuel_tweet_at():
    try:
        # Twitter'a Bağlan
        client = tweepy.Client(
            consumer_key=API_KEY,
            consumer_secret=API_SECRET,
            access_token=ACCESS_TOKEN,
            access_token_secret=ACCESS_SECRET
        )
        print("✅ Bağlantı Başarılı! (Manuel Mod)")
        print("-----------------------------------")
        
        while True:
            # Senden metin ister
            metin = input("\nTweet metnini yaz (Çıkış için 'q'): ")
            
            if metin.lower() == 'q':
                break
            
            # Onay ister
            onay = input(f"\n📢 Bu tweet @PublikSpor hesabından paylaşılacak:\n'{metin}'\nOnaylıyor musun? (e/h): ")
            
            if onay.lower() == 'e':
                client.create_tweet(text=metin)
                print("🚀 TWEET GÖNDERİLDİ!")
            else:
                print("❌ İptal edildi.")

    except Exception as e:
        print(f"Hata: {e}")

if __name__ == "__main__":
    manuel_tweet_at()