import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="NSW Emergency Dept Admission Analytics",
    page_icon="🏥",
    layout="wide",
)

# Connect to DuckDB (Read-Only mode for safety)
@st.cache_resource
def get_db_connection():
    return duckdb.connect("nsw_healthcare_analytics.db", read_only=True)

con = get_db_connection()

# Load data from DuckDB table
@st.cache_data
def load_data():
    query = "SELECT * FROM nsw_hospital_performance;"
    return con.execute(query).fetchdf()

df = load_data()

# --- SIDEBAR FILTERS ---
st.sidebar.header("🎛️ Filter Controls")

# Quarter Selector
selected_quarter = st.sidebar.selectbox(
    "Select Reporting Quarter:",
    options=sorted(df["quarter"].unique(), reverse=True),
    index=0
)

quarter_df = df[df["quarter"] == selected_quarter]

selected_lhd = st.sidebar.multiselect(
    "Select Local Health District (LHD):",
    options=quarter_df["lhd_name"].unique(),
    default=quarter_df["lhd_name"].unique()
)

# Filter dataframe based on sidebar selections
filtered_df = quarter_df[quarter_df["lhd_name"].isin(selected_lhd)]

# --- MAIN DASHBOARD HEADER ---
st.title("🏥 NSW Emergency Dept Admission Analytics")
st.markdown("Operational risk analytics tracking emergency department patient flows and Q2 2026 performance across New South Wales health facilities.")

# --- TOP KPI METRICS ROW ---
col1, col2, col3 = st.columns(3)
with col1:
    total_presentations = int(filtered_df["ed_presentations"].sum()) if "ed_presentations" in filtered_df.columns else 0
    st.metric("Total ED Presentations", f"{total_presentations:,}")
with col2:
    metric_col = "p90_paramedic_transfer_minutes"
    avg_p90 = round(filtered_df[metric_col].mean(), 1) if metric_col in filtered_df.columns else 0.0
    st.metric("Avg P90 Paramedic Transfer (Mins)", f"{avg_p90} mins")
with col3:
    avg_on_time = round(filtered_df["patients_within_4hrs_pct"].mean(), 1) if "patients_within_4hrs_pct" in filtered_df.columns else 0.0
    st.metric("Avg Treatment On-Time Compliance", f"{avg_on_time}%")

st.markdown("---")

# --- CHARTS SECTION ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📊 P90 Paramedic Transfer Times by Hospital")
    if not filtered_df.empty:
        metric_col = "p90_paramedic_transfer_minutes"
        fig_bar = px.bar(
            filtered_df.sort_values(metric_col, ascending=True),
            x=metric_col,
            y="hospital_name",
            color="peer_group",
            orientation="h",
            labels={metric_col: "P90 Transfer Time (Minutes)", "hospital_name": "Hospital"},
            title="90th Percentile Time to Transfer Care from Paramedics"
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.warning("Please select at least one Local Health District from the sidebar.")

with col_right:
    st.subheader("⚡ Presentations vs. Transfer Times")
    if not filtered_df.empty:
        metric_col = "p90_paramedic_transfer_minutes"
        # Drop rows where essential plotting metrics are NaN to prevent Plotly ValueErrors
        scatter_df = filtered_df.dropna(subset=["ed_presentations", metric_col])
        
        if not scatter_df.empty:
            fig_scatter = px.scatter(
                scatter_df,
                x="ed_presentations",
                y=metric_col,
                color="lhd_name",
                hover_name="hospital_name",
                labels={"ed_presentations": "ED Presentations", metric_col: "P90 Transfer Time (Mins)"},
                title="Volume vs. Bottleneck Correlation"
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.warning("Insufficient complete data for scatter plot visualization.")
    else:
        st.warning("No data available for the selected filters.")

# --- DETAILED DATA TABLE ---
st.subheader("📋 Underlying Database Records")
st.dataframe(filtered_df, use_container_width=True)