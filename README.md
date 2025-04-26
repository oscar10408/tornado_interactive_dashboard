# 🌀 Tornado Tracker Dashboard

Explore how tornado patterns and climate change have evolved across the United States over the past decades.  
Built with **Streamlit** and **Altair**, this dashboard offers interactive visualizations across multiple dimensions: location, time, intensity, and environmental factors.

[![Website Preview](preview.png)](https://si649-narrative-project.streamlit.app/)  
🔗 [Live App Here](https://si649-narrative-project.streamlit.app/)

---

## 📊 Features

**2024 State Analysis View**  
Explore tornado counts and intensities across all U.S. states in 2024.  
- Interactive U.S. map by tornado frequency
- Monthly trends in tornado occurrence and intensity
- Tornado size scatterplots (length vs width)
- Distribution of tornadoes by Enhanced Fujita (EF) scale

**Multi-Year Heatmap View (2000–2024)**  
Analyze broader tornado patterns across hours, months, and years.  
- Customize heatmap by different metrics: number of tornadoes, injuries, deaths, property damage, crop damage
- Explore seasonal and hourly tornado patterns
- Zoom in on specific timeframes using dynamic filters

**Climate Change Insights**  
Investigate how rising land surface temperatures correlate with tornado activity from 1950 to 2024.  
- Dual-axis chart: land temperature anomaly vs tornado counts
- Observes positive correlation between temperature rise and tornado reports

---

## 🗂️ Project Structure

```bash
├── data_split/                  # Pre-processed NOAA Storm Events and temperature data
├── streamlit_storm_dashboard.py  # Main Streamlit app
├── preview.png                   # Website preview image
└── README.md                     # This file
