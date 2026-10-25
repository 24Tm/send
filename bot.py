import os
import logging
import io
import threading
import requests
import pandas as pd
import numpy as np
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
    return "Bot is active and running 24/7[span_0](start_span)!"[span_0](end_span)

def run_web():
    app_web.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# دالة الترحيب التفاعلية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "مرحباً بك يا غالي في مستشارك المالي المؤسسي! 🚀\n\n"
        "أنا بوت تحليل الأسهم السعودية (Tadawul). يمكنك استخدام الخيارات التالية:\n\n"
        "• **أرسل رمز أي سهم** (مثل `1120` أو `1820`) لتحليله فوراً 📊\n"
        "• **اكتب كلمة `هدف`** لأقوم بالبحث في السوق عن أقوى الفرص الإيجابية والأسهم المرشحة للانطلاق للأعلى 🟢🎯\n"
    )
    await update.message.reply_text(welcome_message)

# دالة جلب البيانات مباشرة عبر API
def fetch_stock_data_json(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=3mo&interval=1d"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        data = response.json()
        result = data['chart']['result']
        if not result:
            return None
        
        timestamps = result[0]['timestamp']
        quote = result[0]['indicators']['quote'][0]
        
        df = pd.DataFrame({
            'Open': quote.get('open', []),
            'High': quote.get('high', []),
            'Low': quote.get('low', []),
            'Close': quote.get('close', []),
            'Volume': quote.get('volume', [])
        }, index=pd.to_datetime(timestamps, unit='s'))
        
        df.dropna(inplace=True)
        if not df.empty and df['Close'].iloc[-1] > 0:
            return df
    except Exception as e:
        logger.error(f"Error fetching JSON for {symbol}: {e}")
    return None

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
        df = fetch_stock_data_json(sym)
        if df is not None and not df.empty:
            return df, sym
            
    return None, text

# حساب المؤشرات الفنية المتقدمة
def calculate_indicators(df):
    close = df['Close']
    
    # RSI (14)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # Bollinger Bands (20, 2)
    sma_20 = close.rolling(window=20).mean()
    std_20 = close.rolling(window=20).std()
    upper_band = sma_20 + (std_20 * 2)
    lower_band = sma_20 - (std_20 * 2)
    
    # MACD (12, 26, 9)
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=9, adjust=False).mean()
    
    return rsi, upper_band, lower_band, sma_20, macd, signal_line

# دالة رسم الشارت المؤسسي الاحترافي (الشموع اليابانية + 3 لوحات)
def generate_institutional_chart(hist, ticker_symbol, current_price, buy_zone_low, buy_zone_high, target_1, target_2, stop_loss, trend_text):
    rsi, upper_band, lower_band, sma_20, macd, signal_line = calculate_indicators(hist)

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 11), facecolor='#0b0f19', 
                                         gridspec_kw={'height_ratios': [4, 1.2, 1.2]})
    
    # 1. اللوحة الأولى: السعر والشموع اليابانية ومناطق القرار
    ax1.set_facecolor('#111827')
    for i in range(len(hist)):
        op = hist['Open'].iloc[i]
        cl = hist['Close'].iloc[i]
        hi = hist['High'].iloc[i]
        lo = hist['Low'].iloc[i]
        color = '#22c55e' if cl >= op else '#ef4444'
        ax1.plot([i, i], [lo, hi], color=color, linewidth=1, alpha=0.8)
        ax1.bar(i, abs(cl - op), bottom=min(op, cl), color=color, width=0.65)

    ema_50 = hist['Close'].ewm(span=50, adjust=False).mean()
    ax1.plot(range(len(hist)), ema_50, color='#fbbf24', linewidth=1.5, linestyle='--', label='EMA 50')
    ax1.plot(range(len(hist)), upper_band, color='#a855f7', linewidth=1, linestyle=':', alpha=0.7, label='Bollinger Upper')
    ax1.plot(range(len(hist)), lower_band, color='#a855f7', linewidth=1, linestyle=':', alpha=0.7, label='Bollinger Lower')

    ax1.axhspan(buy_zone_low, buy_zone_high, color='#22c55e', alpha=0.15, label='منطقة الشراء (الدعم)')
    ax1.axhspan(stop_loss, buy_zone_low, color='#ef4444', alpha=0.12, label='منطقة الخطر / وقف الخسارة')

    ax1.axhline(y=target_1, color='#34d399', linestyle='-', linewidth=1.5, alpha=0.9, label=f'الهدف الأول: {target_1}')
    ax1.axhline(y=target_2, color='#10b981', linestyle='-', linewidth=1.5, alpha=0.9, label=f'الهدف الثاني: {target_2}')
    ax1.axhline(y=stop_loss, color='#f87171', linestyle='-', linewidth=1.5, alpha=0.9, label=f'وقف الخسارة: {stop_loss}')

    clean_symbol = ticker_symbol.replace('.SR', '').replace('.SA', '')
    ax1.set_title(f"Institutional Candlestick Analysis: {clean_symbol} | الاتجاه: {trend_text}", color='white', fontsize=12, fontweight='bold', pad=12)
    ax1.tick_params(colors='white', labelsize=9)
    ax1.grid(True, color='#1f2937', linestyle=':', alpha=0.7)
    
    legend1 = ax1.legend(loc='upper left', facecolor='#0b0f19', edgecolor='#374151', fontsize=8)
    for text in legend1.get_texts():
        text.set_color('white')

    # 2. اللوحة الثانية: RSI
    ax2.set_facecolor('#111827')
    ax2.plot(range(len(hist)), rsi, color='#38bdf8', linewidth=1.5, label='RSI (14)')
    ax2.axhline(70, color='#ef4444', linestyle='--', linewidth=1, alpha=0.7, label='تشبع شرائي (70)')
    ax2.axhline(30, color='#22c55e', linestyle='--', linewidth=1, alpha=0.7, label='تشبع بيعي (30)')
    ax2.set_ylim(0, 100)
    ax2.tick_params(colors='white', labelsize=8)
    ax2.grid(True, color='#1f2937', linestyle=':', alpha=0.7)
    legend2 = ax2.legend(loc='upper left', facecolor='#0b0f19', edgecolor='#374151', fontsize=7)
    for text in legend2.get_texts():
        text.set_color('white')

    # 3. اللوحة الثالثة: MACD
    ax3.set_facecolor('#111827')
    ax3.plot(range(len(hist)), macd, color='#38bdf8', linewidth=1.2, label='MACD')
    ax3.plot(range(len(hist)), signal_line, color='#fbbf24', linewidth=1.2, label='Signal')
    hist_macd = macd - signal_line
    ax3.bar(range(len(hist)), hist_macd, color=['#22c55e' if val >= 0 else '#ef4444' for val in hist_macd], alpha=0.6, label='Histogram')
    ax3.tick_params(colors='white', labelsize=8)
    ax3.grid(True, color='#1f2937', linestyle=':', alpha=0.7)
    legend3 = ax3.legend(loc='upper left', facecolor='#0b0f19', edgecolor='#374151', fontsize=7)
    for text in legend3.get_texts():
        text.set_color('white')

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=200, facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    return buf, rsi.iloc[-1]

# دالة تحليل ومعالجة السهم وإرسال التقرير
async def process_and_send_stock(update: Update, symbol_text: str):
    hist, ticker_symbol = fetch_stock_data(symbol_text)
    if hist is None or hist.empty:
        await update.message.reply_text(f"عذراً، لم أتمكن من العثور على بيانات للسهم: `{symbol_text}`.")
        return False

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

        ema_50 = hist['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
        trend_text = "صاعد إيجابي 🟢" if current_price > ema_50 else "تصحيحي / فرصة ارتداد 🔵"

        chart_buf, rsi_val = generate_institutional_chart(hist, ticker_symbol, current_price, buy_zone_low, buy_zone_high, target_1, target_2, stop_loss, trend_text)

        display_symbol = ticker_symbol.replace('.SR', '').replace('.SA', '')
        caption = (
            f"🏛️ **التقرير المؤسسي وفرصة الانطلاق:**\n"
            f"Tadawul: `{display_symbol}`\n\n"
            f"• **السعر الحالي:** `{current_price:.2f}` ريال\n"
            f"• **التغير:** `{change:+.2f}` (`{change_pct:+.2f}%`)\n\n"
            f"🎯 **مستويات التداول الرئيسية:**\n"
            f"• 🟢 **منطقة الشراء:** `{buy_zone_low} - {buy_zone_high}`\n"
            f"• 🎯 **الهدف الأول:** `{target_1}` | **الهدف الثاني:** `{target_2}`\n"
            f"• 🛑 **وقف الخسارة:** `{stop_loss}`\n\n"
            f"📉 **المؤشرات الفنية:** RSI: `{rsi_val:.1f}` | فرصة قوية للانطلاق 🚀"
        )

        await update.message.reply_photo(photo=InputFile(chart_buf, filename="institutional_chart.png"), caption=caption, parse_mode="Markdown")
        return True
    except Exception as e:
        logger.error(f"Error processing stock {symbol_text}: {e}")
        return False

# معالجة الرسائل الواردة (سواء رمز سهم أو أمر هدف)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()

    if text == "هدف" or text == "الاهداف" or text == "فرص":
        await update.message.reply_text("🔍 جاري مسح السوق السعودي وفحص الأسهم النشطة لاكتشاف أقوى فرص الانطلاق والارتداد...")
        
        # قائمة بأبرز الأسهم القيادية والنشطة في تداول لفحصها
        watchlist = ["1120", "1180", "2222", "1010", "1150", "2010", "1211", "4300"]
        found_count = 0

        for sym in watchlist:
            hist, ticker_symbol = fetch_stock_data(sym)
            if hist is not None and not hist.empty:
                rsi_val, _, _, _, macd, signal_line = calculate_indicators(hist)
                current_price = hist['Close'].iloc[-1]
                ema_50 = hist['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
                
                # شرط الفرصة القوية (إيجابي أو قرب تشبع بيعي بارتداد قوي)
                if current_price >= ema_50 or rsi_val < 45:
                    success = await process_and_send_stock(update, sym)
                    if success:
                        found_count += 1
                        if found_count >= 2: # نرسل أقوى فرصتين لعدم إزعاج المستخدم
                            break
        
        if found_count == 0:
            await update.message.reply_text("لم يتم العثور على فرص مطابقة بالشروط حالياً، حاول مرة أخرى لاحقاً.")
    else:
        # معالجة السهم الفردي المرسل
        await update.message.reply_text(f"⏳ جاري سحب البيانات وتحليل الشارت المؤسسي للسهم `{text}`... 📊")
        await process_and_send_stock(update, text)

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
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Bot is running continuously with Keep-Alive Web Server & Smart 'Hedaf' Feature...")
    application.run_polling()

if __name__ == '__main__':
    main()