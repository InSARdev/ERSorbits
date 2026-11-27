#!/usr/bin/env python3.13
"""
The figures of the README, made from this repository only.

    python3.13 plots.py [--out docs]

Reads:
- <SATELLITE>/<YYYY>/<MM>/<DD>/index.csv (the served orbit set of every UTC day) and <SATELLITE>/no_orbit.csv;
- <MISSION>/scenes/tracks/ (the scene rows: <track>/<band>.csv, or <track>.csv) and <MISSION>/scenes/tiles/ (the granules);
- docs/land_cells.csv: the 1-degree cells that hold land, the Copernicus GLO-90 tile list. When the file is missing it is
  made once from the public bucket listing (anonymous S3 list requests to copernicus-dem-90m) and kept, so a rebuild of the
  figures needs no network.

Writes PNG files into the output folder (default docs/ of the repository) and prints one line per figure (the file and what
it counts), then the scene table as Markdown:
- orbit_sets.png: per satellite, the served orbit set of every UTC day, the days without an orbit and the days a
  no_orbit.csv span touches;
- <mission>_coverage.png: per 1-degree cell, the most dates of one stack (track, swath, polarisation, direction) whose
  scene footprints meet the cell;
- <mission>_scenes_per_year.png: the scenes per calendar year, stacked by mission phase;
- <mission>_dates_per_stack.png: the histogram of the dates of every stack (track, swath, polarisation, direction, slot).

The same data give the same bytes on one matplotlib version (no time stamp or software tag in the PNG files).
Dependencies: numpy, matplotlib, shapely.
"""
import argparse
import collections
import datetime
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
import numpy as np
import shapely

REPO = os.path.dirname(os.path.abspath(__file__))
SATELLITES = (('ERS1', 'ERS-1'), ('ERS2', 'ERS-2'), ('ENVISAT', 'Envisat'))
MISSIONS = (('ENVISAT', 'Envisat'), ('ERS1', 'ERS-1'), ('ERS2', 'ERS-2'))
# the mission phases of the scene rows, folded into the series of the scenes-per-year bars
PHASE_SERIES = {
    'ENVISAT': (('phase 2 (35-day)', ('2',)), ('phase 3 (30-day)', ('3',))),
    'ERS1': (('35-day (C, G)', ('C', 'G')), ('3-day (A, B, D)', ('A', 'B', 'D'))),
    'ERS2': (('phase A (35-day)', ('A',)), ('phase B (3-day)', ('B',))),
}
KINDS = (('regular', 'regular'), ('offgrid', 'off-grid'), ('extra', 'extra'))

# InSAR.dev figure colours
SEQUENTIAL = ('#cce3fd', '#9dc8f7', '#6aabf1', '#338ced', '#2370cd', '#1757ac', '#0e3d7e')
CATEGORICAL = ('#257de0', '#f47230', '#00b894')
OTHER = '#9c9c9c'
TITLE_INK, TICK_INK, GRID, AXIS = '#191919', '#666666', '#e7e7e7', '#c2c2c2'
# the neutral bands of the orbit timelines and the land of the maps
NO_ORBIT_DAY = '#d9d9d9'
NO_ORBIT_SPAN = '#4d4d4d'
LAND = '#e9e9e9'
# the coverage classes of the maps, the same on every map: dates per stack in log steps (1, 2-4, 5-9, 10-19, 20-49,
# 50-99, 100 and more), one sequential colour each
COVERAGE_BOUNDS = (1, 2, 5, 10, 20, 50, 100)

WIDTH_IN, DPI = 16.0, 100          # 1600 px
SAVE = dict(dpi=DPI, metadata={'Software': None})

GLO90_BUCKET = 'https://copernicus-dem-90m.s3.amazonaws.com/'
GLO90_PREFIX = re.compile(r'^Copernicus_DSM_COG_30_([NS])(\d{2})_00_([EW])(\d{3})_00_DEM/$')
S3 = '{http://s3.amazonaws.com/doc/2006-03-01/}'


def style():
    plt.rcParams.update({
        'font.size': 12, 'axes.titlesize': 15, 'axes.titleweight': 'normal', 'axes.titlecolor': TITLE_INK,
        'axes.titlelocation': 'left', 'axes.titlepad': 10,
        'axes.labelcolor': TICK_INK, 'axes.edgecolor': AXIS, 'axes.linewidth': 0.8,
        'xtick.color': AXIS, 'ytick.color': AXIS, 'xtick.labelcolor': TICK_INK, 'ytick.labelcolor': TICK_INK,
        'xtick.labelsize': 11, 'ytick.labelsize': 11,
        'legend.fontsize': 11, 'legend.labelcolor': TICK_INK, 'legend.frameon': False,
        'figure.facecolor': 'white', 'axes.facecolor': 'white', 'savefig.facecolor': 'white',
        'grid.color': GRID, 'grid.linewidth': 0.6,
    })


def thousands(x, _=None):
    return f'{int(round(x)):,}'


def plain_axes(ax, grid_axis='y'):
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    ax.set_axisbelow(True)
    if grid_axis:
        ax.grid(True, axis=grid_axis)


# ---------------------------------------------------------------------------------------------------------- the orbits

def day_sets(sat):
    """{date: set} of the satellite's UTC days, from the day indexes."""
    out = {}
    root = os.path.join(REPO, sat)
    for y in sorted(d for d in os.listdir(root) if re.fullmatch(r'\d{4}', d)):
        for m in sorted(os.listdir(os.path.join(root, y))):
            for d in sorted(os.listdir(os.path.join(root, y, m))):
                path = os.path.join(root, y, m, d, 'index.csv')
                if not os.path.exists(path):
                    continue
                with open(path) as fh:
                    lines = fh.read().splitlines()
                col = lines[0].split(',').index('set')
                sets = {line.split(',')[col] for line in lines[1:]}
                assert len(sets) == 1, (path, sets)
                out[datetime.date(int(y), int(m), int(d))] = sets.pop()
    return out


def span_days(sat):
    """The UTC days that a span of <SATELLITE>/no_orbit.csv touches, and the number of spans."""
    days = set()
    with open(os.path.join(REPO, sat, 'no_orbit.csv')) as fh:
        lines = fh.read().splitlines()
    assert lines[0].split(',')[:2] == ['start', 'end'], lines[0]
    for line in lines[1:]:
        start, end = (datetime.datetime.fromisoformat(v) for v in line.split(',')[:2])
        day = start.date()
        while day <= end.date():
            # a span that ends at 00:00:00 does not touch the day it ends on
            if day == end.date() and end.time() == datetime.time(0) and end > start:
                break
            days.add(day)
            day += datetime.timedelta(days=1)
    return days, len(lines) - 1


def runs(days):
    """Runs of consecutive days: [(first ordinal, length)]."""
    out = []
    for o in sorted(d.toordinal() for d in days):
        if out and out[-1][0] + out[-1][1] == o:
            out[-1][1] += 1
        else:
            out.append([o, 1])
    return [tuple(r) for r in out]


def plot_orbit_sets(out):
    data = []
    for sat, label in SATELLITES:
        sets = day_sets(sat)
        spans, nspans = span_days(sat)
        first, last = min(sets), max(sets)
        gap = {first + datetime.timedelta(days=k) for k in range((last - first).days + 1)} - set(sets)
        data.append((sat, label, sets, spans, nspans, gap))
    years = [min(min(d[2]) for d in data).year, max(max(d[2]) for d in data).year + 1]
    fig, axes = plt.subplots(len(data), 1, figsize=(WIDTH_IN, 2.15 * len(data) + 0.9), sharex=True)
    lines = []
    for ax, (sat, label, sets, spans, nspans, gap) in zip(axes, data):
        days = collections.Counter(sets.values())
        order = sorted(days, key=lambda s: (-days[s], s))
        shown = order[:len(CATEGORICAL)]
        colour = {s: CATEGORICAL[i] for i, s in enumerate(shown)}
        handles = []
        # the runs of days, the largest series first; every run gets a hairline edge of its own colour, so that a run of a
        # few days (narrower than a pixel) stays visible
        for s in shown:
            dd = [d for d, v in sets.items() if v == s]
            ax.broken_barh(runs(dd), (1.0, 1.0), facecolors=colour[s], edgecolors=colour[s], linewidth=0.7)
            handles.append(Patch(color=colour[s], label=f'{s}: {days[s]:,} days'))
        rest = [s for s in order if s not in shown]
        if rest:
            dd = [d for d, v in sets.items() if v in rest]
            ax.broken_barh(runs(dd), (1.0, 1.0), facecolors=OTHER, edgecolors=OTHER, linewidth=0.7)
            names = ', '.join(rest)
            handles.append(Patch(color=OTHER, label=f'other ({names}): {len(dd):,} days'))
        if gap:
            ax.broken_barh(runs(gap), (1.0, 1.0), facecolors=NO_ORBIT_DAY, edgecolors=NO_ORBIT_DAY, linewidth=0.7)
        handles.append(Patch(color=NO_ORBIT_DAY, label=f'no orbit: {len(gap):,} days'))
        # the days a no_orbit.csv span touches: a mark per day, at least a hairline wide
        ords = sorted(d.toordinal() for d in spans)
        ax.vlines([o + 0.5 for o in ords], 0.15, 0.75, colors=NO_ORBIT_SPAN, linewidth=0.6)
        handles.append(Patch(color=NO_ORBIT_SPAN, label=f'touched by a no_orbit.csv span: {len(spans):,} days '
                                                        f'({nspans:,} spans)'))
        ax.set_ylim(0, 2.15)
        ax.set_yticks([0.45, 1.5], ['no_orbit.csv', 'served set'])
        ax.tick_params(axis='y', length=0)
        ax.set_title(f'{label}: the orbit set served on each UTC day', fontsize=13)
        plain_axes(ax, 'x')
        ax.spines['left'].set_visible(False)
        ax.legend(handles=handles, loc='upper left', bbox_to_anchor=(1.005, 1.0), handlelength=1.2,
                  borderaxespad=0.0)
        lines.append(f'{label} {", ".join(f"{s} {days[s]}" for s in order)}, no orbit {len(gap)}, '
                     f'no_orbit.csv {nspans} spans on {len(spans)} days')
    ticks = [datetime.date(y, 1, 1).toordinal() for y in range(years[0], years[1] + 1)]
    axes[-1].set_xticks(ticks, [str(y) for y in range(years[0], years[1] + 1)])
    axes[-1].set_xlim(ticks[0], ticks[-1])
    axes[-1].margins(x=0)
    fig.tight_layout(h_pad=1.2)
    path = os.path.join(out, 'orbit_sets.png')
    fig.savefig(path, **SAVE)
    plt.close(fig)
    print(f'{path}: the served orbit set of every UTC day per satellite; ' + '; '.join(lines))


# ------------------------------------------------------------------------------------------------------- the land list

def land_cells():
    """The south-west corners (lat, lon) of the 1-degree cells that hold a Copernicus GLO-90 tile."""
    path = os.path.join(REPO, 'docs', 'land_cells.csv')
    if not os.path.exists(path):
        cells, token, requests = [], None, 0
        while True:
            query = {'list-type': '2', 'delimiter': '/'}
            if token:
                query['continuation-token'] = token
            url = GLO90_BUCKET + '?' + urllib.parse.urlencode(query)
            with urllib.request.urlopen(url, timeout=60) as resp:
                root = ET.fromstring(resp.read())
            requests += 1
            for p in root.iter(S3 + 'Prefix'):
                m = GLO90_PREFIX.match(p.text or '')
                if m:
                    lat = int(m[2]) * (1 if m[1] == 'N' else -1)
                    lon = int(m[4]) * (1 if m[3] == 'E' else -1)
                    cells.append((lat, lon))
            if root.findtext(S3 + 'IsTruncated') != 'true':
                break
            token = root.findtext(S3 + 'NextContinuationToken')
        cells = sorted(set(cells))
        assert cells, 'the GLO-90 listing holds no tile'
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as fh:
            fh.write('lat,lon\n' + ''.join(f'{a},{b}\n' for a, b in cells))
        print(f'{path}: {len(cells):,} land cells from {requests} list requests to {GLO90_BUCKET}')
    with open(path) as fh:
        lines = fh.read().splitlines()
    assert lines[0] == 'lat,lon', path
    return [tuple(int(v) for v in line.split(',')) for line in lines[1:]]


# ------------------------------------------------------------------------------------------------------ the scene index

def track_files(mission):
    root = os.path.join(REPO, mission, 'scenes', 'tracks')
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        if os.path.isdir(p):
            for band in sorted(os.listdir(p)):
                if band.endswith('.csv'):
                    yield os.path.join(p, band)
        elif name.endswith('.csv'):
            yield p


def cell_tree():
    """The 1-degree cells, lon -180..360 (a footprint across 180 is stored in 0..360), lat -90..90."""
    lat0, lon0 = np.meshgrid(np.arange(-90, 90), np.arange(-180, 360), indexing='ij')
    lat0, lon0 = lat0.ravel(), lon0.ravel()
    boxes = shapely.box(lon0, lat0, lon0 + 1, lat0 + 1)
    # the cell id in -180..180: (lat + 90) * 360 + (lon + 180) mod 360
    ids = (lat0 + 90) * 360 + (lon0 + 180) % 360
    return shapely.STRtree(boxes), ids


def read_index(mission):
    """Everything the scene figures of a mission count, from its track and tile files."""
    tree, cell_ids = cell_tree()
    series = {ph: name for name, phases in PHASE_SERIES[mission] for ph in phases}
    stacks, slots = {}, {}
    cover, stack_dates = [], []
    per_year, kinds = collections.Counter(), collections.Counter()
    granules = set()
    for path in track_files(mission):
        with open(path) as fh:
            lines = fh.read().splitlines()
        head = lines[0].split(',')
        ci, ki, pi, di, fi = (head.index(c) for c in ('code', 'kind', 'phase', 'direction', 'footprint'))
        sid, did, fps = [], [], []
        for line in lines[1:]:
            v = line.split(',')
            _, field, frame, swath, date, pol = v[ci].split('_')
            kind = 'extra' if v[ki].startswith('extra') else v[ki]
            assert kind in dict(KINDS), (path, v[ki])
            kinds[kind] += 1
            per_year[(int(date[:4]), series[v[pi]])] += 1
            slot = 18 * (int(frame) // 18) + 9
            granules.add((field, slot, swath, v[di]))
            day = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:])).toordinal()
            sid.append(stacks.setdefault((field, swath, pol, v[di]), len(stacks)))
            stack_dates.append((slots.setdefault((field, swath, pol, v[di], slot), len(slots)) << 20) + day)
            did.append(day)
            fps.append(v[fi].split())
        if not fps:
            continue
        npts = np.array([len(f) // 2 for f in fps])
        xy = np.array([x for f in fps for x in f], dtype=float).reshape(-1, 2)
        rings = shapely.linearrings(xy[:, ::-1], indices=np.repeat(np.arange(len(fps)), npts))
        polys = shapely.polygons(rings)
        hit_poly, hit_cell = tree.query(polys, predicate='intersects')
        sid, did = np.array(sid, dtype=np.int64), np.array(did, dtype=np.int64)
        # key: stack (20 bits), cell (17 bits), day ordinal (20 bits)
        key = (sid[hit_poly] << 37) | (cell_ids[hit_cell].astype(np.int64) << 20) | did[hit_poly]
        cover.append(np.unique(key))
    key = np.unique(np.concatenate(cover))
    stack_cell, nd = np.unique(key >> 20, return_counts=True)
    best = np.zeros(180 * 360, dtype=np.int64)
    np.maximum.at(best, stack_cell & ((1 << 17) - 1), nd)
    sd = np.unique(np.array(stack_dates, dtype=np.int64))
    _, dates_per_stack = np.unique(sd >> 20, return_counts=True)
    tiles_dir = os.path.join(REPO, mission, 'scenes', 'tiles')
    tile_files = sorted(f for f in os.listdir(tiles_dir) if f.endswith('.csv'))
    listed = set()
    for f in tile_files:
        with open(os.path.join(tiles_dir, f)) as fh:
            lines = fh.read().splitlines()
        assert lines[0].split(',')[:4] == ['track', 'frame', 'swath', 'direction'], f
        listed |= {tuple(line.split(',')[:4]) for line in lines[1:]}
    listed = {(t, int(fr), s, d) for t, fr, s, d in listed}
    assert listed == granules, (f'{mission}: the tile files list {len(listed)} granules, the track files hold '
                                f'{len(granules)}')
    return dict(best=best.reshape(180, 360), dates_per_stack=dates_per_stack, per_year=per_year, kinds=kinds,
                granules=len(granules), tiles=len(tile_files), stacks=len(stacks), slots=len(slots))


def plot_coverage(out, mission, label, idx, land):
    best = idx['best']
    top = int(best.max())
    bounds = list(COVERAGE_BOUNDS) + [max(top, COVERAGE_BOUNDS[-1]) + 1]
    cmap = ListedColormap(SEQUENTIAL)
    norm = BoundaryNorm(bounds, cmap.N)
    land_grid = np.zeros((180, 360))
    for lat, lon in land:
        land_grid[lat + 90, (lon + 180) % 360] = 1
    fig = plt.figure(figsize=(WIDTH_IN, 9.2))
    ax = fig.add_axes([0.045, 0.15, 0.94, 0.78])
    ax.imshow(np.where(land_grid > 0, 1.0, np.nan), extent=(-180, 180, -90, 90), origin='lower',
              cmap=ListedColormap([LAND]), vmin=0, vmax=1, interpolation='nearest', zorder=1)
    im = ax.imshow(np.ma.masked_less(best, 1), extent=(-180, 180, -90, 90), origin='lower', cmap=cmap, norm=norm,
                   interpolation='nearest', zorder=2)
    ax.set_xlim(-180, 180)
    ax.set_ylim(-90, 90)
    ax.margins(0)
    ax.set_xticks(range(-180, 181, 30), [f'{abs(v)}°{"E" if v > 0 else "W" if v < 0 else ""}'
                                         for v in range(-180, 181, 30)])
    ax.set_yticks(range(-90, 91, 30), [f'{abs(v)}°{"N" if v > 0 else "S" if v < 0 else ""}'
                                       for v in range(-90, 91, 30)])
    # the land outline over the data, the grid under everything
    ax.contour(np.arange(-179.5, 180), np.arange(-89.5, 90), land_grid, levels=[0.5], colors=TICK_INK,
               linewidths=0.4, zorder=3)
    ax.set_axisbelow(True)
    ax.grid(True)
    ax.set_title(f'{label}: the most dates of one stack (track, swath, polarisation, direction) whose scene '
                 f'footprints meet each 1° cell')
    cax = fig.add_axes([0.30, 0.075, 0.40, 0.022])
    cb = fig.colorbar(im, cax=cax, orientation='horizontal', spacing='uniform')
    centres = [(a + b) / 2 for a, b in zip(bounds[:-1], bounds[1:])]
    labels = [f'{a}' if b == a + 1 else f'{a}-{b - 1}' for a, b in zip(bounds[:-2], bounds[1:-1])]
    labels.append(f'{bounds[-2]} and more')
    cb.set_ticks(centres, labels=labels)
    cb.ax.tick_params(length=0, labelcolor=TICK_INK)
    cb.outline.set_visible(False)
    cb.set_label('dates (classes in log steps)', color=TICK_INK)
    fig.legend(handles=[Patch(facecolor=LAND, edgecolor=TICK_INK, linewidth=0.4,
                              label='land (1° cells of the Copernicus GLO-90 tiles)')], loc='lower left',
               bbox_to_anchor=(0.04, 0.055))
    path = os.path.join(out, f'{mission.lower()}_coverage.png')
    fig.savefig(path, **SAVE)
    plt.close(fig)
    cells = int((best > 0).sum())
    print(f'{path}: per 1-degree cell, the most dates of one stack (track, swath, polarisation, direction) whose '
          f'footprints meet it; {cells:,} cells covered, maximum {top} dates, {idx["stacks"]:,} stacks')


def plot_per_year(out, mission, label, idx):
    per_year = idx['per_year']
    years = list(range(min(y for y, _ in per_year), max(y for y, _ in per_year) + 1))
    names = [name for name, _ in PHASE_SERIES[mission]]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 5.2))
    bottom = np.zeros(len(years))
    for name, colour in zip(names, CATEGORICAL):
        h = np.array([per_year.get((y, name), 0) for y in years], dtype=float)
        total = int(h.sum())
        ax.bar(years, h, bottom=bottom, width=0.78, color=colour, edgecolor='white', linewidth=1.5,
               label=f'{name}: {total:,} scenes')
        bottom += h
    ax.set_xticks(years, [str(y) for y in years])
    ax.set_xlim(years[0] - 0.6, years[-1] + 0.6)
    ax.yaxis.set_major_formatter(thousands)
    ax.set_ylabel('scenes')
    ax.tick_params(axis='x', length=0)
    plain_axes(ax, 'y')
    ax.set_title(f'{label}: scenes per calendar year (of the scene date), by mission phase')
    ax.legend(loc='upper left', ncols=len(names))
    ax.set_ylim(0, bottom.max() * 1.12)
    fig.tight_layout()
    path = os.path.join(out, f'{mission.lower()}_scenes_per_year.png')
    fig.savefig(path, **SAVE)
    plt.close(fig)
    print(f'{path}: scenes per calendar year by phase; ' +
          ', '.join(f'{n} {sum(v for (y, s), v in per_year.items() if s == n):,}' for n in names))


def plot_dates_per_stack(out, mission, label, idx):
    n = idx['dates_per_stack']
    top = int(n.max())
    width = 1
    edges = np.arange(1, top + 2) - 0.5
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 5.2))
    ax.hist(n, bins=edges, color=CATEGORICAL[0], edgecolor='white', linewidth=0.6, log=True)
    ax.set_xlim(0, edges[-1] + 0.5)
    ax.set_ylim(bottom=0.7)
    ax.yaxis.set_major_formatter(thousands)
    ax.set_xlabel('dates in the stack')
    ax.set_ylabel('stacks (log)')
    plain_axes(ax, 'y')
    ax.set_title(f'{label}: dates per stack (track, swath, polarisation, direction, slot), '
                 f'{len(n):,} stacks')
    fig.tight_layout()
    path = os.path.join(out, f'{mission.lower()}_dates_per_stack.png')
    fig.savefig(path, **SAVE)
    plt.close(fig)
    print(f'{path}: the dates of every stack (track, swath, polarisation, direction, slot); {len(n):,} stacks, '
          f'median {int(np.median(n))}, maximum {top} dates')


def scene_table(rows):
    head = ['Mission'] + [name for _, name in KINDS] + ['scenes', 'granules', 'tiles']
    out = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    for label, idx in rows:
        k = idx['kinds']
        vals = [k.get(kind, 0) for kind, _ in KINDS] + [sum(k.values()), idx['granules'], idx['tiles']]
        out.append('| ' + ' | '.join([label] + [f'{v:,}' for v in vals]) + ' |')
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out', default='docs', help='output folder, relative to the repository (default docs)')
    args = ap.parse_args()
    out = os.path.join(REPO, args.out)
    os.makedirs(out, exist_ok=True)
    style()
    plot_orbit_sets(out)
    land = land_cells()
    table = []
    for mission, label in MISSIONS:
        if not os.path.isdir(os.path.join(REPO, mission, 'scenes', 'tracks')):
            print(f'{mission}/scenes/tracks/ is not built: its scene figures are not made')
            continue
        idx = read_index(mission)
        plot_coverage(out, mission, label, idx, land)
        plot_per_year(out, mission, label, idx)
        plot_dates_per_stack(out, mission, label, idx)
        table.append((label, idx))
    if table:
        print()
        print(scene_table(table))


if __name__ == '__main__':
    sys.exit(main())
