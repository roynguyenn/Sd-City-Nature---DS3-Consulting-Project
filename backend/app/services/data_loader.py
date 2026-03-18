"""
Data loading and caching utilities — memory-optimised for 512 MB deploy targets.

Column audit (every column referenced across all routers + services):
  id                  — exploratory, taxonomy, comparison, scoring, exploratory_metrics
  observed_on         — exploratory, taxonomy, exploratory_metrics (retention, temporal)
  time_observed_at    — scoring (_compute_best_time_bucket_per_hex), data_loader (_observed_on_dt)
  created_at          — exploratory_metrics (upload_delay via _created_at_dt)
  user_id             — exploratory, taxonomy, comparison, scoring, exploratory_metrics
  quality_grade       — exploratory, comparison, exploratory_metrics
  captive_cultivated  — comparison (captive-wild), spatial (filter), exploratory_metrics
  latitude / longitude— exploratory (_row_to_observation), sd_neighborhoods, geometry source
  species_name        — exploratory, taxonomy, comparison, exploratory_metrics
  common_name         — exploratory, scoring (generate_recommendations), exploratory_metrics
  taxon_group         — exploratory, taxonomy, comparison, exploratory_metrics
  iconic_taxon_name   — scoring (generate_recommendations), spatial (hex_bin), strategy (hex-obs)
  taxon_id            — spatial (hex_bin unique species), scoring
  city                — exploratory, comparison, exploratory_metrics
  during_competition  — comparison, strategy, spatial, scoring
  time_of_day         — exploratory (_row_to_observation), taxonomy (hourly fallback)
  _observed_on_dt     — exploratory (date filter), exploratory_metrics (hour, retention, upload)
  _created_at_dt      — exploratory_metrics (upload_delay)
  hex7                — strategy (hex-observations endpoint)
  geometry            — everywhere (GeoDataFrame)
"""
import zipfile
import pandas as pd
import geopandas as gpd
from typing import Optional
from pathlib import Path
import h3
import gc


def _utc_to_local_hour(series: pd.Series, tz: str = "America/Los_Angeles") -> pd.Series:
    if series.empty or series.isna().all():
        return series
    try:
        return (
            series.dt.tz_localize("UTC", ambiguous="infer")
            .dt.tz_convert(tz)
            .dt.tz_localize(None)
        )
    except Exception:
        return series


_cached_data: Optional[gpd.GeoDataFrame] = None

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_DATA_DIR = _BACKEND_DIR / "data"
_CSV_PATHS = [
    _PROJECT_ROOT / "cleaned_finalized_dataset.csv.zip",
    _PROJECT_ROOT / "cleaned_finalized_dataset.csv",
    _DATA_DIR / "cleaned_finalized_dataset.csv",
    _DATA_DIR / "cleaned_finalized_dataset.csv.zip",
    _DATA_DIR / "cleaned_finalized_dataset_final.csv.zip",
]

# Every column actually referenced by routers/services (post-rename).
# Columns not in this set are dropped immediately after CSV read to save RAM.
_KEEP_COLUMNS = {
    "id",
    "observed_on",
    "time_observed_at",
    "created_at",
    "user_id",
    "quality_grade",
    "captive_cultivated",
    "latitude",
    "longitude",
    "species_name",
    "common_name",
    "taxon_group",
    "iconic_taxon_name",
    "taxon_id",
    "city",
    "during_competition",
    "time_of_day",
    # derived columns added below — kept here for documentation
    "_observed_on_dt",
    "_created_at_dt",
}


class DataLoader:
    """Handles loading and caching of iNaturalist observation data"""

    @staticmethod
    def load_observations(city: str = "San Diego") -> gpd.GeoDataFrame:
        for path in _CSV_PATHS:
            if not path.exists():
                continue
            try:
                if path.suffix == ".zip":
                    with zipfile.ZipFile(path, "r") as z:
                        csv_members = [
                            n for n in z.namelist()
                            if n.endswith(".csv") and "__MACOSX" not in n and not n.startswith(".")
                        ]
                        if not csv_members:
                            raise ValueError("No .csv file found in zip")
                        with z.open(csv_members[0]) as f:
                            df = pd.read_csv(f)
                else:
                    df = pd.read_csv(path)
            except Exception as e:
                print(f"DataLoader: Could not read {path}: {e}")
                continue

            # ── Column renames ──────────────────────────────────────────
            rename = {}
            if "scientific_name" in df.columns and "species_name" not in df.columns:
                rename["scientific_name"] = "species_name"
            if "iconic_taxon_name" in df.columns and "taxon_group" not in df.columns:
                rename["iconic_taxon_name"] = "taxon_group"
            if "community" in df.columns and "city" not in df.columns:
                rename["community"] = "city"
            df = df.rename(columns=rename)

            # Ensure iconic_taxon_name always exists (scoring.py needs it)
            if "iconic_taxon_name" not in df.columns and "taxon_group" in df.columns:
                df["iconic_taxon_name"] = df["taxon_group"]

            # ── Fallbacks for required columns ──────────────────────────
            fallbacks = [
                ("species_name", "scientific_name"),
                ("common_name", "common_name"),
                ("taxon_group", "iconic_taxon_name"),
                ("latitude", "latitude"),
                ("longitude", "longitude"),
                ("observed_on", "observed_on"),
                ("user_id", "user_id"),
                ("quality_grade", "quality_grade"),
                ("city", "community"),
            ]
            for api_col, alt_col in fallbacks:
                if api_col not in df.columns:
                    df[api_col] = df[alt_col] if alt_col in df.columns else ""

            if "id" not in df.columns:
                df["id"] = range(len(df))
            if "time_of_day" not in df.columns:
                df["time_of_day"] = "unknown"
            if "captive_cultivated" not in df.columns:
                df["captive_cultivated"] = pd.NA
            if "during_competition" not in df.columns:
                df["during_competition"] = 1

            # ── Datetime processing ─────────────────────────────────────
            obs_date = pd.to_datetime(df["observed_on"], errors="coerce").dt.normalize()
            df["observed_on"] = obs_date.astype("str")

            if "time_observed_at" in df.columns:
                time_obs = pd.to_datetime(df["time_observed_at"], errors="coerce")
                df["_observed_on_dt"] = (
                    obs_date
                    + pd.to_timedelta(time_obs.dt.hour.fillna(0), unit="h")
                    + pd.to_timedelta(time_obs.dt.minute.fillna(0), unit="m")
                    + pd.to_timedelta(time_obs.dt.second.fillna(0), unit="s")
                )
            else:
                df["_observed_on_dt"] = obs_date

            df["_observed_on_dt"] = _utc_to_local_hour(df["_observed_on_dt"], "America/Los_Angeles")

            if "created_at" in df.columns:
                df["_created_at_dt"] = pd.to_datetime(df["created_at"], errors="coerce")
                df["_created_at_dt"] = _utc_to_local_hour(df["_created_at_dt"], "America/Los_Angeles")

            df["user_id"] = df["user_id"].astype(str)

            # ── Drop rows missing coordinates ───────────────────────────
            df = df.dropna(subset=["latitude", "longitude"])

            # ════════════════════════════════════════════════════════════
            # MEMORY OPTIMISATION 1: drop every column not in _KEEP_COLUMNS
            # ════════════════════════════════════════════════════════════
            keep = [c for c in df.columns if c in _KEEP_COLUMNS]
            df = df[keep].copy()
            gc.collect()

            # ════════════════════════════════════════════════════════════
            # MEMORY OPTIMISATION 2: downcast numerics
            # ════════════════════════════════════════════════════════════
            for col in df.select_dtypes(include=["int64"]).columns:
                df[col] = pd.to_numeric(df[col], downcast="integer")
            for col in df.select_dtypes(include=["float64"]).columns:
                df[col] = pd.to_numeric(df[col], downcast="float")

            # ════════════════════════════════════════════════════════════
            # MEMORY OPTIMISATION 3: low-cardinality strings → category
            # ════════════════════════════════════════════════════════════
            for col in ["quality_grade", "taxon_group", "iconic_taxon_name", "city", "time_of_day"]:
                if col in df.columns:
                    df[col] = df[col].astype("category")

            gc.collect()

            # ── Build GeoDataFrame ──────────────────────────────────────
            gdf = gpd.GeoDataFrame(
                df,
                geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
                crs="EPSG:4326",
            )
            # NOTE: we keep latitude & longitude because exploratory.py _row_to_observation
            # reads them directly (row["latitude"], row["longitude"]).

            print(f"DataLoader: Loaded {len(gdf):,} observations from {path}")

            # ── H3 hex index (vectorised list-comp, lower peak RAM than .apply) ──
            gdf["hex7"] = [
                h3.latlng_to_cell(g.y, g.x, 7) if g is not None else None
                for g in gdf.geometry
            ]

            gc.collect()
            return gdf

        print("DataLoader: No cleaned_finalized_dataset found, using dummy data")
        return DataLoader._dummy_gdf(city)

    # ── cache helpers ───────────────────────────────────────────────────
    @staticmethod
    def get_cached_data() -> gpd.GeoDataFrame:
        global _cached_data
        if _cached_data is None:
            try:
                _cached_data = DataLoader.load_observations()
            except Exception as e:
                print(f"DataLoader: load_observations failed ({e}), using dummy data")
                _cached_data = DataLoader._dummy_gdf()
            if _cached_data is None or len(_cached_data) == 0:
                print("DataLoader: cache empty, using dummy data")
                _cached_data = DataLoader._dummy_gdf()
        return _cached_data

    @staticmethod
    def _dummy_gdf(city: str = "San Diego") -> gpd.GeoDataFrame:
        obs_dt = pd.to_datetime(["2026-04-26"] * 100)
        data = {
            "id": list(range(1, 101)),
            "species_name": ["Quercus agrifolia"] * 100,
            "common_name": ["Coast Live Oak"] * 100,
            "taxon_group": ["Plants"] * 50 + ["Birds"] * 50,
            "latitude": [32.7 + i * 0.01 for i in range(100)],
            "longitude": [-117.1 - i * 0.01 for i in range(100)],
            "observed_on": obs_dt.astype("str").tolist(),
            "_observed_on_dt": obs_dt,
            "time_of_day": ["morning"] * 100,
            "user_id": ["user_1"] * 100,
            "quality_grade": ["research"] * 100,
            "city": [city] * 100,
            "during_competition": [1] * 100,
        }
        df = pd.DataFrame(data)
        return gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
            crs="EPSG:4326",
        )

    @staticmethod
    def get_cached_data_filtered(competition_only: Optional[bool] = None) -> gpd.GeoDataFrame:
        gdf = DataLoader.get_cached_data()
        if competition_only is None:
            return gdf
        if "during_competition" not in gdf.columns:
            return gdf
        value = 1 if competition_only else 0
        return gdf[gdf["during_competition"] == value].copy()

    @staticmethod
    def load_data():
        global _cached_data
        _cached_data = DataLoader.load_observations()
        print(f"Loaded {len(_cached_data)} observations into cache")