#!/usr/bin/env python3
"""
Value Investing Daily Report — Investment Executive Briefing
One sector per day, rotating via day_of_year % 12 (no repeat within any 7-day window).
Depth: cycle position, drivers, risks, per-stock PE/PB/ROE/FCF vs history, Buy/Watch/Avoid.
"""

import os
import json
import html as _html_lib
import smtplib
import time
from collections import defaultdict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone

import requests
import anthropic

# ═══════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL    = os.environ["RECIPIENT_EMAIL"]
FINMIND_TOKEN      = os.environ.get("FINMIND_TOKEN", "")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
FINMIND_API = "https://api.finmindtrade.com/api/v4/data"

# ═══════════════════════════════════════════════════════════════════
# User Holdings
# ═══════════════════════════════════════════════════════════════════
HOLDINGS = {
    "3231": "緯創",
    "0050": "元大台灣50",
    "2618": "長榮航空",
}

# ═══════════════════════════════════════════════════════════════════
# 12 Sectors — index 0-11, rotated by day_of_year % 12
# No two days within any 7-day window share the same sector (period=12 > 7).
# ═══════════════════════════════════════════════════════════════════
ALL_SECTORS = [
    {
        "name": "半導體",
        "tickers": [
            {"id": "2330", "name": "台積電"},
            {"id": "2454", "name": "聯發科"},
            {"id": "2303", "name": "聯電"},
            {"id": "3711", "name": "日月光投控"},
            {"id": "2337", "name": "旺宏"},
        ],
    },
    {
        "name": "電子製造/ODM",
        "tickers": [
            {"id": "2317", "name": "鴻海"},
            {"id": "2382", "name": "廣達"},
            {"id": "2356", "name": "英業達"},
            {"id": "2353", "name": "宏碁"},
            {"id": "3231", "name": "緯創"},
        ],
    },
    {
        "name": "金融/銀行",
        "tickers": [
            {"id": "2882", "name": "國泰金"},
            {"id": "2881", "name": "富邦金"},
            {"id": "2886", "name": "兆豐金"},
            {"id": "2884", "name": "玉山金"},
            {"id": "2891", "name": "中信金"},
        ],
    },
    {
        "name": "航空/航運",
        "tickers": [
            {"id": "2618", "name": "長榮航"},
            {"id": "2610", "name": "華航"},
            {"id": "2603", "name": "長榮"},
            {"id": "2609", "name": "陽明"},
            {"id": "2615", "name": "萬海"},
        ],
    },
    {
        "name": "傳產/化工",
        "tickers": [
            {"id": "1301", "name": "台塑"},
            {"id": "1303", "name": "南亞"},
            {"id": "1326", "name": "台化"},
            {"id": "1314", "name": "中石化"},
            {"id": "1402", "name": "遠東新"},
        ],
    },
    {
        "name": "生技/醫療",
        "tickers": [
            {"id": "4711", "name": "中裕"},
            {"id": "6446", "name": "藥華藥"},
            {"id": "1786", "name": "科妍"},
            {"id": "4174", "name": "浩鼎"},
            {"id": "4168", "name": "醣聯"},
        ],
    },
    {
        "name": "零售/消費",
        "tickers": [
            {"id": "2912", "name": "統一超"},
            {"id": "2903", "name": "遠百"},
            {"id": "2207", "name": "和泰車"},
            {"id": "2915", "name": "潤泰全"},
            {"id": "9904", "name": "寶成"},
        ],
    },
    {
        "name": "營建/房地產",
        "tickers": [
            {"id": "5522", "name": "遠雄"},
            {"id": "2536", "name": "宏普"},
            {"id": "2504", "name": "國產"},
            {"id": "2515", "name": "中工"},
            {"id": "2545", "name": "皇翔"},
        ],
    },
    {
        "name": "鋼鐵/原物料",
        "tickers": [
            {"id": "2002", "name": "中鋼"},
            {"id": "2006", "name": "東和鋼鐵"},
            {"id": "2008", "name": "高興昌"},
            {"id": "1101", "name": "台灣水泥"},
            {"id": "1102", "name": "亞泥"},
        ],
    },
    {
        "name": "電信",
        "tickers": [
            {"id": "2412", "name": "中華電"},
            {"id": "4904", "name": "遠傳"},
            {"id": "3045", "name": "台灣大"},
            {"id": "4977", "name": "亞太電"},
        ],
    },
    {
        "name": "ETF/大盤",
        "tickers": [
            {"id": "0050", "name": "元大台灣50"},
            {"id": "0056", "name": "元大高股息"},
            {"id": "006208", "name": "富邦台50"},
            {"id": "00878", "name": "國泰永續高股息"},
            {"id": "00881", "name": "國泰台灣5G+"},
        ],
    },
    {
        "name": "科技軟體/雲端",
        "tickers": [
            {"id": "5274", "name": "信驊"},
            {"id": "6669", "name": "緯穎"},
            {"id": "3443", "name": "創意電子"},
            {"id": "8299", "name": "群聯電子"},
            {"id": "6770", "name": "力積電"},
        ],
    },
]


# ═══════════════════════════════════════════════════════════════════
# FinMind API Helpers
# ═══════════════════════════════════════════════════════════════════

def _finmind_get(dataset: str, data_id: str, start_date: str) -> list:
    """Call FinMind v4 API; return data list or [] on any error."""
    if not FINMIND_TOKEN:
        return []
    try:
        resp = requests.get(
            FINMIND_API,
            params={
                "dataset": dataset,
                "data_id": data_id,
                "start_date": start_date,
                "token": FINMIND_TOKEN,
            },
            timeout=20,
        )
        resp.raise_for_status()
        j = resp.json()
        if j.get("status") == 200:
            return j.get("data", [])
        print(f"  FinMind [{dataset}] {data_id}: {j.get('msg', 'no msg')}")
        return []
    except Exception as exc:
        print(f"  FinMind error [{dataset}] {data_id}: {exc}")
        return []


def _safe_float(val, decimals: int = 1):
    """Parse float, round, return None on failure or zero."""
    try:
        f = float(val)
        return round(f, decimals) if f != 0 else None
    except (TypeError, ValueError):
        return None


def _latest_by_date(items: list, value_key: str = "value"):
    """Return value from the most recent record in a list, or None."""
    if not items:
        return None
    rec = sorted(items, key=lambda x: x.get("date", ""))[-1]
    return rec.get(value_key)


def fetch_stock_fundamentals(ticker_id: str, ticker_name: str) -> dict:
    """
    Fetch PE, PB, EPS, ROE, debt_ratio, operating_cf, capex for one Taiwan stock.
    All fields may be None if unavailable — caller and Claude handle gracefully.
    """
    result = {
        "id": ticker_id,
        "name": ticker_name,
        "pe": None,
        "pb": None,
        "eps": None,
        "roe": None,
        "debt_ratio": None,
        "operating_cf_bn": None,   # operating cash flow, billions TWD
        "capex_bn": None,           # capex (absolute value), billions TWD
        "fcf_bn": None,             # FCF = op_cf - capex, billions TWD
    }

    today = datetime.now()
    start_30  = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    start_400 = (today - timedelta(days=400)).strftime("%Y-%m-%d")

    # ── 1. P/E and P/B ───────────────────────────────────────────────
    per_data = _finmind_get("TaiwanStockPER", ticker_id, start_30)
    if per_data:
        latest = sorted(per_data, key=lambda x: x.get("date", ""))[-1]
        result["pe"] = _safe_float(latest.get("PER"), 1)
        result["pb"] = _safe_float(latest.get("PBR"), 2)
    time.sleep(0.4)

    # ── 2. EPS and ROE ────────────────────────────────────────────────
    fin_data = _finmind_get("TaiwanStockFinancialStatements", ticker_id, start_400)
    if fin_data:
        by_type: dict = defaultdict(list)
        for item in fin_data:
            by_type[item.get("type", "")].append(item)

        for key in ("EPS", "eps", "BasicEPS"):
            v = _latest_by_date(by_type.get(key, []))
            if v is not None:
                result["eps"] = _safe_float(v, 2)
                break

        for key in ("ROE", "roe"):
            v = _latest_by_date(by_type.get(key, []))
            if v is not None:
                fv = _safe_float(v, 4)
                if fv is not None:
                    # Normalise: FinMind sometimes stores as decimal (0.28), sometimes %
                    result["roe"] = round(fv if abs(fv) > 1 else fv * 100, 1)
                break
    time.sleep(0.4)

    # ── 3. Debt ratio from balance sheet ─────────────────────────────
    bal_data = _finmind_get("TaiwanStockBalanceSheet", ticker_id, start_400)
    if bal_data:
        dates = sorted({d.get("date", "") for d in bal_data}, reverse=True)
        if dates:
            items = [d for d in bal_data if d.get("date") == dates[0]]
            total_assets = total_liab = None
            for item in items:
                t = item.get("type", "")
                v = _safe_float(item.get("value"), 0)
                if v is None:
                    continue
                if t in ("TotalAssets", "Assets"):
                    total_assets = v
                elif t in ("TotalLiabilities", "Liabilities"):
                    total_liab = v
            if total_assets and total_liab and total_assets > 0:
                result["debt_ratio"] = round(total_liab / total_assets * 100, 1)
    time.sleep(0.4)

    # ── 4. Free Cash Flow from cash flow statement ────────────────────
    cf_data = _finmind_get("TaiwanStockCashFlowsStatement", ticker_id, start_400)
    if cf_data:
        by_type_cf: dict = defaultdict(list)
        for item in cf_data:
            by_type_cf[item.get("type", "")].append(item)

        op_cf_raw = None
        for key in ("OperatingActivities", "CashFlowFromOperatingActivities",
                    "NetCashProvidedByUsedInOperatingActivities"):
            v = _latest_by_date(by_type_cf.get(key, []))
            if v is not None:
                op_cf_raw = _safe_float(v, 0)
                break

        capex_raw = None
        for key in ("PurchaseOfPropertyPlantAndEquipment",
                    "AcquisitionOfPropertyPlantAndEquipment",
                    "CapitalExpenditures"):
            v = _latest_by_date(by_type_cf.get(key, []))
            if v is not None:
                capex_raw = _safe_float(v, 0)
                break

        if op_cf_raw is not None:
            result["operating_cf_bn"] = round(op_cf_raw / 1e9, 1)
        if capex_raw is not None:
            result["capex_bn"] = round(abs(capex_raw) / 1e9, 1)
        if op_cf_raw is not None and capex_raw is not None:
            result["fcf_bn"] = round((op_cf_raw - abs(capex_raw)) / 1e9, 1)
        elif op_cf_raw is not None:
            result["fcf_bn"] = round(op_cf_raw / 1e9, 1)
    time.sleep(0.4)

    return result


# ═══════════════════════════════════════════════════════════════════
# Sector Selection & Holdings
# ═══════════════════════════════════════════════════════════════════

def select_daily_sector() -> dict:
    """
    Return today's single sector.
    Formula: day_of_year % 12 → index 0-11.
    Any 7 consecutive days always land on 7 distinct sectors (period=12 > 7).
    """
    day_of_year = datetime.now().timetuple().tm_yday
    return ALL_SECTORS[day_of_year % 12]


def get_sector_holdings(sector: dict) -> list:
    """Return user holdings (id, name) that appear in this sector's ticker list."""
    ticker_ids = {t["id"] for t in sector["tickers"]}
    return [
        {"id": hid, "name": hname}
        for hid, hname in HOLDINGS.items()
        if hid in ticker_ids
    ]


def fetch_sector_data(sector: dict) -> dict:
    """Fetch FinMind fundamentals for all tickers in the sector."""
    companies = []
    for ticker in sector["tickers"]:
        print(f"    [{sector['name']}] {ticker['id']} {ticker['name']}")
        companies.append(fetch_stock_fundamentals(ticker["id"], ticker["name"]))
    return {
        "name": sector["name"],
        "companies": companies,
        "holdings": get_sector_holdings(sector),
    }


# ═══════════════════════════════════════════════════════════════════
# Claude AI — Investment Executive Briefing
# ═══════════════════════════════════════════════════════════════════

def _try_parse_json(raw: str) -> dict | None:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    for suffix in ["}", "}}", "}}", "}]}", "}]}}", "}]}}}"]:
        try:
            return json.loads(raw + suffix)
        except json.JSONDecodeError:
            continue
    last = raw.rfind("}")
    if last > 0:
        try:
            return json.loads(raw[: last + 1])
        except json.JSONDecodeError:
            pass
    return None


_MACRO_RULES = """
【總經邏輯強制規則 — 違反者寧可不寫，勿寫錯】
1. 台幣升值 → 出口商以美元計價的收入換回台幣變少，獲利被壓縮，競爭力下降；對進口商（原料成本降低）有利。
2. 升息（Fed 或央行） → 折現率上升，未來現金流現值縮水；對高本益比/高負債/長存續期成長股傷害最大；銀行淨利差短期可能受益，但若景氣衰退風險升高則反轉。
3. 降息 → 資金成本降低，利好高負債企業與成長股；但若因景氣走弱被迫降息，需區分「預防性降息」與「衰退式降息」，後者對企業盈利仍是負面訊號。
4. 利率倒掛（短率 > 長率） → 歷史上衰退前兆，需明確說明此邏輯，不得把倒掛解讀為「長率下跌因此有利股市」。
5. 原物料漲價 → 上游廠商受益；下游製造業（如電子/汽車）原料成本上升，利潤被壓縮。
6. 油價上漲 → 對航空業（燃油成本佔比高）、航運（船燃費用上升）、化工（石化原料成本上升）為負面；對能源類個股為正面。
7. 通膨 → 央行傾向升息壓通膨（見規則 2）；實質購買力下降對消費類零售有壓力。
8. 景氣下行 → 循環股（鋼鐵、航運、半導體設備）獲利受創明顯；防禦型（電信、公用事業、民生必需品）相對抗跌。
如不確定某個總經關聯，直接省略，勿臆測。
"""


def generate_report(sector_data: dict) -> dict:
    """Send one sector's fundamentals to Claude; receive investment executive briefing JSON."""
    today = datetime.now().strftime("%Y年%m月%d日")
    sname = sector_data["name"]

    holdings = sector_data.get("holdings", [])
    holdings_ctx = (
        "、".join(f"{h['name']}({h['id']})" for h in holdings)
        if holdings else "本日產業無持有個股"
    )

    data_json = json.dumps(sector_data["companies"], ensure_ascii=False, indent=2)

    prompt = f"""
你是台灣市場首席投資主管，今天是 {today}，請針對「{sname}」產業撰寫投資主管簡報。
報告對象是有經驗的投資人，要求：資訊密度高、邏輯嚴謹、觀點明確、不說廢話。

{_MACRO_RULES}

【今日 FinMind 基本面數據】
欄位：pe=本益比、pb=股價淨值比、eps=每股盈餘(TWD)、roe=股東權益報酬率(%)、
      debt_ratio=負債比率(%)、operating_cf_bn=營業現金流(十億TWD)、
      capex_bn=資本支出(十億TWD)、fcf_bn=自由現金流(十億TWD)
null = API 暫無資料，請根據你的知識補充或說明。

{data_json}

【用戶持有個股】
{holdings_ctx}

請嚴格輸出以下 JSON，不含任何 markdown 標記或額外文字：

{{
  "report_date": "{today}",
  "sector": {{
    "name": "{sname}",
    "intro": "產業定位與主要商業模式，2-3句（60-90字）",
    "cycle_position": {{
      "stage": "復甦期|成長期|高峰期|衰退期|底部期",
      "description": "目前週期位置與判斷依據，引用具體數據或事件（80-120字）"
    }},
    "drivers": [
      {{"title": "驅動因子名稱（5-10字）", "detail": "具體說明（40-60字）"}},
      {{"title": "...", "detail": "..."}},
      {{"title": "...", "detail": "..."}}
    ],
    "risks": [
      {{"title": "風險名稱（5-10字）", "detail": "具體說明，含邏輯鏈（40-60字）"}},
      {{"title": "...", "detail": "..."}},
      {{"title": "...", "detail": "..."}}
    ],
    "companies": [
      {{
        "id": "股票代號",
        "name": "公司名稱",
        "pe_comment": "當前PE是否高於/低於其歷史均值，高估或低估的判斷（40-60字）",
        "pb_comment": "PB相對淨值的評估（30-50字）",
        "roe_comment": "ROE水準，與同業或自身歷史比較（30-50字）",
        "fcf_comment": "自由現金流狀況，能否支撐股息/回購/成長投資（40-60字）",
        "verdict": "買入|觀望|避開",
        "verdict_reason": "明確理由，含估值依據與關鍵催化劑或風險（60-80字）"
      }}
    ],
    "macro_context": "當前總經環境對本產業的具體影響，邏輯必須正確；不確定則省略此段改為空字串（60-80字）",
    "sector_verdict": "整體產業建議（買入/觀望/避開）及核心理由（80-100字）",
    "holdings_analysis": null
  }}
}}

若用戶持有個股出現在本日產業，holdings_analysis 填入（否則保留 null）：
{{
  "ticker": "代號",
  "name": "名稱",
  "analysis": "持有者專屬分析：目前估值合理性、與買入理由的符合程度、需要警覺的風險訊號、建議持續持有/加碼/減碼的理由（150-200字）"
}}
"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=5120,
        temperature=0.5,   # lower temperature for more consistent factual logic
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    parsed = _try_parse_json(raw)
    if parsed is not None:
        return parsed

    print(f"JSON parse failed. Raw (first 500 chars): {raw[:500]}")
    return {"_fallback_raw": raw, "report_date": today}


# ═══════════════════════════════════════════════════════════════════
# HTML Email Builder — Executive Briefing Style
# ═══════════════════════════════════════════════════════════════════

def _esc(s) -> str:
    return _html_lib.escape(str(s)) if s else ""


def _val(v, suffix="", fallback="N/A") -> str:
    return f"{v}{suffix}" if v is not None else f"<span style='color:#9ca3af;'>{fallback}</span>"


def _build_fallback_html(raw_text: str, date_str: str) -> str:
    escaped = _html_lib.escape(raw_text)
    paras = "".join(
        f"<p style='margin:0 0 12px;line-height:1.8;'>{line}</p>" if line.strip() else "<br>"
        for line in escaped.splitlines()
    )
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!DOCTYPE html><html lang="zh-TW"><head><meta charset="UTF-8">
<title>投資主管日報 {date_str}</title></head>
<body style="margin:0;padding:0;background:#f3f4f6;
             font-family:'Helvetica Neue',Arial,'PingFang TC',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;">
<tr><td align="center" style="padding:20px 16px;">
<table width="680" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:12px;overflow:hidden;
              box-shadow:0 2px 16px rgba(0,0,0,0.1);">
<tr><td style="background:#1e3a5f;padding:32px 40px;text-align:center;">
  <div style="font-size:26px;font-weight:700;color:#fff;">📋 投資主管日報</div>
  <div style="font-size:14px;color:#bfdbfe;margin-top:6px;">{date_str}</div>
</td></tr>
<tr><td style="padding:32px 40px;font-size:14px;color:#374151;">{paras}</td></tr>
<tr><td style="padding:16px 40px;text-align:center;font-size:12px;color:#9ca3af;
               border-top:1px solid #e5e7eb;">
  本報告由 AI 輔助生成，僅供學習參考，不構成投資建議。生成時間：{ts}
</td></tr>
</table></td></tr></table></body></html>"""


VERDICT_STYLE = {
    "買入": ("background:#dcfce7;color:#15803d;border:1px solid #86efac;", "▲ 買入"),
    "觀望": ("background:#fef9c3;color:#854d0e;border:1px solid #fde047;", "◎ 觀望"),
    "避開": ("background:#fee2e2;color:#b91c1c;border:1px solid #fca5a5;", "▼ 避開"),
}
CYCLE_STYLE = {
    "復甦期": ("#0ea5e9", "🌱"),
    "成長期": ("#22c55e", "📈"),
    "高峰期": ("#f59e0b", "🔝"),
    "衰退期": ("#ef4444", "📉"),
    "底部期": ("#8b5cf6", "🔵"),
}


def _verdict_badge(verdict: str) -> str:
    style, label = VERDICT_STYLE.get(verdict, ("background:#e5e7eb;color:#374151;", verdict or "N/A"))
    return (
        f"<span style='display:inline-block;font-size:12px;font-weight:700;"
        f"padding:3px 12px;border-radius:20px;{style}'>{label}</span>"
    )


def _fundamentals_table(companies: list) -> str:
    rows = ""
    for i, co in enumerate(companies):
        is_holding = co["id"] in HOLDINGS
        bg = "#f8fafc" if i % 2 == 0 else "#ffffff"
        name_extra = (
            " <span style='font-size:10px;background:#dcfce7;color:#15803d;"
            "padding:1px 5px;border-radius:4px;font-weight:600;'>持有</span>"
            if is_holding else ""
        )
        rows += f"""<tr style="background:{bg};border-top:1px solid #f1f5f9;">
  <td style="padding:9px 12px;font-size:13px;color:#1e3a5f;font-weight:600;white-space:nowrap;">
    {_esc(co['name'])}{name_extra}<br>
    <span style="font-size:11px;color:#9ca3af;font-weight:400;">{_esc(co['id'])}</span>
  </td>
  <td style="padding:9px 12px;font-size:13px;text-align:right;">{_val(co.get('pe'),'x')}</td>
  <td style="padding:9px 12px;font-size:13px;text-align:right;">{_val(co.get('pb'),'x')}</td>
  <td style="padding:9px 12px;font-size:13px;text-align:right;">{_val(co.get('roe'),'%')}</td>
  <td style="padding:9px 12px;font-size:13px;text-align:right;">{_val(co.get('debt_ratio'),'%')}</td>
  <td style="padding:9px 12px;font-size:13px;text-align:right;">{_val(co.get('eps'))}</td>
  <td style="padding:9px 12px;font-size:13px;text-align:right;">{_val(co.get('fcf_bn'),'B')}</td>
</tr>"""
    return f"""<table width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;font-size:13px;margin-bottom:20px;
              border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
  <tr style="background:#1e3a5f;">
    <td style="padding:9px 12px;color:#93c5fd;font-size:11px;font-weight:700;
               letter-spacing:.5px;text-transform:uppercase;">公司</td>
    <td style="padding:9px 12px;color:#93c5fd;font-size:11px;font-weight:700;text-align:right;">P/E</td>
    <td style="padding:9px 12px;color:#93c5fd;font-size:11px;font-weight:700;text-align:right;">P/B</td>
    <td style="padding:9px 12px;color:#93c5fd;font-size:11px;font-weight:700;text-align:right;">ROE%</td>
    <td style="padding:9px 12px;color:#93c5fd;font-size:11px;font-weight:700;text-align:right;">負債%</td>
    <td style="padding:9px 12px;color:#93c5fd;font-size:11px;font-weight:700;text-align:right;">EPS</td>
    <td style="padding:9px 12px;color:#93c5fd;font-size:11px;font-weight:700;text-align:right;">FCF(B)</td>
  </tr>
  {rows}
</table>"""


def _driver_risk_section(items: list, is_driver: bool) -> str:
    if not items:
        return ""
    color = "#0369a1" if is_driver else "#dc2626"
    bg    = "#f0f9ff" if is_driver else "#fef2f2"
    border= "#bae6fd" if is_driver else "#fecaca"
    icon  = "▸" if is_driver else "⚠"
    label = "主要驅動因子" if is_driver else "主要風險"
    rows  = ""
    for item in items:
        title  = _esc(item.get("title", ""))
        detail = _esc(item.get("detail", ""))
        rows += (
            f"<tr><td style='padding:8px 0;border-top:1px solid {border};'>"
            f"<span style='font-size:12px;font-weight:700;color:{color};'>"
            f"{icon} {title}</span>"
            f"<div style='font-size:13px;color:#374151;line-height:1.7;margin-top:3px;'>"
            f"{detail}</div></td></tr>"
        )
    return f"""<table width="100%" cellpadding="0" cellspacing="0"
       style="background:{bg};border:1px solid {border};border-radius:8px;
              padding:14px 18px;margin-bottom:12px;">
<tr><td>
  <div style="font-size:11px;font-weight:700;color:{color};letter-spacing:1px;
              text-transform:uppercase;margin-bottom:8px;">{label}</div>
  <table width="100%" cellpadding="0" cellspacing="0">{rows}</table>
</td></tr>
</table>"""


def _company_card(co_data: dict, ai: dict) -> str:
    """Combine raw FinMind data row with Claude's per-stock analysis."""
    is_holding = ai.get("id", "") in HOLDINGS
    verdict = ai.get("verdict", "")
    badge = _verdict_badge(verdict)
    border_color = {"買入": "#86efac", "觀望": "#fde047", "避開": "#fca5a5"}.get(verdict, "#e5e7eb")

    holding_tag = (
        "<span style='font-size:10px;background:#dcfce7;color:#15803d;"
        "padding:1px 6px;border-radius:4px;margin-left:6px;font-weight:600;'>持有</span>"
        if is_holding else ""
    )

    def _row(label, content):
        return (
            f"<tr><td style='padding:6px 0;border-top:1px solid #f3f4f6;'>"
            f"<span style='font-size:11px;font-weight:700;color:#6b7280;text-transform:uppercase;"
            f"letter-spacing:.5px;'>{label}</span>"
            f"<div style='font-size:13px;color:#374151;line-height:1.7;margin-top:2px;'>"
            f"{_esc(content)}</div></td></tr>"
        )

    return f"""<table width="100%" cellpadding="0" cellspacing="0"
       style="border:1px solid {border_color};border-radius:8px;
              margin-bottom:12px;overflow:hidden;">
  <tr><td style="background:#f8fafc;padding:12px 16px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td>
          <span style="font-size:15px;font-weight:700;color:#1e3a5f;">
            {_esc(ai.get('name',''))}
          </span>
          <span style="font-size:12px;color:#9ca3af;margin-left:6px;">
            {_esc(ai.get('id',''))}
          </span>{holding_tag}
        </td>
        <td align="right">{badge}</td>
      </tr>
    </table>
  </td></tr>
  <tr><td style="padding:12px 16px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      {_row("本益比 (P/E)", ai.get("pe_comment",""))}
      {_row("淨值比 (P/B)", ai.get("pb_comment",""))}
      {_row("股東權益報酬率 (ROE)", ai.get("roe_comment",""))}
      {_row("自由現金流 (FCF)", ai.get("fcf_comment",""))}
      <tr><td style="padding:10px 0 0;border-top:1px solid #e5e7eb;">
        <span style="font-size:11px;font-weight:700;color:#374151;text-transform:uppercase;
                     letter-spacing:.5px;">建議理由</span>
        <div style="font-size:13px;color:#374151;line-height:1.7;margin-top:4px;">
          {_esc(ai.get("verdict_reason",""))}
        </div>
      </td></tr>
    </table>
  </td></tr>
</table>"""


def build_html_email(report: dict, sector_data: dict) -> str:
    if "_fallback_raw" in report:
        return _build_fallback_html(report["_fallback_raw"], report.get("report_date", ""))

    date_str = report.get("report_date", datetime.now().strftime("%Y年%m月%d日"))
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    s = report.get("sector", {})
    sname = _esc(s.get("name", ""))

    # Cycle badge
    stage = s.get("cycle_position", {}).get("stage", "")
    cycle_color, cycle_icon = CYCLE_STYLE.get(stage, ("#6b7280", "●"))
    cycle_badge = (
        f"<span style='display:inline-block;background:{cycle_color};color:#fff;"
        f"font-size:11px;font-weight:700;padding:2px 10px;border-radius:20px;"
        f"margin-left:10px;'>{cycle_icon} {_esc(stage)}</span>"
        if stage else ""
    )

    # Overall sector verdict
    sector_verdict_text = s.get("sector_verdict", "")
    sv_badge = ""
    for kw in ("買入", "觀望", "避開"):
        if kw in sector_verdict_text:
            sv_badge = _verdict_badge(kw)
            break

    # Macro context (only render if non-empty)
    macro = s.get("macro_context", "").strip()
    macro_block = ""
    if macro:
        macro_block = f"""
<table width="100%" cellpadding="0" cellspacing="0"
       style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;
              margin-bottom:20px;">
<tr><td style="padding:14px 18px;">
  <div style="font-size:11px;font-weight:700;color:#15803d;letter-spacing:1px;
              text-transform:uppercase;margin-bottom:8px;">🌐 總經環境影響</div>
  <div style="font-size:13px;color:#374151;line-height:1.8;">{_esc(macro)}</div>
</td></tr>
</table>"""

    # Holdings analysis block
    ha = s.get("holdings_analysis")
    holdings_block = ""
    if ha and isinstance(ha, dict) and ha.get("analysis"):
        holdings_block = f"""
<table width="100%" cellpadding="0" cellspacing="0"
       style="background:#fefce8;border:1px solid #fde047;border-radius:8px;
              margin-bottom:20px;">
<tr><td style="padding:16px 20px;">
  <div style="font-size:13px;font-weight:700;color:#854d0e;margin-bottom:10px;">
    📌 持有個股專屬分析：{_esc(ha.get('name',''))} ({_esc(ha.get('ticker',''))})
  </div>
  <div style="font-size:13px;color:#374151;line-height:1.8;">{_esc(ha.get('analysis',''))}</div>
</td></tr>
</table>"""

    # Per-company cards: zip AI output with raw FinMind data for table
    companies_raw = sector_data.get("companies", [])
    companies_ai  = s.get("companies", [])
    # Align by id in case order differs
    raw_map = {c["id"]: c for c in companies_raw}
    ai_map  = {c.get("id", ""): c for c in companies_ai}
    all_ids = [c["id"] for c in companies_raw]

    company_cards = ""
    for cid in all_ids:
        ai_entry = ai_map.get(cid, {"id": cid, "name": raw_map.get(cid, {}).get("name", cid)})
        company_cards += _company_card(raw_map.get(cid, {}), ai_entry)

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>投資主管日報 {date_str}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;
             font-family:'Helvetica Neue',Arial,'PingFang TC','Microsoft JhengHei',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;">
<tr><td align="center" style="padding:20px 16px;">
<table width="680" cellpadding="0" cellspacing="0"
       style="background:#ffffff;border-radius:14px;overflow:hidden;
              box-shadow:0 4px 24px rgba(0,0,0,0.1);">

<!-- ══ HEADER ══ -->
<tr><td style="background:linear-gradient(135deg,#0f2444 0%,#1e3a5f 60%,#2563eb 100%);
               padding:28px 40px;">
  <div style="font-size:10px;color:#93c5fd;letter-spacing:3px;text-transform:uppercase;
              margin-bottom:6px;">INVESTMENT EXECUTIVE BRIEFING</div>
  <div style="font-size:26px;font-weight:800;color:#ffffff;letter-spacing:-0.5px;">
    📋 投資主管日報
  </div>
  <div style="font-size:13px;color:#bfdbfe;margin-top:6px;">
    {date_str} &nbsp;·&nbsp; 每日 23:00 UTC 自動發送
  </div>
</td></tr>

<!-- ══ SECTOR TITLE ══ -->
<tr><td style="background:#f8fafc;padding:20px 40px;border-bottom:1px solid #e2e8f0;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td>
        <div style="font-size:11px;color:#64748b;text-transform:uppercase;
                    letter-spacing:1.5px;margin-bottom:4px;">今日產業</div>
        <div style="font-size:22px;font-weight:800;color:#0f172a;">
          🏭 {sname}{cycle_badge}
        </div>
      </td>
      <td align="right" style="vertical-align:bottom;">
        <div style="font-size:11px;color:#64748b;margin-bottom:4px;text-align:right;">
          整體建議
        </div>
        {sv_badge}
      </td>
    </tr>
  </table>
</td></tr>

<!-- ══ BODY ══ -->
<tr><td style="padding:28px 40px;">

  <!-- Intro -->
  <div style="font-size:14px;color:#374151;line-height:1.8;margin-bottom:20px;
              padding:16px 20px;background:#f8fafc;border-left:4px solid #2563eb;
              border-radius:0 8px 8px 0;">
    {_esc(s.get("intro",""))}
  </div>

  <!-- Cycle position -->
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;
                margin-bottom:20px;">
  <tr><td style="padding:14px 18px;">
    <div style="font-size:11px;font-weight:700;color:{cycle_color};letter-spacing:1px;
                text-transform:uppercase;margin-bottom:6px;">
      {cycle_icon} 週期位置 — {_esc(stage)}
    </div>
    <div style="font-size:13px;color:#374151;line-height:1.8;">
      {_esc(s.get("cycle_position",{}).get("description",""))}
    </div>
  </td></tr>
  </table>

  <!-- Drivers & Risks (side by side intent; email-safe stacked) -->
  {_driver_risk_section(s.get("drivers", []), is_driver=True)}
  {_driver_risk_section(s.get("risks", []), is_driver=False)}

  <!-- Fundamentals Table -->
  <div style="font-size:11px;font-weight:700;color:#374151;text-transform:uppercase;
              letter-spacing:1px;margin-bottom:8px;">📊 基本面數據（FinMind）</div>
  {_fundamentals_table(companies_raw)}

  <!-- Per-stock deep analysis -->
  <div style="font-size:11px;font-weight:700;color:#374151;text-transform:uppercase;
              letter-spacing:1px;margin-bottom:12px;">🔍 個股深度評估</div>
  {company_cards}

  <!-- Macro context -->
  {macro_block}

  <!-- Overall sector verdict -->
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#0f172a;border-radius:8px;margin-bottom:20px;">
  <tr><td style="padding:18px 22px;">
    <div style="font-size:11px;font-weight:700;color:#93c5fd;letter-spacing:1px;
                text-transform:uppercase;margin-bottom:8px;">
      💼 產業整體建議
    </div>
    <div style="font-size:14px;color:#e2e8f0;line-height:1.8;">
      {_esc(sector_verdict_text)}
    </div>
  </td></tr>
  </table>

  <!-- Holdings analysis -->
  {holdings_block}

  <!-- Footer -->
  <table width="100%" cellpadding="0" cellspacing="0"
         style="border-top:1px solid #e2e8f0;padding-top:18px;margin-top:8px;">
  <tr><td style="text-align:center;font-size:11px;color:#9ca3af;line-height:2.2;">
    本報告由 AI 輔助生成，僅供學習參考，不構成任何投資建議。<br>
    數據來源：FinMind API · Anthropic Claude Haiku &nbsp;|&nbsp; 生成時間：{ts}
  </td></tr>
  </table>

</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""

    return html


# ═══════════════════════════════════════════════════════════════════
# Email Sender
# ═══════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

def main():
    print(f"🚀 Daily report starting at {datetime.now(timezone.utc).isoformat()}")

    print("  [1/4] Selecting today's sector...")
    sector = select_daily_sector()
    day_of_year = datetime.now().timetuple().tm_yday
    print(f"        Day {day_of_year} (mod 12 = {day_of_year % 12}) → {sector['name']}")

    print("  [2/4] Fetching FinMind fundamentals...")
    sector_data = fetch_sector_data(sector)

    print("  [3/4] Generating executive briefing (Claude Haiku)...")
    report = generate_report(sector_data)

    print("  [4/4] Building HTML and sending email...")
    html = build_html_email(report, sector_data)

    date_str = datetime.now().strftime("%Y/%m/%d")
    subject  = f"📋 投資主管日報 | {date_str} | {sector['name']}"
    send_email(html, subject)
    print("✅ Done.")


if __name__ == "__main__":
    main()
