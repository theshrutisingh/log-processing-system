"""
Streamlit Dashboard for Log Processing System
Modern, interactive dashboard for visualizing log analytics
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import json
import glob
from pathlib import Path
import alerts
import auth
import otp_utils

# --- CONFIGURATION & STYLING ---
# Page configuration
st.set_page_config(
    page_title="Distributed Log Analytics",
    layout="wide",
    initial_sidebar_state="collapsed" # Hide default sidebar
)

# Custom CSS for "Clean Corporate/Enterprise" Light UI
def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Load External CSS
css_path = Path(__file__).parent / "assets" / "css" / "style.css"
if css_path.exists():
    load_css(str(css_path))
else:
    st.warning("CSS file not found. Styles may be missing.")

# --- IMPORTS ---
# --- IMPORTS ---
try:
    from views.auth_view import login_page
    from views.settings_view import render_settings
    from controllers.data_loader import load_raw_data_v2, filter_data
    from components.ui_components import view_error_details, view_alert_history, render_kpi, render_progress_bar
except ImportError:
    # Fallback for direct execution
    import sys
    sys.path.append(str(Path(__file__).parent))
    from views.auth_view import login_page
    from views.settings_view import render_settings
    from controllers.data_loader import load_raw_data_v2, filter_data
    from components.ui_components import view_error_details, view_alert_history, render_kpi, render_progress_bar

# --- Authentication UI ---
# (Logic moved to views/auth_view.py)

def logout():
    st.session_state.logged_in = False
    st.session_state.username = None

# --- Helper Functions (Loaders) ---

# (Data logic moved to controllers/data_loader.py)


# --- Report Generation ---

def generate_csv_report(df: pd.DataFrame) -> str:
    """Generate CSV report string from current dataframe"""
    if df.empty: return ""
    
    # 1. Summary Section
    total = len(df)
    errors = len(df[df['log_level'] == 'ERROR']) if 'log_level' in df.columns else 0
    warnings = len(df[df['log_level'] == 'WARN']) if 'log_level' in df.columns else 0
    rate = (errors / total * 100) if total > 0 else 0
    
    summary = f"SUMMARY REPORT\nDeprecated Generated_at,{datetime.now()}\nTotal Logs,{total}\nTotal Errors,{errors}\nTotal Warnings,{warnings}\nError Rate,{rate:.2f}%\n"

    # --- Enhanced Metrics ---
    peak_error_info = "N/A"
    most_freq_error = "N/A"
    
    try:
        if not df.empty and 'log_level' in df.columns and 'timestamp' in df.columns:
             err_df_metrics = df[df['log_level'] == 'ERROR'].copy()
             if not err_df_metrics.empty:
                 # 1. Peak Time (Hourly)
                 try:
                     # Ensure we don't breaks original index if needed, but here we work on copy
                     err_df_metrics = err_df_metrics.set_index('timestamp')
                     hourly_counts = err_df_metrics.resample('h').size()
                     if not hourly_counts.empty:
                         peak_ts = hourly_counts.idxmax()
                         peak_val = hourly_counts.max()
                         peak_end = peak_ts + timedelta(hours=1)
                         peak_error_info = f"{peak_ts.strftime('%Y-%m-%d %H:00')} - {peak_end.strftime('%H:00')} (Count: {peak_val})"
                 except Exception: pass
                 
                 # 2. Frequent Error
                 if 'message' in df.columns: # Use original df columns check just in case
                     try:
                         # We use the filtered err_df_metrics (reset index needed? No, value_counts works on Series)
                         # err_df_metrics index is timestamp now, but column 'message' should still be there?
                         # set_index moves column to index? No, keeps others if not dropped? 
                         # Default behavior: `timestamp` moves to index, `message` remains as column.
                         top_err = err_df_metrics['message'].value_counts()
                         if not top_err.empty:
                             msg = top_err.index[0]
                             count = top_err.iloc[0]
                             # Escape commas for CSV safety
                             msg_clean = str(msg).replace(',', ';').replace('\n', ' ')
                             most_freq_error = f"{msg_clean} (Count: {count})"
                     except Exception: pass
    except Exception: pass

    summary += f"Peak Error Time,{peak_error_info}\nMost Frequent Error,{most_freq_error}\n\n"

    
    # 2. Detailed Data
    # Select useful columns
    cols = [c for c in ['timestamp', 'log_level', 'service', 'error_type', 'message'] if c in df.columns]
    
    # Filter for ERRORS only
    error_df = df[df['log_level'] == 'ERROR'] if 'log_level' in df.columns else pd.DataFrame(columns=cols)
    csv_data = error_df[cols].to_csv(index=False)
    
    return summary + "DETAILED ERROR LOGS\n" + csv_data

def generate_json_report(df: pd.DataFrame) -> str:
    """Generate JSON report string from current dataframe"""
    if df.empty: return "{}"
    
    total = len(df)
    errors = len(df[df['log_level'] == 'ERROR']) if 'log_level' in df.columns else 0
    warnings = len(df[df['log_level'] == 'WARN']) if 'log_level' in df.columns else 0
    rate = (errors / total * 100) if total > 0 else 0
    
    report = {
        "report_meta": {
            "generated_at": str(datetime.now()),
            "total_logs": total,
            "total_errors": errors,
            "total_warnings": warnings,
            "error_rate_percent": round(rate, 2)
        },
        "top_errors": [],
        "logs": []
    }
    
    # Top Errors
    if 'message' in df.columns and 'log_level' in df.columns:
        err_df = df[df['log_level'] == 'ERROR']
        if not err_df.empty:
            top = err_df['message'].value_counts().head(5).to_dict()
            report["top_errors"] = [{"message": k, "count": v} for k, v in top.items()]
            
    # Logs (Limit to top 1000 for size safety or dump all? Let's dump all but be careful with memory)
    # Using records orientation
    cols = [c for c in ['timestamp', 'log_level', 'service', 'error_type', 'message'] if c in df.columns]
    
    # Convert timestamp to str for JSON serialization
    export_df = df[cols].copy()
    if 'timestamp' in export_df.columns:
        export_df['timestamp'] = export_df['timestamp'].astype(str)
    
    # Filter for ERRORS only
    if 'log_level' in export_df.columns:
        export_df = export_df[export_df['log_level'] == 'ERROR']
        
    report["logs"] = export_df.to_dict(orient="records")
    
    return json.dumps(report, indent=2)


# --- Main App ---

def render_filters(df: pd.DataFrame):
    with st.container():
        st.markdown('<div class="filter-panel">', unsafe_allow_html=True)
        # Reset Logic
        def reset_filters():
            st.session_state.filter_mode = "All Time"
            # Reset all level checkbox keys
            for key in st.session_state:
                if key.startswith("log_level_"):
                    st.session_state[key] = True

        if st.session_state.get("trigger_reset"):
            st.session_state.trigger_reset = False
            st.rerun()

        h_col1, h_col2 = st.columns([2, 1])
        with h_col1:
            st.markdown("""
<div class="filter-header-row" style="margin-bottom: 0;">
<div class="filter-main-title">Filters</div>
</div>
""", unsafe_allow_html=True)
        with h_col2:
            # Use standard size button, slightly more width in column
            if st.button("Reset", key="reset_btn", use_container_width=True):
                reset_filters()
                st.session_state.trigger_reset = True
                st.rerun()

        # Date Filter Mode
        st.markdown('<div class="filter-section-title">DATE RANGE</div>', unsafe_allow_html=True)
        # Default to All Time (index 0) to ensure all logs from different years are visible
        if "filter_mode" not in st.session_state:
            st.session_state.filter_mode = "All Time"
            
        filter_mode = st.radio(
            "Filter Mode", 
            ["All Time", "Custom Range"], 
            horizontal=True, 
            label_visibility="collapsed",
            key="filter_mode"
        )

        date_range = None
        if filter_mode == "Custom Range":
            # Determine default range based on data
            if not df.empty and 'timestamp' in df.columns:
                max_ts = df['timestamp'].max()
                default_end = max_ts.date()
                default_start = default_end - timedelta(days=7)
            else:
                default_end = datetime.now().date()
                default_start = default_end - timedelta(days=7)
                
            c_start, c_end = st.columns(2)
            with c_start:
                start_date = st.date_input("Start", value=default_start)
            with c_end:
                end_date = st.date_input("End", value=default_end)
            date_range = (start_date, end_date)
        
        st.markdown('<div class="filter-section-title">LOG LEVELS</div>', unsafe_allow_html=True)
        checks = {}
        
        # Dynamic Log Levels to ensure nothing is hidden
        unique_levels = ['INFO', 'WARN', 'ERROR', 'DEBUG']
        if not df.empty and 'log_level' in df.columns:
            # Union of standard levels and actual levels in data
            data_levels = df['log_level'].astype(str).dropna().unique().tolist()
            unique_levels = sorted(list(set(unique_levels + data_levels)))
        
        for lvl in unique_levels:
            # Default True for all to show everything by default
            key = f"log_level_{lvl}"
            if key not in st.session_state:
                st.session_state[key] = True
            checks[lvl] = st.checkbox(lvl, key=key)
            
        selected_levels = [lvl for lvl, checked in checks.items() if checked]
        
        # --- Report Export (Replaced Service Source) ---
        st.markdown('<div class="filter-section-title">REPORT EXPORT</div>', unsafe_allow_html=True)
        
        # We need the CURRENT filtered data for the report, but render_filters happens BEFORE filtering in main()
        # So we can't pass the fully filtered DF here easily without circular dependency.
        # Design Choice: The download buttons will trigger a re-run or we accept that we might need to pass the df *into* render_filters 
        # (which we do: 'df' arg is raw data).
        # But wait, user wants to download the ANALYTICS report, likely on the FILTERED data.
        # If we place buttons here, we only have 'df' (raw). 
        # Ideally, we should move these buttons, OR we duplicate the logic, OR we just export the RAW (or partially filtered) data available here?
        # Better UX: Export what I see.
        # BUT: streamlit buttons rerun the script.
        # Let's keep it simple: We will use the 'df' passed in (which is currently RAW in main call).
        # Actually, let's fix the logic in main to pass filtered_df back? No, that's hard.
        # We'll just generate report based on the RAW data loaded (or if we want to support filters, we need to apply them here too).
        # To avoid code duplication, we'll just export the FULL dataset for now as "Analytical Report" often implies full analysis.
        # OR we can apply the local filters (date/level) right here inside render_filters simply for the export?
        # Let's just pass `df` (raw) for now, as re-implementing filter logic inside the view is messy. 
        # Users can filter in excel/json. 
        # UPDATE: User request says "must generate analytics reports... covering summaries".
        # Let's generate based on 'df' (raw) provided to this function.
        
        csv_data = generate_csv_report(df)
        json_data = generate_json_report(df)
        
        c_csv, c_json = st.columns(2)
        with c_csv:
            st.download_button(
                label="CSV",
                data=csv_data,
                file_name=f"analytics_report_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with c_json:
            st.download_button(
                label="JSON",
                data=json_data,
                file_name=f"analytics_report_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True
            )
        
        st.markdown('<div class="filter-section-title">ACTIONS</div>', unsafe_allow_html=True)
        
        if st.button("Alert History", use_container_width=True):
            start, end = None, None
            top_errors = []
            
            # Logic to calculate Top Frequent Errors for the selected range/mode
            # We must duplicate some logic because main() hasn't processed filtered_df yet
            temp_df = df.copy()
            
            try:
                if date_range:
                    start, end = date_range
                    s_ts = pd.Timestamp(start)
                    e_ts = pd.Timestamp(end) + timedelta(days=1) - timedelta(seconds=1)
                    if 'timestamp' in temp_df.columns:
                        temp_df = temp_df[(temp_df['timestamp'] >= s_ts) & (temp_df['timestamp'] <= e_ts)]
                
                # Force a focused alert check on this specific view
                alerts.check_alerts(temp_df, force=True)

                # Extract top errors
                if not temp_df.empty and 'message' in temp_df.columns and 'log_level' in temp_df.columns:
                     err_df_temp = temp_df[temp_df['log_level'] == 'ERROR']
                     if not err_df_temp.empty:
                         # Get top 5 messages
                         top_errors = err_df_temp['message'].value_counts().head(5).index.tolist()

                # If we are looking for specific errors, we ignore the date range for the ALERT SEARCH
                if top_errors:
                    view_alert_history(None, None, top_errors)
                else:
                    view_alert_history(start, end, top_errors)
            except Exception as e:
                st.error(f"Error accessing alert history: {e}")

        st.markdown('</div>', unsafe_allow_html=True)

        return date_range, selected_levels


def main():
    # Authentication & Session Management
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    
    if "page" not in st.session_state:
        st.session_state.page = "dashboard"
    
    auth.init_db()

    if not st.session_state.logged_in:
        login_page()
        st.stop()
    
    # Sidebar: User Profile & Actions
    with st.sidebar:
        st.markdown(f"""
        <div style="padding: 1rem 0; text-align: center;">
            <div style="width: 64px; height: 64px; background: #0D9488; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; margin: 0 auto 12px auto;">
                {st.session_state.get('username', 'U')[0].upper()}
            </div>
            <h3 style="margin: 0; color: #F8FAFC;">{st.session_state.get('username', 'User')}</h3>
            <p style="margin: 0; color: #94A3B8; font-size: 0.8rem;">Administrator</p>
        </div>
        <hr style="border-color: #334155;">
        """, unsafe_allow_html=True)
        
        st.button("Logout", on_click=logout, type="secondary", use_container_width=True)

    # --- Navigation Logic ---
    if st.session_state.page == "settings":
        render_settings()
    else:
        # --- Dashboard View ---
        
        # Header
        # Using columns to allow interactive buttons
        h_col_title, h_col_actions = st.columns([6, 1])
        
        with h_col_title:
             st.markdown(f"""
            <div class="header-container" style="border-bottom: none; margin-bottom: 0;">
            <div class="app-title-box">
            <div class="app-icon">⚡</div>
            <div>
            <h1 class="app-title">Log Analytics Dashboard</h1>
            <p class="app-subtitle">Distributed Log Processing System</p>
            </div>
            </div>
            </div>
            """, unsafe_allow_html=True)
            
        with h_col_actions:
            # Custom styled buttons for actions using Streamlit columns
            # We use a little CSS hack in style.css to make these look good or just standard buttons
            ac1, ac2, ac3 = st.columns(3)
            with ac2:
                 if st.button("⚙️", key="nav_settings", help="Settings"):
                     st.session_state.page = "settings"
                     st.rerun()
            with ac3:
                 st.button("👤", key="nav_profile", help="Profile")


        st.markdown('<hr style="margin-top: -10px; margin-bottom: 24px; border-color: #E2E8F0;">', unsafe_allow_html=True)


        # Layout: Main Content (3.5) vs Filters (1)
        col_main, col_filters = st.columns([3.5, 1])
    
        # -- Data Processing --
        df = load_raw_data_v2()
    
        # Initialize and Check Alerts
        alerts.init_db()
        user_email = st.session_state.get('user_email')
        new_alerts = alerts.check_alerts(df, target_email=user_email)
        if new_alerts:
            for alert in new_alerts:
                st.toast(f"⚠️ {alert['message']}")
        
        with col_filters:
            time_range, selected_levels = render_filters(df)
            search_query = "All"
        
        # Apply Filters
        filtered_df = filter_data(df, time_range, search_query, selected_levels, "All Services")
    
        
        # KPIs
        def calculate_metrics(data_df):
            if data_df.empty: return 0, 0, 0, 0
            total = len(data_df)
            errs = len(data_df[data_df['log_level'] == 'ERROR']) if 'log_level' in data_df.columns else 0
            warns = len(data_df[data_df['log_level'] == 'WARN']) if 'log_level' in data_df.columns else 0
            rate = (errs / total * 100) if total > 0 else 0
            return total, errs, warns, rate
    
        # 1. Current Period Metrics
        curr_total, curr_err, curr_warn, curr_rate = calculate_metrics(filtered_df)
    
        # 2. Previous Period Metrics (Trend)
        prev_total, prev_err, prev_warn, prev_rate = 0, 0, 0, 0
        has_trend = False
        
        # Trend calculation disabled per user request (incorrect values in Custom Range)
        # if time_range and len(time_range) == 2:
        #     start_date, end_date = time_range
        #     # Calculate previous period
        #     duration = end_date - start_date
        #     prev_end = start_date - timedelta(days=1)
        #     prev_start = prev_end - duration
        #     prev_range = (prev_start, prev_end)
        #     
        #     # Filter for previous period
        #     prev_df = filter_data(df, prev_range, search_query, selected_levels, "All Services")
        #     prev_total, prev_err, prev_warn, prev_rate = calculate_metrics(prev_df)
        #     has_trend = True
    
    
        def format_trend(curr, prev, is_rate=False):
            if not has_trend or prev == 0:
                return "", ""
            
            diff = curr - prev
            if is_rate:
                 # For rate difference, just show absolute change in percentage points?
                 # Or relative? Let's do absolute diff for rate (e.g. +1.2%)
                 pass
                 
            pct = (diff / prev * 100)        
            arrow = "↗" if diff > 0 else "↘" if diff < 0 else "−"
            sign = "+" if diff > 0 else ""
            return arrow, f"{sign}{pct:.0f}%"
    
        # Calculate trends
        t1_arrow, t1_val = format_trend(curr_total, prev_total)
        t2_arrow, t2_val = format_trend(curr_err, prev_err)
        t3_arrow, t3_val = format_trend(curr_warn, prev_warn)
        t4_arrow, t4_val = format_trend(curr_rate, prev_rate, is_rate=True)
    
        with col_main:
            # KPI Row
            k1, k2, k3, k4 = st.columns(4)
            with k1: render_kpi("Total Logs", f"{curr_total:,}", "logs", "#0D9488", "📝", t1_arrow, t1_val) # Primary Teal
            with k2: render_kpi("Total Errors", f"{curr_err:,}", "errs", "#EF4444", "🚨", t2_arrow, t2_val) # Red
            with k3: render_kpi("Warnings", f"{curr_warn:,}", "warns", "#EAB308", "⚠️", t3_arrow, t3_val) # Amber
            with k4: render_kpi("Error Rate", f"{curr_rate:.2f}%", "rate", "#6366F1", "📉", t4_arrow, t4_val) # Indigo
    
            st.markdown("<br>", unsafe_allow_html=True)
    
            # Charts Row
            c1, c2 = st.columns([2, 1])
            
            with c1:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                # Header with controls
                h_col1, h_col2 = st.columns([3, 1])
                with h_col1:
                    st.markdown("""
    <div class="chart-header" style="margin-bottom: 0;">
    <div class="chart-title">Error Trends</div>
    </div>
    """, unsafe_allow_html=True)
                with h_col2:
                    # Granularity selector
                    default_index = 1
                    if not filtered_df.empty and 'timestamp' in filtered_df.columns:
                         try:
                             days_diff = (filtered_df['timestamp'].max() - filtered_df['timestamp'].min()).days
                             if days_diff > 30:
                                 default_index = 2
                         except: pass
                    
                    granularity = st.selectbox(
                        "Granularity", 
                        ["Minute", "Hour", "Day", "Week", "Month"], 
                        index=default_index,
                        label_visibility="collapsed"
                    )
                
                # Map friendly names to pandas offsets (Fixing 'M' deprecation)
                offset_map = { "Minute": "T", "Hour": "h", "Day": "D", "Week": "W", "Month": "ME" }
                resample_rule = offset_map.get(granularity, "h")
    
                # Trend Chart
                if not filtered_df.empty and 'timestamp' in filtered_df.columns:
                    # Prepare Data
                    error_data = pd.DataFrame()
                    warning_data = pd.DataFrame()
                    
                    # Errors
                    err_df = filtered_df[filtered_df['log_level'] == 'ERROR'].copy()
                    err_df = err_df.dropna(subset=['timestamp']) # Ensure valid time for chart
                    if not err_df.empty:
                        error_data = err_df.set_index('timestamp').resample(resample_rule).size().reset_index(name='count')
                        error_data = error_data[error_data['count'] > 0]
                    
                    # Warnings
                    
                    # Warnings
                    warn_df = filtered_df[filtered_df['log_level'] == 'WARN'].copy()
                    warn_df = warn_df.dropna(subset=['timestamp']) # Ensure valid time for chart
                    if not warn_df.empty:
                        warning_data = warn_df.set_index('timestamp').resample(resample_rule).size().reset_index(name='count')
                        # Filter out zero values
                        warning_data = warning_data[warning_data['count'] > 0]
    
                    if not error_data.empty or not warning_data.empty:
                        fig = go.Figure()
    
                        # Add Warnings Trace (Amber)
                        if not warning_data.empty:
                            fig.add_trace(go.Scatter(
                                x=warning_data['timestamp'], 
                                y=warning_data['count'],
                                name='Warnings',
                                mode='lines+markers',
                                line=dict(color='#F59E0B', width=2, shape='linear'), # Linear prevents negative interpolation overshoot
                                marker=dict(size=8, color='#F59E0B', symbol='circle'),
                                fill='tozeroy',
                                fillcolor='rgba(245, 158, 11, 0.1)',
                                hovertemplate='<b>%{x}</b><br>Warnings: %{y}<extra></extra>'
                            ))
    
                        # Add Errors Trace (Red) - On top
                        if not error_data.empty:
                            fig.add_trace(go.Scatter(
                                x=error_data['timestamp'], 
                                y=error_data['count'],
                                name='Errors',
                                mode='lines+markers',
                                line=dict(color='#EF4444', width=3, shape='linear'), # Linear prevents negative interpolation overshoot
                                marker=dict(size=8, color='#EF4444', symbol='circle'),
                                fill='tozeroy',
                                fillcolor='rgba(239, 68, 68, 0.15)',
                                hovertemplate='<b>%{x}</b><br>Errors: %{y}<extra></extra>'
                            ))
    
                        fig.update_layout(
                            title=dict(
                                text="Error & Warning Trends",
                                font=dict(size=14, color='#1E293B'),
                                x=0
                            ),
                            legend=dict(
                                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
                            ),
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            margin=dict(l=0, r=0, t=40, b=0),
                            xaxis=dict(
                                showgrid=True, 
                                gridcolor='#F1F5F9', 
                                title=None, 
                                tickfont=dict(color='#94A3B8')
                            ),
                            yaxis=dict(
                                showgrid=True, 
                                gridcolor='#F8FAFC', 
                                title=None, 
                                tickfont=dict(color='#94A3B8')
                            ),
                            height=320,
                            hovermode="x unified"
                        )
                        st.plotly_chart(fig, config={'displayModeBar': False}, width="stretch")
                    else:
                        st.info("No data for selected period")
                else:
                     # Empty state instead of mock data
                     st.markdown('<div style="height:280px; display:flex; align-items:center; justify-content:center; color:#94A3B8;">No Data Available</div>', unsafe_allow_html=True)
    
                st.markdown('</div>', unsafe_allow_html=True)
                
            with c2:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.markdown('<div class="chart-title" style="margin-bottom:20px;">Distribution</div>', unsafe_allow_html=True)
                
                # Donut Chart for Levels
                levels_data = pd.DataFrame({
                    'Level': ['INFO', 'WARN', 'ERROR'],
                    'Count': [curr_total - curr_err - curr_warn, curr_warn, curr_err]
                })
                colors = ['#0D9488', '#EAB308', '#EF4444'] # Teal, Amber, Red
                
                if curr_total > 0:
                    fig_donut = go.Figure(data=[go.Pie(
                        labels=levels_data['Level'],
                        values=levels_data['Count'],
                        hole=.6,
                        marker=dict(colors=colors),
                        textinfo='none' # Hide text on chart, rely on hover or legend
                    )])
                    fig_donut.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        margin=dict(l=0, r=0, t=0, b=0),
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                        height=280
                    )
                    st.plotly_chart(fig_donut, config={'displayModeBar': False}, width="stretch")
                else:
                     st.markdown('<div style="height:280px; display:flex; align-items:center; justify-content:center; color:#94A3B8;">No Data</div>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
    
            # Bottom Section: Top Errors
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            st.markdown('<div class="chart-title" style="margin-bottom:20px;">Top Frequent Errors</div>', unsafe_allow_html=True)
            
            if not filtered_df.empty and 'message' in filtered_df.columns:
                # Calculate top errors dynamically
                error_data = filtered_df[filtered_df['log_level'] == 'ERROR']
                if not error_data.empty:
                     error_counts = error_data['message'].value_counts().head(5)
                     max_val = error_counts.max()
                     
                     for idx, (message, count) in enumerate(error_counts.items()):
                         # Grid Layout for Custom Card
                         # Use columns to mimic the card structure since we can't put arbitrary HTML containers around streamlit widgets easily
                         # We will use styles to make the container LOOK like a card.
                         
                         with st.container():
                             # Custom HTML wrapper for visual card style is hard with interactive buttons inside.
                             # Instead, we rely on the clean look of the columns and a bottom separator.
                             
                             c1, c2, c3 = st.columns([0.8, 4, 1])
                             
                             with c1:
                                 # Badge
                                 st.markdown('<div class="sev-badge error">CRITICAL</div>', unsafe_allow_html=True)
                                 
                             with c2:
                                 # Message & Progress
                                 pct = (count / max_val * 100) if max_val > 0 else 0
                                 st.markdown(f'''
                                     <div class="err-msg-box" title="{message}">{message}</div>
                                     <div class="err-meta">Last seen: Just now &bull; Service: Auth</div>
                                     <div class="err-bar-bg"><div class="err-bar-fill" style="width: {pct}%; background-color: #EF4444;"></div></div>
                                 ''', unsafe_allow_html=True)
                                 
                             with c3:
                                 # Count & Action
                                 st.markdown(f'<div style="text-align:right; font-weight:700; font-size:1.1rem; color:#1E293B;">{count}</div>', unsafe_allow_html=True)
                                 if st.button("View", key=f"btn_err_{idx}", type="secondary", use_container_width=True):
                                     # Get examples for this error
                                     examples = error_data[error_data['message'] == message]
                                     view_error_details(message, count, examples)
                             
                             st.markdown('<div style="height: 12px;"></div>', unsafe_allow_html=True) # Spacer
    
                else:
                    st.info("No errors found in the current selection.")
            else:
                 st.markdown('<div style="color:#94A3B8; padding: 20px 0;">No data to analyze.</div>', unsafe_allow_html=True)
                
            st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()


