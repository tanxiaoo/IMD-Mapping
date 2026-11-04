"""Shared style for the imperviousness maps of the paper (Milan, Hanoi, HCMC).

Layout follows the LCZ reference figure: street basemap around the raster, UTM
grid labels, optional administrative outline, classed legend (C0-C6 of
Section 3.1, inverted RdYlGn), scale bar and north arrow.
"""
import io
import time
import warnings
from dataclasses import dataclass
from pathlib import Path

import contextily as cx
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Polygon, Rectangle
from PIL import Image
from pyproj import Transformer
from rasterio.warp import Resampling, reproject
from rasterio.windows import from_bounds

REPO = Path(__file__).resolve().parents[2]
COMUNI = Path(r"C:\Users\user\OneDrive - Politecnico di Milano\00LCZ\geo_tessera\report\files"
              r"\Limiti amministrativi Comunali 2020 con aggiornamenti DbT_PGT poligon_20260612"
              r"\geo_export_15a64904-a6bd-40cf-a45c-ea99bc486a64.shp")
NEEDABLES = Path(r"C:\Users\user\OneDrive - Politecnico di Milano\00LCZ\Matej_impervious\Paper_needables")
OUT_PNG = NEEDABLES / "figure_jpeg_png"   # PNG (300 dpi)
OUT_TIFF = NEEDABLES / "figure_tiff"     # TIFF (300 dpi, RGB, uncompressed)
OUT_TABLES = NEEDABLES / "tables_csv_xls"
BOUNDARY = "#2b6cb0"
ATTRIBUTION = "Basemap: Esri World Street Map (Esri, HERE, Garmin, © OpenStreetMap contributors)"

# Imperviousness classes C0-C6 of the paper (Section 3.1).
BOUNDS = [-0.5, 0.5, 20.5, 40.5, 60.5, 80.5, 99.5, 100.5]
LABELS = ["0%", "1–20%", "21–40%", "41–60%", "61–80%", "81–99%", "100%"]
COLORS = [plt.get_cmap("RdYlGn_r")(v) for v in np.linspace(0, 1, 7)]  # inverted RdYlGn
CMAP = ListedColormap(COLORS)
NORM = BoundaryNorm(BOUNDS, CMAP.N)

# Difference maps (prediction - benchmark, percentage points): blue = under-, red = over-prediction.
DIFF_BOUNDS = [-100.5, -60, -40, -20, -5, 5, 20, 40, 60, 100.5]
DIFF_LABELS = ["< −60", "−60 to −40", "−40 to −20", "−20 to −5", "−5 to 5",
               "5 to 20", "20 to 40", "40 to 60", "> 60"]
DIFF_COLORS = [plt.get_cmap("RdBu_r")(v) for v in np.linspace(0.02, 0.98, 9)]
DIFF_COLORS[4] = "#e0e0e0"   # near-zero class in light grey so it does not read as no data
DIFF_CMAP = ListedColormap(DIFF_COLORS)
DIFF_NORM = BoundaryNorm(DIFF_BOUNDS, DIFF_CMAP.N)


@dataclass
class Style:
    cmap: object
    norm: object
    colors: list
    labels: list
    nodata: str = None    # fill for gaps inside the AOI; None lets the basemap show through


IMD = Style(CMAP, NORM, COLORS, LABELS)
# Gaps are filled in white: the basemap's blue water would read as a small negative difference.
DIFF = Style(DIFF_CMAP, DIFF_NORM, DIFF_COLORS, DIFF_LABELS, nodata="white")


@dataclass
class City:
    name: str
    crs: str
    aoi: tuple            # (left, right, bottom, top) of the study area, in crs
    pad: float            # m of basemap shown around the AOI
    tick_step: int        # m between grid labels
    scalebar_km: float    # total scale-bar length
    zoom: int             # basemap zoom level
    boundary: object = None        # GeoDataFrame or None
    boundary_label: str = ""

    @property
    def view(self):
        l, r, b, t = self.aoi
        return (l - self.pad, r + self.pad, b - self.pad, t + self.pad)


def milan():
    g = gpd.read_file(COMUNI)
    metro = g[g["nome_pro"].str.upper() == "MILANO"].to_crs("EPSG:32632").dissolve()
    return City("Milan", "EPSG:32632", (474450, 552300, 5004840, 5062720), 3000, 20000, 20, 11,
                metro, "Metropolitan City of Milan")


# The 30 x 30 km AOIs lie wholly inside the city boundaries, so no outline is drawn.
HANOI = City("Hanoi", "EPSG:32648", (573320, 603330, 2310700, 2340710), 1500, 10000, 10, 12)
HCMC = City("HCMC", "EPSG:32648", (670870, 700880, 1177160, 1207170), 1500, 10000, 10, 12)


def read_imd(path, city, factor=1):
    """IMD raster clipped to the city AOI, block-averaged by `factor` (ignoring nodata, so
    isolated gaps such as cloudy stack pixels do not blank whole blocks), then rounded to
    whole percent so values fall in the C0-C6 classes."""
    l, r, b, t = city.aoi
    with rasterio.open(path) as src:
        win = from_bounds(l, b, r, t, src.transform).round_offsets().round_lengths()
        a = src.read(1, window=win, masked=True).astype("float32").filled(np.nan)
        wb = rasterio.windows.bounds(win, src.transform)
        res = src.res[0]
    a[~np.isfinite(a)] = np.nan
    left, bottom, right, top = wb
    if factor > 1:
        a, nr, nc = block_mean(a, factor)
        right, bottom = left + nc * res, top - nr * res
    return np.ma.masked_invalid(np.round(a)), (left, right, bottom, top)


def block_mean(a, factor):
    nr, nc = (a.shape[0] // factor) * factor, (a.shape[1] // factor) * factor
    blocks = a[:nr, :nc].reshape(nr // factor, factor, nc // factor, factor)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(blocks, axis=(1, 3)), nr, nc


def read_diff(pair, city, factor=1):
    """Prediction minus benchmark (percentage points) over the city AOI, at the 10 m
    prediction grid. The benchmark is resampled (nearest) onto that grid, since the
    Vietnam GHSL grid is offset from it; benchmark values > 100 are nodata. Block
    averaging is applied to the 10 m difference."""
    pred_path, bench_path = pair
    l, r, b, t = city.aoi
    with rasterio.open(pred_path) as src:
        win = from_bounds(l, b, r, t, src.transform).round_offsets().round_lengths()
        pred = src.read(1, window=win, masked=True).astype("float32").filled(np.nan)
        tf = src.window_transform(win)
        left, bottom, right, top = rasterio.windows.bounds(win, src.transform)
        res = src.res[0]
    bench = np.full(pred.shape, np.nan, dtype="float32")
    with rasterio.open(bench_path) as src:
        reproject(src.read(1).astype("float32"), bench, src_transform=src.transform,
                  src_crs=src.crs, src_nodata=src.nodata, dst_transform=tf, dst_crs=src.crs,
                  dst_nodata=np.nan, resampling=Resampling.nearest)
    bench[bench > 100] = np.nan
    d = pred - bench
    d[~np.isfinite(d)] = np.nan
    if factor > 1:
        d, nr, nc = block_mean(d, factor)
        right, bottom = left + nc * res, top - nr * res
    return np.ma.masked_invalid(d), (left, right, bottom, top)


def load(src, city, factor=1):
    """A raster path gives the IMD map; a (prediction, benchmark) pair gives their difference."""
    return read_diff(src, city, factor) if isinstance(src, tuple) else read_imd(src, city, factor)


def basemap(city):
    """Fetch the basemap once so every panel uses the same image."""
    v = city.view
    tr = Transformer.from_crs(city.crs, "EPSG:4326", always_xy=True)
    lons, lats = tr.transform([v[0], v[1], v[0], v[1]], [v[2], v[2], v[3], v[3]])
    img, ext = cx.bounds2img(min(lons), min(lats), max(lons), max(lats), zoom=city.zoom,
                             ll=True, source=cx.providers.Esri.WorldStreetMap)
    return cx.warp_tiles(img, ext, t_crs=city.crs)


def draw(ax, imd, extent, base, city, label, letter=None,
         xlabels=("top", "bottom"), ylabels=("left",), style=IMD):
    v = city.view
    img, ext = base
    ax.imshow(img, extent=ext, alpha=0.8, interpolation="bilinear", zorder=1)
    if style.nodata:
        ax.add_patch(Rectangle((extent[0], extent[2]), extent[1] - extent[0],
                               extent[3] - extent[2], facecolor=style.nodata, zorder=1.5))
    ax.imshow(imd, extent=extent, cmap=style.cmap, norm=style.norm, interpolation="nearest",
              zorder=2)
    if city.boundary is not None:
        city.boundary.boundary.plot(ax=ax, color=BOUNDARY, linewidth=0.9, zorder=3)
    ax.set_xlim(v[0], v[1])
    ax.set_ylim(v[2], v[3])
    ax.set_aspect("equal")

    # Grid labels only at least 2 km inside the AOI, so they never reach the panel edges.
    s, (l, r, b, t), m = city.tick_step, city.aoi, 2000
    xt = list(range(int(np.ceil((l + m) / s) * s), int(r - m) + 1, s))
    yt = list(range(int(np.ceil((b + m) / s) * s), int(t - m) + 1, s))
    ax.set_xticks(xt, [f"{x:d}E" for x in xt], fontsize=6.5)
    ax.set_yticks(yt, [f"{y:d}N" for y in yt], fontsize=6.5, rotation=90, va="center")
    ax.tick_params(top=True, bottom=True, left=True, right=True, length=2.5,
                   labeltop="top" in xlabels, labelbottom="bottom" in xlabels,
                   labelleft="left" in ylabels, labelright="right" in ylabels)
    for sp in ax.spines.values():
        sp.set_linewidth(0.6)

    box = dict(facecolor="white", edgecolor="0.3", linewidth=0.5, pad=2.0)
    ax.text(0.025, 0.03, label, transform=ax.transAxes, fontsize=7, va="bottom", ha="left",
            zorder=5, bbox=box)
    if letter:
        ax.text(0.03, 0.965, letter, transform=ax.transAxes, fontsize=7.5, va="top", ha="left",
                zorder=5, bbox=dict(boxstyle="circle,pad=0.25", facecolor="white",
                                    edgecolor="0.3", linewidth=0.5))


def legend(fig, rect, title, city, style=IMD):
    lax = fig.add_axes(rect)
    lax.axis("off")
    handles = [Patch(facecolor=c, edgecolor="0.4", linewidth=0.3, label=l)
               for c, l in zip(style.colors, style.labels)]
    if style.nodata:
        handles.append(Patch(facecolor=style.nodata, edgecolor="0.4", linewidth=0.3,
                             label="No data (water, clouds)"))
    if city.boundary is not None:
        handles.append(Line2D([], [], color=BOUNDARY, lw=1.1, label=city.boundary_label))
    lax.legend(handles=handles, title=title, ncol=2, loc="upper left", fontsize=7,
               title_fontsize=7.5, frameon=False, handlelength=1.6, handleheight=1.0,
               columnspacing=1.5, alignment="left")


def scalebar_north(fig, x, y, ref_ax, city):
    """Scale bar drawn at the true scale of `ref_ax`, plus a north arrow to its right."""
    ref_ax.apply_aspect()
    pos = ref_ax.get_position()
    v = city.view
    km = city.scalebar_km
    w = pos.width * km * 1000 / (v[1] - v[0])          # figure fraction for `km`
    sax = fig.add_axes([x, y, w, 0.10])
    sax.axis("off")
    sax.set_xlim(0, km)
    sax.set_ylim(0, 3)
    half = km / 2
    for i, x0 in enumerate([0, half]):
        sax.add_patch(Rectangle((x0, 1.0), half, 0.3, facecolor="black" if i == 0 else "white",
                                edgecolor="black", linewidth=0.6, clip_on=False))
    fmt = lambda d: f"{d:g}"
    for xx, t in [(0, "0"), (half, fmt(half)), (km, f"{fmt(km)} km")]:
        sax.text(xx, 1.6, t, ha="center", va="bottom", fontsize=7, clip_on=False)
    nax = fig.add_axes([x + w + 0.04, y, 0.05, 0.10])
    nax.axis("off")
    nax.set_xlim(-1, 1)
    nax.set_ylim(0, 3)
    nax.add_patch(Polygon([(-0.6, 0.4), (0, 2.4), (0, 0.9)], closed=True, facecolor="white",
                          edgecolor="black", lw=0.6))
    nax.add_patch(Polygon([(0.6, 0.4), (0, 2.4), (0, 0.9)], closed=True, facecolor="black",
                          edgecolor="black", lw=0.6))
    nax.text(0, 2.5, "N", ha="center", va="bottom", fontsize=8, fontweight="bold")


def single_map(raster, city, label, legend_title, stem, base=None, style=IMD):
    """One map with legend, scale bar and north arrow. `raster` as in `load`."""
    imd, extent = load(raster, city, factor=4 if city.name == "Milan" else 1)
    base = base if base is not None else basemap(city)
    v = city.view
    aspect = (v[3] - v[2]) / (v[1] - v[0])
    width, map_w = 7.0, 0.84
    map_h_in = map_w * width * aspect
    top_in, bottom_in = 0.35, 1.9                     # top labels; bottom labels + legend
    height = top_in + map_h_in + bottom_in
    fig = plt.figure(figsize=(width, height))
    ax = fig.add_axes([0.09, bottom_in / height, map_w, map_h_in / height])
    draw(ax, imd, extent, base, city, label, style=style)
    legend(fig, [0.09, 0.15 / height, 0.55, 1.35 / height], legend_title, city, style)
    scalebar_north(fig, 0.62, 0.45 / height, ax, city)
    fig.text(0.93, 0.005, ATTRIBUTION, ha="right", va="bottom", fontsize=5.5, color="0.35")
    save(fig, stem)


def panel_figure(maps, city, title, stem, ncols, base=None, factor=1, width=7.2, style=IMD):
    """Grid of maps (letters a, b, ...) sharing one legend, scale bar and north arrow.
    `maps` is a list of (raster, label), raster as in `load`. Grid labels on the outer
    sides only."""
    base = base if base is not None else basemap(city)
    v = city.view
    aspect = (v[3] - v[2]) / (v[1] - v[0])
    nrows = -(-len(maps) // ncols)
    left, gap_x, right = 0.075, 0.015, 0.075
    w = (1 - left - right - gap_x * (ncols - 1)) / ncols
    panel_h_in = w * width * aspect
    top_in, gap_in, bottom_in = 0.35, 0.12, 1.55       # labels, row gap, legend area
    height = top_in + nrows * panel_h_in + (nrows - 1) * gap_in + 0.25 + bottom_in
    fig = plt.figure(figsize=(width, height))
    axes = []
    for i, (raster, label) in enumerate(maps):
        r, c = divmod(i, ncols)
        y_in = height - top_in - (r + 1) * panel_h_in - r * gap_in
        ax = fig.add_axes([left + c * (w + gap_x), y_in / height, w, panel_h_in / height])
        imd, ext = load(raster, city, factor=factor)
        # A panel with no panel below it gets bottom labels (short last row in a 2 x 3 grid).
        last = r == nrows - 1 or i + ncols >= len(maps)
        xl = (("top",) if r == 0 else ()) + (("bottom",) if last else ())
        yl = (("left",) if c == 0 else ()) + (("right",) if c == ncols - 1 else ())
        draw(ax, imd, ext, base, city, label, letter="abcdefgh"[i], xlabels=xl, ylabels=yl,
             style=style)
        axes.append(ax)
    legend(fig, [left, 0.15 / height, 0.55, (bottom_in - 0.2) / height], title, city, style)
    scalebar_north(fig, 0.60, 0.45 / height, axes[0], city)
    fig.text(1 - right, 0.003, ATTRIBUTION, ha="right", va="bottom", fontsize=5.5, color="0.35")
    save(fig, stem)


def save(fig, stem):
    OUT_PNG.mkdir(parents=True, exist_ok=True)
    OUT_TIFF.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300)
    img = Image.open(buf)
    # TIFF: RGB, uncompressed (Pillow's compressed TIFF writers crash on this machine).
    for write in (lambda: img.save(OUT_PNG / f"{stem}.png", dpi=(300, 300)),
                  lambda: img.convert("RGB").save(OUT_TIFF / f"{stem}.tif", dpi=(300, 300))):
        for attempt in range(5):   # OneDrive briefly locks files while syncing them
            try:
                write()
                break
            except OSError:
                if attempt == 4:
                    raise
                time.sleep(2)
    plt.close(fig)
    print("written", stem, "(png, tif)")
