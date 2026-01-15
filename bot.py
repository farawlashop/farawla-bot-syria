import os
import logging
import asyncio
import requests
import json
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from openai import OpenAI
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تحميل الإعدادات من البيئة
TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
GITHUB_PAT = os.environ.get("GITHUB_PAT")
BOT_NAME = os.environ.get("BOT_NAME", "FarawlaShop AI")

# إعداد OpenAI
client = None
if OPENAI_KEY:
    client = OpenAI(api_key=OPENAI_KEY)
else:
    logger.warning("OPENAI_API_KEY is missing. AI responses will be disabled.")

# المجدول والذاكرة
scheduler = AsyncIOScheduler()
chat_history = {}
apk_build_queue = {}

# ==================== وظائف الذكاء الاصطناعي ====================

async def get_ai_response(user_id, user_text, context=None):
    """الحصول على رد ذكي من GPT-4"""
    if not client:
        return "عذراً، نظام الذكاء الاصطناعي غير مفعل حالياً. يرجى إضافة OPENAI_API_KEY في إعدادات Secrets."
    
    if user_id not in chat_history:
        system_prompt = f"""أنت {BOT_NAME}، وكيل ذكي خارق ومستقل لمتجر Farawla Shop.
        
أنت تدير:
- تلجرام (Telegram)
- جيميل (Gmail)
- بلوجر (Blogger)
- فيسبوك (Facebook)

قدراتك الخاصة:
1. **إنشاء تطبيقات APK**: يمكنك تحويل أكواد Python إلى تطبيقات Android
2. **البحث السريع والعميق**: تستطيع البحث في الإنترنت ووسائل التواصل الاجتماعي
3. **إدارة المنصات**: تدير البريد الإلكتروني، المدونات، والقنوات

شخصيتك: احترافية، ذكية جداً، ومفيدة. تجيب بوضوح وبشكل مباشر."""
        
        chat_history[user_id] = [{"role": "system", "content": system_prompt}]
    
    # إضافة السياق إذا كان موجوداً (مثل نتائج البحث)
    if context:
        chat_history[user_id].append({"role": "system", "content": f"معلومات إضافية: {context}"})
    
    chat_history[user_id].append({"role": "user", "content": user_text})
    
    # الحفاظ على آخر 20 رسالة
    if len(chat_history[user_id]) > 21:
        chat_history[user_id] = [chat_history[user_id][0]] + chat_history[user_id][-20:]

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=chat_history[user_id]
        )
        ai_message = response.choices[0].message.content
        chat_history[user_id].append({"role": "assistant", "content": ai_message})
        return ai_message
    except Exception as e:
        logger.error(f"OpenAI Error: {e}")
        return "واجهت مشكلة في التفكير حالياً، سأكون معك خلال لحظات."

# ==================== وظائف البحث ====================

async def quick_search(query, max_results=5):
    """بحث سريع باستخدام DuckDuckGo"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            
        if not results:
            return "لم أجد نتائج للبحث."
        
        formatted_results = "🔍 **نتائج البحث السريع:**\n\n"
        for i, result in enumerate(results, 1):
            formatted_results += f"{i}. **{result['title']}**\n"
            formatted_results += f"   {result['body'][:150]}...\n"
            formatted_results += f"   🔗 {result['href']}\n\n"
        
        return formatted_results
    except Exception as e:
        logger.error(f"Quick Search Error: {e}")
        return f"حدث خطأ أثناء البحث: {str(e)}"

async def deep_search(query, max_results=10):
    """بحث عميق مع تحليل محتوى الصفحات"""
    try:
        # البحث الأولي
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        
        if not results:
            return "لم أجد نتائج للبحث العميق."
        
        formatted_results = "🔬 **نتائج البحث العميق:**\n\n"
        formatted_results += f"تم العثور على {len(results)} نتيجة:\n\n"
        
        # تحليل أول 3 صفحات
        for i, result in enumerate(results[:3], 1):
            formatted_results += f"{i}. **{result['title']}**\n"
            formatted_results += f"   📝 {result['body']}\n"
            
            # محاولة جلب محتوى الصفحة
            try:
                response = requests.get(result['href'], timeout=5, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # استخراج الفقرات
                paragraphs = soup.find_all('p')[:3]
                if paragraphs:
                    content = ' '.join([p.get_text().strip() for p in paragraphs])[:300]
                    formatted_results += f"   💡 ملخص: {content}...\n"
            except:
                pass
            
            formatted_results += f"   🔗 {result['href']}\n\n"
        
        # إضافة باقي النتائج
        if len(results) > 3:
            formatted_results += "\n**نتائج إضافية:**\n"
            for i, result in enumerate(results[3:], 4):
                formatted_results += f"{i}. {result['title']}\n   🔗 {result['href']}\n"
        
        return formatted_results
    except Exception as e:
        logger.error(f"Deep Search Error: {e}")
        return f"حدث خطأ أثناء البحث العميق: {str(e)}"

async def social_search(query, platform="all"):
    """بحث في منصات التواصل الاجتماعي"""
    try:
        results = []
        
        # البحث في منصات مختلفة
        platforms_queries = {
            "twitter": f"site:twitter.com OR site:x.com {query}",
            "facebook": f"site:facebook.com {query}",
            "instagram": f"site:instagram.com {query}",
            "youtube": f"site:youtube.com {query}",
            "reddit": f"site:reddit.com {query}",
            "linkedin": f"site:linkedin.com {query}"
        }
        
        if platform == "all":
            search_query = " OR ".join([f"site:{p}.com" for p in ["twitter", "facebook", "instagram", "youtube", "reddit", "linkedin"]]) + f" {query}"
        else:
            search_query = platforms_queries.get(platform, query)
        
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, max_results=10))
        
        if not results:
            return f"لم أجد نتائج على منصات التواصل الاجتماعي عن: {query}"
        
        formatted_results = "📱 **نتائج البحث في وسائل التواصل الاجتماعي:**\n\n"
        
        for i, result in enumerate(results, 1):
            # تحديد المنصة من الرابط
            url = result['href']
            platform_emoji = "🌐"
            if "twitter.com" in url or "x.com" in url:
                platform_emoji = "🐦"
            elif "facebook.com" in url:
                platform_emoji = "📘"
            elif "instagram.com" in url:
                platform_emoji = "📸"
            elif "youtube.com" in url:
                platform_emoji = "📹"
            elif "reddit.com" in url:
                platform_emoji = "🤖"
            elif "linkedin.com" in url:
                platform_emoji = "💼"
            
            formatted_results += f"{i}. {platform_emoji} **{result['title']}**\n"
            formatted_results += f"   {result['body'][:150]}...\n"
            formatted_results += f"   🔗 {result['href']}\n\n"
        
        return formatted_results
    except Exception as e:
        logger.error(f"Social Search Error: {e}")
        return f"حدث خطأ أثناء البحث في وسائل التواصل: {str(e)}"

# ==================== وظائف إنشاء APK ====================

async def create_apk_info():
    """معلومات عن إنشاء APK"""
    info = """📱 **خدمة إنشاء تطبيقات APK**

أستطيع مساعدتك في تحويل أكواد Python إلى تطبيقات Android!

**الطريقة:**
1. أرسل لي كود Python الخاص بك
2. سأقوم برفعه إلى GitHub
3. سيتم بناء APK تلقائياً عبر GitHub Actions
4. ستحصل على رابط التحميل خلال 10-15 دقيقة

**المتطلبات:**
- كود Python صالح
- اسم التطبيق
- وصف التطبيق (اختياري)

**ملاحظة:** هذه الخدمة تستخدم Buildozer و python-for-android (مفتوحة المصدر)

لبدء إنشاء تطبيق، أرسل الأمر:
`/create_apk`"""
    
    return info

async def start_apk_creation(user_id, app_name, python_code, description=""):
    """بدء عملية إنشاء APK"""
    try:
        # حفظ الطلب في قائمة الانتظار
        apk_build_queue[user_id] = {
            "app_name": app_name,
            "code": python_code,
            "description": description,
            "status": "queued",
            "created_at": datetime.now().isoformat()
        }
        
        # في الواقع، هذه العملية تحتاج إلى:
        # 1. إنشاء مستودع GitHub جديد
        # 2. رفع الكود + ملف buildozer.spec
        # 3. إنشاء GitHub Actions workflow
        # 4. تشغيل البناء
        
        return f"""✅ **تم استلام طلب إنشاء التطبيق!**

📱 اسم التطبيق: {app_name}
⏳ الحالة: في قائمة الانتظار

سيتم بناء التطبيق عبر GitHub Actions. هذه العملية قد تستغرق 10-20 دقيقة.

**ملاحظة:** 
نظراً لمحدودية موارد Replit، سيتم بناء APK عبر GitHub Actions.
لتفعيل هذه الميزة بالكامل، يرجى:
1. إعداد GitHub Personal Access Token
2. إنشاء مستودع خاص للبناء
3. إضافة GitHub Actions workflow

حالياً، الكود جاهز للرفع يدوياً إلى GitHub."""
        
    except Exception as e:
        logger.error(f"APK Creation Error: {e}")
        return f"حدث خطأ أثناء إنشاء التطبيق: {str(e)}"

# ==================== معالجات الأوامر ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البدء"""
    keyboard = [
        [InlineKeyboardButton("🔍 بحث سريع", callback_data="help_search")],
        [InlineKeyboardButton("🔬 بحث عميق", callback_data="help_deep")],
        [InlineKeyboardButton("📱 إنشاء APK", callback_data="help_apk")],
        [InlineKeyboardButton("📲 بحث في وسائل التواصل", callback_data="help_social")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_msg = f"""مرحباً! 👋

أنا **{BOT_NAME}**، وكيلك الذكي المستقل والخارق! 🤖✨

**قدراتي:**
🔍 بحث سريع وعميق في الإنترنت
📱 بحث في وسائل التواصل الاجتماعي
📲 إنشاء تطبيقات Android (APK)
💬 محادثة ذكية مع ذاكرة

**الأوامر المتاحة:**
/search <نص البحث> - بحث سريع
/deep <نص البحث> - بحث عميق
/social <نص البحث> - بحث في وسائل التواصل
/apk - معلومات عن إنشاء APK
/clear - مسح سجل المحادثة

أو فقط أرسل لي رسالة وسأجيبك! 💬"""
    
    await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البحث السريع"""
    if not context.args:
        await update.message.reply_text("❌ يرجى إدخال نص البحث.\nمثال: `/search أخبار سوريا`", parse_mode='Markdown')
        return
    
    query = ' '.join(context.args)
    await update.message.reply_text(f"🔍 جارٍ البحث عن: *{query}*...", parse_mode='Markdown')
    
    results = await quick_search(query)
    
    # تقسيم الرسالة إذا كانت طويلة
    if len(results) > 4000:
        parts = [results[i:i+4000] for i in range(0, len(results), 4000)]
        for part in parts:
            await update.message.reply_text(part, parse_mode='Markdown', disable_web_page_preview=True)
    else:
        await update.message.reply_text(results, parse_mode='Markdown', disable_web_page_preview=True)

async def deep_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البحث العميق"""
    if not context.args:
        await update.message.reply_text("❌ يرجى إدخال نص البحث.\nمثال: `/deep الذكاء الاصطناعي`", parse_mode='Markdown')
        return
    
    query = ' '.join(context.args)
    await update.message.reply_text(f"🔬 جارٍ البحث العميق عن: *{query}*...\nقد يستغرق هذا بضع ثوانٍ...", parse_mode='Markdown')
    
    results = await deep_search(query)
    
    # تقسيم الرسالة إذا كانت طويلة
    if len(results) > 4000:
        parts = [results[i:i+4000] for i in range(0, len(results), 4000)]
        for part in parts:
            await update.message.reply_text(part, parse_mode='Markdown', disable_web_page_preview=True)
    else:
        await update.message.reply_text(results, parse_mode='Markdown', disable_web_page_preview=True)

async def social_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البحث في وسائل التواصل"""
    if not context.args:
        await update.message.reply_text("❌ يرجى إدخال نص البحث.\nمثال: `/social أخبار التكنولوجيا`", parse_mode='Markdown')
        return
    
    query = ' '.join(context.args)
    await update.message.reply_text(f"📱 جارٍ البحث في وسائل التواصل عن: *{query}*...", parse_mode='Markdown')
    
    results = await social_search(query)
    
    # تقسيم الرسالة إذا كانت طويلة
    if len(results) > 4000:
        parts = [results[i:i+4000] for i in range(0, len(results), 4000)]
        for part in parts:
            await update.message.reply_text(part, parse_mode='Markdown', disable_web_page_preview=True)
    else:
        await update.message.reply_text(results, parse_mode='Markdown', disable_web_page_preview=True)

async def apk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر معلومات APK"""
    info = await create_apk_info()
    await update.message.reply_text(info, parse_mode='Markdown')

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مسح سجل المحادثة"""
    user_id = update.effective_user.id
    if user_id in chat_history:
        del chat_history[user_id]
    await update.message.reply_text("✅ تم مسح سجل المحادثة. يمكنك البدء من جديد!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الرسائل النصية"""
    if not update.message or not update.message.text:
        return
    
    user_text = update.message.text
    user_id = update.effective_user.id
    
    # إظهار حالة "يكتب الآن"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # التحقق إذا كانت الرسالة تحتوي على طلب بحث
    if any(keyword in user_text.lower() for keyword in ['ابحث', 'بحث عن', 'ما هو', 'من هو', 'أين', 'متى', 'كيف']):
        # إجراء بحث سريع تلقائي
        search_results = await quick_search(user_text, max_results=3)
        response = await get_ai_response(user_id, user_text, context=search_results)
    else:
        response = await get_ai_response(user_id, user_text)
    
    # تقسيم الرسالة إذا كانت طويلة
    if len(response) > 4000:
        parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
        for part in parts:
            await update.message.reply_text(part, parse_mode='Markdown')
    else:
        await update.message.reply_text(response, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أزرار الإنلاين"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "help_search":
        await query.message.reply_text(
            "🔍 **البحث السريع**\n\nاستخدم: `/search <نص البحث>`\n\nمثال: `/search أخبار سوريا`\n\nسيعطيك نتائج سريعة من محركات البحث.",
            parse_mode='Markdown'
        )
    elif query.data == "help_deep":
        await query.message.reply_text(
            "🔬 **البحث العميق**\n\nاستخدم: `/deep <نص البحث>`\n\nمثال: `/deep الذكاء الاصطناعي`\n\nسيقوم بتحليل محتوى الصفحات ويعطيك معلومات أكثر تفصيلاً.",
            parse_mode='Markdown'
        )
    elif query.data == "help_apk":
        info = await create_apk_info()
        await query.message.reply_text(info, parse_mode='Markdown')
    elif query.data == "help_social":
        await query.message.reply_text(
            "📱 **البحث في وسائل التواصل**\n\nاستخدم: `/social <نص البحث>`\n\nمثال: `/social أخبار التكنولوجيا`\n\nسيبحث في Twitter, Facebook, Instagram, YouTube, Reddit, LinkedIn.",
            parse_mode='Markdown'
        )

# ==================== البرنامج الرئيسي ====================

async def main():
    """البرنامج الرئيسي"""
    if not TOKEN:
        logger.error("TELEGRAM_TOKEN is missing! Bot cannot start.")
        return

    application = ApplicationBuilder().token(TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('search', search_command))
    application.add_handler(CommandHandler('deep', deep_command))
    application.add_handler(CommandHandler('social', social_command))
    application.add_handler(CommandHandler('apk', apk_command))
    application.add_handler(CommandHandler('clear', clear_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    # بدء المجدول
    scheduler.start()
    logger.info(f"{BOT_NAME} is now online and autonomous with advanced features!")
    
    # تشغيل البوت
    await application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped gracefully.")
        pass
