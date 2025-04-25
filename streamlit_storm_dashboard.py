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
### 🌪️ Welcome to the Tornado Tracker

This dashboard offers two powerful views to explore tornado patterns across the U.S.:

- **📍 2024 State Analysis:** Drill down into specific states for a single year  
- **📊 Multi-Year Heatmap:** Uncover broader patterns in tornado activity, damage, and casualties from 2000–2024

Use the sidebar to switch views and explore different years, metrics, or regions.
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

def load_all_years_data():
    dfs = []
    for year in range(2000, 2025):  # Extended to 2024 to match data availability
        pattern = os.path.join(os.path.dirname(__file__), 'data', f'StormEvents_details-ftp_v1.0_d{year}_c20250401_chunk_*.csv')
        files = sorted(glob.glob(pattern))
        if not files:
            st.sidebar.warning(f"⚠️ No files found for year {year} with pattern {pattern}")
            continue

        for file in files:
            try:
                df_year = pd.read_csv(file, encoding='latin1', on_bad_lines='skip')
                if 'TOR_F_SCALE' not in df_year.columns:
                    st.sidebar.warning(f"⚠️ 'TOR_F_SCALE' column missing in {file}")
                    continue
                if 'BEGIN_TIME' not in df_year.columns:
                    st.sidebar.warning(f"⚠️ 'BEGIN_TIME' column missing in {file}")
                    continue
                df_year = df_year[~df_year['TOR_F_SCALE'].isna()].copy()
                dfs.append(df_year)
                # st.write(f"Loaded {file} with {len(df_year)} rows.")
            except Exception as e:
                st.sidebar.error(f"❌ Error reading {file}: {e}")

    if not dfs:
        st.error("⚠️ No data files loaded. Please check the data directory and file patterns.")
        return pd.DataFrame()

    df = pd.concat(dfs, ignore_index=True)
    return df

def load_data_by_year(year):
    pattern = os.path.join("data", f"StormEvents_details-ftp_v1.0_d{year}_c20250401_chunk_*.csv")
    files = sorted(glob.glob(pattern))

    if not files:
        st.warning(f"⚠️ No files found for year {year}")
        return pd.DataFrame()

    dfs = []
    for file in files:
        try:
            df = pd.read_csv(file, on_bad_lines='skip', encoding='latin1')
            if 'TOR_F_SCALE' not in df.columns or 'BEGIN_DATE_TIME' not in df.columns:
                st.sidebar.warning(f"Missing expected columns in: {os.path.basename(file)}")
                continue
            dfs.append(df)
        except Exception as e:
            st.sidebar.error(f"❌ Could not read {os.path.basename(file)}: {e}")

    if not dfs:
        return pd.DataFrame()

    df = pd.concat(dfs, ignore_index=True)
    df = df[~df['TOR_F_SCALE'].isna()].copy()
    df['intensity'] = df['TOR_F_SCALE'].str.extract('(\d+)').astype(float)
    df['date'] = pd.to_datetime(df['BEGIN_DATE_TIME'], format='%d-%b-%y %H:%M:%S', errors='coerce')
    df['month'] = df['date'].dt.month
    state_name_to_fips = {state.name.upper(): int(state.fips) for state in us.states.STATES}
    df['STATE_FIPS'] = df['STATE'].map(state_name_to_fips)

    unmapped_states = df[df['STATE_FIPS'].isna()]['STATE'].unique()
    if len(unmapped_states) > 0:
        st.sidebar.warning(f"⚠️ Unmapped states found: {list(unmapped_states)}\n"
                           "ℹ️ *Note: This is likely due to missing data in the original NOAA dataset.*")

    return df
# ========== SIDEBAR ==========
st.sidebar.title("Tornado Dashboard Settings")
view_mode = st.sidebar.radio("Select View", ['2024 State Analysis', 'Multi-Year Heatmap'])

# ========== VIEW 1: STATE ANALYSIS 2024 ==========
if view_mode == '2024 State Analysis':

    available_years = list(range(2000, 2025))
    selected_year = st.sidebar.selectbox("Select Year:", available_years, index=available_years.index(2024))
    df = load_data_by_year(selected_year)

    all_states = sorted(df["STATE"].dropna().unique().tolist())
    st.sidebar.markdown("### State Filters")
    selected_state = st.sidebar.selectbox("Select State:", ["All States"] + all_states)

    # Dynamically ensure all US states are represented in the map
    # regardless of whether they have tornadoes in the selected year
    full_state_df = pd.DataFrame(
        [(state.name.upper(), int(state.fips)) for state in us.states.STATES],
        columns=["STATE", "STATE_FIPS"]
    )
    full_state_df["id"] = full_state_df["STATE_FIPS"]

    # Aggregate tornado data per state
    state_stats = df.groupby(["STATE", "STATE_FIPS"]).agg(
        tornado_count=('TOR_F_SCALE', 'count'),
        avg_intensity=('intensity', 'mean')
    ).reset_index()

    # Add `id` for merge
    state_stats["id"] = state_stats["STATE_FIPS"]

    # Merge to ensure all states are included
    state_stats = pd.merge(
        full_state_df,
        state_stats,
        on=["STATE", "STATE_FIPS", "id"],
        how="left"
    )
    state_stats["tornado_count"] = state_stats["tornado_count"].fillna(0)
    state_stats["avg_intensity"] = state_stats["avg_intensity"].fillna(0)

    # --- MAP SECTION ---
    st.title("🌀 Tornado Tracker: Interactive Insights Across U.S. States")
    st.subheader(f"1️⃣ Geographic Distribution – {selected_state}, {selected_year}")

    st.markdown("""
    #### 📍 How to Use This View
    - Select a **year** and **state** using the sidebar
    - View state-level tornado **frequency** and **average intensity**
    - Use interactive charts to explore monthly trends, size patterns, and scale distributions
    """)


    states_geo = alt.topo_feature(data.us_10m.url, 'states')

    map_chart = alt.Chart(states_geo).mark_geoshape().encode(
        color=alt.condition(
            alt.datum.tornado_count > 0,
            alt.Color('tornado_count:Q', scale=alt.Scale(scheme='reds'), title='Tornado Count'),
            alt.value('lightgray')  # gray fallback for no tornadoes
        ),
        tooltip=[
            alt.Tooltip('STATE:N', title='State'),
            alt.Tooltip('tornado_count:Q', title='Tornado Count'),
            alt.Tooltip('avg_intensity:Q', title='Avg Intensity')
        ]
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
    st.subheader(f"2️⃣ Monthly Tornado Trends – {selected_state}")
    df_trend = filter_state(df, selected_state)
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
    st.subheader(f"3️⃣ Tornado Size: Length vs. Width – {selected_state}")
    scatter_base = alt.Chart(df).mark_circle(size=60).encode(
        x="TOR_LENGTH:Q",
        y="TOR_WIDTH:Q",
        color=alt.condition(
            alt.datum.STATE == selected_state,
            alt.value("orange"),
            alt.value("lightgray")
        ),
        tooltip=["STATE", "TOR_LENGTH", "TOR_WIDTH", "TOR_F_SCALE"]
    ).properties(width=400, height=300)

    st.altair_chart(scatter_base, use_container_width=True)

    # --- Scale Bar Chart ---
    st.subheader(f"4️⃣ Tornado Frequency by Fujita Scale – {selected_state}")
    selected_state_scale = st.selectbox("Select State for Fujita Scale Bar Chart:", ["All States"] + all_states)

    df_scale = filter_state(df, selected_state)

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

    if df.empty:
        st.error("No data available to display the heatmap. Please ensure data files are correctly placed in the 'data' directory.")
    else:
        # Verify required columns

        st.markdown("""
        #### 📊 How to Use This View
        - Use the sidebar to choose a **metric**, **axis**, and **year range**
        - The central heatmap shows when and how strongly tornadoes occurred across time
        - Hover over heatmap cells or bar charts for detailed values
        """)
        
        required_columns = ['BEGIN_TIME', 'BEGIN_YEARMONTH', 'DAMAGE_PROPERTY', 'DAMAGE_CROPS', 'INJURIES_INDIRECT', 'INJURIES_DIRECT', 'DEATHS_INDIRECT', 'DEATHS_DIRECT', 'EVENT_ID']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            st.error(f"Missing required columns: {missing_columns}. Cannot generate heatmap.")
        else:
            # Time parsing
            df['BEGIN_TIME'] = df['BEGIN_TIME'].astype(str).str.zfill(4)
            df['HOUR'] = df['BEGIN_TIME'].str[:2].astype(int)
            df['YEAR'] = df['BEGIN_YEARMONTH'].astype(str).str[:4].astype(int)
            df['MONTH'] = df['BEGIN_YEARMONTH'].astype(str).str[4:].astype(int)
            df['MONTH_NAME'] = pd.to_datetime(df['MONTH'], format='%m').dt.strftime('%b')
            df['MONTH_NAME'] = pd.Categorical(
                df['MONTH_NAME'],
                categories=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
                ordered=True
            )

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

            # Fold the data
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

            # Sidebar controls for heatmap (replacing Altair bindings)
            st.sidebar.header("Heatmap Settings")
            metric = st.sidebar.selectbox(
                "Display Metric:",
                ['COUNT', 'DAMAGE_PROPERTY', 'DAMAGE_CROPS', 'INJURIES', 'DEATHS'],
                format_func=lambda x: {
                    'COUNT': 'Number of occurrences',
                    'DAMAGE_PROPERTY': 'Damage to properties',
                    'DAMAGE_CROPS': 'Damage to crops',
                    'INJURIES': 'Injuries',
                    'DEATHS': 'Deaths'
                }[x]
            )
            axis_mode = st.sidebar.selectbox(
                "Axis:",
                ['hour_month', 'hour_year', 'year_month'],
                format_func=lambda x: {
                    'hour_month': 'Hour vs Month',
                    'hour_year': 'Hour vs Year',
                    'year_month': 'Year vs Month'
                }[x]
            )
            year_range = st.sidebar.slider("Year Range", min_value=2000, max_value=2024, value=(2000, 2024))

            # Define Altair selectors
            selector = alt.param(name='metric', value=metric)
            axis_selector = alt.param(name='axis_mode', value=axis_mode)
            year_min = alt.param(name='year_min', value=year_range[0])
            year_max = alt.param(name='year_max', value=year_range[1])
            cell_select = alt.selection_point(
                name='cell_select',
                fields=['MONTH_NAME', 'HOUR'],
                on='click',
                clear='mouseout'
            )

            # Filter data early to reduce processing
            filtered_data = folded[
                (folded['metric'] == metric) &
                (folded['YEAR'] >= year_range[0]) &
                (folded['YEAR'] <= year_range[1])
            ]

            # ----- Central Heatmap -----
            heatmap = alt.Chart(filtered_data).add_params(
                selector,
                axis_selector,
                year_min,
                year_max,
                cell_select
            ).transform_calculate(
                xdim="toNumber(axis_mode === 'hour_month' || axis_mode === 'hour_year' ? datum.HOUR : datum.YEAR)",
                ydim="axis_mode === 'hour_month' || axis_mode === 'year_month' ? datum.MONTH_NAME : toNumber(datum.YEAR)"
            ).transform_aggregate(
                value='sum(value)',
                groupby=['xdim', 'ydim']
            ).mark_rect().encode(
                x=alt.X('xdim:O', title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y('ydim:O', sort=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
                        title=None, axis=alt.Axis(labels=False, ticks=False, grid=False)),
                color=alt.Color('value:Q', scale=alt.Scale(scheme='blues'), title="Metric Value", legend=alt.Legend(orient='bottom')),
                tooltip=[
                    alt.Tooltip('xdim:O', title='X'),
                    alt.Tooltip('ydim:O', title='Y'),
                    alt.Tooltip('value:Q', title='Metric Value')
                ]
            ).properties(
                width=600,
                height=300
            )

            # ----- Top Bar Chart (per Hour) -----
            bar_top_base = alt.Chart(filtered_data).add_params(
                selector,
                axis_selector,
                year_min,
                year_max
            ).transform_calculate(
                xdim="toNumber(axis_mode === 'hour_month' || axis_mode === 'hour_year' ? datum.HOUR : datum.YEAR)",
                ydim="axis_mode === 'hour_month' || axis_mode === 'year_month' ? datum.MONTH_NAME : toNumber(datum.YEAR)"
            ).transform_aggregate(
                total='sum(value)',
                groupby=['xdim']
            )

            bar_top = bar_top_base.mark_bar().encode(
                x=alt.X('xdim:O', title=None, axis=alt.Axis(title=None, labels=False, ticks=False, grid=False)),
                y=alt.Y('total:Q', title=None, axis=alt.Axis(title=None, labels=False, ticks=False, grid=False)),
                color=alt.Color('total:Q', scale=alt.Scale(scheme='blues'), legend=None),
                tooltip=[alt.Tooltip('xdim:O', title='X'), alt.Tooltip('total:Q', title='Metric Value')]
            ).properties(
                width=600,
                height=80
            )

            bar_top_label = bar_top_base.transform_window(
                rank='rank(total)',
                sort=[alt.SortField('total', order='descending')]
            ).transform_filter(
                alt.datum.rank == 1
            ).mark_text(
                align='center',
                dy=-5,
                fontSize=11,
                fontWeight='bold'
            ).encode(
                x=alt.X('xdim:O'),
                y=alt.Y('total:Q'),
                text=alt.Text('total:Q', format=".0f")
            )

            bar_top = bar_top + bar_top_label

            # ----- Left Bar Chart (per Month) -----
            bar_left_base = alt.Chart(filtered_data).add_params(
                selector,
                axis_selector,
                year_min,
                year_max
            ).transform_calculate(
                xdim="toNumber(axis_mode === 'hour_month' || axis_mode === 'hour_year' ? datum.HOUR : datum.YEAR)",
                ydim="axis_mode === 'hour_month' || axis_mode === 'year_month' ? datum.MONTH_NAME : toNumber(datum.YEAR)"
            ).transform_aggregate(
                total='sum(value)',
                groupby=['ydim']
            )

            bar_left = bar_left_base.mark_bar().encode(
                y=alt.Y('ydim:O', title=None, sort=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
                        axis=alt.Axis(title=None, labels=False, ticks=False, grid=False)),
                x=alt.X('total:Q', title=None, scale=alt.Scale(reverse=True), axis=alt.Axis(title=None, labels=False, ticks=False, grid=False)),
                color=alt.Color('total:Q', scale=alt.Scale(scheme='blues'), legend=None),
                tooltip=[alt.Tooltip('ydim:O', title='Y'), alt.Tooltip('total:Q', title='Metric Value')]
            ).properties(
                width=80,
                height=300
            )
            
            bar_left_label = bar_left_base.transform_window(
                rank='rank(total)',
                sort=[alt.SortField('total', order='descending')]
            ).transform_filter(
                alt.datum.rank == 1
            ).mark_text(
                align='left',
                dx=5,
                fontSize=11,
                fontWeight='bold',
                color='white'
            ).encode(
                y=alt.Y('ydim:O'),
                x=alt.X('total:Q'),
                text=alt.Text('total:Q', format=".0f")
            )

            bar_left = bar_left + bar_left_label
            
            # ----- Right Labels (for Month/Year) -----
            bar_right_labels = alt.Chart(filtered_data).add_params(
                selector,
                axis_selector,
                year_min,
                year_max
            ).transform_calculate(
                ydim="axis_mode === 'hour_month' || axis_mode === 'year_month' ? datum.MONTH_NAME : toNumber(datum.YEAR)"
            ).mark_bar(opacity=0).encode(
                y=alt.Y('ydim:O', title=None, sort=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
                        axis=alt.Axis(title=None, ticks=False, grid=False, labels=True)),
                x=alt.value(5)
            ).properties(
                width=50,
                height=300
            )

            # ----- Spacer (for Top Row Offset) -----
            spacer = alt.Chart(pd.DataFrame({'x': [0], 'y': [0]})).mark_point(opacity=0).encode(
                x=alt.X('x:Q', axis=alt.Axis(title=None, labels=False, ticks=False, grid=False)),
                y=alt.Y('y:Q', axis=alt.Axis(title=None, labels=False, ticks=False, grid=False))
            ).properties(
                width=80,  # Match bar_left width
                height=80  # Match bar_top height
            )

            # ----- Compose Layout with Offset -----
            top_row = alt.hconcat(
                spacer,
                bar_top,
                spacing=5
            )

            bottom_row = alt.hconcat(
                bar_left,
                heatmap,
                bar_right_labels,
                spacing=5
            ).resolve_scale(color='independent')

            layout = alt.vconcat(
                top_row,
                bottom_row,
                spacing=5
            ).resolve_scale(color='independent')

            # ----- Apply Final Config -----
            full_layout = layout.configure_axis(
                grid=False,
                domain=False
            ).configure_view(
                stroke=None
            ).configure_title(
                fontSize=24,
                anchor='middle',
                font='Arial',
                color='black'
            ).properties(
                title="When do tornadoes occur? What is their effect?"
            )

        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            with st.container():
                st.altair_chart(full_layout, use_container_width=False)

            # Footer
            st.markdown("---")
            st.caption("Data: NOAA Storm Events | Interactive Dashboard built with Streamlit & Altair")
