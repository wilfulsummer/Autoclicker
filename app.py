import io
import json
import random
import threading
import time
import statistics
import tkinter as tk
import unittest
import ctypes
from dataclasses import asdict, dataclass
from pathlib import Path
from tkinter import colorchooser, messagebox, ttk
from tkinter import font as tkfont

from pynput import keyboard, mouse
from engine_bridge import EngineBridge, EngineConfig as NativeEngineConfig
from runtime_paths import APP_DIR, ensure_seed_file

THEME_FILE = ensure_seed_file("theme_settings.json")
PRESETS_FILE = ensure_seed_file("theme_presets.json")
SETTINGS_PRESETS_FILE = ensure_seed_file("settings_presets.json")
APP_SETTINGS_FILE = ensure_seed_file("app_settings.json")
CLICKER_FILE = ensure_seed_file("clicker_settings.json")
DEBUG_LOG_FILE = APP_DIR / "debug_layout.log"


@dataclass
class Theme:
    mode: str = "dark"
    background: str = "#101010"
    panel: str = "#171717"
    text: str = "#D6D6D6"
    muted: str = "#8A8A8A"
    button: str = "#242424"
    accent: str = "#2FA247"
    border: str = "#2B2B2B"
    input_bg: str = "#202020"
    gradient_on: bool = False
    grad_start: str = "#101010"
    grad_end: str = "#181818"
    grad_third: str = ""
    grad_dir: str = "top-bottom"


@dataclass
class Clicker:
    interval_ms: int = 100
    timing_mode: str = "cps"
    click_type: str = "single"
    mouse_button: str = "left"
    jitter_enabled: bool = False
    jitter_radius_px: int = 3
    random_interval_offset_min_ms: int = 0
    random_interval_offset_max_ms: int = 0
    start_hotkey: str = "<f6>"
    stop_hotkey: str = "<f7>"
    toggle_hotkey: str = "<f8>"


@dataclass
class UISettings:
    auto_scale_text: bool = True
    auto_scale_controls: bool = True
    base_scale: float = 1.0
    component_scale: float = 1.0
    high_precision_timing: bool = False
    process_priority_boost: bool = False
    precision_mode: bool = False
    random_interval_offset_min_ms: int = 0
    random_interval_offset_max_ms: int = 0


class SettingsManager:
    def __init__(self) -> None:
        self.settings = UISettings()
        self.presets: dict[str, UISettings] = {}
        self.load()

    def load(self) -> None:
        if not APP_SETTINGS_FILE.exists():
            self._load_presets()
            return
        try:
            self.settings = UISettings(**json.loads(APP_SETTINGS_FILE.read_text(encoding="utf-8")))
        except Exception:
            self.settings = UISettings()
        self._load_presets()

    def save(self) -> None:
        APP_SETTINGS_FILE.write_text(json.dumps(asdict(self.settings), indent=2), encoding="utf-8")
        self.save_presets()

    def _load_presets(self) -> None:
        if not SETTINGS_PRESETS_FILE.exists():
            return
        try:
            self.presets = {
                name: UISettings(**payload)
                for name, payload in json.loads(SETTINGS_PRESETS_FILE.read_text(encoding="utf-8")).items()
            }
        except Exception:
            self.presets = {}

    def save_presets(self) -> None:
        SETTINGS_PRESETS_FILE.write_text(
            json.dumps({name: asdict(preset) for name, preset in self.presets.items()}, indent=2),
            encoding="utf-8",
        )


class ClickerManager:
    def __init__(self) -> None:
        self.clicker = Clicker()
        self.load()

    def load(self) -> None:
        if not CLICKER_FILE.exists():
            return
        try:
            payload = json.loads(CLICKER_FILE.read_text(encoding="utf-8"))
            if "random_interval_offset_min_ms" not in payload or "random_interval_offset_max_ms" not in payload:
                legacy_offset = max(0, int(payload.get("random_interval_offset_ms", 0) or 0))
                payload.setdefault("random_interval_offset_min_ms", legacy_offset)
                payload.setdefault("random_interval_offset_max_ms", legacy_offset)
            payload.pop("random_interval_offset_ms", None)
            self.clicker = Clicker(**payload)
        except Exception:
            self.clicker = Clicker()

    def save(self) -> None:
        CLICKER_FILE.write_text(json.dumps(asdict(self.clicker), indent=2), encoding="utf-8")


class ThemeManager:
    def __init__(self) -> None:
        self.theme = Theme()
        self.presets = {
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

    def light_theme(self) -> Theme:
        return Theme(
            mode="light",
            background="#F1F5F9",
            panel="#FFFFFF",
            text="#0F172A",
            muted="#64748B",
            button="#E2E8F0",
            accent="#2563EB",
            border="#CBD5E1",
            input_bg="#FFFFFF",
            gradient_on=False,
            grad_start="#F1F5F9",
            grad_end="#E2E8F0",
            grad_third="",
            grad_dir="top-bottom",
        )

    def dark_theme(self) -> Theme:
        return Theme(
            mode="dark",
            background="#101010",
            panel="#171717",
            text="#D6D6D6",
            muted="#8A8A8A",
            button="#242424",
            accent="#2FA247",
            border="#2B2B2B",
            input_bg="#202020",
            gradient_on=False,
            grad_start="#101010",
            grad_end="#181818",
            grad_third="",
            grad_dir="top-bottom",
        )


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AutoClicker")
        self.root.geometry("760x470")
        self.root.minsize(700, 430)
        self.root.resizable(True, True)
        self.tm = ThemeManager()
        self.sm = SettingsManager()
        self.cm = ClickerManager()
        self.cfg = self.cm.clicker
        self.mouse = mouse.Controller()
        self.running = False
        self.thread: threading.Thread | None = None
        self.hk: keyboard.GlobalHotKeys | None = None
        self.capture: keyboard.Listener | None = None
        self.mods: set[str] = set()
        self.segment_groups: dict[str, tuple[tk.StringVar, tk.Frame, list[tuple[tk.Button, str]], object | None]] = {}
        self.settings_window: tk.Toplevel | None = None
        self.current_scale = 1.0
        self.animated_buttons: list[dict[str, object]] = []
        self._pending_apply_job: str | None = None
        self._pending_resize_job: str | None = None
        self._pending_resize_settle_job: str | None = None
        self._pending_settings_resize_job: str | None = None
        self._pending_settings_resize_settle_job: str | None = None
        self._high_res_timer_active = False
        self._high_res_timer_period_ms = 1
        self._priority_boost_active = False
        self._previous_priority_class: int | None = None
        self.sync_interval_samples_ms: list[float] = []
        self.sync_interval_errors_ms: list[float] = []
        self.sync_late_clicks = 0
        self._last_sync_stats_ui_job: str | None = None
        self.engine_bridge = EngineBridge(self._handle_engine_message)
        self.engine_backend_active = False
        self.hotkey_editing = False
        self.current_clicker_view = "main"
        self.current_main_view = "autoclicker"
        self.debug_enabled = False
        self._last_root_size: tuple[int, int] = (0, 0)
        self._last_settings_size: tuple[int, int] = (0, 0)
        self._init_vars()
        self._build()
        self._apply_theme()
        self._apply_startup_settings()
        self._start_hotkeys()
        self.root.after(50, lambda: self._apply_visible_settings(update_status=False))
        self.root.after(120, self._finalize_startup_ui)
        self.root.bind("<Configure>", self._on_configure)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_vars(self) -> None:
        t = self.tm.theme
        c = self.cfg
        cps = max(1, round(1000 / max(1, c.interval_ms)))
        self.interval_var = tk.StringVar(value=str(c.interval_ms))
        self.speed_var = tk.StringVar(value=str(cps))
        self.timing_mode_var = tk.StringVar(value=(c.timing_mode if c.timing_mode in {"cps", "interval"} else "cps"))
        total_ms = max(1, c.interval_ms)
        hours, rem = divmod(total_ms, 3_600_000)
        minutes, rem = divmod(rem, 60_000)
        seconds, milliseconds = divmod(rem, 1000)
        self.interval_hours_var = tk.StringVar(value=str(hours) if hours else "")
        self.interval_minutes_var = tk.StringVar(value=str(minutes) if minutes else "")
        self.interval_seconds_var = tk.StringVar(value=str(seconds) if seconds else "")
        self.interval_milliseconds_var = tk.StringVar(value=str(milliseconds) if milliseconds else str(total_ms))
        self.click_type_var = tk.StringVar(value=c.click_type)
        self.button_var = tk.StringVar(value=c.mouse_button)
        self.jitter_enabled_var = tk.BooleanVar(value=getattr(c, "jitter_enabled", False))
        self.jitter_radius_var = tk.StringVar(value=str(max(0, int(getattr(c, "jitter_radius_px", 3)))))
        self.start_var = tk.StringVar(value=c.start_hotkey)
        self.stop_var = tk.StringVar(value=c.stop_hotkey)
        self.toggle_var = tk.StringVar(value=c.toggle_hotkey)
        s = self.sm.settings
        self.auto_scale_text_var = tk.BooleanVar(value=s.auto_scale_text)
        self.auto_scale_controls_var = tk.BooleanVar(value=s.auto_scale_controls)
        self.base_scale_var = tk.DoubleVar(value=s.base_scale)
        self.component_scale_var = tk.DoubleVar(value=s.component_scale)
        self.high_precision_timing_var = tk.BooleanVar(value=s.high_precision_timing)
        self.process_priority_boost_var = tk.BooleanVar(value=getattr(s, "process_priority_boost", False))
        self.precision_mode_var = tk.BooleanVar(value=getattr(s, "precision_mode", False))
        self.random_interval_offset_min_var = tk.StringVar(
            value=str(max(0, int(getattr(s, "random_interval_offset_min_ms", getattr(c, "random_interval_offset_min_ms", 0)))))
        )
        self.random_interval_offset_max_var = tk.StringVar(
            value=str(max(0, int(getattr(s, "random_interval_offset_max_ms", getattr(c, "random_interval_offset_max_ms", 0)))))
        )
        self.preview_view_var = tk.StringVar(value="main")
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
        self.preset_mode_var = tk.StringVar(value="design")
        self.preset_selected_var = tk.StringVar()

    def _build(self) -> None:
        self.bg_canvas = tk.Canvas(self.root, highlightthickness=0, bd=0)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.container = tk.Frame(self.root, bd=0, highlightthickness=0)
        self.container.place(x=0, y=0, relwidth=1, relheight=1)
        self.panel = tk.Frame(self.container, bd=0, highlightthickness=1)
        self.panel.pack(fill="both", expand=True, padx=16, pady=12)

        self.accent_bar = tk.Frame(self.panel, height=3, bd=0, highlightthickness=0)
        self.accent_bar.pack(fill="x", side="top")

        self.topbar = tk.Frame(self.panel, bd=0, highlightthickness=0)
        self.topbar.pack(fill="x", padx=16, pady=(12, 10))
        self.title_label = tk.Label(self.topbar, text="AutoClicker", anchor="w")
        self.title_label.pack(side="left")
        self.window_icons = tk.Label(self.topbar, text="Resize ready", anchor="e")
        self.window_icons.pack(side="right", padx=(0, 10))
        self.settings_button_slot = self._build_fixed_button_slot(self.topbar)
        self.settings_button_slot.pack(side="right", padx=(0, 10))
        self.settings_button = self._create_animated_button(self.settings_button_slot, "⚙", self.open_settings)
        self.settings_button.pack(fill="both", expand=True)
        self.info_button_slot = self._build_fixed_button_slot(self.topbar)
        self.info_button_slot.pack(side="right", padx=(0, 10))
        self.info_button = self._create_animated_button(self.info_button_slot, "Info", self.toggle_info_view)
        self.info_button.pack(fill="both", expand=True)

        self.main_area = tk.Frame(self.panel, bd=0, highlightthickness=0)
        self.main_area.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self.main_area.rowconfigure(0, weight=1)
        self.main_area.columnconfigure(0, weight=5)
        self.main_area.columnconfigure(1, weight=3)

        self.clicker_card = self._build_card(self.main_area, "Autoclicker")
        self.clicker_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.clicker_settings_button = self._create_animated_button(self.clicker_card._header, "⚙", self.toggle_clicker_settings, width=3)  # type: ignore[attr-defined]
        self.clicker_settings_button.pack(side="right")
        self.clicker_body = tk.Frame(self.clicker_card, bd=0, highlightthickness=0)
        self.clicker_body.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self.form = tk.Frame(self.clicker_body, bd=0, highlightthickness=0)
        self.form.pack(fill="both", expand=True)
        self.form.grid_columnconfigure(1, weight=1)
        self.form.grid_columnconfigure(3, weight=1)

        self._grid_label(self.form, "Click Speed", 0, 0)
        self.speed_input = self._build_input(self.form, self.speed_var, width=8)
        self.speed_input.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=6)
        self.speed_unit = tk.Label(self.form, text="cps")
        self.speed_unit.grid(row=0, column=1, sticky="e", padx=(0, 8))

        self._grid_label(self.form, "Button", 0, 2)
        self.button_segment = self._build_segment(
            self.form,
            "mouse_button",
            self.button_var,
            [("L", "left"), ("M", "middle"), ("R", "right")],
            command=self._apply_clicker_selection,
        )
        self.button_segment.grid(row=0, column=3, sticky="ew", pady=6)

        self._grid_label(self.form, "Timing Mode", 1, 0)
        self.timing_mode_combo = ttk.Combobox(
            self.form,
            textvariable=self.timing_mode_var,
            values=["cps", "interval"],
            state="readonly",
        )
        self.timing_mode_combo.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=6)
        self.timing_mode_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_timing_mode_changed())

        self._grid_label(self.form, "Interval", 1, 2)
        self.interval_fields = tk.Frame(self.form, bd=0, highlightthickness=0)
        self.interval_fields.grid(row=1, column=3, sticky="ew", pady=6)
        self.interval_ms_input = self._build_input(self.interval_fields, self.interval_milliseconds_var, width=5)
        self.interval_ms_input.pack(side="left")
        self.interval_ms_label = tk.Label(self.interval_fields, text="ms")
        self.interval_ms_label.pack(side="left", padx=(4, 8))
        self.interval_sec_input = self._build_input(self.interval_fields, self.interval_seconds_var, width=4)
        self.interval_sec_input.pack(side="left")
        self.interval_sec_label = tk.Label(self.interval_fields, text="s")
        self.interval_sec_label.pack(side="left", padx=(4, 8))
        self.interval_min_input = self._build_input(self.interval_fields, self.interval_minutes_var, width=4)
        self.interval_min_input.pack(side="left")
        self.interval_min_label = tk.Label(self.interval_fields, text="m")
        self.interval_min_label.pack(side="left", padx=(4, 8))
        self.interval_hour_input = self._build_input(self.interval_fields, self.interval_hours_var, width=4)
        self.interval_hour_input.pack(side="left")
        self.interval_hour_label = tk.Label(self.interval_fields, text="h")
        self.interval_hour_label.pack(side="left", padx=(4, 0))

        self._grid_label(self.form, "Toggle Key", 2, 0)
        self.toggle_summary = tk.Label(self.form, textvariable=self.toggle_var, anchor="w")
        self.toggle_summary.grid(row=2, column=1, sticky="w", padx=(0, 12), pady=6)
        self.hotkey_hint = tk.Label(self.form, text="Open the small gear on this card to edit the toggle keybind.", anchor="w")
        self.hotkey_hint.grid(row=2, column=3, sticky="w", pady=6)

        self.action_row = tk.Frame(self.form, bd=0, highlightthickness=0)
        self.action_row.grid(row=3, column=0, columnspan=4, sticky="w", pady=(12, 0))
        self.start_button_slot = self._build_fixed_button_slot(self.action_row, width=58, height=30)
        self.start_button_slot.pack(side="left", padx=(0, 8))
        self.start_button = self._create_animated_button(self.start_button_slot, "Start", self.start)
        self.start_button.pack(fill="both", expand=True)
        self.stop_button_slot = self._build_fixed_button_slot(self.action_row, width=58, height=30)
        self.stop_button_slot.pack(side="left", padx=(0, 8))
        self.stop_button = self._create_animated_button(self.stop_button_slot, "Stop", self.stop)
        self.stop_button.pack(fill="both", expand=True)
        self.apply_button_slot = self._build_fixed_button_slot(self.action_row, width=64, height=30)
        self.apply_button_slot.pack(side="left")
        self.apply_button = self._create_animated_button(self.apply_button_slot, "Apply", self.apply_clicker)
        self.apply_button.pack(fill="both", expand=True)

        self.hotkey_panel = tk.Frame(self.clicker_body, bd=0, highlightthickness=0)
        self.hotkey_panel.columnconfigure(1, weight=1)
        self._grid_label(self.hotkey_panel, "Toggle Key", 0, 0)
        self.toggle_hotkey_input = self._build_input(self.hotkey_panel, self.toggle_var)
        self.toggle_hotkey_input.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=6)
        self.hotkey_panel_hint = tk.Label(self.hotkey_panel, text="Click the field, press your combo, then apply it.", anchor="w", justify="left")
        self.hotkey_panel_hint.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 10))
        self.hotkey_panel_actions = tk.Frame(self.hotkey_panel, bd=0, highlightthickness=0)
        self.hotkey_panel_actions.grid(row=2, column=0, columnspan=2, sticky="w")
        self.hotkey_apply_button = self._create_animated_button(self.hotkey_panel_actions, "Apply Hotkey", self.apply_hotkeys)
        self.hotkey_apply_button.pack(side="left", padx=(0, 8))
        self.hotkey_back_button = self._create_animated_button(self.hotkey_panel_actions, "Back", self.toggle_clicker_settings)
        self.hotkey_back_button.pack(side="left")

        self.sidebar = tk.Frame(self.main_area, bd=0, highlightthickness=0)
        self.sidebar.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.sidebar.rowconfigure(0, weight=0)
        self.sidebar.rowconfigure(1, weight=1)
        self.sidebar.columnconfigure(0, weight=1)

        self.extra_features_card = self._build_card(self.sidebar, "Extra Features")
        self.extra_features_card.grid(row=0, column=0, sticky="new")
        self.extra_features_body = tk.Frame(self.extra_features_card, bd=0, highlightthickness=0)
        self.extra_features_body.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.extra_features_form = tk.Frame(self.extra_features_body, bd=0, highlightthickness=0)
        self.extra_features_form.pack(fill="x")
        self.extra_features_form.grid_columnconfigure(1, weight=1)

        self.jitter_toggle = tk.Checkbutton(
            self.extra_features_form,
            text="Enable jitter clicking",
            variable=self.jitter_enabled_var,
            command=lambda: self.apply_clicker(update_status=False),
            anchor="w",
        )
        self.jitter_toggle.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self._grid_label(self.extra_features_form, "Jitter Radius", 1, 0)
        self.jitter_radius_row = tk.Frame(self.extra_features_form, bd=0, highlightthickness=0)
        self.jitter_radius_row.grid(row=1, column=1, sticky="w", pady=6)
        self.jitter_radius_input = self._build_input(self.jitter_radius_row, self.jitter_radius_var, width=6)
        self.jitter_radius_input.pack(side="left")
        self.jitter_radius_label = tk.Label(self.jitter_radius_row, text="px")
        self.jitter_radius_label.pack(side="left", padx=(4, 0))
        self.extra_features_note = tk.Label(
            self.extra_features_body,
            text="Jitter clicking adds a small random offset around your cursor for each click, then returns to the original position.",
            justify="left",
            anchor="nw",
            wraplength=220,
        )
        self.extra_features_note.pack(fill="x", pady=(6, 10))
        self.extra_features_action_row = tk.Frame(self.extra_features_body, bd=0, highlightthickness=0)
        self.extra_features_action_row.pack(fill="x")
        self.extra_features_apply_button_slot = self._build_fixed_button_slot(self.extra_features_action_row, width=94, height=30)
        self.extra_features_apply_button_slot.pack(side="left")
        self.extra_features_apply_button = self._create_animated_button(
            self.extra_features_apply_button_slot,
            "Apply Extras",
            self.apply_clicker,
        )
        self.extra_features_apply_button.pack(fill="both", expand=True)

        self.sidebar_spacer = tk.Frame(self.sidebar, bd=0, highlightthickness=0, height=1)
        self.sidebar_spacer.grid(row=1, column=0, sticky="nsew")

        self.info_card = self._build_card(self.main_area, "Info")
        self.info_card.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.info_body = tk.Frame(self.info_card, bd=0, highlightthickness=0)
        self.info_body.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.info_title = tk.Label(self.info_body, text="How To Use", justify="left", anchor="nw")
        self.info_title.pack(fill="x")
        self.component_note = tk.Label(
            self.info_body,
            text="1. Choose clicks-per-second or a direct interval, then set the mouse button.\n2. Use Extra Features to enable jitter clicking if you want randomized cursor offsets.\n3. Use the small gear to change the toggle keybind.\n4. Press Apply, then use Start/Stop or the toggle hotkey.\n\nAbout: AutoClicker saves styling, layout, and clicker settings.",
            justify="left",
            anchor="nw",
            wraplength=230,
        )
        self.component_note.pack(fill="x", pady=(4, 0))
        self.sync_stats_title = tk.Label(self.info_body, text="Sync Stats", justify="left", anchor="nw")
        self.sync_stats_title.pack(fill="x", pady=(10, 0))
        self.sync_stats_summary = tk.Label(
            self.info_body,
            text="No click timing samples yet. Start the autoclicker to collect live sync stats.",
            justify="left",
            anchor="nw",
            wraplength=230,
        )
        self.sync_stats_summary.pack(fill="x", pady=(4, 0))
        self.test_row = tk.Frame(self.info_body, bd=0, highlightthickness=0)
        self.test_row.pack(fill="x", pady=(8, 0))
        self.run_tests_button_slot = self._build_fixed_button_slot(self.test_row, width=104, height=30)
        self.run_tests_button_slot.pack(side="left")
        self.run_tests_button = self._create_animated_button(self.run_tests_button_slot, "Run Safe Tests", self.run_safe_tests)
        self.run_tests_button.pack(fill="both", expand=True)
        self.test_summary = tk.Label(self.test_row, text="No test run yet.", anchor="w")
        self.test_summary.pack(side="left", padx=(12, 0))
        self.test_output_wrap = tk.Frame(self.info_body, bd=0, highlightthickness=0)
        self.test_output_wrap.pack(fill="x", expand=False, pady=(8, 0))
        self.test_output_wrap.configure(height=42)
        self.test_output_wrap.pack_propagate(False)
        self.test_output = tk.Text(self.test_output_wrap, height=2, wrap="word", relief="flat", bd=0)
        self.test_output.pack(side="left", fill="both", expand=True)
        self.test_output_scroll = tk.Scrollbar(self.test_output_wrap, orient="vertical", command=self.test_output.yview)
        self.test_output.configure(yscrollcommand=self.test_output_scroll.set)
        self._set_test_output_text("Safe test output will appear here after you run the suite.")
        self.test_output_visible = False

        self.footer = tk.Frame(self.panel, bd=0, highlightthickness=0)
        self.footer.pack(fill="x", padx=16, pady=(0, 10))
        self.status = tk.Label(self.footer, text="Ready", anchor="w")
        self.status.pack(side="left")
        self.footer_right = tk.Frame(self.footer, bd=0, highlightthickness=0)
        self.footer_right.pack_propagate(False)
        self.footer_right.pack(side="right", padx=(16, 12))
        self.helper_text = tk.Label(
            self.footer_right,
            text="Responsive layout and saved settings.",
            anchor="e",
            justify="right",
            padx=6,
        )
        self.helper_text.pack(side="right")

        self.speed_input.bind("<Return>", lambda _e: self.apply_clicker())
        self.speed_input.bind("<FocusOut>", lambda _e: self.apply_clicker(update_status=False))
        self.speed_input.bind("<KeyRelease>", lambda _e: self._schedule_visible_apply())
        for entry in (
            self.interval_ms_input,
            self.interval_sec_input,
            self.interval_min_input,
            self.interval_hour_input,
        ):
            entry.bind("<Return>", lambda _e: self.apply_clicker())
            entry.bind("<FocusOut>", lambda _e: self.apply_clicker(update_status=False))
            entry.bind("<KeyRelease>", lambda _e: self._schedule_visible_apply())
        self.jitter_radius_input.bind("<Return>", lambda _e: self.apply_clicker())
        self.jitter_radius_input.bind("<FocusOut>", lambda _e: self.apply_clicker(update_status=False))
        self.jitter_radius_input.bind("<KeyRelease>", lambda _e: self._schedule_visible_apply())
        self._bind_hotkey_entry(self.toggle_hotkey_input, "toggle")
        self._sync_timing_mode_ui()
        self._show_clicker_view("main")
        self._show_main_view("autoclicker")

    def _grid_label(self, parent: tk.Widget, text: str, row: int, column: int) -> tk.Label:
        label = tk.Label(parent, text=text, anchor="w")
        label.grid(row=row, column=column, sticky="w", padx=(0, 8), pady=6)
        return label

    def _build_card(self, parent: tk.Widget, title: str) -> tk.Frame:
        card = tk.Frame(parent, bd=0, highlightthickness=1)
        header = tk.Frame(card, bd=0, highlightthickness=0)
        header.pack(fill="x", padx=14, pady=(12, 8))
        title_label = tk.Label(header, text=title, anchor="w")
        title_label.pack(side="left")
        card._title_label = title_label  # type: ignore[attr-defined]
        card._header = header  # type: ignore[attr-defined]
        return card

    def _build_fixed_button_slot(self, parent: tk.Widget, width: int = 76, height: int = 42) -> tk.Frame:
        slot = tk.Frame(parent, width=width, height=height, bd=0, highlightthickness=0)
        slot.pack_propagate(False)
        return slot

    def _build_input(self, parent: tk.Widget, var: tk.StringVar, width: int = 14) -> tk.Entry:
        entry = tk.Entry(parent, textvariable=var, relief="flat", bd=0, width=width)
        return entry

    def _build_settings_section_label(self, parent: tk.Widget, text: str) -> tk.Label:
        return tk.Label(parent, text=text, anchor="w")

    def _build_settings_note(self, parent: tk.Widget, text: str, wraplength: int = 260) -> tk.Label:
        return tk.Label(parent, text=text, justify="left", anchor="w", wraplength=wraplength)

    def _build_settings_color_control(
        self,
        parent: tk.Widget,
        row: int,
        column: int,
        label_text: str,
        var: tk.StringVar,
        *,
        with_picker: bool = False,
    ) -> tuple[tk.Label, tk.Frame, tk.Entry, tk.Button | None]:
        wrap = tk.Frame(parent, bd=0, highlightthickness=0)
        wrap.grid(row=row, column=column, sticky="ew")
        wrap.columnconfigure(0, weight=1)
        label = tk.Label(wrap, text=label_text, anchor="w")
        label.grid(row=0, column=0, sticky="w")
        entry = self._build_input(wrap, var)
        entry.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        pick_button = None
        if with_picker:
            pick_button = self._create_animated_button(wrap, "Pick", lambda current=var: self.pick(current))
            pick_button.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
        return label, wrap, entry, pick_button

    def _bind_hotkey_entry(self, entry: tk.Entry, target: str) -> None:
        entry.bind("<FocusIn>", lambda _e, t=target: self._begin_hotkey_edit(t))
        entry.bind("<FocusOut>", lambda _e: self._end_hotkey_edit())
        entry.bind("<KeyPress>", lambda event, t=target: self._capture_hotkey_from_entry(event, t))

    def _begin_hotkey_edit(self, target: str) -> None:
        self.hotkey_editing = True
        self._set_status(f"Press a key combo for {target}", "muted")

    def _end_hotkey_edit(self) -> None:
        self.hotkey_editing = False

    def toggle_clicker_settings(self) -> None:
        next_view = "hotkey" if self.current_clicker_view == "main" else "main"
        self._show_clicker_view(next_view)

    def toggle_info_view(self) -> None:
        self._show_main_view("autoclicker" if self.current_main_view == "info" else "info")

    def _show_main_view(self, view: str) -> None:
        self.current_main_view = view
        if view == "info":
            self.clicker_card.grid_remove()
            self.sidebar.grid_remove()
            self.info_card.grid()
            self.info_button.configure(text="Close")
            self._set_status("Info", "muted")
        else:
            self.info_card.grid_remove()
            self._layout_main_cards()
            self.info_button.configure(text="Info")
            if self.running:
                self._set_status("Running", "running")
            else:
                self._set_status("Ready", "running")
        self.root.update_idletasks()
        self.current_scale = 0.0
        self._apply_responsive_scale()
        self._draw_bg()
        self._refresh_wrapped_text()
        self._debug_info_layout(f"show_main_view:{view}")
        self.root.after(50, lambda v=view: self._debug_info_layout(f"show_main_view_after_idle:{v}"))

    def _show_clicker_view(self, view: str) -> None:
        self.current_clicker_view = view
        if view == "hotkey":
            self.form.pack_forget()
            self.hotkey_panel.pack(fill="both", expand=True)
            self._set_status("Toggle hotkey settings", "muted")
        else:
            self.hotkey_panel.pack_forget()
            self.form.pack(fill="both", expand=True)
            if self.running:
                self._set_status("Running", "running")
            else:
                self._set_status("Ready", "running")

    def _layout_main_cards(self, recompute: bool = True) -> None:
        self.main_area.update_idletasks()
        self.main_area.rowconfigure(0, weight=1)
        self.main_area.columnconfigure(0, weight=5)
        self.main_area.columnconfigure(1, weight=3)
        self.clicker_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)
        self.sidebar.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=0)

    def run_safe_tests(self) -> None:
        self._show_test_output()
        self.test_summary.configure(text="Running safe tests...")
        self._set_test_output_text("Running safe tests...\n")
        self.run_tests_button.configure(state="disabled")
        thread = threading.Thread(target=self._run_safe_tests_worker, daemon=True)
        thread.start()

    def _show_test_output(self) -> None:
        if self.test_output_visible:
            return
        self.test_output_wrap.pack_configure(fill="both", expand=True)
        self.test_output_wrap.configure(height=86)
        self.test_output.configure(height=5)
        self.test_output_scroll.pack(side="right", fill="y")
        self.test_output_visible = True
        self.root.update_idletasks()
        self._apply_responsive_scale()
        self._debug_info_layout("show_test_output")

    def _set_test_output_text(self, text: str) -> None:
        self.test_output.configure(state="normal")
        self.test_output.delete("1.0", "end")
        self.test_output.insert("1.0", text)
        self.test_output.yview_moveto(0.0)
        self.test_output.mark_set("insert", "1.0")
        self.test_output.configure(state="disabled")

    def _reset_sync_stats(self) -> None:
        self.sync_interval_samples_ms = []
        self.sync_target_intervals_ms = []
        self.sync_interval_errors_ms = []
        self.sync_late_clicks = 0
        if getattr(self, "root", None):
            try:
                self.root.after(0, self._refresh_sync_stats_display)
            except Exception:
                pass

    def _sync_stats_text(self) -> str:
        if not self.sync_interval_samples_ms:
            return "No click timing samples yet. Start the autoclicker to collect live sync stats."
        avg_ms = statistics.fmean(self.sync_interval_samples_ms)
        avg_target_ms = statistics.fmean(self.sync_target_intervals_ms) if self.sync_target_intervals_ms else avg_ms
        min_ms = min(self.sync_interval_samples_ms)
        max_ms = max(self.sync_interval_samples_ms)
        avg_error_ms = statistics.fmean(self.sync_interval_errors_ms) if self.sync_interval_errors_ms else 0.0
        actual_cps = 1000.0 / avg_ms if avg_ms > 0 else 0.0
        target_cps = 1000.0 / avg_target_ms if avg_target_ms > 0 else 0.0
        return (
            f"Samples: {len(self.sync_interval_samples_ms)}\n"
            f"Actual CPS: {actual_cps:.2f}\n"
            f"Target CPS: {target_cps:.2f}\n"
            f"Average interval: {avg_ms:.2f} ms\n"
            f"Min / Max: {min_ms:.2f} ms / {max_ms:.2f} ms\n"
            f"Average error: {avg_error_ms:.2f} ms\n"
            f"Late clicks: {self.sync_late_clicks}"
        )

    def _refresh_sync_stats_display(self) -> None:
        self._last_sync_stats_ui_job = None
        if hasattr(self, "sync_stats_summary"):
            self.sync_stats_summary.configure(text=self._sync_stats_text())

    def _record_sync_sample(self, actual_interval_ms: float, target_interval_ms: float) -> None:
        self.sync_interval_samples_ms.append(actual_interval_ms)
        if len(self.sync_interval_samples_ms) > 200:
            self.sync_interval_samples_ms.pop(0)
        self.sync_target_intervals_ms.append(target_interval_ms)
        if len(self.sync_target_intervals_ms) > 200:
            self.sync_target_intervals_ms.pop(0)
        error_ms = abs(actual_interval_ms - target_interval_ms)
        self.sync_interval_errors_ms.append(error_ms)
        if len(self.sync_interval_errors_ms) > 200:
            self.sync_interval_errors_ms.pop(0)
        if actual_interval_ms - target_interval_ms > 2.0:
            self.sync_late_clicks += 1
        if getattr(self, "root", None) and self._last_sync_stats_ui_job is None:
            try:
                self._last_sync_stats_ui_job = self.root.after(0, self._refresh_sync_stats_display)
            except Exception:
                self._last_sync_stats_ui_job = None

    def _build_native_engine_config(self) -> NativeEngineConfig:
        interval_ms = float(max(1, int(self.cfg.interval_ms)))
        if self.timing_mode_var.get().strip().lower() == "cps":
            try:
                cps = max(1.0, float(self.speed_var.get().strip()))
                interval_ms = 1000.0 / cps
            except ValueError:
                interval_ms = float(max(1, int(self.cfg.interval_ms)))
        return NativeEngineConfig(
            interval_ms=interval_ms,
            button=str(self.cfg.mouse_button),
            double_click=str(self.cfg.click_type).strip().lower() == "double",
            jitter_enabled=bool(getattr(self.cfg, "jitter_enabled", False)),
            jitter_radius_px=max(0, int(getattr(self.cfg, "jitter_radius_px", 0))),
            random_interval_offset_min_ms=max(0, int(self.random_interval_offset_min_var.get().strip() or "0")),
            random_interval_offset_max_ms=max(0, int(self.random_interval_offset_max_var.get().strip() or "0")),
            high_precision_timing=bool(self.high_precision_timing_var.get()),
            process_priority_boost=bool(self.process_priority_boost_var.get()),
            precision_mode=bool(self.precision_mode_var.get()),
        )

    def _handle_engine_message(self, message: dict) -> None:
        if not getattr(self, "root", None):
            return
        try:
            self.root.after(0, lambda msg=message: self._handle_engine_message_main(msg))
        except Exception:
            pass

    def _handle_engine_message_main(self, message: dict) -> None:
        msg_type = str(message.get("type", "")).strip().lower()
        if msg_type == "syncsample":
            actual = float(message.get("actualIntervalMs", 0.0) or 0.0)
            target = float(message.get("targetIntervalMs", 0.0) or 0.0)
            if actual > 0 and target > 0:
                self._record_sync_sample(actual, target)
            return
        if msg_type == "error":
            self._set_status(str(message.get("message", "Native engine error")), "warning")

    def _run_safe_tests_worker(self) -> None:
        stream = io.StringIO()
        try:
            suite = unittest.defaultTestLoader.loadTestsFromName("test_app_logic")
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
            total = result.testsRun
            failed = len(result.failures) + len(result.errors)
            passed = total - failed
            summary = f"Passed {passed}/{total} tests"
            details = stream.getvalue().strip()
            if failed:
                summary += f" with {failed} failure(s)"
            self.root.after(0, lambda: self._finish_safe_tests(summary, details))
        except Exception as exc:
            details = stream.getvalue() + f"\nTest runner error: {exc}\n"
            self.root.after(0, lambda: self._finish_safe_tests("Safe tests failed to run", details))

    def _finish_safe_tests(self, summary: str, details: str) -> None:
        self.test_summary.configure(text=summary)
        self._set_test_output_text(details or summary)
        self.run_tests_button.configure(state="normal")

    def _capture_hotkey_from_entry(self, event: tk.Event, target: str) -> str:
        hotkey = self._format_hotkey_event(event)
        if not hotkey:
            return "break"
        self.toggle_var.set(hotkey)
        self.toggle_summary.configure(textvariable=self.toggle_var)
        self._set_status(f"{target.capitalize()} hotkey ready to apply", "muted")
        return "break"

    def _format_hotkey_event(self, event: tk.Event) -> str:
        keysym = str(event.keysym or "").lower()
        if not keysym:
            return ""
        modifiers: list[str] = []
        if event.state & 0x4:
            modifiers.append("<ctrl>")
        if event.state & 0x1:
            modifiers.append("<shift>")
        if event.state & 0x20000:
            modifiers.append("<alt>")

        modifier_keys = {
            "shift_l": "<shift>",
            "shift_r": "<shift>",
            "control_l": "<ctrl>",
            "control_r": "<ctrl>",
            "alt_l": "<alt>",
            "alt_r": "<alt>",
        }
        if keysym in modifier_keys:
            key = modifier_keys[keysym]
            return "+".join(sorted(set(modifiers + [key])))

        special_keys = {
            "space": "<space>",
            "return": "<enter>",
            "escape": "<esc>",
            "tab": "<tab>",
            "backspace": "<backspace>",
            "delete": "<delete>",
            "insert": "<insert>",
            "home": "<home>",
            "end": "<end>",
            "prior": "<page_up>",
            "next": "<page_down>",
            "up": "<up>",
            "down": "<down>",
            "left": "<left>",
            "right": "<right>",
        }
        if keysym in special_keys:
            key = special_keys[keysym]
        elif len(keysym) == 1 and keysym.isprintable():
            key = keysym
        else:
            key = f"<{keysym}>"
        return "+".join(modifiers + [key])

    def _create_animated_button(self, parent: tk.Widget, text: str, command, width: int | None = None) -> tk.Button:
        button = tk.Button(parent, text=text, relief="flat", bd=0, command=command, cursor="hand2")
        if width is not None:
            button.configure(width=width)
        spec = {"button": button, "state": "normal"}
        self.animated_buttons.append(spec)
        button.bind("<Enter>", lambda _e, s=spec: self._set_button_state(s, "hover"))
        button.bind("<Leave>", lambda _e, s=spec: self._set_button_state(s, "normal"))
        button.bind("<ButtonPress-1>", lambda _e, s=spec: self._set_button_state(s, "pressed"))
        button.bind("<ButtonRelease-1>", lambda _e, s=spec: self._set_button_state(s, "hover"))
        if hasattr(self, "tm"):
            self._style_animated_button(spec)
        return button

    def _set_button_state(self, spec: dict[str, object], state: str) -> None:
        spec["state"] = state
        self._style_animated_button(spec)
        button = spec["button"]
        label = button.cget("text")
        self._debug_layout(f"animated_button:{label}:{state}")

    def _prune_animated_buttons(self) -> None:
        alive: list[dict[str, object]] = []
        for spec in self.animated_buttons:
            button = spec.get("button")
            if isinstance(button, tk.Widget) and button.winfo_exists():
                alive.append(spec)
        self.animated_buttons = alive

    def _style_animated_button(self, spec: dict[str, object]) -> None:
        t = self.tm.theme
        button = spec["button"]
        if not isinstance(button, tk.Widget) or not button.winfo_exists():
            return
        state = spec["state"]
        is_gear = button in {
            getattr(self, "settings_button", None),
            getattr(self, "clicker_settings_button", None),
        }
        fixed_pad = (10, 5)
        gear_foreground = t.accent if t.mode == "light" else "#F4F7F4"
        if state == "pressed":
            background = t.accent
            foreground = "#F4F7F4"
        elif state == "hover":
            background = "#0E0E0E" if is_gear else t.button
            foreground = gear_foreground if is_gear else t.text
        else:
            background = "#050505" if is_gear else t.button
            foreground = gear_foreground if is_gear else t.text
        button.configure(
            background=background,
            foreground=foreground,
            activebackground=background,
            activeforeground=foreground,
            relief="flat",
            overrelief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=t.border,
            highlightcolor=t.accent if state != "normal" else t.border,
            padx=fixed_pad[0],
            pady=fixed_pad[1],
        )

    def _build_segment(
        self,
        parent: tk.Widget,
        name: str,
        var: tk.StringVar,
        options: list[tuple[str, str]],
        command=None,
    ) -> tk.Frame:
        wrap = tk.Frame(parent, bd=0, highlightthickness=0)
        buttons: list[tuple[tk.Button, str]] = []
        for index, (label, value) in enumerate(options):
            btn = tk.Button(
                wrap,
                text=label,
                relief="flat",
                bd=0,
                width=2,
                padx=8,
                pady=3,
                command=lambda v=value, n=name: self._set_segment_value(n, v),
            )
            btn._segment_name = name  # type: ignore[attr-defined]
            btn._segment_value = value  # type: ignore[attr-defined]
            btn.pack(side="left", padx=(0, 4 if index < len(options) - 1 else 0))
            buttons.append((btn, value))
        self.segment_groups[name] = (var, wrap, buttons, command)
        return wrap

    def _set_segment_value(self, name: str, value: str) -> None:
        self._debug_layout(f"before_segment_change:{name}={value}")
        var, _wrap, _buttons, command = self.segment_groups[name]
        var.set(value)
        self._refresh_segments()
        self.root.update_idletasks()
        self._debug_layout(f"after_segment_refresh:{name}={value}")
        if command:
            command()
        self.root.update_idletasks()
        self._debug_layout(f"after_segment_command:{name}={value}")

    def _debug_layout(self, label: str) -> None:
        if not self.debug_enabled:
            return
        try:
            self.root.update_idletasks()
            lines = [f"[{time.strftime('%H:%M:%S')}] {label}"]
            lines.append(
                "window="
                f"{self.root.winfo_width()}x{self.root.winfo_height()} "
                f"panel={self.panel.winfo_width()}x{self.panel.winfo_height()} "
                f"main_area={self.main_area.winfo_width()}x{self.main_area.winfo_height()} "
                f"clicker_card={self.clicker_card.winfo_width()}x{self.clicker_card.winfo_height()} "
                f"extra_card={self.extra_features_card.winfo_width()}x{self.extra_features_card.winfo_height()}"
            )
            lines.append(
                "footer="
                f"{self.footer.winfo_width()}x{self.footer.winfo_height()} "
                f"status={self.status.winfo_width()}x{self.status.winfo_height()} "
                f"helper={self.helper_text.winfo_width()}x{self.helper_text.winfo_height()}"
            )
            lines.append(
                "mapped="
                f"clicker={self.clicker_card.winfo_ismapped()} "
                f"extra={self.extra_features_card.winfo_ismapped()} "
                f"info={self.info_card.winfo_ismapped()} "
                f"form={self.form.winfo_ismapped()} "
                f"hotkey_panel={self.hotkey_panel.winfo_ismapped()}"
            )
            lines.append(
                "rows="
                f"row0_y={self.clicker_card.winfo_y()} row0_h={self.clicker_card.winfo_height()} "
                f"row1_y={self.extra_features_card.winfo_y()} row1_h={self.extra_features_card.winfo_height()}"
            )
            lines.append(
                "form="
                f"{self.form.winfo_width()}x{self.form.winfo_height()} "
                f"action_row={self.action_row.winfo_width()}x{self.action_row.winfo_height()} "
                f"action_y={self.action_row.winfo_y()}"
            )
            if "mouse_button" in self.segment_groups:
                var, wrap, buttons, _command = self.segment_groups["mouse_button"]
                lines.append(
                    "segment_wrap="
                    f"{wrap.winfo_width()}x{wrap.winfo_height()} selected={var.get()}"
                )
                for btn, value in buttons:
                    lines.append(
                        f"segment_button:{value}="
                        f"{btn.winfo_width()}x{btn.winfo_height()} "
                        f"req={btn.winfo_reqwidth()}x{btn.winfo_reqheight()} "
                        f"x={btn.winfo_x()} y={btn.winfo_y()}"
                    )
            for spec in self.animated_buttons:
                button = spec["button"]
                lines.append(
                    "animated_button:"
                    f"{button.cget('text')} state={spec['state']} "
                    f"{button.winfo_width()}x{button.winfo_height()} "
                    f"req={button.winfo_reqwidth()}x{button.winfo_reqheight()}"
                )
            DEBUG_LOG_FILE.write_text(
                (DEBUG_LOG_FILE.read_text(encoding='utf-8') if DEBUG_LOG_FILE.exists() else "")
                + "\n".join(lines) + "\n\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    def _set_status(self, text: str, tone: str = "accent") -> None:
        palette = {
            "accent": self.tm.theme.accent,
            "muted": self.tm.theme.muted,
            "warning": "#F59E0B",
            "running": "#22C55E",
            "error": "#EF4444",
        }
        self.status.configure(text=text, foreground=palette.get(tone, self.tm.theme.accent))

    def _apply_visible_settings(self, update_status: bool = True) -> None:
        if self._pending_apply_job:
            self.root.after_cancel(self._pending_apply_job)
            self._pending_apply_job = None
        self.apply_clicker(update_status=update_status)

    def _apply_clicker_selection(self) -> None:
        self.apply_clicker(update_status=False)

    def _schedule_visible_apply(self) -> None:
        if self._pending_apply_job:
            self.root.after_cancel(self._pending_apply_job)
        self._pending_apply_job = self.root.after(250, lambda: self.apply_clicker(update_status=False))

    def _on_timing_mode_changed(self) -> None:
        self._sync_timing_mode_ui()
        self.apply_clicker(update_status=False)

    def _sync_timing_mode_ui(self) -> None:
        interval_enabled = self.timing_mode_var.get().strip().lower() == "interval"
        speed_state = "disabled" if interval_enabled else "normal"
        interval_state = "normal" if interval_enabled else "disabled"
        self.speed_input.configure(state=speed_state)
        interval_inputs = (
            self.interval_ms_input,
            self.interval_sec_input,
            self.interval_min_input,
            self.interval_hour_input,
        )
        for entry in interval_inputs:
            entry.configure(state=interval_state)

    def _interval_ms_from_parts(self) -> int:
        current_ms = max(1, getattr(self.cfg, "interval_ms", 100))

        def part(var: tk.StringVar) -> int:
            raw = var.get().strip()
            if not raw:
                return 0
            try:
                return max(0, int(raw))
            except ValueError:
                return 0

        total = (
            part(self.interval_milliseconds_var)
            + part(self.interval_seconds_var) * 1000
            + part(self.interval_minutes_var) * 60_000
            + part(self.interval_hours_var) * 3_600_000
        )
        return total if total > 0 else current_ms

    def _set_interval_parts_from_ms(self, total_ms: int) -> None:
        total_ms = max(1, int(total_ms))
        hours, rem = divmod(total_ms, 3_600_000)
        minutes, rem = divmod(rem, 60_000)
        seconds, milliseconds = divmod(rem, 1000)
        self.interval_hours_var.set(str(hours) if hours else "")
        self.interval_minutes_var.set(str(minutes) if minutes else "")
        self.interval_seconds_var.set(str(seconds) if seconds else "")
        self.interval_milliseconds_var.set(str(milliseconds) if milliseconds else "")

    def _save_clicker_settings(self) -> None:
        self.cm.clicker = Clicker(**asdict(self.cfg))
        self.cm.save()

    def _effective_interval_ms(self) -> int:
        base_ms = max(1, int(getattr(self.cfg, "interval_ms", 100)))
        try:
            min_offset_ms = max(0, int(self.random_interval_offset_min_var.get().strip() or "0"))
        except ValueError:
            min_offset_ms = max(0, int(getattr(self.cfg, "random_interval_offset_min_ms", 0)))
        try:
            max_offset_ms = max(0, int(self.random_interval_offset_max_var.get().strip() or "0"))
        except ValueError:
            max_offset_ms = max(0, int(getattr(self.cfg, "random_interval_offset_max_ms", 0)))
        low, high = sorted((min_offset_ms, max_offset_ms))
        if high <= 0:
            return base_ms
        return max(1, base_ms + random.randint(low, high))

    def _apply_startup_settings(self) -> None:
        self.apply_clicker(update_status=False, save=False)
        self.apply_hotkeys(update_status=False, restart=False, save=False)
        self._set_status("Ready", "running")

    def _finalize_startup_ui(self) -> None:
        if self.root.winfo_width() <= 1 or self.root.winfo_height() <= 1:
            self.root.after(120, self._finalize_startup_ui)
            return
        self.root.update_idletasks()
        self._refresh_segments()
        for spec in self.animated_buttons:
            self._style_animated_button(spec)
        self.current_scale = 0.0
        self._apply_responsive_scale()
        self._draw_bg()
        self._draw_preview()
        self._set_status("Ready", "running")
        self._debug_layout("startup_finalized")

    def _on_configure(self, _event: tk.Event) -> None:
        if _event.widget is not self.root:
            return
        size = (self.root.winfo_width(), self.root.winfo_height())
        if size == self._last_root_size:
            return
        self._last_root_size = size
        if self._pending_resize_job is not None:
            self.root.after_cancel(self._pending_resize_job)
        self._pending_resize_job = self.root.after(60, self._apply_live_resize_updates)
        if self._pending_resize_settle_job is not None:
            self.root.after_cancel(self._pending_resize_settle_job)
        self._pending_resize_settle_job = self.root.after(220, self._apply_settled_resize_updates)

    def _apply_live_resize_updates(self) -> None:
        self._pending_resize_job = None
        self._fit_footer_helper_text()

    def _apply_settled_resize_updates(self) -> None:
        self._pending_resize_settle_job = None
        self._apply_responsive_scale(force=True)
        self._draw_bg()

    def _compute_scale(self) -> float:
        width_scale = self.root.winfo_width() / 760
        height_scale = self.root.winfo_height() / 470
        base = float(self.base_scale_var.get() or 1.0)
        fit_scale = min(width_scale, height_scale)
        if fit_scale >= 1.0:
            return max(0.9, min(1.15, base))
        return max(0.85, min(1.15, fit_scale * base))

    def _apply_responsive_scale(self, force: bool = False, live: bool = False) -> None:
        scale = self._compute_scale()
        threshold = 0.08 if live else 0.03
        if not force and abs(scale - self.current_scale) < threshold:
            return
        if live:
            scale = round(scale / 0.04) * 0.04
        self.current_scale = scale
        text_scale = scale if self.auto_scale_text_var.get() else float(self.base_scale_var.get() or 1.0)
        control_scale = scale if self.auto_scale_controls_var.get() else float(self.base_scale_var.get() or 1.0)
        self._apply_scaled_fonts(text_scale, control_scale)
        if live:
            self._fit_footer_helper_text()
        else:
            self._refresh_wrapped_text()

    def _refresh_wrapped_text(self) -> None:
        if hasattr(self, "info_card"):
            info_width = max(220, self.info_card.winfo_width() - 36)
            self.component_note.configure(wraplength=info_width)
            self.sync_stats_summary.configure(wraplength=info_width)
        if hasattr(self, "extra_features_card"):
            extra_width = max(220, self.extra_features_card.winfo_width() - 36)
            self.extra_features_note.configure(wraplength=extra_width)
        self._fit_footer_helper_text()

    def _fit_footer_helper_text(self) -> None:
        if not hasattr(self, "footer") or not hasattr(self, "helper_text"):
            return
        base_size = getattr(self, "helper_base_font_size", 8)
        text = str(self.helper_text.cget("text"))
        helper_pad = int(self.helper_text.cget("padx") or 0)
        status_width = self.status.winfo_reqwidth()
        available_width = max(170, self.footer.winfo_width() - status_width - 36)
        fitted_size = base_size
        text_width = 0
        for size in range(base_size, 6, -1):
            measure_font = tkfont.Font(family="Segoe UI", size=size)
            text_width = measure_font.measure(text)
            if text_width + (helper_pad * 2) <= available_width:
                fitted_size = size
                break
        self.helper_text.configure(font=("Segoe UI", fitted_size), wraplength=0)
        helper_height = max(self.helper_text.winfo_reqheight(), self.status.winfo_reqheight())
        self.footer_right.configure(width=available_width, height=helper_height)

    def _debug_info_layout(self, label: str) -> None:
        if not self.debug_enabled or not hasattr(self, "info_card"):
            return
        try:
            self.root.update_idletasks()
            lines = [f"[{time.strftime('%H:%M:%S')}] info_layout:{label}"]
            lines.append(
                "info_card="
                f"{self.info_card.winfo_width()}x{self.info_card.winfo_height()} "
                f"mapped={self.info_card.winfo_ismapped()} "
                f"main_area={self.main_area.winfo_width()}x{self.main_area.winfo_height()}"
            )
            lines.append(
                "info_body="
                f"{self.info_body.winfo_width()}x{self.info_body.winfo_height()} "
                f"title={self.info_title.winfo_width()}x{self.info_title.winfo_height()} "
                f"note={self.component_note.winfo_width()}x{self.component_note.winfo_height()}"
            )
            lines.append(
                "mapped="
                f"clicker_card={self.clicker_card.winfo_ismapped()} "
                f"info_card={self.info_card.winfo_ismapped()} "
                f"form={self.form.winfo_ismapped()} "
                f"hotkey_panel={self.hotkey_panel.winfo_ismapped()} "
                f"test_row={self.test_row.winfo_ismapped()} "
                f"test_output_wrap={self.test_output_wrap.winfo_ismapped()} "
                f"test_output_visible={self.test_output_visible}"
            )
            lines.append(
                "test_row="
                f"{self.test_row.winfo_width()}x{self.test_row.winfo_height()} "
                f"summary={self.test_summary.winfo_width()}x{self.test_summary.winfo_height()} "
                f"button={self.run_tests_button.winfo_width()}x{self.run_tests_button.winfo_height()}"
            )
            lines.append(
                "test_output_wrap="
                f"{self.test_output_wrap.winfo_width()}x{self.test_output_wrap.winfo_height()} "
                f"text={self.test_output.winfo_width()}x{self.test_output.winfo_height()} "
                f"scroll={self.test_output_scroll.winfo_width()}x{self.test_output_scroll.winfo_height()} "
                f"text_req={self.test_output.winfo_reqwidth()}x{self.test_output.winfo_reqheight()}"
            )
            lines.append(
                "footer="
                f"{self.footer.winfo_width()}x{self.footer.winfo_height()} "
                f"footer_right={self.footer_right.winfo_width()}x{self.footer_right.winfo_height()} "
                f"status={self.status.winfo_width()}x{self.status.winfo_height()} "
                f"helper={self.helper_text.winfo_width()}x{self.helper_text.winfo_height()} "
                f"helper_req={self.helper_text.winfo_reqwidth()}x{self.helper_text.winfo_reqheight()}"
            )
            DEBUG_LOG_FILE.write_text(
                (DEBUG_LOG_FILE.read_text(encoding="utf-8") if DEBUG_LOG_FILE.exists() else "")
                + "\n".join(lines) + "\n\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    def _apply_scaled_fonts(self, text_scale: float, control_scale: float) -> None:
        title_size = max(10, round(11 * text_scale))
        label_size = max(8, round(9 * text_scale))
        control_size = max(8, round(9 * control_scale))
        pad_x = max(8, round(10 * control_scale))
        pad_y = max(2, round(4 * control_scale))
        self.helper_base_font_size = label_size

        self.title_label.configure(font=("Segoe UI Semibold", title_size))
        self.window_icons.configure(font=("Segoe UI", label_size))
        self.status.configure(font=("Segoe UI", label_size))
        self.helper_text.configure(font=("Segoe UI", label_size))
        self.hotkey_hint.configure(font=("Segoe UI", label_size))
        self.speed_unit.configure(font=("Segoe UI", max(7, label_size - 1)))
        self.interval_ms_label.configure(font=("Segoe UI", max(7, label_size - 1)))
        self.interval_sec_label.configure(font=("Segoe UI", max(7, label_size - 1)))
        self.interval_min_label.configure(font=("Segoe UI", max(7, label_size - 1)))
        self.interval_hour_label.configure(font=("Segoe UI", max(7, label_size - 1)))
        self.settings_button.configure(font=("Segoe UI Symbol", max(10, round(12 * control_scale))))
        self.info_button.configure(font=("Segoe UI Semibold", control_size), padx=pad_x, pady=pad_y)
        self.clicker_settings_button.configure(font=("Segoe UI Symbol", max(10, round(11 * control_scale))))
        slot_height = max(30, round(30 * control_scale))
        self.start_button_slot.configure(width=max(58, round(58 * control_scale)), height=slot_height)
        self.stop_button_slot.configure(width=max(58, round(58 * control_scale)), height=slot_height)
        self.apply_button_slot.configure(width=max(64, round(64 * control_scale)), height=slot_height)
        self.run_tests_button_slot.configure(width=max(104, round(104 * control_scale)), height=slot_height)
        self.start_button.configure(font=("Segoe UI Semibold", control_size), padx=pad_x, pady=pad_y)
        self.stop_button.configure(font=("Segoe UI Semibold", control_size), padx=pad_x, pady=pad_y)
        self.apply_button.configure(font=("Segoe UI Semibold", control_size), padx=pad_x, pady=pad_y)
        self.hotkey_apply_button.configure(font=("Segoe UI Semibold", control_size), padx=pad_x, pady=pad_y)
        self.hotkey_back_button.configure(font=("Segoe UI Semibold", control_size), padx=pad_x, pady=pad_y)
        self.run_tests_button.configure(font=("Segoe UI Semibold", control_size), padx=pad_x, pady=pad_y)
        self.extra_features_apply_button.configure(font=("Segoe UI Semibold", control_size), padx=pad_x, pady=pad_y)
        self.info_title.configure(font=("Segoe UI Semibold", max(9, round(10 * text_scale))))
        self.test_summary.configure(font=("Segoe UI", label_size))
        self.test_output.configure(font=("Consolas", max(8, round(8 * text_scale))))
        self.component_note.configure(font=("Segoe UI", label_size))
        self.component_note.configure(wraplength=max(180, self.info_card.winfo_width() - 36))
        self.sync_stats_title.configure(font=("Segoe UI Semibold", max(9, round(10 * text_scale))))
        self.sync_stats_summary.configure(font=("Segoe UI", label_size))
        self.sync_stats_summary.configure(wraplength=max(180, self.info_card.winfo_width() - 36))
        self.extra_features_note.configure(font=("Segoe UI", label_size))
        self.extra_features_note.configure(wraplength=max(180, self.extra_features_card.winfo_width() - 36))
        self.jitter_toggle.configure(font=("Segoe UI", label_size))
        self.jitter_radius_label.configure(font=("Segoe UI", max(7, label_size - 1)))
        for child in self.form.grid_slaves():
            if isinstance(child, tk.Label):
                child.configure(font=("Segoe UI", label_size))
        for child in self.hotkey_panel.grid_slaves():
            if isinstance(child, tk.Label):
                child.configure(font=("Segoe UI", label_size))
        self.clicker_card._title_label.configure(font=("Segoe UI Semibold", max(10, round(10 * text_scale))))  # type: ignore[attr-defined]
        self.extra_features_card._title_label.configure(font=("Segoe UI Semibold", max(10, round(10 * text_scale))))  # type: ignore[attr-defined]
        self.info_card._title_label.configure(font=("Segoe UI Semibold", max(10, round(10 * text_scale))))  # type: ignore[attr-defined]
        scale_component = float(self.component_scale_var.get() or 1.0)
        body_pad_x = max(8, round(12 * scale_component))
        body_pad_y = max(8, round(12 * scale_component))
        self.clicker_body.pack_configure(padx=body_pad_x, pady=(0, body_pad_y))
        self.extra_features_body.pack_configure(padx=body_pad_x, pady=(0, body_pad_y))
        self.info_body.pack_configure(padx=body_pad_x, pady=(0, max(8, body_pad_y - 4)))
        self.timing_mode_combo.configure(height=max(6, round(8 * control_scale)))
        for entry in (
            self.speed_input,
            self.jitter_radius_input,
            self.toggle_hotkey_input,
            self.interval_ms_input,
            self.interval_sec_input,
            self.interval_min_input,
            self.interval_hour_input,
        ):
            entry.configure(font=("Segoe UI Semibold", control_size))
        for _var, _wrap, buttons, _command in self.segment_groups.values():
            for btn, _value in buttons:
                btn.configure(font=("Segoe UI", control_size), padx=pad_x, pady=pad_y)
        self.extra_features_apply_button_slot.configure(width=max(94, round(94 * control_scale)), height=slot_height)

    def open_settings(self) -> None:
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        self._sync_theme_vars(self.tm.theme)
        win = tk.Toplevel(self.root)
        self.settings_window = win
        win.title("App Settings")
        win.geometry("940x700")
        win.minsize(820, 620)
        win.resizable(True, True)
        win.transient(self.root)
        win.grab_set()
        win.protocol("WM_DELETE_WINDOW", self.close_settings)
        win.bind("<Configure>", self._on_settings_configure)

        shell = tk.Frame(win, bd=0, highlightthickness=0)
        shell.pack(fill="both", expand=True, padx=12, pady=12)
        self.settings_shell = shell

        top = tk.Frame(shell, bd=0, highlightthickness=0)
        top.pack(fill="x", pady=(0, 10))
        self.settings_topbar = top
        self.settings_title = tk.Label(top, text="App Settings", anchor="w")
        self.settings_title.pack(side="left")
        self.settings_close_button = self._create_animated_button(top, "Close", self.close_settings)
        self.settings_close_button.pack(side="right")

        content = tk.Frame(shell, bd=0, highlightthickness=0)
        content.pack(fill="both", expand=True)
        self.settings_content = content
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)

        appearance_card = self._build_card(content, "Appearance Studio")
        appearance_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.settings_card = appearance_card
        self.appearance_body = tk.Frame(appearance_card, bd=0, highlightthickness=0)
        self.appearance_body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.appearance_body.columnconfigure(0, weight=1)

        self.appearance_intro = self._build_settings_note(
            self.appearance_body,
            "Tune the app palette here. Changes update the live preview and apply to the main window when you save them.",
            wraplength=420,
        )
        self.appearance_intro.grid(row=0, column=0, sticky="ew")

        self.appearance_top = tk.Frame(self.appearance_body, bd=0, highlightthickness=0)
        self.appearance_top.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        self.appearance_top.columnconfigure(1, weight=1)
        self.settings_theme_mode_label = tk.Label(self.appearance_top, text="Theme Mode", anchor="w")
        self.settings_theme_mode_label.grid(row=0, column=0, sticky="w", padx=(0, 12))
        self.settings_mode_combo = ttk.Combobox(self.appearance_top, textvariable=self.mode_var, values=["light", "dark", "custom"], state="readonly")
        self.settings_mode_combo.grid(row=0, column=1, sticky="ew", padx=(0, 16))
        self.settings_mode_combo.bind("<<ComboboxSelected>>", lambda _e: self.apply_theme())
        self.settings_accent_label = tk.Label(self.appearance_top, text="Accent", anchor="w")
        self.settings_accent_label.grid(row=0, column=2, sticky="w", padx=(8, 12))
        self.accent_entry = self._build_input(self.appearance_top, self.accent_var)
        self.accent_entry.grid(row=0, column=3, sticky="ew")
        self.appearance_top.columnconfigure(3, weight=1)

        self.palette_section_label = self._build_settings_section_label(self.appearance_body, "Color Palette")
        self.palette_section_label.grid(row=2, column=0, sticky="w", pady=(16, 0))
        self.palette_section_note = self._build_settings_note(
            self.appearance_body,
            "Pick the base surfaces on the left and the contrast colors on the right.",
            wraplength=420,
        )
        self.palette_section_note.grid(row=3, column=0, sticky="ew", pady=(2, 0))

        self.palette_grid = tk.Frame(self.appearance_body, bd=0, highlightthickness=0)
        self.palette_grid.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        self.palette_grid.columnconfigure(0, weight=1)
        self.palette_grid.columnconfigure(1, weight=1)

        self.settings_background_label, self.background_field, self.background_entry, self.background_pick = self._build_settings_color_control(
            self.palette_grid, 0, 0, "Background", self.bg_var, with_picker=True
        )
        self.settings_text_label, self.text_field, self.text_entry, _ = self._build_settings_color_control(
            self.palette_grid, 0, 1, "Text", self.text_var
        )
        self.settings_panel_label, self.panel_field, self.panel_entry, self.panel_pick = self._build_settings_color_control(
            self.palette_grid, 1, 0, "Panel", self.panel_var, with_picker=True
        )
        self.settings_button_label, self.button_field, self.button_entry, _ = self._build_settings_color_control(
            self.palette_grid, 1, 1, "Button", self.button_color_var
        )
        self.settings_input_label, self.input_field, self.input_entry, self.input_pick = self._build_settings_color_control(
            self.palette_grid, 2, 0, "Input", self.input_var, with_picker=True
        )
        self.settings_border_label, self.border_field, self.border_entry, _ = self._build_settings_color_control(
            self.palette_grid, 2, 1, "Border", self.border_var
        )

        self.appearance_actions = tk.Frame(self.appearance_body, bd=0, highlightthickness=0)
        self.appearance_actions.grid(row=5, column=0, sticky="w", pady=(16, 0))
        self.apply_theme_button = self._create_animated_button(self.appearance_actions, "Apply Theme", self.apply_theme)
        self.apply_theme_button.pack(side="left", padx=(0, 8))
        self.reset_theme_button = self._create_animated_button(self.appearance_actions, "Reset", self.reset_theme)
        self.reset_theme_button.pack(side="left", padx=(0, 8))

        self.preview_section_label = self._build_settings_section_label(self.appearance_body, "Preview")
        self.preview_section_label.grid(row=6, column=0, sticky="w", pady=(18, 0))
        self.preview_nav = tk.Frame(self.appearance_body, bd=0, highlightthickness=0)
        self.preview_nav.grid(row=7, column=0, sticky="w", pady=(8, 0))
        self.preview_main_button = self._create_animated_button(self.preview_nav, "Main View", lambda: self._set_preview_view("main"))
        self.preview_main_button.pack(side="left", padx=(0, 8))
        self.preview_hotkey_button = self._create_animated_button(self.preview_nav, "Hotkey View", lambda: self._set_preview_view("hotkey"))
        self.preview_hotkey_button.pack(side="left")

        self.preview = tk.Canvas(self.appearance_body, height=130, highlightthickness=0, bd=0)
        self.preview.grid(row=8, column=0, sticky="nsew", pady=(10, 0))
        self.appearance_body.rowconfigure(8, weight=1)

        right = tk.Frame(content, bd=0, highlightthickness=0)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.rowconfigure(0, weight=0)
        right.rowconfigure(1, weight=1)
        right.rowconfigure(2, weight=0)
        self.settings_right = right

        scale_card = self._build_card(right, "Interface Scale")
        scale_card.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        self.scale_card = scale_card
        scale_body = tk.Frame(scale_card, bd=0, highlightthickness=0)
        scale_body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.scale_body = scale_body
        self.scale_intro = self._build_settings_note(
            scale_body,
            "Adjust the overall density of the app without affecting your click settings.",
            wraplength=260,
        )
        self.scale_intro.pack(fill="x", pady=(0, 8))
        self.scale_text_check = tk.Checkbutton(scale_body, text="Auto-scale text with window size", variable=self.auto_scale_text_var, command=self._save_ui_settings)
        self.scale_text_check.pack(anchor="w", pady=4)
        self.scale_controls_check = tk.Checkbutton(scale_body, text="Auto-scale buttons and inputs", variable=self.auto_scale_controls_var, command=self._save_ui_settings)
        self.scale_controls_check.pack(anchor="w", pady=4)
        scale_row = tk.Frame(scale_body, bd=0, highlightthickness=0)
        scale_row.pack(fill="x", pady=(6, 4))
        self.scale_row = scale_row
        self.scale_label = tk.Label(scale_row, text="Base UI scale", anchor="w")
        self.scale_label.pack(side="left")
        self.scale_value_label = tk.Label(scale_row, text=f"{self.base_scale_var.get():.2f}x", anchor="e")
        self.scale_value_label.pack(side="right")

        self.scale_slider = tk.Scale(
            scale_body,
            from_=0.8,
            to=1.6,
            resolution=0.05,
            orient="horizontal",
            variable=self.base_scale_var,
            showvalue=False,
            command=self._on_scale_slider,
        )
        self.scale_slider.pack(fill="x", pady=(0, 10))
        self.settings_hint = tk.Label(scale_body, text="Use this to keep the UI comfortably sized on larger windows.", justify="left", anchor="w")
        self.settings_hint.pack(fill="x")
        component_row = tk.Frame(scale_body, bd=0, highlightthickness=0)
        component_row.pack(fill="x", pady=(12, 4))
        self.component_row = component_row
        self.component_scale_label = tk.Label(component_row, text="Component size", anchor="w")
        self.component_scale_label.pack(side="left")
        self.component_scale_value_label = tk.Label(component_row, text=f"{self.component_scale_var.get():.2f}x", anchor="e")
        self.component_scale_value_label.pack(side="right")
        self.component_scale_slider = tk.Scale(
            scale_body,
            from_=0.8,
            to=1.5,
            resolution=0.05,
            orient="horizontal",
            variable=self.component_scale_var,
            showvalue=False,
            command=self._on_component_scale_slider,
        )
        self.component_scale_slider.pack(fill="x")

        sync_card = self._build_card(right, "Sync")
        sync_card.grid(row=1, column=0, sticky="nsew", pady=(6, 6))
        self.sync_card = sync_card
        sync_body = tk.Frame(sync_card, bd=0, highlightthickness=0)
        sync_body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.sync_body = sync_body
        self.sync_intro = self._build_settings_note(
            sync_body,
            "These options help stabilize click timing on Windows. Leave them off unless you need tighter timing.",
            wraplength=260,
        )
        self.sync_intro.pack(fill="x", pady=(0, 8))
        self.high_precision_check = tk.Checkbutton(
            sync_body,
            text="High-precision timing (Windows)",
            variable=self.high_precision_timing_var,
            command=self._save_ui_settings,
        )
        self.high_precision_check.pack(anchor="w", pady=4)
        self.high_precision_note = tk.Label(
            sync_body,
            text="Improves click timing by requesting a 1ms system timer while clicking. May use a bit more power while active.",
            justify="left",
            anchor="w",
            wraplength=260,
        )
        self.high_precision_note.pack(fill="x", pady=(2, 6))
        self.process_priority_check = tk.Checkbutton(
            sync_body,
            text="Process priority boost (Windows)",
            variable=self.process_priority_boost_var,
            command=self._save_ui_settings,
        )
        self.process_priority_check.pack(anchor="w", pady=4)
        self.process_priority_note = tk.Label(
            sync_body,
            text="Temporarily raises the app process priority while clicking. This can improve sync under load, but may reduce responsiveness for other apps.",
            justify="left",
            anchor="w",
            wraplength=260,
        )
        self.process_priority_note.pack(fill="x", pady=(2, 6))
        self.precision_mode_check = tk.Checkbutton(
            sync_body,
            text="Precision Mode",
            variable=self.precision_mode_var,
            command=self._save_ui_settings,
        )
        self.precision_mode_check.pack(anchor="w", pady=4)
        self.precision_mode_note = tk.Label(
            sync_body,
            text="Uses a tighter final wait before each click for better sync. This can use more CPU while active.",
            justify="left",
            anchor="w",
            wraplength=260,
        )
        self.precision_mode_note.pack(fill="x", pady=(2, 6))
        self.sync_offset_block = tk.Frame(sync_body, bd=0, highlightthickness=0)
        self.sync_offset_block.pack(fill="x", pady=(8, 0))
        self.sync_offset_label = tk.Label(self.sync_offset_block, text="Random Offset", anchor="w")
        self.sync_offset_label.grid(row=0, column=0, sticky="w", padx=(0, 12), pady=6)
        self.sync_offset_row = tk.Frame(self.sync_offset_block, bd=0, highlightthickness=0)
        self.sync_offset_row.grid(row=0, column=1, sticky="w", pady=6)
        self.random_interval_offset_min_input = self._build_input(self.sync_offset_row, self.random_interval_offset_min_var, width=5)
        self.random_interval_offset_min_input.pack(side="left")
        self.random_interval_offset_to_label = tk.Label(self.sync_offset_row, text="to")
        self.random_interval_offset_to_label.pack(side="left", padx=(6, 6))
        self.random_interval_offset_max_input = self._build_input(self.sync_offset_row, self.random_interval_offset_max_var, width=5)
        self.random_interval_offset_max_input.pack(side="left")
        self.random_interval_offset_label = tk.Label(self.sync_offset_row, text="ms")
        self.random_interval_offset_label.pack(side="left", padx=(4, 0))
        self.sync_offset_note = tk.Label(
            self.sync_offset_block,
            text="Adds extra milliseconds between clicks using a random value from this range.",
            justify="left",
            anchor="w",
            wraplength=260,
        )
        self.sync_offset_note.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        self.sync_offset_block.columnconfigure(1, weight=1)
        for entry in (self.random_interval_offset_min_input, self.random_interval_offset_max_input):
            entry.bind("<Return>", lambda _e: self._save_ui_settings())
            entry.bind("<FocusOut>", lambda _e: self._save_ui_settings())

        preset_card = self._build_card(right, "Presets")
        preset_card.grid(row=2, column=0, sticky="nsew", pady=(6, 0))
        self.preset_card = preset_card
        preset_body = tk.Frame(preset_card, bd=0, highlightthickness=0)
        preset_body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.preset_body = preset_body
        self.preset_intro = self._build_settings_note(
            preset_body,
            "Save a full appearance or settings snapshot so you can swap setups quickly.",
            wraplength=260,
        )
        self.preset_intro.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.preset_name_label = self._grid_label(preset_body, "Preset Name", 1, 0)
        self.preset_name_entry = self._build_input(preset_body, self.preset_name_var)
        self.preset_name_entry.grid(row=1, column=1, sticky="ew", pady=6, padx=(0, 8))
        self.preset_mode_label = self._grid_label(preset_body, "Mode", 2, 0)
        self.preset_mode_combo = ttk.Combobox(
            preset_body,
            textvariable=self.preset_mode_var,
            values=["design", "settings"],
            state="readonly",
        )
        self.preset_mode_combo.grid(row=2, column=1, sticky="ew", pady=6, padx=(0, 8))
        self.preset_mode_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_preset_picker())
        self.save_preset_button = self._create_animated_button(preset_body, "Save Preset", self.save_selected_preset)
        self.save_preset_button.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.preset_select_label = self._grid_label(preset_body, "Saved Presets", 4, 0)
        self.preset_select_combo = ttk.Combobox(
            preset_body,
            textvariable=self.preset_selected_var,
            values=[],
            state="readonly",
        )
        self.preset_select_combo.grid(row=4, column=1, sticky="ew", pady=6, padx=(0, 8))
        self.preset_actions = tk.Frame(preset_body, bd=0, highlightthickness=0)
        self.preset_actions.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.load_preset_button = self._create_animated_button(self.preset_actions, "Load", self.load_selected_preset)
        self.load_preset_button.pack(side="left", padx=(0, 8))
        self.delete_preset_button = self._create_animated_button(self.preset_actions, "Delete", self.delete_selected_preset)
        self.delete_preset_button.pack(side="left")
        preset_body.columnconfigure(1, weight=1)
        for entry in (
            self.accent_entry,
            self.background_entry,
            self.panel_entry,
            self.input_entry,
            self.text_entry,
            self.button_entry,
            self.border_entry,
        ):
            entry.bind("<Return>", lambda _e: self.apply_theme())
            entry.bind("<FocusOut>", lambda _e: self.apply_theme())
        self._refresh_preset_picker()
        self._apply_theme()
        self._style_settings_window()
        self._apply_settings_layout_scale(force=True)
        self.settings_window.update_idletasks()
        self.root.after(0, self._style_settings_window)
        self.settings_window.after(30, self._style_settings_window)

    def close_settings(self) -> None:
        if self._pending_settings_resize_job is not None:
            self.root.after_cancel(self._pending_settings_resize_job)
        if self._pending_settings_resize_settle_job is not None:
            self.root.after_cancel(self._pending_settings_resize_settle_job)
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.destroy()
            self.settings_window = None
        self._prune_animated_buttons()
        self._pending_settings_resize_job = None
        self._pending_settings_resize_settle_job = None
        self._last_settings_size = (0, 0)

    def _on_settings_configure(self, _event: tk.Event) -> None:
        if not self.settings_window or not self.settings_window.winfo_exists():
            return
        if _event.widget is not self.settings_window:
            return
        size = (self.settings_window.winfo_width(), self.settings_window.winfo_height())
        if size == self._last_settings_size:
            return
        self._last_settings_size = size
        if self._pending_settings_resize_job is not None:
            self.root.after_cancel(self._pending_settings_resize_job)
        self._pending_settings_resize_job = self.root.after(60, self._apply_live_settings_resize_updates)
        if self._pending_settings_resize_settle_job is not None:
            self.root.after_cancel(self._pending_settings_resize_settle_job)
        self._pending_settings_resize_settle_job = self.root.after(220, self._apply_settled_settings_resize_updates)

    def _apply_live_settings_resize_updates(self) -> None:
        self._pending_settings_resize_job = None
        self._apply_settings_layout_scale(live=True)

    def _apply_settled_settings_resize_updates(self) -> None:
        self._pending_settings_resize_settle_job = None
        self._apply_settings_layout_scale(force=True)
        self._draw_preview()

    def _apply_settings_layout_scale(self, force: bool = False, live: bool = False) -> None:
        if not self.settings_window or not self.settings_window.winfo_exists():
            return
        width = max(760, self.settings_window.winfo_width())
        height = max(560, self.settings_window.winfo_height())
        scale = max(0.76, min(1.22, min(width / 940, height / 700)))
        if live:
            scale = round(scale / 0.04) * 0.04
        shell_pad = max(8, round(12 * scale))
        top_gap = max(6, round(10 * scale))
        side_gap = max(6, round(8 * scale))
        body_pad = max(8, round(12 * scale))
        row_gap = max(4, round(6 * scale))
        entry_gap = max(8, round(12 * scale))
        pick_gap = max(6, round(8 * scale))
        section_gap = max(6, round(10 * scale))
        preview_height = max(92, round(116 * scale))

        self.settings_shell.pack_configure(padx=shell_pad, pady=shell_pad)
        self.settings_topbar.pack_configure(pady=(0, top_gap))
        self.settings_card.grid_configure(padx=(0, side_gap))
        self.settings_right.grid_configure(padx=(side_gap, 0))
        self.scale_card.grid_configure(pady=(0, max(4, round(6 * scale))))
        self.sync_card.grid_configure(pady=(max(4, round(6 * scale)), max(4, round(6 * scale))))
        self.preset_card.grid_configure(pady=(max(4, round(6 * scale)), 0))
        self.appearance_body.pack_configure(padx=body_pad, pady=(0, body_pad))
        self.scale_body.pack_configure(padx=body_pad, pady=(0, body_pad))
        self.sync_body.pack_configure(padx=body_pad, pady=(0, body_pad))
        self.preset_body.pack_configure(padx=body_pad, pady=(0, body_pad))
        self.appearance_top.grid_configure(pady=(section_gap, 0))
        self.appearance_intro.grid_configure(pady=(0, 0))
        self.palette_section_label.grid_configure(pady=(max(10, round(14 * scale)), 0))
        self.palette_section_note.grid_configure(pady=(max(2, round(3 * scale)), 0))
        self.palette_grid.grid_configure(pady=(section_gap, 0))
        self.palette_grid.grid_columnconfigure(0, pad=entry_gap)
        self.palette_grid.grid_columnconfigure(1, pad=entry_gap)

        for field in (
            self.background_field,
            self.text_field,
            self.panel_field,
            self.button_field,
            self.input_field,
            self.border_field,
        ):
            field.grid_configure(padx=(0, entry_gap), pady=(0, row_gap))
        for button in (self.background_pick, self.panel_pick, self.input_pick):
            if button is not None:
                button.grid_configure(padx=(pick_gap, 0), pady=(6, 0))

        self.appearance_actions.grid_configure(pady=(section_gap, 0))
        self.preview_section_label.grid_configure(pady=(max(10, round(14 * scale)), 0))
        self.preview_nav.grid_configure(pady=(max(4, round(6 * scale)), 0))
        if not live or force:
            self.preview.configure(height=preview_height)
        self.preview_main_button.pack_configure(padx=(0, pick_gap))
        self.apply_theme_button.pack_configure(padx=(0, pick_gap))
        self.reset_theme_button.pack_configure(padx=(0, pick_gap))

        self.scale_text_check.pack_configure(pady=max(2, round(4 * scale)))
        self.scale_controls_check.pack_configure(pady=max(2, round(4 * scale)))
        self.scale_row.pack_configure(pady=(section_gap, row_gap))
        self.scale_slider.pack_configure(pady=(0, section_gap))
        if not live or force:
            self.settings_hint.configure(wraplength=max(180, self.scale_body.winfo_width() - 8))
        self.component_row.pack_configure(pady=(section_gap, row_gap))

        self.scale_intro.pack_configure(pady=(0, section_gap))
        self.high_precision_check.pack_configure(pady=max(2, round(4 * scale)))
        self.sync_intro.pack_configure(pady=(0, section_gap))
        self.high_precision_note.pack_configure(pady=(max(2, round(2 * scale)), section_gap))
        self.process_priority_check.pack_configure(pady=max(2, round(4 * scale)))
        self.process_priority_note.pack_configure(pady=(max(2, round(2 * scale)), section_gap))
        self.precision_mode_check.pack_configure(pady=max(2, round(4 * scale)))
        self.precision_mode_note.pack_configure(pady=(max(2, round(2 * scale)), section_gap))
        self.sync_offset_block.pack_configure(pady=(section_gap, 0))
        self.sync_offset_label.grid_configure(padx=(0, max(6, round(8 * scale))), pady=row_gap)
        self.sync_offset_row.grid_configure(padx=(0, entry_gap), pady=row_gap)
        self.sync_offset_note.grid_configure(pady=(max(2, round(2 * scale)), 0))
        if not live or force:
            sync_wrap = max(220, self.sync_body.winfo_width() - 8)
            self.sync_intro.configure(wraplength=sync_wrap)
            self.high_precision_note.configure(wraplength=sync_wrap)
            self.process_priority_note.configure(wraplength=sync_wrap)
            self.precision_mode_note.configure(wraplength=sync_wrap)
            self.sync_offset_note.configure(wraplength=sync_wrap)

        self.preset_intro.grid_configure(pady=(0, section_gap))
        self.preset_name_label.grid_configure(padx=(0, max(6, round(8 * scale))), pady=row_gap)
        self.preset_name_entry.grid_configure(padx=(0, entry_gap), pady=row_gap)
        self.preset_mode_label.grid_configure(padx=(0, max(6, round(8 * scale))), pady=row_gap)
        self.preset_mode_combo.grid_configure(padx=(0, entry_gap), pady=row_gap)
        self.preset_select_label.grid_configure(padx=(0, max(6, round(8 * scale))), pady=row_gap)
        self.preset_select_combo.grid_configure(padx=(0, entry_gap), pady=row_gap)
        self.save_preset_button.grid_configure(pady=(max(6, round(8 * scale)), 0))
        self.preset_actions.grid_configure(pady=(max(6, round(8 * scale)), 0))
        self.load_preset_button.pack_configure(padx=(0, pick_gap))
        if not live or force:
            appearance_wrap = max(260, self.appearance_body.winfo_width() - 24)
            self.appearance_intro.configure(wraplength=appearance_wrap)
            self.palette_section_note.configure(wraplength=appearance_wrap)
            self.preset_intro.configure(wraplength=max(220, self.preset_body.winfo_width() - 8))
            self.scale_intro.configure(wraplength=max(220, self.scale_body.winfo_width() - 8))

    def _on_scale_slider(self, value: str) -> None:
        self.scale_value_label.configure(text=f"{float(value):.2f}x")
        self._save_ui_settings()

    def _on_component_scale_slider(self, value: str) -> None:
        self.component_scale_value_label.configure(text=f"{float(value):.2f}x")
        self._save_ui_settings()
        self._draw_preview()

    def _set_preview_view(self, view: str) -> None:
        self.preview_view_var.set(view)
        self._draw_preview()

    def _save_ui_settings(self) -> None:
        try:
            random_interval_offset_min = max(0, int(self.random_interval_offset_min_var.get().strip() or "0"))
        except ValueError:
            random_interval_offset_min = max(0, int(getattr(self.sm.settings, "random_interval_offset_min_ms", 0)))
            self.random_interval_offset_min_var.set(str(random_interval_offset_min))
        try:
            random_interval_offset_max = max(0, int(self.random_interval_offset_max_var.get().strip() or "0"))
        except ValueError:
            random_interval_offset_max = max(0, int(getattr(self.sm.settings, "random_interval_offset_max_ms", 0)))
            self.random_interval_offset_max_var.set(str(random_interval_offset_max))
        self.sm.settings = UISettings(
            auto_scale_text=bool(self.auto_scale_text_var.get()),
            auto_scale_controls=bool(self.auto_scale_controls_var.get()),
            base_scale=float(self.base_scale_var.get()),
            component_scale=float(self.component_scale_var.get()),
            high_precision_timing=bool(self.high_precision_timing_var.get()),
            process_priority_boost=bool(self.process_priority_boost_var.get()),
            precision_mode=bool(self.precision_mode_var.get()),
            random_interval_offset_min_ms=random_interval_offset_min,
            random_interval_offset_max_ms=random_interval_offset_max,
        )
        self.sm.save()
        self.current_scale = 0.0
        self._apply_responsive_scale()

    def _preset_names_for_mode(self) -> list[str]:
        mode = self.preset_mode_var.get().strip().lower()
        if mode == "settings":
            return sorted(self.sm.presets.keys(), key=str.lower)
        return sorted(self.tm.presets.keys(), key=str.lower)

    def _refresh_preset_picker(self) -> None:
        if not hasattr(self, "preset_select_combo"):
            return
        names = self._preset_names_for_mode()
        self.preset_select_combo.configure(values=names)
        current = self.preset_selected_var.get().strip()
        if current not in names:
            self.preset_selected_var.set(names[0] if names else "")

    def load_selected_preset(self) -> None:
        name = self.preset_selected_var.get().strip()
        mode = self.preset_mode_var.get().strip().lower()
        if not name:
            return
        if mode == "settings":
            if name not in self.sm.presets:
                return
            preset = self.sm.presets[name]
            self.auto_scale_text_var.set(preset.auto_scale_text)
            self.auto_scale_controls_var.set(preset.auto_scale_controls)
            self.base_scale_var.set(preset.base_scale)
            self.component_scale_var.set(preset.component_scale)
            self.high_precision_timing_var.set(preset.high_precision_timing)
            self.process_priority_boost_var.set(getattr(preset, "process_priority_boost", False))
            self.precision_mode_var.set(getattr(preset, "precision_mode", False))
            self.random_interval_offset_min_var.set(str(max(0, int(getattr(preset, "random_interval_offset_min_ms", 0)))))
            self.random_interval_offset_max_var.set(str(max(0, int(getattr(preset, "random_interval_offset_max_ms", 0)))))
            self.scale_value_label.configure(text=f"{preset.base_scale:.2f}x")
            self.component_scale_value_label.configure(text=f"{preset.component_scale:.2f}x")
            self._save_ui_settings()
            self._set_status(f"Loaded app settings preset: {name}", "running")
            return
        if name not in self.tm.presets:
            return
        self.tm.theme = Theme(**asdict(self.tm.presets[name]))
        self.mode_var.set(self.tm.theme.mode)
        self.bg_var.set(self.tm.theme.background)
        self.text_var.set(self.tm.theme.text)
        self.button_color_var.set(self.tm.theme.button)
        self.accent_var.set(self.tm.theme.accent)
        self.border_var.set(self.tm.theme.border)
        self.input_var.set(self.tm.theme.input_bg)
        self.panel_var.set(self.tm.theme.panel)
        self.muted_var.set(self.tm.theme.muted)
        self.grad_on_var.set(self.tm.theme.gradient_on)
        self.grad_start_var.set(self.tm.theme.grad_start)
        self.grad_end_var.set(self.tm.theme.grad_end)
        self.grad_third_var.set(self.tm.theme.grad_third)
        self.grad_dir_var.set(self.tm.theme.grad_dir)
        self._apply_theme()
        self._set_status(f"Loaded design preset: {name}", "running")

    def delete_selected_preset(self) -> None:
        name = self.preset_selected_var.get().strip()
        mode = self.preset_mode_var.get().strip().lower()
        if not name:
            return
        if mode == "settings":
            if name not in self.sm.presets:
                return
            del self.sm.presets[name]
            self.sm.save_presets()
            self._refresh_preset_picker()
            self._set_status(f"Deleted app settings preset: {name}", "running")
            return
        builtin_theme_presets = {"Midnight", "Ocean", "Neon", "Soft Gray", "Sunset gradient"}
        if name in builtin_theme_presets:
            messagebox.showinfo("Preset", "Built-in design presets cannot be deleted.")
            return
        if name not in self.tm.presets:
            return
        del self.tm.presets[name]
        self.tm.save()
        self._refresh_preset_picker()
        self._set_status(f"Deleted design preset: {name}", "running")

    def _style_settings_window(self) -> None:
        if not self.settings_window or not self.settings_window.winfo_exists():
            return
        t = self.tm.theme
        self.settings_window.configure(background=t.background)
        self.settings_shell.configure(background=t.background)
        self.settings_topbar.configure(background=t.background)
        self.settings_content.configure(background=t.background)
        self.settings_right.configure(background=t.background)
        self.settings_title.configure(background=t.background, foreground=t.text, font=("Segoe UI Semibold", 14))
        for card in (self.settings_card, self.scale_card, self.sync_card, self.preset_card):
            card.configure(background=t.panel, highlightbackground=t.border, highlightcolor=t.border)
            card._header.configure(background=t.panel)  # type: ignore[attr-defined]
            card._title_label.configure(background=t.panel, foreground=t.text, font=("Segoe UI Semibold", 11))  # type: ignore[attr-defined]

        def paint_tree(root: tk.Widget, background: str) -> None:
            for child in root.winfo_children():
                try:
                    if isinstance(child, tk.Frame):
                        child.configure(background=background)
                    elif isinstance(child, tk.Label):
                        child.configure(background=background)
                    elif isinstance(child, tk.Checkbutton):
                        child.configure(background=background, activebackground=background, selectcolor=t.input_bg)
                    elif isinstance(child, tk.Canvas):
                        child.configure(background=background)
                    elif isinstance(child, tk.Scale):
                        child.configure(background=background, troughcolor=t.input_bg, activebackground=t.accent, highlightthickness=0, fg=t.text)
                except Exception:
                    pass
                paint_tree(child, background)

        paint_tree(self.settings_shell, t.background)
        for card in (self.settings_card, self.scale_card, self.sync_card, self.preset_card):
            card.configure(background=t.panel, highlightbackground=t.border, highlightcolor=t.border)
            card._header.configure(background=t.panel)  # type: ignore[attr-defined]
            card._title_label.configure(background=t.panel, foreground=t.text, font=("Segoe UI Semibold", 11))  # type: ignore[attr-defined]
            paint_tree(card, t.panel)

        self.appearance_body.configure(background=t.panel)
        self.scale_body.configure(background=t.panel)
        self.sync_body.configure(background=t.panel)
        self.preset_body.configure(background=t.panel)
        self.appearance_intro.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        self.appearance_top.configure(background=t.panel)
        self.palette_section_label.configure(background=t.panel, foreground=t.text, font=("Segoe UI Semibold", 10))
        self.palette_section_note.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        self.palette_grid.configure(background=t.panel)
        for field in (
            self.background_field,
            self.text_field,
            self.panel_field,
            self.button_field,
            self.input_field,
            self.border_field,
        ):
            field.configure(background=t.panel)
        self.appearance_actions.configure(background=t.panel)
        self.preview_section_label.configure(background=t.panel, foreground=t.text, font=("Segoe UI Semibold", 10))
        self.preview_nav.configure(background=t.panel)
        self.scale_row.configure(background=t.panel)
        self.component_row.configure(background=t.panel)
        self.scale_intro.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        self.sync_intro.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        self.sync_offset_block.configure(background=t.panel)
        self.preset_actions.configure(background=t.panel)
        self.preset_intro.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        self.scale_text_check.configure(background=t.panel, foreground=t.text, activebackground=t.panel, activeforeground=t.text, selectcolor=t.input_bg, font=("Segoe UI", 9))
        self.scale_controls_check.configure(background=t.panel, foreground=t.text, activebackground=t.panel, activeforeground=t.text, selectcolor=t.input_bg, font=("Segoe UI", 9))
        self.scale_label.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        self.scale_value_label.configure(background=t.panel, foreground=t.text, font=("Segoe UI Semibold", 9))
        self.scale_slider.configure(background=t.panel, troughcolor=t.input_bg, activebackground=t.accent, highlightthickness=0, fg=t.text)
        self.settings_hint.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        self.component_scale_label.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        self.component_scale_value_label.configure(background=t.panel, foreground=t.text, font=("Segoe UI Semibold", 9))
        self.component_scale_slider.configure(background=t.panel, troughcolor=t.input_bg, activebackground=t.accent, highlightthickness=0, fg=t.text)
        self.high_precision_check.configure(background=t.panel, foreground=t.text, activebackground=t.panel, activeforeground=t.text, selectcolor=t.input_bg, font=("Segoe UI", 9))
        self.high_precision_note.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.process_priority_check.configure(background=t.panel, foreground=t.text, activebackground=t.panel, activeforeground=t.text, selectcolor=t.input_bg, font=("Segoe UI", 9))
        self.process_priority_note.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.precision_mode_check.configure(background=t.panel, foreground=t.text, activebackground=t.panel, activeforeground=t.text, selectcolor=t.input_bg, font=("Segoe UI", 9))
        self.precision_mode_note.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.sync_offset_label.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        self.sync_offset_row.configure(background=t.panel)
        self.random_interval_offset_to_label.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.random_interval_offset_label.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.sync_offset_note.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        for frame in (self.scale_body.winfo_children() + self.sync_body.winfo_children() + self.preset_body.winfo_children()):
            if isinstance(frame, tk.Frame):
                frame.configure(background=t.panel)
        for parent in (self.appearance_body, self.scale_body, self.sync_body, self.preset_body):
            for child in parent.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(background=t.panel, foreground=t.text, font=("Segoe UI", 9))
        self.appearance_intro.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        self.palette_section_label.configure(background=t.panel, foreground=t.text, font=("Segoe UI Semibold", 10))
        self.palette_section_note.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        self.preview_section_label.configure(background=t.panel, foreground=t.text, font=("Segoe UI Semibold", 10))
        self.scale_intro.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        self.sync_intro.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        self.preset_intro.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        self.settings_hint.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        self.high_precision_note.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.precision_mode_note.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.sync_offset_label.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        self.random_interval_offset_to_label.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.random_interval_offset_label.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.sync_offset_note.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        for label in (self.component_note,):
            label.configure(background=t.panel, foreground=t.muted)
        settings_entries = [
            self.accent_entry,
            self.background_entry,
            self.panel_entry,
            self.input_entry,
            self.text_entry,
            self.button_entry,
            self.border_entry,
            self.preset_name_entry,
            self.random_interval_offset_min_input,
            self.random_interval_offset_max_input,
        ]
        for entry in settings_entries:
            entry.configure(
                background=t.input_bg,
                disabledbackground=t.input_bg,
                foreground=t.text,
                insertbackground=t.text,
                readonlybackground=t.input_bg,
                selectbackground=t.accent,
                selectforeground="#F4F7F4",
                highlightthickness=1,
                highlightbackground=t.border,
                highlightcolor=t.accent,
                relief="flat",
                bd=0,
                font=("Segoe UI Semibold", 9),
            )
        self.settings_mode_combo.configure(style="TCombobox")
        self.preset_mode_combo.configure(style="TCombobox")
        self.preset_select_combo.configure(style="TCombobox")
        self.preview.configure(background=t.background)
        self._prune_animated_buttons()
        for spec in self.animated_buttons:
            self._style_animated_button(spec)
        self._apply_settings_layout_scale()
        self._draw_preview()

    def _build_tabs(self) -> None:
        clicker = ttk.Frame(self.tabs, style="Root.TFrame")
        hotkeys = ttk.Frame(self.tabs, style="Root.TFrame")
        appearance = ttk.Frame(self.tabs, style="Root.TFrame")
        about = ttk.Frame(self.tabs, style="Root.TFrame")
        self.tabs.add(clicker, text="Clicker")
        self.tabs.add(hotkeys, text="Hotkeys")
        self.tabs.add(appearance, text="Appearance")
        self.tabs.add(about, text="About")

        c = ttk.Frame(clicker, padding=12, style="Card.TFrame")
        c.pack(fill="x", padx=6, pady=6)

        top_bar = ttk.Frame(c, style="Card.TFrame")
        top_bar.grid(row=0, column=0, columnspan=5, sticky="ew", pady=(0, 8))
        ttk.Label(top_bar, text="AutoClicker", style="Section.TLabel").pack(side="right")

        ttk.Label(c, text="Click Speed", style="Body.TLabel").grid(row=1, column=0, sticky="w", pady=4)
        speed_wrap = ttk.Frame(c, style="Card.TFrame")
        speed_wrap.grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Entry(speed_wrap, textvariable=self.interval_var, width=8).pack(side="left")
        ttk.Label(speed_wrap, text="cps", style="Muted.TLabel").pack(side="left", padx=(6, 0))

        ttk.Label(c, text="Button", style="Body.TLabel").grid(row=1, column=2, sticky="e", padx=(16, 6), pady=4)
        btn_wrap = ttk.Frame(c, style="Card.TFrame")
        btn_wrap.grid(row=1, column=3, columnspan=2, sticky="w", pady=4)
        ttk.Radiobutton(btn_wrap, text="L", variable=self.button_var, value="left", style="Seg.TRadiobutton").pack(side="left")
        ttk.Radiobutton(btn_wrap, text="M", variable=self.button_var, value="middle", style="Seg.TRadiobutton").pack(side="left", padx=4)
        ttk.Radiobutton(btn_wrap, text="R", variable=self.button_var, value="right", style="Seg.TRadiobutton").pack(side="left")

        ttk.Label(c, text="Hotkey", style="Body.TLabel").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(c, textvariable=self.start_var).grid(row=2, column=1, sticky="ew", pady=4)

        ttk.Label(c, text="Mode", style="Body.TLabel").grid(row=2, column=2, sticky="e", padx=(16, 6), pady=4)
        mode_wrap = ttk.Frame(c, style="Card.TFrame")
        mode_wrap.grid(row=2, column=3, columnspan=2, sticky="w", pady=4)
        ttk.Radiobutton(mode_wrap, text="Single", variable=self.click_type_var, value="single", style="Seg.TRadiobutton").pack(side="left")
        ttk.Radiobutton(mode_wrap, text="Double", variable=self.click_type_var, value="double", style="Seg.TRadiobutton").pack(side="left", padx=4)

        a = ttk.Frame(c, style="Card.TFrame")
        a.grid(row=3, column=0, columnspan=5, sticky="ew", pady=(10, 0))
        ttk.Button(a, text="Start", style="Primary.TButton", command=self.start).pack(side="left", padx=(0, 8))
        ttk.Button(a, text="Stop", style="Secondary.TButton", command=self.stop).pack(side="left", padx=(0, 8))
        ttk.Button(a, text="Apply", style="Secondary.TButton", command=self.apply_clicker).pack(side="left")
        c.columnconfigure(1, weight=1)

        h = ttk.Frame(hotkeys, padding=12, style="Card.TFrame")
        h.pack(fill="x", padx=6, pady=6)
        ttk.Label(h, text="Global Hotkeys", style="Section.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        self._row(h, "Start", self.start_var, 1); ttk.Button(h, text="Capture", style="Secondary.TButton", command=lambda: self.capture_hotkey("start")).grid(row=1, column=2, sticky="e")
        self._row(h, "Stop", self.stop_var, 2); ttk.Button(h, text="Capture", style="Secondary.TButton", command=lambda: self.capture_hotkey("stop")).grid(row=2, column=2, sticky="e")
        self._row(h, "Toggle", self.toggle_var, 3); ttk.Button(h, text="Capture", style="Secondary.TButton", command=lambda: self.capture_hotkey("toggle")).grid(row=3, column=2, sticky="e")
        ttk.Button(h, text="Apply Hotkeys", style="Primary.TButton", command=self.apply_hotkeys).grid(row=4, column=0, sticky="w", pady=(8, 0))
        h.columnconfigure(1, weight=1)

        appearance.columnconfigure(0, weight=3); appearance.columnconfigure(1, weight=2)
        left = ttk.Frame(appearance, padding=12, style="Card.TFrame")
        right = ttk.Frame(appearance, padding=12, style="Card.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(6, 4), pady=6); right.grid(row=0, column=1, sticky="nsew", padx=(4, 6), pady=6)
        left.columnconfigure(1, weight=1); right.columnconfigure(0, weight=1)
        ttk.Label(left, text="Appearance", style="Section.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        mode_combo = self._combo(left, "Theme Mode", self.mode_var, ["light", "dark", "custom"], 1)
        self._color(left, "Background", self.bg_var, 2); self._color(left, "Text", self.text_var, 3); self._color(left, "Button", self.button_color_var, 4)
        self._color(left, "Accent", self.accent_var, 5); self._color(left, "Border", self.border_var, 6); self._color(left, "Input", self.input_var, 7)
        self._color(left, "Panel", self.panel_var, 8); self._color(left, "Muted Text", self.muted_var, 9)
        ttk.Checkbutton(left, text="Enable gradient", variable=self.grad_on_var, style="Card.TCheckbutton").grid(row=10, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self._color(left, "Gradient Start", self.grad_start_var, 11); self._color(left, "Gradient End", self.grad_end_var, 12); self._color(left, "Gradient Third", self.grad_third_var, 13)
        self._combo(left, "Direction", self.grad_dir_var, ["top-bottom", "left-right", "diagonal", "radial"], 14)
        ttk.Button(left, text="Apply Live", style="Primary.TButton", command=self.apply_theme).grid(row=15, column=0, sticky="w", pady=(8, 0))
        ttk.Button(left, text="Reset", style="Secondary.TButton", command=self.reset_theme).grid(row=15, column=1, sticky="w", pady=(8, 0))
        mode_combo.bind("<<ComboboxSelected>>", lambda _e: self.apply_theme())
        ttk.Label(right, text="Live Preview", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.preview = tk.Canvas(right, height=220, highlightthickness=0, bd=0); self.preview.grid(row=1, column=0, sticky="ew", pady=(6, 8))
        self._row(right, "Preset Name", self.preset_name_var, 2)
        ttk.Button(right, text="Save Preset", style="Secondary.TButton", command=self.save_preset).grid(row=3, column=0, sticky="w")
        self.preset_combo = ttk.Combobox(right, textvariable=self.preset_select_var, values=list(self.tm.presets.keys()), state="readonly"); self.preset_combo.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(right, text="Load Preset", style="Secondary.TButton", command=self.load_preset).grid(row=5, column=0, sticky="w", pady=(6, 0))

        ab = ttk.Frame(about, padding=12, style="Card.TFrame"); ab.pack(fill="x", padx=6, pady=6)
        ttk.Label(ab, text="About", style="Section.TLabel").pack(anchor="w")
        ttk.Label(ab, text="AutoClicker with a modern appearance system and preset support.", style="Body.TLabel").pack(anchor="w", pady=(6, 0))

    def _row(self, parent: ttk.Frame, label: str, var: tk.StringVar, row: int) -> None:
        ttk.Label(parent, text=label, style="Body.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", pady=4)
        parent.columnconfigure(1, weight=1)

    def _combo(self, parent: ttk.Frame, label: str, var: tk.StringVar, values: list[str], row: int) -> ttk.Combobox:
        ttk.Label(parent, text=label, style="Body.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        combo = ttk.Combobox(parent, textvariable=var, values=values, state="readonly")
        combo.grid(row=row, column=1, sticky="ew", pady=4)
        parent.columnconfigure(1, weight=1)
        return combo

    def _color(self, parent: ttk.Frame, label: str, var: tk.StringVar, row: int) -> None:
        self._row(parent, label, var, row)
        ttk.Button(parent, text="Pick", style="Secondary.TButton", command=lambda v=var: self.pick(v)).grid(row=row, column=2, sticky="e", padx=(6, 0))

    def pick(self, var: tk.StringVar) -> None:
        chosen = colorchooser.askcolor(color=var.get())
        if chosen[1]:
            var.set(chosen[1]); self.apply_theme()

    def apply_theme(self) -> None:
        mode = self.mode_var.get().strip().lower()
        if mode == "light":
            t = self.tm.light_theme()
            self._sync_theme_vars(t)
        elif mode == "dark":
            t = self.tm.dark_theme()
            self._sync_theme_vars(t)
        else:
            t = Theme(
                mode="custom",
                background=self.bg_var.get().strip(),
                panel=self.panel_var.get().strip(),
                text=self.text_var.get().strip(),
                muted=self.muted_var.get().strip(),
                button=self.button_color_var.get().strip(),
                accent=self.accent_var.get().strip(),
                border=self.border_var.get().strip(),
                input_bg=self.input_var.get().strip(),
                gradient_on=bool(self.grad_on_var.get()),
                grad_start=self.grad_start_var.get().strip(),
                grad_end=self.grad_end_var.get().strip(),
                grad_third=self.grad_third_var.get().strip(),
                grad_dir=self.grad_dir_var.get().strip(),
            )
        self.tm.theme = t
        self.tm.save(); self._apply_theme()

    def _sync_theme_vars(self, t: Theme) -> None:
        self.mode_var.set(t.mode)
        self.bg_var.set(t.background)
        self.text_var.set(t.text)
        self.button_color_var.set(t.button)
        self.accent_var.set(t.accent)
        self.border_var.set(t.border)
        self.input_var.set(t.input_bg)
        self.panel_var.set(t.panel)
        self.muted_var.set(t.muted)
        self.grad_on_var.set(t.gradient_on)
        self.grad_start_var.set(t.grad_start)
        self.grad_end_var.set(t.grad_end)
        self.grad_third_var.set(t.grad_third)
        self.grad_dir_var.set(t.grad_dir)

    def reset_theme(self) -> None:
        self.tm.theme = Theme(); self._init_vars(); self.apply_theme()

    def save_design_preset(self, name: str) -> None:
        if not name:
            messagebox.showerror("Preset", "Enter a design/color preset name.")
            return
        self.tm.presets[name] = Theme(**asdict(self.tm.theme))
        self.tm.save()
        self._refresh_preset_picker()
        self.preset_selected_var.set(name)
        self._set_status(f"Saved design preset: {name}", "running")

    def save_settings_preset(self, name: str) -> None:
        if not name:
            messagebox.showerror("Preset", "Enter an app settings preset name.")
            return
        self._save_ui_settings()
        self.sm.settings = UISettings(
            auto_scale_text=bool(self.auto_scale_text_var.get()),
            auto_scale_controls=bool(self.auto_scale_controls_var.get()),
            base_scale=float(self.base_scale_var.get() or 1.0),
            component_scale=float(self.component_scale_var.get() or 1.0),
            high_precision_timing=bool(self.high_precision_timing_var.get()),
            process_priority_boost=bool(self.process_priority_boost_var.get()),
            precision_mode=bool(self.precision_mode_var.get()),
            random_interval_offset_min_ms=max(0, int(getattr(self.sm.settings, "random_interval_offset_min_ms", 0))),
            random_interval_offset_max_ms=max(0, int(getattr(self.sm.settings, "random_interval_offset_max_ms", 0))),
        )
        self.sm.presets[name] = UISettings(**asdict(self.sm.settings))
        self.sm.save_presets()
        self._refresh_preset_picker()
        self.preset_selected_var.set(name)
        self._set_status(f"Saved app settings preset: {name}", "running")

    def save_selected_preset(self) -> None:
        name = self.preset_name_var.get().strip()
        mode = self.preset_mode_var.get().strip().lower()
        if mode == "settings":
            self.save_settings_preset(name)
        else:
            self.save_design_preset(name)

    def _apply_theme(self) -> None:
        t = self.tm.theme; st = ttk.Style(); st.theme_use("clam")
        st.configure("Root.TFrame", background=t.background); st.configure("Card.TFrame", background=t.panel, borderwidth=1, relief="solid")
        st.configure("Title.TLabel", background=t.background, foreground=t.text, font=("Segoe UI", 18, "bold"))
        st.configure("Section.TLabel", background=t.panel, foreground=t.text, font=("Segoe UI Semibold", 11))
        st.configure("Body.TLabel", background=t.panel, foreground=t.text, font=("Segoe UI", 10))
        st.configure("Muted.TLabel", background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        st.configure("Status.TLabel", background=t.background, foreground="#22C55E", font=("Segoe UI", 10, "bold"))
        st.configure("Card.TCheckbutton", background=t.panel, foreground=t.text)
        st.configure("Primary.TButton", background=t.accent, foreground="#F8FAFC", borderwidth=0, padding=(10, 8))
        st.configure("Secondary.TButton", background=t.button, foreground=t.text, borderwidth=0, padding=(10, 8))
        st.configure("Seg.TRadiobutton", background=t.button, foreground=t.text, padding=(8, 3))
        st.map("Seg.TRadiobutton", background=[("active", t.button)], foreground=[("active", t.text)])
        st.configure("TEntry", fieldbackground=t.input_bg, foreground=t.text, insertcolor=t.text, bordercolor=t.border)
        st.configure(
            "TCombobox",
            fieldbackground=t.input_bg,
            foreground=t.text,
            background=t.input_bg,
            bordercolor=t.border,
            arrowcolor=t.text,
            selectbackground=t.input_bg,
            selectforeground=t.text,
        )
        st.map(
            "TCombobox",
            fieldbackground=[
                ("readonly", t.input_bg),
                ("focus", t.input_bg),
                ("!disabled", t.input_bg),
            ],
            foreground=[
                ("readonly", t.text),
                ("focus", t.text),
                ("!disabled", t.text),
            ],
            selectbackground=[
                ("readonly", t.input_bg),
                ("focus", t.input_bg),
                ("!disabled", t.input_bg),
            ],
            selectforeground=[
                ("readonly", t.text),
                ("focus", t.text),
                ("!disabled", t.text),
            ],
            arrowcolor=[
                ("readonly", t.text),
                ("focus", t.text),
                ("!disabled", t.text),
            ],
            bordercolor=[
                ("focus", t.accent),
                ("!focus", t.border),
            ],
            lightcolor=[
                ("focus", t.accent),
                ("!focus", t.border),
            ],
            darkcolor=[
                ("focus", t.accent),
                ("!focus", t.border),
            ],
        )
        st.configure("App.TNotebook", background=t.background); st.configure("App.TNotebook.Tab", background=t.button, foreground=t.text, padding=(12, 8))
        st.map("App.TNotebook.Tab", background=[("selected", t.panel)], foreground=[("selected", t.accent)])

        self.container.configure(background=t.background)
        self.panel.configure(background=t.panel, highlightbackground=t.border, highlightcolor=t.border)
        self.accent_bar.configure(background=t.accent)
        self.topbar.configure(background=t.panel)
        self.main_area.configure(background=t.panel)
        self.sidebar.configure(background=t.panel)
        self.sidebar_spacer.configure(background=t.panel)
        self.clicker_card.configure(background=t.panel, highlightbackground=t.border, highlightcolor=t.border)
        self.extra_features_card.configure(background=t.panel, highlightbackground=t.border, highlightcolor=t.border)
        self.info_card.configure(background=t.panel, highlightbackground=t.border, highlightcolor=t.border)
        self.clicker_card._header.configure(background=t.panel)  # type: ignore[attr-defined]
        self.extra_features_card._header.configure(background=t.panel)  # type: ignore[attr-defined]
        self.info_card._header.configure(background=t.panel)  # type: ignore[attr-defined]
        self.clicker_card._title_label.configure(background=t.panel, foreground=t.text)  # type: ignore[attr-defined]
        self.extra_features_card._title_label.configure(background=t.panel, foreground=t.text)  # type: ignore[attr-defined]
        self.info_card._title_label.configure(background=t.panel, foreground=t.text)  # type: ignore[attr-defined]
        self.clicker_body.configure(background=t.panel)
        self.extra_features_body.configure(background=t.panel)
        self.extra_features_form.configure(background=t.panel)
        self.extra_features_action_row.configure(background=t.panel)
        self.extra_features_apply_button_slot.configure(background=t.panel)
        self.jitter_radius_row.configure(background=t.panel)
        self.form.configure(background=t.panel)
        self.hotkey_panel.configure(background=t.panel)
        self.hotkey_panel_actions.configure(background=t.panel)
        self.action_row.configure(background=t.panel)
        self.start_button_slot.configure(background=t.panel)
        self.stop_button_slot.configure(background=t.panel)
        self.apply_button_slot.configure(background=t.panel)
        self.run_tests_button_slot.configure(background=t.panel)
        self.info_body.configure(background=t.panel)
        self.test_row.configure(background=t.panel)
        self.test_output_wrap.configure(background=t.panel)
        self.footer.configure(background=t.panel)
        self.footer_right.configure(background=t.panel)
        self.interval_fields.configure(background=t.panel)
        self.title_label.configure(background=t.panel, foreground=t.text, font=("Segoe UI", 10))
        self.window_icons.configure(background=t.panel, foreground=t.muted, font=("Segoe UI Symbol", 10))
        self.speed_unit.configure(background=t.input_bg, foreground=t.muted, font=("Segoe UI", 8))
        self.interval_ms_label.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.interval_sec_label.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.interval_min_label.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.interval_hour_label.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.toggle_summary.configure(background=t.panel, foreground=t.text, font=("Segoe UI Semibold", 9))
        self.status.configure(background=t.panel, foreground=t.accent, font=("Segoe UI", 8))
        self.helper_text.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.hotkey_hint.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.hotkey_panel_hint.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.info_title.configure(background=t.panel, foreground=t.text, font=("Segoe UI Semibold", 10))
        self.sync_stats_title.configure(background=t.panel, foreground=t.text, font=("Segoe UI Semibold", 10))
        self.sync_stats_summary.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.test_summary.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.component_note.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.extra_features_note.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.jitter_toggle.configure(
            background=t.panel,
            foreground=t.text,
            activebackground=t.panel,
            activeforeground=t.text,
            selectcolor=t.input_bg,
            highlightthickness=0,
            bd=0,
        )
        self.jitter_radius_label.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 8))
        self.test_output.configure(
            background=t.input_bg,
            foreground=t.text,
            insertbackground=t.text,
            highlightthickness=1,
            highlightbackground=t.border,
            highlightcolor=t.accent,
            selectbackground=t.accent,
            selectforeground="#F4F7F4",
        )
        self.test_output_scroll.configure(
            background=t.button,
            troughcolor=t.input_bg,
            activebackground=t.accent,
            highlightthickness=0,
            bd=0,
            relief="flat",
        )

        for child in self.form.grid_slaves():
            if isinstance(child, tk.Label):
                child.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        for child in self.extra_features_form.grid_slaves():
            if isinstance(child, tk.Label):
                child.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))
        for child in self.hotkey_panel.grid_slaves():
            if isinstance(child, tk.Label):
                child.configure(background=t.panel, foreground=t.muted, font=("Segoe UI", 9))

        self.timing_mode_combo.configure(style="TCombobox")
        for entry in (
            self.speed_input,
            self.jitter_radius_input,
            self.toggle_hotkey_input,
            self.interval_ms_input,
            self.interval_sec_input,
            self.interval_min_input,
            self.interval_hour_input,
        ):
            entry.configure(
                background=t.input_bg,
                disabledbackground=t.input_bg,
                foreground=t.text,
                insertbackground=t.text,
                readonlybackground=t.input_bg,
                selectbackground=t.accent,
                selectforeground="#F4F7F4",
                highlightthickness=1,
                highlightbackground=t.border,
                highlightcolor=t.accent,
                relief="flat",
                bd=0,
                font=("Segoe UI Semibold", 9),
            )
        self._sync_timing_mode_ui()

        self._refresh_segments()
        self._prune_animated_buttons()
        for spec in self.animated_buttons:
            self._style_animated_button(spec)
        self._draw_bg()
        self._draw_preview()
        self._style_settings_window()
        self.current_scale = 0.0
        self._apply_responsive_scale()

    def _refresh_segments(self) -> None:
        t = self.tm.theme
        for var, wrap, buttons, _command in self.segment_groups.values():
            wrap.configure(background=t.panel)
            for btn, value in buttons:
                active = var.get() == value
                btn.configure(
                    background=t.accent if active else "#363636",
                    foreground="#F4F7F4" if active else t.text,
                    activebackground=t.accent if active else "#3C3C3C",
                    activeforeground="#F4F7F4" if active else t.text,
                    highlightthickness=1,
                    highlightbackground="#58BC6C" if active else "#4C4C4C",
                    highlightcolor="#58BC6C" if active else "#4C4C4C",
                    disabledforeground=t.text,
                    relief="flat",
                    overrelief="flat",
                )

    def _draw_bg(self) -> None:
        t = self.tm.theme; w = max(1, self.root.winfo_width()); h = max(1, self.root.winfo_height())
        self.bg_canvas.delete("all")
        if not t.gradient_on:
            self.bg_canvas.create_rectangle(0, 0, w, h, fill=t.background, outline=""); return
        if t.grad_dir == "left-right":
            for x in range(w): self.bg_canvas.create_line(x, 0, x, h, fill=self.tm.grad_color(x / max(1, w - 1)))
        elif t.grad_dir == "diagonal":
            steps = w + h
            for i in range(steps): self.bg_canvas.create_line(i, 0, 0, i, fill=self.tm.grad_color(i / max(1, steps - 1)))
        elif t.grad_dir == "radial":
            cx, cy = w // 2, h // 2; rmax = int((w * w + h * h) ** 0.5 / 2)
            for r in range(rmax, 0, -4): self.bg_canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=self.tm.grad_color(1 - r / rmax))
        else:
            for y in range(h): self.bg_canvas.create_line(0, y, w, y, fill=self.tm.grad_color(y / max(1, h - 1)))

    def _draw_preview(self) -> None:
        if not hasattr(self, "preview"):
            return
        t = self.tm.theme
        c = self.preview
        if not isinstance(c, tk.Widget) or not c.winfo_exists():
            return
        c.delete("all")
        w = max(260, c.winfo_width())
        h = max(104, c.winfo_height())
        base_scale = float(self.component_scale_var.get() or 1.0)
        width_fit = w / 420
        height_fit = h / 190
        fit_scale = min(1.0, width_fit, height_fit)
        scale = max(0.62, base_scale * fit_scale)
        pad = max(10, round(15 * scale))
        header_h = max(18, round(24 * scale))
        view = self.preview_view_var.get()
        panel_left = pad
        panel_top = pad
        panel_right = w - pad
        panel_bottom = h - pad
        c.create_rectangle(0, 0, w, h, fill=t.background, outline="")
        c.create_rectangle(panel_left, panel_top, panel_right, panel_bottom, fill=t.panel, outline=t.border, width=2)
        c.create_rectangle(panel_left, panel_top, panel_right, panel_top + header_h, fill=t.button, outline="")
        c.create_text(panel_left + 12, panel_top + header_h / 2, anchor="w", text="AutoClicker", fill=t.text, font=("Segoe UI", max(8, round(8 * scale)), "bold"))
        gear_box_w = max(18, round(22 * scale))
        gear_box_h = max(12, round(14 * scale))
        gear_left = panel_right - gear_box_w - 10
        gear_top = panel_top + max(3, round(4 * scale))
        c.create_rectangle(gear_left, gear_top, gear_left + gear_box_w, gear_top + gear_box_h, fill="#050505", outline=t.border)
        c.create_text(gear_left + gear_box_w / 2, gear_top + gear_box_h / 2, text="⚙", fill=t.text, font=("Segoe UI Symbol", max(7, round(8 * scale))))

        inner_left = panel_left + 12
        inner_top = panel_top + header_h + max(7, round(10 * scale))
        title_size = max(8, round(9 * scale))
        body_size = max(7, round(8 * scale))
        micro_size = max(6, round(7 * scale))
        control_h = max(16, round(18 * scale))
        if view == "hotkey":
            c.create_text(inner_left, inner_top, anchor="nw", text="Hotkey Settings", fill=t.text, font=("Segoe UI", title_size, "bold"))
            key_label_top = inner_top + max(14, round(18 * scale))
            c.create_text(inner_left, key_label_top, anchor="nw", text="Toggle Key", fill=t.muted, font=("Segoe UI", micro_size))
            field_top = key_label_top + max(10, round(14 * scale))
            field_right = panel_right - 16
            c.create_rectangle(inner_left, field_top, field_right, field_top + control_h, fill=t.input_bg, outline=t.border)
            c.create_text(inner_left + 8, field_top + control_h / 2, anchor="w", text=self.toggle_var.get(), fill=t.text, font=("Segoe UI", body_size))
            note_top = field_top + control_h + max(7, round(10 * scale))
            c.create_text(inner_left, note_top, anchor="nw", text="Press a combo and apply it.", fill=t.muted, font=("Segoe UI", micro_size))
            btn_top = note_top + max(14, round(18 * scale))
            btn_h = max(16, round(18 * scale))
            primary_w = max(52, round(64 * scale))
            secondary_w = max(44, round(56 * scale))
            c.create_rectangle(inner_left, btn_top, inner_left + primary_w, btn_top + btn_h, fill=t.accent, outline="")
            c.create_text(inner_left + primary_w / 2, btn_top + btn_h / 2, text="Apply", fill="#F8FAFC", font=("Segoe UI", micro_size))
            back_left = inner_left + primary_w + max(8, round(10 * scale))
            c.create_rectangle(back_left, btn_top, back_left + secondary_w, btn_top + btn_h, fill=t.button, outline="")
            c.create_text(back_left + secondary_w / 2, btn_top + btn_h / 2, text="Back", fill=t.text, font=("Segoe UI", micro_size))
            return
        else:
            c.create_text(inner_left, inner_top, anchor="nw", text="Autoclicker", fill=t.text, font=("Segoe UI", title_size, "bold"))
            timing_mode = self.timing_mode_var.get().strip().lower()
            timing_label = "Click Speed" if timing_mode == "cps" else "Interval"
            timing_value = self.speed_var.get() if timing_mode == "cps" else self.interval_var.get()
            row_top = inner_top + max(15, round(18 * scale))
            c.create_text(inner_left, row_top, anchor="nw", text=timing_label, fill=t.muted, font=("Segoe UI", micro_size))
            input_left = inner_left + max(42, round(56 * scale))
            input_right = input_left + max(34, round(46 * scale))
            c.create_rectangle(input_left, row_top - 1, input_right, row_top - 1 + control_h, fill=t.input_bg, outline=t.border)
            c.create_text(input_left + 6, row_top - 1 + control_h / 2, anchor="w", text=timing_value, fill=t.text, font=("Segoe UI", body_size))
            btn_y = row_top - 1
            for idx, label in enumerate(("L", "M", "R")):
                x0 = input_right + max(10, round(12 * scale)) + idx * max(20, round(24 * scale))
                fill = t.accent if self.button_var.get().startswith(label.lower()) else "#363636"
                btn_w = max(16, round(18 * scale))
                btn_h = control_h
                c.create_rectangle(x0, btn_y, x0 + btn_w, btn_y + btn_h, fill=fill, outline=t.border)
                c.create_text(x0 + btn_w / 2, btn_y + btn_h / 2, text=label, fill="#F8FAFC" if fill == t.accent else t.text, font=("Segoe UI", body_size))
            key_top = row_top + control_h + max(10, round(14 * scale))
            c.create_text(inner_left, key_top, anchor="nw", text=f"Toggle Key  {self.toggle_var.get()}", fill=t.muted, font=("Segoe UI", micro_size))
            action_top = key_top + max(14, round(18 * scale))
            action_h = max(16, round(18 * scale))
            start_w = max(36, round(46 * scale))
            stop_w = max(34, round(42 * scale))
            c.create_rectangle(inner_left, action_top, inner_left + start_w, action_top + action_h, fill=t.accent, outline="")
            c.create_text(inner_left + start_w / 2, action_top + action_h / 2, text="Start", fill="#F8FAFC", font=("Segoe UI", micro_size))
            stop_left = inner_left + start_w + max(8, round(10 * scale))
            c.create_rectangle(stop_left, action_top, stop_left + stop_w, action_top + action_h, fill=t.button, outline="")
            c.create_text(stop_left + stop_w / 2, action_top + action_h / 2, text="Stop", fill=t.text, font=("Segoe UI", micro_size))

    def _next_click_deadline(self, previous_deadline: float, now: float, interval_s: float) -> float:
        next_deadline = previous_deadline + interval_s
        if next_deadline < now - interval_s:
            return now + interval_s
        return next_deadline

    def _precise_sleep_until(self, target_time: float) -> None:
        precision_mode = bool(self.precision_mode_var.get())
        while self.running:
            remaining = target_time - time.perf_counter()
            if remaining <= 0:
                return
            if remaining > (0.0035 if precision_mode else 0.006):
                coarse_buffer = 0.0012 if precision_mode else 0.003
                time.sleep(max(0.0005, remaining - coarse_buffer))
            elif remaining > (0.001 if precision_mode else 0.002):
                time.sleep(0.001)
            else:
                # Spin only for the last tiny slice to reduce jitter.
                pass

    def _enable_high_resolution_timer(self) -> None:
        if self._high_res_timer_active:
            return
        if not bool(self.high_precision_timing_var.get()):
            return
        try:
            result = ctypes.windll.winmm.timeBeginPeriod(self._high_res_timer_period_ms)
            if result == 0:
                self._high_res_timer_active = True
        except Exception:
            self._high_res_timer_active = False

    def _disable_high_resolution_timer(self) -> None:
        if not self._high_res_timer_active:
            return
        try:
            ctypes.windll.winmm.timeEndPeriod(self._high_res_timer_period_ms)
        except Exception:
            pass
        self._high_res_timer_active = False

    def _enable_process_priority_boost(self) -> None:
        if self._priority_boost_active:
            return
        if not bool(self.process_priority_boost_var.get()):
            return
        try:
            process = ctypes.windll.kernel32.GetCurrentProcess()
            self._previous_priority_class = ctypes.windll.kernel32.GetPriorityClass(process) or None
            high_priority_class = 0x00000080
            if ctypes.windll.kernel32.SetPriorityClass(process, high_priority_class):
                self._priority_boost_active = True
        except Exception:
            self._priority_boost_active = False
            self._previous_priority_class = None

    def _disable_process_priority_boost(self) -> None:
        if not self._priority_boost_active:
            return
        try:
            process = ctypes.windll.kernel32.GetCurrentProcess()
            restore_priority = self._previous_priority_class or 0x00000020
            ctypes.windll.kernel32.SetPriorityClass(process, restore_priority)
        except Exception:
            pass
        self._priority_boost_active = False
        self._previous_priority_class = None

    def apply_clicker(self, update_status: bool = True, save: bool = True) -> None:
        timing_mode = self.timing_mode_var.get().strip().lower()
        if timing_mode not in {"cps", "interval"}:
            timing_mode = "cps"
            self.timing_mode_var.set(timing_mode)
        self.cfg.timing_mode = timing_mode
        if timing_mode == "interval":
            self.cfg.interval_ms = self._interval_ms_from_parts()
            self._set_interval_parts_from_ms(self.cfg.interval_ms)
            self.speed_var.set(str(max(1, round(1000 / max(1, self.cfg.interval_ms)))))
        else:
            try:
                cps = max(1, int(self.speed_var.get().strip()))
            except ValueError:
                cps = max(1, round(1000 / max(1, self.cfg.interval_ms)))
                self.speed_var.set(str(cps))
            self.cfg.interval_ms = max(1, round(1000 / cps))
            self._set_interval_parts_from_ms(self.cfg.interval_ms)
        self.interval_var.set(str(self.cfg.interval_ms))
        self.cfg.mouse_button = self.button_var.get().strip().lower()
        self.cfg.jitter_enabled = bool(self.jitter_enabled_var.get())
        try:
            jitter_radius = max(0, int(self.jitter_radius_var.get().strip() or "0"))
        except ValueError:
            jitter_radius = max(0, int(getattr(self.cfg, "jitter_radius_px", 3)))
        self.cfg.jitter_radius_px = jitter_radius
        self.jitter_radius_var.set(str(jitter_radius))
        try:
            random_interval_offset_min = max(0, int(self.random_interval_offset_min_var.get().strip() or "0"))
        except ValueError:
            random_interval_offset_min = max(0, int(getattr(self.cfg, "random_interval_offset_min_ms", 0)))
        try:
            random_interval_offset_max = max(0, int(self.random_interval_offset_max_var.get().strip() or "0"))
        except ValueError:
            random_interval_offset_max = max(0, int(getattr(self.cfg, "random_interval_offset_max_ms", 0)))
        self.cfg.random_interval_offset_min_ms = random_interval_offset_min
        self.cfg.random_interval_offset_max_ms = random_interval_offset_max
        self.random_interval_offset_min_var.set(str(random_interval_offset_min))
        self.random_interval_offset_max_var.set(str(random_interval_offset_max))
        self._sync_timing_mode_ui()
        if self.engine_backend_active and self.running:
            try:
                self.engine_bridge.configure(self._build_native_engine_config())
            except Exception:
                self._set_status("Native engine reconfigure failed", "warning")
        if save:
            self._save_clicker_settings()
        if update_status:
            self._set_status("Settings applied")

    def apply_hotkeys(self, update_status: bool = True, restart: bool = True, save: bool = True) -> None:
        self.cfg.toggle_hotkey = self.toggle_var.get().strip().lower()
        if save:
            self._save_clicker_settings()
        if restart:
            self._restart_hotkeys()
        if update_status:
            self._set_status("Hotkeys applied")
            self._show_clicker_view("main")

    def capture_hotkey(self, target: str) -> None:
        if self.capture: self.capture.stop()
        self.mods = set(); self._set_status(f"Press key for {target}...", "warning")
        modmap = {keyboard.Key.ctrl: "<ctrl>", keyboard.Key.ctrl_l: "<ctrl>", keyboard.Key.ctrl_r: "<ctrl>", keyboard.Key.alt: "<alt>", keyboard.Key.alt_l: "<alt>", keyboard.Key.alt_r: "<alt>", keyboard.Key.shift: "<shift>", keyboard.Key.shift_l: "<shift>", keyboard.Key.shift_r: "<shift>"}

        def on_press(k: keyboard.Key | keyboard.KeyCode) -> bool | None:
            if k in modmap: self.mods.add(modmap[k]); return None
            key = None
            if isinstance(k, keyboard.KeyCode) and k.char: key = "<space>" if k.char == " " else k.char.lower()
            elif k is keyboard.Key.space: key = "<space>"
            elif hasattr(k, "name") and k.name: key = f"<{k.name.lower()}>"
            if not key: return None
            hotkey = "+".join(sorted(self.mods) + [key])
            if target == "start": self.start_var.set(hotkey)
            elif target == "stop": self.stop_var.set(hotkey)
            else: self.toggle_var.set(hotkey)
            self.apply_hotkeys(); return False

        self.capture = keyboard.Listener(on_press=on_press); self.capture.start()

    def _mouse_btn(self) -> mouse.Button:
        return {"left": mouse.Button.left, "middle": mouse.Button.middle, "right": mouse.Button.right}[self.cfg.mouse_button]

    def _jitter_position(self, position: tuple[int, int]) -> tuple[int, int]:
        if not getattr(self.cfg, "jitter_enabled", False):
            return position
        radius = max(0, int(getattr(self.cfg, "jitter_radius_px", 0)))
        if radius <= 0:
            return position
        dx = random.randint(-radius, radius)
        dy = random.randint(-radius, radius)
        return (position[0] + dx, position[1] + dy)

    def _perform_click(self) -> None:
        original_position = self.mouse.position
        jittered_position = self._jitter_position(original_position)
        moved = jittered_position != original_position
        if moved:
            self.mouse.position = jittered_position
        self.mouse.click(self._mouse_btn(), 2 if self.cfg.click_type == "double" else 1)
        if moved:
            self.mouse.position = original_position

    def _loop(self) -> None:
        interval_s = max(self._effective_interval_ms() / 1000.0, 0.001)
        next_deadline = time.perf_counter()
        last_click_time: float | None = None
        current_target_interval_ms = interval_s * 1000.0
        while self.running:
            self._precise_sleep_until(next_deadline)
            if not self.running:
                break
            self._perform_click()
            now = time.perf_counter()
            if last_click_time is not None:
                self._record_sync_sample((now - last_click_time) * 1000.0, current_target_interval_ms)
            last_click_time = now
            interval_s = max(self._effective_interval_ms() / 1000.0, 0.001)
            current_target_interval_ms = interval_s * 1000.0
            next_deadline = self._next_click_deadline(next_deadline, now, interval_s)

    def start(self) -> None:
        if self.running: return
        self.apply_clicker(update_status=False)
        self._reset_sync_stats()
        self.engine_backend_active = False
        if self.engine_bridge.available and self.engine_bridge.start_process():
            try:
                self.engine_bridge.configure(self._build_native_engine_config())
                self.engine_bridge.start_clicking()
                self.running = True
                self.thread = None
                self.engine_backend_active = True
                self._set_status("Running (native engine)", "running")
                return
            except Exception:
                self.engine_bridge.shutdown()
                self.engine_backend_active = False
        self._enable_high_resolution_timer()
        self._enable_process_priority_boost()
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        self._set_status("Running", "running")

    def stop(self) -> None:
        self.running = False
        if self.engine_backend_active:
            self.engine_bridge.stop_clicking()
            self.engine_backend_active = False
        self._disable_high_resolution_timer()
        self._disable_process_priority_boost()
        self._set_status("Stopped", "warning")

    def toggle(self) -> None:
        self.stop() if self.running else self.start()

    def _global_toggle(self) -> None:
        if self.hotkey_editing or self.current_clicker_view == "hotkey":
            return
        self.toggle()

    def _start_hotkeys(self) -> None:
        try:
            self.hk = keyboard.GlobalHotKeys({self.cfg.toggle_hotkey: self._global_toggle})
            self.hk.start()
        except Exception:
            self.hk = None
            self._set_status("Hotkeys unavailable", "warning")

    def _restart_hotkeys(self) -> None:
        if self.hk: self.hk.stop()
        self._start_hotkeys()

    def _on_close(self) -> None:
        self.running = False
        self._disable_high_resolution_timer()
        self._disable_process_priority_boost()
        self.engine_bridge.shutdown()
        self.tm.save(); self.sm.save(); self._save_clicker_settings()
        if self.capture: self.capture.stop()
        if self.hk: self.hk.stop()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
