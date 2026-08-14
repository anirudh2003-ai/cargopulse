"""CargoPulse LNG terminal intelligence dashboard."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from dashboard.api_client import (
    get_berths,
    get_calls,
    get_health,
    get_latest_risk,
    get_risk_history,
    get_terminal_daily,
)

st.set_page_config(
    page_title="CargoPulse",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    [data-testid="stMetric"] {
        border-radius: 12px;
    }

    .cp-subtitle {
        color: #7f8c9a;
        font-size: 1rem;
        margin-top: -0.7rem;
        margin-bottom: 1.5rem;
    }

    .cp-section {
        margin-top: 0.4rem;
        margin-bottom: 0.25rem;
    }

    .cp-risk-box {
        padding: 1rem 1.2rem;
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 12px;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }

    .cp-risk-title {
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 0.35rem;
    }

    .cp-risk-text {
        color: #7f8c9a;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=60)
def load_dashboard_data() -> dict:
    """Load dashboard datasets from CargoPulse FastAPI."""

    return {
        "health": get_health(),
        "latest": get_latest_risk(),
        "risk": get_risk_history(limit=30),
        "terminal": get_terminal_daily(limit=30),
        "berths": get_berths(),
        "calls": get_calls(limit=10),
    }


try:
    data = load_dashboard_data()

except requests.RequestException as error:
    st.error(
        "CargoPulse API is unavailable. "
        "Check that the API container is running."
    )

    with st.expander("Technical details"):
        st.exception(error)

    st.stop()


latest = data["latest"]

risk_df = pd.DataFrame(data["risk"])
terminal_df = pd.DataFrame(data["terminal"])
berth_df = pd.DataFrame(data["berths"])
calls_df = pd.DataFrame(data["calls"])


risk_df["metric_date"] = pd.to_datetime(
    risk_df["metric_date"]
)

terminal_df["metric_date"] = pd.to_datetime(
    terminal_df["metric_date"]
)

calls_df["berth_arrival_time"] = pd.to_datetime(
    calls_df["berth_arrival_time"]
)

calls_df["berth_departure_time"] = pd.to_datetime(
    calls_df["berth_departure_time"]
)


risk_df = risk_df.sort_values("metric_date")

terminal_df = terminal_df.sort_values(
    "metric_date"
)


# --------------------------------------------------
# Sidebar
# --------------------------------------------------

with st.sidebar:
    st.title("CargoPulse")

    st.caption(
        "LNG terminal intelligence"
    )

    st.divider()

    st.markdown("### System")

    health = data["health"]

    if (
        health.get("status") == "ok"
        and health.get("database") == "ok"
    ):
        st.success("API & database online")
    else:
        st.warning("System degraded")

    st.markdown(
        "**Terminal:** Sabine Pass LNG"
    )

    st.markdown(
        "**Dataset:** January 2023 AIS"
    )

    st.markdown(
        "**Risk model:** Operational proxy index"
    )

    st.divider()

    st.caption(
        "Risk scores represent an explainable "
        "operational supply-risk index, not a "
        "probability of disruption."
    )


# --------------------------------------------------
# Header
# --------------------------------------------------

st.title("CargoPulse")

st.markdown(
    """
    <div class="cp-subtitle">
        LNG terminal congestion, vessel operations,
        berth performance and explainable supply-risk intelligence
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# Top metrics
# --------------------------------------------------

st.markdown(
    '<h3 class="cp-section">Terminal overview</h3>',
    unsafe_allow_html=True,
)


metric_1, metric_2, metric_3, metric_4, metric_5 = (
    st.columns(5)
)


risk_change = latest.get(
    "risk_change_1d"
)


metric_1.metric(
    label="Operational Risk",
    value=f"{latest['risk_score']:.1f}",
    delta=(
        f"{risk_change:+.1f} pts"
        if risk_change is not None
        else None
    ),
    border=True,
)


metric_2.metric(
    label="Risk Level",
    value=latest["risk_level"].upper(),
    border=True,
)


metric_3.metric(
    label="Terminal Utilisation",
    value=(
        f"{latest['terminal_utilisation_pct']:.1f}%"
    ),
    border=True,
)


metric_4.metric(
    label="Active LNG Calls",
    value=latest["active_calls"],
    border=True,
)


metric_5.metric(
    label="Occupied Berths",
    value=(
        f"{latest['max_occupied_berths']} / 3"
    ),
    border=True,
)


# --------------------------------------------------
# Risk explanation
# --------------------------------------------------

st.markdown(
    f"""
    <div class="cp-risk-box">
        <div class="cp-risk-title">
            {latest['risk_headline']}
        </div>
        <div class="cp-risk-text">
            {latest['risk_explanation']}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


driver_1, driver_2, driver_3 = st.columns(3)


with driver_1:
    st.markdown(
        f"""
        <div class="cp-risk-box">
            <div class="cp-risk-text">
                PRIMARY DRIVER
            </div>
            <div class="cp-risk-title">
                {latest.get('primary_driver') or 'N/A'}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with driver_2:
    st.markdown(
        f"""
        <div class="cp-risk-box">
            <div class="cp-risk-text">
                SECONDARY DRIVER
            </div>
            <div class="cp-risk-title">
                {latest.get('secondary_driver') or 'N/A'}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with driver_3:
    st.markdown(
        f"""
        <div class="cp-risk-box">
            <div class="cp-risk-text">
                SCORE CONFIDENCE
            </div>
            <div class="cp-risk-title">
                {latest['score_confidence'].upper()}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.divider()


# --------------------------------------------------
# Risk intelligence
# --------------------------------------------------

st.subheader("Operational Risk Intelligence")


risk_chart = px.line(
    risk_df,
    x="metric_date",
    y="risk_score",
    markers=True,
    hover_data=[
        "risk_level",
        "score_confidence",
        "terminal_utilisation_pct",
        "active_calls",
    ],
    labels={
        "metric_date": "Date",
        "risk_score": "Operational Risk Index",
        "risk_level": "Risk Level",
        "score_confidence": "Confidence",
        "terminal_utilisation_pct": (
            "Terminal Utilisation (%)"
        ),
        "active_calls": "Active Calls",
    },
)


risk_chart.add_hline(
    y=25,
    line_dash="dot",
    annotation_text="Moderate threshold",
)

risk_chart.add_hline(
    y=50,
    line_dash="dot",
    annotation_text="Elevated threshold",
)

risk_chart.add_hline(
    y=70,
    line_dash="dot",
    annotation_text="High threshold",
)


risk_chart.update_layout(
    yaxis_range=[0, 100],
    height=430,
    margin=dict(
        l=10,
        r=10,
        t=20,
        b=10,
    ),
)


st.plotly_chart(
    risk_chart,
    width="stretch",
)


st.caption(
    "The index combines terminal capacity pressure, "
    "berth saturation, active vessel delays, "
    "delay intensity, trailing utilisation and backlog."
)


st.divider()


# --------------------------------------------------
# Terminal operations
# --------------------------------------------------

st.subheader("Terminal Operations")


left_chart, right_chart = st.columns(2)


with left_chart:
    utilisation_chart = px.area(
        terminal_df,
        x="metric_date",
        y="terminal_utilisation_pct",
        labels={
            "metric_date": "Date",
            "terminal_utilisation_pct": (
                "Utilisation (%)"
            ),
        },
    )

    utilisation_chart.update_layout(
        title="Daily Terminal Utilisation",
        yaxis_range=[0, 100],
        height=360,
        margin=dict(
            l=10,
            r=10,
            t=50,
            b=10,
        ),
    )

    st.plotly_chart(
        utilisation_chart,
        width="stretch",
    )


with right_chart:
    traffic_df = terminal_df[
        [
            "metric_date",
            "arrivals",
            "departures",
        ]
    ].melt(
        id_vars="metric_date",
        var_name="Movement",
        value_name="Vessels",
    )

    traffic_chart = px.bar(
        traffic_df,
        x="metric_date",
        y="Vessels",
        color="Movement",
        barmode="group",
        labels={
            "metric_date": "Date",
        },
    )

    traffic_chart.update_layout(
        title="LNG Vessel Arrivals & Departures",
        height=360,
        margin=dict(
            l=10,
            r=10,
            t=50,
            b=10,
        ),
    )

    st.plotly_chart(
        traffic_chart,
        width="stretch",
    )


st.divider()


# --------------------------------------------------
# Berths
# --------------------------------------------------

st.subheader("Berth Performance")


berth_chart_column, berth_table_column = (
    st.columns([1, 1.4])
)


with berth_chart_column:
    berth_chart = px.bar(
        berth_df,
        x="berth_zone_code",
        y="utilisation_pct",
        text_auto=".1f",
        labels={
            "berth_zone_code": "Berth",
            "utilisation_pct": "Utilisation (%)",
        },
    )

    berth_chart.update_layout(
        title="Berth Utilisation",
        yaxis_range=[0, 100],
        height=370,
        margin=dict(
            l=10,
            r=10,
            t=50,
            b=10,
        ),
    )

    st.plotly_chart(
        berth_chart,
        width="stretch",
    )


with berth_table_column:
    berth_display = berth_df[
        [
            "berth_zone_code",
            "total_calls",
            "scored_calls",
            "median_duration_minutes",
            "mean_estimated_delay_minutes",
            "utilisation_pct",
        ]
    ].copy()

    berth_display[
        "median_duration_hours"
    ] = (
        berth_display[
            "median_duration_minutes"
        ]
        / 60
    )

    berth_display[
        "mean_estimated_delay_hours"
    ] = (
        berth_display[
            "mean_estimated_delay_minutes"
        ]
        / 60
    )

    berth_display = berth_display[
        [
            "berth_zone_code",
            "total_calls",
            "scored_calls",
            "median_duration_hours",
            "mean_estimated_delay_hours",
            "utilisation_pct",
        ]
    ]

    st.dataframe(
        berth_display,
        width="stretch",
        hide_index=True,
        column_config={
            "berth_zone_code": st.column_config.TextColumn(
                "Berth"
            ),
            "total_calls": st.column_config.NumberColumn(
                "Calls",
                format="%d",
            ),
            "scored_calls": st.column_config.NumberColumn(
                "Scored",
                format="%d",
            ),
            "median_duration_hours": (
                st.column_config.NumberColumn(
                    "Median Duration (h)",
                    format="%.1f",
                )
            ),
            "mean_estimated_delay_hours": (
                st.column_config.NumberColumn(
                    "Mean Est. Delay (h)",
                    format="%.1f",
                )
            ),
            "utilisation_pct": (
                st.column_config.NumberColumn(
                    "Utilisation",
                    format="%.1f%%",
                )
            ),
        },
    )


st.caption(
    "Estimated delay represents excess operational "
    "berth duration relative to the applicable "
    "historical baseline; it is not a confirmed "
    "cargo-loading delay."
)


st.divider()


# --------------------------------------------------
# Recent LNG calls
# --------------------------------------------------

st.subheader("Recent LNG Terminal Calls")


calls_display = calls_df[
    [
        "validated_call_id",
        "vessel_name",
        "imo",
        "berth_zone_code",
        "berth_arrival_time",
        "berth_departure_time",
        "berth_duration_minutes",
        "estimated_delay_hours",
        "delay_band",
        "delay_quality",
    ]
].copy()


calls_display[
    "berth_duration_hours"
] = (
    calls_display[
        "berth_duration_minutes"
    ]
    / 60
)


calls_display = calls_display[
    [
        "validated_call_id",
        "vessel_name",
        "imo",
        "berth_zone_code",
        "berth_arrival_time",
        "berth_departure_time",
        "berth_duration_hours",
        "estimated_delay_hours",
        "delay_band",
        "delay_quality",
    ]
]


st.dataframe(
    calls_display,
    width="stretch",
    hide_index=True,
    column_config={
        "validated_call_id": (
            st.column_config.NumberColumn(
                "Call ID",
                format="%d",
            )
        ),
        "vessel_name": st.column_config.TextColumn(
            "Vessel"
        ),
        "imo": st.column_config.NumberColumn(
            "IMO",
            format="%d",
        ),
        "berth_zone_code": (
            st.column_config.TextColumn(
                "Berth"
            )
        ),
        "berth_arrival_time": (
            st.column_config.DatetimeColumn(
                "Berth Arrival",
                format="DD MMM YYYY, HH:mm",
            )
        ),
        "berth_departure_time": (
            st.column_config.DatetimeColumn(
                "Berth Departure",
                format="DD MMM YYYY, HH:mm",
            )
        ),
        "berth_duration_hours": (
            st.column_config.NumberColumn(
                "Duration (h)",
                format="%.1f",
            )
        ),
        "estimated_delay_hours": (
            st.column_config.NumberColumn(
                "Est. Excess Duration (h)",
                format="%.1f",
            )
        ),
        "delay_band": st.column_config.TextColumn(
            "Delay Band"
        ),
        "delay_quality": st.column_config.TextColumn(
            "Data Quality"
        ),
    },
)


st.divider()


# --------------------------------------------------
# Risk components
# --------------------------------------------------

st.subheader("Latest Risk Score Decomposition")


component_names = [
    "Capacity",
    "Saturation",
    "Active Delay",
    "Severe Delay",
    "Delay Intensity",
    "3-Day Utilisation",
    "Backlog",
]


component_values = [
    latest["capacity_points"],
    latest["saturation_points"],
    latest["active_delay_points"],
    latest["active_severe_points"],
    latest["delay_intensity_points"],
    latest["utilisation_3d_points"],
    latest["backlog_points"],
]


component_chart = go.Figure(
    go.Bar(
        x=component_values,
        y=component_names,
        orientation="h",
        text=[
            f"{value:.1f}"
            for value in component_values
        ],
        textposition="auto",
    )
)


component_chart.update_layout(
    xaxis_title="Risk Points",
    yaxis_title="",
    height=400,
    margin=dict(
        l=10,
        r=10,
        t=20,
        b=10,
    ),
)


st.plotly_chart(
    component_chart,
    width="stretch",
)


st.caption(
    "CargoPulse risk is an explainable operational "
    "proxy designed to surface congestion and "
    "terminal pressure. It is not a disruption "
    "probability or trading signal."
)
