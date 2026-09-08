"""Personal stock research. Launch with python -m streamlit run app.py."""
from datetime import datetime, timezone
from html import escape
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
import re
import json
import math
from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote

APP_VERSION = "0.3.1"
METRICS = ['Total Revenue','Operating Revenue','Net Interest Income','Interest Income','Interest Expense','Operating Income','Pretax Income','Tax Provision','Net Income','Total Assets','Total Liabilities Net Minority Interest','Stockholders Equity','Total Debt','Cash And Cash Equivalents','Operating Cash Flow','Investing Cash Flow','Financing Cash Flow','Capital Expenditure','Free Cash Flow']

def parse_timeseries(payload, frequency):
    """Accept only individually currency-tagged INR observations."""
    if payload.get('timeseries', {}).get('error'):
        raise ValueError('Financial source returned an error.')
    mapping = {frequency + m.replace(' ', ''): m for m in METRICS}
    values = {}
    for entry in payload.get('timeseries', {}).get('result') or []:
        for key, name in mapping.items():
            for point in entry.get(key, []):
                val = point.get('reportedValue', {}).get('raw')
                period = point.get('asOfDate')
                if point.get('currencyCode') == 'INR' and period and isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(val):
                    values.setdefault(name, {})[period] = val
    df = pd.DataFrame.from_dict(values, orient='index')
    if not df.empty:
        df = df.reindex(sorted(df.columns, reverse=True), axis=1)
    return df

def fetch_timeseries(symbol, frequency):
    now = int(datetime.now(timezone.utc).timestamp())
    query = urlencode({'type': ','.join(frequency+m.replace(' ', '') for m in METRICS), 'period1': now-6*366*86400, 'period2': now})
    url = 'https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/'+quote(symbol, safe='')+'?'+query
    with urlopen(Request(url, headers={'Accept':'application/json'}), timeout=15) as response:
        return parse_timeseries(json.load(response), frequency)

def load_statements(ticker, info, symbol, errors):
    """Metadata failure must not prevent independent statement retrieval."""
    tables = {}
    groups = [('Annual income','income_stmt','annual',METRICS[:9]),
              ('Quarterly income','quarterly_income_stmt','quarterly',METRICS[:9]),
              ('Balance sheet','balance_sheet','annual',METRICS[9:14]),
              ('Cash flow','cashflow','annual',METRICS[14:])]
    fallback = {}
    for title, attr, frequency, allowed in groups:
        notes = []
        try:
            raw = getattr(ticker, attr)
            if not isinstance(raw, pd.DataFrame):
                raw = pd.DataFrame()
            if raw.empty:
                notes.append('The statement request returned no rows.')
        except Exception as exc:
            raw = pd.DataFrame()
            notes.append('Statement request failed: '+type(exc).__name__+'.')
        currency = info.get('financialCurrency')
        if raw.empty or currency != 'INR':
            if frequency not in fallback:
                try:
                    fallback[frequency] = (fetch_timeseries(symbol, frequency), '')
                except Exception as exc:
                    fallback[frequency] = (pd.DataFrame(), 'Currency-tagged financial request failed: '+type(exc).__name__+'.')
            other, problem = fallback[frequency]
            selected = other.loc[[k for k in allowed if k in other.index]].dropna(how='all')
            if not selected.empty:
                raw, currency = selected, 'INR'
                notes.append('Retrieved independently using currency-tagged financial observations.')
            elif problem:
                notes.append(problem)
        if currency != 'INR' and not raw.empty:
            notes.append('Financial currency is '+(str(currency) if currency else 'unconfirmed')+'; values shown in original provider units, without crore conversion.')
        raw.attrs['currency'] = currency
        raw.attrs['notes'] = notes
        tables[title] = raw
        if raw.empty:
            errors.append(title+': '+' '.join(notes or ['No financial observations returned.']))
    return tables

def normalize_symbol(value):
    value=value.strip().upper().removesuffix('.NS')
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9&-]{0,23}', value):
        raise ValueError('Enter an NSE symbol such as JIOFIN, TCS or LT.')
    return value+'.NS'

def indicators(close):
    close=pd.Series(close,dtype=float).dropna()
    if len(close)<2 or (close<=0).any():
        raise ValueError('Need at least two positive prices.')
    rsi=None
    if len(close)>=15:
        changes=close.diff().iloc[1:]
        gain=changes.iloc[:14].clip(lower=0).mean()
        loss=(-changes.iloc[:14].clip(upper=0)).mean()
        for d in changes.iloc[14:]:
            gain=(gain*13+max(d,0))/14
            loss=(loss*13+max(-d,0))/14
        rsi=50 if gain==loss==0 else 100 if loss==0 else 100-100/(1+gain/loss)
    return {'return':(close.iloc[-1]/close.iloc[0]-1)*100,'drawdown':((close/close.cummax()-1)*100).min(),'rsi':rsi,
            **{f'sma{n}':float(close.iloc[-n:].mean()) if len(close)>=n else None for n in [20,50,200]}}

def statement(raw, convert=True):
    if raw is None or raw.empty:
        return pd.DataFrame()
    # Exclude per-share figures, counts and ratios: dividing these by crore is invalid.
    money=['Total Revenue','Operating Revenue','Net Interest Income','Interest Income','Interest Expense','Operating Income','Pretax Income','Tax Provision','Net Income','Total Assets','Total Liabilities Net Minority Interest','Stockholders Equity','Total Debt','Cash And Cash Equivalents','Operating Cash Flow','Investing Cash Flow','Financing Cash Flow','Capital Expenditure','Free Cash Flow']
    selected=[r for r in money if r in raw.index]
    view=raw.loc[selected].apply(pd.to_numeric,errors='coerce')/(1e7 if convert else 1)
    view.columns=[str(c.date()) if hasattr(c,'date') else str(c) for c in view.columns]
    return view.dropna(how='all')


st.set_page_config(page_title="Equity Research", layout="wide")

@st.cache_data(ttl=900, show_spinner=False)
def retrieve(symbol, version=APP_VERSION):
    ticker = yf.Ticker(symbol)
    errors = []
    history = ticker.history(period="2y", auto_adjust=False, actions=True, timeout=20)
    if history.empty:
        raise ValueError("The provider returned no prices. Check the NSE symbol or retry later.")
    info = {}
    try:
        info = ticker.get_info() or {}
    except Exception:
        errors.append("Company metadata unavailable. Financial statements are requested independently.")
    if info.get("currency") not in (None, "INR"):
        raise ValueError("Unexpected price currency; report withheld.")
    tables = load_statements(ticker, info, symbol, errors)
    return history, info, tables, errors, datetime.now(timezone.utc).isoformat()

st.title("Equity Research")
st.caption(f"Indian stocks · Automatic retrieval · Personal research · v{APP_VERSION}")
if st.session_state.get('app_version') != APP_VERSION:
    st.session_state.pop('result', None)
    st.session_state.app_version = APP_VERSION
with st.form("stock_search"):
    a,b = st.columns([3,1])
    ticker_input = a.text_input("NSE symbol", "JIOFIN", help="Examples: HDFCBANK, TCS, LT. No Zerodha connection needed.")
    submitted = b.form_submit_button("Generate report", use_container_width=True)
if submitted:
    st.session_state.pop("result", None)
    try:
        symbol = normalize_symbol(ticker_input)
        with st.spinner("Retrieving prices and available financial statements…"):
            st.session_state.result = (symbol, *retrieve(symbol))
    except Exception as exc:
        st.error(f"Unable to generate report: {exc}")
        st.info("No sample figures were substituted. Yahoo may temporarily limit requests. Wait and retry.")

if "result" not in st.session_state:
    st.info("Enter an NSE symbol above. Data is fetched when you submit; no account connection is required.")
    st.stop()

symbol, history, info, tables, errors, retrieved = st.session_state.result
name = info.get("longName", symbol)
close = history["Close"].dropna()
close = close[close > 0]
if len(close) < 2:
    st.error("Not enough valid closing prices.")
    st.stop()
stats = indicators(close)
st.header(name)
st.caption(f"Last observation: {close.index[-1].date()} · Retrieved {retrieved} · Yahoo Finance, unverified aggregate data")
cols = st.columns(4)
for col, label, value in zip(cols, ["Last close (INR)", "Price return · observed period", "RSI (14)", "Maximum observed drawdown"],
    [f"₹{close.iloc[-1]:,.0f}", f"{stats['return']:.1f}%", "Unavailable" if stats['rsi'] is None else f"{stats['rsi']:.1f}", f"{stats['drawdown']:.1f}%"]):
    col.metric(label, value)
market, financial, evidence = st.tabs(["Market & technicals", "Financial statements", "Sources & limitations"])
with market:
    chart = go.Figure(go.Scatter(x=close.index, y=close, name="Close", line_color="#087d81"))
    for window in [50,200]:
        if len(close) >= window:
            chart.add_scatter(x=close.index,y=close.rolling(window).mean(),name=f"SMA {window}")
    chart.update_layout(height=440, xaxis_title="Date", yaxis_title="INR", legend_orientation="h", margin=dict(l=10,r=10,t=25,b=10))
    st.plotly_chart(chart, use_container_width=True)
    st.caption("Price return excludes cash dividends. Provider close series may be split-adjusted. The displayed history may be shorter than two years.")
    rows = []
    for n in [20,50,200]:
        val = stats[f"sma{n}"]
        rows.append({"Measure":f"SMA {n}","INR":None if val is None else round(val),"Condition":"Insufficient history" if val is None else "Above average" if close.iloc[-1]>val else "Below average"})
    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    st.download_button("Download price history", history.to_csv(), file_name=f"{symbol}-prices.csv", mime="text/csv")

rendered = []
with financial:
    st.caption("Units are shown above each table. INR crore is used only when financial currency is confirmed. No independent filing reconciliation has been performed.")
    for title, raw in tables.items():
        st.subheader(title)
        confirmed = raw.attrs.get('currency') == 'INR'
        unit = 'INR crore' if confirmed else (str(raw.attrs.get('currency') or 'Currency unconfirmed')+' · original provider units')
        view = statement(raw, convert=confirmed)
        notes = raw.attrs.get('notes', [])
        if view.empty:
            st.warning(' '.join(notes) or 'The source returned no supported monetary rows.')
        else:
            st.caption(unit)
            if not confirmed:
                st.warning('Currency could not be verified. These are unconverted source values, not INR crore.')
            if notes:
                with st.expander('Retrieval details'):
                    for note in notes:
                        st.write(note)
            st.dataframe(view.style.format("{:,.0f}", na_rep="Unavailable"),use_container_width=True)
            st.download_button(f"Download {title.lower()}",view.to_csv(),file_name=f"{symbol}-{title.replace(' ','-')}-{'INR-crore' if confirmed else 'original-units'}.csv",mime="text/csv")
            rendered.append(f"<h2>{escape(title)} · {escape(unit)}</h2>"+view.to_html(float_format=lambda n:f"{n:,.0f}",na_rep="Unavailable"))

with evidence:
    for err in errors:
        st.warning(err)
    st.markdown(f"[Yahoo Finance — {symbol}](https://finance.yahoo.com/quote/{symbol}/financials/) · [NSE financial filings](https://www.nseindia.com/companies-listing/corporate-filings-financial-results)")
    st.write("Prices and statements are third-party aggregates. Missing values are not zero. Annual and quarterly periods are separate. Financial companies require sector-specific analysis; generic industrial ratios are not used to assign ratings.")
    st.write("This version does not provide verified ownership, automated filing reconciliation, peer selection, forecast models or independent target prices. No buy/sell recommendation is inferred from RSI or moving averages.")
    st.caption("Source access may be rate-limited. Retrieval is cached for 15 minutes; changing a ticker triggers a separate request.")
    if st.button("Clear retrieved-data cache"):
        retrieve.clear()
        st.session_state.pop("result",None)
        st.rerun()

html = '<!doctype html><html lang="en"><meta charset="utf-8"><title>'+escape(name)+' research</title><style>body{font:16px/1.6 system-ui;max-width:1100px;margin:40px auto;padding:20px;color:#143447}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px;border:1px solid #ccd6df}h2{margin-top:30px}@media print{table{break-inside:avoid}}</style><h1>'+escape(name)+'</h1><p>'+escape(symbol)+' · Last observation '+str(close.index[-1].date())+' · Retrieved '+escape(retrieved)+'</p><p>Last close INR '+f'{close.iloc[-1]:,.0f}'+'; observed price return '+f'{stats["return"]:.1f}%'+'</p><p>Unverified Yahoo Finance data. No independent recommendation or target price.</p>'+''.join(rendered)+'<h2>Data limitations</h2><ul>'+''.join('<li>'+escape(e)+'</li>' for e in errors)+'</ul><p>Price return excludes cash dividends. Statement units are labelled separately for each table; unconfirmed currencies remain in original provider units. Ownership, forecasts and filing reconciliation are not included.</p></html>'
st.download_button("Download HTML report",html,file_name=f"{symbol}-report.html",mime="text/html")
st.caption("Open the downloaded report in your browser and use Print → Save as PDF.")
