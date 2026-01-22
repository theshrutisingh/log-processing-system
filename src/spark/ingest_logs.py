"""
Log Ingestion Module
Loads CSV log files using native PySpark readers for distributed processing.
"""

import logging
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StringType
from typing import List, Optional
import os
import sys

# Handle imports for both direct execution and module import
try:
    from src.spark.spark_session import get_spark_session, load_config
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.spark.spark_session import get_spark_session, load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_logs_from_csv(
    spark: SparkSession,
    input_path: str,
    header: bool = True
) -> DataFrame:
    """
    Load CSV log files into Spark DataFrame using native Spark reader
    
    Args:
        spark: SparkSession instance
        input_path: Path to CSV file or directory
        header: Whether CSV has header row
        
    Returns:
        Spark DataFrame containing log data
    """
    try:
        logger.info(f"Loading logs from: {input_path}")
        
        # Determine strict path for globbing if it's a directory
        # Spark's read.csv handles directories automatically, but for "recursive" we might need options
        # We will use simple directory read first.
        input_path = os.path.abspath(input_path)
        # Fix: Spark on Windows often prefers forward slashes or URI scheme
        input_path = input_path.replace("\\", "/")
        
        # Try native Spark CSV reader first
        try:
            logger.info("Attempting load with native Spark reader...")
            df = spark.read.option("header", str(header).lower()) \
                .option("inferSchema", "true") \
                .option("quote", "\"") \
                .option("escape", "\"") \
                .csv(input_path)
                
            # Trigger action to verify read works (Spark is lazy)
            count = df.count()
            logger.info(f"Native Spark load successful. Count: {count}")
            
            # Normalize column names for consistency
            for col_name in df.columns:
                df = df.withColumnRenamed(col_name, col_name.lower())
                
                
        except Exception as spark_idx:
            logger.warning(f"Native Spark load failed: {spark_idx}. Falling back to Pandas workaround due to missing winutils.")
            import pandas as pd
            import glob
            
            # Find files
            if os.path.isdir(input_path):
                files = glob.glob(os.path.join(input_path, "*.csv"))
            else:
                files = [input_path]
                
            pdf_list = []
            for f in files:
                try:
                    # Robust loading: read everything as string/object first to prevent type clashes during concat
                    pdf = pd.read_csv(f, header=0 if header else None, quotechar='"', dtype=str)
                    pdf.columns = pdf.columns.str.lower()
                    # Remove duplicate columns
                    pdf = pdf.loc[:, ~pdf.columns.duplicated()]
                    
                    # Manual timestamp construction for workaround (if needed)
                    # Note: Since we forced dtype=str, we must handle conversions carefully later or let Spark infer
                    if 'timestamp' not in pdf.columns and 'date' in pdf.columns and 'time' in pdf.columns:
                        try:
                             time_clean = pdf['time'].astype(str).str.replace(',', '.')
                             pdf['timestamp'] = pd.to_datetime(
                                 pdf['date'].astype(str) + ' ' + time_clean, 
                                 format='mixed', 
                                 dayfirst=False, 
                                 errors='coerce'
                             ).dt.strftime('%Y-%m-%d %H:%M:%S')
                        except: pass
                        
                    pdf_list.append(pdf)
                except Exception as e:
                    logger.warning(f"Failed to read file {f} in Pandas fallback: {e}")
            
            if not pdf_list:
                # Return empty DF ensuring schema validity
                logger.warning("Pandas fallback found no valid data.")
                return spark.createDataFrame([], schema=StructType([]))
                
            try:
                # Robust concat
                full_pdf = pd.concat(pdf_list, ignore_index=True)
                # Fill NaNs
                full_pdf = full_pdf.where(pd.notnull(full_pdf), None)
                
                # OPTIMIZATION: Write to temp file instead of internal createDataFrame
                # This avoids "Task of very large size" error when passing huge data from Driver to Executor
                import tempfile
                import shutil
                
                temp_dir = os.path.join(os.getcwd(), "data", "temp_ingest")
                os.makedirs(temp_dir, exist_ok=True)
                temp_file = os.path.join(temp_dir, "temp_pandas_fallback.parquet")
                
                # Write with pandas (pyarrow engine usually default)
                try:
                    full_pdf.to_parquet(temp_file, index=False)
                    logger.info(f"Wrote intermediate temp file to {temp_file}")
                    
                    # Read with Spark
                    df = spark.read.parquet(temp_file)
                    logger.info(f"Pandas fallback load successful via temp file. Count: {df.count()}")
                    
                except Exception as io_err:
                    logger.warning(f"Failed to use temp file optimization: {io_err}. Falling back to memory (risky for large files).")
                    df = spark.createDataFrame(full_pdf)
                
                count = df.count()
            except Exception as concat_error:
                logger.error(f"Pandas concat/conversion failed: {concat_error}")
                return spark.createDataFrame([], schema=StructType([]))
        
        if count == 0:
            logger.warning("No data loaded from files")
            return df
            
        # Standardize basic columns (common to both paths)
        if "level" in df.columns:
            df = df.withColumnRenamed("level", "log_level")
        if "content" in df.columns:
            df = df.withColumnRenamed("content", "message")
        if "eventtemplate" in df.columns:
            df = df.withColumnRenamed("eventtemplate", "error_type")
            
        # Construct timestamp if missing but date/time exist (Spark path logic)
        # Note: Pandas path already tried to create it.
        # Construct timestamp if missing but date/time exist (Spark path logic)
        # Note: Pandas path already tried to create it.
        if "timestamp" not in df.columns:
            if "date" in df.columns and "time" in df.columns:
                logger.info("Constructing timestamp from date and time columns (Spark)...")
                df = df.withColumn("time_clean", F.regexp_replace(F.col("time"), ",", "."))
                # Just concat, let parse_logs handle the format
                df = df.withColumn(
                    "timestamp", 
                    F.concat_ws(" ", F.col("date"), F.col("time_clean"))
                ).drop("time_clean")
            elif "month" in df.columns and "date" in df.columns and "time" in df.columns:
                logger.info("Constructing timestamp from Month, Date, Time columns (Linux style)...")
                 # Assuming "Jun 14 15:16:01" style. 
                 # We'll just concat them. 
                 # Note: "Date" in Linux logs is the day of month (e.g. "14")
                df = df.withColumn(
                    "timestamp",
                    F.concat_ws(" ", F.col("month"), F.col("date"), F.col("time"))
                )

        return df
        
    except Exception as e:
        logger.error(f"Error loading logs: {e}")
        # Return empty DF on major failure to match previous contract (or raise?)
        # Standardize: Return empty DF or raise. Let's raise to stop pipeline.
        raise


def validate_schema(df: DataFrame, required_columns: List[str]) -> bool:
    """Validate that DataFrame contains required columns"""
    existing_columns = [c.lower() for c in df.columns]
    required_lower = [c.lower() for c in required_columns]
    
    missing_columns = [col for col in required_lower if col not in existing_columns]
    
    if missing_columns:
        logger.warning(f"Missing columns: {missing_columns}")
        logger.info(f"Available columns: {existing_columns}")
        return False
    
    logger.info("Schema validation passed")
    return True


def ingest_logs(config_path: str = "config/config.yaml") -> DataFrame:
    """Main ingestion function"""
    config = load_config(config_path)
    spark = get_spark_session()
    
    raw_logs_dir = config['paths']['raw_logs_dir']
    
    # Check if path exists
    if not os.path.exists(raw_logs_dir):
        logger.warning(f"Directory {raw_logs_dir} does not exist. Creating it.")
        os.makedirs(raw_logs_dir, exist_ok=True)
    
    # Load logs
    df = load_logs_from_csv(spark, raw_logs_dir)
    
    # Validate schema (soft check)
    # Different logs have different columns, but at least message should be there
    if "message" in df.columns or "content" in df.columns:
        pass
    else:
        logger.warning("Likely schema mismatch: 'message' or 'content' column not found.")
    
    logger.info(f"Ingested {df.count()} records")
    return df


if __name__ == "__main__":
    df = ingest_logs()
    df.show(5, truncate=False)
