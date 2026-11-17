"""
Reviewer Feedback Loop & Adaptive Threshold Tuning
Implements Objective 9: Reviewers mark alerts as true/false positive,
and the operational anomaly threshold is re-tuned weekly.
"""

import os
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any
from src.config import DB_PATH, TOP_1_PERCENT_TARGET, PRECISION_TARGET


class AdaptiveFeedbackTuner:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_feedback (
                    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id TEXT NOT NULL,
                    subscriber_id TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    anomaly_score REAL NOT NULL,
                    reviewer_decision TEXT NOT NULL, -- CONFIRMED_TRUE, FALSE_POSITIVE
                    reviewer_notes TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS threshold_history (
                    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operational_threshold REAL NOT NULL,
                    precision_observed REAL NOT NULL,
                    feedback_count INTEGER NOT NULL,
                    action_taken TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def record_reviewer_feedback(
        self,
        alert_id: str,
        subscriber_id: str,
        reason_code: str,
        anomaly_score: float,
        decision: str,
        notes: str = "",
    ):
        """
        Records human-in-the-loop decision from operational staff.
        """
        assert decision in ["CONFIRMED_TRUE", "FALSE_POSITIVE"], "Decision must be CONFIRMED_TRUE or FALSE_POSITIVE"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO review_feedback (alert_id, subscriber_id, reason_code, anomaly_score, reviewer_decision, reviewer_notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (alert_id, subscriber_id, reason_code, float(anomaly_score), decision, notes),
            )

    def weekly_retune_threshold(self, current_threshold: float, min_samples: int = 20) -> Dict[str, Any]:
        """
        Re-tunes the operational decision threshold based on empirical precision.
        Target: Maintain Precision >= 60% while minimizing review volume.
        """
        with sqlite3.connect(self.db_path) as conn:
            df_fb = pd.read_sql_query("SELECT * FROM review_feedback", conn)

        if len(df_fb) < min_samples:
            return {
                "status": "INSUFFICIENT_DATA",
                "feedback_count": len(df_fb),
                "required": min_samples,
                "current_threshold": current_threshold,
                "new_threshold": current_threshold,
                "action": "Maintain current threshold until sufficient feedback is logged.",
            }

        total = len(df_fb)
        tp = (df_fb["reviewer_decision"] == "CONFIRMED_TRUE").sum()
        fp = (df_fb["reviewer_decision"] == "FALSE_POSITIVE").sum()
        observed_precision = tp / (tp + fp) if total > 0 else 0.0

        # Adaptive threshold adjustment logic
        new_threshold = current_threshold
        if observed_precision < PRECISION_TARGET:
            # False alarms are too high (fatiguing review staff) -> increase threshold by 5%
            delta = (PRECISION_TARGET - observed_precision) * 0.15
            new_threshold = min(0.99, current_threshold + delta)
            action = f"TIGHTENED: Precision ({observed_precision*100:.1f}%) < Target ({PRECISION_TARGET*100:.0f}%). Raised threshold by +{delta:.4f} to filter borderline false positives."
        elif observed_precision > 0.85:
            # High precision with safe room -> slightly lower threshold by 2% to catch subtle fraud
            delta = 0.02
            new_threshold = max(0.50, current_threshold - delta)
            action = f"EXPANDED: Precision is exceptionally high ({observed_precision*100:.1f}%). Lowered threshold by -{delta:.4f} to surface additional latent anomalies."
        else:
            action = f"MAINTAINED: Precision ({observed_precision*100:.1f}%) is within optimal operating window [60%, 85%]."

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO threshold_history (operational_threshold, precision_observed, feedback_count, action_taken)
                VALUES (?, ?, ?, ?)
                """,
                (float(new_threshold), float(observed_precision), total, action),
            )

        return {
            "status": "RETUNED",
            "feedback_count": total,
            "true_positives": int(tp),
            "false_positives": int(fp),
            "observed_precision": round(observed_precision, 4),
            "previous_threshold": round(current_threshold, 4),
            "new_threshold": round(new_threshold, 4),
            "action": action,
        }
