import sqlite3
import pandas as pd
from datetime import datetime
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "alerts.db")

def init_db():
    """Initialize the alerts database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            alert_type TEXT,
            message TEXT,
            severity TEXT,
            details TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_alert(alert_type, message, severity, details="", html_body=None, target_email=None):
    """Save an alert to the database and send an email."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO alert_history (timestamp, alert_type, message, severity, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), alert_type, message, severity, details))
        conn.commit()
        conn.close()

        # Email Trigger
        if not html_body:
            # Generate default HTML if not provided
            metrics = {"Message": message, "Severity": severity}
            html_body = create_html_body(f"Alert: {alert_type}", message, metrics, details)
            
        send_email_alert(f"{alert_type} ({severity})", f"{message}\n\n{details}", html_body=html_body, target_email=target_email)

    except Exception as e:
        print(f"Failed to save alert: {e}")

def get_alerts(limit=100, start_date=None, end_date=None):
    """Retrieve alert history with optional date filtering."""
    try:
        conn = sqlite3.connect(DB_PATH)
        query = "SELECT * FROM alert_history"
        params = []
        conditions = []
        
        if start_date:
            conditions.append("timestamp >= ?")
            # Ensure start_date is string or datetime compatible with DB format (ISO)
            params.append(pd.Timestamp(start_date).isoformat())
            
        if end_date:
            conditions.append("timestamp <= ?")
            # End of day
            end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            params.append(end_ts.isoformat())
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += f" ORDER BY id DESC LIMIT {limit}"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        print(f"Failed to fetch alerts: {e}")
        return pd.DataFrame()

def check_alerts(df: pd.DataFrame, force=False, target_email=None):
    """
    Analyze dataframe for conditions to trigger alerts.
    Returns a list of triggered alerts (dicts).
    """
    if df.empty: return []
    
    triggered_alerts = []
    
    # Common Data: Top 5 Errors for Details
    top_errors_str = ""
    if 'message' in df.columns and 'log_level' in df.columns:
        err_df = df[df['log_level'] == 'ERROR']
        if not err_df.empty:
            top = err_df['message'].value_counts().head(20)
            top_errors_str = "Top Errors:\n" + "\n".join([f"- {msg} ({count})" for msg, count in top.items()])

    # --- Rule 1: High Error Rate (> 10%) ---
    total = len(df)
    errors = len(df[df['log_level'] == 'ERROR']) if 'log_level' in df.columns else 0
    rate = (errors / total * 100) if total > 0 else 0
    
    # Deduplication / Cooldown Logic
    is_in_cooldown = False
    if not force:
        last_alerts = get_alerts(limit=1)
        last_alert_time = datetime.min
        if not last_alerts.empty:
             try:
                 last_ts_str = last_alerts.iloc[0]['timestamp']
                 last_alert_time = datetime.fromisoformat(last_ts_str)
             except: pass
             
        time_since_last = (datetime.now() - last_alert_time).total_seconds()
        is_in_cooldown = time_since_last < 3600 
    
    if rate > 10 and not is_in_cooldown:
        msg = f"High Error Rate Detected: {rate:.2f}%"
        # Combine stats and top errors in details
        details = f"Total Logs: {total}\nError Count: {errors}\n{top_errors_str}"
        
        metrics = {"Total Logs": total, "Error Count": errors, "Error Rate": f"{rate:.2f}%"}
        html = create_html_body("High Error Rate Detected", msg, metrics, top_errors_str)
        
        save_alert("High Error Rate", msg, "Critical", details, html_body=html, target_email=target_email)
        triggered_alerts.append({"message": msg, "severity": "Critical"})
        
    # --- Rule 2: Critical Log Rate (> 10% of total logs are CRITICAL) ---
    # User Request: "Critical Rate > 10%"
    # Assuming this means log_level == 'CRITICAL'
    criticals = len(df[df['log_level'] == 'CRITICAL']) if 'log_level' in df.columns else 0
    crit_rate = (criticals / total * 100) if total > 0 else 0
    
    if crit_rate > 10 and not is_in_cooldown:
         msg = f"Critical Log Rate Exceeds 10%: {crit_rate:.2f}%"
         details = f"Total: {total}, Criticals: {criticals}\n{top_errors_str}"
         
         metrics = {"Total Logs": total, "Critical Logs": criticals, "Critical Rate": f"{crit_rate:.2f}%"}
         html = create_html_body("Critical Log Spike", msg, metrics, top_errors_str)
         
         save_alert("High Critical Rate", msg, "Critical", details, html_body=html, target_email=target_email)
         triggered_alerts.append({"message": msg, "severity": "Critical"})

    # --- Rule 3: Frequent Error Patterns (> 5 occurrences) ---
    if 'message' in df.columns and 'log_level' in df.columns:
        err_df = df[df['log_level'] == 'ERROR'].copy()
        if not err_df.empty:
            # Existing Rule: > 5 occurrences (Batch)
            error_counts = err_df['message'].value_counts()
            freq_errors = error_counts[error_counts > 5]
            
            if not freq_errors.empty and not is_in_cooldown:
                count_of_patterns = len(freq_errors)
                top_pattern = freq_errors.index[0]
                top_count = freq_errors.iloc[0]
                
                msg = f"Frequent Error Detected: {top_pattern} ({top_count} times)"
                if count_of_patterns > 1:
                    msg = f"Multiple Frequent Errors Detected ({count_of_patterns} types)"

                details_lines = ["Errors occurring > 5 times:"]
                for err_msg, count in freq_errors.items():
                    details_lines.append(f"- {err_msg}: {count} occurrences")
                details = "\n".join(details_lines)
                
                metrics = {
                    "Unique Frequent Errors": count_of_patterns,
                    "Top Error Count": top_count,
                    "Total Errors in Batch": errors
                }
                
                html = create_html_body("Frequent Error Patterns Detected", msg, metrics, details)
                save_alert("Frequent Error Pattern", msg, "Critical", details, html_body=html, target_email=target_email)
                triggered_alerts.append({"message": msg, "severity": "Critical"})

            # --- New Rule: > 20 occurrences in 1 Hour ---
            # Ensure valid timestamp index
            if 'timestamp' in err_df.columns:
                 # Clean timestamps
                 err_df['timestamp'] = pd.to_datetime(err_df['timestamp'], errors='coerce')
                 err_df = err_df.dropna(subset=['timestamp'])
                 
                 if not err_df.empty:
                     # Identify messages with > 20 occurrences *total* first to filter
                     potential_msgs = error_counts[error_counts > 20].index.tolist()
                     
                     high_freq_triggered = False
                     for target_msg in potential_msgs:
                         if high_freq_triggered: break # Avoid spamming multiple alerts for same burst
                         
                         sub_df = err_df[err_df['message'] == target_msg].sort_values('timestamp')
                         # Rolling count in 1H window
                         # We set index to timestamp, then roll
                         # result is count of events in the window ending at index time
                         rolling_counts = sub_df.set_index('timestamp').rolling('1h').count()
                         
                         # rolling_counts will have column 'message' (and others) with counts
                         # Check if any window has count > 20
                         if not rolling_counts.empty and rolling_counts['message'].max() > 20:
                             max_val = int(rolling_counts['message'].max())
                             
                             alert_msg = f"High Velocity Error: {target_msg} (>20 in 1h)"
                             det_msg = f"Error occurred {max_val} times in a single hour window."
                             
                             if not is_in_cooldown:
                                 metrics_hf = {"Max Hourly Rate": max_val, "Error": target_msg}
                                 html_hf = create_html_body("High Velocity Error Detected", alert_msg, metrics_hf, det_msg)
                                 save_alert("High Velocity Error", alert_msg, "Critical", det_msg, html_body=html_hf, target_email=target_email)
                                 triggered_alerts.append({"message": alert_msg, "severity": "Critical"})
                                 high_freq_triggered = True

    # If forced (Manual Check), ensure we record the context even if thresholds aren't met
    if force and not triggered_alerts:
        msg = "Manual Alert History Check"
        # details = f"Total: {total}, Errors: {errors}\n{top_errors_str}"
        # Removed save_alert to prevent database clutter for manual checks
        triggered_alerts.append({"message": msg, "severity": "Info"})

    return triggered_alerts

# --- Email Sending Logic ---
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
try:
    from . import email_config
except ImportError:
    import email_config

def create_html_body(title, message, metrics, top_errors_str):
    """
    Create a professional HTML email body.
    """
    # Parse top errors from string back to list if needed, or just format the string
    # Expected top_errors_str format: "Top Errors:\n- Msg (Count)..."
    # Let's clean it up for HTML
    error_list_html = ""
    if top_errors_str:
        lines = top_errors_str.split('\n')
        # Skip header "Top Errors:" if present
        items = [l for l in lines if l.strip().startswith('-')]
        if items:
            error_list_html = "<ul>" + "".join([f"<li>{item[2:]}</li>" for item in items]) + "</ul>"
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }}
            .header {{ background-color: #DC2626; color: white; padding: 20px; text-align: center; }}
            .header.info {{ background-color: #2563EB; }}
            .content {{ padding: 20px; background-color: #F9FAFB; }}
            .metrics-table {{ width: 100%; margin-bottom: 20px; border-collapse: collapse; }}
            .metrics-table th, .metrics-table td {{ padding: 10px; border-bottom: 1px solid #eee; text-align: left; }}
            .metrics-table th {{ background-color: #f3f3f3; color: #666; font-size: 0.85em; text-transform: uppercase; }}
            .footer {{ background-color: #f1f1f1; padding: 15px; text-align: center; font-size: 0.8em; color: #666; }}
            h2 {{ margin-top: 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{title}</h1>
            </div>
            <div class="content">
                <h2>{message}</h2>
                <table class="metrics-table">
                    <tr><th>Metric</th><th>Value</th></tr>
                    {''.join([f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in metrics.items()])}
                </table>
                
                <h3>Top Frequent Errors</h3>
                {error_list_html if error_list_html else "<p>No specific error patterns detected.</p>"}
                
                <p style="margin-top: 20px;">
                    <a href="http://localhost:8501" style="background-color: #DC2626; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">View Dashboard</a>
                </p>
            </div>
            <div class="footer">
                <p>This is an automated alert from the Log Processing System.</p>
                <p>Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_email_alert(subject, body, html_body=None, target_email=None):
    """Send an email alert using the configured SMTP server."""
    try:
        sender_email = email_config.SENDER_EMAIL
        sender_password = email_config.SENDER_PASSWORD
        receiver_emails = [target_email] if target_email else email_config.RECEIVER_EMAILS
        smtp_server = email_config.SMTP_SERVER
        smtp_port = email_config.SMTP_PORT

        msg = MIMEMultipart('alternative')
        msg['From'] = sender_email
        msg['To'] = ", ".join(receiver_emails)
        msg['Subject'] = f"[ALERT] {subject}"

        # Attach Plain Text
        part1 = MIMEText(body, 'plain')
        msg.attach(part1)
        
        # Attach HTML if available
        if html_body:
            part2 = MIMEText(html_body, 'html')
            msg.attach(part2)

        # Connect to SMTP Server
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        
        # Send Email
        server.sendmail(sender_email, receiver_emails, msg.as_string())
        server.quit()
        
        print(f"Email alert sent to {receiver_emails}")
        return True
    except Exception as e:
        print(f"Failed to send email alert: {e}")
        return False

