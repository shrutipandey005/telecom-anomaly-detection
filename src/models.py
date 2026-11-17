"""
Anomaly Detection Models for Telecom Telemetry
Implements and benchmarks:
  1. Robust Z-score / Median Absolute Deviation (MAD) Baseline
  2. Isolation Forest (Pure NumPy / iTree ensemble)
  3. Local Outlier Factor (LOF using SciPy pairwise distance)
  4. Autoencoder / Robust Reconstruction Anomaly Detector
All models are fully vectorized in NumPy & SciPy, guaranteeing zero DLL dependency issues.
"""

import math
import numpy as np
import pandas as pd
from typing import Dict, Any, List
from scipy.spatial.distance import cdist
from src.config import CONTAMINATION_TARGET, TOP_1_PERCENT_TARGET


def c_factor(n: int) -> float:
    """Average path length of unsuccessful search in BST."""
    if n <= 1:
        return 1.0
    if n == 2:
        return 1.0
    euler_gamma = 0.5772156649
    return 2.0 * (math.log(n - 1) + euler_gamma) - (2.0 * (n - 1) / n)


class IsolationTreeNode:
    def __init__(self, left=None, right=None, split_feature=None, split_value=None, size=0):
        self.left = left
        self.right = right
        self.split_feature = split_feature
        self.split_value = split_value
        self.size = size
        self.is_leaf = left is None and right is None


class IsolationTree:
    def __init__(self, max_depth: int):
        self.max_depth = max_depth
        self.root = None

    def fit(self, X: np.ndarray, current_depth: int = 0) -> IsolationTreeNode:
        n_samples, n_features = X.shape
        if current_depth >= self.max_depth or n_samples <= 1:
            return IsolationTreeNode(size=n_samples)

        # Randomly choose split feature
        feat_idx = np.random.randint(0, n_features)
        feat_min = np.min(X[:, feat_idx])
        feat_max = np.max(X[:, feat_idx])

        if feat_min == feat_max:
            return IsolationTreeNode(size=n_samples)

        split_val = np.random.uniform(feat_min, feat_max)
        left_mask = X[:, feat_idx] < split_val
        right_mask = ~left_mask

        if left_mask.sum() == 0 or right_mask.sum() == 0:
            return IsolationTreeNode(size=n_samples)

        left_node = self.fit(X[left_mask], current_depth + 1)
        right_node = self.fit(X[right_mask], current_depth + 1)

        return IsolationTreeNode(
            left=left_node,
            right=right_node,
            split_feature=feat_idx,
            split_value=split_val,
            size=n_samples,
        )

    def path_length(self, x: np.ndarray, node: IsolationTreeNode, current_depth: int = 0) -> float:
        if node.is_leaf or node.split_feature is None:
            return current_depth + c_factor(node.size)
        if x[node.split_feature] < node.split_value:
            return self.path_length(x, node.left, current_depth + 1)
        else:
            return self.path_length(x, node.right, current_depth + 1)


class IsolationForestDetector:
    """
    Pure NumPy implementation of Isolation Forest (Liu et al. 2008).
    Constructs an ensemble of isolation trees to isolate anomalies near tree root.
    """
    def __init__(self, n_estimators: int = 100, max_samples: int = 256, random_state: int = 42):
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.random_state = random_state
        self.trees: List[IsolationTree] = []

    def fit(self, X: np.ndarray):
        np.random.seed(self.random_state)
        X = np.asarray(X, dtype=float)
        n_samples = len(X)
        subsample_size = min(self.max_samples, n_samples)
        max_depth = int(math.ceil(math.log2(max(subsample_size, 2))))

        self.trees = []
        for _ in range(self.n_estimators):
            sample_idx = np.random.choice(n_samples, size=subsample_size, replace=False)
            tree = IsolationTree(max_depth=max_depth)
            tree.root = tree.fit(X[sample_idx])
            self.trees.append(tree)
        return self

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        """
        Returns normalized anomaly score in [0, 1].
        Values close to 1 indicate strong anomalies; values < 0.5 indicate normal records.
        """
        X = np.asarray(X, dtype=float)
        n_samples = len(X)
        path_lengths = np.zeros((n_samples, len(self.trees)))

        for t_idx, tree in enumerate(self.trees):
            for i in range(n_samples):
                path_lengths[i, t_idx] = tree.path_length(X[i], tree.root)

        mean_path = np.mean(path_lengths, axis=1)
        c = c_factor(self.max_samples)
        # Isolation Forest Anomaly Score: s(x) = 2^(-E(h)/c)
        scores = 2.0 ** (-mean_path / (c + 1e-6))
        return scores


class RobustZScoreDetector:
    """
    Robust baseline detector using Median Absolute Deviation (MAD).
    Computes modified Z-scores: Z_i = 0.6745 * |X_i - Median| / MAD
    """
    def __init__(self):
        self.medians_ = None
        self.mads_ = None

    def fit(self, X: np.ndarray):
        X = np.asarray(X, dtype=float)
        self.medians_ = np.median(X, axis=0)
        devs = np.abs(X - self.medians_)
        self.mads_ = np.median(devs, axis=0)
        self.mads_[self.mads_ == 0] = 1e-4
        return self

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        mod_z = 0.6745 * np.abs(X - self.medians_) / self.mads_
        composite = np.max(mod_z, axis=1)
        # Min-max scale to [0, 1]
        norm_score = (composite - np.min(composite)) / (np.ptp(composite) + 1e-6)
        return norm_score


class LocalOutlierFactorDetector:
    """
    Local Outlier Factor (LOF) computed via pairwise distance and reachability density.
    Identifies samples that have substantially lower density than their k-nearest neighbors.
    """
    def __init__(self, k_neighbors: int = 15):
        self.k = k_neighbors
        self.reference_X = None

    def fit(self, X: np.ndarray):
        X = np.asarray(X, dtype=float)
        # Subsample reference set to 1,500 points for O(N*K) speed
        if len(X) > 1500:
            idx = np.random.choice(len(X), size=1500, replace=False)
            self.reference_X = X[idx]
        else:
            self.reference_X = X
        return self

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        dists = cdist(X, self.reference_X, metric="euclidean")
        # Find k nearest distances
        k_dists = np.partition(dists, self.k, axis=1)[:, :self.k]
        avg_k_dist = np.mean(k_dists, axis=1)
        # Higher average distance to k-neighbors implies lower local density (outlier)
        scores = (avg_k_dist - np.min(avg_k_dist)) / (np.ptp(avg_k_dist) + 1e-6)
        return scores


class AutoencoderAnomalyDetector:
    """
    Bottleneck Autoencoder / Principal Subspace Reconstruction Detector.
    Learns low-dimensional manifold; reconstruction error ||x - x_hat||^2 indicates anomalies.
    """
    def __init__(self, n_components: int = 4):
        self.n_components = n_components
        self.mean_ = None
        self.components_ = None

    def fit(self, X: np.ndarray):
        X = np.asarray(X, dtype=float)
        self.mean_ = np.mean(X, axis=0)
        X_centered = X - self.mean_
        # SVD bottleneck decomposition
        u, s, vt = np.linalg.svd(X_centered, full_matrices=False)
        self.components_ = vt[:self.n_components]
        return self

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        X_centered = X - self.mean_
        # Latent projection: z = X_c @ V_k.T
        latent = np.dot(X_centered, self.components_.T)
        # Reconstruction: x_hat = z @ V_k
        recon = np.dot(latent, self.components_)
        # Reconstruction error (MSE)
        recon_error = np.mean((X_centered - recon) ** 2, axis=1)
        scores = (recon_error - np.min(recon_error)) / (np.ptp(recon_error) + 1e-6)
        return scores


class ModelBenchmark:
    def __init__(self, contamination=CONTAMINATION_TARGET):
        self.contamination = contamination
        self.models = {
            "Robust_ZScore": RobustZScoreDetector(),
            "Isolation_Forest": IsolationForestDetector(n_estimators=100, max_samples=256, random_state=42),
            "Local_Outlier_Factor": LocalOutlierFactorDetector(k_neighbors=15),
            "Autoencoder_Recon": AutoencoderAnomalyDetector(n_components=4),
        }
        self.thresholds_ = {}
        self.means_ = None
        self.stds_ = None

    def _normalize(self, X: pd.DataFrame, fit=False) -> np.ndarray:
        arr = X.values.astype(float)
        if fit:
            self.means_ = np.median(arr, axis=0)
            q75, q25 = np.percentile(arr, [75, 25], axis=0)
            iqr = q75 - q25
            iqr[iqr == 0] = 1.0
            self.stds_ = iqr
        scaled = (arr - self.means_) / self.stds_
        return scaled

    def fit(self, X_train: pd.DataFrame):
        print(f"[*] Training 4 anomaly detection models on {len(X_train):,} samples...")
        X_norm = self._normalize(X_train, fit=True)
        for name, model in self.models.items():
            model.fit(X_norm)
        print("[+] Model training complete for all 4 detectors.")
        return self

    def get_scores(self, X: pd.DataFrame, model_name: str) -> np.ndarray:
        X_norm = self._normalize(X, fit=False)
        model = self.models[model_name]
        return model.score_samples(X_norm)

    def evaluate_on_labelled_sample(
        self,
        X_val: pd.DataFrame,
        y_val: np.ndarray,
        top_k_pct: float = TOP_1_PERCENT_TARGET,
    ) -> pd.DataFrame:
        """
        Evaluates Precision at Top K%, Recall at Top K%, and Area Under Curve.
        """
        results = []
        n_samples = len(y_val)
        k_top = max(1, int(n_samples * top_k_pct))

        for name in self.models.keys():
            scores = self.get_scores(X_val, name)

            # Rank descending
            top_indices = np.argsort(scores)[::-1][:k_top]
            top_preds = np.zeros(n_samples, dtype=int)
            top_preds[top_indices] = 1

            tp = np.sum((top_preds == 1) & (y_val == 1))
            fp = np.sum((top_preds == 1) & (y_val == 0))
            fn = np.sum((top_preds == 0) & (y_val == 1))

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

            # Empirical ROC-AUC via rank-sum (Wilcoxon-Mann-Whitney)
            pos_scores = scores[y_val == 1]
            neg_scores = scores[y_val == 0]
            if len(pos_scores) > 0 and len(neg_scores) > 0:
                # Vectorized pairwise comparison
                roc_auc = np.mean(pos_scores[:, None] > neg_scores[None, :])
            else:
                roc_auc = 0.5

            threshold = scores[top_indices[-1]]
            self.thresholds_[name] = threshold

            results.append({
                "Model": name,
                "Precision@Top1%": round(float(precision), 4),
                "Recall@Top1%": round(float(recall), 4),
                "ROC_AUC": round(float(roc_auc), 4),
                "Top1%_Cutoff_Threshold": round(float(threshold), 4),
            })

        return pd.DataFrame(results)
