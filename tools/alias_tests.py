"""Alias measurements and listening renders: 'faithful' (EnOsc as is, 44.1 kHz) vs 'os2'.

    python3 tools/alias_tests.py            # writes renders/ and renders/alias_table.md
"""
import os, sys
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import signal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'model'))
import voice as V

OUT = os.path.join(os.path.dirname(__file__), '..', 'renders')
FS = V.FS
# A1, A2, G#3, G#4. Not 200/400 Hz: 44100/200 and 88200/200 are (half-)integers, so aliases would
# land exactly on harmonics and hide from the measurement.
NOTES = [55.0, 110.0, 207.65, 415.30]
ENGINES = ['faithful', 'os2']

# (label, twist mode, twist knob, warp mode, warp knob)
CASES = [
    ('FOLD 50 %', 'feedback', 0.0, 'fold', 0.5),
    ('FOLD 100 %', 'feedback', 0.0, 'fold', 1.0),
    ('CHEB 50 %', 'feedback', 0.0, 'cheby', 0.5),
    ('CHEB 100 %', 'feedback', 0.0, 'cheby', 1.0),
    ('SEGMENT 100 %', 'feedback', 0.0, 'segment', 1.0),
    ('PULSAR 70 %', 'pulsar', 0.7, 'fold', 0.0),
    ('CRUSH 70 %', 'crush', 0.7, 'fold', 0.0),
    ('FEEDBACK 100 % + FOLD 70 %', 'feedback', 1.0, 'fold', 0.7),
]


def a_weight_db(f):
    f = np.maximum(f, 1e-3)
    ra = (12194 ** 2 * f ** 4) / ((f ** 2 + 20.6 ** 2) * np.sqrt((f ** 2 + 107.7 ** 2) * (f ** 2 + 737.9 ** 2))
                                  * (f ** 2 + 12194 ** 2))
    return 20 * np.log10(ra) + 2.0


def alias_metrics(y, f0):
    """A-weighted alias-to-harmonic ratio (20 Hz..16 kHz: above that the decimators transition band
    folds back on purpose, and the ear barely follows) and the loudest single alias component
    in 500 Hz..6 kHz relative to the loudest harmonic, both in dB."""
    N = 1 << 15
    seg = y[int(0.2 * FS):int(0.2 * FS) + N]
    w = signal.windows.blackmanharris(N)
    X = np.abs(np.fft.rfft(seg * w)) ** 2
    f = np.fft.rfftfreq(N, 1 / FS)
    binw = FS / N
    harm = np.zeros_like(X, dtype=bool)
    for k in range(1, int(FS / 2 / f0) + 1):
        c = k * f0 / binw
        harm[max(0, int(c) - 5):int(c) + 6] = True
    harm[:int(15 / binw)] = True                            # DC region does not count
    band = (f >= 20) & (f <= 16000)
    aw = 10 ** (a_weight_db(f) / 10)
    p_h = np.sum((X * aw)[harm & band]) + 1e-30
    p_a = np.sum((X * aw)[~harm & band]) + 1e-30
    mid = (f >= 500) & (f <= 6000) & ~harm
    loud_a = np.max(X[mid]) if mid.any() else 1e-30
    loud_h = np.max(X[harm & band])
    return 10 * np.log10(p_a / p_h), 10 * np.log10(loud_a / loud_h + 1e-30)


def table():
    rows = []
    for label, tm, tk, wm, wk in CASES:
        for f0 in NOTES:
            r = [label, '%.0f Hz' % f0]
            for e in ENGINES:
                y = V.render_osc(f0, tm, tk, wm, wk, engine=e, seconds=1.2)
                a, m = alias_metrics(y, f0)
                r += ['%.1f' % a, '%.1f' % m]
            rows.append(r)
    hdr = ('| Fall | Note | treu: Alias A-bew. | treu: lautester Alias 0,5–6 kHz | os2: Alias A-bew. '
           '| os2: lautester Alias 0,5–6 kHz |\n|---|---|---|---|---|---|\n')
    md = hdr + '\n'.join('| ' + ' | '.join(r) + ' |' for r in rows) + '\n'
    open(os.path.join(OUT, 'alias_table.md'), 'w').write(md)
    return md


def sweep(n):
    """warp knob 0 -> 1 -> 0 over n samples (raised-cosine)."""
    return 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)


def renders():
    n = int(8 * FS)
    knob = sweep(n)
    for wm in ['fold', 'cheby']:
        for f0 in NOTES:
            fig, axs = plt.subplots(1, 2, figsize=(12, 4), sharey=True)
            for ax, e in zip(axs, ENGINES):
                y = V.render_osc(f0, 'feedback', 0.0, wm, knob, engine=e, n=n)
                y = 0.5 * y
                fade = np.minimum(1, np.minimum(np.arange(n), n - 1 - np.arange(n)) / 441)
                y *= fade
                sf.write(os.path.join(OUT, '%s_%03dHz_%s.wav' % (wm, int(f0), e)), y, int(FS), subtype='PCM_24')
                f, t, S = signal.spectrogram(y, FS, window='blackmanharris', nperseg=4096, noverlap=3072)
                ax.pcolormesh(t, f, 10 * np.log10(S + 1e-14), vmin=-130, vmax=-30, shading='auto', cmap='magma')
                ax.set_title('%s %g Hz – %s' % (wm.upper(), f0, 'treu (EnOsc, 44,1 kHz)' if e == 'faithful' else '2× Oversampling'))
                ax.set_xlabel('Zeit (s) – Warp 0 → 100 % → 0')
                ax.set_ylim(0, 22050)
            axs[0].set_ylabel('Hz')
            fig.tight_layout()
            fig.savefig(os.path.join(OUT, 'spec_%s_%03dHz.png' % (wm, int(f0))), dpi=80)
            plt.close(fig)


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    print(table())
    renders()
    print('renders done')
