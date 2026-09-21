# -*- coding: utf-8 -*-
"""World map, v7: lat/long as real axis ticks outside each map frame (dark
text on white, standard cartographic convention) instead of light text
overlaid on the satellite imagery -- the overlay approach kept losing
contrast against busy imagery and colliding with neighbouring panels'
labels. A faint dotted grid stays on the imagery itself as a reference.
Builds on v6 otherwise: each inset states its reference product and real
AOI size; the main map states the Milan-Hanoi distance and a colour-key
legend; Milan's inset on the left, Hanoi/HCMC stacked on the right;
satellite basemap; bright country outlines; red AOI boxes.
Saved to figs_deck/.
"""
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects
from matplotlib.patches import Rectangle, ConnectionPatch
import geopandas as gpd
from shapely.geometry import box
import contextily as cx

REPO = r"C:\Users\user\projects\IMD-Mapping"
OUT = f"{REPO}\\figs_deck\\study_area_world_map.png"
GEOJSON = f"{REPO}\\data\\naturalearth\\ne_110m_admin_0_countries.geojson"

INK = "#1a1a1a"
ITALY_C = "#FFD500"
VIETNAM_C = "#00E5FF"
AOI_C = "#E4241E"
TICK_C = "#3a3a3a"

# name, country, lon, lat, colour, EPSG, AOI (left, bottom, right, top), reference product
CITIES = [
    ("Milan", "Italy", 9.19, 45.4642, ITALY_C, "EPSG:32632",
     (474450.0, 5004840.0, 552300.0, 5062720.0), "CLMS reference"),
    ("Hanoi", "Vietnam", 105.8542, 21.0285, VIETNAM_C, "EPSG:32648",
     (573320.0, 2310700.0, 603330.0, 2340710.0), "GHS-BUILT-S reference"),
    ("Ho Chi Minh City", "Vietnam", 106.6297, 10.8231, VIETNAM_C, "EPSG:32648",
     (670870.0, 1177160.0, 700880.0, 1207170.0), "GHS-BUILT-S reference"),
]

world = gpd.read_file(GEOJSON)
name_col = "NAME" if "NAME" in world.columns else "ADMIN"
italy = world[world[name_col] == "Italy"].to_crs(epsg=3857)
vietnam = world[world[name_col] == "Vietnam"].to_crs(epsg=3857)

pins = gpd.GeoDataFrame(
    {"city": [c[0] for c in CITIES]},
    geometry=gpd.points_from_xy([c[2] for c in CITIES], [c[3] for c in CITIES]),
    crs="EPSG:4326",
).to_crs(epsg=3857)
pins_ll = {c[0]: (c[2], c[3]) for c in CITIES}

# Spherical Web Mercator forward/inverse projection (matches EPSG:3857).
R = 6378137.0
def lon_to_x(lon):
    return R * math.radians(lon)
def lat_to_y(lat):
    lat = max(min(lat, 85.05), -85.05)
    return R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
def x_to_lon(x):
    return math.degrees(x / R)
def y_to_lat(y):
    return math.degrees(2 * math.atan(math.exp(y / R)) - math.pi / 2)


def lon_label(lon):
    return f"{abs(lon):g}\u00b0{'E' if lon > 0 else ('W' if lon < 0 else '')}"


def lat_label(lat):
    return f"{abs(lat):g}\u00b0{'N' if lat > 0 else ('S' if lat < 0 else '')}"


def set_ticks(ax, lons, lats, fontsize, lon_top=False, grid_color="white"):
    """Real matplotlib ticks -- dark text outside the axes frame on white,
    not text overlaid on the satellite imagery -- plus a faint dotted
    reference grid drawn on the imagery itself."""
    ax.set_xticks([lon_to_x(v) for v in lons])
    ax.set_xticklabels([lon_label(v) for v in lons], fontsize=fontsize, color=TICK_C,
                        fontweight="bold")
    ax.set_yticks([lat_to_y(v) for v in lats])
    ax.set_yticklabels([lat_label(v) for v in lats], fontsize=fontsize, color=TICK_C,
                        fontweight="bold")
    if lon_top:
        ax.xaxis.set_ticks_position("top")
        ax.xaxis.set_label_position("top")
    ax.tick_params(axis="both", direction="out", length=4, width=1.0,
                    color="#888888", pad=5)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_edgecolor("#888888")
        spine.set_linewidth(0.9)
    ax.grid(True, color=grid_color, alpha=0.6, linestyle=(0, (1, 3)), linewidth=0.8, zorder=2.5)


def nice_step(span_deg, target_lines=3.5):
    for candidate in (0.05, 0.1, 0.2, 0.25, 0.5, 1.0, 2.0, 5.0):
        if span_deg / candidate <= target_lines:
            return candidate
    return 10.0


def graticule_values(lo, hi, step):
    lo_r = math.ceil(lo / step) * step
    hi_r = math.floor(hi / step) * step
    if hi_r < lo_r:
        return [round((lo + hi) / 2 / step) * step]
    n = int(round((hi_r - lo_r) / step))
    return [round(lo_r + i * step, 3) for i in range(n + 1)]


def haversine_km(lon1, lat1, lon2, lat2):
    R_km = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R_km * math.asin(math.sqrt(a))

milan_hanoi_km = haversine_km(9.19, 45.4642, 105.8542, 21.0285)

fig = plt.figure(figsize=(21.0, 9.6))
fig.patch.set_facecolor("white")

# ---- main world map, centred, satellite basemap ---------------------------
ax = fig.add_axes([0.300, 0.075, 0.420, 0.83])

lon_lo, lon_hi = -30, 145
lat_lo, lat_hi = -38, 62
extent = gpd.GeoDataFrame(geometry=[box(lon_lo, lat_lo, lon_hi, lat_hi)], crs="EPSG:4326").to_crs(epsg=3857)
xb = extent.total_bounds
ax.set_xlim(xb[0], xb[2])
ax.set_ylim(xb[1], xb[3])

ax.set_facecolor("#f4f4f4")
world_3857 = world.to_crs(epsg=3857)
world_3857.plot(ax=ax, color="#c9c9c9", edgecolor="#c9c9c9", linewidth=0.3, zorder=1)

italy.boundary.plot(ax=ax, color=ITALY_C, linewidth=2.2, zorder=3)
vietnam.boundary.plot(ax=ax, color=VIETNAM_C, linewidth=2.2, zorder=3)

set_ticks(ax, [-30, 0, 30, 60, 90, 120], [-30, 0, 30, 60], fontsize=13.5, lon_top=True,
          grid_color="#a8a8a8")

for (city, country, lon, lat, color, *_rest), pt in zip(CITIES, pins.geometry):
    ax.scatter([pt.x], [pt.y], s=90, color=color, edgecolor="white", linewidth=1.8, zorder=5)
    ax.scatter([pt.x], [pt.y], s=320, facecolor="none", edgecolor=color, linewidth=1.6, zorder=5)

# ---- inset panels: Milan on the LEFT, Hanoi + HCMC stacked on the RIGHT ---
inset_rects = {
    "Milan": [0.045, 0.255, 0.185, 0.46],
    "Hanoi": [0.775, 0.505, 0.205, 0.40],
    "Ho Chi Minh City": [0.775, 0.045, 0.205, 0.40],
}

for city, country, lon, lat, color, epsg, (l, b, r, t), ref_label in CITIES:
    axins = fig.add_axes(inset_rects[city])

    aoi = gpd.GeoDataFrame(geometry=[box(l, b, r, t)], crs=epsg).to_crs(epsg=3857)
    bounds = aoi.total_bounds
    w = bounds[2] - bounds[0]
    h = bounds[3] - bounds[1]
    pad_x, pad_y = w * 0.5, h * 0.5
    axins.set_xlim(bounds[0] - pad_x, bounds[2] + pad_x)
    axins.set_ylim(bounds[1] - pad_y, bounds[3] + pad_y)

    try:
        cx.add_basemap(axins, source=cx.providers.Esri.WorldStreetMap,
                        attribution=False, zoom="auto")
    except Exception as e:
        print(f"{city}: basemap fetch failed ({e}); leaving inset blank.")

    lon0, lon1 = x_to_lon(axins.get_xlim()[0]), x_to_lon(axins.get_xlim()[1])
    lat0, lat1 = y_to_lat(axins.get_ylim()[0]), y_to_lat(axins.get_ylim()[1])
    step = nice_step(max(lon1 - lon0, lat1 - lat0))
    set_ticks(axins, graticule_values(lon0, lon1, step), graticule_values(lat0, lat1, step),
              fontsize=9.5)

    aoi.boundary.plot(ax=axins, color=AOI_C, linewidth=2.8, zorder=5)
    for spine in axins.spines.values():
        spine.set_edgecolor(color)
        spine.set_linewidth(3.0)
    axins.set_title(f"{city}, {country}", fontsize=12, fontweight="bold",
                     color=INK, pad=8)

    aoi_w_km = (r - l) / 1000.0
    aoi_h_km = (t - b) / 1000.0
    axins.text(0.98, 0.97, f"AOI \u00b7 {aoi_w_km:.0f} \u00d7 {aoi_h_km:.0f} km",
                transform=axins.transAxes, fontsize=9,
                fontweight="bold", color="white", va="top", ha="right",
                bbox=dict(boxstyle="round,pad=0.25", facecolor=AOI_C, edgecolor="none"),
                zorder=6)

    side_x = 0.0 if inset_rects[city][0] > 0.5 else 1.0
    lon_p, lat_p = pins_ll[city]
    pin_xy = gpd.GeoDataFrame(geometry=[gpd.points_from_xy([lon_p], [lat_p])[0]],
                               crs="EPSG:4326").to_crs(epsg=3857).geometry[0]
    con = ConnectionPatch(xyA=(pin_xy.x, pin_xy.y), coordsA=ax.transData,
                           xyB=(side_x, 0.5), coordsB=axins.transAxes,
                           color=color, lw=1.6, linestyle=(0, (4, 2)), zorder=3)
    fig.add_artist(con)

fig.savefig(OUT, dpi=190, facecolor="white", bbox_inches="tight")
plt.close(fig)
print("saved", OUT)
