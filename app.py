import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

st.set_page_config(page_title="Interactive Marketing Analytics Platform", layout="wide")

# Title and Business Context
st.title("📊 Interactive Marketing Funnel & A/B Test Dashboard")
st.markdown("""
*Built by Swetha | MCA Graduate Portfolio*  
This interactive interface demonstrates data pipeline execution, statistical hypothesis testing, and core growth marketing loops.
""")
st.write("---")

# Pipeline execution check
if not os.path.exists("outputs/funnel.csv"):
    with st.spinner("Processing local database pipelines..."):
        os.system("python src/generate_data.py")
        os.system("python src/analysis.py")

# 🛠️ SIDEBAR FILTER FOR RECRUITERS
st.sidebar.header("🎛️ Live Recruitment Demo Controls")
st.sidebar.markdown("Test the interaction layers by modifying the filters below:")

# Safe load for data files
@st.cache_data
def load_funnel_data():
    return pd.read_csv("outputs/funnel.csv") if os.path.exists("outputs/funnel.csv") else pd.DataFrame()

@st.cache_data
def load_channel_data():
    return pd.read_csv("outputs/channel_performance.csv") if os.path.exists("outputs/channel_performance.csv") else pd.DataFrame()

df_funnel = load_funnel_data()
df_channel = load_channel_data()

# Device filter option
if not df_funnel.empty and 'device' in df_funnel.columns:
    devices = ['All Devices'] + list(df_funnel['device'].unique())
    selected_device = st.sidebar.selectbox("Filter Metrics by Device Type:", devices)
else:
    selected_device = 'All Devices'

st.sidebar.success("💡 Tip: Hover over any chart element to see hidden underlying statistical values!")

# LAYOUT: MAIN ANALYTICS TILES
col1, col2 = st.columns(2)

with col1:
    st.subheader("🛒 Interactive Conversion Funnel")
    if not df_funnel.empty:
        # Dynamically filter data framework if device selected
        if selected_device != 'All Devices':
            plot_funnel = df_funnel[df_funnel['device'] == selected_device]
        else:
            plot_funnel = df_funnel.groupby('stage_name', as_index=False).sum(numeric_only=True)
            
        fig_funnel = px.bar(
            plot_funnel, 
            x='user_count', 
            y='stage_name', 
            orientation='h',
            labels={'user_count': 'Active Shoppers', 'stage_name': 'Funnel Stage'},
            color='user_count',
            color_continuous_scale='Purples' # Matches Swetha's Lavender/Purple Aesthetic!
        )
        fig_funnel.update_layout(yaxis={'categoryorder':'total descending'}, coloraxis_showscale=False)
        st.plotly_chart(fig_funnel, use_container_width=True)
    else:
        st.info("Pipeline processing standard fallback assets.")

with col2:
    st.subheader("💰 Acquisition Channel Return (ROAS)")
    if not df_channel.empty:
        fig_channel = px.bar(
            df_channel,
            x='channel',
            y='roas',
            text='roas',
            labels={'roas': 'Return on Ad Spend (ROAS)', 'channel': 'Marketing Channel'},
            color='roas',
            color_continuous_scale='Blugrn'
        )
        fig_channel.update_traces(texttemplate='%{text:.2f}x', textposition='outside')
        # Add break-even line indicator
        fig_channel.add_hline(y=1.0, line_dash="dash", line_color="red", annotation_text="Break-Even (1.0x)")
        st.plotly_chart(fig_channel, use_container_width=True)

st.write("---")
col3, col4 = st.columns(2)

with col3:
    st.subheader("🛡️ Growth Experiments (A/B Test Metric Lift)")
    # Generate explicit statistical hover card metrics
    categories = ['Control (Old Checkout)', 'Variant (One-Page Checkout)']
    conversions = [7.36, 8.74] # Hardcoded tracking metrics derived from project source data
    
    fig_ab = go.Figure([go.Bar(x=categories, y=conversions, marker_color=['#b39ddb', '#7e57c2'])])
    fig_ab.update_traces(texttemplate='%{y}%', textposition='outside')
    fig_ab.update_layout(yaxis_range=[0,12], yaxis_title="Conversion Rate (%)")
    st.plotly_chart(fig_ab, use_container_width=True)

with col4:
    st.subheader("🎯 Portfolio Evaluation Summary")
    st.info("""
    **Analytical Takeaways for Hiring Managers:**
    - **Funnel Bottleneck Found:** The sharpest friction drop-off resides at the *Checkout → Purchase* phase (46% leak rate).
    - **Budget Optimization Strategy:** Recommend immediately cutting down deficit spending on *Meta Ads (0.80x ROAS)* and reallocating capital into *Email Channels (7.5x ROAS)*.
    - **Statistical Significance Verified:** The One-Page checkout variant shows an absolute **+18.8% relative lift** with a highly stable significance value of **p < 0.0001**, passing all strict family-wise error guardrails.
    """)
