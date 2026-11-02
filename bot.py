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
    
    low_14 = df['Low'].rolling(window=14).min()
    high_14 = df['High'].rolling(window=14).max()
    df['Stoch_K'] = 100 * ((df['Close'] - low_14) / (high_14 - low_14))
    
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']
    df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()
    df['High_52w'] = df['High'].rolling(window=252, min_periods=20).max()

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
    ax1.plot(df.index, df['EMA50'], label='متوسط 50 يوم (EMA)', color='#fbbf24', linewidth=1.2)
    ax1.plot(df.index, df['BB_UP'], label='بولينجر العرضي', color='#94a3b8', linestyle=':', alpha=0.7)
    ax1.plot(df.index, df['BB_DOWN'], color='#94a3b8', linestyle=':', alpha=0.7)
    
    # تظليل منطقة الدخول باللون الأخضر إذا توفرت الحدود
    if entry_low and entry_high:
        ax1.axhspan(entry_low, entry_high, color='#22c55e', alpha=0.25, label='منطقة الدخول الموصى بها')

    ax1.set_title(f"التحليل الفني المؤسسي | {comp_name} [{clean_symbol}] - {tf_name}", fontsize=12, fontweight='bold', color='white', pad=10)
    ax1.set_ylabel("السعر", color='white', fontsize=10)
    leg1 = ax1.legend(loc='upper left', facecolor='#0f172a', edgecolor='none', fontsize=8)
    for text in leg1.get_texts():
        text.set_color('white')

    ax2.plot(df.index, df['RSI'], label='مؤشر القوة النسبية RSI (14)', color='#c084fc', linewidth=1.2)
    ax2.axhline(70, color='#ef4444', linestyle='--', alpha=0.7, label='تشبع شرائي (70)')
    ax2.axhline(30, color='#22c55e', linestyle='--', alpha=0.7, label='تشبع بيعي (30)')
    ax2.set_ylabel("RSI", color='white', fontsize=10)
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
    chart_path = f"/tmp/{clean_symbol}_{interval}_global_chart.png"
    plt.savefig(chart_path, dpi=180, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    return chart_path

# ==================== لوحة المفاتيح الرئيسية ====================
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
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
        "🏛 **مرحباً بك في المنصة المؤسسية العالمية المتقدمة**\n\n"
        "• إظهار اسم الشركة بجانب الرقم تلقائياً مع تظليل مناطق الدخول باللون الأخضر على الشارت.\n"
        "• **رابط دعوتك الخاص:**\n"
        f"`{ref_link}`\n\n"
        "👇 **اختر من الأزرار أدناه أو أرسل رمز/رقم السهم مباشرة:**"
    )
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(commands=['stats', 'users'])
def show_user_stats(message):
    save_user(message)
    users_data = load_users()
    total_users = len(users_data)
    details = f"📊 **إحصائيات المستخدمين:**\n\n• إجمالي المستخدمين: **{total_users}** مستخدم"
    bot.reply_to(message, details, parse_mode="Markdown")

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if ADMIN_ID and message.chat.id != ADMIN_ID:
        return
    text_parts = message.text.split(maxsplit=1)
    if len(text_parts) < 2:
        bot.reply_to(message, "❌ الاستخدام الصحيح:\n`/broadcast رسالتك هنا`", parse_mode="Markdown")
        return
    msg_to_send = text_parts[1]
    users_data = load_users()
    success = 0
    for uid in users_data.keys():
        try:
            bot.send_message(int(uid), f"📢 **إعلان إداري:**\n\n{msg_to_send}", parse_mode="Markdown")
            success += 1
        except:
            pass
    bot.reply_to(message, f"✅ تم إرسال البث إلى `{success}` مستخدم.", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text and "رابط دعوتي" in message.text)
def my_referral_link(message):
    save_user(message)
    bot_info = bot.get_me()
    user_id = message.chat.id
    users_data = load_users()
    ref_count = users_data.get(str(user_id), {}).get("referrals_count", 0)
    ref_link = f"https://t.me/{bot_info.username}?start=REF_{user_id}"
    resp = f"🔗 **برنامج الدعوة:**\n\nرابطك:\n`{ref_link}`\n\n👥 عدد المدعوين: **{ref_count}** شخص."
    bot.reply_to(message, resp, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text and "المساعدة" in message.text)
def send_help(message):
    save_user(message)
    text = (
        "⚙️ **دليل الأزرار والوظائف:**\n"
        "1️⃣ **رادار ما قبل الانطلاقة:** يفحص الأسهم الأمريكية تحت 1$ في مناطق التجميع.\n"
        "2️⃣ **دخول المضارب (السوق السعودي):** يفحص أسهم تداول للحركة اللحظية.\n"
        "3️⃣ **رادار التشبع البيعي:** يفحص جميع الأسهم (سعودي وأمريكي) الاستوكاستيك فيها تحت 20.\n"
        "4️⃣ **استوكاستيك السعودي (< 20):** مخصص لأسهم السوق السعودي مع اسم الشركة ومناطق الدخول الخضراء.\n"
        "5️⃣ **البحث المباشر:** أرسل رمز السهم أو رقمه في أي وقت."
    )
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=get_main_keyboard())

# --- 1. زر رادار ما قبل الانطلاقة ---
@bot.message_handler(func=lambda message: message.text and "رادار ما قبل الانطلاقة" in message.text)
def trader_pre_breakout_scan(message):
    save_user(message)
    bot.reply_to(message, "🔍 جاري فحص الأسهم الأمريكية تحت 1 دولار للبحث عن فرص التجميع...", reply_markup=get_main_keyboard())
    
    matched = []
    for symbol in US_CHEAP_WATCHLIST:
        df = get_stock_data(symbol, interval="1d")
        if df is not None and not df.empty:
            last_close = float(df['Close'].iloc[-1])
            prev_close = float(df['Close'].iloc[-2])
            change_pct = ((last_close - prev_close) / prev_close) * 100
            last_rsi = float(df['RSI'].iloc[-1])
            
            if last_close < 1.00 and -4.0 <= change_pct <= 4.0 and (35 <= last_rsi <= 55):
                comp_name = get_company_name(symbol)
                matched.append((symbol, comp_name, last_close, change_pct))
                if len(matched) >= 8:
                    break

    if not matched:
        bot.reply_to(message, "❌ لم يتم العثور على أسهم مطابقة حالياً.", reply_markup=get_main_keyboard())
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    for symbol, comp_name, price, chg in matched:
        btn_text = f"🎯 {comp_name} ({symbol}) [${price:.4f}]"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"trader_pick_{symbol}"))

    bot.send_message(message.chat.id, "🟢 **فرص ما قبل الانطلاقة (تحت $1):**\nاختر السهم لعرض الشارت:", reply_markup=markup)

# --- 2. زر دخول المضارب (السوق السعودي) ---
@bot.message_handler(func=lambda message: message.text and "دخول المضارب (السوق السعودي)" in message.text)
def trader_tadawul_scan(message):
    save_user(message)
    bot.reply_to(message, "⚡ جاري مسح السوق السعودي واصطياد فرص المضاربة اللحظية...", reply_markup=get_main_keyboard())
    matched = []
    for symbol in TADAWUL_WATCHLIST:
        df = get_stock_data(symbol, interval="1d")
        if df is not None and not df.empty:
            last_close = float(df['Close'].iloc[-1])
            last_vol = float(df['Volume'].iloc[-1])
            vol_sma = float(df['Vol_SMA20'].iloc[-1]) if not pd.isna(df['Vol_SMA20'].iloc[-1]) else last_vol
            last_rsi = float(df['RSI'].iloc[-1])
            if last_vol > (vol_sma * 1.2) or (40 <= last_rsi <= 65):
                clean_sym = symbol.replace('.SR', '')
                comp_name = get_company_name(symbol)
                matched.append((comp_name, clean_sym, symbol, last_close))
                if len(matched) >= 6: break
    if not matched:
        bot.reply_to(message, "❌ لم يتم العثور على فرص مطابقة في السوق السعودي حالياً.", reply_markup=get_main_keyboard())
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    for comp_name, clean_sym, full_sym, price in matched:
        markup.add(types.InlineKeyboardButton(f"🇸🇦 {comp_name} ({clean_sym}) [{price} ر.س]", callback_data=f"trader_pick_{full_sym}"))
    bot.send_message(message.chat.id, "⚡ **فرص المضاربة اللحظية (السوق السعودي):**\nاختر السهم لعرض الشارت:", reply_markup=markup)

# --- 3. زر رادار التشبع البيعي الشامل ---
@bot.message_handler(func=lambda message: message.text and "رادار التشبع البيعي" in message.text)
def stochastic_oversold_scan(message):
    save_user(message)
    bot.reply_to(message, "📉 جاري فحص الأسهم التي تعاني من ضغط بيعي (استوكاستيك < 20)...", reply_markup=get_main_keyboard())
    
    all_watchlist = TADAWUL_WATCHLIST + US_CHEAP_WATCHLIST
    matched = []
    
    for symbol in all_watchlist:
        df = get_stock_data(symbol, interval="1d")
        if df is not None and not df.empty and 'Stoch_K' in df.columns:
            last_close = float(df['Close'].iloc[-1])
            stoch_val = float(df['Stoch_K'].iloc[-1])
            
            if not pd.isna(stoch_val) and stoch_val < 20:
                clean_sym = symbol.replace('.SR', '')
                comp_name = get_company_name(symbol)
                matched.append((comp_name, clean_sym, symbol, last_close, stoch_val))
                if len(matched) >= 8:
                    break

    if not matched:
        bot.reply_to(message, "❌ لم يتم العثور على أسهم تتداول تحت 20 في الاستوكاستيك حالياً.", reply_markup=get_main_keyboard())
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    for comp_name, clean_sym, full_sym, price, stoch in matched:
        btn_text = f"🎯 {comp_name} ({clean_sym}) [Stoch: {stoch:.1f}]"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"trader_pick_{full_sym}"))

    bot.send_message(message.chat.id, "📉 **أسهم مناطق التشبع البيعي الشامل (Stochastic < 20):**", reply_markup=markup)

# --- 4. زر استوكاستيك السعودي حصرياً ---
@bot.message_handler(func=lambda message: message.text and "استوكاستيك السعودي" in message.text)
def tadawul_stochastic_scan(message):
    save_user(message)
    bot.reply_to(message, "🇸🇦 جاري مسح السوق السعودي لاكتشاف الأصول القابعة تحت 20 في مؤشر الاستوكاستيك...", reply_markup=get_main_keyboard())
    
    matched = []
    for symbol in TADAWUL_WATCHLIST:
        df = get_stock_data(symbol, interval="1d")
        if df is not None and not df.empty and 'Stoch_K' in df.columns:
            last_close = float(df['Close'].iloc[-1])
            stoch_val = float(df['Stoch_K'].iloc[-1])
            
            if not pd.isna(stoch_val) and stoch_val < 20:
                clean_sym = symbol.replace('.SR', '')
                comp_name = get_company_name(symbol)
                matched.append((comp_name, clean_sym, symbol, last_close, stoch_val))
                if len(matched) >= 8:
                    break

    if not matched:
        bot.reply_to(message, "❌ لا توجد أسهم سعودية تتداول تحت 20 في الاستوكاستيك ضمن القائمة حالياً.", reply_markup=get_main_keyboard())
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    for comp_name, clean_sym, full_sym, price, stoch in matched:
        btn_text = f"🇸🇦 {comp_name} ({clean_sym}) [Stoch: {stoch:.1f}]"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"trader_pick_{full_sym}"))

    bot.send_message(message.chat.id, "🇸🇦 **الأسهم السعودية في مناطق التشبع البيعي (Stochastic < 20):**", reply_markup=markup)

# --- 5. رادار الاختراق والسيولة ---
@bot.message_handler(func=lambda message: message.text and "رادار الاختراق والسيولة" in message.text)
def breakout_sniper_scan(message):
    save_user(message)
    bot.reply_to(message, "🚀 جاري تشغيل رادار اختراق القمم والسيولة...", reply_markup=get_main_keyboard())
    combined_list = TADAWUL_WATCHLIST[:3] + US_CHEAP_WATCHLIST[:3]
    found = False
    for symbol in combined_list:
        df = get_stock_data(symbol, interval="1d")
        if df is not None and not df.empty:
            last_close = float(df['Close'].iloc[-1])
            high_52 = float(df['High_52w'].iloc[-1]) if not pd.isna(df['High_52w'].iloc[-1]) else last_close
            last_vol = float(df['Volume'].iloc[-1])
            vol_sma = float(df['Vol_SMA20'].iloc[-1]) if not pd.isna(df['Vol_SMA20'].iloc[-1]) else last_vol
            
            if last_close >= (high_52 * 0.98) or last_vol > (vol_sma * 1.5):
                found = True
                clean_sym = symbol.replace('.SR', '')
                comp_name = get_company_name(symbol)
                currency = "$" if not symbol.endswith(".SR") else "ريال"
                prev_close = float(df['Close'].iloc[-2])
                change_pct = ((last_close - prev_close) / prev_close) * 100
                
                entry_low = round(last_close * 0.990, 4) if last_close < 1 else round(last_close * 0.985, 2)
                entry_high = round(last_close * 1.002, 4) if last_close < 1 else round(last_close * 1.00, 2)

                alert_text = (
                    f"🚀 **رادار اختراق المقاومات والسيولة:**\n\n"
                    f"📊 **الشركة:** `{comp_name}` (`{clean_sym}`)\n"
                    f"• **السعر الحالي:** {last_close:.4f} {currency}\n"
                    f"• **التغير اليومي:** {change_pct:.2f}%\n"
                    f"• **قمة 52 أسبوع:** {high_52:.4f} {currency}"
                )
                chart_path = generate_professional_chart(df, symbol, interval="1d", entry_low=entry_low, entry_high=entry_high)
                with open(chart_path, 'rb') as photo:
                    bot.send_photo(message.chat.id, photo, caption=alert_text, parse_mode="Markdown", reply_markup=get_inline_keyboard(symbol))
                break
    if not found:
        bot.reply_to(message, "لم يتم رصد اختراقات قوية حالياً.", reply_markup=get_main_keyboard())

# --- السوق السعودي اليومي والتحليل الأسبوعي ---
@bot.message_handler(func=lambda message: message.text and ("السوق السعودي اليومي" in message.text or "التحليل الأسبوعي" in message.text))
def quick_menus(message):
    save_user(message)
    interval = "1wk" if "الأسبوعي" in message.text else "1d"
    symbol = "1120.SR"
    tf_name = "الإطار الأسبوعي" if interval == "1wk" else "الإطار اليومي"
    
    df = get_stock_data(symbol, interval=interval)
    if df is None:
        bot.reply_to(message, "❌ تعذر جلب البيانات.", reply_markup=get_main_keyboard())
        return
    last_close = float(df['Close'].iloc[-1])
    comp_name = get_company_name(symbol)
    response = f"📊 **مؤشر السوق القياسي ({comp_name} - {tf_name}):**\n• السعر: {round(last_close, 2)} ريال"
    chart_path = generate_professional_chart(df, symbol, interval=interval)
    with open(chart_path, 'rb') as photo:
        bot.send_photo(message.chat.id, photo, caption=response, parse_mode="Markdown", reply_markup=get_inline_keyboard(symbol))

@bot.callback_query_handler(func=lambda call: call.data.startswith("trader_pick_"))
def handle_trader_pick(call):
    save_user(call.message)
    symbol = call.data.replace("trader_pick_", "")
    clean_sym = symbol.replace('.SR', '')
    comp_name = get_company_name(symbol)
    currency = "$" if not symbol.endswith(".SR") else "ريال"
    
    bot.answer_callback_query(call.id, text=f"جاري تحضير التحليل لـ {comp_name}...")
    df = get_stock_data(symbol, interval="1d")
    if df is None or df.empty:
        bot.send_message(call.message.chat.id, f"❌ تعذر جلب بيانات السهم {clean_sym}.")
        return
        
    last_close = float(df['Close'].iloc[-1])
    prev_close = float(df['Close'].iloc[-2])
    change = last_close - prev_close
    change_pct = (change / prev_close) * 100
    last_rsi = float(df['RSI'].iloc[-1])
    last_stoch = float(df['Stoch_K'].iloc[-1]) if 'Stoch_K' in df.columns else 0.0
    
    entry_low = round(last_close * 0.990, 4) if last_close < 1 else round(last_close * 0.985, 2)
    entry_high = round(last_close * 1.002, 4) if last_close < 1 else round(last_close * 1.00, 2)
    target_1 = round(last_close * 1.06, 4) if last_close < 1 else round(last_close * 1.05, 2)
    target_2 = round(last_close * 1.15, 4) if last_close < 1 else round(last_close * 1.10, 2)
    stop_loss = round(last_close * 0.94, 4) if last_close < 1 else round(last_close * 0.945, 2)
    
    report = (
        f"🟢 **تقرير التحليل الفني ومناطق الدخول:**\n\n"
        f"📊 **الشركة:** `{comp_name}` (`{clean_sym}`)\n\n"
        f"• **السعر الحالي:** {last_close:.4f} {currency}\n"
        f"• **التغير اليومي:** {'+' if change >= 0 else ''}{change:.4f} ({change_pct:.2f}%)\n\n"
        f"🎯 **مستويات الدعم والأهداف:**\n"
        f"• 🟢 **منطقة الشراء (مظللة أخضر ع الشارت):** ({entry_low} - {entry_high}) {currency}\n"
        f"• 🎯 **الهدف الأول:** {target_1} {currency}\n"
        f"• 🎯 **الهدف الثاني:** {target_2} {currency}\n"
        f"• 🛑 **وقف الخسارة:** {stop_loss} {currency}\n\n"
        f"📈 **المؤشرات:**\n"
        f"• RSI: **{round(last_rsi, 1)}** | Stoch: **{round(last_stoch, 1)}**"
    )
    
    chart_path = generate_professional_chart(df, symbol, interval="1d", entry_low=entry_low, entry_high=entry_high)
    with open(chart_path, 'rb') as photo:
        bot.send_photo(call.message.chat.id, photo, caption=report, parse_mode="Markdown", reply_markup=get_inline_keyboard(symbol))

@bot.callback_query_handler(func=lambda call: call.data.startswith("tf_") or call.data.startswith("dca_"))
def handle_inline_callbacks(call):
    save_user(call.message)
    if call.data.startswith("tf_"):
        parts = call.data.split("_")
        interval, symbol = parts[1], parts[2]
        bot.answer_callback_query(call.id, text="تم تحديث الإطار الزمني...")
        df = get_stock_data(symbol, interval=interval)
        last_close = float(df['Close'].iloc[-1])
        comp_name = get_company_name(symbol)
        response = f"📊 **تحديث الشارت ({comp_name}):**\n• السعر: {last_close:.4f}"
        chart_path = generate_professional_chart(df, symbol, interval=interval)
        with open(chart_path, 'rb') as photo:
            bot.send_photo(call.message.chat.id, photo, caption=response, parse_mode="Markdown", reply_markup=get_inline_keyboard(symbol))
    elif call.data.startswith("dca_"):
        symbol = call.data.split("_")[1]
        clean_sym = symbol.replace('.SR', '')
        comp_name = get_company_name(symbol)
        bot.answer_callback_query(call.id, text="🧮 حاسبة تعديل التكلفة")
        guide_text = f"🧮 **حاسبة التعديل للشركة ({comp_name} - `{clean_sym}`):**\nأرسل هكذا:\n`تعديل {clean_sym} [الكمية الحالية] [متوسطك] [الكمية الجديدة]`"
        bot.send_message(call.message.chat.id, guide_text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text and message.text.strip().startswith("تعديل"))
def calculate_dca_result(message):
    save_user(message)
    try:
        parts = message.text.strip().split()
        sym = parts[1].upper()
        symbol = sym if "." in sym or not sym.isdigit() else sym + ".SR"
        curr_shares, curr_avg, new_shares = float(parts[2]), float(parts[3]), float(parts[4])
        df = yf.Ticker(symbol).history(period="1d")
        market_price = float(df['Close'].iloc[-1])
        new_avg = ((curr_shares * curr_avg) + (new_shares * market_price)) / (curr_shares + new_shares)
        comp_name = get_company_name(symbol)
        bot.reply_to(message, f"🧮 متوسطك الجديد للشركة ({comp_name} - `{sym}`): **{new_avg:.4f}**", parse_mode="Markdown", reply_markup=get_main_keyboard())
    except:
        bot.reply_to(message, "❌ خطأ في الصيغة. استخدم: `تعديل [الرمز] [الكمية] [المتوسط] [الكمية الجديدة]`", parse_mode="Markdown")

# --- السياق الذكي للبحث المباشر ---
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
        
        bot.reply_to(message, f"⏳ جاري تحليل `{comp_name}` ({clean_target}) وجلب الشارت...", reply_markup=get_main_keyboard())
        df = get_stock_data(target_symbol, interval="1d")
        
        if df is None or df.empty:
            bot.reply_to(message, f"❌ لم يتم العثور على بيانات للرمز `{clean_target}`.", reply_markup=get_main_keyboard())
            return
            
        last_close = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2])
        change = last_close - prev_close
        change_pct = (change / prev_close) * 100
        last_rsi = float(df['RSI'].iloc[-1])
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
            f"• 🟢 **منطقة الشراء (مظللة أخضر ع الشارت):** ({buy_low} - {buy_high}) {currency}\n"
            f"• 🎯 **الهدف الأول:** {t1} {currency} | **الهدف الثاني:** {t2} {currency}\n"
            f"• 🛑 **وقف الخسارة:** {stop} {currency}\n\n"
            f"📉 **المؤشرات:**\n"
            f"• RSI: **{round(last_rsi, 1)}** | Stoch: **{round(last_stoch, 1)}**"
        )
        
        chart_path = generate_professional_chart(df, target_symbol, interval="1d", entry_low=buy_low, entry_high=buy_high)
        with open(chart_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=response, parse_mode="Markdown", reply_markup=get_inline_keyboard(target_symbol))
    else:
        bot.reply_to(message, f"🤖 أهلاً بك! يمكنك استخدام الأزرار في الأسفل أو إرسال رمز/رقم السهم مباشرة.", reply_markup=get_main_keyboard())

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("Multi-Button Institutional Sniper Bot is running...")
    bot.infinity_polling()