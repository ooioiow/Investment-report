#!/usr/bin/env python3
"""
Value Investing Daily Report - Taiwan Market Industry Rotation
Runs every day at 23:00 UTC via GitHub Actions.
Each day rotates through 2 of 12 industries; includes fundamentals from FinMind API.
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
# User Holdings  (ticker_id → display_name)
# ═══════════════════════════════════════════════════════════════════
HOLDINGS = {
    "3231": "緯創",
    "0050": "元大台灣50",
    "2618": "長榮航空",
}

# ═══════════════════════════════════════════════════════════════════
# 12 Industry Sectors with 3-5 representative Taiwan listed companies
# Order index 0-11 maps to the rotation schedule.
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
    """Parse float and round; return None on failure or non-positive."""
    try:
        f = float(val)
        if f == 0:
            return None
        return round(f, decimals)
    except (TypeError, ValueError):
        return None


def fetch_stock_fundamentals(ticker_id: str, ticker_name: str) -> dict:
    """
    Fetch PE, PB, EPS, ROE, debt_ratio from FinMind for one Taiwan stock.
    All five fields may be None if unavailable.
    """
    result = {
        "id": ticker_id,
        "name": ticker_name,
        "pe": None,
        "pb": None,
        "eps": None,
        "roe": None,
        "debt_ratio": None,
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

    # ── 2. EPS and ROE from quarterly financial statements ────────────
    fin_data = _finmind_get("TaiwanStockFinancialStatements", ticker_id, start_400)
    if fin_data:
        by_type: dict[str, list] = defaultdict(list)
        for item in fin_data:
            by_type[item.get("type", "")].append(item)

        # EPS
        for key in ("EPS", "eps", "BasicEPS"):
            items = sorted(by_type.get(key, []), key=lambda x: x.get("date", ""))
            if items:
                result["eps"] = _safe_float(items[-1].get("value"), 2)
                break

        # ROE – might be stored as decimal (0.28) or percentage (28.0)
        for key in ("ROE", "roe"):
            items = sorted(by_type.get(key, []), key=lambda x: x.get("date", ""))
            if items:
                v = _safe_float(items[-1].get("value"), 4)
                if v is not None:
                    result["roe"] = round(v if abs(v) > 1 else v * 100, 1)
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
                if t in ("TotalAssets", "Assets", "asset"):
                    total_assets = v
                elif t in ("TotalLiabilities", "Liabilities", "liability"):
                    total_liab = v
            if total_assets and total_liab and total_assets > 0:
                result["debt_ratio"] = round(total_liab / total_assets * 100, 1)
    time.sleep(0.4)

    return result


# ═══════════════════════════════════════════════════════════════════
# Sector Selection & Holdings Detection
# ═══════════════════════════════════════════════════════════════════

def select_daily_sectors() -> list:
    """Return today's 2 sectors using (day_of_year // 2) % 12 as start index."""
    day_of_year = datetime.now().timetuple().tm_yday
    start = (day_of_year // 2) % 12
    s1 = ALL_SECTORS[start]
    s2 = ALL_SECTORS[(start + 1) % 12]
    return [s1, s2]


def get_sector_holdings(sector: dict) -> list:
    """Return user holdings (id, name) that appear in this sector's ticker list."""
    ticker_ids = {t["id"] for t in sector["tickers"]}
    return [
        {"id": hid, "name": hname}
        for hid, hname in HOLDINGS.items()
        if hid in ticker_ids
    ]


def fetch_sectors_data(sectors: list) -> list:
    """Fetch FinMind fundamentals for all tickers in both sectors."""
    results = []
    for sector in sectors:
        companies = []
        for ticker in sector["tickers"]:
            print(f"    [{sector['name']}] fetching {ticker['id']} {ticker['name']}")
            data = fetch_stock_fundamentals(ticker["id"], ticker["name"])
            companies.append(data)
        results.append({
            "name": sector["name"],
            "companies": companies,
            "holdings": get_sector_holdings(sector),
        })
    return results


# ═══════════════════════════════════════════════════════════════════
# Claude AI Analysis
# ═══════════════════════════════════════════════════════════════════

def _try_parse_json(raw: str) -> dict | None:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    for suffix in ["}", "}}", "}]}", "}]}}", "}]}}}"]:
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


def generate_report(sectors_data: list) -> dict:
    """Send sector fundamentals to Claude and get structured JSON analysis."""
    today = datetime.now().strftime("%Y年%m月%d日")

    # Build holdings context string for the prompt
    holdings_lines = []
    for sd in sectors_data:
        if sd["holdings"]:
            names = "、".join(f"{h['name']}({h['id']})" for h in sd["holdings"])
            holdings_lines.append(f"- {sd['name']}：{names}")
    holdings_ctx = "\n".join(holdings_lines) if holdings_lines else "今日產業無持有個股"

    data_json = json.dumps(sectors_data, ensure_ascii=False, indent=2)

    prompt = f"""
你是專業的價值投資分析師，擅長台灣股市基本面研究。
今天是 {today}。請根據以下兩個產業的基本面數據，用**繁體中文**生成產業學習日報分析。

【今日兩個產業數據（來自 FinMind API）】
欄位說明：pe=本益比, pb=股價淨值比, eps=每股盈餘, roe=股東權益報酬率(%), debt_ratio=負債比率(%)
null 表示 API 資料暫時無法取得，請根據你的知識補充估算或說明。

{data_json}

【用戶持有個股（若出現在今日產業中，需額外加入持有個股分析）】
{holdings_ctx}

請嚴格輸出以下 JSON 結構，不含任何 markdown 標記或額外文字：

{{
  "report_date": "{today}",
  "sectors": [
    {{
      "name": "產業名稱",
      "intro": "產業簡介，2-3句說明商業模式與主要獲利驅動力（60-90字）",
      "commentary": {{
        "valuation_level": "目前整體估值水位評估，結合PE/PB數據說明（50-80字）",
        "key_metrics": "價值投資者應重點觀察的指標與原因（50-80字）",
        "value_perspective": "從巴菲特式價值投資角度的整體觀察與建議（80-100字）"
      }},
      "holdings_analysis": null
    }}
  ]
}}

若某產業有用戶持有個股，請將該產業的 holdings_analysis 填入（不要留 null）：
{{
  "ticker": "股票代號",
  "name": "公司名稱",
  "analysis": "針對持有者的深度分析：目前估值是否合理、長期競爭優勢、需注意的風險、建議觀察的財務指標（150-200字）"
}}
"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        temperature=0.6,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    parsed = _try_parse_json(raw)
    if parsed is not None:
        return parsed

    print(f"JSON parse failed. Raw (first 400 chars): {raw[:400]}")
    return {"_fallback_raw": raw, "report_date": today}


# ═══════════════════════════════════════════════════════════════════
# HTML Email Builder
# ═══════════════════════════════════════════════════════════════════

def _val(v, suffix="", fallback="N/A") -> str:
    return f"{v}{suffix}" if v is not None else fallback


def _build_fallback_html(raw_text: str, date_str: str) -> str:
    escaped = _html_lib.escape(raw_text)
    paragraphs = "".join(
        f"<p style='margin:0 0 12px;line-height:1.8;'>{line}</p>" if line.strip() else "<br>"
        for line in escaped.splitlines()
    )
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="UTF-8"><title>投資學習日報 {date_str}</title></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:'Helvetica Neue',Arial,'PingFang TC',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;">
<tr><td align="center" style="padding:20px 16px;">
<table width="660" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
<tr><td style="background:linear-gradient(135deg,#1e3a5f,#2563eb);padding:32px 40px;text-align:center;">
  <div style="font-size:28px;font-weight:700;color:#fff;margin-bottom:8px;">📊 投資學習日報</div>
  <div style="font-size:14px;color:#bfdbfe;">{date_str}</div>
</td></tr>
<tr><td style="padding:32px 40px;">
  <div style="font-size:14px;color:#374151;">{paragraphs}</div>
  <table width="100%" cellpadding="0" cellspacing="0"
         style="border-top:1px solid #e5e7eb;margin-top:32px;padding-top:20px;">
  <tr><td style="text-align:center;font-size:12px;color:#9ca3af;line-height:2;">
    本報告由 AI 輔助生成，僅供學習參考，不構成投資建議。<br>
    數據來源：FinMind API · Anthropic Claude Haiku<br>
    生成時間：{ts}
  </td></tr>
  </table>
</td></tr>
</table>
</td></tr>
</table>
</body></html>"""


def _fundamentals_table(companies: list) -> str:
    header = """
<table width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;font-size:13px;margin-bottom:16px;">
  <tr style="background:#1e3a5f;">
    <td style="padding:9px 12px;color:#fff;font-weight:700;">公司</td>
    <td style="padding:9px 12px;color:#fff;font-weight:700;text-align:right;">P/E</td>
    <td style="padding:9px 12px;color:#fff;font-weight:700;text-align:right;">P/B</td>
    <td style="padding:9px 12px;color:#fff;font-weight:700;text-align:right;">ROE%</td>
    <td style="padding:9px 12px;color:#fff;font-weight:700;text-align:right;">負債比%</td>
    <td style="padding:9px 12px;color:#fff;font-weight:700;text-align:right;">EPS</td>
  </tr>"""
    rows = ""
    for i, co in enumerate(companies):
        bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
        is_holding = co["id"] in HOLDINGS
        name_style = "font-weight:700;color:#15803d;" if is_holding else "color:#1e3a5f;"
        holding_badge = (
            " <span style='font-size:10px;background:#dcfce7;color:#15803d;"
            "padding:1px 5px;border-radius:4px;'>持有</span>"
            if is_holding else ""
        )
        rows += f"""
  <tr style="background:{bg};border-top:1px solid #f1f5f9;">
    <td style="padding:10px 12px;{name_style}">{co['name']}({co['id']}){holding_badge}</td>
    <td style="padding:10px 12px;text-align:right;color:#374151;">{_val(co.get('pe'), 'x')}</td>
    <td style="padding:10px 12px;text-align:right;color:#374151;">{_val(co.get('pb'), 'x')}</td>
    <td style="padding:10px 12px;text-align:right;color:#374151;">{_val(co.get('roe'), '%')}</td>
    <td style="padding:10px 12px;text-align:right;color:#374151;">{_val(co.get('debt_ratio'), '%')}</td>
    <td style="padding:10px 12px;text-align:right;color:#374151;">{_val(co.get('eps'))}</td>
  </tr>"""
    return header + rows + "</table>"


def _commentary_box(commentary: dict) -> str:
    v = commentary.get("valuation_level", "")
    k = commentary.get("key_metrics", "")
    p = commentary.get("value_perspective", "")
    return f"""
<table width="100%" cellpadding="0" cellspacing="0"
       style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;margin-bottom:12px;">
  <tr><td style="padding:16px 20px;">
    <div style="font-size:12px;font-weight:700;color:#92400e;letter-spacing:1px;
                text-transform:uppercase;margin-bottom:12px;">💡 Claude 分析</div>
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr><td style="padding:0 0 8px;">
        <span style="font-size:12px;font-weight:700;color:#d97706;">▸ 估值水位</span><br>
        <span style="font-size:13px;color:#374151;line-height:1.7;">{_html_lib.escape(v)}</span>
      </td></tr>
      <tr><td style="padding:8px 0;border-top:1px solid #fde68a;">
        <span style="font-size:12px;font-weight:700;color:#d97706;">▸ 關鍵指標</span><br>
        <span style="font-size:13px;color:#374151;line-height:1.7;">{_html_lib.escape(k)}</span>
      </td></tr>
      <tr><td style="padding:8px 0 0;border-top:1px solid #fde68a;">
        <span style="font-size:12px;font-weight:700;color:#d97706;">▸ 價值投資觀察</span><br>
        <span style="font-size:13px;color:#374151;line-height:1.7;">{_html_lib.escape(p)}</span>
      </td></tr>
    </table>
  </td></tr>
</table>"""


def _holdings_box(ha: dict) -> str:
    analysis = _html_lib.escape(ha.get("analysis", ""))
    ticker = ha.get("ticker", "")
    name = ha.get("name", "")
    return f"""
<table width="100%" cellpadding="0" cellspacing="0"
       style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;margin-bottom:12px;">
  <tr><td style="padding:16px 20px;">
    <div style="font-size:13px;font-weight:700;color:#15803d;margin-bottom:10px;">
      📌 持有個股分析：{_html_lib.escape(name)} ({_html_lib.escape(ticker)})
    </div>
    <div style="font-size:13px;color:#374151;line-height:1.8;">{analysis}</div>
  </td></tr>
</table>"""


def build_html_email(report: dict, sectors_data: list) -> str:
    if "_fallback_raw" in report:
        return _build_fallback_html(report["_fallback_raw"], report.get("report_date", ""))

    date_str = report.get("report_date", datetime.now().strftime("%Y年%m月%d日"))
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Build a lookup: sector name → companies list (from raw FinMind data)
    companies_by_sector = {sd["name"]: sd["companies"] for sd in sectors_data}

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>投資學習日報 {date_str}</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;
             font-family:'Helvetica Neue',Arial,'PingFang TC','Microsoft JhengHei',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;">
<tr><td align="center" style="padding:20px 16px;">
<table width="660" cellpadding="0" cellspacing="0"
       style="background:#ffffff;border-radius:12px;overflow:hidden;
              box-shadow:0 2px 12px rgba(0,0,0,0.08);">

<!-- HEADER -->
<tr><td style="background:linear-gradient(135deg,#1e3a5f 0%,#2563eb 100%);
               padding:32px 40px;text-align:center;">
  <div style="font-size:11px;color:#93c5fd;letter-spacing:3px;
              text-transform:uppercase;margin-bottom:8px;">DAILY INVESTMENT REPORT</div>
  <div style="font-size:28px;font-weight:700;color:#ffffff;margin-bottom:8px;">
    📊 投資學習日報
  </div>
  <div style="font-size:14px;color:#bfdbfe;">{date_str} &nbsp;·&nbsp; 每日 23:00 UTC 自動發送</div>
</td></tr>

<tr><td style="padding:32px 40px;">
"""

    # Sector blocks
    sector_colors = ["#0369a1", "#065f46"]
    for idx, sector_info in enumerate(report.get("sectors", [])):
        sname = sector_info.get("name", "")
        intro = _html_lib.escape(sector_info.get("intro", ""))
        commentary = sector_info.get("commentary", {})
        holdings_analysis = sector_info.get("holdings_analysis")
        companies = companies_by_sector.get(sname, [])
        color = sector_colors[idx % len(sector_colors)]

        html += f"""
<!-- SECTOR: {_html_lib.escape(sname)} -->
<table width="100%" cellpadding="0" cellspacing="0"
       style="border:1px solid #e5e7eb;border-radius:10px;
              margin-bottom:28px;overflow:hidden;">
  <!-- sector header -->
  <tr><td style="background:{color};padding:16px 24px;">
    <div style="font-size:17px;font-weight:700;color:#ffffff;">🏭 {_html_lib.escape(sname)}</div>
  </td></tr>
  <!-- intro -->
  <tr><td style="background:#f8fafc;padding:14px 24px;
                 border-bottom:1px solid #e5e7eb;">
    <div style="font-size:13px;color:#374151;line-height:1.8;">{intro}</div>
  </td></tr>
  <!-- table + commentary + holdings -->
  <tr><td style="padding:20px 24px;">
    {_fundamentals_table(companies)}
    {_commentary_box(commentary)}
    {_holdings_box(holdings_analysis) if holdings_analysis else ""}
  </td></tr>
</table>"""

    # Footer
    html += f"""
<table width="100%" cellpadding="0" cellspacing="0"
       style="border-top:1px solid #e5e7eb;margin-top:16px;padding-top:20px;">
  <tr><td style="text-align:center;font-size:12px;color:#9ca3af;line-height:2;">
    本報告由 AI 輔助生成，僅供學習參考，不構成任何投資建議。<br>
    數據來源：FinMind API · Anthropic Claude Haiku<br>
    生成時間：{ts}
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

    print("  [1/4] Selecting today's sectors...")
    sectors = select_daily_sectors()
    day_of_year = datetime.now().timetuple().tm_yday
    print(f"        Day {day_of_year} → sectors: {[s['name'] for s in sectors]}")

    print("  [2/4] Fetching FinMind fundamentals...")
    sectors_data = fetch_sectors_data(sectors)

    print("  [3/4] Generating AI analysis (Claude Haiku)...")
    report = generate_report(sectors_data)

    print("  [4/4] Building HTML and sending email...")
    html = build_html_email(report, sectors_data)

    date_str = datetime.now().strftime("%Y/%m/%d")
    subject  = f"📊 投資學習日報 | {date_str} | {' & '.join(s['name'] for s in sectors)}"
    send_email(html, subject)
    print("✅ Done.")


if __name__ == "__main__":
    main()
