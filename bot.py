import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import requests
import os

# --- Configuration & Secrets ---
# These are pulled from your GitHub Repository Secrets
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing. Skipping alert.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending alert: {e}")

def get_nifty_data():
    # Fetch 5m and 1m data
    df_5m = yf.download("^NSEI", period="5d", interval="5m")
    df_1m = yf.download("^NSEI", period="2d", interval="1m")
    return df_5m, df_1m

def apply_strategy(df5, df1):
    # Indicators
    df5['SMA5'] = ta.sma(df5['Close'], length=5)
    df5['EMA18'] = ta.ema(df5['Close'], length=18)
    df5['SMA50'] = ta.sma(df5['Close'], length=50)
    df5['RSI14_5m'] = ta.rsi(df5['Close'], length=14)
    
    rsi1m = ta.rsi(df1['Close'], length=14)
    df5['RSI14_1m'] = rsi1m.reindex(df5.index, method='ffill')

    df5['VWAP'] = ta.vwap(df5['High'], df5['Low'], df5['Close'], df5['Volume'])
    bb = ta.bbands(df5['Close'], length=20, std=1)
    df5['BB_Upper_1'] = bb['BBU_20_1.0']

    qqe = ta.qqe(df5['Close'])
    df5['QQE_Green'] = qqe.iloc[:, 0] > qqe.iloc[:, 2]
    
    # Hoffman IRB Logic
    df5['Range'] = df5['High'] - df5['Low']
    df5['Is_IRB_Setup'] = (df5['Close'] <= (df5['Low'] + 0.45 * df5['Range'])) & (df5['High'] > df5['High'].shift(1))
    df5['IRB_High'] = df5['High'].where(df5['Is_IRB_Setup']).ffill()
    
    # Check current status
    curr = df5.iloc[-1]
    prev = df5.iloc[-2]

    # Signal Condition
    is_signal = (
        (curr['Close'] > curr['VWAP']) and (curr['RSI14_5m'] > 55) and 
        (curr['RSI14_1m'] > 55) and (curr['Close'] > curr['BB_Upper_1']) and
        (curr['Close'] > curr['IRB_High']) and (curr['QQE_Green']) and
        (curr['SMA5'] > curr['EMA18']) and (curr['SMA5'] > curr['SMA50'])
    )
    
    return curr, is_signal

# --- Main Execution ---
df_5m, df_1m = get_nifty_data()
current_row, signal_found = apply_strategy(df_5m, df_1m)

if signal_found:
    entry = round(current_row['Close'], 2)
    sl = round(current_row['Low'], 2) # Simplified SL for alert
    risk = entry - sl
    tp1 = round(entry + risk, 2)
    tp2 = round(entry + (risk * 2), 2)
    
    msg = (
        f"🚀 *NIFTY BUY SIGNAL FOUND*\n\n"
        f"Entry: `{entry}`\n"
        f"Stop Loss: `{sl}`\n"
        f"Target 1 (50%): `{tp1}`\n"
        f"Target 2 (Final): `{tp2}`\n\n"
        f"Note: Once T1 is hit, move SL to Entry!"
    )
    send_telegram_msg(msg)
    print("Signal found and alert sent.")
else:
    print("No signal at this interval.")
