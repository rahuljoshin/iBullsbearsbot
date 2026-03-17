import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np


def get_nifty_data():
    # Fetches 5-minute and 1-minute data for Nifty 50
    df_5m = yf.download("^NSEI", period="1mo", interval="5m")
    df_1m = yf.download("^NSEI", period="7d", interval="1m")
    return df_5m, df_1m


def apply_strategy(df5, df1):
    # Standard Technical Indicators
    df5['SMA5'] = ta.sma(df5['Close'], length=5)
    df5['EMA18'] = ta.ema(df5['Close'], length=18)
    df5['SMA50'] = ta.sma(df5['Close'], length=50)
    df5['RSI14_5m'] = ta.rsi(df5['Close'], length=14)

    # RSI alignment (1m to 5m)
    rsi1m = ta.rsi(df1['Close'], length=14)
    df5['RSI14_1m'] = rsi1m.reindex(df5.index, method='ffill')

    # VWAP and BB1
    df5['VWAP'] = ta.vwap(df5['High'], df5['Low'], df5['Close'], df5['Volume'])
    bb = ta.bbands(df5['Close'], length=20, std=1)
    df5['BB_Upper_1'] = bb['BBU_20_1.0']

    # QQE and IRB
    qqe = ta.qqe(df5['Close'])
    df5['QQE_Green'] = qqe.iloc[:, 0] > qqe.iloc[:, 2]

    df5['Range'] = df5['High'] - df5['Low']
    df5['Is_IRB_Setup'] = (df5['Close'] <= (df5['Low'] + 0.45 * df5['Range'])) & (df5['High'] > df5['High'].shift(1))
    df5['IRB_High'] = df5['High'].where(df5['Is_IRB_Setup']).ffill()
    df5['IRB_Crossing'] = (df5['Close'] > df5['IRB_High'])

    # Entry Signal
    df5['Signal'] = (
            (df5['Close'] > df5['VWAP']) & (df5['RSI14_5m'] > 55) &
            (df5['RSI14_1m'] > 55) & (df5['Close'] > df5['BB_Upper_1']) &
            (df5['IRB_Crossing']) & (df5['QQE_Green']) &
            (df5['SMA5'] > df5['EMA18']) & (df5['SMA5'] > df5['SMA50'])
    )
    return df5


def simulate_trades(df):
    df['Entry_Price'] = np.nan
    df['SL'] = np.nan
    df['TP_Partial'] = np.nan  # Target 1 (1:1 RR)
    df['TP_Final'] = np.nan  # Target 2 (2:1 RR)

    for i in range(len(df)):
        if df['Signal'].iloc[i]:
            entry = df['Close'].iloc[i]
            sl = df['Low'].where(df['Is_IRB_Setup']).ffill().iloc[i]
            risk = entry - sl

            if risk > 0:
                df.iat[i, df.columns.get_loc('Entry_Price')] = round(entry, 2)
                df.iat[i, df.columns.get_loc('SL')] = round(sl, 2)
                df.iat[i, df.columns.get_loc('TP_Partial')] = round(entry + risk, 2)
                df.iat[i, df.columns.get_loc('TP_Final')] = round(entry + (risk * 2), 2)
    return df


# Execution
df_5m, df_1m = get_nifty_data()
df_final = simulate_trades(apply_strategy(df_5m, df_1m))

# Performance Report
active_trades = df_final[df_final['Signal'] == True]
print(f"Signals Found (Last 30 Days): {len(active_trades)}")
print(active_trades[['Entry_Price', 'SL', 'TP_Partial', 'TP_Final']].tail(5))
