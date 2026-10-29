"""H3 hexbin view for the regional potential map dashboard (DB-014), on synthetic data.

Same method as the Integrated Platform impact map: every location is indexed with
h3.latlng_to_cell, values are summed per cell, and cells are coloured by quantile class.
Hexagons are drawn as inline SVG on the server over raster basemap tiles (OpenStreetMap by
default, like the Integrated Platform). Set HUB_TILE_URL to an approved / self-hosted tile
server, or to an empty string to run fully offline without a basemap.
"""
import math
import os
import random
from urllib.parse import urlsplit

import h3

MAP_DASHBOARDS = {"DB-014"}
TILE_URL = os.environ.get("HUB_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
TILE_ATTRIBUTION = os.environ.get("HUB_TILE_ATTRIBUTION", "© OpenStreetMap contributors")


def tile_origin() -> str:
    """Origin the map page may load basemap images from (added to its CSP img-src)."""
    u = urlsplit(TILE_URL)
    return f"{u.scheme}://{u.netloc}" if u.scheme and u.netloc else ""
RESOLUTIONS = {7: "City", 8: "Area", 9: "Neighbourhood"}
DEFAULT_RESOLUTION = 8

METRICS = {
    "potential": dict(label="Untapped funding potential", unit="IDR bn", palette="orange"),
    "penetration": dict(label="Bank share of local funds", unit="%", palette="teal"),
    "dpk": dict(label="Bank third-party funds (DPK)", unit="IDR bn", palette="teal"),
    "casa_ratio": dict(label="CASA ratio", unit="%", palette="teal"),
    "customers": dict(label="Funding customers", unit="customers", palette="teal"),
    "branches": dict(label="Branches & outlets", unit="outlets", palette="slate"),
}
DEFAULT_METRIC = "potential"
PALETTES = {  # light → dark; 5 quantile classes
    "teal": ["#d4ecee", "#9fd0d4", "#5fb0b7", "#1f8790", "#00575f"],
    "orange": ["#fde4d6", "#fbbf9c", "#f6935f", "#e8682d", "#b8461a"],
    "slate": ["#e2e8f0", "#b6c2d1", "#8597ad", "#566a85", "#2f3f57"],
}

# Synthetic funding hot-spots in Greater Jakarta:
# name, regional office (wilayah), lat, lon, spread (deg), points, CASA share, market size vs. Bank funds.
AREAS = [
    ("Sudirman–Thamrin", "Jakarta Senayan", -6.2050, 106.8220, .012, 120, .78, 2.4),
    ("Kuningan", "Jakarta Senayan", -6.2290, 106.8310, .010, 80, .74, 2.9),
    ("Kebayoran Baru", "Jakarta Senayan", -6.2440, 106.7990, .012, 70, .61, 3.6),
    ("Kelapa Gading", "Jakarta Kota", -6.1600, 106.9060, .013, 75, .55, 4.4),
    ("Pluit", "Jakarta Kota", -6.1240, 106.7880, .012, 55, .52, 3.9),
    ("Tangerang", "Tangerang", -6.1790, 106.6320, .020, 50, .48, 4.8),
    ("BSD City", "Tangerang", -6.3010, 106.6530, .018, 60, .57, 5.6),
    ("Depok", "Bogor & Depok", -6.4000, 106.8190, .020, 45, .44, 3.3),
    ("Cibubur", "Bogor & Depok", -6.3660, 106.8900, .015, 35, .46, 4.6),
    ("Bogor", "Bogor & Depok", -6.5950, 106.8060, .018, 40, .42, 3.1),
    ("Bekasi", "Bekasi", -6.2390, 106.9930, .020, 55, .49, 4.1),
    ("Cikarang", "Bekasi", -6.3020, 107.1520, .022, 40, .66, 6.2),
]
WILAYAH = sorted({a[1] for a in AREAS})


def _locations():
    """Deterministic synthetic account clusters and branch outlets."""
    rnd = random.Random(14)
    out = []
    for name, wilayah, lat, lon, spread, n, casa, market in AREAS:
        for _ in range(n):
            dpk = rnd.lognormvariate(2.4, .7)  # IDR bn per cluster
            share = min(.95, max(.15, rnd.gauss(casa, .08)))
            out.append(dict(area=name, wilayah=wilayah, lat=rnd.gauss(lat, spread), lon=rnd.gauss(lon, spread * 1.2),
                            dpk=dpk, casa=dpk * share, market=dpk * rnd.uniform(.7, 1.3) * market,
                            customers=int(dpk * rnd.uniform(90, 160)), branch=rnd.random() < .12))
    return out


LOCATIONS = _locations()


def _breaks(values, k=5):
    vals = sorted(v for v in values if v > 0)
    return sorted({vals[max(0, int(len(vals) * (i + 1) / k) - 1)] for i in range(k)}) if vals else []


def _classify(v, breaks):
    return next((i for i, b in enumerate(breaks) if v <= b), len(breaks) - 1)


def _merc(lat, lon):
    return math.radians(lon), math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def _fmt(v):
    return f"{v:,.0f}" if v >= 100 else f"{v:,.1f}"


def hexmap(metric=DEFAULT_METRIC, resolution=DEFAULT_RESOLUTION, wilayah="", width=880):
    metric = metric if metric in METRICS else DEFAULT_METRIC
    resolution = resolution if resolution in RESOLUTIONS else DEFAULT_RESOLUTION
    wilayah = wilayah if wilayah in WILAYAH else ""
    locs = [loc for loc in LOCATIONS if not wilayah or loc["wilayah"] == wilayah]

    cells = {}
    for loc in locs:
        idx = h3.latlng_to_cell(loc["lat"], loc["lon"], resolution)
        c = cells.setdefault(idx, dict(dpk=0.0, casa=0.0, market=0.0, customers=0, branches=0, areas=set(),
                                       wilayah=set()))
        for k in ("dpk", "casa", "market", "customers"):
            c[k] += loc[k]
        c["branches"] += loc["branch"]
        c["areas"].add(loc["area"])
        c["wilayah"].add(loc["wilayah"])
    for c in cells.values():
        c["casa_ratio"] = 100 * c["casa"] / c["dpk"]
        c["potential"] = max(0.0, c["market"] - c["dpk"])
        c["penetration"] = 100 * c["dpk"] / c["market"]

    breaks = _breaks(c[metric] for c in cells.values())
    pal = PALETTES[METRICS[metric]["palette"]]

    # Project every hexagon vertex (Web Mercator) into one SVG viewport fitted to the selection.
    rings = {idx: [_merc(lat, lon) for lat, lon in h3.cell_to_boundary(idx)] for idx in cells}
    xs = [x for r in rings.values() for x, _ in r]
    ys = [y for r in rings.values() for _, y in r]
    pad = 34
    scale = (width - 2 * pad) / (max(xs) - min(xs))
    height = int((max(ys) - min(ys)) * scale + 2 * pad)

    def px(x, y):
        return round(pad + (x - min(xs)) * scale, 1), round(pad + (max(ys) - y) * scale, 1)

    # Basemap tiles (slippy-map z/x/y) that cover the viewport, placed with the same projection.
    tiles = []
    if TILE_URL:
        span = 2 * math.pi
        z = max(3, min(17, round(math.log2(scale * span / 256))))
        n = 2 ** z
        size = scale * span / n
        x0, x1 = min(xs) - pad / scale, max(xs) + pad / scale
        y0, y1 = min(ys) - pad / scale, max(ys) + pad / scale
        for tx in range(int((x0 / span + .5) * n), int((x1 / span + .5) * n) + 1):
            for ty in range(int((.5 - y1 / span) * n), int((.5 - y0 / span) * n) + 1):
                left, top = px((tx / n - .5) * span, (.5 - ty / n) * span)
                tiles.append(dict(url=TILE_URL.format(z=z, x=tx, y=ty), left=round(100 * left / width, 3),
                                  top=round(100 * top / height, 3), size=round(100 * size / width, 3)))

    out = []
    for idx, c in sorted(cells.items(), key=lambda kv: kv[1][metric]):
        cls = _classify(c[metric], breaks) if c[metric] > 0 else -1
        lat, lon = h3.cell_to_latlng(idx)
        out.append(dict(h3=idx, points=" ".join(f"{x},{y}" for x, y in (px(*p) for p in rings[idx])), cls=cls,
                        fill=pal[cls] if cls >= 0 else "#ffffff", value=c[metric],
                        area=", ".join(sorted(c["areas"])), wilayah=", ".join(sorted(c["wilayah"])),
                        potential=round(c["potential"], 1), penetration=round(c["penetration"], 1),
                        dpk=round(c["dpk"], 1), casa_ratio=round(c["casa_ratio"], 1), customers=c["customers"],
                        branches=c["branches"], center=f"{lat:.4f}, {lon:.4f}"))

    # Where a regional head should look first: most untapped potential, flagged when there is no outlet.
    priority = sorted(out, key=lambda c: -c["potential"])[:5]

    labels = []
    for name, wl, lat, lon, *_ in AREAS:
        if not wilayah or wl == wilayah:
            x, y = px(*_merc(lat, lon))
            labels.append(dict(name=name, x=x, y=round(y - 16, 1)))

    km_per_px = 6371 / scale * math.cos(math.radians(-6.3))
    bar_km = 5 if wilayah else 10
    legend, lo = [], 0
    for i, b in enumerate(breaks):
        legend.append(dict(color=pal[i], label=f"{_fmt(lo)} – {_fmt(b)}"))
        lo = b
    dpk, market = sum(c["dpk"] for c in cells.values()), sum(c["market"] for c in cells.values())
    return dict(
        metric=metric, metric_info=METRICS[metric], metrics=METRICS, resolution=resolution,
        resolutions=RESOLUTIONS, wilayah=wilayah, wilayah_options=WILAYAH, width=width, height=height,
        cells=out, labels=labels, legend=legend, priority=priority, tiles=tiles, attribution=TILE_ATTRIBUTION,
        scale_px=round(bar_km / km_per_px, 1), scale_km=bar_km, h3_version=h3.__version__,
        summary=dict(cells=len(cells), locations=len(locs), dpk=round(dpk), potential=round(market - dpk),
                     penetration=round(100 * dpk / market, 1), customers=sum(c["customers"] for c in cells.values()),
                     branches=sum(c["branches"] for c in cells.values()),
                     no_outlet=sum(1 for c in priority if not c["branches"])),
    )
