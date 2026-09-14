"""WaveLogic MSO launcher.

Shows a native welcome window with setup instructions, closes any app
already running on localhost:8501, then starts the bundled Streamlit
server (a normal Python runtime shipped alongside the exe) in the app's
install directory and opens the default browser.

Only this file is compiled by Nuitka into WaveLogicMSO.exe; Streamlit and
the data stack run interpreted from the bundled "python" folder.  This
avoids the hard crashes (0x40000015) seen when compiling Streamlit itself.

Debugging aids:
  * Waves a ruler: logs always live in %%LOCALAPPDATA%%\\WaveLogicMSO\\wavelogic_launch.log
    (and are mirrored into the app folder when that folder is really writable).
  * Run the exe with --debug   (or env WAVELOGIC_DEBUG=1)   for verbose logs
    and Streamlit's own debug logging.
  * Run with --autolaunch       (or env WAVELOGIC_AUTOLAUNCH=1) to skip the
    welcome window and start the server immediately (used for testing/dev).
"""
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

APP_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
APP_VERSION = "1.0.2"
APP_PORT = 8501
CREATE_NO_WINDOW = 0x08000000
BASE = "http://127.0.0.1:%d" % APP_PORT

# The GUI imports are optional.  If Tk/PIL are missing or fail to load in a
# particular install we still start the server and just log the reason.
try:
    import tkinter as tk
except Exception:
    tk = None
try:
    from PIL import Image
    from PIL import ImageTk
except Exception:
    Image = None
    ImageTk = None


def _log_dirs():
    """Return (primary, secondary) log directories.

    Primary is always %%LOCALAPPDATA%%\\WaveLogicMSO (guaranteed writable).
    Secondary is the app folder, but only if a real probe write succeeds:
    os.access() reports True for non-elevated admins against Program Files,
    so we do not trust it and prove writability with an actual create.
    """
    primary = Path(os.environ.get("LOCALAPPDATA", ".")) / "WaveLogicMSO"
    try:
        primary.mkdir(parents=True, exist_ok=True)
    except Exception:
        primary = Path(tempfile.gettempdir()) / "WaveLogicMSO"
        try:
            primary.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    secondary = None
    try:
        probe = APP_DIR / ".probe_write"
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        secondary = APP_DIR
    except Exception:
        secondary = None
    return primary, secondary


_LOG_PRIMARY, _LOG_SECONDARY = _log_dirs()
LOG_FILE = _LOG_PRIMARY / "wavelogic_launch.log"
STREAMLIT_LOG = _LOG_PRIMARY / "wavelogic_streamlit.log"


def _log(msg: str) -> None:
    line = "[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    for target in (_LOG_PRIMARY, _LOG_SECONDARY):
        if target is None:
            continue
        try:
            with open(target / "wavelogic_launch.log", "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass


def _log_tail(path: Path, max_lines: int = 30) -> None:
    """Mirror the tail of a secondary log into the primary launch log."""
    try:
        lines = path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()[-max_lines:]
    except Exception:
        return
    _log(f"--- {path.name} tail ---")
    for line in lines:
        _log("  | " + line)


def _flag(name: str) -> bool:
    if os.environ.get("WAVELOGIC_" + name.upper()):
        return True
    for a in sys.argv[1:]:
        if a.lower().replace("-", "") == name.lower():
            return True
    return False


AUTOLAUNCH = _flag("autolaunch")
DEBUG = _flag("debug")

BG = "#0b1220"
PANEL = "#111a2e"
BORDER = "#233252"
TEXT = "#dbe4f5"
MUTED = "#7f90b0"
ACCENT = "#3b82f6"
AMBER = "#ffd43b"


def _port_listeners(port: int) -> set[int]:
    """Return PIDs currently listening on the given TCP port (localhost)."""
    try:
        out = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True, text=True,
            creationflags=CREATE_NO_WINDOW, timeout=15,
        ).stdout
    except Exception:
        return set()

    pids: set[int] = set()
    pattern = re.compile(r":%d\b\s+\S+\s+(?:LISTENING|LISTEN)\s+(\d+)$" % port)
    for line in out.splitlines():
        m = pattern.search(line.strip())
        if m:
            pids.add(int(m.group(1)))
    return pids


def _kill_pids(pids: set[int]) -> None:
    for pid in pids:
        if pid in (0,):
            continue
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True, text=True,
                creationflags=CREATE_NO_WINDOW, timeout=10,
            )
        except Exception:
            pass


def _port_free(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def free_port(port: int) -> bool:
    """Try to free the given port by closing any session already running there."""
    for _ in range(3):
        if _port_free(port):
            return True
        pids = _port_listeners(port)
        if not pids:
            return _port_free(port)
        _kill_pids(pids)
        time.sleep(0.8)
    return _port_free(port)


def _wait_and_open_browser(url: str = BASE, timeout_s: int = 60) -> None:
    """Wait for the local server, then open the default browser ourselves.

    Streamlit's own browser-launch is unreliable when the server runs as a
    hidden child process, so the launcher opens the URL directly via
    os.startfile once the port actually answers.
    """
    import urllib.request

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.5)
    else:
        _log("browser: server did not answer in %ss, giving up" % timeout_s)
        return

    _log("browser: server up, opening " + url)
    try:
        if os.name == "nt":
            os.startfile(url)
            _log("browser: os.startfile issued")
            return
    except Exception:
        _log("browser: os.startfile failed, falling back to webbrowser\n"
             + traceback.format_exc())
    try:
        import webbrowser
        webbrowser.open(url)
        _log("browser: webbrowser.open issued")
    except Exception:
        _log("browser: webbrowser.open failed\n" + traceback.format_exc())


def _center(root: tk.Tk, w: int, h: int) -> None:
    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = max(0, (sw - w) // 2)
    y = max(0, (sh - h) // 2 - 10)
    root.geometry(f"{w}x{h}+{x}+{y}")


def show_welcome() -> bool:
    """Show the native welcome window; True = proceed to start the app."""
    _log("welcome: enter")
    if tk is None:
        _log("welcome: tkinter unavailable, starting server without GUI")
        return True
    try:
        return _show_welcome_impl()
    except Exception:
        _log("welcome: exception, launching anyway\n" + traceback.format_exc())
        return True
    finally:
        _log("welcome: exit")


def _show_welcome_impl() -> bool:
    root = tk.Tk()
    _log("welcome: tk root created")
    root.title(f"Welcome to WaveLogic MSO {APP_VERSION}")
    root.configure(bg=BG)
    root.resizable(False, False)

    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    win_w = min(1080, int(sw * 0.88))
    win_h = min(840, int(sh * 0.9))

    icon_path = APP_DIR / "wavelogic_logo.ico"
    if icon_path.exists():
        try:
            root.iconbitmap(default=str(icon_path))
        except tk.TclError:
            pass
    _log("welcome: icon ok")

    state = {"launch": False}

    logo_path = APP_DIR / "wavelogic_logo.png"
    photo = None
    if logo_path.exists() and Image is not None and ImageTk is not None:
        try:
            img = Image.open(logo_path)
            img.thumbnail((int(win_w * 0.82), int(win_h * 0.18)))
            photo = ImageTk.PhotoImage(img)
        except Exception:
            photo = None
    _log("welcome: logo loaded")

    header = tk.Frame(root, bg=BG)
    header.pack(fill="x", padx=int(win_w * 0.05), pady=(int(win_h * 0.04), 6))

    if photo is not None:
        tk.Label(header, image=photo, bg=BG).pack()

    title = tk.Label(
        header,
        text="Welcome to WaveLogic MSO",
        bg=BG,
        fg=TEXT,
        font=("Segoe UI", 24, "bold"),
    )
    title.pack(pady=(14, 0))

    sub = tk.Label(
        header,
        text="Multi-Channel Protocol Analyzer   \u00b7   v" + APP_VERSION,
        bg=BG,
        fg=MUTED,
        font=("Segoe UI", 12),
    )
    sub.pack(pady=(4, 0))

    panel = tk.Frame(root, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    panel.pack(fill="both", expand=True, padx=int(win_w * 0.05), pady=(14, 8))

    wrap = int(win_w * 0.75)

    steps = [
        ("1. Capture",
         "Export an oscilloscope session to CSV: one time column plus one or "
         "more numeric channels (volt values)."),
        ("2. Import",
         "After launching, pick a CSV (or the bundled example), choose the "
         "delimiter and skip any metadata rows before the header."),
        ("3. Analyze",
         "Work with channels on a shared time axis, cursors and math "
         "channels; decode UART, SPI, I2C, PWM, Manchester and NRZ with the "
         "built-in protocol decoder pack."),
        ("4. Export",
         "Download decoded payloads, sample arrays and the current waveform "
         "view as CSV or PNG."),
    ]

    for heading, body in steps:
        row = tk.Frame(panel, bg=PANEL)
        row.pack(fill="x", padx=int(win_w * 0.04), pady=(int(win_h * 0.022), 0))
        tk.Label(
            row, text=heading, bg=PANEL, fg=AMBER,
            font=("Segoe UI", 13, "bold"), anchor="w", justify="left",
        ).pack(fill="x")
        tk.Label(
            row, text=body, bg=PANEL, fg=TEXT,
            font=("Segoe UI", 11), anchor="w", justify="left", wraplength=wrap,
        ).pack(fill="x", pady=(2, 0))

    tk.Label(
        panel,
        text=(f"On start the app opens at http://127.0.0.1:{APP_PORT} \u2014 any "
              f"existing session already running there is closed automatically."),
        bg=PANEL, fg=ACCENT, font=("Segoe UI", 10), anchor="w", justify="left",
        wraplength=wrap,
    ).pack(fill="x", padx=int(win_w * 0.04), pady=(int(win_h * 0.02), 0))

    tk.Label(
        panel,
        text=f"Install location:  {APP_DIR}",
        bg=PANEL, fg=MUTED, font=("Segoe UI", 9), anchor="w",
    ).pack(fill="x", padx=int(win_w * 0.04), pady=(int(win_h * 0.018), int(win_h * 0.012)))

    buttons = tk.Frame(root, bg=BG)
    buttons.pack(fill="x", padx=int(win_w * 0.05), pady=(4, int(win_h * 0.03)))

    def on_launch() -> None:
        state["launch"] = True
        root.destroy()

    def on_exit() -> None:
        state["launch"] = False
        root.destroy()

    tk.Button(
        buttons, text="Launch WaveLogic MSO", command=on_launch,
        bg=ACCENT, fg="#ffffff", activebackground="#2563eb", activeforeground="#ffffff",
        relief="flat", borderwidth=0, padx=26, pady=12,
        font=("Segoe UI", 13, "bold"), cursor="hand2",
    ).pack(side="left")
    tk.Button(
        buttons, text="Exit", command=on_exit,
        bg=BG, fg=MUTED, activebackground=PANEL, activeforeground=TEXT,
        relief="flat", borderwidth=0, padx=20, pady=12,
        font=("Segoe UI", 11),
    ).pack(side="left", padx=(14, 0))

    root.bind("<Return>", lambda _e: on_launch())
    root.bind("<Escape>", lambda _e: on_exit())
    root.protocol("WM_DELETE_WINDOW", on_exit)

    _center(root, win_w, win_h)
    _log(f"welcome: geometry {win_w}x{win_h}, about to enter mainloop")
    root.mainloop()
    _log(f"welcome: mainloop exited, launch={state['launch']}")
    return state["launch"]


def main() -> int:
    _log(f"main: WaveLogic MSO v{APP_VERSION} launcher started")
    _log(f"main: exe dir    : {APP_DIR}")
    _log(f"main: log file   : {LOG_FILE}")
    _log(f"main: flags      : autolaunch={AUTOLAUNCH} debug={DEBUG}")
    _log(f"main: python     : {sys.version.split()[0]}")
    os.chdir(APP_DIR)
    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))

    try:
        if not AUTOLAUNCH and not show_welcome():
            _log("main: user chose Exit")
            return 0

        free_port(APP_PORT)
        _log(f"main: port {APP_PORT} cleared")

        python_exe = APP_DIR / "python" / "python.exe"
        if not python_exe.exists():
            _log("main: bundled python.exe MISSING at " + str(python_exe))
            return 1

        app_path = str(APP_DIR / "app.py")
        cmd = [
            str(python_exe),
            "-m", "streamlit", "run", app_path,
            "--server.address=127.0.0.1",
            "--server.headless=true",
            "--server.showEmailPrompt=false",
            "--browser.gatherUsageStats=false",
            "--global.developmentMode=false",
        ]
        if DEBUG:
            cmd += ["--logger.level=debug"]
        _log("main: cmd=" + " ".join(cmd))

        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        with open(STREAMLIT_LOG, "a", encoding="utf-8") as sl:
            _log("main: starting streamlit via bundled python")
            proc = subprocess.Popen(
                cmd,
                cwd=str(APP_DIR),
                env=env,
                stdout=sl,
                stderr=sl,
                creationflags=CREATE_NO_WINDOW,
            )
            _log(f"main: streamlit pid={proc.pid}")
            threading.Thread(
                target=_wait_and_open_browser, daemon=True
            ).start()

            # If the server dies almost immediately, dump its tail into the
            # launch log so the failure is visible even if nobody watches it.
            time.sleep(20)
            if proc.poll() is not None:
                _log(f"main: streamlit exited early with code {proc.returncode}")
                _log_tail(STREAMLIT_LOG)
            rc = proc.wait()
        _log(f"main: streamlit exited with code {rc}")
        if rc != 0:
            _log_tail(STREAMLIT_LOG)
        return rc
    except Exception:
        _log("main: unhandled exception\n" + traceback.format_exc())
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass