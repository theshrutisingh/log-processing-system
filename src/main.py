"""
Main Processing Pipeline
Orchestrates the entire log processing workflow
"""

import logging
import sys
import os

# Get project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)  # Change to project root for relative paths

# Add src to path
sys.path.insert(0, project_root)

from src.spark.spark_session import create_spark_session, load_config
from src.spark.ingest_logs import ingest_logs
from src.spark.parse_logs import parse_logs
from src.spark.analytics import run_all_analytics, generate_summary_statistics
from src.spark.alerts import check_alerts
from src.spark.export_reports import export_all_reports


# Force UTF-8 encoding for stdout/stderr to satisfy Windows console
import io
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main processing pipeline"""
    try:
        logger.info("=" * 60)
        logger.info("Starting Distributed Log Processing System")
        logger.info("=" * 60)
        
        # Load configuration
        config = load_config()
        
        # Create Spark session
        logger.info("Phase 1: Setting up Spark environment...")
        spark = create_spark_session(config)
        
        # Ingest logs
        logger.info("Phase 2: Ingesting logs...")
        df_raw = ingest_logs()
        
        # Parse logs
        logger.info("Phase 3: Parsing and normalizing logs...")
        df_parsed = parse_logs(df_raw)
        
        # Run analytics
        logger.info("Phase 4: Running analytics...")
        analytics_results = run_all_analytics(df_parsed, config)
        
        # Generate summary statistics
        summary = generate_summary_statistics(df_parsed)
        logger.info(f"Summary Statistics: {summary}")
        
        # Check alerts
        logger.info("Phase 5: Checking alerts...")
        alert_manager = check_alerts(df_parsed)
        
        # Export reports
        logger.info("Phase 6: Exporting reports...")
        export_all_reports(analytics_results, df_parsed, config_path="config/config.yaml")
        
        # Export summary stats for dashboard
        from src.spark.export_reports import export_summary_stats
        export_summary_stats(summary, config_path="config/config.yaml")
        
        logger.info("=" * 60)
        logger.info("Processing completed successfully!")
        logger.info("=" * 60)
        logger.info("Reports are available in:")
        logger.info(f"  - CSV: {config['paths']['reports_csv_dir']}")
        logger.info(f"  - JSON: {config['paths']['reports_json_dir']}")
        logger.info("=" * 60)
        
        # Stop Spark session
        spark.stop()
        
    except Exception as e:
        logger.error(f"Error in main pipeline: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

