"""影片合成器 - 使用 FFmpeg 合成語音和動畫"""

import os
import shutil
import subprocess


class VideoComposer:
    def __init__(self):
        if not shutil.which("ffmpeg"):
            raise RuntimeError(
                "找不到 ffmpeg！請安裝 FFmpeg 並確保它在 PATH 中。\n"
                "Windows 下載：https://www.gyan.dev/ffmpeg/builds/\n"
                "Mac：brew install ffmpeg\n"
                "Linux：sudo apt install ffmpeg"
            )

    def compose(self, video_path: str, audio_path: str, name: str = "output") -> str:
        output_path = os.path.join("output", f"{name}_final.mp4")

        v_dur = self._duration(video_path)
        a_dur = self._duration(audio_path)
        print(f"      視頻 {v_dur:.2f}s  音頻 {a_dur:.2f}s")

        if abs(v_dur - a_dur) < 0.5:
            self._mux_simple(video_path, audio_path, output_path)
        elif v_dur < a_dur:
            self._mux_loop(video_path, audio_path, a_dur, output_path)
        else:
            self._mux_trim(video_path, audio_path, a_dur, output_path)

        mb = os.path.getsize(output_path) / 1024 / 1024
        print(f"      輸出：{output_path}  ({mb:.1f} MB)")
        return output_path

    # ── FFmpeg 策略 ───────────────────────────────────────
    def _mux_simple(self, v, a, out):
        self._run(["ffmpeg","-y","-i",v,"-i",a,
                   "-c:v","copy","-c:a","aac","-b:a","192k",
                   "-map","0:v:0","-map","1:a:0","-shortest", out], "直接合成")

    def _mux_loop(self, v, a, dur, out):
        self._run(["ffmpeg","-y","-stream_loop","-1","-i",v,"-i",a,
                   "-c:v","libx264","-preset","fast","-crf","23",
                   "-c:a","aac","-b:a","192k",
                   "-t",str(dur+0.5),
                   "-map","0:v:0","-map","1:a:0","-shortest", out], "循環視頻合成")

    def _mux_trim(self, v, a, dur, out):
        self._run(["ffmpeg","-y","-i",v,"-i",a,
                   "-c:v","libx264","-preset","fast","-crf","23",
                   "-c:a","aac","-b:a","192k",
                   "-t",str(dur),
                   "-map","0:v:0","-map","1:a:0", out], "裁剪視頻合成")

    def _run(self, cmd, desc):
        print(f"      FFmpeg {desc}...")
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(f"[FFmpeg stderr]\n{r.stderr[-2000:]}")
            raise RuntimeError(f"FFmpeg 失敗（exit {r.returncode}）")

    def _duration(self, path: str) -> float:
        r = subprocess.run(
            ["ffprobe","-v","error","-show_entries","format=duration",
             "-of","default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True
        )
        try:
            return float(r.stdout.strip())
        except ValueError:
            return 0.0
