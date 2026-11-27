#!/usr/bin/env python3
"""Build the Envisat / ERS scene index beside the orbits from ESA's public catalogue (SO-Cat).

    python3.13 build_scenes.py CACHE_DIR --harvest                      harvest the whole catalogue into CACHE_DIR/socat/
    python3.13 build_scenes.py CACHE_DIR --harvest --months 1991-07     only these months (YYYY-MM or COLLECTION:YYYY-MM)
    python3.13 build_scenes.py CACHE_DIR --stage rows [--jobs 8]        build the scene rows CACHE_DIR/rows/ from CACHE_DIR/socat/
    python3.13 build_scenes.py CACHE_DIR --stage footprints [--jobs 8]  the footprint of every row into CACHE_DIR/footprints/
    python3.13 build_scenes.py CACHE_DIR --stage tree                   the track files and tiles under <MISSION>/scenes/
    python3.13 build_scenes.py CACHE_DIR --stage all [--jobs 8]         rows, footprints, tree

The cache folder lies outside the repository. The catalogue answers are kept there, never in the repository.

Harvest: one POST per collection (ASA_IMS_1P, SAR_IMS_1P) and calendar month, every field, as tab-separated values, into
CACHE_DIR/socat/<collection>_<YYYY-MM>.tsv; the row count of each answer is checked against its X-ESA-SOCat-Record-Count header
and each request is retried. Resumable: a month file is written whole (through a temporary file) and is not requested again.
SO-Cat includes the stop day, so neighbouring months share a day of records; the build keeps each productId once.

The rows stage, from CACHE_DIR/socat/ and the repository's orbits (no network; --jobs processes for the nodes):
1. read the month files; keep each productId once (the first read, the files in name order);
2. filter, the library's logic copied unchanged from insardev_toolkit/ESA.py (ESA._parse_id, _parseable, _delivery_record,
   _archive_record, _span_matches, _node, _node_marked, ...), orbit by orbit: the delivery records (format and node
   marks) and the records longer than 15.1 s are left out; the regular scenes (archive records whose time from the node
   spans their acquisition) and the ERS extra records (extra_record) are kept, every one of them: records that start
   together (the same data catalogued twice) are all kept, none is chosen;
3. skip the phases ERS-1 E, F, R and ERS-2 X (SKIP);
4. the precise node of every orbit that holds a kept record (ascending_node: the ascending zero of the precise orbit); an
   orbit without a usable orbit there is left out with its records (D5). The orbit's catalogue node is the median over its
   regular records of (beginAcquisition - startTimeFromAscendingNode), and R = catalogue node - precise node (node_step).
   An orbit with |R| above NODE_BOUND of its satellite (ERS: 0.5 s, the drifting orbits) is left out whole; an orbit
   without a regular record is left out when an extra record's (begin - start) - precise node lies farther than
   NODE_BOUND from both 0 and 1 s. ENVISAT orbits are not left out by R (NODE_BOUND None);
5. name each record (rule U) from its code start a, seconds after the node of its orbit: a regular or off-grid record's
   own startTimeFromAscendingNode as given (ESA's catalogue grid), an ERS extra record's beginAcquisition - the orbit's
   catalogue node, or its precise node in an orbit without a regular record; frame f = floor(7200 a / T + 0.5) + 9
   (frame_of) with the nominal period T of its phase; f < 0 moves it to the previous orbit with a + T, f > 7199 to the next
   one with a - T; the grid slot (a regular scene of ESA's cut) is a multiple of 18 frames of a; track =
   (orbit - c - 1) mod N + 1 of its phase (PHASES); the code <ENV|ER1|ER2>_<track field>_<f:04d>_<swath>_<YYYYMMDD of
   begin>_<pol>;
6. list every named record: one row each, nothing chosen among them;
7. assert: every productId listed once; every frame within 0..7199; every catalogue track label equal to the derived
   track of its orbit or one less. A failed assert stops the build and names the records; nothing is written then. Codes
   may repeat: the records that share a code are counted (shared_codes);
8. write CACHE_DIR/rows/<MISSION>/<track field>.tsv (ROW_COLUMNS, sorted by begin, then code; node_ms is the code start a
   in ms, and t_first_ms, t_last_ms the acquisition [beginAcquisition, endAcquisition] in the same frame: node_ms and
   node_ms + (end - begin)), CACHE_DIR/rows/nodes.tsv (NODE_COLUMNS: every orbit whose node was sought, its precise node,
   R and state) and CACHE_DIR/rows/summary.json (the counts of each step, the shared codes, the orbits left out with
   their R, the largest |R| of each satellite). Files whose bytes do not change are not rewritten; files under rows/ that
   this build no longer produces are listed as stale, nothing is deleted. No file holds a time stamp, a host name or a run
   id.

Every granule listed (the user, 2026-11-26: the index "for the each ESA granule returns footprint and orbit plus allows to
search the granules by AOI (and on client filter by date range, etc)"; "we dont need to skip granules by some our invented
rules"): every record that passes the filters above (the harvest's one record per productId, the delivery records, the
15.1 s limit, the regular and extra tests, the skipped phases, the orbits without a usable orbit and the drifting orbits)
is a row, records that start together included; the client chooses among overlapping ones. Two or more records under one
code (the same data catalogued twice) are all listed ("we have to show both because user can look for an exact
granule"); which one a download takes is the toolkit's rule, not the index's. The codes stay ("in the search results user see the local names and can check if already have
them").

Names and times (the user, 2026-11-26: "we have to use ESA catalog grabules - we cannot make them incompatible. and we have
to use the presize nodes to skip drifting orbits."): the names follow ESA's catalogue grid. A
regular or off-grid record's code start and node_ms are its own catalogue startTimeFromAscendingNode as given. An ERS
extra record's catalogue start lies 1 s or 0 s before its data, so its code start and node_ms are its beginAcquisition
less the catalogue node of its orbit (the median of begin - start over the orbit's regular records, which agree within
1 ms), or less the precise node in an orbit without a regular record (the ERS catalogue node equals the precise one:
median 0.07 ms, p1 / p99 -14 / +13 ms on the 2026-11-25 catalogue). The precise node decides only which orbits are
listed: an orbit whose catalogue node is more than NODE_BOUND off its precise node, or that has no usable precise orbit, is not
listed (the user, 2026-11-26: "a skipped month for users may be better than unknown accuracy frame for that period"). An
ERS extra record is identified from its own fields: an archive record (_archive_record) whose time from the ascending node
spans its acquisition plus 1.00 s (EXTRA_EXCESS within EXTRA_TOLERANCE) and whose recordLastUpdate lies before
EXTRA_BEFORE (the 2025-09 delivery records). Its kind column is
'extra'; a regular record's is 'regular' on its grid slot and 'offgrid' off it. Every row's acquisition (t_first_ms,
t_last_ms) is its own span [beginAcquisition, endAcquisition]: it depends on no other record.

The footprints stage, from CACHE_DIR/rows/, the repository's orbits and look rows (<MISSION>/scenes/look.csv) and the
Copernicus GLO-90 DEM (public bucket; its tiles kept in CACHE_DIR/heights/): the plain orbit prediction of each row on the
terrain, never widened, no search margin (the user, 2026-11-26):
1. window: ESA's processing window of the product, [beginAcquisition - PROCESS_BEFORE, endAcquisition + PROCESS_AFTER]
   (row_window, footprint_window), in seconds since 1970 (the user, 2026-11-27: the footprint covers the product; the
   product's lines lie inside it, see PROCESS_BEFORE);
2. orbit: the toolkit's own selection (utils_esa_orbit._orbit) over this repository; a row without a usable orbit (the
   selection raises ValueError) has no footprint and is not listed (D5; CACHE_DIR/footprints/no_orbit.tsv names them);
3. slant ranges: at the window's middle time the lines of sight at the look row's near and far look angles (off the
   geodetic nadir, in the zero-Doppler plane, right of the track) meet the WGS84 ellipsoid at R_near and R_far;
4. terrain: the zero-Doppler ground points of the window at R_near and R_far (the near and far edges) and of its first and
   last line between them, on the GLO-90 overview of 360 m plus the EGM2008 geoid. Each edge is sampled by the terrain:
   first a point every COARSE metres; an interval between two points is halved while the terrain heights in its band
   (the ground the edge can take between them, for the heights found there) times the band's cot(incidence) exceed
   BAND_LIMIT; never a step below FLOOR, so a layover spike narrower than FLOOR is not represented, by design. A point is
   the root of the ellipsoidal height of the circle point less the terrain height: its height bracket narrowed to the
   terrain of its own band, then scanned in SCAN DEM pixel on the ground and refined linearly (near edge: the root nearest
   the track; far edge: the farthest; lines: the nearest), or iterated where the bracket is flat;
5. outline: each edge simplified by Douglas-Peucker to TOLERANCE metres in the local tangent plane, the corners kept;
   longitudes -180..180, or 0..360 for an outline across 180 (FABLE_INDEX 3.4); vertices 'lat lon ...', 4 decimals.
Each row's vertices are kept in CACHE_DIR/footprints/<MISSION>/<track field>.tsv (FOOTPRINT_COLUMNS, one line per row by
its productId: a code may name two rows) under a key: the SHA-256 of the row's
inputs (productId, the window, satellite, swath, phase, the look row's near and far angles, the SHA-256 of every orbit zip the
orbit selection read, DEM_SOURCE and FOOTPRINT_VERSION). A rebuild computes only the rows whose key is missing. The track
files are the units of work (--jobs processes), their rows in time order, so that a process reuses its DEM blocks.

The tree stage, from CACHE_DIR/rows/ and CACHE_DIR/footprints/, writes <MISSION>/scenes/ of this repository:
- tracks/<track field>/<BAND x (frame // BAND), 4 digits>.csv: TRACK_COLUMNS, rows sorted by (begin, code);
- tiles/<N|S><lat:02d><E|W><lon:03d>.csv, 5 x 5 degrees named by the south-west corner (-180..180): one row per granule
  (track field, slot frame, swath, direction): TILE_COLUMNS, sorted by (track, frame, swath, direction). The outline is the
  convex hull of the granule's stored scene footprints, given with 2 decimals so that it contains the hull (asserted); the
  granule is listed in every tile the hull meets (closed sets). A hull across 180 is in 0..360, and listed on both sides;
- tiles.csv: name,rows of every tile file.
Files whose bytes do not change are not rewritten; the files under <MISSION>/scenes/ that the build no longer produces
are deleted (look.csv, an input, is kept). No file holds a time stamp, a host name or a run id.
"""
import argparse
import collections
import hashlib
import json
import math
import os
import re
import resource
import sys
import time

REPO = os.path.dirname(os.path.abspath(__file__))

# the catalogue
SOCAT_URL = 'https://esar-ds.eo.esa.int/socat/{}/search'
# the months of each collection: first month, the month after the last
HARVEST = (('ASA_IMS_1P', (2002, 3), (2012, 5)), ('SAR_IMS_1P', (1991, 7), (2011, 8)))
HTTP_TIMEOUT = (30, 600)
RETRIES = 6
MONTH_FILE = re.compile(r'^(ASA_IMS_1P|SAR_IMS_1P)_(\d{4})-(\d{2})\.tsv$')

# the repository folder of each satellite
MISSION = {'ENVISAT': 'ENVISAT', 'ERS-1': 'ERS1', 'ERS-2': 'ERS2'}
# the phases not indexed (decided 2026-11-25): the ERS-1 168-day phases E and F, its roll-tilt phase R, and ERS-2 phase X
SKIP = {('ERS-1', 'E'), ('ERS-1', 'F'), ('ERS-1', 'R'), ('ERS-2', 'X')}
# the track of an orbit per (satellite, missionPhase): (N tracks, c); track = (orbit - c - 1) mod N + 1. c is the value of
# (orbit - track) mod N that the catalogue labels carry (ERS-2 A: 50,866 of 51,355 orbits, every Envisat orbit; the others are
# the stale labels of a data take across the ascending node, labelled with the previous orbit's track, FABLE_INDEX 1.3)
PHASES = {
    ('ENVISAT', '2'): (501, 54), ('ENVISAT', '3'): (431, 18),
    ('ERS-1', 'A'): (43, 11), ('ERS-1', 'B'): (43, 11), ('ERS-1', 'C'): (501, 145), ('ERS-1', 'D'): (43, 42),
    ('ERS-1', 'G'): (501, 489),
    ('ERS-2', 'A'): (501, 355), ('ERS-2', 'B'): (43, 30),
}
# the ascending node of an orbit is sought in the precise orbit of this many seconds either side of the catalogue's node
# (the median of begin - start over the orbit's records; the orbit selection adds its MARGIN)
NODE_WINDOW = 60.0
# the bound of |R| per satellite, seconds, None for none (R of an orbit: its catalogue node, the median over its regular
# records of beginAcquisition - startTimeFromAscendingNode, less its node from the precise orbit; index/IDX1f_report.md
# section 2, the 2026-11-25 dump). ERS: 0.5 s leaves out the drifting orbits of the user's decision (KNODE, |R|
# 0.52-10.47 s; "we have to use the presize nodes to skip drifting orbits"); it lies in the gap of the sorted |R| of ERS-2
# (363.1 to 574.5 ms) and in a gap of ERS-1 (489.1 to 521.0 ms). ENVISAT: none; its R is ESA's own node convention, a
# yearly pattern of up to 2.3 s that is the same for every record of an orbit (index/IDX1f_r2_note.md)
NODE_BOUND = {'ENVISAT': None, 'ERS-1': 0.5, 'ERS-2': 0.5}
# the orbits of one unit of work of the node step (consecutive orbits share their orbit files)
NODE_CHUNK = 250
NODE_COLUMNS = ('satellite', 'orbit', 'node', 'R_ms', 'extra_ms', 'regular', 'extra', 'state')
# an ERS extra record: an archive record whose time from the node spans its acquisition plus EXTRA_EXCESS seconds (within
# EXTRA_TOLERANCE; 1.00 s on every one of the 604,980 such records of the 2026-11-25 dump) and whose recordLastUpdate lies
# before EXTRA_BEFORE (the delivery records were created in 2025-09; none of those 604,980 was updated in 2025). Left out:
# 68 records of 2025-09 and 4 of 2018 whose end lies an hour before their begin (index/IDX1d_report.md section 1)
EXTRA_EXCESS = 1.0
EXTRA_TOLERANCE = 0.05
# ESA's processing window of an IMS product, s: the product's MPH SENSING_START is beginAcquisition - 1.5 s and its
# SENSING_STOP endAcquisition + 2.5 s (both exact in 151 of 347 Envisat and 12 of 50 ERS headers read in 2026-11; the others
# start later or stop earlier, none more than 8 ms outside). The product's lines (its zero-Doppler first and last times) lie
# inside this window in 319 of 347 Envisat headers and 32 of 50 ERS headers; the others reach at most 0.22 s (Envisat) and
# 1.77 s (ERS-2, the gyroscope years) beyond it. The footprint covers this window (the user, 2026-11-27), so that a search finds the
# products whose lines hold the area, not only the catalogue's nominal frame (begin .. end, 15.09 s).
PROCESS_BEFORE = 1.5
PROCESS_AFTER = 2.5
EXTRA_BEFORE = '2025-09-01'
ROW_COLUMNS = ('code', 'productId', 'kind', 'phase', 'orbit', 'direction', 'begin', 'end', 'node_ms', 'esa_frame', 'bperp',
               'doppler', 'swath', 'pol', 'satellite', 't_first_ms', 't_last_ms')
KIND_NAME = {'R': 'regular', 'E': 'extra'}
LOG = []

# the footprints, edges sampled by the terrain (index/IDX1e_report.md; the user, 2026-11-26: "we store the footprints with
# 500m accuracy", "why than do you compute even on sea level with the same accuracy?"): each edge first at the step COARSE
# (m); an interval halved while the terrain heights in its band could move the edge by more than BAND_LIMIT (m); never a
# step below FLOOR (m); each edge then simplified by Douglas-Peucker to TOLERANCE (m). The quarter-pixel scan after
# IDX0_verify F2. Chosen on IDX0's 228 scenes against their dense 30 m outlines (C 1000-4000 m, B 50-300 m, F 90-360 m): the
# cheapest with the distance p95 at most 500 m (441 m), the 6 scenes above 500 m layover spikes of 30-149 m; FLOOR 360 m
# fails (p95 562 m), BAND_LIMIT does not change the distances up to 300 m
COARSE = 2000.0
BAND_LIMIT = 300.0
FLOOR = 180.0
TOLERANCE = 400.0
SCAN = 0.25
# the edge length of one DEM window, m (whole coarse intervals): every edge of a 15-18 s scene in one window (on IDX0's 228
# scenes 18.3 ms median CPU per footprint against 22.8 ms with 50 km and 29.5 ms with 25 km windows; the distances from the
# dense outlines differ on 3 and 5 of the 228 scenes, by at most 6 m)
PIECE = 150000.0
# the heights every terrain point lies between, m (the first bracket; the ground points at these and at their middle give
# the band of any height range by quadratic interpolation)
HEIGHT_SPAN = (-500.0, 9000.0)
# theta_at: Newton until the height is within THETA_TOL m, at most THETA_STEPS updates
THETA_TOL = 1.0
THETA_STEPS = 4
# a point whose height bracket is narrower than FLAT (m) is solved by iteration, a wider one by the scan
FLAT = 2.5
GLO90 = ('https://copernicus-dem-90m.s3.amazonaws.com/Copernicus_DSM_COG_30_{ns}_00_{ew}_00_DEM/'
         'Copernicus_DSM_COG_30_{ns}_00_{ew}_00_DEM.tif')
# the GLO-90 overview read (2: 4 x 90 m) and the geoid on its 0.02-degree lattice
DEM_LEVEL = 2
GEOID_STEP = 0.02
DEM_SOURCE = 'Copernicus GLO-90 COG overview 2 (360 m) + EGM2008 (insardev_toolkit.utils_geoid) on a 0.02-degree lattice'
# a new value recomputes every footprint: change it with any change of the footprint code
FOOTPRINT_VERSION = (f'IDX1e-1 coarse {COARSE} band {BAND_LIMIT} floor {FLOOR} tolerance {TOLERANCE} scan {SCAN} piece {PIECE} '
                     f'span {HEIGHT_SPAN} theta {THETA_TOL} {THETA_STEPS} flat {FLAT}')
# per process: the decoded DEM blocks kept (LRU, bytes), the geoid cells kept (LRU, 1-degree cells of 50 x 50 float64,
# 20 kB each) and the orbit repository files kept (LRU, bytes)
BLOCK_BYTES = 256 << 20
GEOID_CELLS = 4096
ORBIT_BYTES = 128 << 20
# the track files: bands of this many code frames
BAND = 180
TRACK_COLUMNS = ('code', 'productId', 'kind', 'phase', 'orbit', 'direction', 'begin', 'end', 'node_ms', 'esa_frame', 'bperp',
                 'doppler', 'footprint')
TILE_COLUMNS = ('track', 'frame', 'swath', 'direction', 'scenes', 'first', 'last', 'outline')
# tile size in units of 1e-4 degree (the stored footprint vertices)
TILE = 50000
FOOTPRINT_COLUMNS = ('code', 'productId', 'key', 'footprint', 'no_orbit')
WGS_A = 6378137.0
WGS_F = 1.0 / 298.257223563
WGS_E2 = WGS_F * (2 - WGS_F)
WGS_B = WGS_A * (1 - WGS_F)
WGS_EP2 = WGS_E2 / (1 - WGS_E2)

# >>> COPIED UNCHANGED FROM insardev_toolkit/ESA.py (constants)
# code prefix and file extension per satellite, and the satellite of a code prefix
_PREFIX = {'ENVISAT': 'ENV', 'ERS-1': 'ER1', 'ERS-2': 'ER2'}
# orbit grids per (satellite, missionPhase) (session/patches/esa_alos1 U2a Q1 and Q7): the repeat period T = cycle / orbits,
# the node longitude of track 1 lam1 (degrees; None where it is not measured) and whether it is a 35-day grid (a 3-digit track
# field in the code; the other grids carry the phase letter before a 4-digit track)
_DAY = 86400.0
_T35, _T3, _T168, _T30 = 35 * _DAY / 501, 3 * _DAY / 43, 168 * _DAY / 2411, 30 * _DAY / 431
_GRIDS = {
    ('ENVISAT', '2'): (_T35, 0.204, True), ('ENVISAT', '3'): (_T30, None, False),
    ('ERS-1', 'R'): (_T35, 0.204, True), ('ERS-1', 'C'): (_T35, 0.204, True), ('ERS-1', 'G'): (_T35, 0.204, True),
    ('ERS-1', 'A'): (_T3, 7.84, False), ('ERS-1', 'B'): (_T3, 5.96, False), ('ERS-1', 'D'): (_T3, 5.98, False),
    ('ERS-1', 'E'): (_T168, 0.21, False), ('ERS-1', 'F'): (_T168, 0.25, False),
    ('ERS-2', 'A'): (_T35, 0.204, True), ('ERS-2', 'B'): (_T3, None, False),
}
# the kinds of an ERS extra record (U2c Q3, measured on 8 products; ESA serves the two kinds, the others not as a scene) are
# told apart by (begin - the catalogue's start time from the node) less the orbit's node time: 1 s for A, 0 for B
_KIND_TOLERANCE = 0.05
# a regular record starts on its grid when its start frame lies this close to a multiple of 18 frames (ERS: within 0.048)
_ON_GRID = 0.25
_ID = re.compile(r'^(?P<collection>ASA_IMS_1P|SAR_IMS_1P)(?P<centre>N[A-Z0-9]{3}|REOD)(?P<date>\d{8})_(?P<time>\d{6})_'
                 r'(?P<duration>\d{8})(?P<phase>[0-9A-Z])(?P<cycle>\d{3})_(?P<track>\d{5})_(?P<orbit>\d{5})_(?P<counter>\d{4})$')
# <<< END OF THE COPIED CONSTANTS


# >>> COPIED UNCHANGED FROM insardev_toolkit/ESA.py (functions; not _extras: the build names the ERS extra records from
# their own fields, extra_record)
def _epoch(text):
    """
    Seconds since 1970 (UTC) of a catalogue time such as '2008-01-16T20:47:12.123Z'.

    Parameters
    ----------
    text : str
        ISO time, with or without 'Z'.

    Returns
    -------
    float

    Examples
    --------
    >>> _epoch('1970-01-01T00:00:01.500Z')
    1.5
    """
    from datetime import datetime, timezone
    value = datetime.fromisoformat(text.replace('Z', '+00:00'))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def _delivery_record(row):
    """
    Whether a catalogue record is a delivery record by its number formats: one of the records ESA created in 2025 for the
    copies it delivered on request (the 18 s scenes and the short scenes of the same orbits), partial and duplicating archive
    scenes. Its orbitNumber is zero-padded to 6 digits ('023029') and its wrsLongitudeGrid to 4 digits ('0129'), or its
    productId has the centre field REOD ('SAR_IMS_1PREOD20110505_...'; 1,271 ERS and 217 Envisat records of the cached
    catalogue, all created in 2025 and mostly 28-30 s long). The archive records have none of these (their orbit numbers have
    at most 5 digits and no leading zero, and the 4-digit tracks of the ERS-1 168-day phases E and F, such as '1672', have no
    leading zero either). Not every delivery record has a format mark: 7 of the cached catalogue (ERS-2 orbit 11061 of
    1997-06-01, created in 2025-09, 16-18 s) have none; the second mark, the orbit's node time (_node_marked), finds them.

    Parameters
    ----------
    row : dict
        A SO-Cat record.

    Returns
    -------
    bool

    Examples
    --------
    >>> _delivery_record({'orbitNumber': '023029', 'wrsLongitudeGrid': '0129'})
    True
    >>> _delivery_record({'orbitNumber': '83866', 'wrsLongitudeGrid': '29', 'productId': 'SAR_IMS_1PREOD20110505_211439_00000028B189_00029_83866_0000'})
    True
    >>> _delivery_record({'orbitNumber': '16593', 'wrsLongitudeGrid': '1672', 'productId': 'SAR_IMS_1PNESA19940503_211738_00000015E012_01672_16593_0000'})
    False
    """
    track = row['wrsLongitudeGrid']
    return (row['orbitNumber'].startswith('0') or (len(track) >= 4 and track.startswith('0'))
            or row.get('productId', '')[10:14] == 'REOD')


def _archive_record(row):
    """
    Whether a catalogue record is an archive record of a scene: a record in the archive's format (not a delivery record,
    _delivery_record), whose productId has a duration field of at most '00000015' and whose acquisition lasts at most 15.1 s (a
    shorter scene ends a data take: the Envisat records of 13 s are legitimate scenes). The delivery records, the 18 s scenes
    and short scenes inside them (36 ERS records of 3-15 s pass the duration rule), are never listed. The year of the record
    plays no part: 1,278 ERS and 217 Envisat records in the archive's format updated in 2025 last 16-30 s and fail the duration
    rule.

    Parameters
    ----------
    row : dict
        A SO-Cat record.

    Returns
    -------
    bool

    Examples
    --------
    >>> _archive_record({'productId': 'SAR_IMS_1PNESA19960227_211738_00000015G154_00129_24165_0000', 'orbitNumber': '24165',
    ...                  'wrsLongitudeGrid': '129',
    ...                  'beginAcquisition': '1996-02-27T21:17:38.000Z', 'endAcquisition': '1996-02-27T21:17:53.090Z'})
    True
    """
    if _delivery_record(row):
        return False
    try:
        field = int(row['productId'][30:38])
    except ValueError:
        return False
    # the duration in whole milliseconds: a record of exactly 15.100 s passes (IDX1V F1: float seconds read 15.1000000x)
    duration_ms = round((_epoch(row['endAcquisition']) - _epoch(row['beginAcquisition'])) * 1000)
    return field <= 15 and duration_ms <= 15100


def _span_matches(row):
    """
    Whether the time from the ascending node of a record spans its acquisition (completion - start = end - begin within 0.05 s):
    true for a regular scene, false for an ERS extra record (1 s longer).

    Parameters
    ----------
    row : dict
        A SO-Cat record.

    Returns
    -------
    bool or None
        None for a record without readable times from the node.

    Examples
    --------
    >>> _span_matches({'startTimeFromAscendingNode': '679042', 'completionTimeFromAscendingNode': '694132',
    ...                'beginAcquisition': '2002-11-13T20:47:33.390Z', 'endAcquisition': '2002-11-13T20:47:48.480Z'})
    True
    """
    try:
        span = (float(row['completionTimeFromAscendingNode']) - float(row['startTimeFromAscendingNode'])) / 1000
    except ValueError:
        return None
    return abs(span - (_epoch(row['endAcquisition']) - _epoch(row['beginAcquisition']))) < 0.05


def _orbit_key(row):
    """
    The orbit of a record: (satellite, orbit number as an integer).

    Parameters
    ----------
    row : dict
        A SO-Cat record.

    Returns
    -------
    tuple

    Examples
    --------
    >>> _orbit_key({'productId': 'ASA_IMS_1PNESA20080116_204713_000000152065_00129_30744_0000', 'orbitNumber': '030744'})
    ('ENVISAT', 30744)
    """
    return _platform(row), int(row['orbitNumber'])


def _node(row):
    """
    The ascending node time a record implies: its begin less its time from the node (startTimeFromAscendingNode), seconds
    since 1970; None for a record without a readable time from the node.

    Parameters
    ----------
    row : dict
        A SO-Cat record.

    Returns
    -------
    float or None

    Examples
    --------
    >>> _node({'beginAcquisition': '1970-01-01T00:11:20.000Z', 'startTimeFromAscendingNode': '679000'})
    1.0
    """
    try:
        return _epoch(row['beginAcquisition']) - float(row['startTimeFromAscendingNode']) / 1000
    except ValueError:
        return None


def _node_marked(rows):
    """
    The second mark of a delivery record, independent of the number formats (_delivery_record): its node time (_node). The
    archive records of an orbit share one node time: the regular scenes within 1 ms (6,758 cached orbits), the ERS extra
    records 1 s (kind A) or 0 s (kind B) after it (U2c Q3). The delivery records do not: 4,915 of the 4,936 cached ones
    differ from it by more than 0.1 s, the 7 without a format mark by 1273-1333 s (FABLE_ESA_review.md F4). The orbit's node
    time is the median over its archive records that span their acquisition (_archive_record, _span_matches), or, for an
    orbit without one, the least over its other archive records (as _extras takes it). A record is marked when its node time
    differs from its orbit's by neither 0 nor 1 s (within _KIND_TOLERANCE).

    Parameters
    ----------
    rows : list of dict
        SO-Cat records (any satellite and orbit).

    Returns
    -------
    set of str
        The productIds of the marked records (the records marked by the formats are left to _delivery_record).

    Examples
    --------
    >>> _node_marked([])
    set()
    """
    import statistics
    regular, other = {}, {}
    for row in rows:
        node = _node(row)
        if node is None or not _archive_record(row):
            continue
        (regular if _span_matches(row) else other).setdefault(_orbit_key(row), []).append(node)
    marked = set()
    for row in rows:
        key, node = _orbit_key(row), _node(row)
        if node is None or _delivery_record(row) or not (key in regular or key in other):
            continue
        reference = statistics.median(regular[key]) if key in regular else min(other[key])
        shift = node - reference
        if abs(shift) >= _KIND_TOLERANCE and abs(shift - 1) >= _KIND_TOLERANCE:
            marked.add(row['productId'])
    return marked


def _parseable(rows):
    """
    Split catalogue records into those whose productId has the known fields and a real calendar date and time (ESA._parse_id reads
    it) and those that have not: a productId of another format, and one of the format with an impossible date or time (month 13,
    hour 25). ESA.search leaves the others out with a WARNING naming them, so that one odd record never stops a search.

    Parameters
    ----------
    rows : list of dict
        SO-Cat records.

    Returns
    -------
    tuple
        (kept, left_out): two lists of records.

    Examples
    --------
    >>> _parseable([{'productId': 'ASA_IMS_1PNESA20080116_204713_000000152065_00129_30744_0000'}, {'productId': 'x'}])[1]
    [{'productId': 'x'}]
    >>> _parseable([{'productId': 'ASA_IMS_1PNESA20081316_254713_000000152065_00129_30744_0000'}])[0]
    []
    """
    kept, left_out = [], []
    for row in rows:
        try:
            ESA._parse_id(row.get('productId', ''))
        except ValueError:
            left_out.append(row)
        else:
            kept.append(row)
    return kept, left_out


def _platform(row):
    """
    The satellite of a catalogue record: 'ENVISAT', 'ERS-1' or 'ERS-2' (platformSerialIdentifier for ERS, else the productId).

    Parameters
    ----------
    row : dict
        A SO-Cat record.

    Returns
    -------
    str

    Examples
    --------
    >>> _platform({'productId': 'SAR_IMS_1PNESA19960228_211738_00000015A009_00129_04492_0000', 'platformSerialIdentifier': '2'})
    'ERS-2'
    """
    serial = row.get('platformSerialIdentifier', '')
    if row['productId'].startswith('SAR') and serial in ('1', '2'):
        return f'ERS-{serial}'
    return ESA._parse_id(row['productId'])['platform']


class ESA:
    """The library class's one method that the copied functions call (ESA._parse_id), copied unchanged."""

    @staticmethod
    def _parse_id(productId):
        """
        The fields of a productId, the ID that the download takes.

        Parameters
        ----------
        productId : str
            Such as 'SAR_IMS_1PNESA19960227_211738_00000015G154_00129_24165_0000'. The 1,488 delivery records of the cached
            catalogue whose centre field is REOD instead of NESA (all created in 2025, 28-30 s long, _delivery_record) have the
            same fields and are read as well.

        Returns
        -------
        dict
            collection ('ASA_IMS_1P' or 'SAR_IMS_1P'), platform ('ENVISAT', 'ERS-1', 'ERS-2'), start (datetime, UTC), orbit,
            track, phase, cycle (int), duration (seconds, int) and centre ('NESA' and the like, or 'REOD'). ERS-2 is told from
            ERS-1 by its phases: A or B from 1995 on, and X.

        Raises
        ------
        ValueError
            For a malformed ID.

        Examples
        --------
        >>> ESA._parse_id('ASA_IMS_1PNESA20080116_204713_000000152065_00129_30744_0000')['platform']
        'ENVISAT'
        """
        from datetime import datetime, timezone
        match = _ID.match(productId) if isinstance(productId, str) else None
        try:
            start = datetime.strptime(match['date'] + match['time'], '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            raise ValueError(f'Malformed ESA productId {productId!r}: expected such as '
                             f'SAR_IMS_1PNESA19960227_211738_00000015G154_00129_24165_0000.') from None
        phase = match['phase']
        if match['collection'] == 'ASA_IMS_1P':
            platform = 'ENVISAT'
        elif phase == 'X' or (phase in 'AB' and start.year >= 1995):
            platform = 'ERS-2'
        else:
            platform = 'ERS-1'
        return dict(collection=match['collection'], platform=platform, start=start, orbit=int(match['orbit']),
                    track=int(match['track']), phase=phase, cycle=int(match['cycle']), duration=int(match['duration']),
                    centre=match['centre'])
# <<< END OF THE COPIED FUNCTIONS


def log(*args):
    line = ' '.join(str(a) for a in args)
    print(line, flush=True)
    LOG.append(line)


def write_if_changed(path, data):
    if os.path.exists(path) and open(path, 'rb').read() == data:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + '.tmp', 'wb') as fh:
        fh.write(data)
    os.replace(path + '.tmp', path)
    return True


def peak_gb():
    """The peak resident memory of this process, GB (ru_maxrss: bytes on macOS, kB on Linux)."""
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / 1e9 if sys.platform == 'darwin' else rss / 1e6


# ------------------------------------------------------------------------------------------------------------------- harvest

def month_list(first, after):
    y, m = first
    while (y, m) < after:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def harvest(cache, months=None):
    """One POST per collection and month into cache/socat/<collection>_<YYYY-MM>.tsv; months limits it (a set of 'YYYY-MM' or
    'COLLECTION:YYYY-MM'). A month file that exists is complete (written through a temporary file) and not requested again."""
    import requests
    out = os.path.join(cache, 'socat')
    os.makedirs(out, exist_ok=True)
    session = requests.Session()
    session.trust_env = False
    session.headers['User-Agent'] = 'Mozilla/5.0 (insardev catalogue index)'
    total = requested = 0
    for coll, first, after in HARVEST:
        for y, m in month_list(first, after):
            name = f'{y}-{m:02d}'
            if months is not None and name not in months and f'{coll}:{name}' not in months:
                continue
            path = os.path.join(out, f'{coll}_{name}.tsv')
            if os.path.exists(path):
                continue
            y2, m2 = (y + 1, 1) if m == 12 else (y, m + 1)
            data = {'service': 'SimpleOnlineCatalogue', 'version': '1.2', 'request': 'search',
                    'format': 'text/tab-separated-values',
                    'query.beginAcquisition.start': f'{y}-{m:02d}-01', 'query.beginAcquisition.stop': f'{y2}-{m2:02d}-01'}
            for attempt in range(RETRIES):
                try:
                    r = session.post(SOCAT_URL.format(coll), data=data, headers={'Connection': 'close'}, timeout=HTTP_TIMEOUT)
                    if r.status_code != 200:
                        raise RuntimeError(f'HTTP {r.status_code} {r.text[:300]}')
                    count = int(r.headers['X-ESA-SOCat-Record-Count'])
                    text = r.text
                    n = sum(1 for line in text.splitlines()[1:] if line.strip())
                    if n != count:
                        raise RuntimeError(f'{n} rows, the header counts {count}')
                    break
                except Exception as e:
                    log(f'{coll} {name}: attempt {attempt + 1} failed: {type(e).__name__} {str(e)[:200]}')
                    if attempt + 1 == RETRIES:
                        sys.exit(f'{coll} {name}: harvest failed')
                    time.sleep(10 * 2 ** attempt)
            with open(path + '.tmp', 'w', encoding='utf-8') as fh:
                fh.write(text)
            os.replace(path + '.tmp', path)
            total += n
            requested += 1
            log(f'{coll} {name}: {n} records (header {count})')
    log(f'harvest: {requested} months requested, {total} records')


# ------------------------------------------------------------------------------------------------------------------ the rows

class Rec:
    """A kept catalogue record and its name: a (its code start, seconds after the node of its named orbit: name_records) and
    the names from it; s, c (the catalogue's start and completion from the node, ms text); begin_ms, end_ms (its
    acquisition, ms since 1970, UTC)."""
    __slots__ = ('sat', 'orbit', 'phase', 'label', 'swath', 'pol', 'dir', 'kind', 'begin_ms', 'end_ms', 's', 'c', 'esa',
                 'bperp', 'dop', 'pid',
                 'a', 'norbit', 'moved', 'track', 'field', 'frame', 'og', 'code')


def read_records(socat, st):
    """The kept records of the month files of socat/ (regular scenes and ERS extra records), each productId
    once; the counts of each step go to st (a dict of counters)."""
    files = {}
    for name in sorted(os.listdir(socat)):
        mt = MONTH_FILE.match(name)
        if mt is None:
            st['files not read (other names)'].append(name)
            continue
        files.setdefault(mt.group(1), []).append((name, f'{mt.group(2)}-{mt.group(3)}-01T00:00:00Z'))
    if not files:
        sys.exit(f'no catalogue month file in {socat}')
    seen, recs = {}, []
    c = st['read']
    for coll in ('ASA_IMS_1P', 'SAR_IMS_1P'):
        c[f'{coll} files'] = len(files.get(coll, []))
        buffer = {}
        for i, (name, month) in enumerate(files.get(coll, []) + [(None, None)]):
            if name is not None:
                with open(os.path.join(socat, name), encoding='utf-8') as fh:
                    lines = [line for line in fh.read().splitlines() if line.strip()]
                if not lines:
                    st['files not read (empty)'].append(name)
                    continue
                header = lines[0].split('\t')
                for line in lines[1:]:
                    row = dict(zip(header, line.split('\t')))
                    c[f'{coll} rows'] += 1
                    pid = row.get('productId', '')
                    h = hash(line)
                    if pid in seen:
                        if seen[pid] == h:
                            c[f'{coll} repeated rows dropped (identical)'] += 1
                        else:
                            c[f'{coll} repeated rows dropped (differing; the first read kept)'] += 1
                            st['repeated productIds differing'].append(pid)
                        continue
                    seen[pid] = h
                    c[f'{coll} records'] += 1
                    kept, left = _parseable([row])
                    if left:
                        c[f'{coll} unparseable productId'] += 1
                        continue
                    try:
                        key = _orbit_key(row)
                    except ValueError:
                        c[f'{coll} unreadable orbitNumber'] += 1
                        continue
                    buffer.setdefault(key, []).append(row)
                start = _epoch(month)
                # an orbit whose first record began before this month is complete: its records end within the first
                # day of this month, which this file holds (SO-Cat includes the stop day)
                done = [k for k, rows in buffer.items() if min(_epoch(r['beginAcquisition']) for r in rows) < start]
            else:
                done = list(buffer)
            recs += filter_records([r for k in done for r in buffer.pop(k)], st['filter'])
    return recs


def extra_record(row):
    """
    Whether an archive record (_archive_record) whose time from the node does not span its acquisition (_span_matches False)
    is an ERS extra record, from its own fields only: its time from the node spans its acquisition plus EXTRA_EXCESS (within
    EXTRA_TOLERANCE) and its recordLastUpdate lies before EXTRA_BEFORE.

    Parameters
    ----------
    row : dict
        A SO-Cat record.

    Returns
    -------
    bool

    Examples
    --------
    >>> row = {'startTimeFromAscendingNode': '679042', 'completionTimeFromAscendingNode': '695132',
    ...        'beginAcquisition': '1996-02-27T21:17:38.000Z', 'endAcquisition': '1996-02-27T21:17:53.090Z',
    ...        'recordLastUpdate': '2021-03-01T10:00:00Z'}
    >>> extra_record(row)
    True
    >>> extra_record(dict(row, completionTimeFromAscendingNode='695332'))
    False
    >>> extra_record(dict(row, recordLastUpdate='2025-09-18T10:32:29Z'))
    False
    """
    span = (float(row['completionTimeFromAscendingNode']) - float(row['startTimeFromAscendingNode'])) / 1000
    excess = span - (_epoch(row['endAcquisition']) - _epoch(row['beginAcquisition']))
    return abs(excess - EXTRA_EXCESS) < EXTRA_TOLERANCE and row['recordLastUpdate'] < EXTRA_BEFORE


def filter_records(rows, c):
    """The library's archive filter over the records of whole orbits: the regular scenes and the ERS extra records
    (extra_record), every one that passes (none is chosen among records that start together), as Rec."""
    marked = _node_marked(rows)
    regular, extras = [], []
    for row in rows:
        coll = row['productId'][:3]
        if _delivery_record(row):
            c[f'{coll} delivery record (format mark)'] += 1
        elif not _archive_record(row):
            c[f'{coll} archive format, longer than 15.1 s'] += 1
        else:
            span = _span_matches(row)
            if span is None:
                c[f'{coll} archive record without readable times from the node'] += 1
            elif span and row['productId'] in marked:
                c[f'{coll} delivery record (node mark)'] += 1
            elif span:
                regular.append(row)
            elif extra_record(row):
                extras.append(row)
            else:
                c[f'{coll} span differs from the acquisition, not an extra record (excess or update)'] += 1
    c['kept regular'] += len(regular)
    c['kept extra'] += len(extras)
    out = []
    for kind, kept in (('R', regular), ('E', extras)):
        for row in kept:
            r = Rec()
            r.sat, r.orbit = _orbit_key(row)
            r.phase, r.label = row['missionPhase'], int(row['wrsLongitudeGrid'])
            r.swath, r.pol = row['swathIdentifier'], row['polarisationChannels'].strip().upper()
            r.dir, r.kind = row['orbitDirection'][0], kind
            r.begin_ms = int(round(_epoch(row['beginAcquisition']) * 1000))
            r.end_ms = int(round(_epoch(row['endAcquisition']) * 1000))
            r.s, r.c = row['startTimeFromAscendingNode'], row['completionTimeFromAscendingNode']
            r.esa, r.bperp = row.get('wrsLatitudeGrid', '').strip(), row.get('baselinePerpendicularOffset', '').strip()
            r.dop, r.pid = (row.get('dopplerFrequency') or '').strip(), row['productId']
            r.moved = 0
            out.append(r)
    return out


def skip_records(recs, st):
    kept, unknown = [], []
    for r in recs:
        if (r.sat, r.phase) in SKIP:
            st['skip'][f'{r.sat} {r.phase}'] += 1
        elif (r.sat, r.phase) not in PHASES or (r.sat, r.phase) not in _GRIDS:
            unknown.append(r)
        else:
            kept.append(r)
    if unknown:
        fail('records of a phase with no constants (PHASES)', [f'{r.pid} {r.sat} phase {r.phase}' for r in unknown])
    return kept


def derived_track(sat, phase, orbit):
    n, c = PHASES[(sat, phase)]
    return (orbit - c - 1) % n + 1


def ascending_node(satellite, guess, reader):
    """
    The ascending node nearest a guess (seconds since 1970, UTC): the zero of the Earth-fixed z going north of the precise
    orbit selected by the toolkit (utils_esa_orbit._orbit over this repository, reader an OrbitReader) for the window
    guess +- NODE_WINDOW; from the linear root between the two vectors around it, Newton steps t -= z / vz on the
    selection's 9-point Lagrange interpolation until a step is below 1 ns (index/KNODE_report.md section 1).

    Returns
    -------
    (float, None) the node, or (None, str) the reason: the selection raises ValueError (no usable orbit), or the window
    holds no ascending zero of z.

    Examples
    --------
    >>> ascending_node('ERS-1', 680824774.906, OrbitReader(REPO))
    (680824774.922615, None)
    """
    import numpy as np
    from insardev_toolkit import utils_esa_orbit
    epoch = np.datetime64('1970-01-01T00:00:00', 'ns')

    def at(t):
        return epoch + np.int64(round(t * 1e9)) * np.timedelta64(1, 'ns')
    try:
        orbit = utils_esa_orbit._orbit(satellite, at(guess - NODE_WINDOW), at(guess + NODE_WINDOW), reader)
    except ValueError as e:
        return None, ' '.join(str(e).split())
    times, vectors = orbit['times'], orbit['vectors']
    sec = (times - epoch).astype(np.int64) / 1e9
    z = vectors[:, 2]
    up = np.nonzero((z[:-1] < 0) & (z[1:] >= 0))[0]
    if len(up) == 0:
        return None, 'no ascending zero of z in the window'
    i = up[np.argmin(np.abs(sec[up] - guess))]
    # Newton in seconds after the vector before the zero (float64 resolves 1e-15 s there, 1e-7 s on seconds since 1970)
    ref, ns = times[i], np.timedelta64(1, 'ns')
    dt = -z[i] / (z[i + 1] - z[i]) * (sec[i + 1] - sec[i])
    for _ in range(20):
        sv = utils_esa_orbit.interpolate(times, vectors[:, :3], vectors[:, 3:], np.array([ref + np.int64(round(dt * 1e9))
                                                                                          * ns]))[0]
        step = sv[2] / sv[5]
        dt -= step
        if abs(step) < 1e-9:
            return float(sec[i] + dt), None
    return None, 'the node did not converge'


def _node_start(repo):
    WORKER.update(node_reader=OrbitReader(repo))


def _node_unit(items):
    """The nodes of a list of (satellite, orbit, guess): [(satellite, orbit, node, reason), ...]."""
    reader = WORKER['node_reader']
    return [(sat, orbit, *ascending_node(sat, guess, reader)) for sat, orbit, guess in items]


def orbit_nodes(items, jobs):
    """{(satellite, orbit): (node, reason)} of a list of (satellite, orbit, guess), in jobs processes (units of NODE_CHUNK
    consecutive orbits); the result does not depend on jobs."""
    items = sorted(items)
    chunks = [items[k:k + NODE_CHUNK] for k in range(0, len(items), NODE_CHUNK)]
    out = {}
    if jobs == 1 or len(chunks) <= 1:
        _node_start(REPO)
        for part in map(_node_unit, chunks):
            out.update({(s, o): (n, why) for s, o, n, why in part})
        return out
    import multiprocessing
    with multiprocessing.get_context('spawn').Pool(min(jobs, len(chunks)), _node_start, (REPO,)) as pool:
        for part in pool.imap_unordered(_node_unit, chunks):
            out.update({(s, o): (n, why) for s, o, n, why in part})
    return out


def frame_of(t, T):
    """
    The code frame of a time t after the node (seconds) with the nominal period T: floor(7200 t / T + 0.5) + 9.

    Examples
    --------
    >>> frame_of(0.0, 6000.0), frame_of(-5.0, 6000.0), frame_of(6000.0, 6000.0)
    (9, 3, 7209)
    """
    return math.floor(7200 * t / T + 0.5) + 9


def node_step(recs, st, jobs):
    """
    The precise nodes of the orbits of the kept records (ascending_node), the orbits left out, and the node of each kept
    orbit that an ERS extra record's code start is counted from. Per orbit: its catalogue node, the median over its regular
    records of (beginAcquisition - startTimeFromAscendingNode), and R = catalogue node - precise node. Left out with all
    their records: an orbit without a usable orbit at its node (D5); an orbit with |R| above NODE_BOUND of its satellite
    (the drifting orbits); an orbit without a regular record when an extra record's (begin - start) - precise node lies
    farther than NODE_BOUND from both 0 and 1 s. The node of a kept orbit is its catalogue node, or its precise node when it
    has no regular record. Returns (kept records, {(satellite, orbit): node in seconds since 1970, None for an orbit left
    out}, the rows of rows/nodes.tsv); the counts go to st['nodes'], the orbits left out to st['orbits left out'], the
    largest |R| to st['largest |R|'].
    """
    import statistics
    c = st['nodes']
    by_orbit = {}
    for r in recs:
        by_orbit.setdefault((r.sat, r.orbit), []).append(r)
    items = [(sat, o, statistics.median((r.begin_ms - float(r.s)) / 1000 for r in rs))
             for (sat, o), rs in by_orbit.items()]
    found = orbit_nodes(items, jobs)
    nodes, table, kept, worst = {}, {}, [], {}
    for key in sorted(by_orbit):
        sat, o = key
        rs = by_orbit[key]
        node, reason = found[key]
        nreg = sum(r.kind == 'R' for r in rs)
        counts = (str(nreg), str(len(rs) - nreg))
        nodes[key] = None
        kinds = f'{nreg} regular, {len(rs) - nreg} extra'
        if node is None:
            c[f'{sat} orbits without a usable orbit at the node'] += 1
            c[f'{sat} regular records of orbits without a usable orbit (not listed)'] += nreg
            c[f'{sat} extra records of orbits without a usable orbit (not listed)'] += len(rs) - nreg
            table[key] = ('', '', '', *counts, f'no orbit: {reason}')
            st['orbits left out'].append(f'{sat} {o} no usable orbit ({kinds}): {reason}')
            continue
        bound = NODE_BOUND[sat]
        if nreg:
            # the catalogue node in ms since 1970 (whole or half ms: begin and start are whole ms)
            catalogue = statistics.median(r.begin_ms - float(r.s) for r in rs if r.kind == 'R')
            R = catalogue / 1000 - node
            worst.setdefault(sat, []).append((abs(R), o))
            off, text = bound is not None and abs(R) > bound, (f'{R * 1000:.3f}', '')
            why = f'R {R * 1000:+.3f} ms'
            code_node = catalogue / 1000
        else:
            x = max(min(abs((r.begin_ms - float(r.s)) / 1000 - node), abs((r.begin_ms - float(r.s)) / 1000 - node - 1))
                    for r in rs)
            off, text = bound is not None and x > bound, ('', f'{x * 1000:.3f}')
            why = f'no regular record; an extra record {x * 1000:.3f} ms from 0 and 1 s'
            code_node = node
        c[f'{sat} orbits with a node'] += 1
        if off:
            c[f'{sat} orbits left out (|R| above NODE_BOUND)'] += 1
            c[f'{sat} regular records of orbits left out by NODE_BOUND (not listed)'] += nreg
            c[f'{sat} extra records of orbits left out by NODE_BOUND (not listed)'] += len(rs) - nreg
            table[key] = (f'{node:.6f}', *text, *counts, 'inconsistent')
            st['orbits left out'].append(f'{sat} {o} {why} ({kinds})')
            continue
        table[key] = (f'{node:.6f}', *text, *counts, 'kept')
        nodes[key] = code_node
        kept += rs
    for sat, values in sorted(worst.items()):
        values.sort()
        st['largest |R|'][sat] = [f'{o} {v * 1000:.3f}' for v, o in values[-120:]]
    rows = [(sat, str(o), *table[(sat, o)]) for sat, o in sorted(table)]
    return kept, nodes, rows


def name_records(recs, nodes, st):
    """Rule U from each record's own fields: the code start a, frame, the node move, track, code (FABLE_INDEX 2.1). The
    names follow ESA's catalogue grid: a regular or off-grid record's a (seconds after the node, node_ms) is its own
    catalogue startTimeFromAscendingNode as given; an ERS extra record's, whose catalogue start lies 1 s or 0 s before its
    data, is beginAcquisition - the node of its orbit (node_step: the orbit's catalogue node, or its precise node in an
    orbit without a regular record). frame = frame_of(a, T) with the nominal period T of the phase; a frame below 0 moves
    the record to the previous orbit with a + T, above 7199 to the next with a - T (D4; a record moved into an orbit that
    is not listed keeps its name and is counted). The grid slot (og) of a regular record: a within _ON_GRID of a multiple
    of 18 frames. Returns the named records."""
    for r in recs:
        T, _, is35 = _GRIDS[(r.sat, r.phase)]
        r.a = (r.begin_ms / 1000 - nodes[(r.sat, r.orbit)]) if r.kind == 'E' else float(r.s) / 1000
        frame = frame_of(r.a, T)
        r.norbit = r.orbit
        if frame < 0 or frame > 7199:
            r.moved = -1 if frame < 0 else 1
            r.norbit += r.moved
            r.a += -r.moved * T
            frame = frame_of(r.a, T)
            st['moves'][f'{r.sat} {KIND_NAME[r.kind]} to the {"previous" if r.moved < 0 else "next"} orbit'] += 1
            if nodes.get((r.sat, r.norbit), 0) is None:
                st['moves'][f'{r.sat} {KIND_NAME[r.kind]} moved into an orbit that is not listed (named, kept)'] += 1
        r.frame = frame
        sf = 7200 * r.a / T
        r.og = r.kind == 'R' and abs(sf - 18 * round(sf / 18)) < _ON_GRID
        r.track = derived_track(r.sat, r.phase, r.norbit)
        r.field = f'{r.track:03d}' if is35 else f'{r.phase}{r.track:04d}'
        date = time.strftime('%Y%m%d', time.gmtime(r.begin_ms // 1000))
        r.code = f'{_PREFIX[r.sat]}_{r.field}_{r.frame:04d}_{r.swath}_{date}_{r.pol}'
    return recs


def row_kind(r):
    """
    The kind column of a row: 'extra' of an ERS extra record; of a regular record 'regular' on its grid slot (og), else
    'offgrid'.

    Examples
    --------
    >>> r = Rec(); r.kind, r.og = 'R', True
    >>> row_kind(r)
    'regular'
    >>> r.og = False; row_kind(r)
    'offgrid'
    """
    if r.kind != 'R':
        return KIND_NAME[r.kind]
    return 'regular' if r.og else 'offgrid'


def fail(what, names):
    log(f'ASSERT FAILED: {what}: {len(names)}')
    for name in names[:200]:
        log(f'  {name}')
    if len(names) > 200:
        log(f'  ... and {len(names) - 200} more')
    return names


def shared_codes(recs, c):
    """
    Count the codes that name more than one record (the same data catalogued twice: every record is listed, the codes
    stay): the groups by satellite and kinds into the counter c ('<satellite> <kind>+<kind>...', the kinds sorted), and
    'codes' (the distinct codes), 'shared-code groups' and 'rows in shared-code groups' in total.

    Examples
    --------
    >>> r1, r2, r3 = Rec(), Rec(), Rec()
    >>> for r, pid in ((r1, 'a'), (r2, 'b'), (r3, 'c')):
    ...     r.sat, r.kind, r.og, r.code, r.pid = 'ENVISAT', 'R', True, 'ENV_001_0009_IS2_20080116_VV', pid
    >>> r3.code = 'ENV_001_0027_IS2_20080116_VV'
    >>> c = Counter(); shared_codes([r1, r2, r3], c); dict(c)
    {'codes': 2, 'ENVISAT regular+regular': 1, 'shared-code groups': 1, 'rows in shared-code groups': 2}
    """
    codes = {}
    for r in recs:
        codes.setdefault(r.code, []).append(r)
    c['codes'] = len(codes)
    for code in sorted(codes):
        rs = codes[code]
        if len(rs) > 1:
            c[f'{rs[0].sat} {"+".join(sorted(row_kind(r) for r in rs))}'] += 1
            c['shared-code groups'] += 1
            c['rows in shared-code groups'] += len(rs)


def check(recs, st):
    """The asserts over the listed records: every productId once; every frame within 0..7199; every catalogue track label
    equal to the derived track of its own orbit or one less. Returns the number of failed asserts (each named in the
    log). Codes may repeat (shared_codes counts them)."""
    failed = 0
    c = st['asserts']
    pids = Counter()
    for r in recs:
        pids[r.pid] += 1
    twice = sorted(pid for pid, n in pids.items() if n > 1)
    c['productIds'] = len(pids)
    if twice:
        failed += 1
        fail('one productId listed twice', [f'{pid}: {pids[pid]} rows' for pid in twice])
    outside = [r for r in recs if not 0 <= r.frame <= 7199]
    if outside:
        failed += 1
        fail('a frame outside 0..7199 after the node move', [f'{r.pid} frame {r.frame}' for r in outside])
    bad = []
    for r in recs:
        n = PHASES[(r.sat, r.phase)][0]
        d = (r.label - derived_track(r.sat, r.phase, r.orbit)) % n
        if d == 0:
            c[f'{r.sat} track label equal to the derived track'] += 1
        elif d == n - 1:
            c[f'{r.sat} track label one less than the derived track (stale)'] += 1
        else:
            bad.append(f'{r.pid} label {r.label} derived {derived_track(r.sat, r.phase, r.orbit)}')
    if bad:
        failed += 1
        fail('a catalogue track label neither the derived track nor one less', bad)
    return failed


def iso(ms):
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(ms // 1000)) + f'.{ms % 1000:03d}Z'


def row_text(r):
    """A row (ROW_COLUMNS): node_ms is the code start a in whole ms (name_records); t_first_ms and t_last_ms are the
    record's own acquisition [beginAcquisition, endAcquisition] in the same frame, node_ms and node_ms + (end - begin), so
    that begin + (t - node_ms) gives it back (row_window)."""
    node_ms = round(r.a * 1000)
    return '\t'.join((r.code, r.pid, row_kind(r), r.phase, str(r.norbit), r.dir, iso(r.begin_ms), iso(r.end_ms),
                      str(node_ms), r.esa, r.bperp, r.dop, r.swath, r.pol, r.sat,
                      str(node_ms), str(node_ms + r.end_ms - r.begin_ms)))


def write_rows(cache, listed, st):
    files = {}
    for r in listed:
        files.setdefault(os.path.join(MISSION[r.sat], r.field + '.tsv'), []).append((iso(r.begin_ms), r.code, row_text(r)))
    root = os.path.join(cache, 'rows')
    written = 0
    for rel, rows in sorted(files.items()):
        rows.sort()
        data = ('\t'.join(ROW_COLUMNS) + '\n' + ''.join(text + '\n' for _, _, text in rows)).encode()
        written += write_if_changed(os.path.join(root, rel), data)
        st['files'][rel.split(os.sep)[0]] += 1
    stale = []
    for mission in sorted(set(MISSION.values())):
        folder = os.path.join(root, mission)
        if os.path.isdir(folder):
            stale += [os.path.join(mission, f) for f in sorted(os.listdir(folder)) if os.path.join(mission, f) not in files]
    return written, stale


def stage_rows(cache, jobs):
    t0 = time.time()
    socat = os.path.join(cache, 'socat')
    names = ('read', 'filter', 'skip', 'nodes', 'moves', 'listed', 'shared codes', 'asserts', 'files')
    st = {k: {} for k in names}
    for k in names:
        st[k] = Counter()
    st['files not read (other names)'], st['files not read (empty)'], st['repeated productIds differing'] = [], [], []
    st['orbits left out'], st['largest |R|'] = [], {}
    times = {}
    all_kept = read_records(socat, st)
    times['read, de-duplicate and filter'] = time.time() - t0
    log(f'read and filter: {len(all_kept)} kept records, {times["read, de-duplicate and filter"]:.0f} s')
    t = time.time()
    phased = skip_records(all_kept, st)
    times['skip'] = time.time() - t
    t = time.time()
    consistent, nodes, node_rows = node_step(phased, st, jobs)
    times['nodes'] = time.time() - t
    log(f'nodes: {len(node_rows)} orbits sought, {len(consistent)} of {len(phased)} records in orbits kept, '
        f'{times["nodes"]:.0f} s ({jobs} processes)')
    t = time.time()
    listed = name_records(consistent, nodes, st)
    for r in listed:
        st['listed'][f'{r.sat} {row_kind(r)}'] += 1
    times['name'] = time.time() - t
    t = time.time()
    failed = check(listed, st)
    shared_codes(listed, st['shared codes'])
    times['asserts and shared codes'] = time.time() - t
    if failed:
        log(f'{failed} assert(s) failed: nothing written')
        return 1
    t = time.time()
    written, stale = write_rows(cache, listed, st)
    written += write_if_changed(os.path.join(cache, 'rows', 'nodes.tsv'), (
        '\t'.join(NODE_COLUMNS) + '\n' + ''.join('\t'.join(row) + '\n' for row in node_rows)).encode())
    summary = {k: dict(sorted(st[k].items())) for k in names}
    for k in ('files not read (other names)', 'files not read (empty)', 'repeated productIds differing',
              'orbits left out', 'largest |R|'):
        summary[k] = st[k]
    summary['NODE_BOUND (s)'] = {k: v for k, v in sorted(NODE_BOUND.items())}
    summary['kept records'] = len(all_kept)
    summary['records of the kept phases'] = len(phased)
    summary['records in orbits kept (node_step)'] = len(consistent)
    summary['listed rows'] = len(listed)
    summary['stale files'] = stale
    written += write_if_changed(os.path.join(cache, 'rows', 'summary.json'),
                                (json.dumps(summary, indent=1, sort_keys=True) + '\n').encode())
    times['write'] = time.time() - t
    for k, v in times.items():
        log(f'time {k}: {v:.1f} s')
    log(f'rows: {len(listed)} listed; {st["shared codes"]["shared-code groups"]} shared-code groups; {written} files '
        f'written; {len(stale)} stale files'
        + ''.join(f'\n  stale: {s}' for s in stale))
    log(f'done in {time.time() - t0:.0f} s; peak memory {peak_gb():.2f} GB')
    return 0


# ---------------------------------------------------------------------------------------------------------------- footprints
# Ported from IDX1b's scenes_footprint.py (index/IDX1b_report.md section 2, verified in IDX1b_verify.md). Changed here: the
# tile-absence marker is read back (IDX1b_verify D1); the geoid is computed once per 1-degree cell of its 0.02-degree
# lattice and process (Heights.geoid_cell); the decoded DEM blocks are cropped to the raster and kept in an LRU by bytes.
# IDX1e: the edges sampled by the terrain (edges, roots, HeightRange, Piece), theta_at with the analytic derivative and
# THETA_TOL, Bowring with one iteration.

def ecef(lat, lon, h):
    """
    Earth-fixed XYZ (m) of geodetic latitude, longitude (degrees) and height (m) on WGS84.

    Examples
    --------
    >>> ecef(0.0, 0.0, 0.0).tolist()
    [6378137.0, 0.0, 0.0]
    """
    import numpy as np
    lat, lon = np.radians(lat), np.radians(lon)
    n = WGS_A / np.sqrt(1 - WGS_E2 * np.sin(lat) ** 2)
    return np.stack([(n + h) * np.cos(lat) * np.cos(lon), (n + h) * np.cos(lat) * np.sin(lon),
                     (n * (1 - WGS_E2) + h) * np.sin(lat)], axis=-1)


def bowring(P):
    """
    (geodetic latitude in radians, distance from the axis p, height) of Earth-fixed points (..., 3): Bowring's formula, one
    iteration (index/IDX1e_report.md: below 1e-6 m for heights of -500 .. 9000 m, below 1 cm at 700-900 km).

    Examples
    --------
    >>> [round(float(v), 6) for v in bowring(ecef(0.0, 0.0, 100.0))]
    [0.0, 6378237.0, 100.0]
    """
    import numpy as np
    P = np.asarray(P, float)
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    p = np.hypot(x, y)
    u = np.arctan2(z * WGS_A, p * WGS_B)
    lat = np.arctan2(z + WGS_EP2 * WGS_B * np.sin(u) ** 3, p - WGS_E2 * WGS_A * np.cos(u) ** 3)
    s = np.sin(lat)
    n = WGS_A / np.sqrt(1 - WGS_E2 * s * s)
    c = np.cos(lat)
    pole = np.abs(c) <= 1e-9
    # each branch divided only where it is used (no 0 / 0 at the equator or the poles)
    h = np.where(pole, np.abs(z) / np.where(pole, np.abs(s), 1.0) - n * (1 - WGS_E2), p / np.where(pole, 1.0, c) - n)
    return lat, p, h


def geodetic(P, lonlat=True):
    """
    Geodetic latitude, longitude (degrees, -180..180) and height (m) of Earth-fixed points (..., 3), `bowring`. lonlat
    False: (None, None, height), the height computed by the same operations.

    Examples
    --------
    >>> [round(float(v), 6) for v in geodetic(ecef(45.0, 10.0, 1234.5))]
    [45.0, 10.0, 1234.5]
    >>> P = ecef([10.0, -80.0, 89.9], [170.0, -179.9, 5.0], [9000.0, -500.0, 0.0])
    >>> bool((geodetic(P, False)[2] == geodetic(P)[2]).all())
    True
    """
    import numpy as np
    lat, _, h = bowring(P)
    if not lonlat:
        return None, None, h
    P = np.asarray(P, float)
    return np.degrees(lat), np.degrees(np.arctan2(P[..., 1], P[..., 0])), h


def tangent(lat0, lon0, lat, lon):
    """
    East and north metres of ellipsoid points (h = 0) in the tangent plane at (lat0, lon0): the Earth-fixed difference
    rotated into the local east-north axes (exact at any latitude and across 180 degrees).

    Examples
    --------
    >>> [round(float(v)) for v in tangent(45.0, 10.0, 45.01, 10.0)]
    [0, 1111]
    >>> [round(float(v)) for v in tangent(0.0, 179.99, 0.0, -179.99)]
    [2226, 0]
    """
    import numpy as np
    la, lo = math.radians(lat0), math.radians(lon0)
    d = ecef(np.asarray(lat, float), np.asarray(lon, float), 0.0) - ecef(lat0, lon0, 0.0)
    e = -math.sin(lo) * d[..., 0] + math.cos(lo) * d[..., 1]
    n = -math.sin(la) * math.cos(lo) * d[..., 0] - math.sin(la) * math.sin(lo) * d[..., 1] + math.cos(la) * d[..., 2]
    return e, n


def frame360(points):
    """
    The antimeridian convention (FABLE_INDEX_report 3.4): an outline whose longitudes (as given, -180..180) span more
    than 180 degrees crosses 180 and is returned in 0..360; every other one in -180..180.

    Examples
    --------
    >>> frame360([(-5.0, 179.5), (-5.0, -179.5), (-4.0, -179.6)])
    [(-5.0, 179.5), (-5.0, 180.5), (-4.0, 180.4)]
    >>> frame360([(40.0, 14.0), (41.0, 14.5)])
    [(40.0, 14.0), (41.0, 14.5)]
    """
    lons = [(lo + 180.0) % 360.0 - 180.0 for _, lo in points]
    if max(lons) - min(lons) > 180.0:
        return [(la, lo % 360.0) for (la, _), lo in zip(points, lons)]
    return [(la, lo) for (la, _), lo in zip(points, lons)]


def read_look_rows(repo):
    """
    The look rows of every satellite, {satellite: [row dict, ...]}, from <repo>/<ENVISAT|ERS1|ERS2>/scenes/look.csv.

    Examples
    --------
    >>> sorted(read_look_rows(REPO))
    ['ENVISAT', 'ERS-1', 'ERS-2']
    """
    import csv
    out = {}
    for sat, name in MISSION.items():
        with open(os.path.join(repo, name, 'scenes', 'look.csv'), newline='') as fh:
            out[sat] = list(csv.DictReader(fh))
    return out


def look_row(look_rows, satellite, swath, phase):
    """
    (look_near, look_far) degrees of the row of a satellite, swath and phase; ValueError when none holds it.

    Examples
    --------
    >>> look_row({'ERS-2': [dict(swath='IS2', phases='A B', look_near='16.96', look_far='23.53')]}, 'ERS-2', 'IS2', 'A')
    (16.96, 23.53)
    """
    for r in look_rows.get(satellite, []):
        if r['swath'] == swath and str(phase) in r['phases'].split():
            return float(r['look_near']), float(r['look_far'])
    raise ValueError(f'no look row for {satellite} {swath} phase {phase}')


class OrbitReader:
    """
    The reader get(path, limit) of this repository's orbits for utils_esa_orbit._orbit: the bytes of a file (path relative
    to the root), HTTP.NotFound when absent. The files are kept in an LRU of at most `limit` bytes. `select` runs the
    toolkit's selection and names the orbit zips it read, with their SHA-256.

    Examples
    --------
    >>> OrbitReader(REPO).select('ENVISAT', 1200516432.0, 1200516451.0)[0]['date']
    '2008-01-16'
    """

    def __init__(self, repo, limit=ORBIT_BYTES):
        self.repo, self.limit = repo, limit
        self.files, self.held, self.digests, self.used = collections.OrderedDict(), 0, {}, None

    def __call__(self, path, limit=None):
        from insardev_toolkit import HTTP
        if path in self.files:
            self.files.move_to_end(path)
            data = self.files[path]
        else:
            p = os.path.join(self.repo, path)
            data = None
            if os.path.isfile(p):
                with open(p, 'rb') as fh:
                    data = fh.read()
            self.files[path] = data
            self.held += len(data or b'')
            while self.held > self.limit and len(self.files) > 1:
                _, old = self.files.popitem(last=False)
                self.held -= len(old or b'')
        if data is None:
            raise HTTP.NotFound(path)
        if self.used is not None and path.endswith('.zip'):
            self.used.add(path)
            if path not in self.digests:
                self.digests[path] = hashlib.sha256(data).hexdigest()
        return data

    def select(self, satellite, first, last):
        """(orbit, [(zip path, sha256), ...], None), or (None, None, the reason) when the selection raises ValueError."""
        self.used = set()
        try:
            orbit = scene_orbit(satellite, first, last, self)
        except ValueError as e:
            return None, None, ' '.join(str(e).split())
        finally:
            used, self.used = self.used, None
        return orbit, [(p, self.digests[p]) for p in sorted(used)], None


def scene_orbit(satellite, first, last, orbit_reader):
    """
    The precise orbit of a window (seconds since 1970) through the toolkit's own selection (utils_esa_orbit._orbit: the
    day indexes, the arc choice, the jump and no_orbit checks), as utils_envisat.orbit_dict; ValueError as orbit_vectors
    raises it (no usable orbit).

    Examples
    --------
    >>> scene_orbit('ENVISAT', 1200516432.0, 1200516451.0, OrbitReader(REPO))['date']
    '2008-01-16'
    """
    import numpy as np
    from insardev_toolkit import utils_esa_orbit, utils_envisat
    epoch = np.datetime64('1970-01-01T00:00:00', 'ns')
    t0 = epoch + np.int64(round(first * 1e9)) * np.timedelta64(1, 'ns')
    t1 = epoch + np.int64(round(last * 1e9)) * np.timedelta64(1, 'ns')
    return utils_envisat.orbit_dict(utils_esa_orbit._orbit(satellite, t0, t1, orbit_reader))


def day_seconds(orbit, unix):
    """
    Seconds of the orbit's day of a time in seconds since 1970.

    Examples
    --------
    >>> day_seconds({'date': '1970-01-02'}, 86400.5)
    0.5
    """
    import numpy as np
    day = np.datetime64(orbit['date'], 'D').astype('datetime64[s]').astype(np.int64)
    return float(unix - day)


def plane(orbit, t):
    """
    The satellite state and the zero-Doppler plane at times t (seconds of the orbit's day): S, V (n, 3), the unit down d
    (geodetic down at S made normal to V) and the unit right r = d x V/|V|.

    Examples
    --------
    >>> S, V, d, r = plane(orbit, [t_mid])
    """
    import numpy as np
    from insardev_toolkit.utils_alos2_orbit import orbit_state
    S, V = orbit_state(orbit, np.atleast_1d(np.asarray(t, float)))
    lat, lon, _ = geodetic(S)
    la, lo = np.radians(lat), np.radians(lon)
    d = -np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=-1)
    a = V / np.linalg.norm(V, axis=-1, keepdims=True)
    d = d - np.sum(d * a, axis=-1, keepdims=True) * a
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    r = np.cross(d, a)
    return S, V, d, r


def slant_ranges(orbit, t, looks):
    """
    The slant ranges (m) at which the lines of sight at the look angles (degrees off the geodetic nadir, in the
    zero-Doppler plane, right of the track) meet the WGS84 ellipsoid, at the time t (seconds of the orbit's day).

    Examples
    --------
    >>> near, far = slant_ranges(orbit, t_mid, (16.96, 23.53))
    """
    S, V, d, r = plane(orbit, [t])
    S, d, r = S[0], d[0], r[0]
    out = []
    for look in looks:
        u = math.cos(math.radians(look)) * d + math.sin(math.radians(look)) * r
        qa = (u[0] ** 2 + u[1] ** 2) / WGS_A ** 2 + u[2] ** 2 / WGS_B ** 2
        qb = 2 * ((S[0] * u[0] + S[1] * u[1]) / WGS_A ** 2 + S[2] * u[2] / WGS_B ** 2)
        qc = (S[0] ** 2 + S[1] ** 2) / WGS_A ** 2 + S[2] ** 2 / WGS_B ** 2 - 1
        out.append(float((-qb - math.sqrt(qb * qb - 4 * qa * qc)) / (2 * qa)))
    return out


def circle(S, d, r, R, theta):
    """
    Points S + R (cos theta d + sin theta r); S, d, r (n, 3), R (n,), theta (n,) or (n, m) -> (n, 3) or (n, m, 3).

    Examples
    --------
    >>> import numpy as np
    >>> circle(np.zeros((1, 3)), np.array([[0.0, 0, -1]]), np.array([[1.0, 0, 0]]), np.array([2.0]), np.array([0.0])).tolist()
    [[0.0, 0.0, -2.0]]
    """
    import numpy as np
    theta = np.asarray(theta, float)
    if theta.ndim == 1:
        return S + R[:, None] * (np.cos(theta)[:, None] * d + np.sin(theta)[:, None] * r)
    return S[:, None, :] + R[:, None, None] * (np.cos(theta)[..., None] * d[:, None, :] + np.sin(theta)[..., None] * r[:, None, :])


def theta_at(S, d, r, R, h, theta0=None):
    """
    The angle theta at which the circle point S + R (cos theta d + sin theta r) has the geodetic height h (scalar or
    (n,)): Newton with the analytic derivative dh/dtheta = up . R (-sin theta d + cos theta r) (up: the geodetic normal at
    the point), until every height is within THETA_TOL metres (at most THETA_STEPS updates), from theta0 (default: the
    spherical law of cosines).

    Examples
    --------
    >>> import numpy as np
    >>> S = ecef(0.0, 0.0, 800e3)[None]; d = -S / np.linalg.norm(S); r = np.array([[0.0, -1.0, 0.0]])
    >>> th = theta_at(S, d, r, np.array([850e3]), 0.0)
    >>> abs(float(geodetic(circle(S, d, r, np.array([850e3]), th))[2][0])) < THETA_TOL
    True
    """
    import numpy as np
    n = len(S)
    h = np.broadcast_to(np.asarray(h, float), (n,))
    if theta0 is None:
        rs = np.linalg.norm(S, axis=-1)
        lat, _, _ = geodetic(S)
        rho = np.linalg.norm(ecef(lat, 0.0 * lat, 0.0 * lat), axis=-1) + h
        theta0 = np.arccos(np.clip((R ** 2 + rs ** 2 - rho ** 2) / (2 * R * rs), -1, 1))
    th = np.array(np.broadcast_to(np.asarray(theta0, float), (n,)), float)
    for k in range(THETA_STEPS + 1):
        c, s = np.cos(th), np.sin(th)
        P = S + R[:, None] * (c[:, None] * d + s[:, None] * r)
        lat, p, hg = bowring(P)
        g = hg - h
        go = np.abs(g) >= THETA_TOL
        if k == THETA_STEPS or not go.any():
            break
        cl = np.cos(lat)
        up = np.stack([cl * P[:, 0] / p, cl * P[:, 1] / p, np.sin(lat)], axis=-1)
        th = np.where(go, th - g / np.sum(up * (R[:, None] * (c[:, None] * r - s[:, None] * d)), axis=-1), th)
    return th


class Missing(Exception):
    """The bucket holds no tile there (HTTP 404 or 403: open sea)."""


class COG:
    """
    A cloud-optimized GeoTIFF (classic TIFF, little-endian, tiled, deflate, float32) read by HTTP Range requests: the
    header once, then single blocks. Every request is counted in `stats`. Blocks, the header and a tile's absence (an
    empty file 'missing') are kept on disk: `caches` is a list of tile folders read in order, the LAST one written.

    Examples
    --------
    >>> COG(GLO90.format(ns='N46', ew='E010'), requests.Session(), Counter(), [CACHE + '/heights/glo90/N46E010']).levels[0]['width']
    1200
    """
    TAGS = {256: 'width', 257: 'height', 259: 'compression', 277: 'spp', 258: 'bits', 317: 'predictor', 322: 'tw',
            323: 'th', 324: 'offsets', 325: 'counts', 339: 'format', 254: 'subfile', 33550: 'scale', 33922: 'tie',
            34735: 'geokeys', 42113: 'nodata'}
    TYPES = {1: ('B', 1), 2: ('s', 1), 3: ('H', 2), 4: ('I', 4), 11: ('f', 4), 12: ('d', 8), 16: ('Q', 8)}

    def __init__(self, url, session, stats, caches=(), head=16384):
        import struct
        import numpy as np
        self.url, self.session, self.stats, self.caches = url, session, stats, list(caches)
        # the marker is an empty file: read back as b'' (IDX1b_verify D1)
        if self._find('missing') is not None:
            stats['tiles absent (marker read)'] += 1
            raise Missing(url)
        raw = self._find(f'header_{head}.bin')
        if raw is None:
            try:
                data = self._get(0, head, 'header')
            except Missing:
                self._put('missing', b'')
                raise
            self._put(f'header_{head}.bin', data)
        else:
            data = raw
        if data[:4] != b'II*\x00':
            raise ValueError(f'{url}: not a classic little-endian TIFF')
        self.data = data
        off = struct.unpack('<I', data[4:8])[0]
        levels = []
        while off:
            ifd, off = self._ifd(off)
            if int(ifd.get('subfile', [0])[0]) & 4:
                continue
            levels.append(ifd)
        full = levels[0]
        sx, sy = float(full['scale'][0]), float(full['scale'][1])
        x0, y0 = float(full['tie'][3]), float(full['tie'][4])
        keys = list(full.get('geokeys', []))
        raster = 1
        for k in range(4, len(keys), 4):
            if keys[k] == 1025:
                raster = keys[k + 3]
        half = 0.0 if raster == 2 else 0.5
        self.west, self.north = x0 - (0.5 - half) * sx, y0 + (0.5 - half) * sy
        self.east, self.south = self.west + sx * full['width'][0], self.north - sy * full['height'][0]
        self.levels = []
        for ifd in levels:
            w, h = int(ifd['width'][0]), int(ifd['height'][0])
            if int(ifd.get('compression', [1])[0]) not in (1, 8, 32946):
                raise ValueError(f'{url}: compression {ifd["compression"]}')
            self.levels.append(dict(width=w, height=h, tw=int(ifd['tw'][0]), th=int(ifd['th'][0]),
                                    offsets=np.asarray(ifd['offsets'], np.int64), counts=np.asarray(ifd['counts'], np.int64),
                                    predictor=int(ifd.get('predictor', [1])[0]),
                                    compression=int(ifd.get('compression', [1])[0]),
                                    dx=(self.east - self.west) / w, dy=(self.north - self.south) / h))
        nodata = full.get('nodata')
        self.nodata = float(nodata.strip('\x00 ')) if isinstance(nodata, str) and nodata.strip('\x00 ') else None

    def _find(self, name):
        for c in self.caches:
            p = os.path.join(c, name)
            if os.path.exists(p):
                with open(p, 'rb') as fh:
                    return fh.read()
        return None

    def _put(self, name, raw):
        if not self.caches:
            return
        os.makedirs(self.caches[-1], exist_ok=True)
        p = os.path.join(self.caches[-1], name)
        tmp = f'{p}.{os.getpid()}.part'
        with open(tmp, 'wb') as fh:
            fh.write(raw)
        os.replace(tmp, p)

    def _get(self, start, size, kind):
        import requests
        for attempt in range(6):
            try:
                r = self.session.get(self.url, headers={'Range': f'bytes={start}-{start + size - 1}'}, timeout=(10, 120))
                if r.status_code in (403, 404):
                    self.stats['requests answered absent'] += 1
                    raise Missing(self.url)
                r.raise_for_status()
                if kind == 'block' and len(r.content) != size:
                    raise IOError(f'{self.url}: {len(r.content)} bytes for {size}')
                break
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError, IOError) as e:
                if isinstance(e, requests.HTTPError) and e.response is not None and e.response.status_code < 500:
                    raise
                if attempt == 5:
                    raise
                self.stats['retries'] += 1
                time.sleep(2 * (attempt + 1))
        self.stats['requests'] += 1
        self.stats[kind + ' bytes requested'] += len(r.content)
        return r.content

    def _bytes(self, start, size):
        if start + size <= len(self.data):
            return self.data[start:start + size]
        return self._get(start, size, 'header')

    def _ifd(self, off):
        import struct
        n = struct.unpack('<H', self._bytes(off, 2))[0]
        raw = self._bytes(off + 2, n * 12 + 4)
        out = {}
        for k in range(n):
            tag, typ, count, value = struct.unpack('<HHII', raw[12 * k:12 * k + 12])
            if tag not in self.TAGS or typ not in self.TYPES:
                continue
            code, size = self.TYPES[typ]
            total = size * count
            blob = raw[12 * k + 8:12 * k + 8 + total] if total <= 4 else self._bytes(value, total)
            if code == 's':
                out[self.TAGS[tag]] = blob.decode('latin-1')
            else:
                out[self.TAGS[tag]] = list(struct.unpack(f'<{count}{code}', blob))
        return out, struct.unpack('<I', raw[n * 12:n * 12 + 4])[0]

    def decode(self, level, bx, by):
        """The decoded block of a level, float32, NaN at nodata, cropped to the raster (a GLO-90 overview of 300 x 300
        pixels lies in one block of 2048 x 2048)."""
        import zlib
        import numpy as np
        L = self.levels[level]
        per_row = -(-L['width'] // L['tw'])
        k = by * per_row + bx
        start, size = int(L['offsets'][k]), int(L['counts'][k])
        name = f'{level}_{bx}_{by}.bin'
        raw = self._find(name)
        if raw is None:
            raw = self._get(start, size, 'block')
            self._put(name, raw)
        data = zlib.decompress(raw) if L['compression'] in (8, 32946) else raw
        tw, th = L['tw'], L['th']
        if L['predictor'] == 3:
            b = np.cumsum(np.frombuffer(data, np.uint8).reshape(th, 4 * tw), axis=1, dtype=np.uint8).reshape(th, 4, tw)
            arr = b.transpose(0, 2, 1)[:, :, ::-1].copy().view('<f4').reshape(th, tw)
        else:
            arr = np.frombuffer(data, '<f4').reshape(th, tw)
            if L['predictor'] == 2:
                arr = np.cumsum(arr, axis=1, dtype=np.float32)
        arr = np.array(arr[:min(th, L['height'] - by * th), :min(tw, L['width'] - bx * tw)], np.float32)
        if self.nodata is not None:
            arr[arr == self.nodata] = np.nan
        return arr


def tile_name(lat, lon):
    """
    The (ns, ew) name parts of the 1-degree DEM tile holding (lat, lon).

    Examples
    --------
    >>> tile_name(40.8, -0.2)
    ('N40', 'W001')
    """
    la, lo = int(math.floor(lat)), int(math.floor(lon))
    return (f'N{la:02d}' if la >= 0 else f'S{-la:02d}'), (f'E{lo:03d}' if lo >= 0 else f'W{-lo:03d}')


class Heights:
    """
    Ellipsoidal terrain heights of the GLO-90 overview DEM_LEVEL (360 m) plus the EGM2008 geoid, read window by window:
    `window(south, north, west, east)` gives (lat axis ascending, lon axis ascending, heights); `at(grid, lat, lon)`
    samples it bilinearly. caches: the tile cache folders (each holds glo90/<tile>/), read in order, the last one written.
    Per process: the decoded blocks in an LRU of `block_bytes`, the COG headers of `tiles` tiles, the geoid of
    `geoid_cells` 1-degree cells.

    Examples
    --------
    >>> Heights([CACHE + '/heights']).window(46.0, 46.1, 10.0, 10.1)[2].shape
    (36, 36)
    """
    GEOID_CELL = round(1 / GEOID_STEP)

    def __init__(self, caches, session=None, block_bytes=BLOCK_BYTES, geoid_cells=GEOID_CELLS, tiles=4096):
        self.caches, self.session, self.stats = list(caches), session, Counter()
        self.tiles, self.max_tiles = collections.OrderedDict(), tiles
        self.blocks, self.block_bytes, self.held = collections.OrderedDict(), block_bytes, 0
        self.geoid, self.geoid_cells = collections.OrderedDict(), geoid_cells

    @staticmethod
    def step():
        """The grid step in degrees of latitude."""
        return 3.0 / 3600 * 2 ** DEM_LEVEL

    def pixel_m(self):
        """The ground size of a pixel along latitude, metres."""
        return self.step() * 111320.0

    def tile(self, ns, ew):
        """The COG of a tile, None where the bucket holds none."""
        key = (ns, ew)
        if key in self.tiles:
            self.tiles.move_to_end(key)
            return self.tiles[key]
        if self.session is None:
            import requests
            self.session = requests.Session()
        try:
            cog = COG(GLO90.format(ns=ns, ew=ew), self.session, self.stats,
                      [os.path.join(c, 'glo90', f'{ns}{ew}') for c in self.caches])
        except Missing:
            cog = None
        self.tiles[key] = cog
        if len(self.tiles) > self.max_tiles:
            self.tiles.popitem(last=False)
        return cog

    def block(self, cog, bx, by):
        key = (cog.url, bx, by)
        arr = self.blocks.get(key)
        if arr is not None:
            self.blocks.move_to_end(key)
            self.stats['block hits'] += 1
            return arr
        arr = cog.decode(DEM_LEVEL, bx, by)
        self.stats['block reads'] += 1
        self.blocks[key] = arr
        self.held += arr.nbytes
        while self.held > self.block_bytes and len(self.blocks) > 1:
            _, old = self.blocks.popitem(last=False)
            self.held -= old.nbytes
        return arr

    def read(self, cog, r0, r1, c0, c1):
        """Rows r0..r1-1 and columns c0..c1-1 of the level (clipped to the raster by the caller)."""
        import numpy as np
        L = cog.levels[DEM_LEVEL]
        out = np.empty((r1 - r0, c1 - c0), np.float32)
        for by in range(r0 // L['th'], (r1 - 1) // L['th'] + 1):
            for bx in range(c0 // L['tw'], (c1 - 1) // L['tw'] + 1):
                blk = self.block(cog, bx, by)
                ra, rb = max(r0, by * L['th']), min(r1, (by + 1) * L['th'])
                ca, cb = max(c0, bx * L['tw']), min(c1, (bx + 1) * L['tw'])
                out[ra - r0:rb - r0, ca - c0:cb - c0] = blk[ra - by * L['th']:rb - by * L['th'], ca - bx * L['tw']:cb - bx * L['tw']]
        return out

    def geoid_cell(self, i, j):
        """EGM2008 (m) on the GEOID_STEP lattice of the 1-degree cell of lattice rows GEOID_CELL i.. and columns
        GEOID_CELL j.. (latitudes clipped to +-90; j of -180..179 degrees)."""
        import numpy as np
        from insardev_toolkit.utils_geoid import geoid_height
        key = (i, j)
        cell = self.geoid.get(key)
        if cell is not None:
            self.geoid.move_to_end(key)
            return cell
        n = self.GEOID_CELL
        lat = np.clip(np.arange(n * i, n * i + n) * GEOID_STEP, -90, 90)
        lon = np.arange(n * j, n * j + n) * GEOID_STEP
        cell = geoid_height(lat, lon, 'EGM2008', grid=True)
        self.stats['geoid cells computed'] += 1
        self.geoid[key] = cell
        if len(self.geoid) > self.geoid_cells:
            self.geoid.popitem(last=False)
        return cell

    def geoid_grid(self, klat, klon):
        """EGM2008 (m) at the lattice points klat x klon (integers: GEOID_STEP x k degrees; longitudes may pass 180)."""
        import numpy as np
        n = self.GEOID_CELL
        half = round(180 / GEOID_STEP)
        out = np.empty((len(klat), len(klon)))
        ci = klat // n
        kn = (klon + half) % (2 * half) - half
        cj = kn // n
        for i in np.unique(ci):
            rows = np.nonzero(ci == i)[0]
            for j in np.unique(cj):
                cols = np.nonzero(cj == j)[0]
                cell = self.geoid_cell(int(i), int(j))
                out[np.ix_(rows, cols)] = cell[np.ix_(klat[rows] - n * i, kn[cols] - n * j)]
        return out

    def window(self, south, north, west, east):
        """
        (lat axis, lon axis, ellipsoidal heights) covering the box (longitudes continuous, west < east, may pass 180),
        with two pixels more on each side.
        """
        import numpy as np
        from scipy.ndimage import map_coordinates
        tiles = []
        for la in range(int(math.floor(south - 0.01)), int(math.floor(north + 0.01)) + 1):
            for lo in range(int(math.floor(west - 0.01)), int(math.floor(east + 0.01)) + 1):
                lo_n = (lo + 180) % 360 - 180
                tiles.append((la, lo, self.tile(*tile_name(la + 0.5, lo_n + 0.5))))
        dy = self.step()
        present = [t[2] for t in tiles if t[2] is not None]
        if present:
            finest = min(present, key=lambda c: c.levels[DEM_LEVEL]['dx'])
            dx = finest.levels[DEM_LEVEL]['dx']
            py = ((finest.north - 0.5 * dy) / dy) % 1.0
            px = ((finest.west + 0.5 * dx) / dx) % 1.0
        else:
            dx, py, px = dy, 0.0, 0.0
        r0, r1 = math.floor(south / dy - py) - 2, math.ceil(north / dy - py) + 2
        c0, c1 = math.floor(west / dx - px) - 2, math.ceil(east / dx - px) + 2
        lat = (np.arange(r0, r1 + 1) + py) * dy
        lon = (np.arange(c0, c1 + 1) + px) * dx
        z = np.zeros((len(lat), len(lon)), np.float32)
        for la, lo, cog in tiles:
            if cog is None:
                continue
            L = cog.levels[DEM_LEVEL]
            lo_shift = lo - ((lo + 180) % 360 - 180)
            iy = np.nonzero((lat > cog.south) & (lat < cog.north))[0]
            ix = np.nonzero((lon - lo_shift > cog.west) & (lon - lo_shift < cog.east))[0]
            if not len(iy) or not len(ix):
                continue
            rows = np.clip(((cog.north - lat[iy]) / L['dy']).astype(int), 0, L['height'] - 1)
            cols = np.clip(((lon[ix] - lo_shift - cog.west) / L['dx']).astype(int), 0, L['width'] - 1)
            w = self.read(cog, rows.min(), rows.max() + 1, cols.min(), cols.max() + 1)
            z[np.ix_(iy, ix)] = w[np.ix_(rows - rows.min(), cols - cols.min())]
        z = np.nan_to_num(z, nan=0.0)
        klat = np.arange(math.floor(lat[0] / GEOID_STEP) - 1, math.ceil(lat[-1] / GEOID_STEP) + 2)
        klon = np.arange(math.floor(lon[0] / GEOID_STEP) - 1, math.ceil(lon[-1] / GEOID_STEP) + 2)
        N = self.geoid_grid(klat, klon)
        gi = (lat - klat[0] * GEOID_STEP) / GEOID_STEP
        gj = (lon - klon[0] * GEOID_STEP) / GEOID_STEP
        z += map_coordinates(N, np.meshgrid(gi, gj, indexing='ij'), order=1, mode='nearest').astype(np.float32)
        return lat, lon, z

    @staticmethod
    def at(grid, lat, lon):
        """Bilinear heights of a window grid at points (lon on the grid's side of 180)."""
        import numpy as np
        from scipy.ndimage import map_coordinates
        glat, glon, z = grid
        i = (np.asarray(lat, float) - glat[0]) / (glat[1] - glat[0])
        j = (np.asarray(lon, float) - glon[0]) / (glon[1] - glon[0])
        return map_coordinates(z, [i.ravel(), j.ravel()], order=1, mode='nearest').reshape(np.shape(lat))


def _box(lat, lon):
    """
    (south, north, west, east, ref) of points, longitudes kept continuous around their circular mean `ref` (a median
    of longitudes split across 180 lies near 0 and makes the box span the globe).

    Examples
    --------
    >>> [round(v, 2) for v in _box([1.0, 2.0], [179.9, -179.9])]
    [1.0, 2.0, 179.9, 180.1, 180.0]
    """
    import numpy as np
    lon = np.asarray(lon, float)
    r = np.radians(lon)
    ref = float(np.degrees(np.arctan2(np.mean(np.sin(r)), np.mean(np.cos(r)))))
    lon = (lon - ref + 180.0) % 360.0 - 180.0 + ref
    return float(np.min(lat)), float(np.max(lat)), float(np.min(lon)), float(np.max(lon)), ref


class HeightRange:
    """
    The smallest and largest height of a window grid over index rectangles: a sparse table of minima and maxima over
    2^ky x 2^kx blocks, each level built when a query first needs it.

    Examples
    --------
    >>> import numpy as np
    >>> z = np.arange(20.0).reshape(4, 5)
    >>> [v.tolist() for v in HeightRange(z).query(np.array([0, 1]), np.array([1, 3]), np.array([0, 2]), np.array([2, 2]))]
    [[0.0, 7.0], [7.0, 17.0]]
    """

    def __init__(self, z):
        import numpy as np
        z = np.asarray(z, float)
        self.ny, self.nx = z.shape
        self.levels = {(0, 0): (z, z)}

    def _level(self, ky, kx):
        import numpy as np
        key = (ky, kx)
        if key not in self.levels:
            if kx == 0:
                lo, hi = self._level(ky - 1, 0)
                s = 1 << (ky - 1)
                self.levels[key] = (np.minimum(lo[:-s], lo[s:]), np.maximum(hi[:-s], hi[s:]))
            else:
                lo, hi = self._level(ky, kx - 1)
                s = 1 << (kx - 1)
                self.levels[key] = (np.minimum(lo[:, :-s], lo[:, s:]), np.maximum(hi[:, :-s], hi[:, s:]))
        return self.levels[key]

    def query(self, r0, r1, c0, c1):
        """(minima, maxima) over the rows r0..r1 and columns c0..c1 (inclusive integer arrays, clipped to the grid)."""
        import numpy as np
        r0, r1 = np.clip(r0, 0, self.ny - 1), np.clip(r1, 0, self.ny - 1)
        c0, c1 = np.clip(c0, 0, self.nx - 1), np.clip(c1, 0, self.nx - 1)
        ky = np.floor(np.log2(r1 - r0 + 1)).astype(int)
        kx = np.floor(np.log2(c1 - c0 + 1)).astype(int)
        mn, mx = np.empty(len(r0)), np.empty(len(r0))
        keys = ky * 64 + kx
        for key in np.unique(keys):
            m = keys == key
            a, b = int(key) // 64, int(key) % 64
            lo, hi = self._level(a, b)
            ra, rb, ca, cb = r0[m], r1[m] - (1 << a) + 1, c0[m], c1[m] - (1 << b) + 1
            mn[m] = np.minimum(np.minimum(lo[ra, ca], lo[ra, cb]), np.minimum(lo[rb, ca], lo[rb, cb]))
            mx[m] = np.maximum(np.maximum(hi[ra, ca], hi[ra, cb]), np.maximum(hi[rb, ca], hi[rb, cb]))
        return mn, mx


class Piece:
    """
    The DEM window of a piece of an edge (the box of its ground points at the HEIGHT_SPAN heights, `_box`): its grid, the
    reference longitude, the first height bracket [lo, hi] (the window's heights -1 / +1 m) and `span(lat, lon)`, the
    heights of the grid nodes that bilinear sampling of the hull of (n, k) points uses (their index box and one node more on
    each side).

    Examples
    --------
    >>> pc = Piece(Heights([CACHE + '/heights']), [46.0, 46.1], [10.0, 10.1])
    >>> bool(pc.lo < pc.hi), [float(v) for v in pc.span(np.array([[46.05]]), np.array([[10.05]]))[0]] >= [pc.lo]
    (True, True)
    """

    def __init__(self, heights, lat, lon):
        import numpy as np
        s, n, w, e, self.ref = _box(lat, lon)
        self.grid = heights.window(s, n, w, e)
        glat, glon, z = self.grid
        self.lo, self.hi = float(z.min()) - 1.0, float(z.max()) + 1.0
        self.range = HeightRange(z)
        self.la0, self.dla, self.lo0, self.dlo = glat[0], glat[1] - glat[0], glon[0], glon[1] - glon[0]

    def lon(self, lon):
        """Longitudes on this window's side of 180."""
        return (lon - self.ref + 180.0) % 360.0 - 180.0 + self.ref

    def span(self, lat, lon):
        import numpy as np
        i = (lat - self.la0) / self.dla
        j = (self.lon(lon) - self.lo0) / self.dlo
        return self.range.query(np.floor(i.min(axis=1)).astype(int) - 1, np.floor(i.max(axis=1)).astype(int) + 2,
                                np.floor(j.min(axis=1)).astype(int) - 1, np.floor(j.max(axis=1)).astype(int) + 2)


def _ground(S, d, r, R, th):
    """(lat, lon, h) of circle points."""
    return geodetic(circle(S, d, r, R, th))


def prepare(orbit, t, R):
    """
    The points (t seconds of the orbit's day, R slant ranges m) of an edge: the zero-Doppler plane, and the ground points
    at the heights HEIGHT_SPAN and their middle (theta and lat, lon; longitudes continuous with the first), from which
    `at_height` gives the ground point of any height by quadratic interpolation (index/IDX1e_report.md: within 9 m), and
    the ground distance per metre of height, cot (the largest of the two halves).

    Examples
    --------
    >>> p = prepare(orbit, np.array([t0]), np.array([near]))
    """
    import numpy as np
    S, V, d, r = plane(orbit, t)
    R = np.asarray(R, float)
    h0, h2 = HEIGHT_SPAN
    th0 = theta_at(S, d, r, R, h0)
    th2 = theta_at(S, d, r, R, h2, th0)
    th1 = theta_at(S, d, r, R, 0.5 * (h0 + h2), 0.5 * (th0 + th2))
    P = [circle(S, d, r, R, th) for th in (th0, th1, th2)]
    la, lo, _ = geodetic(np.concatenate(P))
    n = len(R)
    lo = lo.reshape(3, n)
    lo = (lo - lo[0] + 180.0) % 360.0 - 180.0 + lo[0]
    half = 0.5 * (h2 - h0)
    cot = np.maximum(np.linalg.norm(P[1] - P[0], axis=-1), np.linalg.norm(P[2] - P[1], axis=-1))
    cot = np.sqrt(np.maximum(cot * cot - half * half, 0.0)) / half
    return dict(S=S, d=d, r=r, R=R, th=np.stack([th0, th1, th2]), la=la.reshape(3, n), lo=lo, cot=cot)


def quadratic(la, lo):
    """The coefficients (c0, c1, c2), each (2, n), of lat and lon (rows) as c0 + c1 s + c2 s^2 through the ground points
    at HEIGHT_SPAN and its middle (la, lo (3, n); s = 0, 1/2, 1)."""
    import numpy as np
    v = np.stack([la, lo], 1)
    return v[0], -3 * v[0] + 4 * v[1] - v[2], 2 * v[0] - 4 * v[1] + 2 * v[2]


def at_height(q, idx, h):
    """
    The ground lat, lon of the points idx of `quadratic` q at the heights h (arrays): quadratic in h through HEIGHT_SPAN
    and its middle; longitudes continuous with the point's at HEIGHT_SPAN[0].

    Examples
    --------
    >>> import numpy as np
    >>> q = quadratic(np.array([[0.0], [1.0], [2.0]]), np.array([[5.0], [5.0], [5.0]]))
    >>> [v.tolist() for v in at_height(q, np.array([0]), np.array([HEIGHT_SPAN[1]]))]
    [[2.0], [5.0]]
    """
    h0, h2 = HEIGHT_SPAN
    s = (h - h0) / (h2 - h0)
    c0, c1, c2 = (c[:, idx] for c in q)
    v = c0 + s * (c1 + s * c2)
    return v[0], v[1]


def narrow(pieces, pid, corners, iterations=3):
    """
    The height bracket [a, b] of each band (pieces[pid] its window): from the window's bracket, narrowed at most
    `iterations` times to the heights of the grid nodes under the band's ground for [a, b] (corners(a, b, rows) ->
    (lat, lon), (len(rows), k)); a band stops when its bracket no longer changes. Every terrain point of the band whose
    height lies in [a, b] keeps it in the narrowed [a, b].
    """
    import numpy as np
    a = np.array([pieces[q].lo for q in pid], float)
    b = np.array([pieces[q].hi for q in pid], float)
    rows = np.arange(len(pid))
    for _ in range(iterations):
        la, lo = corners(a[rows], b[rows], rows)
        mn, mx = np.empty(len(rows)), np.empty(len(rows))
        for q in np.unique(pid[rows]):
            m = pid[rows] == q
            mn[m], mx[m] = pieces[q].span(la[m], lo[m])
        a2, b2 = np.maximum(a[rows], mn), np.minimum(b[rows], mx)
        changed = (a2 != a[rows]) | (b2 != b[rows])
        a[rows], b[rows] = a2, b2
        rows = rows[changed]
        if not len(rows):
            break
    return a, b


def roots(p, far, pieces, pid, heights, scan=SCAN):
    """
    The terrain point of each prepared point (`prepare`): its height bracket narrowed to the terrain of its own in-plane
    band (`narrow`); a bracket narrower than FLAT by iteration, the others by the scan of f(theta) = hgeo - H in steps of
    `scan` DEM pixel over [theta(a - 2 m), theta(b + 2 m)], refined linearly: the root nearest the track, or the farthest
    where `far`.

    Returns
    -------
    tuple
        lat, lon (-180..180), h arrays.
    """
    import numpy as np
    S, d, r, R = p['S'], p['d'], p['r'], p['R']
    n = len(R)

    q = quadratic(p['la'], p['lo'])

    def own(aa, bb, m):
        la1, lo1 = at_height(q, m, aa)
        la2, lo2 = at_height(q, m, bb)
        return np.stack([la1, la2], 1), np.stack([lo1, lo2], 1)
    a, b = narrow(pieces, pid, own)
    h0, h2 = HEIGHT_SPAN

    def guess(h, k):
        s = (h - h0) / (h2 - h0)
        th = p['th'][:, k]
        return (1 - s) * (1 - 2 * s) * th[0] + 4 * s * (1 - s) * th[1] + s * (2 * s - 1) * th[2]

    def terrain_at(la, lo, q):
        out = np.empty(len(la))
        for v in np.unique(q):
            m = q == v
            out[m] = Heights.at(pieces[v].grid, la[m], pieces[v].lon(lo[m]))
        return out
    th = np.empty(n)
    flat = np.nonzero(b - a < FLAT)[0]
    if len(flat):
        k = flat
        t = theta_at(S[k], d[k], r[k], R[k], 0.5 * (a[k] + b[k]), guess(0.5 * (a[k] + b[k]), k))
        for _ in range(2):
            la, lo, _ = _ground(S[k], d[k], r[k], R[k], t)
            t = theta_at(S[k], d[k], r[k], R[k], terrain_at(la, lo, pid[k]), t)
        th[k] = t
    k = np.nonzero(b - a >= FLAT)[0]
    if len(k):
        Sk, dk, rk, Rk = S[k], d[k], r[k], R[k]
        t_lo = theta_at(Sk, dk, rk, Rk, a[k] - 2.0, guess(a[k] - 2.0, k))
        t_hi = theta_at(Sk, dk, rk, Rk, b[k] + 2.0, guess(b[k] + 2.0, k))
        reach = np.linalg.norm(circle(Sk, dk, rk, Rk, t_hi) - circle(Sk, dk, rk, Rk, t_lo), axis=-1)
        m = np.ceil(reach / (scan * heights.pixel_m())).astype(int) + 2
        start = np.concatenate([[0], np.cumsum(m)[:-1]])
        owner = np.repeat(np.arange(len(k)), m)
        tot = len(owner)
        u = (np.arange(tot) - start[owner]) / (m[owner] - 1)
        TH = t_lo[owner] + (t_hi - t_lo)[owner] * u
        la, lo, hg = _ground(Sk[owner], dk[owner], rk[owner], Rk[owner], TH)
        f = hg - terrain_at(la, lo, pid[k][owner])
        last = start + m - 1
        cross = np.zeros(tot, bool)
        cross[:-1] = (f[:-1] < 0) & (f[1:] >= 0)
        cross[last] = False
        pos = np.arange(tot)
        first_c = np.minimum.reduceat(np.where(cross, pos, tot), start)
        last_c = np.maximum.reduceat(np.where(cross, pos, -1), start)
        has = first_c < tot
        kk = np.where(far[k], last_c, first_c)
        if not has.all():
            # no crossing: the sample of the smallest |f| (not the last of the point)
            af = np.abs(f)
            af[last] = np.inf
            kk = np.where(has, kk, np.lexsort((af, owner))[start])
            heights.stats['unbracketed points'] += int((~has).sum())
        f0, f1 = f[kk], f[kk + 1]
        frac = np.where(has, np.clip(f0 / np.where(f0 != f1, f0 - f1, 1.0), 0, 1), 0.0)
        th[k] = TH[kk] + frac * (TH[kk + 1] - TH[kk])
    return _ground(S, d, r, R, th)


def edges(orbit, t_first, t_last, ranges, heights, info=None):
    """
    The four edges of a footprint, sampled by the terrain: near (t_first -> t_last at R_near), stop line (t_last, R_near
    -> R_far), far (t_last -> t_first at R_far), start line (t_first, R_far -> R_near). t in seconds of the orbit's day;
    ranges = (R_near, R_far) metres.
    - Each edge of ground length L is a lattice of N = floor(L / FLOOR) equal steps (at least one); its points are first
      computed every 2^k steps, the largest 2^k steps not above COARSE (and the last point);
    - an interval between two computed points (i, j) is halved while j - i >= 2 and its band, the ground the edge can take
      between them for the terrain heights found there (`narrow` on the corners of both points at [a, b]), is wider than
      BAND_LIMIT: (b - a) x cot(incidence) > BAND_LIMIT;
    - DEM windows: one per PIECE metres of an edge (whole coarse intervals).
    info (a dict) gets the number of points and levels.

    Returns
    -------
    dict
        near, stop, far, start: (lat, lon, h) arrays of the computed points in edge order.

    Examples
    --------
    >>> e = edges(orbit, t0, t1, slant_ranges(orbit, 0.5 * (t0 + t1), (16.96, 23.53)), heights)
    """
    import numpy as np
    near, far = ranges
    t_mid = 0.5 * (t_first + t_last)
    S, V, d, r = plane(orbit, [t_mid])
    v_ground = float(np.linalg.norm(V[0])) * WGS_A / float(np.linalg.norm(S[0]))
    RR = np.array([near, far])
    SS, dd, rr = np.repeat(S, 2, 0), np.repeat(d, 2, 0), np.repeat(r, 2, 0)
    P = circle(SS, dd, rr, RR, theta_at(SS, dd, rr, RR, 0.0))
    across = float(np.linalg.norm(P[1] - P[0]))
    # per edge: (t at u = 0, t at u = 1, R at 0, R at 1, ground length, far side)
    spec = [(t_first, t_last, near, near, (t_last - t_first) * v_ground, False),
            (t_last, t_last, near, far, across, False),
            (t_last, t_first, far, far, (t_last - t_first) * v_ground, True),
            (t_first, t_first, far, near, across, False)]
    N = np.array([max(1, int(math.floor(L / FLOOR))) for *_, L, _ in spec])
    step = np.array([L for *_, L, _ in spec]) / N
    cs = np.ones(4, int)   # the coarse step in lattice steps: the largest 2^k with 2^k x step <= COARSE (at least 1)
    for e in range(4):
        while 2 * cs[e] * step[e] <= COARSE:
            cs[e] *= 2
    pu = np.maximum(1, np.floor(PIECE / (cs * step)).astype(int)) * cs
    npieces = -(-N // pu)
    off = np.concatenate([[0], np.cumsum(N + 1)[:-1]])
    pbase = np.concatenate([[0], np.cumsum(npieces)[:-1]])
    total = int((N + 1).sum())
    edge_of = np.repeat(np.arange(4), N + 1)
    index_of = np.arange(total) - off[edge_of]
    ta, tb, ra, rb = (np.array([s[k] for s in spec]) for k in range(4))
    is_far = np.array([s[5] for s in spec])
    lat, lon, hgt = np.full(total, np.nan), np.full(total, np.nan), np.full(total, np.nan)
    store = dict(la=np.full((3, total), np.nan), lo=np.full((3, total), np.nan), cot=np.full(total, np.nan))
    pieces = []

    def prepared(g):
        """prepare() of the global points g, kept in `store`."""
        e = edge_of[g]
        u = index_of[g] / N[e]
        p = prepare(orbit, ta[e] + u * (tb[e] - ta[e]), ra[e] + u * (rb[e] - ra[e]))
        store['la'][:, g], store['lo'][:, g], store['cot'][g] = p['la'], p['lo'], p['cot']
        return p

    def solve(g, p):
        e = edge_of[g]
        pid = pbase[e] + np.minimum(index_of[g] // pu[e], npieces[e] - 1)
        lat[g], lon[g], hgt[g] = roots(p, is_far[e], pieces, pid, heights)

    coarse = np.nonzero((index_of % cs[edge_of] == 0) | (index_of == N[edge_of]))[0]
    p = prepared(coarse)
    for e in range(4):
        for q in range(npieces[e]):
            g = coarse[(edge_of[coarse] == e) & (index_of[coarse] >= q * pu[e]) & (index_of[coarse] <= (q + 1) * pu[e])]
            pieces.append(Piece(heights, store['la'][:, g].ravel(), store['lo'][:, g].ravel()))
    solve(coarse, p)
    # the intervals between consecutive coarse points of an edge
    gi = coarse[:-1][edge_of[coarse[:-1]] == edge_of[coarse[1:]]]
    gj = coarse[1:][edge_of[coarse[:-1]] == edge_of[coarse[1:]]]
    levels = 0
    while len(gi):
        levels += 1
        e = edge_of[gi]
        ipid = pbase[e] + index_of[gi] // pu[e]
        cot = np.maximum(store['cot'][gi], store['cot'][gj])
        lo_j = (store['lo'][:, gj] - store['lo'][0, gi] + 180.0) % 360.0 - 180.0 + store['lo'][0, gi]
        qi = quadratic(store['la'][:, gi], store['lo'][:, gi])
        qj = quadratic(store['la'][:, gj], lo_j)

        def band(aa, bb, m):
            la1, lo1 = at_height(qi, m, aa)
            la2, lo2 = at_height(qi, m, bb)
            la3, lo3 = at_height(qj, m, aa)
            la4, lo4 = at_height(qj, m, bb)
            return np.stack([la1, la2, la3, la4], 1), np.stack([lo1, lo2, lo3, lo4], 1)
        a, b = narrow(pieces, ipid, band)
        split = ((b - a) * cot > BAND_LIMIT) & (gj - gi >= 2)
        gi, gj = gi[split], gj[split]
        if not len(gi):
            break
        mid = gi + (gj - gi) // 2
        solve(mid, prepared(mid))
        gi, gj = np.concatenate([gi, mid]), np.concatenate([mid, gj])
    done = ~np.isnan(lat)
    if info is not None:
        info.update(points=int(done.sum()), levels=levels, pieces=len(pieces))
    out = {}
    for e, name in enumerate(('near', 'stop', 'far', 'start')):
        g = np.nonzero(done & (edge_of == e))[0]
        out[name] = (lat[g], lon[g], hgt[g])
    return out


def douglas_peucker(x, y, tolerance):
    """
    The indices of a polyline's vertices kept by Douglas-Peucker: every dropped point lies within `tolerance` of the
    kept polyline (the first and last points are kept).

    Examples
    --------
    >>> import numpy as np
    >>> douglas_peucker(np.array([0.0, 1, 2, 3]), np.array([0.0, 0.1, -0.1, 0]), 0.5).tolist()
    [0, 3]
    """
    import numpy as np
    keep = np.zeros(len(x), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(x) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        dx, dy = x[j] - x[i], y[j] - y[i]
        L = math.hypot(dx, dy)
        px, py = x[i + 1:j] - x[i], y[i + 1:j] - y[i]
        if L == 0:
            dist = np.hypot(px, py)
        else:
            t = np.clip((px * dx + py * dy) / (L * L), 0, 1)
            dist = np.hypot(px - t * dx, py - t * dy)
        k = int(np.argmax(dist))
        if dist[k] > tolerance:
            keep[i + 1 + k] = True
            stack += [(i, i + 1 + k), (i + 1 + k, j)]
    return np.nonzero(keep)[0]


def outline(e, tolerance=TOLERANCE):
    """
    The footprint polygon of `edges`: each edge simplified by Douglas-Peucker to `tolerance` metres in the tangent plane
    of the first near point (the corners kept), joined as the edges run, the first vertex not repeated; not widened;
    longitudes -180..180 as computed (`frame360` sets the convention). tolerance 0 keeps every point.

    Returns
    -------
    list of (lat, lon)

    Examples
    --------
    >>> len(outline(edges(orbit, t0, t1, ranges, heights))) >= 4
    True
    """
    import numpy as np
    lat0, lon0 = float(e['near'][0][0]), float(e['near'][1][0])
    pts = []
    for name in ('near', 'stop', 'far', 'start'):
        la, lo = e[name][0], e[name][1]
        if tolerance > 0:
            x, y = tangent(lat0, lon0, la, lo)
            keep = douglas_peucker(np.asarray(x), np.asarray(y), tolerance)
        else:
            keep = np.arange(len(la))
        pts += [(float(la[k]), float(lo[k])) for k in keep[:-1]]
    return pts


def footprint(first, last, looks, heights, orbit, info=None):
    """
    The outline of a window: (lat, lon) vertices (`frame360` longitudes). first, last: the window, seconds since 1970;
    looks: (look_near, look_far) degrees; heights: `Heights`; orbit: `scene_orbit` of the window; info: see `edges`.

    Examples
    --------
    >>> reader = OrbitReader(REPO)
    >>> orbit = reader.select('ENVISAT', 1200516432.0, 1200516451.0)[0]
    >>> len(footprint(1200516432.0, 1200516451.0, (16.48, 23.18), Heights([CACHE + '/heights']), orbit)) > 3
    True
    """
    t0, t1 = day_seconds(orbit, first), day_seconds(orbit, last)
    ranges = slant_ranges(orbit, 0.5 * (t0 + t1), looks)
    return frame360(outline(edges(orbit, t0, t1, ranges, heights, info), TOLERANCE))


def units_text(k, decimals):
    """
    The decimal text of an integer number of 10^-decimals units.

    Examples
    --------
    >>> units_text(-1234, 4), units_text(5, 2), units_text(-5, 2)
    ('-0.1234', '0.05', '-0.05')
    """
    sign, k = ('-' if k < 0 else ''), abs(k)
    return f'{sign}{k // 10 ** decimals}.{k % 10 ** decimals:0{decimals}d}'


def text_units(text, decimals):
    """
    The integer number of 10^-decimals units of a decimal text with exactly that many decimals.

    Examples
    --------
    >>> text_units('-0.1234', 4), text_units('181.0500', 4)
    (-1234, 1810500)
    """
    sign = -1 if text.startswith('-') else 1
    whole, frac = text.lstrip('-').split('.')
    assert len(frac) == decimals, text
    return sign * (int(whole) * 10 ** decimals + int(frac))


def footprint_text(points):
    """
    'lat lon lat lon ...' with 4 decimals.

    Examples
    --------
    >>> footprint_text([(45.12344, 179.99996), (-0.00001, 10.0)])
    '45.1234 180.0000 0.0000 10.0000'
    """
    return ' '.join(f'{units_text(round(la * 1e4), 4)} {units_text(round(lo * 1e4), 4)}' for la, lo in points)


def footprint_key(pid, first_ms, last_ms, sat, swath, phase, looks, zips):
    """The SHA-256 of a row's footprint inputs."""
    h = hashlib.sha256()
    for part in (FOOTPRINT_VERSION, DEM_SOURCE, pid, str(first_ms), str(last_ms), sat, swath, phase, repr(looks[0]),
                 repr(looks[1]), *[f'{p} {sha}' for p, sha in zips]):
        h.update(part.encode() + b'\n')
    return h.hexdigest()


def iso_ms(text):
    """
    Milliseconds since 1970 of 'YYYY-MM-DDTHH:MM:SS.mmmZ'.

    Examples
    --------
    >>> iso_ms('1970-01-01T00:00:01.500Z')
    1500
    """
    import calendar
    return calendar.timegm(time.strptime(text[:19], '%Y-%m-%dT%H:%M:%S')) * 1000 + int(text[20:23])


def read_rows(path):
    with open(path, encoding='utf-8') as fh:
        lines = fh.read().splitlines()
    header = lines[0].split('\t')
    assert tuple(header) == ROW_COLUMNS, path
    return [dict(zip(header, line.split('\t'))) for line in lines[1:]]


def row_window(row):
    """The acquisition of a row in ms since 1970: begin + (t_first_ms - node_ms), begin + (t_last_ms - node_ms)."""
    b = iso_ms(row['begin'])
    return b + int(row['t_first_ms']) - int(row['node_ms']), b + int(row['t_last_ms']) - int(row['node_ms'])


def footprint_window(row):
    """The window of a row's orbit selection and footprint in ms since 1970: ESA's processing window of the product, its
    acquisition (row_window) less PROCESS_BEFORE and plus PROCESS_AFTER."""
    first_ms, last_ms = row_window(row)
    return first_ms - round(PROCESS_BEFORE * 1000), last_ms + round(PROCESS_AFTER * 1000)


def read_store(path):
    """The lines of a footprint store file as dicts by its header (empty when absent). A store written before the
    productId column (FOOTPRINT_COLUMNS) is read as well: its keys and footprints are reused, the footprints stage rewrites
    it."""
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as fh:
        lines = fh.read().splitlines()
    header = lines[0].split('\t')
    assert 'key' in header and 'footprint' in header, path
    return [dict(zip(header, line.split('\t'))) for line in lines[1:]]


WORKER = {}


def _fp_start(repo, cache):
    WORKER.update(looks=read_look_rows(repo), heights=Heights([os.path.join(cache, 'heights')]), reader=OrbitReader(repo))


def _fp_unit(task):
    """The footprints of one track file of rows, in its row order (time): the store's vertices for the keys it holds,
    the others computed (and appended to a .part file as they come, so that a stopped run keeps them)."""
    mission, field, cache = task
    looks_rows, heights, reader = WORKER['looks'], WORKER['heights'], WORKER['reader']
    rows = read_rows(os.path.join(cache, 'rows', mission, field + '.tsv'))
    store = os.path.join(cache, 'footprints', mission, field + '.tsv')
    part = store + '.part'
    known = {e['key']: e['footprint'] for e in read_store(store) if e['key'] and e['footprint']}
    if os.path.exists(part):
        with open(part, encoding='utf-8') as fh:
            for line in fh.read().splitlines():
                p = line.split('\t')
                if len(p) == 2 and p[1]:
                    known[p[0]] = p[1]
    os.makedirs(os.path.dirname(store), exist_ok=True)
    out, no_orbit = [], []
    res = dict(mission=mission, field=field, rows=len(rows), computed=0, cached=0, cpu=0.0, wall=0.0, select_cpu=0.0)
    before = Counter(heights.stats)
    with open(part, 'a', encoding='utf-8') as ph:
        for row in rows:
            first_ms, last_ms = footprint_window(row)
            sat = row['satellite']
            looks = look_row(looks_rows, sat, row['swath'], row['phase'])
            c0 = time.process_time()
            orbit, zips, reason = reader.select(sat, first_ms / 1000, last_ms / 1000)
            res['select_cpu'] += time.process_time() - c0
            if orbit is None:
                reason = reason.replace('\t', ' ')
                out.append((row['code'], row['productId'], '', '', reason))
                no_orbit.append((mission, row['begin'], row['code'], row['productId'], first_ms, last_ms, reason))
                continue
            key = footprint_key(row['productId'], first_ms, last_ms, sat, row['swath'], row['phase'], looks, zips)
            fp = known.get(key)
            if fp is None:
                c0, w0 = time.process_time(), time.perf_counter()
                fp = footprint_text(footprint(first_ms / 1000, last_ms / 1000, looks, heights, orbit))
                res['cpu'] += time.process_time() - c0
                res['wall'] += time.perf_counter() - w0
                res['computed'] += 1
                known[key] = fp
                ph.write(f'{key}\t{fp}\n')
                ph.flush()
            else:
                res['cached'] += 1
            out.append((row['code'], row['productId'], key, fp, ''))
    data = ('\t'.join(FOOTPRINT_COLUMNS) + '\n' + ''.join('\t'.join(o) + '\n' for o in out)).encode()
    write_if_changed(store, data)
    os.remove(part)
    res['no_orbit'] = no_orbit
    res['heights'] = {k: v - before.get(k, 0) for k, v in heights.stats.items() if v != before.get(k, 0)}
    res['rss_gb'] = peak_gb()
    return res


def reason_class(reason):
    """A no-orbit reason with its numbers, times and file names left out."""
    text = re.sub(r'\S*\d\S*', '#', reason)
    return ' '.join(text.split())[:160]


def stage_footprints(cache, jobs):
    import multiprocessing
    t0 = time.time()
    for name in MISSION.values():
        if not os.path.exists(os.path.join(REPO, name, 'scenes', 'look.csv')):
            sys.exit(f'{name}/scenes/look.csv is missing: the footprints need the look rows')
    rows_root = os.path.join(cache, 'rows')
    tasks = []
    for mission in sorted(set(MISSION.values())):
        folder = os.path.join(rows_root, mission)
        if os.path.isdir(folder):
            for f in sorted(os.listdir(folder)):
                if f.endswith('.tsv'):
                    tasks.append((os.path.getsize(os.path.join(folder, f)), mission, f[:-4]))
    if not tasks:
        sys.exit(f'no rows in {rows_root}: run --stage rows first')
    # the largest track files first (the balance of the processes); the result does not depend on the order
    tasks.sort(key=lambda t: (-t[0], t[1], t[2]))
    os.makedirs(os.path.join(cache, 'heights'), exist_ok=True)
    total, no_orbit, hstats = Counter(), [], Counter()
    rss, done = [], 0
    ctx = multiprocessing.get_context('spawn')
    with ctx.Pool(jobs, _fp_start, (REPO, cache), maxtasksperchild=None) as pool:
        for res in pool.imap_unordered(_fp_unit, [(m, f, cache) for _, m, f in tasks]):
            done += 1
            for k in ('rows', 'computed', 'cached', 'cpu', 'wall', 'select_cpu'):
                total[k] += res[k]
            total[f'{res["mission"]} rows'] += res['rows']
            total[f'{res["mission"]} no orbit'] += len(res['no_orbit'])
            no_orbit += res['no_orbit']
            hstats.update(res['heights'])
            rss.append(res['rss_gb'])
            if done % 50 == 0 or done == len(tasks):
                log(f'footprints: {done} of {len(tasks)} track files, {total["computed"]} computed, {total["cached"]} '
                    f'from the store, {len(no_orbit)} without an orbit, {time.time() - t0:.0f} s')
    no_orbit.sort()
    lines = ['mission\tcode\tproductId\tfirst_ms\tlast_ms\treason']
    lines += [f'{m}\t{c}\t{p}\t{a}\t{b}\t{r}' for m, _, c, p, a, b, r in no_orbit]
    write_if_changed(os.path.join(cache, 'footprints', 'no_orbit.tsv'), ('\n'.join(lines) + '\n').encode())
    classes = Counter()
    for m, _, c, p, a, b, r in no_orbit:
        classes[f'{m}: {reason_class(r)}'] += 1
    stale = []
    for mission in sorted(set(MISSION.values())):
        folder = os.path.join(cache, 'footprints', mission)
        if os.path.isdir(folder):
            names = {f'{f}.tsv' for _, m, f in tasks if m == mission}
            stale += [os.path.join(mission, f) for f in sorted(os.listdir(folder)) if f not in names]
    summary = {'rows': total['rows'], 'footprints': total['rows'] - len(no_orbit), 'no orbit': len(no_orbit),
               'per mission': {k: v for k, v in sorted(total.items()) if k.endswith(('rows', 'no orbit')) and ' ' in k
                               and k.split(' ')[0] in MISSION.values()},
               'no orbit by reason': dict(sorted(classes.items())), 'stale store files': stale}
    write_if_changed(os.path.join(cache, 'footprints', 'summary.json'),
                     (json.dumps(summary, indent=1, sort_keys=True) + '\n').encode())
    n = max(total['computed'], 1)
    log(f'footprints: {total["rows"]} rows: {total["computed"]} computed, {total["cached"]} from the store, '
        f'{len(no_orbit)} without a usable orbit; {jobs} processes, {time.time() - t0:.0f} s wall')
    log(f'time per computed footprint (one process): cpu {total["cpu"] / n:.3f} s, wall {total["wall"] / n:.3f} s; orbit '
        f'selection cpu {total["select_cpu"] / max(total["rows"], 1):.4f} s per row; peak memory of a process '
        f'{max(rss):.2f} GB')
    log('heights: ' + json.dumps(dict(sorted(hstats.items()))))
    for k, v in sorted(classes.items()):
        log(f'  no orbit: {v} {k}')
    if stale:
        log(f'stale store files: {len(stale)}' + ''.join(f'\n  stale: {s}' for s in stale))
    return 0


def hull(points):
    """
    The convex hull of integer points (x, y), counter-clockwise from the least (x, y), collinear points left out
    (Andrew's monotone chain, exact).

    Examples
    --------
    >>> hull([(0, 0), (2, 0), (1, 1), (2, 2), (0, 2), (1, 0)])
    [(0, 0), (2, 0), (2, 2), (0, 2)]
    """
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def inside(poly, p):
    """
    Whether the point p lies in the closed convex polygon poly (counter-clockwise, integers; exact).

    Examples
    --------
    >>> inside([(0, 0), (2, 0), (2, 2), (0, 2)], (2, 1)), inside([(0, 0), (2, 0), (2, 2), (0, 2)], (3, 1))
    (True, False)
    """
    if len(poly) == 1:
        return tuple(p) == tuple(poly[0])
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        c = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        if c < 0 or (len(poly) == 2 and c != 0):
            return False
    if len(poly) == 2:
        return min(poly)[0] <= p[0] <= max(poly)[0] and min(q[1] for q in poly) <= p[1] <= max(q[1] for q in poly)
    return True


def outline_cells(points, cell=100):
    """
    The convex polygon on the lattice of `cell` units that contains the convex hull of integer points: the hull of the
    corners of the lattice cells that hold its vertices (exact).

    Examples
    --------
    >>> outline_cells([(5, 5), (150, 20), (60, 230)])
    [(0, 0), (200, 0), (200, 100), (100, 300), (0, 300)]
    """
    out = []
    for x, y in hull(points):
        x0, y0 = (x // cell) * cell, (y // cell) * cell
        x1, y1 = -((-x) // cell) * cell, -((-y) // cell) * cell
        out += [(x0, y0), (x0, y1), (x1, y0), (x1, y1)]
    return hull(out)


def meets(poly, x0, y0, x1, y1):
    """
    Whether the closed convex polygon poly (counter-clockwise, integers) meets the closed rectangle [x0, x1] x [y0, y1]
    (separating axes, exact).

    Examples
    --------
    >>> meets([(0, 0), (10, 0), (0, 10)], 5, 5, 9, 9), meets([(0, 0), (10, 0), (0, 10)], 6, 6, 9, 9)
    (True, False)
    """
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    if max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1:
        return False
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        nx, ny = -(b[1] - a[1]), b[0] - a[0]
        if nx == 0 and ny == 0:
            continue
        pp = [nx * p[0] + ny * p[1] for p in poly]
        rp = [nx * c[0] + ny * c[1] for c in corners]
        if max(rp) < min(pp) or min(rp) > max(pp):
            return False
    return True


def tile_of(x0, y0):
    """
    The name of the 5-degree tile of south-west corner (x0, y0) in 1e-4 degree units (longitude in any frame).

    Examples
    --------
    >>> tile_of(1800000, 650000), tile_of(1750000, -50000), tile_of(-1800000, 0)
    ('N65W180', 'S05E175', 'N00W180')
    """
    la = y0 // 10000
    lo = (x0 // 10000 + 180) % 360 - 180
    return f'{"N" if la >= 0 else "S"}{abs(la):02d}{"E" if lo >= 0 else "W"}{abs(lo):03d}'


def granule_frame(points):
    """
    Integer (lon, lat) points of a granule in one frame: -180..180, or 0..360 when they span more than 180 degrees.

    Examples
    --------
    >>> granule_frame([(1799000, 0), (1801000, 10), (-1799500, 20)])
    [(1799000, 0), (1801000, 10), (1800500, 20)]
    """
    pts = [(x - 3600000 if x > 1800000 else x, y) for x, y in points]
    if max(p[0] for p in pts) - min(p[0] for p in pts) > 1800000:
        pts = [(x + 3600000 if x < 0 else x, y) for x, y in pts]
    return pts


def stage_tree(cache):
    t0 = time.time()
    produced, counts = set(), Counter()
    for mission in sorted(set(MISSION.values())):
        rows_dir = os.path.join(cache, 'rows', mission)
        bands, granules = {}, {}
        for f in sorted(os.listdir(rows_dir)) if os.path.isdir(rows_dir) else []:
            if not f.endswith('.tsv'):
                continue
            field = f[:-4]
            rows = read_rows(os.path.join(rows_dir, f))
            entries = read_store(os.path.join(cache, 'footprints', mission, f))
            if entries and tuple(entries[0]) != FOOTPRINT_COLUMNS:
                sys.exit(f'{mission}/{f}: a footprint store of other columns: run --stage footprints first')
            store = {e['productId']: e for e in entries}
            missing = [r['productId'] for r in rows if r['productId'] not in store]
            if missing:
                sys.exit(f'{mission}/{f}: {len(missing)} rows without a footprint record (first {missing[0]}): run '
                         f'--stage footprints first')
            for row in rows:
                entry = store[row['productId']]
                assert entry['code'] == row['code'], (row['productId'], entry['code'], row['code'])
                fp = entry['footprint']
                if not fp:
                    counts[f'{mission} rows without a usable orbit (not listed)'] += 1
                    continue
                parts = row['code'].split('_')
                assert parts[1] == field, row['code']
                frame, swath, date = int(parts[2]), parts[3], parts[4]
                values = [row[c] for c in TRACK_COLUMNS[:-1]] + [fp]
                assert not any(ch in v for v in values for ch in ',"\n\r'), row['code']
                rel = os.path.join('tracks', field, f'{BAND * (frame // BAND):04d}.csv')
                bands.setdefault(rel, []).append((row['begin'], row['code'], ','.join(values)))
                nums = fp.split()
                g = granules.setdefault((field, 18 * (frame // 18) + 9, swath, row['direction']), [0, date, date, []])
                g[0] += 1
                g[1], g[2] = min(g[1], date), max(g[2], date)
                g[3] += [(text_units(nums[k + 1], 4), text_units(nums[k], 4)) for k in range(0, len(nums), 2)]
                counts[f'{mission} track rows'] += 1
        root = os.path.join(REPO, mission, 'scenes')
        for rel, rows in sorted(bands.items()):
            rows.sort()
            data = (','.join(TRACK_COLUMNS) + '\n' + ''.join(t + '\n' for _, _, t in rows)).encode()
            counts['files written'] += write_if_changed(os.path.join(root, rel), data)
            produced.add(os.path.join(root, rel))
            counts[f'{mission} track files'] += 1
        tiles = {}
        for (field, slot, swath, direction), (n, first, last, pts) in sorted(granules.items(),
                                                                            key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], kv[0][3])):
            pts = granule_frame(pts)
            exact = hull(pts)
            poly = outline_cells(exact)
            bad = [p for p in exact if not inside(poly, p)]
            assert not bad, f'{mission} {field} {slot} {swath} {direction}: the outline leaves out hull vertices {bad[:3]}'
            text = ' '.join(f'{units_text(y // 100, 2)} {units_text(x // 100, 2)}' for x, y in poly)
            line = f'{field},{slot:04d},{swath},{direction},{n},{first},{last},{text}'
            xs, ys = [p[0] for p in exact], [p[1] for p in exact]
            listed = 0
            for ty in range((min(ys) // TILE) * TILE, max(ys) + 1, TILE):
                for tx in range((min(xs) // TILE) * TILE, max(xs) + 1, TILE):
                    if meets(exact, tx, ty, tx + TILE, ty + TILE):
                        tiles.setdefault(tile_of(tx, ty), []).append(line)
                        listed += 1
            assert listed, f'{mission} {field} {slot}: in no tile'
            counts[f'{mission} granules'] += 1
            counts[f'{mission} granule listings'] += listed
            if max(xs) > 1800000:
                counts[f'{mission} granules across 180'] += 1
        index = []
        for name, lines in sorted(tiles.items()):
            rel = os.path.join('tiles', name + '.csv')
            data = (','.join(TILE_COLUMNS) + '\n' + ''.join(t + '\n' for t in lines)).encode()
            counts['files written'] += write_if_changed(os.path.join(root, rel), data)
            produced.add(os.path.join(root, rel))
            index.append(f'{name},{len(lines)}')
        if index or os.path.isdir(root):
            path = os.path.join(root, 'tiles.csv')
            counts['files written'] += write_if_changed(path, ('name,rows\n' + ''.join(t + '\n' for t in index)).encode())
            produced.add(path)
        counts[f'{mission} tile files'] += len(index)
    # the files under <MISSION>/scenes/ that this build no longer produces (look.csv is an input)
    deleted = []
    for mission in sorted(set(MISSION.values())):
        root = os.path.join(REPO, mission, 'scenes')
        if not os.path.isdir(root):
            continue
        for d, dirs, files in os.walk(root, topdown=False):
            for f in sorted(files):
                p = os.path.join(d, f)
                if p not in produced and p != os.path.join(root, 'look.csv'):
                    os.remove(p)
                    deleted.append(os.path.relpath(p, REPO))
            if d != root and not os.listdir(d):
                os.rmdir(d)
    for k, v in sorted(counts.items()):
        log(f'tree: {k}: {v}')
    log(f'tree: {len(deleted)} files deleted (no longer produced)' + ''.join(f'\n  deleted: {s}' for s in deleted[:50])
        + (f'\n  ... and {len(deleted) - 50} more' if len(deleted) > 50 else ''))
    log(f'tree: done in {time.time() - t0:.0f} s')
    return 0


class Counter(dict):
    def __missing__(self, key):
        return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cache', help='cache folder for the catalogue, the rows, the footprints and the DEM tiles (outside the '
                                  'repository)')
    ap.add_argument('--harvest', action='store_true', help='harvest the catalogue months that the cache lacks')
    ap.add_argument('--months', help='harvest only these months: YYYY-MM or COLLECTION:YYYY-MM, comma-separated')
    ap.add_argument('--stage', choices=('rows', 'footprints', 'tree', 'all'), help='the stage to build (all: rows, '
                                                                                    'footprints, tree)')
    ap.add_argument('--jobs', type=int, default=8, help='processes of the nodes (rows stage) and of the footprints stage '
                                                        '(default 8)')
    args = ap.parse_args()
    if not args.harvest and args.stage is None:
        ap.error('nothing to do: give --harvest and/or --stage')
    if args.months and not args.harvest:
        ap.error('--months limits --harvest')
    if args.jobs < 1:
        ap.error('--jobs must be at least 1')
    # symlinks resolved on both sides: a link to a folder inside the repository is inside it
    cache = os.path.realpath(args.cache)
    if os.path.commonpath([cache, os.path.realpath(REPO)]) == os.path.realpath(REPO):
        sys.exit('the cache folder must be outside the repository')
    os.makedirs(cache, exist_ok=True)
    # one thread per process: the nodes of the rows stage and the footprints stage run --jobs processes
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS',
                 'NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    if args.harvest:
        harvest(cache, None if not args.months else {m.strip() for m in args.months.split(',') if m.strip()})
    if args.stage in ('rows', 'all') and stage_rows(cache, args.jobs):
        sys.exit(1)
    if args.stage in ('footprints', 'all') and stage_footprints(cache, args.jobs):
        sys.exit(1)
    if args.stage in ('tree', 'all') and stage_tree(cache):
        sys.exit(1)


if __name__ == '__main__':
    main()
