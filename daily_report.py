#!/usr/bin/env python3
"""
Investment Learning Daily Report
- 第一層產業：每日輪換（系統性學習）
- 第二層產業：當日熱點（由 Claude 根據新聞判斷）
"""

import os
import json
import html as _html_lib
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf
import feedparser
import anthropic

# ── Config ─────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL    = os.environ["RECIPIENT_EMAIL"]

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
QUESTION_FILE = Path("yesterday_question.json")

# ── 持倉 ───────────────────────────────────────────────────────────────────────
MY_HOLDINGS = [
    {"ticker": "0050.TW", "name": "元大台灣50"},
    {"ticker": "2618.TW", "name": "長榮航"},
]

# ── 大盤指數 ───────────────────────────────────────────────────────────────────
MARKET_INDICES = [
    {"label": "台股加權",     "ticker": "^TWII"},
    {"label": "S&P 500",     "ticker": "^GSPC"},
    {"label": "USD/TWD",     "ticker": "TWD=X"},
    {"label": "VIX 恐慌指數","ticker": "^VIX"},
]

# ── 輪換產業（每天一個，系統性學習）──────────────────────────────────────────
ALL_SECTORS = [
    {"name": "航運業",      "tickers": ["2603.TW","2609.TW","2615.TW"], "desc": "長榮、陽明、萬海，台灣三大航運龍頭"},
    {"name": "半導體",      "tickers": ["2330.TW","2303.TW"],           "desc": "台積電、聯電，台灣護國神山"},
    {"name": "金融保險",    "tickers": ["2882.TW","2891.TW"],           "desc": "國泰金、中信金，壽險與銀行"},
    {"name": "電子零組件",  "tickers": ["2317.TW","2354.TW"],           "desc": "鴻海、鴻準，電子代工與機殼"},
    {"name": "生技醫療",    "tickers": ["4743.TW","1786.TW"],           "desc": "合一、科妍，台灣生技代表"},
    {"name": "鋼鐵",        "tickers": ["2002.TW","2008.TW"],           "desc": "中鋼、高興昌，原物料循環"},
    {"name": "電動車供應鏈","tickers": ["2308.TW","6213.TW"],           "desc": "台達電、聯茂，電動車零組件"},
    {"name": "DRAM記憶體",  "tickers": ["4256.TW","3474.TW"],           "desc": "台灣記憶體產業"},
    {"name": "被動元件",    "tickers": ["2327.TW","2356.TW"],           "desc": "國巨、英業達，電子基礎元件"},
    {"name": "網路通訊",    "tickers": ["2408.TW","3045.TW"],           "desc": "南亞科、台灣大，通訊基礎建設"},
    {"name": "觀光餐飲",    "tickers": ["2618.TW","2707.TW"],           "desc": "長榮航、晶華，內需消費復甦"},
    {"name": "電信",        "tickers": ["2412.TW","3045.TW"],           "desc": "中華電、台灣大，高殖利率防禦"},
    {"name": "建材營建",    "tickers": ["2501.TW","2511.TW"],           "desc": "國建、中建，房地產景氣連動"},
    {"name": "石化塑膠",    "tickers": ["1301.TW","1303.TW"],           "desc": "台塑、南亞，傳產循環股"},
    {"name": "食品飲料",    "tickers": ["1216.TW","1210.TW"],           "desc": "統一、大成，民生必需品"},
]

# 熱點產業候選（Claude 從這裡選一個，並帶入對應股票）
HOT_SECTOR_CANDIDATES = {
    "航運業":      {"tickers": ["2603.TW","2609.TW","2615.TW"], "desc": "長榮、陽明、萬海"},
    "半導體":      {"tickers": ["2330.TW","2303.TW"],           "desc": "台積電、聯電"},
    "AI伺服器":    {"tickers": ["2317.TW","3231.TW"],           "desc": "鴻海、緯創"},
    "金融保險":    {"tickers": ["2882.TW","2891.TW"],           "desc": "國泰金、中信金"},
    "電動車":      {"tickers": ["2308.TW","6213.TW"],           "desc": "台達電、聯茂"},
    "生技醫療":    {"tickers": ["4743.TW","1786.TW"],           "desc": "合一、科妍"},
    "鋼鐵原物料":  {"tickers": ["2002.TW","2008.TW"],           "desc": "中鋼、高興昌"},
    "電信":        {"tickers": ["2412.TW","3045.TW"],           "desc": "中華電、台灣大"},
    "DRAM記憶體":  {"tickers": ["4256.TW","3474.TW"],           "desc": "南亞科、華邦電"},
    "觀光餐飲":    {"tickers": ["2618.TW","2707.TW"],           "desc": "長榮航、晶華"},
}

# ── 每日概念 ───────────────────────────────────────────────────────────────────
INVESTMENT_CONCEPTS = [
    ("本益比 P/E Ratio",          "判斷股票貴不貴最基本的工具，現在股價是每年獲利的幾倍？"),
    ("殖利率 Dividend Yield",     "每年配息÷股價，數字越高代表現金回報越豐厚"),
    ("股價淨值比 P/B Ratio",      "股價相對於公司帳面資產的溢價，銀行股常用這個指標"),
    ("本益成長比 PEG",            "P/E除以盈餘成長率，低於1通常被認為被低估"),
    ("EV/EBITDA",                 "企業整體價值相對於稅前息前折舊前利潤，跨國比較常用"),
    ("自由現金流 FCF",            "真正流入公司口袋的現金，比帳面獲利更難造假"),
    ("毛利率",                    "收入扣掉直接成本後的比例，反映產品競爭力"),
    ("淨利率",                    "最終淨利佔營收的比例，數字越穩定代表公司體質越好"),
    ("股東權益報酬率 ROE",        "公司用股東的錢賺了多少？巴菲特最愛看這個"),
    ("負債比率",                  "負債佔總資產的比例，越低代表財務越穩健"),
    ("流動比率",                  "流動資產÷流動負債，判斷公司短期還錢能力"),
    ("資本支出 CapEx",            "公司買設備廠房花多少錢，重資產vs輕資產商業模式的差異"),
    ("ROIC 投入資本回報率",       "衡量公司把每一塊錢資本運用得多有效率"),
    ("護城河 Economic Moat",      "讓競爭對手難以入侵的競爭優勢，品牌、專利、網路效應等"),
    ("Porter五力分析",            "從供應商、買家、競爭者、替代品、新進者五個角度分析產業"),
    ("市占率",                    "公司在同產業的銷售份額，市占率擴張是成長的訊號"),
    ("景氣循環股",                "隨景氣好壞大幅波動的行業，如航運、鋼鐵、石化"),
    ("防禦型股票",                "景氣下行時仍能維持獲利的行業，如電信、食品、醫療"),
    ("巴菲特指標",                "股市總市值÷GDP，用來判斷整體市場高估或低估"),
    ("殖利率曲線倒掛",            "短債利率高於長債，歷史上常是經濟衰退的前兆"),
    ("聯準會利率政策",            "升息讓借錢變貴、股票估值下降；降息反之"),
    ("CPI通膨指標",               "物價上漲速度，影響央行政策和企業成本"),
    ("PMI採購經理人指數",         "超過50代表製造業擴張，低於50代表收縮"),
    ("失業率",                    "就業市場強弱是消費力的基礎，影響企業獲利"),
    ("RSI相對強弱指標",           "0-100的指標，低於30可能超賣，高於70可能超買"),
    ("移動平均線 MA",             "平滑價格波動，判斷趨勢方向，黃金交叉是漲訊號"),
    ("成交量",                    "價漲量增是健康上漲，價漲量縮要小心"),
    ("價值投資",                  "以低於內在價值的價格買入，等市場回歸理性"),
    ("成長投資",                  "買高速成長的公司，願意付出更高估值換取未來獲利"),
    ("安全邊際",                  "買入價格要遠低於估算的內在價值，給自己犯錯的空間"),
    ("分散投資",                  "不把雞蛋放在同一個籃子，降低單一股票風險"),
    ("定期定額",                  "每月固定金額買入，用時間平攤成本，適合0050這類ETF"),
    ("股息再投資",                "把配息拿去繼續買股，複利效應長期非常驚人"),
    ("資產配置",                  "股票、債券、現金的比例分配，決定整體組合的風險報酬"),
    ("外資動向",                  "外國法人的買賣方向，資金龐大對台股影響力很大"),
    ("投信買賣超",                "台灣本土基金的操作方向，常影響中小型股"),
    ("融資餘額",                  "散戶借錢買股的金額，融資大增代表散戶過度樂觀要小心"),
    ("法人籌碼集中度",            "主力持股集中，籌碼越安定越不容易大跌"),
]

RSS_FEEDS = [
    "https://finance.yahoo.com/news/rssindex",
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5ETWII&region=TW&lang=zh-TW",
]


# ══════════════════════════════════════════════════════════════════════════════
# 昨日問題讀寫
# ══════════════════════════════════════════════════════════════════════════════

def load_yesterday_question() -> str:
    if QUESTION_FILE.exists():
        try:
            data = json.loads(QUESTION_FILE.read_text(encoding="utf-8"))
            return data.get("question", "")
        except Exception:
            pass
    return "這是第一天的報告，還沒有昨日問題，今天開始積累吧！"


def save_todays_question(question: str) -> None:
    QUESTION_FILE.write_text(
        json.dumps({"question": question, "date": datetime.now().strftime("%Y-%m-%d")},
                   ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"💾 今日問題已存檔：{question[:60]}...")


# ══════════════════════════════════════════════════════════════════════════════
# 技術指標
# ══════════════════════════════════════════════════════════════════════════════

def compute_rsi(closes: list, period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def compute_ma(closes: list, period: int) -> float | None:
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)


def safe_div_yield(info: dict, current_price: float) -> float | None:
    rate = info.get("dividendRate")
    if not rate or not current_price or current_price == 0:
        return None
    result = round((rate / current_price) * 100, 2)
    return None if result > 20 else result


# ══════════════════════════════════════════════════════════════════════════════
# 抓取數據
# ══════════════════════════════════════════════════════════════════════════════

def fetch_market_data() -> list:
    results = []
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=10)
    for item in MARKET_INDICES:
        try:
            hist = yf.Ticker(item["ticker"]).history(
                start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
            if hist.empty or len(hist) < 2:
                results.append({"label": item["label"], "error": "資料不足"})
                continue
            current = float(hist["Close"].iloc[-1])
            prev    = float(hist["Close"].iloc[-2])
            results.append({
                "label": item["label"], "ticker": item["ticker"],
                "current": round(current, 2),
                "change_pct": round((current - prev) / prev * 100, 2),
            })
        except Exception as e:
            results.append({"label": item["label"], "error": str(e)})
    return results


def fetch_holdings_data() -> list:
    results = []
    for holding in MY_HOLDINGS:
        try:
            t    = yf.Ticker(holding["ticker"])
            info = t.info
            hist = t.history(period="6mo")
            if hist.empty:
                results.append({**holding, "error": "資料不足"})
                continue
            closes     = [float(x) for x in hist["Close"].tolist()]
            current    = closes[-1]
            prev       = closes[-2] if len(closes) > 1 else current
            change_pct = (current - prev) / prev * 100
            rsi  = compute_rsi(closes)
            ma20 = compute_ma(closes, 20)
            ma60 = compute_ma(closes, 60)
            w52h = info.get("fiftyTwoWeekHigh")
            w52l = info.get("fiftyTwoWeekLow")
            pos_pct = None
            if w52h and w52l and w52h != w52l:
                pos_pct = round((current - w52l) / (w52h - w52l) * 100, 1)
            results.append({
                "ticker": holding["ticker"], "name": holding["name"],
                "current": round(current, 2), "change_pct": round(change_pct, 2),
                "rsi": rsi, "ma20": ma20, "ma60": ma60,
                "above_ma20": current > ma20 if ma20 else None,
                "above_ma60": current > ma60 if ma60 else None,
                "position_in_52w_pct": pos_pct,
                "pe": round(info.get("trailingPE"), 1) if info.get("trailingPE") else None,
                "div_yield_pct": safe_div_yield(info, current),
            })
        except Exception as e:
            results.append({**holding, "error": str(e)})
    return results


def fetch_sector_stocks(tickers: list) -> list:
    stocks = []
    for ticker_str in tickers:
        try:
            t    = yf.Ticker(ticker_str)
            info = t.info
            hist = t.history(period="3mo")
            closes  = [float(x) for x in hist["Close"].tolist()] if not hist.empty else []
            current = closes[-1] if closes else None
            ma20_val = compute_ma(closes, 20)
            stocks.append({
                "ticker":    ticker_str,
                "name":      info.get("longName") or info.get("shortName") or ticker_str,
                "current":   round(current, 2) if current else None,
                "rsi":       compute_rsi(closes) if closes else None,
                "ma20":      round(ma20_val, 2) if ma20_val else None,
                "pe":        round(info.get("trailingPE"), 1) if info.get("trailingPE") else None,
                "div_yield": safe_div_yield(info, current) if current else None,
            })
        except Exception as e:
            stocks.append({"ticker": ticker_str, "error": str(e)})
    return stocks


def fetch_news(max_items: int = 12) -> list:
    news = []
    per_feed = max(1, max_items // len(RSS_FEEDS))
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:per_feed]:
                news.append({
                    "title":   entry.get("title", "").strip(),
                    "summary": entry.get("summary", "")[:250].strip(),
                })
        except Exception as e:
            print(f"RSS error ({url}): {e}")
    return news[:max_items]


def select_today_rotation_sector() -> dict:
    return ALL_SECTORS[datetime.now().timetuple().tm_yday % len(ALL_SECTORS)]


def select_today_concept() -> tuple:
    return INVESTMENT_CONCEPTS[datetime.now().timetuple().tm_yday % len(INVESTMENT_CONCEPTS)]


# ══════════════════════════════════════════════════════════════════════════════
# Claude 判斷熱點產業
# ══════════════════════════════════════════════════════════════════════════════

def detect_hot_sector(news: list) -> dict:
    """讓 Claude 根據今日新聞判斷最熱門的台股產業，從候選清單選一個"""
    candidates = list(HOT_SECTOR_CANDIDATES.keys())
    news_text  = "\n".join(f"- {n['title']}" for n in news[:10])

    prompt = f"""根據以下今日財經新聞標題，判斷今天台股最受關注的產業。
只能從這個清單選一個：{candidates}
新聞：
{news_text}

只輸出產業名稱，不要其他文字。例如：半導體"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        sector_name = response.content[0].text.strip()
        if sector_name in HOT_SECTOR_CANDIDATES:
            candidate = HOT_SECTOR_CANDIDATES[sector_name]
            return {
                "name":    sector_name,
                "desc":    candidate["desc"],
                "tickers": candidate["tickers"],
                "stocks":  fetch_sector_stocks(candidate["tickers"]),
            }
    except Exception as e:
        print(f"Hot sector detection failed: {e}")

    # fallback：用輪換產業的下一個
    fallback_idx = (datetime.now().timetuple().tm_yday + 1) % len(ALL_SECTORS)
    fallback = ALL_SECTORS[fallback_idx]
    return {**fallback, "stocks": fetch_sector_stocks(fallback["tickers"])}


# ══════════════════════════════════════════════════════════════════════════════
# JSON 修復
# ══════════════════════════════════════════════════════════════════════════════

def _try_parse_json(raw: str) -> dict | None:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    for suffix in ["}", "}}", "}]}", "}]}}", "}]}}}}"]:
        try:
            return json.loads(raw + suffix)
        except json.JSONDecodeError:
            continue
    last_brace = raw.rfind("}")
    if last_brace > 0:
        try:
            return json.loads(raw[: last_brace + 1])
        except json.JSONDecodeError:
            pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Claude AI 主分析
# ══════════════════════════════════════════════════════════════════════════════

def generate_report(
    market_data, holdings_data, rotation_sector_data, hot_sector_data,
    news, concept, yesterday_question
) -> dict:
    today = datetime.now(timezone.utc).astimezone(
        timezone(timedelta(hours=8))
    ).strftime("%Y年%m月%d日")
    concept_name, concept_hint = concept

    prompt = f"""
你是台股投資教育者，幫助一位剛入門的大學生每天學習投資。
用繁體中文，語氣親切直接，不廢話。

今日日期：{today}
【大盤】{json.dumps(market_data, ensure_ascii=False)}
【持倉】{json.dumps(holdings_data, ensure_ascii=False)}
【輪換產業：{rotation_sector_data['name']}】{json.dumps(rotation_sector_data, ensure_ascii=False)}
【今日熱點產業：{hot_sector_data['name']}】{json.dumps(hot_sector_data, ensure_ascii=False)}
【新聞】{json.dumps(news[:10], ensure_ascii=False)}
【概念】{concept_name}：{concept_hint}
【昨日問題】{yesterday_question}

輸出以下 JSON，不含任何 markdown 或額外文字：
{{
  "report_date": "{today}",
  "market_summary": [{{"label":"指數","current":數字,"change_pct":數字,"one_line":"20字內"}}],
  "holdings": [{{
    "ticker":"代號","name":"名稱","current":數字,"change_pct":數字,
    "rsi":數字或null,"ma20":數字或null,"ma60":數字或null,
    "above_ma20":true或false或null,"above_ma60":true或false或null,
    "position_in_52w_pct":數字或null,"div_yield_pct":數字或null,
    "rsi_interpretation":"30字內","ma_interpretation":"30字內",
    "overall_status":"40字內"
  }}],
  "rotation_sector": {{
    "name":"產業名","desc":"簡介","trend":"100字內",
    "stocks":[{{"ticker":"代號","name":"名稱","current":數字或null,"rsi":數字或null,
      "pe":數字或null,"div_yield":數字或null,
      "rsi_signal":"超買/中性/超賣","valuation":"偏貴/合理/偏便宜","one_line":"40字內"}}],
    "key_insight":"60字內"
  }},
  "hot_sector": {{
    "name":"產業名","why_hot":"為什麼今天這個產業是熱點，結合新聞說明，60字內",
    "desc":"簡介","trend":"100字內",
    "stocks":[{{"ticker":"代號","name":"名稱","current":數字或null,"rsi":數字或null,
      "pe":數字或null,"div_yield":數字或null,
      "rsi_signal":"超買/中性/超賣","valuation":"偏貴/合理/偏便宜","one_line":"40字內"}}],
    "key_insight":"60字內"
  }},
  "news_summary": [{{"title":"標題","impact":"30字內"}}],
  "concept_today": {{
    "name":"{concept_name}","definition":"50字內","why_it_matters":"50字內",
    "how_to_use":"80字內","todays_example":"80字內","key_takeaway":"20字內"
  }},
  "yesterday_answer": {{
    "question":"{yesterday_question}",
    "answer":"100字內","lesson":"50字內"
  }},
  "todays_question": {{
    "question":"根據今天數據出一個有明確答案的思考題",
    "hint":"30字內提示，不直接給答案"
  }}
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=5000,
        temperature=0.5,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    parsed = _try_parse_json(raw)
    if parsed is not None:
        return parsed
    print(f"JSON parse failed. Raw: {raw[:300]}")
    return {"_fallback_raw": raw, "report_date": today}


# ══════════════════════════════════════════════════════════════════════════════
# HTML Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _pct_color(pct):
    if pct is None: return "#6b7280"
    return "#16a34a" if float(pct) >= 0 else "#dc2626"

def _pct_arrow(pct):
    if pct is None: return "N/A"
    arrow = "▲" if float(pct) >= 0 else "▼"
    return f"{arrow} {abs(float(pct)):.2f}%"

def _rsi_color(rsi):
    if rsi is None: return "#6b7280"
    if rsi < 30: return "#2563eb"
    if rsi > 70: return "#dc2626"
    return "#16a34a"

def _rsi_label(rsi):
    if rsi is None: return "N/A"
    if rsi < 30: return f"{rsi} 超賣區"
    if rsi > 70: return f"{rsi} 超買區"
    return f"{rsi} 中性"

VERDICT_COLOR = {"偏貴": "#dc2626", "合理": "#d97706", "偏便宜": "#16a34a"}


def _render_sector_block(sector: dict, accent_color: str, label: str, badge_fn) -> str:
    """共用的產業區塊 HTML，輪換產業和熱點產業都用這個"""
    why_hot = sector.get("why_hot", "")
    html = f"""<table width='100%' cellpadding='0' cellspacing='0' style='border:1px solid #e0e7ff;border-radius:10px;overflow:hidden;margin-bottom:16px;'>
<tr><td style='background:{accent_color};padding:14px 20px;border-bottom:1px solid #e0e7ff;'>
  <div style='font-size:11px;color:rgba(255,255,255,0.7);margin-bottom:4px;'>{label}</div>
  <div style='font-size:16px;font-weight:700;color:#fff;'>{sector.get('name','')}</div>
  <div style='font-size:13px;color:rgba(255,255,255,0.85);margin-top:4px;'>{sector.get('desc','')}</div>
</td></tr>"""

    if why_hot:
        html += f"""<tr><td style='background:#fef9c3;padding:10px 20px;border-bottom:1px solid #fde68a;'>
  <span style='font-size:12px;font-weight:700;color:#92400e;'>🔥 為什麼今天熱：</span>
  <span style='font-size:13px;color:#78350f;'>{why_hot}</span>
</td></tr>"""

    html += f"""<tr><td style='padding:14px 20px;'>
  <div style='font-size:13px;color:#374151;line-height:1.7;margin-bottom:12px;'>{sector.get('trend','')}</div>"""

    for stock in sector.get("stocks", []):
        rsi = stock.get("rsi")
        signal = stock.get("rsi_signal", "中性")
        valuation = stock.get("valuation", "合理")
        vcolor = VERDICT_COLOR.get(valuation, "#6b7280")
        signal_color = {"超買": "#dc2626", "超賣": "#2563eb", "中性": "#16a34a"}.get(signal, "#6b7280")
        div = stock.get("div_yield")
        div_str = f"{div}%" if div else "資料待確認"

        html += f"""<table width='100%' cellpadding='0' cellspacing='0' style='background:#f9fafb;border-radius:8px;margin-bottom:8px;'>
<tr><td style='padding:12px 16px;'>
  <table width='100%'><tr>
    <td><span style='font-size:14px;font-weight:700;color:#1e3a5f;'>{stock.get('ticker','')} {stock.get('name','')}</span></td>
    <td align='right'>
      {badge_fn(signal, signal_color)}&nbsp;{badge_fn(valuation, vcolor)}
    </td>
  </tr></table>
  <table width='100%' style='margin-top:8px;'><tr>
    <td style='font-size:13px;color:#6b7280;'>RSI: <strong style='color:{_rsi_color(rsi)};'>{_rsi_label(rsi)}</strong></td>
    <td style='font-size:13px;color:#6b7280;'>PE: <strong>{stock.get('pe','N/A')}</strong></td>
    <td style='font-size:13px;color:#6b7280;'>殖利率: <strong>{div_str}</strong></td>
  </tr></table>
  <div style='font-size:13px;color:#374151;margin-top:8px;'>{stock.get('one_line','')}</div>
</td></tr></table>"""

    html += f"""</td></tr>
<tr><td style='background:#f8fafc;padding:10px 20px;border-top:1px solid #e5e7eb;'>
  <span style='font-size:12px;font-weight:700;color:#4f46e5;'>🔑 重點：</span>
  <span style='font-size:13px;color:#374151;'>{sector.get('key_insight','')}</span>
</td></tr></table>"""

    return html


# ══════════════════════════════════════════════════════════════════════════════
# HTML Email Builder
# ══════════════════════════════════════════════════════════════════════════════

def build_html_email(report: dict) -> str:
    if "_fallback_raw" in report:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        escaped = _html_lib.escape(report["_fallback_raw"])
        return f"""<!DOCTYPE html><html lang="zh-TW"><head><meta charset="UTF-8"></head>
<body style="font-family:sans-serif;padding:20px;"><h2>投資日報 {report.get('report_date','')}</h2>
<pre style="white-space:pre-wrap;">{escaped}</pre>
<p style="color:#9ca3af;font-size:12px;">{ts}</p></body></html>"""

    date_str = report.get("report_date", "")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def section(title, color):
        return (f"<table width='100%' cellpadding='0' cellspacing='0' style='margin:28px 0 16px;'>"
                f"<tr><td style='border-left:4px solid {color};padding-left:12px;"
                f"font-size:18px;font-weight:700;color:#1e3a5f;'>{title}</td></tr></table>")

    def badge(text, color):
        return f"<span style='background:{color};color:#fff;font-size:11px;font-weight:700;padding:2px 10px;border-radius:20px;'>{text}</span>"

    html = f"""<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>每日投資學習報告 {date_str}</title></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:'Helvetica Neue',Arial,'PingFang TC','Microsoft JhengHei',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:20px 16px;">
<table width="660" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
<tr><td style="background:linear-gradient(135deg,#1e3a5f,#1d4ed8);padding:28px 40px;text-align:center;">
  <div style="font-size:11px;color:#93c5fd;letter-spacing:3px;margin-bottom:6px;">DAILY INVESTMENT LEARNING</div>
  <div style="font-size:26px;font-weight:700;color:#fff;margin-bottom:6px;">📊 每日投資學習報告</div>
  <div style="font-size:13px;color:#bfdbfe;">{date_str} · 每日 08:00 台北時間</div>
</td></tr>
<tr><td style="padding:28px 40px;">"""

    # 大盤
    html += section("📈 今日大盤概況", "#2563eb")
    html += "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse;'><tr style='background:#f8fafc;'><td style='padding:8px 12px;font-size:12px;color:#6b7280;font-weight:700;'>指數</td><td style='padding:8px 12px;font-size:12px;color:#6b7280;font-weight:700;text-align:right;'>現值</td><td style='padding:8px 12px;font-size:12px;color:#6b7280;font-weight:700;text-align:right;'>漲跌</td><td style='padding:8px 12px;font-size:12px;color:#6b7280;font-weight:700;'>解讀</td></tr>"
    for i, item in enumerate(report.get("market_summary", [])):
        bg = "#fff" if i % 2 == 0 else "#f8fafc"
        pct, cur = item.get("change_pct"), item.get("current")
        html += f"<tr style='background:{bg};border-top:1px solid #f1f5f9;'><td style='padding:10px 12px;font-size:14px;font-weight:700;color:#1e3a5f;'>{item.get('label','')}</td><td style='padding:10px 12px;font-size:14px;text-align:right;'>{f'{cur:,.2f}' if cur else 'N/A'}</td><td style='padding:10px 12px;font-size:14px;font-weight:700;color:{_pct_color(pct)};text-align:right;'>{_pct_arrow(pct)}</td><td style='padding:10px 12px;font-size:13px;color:#6b7280;'>{item.get('one_line','')}</td></tr>"
    html += "</table>"

    # 持倉
    html += section("💼 我的持倉狀況", "#059669")
    for h in report.get("holdings", []):
        pct, rsi = h.get("change_pct"), h.get("rsi")
        ma20, ma60 = h.get("ma20"), h.get("ma60")
        pos  = h.get("position_in_52w_pct")
        div  = h.get("div_yield_pct")
        div_str = f"{div}%" if div else "資料待確認"
        html += f"""<table width='100%' cellpadding='0' cellspacing='0' style='border:1px solid #e5e7eb;border-radius:10px;margin-bottom:14px;overflow:hidden;'>
<tr><td style='background:#f0fdf4;padding:14px 20px;border-bottom:1px solid #d1fae5;'>
  <table width='100%'><tr>
    <td><span style='font-size:16px;font-weight:700;color:#065f46;'>{h.get('ticker','')} {h.get('name','')}</span></td>
    <td align='right'><span style='font-size:18px;font-weight:700;color:#1e3a5f;'>{h.get('current','N/A')}</span>&nbsp;<span style='font-size:14px;font-weight:700;color:{_pct_color(pct)};'>{_pct_arrow(pct)}</span></td>
  </tr></table>
</td></tr>
<tr><td style='padding:14px 20px;'>
  <table width='100%'><tr>
    <td width='25%' style='padding:6px 0;'><div style='font-size:11px;color:#6b7280;margin-bottom:3px;'>RSI (14)</div><div style='font-size:15px;font-weight:700;color:{_rsi_color(rsi)};'>{_rsi_label(rsi)}</div><div style='font-size:12px;color:#6b7280;margin-top:3px;'>{h.get('rsi_interpretation','')}</div></td>
    <td width='30%' style='padding:6px 0;border-left:1px solid #f1f5f9;padding-left:12px;'><div style='font-size:11px;color:#6b7280;margin-bottom:3px;'>均線位置</div><div style='font-size:13px;font-weight:600;color:#374151;'>MA20: {ma20 or 'N/A'} {'✅' if h.get('above_ma20') else '⚠️' if h.get('above_ma20') is False else ''}</div><div style='font-size:13px;font-weight:600;color:#374151;'>MA60: {ma60 or 'N/A'} {'✅' if h.get('above_ma60') else '⚠️' if h.get('above_ma60') is False else ''}</div><div style='font-size:12px;color:#6b7280;margin-top:3px;'>{h.get('ma_interpretation','')}</div></td>
    <td width='25%' style='padding:6px 0;border-left:1px solid #f1f5f9;padding-left:12px;'><div style='font-size:11px;color:#6b7280;margin-bottom:3px;'>52週區間</div><div style='font-size:15px;font-weight:700;color:#1e3a5f;'>{f'{pos:.0f}%' if pos is not None else 'N/A'}</div><div style='font-size:12px;color:#6b7280;'>{'接近年高' if pos and pos>70 else '接近年低' if pos and pos<30 else '中間區間'}</div></td>
    <td width='20%' style='padding:6px 0;border-left:1px solid #f1f5f9;padding-left:12px;'><div style='font-size:11px;color:#6b7280;margin-bottom:3px;'>殖利率</div><div style='font-size:15px;font-weight:700;color:#059669;'>{div_str}</div></td>
  </tr></table>
  <div style='background:#eff6ff;border-radius:6px;padding:10px 14px;margin-top:12px;font-size:13px;color:#1e40af;'>💬 {h.get('overall_status','')}</div>
</td></tr></table>"""

    # 新聞
    html += section("🌐 今日重要新聞", "#7c3aed")
    html += "<table width='100%' cellpadding='0' cellspacing='0'>"
    for n in report.get("news_summary", [])[:5]:
        html += f"<tr><td style='padding:10px 0;border-bottom:1px solid #f3f4f6;'><div style='font-size:14px;font-weight:600;color:#374151;margin-bottom:4px;'>{n.get('title','')}</div><div style='font-size:13px;color:#7c3aed;'>📌 {n.get('impact','')}</div></td></tr>"
    html += "</table>"

    # 概念
    concept = report.get("concept_today", {})
    html += section("📚 今日投資概念", "#d97706")
    html += f"""<table width='100%' cellpadding='0' cellspacing='0' style='border:1px solid #fde68a;border-radius:10px;overflow:hidden;'>
<tr><td style='background:linear-gradient(135deg,#78350f,#d97706);padding:14px 24px;'><div style='font-size:17px;font-weight:700;color:#fff;'>{concept.get('name','')}</div></td></tr>
<tr><td style='background:#fffbeb;padding:20px 24px;'>
  <table width='100%' cellpadding='0' cellspacing='0'>
  <tr><td style='padding:8px 0;border-bottom:1px solid #fde68a;'><div style='font-size:11px;color:#d97706;font-weight:700;margin-bottom:4px;'>📖 定義</div><div style='font-size:14px;color:#374151;line-height:1.7;'>{concept.get('definition','')}</div></td></tr>
  <tr><td style='padding:8px 0;border-bottom:1px solid #fde68a;'><div style='font-size:11px;color:#d97706;font-weight:700;margin-bottom:4px;'>❓ 為什麼重要</div><div style='font-size:14px;color:#374151;line-height:1.7;'>{concept.get('why_it_matters','')}</div></td></tr>
  <tr><td style='padding:8px 0;border-bottom:1px solid #fde68a;'><div style='font-size:11px;color:#d97706;font-weight:700;margin-bottom:4px;'>🎯 怎麼用</div><div style='font-size:14px;color:#374151;line-height:1.7;'>{concept.get('how_to_use','')}</div></td></tr>
  <tr><td style='padding:8px 0;border-bottom:1px solid #fde68a;'><div style='font-size:11px;color:#d97706;font-weight:700;margin-bottom:4px;'>💡 今日實例</div><div style='font-size:14px;color:#374151;line-height:1.7;'>{concept.get('todays_example','')}</div></td></tr>
  <tr><td style='padding:12px 0;'><div style='background:#fef3c7;border-radius:8px;padding:12px 16px;'><div style='font-size:12px;font-weight:700;color:#92400e;margin-bottom:4px;'>⭐ 今日重點</div><div style='font-size:15px;font-weight:600;color:#78350f;'>{concept.get('key_takeaway','')}</div></div></td></tr>
  </table>
</td></tr></table>"""

    # 昨日解答
    yesterday = report.get("yesterday_answer", {})
    if yesterday.get("answer"):
        html += section("✅ 昨日問題解答", "#059669")
        html += f"""<table width='100%' cellpadding='0' cellspacing='0' style='border:1px solid #d1fae5;border-radius:10px;overflow:hidden;'>
<tr><td style='background:#f0fdf4;padding:12px 20px;border-bottom:1px solid #d1fae5;'><div style='font-size:12px;color:#6b7280;margin-bottom:4px;'>昨日問題</div><div style='font-size:14px;font-weight:600;color:#374151;'>{yesterday.get('question','')}</div></td></tr>
<tr><td style='padding:16px 20px;'><div style='font-size:14px;color:#374151;line-height:1.7;margin-bottom:10px;'>{yesterday.get('answer','')}</div><div style='background:#eff6ff;border-radius:6px;padding:10px 14px;font-size:13px;color:#1e40af;'>🎓 學到的投資邏輯：{yesterday.get('lesson','')}</div></td></tr></table>"""

    # 今日提問
    todays_q = report.get("todays_question", {})
    html += section("🤔 今日思考題（明天解答）", "#dc2626")
    html += f"""<table width='100%' cellpadding='0' cellspacing='0' style='border:2px solid #fecaca;border-radius:10px;'>
<tr><td style='background:#fff1f2;padding:20px 24px;'>
  <div style='font-size:16px;font-weight:600;color:#991b1b;line-height:1.7;margin-bottom:12px;'>{todays_q.get('question','')}</div>
  <div style='font-size:13px;color:#b91c1c;'>💡 提示：{todays_q.get('hint','')}</div>
</td></tr></table>
<div style='font-size:12px;color:#9ca3af;text-align:center;margin-top:8px;'>想想看，明天的報告會公佈答案 🎯</div>"""

    # 進階區
    html += """<table width='100%' cellpadding='0' cellspacing='0' style='margin:32px 0 20px;'>
<tr><td style='border-top:2px dashed #e5e7eb;padding-top:20px;text-align:center;'>
  <span style='background:#f3f4f6;padding:4px 16px;font-size:13px;color:#6b7280;border-radius:20px;border:1px solid #e5e7eb;'>── 進階區（看不懂沒關係，慢慢會的）──</span>
</td></tr></table>"""

    html += section("🏭 今日產業分析", "#6366f1")

    # 輪換產業
    rotation = report.get("rotation_sector", {})
    html += _render_sector_block(rotation, "#4f46e5", "📅 今日輪換產業（系統性學習）", badge)

    # 熱點產業
    hot = report.get("hot_sector", {})
    html += _render_sector_block(hot, "#b45309", "🔥 今日市場熱點", badge)

    # Footer
    html += f"""
<table width='100%' cellpadding='0' cellspacing='0' style='border-top:1px solid #e5e7eb;margin-top:32px;padding-top:20px;'>
<tr><td style='text-align:center;font-size:12px;color:#9ca3af;line-height:2;'>
  本報告由 AI 輔助生成，僅供學習參考，不構成任何投資建議。<br>
  數據來源：Yahoo Finance · Anthropic Claude Sonnet · RSS 新聞<br>
  生成時間：{ts}
</td></tr></table>
</td></tr></table></td></tr></table></body></html>"""

    return html


# ══════════════════════════════════════════════════════════════════════════════
# 寄信
# ══════════════════════════════════════════════════════════════════════════════

def send_email(html_content: str, subject: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText("請使用支援 HTML 的郵件客戶端查看本日報。", "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_bytes())
    print(f"✅ Email sent → {RECIPIENT_EMAIL}")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    now_tw = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    print(f"🚀 Daily report starting at {now_tw.strftime('%Y-%m-%d %H:%M')} Taipei time")

    yesterday_question = load_yesterday_question()

    print("  [1/6] Fetching market data...")
    market_data = fetch_market_data()

    print("  [2/6] Fetching holdings data...")
    holdings_data = fetch_holdings_data()

    print("  [3/6] Fetching news...")
    news = fetch_news()

    print("  [4/6] Selecting rotation sector & concept...")
    rotation_sector_raw = select_today_rotation_sector()
    concept = select_today_concept()
    rotation_sector_data = {
        **rotation_sector_raw,
        "stocks": fetch_sector_stocks(rotation_sector_raw["tickers"])
    }
    print(f"        Rotation: {rotation_sector_raw['name']}, Concept: {concept[0]}")

    print("  [5/6] Detecting hot sector from news...")
    hot_sector_data = detect_hot_sector(news)
    print(f"        Hot sector: {hot_sector_data['name']}")

    print("  [6/6] Generating AI analysis...")
    report = generate_report(
        market_data, holdings_data, rotation_sector_data,
        hot_sector_data, news, concept, yesterday_question
    )

    todays_q = report.get("todays_question", {}).get("question", "")
    if todays_q:
        save_todays_question(todays_q)

    html     = build_html_email(report)
    date_str = now_tw.strftime("%Y/%m/%d")
    subject  = f"📊 投資日報 {date_str} ｜今日概念：{concept[0]}"

    send_email(html, subject)
    print("✅ Done.")


if __name__ == "__main__":
    main()
