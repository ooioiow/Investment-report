#!/usr/bin/env python3
"""
不需要 API Key 的測試腳本。
用內建的巴菲特指標資料直接測試 Manim + FFmpeg 管道。

用法：
  py test_demo.py                    # 只生成動畫（需要 Manim）
  py test_demo.py --full             # 動畫 + 靜音合成（需要 Manim + FFmpeg）
  py test_demo.py --quality medium   # 720p（預設 low=480p 較快）
"""

import argparse
import os
import shutil
import subprocess
import sys

# ── 環境診斷（最早執行，確保問題一目瞭然）────────────────────
print(f"[診斷] Python: {sys.executable}")
print(f"[診斷] 工作目錄: {os.getcwd()}")

# 確認 manim 可以 import
try:
    import manim
    print(f"[診斷] manim 版本: {manim.__version__}  OK")
except ImportError:
    print("[錯誤] manim 未安裝，請執行：")
    print(f"       {sys.executable} -m pip install manim")
    sys.exit(1)

# 確認 ffmpeg（--full 模式才需要，但先偵測）
_ffmpeg = shutil.which("ffmpeg")
print(f"[診斷] ffmpeg: {_ffmpeg or '未找到（--full 模式才需要）'}")

from generators.animation_generator import AnimationGenerator
from generators.video_composer import VideoComposer


BUFFETT_DATA = {
    "narration": (
        "你知道股市有沒有泡沫，巴菲特只用一個指標就能判斷嗎？"
        "這個指標叫做巴菲特指標，公式超簡單：股市總市值除以GDP。"
        "就像你買房子，要看房價是不是遠超過建造成本。"
        "2000年科技泡沫，這個指標衝破150%，接著股市崩跌將近一半。"
        "2008年金融海嘯前也是，指標高達140%，然後又是一場大跌。"
        "現在這個指標大約在175%，遠超過合理區間的115%。"
        "記住，這只是一個工具，不是水晶球。但忽視它，你可能會後悔。"
    ),
    "title":    "巴菲特指標",
    "subtitle": "股市泡沫程度的X光機",
    "key_formula": "股市總市值 ÷ 國內生產毛額 × 100%",
    "key_points": [
        "衡量股市整體估值是否偏高",
        "低於75%低估，高於115%要小心",
        "2000和2008崩盤前均超過140%",
    ],
    "metaphor":          "就像用房屋售價除以建造成本，判斷是否買貴了",
    "historical_example":"2000年科技泡沫前指標衝破150%，股市隨後崩跌近50%",
    "conclusion":        "任何指標都只是工具，判斷力才是核心！",
    "risk_zones": {
        "undervalued": "< 75%",
        "fair":        "75% - 115%",
        "overvalued":  "> 115%",
        "danger":      "> 150%",
    },
    "chart_data": {
        "title":   "巴菲特指標歷史走勢（美國）",
        "x_label": "年份",
        "y_label": "指標值 (%)",
        "years":   [2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024],
        "values":  [143,  78,   96,   107,  58,   93,   106,  132,  130,  148,  188,  156,  175],
        "threshold_low":    75,
        "threshold_fair":   115,
        "threshold_danger": 150,
        "current_value":    175,
    },
    "visual_scenes": [
        {"type": "title",      "weight": 0.10, "description": "標題"},
        {"type": "concept",    "weight": 0.20, "description": "概念"},
        {"type": "formula",    "weight": 0.15, "description": "公式"},
        {"type": "chart",      "weight": 0.30, "description": "圖表"},
        {"type": "keypoints",  "weight": 0.15, "description": "重點"},
        {"type": "conclusion", "weight": 0.10, "description": "結語"},
    ],
}


def make_silent_mp3(duration: float, path: str):
    """用 FFmpeg 建立靜音 MP3（測試用）"""
    cmd = ["ffmpeg", "-y",
           "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
           "-t", str(duration),
           "-c:a", "libmp3lame", "-b:a", "128k",
           path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"建立靜音 MP3 失敗：{r.stderr}")


def main():
    parser = argparse.ArgumentParser(description="巴菲特指標 Demo（不需要 API Key）")
    parser.add_argument("--full",    action="store_true",
                        help="完整流程（含 FFmpeg 合成，使用靜音音頻）")
    parser.add_argument("--quality", choices=["low","medium","high"], default="low",
                        help="動畫品質（預設 low=480p 較快）")
    args = parser.parse_args()

    os.makedirs("output",     exist_ok=True)
    os.makedirs("temp",       exist_ok=True)
    os.makedirs("animations", exist_ok=True)

    duration = 55.0
    name     = "巴菲特指標_demo"

    print("=" * 52)
    print("  巴菲特指標 Demo  |  品質:", args.quality)
    print("=" * 52)

    print("\n[1/2] 生成 Manim 動畫...")
    anim = AnimationGenerator(quality=args.quality)
    video_path = anim.generate(BUFFETT_DATA, duration, name)
    print(f"      完成：{video_path}")

    if args.full:
        print("\n[2/2] 合成影片（靜音）...")
        audio_path = os.path.join("temp", f"{name}_silent.mp3")
        make_silent_mp3(duration, audio_path)
        output_path = VideoComposer().compose(video_path, audio_path, name)
        print(f"\n[完成] 最終影片：{output_path}")
    else:
        print(f"\n[完成] 動畫已生成：{video_path}")
        print("  加 --full 可測試 FFmpeg 合成")


if __name__ == "__main__":
    main()
