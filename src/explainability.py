"""
Explainability & Reason Code Assignment Engine
Translates model scores and feature deviations into plain-language reason codes
for non-technical operations and revenue assurance reviewers.
"""

import pandas as pd
from typing import Dict, Any, List
from src.config import REASON_CODES


class AnomalyExplainer:
    def __init__(self):
        self.reason_catalog = REASON_CODES

    def explain_record(self, raw_row: pd.Series, feature_row: pd.Series, anomaly_score: float) -> Dict[str, Any]:
        """
        Determines primary and secondary reason codes and plain-English narrative.
        """
        code = "ANOMALY_PEER_OUTLIER"
        explanation = "Subscriber exhibits high multi-dimensional deviation from standard plan cohort behavior."
        action = "Inspect historical usage and contact subscriber if trend persists."

        # Rule 1: Ported-out active subscriber
        if feature_row.get("ported_out_active_flag", 0) > 0.5:
            code = "DATA_PORTED_OUT_ACTIVE"
            explanation = (
                f"Subscriber {raw_row.get('SubscriberID')} is flagged as Ported-Out in the MNP registry, "
                f"yet the billing CRM shows active data sessions."
            )
            action = "Immediately suspend billing account and audit MNP port-completion logs."

        # Rule 2: Unmatched Tower ID
        elif feature_row.get("unmatched_tower_flag", 0) > 0.5:
            code = "DATA_UNMATCHED_TOWER"
            explanation = (
                f"Routing Tower ID '{raw_row.get('TowerID')}' is not recognized in the Thiruvananthapuram "
                f"Master Topology Registry. Traffic may be misrouted or improperly provisioned."
            )
            action = "Dispatch NOC network engineering ticket to audit OLT routing table."

        # Rule 3: Missing regulatory circle code
        elif feature_row.get("missing_circle_flag", 0) > 0.5:
            code = "DATA_MISSING_CIRCLE"
            explanation = (
                f"Recharge/CDR record is missing mandatory TRAI circle code ('KL'). Value: '{raw_row.get('CircleCode')}'."
            )
            action = "Reprocess record through billing mediation gateway to backfill circle identifier."

        # Rule 4: High recharge velocity (fraud / carding)
        elif feature_row.get("recharge_velocity", 0) >= 3.0 or feature_row.get("recharge_amount_ratio", 0) >= 3.0:
            code = "FRAUD_RECHARGE_VELOCITY"
            count = int(raw_row.get("RechargeCount24h", 0))
            amt = raw_row.get("RechargeAmountINR", 0)
            explanation = (
                f"Subscriber initiated {count} recharges in 24 hours totaling ₹{amt:,}, exceeding normal frequency limits."
            )
            action = "Hold recharge credits and verify payment gateway transaction authorization."

        # Rule 5: Silent fibre fault (High complaints + near zero usage)
        elif (
            feature_row.get("complaint_to_usage_ratio", 0) >= 15.0
            or (raw_row.get("ComplaintCount30d", 0) >= 3 and raw_row.get("DailyUsageGB", 0) < 1.0)
        ):
            code = "FAULT_SILENT_OUTAGE"
            tix = int(raw_row.get("ComplaintCount30d", 0))
            usage = raw_row.get("DailyUsageGB", 0)
            explanation = (
                f"Subscriber logged {tix} complaints in past 30 days while consumption dropped to {usage:.2f} GB. "
                f"High probability of undetected optical fibre line break or ONT power failure."
            )
            action = "Dispatch field technician to test optical power at customer ONT premises."

        # Rule 6: Midnight bandwidth burst / proxy fraud
        elif feature_row.get("midnight_ratio", 0) >= 0.50 and feature_row.get("usage_rolling_deviation", 0) >= 3.0:
            code = "FRAUD_MIDNIGHT_SPIKE"
            daily = raw_row.get("DailyUsageGB", 0)
            mid = raw_row.get("MidnightUsageGB", 0)
            roll = raw_row.get("Rolling7dAvgGB", 0)
            explanation = (
                f"Daily consumption reached {daily:.1f} GB (rolling avg: {roll:.1f} GB). "
                f"{mid:.1f} GB ({(mid/(daily+1e-4))*100:.1f}%) consumed during off-peak midnight hours (00:00-06:00)."
            )
            action = "Check Fair Usage Policy (FUP) compliance and investigate potential ISP line resale."

        # Rule 7: Rare plan-tower combo or cohort outlier
        elif feature_row.get("rare_plan_tower_penalty", 0) > 8.0:
            code = "ANOMALY_PEER_OUTLIER"
            plan = raw_row.get("PlanName")
            tower = raw_row.get("TowerID")
            explanation = (
                f"Unusual combination of plan '{plan}' provisioned on OLT/Tower '{tower}' with high usage divergence."
            )
            action = "Review provisioning tier in CRM and ensure correct VLAN configuration."

        catalog_meta = self.reason_catalog.get(code, self.reason_catalog["ANOMALY_PEER_OUTLIER"])

        return {
            "ReasonCode": code,
            "ReasonTitle": catalog_meta["title"],
            "Category": catalog_meta["category"],
            "Priority": catalog_meta["priority"],
            "PlainExplanation": explanation,
            "RecommendedAction": action,
            "AnomalyScore": round(float(anomaly_score), 4),
        }

    def generate_review_table(
        self, raw_df: pd.DataFrame, features_df: pd.DataFrame, anomaly_scores: pd.Series
    ) -> pd.DataFrame:
        """
        Constructs the comprehensive review table for operations staff.
        """
        review_records = []
        for i in range(len(raw_df)):
            raw_row = raw_df.iloc[i]
            feat_row = features_df.iloc[i]
            score = anomaly_scores.iloc[i] if isinstance(anomaly_scores, pd.Series) else anomaly_scores[i]

            exp = self.explain_record(raw_row, feat_row, score)

            rec = {
                "AlertID": f"ALT-TRV-{100000 + i}",
                "SubscriberID": raw_row["SubscriberID"],
                "PlanName": raw_row["PlanName"],
                "TowerID": raw_row["TowerID"],
                "AnomalyScore": exp["AnomalyScore"],
                "ReasonCode": exp["ReasonCode"],
                "ReasonTitle": exp["ReasonTitle"],
                "Category": exp["Category"],
                "Priority": exp["Priority"],
                "PlainExplanation": exp["PlainExplanation"],
                "RecommendedAction": exp["RecommendedAction"],
                "ReviewStatus": "PENDING",  # PENDING, CONFIRMED_TRUE, FALSE_POSITIVE
                "DailyUsageGB": raw_row["DailyUsageGB"],
                "Rolling7dAvgGB": raw_row["Rolling7dAvgGB"],
                "ComplaintCount": raw_row["ComplaintCount30d"],
            }
            review_records.append(rec)

        return pd.DataFrame(review_records)
