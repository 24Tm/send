def fetch_stock_data(text):
    text = text.strip().upper()
    possible_symbols = []
    
    if text.isdigit():
        # محاولة اللاحقتين المعتمدتين في السوق السعودي لدى ياهو فاينانس
        possible_symbols = [f"{text}.SR", f"{text}.SA"]
    elif text.endswith("SR") and not text.endswith(".SR"):
        base = text[:-2].strip()
        possible_symbols = [f"{base}.SR", f"{base}.SA"]
    elif text.endswith("SA") and not text.endswith(".SA"):
        base = text[:-2].strip()
        possible_symbols = [f"{base}.SA", f"{base}.SR"]
    else:
        possible_symbols = [text, f"{text}.SR", f"{text}.SA"]

    for sym in possible_symbols:
        try:
            stock = yf.Ticker(sym)
            hist = stock.history(period="3mo")
            if not hist.empty and len(hist) > 0 and hist['Close'].iloc[-1] > 0:
                return hist, sym
        except Exception:
            continue
    return None, text
