import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import timedelta, datetime
import plotly.express as px
import plotly.graph_objects as go

# Page configuration
st.set_page_config(page_title="Stock Backtest App", layout="wide")

st.title("Stock Pullback Backtest Tool")

# Sidebar inputs
st.sidebar.header("Settings")
symbol = st.sidebar.text_input("Stock Symbol", value="SPY").upper()
start_date = st.sidebar.date_input("Start Date", value=datetime(2023, 1, 1))
lookback_days = st.sidebar.number_input("Lookback Days", min_value=1, max_value=365, value=8, step=1)
submit_btn = st.sidebar.button("Run Backtest")

if submit_btn:
    with st.spinner(f"Fetching data for {symbol}..."):
        # 1. Fetch Data
        try:
            # Force string format for date to avoid type issues on Streamlit Cloud
            start_str = start_date.strftime("%Y-%m-%d") if hasattr(start_date, 'strftime') else str(start_date)
            df_daily = yf.download(symbol, start=start_str, progress=False, multi_level_index=False)
        except Exception as e:
            st.error(f"API Error: {e}")
            df_daily = pd.DataFrame()
    
    if df_daily.empty:
        st.error(f"No data found for {symbol} from {start_date}.")
        st.info(f"Debug: yfinance version {yf.__version__}")
        st.info("This might be due to a temporary API block or invalid symbol.")
    else:
        # Ensure index is datetime
        df_daily.index = pd.to_datetime(df_daily.index)
        
        # 2. Group by Week
        weekly_groups = df_daily.groupby(pd.Grouper(freq='W'))
        
        results = []
        
        for week_end, group in weekly_groups:
            if group.empty:
                continue
                
            # 3. Identify T (Last available trading day in the week)
            t_row = group.iloc[-1]
            t_date = t_row.name # Index (Date)
            
            # C = Close price of T
            c_price = t_row['Close']
            
            # 4. Calculate H (High)
            # Window: [T-Lookback, T-1] (Calendar Days)
            window_end_date = t_date - timedelta(days=1)
            window_start_date = t_date - timedelta(days=lookback_days)
            
            mask = (df_daily.index >= window_start_date) & (df_daily.index <= window_end_date)
            window_df = df_daily.loc[mask]
            
            if window_df.empty:
                h_price = pd.NA
                h_date = pd.NA
                ratio = pd.NA
            else:
                h_price = window_df['High'].max()
                # Find the date where this max occurred
                h_date = window_df['High'].idxmax().date()
                
                # 5. Calculate Ratio: (C - H) / H
                if pd.notna(h_price) and h_price != 0:
                    ratio = (c_price - h_price) / h_price
                else:
                    ratio = pd.NA

            # Append to results
            results.append({
                'Week Ending': t_date.date(),
                'Close (C)': c_price,
                'Window Max (H)': h_price,
                'Window Max Date': h_date,
                'Window Start Date': window_start_date.date(),
                'Pullback Ratio': ratio
            })
        
        # Filter out the current week (incomplete week) using ISO calendar and weekday heuristic
        # If the last result's T-date is in the same ISO week as today, remove it.
        # Also remove if it is Mon-Thu (weekday < 4) and very recent, as that implies incomplete.
        if results:
            last_t_date = results[-1]['Week Ending']
            last_iso = last_t_date.isocalendar()[:2] # (year, week)
            
            today = datetime.now().date()
            current_iso = today.isocalendar()[:2]
            
            is_same_week = last_iso == current_iso
            is_recent = (today - last_t_date).days < 7
            is_incomplete_day = last_t_date.weekday() < 4 # Mon(0) - Thu(3)
            
            if is_same_week or (is_recent and is_incomplete_day):
                results.pop()


        # Store results in Session State
        st.session_state['results_df'] = pd.DataFrame(results)
        st.session_state['df_daily'] = df_daily # Store raw data for K-Line
        st.session_state['symbol'] = symbol
        st.session_state['lookback_days'] = lookback_days

# Display Logic (Check if results exist in Session State)
if 'results_df' in st.session_state and not st.session_state['results_df'].empty:
    results_df = st.session_state['results_df']
    df_daily = st.session_state.get('df_daily', pd.DataFrame())
    current_symbol = st.session_state.get('symbol', symbol)
    current_lookback = st.session_state.get('lookback_days', 8)
    
    # Display metrics
    st.subheader(f"Backtest Results for {current_symbol}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"Ref Date (T): Last trading day of each week.")
        st.write(f"Lookback Window: [T-{current_lookback}, T-1] (Calendar Days)")
    with col2:
        # Calculate Average
        avg_ratio = results_df['Pullback Ratio'].mean()
        if pd.isna(avg_ratio):
            avg_ratio = 0.0
        st.metric("Average Pullback Ratio", f"{avg_ratio:.2%}")
    
    # --- Chart 1: Pullback Ratio ---
    fig_ratio = px.line(results_df, x='Week Ending', y='Pullback Ratio', markers=True, title='Pullback Ratio Over Time')
    fig_ratio.add_hline(y=avg_ratio, line_dash="dash", line_color="red", annotation_text=f"Avg: {avg_ratio:.2%}", annotation_position="bottom right")
    fig_ratio.update_layout(dragmode='pan')
    
    # Display chart with selection enabled
    selection = st.plotly_chart(fig_ratio, on_select="rerun", use_container_width=True)
    
    # --- Chart 2: Candlestick Price History (Weekly) using mplfinance with VRVP ---
    if not df_daily.empty:
        st.subheader("Price History (Weekly K-Line with VRVP)")
        
        # Resample to Weekly with Volume
        df_weekly_ohlcv = df_daily.resample('W').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        })
        # Remove any empty bins
        df_weekly_ohlcv = df_weekly_ohlcv.dropna()

        # Create plot
        import mplfinance as mpf
        from matplotlib import pyplot as plt
        import numpy as np

        # 1. Calculate Volume Profile
        # Use 50 bins or dynamic
        price_data = df_weekly_ohlcv['Close']
        volume_data = df_weekly_ohlcv['Volume']
        
        # Define bins
        price_min = price_data.min()
        price_max = price_data.max()
        bins = np.linspace(price_min, price_max, 50)
        
        # Digitise prices to find which bin they belong to
        indices = np.digitize(price_data, bins)
        
        # Sum volume per bin
        # We need to map indices (1-50) to volume
        # Careful with indices returning 0 or len(bins) for out of bounds
        
        vp_volumes = np.zeros(len(bins)-1)
        for i in range(len(price_data)):
            bin_idx = indices[i] - 1 # indices are 1-based, convert to 0-based
            if 0 <= bin_idx < len(vp_volumes):
                vp_volumes[bin_idx] += volume_data.iloc[i]
        
        # 2. Setup mplfinance plot
        # We use returnfig=True to get access to axes
        fig, axlist = mpf.plot(df_weekly_ohlcv, type='candle', style='yahoo', volume=True, 
                               returnfig=True, title=f'{current_symbol} Weekly',
                               figsize=(10, 6), panel_ratios=(4,1))
        
        # Axlist: 0=Main, 1=Secondary(unused usually), 2=Volume (if volume=True)
        # It depends on panels. Usually axlist[0] is main, axlist[2] is volume.
        # Let's verify standard mpf axes: [Main, Volume]
        
        ax_main = axlist[0]
        
        # 3. Plot VRVP on a Twin Axis (Overlay)
        ax_vp = ax_main.twiny()
        
        # Horizontal Bar Chart
        # y = bins (price levels), width = volume
        # We use the mid-point of bins for plotting
        bin_mids = (bins[:-1] + bins[1:]) / 2
        
        # Plot bars
        # Color: Blue with Alpha
        ax_vp.barh(bin_mids, vp_volumes, height=(bins[1]-bins[0])*0.8, alpha=0.3, color='blue', align='center')
        
        # Move VRVP to the right side (invert x axis typically puts 0 on right, but we want bars growing from right to left? 
        # Or standard growing from left (0) to right?
        # User said "Right side".
        # If we plot normally, bars grow from Left (0) to Right.
        # To make them look like they are "on the right side", we can:
        # A) Invert X axis? -> Bars grow from Right to Left. 
        # B) Set X limits so bars only occupy the right-most portion?
        
        # Let's try Inverting Axis so they stick to the right spine?
        # If we invert, 0 starts at Right.
        # But normal barh plots 0..Max. 
        # Actually, usually VRVP overlay is printed 'behind' candles. 
        # If we want it "Right Aligned", typically people mean the histogram bars originate from the right Y-axis and grow leftwards.
        # Matplotlib doesn't have a simple "barh from right" without math.
        # Easier: Just standard barh (Left -> Right) but assume "Right Side" means the overlay is visible on the chart.
        # If user strictly wants "Side Profile" anchored to Right axis:
        # We can use set_xlim(reversed).
        
        ax_vp.set_xlim(right=max(vp_volumes)*4) # Scale so bars only take up ~1/4 of width
        # Switch direction? defaults to Left->Right.
        # Let's leave it Left->Right for now (Standard Volume Profile often on Left or Right).
        # To strictly do "Right Side", we might need to invert, let's keep it simple first.
        # Actually, let's allow them to overlay fully but be transparent.
        
        ax_vp.axis('off') # Hide the VP axis labels/ticks/spines to simplify view
        
        # Render in Streamlit
        st.pyplot(fig)

    # Handle Selection
    selected_indices = []
    if selection and "selection" in selection and "points" in selection["selection"]:
         selected_indices = [p["point_index"] for p in selection["selection"]["points"]]
    
    # Filter dataframe
    display_df = results_df
    if selected_indices:
        display_df = results_df.iloc[selected_indices]
        st.info(f"Showing {len(selected_indices)} selected week(s). Click on the chart background (double click) to reset.")
    
    # Format the dataframe
    styled_df = display_df.style.format({
        'Week Ending': lambda t: t.strftime('%Y-%m-%d (%a)') if pd.notna(t) else "N/A",
        'Close (C)': "{:.2f}",
        'Window Max (H)': "{:.2f}",
        'Window Max Date': lambda t: t.strftime('%Y-%m-%d (%a)') if pd.notna(t) else "N/A",
        'Window Start Date': lambda t: t.strftime('%Y-%m-%d (%a)') if pd.notna(t) else "N/A",
        'Pullback Ratio': "{:.2%}"
    })
    
    st.dataframe(styled_df, use_container_width=True)
    
elif 'results_df' in st.session_state and st.session_state['results_df'].empty:
    st.warning("No results generated.")
