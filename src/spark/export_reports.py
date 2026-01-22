"""
Report Export Module
Exports analytics results to CSV and JSON using native PySpark write operations.
"""

import logging
from pyspark.sql import DataFrame
from typing import Dict
import os
import sys
import shutil

# Handle imports for both direct execution and module import
try:
    from src.spark.spark_session import load_config
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.spark.spark_session import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def export_to_csv(df: DataFrame, output_path: str, mode: str = "overwrite") -> None:
    """
    Export DataFrame to CSV using Spark (with Pandas fallback)
    """
    try:
        logger.info(f"Exporting to CSV: {output_path}")
        
        if mode == "overwrite":
            if os.path.exists(output_path):
                shutil.rmtree(output_path)
        
        # Try native Spark
        try:
            df.coalesce(1).write \
                .mode(mode) \
                .option("header", "true") \
                .csv(output_path)
            logger.info(f"Successfully exported to {output_path} (Spark)")
        except Exception:
            logger.warning("Spark CSV export failed, trying Pandas fallback...")
            # Fallback
            pdf = df.toPandas()
            # If path was dir, pandas writes to file. ensure dir exists
            p_dir = os.path.dirname(output_path)
            if p_dir and not os.path.exists(p_dir):
                os.makedirs(p_dir, exist_ok=True)
                
            # If output_path is intended as a directory by Spark, Pandas usually writes a file.
            # But dashboards might expect a specific file. 
            # Our config points to 'reports/csv/errors_by_type' (no extension in config usually? or with .csv?)
            # The config usually has directory. 
            # Let's append .csv if missing for pandas file
            file_path = output_path
            if not file_path.endswith('.csv'):
                file_path = os.path.join(output_path, "report.csv")
                # Pandas needs directory for that
                os.makedirs(output_path, exist_ok=True)
                
            pdf.to_csv(file_path, index=False)
            logger.info(f"Successfully exported to {file_path} (Pandas)")

    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}")
        raise


def export_to_json(df: DataFrame, output_path: str, mode: str = "overwrite") -> None:
    """
    Export DataFrame to JSON using Spark (with Pandas fallback)
    """
    try:
        logger.info(f"Exporting to JSON: {output_path}")
        
        if mode == "overwrite":
             if os.path.exists(output_path):
                shutil.rmtree(output_path)
                
        # Try native Spark
        try:
            df.coalesce(1).write \
                .mode(mode) \
                .json(output_path)
            logger.info(f"Successfully exported to {output_path} (Spark)")
        except Exception:
            logger.warning("Spark JSON export failed, trying Pandas fallback...")
            # Fallback
            pdf = df.toPandas()
            
            # Similar directory vs file logic
            file_path = output_path
            if not file_path.endswith('.json'):
                file_path = os.path.join(output_path, "report.json")
                os.makedirs(output_path, exist_ok=True)
                
            pdf.to_json(file_path, orient='records', indent=2)
            logger.info(f"Successfully exported to {file_path} (Pandas)")
            
    except Exception as e:
        logger.error(f"Error exporting to JSON: {e}")
        raise


def export_to_parquet(df: DataFrame, output_path: str, mode: str = "overwrite") -> None:
    """
    Export DataFrame to Parquet format
    """
    try:
        logger.info(f"Exporting to Parquet: {output_path}")
        
        # Try native Spark
        try:
            df.write.mode(mode).parquet(output_path)
            logger.info(f"Successfully exported to {output_path} (Spark)")
        except Exception:
            logger.warning("Spark Parquet export failed, trying Pandas fallback...")
            pdf = df.toPandas()
            try:
                # Handle directory path for Pandas (which expects a file path usually, unlike Spark)
                target_path = output_path
                if not target_path.lower().endswith('.parquet'):
                    os.makedirs(target_path, exist_ok=True)
                    target_path = os.path.join(target_path, "logs.parquet")
                    
                pdf.to_parquet(target_path, index=False)
                logger.info(f"Successfully exported to {target_path} (Pandas)")
            except Exception as pe:
                logger.error(f"Pandas Parquet export also failed (missing pyarrow?): {pe}")
                
    except Exception as e:
        logger.error(f"Error exporting to Parquet: {e}")
        # Don't raise here for Parquet as it's optional for dashboard immediate view
        pass


def generate_summary_report(analytics_results: Dict[str, DataFrame], config_path: str = "config/config.yaml") -> None:
    """Generate summary report in CSV format"""
    config = load_config(config_path)
    reports_csv_dir = config['paths']['reports_csv_dir']
    
    logger.info("Generating summary report...")
    
    export_to_csv(
        analytics_results.get("errors_by_type", None),
        f"{reports_csv_dir}/errors_by_type"  # Spark output is dir
    )
    
    export_to_csv(
        analytics_results.get("errors_by_hour", None),
        f"{reports_csv_dir}/errors_by_hour"
    )
    
    export_to_csv(
        analytics_results.get("top_n_errors", None),
        f"{reports_csv_dir}/top_errors"
    )
    
    export_to_csv(
        analytics_results.get("errors_per_ip", None),
        f"{reports_csv_dir}/errors_per_ip"
    )
    
    export_to_csv(
        analytics_results.get("errors_per_service", None),
        f"{reports_csv_dir}/errors_per_service"
    )
    
    logger.info("Summary report generation completed")


def generate_detailed_report(analytics_results: Dict[str, DataFrame], config_path: str = "config/config.yaml") -> None:
    """Generate detailed report in JSON format"""
    config = load_config(config_path)
    reports_json_dir = config['paths']['reports_json_dir']
    
    logger.info("Generating detailed report...")
    
    export_to_json(
        analytics_results.get("error_trends", None),
        f"{reports_json_dir}/error_trends"
    )
    
    export_to_json(
        analytics_results.get("errors_by_day", None),
        f"{reports_json_dir}/errors_by_day"
    )
    
    export_to_json(
        analytics_results.get("errors_by_severity", None),
        f"{reports_json_dir}/errors_by_severity"
    )
    
    logger.info("Detailed report generation completed")


def export_summary_stats(summary: Dict, config_path: str = "config/config.yaml") -> None:
    """Export summary statistics to JSON"""
    import json
    
    config = load_config(config_path)
    reports_json_dir = config['paths']['reports_json_dir']
    
    output_path = f"{reports_json_dir}/summary.json"
    
    # This is a small dict, python write is fine
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    
    logger.info(f"Exporting summary stats to: {output_path}")
    
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info("Summary stats exported successfully")


def export_all_reports(analytics_results: Dict[str, DataFrame], df_parsed: DataFrame = None, config_path: str = "config/config.yaml") -> None:
    """Export all reports"""
    logger.info("Exporting all reports...")
    
    generate_summary_report(analytics_results, config_path)
    generate_detailed_report(analytics_results, config_path)
    
    if df_parsed is not None:
        config = load_config(config_path)
        parquet_dir = config['paths'].get('parquet_dir', 'data/processed')
        export_to_parquet(df_parsed, parquet_dir)
    
    logger.info("All reports exported successfully")
