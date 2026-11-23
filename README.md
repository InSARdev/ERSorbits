# ERS-1, ERS-2 and Envisat Orbits
This repository offers well-structured daily precise orbits of ERS-1, ERS-2 and Envisat for SAR and InSAR processing with
[InSAR.dev](https://insar.dev/). The missions have ended, so the archive is complete and static: it is rebuilt by `build.py` only
when a source server publishes newer orbits.

For every satellite and UTC day the repository holds the orbits of one set: the highest-ranked orbit set (by the gravity model
of its solution, with Delft's operational orbits as a fallback below every precise set; see the ranking below) that covers the
whole day, or, on a day no set covers whole, the highest-ranked set that covers part of it. The sets come from public servers that need no credentials (TU Delft's anonymous FTP and ESA's STEP
auxiliary data server). Every orbit file is stored unchanged, one file per zip archive, in the folder of the day its arc
starts, and every day that an orbit covers has an `index.csv` that lists the arcs to use for that day.

## Sources

| Satellite | Source | Set | Files | Production date (`produced`) |
|---|---|---|---|---|
| ERS-1 | TU Delft (DEOS), `ftp://dutlru2.lr.tudelft.nl/pub/orbits/ODR.ERS-1/dgm-e04/` | `ODR.ERS-1/dgm-e04` | `ODR.<arc>` + `arclist` | the file's FTP `MDTM` time |
| ERS-1 | TU Delft (DEOS), `.../ODR.ERS-1/dgm-e04.fd/` | `ODR.ERS-1/dgm-e04.fd` | `ODR.<arc>` + `arclist` | the file's FTP `MDTM` time |
| ERS-1 | TU Delft (DEOS), `.../ODR.ERS-1/jgm3/` | `ODR.ERS-1/jgm3` | `ODR.<arc>` + `arclist` | the file's FTP `MDTM` time |
| ERS-1 | ESA STEP, `https://step.esa.int/auxdata/orbits/ers_precise_orb/ERS1/<year>.zip` (1991-1996, 1998-2000) | `ers_precise_orb/ERS1` | `PRC_<yymmdd>_<orbit>_rev2` | 1995-03-24 (see below) |
| ERS-2 | TU Delft (DEOS), `.../ODR.ERS-2/eigen-grace01s/` | `ODR.ERS-2/eigen-grace01s` | `ODR.<arc>` + `arclist` | the file's FTP `MDTM` time |
| ERS-2 | TU Delft (DEOS), `.../ODR.ERS-2/grim5-c1/` | `ODR.ERS-2/grim5-c1` | `ODR.<arc>` + `arclist` | the file's FTP `MDTM` time |
| ERS-2 | TU Delft (DEOS), `.../ODR.ERS-2/dgm-e04/` | `ODR.ERS-2/dgm-e04` | `ODR.<arc>` + `arclist` | the file's FTP `MDTM` time |
| ERS-2 | TU Delft (DEOS), `.../ODR.ERS-2/dgm-e04.fd/` | `ODR.ERS-2/dgm-e04.fd` | `ODR.<arc>` + `arclist` | the file's FTP `MDTM` time |
| ERS-2 | TU Delft (DEOS), `.../ODR.ERS-2/jgm3/` | `ODR.ERS-2/jgm3` | `ODR.<arc>` + `arclist` | the file's FTP `MDTM` time |
| ERS-2 | ESA STEP, `https://step.esa.int/auxdata/orbits/ers_precise_orb/ERS2/<year>.zip` (1995-2011) | `ers_precise_orb/ERS2` | `PRC_<yymmdd>_<orbit>_rev2` | 1995-03-24 (see below) |
| Envisat | ESA STEP, `https://step.esa.int/auxdata/orbits/Doris/vor/<year>.zip` (2002-2012) | `Doris/vor` | `DOR_VOR_AXVF-P<publish>_<start>_<stop>` | the `P<YYYYMMDD_HHMMSS>` publish time in the name |
| Envisat | TU Delft (DEOS), `.../ODR.ENVISAT1/eigen-cg03c/` | `ODR.ENVISAT1/eigen-cg03c` | `ODR.<arc>` + `arclist` | the file's FTP `MDTM` time |
| Envisat | TU Delft (DEOS), `.../POE.ENVISAT1/eigen-cg03c/` | `POE.ENVISAT1/eigen-cg03c` | `envisat.<arc>.poe.gz` (spans from the ODR `arclist` of the same set) | the file's FTP `MDTM` time |

The arc spans (`start`, `end`, UTC) come from the Delft `arclist` of each set (to the minute), from the first and last state
vectors of the PRC files (their TDT times converted to UTC with the TDT-UTC offset in each file), and from `SENSING_START` /
`SENSING_STOP` of the DORIS files. Most Delft arcs start and end at 00:00 or 12:00 UTC; 99 of the 4,292 Delft arcs used do not
(60 of them in the Envisat sets): they start or end at 23:59, at 11:59, or at another minute, often the minute where one arc
hands over to the next.

**PRC production date.** The PRC files hold no production date, and the member dates in STEP's zips are repacks: every outer
member is dated 2015-02, and 1,742 of the 1,775 inner files are dated 2014-04 (the other 33: 7 dated 2012-06, 20 dated 2013-07,
6 dated 2013-09), whatever the arc's year. "rev2" is the German PAF's (D-PAF) revision 2 orbit, computed with the PGM055
gravity model, in operational use for arcs from 1995-03-24, with 8-10 cm radial accuracy (revision 1: 12-15 cm). Source: ESA's
D-PAF "Altimeter and Orbit Global Products Manual", ERS-D-GPM-31200 (GFZ/D-PAF), its PRC product specification and PRC
history ("Aug.95, Mar.24, 1995 ff, Rev. 2, PGM055, improved gravity model"),
<https://earth.esa.int/eogateway/documents/20142/37627/ERS-Altimeter-and-Orbit-Global-Products-Manual.pdf>. Every PRC arc
therefore carries `produced` = 1995-03-24. The production date decides only between sets of the same rank (see the ranking
below).

Not used:
- TU Delft `ODR.ERS-2/dgm-e09spx` (DGM-E09 gravity field, 231 arcs 1995-05-02 .. 1999-06-04, its ODR files dated
  1999-08-13). Its arcs meet end to end instead of overlapping: of its 230 pairs of consecutive arcs, 201 meet end to end,
  1 overlaps and 28 leave a hole between them, 481.9 h in all (12 holes of 1 minute to 1.3 h, 16 of 12.6 to 84 h). Under the
  whole-day rule each hole gives its day to another set: with this set ranked above DGM-E04, a 1995-1999 ERS-2 stack switched
  between DGM-E09 and DGM-E04 at 56 day boundaries (43 days). DGM-E04 (`ODR.ERS-2/dgm-e04`) covers the same years
  continuously and is a published solution (Scharroo and Visser, 1998), so ERS-2 takes DGM-E04 for 1995-2001. The holes (UTC):

  | No arc covers | Hours | No arc covers | Hours |
  |---|---|---|---|
  | 1996-01-15T06:30 .. 19:08 | 12.63 | 1998-06-07T01:43 .. 1998-06-09T01:02 | 47.32 |
  | 1996-01-22T06:50 .. 1996-01-24T17:00 | 58.17 | 1998-06-24T06:30 .. 1998-06-25T00:11 | 17.68 |
  | 1996-01-27T01:27 .. 02:20 | 0.88 | 1998-07-18T06:00 .. 23:40 | 17.67 |
  | 1996-03-22T06:26 .. 20:41 | 14.25 | 1998-08-21T04:51 .. 05:42 | 0.85 |
  | 1996-08-21T05:59 .. 1996-08-23T00:28 | 42.48 | 1998-09-18T01:06 .. 01:57 | 0.85 |
  | 1996-12-03T05:40 .. 20:03 | 14.38 | 1998-10-20T01:53 .. 03:00 | 1.12 |
  | 1997-02-10T06:13 .. 18:49 | 12.60 | 1998-11-12T00:53 .. 01:45 | 0.87 |
  | 1997-02-13T06:19 .. 1997-02-15T23:17 | 64.97 | 1998-11-22T05:47 .. 19:00 | 13.22 |
  | 1997-04-22T05:42 .. 19:08 | 13.43 | 1999-01-06T10:21 .. 11:15 | 0.90 |
  | 1997-04-24T03:49 .. 04:39 | 0.83 | 1999-02-05T06:00 .. 1999-02-06T00:30 | 18.50 |
  | 1997-07-01T01:12 .. 01:13 | 0.02 | 1999-03-03T05:19 .. 1999-03-04T01:00 | 19.68 |
  | 1997-09-16T00:00 .. 1997-09-19T12:00 | 84.00 | 1999-03-29T00:00 .. 01:20 | 1.33 |
  | 1997-12-09T05:30 .. 1997-12-10T02:00 | 20.50 | 1999-04-28T00:20 .. 01:20 | 1.00 |
  | 1998-05-27T01:16 .. 02:06 | 0.83 | 1999-05-21T06:43 .. 07:40 | 0.95 |

- TU Delft `ODR.ERS-2/dgm-e04.prelim` (preliminary DGM-E04 arcs 2001-01-09..2003-07-10, 252 arcs) and `ODR.ERS-2/dgm-e04.auto`
  (20 daily `ODR.<yymmdd>` files of October 2005 from the automatic processing, no arclist): preliminary and automatic orbits,
  not the final solution of their model.
- TU Delft `ODR.ENVISAT1/outdated/` (older Envisat sets: `eigen-grace01s`, `eigen3p`, `ggm01c`, `ggm01s`, `grim5-c1`).
- GMTSAR's orbit archive (a stale copy) and ESA's REAPER reprocessed ERS orbits (they need credentials and are not
  redistributable).
- One non-orbit file in STEP's Envisat 2012 zip (`DOR_DOP_1POF-P20120406_000412_000859872113_00233_52832_3920.N1`, a Doppler
  product).

## Gravity-model ranking

Sets are ranked by the gravity model of their orbit solution, newest model first. Delft's operational orbits (the
`dgm-e04.fd` sets) rank below every precise set, as a fallback for the days no precise set covers whole. Only sets of the same rank
are ranked by file date (`produced`, newest first). Model dates are those of the model's publication or release, with their
source. The last column gives the radial orbit accuracy reported for the set's orbits, with its source; '-' where no source
reports one.

ERS-1 and ERS-2:

| Rank | Gravity model | Model date | Source of the date | Sets in this repository (arcs on the server) | Reported radial accuracy (source) |
|---|---|---|---|---|---|
| 1 | EIGEN-GRACE01S | 2003 | Reigber, C., Schmidt, R., Flechtner, F., König, R., Meyer, U., Neumayer, K.H., Schwintzer, P., Zhu, S.Y. (2003), "First EIGEN gravity field model based on GRACE mission data only", GFZ Potsdam; ICGEM model table, <https://icgem.gfz-potsdam.de/tom_longtime> | `ODR.ERS-2/eigen-grace01s` (2001-12-21 .. 2008-01-24, files of 2007-01 .. 2008-02) | - |
| 2 | GRIM5-C1 | 1999 (published 2000) | Gruber, T., Bode, A., Reigber, C., Schwintzer, P., Balmino, G., Biancale, R., Lemoine, J.-M. (2000), "GRIM5-C1: Combination solution of the global gravity field to degree and order 120", Geophys. Res. Lett. 27(24), 4005-4008, [doi:10.1029/2000GL011589](https://doi.org/10.1029/2000GL011589); ICGEM lists the model as of 1999 | `ODR.ERS-2/grim5-c1` (2001-12-21 .. 2003-03-27, files of 2003-01 .. 2003-04) | - |
| 3 | DGM-E04, precise | 1998 | Scharroo, R. and Visser, P. (1998), "Precise orbit determination and gravity field improvement for the ERS satellites", J. Geophys. Res. 103(C4), 8113-8127, [doi:10.1029/97JC03179](https://doi.org/10.1029/97JC03179) | `ODR.ERS-1/dgm-e04` (1991-07-30 .. 1996-06-06), `ODR.ERS-2/dgm-e04` (1995-04-28 .. 2003-08-14) | 5 cm RMS (Scharroo and Visser 1998, abstract: "the orbits computed with JGM 3 have a radial root-mean-square orbit accuracy of 7 cm, with DGM-E04 5 cm") |
| 4 | PGM055 | 1995 (operational from August 1995, for arcs from 1995-03-24) | ESA's D-PAF "Altimeter and Orbit Global Products Manual" ERS-D-GPM-31200, PRC history, <https://earth.esa.int/eogateway/documents/20142/37627/ERS-Altimeter-and-Orbit-Global-Products-Manual.pdf> | `ers_precise_orb/ERS1` (PRC, 1991-07-27 .. 2000-03-08), `ers_precise_orb/ERS2` (PRC, 1995-04-28 .. 2011-07-06) | about 8-10 cm (D-PAF manual ERS-D-GPM-31200, PRC quality assessment: "the revision 2 provides about 8-10 cm radial accuracy"; revision 1: 12-15 cm) |
| 5 | JGM-3 | 1994 (published 1996) | Tapley, B.D., Watkins, M.M., Ries, J.C., et al. (1996), "The Joint Gravity Model 3", J. Geophys. Res. 101(B12), 28029-28049, [doi:10.1029/96JB01645](https://doi.org/10.1029/96JB01645); ICGEM lists the model as of 1994 | `ODR.ERS-1/jgm3` (1992-04-10 .. 1996-06-06), `ODR.ERS-2/jgm3` (1995-04-28 .. 2003-03-27) | 7 cm RMS (Scharroo and Visser 1998, abstract, as above) |
| 6 | DGM-E04, operational (fallback) | 1998 (the model of rank 3) | as rank 3 | `ODR.ERS-1/dgm-e04.fd` (1996-06-04 .. 2000-03-12), `ODR.ERS-2/dgm-e04.fd` (2001-11-20 .. 2003-08-21) | - |

Envisat:

| Rank | Gravity model | Model date | Source of the date | Sets in this repository (arcs on the server) | Reported radial accuracy (source) |
|---|---|---|---|---|---|
| 1 | GDR-D | 2012 | the files only: the publish times in their names, 2012-02-22 .. 2012-12-19; their headers name no gravity model or standard | `Doris/vor` (2002-04-09 .. 2012-04-11) | - |
| 2 | EIGEN-CG03C | 2005 | Förste, C., Flechtner, F., Schmidt, R., et al. (2005), "A new high resolution global gravity field model derived from combination of GRACE and CHAMP mission and altimetry/gravimetry surface gravity data", poster, EGU General Assembly 2005, Vienna; ICGEM model table, <https://icgem.gfz-potsdam.de/tom_longtime> | `ODR.ENVISAT1/eigen-cg03c` (2002-04-09 .. 2008-01-06), `POE.ENVISAT1/eigen-cg03c` (2005-12-30 .. 2006-07-02) | - |

Accuracy sources: the Scharroo and Visser (1998) figures are their radial RMS orbit accuracy of Delft's ERS-1 and ERS-2 orbits of
the Tandem Mission (abstract, read from the Crossref record of doi:10.1029/97JC03179); the PRC figure is the D-PAF manual's
(above). The report "REAPER: ERS-1 and ERS-2 Orbit Validation Report" (Otten, M., Visser, P., Massmann, F.-H., Rudenko, S.,
Scharroo, R., 2011-06-20) uses Delft's DGM-E04 orbits as its reference: their altimeter crossover RMS is 8.28 cm (ERS-1, 1991-1996) and 7.31 cm (ERS-2,
1995-2003), the periods of its tables 4.1 and 4.2 (after 3.5-sigma editing), and REAPER's reprocessed orbits lower it by about 3 mm
(ERS-1) and 5 mm (ERS-2). A crossover RMS includes sea-surface variability and is not a radial orbit accuracy, so it is not in
the column; REAPER's orbits are not public and are not used here. No source read reports an accuracy for the other sets.

Why: a newer gravity model gives the more accurate orbit. The radial orbit error of these satellites depends on the accuracy
of the gravity field model, and Scharroo and Visser (1998) measure it for ERS: a radial RMS orbit accuracy of 7 cm with JGM-3
and 5 cm with DGM-E04; the D-PAF manual gives 8-10 cm for the PRC rev2 (PGM055) orbits. Sets of the same rank go by file
date, newest first (a later file is a later processing of the same solution). The preliminary (`dgm-e04.prelim`) and
automatic (`dgm-e04.auto`) Delft sets are excluded: they are not the final orbits of their model. The `dgm-e09spx` set
(DGM-E09) is excluded for the holes between its arcs (see Not used above).

Why the operational sets rank last: they share the DGM-E04 model with rank 3 but not its data. Every `dgm-e04.fd` file on the
server, ERS-1 (91) and ERS-2 (180), is listed with distribution version 402 in its set's arclist. The ERS-1 `dgm-e04.fd`
arclist describes the set as:

> Version description: DGM-E04 gravity field, Quick-look SLR normal points,
> DUT(LSC)98L02 coordinates, 6-hourly drag, dayly empir. accel.
> 402: Operational orbit.

while the precise `dgm-e04` sets (versions 405 and 424) are described as:

> Version description: DGM-E04 gravity field, Quick-look SLR, OPR single xovers,
> DUT(LSC)95L02 coordinates, 6-hourly drag, dayly empir. accel. 424: includes ERS
> dual xovers (simultaneous solution). 405: includes altimeter heights.

The operational orbits use no altimeter crossovers. (The ERS-2 `dgm-e04.fd` arclist repeats the precise description in its
header, but lists all 180 of its files as version 402.) As a fallback, ERS-1 `dgm-e04.fd` serves the 11 days no precise set
covers whole (1996-07-26 .. 1996-07-31 and 2000-03-08 .. 2000-03-12; on 1996-07-26 the PRC arcs end at 23:53), and ERS-2
`dgm-e04.fd` the 4 days 2002-03-15 .. 2002-03-18.

No day is decided by the order of JGM-3 against PGM055, nor by the order of the operational sets against JGM-3: on no day are
two such sets the two highest-ranked sets that compete for it (counted both among the sets covering the day whole and among
all sets covering any part of it).

The `eigen-grace01s` arclist header says "GRIM5-C1 gravity field" (the same description line as the `grim5-c1` set), while the
set's folder name says EIGEN-GRACE01S. The ranking is the same either way: if the set is a GRIM5-C1 solution, the two sets
share a model and go by file date, and `eigen-grace01s` (files of 2007-01 .. 2008-02) is newer than `grim5-c1` (files of 2003).

## Selection rule

The selection unit is the **UTC day**, per satellite, and the sets are ranked by the gravity-model ranking above:

1. **Whole-day set first.** The day goes to the highest-ranked set whose arcs together cover the **whole** day (00:00:00 to
   24:00:00 UTC). Between sets of the same rank, a set's production date for a day is the newest `produced` of its
   arcs covering that day.
2. Only when no set covers the whole day does the day go to the highest-ranked set that covers any part of it (the days listed
   below).
3. The day's `index.csv` lists the arcs of that one set that cover any part of the day, and only those.
4. An arc is kept (stored in the repository) when it is listed for at least one day; every other arc is dropped. The build log
   lists every dropped arc with its reason.

Why: a stack of scenes (an interferogram series over months or years) needs orbits from one consistent set, not orbits that
jump between sets from one scene to the next. With the per-day rule a stack switches sets only at the day boundaries between
periods (the coverage table below), and all scenes of one day take the same set. A set takes over on its first whole day: where
a higher-ranked set's first or last arc starts or ends inside a day, or its arcs leave hours of a day uncovered, that day stays
with a lower-ranked set that covers it whole, so no part of it is left without an orbit.

The ERS-2 `ODR.ERS-2/eigen-grace01s` set (2001-12-21 .. 2008-01-24) has four such breaks inside its period. There a 2002-2008
ERS-2 stack takes another set:
- 2002-03-11 .. 03-18: no set has an arc on 03-11 .. 03-14 (PRC included). On 03-15 .. 03-18 only the operational
  `ODR.ERS-2/dgm-e04.fd` does, and it serves those days.
- 2006-01-01 .. 01-02, 2006-03-02 .. 03-03 and 2007-12-09 .. 12-10: `ers_precise_orb/ERS2` (PRC).
The set is kept because it is the highest-ranked ERS-2 set.

**To find a scene's orbit:** read `<SATELLITE>/<YYYY>/<MM>/<DD>/index.csv` of the scene's UTC day (the day of its first line).
All its rows belong to one set. Of the rows whose span (`start` <= scene start, scene end <= `end`) covers the scene, take the
one whose span centre is nearest the scene. Take the nearest centre only among the arcs that cover the scene: when a long arc
and a short one are listed for one day, the short arc's centre can be nearer a scene that lies only in the long arc. When no
single arc covers the scene but it crosses from one arc to the next of the set (PRC arcs meet end to end: one ends at the
second the next starts), join the two arcs: in ESA's catalogue 15 ERS-2 `SAR_IMS_1P` frames. A scene that crosses midnight
takes the arcs of both days' indexes; in ESA's catalogue the two days of every such frame have the same set. A day without
`index.csv` has no orbit.

**Days no set covers whole.** On these days no set covers the whole day, so the day goes to the highest-ranked set covering
part of it; the stretch that set leaves open has no orbit in the repository (times UTC, to the second). Each lies at the edge
of a gap or at the first or last arc of a satellite:

| Satellite | Day | Day's set | Open stretch (no orbit) | Also covered by | `SAR_IMS_1P` / `ASA_IMS_1P` frames in it |
|---|---|---|---|---|---|
| ERS-1 | 1991-07-27 | `ers_precise_orb/ERS1` | 1991-07-27T00:00:00..1991-07-27T19:27:00 | - | 0 |
| ERS-1 | 1998-07-20 | `ers_precise_orb/ERS1` | 1998-07-20T00:00:00..1998-07-20T20:00:00 | - | 16 |
| ERS-1 | 2000-03-12 | `ODR.ERS-1/dgm-e04.fd` | 2000-03-12T12:00:00..2000-03-13T00:00:00 | - | 0 |
| ERS-2 | 1995-04-28 | `ODR.ERS-2/dgm-e04` | 1995-04-28T00:00:00..1995-04-28T12:00:00 | `PRC_950428_00103_rev2` from 07:06:00 | 0 |
| ERS-2 | 2001-01-21 | `ODR.ERS-2/dgm-e04` | 2001-01-21T12:00:00..2001-01-22T00:00:00 | - | 0 |
| ERS-2 | 2002-03-10 | `ODR.ERS-2/eigen-grace01s` | 2002-03-10T12:00:00..2002-03-11T00:00:00 | - | 0 |
| ERS-2 | 2002-03-15 | `ODR.ERS-2/dgm-e04.fd` | 2002-03-15T00:00:00..2002-03-15T12:00:00 | - | 0 |
| ERS-2 | 2010-12-29 | `ers_precise_orb/ERS2` | 2010-12-29T23:32:30..2010-12-30T00:00:00 | - | 25 |
| Envisat | 2010-10-31 | `Doris/vor` | 2010-10-31T00:23:26..2010-11-01T00:00:00 | - | 58 |
| Envisat | 2010-11-29 | `Doris/vor` | 2010-11-29T00:00:00..2010-11-29T21:55:26 | - | 96 |
| Envisat | 2012-04-11 | `Doris/vor` | 2012-04-11T00:23:26..2012-04-12T00:00:00 | - | 0 |

## Layout and index format

```
ERS1/  ERS2/  ENVISAT/
  index.csv                         every kept arc of the satellite
  <YYYY>/<MM>/<DD>/                 UTC day
    index.csv                       the arcs to use for this day (one set)
    <arc>.zip                       one zip per kept arc, in the folder of the arc's start day
```

Zip names: `ODR_<set>_<arc>.zip` holding the Delft `ODR.<arc>` (e.g. `ODR_eigen-grace01s_800.zip` holding `ODR.800`),
`POE_<set>_<arc>.zip` holding `envisat.<arc>.poe.gz`, `PRC_<yymmdd>_<orbit>_rev2.zip` holding the PRC file of that name, and
`DOR_VOR_AXVF-P<...>.zip` holding the DORIS file of that name. Each zip holds the original file, byte for byte.

`index.csv` columns:

| Column | Meaning |
|---|---|
| `path` | the zip, relative to the repository root |
| `start`, `end` | the arc's span, UTC, `YYYY-MM-DDTHH:MM:SS` |
| `source` | `TU Delft DEOS` or `ESA STEP` |
| `set` | the orbit set (the source folder) |
| `model` | the gravity model of the set's solution (see the ranking) |
| `produced` | the production date (see Sources); it ranks sets of the same rank |
| `sha256` | the SHA-256 of the original orbit file (the zip's member) |

Example: `ERS2/1997/12/18/index.csv`.

## Coverage

Arcs per set: all arcs on the server, the kept and dropped ones, the span of the kept arcs, and the number of days the set wins.

| Satellite | Set | Model | Produced | Arcs span | Arcs | Kept | Dropped | Kept span | Days won |
|---|---|---|---|---|---|---|---|---|---|
| ERS-1 | `ODR.ERS-1/dgm-e04` | DGM-E04 | 1996-11-13 .. 1998-12-27 | 1991-07-30 .. 1996-06-06 | 506 | 506 | 0 | 1991-07-30 .. 1996-06-06 | 1773 |
| ERS-1 | `ODR.ERS-1/dgm-e04.fd` (operational) | DGM-E04 | 1999-11-15 .. 2004-05-14 | 1996-06-04 .. 2000-03-12 | 91 | 4 | 87 | 1996-07-23 .. 2000-03-12 | 11 |
| ERS-1 | `ers_precise_orb/ERS1` (PRC) | PGM055 | 1995-03-24 | 1991-07-27 .. 2000-03-08 | 516 | 154 | 362 | 1991-07-27 .. 2000-03-08 | 650 |
| ERS-1 | `ODR.ERS-1/jgm3` | JGM-3 | 1996-02-13 .. 1997-04-21 | 1992-04-10 .. 1996-06-06 | 433 | 0 | 433 | - | 0 |
| ERS-2 | `ODR.ERS-2/eigen-grace01s` | EIGEN-GRACE01S | 2007-01-24 .. 2008-02-26 | 2001-12-21 .. 2008-01-24 | 629 | 629 | 0 | 2001-12-21 .. 2008-01-24 | 2210 |
| ERS-2 | `ODR.ERS-2/grim5-c1` | GRIM5-C1 | 2003-01-30 .. 2003-04-25 | 2001-12-21 .. 2003-03-27 | 128 | 0 | 128 | - | 0 |
| ERS-2 | `ODR.ERS-2/dgm-e04` | DGM-E04 | 1996-12-04 .. 2003-12-09 | 1995-04-28 .. 2003-08-14 | 857 | 690 | 167 | 1995-04-28 .. 2001-12-27 | 2415 |
| ERS-2 | `ODR.ERS-2/dgm-e04.fd` (operational) | DGM-E04 | 2001-11-27 .. 2003-12-04 | 2001-11-20 .. 2003-08-21 | 180 | 1 | 179 | 2002-03-15 .. 2002-03-21 | 4 |
| ERS-2 | `ers_precise_orb/ERS2` (PRC) | PGM055 | 1995-03-24 | 1995-04-28 .. 2011-07-06 | 1259 | 271 | 988 | 2006-01-01 .. 2011-07-06 | 1261 |
| ERS-2 | `ODR.ERS-2/jgm3` | JGM-3 | 1996-12-05 .. 2003-06-16 | 1995-04-28 .. 2003-03-27 | 817 | 0 | 817 | - | 0 |
| Envisat | `Doris/vor` | GDR-D | 2012-02-22 .. 2012-12-19 | 2002-04-09 .. 2012-04-11 | 3610 | 3610 | 0 | 2002-04-09 .. 2012-04-11 | 3613 |
| Envisat | `ODR.ENVISAT1/eigen-cg03c` | EIGEN-CG03C | 2007-01-19 .. 2008-02-07 | 2002-04-09 .. 2008-01-06 | 599 | 6 | 593 | 2002-04-09 .. 2002-06-13 | 15 |
| Envisat | `POE.ENVISAT1/eigen-cg03c` | EIGEN-CG03C | 2007-07-24 | 2005-12-30 .. 2006-07-02 | 52 | 0 | 52 | - | 0 |

The JGM-3 and GRIM5-C1 sets and the Envisat POE set win no day: a higher-ranked set covers every day they cover whole.

Days covered per satellite: ERS-1 2,434 (2,431 covered whole by a set, 3 not), ERS-2 5,890 (5,885 and 5), Envisat 3,628
(3,625 and 3).

Periods (UTC days) and the set that serves them:

| Satellite | Days | Set |
|---|---|---|
| ERS-1 | 1991-07-27 .. 1991-07-29, 1996-06-06 .. 1996-07-25, 1998-07-20 .. 2000-03-07 | PRC |
| ERS-1 | 1991-07-30 .. 1996-06-05 | `dgm-e04` |
| ERS-1 | 1996-07-26 .. 1996-07-31, 2000-03-08 .. 2000-03-12 | `dgm-e04.fd` (operational) |
| ERS-1 | 1996-08-01 .. 1998-07-19 | no orbit (gap) |
| ERS-2 | 1995-04-28 .. 2001-01-21, 2001-02-06 .. 2001-12-21 | `dgm-e04` |
| ERS-2 | 2001-01-22 .. 2001-02-05 | no orbit (gap) |
| ERS-2 | 2001-12-22 .. 2002-03-10, 2002-03-19 .. 2005-12-31, 2006-01-03 .. 2006-03-01, 2006-03-04 .. 2007-12-08, 2007-12-11 .. 2008-01-23 | `eigen-grace01s` |
| ERS-2 | 2002-03-11 .. 2002-03-14 | no orbit (gap) |
| ERS-2 | 2002-03-15 .. 2002-03-18 | `dgm-e04.fd` (operational) |
| ERS-2 | 2006-01-01 .. 2006-01-02, 2006-03-02 .. 2006-03-03, 2007-12-09 .. 2007-12-10, 2008-01-24 .. 2010-12-29, 2011-01-03 .. 2011-07-05 | PRC |
| ERS-2 | 2010-12-30 .. 2011-01-02 | no orbit (gap) |
| Envisat | 2002-04-09, 2002-05-28 .. 2002-06-10 | `ODR.ENVISAT1/eigen-cg03c` |
| Envisat | 2002-04-10 .. 2002-05-27, 2002-06-11 .. 2010-10-31, 2010-11-29 .. 2012-04-11 | `Doris/vor` |
| Envisat | 2010-11-01 .. 2010-11-28 | no orbit (gap) |

## Gaps

Spans that no arc of any set covers, to the second (UTC), and the whole days inside them:

| Satellite | No arc covers | Whole days without an orbit |
|---|---|---|
| ERS-1 | 1996-08-01T00:00:00 .. 1998-07-20T20:00:00 | 1996-08-01 .. 1998-07-19 (718 days) |
| ERS-2 | 2001-01-21T12:00:00 .. 2001-02-06T00:00:00 | 2001-01-22 .. 2001-02-05 (15 days) |
| ERS-2 | 2002-03-10T12:00:00 .. 2002-03-15T12:00:00 | 2002-03-11 .. 2002-03-14 (4 days) |
| ERS-2 | 2010-12-29T23:32:30 .. 2011-01-03T00:00:00 | 2010-12-30 .. 2011-01-02 (4 days) |
| Envisat | 2010-10-31T00:23:26 .. 2010-11-29T21:55:26 | 2010-11-01 .. 2010-11-28 (28 days) |

Before the first and after the last arc there is no orbit either: ERS-1 before 1991-07-27T19:27:00 and after
2000-03-12T12:00:00, ERS-2 before 1995-04-28T07:06:00 and after 2011-07-06T00:00:00, Envisat before 2002-04-09T00:00:00 and
after 2012-04-11T00:23:26. The open stretches of the days no set covers whole (above) have no orbit in the repository either;
each of them lies at one of these gaps or ends.

## Rebuild

`build.py` (Python 3.13 with `requests`) rebuilds the whole tree from the servers:

```bash
python3.13 build.py CACHE_DIR              # download what is missing into CACHE_DIR, then build the tree
python3.13 build.py CACHE_DIR --offline    # build from CACHE_DIR only
python3.13 build.py CACHE_DIR --download-only
```

The downloads go into `CACHE_DIR` (outside the repository; symlinks are resolved before this is checked) and are resumable: a
file whose size matches the server's is not downloaded again, an interrupted HTTP download continues from its partial file, and
every network step has a timeout and retries. The full download is about 2.95 GB (Delft about 0.60 GB, STEP about 2.35 GB).
The build writes `CACHE_DIR/build_log.txt` (the kept and dropped arcs with reasons, the gaps, the number of days of each kind,
and the days no set covers whole) and `CACHE_DIR/summary.json`. It rewrites only files whose content changed and lists the
files under `ERS1/`, `ERS2/` and `ENVISAT/` that it no longer produces; remove those with `git rm`.

The repository is about 1.02 GB in 17,829 files (ERS1 0.24 GB, ERS2 0.51 GB, ENVISAT 0.27 GB; no file above 50 MB).

## Sources and Attribution

- **TU Delft, Delft Institute for Earth-Oriented Space Research (DEOS).** Anonymous FTP
  `ftp://dutlru2.lr.tudelft.nl/pub/orbits/`. Sets used, with their gravity models (the sets that win no day compete under the
  ranking but have no arc in the repository):
  - `ODR.ERS-1/dgm-e04` and `ODR.ERS-2/dgm-e04`: DGM-E04 (precise);
  - `ODR.ERS-1/dgm-e04.fd` and `ODR.ERS-2/dgm-e04.fd`: DGM-E04 (operational orbits, a fallback, see the ranking);
  - `ODR.ERS-2/eigen-grace01s`: EIGEN-GRACE01S (its arclist says GRIM5-C1, see the ranking);
  - `ODR.ERS-2/grim5-c1`: GRIM5-C1 (no arc kept);
  - `ODR.ERS-1/jgm3` and `ODR.ERS-2/jgm3`: JGM-3 (no arc kept);
  - `ODR.ENVISAT1/eigen-cg03c` and `POE.ENVISAT1/eigen-cg03c`: EIGEN-CG03C.

  The gravity model is the name of each set's folder on the server and the description line of its arclist. The ODR and POE
  files name no producer; the arclists say "generated by the Delft Institute for Earth Oriented Space Research (DEOS)".
  Reference: Scharroo, R. and Visser, P. (1998), "Precise orbit determination
  and gravity field improvement for the ERS satellites", J. Geophys. Res. 103(C4), 8113-8127,
  [doi:10.1029/97JC03179](https://doi.org/10.1029/97JC03179).
- **ESA STEP auxiliary data server** `https://step.esa.int/auxdata/orbits/`:
  - the ERS PRC precise orbits, revision 2 (`ers_precise_orb/ERS1`, `ers_precise_orb/ERS2`), produced for ESA by the German
    Processing and Archiving Facility (D-PAF), whose orbit processing is done at the GeoForschungsZentrum Potsdam (GFZ). The
    producer is named by ESA's document, the D-PAF "Altimeter and Orbit Global Products Manual" ERS-D-GPM-31200
    (<https://earth.esa.int/eogateway/documents/20142/37627/ERS-Altimeter-and-Orbit-Global-Products-Manual.pdf>); the files'
    own header names only the product (`ERS1.ORB.PRC`, `ERS2.ORB.PRC`).
  - the Envisat DORIS precise orbits, `DOR_VOR_AX` (`Doris/vor`), published (the `P` time in the file names) between
    2012-02-22 and 2012-12-19. The files' own header names the processing centre as `O_M`, the station as `ORBITE MISSION`
    and the software as `orbito/4.2`; no producer is named beyond these fields.
- **Terms.** The orbit files remain the work of their producers and are redistributed unchanged, as published on these public
  servers. The scripts of this repository are under the [LICENSE](LICENSE) (BSD 3-Clause).
- **Serving.** The files are also served at `https://ersorbits.insar.dev/<path>` (a cache in front of this repository), e.g.
  <https://ersorbits.insar.dev/ERS2/1997/12/18/index.csv>.
