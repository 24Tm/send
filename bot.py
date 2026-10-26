import os
import threading
import telebot
from telebot import types
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask

# ==================== إعداد خادم الويب (Keep-Alive) ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is active and running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ==================== إعدادات بوت تيليقرام ====================
TOKEN = "8961540572:AAGLzgU3PwqXopo_BGyai7t4PzJf1cB-eGs"
bot = telebot.TeleBot(TOKEN)

WATCHLIST = [
    "1120.SR", "1180.SR", "2222.SR", "1211.SR", "2010.SR", 
    "1301.SR", "4200.SR", "7010.SR", "1820.SR", "4300.SR"
]

def calculate_indicators(df):
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    sma20 = df['Close'].rolling(window=20).mean()
    std20 = df['Close'].rolling(window=20).std()
    df['BB_UP'] = sma20 + (std20 * 2)
    df['BB_DOWN'] = sma20 - (std20 * 2)
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']

def get_stock_data(symbol, interval="1d"):
    try:
        ticker = yf.Ticker(symbol)
        period = "2y" if interval == "1wk" else "6mo"
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return None
        calculate_indicators(df)
        return df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

def generate_chart(df, symbol, interval="1d"):
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 10), sharex=True, gridspec_kw={'height_ratios': [3, 1, 1]})
    tf_label = "Weekly (أسبوعي)" if interval == "1wk" else "Daily (يومي)"
    
    ax1.plot(df.index, df['Close'], label='Close', color='blue', alpha=0.5)
    ax1.plot(df.index, df['EMA50'], label='EMA 50', color='orange')
    ax1.plot(df.index, df['BB_UP'], label='BB Upper', color='gray', linestyle='--')
    ax1.plot(df.index, df['BB_DOWN'], label='BB Lower', color='gray', linestyle='--')
    ax1.set_title(f"Institutional Analysis: {symbol} [{tf_label}]", fontsize=14, fontweight='bold', color='navy')
    ax1.set_ylabel("Price (SAR)")
    ax1.legend(loc='upper left')
    ax1.grid(True, linestyle=':', alpha=0.6)
    
    ax2.plot(df.index, df['RSI'], label='RSI (14)', color='purple')
    ax2.axhline(70, color='red', linestyle='--', alpha=0.5)
    ax2.axhline(30, color='green', linestyle='--', alpha=0.5)
    ax2.set_ylabel("RSI")
    ax2.legend(loc='upper left')
    ax2.grid(True, linestyle=':', alpha=0.6)
    
    ax3.plot(df.index, df['MACD'], label='MACD', color='blue')
    ax3.plot(df.index, df['Signal'], label='Signal', color='red')
    ax3.bar(df.index, df['Hist'], label='Histogram', color='gray', alpha=0.5)
    ax3.set_ylabel("MACD")
    ax3.legend(loc='upper left')
    ax3.grid(True, linestyle=':', alpha=0.6)
    
    plt.tight_layout()
    chart_path = f"/tmp/{symbol.replace('.SR', '')}_{interval}_chart.png"
    plt.savefig(chart_path, dpi=150)
    plt.close()
    return chart_path

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_target = types.KeyboardButton("🎯 هدف (فحص الفرص)")
    btn_daily = types.KeyboardButton("📈 السوق السعودي اليومي")
    btn_weekly = types.KeyboardButton("📅 التحليل الأسبوعي طويل الأجل")
    btn_help = types.KeyboardButton("⚙️ المساعدة")
    markup.add(btn_target, btn_daily, btn_weekly, btn_help)
    return markup

def get_inline_keyboard(symbol):
    markup = types.InlineKeyboardMarkup()
    btn_d = types.InlineKeyboardButton("📊 يومي (Daily)", callback_data=f"tf_1d_{symbol}")
    btn_w = types.InlineKeyboardButton("📆 أسبوعي (Weekly)", callback_data=f"tf_1wk_{symbol}")
    markup.add(btn_d, btn_w)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "🏛 **أهلاً بك في نظام التحليل المؤسسي للسوق السعودي (Tadawul)**\n\n"
        "استخدم الأزرار السريعة أسفل الشاشة أو أرسل رمز السهم مباشرة (مثال: `1820` أو `2222`)."
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text and "المساعدة" in message.text)
def send_help_menu(message):
    help_text = (
        "⚙️ **دليل الاستخدام:**\n"
        "• اضغط على **🎯 هدف** لفحص قائمة الأسهم بحثاً عن فرص الانطلاق.\n"
        "• اكتب رمز أي سهم (مثل `1120` أو `2222`) للحصول على تقريره الفني مع أزرار التبديل الفوري.\n"
        "• البوت يعمل على مدار الساعة 24/7."
    )
    bot.reply_to(message, help_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text and "هدف" in message.text)
def scan_targets(message):
    bot.reply_to(message, "🔍 جاري فحص السوق والبحث عن أقوى فرص الانطلاق (هدف)... يرجى الانتظار قليلاً.", reply_markup=get_main_keyboard())
    found = False
    for symbol in WATCHLIST:
        df = get_stock_data(symbol, interval="1d")
        if df is not None and not df.empty:
            last_rsi = df['RSI'].iloc[-1]
            last_close = df['Close'].iloc[-1]
            ema50 = df['EMA50'].iloc[-1]
            
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
                    f"🏛 **فرصة انطلاق استثمارية (هدف):**\n\n"
                    f"📊 **Tadawul:** {symbol.replace('.SR', '')}\n\n"
                    f"• السعر الحالي: **{round(last_close, 2)} ريال**\n"
                    f"• التغير: **{'+' if change >= 0 else ''}{round(change, 2)} ({round(change_pct, 2)}%)**\n\n"
                    f"🎯 **مستويات التداول الرئيسية:**\n"
                    f"• 🟢 منطقة الشراء: **{buy_zone_low} - {buy_zone_high}**\n"
                    f"• 🎯 الهدف الأول: **{target1}** | الهدف الثاني: **{target2}**\n"
                    f"• 🛑 وقف الخسارة: **{stop_loss}**\n\n"
                    f"📉 **المؤشرات:** RSI: {round(last_rsi, 1)}"
                )
                
                chart_path = generate_chart(df, symbol, interval="1d")
                with open(chart_path, 'rb') as photo:
                    bot.send_photo(message.chat.id, photo, caption=response, parse_mode="Markdown", reply_markup=get_inline_keyboard(symbol))
                break
                
    if not found:
        bot.reply_to(message, "لم يتم العثور على فرص مطابقة للمعايير بدقة في القائمة حالياً.", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text and ("السوق السعودي اليومي" in message.text or "التحليل الأسبوعي" in message.text))
def handle_quick_menus(message):
    if "اليومي" in message.text:
        symbol = "2222.SR"
    else:
        symbol = "1120.SR"
    
    interval = "1wk" if "الأسبوعي" in message.text else "1d"
    tf_name = "أسبوعي طويل الأجل" if interval == "1wk" else "يومي"
    
    bot.reply_to(message, f"⏳ جاري جلب التحليل الفني بفاصل ({tf_name}) للسهم الافتراضي {symbol.replace('.SR', '')}...")
    df = get_stock_data(symbol, interval=interval)
    
    if df is None or df.empty:
        bot.reply_to(message, "❌ تعذر جلب البيانات حالياً.", reply_markup=get_main_keyboard())
        return
        
    last_close = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2]
    change = last_close - prev_close
    change_pct = (change / prev_close) * 100
    last_rsi = df['RSI'].iloc[-1]
    
    response = (
        f"🏛 **تقرير التحليل المؤسسي ({tf_name}):**\n\n"
        f"📊 **Tadawul:** {symbol.replace('.SR', '')}\n\n"
        f"• السعر الحالي: **{round(last_close, 2)} ريال**\n"
        f"• التغير: **{'+' if change >= 0 else ''}{round(change, 2)} ({round(change_pct, 2)}%)**\n\n"
        f"📉 **المؤشرات الفنية:** RSI: {round(last_rsi, 1)}"
    )
    
    chart_path = generate_chart(df, symbol, interval=interval)
    with open(chart_path, 'rb') as photo:
        bot.send_photo(message.chat.id, photo, caption=response, parse_mode="Markdown", reply_markup=get_inline_keyboard(symbol))

@bot.callback_query_handler(func=lambda call: call.data.startswith("tf_"))
def handle_inline_timeframe(call):
    parts = call.data.split("_")
    interval = parts[1]
    symbol = parts[2]
    
    tf_text = "الإطار الأسبوعي (Weekly)" if interval == "1wk" else "الإطار اليومي (Daily)"
    bot.answer_callback_query(call.id, text=f"جاري التحديث إلى {tf_text}...")
    
    df = get_stock_data(symbol, interval=interval)
    if df is None or df.empty:
        bot.send_message(call.message.chat.id, "❌ حدث خطأ أثناء جلب البيانات الجديدة.")
        return
        
    last_close = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2]
    change = last_close - prev_close
    change_pct = (change / prev_close) * 100
    last_rsi = df['RSI'].iloc[-1]
    
    response = (
        f"🏛 **تحديث التحليل المؤسسي [{tf_text}]:**\n\n"
        f"📊 **Tadawul:** {symbol.replace('.SR', '')}\n\n"
        f"• السعر الحالي: **{round(last_close, 2)} ريال**\n"
        f"• التغير: **{'+' if change >= 0 else ''}{round(change, 2)} ({round(change_pct, 2)}%)**\n\n"
        f"📉 **المؤشرات الفنية:** RSI: {round(last_rsi, 1)}"
    )
    
    chart_path = generate_chart(df, symbol, interval=interval)
    with open(chart_path, 'rb') as photo:
        bot.send_photo(call.message.chat.id, photo, caption=response, parse_mode="Markdown", reply_markup=get_inline_keyboard(symbol))

@bot.message_handler(func=lambda message: True)
def handle_stock_query(message):
    text = message.text.strip().upper()
    symbol = text + ".SR" if not text.endswith(".SR") else text
    
    bot.reply_to(message, f"⏳ جاري جلب البيانات والتحليل الفني للسهم {symbol}...", reply_markup=get_main_keyboard())
    df = get_stock_data(symbol, interval="1d")
    
    if df is None or df.empty:
        bot.reply_to(message, "❌ لم يتم العثور على بيانات لهذا السهم. تأكد من صحة رمز السهم (مثال: 1820).", reply_markup=get_main_keyboard())
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
        f"• التغير: **{'+' if change >= 0 else ''}{round(change, 2)} ({round(change_pct, 2)}%)**\n\n"
        f"🎯 **مستويات التداول الرئيسية:**\n"
        f"• 🟢 منطقة الشراء: **{buy_zone_low} - {buy_zone_high}**\n"
        f"• 🎯 الهدف الأول: **{target1}** | الهدف الثاني: **{target2}**\n"
        f"• 🛑 وقف الخسارة: **{stop_loss}**\n\n"
        f"📉 **المؤشرات الفنية:** RSI: {round(last_rsi, 1)}"
    )
    
    chart_path = generate_chart(df, symbol, interval="1d")
    with open(chart_path, 'rb') as photo:
        bot.send_photo(message.chat.id, photo, caption=response, parse_mode="Markdown", reply_markup=get_inline_keyboard(symbol))

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    print("Bot and Flask keep-alive server are starting...")
    bot.infinity_polling()
