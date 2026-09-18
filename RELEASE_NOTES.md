# Release Notes

## Differential Manchester multi-message analysis

### Added

- Optional multi-message Differential Manchester scanning, enabled with
  **Detect multiple messages (multi-burst scan)** (opt-in; disabled by default).
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

- Existing single-message Differential Manchester path preserved and remains the
  default.
- `decode_waveform()` unchanged.
- Unrelated protocol paths (UART/RS-232, SPI, I2C, Manchester, NRZ, PWM)
  unchanged.

### Notes

- Multi-message mode is intentionally conservative and opt-in.
- Acceptance thresholds are engineering safety heuristics, not formal protocol
  specifications; `~12.8 µs` is an empirical timing prior, not a universal
  protocol constant.
- No protocol-compliance claims are made for any third-party standard.
