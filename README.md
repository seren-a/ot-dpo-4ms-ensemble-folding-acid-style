# ot-dpo-4ms-ensemble-folding-acid-style

A complex-oscillator bass voice for the Elektron Octatrack MKII (OS 1.40C, via
[octabam](https://github.com/sambanks/octabam) / Modwerk): an Ensemble-Oscillator-style sine
oscillator with Twist (FEEDBACK, PULSAR, CRUSH) and Warp (FOLD, CHEB, SEGMENT), two
sub-oscillators (−1 / −2 octaves, kept out of the folder), into a TB-303 diode ladder.

**Status: reference model only (Python).** No firmware code yet. Nothing here touches an
Octatrack.

## Layout

| Path | What |
|---|---|
| `model/tables.py` | EnOsc's tables (sine, Chebyshev, fold, fold gain, triangles), generated as on EnOsc |
| `model/voice.py` | The voice: Twist/Warp per EnOsc, 2 locked subs, engines `faithful` (44.1 kHz, EnOsc as is) and `os2` (2× + half-band decimator) |
| `model/acid.py` | The voice into OCTA303's TB-303 filter (imported from an octabam checkout, not copied) |
| `tools/alias_tests.py` | Alias measurements (A-weighted) + listening sweeps + spectrograms |
| `tools/precision_tests.py` | What limits each mode: oversampling vs. table size / bit depth |
| `tools/acid_demo.py` | A 4-bar acid pattern, `faithful` vs `os2` |
| `docs/BEFUNDE.md` | Findings and the plan for the ColdFire module (German) |

## Run

```sh
pip install -r requirements.txt
git clone --depth 1 https://github.com/sambanks/octabam ../octabam   # for acid.py (or set OCTABAM=)
python3 tools/alias_tests.py
python3 tools/precision_tests.py
python3 tools/acid_demo.py
```

WAVs land in `renders/` (not committed; tables and spectrograms are).

## Credits

Algorithms after the 4ms Ensemble Oscillator by Matthias Puech and Dan Green (BSD-style),
filter by OCTA303 by Marko Brajković (MIT), target platform octabam by Sam Banks (MIT).
See `THIRD_PARTY.md`.
