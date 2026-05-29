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
st.set_page_config(page_title="韭菜分析師 | 上帝模式版", layout="wide", initial_sidebar_state="expanded")

# 👑 系統管理員名單與密碼設定
ADMIN_USERS = ["陳奕德", "Admin", "管理員"]
ADMIN_PASSWORD = "77777777"  # ⬅️ 在這裡設定你的專屬管理員密碼 (可隨時修改)

BROKERS = {
    "永豐金證券 (大戶投 - 2折)": 0.2, "國泰綜合證券 (2.8折)": 0.28, "口袋證券 (2.8折)": 0.28,
    "富邦證券 (6折)": 0.6, "元大證券 (6折)": 0.6, "凱基證券 (6折)": 0.6,
    "玉山證券 (6折)": 0.6, "群益金鼎證券 (6折)": 0.6, "自訂 / 無折讓 (10折)": 1.0
}

# ==========================================
# 0. 全域系統資料庫 (用來記錄封鎖名單)
# ==========================================
SYSTEM_FILE = "system_config.json"

def load_system_config():
    if os.path.exists(SYSTEM_FILE):
        try:
            with open(SYSTEM_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"blocked_users": []}
    return {"blocked_users": []}

def save_system_config(config):
    with open(SYSTEM_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

sys_config = load_system_config()

# ==========================================
# 1. 帳號登入系統與封鎖攔截 (🛡️ 新增密碼驗證)
# ==========================================
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

if st.session_state.current_user is None:
    st.title("🔐 韭菜分析師 - 登入系統")
    st.markdown("##### 建立或登入您的個人專屬戰情室")
    
    # 掃描本地端已經存在的 user_XXX.json 檔案 (把管理員從捷徑中剔除，保護隱私)
    raw_users = [f.replace("user_", "").replace(".json", "") for f in os.listdir(".") if f.startswith("user_") and f.endswith(".json")]
    existing_users = [u for u in raw_users if u not in ADMIN_USERS]
    
    if existing_users:
        st.write("👤 **一般用戶快速登入：**")
        cols = st.columns(min(len(existing_users), 5))
        for i, user in enumerate(existing_users):
            if cols[i % 5].button(f"🔑 {user}", use_container_width=True):
                # 攔截黑名單
                if user in sys_config.get("blocked_users", []):
                    st.error(f"🚫 登入失敗！帳號「{user}」已被管理員封鎖。")
                else:
                    st.session_state.current_user = user
                    st.rerun()
        st.markdown("---")
        st.write("✨ **或手動登入 / 建立新帳號：**")

    # 傳統文字輸入登入框 (加入密碼欄位)
    with st.form("login_form"):
        username = st.text_input("請輸入您的名字：", max_chars=20, placeholder="例如：陳大明")
        password = st.text_input("密碼 (僅管理員需要填寫，一般用戶留白即可)：", type="password")
        submit = st.form_submit_button("進入戰情室")
        
        if submit and username.strip():
            clean_name = username.strip()
            
            # 1. 檢查是否在黑名單
            if clean_name in sys_config.get("blocked_users", []):
                st.error(f"🚫 登入失敗！帳號「{clean_name}」已被管理員封鎖。")
            
            # 2. 檢查是否為管理員，若是則核對密碼
            elif clean_name in ADMIN_USERS:
                if password == ADMIN_PASSWORD:
                    st.session_state.current_user = clean_name
                    st.rerun()
                else:
                    st.error("🚫 登入失敗！管理員密碼錯誤，拒絕存取。")
            
            # 3. 一般用戶正常登入 (不管密碼)
            else:
                st.session_state.current_user = clean_name
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
    default_data = {"session_date": current_session, "portfolio": {}, "pnl_history": [], "broker": "永豐金證券 (大戶投 - 2折)"}
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
    data_to_save = {"session_date": current_session, "portfolio": portfolio_data, "pnl_history": trimmed_pnl, "broker": broker}
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=4)

if 'db' not in st.session_state:
    st.session_state.db = load_data()

# ==========================================
# 3. 側邊欄：個人檔案、權限管理與損益紀錄
# ==========================================
with st.sidebar:
    # 👑 上帝模式判斷
    is_admin = USER in ADMIN_USERS
    role_icon = "👑 (管理員)" if is_admin else "👤 (一般用戶)"
    
    st.header(f"{role_icon} {USER}")
    
    # --- 管理員專屬後台 ---
    if is_admin:
        with st.expander("🛠️ 管理員控制台", expanded=True):
            st.markdown("⚠️ **生殺大權，謹慎使用**")
            all_users = [f.replace("user_", "").replace(".json", "") for f in os.listdir(".") if f.startswith("user_") and f.endswith(".json")]
            target_users = [u for u in all_users if u not in ADMIN_USERS]
            
            if target_users:
                user_to_manage = st.selectbox("選擇懲罰對象：", ["請選擇..."] + target_users)
                if user_to_manage != "請選擇...":
                    col_m1, col_m2 = st.columns(2)
                    with col_m1:
                        if st.button("🚫 封鎖帳號"):
                            if user_to_manage not in sys_config["blocked_users"]:
                                sys_config["blocked_users"].append(user_to_manage)
                                save_system_config(sys_config)
                                st.success(f"已封鎖 {user_to_manage}！")
                                time.sleep(1)
                                st.rerun()
                    with col_m2:
                        if st.button("🗑️ 刪除檔案"):
                            try:
                                os.remove(f"user_{user_to_manage}.json")
                                st.success(f"已徹底刪除 {user_to_manage}！")
                                time.sleep(1)
                                st.rerun()
                            except:
                                st.error("刪除失敗。")
            else:
                st.caption("目前沒有其他使用者。")
            
            blocked_list = sys_config.get("blocked_users", [])
            if blocked_list:
                st.markdown("---")
                user_to_unblock = st.selectbox("選擇赦免對象：", ["請選擇..."] + blocked_list)
                if user_to_unblock != "請選擇..." and st.button("✅ 解除封鎖"):
                    sys_config["blocked_users"].remove(user_to_unblock)
                    save_system_config(sys_config)
                    st.success(f"已解除 {user_to_unblock} 的封鎖！")
                    time.sleep(1)
                    st.rerun()

    # --- 一般用戶 / 券商設定 ---
    st.markdown("---")
    current_broker = st.session_state.db.get("broker", "永豐金證券 (大戶投 - 2折)")
    broker_list = list(BROKERS.keys())
    broker_index = broker_list.index(current_broker) if current_broker in broker_list else 0
    
    selected_broker = st.selectbox("🏦 常用券商與折讓", broker_list, index=broker_index)
    if selected_broker != current_broker:
        st.session_state.db["broker"] = selected_broker
        save_data(st.session_state.db["portfolio"], st.session_state.db["pnl_history"], selected_broker)
        st.rerun()
        
    discount = BROKERS[selected_broker]
    
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

    st.markdown("---")
    if st.button("🚪 登出系統", use_container_width=True):
        st.session_state.current_user = None
        st.session_state.pop('db', None)
        st.rerun()
        
    if st.button("🧨 永久刪除我的帳號", use_container_width=True, type="primary"):
        try:
            os.remove(DATA_FILE)
        except:
            pass
        st.session_state.current_user = None
        st.session_state.pop('db', None)
        st.rerun()

# ==========================================
# 4. 核心功能與 AI 演算法
# ==========================================
st.title("🥬 你的錢包，我來當沖 (上帝模式版)")

@st.cache_data(ttl=10) 
def get_stock_data(ticker):
    try:
        ticker_str = str(ticker).strip()
        stock = yf.Ticker(f"{ticker_str}.TW")
        hist = stock.history(period="1d", interval="1m")
        if hist.empty: return None
        current_price = round(hist['Close'].iloc[-1], 2)
        
        hist['Typical_Price'] = (hist['High'] + hist['Low'] + hist['Close']) / 3
        hist['Cum_Vol'] = hist['Volume'].cumsum()
        hist['Cum_Vol_Price'] = (hist['Typical_Price'] * hist['Volume']).cumsum()
        vwap = current_price
        if hist['Cum_Vol'].iloc[-1] > 0:
            vwap = round(hist['Cum_Vol_Price'].iloc[-1] / hist['Cum_Vol'].iloc[-1], 2)
            
        return {"price": current_price, "vwap": vwap, "high": hist['High'].max(), "low": hist['Low'].min()}
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
        strategy = "⚖️ 多空交戰"
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
# 5. 雙面板與操作區
# ==========================================
with st.expander("📖 點我查看：燈號圖示說明與 AI 預測原理", expanded=False):
    st.markdown("""
    * 🔴 **斷尾求生 (強制停損)**：淨報酬觸及 **-1.5%** 或 **跌破均價線**。
    * 🔵 **入袋為安 (達標停利)**：淨報酬達 **+2.0%**。
    * 🟢 **準備上車 (站上均價)**：空手且強勢站在均價線之上。
    """)

with st.expander("📡 AI 雷達戰術板 (今日最佳衝浪標的)", expanded=False):
    radar_picks = run_radar()
    if radar_picks:
        for i, pick in enumerate(radar_picks):
            st.info(f"**🏆 Top {i+1}: {pick['名稱']} ({pick['代號']})** ｜ 現價: {pick['現價']} ｜ 振幅: {pick['振幅']:.2f}% \n\n 🤖 **AI 戰術：** {pick['策略']}")

st.markdown("---")
st.subheader("➕ 佈署新戰場")
col1, col2, col3, col4 = st.columns([2, 2, 2, 4])
with col1:
    new_ticker = st.text_input("股票代號", max_chars=6)
with col2:
    new_name = st.text_input("股票名稱")
with col3:
    new_entry = st.number_input("進場價 (未進填0)", min_value=0.0, step=0.1, value=0.0)
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
    st.subheader("🎯 當沖戰情室 (含真實成本計算)")
with col_btn1:
    if st.button("🔄 強制手動更新"):
        st.cache_data.clear() 
        st.rerun()
with col_btn2:
    auto_refresh = st.toggle("⚡ 開啟自動更新", value=False)

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
