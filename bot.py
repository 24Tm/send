import os
import logging
import yfinance as yf
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# إعداد السجلات (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# دالة رسالة الترحيب /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "مرحباً بك! 📈\n\n"
        "أنا بوت تحليل الأسهم. أرسل لي رمز السهم "
        "(مثل `AAPL` للأسهم الأمريكية، أو رقم السهم السعودي مثل `1820`) "
        "وسأعطيك آخر سعر تحليل سريع له."
    )
    await update.message.reply_text(welcome_message)

# دالة استقبال رموز الأسهم ومعالجتها
async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    
    # معالجة ذكية للأسهم السعودية:
    if text.isdigit():
        # إذا أدخل أرقاماً فقط (مثال: 1820) -> أضف .SR
        ticker_symbol = f"{text}.SR"
    elif text.endswith("SR") and not text.endswith(".SR"):
        # إذا كتبه المستخدم هكذا (1820SR) بدون نقطة -> أضف النقطة لتصبح (1820.SR)
        ticker_symbol = text[:-2] + ".SR"
    else:
        ticker_symbol = text

    await update.message.reply_text(f"جاري جلب بيانات السهم `{ticker_symbol}` ... ⏳")

    try:
        # جلب بيانات السهم باستخدام yfinance
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period="5d")

        if hist.empty:
            await update.message.reply_text(f"عذراً، لم أتمكن من العثور على بيانات للسهم: `{ticker_symbol}`. تأكد من صحة الرمز.")
            return

        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        change = current_price - prev_close
        change_pct = (change / prev_close) * 100

        # تجهيز رسالة الرد
        response = (
            f"📊 **تحليل السهم: {ticker_symbol}**\n\n"
            f"• السعر الحالي: `{current_price:.2f}`\n"
            f"• التغير: `{change:+.2f} ({change_pct:+.2f}%)`\n"
        )
        await update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error fetching data for {ticker_symbol}: {e}")
        await update.message.reply_text("حدث خطأ أثناء جلب بيانات السهم. حاول مرة أخرى لاحقاً.")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_stock))

    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
