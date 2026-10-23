#!/usr/bin/env python3
"""
Lufträume Deutschland für Flulino.

Lädt die Luftraumdaten von open flightmaps (OFMA, OpenAir-Format) für den aktuellen
AIRAC-Zyklus, wandelt sie in das kompakte Flulino-Format um und schreibt sie nach
data/airspaces-de.json. Läuft automatisch als GitHub Action (siehe .github/workflows).

Quelle: © open flightmaps association (OFMA), OFMA General Users License.
Die Daten werden nur umgewandelt (Format), inhaltlich nicht verändert.

Ausgabe-Format je Luftraum (wie in der App):
  [Name, Typ, ICAO-Klasse, untere Grenze, obere Grenze, untere in ft, [lon,lat,lon,lat,…]]
  Typ  (wie openAIP): 1 ED-R, 2 ED-D, 3 ED-P, 4 CTR, 5 TMZ, 6 RMZ, 7 TMA, 8 TRA, 9 TSA,
                      13 ATZ, 21 Segelflug, 26 CTA, 0 sonst
  Klasse: 0..6 = A..G, 8 = keine
Nur Pythons Standardbibliothek, keine Zusatzpakete.
"""
import io
import json
import math
import os
import re
import sys
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'airspaces-de.json')
BASE = 'https://snapshots.openflightmaps.org/live/{airac}/openair/{folder}/latest/openair_{cc}.zip'
# Ordnernamen für Deutschland bei open flightmaps (wird der Reihe nach probiert; mehrere Treffer werden zusammengeführt)
FOLDERS = os.environ.get('OFM_FOLDERS', 'ed,edww,edgg,edmm,eduu').split(',')
CC = os.environ.get('OFM_CC', 'ed')
UA = 'Flulino airspace updater (https://flulino.de)'

# ---------------------------------------------------------------- AIRAC
REF = date(2024, 1, 25)  # AIRAC 2401


def airac_for(d: date):
    """AIRAC-Zyklus (z. B. '2611') und Startdatum für ein Datum."""
    n = (d - REF).days // 28
    start = REF + timedelta(days=28 * n)
    first = start
    while (first - timedelta(days=28)).year == start.year:
        first -= timedelta(days=28)
    num = (start - first).days // 28 + 1
    return f'{start.year % 100:02d}{num:02d}', start


# ---------------------------------------------------------------- Download
def fetch(url: str):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except Exception as e:  # noqa: BLE001
        print(f'  – {url}  ({e})')
        return None


def openair_texts(data: bytes):
    texts = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if name.lower().endswith(('.txt', '.air', '.openair')) or 'openair' in name.lower():
                raw = z.read(name)
                for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
                    try:
                        texts.append(raw.decode(enc)); break
                    except UnicodeDecodeError:
                        continue
    return texts


# ---------------------------------------------------------------- OpenAir
COORD = re.compile(
    r'(\d{1,2})[:\s](\d{1,2}(?:\.\d+)?)(?:[:\s](\d{1,2}(?:\.\d+)?))?\s*([NS])\s*[,]?\s*'
    r'(\d{1,3})[:\s](\d{1,2}(?:\.\d+)?)(?:[:\s](\d{1,2}(?:\.\d+)?))?\s*([EW])', re.I)
NM = 1852.0
R_EARTH = 6371008.8


def parse_coord(s: str):
    m = COORD.search(s)
    if not m:
        return None
    la = float(m.group(1)) + float(m.group(2)) / 60 + (float(m.group(3)) / 3600 if m.group(3) else 0)
    lo = float(m.group(5)) + float(m.group(6)) / 60 + (float(m.group(7)) / 3600 if m.group(7) else 0)
    if m.group(4).upper() == 'S': la = -la
    if m.group(8).upper() == 'W': lo = -lo
    return la, lo


def dest(la, lo, brg_deg, dist_m):
    """Punkt in Entfernung/Richtung (Großkreis)."""
    d = dist_m / R_EARTH
    b = math.radians(brg_deg)
    p1, l1 = math.radians(la), math.radians(lo)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), (math.degrees(l2) + 540) % 360 - 180


def bearing_dist(la1, lo1, la2, lo2):
    p1, p2 = math.radians(la1), math.radians(la2)
    dl = math.radians(lo2 - lo1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    brg = (math.degrees(math.atan2(y, x)) + 360) % 360
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return brg, 2 * R_EARTH * math.asin(math.sqrt(a))


def arc(center, r_m, a1, a2, cw, step=4.0):
    pts = []
    if cw:
        sweep = (a2 - a1) % 360 or 360
        n = max(2, int(sweep / step))
        for k in range(n + 1): pts.append(dest(*center, a1 + sweep * k / n, r_m))
    else:
        sweep = (a1 - a2) % 360 or 360
        n = max(2, int(sweep / step))
        for k in range(n + 1): pts.append(dest(*center, a1 - sweep * k / n, r_m))
    return pts


def parse_limit(s: str):
    """→ (Anzeige, Fuß über MSL ungefähr)"""
    t = (s or '').strip().upper()
    if not t or t in ('GND', 'SFC', '0', '0 GND', '0FT GND', '0 FT GND', '0FT AGL'):
        return 'GND', 0
    if t.startswith(('UNL', 'UNLTD', 'UNLIM')):
        return 'UNL', 99999
    m = re.search(r'FL\s*(\d+)', t)
    if m:
        v = int(m.group(1)); return f'FL {v:02d}', v * 100
    m = re.search(r'(\d+(?:\.\d+)?)(?![\d.])\s*(?:(FT|F|M)(?![A-Z]))?\s*(AMSL|MSL|AGL|GND|SFC|STD|ASFC)?', t)
    if not m:
        return t, 0
    v = float(m.group(1)); unit = (m.group(2) or 'FT').upper(); ref = (m.group(3) or 'MSL').upper()
    ft = v * 3.2808 if unit == 'M' else v
    vtxt = f'{int(round(v))} m' if unit == 'M' else f'{int(round(v))} ft'
    if ref in ('AGL', 'GND', 'SFC', 'ASFC'):
        return (f'{vtxt} GND' if v else 'GND'), int(round(ft))
    return f'{vtxt} {"STD" if ref == "STD" else "MSL"}', int(round(ft))


CLASS = {c: i for i, c in enumerate('ABCDEFG')}
TYPE_BY_KEY = {
    'R': 1, 'RESTRICTED': 1, 'Q': 2, 'DANGER': 2, 'P': 3, 'PROHIBITED': 3,
    'CTR': 4, 'TMZ': 5, 'RMZ': 6, 'TMA': 7, 'TRA': 8, 'TSA': 9, 'ATZ': 13, 'HTZ': 20,
    'GP': 21, 'GLIDING': 21, 'GLIDING_SECTOR': 21, 'W': 21, 'WAVE': 21, 'CTA': 26,
}
SKIP_KEYS = {'FIR', 'UIR', 'FIS', 'AWY', 'ADIZ', 'OTH_FIR', 'ACC', 'UTA', 'LTA', 'SECTOR'}


def classify(ac: str, ay: str, name: str):
    ac = (ac or '').strip().upper(); ay = (ay or '').strip().upper().replace(' ', '_'); n = name.upper()
    if ac in SKIP_KEYS or ay in SKIP_KEYS or re.search(r'\bFIR\b|\bUIR\b|\bFIS\b', n):
        return None
    cls = CLASS.get(ac, 8)
    typ = TYPE_BY_KEY.get(ay) or (TYPE_BY_KEY.get(ac) if ac not in CLASS else 0) or 0
    if not typ:
        for key, t in (('CTR', 4), ('TMZ', 5), ('RMZ', 6), ('ATZ', 13), ('TMA', 7), ('CTA', 26),
                       ('ED-R', 1), ('ED-D', 2), ('ED-P', 3), ('TRA', 8), ('TSA', 9)):
            if re.search(r'(^|[^A-Z])' + re.escape(key) + r'([^A-Z]|$)', n):
                typ = t; break
        if not typ and re.search(r'SEGELF|GLIDER|GLD|WAVE', n):
            typ = 21
    if cls == 8 and ac in CLASS:
        cls = CLASS[ac]
    return typ, cls


def parse_openair(text: str):
    out = []
    cur = None
    center = None
    cw = True

    def finish():
        if cur and len(cur['pts']) >= 3:
            out.append(cur)

    for raw in text.splitlines():
        line = raw.split('*', 1)[0].strip() if not raw.strip().startswith('*') else ''
        if not line:
            continue
        key, _, rest = line.partition(' ')
        key = key.upper(); rest = rest.strip()
        if key == 'AC':
            finish()
            cur = {'ac': rest, 'ay': '', 'name': '', 'ah': '', 'al': '', 'pts': []}
            center = None; cw = True
        elif cur is None:
            continue
        elif key == 'AY': cur['ay'] = rest
        elif key == 'AN': cur['name'] = rest
        elif key == 'AH': cur['ah'] = rest
        elif key == 'AL': cur['al'] = rest
        elif key == 'V':
            k, _, v = rest.partition('=')
            k = k.strip().upper(); v = v.strip()
            if k == 'X': center = parse_coord(v)
            elif k == 'D': cw = not v.startswith('-')
        elif key == 'DP':
            c = parse_coord(rest)
            if c: cur['pts'].append(c)
        elif key == 'DC' and center:
            r = float(rest.replace(',', '.').split()[0]) * NM
            cur['pts'].extend(arc(center, r, 0, 360, True, step=6.0)[:-1])
        elif key == 'DA' and center:
            parts = [p.strip() for p in rest.split(',')]
            if len(parts) >= 3:
                r, a1, a2 = (float(p) for p in parts[:3])
                cur['pts'].extend(arc(center, r * NM, a1, a2, cw))
        elif key == 'DB' and center:
            ms = list(COORD.finditer(rest))
            if len(ms) >= 2:
                p1 = parse_coord(ms[0].group(0)); p2 = parse_coord(ms[1].group(0))
                b1, d1 = bearing_dist(*center, *p1)
                b2, _ = bearing_dist(*center, *p2)
                pts = arc(center, d1, b1, b2, cw)
                pts[0] = p1; pts[-1] = p2
                cur['pts'].extend(pts)
    finish()
    return out


def to_zone(a):
    cl = classify(a['ac'], a['ay'], a['name'])
    if cl is None:
        return None
    typ, cls = cl
    low_txt, low_ft = parse_limit(a['al'])
    up_txt, _ = parse_limit(a['ah'])
    if low_ft >= 10000:  # nur was für VFR interessant ist (unter FL 100)
        return None
    if cls == 6 and not typ:  # Luftraum G nicht zeichnen
        return None
    flat, prev = [], None
    for la, lo in a['pts']:
        p = (round(lo, 4), round(la, 4))
        if p == prev: continue
        flat.extend(p); prev = p
    if len(flat) >= 4 and flat[0] == flat[-2] and flat[1] == flat[-1]:
        flat = flat[:-2]
    if len(flat) < 6:
        return None
    xs, ys = flat[0::2], flat[1::2]
    if cls == 4 and not typ and (max(xs) - min(xs)) * (max(ys) - min(ys)) > 4:
        return None  # flächendeckendes E (über ganz Deutschland) nicht zeichnen
    return [a['name'] or '?', typ, cls, low_txt, up_txt, low_ft, flat]


# ---------------------------------------------------------------- Hauptprogramm
def main():
    today = datetime.now(timezone.utc).date()
    zones, seen, used = [], set(), []
    for d in (today, today - timedelta(days=28)):
        airac, start = airac_for(d)
        print(f'AIRAC {airac} (gültig ab {start})')
        for folder in FOLDERS:
            url = BASE.format(airac=airac, folder=folder.strip(), cc=CC)
            data = fetch(url)
            if not data:
                continue
            try:
                texts = openair_texts(data)
            except zipfile.BadZipFile:
                print(f'  – {url}  (keine ZIP-Datei)'); continue
            n0 = len(zones)
            for t in texts:
                for a in parse_openair(t):
                    z = to_zone(a)
                    if not z: continue
                    k = (z[0], z[3], z[4], z[6][0], z[6][1])
                    if k in seen: continue
                    seen.add(k); zones.append(z)
            print(f'  ✓ {url}  → {len(zones) - n0} Lufträume')
            used.append(url)
        if zones:
            break
    if not zones:
        print('FEHLER: Keine Luftraumdaten gefunden. Bestehende Datei bleibt unverändert.')
        sys.exit(1)
    zones.sort(key=lambda z: (z[1], z[0]))
    doc = {
        'format': 'flulino-airspaces', 'version': 1, 'airac': airac, 'validFrom': start.isoformat(),
        'source': '© open flightmaps association (OFMA), OFMA General Users License',
        'generatedAt': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'zones': zones,
    }
    old = None
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding='utf-8') as f: old = json.load(f)
        except Exception:  # noqa: BLE001
            old = None
    if old and old.get('airac') == doc['airac'] and old.get('zones') == doc['zones']:
        print('Keine Änderung.')
        return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print(f'Gespeichert: {len(zones)} Lufträume, AIRAC {airac}, {os.path.getsize(OUT) // 1024} KB')


if __name__ == '__main__':
    main()
