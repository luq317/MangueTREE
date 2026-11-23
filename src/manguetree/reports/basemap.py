"""Satellite background for the plot-location map of the reports.

Tiles come from the Esri World Imagery service, fetched with the standard library when the
report is made (they are cached in the temporary folder). Without internet access the
function returns None and the report keeps the plain map of coordinates."""
from __future__ import annotations

import io
import math
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TILE_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ATTRIBUTION = "Esri, Maxar, Earthstar Geographics"
MAX_TILES = 16          # per side: 4 x 4 tiles at most
MAX_ZOOM = 17
TIMEOUT = 6
_CACHE = Path(tempfile.gettempdir()) / "manguetree_tiles"
_OFFLINE_UNTIL = 0.0      # after a failed download the next tries wait a minute (no repeated timeouts)


def _xy(lat, lon, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    lat_r = math.radians(max(min(lat, 85.0511), -85.0511))
    y = (1 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2 * n
    return x, y


def padded_bounds(lat, lon, min_span=0.02, pad=0.25):
    """(lat0, lat1, lon0, lon1): the points' box with a margin and a minimum size."""
    la0, la1, lo0, lo1 = min(lat), max(lat), min(lon), max(lon)
    dla, dlo = max(la1 - la0, min_span), max(lo1 - lo0, min_span)
    cla, clo = (la0 + la1) / 2, (lo0 + lo1) / 2
    return cla - dla * (0.5 + pad), cla + dla * (0.5 + pad), clo - dlo * (0.5 + pad), clo + dlo * (0.5 + pad)


def choose_zoom(bounds, max_side=4, max_zoom=MAX_ZOOM):
    la0, la1, lo0, lo1 = bounds
    for z in range(max_zoom, 0, -1):
        x0, y1 = _xy(la0, lo0, z); x1, y0 = _xy(la1, lo1, z)
        if math.floor(x1) - math.floor(x0) + 1 <= max_side and math.floor(y1) - math.floor(y0) + 1 <= max_side:
            return z
    return 1


def _fetch(z, x, y):
    f = _CACHE / f"{z}_{x}_{y}.jpg"
    if f.exists():
        return f.read_bytes()
    import urllib.request
    req = urllib.request.Request(TILE_URL.format(z=z, x=x, y=y), headers={"User-Agent": "MangueTREE report"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = r.read()
    _CACHE.mkdir(parents=True, exist_ok=True)
    f.write_bytes(data)
    return data


def background(bounds, fetch=_fetch):
    """(RGB array, (lon0, lon1, lat0, lat1)) of the satellite image covering ``bounds``, or None
    when any tile cannot be downloaded."""
    import numpy as np
    from PIL import Image
    import time
    global _OFFLINE_UNTIL
    if fetch is _fetch and time.time() < _OFFLINE_UNTIL:
        return None
    la0, la1, lo0, lo1 = bounds
    z = choose_zoom(bounds)
    fx0, fy1 = _xy(la0, lo0, z); fx1, fy0 = _xy(la1, lo1, z)
    tx0, tx1, ty0, ty1 = int(math.floor(fx0)), int(math.floor(fx1)), int(math.floor(fy0)), int(math.floor(fy1))
    jobs = [(x, y) for y in range(ty0, ty1 + 1) for x in range(tx0, tx1 + 1)]
    try:
        with ThreadPoolExecutor(max_workers=8) as ex:
            imgs = list(ex.map(lambda p: fetch(z, p[0], p[1]), jobs))
        canvas = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
        for (x, y), raw in zip(jobs, imgs):
            canvas.paste(Image.open(io.BytesIO(raw)).convert("RGB").resize((256, 256)), ((x - tx0) * 256, (y - ty0) * 256))
    except Exception:
        if fetch is _fetch:
            _OFFLINE_UNTIL = time.time() + 60
        return None
    px = lambda v, t0: int(round((v - t0) * 256))
    crop = canvas.crop((px(fx0, tx0), px(fy0, ty0), px(fx1, tx0), px(fy1, ty0)))
    return np.asarray(crop), (lo0, lo1, la0, la1)
