import os
import logging
import io
import threading
import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# إعداد التسجيل والمراقبة
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# إنشاء سيرفر ويب وهمي لمنع البوت من النوم على استضافة Render
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot is active and running 24/7[span_1](start_span)!"[span_1](end_span)

def run_web():
    app_web.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# دالة الترحيب التفاعلية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "مرحباً بك يا غالي في مستشارك المالي البصري! 🚀\n\n"
        "أنا بوت تحليل الأسهم السعودية (Tadawul). أرسل لي أي رمز سهم (مثل `1120` أو `1820`) وسأعطيك:\n\n"
        "• **شارت فني مطور ومظلل بمناطق القرار** 📊\n"
        "• السعر الحالي ومستويات الدعم، الهدف، ووقف الخسارة 🟢🎯\n"
    )
    await update.message.reply_text(welcome_message)

# دالة جلب البيانات مع فحص اللاحقات لضمان عدم حدوث خطأ
def fetch_stock_data(text):
    text = text.strip().upper()
    possible_symbols = []
    
    if text.isdigit():
        possible_symbols = [f"{text}.SR", f"{text}.SA", text]
    elif text.endswith("SR") and not text.endswith(".SR"):
        base = text[:-2].strip()
        possible_symbols = [f"{base}.SR", f"{base}.SA"]
    else:
        possible_symbols = [text, f"{text}.SR", f"{text}.SA"]

    for sym in possible_symbols:
        try:
            stock = yf.Ticker(sym)
            hist = stock.history(period="3mo")
            if not hist.empty and len(hist) > 0 and hist['Close'].iloc[-1] > 0:
                return hist, sym
        except Exception:
            continue
    return None, text

# حساب مؤشر القوة النسبية RSI
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

# دالة رسم الشارت الفني المطور ومناطق القرار
def generate_advanced_chart(hist, ticker_symbol, current_price, buy_zone_low, buy_zone_high, target_1, target_2, stop_loss, trend_text):
    fig, ax = plt.subplots(figsize=(11, 7), facecolor='#0f172a')
    ax.set_facecolor('#1e293b')

    # رسم خط السعر ومتوسط 50
    ax.plot(hist.index, hist['Close'], color='#38bdf8', linewidth=2.2, label='سعر الإغلاق')
    ema_50 = hist['Close'].ewm(span=50, adjust=False).mean()
    ax.plot(hist.index, ema_50, color='#fbbf24', linewidth=1.8, linestyle='--', label='متحرك 50 (EMA)')

    # مناطق الشطر والقرار المظللة
    ax.axhspan(buy_zone_low, buy_zone_high, color='#22c55e', alpha=0.15, label='منطقة الشراء (الدعم)')
    ax.axhspan(stop_loss, buy_zone_low, color='#ef4444', alpha=0.12, label='منطقة الخطر / وقف الخسارة')

    # الخطوط الإرشادية للأهداف ووقف الخسارة
    ax.axhline(y=target_1, color='#34d399', linestyle='-', linewidth=1.5, alpha=0.9, label=f'الهدف الأول: {target_1}')
    ax.axhline(y=target_2, color='#10b981', linestyle='-', linewidth=1.5, alpha=0.9, label=f'الهدف الثاني: {target_2}')
    ax.axhline(y=stop_loss, color='#f87171', linestyle='-', linewidth=1.5, alpha=0.9, label=f'وقف الخسارة: {stop_loss}')

    clean_symbol = ticker_symbol.replace('.SR', '').replace('.SA', '')
    ax.set_title(f"Technical Analysis Chart: {clean_symbol} | الاتجاه: {trend_text}", color='white', fontsize=12, fontweight='bold', pad=15)
    
    ax.tick_params(colors='white', labelsize=10)
    ax.grid(True, color='#334155', linestyle=':', alpha=0.6)
    
    legend = ax.legend(loc='upper left', facecolor='#0f172a', edgecolor='#334155', fontsize=9)
    for text in legend.get_texts():
        text.set_color('white')

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=180, facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    return buf

# معالجة طلب السهم من المستخدم
async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    await update.message.reply_text(f"⏳ جاري سحب البيانات والتحليل الفني للسهم `{text}` . جارٍ رسم الشارت المطور وإرساله... 📊")

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

        if current_price > ema_50 and rsi_val > 50:
            trend_text = "صاعد إيجابي 🟢"
        elif rsi_val < 30:
            trend_text = "تشبع بيعي (فرصة ارتداد) 🔵"
        else:
            trend_text = "هابط / تصحيحي 🔴"

        display_symbol = ticker_symbol.replace('.SR', '').replace('.SA', '')
        chart_buf = generate_advanced_chart(hist, ticker_symbol, current_price, buy_zone_low, buy_zone_high, target_1, target_2, stop_loss, trend_text)

        caption = (
            f"📊 **التقرير الفني الشامل للسهم:**\n"
            f"Tadawul: `{display_symbol}`\n\n"
            f"• **السعر الحالي:** `{current_price:.2f}` ريال\n"
            f"• **التغير:** `{change:+.2f}` (`{change_pct:+.2f}%`)\n\n"
            f"🎯 **مستويات التداول:**\n"
            f"• 🟢 **منطقة الشراء:** `{buy_zone_low} - {buy_zone_high}`\n"
            f"• 🎯 **الهدف الأول:** `{target_1}` | **الهدف الثاني:** `{target_2}`\n"
            f"• 🛑 **وقف الخسارة:** `{stop_loss}`\n\n"
            f"📉 **المؤشرات:** RSI: `{rsi_val:.1f}`"
        )

        await update.message.reply_photo(photo=InputFile(chart_buf, filename="chart.png"), caption=caption, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error handling stock {text}: {e}")
        await update.message.reply_text("حدث خطأ أثناء معالجة الشارت الفني.")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

    # تشغيل سيرفر الويب في خلفية منفصلة لمنع خمول البوت
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_stock))

    print("Bot is running continuously with Keep-Alive Web Server...")
    application.run_polling()

if __name__ == '__main__':
    main()
