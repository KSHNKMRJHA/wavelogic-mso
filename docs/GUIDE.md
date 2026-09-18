# WaveLogic MSO — User Guide

A complete, step-by-step tutorial for WaveLogic MSO. The same content is
available in-app on the **User Guide** page.

## Overall workflow

1. Start WaveLogic MSO.
2. Upload/import a CSV capture.
3. Verify the detected time column and channels.
4. Select a protocol.
5. Configure that protocol.
6. Analyze / decode.
7. Inspect the waveform.
8. Inspect the decoded results.
9. Export results if required.
10. Use **Debug & Logs** when troubleshooting.

## 1. Launch the app

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux
python -m pip install -r requirements.txt
streamlit run app.py
```

Open **http://localhost:8501**.

## 2. Import a CSV

1. Click **Upload oscilloscope CSV**.
2. Select the delimiter: **Comma**, **Semicolon**, or **Tab**.
3. If the file has metadata lines above the header, set **Metadata rows before
   header** to skip them.
4. The time column is auto-detected; override it with the **Time column**
   dropdown if needed, and set **CSV time unit** when the file is not in
   seconds.

### CSV format reference

```csv
Time(s),CH1,CH2
0.000000,3.3,1.20
0.000001,3.3,1.21
0.000002,0.0,1.22
```

- One numeric time column + one or more numeric channel columns.
- Voltages are assumed to be in volts.

### Time axis and timestamp quality

- Clean, usable timestamps can be used directly (**Use CSV timestamps
  directly**).
- Low-quality, quantized, duplicated or non-monotonic timestamps are detected
  automatically and default to **Reconstruct uniform timestamps**, which builds
  a uniform time axis from row order and the capture duration.
- This affects only the *time axis* used for display and decoding. The
  underlying channel samples passed to the decoders remain the full-resolution
  waveform, and exports keep both the original and applied timestamps.

## 3. View channels

Tick channels under **Show simultaneously**. They share one time axis, drawn
as transparent color-coded overlays. Large files are simplified for
responsiveness (adjust with **Total plotted-point budget**); decoding and
exports always keep full resolution.

## 4. Zoom and read cursors

Use the Plotly toolbar: box zoom, pan, home. The crosshair tool updates the
cursor readouts (per-channel values + time deltas) at the pointer position.

## 5. Math channels and display controls

- **Add differential math channel** → adds a computed **Math A - Math B** trace.
- **Channel display controls** set **Display gain**, **Display offset (V)** and
  **Invert display** per channel. These are display-only; decoders always use
  raw voltage samples.

## 6. Decode UART (quick win)

Under *Signal decoding (protocol analyzer)*:

1. ✅ **Enable decoding**
2. Protocol → **UART / RS-232**
3. **Decoder source** → the TX channel (`sample_data/uart_example.csv` is
   already a UART frame)
4. Baud = **9600**, 8 data bits, no parity, 1 stop bit, idle **HIGH**
5. Read the frames table: byte number, hex, decimal, ASCII, bit order, status.

## 7. Decode SPI or I2C

Required channels must be **ticked visible** in the sidebar first.

- **SPI** — channels: SCLK, MOSI, MISO, CS. Configure CPOL/CPHA, active
  chip-select level, bits per word, MSB-first, and CS-gap merging.
- **I2C** — channels: SCL, SDA. The transcript shows START, address + R/W,
  ACK/NACK per byte, data, and STOP.

If a required channel is missing the decoder says so instead of guessing.

## 8. Differential Manchester

Differential Manchester has two explicit **Analysis mode** options. Choose the
mode first, then the channels and timing.

### Step A — Select the protocol

Protocol → **Differential Manchester (legacy project)**.

### Step B — Choose Analysis mode

- **Multi-message / Burst Scan** *(default)* — recommended for captures that may
  contain one or more messages. It scans the selected window for independently
  validated messages and reports each one separately. You do **not** need to
  crop the capture to a single frame.
- **Single Frame** — use this when you have deliberately narrowed the window to
  one frame; it runs the legacy single-frame decoder for detailed analysis of
  that frame.

### Step C — Choose the decoder signal source

WaveLogic MSO always decodes **one logical waveform**. Choose how it is provided:

- **Single / derived signal** *(default)* — decode one waveform directly via the
  **Decode signal** dropdown. It lists every signal available to the decoder: a
  physical channel (for example `CH3`), or a math/derived channel you created
  (for example `MATH: CH3 - CH4`).
- **Differential pair** — WaveLogic MSO constructs one differential waveform
  from two physical channels. Select **Positive (+)** and **Negative (−)**; the
  panel shows the derived signal (for example `Derived signal: CH3(V) − CH4(V)`).

In **Differential pair** mode the UI may show a suggestion such as *Suggested
differential pair: CH3(V) / CH4(V)* when two channels are clearly the most
active. The suggestion is only a convenience, applies only to differential-pair
mode, and is **not** a guaranteed protocol identification — you can always select
the channels manually. Some captures use CH3/CH4; treat that as an example, not a
rule.

### Step D — Timing configuration

- **Nominal bit time (µs)** — in microseconds; defaults to `12.8 µs`. Adjust it
  if the capture uses different timing.
- **Preamble bit count** (default 22), **Clock alignment**, and **Transition
  hold-off (µs)** are also available.
- `12.8 µs` is an empirical default for this workflow, **not** a universal
  Differential Manchester protocol specification.

### Step E — Read the results

A successful **Multi-message / Burst Scan** shows the **Validated messages**
count, a compact per-message summary table, a **Select message** dropdown, and
the full detail for the selected message (status chips, metrics, decoded bits,
packet bytes, pulse timing, frame summary, waveform figure, text summary).

Only **independently validated** messages are presented as detected messages —
not every region of electrical activity becomes a decoded message. If nothing is
validated, the panel reports the scanner status, candidate regions, decoder
calls and the selected settings so you can adjust the channel pair or bit time.

**Single Frame** additionally provides **Threshold mode** (Automatic / Manual)
with LOW/HIGH threshold inputs. Manual thresholds apply to Single Frame only.

### Long-window guidance

If Single Frame reports that the selected window spans too many half-bit cells,
the window is too large for the single-frame decoder. This is intentional
protection and the data is never silently cropped. Either:

1. narrow the **Window** controls to one frame, or
2. switch **Analysis mode** to **Multi-message / Burst Scan**.

## 9. Other protocols

- **Manchester (Biphase-L)** — bit-aligned Manchester decoding.
- **NRZ** — clocked NRZ with phase and bits-per-word options.
- **PWM** — per-pulse period and duty measured directly.

## 10. Export

- **Per-protocol CSV** — the decoded tables.
- **Summary text log** — metrics + transcript, ready for a bug report.
- **Offline interactive HTML** — the visible window as a self-contained Plotly
  chart (no CDN).
- **Full-resolution window CSV** and a **ZIP** with everything.
- Differential Manchester burst scans also produce `dm_messages_summary.csv` and
  `dm_messages_bits.csv`.

## 11. Debug & Logs

At the bottom of the page is an opt-in **Debug & Logs** section, **disabled by
default**. Enable **Enable debug & diagnostic logs** to see application and
runtime information, `analyzer_core` import diagnostics, imported-API
verification, the current application state, the most recent exception, and the
bounded recent log records.

It also provides **Download debug log**, **Download diagnostics** (JSON) and
**Clear debug log**. Diagnostics are observational only — no secrets,
credentials, environment variables or uploaded waveform contents are shown or
downloaded.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| "CSV import failed" | Wrong delimiter / metadata rows / non-UTF-8. Adjust the import options. |
| "required channel missing" | Tick the channel under **Show simultaneously**. |
| Decoder warning "not strictly increasing" | Expected — a uniform time axis was reconstructed for display and decoding. The decoder still receives full-resolution samples. |
| Single Frame: "the selected window spans too many half-bit cells" | Narrow the **Window** controls to one frame, or switch **Analysis mode** to **Multi-message / Burst Scan**. |
| Burst Scan: "No independently validated messages were found" | Check the decoder signal (and, in differential-pair mode, the Positive/Negative channels), the nominal bit time, and the selected window. Only independently validated messages are reported. |
| Burst Scan: decoder-call budget warning | The scan may be incomplete; validated messages remain valid. Narrow the window or refine the decoder signal. |
| Slow chart on huge files | Display simplification is automatic; decoding and exports keep full resolution. |
