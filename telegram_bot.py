import requests
from bs4 import BeautifulSoup
import time
import datetime
import telebot
import re
import pytz
import os
import json
import subprocess

# إعدادات البوت
TOKEN = os.environ.get('TELEGRAM_TOKEN', '8566644337:AAHA1kwjhaUYPrrFiupYy0yssDoz5OmRyG0')
CHANNEL_ID = '@FarawlaShop'
bot = telebot.TeleBot(TOKEN)

# إعدادات فيسبوك
FB_PAGE_ACCESS_TOKEN = os.environ.get('FB_PAGE_ACCESS_TOKEN', '')
FB_PAGE_ID = os.environ.get('FB_PAGE_ID', '61584349121096')
FB_GROUP_ID = os.environ.get('FB_GROUP_ID', '1886606601759050')

# إعدادات Blogger و Gmail
BLOGGER_EMAIL = "farawlashop963@blogger.com"

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

        # تثبيت أسعار المحروقات
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
    
    msg += "📢 *تابعونا عبر منصاتنا:*\n"
    msg += "━━━━━━━━━━━━━━━━━━\n\n"
    msg += "🔗 *تلجرام:*\nhttps://t.me/FarawlaShop\n\n"
    msg += "🔗 *فيسبوك:*\nhttps://www.facebook.com/profile.php?id=61584349121096\n\n"
    msg += "━━━━━━━━━━━━━━━━━━"
    return msg

def format_html_msg(data):
    """تنسيق الرسالة لـ Blogger بتنسيق HTML احترافي"""
    def calc_new(val_str):
        try:
            val = float(val_str.replace(',', ''))
            return f"{val/100:,.2f}"
        except: return "0.00"

    html = f"""
    <div dir="rtl" style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #d32f2f; text-align: center;">🇸🇾 نشرة أسعار الصرف والذهب في سوريا 🇸🇾</h2>
        <p style="text-align: center; background: #f5f5f5; padding: 10px; border-radius: 5px;">
            ⏰ <strong>{data['date']}</strong> (توقيت دمشق)
        </p>
        
        <h3 style="border-bottom: 2px solid #d32f2f; padding-bottom: 5px;">💰 أسعار العملات (شراء | مبيع)</h3>
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
            <tr style="background: #fce4ec;">
                <th style="border: 1px solid #ddd; padding: 8px;">العملة</th>
                <th style="border: 1px solid #ddd; padding: 8px;">ليرة قديمة</th>
                <th style="border: 1px solid #ddd; padding: 8px;">ليرة جديدة ✨</th>
            </tr>
    """
    for c in data['currencies']:
        html += f"""
            <tr>
                <td style="border: 1px solid #ddd; padding: 8px;">{c['name']} ({c['code']})</td>
                <td style="border: 1px solid #ddd; padding: 8px;">{c['buy']} | {c['sell']}</td>
                <td style="border: 1px solid #ddd; padding: 8px;">{calc_new(c['buy'])} | {calc_new(c['sell'])}</td>
            </tr>
        """
    html += "</table>"

    if data['gold']:
        html += """
        <h3 style="border-bottom: 2px solid #fbc02d; padding-bottom: 5px;">✨ أسعار الذهب</h3>
        <ul style="list-style: none; padding: 0;">
        """
        for g in data['gold']:
            html += f"""
            <li style="background: #fff9c4; margin-bottom: 10px; padding: 10px; border-radius: 5px; border-right: 5px solid #fbc02d;">
                <strong>{g['name']}:</strong><br>
                ليرة قديمة: {g['price_syp']} ل.س | ليرة جديدة: {calc_new(g['price_syp'])} ل.س | بالدولار: ${g['price_usd']}
            </li>
            """
        html += "</ul>"

    html += """
        <hr>
        <p style="text-align: center;">
            📢 تابعونا عبر منصاتنا:<br>
            <a href="https://t.me/FarawlaShop">تلجرام</a> | 
            <a href="https://www.facebook.com/profile.php?id=61584349121096">فيسبوك</a>
        </p>
    </div>
    """
    return html

def publish_to_blogger(data):
    """النشر على Blogger عبر إرسال بريد إلكتروني من Gmail"""
    subject = f"نشرة أسعار الصرف والذهب في سوريا - {data['date']}"
    content = format_html_msg(data)
    
    # استخدام manus-mcp-cli لإرسال البريد
    mcp_input = {
        "messages": [{
            "to": [BLOGGER_EMAIL],
            "subject": subject,
            "content": content
        }]
    }
    
    try:
        cmd = f"manus-mcp-cli tool call gmail_send_messages --server gmail --input '{json.dumps(mcp_input)}'"
        subprocess.run(cmd, shell=True, check=True)
        print("✅ Blogger: Success via Gmail!")
        return True
    except Exception as e:
        print(f"❌ Blogger Error: {e}")
        return False

def manage_gmail_inbox():
    """فحص البريد الوارد والرد على الاستفسارات ذكياً"""
    try:
        # البحث عن رسائل غير مقروءة
        search_cmd = "manus-mcp-cli tool call gmail_search_messages --server gmail --input '{\"q\": \"is:unread\", \"max_results\": 5}'"
        result = subprocess.check_output(search_cmd, shell=True).decode()
        # (هنا يتم تحليل النتيجة والرد باستخدام GPT-4 في نسخة أكثر تقدماً)
        print("✅ Gmail Inbox checked.")
    except Exception as e:
        print(f"❌ Gmail Management Error: {e}")

def main():
    print("🚀 Starting autonomous update...")
    data = get_data()
    if data and data['currencies']:
        # 1. تلجرام
        telegram_message = format_msg(data)
        publish_to_telegram(telegram_message)
        
        # 2. فيسبوك
        facebook_message = format_msg(data).replace('*', '') # تنظيف بسيط للفيسبوك
        publish_to_facebook_page(facebook_message)
        
        # 3. Blogger (الجديد)
        publish_to_blogger(data)
        
        # 4. إدارة Gmail (الجديد)
        manage_gmail_inbox()
        
        print("\n✅ All autonomous tasks completed!")
    else:
        print("❌ No data found.")

def publish_to_telegram(message):
    try:
        bot.send_message(CHANNEL_ID, message, parse_mode='Markdown', disable_web_page_preview=True)
        print("✅ Telegram: Success!")
    except Exception as e: print(f"❌ Telegram Error: {e}")

def publish_to_facebook_page(message):
    if not FB_PAGE_ACCESS_TOKEN: return
    try:
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/feed"
        payload = {'message': message, 'access_token': FB_PAGE_ACCESS_TOKEN}
        requests.post(url, data=payload, timeout=30)
        print("✅ Facebook: Success!")
    except Exception as e: print(f"❌ Facebook Error: {e}")

if __name__ == "__main__":
    main()
