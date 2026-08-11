from __future__ import annotations

import argparse
import math
import os
from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from shapely import affinity
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA
from sqlalchemy import create_engine, text
from shapely import affinity, concave_hull
from shapely.geometry import (
    GeometryCollection,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)
from shapely.ops import unary_union
from shapely.validation import make_valid

PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]

DATABASE_CRS = "EPSG:4326"
METRIC_CRS = "EPSG:32615"

DBSCAN_EPS_METRES = 50
DBSCAN_MIN_SAMPLES = 20

# Extra tolerance surrounding the observed stationary AIS cloud.
BERTH_MARGIN_METRES = 15

# Prevent a very tight AIS cloud from producing an unrealistically
# tiny analytical berth geofence.
MIN_BERTH_LENGTH_METRES = 80
MIN_BERTH_WIDTH_METRES = 40

TERMINAL_LONGITUDE = -93.8740512
TERMINAL_LATITUDE = 29.7540967

# Support-zone configuration

ANCHORAGE_SEARCH_RADIUS_METRES = 15_000
ANCHORAGE_LOOKBACK_HOURS = 48

ANCHORAGE_DBSCAN_EPS_METRES = 200
ANCHORAGE_DBSCAN_MIN_SAMPLES = 20
ANCHORAGE_MIN_VESSELS = 2
ANCHORAGE_BUFFER_METRES = 80

BERTH_EXCLUSION_BUFFER_METRES = 120

# Tighter terminal-local manoeuvring area
MANOEUVRE_MAX_DISTANCE_METRES = 1_500
MANOEUVRE_BUFFER_METRES = 50

# Only model the nearby operational channel
CHANNEL_MAX_DISTANCE_METRES = 3_000
CHANNEL_BUFFER_METRES = 60
CHANNEL_MIN_COMPONENT_AREA_M2 = 5_000

# Wider terminal area, but not a huge 5 km circle
APPROACH_MAX_DISTANCE_METRES = 2_500
APPROACH_BUFFER_METRES = 175


def load_stationary_positions(engine):
    query = """
        SELECT
            position_id,
            mmsi,
            imo,
            vessel_name,
            position_timestamp,
            speed_over_ground,
            heading_degrees,
            geom
        FROM public.geofence_reference_positions
        WHERE speed_over_ground < 0.5
    """

    return gpd.read_postgis(
        query,
        engine,
        geom_col="geom",
    )


def load_berth_templates(engine):
    query = """
        SELECT
            zone_code,
            geom AS geometry
        FROM public.terminal_zones_before_berth_autofit
        WHERE zone_type = 'berth'
        ORDER BY zone_code
    """

    templates = gpd.read_postgis(
        query,
        engine,
        geom_col="geometry",
    )

    if templates.crs is None:
        templates = templates.set_crs(DATABASE_CRS)

    if len(templates) != 3:
        raise RuntimeError(
            f"Expected 3 berth templates, found {len(templates)}."
        )

    # Check the geometries before reprojection.
    for _, row in templates.iterrows():
        geometry = row.geometry

        if geometry is None or geometry.is_empty:
            raise RuntimeError(
                f"{row['zone_code']} has an empty geometry."
            )

        if geometry.geom_type not in (
            "Polygon",
            "MultiPolygon",
        ):
            raise RuntimeError(
                f"{row['zone_code']} has unexpected geometry "
                f"type: {geometry.geom_type}"
            )

        if not geometry.is_valid:
            raise RuntimeError(
                f"{row['zone_code']} has invalid geometry."
            )

    return templates.to_crs(METRIC_CRS)


def cluster_stationary_positions(positions):
    metric = positions.to_crs(METRIC_CRS).copy()

    coordinates = np.column_stack(
        [
            metric.geometry.x.to_numpy(),
            metric.geometry.y.to_numpy(),
        ]
    )

    model = DBSCAN(
        eps=DBSCAN_EPS_METRES,
        min_samples=DBSCAN_MIN_SAMPLES,
    )

    metric["cluster_id"] = model.fit_predict(
        coordinates
    )

    return metric

def calculate_heading_axis(headings):
    """
    Calculate dominant vessel orientation.

    Heading is directional (0-360 degrees), but a berth axis is
    undirected: 45 degrees and 225 degrees describe the same axis.

    Doubling the angles before averaging handles this correctly.
    """

    headings = np.asarray(headings, dtype=float)

    headings = headings[
        np.isfinite(headings)
        & (headings >= 0)
        & (headings < 360)
    ]

    if len(headings) == 0:
        return None, None

    radians = np.deg2rad(headings)

    mean_cos = np.mean(np.cos(2 * radians))
    mean_sin = np.mean(np.sin(2 * radians))

    axis_radians = 0.5 * np.arctan2(
        mean_sin,
        mean_cos,
    )

    heading_axis = (
        np.rad2deg(axis_radians) % 180
    )

    concentration = np.sqrt(
        mean_cos ** 2
        + mean_sin ** 2
    )

    return (
        float(heading_axis),
        float(concentration),
    )


def analyse_cluster(group):
    """
    Estimate:
      - centre
      - principal direction
      - robust length
      - robust width

    using PCA on the stationary AIS cloud.
    """

    coordinates = np.column_stack(
        [
            group.geometry.x.to_numpy(),
            group.geometry.y.to_numpy(),
        ]
    )

    centre = coordinates.mean(axis=0)

    centred = coordinates - centre

    pca = PCA(n_components=2)
    projected = pca.fit_transform(centred)

    principal_axis = pca.components_[0]

    angle_degrees = math.degrees(
        math.atan2(
            principal_axis[1],
            principal_axis[0],
        )
    )

    # Ignore the most extreme 2% at each edge so a handful of
    # noisy AIS positions do not determine the polygon dimensions.
    long_low, long_high = np.quantile(
        projected[:, 0],
        [0.02, 0.98],
    )

    wide_low, wide_high = np.quantile(
        projected[:, 1],
        [0.02, 0.98],
    )

    observed_length = long_high - long_low
    observed_width = wide_high - wide_low

    target_length = max(
        observed_length + 2 * BERTH_MARGIN_METRES,
        MIN_BERTH_LENGTH_METRES,
    )

    target_width = max(
        observed_width + 2 * BERTH_MARGIN_METRES,
        MIN_BERTH_WIDTH_METRES,
    )
    heading_axis, heading_concentration = (
    calculate_heading_axis(
        group["heading_degrees"]
    )
)

    heading_rotation = (
    90.0 - heading_axis
    )

    # A polygon axis is equivalent every 180 degrees.
    # Keep the angle in a convenient -90 to +90 range.
    heading_rotation = (
        (heading_rotation + 90.0) % 180.0
    ) - 90.0

    return {
        "centre_x": float(centre[0]),
        "centre_y": float(centre[1]),
        "angle_degrees": float(angle_degrees),
        "heading_axis_degrees": heading_axis,
        "heading_rotation_degrees": float(heading_rotation),
        "heading_concentration": heading_concentration,
        "observed_length": float(observed_length),
        "observed_width": float(observed_width),
        "target_length": float(target_length),
        "target_width": float(target_width),
        "point_count": len(group),
        "vessel_count": group["mmsi"].nunique(),
    }


def rectangle_properties(geometry):
    """
    Find the orientation, length and width of a template polygon
    using its minimum rotated rectangle.
    """

    rectangle = geometry.minimum_rotated_rectangle

    coordinates = list(
        rectangle.exterior.coords
    )[:4]

    edges = []

    for index in range(4):
        start = coordinates[index]
        end = coordinates[(index + 1) % 4]

        dx = end[0] - start[0]
        dy = end[1] - start[1]

        length = math.hypot(dx, dy)

        angle = math.degrees(
            math.atan2(dy, dx)
        )

        edges.append(
            (length, angle)
        )

    longest = max(
        edges,
        key=lambda item: item[0],
    )

    shortest = min(
        edges,
        key=lambda item: item[0],
    )

    return {
        "angle": longest[1],
        "length": longest[0],
        "width": shortest[0],
    }


def fit_template_to_cluster(
    template_geometry,
    cluster,
):
    properties = rectangle_properties(
        template_geometry
    )

    centroid = template_geometry.centroid

    geometry = affinity.translate(
        template_geometry,
        xoff=-centroid.x,
        yoff=-centroid.y,
    )

    # Remove the template's original rotation.
    geometry = affinity.rotate(
        geometry,
        -properties["angle"],
        origin=(0, 0),
        use_radians=False,
    )

    scale_x = (
        cluster["target_length"]
        / properties["length"]
    )

    scale_y = (
        cluster["target_width"]
        / properties["width"]
    )

    geometry = affinity.scale(
        geometry,
        xfact=scale_x,
        yfact=scale_y,
        origin=(0, 0),
    )

    # Rotate it to match the AIS cloud.
    geometry = affinity.rotate(
    geometry,
    cluster["heading_rotation_degrees"],
    origin=(0, 0),
    use_radians=False,
)

    # Move it onto the stationary AIS cluster.
    geometry = affinity.translate(
        geometry,
        xoff=cluster["centre_x"],
        yoff=cluster["centre_y"],
    )

    return geometry


def build_cluster_profiles(clustered):
    valid = clustered[
        clustered["cluster_id"] != -1
    ].copy()

    profiles = []

    for cluster_id, group in valid.groupby(
        "cluster_id"
    ):
        profile = analyse_cluster(group)

        profile["cluster_id"] = int(
            cluster_id
        )

        profiles.append(profile)

    if len(profiles) != 3:
        raise RuntimeError(
            "Expected exactly 3 stationary clusters at "
            f"eps={DBSCAN_EPS_METRES} m, "
            f"found {len(profiles)}."
        )

    # Arrange west -> east.
    profiles.sort(
        key=lambda profile: profile["centre_x"]
    )

    return profiles


def pair_templates_with_clusters(
    templates,
    profiles,
):
    """
    Preserve the spatial left-to-right order of the original
    three berth templates.

    This is provisional analytical numbering and should be
    checked visually against the terminal map.
    """

    templates = templates.copy()

    templates["template_x"] = (
        templates.geometry.centroid.x
    )

    templates = templates.sort_values(
        "template_x"
    ).reset_index(drop=True)

    fitted_records = []

    for index, (_, template) in enumerate(
        templates.iterrows()
    ):
        profile = profiles[index]

        geometry = fit_template_to_cluster(
            template.geometry,
            profile,
        )

        fitted_records.append(
            {
                "zone_code": template["zone_code"],
                "cluster_id": profile["cluster_id"],
                "point_count": profile["point_count"],
                "vessel_count": profile["vessel_count"],
                "angle_degrees": profile["angle_degrees"],
                "target_length_metres":
                    profile["target_length"],
                "target_width_metres":
                    profile["target_width"],
                "heading_axis_degrees":
                profile["heading_axis_degrees"],
                "heading_rotation_degrees": profile["heading_rotation_degrees"],
                "heading_concentration":
                profile["heading_concentration"],
                "geometry": geometry,
            }
        )

    return gpd.GeoDataFrame(
        fitted_records,
        geometry="geometry",
        crs=METRIC_CRS,
    )


def print_results(fitted):
    display = fitted.to_crs(
        DATABASE_CRS
    ).copy()

    display["longitude"] = (
        display.geometry.centroid.x
    )

    display["latitude"] = (
        display.geometry.centroid.y
    )

    print()
    print("=" * 110)
    print("AUTOMATIC BERTH FIT")
    print("=" * 110)

    for _, row in display.iterrows():
        print()
        print(
            f"{row['zone_code']} "
            f"← cluster {row['cluster_id']}"
        )

        print(
            f"  vessels:   "
            f"{row['vessel_count']}"
        )

        print(
            f"  points:    "
            f"{row['point_count']:,}"
        )

        print(
            f"  centre:    "
            f"{row['longitude']:.6f}, "
            f"{row['latitude']:.6f}"
        )

        print(
            f"  length:    "
            f"{row['target_length_metres']:.1f} m"
        )

        print(
            f"  width:     "
            f"{row['target_width_metres']:.1f} m"
        )

        print(
            f"  rotation:  "
            f"{row['angle_degrees']:.1f}°"
        )

        print(
            f"  AIS heading axis: "
            f"{row['heading_axis_degrees']:.1f}°"
        )

        print(
            f"  heading strength: "
            f"{row['heading_concentration']:.3f}"
        )

        print(
            f"  valid:     "
            f"{row.geometry.is_valid}"
        )

        print(
    f"  fitted rotation: "
    f"{row['heading_rotation_degrees']:.1f}°"
    )


def export_candidates(fitted):
    output_path = (
        PROJECT_ROOT
        / "data"
        / "reference"
        / "auto_fitted_berths.geojson"
    )

    output = fitted.to_crs(
        DATABASE_CRS
    )

    output.to_file(
        output_path,
        driver="GeoJSON",
    )

    print()
    print(
        f"Candidate berths saved to:"
        f"\n{output_path}"
    )


def apply_to_database(
    engine,
    fitted,
):
    wgs84 = fitted.to_crs(
        DATABASE_CRS
    )

    update_sql = text(
        """
        UPDATE public.terminal_zones
        SET
            geom = ST_Multi(
                ST_SetSRID(
                    ST_GeomFromText(:geometry_wkt),
                    4326
                )
            ),
            geometry_confidence = 'medium',
            updated_at = NOW()
        WHERE zone_code = :zone_code
        """
    )

    with engine.begin() as connection:
        for _, row in wgs84.iterrows():
            connection.execute(
                update_sql,
                {
                    "zone_code":
                        row["zone_code"],
                    "geometry_wkt":
                        row.geometry.wkt,
                },
            )

    print()
    print(
        "The three berth polygons were "
        "updated in terminal_zones."
    )

def validate_berth_overlaps(fitted):
    print()
    print("=" * 70)
    print("BERTH OVERLAP CHECK")
    print("=" * 70)

    has_overlap = False

    for i in range(len(fitted)):
        for j in range(i + 1, len(fitted)):
            first = fitted.iloc[i]
            second = fitted.iloc[j]

            intersection = first.geometry.intersection(
                second.geometry
            )

            overlap_area = intersection.area

            print(
                f"{first['zone_code']} vs "
                f"{second['zone_code']}: "
                f"{overlap_area:.2f} m²"
            )

            if overlap_area > 1.0:
                has_overlap = True

    if has_overlap:
        raise RuntimeError(
            "Berth polygons overlap. "
            "Do not apply these candidates."
        )

    print("No material berth overlap detected.")

def force_multipolygon(
    geometry,
    min_part_area=0.0,
):
    """
    Repair polygon geometry and always return a MultiPolygon.
    """

    geometry = make_valid(geometry)

    if isinstance(geometry, Polygon):
        parts = [geometry]

    elif isinstance(geometry, MultiPolygon):
        parts = list(geometry.geoms)

    elif isinstance(geometry, GeometryCollection):
        parts = [
            item
            for item in geometry.geoms
            if isinstance(item, Polygon)
        ]

    else:
        raise ValueError(
            f"Unsupported polygon geometry: "
            f"{geometry.geom_type}"
        )

    parts = [
        polygon
        for polygon in parts
        if polygon.area >= min_part_area
    ]

    if not parts:
        raise ValueError(
            "No usable polygon parts remained."
        )

    return MultiPolygon(parts)


def terminal_point_metric():
    """
    Return the Sabine Pass terminal point in UTM metres.
    """

    point = gpd.GeoSeries(
        [
            Point(
                TERMINAL_LONGITUDE,
                TERMINAL_LATITUDE,
            )
        ],
        crs=DATABASE_CRS,
    ).to_crs(METRIC_CRS)

    return point.iloc[0]


def load_support_reference_positions(engine):
    """
    Positions around confirmed LNG calls.

    This is suitable for manoeuvring/channel analysis.
    """

    query = """
        SELECT
            position_id,
            mmsi,
            imo,
            vessel_name,
            position_timestamp,
            speed_over_ground,
            heading_degrees,
            geom
        FROM public.geofence_reference_positions
    """

    positions = gpd.read_postgis(
        query,
        engine,
        geom_col="geom",
    )

    return positions.to_crs(METRIC_CRS)


def load_anchorage_search_positions(engine):
    """
    Load AIS positions around each confirmed LNG call.

    We deliberately do NOT use calls.arrival_time as the berth-arrival
    time. Instead, Python will determine the first actual entry into
    one of our fitted berth polygons.
    """

    query = f"""
        SELECT
            calls.validated_call_id,

            positions.mmsi,
            calls.imo,
            calls.vessel_name,

            positions.recorded_at
                AS position_timestamp,

            positions.speed_knots
                AS speed_over_ground,

            positions.heading_degrees,

            positions.location::geometry(Point, 4326)
                AS geom

        FROM public.ais_positions AS positions

        JOIN public.confirmed_lng_port_calls AS calls
            ON calls.mmsi = positions.mmsi

        WHERE
            positions.recorded_at
                >= calls.arrival_time
                   - INTERVAL '{ANCHORAGE_LOOKBACK_HOURS} hours'

            AND positions.recorded_at
                <= calls.departure_time
                   + INTERVAL '2 hours'

            AND ST_DWithin(
                positions.location,

                ST_SetSRID(
                    ST_MakePoint(
                        {TERMINAL_LONGITUDE},
                        {TERMINAL_LATITUDE}
                    ),
                    4326
                )::geography,

                {ANCHORAGE_SEARCH_RADIUS_METRES}
            )
    """

    positions = gpd.read_postgis(
        query,
        engine,
        geom_col="geom",
    )

    return positions.to_crs(
        METRIC_CRS
    )


def concave_polygon_from_points(
    points,
    ratio,
    buffer_metres,
):
    """
    Build an irregular evidence-based polygon around AIS points.
    """

    if len(points) < 3:
        raise RuntimeError(
            "Not enough AIS points to create a polygon."
        )

    point_cloud = MultiPoint(
        list(points.geometry)
    )

    if len(points) >= 4:
        geometry = concave_hull(
            point_cloud,
            ratio=ratio,
            allow_holes=False,
        )
    else:
        geometry = point_cloud.convex_hull

    geometry = geometry.buffer(
        buffer_metres
    )

    return force_multipolygon(
        geometry
    )


def generate_anchorage_zone(
    search_positions,
    fitted_berths,
):
    """
    Find repeated stationary waiting locations occurring BEFORE a
    vessel's first detected entry into one of the fitted berth zones.

    Returns None when this dataset does not contain sufficient evidence
    for a distinct anchorage.
    """

    berth_union = unary_union(
        list(fitted_berths.geometry)
    )

    berth_exclusion = berth_union.buffer(
        BERTH_EXCLUSION_BUFFER_METRES
    )

    candidate_groups = []

    calls_with_berth_entry = 0

    for validated_call_id, group in (
        search_positions.groupby(
            "validated_call_id"
        )
    ):
        group = group.sort_values(
            "position_timestamp"
        ).copy()

        # Find positions that physically enter one of our fitted
        # berth polygons.
        inside_berth = group.geometry.within(
            berth_union
        )

        berth_hits = group[
            inside_berth
        ]

        if berth_hits.empty:
            continue

        calls_with_berth_entry += 1

        first_berth_time = (
            berth_hits[
                "position_timestamp"
            ].min()
        )

        # Anchorage candidate:
        #   - before actual berth entry
        #   - effectively stationary
        #   - outside berth + safety buffer
        waiting = group[
            (
                group["position_timestamp"]
                < first_berth_time
            )
            & (
                group["speed_over_ground"]
                < 0.5
            )
        ].copy()

        waiting = waiting[
            ~waiting.geometry.within(
                berth_exclusion
            )
        ].copy()

        # Require at least several observations from this call,
        # otherwise a single noisy stopped point is not useful.
        if len(waiting) >= 3:
            candidate_groups.append(
                waiting
            )

    print()
    print(
        f"Calls with detected berth entry: "
        f"{calls_with_berth_entry}"
    )

    if not candidate_groups:
        print(
            "Anchorage: no qualifying pre-berth "
            "stationary sequences found."
        )

        return None

    candidates = pd.concat(
        candidate_groups,
        ignore_index=True,
    )

    candidates = gpd.GeoDataFrame(
        candidates,
        geometry="geom",
        crs=METRIC_CRS,
    )

    # GeoPandas expects its active geometry column to be set.
    candidates = candidates.set_geometry(
        "geom"
    )

    print(
        f"Pre-berth stationary candidate points: "
        f"{len(candidates):,}"
    )

    print(
        f"Candidate vessels: "
        f"{candidates['mmsi'].nunique()}"
    )

    if len(candidates) < (
        ANCHORAGE_DBSCAN_MIN_SAMPLES
    ):
        print(
            "Anchorage: insufficient evidence "
            "for a separate anchorage zone."
        )

        return None

    coordinates = np.column_stack(
        [
            candidates.geometry.x.to_numpy(),
            candidates.geometry.y.to_numpy(),
        ]
    )

    model = DBSCAN(
        eps=ANCHORAGE_DBSCAN_EPS_METRES,
        min_samples=ANCHORAGE_DBSCAN_MIN_SAMPLES,
    )

    candidates["cluster_id"] = (
        model.fit_predict(
            coordinates
        )
    )

    clustered = candidates[
        candidates["cluster_id"] != -1
    ].copy()

    if clustered.empty:
        print(
            "Anchorage: DBSCAN found no stable "
            "stationary waiting cluster."
        )

        return None

    cluster_summary = (
        clustered.groupby(
            "cluster_id"
        )
        .agg(
            point_count=(
                "mmsi",
                "size",
            ),
            vessel_count=(
                "mmsi",
                "nunique",
            ),
            call_count=(
                "validated_call_id",
                "nunique",
            ),
        )
        .reset_index()
    )

    cluster_summary = cluster_summary[
        cluster_summary["vessel_count"]
        >= ANCHORAGE_MIN_VESSELS
    ].copy()

    if cluster_summary.empty:
        print(
            "Anchorage: stationary clusters exist, "
            "but none were repeatedly used by enough "
            "different vessels."
        )

        return None

    cluster_summary = (
        cluster_summary.sort_values(
            [
                "vessel_count",
                "call_count",
                "point_count",
            ],
            ascending=False,
        )
    )

    print()
    print("=" * 80)
    print("ANCHORAGE CLUSTERS")
    print("=" * 80)

    print(
        cluster_summary.to_string(
            index=False
        )
    )

    best_cluster_id = int(
        cluster_summary.iloc[0][
            "cluster_id"
        ]
    )

    anchor_points = clustered[
        clustered["cluster_id"]
        == best_cluster_id
    ].copy()

    geometry = (
        concave_polygon_from_points(
            anchor_points,
            ratio=0.20,
            buffer_metres=(
                ANCHORAGE_BUFFER_METRES
            ),
        )
    )

    overlap_area = (
        geometry
        .intersection(
            berth_union
        )
        .area
    )

    if overlap_area > 1.0:
        raise RuntimeError(
            "Generated anchorage overlaps "
            "a berth by "
            f"{overlap_area:.2f} m²."
        )

    best_summary = (
        cluster_summary.iloc[0]
    )

    return {
        "zone_code":
            "SPL_ANCHORAGE_1",

        "zone_type":
            "anchorage",

        "method":
            "preberth_stationary_dbscan",

        "point_count":
            int(
                best_summary[
                    "point_count"
                ]
            ),

        "vessel_count":
            int(
                best_summary[
                    "vessel_count"
                ]
            ),

        "geometry":
            geometry,
    }


def generate_manoeuvre_zone(
    reference_positions,
    fitted_berths,
):
    """
    Generate the slow-speed manoeuvring area immediately around
    the terminal.
    """

    target = terminal_point_metric()

    berth_union = unary_union(
        list(fitted_berths.geometry)
    )

    berth_exclusion = berth_union.buffer(
        BERTH_EXCLUSION_BUFFER_METRES
    )

    points = reference_positions[
        (
            reference_positions[
                "speed_over_ground"
            ] >= 0.5
        )
        & (
            reference_positions[
                "speed_over_ground"
            ] < 2
        )
    ].copy()

    distances = points.geometry.distance(
        target
    )

    points = points[
        distances
        <= MANOEUVRE_MAX_DISTANCE_METRES
    ].copy()

    points = points[
        ~points.geometry.within(
            berth_exclusion
        )
    ].copy()

    if len(points) < 20:
        raise RuntimeError(
            "Not enough slow-speed AIS positions "
            "to generate the manoeuvring zone."
        )

    geometry = concave_polygon_from_points(
        points,
        ratio=0.20,
        buffer_metres=MANOEUVRE_BUFFER_METRES,
    )

    return {
        "zone_code": "SPL_MANOEUVRE",
        "zone_type": "manoeuvring_basin",
        "method": "slow_speed_concave_hull",
        "point_count": len(points),
        "vessel_count": (
            points["mmsi"].nunique()
        ),
        "geometry": geometry,
    }


def generate_channel_zone(
    reference_positions,
):
    """
    Generate an AIS-derived shipping corridor.

    Buffering a MultiPoint creates a corridor wherever moving AIS
    observations are sufficiently close together.
    """

    target = terminal_point_metric()

    points = reference_positions[
        reference_positions[
            "speed_over_ground"
        ] >= 2
    ].copy()

    distances = points.geometry.distance(
        target
    )

    points = points[
        distances
        <= CHANNEL_MAX_DISTANCE_METRES
    ].copy()

    if len(points) < 20:
        raise RuntimeError(
            "Not enough moving AIS positions "
            "to generate a channel."
        )

    cloud = MultiPoint(
        list(points.geometry)
    )

    geometry = cloud.buffer(
        CHANNEL_BUFFER_METRES
    )

    # Smooth small gaps without radically changing the track.
    geometry = (
        geometry
        .buffer(40)
        .buffer(-40)
    )

    geometry = force_multipolygon(
        geometry,
        min_part_area=(
            CHANNEL_MIN_COMPONENT_AREA_M2
        ),
    )

    return {
        "zone_code": "SPL_CHANNEL",
        "zone_type": "shipping_channel",
        "method": "moving_ais_buffer_corridor",
        "point_count": len(points),
        "vessel_count": (
            points["mmsi"].nunique()
        ),
        "geometry": geometry,
    }


def generate_approach_zone(
    reference_positions,
    fitted_berths,
):
    """
    Generate an AIS-derived terminal approach envelope.

    The zone follows actual vessel positions rather than using
    a fixed circular buffer around the terminal.
    """

    berth_union = unary_union(
        list(fitted_berths.geometry)
    )

    berth_centre = berth_union.centroid

    distances = reference_positions.geometry.distance(
        berth_centre
    )

    points = reference_positions[
        distances <= APPROACH_MAX_DISTANCE_METRES
    ].copy()

    if len(points) < 20:
        raise RuntimeError(
            "Not enough AIS positions to generate "
            "the approach zone."
        )

    geometry = concave_polygon_from_points(
        points,
        ratio=0.15,
        buffer_metres=APPROACH_BUFFER_METRES,
    )

    # Always make sure the berth complex itself is included.
    geometry = unary_union(
        [
            geometry,
            berth_union.buffer(100),
        ]
    )

    geometry = force_multipolygon(
        geometry
    )

    return {
        "zone_code": "SPL_APPROACH",
        "zone_type": "approach",
        "method": "ais_approach_concave_hull",
        "point_count": len(points),
        "vessel_count": points["mmsi"].nunique(),
        "geometry": geometry,
    }

def generate_support_zones(
    engine,
    fitted_berths,
):
    """
    Generate anchorage, manoeuvring, channel and approach zones.

    Anchorage is optional: if there is not enough evidence for one,
    the other support zones are still generated.
    """

    reference_positions = (
        load_support_reference_positions(
            engine
        )
    )

    anchorage_search_positions = (
        load_anchorage_search_positions(
            engine
        )
    )

    print()
    print(
        f"Reference positions for support zones: "
        f"{len(reference_positions):,}"
    )

    print(
        f"Anchorage search positions: "
        f"{len(anchorage_search_positions):,}"
    )

    records = []

    # ---------------------------------------------------------
    # Anchorage
    # ---------------------------------------------------------

    anchorage = generate_anchorage_zone(
        anchorage_search_positions,
        fitted_berths,
    )

    if anchorage is not None:
        records.append(
            anchorage
        )

    # ---------------------------------------------------------
    # Manoeuvring basin
    # Always generate independently of anchorage.
    # ---------------------------------------------------------

    records.append(
        generate_manoeuvre_zone(
            reference_positions,
            fitted_berths,
        )
    )

    # ---------------------------------------------------------
    # Shipping channel
    # ---------------------------------------------------------

    records.append(
        generate_channel_zone(
            reference_positions,
        )
    )

    # ---------------------------------------------------------
    # Approach zone
    # ---------------------------------------------------------

    records.append(
    generate_approach_zone(
        reference_positions,
        fitted_berths,
    )
)

    generated_codes = {
        record["zone_code"]
        for record in records
    }

    if "SPL_ANCHORAGE_1" not in generated_codes:
        print()
        print(
            "NOTE: No evidence-based anchorage "
            "polygon was generated."
        )

    print()
    print(
        "Support zones generated: "
        + ", ".join(
            sorted(generated_codes)
        )
    )

    return gpd.GeoDataFrame(
        records,
        geometry="geometry",
        crs=METRIC_CRS,
    )


def validate_support_zones(
    support_zones,
):
    print()
    print("=" * 80)
    print("SUPPORT ZONE VALIDATION")
    print("=" * 80)

    for _, row in support_zones.iterrows():
        print(
            f"{row['zone_code']:<20} "
            f"valid={str(row.geometry.is_valid):<5} "
            f"area={row.geometry.area:,.1f} m² "
            f"points={row['point_count']:,} "
            f"vessels={row['vessel_count']}"
        )

        if not row.geometry.is_valid:
            raise RuntimeError(
                f"{row['zone_code']} is invalid."
            )


def export_all_terminal_zone_candidates(
    fitted_berths,
    support_zones,
):
    """
    Write all seven candidate zones to one QGIS-friendly GeoJSON.
    """

    records = []

    for _, row in fitted_berths.iterrows():
        records.append(
            {
                "zone_code":
                    row["zone_code"],

                "zone_type":
                    "berth",

                "method":
                    "stationary_dbscan_ais_heading",

                "geometry":
                    row.geometry,
            }
        )

    for _, row in support_zones.iterrows():
        records.append(
            {
                "zone_code":
                    row["zone_code"],

                "zone_type":
                    row["zone_type"],

                "method":
                    row["method"],

                "geometry":
                    row.geometry,
            }
        )

    combined = gpd.GeoDataFrame(
        records,
        geometry="geometry",
        crs=METRIC_CRS,
    ).to_crs(DATABASE_CRS)

    output_path = (
        PROJECT_ROOT
        / "data"
        / "reference"
        / "auto_fitted_terminal_zones.geojson"
    )

    combined.to_file(
        output_path,
        driver="GeoJSON",
    )

    print()
    print(
        "All 7 candidate zones saved to:"
    )
    print(output_path)


def apply_support_zones_to_database(
    engine,
    support_zones,
):
    """
    Replace the geometry of the existing four support-zone rows.
    """

    required = {
    "SPL_MANOEUVRE",
    "SPL_CHANNEL",
    "SPL_APPROACH",
}

    actual = set(
        support_zones["zone_code"]
    )

    if "SPL_ANCHORAGE_1" not in actual:
        print(
            "No anchorage candidate was generated. "
            "SPL_ANCHORAGE_1 will NOT be updated."
        )

    missing = required - actual

    if missing:
        raise RuntimeError(
            "Refusing to apply support zones. "
            f"Missing: {sorted(missing)}"
        )

    wgs84 = support_zones.to_crs(
        DATABASE_CRS
    )

    update_sql = text(
        """
        UPDATE public.terminal_zones
        SET
            geom = ST_Multi(
                ST_SetSRID(
                    ST_GeomFromText(:geometry_wkt),
                    4326
                )
            ),

            source_name =
                'AIS-derived',

            source_reference =
                'January 2023 NOAA AIS / CargoPulse automatic geofence fitting',

            geometry_confidence =
                'medium',

            updated_at =
                NOW()

        WHERE zone_code = :zone_code
        """
    )

    with engine.begin() as connection:
        for _, row in wgs84.iterrows():
            connection.execute(
                update_sql,
                {
                    "zone_code":
                        row["zone_code"],

                    "geometry_wkt":
                        row.geometry.wkt,
                },
            )

    print()
    print(
        "Anchorage, manoeuvring, channel and "
        "approach geometries updated."
    )
def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Write fitted berth geometries into "
            "public.terminal_zones."
        ),
    )
    parser.add_argument(
    "--apply-support",
    action="store_true",
    help=(
        "Write anchorage, manoeuvring, channel "
        "and approach geometries into "
        "public.terminal_zones."
    ),
)

    args = parser.parse_args()

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
    )

    positions = load_stationary_positions(
        engine
    )

    print(
        f"Stationary AIS positions loaded: "
        f"{len(positions):,}"
    )

    clustered = cluster_stationary_positions(
        positions
    )

    profiles = build_cluster_profiles(
        clustered
    )

    templates = load_berth_templates(
        engine
    )

    fitted = pair_templates_with_clusters(
        templates,
        profiles,
    )

    print_results(
        fitted
    )

    validate_berth_overlaps(
    fitted
)
    support_zones = generate_support_zones(
    engine,
    fitted,
)

    validate_support_zones(
        support_zones
    )

    export_all_terminal_zone_candidates(
        fitted,
        support_zones,
    )

    export_candidates(
        fitted
    )

    if args.apply:
        apply_to_database(
            engine,
            fitted,
        )

    if args.apply_support:
        apply_support_zones_to_database(
            engine,
            support_zones,
        )

    if (
        not args.apply
        and not args.apply_support
    ):
        print()
        print(
            "DRY RUN ONLY — database was not changed."
        )

        print()
        print(
            "After visually checking the seven zones:"
        )

        print(
            "Berths:"
        )
        print(
            "python -m processing.auto_fit_berths --apply"
        )

        print()
        print(
            "Support zones:"
        )
        print(
            "python -m processing.auto_fit_berths --apply-support"
        )
    else:
        print()
        print(
            "DRY RUN ONLY — database was not changed."
        )
        print(
            "After checking the output, run:"
        )
        print(
            "python -m processing.auto_fit_berths --apply"
        )


if __name__ == "__main__":
    main()
