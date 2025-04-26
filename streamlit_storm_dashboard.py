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
def load_all_years_data():
    dfs = []
    for year in range(2000, 2002):  # Extended to 2024 to match data availability
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

    # --- INTRO SECTION ---
    st.markdown("""
    ## How do tornadoes compare with other storm events?

    First off, let's take a look at how the destructive force of tornadoes compares with other storm events in the U.S., using the most recent data from 2024 as a current snapshot of annual trends.
    While technological advances in forecasting have improved warning times, tornadoes continue to pose major risks, with 2024 data showing they remain a leading cause of storm-related injuries and considerable economic losses ([NOAA, 2024](https://www.spc.noaa.gov/climo/)).
    
    Data tracked on injuries and deaths (in number), as well as damage to both property and crops (in dollars) can give us insight into this.
    In the below graph, we can see that in 2024 tornadoes were, by far, the number 1 cause of injuries! They were also the 4th highest cause of property damage, and fell in the top 10 for both deaths (6th) and crop damage (9th) as well.
    Looking across multiple types of impact—injuries, deaths, and economic damage—gives a fuller picture of how tornadoes affect communities beyond just headline-grabbing destruction.
    
    """)
    st.markdown("<br>", unsafe_allow_html=True)   # One line break

    # Display static image
    st.image('comparison_chart.svg', use_container_width=True)

    st.markdown("""
    As you can see above, tornadoes are among the most powerful and destructive natural disasters in the United States, with the country experiencing more tornadoes than any other nation.  
    On average, about 1,000 tornadoes are reported each year across the U.S., causing significant damage to property, crops, and human life ([NOAA, 2023](https://www.noaa.gov/education/resource-collections/weather-atmosphere/tornadoes)).
    As you explore the interactive charts below, think about how these different categories show up in different ways.
    """)

    
    # --- MAP SECTION SETUP ---
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
    st.markdown("""
    ## 📘 Dashboard Guide
    
    Welcome to the Tornado Tracker Dashboard — an interactive data exploration tool that reveals patterns in U.S. tornado activity.
    
    ### 🔍 How to Use
    - Use the **sidebar** to select a specific **year** and **state**
    - Hover over visualizations to view detailed statistics
    - Explore monthly, geographic, and scale-based patterns
    
    """)
    
    st.subheader(f"1️⃣ Geographic Distribution – {selected_state}, {selected_year}")
    st.markdown("""
    This map shows the number of tornadoes per state. Darker red shades indicate higher counts. Hover over a state to view:
    - **Total tornadoes**
    - **Average intensity** (based on EF scale)
    
    🕵️‍♂️ **Tip**: Gray areas had **no recorded tornadoes** during the selected year.
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

    st.markdown("""
    ## 🌪️ Tornado Impacts Across Key Regions
    
    Tornadoes cause devastating impacts across many U.S. regions. In 2024, several areas were particularly affected:
    
    ### ⚠️ Areas of Significant Tornado Activity:
    - **Oklahoma** experienced some of the highest tornado activity nationwide, with numerous strong and long-tracked tornadoes causing damage across both rural and urban communities.
    - **Illinois** also faced an unusually active season. Tornadoes struck parts of the state that are typically vulnerable, affecting towns, farmland, and suburbs alike.
    - **Miami and parts of southern Florida** recorded several tornado events, mainly weaker tornadoes (EF0–EF1), often connected to tropical weather systems. Even lower-rated tornadoes can cause serious damage, especially in densely populated areas.
    
    ### 🏛️ Impact Across the Midwest
    The most active region, often referred to as "**Tornado Alley**," spans much of the **Midwest**, including states like Missouri, Kansas, and Iowa. This region as a whole continued to face heightened tornado risks in 2024. This reflects ongoing patterns where warm, moist air from the Gulf meets cold, dry air from Canada, creating the perfect conditions for severe storms ([American Meteorological Society, 2022](https://www.ametsoc.org/index.cfm/ams/about-ams/ams-statements/statements-of-the-ams-in-force/tornadoes/)).

     parts of Texas, Oklahoma, Kansas, and Nebraska, where warm, moist air from the Gulf of Mexico collides with cool, dry air from Canada, creating ideal conditions for severe storms 

    🔎 Use the interactive maps and charts above to explore how tornado frequency and intensity varied across states and months.
    """)


    # Filtered Data
    def filter_state(df, selected_state):
        return df if selected_state == "All States" else df[df["STATE"] == selected_state]

    # --- Monthly Trend Chart ---
    st.subheader(f"2️⃣ Monthly Tornado Trends – {selected_state}")
    st.markdown("""
    This chart shows how tornado **frequency** and **intensity** change throughout the year.
    
    - **Bars** = Number of tornadoes per month
    - **Orange line** = Average tornado intensity (EF scale)
    
    Use the brush tool to highlight specific months!
    """)

    df_trend = filter_state(df, selected_state)
    brush = alt.selection_interval(encodings=["x"])

    intensity = alt.Chart(df_trend).mark_line(point=True).encode(
        x=alt.X("month:O", axis=alt.Axis(labelAngle=0)),  # Rotate x-axis labels horizontal
        y=alt.Y("average(intensity):Q", axis=alt.Axis(titleColor="orange")),  # Y-axis title color
        color=alt.value("orange"),
        opacity=alt.condition(brush, alt.value(1), alt.value(0.3))
    ).add_params(brush)

    count = alt.Chart(df_trend).mark_bar(opacity=0.5).encode(
        x=alt.X("month:O", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("count():Q", axis=alt.Axis(titleColor="steelblue")),  # Y-axis title color
        color=alt.value("steelblue")
    )

    st.altair_chart((intensity + count).resolve_scale(y="independent").properties(width=800, height=250), use_container_width=True)

    # --- Scatter Chart ---
    st.subheader(f"3️⃣ Tornado Size: Length vs. Width – {selected_state}")
    st.markdown("""
    Each dot represents a tornado's **path length** and **width**.
    
    - **Orange**: Tornadoes from the selected state (if selected in sidebar)
    - **Gray**: All other tornadoes in the U.S. in the selected year
    
    Use this to spot unusually large or narrow tornadoes!
    """)

    scatter_base = alt.Chart(df).mark_circle(size=60).encode(
        x=alt.X("TOR_LENGTH:Q", title='Length'),
        y=alt.Y("TOR_WIDTH:Q", title='Width'),
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
    st.markdown("""
    The Enhanced Fujita (EF) scale classifies tornadoes by wind damage:
    
    - **EF0–EF1**: Weak (light to moderate damage)
    - **EF2–EF3**: Strong (considerable damage)
    - **EF4–EF5**: Violent (devastating to incredible damage)
    - **EFU**: Unrated / Unknown
    
    This bar chart shows how tornadoes in the selected state are distributed by EF scale.
    """)

    df_scale = filter_state(df, selected_state)

    scale_chart = alt.Chart(df_scale).mark_bar().encode(
        x=alt.X("TOR_F_SCALE:N", title='Scale', axis=alt.Axis(labelAngle=0)), # Rotate x-axis labels horizontal
        y="count():Q",
        color=alt.Color("TOR_F_SCALE:N",
                        legend=None,
                        scale = alt.Scale(
                            domain=['EF0', 'EF1', 'EF2', 'EF3', 'EF4', 'EF5', 'EFU'],
                            range=['#FEF001', '#FFCE03', '#FD9A01', '#FD6104', '#FF2C05', '#F00505', '#D3D3D3']
                        )
        )
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
        st.markdown('---')

        st.title("🌪️ When do tornadoes occur?")
        st.markdown("""
        #### ⚠️ The 2011 Super Outbreak 
        The year 2011 stands out as one of the most catastrophic tornado seasons in U.S. history, marked by an extraordinary level of tornado activity and devastation. Central to this was the April 25–28 Super Outbreak, which unleashed 360 tornadoes across 21 states, including four EF5 tornadoes—the highest rating on the Enhanced Fujita scale. On April 27 alone, a record-shattering 219 tornadoes were confirmed, making it the most active tornado day ever recorded. The human toll was staggering, with 324 tornado-related deaths, 238 of which occurred in Alabama alone, and an additional 24 fatalities caused by related thunderstorm events. April 2011 saw a total of 758 tornadoes, making it the single most active tornado month in U.S. history. This unparalleled outbreak not only redefined the scale of tornado disasters but also revealed how a short window of extreme weather can account for a significant portion of yearly destruction and loss of life.
        
        Building on lessons from historic events like 2011, it becomes clear that uncovering temporal and seasonal tornado patterns is crucial for both understanding and preparedness. Tornadoes are among the most destructive natural phenomena, and their behavior—when examined over time and across impact metrics—can provide key insights into risk. This interactive visualization allows users to explore tornado occurrences and their effects across time, seasonality, and different impact dimensions, unlocking patterns that are often hidden in raw data.

        """)

        st.markdown("---")

        st.markdown("""
        #### 📊 How to Use the Heatmap
        This interactive heatmap helps you explore when tornadoes happen, how intense they are, and how their impact varies across different timeframes and dimensions. Here's how you can navigate it:
        
        - 1️⃣ Select Time Duration (Which years do you want to analyze):
             Use the year range slider to focus on a specific period—from 2000 to 2024. Whether you're interested in a single year or long-term trends, this control lets you zoom in or out as needed.

        - 2️⃣ Switch Between Time Axes (Choose how you want to explore time):
            - Hour vs. Month: When during the day do tornadoes most commonly occur in each month?
            - Year vs. Month: How has tornado activity changed across months over the years?
            - Hour vs. Year: Are tornadoes happening at different times of day in recent years?

        - 3️⃣ Choose a Metric (What kind of impact do you want to examine):
            Toggle between: Number of tornadoes, Injuries, Deaths, Property Damage, and Crop damage.

        - 4️⃣ Hover over heatmap cells or bar charts for detailed values
                    
        These tools allow you to uncover patterns that go beyond what’s visible in static charts. Whether you're studying trends, investigating specific years, or simply exploring out of curiosity, the heatmap offers a flexible way to ask and answer deeper questions.
        """)
        
        st.markdown("---")

        st.markdown("""
        #### 🔎 Questions You Might Want To Explore:
        - Do tornadoes occur more often at night or in the afternoon?
        - Has tornado damage increased in the last decade?
        - Which month sees the most tornado-related deaths?
        - What are the most dangerous hours across all years?
        """)

        st.markdown("---")

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
