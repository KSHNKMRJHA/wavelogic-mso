# Release Notes

## Decoder signal source selection

### Added

- **Decoder Signal Source** selector for Differential Manchester, replacing the
  Channel A / Channel B mental model:
  - **Single / derived signal** *(default)* — decode one waveform: a physical
    channel or a math/derived channel you created.
  - **Differential pair** — WaveLogic MSO constructs one differential waveform
    from two physical channels via **Positive (+)** / **Negative (−)**, shown as
    a live `Derived signal: CH3 − CH4` readout.
- The **Decode signal** list reuses the existing visible/math channel
  representation, so a math channel already shown on the scope can be decoded
  directly — no duplicate waveform computation.
- Burst-scan results now state the decoded signal (`Decoder signal: …`).
- The differential-pair suggestion now appears **only** in differential-pair
  mode.

### Changed

- Multi-message single-signal scanning feeds the selected waveform to the
  existing paired-channel scanner (same waveform on both inputs) and still never
  runs the legacy decoder across a whole capture.
- Single Frame accepts a single/derived signal; in differential-pair mode it
  decodes the constructed differential waveform.
- Documentation and in-app help updated to the "one logical signal" model.

### Compatibility

- Scanner heuristics, decoder acceptance criteria, timing algorithms, timestamp
  reconstruction, and message validation are unchanged.
- `decode_waveform()` and `analyzer_core.py` are unchanged.

## Explicit Differential Manchester analysis modes and burst-scan UX

> **Superseded terminology:** the "Channel A / Channel B" control described
> below was replaced by the **Decoder Signal Source** selector (see the section
> above). Behaviour and acceptance model are unchanged.

### Added

- Explicit **Analysis mode** selector for Differential Manchester with two
  modes: **Multi-message / Burst Scan** (default) and **Single Frame**.
- **Multi-message / Burst Scan** scans the selected capture/window for
  independently validated messages — the user does not have to crop to a single
  frame first.
- **Channel A / Channel B** selection, with a convenience suggestion for a
  likely active differential pair (for example `CH3` / `CH4` when those channels
  are clearly the most active). The suggestion is only a hint and never
  overrides a manual choice.
- Burst-scan result presentation: validated-message count, a compact per-message
  summary, a message selector, and the per-message detail view.
- Actionable long-window guidance: when the single-frame decoder rejects an
  oversized window it reports the sample count, window duration and configured
  bit time, and recommends narrowing the window or switching to
  Multi-message / Burst Scan — data is never silently cropped.
- Clearer empty-result diagnostics: scanner status, candidate regions, decoder
  calls, decoder-call-budget flag, selected channels, bit time and window
  duration.

### Changed

- The legacy decoder now runs only in **Single Frame** mode. The
  multi-message workflow calls the existing paired-channel scanner and never
  applies the legacy decoder to a whole capture.
- The Differential Manchester panel is reorganised into explicit sections
  (Analysis mode · Channels · Timing configuration · Result), replacing the old
  "Detect multiple messages" checkbox.
- Documentation and in-app help refreshed to match the current workflow.

### Compatibility

- Scanner acceptance criteria, timing tolerance, sparse-transition rejection,
  boundary coverage, duplicate clustering and the decoder-call budget are
  unchanged.
- `decode_waveform()` and `analyzer_core.py` are unchanged.
- Unrelated protocol paths (UART/RS-232, SPI, I2C, Manchester, NRZ, PWM) are
  unchanged.

### Notes

- `~12.8 µs` remains an empirical default bit-time value used for the current
  workflow; it is not a universal Differential Manchester protocol constant.

## Differential Manchester multi-message analysis

> **Superseded UI:** the multi-message scanner below is now selected through the
> explicit **Analysis mode → Multi-message / Burst Scan** control described
> above, rather than the older "Detect multiple messages (multi-burst scan)"
> checkbox. The scanner behaviour and acceptance model are unchanged.

### Added

- Differential Manchester multi-message scanning (originally introduced as the
  opt-in "Detect multiple messages" checkbox; now selected through
  **Analysis mode → Multi-message / Burst Scan**).
- Validated message aggregation with a message count and per-message summary.
- **Message N** selection with a per-message detail view.
- Logical frame start/end offsets for each validated message, distinct from the
  decoder window and pre-roll.
- Per-message waveform detail cropped to the logical frame boundaries.
- Message-level CSV exports: `dm_messages_summary.csv` and
  `dm_messages_bits.csv`.

### Safety

- Independent raw-transition structural validation: boundary coverage is derived
  from the original waveform samples, not from the decoder's fitted grid.
- Structural boundary coverage and a minimum transition-density guard reject
  sparse decoder-grid fits (decoder timing fit alone is not acceptance).
- Local timing plausibility prefilter before expensive decoding.
- Duplicate clustering collapses CH3/CH4 and transition-offset detections of the
  same physical frame into one message.
- Long captures report only independently validated frames; otherwise no
  validated message is shown.
- Bounded decoder-call budget so pathological captures cannot trigger unbounded
  work; reaching it flags the scan as potentially incomplete.

### Compatibility

- The existing single-frame Differential Manchester path is preserved (now
  selected via **Analysis mode → Single Frame**). **Multi-message / Burst
  Scan** is the default analysis mode as of the analysis-modes update above.
- `decode_waveform()` unchanged.
- Unrelated protocol paths (UART/RS-232, SPI, I2C, Manchester, NRZ, PWM)
  unchanged.

### Notes

- Multi-message analysis is intentionally conservative; it is now the default
  Differential Manchester analysis mode.
- Acceptance thresholds are engineering safety heuristics, not formal protocol
  specifications; `~12.8 µs` is an empirical timing prior, not a universal
  protocol constant.
- No protocol-compliance claims are made for any third-party standard.
