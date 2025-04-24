import streamlit as st
import pandas as pd
import altair as alt
from vega_datasets import data as vega_data
import us
import os


st.set_page_config(layout="wide")

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

def load_data():
    file_path = os.path.join(os.path.dirname(__file__), 'data/StormEvents_details-ftp_v1.0_d2024_c20250401_chunk_1.csv')
    if os.path.exists(file_path):
        df = pd.read_csv(file_path, encoding='latin1')
        return df
    else:
        st.error("❌ Data file not found.")
        return pd.DataFrame()

data_2024 = load_data()

if data_2024.empty:
    st.stop()

# Tornado-specific filtering and preprocessing
tornado_data = data_2024[~data_2024['TOR_F_SCALE'].isna()].copy()
tornado_data.loc[:, 'intensity'] = tornado_data['TOR_F_SCALE'].str.extract(r'(\d+)').astype(float)
# Fixing UserWarning: Specify the datetime format explicitly
tornado_data['date'] = pd.to_datetime(tornado_data['BEGIN_DATE_TIME'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
tornado_data['month'] = tornado_data['date'].dt.month

# Aggregate stats by state
state_tornado_stats = tornado_data.groupby(['STATE', 'STATE_FIPS']).agg(
    tornado_count=('TOR_F_SCALE', 'count'),
    avg_intensity=('intensity', 'mean'),
    avg_length=('TOR_LENGTH', 'mean')
).reset_index()

# Interactive charts
states = alt.topo_feature(vega_data.us_10m.url, 'states')
state_select = alt.selection_point(fields=['STATE'], toggle=True)
time_brush = alt.selection_interval(encodings=['x'])

map_chart = alt.Chart(states).mark_geoshape().encode(
    color=alt.condition(
        state_select,
        alt.Color('tornado_count:Q', scale=alt.Scale(scheme='reds'), title='Tornado Count'),
        alt.value('lightgray')
    ),
    tooltip=[
        alt.Tooltip('state_name:N', title='State'),
        alt.Tooltip('tornado_count:Q', title='Tornado Count'),
        alt.Tooltip('avg_intensity:Q', title='Avg. Intensity', format='.1f')
    ]
).transform_lookup(
    lookup='id',
    from_=alt.LookupData(state_tornado_stats, 'STATE_FIPS', 
                         ['STATE', 'tornado_count', 'avg_intensity', 'avg_length'])
).transform_calculate(
    tornado_count='isValid(datum.tornado_count) ? datum.tornado_count : 0',
    avg_intensity='isValid(datum.avg_intensity) ? datum.avg_intensity : 0',
    state_name='isValid(datum.STATE) ? datum.STATE : "No Data"'
).project(
    type='albersUsa'
).properties(
    width=700,
    height=400,
    title='Tornado Events by State (2024) - Click to filter'
).add_params(
    state_select
)

intensity_chart = alt.Chart(tornado_data).mark_line(point=True).encode(
    x='month:O',
    y=alt.Y('average(intensity):Q', title='Avg Intensity'),
    color=alt.value('orange'),
    opacity=alt.condition(time_brush, alt.value(1), alt.value(0.7))
).transform_filter(state_select)

count_chart = alt.Chart(tornado_data).mark_bar(opacity=0.5).encode(
    x='month:O',
    y=alt.Y('count():Q', title='Event Count'),
    color=alt.value('steelblue')
).transform_filter(state_select)

monthly_chart = alt.layer(intensity_chart, count_chart).resolve_scale(y='independent').properties(
    width=700,
    height=200,
    title='Monthly Tornado Intensity & Count'
).add_params(time_brush)

scatter_chart = alt.Chart(tornado_data).mark_circle().encode(
    x='TOR_LENGTH:Q',
    y='TOR_WIDTH:Q',
    size=alt.Size('intensity:Q', scale=alt.Scale(range=[50, 300])),
    color=alt.Color('TOR_F_SCALE:N', scale=alt.Scale(scheme='viridis')),
    tooltip=['STATE:N', 'TOR_F_SCALE:N', 'TOR_LENGTH:Q', 'TOR_WIDTH:Q', 'BEGIN_DATE_TIME:T'],
    opacity=alt.condition(state_select, alt.value(0.8), alt.value(0.2))
).transform_filter(state_select).transform_filter(time_brush).properties(
    width=350,
    height=300,
    title='Tornado Characteristics'
)

scale_chart = alt.Chart(tornado_data).mark_bar().encode(
    x='TOR_F_SCALE:N',
    y='count():Q',
    color=alt.Color('TOR_F_SCALE:N', scale=alt.Scale(scheme='viridis')),
    opacity=alt.condition(state_select, alt.value(1), alt.value(0.2))
).transform_filter(state_select).transform_filter(time_brush).properties(
    width=350,
    height=300,
    title='Tornado Counts by Scale'
)

no_data_text = alt.Chart(pd.DataFrame([{'text': 'Click a state to view details'}])).mark_text(
    fontSize=15, font='Arial', align='center', baseline='middle'
).encode(text='text:N').transform_filter(~state_select)

monthly_chart_with_text = alt.layer(monthly_chart, no_data_text)
details = alt.hconcat(scatter_chart, scale_chart)

final_chart = alt.vconcat(map_chart, monthly_chart_with_text, details).configure_view(stroke=None)

# Display in Streamlit
st.subheader("📊 Tornado Characteristics and Severity Analysis")
st.altair_chart(final_chart, use_container_width=True)


def load_multi_year_data():
    dfs = []
    for year in range(2000, 2002):
        path = f"data/StormEvents_details-ftp_v1.0_d{year}_c20250401_chunk_*.csv"
        try:
            df_year = pd.read_csv(path, on_bad_lines='skip', engine='python')
            df_year = df_year[~df_year['TOR_F_SCALE'].isna()].copy()
            dfs.append(df_year)
        except Exception:
            continue
    df = pd.concat(dfs, ignore_index=True)

    df['BEGIN_TIME'] = df['BEGIN_TIME'].astype(str).str.zfill(4)
    df['HOUR'] = df['BEGIN_TIME'].str[:2].astype(int)
    df['YEAR'] = df['BEGIN_YEARMONTH'].astype(str).str[:4].astype(int)
    df['MONTH'] = df['BEGIN_YEARMONTH'].astype(str).str[4:].astype(int)
    df['MONTH_NAME'] = pd.to_datetime(df['MONTH'], format='%m').dt.strftime('%b')
    df['MONTH_NAME'] = pd.Categorical(df['MONTH_NAME'], categories=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'], ordered=True)

    df['INJURIES'] = df['INJURIES_INDIRECT'] + df['INJURIES_DIRECT']
    df['DEATHS'] = df['DEATHS_INDIRECT'] + df['DEATHS_DIRECT']

    def parse_damage(value):
        try:
            if isinstance(value, str):
                value = value.strip().upper()
                if value.endswith('K'):
                    return float(value[:-1]) * 1e3
                elif value.endswith('M'):
                    return float(value[:-1]) * 1e6
                else:
                    return float(value)
            return float(value)
        except:
            return 0.0

    df['DAMAGE_PROPERTY_PARSED'] = df['DAMAGE_PROPERTY'].apply(parse_damage)
    df['DAMAGE_CROPS_PARSED'] = df['DAMAGE_CROPS'].apply(parse_damage)

    df['TOR_F_SCALE'] = df['TOR_F_SCALE'].fillna("F0")
    df['intensity'] = df['TOR_F_SCALE'].str.extract('(\\d+)').astype(float)
    df['date'] = pd.to_datetime(df['BEGIN_DATE_TIME'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    df['month'] = df['date'].dt.month

    # Fixing FutureWarning: observed=False is deprecated
    folded_df = df.groupby(['MONTH_NAME', 'HOUR', 'YEAR'], observed=False).agg(
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
    return df, folded_df

df, folded_df = load_multi_year_data()

# Heatmap Controls
st.sidebar.header("📌 Heatmap Settings")
metric = st.sidebar.radio("Select Metric", ["COUNT", "DAMAGE_PROPERTY", "DAMAGE_CROPS", "INJURIES", "DEATHS"], format_func=lambda x: x.replace("_", " ").title())
axis_mode = st.sidebar.selectbox("Select Axis Mode", ["hour_month", "hour_year", "year_month"])
year_range = st.sidebar.slider("Select Year Range", 2000, 2024, (2000, 2024))

filtered_df = folded_df[(folded_df['metric'] == metric) & (folded_df['YEAR'] >= year_range[0]) & (folded_df['YEAR'] <= year_range[1])]
# Fixing SettingWithCopyWarning: Use .loc to modify DataFrame slices
filtered_df.loc[:, 'xdim'] = filtered_df.apply(lambda r: r['HOUR'] if 'hour' in axis_mode else r['YEAR'], axis=1)
filtered_df.loc[:, 'ydim'] = filtered_df.apply(lambda r: r['MONTH_NAME'] if 'month' in axis_mode else r['YEAR'], axis=1)

heatmap = alt.Chart(filtered_df).mark_rect().encode(
    x=alt.X('xdim:O', title=None, axis=alt.Axis(labelAngle=0)),
    y=alt.Y('ydim:O', title=None, axis=alt.Axis(labels=False, ticks=False, grid=False)),
    color=alt.Color('value:Q', scale=alt.Scale(scheme='blues'), title="Metric Value"),
    tooltip=[alt.Tooltip('xdim:O', title='X'), alt.Tooltip('ydim:O', title='Y'), alt.Tooltip('value:Q')]
).properties(
    width=700,
    height=300,
    title=f"📊 Tornado {metric.replace('_', ' ').title()} by {axis_mode.replace('_', ' ').title()}"
)

st.subheader("📊 Multi-Year Tornado Trend Heatmap")
st.altair_chart(heatmap, use_container_width=True)
