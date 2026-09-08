# Stock Research — Streamlit

## Update 0.3.1 — financial retrieval fix

Replace the three repository files with this ZIP's contents and wait for Streamlit to redeploy. Check that v0.3.1 appears under the app title, then generate a new report. Old session results are invalidated automatically.

Statement retrieval no longer depends on a successful company-metadata request. An additional Yahoo financial-timeseries request accepts only currency-tagged INR observations. If those are unavailable but statement rows exist, they are shown in original units with an explicit unconfirmed-currency warning. This does not bypass provider access restrictions or guarantee availability. Empty sections now show the specific retrieval failure category.

Regression checks cover missing metadata, independent statement requests, currency-tagged fallback, INR conversion, unknown original units and complete provider failure. Live Streamlit Cloud retrieval is still unverified.

## Deploy from GitHub

1. Extract this ZIP. It contains exactly app.py, requirements.txt and readme.md at its root.
2. Upload all three files to a GitHub repository.
3. Open https://share.streamlit.io/ and connect the repository.
4. Choose your branch and set the main file path to app.py. Use Python 3.11 or 3.12 in deployment settings.
5. Deploy. Dependencies install from requirements.txt; no secrets or Zerodha API key are required.

Enter an NSE ticker such as JIOFIN, HDFCBANK, TCS or LT and click Generate report. Available views include price charts, technical measures, annual and quarterly income statements, balance sheets, cash flow, and source limitations. Download prices and statements as CSV or download an HTML report. Open the HTML report in a browser and print to PDF. The HTML export includes tables, not the interactive price chart.

## Local use (optional)

    python -m pip install -r requirements.txt
    python -m streamlit run app.py

## What is implemented

- Automatic market-data and financial-statement retrieval through yfinance.
- Plotly price charts, 20/50/200-session simple moving averages and Wilder RSI (14).
- Observed-period price return and maximum close-to-close drawdown.
- Financial currency validation; INR crore conversion only for monetary statement rows.
- Missing-data messages, 15-minute retrieval cache and downloads.
- Whole-rupee displays; EPS and share counts are not mistakenly converted to crore.

## Limits and verification

Yahoo Finance is an unofficial, aggregated source and may rate-limit requests from Streamlit hosting. Deploying successfully does not establish that every ticker or statement is available. Failures show an error rather than sample data. When currency cannot be confirmed, available statements remain in original provider units with clear labels. Retrieved prices may be delayed and split-adjusted; price returns exclude cash dividends.

This version does not include independent filing verification, reconciled ownership, peer selection, sector-specific forecasts or target-price models. It does not issue buy/sell recommendations. It is a working code package for the initial workflow, not the complete planned research platform.

Checks completed: Python syntax, ticker normalization, RSI, drawdown and monetary-unit conversion. Live Yahoo retrieval and a Streamlit browser session have not been verified in the delivery environment. Dependency bounds are not a fully tested lockfile. Keep the deployment log if installation or retrieval fails.

The application has no custom login. Configure visibility in Streamlit Community Cloud if you want to restrict viewers. Hosting and data-provider terms apply; review Yahoo/yfinance usage terms before redistributing data or using it commercially.

## Official references

- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app
- https://docs.streamlit.io/get-started/installation/command-line
- https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.html
