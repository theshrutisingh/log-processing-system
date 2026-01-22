"""
Core Analytics Module
Computes analytics using native PySpark DataFrame operations for true distributed processing.
"""

import logging
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, LongType
from pyspark.sql.window import Window
from typing import Dict, Optional
import sys
import os

# Handle imports for both direct execution and module import
try:
    from src.spark.spark_session import get_spark_session, load_config
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.spark.spark_session import get_spark_session, load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def compute_total_log_count(df: DataFrame) -> int:
    """Compute total number of logs"""
    total = df.count()
    logger.info(f"Total log count: {total}")
    return total


def compute_error_count(df: DataFrame) -> int:
    """Compute total number of errors"""
    error_count = df.filter(F.col("log_level") == "ERROR").count()
    logger.info(f"Total error count: {error_count}")
    return error_count


def compute_error_rate(df: DataFrame) -> float:
    """Compute error rate (errors / total logs)"""
    total = compute_total_log_count(df)
    if total == 0:
        return 0.0
    
    errors = compute_error_count(df)
    rate = errors / total
    logger.info(f"Error rate: {rate:.4f} ({rate*100:.2f}%)")
    return rate


def errors_by_type(df: DataFrame) -> DataFrame:
    """Group errors by error type using native PySpark"""
    logger.info("Computing errors by type...")
    
    result = (
        df.filter(F.col("log_level") == "ERROR")
        .groupBy("error_type")
        .agg(F.count("*").alias("count"))
        .orderBy(F.col("count").desc())
    )
    
    return result


def errors_by_severity(df: DataFrame) -> DataFrame:
    """Group errors by severity level using native PySpark"""
    logger.info("Computing errors by severity...")
    
    result = (
        df.filter(F.col("log_level") == "ERROR")
        .groupBy("severity", "log_level")
        .agg(F.count("*").alias("count"))
        .orderBy(F.col("severity").desc())
    )
    
    return result


def errors_by_time(df: DataFrame, time_unit: str = "hour") -> DataFrame:
    """Group errors by time (hour/day) using native PySpark"""
    logger.info(f"Computing errors by {time_unit}...")
    
    errors_df = df.filter(F.col("log_level") == "ERROR")
    
    if time_unit == "hour":
        result = (
            errors_df
            .withColumn("date", F.to_date("timestamp"))
            .withColumn("hour", F.hour("timestamp"))
            .groupBy("date", "hour")
            .agg(F.count("*").alias("error_count"))
            .orderBy("date", "hour")
        )
    else:  # day
        result = (
            errors_df
            .withColumn("date", F.to_date("timestamp"))
            .groupBy("date")
            .agg(F.count("*").alias("error_count"))
            .orderBy("date")
        )
    
    return result


def top_n_errors(df: DataFrame, n: int = 10) -> DataFrame:
    """Get top N most frequent errors using native PySpark"""
    logger.info(f"Computing top {n} errors...")
    
    result = (
        df.filter(F.col("log_level") == "ERROR")
        .groupBy("error_type", "message")
        .agg(F.count("*").alias("count"))
        .orderBy(F.col("count").desc())
        .limit(n)
    )
    
    return result


def error_trends_over_time(df: DataFrame, window_size: str = "1h") -> DataFrame:
    """Compute error trends over time using PySpark window functions"""
    logger.info(f"Computing error trends with {window_size} windows...")
    
    # Parse window size (e.g., "1h" -> 1 hour)
    interval = window_size.replace("h", " hour").replace("d", " day").replace("m", " minute")
    
    result = (
        df.filter(F.col("log_level") == "ERROR")
        .withColumn("time_window", F.window("timestamp", interval))
        .groupBy("time_window")
        .agg(F.count("*").alias("error_count"))
        .withColumn("time_window", F.col("time_window.start"))  # Extract window start
        .orderBy("time_window")
    )
    
    return result


def errors_per_ip(df: DataFrame) -> DataFrame:
    """Group errors by IP address using native PySpark"""
    logger.info("Computing errors per IP...")
    
    result = (
        df.filter(
            (F.col("log_level") == "ERROR") & 
            (F.col("ip_address").isNotNull()) & 
            (F.col("ip_address") != "")
        )
        .groupBy("ip_address")
        .agg(F.count("*").alias("error_count"))
        .orderBy(F.col("error_count").desc())
    )
    
    return result


def errors_per_service(df: DataFrame) -> DataFrame:
    """Group errors by service using native PySpark"""
    logger.info("Computing errors per service...")
    
    result = (
        df.filter(
            (F.col("log_level") == "ERROR") & 
            (F.col("service_name").isNotNull()) & 
            (F.col("service_name") != "")
        )
        .groupBy("service_name")
        .agg(F.count("*").alias("error_count"))
        .orderBy(F.col("error_count").desc())
    )
    
    return result


def generate_summary_statistics(df: DataFrame) -> Dict:
    """Generate comprehensive summary statistics using native PySpark"""
    logger.info("Generating summary statistics...")
    
    # All counts using Spark
    total_logs = compute_total_log_count(df)
    total_errors = compute_error_count(df)
    error_rate = compute_error_rate(df)
    
    # Log level distribution using Spark
    log_level_df = df.groupBy("log_level").count().collect()
    log_level_counts = {row["log_level"]: row["count"] for row in log_level_df}
    
    # Unique counts using Spark's countDistinct
    unique_counts = df.agg(
        F.countDistinct(F.when(F.col("ip_address") != "", F.col("ip_address"))).alias("unique_ips"),
        F.countDistinct(F.when(F.col("service_name") != "", F.col("service_name"))).alias("unique_services"),
        F.countDistinct(
            F.when(F.col("log_level") == "ERROR", F.col("error_type"))
        ).alias("unique_error_types")
    ).collect()[0]
    
    summary = {
        "total_logs": total_logs,
        "total_errors": total_errors,
        "error_rate": error_rate,
        "log_level_counts": log_level_counts,
        "unique_ips": unique_counts["unique_ips"] or 0,
        "unique_services": unique_counts["unique_services"] or 0,
        "unique_error_types": unique_counts["unique_error_types"] or 0
    }
    
    logger.info(f"Summary statistics generated: {summary}")
    return summary


def run_all_analytics(df: DataFrame, config: Optional[Dict] = None) -> Dict[str, DataFrame]:
    """Run all analytics and return results as DataFrames"""
    if config is None:
        config = load_config()
    
    top_n = config.get('analytics', {}).get('top_n_errors', 10)
    
    logger.info("Running all analytics...")
    
    # All functions now use native PySpark operations
    results = {
        "errors_by_type": errors_by_type(df),
        "errors_by_severity": errors_by_severity(df),
        "errors_by_hour": errors_by_time(df, "hour"),
        "errors_by_day": errors_by_time(df, "day"),
        "top_n_errors": top_n_errors(df, top_n),
        "error_trends": error_trends_over_time(df, "1h"),
        "errors_per_ip": errors_per_ip(df),
        "errors_per_service": errors_per_service(df)
    }
    
    # Cache results for potential reuse
    for name, result_df in results.items():
        result_df.cache()
        logger.info(f"Cached {name} results")
    
    logger.info("All analytics completed")
    return results


if __name__ == "__main__":
    from ingest_logs import ingest_logs
    from parse_logs import parse_logs
    
    spark = get_spark_session()
    df_raw = ingest_logs()
    df_parsed = parse_logs(df_raw)
    
    # Run analytics
    analytics_results = run_all_analytics(df_parsed)
    
    # Display results
    for name, result_df in analytics_results.items():
        print(f"\n{name}:")
        result_df.show(20, truncate=False)
