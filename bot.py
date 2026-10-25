import os
import logging
import io
import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

WATCHLIST_SYMBOLS = ["1120.SR", "1180.SR", "2222.SR", "1010.SR", "1820.SR"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "مرحباً بك يا غالي! 🚀\n\n"
        "أنا بوت تحليل الأسهم المطور. أرسل لي أي رمز سهم (مثل `1820`) وسأعطيك:\n\n"
        "• **شارت فني مطور ومظلل بمناطق القرار** 📊\n"
        "• اتجاه السوق المتوقع ومستويات الدخول والخروج بدقة 🟢🎯\n"
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

def generate_advanced_chart(hist, ticker_symbol, current_price, buy_zone_low, buy_zone_high, target_1, target_2, stop_loss, trend_text):
    """دالة رسم الشارت المتقدم مع مناطق القرار والاتجاهات الواضحة"""
    fig, ax = plt.subplots(figsize=(11, 7), facecolor='#0f172a')
    ax.set_facecolor('#1e293b')

    # رسم خط السعر التاريخي
    ax.plot(hist.index, hist['Close'], color='#38bdf8', linewidth=2.2, label='سعر الإغلاق')
    
    # المتوسط المتحرك EMA 50
    ema_50 = hist['Close'].ewm(span=50, adjust=False).mean()
    ax.plot(hist.index, ema_50, color='#fbbf24', linewidth=1.8, linestyle='--', label='متحرك 50 (EMA)')

    # تظليل منطقة الشراء ومنطقة المخاطرة على الشارت لسهولة اتخاذ القرار
    ax.axhspan(buy_zone_low, buy_zone_high, color='#22c55e', alpha=0.15, label='منطقة الشراء (الدعم)')
    ax.axhspan(stop_loss, buy_zone_low, color='#ef4444', alpha=0.12, label='منطقة الخطر / وقف الخسارة')

    # خطوط الأهداف ومستويات التداول الواضحة
    ax.axhline(y=target_1, color='#34d399', linestyle='-', linewidth=1.5, alpha=0.9, label=f'الهدف الأول: {target_1}')
    ax.axhline(y=target_2, color='#10b981', linestyle='-', linewidth=1.5, alpha=0.9, label=f'الهدف الثاني: {target_2}')
    ax.axhline(y=stop_loss, color='#f87171', linestyle='-', linewidth=1.5, alpha=0.9, label=f'وقف الخسارة: {stop_loss}')

    clean_symbol = ticker_symbol.replace('.SR', '').replace('.SA', '')
    
    # عنوان الشارت مع الاتجاه المتوقع
    ax.set_title(f"Tadawul Decision Chart: {clean_symbol} | الاتجاه: {trend_text}", color='white', fontsize=13, fontweight='bold', pad=15)
    
    ax.tick_params(colors='white', labelsize=10)
    ax.grid(True, color='#334155', linestyle=':', alpha=0.6)
    
    # ترتيب الليبلز بشكل احترافي
    legend = ax.legend(loc='upper left', facecolor='#0f172a', edgecolor='#334155', fontsize=9)
    for text in legend.get_texts():
        text.set_color('white')

    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=180, facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    return buf

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    await update.message.reply_text(f"⏳ جاري تحليل السهم `{text}` ورسم خريطة القرار الفنية...")

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

        # تحديد الاتجاه والقرار بناءً على المعطيات
        if current_price > ema_50 and rsi_val > 50:
            trend_text = "صاعد إيجابي 🟢 (زخم شراء)"
        elif rsi_val < 30:
            trend_text = "تشبع بيعي - فرصة ارتداد مرتقبة 🔵"
        else:
            trend_text = "هابط / تصحيحي 🔴 (مراقبة الدعم)"

        rsi_status = "تشبع شرائي ⚠️" if rsi_val > 70 else ("تشبع بيعي (فرصة ارتداد) 🟢" if rsi_val < 30 else "متوازن ⚖️")
        display_symbol = f"Tadawul: {ticker_symbol.replace('.SR', '').replace('.SA', '')}"

        # توليد الشارت المتقدم المظلل
        chart_buf = generate_advanced_chart(hist, ticker_symbol, current_price, buy_zone_low, buy_zone_high, target_1, target_2, stop_loss, trend_text)

        caption = (
            f"📊 **خريطة القرار الفني للسهم: `{display_symbol}`**\n\n"
            f"• **السعر الحالي:** `{current_price:.2f}` ريال `({change:+.2f}%)`\n\n"
            f"🎯 **مستويات اتخاذ القرار:**\n"
            f"• 🟢 **منطقة الشراء (الدعم):** `{buy_zone_low} - {buy_zone_high}`\n"
            f"• 🎯 **الأهداف المتوقعة:** الهدف 1 (`{target_1}`) | الهدف 2 (`{target_2}`)\n"
            f"• 🛑 **حائط وقف الخسارة:** `{stop_loss}`\n\n"
            f"📉 **الرؤية والزخم:**\n"
            f"• RSI: `{rsi_val:.1f}` ({rsi_status})\n"
            f"• التقييم العام: **{trend_text}**\n\n"
            f"💡 *الصورة أعلاه مصممة لتوضيح مناطق السيولة والدعم لتساعدك في اتخاذ القرار مباشرة.*"
        )

        await update.message.reply_photo(photo=InputFile(chart_buf, filename="decision_chart.png"), caption=caption, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error handling stock {text}: {e}")
        await update.message.reply_text("حدث خطأ أثناء معالجة الشارت الفني.")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_stock))

    print("Bot running with Advanced Decision Chart...")
    application.run_polling()

if __name__ == '__main__':
    main()
