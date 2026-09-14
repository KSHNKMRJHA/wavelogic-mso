# WaveLogic MSO

**Multi-Channel Protocol Analyzer** — a bench-style oscilloscope and protocol
decoder that runs entirely on CSV files, in your browser.

> Designed by **Piston** · Developed by **Kishan J.**
> Made with love and Open-Source AI — free forever, like it should be.

**▶ Try it live: [wavelogic.streamlit.app](https://wavelogic.streamlit.app/)** —
free community-cloud deployment, no install needed.

WaveLogic MSO turns plain CSV recordings into a fully interactive scope: upload
a capture, view any combination of channels on a shared time axis, zoom and
cursor through it, compare signals, and decode the protocols hidden in the
waveforms — without a vendor tool, a license key, or the cloud.

## Why it exists

A CSV from a logic analyzer once failed with:
> *Decoding requires strictly increasing timestamps.*

So this decoder was built to handle exactly that: duplicate or non-monotonic
timestamps are automatically detected and reconstructed into a uniform time
base, with a clear warning, **instead of the analysis simply failing.**

## Feature highlights

- **Scope view** — simultaneous channels, color-coded overlays, crosshair
  cursors, and a self-contained offline **HTML** export (Plotly embedded, no CDN).
- **Signal math** — differential (A - B) and inverted channels, plus per-window
  readouts: edge frequency, duty cycle, logic levels, transition counts.
- **Protocol decoders** — UART / RS-232, SPI (4-wire), I2C (7-bit), Manchester,
  Differential Manchester (legacy), NRZ, and PWM — each with configuration
  options, status chips, metrics, exportable tables, and a plain-text transcript.
- **Robustness** — Schmitt-style hysteresis logic extraction, automatic
  decimation for large files, full-resolution exports.
- **Local-first** — everything runs on your machine; no account, no cloud.

## Getting started

You can run WaveLogic MSO in three ways — pick whichever suits you.

### Option 1 — Live web app (no install)

[![Streamlit App](https://img.shields.io/badge/Try-it_live-ff4b4b?style=for-the-badge&logo=streamlit&logoColor=white)](https://wavelogic.streamlit.app/)

Open **https://wavelogic.streamlit.app** in your browser — no download, no
account, no Python required.  Hosted on Streamlit Community Cloud.

### Option 2 — From source (Windows, macOS, Linux)

Requires **Python 3.10+**.

```bash
git clone https://github.com/KSHNKMRJHA/wavelogic-mso.git
cd wavelogic-mso

python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

python -m pip install -r requirements.txt
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

> Keep the app pinned to loopback for privacy:
> `streamlit run app.py --server.address 127.0.0.1`

### Option 3 — Windows installer (no Python needed)

A **standalone Windows installer** is published on the
[Releases](https://github.com/KSHNKMRJHA/wavelogic-mso/releases) page.
It bundles everything (Python 3.12, all dependencies, and the app) into a
single `.exe` setup — **no Python installation required**.

1. Download `WaveLogicMSO-Setup_v1.0.0.exe` from the latest Release.
2. Run the installer.  The VC++ runtime is installed automatically.
3. Launch **WaveLogic MSO** from the Start Menu (or desktop shortcut).
4. A native welcome window opens; click **Launch** to start the server.
5. Your default browser opens automatically to `http://localhost:8501`.

If a previous session is already running on port 8501, it is closed
automatically before the new one starts.

## Trying it with a sample

Import `sample_data/uart_example.csv` (a 9600-baud UART frame at 16 samples per
bit, containing duplicate timestamps on purpose). Enable decoding → **UART /
RS-232** → source = `TX` → baud 9600 → see the decoded bytes.

## Documentation

| File | What it covers |
| --- | --- |
| [docs/GUIDE.md](docs/GUIDE.md) | Step-by-step tutorial (view, math, decode, export) |
| [docs/FEATURES.md](docs/FEATURES.md) | Full feature list |
| [docs/CREDITS.md](docs/CREDITS.md) | Credits and license |
| In-app pages | Introduction, User Guide, Features, Credits (sidebar) |

## CSV format

One numeric time column plus one or more numeric channel columns:

```csv
Time(s),CH1,CH2
0.000000,3.3,1.20
0.000001,3.3,1.21
0.000002,0.0,1.22
```

- Delimiters: comma, semicolon, or tab.
- Optional metadata rows above the header are supported.
- Duplicate / non-monotonic timestamps are handled automatically by the decoder.
- Voltage columns are assumed to be in volts.

## Protocol list

| Protocol | Options | Output |
| --- | --- | --- |
| UART / RS-232 | baud, data bits, parity, stop bits, idle level, bit order | frames: byte number, hex, decimal, ASCII, status |
| SPI (4-wire) | CPOL/CPHA, active CS, bits/word, MSB-first, CS-gap merge | frames: MOSI/MISO words per frame |
| I2C (7-bit) | SCL + SDA | transcript: START, address+R/W, ACK/NACK, data, STOP |
| Manchester | bit alignment | bits + hex words |
| Differential Manchester (legacy) | alignment | bits hex groups |
| NRZ | phase, bits/word, MSB-first | bits + hex words |
| PWM | per-pulse | period & duty per pulse |

## Development

```bash
python -m py_compile analyzer_core.py app.py
```

The core analysis lives in `analyzer_core.py` (UI-free, unit-testable); the UI
lives in `app.py`; branding lives in `branding.py`; in-app docs live in
`pages/`.

### Building the Windows installer from source

Requires **Windows 10/11 x64** and [Inno Setup 6](https://jrsoftware.org/isinfo.php).

```powershell
cd installer_build

# 1. Build the small launcher exe (Nuitka, ~2 min)
.\build_launcher.bat

# 2. Bundle a portable Python 3.12 + all packages (~400 MB)
powershell -ExecutionPolicy Bypass -File make_runtime_bundle.ps1

# 3. Create the setup installer
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer.iss
#    -> output\WaveLogicMSO-Setup_v1.0.0.exe
```

The installer bundles the whole app (no Python install needed by the end user)
and is typically published as a GitHub Release asset.

## Credits

- **Designer:** Piston
- **Developer:** Kishan J. — <https://github.com/KSHNKMRJHA>
- **Made with:** love and Open-Source AI
- **Powered by:** Streamlit, NumPy, pandas, Plotly, Python

## License

[MIT](LICENSE) © 2026 Kishan J.