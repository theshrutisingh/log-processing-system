"""
Log Parsing and Normalization Module
Cleans and normalizes log data using PySpark native transformations.
"""

import logging
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.functions import (
    col, when, regexp_extract, trim, lower, upper,
    to_timestamp, hour, dayofmonth, month, year,
    split, size, regexp_replace, isnan, isnull, coalesce, lit
)
from typing import Optional
import sys
import os

# Handle imports for both direct execution and module import
try:
    from src.spark.spark_session import get_spark_session
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.spark.spark_session import get_spark_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_null_rows(df: DataFrame) -> DataFrame:
    """
    Remove rows that are completely unusable.
    Relaxed check: Keep row if at least 'message' or 'timestamp' exists.
    """
    initial_count = df.count()
    
    # Only drop if BOTH critical fields are missing
    # or if message is completely empty
    df_cleaned = df.filter(
        col("timestamp").isNotNull() |
        (col("message").isNotNull() & (trim(col("message")) != ""))
    )
    
    final_count = df_cleaned.count()
    removed = initial_count - final_count
    
    if removed > 0:
        logger.info(f"Removed {removed} invalid rows")
    
    return df_cleaned


def normalize_timestamps(df: DataFrame, timestamp_col: str = "timestamp") -> DataFrame:
    """
    Normalize timestamp column to standard format.
    Handles multiple formats robustly.
    """
    logger.info("Normalizing timestamps...")
    
    # If timestamp is string, try to parse it. 
    # Current ingestion might produce 'yyyy-MM-dd HH:mm:ss' or 'yyyy-MM-dd HH:mm:ss.SSS'
    
    # Handle Linux logs which might be "Jun 14 15:16:01" (missing year)
    # We prepend a default year (e.g. 2025) to make it parsable
    # Check if format matches "MMM d HH:mm:ss" approximately (regex check is expensive, maybe just try parse?)
    # Spark's to_timestamp with strict format will return null if it doesn't match, so we can just chain coalesce.
    
    # Pre-process for Linux logs: "Jun 14 15:16:01" -> "2025 Jun 14 15:16:01"
    # We blindly prepend 2025 to everything? No, that ruins other formats.
    # We can try to match the pattern or just create a new column candidate.
    
    current_year = "2025" # Default year for logs missing year
    
    df = df.withColumn(
        "ts_linux_candidate", 
        F.concat(lit(f"{current_year} "), col(timestamp_col))
    )

    # We use coalesce to try multiple formats
    df_normalized = df.withColumn(
        "ts_parsed",
        coalesce(
            to_timestamp(col(timestamp_col)), # Spark default inference
            to_timestamp(col(timestamp_col), "yyyy-MM-dd HH:mm:ss"),
            to_timestamp(col(timestamp_col), "yyyy-MM-dd HH:mm:ss.SSS"),
            to_timestamp(col(timestamp_col), "yyyy-MM-dd'T'HH:mm:ss"),
            to_timestamp(col(timestamp_col), "yyyy-MM-dd"),
            # Spark Logs: 17/06/09 20:10:40 (yy/MM/dd)
            to_timestamp(col(timestamp_col), "yy/MM/dd HH:mm:ss"),
            # Linux Logs: Jun 14 15:16:01 (using candidate with prepended year)
            to_timestamp(col("ts_linux_candidate"), "yyyy MMM d HH:mm:ss"),
            # Linux Logs: Jun  4 15:16:01 (two spaces for single digit day?) 
            # Spark's simpleDateFormat 'd' handles 1 or 2 digits usually, but spaces might matter.
            to_timestamp(col("ts_linux_candidate"), "yyyy MMM  d HH:mm:ss")
        )
    ).drop("ts_linux_candidate")
    
    # Fallback: if parsing failed, keep original if it was already timestamp type, or null
    df_normalized = df_normalized.withColumn(
        timestamp_col,
        coalesce(col("ts_parsed"), col(timestamp_col)) 
    ).drop("ts_parsed")
    
    # Filter out where timestamp couldn't be parsed if critical? 
    # OR keep them and allow null timestamps? 
    # Analytics relies on timestamp, so let's filter null timestamps here if strict.
    # But let's log warning instead of dropping silently?
    # actually, analytics needs timestamp.
    
    # Extract time components IF timestamp is valid
    df_normalized = df_normalized.withColumn("hour", hour(col(timestamp_col))) \
        .withColumn("day", dayofmonth(col(timestamp_col))) \
        .withColumn("month", month(col(timestamp_col))) \
        .withColumn("year", year(col(timestamp_col))) \
        .withColumn("date", col(timestamp_col).cast("date"))
    
    return df_normalized


def standardize_log_level(df: DataFrame, log_level_col: str = "log_level") -> DataFrame:
    """Standardize log level values (INFO, WARN, ERROR, etc.)"""
    logger.info("Standardizing log levels...")
    
    # If log_level is missing, default to INFO or UNKNOWN?
    # Let's try to extract from message if missing?
    
    df_standardized = df.withColumn(
        log_level_col,
        trim(upper(col(log_level_col)))
    )
    
    # Fill nulls
    df_standardized = df_standardized.fillna({log_level_col: "INFO"})
    
    df_standardized = df_standardized.withColumn(
        "severity",
        when(col(log_level_col) == "ERROR", 3)
        .when(col(log_level_col) == "WARN", 2)
        .when(col(log_level_col) == "INFO", 1)
        .when(col(log_level_col) == "DEBUG", 0)
        .otherwise(1)
    )
    
    return df_standardized


def extract_error_type(df: DataFrame, message_col: str = "message") -> DataFrame:
    """Extract error type from message field"""
    logger.info("Extracting error types...")
    
    # Start with existing error_type if ingested
    if "error_type" not in df.columns:
        df = df.withColumn("error_type", lit(None).cast("string"))
        
    # Standardize existing error_type
    df = df.withColumn("error_type", trim(col("error_type")))
    
    # If error_type is null/empty, try to extract from message
    df_with_error = df.withColumn(
        "error_type",
        when(
            (col("error_type").isNotNull()) & (col("error_type") != ""), 
            col("error_type")
        ).otherwise(
            # Extraction logic
            when(
                regexp_extract(col(message_col), r"(?i)(exception|error|failed|failure)", 1) != "",
                regexp_extract(col(message_col), r"(?i)(\w+Exception|\w+Error|\w+Failure)", 1)
            ).when(
                regexp_extract(col(message_col), r"(?i)(timeout|time out)", 1) != "",
                "TimeoutError"
            ).when(
                regexp_extract(col(message_col), r"(?i)(connection|connect)", 1) != "",
                "ConnectionError"
            ).when(
                regexp_extract(col(message_col), r"(?i)(authentication|auth|unauthorized)", 1) != "",
                "AuthenticationError"
            ).when(
                regexp_extract(col(message_col), r"(?i)(not found|404)", 1) != "",
                "NotFoundError"
            ).when(
                regexp_extract(col(message_col), r"(?i)(permission|forbidden|403)", 1) != "",
                "PermissionError"
            ).otherwise("UnknownError")
        )
    )
    
    return df_with_error


def extract_ip_address(df: DataFrame, message_col: str = "message") -> DataFrame:
    """Extract IP address"""
    logger.info("Extracting IP addresses...")
    
    if "ip_address" in df.columns:
        # Already exists (maybe renamed from 'ip' in ingest)
        return df
        
    # Check if 'ip' or 'IP' column existed and wasn't renamed? 
    # Ingest does lowercase rename. So 'ip' might exist.
    if "ip" in df.columns:
        return df.withColumnRenamed("ip", "ip_address")
        
    # Extract from message
    ip_pattern = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    df_with_ip = df.withColumn(
        "ip_address",
        regexp_extract(col(message_col), ip_pattern, 0)
    )
    
    return df_with_ip


def extract_service_endpoint(df: DataFrame, message_col: str = "message") -> DataFrame:
    """Extract service and endpoint information"""
    logger.info("Extracting service and endpoint information...")
    
    df_with_service = df
    
    if "service_name" not in df.columns:
        if "service" in df.columns:
            df_with_service = df_with_service.withColumnRenamed("service", "service_name")
        else:
             df_with_service = df_with_service.withColumn(
                "service_name",
                regexp_extract(col(message_col), r"(?i)(service|api|endpoint)[:\s]+([\w/-]+)", 2)
            )
            
    if "endpoint_path" not in df.columns:
        if "endpoint" in df.columns:
             df_with_service = df_with_service.withColumnRenamed("endpoint", "endpoint_path")
        else:
            df_with_service = df_with_service.withColumn(
                "endpoint_path",
                regexp_extract(col(message_col), r"(GET|POST|PUT|DELETE|PATCH)\s+([/\w-]+)", 2)
            )
            
    return df_with_service


def parse_logs(df: DataFrame) -> DataFrame:
    """Main parsing function"""
    logger.info("Starting log parsing and normalization...")
    
    initial_count = df.count()
    logger.info(f"Processing {initial_count} records")
    
    # 1. Clean nulls (relaxed)
    df = clean_null_rows(df)
    
    # 2. Normalize timestamps
    df = normalize_timestamps(df)
    
    # 3. Standardize log levels
    df = standardize_log_level(df)
    
    # 4. Extract entities
    df = extract_error_type(df)
    df = extract_ip_address(df)
    df = extract_service_endpoint(df)
    
    # 5. Clean message
    if "message" in df.columns:
        df = df.withColumn("message", trim(col("message")))
    else:
        # Should have been caught by validation, but ensure column exists
        df = df.withColumn("message", lit(""))
    
    final_count = df.count()
    logger.info(f"Parsing completed. Processed {final_count} records")
    
    return df
