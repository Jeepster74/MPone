import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_folium import folium_static
import folium
from folium.plugins import MarkerCluster
import os
import json

# Page Config
st.set_page_config(
    page_title="MP One | Market Analysis",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark Mode Aestethic (Vibe check)
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .stMetric {
        background-color: rgba(255, 255, 255, 0.05);
        padding: 15px;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# 1. AUTHENTICATION
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'auth_config.yaml')
with open(CONFIG_PATH) as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

authenticator.login(location='main')

if st.session_state['authentication_status'] == False:
    st.error('Username/password is incorrect')
elif st.session_state['authentication_status'] == None:
    st.warning('Please enter your username and password')
elif st.session_state['authentication_status']:
    # Get user info from state
    name = st.session_state['name']
    username = st.session_state['username']
    # 2. DATA LOADING
    @st.cache_data(ttl=60) # Refresh every minute to pick up background script updates
    def load_data():
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        csv_path = os.path.join(root_dir, 'data', 'karting_enriched.csv')
        df = pd.read_csv(csv_path)
        # Type cleanup
        for col in ['is_indoor', 'is_outdoor', 'is_sim']:
            df[col] = df[col].astype(bool)
        return df

    df = load_data()

    # SIDEBAR
    st.sidebar.title(f"Welcome, {name}")
    authenticator.logout('Logout', 'sidebar')

    st.sidebar.divider()
    st.sidebar.subheader("Global Filters")
    
    country_filter = st.sidebar.multiselect("Countries", options=sorted(df['Country'].unique()), default=df['Country'].unique()[:5])
    
    type_filter = st.sidebar.multiselect(
        "Facility Features", 
        options=["Indoor", "Outdoor", "SIM Racing"],
        default=["Indoor", "Outdoor"]
    )

    # Filter Strategy
    filtered_df = df[df['Country'].isin(country_filter)]
    if "Indoor" not in type_filter: filtered_df = filtered_df[~filtered_df['is_indoor']]
    if "Outdoor" not in type_filter: filtered_df = filtered_df[~filtered_df['is_outdoor']]
    if "SIM Racing" in type_filter: filtered_df = filtered_df[filtered_df['is_sim']]

    # HEADER
    st.title("🏎️ MP One | Market Intelligence Dashboard")
    st.markdown("---")

    # TOP METRICS
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Locations", f"{len(filtered_df)}")
    with m2:
        wealth_mean = filtered_df['disposable_income_pps'].mean()
        st.metric("Avg. Regional Wealth", f"{wealth_mean:,.0f} PPS")
    with m3:
        indoor_count = filtered_df['is_indoor'].sum()
        st.metric("Indoor Tracks", f"{indoor_count}")
    with m4:
        sim_count = filtered_df['is_sim'].sum()
        st.metric("SIM Facilities", f"{sim_count}")

    st.divider()

    # MAIN CONTENT (Map & Stats)
    c1, c2 = st.columns([2, 1])

    with c1:
        st.subheader("📍 Geospatial Distribution & Wealth")
        
        # Folium Map
        m = folium.Map(location=[50.8, 4.4], zoom_start=5, tiles="cartodb dark_matter")
        marker_cluster = MarkerCluster().add_to(m)

        for _, row in filtered_df.iterrows():
            if pd.notna(row['Latitude']) and pd.notna(row['Longitude']):
                color = 'blue'
                if row['is_indoor'] and row['is_outdoor']: color = 'orange'
                elif row['is_indoor']: color = 'green'
                elif row['is_sim']: color = 'purple'
                
                popup_text = f"<b>{row['Name']}</b><br>Wealth: {row['disposable_income_pps']} PPS"
                folium.Marker(
                    location=[row['Latitude'], row['Longitude']],
                    popup=popup_text,
                    icon=folium.Icon(color=color, icon='info-sign')
                ).add_to(marker_cluster)

        folium_static(m, width=800, height=500)

    with c2:
        st.subheader("💡 Market Insights")
        
        # Wealth Distribution Chart
        fig = px.histogram(
            filtered_df, 
            x='disposable_income_pps', 
            nbins=20,
            title="Socio-Economic Wealth Spread",
            color_discrete_sequence=['#1FBAD6']
        )
        fig.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)

        # Facility Composition
        comp_data = {
            "Type": ["Indoor", "Outdoor", "SIM"],
            "Count": [filtered_df['is_indoor'].sum(), filtered_df['is_outdoor'].sum(), filtered_df['is_sim'].sum()]
        }
        fig_pie = px.pie(comp_data, values='Count', names='Type', hole=.4, title="Facility Mix")
        fig_pie.update_layout(template="plotly_dark", showlegend=False, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_pie, use_container_width=True)

    # TABLE VIEW
    st.divider()
    st.subheader("📋 Top Acquisition Targets (by Data Density)")
    st.dataframe(
        filtered_df[['Name', 'City', 'Country', 'disposable_income_pps', 'building_sqm', 'Review Velocity (12m)']].sort_values('disposable_income_pps', ascending=False).head(50),
        use_container_width=True
    )
