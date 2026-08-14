from __future__ import annotations

import os
from pathlib import Path

import geopandas as gpd
import pandas as pd
from dotenv import load_dotenv
from sklearn.cluster import DBSCAN
from sqlalchemy import create_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]

DATABASE_CRS = "EPSG:4326"
METRIC_CRS = "EPSG:32615"


def load_stationary_positions(engine):
    query = """
        SELECT
            position_id,
            mmsi,
            imo,
            vessel_name,
            position_timestamp,
            speed_over_ground,
            geom
        FROM public.geofence_reference_positions
        WHERE speed_over_ground < 0.5
    """

    gdf = gpd.read_postgis(
        query,
        engine,
        geom_col="geom",
    )

    return gdf


def cluster_positions(gdf, eps_metres):
    metric = gdf.to_crs(METRIC_CRS)

    coordinates = pd.DataFrame(
        {
            "x": metric.geometry.x,
            "y": metric.geometry.y,
        }
    ).to_numpy()

    model = DBSCAN(
        eps=eps_metres,
        min_samples=20,
    )

    metric["cluster_id"] = model.fit_predict(
        coordinates
    )

    return metric


def summarise_clusters(clustered):
    valid = clustered[
        clustered["cluster_id"] != -1
    ].copy()

    summary = (
        valid.groupby("cluster_id")
        .agg(
            point_count=("position_id", "count"),
            vessel_count=("mmsi", "nunique"),
            imo_count=("imo", "nunique"),
            min_time=("position_timestamp", "min"),
            max_time=("position_timestamp", "max"),
        )
        .reset_index()
    )

    centroid_records = []

    for cluster_id, group in valid.groupby("cluster_id"):
        centroid = group.geometry.union_all().centroid

        centroid_records.append(
            {
                "cluster_id": cluster_id,
                "geometry": centroid,
            }
        )

    centroid_gdf = gpd.GeoDataFrame(
        centroid_records,
        geometry="geometry",
        crs=METRIC_CRS,
    ).to_crs(DATABASE_CRS)

    centroid_gdf["longitude"] = (
        centroid_gdf.geometry.x
    )

    centroid_gdf["latitude"] = (
        centroid_gdf.geometry.y
    )

    summary = summary.merge(
        centroid_gdf[
            [
                "cluster_id",
                "longitude",
                "latitude",
            ]
        ],
        on="cluster_id",
        how="left",
    )

    summary = summary.sort_values(
        [
            "vessel_count",
            "point_count",
        ],
        ascending=False,
    )

    return summary


def main():
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
    )

    positions = load_stationary_positions(engine)

    print(
        f"Stationary positions loaded: "
        f"{len(positions):,}"
    )

    chosen_eps = 50

    clustered = cluster_positions(
        positions,
        chosen_eps,
    )

    noise_count = (
        clustered["cluster_id"] == -1
    ).sum()

    cluster_count = (
        clustered.loc[
            clustered["cluster_id"] != -1,
            "cluster_id",
        ]
        .nunique()
    )

    print()
    print("=" * 100)
    print(
        f"STATIONARY CLUSTERS — EPS {chosen_eps} m"
    )
    print("=" * 100)

    print(
        f"Clusters found: {cluster_count}"
    )
    print(
        f"Noise points: {noise_count:,}"
    )

    summary = summarise_clusters(
        clustered
    )

    print()
    print(
        summary.to_string(
            index=False
        )
    )

    output_path = (
        PROJECT_ROOT
        / "data"
        / "reference"
        / "stationary_cluster_summary.csv"
    )

    summary.to_csv(
        output_path,
        index=False,
    )

    print()
    print(
        f"Saved cluster summary to: "
        f"{output_path}"
    )

if __name__ == "__main__":
    main()
