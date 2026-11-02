import streamlit as st
import os
from PIL import Image

st.set_page_config(page_title="Marketing Funnel & A/B Test Analytics", layout="wide")

st.title("📈 Marketing Funnel & A/B Test Analytics Dashboard")
st.write("An end-to-end performance analysis of an acquisition funnel and checkout-page optimization.")

# Check if charts exist; if not, execute the processing engine to build them
if not os.path.exists("outputs/charts/01_funnel.png"):
    with st.spinner("Executing pipeline engine (Data generation + SQL compilation + Statistics computation)..."):
        os.system("python src/generate_data.py")
        os.system("python src/analysis.py")

# Layout columns to display your key outputs side-by-side
col1, col2 = st.columns(2)
with col1:
    st.subheader("Conversion Funnel Drops")
    if os.path.exists("outputs/charts/01_funnel.png"):
        st.image("outputs/charts/01_funnel.png", use_container_width=True)
    
    st.subheader("Device Segment Heatmaps")
    if os.path.exists("outputs/charts/04_device_funnel_heatmap.png"):
        st.image("outputs/charts/04_device_funnel_heatmap.png", use_container_width=True)

with col2:
    st.subheader("Paid Acquisition Channel ROAS & CAC")
    if os.path.exists("outputs/charts/02_channel_roas_cac.png"):
        st.image("outputs/charts/02_channel_roas_cac.png", use_container_width=True)
        
    st.subheader("Statistical A/B Test Performance")
    if os.path.exists("outputs/charts/05_ab_test_results.png"):
        st.image("outputs/charts/05_ab_test_results.png", use_container_width=True)
