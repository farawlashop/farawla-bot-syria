import os
import logging
import asyncio
import requests
from bs4 import BeautifulSoup
from telegram import Bot
from datetime import datetime
import re

# إعداد السجلات بشكل احترافي
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# الإعدادات الأساسية
TOKEN = "7990500630:AAGtX2lQz2VU3KWtGlP4_hzrZcaMATo-At8"
CHANNEL_ID = "@FarawlaShop"
URL = "https://sp-today.com/"

# قاموس أسماء الدول والعملات (لإزالة الرموز تماماً)
CURRENCY_NAMES = {
    'USD': 'الدولار الأمريكي',
    'EUR': 'اليورو الأوروبي',
    'TRY': 'الليرة التركية',
    'SAR': 'الريال السعودي',
    'AED': 'الدرهم الإماراتي',
    'EGP': 'الجنيه المصري',
    'GBP': 'الجنيه الإسترليني',
    'JOD': 'الدينار الأردني',
    'KWD': 'الدينار الكويتي',
    'QAR': 'الريال القطري',
    'BHD': 'الدينار البحريني',
    'OMR': 'الريال العماني',
    'LYD': 'الدينار الليبي',
    'IQD': 'الدينار العراقي',
    'CAD': 'الدولار الكندي',
    'AUD': 'الدولار الأسترالي',
    'CHF': 'الفرنك السويسري',
    'SEK': 'الكرونة السويدية',
    'NOK': 'الكرونة النرويجية',
    'DKK': 'الكرونة الدنماركية',
    'RUB': 'الروبل الروسي',
    'DZD': 'الدينار الجزائري',
    'MAD': 'الدرهم المغربي',
    'TND': 'الدينار التونسي',
    'MYR': 'الرينغيت الماليزي',
    'NZD': 'الدولار النيوزيلندي',
    'ZAR': 'الراند الجنوب أفريقي',
    'IRR': 'الريال الإيراني',
    'SGD': 'الدولار السنغافوري',
    'BRL': 'الريال البرازيلي'
}

# ذاكرة لتخزين آخر الأسعار المنشورة
last_prices = {}

def clean_number(text):
    """تنظيف الأرقام من الفواصل والرموز"""
    try:
        return float(re.sub(r'[^\d.]', '', text.replace(',', '')))
    except:
        return 0.0

def get_data():
    """جلب البيانات من الموقع وتنظيمها في هيكل بيانات ثابت"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(URL, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        data = {
            'main_currencies': [],
            'other_currencies': [],
            'gold': {},
            'fuel': {},
            'timestamp': datetime.now().strftime("%Y-%m-%d | %I:%M %p")
        }

        # 1. استخراج العملات
        currency_elements = soup.find_all('a', href=re.compile(r'/currency/'))
        usd_sell = 12020.0 # قيمة افتراضية في حال الفشل
        
        for el in currency_elements:
            text = el.get_text(separator=' ', strip=True)
            parts = text.split()
            if len(parts) >= 4:
                code = parts[0].upper()
                if code in CURRENCY_NAMES:
                    # البحث عن أول رقمين يمثلان الشراء والمبيع
                    prices = [p for p in parts if re.match(r'^\d{1,3}(,\d{3})*(\.\d+)?$', p)]
                    if len(prices) >= 2:
                        buy = clean_number(prices[0])
                        sell = clean_number(prices[1])
                        
                        item = {
                            'name': CURRENCY_NAMES[code],
                            'code': code,
                            'buy': buy,
                            'sell': sell
                        }
                        
                        if code == 'USD': usd_sell = sell
                        
                        if code in ['USD', 'EUR', 'TRY', 'SAR', 'AED', 'EGP']:
                            data['main_currencies'].append(item)
                        else:
                            data['other_currencies'].append(item)

        # 2. استخراج الذهب
        gold_links = soup.find_all('a', href=re.compile(r'/gold'))
        for link in gold_links:
            text = link.get_text(separator=' ', strip=True)
            nums = re.findall(r'[\d,.]+', text)
            if '21K' in text and len(nums) >= 5:
                data['gold']['21'] = {'usd': nums[2], 'syp': clean_number(nums[3])}
            elif '18K' in text and len(nums) >= 5:
                data['gold']['18'] = {'usd': nums[2], 'syp': clean_number(nums[3])}
            elif 'أونصة' in text:
                match = re.search(r'\$([\d,.]+)', text)
                if match: data['gold']['ounce'] = match.group(1)

        # 3. استخراج المحروقات
        energy_links = soup.find_all('a', href=re.compile(r'/energy'))
        for link in energy_links:
            text = link.get_text(separator=' ', strip=True)
            price_match = re.search(r'\$([\d.]+)', text)
            if price_match:
                price_usd = float(price_match.group(1))
                if 'بنزين' in text: data['fuel']['بنزين'] = price_usd
                elif 'مازوت' in text: data['fuel']['مازوت'] = price_usd
                elif 'غاز' in text: data['fuel']['غاز'] = price_usd

        # إضافة سعر الدولار للمحروقات والعملات الأخرى
        data['usd_sell'] = usd_sell
        return data
    except Exception as e:
        logger.error(f"Error in get_data: {e}")
        return None

def format_message(data):
    """تنسيق الرسالة النهائية بناءً على البيانات المنظمة"""
    usd_sell = data['usd_sell']
    
    msg = f"🇸🇾 نشرة أسعار الصرف والذهب في سوريا 🇸🇾\n"
    msg += f"⏰ {data['timestamp']} (توقيت دمشق)\n\n"
    
    # العملات الرئيسية
    msg += f"💰 أسعار العملات (شراء | مبيع):\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    for c in data['main_currencies']:
        msg += f"🔹 {c['name']}:\n"
        msg += f"  - ليرة قديمة: {int(c['buy']):,} | {int(c['sell']):,}\n"
        msg += f"  - ليرة جديدة: {c['buy']/100:,.2f} | {c['sell']/100:,.2f} ✨\n"

    # بقية العملات
    if data['other_currencies']:
        msg += f"\n🌍 بقية العملات:\n"
        msg += f"━━━━━━━━━━━━━━━━━━\n"
        for c in data['other_currencies']:
            msg += f"🔸 {c['name']}:\n"
            msg += f"  - ليرة قديمة: {int(c['buy']):,} | {int(c['sell']):,}\n"
            msg += f"  - ليرة جديدة: {c['buy']/100:,.2f} | {c['sell']/100:,.2f}\n"
            msg += f"  - سعر دولار: {(c['buy']/usd_sell):,.2f} $\n"

    # الذهب
    msg += f"\n✨ أسعار الذهب:\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    if '21' in data['gold']:
        syp = data['gold']['21']['syp']
        msg += f"🔸 عيار 21:\n"
        msg += f"  - ليرة قديمة: {int(syp):,} ل.س\n"
        msg += f"  - ليرة جديدة: {syp/100:,.2f} ل.س\n"
        msg += f"  - بالدولار: ${data['gold']['21']['usd']}\n"
    if '18' in data['gold']:
        syp = data['gold']['18']['syp']
        msg += f"🔸 عيار 18:\n"
        msg += f"  - ليرة قديمة: {int(syp):,} ل.س\n"
        msg += f"  - ليرة جديدة: {syp/100:,.2f} ل.س\n"
        msg += f"  - بالدولار: ${data['gold']['18']['usd']}\n"
    if 'ounce' in data['gold']:
        msg += f"\n🌍 أونصة الذهب: ${data['gold']['ounce']}\n"

    # المحروقات
    if data['fuel']:
        msg += f"\n⛽ المحروقات والطاقة:\n"
        msg += f"━━━━━━━━━━━━━━━━━━\n"
        for name, p_usd in data['fuel'].items():
            p_old = int(p_usd * usd_sell)
            msg += f"🔹 سعر {name}:\n"
            msg += f"  - ليرة قديمة: {p_old:,} ل.س\n"
            msg += f"  - ليرة جديدة: {p_old/100:,.2f} ل.س\n"
            msg += f"  - بالدولار: ${p_usd:.2f}\n"

    # الروابط
    msg += f"\n📢 تابعونا عبر منصاتنا:\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"🔗 تلجرام: \n\n https://t.me/FarawlaShop \n\n\n"
    msg += f"🔗 واتساب: \n\n https://whatsapp.com/channel/0029VaQSQveCRs1vibyRZp3A \n\n\n"
    msg += f"🔗 فيسبوك: \n\n https://www.facebook.com/profile.php?id=61584349121096 \n"

    return msg

async def main():
    bot = Bot(token=TOKEN)
    global last_prices
    logger.info("Bot started with stable architecture...")
    
    while True:
        data = get_data()
        if data and (data['main_currencies'] or data['fuel']):
            # إنشاء بصمة فريدة للحالة الحالية لمقارنتها
            current_state = {
                'currencies': {c['code']: c['sell'] for c in data['main_currencies']},
                'gold_21': data['gold'].get('21', {}).get('syp'),
                'fuel': data['fuel']
            }
            
            if current_state != last_prices:
                logger.info("Detected price change, sending update...")
                message = format_message(data)
                try:
                    await bot.send_message(chat_id=CHANNEL_ID, text=message, disable_web_page_preview=True)
                    last_prices = current_state
                    logger.info("Update sent successfully.")
                except Exception as e:
                    logger.error(f"Failed to send message: {e}")
            else:
                logger.info("No significant change detected.")
        else:
            logger.warning("Data fetch returned empty or failed.")
        
        # الانتظار لمدة 5 دقائق قبل الفحص التالي
        await asyncio.sleep(300)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.critical(f"Bot crashed: {e}")
