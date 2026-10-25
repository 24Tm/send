import os
import pandas as pd
import pandas_ta as ta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import yfinance as yf

# قراءة توكن البوت من متغيرات البيئة بأمان
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
    "أهلاً بك! استخدم الأمر هكذا لتحليل أي سهم:\n`/analyze 1120.SR`\nمثال:"
    " الأسهم السعودية تضاف لها `.SR`",
    parse_mode="Markdown",
  )


async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if not context.args:
    await update.message.reply_text(
      "الرجاء كتابة رمز السهم بجانب الأمر. مثال:\n`/analyze 1120.SR`",
      parse_mode="Markdown",
    )
    return

  symbol = context.args[0].upper()
  await update.message.reply_text(
    f"⏳ جاري جلب بيانات السهم `{symbol}` وتحليله فنياً..."
  )

  try:
    # جلب بيانات السهم آخر 6 أشهر
    df = yf.download(symbol, period="6mo", interval="1d", progress=False)

    if df.empty:
      await update.message.reply_text(
        "❌ لم أتمكن من العثور على بيانات لهذا السهم. تأكد من الرمز الصحيح (مثال:"
        " 1120.SR لمصرف الراجحي)."
      )
      return

    # حساب المؤشرات الفنية
    df["SMA_50"] = ta.sma(df["Close"], length=50)
    df["SMA_200"] = ta.sma(df["Close"], length=200)
    df["RSI"] = ta.rsi(df["Close"], length=14)

    last_close = float(df["Close"].iloc[-1])
    last_rsi = float(df["RSI"].iloc[-1])
    sma_50 = (
      float(df["SMA_50"].iloc[-1]) if not pd.isna(df["SMA_50"].iloc[-1]) else 0
    )

    # منطق التوصيات
    if last_rsi < 30 and last_close > sma_50:
      recommendation = "🟢 **دخول مضارب** (تشبع بيعي مع ارتداد محتمل)"
    elif last_rsi > 70:
      recommendation = "🔴 **خروج / جني أرباح** (تشبع شرائي)"
    elif last_close > sma_50:
      recommendation = "🔵 **شراء** (اتجاه صاعد مستقر)"
    else:
      recommendation = "⚠️ **حياد / مراقبة** (سلبية أو تذبذب)"

    report = f"""
📊 **تقرير تحليل السهم: {symbol}**
------------------
💰 سعر الإغلاق: `{last_close:.2f}`
📈 مؤشر القوة النسبي (RSI): `{last_rsi:.2f}`
🎯 **التوصية:** {recommendation}
    """
    await update.message.reply_text(report, parse_mode="Markdown")

  except Exception as e:
    await update.message.reply_text(
      f"حدث خطأ أثناء معالجة البيانات: {str(e)}"
    )


def main():
  if not TOKEN:
    print("خطأ: يرجى تحديد توكن البوت في متغيرات البيئة.")
    return

  app = ApplicationBuilder().token(TOKEN).build()

  app.add_handler(CommandHandler("start", start))
  app.add_handler(CommandHandler("analyze", analyze))

  print("البوت يعمل الآن...")
  app.run_polling()


if __name__ == "__main__":
  main()
