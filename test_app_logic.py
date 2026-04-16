import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import app
import engine_bridge


class DummyVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DummyButton:
    def __init__(self):
        self.config = {}

    def configure(self, **kwargs):
        self.config.update(kwargs)


class DummyFrame:
    def __init__(self):
        self.config = {}

    def configure(self, **kwargs):
        self.config.update(kwargs)


class AppLogicTests(unittest.TestCase):
    def make_app(self):
        instance = app.App.__new__(app.App)
        instance.cfg = app.Clicker()
        instance.tm = SimpleNamespace(theme=app.Theme())
        instance.button_var = DummyVar("left")
        instance.speed_var = DummyVar("10")
        instance.interval_var = DummyVar("100")
        instance.timing_mode_var = DummyVar("cps")
        instance.jitter_enabled_var = DummyVar(False)
        instance.jitter_radius_var = DummyVar("3")
        instance.random_interval_offset_min_var = DummyVar("0")
        instance.random_interval_offset_max_var = DummyVar("0")
        instance.high_precision_timing_var = DummyVar(False)
        instance.process_priority_boost_var = DummyVar(False)
        instance.precision_mode_var = DummyVar(False)
        instance.interval_milliseconds_var = DummyVar("100")
        instance.interval_seconds_var = DummyVar("")
        instance.interval_minutes_var = DummyVar("")
        instance.interval_hours_var = DummyVar("")
        instance.toggle_var = DummyVar("<f8>")
        instance.root = SimpleNamespace(after=lambda *args, **kwargs: None)
        instance.running = False
        instance._high_res_timer_active = False
        instance._high_res_timer_period_ms = 1
        instance.engine_backend_active = False
        instance.hotkey_editing = False
        instance.current_clicker_view = "main"
        instance.engine_bridge = SimpleNamespace(
            available=False,
            start_process=MagicMock(return_value=False),
            configure=MagicMock(),
            start_clicking=MagicMock(),
            stop_clicking=MagicMock(),
            shutdown=MagicMock(),
        )
        instance._save_clicker_settings = MagicMock()
        instance._set_status = MagicMock()
        instance._sync_timing_mode_ui = MagicMock()
        instance._interval_ms_from_parts = app.App._interval_ms_from_parts.__get__(instance, app.App)
        instance._set_interval_parts_from_ms = app.App._set_interval_parts_from_ms.__get__(instance, app.App)
        instance._next_click_deadline = app.App._next_click_deadline.__get__(instance, app.App)
        instance._precise_sleep_until = app.App._precise_sleep_until.__get__(instance, app.App)
        instance._disable_high_resolution_timer = MagicMock()
        instance._enable_high_resolution_timer = MagicMock()
        instance._disable_process_priority_boost = MagicMock()
        instance._enable_process_priority_boost = MagicMock()
        instance.apply_clicker = app.App.apply_clicker.__get__(instance, app.App)
        instance.apply_hotkeys = app.App.apply_hotkeys.__get__(instance, app.App)
        instance._mouse_btn = app.App._mouse_btn.__get__(instance, app.App)
        instance._jitter_position = app.App._jitter_position.__get__(instance, app.App)
        instance._perform_click = app.App._perform_click.__get__(instance, app.App)
        instance._effective_interval_ms = app.App._effective_interval_ms.__get__(instance, app.App)
        instance._build_native_engine_config = app.App._build_native_engine_config.__get__(instance, app.App)
        instance._reset_sync_stats = app.App._reset_sync_stats.__get__(instance, app.App)
        instance._sync_stats_text = app.App._sync_stats_text.__get__(instance, app.App)
        instance._record_sync_sample = app.App._record_sync_sample.__get__(instance, app.App)
        instance._format_hotkey_event = app.App._format_hotkey_event.__get__(instance, app.App)
        instance._global_toggle = app.App._global_toggle.__get__(instance, app.App)
        instance.sync_interval_samples_ms = []
        instance.sync_target_intervals_ms = []
        instance.sync_interval_errors_ms = []
        instance.sync_late_clicks = 0
        instance._last_sync_stats_ui_job = None
        return instance

    def test_apply_clicker_updates_interval_and_saves(self):
        instance = self.make_app()
        instance.apply_clicker(update_status=False)
        self.assertEqual(instance.cfg.interval_ms, 100)
        self.assertEqual(instance.interval_var.get(), "100")
        self.assertEqual(instance.cfg.mouse_button, "left")
        self.assertFalse(instance.cfg.jitter_enabled)
        self.assertEqual(instance.cfg.jitter_radius_px, 3)
        self.assertEqual(instance.cfg.random_interval_offset_min_ms, 0)
        self.assertEqual(instance.cfg.random_interval_offset_max_ms, 0)
        instance._save_clicker_settings.assert_called_once()

    def test_apply_clicker_updates_jitter_settings(self):
        instance = self.make_app()
        instance.jitter_enabled_var.set(True)
        instance.jitter_radius_var.set("7")
        instance.random_interval_offset_min_var.set("4")
        instance.random_interval_offset_max_var.set("18")
        instance.apply_clicker(update_status=False, save=False)
        self.assertTrue(instance.cfg.jitter_enabled)
        self.assertEqual(instance.cfg.jitter_radius_px, 7)
        self.assertEqual(instance.cfg.random_interval_offset_min_ms, 4)
        self.assertEqual(instance.cfg.random_interval_offset_max_ms, 18)

    def test_apply_clicker_recovers_from_invalid_jitter_radius(self):
        instance = self.make_app()
        instance.cfg.jitter_radius_px = 5
        instance.jitter_radius_var.set("abc")
        instance.apply_clicker(update_status=False, save=False)
        self.assertEqual(instance.cfg.jitter_radius_px, 5)
        self.assertEqual(instance.jitter_radius_var.get(), "5")

    def test_apply_clicker_recovers_from_invalid_random_interval_offset_min(self):
        instance = self.make_app()
        instance.cfg.random_interval_offset_min_ms = 9
        instance.random_interval_offset_min_var.set("abc")
        instance.apply_clicker(update_status=False, save=False)
        self.assertEqual(instance.cfg.random_interval_offset_min_ms, 9)
        self.assertEqual(instance.random_interval_offset_min_var.get(), "9")

    def test_apply_clicker_recovers_from_invalid_random_interval_offset_max(self):
        instance = self.make_app()
        instance.cfg.random_interval_offset_max_ms = 13
        instance.random_interval_offset_max_var.set("abc")
        instance.apply_clicker(update_status=False, save=False)
        self.assertEqual(instance.cfg.random_interval_offset_max_ms, 13)
        self.assertEqual(instance.random_interval_offset_max_var.get(), "13")

    def test_apply_clicker_recovers_from_invalid_speed(self):
        instance = self.make_app()
        instance.cfg.interval_ms = 200
        instance.speed_var.set("abc")
        instance.apply_clicker(update_status=False, save=False)
        self.assertEqual(instance.speed_var.get(), "5")
        self.assertEqual(instance.cfg.interval_ms, 200)

    def test_apply_clicker_uses_interval_mode_parts(self):
        instance = self.make_app()
        instance.timing_mode_var.set("interval")
        instance.interval_milliseconds_var.set("250")
        instance.interval_seconds_var.set("1")
        instance.interval_minutes_var.set("")
        instance.interval_hours_var.set("")
        instance.apply_clicker(update_status=False, save=False)
        self.assertEqual(instance.cfg.interval_ms, 1250)
        self.assertEqual(instance.speed_var.get(), "1")

    def test_interval_mode_recovers_from_empty_parts(self):
        instance = self.make_app()
        instance.cfg.interval_ms = 200
        instance.timing_mode_var.set("interval")
        instance.interval_milliseconds_var.set("")
        instance.interval_seconds_var.set("")
        instance.interval_minutes_var.set("")
        instance.interval_hours_var.set("")
        instance.apply_clicker(update_status=False, save=False)
        self.assertEqual(instance.cfg.interval_ms, 200)

    def test_next_click_deadline_keeps_rhythm_when_close(self):
        instance = self.make_app()
        self.assertEqual(instance._next_click_deadline(10.0, 10.05, 0.1), 10.1)

    def test_next_click_deadline_resyncs_when_far_behind(self):
        instance = self.make_app()
        self.assertEqual(instance._next_click_deadline(10.0, 10.25, 0.1), 10.35)

    def test_format_hotkey_event_with_modifiers(self):
        instance = self.make_app()
        event = SimpleNamespace(keysym="Y", state=0x4 | 0x1)
        self.assertEqual(instance._format_hotkey_event(event), "<ctrl>+<shift>+y")

    def test_mouse_button_mapping(self):
        instance = self.make_app()
        instance.cfg.mouse_button = "middle"
        self.assertEqual(instance._mouse_btn(), app.mouse.Button.middle)

    def test_jitter_position_is_unchanged_when_disabled(self):
        instance = self.make_app()
        with patch("app.random.randint") as randint_mock:
            self.assertEqual(instance._jitter_position((100, 200)), (100, 200))
        randint_mock.assert_not_called()

    def test_jitter_position_uses_random_offset_when_enabled(self):
        instance = self.make_app()
        instance.cfg.jitter_enabled = True
        instance.cfg.jitter_radius_px = 4
        with patch("app.random.randint", side_effect=[3, -2]) as randint_mock:
            self.assertEqual(instance._jitter_position((100, 200)), (103, 198))
        self.assertEqual(randint_mock.call_count, 2)

    def test_effective_interval_is_base_when_random_offset_disabled(self):
        instance = self.make_app()
        instance.cfg.interval_ms = 125
        instance.random_interval_offset_min_var.set("0")
        instance.random_interval_offset_max_var.set("0")
        with patch("app.random.randint") as randint_mock:
            self.assertEqual(instance._effective_interval_ms(), 125)
        randint_mock.assert_not_called()

    def test_effective_interval_uses_random_offset_range_when_enabled(self):
        instance = self.make_app()
        instance.cfg.interval_ms = 125
        instance.random_interval_offset_min_var.set("5")
        instance.random_interval_offset_max_var.set("20")
        with patch("app.random.randint", return_value=11) as randint_mock:
            self.assertEqual(instance._effective_interval_ms(), 136)
        randint_mock.assert_called_once_with(5, 20)

    def test_effective_interval_sorts_random_offset_range(self):
        instance = self.make_app()
        instance.cfg.interval_ms = 125
        instance.random_interval_offset_min_var.set("20")
        instance.random_interval_offset_max_var.set("5")
        with patch("app.random.randint", return_value=7) as randint_mock:
            self.assertEqual(instance._effective_interval_ms(), 132)
        randint_mock.assert_called_once_with(5, 20)

    def test_perform_click_restores_cursor_after_jitter(self):
        instance = self.make_app()
        instance.cfg.jitter_enabled = True
        instance.cfg.jitter_radius_px = 3
        instance.mouse = SimpleNamespace(position=(50, 60), click=MagicMock())
        with patch("app.random.randint", side_effect=[2, -1]):
            instance._perform_click()
        self.assertEqual(instance.mouse.position, (50, 60))
        instance.mouse.click.assert_called_once_with(app.mouse.Button.left, 1)

    def test_global_toggle_is_ignored_while_editing(self):
        instance = self.make_app()
        instance.hotkey_editing = True
        instance.toggle = MagicMock()
        instance._global_toggle()
        instance.toggle.assert_not_called()

    def test_global_toggle_runs_when_idle(self):
        instance = self.make_app()
        instance.toggle = MagicMock()
        instance._global_toggle()
        instance.toggle.assert_called_once()

    def test_start_spawns_thread_without_real_clicking(self):
        instance = self.make_app()
        instance.thread = None
        instance.apply_clicker = MagicMock()
        instance._set_status = MagicMock()
        instance._loop = MagicMock()
        with patch("app.threading.Thread") as thread_cls:
            fake_thread = MagicMock()
            thread_cls.return_value = fake_thread
            app.App.start(instance)
        instance.apply_clicker.assert_called_once_with(update_status=False)
        instance._enable_high_resolution_timer.assert_called_once()
        instance._enable_process_priority_boost.assert_called_once()
        self.assertTrue(instance.running)
        thread_cls.assert_called_once()
        fake_thread.start.assert_called_once()
        instance._set_status.assert_called_once_with("Running", "running")

    def test_start_prefers_native_engine_when_available(self):
        instance = self.make_app()
        instance.thread = None
        instance.apply_clicker = MagicMock()
        instance._set_status = MagicMock()
        instance._reset_sync_stats = MagicMock()
        instance.engine_bridge.available = True
        instance.engine_bridge.start_process.return_value = True
        app.App.start(instance)
        instance.engine_bridge.start_process.assert_called_once()
        instance.engine_bridge.configure.assert_called_once()
        instance.engine_bridge.start_clicking.assert_called_once()
        self.assertTrue(instance.running)
        self.assertTrue(instance.engine_backend_active)
        instance._set_status.assert_called_once_with("Running (native engine)", "running")

    def test_stop_disables_high_resolution_timer(self):
        instance = self.make_app()
        app.App.stop(instance)
        instance._disable_high_resolution_timer.assert_called_once()
        instance._disable_process_priority_boost.assert_called_once()
        instance._set_status.assert_called_once_with("Stopped", "warning")

    def test_stop_sends_stop_to_native_engine_when_active(self):
        instance = self.make_app()
        instance.engine_backend_active = True
        app.App.stop(instance)
        instance.engine_bridge.stop_clicking.assert_called_once()
        self.assertFalse(instance.engine_backend_active)

    def test_high_precision_timer_is_skipped_when_setting_off(self):
        instance = self.make_app()
        instance._high_res_timer_active = False
        instance._enable_high_resolution_timer = app.App._enable_high_resolution_timer.__get__(instance, app.App)
        instance._enable_high_resolution_timer()
        self.assertFalse(instance._high_res_timer_active)

    def test_process_priority_boost_is_skipped_when_setting_off(self):
        instance = self.make_app()
        instance._priority_boost_active = False
        instance._previous_priority_class = None
        instance._enable_process_priority_boost = app.App._enable_process_priority_boost.__get__(instance, app.App)
        instance._enable_process_priority_boost()
        self.assertFalse(instance._priority_boost_active)

    def test_sync_stats_text_uses_empty_message_without_samples(self):
        instance = self.make_app()
        self.assertIn("No click timing samples yet", instance._sync_stats_text())

    def test_record_sync_sample_updates_summary_data(self):
        instance = self.make_app()
        instance._record_sync_sample(102.0, 100.0)
        instance._record_sync_sample(110.0, 100.0)
        self.assertEqual(len(instance.sync_interval_samples_ms), 2)
        self.assertEqual(len(instance.sync_target_intervals_ms), 2)
        self.assertEqual(len(instance.sync_interval_errors_ms), 2)
        self.assertEqual(instance.sync_late_clicks, 1)
        summary = instance._sync_stats_text()
        self.assertIn("Samples: 2", summary)
        self.assertIn("Actual CPS", summary)
        self.assertIn("Target CPS", summary)
        self.assertIn("Average interval", summary)
        self.assertIn("Late clicks: 1", summary)

    def test_build_native_engine_config_reflects_current_settings(self):
        instance = self.make_app()
        instance.timing_mode_var.set("interval")
        instance.cfg.interval_ms = 125
        instance.cfg.click_type = "double"
        instance.cfg.jitter_enabled = True
        instance.cfg.jitter_radius_px = 6
        instance.random_interval_offset_min_var.set("3")
        instance.random_interval_offset_max_var.set("9")
        instance.high_precision_timing_var.set(True)
        instance.process_priority_boost_var.set(True)
        instance.precision_mode_var.set(True)
        config = instance._build_native_engine_config()
        self.assertEqual(config.interval_ms, 125)
        self.assertTrue(config.double_click)
        self.assertTrue(config.jitter_enabled)
        self.assertEqual(config.jitter_radius_px, 6)
        self.assertEqual(config.random_interval_offset_min_ms, 3)
        self.assertEqual(config.random_interval_offset_max_ms, 9)
        self.assertTrue(config.high_precision_timing)
        self.assertTrue(config.process_priority_boost)
        self.assertTrue(config.precision_mode)

    def test_build_native_engine_config_keeps_fractional_cps_interval(self):
        instance = self.make_app()
        instance.timing_mode_var.set("cps")
        instance.speed_var.set("120")
        config = instance._build_native_engine_config()
        self.assertAlmostEqual(config.interval_ms, 1000.0 / 120.0, places=3)

    def test_engine_bridge_uses_camel_case_payload(self):
        bridge = engine_bridge.EngineBridge()
        bridge._send = MagicMock()
        bridge.configure(
            engine_bridge.EngineConfig(
                interval_ms=250,
                button="middle",
                double_click=True,
                jitter_enabled=True,
                jitter_radius_px=7,
                random_interval_offset_min_ms=3,
                random_interval_offset_max_ms=9,
                high_precision_timing=True,
                process_priority_boost=True,
                precision_mode=True,
            )
        )
        bridge._send.assert_called_once_with(
            {
                "type": "configure",
                "intervalMs": 250,
                "button": "middle",
                "doubleClick": True,
                "jitterEnabled": True,
                "jitterRadiusPx": 7,
                "randomIntervalOffsetMinMs": 3,
                "randomIntervalOffsetMaxMs": 9,
                "highPrecisionTiming": True,
                "processPriorityBoost": True,
                "precisionMode": True,
            }
        )

    def test_refresh_segments_does_not_override_geometry_font(self):
        instance = self.make_app()
        instance._refresh_segments = app.App._refresh_segments.__get__(instance, app.App)
        wrap = DummyFrame()
        left = DummyButton()
        middle = DummyButton()
        right = DummyButton()
        instance.segment_groups = {
            "mouse_button": (
                DummyVar("middle"),
                wrap,
                [(left, "left"), (middle, "middle"), (right, "right")],
                None,
            )
        }
        instance._refresh_segments()
        self.assertEqual(wrap.config["background"], instance.tm.theme.panel)
        self.assertNotIn("font", left.config)
        self.assertEqual(left.config["relief"], "flat")
        self.assertEqual(middle.config["relief"], "flat")


if __name__ == "__main__":
    unittest.main()
