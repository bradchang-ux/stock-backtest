import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import timedelta, datetime
import plotly.express as px

# Page configuration
st.set_page_config(page_title="Stock Backtest App", layout="wide")

st.title("Stock Pullback Backtest Tool")

# Sidebar inputs
st.sidebar.header("Settings")
symbol = st.sidebar.text_input("Stock Symbol", value="SPY").upper()
start_date = st.sidebar.date_input("Start Date", value=datetime(2023, 1, 1))
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
            # Window: [T-8, T-1] (Calendar Days)
            window_end_date = t_date - timedelta(days=1)
            window_start_date = t_date - timedelta(days=8)
            
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
        st.session_state['symbol'] = symbol

# Display Logic (Check if results exist in Session State)
if 'results_df' in st.session_state and not st.session_state['results_df'].empty:
    results_df = st.session_state['results_df']
    current_symbol = st.session_state.get('symbol', symbol)
    
    # Display metrics
    st.subheader(f"Backtest Results for {current_symbol}")
    st.write(f"Ref Date (T): Last trading day of each week.")
    st.write(f"Lookback Window: [T-8, T-1] (Calendar Days)")
    
    # Plotly Chart
    fig = px.line(results_df, x='Week Ending', y='Pullback Ratio', markers=True, title='Pullback Ratio Over Time')
    
    # Add Average Line
    avg_ratio = results_df['Pullback Ratio'].mean()
    fig.add_hline(y=avg_ratio, line_dash="dash", line_color="red", annotation_text=f"Avg: {avg_ratio:.2%}", annotation_position="bottom right")

    fig.update_layout(dragmode='pan')

    # Display chart with selection enabled
    selection = st.plotly_chart(fig, on_select="rerun", use_container_width=True)
    
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
