"""Windows 鼠标连点器

使用 Python + Tkinter + ctypes 实现，直接调用 Windows 原生 API：
- SendInput: 模拟鼠标点击
- RegisterHotKey: 全局快捷键
- timeBeginPeriod / timeEndPeriod: 提高定时精度

默认快捷键：
- F8: 捕获当前鼠标坐标
- F9: 开始 / 停止
- F10: 强制停止
"""

from __future__ import annotations

import ctypes
import json
import os
import queue
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError as exc:  # pragma: no cover
    raise SystemExit("当前 Python 环境缺少 Tkinter，无法启动图形界面。") from exc


APP_NAME = "AutoClicker"
APP_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
SETTINGS_FILE = APP_DIR / "settings.json"


def resource_path(name: str) -> str:
    """返回源码运行或 PyInstaller 打包后的资源路径。"""
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, name)


DEFAULT_SETTINGS = {
    "button": "left",
    "click_mode": "single",
    "position_mode": "cursor",
    "fixed_x": 0,
    "fixed_y": 0,
    "interval_mode": "cps",
    "cps": 1,
    "custom_interval_ms": 100,
    "double_click_gap_ms": 30,
    "repeat_mode": "infinite",
    "repeat_count": 100,
    "duration_seconds": 60,
    "start_stop_hotkey": "F9",
    "emergency_stop_hotkey": "F10",
    "capture_hotkey": "F8",
}


def parse_int(text: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    """宽松地把用户输入转换为整数。"""
    try:
        value = int(str(text).strip())
    except (TypeError, ValueError):
        return default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


class SettingsStore:
    """负责配置的读写。"""

    @staticmethod
    def load() -> dict:
        data = dict(DEFAULT_SETTINGS)
        try:
            if SETTINGS_FILE.exists():
                loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data.update(loaded)
        except (OSError, ValueError):
            pass
        return data

    @staticmethod
    def save(settings: dict) -> None:
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(
                json.dumps(settings, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass


class Point(ctypes.Structure):
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


class Msg(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", Point),
    ]


class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KeybdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class InputUnion(ctypes.Union):
    _fields_ = [
        ("mi", MouseInput),
        ("ki", KeybdInput),
        ("hi", HardwareInput),
    ]


class Input(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", InputUnion),
    ]


class Win32:
    """Windows API 的声明与封装。"""

    WM_HOTKEY = 0x0312
    WM_QUIT = 0x0012

    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_WIN = 0x0008
    MOD_NOREPEAT = 0x4000

    INPUT_MOUSE = 0

    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_MIDDLEDOWN = 0x0020
    MOUSEEVENTF_MIDDLEUP = 0x0040

    VK_F8 = 0x77
    VK_F9 = 0x78
    VK_F10 = 0x79

    def __init__(self) -> None:
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        self.winmm = ctypes.windll.winmm

        self.user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
        self.user32.SendInput.restype = wintypes.UINT

        self.user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        self.user32.SetCursorPos.restype = wintypes.BOOL

        self.user32.GetCursorPos.argtypes = [ctypes.POINTER(Point)]
        self.user32.GetCursorPos.restype = wintypes.BOOL

        self.user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        self.user32.RegisterHotKey.restype = wintypes.BOOL

        self.user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.UnregisterHotKey.restype = wintypes.BOOL

        self.user32.GetMessageW.argtypes = [ctypes.POINTER(Msg), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        self.user32.GetMessageW.restype = ctypes.c_int

        self.user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.user32.PostThreadMessageW.restype = wintypes.BOOL

        self.winmm.timeBeginPeriod.argtypes = [wintypes.UINT]
        self.winmm.timeBeginPeriod.restype = wintypes.DWORD

        self.winmm.timeEndPeriod.argtypes = [wintypes.UINT]
        self.winmm.timeEndPeriod.restype = wintypes.DWORD

    def send_mouse_input(self, flags: int, x: int | None = None, y: int | None = None) -> bool:
        if x is not None and y is not None:
            if not self.set_cursor_position(x, y):
                return False

        mouse_input = MouseInput()
        mouse_input.dx = 0
        mouse_input.dy = 0
        mouse_input.mouseData = 0
        mouse_input.dwFlags = flags
        mouse_input.time = 0
        mouse_input.dwExtraInfo = 0

        event = Input()
        event.type = self.INPUT_MOUSE
        event.u.mi = mouse_input

        sent = self.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(Input))
        return sent == 1

    def set_cursor_position(self, x: int, y: int) -> bool:
        return bool(self.user32.SetCursorPos(int(x), int(y)))

    def get_cursor_position(self) -> tuple[int, int]:
        point = Point()
        if self.user32.GetCursorPos(ctypes.byref(point)):
            return int(point.x), int(point.y)
        return 0, 0

    def time_begin(self) -> None:
        self.winmm.timeBeginPeriod(1)

    def time_end(self) -> None:
        self.winmm.timeEndPeriod(1)


class InputSimulator:
    """把低层 Win32 封装成鼠标动作。"""

    def __init__(self, win32: Win32) -> None:
        self._win32 = win32

    @staticmethod
    def _button_flags(button: str) -> tuple[int, int]:
        if button == "right":
            return Win32.MOUSEEVENTF_RIGHTDOWN, Win32.MOUSEEVENTF_RIGHTUP
        if button == "middle":
            return Win32.MOUSEEVENTF_MIDDLEDOWN, Win32.MOUSEEVENTF_MIDDLEUP
        return Win32.MOUSEEVENTF_LEFTDOWN, Win32.MOUSEEVENTF_LEFTUP

    def single_click(self, button: str, x: int | None = None, y: int | None = None) -> None:
        down, up = self._button_flags(button)
        if x is not None and y is not None:
            self._win32.set_cursor_position(x, y)
        self._win32.send_mouse_input(down)
        self._win32.send_mouse_input(up)

    def double_click(
        self,
        button: str,
        x: int | None = None,
        y: int | None = None,
        gap_ms: int = 30,
    ) -> None:
        down, up = self._button_flags(button)
        if x is not None and y is not None:
            self._win32.set_cursor_position(x, y)

        self._win32.send_mouse_input(down)
        self._win32.send_mouse_input(up)
        if gap_ms > 0:
            time.sleep(gap_ms / 1000.0)
        self._win32.send_mouse_input(down)
        self._win32.send_mouse_input(up)

    def get_cursor(self) -> tuple[int, int]:
        return self._win32.get_cursor_position()


class ClickEngine:
    """后台点击任务引擎。"""

    def __init__(self, input_simulator: InputSimulator) -> None:
        self._input = input_simulator
        self._win32 = input_simulator._win32
        self._lock = threading.Lock()
        self._running = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._count = 0
        self._started_at = 0.0

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def snapshot(self) -> dict:
        with self._lock:
            elapsed = 0.0
            if self._running and self._started_at:
                elapsed = time.perf_counter() - self._started_at
            return {
                "running": self._running,
                "count": self._count,
                "elapsed": elapsed,
            }

    def start(self, settings: dict) -> bool:
        with self._lock:
            if self._running:
                return False
            self._running = True
            self._stop_event = threading.Event()
            self._count = 0
            self._started_at = time.perf_counter()
            self._thread = threading.Thread(
                target=self._run,
                args=(dict(settings),),
                name="ClickEngine",
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            thread = self._thread
            self._running = False

        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    @staticmethod
    def _resolve_interval(settings: dict) -> float:
        if settings.get("interval_mode") == "custom":
            ms = parse_int(settings.get("custom_interval_ms", 100), 100, 1, 600000)
            return ms / 1000.0

        cps = parse_int(settings.get("cps", 1), 1)
        cps_map = {100: 0.01, 10: 0.1, 1: 1.0}
        return cps_map.get(cps, 1.0)

    def _run(self, settings: dict) -> None:
        self._win32.time_begin()
        try:
            interval = self._resolve_interval(settings)
            button = settings.get("button", "left")
            click_mode = settings.get("click_mode", "single")
            position_mode = settings.get("position_mode", "cursor")
            fixed_x = parse_int(settings.get("fixed_x", 0), 0, -100000, 100000)
            fixed_y = parse_int(settings.get("fixed_y", 0), 0, -100000, 100000)
            gap_ms = parse_int(settings.get("double_click_gap_ms", 30), 30, 0, 1000)

            repeat_mode = settings.get("repeat_mode", "infinite")
            end_count = parse_int(settings.get("repeat_count", 100), 100, 1, 2_147_483_647)
            duration = parse_int(settings.get("duration_seconds", 60), 60, 1, 86400)
            deadline = time.perf_counter() + duration if repeat_mode == "duration" else None

            next_click_time = time.perf_counter()

            while not self._stop_event.is_set():
                if position_mode == "fixed":
                    x, y = fixed_x, fixed_y
                else:
                    x, y = None, None

                if click_mode == "double":
                    self._input.double_click(button, x, y, gap_ms)
                else:
                    self._input.single_click(button, x, y)

                with self._lock:
                    self._count += 1
                    count = self._count

                if repeat_mode == "count" and count >= end_count:
                    break
                if deadline is not None and time.perf_counter() >= deadline:
                    break

                next_click_time += interval
                delay = next_click_time - time.perf_counter()
                if delay < -interval * 2:
                    next_click_time = time.perf_counter()
                elif delay > 0:
                    self._wait_until(delay)
        finally:
            self._win32.time_end()
            with self._lock:
                self._running = False
                self._thread = None

    @staticmethod
    def _wait_until(seconds: float) -> None:
        if seconds <= 0:
            return
        target = time.perf_counter() + seconds
        while True:
            remaining = target - time.perf_counter()
            if remaining <= 0:
                return
            if remaining > 0.0015:
                time.sleep(remaining - 0.001)
            else:
                while time.perf_counter() < target:
                    pass
                return


class HotkeyListener:
    """独立线程监听全局快捷键。"""

    HOTKEY_START_STOP = 1
    HOTKEY_EMERGENCY_STOP = 2
    HOTKEY_CAPTURE = 3

    HOTKEYS = (
        (HOTKEY_START_STOP, Win32.VK_F9, "F9"),
        (HOTKEY_EMERGENCY_STOP, Win32.VK_F10, "F10"),
        (HOTKEY_CAPTURE, Win32.VK_F8, "F8"),
    )

    def __init__(self, win32: Win32) -> None:
        self._win32 = win32
        self._thread: threading.Thread | None = None
        self._callbacks: dict[int, callable] = {}
        self._error_callback: callable | None = None

    def start(self, callbacks: dict[int, callable], error_callback: callable) -> None:
        self._callbacks = callbacks
        self._error_callback = error_callback
        self._thread = threading.Thread(target=self._run, name="HotkeyListener", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        thread = self._thread
        if thread is None or not thread.is_alive():
            return
        self._win32.user32.PostThreadMessageW(
            wintypes.DWORD(thread.ident),
            Win32.WM_QUIT,
            0,
            0,
        )
        thread.join(timeout=2.0)

    def _run(self) -> None:
        registered: list[int] = []
        try:
            for hotkey_id, vk, name in self.HOTKEYS:
                ok = self._win32.user32.RegisterHotKey(
                    None,
                    hotkey_id,
                    Win32.MOD_NOREPEAT,
                    vk,
                )
                if ok:
                    registered.append(hotkey_id)
                elif self._error_callback is not None:
                    self._error_callback(name)

            msg = Msg()
            while True:
                result = self._win32.user32.GetMessageW(
                    ctypes.byref(msg),
                    None,
                    0,
                    0,
                )
                if result <= 0:
                    break
                if msg.message == Win32.WM_HOTKEY:
                    callback = self._callbacks.get(int(msg.wParam))
                    if callback is not None:
                        callback(int(msg.wParam))
        finally:
            for hotkey_id in registered:
                self._win32.user32.UnregisterHotKey(None, hotkey_id)


class AutoClickerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("鼠标连点器")
        self.root.resizable(True, True)
        self._set_window_icon()

        self._settings_lock = threading.Lock()
        self._current_settings = dict(DEFAULT_SETTINGS)
        self._ui_queue: queue.Queue[tuple] = queue.Queue()
        self._hotkey_error = ""

        self.win32 = Win32()
        self.input_simulator = InputSimulator(self.win32)
        self.engine = ClickEngine(self.input_simulator)
        self.hotkeys = HotkeyListener(self.win32)

        self._create_variables()
        self._build_ui()
        self.root.update_idletasks()
        self.root.minsize(self.root.winfo_reqwidth(), self.root.winfo_reqheight())
        self._load_settings_into_ui()
        self._bind_variable_traces()
        self._sync_settings_from_ui()

        self.hotkeys.start(
            {
                HotkeyListener.HOTKEY_START_STOP: self._on_hotkey_start_stop,
                HotkeyListener.HOTKEY_EMERGENCY_STOP: self._on_hotkey_force_stop,
                HotkeyListener.HOTKEY_CAPTURE: self._on_hotkey_capture,
            },
            self._on_hotkey_error,
        )

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(50, self._poll_ui_queue)
        self.root.after(100, self._refresh_status)

    def _set_window_icon(self) -> None:
        icon_path = resource_path("app.ico")
        try:
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception:
            pass

    # ---------- UI 初始化 ----------

    def _create_variables(self) -> None:
        self.button_var = tk.StringVar(value="left")
        self.click_mode_var = tk.StringVar(value="single")
        self.position_var = tk.StringVar(value="cursor")
        self.x_var = tk.StringVar(value="0")
        self.y_var = tk.StringVar(value="0")
        self.interval_mode_var = tk.StringVar(value="1")
        self.custom_ms_var = tk.StringVar(value="100")
        self.repeat_mode_var = tk.StringVar(value="infinite")
        self.repeat_count_var = tk.StringVar(value="100")
        self.duration_sec_var = tk.StringVar(value="60")
        self.status_var = tk.StringVar(value="待机")

    def _build_ui(self) -> None:
        padding = {"padx": 12, "pady": 4}
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        button_frame = ttk.LabelFrame(main, text="鼠标按键", padding=10)
        button_frame.pack(fill="x", pady=(0, 8))
        ttk.Radiobutton(button_frame, text="左键", variable=self.button_var, value="left").pack(side="left", padx=(0, 18))
        ttk.Radiobutton(button_frame, text="右键", variable=self.button_var, value="right").pack(side="left", padx=(0, 18))
        ttk.Radiobutton(button_frame, text="中键", variable=self.button_var, value="middle").pack(side="left")

        mode_frame = ttk.LabelFrame(main, text="点击方式", padding=10)
        mode_frame.pack(fill="x", pady=(0, 8))
        ttk.Radiobutton(mode_frame, text="单击", variable=self.click_mode_var, value="single").pack(side="left", padx=(0, 18))
        ttk.Radiobutton(mode_frame, text="双击", variable=self.click_mode_var, value="double").pack(side="left")

        position_frame = ttk.LabelFrame(main, text="点击位置", padding=10)
        position_frame.pack(fill="x", pady=(0, 8))
        ttk.Radiobutton(position_frame, text="鼠标光标所在位置", variable=self.position_var, value="cursor").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(position_frame, text="指定坐标", variable=self.position_var, value="fixed").grid(row=1, column=0, sticky="w", pady=(8, 0))

        coord_row = ttk.Frame(position_frame)
        coord_row.grid(row=1, column=1, sticky="w", pady=(8, 0), padx=(12, 0))
        ttk.Label(coord_row, text="X:").pack(side="left")
        ttk.Entry(coord_row, textvariable=self.x_var, width=8).pack(side="left", padx=(4, 10))
        ttk.Label(coord_row, text="Y:").pack(side="left")
        ttk.Entry(coord_row, textvariable=self.y_var, width=8).pack(side="left", padx=(4, 10))
        ttk.Button(coord_row, text="捕获当前坐标 (F8)", command=self._capture_coordinates).pack(side="left")

        speed_frame = ttk.LabelFrame(main, text="每次点击间隔", padding=10)
        speed_frame.pack(fill="x", pady=(0, 8))
        ttk.Radiobutton(speed_frame, text="每秒 100 次", variable=self.interval_mode_var, value="100").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(speed_frame, text="每秒 10 次", variable=self.interval_mode_var, value="10").grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(speed_frame, text="每秒 1 次（默认）", variable=self.interval_mode_var, value="1").grid(row=2, column=0, sticky="w")
        ttk.Radiobutton(speed_frame, text="自定义间隔", variable=self.interval_mode_var, value="custom").grid(row=3, column=0, sticky="w")

        custom_row = ttk.Frame(speed_frame)
        custom_row.grid(row=3, column=1, sticky="w", padx=(12, 0))
        ttk.Entry(custom_row, textvariable=self.custom_ms_var, width=8).pack(side="left")
        ttk.Label(custom_row, text="毫秒").pack(side="left", padx=(5, 0))

        repeat_frame = ttk.LabelFrame(main, text="重复方式", padding=10)
        repeat_frame.pack(fill="x", pady=(0, 8))
        ttk.Radiobutton(repeat_frame, text="一直执行直到停止（默认）", variable=self.repeat_mode_var, value="infinite").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(repeat_frame, text="重复次数", variable=self.repeat_mode_var, value="count").grid(row=1, column=0, sticky="w")
        ttk.Entry(repeat_frame, textvariable=self.repeat_count_var, width=10).grid(row=1, column=1, sticky="w", padx=(12, 0))
        ttk.Label(repeat_frame, text="次").grid(row=1, column=2, sticky="w", padx=(5, 0))
        ttk.Radiobutton(repeat_frame, text="执行时长", variable=self.repeat_mode_var, value="duration").grid(row=2, column=0, sticky="w")
        ttk.Entry(repeat_frame, textvariable=self.duration_sec_var, width=10).grid(row=2, column=1, sticky="w", padx=(12, 0))
        ttk.Label(repeat_frame, text="秒").grid(row=2, column=2, sticky="w", padx=(5, 0))

        action_frame = ttk.Frame(main)
        action_frame.pack(fill="x", pady=(6, 0))
        self.start_button = ttk.Button(action_frame, text="开始点击（快捷键 F9）", command=self._on_start_stop_clicked)
        self.start_button.pack(side="left", fill="x", expand=True)

        status_frame = ttk.Frame(main)
        status_frame.pack(fill="x", pady=(10, 0))
        self.status_indicator = tk.Label(
            status_frame,
            text="●",
            font=("Segoe UI", 13),
            fg="#9e9e9e",
            bg=self.root.cget("bg"),
        )
        self.status_indicator.pack(side="left", padx=(0, 7))
        ttk.Label(status_frame, textvariable=self.status_var, anchor="w").pack(side="left", fill="x", expand=True)

        footer_frame = ttk.Frame(main)
        footer_frame.pack(fill="x", pady=(8, 0))
        ttk.Label(
            footer_frame,
            text="快捷键：F8 捕获坐标 | F9 开始/停止 | F10 强制停止",
            foreground="#666666",
        ).pack(side="left")
        ttk.Label(
            footer_frame,
            text="作者：闲人老马",
            foreground="#888888",
        ).pack(side="right")

    def _bind_variable_traces(self) -> None:
        variables = (
            self.button_var,
            self.click_mode_var,
            self.position_var,
            self.x_var,
            self.y_var,
            self.interval_mode_var,
            self.custom_ms_var,
            self.repeat_mode_var,
            self.repeat_count_var,
            self.duration_sec_var,
        )
        for variable in variables:
            variable.trace_add("write", lambda *_args: self._sync_settings_from_ui())

    # ---------- 配置同步 ----------

    def _sync_settings_from_ui(self) -> None:
        settings = self._read_settings_from_ui()
        with self._settings_lock:
            self._current_settings = settings

    def _read_settings_from_ui(self) -> dict:
        settings = dict(DEFAULT_SETTINGS)
        settings["button"] = self.button_var.get()
        settings["click_mode"] = self.click_mode_var.get()
        settings["position_mode"] = self.position_var.get()
        settings["fixed_x"] = parse_int(self.x_var.get(), 0, -100000, 100000)
        settings["fixed_y"] = parse_int(self.y_var.get(), 0, -100000, 100000)
        interval_choice = self.interval_mode_var.get()
        if interval_choice == "custom":
            settings["interval_mode"] = "custom"
        else:
            settings["interval_mode"] = "cps"
            settings["cps"] = parse_int(interval_choice, 1)
        settings["custom_interval_ms"] = parse_int(self.custom_ms_var.get(), 100, 1, 600000)
        settings["repeat_mode"] = self.repeat_mode_var.get()
        settings["repeat_count"] = parse_int(self.repeat_count_var.get(), 100, 1, 2_147_483_647)
        settings["duration_seconds"] = parse_int(self.duration_sec_var.get(), 60, 1, 86400)
        return settings

    def _get_current_settings(self) -> dict:
        with self._settings_lock:
            return dict(self._current_settings)

    def _load_settings_into_ui(self) -> None:
        settings = SettingsStore.load()
        self.button_var.set(str(settings.get("button", "left")))
        self.click_mode_var.set(str(settings.get("click_mode", "single")))
        self.position_var.set(str(settings.get("position_mode", "cursor")))
        self.x_var.set(str(settings.get("fixed_x", 0)))
        self.y_var.set(str(settings.get("fixed_y", 0)))
        if settings.get("interval_mode", "cps") == "custom":
            self.interval_mode_var.set("custom")
        else:
            self.interval_mode_var.set(str(settings.get("cps", 1)))
        self.custom_ms_var.set(str(settings.get("custom_interval_ms", 100)))
        self.repeat_mode_var.set(str(settings.get("repeat_mode", "infinite")))
        self.repeat_count_var.set(str(settings.get("repeat_count", 100)))
        self.duration_sec_var.set(str(settings.get("duration_seconds", 60)))

    # ---------- 用户操作 ----------

    def _on_start_stop_clicked(self) -> None:
        if self.engine.running:
            self.engine.stop()
        else:
            self._sync_settings_from_ui()
            self.engine.start(self._get_current_settings())
        self._refresh_status()

    def _capture_coordinates(self) -> None:
        x, y = self.input_simulator.get_cursor()
        self.x_var.set(str(x))
        self.y_var.set(str(y))
        self.position_var.set("fixed")
        self._refresh_status()

    def _on_hotkey_start_stop(self, _hotkey_id: int) -> None:
        if self.engine.running:
            self.engine.stop()
        else:
            self.engine.start(self._get_current_settings())
        self._ui_queue.put(("refresh", None))

    def _on_hotkey_force_stop(self, _hotkey_id: int) -> None:
        self.engine.stop()
        self._ui_queue.put(("refresh", None))

    def _on_hotkey_capture(self, _hotkey_id: int) -> None:
        x, y = self.input_simulator.get_cursor()
        self._ui_queue.put(("capture", (x, y)))

    def _on_hotkey_error(self, hotkey_name: str) -> None:
        self._ui_queue.put(("error", hotkey_name))

    # ---------- UI 刷新 ----------

    def _poll_ui_queue(self) -> None:
        try:
            while True:
                item = self._ui_queue.get_nowait()
                kind = item[0]
                if kind == "refresh":
                    self._refresh_status()
                elif kind == "capture":
                    _, (x, y) = item
                    self.x_var.set(str(x))
                    self.y_var.set(str(y))
                    self.position_var.set("fixed")
                    self._refresh_status()
                elif kind == "error":
                    _, hotkey_name = item
                    self._hotkey_error = (
                        f"警告：全局快捷键 {hotkey_name} 注册失败，可能已被其他程序占用"
                    )
                    self._refresh_status()
        except queue.Empty:
            pass
        finally:
            self.root.after(50, self._poll_ui_queue)

    def _refresh_status(self) -> None:
        snapshot = self.engine.snapshot()
        if snapshot["running"]:
            indicator_color = "#2e9e44"
            state_text = "运行中"
            status = f"{state_text} | 已完成 {snapshot['count']} 次 | {snapshot['elapsed']:.1f} 秒"
            button_text = "停止点击（快捷键 F9）"
        elif snapshot["count"]:
            indicator_color = "#e08600"
            state_text = "已停止"
            status = f"{state_text} | 本次完成 {snapshot['count']} 次"
            button_text = "开始点击（快捷键 F9）"
        else:
            indicator_color = "#9e9e9e"
            state_text = "待机（未开始）"
            status = state_text
            button_text = "开始点击（快捷键 F9）"

        if self._hotkey_error:
            status = f"{status} | {self._hotkey_error}"

        self.status_indicator.config(fg=indicator_color)
        self.status_var.set(status)
        self.start_button.config(text=button_text)
        self.root.after(100, self._refresh_status)

    # ---------- 生命周期 ----------

    def _on_close(self) -> None:
        self.engine.stop()
        self.hotkeys.stop()
        self._sync_settings_from_ui()
        SettingsStore.save(self._get_current_settings())
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        print("AutoClicker selftest")
        print(f"Input structure size: {ctypes.sizeof(Input)}")
        print(f"Settings path: {SETTINGS_FILE}")
        return 0

    try:
        app = AutoClickerApp()
    except Exception as exc:  # pragma: no cover
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("鼠标连点器", f"启动失败：{exc}")
            root.destroy()
        except Exception:
            print(f"启动失败：{exc}", file=sys.stderr)
        return 1

    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
