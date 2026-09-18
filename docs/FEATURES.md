# WaveLogic MSO — Feature List

Everything in this list ships in the app. There is no paid tier.

## Scope & measurement

- **Simultaneous channels** — any subset of channels on one shared time axis,
  as transparent color-coded overlays.
- **Automatic decimation** — large captures stay responsive; exports keep full
  resolution.
- **Crosshair cursors** — pointer readouts with per-channel values and time
  deltas.
- **Differential & inverted channels** — A - B math and inverted copies drawn
  as real traces.
- **Window readouts** — edge frequency, duty cycle, logic levels, transition
  counts, per visible window.
- **Offline HTML export** — self-contained Plotly chart; no CDN required.

## Protocol decoders

| Protocol | Highlights |
| --- | --- |
| UART / RS-232 | baud, data bits, parity, stop bits, idle level, bit order; framing/parity status per frame |
| SPI (4-wire) | CPOL/CPHA, active CS, bits/word, MSB-first, CS-gap merge |
| I2C (7-bit) | full transcript: START, address+R/W, ACK/NACK per byte, STOP; end-of-stream robust |
| Manchester (Biphase-L) | standard bit alignment with midpoint-transition handling |
| Differential Manchester | explicit **Analysis mode**: Multi-message / Burst Scan or Single Frame; Channel A/B, nominal bit time, preamble count, clock alignment, transition hold-off |
| NRZ (clocked) | phase alignment, bits/word, MSB-first, robust clock fit |
| PWM | per-pulse period and duty measured from the waveform |

## Differential Manchester analysis modes

- **Multi-message / Burst Scan** *(default)* — scans the selected capture/window
  with the paired-channel scanner and presents each independently validated
  message (count, per-message summary, message selector, per-message detail and
  message-level CSV exports).
- **Single Frame** — runs the legacy single-frame decoder on Channel A, with
  automatic/manual thresholds; appropriate for a window deliberately cropped to
  one frame.
- **Channel A / Channel B** selection with a convenience suggestion for a likely
  active differential pair (a hint only, never a guaranteed protocol
  identification).
- **Long-window guidance** — if the single-frame decoder rejects an oversized
  window, the app reports samples/duration/bit time and recommends narrowing the
  window or switching to Multi-message / Burst Scan; data is never silently
  cropped.
- Only independently validated messages are reported as detected messages.

## Robustness & quality

- **Timestamp repair** — duplicate/non-monotonic timestamps never break
  decoding; a uniform time base is reconstructed and reported.
- **Schmitt-style logic extraction** — noise-resistant hysteresis
  thresholding of analog samples into 0/1 levels.
- **Status chips** — OK / FAIL / WARNING per decode, plus per-protocol metric
  tiles (baud, frames, NACK count, duty, ...).
- **Plain-text decode log** — human-readable transcript for bug reports.
- **Local-first** — no cloud submission of your capture data.

## Diagnostics

- **Debug & Logs** — an opt-in panel at the bottom of the page, disabled by
  default. When enabled it shows application information (build label, Python
  and Streamlit versions), runtime information (working directory, `sys.path`,
  platform, process id), `analyzer_core` import diagnostics, imported-API
  verification, the current application state, the most recent exception, and a
  bounded buffer of recent log records.
- **Downloads** — **Download debug log** (text), **Download diagnostics**
  (JSON), and **Clear debug log**.
- **Safe by design** — no secrets, credentials, environment variables, or
  uploaded waveform contents are displayed or downloaded.

## In-app documentation

- Introduction page
- User Guide page
- Features page
- Credits page