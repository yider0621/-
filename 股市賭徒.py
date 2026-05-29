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
st.set_page_config(page_title="韭菜分析師 | 成本精算版", layout="wide", initial_sidebar_state="expanded")

BROKERS = {
    "永豐金證券 (大戶投 - 2折)": 0.2,
    "國泰綜合證券 (2.8折)": 0.28,
    "口袋證券 (2.8折)": 0.28,
    "富邦證券 (6折)": 0.6,
    "元大證券 (6折)": 0.6,
    "凱基證券 (6折)": 0.6,
    "玉山證券 (6折)": 0.6,
    "群益金鼎證券 (6折)": 0.6,
    "自訂 / 無折讓 (10折)": 1.0
}

# ==========================================
# 1. 帳號登入系統 (➡️ 新增快速登入捷徑)
# ==========================================
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

if st.session_state.current_user is None:
    st.title("🔐 韭菜分析師 - 登入系統")
    st.markdown("##### 建立或登入您的個人專屬戰情室")
    
    # 掃描本地端已經存在的 user_XXX.json 檔案
    existing_users = []
    for filename in os.listdir("."):
        if filename.startswith("user_") and filename.endswith(".json"):
            # 把檔名的 "user_" 和 ".json" 去除，只保留名字
            user_name = filename.replace("user_", "").replace(".json", "")
            existing_users.append(user_name)
    
    # 如果有歷史紀錄，顯示快速登入按鈕
    if existing_users:
        st.write("👤 **快速登入 (曾建立的帳號)：**")
        # 將按鈕排成一列 (最多排4個，超過自動換行)
        cols = st.columns(min(len(existing_users), 4))
        for i, user in enumerate(existing_users):
            if cols[i % 4].button(f"🔑 {user}", use_container_width=True):
                st.session_state.current_user = user
                st.rerun()
        
        st.markdown("---")
        st.write("✨ **或建立新帳號：**")

    # 傳統文字輸入登入框
    with st.form("login_form"):
        username = st.text_input("請輸入您的名字：", max_chars=20, placeholder="例如：陳大明")
        submit = st.form_submit_button("進入戰情室")
        if submit and username.strip():
            st.session_state.current_user = username.strip()
            st.rerun()
        elif submit:
            st.warning("⚠️ 名字不能為空！")
    st.stop()

# ==========================================
# 2. 獨立資料庫設定
# ==========================================
USER = st.session_state.current_user
DATA_FILE = f"user_{USER}.json"
tw_now = datetime.utcnow() + timedelta(hours=8)

if tw_now.hour >= 14:
    current_session = (tw_now + timedelta(days=1)).date().isoformat()
else:
    current_session = tw_now.date().isoformat()

def load_data():
    default_data = {
        "session_date": current_session, 
        "portfolio": {}, 
        "pnl_history": [],
        "broker": "永豐金證券 (大戶投 - 2折)" 
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("session_date") != current_session:
                    data["session_date"] = current_session
                    data["portfolio"] = {}
                if "broker" not in data:
                    data["broker"] = default_data["broker"]
                return data
        except:
            return default_data
    return default_data

def save_data(portfolio_data, pnl_data, broker):
    trimmed_pnl = pnl_data[-10:] if len(pnl_data) > 10 else pnl_data
    data_to_save = {
        "session_date": current_session,
        "portfolio": portfolio_data,
        "pnl_history": trimmed_pnl,
        "broker": broker
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=4)

if 'db' not in st.session_state:
    st.session_state.db = load_data()

# ==========================================
# 3. 側邊欄：個人檔案與損益紀錄
# ==========================================
with st.sidebar:
    st.header(f"👤 {USER} 的專屬檔案")
    
    current_broker = st.session_state.db.get("broker", "永豐金證券 (大戶投 - 2折)")
    broker_list = list(BROKERS.keys())
    broker_index = broker_list.index(current_broker) if current_broker in broker_list else 0
    
    selected_broker = st.selectbox("🏦 常用券商與折讓", broker_list, index=broker_index)
    if selected_broker != current_broker:
        st.session_state.db["broker"] = selected_broker
        save_data(st.session_state.db["portfolio"], st.session_state.db["pnl_history"], selected_broker)
        st.rerun()
        
    discount = BROKERS[selected_broker]
    st.caption(f"目前計算基準：手續費 {discount*10} 折，當沖證交稅 0.15%")
    
    if st.button("🚪 登出", use_container_width=True):
        st.session_state.current_user = None
        st.session_state.pop('db', None)
        st.rerun()
        
    st.markdown("---")
    st.subheader("💰 每日真實損益日誌 (近10天)")
    
    pnl_data = st.session_state.db.get("pnl_history", [])
    if not pnl_data:
        pnl_data = [{"日期": tw_now.strftime("%Y-%m-%d"), "淨損益(扣手續費)": 0, "檢討備註": "開始紀錄！"}]
    
    pnl_df = pd.DataFrame(pnl_data)
    edited_pnl = st.data_editor(pnl_df, num_rows="dynamic", use_container_width=True, hide_index=True)
    
    new_pnl_list = edited_pnl.to_dict(orient="records")
    if new_pnl_list != st.session_state.db.get("pnl_history", []):
        st.session_state.db["pnl_history"] = new_pnl_list
        save_data(st.session_state.db["portfolio"], new_pnl_list, st.session_state.db["broker"])

# ==========================================
# 4. 核心功能與 AI 演算法
# ==========================================
st.title("🥬 你的錢包，我來當沖 (成本精算版)")

@st.cache_data(ttl=10) 
def get_stock_data(ticker):
    try:
        ticker_str = str(ticker).strip()
        stock = yf.Ticker(f"{ticker_str}.TW")
        hist = stock.history(period="1d", interval="1m")
        if hist.empty: return None
        
        current_price = round(hist['Close'].iloc[-1], 2)
        total_volume = int(hist['Volume'].sum())
        
        hist['Typical_Price'] = (hist['High'] + hist['Low'] + hist['Close']) / 3
        hist['Cum_Vol'] = hist['Volume'].cumsum()
        hist['Cum_Vol_Price'] = (hist['Typical_Price'] * hist['Volume']).cumsum()
        vwap = current_price
        if hist['Cum_Vol'].iloc[-1] > 0:
            vwap = round(hist['Cum_Vol_Price'].iloc[-1] / hist['Cum_Vol'].iloc[-1], 2)
            
        return {"price": current_price, "vwap": vwap, "volume": total_volume, "high": hist['High'].max(), "low": hist['Low'].min()}
    except:
        return None

def analyze_trend(current_price, vwap, high, low):
    if current_price == 0 or vwap == 0: return "無數據", 50, "觀望"
    trend_score = 50 
    if current_price > vwap:
        trend_score += 15
        strategy = f"📈 偏多 (建議回測 {vwap} 有守做多)"
    elif current_price < vwap:
        trend_score -= 15
        strategy = f"📉 偏空 (建議反彈 {vwap} 不過做空)"
    else:
        strategy = "⚖️ 多空交戰 (靠近均價線)"
    return direction if (direction := "🚀 突破機率高" if current_price >= high * 0.99 else "🪂 破底機率高" if current_price <= low * 1.01 else "盤整中") else "盤整中", max(10, min(90, trend_score)), strategy

@st.cache_data(ttl=3600) 
def run_radar():
    candidates = {"2330": "台積電", "2317": "鴻海", "3481": "群創", "6770": "力積電", "2603": "長榮", "1519": "華城", "3231": "緯創"}
    results = []
    for ticker, name in candidates.items():
        data = get_stock_data(ticker)
        if data and data['price'] > 0:
            results.append({"代號": ticker, "名稱": name, "振幅": ((data['high'] - data['low']) / data['low']) * 100, "價差": round(data['high'] - data['low'], 2), "現價": data['price'], "策略": analyze_trend(data['price'], data['vwap'], data['high'], data['low'])[2]})
    return sorted(results, key=lambda x: x["振幅"], reverse=True)[:3]

# ==========================================
# 5. 雙面板：說明與雷達
# ==========================================
with st.expander("📖 點我查看：燈號圖示說明與 AI 預測原理", expanded=False):
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
        **【持倉中燈號】**
        * 🔴 **斷尾求生 (強制停損)**：淨報酬率觸及 **-1.5%** 或 **現價跌破動態均價線**。
        * 🔵 **入袋為安 (達標停利)**：真實淨獲利達到 **+2.0%** 以上。
        * 🟡 **繼續煎熬 (持有觀察)**：獲利未達標，也沒跌破防線。
        """)
    with col_b:
        st.markdown("""
        **【空手觀察燈號】**
        * 🟢 **準備上車 (站上均價)**：股價強勢站在均價線之上。
        * ⚪ **旁邊玩沙 (均價之下)**：股價弱勢，手綁起來絕對不要買多。
        """)
    st.info("💡 **核心指標【動態均價線 VWAP】**：當沖最重要的生命線！代表今天所有市場參與者的平均買進成本。\n\n🤖 **AI 趨勢分析**：根據股價與均價線乖離率推算多方勝率。>50% 偏多，<50% 偏空。")

with st.expander("📡 AI 雷達戰術板 (今日最佳衝浪標的)", expanded=False):
    radar_picks = run_radar()
    if radar_picks:
        for i, pick in enumerate(radar_picks):
            st.info(f"**🏆 Top {i+1}: {pick['名稱']} ({pick['代號']})** ｜ 現價: {pick['現價']} ｜ 振幅: {pick['振幅']:.2f}% \n\n 🤖 **AI 戰術：** {pick['策略']}")
    else:
        st.write("雷達收集中或假日休市。")

st.markdown("---")

# ==========================================
# 6. 新增自選股與儀表板
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
            save_data(st.session_state.db["portfolio"], st.session_state.db["pnl_history"], st.session_state.db["broker"])
            st.success(f"✅ {new_name} 已加入！")
            st.rerun()

st.markdown("---")
col_title, col_btn1, col_btn2 = st.columns([6, 2, 2])
with col_title:
    st.subheader("🎯 當沖戰情室 (含真實交易成本計算)")
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
        row = {
            "🗑️ 刪除": False, "股票代號": ticker, "股票名稱": info["名稱"], 
            "目前報價": data['price'], "你的進場價": info["進場價"], 
            "🛡️ 損平價": 0.0, "真實淨報酬(%)": 0.0, 
            "多方勝率(%)": analyze_trend(data['price'], data['vwap'], data['high'], data['low'])[1], 
            "行動指令": ""
        }
        
        if info["進場價"] > 0:
            entry_p = info["進場價"]
            curr_p = data['price']
            
            buy_fee = entry_p * 0.001425 * discount
            sell_fee = curr_p * 0.001425 * discount
            tax = curr_p * 0.0015
            
            net_profit = curr_p - entry_p - buy_fee - sell_fee - tax
            net_return_pct = (net_profit / entry_p) * 100
            row["真實淨報酬(%)"] = round(net_return_pct, 2)
            
            breakeven = (entry_p * (1 + 0.001425 * discount)) / (1 - 0.001425 * discount - 0.0015)
            row["🛡️ 損平價"] = round(breakeven, 2)
            
            if net_return_pct <= -1.5 or curr_p < data['vwap']:
                row["行動指令"] = "🔴 斷尾求生"
            elif net_return_pct >= 2.0:
                row["行動指令"] = "🔵 入袋為安"
            else:
                row["行動指令"] = "🟡 繼續煎熬"
        else:
            row["行動指令"] = "🟢 準備上車" if data['price'] > data['vwap'] else "⚪ 旁邊玩沙"
    else:
        row = {"🗑️ 刪除": False, "股票代號": ticker, "股票名稱": info["名稱"], "行動指令": "⚠️ 報價異常"}
    display_data.append(row)

df = pd.DataFrame(display_data)
edited_df = st.data_editor(
    df, disabled=["股票代號", "股票名稱", "目前報價", "🛡️ 損平價", "真實淨報酬(%)", "多方勝率(%)", "行動指令"], 
    hide_index=True, width="stretch"
)

need_rerun = False
new_portfolio = {}
for index, row in edited_df.iterrows():
    if row.get("🗑️ 刪除", False) == True: continue
    ticker = str(row["股票代號"]).strip()
    if not ticker: continue
    new_portfolio[ticker] = {"名稱": str(row["股票名稱"]).strip(), "進場價": float(row.get("你的進場價", 0.0))}

if new_portfolio != st.session_state.db["portfolio"]:
    st.session_state.db["portfolio"] = new_portfolio 
    save_data(new_portfolio, st.session_state.db["pnl_history"], st.session_state.db["broker"])
    st.rerun() 

if auto_refresh:
    time.sleep(10)
    st.rerun()
