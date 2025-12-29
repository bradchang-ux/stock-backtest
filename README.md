# Stock Backtest Web App

A Streamlit web application to backtest a specific weekly stock pullback strategy.

## Features
- **Data Source**: Fetches daily OHLC data using `yfinance`.
- **Interactive Charts**: Plotly-powered charts with click-to-filter functionality.
- **Weekly Strategy**:
    1. Identify Reference Day (**T**) for each week.
    2. Determine Lookback Window: `[T-8, T-1]` (Calendar Days).
    3. Calculate Window Max (**H**).
    4. Compute Pullback Ratio: `(C - H) / H`.

## Local Installation

1. Clone this repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   streamlit run app.py
   ```

## Deployment

### Streamlit Community Cloud
1. Push this code to GitHub.
2. Connect your repository on [share.streamlit.io](https://share.streamlit.io/).
3. Deploy!

### GitHub Actions
This repository includes a CI workflow that automatically tests the build on every push to `main`.
