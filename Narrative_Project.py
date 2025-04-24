#!/usr/bin/env python
# coding: utf-8

# # Narrative Project

# In[1]:


import pandas as pd
import altair as alt
alt.data_transformers.disable_max_rows()


# In[ ]:


# import os
# import csv

# for year in range(2000,2025):
#     # 設定檔案大小限制（例如 2GB）
#     MAX_FILE_SIZE = 22 * 1024 * 1024  # 2GB in bytes
#     input_file = "data/StormEvents_details-ftp_v1.0_d"+str(year)+"_c20250401.csv"
#     output_prefix = "data_split/StormEvents_details-ftp_v1.0_d"+str(year)+"_c20250401_chunk_"

#     with open(input_file, 'r', newline='', encoding='utf-8') as infile:
#         reader = csv.reader(infile)
#         header = next(reader)

#         file_count = 1
#         output_file = f"{output_prefix}{file_count}.csv"
#         outfile = open(output_file, 'w', newline='', encoding='utf-8')
#         writer = csv.writer(outfile)
#         writer.writerow(header)

#         current_size = os.path.getsize(output_file)

#         for row in reader:
#             writer.writerow(row)
#             current_size += sum(len(field.encode('utf-8')) for field in row) + len(row)  # rough estimate
#             if current_size >= MAX_FILE_SIZE:
#                 outfile.close()
#                 file_count += 1
#                 output_file = f"{output_prefix}{file_count}.csv"
#                 outfile = open(output_file, 'w', newline='', encoding='utf-8')
#                 writer = csv.writer(outfile)
#                 writer.writerow(header)
#                 current_size = os.path.getsize(output_file)

#         outfile.close()


# In[62]:


dfs = []

for year in range(2000, 2025):
    path = f"data/StormEvents_details-ftp_v1.0_d{year}_c20250401.csv"
    
    try:
        df_year = pd.read_csv(path, encoding='latin1')
        # df_year = df_year[~df_year['TOR_F_SCALE'].isna()].copy()
        dfs.append(df_year)
        print(f"Loaded {year} with {len(df_year)} rows.")
    except FileNotFoundError:
        print(f"File not found for year {year}")
    except Exception as e:
        print(f"Error reading {year}: {e}")

# 合併所有年份的資料
df = pd.concat(dfs, ignore_index=True)


# In[5]:


df = df[~df['TOR_F_SCALE'].isna()].copy()

# Handle times with inconsistent lengths like 230, 1947, etc.
# Pad the BEGIN_TIME column to ensure 4-digit formatting (e.g., 0230 becomes 02:30)
df['BEGIN_TIME'] = df['BEGIN_TIME'].astype(str).str.zfill(4)
df['HOUR'] = df['BEGIN_TIME'].str[:2].astype(int)

# Extract year and month from BEGIN_YEARMONTH
df['YEAR'] = df['BEGIN_YEARMONTH'].astype(str).str[:4].astype(int)
df['MONTH'] = df['BEGIN_YEARMONTH'].astype(str).str[4:].astype(int)

# Optionally map month number to month name
df['MONTH_NAME'] = pd.to_datetime(df['MONTH'], format='%m').dt.strftime('%b')
df['MONTH_NAME'] = pd.Categorical(df['MONTH_NAME'], categories=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'], ordered=True)

df["INJURIES"] = df["INJURIES_INDIRECT"] + df["INJURIES_DIRECT"]
df["DEATHS"] = df["DEATHS_INDIRECT"] + df["DEATHS_DIRECT"]

df["YEAR"] = df['BEGIN_YEARMONTH'].astype(str).str[:4].astype(int)


# In[6]:


# Helper function to convert strings like "25.00M" to float
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


# In[7]:


# Fold the data so it works dynamically
folded_df = df.groupby(['MONTH_NAME', 'HOUR', 'YEAR']).agg(
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

folded_df['MONTH_NAME'] = folded_df['MONTH_NAME'].astype(str)
folded_df['HOUR'] = folded_df['HOUR'].astype(int)
folded_df['YEAR'] = folded_df['YEAR'].astype(int)


# In[8]:


# Create selector
selector = alt.param(
    name='metric',
    bind=alt.binding_radio(
        options=['COUNT', 'DAMAGE_PROPERTY', 'DAMAGE_CROPS', 'INJURIES', 'DEATHS'],
        labels=['Number of occurrence', 'Damage to properties', 'Damage to crops', 'Injuries', 'Deaths'],
        name='Display Metric:'
    ),
    value='COUNT'
)


# In[9]:


cell_select = alt.selection_point(
    name='cell_select',
    fields=['MONTH_NAME', 'HOUR'],
    on='click',
    clear='mouseout'  # or use 'mouseout' for auto-clear
)


# In[10]:


axis_selector = alt.param(
    name='axis_mode',
    bind=alt.binding_select(
        options=['hour_month', 'hour_year', 'year_month'],
        labels=['Hour vs Month', 'Hour vs Year', 'Year vs Month'],
        name='Axis: '
    ),
    value='hour_month'
)


# In[11]:


year_min = alt.param(name='year_min', value=2000, bind=alt.binding_range(min=2000, max=2025, name='Start Year', step=1))
year_max = alt.param(name='year_max', value=2025, bind=alt.binding_range(min=2000, max=2025, name='End Year', step=1))


# In[56]:


# ----- Central Heatmap -----
heatmap = alt.Chart(folded_df).add_params(
    selector,
    axis_selector,
    year_min,
    year_max
).transform_filter(
    alt.datum.metric == selector
).transform_filter("datum.YEAR >= year_min && datum.YEAR <= year_max"
).transform_calculate(
    xdim="toNumber(axis_mode === 'hour_month' || axis_mode === 'hour_year' ? datum.HOUR : datum.YEAR)",
    ydim="axis_mode === 'hour_month' || axis_mode === 'year_month' ? datum.MONTH_NAME : toNumber(datum.YEAR)"
).transform_aggregate(
    value='sum(value)',  
    groupby=['xdim', 'ydim'] 
).mark_rect().encode(
    x=alt.X('xdim:O', title=None, axis=alt.Axis(labelAngle=0)),
    y=alt.Y('ydim:O', sort=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
             title=None, axis=alt.Axis(labels=False, ticks=False, grid=False),),
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
bar_top_base = alt.Chart(folded_df).add_params(
    selector,
    axis_selector,
    year_min,
    year_max
).transform_filter(
    alt.datum.metric == selector
).transform_filter("datum.YEAR >= year_min && datum.YEAR <= year_max"
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
bar_left_base = alt.Chart(folded_df).add_params(
    selector,
    axis_selector,
    year_min,
    year_max
).transform_filter(
    alt.datum.metric == selector
).transform_filter("datum.YEAR >= year_min && datum.YEAR <= year_max"
).transform_calculate(
    xdim="toNumber(axis_mode === 'hour_month' || axis_mode === 'hour_year' ? datum.HOUR : datum.YEAR)",
    ydim="axis_mode === 'hour_month' || axis_mode === 'year_month' ? datum.MONTH_NAME : toNumber(datum.YEAR)"
).transform_aggregate(
    total='sum(value)',
    groupby=['ydim']
)

bar_left = bar_left_base.mark_bar().encode(
    y=alt.Y('ydim:O', title=None, axis=alt.Axis(title=None, labels=False, ticks=False, grid=False)),
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
    fontSize=11,
    dx=5,
    color='white',
    fontWeight='bold'
).encode(
    y=alt.Y('ydim:O'),
    x=alt.X('total:Q'),
    text=alt.Text('total:Q', format=".0f")
)

bar_left = bar_left + bar_left_label



# In[57]:


bar_right_labels = alt.Chart(folded_df).add_params(
    selector,
    axis_selector,
    year_min,
    year_max
).transform_filter(
    alt.datum.metric == selector
).transform_filter("datum.YEAR >= year_min && datum.YEAR <= year_max"
).transform_calculate(
    ydim="axis_mode === 'hour_month' || axis_mode === 'year_month' ? datum.MONTH_NAME : toNumber(datum.YEAR)"
).mark_bar(opacity=0).encode(
    y=alt.Y('ydim:O',
    title=None,
    sort=None,
    axis=alt.Axis(title=None, ticks=False, grid=False)),
    x=alt.value(5)
).properties(
    width=50,   
    height=300
)


# In[58]:


spacer = alt.Chart(pd.DataFrame({'x': [0], 'y': [0]})).mark_point(opacity=0).encode(
    x=alt.X('x:Q',  axis=alt.Axis(title=None, labels=False, ticks=False, grid=False)),
    y=alt.Y('y:Q',  axis=alt.Axis(title=None, labels=False, ticks=False, grid=False)),
).properties(
    width=80,   # same as bar_left width
    height=80   # same as bar_top height
)

# --- Compose layout with offset ---
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

# --- Apply final config ---
full_layout = layout.configure_axis(
    grid=False,
    domain=False
).resolve_scale(
    color='independent'
).configure_view(
    stroke=None  # Remove all chart borders
).configure_title(
    fontSize=24,      
    anchor='middle',  
    font='Arial',     
    color='black'     
).properties(
    title="When do tornadoes occur? What is their effect?"
)

full_layout


# # Map

# In[16]:


import altair as alt
import pandas as pd
import us
from vega_datasets import data

tornado_data = df[~df['TOR_F_SCALE'].isna()].copy()

tornado_data['intensity'] = tornado_data['TOR_F_SCALE'].str.extract('(\d+)').astype(float)

tornado_data['date'] = pd.to_datetime(tornado_data['BEGIN_DATE_TIME'])
tornado_data['month'] = tornado_data['date'].dt.month

state_select = alt.selection_multi(fields=['STATE'])

time_brush = alt.selection_interval(encodings=['x'])

state_tornado_stats = tornado_data.groupby(['STATE', 'STATE_FIPS']).agg(
    tornado_count=('TOR_F_SCALE', 'count'),
    avg_intensity=('intensity', 'mean'),
    avg_length=('TOR_LENGTH', 'mean')
).reset_index()

states = alt.topo_feature(data.us_10m.url, 'states')

map_chart = alt.Chart(states).mark_geoshape().encode(
    color=alt.condition(
        state_select,
        alt.Color('tornado_count:Q', scale=alt.Scale(scheme='reds'), title='Tornado Count'),
        alt.value('lightgray')
    ),
    stroke=alt.value('white'),
    strokeWidth=alt.condition(state_select, alt.value(2), alt.value(0.5)),
    tooltip=[
        alt.Tooltip('state_name:N', title='State'),
        alt.Tooltip('tornado_count:Q', title='Tornado Count'),
        alt.Tooltip('avg_intensity:Q', title='Avg. Intensity', format='.1f')
    ]
).transform_lookup(
    lookup='id',
    from_=alt.LookupData(
        data=state_tornado_stats,
        key='STATE_FIPS',
        fields=['STATE', 'tornado_count', 'avg_intensity', 'avg_length']
    )
).transform_calculate(
    tornado_count='isValid(datum.tornado_count) ? datum.tornado_count : 0',
    avg_intensity='isValid(datum.avg_intensity) ? datum.avg_intensity : 0',
    state_name='isValid(datum.STATE) ? datum.STATE : "No Data"'
).project(
    type='albersUsa'
).properties(
    width=700,
    height=400,
    title='Tornado Events by State (2024) - Click on states to select'
).add_params(
    state_select
)

intensity_chart = alt.Chart(tornado_data).mark_line(point=True).encode(
    x=alt.X('month:O', title='Month', axis=alt.Axis(labelAngle=0)),
    y=alt.Y('average(intensity):Q',
           title='Average Tornado Intensity',
           scale=alt.Scale(domain=[0, 5])),
    color=alt.value('orange'),
    opacity=alt.condition(time_brush, alt.value(1), alt.value(0.7))
).transform_filter(
    alt.datum.intensity > 0
).transform_filter(
    state_select
)

count_chart = alt.Chart(tornado_data).mark_bar(opacity=0.5).encode(
    x=alt.X('month:O', title='Month'),
    y=alt.Y('count():Q',
           title='Number of Tornado Events',
           axis=alt.Axis(titleColor='steelblue')),
    color=alt.value('steelblue')
).transform_filter(
    state_select
)


monthly_chart = alt.layer(
    intensity_chart,
    count_chart
).resolve_scale(
    y='independent'
).properties(
    width=700,
    height=200,
    title='Monthly Tornado Intensity & Event Count - Drag to select time range'
).add_params(
    time_brush
)

scatter_chart = alt.Chart(tornado_data).mark_circle().encode(
    x=alt.X('TOR_LENGTH:Q', title='Tornado Length (miles)'),
    y=alt.Y('TOR_WIDTH:Q', title='Tornado Width (yards)'),
    size=alt.Size('intensity:Q', scale=alt.Scale(range=[50, 300]), title='Intensity'),
    color=alt.Color('TOR_F_SCALE:N', title='Tornado Scale', scale=alt.Scale(scheme='viridis')),
    opacity=alt.condition(state_select, alt.value(0.8), alt.value(0.2)),
    tooltip=[
        alt.Tooltip('STATE:N', title='State'),
        alt.Tooltip('TOR_F_SCALE:N', title='F Scale'),
        alt.Tooltip('TOR_LENGTH:Q', title='Length (miles)', format='.2f'),
        alt.Tooltip('TOR_WIDTH:Q', title='Width (yards)', format='.2f'),
        alt.Tooltip('BEGIN_DATE_TIME:T', title='Date/Time')
    ]
).transform_filter(
    state_select
).transform_filter(
    time_brush
).properties(
    width=350,
    height=300,
    title='Tornado Characteristics'
)

# Create a bar chart showing tornado counts by F-scale
scale_chart = alt.Chart(tornado_data).mark_bar().encode(
    x=alt.X('TOR_F_SCALE:N', title='Tornado Scale'),
    y=alt.Y('count():Q', title='Number of Tornadoes'),
    color=alt.Color('TOR_F_SCALE:N', title='Tornado Scale', scale=alt.Scale(scheme='viridis')),
    opacity=alt.condition(state_select, alt.value(1), alt.value(0.2))
).transform_filter(
    state_select
).transform_filter(
    time_brush
).properties(
    width=350,
    height=300,
    title='Tornado Counts by Scale'
)

# Add a text layer for when no state is selected
no_data_text = alt.Chart(pd.DataFrame([{'text': 'Click on states in the map to see data'}])).mark_text(
    fontSize=15,
    font='Arial',
    align='center',
    baseline='middle'
).encode(
    text='text:N'
).transform_filter(
    ~state_select
)

# Layer the monthly chart with the no data message
monthly_chart_with_text = alt.layer(monthly_chart, no_data_text)

# Combine the scatter and bar charts side by side
details_composite = alt.hconcat(scatter_chart, scale_chart)

# Combine all charts into final visualization
final_chart = alt.vconcat(
    map_chart,
    monthly_chart_with_text,
    details_composite
).resolve_scale(
    color=alt.ResolveMode('independent')
).configure_view(
    stroke=None
)

final_chart


# In[146]:


full_layout


# In[64]:


import pandas as pd
import altair as alt

# Aggregate totals
agg_df = df.groupby('EVENT_TYPE').agg({
    'TOTAL_INJURIES': 'sum',
    'TOTAL_DEATHS': 'sum',
    'DAMAGE_PROPERTY_NUM': 'sum',
    'DAMAGE_CROPS_NUM': 'sum'
}).reset_index()

# Function to generate each chart
def make_chart(df, value_col, title, color):
    top10 = df.nlargest(10, value_col).copy()
    top10['EVENT_TYPE'] = pd.Categorical(
        top10['EVENT_TYPE'],
        categories=top10.sort_values(value_col, ascending=False)['EVENT_TYPE'],
        ordered=True
    )

    return alt.Chart(top10).mark_bar().encode(
        y=alt.Y('EVENT_TYPE:N', sort=None, title='Event Type'),
        x=alt.X(f'{value_col}:Q', title=None),
        tooltip=['EVENT_TYPE:N', f'{value_col}:Q'],
        color=alt.value(color)
    ).properties(
        width=300,
        height=200,
        title=title
    )

# Create each of the 4 charts
injuries_chart = make_chart(agg_df, 'TOTAL_INJURIES', 'Top 10 by Injuries', '#e15759')
deaths_chart = make_chart(agg_df, 'TOTAL_DEATHS', 'Top 10 by Deaths', '#4e79a7')
prop_damage_chart = make_chart(agg_df, 'DAMAGE_PROPERTY_NUM', 'Top 10 by Property Damage', '#f28e2b')
crop_damage_chart = make_chart(agg_df, 'DAMAGE_CROPS_NUM', 'Top 10 by Crop Damage', '#76b7b2')

# Arrange in 2x2 grid
final_chart = (injuries_chart | deaths_chart) & (prop_damage_chart | crop_damage_chart)
final_chart


# # Website Design

# In[1]:


full_layout.save('heatmap.html')

