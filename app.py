import streamlit as st
import pandas as pd
import yfinance as yf
import time

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Uncle's Radar", page_icon="💰", layout="wide")

# --- TITLE & INTRO ---
st.title("Uncle's Insider Radar")
st.markdown("### The 'High Conviction' Stock Screener")
st.markdown("""
This tool automates the **'Promoter Buying Strategy'**. It scans raw NSE data to find companies 
where the Owners (Promoters) are buying their own shares via Open Market, then filters them for financial quality.
""")

# --- INSTRUCTIONS (New Feature) ---
with st.expander("📝 How to use this tool (Click to Expand)"):
    st.write("""
    1. **Download Data:** Go to the [NSE Insider Trading Page](https://www.nseindia.com/companies-listing/corporate-filings-insider-trading).
    2. **Filter:** On the left side of the NSE page, select **"3M"** (Last 3 Months).
    3. **Download:** Click the small **"Download CSV"** icon (top-right of the table).
    4. **Upload:** Drag and drop that CSV file into the box below.
    """)

# --- SIDEBAR: THE CONTROL PANEL ---
st.sidebar.header("⚙️ Filter Settings")
st.sidebar.write("Tweak these to match your risk appetite.")

# Sliders for the Uncle's Logic
pe_limit = st.sidebar.slider("Max P/E Ratio (Expensive Check)", 10, 100, 60, help="Reject companies with P/E higher than this.")
roe_limit = st.sidebar.slider("Min ROE % (Efficiency Check)", 0, 30, 10, help="Reject companies with ROE lower than this.")
debt_limit = st.sidebar.slider("Max Debt/Equity", 0.0, 5.0, 2.0, help="Reject companies with Debt/Equity higher than this.")

# --- HELPER FUNCTION ---
def get_col_name(df, keywords):
    for col in df.columns:
        if all(k.lower() in col.lower() for k in keywords):
            return col
    return None

# --- STEP 1: FILE UPLOAD ---
st.divider()
uploaded_file = st.file_uploader("📂 Step 1: Upload NSE Insider Trading CSV", type=['csv'])

if uploaded_file is not None:
    # 1. LOAD DATA
    try:
        df = pd.read_csv(uploaded_file)
        df.columns = df.columns.str.replace('\n', '', regex=False).str.strip()
        st.success("✅ File Loaded Successfully! Processing data...")
    except Exception as e:
        st.error(f"Error loading file: {e}")
        st.stop()

    # 2. COLUMN MAPPING
    person_col = get_col_name(df, ['Category', 'Person'])
    type_col = get_col_name(df, ['Transaction', 'Type']) 
    if not type_col: type_col = get_col_name(df, ['Acquis', 'Dispos']) 
    val_col = get_col_name(df, ['Value', 'Security'])
    mode_col = get_col_name(df, ['Mode', 'Acquis'])

    if not all([person_col, type_col, val_col, mode_col]):
        st.error("❌ Could not detect required columns. Please check the file format.")
        st.stop()

    # 3. FILTERING
    promoter_df = df[df[person_col].str.contains('Promoter', case=False, na=False)]
    buy_df = promoter_df[
        promoter_df[type_col].str.contains('Buy', case=False, na=False) | 
        promoter_df[type_col].str.contains('Acqui', case=False, na=False)
    ]
    final_df = buy_df[buy_df[mode_col].str.startswith('Market P', na=False)]

    # 4. GROUPING
    final_df[val_col] = pd.to_numeric(final_df[val_col], errors='coerce')
    grouped_df = final_df.groupby('SYMBOL')[val_col].sum().reset_index()
    grouped_df['Value (Cr)'] = round(grouped_df[val_col] / 10000000, 2)
    grouped_df = grouped_df.sort_values(by='Value (Cr)', ascending=False)

    # SHOW RAW RESULTS
    st.subheader(f"📢 Found {len(grouped_df)} Companies with Promoter Buying")
    st.dataframe(grouped_df.head(10), use_container_width=True)

    # --- STEP 2: FUNDAMENTAL CHECK ---
    st.divider()
    st.subheader("🔍 Step 2: Quality Check (Yahoo Finance)")
    st.markdown("We will now cross-reference these companies with live market data to remove 'Traps'.")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        num_stocks = st.slider("How many top stocks to scan?", 5, 50, 10)
    with col2:
        st.write("") # Spacer
        st.write("") # Spacer
        run_scan = st.button("Run Deep Scan 🚀", type="primary")
    
    if run_scan:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        top_picks = grouped_df.head(num_stocks).copy()
        
        pe_ratios = []
        roes = []
        debt_ratios = []
        current_prices = []
        
        # SCANNING LOOP
        for i, symbol in enumerate(top_picks['SYMBOL']):
            status_text.text(f"Scanning {symbol}...")
            try:
                ticker = yf.Ticker(f"{symbol}.NS")
                info = ticker.info
                
                pe = info.get('trailingPE', 0)
                roe = info.get('returnOnEquity', 0)
                debt = info.get('debtToEquity', 0)
                price = info.get('currentPrice', 0)
                
                if pe is None: pe = 0
                if roe is None: roe = 0
                if debt is None: debt = 0
                
                pe_ratios.append(pe)
                roes.append(roe)
                debt_ratios.append(debt)
                current_prices.append(price)
                
            except Exception:
                pe_ratios.append(0)
                roes.append(0)
                debt_ratios.append(0)
                current_prices.append(0)
            
            progress_bar.progress((i + 1) / num_stocks)
        
        status_text.text("Scan Complete!")
        
        # ADD DATA TO DF
        top_picks['Price'] = current_prices
        top_picks['P/E'] = pe_ratios
        top_picks['ROE %'] = [round(r * 100, 2) for r in roes]
        top_picks['Debt/Eq'] = debt_ratios
        
        # APPLY SLIDER FILTERS
        gold_stocks = top_picks[
            (top_picks['P/E'] > 0) & 
            (top_picks['P/E'] < pe_limit) & 
            (top_picks['ROE %'] > roe_limit) &
            (top_picks['Debt/Eq'] < debt_limit * 100)
        ]
        
        # SHOW FINAL LIST
        st.success(f"🏆 Found {len(gold_stocks)} Golden Stocks!")
        st.dataframe(gold_stocks.style.highlight_max(axis=0, color='lightgreen'), use_container_width=True)
        
        # SHOW REJECTS
        with st.expander("See Rejected Stocks (Traps)"):
            rejected = top_picks[~top_picks.index.isin(gold_stocks.index)]
            st.write(rejected)

# --- DISCLAIMER---
st.divider()
st.warning("""
**⚠️ DISCLAIMER:** This tool is for **Educational and Informational Purposes Only**. 
The creator of this tool is **not** a SEBI registered Research Analyst or Investment Advisor. 
The stocks listed above are **not** buy/sell recommendations. Market data (via Yahoo Finance) may be delayed or inaccurate. 
Please consult a certified financial advisor before making any investment decisions.
""")