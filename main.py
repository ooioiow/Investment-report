#!/usr/bin/env python3
"""金融短影音自動生成系統 - 主入口"""

import argparse
import os
import sys
import time
import traceback

# ── 第一件事：強制 stdout/stderr 使用 UTF-8，避免 Windows CP950 吃掉輸出 ──
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def p(msg="", flush=True):
    """帶 flush 的 print，確保每行立刻顯示"""
    print(msg, flush=flush)


def banner(title):
    p("=" * 62)
    p(f"  {title}")
    p("=" * 62)


def step(n, total, msg):
    p(f"\n[{n}/{total}] {msg}")


def ok(msg):
    p(f"      [OK] {msg}")


def info(msg):
    p(f"      {msg}")


def fail(msg):
    p(f"\n[FAIL] {msg}", flush=True)


# ── 環境診斷（最早執行） ──────────────────────────────────────────────────────
p(f"[診斷] Python  : {sys.executable}")
p(f"[診斷] 版本    : {sys.version.split()[0]}")
p(f"[診斷] 工作目錄: {os.getcwd()}")


def check_env_vars():
    required = ["ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY"]
    missing  = [k for k in required if not os.environ.get(k)]
    if missing:
        fail("缺少以下環境變數，請設定後重試：")
        for k in missing:
            p(f"      {k}  <-- 未設定")
        p()
        p("  Windows PowerShell 設定方式：")
        p('      $env:ANTHROPIC_API_KEY  = "sk-ant-..."')
        p('      $env:ELEVENLABS_API_KEY = "..."')
        p()
        p("  注意：每次開新 PowerShell 視窗都要重新設定，")
        p("        或把它們加到系統環境變數（永久生效）。")
        sys.exit(1)

    # 顯示金鑰前 8 碼（確認是否正確）
    for k in required:
        val = os.environ[k]
        masked = val[:8] + "..." if len(val) > 8 else val
        ok(f"{k} = {masked}")


def check_imports():
    """確認所有依賴都能 import"""
    p("\n[前置檢查] 載入模組...")
    modules = [
        ("anthropic",   "anthropic"),
        ("requests",    "requests"),
        ("manim",       "manim"),
    ]
    import shutil
    for display, name in modules:
        try:
            mod = __import__(name)
            ver = getattr(mod, "__version__", "?")
            ok(f"{display} {ver}")
        except ImportError as e:
            fail(f"無法載入 {display}：{e}")
            p(f"      請執行：{sys.executable} -m pip install {name}")
            sys.exit(1)

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        ok(f"ffmpeg  {ffmpeg}")
    else:
        fail("找不到 ffmpeg，請安裝並加入 PATH")
        p("      Windows 下載：https://www.gyan.dev/ffmpeg/builds/")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="金融短影音自動生成系統",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  python main.py
  python main.py --topic 本益比 --audience 大學生
  python main.py --topic 通貨膨脹 --audience 上班族 --quality high
        """,
    )
    parser.add_argument("--topic",    type=str, default="巴菲特指標",
                        help="影片主題（預設：巴菲特指標）")
    parser.add_argument("--audience", type=str, default="高中生",
                        help="目標受眾（預設：高中生）")
    parser.add_argument("--quality",  choices=["low", "medium", "high"], default="medium",
                        help="動畫品質 low=480p / medium=720p / high=1080p（預設：medium）")
    parser.add_argument("--voice-id", type=str, default=None,
                        help="ElevenLabs 聲音 ID（選填）")
    args = parser.parse_args()

    # ── 前置檢查 ──────────────────────────────────────────────
    check_env_vars()
    check_imports()

    # ── 建立目錄 ──────────────────────────────────────────────
    for d in ("output", "temp", "animations"):
        os.makedirs(d, exist_ok=True)

    safe_topic = args.topic.replace(" ", "_").replace("/", "-")
    start_time = time.time()

    banner("金融短影音自動生成系統")
    info(f"主題  : {args.topic}")
    info(f"受眾  : {args.audience}")
    info(f"品質  : {args.quality}")
    p("=" * 62)

    # ── Step 1: 腳本生成 ──────────────────────────────────────
    step(1, 4, "用 Claude API 生成腳本...")
    try:
        from generators.script_generator import ScriptGenerator
        script_gen  = ScriptGenerator()
        script_data = script_gen.generate(args.topic, args.audience)
        narration   = script_data.get("narration", "")
        ok(f"腳本字數  : {len(narration)} 字")
        ok(f"預估時長  : 約 {len(narration) / 3:.0f} 秒")
        ok(f"標題      : {script_data.get('title', '(無)')}")
        ok(f"副標題    : {script_data.get('subtitle', '(無)')}")
        if not narration:
            fail("腳本 narration 欄位為空，請確認 Claude API 回應")
            sys.exit(1)
    except Exception as e:
        fail(f"腳本生成失敗：{e}")
        traceback.print_exc()
        sys.exit(1)

    # ── Step 2: 語音生成 ──────────────────────────────────────
    step(2, 4, "用 ElevenLabs 生成配音...")
    try:
        from generators.voice_generator import VoiceGenerator
        voice_id  = args.voice_id or os.environ.get("ELEVENLABS_VOICE_ID")
        voice_gen = VoiceGenerator(voice_id=voice_id)
        audio_path, duration = voice_gen.generate(script_data["narration"], safe_topic)
        ok(f"音頻路徑  : {audio_path}")
        ok(f"音頻時長  : {duration:.1f} 秒")
        if duration < 1:
            fail(f"音頻時長異常（{duration:.1f}s），請確認 ElevenLabs 回應是否正確")
            sys.exit(1)
    except Exception as e:
        fail(f"配音生成失敗：{e}")
        traceback.print_exc()
        sys.exit(1)

    # ── Step 3: 動畫生成 ──────────────────────────────────────
    step(3, 4, f"用 Manim 生成動畫（{duration:.1f} 秒，品質 {args.quality}）...")
    info("Manim 渲染過程中會有進度條輸出，請耐心等待...")
    try:
        from generators.animation_generator import AnimationGenerator
        anim_gen   = AnimationGenerator(quality=args.quality)
        video_path = anim_gen.generate(script_data, duration, safe_topic)
        ok(f"動畫路徑  : {video_path}")
        size_mb = os.path.getsize(video_path) / 1024 / 1024
        ok(f"動畫大小  : {size_mb:.1f} MB")
    except Exception as e:
        fail(f"動畫生成失敗：{e}")
        traceback.print_exc()
        sys.exit(1)

    # ── Step 4: 影片合成 ──────────────────────────────────────
    step(4, 4, "用 FFmpeg 合成影片...")
    try:
        from generators.video_composer import VideoComposer
        output_path = VideoComposer().compose(video_path, audio_path, safe_topic)
        ok(f"輸出路徑  : {output_path}")
        size_mb = os.path.getsize(output_path) / 1024 / 1024
        ok(f"檔案大小  : {size_mb:.1f} MB")
    except Exception as e:
        fail(f"影片合成失敗：{e}")
        traceback.print_exc()
        sys.exit(1)

    # ── 完成 ───────────────────────────────────────────────────
    elapsed = time.time() - start_time
    p()
    banner(f"完成！耗時 {elapsed:.0f} 秒")
    p(f"  影片位置：{output_path}")
    p("=" * 62)


if __name__ == "__main__":
    main()
