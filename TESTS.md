# GalacticCIC Test Checklist

[Back to README](README.md)

## Run Tests Locally

```bash
# Install test dependencies
pip install behave

# Run BDD tests
python3 -m behave tests/features/

# Run unit tests
python3 -m unittest tests/test_collectors -v
```

## Test Scenarios

Last updated: 2026-02-23

| Feature | Scenario | Status |
|---------|----------|--------|
| **agents.feature** | Display all configured agents | ✅ passing |
| **agents.feature** | Show session counts per agent | ✅ passing |
| **agents.feature** | Handle openclaw command failure gracefully | ✅ passing |
| **server.feature** | Display CPU, memory, and disk usage | ✅ passing |
| **server.feature** | Color code based on thresholds | ✅ passing |
| **server.feature** | Show gateway status | ✅ passing |
| **cron.feature** | Display all cron jobs with status | ✅ passing |
| **cron.feature** | Highlight error jobs | ✅ passing |
| **cron.feature** | Show consecutive error count | ✅ passing |
| **security.feature** | Show SSH login status | ✅ passing |
| **security.feature** | Alert on high failed login count | ✅ passing |
| **security.feature** | Show listening ports | ✅ passing |
| **activity.feature** | Display recent events | ✅ passing |
| **activity.feature** | Color code events by level | ✅ passing |
| **activity.feature** | Filter activity log | ✅ passing |
| **navigation.feature** | Quit with q | ✅ passing |
| **navigation.feature** | Force refresh with r | ✅ passing |
| **navigation.feature** | Focus panel with number keys | ✅ passing |
| **install.feature** | Package is importable | ✅ passing |
| **install.feature** | Module is runnable | ✅ passing |
| **install.feature** | Dependencies are available | ✅ passing |
| **database.feature** | Database is created on startup | ✅ passing |
| **database.feature** | Record and retrieve agent metrics | ✅ passing |
| **database.feature** | Calculate tokens per hour | ✅ passing |
| **database.feature** | Server trend arrows | ✅ passing |

## Unit Tests

| Test Class | Test | Status |
|------------|------|--------|
| **TestRunCommand** | test_successful_command | ✅ passing |
| **TestRunCommand** | test_failing_command | ✅ passing |
| **TestRunCommand** | test_missing_command | ✅ passing |
| **TestRunCommand** | test_timeout | ✅ passing |
| **TestParseSize** | test_gigabytes | ✅ passing |
| **TestParseSize** | test_megabytes | ✅ passing |
| **TestParseSize** | test_terabytes | ✅ passing |
| **TestParseSize** | test_invalid | ✅ passing |
| **TestParseStorageBytes** | test_megabytes | ✅ passing |
| **TestParseStorageBytes** | test_gigabytes | ✅ passing |
| **TestParseStorageBytes** | test_invalid | ✅ passing |
| **TestCollectors** | test_server_health_returns_dict | ✅ passing |
| **TestCollectors** | test_agents_data_returns_dict | ✅ passing |
| **TestCollectors** | test_cron_jobs_returns_dict | ✅ passing |
| **TestCollectors** | test_security_status_returns_dict | ✅ passing |
| **TestCollectors** | test_activity_log_returns_list | ✅ passing |
| **TestMetricsDB** | test_db_creates_file | ✅ passing |
| **TestMetricsDB** | test_schema_version | ✅ passing |
| **TestMetricsDB** | test_insert_and_fetch_server_metrics | ✅ passing |
| **TestMetricsDB** | test_insert_and_fetch_agent_metrics | ✅ passing |
| **TestMetricsDB** | test_prune_old_records | ✅ passing |
| **TestMetricsDB** | test_recent_records_survive_prune | ✅ passing |
| **TestMetricsRecorder** | test_record_agents | ✅ passing |
| **TestMetricsRecorder** | test_record_server | ✅ passing |
| **TestMetricsRecorder** | test_record_security | ✅ passing |
| **TestTrendCalculator** | test_no_data_returns_dashes | ✅ passing |
| **TestTrendCalculator** | test_tokens_per_hour_empty | ✅ passing |
| **TestTrendCalculator** | test_tokens_per_hour_calculation | ✅ passing |
| **TestTrendCalculator** | test_server_trends_with_data | ✅ passing |
