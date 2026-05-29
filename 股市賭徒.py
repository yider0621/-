import streamlit as st
import pandas as pd
import yfinance as yf
import time
import json
import os
from datetime import datetime, timedelta

# ==========================================
# 網頁基本設定
# ==========================================
st.set_page_config(page_title="韭菜分析師", layout="wide")
st.title("🥬 你的錢包，我來當沖")
st.markdown("##### 韭菜分析師專屬儀表板：自帶 14:00 自動斷捨離與選股雷達")

# ==========================================
# 系統時間與資料庫設定
# ==========================================
# 取得台灣時間 (UTC+8)
tw_now = datetime.utcnow() + timedelta(hours=8)
DATA_FILE = "portfolio.json"

# 判斷當前所屬的「交易日區間」
# 如果現在超過 14:00，就把下個交易日當作新的 session
if tw_now.time() >= datetime.time(14, 0):
    current_session = (tw_now + timedelta(days=1)).date().isoformat()
else:
    current_session = tw_now.date().isoformat()

# 讀取本地資料庫 (JSON)
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 檢查是否需要執行 14:00 每日大洗牌
                if data.get("session_date") != current_session:
                    return {"session_date": current_session, "portfolio": {}}
                return data
        except:
            return {"session_date": current_session, "portfolio": {}}
    return {"session_date": current_session, "portfolio": {}}

# 寫入本地資料庫 (JSON)
def save_data(portfolio_data):
    data_to_save = {
        "session_date": current_session,
        "portfolio": portfolio_data
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=4)

# 初始化狀態
if 'db' not in st.session_state:
    st.session_state.db = load_data()

# ==========================================
# 當沖選股雷達 (自動尋找高振幅標的)
# ==========================================
@st.cache_data(ttl=3600) # 雷達一小時更新一次即可
def run_radar():
    # 精選高波動候選池 (涵蓋半導體、記憶體、面板、重電、航運等熱門當沖族群)
    candidates = {
        "2330": "台積電", "2317": "鴻海", "3481": "群創", 
        "6770": "力積電", "2408": "南亞科", "3260": "威剛", "2344": "華邦電",
        "2603": "長榮", "1519": "華城", "3231": "緯創", "2382": "廣達"
    }
    
    results = []
    for ticker, name in candidates.items():
        try:
            stock = yf.Ticker(f"{ticker}.TW")
            hist = stock.history(period="1d")
            if not hist.empty:
                high = hist['High'].iloc[-1]
                low = hist['Low'].iloc[-1]
                open_p = hist['Open'].iloc[-1]
                
                # 計算日內振幅: (高-低) / 開盤價
                if open_p > 0:
                    amplitude = ((high - low) / open_p) * 100
                    results.append({
                        "代號": ticker, 
                        "名稱": name, 
                        "振幅(%)": round(amplitude, 2),
                        "今日高低價差": round(high - low, 2)
                    })
        except:
            pass
            
    # 依照振幅排序，取前三名
    results = sorted(results, key=lambda x: x["振幅(%)"], reverse=True)[:3]
    return results

# ==========================================
# 雷達顯示區塊 (側邊欄或展開面板)
# ==========================================
with st.expander("📡 當沖選股雷達 (尋找今日最佳衝浪標的)", expanded=False):
    st.markdown("雷達掃描邏輯：從熱門高週轉率族群中，自動挑選**日內振幅最大**的前三名股票。振幅夠大，才有價差空間！")
    radar_picks = run_radar()
    
    if radar_picks:
        cols = st.columns(3)
        for i, pick in enumerate(radar_picks):
            with cols[i]:
                st.metric(
                    label=f"🏆 Top {i+1}: {pick['名稱']} ({pick['代號']})", 
                    value=f"振幅 {pick['振幅(%)']}%", 
                    delta=f"高低價差 {pick['今日高低價差']} 元",
                    delta_color="off"
                )
    else:
        st.write("雷達收集中或假日休市。")

st.markdown("---")

# ==========================================
# 核心功能：抓取即時報價 (快取 10 秒)
# ==========================================
@st.cache_data(ttl=10) 
def get_stock_data(ticker):
    try:
        ticker_str = str(ticker).strip()
        stock = yf.Ticker(f"{ticker_str}.TW")
        hist = stock.history(period="1d", interval="1m")
        if hist.empty:
            return 0.0, 0.0
        
        current_price = round(hist['Close'].iloc[-1], 2)
        hist['Typical_Price'] = (hist['High'] + hist['Low'] + hist['Close']) / 3
        hist['Cum_Vol'] = hist['Volume'].cumsum()
        hist['Cum_Vol_Price'] = (hist['Typical_Price'] * hist['Volume']).cumsum()
        
        vwap = current_price
        if hist['Cum_Vol'].iloc[-1] > 0:
            vwap = round(hist['Cum_Vol_Price'].iloc[-1] / hist['Cum_Vol'].iloc[-1], 2)
            
        return current_price, vwap
    except:
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
            st.session_state.db["portfolio"][new_ticker] = {"名稱": new_name, "進場價": 0.0}
            save_data(st.session_state.db["portfolio"]) # 立即存檔
            st.success(f"✅ {new_name} ({new_ticker}) 已加入戰場並存檔！")
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
for ticker, info in st.session_state.db["portfolio"].items():
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
        row["行動指令"] = "⚠️ 報價異常"
        
    display_data.append(row)

df = pd.DataFrame(display_data)

st.markdown(f"💡 **系統狀態：** 目前資料區間為 `{current_session}`。每日 14:00 將自動清空所有資料，迎接新戰場。")

edited_df = st.data_editor(
    df,
    disabled=["動態均價線", "目前報價", "報酬率(%)", "行動指令"], 
    hide_index=True,
    width="stretch"
)

# 核對編輯並存檔
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

# 如果有任何變動（修改價格、代號、或刪除），就寫入 JSON 檔案
if new_portfolio != st.session_state.db["portfolio"]:
    st.session_state.db["portfolio"] = new_portfolio 
    save_data(new_portfolio)
    st.rerun() 

if auto_refresh:
    time.sleep(10)
    st.rerun()
