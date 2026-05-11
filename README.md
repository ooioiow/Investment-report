# 金融短影音自動生成系統

輸入主題和受眾，自動生成 60 秒以內的中文金融教育短影音（MP4）。

```
主題：巴菲特指標  受眾：高中生
         ↓
 [Claude API]  → 中文腳本 + 動畫場景規劃
         ↓
 [ElevenLabs]  → 中文語音 MP3
         ↓
 [Manim]       → 黑板風格動態動畫（6 場景）
         ↓
 [FFmpeg]      → 合成最終 MP4
         ↓
 output/巴菲特指標_final.mp4
```

---

## 安裝

### 1. Python 套件
```bash
pip install -r requirements.txt
```

### 2. 系統工具

FFmpeg（必須）
- Windows: https://www.gyan.dev/ffmpeg/builds/
- Mac: brew install ffmpeg
- Linux: sudo apt install ffmpeg

LaTeX / MiKTeX（Manim 需要）
- Windows: https://miktex.org/download
- Mac: brew install --cask mactex-no-gui
- Linux: sudo apt install texlive-full

中文字體（Linux）: sudo apt install fonts-noto-cjk

### 3. API 金鑰

Anthropic: https://console.anthropic.com → API Keys → Create Key
ElevenLabs: https://elevenlabs.io → 頭像 → Profile + API key

---

## 環境變數

```powershell
# Windows PowerShell
$env:ANTHROPIC_API_KEY  = "sk-ant-xxxxxxxx"
$env:ELEVENLABS_API_KEY = "xxxxxxxxxxxxxxxx"
```

```bash
# macOS / Linux
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxx"
export ELEVENLABS_API_KEY="xxxxxxxxxxxxxxxx"
```

---

## 執行

```bash
# 巴菲特指標 Demo（預設）
py main.py

# 其他主題
py main.py --topic 本益比 --audience 大學生
py main.py --topic 通貨膨脹 --audience 上班族 --quality high

# 不需 API Key 先測試管道
py test_demo.py            # 只測 Manim
py test_demo.py --full     # 測完整管道（靜音音頻）
```

---

## 參數

| 參數 | 說明 | 預設 |
|------|------|------|
| --topic | 金融主題 | 巴菲特指標 |
| --audience | 目標受眾 | 高中生 |
| --quality | low=480p / medium=720p / high=1080p | medium |
| --voice-id | ElevenLabs 聲音 ID | 預設多語言女聲 |

---

## 目錄結構

```
Desktop\Claude\
├── main.py
├── test_demo.py
├── requirements.txt
├── README.md
├── generators\
│   ├── script_generator.py   Claude API
│   ├── voice_generator.py    ElevenLabs
│   ├── animation_generator.py  Manim
│   └── video_composer.py     FFmpeg
├── animations\   暫存 Manim 腳本
├── temp\         暫存音頻+動畫
└── output\       最終 MP4
```

---

## 動畫場景（黑板風格）

| 場景 | 比例 | 內容 |
|------|------|------|
| 標題 | 10% | 金色標題漸入 |
| 概念說明 | 20% | 比喻卡片 + 歷史案例 |
| 核心公式 | 15% | 公式拆解動畫 |
| 歷史走勢圖 | 30% | 動態折線圖 + 四色區間 |
| 重點整理 | 15% | 條列要點 + 風險徽章 |
| 金句結語 | 10% | 帶走的一句話 |
