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
  Differential Manchester, NRZ, and PWM — each with configuration options,
  status chips, metrics, exportable tables, and a plain-text transcript.
- **Differential Manchester analysis modes** — **Multi-message / Burst Scan**
  finds and independently validates every message in a long capture, while
  **Single Frame** runs the legacy decoder on one frame.
- **Robustness** — Schmitt-style hysteresis logic extraction, automatic display
  decimation for large files, full-resolution decoding and exports.
- **Debug & Logs** — an opt-in, bottom-of-page panel with runtime and import
  diagnostics, a bounded recent-log buffer, and log/diagnostics downloads.
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
| [RELEASE_NOTES.md](RELEASE_NOTES.md) | Release notes (Differential Manchester analysis modes, multi-message scanning) |
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
| Differential Manchester | analysis mode (Multi-message / Burst Scan or Single Frame), decoder signal source (single/derived signal or differential pair), nominal bit time, preamble count, clock alignment, transition hold-off | validated messages count, per-message summary, decoded bits + hex per message (Single Frame: bits + hex groups) |
| NRZ | phase, bits/word, MSB-first | bits + hex words |
| PWM | per-pulse | period & duty per pulse |

## Differential Manchester

Differential Manchester analysis offers two explicit **Analysis mode** options:

| Analysis mode | When to use | What it does |
| --- | --- | --- |
| **Multi-message / Burst Scan** *(default)* | Captures that may contain one or more messages | Scans the selected capture/window with the paired-channel scanner and presents each independently validated message |
| **Single Frame** | A window you have deliberately cropped to one frame | Runs the legacy single-frame decoder on the selected signal |

Multi-message / Burst Scan does **not** require you to crop the capture to a
single frame first, and the legacy decoder is never applied to an entire
capture in that mode.

### Decoder signal source

WaveLogic MSO always decodes **one logical waveform**. Choose how that waveform
is provided:

| Source | What it means | Controls |
| --- | --- | --- |
| **Single / derived signal** *(default)* | Decode one waveform directly | **Decode signal** — a physical channel (e.g. `CH3`) or a math/derived channel you created (e.g. `MATH: CH3 - CH4`) |
| **Differential pair** | WaveLogic MSO constructs one differential waveform from two physical channels | **Positive (+)** and **Negative (−)**, plus a live `Derived signal: CH3 − CH4` readout |

The **Decode signal** list contains everything currently available to the
decoder — physical channels and any visible math/derived channel. Nothing is
computed twice: a math channel shown on the scope is the same signal offered to
the decoder.

In **Differential pair** mode a suggestion such as *Suggested differential pair:
CH3(V) / CH4(V)* may appear when two channels are clearly the most active. The
suggestion is only a convenience, applies only to differential-pair mode, and is
never a guaranteed protocol identification. Common captures often use
`CH3`/`CH4`, but that is an example, not a requirement.

### Timing configuration

**Nominal bit time** is expressed in microseconds (µs) and defaults to
`12.8 µs`; adjust it when a capture uses different timing. `12.8 µs` is an
**empirical default** for the current workflow, not a universal Differential
Manchester protocol specification. Other controls: preamble bit count, clock
alignment, and transition hold-off.

### Results

Multi-message / Burst Scan reports:

- the number of independently validated messages
- a compact per-message summary table (message, start/end, duration, decoded
  bits, packet bits, fitted bit time, preamble/sync/clock status, structural
  coverage)
- a message selector with a per-message detail view (status chips, metrics,
  decoded bits, packet bytes, pulse timing, frame summary, waveform figure, text
  summary)
- scan diagnostics when nothing is validated

Only independently validated messages are presented as detected messages. Not
every region of electrical activity becomes a decoded message. Successful scans
also export `dm_messages_summary.csv` and `dm_messages_bits.csv`.

### Long-window guidance

If **Single Frame** reports that the selected window spans too many half-bit
cells, the window is too large for the single-frame decoder. This is intentional
protection and the data is never silently cropped. Either:

1. narrow the **Window** controls to one frame, or
2. switch **Analysis mode** to **Multi-message / Burst Scan**.

### Acceptance model (conservative by design)

A decoder timing fit alone is not sufficient evidence. A candidate is presented
as a validated message only when several independent signals agree:

- paired channel activity (in differential-pair mode the two selected channels
  are correlated)
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

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| `CSV import failed` | Check the delimiter, "Metadata rows before header", and that the file is UTF-8. |
| "required channel missing" | Tick the channel under **Show simultaneously** in the sidebar. |
| Warning: timestamps "not strictly increasing" | Expected for duplicated/quantized timestamps — a uniform time axis is reconstructed for display and decoding. |
| Single Frame: "the selected window spans too many half-bit cells" | The window is too large for the single-frame decoder. Narrow the **Window** controls to one frame, or switch **Analysis mode** to **Multi-message / Burst Scan**. |
| Burst Scan: "No independently validated Differential Manchester messages were found" | Check the decoder signal (and, in differential-pair mode, the Positive/Negative channels), the nominal bit time, and the selected capture window. The scanner only reports independently validated messages. |
| Burst Scan: budget warning | The decoder-call budget was reached; messages already validated remain valid, but the scan may be incomplete. Narrow the window or refine the decoder signal. |
| Slow chart on huge files | Display decimation is automatic; decoding and exports use full resolution. |

## Debug & Logs

At the bottom of the page there is an opt-in **Debug & Logs** section, disabled
by default. When enabled it shows:

- application information (build label, Python and Streamlit versions)
- runtime information (working directory, `sys.path`, platform, process id)
- `analyzer_core` import diagnostics (resolved file, size, hash, and whether the
  expected helper is present)
- imported API verification for every symbol the app imports from
  `analyzer_core`
- a safe result for the exact `analyzer_core` named import
- current application state (file/window/protocol/mode)
- the most recent exception, when one occurred
- the most recent bounded application log records (timestamp, level, message)

It also provides **Download debug log** (text), **Download diagnostics** (JSON)
and **Clear debug log**. Diagnostics are observational only: no secrets,
credentials, environment variables, or uploaded waveform contents are shown or
included in the downloads.

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