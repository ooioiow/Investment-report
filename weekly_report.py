#!/usr/bin/env python3
"""
Investment Learning Weekly Report
Runs every Sunday at 20:00 Taipei time (12:00 UTC via GitHub Actions)
"""

import os
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone

import yfinance as yf
import feedparser
import google.generativeai as genai

# ── Config from environment variables ─────────────────────────────────────────
GEMINI_API_KEY     = os.environ["GEMINI_API_KEY"]
GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL    = os.environ["RECIPIENT_EMAIL"]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ── Market Indices ─────────────────────────────────────────────────────────────
MARKET_INDICES = [
    {"label": "S&P 500",  "ticker": "^GSPC"},
    {"label": "Nasdaq",   "ticker": "^IXIC"},
    {"label": "台股加權", "ticker": "^TWII"},
    {"label": "USD/TWD",  "ticker": "TWD=X"},
    {"label": "VIX",      "ticker": "^VIX"},
]

# ── Sector Pool: 3 selected per week by rotation ──────────────────────────────
ALL_SECTORS = [
    {"name": "AI 與雲端",  "tickers": ["NVDA", "MSFT"],    "desc": "人工智慧、雲端運算、大型語言模型"},
    {"name": "半導體",     "tickers": ["TSM",  "ASML"],    "desc": "晶圓代工、半導體設備、先進製程"},
    {"name": "生技醫療",   "tickers": ["JNJ",  "UNH"],     "desc": "製藥研發、醫療保險、醫療器材"},
    {"name": "清潔能源",   "tickers": ["NEE",  "ENPH"],    "desc": "再生能源、太陽能、儲能系統"},
    {"name": "消費必需品", "tickers": ["KO",   "PG"],      "desc": "飲料、日用品、防禦型配置"},
    {"name": "支付金融",   "tickers": ["V",    "MA"],      "desc": "支付網路、跨境交易、數位金融"},
    {"name": "台灣供應鏈", "tickers": ["2330.TW", "2317.TW"], "desc": "台積電與鴻海，台灣科技核心"},
]

# ── Investment Concepts: rotates weekly ───────────────────────────────────────
INVESTMENT_CONCEPTS = [
    "自由現金流（Free Cash Flow, FCF）",
    "護城河（Economic Moat）",
    "股東權益報酬率（Return on Equity, ROE）",
    "本益比與本益成長比（P/E & PEG Ratio）",
    "企業價值倍數（EV/EBITDA）",
    "股息成長投資策略（Dividend Growth Investing）",
    "毛利率與淨利率的意義（Gross & Net Margin）",
    "資本支出與輕資產商業模式（CapEx & Asset-Light）",
    "投入資本回報率（Return on Invested Capital, ROIC）",
    "安全邊際（Margin of Safety）",
    "複利效應與長期投資的力量",
    "資產負債表解讀：財務健康度評估",
    "現金流量表三大部分：判斷真實獲利能力",
    "競爭優勢分析：Porter's Five Forces",
    "分散投資、相關性與組合波動率",
    "景氣循環股 vs 防禦型股票的選擇時機",
    "成長型投資 vs 價值型投資",
    "巴菲特指標（Buffett Indicator）與市場估值",
    "殖利率曲線倒掛與衰退預測",
    "股票回購（Buyback）對股東價值的影響",
]

# ── RSS News Feeds ─────────────────────────────────────────────────────────────
RSS_FEEDS = [
    "https://finance.yahoo.com/news/rssindex",
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US",
]


# ══════════════════════════════════════════════════════════════════════════════
# Data Fetching
# ══════════════════════════════════════════════════════════════════════════════

def fetch_market_data() -> list:
    """Fetch weekly performance for all five market indices."""
    results = []
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=12)  # buffer for holidays/weekends

    for item in MARKET_INDICES:
        try:
            hist = yf.Ticker(item["ticker"]).history(
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
            )
            if hist.empty or len(hist) < 2:
                results.append({"label": item["label"], "ticker": item["ticker"], "error": "資料不足"})
                continue

            current = float(hist["Close"].iloc[-1])
            # Compare to close from ~5 trading days ago
            lookback = min(6, len(hist) - 1)
            prev = float(hist["Close"].iloc[-lookback - 1])
            change_pct = (current - prev) / prev * 100

            results.append({
                "label": item["label"],
                "ticker": item["ticker"],
                "current": round(current, 2),
                "prev": round(prev, 2),
                "change_pct": round(change_pct, 2),
            })
        except Exception as e:
            results.append({"label": item["label"], "ticker": item["ticker"], "error": str(e)})

    return results


def fetch_news(max_items: int = 18) -> list:
    """Fetch recent financial headlines from RSS feeds."""
    news = []
    per_feed = max(1, max_items // len(RSS_FEEDS))
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:per_feed]:
                news.append({
                    "title": entry.get("title", "").strip(),
                    "summary": entry.get("summary", "")[:300].strip(),
                    "published": entry.get("published", ""),
                })
        except Exception as e:
            print(f"RSS fetch error ({url}): {e}")
    return news[:max_items]


def fetch_sector_data(sectors: list) -> list:
    """Fetch yfinance data for each sector's representative stocks."""
    result = []
    for sector in sectors:
        stocks = []
        for ticker_str in sector["tickers"]:
            try:
                t = yf.Ticker(ticker_str)
                info = t.info
                hist = t.history(period="1y")

                # Best-effort current price
                current_price = (
                    info.get("currentPrice")
                    or info.get("regularMarketPrice")
                    or (float(hist["Close"].iloc[-1]) if not hist.empty else None)
                )

                w52h = info.get("fiftyTwoWeekHigh")
                w52l = info.get("fiftyTwoWeekLow")
                pe_trailing = info.get("trailingPE")
                pe_forward = info.get("forwardPE")

                pos_pct = None
                if w52h and w52l and current_price and w52h != w52l:
                    pos_pct = round((current_price - w52l) / (w52h - w52l) * 100, 1)

                stocks.append({
                    "ticker": ticker_str,
                    "name": info.get("longName") or info.get("shortName") or ticker_str,
                    "current_price": round(current_price, 2) if current_price else None,
                    "pe_trailing": round(pe_trailing, 1) if pe_trailing else None,
                    "pe_forward": round(pe_forward, 1) if pe_forward else None,
                    "week52_high": round(w52h, 2) if w52h else None,
                    "week52_low": round(w52l, 2) if w52l else None,
                    "position_in_52w_pct": pos_pct,
                    "market_cap_b": round(info.get("marketCap", 0) / 1e9, 1) if info.get("marketCap") else None,
                })
            except Exception as e:
                stocks.append({"ticker": ticker_str, "error": str(e)})

        result.append({
            "name": sector["name"],
            "desc": sector["desc"],
            "stocks": stocks,
        })
    return result


def select_weekly_sectors() -> list:
    week_num = datetime.now().isocalendar()[1]
    start = (week_num * 3) % len(ALL_SECTORS)
    selected = (ALL_SECTORS + ALL_SECTORS)[start : start + 3]  # wrap-around safe
    return selected


def select_weekly_concept() -> str:
    week_num = datetime.now().isocalendar()[1]
    return INVESTMENT_CONCEPTS[week_num % len(INVESTMENT_CONCEPTS)]


# ══════════════════════════════════════════════════════════════════════════════
# Gemini AI Analysis
# ══════════════════════════════════════════════════════════════════════════════

def generate_report(market_data: list, news: list, sector_data: list, concept: str) -> dict:
    """Send all collected data to Gemini and receive structured JSON analysis."""

    market_text = "\n".join(
        f"- {d['label']} ({d['ticker']}): 現值 {d.get('current','N/A')}, 週漲跌 {d.get('change_pct','N/A')}%"
        if "error" not in d
        else f"- {d['label']}: 資料獲取失敗 ({d['error']})"
        for d in market_data
    )

    news_text = "\n".join(
        f"- {n['title']}: {n['summary']}" for n in news[:15]
    )

    today = datetime.now().strftime("%Y年%m月%d日")

    prompt = f"""
你是專業的長線投資分析師，擅長基本面分析與價值投資。請根據以下數據，用**繁體中文**生成投資學習週報分析。

今日日期：{today}

【市場數據】
{market_text}

【本週財經新聞】
{news_text}

【產業與個股數據】
{json.dumps(sector_data, ensure_ascii=False, indent=2)}

【本週投資概念】
{concept}

請嚴格輸出以下 JSON 結構（不含任何額外文字或 markdown 標記）：

{{
  "report_date": "{today}",
  "market_summary": [
    {{
      "label": "指數名稱",
      "change_pct": 數字,
      "current": 數字,
      "interpretation": "以長線投資者視角，一句話解讀本週走勢（20-40 字）"
    }}
  ],
  "macro_events": {{
    "bullets": ["重要事件1", "重要事件2", "重要事件3"],
    "long_term_significance": "對長線投資者的意義（100-150 字）"
  }},
  "sector_trends": [
    {{
      "sector_name": "產業名稱",
      "trend_description": "本週產業趨勢（80-100 字）",
      "stocks": [
        {{
          "ticker": "代號",
          "name": "公司名稱",
          "current_price": 數字或null,
          "pe_trailing": 數字或null,
          "pe_5yr_avg_estimate": "根據你的知識，這家公司近5年平均本益比大約為多少？直接給數字",
          "pe_assessment": "現在PE相較5年均值的判斷，一句話",
          "week52_high": 數字或null,
          "week52_low": 數字或null,
          "position_in_52w_pct": 數字或null,
          "price_position_label": "接近年高點／中間區間／接近年低點",
          "valuation_verdict": "偏貴／合理／偏便宜",
          "valuation_reason": "長線估值判斷理由（50-80 字）",
          "key_risks": ["風險1", "風險2", "風險3"]
        }}
      ]
    }}
  ],
  "investment_concept": {{
    "name": "{concept}",
    "definition": "定義（50-80 字）",
    "calculation": "計算方式或判斷方法（可含公式）",
    "how_to_use": "如何用於選股（100-120 字）",
    "real_example": "以一家知名公司為例說明（80-100 字）",
    "key_takeaway": "本週學習一句話精華"
  }}
}}
"""

    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.65,
            max_output_tokens=4096,
            response_mime_type="application/json",
        ),
    )

    raw = response.text.strip()
    # Strip markdown fences if model ignores mime type
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}\nRaw (first 600 chars): {raw[:600]}")
        return {"error": "AI 分析生成失敗，請稍後重試", "raw": raw}


# ══════════════════════════════════════════════════════════════════════════════
# HTML Email Builder
# ══════════════════════════════════════════════════════════════════════════════

def _pct_color(pct):
    if pct is None:
        return "#6b7280"
    return "#16a34a" if float(pct) >= 0 else "#dc2626"

def _pct_label(pct):
    if pct is None:
        return "N/A"
    arrow = "▲" if float(pct) >= 0 else "▼"
    return f"{arrow} {abs(float(pct)):.2f}%"

VERDICT_COLOR = {"偏貴": "#dc2626", "合理": "#d97706", "偏便宜": "#16a34a"}


def build_html_email(report: dict) -> str:
    if "error" in report:
        return (
            "<html><body style='font-family:Arial;padding:20px;'>"
            f"<h2>⚠ 報告生成失敗</h2><p>{report['error']}</p>"
            f"<pre style='font-size:12px;color:#666'>{report.get('raw','')[:2000]}</pre>"
            "</body></html>"
        )

    date_str = report.get("report_date", datetime.now().strftime("%Y年%m月%d日"))

    # ── Helpers ──────────────────────────────────────────────────────────────
    def td(content, style=""):
        return f"<td style='padding:10px 12px;font-size:14px;{style}'>{content}</td>"

    def section_header(title, color):
        return (
            f"<table width='100%' cellpadding='0' cellspacing='0' style='margin-bottom:20px;margin-top:28px;'>"
            f"<tr><td style='border-left:4px solid {color};padding-left:12px;"
            f"font-size:18px;font-weight:700;color:#1e3a5f;'>{title}</td></tr>"
            f"</table>"
        )

    # ── Start HTML ────────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>投資學習週報 {date_str}</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:'Helvetica Neue',Arial,'PingFang TC','Microsoft JhengHei',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;">
<tr><td align="center" style="padding:20px 16px;">
<table width="660" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">

<!-- ═══ HEADER ═══ -->
<tr><td style="background:linear-gradient(135deg,#1e3a5f 0%,#2563eb 100%);padding:32px 40px;text-align:center;">
  <div style="font-size:11px;color:#93c5fd;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px;">WEEKLY INVESTMENT REPORT</div>
  <div style="font-size:28px;font-weight:700;color:#ffffff;margin-bottom:8px;">📊 投資學習週報</div>
  <div style="font-size:14px;color:#bfdbfe;">{date_str} &nbsp;·&nbsp; 每週日 20:00 台北時間自動發送</div>
</td></tr>

<tr><td style="padding:32px 40px;">
"""

    # ── Section 1: Market Summary ─────────────────────────────────────────────
    html += section_header("📈 本週市場表現", "#2563eb")
    html += """<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-bottom:8px;">
<tr style="background:#f8fafc;">
  <td style="padding:10px 12px;font-size:12px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:1px;">指數</td>
  <td style="padding:10px 12px;font-size:12px;font-weight:700;color:#6b7280;text-align:right;">現值</td>
  <td style="padding:10px 12px;font-size:12px;font-weight:700;color:#6b7280;text-align:right;">週漲跌</td>
  <td style="padding:10px 12px;font-size:12px;font-weight:700;color:#6b7280;">長線解讀</td>
</tr>"""

    for i, item in enumerate(report.get("market_summary", [])):
        bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
        pct = item.get("change_pct")
        color = _pct_color(pct)
        label_str = _pct_label(pct)
        cur = item.get("current")
        cur_str = f"{cur:,.2f}" if cur else "N/A"
        html += f"""<tr style="background:{bg};border-top:1px solid #f1f5f9;">
  <td style="padding:12px;font-size:14px;font-weight:700;color:#1e3a5f;">{item.get('label','')}</td>
  <td style="padding:12px;font-size:14px;color:#374151;text-align:right;font-variant-numeric:tabular-nums;">{cur_str}</td>
  <td style="padding:12px;font-size:14px;font-weight:700;color:{color};text-align:right;">{label_str}</td>
  <td style="padding:12px;font-size:13px;color:#6b7280;line-height:1.6;">{item.get('interpretation','')}</td>
</tr>"""

    html += "</table>"

    # ── Section 2: Macro Events ───────────────────────────────────────────────
    macro = report.get("macro_events", {})
    html += section_header("🌐 本週重要總經事件", "#7c3aed")

    bullets_html = "".join(
        f"<tr><td style='padding:6px 0;font-size:14px;color:#374151;line-height:1.7;'>"
        f"<span style='color:#7c3aed;font-weight:700;margin-right:6px;'>•</span>{b}</td></tr>"
        for b in macro.get("bullets", [])
    )
    html += f"""<table width="100%" cellpadding="0" cellspacing="0" style="background:#faf5ff;border:1px solid #e9d5ff;border-radius:8px;padding:16px 20px;margin-bottom:12px;">
<tr><td><table width="100%" cellpadding="0" cellspacing="0">{bullets_html}</table></td></tr>
</table>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;margin-bottom:8px;">
<tr><td style="padding:16px 20px;">
  <div style="font-size:12px;font-weight:700;color:#2563eb;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px;">💡 對長線投資者的意義</div>
  <div style="font-size:14px;color:#374151;line-height:1.7;">{macro.get('long_term_significance','')}</div>
</td></tr>
</table>"""

    # ── Section 3: Sector Trends ──────────────────────────────────────────────
    html += section_header("🏭 本週產業趨勢與個股分析", "#059669")

    for sector in report.get("sector_trends", []):
        html += f"""<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:10px;margin-bottom:20px;overflow:hidden;">
<tr><td style="background:#f0fdf4;padding:16px 20px;border-bottom:1px solid #d1fae5;">
  <div style="font-size:16px;font-weight:700;color:#065f46;">🏷 {sector.get('sector_name','')}</div>
  <div style="font-size:13px;color:#374151;margin-top:6px;line-height:1.6;">{sector.get('trend_description','')}</div>
</td></tr>
<tr><td style="padding:16px 20px;">"""

        for stock in sector.get("stocks", []):
            verdict = stock.get("valuation_verdict", "")
            vcolor = VERDICT_COLOR.get(verdict, "#6b7280")

            pe_t = stock.get("pe_trailing")
            pe_5 = stock.get("pe_5yr_avg_estimate")
            pe_str = f"{pe_t:.1f}x" if pe_t else "N/A"
            pe5_str = f"（5年均值估 {pe_5}x）" if pe_5 else ""

            w52h = stock.get("week52_high")
            w52l = stock.get("week52_low")
            pos = stock.get("position_in_52w_pct")
            range_str = f"{w52l} ~ {w52h}" if w52h and w52l else "N/A"
            pos_str = f"，目前在年內區間 <strong>{pos:.0f}%</strong> 位置" if pos is not None else ""
            pos_label = stock.get("price_position_label", "")

            risks = stock.get("key_risks", [])
            risks_html = "".join(
                f"<span style='display:inline-block;background:#fff8f1;border:1px solid #fed7aa;"
                f"border-radius:4px;padding:2px 8px;font-size:12px;color:#c2410c;margin:2px 4px 2px 0;'>{r}</span>"
                for r in (risks if isinstance(risks, list) else [risks])
            )
            pe_assess = stock.get("pe_assessment", "")
            val_reason = stock.get("valuation_reason", "")

            html += f"""<table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;border-radius:8px;margin-bottom:12px;">
<tr>
  <td style="padding:14px 16px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td>
          <span style="font-size:16px;font-weight:700;color:#1e3a5f;">{stock.get('ticker','')}</span>
          <span style="font-size:13px;color:#6b7280;margin-left:8px;">{stock.get('name','')}</span>
        </td>
        <td align="right">
          <span style="background:{vcolor};color:#fff;font-size:12px;font-weight:700;padding:3px 12px;border-radius:20px;">{verdict}</span>
        </td>
      </tr>
    </table>
    <!-- PE Row -->
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:10px;">
      <tr>
        <td width="50%" style="font-size:13px;color:#374151;padding-right:8px;">
          <span style="color:#6b7280;">📊 本益比：</span><strong>{pe_str}</strong> {pe5_str}
        </td>
        <td width="50%" style="font-size:13px;color:#374151;">
          <span style="color:#6b7280;">📉 52週區間：</span>{range_str}
        </td>
      </tr>
      <tr>
        <td style="font-size:13px;color:#6b7280;padding-top:4px;">{pe_assess}</td>
        <td style="font-size:13px;color:#6b7280;padding-top:4px;">{pos_label}{pos_str}</td>
      </tr>
    </table>
    <!-- Valuation reason -->
    <div style="font-size:13px;color:#374151;line-height:1.7;margin-top:10px;">
      <span style="font-weight:700;color:#065f46;">💬 估值理由：</span>{val_reason}
    </div>
    <!-- Risks -->
    <div style="margin-top:10px;">
      <span style="font-size:12px;font-weight:700;color:#d97706;">⚠ 主要風險：</span>
      <div style="margin-top:4px;">{risks_html}</div>
    </div>
  </td>
</tr>
</table>"""

        html += "</td></tr></table>"

    # ── Section 4: Investment Concept ─────────────────────────────────────────
    concept = report.get("investment_concept", {})
    html += section_header("📚 本週投資概念學習", "#d97706")

    def concept_row(icon, label, content):
        return (
            f"<tr><td style='padding:14px 0;border-top:1px solid #fde68a;'>"
            f"<div style='font-size:12px;font-weight:700;color:#d97706;text-transform:uppercase;"
            f"letter-spacing:1px;margin-bottom:6px;'>{icon} {label}</div>"
            f"<div style='font-size:14px;color:#374151;line-height:1.7;'>{content}</div>"
            f"</td></tr>"
        )

    calc_content = concept.get("calculation", "")
    calc_html = f"<code style='font-family:monospace;background:#fffbeb;padding:8px 12px;border-radius:6px;border:1px solid #fde68a;display:block;white-space:pre-wrap;font-size:13px;color:#92400e;'>{calc_content}</code>"

    html += f"""<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #fde68a;border-radius:10px;overflow:hidden;">
<tr><td style="background:linear-gradient(135deg,#78350f,#d97706);padding:16px 24px;">
  <div style="font-size:17px;font-weight:700;color:#ffffff;">{concept.get('name','')}</div>
</td></tr>
<tr><td style="background:#fffbeb;padding:20px 24px;">
  <table width="100%" cellpadding="0" cellspacing="0">
    {concept_row("📖", "定義", concept.get("definition", ""))}
    {concept_row("🔢", "計算方式", calc_html)}
    {concept_row("🎯", "如何應用於選股", concept.get("how_to_use", ""))}
    {concept_row("💼", "實際案例", concept.get("real_example", ""))}
    <tr><td style="padding-top:16px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#fef3c7;border:1px solid #fde68a;border-radius:8px;">
        <tr><td style="padding:14px 16px;">
          <div style="font-size:12px;font-weight:700;color:#92400e;margin-bottom:6px;">💡 本週重點</div>
          <div style="font-size:14px;font-weight:600;color:#78350f;line-height:1.6;">{concept.get("key_takeaway", "")}</div>
        </td></tr>
      </table>
    </td></tr>
  </table>
</td></tr>
</table>"""

    # ── Footer ────────────────────────────────────────────────────────────────
    html += f"""
<table width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #e5e7eb;margin-top:32px;padding-top:20px;">
<tr><td style="text-align:center;font-size:12px;color:#9ca3af;line-height:2;">
  本報告由 AI 輔助生成，僅供學習參考，不構成任何投資建議。<br>
  數據來源：Yahoo Finance (yfinance) · Google Gemini 1.5 Flash · RSS 新聞<br>
  生成時間：{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
</td></tr>
</table>

</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""

    return html


# ══════════════════════════════════════════════════════════════════════════════
# Email Sender
# ══════════════════════════════════════════════════════════════════════════════

def send_email(html_content: str, subject: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT_EMAIL

    msg.attach(MIMEText("請使用支援 HTML 的郵件客戶端查看本週報。", "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_bytes())

    print(f"✅ Email sent → {RECIPIENT_EMAIL}")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"🚀 Weekly report starting at {datetime.now(timezone.utc).isoformat()}")

    print("  [1/5] Fetching market data...")
    market_data = fetch_market_data()

    print("  [2/5] Fetching news RSS...")
    news = fetch_news()

    print("  [3/5] Selecting sectors & concept...")
    sectors = select_weekly_sectors()
    concept = select_weekly_concept()
    print(f"        Sectors: {[s['name'] for s in sectors]}")
    print(f"        Concept: {concept}")

    print("  [4/5] Fetching sector stock data...")
    sector_data = fetch_sector_data(sectors)

    print("  [5/5] Generating AI analysis (Gemini)...")
    report = generate_report(market_data, news, sector_data, concept)

    html = build_html_email(report)

    week_num = datetime.now().isocalendar()[1]
    date_str  = datetime.now().strftime("%Y/%m/%d")
    subject   = f"📊 投資學習週報 W{week_num:02d} | {date_str}"

    send_email(html, subject)
    print("✅ Done.")


if __name__ == "__main__":
    main()
