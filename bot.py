import os
import logging
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from openai import OpenAI
from github import Github
from datetime import timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from dotenv import load_dotenv

# تحميل الإعدادات
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_NAME = os.getenv("BOT_NAME", "FarawlaShop")

# إعداد OpenAI
client = OpenAI()

# إعداد GitHub
GITHUB_PAT = os.getenv("GITHUB_PAT")
REPO_NAME = "farawlashop/farawla-shop-ai-agent"
SCHEDULE_FILE = "SCHEDULED_TASKS.md"

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# إعداد المجدول
scheduler = AsyncIOScheduler()

# ذاكرة بسيطة للمحادثات
chat_history = {}

async def get_ai_response(user_id, user_text):
    if user_id not in chat_history:
        chat_history[user_id] = [
            {"role": "system", "content": f"أنت وكيل ذكي خارق ومستقل تدعى {BOT_NAME}. أنت تعمل كمدير لمتجر Farawla Shop. شخصيتك احترافية، ذكية، وتساعد المستخدمين في كل شيء. أنت لست مجرد بوت، بل وكيل ذكي قادر على التفكير والتحليل وتنفيذ المهام. تحدث دائماً باللغة العربية بلهجة مهذبة وعملية."}
        ]
    
    chat_history[user_id].append({"role": "user", "content": user_text})
    
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
        logging.error(f"OpenAI Error: {e}")
        return "عذراً، واجهت مشكلة في معالجة طلبك الآن. سأحاول مجدداً لاحقاً."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = f"مرحباً {user.first_name}! أنا {BOT_NAME}، وكيلك الذكي المستقل. كيف يمكنني مساعدتك اليوم؟"
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    response = await get_ai_response(user_id, user_text)
    await update.message.reply_text(response)

async def update_github_schedule(task_text, run_date, status="PENDING"):
    if not GITHUB_PAT:
        logging.error("GITHUB_PAT is not set. Cannot update GitHub.")
        return False

    try:
        g = Github(GITHUB_PAT)
        repo = g.get_repo(REPO_NAME)
        
        # محاولة قراءة المحتوى الحالي
        try:
            contents = repo.get_contents(SCHEDULE_FILE)
            current_content = contents.decoded_content.decode("utf-8")
        except Exception:
            # الملف غير موجود، نبدأ بمحتوى فارغ
            current_content = "# المهام المجدولة لـ Farawla Shop\n\n"
            contents = None

        # إضافة المهمة الجديدة
        task_entry = f"- [ ] **{status}** | {run_date.strftime('%Y-%m-%d %H:%M:%S')} | {task_text}\n"
        new_content = current_content + task_entry
        
        commit_message = f"جدولة مهمة جديدة: {task_text[:50]}..."
        
        if contents:
            repo.update_file(contents.path, commit_message, new_content, contents.sha)
        else:
            repo.create_file(SCHEDULE_FILE, commit_message, new_content)
            
        return True
    except Exception as e:
        logging.error(f"GitHub Update Error: {e}")
        return False

async def scheduled_task(chat_id, text, bot):
    await bot.send_message(chat_id=chat_id, text=f"📢 مهمة مجدولة: {text}")

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        seconds = int(context.args[0])
        text = " ".join(context.args[1:])
        chat_id = update.effective_chat.id
        bot = context.bot
        
        # تحويل المدخل إلى تاريخ تشغيل مستقبلي
        run_date = datetime.now() + timedelta(seconds=seconds)
        
        # إضافة المهمة إلى المجدول
        scheduler.add_job(scheduled_task, 'date', run_date=run_date, args=[chat_id, text, context.bot], id=f"job_{run_date.timestamp()}")
        
        # تحديث GitHub
        github_success = await update_github_schedule(text, run_date)
        
        if github_success:
            await update.message.reply_text(f"تمت جدولة المهمة بنجاح في {run_date.strftime('%Y-%m-%d %H:%M:%S')} وتم تسجيلها في GitHub.")
        else:
            await update.message.reply_text(f"تمت جدولة المهمة بنجاح في {run_date.strftime('%Y-%m-%d %H:%M:%S')}، ولكن فشل تسجيلها في GitHub. يرجى التأكد من مفتاح GITHUB_PAT.")
    except (IndexError, ValueError):
        await update.message.reply_text("الرجاء استخدام الصيغة: /schedule [ثواني] [النص]")

async def main():
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('schedule', schedule_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    scheduler.start()
    
    print(f"{BOT_NAME} is running...")
    async with application:
        await application.initialize()
        await application.start()
        
        # محاولة بدء الاستقبال مع معالجة خطأ التعارض
        try:
            await application.updater.start_polling(drop_pending_updates=True)
        except Exception as e:
            print(f"Error starting polling: {e}")
            
        while True:
            await asyncio.sleep(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
