"""
Whiteout Survival - Beast Rally Assistant

Checks the march count every few seconds. When the count is not full, it runs a
configurable click sequence to find a beast, start a rally, and handle stamina
prompts.
"""

import json
import os
import re
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import cv2
import numpy as np
import pyautogui
import pygetwindow as gw
from mss import mss
from pynput import keyboard

try:
    from paddleocr import PaddleOCR
except Exception:
    PaddleOCR = None


pyautogui.FAILSAFE = True

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "beast_rally_config.json")

BG = "#f5f7fb"
BG2 = "#ffffff"
FG = "#243047"
FG_DIM = "#7b89a3"
ACCENT = "#4678f5"
GREEN = "#2da57a"
RED = "#dc5965"
YELLOW = "#b57c23"
BORDER = "#dfe6f1"


DEFAULT_CONFIG = {
    "window_title": "",
    "window_slots": [
        {"enabled": True, "title": ""},
        {"enabled": False, "title": ""},
        {"enabled": False, "title": ""},
    ],
    "ref_width": 777,
    "ref_height": 1396,
    "interval_sec": 10.0,
    "click_delay_sec": 0.8,
    "after_search_delay_sec": 1.5,
    "after_rally_delay_sec": 1.0,
    "runtime_limit_enabled": False,
    "runtime_limit_hours": 1.0,
    "one_soldier_enabled": False,
    "beast_level_min": 6,
    "beast_level_max": 8,
    "regions": {
        "march_count": {"rx1": 198, "ry1": 270, "rx2": 280, "ry2": 316},
        "march_cost": {"rx1": 320, "ry1": 1115, "rx2": 460, "ry2": 1160},
        "marching_check": {"rx1": 38, "ry1": 270, "rx2": 132, "ry2": 316},
        "march_time": {"rx1": 285, "ry1": 1210, "rx2": 500, "ry2": 1260},
        "beast_level": {"rx1": 275, "ry1": 1040, "rx2": 500, "ry2": 1100},
    },
    "points": {
        "world_search": [705, 1185],
        "beast_tab": [112, 990],
        "search_button": [390, 1210],
        "rally_button": [390, 1190],
        "start_rally_button": [390, 1190],
        "march_button": [390, 1190],
        "recall_all_button": [180, 1180],
        "soldier_add_button": [575, 940],
        "stamina_prompt_button": [390, 810],
        "stamina_use_button": [390, 1040],
        "beast_level_up": [520, 1100],
        "beast_level_down": [260, 1100],
        "back_button": [55, 85],
    },
}


POINT_LABELS = {
    "world_search": "打开搜索/放大镜",
    "beast_tab": "巨兽页签",
    "search_button": "搜索巨兽",
    "rally_button": "集结按钮",
    "start_rally_button": "发起集结",
    "march_button": "出征",
    "recall_all_button": "全部撤回",
    "soldier_add_button": "士兵加一",
    "stamina_prompt_button": "第一次补充体力",
    "stamina_use_button": "补满体力",
    "beast_level_up": "巨兽等级增加",
    "beast_level_down": "巨兽等级减少",
    "back_button": "返回",
}

REGION_LABELS = {
    "march_count": "行军数区域",
    "march_cost": "出征体力数字区域",
    "marching_check": "二次行军识别区域",
    "march_time": "出征时间识别区域",
    "beast_level": "巨兽等级识别区域",
}


def deep_merge(base, patch):
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config():
    if not os.path.exists(CONFIG_PATH):
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))
        return normalize_config(cfg)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = deep_merge(DEFAULT_CONFIG, json.load(f))
            return normalize_config(cfg)
    except Exception:
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))
        return normalize_config(cfg)


def normalize_config(cfg):
    old_title = cfg.get("window_title", DEFAULT_CONFIG["window_title"])
    slots = cfg.get("window_slots") or []
    fixed = []
    for i in range(3):
        if i < len(slots) and isinstance(slots[i], dict):
            slot = dict(slots[i])
        else:
            slot = {}
        if i == 0 and not slot.get("title"):
            slot["title"] = old_title
        slot.setdefault("title", old_title if i == 0 else "")
        slot.setdefault("enabled", i == 0)
        fixed.append(slot)
    cfg["window_slots"] = fixed
    cfg["window_title"] = fixed[0]["title"]
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def apply_light_theme(root):
    style = ttk.Style()
    style.theme_use("clam")
    style.configure(
        ".",
        background=BG,
        foreground=FG,
        fieldbackground=BG2,
        bordercolor=BORDER,
        darkcolor=BG2,
        lightcolor=BG2,
        troughcolor=BG2,
        selectbackground=ACCENT,
        selectforeground=BG,
        font=("Microsoft YaHei UI", 9),
    )
    style.configure("TLabel", background=BG2, foreground=FG)
    style.configure("TFrame", background=BG2)
    style.configure("TLabelframe", background=BG, foreground=ACCENT, bordercolor=BORDER)
    style.configure("TLabelframe.Label", background=BG, foreground=ACCENT)
    style.configure("TButton", background=BG2, foreground=FG, bordercolor=BORDER, padding=(10, 5))
    style.map("TButton", background=[("active", ACCENT)], foreground=[("active", BG)])
    style.configure("Green.TButton", background="#4678f5", foreground="white")
    style.configure("Red.TButton", background="#fff1f2", foreground=RED)
    style.configure("Yellow.TButton", background="#f0f4fb", foreground=YELLOW)
    style.configure("Title.TLabel", font=("Microsoft YaHei UI", 15, "bold"))
    style.configure("Dim.TLabel", foreground=FG_DIM)
    style.configure("Green.TLabel", foreground=GREEN)
    style.configure("Red.TLabel", foreground=RED)
    style.configure("TButton", padding=(12, 8))
    style.configure("TEntry", padding=6, fieldbackground="#f8faff")
    style.configure("TSpinbox", padding=5, fieldbackground="#f8faff", arrowcolor=FG)
    style.configure("TCombobox", padding=6, fieldbackground="#f8faff", arrowcolor=FG)
    style.map("TCombobox", fieldbackground=[("readonly", "#f8faff")], foreground=[("readonly", FG)])
    root.option_add("*TCombobox*Listbox.background", BG2)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "white")
    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", padding=(18, 9), background="#eaf0f8", foreground=FG_DIM)
    style.map("TNotebook.Tab", background=[("selected", BG2)], foreground=[("selected", ACCENT)])
    style.configure("Heading.TLabel", font=("Microsoft YaHei UI", 11, "bold"))
    style.map("TButton", background=[("disabled", "#f1f4f9"), ("active", "#e9f0ff")],
              foreground=[("disabled", "#9aa7bb"), ("active", ACCENT)])
    style.map("Green.TButton", background=[("disabled", "#dce7ff"), ("active", "#3466e3")],
              foreground=[("disabled", "#6485c9"), ("active", "white")])
    root.configure(bg=BG)


class LightDropdown(ttk.Frame):
    def __init__(self, parent, variable, values, width=24, anchor=tk.W, font=None):
        super().__init__(parent)
        self.variable = variable
        self.values = list(values)
        self.display_var = tk.StringVar()
        self.button = ttk.Combobox(self,textvariable=self.display_var,values=self.values,
                                  state="readonly",width=width,font=font or ("Microsoft YaHei UI",9))
        self.button.pack(fill=tk.X)
        self.button.bind("<<ComboboxSelected>>",lambda e:self.variable.set(self.display_var.get()))
        if self.variable.get():
            self.set(self.variable.get())
        elif self.values:
            self.set(self.values[0])

    def get(self):
        return self.variable.get()

    def set(self, value):
        value = str(value)
        self.variable.set(value)
        self.display_var.set(value)


class RoundedCard(tk.Canvas):
    def __init__(self, parent, stretch=False):
        self.stretch = stretch
        super().__init__(parent, bg=BG, highlightthickness=0, bd=0, height=150)
        self.body = ttk.Frame(self, padding=(18, 8))
        self.window = self.create_window(1, 1, window=self.body, anchor="nw")
        self.bind("<Configure>", self._layout)
        self.body.bind("<Configure>", self._height)

    def _height(self, event):
        if not self.stretch:
            self.configure(height=self.body.winfo_reqheight() + 16)

    def _layout(self, event):
        w, h, r = event.width-1, event.height-1, 18
        self.delete("card")
        points = [r,1,w-r,1,w,1,w,r,w,h-r,w,h,w-r,h,r,h,1,h,1,h-r,1,r,1,1]
        self.create_polygon(points, smooth=True, splinesteps=24, fill=BG2,
                            outline=BORDER, tags="card")
        self.tag_lower("card")
        self.coords(self.window, 8, 8)
        self.itemconfigure(self.window, width=max(1,w-16))
        if self.stretch:
            self.itemconfigure(self.window, height=max(1,h-16))

class Toggle(tk.Canvas):
    def __init__(self, parent, variable, command):
        super().__init__(parent, width=48, height=28, bg=BG2, highlightthickness=0,
                         cursor="hand2", takefocus=True)
        self.variable, self.command = variable, command
        self.bind("<Button-1>", self._toggle)
        self.bind("<space>", self._toggle)
        self.bind("<FocusIn>", lambda e: self._draw())
        self.bind("<FocusOut>", lambda e: self._draw())
        variable.trace_add("write", lambda *args: self._draw())
        self._draw()

    def _toggle(self, event=None):
        self.variable.set(not self.variable.get())
        self.command()

    def _draw(self):
        self.delete("all")
        color = ACCENT if self.variable.get() else "#cbd4e3"
        self.create_line(14,14,34,14,fill=color,width=26,capstyle=tk.ROUND)
        x = 34 if self.variable.get() else 14
        self.create_oval(x-9,5,x+9,23,fill="white",outline="white")
        if self.focus_get() == self:
            self.create_rectangle(1,1,47,27,outline=ACCENT,dash=(2,2))


class BeastRallyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("无尽冬日 自动巨兽集结")
        self._setup_window_geometry(1120, 840)
        self.root.resizable(True, True)
        apply_light_theme(root)

        self.cfg = load_config()
        self.sct = None
        self.ocr = None
        self.running = False
        self.paused = False
        self.worker_thread = None
        self.win_left = 0
        self.win_top = 0
        self.win_width = 0
        self.win_height = 0
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.stat_checks = 0
        self.stat_rallies = 0
        self.stat_stamina = 0
        self.stat_ocr_fail = 0
        self.consecutive_march_fail = 0
        self.first_round = True

        self.window_enabled_vars = [
            tk.BooleanVar(value=bool(slot.get("enabled", i == 0)))
            for i, slot in enumerate(self.cfg["window_slots"])
        ]
        self.window_title_vars = [
            tk.StringVar(value=slot.get("title", ""))
            for slot in self.cfg["window_slots"]
        ]
        self.active_window_slot = 0
        self.var_window_title = self.window_title_vars[0]
        self.var_interval = tk.DoubleVar(value=self.cfg["interval_sec"])
        self.var_click_delay = tk.DoubleVar(value=self.cfg["click_delay_sec"])
        self.var_after_search = tk.DoubleVar(value=self.cfg["after_search_delay_sec"])
        self.var_after_rally = tk.DoubleVar(value=self.cfg["after_rally_delay_sec"])
        self.var_runtime_limit = tk.BooleanVar(value=bool(self.cfg.get("runtime_limit_enabled", False)))
        self.var_runtime_hours = tk.DoubleVar(value=float(self.cfg.get("runtime_limit_hours", 1.0)))
        self.var_one_soldier = tk.BooleanVar(value=bool(self.cfg.get("one_soldier_enabled", False)))
        self.var_beast_level_min = tk.StringVar(value=str(self._clamp_level(self.cfg.get("beast_level_min", 6))))
        self.var_beast_level_max = tk.StringVar(value=str(self._clamp_level(self.cfg.get("beast_level_max", 8))))
        self.target_beast_level = self._clamp_level(self.var_beast_level_max.get())
        self.var_point = tk.StringVar(value="world_search")
        self.var_region = tk.StringVar(value="march_count")
        self.var_debug = tk.BooleanVar(value=False)
        self.stop_at_time = None
        self.calibration_delay_sec = 3.0

        self._build_ui()
        self._setup_hotkeys()

    def _setup_window_geometry(self, want_w, want_h):
        # 根据屏幕大小自适应：高 DPI 缩放下也不超出屏幕，并居中显示
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        w = min(want_w, screen_w - 40)
        h = min(want_h, screen_h - 80)
        x = max(0, (screen_w - w) // 2)
        y = max(0, (screen_h - h) // 2 - 20)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(480, 480)

    def _build_ui(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill=tk.X, padx=26, pady=(12,10))
        tk.Label(header, text="巨兽集结助手", font=("Microsoft YaHei UI",21,"bold"), bg=BG, fg=FG).pack(anchor="w")
        tk.Label(header, text="无尽冬日 / 寒霜启示录  ·  Whiteout Survival", font=("Microsoft YaHei UI",9), bg=BG, fg=FG_DIM).pack(anchor="w", pady=(5,0))
        columns = tk.Frame(self.root, bg=BG)
        columns.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0,12))
        columns.columnconfigure(0, weight=1, uniform="columns")
        columns.columnconfigure(1, weight=1, uniform="columns")
        columns.rowconfigure(0, weight=1)
        left_panel = tk.Frame(columns,bg=BG)
        left_panel.grid(row=0,column=0,sticky="nsew",padx=(0,14))
        self.settings_tabs = ttk.Notebook(left_panel)
        self.settings_tabs.pack(fill=tk.BOTH,expand=True)

        def page(title):
            host = tk.Frame(self.settings_tabs, bg=BG)
            self.settings_tabs.add(host, text=title)
            canvas = tk.Canvas(host, bg=BG, highlightthickness=0, bd=0)
            scroll = ttk.Scrollbar(host, orient="vertical", command=canvas.yview)
            scroll.pack(side=tk.RIGHT,fill=tk.Y)
            canvas.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
            body = tk.Frame(canvas,bg=BG)
            item = canvas.create_window(0,0,window=body,anchor="nw")
            canvas.configure(yscrollcommand=scroll.set)
            body.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.bind("<Configure>",lambda e:canvas.itemconfigure(item,width=e.width))
            return body

        main_page = page("集结设置")
        cal_page = page("校准工具")
        def make_card(parent, title):
            shell = RoundedCard(parent)
            shell.pack(fill=tk.X,pady=(10,0))
            ttk.Label(shell.body,text=title,style="Heading.TLabel").pack(anchor="w",pady=(0,6))
            return shell.body

        win = make_card(main_page,"游戏窗口")
        for i in range(3):
            row=ttk.Frame(win)
            row.pack(fill=tk.X,pady=(0,3))
            ttk.Label(row,text=f"窗口 {i+1}").pack(side=tk.LEFT,padx=(0,8))
            ttk.Entry(row,textvariable=self.window_title_vars[i],width=16).pack(side=tk.LEFT,fill=tk.X,expand=True,padx=(0,8))
            ttk.Button(row,text="检测",command=lambda idx=i:self._detect_window(idx)).pack(side=tk.LEFT,padx=(0,10))
            self._check(row,self.window_enabled_vars[i]).pack(side=tk.RIGHT)
        self.lbl_window=ttk.Label(win,text="未检测窗口",style="Dim.TLabel",wraplength=420)
        self.lbl_window.pack(anchor="w",pady=(2,0))

        params=make_card(main_page,"集结设置")
        row=ttk.Frame(params); row.pack(fill=tk.X)
        self._spin(row,"巡检间隔",self.var_interval,3,60,1)
        self._spin(row,"点击延迟",self.var_click_delay,0.2,3.0,0.1)
        row=ttk.Frame(params); row.pack(fill=tk.X,pady=(8,10))
        self._spin(row,"搜索等待",self.var_after_search,0.5,6.0,0.5)
        self._spin(row,"集结等待",self.var_after_rally,0.5,5.0,0.5)
        row=ttk.Frame(params); row.pack(fill=tk.X)
        ttk.Label(row,text="巨兽等级").pack(side=tk.LEFT,padx=(4,12))
        levels=[str(i) for i in range(1,9)]
        self.cb_level_min=LightDropdown(row,self.var_beast_level_min,levels,width=5,anchor=tk.CENTER)
        self.cb_level_min.pack(side=tk.LEFT)
        ttk.Label(row,text="至").pack(side=tk.LEFT,padx=10)
        self.cb_level_max=LightDropdown(row,self.var_beast_level_max,levels,width=5,anchor=tk.CENTER)
        self.cb_level_max.pack(side=tk.LEFT)
        tk.Frame(params,bg=BORDER,height=1).pack(fill=tk.X,pady=8)
        row=ttk.Frame(params); row.pack(fill=tk.X)
        self._check(row,self.var_one_soldier,"一兵集结").pack(side=tk.LEFT)
        self._check(row,self.var_debug,"调试截图").pack(side=tk.RIGHT)
        row=ttk.Frame(params); row.pack(fill=tk.X,pady=(8,0))
        self._check(row,self.var_runtime_limit,"限时运行").pack(side=tk.LEFT,padx=(0,12))
        self._spin(row,"小时",self.var_runtime_hours,0.1,24,0.1)

        ctrl=make_card(left_panel,"运行控制")
        row=ttk.Frame(ctrl); row.pack(fill=tk.X)
        self.btn_start=ttk.Button(row,text="开始 F5",style="Green.TButton",command=self._toggle_run)
        self.btn_start.pack(side=tk.LEFT,fill=tk.X,expand=True,padx=(0,8))
        self.btn_pause=ttk.Button(row,text="暂停 F6",style="Yellow.TButton",command=self._toggle_pause,state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT,padx=(0,8))
        self.btn_stop=ttk.Button(row,text="停止",style="Red.TButton",command=self._stop,state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT)
        ttk.Button(ctrl,text="保存当前配置",command=self._save_from_ui).pack(fill=tk.X,pady=(10,0))

        frm_cal = make_card(cal_page, "点击点校准")
        row_cal_select = ttk.Frame(frm_cal)
        row_cal_select.pack(fill=tk.X)
        point_values = [f"{key} | {POINT_LABELS[key]}" for key in POINT_LABELS]
        self.cb_point = LightDropdown(row_cal_select, self.var_point, point_values, width=42)
        self.cb_point.pack(side=tk.LEFT, padx=4)
        self.cb_point.set(point_values[0])
        row_cal_actions = ttk.Frame(frm_cal)
        row_cal_actions.pack(fill=tk.X, pady=(10,0))
        ttk.Button(row_cal_actions, text="倒计时记录此点", command=self._record_point).pack(side=tk.LEFT, padx=4)
        ttk.Button(row_cal_actions, text="鼠标依次预览", command=self._preview_points).pack(side=tk.LEFT, padx=4)

        frm_region = make_card(cal_page, "识别区域校准")
        row_region_select = ttk.Frame(frm_region)
        row_region_select.pack(fill=tk.X)
        row_region_buttons = ttk.Frame(frm_region)
        row_region_buttons.pack(fill=tk.X, pady=(8, 0))
        row_region_buttons2 = ttk.Frame(frm_region)
        row_region_buttons2.pack(fill=tk.X, pady=(8, 0))
        region_values = [f"{key} | {REGION_LABELS[key]}" for key in REGION_LABELS]
        self.cb_region = LightDropdown(row_region_select, self.var_region, region_values, width=42)
        self.cb_region.pack(side=tk.LEFT, padx=4)
        self.cb_region.set(region_values[0])
        ttk.Button(row_region_buttons, text="倒计时记录左上角", command=lambda: self._record_region_corner("lt")).pack(side=tk.LEFT, padx=4)
        ttk.Button(row_region_buttons, text="倒计时记录右下角", command=lambda: self._record_region_corner("rb")).pack(side=tk.LEFT, padx=4)
        ttk.Button(row_region_buttons2, text="测试识别行军数", command=self._test_march_ocr).pack(side=tk.LEFT, padx=4)
        ttk.Button(row_region_buttons2, text="测试红色", command=self._test_stamina_red).pack(side=tk.LEFT, padx=4)
        ttk.Button(row_region_buttons2, text="测试二次行军", command=self._test_marching_check).pack(side=tk.LEFT, padx=4)
        row_region_buttons3 = ttk.Frame(frm_region)
        row_region_buttons3.pack(fill=tk.X, pady=(8,0))
        ttk.Button(row_region_buttons3, text="测试出征时间", command=self._test_march_time_ocr).pack(side=tk.LEFT, padx=4)
        ttk.Button(row_region_buttons3, text="测试巨兽等级", command=self._test_beast_level_ocr).pack(side=tk.LEFT, padx=4)


        help_card=make_card(cal_page,"执行说明")
        ttk.Label(help_card,text="检查行军数 → 搜索巨兽 → 调整等级 → 发起集结 → 出征。\n行军数达到 6/6 时等待下一轮；出征路程超过 1 分钟，下次在所选范围内降低一级并循环。\n一兵集结会先全部撤回，再添加一名士兵。\n校准前请先停止运行，倒计时期间将鼠标移到目标位置。",wraplength=415,style="Dim.TLabel",justify=tk.LEFT).pack(anchor="w")
        log_card=RoundedCard(columns,stretch=True)
        log_card.grid(row=0,column=1,sticky="nsew")
        body=log_card.body
        ttk.Label(body,text="运行日志",style="Heading.TLabel").pack(anchor="w")
        self.lbl_stats=ttk.Label(body,text="检查 0 | 集结 0 | 补体力 0 | OCR失败 0",style="Dim.TLabel",wraplength=450)
        self.lbl_stats.pack(anchor="w",pady=(8,12))
        self.log_text=scrolledtext.ScrolledText(body,height=10,width=35,wrap=tk.WORD,state=tk.DISABLED,
            bg="#f8faff",fg=FG,insertbackground=FG,selectbackground=ACCENT,selectforeground="white",
            borderwidth=0,highlightthickness=0,font=("Microsoft YaHei UI",9),padx=10,pady=10)
        self.log_text.pack(fill=tk.BOTH,expand=True)
        for tag,color in [("good",GREEN),("bad",RED),("warn",YELLOW),("info",ACCENT)]:
            self.log_text.tag_configure(tag,foreground=color)
        tk.Label(self.root,text="F5 开始 / 停止     F6 暂停 / 继续     F8 停止",bg=BG,fg=FG_DIM,font=("Microsoft YaHei UI",9)).pack(pady=(0,12))

    def _spin(self, parent, label, var, from_, to, inc):
        ttk.Label(parent, text=label).pack(side=tk.LEFT, padx=(4, 2))
        ttk.Spinbox(parent, textvariable=var, from_=from_, to=to, increment=inc, width=5).pack(side=tk.LEFT, padx=(0, 10))

    def _check(self, parent, var, text=""):
        frame=ttk.Frame(parent)
        Toggle(frame,var,lambda:None).pack(side=tk.LEFT)
        if text:
            label=ttk.Label(frame,text=text)
            label.pack(side=tk.LEFT,padx=(7,0))
            label.bind("<Button-1>",lambda e:var.set(not var.get()))
        return frame

    def log(self, msg, tag=None):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
        self.root.after(0, self._append_log, line, tag)

    def _append_log(self, line, tag=None):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, line, tag)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _update_stats(self):
        text = (
            f"检查 {self.stat_checks} | 集结 {self.stat_rallies} | "
            f"补体力 {self.stat_stamina} | OCR失败 {self.stat_ocr_fail} | 目标{self.target_beast_level}级"
        )
        self.root.after(0, self.lbl_stats.configure, {"text": text})

    def _save_from_ui(self):
        slots = []
        for enabled_var, title_var in zip(self.window_enabled_vars, self.window_title_vars):
            slots.append({"enabled": bool(enabled_var.get()), "title": title_var.get().strip()})
        min_level, max_level = self._level_range()
        self.cfg["window_slots"] = slots
        self.cfg["window_title"] = slots[0]["title"]
        self.cfg["interval_sec"] = float(self.var_interval.get())
        self.cfg["click_delay_sec"] = float(self.var_click_delay.get())
        self.cfg["after_search_delay_sec"] = float(self.var_after_search.get())
        self.cfg["after_rally_delay_sec"] = float(self.var_after_rally.get())
        self.cfg["runtime_limit_enabled"] = bool(self.var_runtime_limit.get())
        self.cfg["runtime_limit_hours"] = float(self.var_runtime_hours.get())
        self.cfg["one_soldier_enabled"] = bool(self.var_one_soldier.get())
        self.cfg["beast_level_min"] = min_level
        self.cfg["beast_level_max"] = max_level
        self.var_beast_level_min.set(min_level)
        self.var_beast_level_max.set(max_level)
        if not min_level <= self.target_beast_level <= max_level:
            self.target_beast_level = max_level
        save_config(self.cfg)
        self.log("配置已保存", "good")

    def _enabled_window_indices(self):
        indices = []
        for i, (enabled_var, title_var) in enumerate(zip(self.window_enabled_vars, self.window_title_vars)):
            if enabled_var.get() and title_var.get().strip():
                indices.append(i)
        return indices

    def _detect_window(self, slot_index=None):
        if slot_index is None:
            enabled = self._enabled_window_indices()
            slot_index = enabled[0] if enabled else self.active_window_slot
        title = self.window_title_vars[slot_index].get().strip()
        if not title:
            self.lbl_window.configure(text="请输入窗口标题", style="Red.TLabel")
            return False
        windows = gw.getWindowsWithTitle(title)
        if not windows:
            self.lbl_window.configure(text=f"未找到 {title}", style="Red.TLabel")
            self.log(f"未找到标题包含 '{title}' 的窗口", "bad")
            return False
        win = windows[0]
        if win.isMinimized:
            win.restore()
            time.sleep(0.3)
        try:
            win.activate()
            time.sleep(0.2)
        except Exception:
            pass
        self.win_left = win.left
        self.win_top = win.top
        self.win_width = win.width
        self.win_height = win.height
        self.active_window_slot = slot_index
        self.scale_x = win.width / float(self.cfg["ref_width"])
        self.scale_y = win.height / float(self.cfg["ref_height"])
        self.lbl_window.configure(text=f"窗口{slot_index + 1}: ({win.left},{win.top}) {win.width}x{win.height}", style="Green.TLabel")
        self.log(f"窗口{slot_index + 1} 已绑定：({win.left},{win.top}) {win.width}x{win.height}", "good")
        return True

    def _advance_window_slot(self, pause_before_wrap=False):
        enabled = self._enabled_window_indices()
        if len(enabled) < 2:
            return False
        start_pos = enabled.index(self.active_window_slot) if self.active_window_slot in enabled else -1
        for offset in range(1, len(enabled) + 1):
            next_pos = (start_pos + offset) % len(enabled)
            next_slot = enabled[next_pos]
            wrapped = next_pos == 0
            if wrapped and pause_before_wrap:
                self.log("已跑完一圈，等待下一轮巡检", "info")
                self._sleep_interruptible(float(self.var_interval.get()))
                if not self.running:
                    return True
            self.log(f"切换到窗口{next_slot + 1}", "info")
            if self._detect_window(next_slot):
                return wrapped
        self.log("所有已勾选窗口都未能绑定，暂时保持当前窗口", "warn")
        return False

    def _selected_point_key(self):
        return self.cb_point.get().split("|", 1)[0].strip()

    def _selected_region_key(self):
        return self.cb_region.get().split("|", 1)[0].strip()

    def _record_point(self):
        if not self._detect_window():
            return
        key = self._selected_point_key()

        def capture():
            self._countdown_for_mouse(f"请把鼠标移到：{POINT_LABELS[key]}")
            x, y = pyautogui.position()
            rx = int((x - self.win_left) / self.scale_x)
            ry = int((y - self.win_top) / self.scale_y)
            self.cfg["points"][key] = [rx, ry]
            save_config(self.cfg)
            self.log(f"已记录 {POINT_LABELS[key]}：相对坐标 ({rx}, {ry})", "good")

        threading.Thread(target=capture, daemon=True).start()

    def _record_region_corner(self, corner):
        if not self._detect_window():
            return
        key = self._selected_region_key()
        if corner == "lt":
            name = "左上角"
        else:
            name = "右下角"

        def capture():
            self._countdown_for_mouse(f"请把鼠标移到：{REGION_LABELS[key]} {name}")
            x, y = pyautogui.position()
            rx = int((x - self.win_left) / self.scale_x)
            ry = int((y - self.win_top) / self.scale_y)
            region = self.cfg["regions"][key]
            if corner == "lt":
                region["rx1"] = rx
                region["ry1"] = ry
            else:
                region["rx2"] = rx
                region["ry2"] = ry
            save_config(self.cfg)
            self.log(f"已记录 {REGION_LABELS[key]} {name}：({rx}, {ry})", "good")

        threading.Thread(target=capture, daemon=True).start()

    def _countdown_for_mouse(self, message):
        for left in range(int(self.calibration_delay_sec), 0, -1):
            self.log(f"{message}，{left} 秒后记录鼠标位置", "info")
            time.sleep(1.0)

    def _preview_points(self):
        if not self._detect_window():
            return

        def run():
            for key, label in POINT_LABELS.items():
                pt = self._abs_point(key)
                self.log(f"预览 {label}: {pt}", "info")
                pyautogui.moveTo(pt[0], pt[1], duration=0.15)
                time.sleep(0.8)
            pyautogui.moveTo(100, 100)

        threading.Thread(target=run, daemon=True).start()

    def _abs_point(self, key):
        x, y = self.cfg["points"][key]
        return int(x * self.scale_x) + self.win_left, int(y * self.scale_y) + self.win_top

    def _abs_region(self, key):
        r = self.cfg["regions"][key]
        return {
            "left": int(r["rx1"] * self.scale_x) + self.win_left,
            "top": int(r["ry1"] * self.scale_y) + self.win_top,
            "width": max(1, int((r["rx2"] - r["rx1"]) * self.scale_x)),
            "height": max(1, int((r["ry2"] - r["ry1"]) * self.scale_y)),
        }

    def _grab(self, region_key):
        region = self._abs_region(region_key)
        img = np.array(self.sct.grab(region))[:, :, :3]
        return img

    def _ensure_ocr(self):
        if self.ocr is not None:
            return True
        if PaddleOCR is None:
            self.log("PaddleOCR 未安装，无法识别行军数", "bad")
            return False
        self.log("正在加载 OCR，第一次会慢一点...", "info")
        candidates = [
            {"lang": "ch", "use_textline_orientation": False, "show_log": False},
            {"lang": "ch", "use_textline_orientation": False},
            {"lang": "ch", "use_angle_cls": False, "show_log": False},
            {"lang": "ch", "use_angle_cls": False},
            {"lang": "ch"},
        ]
        model_root = os.path.join(APP_DIR, "models")
        model_options = {}
        for kind in ("det", "rec", "cls"):
            path = os.path.join(model_root, kind)
            if os.path.isfile(os.path.join(path, "inference.pdmodel")):
                model_options[kind + "_model_dir"] = path
        last_exc = None
        for kwargs in candidates:
            kwargs = dict(kwargs, **model_options)
            try:
                self.ocr = PaddleOCR(**kwargs)
                self.log("OCR 已就绪", "good")
                return True
            except Exception as exc:
                last_exc = exc
        self.log(f"OCR 初始化失败：{type(last_exc).__name__}: {last_exc}", "bad")
        return False

    def _ocr_text(self, img):
        if not self._ensure_ocr():
            return ""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        res = self.ocr.ocr(gray, cls=False)
        if not res or not res[0]:
            return ""
        return " ".join(line[1][0] for line in res[0])

    @staticmethod
    def _parse_march_count(text):
        clean = text.replace(" ", "").replace("／", "/").replace("\\", "/")
        clean = clean.replace("O", "0").replace("o", "0").replace("I", "1").replace("l", "1")
        match = re.search(r"(\d)\s*/\s*(\d)", clean)
        if match:
            return int(match.group(1)), int(match.group(2))
        digits = re.findall(r"\d", clean)
        if len(digits) >= 2:
            return int(digits[0]), int(digits[1])
        return None, None

    @staticmethod
    def _clamp_level(value):
        try:
            level = int(value)
        except Exception:
            level = 1
        return max(1, min(8, level))

    def _level_range(self):
        min_level = self._clamp_level(self.var_beast_level_min.get())
        max_level = self._clamp_level(self.var_beast_level_max.get())
        if min_level > max_level:
            min_level, max_level = max_level, min_level
        return min_level, max_level

    @staticmethod
    def _parse_travel_time(text):
        clean = text.replace(" ", "")
        clean = clean.replace("O", "0").replace("o", "0").replace("：", ":").replace("﹕", ":")
        colon = re.search(r"(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?", clean)
        if colon:
            first = int(colon.group(1))
            second = int(colon.group(2))
            third = colon.group(3)
            if third is None:
                return first * 60 + second
            return first * 3600 + second * 60 + int(third)

        total = 0
        matched = False
        hour = re.search(r"(\d+)\s*(?:小时|小時|h|H)", clean)
        minute = re.search(r"(\d+)\s*(?:分钟|分鐘|分|m|M)", clean)
        second = re.search(r"(\d+)\s*(?:秒钟|秒|s|S)", clean)
        if hour:
            total += int(hour.group(1)) * 3600
            matched = True
        if minute:
            total += int(minute.group(1)) * 60
            matched = True
        if second:
            total += int(second.group(1))
            matched = True
        return total if matched else None

    @staticmethod
    def _format_seconds(seconds):
        if seconds is None:
            return "未知"
        minutes, sec = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{sec:02d}"
        return f"{minutes}:{sec:02d}"

    @staticmethod
    def _parse_beast_level(text):
        clean = text.replace(" ", "")
        clean = clean.replace("O", "0").replace("o", "0").replace("I", "1").replace("l", "1")
        for pattern in (r"(?:Lv|LV|Level|等级|等級|级|級)\D*([1-8])", r"([1-8])\s*(?:级|級)"):
            match = re.search(pattern, clean)
            if match:
                return int(match.group(1))
        digits = re.findall(r"[1-8]", clean)
        if digits:
            return int(digits[0])
        return None

    def _read_march_count(self):
        img = self._grab("march_count")
        if self.var_debug.get():
            self._save_debug_image("march_count", img)
        text = self._ocr_text(img)
        current, max_count = self._parse_march_count(text)
        if current is None:
            self.stat_ocr_fail += 1
            self.log(f"行军数识别失败，OCR='{text}'", "warn")
            return None, None, text
        self.log(f"当前行军数：{current}/{max_count}，OCR='{text}'")
        return current, max_count, text

    def _read_march_time(self):
        img = self._grab("march_time")
        if self.var_debug.get():
            self._save_debug_image("march_time", img)
        text = self._ocr_text(img)
        seconds = self._parse_travel_time(text)
        if seconds is None:
            self.stat_ocr_fail += 1
            self.log(f"出征时间识别失败，OCR='{text}'", "warn")
            return None, text
        self.log(f"出征路程时间：{self._format_seconds(seconds)}，OCR='{text}'")
        return seconds, text

    def _read_beast_level(self):
        img = self._grab("beast_level")
        if self.var_debug.get():
            self._save_debug_image("beast_level", img)
        text = self._ocr_text(img)
        level = self._parse_beast_level(text)
        if level is None:
            self.stat_ocr_fail += 1
            self.log(f"巨兽等级识别失败，OCR='{text}'", "warn")
            return None, text
        self.log(f"当前巨兽等级：{level}，OCR='{text}'")
        return level, text

    def _set_beast_level(self, target_level):
        target_level = self._clamp_level(target_level)
        current_level, _ = self._read_beast_level()
        if current_level is None:
            self.log(f"无法识别当前巨兽等级，暂不点击等级调整；目标仍记为 {target_level} 级", "warn")
            self.target_beast_level = target_level
            self._update_stats()
            return False

        diff = target_level - current_level
        if diff == 0:
            self.target_beast_level = target_level
            self._update_stats()
            self.log(f"巨兽等级已是 {target_level} 级")
            return True

        key = "beast_level_up" if diff > 0 else "beast_level_down"
        for _ in range(abs(diff)):
            self._click(key, delay=0.35)
        self.target_beast_level = target_level
        self._update_stats()
        self.log(f"已尝试把巨兽等级从 {current_level} 调整到 {target_level}", "good")
        return True

    def _advance_target_level_after_far(self):
        min_level, max_level = self._level_range()
        next_level = self.target_beast_level - 1
        if next_level < min_level:
            next_level = max_level
        old_level = self.target_beast_level
        self.target_beast_level = next_level
        self._update_stats()
        self.log(f"路程超过 1 分钟：下次从 {old_level} 级切换到 {next_level} 级", "warn")

    def _check_march_time_for_next_level(self):
        seconds, _ = self._read_march_time()
        self._update_stats()
        if seconds is None:
            return
        if seconds > 60:
            self._advance_target_level_after_far()
        else:
            self.log(f"路程 {self._format_seconds(seconds)} 未超过 1 分钟，继续使用 {self.target_beast_level} 级", "good")

    def _march_cost_is_red(self):
        img = self._grab("march_cost")
        if self.var_debug.get():
            self._save_debug_image("march_cost", img)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        red_mask = (
            cv2.inRange(hsv, (0, 80, 80), (12, 255, 255))
            | cv2.inRange(hsv, (165, 80, 80), (180, 255, 255))
        )
        bright_mask = cv2.inRange(hsv, (0, 0, 70), (180, 255, 255))
        red_pixels = cv2.countNonZero(red_mask)
        bright_pixels = max(1, cv2.countNonZero(bright_mask))
        ratio = red_pixels / bright_pixels
        self.log(f"出征体力数字红色占比：{ratio:.3f}")
        return ratio >= 0.08

    def _test_stamina_red(self):
        if not self._detect_window():
            return
        self.sct = mss()
        is_red = self._march_cost_is_red()
        msg = "检测为红色：体力不足" if is_red else "未检测到红色：体力看起来足够"
        messagebox.showinfo("测试红色", msg)

    def _secondary_has_marching(self):
        img = self._grab("marching_check")
        if self.var_debug.get():
            self._save_debug_image("marching_check", img)
        text = self._ocr_text(img)
        compact = text.replace(" ", "")
        hit = "行军" in compact
        self.log(f"二次行军识别：{'识别到行军' if hit else '未识别到行军'}，OCR='{text}'")
        return hit

    def _test_marching_check(self):
        if not self._detect_window():
            return
        self.sct = mss()
        has_marching = self._secondary_has_marching()
        msg = "检测到行军" if has_marching else "未检测到行军，可视为没有行军在路上"
        messagebox.showinfo("测试二次行军", msg)

    def _test_march_time_ocr(self):
        if not self._detect_window():
            return
        self.sct = mss()
        seconds, text = self._read_march_time()
        if seconds is None:
            messagebox.showwarning("测试出征时间", f"识别失败\nOCR: {text}")
        else:
            messagebox.showinfo("测试出征时间", f"识别结果：{self._format_seconds(seconds)}\nOCR: {text}")

    def _test_beast_level_ocr(self):
        if not self._detect_window():
            return
        self.sct = mss()
        level, text = self._read_beast_level()
        if level is None:
            messagebox.showwarning("测试巨兽等级", f"识别失败\nOCR: {text}")
        else:
            messagebox.showinfo("测试巨兽等级", f"识别结果：{level} 级\nOCR: {text}")

    def _save_debug_image(self, name, img):
        debug_dir = os.path.join(APP_DIR, "beast_rally_debug")
        try:
            os.makedirs(debug_dir, exist_ok=True)
            path = os.path.join(debug_dir, f"{time.strftime('%H%M%S')}_{name}.png")
            # cv2.imwrite 在含中文/日文的路径下会静默失败，改用 imencode + 二进制写入
            ok, buf = cv2.imencode(".png", img)
            if not ok:
                self.log("调试截图编码失败", "warn")
                return
            with open(path, "wb") as f:
                f.write(buf.tobytes())
        except Exception as exc:
            self.log(f"调试截图保存失败：{type(exc).__name__}: {exc}", "warn")

    def _click(self, key, delay=None):
        if delay is None:
            delay = float(self.var_click_delay.get())
        x, y = self._abs_point(key)
        pyautogui.click(x, y)
        pyautogui.moveTo(100, 100)
        self.log(f"点击 {POINT_LABELS[key]}")
        time.sleep(delay)

    def _recover_from_march_ocr_fail(self):
        self.log("行军数 OCR 失败，点击返回尝试回到野外页面", "warn")
        self._click("back_button", delay=1.0)

    def _march_with_optional_one_soldier(self):
        if self.var_one_soldier.get():
            self.log("一兵集结已开启：出征前执行全部撤回 -> 士兵加一", "info")
            self._click("recall_all_button", delay=0.5)
            self._click("soldier_add_button", delay=0.5)
        self._click("march_button", delay=1.2)

    def _refill_stamina_from_march(self):
        self.log("出征体力数字为红色，进入补充体力流程", "warn")
        self._click("march_button", delay=1.2)
        self._click("stamina_prompt_button", delay=0.8)
        self._click("stamina_use_button", delay=1.0)
        self.stat_stamina += 1
        self._update_stats()
        time.sleep(0.4)
        self._click("back_button", delay=1.0)
        self.log("补充体力后已点击返回")
        self._march_with_optional_one_soldier()
        self.log("补充体力后已再次点击出征，交给下一轮巡检处理结果")

    def _launch_rally(self):
        self.log(f"行军未满，开始寻找 {self.target_beast_level} 级巨兽并发起集结", "info")
        self._click("world_search")
        self._click("beast_tab")
        self._set_beast_level(self.target_beast_level)
        self._click("search_button", delay=float(self.var_after_search.get()))
        self._click("rally_button", delay=float(self.var_after_rally.get()))
        self._click("start_rally_button", delay=1.2)
        self._check_march_time_for_next_level()
        if self._march_cost_is_red():
            self._refill_stamina_from_march()
        else:
            self._march_with_optional_one_soldier()
        self.stat_rallies += 1
        self._update_stats()
        self._verify_after_march()
        self.log("集结流程已执行完一轮", "good")

    def _verify_after_march(self):
        # 出征后复查行军数：若连续识别不到，多半是该巨兽已被他人集结、弹出了提示框，
        # 此时点两下返回关掉弹窗，结束本轮。
        time.sleep(0.8)
        for attempt in range(2):
            current, _, _ = self._read_march_count()
            if current is not None:
                return True
            if attempt == 0 and self.running:
                time.sleep(1.0)
        self.log("出征后识别不到行军数，疑似该巨兽已被集结弹窗，点两下返回结束本轮", "warn")
        self._click("back_button", delay=0.8)
        self._click("back_button", delay=0.8)
        return False

    def _test_march_ocr(self):
        if not self._detect_window():
            return
        self.sct = mss()
        current, max_count, text = self._read_march_count()
        if current is None:
            messagebox.showwarning("测试识别", f"识别失败\nOCR: {text}")
        else:
            messagebox.showinfo("测试识别", f"识别结果：{current}/{max_count}\nOCR: {text}")

    def _toggle_run(self):
        if self.running:
            self._stop()
        else:
            self._start()

    def _start(self):
        self._save_from_ui()
        if not self._detect_window():
            return
        self.running = True
        self.paused = False
        self.stat_checks = 0
        self.stat_rallies = 0
        self.stat_stamina = 0
        self.stat_ocr_fail = 0
        self.consecutive_march_fail = 0
        self.first_round = True
        _, max_level = self._level_range()
        self.target_beast_level = max_level
        self.stop_at_time = None
        if self.var_runtime_limit.get():
            hours = max(0.1, float(self.var_runtime_hours.get()))
            self.stop_at_time = time.time() + hours * 3600
            self.log(f"限时运行已开启：{hours:.1f} 小时后自动停止", "info")
        self._update_stats()
        self.btn_start.configure(text="运行中", state=tk.DISABLED)
        self.btn_pause.configure(state=tk.NORMAL)
        self.btn_stop.configure(state=tk.NORMAL)
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def _stop(self):
        was_running = self.running
        self.running = False
        self.paused = False
        self.stop_at_time = None
        self.btn_start.configure(text="开始 F5", state=tk.NORMAL)
        self.btn_pause.configure(text="暂停 F6", state=tk.DISABLED)
        self.btn_stop.configure(text="停止 F8", state=tk.DISABLED)
        if was_running:
            self.log("已停止", "info")

    def _toggle_pause(self):
        if not self.running:
            return
        self.paused = not self.paused
        self.btn_pause.configure(text="继续 F6" if self.paused else "暂停 F6")
        self.log("已暂停" if self.paused else "已继续", "warn" if self.paused else "good")

    def _sleep_interruptible(self, seconds):
        remaining = float(seconds)
        last = time.time()
        while self.running and remaining > 0:
            if self._runtime_expired():
                break
            time.sleep(0.2)
            now = time.time()
            if not self.paused:
                remaining -= now - last
            last = now

    def _runtime_expired(self):
        if self.stop_at_time is None:
            return False
        if time.time() < self.stop_at_time:
            return False
        self.log("限时运行到点，自动停止", "info")
        self.running = False
        return True

    def _worker(self):
        self.sct = mss()
        if not self._ensure_ocr():
            self.root.after(0, self._stop)
            return

        while self.running:
            try:
                if self._runtime_expired():
                    break
                while self.paused and self.running:
                    if self._runtime_expired():
                        break
                    time.sleep(0.2)
                if not self.running:
                    break

                self.stat_checks += 1
                self._update_stats()
                current, max_count, _ = self._read_march_count()
                if current is None:
                    if self.first_round:
                        self.first_round = False
                        self.log("首轮未识别到行军数（可能还没有行军），直接开始搜索巨兽", "info")
                        self._launch_rally()
                        if len(self._enabled_window_indices()) >= 2:
                            self._advance_window_slot(pause_before_wrap=True)
                        else:
                            self._sleep_interruptible(float(self.var_interval.get()))
                        continue
                    self.consecutive_march_fail += 1
                    if self._secondary_has_marching():
                        self._recover_from_march_ocr_fail()
                        self.consecutive_march_fail = 0
                    elif self.consecutive_march_fail >= 3:
                        self.log("行军数连续识别失败 3 次，点击返回尝试恢复界面", "warn")
                        self._click("back_button", delay=1.0)
                        self.consecutive_march_fail = 0
                    else:
                        self.log(f"行军数识别失败（连续第 {self.consecutive_march_fail} 次），本轮跳过", "warn")
                    if len(self._enabled_window_indices()) >= 2:
                        self._advance_window_slot(pause_before_wrap=True)
                    else:
                        self._sleep_interruptible(float(self.var_interval.get()))
                    continue

                self.consecutive_march_fail = 0
                self.first_round = False
                if current >= max_count:
                    self.log("行军已满，等待下一轮", "good")
                else:
                    self._launch_rally()

                if len(self._enabled_window_indices()) >= 2:
                    self._advance_window_slot(pause_before_wrap=True)
                else:
                    self._sleep_interruptible(float(self.var_interval.get()))
            except pyautogui.FailSafeException:
                self.log("紧急停止：鼠标移到了屏幕角落，已停止运行", "bad")
                self.running = False
                break
            except Exception as exc:
                self.log(f"异常：{type(exc).__name__}: {exc}", "bad")
                time.sleep(1.0)

        self.root.after(0, self._stop)

    def _setup_hotkeys(self):
        def on_press(key):
            try:
                if key == keyboard.Key.f5:
                    self.root.after(0, self._toggle_run)
                elif key == keyboard.Key.f6:
                    self.root.after(0, self._toggle_pause)
                elif key == keyboard.Key.f8:
                    self.root.after(0, self._stop)
            except Exception:
                pass

        keyboard.Listener(on_press=on_press, daemon=True).start()


if __name__ == "__main__":
    # 声明高 DPI 感知，避免在 125%/150% 缩放下窗口被放大、模糊或显示不全
    try:
        from ctypes import windll
        try:
            windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            windll.user32.SetProcessDPIAware()
    except Exception:
        pass
    root = tk.Tk()
    BeastRallyApp(root)
    root.mainloop()
