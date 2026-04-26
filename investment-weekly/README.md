# 📊 投資學習週報系統

每週日晚上 20:00（台北時間）自動寄送 HTML 格式投資學習週報到你的信箱。

## 報告包含

| 區塊 | 內容 |
|------|------|
| 市場表現 | S&P500、Nasdaq、台股加權、USD/TWD、VIX，每個附長線解讀 |
| 總經事件 | 本週重要財經事件摘要 + 對長線投資者的意義 |
| 產業趨勢 | 3 個產業、各 2 檔代表股，含 PE vs 5年均值、52週位置、估值判斷、風險點 |
| 投資概念 | 每週一個基本面概念（自由現金流、護城河、ROE…，20 週循環） |

---

## 快速開始

### 1. Fork / Clone 這個 repo

```bash
git clone https://github.com/YOUR_USERNAME/investment-weekly.git
cd investment-weekly
```

### 2. 取得三個 API 金鑰

#### A. Gemini API Key（Google AI Studio）

1. 前往 [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. 登入 Google 帳號
3. 點擊「**Create API Key**」
4. 選擇一個 Google Cloud Project（或建立新的）
5. 複製產生的 API Key（格式：`AIzaSy...`）
6. **免費額度**：gemini-1.5-flash 每分鐘 15 次請求，每天 1500 次，足夠每週一封

#### B. Gmail App Password（應用程式密碼）

> ⚠️ 一般密碼**無法**用於 SMTP。必須使用 App Password。

1. 登入你的 Gmail 帳號
2. 前往 [https://myaccount.google.com/security](https://myaccount.google.com/security)
3. 確認已開啟「**兩步驟驗證（2-Step Verification）**」（必要條件）
4. 在安全性頁面搜尋「**App passwords**」或「**應用程式密碼**」
5. 點擊進入，在 App name 輸入 `investment-weekly`，點擊「**Create**」
6. 複製顯示的 16 位密碼（格式：`xxxx xxxx xxxx xxxx`，去掉空格後使用）

#### C. yfinance 和 feedparser

不需要 API Key，直接從 Yahoo Finance 公開端點抓取資料。

---

### 3. 設定 GitHub Secrets

1. 前往你的 GitHub repo 頁面
2. 點擊上方「**Settings**」
3. 左側選「**Secrets and variables** → **Actions**」
4. 點擊「**New repository secret**」，依序新增以下四個：

| Secret 名稱 | 說明 | 範例值 |
|-------------|------|--------|
| `GEMINI_API_KEY` | Google AI Studio 的 API Key | `AIzaSyXXXXXXXXXXXX` |
| `GMAIL_USER` | 你的 Gmail 地址（發信人） | `yourname@gmail.com` |
| `GMAIL_APP_PASSWORD` | 剛才產生的 16 位 App Password | `abcdabcdabcdabcd` |
| `RECIPIENT_EMAIL` | 收件人信箱（可以和發信人相同） | `yourname@gmail.com` |

> 💡 `GMAIL_USER` 和 `RECIPIENT_EMAIL` 可以填同一個 Gmail，報告就會寄給自己。

---

### 4. 啟用 GitHub Actions

1. 前往 repo 的「**Actions**」頁面
2. 如果看到提示，點擊「**I understand my workflows, go ahead and enable them**」
3. 排程會在每週日 12:00 UTC（台北時間 20:00）自動執行

#### 立即測試（手動觸發）

1. 點擊 Actions → **Weekly Investment Report**
2. 點擊「**Run workflow**」→「**Run workflow**」
3. 約 2-3 分鐘後查看信箱

---

## 本機測試

```bash
# 建立虛擬環境
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 安裝依賴
pip install -r requirements.txt

# 設定環境變數（Windows PowerShell）
$env:GEMINI_API_KEY     = "你的金鑰"
$env:GMAIL_USER         = "yourname@gmail.com"
$env:GMAIL_APP_PASSWORD = "你的App密碼"
$env:RECIPIENT_EMAIL    = "收件人@gmail.com"

# 執行
python weekly_report.py
```

```bash
# macOS/Linux
export GEMINI_API_KEY="你的金鑰"
export GMAIL_USER="yourname@gmail.com"
export GMAIL_APP_PASSWORD="你的App密碼"
export RECIPIENT_EMAIL="收件人@gmail.com"
python weekly_report.py
```

---

## 技術架構

```
weekly_report.py
│
├── fetch_market_data()      → yfinance：S&P500、Nasdaq、台股、USD/TWD、VIX 週漲跌
├── fetch_news()             → feedparser：Yahoo Finance RSS 最新財經標題
├── fetch_sector_data()      → yfinance：PE、52週高低點、市值
├── select_weekly_sectors()  → 7 個產業輪流，每週顯示 3 個
├── select_weekly_concept()  → 20 個投資概念循環
│
├── generate_report()        → Gemini 1.5 Flash（JSON mode）生成全部分析文字
│                              繁體中文輸出
│
├── build_html_email()       → Table-based HTML，相容 Gmail/Outlook/Apple Mail
└── send_email()             → Gmail SMTP SSL (port 465)
```

### 產業輪換表（7 週一輪）

| 週次 mod 7 | 產業 1 | 產業 2 | 產業 3 |
|:-----------:|--------|--------|--------|
| 0 | AI 與雲端 | 半導體 | 生技醫療 |
| 1 | 半導體 | 生技醫療 | 清潔能源 |
| 2 | 生技醫療 | 清潔能源 | 消費必需品 |
| 3 | 清潔能源 | 消費必需品 | 支付金融 |
| 4 | 消費必需品 | 支付金融 | 台灣供應鏈 |
| 5 | 支付金融 | 台灣供應鏈 | AI 與雲端 |
| 6 | 台灣供應鏈 | AI 與雲端 | 半導體 |

---

## 常見問題

**Q: Gmail 寄信失敗，顯示 SMTPAuthenticationError？**
- 確認已開啟兩步驟驗證
- App Password 必須去除空格（16個連續字母）
- 不要使用一般 Gmail 密碼

**Q: yfinance 抓不到台股（^TWII）？**
- 台股週末及假日無資料，這是正常的
- 腳本有 12 天回溯緩衝，會自動找最近的交易日

**Q: Gemini 回傳不是有效 JSON？**
- 已加入自動清理 markdown fences 的邏輯
- 若仍失敗，報告會顯示錯誤訊息並附原始回應

**Q: 每週 GitHub Actions 執行費用？**
- GitHub Free 方案每月有 2000 分鐘免費額度
- 本腳本每次約 2-4 分鐘，每週一次 = 每月 8-16 分鐘，完全免費

---

## 自訂

- **新增產業/股票**：修改 `ALL_SECTORS` 列表
- **新增投資概念**：在 `INVESTMENT_CONCEPTS` 加入項目
- **換 RSS 來源**：修改 `RSS_FEEDS`（支援任何標準 RSS/Atom feed）
- **換模型**：在 `model = genai.GenerativeModel(...)` 改為 `gemini-1.5-pro` 等

---

## 依賴版本

| 套件 | 用途 |
|------|------|
| `yfinance >= 0.2.36` | 股市數據（PE、52週高低、歷史價格） |
| `feedparser >= 6.0.11` | RSS 新聞解析 |
| `google-generativeai >= 0.7.0` | Gemini API（分析 + 文字生成） |
