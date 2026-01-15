import requests
from bs4 import BeautifulSoup
import time
import datetime
import telebot
import re
import pytz
import os

# إعدادات البوت
TOKEN = os.environ.get('TELEGRAM_TOKEN', '8566644337:AAHA1kwjhaUYPrrFiupYy0yssDoz5OmRyG0')
CHANNEL_ID = '@FarawlaShop'
bot = telebot.TeleBot(TOKEN)

# إعدادات فيسبوك
FB_PAGE_ACCESS_TOKEN = os.environ.get('FB_PAGE_ACCESS_TOKEN', '')
FB_PAGE_ID = os.environ.get('FB_PAGE_ID', '61584349121096')
FB_GROUP_ID = os.environ.get('FB_GROUP_ID', '1886606601759050')

def get_data():
    url = "https://sp-today.com/ar/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')
        data = {'currencies': [], 'gold': [], 'fuel': []}

        # استخراج العملات
        target_currencies = {
            'USD': 'دولار أمريكي',
            'EUR': 'يورو',
            'TRY': 'ليرة تركية',
            'SAR': 'ريال سعودي',
            'AED': 'درهم إماراتي',
            'EGP': 'جنيه مصري'
        }
        
        links = soup.find_all('a')
        found_codes = set()
        usd_sell_price = 14800 # قيمة افتراضية تقريبية
        
        for link in links:
            text = link.get_text(separator="|").strip()
            parts = [p.strip() for p in text.split('|') if p.strip()]
            
            for code, name in target_currencies.items():
                if code in parts and code not in found_codes:
                    prices = []
                    for p in parts:
                        clean_p = p.replace(',', '')
                        if clean_p.replace('.', '').isdigit():
                            prices.append(p)
                    
                    if len(prices) >= 2:
                        data['currencies'].append({
                            'code': code,
                            'name': name,
                            'buy': prices[0],
                            'sell': prices[1]
                        })
                        found_codes.add(code)
                        if code == 'USD':
                            usd_sell_price = float(prices[1].replace(',', ''))

        data['usd_rate'] = usd_sell_price

        # استخراج الذهب
        for link in links:
            text = link.get_text(separator="|").strip()
            parts = [p.strip() for p in text.split('|') if p.strip()]
            if '21K' in parts and len(parts) >= 5:
                data['gold'].append({'name': 'عيار 21', 'price_syp': parts[4], 'price_usd': parts[2].replace('$', '')})
            elif '18K' in parts and len(parts) >= 5:
                data['gold'].append({'name': 'عيار 18', 'price_syp': parts[4], 'price_usd': parts[2].replace('$', '')})
            elif 'أونصة الذهب' in text:
                match = re.search(r'\$(\d+[\d,.]*)', text)
                if match: data['gold_ounce'] = match.group(1)

        # تثبيت أسعار المحروقات (آخر تسعيرة معروفة)
        fuel_defaults = [
            {'name': 'بنزين', 'price_usd': 0.85},
            {'name': 'مازوت', 'price_usd': 0.75},
            {'name': 'غاز', 'price_usd': 10.50}
        ]
        
        for f in fuel_defaults:
            price_syp = f['price_usd'] * usd_sell_price
            data['fuel'].append({
                'name': f['name'],
                'price_syp': f"{price_syp:,.0f}",
                'price_usd': f"{f['price_usd']:.2f}"
            })

        syria_tz = pytz.timezone('Asia/Damascus')
        now_syria = datetime.datetime.now(syria_tz)
        data['date'] = now_syria.strftime("%Y-%m-%d | %I:%M %p")
        return data
    except Exception as e:
        print(f"Error: {e}")
        return None

def format_msg(data):
    def calc_new(val_str):
        try:
            val = float(val_str.replace(',', ''))
            return f"{val/100:,.2f}"
        except: return "0.00"

    msg = "🇸🇾 *نشرة أسعار الصرف والذهب في سوريا* 🇸🇾\n"
    msg += f"⏰ \`{data['date']}\` (توقيت دمشق)\n\n"
    
    if data['currencies']:
        msg += "💰 *أسعار العملات (شراء | مبيع):*\n"
        msg += "━━━━━━━━━━━━━━━━━━\n"
        for c in data['currencies']:
            msg += f"🔹 *{c['name']} ({c['code']}):*\n"
            msg += f"  - ليرة قديمة: {c['buy']} | {c['sell']}\n"
            msg += f"  - ليرة جديدة: \`{calc_new(c['buy'])}\` | \`{calc_new(c['sell'])}\` ✨\n\n"
    
    if data['gold'] or 'gold_ounce' in data:
        msg += "✨ *أسعار الذهب:*\n"
        msg += "━━━━━━━━━━━━━━━━━━\n"
        for g in data['gold']:
            msg += f"🔸 *{g['name']}:*\n"
            msg += f"  - ليرة قديمة: {g['price_syp']} ل.س\n"
            msg += f"  - ليرة جديدة: \`{calc_new(g['price_syp'])}\` ل.س\n"
            msg += f"  - بالدولار: \`\${g['price_usd']}\`\n\n"
        if 'gold_ounce' in data:
            msg += f"🌍 أونصة الذهب: \`\${data['gold_ounce']}\`\n\n"
    
    if data['fuel']:
        msg += "⛽ *المحروقات والطاقة:*\n"
        msg += "━━━━━━━━━━━━━━━━━━\n"
        for f in data['fuel']:
            msg += f"🔹 *{f['name']}:*\n"
            msg += f"  - ليرة قديمة: {f['price_syp']} ل.س\n"
            msg += f"  - ليرة جديدة: \`{calc_new(f['price_syp'])}\` ل.س\n"
            msg += f"  - بالدولار: \`\${f['price_usd']}\`\n\n"
    
    msg += "📢 *تابعونا عبر منصاتنا:*\n"
    msg += "━━━━━━━━━━━━━━━━━━\n\n"
    msg += "🔗 *تلجرام:*\nhttps://t.me/FarawlaShop\n\n"
    msg += "🔗 *واتساب:*\nhttps://whatsapp.com/channel/0029VaQSQveCRs1vibyRZp3A\n\n"
    msg += "🔗 *فيسبوك:*\nhttps://www.facebook.com/profile.php?id=61584349121096\n\n"
    msg += "━━━━━━━━━━━━━━━━━━"
    return msg

def format_fb_msg(data):
    """تنسيق الرسالة لفيسبوك (بدون Markdown)"""
    def calc_new(val_str):
        try:
            val = float(val_str.replace(',', ''))
            return f"{val/100:,.2f}"
        except: return "0.00"

    msg = "🇸🇾 نشرة أسعار الصرف والذهب في سوريا 🇸🇾\n"
    msg += f"⏰ {data['date']} (توقيت دمشق)\n\n"
    
    if data['currencies']:
        msg += "💰 أسعار العملات (شراء | مبيع):\n"
        msg += "━━━━━━━━━━━━━━━━━━\n"
        for c in data['currencies']:
            msg += f"🔹 {c['name']} ({c['code']}):\n"
            msg += f"  - ليرة قديمة: {c['buy']} | {c['sell']}\n"
            msg += f"  - ليرة جديدة: {calc_new(c['buy'])} | {calc_new(c['sell'])} ✨\n\n"
    
    if data['gold'] or 'gold_ounce' in data:
        msg += "✨ أسعار الذهب:\n"
        msg += "━━━━━━━━━━━━━━━━━━\n"
        for g in data['gold']:
            msg += f"🔸 {g['name']}:\n"
            msg += f"  - ليرة قديمة: {g['price_syp']} ل.س\n"
            msg += f"  - ليرة جديدة: {calc_new(g['price_syp'])} ل.س\n"
            msg += f"  - بالدولار: ${g['price_usd']}\n\n"
        if 'gold_ounce' in data:
            msg += f"🌍 أونصة الذهب: ${data['gold_ounce']}\n\n"
    
    if data['fuel']:
        msg += "⛽ المحروقات والطاقة:\n"
        msg += "━━━━━━━━━━━━━━━━━━\n"
        for f in data['fuel']:
            msg += f"🔹 {f['name']}:\n"
            msg += f"  - ليرة قديمة: {f['price_syp']} ل.س\n"
            msg += f"  - ليرة جديدة: {calc_new(f['price_syp'])} ل.س\n"
            msg += f"  - بالدولار: ${f['price_usd']}\n\n"
    
    msg += "📢 تابعونا عبر منصاتنا:\n"
    msg += "━━━━━━━━━━━━━━━━━━\n\n"
    msg += "🔗 تلجرام:\nhttps://t.me/FarawlaShop\n\n"
    msg += "🔗 واتساب:\nhttps://whatsapp.com/channel/0029VaQSQveCRs1vibyRZp3A\n\n"
    msg += "🔗 فيسبوك:\nhttps://www.facebook.com/profile.php?id=61584349121096\n\n"
    msg += "━━━━━━━━━━━━━━━━━━"
    return msg

def publish_to_telegram(message):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            bot.send_message(CHANNEL_ID, message, parse_mode='Markdown', disable_web_page_preview=True)
            print("✅ Telegram: Success!")
            return True
        except Exception as e:
            print(f"❌ Telegram Error (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
    return False

def publish_to_facebook_page(message):
    if not FB_PAGE_ACCESS_TOKEN:
        print("⚠️ Facebook Page: No access token provided, skipping...")
        return False
    try:
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/feed"
        payload = {'message': message, 'access_token': FB_PAGE_ACCESS_TOKEN}
        response = requests.post(url, data=payload, timeout=30)
        if response.status_code == 200:
            print("✅ Facebook Page: Success!")
            return True
        else:
            print(f"❌ Facebook Page Error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Facebook Page Error: {e}")
        return False

def publish_to_facebook_group(message):
    if not FB_PAGE_ACCESS_TOKEN:
        print("⚠️ Facebook Group: No access token provided, skipping...")
        return False
    try:
        url = f"https://graph.facebook.com/v18.0/{FB_GROUP_ID}/feed"
        payload = {'message': message, 'access_token': FB_PAGE_ACCESS_TOKEN}
        response = requests.post(url, data=payload, timeout=30)
        if response.status_code == 200:
            print("✅ Facebook Group: Success!")
            return True
        else:
            print(f"❌ Facebook Group Error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Facebook Group Error: {e}")
        return False

def main():
    print("🚀 Starting update...")
    data = get_data()
    if data and data['currencies']:
        telegram_message = format_msg(data)
        publish_to_telegram(telegram_message)
        facebook_message = format_fb_msg(data)
        publish_to_facebook_page(facebook_message)
        publish_to_facebook_group(facebook_message)
        print("\n✅ All publishing tasks completed!")
    else:
        print("❌ No data found.")

if __name__ == "__main__":
    main()
