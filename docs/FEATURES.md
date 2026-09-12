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
| Differential Manchester (legacy) | original project convention; metaview 16-bit aligned |
| NRZ (clocked) | phase alignment, bits/word, MSB-first, robust clock fit |
| PWM | per-pulse period and duty measured from the waveform |

## Robustness & quality

- **Timestamp repair** — duplicate/non-monotonic timestamps never break
  decoding; a uniform time base is reconstructed and reported.
- **Schmitt-style logic extraction** — noise-resistant hysteresis
  thresholding of analog samples into 0/1 levels.
- **Status chips** — OK / FAIL / WARNING per decode, plus per-protocol metric
  tiles (baud, frames, NACK count, duty, ...).
- **Plain-text decode log** — human-readable transcript for bug reports.
- **Local-first** — no cloud submission of your capture data.

## In-app documentation

- Introduction page
- User Guide page
- Features page
- Credits page