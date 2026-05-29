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
st.set_page_config(page_title="韭菜分析師 | AI 量化版", layout="wide")
st.title("🥬 你的錢包，我來當沖 (AI 預測版)")
st.markdown("##### 導入動能演算法：自動判斷多空趨勢與進場勝率")

# ==========================================
# 系統時間與資料庫設定
# ==========================================
tw_now = datetime.utcnow() + timedelta(hours=8)
DATA_FILE = "portfolio.json"

if tw_now.hour >= 14:
    current_session = (tw_now + timedelta(days=1)).date().isoformat()
else:
    current_session = tw_now.date().isoformat()

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("session_date") != current_session:
                    return {"session_date": current_session, "portfolio": {}}
                return data
        except:
            return {"session_date": current_session, "portfolio": {}}
    return {"session_date": current_session, "portfolio": {}}

def save_data(portfolio_data):
    data_to_save = {"session_date": current_session, "portfolio": portfolio_data}
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=4)

if 'db' not in st.session_state:
    st.session_state.db = load_data()

# ==========================================
# 核心功能：抓取即時報價與動能計算 (快取 10 秒)
# ==========================================
@st.cache_data(ttl=10) 
def get_stock_data(ticker):
    try:
        ticker_str = str(ticker).strip()
        stock = yf.Ticker(f"{ticker_str}.TW")
        hist = stock.history(period="1d", interval="1m")
        if hist.empty:
            return None
        
        current_price = round(hist['Close'].iloc[-1], 2)
        total_volume = int(hist['Volume'].sum())
        
        # 計算動態均價線 (VWAP)
        hist['Typical_Price'] = (hist['High'] + hist['Low'] + hist['Close']) / 3
        hist['Cum_Vol'] = hist['Volume'].cumsum()
        hist['Cum_Vol_Price'] = (hist['Typical_Price'] * hist['Volume']).cumsum()
        vwap = current_price
        if hist['Cum_Vol'].iloc[-1] > 0:
            vwap = round(hist['Cum_Vol_Price'].iloc[-1] / hist['Cum_Vol'].iloc[-1], 2)
            
        return {"price": current_price, "vwap": vwap, "volume": total_volume, "high": hist['High'].max(), "low": hist['Low'].min()}
    except:
        return None

# ==========================================
# 演算法：AI 多空分析與預測模型
# ==========================================
def analyze_trend(current_price, vwap, high, low):
    # 簡單動能模型：依照均價線與當日高低點相對位置評分
    if current_price == 0 or vwap == 0:
        return "無數據", 50, "觀望"
        
    trend_score = 50 # 基準分
    
    # 均價線乖離判定
    if current_price > vwap:
        trend_score += 15
        strategy = f"📈 偏多 (建議回測 {vwap} 有守做多)"
    elif current_price < vwap:
        trend_score -= 15
        strategy = f"📉 偏空 (建議反彈 {vwap} 不過做空)"
    else:
        strategy = "⚖️ 多空交戰 (靠近均價線)"
        
    # 位階判定 (強勢創高或弱勢破底)
    if current_price >= high * 0.99: # 接近今日最高點
        trend_score += 15
        direction = "🚀 向上突破機率高"
    elif current_price <= low * 1.01: # 接近今日最低點
        trend_score -= 15
        direction = "🪂 向下破底機率高"
    else:
        direction = "波動盤整中"

    # 確保分數在合理區間
    trend_score = max(10, min(90, trend_score))
    
    return direction, trend_score, strategy

# ==========================================
# 當沖選股雷達 (含 AI 戰術分析)
# ==========================================
@st.cache_data(ttl=3600) 
def run_radar():
    candidates = {"2330": "台積電", "2317": "鴻海", "3481": "群創", "6770": "力積電", "2603": "長榮", "1519": "華城", "3231": "緯創"}
    results = []
    for ticker, name in candidates.items():
        data = get_stock_data(ticker)
        if data and data['price'] > 0:
            open_p = data['price'] # 簡化計算
            amplitude = ((data['high'] - data['low']) / data['low']) * 100
            direction, score, strategy = analyze_trend(data['price'], data['vwap'], data['high'], data['low'])
            
            results.append({
                "代號": ticker, "名稱": name, "振幅": amplitude, 
                "價差": round(data['high'] - data['low'], 2),
                "現價": data['price'], "策略": strategy
            })
    return sorted(results, key=lambda x: x["振幅"], reverse=True)[:3]

# ==========================================
# ➡️ 雙面板區塊：圖示說明 ＆ 選股雷達
# ==========================================
with st.expander("📖 點我查看：操作手冊與 AI 預測原理", expanded=False):
    st.markdown("""
    * **AI 趨勢分析**：根據即時股價與「動態均價線 (VWAP)」的乖離率，加上當日高低點位階推算。
    * **勝率(%)**：高於 50% 偏多，低於 50% 偏空。極端值 (>75% 或 <25%) 代表方向明確但需防範追高殺低。
    * *免責聲明：預測模型為量價演算法推估，缺乏五檔委買賣籌碼數據，僅供紀律參考，盈虧自負！*
    """)

with st.expander("📡 AI 雷達戰術板 (今日最佳衝浪標的)", expanded=False):
    radar_picks = run_radar()
    if radar_picks:
        for i, pick in enumerate(radar_picks):
            st.info(f"**🏆 Top {i+1}: {pick['名稱']} ({pick['代號']})** ｜ 現價: {pick['現價']} ｜ 振幅: {pick['振幅']:.2f}% (價差 {pick['價差']} 元) \n\n 🤖 **AI 戰術建議：** {pick['策略']}")
    else:
        st.write("雷達收集中或假日休市。")

st.markdown("---")

# ==========================================
# 區塊一：新增自選股 (➡️ 升級：加入進場價輸入框)
# ==========================================
st.subheader("➕ 佈署新戰場")
col1, col2, col3, col4 = st.columns([2, 2, 2, 4])
with col1:
    new_ticker = st.text_input("股票代號 (如: 2330)", max_chars=6)
with col2:
    new_name = st.text_input("股票名稱 (如: 台積電)")
with col3:
    new_entry = st.number_input("進場價 (未進場填0)", min_value=0.0, step=0.1, value=0.0)
with col4:
    st.write("") 
    st.write("")
    if st.button("加入 AI 監控面板"):
        if new_ticker and new_name:
            st.session_state.db["portfolio"][new_ticker] = {"名稱": new_name, "進場價": float(new_entry)}
            save_data(st.session_state.db["portfolio"])
            st.success(f"✅ {new_name} 已加入！預設進場價：{new_entry}")
            st.rerun()

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
    data = get_stock_data(ticker)
    
    if data:
        direction, score, strategy = analyze_trend(data['price'], data['vwap'], data['high'], data['low'])
        
        row = {
            "🗑️ 刪除": False,
            "股票代號": ticker,
            "股票名稱": info["名稱"],
            "目前報價": data['price'],
            "動態均價": data['vwap'],
            "成交量(股)": data['volume'],
            "🤖 AI 趨勢分析": direction,
            "多方勝率(%)": score,
            "你的進場價": info["進場價"],
            "報酬率(%)": 0.0,
            "行動指令": ""
        }
        
        # 停損停利紀律邏輯
        if info["進場價"] > 0:
            profit_loss_pct = ((data['price'] - info["進場價"]) / info["進場價"]) * 100
            row["報酬率(%)"] = round(profit_loss_pct, 2)
            
            if profit_loss_pct <= -1.5 or data['price'] < data['vwap']:
                row["行動指令"] = "🔴 斷尾求生"
            elif profit_loss_pct >= 2.0:
                row["行動指令"] = "🔵 入袋為安"
            else:
                row["行動指令"] = "🟡 繼續煎熬"
        else:
            if data['price'] > data['vwap']:
                row["行動指令"] = "🟢 準備上車"
            else:
                row["行動指令"] = "⚪ 旁邊玩沙"
    else:
        row = {"🗑️ 刪除": False, "股票代號": ticker, "股票名稱": info["名稱"], "行動指令": "⚠️ 報價異常"}
        
    display_data.append(row)

df = pd.DataFrame(display_data)

edited_df = st.data_editor(
    df,
    disabled=["目前報價", "動態均價", "成交量(股)", "🤖 AI 趨勢分析", "多方勝率(%)", "報酬率(%)", "行動指令"], 
    hide_index=True,
    width="stretch"
)

# 核對編輯並存檔
need_rerun = False
new_portfolio = {}

for index, row in edited_df.iterrows():
    if row.get("🗑️ 刪除", False) == True:
        continue
    ticker = str(row["股票代號"]).strip()
    if not ticker: continue
    new_portfolio[ticker] = {"名稱": str(row["股票名稱"]).strip(), "進場價": float(row.get("你的進場價", 0.0))}

if new_portfolio != st.session_state.db["portfolio"]:
    st.session_state.db["portfolio"] = new_portfolio 
    save_data(new_portfolio)
    st.rerun() 

if auto_refresh:
    time.sleep(10)
    st.rerun()
