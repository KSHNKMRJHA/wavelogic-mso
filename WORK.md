# WaveLogic MSO Engineering Work Document

This is a persistent investigation handoff for the next AI coding agent. It is
not a release document.

**Do not commit, push, tag, or release anything unless explicitly instructed.**

## Project

- Project: WaveLogic MSO - Multi-Channel Protocol Analyzer
- Repository: https://github.com/KSHNKMRJHA/wavelogic-mso
- Branch: `main`
- Streamlit application: `app.py`
- Current published Git revision: `820a5fd`
- Current application build identification: `v11 · build 820a5fd`
- The version/build label was recently added and is working.

## Current Primary Problem

The capture `stm32wink150ms0.csv` produces two simultaneous problems in the
public Streamlit application:

1. Decoder error:

   ```text
   Decoder could not analyze this window:
   The waveform could not be separated into LOW and HIGH levels.
   ```

2. The displayed waveform does not visually resemble the actual oscilloscope
   waveform.

The issue may be upstream of the protocol decoder. Do not immediately modify
the decoder. First identify where the captured signal representation becomes
incorrect.

## Capture Information

- File: `stm32wink150ms0.csv`
- Approximate size: 62.1 MB
- Current Streamlit observations:
  - Window samples: 1,000,000
  - Sampled window span: 1,500,020 us
  - Median positive delta-t: 10.000000 us
- The UI reports duplicate/reset timestamps and displays a warning that the
  selected timestamps are not strictly increasing.
- The application therefore uses a uniform reconstructed time axis for this
  capture.

These UI values must be checked against the actual CSV contents. Do not assume
they are correct.

## Historical Expected Behavior

This exact capture was previously validated during the Differential Manchester
multi-message implementation with the expected result:

```text
4 independently validated messages
```

The previously validated production architecture was:

```text
full waveform
    -> paired CH3/CH4 electrical activity
    -> transition-aligned candidate refinement
    -> multi-offset/all-offset preamble search
    -> local timing validation
    -> existing decode_waveform(candidate)
    -> preamble + sync + clock acceptance
    -> independent validation
    -> accepted message
    -> continue scanning
```

The legacy decoder is `decode_waveform()`. It must remain unchanged unless the
investigation conclusively proves that the decoder itself is the source of the
problem.

## Other Known Validation Results

Previously validated Differential Manchester multi-message results:

| Capture | Validated messages |
| --- | ---: |
| `lpmwink1.7ms0.csv` | 2 |
| `wink 2 resp0.csv` | 2 |
| `stm32wink150ms0.csv` | 4 |
| `ackn0.csv` | 1 |
| `RigolDS0.csv` | 1 |
| `wnk0.csv` | 0 |
| `stm32_wink1s0.csv` | 0 |
| `wink_1s0.csv` | 0 |

Do not weaken rejection criteria merely to make a capture decode. These
production acceptance concepts must remain intact:

- Paired electrical activity
- Sufficient transition density
- Local timing consistency
- Preamble validation
- Sync validation
- Clock validation
- Independent boundary coverage
- Sparse-transition rejection
- Duplicate clustering
- Decoder-call budget

The empirical 12.8 us timing cluster is not a protocol specification and must
not become an unconditional hard-coded acceptance rule.

## Primary Investigation Plan

Trace the complete data path in this order:

```text
CSV
  -> CSV parser
  -> timestamp handling
  -> duplicate/reset handling
  -> uniform time reconstruction
  -> selected window
  -> raw channel arrays
  -> channel mapping
  -> display/downsampling pipeline
  -> Plotly waveform
  -> decoder input
  -> Differential Manchester orchestration
  -> candidate extraction
  -> legacy decoder
```

The goal is to identify the first point where the actual captured signal
differs from the representation being used.

## 1. Raw CSV Investigation

Inspect the actual `stm32wink150ms0.csv` contents and record:

- CSV header and metadata/header rows
- Time column
- CH1, CH2, CH3, and CH4 columns
- Total row count
- Duplicate timestamp count
- Timestamp reset count and locations
- NaN and empty-value counts
- CH1 min/max/mean/median
- CH2 min/max/mean/median
- CH3 min/max/mean/median
- CH4 min/max/mean/median
- Useful unique-voltage characteristics
- Median positive delta-t
- Minimum positive delta-t
- Maximum positive delta-t
- Largest timestamp gap
- Total capture duration

Compare all results with the Streamlit summary. Use the actual file, not only
the UI output.

## 2. Time Axis Investigation

Trace the exact timestamp processing and record:

```text
raw_time[0]
raw_time[-1]
raw_time length
median(diff(raw_time))

reconstructed_time[0]
reconstructed_time[-1]
reconstructed length
reconstructed sample interval
```

Determine whether uniform reconstruction:

- Preserves sample order
- Preserves capture duration appropriately
- Preserves the intended sample interval
- Stretches the waveform
- Compresses the waveform
- Creates artificial transitions
- Removes transitions
- Changes message timing

The decoder requires strictly increasing timestamps. Do not remove that
requirement. If duplicate/reset timestamps cause reconstruction, verify that
the reconstruction is mathematically correct and does not stretch, compress,
reorder, or distort the captured waveform.

## 3. Channel Mapping

Verify the exact mapping:

```text
CSV CH1 -> application CH1
CSV CH2 -> application CH2
CSV CH3 -> application CH3
CSV CH4 -> application CH4
```

Check for channel swapping, offsets, polarity inversion, gain, normalization,
differential substitution, or accidental use of display values as decoder
input. Display gain/offset/polarity may be used for visualization, but decoder
input must remain raw voltage data.

## 4. Differential Manchester Signal Path

Determine exactly which channels and representation the existing Differential
Manchester implementation uses. Verify that the current application uses the
same pair and raw signal representation that previously produced four messages
for `stm32wink150ms0.csv`.

Do not guess the channel pair. Trace the implementation and tests. Compare:

```text
CH3
CH4
CH3 - CH4
```

and any existing differential processing.

## 5. Display/Waveform Fidelity

Trace the exact display pipeline and record:

- Raw samples
- Selected window
- Display point budget
- Actual plotted samples
- Downsampling method
- Interpolation method
- Aggregation method
- Envelope/min-max handling
- Plotly trace data
- Exact number of points sent to Plotly for the 1,000,000-sample window

The UI currently says:

```text
Display rendering may simplify very short gaps.
```

Determine whether simplification eliminates narrow pulses, rising/falling edges,
short gaps, transition timing, or relative CH3/CH4 timing. A digital or
logic-like waveform must not be visually converted into a fundamentally
different signal. Do not blindly increase the display point budget; first
identify the transformation causing the mismatch.

## 6. Display Data vs Decoder Data

Explicitly verify whether the decoder receives:

- Raw full-resolution samples
- Display-downsampled samples
- Reconstructed samples
- Interpolated samples
- Another transformed representation

The decoder must not accidentally receive a visualization/downsampled
representation when the architecture requires appropriate full-resolution raw
data. Display simplification must be isolated from decoder input.

## 7. Display vs Full-Resolution Diagnostic Comparison

Create a diagnostic comparison for a small region containing one known
Differential Manchester message. Compare:

```text
A. Raw full-resolution CH3/CH4 samples
B. Data passed to the decoder
C. Data rendered by Plotly
```

For each representation, record sample count, timestamp positions, transition
locations, polarity, and any gain/offset. These must preserve the same
transition locations and signal polarity. If they differ, identify the exact
function and line where the transformation occurs.

## 8. Low/High Failure Investigation

Only after the import, timestamp, channel, display, and decoder-input pipeline
has been traced, investigate why the legacy decoder reports:

```text
The waveform could not be separated into LOW and HIGH levels.
```

Possible causes include:

- Wrong channel
- Wrong channel pair
- Wrong polarity
- Gain or offset applied before decoding
- Reconstructed timestamps paired with the wrong voltage samples
- Display/downsampled data passed to the decoder
- A window boundary that excludes required levels or preamble context
- Flattened or distorted voltage values
- Incorrect low/high clustering caused by imported data rather than protocol
  logic
- A genuine legacy decoder limitation, only after upstream causes are ruled
  out

Do not change decoder behavior while these upstream hypotheses remain untested.

## 9. Required Investigation Evidence

Before proposing a code fix, produce an evidence table containing:

| Stage | Representation | Sample count | Time start/end | Interval | Signal notes |
| --- | --- | ---: | --- | --- | --- |
| CSV import |  |  |  |  |  |
| Selected window |  |  |  |  |  |
| Reconstructed axis |  |  |  |  |  |
| Decoder input |  |  |  |  |  |
| Plotly trace |  |  |  |  |  |

Also include a small-region comparison with exact transition indices/times for
CH3, CH4, and any differential signal. Preserve the raw diagnostic output in
the worktree if practical, but do not commit generated large data or secrets.

## 10. Code Invariants

Until the investigation proves otherwise:

- Leave `decode_waveform()` unchanged.
- Leave protocol decoder acceptance criteria unchanged.
- Leave Differential Manchester rejection criteria unchanged.
- Do not make the 12.8 us cluster an unconditional protocol rule.
- Do not pass Plotly display data into the decoder.
- Do not remove strict timestamp monotonicity requirements.
- Do not weaken sparse-transition rejection.
- Do not increase display point budget as a substitute for root-cause analysis.
- Do not modify unrelated application behavior.
- Do not commit, push, tag, or release.

## Investigation Progress

No capture-level investigation has been completed in this document yet.

When continuing, append dated findings here rather than replacing the problem
statement or invariants above.

### Initial Status

- `WORK.md` created as a persistent handoff.
- Repository was clean before this document was created.
- No code, decoder logic, protocol logic, or UI behavior has been changed by
  this investigation document.
- Next action: inspect the actual CSV and trace the import/time/display/decoder
  pipeline in the order specified above.

### Findings — 2026-09-18 (local investigation against HEAD `820a5fd`)

The capture `sample_latest/stm32wink150ms0.csv` (65,102,149 bytes) was
available locally, so every statistic below was measured, not assumed.

#### 1. Raw CSV (WORK.md section 1) — measured

- Header: `Time(s),CH1(V),CH2(V),CH3(V),CH4(V)` — no metadata rows, seconds,
  volts, zero NaN in any column.
- Rows: 1,000,000. Unique timestamps: 182,563 (81.7% duplicates, 817,437 zero
  steps, 0 backward steps, 0 resets). Duration: 1.50002 s.
- Timestamps are print-quantized to 5 significant figures (quantum 1 µs near
  t=0, 10 µs mid-file, 100 µs at the tail). This quantization — not scope
  acquisition — is the source of all duplicates.
- Median positive Δt: exactly 10 µs. Min: 1 µs. Max: 100 µs. Mean distinct
  spacing 8.2 µs. Inferred true grid: uniform ~1.5 µs
  (duration/(n−1) = 1.5000215 µs), consistent with every observed quantum.
- Voltages: CH1 median 0.0 (30 unique, max 5.86 V single spike block 62),
  CH2 median −0.32 (22 unique), CH3 median −0.008 std 0.051 (111 unique),
  CH4 median −0.016 std 0.052 (112 unique).
- Burst energy in CH3−CH4: exactly 4 high-energy blocks (rows ~20–30k,
  ~280–290k, ~540–550k, ~620–630k; abs times ~0 ms, ~388 ms, ~786 ms,
  ~907 ms). All other blocks are idle noise (std ~0.0068).

#### 2. Time axis (section 2) — measured

- `prepare_time_axis` reconstruction (`np.linspace(first, last, n)`) recovers
  the true 1.5000215 µs grid to within endpoint print-rounding (~33 ppm).
  Reconstruction is mathematically sound for this file; it does not stretch,
  compress, reorder, or invent transitions.
- Correction to the handoff: `main()` has NO "Automatic" time-axis mode. The
  sidebar radio (`app.py`, formerly line 1369) offers only Direct (default)
  or Reconstruction. `render_decoder` then independently defaults its decode
  axis to reconstruction when the window time is not strictly increasing.
  These are two separate decisions.

#### 3. Channel mapping (section 3) — verified in code

- `signals[name]` is built 1:1 from CSV columns (`app.py` main loop); no swap,
  gain, offset, inversion, or normalization touches decoder input. Display
  gain/offset/invert apply only inside `make_scope_figure`. MATH channel is
  opt-in (default off). Mapping is correct.

#### 4. Differential Manchester signal path (section 4) — verified

- Historical pair CH3/CH4 confirmed: full-waveform
  `scan_differential_manchester(decode_time, CH3, CH4, 12.8 µs, …)` on the
  current code returns **4 validated messages** (1.5 s scan; fits
  12.7986–12.8018 µs; coverage ≥ 0.987; 4 regions; 1008 decoder calls; budget
  not hit). A 40k-sample slice around burst 2 also validates 1 message.
- Decoder input is full-resolution raw window data (`window_signals`), never
  display-downsampled. Display uses `display_envelope` only.

#### 5/6. Display fidelity and display-vs-decoder (sections 5–6) — measured

- Default scope x-axis is the RAW print-quantized timestamps (radio default
  was Direct). In burst block 28 (10k rows): only 1,501 unique x (85%
  duplicates), quantum exactly 10 µs vs true 1.5 µs grid, ~6.7 samples stacked
  per x-column, max |x_raw − x_true| = 11.2 µs — nearly one 12.8 µs bit cell.
- Decoder, in contrast, defaults to the reconstructed true grid. So by
  default the scope view and the decoder used DIFFERENT time axes: smeared
  10 µs-column edges on screen vs exact timing in decode. This is the visual
  mismatch mechanism (ROOT CAUSE R2).
- Full-window envelope at default budget: 13,220 points/trace (80k/4 traces);
  per-bucket min/max preserved, so bursts still appear as spikes zoomed out.
  Narrowed windows (n ≤ budget) pass through exactly.

#### 7. Low/HIGH failure (section 8) — reproduced, root-caused (R1)

- `estimate_logic_levels_and_thresholds` on full-window CH1 and CH2 raises
  exactly `The waveform could not be separated into LOW and HIGH levels.`
  Both channels are single-level (≥98% identical after p1–p99 clipping), so
  one k-medians cluster is empty. CH3/CH4 separate fine (spans ~72 mV;
  21,472 / 20,510 transitions). An idle-only CH3 window also separates (span
  0.064 V), so the reported error cannot come from an idle window.
- Call path: `render_decoder` → DM legacy branch → line 866 threshold
  estimation on the user-selected single "Decoder source" → caught at the
  `try` (line 823) → `st.error("Decoder could not analyze this window: …")`
  at line 1269–1270. The scanner is only reachable AFTER line 866 succeeds.
- Conclusion: the pipeline, reconstruction, channels, thresholds, scanner,
  and legacy decoder are all correct for this capture. The deployed error
  occurs when the selected decoder source is a single-level channel
  (CH1/CH2). No decoder change is warranted; weakening LOW/HIGH validation
  would violate the invariants.

#### Evidence table

| Stage | Representation | Samples | Time start/end | Interval | Notes |
| --- | --- | ---: | --- | --- | --- |
| CSV import | `pd.read_csv`, raw text | 1,000,000 | −0.03182…1.4682 s | quantized (1/10/100 µs) | 0 NaN; 182,563 unique t |
| Selected window | full file (defaults) | 1,000,000 | span 1,500,020 µs | same as above | UI metrics verified exact |
| Reconstructed axis | `linspace` | 1,000,000 | same endpoints | 1.5000215 µs | ≈ true grid; 4-msg scan proves it |
| Decoder input | raw `window_signals` | 1,000,000/ch | — | — | CH3 21,472 / CH4 20,510 transitions |
| Plotly trace | `display_envelope` | 13,220/trace | quantized x | bucket min/max | 85% dup x in bursts; ≤11.2 µs x-error |

#### Fix applied (display-only, 2026-09-18, uncommitted)

- ROOT CAUSE R2 fix: the scope view defaulted to quantized raw time while the
  decoder used the reconstructed grid. Added pure helper
  `default_timestamp_mode(quality)` in `analyzer_core.py` (reconstruction
  default iff `low_precision`, else direct) and used it as the sidebar radio
  default in `app.py` (quality now assessed before the radio; user override
  retained; `prepare_time_axis`, decode path, thresholds, scanner,
  `decode_waveform()` all untouched).
- Regression test: `tests/test_timestamp_mode.py` (6 tests). Full suite:
  24 passed / 0 failed. `py_compile` and `git diff --check` clean.
- ROOT CAUSE R1 requires no code change: with Decoder source `CH3(V)`,
  paired channel `CH4(V)`, multi-message enabled, nominal 12.8 µs, the app
  returns the historical 4 messages. Selecting a flat channel (CH1/CH2)
  correctly refuses with the LOW/HIGH error.

#### Remaining / next-agent instructions

- Do NOT commit/push/tag/release (no instruction to do so).
- Suggested deployed retest: upload `stm32wink150ms0.csv`, keep reconstructed
  default, enable decoding → DM legacy → source `CH3(V)` → multi-message →
  paired `CH4(V)` → expect 4 validated messages at ~0/388/786/907 ms.
- Optional UX follow-up (not implemented): guide channel selection or defer
  single-channel estimation when multi-message scan is intended. Any such
  change must not weaken LOW/HIGH validation or acceptance criteria.
- Diagnostic scripts used (outside repo, not committed):
  `wl_csv_stats.py`, `wl_levels.py`, `wl_scanslice.py`, `wl_scanfull.py`,
  `wl_display.py` in `C:\Users\Lenovo\AppData\Local\Temp\opencode\`.
- `decode_waveform()` was NOT modified. No acceptance criteria were changed.

### Senior verification — 2026-09-18 (independent re-run against HEAD `820a5fd` + patch)

A second agent independently re-verified every claim above against the actual
code and the local capture (`sample_latest/stm32wink150ms0.csv`, 65,102,149
bytes). Nothing was taken on trust.

- R1 CONFIRMED: channel order is `[CH1(V), CH2(V), CH3(V), CH4(V)]`, so the
  default "Decoder source" (`st.selectbox` index 0) is the flat `CH1(V)`.
  Full-window level estimation raises the exact reported message on CH1/CH2
  and succeeds on CH3/CH4 (spans 0.071896/0.071258). The estimation at
  `app.py:867` executes before the multi-message checkbox (`:885`) and the
  scanner call (`:907`), inside the `try` at `:824` whose `except` at
  `:1270–1271` renders the exact UI error. The scanner is genuinely gated.
  Factory defaults therefore reproduce the reported error with no user error
  required beyond accepting defaults.
- R2 CONFIRMED: actual file quality is `low_precision=True` (dup 0.8174 +
  coarse-resolution reasons, 0 backward steps) → helper returns
  `Reconstruct uniform timestamps` → prepared axis strictly increasing,
  1,000,000 samples, 1.5000215 µs interval. Display/decoder axis mismatch by
  default is resolved by the patch; decode axis behavior is unchanged.
- 4-message reproduction CONFIRMED live: `scan_differential_manchester` on
  `(linspace, CH3, CH4)` → status `validated`, 4 messages (153/153/152/104
  bits; fits 12.7986/12.8002/12.8004/12.8018; 4 regions; 1008 decoder calls;
  budget not hit) in ~1.4 s.
- Edge cases probed: clean uniform → Direct/strict; print-quantized →
  Reconstruct/strict; reset-concatenated → Reconstruct/strict (pre-existing
  `prepare_time_axis` semantics + warning banner intact at `app.py:1423`);
  single/all-identical timestamps → clear `ValueError` from prepare (main
  guards `len<2`; all-identical previously errored later with a different
  message — degenerate input, no action needed); NaN → guarded before
  quality; empty → pre-existing `IndexError` in quality, unreachable via
  `len<2` guard; `helper(None)`/non-dict → safe Direct default.
- No hidden cost: the quality call was moved, not duplicated; no new array
  copies; radio default is deterministic; figure-cache `revision` still
  includes the mode; export still carries both time axes; user override of
  either mode is fully retained.
- Tests: the 6 existing helper tests were judged contract-level but real;
  one end-to-end regression test was ADDED
  (`test_print_quantized_grid_default_axis_is_strictly_increasing`): a
  print-quantized uniform grid must route to reconstruction AND be accepted
  by `prepare_time_axis` with preserved length/endpoints and strict
  monotonicity. Suite: 25 passed / 0 failed. `py_compile` and
  `git diff --check` clean.
- Patch classification: READY FOR DEPLOYMENT from a code-verification
  standpoint (release itself remains a human decision). No correction to the
  patch logic was required; only the one regression test was added.
- `decode_waveform()` NOT modified. No acceptance criteria, timing
  tolerances, coverage rules, rejection logic, budgets, or filename-specific
  handling added or changed. Nothing committed, pushed, tagged, or released.

## Change Control

This document is intentionally an investigation artifact. Any future code
change must state:

1. The measured root cause.
2. Why the change is upstream of or separate from the legacy decoder, if
   applicable.
3. The tests or diagnostics that demonstrate the fix.
4. Confirmation that the known validated captures and rejection criteria remain
   intact.

Do not turn this document into release notes. Keep release actions and release
verification separate from this investigation log.
