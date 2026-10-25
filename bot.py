import os
import logging
import yfinance as yf
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
 
# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# قائمة الأسهم الافتراضية للمراقبة التلقائية في الخلفية
WATCHLIST_SYMBOLS = ["1120.SR", "1180.SR", "2222.SR", "1010.SR", "1820.SR"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "مرحباً بك يا غالي! 🚀\n\n"
        "أنا بوت تحليل الأسهم المطور. أرسل لي أي رقم أو رمز سهم (مثل `1820` لبنك البلاد أو `1120`) وسأعطيك:\n\n"
        "• السعر الحالي ونسبة التغير 📊\n"
        "• أفضل منطقة شراء (دعم) 🟢\n"
        "• أهداف الخروج (الهدف الأول والثاني) 🎯\n"
        "• نقطة وقف الخسارة 🛑\n"
        "• مؤشر الزخم RSI واتجاه المتوسط EMA 📈\n\n"
        "💡 **الأوامر:**\n"
        "• أرسل رقم السهم مباشرة للتحليل الشامل.\n"
        "• أرسل الأمر `/monitor` لتفعيل التنبيهات التلقائية للفرص في الخلفية."
    )
    await update.message.reply_text(welcome_message)

def fetch_stock_data(text):
    text = text.strip().upper()
    possible_symbols = []
    if text.isdigit():
        possible_symbols = [f"{text}.SR", f"{text}.SA"]
    elif text.endswith("SR") and not text.endswith(".SR"):
        base = text[:-2]
        possible_symbols = [f"{base}.SR", f"{base}.SA"]
    else:
        possible_symbols = [text]

    for sym in possible_symbols:
        try:
            stock = yf.Ticker(sym)
            hist = stock.history(period="3mo")
            if not hist.empty and hist['Close'].iloc[-1] > 0:
                return hist, sym
        except Exception:
            continue
    return None, text

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    await update.message.reply_text(f"جاري جلب وتحليل كافة البيانات الفنية للسهم `{text}` ... ⏳")

    hist, ticker_symbol = fetch_stock_data(text)
    if hist is None or hist.empty:
        await update.message.reply_text(f"عذراً، لم أتمكن من العثور على بيانات صحيحة للسهم: `{text}`. تأكد من صحة الرمز.")
        return

    try:
        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        change = current_price - prev_close
        change_pct = (change / prev_close) * 100

        # حساب الدعوم والمقاومات
        support_level = hist['Low'].tail(10).min()
        resistance_level = hist['High'].tail(10).max()

        buy_zone_low = round(support_level * 0.99, 2)
        buy_zone_high = round(support_level * 1.01, 2)
        target_1 = round(current_price * 1.03, 2)
        target_2 = round(max(resistance_level, current_price * 1.06), 2)
        stop_loss = round(buy_zone_low * 0.97, 2)

        # حساب مؤشرات الزخم المتقدمة
        rsi_val = calculate_rsi(hist['Close'])
        ema_50 = hist['Close'].ewm(span=50, adjust=False).mean().iloc[-1]

        trend_status = "صاعد 🟢" if current_price > ema_50 else "هابط أو تصحيحي 🔴"
        rsi_status = "تشبع شرائي ⚠️" if rsi_val > 70 else ("تشبع بيعي (فرصة ارتداد) 🟢" if rsi_val < 30 else "متوازن ⚖️")
        
        display_symbol = f"Tadawul: {ticker_symbol.replace('.SR', '').replace('.SA', '')}"

        # تجهيز الرسالة الشاملة بجميع التفاصيل
        response = (
            f"📊 **التقرير الفني الشامل للسهم: `{display_symbol}`**\n\n"
            f"• **السعر الحالي:** `{current_price:.2f}` ريال\n"
            f"• **التغير:** `{change:+.2f} ({change_pct:+.2f}%)`\n\n"
            f"🎯 **مستويات التداول (الدخول والخروج):**\n"
            f"• 🟢 **منطقة الشراء:** `{buy_zone_low} - {buy_zone_high}`\n"
            f"• 🎯 **الهدف الأول (خروج):** `{target_1}`\n"
            f"• 🚀 **الهدف الثاني (خروج):** `{target_2}`\n"
            f"• 🛑 **وقف الخسارة:** `{stop_loss}`\n\n"
            f"📉 **تحليل الزخم والقوة (مؤشرات متقدمة):**\n"
            f"• **مؤشر RSI:** `{rsi_val:.1f}` ({rsi_status})\n"
            f"• **اتجاه المتوسط (EMA 50):** {trend_status}\n\n"
            f"⚠️ *ملاحظة: هذا التحليل آلي للاستئناس وليست توصية مباشرة.*"
        )
        await update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error handling stock {text}: {e}")
        await update.message.reply_text("حدث خطأ أثناء معالجة بيانات السهم الفنية.")

# دالة التنبيهات التلقائية في الخلفية
async def check_market_explosions(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id

    for sym in WATCHLIST_SYMBOLS:
        hist, ticker_symbol = fetch_stock_data(sym)
        if hist is None or hist.empty:
            continue
        try:
            current_price = hist['Close'].iloc[-1]
            recent_low = hist['Low'].tail(10).min()
            distance_from_support = ((current_price - recent_low) / recent_low) * 100
            rsi_val = calculate_rsi(hist['Close'])

            if distance_from_support <= 1.2 and rsi_val < 38:
                alert_msg = (
                    f"🚨🔥 **تنبيه تلقائي: فرصة ارتداد قوية!**\n\n"
                    f"• السهم: `Tadawul: {ticker_symbol.replace('.SR', '')}`\n"
                    f"• السعر الحالي: `{current_price:.2f}` ريال\n"
                    f"• السهم يرتكز قرب الدعم بنسبة `{distance_from_support:.2f}%` مع مؤشر RSI منخفض (`{rsi_val:.1f}`)."
                )
                await context.bot.send_message(chat_id=chat_id, text=alert_msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Background check error for {sym}: {e}")

async def start_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if current_jobs:
        await update.message.reply_text("المراقبة التلقائية مفعلة لديك مسبقاً وأنا أراقب السوق بالخلفية! 🟢")
        return

    context.job_queue.run_repeating(check_market_explosions, interval=3600, first=10, chat_id=chat_id, name=str(chat_id))
    await update.message.reply_text("✅ تم تفعيل **المراقبة الذاتية التلقائية** بنجاح! سأراسلك فوراً عند رصد أي فرصة انفجار أو ارتداد في السوق.")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("monitor", start_monitoring))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_stock))

    print("Bot is running with full features...")
    application.run_polling()

if __name__ == '__main__':
    main()