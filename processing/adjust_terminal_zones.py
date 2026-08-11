from __future__ import annotations

import json
import os
from pathlib import Path

import geopandas as gpd
from dotenv import load_dotenv
from shapely import affinity
from shapely.geometry import MultiPolygon, Polygon
from shapely.validation import make_valid
from sqlalchemy import create_engine, text


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONFIG_PATH = (
    PROJECT_ROOT
    / "data"
    / "reference"
    / "sabine_pass_zone_adjustments.json"
)

load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]

# Sabine Pass lies in UTM Zone 15N.
METRIC_CRS = "EPSG:32615"
DATABASE_CRS = "EPSG:4326"


def force_multipolygon(geometry):
    """
    Make a geometry valid and return Polygon/MultiPolygon geometry.
    """

    if not geometry.is_valid:
        geometry = make_valid(geometry)

    if isinstance(geometry, Polygon):
        return MultiPolygon([geometry])

    if isinstance(geometry, MultiPolygon):
        return geometry

    # make_valid can occasionally return a GeometryCollection.
    polygons = [
        item
        for item in geometry.geoms
        if isinstance(item, Polygon)
    ]

    if not polygons:
        raise ValueError(
            "Geometry could not be converted to a polygon."
        )

    return MultiPolygon(polygons)


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_template_zones(engine):
    query = """
        SELECT
            zone_id,
            zone_code,
            geom AS geometry
        FROM public.terminal_zones
        ORDER BY zone_priority, zone_code
    """

    zones = gpd.read_postgis(
        query,
        engine,
        geom_col="geometry",
    )

    if zones.crs is None:
        zones = zones.set_crs(DATABASE_CRS)

    if len(zones) != 7:
        raise RuntimeError(
            f"Expected 7 terminal zones, found {len(zones)}."
        )

    return zones


def normalize_template(zones, target):
    """
    Treat the user's current drawing as an abstract template.

    Its current longitude/latitude does NOT matter.

    We preserve the relative positions and shapes, but map the whole
    drawing into a real metric coordinate system around Sabine Pass.
    """

    min_x, min_y, max_x, max_y = zones.total_bounds

    width = max_x - min_x

    if width <= 0:
        raise RuntimeError("Template width is invalid.")

    centre_x = (min_x + max_x) / 2
    centre_y = (min_y + max_y) / 2

    # Obtain Sabine Pass centre in UTM metres.
    target_point = gpd.GeoSeries.from_xy(
        [target["longitude"]],
        [target["latitude"]],
        crs=DATABASE_CRS,
    ).to_crs(METRIC_CRS)

    target_x = target_point.iloc[0].x
    target_y = target_point.iloc[0].y

    target_width = target["overall_width_metres"]

    scale_factor = target_width / width

    transformed = zones.copy()

    new_geometries = []

    for geometry in zones.geometry:
        # Move arbitrary template centre to coordinate origin.
        geometry = affinity.translate(
            geometry,
            xoff=-centre_x,
            yoff=-centre_y,
        )

        # Convert template coordinate units into metres.
        geometry = affinity.scale(
            geometry,
            xfact=scale_factor,
            yfact=scale_factor,
            origin=(0, 0),
        )

        # Move it to the real Sabine Pass UTM coordinate.
        geometry = affinity.translate(
            geometry,
            xoff=target_x,
            yoff=target_y,
        )

        new_geometries.append(geometry)

    transformed.geometry = new_geometries

    # The transformed coordinates are now UTM metres.
    transformed = transformed.set_crs(
        METRIC_CRS,
        allow_override=True,
    )

    group_rotation = target.get(
        "rotation_degrees",
        0,
    )

    if group_rotation:
        group_centre = (
            target_x,
            target_y,
        )

        transformed.geometry = transformed.geometry.apply(
            lambda geometry: affinity.rotate(
                geometry,
                group_rotation,
                origin=group_centre,
                use_radians=False,
            )
        )

    return transformed


def apply_zone_adjustments(zones, config):
    """
    Apply individual translation, scaling and rotation.
    """

    zone_config = config["zones"]

    result = zones.copy()

    adjusted_geometries = []

    for _, row in result.iterrows():
        zone_code = row["zone_code"]
        geometry = row.geometry

        settings = zone_config.get(
            zone_code,
            {},
        )

        scale_x = settings.get("scale_x", 1.0)
        scale_y = settings.get("scale_y", 1.0)

        rotation = settings.get(
            "rotation_degrees",
            0,
        )

        move_x = settings.get(
            "move_x_metres",
            0,
        )

        move_y = settings.get(
            "move_y_metres",
            0,
        )

        # Resize around this zone's own centre.
        geometry = affinity.scale(
            geometry,
            xfact=scale_x,
            yfact=scale_y,
            origin="centroid",
        )

        # Rotate around this zone's own centre.
        geometry = affinity.rotate(
            geometry,
            rotation,
            origin="centroid",
            use_radians=False,
        )

        # Move in metres.
        geometry = affinity.translate(
            geometry,
            xoff=move_x,
            yoff=move_y,
        )

        geometry = force_multipolygon(
            geometry
        )

        adjusted_geometries.append(geometry)

    result.geometry = adjusted_geometries

    return result


def validate_zones(zones):
    print()
    print("=" * 72)
    print("GEOMETRY VALIDATION")
    print("=" * 72)

    failed = False

    for _, row in zones.iterrows():
        geometry = row.geometry

        valid = geometry.is_valid
        area = geometry.area

        print(
            f"{row['zone_code']:<20} "
            f"valid={str(valid):<5} "
            f"area={area:,.2f} m²"
        )

        if not valid:
            failed = True

    if failed:
        raise RuntimeError(
            "At least one generated geometry is invalid."
        )


def update_database(engine, zones):
    """
    Convert back to WGS84 and update the existing PostGIS rows.
    """

    wgs84 = zones.to_crs(DATABASE_CRS)

    sql = text(
        """
        UPDATE public.terminal_zones
        SET
            geom = ST_Multi(
                ST_SetSRID(
                    ST_GeomFromText(:wkt),
                    4326
                )
            ),
            updated_at = NOW()
        WHERE zone_code = :zone_code
        """
    )

    with engine.begin() as connection:
        for _, row in wgs84.iterrows():
            connection.execute(
                sql,
                {
                    "zone_code": row["zone_code"],
                    "wkt": row.geometry.wkt,
                },
            )


def main():
    config = load_config()

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
    )

    zones = load_template_zones(engine)

    print(f"Template zones loaded: {len(zones)}")

    adjusted = normalize_template(
        zones,
        config["target"],
    )

    adjusted = apply_zone_adjustments(
        adjusted,
        config,
    )

    validate_zones(adjusted)

    update_database(
        engine,
        adjusted,
    )

    print()
    print("Terminal zones updated successfully.")


if __name__ == "__main__":
    main()
