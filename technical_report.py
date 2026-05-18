#!/usr/bin/env python3
"""
Daily Technical Analysis Report
Runs every day at 23:30 UTC via GitHub Actions.

Tracks: S&P500, Taiwan Weighted, TSMC, MediaTek, Taiwan Mobile
Indicators: RSI(14), MACD(12,26,9), Bollinger Bands(20,2), Volume anomaly
"""

import os
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone

import yfinance as yf
import pandas as pd
import numpy as np
import anthropic

# ── Config from environment variables ─────────────────────────────────────────
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL    = os.environ["RECIPIENT_EMAIL"]

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Watchlist ──────────────────────────────────────────────────────────────────
WATCHLIST = [
    {"label": "S&P 500",  "ticker": "^GSPC",   "has_volume": True},
    {"label": "台股加權", "ticker": "^TWII",   "has_volume": False},  # index: volume unreliable
    {"label": "台積電",   "ticker": "2330.TW", "has_volume": True},
    {"label": "聯發科",   "ticker": "2454.TW", "has_volume": True},
    {"label": "台灣大",   "ticker": "3045.TW", "has_volume": True},
]


# ══════════════════════════════════════════════════════════════════════════════
# Technical Indicator Calculations (pure pandas/numpy, no TA-Lib)
# ══════════════════════════════════════════════════════════════════════════════

def calc_rsi(close: pd.Series, period: int = 14) -> float:
    """Wilder's RSI using EWM (equivalent to Wilder smoothing)."""
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])


def calc_macd(close: pd.Series) -> tuple[float, float, float]:
    """MACD (12, 26, 9). Returns (macd_line, signal_line, histogram)."""
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line   = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram   = macd_line - signal_line
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(histogram.iloc[-1])


def calc_bollinger(close: pd.Series, period: int = 20, num_std: float = 2.0) -> dict:
    """Bollinger Bands (period, ±num_std). Returns band values and %B position."""
    sma   = close.rolling(period).mean()
    std   = close.rolling(period).std(ddof=0)
    upper = sma + num_std * std
    lower = sma - num_std * std
    price = float(close.iloc[-1])
    u, m, l = float(upper.iloc[-1]), float(sma.iloc[-1]), float(lower.iloc[-1])
    pct_b = (price - l) / (u - l) * 100 if (u - l) != 0 else 50.0
    return {"upper": u, "mid": m, "lower": l, "pct_b": round(pct_b, 1)}


def calc_volume_ratio(volume: pd.Series, period: int = 20) -> dict | None:
    """Compare today's volume to the rolling average. Returns None if unreliable."""
    if volume.isna().all() or (volume == 0).all():
        return None
    clean = volume.replace(0, np.nan).dropna()
    if len(clean) < period:
        return None
    avg     = float(clean.rolling(period).mean().iloc[-1])
    current = float(clean.iloc[-1])
    ratio   = round(current / avg, 2) if avg > 0 else None
    return {"current": int(current), "avg": int(avg), "ratio": ratio}


# ── Derived labels ─────────────────────────────────────────────────────────────

def rsi_label(rsi: float) -> str:
    if rsi > 70:  return "超買區（>70）"
    if rsi < 30:  return "超賣區（<30）"
    if rsi > 60:  return "偏強（60-70）"
    if rsi < 40:  return "偏弱（30-40）"
    return "中性（40-60）"


def macd_label(hist: float) -> tuple[str, str]:
    """Returns (trend_label, color_hint)."""
    if hist > 0:  return "多頭排列 ▲", "bullish"
    return "空頭排列 ▼", "bearish"


def bb_label(pct_b: float) -> str:
    if pct_b > 90:  return "突破上軌"
    if pct_b > 75:  return "接近上軌"
    if pct_b > 55:  return "上方區間"
    if pct_b > 45:  return "中間區間"
    if pct_b > 25:  return "下方區間"
    if pct_b > 10:  return "接近下軌"
    return "跌破下軌"


def vol_label_flag(ratio: float | None) -> tuple[str, str]:
    """Returns (label, emoji flag)."""
    if ratio is None:  return "資料不足", "⚫"
    if ratio > 3.0:    return "成交量極度異常", "🔴"
    if ratio > 2.0:    return "成交量異常偏高", "🟠"
    if ratio > 1.5:    return "成交量偏高",    "🟡"
    if ratio < 0.5:    return "成交量極低",    "⚪"
    if ratio < 0.7:    return "成交量偏低",    "🔵"
    return "成交量正常", "🟢"


def compute_verdict(rsi: float, hist: float, pct_b: float) -> str:
    """
    Combine RSI, MACD histogram and %B into a single verdict.
    Requires at least 2 of 3 signals to agree before calling overbought/oversold.
    """
    ob = sum([rsi > 70, pct_b > 80, hist < 0 and pct_b > 60])  # overbought signals
    os = sum([rsi < 30, pct_b < 20, hist > 0 and pct_b < 40])  # oversold signals
    if rsi > 75 or (ob >= 2):   return "超買"
    if rsi < 25 or (os >= 2):   return "超賣"
    if rsi > 65 or pct_b > 70:  return "偏強"
    if rsi < 35 or pct_b < 30:  return "偏弱"
    return "中性"


# ══════════════════════════════════════════════════════════════════════════════
# Data Fetching
# ══════════════════════════════════════════════════════════════════════════════

def fetch_all() -> list[dict]:
    """Fetch 90 days of OHLCV and compute all technical indicators."""
    results = []
    for item in WATCHLIST:
        ticker_str = item["ticker"]
        try:
            hist = yf.Ticker(ticker_str).history(period="90d")
            if hist.empty or len(hist) < 35:
                results.append({**item, "error": "歷史資料不足（<35日）"})
                continue

            close  = hist["Close"].dropna()
            volume = hist["Volume"] if item["has_volume"] else pd.Series([], dtype=float)

            rsi                     = calc_rsi(close)
            macd_line, sig, hist_v  = calc_macd(close)
            bb                      = calc_bollinger(close)
            vol                     = calc_volume_ratio(volume) if item["has_volume"] else None

            price     = float(close.iloc[-1])
            prev      = float(close.iloc[-2])
            chg_pct   = (price - prev) / prev * 100

            ml_str, mc = macd_label(hist_v)
            vl, vf     = vol_label_flag(vol["ratio"] if vol else None)

            results.append({
                "label":        item["label"],
                "ticker":       ticker_str,
                "has_volume":   item["has_volume"],
                # Price
                "price":        round(price, 2),
                "chg_pct":      round(chg_pct, 2),
                # RSI
                "rsi":          round(rsi, 1),
                "rsi_label":    rsi_label(rsi),
                # MACD
                "macd_line":    round(macd_line, 4),
                "macd_sig":     round(sig, 4),
                "macd_hist":    round(hist_v, 4),
                "macd_label":   ml_str,
                "macd_color":   mc,
                # Bollinger
                "bb_upper":     round(bb["upper"], 2),
                "bb_mid":       round(bb["mid"],   2),
                "bb_lower":     round(bb["lower"],  2),
                "bb_pct_b":     bb["pct_b"],
                "bb_label":     bb_label(bb["pct_b"]),
                # Volume
                "vol_ratio":    vol["ratio"] if vol else None,
                "vol_label":    vl,
                "vol_flag":     vf,
                # Verdict
                "verdict":      compute_verdict(rsi, hist_v, bb["pct_b"]),
            })

        except Exception as e:
            results.append({**item, "error": str(e)})

    return results


# ══════════════════════════════════════════════════════════════════════════════
# Claude AI Analysis
# ══════════════════════════════════════════════════════════════════════════════

def generate_analysis(data: list[dict]) -> dict:
    """Ask Claude Haiku for market overview and per-stock short-term suggestions."""

    lines = []
    for d in data:
        if "error" in d:
            lines.append(f"- {d['label']} ({d['ticker']}): 資料取得失敗")
            continue
        vol_part = f"成交量={d['vol_label']}({d['vol_ratio']}x)" if d["has_volume"] else "成交量=N/A"
        lines.append(
            f"- {d['label']} ({d['ticker']}): "
            f"收盤={d['price']} 日漲跌={d['chg_pct']:+.2f}% | "
            f"RSI={d['rsi']}({d['rsi_label']}) | "
            f"MACD={d['macd_label']} 柱={d['macd_hist']:+.4f} | "
            f"布林%B={d['bb_pct_b']}%({d['bb_label']}) | "
            f"{vol_part} | "
            f"初步判斷={d['verdict']}"
        )

    today = datetime.now().strftime("%Y年%m月%d日")

    prompt = f"""
你是專業的技術分析師，擅長台股與美股的短線技術分析。請根據以下今日技術指標，用**繁體中文**提供精準分析。

今日日期：{today}

【今日技術指標摘要】
{chr(10).join(lines)}

【分析規則 — 必須嚴格遵守】
1. RSI > 70 → 超買，注意獲利了結或回調；RSI < 30 → 超賣，留意反彈但需確認底部
2. MACD 柱狀圖 > 0 且擴張 → 短線多頭動能增強；< 0 且擴大 → 空頭動能增強
3. 布林 %B > 80% → 價格接近或突破上軌，短線強勢但過熱風險；< 20% → 接近下軌，可能超賣
4. 成交量異常偏高搭配上漲 → 突破有效；搭配下跌 → 恐慌出逃，需留意
5. 指標間矛盾時（如 RSI 超買但 MACD 仍多頭）必須點出矛盾並給出平衡建議
6. 所有分析必須符合基本技術分析邏輯，不能出現逻輯矛盾

請輸出嚴格的 JSON 格式，不含任何 markdown 標記或額外文字：

{{
  "market_overview": "今日整體技術面簡評，涵蓋美台市場連動性（60-80 字）",
  "analyses": [
    {{
      "ticker": "標的代號",
      "label": "標的名稱",
      "verdict": "超買／超賣／偏強／偏弱／中性",
      "key_signal": "最值得注意的技術訊號，指出矛盾或共振（25-35 字）",
      "short_term_suggestion": "短線操作建議，包含支撐壓力位參考（40-55 字）",
      "stop_loss_note": "停損或風控提醒（20-30 字）"
    }}
  ],
  "risk_reminder": "今日整體操作風險提示，點出最大尾端風險（35-50 字）"
}}
"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        temperature=0.3,   # low temp → deterministic, logic-consistent output
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        lines_raw = raw.splitlines()
        raw = "\n".join(lines_raw[1:-1] if lines_raw[-1].strip() == "```" else lines_raw[1:])

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}\nRaw: {raw[:400]}")
        return {
            "market_overview": "分析生成失敗，請手動查閱指標。",
            "analyses": [],
            "risk_reminder": "AI 分析暫時無法使用，請自行評估風險。",
        }


# ══════════════════════════════════════════════════════════════════════════════
# HTML Email Builder
# ══════════════════════════════════════════════════════════════════════════════

# Verdict → visual style mapping
_VSTYLE: dict[str, dict] = {
    "超買": {"bg": "#fef2f2", "border": "#fca5a5", "badge": "#dc2626"},
    "超賣": {"bg": "#f0fdf4", "border": "#86efac", "badge": "#16a34a"},
    "偏強": {"bg": "#fffbeb", "border": "#fde68a", "badge": "#d97706"},
    "偏弱": {"bg": "#f0f9ff", "border": "#bae6fd", "badge": "#0284c7"},
    "中性": {"bg": "#f8fafc", "border": "#cbd5e1", "badge": "#475569"},
}
_DEFAULT_VSTYLE = {"bg": "#f8fafc", "border": "#cbd5e1", "badge": "#475569"}


def _bar(pct: float, width: int, color: str) -> str:
    """Table-based horizontal progress bar (email-safe, no CSS Grid/Flex)."""
    filled = max(0, min(int(pct / 100 * width), width))
    empty  = width - filled
    return (
        f"<table cellpadding='0' cellspacing='0' style='display:inline-table;"
        f"width:{width}px;height:8px;border-radius:4px;overflow:hidden;"
        f"background:#e2e8f0;vertical-align:middle;'><tr>"
        f"<td style='width:{filled}px;background:{color};height:8px;'></td>"
        f"<td style='width:{empty}px;background:#e2e8f0;height:8px;'></td>"
        f"</tr></table>"
    )


def _rsi_visual(rsi: float) -> str:
    color = "#dc2626" if rsi > 70 else ("#16a34a" if rsi < 30 else "#3b82f6")
    bar   = _bar(rsi, 100, color)
    return (
        f"{bar}&nbsp;"
        f"<span style='font-size:13px;font-weight:700;color:{color};'>{rsi:.1f}</span>"
    )


def _bb_visual(pct_b: float) -> str:
    color = "#dc2626" if pct_b > 80 else ("#16a34a" if pct_b < 20 else "#3b82f6")
    bar   = _bar(min(max(pct_b, 0), 100), 100, color)
    return (
        f"{bar}&nbsp;"
        f"<span style='font-size:13px;font-weight:700;color:{color};'>{pct_b:.0f}%</span>"
    )


def _macd_visual(label: str, hist: float) -> str:
    color = "#16a34a" if hist > 0 else "#dc2626"
    return f"<span style='font-size:13px;font-weight:700;color:{color};'>{label}</span>"


def build_html(tech_data: list[dict], analysis: dict, report_date: str) -> str:
    ai_map = {a["ticker"]: a for a in analysis.get("analyses", [])}

    # ── outer shell ───────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>每日技術分析 {report_date}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;
  font-family:'Helvetica Neue',Arial,'PingFang TC','Microsoft JhengHei',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;">
<tr><td align="center" style="padding:20px 16px;">
<table width="680" cellpadding="0" cellspacing="0"
  style="background:#fff;border-radius:12px;overflow:hidden;
         box-shadow:0 2px 16px rgba(0,0,0,0.09);">

<!-- ═══ HEADER ═══ -->
<tr><td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 55%,#0369a1 100%);
               padding:26px 40px;text-align:center;">
  <div style="font-size:11px;color:#7dd3fc;letter-spacing:3px;
              text-transform:uppercase;margin-bottom:6px;">DAILY TECHNICAL ANALYSIS</div>
  <div style="font-size:26px;font-weight:700;color:#fff;margin-bottom:6px;">📉 每日技術分析報告</div>
  <div style="font-size:13px;color:#bae6fd;">{report_date} &nbsp;·&nbsp; 23:30 UTC 自動生成</div>
</td></tr>

<tr><td style="padding:28px 40px;">
"""

    # ── market overview ────────────────────────────────────────────────────────
    overview = analysis.get("market_overview", "")
    if overview:
        html += f"""<table width="100%" cellpadding="0" cellspacing="0"
  style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;margin-bottom:24px;">
<tr><td style="padding:16px 20px;">
  <div style="font-size:11px;font-weight:700;color:#2563eb;letter-spacing:1px;
              text-transform:uppercase;margin-bottom:8px;">🌐 今日市場技術面概覽</div>
  <div style="font-size:14px;color:#1e40af;line-height:1.7;">{overview}</div>
</td></tr></table>
"""

    # ── section title ──────────────────────────────────────────────────────────
    html += """<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">
<tr><td style="border-left:4px solid #0369a1;padding-left:12px;
               font-size:16px;font-weight:700;color:#0f172a;">
  📊 個股 / 指數技術指標詳情
</td></tr></table>
"""

    # ── per-ticker cards ───────────────────────────────────────────────────────
    for d in tech_data:
        if "error" in d:
            html += (
                f"<table width='100%' cellpadding='0' cellspacing='0' "
                f"style='border:1px solid #e5e7eb;border-radius:8px;margin-bottom:12px;'>"
                f"<tr><td style='padding:14px 16px;font-size:14px;color:#9ca3af;'>"
                f"{d['label']} ({d['ticker']}) — 資料取得失敗：{d['error']}"
                f"</td></tr></table>\n"
            )
            continue

        vs     = _VSTYLE.get(d["verdict"], _DEFAULT_VSTYLE)
        ai     = ai_map.get(d["ticker"], {})
        chg_c  = "#16a34a" if d["chg_pct"] >= 0 else "#dc2626"
        chg_a  = "▲" if d["chg_pct"] >= 0 else "▼"

        html += f"""
<!-- ── {d['label']} ── -->
<table width="100%" cellpadding="0" cellspacing="0"
  style="border:1px solid {vs['border']};border-radius:10px;margin-bottom:14px;overflow:hidden;">

<!-- card header -->
<tr><td style="background:{vs['bg']};padding:13px 18px;
               border-bottom:1px solid {vs['border']};">
  <table width="100%" cellpadding="0" cellspacing="0"><tr>
    <td>
      <span style="font-size:17px;font-weight:700;color:#0f172a;">{d['label']}</span>
      <span style="font-size:12px;color:#64748b;margin-left:8px;">{d['ticker']}</span>
    </td>
    <td align="right">
      <span style="font-size:20px;font-weight:700;color:#0f172a;">
        {d['price']:,.2f}
      </span>
      <span style="font-size:14px;font-weight:700;color:{chg_c};margin-left:6px;">
        {chg_a}&nbsp;{abs(d['chg_pct']):.2f}%
      </span>
      <span style="background:{vs['badge']};color:#fff;font-size:11px;font-weight:700;
                   padding:3px 11px;border-radius:16px;margin-left:10px;">
        {d['verdict']}
      </span>
    </td>
  </tr></table>
</td></tr>

<!-- indicators row -->
<tr><td style="padding:14px 18px;">
<table width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <!-- RSI -->
    <td width="33%" style="padding:0 10px 0 0;vertical-align:top;">
      <div style="font-size:10px;font-weight:700;color:#64748b;letter-spacing:1px;
                  text-transform:uppercase;margin-bottom:8px;">RSI (14)</div>
      <div>{_rsi_visual(d['rsi'])}</div>
      <div style="font-size:11px;color:#94a3b8;margin-top:5px;">{d['rsi_label']}</div>
    </td>
    <!-- MACD -->
    <td width="34%" style="padding:0 10px;vertical-align:top;
                            border-left:1px solid #f1f5f9;">
      <div style="font-size:10px;font-weight:700;color:#64748b;letter-spacing:1px;
                  text-transform:uppercase;margin-bottom:8px;">MACD (12,26,9)</div>
      <div>{_macd_visual(d['macd_label'], d['macd_hist'])}</div>
      <div style="font-size:11px;color:#94a3b8;margin-top:5px;">
        柱狀圖&nbsp;{d['macd_hist']:+.4f}
      </div>
    </td>
    <!-- Bollinger -->
    <td width="33%" style="padding:0 0 0 10px;vertical-align:top;
                            border-left:1px solid #f1f5f9;">
      <div style="font-size:10px;font-weight:700;color:#64748b;letter-spacing:1px;
                  text-transform:uppercase;margin-bottom:8px;">布林通道 (20,2) %B</div>
      <div>{_bb_visual(d['bb_pct_b'])}</div>
      <div style="font-size:11px;color:#94a3b8;margin-top:5px;">
        {d['bb_label']}&nbsp;|&nbsp;上軌&nbsp;{d['bb_upper']:,.2f}
      </div>
    </td>
  </tr>

  <!-- volume row -->
  <tr><td colspan="3" style="padding-top:12px;border-top:1px solid #f1f5f9;">
    <span style="font-size:12px;color:#64748b;">成交量：</span>
"""
        if d["has_volume"] and d["vol_ratio"] is not None:
            html += (
                f"    <span style='font-size:13px;font-weight:600;color:#0f172a;'>"
                f"{d['vol_flag']} {d['vol_label']}</span>"
                f"    <span style='font-size:12px;color:#94a3b8;margin-left:6px;'>"
                f"（當日 {d['vol_ratio']:.1f}x 20日均量）</span>\n"
            )
        else:
            html += (
                "    <span style='font-size:13px;color:#94a3b8;'>"
                "⚫ 指數成交量不納入異常偵測</span>\n"
            )

        html += "  </td></tr>\n"

        # Claude AI suggestions
        key_signal  = ai.get("key_signal", "")
        suggestion  = ai.get("short_term_suggestion", "")
        stop_note   = ai.get("stop_loss_note", "")

        if key_signal or suggestion:
            html += "  <tr><td colspan='3' style='padding-top:12px;border-top:1px solid #f1f5f9;'>\n"
            if key_signal:
                html += (
                    f"    <div style='font-size:12px;color:#0369a1;margin-bottom:8px;'>"
                    f"<span style='font-weight:700;'>⚡ 關鍵訊號：</span>{key_signal}</div>\n"
                )
            if suggestion:
                html += (
                    f"    <div style='background:#f8fafc;border-left:3px solid #0369a1;"
                    f"padding:10px 14px;border-radius:0 6px 6px 0;font-size:13px;"
                    f"color:#374151;line-height:1.7;margin-bottom:8px;'>"
                    f"<span style='font-weight:700;color:#0369a1;'>💡 短線建議：</span>"
                    f"{suggestion}</div>\n"
                )
            if stop_note:
                html += (
                    f"    <div style='font-size:12px;color:#b45309;'>"
                    f"<span style='font-weight:700;'>🛑 風控提醒：</span>{stop_note}</div>\n"
                )
            html += "  </td></tr>\n"

        html += "</table>\n</td></tr>\n</table>\n"

    # ── risk reminder ──────────────────────────────────────────────────────────
    risk = analysis.get("risk_reminder", "")
    if risk:
        html += f"""<table width="100%" cellpadding="0" cellspacing="0"
  style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;
         margin-top:4px;margin-bottom:24px;">
<tr><td style="padding:14px 18px;">
  <span style="font-size:12px;font-weight:700;color:#c2410c;">⚠ 今日整體風險提示：</span>
  <span style="font-size:13px;color:#7c2d12;line-height:1.7;">{risk}</span>
</td></tr></table>
"""

    # ── footer ─────────────────────────────────────────────────────────────────
    gen_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html += f"""<table width="100%" cellpadding="0" cellspacing="0"
  style="border-top:1px solid #e5e7eb;padding-top:18px;">
<tr><td style="text-align:center;font-size:12px;color:#9ca3af;line-height:2.2;">
  技術指標由 yfinance 數據自行計算（RSI·MACD·布林通道·成交量比），AI 分析僅供參考，不構成投資建議。<br>
  數據來源：Yahoo Finance · Anthropic Claude Haiku &nbsp;|&nbsp; 生成時間：{gen_time}
</td></tr></table>

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
    msg.attach(MIMEText("請使用支援 HTML 的郵件客戶端查看本報告。", "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_bytes())
    print(f"✅ Email sent → {RECIPIENT_EMAIL}")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print(f"🚀 Technical report starting at {datetime.now(timezone.utc).isoformat()}")

    print("  [1/3] Fetching OHLCV and computing indicators...")
    tech_data = fetch_all()
    for d in tech_data:
        status = d.get("error", f"RSI={d.get('rsi')}  verdict={d.get('verdict')}")
        print(f"        {d['label']}: {status}")

    print("  [2/3] Generating Claude analysis...")
    analysis = generate_analysis(tech_data)

    print("  [3/3] Building HTML and sending email...")
    report_date = datetime.now().strftime("%Y年%m月%d日")
    html        = build_html(tech_data, analysis, report_date)
    today_str   = datetime.now().strftime("%Y/%m/%d")
    subject     = f"📉 每日技術分析 | {today_str}"

    send_email(html, subject)
    print("✅ Done.")


if __name__ == "__main__":
    main()
