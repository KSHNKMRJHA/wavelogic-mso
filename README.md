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

1. Download `WaveLogicMSO-Setup_v1.0.2.exe` from the latest Release.
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
| [RELEASE_NOTES.md](RELEASE_NOTES.md) | Multi-message Differential Manchester release notes |
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

## Differential Manchester: multi-message analysis

The legacy Differential Manchester decoder analyzes one frame per selected
window. An optional, conservative multi-message scanner can locate and present
several independently validated bursts in the same capture.

Enable **Detect multiple messages (multi-burst scan)** when analyzing captures
that may contain multiple Differential Manchester bursts. Multi-message mode is
opt-in so the established single-message presentation stays the default.

Multi-message mode provides:

- a validated-message count and a compact per-message summary table
- **Message N** selection with a per-message detail view
- logical frame start/end offsets (distinct from the decoder window and pre-roll)
- per-message waveform detail cropped to the logical frame boundaries
- CSV exports: `dm_messages_summary.csv` and `dm_messages_bits.csv`

With multi-message mode disabled, the existing single-message decoder, threshold
controls, plotting, and exports behave exactly as before.

### Acceptance model (conservative by design)

A decoder timing fit alone is not sufficient evidence. A candidate is presented
as a validated message only when several independent signals agree:

- paired channel activity (the two selected channels are correlated)
- transition-aligned candidate search with decoder pre-roll context
- cheap local timing plausibility screening
- the existing Differential Manchester decoder's own checks (preamble, sync,
  clock fit)
- independent raw-transition structural validation against the decoded
  boundaries (boundary-transition coverage computed from the original samples)
- duplicate clustering so one physical frame is not reported twice
- continued scanning after rejected candidates (recovery)

These are engineering safety heuristics, not formal protocol specifications.

### Timing caveat

`~12.8 µs` is an empirical timing prior used only to bound a cheap plausibility
prefilter for the current capture family. It is **not** a universal Differential
Manchester protocol constant, and a fitted timing value by itself does not
accept a message. Candidates are judged by independent transition structure, not
by their fitted timing value alone.

### Long captures

For long or noisy captures the scanner reports only independently validated
frames. If none are found, the UI reports that no independently validated
message was found under the current conservative criteria — it does not assert
that no frame exists.

### Decoder-call budget

Scanning runs under a bounded decoder-call budget so pathological captures
cannot trigger unbounded work. Reaching the budget means the scan may be
incomplete: messages already validated remain valid, and the UI warns that
additional messages may exist. A budget-limited scan must not be read as an
exhaustive negative result.

### Offsets

Each validated message exposes its logical frame start/end separately from the
decoder window (which includes pre-roll context). Logical boundaries describe
the decoded message; the decoder window describes the input supplied to the
decoder. Window-relative and capture-relative times are both reported so the
time origin is never ambiguous.

### Architecture

```text
CSV
  -> preprocessing / time handling
  -> protocol-specific candidate detection
  -> existing decoder (authoritative bitstream decoder)
  -> independent validation
  -> clustering
  -> aggregation
  -> UI / export
```

The existing decoder remains the authoritative bitstream decoder; the
orchestration layer only decides whether a candidate has sufficient independent
waveform evidence to be presented as a validated message.

## Development

```bash
python -m py_compile analyzer_core.py app.py
python -m unittest discover -s tests
```

The core analysis lives in `analyzer_core.py` (UI-free, unit-testable); the UI
lives in `app.py`; branding lives in `branding.py`; in-app docs live in
`pages/`; decoder tests live in `tests/`.

### Version/build label

The header shows `v<N> · build <short-sha>`, where `<N>` is the commit count of
the running commit (equal to the GitHub `main` history on a published branch)
and `<short-sha>` is the first 7 characters of that commit. It is resolved
dynamically, in this order:

1. Git metadata when running from a checkout.
2. `WAVELOGIC_COMMIT_COUNT` and `WAVELOGIC_COMMIT_SHA` environment variables.
3. Streamlit secrets `wavelogic_commit_count` and `wavelogic_commit_sha`.

If none are available (for example a deployment without `.git`), no version
label is shown. The application never fails because build metadata is missing.

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
#    -> output\WaveLogicMSO-Setup_v1.0.2.exe
```

### Debugging an installed app

- The launcher always writes a simple log to
  `%LOCALAPPDATA%\WaveLogicMSO\wavelogic_launch.log` (plus
  `wavelogic_streamlit.log`), and mirrors it into the install folder when
  that folder is writable.
- Start Menu → **"WaveLogic MSO (Debug console)"** runs the bundled server in
  a visible console window with live output (`wavelogic-debug.bat`).
- `WaveLogicMSO.exe --debug --autolaunch` skips the welcome window, enables
  verbose/Streamlit debug logging, and starts the server immediately.

The installer bundles the whole app (no Python install needed by the end user)
and is typically published as a GitHub Release asset.

## Credits

- **Designer:** Piston
- **Developer:** Kishan J. — <https://github.com/KSHNKMRJHA>
- **Made with:** love and Open-Source AI
- **Powered by:** Streamlit, NumPy, pandas, Plotly, Python

## Contact & Connect

Have a question, idea, or want to collaborate? Reach out on LinkedIn:

- [**Kishan J. on LinkedIn**](https://www.linkedin.com/in/kshnkmrjha/)

## License

[MIT](LICENSE) © 2026 Kishan J.