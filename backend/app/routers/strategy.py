"""
Strategy Recommendations API Router
"""
from fastapi import APIRouter
from typing import List
from app.models.schemas import PriorityZonesBundle, TimingWindowResponse
from app.services.data_loader import DataLoader
from app.services.spatial import generate_county_hex_grid, hex_bin_observations, build_fill_boundary
from app.services.scoring import calculate_timing_efficiency, calculate_priority_score, generate_recommendations
from app.config import HEX_RESOLUTION
import geopandas as gpd
from pathlib import Path
import shapely
from fastapi import Query
import numpy as np
import pandas as pd

router = APIRouter(prefix="/strategy", tags=["strategy"])

BACKEND_DIR = Path(__file__).resolve().parents[2]
SD_PATH = BACKEND_DIR / "data" / "San_Diego_County_Boundary_(GIS)_20260216.geojson"

if not SD_PATH.exists():
    raise FileNotFoundError(f"Boundary geojson not found: {SD_PATH}")

sd_boundary = gpd.read_file(SD_PATH, engine="pyogrio")

SD_COASTAL = BACKEND_DIR / "data" / "coastal_zones.geojson"
sd_coastal = gpd.read_file(SD_COASTAL, engine="pyogrio")

SD_GREENERY = BACKEND_DIR / "data" / "greenery.geojson"
sd_greenery = gpd.read_file(SD_GREENERY, engine="pyogrio", on_invalid="ignore")

# Pre-computed cache
_priority_zones_cache = None


def _compute_priority_zones():
    """Heavy computation — run once, cache forever."""
    global _priority_zones_cache
    if _priority_zones_cache is not None:
        return _priority_zones_cache

    print("Computing priority zones (this may take a minute)...")
    gdf = DataLoader.get_cached_data()

    fill_boundary = sd_boundary.to_crs("EPSG:26911").copy()
    fill_boundary["geometry"] = fill_boundary.buffer(10000)
    fill_boundary = fill_boundary.to_crs(sd_boundary.crs)

    hex_stats = hex_bin_observations(
        gdf=gdf,
        county_boundary=fill_boundary,
        resolution=7,
        min_non_cnc=30,
        use_existing_cnc_flag=True,
    )

    hex_scored = calculate_priority_score(hex_stats)
    hexs_finalized = generate_recommendations(hex_scored, gdf, top_n=len(hex_scored), parks_gdf=sd_greenery)

    _priority_zones_cache = {"hexes": hexs_finalized, "top": hexs_finalized}
    print(f"Priority zones computed: {len(hexs_finalized)} hexes cached.")
    return _priority_zones_cache


@router.get("/priority-zones")
async def get_priority_zones():
    try:
        return _compute_priority_zones()
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise


@router.get("/hex-observations/{hex_id}")
async def get_hex_observations(
    hex_id: str,
    type: str = Query(default="both", regex="^(non_cnc|cnc|both)$")
):
    gdf = DataLoader.get_cached_data()
    hex_obs = gdf[gdf["hex7"] == hex_id].copy()

    hex_obs["during_competition"] = pd.to_numeric(hex_obs["during_competition"], errors="coerce").fillna(0).astype(int)

    if type == "non_cnc":
        hex_obs = hex_obs[hex_obs["during_competition"] == 0]
    elif type == "cnc":
        hex_obs = hex_obs[hex_obs["during_competition"] == 1]

    def safe_str(val) -> str:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return "Unknown"
        return str(val)

    return [
        {
            "lat": float(row.geometry.y),
            "lng": float(row.geometry.x),
            "common_name": safe_str(row.get("common_name")),
            "iconic_taxon": safe_str(row.get("iconic_taxon_name")),
            "is_cnc": bool(row["during_competition"]),
        }
        for _, row in hex_obs.iterrows()
        if row.geometry is not None
    ]