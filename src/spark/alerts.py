"""
Alert System Module
Implements configurable alerting based on thresholds
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from pyspark.sql import DataFrame
import sys
import os

# Handle imports for both direct execution and module import
try:
    from src.spark.spark_session import load_config
    from src.spark.analytics import compute_error_rate, compute_error_count
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.spark.spark_session import load_config
    from src.spark.analytics import compute_error_rate, compute_error_count

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlertManager:
    """Manages alert generation and history"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialize AlertManager with configuration
        
        Args:
            config_path: Path to configuration file
        """
        self.config = load_config(config_path)
        self.alert_config = self.config.get('alerts', {})
        self.alert_history: List[Dict] = []
        
        # Setup alert log file
        self.alert_log_file = "reports/alerts.log"
        import os
        os.makedirs("reports", exist_ok=True)
    
    def log_alert(self, alert_type: str, message: str, severity: str = "WARNING"):
        """
        Log alert to console and file
        
        Args:
            alert_type: Type of alert
            message: Alert message
            severity: Alert severity level
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alert_entry = {
            "timestamp": timestamp,
            "type": alert_type,
            "message": message,
            "severity": severity
        }
        
        self.alert_history.append(alert_entry)
        
        # Print to console
        alert_str = f"[{timestamp}] [{severity}] {alert_type}: {message}"
        logger.warning(alert_str)
        print(f"\n⚠️  ALERT: {alert_str}\n")
        
        # Write to file
        try:
            with open(self.alert_log_file, 'a') as f:
                f.write(f"{alert_str}\n")
        except Exception as e:
            logger.error(f"Error writing to alert log: {e}")

        # Send Email for Critical Alerts
        if severity == "CRITICAL":
            self.send_email_alert(alert_type, message, severity)

    def create_html_body(self, title, message, severity):
        """Create a professional HTML email body."""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }}
                .header {{ background-color: #DC2626; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #F9FAFB; }}
                .footer {{ background-color: #f1f1f1; padding: 15px; text-align: center; font-size: 0.8em; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{title}</h1>
                </div>
                <div class="content">
                    <h2>{message}</h2>
                    <p><strong>Severity:</strong> {severity}</p>
                    <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
                <div class="footer">
                    <p>Automated Alert from Spark Log Pipeline</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def send_email_alert(self, subject, body, severity):
        """Send an email alert using the configured SMTP server."""
        try:
            # Import here to avoid circular dependencies or path issues if config is missing
            try:
                from src.spark import email_config
            except ImportError:
                 # Fallback for direct execution
                 import email_config

            sender_email = email_config.SENDER_EMAIL
            sender_password = email_config.SENDER_PASSWORD
            receiver_emails = email_config.RECEIVER_EMAILS
            smtp_server = email_config.SMTP_SERVER
            smtp_port = email_config.SMTP_PORT

            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart('alternative')
            msg['From'] = sender_email
            msg['To'] = ", ".join(receiver_emails)
            msg['Subject'] = f"[PIPELINE ALERT] {subject}"

            # Plain text fallback
            part1 = MIMEText(f"{subject}\n\n{body}\n\nSeverity: {severity}", 'plain')
            msg.attach(part1)
            
            # HTML Body
            html_content = self.create_html_body(subject, body, severity)
            part2 = MIMEText(html_content, 'html')
            msg.attach(part2)

            # Connect to SMTP Server
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            
            # Send Email
            server.sendmail(sender_email, receiver_emails, msg.as_string())
            server.quit()
            
            print(f"📧 Email alert sent to {receiver_emails}")
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            print(f"❌ Failed to send email alert: {e}")
    
    def check_error_rate_alert(self, df: DataFrame) -> bool:
        """
        Check if error rate exceeds threshold
        
        Args:
            df: Parsed log DataFrame
            
        Returns:
            True if alert was triggered
        """
        threshold = self.alert_config.get('error_rate_threshold', 0.1)
        error_rate = compute_error_rate(df)
        
        if error_rate > threshold:
            self.log_alert(
                "HIGH_ERROR_RATE",
                f"Error rate {error_rate:.2%} exceeds threshold {threshold:.2%}",
                "CRITICAL"
            )
            return True
        return False
    
    def check_error_count_alert(self, df: DataFrame) -> bool:
        """
        Check if error count exceeds threshold
        
        Args:
            df: Parsed log DataFrame
            
        Returns:
            True if alert was triggered
        """
        threshold = self.alert_config.get('error_count_threshold', 100)
        error_count = compute_error_count(df)
        
        if error_count > threshold:
            self.log_alert(
                "HIGH_ERROR_COUNT",
                f"Total error count {error_count} exceeds threshold {threshold}",
                "CRITICAL"
            )
            return True
        return False
    
    def check_critical_errors_alert(self, df: DataFrame) -> bool:
        """
        Check if critical errors appear
        
        Args:
            df: Parsed log DataFrame
            
        Returns:
            True if alert was triggered
        """
        threshold = self.alert_config.get('critical_error_count', 5)
        
        from pyspark.sql.functions import col, count
        
        critical_errors = df.filter(
            (col("log_level") == "ERROR") & 
            (col("severity") >= 3)
        ).count()
        
        if critical_errors >= threshold:
            self.log_alert(
                "CRITICAL_ERRORS",
                f"Found {critical_errors} critical errors (threshold: {threshold})",
                "CRITICAL"
            )
            return True
        return False

    def check_frequent_errors_alert(self, df: DataFrame) -> bool:
        """
        Check for errors occurring > 5 times
        """
        from pyspark.sql.functions import col, count, desc
        
        # Filter for ERROR logs
        errors_df = df.filter(col("log_level") == "ERROR")
        
        # Group by message and count
        freq_errors = errors_df.groupBy("message").agg(count("*").alias("count")) \
                        .filter(col("count") > 5) \
                        .orderBy(desc("count"))
        
        # We need to collect to local list to check if empty and iterate
        # Use limit to avoid pulling too much data if massive
        top_freq = freq_errors.limit(10).collect()
        
        if top_freq:
            # Trigger Alert
            count_patterns = len(top_freq)
            top_msg = top_freq[0]['message']
            top_count = top_freq[0]['count']
            
            alert_msg = f"Frequent Error: {top_msg} ({top_count} times)"
            if count_patterns > 1:
                alert_msg = f"Multiple Frequent Errors Detected ({count_patterns} distinct types > 5 occ.)"
                
            # Construct details
            details = "Errors occurring > 5 times:\n"
            for row in top_freq:
                details += f"- {row['message']}: {row['count']}\n"
            
            # Log Alert (this triggers email)
            self.log_alert("FREQUENT_ERRORS", f"{alert_msg}\n\n{details}", "CRITICAL")
            return True
            
        return False
    
    def check_all_alerts(self, df: DataFrame) -> List[Dict]:
        """
        Run all alert checks
        
        Args:
            df: Parsed log DataFrame
            
        Returns:
            List of triggered alerts
        """
        logger.info("Running alert checks...")
        
        alerts_triggered = []
        
        # Check error rate
        if self.check_error_rate_alert(df):
            alerts_triggered.append({
                "type": "HIGH_ERROR_RATE",
                "timestamp": datetime.now().isoformat()
            })
        
        # Check error count
        if self.check_error_count_alert(df):
            alerts_triggered.append({
                "type": "HIGH_ERROR_COUNT",
                "timestamp": datetime.now().isoformat()
            })
        
        # Check critical errors
        if self.check_critical_errors_alert(df):
            alerts_triggered.append({
                "type": "CRITICAL_ERRORS",
                "timestamp": datetime.now().isoformat()
            })

        # Check frequent errors (> 5 times)
        if self.check_frequent_errors_alert(df):
            alerts_triggered.append({
                "type": "FREQUENT_ERRORS",
                "timestamp": datetime.now().isoformat()
            })
        
        if not alerts_triggered:
            logger.info("No alerts triggered. System is healthy.")
        
        return alerts_triggered
    
    def get_recent_alerts(self, limit: int = 20) -> List[Dict]:
        """
        Get recent alerts from history
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of recent alerts
        """
        return self.alert_history[-limit:]
    
    def get_alert_summary(self) -> Dict:
        """
        Get summary of alert history
        
        Returns:
            Dictionary with alert statistics
        """
        total_alerts = len(self.alert_history)
        
        alert_types = {}
        for alert in self.alert_history:
            alert_type = alert.get("type", "UNKNOWN")
            alert_types[alert_type] = alert_types.get(alert_type, 0) + 1
        
        return {
            "total_alerts": total_alerts,
            "alert_types": alert_types,
            "recent_alerts": self.get_recent_alerts(10)
        }


def check_alerts(df: DataFrame, config_path: str = "config/config.yaml") -> AlertManager:
    """
    Convenience function to check alerts
    
    Args:
        df: Parsed log DataFrame
        config_path: Path to configuration file
        
    Returns:
        AlertManager instance
    """
    alert_manager = AlertManager(config_path)
    alert_manager.check_all_alerts(df)
    return alert_manager


if __name__ == "__main__":
    from ingest_logs import ingest_logs
    from parse_logs import parse_logs
    
    from spark_session import get_spark_session
    
    spark = get_spark_session()
    df_raw = ingest_logs()
    df_parsed = parse_logs(df_raw)
    
    # Check alerts
    alert_manager = check_alerts(df_parsed)
    
    # Display alert summary
    summary = alert_manager.get_alert_summary()
    print(f"\nAlert Summary: {summary}")

