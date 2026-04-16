import json
import threading
import time
import tkinter as tk
from dataclasses import asdict, dataclass
from pathlib import Path
from tkinter import colorchooser, messagebox, ttk

from pynput import keyboard, mouse


APP_DIR = Path(__file__).resolve().parent
THEME_FILE = APP_DIR / "theme_settings.json"
PRESETS_FILE = APP_DIR / "theme_presets.json"


@dataclass
class Theme:
    mode: str = "dark"
    background: str = "#0B1220"
    panel: str = "#111827"
    text: str = "#E5E7EB"
    muted: str = "#94A3B8"
    button: str = "#1F2937"
    accent: str = "#3B82F6"
    border: str = "#334155"
    input_bg: str = "#0F172A"
    gradient_on: bool = False
    grad_start: str = "#0B1220"
    grad_end: str = "#1E293B"
    grad_third: str = ""
    grad_dir: str = "top-bottom"


@dataclass
class Clicker:
    interval_ms: int = 100
    click_type: str = "single"
    mouse_button: str = "left"
    start_hotkey: str = "<f6>"
    stop_hotkey: str = "<f7>"
    toggle_hotkey: str = "<f8>"


class ThemeManager:
    def __init__(self) -> None:
        self.theme = Theme()
        self.presets: dict[str, Theme] = {
            "Midnight": Theme(),
            "Ocean": Theme(background="#071A2F", panel="#0D2743", input_bg="#0A223C", accent="#0284C7", border="#1D4E89", text="#E0F2FE", muted="#7DD3FC"),
            "Neon": Theme(background="#0A0A12", panel="#11111B", input_bg="#0B0B14", accent="#22D3EE", border="#155E75", text="#E2E8F0", muted="#67E8F9", button="#172554"),
            "Soft Gray": Theme(mode="light", background="#F1F5F9", panel="#FFFFFF", input_bg="#FFFFFF", accent="#2563EB", border="#CBD5E1", text="#0F172A", muted="#64748B", button="#E2E8F0"),
            "Sunset gradient": Theme(mode="custom", background="#2A1436", panel="#1F112A", input_bg="#180D22", accent="#F97316", border="#7C2D12", text="#FFF7ED", muted="#FDBA74", button="#3B1A2C", gradient_on=True, grad_start="#4C1D95", grad_end="#EA580C", grad_third="#F43F5E", grad_dir="diagonal"),
        }
        self.load()

    def save(self) -> None:
        THEME_FILE.write_text(json.dumps(asdict(self.theme), indent=2), encoding="utf-8")
        custom = {k: asdict(v) for k, v in self.presets.items() if k not in {"Midnight", "Ocean", "Neon", "Soft Gray", "Sunset gradient"}}
        PRESETS_FILE.write_text(json.dumps(custom, indent=2), encoding="utf-8")

    def load(self) -> None:
        if THEME_FILE.exists():
            try:
                self.theme = Theme(**json.loads(THEME_FILE.read_text(encoding="utf-8")))
            except Exception:
                self.theme = Theme()
        if PRESETS_FILE.exists():
            try:
                for name, payload in json.loads(PRESETS_FILE.read_text(encoding="utf-8")).items():
                    self.presets[name] = Theme(**payload)
            except Exception:
                pass

    def blend(self, c1: str, c2: str, t: float) -> str:
        t = max(0.0, min(1.0, t))
        a = tuple(int(c1[i:i + 2], 16) for i in (1, 3, 5))
        b = tuple(int(c2[i:i + 2], 16) for i in (1, 3, 5))
        rgb = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

    def grad_color(self, t: float) -> str:
        th = self.theme
        if th.grad_third:
            if t <= 0.5:
                return self.blend(th.grad_start, th.grad_third, t * 2)
            return self.blend(th.grad_third, th.grad_end, (t - 0.5) * 2)
        return self.blend(th.grad_start, th.grad_end, t)


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AutoClicker")
        self.root.geometry("1060x700")
        self.root.minsize(960, 640)

        self.tm = ThemeManager()
        self.cfg = Clicker()
        self.mouse = mouse.Controller()
        self.running = False
        self.thread: threading.Thread | None = None
        self.hk: keyboard.GlobalHotKeys | None = None
        self.capture: keyboard.Listener | None = None
        self.mods: set[str] = set()

        self._init_vars()
        self._build()
        self._apply_theme()
        self._start_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Configure>", lambda _e: self._draw_bg())

    def _init_vars(self) -> None:
        t = self.tm.theme
        c = self.cfg
        self.interval_var = tk.StringVar(value=str(c.interval_ms))
        self.click_type_var = tk.StringVar(value=c.click_type)
        self.button_var = tk.StringVar(value=c.mouse_button)
        self.start_var = tk.StringVar(value=c.start_hotkey)
        self.stop_var = tk.StringVar(value=c.stop_hotkey)
        self.toggle_var = tk.StringVar(value=c.toggle_hotkey)

        self.mode_var = tk.StringVar(value=t.mode)
        self.bg_var = tk.StringVar(value=t.background)
        self.text_var = tk.StringVar(value=t.text)
        self.button_color_var = tk.StringVar(value=t.button)
        self.accent_var = tk.StringVar(value=t.accent)
        self.border_var = tk.StringVar(value=t.border)
        self.input_var = tk.StringVar(value=t.input_bg)
        self.panel_var = tk.StringVar(value=t.panel)
        self.muted_var = tk.StringVar(value=t.muted)
        self.grad_on_var = tk.BooleanVar(value=t.gradient_on)
        self.grad_start_var = tk.StringVar(value=t.grad_start)
        self.grad_end_var = tk.StringVar(value=t.grad_end)
        self.grad_third_var = tk.StringVar(value=t.grad_third)
        self.grad_dir_var = tk.StringVar(value=t.grad_dir)
        self.preset_name_var = tk.StringVar()
        self.preset_select_var = tk.StringVar(value="Midnight")

    def _build(self) -> None:
        self.bg_canvas = tk.Canvas(self.root, highlightthickness=0, bd=0)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.container = ttk.Frame(self.root, padding=12, style="Root.TFrame")
        self.container.place(x=0, y=0, relwidth=1, relheight=1)
        self.container.columnconfigure(0, weight=1)
        self.container.rowconfigure(1, weight=1)

        top = ttk.Frame(self.container, style="Root.TFrame")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top.columnconfigure(0, weight=1)
        ttk.Label(top, text="AutoClicker", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        self.status = ttk.Label(top, text="Ready", style="Status.TLabel")
        self.status.grid(row=0, column=1, sticky="e")

        self.tabs = ttk.Notebook(self.container, style="App.TNotebook")
        self.tabs.grid(row=1, column=0, sticky="nsew")
        self.tab_clicker = ttk.Frame(self.tabs, style="Root.TFrame")
        self.tab_hotkeys = ttk.Frame(self.tabs, style="Root.TFrame")
        self.tab_appearance = ttk.Frame(self.tabs, style="Root.TFrame")
        self.tab_advanced = ttk.Frame(self.tabs, style="Root.TFrame")
        self.tab_about = ttk.Frame(self.tabs, style="Root.TFrame")
        for name, tab in [("Clicker", self.tab_clicker), ("Hotkeys", self.tab_hotkeys), ("Appearance", self.tab_appearance), ("Advanced", self.tab_advanced), ("About", self.tab_about)]:
            self.tabs.add(tab, text=name)

        self._build_clicker_tab()
        self._build_hotkeys_tab()
        self._build_appearance_tab()
        self._build_simple_tab(self.tab_advanced, "Advanced", "Reserved for advanced controls and future features.")
        self._build_simple_tab(self.tab_about, "About", "AutoClicker with a modern theme system and live customization.")

    def _build_simple_tab(self, tab: ttk.Frame, title: str, desc: str) -> None:
        card = ttk.Frame(tab, padding=12, style="Card.TFrame")
        card.pack(fill="x", padx=6, pady=6)
        ttk.Label(card, text=title, style="Section.TLabel").pack(anchor="w")
        ttk.Label(card, text=desc, style="Body.TLabel").pack(anchor="w", pady=(6, 0))

    def _build_clicker_tab(self) -> None:
        card = ttk.Frame(self.tab_clicker, padding=12, style="Card.TFrame")
        card.pack(fill="x", padx=6, pady=6)
        ttk.Label(card, text="Click Settings", style="Section.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        self._row(card, "Interval (ms)", self.interval_var, 1)
        self._combo(card, "Click Type", self.click_type_var, ["single", "double"], 2)
        self._combo(card, "Mouse Button", self.button_var, ["left", "middle", "right"], 3)
        actions = ttk.Frame(card, style="Card.TFrame")
        actions.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Start", style="Primary.TButton", command=self.start).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Stop", style="Secondary.TButton", command=self.stop).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Apply", style="Secondary.TButton", command=self.apply_clicker).pack(side="left")
        card.columnconfigure(1, weight=1)

    def _build_hotkeys_tab(self) -> None:
        card = ttk.Frame(self.tab_hotkeys, padding=12, style="Card.TFrame")
        card.pack(fill="x", padx=6, pady=6)
        ttk.Label(card, text="Global Hotkeys", style="Section.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        self._row(card, "Start", self.start_var, 1)
        ttk.Button(card, text="Capture", style="Secondary.TButton", command=lambda: self.capture_hotkey("start")).grid(row=1, column=2, sticky="e")
        self._row(card, "Stop", self.stop_var, 2)
        ttk.Button(card, text="Capture", style="Secondary.TButton", command=lambda: self.capture_hotkey("stop")).grid(row=2, column=2, sticky="e")
        self._row(card, "Toggle", self.toggle_var, 3)
        ttk.Button(card, text="Capture", style="Secondary.TButton", command=lambda: self.capture_hotkey("toggle")).grid(row=3, column=2, sticky="e")
        ttk.Button(card, text="Apply Hotkeys", style="Primary.TButton", command=self.apply_hotkeys).grid(row=4, column=0, sticky="w", pady=(8, 0))
        card.columnconfigure(1, weight=1)

    def _build_appearance_tab(self) -> None:
        self.tab_appearance.columnconfigure(0, weight=3)
        self.tab_appearance.columnconfigure(1, weight=2)
        left = ttk.Frame(self.tab_appearance, padding=12, style="Card.TFrame")
        right = ttk.Frame(self.tab_appearance, padding=12, style="Card.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(6, 4), pady=6)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 6), pady=6)
        left.columnconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        ttk.Label(left, text="Appearance", style="Section.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        self._combo(left, "Theme Mode", self.mode_var, ["light", "dark", "custom"], 1)
        self._color(left, "Background", self.bg_var, 2)
        self._color(left, "Text", self.text_var, 3)
        self._color(left, "Button", self.button_color_var, 4)
        self._color(left, "Accent", self.accent_var, 5)
        self._color(left, "Border", self.border_var, 6)
        self._color(left, "Input", self.input_var, 7)
        self._color(left, "Panel", self.panel_var, 8)
        self._color(left, "Muted Text", self.muted_var, 9)
        ttk.Checkbutton(left, text="Enable gradient", variable=self.grad_on_var, style="Card.TCheckbutton").grid(row=10, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self._color(left, "Gradient Start", self.grad_start_var, 11)
        self._color(left, "Gradient End", self.grad_end_var, 12)
        self._color(left, "Gradient Third", self.grad_third_var, 13)
        self._combo(left, "Direction", self.grad_dir_var, ["top-bottom", "left-right", "diagonal", "radial"], 14)
        ttk.Button(left, text="Apply Live", style="Primary.TButton", command=self.apply_theme).grid(row=15, column=0, sticky="w", pady=(8, 0))
        ttk.Button(left, text="Reset", style="Secondary.TButton", command=self.reset_theme).grid(row=15, column=1, sticky="w", pady=(8, 0))

        ttk.Label(right, text="Live Preview", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.preview = tk.Canvas(right, height=220, highlightthickness=0, bd=0)
        self.preview.grid(row=1, column=0, sticky="ew", pady=(6, 8))
        self._row(right, "Preset Name", self.preset_name_var, 2)
        ttk.Button(right, text="Save Preset", style="Secondary.TButton", command=self.save_preset).grid(row=3, column=0, sticky="w")
        self.preset_combo = ttk.Combobox(right, textvariable=self.preset_select_var, values=list(self.tm.presets.keys()), state="readonly")
        self.preset_combo.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(right, text="Load Preset", style="Secondary.TButton", command=self.load_preset).grid(row=5, column=0, sticky="w", pady=(6, 0))

    def _row(self, parent: ttk.Frame, label: str, var: tk.StringVar, row: int) -> None:
        ttk.Label(parent, text=label, style="Body.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", pady=4)
        parent.columnconfigure(1, weight=1)

    def _combo(self, parent: ttk.Frame, label: str, var: tk.StringVar, values: list[str], row: int) -> None:
        ttk.Label(parent, text=label, style="Body.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(parent, textvariable=var, values=values, state="readonly").grid(row=row, column=1, sticky="ew", pady=4)
        parent.columnconfigure(1, weight=1)

    def _color(self, parent: ttk.Frame, label: str, var: tk.StringVar, row: int) -> None:
        self._row(parent, label, var, row)
        ttk.Button(parent, text="Pick", style="Secondary.TButton", command=lambda v=var: self.pick(v)).grid(row=row, column=2, sticky="e", padx=(6, 0))

    def pick(self, var: tk.StringVar) -> None:
        chosen = colorchooser.askcolor(color=var.get())
        if chosen[1]:
            var.set(chosen[1])
            self.apply_theme()

    def apply_theme(self) -> None:
        t = self.tm.theme
        t.mode = self.mode_var.get().strip().lower()
        t.background = self.bg_var.get().strip()
        t.text = self.text_var.get().strip()
        t.button = self.button_color_var.get().strip()
        t.accent = self.accent_var.get().strip()
        t.border = self.border_var.get().strip()
        t.input_bg = self.input_var.get().strip()
        t.panel = self.panel_var.get().strip()
        t.muted = self.muted_var.get().strip()
        t.gradient_on = bool(self.grad_on_var.get())
        t.grad_start = self.grad_start_var.get().strip()
        t.grad_end = self.grad_end_var.get().strip()
        t.grad_third = self.grad_third_var.get().strip()
        t.grad_dir = self.grad_dir_var.get().strip()
        self.tm.save()
        self._apply_theme()

    def reset_theme(self) -> None:
        self.tm.theme = Theme()
        self._init_vars()
        self.apply_theme()

    def save_preset(self) -> None:
        name = self.preset_name_var.get().strip()
        if not name:
            messagebox.showerror("Preset", "Enter a preset name.")
            return
        self.tm.presets[name] = Theme(**asdict(self.tm.theme))
        self.tm.save()
        self.preset_combo.configure(values=list(self.tm.presets.keys()))
        self.preset_select_var.set(name)

    def load_preset(self) -> None:
        name = self.preset_select_var.get().strip()
        if name not in self.tm.presets:
            return
        self.tm.theme = Theme(**asdict(self.tm.presets[name]))
        self._init_vars()
        self._apply_theme()

    def _apply_theme(self) -> None:
        t = self.tm.theme
        st = ttk.Style()
        st.theme_use("clam")
        st.configure("Root.TFrame", background=t.background)
        st.configure("Card.TFrame", background=t.panel, borderwidth=1, relief="solid")
        st.configure("Title.TLabel", background=t.background, foreground=t.text, font=("Segoe UI", 18, "bold"))
        st.configure("Section.TLabel", background=t.panel, foreground=t.text, font=("Segoe UI Semibold", 11))
        st.configure("Body.TLabel", background=t.panel, foreground=t.text, font=("Segoe UI", 10))
        st.configure("Muted.TLabel", background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        st.configure("Status.TLabel", background=t.background, foreground="#22C55E", font=("Segoe UI", 10, "bold"))
        st.configure("Card.TCheckbutton", background=t.panel, foreground=t.text)
        st.configure("Primary.TButton", background=t.accent, foreground="#F8FAFC", borderwidth=0, padding=(10, 8))
        st.configure("Secondary.TButton", background=t.button, foreground=t.text, borderwidth=0, padding=(10, 8))
        st.configure("TEntry", fieldbackground=t.input_bg, foreground=t.text, insertcolor=t.text, bordercolor=t.border)
        st.configure("TCombobox", fieldbackground=t.input_bg, foreground=t.text, background=t.input_bg, bordercolor=t.border)
        st.configure("App.TNotebook", background=t.background)
        st.configure("App.TNotebook.Tab", background=t.button, foreground=t.text, padding=(12, 8))
        st.map("App.TNotebook.Tab", background=[("selected", t.panel)], foreground=[("selected", t.accent)])
        self._draw_bg()
        self._draw_preview()

    def _draw_bg(self) -> None:
        t = self.tm.theme
        w = max(1, self.root.winfo_width())
        h = max(1, self.root.winfo_height())
        self.bg_canvas.delete("all")
        if not t.gradient_on:
            self.bg_canvas.create_rectangle(0, 0, w, h, fill=t.background, outline="")
            return
        if t.grad_dir == "left-right":
            for x in range(w):
                self.bg_canvas.create_line(x, 0, x, h, fill=self.tm.grad_color(x / max(1, w - 1)))
        elif t.grad_dir == "diagonal":
            steps = w + h
            for i in range(steps):
                color = self.tm.grad_color(i / max(1, steps - 1))
                self.bg_canvas.create_line(i, 0, 0, i, fill=color)
        elif t.grad_dir == "radial":
            cx, cy = w // 2, h // 2
            rmax = int((w * w + h * h) ** 0.5 / 2)
            for r in range(rmax, 0, -4):
                self.bg_canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=self.tm.grad_color(1 - r / rmax))
        else:
            for y in range(h):
                self.bg_canvas.create_line(0, y, w, y, fill=self.tm.grad_color(y / max(1, h - 1)))

    def _draw_preview(self) -> None:
        if not hasattr(self, "preview"):
            return
        t = self.tm.theme
        c = self.preview
        c.delete("all")
        w = max(280, c.winfo_width())
        h = max(220, c.winfo_height())
        if t.gradient_on:
            for y in range(h):
                c.create_line(0, y, w, y, fill=self.tm.grad_color(y / max(1, h - 1)))
        else:
            c.create_rectangle(0, 0, w, h, fill=t.background, outline="")
        c.create_rectangle(20, 20, w - 20, h - 20, fill=t.panel, outline=t.border, width=2)
        c.create_text(32, 36, anchor="w", text="Preview", fill=t.text, font=("Segoe UI", 11, "bold"))
        c.create_rectangle(32, 52, 140, 84, fill=t.accent, outline="")
        c.create_text(86, 68, text="Primary", fill="#F8FAFC")
        c.create_rectangle(150, 52, 258, 84, fill=t.button, outline="")
        c.create_text(204, 68, text="Secondary", fill=t.text)

    def apply_clicker(self) -> None:
        self.cfg.interval_ms = max(1, int(self.interval_var.get().strip()))
        self.cfg.click_type = self.click_type_var.get().strip().lower()
        self.cfg.mouse_button = self.button_var.get().strip().lower()
        self.status.configure(text="Settings applied", foreground="#60A5FA")

    def apply_hotkeys(self) -> None:
        self.cfg.start_hotkey = self.start_var.get().strip().lower()
        self.cfg.stop_hotkey = self.stop_var.get().strip().lower()
        self.cfg.toggle_hotkey = self.toggle_var.get().strip().lower()
        self._restart_hotkeys()
        self.status.configure(text="Hotkeys applied", foreground="#60A5FA")

    def capture_hotkey(self, target: str) -> None:
        if self.capture:
            self.capture.stop()
            self.capture = None
        self.mods = set()
        self.status.configure(text=f"Press key for {target}...", foreground="#F59E0B")
        modmap = {
            keyboard.Key.ctrl: "<ctrl>", keyboard.Key.ctrl_l: "<ctrl>", keyboard.Key.ctrl_r: "<ctrl>",
            keyboard.Key.alt: "<alt>", keyboard.Key.alt_l: "<alt>", keyboard.Key.alt_r: "<alt>",
            keyboard.Key.shift: "<shift>", keyboard.Key.shift_l: "<shift>", keyboard.Key.shift_r: "<shift>",
        }

        def on_press(k: keyboard.Key | keyboard.KeyCode) -> bool | None:
            if k in modmap:
                self.mods.add(modmap[k])
                return None
            key = None
            if isinstance(k, keyboard.KeyCode) and k.char:
                key = "<space>" if k.char == " " else k.char.lower()
            elif k is keyboard.Key.space:
                key = "<space>"
            elif hasattr(k, "name") and k.name:
                key = f"<{k.name.lower()}>"
            if not key:
                return None
            hotkey = "+".join(sorted(self.mods) + [key])
            if target == "start":
                self.start_var.set(hotkey)
            elif target == "stop":
                self.stop_var.set(hotkey)
            else:
                self.toggle_var.set(hotkey)
            self.apply_hotkeys()
            return False

        self.capture = keyboard.Listener(on_press=on_press)
        self.capture.start()

    def _mouse_btn(self) -> mouse.Button:
        return {"left": mouse.Button.left, "middle": mouse.Button.middle, "right": mouse.Button.right}[self.cfg.mouse_button]

    def _loop(self) -> None:
        while self.running:
            self.mouse.click(self._mouse_btn(), 2 if self.cfg.click_type == "double" else 1)
            self._safe_status("Running", "#22C55E")
            time.sleep(max(self.cfg.interval_ms / 1000.0, 0.001))

    def _safe_status(self, text: str, color: str) -> None:
        if threading.current_thread() is threading.main_thread():
            self.status.configure(text=text, foreground=color)
        else:
            self.root.after(0, lambda: self.status.configure(text=text, foreground=color))

    def start(self) -> None:
        if self.running:
            return
        self.apply_clicker()
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        self.status.configure(text="Running", foreground="#22C55E")

    def stop(self) -> None:
        self.running = False
        self.status.configure(text="Stopped", foreground="#F59E0B")

    def toggle(self) -> None:
        self.stop() if self.running else self.start()

    def _start_hotkeys(self) -> None:
        self.hk = keyboard.GlobalHotKeys({
            self.cfg.start_hotkey: self.start,
            self.cfg.stop_hotkey: self.stop,
            self.cfg.toggle_hotkey: self.toggle,
        })
        self.hk.start()

    def _restart_hotkeys(self) -> None:
        if self.hk:
            self.hk.stop()
            self.hk = None
        self._start_hotkeys()

    def _on_close(self) -> None:
        self.running = False
        self.tm.save()
        if self.capture:
            self.capture.stop()
        if self.hk:
            self.hk.stop()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
import ctypes
import json
import os
import threading
import time
import tkinter as tk
from dataclasses import asdict, dataclass
from pathlib import Path
from tkinter import colorchooser, messagebox, simpledialog, ttk

from pynput import keyboard, mouse


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
APP_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = APP_DIR / "user_settings.json"
PRESETS_FILE = APP_DIR / "theme_presets.json"


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


@dataclass
class ThemeConfig:
    name: str = "Dark"
    mode: str = "dark"
    background_color: str = "#0B1220"
    text_color: str = "#E5E7EB"
    button_color: str = "#1F2937"
    accent_color: str = "#3B82F6"
    border_color: str = "#334155"
    input_color: str = "#111827"
    panel_color: str = "#0F172A"
    muted_text_color: str = "#94A3B8"
    gradient_enabled: bool = False
    gradient_start: str = "#0B1220"
    gradient_end: str = "#111827"
    gradient_third: str = ""
    gradient_direction: str = "top-bottom"


@dataclass
class ClickerConfig:
    interval_ms: int = 100
    click_type: str = "single"
    mouse_button: str = "left"
    position_mode: str = "current"
    fixed_x: int = 500
    fixed_y: int = 500
    start_hotkey: str = "<f6>"
    stop_hotkey: str = "<f7>"
    toggle_hotkey: str = "<f8>"
    edge_guard_enabled: bool = False
    edge_left_px: int = 20
    edge_right_px: int = 20
    edge_top_px: int = 20
    edge_bottom_px: int = 20
    edge_relative_to_app: bool = False
    only_target_app: bool = False
    target_app_title: str = ""
    target_app_exe: str = ""


class ThemeManager:
    def __init__(self) -> None:
        self.builtins = self._builtin_presets()
        self.custom_presets: dict[str, ThemeConfig] = {}
        self.current_theme = ThemeConfig()
        self.load_presets()
        self.load_last_theme()

    def _builtin_presets(self) -> dict[str, ThemeConfig]:
        return {
            "Midnight": ThemeConfig(name="Midnight", mode="dark"),
            "Ocean": ThemeConfig(
                name="Ocean",
                mode="dark",
                background_color="#071A2F",
                panel_color="#0D2743",
                input_color="#0A223C",
                accent_color="#0284C7",
                border_color="#1D4E89",
                text_color="#E0F2FE",
                muted_text_color="#7DD3FC",
            ),
            "Neon": ThemeConfig(
                name="Neon",
                mode="dark",
                background_color="#0A0A12",
                panel_color="#11111B",
                input_color="#0B0B14",
                accent_color="#22D3EE",
                border_color="#155E75",
                text_color="#E2E8F0",
                muted_text_color="#67E8F9",
                button_color="#172554",
            ),
            "Soft Gray": ThemeConfig(
                name="Soft Gray",
                mode="light",
                background_color="#F1F5F9",
                panel_color="#FFFFFF",
                input_color="#FFFFFF",
                accent_color="#2563EB",
                border_color="#CBD5E1",
                text_color="#0F172A",
                muted_text_color="#64748B",
                button_color="#E2E8F0",
            ),
            "Sunset gradient": ThemeConfig(
                name="Sunset gradient",
                mode="custom",
                background_color="#2A1436",
                panel_color="#1F112A",
                input_color="#180D22",
                accent_color="#F97316",
                border_color="#7C2D12",
                text_color="#FFF7ED",
                muted_text_color="#FDBA74",
                button_color="#3B1A2C",
                gradient_enabled=True,
                gradient_start="#4C1D95",
                gradient_end="#EA580C",
                gradient_third="#F43F5E",
                gradient_direction="diagonal",
            ),
        }

    def all_preset_names(self) -> list[str]:
        return list(self.builtins.keys()) + sorted(self.custom_presets.keys())

    def get_preset(self, name: str) -> ThemeConfig | None:
        if name in self.builtins:
            return ThemeConfig(**asdict(self.builtins[name]))
        if name in self.custom_presets:
            return ThemeConfig(**asdict(self.custom_presets[name]))
        return None

    def save_presets(self) -> None:
        payload = {name: asdict(cfg) for name, cfg in self.custom_presets.items()}
        PRESETS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_presets(self) -> None:
        if not PRESETS_FILE.exists():
            return
        try:
            raw = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
            for name, cfg in raw.items():
                self.custom_presets[name] = ThemeConfig(**cfg)
        except Exception:
            self.custom_presets = {}

    def save_last_theme(self) -> None:
        payload = {"last_theme": asdict(self.current_theme)}
        SETTINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_last_theme(self) -> None:
        if not SETTINGS_FILE.exists():
            return
        try:
            raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if "last_theme" in raw:
                self.current_theme = ThemeConfig(**raw["last_theme"])
        except Exception:
            self.current_theme = ThemeConfig()

    def save_custom_preset(self, name: str, theme: ThemeConfig) -> None:
        copied = ThemeConfig(**asdict(theme))
        copied.name = name
        self.custom_presets[name] = copied
        self.save_presets()

    def is_dark_like(self, theme: ThemeConfig | None = None) -> bool:
        t = theme or self.current_theme
        if t.mode == "dark":
            return True
        if t.mode == "light":
            return False
        return self._luminance(t.background_color) < 0.5

    def validate_color(self, value: str) -> bool:
        if len(value) != 7 or not value.startswith("#"):
            return False
        try:
            int(value[1:], 16)
            return True
        except ValueError:
            return False

    def _hex_to_rgb(self, value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    def _rgb_to_hex(self, rgb: tuple[int, int, int]) -> str:
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

    def _lerp(self, a: int, b: int, t: float) -> int:
        return int(a + (b - a) * t)

    def blend(self, c1: str, c2: str, t: float) -> str:
        r1, g1, b1 = self._hex_to_rgb(c1)
        r2, g2, b2 = self._hex_to_rgb(c2)
        return self._rgb_to_hex(
            (self._lerp(r1, r2, t), self._lerp(g1, g2, t), self._lerp(b1, b2, t))
        )

    def gradient_color(self, theme: ThemeConfig, t: float) -> str:
        t = max(0.0, min(1.0, t))
        if theme.gradient_third and self.validate_color(theme.gradient_third):
            if t <= 0.5:
                return self.blend(theme.gradient_start, theme.gradient_third, t * 2)
            return self.blend(theme.gradient_third, theme.gradient_end, (t - 0.5) * 2)
        return self.blend(theme.gradient_start, theme.gradient_end, t)

    def _luminance(self, color: str) -> float:
        r, g, b = self._hex_to_rgb(color)
        return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


class AutoClickerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AutoClicker")
        self.root.geometry("1080x720")
        self.root.minsize(980, 660)

        self.theme_manager = ThemeManager()
        self.config = ClickerConfig()
        self.mouse_controller = mouse.Controller()
        self.hotkey_listener: keyboard.GlobalHotKeys | None = None
        self.capture_listener: keyboard.Listener | None = None
        self.capture_modifiers: set[str] = set()
        self.running = False
        self.worker_thread: threading.Thread | None = None
        self.app_is_closing = False

        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        self._init_vars()
        self._build_base_ui()
        self._build_tabs()
        self._apply_theme()
        self._bind_events()
        self._start_hotkey_listener()
        self._refresh_status("Ready")

    def _init_vars(self) -> None:
        c = self.config
        t = self.theme_manager.current_theme

        self.interval_var = tk.StringVar(value=str(c.interval_ms))
        self.click_type_var = tk.StringVar(value=c.click_type)
        self.mouse_button_var = tk.StringVar(value=c.mouse_button)
        self.position_mode_var = tk.StringVar(value=c.position_mode)
        self.fixed_x_var = tk.StringVar(value=str(c.fixed_x))
        self.fixed_y_var = tk.StringVar(value=str(c.fixed_y))

        self.start_hotkey_var = tk.StringVar(value=c.start_hotkey)
        self.stop_hotkey_var = tk.StringVar(value=c.stop_hotkey)
        self.toggle_hotkey_var = tk.StringVar(value=c.toggle_hotkey)

        self.edge_guard_var = tk.BooleanVar(value=c.edge_guard_enabled)
        self.edge_left_var = tk.StringVar(value=str(c.edge_left_px))
        self.edge_right_var = tk.StringVar(value=str(c.edge_right_px))
        self.edge_top_var = tk.StringVar(value=str(c.edge_top_px))
        self.edge_bottom_var = tk.StringVar(value=str(c.edge_bottom_px))
        self.edge_relative_var = tk.BooleanVar(value=c.edge_relative_to_app)
        self.only_target_app_var = tk.BooleanVar(value=c.only_target_app)
        self.target_app_var = tk.StringVar(value="No app selected")

        self.theme_mode_var = tk.StringVar(value=t.mode)
        self.bg_color_var = tk.StringVar(value=t.background_color)
        self.text_color_var = tk.StringVar(value=t.text_color)
        self.button_color_var = tk.StringVar(value=t.button_color)
        self.accent_color_var = tk.StringVar(value=t.accent_color)
        self.border_color_var = tk.StringVar(value=t.border_color)
        self.input_color_var = tk.StringVar(value=t.input_color)
        self.panel_color_var = tk.StringVar(value=t.panel_color)
        self.muted_text_var = tk.StringVar(value=t.muted_text_color)
        self.gradient_enabled_var = tk.BooleanVar(value=t.gradient_enabled)
        self.gradient_start_var = tk.StringVar(value=t.gradient_start)
        self.gradient_end_var = tk.StringVar(value=t.gradient_end)
        self.gradient_third_var = tk.StringVar(value=t.gradient_third)
        self.gradient_direction_var = tk.StringVar(value=t.gradient_direction)
        self.preset_name_var = tk.StringVar(value="")
        self.preset_select_var = tk.StringVar(value="")

    def _build_base_ui(self) -> None:
        self.background_canvas = tk.Canvas(self.root, highlightthickness=0, bd=0)
        self.background_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        self.main_container = ttk.Frame(self.root, padding=12, style="Root.TFrame")
        self.main_container.place(x=0, y=0, relwidth=1, relheight=1)
        self.main_container.columnconfigure(0, weight=1)
        self.main_container.rowconfigure(1, weight=1)

        top = ttk.Frame(self.main_container, style="Root.TFrame")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top.columnconfigure(0, weight=1)
        ttk.Label(top, text="AutoClicker", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        self.status_label = ttk.Label(top, text="Ready", style="Status.TLabel")
        self.status_label.grid(row=0, column=1, sticky="e")

        self.notebook = ttk.Notebook(self.main_container, style="App.TNotebook")
        self.notebook.grid(row=1, column=0, sticky="nsew")

    def _build_tabs(self) -> None:
        self.clicker_tab = ttk.Frame(self.notebook, style="Root.TFrame")
        self.hotkeys_tab = ttk.Frame(self.notebook, style="Root.TFrame")
        self.appearance_tab = ttk.Frame(self.notebook, style="Root.TFrame")
        self.advanced_tab = ttk.Frame(self.notebook, style="Root.TFrame")
        self.about_tab = ttk.Frame(self.notebook, style="Root.TFrame")

        self.notebook.add(self.clicker_tab, text="Clicker")
        self.notebook.add(self.hotkeys_tab, text="Hotkeys")
        self.notebook.add(self.appearance_tab, text="Appearance")
        self.notebook.add(self.advanced_tab, text="Advanced")
        self.notebook.add(self.about_tab, text="About")

        self._build_clicker_tab()
        self._build_hotkeys_tab()
        self._build_appearance_tab()
        self._build_advanced_tab()
        self._build_about_tab()

    def _build_clicker_tab(self) -> None:
        self.clicker_tab.columnconfigure(0, weight=1)
        self.clicker_tab.columnconfigure(1, weight=1)

        left_card = ttk.Frame(self.clicker_tab, padding=12, style="Card.TFrame")
        right_card = ttk.Frame(self.clicker_tab, padding=12, style="Card.TFrame")
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 8))
        right_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 8))

        self._card_title(left_card, "Click Settings")
        self._row_entry(left_card, "Interval (ms)", self.interval_var, 1)
        self._row_combo(left_card, "Click Type", self.click_type_var, ["single", "double"], 2)
        self._row_combo(left_card, "Mouse Button", self.mouse_button_var, ["left", "middle", "right"], 3)
        self._row_combo(
            left_card, "Position Mode", self.position_mode_var, ["current", "fixed"], 4, self._toggle_fixed_entries
        )
        self.fixed_x_entry = self._row_entry(left_card, "Fixed X", self.fixed_x_var, 5)
        self.fixed_y_entry = self._row_entry(left_card, "Fixed Y", self.fixed_y_var, 6)

        self._card_title(right_card, "Quick Actions")
        action_row = ttk.Frame(right_card, style="Card.TFrame")
        action_row.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        ttk.Button(action_row, text="Start", style="Primary.TButton", command=self.start_clicking).pack(side="left", padx=(0, 8))
        ttk.Button(action_row, text="Stop", style="Secondary.TButton", command=self.stop_clicking).pack(side="left", padx=(0, 8))
        ttk.Button(action_row, text="Apply", style="Secondary.TButton", command=self.apply_clicker_settings).pack(side="left")

        self.summary_label = ttk.Label(right_card, text="", style="Body.TLabel")
        self.summary_label.grid(row=2, column=0, sticky="w", pady=(6, 0))
        help_label = ttk.Label(
            right_card,
            text="Tip: use Hotkeys tab to capture new keybinds quickly.",
            style="Muted.TLabel",
        )
        help_label.grid(row=3, column=0, sticky="w", pady=(6, 0))

        left_card.columnconfigure(1, weight=1)
        right_card.columnconfigure(0, weight=1)
        self._toggle_fixed_entries()
        self._update_summary()

    def _build_hotkeys_tab(self) -> None:
        card = ttk.Frame(self.hotkeys_tab, padding=12, style="Card.TFrame")
        card.pack(fill="x", padx=6, pady=6)
        self._card_title(card, "Global Hotkeys")

        self._hotkey_row(card, "Start", self.start_hotkey_var, 1, lambda: self._capture_hotkey("start"))
        self._hotkey_row(card, "Stop", self.stop_hotkey_var, 2, lambda: self._capture_hotkey("stop"))
        self._hotkey_row(card, "Toggle", self.toggle_hotkey_var, 3, lambda: self._capture_hotkey("toggle"))
        ttk.Button(card, text="Apply Hotkeys", style="Primary.TButton", command=self.apply_hotkeys).grid(row=4, column=0, sticky="w", pady=(10, 0))
        ttk.Label(card, text="Format example: <ctrl>+<alt>+s", style="Muted.TLabel").grid(row=4, column=1, sticky="e", pady=(10, 0))
        card.columnconfigure(1, weight=1)

    def _build_appearance_tab(self) -> None:
        self.appearance_tab.columnconfigure(0, weight=3)
        self.appearance_tab.columnconfigure(1, weight=2)

        controls = ttk.Frame(self.appearance_tab, padding=12, style="Card.TFrame")
        preview = ttk.Frame(self.appearance_tab, padding=12, style="Card.TFrame")
        controls.grid(row=0, column=0, sticky="nsew", padx=(6, 4), pady=6)
        preview.grid(row=0, column=1, sticky="nsew", padx=(4, 6), pady=6)
        controls.columnconfigure(1, weight=1)
        preview.columnconfigure(0, weight=1)

        self._card_title(controls, "Theme System")
        self._row_combo(controls, "Theme Mode", self.theme_mode_var, ["light", "dark", "custom"], 1, self._set_mode_defaults)
        self._color_row(controls, "Background", self.bg_color_var, 2)
        self._color_row(controls, "Text", self.text_color_var, 3)
        self._color_row(controls, "Button", self.button_color_var, 4)
        self._color_row(controls, "Accent", self.accent_color_var, 5)
        self._color_row(controls, "Border", self.border_color_var, 6)
        self._color_row(controls, "Input", self.input_color_var, 7)
        self._color_row(controls, "Panel", self.panel_color_var, 8)
        self._color_row(controls, "Muted Text", self.muted_text_var, 9)

        ttk.Separator(controls).grid(row=10, column=0, columnspan=3, sticky="ew", pady=8)
        ttk.Checkbutton(
            controls,
            text="Enable gradient background",
            variable=self.gradient_enabled_var,
            command=self._toggle_gradient_controls,
            style="Card.TCheckbutton",
        ).grid(row=11, column=0, columnspan=3, sticky="w")
        self._color_row(controls, "Gradient Start", self.gradient_start_var, 12)
        self._color_row(controls, "Gradient End", self.gradient_end_var, 13)
        self._color_row(controls, "Gradient Third (optional)", self.gradient_third_var, 14)
        self._row_combo(
            controls,
            "Direction",
            self.gradient_direction_var,
            ["top-bottom", "left-right", "diagonal", "radial"],
            15,
        )

        btns = ttk.Frame(controls, style="Card.TFrame")
        btns.grid(row=16, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Button(btns, text="Apply Live", style="Primary.TButton", command=self.apply_theme_from_controls).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Reset Defaults", style="Secondary.TButton", command=self.reset_theme_defaults).pack(side="left")

        self._card_title(preview, "Live Preview")
        self.preview_canvas = tk.Canvas(preview, height=220, highlightthickness=0, bd=0)
        self.preview_canvas.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        self.preview_sample = ttk.Label(
            preview,
            text="Buttons, text, and backgrounds update live.",
            style="Body.TLabel",
        )
        self.preview_sample.grid(row=2, column=0, sticky="w")

        ttk.Separator(preview).grid(row=3, column=0, sticky="ew", pady=8)
        self._row_entry(preview, "Preset Name", self.preset_name_var, 4)
        ttk.Button(preview, text="Save Preset", style="Secondary.TButton", command=self.save_preset).grid(row=5, column=0, sticky="w", pady=(4, 8))
        self.preset_combo = ttk.Combobox(preview, textvariable=self.preset_select_var, state="readonly")
        self.preset_combo.grid(row=6, column=0, sticky="ew")
        ttk.Button(preview, text="Load Preset", style="Secondary.TButton", command=self.load_selected_preset).grid(row=7, column=0, sticky="w", pady=(6, 0))
        self._refresh_preset_combo()
        self._toggle_gradient_controls()

    def _build_advanced_tab(self) -> None:
        card = ttk.Frame(self.advanced_tab, padding=12, style="Card.TFrame")
        card.pack(fill="x", padx=6, pady=6)
        self._card_title(card, "Edge + App Safety")
        ttk.Checkbutton(card, text="Disable near edges", variable=self.edge_guard_var, command=self._toggle_edge_entries, style="Card.TCheckbutton").grid(row=1, column=0, columnspan=3, sticky="w")
        self.edge_left_entry = self._row_entry(card, "Left (px)", self.edge_left_var, 2)
        self.edge_right_entry = self._row_entry(card, "Right (px)", self.edge_right_var, 3)
        self.edge_top_entry = self._row_entry(card, "Top (px)", self.edge_top_var, 4)
        self.edge_bottom_entry = self._row_entry(card, "Bottom (px)", self.edge_bottom_var, 5)
        ttk.Checkbutton(card, text="Apply edge guard to selected app window", variable=self.edge_relative_var, style="Card.TCheckbutton").grid(row=6, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(card, text="Only click when selected app is active", variable=self.only_target_app_var, style="Card.TCheckbutton").grid(row=7, column=0, columnspan=3, sticky="w")
        ttk.Button(card, text="Capture Current App", style="Secondary.TButton", command=self.capture_current_app).grid(row=8, column=0, sticky="w", pady=(8, 0))
        ttk.Label(card, textvariable=self.target_app_var, style="Muted.TLabel").grid(row=8, column=1, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(card, text="Apply Advanced", style="Primary.TButton", command=self.apply_clicker_settings).grid(row=9, column=0, sticky="w", pady=(10, 0))
        card.columnconfigure(1, weight=1)
        self._toggle_edge_entries()

    def _build_about_tab(self) -> None:
        card = ttk.Frame(self.about_tab, padding=12, style="Card.TFrame")
        card.pack(fill="both", expand=True, padx=6, pady=6)
        self._card_title(card, "About")
        text = (
            "AutoClicker\n\n"
            "Design goals:\n"
            "- Clean, modern, minimal UI\n"
            "- Theme customization with live preview\n"
            "- Preset save/load support\n"
            "- Structured for future expansion\n"
        )
        ttk.Label(card, text=text, style="Body.TLabel", justify="left").pack(anchor="w")

    def _card_title(self, parent: ttk.Frame, text: str) -> None:
        ttk.Label(parent, text=text, style="Section.TLabel").grid(row=0, column=0, sticky="w", columnspan=3, pady=(0, 8))

    def _row_entry(self, parent: ttk.Frame, label: str, var: tk.StringVar, row: int) -> ttk.Entry:
        ttk.Label(parent, text=label, style="Body.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
        e = ttk.Entry(parent, textvariable=var)
        e.grid(row=row, column=1, sticky="ew", pady=4, padx=(0, 6))
        parent.columnconfigure(1, weight=1)
        return e

    def _row_combo(
        self,
        parent: ttk.Frame,
        label: str,
        var: tk.StringVar,
        values: list[str],
        row: int,
        callback=None,
    ) -> ttk.Combobox:
        ttk.Label(parent, text=label, style="Body.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
        combo = ttk.Combobox(parent, textvariable=var, values=values, state="readonly")
        combo.grid(row=row, column=1, sticky="ew", pady=4, padx=(0, 6))
        parent.columnconfigure(1, weight=1)
        if callback:
            combo.bind("<<ComboboxSelected>>", lambda _e: callback())
        return combo

    def _hotkey_row(self, parent: ttk.Frame, label: str, var: tk.StringVar, row: int, capture_cmd) -> None:
        ttk.Label(parent, text=label, style="Body.TLabel").grid(row=row, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", pady=5, padx=(6, 6))
        ttk.Button(parent, text="Capture", style="Secondary.TButton", command=capture_cmd).grid(row=row, column=2, sticky="e", pady=5)

    def _color_row(self, parent: ttk.Frame, label: str, var: tk.StringVar, row: int) -> None:
        self._row_entry(parent, label, var, row)
        ttk.Button(parent, text="Pick", style="Secondary.TButton", command=lambda v=var: self.pick_color(v)).grid(row=row, column=2, sticky="e", pady=4)

    def pick_color(self, var: tk.StringVar) -> None:
        chosen = colorchooser.askcolor(color=var.get())
        if chosen[1]:
            var.set(chosen[1])
            self.apply_theme_from_controls()

    def _bind_events(self) -> None:
        self.root.bind("<Configure>", lambda _e: self._draw_root_background())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _apply_theme(self) -> None:
        t = self.theme_manager.current_theme
        dark_like = self.theme_manager.is_dark_like(t)
        root_bg = t.background_color
        panel_bg = t.panel_color
        text = t.text_color
        muted = t.muted_text_color

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Root.TFrame", background=root_bg)
        style.configure("Card.TFrame", background=panel_bg, borderwidth=1, relief="solid")
        style.configure("Title.TLabel", background=root_bg, foreground=text, font=("Segoe UI", 18, "bold"))
        style.configure("Section.TLabel", background=panel_bg, foreground=text, font=("Segoe UI Semibold", 11))
        style.configure("Body.TLabel", background=panel_bg, foreground=text, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=panel_bg, foreground=muted, font=("Segoe UI", 9))
        style.configure("Status.TLabel", background=root_bg, foreground="#22C55E", font=("Segoe UI Semibold", 10))

        style.configure("Card.TCheckbutton", background=panel_bg, foreground=text)
        style.configure("Primary.TButton", foreground="#F8FAFC", background=t.accent_color, borderwidth=0, padding=(10, 8))
        style.map("Primary.TButton", background=[("active", self.theme_manager.blend(t.accent_color, "#000000", 0.2))])
        style.configure("Secondary.TButton", foreground=text, background=t.button_color, borderwidth=0, padding=(10, 8))
        style.map("Secondary.TButton", background=[("active", self.theme_manager.blend(t.button_color, "#ffffff" if dark_like else "#000000", 0.12))])

        style.configure("TEntry", fieldbackground=t.input_color, foreground=text, insertcolor=text, bordercolor=t.border_color)
        style.configure("TCombobox", fieldbackground=t.input_color, foreground=text, background=t.input_color, bordercolor=t.border_color)
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", t.input_color)],
            selectbackground=[("readonly", t.input_color)],
            selectforeground=[("readonly", text)],
        )

        style.configure("App.TNotebook", background=root_bg, borderwidth=0)
        style.configure("App.TNotebook.Tab", padding=(14, 8), background=t.button_color, foreground=text)
        style.map("App.TNotebook.Tab", background=[("selected", t.panel_color)], foreground=[("selected", t.accent_color)])

        self.main_container.configure(style="Root.TFrame")
        self._draw_root_background()
        self._draw_preview()
        self._refresh_status(self.status_label.cget("text") if self.status_label else "Ready")

    def _draw_root_background(self) -> None:
        t = self.theme_manager.current_theme
        w = max(1, self.root.winfo_width())
        h = max(1, self.root.winfo_height())
        self.background_canvas.delete("all")

        if not t.gradient_enabled:
            self.background_canvas.create_rectangle(0, 0, w, h, fill=t.background_color, outline="")
            return

        direction = t.gradient_direction
        if direction == "left-right":
            for x in range(w):
                color = self.theme_manager.gradient_color(t, x / max(1, w - 1))
                self.background_canvas.create_line(x, 0, x, h, fill=color)
        elif direction == "diagonal":
            steps = w + h
            for i in range(steps):
                color = self.theme_manager.gradient_color(t, i / max(1, steps - 1))
                self.background_canvas.create_line(i, 0, 0, i, fill=color)
                self.background_canvas.create_line(w, i, i, h, fill=color)
        elif direction == "radial":
            cx, cy = w // 2, h // 2
            radius = int((w**2 + h**2) ** 0.5 / 2)
            for r in range(radius, 0, -3):
                tval = 1 - (r / radius)
                color = self.theme_manager.gradient_color(t, tval)
                self.background_canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color)
        else:
            for y in range(h):
                color = self.theme_manager.gradient_color(t, y / max(1, h - 1))
                self.background_canvas.create_line(0, y, w, y, fill=color)

    def _draw_preview(self) -> None:
        if not hasattr(self, "preview_canvas"):
            return
        c = self.preview_canvas
        c.delete("all")
        t = self.theme_manager.current_theme
        w = max(1, c.winfo_width() or 280)
        h = max(1, c.winfo_height() or 220)
        if t.gradient_enabled:
            for y in range(h):
                color = self.theme_manager.gradient_color(t, y / max(1, h - 1))
                c.create_line(0, y, w, y, fill=color)
        else:
            c.create_rectangle(0, 0, w, h, fill=t.background_color, outline="")
        c.create_rectangle(18, 18, w - 18, h - 18, fill=t.panel_color, outline=t.border_color, width=2)
        c.create_text(30, 36, anchor="w", text="Preview Card", fill=t.text_color, font=("Segoe UI", 11, "bold"))
        c.create_rectangle(30, 56, 150, 88, fill=t.accent_color, outline="")
        c.create_text(90, 72, text="Primary", fill="#F8FAFC", font=("Segoe UI", 9, "bold"))
        c.create_rectangle(160, 56, 280, 88, fill=t.button_color, outline="")
        c.create_text(220, 72, text="Secondary", fill=t.text_color, font=("Segoe UI", 9))
        c.create_rectangle(30, 100, 280, 130, fill=t.input_color, outline=t.border_color)
        c.create_text(38, 115, anchor="w", text="Input preview", fill=t.muted_text_color, font=("Segoe UI", 9))

    def _set_mode_defaults(self) -> None:
        mode = self.theme_mode_var.get().strip().lower()
        if mode == "light":
            preset = ThemeConfig(mode="light", background_color="#F1F5F9", panel_color="#FFFFFF", input_color="#FFFFFF", text_color="#0F172A", muted_text_color="#64748B", button_color="#E2E8F0", accent_color="#2563EB", border_color="#CBD5E1")
        elif mode == "dark":
            preset = ThemeConfig(mode="dark", background_color="#0B1220", panel_color="#0F172A", input_color="#111827", text_color="#E5E7EB", muted_text_color="#94A3B8", button_color="#1F2937", accent_color="#3B82F6", border_color="#334155")
        else:
            preset = ThemeConfig(mode="custom")
        self._set_theme_controls_from_theme(preset)
        self.apply_theme_from_controls()

    def _set_theme_controls_from_theme(self, t: ThemeConfig) -> None:
        self.theme_mode_var.set(t.mode)
        self.bg_color_var.set(t.background_color)
        self.text_color_var.set(t.text_color)
        self.button_color_var.set(t.button_color)
        self.accent_color_var.set(t.accent_color)
        self.border_color_var.set(t.border_color)
        self.input_color_var.set(t.input_color)
        self.panel_color_var.set(t.panel_color)
        self.muted_text_var.set(t.muted_text_color)
        self.gradient_enabled_var.set(t.gradient_enabled)
        self.gradient_start_var.set(t.gradient_start)
        self.gradient_end_var.set(t.gradient_end)
        self.gradient_third_var.set(t.gradient_third)
        self.gradient_direction_var.set(t.gradient_direction)
        self._toggle_gradient_controls()

    def _theme_from_controls(self) -> ThemeConfig:
        return ThemeConfig(
            name="custom-live",
            mode=self.theme_mode_var.get().strip().lower(),
            background_color=self.bg_color_var.get().strip(),
            text_color=self.text_color_var.get().strip(),
            button_color=self.button_color_var.get().strip(),
            accent_color=self.accent_color_var.get().strip(),
            border_color=self.border_color_var.get().strip(),
            input_color=self.input_color_var.get().strip(),
            panel_color=self.panel_color_var.get().strip(),
            muted_text_color=self.muted_text_var.get().strip(),
            gradient_enabled=bool(self.gradient_enabled_var.get()),
            gradient_start=self.gradient_start_var.get().strip(),
            gradient_end=self.gradient_end_var.get().strip(),
            gradient_third=self.gradient_third_var.get().strip(),
            gradient_direction=self.gradient_direction_var.get().strip(),
        )

    def _toggle_gradient_controls(self) -> None:
        enabled = self.gradient_enabled_var.get()
        state = "normal" if enabled else "disabled"
        for widget in (
            self.appearance_tab.grid_slaves(row=0, column=0) + self.appearance_tab.grid_slaves(row=0, column=1)
        ):
            _ = widget
        # Specific entry widgets are in controls card, set by row index lookups.
        # Simpler and stable: set only variables via current states at apply-time.
        self._draw_preview()

    def _toggle_fixed_entries(self) -> None:
        state = "normal" if self.position_mode_var.get().strip().lower() == "fixed" else "disabled"
        self.fixed_x_entry.configure(state=state)
        self.fixed_y_entry.configure(state=state)

    def _toggle_edge_entries(self) -> None:
        state = "normal" if self.edge_guard_var.get() else "disabled"
        self.edge_left_entry.configure(state=state)
        self.edge_right_entry.configure(state=state)
        self.edge_top_entry.configure(state=state)
        self.edge_bottom_entry.configure(state=state)

    def apply_theme_from_controls(self) -> None:
        new_theme = self._theme_from_controls()
        color_fields = [
            new_theme.background_color,
            new_theme.text_color,
            new_theme.button_color,
            new_theme.accent_color,
            new_theme.border_color,
            new_theme.input_color,
            new_theme.panel_color,
            new_theme.muted_text_color,
        ]
        if new_theme.gradient_enabled:
            color_fields.extend([new_theme.gradient_start, new_theme.gradient_end])
            if new_theme.gradient_third:
                color_fields.append(new_theme.gradient_third)
        for color in color_fields:
            if not self.theme_manager.validate_color(color):
                messagebox.showerror("Theme", f"Invalid color: {color}")
                return
        self.theme_manager.current_theme = new_theme
        self.theme_manager.save_last_theme()
        self._apply_theme()
        self._refresh_status("Theme applied")

    def reset_theme_defaults(self) -> None:
        preset = self.theme_manager.get_preset("Midnight") or ThemeConfig(mode="dark")
        self._set_theme_controls_from_theme(preset)
        self.apply_theme_from_controls()

    def _refresh_preset_combo(self) -> None:
        self.preset_combo.configure(values=self.theme_manager.all_preset_names())
        if not self.preset_select_var.get() and self.theme_manager.all_preset_names():
            self.preset_select_var.set(self.theme_manager.all_preset_names()[0])

    def save_preset(self) -> None:
        name = self.preset_name_var.get().strip()
        if not name:
            name = simpledialog.askstring("Preset name", "Enter a preset name:", parent=self.root) or ""
            name = name.strip()
        if not name:
            return
        self.theme_manager.save_custom_preset(name, self._theme_from_controls())
        self._refresh_preset_combo()
        self.preset_select_var.set(name)
        self._refresh_status(f"Preset '{name}' saved")

    def load_selected_preset(self) -> None:
        name = self.preset_select_var.get().strip()
        theme = self.theme_manager.get_preset(name)
        if theme is None:
            messagebox.showerror("Preset", "Select a valid preset.")
            return
        self._set_theme_controls_from_theme(theme)
        self.apply_theme_from_controls()
        self._refresh_status(f"Preset '{name}' loaded")

    def _refresh_status(self, text: str, color: str = "#22C55E") -> None:
        if self.app_is_closing:
            return
        if threading.current_thread() is threading.main_thread():
            self.status_label.configure(text=text, foreground=color)
            return
        self.root.after(0, lambda: self._refresh_status(text, color))

    def _update_summary(self) -> None:
        target = self.config.target_app_exe if self.config.target_app_exe else "Any app"
        self.summary_label.configure(
            text=(
                f"{self.config.interval_ms}ms | {self.config.click_type} | "
                f"{self.config.mouse_button} | Target: {target}"
            )
        )

    def apply_hotkeys(self) -> None:
        start = self.start_hotkey_var.get().strip().lower()
        stop = self.stop_hotkey_var.get().strip().lower()
        toggle = self.toggle_hotkey_var.get().strip().lower()
        if not start or not stop or not toggle:
            messagebox.showerror("Hotkeys", "Hotkeys cannot be empty.")
            return
        if len({start, stop, toggle}) < 3:
            messagebox.showerror("Hotkeys", "Start, Stop, and Toggle must be different.")
            return
        self.config.start_hotkey = start
        self.config.stop_hotkey = stop
        self.config.toggle_hotkey = toggle
        self._restart_hotkey_listener()
        self._refresh_status("Hotkeys applied", "#60A5FA")

    def _format_hotkey_key(self, key_obj: keyboard.Key | keyboard.KeyCode) -> str | None:
        if isinstance(key_obj, keyboard.KeyCode):
            if not key_obj.char:
                return None
            return "<space>" if key_obj.char == " " else key_obj.char.lower()
        if key_obj is keyboard.Key.space:
            return "<space>"
        if key_obj.name:
            return f"<{key_obj.name.lower()}>"
        return None

    def _capture_hotkey(self, target: str) -> None:
        if self.capture_listener is not None:
            self.capture_listener.stop()
            self.capture_listener = None
        self.capture_modifiers = set()
        self._refresh_status(f"Press key for {target}", "#F59E0B")

        mod_map = {
            keyboard.Key.ctrl: "<ctrl>",
            keyboard.Key.ctrl_l: "<ctrl>",
            keyboard.Key.ctrl_r: "<ctrl>",
            keyboard.Key.alt: "<alt>",
            keyboard.Key.alt_l: "<alt>",
            keyboard.Key.alt_r: "<alt>",
            keyboard.Key.shift: "<shift>",
            keyboard.Key.shift_l: "<shift>",
            keyboard.Key.shift_r: "<shift>",
        }

        def on_press(key_obj: keyboard.Key | keyboard.KeyCode) -> bool | None:
            mod = mod_map.get(key_obj)
            if mod:
                self.capture_modifiers.add(mod)
                return None
            key_name = self._format_hotkey_key(key_obj)
            if not key_name:
                return None
            hotkey = "+".join(sorted(self.capture_modifiers) + [key_name])
            if target == "start":
                self.start_hotkey_var.set(hotkey)
            elif target == "stop":
                self.stop_hotkey_var.set(hotkey)
            else:
                self.toggle_hotkey_var.set(hotkey)
            self.apply_hotkeys()
            return False

        self.capture_listener = keyboard.Listener(on_press=on_press)
        self.capture_listener.start()

    def apply_clicker_settings(self) -> None:
        try:
            interval = int(self.interval_var.get().strip())
            if interval <= 0:
                raise ValueError("Interval must be > 0.")
            edge_vals = [
                int(self.edge_left_var.get().strip()),
                int(self.edge_right_var.get().strip()),
                int(self.edge_top_var.get().strip()),
                int(self.edge_bottom_var.get().strip()),
            ]
            if min(edge_vals) < 0:
                raise ValueError("Edge distances must be >= 0.")
            self.config.interval_ms = interval
            self.config.click_type = self.click_type_var.get().strip().lower()
            self.config.mouse_button = self.mouse_button_var.get().strip().lower()
            self.config.position_mode = self.position_mode_var.get().strip().lower()
            self.config.fixed_x = int(self.fixed_x_var.get().strip())
            self.config.fixed_y = int(self.fixed_y_var.get().strip())
            self.config.edge_guard_enabled = bool(self.edge_guard_var.get())
            self.config.edge_left_px = edge_vals[0]
            self.config.edge_right_px = edge_vals[1]
            self.config.edge_top_px = edge_vals[2]
            self.config.edge_bottom_px = edge_vals[3]
            self.config.edge_relative_to_app = bool(self.edge_relative_var.get())
            self.config.only_target_app = bool(self.only_target_app_var.get())
            self._update_summary()
            self._refresh_status("Settings applied", "#60A5FA")
        except Exception as exc:
            messagebox.showerror("Settings", str(exc))

    def _start_hotkey_listener(self) -> None:
        try:
            mapping = {
                self.config.start_hotkey: self.start_clicking,
                self.config.stop_hotkey: self.stop_clicking,
                self.config.toggle_hotkey: self.toggle_clicking,
            }
            self.hotkey_listener = keyboard.GlobalHotKeys(mapping)
            self.hotkey_listener.start()
        except Exception as exc:
            self._refresh_status("Hotkey registration failed", "#EF4444")
            messagebox.showerror("Hotkeys", str(exc))

    def _restart_hotkey_listener(self) -> None:
        if self.hotkey_listener is not None:
            self.hotkey_listener.stop()
            self.hotkey_listener = None
        self._start_hotkey_listener()

    def _get_foreground_app_info(self) -> tuple[str, str, tuple[int, int, int, int] | None]:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "", "", None

        title_buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buf, 512)
        title = title_buf.value.strip()

        rect = RECT()
        bounds = None
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            bounds = (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))

        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe_name = ""
        if pid.value:
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
            if handle:
                try:
                    size = ctypes.c_ulong(1024)
                    path = ctypes.create_unicode_buffer(1024)
                    ok = kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size))
                    if ok:
                        exe_name = os.path.basename(path.value).lower()
                finally:
                    kernel32.CloseHandle(handle)
        return title, exe_name, bounds

    def capture_current_app(self) -> None:
        title, exe_name, _ = self._get_foreground_app_info()
        if not title and not exe_name:
            messagebox.showerror("App", "Could not capture current app.")
            return
        self.config.target_app_title = title
        self.config.target_app_exe = exe_name
        self.target_app_var.set(f"Selected app: {exe_name or title}")
        self._update_summary()
        self._refresh_status("Target app captured", "#60A5FA")

    def _is_target_app_active(self) -> tuple[bool, tuple[int, int, int, int] | None]:
        if not self.config.only_target_app:
            return True, None
        title, exe_name, bounds = self._get_foreground_app_info()
        if self.config.target_app_exe and exe_name != self.config.target_app_exe:
            return False, None
        if self.config.target_app_title and title != self.config.target_app_title:
            return False, None
        return bool(title or exe_name), bounds

    def _near_edge(self, x: int, y: int, bounds: tuple[int, int, int, int] | None) -> bool:
        if not self.config.edge_guard_enabled:
            return False
        if bounds is None:
            left, top, right, bottom = 0, 0, self.screen_width - 1, self.screen_height - 1
        else:
            left, top, right, bottom = bounds
        return (
            x <= left + self.config.edge_left_px
            or x >= right - self.config.edge_right_px
            or y <= top + self.config.edge_top_px
            or y >= bottom - self.config.edge_bottom_px
        )

    def _mouse_button(self) -> mouse.Button:
        return {
            "left": mouse.Button.left,
            "middle": mouse.Button.middle,
            "right": mouse.Button.right,
        }[self.config.mouse_button]

    def _click_loop(self) -> None:
        while self.running and not self.app_is_closing:
            target_ok, app_bounds = self._is_target_app_active()
            if not target_ok:
                self._refresh_status("Paused: selected app not active", "#F59E0B")
                time.sleep(max(self.config.interval_ms / 1000.0, 0.001))
                continue

            if self.config.position_mode == "fixed":
                x, y = self.config.fixed_x, self.config.fixed_y
            else:
                pos = self.mouse_controller.position
                x, y = int(pos[0]), int(pos[1])

            bounds = app_bounds if self.config.edge_relative_to_app else None
            if self._near_edge(x, y, bounds):
                self._refresh_status("Paused: pointer near edge", "#F59E0B")
                time.sleep(max(self.config.interval_ms / 1000.0, 0.001))
                continue

            if self.config.position_mode == "fixed":
                self.mouse_controller.position = (x, y)
            clicks = 2 if self.config.click_type == "double" else 1
            self.mouse_controller.click(self._mouse_button(), clicks)
            self._refresh_status("Running")
            time.sleep(max(self.config.interval_ms / 1000.0, 0.001))

    def start_clicking(self) -> None:
        if self.running:
            return
        self.apply_clicker_settings()
        self.running = True
        self.worker_thread = threading.Thread(target=self._click_loop, daemon=True)
        self.worker_thread.start()
        self._refresh_status("Running")

    def stop_clicking(self) -> None:
        self.running = False
        self._refresh_status("Stopped", "#F59E0B")

    def toggle_clicking(self) -> None:
        if self.running:
            self.stop_clicking()
        else:
            self.start_clicking()

    def _on_close(self) -> None:
        self.app_is_closing = True
        self.running = False
        self.theme_manager.save_last_theme()
        if self.capture_listener is not None:
            self.capture_listener.stop()
            self.capture_listener = None
        if self.hotkey_listener is not None:
            self.hotkey_listener.stop()
            self.hotkey_listener = None
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    AutoClickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
import os
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import colorchooser, messagebox, ttk

from pynput import keyboard, mouse


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


@dataclass
class AppConfig:
    interval_ms: int = 100
    click_type: str = "single"
    mouse_button: str = "left"
    position_mode: str = "current"
    fixed_x: int = 500
    fixed_y: int = 500
    start_hotkey: str = "<f6>"
    stop_hotkey: str = "<f7>"
    toggle_hotkey: str = "<f8>"
    edge_guard_enabled: bool = False
    edge_left_px: int = 20
    edge_right_px: int = 20
    edge_top_px: int = 20
    edge_bottom_px: int = 20
    edge_relative_to_app: bool = False
    only_target_app: bool = False
    target_app_title: str = ""
    target_app_exe: str = ""
    ui_theme: str = "dark"
    background_color: str = "#0B1220"


class AutoClickerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AutoClicker")
        self.root.geometry("860x620")
        self.root.minsize(780, 560)

        self.config = AppConfig()
        self.mouse_controller = mouse.Controller()
        self.running = False
        self.worker_thread: threading.Thread | None = None
        self.hotkey_listener: keyboard.GlobalHotKeys | None = None
        self.capture_listener: keyboard.Listener | None = None
        self.capture_modifiers: set[str] = set()
        self.app_is_closing = False
        self.pause_reason = ""
        self.screen_width = root.winfo_screenwidth()
        self.screen_height = root.winfo_screenheight()

        self.interval_var = tk.StringVar(value=str(self.config.interval_ms))
        self.click_type_var = tk.StringVar(value=self.config.click_type)
        self.mouse_button_var = tk.StringVar(value=self.config.mouse_button)
        self.position_mode_var = tk.StringVar(value=self.config.position_mode)
        self.fixed_x_var = tk.StringVar(value=str(self.config.fixed_x))
        self.fixed_y_var = tk.StringVar(value=str(self.config.fixed_y))
        self.edge_guard_var = tk.BooleanVar(value=self.config.edge_guard_enabled)
        self.edge_left_var = tk.StringVar(value=str(self.config.edge_left_px))
        self.edge_right_var = tk.StringVar(value=str(self.config.edge_right_px))
        self.edge_top_var = tk.StringVar(value=str(self.config.edge_top_px))
        self.edge_bottom_var = tk.StringVar(value=str(self.config.edge_bottom_px))
        self.edge_relative_var = tk.BooleanVar(value=self.config.edge_relative_to_app)
        self.only_target_app_var = tk.BooleanVar(value=self.config.only_target_app)
        self.target_app_display_var = tk.StringVar(value="No app selected")

        self.status_label: ttk.Label | None = None
        self.summary_label: ttk.Label | None = None

        self._apply_style()
        self._build_ui()
        self._start_hotkey_listener()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_status("Ready", "#22C55E")

    def _palette(self) -> dict[str, str]:
        if self.config.ui_theme == "light":
            return {
                "bg": self.config.background_color,
                "panel": "#FFFFFF",
                "text": "#0F172A",
                "sub": "#475569",
                "border": "#D1D5DB",
                "entry_bg": "#FFFFFF",
                "btn_bg": "#E5E7EB",
                "btn_fg": "#111827",
                "accent": "#2563EB",
                "accent_hover": "#1D4ED8",
            }
        return {
            "bg": self.config.background_color,
            "panel": "#111827",
            "text": "#F9FAFB",
            "sub": "#94A3B8",
            "border": "#1F2937",
            "entry_bg": "#0B1220",
            "btn_bg": "#1F2937",
            "btn_fg": "#E5E7EB",
            "accent": "#2563EB",
            "accent_hover": "#1D4ED8",
        }

    def _apply_style(self) -> None:
        c = self._palette()
        self.root.configure(bg=c["bg"])
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Root.TFrame", background=c["bg"])
        style.configure("Panel.TFrame", background=c["panel"], borderwidth=1, relief="solid")
        style.configure("Title.TLabel", background=c["bg"], foreground=c["text"], font=("Segoe UI", 16, "bold"))
        style.configure("TopHint.TLabel", background=c["bg"], foreground=c["sub"], font=("Segoe UI", 9))
        style.configure("Section.TLabel", background=c["panel"], foreground=c["text"], font=("Segoe UI Semibold", 11))
        style.configure("Body.TLabel", background=c["panel"], foreground=c["text"], font=("Segoe UI", 10))
        style.configure("SubBody.TLabel", background=c["panel"], foreground=c["sub"], font=("Segoe UI", 9))
        style.configure("Status.TLabel", background=c["panel"], foreground="#22C55E", font=("Segoe UI", 10, "bold"))

        style.configure("Primary.TButton", foreground="#F9FAFB", background=c["accent"], padding=(10, 8), borderwidth=0)
        style.map("Primary.TButton", background=[("active", c["accent_hover"])])
        style.configure("Secondary.TButton", foreground=c["btn_fg"], background=c["btn_bg"], padding=(10, 8), borderwidth=0)
        style.map("Secondary.TButton", background=[("active", c["border"])])

        style.configure("TEntry", fieldbackground=c["entry_bg"], foreground=c["text"], insertcolor=c["text"], bordercolor=c["border"])
        style.configure("TCombobox", fieldbackground=c["entry_bg"], foreground=c["text"], background=c["entry_bg"], bordercolor=c["border"])
        style.map("TCombobox", fieldbackground=[("readonly", c["entry_bg"])], selectforeground=[("readonly", c["text"])], selectbackground=[("readonly", c["entry_bg"])])

        style.configure("TRadiobutton", background=c["panel"], foreground=c["text"])
        style.configure("TCheckbutton", background=c["panel"], foreground=c["text"])

    def _build_ui(self) -> None:
        self.root_frame = ttk.Frame(self.root, style="Root.TFrame", padding=14)
        self.root_frame.pack(fill="both", expand=True)
        self.root_frame.columnconfigure(0, weight=1)

        top = ttk.Frame(self.root_frame, style="Root.TFrame")
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="AutoClicker", style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="? App", style="Secondary.TButton", command=self._open_app_settings).pack(side="right")

        ttk.Label(
            self.root_frame,
            text="Advanced dark UI with focused controls",
            style="TopHint.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 12))

        grid = ttk.Frame(self.root_frame, style="Root.TFrame")
        grid.grid(row=2, column=0, sticky="nsew")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        self.root_frame.rowconfigure(2, weight=1)

        left = ttk.Frame(grid, style="Panel.TFrame", padding=12)
        right = ttk.Frame(grid, style="Panel.TFrame", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        left.columnconfigure(1, weight=1)
        right.columnconfigure(1, weight=1)

        ttk.Label(left, text="Clicking", style="Section.TLabel").grid(row=0, column=0, sticky="w", columnspan=2, pady=(0, 8))
        self._add_row_entry(left, "Interval (ms)", self.interval_var, 1)
        self._add_row_combo(left, "Click Type", self.click_type_var, ["single", "double"], 2)
        self._add_row_combo(left, "Mouse Button", self.mouse_button_var, ["left", "middle", "right"], 3)
        self._add_row_combo(left, "Position", self.position_mode_var, ["current", "fixed"], 4, self._toggle_fixed_entries)
        self.fixed_x_entry = self._add_row_entry(left, "Fixed X", self.fixed_x_var, 5)
        self.fixed_y_entry = self._add_row_entry(left, "Fixed Y", self.fixed_y_var, 6)

        hotkey_row = ttk.Frame(left, style="Panel.TFrame")
        hotkey_row.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(hotkey_row, text="Start Key", style="Secondary.TButton", command=lambda: self._capture_hotkey("start")).pack(side="left", padx=(0, 6))
        ttk.Button(hotkey_row, text="Stop Key", style="Secondary.TButton", command=lambda: self._capture_hotkey("stop")).pack(side="left", padx=(0, 6))
        ttk.Button(hotkey_row, text="Toggle Key", style="Secondary.TButton", command=lambda: self._capture_hotkey("toggle")).pack(side="left")

        action_row = ttk.Frame(left, style="Panel.TFrame")
        action_row.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(action_row, text="Start", style="Primary.TButton", command=self.start_clicking).pack(side="left", padx=(0, 8))
        ttk.Button(action_row, text="Stop", style="Secondary.TButton", command=self.stop_clicking).pack(side="left", padx=(0, 8))
        ttk.Button(action_row, text="? Clicker", style="Secondary.TButton", command=self._open_clicker_settings).pack(side="left")

        ttk.Label(right, text="Edge Stop + App Target", style="Section.TLabel").grid(row=0, column=0, sticky="w", columnspan=2, pady=(0, 8))
        ttk.Checkbutton(right, text="Disable near screen/app edges", variable=self.edge_guard_var, command=self._toggle_edge_entries).grid(row=1, column=0, columnspan=2, sticky="w")
        self.edge_left_entry = self._add_row_entry(right, "Left (px)", self.edge_left_var, 2)
        self.edge_right_entry = self._add_row_entry(right, "Right (px)", self.edge_right_var, 3)
        self.edge_top_entry = self._add_row_entry(right, "Top (px)", self.edge_top_var, 4)
        self.edge_bottom_entry = self._add_row_entry(right, "Bottom (px)", self.edge_bottom_var, 5)
        ttk.Checkbutton(right, text="Apply edge guard to selected app window", variable=self.edge_relative_var).grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Checkbutton(right, text="Only click when selected app is active", variable=self.only_target_app_var).grid(row=7, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Button(right, text="Capture Current App", style="Secondary.TButton", command=self._capture_current_app).grid(row=8, column=0, sticky="w", pady=(8, 0))
        ttk.Label(right, textvariable=self.target_app_display_var, style="SubBody.TLabel").grid(row=9, column=0, columnspan=2, sticky="w", pady=(6, 0))

        status_panel = ttk.Frame(self.root_frame, style="Panel.TFrame", padding=10)
        status_panel.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.summary_label = ttk.Label(status_panel, text="", style="Body.TLabel")
        self.summary_label.pack(anchor="w")
        self.status_label = ttk.Label(status_panel, text="Ready", style="Status.TLabel")
        self.status_label.pack(anchor="w", pady=(4, 0))

        self._toggle_fixed_entries()
        self._toggle_edge_entries()
        self._sync_config_from_ui(update_listener=False)
        self._update_summary()

    def _add_row_entry(self, parent: ttk.Frame, label: str, var: tk.StringVar, row: int) -> ttk.Entry:
        ttk.Label(parent, text=label, style="Body.TLabel").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 10))
        entry = ttk.Entry(parent, textvariable=var, width=16)
        entry.grid(row=row, column=1, sticky="ew", pady=4)
        return entry

    def _add_row_combo(
        self,
        parent: ttk.Frame,
        label: str,
        var: tk.StringVar,
        values: list[str],
        row: int,
        callback=None,
    ) -> ttk.Combobox:
        ttk.Label(parent, text=label, style="Body.TLabel").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 10))
        combo = ttk.Combobox(parent, textvariable=var, state="readonly", values=values, width=14)
        combo.grid(row=row, column=1, sticky="ew", pady=4)
        if callback:
            combo.bind("<<ComboboxSelected>>", lambda _e: callback())
        return combo

    def _toggle_fixed_entries(self) -> None:
        mode = self.position_mode_var.get().strip().lower()
        state = "normal" if mode == "fixed" else "disabled"
        self.fixed_x_entry.configure(state=state)
        self.fixed_y_entry.configure(state=state)

    def _toggle_edge_entries(self) -> None:
        state = "normal" if self.edge_guard_var.get() else "disabled"
        self.edge_left_entry.configure(state=state)
        self.edge_right_entry.configure(state=state)
        self.edge_top_entry.configure(state=state)
        self.edge_bottom_entry.configure(state=state)

    def _refresh_status(self, text: str, color: str) -> None:
        if self.app_is_closing:
            return
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, lambda: self._refresh_status(text, color))
            return
        if self.status_label is not None:
            self.status_label.configure(text=text, foreground=color)

    def _update_summary(self) -> None:
        if self.summary_label is None:
            return
        target = self.config.target_app_exe if self.config.target_app_exe else "Any app"
        self.summary_label.configure(
            text=f"{self.config.interval_ms}ms | {self.config.click_type} | {self.config.mouse_button} | Target: {target}"
        )

    def _format_hotkey_key(self, pressed_key: keyboard.Key | keyboard.KeyCode) -> str | None:
        if isinstance(pressed_key, keyboard.KeyCode):
            if not pressed_key.char:
                return None
            return "<space>" if pressed_key.char == " " else pressed_key.char.lower()
        if pressed_key is keyboard.Key.space:
            return "<space>"
        if pressed_key.name:
            return f"<{pressed_key.name.lower()}>"
        return None

    def _capture_hotkey(self, target: str) -> None:
        if self.capture_listener is not None:
            self.capture_listener.stop()
            self.capture_listener = None
        self.capture_modifiers = set()
        self._refresh_status(f"Press key for {target}", "#FBBF24")

        mod_map = {
            keyboard.Key.ctrl: "<ctrl>",
            keyboard.Key.ctrl_l: "<ctrl>",
            keyboard.Key.ctrl_r: "<ctrl>",
            keyboard.Key.alt: "<alt>",
            keyboard.Key.alt_l: "<alt>",
            keyboard.Key.alt_r: "<alt>",
            keyboard.Key.shift: "<shift>",
            keyboard.Key.shift_l: "<shift>",
            keyboard.Key.shift_r: "<shift>",
        }

        def on_press(pressed_key: keyboard.Key | keyboard.KeyCode) -> bool | None:
            modifier = mod_map.get(pressed_key)
            if modifier:
                self.capture_modifiers.add(modifier)
                return None
            key_text = self._format_hotkey_key(pressed_key)
            if not key_text:
                return None
            hotkey = "+".join(sorted(self.capture_modifiers) + [key_text])
            if target == "start":
                self.config.start_hotkey = hotkey
            elif target == "stop":
                self.config.stop_hotkey = hotkey
            else:
                self.config.toggle_hotkey = hotkey
            self._restart_hotkey_listener()
            self._refresh_status(f"{target.capitalize()} key: {hotkey}", "#60A5FA")
            return False

        self.capture_listener = keyboard.Listener(on_press=on_press)
        self.capture_listener.start()

    def _get_foreground_app_info(self) -> tuple[str, str, tuple[int, int, int, int] | None]:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "", "", None
        title_buffer = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buffer, 512)
        title = title_buffer.value.strip()

        rect = RECT()
        rect_tuple = None
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            rect_tuple = (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))

        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe_name = ""
        if pid.value:
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
            if handle:
                try:
                    size = ctypes.c_ulong(1024)
                    path = ctypes.create_unicode_buffer(1024)
                    ok = kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size))
                    if ok:
                        exe_name = os.path.basename(path.value).lower()
                finally:
                    kernel32.CloseHandle(handle)
        return title, exe_name, rect_tuple

    def _capture_current_app(self) -> None:
        title, exe_name, _rect = self._get_foreground_app_info()
        if not title and not exe_name:
            messagebox.showerror("App capture", "Could not read current active app.")
            return
        self.config.target_app_title = title
        self.config.target_app_exe = exe_name
        self.target_app_display_var.set(f"Selected app: {exe_name or title}")
        self._update_summary()
        self._refresh_status("Target app captured", "#60A5FA")

    def _is_target_app_active(self) -> tuple[bool, tuple[int, int, int, int] | None]:
        if not self.config.only_target_app:
            return True, None
        title, exe_name, rect = self._get_foreground_app_info()
        if self.config.target_app_exe and exe_name != self.config.target_app_exe:
            return False, None
        if self.config.target_app_title and title != self.config.target_app_title:
            return False, None
        return bool(title or exe_name), rect

    def _is_near_edge(self, x: int, y: int, bounds: tuple[int, int, int, int] | None) -> bool:
        if not self.config.edge_guard_enabled:
            return False
        if bounds is None:
            left, top, right, bottom = 0, 0, self.screen_width - 1, self.screen_height - 1
        else:
            left, top, right, bottom = bounds
        return (
            x <= left + self.config.edge_left_px
            or x >= right - self.config.edge_right_px
            or y <= top + self.config.edge_top_px
            or y >= bottom - self.config.edge_bottom_px
        )

    def _sync_config_from_ui(self, update_listener: bool = True) -> None:
        interval = int(self.interval_var.get().strip())
        if interval <= 0:
            raise ValueError("Interval must be greater than 0.")
        click_type = self.click_type_var.get().strip().lower()
        mouse_button = self.mouse_button_var.get().strip().lower()
        position_mode = self.position_mode_var.get().strip().lower()
        fixed_x = int(self.fixed_x_var.get().strip())
        fixed_y = int(self.fixed_y_var.get().strip())
        edge_left = int(self.edge_left_var.get().strip())
        edge_right = int(self.edge_right_var.get().strip())
        edge_top = int(self.edge_top_var.get().strip())
        edge_bottom = int(self.edge_bottom_var.get().strip())
        if min(edge_left, edge_right, edge_top, edge_bottom) < 0:
            raise ValueError("Edge values must be >= 0.")

        self.config.interval_ms = interval
        self.config.click_type = click_type
        self.config.mouse_button = mouse_button
        self.config.position_mode = position_mode
        self.config.fixed_x = fixed_x
        self.config.fixed_y = fixed_y
        self.config.edge_guard_enabled = bool(self.edge_guard_var.get())
        self.config.edge_left_px = edge_left
        self.config.edge_right_px = edge_right
        self.config.edge_top_px = edge_top
        self.config.edge_bottom_px = edge_bottom
        self.config.edge_relative_to_app = bool(self.edge_relative_var.get())
        self.config.only_target_app = bool(self.only_target_app_var.get())
        if update_listener:
            self._restart_hotkey_listener()
        self._update_summary()

    def _click_loop(self) -> None:
        while self.running and not self.app_is_closing:
            try:
                self._sync_config_from_ui(update_listener=False)
            except Exception:
                self._refresh_status("Invalid settings", "#EF4444")
                time.sleep(0.2)
                continue

            target_ok, app_rect = self._is_target_app_active()
            if not target_ok:
                self._refresh_status("Paused: selected app not active", "#FBBF24")
                time.sleep(max(self.config.interval_ms / 1000.0, 0.001))
                continue

            if self.config.position_mode == "fixed":
                x, y = self.config.fixed_x, self.config.fixed_y
            else:
                pos = self.mouse_controller.position
                x, y = int(pos[0]), int(pos[1])

            bounds = app_rect if self.config.edge_relative_to_app else None
            if self._is_near_edge(x, y, bounds):
                self._refresh_status("Paused: pointer near edge", "#FBBF24")
                time.sleep(max(self.config.interval_ms / 1000.0, 0.001))
                continue

            if self.config.position_mode == "fixed":
                self.mouse_controller.position = (x, y)
            clicks = 2 if self.config.click_type == "double" else 1
            self.mouse_controller.click(self._mouse_button(), clicks)
            self._refresh_status("Running", "#22C55E")
            time.sleep(max(self.config.interval_ms / 1000.0, 0.001))

    def _mouse_button(self) -> mouse.Button:
        return {
            "left": mouse.Button.left,
            "middle": mouse.Button.middle,
            "right": mouse.Button.right,
        }[self.config.mouse_button]

    def start_clicking(self) -> None:
        if self.running:
            return
        try:
            self._sync_config_from_ui(update_listener=True)
        except Exception as exc:
            messagebox.showerror("Settings error", str(exc))
            return
        self.running = True
        self.worker_thread = threading.Thread(target=self._click_loop, daemon=True)
        self.worker_thread.start()
        self._refresh_status("Running", "#22C55E")

    def stop_clicking(self) -> None:
        self.running = False
        self._refresh_status("Stopped", "#F59E0B")

    def toggle_clicking(self) -> None:
        if self.running:
            self.stop_clicking()
        else:
            self.start_clicking()

    def _start_hotkey_listener(self) -> None:
        try:
            mapping = {
                self.config.start_hotkey: self.start_clicking,
                self.config.stop_hotkey: self.stop_clicking,
                self.config.toggle_hotkey: self.toggle_clicking,
            }
            self.hotkey_listener = keyboard.GlobalHotKeys(mapping)
            self.hotkey_listener.start()
        except Exception as exc:
            self._refresh_status("Hotkey registration failed", "#EF4444")
            messagebox.showerror("Hotkey error", str(exc))

    def _restart_hotkey_listener(self) -> None:
        if self.hotkey_listener is not None:
            self.hotkey_listener.stop()
            self.hotkey_listener = None
        self._start_hotkey_listener()

    def _open_clicker_settings(self) -> None:
        messagebox.showinfo(
            "Clicker Settings",
            "Most clicker settings are directly on the main panel for faster access.",
        )

    def _open_app_settings(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("App Settings")
        win.geometry("420x220")
        win.transient(self.root)
        win.grab_set()

        panel = ttk.Frame(win, style="Panel.TFrame", padding=12)
        panel.pack(fill="both", expand=True, padx=10, pady=10)
        panel.columnconfigure(1, weight=1)

        theme_var = tk.StringVar(value=self.config.ui_theme)
        bg_var = tk.StringVar(value=self.config.background_color)

        ttk.Label(panel, text="Theme", style="Body.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Combobox(panel, textvariable=theme_var, state="readonly", values=["dark", "light"]).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Label(panel, text="Background", style="Body.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Entry(panel, textvariable=bg_var).grid(row=1, column=1, sticky="ew", pady=5)

        def pick_color() -> None:
            result = colorchooser.askcolor(color=bg_var.get(), title="Choose background color")
            if result[1]:
                bg_var.set(result[1])

        ttk.Button(panel, text="Pick Color", style="Secondary.TButton", command=pick_color).grid(row=2, column=0, sticky="w", pady=(8, 0))

        def apply_settings() -> None:
            color_val = bg_var.get().strip()
            if not color_val.startswith("#") or len(color_val) != 7:
                messagebox.showerror("Invalid color", "Use #RRGGBB format.")
                return
            self.config.ui_theme = theme_var.get().strip().lower()
            self.config.background_color = color_val
            self.root_frame.destroy()
            self._apply_style()
            self._build_ui()
            self._refresh_status("App style updated", "#60A5FA")
            win.destroy()

        ttk.Button(panel, text="Apply", style="Primary.TButton", command=apply_settings).grid(row=3, column=0, sticky="w", pady=(14, 0))
        ttk.Button(panel, text="Cancel", style="Secondary.TButton", command=win.destroy).grid(row=3, column=1, sticky="w", pady=(14, 0))

    def _on_close(self) -> None:
        self.app_is_closing = True
        self.running = False
        if self.capture_listener is not None:
            self.capture_listener.stop()
            self.capture_listener = None
        if self.hotkey_listener is not None:
            self.hotkey_listener.stop()
            self.hotkey_listener = None
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    AutoClickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
