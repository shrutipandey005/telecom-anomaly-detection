"""
Feature Engineering Pipeline for Telecom Anomaly Detection
Engineers behavioral deviations, peer group comparisons, and rare categorical interactions.
"""

import numpy as np
import pandas as pd
from src.config import VALID_TOWERS, VALID_CIRCLE_CODES, BROADBAND_PLANS


FEATURE_NAMES = [
    "usage_rolling_deviation",
    "midnight_ratio",
    "peer_usage_ratio",
    "peer_usage_zscore",
    "recharge_velocity",
    "recharge_amount_ratio",
    "complaint_to_usage_ratio",
    "unmatched_tower_flag",
    "ported_out_active_flag",
    "missing_circle_flag",
    "rare_plan_tower_penalty",
]


class TelecomFeatureEngineer:
    def __init__(self):
        self.plan_usage_stats_ = {}
        self.plan_tower_freq_ = {}

    def fit(self, df: pd.DataFrame):
        """
        Learns peer cohort statistics (mean, std) and plan-tower joint distribution.
        """
        # Learn plan cohort usage distribution
        for plan in df["PlanName"].unique():
            subset = df[df["PlanName"] == plan]["DailyUsageGB"]
            mean_val = float(subset.mean()) if len(subset) > 0 else 20.0
            std_val = float(subset.std()) if len(subset) > 1 and subset.std() > 0 else 5.0
            self.plan_usage_stats_[plan] = (mean_val, std_val)

        # Learn joint plan-tower categorical frequency
        joint_series = df["PlanName"] + "||" + df["TowerID"]
        freq_table = joint_series.value_counts(normalize=True).to_dict()
        self.plan_tower_freq_ = freq_table

        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforms raw records into the engineered numerical feature matrix.
        """
        features_df = pd.DataFrame(index=df.index)

        # 1. Deviation from rolling 7-day baseline
        features_df["usage_rolling_deviation"] = (
            (df["DailyUsageGB"] - df["Rolling7dAvgGB"]) / (df["Rolling7dStdGB"] + 1e-4)
        ).clip(-10.0, 50.0)

        # 2. Midnight bandwidth ratio (00:00 - 06:00)
        features_df["midnight_ratio"] = (
            df["MidnightUsageGB"] / (df["DailyUsageGB"] + 1e-4)
        ).clip(0.0, 1.0)

        # 3 & 4. Peer-group comparisons by broadband plan cohort
        peer_means = df["PlanName"].map(lambda p: self.plan_usage_stats_.get(p, (20.0, 5.0))[0])
        peer_stds = df["PlanName"].map(lambda p: self.plan_usage_stats_.get(p, (20.0, 5.0))[1])

        features_df["peer_usage_ratio"] = (df["DailyUsageGB"] / (peer_means + 1e-4)).clip(0.0, 30.0)
        features_df["peer_usage_zscore"] = ((df["DailyUsageGB"] - peer_means) / (peer_stds + 1e-4)).clip(-5.0, 30.0)

        # 5. Recharge velocity (count in 24 hours)
        features_df["recharge_velocity"] = df["RechargeCount24h"].astype(float)

        # 6. Recharge amount deviation from nominal plan price
        nominal_prices = df["PlanName"].map(
            lambda p: BROADBAND_PLANS.get(p, {"price_inr": 499})["price_inr"]
        )
        features_df["recharge_amount_ratio"] = (df["RechargeAmountINR"] / (nominal_prices + 1e-4)).clip(0.0, 20.0)

        # 7. Complaint to usage ratio (identifies silent fibre faults)
        features_df["complaint_to_usage_ratio"] = (
            df["ComplaintCount30d"] / (df["DailyUsageGB"] + 0.1)
        ).clip(0.0, 100.0)

        # 8. Unmatched tower flag (1 if missing from Master Topology)
        features_df["unmatched_tower_flag"] = (
            ~df["TowerID"].isin(VALID_TOWERS)
        ).astype(float)

        # 9. Ported-out active flag (1 if ported out in MNP but active)
        features_df["ported_out_active_flag"] = (
            (df["IsPortedOutMNP"] == 1) & (df["SubscriberStatus"] == "Active")
        ).astype(float)

        # 10. Missing circle code flag
        features_df["missing_circle_flag"] = (
            df["CircleCode"].isna()
            | (df["CircleCode"] == "MISSING")
            | (~df["CircleCode"].isin(VALID_CIRCLE_CODES))
        ).astype(float)

        # 11. Rare categorical combinations penalty: -log(P(plan, tower))
        joint_series = df["PlanName"] + "||" + df["TowerID"]
        min_freq = 1e-5
        probs = joint_series.map(lambda k: self.plan_tower_freq_.get(k, min_freq))
        features_df["rare_plan_tower_penalty"] = -np.log(np.maximum(probs, min_freq))

        return features_df[FEATURE_NAMES]

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        return self.fit(df).transform(df)


if __name__ == "__main__":
    import os
    from src.config import DATA_DIR
    csv_path = os.path.join(DATA_DIR, "telecom_subscriber_records.csv")
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        fe = TelecomFeatureEngineer()
        feats = fe.fit_transform(df)
        print(f"[+] Feature matrix shape: {feats.shape}")
        print(feats.describe().T[["mean", "std", "min", "max"]])
