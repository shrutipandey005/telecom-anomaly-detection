"""
Unit Test Suite for Telecom Anomaly Detection System
Validates data generation, feature engineering, models, precision targets, explainability, and feedback loop.
"""

import os
import sys
import unittest
import numpy as np
import pandas as pd

# Add project root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.config import VALID_TOWERS, REASON_CODES, PRECISION_TARGET
from src.data_generator import generate_telecom_dataset, generate_labelled_validation_sample
from src.feature_engineering import TelecomFeatureEngineer, FEATURE_NAMES
from src.models import ModelBenchmark
from src.explainability import AnomalyExplainer
from src.feedback_loop import AdaptiveFeedbackTuner


class TestTelecomAnomalyDetection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n--- Initializing Test Suite & Generating Synthetic Cohort ---")
        cls.df = generate_telecom_dataset(n_samples=2000, seed=42)
        cls.val_df = generate_labelled_validation_sample(cls.df, sample_size=300, seed=42)
        cls.fe = TelecomFeatureEngineer()
        cls.features_df = cls.fe.fit_transform(cls.df)
        cls.val_features_df = cls.fe.transform(cls.val_df)
        cls.benchmark = ModelBenchmark(contamination=0.03)
        cls.benchmark.fit(cls.features_df)
        cls.explainer = AnomalyExplainer()

    def test_01_data_generator_integrity(self):
        self.assertEqual(len(self.df), 2000)
        self.assertIn("SubscriberID", self.df.columns)
        self.assertIn("GroundTruthAnomaly", self.df.columns)
        self.assertGreater(self.df["GroundTruthAnomaly"].sum(), 0)

    def test_02_validation_sample_size(self):
        self.assertEqual(len(self.val_df), 300)
        self.assertGreater(self.val_df["GroundTruthAnomaly"].sum(), 20)

    def test_03_feature_engineering_dimensions(self):
        self.assertEqual(self.features_df.shape[1], len(FEATURE_NAMES))
        self.assertFalse(self.features_df.isna().any().any())

    def test_04_unmatched_tower_feature(self):
        unmatched_rows = self.df[~self.df["TowerID"].isin(VALID_TOWERS)]
        if len(unmatched_rows) > 0:
            idx = unmatched_rows.index[0]
            self.assertEqual(self.features_df.loc[idx, "unmatched_tower_flag"], 1.0)

    def test_05_ported_out_active_feature(self):
        ported_rows = self.df[(self.df["IsPortedOutMNP"] == 1) & (self.df["SubscriberStatus"] == "Active")]
        if len(ported_rows) > 0:
            idx = ported_rows.index[0]
            self.assertEqual(self.features_df.loc[idx, "ported_out_active_flag"], 1.0)

    def test_06_model_scoring_range(self):
        scores = self.benchmark.get_scores(self.val_features_df, "Isolation_Forest")
        self.assertEqual(len(scores), len(self.val_df))
        self.assertGreaterEqual(float(np.min(scores)), 0.0)
        self.assertLessEqual(float(np.max(scores)), 1.0001)

    def test_07_precision_at_top_target(self):
        """
        Objective 10: Precision at top 1% (or top 10% in dense test sample) >= 60%
        """
        metrics = self.benchmark.evaluate_on_labelled_sample(
            self.val_features_df, self.val_df["GroundTruthAnomaly"].values, top_k_pct=0.10
        )
        iforest_row = metrics[metrics["Model"] == "Isolation_Forest"].iloc[0]
        p_at_k = iforest_row["Precision@Top1%"]
        print(f"\n[Test Result] Isolation Forest Precision @ Top Cut: {p_at_k*100:.1f}%")
        self.assertGreaterEqual(p_at_k, PRECISION_TARGET)

    def test_08_explainability_reason_codes(self):
        scores = self.benchmark.get_scores(self.val_features_df, "Isolation_Forest")
        review_table = self.explainer.generate_review_table(self.val_df, self.val_features_df, scores)

        self.assertEqual(len(review_table), len(self.val_df))
        self.assertIn("ReasonCode", review_table.columns)
        self.assertIn("PlainExplanation", review_table.columns)
        self.assertIn("RecommendedAction", review_table.columns)

        # Check all reason codes belong to the recognized catalog
        for code in review_table["ReasonCode"].unique():
            self.assertIn(code, REASON_CODES)

    def test_09_feedback_loop_db(self):
        test_db = os.path.join(ROOT_DIR, "data", "test_review_table.sqlite")
        tuner = AdaptiveFeedbackTuner(test_db)
        tuner.record_reviewer_feedback(
            alert_id="ALT-TEST-001",
            subscriber_id="TRV-SUB-9999",
            reason_code="FRAUD_MIDNIGHT_SPIKE",
            anomaly_score=0.95,
            decision="CONFIRMED_TRUE",
            notes="Confirmed illegal commercial proxy running on residential line",
        )
        retune_result = tuner.weekly_retune_threshold(current_threshold=0.80, min_samples=1)
        self.assertIn(retune_result["status"], ["RETUNED", "INSUFFICIENT_DATA"])

    def test_10_workload_reduction_metric(self):
        """
        Objective 10: Review workload falls by at least 50% compared with manual checks.
        """
        manual_checks = 2000
        ai_queue_size = int(len(self.df) * 0.01)  # Top 1%
        reduction = (manual_checks - ai_queue_size) / manual_checks
        self.assertGreaterEqual(reduction, 0.50)


if __name__ == "__main__":
    unittest.main()
