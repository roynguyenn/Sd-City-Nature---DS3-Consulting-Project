"""
Lightweight FastAPI server that serves pre-computed static JSON files.
No pandas, geopandas, h3, or heavy computation needed at runtime.
Memory usage: ~50MB.
"""
import json
import os
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional

app = FastAPI(
    title="SD City Nature Challenge API",
    description="Backend API for biodiversity observation analysis",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static_api"
HEX_OBS_DIR = STATIC_DIR / "hex_obs"


def _load(name: str):
    """Load a pre-computed JSON file."""
    path = STATIC_DIR / f"{name}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _competition_key(competition_only: Optional[bool]) -> str:
    if competition_only is None:
        return "all"
    return "competition" if competition_only else "non_competition"


# ── Health ──────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"message": "SD City Nature Challenge API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# ── Exploratory ─────────────────────────────────────────────────
@app.get("/api/exploratory/dashboard")
async def get_exploratory_dashboard(
    competition_only: Optional[bool] = Query(None),
):
    key = _competition_key(competition_only)
    data = _load(f"exploratory_dashboard_{key}")
    if data is None:
        data = _load("exploratory_dashboard_all")
    return data or {}


@app.get("/api/exploratory/observations")
async def get_observations(
    limit: int = Query(50000, ge=1, le=500000),
    competition_only: Optional[bool] = Query(None),
    research_grade_only: bool = Query(False),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    key = _competition_key(competition_only)
    data = _load(f"exploratory_observations_{key}")
    if data is None:
        data = _load("exploratory_observations_all")
    if data is None:
        return []

    # Apply filters on pre-computed data
    if research_grade_only:
        data = [d for d in data if d.get("quality_grade") == "research"]
    if date_from:
        data = [d for d in data if d.get("observed_on", "") >= date_from]
    if date_to:
        data = [d for d in data if d.get("observed_on", "") <= date_to]

    return data[:limit]


@app.get("/api/exploratory/taxonomy-summary")
async def get_taxonomy_summary(competition_only: Optional[bool] = Query(None)):
    key = _competition_key(competition_only)
    dashboard = _load(f"exploratory_dashboard_{key}")
    if dashboard and "taxonomy_summary" in dashboard:
        return dashboard["taxonomy_summary"]
    return []


@app.get("/api/exploratory/temporal-trends")
async def get_temporal_trends(competition_only: Optional[bool] = Query(None)):
    key = _competition_key(competition_only)
    dashboard = _load(f"exploratory_dashboard_{key}")
    if dashboard and "temporal_trends" in dashboard:
        return dashboard["temporal_trends"]
    return []


@app.get("/api/exploratory/user-contribution")
async def get_user_contribution(competition_only: Optional[bool] = Query(None)):
    key = _competition_key(competition_only)
    dashboard = _load(f"exploratory_dashboard_{key}")
    if dashboard and "user_contribution" in dashboard:
        buckets = dashboard["user_contribution"].get("buckets", [])
        return [{"bucket_label": b["bucket_label"], "user_count": b["user_count"]} for b in buckets]
    return []


@app.get("/api/exploratory/species-accumulation")
async def get_species_accumulation(competition_only: Optional[bool] = Query(None)):
    key = _competition_key(competition_only)
    data = _load(f"exploratory_species_accumulation_{key}")
    if data is None:
        data = _load("exploratory_species_accumulation_all")
    return data or []


# ── Comparison ──────────────────────────────────────────────────
@app.get("/api/comparison/city-stats")
async def get_city_stats():
    return _load("comparison_city_stats") or []


@app.get("/api/comparison/yearly-trends")
async def get_yearly_trends():
    return _load("comparison_yearly_trends") or []


@app.get("/api/comparison/quality")
async def get_city_quality(competition_only: Optional[bool] = Query(None)):
    return _load("comparison_quality") or []


@app.get("/api/comparison/contributors")
async def get_city_contributors(competition_only: Optional[bool] = Query(None)):
    return _load("comparison_contributors") or []


@app.get("/api/comparison/captive-wild")
async def get_city_captive_wild(competition_only: Optional[bool] = Query(None)):
    return _load("comparison_captive_wild") or []


@app.get("/api/comparison/spatial")
async def get_city_spatial():
    return _load("comparison_spatial") or []


@app.get("/api/comparison/competition-split")
async def get_competition_split():
    return _load("comparison_competition_split") or []


@app.get("/api/comparison/top-communities")
async def get_top_communities(
    limit: int = Query(15, ge=1, le=50),
    competition_only: Optional[bool] = Query(None),
):
    data = _load("comparison_top_communities") or []
    return data[:limit]


@app.get("/api/comparison/taxon-comparison")
async def get_taxon_comparison():
    return _load("comparison_taxon_comparison") or []


@app.get("/api/comparison/top-species")
async def get_top_species(
    limit: int = Query(15, ge=1, le=50),
    competition_only: Optional[bool] = Query(None),
):
    data = _load("comparison_top_species") or []
    return data[:limit]


@app.get("/api/comparison/city-taxon-breakdown")
async def get_city_taxon_breakdown():
    return _load("comparison_city_taxon_breakdown") or []


@app.get("/api/comparison/city-top-species")
async def get_city_top_species(city: Optional[str] = Query(None)):
    data = _load("comparison_city_top_species") or []
    if city:
        data = [r for r in data if r.get("city") == city]
    return data


# ── Strategy ────────────────────────────────────────────────────
@app.get("/api/strategy/priority-zones")
async def get_priority_zones():
    return _load("strategy_priority_zones") or {"hexes": [], "top": []}


@app.get("/api/strategy/hex-observations/{hex_id}")
async def get_hex_observations(
    hex_id: str,
    type: str = Query(default="both", pattern="^(non_cnc|cnc|both)$"),
):
    path = HEX_OBS_DIR / f"{hex_id}.json"
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)

    if type == "non_cnc":
        data = [d for d in data if not d.get("is_cnc")]
    elif type == "cnc":
        data = [d for d in data if d.get("is_cnc")]

    return data


@app.get("/api/strategy/timing-windows")
async def get_timing_windows():
    return [
        {
            "day_of_week": "Saturday",
            "hour": 9,
            "observation_count": 420,
            "unique_species": 185,
            "efficiency_score": 78.4,
        }
    ]


# ── Hotspots (stub) ────────────────────────────────────────────
@app.get("/api/hotspots/hexbins")
async def get_hexbins():
    return []


@app.get("/api/hotspots/gaps")
async def get_gaps():
    return []


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
