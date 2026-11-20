# 投資自動報告系統

以 GitHub Actions 排程，串接 Yahoo Finance（yfinance）與 FinMind 市場數據及 Claude API，每日自動產出投資分析報告，並透過 Gmail SMTP 寄送 HTML 格式郵件。本 repo 包含三個獨立的報告：

```
.
├── daily_report.py                    # 每日投資學習報告（持股追蹤、產業輪動、熱點產業）
├── value_investing_report.py          # 價值投資日報
├── technical_report.py                # 技術分析日報
├── requirements.txt
└── .github/workflows/
    ├── daily_report.yml               # 每日 23:00 UTC 排程
    ├── value_investing_report.yml     # 每日 23:00 UTC 排程
    └── technical_report.yml           # 每日 23:30 UTC 排程
```

> 專案心得：實際運行後發現，AI 產出的分析常常看起來合理、但推論有誤，因此數據與邏輯仍需人工核對。

---

## 系統一：價值投資日報

**檔案：** `value_investing_report.py`  
**排程：** 每日 **23:00 UTC**（台北時間 07:00）  
**Workflow：** `value_investing_report.yml`（名稱：`Value Investing Daily Report`）

### 功能

| 區塊 | 內容 |
|------|------|
| 市場表現 | S&P500、Nasdaq、台股加權、USD/TWD、VIX，每個附長線解讀 |
| 總經事件 | 本週重要財經事件摘要 + 對長線投資者的意義 |
| 產業趨勢 | 3 個產業（7 週輪換）、各 2 檔代表股，含 PE vs 5 年均值、52 週位置、估值判斷、風險點 |
| 投資概念 | 每週一個基本面概念（自由現金流、護城河、ROE…，20 週循環） |

### 資料來源

- **股市數據**：`yfinance`
- **財經新聞**：`feedparser`（Yahoo Finance RSS）
- **AI 分析**：Anthropic Claude Haiku（`claude-haiku-4-5-20251001`），繁體中文輸出

---

## 系統二：技術分析日報

**檔案：** `technical_report.py`  
**排程：** 每日 **23:30 UTC**（台北時間 07:30，美台股均已收盤）  
**Workflow：** `technical_report.yml`（名稱：`Technical Analysis Daily Report`）

### 追蹤標的

| 標的 | 代號 |
|------|------|
| S&P 500 | `^GSPC` |
| 台股加權 | `^TWII` |
| 台積電 | `2330.TW` |
| 聯發科 | `2454.TW` |
| 台灣大 | `3045.TW` |

### 技術指標（全部用 pandas/numpy 自行計算，不需 TA-Lib）

| 指標 | 參數 | 說明 |
|------|------|------|
| RSI | 14 日 | Wilder's RSI；>70 超買、<30 超賣 |
| MACD | (12, 26, 9) | 柱狀圖 > 0 為多頭動能，< 0 為空頭 |
| 布林通道 | (20, ±2σ) | %B 位置：>80% 接近上軌，<20% 接近下軌 |
| 成交量異常 | 20 日均量 | 比率 > 2x 標記異常，指數成交量不納入偵測 |

### AI 輸出（Claude Haiku）

每個標的提供：超買／超賣／偏強／偏弱／中性判斷、關鍵訊號、短線操作建議（含支撐壓力位）、停損提醒，以及整體市場風險提示。temperature=0.3 確保分析邏輯一致。

---

## GitHub Secrets 設定

前往 repo → **Settings → Secrets and variables → Actions → New repository secret**，加入以下四個：

| Secret 名稱 | 說明 |
|-------------|------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| `GMAIL_USER` | Gmail 發信地址，例如 `you@gmail.com` |
| `GMAIL_APP_PASSWORD` | Gmail App Password（16 位，需先開啟兩步驟驗證） |
| `RECIPIENT_EMAIL` | 收件信箱（可與 `GMAIL_USER` 相同） |

### 取得 Gmail App Password

1. 登入 Gmail → [myaccount.google.com/security](https://myaccount.google.com/security)
2. 確認已開啟「兩步驟驗證」
3. 搜尋「App passwords」→ 輸入名稱（如 `investment-reports`）→ **Create**
4. 複製 16 位密碼（去除空格後填入 Secret）

---

## 安裝與本機測試

```bash
pip install -r requirements.txt
```

```bash
# macOS / Linux
export ANTHROPIC_API_KEY="sk-ant-..."
export GMAIL_USER="you@gmail.com"
export GMAIL_APP_PASSWORD="abcdabcdabcdabcd"
export RECIPIENT_EMAIL="you@gmail.com"

python value_investing_report.py   # 測試價值投資日報
python technical_report.py         # 測試技術分析日報
```

```powershell
# Windows PowerShell
$env:ANTHROPIC_API_KEY  = "sk-ant-..."
$env:GMAIL_USER         = "you@gmail.com"
$env:GMAIL_APP_PASSWORD = "abcdabcdabcdabcd"
$env:RECIPIENT_EMAIL    = "you@gmail.com"

py value_investing_report.py
py technical_report.py
```

### 手動觸發 GitHub Actions

Actions 頁面 → 選擇 workflow → **Run workflow** → 約 2–4 分鐘後查看信箱。

---

## 依賴套件

```
anthropic>=0.40.0      # Claude API
yfinance>=0.2.36       # 股市數據
feedparser>=6.0.11     # RSS 新聞
pandas>=2.0.0          # 技術指標計算
numpy>=1.26.0          # 技術指標計算
requests>=2.31.0       # HTTP
```
