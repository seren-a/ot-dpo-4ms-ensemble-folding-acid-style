# Third-party code

## 4ms Ensemble Oscillator (github.com/4ms/enosc)

Ported algorithms and table generation in `model/tables.py` and `model/voice.py` (Twist, Warp, knob laws, anti-aliasing laws).

```
Ensemble Oscillator source code is
Copyright (c) 2020, Matthias Puech and Dan Green

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

```

## OCTA303 (github.com/braikomarko-hub/acidtrack-modules, in sambanks/octabam)

Not copied. `model/acid.py` imports `tools/octa303/ref303.py` from an octabam checkout and replaces only its oscillator lines at import time. MIT License, Copyright (c) 2026 Marko Brajković.

## octabam (github.com/sambanks/octabam)

MIT License, Copyright (c) 2026 Sam Banks. Target build system for the ColdFire module (planned).
