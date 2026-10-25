import os
import logging
import io
import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use('Agg') # لمنع فتح واجهة رسومية على السيرفر
import matplotlib.pyplot as plt
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

WATCHLIST_SYMBOLS = ["1120.SR", "1180.SR", "2222.SR", "1010.SR", "1820.SR"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "مرحباً بك يا غالي! 🚀\n\n"
        "أنا بوت تحليل الأسهم المطور. أرسل لي أي رقم أو رمز سهم (مثل `1820`) وسأعطيك:\n\n"
        "• **صورة الشارت الفني المطور** جاهزة للنشر 📊\n"
        "• السعر الحالي ونسبة التغير ومناطق الدخول والخروج 🟢🎯\n"
        "• مؤشر RSI واتجاه المتوسط EMA 📈\n\n"
        "💡 **الأوامر:**\n"
        "• أرسل رقم السهم مباشرة للحصول على التحليل مع الشارت كصورة.\n"
        "• أرسل الأمر `/monitor` لتفعيل التنبيهات التلقائية في الخلفية."
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

def generate_chart_image(hist, ticker_symbol, current_price, buy_zone_low, target_1, stop_loss):
    """دالة لرسم الشارت وتصديره كصورة جاهزة"""
    fig, ax = plt.subplots(figsize=(10, 6), facecolor='#121212')
    ax.set_facecolor('#1e1e1e')

    # رسم خط السعر
    ax.plot(hist.index, hist['Close'], color='#00ffcc', linewidth=2, label='السعر (Close)')
    
    # حساب المتوسط المتحرك EMA 50 للرسم
    ema_50 = hist['Close'].ewm(span=50, adjust=False).mean()
    ax.plot(hist.index, ema_50, color='#ff9900', linewidth=1.5, linestyle='--', label='EMA 50')

    # خطوط المستويات الحسابية
    ax.axhline(y=current_price, color='#ffffff', linestyle=':', alpha=0.7, label=f'السعر الحالي: {current_price}')
    ax.axhline(y=buy_zone_low, color='#00ff00', linestyle='-', alpha=0.8, label=f'منطقة الشراء: {buy_zone_low}')
    ax.axhline(y=target_1, color='#00bfff', linestyle='-', alpha=0.8, label=f'الهدف الأول: {target_1}')
    ax.axhline(y=stop_loss, color='#ff4d4d', linestyle='-', alpha=0.8, label=f'وقف الخسارة: {stop_loss}')

    clean_symbol = ticker_symbol.replace('.SR', '').replace('.SA', '')
    ax.set_title(f"Tadawul Analysis: {clean_symbol}", color='white', fontsize=14, fontweight='bold', pad=15)
    ax.tick_params(colors='white', labelsize=10)
    ax.grid(True, color='#333333', linestyle='--', alpha=0.5)
    
    legend = ax.legend(loc='upper left', facecolor='#2d2d2d', edgecolor='none')
    for text in legend.get_texts():
        text.set_color('white')

    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    return buf

async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    await update.message.reply_text(f"جاري سحب البيانات ورسم الشارت الفني للسهم `{text}` ... ⏳")

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
        
        display_symbol = f"Tadawul: {ticker_symbol.replace('.SR', '').replace('.SA', '')}"

        # توليد الشارت كصورة
        chart_buf = generate_chart_image(hist, ticker_symbol, current_price, buy_zone_low, target_1, stop_loss)

        # النص التوضيحي المرافق للصورة
        caption = (
            f"📊 **التقرير الفني الشامل للسهم: `{display_symbol}`**\n\n"
            f"• **السعر الحالي:** `{current_price:.2f}` ريال\n"
            f"• **التغير:** `{change:+.2f} ({change_pct:+.2f}%)`\n\n"
            f"🎯 **مستويات التداول:**\n"
            f"• 🟢 **منطقة الشراء:** `{buy_zone_low} - {buy_zone_high}`\n"
            f"• 🎯 **الهدف الأول:** `{target_1}` | **الهدف الثاني:** `{target_2}`\n"
            f"• 🛑 **وقف الخسارة:** `{stop_loss}`\n\n"
            f"📉 **الزخم:** RSI: `{rsi_val:.1f}` ({rsi_status}) | الاتجاه: {trend_status}\n\n"
            f"📸 *هذه الصورة والشارت جاهزتان للمشاركة والنشر مباشرة!*"
        )

        # إرسال الصورة ومعها النص
        await update.message.reply_photo(photo=InputFile(chart_buf, filename="chart.png"), caption=caption, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error handling stock {text}: {e}")
        await update.message.reply_text("حدث خطأ أثناء رسم الشارت ومعالجة بيانات السهم.")

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
                    f"• يرتكز قرب الدعم بنسبة `{distance_from_support:.2f}%` مع RSI منخفض (`{rsi_val:.1f}`)."
                )
                await context.bot.send_message(chat_id=chat_id, text=alert_msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Background check error for {sym}: {e}")

async def start_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if current_jobs:
        await update.message.reply_text("المراقبة التلقائية مفعلة لديك مسبقاً! 🟢")
        return

    context.job_queue.run_repeating(check_market_explosions, interval=3600, first=10, chat_id=chat_id, name=str(chat_id))
    await update.message.reply_text("✅ تم تفعيل **المراقبة الذاتية** بنجاح وسأراسلك بالفرص فوراً!")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("monitor", start_monitoring))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_stock))

    print("Bot is running with Chart generation feature...")
    application.run_polling()

if __name__ == '__main__':
    main()