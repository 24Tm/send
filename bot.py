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
        "(مثل `AAPL` للأسهم الأمريكية، أو رقم السهم السعودي مثل `1820` أو `1120`) "
        "وسأعطيك تحليلاً يشتمل على السعر الحالي، مناطق الشراء، وأهداف الخروج."
    )
    await update.message.reply_text(welcome_message)

# دالة استقبال رموز الأسهم ومعالجتها
async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    
    # تحديد الصيغ المحتملة للأسهم السعودية والعالمية
    possible_symbols = []
    if text.isdigit():
        possible_symbols = [f"{text}.SR", f"{text}.SA", text]
    elif text.endswith("SR") and not text.endswith(".SR"):
        base = text[:-2]
        possible_symbols = [f"{base}.SR", f"{base}.SA", text]
    else:
        possible_symbols = [text]

    await update.message.reply_text(f"جاري جلب بيانات وتحليل السهم `{text}` ... ⏳")

    hist = None
    ticker_symbol = text

    try:
        # تجربة جلب البيانات عبر الصيغ المتاحة
        for sym in possible_symbols:
            stock = yf.Ticker(sym)
            temp_hist = stock.history(period="1mo")
            if not temp_hist.empty:
                hist = temp_hist
                ticker_symbol = sym
                break

        if hist is None or hist.empty:
            await update.message.reply_text(
                f"عذراً، لم أتمكن من العثور على بيانات للسهم: `{text}`.\n"
                "تأكد من صحة الرمز أو الرقم المدخل."
            )
            return

        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        change = current_price - prev_close
        change_pct = (change / prev_close) * 100

        # حساب مستويات الدعم والمقاومة ومناطق الشراء والخروج
        support_level = hist['Low'].tail(10).min()   # مستوى الدعم القريب
        resistance_level = hist['High'].tail(10).max() # مستوى المقاومة القريب

        # منطقة الشراء المقترحة (حول مستوى الدعم)
        buy_zone_low = round(support_level * 0.99, 2)
        buy_zone_high = round(support_level * 1.01, 2)

        # منطقة الخروج / الهدف المقترح (حول مستوى المقاومة أو بنسبة ربح مستهدفة)
        exit_target = round(max(resistance_level, current_price * 1.04), 2)
        recent_low = hist['Low'].min()

        # تجهيز رسالة الرد المفصلة
        response = (
            f"📊 **تحليل السهم: {ticker_symbol}**\n\n"
            f"• السعر الحالي: `{current_price:.2f}`\n"
            f"• التغير: `{change:+.2f} ({change_pct:+.2f}%)`\n\n"
            f"🎯 **التحليل الفني والمستويات:**\n"
            f"• 🟢 **أفضل منطقة شراء:** `{buy_zone_low} - {buy_zone_high}`\n"
            f"• 🔴 **منطقة الخروج (الهدف):** `{exit_target}`\n"
            f"• 📉 أدنى سعر شهري: `{recent_low:.2f}`\n\n"
            f"⚠️ *ملاحظة: هذا التحليل آلي للاستئناس وليس توصية بيع أو شراء مباشرة.*"
        )
        await update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error fetching data for {text}: {e}")
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