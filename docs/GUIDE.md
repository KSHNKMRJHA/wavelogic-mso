# WaveLogic MSO — User Guide

A complete, step-by-step tutorial for WaveLogic MSO. The same content is
available in-app on the **User Guide** page.

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
   dropdown if needed.

### CSV format reference

```csv
Time(s),CH1,CH2
0.000000,3.3,1.20
0.000001,3.3,1.21
0.000002,0.0,1.22
```

- One numeric time column + one or more numeric channel columns.
- Voltages are assumed to be in volts.
- Duplicate or non-monotonic timestamps are repaired automatically by the
  decoder (a warning tells you when).

## 3. View channels

Tick channels under **Show simultaneously**. They share one time axis, drawn
as transparent color-coded overlays. Large files are decimated for
responsiveness; exports always keep full resolution.

## 4. Zoom and read cursors

Use the Plotly toolbar: box zoom, pan, home. The crosshair tool updates the
cursor readouts (per-channel values + time deltas) at the pointer position.

## 5. Math channels

- **Enable math channels** → adds **Differential (A - B)** and **Invert (A)**
  traces to the plot.
- **Window readouts** compute edge frequency, duty cycle, logic levels and
  transition counts for the visible window.

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

## 8. Other protocols

- **Manchester / Differential Manchester** — bit-aligned Manchester decoding.
- **NRZ** — clocked NRZ with phase and bits-per-word options.
- **PWM** — per-pulse period and duty measured directly.

## 9. Export

- **Per-protocol CSV** — the decoded tables.
- **Summary text log** — metrics + transcript, ready for a bug report.
- **Offline interactive HTML** — the visible window as a self-contained Plotly
  chart (no CDN).
- **Full-resolution window CSV** and a **ZIP** with everything.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| "CSV import failed" | Wrong delimiter / metadata rows / non-UTF-8. Adjust the import options. |
| "required channel missing" | Tick the channel under **Show simultaneously**. |
| Decoder warning "not strictly increasing" | Expected — the decoder rebuilt a uniform time base. |
| Slow chart on huge files | Decimation is automatic; exports keep full resolution. |