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
import re
import json

# ==================== خادم الويب للحفاظ على التشغيل 24/7 ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Multi-Button Institutional Sniper Bot is active 24/7!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ==================== إعدادات بوت تيليقرام ====================
TOKEN = "8961540572:AAGLzgU3PwqXopo_BGyai7t4PzJf1cB-eGs"
bot = telebot.TeleBot(TOKEN)

ADMIN_ID = 000000000  # استبدل الأصفار بمعرفك الرقمي إن أردت

TADAWUL_WATCHLIST = [
    "1120.SR", "1180.SR", "2222.SR", "1211.SR", "2010.SR", 
    "1301.SR", "4200.SR", "7010.SR", "1820.SR", "4300.SR",
    "2380.SR", "4001.SR", "2240.SR", "4140.SR", "1010.SR",
    "1020.SR", "1150.SR", "2020.SR", "2060.SR", "2280.SR",
    "2310.SR", "3030.SR", "3050.SR", "4030.SR", "4050.SR",
    "4190.SR", "5110.SR", "6010.SR", "7020.SR", "8210.SR"
]

US_CHEAP_WATCHLIST = [
    "URG", "IBIO", "TVRD", "TNYA", "CNTB", 
    "NMRA", "GPUS", "BURU", "ATCH", "MKDW"
]

USERS_FILE = "global_elite_users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_user(message):
    users = load_users()
    user_id = str(message.chat.id)
    first_name = message.chat.first_name or "مستخدم"
    username = f"@{message.chat.username}" if message.chat.username else "بدون معرف"
    
    text = message.text if message.text else ""
    referred_by = None
    if text.startswith("/start REF_"):
        referred_by = text.split("_")[1]

    if user_id not in users:
        users[user_id] = {
            "name": first_name,
            "username": username,
            "id": user_id,
            "referred_by": referred_by,
            "referrals_count": 0
        }
        if referred_by and referred_by in users:
            users[referred_by]["referrals_count"] += 1
            
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=4)

def get_company_name(symbol):
    try:
        t = yf.Ticker(symbol)
        info = t.info
        name = info.get('longName') or info.get('shortName') or symbol.replace('.SR', '')
        return name
    except:
        return symbol.replace('.SR', '')

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
    
    # --- إعدادات الاستوكاستك الفعلية (5, 3, 3) ---
    low_5 = df['Low'].rolling(window=5).min()
    high_5 = df['High'].rolling(window=5).max()
    k_raw = 100 * ((df['Close'] - low_5) / (high_5 - low_5))
    df['Stoch_K'] = k_raw.rolling(window=3).mean()
    df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()
    
    # --- مؤشر MACD ---
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']
    df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()
    df['High_52w'] = df['High'].rolling(window=252, min_periods=20).max()
    
    # --- توليد إشارات التقاطع (Stoch 5,3,3 + MACD) تلقائياً على الشموع ---
    df['Buy_Signal'] = False
    for i in range(1, len(df)):
        k_prev, k_curr = df['Stoch_K'].iloc[i-1], df['Stoch_K'].iloc[i]
        d_prev, d_curr = df['Stoch_D'].iloc[i-1], df['Stoch_D'].iloc[i]
        h_prev, h_curr = df['Hist'].iloc[i-1], df['Hist'].iloc[i]
        
        if not pd.isna(k_prev) and not pd.isna(k_curr):
            stoch_cross = (k_prev <= d_prev) and (k_curr > d_curr)
            macd_ok = (h_curr > h_prev) or (h_curr > 0)
            if stoch_cross and macd_ok:
                df.iat[i, df.columns.get_loc('Buy_Signal')] = True

def get_stock_data(symbol, interval="1d"):
    try:
        ticker = yf.Ticker(symbol)
        period = "1y" if interval == "1wk" else "6mo"
        df = ticker.history(period=period, interval=interval)
        if df is None or df.empty or len(df) < 5:
            return None
        df = df.dropna(subset=['Close'])
        calculate_indicators(df)
        return df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

def generate_professional_chart(df, symbol, interval="1d", entry_low=None, entry_high=None):
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 11), sharex=True, gridspec_kw={'height_ratios': [3, 1, 1]})
    tf_name = "الإطار الأسبوعي (Weekly)" if interval == "1wk" else "الإطار اليومي (Daily)"
    clean_symbol = symbol.replace('.SR', '')
    comp_name = get_company_name(symbol)
    
    fig.patch.set_facecolor('#0f172a')
    for ax in [ax1, ax2, ax3]:
        ax.set_facecolor('#1e293b')
        ax.tick_params(colors='white', labelsize=10)
        ax.grid(True, linestyle='--', alpha=0.2, color='white')
        for spine in ax.spines.values():
            spine.set_color('#334155')

    ax1.plot(df.index, df['Close'], label='سعر الإغلاق', color='#38bdf8', linewidth=1.5)
    ax1.plot(df.index, df['EMA50'], label='متوسط 50 (EMA)', color='#fbbf24', linewidth=1.2)
    ax1.plot(df.index, df['BB_UP'], label='بولينجر العرضي', color='#94a3b8', linestyle=':', alpha=0.7)
    ax1.plot(df.index, df['BB_DOWN'], color='#94a3b8', linestyle=':', alpha=0.7)
    
    # --- رسم أسهم الإشارات (Buy Signals) على الشارت الرئيسي ---
    buy_signals = df[df['Buy_Signal'] == True]
    if not buy_signals.empty:
        ax1.scatter(buy_signals.index, buy_signals['Low'] * 0.98, marker='^', color='#22c55e', s=120, zorder=5, label='إشارة شراء (Stoch+MACD)')

    if entry_low and entry_high:
        ax1.axhspan(entry_low, entry_high, color='#22c55e', alpha=0.25, label='منطقة الدخول الموصى بها')

    ax1.set_title(f"إشارات الدخول المؤسسية | {comp_name} [{clean_symbol}] - {tf_name}", fontsize=12, fontweight='bold', color='white', pad=10)
    ax1.set_ylabel("السعر", color='white', fontsize=10)
    leg1 = ax1.legend(loc='upper left', facecolor='#0f172a', edgecolor='none', fontsize=8)
    for text in leg1.get_texts():
        text.set_color('white')

    # مؤشر الاستوكاستك (5,3,3) الفرعي الثاني بدلاً من RSI القديم للتوضيح الدقيق
    ax2.plot(df.index, df['Stoch_K'], label='%K (5,3,3)', color='#f97316', linewidth=1.2)
    ax2.plot(df.index, df['Stoch_D'], label='%D (3)', color='#38bdf8', linewidth=1.2)
    ax2.axhline(80, color='#ef4444', linestyle='--', alpha=0.7, label='تشبع شرائي (80)')
    ax2.axhline(20, color='#22c55e', linestyle='--', alpha=0.7, label='تشبع بيعي (20)')
    ax2.set_ylabel("Stoch", color='white', fontsize=10)
    leg2 = ax2.legend(loc='upper left', facecolor='#0f172a', edgecolor='none', fontsize=8)
    for text in leg2.get_texts():
        text.set_color('white')

    ax3.plot(df.index, df['MACD'], label='MACD', color='#38bdf8', linewidth=1.2)
    ax3.plot(df.index, df['Signal'], label='خط الإشارة', color='#f43f5e', linewidth=1.2)
    ax3.bar(df.index, df['Hist'], label='Histogram', color='#64748b', alpha=0.6)
    ax3.set_ylabel("MACD", color='white', fontsize=10)
    leg3 = ax3.legend(loc='upper left', facecolor='#0f172a', edgecolor='none', fontsize=8)
    for text in leg3.get_texts():
        text.set_color('white')

    plt.tight_layout()
    chart_path = f"/tmp/{clean_symbol}_{interval}_signal_chart.png"
    plt.savefig(chart_path, dpi=180, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    return chart_path

# ==================== لوحة المفاتيح الرئيسية ====================
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("⚡ رادار تقاطع (5,3,3) + MACD"),
        types.KeyboardButton("🇺🇸 رادار ما قبل الانطلاقة (< $1)"),
        types.KeyboardButton("⚡ دخول المضارب (السوق السعودي)"),
        types.KeyboardButton("📉 رادار التشبع البيعي (استوكاستيك < 20)"),
        types.KeyboardButton("🇸🇦 استوكاستيك السعودي (< 20)"),
        types.KeyboardButton("🚀 رادار الاختراق والسيولة"),
        types.KeyboardButton("📈 السوق السعودي اليومي"),
        types.KeyboardButton("📅 التحليل الأسبوعي"),
        types.KeyboardButton("🔗 رابط دعوتي والترشيح"),
        types.KeyboardButton("⚙️ المساعدة والدليل")
    )
    return markup

def get_inline_keyboard(symbol):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_d = types.InlineKeyboardButton("📊 يومي (Daily)", callback_data=f"tf_1d_{symbol}")
    btn_w = types.InlineKeyboardButton("📆 أسبوعي (Weekly)", callback_data=f"tf_1wk_{symbol}")
    btn_dca = types.InlineKeyboardButton("🧮 حاسبة تعديل التكلفة", callback_data=f"dca_{symbol}")
    markup.add(btn_d, btn_w)
    markup.add(btn_dca)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    save_user(message)
    bot_info = bot.get_me()
    user_id = message.chat.id
    ref_link = f"https://t.me/{bot_info.username}?start=REF_{user_id}"
    
    text = (
        "🏛 **مرحباً بك في المنصة المؤسسية المزودة بإشارات الدخول الآلية**\n\n"
        "• تظهر الآن أسهم الشراء الخضراء (▲) تلقائياً على الشارت عند تحقق تقاطع الاستوكاستك (5,3,3) مع الـ MACD[span_1](start_span)[span_1](end_span).\n"
        "• **رابط دعوتك الخاص:**\n"
        f"`{ref_link}`\n\n"
        "👇 **اختر من الأزرار أدناه أو أرسل رمز/رقم السهم مباشرة:**"
    )
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=get_main_keyboard())

# --- رادار تقاطع الاستوكاستك (5,3,3) مع MACD وإظهار الإشارات ---
@bot.message_handler(func=lambda message: message.text and "رادار تقاطع (5,3,3) + MACD" in message.text)
def stoch_macd_sniper_scan(message):
    save_user(message)
    bot.reply_to(message, "⚡ جاري فحص الأسهم واصطياد فرص التقاطع المزدوج (5,3,3 + MACD)...", reply_markup=get_main_keyboard())
    
    matched = []
    for symbol in TADAWUL_WATCHLIST:
        df = get_stock_data(symbol, interval="1d")
        if df is not None and not df.empty and 'Stoch_K' in df.columns:
            k_curr = float(df['Stoch_K'].iloc[-1])
            d_curr = float(df['Stoch_D'].iloc[-1])
            k_prev = float(df['Stoch_K'].iloc[-2])
            d_prev = float(df['Stoch_D'].iloc[-2])
            
            hist_curr = float(df['Hist'].iloc[-1])
            hist_prev = float(df['Hist'].iloc[-2])
            
            is_stoch_crossover = (k_prev <= d_prev) and (k_curr > d_curr)
            is_macd_improving = (hist_curr > hist_prev) or (hist_curr > 0)
            
            if is_stoch_crossover and is_macd_improving:
                clean_sym = symbol.replace('.SR', '')
                comp_name = get_company_name(symbol)
                last_close = float(df['Close'].iloc[-1])
                matched.append((comp_name, clean_sym, symbol, last_close, k_curr))
                if len(matched) >= 8:
                    break

    if not matched:
        bot.reply_to(message, "❌ لم يتم العثور على أسهم تحققت فيها شروط التقاطع المزدوج حالياً.", reply_markup=get_main_keyboard())
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    for comp_name, clean_sym, full_sym, price, stoch in matched:
        btn_text = f"🎯 {comp_name} ({clean_sym}) [Stoch: {stoch:.1f}]"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"trader_pick_{full_sym}"))

    bot.send_message(message.chat.id, "🟢 **الأسهم المطابقة لإستراتيجية التقاطع (مع ظهور إشارات الدخول ع الشارت):**", reply_markup=markup)

# باقي دوال البوت الأساسية والبحث المباشر...
@bot.message_handler(func=lambda message: True)
def handle_context_aware_message(message):
    save_user(message)
    text = message.text.strip()
    
    numbers_found = re.findall(r'\b\d{3,5}\b', text)
    words = text.split()
    english_tickers = [w.upper() for w in words if w.isalpha() and len(w) <= 5 and all(ord(c) < 128 for c in w)]
    
    target_symbol = None
    if numbers_found:
        target_symbol = numbers_found[0] + ".SR"
    elif english_tickers:
        target_symbol = english_tickers[0].upper()
    elif text.isdigit():
        target_symbol = text + ".SR"

    if target_symbol:
        clean_target = target_symbol.replace('.SR', '')
        comp_name = get_company_name(target_symbol)
        currency = "$" if not target_symbol.endswith(".SR") else "ريال"
        
        bot.reply_to(message, f"⏳ جاري تحليل `{comp_name}` ({clean_target}) ورسم إشارات الدخول...", reply_markup=get_main_keyboard())
        df = get_stock_data(target_symbol, interval="1d")
        
        if df is None or df.empty:
            bot.reply_to(message, f"❌ لم يتم العثور على بيانات للرمز `{clean_target}`.", reply_markup=get_main_keyboard())
            return
            
        last_close = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2])
        change = last_close - prev_close
        change_pct = (change / prev_close) * 100
        last_stoch = float(df['Stoch_K'].iloc[-1]) if 'Stoch_K' in df.columns else 0.0
        
        buy_low = round(last_close * 0.990, 4) if last_close < 1 else round(last_close * 0.985, 2)
        buy_high = round(last_close * 1.002, 4) if last_close < 1 else round(last_close * 1.00, 2)
        t1 = round(last_close * 1.06, 4) if last_close < 1 else round(last_close * 1.05, 2)
        t2 = round(last_close * 1.15, 4) if last_close < 1 else round(last_close * 1.10, 2)
        stop = round(last_close * 0.94, 4) if last_close < 1 else round(last_close * 0.945, 2)
        
        response = (
            f"🏛 **تحليل الشركة: {comp_name} (`{clean_target}`):**\n\n"
            f"• **السعر الحالي:** {last_close:.4f} {currency}\n"
            f"• **التغير:** {'+' if change >= 0 else ''}{change:.4f} ({change_pct:.2f}%)\n\n"
            f"🎯 **مستويات الدعم والهدف:**\n"
            f"• 🟢 **منطقة الشراء (مظللة أخضر):** ({buy_low} - {buy_high}) {currency}\n"
            f"• 🎯 **الهدف الأول:** {t1} {currency} | **الهدف الثاني:** {t2} {currency}\n"
            f"• 🛑 **وقف الخسارة:** {stop} {currency}\n\n"
            f"📉 **مؤشر Stoch (5,3,3):** **{round(last_stoch, 1)}**"
        )
        
        chart_path = generate_professional_chart(df, target_symbol, interval="1d", entry_low=buy_low, entry_high=buy_high)
        with open(chart_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=response, parse_mode="Markdown", reply_markup=get_inline_keyboard(target_symbol))
    else:
        bot.reply_to(message, f"🤖 أهلاً بك! يمكنك النقر على الزر الجديد في القائمة لاختبار الرادار الفني.", reply_markup=get_main_keyboard())

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("Multi-Button Institutional Sniper Bot with Signal Markers is running...")
    bot.infinity_polling()
