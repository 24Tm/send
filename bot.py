import os
import time
import threading
import schedule
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
    return "Wide-Scan Elite Sniper Bot is active 24/7!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ==================== إعدادات بوت تيليقرام ====================
TOKEN = "8961540572:AAGLzgU3PwqXopo_BGyai7t4PzJf1cB-eGs"
bot = telebot.TeleBot(TOKEN)

# قائمة واسعة وموسعة لأسهم السوق السعودي (تداول) بمختلف القطاعات
TADAWUL_NAMES = {
    "1120.SR": "الراجحي",
    "1180.SR": "الإنماء",
    "2222.SR": "أرامكو السعودية",
    "1211.SR": "معادن",
    "2010.SR": "سابك",
    "1301.SR": "التنمية الغذائية",
    "4200.SR": "الدريس",
    "7010.SR": "إس تي سي",
    "4300.SR": "دار الأركان",
    "2380.SR": "بوان",
    "4001.SR": "أسواق العثيم",
    "2240.SR": "الزامل للصناعة",
    "1010.SR": "الرياض",
    "1020.SR": "الجزيرة",
    "1150.SR": "الأول",
    "2020.SR": "سابك للمغذيات",
    "2280.SR": "المراعي",
    "2310.SR": "سبكيم العالمية",
    "3030.SR": "الاسمنت السعودية",
    "5110.SR": "الكهرباء السعودية",
    "4190.SR": "جرير",
    "7020.SR": "اتحاد عذيب",
    "1080.SR": "البلد",
    "1110.SR": "الاستثمار",
    "1212.SR": "البحر الأحمر",
    "1830.SR": "سينومي ريتيل",
    "2080.SR": "بيشة",
    "2150.SR": "الأسماك",
    "2160.SR": "مفكو",
    "2170.SR": "الوطنية للتعليم",
    "2220.SR": "الماجدية",
    "2230.SR": "قزاز",
    "3001.SR": "أسمنت العربية",
    "3002.SR": "أسمنت اليمامة",
    "3003.SR": "أسمنت السعودية",
    "3004.SR": "أسمنت القصيم",
    "3005.SR": "أسمنت الجنوب",
    "4002.SR": "المواساة",
    "4003.SR": "الشرقية للتنمية",
    "4004.SR": "دله الصحية",
    "4005.SR": "سليمان الحبيب"
}

TADAWUL_WATCHLIST = list(TADAWUL_NAMES.keys())

US_EXPANDED_WATCHLIST = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", 
    "AMD", "INTC", "PLTR", "F", "BAC", "PFE", "UBER", "NFLX", "DIS"
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
    if symbol in TADAWUL_NAMES:
        return TADAWUL_NAMES[symbol]
    try:
        t = yf.Ticker(symbol)
        info = t.info
        name = info.get('longName') or info.get('shortName') or symbol
        return name
    except:
        return symbol

def calculate_indicators(df):
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
    
    df['Bottom_Sniper'] = False
    df['Weekly_Oversold'] = False
    
    for i in range(2, len(df)):
        k_prev = df['Stoch_K'].iloc[i-1]
        k_curr = df['Stoch_K'].iloc[i]
        d_prev = df['Stoch_D'].iloc[i-1]
        d_curr = df['Stoch_D'].iloc[i]
        
        macd_prev = df['MACD'].iloc[i-1]
        macd_curr = df['MACD'].iloc[i]
        sig_prev = df['Signal'].iloc[i-1]
        sig_curr = df['Signal'].iloc[i]
        
        stoch_from_oversold = (k_prev <= 25) or (d_prev <= 25)
        stoch_crossover = (k_prev <= d_prev) and (k_curr > d_curr) and stoch_from_oversold
        macd_crossover = (macd_prev <= sig_prev) and (macd_curr > sig_curr)
        
        if stoch_crossover and macd_crossover:
            df.iat[i, df.columns.get_loc('Bottom_Sniper')] = True
            
        if k_curr <= 25 and k_curr > k_prev:
            df.iat[i, df.columns.get_loc('Weekly_Oversold')] = True

def get_stock_data(symbol, interval="1d"):
    try:
        ticker = yf.Ticker(symbol)
        period = "1y" if interval == "1wk" else "75d"
        df = ticker.history(period=period, interval=interval)
        if df is None or df.empty or len(df) < 10:
            return None
        df = df.dropna(subset=['Close'])
        calculate_indicators(df)
        return df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

def generate_professional_chart(df, symbol, interval="1d", entry_low=None, entry_high=None):
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 11), sharex=True, gridspec_kw={'height_ratios': [3.2, 1.2, 1.2]})
    tf_name = "الإطار الأسبوعي الاستثماري" if interval == "1wk" else "الإطار اليومي (أحدث الحركة السعرية)"
    clean_symbol = symbol.replace('.SR', '')
    comp_name = get_company_name(symbol)
    
    fig.patch.set_facecolor('#0b0f19')
    for ax in [ax1, ax2, ax3]:
        ax.set_facecolor('#111827')
        ax.tick_params(colors='white', labelsize=10)
        ax.grid(True, linestyle='--', alpha=0.3, color='#374151')
        for spine in ax.spines.values():
            spine.set_color('#4b5563')

    ax1.plot(df.index, df['Close'], label='سعر الإغلاق', color='#38bdf8', linewidth=2.0)
    ax1.plot(df.index, df['EMA50'], label='متوسط 50', color='#fbbf24', linewidth=1.3)
    ax1.plot(df.index, df['BB_UP'], label='بولينجر العلوي', color='#9ca3af', linestyle=':', alpha=0.7)
    ax1.plot(df.index, df['BB_DOWN'], label='بولينجر السفلي', color='#9ca3af', linestyle=':', alpha=0.7)
    
    recent_signals = df[df['Bottom_Sniper'] == True]
    if not recent_signals.empty:
        ax1.scatter(recent_signals.index, recent_signals['Low'] * 0.99, marker='^', color='#22c55e', s=180, zorder=5, label='فرصة دخول مؤكدة 🎯')

    if entry_low and entry_high:
        ax1.axhspan(entry_low, entry_high, color='#22c55e', alpha=0.25, label='منطقة الدخول الموصى بها')

    ax1.set_title(f"تحليل القاع النظيف | {comp_name} [{clean_symbol}] - {tf_name}", fontsize=13, fontweight='bold', color='white', pad=10)
    ax1.set_ylabel("السعر", color='white', fontsize=10, fontweight='bold')
    leg1 = ax1.legend(loc='upper left', facecolor='#1f2937', edgecolor='none', fontsize=8)
    for text in leg1.get_texts():
        text.set_color('white')

    ax2.plot(df.index, df['Stoch_K'], label='%K (5,3,3)', color='#f97316', linewidth=1.4)
    ax2.plot(df.index, df['Stoch_D'], label='%D (3)', color='#38bdf8', linewidth=1.4)
    ax2.axhline(80, color='#ef4444', linestyle='--', alpha=0.7, label='تشبع شرائي (80)')
    ax2.axhline(20, color='#22c55e', linestyle='--', alpha=0.7, label='تشبع بيعي (20)')
    ax2.set_ylabel("Stoch", color='white', fontsize=10, fontweight='bold')
    leg2 = ax2.legend(loc='upper left', facecolor='#1f2937', edgecolor='none', fontsize=8)
    for text in leg2.get_texts():
        text.set_color('white')

    ax3.plot(df.index, df['MACD'], label='MACD', color='#38bdf8', linewidth=1.4)
    ax3.plot(df.index, df['Signal'], label='الإشارة', color='#f43f5e', linewidth=1.4)
    ax3.bar(df.index, df['Hist'], label='Histogram', color='#9ca3af', alpha=0.6)
    ax3.set_ylabel("MACD", color='white', fontsize=10, fontweight='bold')
    leg3 = ax3.legend(loc='upper left', facecolor='#1f2937', edgecolor='none', fontsize=8)
    for text in leg3.get_texts():
        text.set_color('white')

    plt.tight_layout()
    chart_path = f"/tmp/{clean_symbol}_{interval}_chart.png"
    plt.savefig(chart_path, dpi=200, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    return chart_path

# ==================== لوحة المفاتيح الرئيسية ====================
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(
        types.KeyboardButton("🎯 رادار قنص القاع السعودي الشامل"),
        types.KeyboardButton("🇺🇸 صفقات قنص القاع الأمريكي الشامل"),
        types.KeyboardButton("📊 أسهم العوائد والتشبع الأسبوعي (استثماري)"),
        types.KeyboardButton("📈 المؤشر العام للسوق السعودي"),
        types.KeyboardButton("🔗 رابط دعوتي والترشيح الشخصي"),
        types.KeyboardButton("⚙️ دليل الاستخدام السريع")
    )
    return markup

def get_inline_keyboard(symbol):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_d = types.InlineKeyboardButton("📊 يومي (Daily)", callback_data=f"tf_1d_{symbol}")
    btn_w = types.InlineKeyboardButton("📆 أسبوعي (Weekly)", callback_data=f"tf_1wk_{symbol}")
    markup.add(btn_d, btn_w)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    save_user(message)
    bot_info = bot.get_me()
    user_id = message.chat.id
    ref_link = f"https://t.me/{bot_info.username}?start=REF_{user_id}"
    
    text = (
        "⚡ **منصة قنص القيعان الذكية (الفحص الواسع والشامل)**\n\n"
        "• يغطي الرادار الآن شريحة واسعة وموسعة من أسهم السوق السعودي والأمريكي.\n"
        "• العمل آلي بالكامل ويرسل التنبيهات من تلقاء نفسه.\n\n"
        "• **رابط دعوتك الخاص:**\n"
        f"`{ref_link}`\n\n"
        "👇 **اختر من الأزرار الاحترافية أدناه للبدء:**"
    )
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=get_main_keyboard())

# --- رادار السوق السعودي الشامل ---
@bot.message_handler(func=lambda message: message.text and "رادار قنص القاع السعودي الشامل" in message.text)
def tadawul_market_scan(message):
    save_user(message)
    bot.reply_to(message, "🇸🇦 جاري الفحص الشامل لجميع أسهم القطاعات السعودية لاصطياد قيعان الدخول...", reply_markup=get_main_keyboard())
    
    matched = []
    for symbol in TADAWUL_WATCHLIST:
        df = get_stock_data(symbol, interval="1d")
        if df is not None and not df.empty and 'Bottom_Sniper' in df.columns:
            if df['Bottom_Sniper'].iloc[-1] or df['Bottom_Sniper'].iloc[-2]:
                clean_sym = symbol.replace('.SR', '')
                comp_name = get_company_name(symbol)
                last_close = float(df['Close'].iloc[-1])
                stoch_val = float(df['Stoch_K'].iloc[-1])
                matched.append((comp_name, clean_sym, symbol, last_close, stoch_val))
                if len(matched) >= 8:
                    break

    if not matched:
        bot.reply_to(message, "❌ لا توجد فرص شراء مطابقة حالياً في الفحص الشامل.", reply_markup=get_main_keyboard())
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for comp_name, clean_sym, full_sym, price, stoch in matched:
        btn_text = f"🇸🇦 {comp_name} ({clean_sym}) [Stoch: {stoch:.1f}] - دخول من القاع 🎯"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"trader_pick_{full_sym}"))

    bot.send_message(message.chat.id, "🎯 **نتائج الفحص الشامل للسوق السعودي:**", reply_markup=markup)

# --- رادار السوق الأمريكي الشامل ---
@bot.message_handler(func=lambda message: message.text and "صفقات قنص القاع الأمريكي الشامل" in message.text)
def us_bottom_sniper_scan(message):
    save_user(message)
    bot.reply_to(message, "🇺🇸 جاري الفحص الشامل للأسهم الأمريكية...", reply_markup=get_main_keyboard())
    
    matched = []
    for symbol in US_EXPANDED_WATCHLIST:
        df = get_stock_data(symbol, interval="1d")
        if df is not None and not df.empty and 'Bottom_Sniper' in df.columns:
            if df['Bottom_Sniper'].iloc[-1] or df['Bottom_Sniper'].iloc[-2]:
                comp_name = get_company_name(symbol)
                last_close = float(df['Close'].iloc[-1])
                stoch_val = float(df['Stoch_K'].iloc[-1])
                matched.append((comp_name, symbol, symbol, last_close, stoch_val))
                if len(matched) >= 8:
                    break

    if not matched:
        bot.reply_to(message, "❌ لا توجد فرص حالياً في الأسهم الأمريكية.", reply_markup=get_main_keyboard())
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for comp_name, clean_sym, full_sym, price, stoch in matched:
        btn_text = f"🇺🇸 {comp_name} ({clean_sym}) [Stoch: {stoch:.1f}] - دخول من القاع 🎯"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"trader_pick_{full_sym}"))

    bot.send_message(message.chat.id, "🇺🇸 **نتائج الفحص الشامل للسوق الأمريكي:**", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text and "أسهم العوائد والتشبع الأسبوعي" in message.text)
def weekly_dividends_scan(message):
    save_user(message)
    bot.reply_to(message, "📊 جاري فحص الإطار الأسبوعي الاستثماري على نطاق واسع...", reply_markup=get_main_keyboard())
    
    matched = []
    for symbol in TADAWUL_WATCHLIST:
        df = get_stock_data(symbol, interval="1wk")
        if df is not None and not df.empty and 'Weekly_Oversold' in df.columns:
            if df['Weekly_Oversold'].iloc[-1] or df['Weekly_Oversold'].iloc[-2]:
                clean_sym = symbol.replace('.SR', '')
                comp_name = get_company_name(symbol)
                last_close = float(df['Close'].iloc[-1])
                stoch_val = float(df['Stoch_K'].iloc[-1])
                matched.append((comp_name, clean_sym, symbol, last_close, stoch_val))
                if len(matched) >= 8:
                    break

    if not matched:
        bot.reply_to(message, "❌ لا توجد أسهم مطابقة في التشبع الأسبوعي حالياً.", reply_markup=get_main_keyboard())
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for comp_name, clean_sym, full_sym, price, stoch in matched:
        btn_text = f"📊 {comp_name} ({clean_sym}) [Stoch W: {stoch:.1f}] - استثمار آمن"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"trader_pick_{full_sym}"))

    bot.send_message(message.chat.id, "🛡️ **فرص بناء المراكز الاستثمارية (تشبع أسبوعي واسع):**", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text and "المؤشر العام للسوق السعودي" in message.text)
def daily_market_menu(message):
    save_user(message)
    symbol = "1120.SR"
    df = get_stock_data(symbol, interval="1d")
    if df is None:
        bot.reply_to(message, "❌ تعذر جلب البيانات.", reply_markup=get_main_keyboard())
        return
    last_close = float(df['Close'].iloc[-1])
    comp_name = get_company_name(symbol)
    response = f"📈 **حالة المؤشر والقياديات ({comp_name}):**\n• السعر: {round(last_close, 2)} ريال"
    chart_path = generate_professional_chart(df, symbol, interval="1d")
    with open(chart_path, 'rb') as photo:
        bot.send_photo(message.chat.id, photo, caption=response, parse_mode="Markdown", reply_markup=get_inline_keyboard(symbol))

@bot.message_handler(func=lambda message: message.text and "رابط دعوتي" in message.text)
def my_referral_link(message):
    save_user(message)
    bot_info = bot.get_me()
    user_id = message.chat.id
    users_data = load_users()
    ref_count = users_data.get(str(user_id), {}).get("referrals_count", 0)
    ref_link = f"https://t.me/{bot_info.username}?start=REF_{user_id}"
    resp = f"🔗 **برنامج الدعوة والترشيح الشخصي:**\n\nرابطك الخاص:\n`{ref_link}`\n\n👥 عدد المدعوين: **{ref_count}** شخص."
    bot.reply_to(message, resp, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text and "دليل الاستخدام السريع" in message.text)
def send_help(message):
    save_user(message)
    text = (
        "⚙️ **دليل النظام الاحترافي:**\n"
        "• تم توسيع نطاق البحث ليشمل باقة واسعة وموسعة من أسهم السوق السعودي والأمريكي.\n"
        "• يمكنك إرسال رقم أو رمز أي سهم (مثل `1180` أو `1211` أو أي سهم تريده) لتحليله فوراً بغض النظر عن القائمة."
    )
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("trader_pick_"))
def handle_trader_pick(call):
    save_user(call.message)
    symbol = call.data.replace("trader_pick_", "")
    clean_sym = symbol.replace('.SR', '')
    comp_name = get_company_name(symbol)
    currency = "$" if not symbol.endswith(".SR") else "ريال"
    
    bot.answer_callback_query(call.id, text=f"جاري إعداد التقرير الاحترافي لـ {comp_name}...")
    df = get_stock_data(symbol, interval="1d")
    if df is None or df.empty:
        bot.send_message(call.message.chat.id, f"❌ تعذر جلب بيانات السهم.")
        return
        
    last_close = float(df['Close'].iloc[-1])
    prev_close = float(df['Close'].iloc[-2])
    change = last_close - prev_close
    change_pct = (change / prev_close) * 100
    last_stoch = float(df['Stoch_K'].iloc[-1]) if 'Stoch_K' in df.columns else 0.0
    
    entry_low = round(last_close * 0.985, 2) if currency == "ريال" else round(last_close * 0.985, 4)
    entry_high = round(last_close * 1.00, 2) if currency == "ريال" else round(last_close * 1.00, 4)
    target_1 = round(last_close * 1.03, 2) if currency == "ريال" else round(last_close * 1.05, 4)
    stop_loss = round(last_close * 0.97, 2) if currency == "ريال" else round(last_close * 0.94, 4)
    
    report = (
        f"🎯 **تقرير قنص القاع الاحترافي:**\n\n"
        f"📊 **الشركة:** `{comp_name}` (`{clean_sym}`)\n\n"
        f"• **السعر الحالي:** {last_close:.4f} {currency}\n"
        f"• **التغير اليومي:** {'+' if change >= 0 else ''}{change:.4f} ({change_pct:.2f}%)\n\n"
        f"📋 **خطة الدخول وإدارة الصفقة:**\n"
        f"• 🟢 **منطقة الشراء الموصى بها:** ({entry_low} - {entry_high}) {currency}\n"
        f"• 🎯 **الهدف الأول (+3%):** {target_1} {currency}\n"
        f"• 🛑 **وقف الخسارة:** {stop_loss} {currency}\n\n"
        f"📉 **مؤشر Stoch اللحظي:** **{round(last_stoch, 1)}**"
    )
    
    chart_path = generate_professional_chart(df, symbol, interval="1d", entry_low=entry_low, entry_high=entry_high)
    with open(chart_path, 'rb') as photo:
        bot.send_photo(call.message.chat.id, photo, caption=report, parse_mode="Markdown", reply_markup=get_inline_keyboard(symbol))

@bot.callback_query_handler(func=lambda call: call.data.startswith("tf_"))
def handle_tf_callbacks(call):
    save_user(call.message)
    parts = call.data.split("_")
    interval, symbol = parts[1], parts[2]
    bot.answer_callback_query(call.id, text="جاري تحديث الإطار الزمني...")
    df = get_stock_data(symbol, interval=interval)
    last_close = float(df['Close'].iloc[-1])
    comp_name = get_company_name(symbol)
    currency = "$" if not symbol.endswith(".SR") else "ريال"
    response = f"📊 **تحديث الشارت ({comp_name}):**\n• السعر: {last_close:.4f} {currency}"
    chart_path = generate_professional_chart(df, symbol, interval=interval)
    with open(chart_path, 'rb') as photo:
        bot.send_photo(call.message.chat.id, photo, caption=response, parse_mode="Markdown", reply_markup=get_inline_keyboard(symbol))

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
        
        bot.reply_to(message, f"⏳ جاري تجهيز الشارت النظيف والتقرير الفني الشامل لـ `{comp_name}`...", reply_markup=get_main_keyboard())
        df = get_stock_data(target_symbol, interval="1d")
        
        if df is None or df.empty:
            bot.reply_to(message, f"❌ لم يتم العثور على بيانات كافية للرمز `{clean_target}`.", reply_markup=get_main_keyboard())
            return
            
        last_close = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2])
        change = last_close - prev_close
        change_pct = (change / prev_close) * 100
        last_stoch = float(df['Stoch_K'].iloc[-1]) if 'Stoch_K' in df.columns else 0.0
        
        buy_low = round(last_close * 0.985, 2) if currency == "ريال" else round(last_close * 0.985, 4)
        buy_high = round(last_close * 1.00, 2) if currency == "ريال" else round(last_close * 1.00, 4)
        t1 = round(last_close * 1.03, 2) if currency == "ريال" else round(last_close * 1.05, 4)
        stop = round(last_close * 0.97, 2) if currency == "ريال" else round(last_close * 0.94, 4)
        
        response = (
            f"🎯 **تقرير تحليل السهم: {comp_name} (`{clean_target}`):**\n\n"
            f"• **السعر الحالي:** {last_close:.4f} {currency}\n"
            f"• **التغير اليومي:** {'+' if change >= 0 else ''}{change:.4f} ({change_pct:.2f}%)\n\n"
            f"📋 **خطة الدخول المباشر:**\n"
            f"• 🟢 **منطقة الشراء:** ({buy_low} - {buy_high}) {currency}\n"
            f"• 🎯 **الهدف الأول:** {t1} {currency}\n"
            f"• 🛑 **وقف الخسارة:** {stop} {currency}\n\n"
            f"📉 **مؤشر Stoch:** **{round(last_stoch, 1)}**"
        )
        
        chart_path = generate_professional_chart(df, target_symbol, interval="1d", entry_low=buy_low, entry_high=buy_high)
        with open(chart_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=response, parse_mode="Markdown", reply_markup=get_inline_keyboard(target_symbol))
    else:
        bot.reply_to(message, f"🤖 أهلاً بك! يمكنك إرسال رقم أو رمز أي سهم (مثل 1180 أو 1211) في أي وقت لتحليله فوراً.", reply_markup=get_main_keyboard())

# --- دالة الإرسال التلقائي اليومي الشامل ---
def job_auto_market_scan():
    users = load_users()
    if not users:
        return
    
    for user_id in users.keys():
        try:
            bot.send_message(int(user_id), "🔔 **تنبيه تلقائي من الرادار الشامل:** جاري فحص السوق لاصطياد الفرصة المؤكدة...")
            
            for symbol in TADAWUL_WATCHLIST:
                df = get_stock_data(symbol, interval="1d")
                if df is not None and not df.empty and 'Bottom_Sniper' in df.columns:
                    if df['Bottom_Sniper'].iloc[-1] or df['Bottom_Sniper'].iloc[-2]:
                        clean_sym = symbol.replace('.SR', '')
                        comp_name = get_company_name(symbol)
                        last_close = float(df['Close'].iloc[-1])
                        last_stoch = float(df['Stoch_K'].iloc[-1])
                        
                        entry_low = round(last_close * 0.985, 2)
                        entry_high = round(last_close * 1.00, 2)
                        t1 = round(last_close * 1.03, 2)
                        stop = round(last_close * 0.97, 2)
                        
                        report = (
                            f"🎯 **فرصة دخول مؤكدة (تنبيه آلي واسع):**\n\n"
                            f"📊 **الشركة:** `{comp_name}` (`{clean_sym}`)\n\n"
                            f"• **السعر الحالي:** {last_close:.2f} ريال\n"
                            f"• **نوع الفرصة:** قاع حقيقي ونظيف 🎯\n\n"
                            f"🎯 **المستويات الفنية:**\n"
                            f"• 🟢 **منطقة الشراء:** ({entry_low} - {entry_high}) ريال\n"
                            f"• 🎯 **الهدف الأول:** {t1} ريال\n"
                            f"• 🛑 **وقف الخسارة:** {stop} ريال"
                        )
                        
                        chart_path = generate_professional_chart(df, symbol, interval="1d", entry_low=entry_low, entry_high=entry_high)
                        with open(chart_path, 'rb') as photo:
                            bot.send_photo(int(user_id), photo, caption=report, parse_mode="Markdown", reply_markup=get_inline_keyboard(symbol))
                        break
        except Exception as e:
            print(f"Error in auto job for user {user_id}: {e}")

def run_scheduler():
    schedule.every().day.at("11:00").do(job_auto_market_scan)
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    print("Wide-Scan Professional Sniper Bot is running successfully...")
    bot.infinity_polling()
