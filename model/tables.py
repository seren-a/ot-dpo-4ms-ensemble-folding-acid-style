"""Lookup tables for the voice, generated the way the 4ms Ensemble Oscillator builds them.

Ported from 4ms/enosc `src/dynamic_data.cc` and `data/data.py`.
Copyright (c) 2020, Matthias Puech and Dan Green (BSD-2-Clause style, see THIRD_PARTY.md).

Differences to the original (documented on purpose):
- sine: computed with np.sin instead of the MagicSine recursion (difference < 1 LSB of s1_15).
- fold: by default uses enosc's Math::fast_sine (parabola + 0.225 correction), as the module does.
  `FOLD_FAST_SINE=True` (the default) reproduces enosc's fast_sine.
"""
import numpy as np

SINE_SIZE = 512 + 1          # sine_size
CHEBY_TABLES = 16            # cheby_tables (T1..T16)
CHEBY_SIZE = 512 + 1         # cheby_size
FOLD_SIZE = 1024 + 1         # fold_size
FOLDS = 6.0
FOLD_FAST_SINE = True        # match enosc's Math::fast_sine


def _s1_15(x):
    """s1_15::inclusive: round to Q15, clamp to [-32767, 32767]."""
    return np.clip(np.round(np.asarray(x) * 32768.0), -32767, 32767).astype(np.int32)


def _fast_sine(p):
    """enosc Math::fast_sine for p in [0,1) cycles (faster_sine + 0.225 correction)."""
    # faster_sine: parabola through 0, 0.5, 1 (as in easiglib)
    x = p * 2.0 - 1.0                 # faster_sine: 4 (x - x|x|), x = 2p - 1
    y = 4.0 * (x - x * np.abs(x))
    return 0.225 * (y * np.abs(y) - y) + y


def sine_table():
    i = np.arange(SINE_SIZE)
    v = _s1_15(np.sin(2 * np.pi * i / (SINE_SIZE - 1)))
    d = np.zeros_like(v)
    d[:-1] = v[1:] - v[:-1]
    return v, d


def cheby_tables():
    lin = np.arange(CHEBY_SIZE) * 2.0 / (CHEBY_SIZE - 1) - 1.0
    t = np.zeros((CHEBY_TABLES, CHEBY_SIZE))
    t[0] = lin
    t[1] = 2 * lin * lin - 1
    for n in range(2, CHEBY_TABLES):
        t[n] = 2 * t[0] * t[n - 1] - t[n - 2]
    return t


def fold_table():
    out = np.zeros(FOLD_SIZE)
    for i in range(FOLD_SIZE):
        x = i / (FOLD_SIZE - 3)            # enosc: "this -3 makes the curve symmetrical"
        x = FOLDS * (2 * x - 1)
        g = 1.0 / (1.0 + abs(x))
        p = 16.0 / (2 * np.pi) * x * g
        p -= np.floor(p)
        s = _fast_sine(p) if FOLD_FAST_SINE else np.sin(2 * np.pi * p)
        out[i] = -g * (x + s)
    d = np.zeros_like(out)
    d[:-1] = out[1:] - out[:-1]
    return out, d


def fold_max_table(fold):
    start = (FOLD_SIZE - 1) // 2
    n = start + 1
    fm = np.zeros(n)
    m = 0.0
    for i in range(n):
        m = max(abs(fold[i + start]), m)
        fm[i] = 0.92 / (m + 0.00001)
    return fm


TRIANGLES_12THS = [
    [-12, -9, -6, -3, 0, 3, 6, 9, 12],
    [-12, -12, -8, -4, 0, 4, 8, 12, 12],
    [-12, -12, -12, -6, 0, 6, 12, 12, 12],
    [-12, -12, -12, -12, 0, 12, 12, 12, 12],
    [-12, -6, -12, -6, 0, 6, 12, 6, 12],
    [-12, -6, 0, -12, 0, 12, 0, 6, 12],
    [-12, -6, 12, -12, 0, 12, -12, 6, 12],
    [12, -12, 12, -12, 0, 12, -12, 12, -12],
]


def triangle_tables():
    return np.array(TRIANGLES_12THS, dtype=np.float64) / 12.0


def all_tables():
    sv, sd = sine_table()
    fv, fd = fold_table()
    return dict(sine_v=sv, sine_d=sd, cheby=cheby_tables(), fold_v=fv, fold_d=fd,
                fold_max=fold_max_table(fv), tri=triangle_tables())


def memory_words():
    """Table footprint in 32-bit words if stored as on the target (rough)."""
    t = all_tables()
    return {'sine (v+d)': 2 * SINE_SIZE, 'cheby': CHEBY_TABLES * CHEBY_SIZE,
            'fold (v+d)': 2 * FOLD_SIZE, 'fold_max': len(t['fold_max']), 'triangles': 8 * 9}


if __name__ == '__main__':
    w = memory_words()
    print(w, 'total', sum(w.values()))
