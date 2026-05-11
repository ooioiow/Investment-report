#!/usr/bin/env python3
from manim import *
import json

_DATA_FILE      = "C:/Users/win11user/Desktop/Claude/animations/巴菲特指標_demo_data.json"
_TOTAL_DURATION = 55.0
_CHINESE_FONT   = "Microsoft YaHei"

with open(_DATA_FILE, encoding="utf-8") as _f:
    DATA = json.load(_f)

TOTAL_DURATION = _TOTAL_DURATION
CHINESE_FONT   = _CHINESE_FONT

# ── 顏色主題 ─────────────────────────────────────────────
BG_COLOR       = "#0D1117"
PANEL_COLOR    = "#161B22"
ACCENT_GOLD    = "#F0C040"
ACCENT_CYAN    = "#58C4DD"
ACCENT_GREEN   = "#4EC97B"
ACCENT_ORANGE  = "#FF9500"
TEXT_PRIMARY   = "#E6EDF3"
TEXT_SECONDARY = "#8B949E"
ZONE_LOW       = "#4EC97B"
ZONE_FAIR      = "#58C4DD"
ZONE_HIGH      = "#FC6255"
ZONE_DANGER    = "#FF4400"


def cn(text, size=36, color=TEXT_PRIMARY, weight=NORMAL):
    return Text(text, font=CHINESE_FONT, font_size=size, color=color, weight=weight)


def scene_dur(kind, fallback=0.167):
    for s in DATA.get("visual_scenes", []):
        if s["type"] == kind:
            return max(2.0, TOTAL_DURATION * s["weight"])
    return max(2.0, TOTAL_DURATION * fallback)


class FinancialVideoScene(Scene):

    def setup(self):
        self.camera.background_color = BG_COLOR

    def construct(self):
        self.scene_title()
        self.scene_concept()
        self.scene_formula()
        self.scene_chart()
        self.scene_keypoints()
        self.scene_conclusion()

    # ── Scene 1: Title ────────────────────────────────────
    def scene_title(self):
        dur = scene_dur("title")
        glow = Circle(radius=3.5, color=ACCENT_GOLD, fill_opacity=0.03,
                      stroke_width=1, stroke_opacity=0.3)
        title = cn(DATA["title"], size=52, color=ACCENT_GOLD, weight=BOLD)
        title.shift(UP * 0.8)
        sub = cn(DATA["subtitle"], size=26, color=TEXT_SECONDARY)
        sub.next_to(title, DOWN, buff=0.45)
        line = Line(LEFT*3, RIGHT*3, color=ACCENT_GOLD, stroke_width=1.5, stroke_opacity=0.6)
        line.next_to(sub, DOWN, buff=0.4)
        tag = cn("金融教育短影音", size=20, color=TEXT_SECONDARY)
        tag.next_to(line, DOWN, buff=0.35)

        self.play(FadeIn(glow, scale=0.8), Write(title), run_time=1.2)
        self.play(FadeIn(sub, shift=UP*0.2), GrowFromCenter(line), run_time=0.8)
        self.play(FadeIn(tag), run_time=0.5)
        self.wait(max(0.2, dur - 2.5))
        self.play(FadeOut(VGroup(glow, title, sub, line, tag)), run_time=0.5)

    # ── Scene 2: Concept ──────────────────────────────────
    def scene_concept(self):
        dur = scene_dur("concept")
        sec = cn("概念說明", size=30, color=ACCENT_CYAN, weight=BOLD)
        sec.to_edge(UP, buff=0.5)
        uline = Line(LEFT*1.2, RIGHT*1.2, color=ACCENT_CYAN, stroke_width=2)
        uline.next_to(sec, DOWN, buff=0.1)

        metaphor = DATA.get("metaphor", "")
        card = RoundedRectangle(width=9, height=1.6, corner_radius=0.2,
                                fill_color=PANEL_COLOR, fill_opacity=1,
                                stroke_color=ACCENT_GOLD, stroke_width=1.5)
        card.shift(UP * 1.2)
        card_txt = cn(metaphor, size=24, color=ACCENT_GOLD)
        card_txt.move_to(card.get_center())

        example = DATA.get("historical_example", "")
        wrapped = [example[i:i+24] for i in range(0, len(example), 24)]
        ex_lines = VGroup(*[
            cn(ln, size=22, color=TEXT_PRIMARY if i==0 else TEXT_SECONDARY)
            for i, ln in enumerate(wrapped)
        ]).arrange(DOWN, buff=0.15, aligned_edge=LEFT)
        ex_lines.shift(DOWN * 1.2)
        ex_lbl = cn("歷史案例", size=20, color=ACCENT_ORANGE)
        ex_lbl.next_to(ex_lines, UP, buff=0.25, aligned_edge=LEFT)

        self.play(FadeIn(sec, shift=DOWN*0.2), GrowFromCenter(uline), run_time=0.7)
        self.play(DrawBorderThenFill(card), run_time=0.8)
        self.play(Write(card_txt), run_time=0.9)
        self.play(FadeIn(ex_lbl, shift=UP*0.1), FadeIn(ex_lines, shift=UP*0.1), run_time=0.8)
        self.wait(max(0.2, dur - 3.2))
        self.play(FadeOut(VGroup(sec, uline, card, card_txt, ex_lbl, ex_lines)), run_time=0.5)

    # ── Scene 3: Formula ──────────────────────────────────
    def scene_formula(self):
        dur = scene_dur("formula")
        sec = cn("核心公式", size=30, color=ACCENT_CYAN, weight=BOLD)
        sec.to_edge(UP, buff=0.5)

        formula = DATA.get("key_formula", "股市總市值 / 國內生產毛額 x 100%")
        box = RoundedRectangle(width=9, height=2.2, corner_radius=0.3,
                               fill_color=PANEL_COLOR, fill_opacity=1,
                               stroke_color=ACCENT_CYAN, stroke_width=2)
        box.shift(UP * 0.5)
        f_txt = cn(formula, size=28, color=ACCENT_GOLD, weight=BOLD)
        f_txt.move_to(box.get_center())
        eq = cn("= 指標數值 (%)", size=22, color=TEXT_SECONDARY)
        eq.next_to(box, DOWN, buff=0.3)

        sep = "÷" if "÷" in formula else ("/" if "/" in formula else None)
        breakdown = VGroup()
        if sep:
            parts = formula.split(sep, 1)
            breakdown = VGroup(
                cn(parts[0].strip(), size=20, color=ACCENT_GREEN),
                cn(sep, size=28, color=TEXT_SECONDARY),
                cn(parts[1].strip(), size=20, color=ACCENT_CYAN),
            ).arrange(RIGHT, buff=0.3)
            breakdown.next_to(eq, DOWN, buff=0.25)

        self.play(Write(sec), run_time=0.6)
        self.play(DrawBorderThenFill(box), run_time=0.8)
        self.play(Write(f_txt), run_time=1.0)
        self.play(FadeIn(eq), run_time=0.5)
        if breakdown:
            self.play(FadeIn(breakdown, shift=UP*0.2), run_time=0.7)
        self.wait(max(0.2, dur - 3.6))
        self.play(FadeOut(VGroup(sec, box, f_txt, eq, breakdown)), run_time=0.5)

    # ── Scene 4: Chart ────────────────────────────────────
    def scene_chart(self):
        dur = scene_dur("chart")
        cd        = DATA.get("chart_data", {})
        years     = cd.get("years",  list(range(2000, 2025, 2)))
        values    = cd.get("values", [100]*len(years))
        th_low    = cd.get("threshold_low",    75)
        th_fair   = cd.get("threshold_fair",   115)
        th_danger = cd.get("threshold_danger", 150)
        current   = cd.get("current_value",    150)
        lbl       = cd.get("title", "歷史走勢")
        y_max     = max(max(values), th_danger) * 1.2

        sec = cn(lbl, size=28, color=ACCENT_CYAN, weight=BOLD)
        sec.to_edge(UP, buff=0.4)

        # numbers_to_include 會觸發 LaTeX；改用純 Text 手動加 Y 軸標籤
        ax = Axes(
            x_range=[0, len(years)-1, 1],
            y_range=[0, y_max, 50],
            x_length=9, y_length=4.2,
            axis_config={"color": TEXT_SECONDARY, "stroke_width": 1.5, "include_tip": False},
            x_axis_config={"include_numbers": False},
            y_axis_config={"include_numbers": False},
        )
        ax.shift(DOWN * 0.3)

        # 手動 Y 軸刻度標籤（純 Text，不需要 LaTeX）
        y_tick_lbls = VGroup(*[
            cn(str(yv)+"%", size=14, color=TEXT_SECONDARY).next_to(ax.c2p(0, yv), LEFT, buff=0.12)
            for yv in [th_low, th_fair, th_danger]
        ])

        yr_lbls = VGroup(*[
            cn(str(yr), size=13, color=TEXT_SECONDARY).next_to(ax.c2p(i,0), DOWN, buff=0.15)
            for i, yr in enumerate(years) if i % 2 == 0
        ])

        def zrect(y0, y1, color, op=0.12):
            p1, p2 = ax.c2p(0,y0), ax.c2p(len(years)-1, y1)
            r = Rectangle(width=abs(p2[0]-p1[0]), height=abs(p2[1]-p1[1]),
                          fill_color=color, fill_opacity=op, stroke_width=0)
            r.move_to([(p1[0]+p2[0])/2, (p1[1]+p2[1])/2, 0])
            return r

        zones = VGroup(
            zrect(0, th_low, ZONE_LOW),
            zrect(th_low, th_fair, ZONE_FAIR),
            zrect(th_fair, th_danger, ZONE_HIGH),
            zrect(th_danger, y_max, ZONE_DANGER, 0.08),
        )

        def dline(y, color, txt):
            dl = DashedLine(ax.c2p(0,y), ax.c2p(len(years)-1,y),
                            color=color, stroke_width=1.5, dash_length=0.12)
            lb = cn(str(y)+"%", size=14, color=color)
            lb.next_to(ax.c2p(len(years)-1, y), RIGHT, buff=0.12)
            return VGroup(dl, lb)

        thresholds = VGroup(
            dline(th_low,    ZONE_LOW,    str(th_low)),
            dline(th_fair,   ZONE_FAIR,   str(th_fair)),
            dline(th_danger, ZONE_DANGER, str(th_danger)),
        )

        data_line = VMobject(color=ACCENT_GOLD, stroke_width=2.5)
        data_line.set_points_as_corners([ax.c2p(i,v) for i,v in enumerate(values)])

        cur_dot = Dot(ax.c2p(len(values)-1, values[-1]), color=ACCENT_GOLD, radius=0.1)
        cur_lbl = cn("現在 "+str(current)+"%", size=17, color=ACCENT_GOLD, weight=BOLD)
        cur_lbl.next_to(cur_dot, UP+RIGHT, buff=0.1)

        legend_items = [
            (ZONE_LOW,    "低估 <"+str(th_low)+"%"),
            (ZONE_FAIR,   "合理 "+str(th_low)+"-"+str(th_fair)+"%"),
            (ZONE_HIGH,   "高估 >"+str(th_fair)+"%"),
            (ZONE_DANGER, "危險 >"+str(th_danger)+"%"),
        ]
        legend = VGroup(*[
            VGroup(Dot(color=c, radius=0.07),
                   cn(t, size=15, color=TEXT_SECONDARY).shift(RIGHT*0.1))
            .arrange(RIGHT, buff=0.1)
            for c, t in legend_items
        ]).arrange(RIGHT, buff=0.35)
        legend.to_edge(DOWN, buff=0.25)

        self.play(Write(sec), run_time=0.5)
        self.play(Create(ax), FadeIn(yr_lbls), FadeIn(y_tick_lbls), run_time=0.7)
        self.play(FadeIn(zones), run_time=0.5)
        self.play(Create(thresholds), run_time=0.7)
        self.play(Create(data_line), run_time=1.5)
        self.play(FadeIn(cur_dot, scale=1.5), Write(cur_lbl), run_time=0.6)
        self.play(FadeIn(legend), run_time=0.5)
        self.wait(max(0.5, dur - 4.5))
        self.play(FadeOut(VGroup(sec, ax, yr_lbls, y_tick_lbls, zones, thresholds,
                                  data_line, cur_dot, cur_lbl, legend)), run_time=0.5)

    # ── Scene 5: Key Points ───────────────────────────────
    def scene_keypoints(self):
        dur    = scene_dur("keypoints")
        points = DATA.get("key_points", [])
        icons  = ["①", "②", "③", "④"]

        sec = cn("重點整理", size=30, color=ACCENT_CYAN, weight=BOLD)
        sec.to_edge(UP, buff=0.5)

        cards = VGroup()
        for i, pt in enumerate(points[:4]):
            card = RoundedRectangle(width=8.5, height=0.95, corner_radius=0.15,
                                    fill_color=PANEL_COLOR, fill_opacity=1,
                                    stroke_color=ACCENT_CYAN, stroke_width=1, stroke_opacity=0.5)
            icon = cn(icons[i], size=26, color=ACCENT_GOLD, weight=BOLD)
            icon.move_to(card.get_left() + RIGHT*0.5)
            txt = cn(pt, size=22, color=TEXT_PRIMARY)
            txt.move_to(card.get_center() + RIGHT*0.3)
            cards.add(VGroup(card, icon, txt))
        cards.arrange(DOWN, buff=0.2)
        cards.next_to(sec, DOWN, buff=0.4)

        rz = DATA.get("risk_zones", {})
        badge_row = VGroup()
        if rz:
            defs = [("低估", rz.get("undervalued","< 75%"),  ZONE_LOW),
                    ("合理", rz.get("fair","75-115%"),        ZONE_FAIR),
                    ("高估", rz.get("overvalued","> 115%"),   ZONE_HIGH),
                    ("危險", rz.get("danger","> 150%"),       ZONE_DANGER)]
            for lbl, val, color in defs:
                bg = RoundedRectangle(width=2.0, height=0.65, corner_radius=0.15,
                                      fill_color=color, fill_opacity=0.25,
                                      stroke_color=color, stroke_width=1.5)
                bt = cn(lbl+"\n"+val, size=16, color=color)
                bt.move_to(bg.get_center())
                badge_row.add(VGroup(bg, bt))
            badge_row.arrange(RIGHT, buff=0.25)
            badge_row.next_to(cards, DOWN, buff=0.3)

        self.play(Write(sec), run_time=0.5)
        for c in cards:
            self.play(FadeIn(c, shift=LEFT*0.3), run_time=0.4)
        if badge_row:
            self.play(FadeIn(badge_row, shift=UP*0.2), run_time=0.6)
        self.wait(max(0.2, dur - len(points)*0.4 - 1.5))
        self.play(FadeOut(VGroup(sec, cards, badge_row)), run_time=0.5)

    # ── Scene 6: Conclusion ───────────────────────────────
    def scene_conclusion(self):
        dur = scene_dur("conclusion")
        conclusion = DATA.get("conclusion", "投資需謹慎，判斷力才是核心！")

        inner = Circle(radius=2.5, color=ACCENT_GOLD,
                       fill_color=PANEL_COLOR, fill_opacity=0.6, stroke_width=0)
        ring  = Circle(radius=2.8, color=ACCENT_GOLD, stroke_width=1.5, stroke_opacity=0.5)
        lbl   = cn("記住", size=36, color=ACCENT_GOLD, weight=BOLD)
        lbl.shift(UP * 0.9)
        con_txt = cn(conclusion, size=28, color=TEXT_PRIMARY, weight=BOLD)
        con_txt.next_to(lbl, DOWN, buff=0.4)
        topic_tag = cn(DATA.get("title",""), size=18, color=TEXT_SECONDARY)
        topic_tag.next_to(con_txt, DOWN, buff=0.5)
        credit = cn("金融教育短影音  ·  AI 自動生成", size=15, color=TEXT_SECONDARY)
        credit.to_edge(DOWN, buff=0.35)

        self.play(GrowFromCenter(inner), Create(ring), run_time=0.8)
        self.play(FadeIn(lbl, scale=1.3), run_time=0.5)
        self.play(Write(con_txt), run_time=1.0)
        self.play(FadeIn(topic_tag), FadeIn(credit), run_time=0.6)
        self.wait(max(0.5, dur - 2.9))
