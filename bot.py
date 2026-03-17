#!pip install pandas_ta
import pandas_ta as ta

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os


ticker = "^NSEI"
def get_nifty_data():
    # Fetch 5m and 1m data
    df_5m = yf.download(ticker, period="5d", interval="5m")
    df_1m = yf.download(ticker, period="2d", interval="1m")

    # Flatten MultiIndex columns and rename for easier access
    # Example: ('Price', 'Close') -> 'Close'
    #          ('Volume', '') -> 'Volume'
    def flatten_columns(df):
        new_columns = []
        for col in df.columns.values:
            if isinstance(col, tuple):
                # Join non-empty parts of the tuple
                new_col = '_'.join(filter(None, col))
            else:
                new_col = str(col)
            new_columns.append(new_col)
        df.columns = new_columns
        
        # Clean up common prefixes if they appear (e.g., 'Price_Close' to 'Close')
        df.columns = [col.replace('Price_', '') for col in df.columns]
        #df.columns = [col.replace(f'_{ticker}', '') for col in df.columns]
        df.columns = df.columns.str.replace(f'_{ticker}', '', regex=False)

        #print(df.columns)
        # Drop any 'Ticker' related columns if they are not needed for calculations
        df = df.drop(columns=[col for col in df.columns if 'Ticker' in col], errors='ignore')
        
        return df

    df_5m = flatten_columns(df_5m)
    df_1m = flatten_columns(df_1m)

    return df_5m, df_1m

def apply_strategy(df5, df1):
    # Indicators
    df5['SMA5'] = ta.sma(df5['Close'], length=5)
    df5['EMA18'] = ta.ema(df5['Close'], length=18)
    df5['SMA50'] = ta.sma(df5['Close'], length=50)
    df5['RSI14_5m'] = ta.rsi(df5['Close'], length=14)
    print(df5)

    # Check if df1 has enough data to calculate RSI (length 14 for RSI)
    if len(df1) >= 14:
        rsi1m = ta.rsi(df1['Close'], length=14)
        if rsi1m is not None:
            df5['RSI14_1m'] = rsi1m.reindex(df5.index, method='ffill')
        else:
            # If ta.rsi returns None even with enough data, fill with NaN
            df5['RSI14_1m'] = np.nan
    else:
        # If df1 doesn't have enough data, fill with NaN
        df5['RSI14_1m'] = np.nan

    df5['VWAP'] = ta.vwap(df5['High'], df5['Low'], df5['Close'], df5['Volume'])
    bb = ta.bbands(df5['Close'], length=20, std=1)

    #print(bb)

    # Check if bb is None before accessing its keys
    if bb is not None:
        df5['BB_Upper_1'] = bb['BBU_20_2.0_2.0']
    else:
        df5['BB_Upper_1'] = np.nan # Fill with NaN if BBands cannot be calculated

    qqe = ta.qqe(df5['Close'])
    # Check if qqe is None before accessing its columns
    if qqe is not None:
        df5['QQE_Green'] = qqe.iloc[:, 0] > qqe.iloc[:, 2]
    else:
        df5['QQE_Green'] = np.nan # Fill with NaN if QQE cannot be calculated

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
#print(df_5m)
#print(df_1m)
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
