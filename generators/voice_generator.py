"""配音生成器 - 使用 ElevenLabs API 生成中文語音"""

import os
import struct

import requests


ELEVENLABS_MODEL  = "eleven_multilingual_v2"
DEFAULT_VOICE_ID  = "EXAVITQu4vr4xnSDxMaL"   # Bella - 支援多語言含中文


class VoiceGenerator:
    def __init__(self, voice_id: str = None):
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY 環境變數未設定")
        self.api_key = api_key
        self.voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
        self.model    = os.environ.get("ELEVENLABS_MODEL", ELEVENLABS_MODEL)

    def generate(self, text: str, name: str = "audio") -> tuple:
        """生成語音 MP3，回傳 (檔案路徑, 時長秒數)"""
        output_path = os.path.join("temp", f"{name}_voice.mp3")

        print(f"      聲音 ID：{self.voice_id}")
        print(f"      模型：{self.model}")

        audio_bytes = self._call_api(text)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        duration = self._estimate_duration(output_path)
        print(f"      已儲存：{output_path}  ({duration:.1f}s)")
        return output_path, duration

    def _call_api(self, text: str) -> bytes:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "xi-api-key":   self.api_key,
            "Content-Type": "application/json",
            "Accept":       "audio/mpeg",
        }
        payload = {
            "text":       text,
            "model_id":   self.model,
            "voice_settings": {
                "stability":        0.55,
                "similarity_boost": 0.75,
                "style":            0.15,
                "use_speaker_boost": True,
            },
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        if resp.status_code == 401:
            raise ValueError("ElevenLabs API Key 無效，請確認 ELEVENLABS_API_KEY")
        if resp.status_code != 200:
            raise RuntimeError(f"ElevenLabs API 錯誤 {resp.status_code}：{resp.text}")
        return resp.content

    def _estimate_duration(self, path: str) -> float:
        """解析 MP3 幀頭估算時長，失敗則用檔案大小估算"""
        try:
            return self._parse_mp3_duration(path)
        except Exception:
            size = os.path.getsize(path)
            return max(5.0, size / 16000)   # 假設 128kbps ≈ 16KB/s

    def _parse_mp3_duration(self, path: str) -> float:
        with open(path, "rb") as f:
            data = f.read(500_000)   # 掃描前 500KB 即可

        total_dur = 0.0
        frame_cnt = 0
        i = 0
        while i < len(data) - 4:
            if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
                hdr = struct.unpack(">I", data[i:i+4])[0]
                version    = (hdr >> 19) & 0x3
                layer      = (hdr >> 17) & 0x3
                br_idx     = (hdr >> 12) & 0xF
                sr_idx     = (hdr >> 10) & 0x3
                padding    = (hdr >>  9) & 0x1
                if version == 3 and layer == 1:          # MPEG1 Layer3
                    br_tbl = [0,32,40,48,56,64,80,96,112,128,160,192,224,256,320,0]
                    sr_tbl = [44100, 48000, 32000, 0]
                    if 0 < br_idx < 15 and sr_idx < 3:
                        br = br_tbl[br_idx] * 1000
                        sr = sr_tbl[sr_idx]
                        if br and sr:
                            frame_size = 144 * br // sr + padding
                            total_dur += 1152 / sr
                            frame_cnt += 1
                            i += frame_size
                            continue
            i += 1
        if frame_cnt > 10:
            return total_dur
        raise ValueError("MP3 幀解析失敗")
