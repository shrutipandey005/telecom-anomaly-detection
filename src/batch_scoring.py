"""
Daily Batch Scoring Job for Telecom Anomaly Detection
Simulates daily scheduled scoring pipeline:
  1. Ingests daily subscriber usage & transaction records
  2. Extracts engineered features
  3. Evaluates Isolation Forest anomaly detector
  4. Generates non-technical reason codes and recommended actions
  5. Writes prioritized alerts to SQLite review table and CSV
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

# Add project root to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.config import (
    DATA_DIR,
    DB_PATH,
    TOP_1_PERCENT_TARGET,
    PRECISION_TARGET,
)
from src.feature_engineering import TelecomFeatureEngineer
from src.models import ModelBenchmark
from src.explainability import AnomalyExplainer


def run_daily_batch_scoring(
    input_csv_path: str = None,
    output_db_path: str = DB_PATH,
    top_cutoff_pct: float = TOP_1_PERCENT_TARGET,
):
    print("=" * 78)
    print("  ANANTHAPURI FIBRENET - DAILY ANOMALY DETECTION BATCH SCORING JOB")
    print(f"  Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 78)

    if input_csv_path is None:
        input_csv_path = os.path.join(DATA_DIR, "telecom_subscriber_records.csv")

    if not os.path.exists(input_csv_path):
        from src.data_generator import generate_telecom_dataset
        df = generate_telecom_dataset(50000)
        df.to_csv(input_csv_path, index=False)
    else:
        df = pd.read_csv(input_csv_path)

    n_total = len(df)
    print(f"[*] Ingested daily batch of {n_total:,} subscriber telemetry records.")

    # 1. Feature Engineering
    print("[*] Computing behavioral deviations and peer group metrics...")
    fe = TelecomFeatureEngineer()
    features_df = fe.fit_transform(df)

    # 2. Model Scoring (Isolation Forest Production Engine)
    print("[*] Running Isolation Forest scoring engine...")
    benchmark = ModelBenchmark(contamination=0.015)
    benchmark.fit(features_df)
    scores = benchmark.get_scores(features_df, "Isolation_Forest")
    df["AnomalyScore"] = scores

    # 3. Operational Cutoff (Top 1% Review Queue)
    k_cutoff = max(10, int(n_total * top_cutoff_pct))
    threshold = float(np.partition(scores, -k_cutoff)[-k_cutoff])
    print(f"[+] Top {top_cutoff_pct*100:.1f}% priority threshold: {threshold:.4f} (Quota: {k_cutoff:,} items)")

    # 4. Reason Code Assignment & Explainability
    print("[*] Assigning non-technical reason codes & explanations...")
    explainer = AnomalyExplainer()
    review_table = explainer.generate_review_table(df, features_df, scores)

    # Prioritize: High-score items that exceed threshold
    flagged_alerts = review_table[review_table["AnomalyScore"] >= threshold].copy()
    flagged_alerts = flagged_alerts.sort_values("AnomalyScore", ascending=False).reset_index(drop=True)

    # 5. Persist to SQLite Database and CSV
    os.makedirs(os.path.dirname(output_db_path), exist_ok=True)
    with sqlite3.connect(output_db_path) as conn:
        flagged_alerts.to_sql("daily_review_queue", conn, if_exists="replace", index=False)
        review_table.head(1000).to_sql("all_scored_telemetry", conn, if_exists="replace", index=False)

    csv_out = os.path.join(DATA_DIR, "daily_review_queue.csv")
    flagged_alerts.to_csv(csv_out, index=False)

    # 6. Calculate Workload Reduction vs Manual Review
    # Manual review was scanning ~2,000 raw suspicious records/day
    manual_baseline_volume = 2000
    ai_volume = len(flagged_alerts)
    workload_reduction_pct = ((manual_baseline_volume - ai_volume) / manual_baseline_volume) * 100

    print("\n" + "=" * 78)
    print("  DAILY BATCH SCORING SUMMARY & OPERATIONAL IMPACT")
    print("=" * 78)
    print(f"  Total Ingested Records:      {n_total:,}")
    print(f"  Flagged High-Priority Alerts:{ai_volume:,} (Top {ai_volume/n_total*100:.2f}%)")
    print(f"  Prior Manual Review Volume:  ~{manual_baseline_volume:,} records/day")
    print(f"  Staff Workload Reduction:    {workload_reduction_pct:.1f}% (Target: >= 50%)")
    print(f"  Database Table Populated:    {output_db_path} -> daily_review_queue")
    print(f"  CSV Review Queue Exported:   {csv_out}")

    print("\n[Alert Breakdown by Reason Code]:")
    breakdown = flagged_alerts["ReasonCode"].value_counts()
    for code, count in breakdown.items():
        title = explainer.reason_catalog.get(code, {}).get("title", code)
        print(f"    - {code:<26} ({title}): {count:>4} alerts ({count/ai_volume*100:.1f}%)")

    print("=" * 78 + "\n")
    return flagged_alerts, benchmark, fe


if __name__ == "__main__":
    run_daily_batch_scoring()
