# streamlit_storm_dashboard.py

import streamlit as st
import pandas as pd
import altair as alt
import os
from vega_datasets import data as vega_data
from vega_datasets import data
import us
import json
import glob

st.set_page_config(layout="wide")
alt.data_transformers.disable_max_rows()

st.title("🌀 Tornado Tracker: Interactive Insights Across U.S. States")

st.markdown("""
## Explore the Power and Patterns of Nature's Most Violent Storms

Welcome to the Tornado Tracker dashboard, your interactive portal into the fascinating and destructive world of tornadoes across the United States. This tool transforms complex meteorological data into intuitive visualizations, allowing you to:

- **Discover regional tornado hotspots** across the American landscape
- **Analyze seasonal patterns** that reveal when different states face the highest risk
- **Compare tornado characteristics** from mild EF0 events to devastating EF5 monsters
- **Identify trends** that may reflect the changing climate's impact on severe weather

Powered by the latest NOAA data from 2024, this dashboard combines data science with meteorological insights to create a comprehensive view of tornado activity.

### How to Use This Dashboard
👉 **Click on any state** in the map to filter all charts to that location  
👉 **Brush across months** in the timeline to focus on specific time periods  
👉 **Hover over elements** to reveal detailed information about individual data points
""")

st.markdown("---")


@st.cache_data
def load_2024_data():
    file_path = os.path.join(os.path.dirname(__file__), 'data/StormEvents_details-ftp_v1.0_d2024_c20250401_chunk_1.csv')
    if os.path.exists(file_path):
        df = pd.read_csv(file_path, encoding='latin1')
        df = df[~df['TOR_F_SCALE'].isna()].copy()

        # Convert F-scale to numeric intensity
        df['intensity'] = df['TOR_F_SCALE'].str.extract('(\d+)').astype(float)

        # Parse date with correct format
        df['date'] = pd.to_datetime(df['BEGIN_DATE_TIME'], format='%d-%b-%y %H:%M:%S', errors='coerce')
        df['month'] = df['date'].dt.month

        # Create mapping from state names to FIPS codes
        state_name_to_fips = {state.name.upper(): int(state.fips) for state in us.states.STATES}
        df['STATE_FIPS'] = df['STATE'].map(state_name_to_fips)

        # Show warning in sidebar if any states couldn't be mapped
        unmapped_states = df[df['STATE_FIPS'].isna()]['STATE'].unique()
        if len(unmapped_states) > 0:
            st.sidebar.warning(f"⚠️ Unmapped states found: {list(unmapped_states)}")

        return df
    else:
        st.error("❌ Data file not found.")
        return pd.DataFrame()

@st.cache_data
def load_all_years_data():
    dfs = []
    for year in range(2000, 2002):
        pattern = f"data/StormEvents_details-ftp_v1.0_d{year}_c20250401_chunk_*.csv"
        files = sorted(glob.glob(pattern))

        for file in files:
            try:
                df_year = pd.read_csv(file, encoding='latin1', on_bad_lines='skip')
                df_year = df_year[~df_year['TOR_F_SCALE'].isna()].copy()
                dfs.append(df_year)
                print(f"Loaded {file} with {len(df_year)} rows.")
            except Exception as e:
                print(f"❌ Error reading {file}: {e}")

    if not dfs:
        print("⚠️ No files loaded.")
        return pd.DataFrame(), pd.DataFrame()


# ========== SIDEBAR ==========
st.sidebar.title("Tornado Dashboard Settings")
view_mode = st.sidebar.radio("Select View", ['2024 State Analysis', 'Multi-Year Heatmap'])

# ========== VIEW 1: STATE ANALYSIS 2024 ==========
if view_mode == '2024 State Analysis':
    df = load_2024_data()
    all_states = sorted(df["STATE"].dropna().unique().tolist())
    if "NEVADA" not in all_states:
        all_states.append("NEVADA")

    st.title("🌀 Tornado Tracker: Interactive Insights Across U.S. States")
    # --- Map Section ---
    st.subheader("1️⃣ Geographic Distribution")
    selected_state_map = st.selectbox("Select State for Map Insight:", ["All States"] + all_states)

    # Map Data Prep
    state_stats = df.groupby(["STATE", "STATE_FIPS"]).agg(
        tornado_count=('TOR_F_SCALE', 'count'),
        avg_intensity=('intensity', 'mean')
    ).reset_index()
    state_stats['id'] = state_stats['STATE_FIPS'].astype(int)
    if "NEVADA" not in state_stats["STATE"].values:
        state_stats = pd.concat([
            state_stats,
            pd.DataFrame([{"STATE": "NEVADA", "STATE_FIPS": "32", "tornado_count": 0, "avg_intensity": 0, "id": 32}])
        ])

    states_geo = alt.topo_feature(data.us_10m.url, 'states')
    map_chart = alt.Chart(states_geo).mark_geoshape().encode(
        color=alt.Color('tornado_count:Q', scale=alt.Scale(scheme='reds'), title='Tornado Count'),
        tooltip=["STATE:N", "tornado_count:Q"]
    ).transform_lookup(
        lookup='id',
        from_=alt.LookupData(state_stats, key='id', fields=['STATE', 'tornado_count', 'avg_intensity'])
    ).project(
        type='albersUsa'
    ).properties(width=800, height=500)

    st.altair_chart(map_chart, use_container_width=True)

    # Filtered Data
    def filter_state(df, selected_state):
        return df if selected_state == "All States" else df[df["STATE"] == selected_state]

    # --- Monthly Trend Chart ---
    st.subheader("2️⃣ Monthly Tornado Trends")
    selected_state_trend = st.selectbox("Select State for Monthly Trends:", ["All States"] + all_states)

    df_trend = filter_state(df, selected_state_trend)
    brush = alt.selection_interval(encodings=["x"])

    intensity = alt.Chart(df_trend).mark_line(point=True).encode(
        x="month:O",
        y="average(intensity):Q",
        color=alt.value("orange"),
        opacity=alt.condition(brush, alt.value(1), alt.value(0.3))
    ).add_params(brush)

    count = alt.Chart(df_trend).mark_bar(opacity=0.5).encode(
        x="month:O",
        y="count():Q",
        color=alt.value("steelblue")
    )

    st.altair_chart((intensity + count).resolve_scale(y="independent").properties(width=800, height=250), use_container_width=True)

    # --- Scatter Chart ---
    st.subheader("3️⃣ Tornado Size: Length vs. Width")
    selected_state_scatter = st.selectbox("Highlight State in Scatter Plot:", ["All States"] + all_states)

    scatter_base = alt.Chart(df).mark_circle(size=60).encode(
        x="TOR_LENGTH:Q",
        y="TOR_WIDTH:Q",
        color=alt.condition(
            alt.datum.STATE == selected_state_scatter,
            alt.value("orange"),
            alt.value("lightgray")
        ),
        tooltip=["STATE", "TOR_LENGTH", "TOR_WIDTH", "TOR_F_SCALE"]
    ).properties(width=400, height=300)

    st.altair_chart(scatter_base, use_container_width=True)

    # --- Scale Bar Chart ---
    st.subheader("4️⃣ Tornado Frequency by Fujita Scale")
    selected_state_scale = st.selectbox("Select State for Fujita Scale Bar Chart:", ["All States"] + all_states)

    df_scale = filter_state(df, selected_state_scale)

    scale_chart = alt.Chart(df_scale).mark_bar().encode(
        x="TOR_F_SCALE:N",
        y="count():Q",
        color="TOR_F_SCALE:N"
    ).properties(width=400, height=300)

    st.altair_chart(scale_chart, use_container_width=True)

    # Footer
    st.markdown("---")
    st.caption("Data: NOAA Storm Events 2024 | Interactive Dashboard built with Streamlit & Altair")

# ========== VIEW 2: MULTI-YEAR HEATMAP ==========
else:
    df = load_all_years_data()

    # Time parsing
    df['BEGIN_TIME'] = df['BEGIN_TIME'].astype(str).str.zfill(4)
    df['HOUR'] = df['BEGIN_TIME'].str[:2].astype(int)
    df['YEAR'] = df['BEGIN_YEARMONTH'].astype(str).str[:4].astype(int)
    df['MONTH'] = df['BEGIN_YEARMONTH'].astype(str).str[4:].astype(int)
    df['MONTH_NAME'] = pd.to_datetime(df['MONTH'], format='%m').dt.strftime('%b')
    df['MONTH_NAME'] = pd.Categorical(df['MONTH_NAME'],
                                      categories=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
                                      ordered=True)

    # Clean up damage fields
    def parse_damage(val):
        try:
            val = str(val).strip().upper()
            if val.endswith("K"):
                return float(val[:-1]) * 1e3
            elif val.endswith("M"):
                return float(val[:-1]) * 1e6
            return float(val)
        except:
            return 0.0

    df["DAMAGE_PROPERTY_PARSED"] = df["DAMAGE_PROPERTY"].apply(parse_damage)
    df["DAMAGE_CROPS_PARSED"] = df["DAMAGE_CROPS"].apply(parse_damage)
    df["INJURIES"] = df["INJURIES_INDIRECT"] + df["INJURIES_DIRECT"]
    df["DEATHS"] = df["DEATHS_INDIRECT"] + df["DEATHS_DIRECT"]

    folded = df.groupby(['MONTH_NAME', 'HOUR', 'YEAR']).agg(
        COUNT=('EVENT_ID', 'count'),
        DAMAGE_PROPERTY=('DAMAGE_PROPERTY_PARSED', 'sum'),
        DAMAGE_CROPS=('DAMAGE_CROPS_PARSED', 'sum'),
        INJURIES=('INJURIES', 'sum'),
        DEATHS=('DEATHS', 'sum')
    ).reset_index().melt(
        id_vars=['MONTH_NAME', 'HOUR', 'YEAR'],
        value_vars=['COUNT', 'DAMAGE_PROPERTY', 'DAMAGE_CROPS', 'INJURIES', 'DEATHS'],
        var_name='metric',
        value_name='value'
    )

    # Interactions
    metric = st.selectbox("Select Metric", ['COUNT', 'DAMAGE_PROPERTY', 'DAMAGE_CROPS', 'INJURIES', 'DEATHS'])
    axis_mode = st.selectbox("Axis Mode", ['hour_month', 'hour_year', 'year_month'])
    year_range = st.slider("Year Range", 2000, 2024, (2005, 2024))

    folded = folded[folded['metric'] == metric]
    folded = folded[(folded['YEAR'] >= year_range[0]) & (folded['YEAR'] <= year_range[1])]

    xdim = folded['HOUR'] if 'hour' in axis_mode else folded['YEAR']
    ydim = folded['MONTH_NAME'] if 'month' in axis_mode else folded['YEAR']

    heatmap = alt.Chart(folded).transform_calculate(
        xdim="toNumber(datum.HOUR)" if 'hour' in axis_mode else "datum.YEAR",
        ydim="datum.MONTH_NAME" if 'month' in axis_mode else "toNumber(datum.YEAR)"
    ).transform_aggregate(
        value='sum(value)', groupby=['xdim', 'ydim']
    ).mark_rect().encode(
        x=alt.X('xdim:O', title=None),
        y=alt.Y('ydim:O', title=None),
        color=alt.Color('value:Q', scale=alt.Scale(scheme='blues')),
        tooltip=['xdim:O', 'ydim:O', 'value:Q']
    ).properties(width=800, height=600)

    # Heatmap centered on the page
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        with st.container():
            st.altair_chart(heatmap, use_container_width=False)
