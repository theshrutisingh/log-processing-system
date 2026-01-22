# Distributed Log Processing System - Technical Documentation

**Version:** 1.0.0
**Date:** January 19, 2026
**Author:** AI Assistant (on behalf of Engineering Team)

---

## 📘 Table of Contents

1.  [Project Overview](#1-project-overview)
2.  [System Architecture](#2-system-architecture)
3.  [Folder Structure Explanation](#3-folder-structure-explanation)
4.  [Module-wise Detailed Explanation](#4-module-wise-detailed-explanation)
5.  [API Documentation](#5-api-documentation)
6.  [Authentication & Security](#6-authentication--security)
7.  [Dashboard & UI Working](#7-dashboard--ui-working)
8.  [Email & Notification System](#8-email--notification-system)
9.  [Error Handling & Logging](#9-error-handling--logging)
10. [AI / ML Integration](#10-ai--ml-integration)
11. [Database Design](#11-database-design)
12. [Performance Optimization](#12-performance-optimization)
13. [Deployment & Configuration](#13-deployment--configuration)
14. [Known Limitations](#14-known-limitations)
15. [Future Enhancements](#15-future-enhancements)
16. [Conclusion](#16-conclusion)

---

## 1. Project Overview

### Project Title
**Distributed Log Analytics & Monitoring System**

### Problem Statement
Modern distributed applications generate massive volumes of logs across various services (Linux, Spark, Application). Manual inspection of these logs for error detection, trend analysis, and root cause identification is inefficient and error-prone. A centralized, automated system is needed to ingest, parse, analyze, and visualize log data in real-time.

### Objectives
*   **Centralize Log Management:** Ingest logs from multiple sources (CSV, textual).
*   **Automated Parsing:** Normalize varied log formats (timestamps, levels, messages).
*   **Analytics & Insights:** Compute critical metrics like error rates, frequent failures, and trends.
*   **Real-time Visualization:** Provide an interactive dashboard for monitoring.
*   **Proactive Alerting:** Notify administrators of critical errors or threshold breaches via email.

### Target Users
*   **DevOps Engineers:** For monitoring system health and deployment stability.
*   **Developers:** For debugging specific error traces and application failures.
*   **System Administrators:** For tracking security attempts and infrastructure warnings.

### Key Features
*   **Multi-Source Ingestion:** Supports Linux system logs, Spark application logs, and custom CSV logs.
*   **Distributed Processing:** Utilizes **PySpark** for scalable data processing.
*   **Interactive Dashboard:** **Streamlit**-based UI with dynamic filtering and **Plotly** charts.
*   **Automated Reporting:** Generates downloadable CSV and JSON analytical reports.
*   **Role-Based Access:** Secure login with hashed credentials.
*   **Email Alerts:** Automated notifications for high error rates or critical incidents.

### Technology Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Frontend** | **Streamlit** (Python) | Interactive web interface for the dashboard. |
| **Visualization** | **Plotly Express / Graph Objects** | Interactive charts (Line, Donut, Bar). |
| **Backend Logic** | **Python 3.x** | Core application logic. |
| **Analytics Engine** | **Apache Spark (PySpark)** | Distributed data processing and aggregation. |
| **Data Processing** | **Pandas** | Lightweight data manipulation for UI rendering. |
| **Database (Auth)** | **SQLite** | Lightweight relational DB for user credentials. |
| **Data Storage** | **Parquet** / CSV | Columnar storage for processed logs. |
| **Security** | **Bcrypt** | Password hashing and salt management. |
| **Tools** | Git, Virtualenv | Version control and environment management. |

---

## 2. System Architecture

### High-Level Architecture
The system follows a **Monolithic Data Pipeline Architecture** with a decoupled frontend.
1.  **Ingestion Layer**: Reads raw log files from the local filesystem.
2.  **Processing Layer (Spark)**: Cleans, parses, and aggregates data using PySpark.
3.  **Storage Layer**: Saves processed data as Parquet files (Data Lake) and User data in SQLite.
4.  **Presentation Layer (Streamlit)**: Reads processed data and presents it via a Web UI.

### Component Interaction Flow
1.  **User Action**: User logs in via Streamlit UI.
2.  **Authentication**: Credentials checked against `users.db` (SQLite).
3.  **Data Request**: Dashboard requests data from `data_loader.py`.
4.  **Data Loading**: 
    *   If cached/processed data exists (Parquet), it is loaded via Pandas.
    *   If not, raw logs are ingested.
5.  **Analytics Service** (Background/On-demand):
    *   `main.py` triggers `SparkSession`.
    *   `ingest_logs.py` reads raw CSVs.
    *   `parse_logs.py` normalizes schemas.
    *   `analytics.py` computes aggregations (Top N errors, trends).
    *   `alerts.py` checks thresholds and sends emails via SMTP.

### API Request–Response Lifecycle (Internal)
Since the application runs locally without a REST API server, the lifecycle is function-call based:
1.  **UI Event**: User selects a date filter.
2.  **Function Call**: `app.py` calls `filter_data()`.
3.  **Processing**: Pandas filters the DataFrame in memory.
4.  **Response**: Filtered DataFrame returned to UI for rendering.

---

## 3. Folder Structure Explanation

```
/project_root
├── config/                 # Configuration files
│   └── config.yaml         # Central config (paths, thresholds, email settings)
├── data/                   # Data storage
│   ├── raw_logs/           # Input CSV/Log files
│   └── processed/          # Parquet output files
├── reports/                # Generated reports (CSV/JSON/Logs)
├── src/                    # Source Code
│   ├── dashboard/          # Frontend Module
│   │   ├── assets/         # CSS, Images
│   │   ├── components/     # Reusable UI widgets (cards, charts)
│   │   ├── controllers/    # UI Logic & Data Loading
│   │   ├── data/           # SQLite DB for Auth
│   │   ├── views/          # Page layouts (Login, Home)
│   │   ├── app.py          # Main Streamlit Entry Point
│   │   ├── auth.py         # Authentication Logic
│   │   └── alerts.py       # Frontend Alert Logic
│   ├── spark/              # Backend Analytics Module
│   │   ├── analytics.py    # Core Spark Calculations
│   │   ├── ingest_logs.py  # Data Loading (Spark)
│   │   ├── parse_logs.py   # Data Cleaning & Regex (Spark)
│   │   ├── alerts.py       # Backend Alerting Logic
│   │   └── main.py         # Pipeline Orchestration
└── requirements.txt        # Python Dependencies
```

---

## 4. Module-wise Detailed Explanation

### 4.1. Authentication Module
*   **File**: `src/dashboard/auth.py`
*   **Purpose**: Manages user identity and access control.
*   **Inputs**: Username, Password.
*   **Outputs**: Boolean (Success/Fail), Session State.
*   **Logic**:
    1.  `init_db()`: Checks if `users.db` exists, creates table if not.
    2.  `create_user()`: Hashes password using `bcrypt` and inserts into SQLite.
    3.  `check_credentials()`: Retrieves hashed password, verifies match.

### 4.2. Dashboard Module
*   **File**: `src/dashboard/app.py`
*   **Purpose**: Main user interface.
*   **Logic**:
    *   Checks `st.session_state.logged_in`. If False, renders Login View.
    *   Loads data via `load_raw_data_v2`.
    *   Renders sidebar (User info) and Main area (KPIs, Charts).
    *   Handles "Export Report" actions.

### 4.3. Spark Analytics Module
*   **Files**: `src/spark/analytics.py`, `parse_logs.py`
*   **Purpose**: Heavy-duty data processing.
*   **Logic**:
    *   **Parsing**: Uses Regex to extract IP, Service Name, and Error Type from raw text messages.
    *   **Aggregation**: Uses `groupBy` and `window` functions to compute error trends over time.

### 4.4. Alerting Module
*   **File**: `src/spark/alerts.py`
*   **Purpose**: Monitors data for anomalies.
*   **Logic**:
    *   Defines thresholds (e.g., Error Rate > 10%).
    *   `check_error_rate_alert()`: Computes rate; triggers alert if threshold breached.
    *   `send_email_alert()`: Connects to SMTP server to send HTML emails.

---

## 5. API Documentation (Internal Interfaces)

*Note: The system operates as a CLI/GUI application. Below are the key internal function interfaces.*

| Function / Endpoint | Module | Inputs | Outputs | Description |
| :--- | :--- | :--- | :--- | :--- |
| `run_all_analytics` | `analytics.py` | `df` (Spark DataFrame) | `Dict[str, DataFrame]` | Runs full suite of analytics (trends, distribution). |
| `ingest_logs` | `ingest_logs.py` | `config_path` | `DataFrame` | Reads raw CSVs into Spark. |
| `check_credentials` | `auth.py` | `username`, `password` | `bool` | Verifies user login. |
| `load_raw_data_v2` | `data_loader.py` | `data_dir` | `pd.DataFrame` | Loads processed data for UI. |

---

## 6. Authentication & Security

*   **Mechanism**: Session-based authentication using Streamlit Session State.
*   **Storage**: Credentials stored in `src/dashboard/data/users.db` (SQLite).
*   **Password Security**:
    *   **Hashing**: Uses `bcrypt` (industry standard) with automatic salting.
    *   **Protection**: Passwords are **never** stored in plain text.
*   **Flow**:
    1.  User enters credentials.
    2.  System fetches hash from DB.
    3.  `bcrypt.checkpw` validates input.
    4.  On success, `st.session_state.logged_in = True`.

---

## 7. Dashboard & UI Working

1.  **Login Page**: Simple form. On success, redirects to Dashboard.
2.  **Sidebar**:
    *   Displays User Profile.
    *   Logout button clears session.
3.  **Top Filters**:
    *   **Date Range**: "All Time" or "Custom Range".
    *   **Log Levels**: Checkboxes (INFO, WARN, ERROR).
    *   **Reset**: Clears all filters.
4.  **Main View**:
    *   **KPI Cards**: Total Logs, Error Count, Warnings, Error Rate. Shows trend arrows compared to previous period.
    *   **Trend Chart**: Line chart showing Errors vs Warnings over time.
    *   **Distribution**: Donut chart of log levels.
    *   **Top Errors**: List of most frequent error messages with a progress bar.

---

## 8. Email & Notification System

*   **Trigger Points**:
    *   High Error Rate (>10% default).
    *   Critical Error Count (>5 occurrences).
    *   Frequent Error Pattern (Same error > 5 times).
*   **Service**: Standard SMTP (configured in `email_config.py`).
*   **Templates**: HTML template with red header for Critical alerts, including timestamp and severity.
*   **Fallback**: Logs alerts to `reports/alerts.log` if Email fails.

---

## 9. Error Handling & Logging

*   **Global Handling**:
    *   `try-except` blocks wrap major pipeline steps in `main.py`.
    *   UI components gracefully handle missing data (display "No Data" instead of crashing).
*   **Data Recovery**:
    *   `ingest_logs.py` has a **Pandas Fallback**: If Spark native reader fails (common on Windows without winutils), it switches to a Pandas-based reader seamlessly.
*   **Logging**:
    *   Uses Python's `logging` module.
    *   Logs written to console and `debug.log`.

---

## 10. AI / ML Integration

*   **Current State**: **Statistical Anomaly Detection**.
    *   The system uses statistical thresholds rather than neural networks.
*   **Detection Logic**:
    *   **Frequency Analysis**: Identifies spikes in specific error messages (`check_frequent_errors_alert`).
    *   **Trend Analysis**: Detects sudden increases in error rates via moving averages (simulated via window functions).
*   **Future AI**: The architecture supports plugging in a standard Scikit-Learn outlier detection model in `analytics.py`.

---

## 11. Database Design

### 1. User Database (`users.db`)
*   **Type**: SQLite (Relational).
*   **Table**: `users`
    *   `username` (TEXT, PK)
    *   `password` (TEXT, Hashed)
    *   `email` (TEXT)

### 2. Log Data Store
*   **Type**: File-based (Data Lake).
*   **Format**: Parquet (for intermediate processing) and CSV (raw ingestion).
*   **Schema (Spark DataFrame)**:
    *   `timestamp` (TimestampType)
    *   `log_level` (StringType)
    *   `message` (StringType)
    *   `error_type` (StringType)
    *   `service_name` (StringType)
    *   `ip_address` (StringType)

---

## 12. Performance Optimization

*   **Caching Strategy**:
    *   **Spark**: `.cache()` is called on heavy aggregation results in `analytics.py` to prevent re-computation.
    *   **Streamlit**: `@st.cache_data` decorator is used on `load_raw_data_v2` to keep the dataframe in memory, preventing disk reads on every UI interaction.
*   **Ingestion**:
    *   Uses **Vectorized Operations** in Pandas/Spark.
    *   Avoids Python loops for data processing.

---

## 13. Deployment & Configuration

### Prerequisites
*   Python 3.10+
*   Java 8+ (for PySpark)

### Key Environment Variables
*   `SPARK_HOME`: Path to Spark installation.
*   `HADOOP_HOME`: Path to winutils (if on Windows).

### Configuration (`config/config.yaml`)
*   Alert thresholds (`error_rate_threshold`).
*   Directory paths (`raw_logs_dir`).
*   Email credentials (stored in `src/spark/email_config.py` for security).

### Steps
1.  Install dependencies: `pip install -r requirements.txt`.
2.  Run Pipeline: `python src/main.py` (Ingest & Process).
3.  Launch UI: `streamlit run src/dashboard/app.py`.

---

## 14. Known Limitations

*   **Single Node Spark**: Currently configured for local mode (`local[*]`). Requires cluster configuration for multi-node.
*   **Memory Usage**: large log files (>10GB) might overwhelm the Pandas fallback if Spark fails.
*   **Real-time Latency**: The dashboard reads from processed files; it is "near real-time" rather than true streaming.

---

## 15. Future Enhancements

*   **True AI Integration**: Implement `IsolationForest` for unsupervised anomaly detection.
*   **Database Migration**: Move `users.db` to PostgreSQL for scalability.
*   **Streaming**: Switch to **Spark Structured Streaming** for sub-second latency.
*   **Containerization**: Dockerize the application for easier deployment on Kubernetes.

---

## 16. Conclusion

The **Distributed Log Analytics System** provides a robust, scalable foundation for monitoring application health. By combining **PySpark's** processing power with **Streamlit's** modern UI, it delivers actionable insights and proactive alerts. The modular architecture ensures maintainability and allows for easy future upgrades to advanced ML capabilities.
