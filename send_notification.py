import requests

TOKEN = "8357883858:AAEt_Csdcft7Obzv85J15F3WaYsXiZJ-FfQ"
CHAT_ID = "-4537586641"  # ID твоей группы

def send_telegram_notification(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": text
    }

    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Ошибка отправки в Telegram:", e)
