"""SafeSphere AI - Enhanced UI/UX Version"""
import streamlit as st
from safesphere_intelligence import analyze_location_demo

# Page config
st.set_page_config(page_title="SafeSphere AI", page_icon="🛡️", layout="wide")

# Custom CSS
st.markdown("""
<style>
    .stAlert {border-radius: 10px;}
    .stMetric {background-color: #f0f2f6; padding: 10px; border-radius: 8px;}
    h1 {color: #1f77b4;}
    h2 {color: #2ca02c;}
    .alert-card {
        background-color: #f8f9fa;
        border-left: 5px solid;
        padding: 15px;
        margin: 10px 0;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.title("🛡️ SafeSphere AI")
st.markdown("### Personal Risk Intelligence for Safer Travel")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    demo_mode = st.toggle("🎭 Demo Mode", value=True)
    
    if demo_mode:
        st.success("✅ Using demo data - perfect for presentations")
        scenario = st.selectbox("Select Scenario", ["normal", "flood", "earthquake", "cyclone", "multi"])
    else:
        st.info("ℹ️ Fetching real-time data from APIs")
    
    st.markdown("---")
    st.markdown("### 📖 How to Use")
    st.markdown("""
    1. Enter location details
    2. Choose demo or live mode
    3. Click 'Analyze Location'
    4. View environmental data & alerts
    """)
    
    st.markdown("---")
    st.markdown("**SafeSphere AI** © 2024")

# Main content
st.markdown("---")

# Location section
st.subheader("📍 Location Details")

col1, col2, col3 = st.columns(3)

with col1:
    location_name = st.text_input("Location Name", value="Chennai, India")

with col2:
    latitude = st.number_input("Latitude", value=13.0827, format="%.4f", min_value=-90.0, max_value=90.0)

with col3:
    longitude = st.number_input("Longitude", value=80.2707, format="%.4f", min_value=-180.0, max_value=180.0)

# Quick presets
st.markdown("**⚡ Quick Select:**")
col_p1, col_p2, col_p3, col_p4, col_p5 = st.columns(5)

presets = [
    ("🇮🇳 Chennai", 13.0827, 80.2707),
    ("🇮🇳 Delhi", 28.7041, 77.1025),
    ("🇮🇳 Mumbai", 19.0760, 72.8777),
    ("🇯🇵 Tokyo", 35.6762, 139.6503),
    ("🇺🇸 SF", 37.7749, -122.4194)
]

for i, (name, lat, lon) in enumerate(presets):
    with [col_p1, col_p2, col_p3, col_p4, col_p5][i]:
        if st.button(name, use_container_width=True, key=f"btn_{i}"):
            location_name, latitude, longitude = name, lat, lon
            st.rerun()

# Analyze button
st.markdown("---")
analyze_btn = st.button("🔍 Analyze Location", type="primary", use_container_width=True)

# Process analysis
if analyze_btn:
    with st.spinner("🔄 Analyzing location..."):
        result = analyze_location_demo(latitude, longitude, location_name, scenario if demo_mode else "normal")
    
    if result["status"] in ["success", "partial"]:
        
        # Demo warning
        if result.get("is_demo_mode"):
            st.warning("⚠️ **DEMO MODE**: Simulated data for demonstration")
        
        # Environment section
        st.subheader("🌍 Current Environmental Conditions")
        
        env = result["environment"]
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(label="🌡️ Temperature", value=f"{env.get('temperature_c', 0):.1f} °C")
            st.metric(label="💧 Precipitation", value=f"{env.get('precipitation_mm', 0):.1f} mm")
        
        with col2:
            st.metric(label="🌧️ Rain Probability", value=f"{env.get('precipitation_probability', 0)}%")
            st.metric(label="💨 Wind Speed", value=f"{env.get('wind_speed_kmh', 0):.1f} km/h")
        
        with col3:
            aqi = env.get('aqi')
            st.metric(label="🌫️ AQI", value=aqi if aqi else "N/A")
            pm2_5 = env.get('pm2_5')
            st.metric(label="🔬 PM2.5", value=f"{pm2_5:.1f}" if pm2_5 else "N/A")
        
        with col4:
            st.metric(label="📊 Data Status", value="🎭 Demo" if demo_mode else "✅ Live")
            st.metric(label="🕐 Updated", value="Just now")
        
        st.caption(f"Last updated: {env.get('updated_at', 'N/A')}")
        
        # Alerts section
        st.markdown("---")
        st.subheader("🔔 Safety Alerts")
        
        alerts = result.get("alerts", [])
        
        if alerts:
            alerts_sorted = sorted(alerts, key=lambda x: x.get("priority_score", 0), reverse=True)
            st.success(f"⚠️ Found {len(alerts_sorted)} alert(s) requiring your attention")
            
            for alert in alerts_sorted:
                severity = alert.get("severity", "LOW")
                
                if severity == "CRITICAL":
                    color = "red"
                    icon = "🔴"
                    border_color = "#ff4444"
                elif severity == "HIGH":
                    color = "orange"
                    icon = "🟠"
                    border_color = "#ff8800"
                elif severity == "MODERATE":
                    color = "yellow"
                    icon = "🟡"
                    border_color = "#ffaa00"
                else:
                    color = "green"
                    icon = "🟢"
                    border_color = "#00aa00"
                
                st.markdown(f"""
                <div class="alert-card" style="border-color: {border_color};">
                    <h3>{icon} {alert.get('title', 'Safety Alert')}</h3>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown(f"**Severity:** :{color}[**{severity}**]")
                    st.markdown(f"**Priority Score:** {alert.get('priority_score', 0)}/100")
                
                with col2:
                    st.markdown(f"**Hazard Type:** {alert.get('hazard_type', 'N/A')}")
                    st.markdown(f"**Source:** {alert.get('source', 'N/A')}")
                
                st.info(alert.get("summary", "No summary available"), icon="ℹ️")
                
                with st.expander("🤔 Why am I seeing this alert?", expanded=False):
                    st.write(alert.get("why", "No explanation available"))
                    
                    priority_breakdown = alert.get("priority_breakdown")
                    if priority_breakdown:
                        st.markdown("**Priority Score Breakdown:**")
                        for factor in priority_breakdown.get("factors", []):
                            st.write(f"- {factor}")
                        st.write(f"**Total: {priority_breakdown.get('score', 0)} points ({priority_breakdown.get('level', 'UNKNOWN')})**")
                
                st.markdown("**✅ Recommended Actions:**")
                for action in alert.get("actions", []):
                    st.write(f"- {action}")
                
                st.markdown("**❌ Things to Avoid:**")
                for item in alert.get("avoid", []):
                    st.write(f"- {item}")
                
                with st.expander("📋 Additional Details"):
                    if alert.get('distance_km'):
                        st.write(f"**Distance:** {alert.get('distance_km')} km")
                    if alert.get('location'):
                        st.write(f"**Location:** {alert.get('location')}")
                    st.write(f"**Confidence:** {alert.get('confidence', 0):.0%}")
                    st.write(f"**Timestamp:** {alert.get('timestamp', 'N/A')}")
                
                st.markdown("---")
        
        else:
            st.success("✅ No significant hazards detected. Conditions appear normal.", icon="✅")
            st.info("ℹ️ This doesn't mean there's no risk - always stay informed.")
    
    else:
        st.error(f"❌ Analysis failed: {result.get('error_message', 'Unknown error')}")
        st.info("💡 Try again or switch to demo mode.")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 20px;">
    <p><strong>🛡️ SafeSphere AI</strong> - Personal Risk Intelligence for Safer Travel</p>
    <p style="font-size: 12px;">
        This is a decision-support tool, NOT an official disaster warning system. 
        Always follow guidance from local authorities and official sources.
    </p>
</div>
""", unsafe_allow_html=True)
