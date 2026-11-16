"""Reference model of one OT voice: EnOsc-style sine oscillator with Twist and Warp, plus two
sub-oscillators (-1 / -2 octaves) that bypass the folder.

Twist / Warp follow 4ms/enosc `src/oscillator.hh`, `src/distortion.hh`, `src/control.hh`
(Copyright (c) 2020, Matthias Puech and Dan Green; BSD-2-Clause style, see THIRD_PARTY.md).

Number formats are the ones EnOsc itself uses: u0_32 phase, s1_15 sine table with difference
interpolation, integer Twist; Warp evaluated in float on interpolated tables (as on EnOsc).
The ColdFire module will be integer throughout; that port gets its own bit-exact reference.

Two engine modes:
- 'faithful': runs at the OT rate (44.1 kHz) with EnOsc's own anti-aliasing (amounts lowered
  with pitch), i.e. EnOsc's sound including its aliasing.
- 'os2': the oscillator + Twist + Warp run at 2x (88.2 kHz) and are decimated by a half-band
  FIR. Subs are band-limited (sine, or PolyBLEP square) and run at the base rate.
"""
import numpy as np
from numba import njit
from scipy import signal

from tables import all_tables, CHEBY_TABLES

T = all_tables()
SINE_V, SINE_D = T['sine_v'].astype(np.int64), T['sine_d'].astype(np.int64)
CHEBY = T['cheby']
FOLD_V, FOLD_D = T['fold_v'], T['fold_d']
FOLD_MAX = T['fold_max']
TRI = T['tri']

FS = 44100.0
TWIST_MODES = {'feedback': 0, 'pulsar': 1, 'crush': 2}
WARP_MODES = {'fold': 0, 'cheby': 1, 'segment': 2}
M32 = (1 << 32) - 1


# --- knob laws (enosc control.hh) -------------------------------------------------------------

def crop_down(e, x):
    x = np.asarray(x, dtype=np.float64)
    return np.where(x < e, 0.0, (x - e) / (1.0 - e))


def twist_law(mode, knob):
    t = crop_down(0.01, knob)
    if mode == 'feedback':
        return t * t * 0.7
    if mode == 'pulsar':
        return np.exp2(t * t * 6.0)            # 1..64
    return t * t * 0.5                         # crush


def warp_law(mode, knob):
    w = crop_down(0.01, knob)
    if mode == 'fold':
        return w * w * 0.9 + 0.004
    return w


# --- EnOsc anti-aliasing: amounts lowered with pitch (distortion.hh, namespace Antialias) ------

def aa_twist(mode, fn, amount):
    if mode == 'feedback':
        return amount * max(0.0, 1 - 2 * fn) ** 2
    if mode == 'pulsar':
        return (amount - 1) * max(0.0, 1 - 2 * fn) ** 16 + 1
    return amount                              # crush: none


def aa_warp(mode, fn, amount):
    if mode == 'fold':
        return np.maximum(amount * max(0.0, 1 - 8 * fn) ** 4, 0.004)
    if mode == 'cheby':
        return amount * max(0.0, 1 - 6 * fn)
    return amount * max(0.0, (1 - 4 * fn) ** 3)


# --- per-sample kernel ------------------------------------------------------------------------

@njit(cache=True)
def _sine_q15(ph):
    i = ph >> 23
    frac = ph & ((1 << 23) - 1)
    return SINE_V_[i] + ((SINE_D_[i] * frac) >> 23)


SINE_V_, SINE_D_ = SINE_V, SINE_D


@njit(cache=True)
def _twist(mode, ph, amount, lp):
    """returns (phase used for the sine, feedback amount as u0_16 or -1)"""
    if mode == 0:                                         # FEEDBACK: in the sine shaper
        fb = int(amount * 65536.0)
        if fb > 65535:
            fb = 65535
        ph = (ph + lp * fb + (fb << 16)) & 0xFFFFFFFF
        return ph
    if mode == 1:                                         # PULSAR: u0_16 * u7_9, min 1, wrap
        p = int(amount * 512.0)
        prod = (ph >> 16) * p                             # u7_25
        if prod > (1 << 25):
            prod = 1 << 25
        return ((prod & ((1 << 25) - 1)) << 7) & 0xFFFFFFFF
    am = int(amount * 65536.0)                            # CRUSH: bit games on the phase
    if am > 65535:
        am = 65535
    x = ph ^ (((ph >> 16) * am) & 0xFFFFFFFF)
    x ^= (16384 * am) & 0xFFFFFFFF
    return x & 0xFFFFFFFF


@njit(cache=True)
def _warp(mode, xq15, amount, cheby, fold_v, fold_d, fold_max, tri):
    x = xq15 / 32768.0
    if mode == 0:                                         # FOLD
        if amount <= 0.005:
            return x
        s = x * amount                                    # s1_31
        u = (s + 1.0) * 0.5                               # to_unsigned_scale, 0..1
        ph = int(u * 4294967296.0)
        if ph > 0xFFFFFFFF:
            ph = 0xFFFFFFFF
        i = ph >> 22
        frac = (ph & ((1 << 22) - 1)) / 4194304.0
        r = fold_v[i] + fold_d[i] * frac
        fi = amount * (len(fold_max) - 1)
        j = int(fi)
        if j >= len(fold_max) - 1:
            g = fold_max[len(fold_max) - 1]
        else:
            g = fold_max[j] + (fold_max[j + 1] - fold_max[j]) * (fi - j)
        return r * g
    u = (xq15 + 32768) / 65536.0                          # to_unsigned_scale
    if mode == 1:                                         # CHEBY: crossfade between orders
        a = amount * (cheby.shape[0] - 2)
        idx = int(a)
        if idx > cheby.shape[0] - 2:
            idx = cheby.shape[0] - 2
        fr = a - idx
        n = cheby.shape[1] - 1
        p = u * n
        k = int(p)
        if k >= n:
            k = n - 1
        pf = p - k
        s1 = cheby[idx, k] + (cheby[idx, k + 1] - cheby[idx, k]) * pf
        s2 = cheby[idx + 1, k] + (cheby[idx + 1, k + 1] - cheby[idx + 1, k]) * pf
        return s1 + (s2 - s1) * fr
    a = amount * (tri.shape[0] - 1)                       # SEGMENT
    idx = int(a)
    if idx > tri.shape[0] - 2:
        idx = tri.shape[0] - 2
    fr = a - idx
    n = tri.shape[1] - 1
    p = u * n
    k = int(p)
    if k >= n:
        k = n - 1
    pf = p - k
    s1 = tri[idx, k] + (tri[idx, k + 1] - tri[idx, k]) * pf
    s2 = tri[idx + 1, k] + (tri[idx + 1, k + 1] - tri[idx + 1, k]) * pf
    return s1 + (s2 - s1) * fr


@njit(cache=True)
def osc_kernel(inc, twist_mode, twist_amt, warp_mode, warp_amt, cheby, fold_v, fold_d, fold_max, tri):
    """inc: uint32 phase increments per sample (at the engine rate). Returns the Warp output."""
    n = inc.shape[0]
    out = np.zeros(n)
    acc = 0
    lp = 0
    for i in range(n):
        acc = (acc + inc[i]) & 0xFFFFFFFF
        ph = _twist(twist_mode, acc, twist_amt[i], lp)
        s = _sine_q15(ph)
        if twist_mode == 0:
            lp += (s >> 2) - (lp >> 2)                    # IOnePoleLp<s1_15, 2>
        out[i] = _warp(warp_mode, s, warp_amt[i], cheby, fold_v, fold_d, fold_max, tri)
    return out


@njit(cache=True)
def _blep(t, dt):
    if t < dt:
        t = t / dt
        return t + t - t * t - 1.0
    if t > 1.0 - dt:
        t = (t - 1.0) / dt
        return t * t + t + t + 1.0
    return 0.0


@njit(cache=True)
def sub_kernel(inc, shape):
    """Two subs locked to the main phase: one accumulator with 2 extra bits. shape 0 = sine,
    1 = PolyBLEP square. Returns (sub1, sub2) in [-1, 1]."""
    n = inc.shape[0]
    s1 = np.zeros(n)
    s2 = np.zeros(n)
    acc = 0                                               # 34-bit accumulator
    for i in range(n):
        acc = (acc + inc[i]) & ((1 << 34) - 1)
        p1 = (acc >> 1) & 0xFFFFFFFF
        p2 = (acc >> 2) & 0xFFFFFFFF
        if shape == 0:
            s1[i] = _sine_q15(p1) / 32768.0
            s2[i] = _sine_q15(p2) / 32768.0
        else:
            for k in range(2):
                p = p1 if k == 0 else p2
                d = inc[i] / (2.0 if k == 0 else 4.0) / 4294967296.0
                t = p / 4294967296.0
                v = 1.0 if t < 0.5 else -1.0
                v += _blep(t, d)
                t2 = t + 0.5
                if t2 >= 1.0:
                    t2 -= 1.0
                v -= _blep(t2, d)
                if k == 0:
                    s1[i] = v
                else:
                    s2[i] = v
    return s1, s2


# --- decimator --------------------------------------------------------------------------------

def halfband(numtaps=55, atten_db=90.0):
    """Half-band low-pass for 2x -> 1x. Passband to ~18 kHz, stopband from ~26 kHz (at 88.2 kHz)."""
    beta = signal.kaiser_beta(atten_db)
    h = signal.firwin(numtaps, 0.5, window=('kaiser', beta))
    h[np.abs(h) < 1e-12] = 0.0                            # exact zeros at even offsets
    return h


HB = halfband()


def hb_cost(h=HB):
    return int(np.count_nonzero(h))


# --- one voice --------------------------------------------------------------------------------

def inc_of_hz(hz, rate):
    return np.uint32(int(round(hz / rate * 4294967296.0)) & M32)


def render_osc(hz, twist_mode='feedback', twist_knob=0.0, warp_mode='fold', warp_knob=0.0,
               engine='faithful', n=None, seconds=2.0, enosc_aa=True):
    """Main oscillator only. hz, twist_knob, warp_knob: scalars or per-sample arrays (base rate)."""
    if n is None:
        n = int(seconds * FS)
    hz = np.broadcast_to(np.asarray(hz, dtype=np.float64), (n,))
    tk = np.broadcast_to(np.asarray(twist_knob, dtype=np.float64), (n,))
    wk = np.broadcast_to(np.asarray(warp_knob, dtype=np.float64), (n,))
    tw = twist_law(twist_mode, tk)
    wa = warp_law(warp_mode, wk)
    if enosc_aa:                                           # by pitch, relative to the OT rate
        fn = hz / FS
        tw = np.array([aa_twist(twist_mode, f, a) for f, a in zip(fn[::64], tw[::64])]).repeat(64)[:n] \
            if n > 64 else np.array([aa_twist(twist_mode, f, a) for f, a in zip(fn, tw)])
        wa = np.array([aa_warp(warp_mode, f, a) for f, a in zip(fn[::64], wa[::64])]).repeat(64)[:n] \
            if n > 64 else np.array([aa_warp(warp_mode, f, a) for f, a in zip(fn, wa)])
    k = 1 if engine == 'faithful' else 2
    rate = FS * k
    inc = (np.round(hz / rate * 4294967296.0).astype(np.int64) & M32).repeat(k)
    out = osc_kernel(inc, TWIST_MODES[twist_mode], np.repeat(tw, k), WARP_MODES[warp_mode],
                     np.repeat(wa, k), CHEBY, FOLD_V, FOLD_D, FOLD_MAX, TRI)
    if k == 2:
        # odd phase: with numtaps = 4k+3 the delay (numtaps-1)/2 is odd at 2x, so taking the odd
        # samples leaves an integer delay of (numtaps-3)/4 at the base rate
        out = signal.lfilter(HB, 1.0, out)[1::2]
        d = (len(HB) - 3) // 4
        out = np.concatenate([out[d:], np.zeros(d)])
    return out


def render_subs(hz, n, shape='sine'):
    hz = np.broadcast_to(np.asarray(hz, dtype=np.float64), (n,))
    inc = np.round(hz / FS * 4294967296.0).astype(np.int64) & M32
    return sub_kernel(inc, 0 if shape == 'sine' else 1)


def render_voice(hz, sub1=0.0, sub2=0.0, sub_shape='sine', **kw):
    main = render_osc(hz, **kw)
    s1, s2 = render_subs(hz, len(main), sub_shape)
    return main + sub1 * s1 + sub2 * s2
