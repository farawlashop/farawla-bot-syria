import os
import logging
import asyncio
import requests
from bs4 import BeautifulSoup
from telegram import Bot
from datetime import datetime
import re

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# الإعدادات
TOKEN = "7990500630:AAGtX2lQz2VU3KWtGlP4_hzrZcaMATo-At8"
CHANNEL_ID = "@FarawlaShop"
URL = "https://sp-today.com/"

# ذاكرة لتخزين آخر الأسعار المنشورة لتجنب التكرار
last_prices = {}

def get_data():
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(URL, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        data = {
            'currencies': [],
            'gold': {},
            'fuel': {},
            'timestamp': datetime.now().strftime("%Y-%m-%d | %I:%M %p")
        }

        # استخراج العملات
        currency_elements = soup.find_all('a', href=re.compile(r'/currency/'))
        for el in currency_elements:
            text = el.get_text(separator=' ', strip=True)
            parts = text.split()
            if len(parts) >= 4:
                code = parts[0]
                prices = [p.replace(',', '') for p in parts if re.match(r'^\d{1,3}(,\d{3})*$', p)]
                if len(prices) >= 2:
                    data['currencies'].append({
                        'code': code,
                        'buy': prices[0],
                        'sell': prices[1]
                    })

        # استخراج الذهب
        gold_links = soup.find_all('a', href=re.compile(r'/gold'))
        for link in gold_links:
            text = link.get_text(separator=' ', strip=True)
            if '21K' in text:
                nums = re.findall(r'[\d,.]+', text)
                if len(nums) >= 5:
                    data['gold']['21'] = {'usd': nums[2], 'syp': nums[3].replace(',', '')}
            elif '18K' in text:
                nums = re.findall(r'[\d,.]+', text)
                if len(nums) >= 5:
                    data['gold']['18'] = {'usd': nums[2], 'syp': nums[3].replace(',', '')}
            elif 'أونصة' in text:
                match = re.search(r'\$([\d,.]+)', text)
                if match: data['gold']['ounce'] = match.group(1)

        # استخراج المحروقات - تحسين البحث
        energy_links = soup.find_all('a', href=re.compile(r'/energy'))
        for link in energy_links:
            text = link.get_text(separator=' ', strip=True)
            price_match = re.search(r'\$([\d.]+)', text)
            if price_match:
                price = price_match.group(1)
                if 'بنزين' in text: data['fuel']['gasoline'] = price
                elif 'مازوت' in text: data['fuel']['diesel'] = price
                elif 'غاز' in text: data['fuel']['gas'] = price

        return data
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return None

def format_message(data):
    usd_sell = 12020
    for c in data['currencies']:
        if c['code'] == 'USD':
            usd_sell = float(c['sell'])
            break

    msg = f"🇸🇾 نشرة أسعار الصرف والذهب في سوريا 🇸🇾\n"
    msg += f"⏰ {data['timestamp']} (توقيت دمشق)\n\n"
    
    msg += f"💰 أسعار العملات (شراء | مبيع):\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    
    main_currencies = {
        'USD': 'الدولار الأمريكي', 'EUR': 'اليورو', 'TRY': 'الليرة التركية',
        'SAR': 'الريال السعودي', 'AED': 'الدرهم الإماراتي', 'EGP': 'الجنيه المصري'
    }
    
    added_codes = set()
    for c in data['currencies']:
        if c['code'] in main_currencies and c['code'] not in added_codes:
            buy_old = int(c['buy'])
            sell_old = int(c['sell'])
            msg += f"🔹 {main_currencies[c['code']]}:\n"
            msg += f"  - ليرة قديمة: {buy_old:,} | {sell_old:,}\n"
            msg += f"  - ليرة جديدة: {buy_old/100:,.2f} | {sell_old/100:,.2f} ✨\n"
            added_codes.add(c['code'])

    msg += f"\n🌍 بقية العملات:\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    
    other_currencies = {
        'LYD': 'ليبيا', 'JOD': 'الأردن', 'KWD': 'الكويت', 'GBP': 'بريطانيا',
        'QAR': 'قطر', 'BHD': 'البحرين', 'SEK': 'السويد', 'CAD': 'كندا',
        'OMR': 'عمان', 'NOK': 'النرويج', 'DKK': 'الدنمارك', 'DZD': 'الجزائر',
        'MAD': 'المغرب', 'TND': 'تونس', 'RUB': 'روسيا', 'MYR': 'ماليزيا',
        'BRL': 'البرازيل', 'NZD': 'نيوزيلندا', 'CHF': 'سويسرا', 'AUD': 'أستراليا',
        'ZAR': 'جنوب أفريقيا', 'IQD': 'العراق', 'IRR': 'إيران', 'SGD': 'سنغافورة'
    }

    for c in data['currencies']:
        if c['code'] in other_currencies and c['code'] not in added_codes:
            buy_old = int(c['buy'])
            sell_old = int(c['sell'])
            msg += f"🔸 {other_currencies[c['code']]}:\n"
            msg += f"  - ليرة قديمة: {buy_old:,} | {sell_old:,}\n"
            msg += f"  - ليرة جديدة: {buy_old/100:,.2f} | {sell_old/100:,.2f}\n"
            msg += f"  - سعر دولار: {(buy_old/usd_sell):,.2f} $\n"
            added_codes.add(c['code'])

    msg += f"\n✨ أسعار الذهب:\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    if '21' in data['gold']:
        syp_old = int(data['gold']['21']['syp'])
        msg += f"🔸 عيار 21:\n"
        msg += f"  - ليرة قديمة: {syp_old:,} ل.س\n"
        msg += f"  - ليرة جديدة: {syp_old/100:,.2f} ل.س\n"
        msg += f"  - بالدولار: ${data['gold']['21']['usd']}\n"
    if '18' in data['gold']:
        syp_old = int(data['gold']['18']['syp'])
        msg += f"🔸 عيار 18:\n"
        msg += f"  - ليرة قديمة: {syp_old:,} ل.س\n"
        msg += f"  - ليرة جديدة: {syp_old/100:,.2f} ل.س\n"
        msg += f"  - بالدولار: ${data['gold']['18']['usd']}\n"
    if 'ounce' in data['gold']:
        msg += f"\n🌍 أونصة الذهب: ${data['gold']['ounce']}\n"

    msg += f"\n⛽ المحروقات والطاقة:\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    fuel_names = {'gasoline': 'بنزين', 'diesel': 'مازوت', 'gas': 'غاز'}
    for key, name in fuel_names.items():
        if key in data['fuel']:
            p_usd = float(data['fuel'][key])
            p_old = int(p_usd * usd_sell)
            msg += f"🔹 سعر {name}:\n"
            msg += f"  - ليرة قديمة: {p_old:,} ل.س\n"
            msg += f"  - ليرة جديدة: {p_old/100:,.2f} ل.س\n"
            msg += f"  - بالدولار: ${p_usd:.2f}\n"

    msg += f"\n📢 تابعونا عبر منصاتنا:\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"🔗 تلجرام: \n\n https://t.me/FarawlaShop \n\n\n"
    msg += f"🔗 واتساب: \n\n https://whatsapp.com/channel/0029VaQSQveCRs1vibyRZp3A \n\n\n"
    msg += f"🔗 فيسبوك: \n\n https://www.facebook.com/profile.php?id=61584349121096 \n"

    return msg

async def main():
    bot = Bot(token=TOKEN)
    global last_prices
    logger.info("Bot started...")
    
    while True:
        data = get_data()
        if data and data['currencies']:
            current_state = {c['code']: c['sell'] for c in data['currencies']}
            current_state['g21'] = data['gold'].get('21', {}).get('syp')
            current_state['fuel'] = str(data['fuel'])
            
            if current_state != last_prices:
                logger.info("Prices changed, sending update...")
                message = format_message(data)
                try:
                    await bot.send_message(chat_id=CHANNEL_ID, text=message, disable_web_page_preview=True)
                    last_prices = current_state
                    logger.info("Message sent successfully.")
                except Exception as e:
                    logger.error(f"Failed to send message: {e}")
            else:
                logger.info("No change in prices.")
        else:
            logger.warning("Failed to fetch data or data is empty.")
        
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main())
