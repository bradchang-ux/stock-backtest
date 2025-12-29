import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def verify_logic():
    symbol = "SPY"
    # Pick a specific week to test manually.
    # Target Week Ending around: 2023-10-27 (Friday)
    # Week range (Pandas W): usually ends Sunday.
    # Let's see what the logic produces.
    
    print(f"Fetching data for {symbol}...")
    start_date = "2023-10-01"
    end_date = "2023-11-15"
    df = yf.download(symbol, start=start_date, end=end_date, progress=False, multi_level_index=False)
    df.index = pd.to_datetime(df.index)
    
    print("Data fetched. Rows:", len(df))
    
    # 2. Group by Week
    weekly_groups = df.groupby(pd.Grouper(freq='W'))
    
    for week_end, group in weekly_groups:
        if group.empty:
            continue
            
        t_row = group.iloc[-1]
        t_date = t_row.name
        c_price = t_row['Close']
        
        # Check a specific date we want to verify
        # Let's look for the week ending around Oct 27, 2023.
        # 2023-10-27 was a Friday. The Resample 'W' usually bins to Sunday 2023-10-29.
        # So the group should be the week of Oct 23-27.
        
        if t_date.date() == datetime(2023, 10, 27).date():
            print(f"\n--- VERIFICATION TARGET FOUND: {t_date.date()} ---")
            print(f"C (Close on T): {c_price:.2f}")
            
            # Recalculate H manually
            # Window: T-8 to T-1
            # T = Oct 27
            # T-1 = Oct 26
            # T-8 = Oct 19
            # Range: [Oct 19, Oct 26]
            
            w_start = t_date - timedelta(days=8)
            w_end = t_date - timedelta(days=1)
            print(f"Window: {w_start.date()} to {w_end.date()}")
            
            mask = (df.index >= w_start) & (df.index <= w_end)
            w_df = df.loc[mask]
            
            print("Dates in Window:")
            for d in w_df.index:
                print(f"  {d.date()}: High {w_df.loc[d]['High']:.2f}")
            
            h_actual = w_df['High'].max()
            print(f"Calculated H: {h_actual:.2f}")
            
            ratio = (c_price - h_actual) / h_actual
            print(f"Ratio: {ratio:.2%}")
            break

if __name__ == "__main__":
    verify_logic()
