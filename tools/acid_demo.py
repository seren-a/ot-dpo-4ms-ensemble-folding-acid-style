"""Acid demo: the voice (Warp sweep + 2 subs) through OCTA303's TB-303 filter, 'faithful' vs 'os2'.

    python3 tools/acid_demo.py      # writes renders/acid_*.wav
"""
import os, sys
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'model'))
import voice as V
import acid as A

OUT = os.path.join(os.path.dirname(__file__), '..', 'renders')

# (semitones rel. C3, accent, slide); C2 = -12, C1 = -24
BAR = [(-24, 0, 0), (-12, 1, 0), (-24, 0, 0), (-21, 0, 1), (None, 0, 0), (-24, 0, 0), (-17, 1, 0), (-19, 0, 1),
       (-24, 0, 0), (-24, 0, 0), (-12, 1, 1), (-14, 0, 1), (None, 0, 0), (-21, 1, 0), (-24, 0, 0), (-22, 0, 1)]
PATTERN = BAR * 4

PATCHES = {
    # name: (warp mode, twist mode, twist knob, sub1, sub2, cut, res, env, dec)
    'fold': ('fold', 'feedback', 0.0, 0.5, 0.3, 45, 100, 70, 45),
    'cheby': ('cheby', 'feedback', 0.0, 0.5, 0.3, 50, 95, 65, 45),
    'fold_pulsar': ('fold', 'pulsar', 0.45, 0.6, 0.0, 55, 90, 60, 50),
}


def voice_fn(warp_mode, twist_mode, twist_knob, sub1, sub2, engine):
    def f(hz):
        n = len(hz)
        t = np.arange(n) / V.FS
        knob = 0.5 - 0.5 * np.cos(2 * np.pi * t / (n / V.FS))     # warp 0 -> 100 % -> 0 over the take
        main = V.render_osc(hz, twist_mode, twist_knob, warp_mode, knob, engine=engine, n=n)
        s1, s2 = V.render_subs(hz, n, 'sine')
        return (main + sub1 * s1 + sub2 * s2) / (1 + sub1 + sub2)
    return f


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for name, (wm, tm, tk, s1, s2, cut, res, env, dec) in PATCHES.items():
        ys = {}
        for e in ['faithful', 'os2']:
            ys[e] = A.render_acid(PATTERN, voice_fn(wm, tm, tk, s1, s2, e), cut=cut, res=res, env=env, dec=dec)
        g = 0.89 / max(np.abs(ys['faithful']).max(), np.abs(ys['os2']).max())
        for e, y in ys.items():
            sf.write(os.path.join(OUT, 'acid_%s_%s.wav' % (name, e)), y * g, 44100, subtype='PCM_24')
        print(name, 'done')
