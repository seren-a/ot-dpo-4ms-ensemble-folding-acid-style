"""Voice -> TB-303 filter, using OCTA303's golden reference (MIT, (c) 2026 Marko Brajkovic,
github.com/braikomarko-hub/acidtrack-modules, now in sambanks/octabam tools/octa303/ref303.py).

Nothing of ref303 is copied here: the module is imported from an octabam checkout and its
`sample()` is rewritten at import time so that the ladder's input x comes from our oscillator
instead of OCTA303's PolyBLEP saw / square. Everything after the oscillator (pre-HP, drive,
diode ladder, feedback HP, accent sweep, VCA, output stage) is OCTA303's, bit for bit.

Set OCTABAM=/path/to/octabam (default: ../octabam next to this repo, then /home/claude/ext/...).
"""
import inspect, os, sys, textwrap
import numpy as np

_CANDIDATES = [os.environ.get('OCTABAM', ''),
               os.path.join(os.path.dirname(__file__), '..', '..', 'octabam'),
               '/home/claude/ext/sambanks_octabam']
for _c in _CANDIDATES:
    if _c and os.path.exists(os.path.join(_c, 'tools', 'octa303', 'ref303.py')):
        sys.path.insert(0, os.path.join(_c, 'tools', 'octa303'))
        break
else:
    raise ImportError('octabam checkout not found: set OCTABAM')

import ref303 as R          # noqa: E402
import o3tables as T        # noqa: E402

R.CHECK = False             # range checks off for speed (the stress tests in octabam keep them on)

# --- sample() with an external oscillator --------------------------------------------------------
_src = textwrap.dedent(inspect.getsource(R.sample))
_a = _src.index('    inc = st.inc')
_b = _src.index('    st.hp += ')
_src = _src[:_a] + '    x = st.xin\n' + _src[_b:]
_src = _src.replace('def sample(st):', 'def sample_ext(st):')
_ns = dict(vars(R))
exec(_src, _ns)
sample_ext = _ns['sample_ext']
Q20 = 1 << 20               # OCTA303's oscillator full scale


def hz_of_pcur(pcur):
    return R.inc_of_p(pcur >> 8) * 44100.0 / 4294967296.0


def note_word(semi):
    """semitones relative to OCTA303's TUNE 0"""
    return 0x4000 + semi * 256


def run_pattern(pattern, cut=50, res=100, env=70, dec=40, bpm=125.0, osc=None, tail=0.5):
    """pattern: list of (semi | None, accent, slide) per 16th step.
    osc(hz_per_sample) -> float array in [-1, 1] (our voice). osc=None renders x = 0 to obtain
    the pitch trajectory. Returns (audio float, hz per sample)."""
    fs = 44100
    step = int(round(fs * 60.0 / bpm / 4))
    n = step * len(pattern) + int(tail * fs)
    st = R.Track()
    R.set_df(st, None)
    R.set_setup(st, None, None)
    st.cut, st.res, st.env, st.dec = cut, res, env, dec
    xin = None if osc is None else np.round(np.clip(osc, -1.5, 1.5) * Q20).astype(np.int64)
    hz = np.zeros(n)
    out = np.zeros(n)
    started = False
    for i in range(n):
        if i % step == 0 and i // step < len(pattern):
            semi, acc, slide = pattern[i // step]
            if semi is not None:
                w = [note_word(semi), cut << 8, res << 8, env << 8, dec << 8, (127 if acc else 0) << 8]
                st.ptgt = R.clamp(R.p_of_word(w[0]) + st.fine, T.P_LO, T.P_HI)
                if not (slide and started):
                    R.note_on(st, 0, w)
                    started = True
        st.cs -= 1
        if st.cs == 0:
            st.cs = T.CS
            R.ctrl(st)
        hz[i] = hz_of_pcur(st.pcur)
        st.xin = 0 if xin is None else int(xin[i])
        out[i] = sample_ext(st) / float(1 << (20 + 1))     # S20 + output stage gain, ~[-1, 1]
    return out, hz


def render_acid(pattern, voice_fn, **kw):
    """Two passes: the pitch trajectory first (ctrl does not depend on the audio without
    dEVILish FM), then the voice along it, then the filter."""
    _, hz = run_pattern(pattern, osc=None, **kw)
    x = voice_fn(hz)
    y, _ = run_pattern(pattern, osc=x, **kw)
    return y
