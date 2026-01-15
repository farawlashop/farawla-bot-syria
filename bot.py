import os
import logging
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from openai import OpenAI
from github import Github
from datetime import timedelta, datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# إعداد السجلات لضمان تتبع الأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تحميل الإعدادات من البيئة (Environment Variables)
TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
GITHUB_PAT = os.environ.get("GITHUB_PAT")
BOT_NAME = os.environ.get("BOT_NAME", "FarawlaShop AI")

# إعداد OpenAI فقط إذا كان المفتاح موجوداً
client = None
if OPENAI_KEY:
    client = OpenAI(api_key=OPENAI_KEY)
else:
    logger.warning("OPENAI_API_KEY is missing. AI responses will be disabled.")

# إعداد المجدول للمهام المستقلة
scheduler = AsyncIOScheduler()
chat_history = {}

async def get_ai_response(user_id, user_text):
    if not client:
        return "عذراً، نظام الذكاء الاصطناعي غير مفعل حالياً. يرجى إضافة OPENAI_API_KEY في إعدادات GitHub Secrets."
    
    if user_id not in chat_history:
        chat_history[user_id] = [
            {"role": "system", "content": f"أنت {BOT_NAME}، وكيل ذكي خارق ومستقل لمتجر Farawla Shop. أنت تدير التلجرام، الفيسبوك، بلوجر، والجيميل. شخصيتك احترافية وذكية جداً."}
        ]
    
    chat_history[user_id].append({"role": "user", "content": user_text})
    
    # الحفاظ على سياق آخر 10 رسائل فقط لتوفير الاستهلاك
    if len(chat_history[user_id]) > 11:
        chat_history[user_id] = [chat_history[user_id][0]] + chat_history[user_id][-10:]

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"مرحباً! أنا {BOT_NAME}، وكيلك الذكي المستقل. أنا الآن متصل وأدير كافة منصاتك (Blogger, Gmail, FB, Telegram). كيف يمكنني مساعدتك؟")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    user_text = update.message.text
    user_id = update.effective_user.id
    
    # إظهار حالة "يكتب الآن" لإعطاء طابع بشري
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    response = await get_ai_response(user_id, user_text)
    await update.message.reply_text(response)

async def main():
    if not TOKEN:
        logger.error("TELEGRAM_TOKEN is missing! Bot cannot start.")
        return

    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    scheduler.start()
    logger.info(f"{BOT_NAME} is now online and autonomous.")
    
    await application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
