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

# قائمة الأسهم الافتراضية للمراقبة التلقائية (يمكنك تعديلها أو إضافتها)
WATCHLIST_SYMBOLS = ["1120.SR", "1180.SR", "2222.SR", "1010.SR", "7010.SR"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "مرحباً بك يا غالي! 🚀\n\n"
        "أنا بوت تحليل الأسهم المطور مع **نظام التنبيهات الاستباقية للفرص الانفجارية**.\n\n"
        "• سأقوم بمراقبة الأسهم وقюم بإرسال تنبيه تلقائي عند رصد فرصة ارتداد أو انفجار سعري.\n"
        "• يمكنك أيضاً إرسال أي رمز سهم يدوياً في أي وقت للتحليل الفوري."
    )
    await update.message.reply_text(welcome_message)

def fetch_stock_data(text):
    text = text.strip().upper()
    possible_symbols = []
    if text.isdigit():
        possible_symbols = [f"{text}.SR", f"{text}.SA", text]
    elif text.endswith("SR") and not text.endswith(".SR"):
        base = text[:-2]
        possible_symbols = [f"{base}.SR", f"{base}.SA", text]
    else:
        possible_symbols = [text]

    for sym in possible_symbols:
        try:
            stock = yf.Ticker(sym)
            hist = stock.history(period="3mo")
            if not hist.empty:
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
    await update.message.reply_text(f"جاري جلب بيانات وتحليل الزخم للسهم `{text}` ... ⏳")

    hist, ticker_symbol = fetch_stock_data(text)
    if hist is None or hist.empty:
        await update.message.reply_text(f"عذراً، لم أتمكن من العثور على بيانات للسهم: `{text}`.")
        return

    try:
        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        change = current_price - prev_close
        change_pct = (change / prev_close) * 100

        support_level = hist['Low'].tail(10).min()
        resistance_level = hist['High'].tail(10).max()

        buy_zone_low = round(support_level * 0.99, 2)
        buy_zone_high = round(support_level * 1.01, 2)
        target_1 = round(current_price * 1.03, 2)
        target_2 = round(max(resistance_level, current_price * 1.06), 2)
        stop_loss = round(buy_zone_low * 0.97, 2)

        rsi_val = calculate_rsi(hist['Close'])
        ema_50 = hist['Close'].ewm(span=50, adjust=False).mean().iloc[-1]

        trend_status = "صاعد 🟢" if current_price > ema_50 else "هابط أو تصحيحي 🔴"
        rsi_status = "تشبع شرائي ⚠️" if rsi_val > 70 else ("تشبع بيعي (فرصة ارتداد) 🟢" if rsi_val < 30 else "متوازن ⚖️")
        display_symbol = ticker_symbol.replace(".SR", " (Tadawul)")

        response = (
            f"📊 **تقرير تحليل وزخم السهم: `{display_symbol}`**\n\n"
            f"• **السعر الحالي:** `{current_price:.2f}`\n"
            f"• **التغير:** `{change:+.2f} ({change_pct:+.2f}%)`\n\n"
            f"🎯 **المستويات ومناطق التداول:**\n"
            f"• 🟢 **منطقة الشراء:** `{buy_zone_low} - {buy_zone_high}`\n"
            f"• 🎯 **الهدف الأول:** `{target_1}` | **الهدف الثاني:** `{target_2}`\n"
            f"• 🛑 **وقف الخسارة:** `{stop_loss}`\n\n"
            f"📉 **تحليل الزخم المتقدم:**\n"
            f"• **RSI:** `{rsi_val:.1f}` ({rsi_status})\n"
            f"• **الاتجاه (EMA 50):** {trend_status}"
        )
        await update.message.reply_text(response, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("حدث خطأ أثناء معالجة بيانات السهم.")

# دالة الفحص التلقائي وإرسال التنبيهات من ذاته في الخلفية
async def check_market_explosions(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id  # إرسال التنبيه لنفس الشات أو المستخدم الذي تواصل مع البوت

    for sym in WATCHLIST_SYMBOLS:
        hist, ticker_symbol = fetch_stock_data(sym)
        if hist is None or hist.empty:
            continue
        try:
            current_price = hist['Close'].iloc[-1]
            recent_low = hist['Low'].tail(10).min()
            distance_from_support = ((current_price - recent_low) / recent_low) * 100
            volume_avg = hist['Volume'].tail(10).mean()
            current_volume = hist['Volume'].iloc[-1]
            rsi_val = calculate_rsi(hist['Close'])

            # شروط رصد الفرصة الانفجارية أو الارتدادية
            if distance_from_support <= 1.2 and rsi_val < 38:
                alert_msg = (
                    f"🚨🔥 **تنبيه فرصة انفجار / ارتداد قوية!**\n\n"
                    f"• السهم: `{ticker_symbol}`\n"
                    f"• السعر الحالي: `{current_price:.2f}`\n"
                    f"• السهم يرتكز قرب منطقة دعم قوية بنسبة `{distance_from_support:.2f}%`\n"
                    f"• مؤشر القوة النسبية RSI منخفض (`{rsi_val:.1f}`) مما يشير لقرب ارتداد صاعد!"
                )
                await context.bot.send_message(chat_id=chat_id, text=alert_msg, parse_mode="Markdown")
            
            elif current_volume > (volume_avg * 1.8) and current_price > hist['Close'].iloc[-2]:
                alert_msg = (
                    f"🚀⚡ **رصد تدفق سيولة واختراق محتمل!**\n\n"
                    f"• السهم: `{ticker_symbol}`\n"
                    f"• السعر الحالي: `{current_price:.2f}`\n"
                    f"• تم رصد ارتفاع غير معتاد في حجم التداول مع حركة إيجابية للسعر."
                )
                await context.bot.send_message(chat_id=chat_id, text=alert_msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Background check error for {sym}: {e}")

# أمر لتفعيل المراقبة التلقائية وإرسال التنبيهات ذاتياً
async def start_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # التأكد من عدم تكرار المهمة لذات المستخدم
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if current_jobs:
        await update.message.reply_text("المراقبة التلقائية مفعلة لديك مسبقاً وأنا أراقب السوق لأجلك! 🟢")
        return

    # جدولة الفحص التلقائي كل ساعة (3600 ثانية) أو كل نصف ساعة
    context.job_queue.run_repeating(check_market_explosions, interval=3600, first=10, chat_id=chat_id, name=str(chat_id))
    await update.message.reply_text("✅ تم تفعيل **المراقبة الذاتية التلقائية** بنجاح!\nسأقوم بفحص الأسهم وإرسال تنبيهات فورية لك عند رصد أي فرصة انفجار أو ارتداد.")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("monitor", start_monitoring))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_stock))

    print("Bot is running with Proactive Alerts...")
    application.run_polling()

if __name__ == '__main__':
    main()