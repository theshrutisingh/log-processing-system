import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path to allow importing 'alerts' from dashboard root
# This assumes this file is in src/dashboard/components/
try:
    import alerts
except ImportError:
    sys.path.append(str(Path(__file__).parent.parent))
    import alerts

# --- UI Renderers ---

def render_kpi(title, value, unit, color, icon, trend, trend_val):
    trend_html = ""
    if trend_val and trend:
        # enhanced trend display
        trend_bg = f"{color}15" # 10-15% opacity
        trend_html = f"""<div class="kpi-trend" style="color: {color}; background-color: {trend_bg};">{trend} {trend_val}</div>"""
        
    st.markdown(f"""
<div class="kpi-card">
<div class="kpi-header">
<div class="kpi-icon-wrapper" style="background-color: {color}15; color: {color};">
{icon}
</div>
{trend_html}
</div>
<div class="kpi-value">{value}<span style="font-size: 1.1rem; color: var(--text-muted); font-weight: 500; margin-left: 4px;">{unit}</span></div>
<div class="kpi-title">{title}</div>
</div>
""", unsafe_allow_html=True)

def render_progress_bar(label, value, max_val, color):
    # Safe division
    pct = (value / max_val * 100) if max_val > 0 else 0
    st.markdown(f"""
<div style="margin-bottom: 16px;">
<div class="prog-label-row">
<span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 80%;">{label}</span>
<span style="font-weight: 600;">{value}</span>
</div>
<div class="prog-bg">
<div class="prog-fill" style="width: {pct}%; background-color: {color};"></div>
</div>
</div>
""", unsafe_allow_html=True)

@st.dialog("Error Details")
def view_error_details(message: str, count: int, examples: pd.DataFrame):
    """
    Dialog to show detailed information about an error.
    """
    st.markdown(f"### Error Message")
    st.code(message, language="text")
    
    st.markdown("### Summary")
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Total Occurrences", count)
    with c2: 
        if not examples.empty and 'timestamp' in examples.columns:
            st.metric("First Seen", examples['timestamp'].min().strftime('%Y-%m-%d %H:%M'))
    with c3:
        if not examples.empty and 'timestamp' in examples.columns:
             st.metric("Last Seen", examples['timestamp'].max().strftime('%Y-%m-%d %H:%M'))
             
    st.markdown("### Latest Occurrences")
    if not examples.empty:
        display_cols = ['timestamp', 'log_level', 'service', 'message']
        # Filter explicitly available columns
        existing_cols = [c for c in display_cols if c in examples.columns]
        # Fallback if service not there
        if 'service' not in existing_cols and 'service' not in examples.columns:
             examples['service'] = "Auth" # Mock/Default if missing
             existing_cols = ['timestamp', 'log_level', 'service', 'message']
        
        st.dataframe(
            examples[existing_cols].head(100),
            use_container_width=True,
            hide_index=True,
            column_config={
                "timestamp": st.column_config.DatetimeColumn("Time", format="D MMM, HH:mm:ss"),
                "log_level": "Level",
                "service": "Service",
                "message": st.column_config.TextColumn("Message", width="large")
            }
        )
    else:
        st.info("No detailed occurrences data available.")

@st.dialog("Alert History")
def view_alert_history(start_date=None, end_date=None, target_errors=None):
    st.markdown("### Recent Alerts")
    
    # Load alerts
    history_df = alerts.get_alerts(start_date=start_date, end_date=end_date)
    
    # Filter by Top Errors if requested
    if target_errors and not history_df.empty and ('details' in history_df.columns or 'message' in history_df.columns):
        # Use simple string inclusion instead of regex to avoid crashes with special chars in logs
        def is_relevant(row):
            txt = str(row.get('details', '')) + " " + str(row.get('message', ''))
            return any(str(err) in txt for err in target_errors)
            
        history_df = history_df[history_df.apply(is_relevant, axis=1)]

    if not history_df.empty:
        # Display Table
        st.dataframe(
            history_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "timestamp": "Time",
                "alert_type": "Type",
                "message": "Message",
                "severity": "Severity",
                "details": "Details"
            }
        )
        
        # Download
        csv = history_df.to_csv(index=False)
        st.download_button(
            label="Download Alerts (CSV)",
            data=csv,
            file_name=f"alert_history_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("No alerts found matching the criteria.")
