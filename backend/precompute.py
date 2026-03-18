"""
Pre-compute all API responses and save as static JSON files.
Run this locally: python precompute.py
Then commit the generated JSON files in backend/static_api/
"""
import json
import sys
import os
import asyncio

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from app.services.data_loader import DataLoader
from app.services.taxonomy import summarize_by_taxon, get_temporal_trends, get_user_contribution_buckets
from app.services.exploratory_metrics import get_dashboard, get_species_accumulation_curve

OUT_DIR = os.path.join(os.path.dirname(__file__), "static_api")
os.makedirs(OUT_DIR, exist_ok=True)


def save(name, data):
    path = os.path.join(OUT_DIR, f"{name}.json")
    with open(path, "w") as f:
        json.dump(data, f)
    size_mb = os.path.getsize(path) / 1024 / 1024
    print(f"  Saved {name}.json ({size_mb:.1f} MB)")


def precompute_exploratory():
    """Pre-compute all exploratory endpoints for each filter."""
    print("\n=== Exploratory ===")

    for label, comp_only in [("all", None), ("competition", True), ("non_competition", False)]:
        print(f"\nFilter: {label}")
        gdf = DataLoader.get_cached_data_filtered(comp_only)

        # Dashboard
        dashboard = get_dashboard(
            gdf,
            taxonomy_summary_fn=summarize_by_taxon,
            temporal_trends_fn=get_temporal_trends,
        )
        save(f"exploratory_dashboard_{label}", dashboard)

        # Species accumulation
        accum = get_species_accumulation_curve(gdf)
        save(f"exploratory_species_accumulation_{label}", accum)

        # Observations (limit to 250k, convert to dicts)
        obs_gdf = gdf.head(250000)
        per_user = obs_gdf.groupby("user_id").size().to_dict() if "user_id" in obs_gdf.columns else {}
        observations = []
        for _, row in obs_gdf.iterrows():
            obs_on = row.get("observed_on", "")
            if hasattr(obs_on, "strftime"):
                obs_on = obs_on.strftime("%Y-%m-%d") if obs_on else ""

            uid = str(row.get("user_id", ""))
            n = per_user.get(uid, 0)
            if n <= 1:
                tier = "1"
            elif n <= 5:
                tier = "2-5"
            elif n <= 20:
                tier = "6-20"
            else:
                tier = "21+"

            observations.append({
                "id": int(row.get("id", 0)),
                "species_name": str(row.get("species_name", "")),
                "common_name": str(row.get("common_name", "")),
                "taxon_group": str(row.get("taxon_group", "")),
                "latitude": float(row.geometry.y) if row.geometry else 0,
                "longitude": float(row.geometry.x) if row.geometry else 0,
                "observed_on": str(obs_on),
                "time_of_day": str(row.get("time_of_day", "unknown")),
                "user_id": uid,
                "quality_grade": str(row.get("quality_grade", "")),
                "city": str(row.get("city", "")),
                "contributor_tier": tier,
            })
        save(f"exploratory_observations_{label}", observations)


def precompute_comparison():
    """Pre-compute comparison endpoints."""
    import pandas as pd
    from pathlib import Path

    print("\n=== Comparison ===")
    DATA_DIR = Path(__file__).resolve().parent / "data"

    # City stats & yearly trends (from CSV)
    stats_path = DATA_DIR / "cnc_city_stats.csv"
    if stats_path.exists():
        df = pd.read_csv(stats_path)
        save("comparison_yearly_trends", df.to_dict("records"))
        max_year = df["year"].max()
        save("comparison_city_stats", df[df["year"] == max_year].to_dict("records"))

    # City taxon breakdown
    taxon_path = DATA_DIR / "cnc_city_taxon.csv"
    if taxon_path.exists():
        save("comparison_city_taxon_breakdown", pd.read_csv(taxon_path).to_dict("records"))

    # City top species
    species_path = DATA_DIR / "cnc_city_top_species.csv"
    if species_path.exists():
        save("comparison_city_top_species", pd.read_csv(species_path).to_dict("records"))

    # Data-driven endpoints from cached data
    gdf = DataLoader.get_cached_data()
    if "city" not in gdf.columns and "community" in gdf.columns:
        gdf = gdf.rename(columns={"community": "city"})

    # Competition split
    if "during_competition" in gdf.columns:
        results = []
        for val, window_label in [(1, "competition"), (0, "non_competition")]:
            sub = gdf[gdf["during_competition"] == val]
            n = len(sub)
            sp = sub["species_name"].nunique() if "species_name" in sub.columns else 0
            users = sub["user_id"].nunique() if "user_id" in sub.columns else 0
            rg = 0.0
            if "quality_grade" in sub.columns and n > 0:
                rg = round(100 * (sub["quality_grade"].astype(str).str.lower() == "research").sum() / n, 1)
            spo = round(sp / max(n, 1), 4)
            results.append({
                "window": window_label, "observations": int(n), "unique_species": int(sp),
                "participants": int(users), "research_pct": rg, "species_per_observation": spo,
            })
        save("comparison_competition_split", results)

    # Quality by city
    if "quality_grade" in gdf.columns and "city" in gdf.columns:
        city_col = gdf["city"].fillna("Unknown").astype(str)
        q = gdf["quality_grade"].fillna("unknown").astype(str).str.lower()
        temp = gdf.copy()
        temp["_city"] = city_col
        temp["_research"] = (q == "research").astype(int)
        temp["_needs_id"] = (q == "needs_id").astype(int)
        temp["_casual"] = (q == "casual").astype(int)
        agg = temp.groupby("_city").agg(
            total=("id", "count"),
            research_count=("_research", "sum"),
            needs_id_count=("_needs_id", "sum"),
            casual_count=("_casual", "sum"),
        ).reset_index()
        agg.columns = ["city", "total", "research_count", "needs_id_count", "casual_count"]
        agg["research_pct"] = (100 * agg["research_count"] / agg["total"].replace(0, 1)).round(1)
        for c in ["total", "research_count", "needs_id_count", "casual_count"]:
            agg[c] = agg[c].astype(int)
        save("comparison_quality", agg.to_dict("records"))

    # Contributors by city
    if "user_id" in gdf.columns and "city" in gdf.columns:
        temp = gdf.copy()
        temp["_city"] = temp["city"].fillna("Unknown").astype(str)
        obs_per_user = temp.groupby(["_city", "user_id"]).size().reset_index(name="obs_count")
        agg = obs_per_user.groupby("_city").agg(
            user_count=("user_id", "count"), total_observations=("obs_count", "sum"),
        ).reset_index()
        agg.columns = ["city", "user_count", "total_observations"]
        agg["mean_obs_per_user"] = (agg["total_observations"] / agg["user_count"].replace(0, 1)).round(1)
        save("comparison_contributors", agg.to_dict("records"))

    # Taxon comparison
    if "taxon_group" in gdf.columns and "during_competition" in gdf.columns:
        temp = gdf.copy()
        temp["_taxon"] = temp["taxon_group"].fillna("Unknown").astype(str)
        comp = temp[temp["during_competition"] == 1].groupby("_taxon").size()
        non_comp = temp[temp["during_competition"] == 0].groupby("_taxon").size()
        all_taxons = sorted(set(comp.index) | set(non_comp.index))
        results = []
        for t in all_taxons:
            cc = int(comp.get(t, 0))
            nc = int(non_comp.get(t, 0))
            results.append({"taxon_group": t, "competition_count": cc, "non_competition_count": nc, "total": cc + nc})
        results.sort(key=lambda x: x["total"], reverse=True)
        save("comparison_taxon_comparison", results)

    # Top species
    if "species_name" in gdf.columns:
        temp = gdf.copy()
        temp["_sp"] = temp["species_name"].fillna("").astype(str).str.strip()
        temp = temp[temp["_sp"] != ""]
        counts = temp.groupby("_sp").agg(
            count=("_sp", "count"),
            common_name=("common_name", "first") if "common_name" in temp.columns else ("_sp", "first"),
            taxon_group=("taxon_group", "first") if "taxon_group" in temp.columns else ("_sp", "first"),
        ).reset_index().rename(columns={"_sp": "scientific_name"})
        counts["common_name"] = counts["common_name"].fillna("").astype(str)
        counts["taxon_group"] = counts["taxon_group"].fillna("Unknown").astype(str)
        counts = counts.sort_values("count", ascending=False).head(15)
        save("comparison_top_species", counts.to_dict("records"))

    # Top communities
    if "city" in gdf.columns:
        temp = gdf.copy()
        temp["_comm"] = temp["city"].fillna("Unknown").astype(str)
        agg = temp.groupby("_comm").agg(
            observations=("_comm", "count"),
            unique_species=("species_name", "nunique"),
            participants=("user_id", "nunique"),
        ).reset_index().rename(columns={"_comm": "community"})
        agg["species_per_observation"] = (agg["unique_species"] / agg["observations"].replace(0, 1)).round(4)
        agg = agg.sort_values("observations", ascending=False).head(15)
        save("comparison_top_communities", agg.to_dict("records"))

    # Captive wild by city
    if "captive_cultivated" in gdf.columns and "city" in gdf.columns:
        temp = gdf.copy()
        temp["_city"] = temp["city"].fillna("Unknown").astype(str)
        captive = temp["captive_cultivated"].fillna(False)
        if captive.dtype == object:
            captive = captive.astype(str).str.lower().isin(("true", "1", "yes"))
        temp["_captive"] = captive.astype(int)
        agg = temp.groupby("_city").agg(total=("id", "count"), captive_count=("_captive", "sum")).reset_index()
        agg.columns = ["city", "total", "captive_count"]
        agg["wild_count"] = agg["total"] - agg["captive_count"]
        agg["wild_pct"] = (100 * agg["wild_count"] / agg["total"]).round(1)
        agg["captive_pct"] = (100 * agg["captive_count"] / agg["total"]).round(1)
        for c in ["captive_count", "wild_count"]:
            agg[c] = agg[c].astype(int)
        save("comparison_captive_wild", agg[["city", "wild_count", "captive_count", "wild_pct", "captive_pct"]].to_dict("records"))


def precompute_strategy():
    """Pre-compute strategy priority zones."""
    import geopandas as gpd
    from app.services.spatial import hex_bin_observations, build_fill_boundary
    from app.services.scoring import calculate_priority_score, generate_recommendations
    from pathlib import Path

    print("\n=== Strategy ===")
    BACKEND_DIR = Path(__file__).resolve().parent
    sd_boundary = gpd.read_file(BACKEND_DIR / "data" / "San_Diego_County_Boundary_(GIS)_20260216.geojson", engine="pyogrio")
    sd_coastal = gpd.read_file(BACKEND_DIR / "data" / "coastal_zones.geojson", engine="pyogrio")
    sd_greenery = gpd.read_file(BACKEND_DIR / "data" / "greenery.geojson", engine="pyogrio", on_invalid="ignore")

    gdf = DataLoader.get_cached_data()

    fill_boundary = sd_boundary.to_crs("EPSG:26911").copy()
    fill_boundary["geometry"] = fill_boundary.buffer(10000)
    fill_boundary = fill_boundary.to_crs(sd_boundary.crs)

    hex_stats = hex_bin_observations(
        gdf=gdf, county_boundary=fill_boundary, resolution=7,
        min_non_cnc=30, use_existing_cnc_flag=True,
    )
    hex_scored = calculate_priority_score(hex_stats)
    hexs_finalized = generate_recommendations(hex_scored, gdf, top_n=len(hex_scored), parks_gdf=sd_greenery)

    save("strategy_priority_zones", {"hexes": hexs_finalized, "top": hexs_finalized})

    # Pre-compute hex observations for each hex
    print("  Pre-computing hex observations...")
    hex_obs_dir = os.path.join(OUT_DIR, "hex_obs")
    os.makedirs(hex_obs_dir, exist_ok=True)

    import numpy as np
    for hex_entry in hexs_finalized:
        hex_id = hex_entry["zone_id"]
        hex_obs = gdf[gdf["hex7"] == hex_id].copy()

        def safe_str(val):
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return "Unknown"
            return str(val)

        obs_list = [
            {
                "lat": float(row.geometry.y),
                "lng": float(row.geometry.x),
                "common_name": safe_str(row.get("common_name")),
                "iconic_taxon": safe_str(row.get("iconic_taxon_name")),
                "is_cnc": bool(row.get("during_competition", 0)),
            }
            for _, row in hex_obs.iterrows()
            if row.geometry is not None
        ]
        # Save per-hex file
        path = os.path.join(hex_obs_dir, f"{hex_id}.json")
        with open(path, "w") as f:
            json.dump(obs_list, f)

    print(f"  Saved {len(hexs_finalized)} hex observation files")


if __name__ == "__main__":
    print("Loading data...")
    DataLoader.load_data()

    precompute_exploratory()
    precompute_comparison()
    precompute_strategy()

    print(f"\nDone! All files saved to {OUT_DIR}/")
    print("Commit the static_api/ folder and push to deploy.")
