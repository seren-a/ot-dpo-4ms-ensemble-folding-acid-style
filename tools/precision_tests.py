"""What limits each mode: oversampling factor, or table size / bit depth?

    python3 tools/precision_tests.py     # writes renders/precision.md

1. Oversampling ladder 1x..16x (ideal polyphase decimation) per mode: if the alias floor keeps
   falling ~6 dB per doubling, the mode has hard edges (only more oversampling or edge correction
   helps); if it stops, something else (tables, precision) is the floor.
2. CHEB computed directly (Chebyshev recurrence instead of EnOsc's 513-point tables), with the
   sine at 16 / 24 bit and 512 / 2048 / 4096 table points.
"""
import os, sys
import numpy as np
from numba import njit
from scipy import signal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'model'))
sys.path.insert(0, os.path.dirname(__file__))
import voice as V
from alias_tests import alias_metrics

OUT = os.path.join(os.path.dirname(__file__), '..', 'renders')
FS = 44100.0
N = int(1.2 * FS)


def os_render(f0, tm, tk, wm, wk, k):
    tw = float(V.aa_twist(tm, f0 / FS, float(V.twist_law(tm, tk))))
    wa = float(V.aa_warp(wm, f0 / FS, float(V.warp_law(wm, wk))))
    inc = np.full(N * k, int(round(f0 / (FS * k) * 2 ** 32)), dtype=np.int64)
    y = V.osc_kernel(inc, V.TWIST_MODES[tm], np.full(N * k, tw), V.WARP_MODES[wm], np.full(N * k, wa),
                     V.CHEBY, V.FOLD_V, V.FOLD_D, V.FOLD_MAX, V.TRI)
    return signal.resample_poly(y, 1, k, window=('kaiser', 12)) if k > 1 else y


@njit(cache=True)
def cheb_direct(inc, amount, bits, tabsize):
    n = inc.shape[0]
    out = np.zeros(n)
    acc = 0
    a = amount * 14
    idx = int(a)
    fr = a - idx
    sc = 2.0 ** (bits - 1) - 1
    for i in range(n):
        acc = (acc + inc[i]) & 0xFFFFFFFF
        p = acc / 4294967296.0 * tabsize
        j = int(p)
        f = p - j
        s0 = np.round(np.sin(2 * np.pi * j / tabsize) * sc)
        s1 = np.round(np.sin(2 * np.pi * (j + 1) / tabsize) * sc)
        x = np.round(s0 + (s1 - s0) * f) / sc
        tm, tn = 1.0, x                                   # T0, T1
        for _ in range(idx):
            tm, tn = tn, 2 * x * tn - tm
        out[i] = tn + (2 * x * tn - tm - tn) * fr
    return out


CASES = [('FOLD 100 %', 'feedback', 0.0, 'fold', 1.0), ('CHEB 100 %', 'feedback', 0.0, 'cheby', 1.0),
         ('PULSAR 70 %', 'pulsar', 0.7, 'fold', 0.0), ('CRUSH 70 %', 'crush', 0.7, 'fold', 0.0),
         ('FEEDBACK 100 % + FOLD 70 %', 'feedback', 1.0, 'fold', 0.7)]

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    md = ['## 1. Oversampling-Leiter (Alias A-bewertet, dB, 20 Hz–16 kHz)\n',
          '| Fall | Note | 1× | 2× | 4× | 8× | 16× |', '|---|---|---|---|---|---|---|']
    for label, tm, tk, wm, wk in CASES:
        for f0 in (110.0, 415.30):
            r = [alias_metrics(os_render(f0, tm, tk, wm, wk, k), f0)[0] for k in (1, 2, 4, 8, 16)]
            md.append('| %s | %.0f Hz | %s |' % (label, f0, ' | '.join('%.1f' % v for v in r)))
    md += ['\n## 2. CHEB direkt berechnet (Rekursion statt Tabellen), 1×\n',
           '| Note | EnOsc-Tabellen | 16 bit / 512 | 24 bit / 512 | 24 bit / 2048 | 24 bit / 4096 |',
           '|---|---|---|---|---|---|']
    for f0 in (55.0, 110.0, 207.65, 415.30):
        inc = np.full(N, int(round(f0 / FS * 2 ** 32)), dtype=np.int64)
        am = float(V.aa_warp('cheby', f0 / FS, 1.0))
        r = [alias_metrics(V.render_osc(f0, 'feedback', 0, 'cheby', 1.0, n=N), f0)[0]]
        r += [alias_metrics(cheb_direct(inc, am, b, t), f0)[0] for b, t in ((16, 512), (24, 512), (24, 2048), (24, 4096))]
        md.append('| %.0f Hz | %s |' % (f0, ' | '.join('%.1f' % v for v in r)))
    text = '\n'.join(md) + '\n'
    open(os.path.join(OUT, 'precision.md'), 'w').write(text)
    print(text)
