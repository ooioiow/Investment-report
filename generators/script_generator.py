"""腳本生成器 - 使用 Anthropic Claude API 生成金融教育腳本"""

import json
import os
import re

import anthropic


SYSTEM_PROMPT = """你是一位頂尖的金融教育短影音腳本作家，擅長把複雜的金融概念用最淺顯易懂的方式傳遞給不同年齡層的觀眾。
你的腳本特色：
- 開場必須有吸引力的鉤子（Hook），讓人想繼續看
- 善用生活化的比喻（例如：把股市比作菜市場）
- 有具體的歷史案例和數字支撐
- 結尾有清晰的行動指南或思考問題
- 語氣親切自然，像朋友在聊天"""


SCRIPT_PROMPT_TEMPLATE = """請為以下主題生成一個金融教育短影音的完整內容包，所有文字必須是繁體中文：

主題：{topic}
目標受眾：{audience}

腳本要求：
1. 旁白腳本（narration）：{char_count} 字左右，適合配音朗讀
2. 開頭要有吸引人的問題或驚人的數字
3. 必須包含一個生動的比喻
4. 必須有一個真實的歷史案例（包含年份和具體數字）
5. 結尾要有一句讓人記住的話

請以 JSON 格式回覆，格式如下（只回覆 JSON，不要其他文字）：
{{
  "narration": "完整旁白腳本，約{char_count}字，這是配音員會念出來的文字",
  "title": "吸引人的影片標題，10字以內",
  "subtitle": "一句話說明這個指標的用途，20字以內",
  "key_formula": "核心公式或定義（若有數學公式用文字表達，例如：股市總市值 ÷ 國內生產毛額 × 100%）",
  "key_points": [
    "重點一：最重要的概念（15字以內）",
    "重點二：如何解讀（15字以內）",
    "重點三：實際應用提示（15字以內）"
  ],
  "metaphor": "使用的核心比喻描述，一句話",
  "historical_example": "歷史案例的簡短說明，包含年份和數字",
  "conclusion": "讓觀眾帶走的一句話金句，20字以內",
  "risk_zones": {{
    "undervalued": "低估區間描述（例如：< 75%）",
    "fair": "合理區間描述（例如：75%-115%）",
    "overvalued": "高估區間描述（例如：> 115%）",
    "danger": "極度高估描述（例如：> 150%）"
  }},
  "chart_data": {{
    "title": "圖表標題（例如：巴菲特指標歷史走勢）",
    "x_label": "X軸標籤（例如：年份）",
    "y_label": "Y軸標籤（例如：指標值 %）",
    "years": [2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024],
    "values": [143, 78, 95, 105, 58, 93, 105, 132, 129, 148, 185, 155, 175],
    "threshold_low": 75,
    "threshold_fair": 115,
    "threshold_danger": 150,
    "current_value": 175
  }},
  "visual_scenes": [
    {{"type": "title",      "weight": 0.10, "description": "標題場景"}},
    {{"type": "concept",    "weight": 0.20, "description": "概念說明場景"}},
    {{"type": "formula",    "weight": 0.15, "description": "公式展示場景"}},
    {{"type": "chart",      "weight": 0.30, "description": "歷史走勢圖場景"}},
    {{"type": "keypoints",  "weight": 0.15, "description": "重點整理場景"}},
    {{"type": "conclusion", "weight": 0.10, "description": "結語場景"}}
  ]
}}"""


class ScriptGenerator:
    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 環境變數未設定")
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate(self, topic: str, audience: str) -> dict:
        char_count = 170  # ~60 秒 @ 3字/秒

        prompt = SCRIPT_PROMPT_TEMPLATE.format(
            topic=topic,
            audience=audience,
            char_count=char_count,
        )

        print(f"      呼叫 Claude API 生成腳本...")
        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        raw = self._clean_json(raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"      [警告] JSON 解析失敗，嘗試修復... ({e})")
            data = self._fallback_parse(raw, topic)

        return self._validate_and_fill(data, topic)

    def _clean_json(self, text: str) -> str:
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        return text.strip()

    def _fallback_parse(self, text: str, topic: str) -> dict:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return self._default_data(topic)

    def _validate_and_fill(self, data: dict, topic: str) -> dict:
        defaults = self._default_data(topic)
        for key, val in defaults.items():
            if key not in data or not data[key]:
                data[key] = val
        cd = data.get("chart_data", {})
        if not isinstance(cd.get("years"), list) or len(cd.get("years", [])) < 5:
            data["chart_data"] = defaults["chart_data"]
        if not isinstance(data.get("visual_scenes"), list):
            data["visual_scenes"] = defaults["visual_scenes"]
        return data

    def _default_data(self, topic: str) -> dict:
        return {
            "narration": f"今天我們來聊聊{topic}。這是一個非常重要的金融指標，能幫助我們判斷股市是否泡沫化。",
            "title": topic,
            "subtitle": f"認識{topic}的完整指南",
            "key_formula": "股市總市值 ÷ 國內生產毛額 × 100%",
            "key_points": [
                "衡量股市整體估值水準",
                "低於75%為低估，高於115%為高估",
                "長期投資的重要參考指標",
            ],
            "metaphor": "就像用房屋售價除以建造成本，判斷是否買貴了",
            "historical_example": "2008年金融危機前，指標衝破150%，隨後股市崩跌50%",
            "conclusion": "記住：任何指標都只是工具，判斷力才是關鍵！",
            "risk_zones": {
                "undervalued": "< 75%",
                "fair": "75% - 115%",
                "overvalued": "> 115%",
                "danger": "> 150%",
            },
            "chart_data": {
                "title": f"{topic}歷史走勢",
                "x_label": "年份",
                "y_label": "指標值 (%)",
                "years": [2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024],
                "values": [143, 78, 96, 107, 58, 93, 106, 132, 130, 148, 188, 156, 175],
                "threshold_low": 75,
                "threshold_fair": 115,
                "threshold_danger": 150,
                "current_value": 175,
            },
            "visual_scenes": [
                {"type": "title",      "weight": 0.10, "description": "標題場景"},
                {"type": "concept",    "weight": 0.20, "description": "概念說明場景"},
                {"type": "formula",    "weight": 0.15, "description": "公式展示場景"},
                {"type": "chart",      "weight": 0.30, "description": "歷史走勢圖場景"},
                {"type": "keypoints",  "weight": 0.15, "description": "重點整理場景"},
                {"type": "conclusion", "weight": 0.10, "description": "結語場景"},
            ],
        }
