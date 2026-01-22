"""
Spark Session Management Module
Creates and manages reusable SparkSession instances
Compatible with PySpark 3.5.1 (Windows + Python 3.11)
"""

import logging
import os

# Fix: Unset SPARK_HOME if set to avoid conflicts with external Spark installations
# This MUST happen before pyspark is imported
# Fix: Unset SPARK_HOME if set to avoid conflicts with external Spark installations
# This MUST happen before pyspark is imported
if "SPARK_HOME" in os.environ:
    del os.environ["SPARK_HOME"]

# Fix: Sanitize environment variables for Windows (remove leading/trailing spaces)
# This fixes "The filename, directory name, or volume label syntax is incorrect" error
for env_var in ["JAVA_HOME", "HADOOP_HOME"]:
    if os.environ.get(env_var):
        os.environ[env_var] = os.environ[env_var].strip()

# Fix: Add HADOOP_HOME/bin to PATH for hadoop.dll
if "HADOOP_HOME" in os.environ:
    hadoop_bin = os.path.join(os.environ["HADOOP_HOME"], "bin")
    if hadoop_bin not in os.environ["PATH"]:
        os.environ["PATH"] += os.pathsep + hadoop_bin

# Fix: Force Spark to use IPv4 loopback
os.environ["SPARK_LOCAL_IP"] = "127.0.0.1"

from pyspark.sql import SparkSession
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_config(config_path: str = "config/config.yaml") -> dict:
    """
    Load configuration from YAML file
    """
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        logger.info(f"Configuration loaded from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        raise


def create_spark_session(config: dict = None) -> SparkSession:
    """
    Create and configure SparkSession (Spark 3.5.1 safe)
    """
    if config is None:
        config = load_config()

    spark_cfg = config.get("spark", {})

    builder = (
        SparkSession.builder
        .appName(spark_cfg.get("app_name", "DistributedLogProcessor"))
        .appName(spark_cfg.get("app_name", "DistributedLogProcessor"))
        .master("local[1]") # Force single thread for stability
        # Fix for Windows: Force driver to bind to loopback to avoid VPN/Network issues causing ConnectionReset
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.driver.host", "localhost")
        .config("spark.sql.warehouse.dir", "file:///C:/temp/spark-warehouse")
        .config("spark.local.dir", "C:/temp/spark-temp")
        .config("spark.driver.extraJavaOptions", "-Djava.io.tmpdir=C:/temp/spark-temp")
    )

    # Memory configuration
    builder = builder.config(
        "spark.executor.memory",
        spark_cfg.get("executor_memory", "2g")
    )
    builder = builder.config(
        "spark.driver.memory",
        spark_cfg.get("driver_memory", "1g")
    )
    
    # Fix: Explicitly set java.library.path for hadoop.dll
    if "HADOOP_HOME" in os.environ:
        hadoop_bin = os.path.join(os.environ["HADOOP_HOME"], "bin")
        builder = builder.config("spark.driver.extraJavaOptions", f"-Djava.library.path={hadoop_bin}")
        
    builder = builder.config(
        "spark.driver.maxResultSize",
        spark_cfg.get("max_result_size", "1g")
    )

    # Performance & stability (safe for Spark 3.5)
    builder = builder.config("spark.sql.adaptive.enabled", "true")
    builder = builder.config(
        "spark.sql.adaptive.coalescePartitions.enabled", "true"
    )

    spark = builder.getOrCreate()

    spark.sparkContext.setLogLevel(
        spark_cfg.get("log_level", "WARN")
    )

    logger.info(f"SparkSession created: {spark.sparkContext.appName}")
    logger.info(f"Spark Master: {spark.sparkContext.master}")

    return spark


def get_spark_session() -> SparkSession:
    """
    Get active SparkSession or create one
    """
    spark = SparkSession.getActiveSession()
    if spark is None:
        spark = create_spark_session()
    return spark
