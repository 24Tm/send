import os
import telegram
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import yfinance as yf
import pandas as pd

# قراءة التوكن من متغيرات البيئة التي أضفناها في Render
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# دالة بداية التشغيل /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحباً بك! 📈\n"
        "أنا بوت تحليل الأسهم. أرسل لي رمز السهم (مثل AAPL أو TSLA أو MSFT) وسأعطيك آخر سعر تحليل سريع له."
    )

# دالة تحليل السهم عند إرسال الرمز
async def analyze_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    
    # تجنب الرد على الكلمات الطويلة جداً
    if len(text) > 10:
        return

    await update.message.reply_text(f"جاري جلب بيانات السهم `{text}`... ⏳")

    try:
        # جلب بيانات السهم عبر yfinance
        stock = yf.Ticker(text)
        hist = stock.history(period="1mo")
        
        if hist.empty:
            await update.message.reply_text(f"عذراً، لم أتمكن من العثور على بيانات للسهم: `{text}`. تأكد من صحة الرمز.")
            return

        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        change = current_price - prev_close
        change_pct = (change / prev_close) * 100

        # حساب المتوسط المتحرك البسيط لمدة 5 أيام عبر pandas العادية
        sma_5 = hist['Close'].rolling(window=5).mean().iloc[-1]

        # صياغة رسالة الرد
        msg = (
            f"📊 **تحليل السهم: {text}**\n\n"
            f"💰 السعر الحالي: `{current_price:.2f}`\n"
            f"📉 التغير: `{change:+.2f}` (`{change_pct:+.2f}%`)\n"
            f"📈 المتوسط المتحرك (5 أيام): `{sma_5:.2f}`\n"
        )
        
        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text("حدث خطأ أثناء جلب بيانات السهم. حاول مرة أخرى لاحقاً.")

def main():
    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is not set.")
        return

    # بناء وتشغيل البوت
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), analyze_stock))

    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
