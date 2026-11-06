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
    return "Ultra-Clear Sniper Bot is active 24/7!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ==================== إعدادات بوت تيليقرام ====================
TOKEN = "8961540572:AAGLzgU3PwqXopo_BGyai7t4PzJf1cB-eGs"
bot = telebot.TeleBot(TOKEN)

ADMIN_ID = 000000000  # استبدل الأصفار بمعرفك الرقمي إن أردت

# قاموس الأسماء العربية المضمونة لأسهم السوق السعودي لضمان ظهورها فوراً
TADAWUL_NAMES = {
    "1120.SR": "الراجحي",
    "1180.SR": "الإنماء",
    "2222.SR": "أرامكو السعودية",
    "1211.SR": "معادن",
    "2010.SR": "سابك",
    "1301.SR": "التنمية الغذائية",
    "4200.SR": "الدريس",
    "7010.SR": "إس تي سي",
    "1820.SR": "بان القابضة",
    "4300.SR": "دار الأركان",
    "2380.SR": "بوان",
    "4001.SR": "أسواق العثيم",
    "2240.SR": "الزامل للصناعة",
    "4140.SR": "بابه",
    "1010.SR": "الرياض",
    "1020.SR": "الجزيرة",
    "1150.SR": "الأول",
    "2020.SR": "سابك للمغذيات الزراعية",
    "2060.SR": "اتحاد اليمامة",
    "2280.SR": "المراعي",
    "2310.SR": "سبكيم العالمية",
    "3030.SR": "الاسمنت السعودية",
    "3050.SR": "الأسمنت العربية",
    "4030.SR": "الكهرباء السعودية",
    "4050.SR": "الباحة",
    "4190.SR": "جرير",
    "5110.SR": "كهرباء السعودية",
    "6010.SR": "نقي",
    "7020.SR": "اتحاد عذيب",
    "8210.SR": "ولاء للتأمين"
}

TADAWUL_WATCHLIST = list(TADAWUL_NAMES.keys())

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
    # استخدام القاموس المباشر للأسهم السعودية لضمان الاسم العربي الدقيق
    if symbol in TADAWUL_NAMES:
        return TADAWUL_NAMES[symbol]
    try:
        t = yf.Ticker(symbol)
        info = t.info
        name = info.get('longName') or info.get('shortName') or symbol.replace('.SR', '')
        return name
    except:
        return symbol.replace('.SR', '')

def calculate_verified_indicators(df):
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    sma20 = df['Close'].rolling(window=20).mean()
    std20 = df['Close'].rolling(window=20).std()
    df['BB_UP'] = sma20 + (std20 * 2)
    df['BB_DOWN'] = sma20 - (std20 * 2)
    
    low_5 = df['Low'].rolling(window=5).min()
    high_5 = df['High'].rolling(window=5).max()
    k_raw = 100 * ((df['Close'] - low_5) / (high_5 - low_5))
    df['Stoch_K'] = k_raw.rolling(window=3).mean()
    df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()
    
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']
    df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()
    
    df['Verified_Buy'] = False
    for i in range(2, len(df)):
        k_prev = df['Stoch_K'].iloc[i-1]
        k_curr = df['Stoch_K'].iloc[i]
        d_prev = df['Stoch_D'].iloc[i-1]
        d_curr = df['Stoch_D'].iloc[i]
        
        hist_curr = df['Hist'].iloc[i]
        hist_prev = df['Hist'].iloc[i-1]
        
        stoch_crossover = (k_prev <= d_prev) and (k_curr > d_curr) and (k_curr < 65)
        macd_support = (hist_curr > hist_prev) or (hist_curr > 0)
        
        if stoch_crossover and macd_support:
            df.iat[i, df.columns.get_loc('Verified_Buy')] = True

def get_stock_data(symbol, interval="1d"):
    try:
        ticker = yf.Ticker(symbol)
        period = "1y" if interval == "1wk" else "6mo"
        df = ticker.history(period=period, interval=interval)
        if df is None or df.empty or len(df) < 10:
            return None
        df = df.dropna(subset=['Close'])
        calculate_verified_indicators(df)
        return df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

def generate_professional_chart(df, symbol, interval="1d", entry_low=None, entry_high=None):
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 13), sharex=True, gridspec_kw={'height_ratios': [3.2, 1.2, 1.2]})
    tf_name = "الإطار الأسبوعي (Weekly)" if interval == "1wk" else "الإطار اليومي (Daily)"
    clean_symbol = symbol.replace('.SR', '')
    comp_name = get_company_name(symbol)
    
    fig.patch.set_facecolor('#0b0f19')
    for ax in [ax1, ax2, ax3]:
        ax.set_facecolor('#111827')
        ax.tick_params(colors='white', labelsize=11)
        ax.grid(True, linestyle='--', alpha=0.3, color='#374151')
        for spine in ax.spines.values():
            spine.set_color('#4b5563')

    ax1.plot(df.index, df['Close'], label='سعر الإغلاق', color='#38bdf8', linewidth=2.0)
    ax1.plot(df.index, df['EMA50'], label='متوسط 50 (EMA)', color='#fbbf24', linewidth=1.5)
    ax1.plot(df.index, df['BB_UP'], label='بولينجر العلوي', color='#9ca3af', linestyle=':', alpha=0.8)
    ax1.plot(df.index, df['BB_DOWN'], label='بولينجر السفلي', color='#9ca3af', linestyle=':', alpha=0.8)
    
    signals = df[df['Verified_Buy'] == True]
    if not signals.empty:
        ax1.scatter(signals.index, signals['Low'] * 0.985, marker='^', color='#22c55e', s=160, zorder=5, label='إشارة شراء مؤكدة 🎯')

    if entry_low and entry_high:
        ax1.axhspan(entry_low, entry_high, color='#22c55e', alpha=0.3, label='منطقة الدخول الموصى بها')

    ax1.set_title(f"التحليل الفني فائق الوضوح | {comp_name} [{clean_symbol}] - {tf_name}", fontsize=14, fontweight='bold', color='white', pad=12)
    ax1.set_ylabel("السعر", color='white', fontsize=11, fontweight='bold')
    leg1 = ax1.legend(loc='upper left', facecolor='#1f2937', edgecolor='none', fontsize=9)
    for text in leg1.get_texts():
        text.set_color('white')

    ax2.plot(df.index, df['Stoch_K'], label='%K (5,3,3)', color='#f97316', linewidth=1.5)
    ax2.plot(df.index, df['Stoch_D'], label='%D (3)', color='#38bdf8', linewidth=1.5)
    ax2.axhline(80, color='#ef4444', linestyle='--', alpha=0.8, label='تشبع شرائي (80)')
    ax2.axhline(20, color='#22c55e', linestyle='--', alpha=0.8, label='تشبع بيعي (20)')
    ax2.set_ylabel("Stoch", color='white', fontsize=11, fontweight='bold')
    leg2 = ax2.legend(loc='upper left', facecolor='#1f2937', edgecolor='none', fontsize=9)
    for text in leg2.get_texts():
        text.set_color('white')

    ax3.plot(df.index, df['MACD'], label='MACD', color='#38bdf8', linewidth=1.5)
    ax3.plot(df.index, df['Signal'], label='خط الإشارة', color='#f43f5e', linewidth=1.5)
    ax3.bar(df.index, df['Hist'], label='Histogram', color='#9ca3af', alpha=0.7)
    ax3.set_ylabel("MACD", color='white', fontsize=11, fontweight='bold')
    leg3 = ax3.legend(loc='upper left', facecolor='#1f2937', edgecolor='none', fontsize=9)
    for text in leg3.get_texts():
        text.set_color('white')

    plt.tight_layout()
    chart_path = f"/tmp/{clean_symbol}_{interval}_ultraclear_chart.png"
    plt.savefig(chart_path, dpi=220, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    return chart_path

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🎯 رادار الصفقات المؤكدة (السعودي)"),
        types.KeyboardButton("🎯 رادار الصفقات المؤكدة (الأمريكي)"),
        types.KeyboardButton("🇸🇦 استوكاستيك السعودي (< 20)"),
        types.KeyboardButton("🇺🇸 رادار ما قبل الانطلاقة (< $1)"),
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
        "🏛 **منصة القنص المؤسسي - مع الأسماء العربية المباشرة**\n\n"
        "• تظهر الآن أسماء الشركات باللغة العربية بجانب الأكواد بدلاً من تكرار الرقم.\n"
        "• **رابط دعوتك الخاص:**\n"
        f"`{ref_link}`\n\n"
        "👇 **اختر من الأزرار أدناه للبدء:**"
    )
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text and "رادار الصفقات المؤكدة (السعودي)" in message.text)
def verified_tadawul_scan(message):
    save_user(message)
    bot.reply_to(message, "🔍 جاري فحص الأسهم السعودية وإظهار أسمائها العربية المباشرة...", reply_markup=get_main_keyboard())
    
    matched = []
    for symbol in TADAWUL_WATCHLIST:
        df = get_stock_data(symbol, interval="1d")
        if df is not None and not df.empty and 'Verified_Buy' in df.columns:
            recent_signal = df['Verified_Buy'].iloc[-2:].any()
            if recent_signal:
                clean_sym = symbol.replace('.SR', '')
                comp_name = get_company_name(symbol)
                last_close = float(df['Close'].iloc[-1])
                stoch_val = float(df['Stoch_K'].iloc[-1])
                matched.append((comp_name, clean_sym, symbol, last_close, stoch_val))
                if len(matched) >= 8:
                    break

    if not matched:
        bot.reply_to(message, "❌ لا توجد صفقات مطابقة بالمعايير الصارمة حالياً.", reply_markup=get_main_keyboard())
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for comp_name, clean_sym, full_sym, price, stoch in matched:
        btn_text = f"🇸🇦 {comp_name} ({clean_sym}) [Stoch: {stoch:.1f}]"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"trader_pick_{full_sym}"))

    bot.send_message(message.chat.id, "🟢 **الفرص المؤكدة في السوق السعودي (الاسم العربي + الرمز):**", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text and "رادار الصفقات المؤكدة (الأمريكي)" in message.text)
def verified_us_scan(message):
    save_user(message)
    bot.reply_to(message, "🇺🇸 جاري فحص الأسهم الأمريكية وإظهار نتائجها...", reply_markup=get_main_keyboard())
    
    matched = []
    for symbol in US_CHEAP_WATCHLIST:
        df = get_stock_data(symbol, interval="1d")
        if df is not None and not df.empty and 'Verified_Buy' in df.columns:
            recent_signal = df['Verified_Buy'].iloc[-2:].any()
            if recent_signal:
                comp_name = get_company_name(symbol)
                last_close = float(df['Close'].iloc[-1])
                stoch_val = float(df['Stoch_K'].iloc[-1])
                matched.append((comp_name, symbol, symbol, last_close, stoch_val))
                if len(matched) >= 8:
                    break

    if not matched:
        bot.reply_to(message, "❌ لا توجد صفقات أمريكية مطابقة حالياً.", reply_markup=get_main_keyboard())
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for comp_name, clean_sym, full_sym, price, stoch in matched:
        btn_text = f"🇺🇸 {comp_name} ({clean_sym}) [Stoch: {stoch:.1f}]"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"trader_pick_{full_sym}"))

    bot.send_message(message.chat.id, "🇺🇸 **الفرص المؤكدة في السوق الأمريكي:**", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text and "استوكاستيك السعودي" in message.text)
def tadawul_stochastic_scan(message):
    save_user(message)
    bot.reply_to(message, "🇸🇦 جاري مسح الأسهم في قاع التشبع البيعي مع أسمائها العربية...", reply_markup=get_main_keyboard())
    matched = []
    for symbol in TADAWUL_WATCHLIST:
        df = get_stock_data(symbol, interval="1d")
        if df is not None and not df.empty and 'Stoch_K' in df.columns:
            stoch_val = float(df['Stoch_K'].iloc[-1])
            if stoch_val < 20:
                clean_sym = symbol.replace('.SR', '')
                comp_name = get_company_name(symbol)
                matched.append((comp_name, clean_sym, symbol, stoch_val))
                if len(matched) >= 8: break
    if not matched:
        bot.reply_to(message, "❌ لا توجد أسهم حالياً تحت 20.", reply_markup=get_main_keyboard())
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for comp_name, clean_sym, full_sym, stoch in matched:
        markup.add(types.InlineKeyboardButton(f"🇸🇦 {comp_name} ({clean_sym}) [Stoch: {stoch:.1f}]", callback_data=f"trader_pick_{full_sym}"))
    bot.send_message(message.chat.id, "📉 **أسهم التشبع البيعي (الاسم العربي الصريح):**", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text and ("السوق السعودي اليومي" in message.text or "التحليل الأسبوعي" in message.text))
def quick_menus(message):
    save_user(message)
    interval = "1wk" if "الأسبوعي" in message.text else "1d"
    symbol = "1120.SR"
    tf_name = "الإطار الأسبوعي" if interval == "1wk" else "الإطار اليومي"
    df = get_stock_data(symbol, interval=interval)
    last_close = float(df['Close'].iloc[-1])
    comp_name = get_company_name(symbol)
    response = f"📊 **المؤشر القياسي ({comp_name} - {tf_name}):**\n• السعر: {round(last_close, 2)} ريال"
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
    
    bot.answer_callback_query(call.id, text=f"جاري جلب التحليل لـ {comp_name}...")
    df = get_stock_data(symbol, interval="1d")
    if df is None or df.empty:
        bot.send_message(call.message.chat.id, f"❌ تعذر جلب بيانات السهم.")
        return
        
    last_close = float(df['Close'].iloc[-1])
    prev_close = float(df['Close'].iloc[-2])
    change = last_close - prev_close
    change_pct = (change / prev_close) * 100
    last_stoch = float(df['Stoch_K'].iloc[-1]) if 'Stoch_K' in df.columns else 0.0
    
    entry_low = round(last_close * 0.990, 4) if last_close < 1 else round(last_close * 0.985, 2)
    entry_high = round(last_close * 1.002, 4) if last_close < 1 else round(last_close * 1.00, 2)
    target_1 = round(last_close * 1.06, 4) if last_close < 1 else round(last_close * 1.05, 2)
    target_2 = round(last_close * 1.15, 4) if last_close < 1 else round(last_close * 1.10, 2)
    stop_loss = round(last_close * 0.94, 4) if last_close < 1 else round(last_close * 0.945, 2)
    
    report = (
        f"🎯 **تقرير الصفقات المؤكدة (الاسم العربي الصريح):**\n\n"
        f"📊 **الشركة:** `{comp_name}` (`{clean_sym}`)\n\n"
        f"• **السعر الحالي:** {last_close:.4f} {currency}\n"
        f"• **التغير:** {'+' if change >= 0 else ''}{change:.4f} ({change_pct:.2f}%)\n\n"
        f"🎯 **مستويات الإدارة الفنية:**\n"
        f"• 🟢 **منطقة الشراء (مظللة أخضر ع الشارت):** ({entry_low} - {entry_high}) {currency}\n"
        f"• 🎯 **الهدف الأول:** {target_1} {currency}\n"
        f"• 🎯 **الهدف الثاني:** {target_2} {currency}\n"
        f"• 🛑 **وقف الخسارة:** {stop_loss} {currency}\n\n"
        f"📉 **مؤشر Stoch (5,3,3):** **{round(last_stoch, 1)}**"
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
        bot.answer_callback_query(call.id, text="تم تحديث الإطار الزمني بدقة...")
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
        
        bot.reply_to(message, f"⏳ جاري فحص ورسم الشارت فائق الوضوح لـ `{comp_name}`...", reply_markup=get_main_keyboard())
        df = get_stock_data(target_symbol, interval="1d")
        
        if df is None or df.empty:
            bot.reply_to(message, f"❌ لم يتم العثور على بيانات كافية للرمز `{clean_target}`.", reply_markup=get_main_keyboard())
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
            f"🏛 **التحليل الفني للشركة: {comp_name} (`{clean_target}`):**\n\n"
            f"• **السعر الحالي:** {last_close:.4f} {currency}\n"
            f"• **التغير:** {'+' if change >= 0 else ''}{change:.4f} ({change_pct:.2f}%)\n\n"
            f"🎯 **مستويات الدعم والهدف:**\n"
            f"• 🟢 **منطقة الشراء (مظللة أخضر ع الشارت):** ({buy_low} - {buy_high}) {currency}\n"
            f"• 🎯 **الهدف الأول:** t1 {currency} | **الهدف الثاني:** t2 {currency}\n"
            f"• 🛑 **وقف الخسارة:** {stop} {currency}\n\n"
            f"📉 **مؤشر Stoch (5,3,3):** **{round(last_stoch, 1)}**"
        )
        
        chart_path = generate_professional_chart(df, target_symbol, interval="1d", entry_low=buy_low, entry_high=buy_high)
        with open(chart_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=response, parse_mode="Markdown", reply_markup=get_inline_keyboard(target_symbol))
    else:
        bot.reply_to(message, f"🤖 أهلاً بك! استخدم الأزرار للاطلاع على أسماء الشركات وفرص الشراء الواضحة.", reply_markup=get_main_keyboard())

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("Ultra-Clear Sniper Bot with Arabic Names is running successfully...")
    bot.infinity_polling()