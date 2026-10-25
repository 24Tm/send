import os
import logging
import yfinance as yf
import pandas as pd
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
        "مرحباً بك يا غالي! 📈\n\n"
        "أنا بوت تحليل الأسهم المطور والذكي. أرسل لي رمز السهم "
        "(مثل `AAPL` للأمريكي، أو رقم السهم السعودي مثل `1120` أو `1820`) وسأعطيك:\n"
        "• السعر الحالي ونسبة التغير\n"
        "• أفضل منطقة شراء (الدعم) وأهداف الخروج\n"
        "• مؤشرات الزخم المتقدمة (RSI و EMA)\n\n"
        "💡 **الأوامر المتاحة:**\n"
        "• أرسل رقم أو رمز السهم مباشرة للتحليل.\n"
        "• أكتب `/scan [الرمز]` لفحص فرص الاختراق والارتداد الذكي."
    )
    await update.message.reply_text(welcome_message)

# دالة مساعدة لتنظيف الرمز وجلب البيانات التاريخية الكافية للمؤشرات (3 أشهر)
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

# دالة حساب مؤشر القوة النسبية RSI
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

# دالة استقبال وتحليل الأسهم بالطريقة الشاملة
async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    await update.message.reply_text(f"جاري جلب بيانات وتحليل الزخم للسهم `{text}` ... ⏳")

    hist, ticker_symbol = fetch_stock_data(text)

    if hist is None or hist.empty:
        await update.message.reply_text(f"عذراً، لم أتمكن من العثور على بيانات للسهم: `{text}`. تأكد من صحة الرمز.")
        return

    try:
        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        change = current_price - prev_close
        change_pct = (change / prev_close) * 100

        # حساب المستويات الفنية والدعم والمقاومة
        support_level = hist['Low'].tail(10).min()
        resistance_level = hist['High'].tail(10).max()

        buy_zone_low = round(support_level * 0.99, 2)
        buy_zone_high = round(support_level * 1.01, 2)
        target_1 = round(current_price * 1.03, 2)
        target_2 = round(max(resistance_level, current_price * 1.06), 2)
        stop_loss = round(buy_zone_low * 0.97, 2)

        # حساب مؤشرات الزخم (RSI والموسط المتحرك الأسي EMA)
        rsi_val = calculate_rsi(hist['Close'])
        ema_50 = hist['Close'].ewm(span=50, adjust=False).mean().iloc[-1]

        # تحديد حالة الزخم واتجاه السهم
        trend_status = "صاعد 🟢" if current_price > ema_50 else "هابط أو تصحيحي 🔴"
        rsi_status = ""
        if rsi_val > 70:
            rsi_status = "تشبع شرائي ⚠️"
        elif rsi_val < 30:
            rsi_status = "تشبع بيعي (فرصة ارتداد محتملة) 🟢"
        else:
            rsi_status = "متوازن ⚖️"

        display_symbol = ticker_symbol.replace(".SR", " (Tadawul)").replace(".SA", " (Tadawul)")

        response = (
            f"📊 **تقرير تحليل وزخم السهم: `{display_symbol}`**\n\n"
            f"• **السعر الحالي:** `{current_price:.2f}`\n"
            f"• **التغير:** `{change:+.2f} ({change_pct:+.2f}%)`\n\n"
            f"🎯 **المستويات ومناطق التداول:**\n"
            f"• 🟢 **منطقة الشراء:** `{buy_zone_low} - {buy_zone_high}`\n"
            f"• 🎯 **الهدف الأول:** `{target_1}` | **الهدف الثاني:** `{target_2}`\n"
            f"• 🛑 **وقف الخسارة:** `{stop_loss}`\n\n"
            f"📉 **تحليل الزخم المتقدم (الفكرة الأولى):**\n"
            f"• **مؤشر القوة النسبية (RSI):** `{rsi_val:.1f}` ({rsi_status})\n"
            f"• **اتجاه المتوسط (EMA 50):** {trend_status}\n\n"
            f"⚠️ *ملاحظة: هذا التحليل آلي للاستئناس وليست توصية مباشرة.*"
        )
        await update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error analyzing stock {text}: {e}")
        await update.message.reply_text("حدث خطأ أثناء معالجة بيانات السهم الفنية.")

# دالة الفحص الذكي للفرص (الفكرة الثانية: Smart Scanner)
async def scan_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("الرجاء إدخال رمز السهم بعد الأمر. مثال:\n`/scan 1120` أو `/scan AAPL`", parse_mode="Markdown")
        return

    text = context.args[0]
    await update.message.reply_text(f"🔍 جاري إجراء المسح الذكي لفرص الارتداد والاختراق للسهم `{text}` ... ⏳")

    hist, ticker_symbol = fetch_stock_data(text)
    if hist is None or hist.empty:
        await update.message.reply_text(f"عذراً، لم نتمكن من جلب بيانات السهم `{text}` للفحص الذكي.")
        return

    try:
        current_price = hist['Close'].iloc[-1]
        recent_low = hist['Low'].tail(10).min()
        distance_from_support = ((current_price - recent_low) / recent_low) * 100
        volume_avg = hist['Volume'].tail(10).mean()
        current_volume = hist['Volume'].iloc[-1]
        rsi_val = calculate_rsi(hist['Close'])

        # شروط الفحص الذكي للفرص
        signal_note = "حالة عادية، انتظر اقتراب السعر أكثر من الدعم."
        if distance_from_support <= 1.5 and rsi_val < 40:
            signal_note = "🔥 **فرصة قوية!** السهم يرتكز قرب منطقة دعم رئيسية مع مؤشر RSI منخفض (منطقة ارتداد)."
        elif current_volume > (volume_avg * 1.5) and current_price > hist['Close'].iloc[-2]:
            signal_note = "🚀 **تنبيه سيولة واختراق!** رصد زيادة ملحوظة في حجم التداول مع صعود سعري."

        report = (
            f"📡 **نتيجة الفحص الذكي (Smart Scanner):**\n"
            f"• الرمز: `{ticker_symbol}`\n"
            f"• البعد عن الدعم الأخير: `{distance_from_support:.2f}%`\n"
            f"• تقييم الفرصة: {signal_note}"
        )
        await update.message.reply_text(report, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in scanner for {text}: {e}")
        await update.message.reply_text("حدث خطأ أثناء عملية المسح الفني.")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("scan", scan_stock))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_stock))

    print("Bot is running with Advanced Features...")
    application.run_polling()

if __name__ == '__main__':
    main()