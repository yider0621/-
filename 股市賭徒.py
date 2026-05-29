import streamlit as st
import pandas as pd
import yfinance as yf
import time

# ==========================================
# 網頁基本設定 (名稱與主題更新)
# ==========================================
st.set_page_config(page_title="韭菜分析師", layout="wide")
st.title("🥬 你的錢包，我來當沖")
st.markdown("##### 韭菜分析師專屬儀表板：不再被當提款機的最後防線")

# ==========================================
# 狀態管理 (Session State)
# ==========================================
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {
        "6770": {"名稱": "力積電", "進場價": 84.0},
        "3481": {"名稱": "群創", "進場價": 0.0}
    }


# ==========================================
# 核心功能：抓取即時報價 (快取 10 秒)
# ==========================================
@st.cache_data(ttl=10)
def get_stock_data(ticker):
    try:
        ticker_str = str(ticker).strip()
        if not ticker_str:
            return 0.0, 0.0

        stock = yf.Ticker(f"{ticker_str}.TW")
        hist = stock.history(period="1d", interval="1m")

        if hist.empty:
            return 0.0, 0.0

        current_price = round(hist['Close'].iloc[-1], 2)

        hist['Typical_Price'] = (hist['High'] + hist['Low'] + hist['Close']) / 3
        hist['Cum_Vol'] = hist['Volume'].cumsum()
        hist['Cum_Vol_Price'] = (hist['Typical_Price'] * hist['Volume']).cumsum()

        if hist['Cum_Vol'].iloc[-1] > 0:
            vwap = round(hist['Cum_Vol_Price'].iloc[-1] / hist['Cum_Vol'].iloc[-1], 2)
        else:
            vwap = current_price

        return current_price, vwap
    except Exception as e:
        return 0.0, 0.0


# ==========================================
# 區塊一：新增自選股介面
# ==========================================
st.subheader("➕ 新增待宰羔羊 (觀察標的)")
col1, col2, col3 = st.columns([2, 2, 8])
with col1:
    new_ticker = st.text_input("輸入股票代號 (如: 2330)", max_chars=6)
with col2:
    new_name = st.text_input("輸入股票名稱 (如: 台積電)")
with col3:
    st.write("")
    st.write("")
    if st.button("加入監控面板"):
        if new_ticker and new_name:
            st.session_state.portfolio[new_ticker] = {"名稱": new_name, "進場價": 0.0}
            st.success(f"✅ {new_name} ({new_ticker}) 已加入戰場！")
            st.rerun()
        else:
            st.warning("請填寫代號與名稱！")

st.markdown("---")

# ==========================================
# 區塊二：動態儀表板與邏輯運算
# ==========================================
col_title, col_btn1, col_btn2 = st.columns([6, 2, 2])
with col_title:
    st.subheader("🎯 當沖戰情室")
with col_btn1:
    if st.button("🔄 強制手動更新"):
        st.cache_data.clear()
        st.rerun()
with col_btn2:
    auto_refresh = st.toggle("⚡ 開啟自動更新 (10秒)", value=False)

display_data = []
for ticker, info in st.session_state.portfolio.items():
    current_price, vwap = get_stock_data(ticker)

    row = {
        "🗑️ 刪除": False,
        "股票代號": ticker,
        "股票名稱": info["名稱"],
        "動態均價線": vwap,
        "目前報價": current_price,
        "你的進場價": info["進場價"],
        "報酬率(%)": 0.0,
        "行動指令": ""
    }

    if info["進場價"] > 0 and current_price > 0:
        profit_loss_pct = ((current_price - info["進場價"]) / info["進場價"]) * 100
        row["報酬率(%)"] = round(profit_loss_pct, 2)

        if profit_loss_pct <= -1.5 or current_price < vwap:
            row["行動指令"] = "🔴 斷尾求生 (強制停損)"
        elif profit_loss_pct >= 2.0:
            row["行動指令"] = "🔵 入袋為安 (達標停利)"
        else:
            row["行動指令"] = "🟡 繼續煎熬 (持有觀察)"

    elif current_price > 0:
        if current_price > vwap:
            row["行動指令"] = "🟢 準備上車 (站上均價)"
        else:
            row["行動指令"] = "⚪ 旁邊玩沙 (均價之下)"
    else:
        row["行動指令"] = "⚠️ 報價異常 (請檢查代號)"

    display_data.append(row)

df = pd.DataFrame(display_data)

st.markdown(
    "💡 **操作手冊：直接在表格內修改「股票代號」或「進場價」，系統會自動抓取新報價。打勾可移除該列。編輯時請先關閉右上角自動更新。**")

edited_df = st.data_editor(
    df,
    disabled=["動態均價線", "目前報價", "報酬率(%)", "行動指令"],
    hide_index=True,
    width="stretch"
)

need_rerun = False
new_portfolio = {}

for index, row in edited_df.iterrows():
    if row["🗑️ 刪除"] == True:
        continue

    ticker = str(row["股票代號"]).strip()
    if not ticker:
        continue

    new_name = str(row["股票名稱"]).strip()
    new_entry_price = float(row["你的進場價"])
    new_portfolio[ticker] = {"名稱": new_name, "進場價": new_entry_price}

if new_portfolio != st.session_state.portfolio:
    st.session_state.portfolio = new_portfolio
    st.rerun()

st.markdown("---")
st.warning("⚠️ **韭菜生存守則**：設定停損為 -1.5% 或 股價跌破動態均價線。當亮起紅燈，請立即切換至券商 APP 砍單，絕不留戀。")

if auto_refresh:
    time.sleep(10)
    st.rerun()