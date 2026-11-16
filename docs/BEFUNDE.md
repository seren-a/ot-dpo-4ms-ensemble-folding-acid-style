# Befunde: Referenzmodell v0 (17.11.2026)

Ziel: eine Stimme für die OT MKII. Sinus-Oszillator mit Twist/Warp nach dem 4ms Ensemble Oscillator,
zwei Subs (−1/−2 Oktaven, am Folder vorbei), danach die 303-Ladder von OCTA-303. Synth-Maschinen
laufen bei octabam auf dem **ColdFire** (Integer, im FLEX-Renderer), nicht auf dem DSP.

Alle Zahlen: Alias-Anteil A-bewertet relativ zu den Harmonischen, 20 Hz–16 kHz, in dB (je negativer,
desto sauberer). Testnoten A1, A2, G#3, G#4. Nicht 200/400 Hz, weil bei 44 100/200 die Aliase genau auf
Harmonischen landen und sich vor der Messung verstecken würden. Reproduzierbar mit `tools/alias_tests.py`
und `tools/precision_tests.py`.

## 1. EnOsc „treu“ aliast bei höheren Noten deutlich – vor allem FOLD

| | 55 Hz | 110 Hz | 208 Hz | 415 Hz |
|---|---|---|---|---|
| FOLD 100 %, treu (44,1 kHz) | −70 | −58 | −43 | **−28** |
| FOLD 100 %, 2× | −77 | −77 | −68 | −56 |
| FOLD 100 %, 4× | | −80 | | −78 |

EnOsc hat kein Oversampling. Es nimmt nur die Stärke mit der Tonhöhe zurück, und im Bassbereich greift
das kaum. Im Sub- und Bassbereich (≤ 110 Hz) ist FOLD auch treu noch sauber. Ab etwa 200 Hz hört man es:
Das ist genau der Bereich, den du angesprochen hast. 2× bringt 19–28 dB, 4× bei 415 Hz noch einmal 22 dB.

## 2. CHEB: Begrenzt wird es von der Präzision, nicht vom Oversampling

Das hattest du vermutet, und es stimmt. EnOsc legt die Chebyshev-Polynome als Tabellen mit 513 Punkten
ab und liest sie linear interpoliert. Die Knicke der Interpolation erzeugen Obertöne über Nyquist, und
die 16-Bit-Sinustabelle davor wird von T16 um bis zu 48 dB verstärkt. Mit Oversampling kommt man
deshalb kaum weiter (−54 → −58 bei 2×).

Rechnet man die Polynome stattdessen direkt per Rekursion (T(n+1) = 2x·T(n) − T(n−1), auf dem ColdFire
etwa 16 Multiplikationen):

| | EnOsc-Tabellen | 16 bit / 512 | 24 bit / 512 | **24 bit / 2048** |
|---|---|---|---|---|
| 110 Hz | −60 | −66 | −72 | **−91** |
| 415 Hz | −54 | −64 | −69 | **−91** |

Mit einer 24-Bit-Sinustabelle mit 2048 Punkten ist CHEB **ohne** Oversampling sauber. Bei 16 Bit ist
bei etwa −65 dB Schluss, egal wie groß die Tabelle ist.

## 3. CRUSH und starkes FEEDBACK: harte Kanten, nur 6 dB pro Verdopplung

| | 1× | 2× | 4× | 8× | 16× |
|---|---|---|---|---|---|
| CRUSH 70 %, 110 Hz | −21 | −27 | −33 | −39 | −45 |
| FEEDBACK 100 % + FOLD 70 %, 110 Hz | −20 | −26 | −32 | −39 | −45 |

Das ist echtes Aliasing (jede Verdopplung bringt 6 dB, typisch für Sprünge in der Wellenform) und es
gehört zum Klang des Ensemble Oscillators. Mit vertretbarem Oversampling wird das nicht sauber. Möglich
wären: so lassen („treu“), den Regelbereich mit der Tonhöhe stärker begrenzen, oder die Sprünge per
BLEP glätten. Das ist aufwendig und noch nicht untersucht. **Das musst du entscheiden.**

## 4. PULSAR und SEGMENT: 2× bringt 12–13 dB

PULSAR 70 % bei 415 Hz: −47 (treu) → −60 (2×) → −72 (4×).

## 5. Folgerungen für das ColdFire-Modul

- Oszillator, Twist und FOLD/SEGMENT/PULSAR mit **2× intern**, danach ein Halfband-Filter (55 Taps,
  davon 29 nicht null, also etwa 15 Multiplikationen pro Ausgangssample dank Symmetrie). 4× nur, wenn das
  Budget reicht, am ehesten für FOLD ab etwa 200 Hz.
- **CHEB per Rekursion** auf einem **24-Bit-Sinus mit 2048 Punkten**, bei 1×. Die 16 Chebyshev-Tabellen
  von EnOsc (8208 Worte) entfallen.
- Subs: Sinus aus derselben Tabelle, Rechteck mit PolyBLEP, gekoppelt über einen 34-Bit-Phasenakku.
  Damit kann ein Sub nie gegen den Hauptoszillator driften.
- Schalter **TREU / SAUBER**, damit du A/B auf dem Gerät hören kannst.
- Der Filter kommt unverändert von OCTA-303.
- Speicher: EnOsc-Tabellen insgesamt etwa 11 900 Worte. Meine frühere Schätzung von „etwa 6000“ war zu
  niedrig. Ohne die Cheby-Tabellen sind es etwa 3700, dazu kommt der 2048er-Sinus.
- Die Kosten auf dem ColdFire sind **noch nicht gemessen**. Zum Vergleich: OCTA-303 schätzt etwa 6 %
  pro Stimme, CX OSC hat auf einer MKII sechs Stimmen als Maximum. Gemessen wird mit CF METER /
  LOAD METER im Emulator (octa-panel), dann auf dem Gerät.

## 6. Anhören (`renders/`)

- `fold_*Hz_{faithful,os2}.wav`, `cheby_*`: Warp 0 → 100 % → 0 über 8 s, ohne Filter.
- `acid_{fold,cheby,fold_pulsar}_{faithful,os2}.wav`: vier Takte Acid, Warp-Sweep, Subs, OCTA-303-Filter.
  Beide Versionen haben dieselbe Verstärkung.
- Der Klick beim Notenanschlag kommt von OCTA-303s VCA, der in 16 Samples (0,36 ms) aufmacht.
  Unser Oszillator läuft frei durch, ohne Phasen-Reset.

## Offen

1. Bit-exaktes Integer-Modell (Q-Formate wie auf dem ColdFire), dann Assembler-Port als Fork von CX OSC
   bzw. FM SYNTH im octabam-Modulformat.
2. Parameter-Belegung (6 PLAYBACK- und 6 SETUP-Regler): Vorschlag folgt, sobald 3. geklärt ist.
3. Deine Entscheidung zu CRUSH/FEEDBACK (siehe 3.).
4. Kleiner Klick, wenn FOLD bei etwa 5 % des Reglers einsetzt (in den Sweeps bei etwa 0,65 s und
   7,35 s zu sehen). Das kommt aus EnOscs eigener Logik: Unter einer Stärke von 0,005 wird der Folder
   umgangen, darüber gilt die Gain-Korrektur `fold_max` (Spitze 0,92 statt 1,0). Im Modul wird das
   übergeblendet statt umgeschaltet.
