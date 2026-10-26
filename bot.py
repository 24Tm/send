import os
import threading
import telebot
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask

# إعداد الـ Flask للحفاظ على بقاء البوت مستيقظاً على Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is active and running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# إعداد توكن البوت
TOKEN = "7963428987:AAEI_Z5bE6ZJmY2H0H7iC2l5Y9v2w3x4y5z" # استبدل التوكن إذا لزم الأمر، أو دعه كما هو إذا كان صحيحاً
bot = telebot.TeleBot(TOKEN)

# قائمة الأسهم المفضلة لفحصها عند طلب "هدف"
WATCHLIST = [
    "1120.SR", "1180.SR", "2222.SR", "1211.SR", "2010.SR", 
    "1301.SR", "4200.SR", "7010.SR", "1820.SR", "4300.SR"
]

def calculate_indicators(df):
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    
    # Bollinger Bands
    sma20 = df['Close'].rolling(window=20).mean()
    std20 = df['Close'].rolling(window=20).std()
    df['BB_UP'] = sma20 + (std20 * 2)
    df['BB_DOWN'] = sma20 - (std20 * 2)
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']

def get_stock_data(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="6mo")
        if df.empty:
            return None
        calculate_indicators(df)
        return df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

def generate_chart(df, symbol):
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 10), sharex=True, gridspec_kw={'height_ratios': [3, 1, 1]})
    
    # الرسم الأول: الشموع والمؤشرات
    ax1.plot(df.index, df['Close'], label='Close', color='blue', alpha=0.5)
    ax1.plot(df.index, df['EMA50'], label='EMA 50', color='orange')
    ax1.plot(df.index, df['BB_UP'], label='BB Upper', color='gray', linestyle='--')
    ax1.plot(df.index, df['BB_DOWN'], label='BB Lower', color='gray', linestyle='--')
    ax1.set_title(f"Institutional Analysis: {symbol}", fontsize=14, fontweight='bold', color='navy')
    ax1.set_ylabel("Price (SAR)")
    ax1.legend(loc='upper left')
    ax1.grid(True, linestyle=':', alpha=0.6)
    
    # الرسم الثاني: مؤشر RSI
    ax2.plot(df.index, df['RSI'], label='RSI (14)', color='purple')
    ax2.axhline(70, color='red', linestyle='--', alpha=0.5)
    ax2.axhline(30, color='green', linestyle='--', alpha=0.5)
    ax2.set_ylabel("RSI")
    ax2.legend(loc='upper left')
    ax2.grid(True, linestyle=':', alpha=0.6)
    
    # الرسم الثالث: مؤشر MACD
    ax3.plot(df.index, df['MACD'], label='MACD', color='blue')
    ax3.plot(df.index, df['Signal'], label='Signal', color='red')
    ax3.bar(df.index, df['Hist'], label='Histogram', color='gray', alpha=0.5)
    ax3.set_ylabel("MACD")
    ax3.legend(loc='upper left')
    ax3.grid(True, linestyle=':', alpha=0.6)
    
    plt.tight_layout()
    chart_path = f"/tmp/{symbol.replace('.SR', '')}_chart.png"
    plt.savefig(chart_path, dpi=150)
    plt.close()
    return chart_path

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً بك! استخدم رمز السهم (مثل 1820 أو 2222) للحصول على التحليل الفني، أو اكتب **هدف** لفحص أقوى الفرص.")

@bot.message_handler(func=lambda message: message.text and message.text.strip() == "هدف")
def scan_targets(message):
    bot.reply_to(message, "🔍 جاري فحص السوق والبحث عن أقوى فرص الانطلاق (هدف)... يرجى الانتظار قليلاً.")
    found = False
    for symbol in WATCHLIST:
        df = get_stock_data(symbol)
        if df is not None and not df.empty:
            last_rsi = df['RSI'].iloc[-1]
            last_close = df['Close'].iloc[-1]
            ema50 = df['EMA50'].iloc[-1]
            
            # شرط الفرصة: قريب من المتوسط أو RSI ممتاز
            if last_rsi < 45 or last_close > ema50:
                found = True
                change = last_close - df['Close'].iloc[-2]
                change_pct = (change / df['Close'].iloc[-2]) * 100
                
                buy_zone_low = round(last_close * 0.98, 2)
                buy_zone_high = round(last_close * 1.00, 2)
                target1 = round(last_close * 1.05, 2)
                target2 = round(last_close * 1.10, 2)
                stop_loss = round(last_close * 0.95, 2)
                
                response = (
                    f"🏛 **التقرير المؤسسي وفرصة الانطلاق:**\n\n"
                    f"📊 **Tadawul:** {symbol.replace('.SR', '')}\n\n"
                    f"• السعر الحالي: **{round(last_close, 2)} ريال**\n"
                    f"• التغير: **{'+' if change >= ''}{round(change, 2)} ({round(change_pct, 2)}%)**\n\n"
                    f"🎯 **مستويات التداول الرئيسية:**\n"
                    f"• 🟢 منطقة الشراء: **{buy_zone_low} - {buy_zone_high}**\n"
                    f"• 🎯 الهدف الأول: **{target1}** | الهدف الثاني: **{target2}**\n"
                    f"• 🛑 وقف الخسارة: **{stop_loss}**\n\n"
                    f"📉 **المؤشرات الفنية:** RSI: {round(last_rsi, 1)}\n"
                    f"🚀 | **فرصة قوية للانطلاق**"
                )
                
                chart_path = generate_chart(df, symbol)
                with open(chart_path, 'rb') as photo:
                    bot.send_photo(message.chat.id, photo, caption=response, parse_mode="Markdown")
                break # نرسل أول فرصة قوية مطابقة للمعيار كبداية
                
    if not found:
        bot.reply_to(message, "لم يتم العثور على فرص مطابقة للمعايير بدقة في القائمة حالياً.")

@bot.message_handler(func=lambda message: True)
def handle_stock_query(message):
    text = message.text.strip().upper()
    symbol = text + ".SR" if not text.endswith(".SR") else text
    
    bot.send_reply = bot.reply_to(message, f"⏳ جاري جلب البيانات والتحليل الفني للسهم {symbol}...")
    df = get_stock_data(symbol)
    
    if df is None or df.empty:
        bot.reply_to(message, "❌ لم يتم العثور على بيانات لهذا السهم. تأكد من صحة رمز السهم (مثال: 1820).")
        return
        
    last_close = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2]
    change = last_close - prev_close
    change_pct = (change / prev_close) * 100
    last_rsi = df['RSI'].iloc[-1]
    
    buy_zone_low = round(last_close * 0.98, 2)
    buy_zone_high = round(last_close * 1.00, 2)
    target1 = round(last_close * 1.05, 2)
    target2 = round(last_close * 1.10, 2)
    stop_loss = round(last_close * 0.95, 2)
    
    response = (
        f"🏛 **التقرير المؤسسي للسهم:**\n\n"
        f"📊 **Tadawul:** {symbol.replace('.SR', '')}\n\n"
        f"• السعر الحالي: **{round(last_close, 2)} ريال**\n"
        f"• التغير: **{'+' if change >= 0 else ''}{round(change, 2)} ({'+' if change_pct >= 0 else ''}{round(change_pct, 2)}%)**\n\n"
        f"🎯 **مستويات التداول الرئيسية:**\n"
        f"• 🟢 منطقة الشراء: **{buy_zone_low} - {buy_zone_high}**\n"
        f"• 🎯 الهدف الأول: **{target1}** | الهدف الثاني: **{target2}**\n"
        f"• 🛑 وقف الخسارة: **{stop_loss}**\n\n"
        f"📉 **المؤشرات الفنية:** RSI: {round(last_rsi, 1)}\n"
        f"📈 **التحليل:** {'منطقة ارتداد إيجابية' if last_rsi < 45 else 'زخم صاعد مستمر'}"
    )
    
    chart_path = generate_chart(df, symbol)
    with open(chart_path, 'rb') as photo:
        bot.send_photo(message.chat.id, photo, caption=response, parse_mode="Markdown")

if __name__ == "__main__":
    # تشغيل خادم الويب Flask في مسار منفصل لتلبية متطلبات الاستضافة
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    # تشغيل البوت
    print("Bot is starting...")
    bot.infinity_polling()