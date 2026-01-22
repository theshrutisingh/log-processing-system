# Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

**Note**: Ensure Java 8+ is installed. Check with:
```bash
java -version
```

### Step 2: Verify Sample Data

Sample log data is already included in `data/raw_logs/sample_logs.csv`. You can add your own CSV files to this directory.

### Step 3: Run Processing

Process the logs using PySpark:

```bash
python src/main.py
```

This will:
- Load logs from `data/raw_logs/`
- Parse and normalize the data
- Run analytics
- Check for alerts
- Generate reports in `reports/csv/` and `reports/json/`

### Step 4: Launch Dashboard

In a new terminal:

```bash
streamlit run src/dashboard/app.py
```

The dashboard will open at `http://localhost:8501`

## 📊 What You'll See

### Processing Output
- Log ingestion progress
- Parsing statistics
- Analytics results
- Alert notifications (if any)
- Report generation confirmation

### Dashboard Features
- **Metrics Cards**: Total logs, errors, error rate
- **Charts**: Error trends, top errors, errors by IP/service
- **Filters**: Date range, log level selection
- **Alert Panel**: Recent alerts
- **Detailed Tables**: Top errors, trends, severity

## 🔧 Troubleshooting

### "Java not found"
Install Java 8 or higher and set `JAVA_HOME`:
- Windows: Download from Oracle or use OpenJDK
- Linux: `sudo apt-get install openjdk-8-jdk`
- Mac: `brew install openjdk@8`

### "Module not found"
Ensure you're running from the project root directory.

### "No data in dashboard"
Make sure you've run `python src/main.py` first to generate reports.

## 📝 Next Steps

1. **Add Your Logs**: Place CSV files in `data/raw_logs/`
2. **Customize Config**: Edit `config/config.yaml` for your needs
3. **Adjust Alerts**: Modify thresholds in config file
4. **Extend Analytics**: Add new analytics in `src/spark/analytics.py`

## 🎯 Example Workflow

```bash
# 1. Add your log files
cp your_logs.csv data/raw_logs/

# 2. Process logs
python src/main.py

# 3. View dashboard
streamlit run src/dashboard/app.py

# 4. Check reports
ls reports/csv/
ls reports/json/
```

Happy processing! 🎉


