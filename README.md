# WaveLogic MSO

**Multi-Channel Protocol Analyzer** — a bench-style oscilloscope and protocol
decoder that runs entirely on CSV files, in your browser.

> Designed by **Piston** · Developed by **Kishan J.**
> Made with love and Open-Source AI — free forever, like it should be.

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

## Credits

- **Designer:** Piston
- **Developer:** Kishan J. — <https://github.com/KSHNKMRJHA>
- **Made with:** love and Open-Source AI
- **Powered by:** Streamlit, NumPy, pandas, Plotly, Python

## License

[MIT](LICENSE) © 2026 Kishan J.