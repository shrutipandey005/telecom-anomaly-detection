"""
Synthetic Data Generator for Telecom Anomaly Detection
Simulates Thiruvananthapuram Fibre Broadband Provider ("Ananthapuri FibreNet")
"""

import os
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.config import (
    DATA_DIR,
    VALID_TOWERS,
    VALID_CIRCLE_CODES,
    BROADBAND_PLANS,
)


def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)


def generate_telecom_dataset(n_samples=50000, seed=42):
    """
    Generates synthetic telecom subscriber dataset simulating daily operations.
    Includes normal subscriber usage patterns and realistic injected anomalies:
      - 0.5% Tower IDs not matching master list
      - 0.3% Ported-out subscribers still marked Active
      - 0.4% Recharge records missing Circle Code
      - 0.4% Midnight bandwidth spikes / proxy redistribution
      - 0.3% High recharge velocity (prepaid carding)
      - 0.3% Silent fibre breaks (repeated complaints + zero usage)
    """
    set_seed(seed)
    print(f"[*] Generating {n_samples:,} subscriber telemetry records...")

    plan_names = list(BROADBAND_PLANS.keys())
    plan_weights = [0.45, 0.35, 0.15, 0.05]  # Most on 50M/100M

    subscriber_ids = [f"TRV-SUB-{i:07d}" for i in range(100001, 100001 + n_samples)]
    assigned_plans = np.random.choice(plan_names, size=n_samples, p=plan_weights)
    assigned_towers = np.random.choice(VALID_TOWERS, size=n_samples)
    assigned_circles = np.random.choice(VALID_CIRCLE_CODES, size=n_samples, p=[0.90, 0.10])

    # Baseline daily usage (GB) per plan
    base_usage = {
        "Fibre_Basic_50M": (12.0, 4.0),
        "Fibre_Value_100M": (25.0, 7.0),
        "Fibre_Super_300M": (48.0, 12.0),
        "Fibre_Biz_1G": (110.0, 25.0),
    }

    daily_usage_gb = np.zeros(n_samples)
    rolling_7d_avg_gb = np.zeros(n_samples)
    rolling_7d_std_gb = np.zeros(n_samples)
    midnight_usage_gb = np.zeros(n_samples)

    for i in range(n_samples):
        mean_u, std_u = base_usage[assigned_plans[i]]
        # Normal rolling baseline
        roll_mean = max(1.0, np.random.normal(mean_u, std_u * 0.4))
        roll_std = max(0.5, roll_mean * 0.2)
        today_u = max(0.5, np.random.normal(roll_mean, roll_std))

        # Midnight usage (00:00 - 06:00): normally 8% - 15% of daily usage
        midnight_pct = np.random.uniform(0.08, 0.18)
        mid_u = today_u * midnight_pct

        daily_usage_gb[i] = round(today_u, 2)
        rolling_7d_avg_gb[i] = round(roll_mean, 2)
        rolling_7d_std_gb[i] = round(roll_std, 2)
        midnight_usage_gb[i] = round(mid_u, 2)

    # Recharge telemetry
    monthly_recharge_amounts = [BROADBAND_PLANS[p]["price_inr"] for p in assigned_plans]
    recharge_counts_24h = np.random.choice([0, 1, 2], size=n_samples, p=[0.70, 0.28, 0.02])

    # Complaint telemetry
    complaint_counts_30d = np.random.choice([0, 1, 2, 3], size=n_samples, p=[0.82, 0.13, 0.04, 0.01])
    resolution_time_hrs = np.random.exponential(scale=6.0, size=n_samples) + 1.0

    # Subscriber status
    sub_statuses = np.array(["Active"] * n_samples, dtype=object)
    is_ported_out = np.zeros(n_samples, dtype=int)

    # Ground-truth anomaly labels (0 = Normal, 1 = Genuine Anomaly)
    ground_truth = np.zeros(n_samples, dtype=int)
    anomaly_types = np.array(["NORMAL"] * n_samples, dtype=object)

    # Injected Anomaly 1: Unmatched Tower IDs (~0.5%)
    n_unmatched = int(n_samples * 0.005)
    unmatched_indices = np.random.choice(n_samples, size=n_unmatched, replace=False)
    bogus_towers = ["TRV-UNKN-99", "EXT-BLR-01", "TRV-TEMP-77", "TRV-UNKNOWN-00", "TRV-INVALID"]
    for idx in unmatched_indices:
        assigned_towers[idx] = random.choice(bogus_towers)
        ground_truth[idx] = 1
        anomaly_types[idx] = "DATA_UNMATCHED_TOWER"

    # Injected Anomaly 2: Ported-out subscribers still marked Active (~0.3%)
    n_ported = int(n_samples * 0.003)
    ported_indices = np.random.choice(
        [i for i in range(n_samples) if ground_truth[i] == 0], size=n_ported, replace=False
    )
    for idx in ported_indices:
        is_ported_out[idx] = 1  # Marked ported-out in MNP
        sub_statuses[idx] = "Active"  # But active in billing!
        ground_truth[idx] = 1
        anomaly_types[idx] = "DATA_PORTED_OUT_ACTIVE"

    # Injected Anomaly 3: Missing Circle Codes in recharge records (~0.4%)
    n_circle = int(n_samples * 0.004)
    circle_indices = np.random.choice(
        [i for i in range(n_samples) if ground_truth[i] == 0], size=n_circle, replace=False
    )
    for idx in circle_indices:
        assigned_circles[idx] = "MISSING"
        ground_truth[idx] = 1
        anomaly_types[idx] = "DATA_MISSING_CIRCLE"

    # Injected Anomaly 4: Midnight Heavy Bandwidth Spike (~0.4%)
    n_midnight = int(n_samples * 0.004)
    midnight_indices = np.random.choice(
        [i for i in range(n_samples) if ground_truth[i] == 0 and assigned_plans[i] == "Fibre_Basic_50M"],
        size=n_midnight,
        replace=False,
    )
    for idx in midnight_indices:
        # Massive midnight burst (e.g. 180 - 450 GB on a 50Mbps residential plan)
        spike_gb = np.random.uniform(180.0, 480.0)
        daily_usage_gb[idx] = round(rolling_7d_avg_gb[idx] + spike_gb, 2)
        midnight_usage_gb[idx] = round(spike_gb * np.random.uniform(0.75, 0.95), 2)
        ground_truth[idx] = 1
        anomaly_types[idx] = "FRAUD_MIDNIGHT_SPIKE"

    # Injected Anomaly 5: High Recharge Velocity (~0.3%)
    n_velocity = int(n_samples * 0.003)
    velocity_indices = np.random.choice(
        [i for i in range(n_samples) if ground_truth[i] == 0], size=n_velocity, replace=False
    )
    for idx in velocity_indices:
        recharge_counts_24h[idx] = np.random.randint(4, 8)  # 4-7 recharges in 24 hours!
        monthly_recharge_amounts[idx] = monthly_recharge_amounts[idx] * recharge_counts_24h[idx]
        ground_truth[idx] = 1
        anomaly_types[idx] = "FRAUD_RECHARGE_VELOCITY"

    # Injected Anomaly 6: Silent Fibre Faults (~0.3%)
    n_silent = int(n_samples * 0.003)
    silent_indices = np.random.choice(
        [i for i in range(n_samples) if ground_truth[i] == 0], size=n_silent, replace=False
    )
    for idx in silent_indices:
        # High complaints (4-7 tickets) but virtually 0.0 GB usage
        complaint_counts_30d[idx] = np.random.randint(4, 8)
        daily_usage_gb[idx] = round(np.random.uniform(0.0, 0.05), 2)
        midnight_usage_gb[idx] = 0.0
        resolution_time_hrs[idx] = round(np.random.uniform(48.0, 120.0), 1)
        ground_truth[idx] = 1
        anomaly_types[idx] = "FAULT_SILENT_OUTAGE"

    # Assemble master DataFrame
    df = pd.DataFrame(
        {
            "SubscriberID": subscriber_ids,
            "PlanName": assigned_plans,
            "TowerID": assigned_towers,
            "CircleCode": assigned_circles,
            "SubscriberStatus": sub_statuses,
            "IsPortedOutMNP": is_ported_out,
            "DailyUsageGB": daily_usage_gb,
            "Rolling7dAvgGB": rolling_7d_avg_gb,
            "Rolling7dStdGB": rolling_7d_std_gb,
            "MidnightUsageGB": midnight_usage_gb,
            "RechargeAmountINR": monthly_recharge_amounts,
            "RechargeCount24h": recharge_counts_24h,
            "ComplaintCount30d": complaint_counts_30d,
            "AvgResolutionHours": np.round(resolution_time_hrs, 1),
            "GroundTruthAnomaly": ground_truth,
            "AnomalyCategory": anomaly_types,
        }
    )

    print(f"[+] Dataset created with {len(df):,} rows.")
    print(f"[*] Anomaly breakdown: Total Anomalies = {df['GroundTruthAnomaly'].sum():,} ({df['GroundTruthAnomaly'].mean()*100:.2f}%)")
    for cat, count in df["AnomalyCategory"].value_counts().items():
        if cat != "NORMAL":
            print(f"    - {cat:<26}: {count:>4} cases")

    return df


def generate_labelled_validation_sample(df, sample_size=300, seed=42):
    """
    Creates a small, rigorously annotated benchmark sample of 300 cases
    as requested in Objective 6 (evaluating Precision at top 1%).
    Ensures proportional representation across anomaly types.
    """
    set_seed(seed)
    # Stratified selection: ~70 anomalies and ~230 normal cases
    anomalies_df = df[df["GroundTruthAnomaly"] == 1]
    normal_df = df[df["GroundTruthAnomaly"] == 0]

    n_anom = min(75, len(anomalies_df))
    n_norm = sample_size - n_anom

    sample_anom = anomalies_df.sample(n=n_anom, random_state=seed)
    sample_norm = normal_df.sample(n=n_norm, random_state=seed)

    validation_300 = pd.concat([sample_anom, sample_norm]).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    validation_path = os.path.join(DATA_DIR, "labelled_validation_300.csv")
    validation_300.to_csv(validation_path, index=False)
    print(f"[+] Saved 300-case labelled validation dataset to: {validation_path}")
    print(f"    - Normal records: {n_norm}")
    print(f"    - True Anomalies: {n_anom} ({n_anom/sample_size*100:.1f}%)")
    return validation_300


if __name__ == "__main__":
    df = generate_telecom_dataset(50000)
    csv_path = os.path.join(DATA_DIR, "telecom_subscriber_records.csv")
    df.to_csv(csv_path, index=False)
    print(f"[+] Saved raw records to: {csv_path}")

    val_df = generate_labelled_validation_sample(df, sample_size=300)
