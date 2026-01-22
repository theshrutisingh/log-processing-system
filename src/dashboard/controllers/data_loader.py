import streamlit as st
import pandas as pd
import os
import glob
from datetime import datetime, timedelta

@st.cache_data
def load_raw_data_v2(
    data_dir: str = os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
        "logs.parquet"
    )
) -> pd.DataFrame:
    """Load processed log data"""
    try:
        # Try Parquet first
        parquet_path = data_dir
        if os.path.exists(parquet_path):
            df = pd.DataFrame()
            if os.path.isfile(parquet_path) and parquet_path.endswith('.parquet'):
                df = pd.read_parquet(parquet_path)
            elif os.path.isdir(parquet_path):
                parquet_files = glob.glob(os.path.join(parquet_path, "*.parquet"))
                if parquet_files:
                    df_list = []
                    for f in parquet_files:
                        try:
                            # Safe read per file
                            temp_df = pd.read_parquet(f)
                            if not temp_df.empty:
                                df_list.append(temp_df)
                        except Exception as e:
                            # Log and continue - do not crash dashboard
                            print(f"Warning: Failed to load parquet file {f}: {e}")
                            continue
                            
                    if df_list:
                        df = pd.concat(df_list, ignore_index=True)
            
            if not df.empty:
                if 'timestamp' in df.columns:
                    # 1. Primary Parse: Mixed Format
                    df['temp_ts'] = pd.to_datetime(df['timestamp'], format='mixed', dayfirst=False, errors='coerce')
                    
                    # 2. Secondary Parse: Unix Epoch (for scientific notation strings like '1.13E9')
                    mask = df['temp_ts'].isna() & df['timestamp'].notna()
                    if mask.any():
                        try:
                            unix_ts = pd.to_numeric(df.loc[mask, 'timestamp'], errors='coerce')
                            df.loc[mask, 'temp_ts'] = pd.to_datetime(unix_ts, unit='s', errors='coerce')
                        except Exception: pass
                    
                    df['timestamp'] = df['temp_ts']
                    df.drop(columns=['temp_ts'], inplace=True)

                # Normalize Log Levels
                if 'level' in df.columns: df.rename(columns={'level': 'log_level'}, inplace=True)
                if 'log_level' not in df.columns: df['log_level'] = "UNKNOWN"
                df['log_level'] = df['log_level'].fillna("UNKNOWN").astype(str).str.upper()
                df['log_level'] = df['log_level'].replace({'WARNING': 'WARN', 'COMBO': 'INFO'})

                if 'content' in df.columns: df.rename(columns={'content': 'message'}, inplace=True)
                if 'eventtemplate' in df.columns: df.rename(columns={'eventtemplate': 'error_type'}, inplace=True)
                
                if 'timestamp' in df.columns:
                    # df = df.dropna(subset=['timestamp']) # Allow NaT for Total Count
                    return df.sort_values('timestamp', ascending=False)
                return df
        
        # Fallback to CSV
        csv_dir = "data/raw_logs"
        if not os.path.exists(csv_dir):
            return pd.DataFrame()
            
        all_files = glob.glob(os.path.join(csv_dir, "*.csv"))
        if not all_files:
            return pd.DataFrame()
            
        df_list = []
        for filename in all_files:
            try:
                df = pd.read_csv(filename, header=0, quotechar='"')
                df.columns = df.columns.str.lower()
                # Remove duplicate columns to prevent index errors
                df = df.loc[:, ~df.columns.duplicated()]
                
                if 'timestamp' not in df.columns:
                    # Linux Logs: Month, Date, Time (No Year)
                    if 'month' in df.columns and 'date' in df.columns and 'time' in df.columns:
                        try:
                            # Construct string: "2025 Jun 14 15:16:01"
                            # Default year 2025
                            current_year = "2025"
                            combined_linux = current_year + " " + df['month'].astype(str) + " " + df['date'].astype(str) + " " + df['time'].astype(str)
                            # Parse
                            df['timestamp'] = pd.to_datetime(combined_linux, format='%Y %b %d %H:%M:%S', errors='coerce')
                        except Exception: pass

                    # Spark/Windows Logs: Date, Time
                    if 'timestamp' not in df.columns and 'date' in df.columns and 'time' in df.columns:
                         try:
                            # Normalize columns to string and strip whitespace
                            d_str = df['date'].astype(str).str.strip().str.replace('[', '').str.replace(']', '')
                            t_str = df['time'].astype(str).str.strip().str.replace('[', '').str.replace(']', '').str.replace(',', '.') 
                            combined = d_str + ' ' + t_str
                            
                            # Try parsing with multiple formats
                            # 1. Standard with milliseconds: 2016-09-28 04:30:30.123
                            df['timestamp'] = pd.to_datetime(combined, format='%Y-%m-%d %H:%M:%S.%f', errors='coerce')
                            
                            # 2. Standard without milliseconds: 2016-09-28 04:30:30
                            mask = df['timestamp'].isna()
                            if mask.any():
                                 df.loc[mask, 'timestamp'] = pd.to_datetime(combined[mask], format='%Y-%m-%d %H:%M:%S', errors='coerce')
                                 
                            # 3. Short Year with slashes: 17/06/09 20:10:40 (Spark)
                            mask = df['timestamp'].isna()
                            if mask.any():
                                 df.loc[mask, 'timestamp'] = pd.to_datetime(combined[mask], format='%y/%m/%d %H:%M:%S', errors='coerce')

                            # 4. Fallback to generic parser for any remaining (suppress warning if possible)
                            mask = df['timestamp'].isna()
                            if mask.any():
                                try:
                                    df.loc[mask, 'timestamp'] = pd.to_datetime(combined[mask], errors='coerce')
                                except: pass

                         except Exception as e: 
                             pass
                
                # Normalize Log Levels
                if 'level' in df.columns: 
                    df.rename(columns={'level': 'log_level'}, inplace=True)
                
                if 'log_level' not in df.columns:
                    df['log_level'] = "UNKNOWN"
                
                df['log_level'] = df['log_level'].fillna("UNKNOWN").astype(str).str.upper()
                df['log_level'] = df['log_level'].replace({'WARNING': 'WARN', 'COMBO': 'INFO'})

                if 'content' in df.columns: df.rename(columns={'content': 'message'}, inplace=True)
                if 'eventtemplate' in df.columns: df.rename(columns={'eventtemplate': 'error_type'}, inplace=True)
                
                if 'timestamp' in df.columns:
                    # Use robust parsing for mixed formats (handles newlogs.csv)
                    df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', dayfirst=False, errors='coerce')
                    df = df.dropna(subset=['timestamp'])
                    
                df_list.append(df)
            except Exception: 
                continue
                
        if not df_list: return pd.DataFrame()
        final_df = pd.concat(df_list, ignore_index=True)
        return final_df.sort_values('timestamp', ascending=False) if 'timestamp' in final_df.columns else final_df
    except Exception as e:
        return pd.DataFrame()

def filter_data(df: pd.DataFrame, date_range, search_query: str, selected_levels: list, service_source: str) -> pd.DataFrame:
    """Apply filters"""
    if df.empty: return df
    filtered_df = df.copy()
    
    # Time Range
    if date_range and len(date_range) == 2:
        start_date, end_date = date_range
        # Convert to datetime64[ns] to match df
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date) + timedelta(days=1) - timedelta(seconds=1)
        if 'timestamp' in filtered_df.columns:
            filtered_df = filtered_df[(filtered_df['timestamp'] >= start_ts) & (filtered_df['timestamp'] <= end_ts)]
        
    # Log Levels
    if 'log_level' in filtered_df.columns and selected_levels:
        # Filter if selected, if none selected imply ALL? Or None? Usually ALL if empty or check "All". 
        # But here we have explicit checkboxes.
        if selected_levels:
            # Case insensitive
            filtered_df = filtered_df[filtered_df['log_level'].astype(str).str.upper().isin(selected_levels)]
            
    # Search (now exact match via dropdown)
    if search_query and search_query != "All":
        # Check if we should filter by error_type or message
        # We assume if the user selected something, it came from the list generated in render_filters
        target_col = 'error_type' if 'error_type' in filtered_df.columns else 'message'
        
        if target_col in filtered_df.columns:
             filtered_df = filtered_df[filtered_df[target_col] == search_query]
        
    return filtered_df
