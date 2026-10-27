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
    return "Institutional Elite Sniper & Whale Detector Bot is active and running 24/7!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ==================== إعدادات بوت تيليقرام ====================
TOKEN = "8961540572:AAGLzgU3PwqXopo_BGyai7t4PzJf1cB-eGs"
bot = telebot.TeleBot(TOKEN)

# ⚠️ ضع هنا معرف التيليقرام الخاص بك (Admin ID) لتتمكن من استخدام أوامر الأدمن مثل الإذاعة
ADMIN_ID = 000000000  # استبدل الأصفار بمعرفك الرقمي إن أردت

WATCHLIST = [
    "1120.SR", "1180.SR", "2222.SR", "1211.SR", "2010.SR", 
    "1301.SR", "4200.SR", "7010.SR", "1820.SR", "4300.SR"
]

USERS_FILE = "elite_users_data.json"

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

def generate_professional_chart(df, symbol, interval="1d"):
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 11), sharex=True, gridspec_kw={'height_ratios': [3, 1, 1]})
    tf_name = "الإطار الأسبوعي (Weekly)" if interval == "1wk" else "الإطار اليومي (Daily)"
    clean_symbol = symbol.replace('.SR', '')
    
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
    ax1.set_title(f"التحليل الفني المؤسسي | سهم: {clean_symbol} [{tf_name}]", fontsize=13, fontweight='bold', color='white', pad=10)
    ax1.set_ylabel("السعر (ريال)", color='white', fontsize=10)
    leg1 = ax1.legend(loc='upper left', facecolor='#0f172a', edgecolor='none')
    for text in leg1.get_texts():
        text.set_color('white')

    ax2.plot(df.index, df['RSI'], label='مؤشر القوة النسبية RSI (14)', color='#c084fc', linewidth=1.2)
    ax2.axhline(70, color='#ef4444', linestyle='--', alpha=0.7, label='منطقة التشبع الشرائي (70)')
    ax2.axhline(30, color='#22c55e', linestyle='--', alpha=0.7, label='منطقة التشبع البيعي (30)')
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
    chart_path = f"/tmp/{clean_symbol}_{interval}_pro_chart.png"
    plt.savefig(chart_path, dpi=180, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    return chart_path

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🎯 فحص الفرص والاهداف"),
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
        "🏛 **مرحباً بك في المنصة المؤسسية المتقدمة للسوق السعودي (Tadawul)**\n\n"
        "• تحليل فني ذكي، رادار اختراق القمم، كاشف سيولة صناع السوق (Whales)، وحاسبة تعديل التكلفة.\n"
        "• **رابط دعوتك الخاص لنشر البوت:**\n"
        f"`{ref_link}`\n\n"
        "👇 **اختر من الأزرار أدناه، أو أرسل رمز السهم، أو اسأل سؤالك مباشرة:**"
    )
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(commands=['stats', 'users'])
def show_user_stats(message):
    save_user(message)
    users_data = load_users()
    total_users = len(users_data)
    
    details = f"📊 **لوحة الإحصائيات المؤسسية السرية:**\n\n• إجمالي المستخدمين: **{total_users}** مستخدم\n\n**أبرز الداعمين نشاطاً:**\n"
    sorted_users = sorted(users_data.values(), key=lambda x: x['referrals_count'], reverse=True)
    for idx, u in enumerate(sorted_users[:5], 1):
        if u['referrals_count'] > 0:
            details += f"{idx}. {u['name']} ({u['referrals_count']} دعوات)\n"
            
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
            bot.send_message(int(uid), f"📢 **إعلان هام من الإدارة:**\n\n{msg_to_send}", parse_mode="Markdown")
            success += 1
        except:
            pass
    bot.reply_to(message, f"✅ تم إرسال البث بنجاح إلى `{success}` مستخدم.", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text and "رابط دعوتي" in message.text)
def my_referral_link(message):
    save_user(message)
    bot_info = bot.get_me()
    user_id = message.chat.id
    users_data = load_users()
    ref_count = users_data.get(str(user_id), {}).get("referrals_count", 0)
    ref_link = f"https://t.me/{bot_info.username}?start=REF_{user_id}"
    
    resp = (
        f"🔗 **برنامج الدعوة والنشر الذكي:**\n\n"
        f"شارك رابطك الخاص مع أصدقائك وفي قروبات التداول:\n"
        f"`{ref_link}`\n\n"
        f"👥 عدد الأشخاص الذين انضموا عبر رابطك: **{ref_count}** شخص.\n"
        f"شكراً لمساهمتك في نشر المنصة!"
    )
    bot.reply_to(message, resp, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text and "المساعدة" in message.text)
def send_help(message):
    save_user(message)
    text = (
        "⚙️ **دليل الاستخدام الاحترافي:**\n"
        "1️⃣ **البحث الذكي:** اكتب سؤالك واذكر رقم السهم (مثل: `أين دعم سهم 1820؟`).\n"
        "2️⃣ **البحث المباشر:** أرسل رقم السهم (مثل `2222`).\n"
        "3️⃣ **حاسبة التعديل:** أرسل `تعديل [الرمز] [كميتك] [متوسطك] [الكمية الجديدة]`"
    )
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text and "رادار الاختراق" in message.text)
def breakout_sniper_scan(message):
    save_user(message)
    bot.reply_to(message, "🚀 جاري تشغيل رادار اختراق القمم (Breakout Sniper) وكاشف سيولة صناع السوق (Whales)...", reply_markup=get_main_keyboard())
    found = False
    for symbol in WATCHLIST:
        df = get_stock_data(symbol, interval="1d")
        if df is not None and not df.empty:
            last_close = float(df['Close'].iloc[-1])
            high_52 = float(df['High_52w'].iloc[-1]) if not pd.isna(df['High_52w'].iloc[-1]) else last_close
            last_vol = float(df['Volume'].iloc[-1])
            vol_sma = float(df['Vol_SMA20'].iloc[-1]) if not pd.isna(df['Vol_SMA20'].iloc[-1]) else last_vol
            
            # شرط الاختراق أو التدفق الهائل للسيولة (صناع السوق)
            if last_close >= (high_52 * 0.98) or last_vol > (vol_sma * 1.6):
                found = True
                prev_close = float(df['Close'].iloc[-2])
                change = last_close - prev_close
                change_pct = (change / prev_close) * 100
                vol_ratio = round(last_vol / vol_sma, 2) if vol_sma > 0 else 1.0
                
                sniper_alert = (
                    f"🚀 **رادار اختراق المقاومات والسيولة الكبرى (Sniper & Whales):**\n\n"
                    f"📊 **سهم تداول:** `{symbol.replace('.SR', '')}`\n\n"
                    f"• **السعر الحالي:** {round(last_close, 2)} ريال\n"
                    f"• **التغير اليومي:** {'+' if change >= 0 else ''}{round(change, 2)} ({round(change_pct, 2)}%)\n"
                    f"• **أعلى قمة تتبع (52 أسبوع):** {round(high_52, 2)} ريال\n\n"
                    f"🐋 **كاشف سيولة صناع السوق:**\n"
                    f"• حجم التداول يشكل **{vol_ratio}x** من المتوسط التاريخي! ⚡️\n"
                    f"• الحالة: **فرصة اختراق قوية / دخول محافظ كبرى**"
                )
                
                chart_path = generate_professional_chart(df, symbol, interval="1d")
                with open(chart_path, 'rb') as photo:
                    bot.send_photo(message.chat.id, photo, caption=sniper_alert, parse_mode="Markdown", reply_markup=get_inline_keyboard(symbol))
                break
                
    if not found:
        bot.reply_to(message, "لم يتم رصد اختراقات أو تدفقات ضخمة لصناع السوق في قائمة المتابعة حالياً.", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text and "فحص الفرص" in message.text)
def scan_targets(message):
    save_user(message)
    bot.reply_to(message, "🔍 جاري فحص رادار السيولة وأحجام التداول في السوق السعودي...", reply_markup=get_main_keyboard())
    found = False
    for symbol in WATCHLIST:
        df = get_stock_data(symbol, interval="1d")
        if df is not None and not df.empty:
            last_rsi = float(df['RSI'].iloc[-1])
            last_close = float(df['Close'].iloc[-1])
            last_vol = float(df['Volume'].iloc[-1])
            vol_sma = float(df['Vol_SMA20'].iloc[-1]) if not pd.isna(df['Vol_SMA20'].iloc[-1]) else last_vol
            
            if last_vol > (vol_sma * 1.3) or last_rsi < 50:
                found = True
                prev_close = float(df['Close'].iloc[-2])
                change = last_close - prev_close
                change_pct = (change / prev_close) * 100
                
                buy_low = round(last_close * 0.985, 2)
                buy_high = round(last_close * 1.00, 2)
                t1 = round(last_close * 1.04, 2)
                t2 = round(last_close * 1.08, 2)
                stop = round(last_close * 0.95, 2)
                
                volume_status = "🔥 تدفق سيولة مؤسسي عالٍ جداً" if last_vol > (vol_sma * 1.5) else "⚖️ حركة سيولة طبيعية متوازنة"
                
                response = (
                    f"🏛 **تقرير رادار السيولة وفرصة انطلاق:**\n\n"
                    f"📊 **شركة تداول:** `{symbol.replace('.SR', '')}`\n\n"
                    f"• **السعر الحالي:** {round(last_close, 2)} ريال\n"
                    f"• **التغير اليومي:** {'+' if change >= 0 else ''}{round(change, 2)} ({round(change_pct, 2)}%)\n\n"
                    f"🎯 **مستويات التداول الرئيسية:**\n"
                    f"• 🟢 **منطقة الشراء المقترحة:** ({buy_low} - {buy_high}) ريال\n"
                    f"• 🎯 **الهدف الأول:** {t1} ريال | **الهدف الثاني:** {t2} ريال\n"
                    f"• 🛑 **وقف الخسارة الإلزامي:** {stop} ريال\n\n"
                    f"📊 **رادار السيولة والمؤشرات:**\n"
                    f"• حالة السيولة: **{volume_status}**\n"
                    f"• مؤشر RSI: **{round(last_rsi, 1)}**"
                )
                
                chart_path = generate_professional_chart(df, symbol, interval="1d")
                with open(chart_path, 'rb') as photo:
                    bot.send_photo(message.chat.id, photo, caption=response, parse_mode="Markdown", reply_markup=get_inline_keyboard(symbol))
                break
                
    if not found:
        bot.reply_to(message, "لم يتم العثور على فرص مطابقة لمعايير رادار السيولة حالياً.", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text and ("السوق السعودي اليومي" in message.text or "التحليل الأسبوعي" in message.text))
def quick_menus(message):
    save_user(message)
    interval = "1wk" if "الأسبوعي" in message.text else "1d"
    symbol = "1120.SR"
    tf_desc = "الإطار الأسبوعي طويل الأجل" if interval == "1wk" else "الإطار اليومي"
    
    bot.reply_to(message, f"⏳ جاري جلب تحليل السيولة بفاصل ({tf_desc})...")
    df = get_stock_data(symbol, interval=interval)
    if df is None:
        bot.reply_to(message, "❌ تعذر جلب البيانات حالياً.", reply_markup=get_main_keyboard())
        return
        
    last_close = float(df['Close'].iloc[-1])
    prev_close = float(df['Close'].iloc[-2])
    change = last_close - prev_close
    change_pct = (change / prev_close) * 100
    last_rsi = float(df['RSI'].iloc[-1])
    
    response = (
        f"🏛 **تقرير مؤشر السوق والأسهم القيادية ({tf_desc}):**\n\n"
        f"📊 **السهم المرجعي:** `{symbol.replace('.SR', '')}`\n\n"
        f"• **السعر الحالي:** {round(last_close, 2)} ريال\n"
        f"• **التغير:** {'+' if change >= 0 else ''}{round(change, 2)} ({round(change_pct, 2)}%)\n"
        f"• **مؤشر RSI:** {round(last_rsi, 1)}"
    )
    
    chart_path = generate_professional_chart(df, symbol, interval=interval)
    with open(chart_path, 'rb') as photo:
        bot.send_photo(message.chat.id, photo, caption=response, parse_mode="Markdown", reply_markup=get_inline_keyboard(symbol))

@bot.callback_query_handler(func=lambda call: call.data.startswith("tf_") or call.data.startswith("dca_"))
def handle_inline_callbacks(call):
    save_user(call.message)
    if call.data.startswith("tf_"):
        parts = call.data.split("_")
        interval = parts[1]
        symbol = parts[2]
        
        tf_name = "الإطار الأسبوعي (Weekly)" if interval == "1wk" else "الإطار اليومي (Daily)"
        bot.answer_callback_query(call.id, text=f"تم التبديل إلى {tf_name} بنجاح...")
        
        df = get_stock_data(symbol, interval=interval)
        if df is None:
            bot.send_message(call.message.chat.id, "❌ حدث خطأ أثناء تحديث بيانات الشارت.")
            return
            
        last_close = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2])
        change = last_close - prev_close
        change_pct = (change / prev_close) * 100
        last_rsi = float(df['RSI'].iloc[-1])
        
        response = (
            f"🏛 **تحديث التحليل المؤسسي [{tf_name}]:**\n\n"
            f"📊 **Tadawul:** `{symbol.replace('.SR', '')}`\n\n"
            f"• **السعر الحالي:** {round(last_close, 2)} ريال\n"
            f"• **التغير:** {'+' if change >= 0 else ''}{round(change, 2)} ({round(change_pct, 2)}%)\n"
            f"• **مؤشر القوة النسبية RSI:** {round(last_rsi, 1)}"
        )
        
        chart_path = generate_professional_chart(df, symbol, interval=interval)
        with open(chart_path, 'rb') as photo:
            bot.send_photo(call.message.chat.id, photo, caption=response, parse_mode="Markdown", reply_markup=get_inline_keyboard(symbol))
            
    elif call.data.startswith("dca_"):
        symbol = call.data.split("_")[1]
        clean_sym = symbol.replace('.SR', '')
        bot.answer_callback_query(call.id, text="🧮 حاسبة تعديل التكلفة السريعة")
        
        guide_text = (
            f"🧮 **دليل حاسبة تعديل التكلفة للسهم (`{clean_sym}`):**\n\n"
            f"لحساب متوسط السعر الجديد فوراً، أرسل رسالة بالشكل التالي:\n\n"
            f"`تعديل {clean_sym} [كميتك الحالية] [متوسطك الحالي] [الكمية الجديدة]`\n\n"
            f"📌 **مثال سريع:**\n"
            f"`تعديل {clean_sym} 1000 2.50 500`"
        )
        bot.send_message(call.message.chat.id, guide_text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text and message.text.strip().startswith("تعديل"))
def calculate_dca_result(message):
    save_user(message)
    try:
        parts = message.text.strip().split()
        if len(parts) < 5:
            bot.reply_to(message, "❌ الصيغة غير صحيحة. يرجى الإرسال هكذا:\n`تعديل [الرمز] [كميتك الحالية] [متوسطك الحالي] [الكمية الجديدة]`", parse_mode="Markdown")
            return
            
        sym = parts[1].upper()
        symbol = sym + ".SR" if not sym.endswith(".SR") else sym
        curr_shares = float(parts[2])
        curr_avg = float(parts[3])
        new_shares = float(parts[4])
        
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1d")
        if df is None or df.empty:
            bot.reply_to(message, "❌ تعذر جلب السعر الحالي للسهم لتنفيذ الحساب.")
            return
        market_price = float(df['Close'].iloc[-1])
        
        total_old_cost = curr_shares * curr_avg
        total_new_cost = new_shares * market_price
        total_shares = curr_shares + new_shares
        new_average = (total_old_cost + total_new_cost) / total_shares
        
        diff_avg = new_average - curr_avg
        
        result_msg = (
            f"🧮 **نتيجة حساب تعديل التكلفة (`{sym}`):**\n\n"
            f"• **السعر الحالي بالسوق:** {market_price:.2f} ريال\n"
            f"• **الكمية القديمة:** {curr_shares:,.0f} سهم (بمتوسط {curr_avg:.2f} ريال)\n"
            f"• **الكمية الجديدة المضافة:** {new_shares:,.0f} سهم\n\n"
            f"🎯 **النتيجة النهائية:**\n"
            f"• **إجمالي الأسهم:** {total_shares:,.0f} سهم\n"
            f"• **متوسط التكلفة الجديد:** **{new_average:.2f} ريال**\n"
            f"• **مقدار الانخفاض في المتوسط:** {abs(diff_avg):.2f} ريال\n\n"
            f"💪 بالتوفيق في صفقاتك!"
        )
        bot.reply_to(message, result_msg, parse_mode="Markdown", reply_markup=get_main_keyboard())
    except Exception as e:
        bot.reply_to(message, "❌ حدث خطأ في قراءة الأرقام. تأكد من كتابة الأرقام بشكل صحيح.")

@bot.message_handler(func=lambda message: True)
def handle_context_aware_message(message):
    save_user(message)
    text = message.text.strip()
    
    numbers_found = re.findall(r'\b\d{3,5}\b', text)
    
    if numbers_found or text.upper().endswith(".SR") or text.isdigit():
        target_num = numbers_found[0] if numbers_found else text.upper().replace(".SR", "")
        symbol = target_num + ".SR"
        
        bot.reply_to(message, f"⏳ فهمت قصدك! جاري تحليل السهم `{target_num}` وجلب مستويات الدعم والشارت بناءً على سؤالك...", reply_markup=get_main_keyboard())
        df = get_stock_data(symbol, interval="1d")
        
        if df is None or df.empty:
            bot.reply_to(message, f"❌ لم يتم العثور على بيانات للسهم `{target_num}`. تأكد من صحة رقم السهم في السوق السعودي.", reply_markup=get_main_keyboard())
            return
            
        last_close = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2])
        change = last_close - prev_close
        change_pct = (change / prev_close) * 100
        last_rsi = float(df['RSI'].iloc[-1])
        last_vol = float(df['Volume'].iloc[-1])
        vol_sma = float(df['Vol_SMA20'].iloc[-1]) if not pd.isna(df['Vol_SMA20'].iloc[-1]) else last_vol
        
        buy_low = round(last_close * 0.985, 2)
        buy_high = round(last_close * 1.00, 2)
        t1 = round(last_close * 1.05, 2)
        t2 = round(last_close * 1.10, 2)
        stop = round(last_close * 0.945, 2)
        
        vol_ratio = round(last_vol / vol_sma, 2) if vol_sma > 0 else 1.0
        vol_desc = f"نشاط سيولة عالي ({vol_ratio}x من المتوسط) 🔥" if vol_ratio > 1.2 else "حجم تداول طبيعي مستقر ⚖️"
        
        response = (
            f"🏛 **رد تحليلي حسب سؤالك (سهم `{target_num}`):**\n\n"
            f"• **السعر الحالي:** {round(last_close, 2)} ريال\n"
            f"• **التغير:** {'+' if change >= 0 else ''}{round(change, 2)} ({round(change_pct, 2)}%)\n\n"
            f"🎯 **مستويات الدعم والهدف بناءً على طلبك:**\n"
            f"• 🟢 **منطقة الدعم والشراء المناسبة:** ({buy_low} - {buy_high}) ريال\n"
            f"• 🎯 **الهدف الأول:** {t1} ريال | **الهدف الثاني:** {t2} ريال\n"
            f"• 🛑 **وقف الخسارة الصارم:** {stop} ريال\n\n"
            f"📉 **تحليل المؤشرات والسيولة:**\n"
            f"• رادار أحجام التداول: **{vol_desc}**\n"
            f"• مؤشر RSI (14): **{round(last_rsi, 1)}**"
        )
        
        chart_path = generate_professional_chart(df, symbol, interval="1d")
        with open(chart_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=response, parse_mode="Markdown", reply_markup=get_inline_keyboard(symbol))
    else:
        chat_reply = (
            f"🤖 **مرحباً بك يا غالي:**\n\n"
            f"لقد استلمت سؤالك: *\"{text}\"*\n\n"
            f"💡 لكي أجيبك بدقة على نفس سياق سؤالك، يرجى **ذكر رقم السهم** في جملتك (مثال: *ما هي مناطق دعم سهم 1820؟* أو *كيف أحلل سهم 1120؟*)، وسأقوم بتحليله وإرسال الشارت والمستويات فوراً!"
        )
        bot.reply_to(message, chat_reply, parse_mode="Markdown", reply_markup=get_main_keyboard())

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    print("Institutional Elite Sniper & Whale Detector Bot is running...")
    bot.infinity_polling()
