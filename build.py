#!/usr/bin/env python3
"""Rebuild the whole ERSorbits tree (ERS1/, ERS2/, ENVISAT/) from the public orbit servers.

    python3.13 build.py CACHE_DIR            download what is missing into CACHE_DIR, then build the tree
    python3.13 build.py CACHE_DIR --offline  build from CACHE_DIR only
    python3.13 build.py CACHE_DIR --download-only

Downloads go into CACHE_DIR only (never into the repository). They are resumable: a file whose size matches the server's is
not downloaded again, and an interrupted HTTP download continues from its partial file. Every network step has a timeout and
retries. The tree is written next to this script; existing files with identical content are not rewritten. Files under the
satellite folders that this build does not produce are listed as stale (remove them with git rm); nothing is deleted.

Selection rule, per satellite and UTC day: the day goes to the highest-ranked set whose arcs together cover the WHOLE day;
only when no set covers the whole day, to the highest-ranked set covering any part of it. Sets rank by the gravity model of
their solution, newest model generation first, and Delft's operational sets (OPERATIONAL) rank below every precise set as a
fallback (RANK_ORDER, below); only sets of the same model rank by production date, a set's production date for a day being
the newest production date of its arcs covering that day. Every arc of the day's set
covering the day is listed for it (of arcs of one set with the identical span, only the newest). An arc is kept when it is
listed for at least one day; every other arc is dropped. A stack of scenes thus takes one consistent set, switching only at
day boundaries between periods, and a set takes over on its first whole day. Production dates: Delft = the file's FTP MDTM,
DORIS = the P<publish time> of its name, PRC rev2 = 1995-03-24 (PRC_PRODUCED, below). Days no source covers are gaps. The build log
(CACHE_DIR/build_log.txt) and CACHE_DIR/summary.json list the kept and dropped arcs, the gaps, the number of days of each
kind, and the days no set covers whole with the stretches their set leaves open.
"""
import argparse
import bisect
import csv
import datetime as dt
import ftplib
import gzip
import hashlib
import io
import json
import os
import re
import struct
import sys
import time
import zipfile

import requests

REPO = os.path.dirname(os.path.abspath(__file__))
SATELLITES = ('ERS1', 'ERS2', 'ENVISAT')

DELFT_HOST = 'dutlru2.lr.tudelft.nl'
DELFT_ROOT = '/pub/orbits'
DELFT_SOURCE = 'TU Delft DEOS'
# (satellite, FTP folder, set, kind); POE files take their arc spans from the arclist of the ODR set of the same name.
# Not used: ODR.ERS-2/dgm-e09spx (DGM-E09, 1995-05..1999-06): its arcs meet end to end with 28 holes between them (482 h), so
# under the whole-day rule a 1995-1999 ERS-2 stack would switch between DGM-E09 and DGM-E04 at 56 day boundaries; DGM-E04
# (dgm-e04) is continuous and published (the README gives the hole table). dgm-e04.prelim (preliminary) and dgm-e04.auto
# (automatic, no arclist) are not the final orbits of their model; ODR.ENVISAT1/outdated holds superseded Envisat sets.
DELFT_SETS = (
    ('ERS1', 'ODR.ERS-1', 'dgm-e04', 'ODR'),
    ('ERS1', 'ODR.ERS-1', 'dgm-e04.fd', 'ODR'),
    ('ERS1', 'ODR.ERS-1', 'jgm3', 'ODR'),
    ('ERS2', 'ODR.ERS-2', 'dgm-e04', 'ODR'),
    ('ERS2', 'ODR.ERS-2', 'dgm-e04.fd', 'ODR'),
    ('ERS2', 'ODR.ERS-2', 'eigen-grace01s', 'ODR'),
    ('ERS2', 'ODR.ERS-2', 'grim5-c1', 'ODR'),
    ('ERS2', 'ODR.ERS-2', 'jgm3', 'ODR'),
    ('ENVISAT', 'ODR.ENVISAT1', 'eigen-cg03c', 'ODR'),
    ('ENVISAT', 'POE.ENVISAT1', 'eigen-cg03c', 'POE'),
)
STEP_BASE = 'https://step.esa.int/auxdata/orbits/'
STEP_SOURCE = 'ESA STEP'
# (satellite, set = folder on STEP, years); ERS-1 1997 is not served
STEP_SETS = (
    ('ERS1', 'ers_precise_orb/ERS1', [*range(1991, 1997), *range(1998, 2001)]),
    ('ERS2', 'ers_precise_orb/ERS2', list(range(1995, 2012))),
    ('ENVISAT', 'Doris/vor', list(range(2002, 2013))),
)
# The gravity model of each set's orbit solution (Delft: the set's folder name and arclist; PRC rev2: PGM055, D-PAF manual;
# DORIS: GDR-D, published 2012; the DORIS files name no model).
SET_MODEL = {
    'ODR.ERS-1/dgm-e04': 'DGM-E04', 'ODR.ERS-1/dgm-e04.fd': 'DGM-E04', 'ODR.ERS-1/jgm3': 'JGM-3',
    'ers_precise_orb/ERS1': 'PGM055',
    'ODR.ERS-2/eigen-grace01s': 'EIGEN-GRACE01S', 'ODR.ERS-2/grim5-c1': 'GRIM5-C1',
    'ODR.ERS-2/dgm-e04': 'DGM-E04', 'ODR.ERS-2/dgm-e04.fd': 'DGM-E04', 'ODR.ERS-2/jgm3': 'JGM-3',
    'ers_precise_orb/ERS2': 'PGM055',
    'Doris/vor': 'GDR-D', 'ODR.ENVISAT1/eigen-cg03c': 'EIGEN-CG03C', 'POE.ENVISAT1/eigen-cg03c': 'EIGEN-CG03C',
}
# Delft's operational orbits (arclist version 402, "Operational orbit": quick-look SLR normal points, no altimeter crossovers):
# a fallback below every precise set.
OPERATIONAL = ('ODR.ERS-1/dgm-e04.fd', 'ODR.ERS-2/dgm-e04.fd')
# Set precedence: newest gravity model generation first; sets of the same model by file date (newest first); the operational
# sets last. ERS: EIGEN-GRACE01S (2003) > GRIM5-C1 (1999) > DGM-E04 precise (1998) > PGM055 (1995) > JGM-3 (1994) >
# DGM-E04 operational. Envisat: GDR-D (published 2012) > EIGEN-CG03C (2005). The README gives the sources.
RANK_ORDER = ('EIGEN-GRACE01S', 'GRIM5-C1', 'DGM-E04', 'PGM055', 'JGM-3', 'DGM-E04 operational', 'GDR-D', 'EIGEN-CG03C')


def set_class(s):
    """The set's place in RANK_ORDER: its gravity model, or 'DGM-E04 operational' for an operational set."""
    return 'DGM-E04 operational' if s in OPERATIONAL else SET_MODEL[s]
HTTP_TIMEOUT = (30, 120)
RETRIES = 6
INDEX_COLUMNS = ('path', 'start', 'end', 'source', 'set', 'model', 'produced', 'sha256')
ODR_EPOCH = dt.datetime(1985, 1, 1)
PRC_EPOCH = dt.datetime(2000, 1, 1, 12)
TFMT = '%Y-%m-%dT%H:%M:%S'
# The PRC files hold no production date, and STEP's zip member dates are repacks (outer 2015-02; inner 2014-04, a few 2012-06,
# 2013-07 or 2013-09; whatever the arc's year). "rev2" is D-PAF's revision 2 (gravity model PGM055), in operational use for arcs from 1995-03-24: ESA's D-PAF
# "Altimeter and Orbit Global Products Manual" ERS-D-GPM-31200 (GFZ), its product history and PRC product sections,
# https://earth.esa.int/eogateway/documents/20142/37627/ERS-Altimeter-and-Orbit-Global-Products-Manual.pdf
PRC_PRODUCED = dt.datetime(1995, 3, 24)

LOG = []


def log(*args):
    line = ' '.join(str(a) for a in args)
    print(line, flush=True)
    LOG.append(line)


def backoff(attempt):
    time.sleep(min(60, 5 * 2 ** attempt))


# ------------------------------------------------------------------------------------------------------------------ download
class Ftp:
    """One anonymous FTP connection, reopened on a network error."""

    def __init__(self):
        self.ftp = None

    def call(self, fn):
        for attempt in range(RETRIES):
            try:
                if self.ftp is None:
                    self.ftp = ftplib.FTP(DELFT_HOST, timeout=60)
                    self.ftp.login()
                return fn(self.ftp)
            except ftplib.error_perm:
                raise
            except (*ftplib.all_errors, EOFError) as e:
                log(f'  FTP retry {attempt + 1}/{RETRIES}: {type(e).__name__}: {e}')
                try:
                    self.ftp.close()
                except Exception:
                    pass
                self.ftp = None
                backoff(attempt)
        raise RuntimeError('FTP: too many failures')

    def close(self):
        if self.ftp is not None:
            try:
                self.ftp.quit()
            except Exception:
                pass
        self.ftp = None


def delft_wanted(kind, name):
    if kind == 'ODR':
        return name == 'arclist' or re.fullmatch(r'ODR\.[0-9A-Z]\d\d', name) is not None
    return re.fullmatch(r'envisat\.\d{3}\.poe\.gz', name) is not None


FTP_CONNECTIONS = 3  # the server refuses a 4th connection from one address (421 too many connections)


def delft_fetch(ftp, path, name, size, dest):
    """MDTM and RETR of one file through one connection; the file is renamed into place after its size is checked."""
    mdtm = ftp.call(lambda f: f.sendcmd(f'MDTM {path}/{name}')).split()[-1]
    for attempt in range(RETRIES):
        with open(dest + '.part', 'wb') as fh:
            ftp.call(lambda f: (fh.seek(0), fh.truncate(), f.retrbinary(f'RETR {path}/{name}', fh.write)))
        if os.path.getsize(dest + '.part') == size:
            os.replace(dest + '.part', dest)
            return mdtm
        log(f'  size mismatch {path}/{name}, retry')
        backoff(attempt)
    raise RuntimeError(f'{path}/{name}: size mismatch')


def download_delft(cache):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    local_ftp = threading.local()
    connections = []

    def worker_ftp():
        if not hasattr(local_ftp, 'ftp'):
            local_ftp.ftp = Ftp()
            connections.append(local_ftp.ftp)
        return local_ftp.ftp
    with ThreadPoolExecutor(FTP_CONNECTIONS) as pool:
        for sat, folder, oset, kind in DELFT_SETS:
            path = f'{DELFT_ROOT}/{folder}/{oset}'
            local = os.path.join(cache, 'delft', folder, oset)
            os.makedirs(local, exist_ok=True)
            lines = []
            # the listing goes through a worker's connection: the server allows only FTP_CONNECTIONS per address
            pool.submit(lambda: worker_ftp().call(lambda f: (lines.clear(), f.retrlines(f'LIST {path}', lines.append)))).result()
            entries = {}
            for line in lines:
                parts = line.split()
                if line.startswith('-') and len(parts) >= 9 and delft_wanted(kind, parts[-1]):
                    entries[parts[-1]] = {'size': int(parts[4]), 'list': ' '.join(parts[5:8])}
            listing_path = os.path.join(local, 'listing.json')
            listing = json.load(open(listing_path)) if os.path.exists(listing_path) else {}
            todo = []
            for name, e in sorted(entries.items()):
                dest = os.path.join(local, name)
                old = listing.get(name)
                if not (old and old['size'] == e['size'] and old.get('mdtm') and os.path.exists(dest)
                        and os.path.getsize(dest) == e['size']):
                    todo.append(name)
            t0 = time.time()
            futures = {name: pool.submit(lambda n: delft_fetch(worker_ftp(), path, n, entries[n]['size'],
                                                               os.path.join(local, n)), name) for name in todo}
            try:
                for k, (name, fut) in enumerate(futures.items()):
                    entries[name]['mdtm'] = fut.result()
                    listing[name] = entries[name]
                    if k % 50 == 49:
                        json.dump(listing, open(listing_path, 'w'), indent=1, sort_keys=True)
            finally:
                json.dump({k: v for k, v in listing.items() if k in entries}, open(listing_path, 'w'), indent=1, sort_keys=True)
            log(f'Delft {folder}/{oset}: {len(entries)} files, {sum(e["size"] for e in entries.values())} B; '
                f'downloaded now {len(todo)} files, {sum(entries[n]["size"] for n in todo)} B in {time.time() - t0:.0f} s')
    for c in connections:
        c.close()


def http_download(session, url, dest):
    """Download url to dest, resuming a partial file; False when the server has no such file (404)."""
    for attempt in range(RETRIES):
        try:
            h = session.head(url, timeout=HTTP_TIMEOUT, allow_redirects=True)
            if h.status_code == 404:
                return False
            h.raise_for_status()
            size = int(h.headers['Content-Length'])
            meta = {'size': size, 'last_modified': h.headers.get('Last-Modified')}
            if os.path.exists(dest) and os.path.getsize(dest) == size:
                return meta
            part = dest + '.part'
            have = os.path.getsize(part) if os.path.exists(part) else 0
            headers = {'Range': f'bytes={have}-'} if 0 < have < size else {}
            with session.get(url, headers=headers, stream=True, timeout=HTTP_TIMEOUT) as r:
                r.raise_for_status()
                mode = 'ab' if headers and r.status_code == 206 else 'wb'
                with open(part, mode) as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
            if os.path.getsize(part) == size:
                os.replace(part, dest)
                return meta
            log(f'  {url}: {os.path.getsize(part)} of {size} B, continuing')
        except (requests.RequestException, OSError, KeyError, ValueError) as e:
            log(f'  HTTP retry {attempt + 1}/{RETRIES} {url}: {type(e).__name__}: {e}')
        backoff(attempt)
    raise RuntimeError(f'{url}: download failed')


def download_step(cache):
    session = requests.Session()
    session.headers['User-Agent'] = 'insardev-orbits-build/1.0'
    for sat, sset, years in STEP_SETS:
        local = os.path.join(cache, 'step', sset)
        os.makedirs(local, exist_ok=True)
        listing_path = os.path.join(local, 'listing.json')
        listing = json.load(open(listing_path)) if os.path.exists(listing_path) else {}
        for year in years:
            url = f'{STEP_BASE}{sset}/{year}.zip'
            t0 = time.time()
            done = os.path.exists(os.path.join(local, f'{year}.zip'))
            meta = http_download(session, url, os.path.join(local, f'{year}.zip'))
            if not meta:
                log(f'STEP {url}: not served (404)')
                continue
            listing[str(year)] = meta
            log(f'STEP {url}: {meta["size"]} B, Last-Modified {meta["last_modified"]}'
                + ('' if done else f', downloaded in {time.time() - t0:.0f} s'))
        json.dump(listing, open(listing_path, 'w'), indent=1, sort_keys=True)


# ------------------------------------------------------------------------------------------------------------------ parsers
def parse_arclist(text):
    """Arc number -> (start, end) UTC from a Delft arclist ('yymmdd hh:mm - yymmdd hh:mm')."""
    arcs = {}
    for m in re.finditer(r'^\s*([0-9A-Z]\d\d)\s+(\d{6})\s+(\d{1,2}):(\d\d)\s+-\s+(\d{6})\s+(\d{1,2}):(\d\d)', text, re.M):
        def when(d, hh, mm):
            y = int(d[:2])
            return dt.datetime(1900 + y if y >= 50 else 2000 + y, int(d[2:4]), int(d[4:6]), int(hh), int(mm))
        arcs[m.group(1)] = (when(*m.group(2, 3, 4)), when(*m.group(5, 6, 7)))
    return arcs


def parse_odr(data):
    """Delft ODR: 'xODR', satellite, then (repeat, arc, n, version); records (t s after 1985 UTC, lat, lon 1e-7 deg, h mm)."""
    assert data[:4] in (b'xODR', b'@ODR'), data[:4]
    rep, arc, n, ver = struct.unpack('>4i', data[16:32])
    assert len(data) == 32 + 16 * n, (len(data), n)
    recs = [struct.unpack('>4i', data[32 + 16 * k:48 + 16 * k]) for k in (0, n - 1)]
    pts = [(ODR_EPOCH + dt.timedelta(seconds=r[0]), r[1] / 1e7, r[2] / 1e7, r[3] / 1e3) for r in recs]
    return {'satellite': data[4:12].decode().strip(), 'arc': arc, 'n': n, 'version': ver, 'first': pts[0], 'last': pts[-1]}


def parse_poe(gzdata):
    """Delft POE (gzip text): 4 lines per epoch, the first holding yyyymmddhhmm (D format) and seconds, then position."""
    lines = gzip.decompress(gzdata).decode('latin-1').splitlines()
    assert len(lines) % 4 == 0, len(lines)

    def epoch(k):
        a = lines[4 * k]
        stamp = f'{float(a[:22].replace("D", "E")):.0f}'
        t = dt.datetime.strptime(stamp, '%Y%m%d%H%M') + dt.timedelta(seconds=float(a[22:44]))
        b = lines[4 * k + 1]
        xyz = [float(b[i:i + 22]) for i in (0, 22, 44)]
        return t, xyz
    n = len(lines) // 4
    return {'n': n, 'first': epoch(0), 'last': epoch(n - 1)}


def parse_prc(data):
    """D-PAF PRC: 130-byte records; STATE holds TDT-UTC (ms); STTERR: day (0.1 d after 2000-01-01 12h TDT), us of day, x y z mm,
    v um/s."""
    recs = [data[i:i + 130] for i in range(0, len(data), 130)]
    assert recs[0].startswith(b'DSIDP') and recs[1].startswith(b'STATE'), recs[:2]
    tdt_utc = int(recs[1][47:52]) / 1e3
    state = recs[1].decode()
    terr = [r for r in recs if r.startswith(b'STTERR')]

    def epoch(r):
        s = r.decode()[6:]
        day, usec = int(s[8:14]), int(s[14:25])
        t = PRC_EPOCH + dt.timedelta(days=day / 10, microseconds=usec) - dt.timedelta(seconds=tdt_utc)
        xyz = [int(s[a:b]) / 1e3 for a, b in ((25, 37), (37, 49), (49, 61))]
        return t, xyz
    return {'tdt_utc': tdt_utc, 'state': state[:60].strip(), 'n': len(terr), 'first': epoch(terr[0]), 'last': epoch(terr[-1]),
            'state_span': [PRC_EPOCH + dt.timedelta(days=int(state[5:12]) / 10), PRC_EPOCH + dt.timedelta(days=int(state[12:18]) / 10)]}


def parse_dor(data):
    """Envisat DOR_VOR MPH fields and the first and last 129-byte data set records."""
    mph = int(re.search(rb'SPH_SIZE=\+(\d+)', data[:1300]).group(1))
    head = data[:data.index(b'SPH_SIZE=')].decode('ascii')
    f = dict(re.findall(r'^([A-Z_]+)=(.*)$', head, re.M))
    when = lambda s: dt.datetime.strptime(s.strip('"').strip()[:20], '%d-%b-%Y %H:%M:%S')
    dsd = re.search(rb'DS_NAME="DORIS PRECISE ORBIT\s*"\s*DS_TYPE=M\s*FILENAME="[^"]*"\s*DS_OFFSET=\+(\d+)<bytes>\s*'
                    rb'DS_SIZE=\+(\d+)<bytes>\s*NUM_DSR=\+(\d+)\s*DSR_SIZE=\+(\d+)<bytes>', data[:20000])
    off, size, n, rec = (int(x) for x in dsd.groups())
    assert size == n * rec and off + size <= len(data), (off, size, n, rec, len(data))
    recs = [data[off + rec * k:off + rec * (k + 1)].decode('ascii') for k in (0, n - 1)]
    pts = [(when(r[:27]), [float(x) for x in r[45:].split()[:3]]) for r in recs]
    return {'product': f['PRODUCT'].strip('"').strip(), 'proc_time': when(f['PROC_TIME']), 'software': f['SOFTWARE_VER'].strip('"').strip(),
            'start': when(f['SENSING_START']), 'stop': when(f['SENSING_STOP']), 'n': n, 'first': pts[0], 'last': pts[-1]}


# ------------------------------------------------------------------------------------------------------------------ arcs
def sha256(data):
    return hashlib.sha256(data).hexdigest()


def delft_arcs(cache):
    arcs = []
    for sat, folder, oset, kind in DELFT_SETS:
        local = os.path.join(cache, 'delft', folder, oset)
        listing = json.load(open(os.path.join(local, 'listing.json')))
        odr_dir = os.path.join(cache, 'delft', folder.replace('POE.', 'ODR.'), oset)
        arclist = parse_arclist(open(os.path.join(odr_dir, 'arclist'), encoding='latin-1').read())
        for name in sorted(listing):
            if name == 'arclist':
                continue
            number = name.split('.')[1]
            if number not in arclist:
                log(f'  {folder}/{oset}/{name}: arc not in the arclist, not used')
                continue
            data = open(os.path.join(local, name), 'rb').read()
            start, end = arclist[number]
            m = listing[name]['mdtm']
            produced = dt.datetime.strptime(m[:14], '%Y%m%d%H%M%S')
            arcs.append({'sat': sat, 'source': DELFT_SOURCE, 'set': f'{folder}/{oset}', 'name': name,
                         'zip': f'{kind}_{oset}_{number}.zip', 'member': name, 'start': start, 'end': end,
                         'produced': produced, 'sha256': sha256(data), 'size': len(data),
                         'ref': ('file', os.path.join(local, name))})
    return arcs


def step_members(path):
    """(outer member, inner member, ZipInfo of the inner member, bytes) for every nested zip of a STEP year zip."""
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if not info.filename.endswith('.zip'):
                continue
            with zipfile.ZipFile(io.BytesIO(z.read(info))) as inner:
                for j in inner.infolist():
                    if not j.is_dir():
                        yield info.filename, j, inner.read(j)


def step_arcs(cache):
    arcs = []
    for sat, sset, years in STEP_SETS:
        for year in years:
            path = os.path.join(cache, 'step', sset, f'{year}.zip')
            if not os.path.exists(path):
                continue
            for outer, j, data in step_members(path):
                name = os.path.basename(j.filename)
                pattern = r'DOR_VOR_AXVF-P\d{8}_\d{6}_\d{8}_\d{6}_\d{8}_\d{6}' if sset.startswith('Doris') else r'PRC_\d{6}_\d{5}_rev2'
                if not re.fullmatch(pattern, name):
                    log(f'  {sset}/{year}.zip {outer}: {name} is not an orbit file of this set, not used')
                    continue
                if sset.startswith('Doris'):
                    d = parse_dor(data)
                    m = re.match(r'DOR_VOR_AXVF-P(\d{8})_(\d{6})_', name)
                    produced = dt.datetime.strptime(m.group(1) + m.group(2), '%Y%m%d%H%M%S')
                    if produced != d['proc_time'] or d['product'] != name:
                        log(f'  {name}: name/MPH differ: PROC_TIME {d["proc_time"]}, PRODUCT {d["product"]}')
                    start, end = d['start'], d['stop']
                else:
                    d = parse_prc(data)
                    produced = PRC_PRODUCED
                    start, end = d['first'][0], d['last'][0]
                arcs.append({'sat': sat, 'source': STEP_SOURCE, 'set': sset, 'name': name, 'zip': f'{name}.zip', 'member': name,
                             'start': start.replace(microsecond=0), 'end': end.replace(microsecond=0), 'produced': produced,
                             'sha256': sha256(data), 'size': len(data), 'ref': ('step', path, outer, j.filename)})
    return arcs


def read_original(arc):
    if arc['ref'][0] == 'file':
        return open(arc['ref'][1], 'rb').read()
    _, path, outer, member = arc['ref']
    with zipfile.ZipFile(path) as z, zipfile.ZipFile(io.BytesIO(z.read(outer))) as inner:
        return inner.read(member)


# ------------------------------------------------------------------------------------------------------------------ selection
def days_of(arc):
    """UTC days the arc covers any part of."""
    d = arc['start'].date()
    out = []
    while dt.datetime.combine(d, dt.time()) < arc['end']:
        out.append(d)
        d += dt.timedelta(days=1)
    return out


def select(arcs):
    """Return kept arcs, dropped arcs (with reasons) and gap days, per satellite."""
    result = {}
    for sat in SATELLITES:
        mine = [a for a in arcs if a['sat'] == sat]
        dropped = []
        # one span within one set: the newest file only; one name within one set: the newest only
        best = {}
        for a in sorted(mine, key=lambda a: a['produced']):
            for key in ((a['set'], a['start'], a['end']), (a['set'], a['name'])):
                if key in best and best[key] is not a:
                    old = best[key]
                    if old['sha256'] == a['sha256']:
                        old['reason'] = f'identical copy of {a["name"]}'
                    else:
                        old['reason'] = f'superseded in its set by {a["name"]} (produced {a["produced"]:{TFMT}})'
                best[key] = a
        live = [a for a in mine if 'reason' not in a]
        dropped += [a for a in mine if 'reason' in a]
        byday = {}
        for a in live:
            for d in days_of(a):
                byday.setdefault(d, []).append(a)
        for a in live:
            a['won'] = []
        partial = []
        daykind = {}
        for d, cands in sorted(byday.items()):
            day0 = dt.datetime.combine(d, dt.time())
            day1 = day0 + dt.timedelta(days=1)
            # per set: its place in RANK_ORDER, then the newest production date of its arcs covering the day, and whether
            # they cover the whole day
            sets = {}
            for a in cands:
                sets.setdefault(a['set'], []).append(a)
            rank = {s: (-RANK_ORDER.index(set_class(s)), max(a['produced'] for a in v), s) for s, v in sets.items()}
            whole = [s for s, v in sets.items()
                     if not subtract([(day0, day1)], [(max(a['start'], day0), min(a['end'], day1)) for a in v])]
            winner = max(whole or sets, key=lambda s: rank[s])
            daykind[d] = 'whole' if whole else 'partial'
            for a in cands:
                if a['set'] == winner:
                    a['won'].append(d)
                else:
                    a.setdefault('lost_to', set()).add(winner)
            if whole:
                continue
            # no set covers the whole day: the parts of the day the winning set leaves open (another set may cover some)
            mine_d = [(max(a['start'], day0), min(a['end'], day1)) for a in sets[winner]]
            others = [a for a in cands if a['set'] != winner]
            for s, e in subtract([(day0, day1)], mine_d):
                over = [a for a in others if a['start'] < e and a['end'] > s]
                partial.append({'start': s, 'end': e, 'winner': winner, 'other_sets': sorted({a['set'] for a in over}),
                                'other_arcs': sorted(a['name'] for a in over)})
        kept = sorted([a for a in live if a['won']], key=lambda a: (a['start'], a['set'], a['name']))
        for a in live:
            if not a['won']:
                a['reason'] = 'listed for no day; each of its days goes to: ' + ', '.join(sorted(a.get('lost_to', ())))
                dropped.append(a)
        if byday:
            first, last = min(byday), max(byday)
            gaps, d = [], first
            while d <= last:
                if d not in byday:
                    gaps.append(d)
                d += dt.timedelta(days=1)
        else:
            gaps = []
        result[sat] = {'kept': kept, 'dropped': sorted(dropped, key=lambda a: (a['start'], a['set'], a['name'])), 'gaps': gaps,
                       'holes': holes(live), 'partial': partial, 'daykind': daykind}
    return result


def union(spans):
    """Merged (start, end) intervals; touching intervals merge."""
    out = []
    for s, e in sorted(x for x in spans if x[1] > x[0]):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [tuple(x) for x in out]


def subtract(base, spans):
    """Parts of the base intervals not covered by spans."""
    out = []
    cover = union(spans)
    for s, e in base:
        t = s
        for cs, ce in cover:
            if ce <= t or cs >= e:
                continue
            if cs > t:
                out.append((t, cs))
            t = max(t, ce)
        if t < e:
            out.append((t, e))
    return out


def ranges(days):
    out = []
    for d in days:
        if out and (d - out[-1][1]).days == 1:
            out[-1][1] = d
        else:
            out.append([d, d])
    return out


def holes(kept):
    """Time intervals between the first start and the last end that no kept arc covers."""
    spans = sorted((a['start'], a['end']) for a in kept)
    out, reach = [], None
    for s, e in spans:
        if reach is not None and s > reach:
            out.append((reach, s))
        reach = e if reach is None else max(reach, e)
    return out


# ------------------------------------------------------------------------------------------------------------------ writing
def zip_bytes(member, data, when):
    buf = io.BytesIO()
    info = zipfile.ZipInfo(member, date_time=when.timetuple()[:6])
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o644 << 16
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr(info, data, compresslevel=9)
    return buf.getvalue()


def write_if_changed(path, data):
    if os.path.exists(path) and open(path, 'rb').read() == data:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + '.tmp', 'wb') as fh:
        fh.write(data)
    os.replace(path + '.tmp', path)
    return True


def index_csv(rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(INDEX_COLUMNS)
    for a in rows:
        w.writerow([a['path'], f'{a["start"]:{TFMT}}', f'{a["end"]:{TFMT}}', a['source'], a['set'], SET_MODEL[a['set']],
                    f'{a["produced"]:{TFMT}}', a['sha256']])
    return buf.getvalue().encode()


def write_tree(result):
    produced_files = set()
    nwritten = 0
    for sat, r in result.items():
        days = {}
        for a in r['kept']:
            a['path'] = f'{sat}/{a["start"]:%Y/%m/%d}/{a["zip"]}'
            data = read_original(a)
            assert sha256(data) == a['sha256'], a['name']
            nwritten += write_if_changed(os.path.join(REPO, a['path']), zip_bytes(a['member'], data, a['produced']))
            produced_files.add(a['path'])
            for d in a['won']:  # a day's index lists the winning set's arcs only
                days.setdefault(d, []).append(a)
        for d, rows in days.items():
            p = f'{sat}/{d:%Y/%m/%d}/index.csv'
            nwritten += write_if_changed(os.path.join(REPO, p), index_csv(sorted(rows, key=lambda a: (a['start'], a['path']))))
            produced_files.add(p)
        p = f'{sat}/index.csv'
        nwritten += write_if_changed(os.path.join(REPO, p), index_csv(r['kept']))
        produced_files.add(p)
    stale = []
    for sat in SATELLITES:
        for root, _, files in os.walk(os.path.join(REPO, sat)):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), REPO)
                if rel not in produced_files:
                    stale.append(rel)
    log(f'tree: {len(produced_files)} files, {nwritten} written or changed now, {len(stale)} stale')
    for s in sorted(stale):
        log(f'  stale (not produced by this build): {s}')


def report(result, cache):
    summary = {}
    for sat, r in result.items():
        log(f'== {sat}')
        sets = sorted({a['set'] for a in r['kept'] + r['dropped']})
        summary[sat] = {'sets': {}, 'gaps': [[f'{a}', f'{b}'] for a, b in ranges(r['gaps'])],
                        'holes': [[f'{a:{TFMT}}', f'{b:{TFMT}}'] for a, b in r['holes']],
                        'partial': [{'start': f'{p["start"]:{TFMT}}', 'end': f'{p["end"]:{TFMT}}', 'winner': p['winner'],
                                     'other_sets': p['other_sets'], 'other_arcs': p['other_arcs']} for p in r['partial']]}
        for s in sets:
            k = [a for a in r['kept'] if a['set'] == s]
            dr = [a for a in r['dropped'] if a['set'] == s]
            allarcs = k + dr
            won = sorted({d for a in k for d in a['won']})
            info = {'model': SET_MODEL[s], 'arcs': len(allarcs), 'kept': len(k), 'dropped': len(dr),
                    'span': [f'{min(a["start"] for a in allarcs):{TFMT}}', f'{max(a["end"] for a in allarcs):{TFMT}}'],
                    'produced': [f'{min(a["produced"] for a in allarcs):{TFMT}}', f'{max(a["produced"] for a in allarcs):{TFMT}}'],
                    'kept_span': [f'{min(a["start"] for a in k):{TFMT}}', f'{max(a["end"] for a in k):{TFMT}}'] if k else None,
                    'days_won': len(won), 'days_won_ranges': [[f'{a}', f'{b}'] for a, b in ranges(won)],
                    'kept_arcs': [a['name'] for a in k],
                    'dropped_arcs': [[a['name'], a['reason']] for a in dr]}
            summary[sat]['sets'][s] = info
            log(f'  {s} ({info["model"]}): {info["arcs"]} arcs, kept {info["kept"]}, dropped {info["dropped"]}, span {info["span"]}, '
                f'produced {info["produced"]}, days won {info["days_won"]}')
            for a in dr:
                log(f'    dropped {s} {a["name"]} {a["start"]:{TFMT}}..{a["end"]:{TFMT}}: {a["reason"]}')
        log(f'  gaps (days no source covers): {len(r["gaps"])} days')
        for a, b in ranges(r['gaps']):
            log(f'    gap {a}..{b} ({(b - a).days + 1} d)')
        log(f'  gaps to the second (no arc of any set covers): {len(summary[sat]["holes"])}')
        for a, b in summary[sat]['holes']:
            log(f'    gap {a}..{b}')
        kinds = sorted(r['daykind'].values())
        summary[sat]['days'] = {'covered': len(kinds), 'whole': kinds.count('whole'), 'partial': kinds.count('partial'),
                                'partial_days': [f'{d}' for d, k in sorted(r['daykind'].items()) if k == 'partial']}
        log(f'  covered days: {len(kinds)}; a set covers the whole day: {kinds.count("whole")}; '
            f'no set covers the whole day: {kinds.count("partial")}')
        log(f'  open stretches of the days no set covers whole (the day\'s set leaves them open): {len(summary[sat]["partial"])}')
        for p in summary[sat]['partial']:
            log(f'    open {p["start"]}..{p["end"]} day set {p["winner"]}'
                + (f', also covered by {",".join(p["other_sets"])} {",".join(p["other_arcs"])}' if p['other_sets'] else ''))
    json.dump(summary, open(os.path.join(cache, 'summary.json'), 'w'), indent=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cache', help='cache folder for the downloads (outside the repository)')
    ap.add_argument('--offline', action='store_true', help='build from the cache only')
    ap.add_argument('--download-only', action='store_true', help='download into the cache, do not build')
    ap.add_argument('--sources', choices=('all', 'delft', 'step'), default='all', help='which servers to download from')
    args = ap.parse_args()
    # symlinks resolved on both sides: a link to a folder inside the repository is inside it
    cache = os.path.realpath(args.cache)
    if os.path.commonpath([cache, os.path.realpath(REPO)]) == os.path.realpath(REPO):
        sys.exit('the cache folder must be outside the repository')
    os.makedirs(cache, exist_ok=True)
    t0 = time.time()
    if not args.offline:
        if args.sources in ('all', 'delft'):
            download_delft(cache)
        if args.sources in ('all', 'step'):
            download_step(cache)
    if not args.download_only:
        arcs = delft_arcs(cache) + step_arcs(cache)
        log(f'arcs read: {len(arcs)}')
        result = select(arcs)
        report(result, cache)
        write_tree(result)
    log(f'done in {time.time() - t0:.0f} s')
    with open(os.path.join(cache, 'build_log.txt'), 'w') as fh:
        fh.write('\n'.join(LOG) + '\n')


if __name__ == '__main__':
    main()
