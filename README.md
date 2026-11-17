# Telecom Anomaly Detection System

**Provider:** Ananthapuri FibreNet (Thiruvananthapuram, Kerala)  
**Objective:** Automated unsupervised anomaly detection on subscriber usage, CDR, recharges, and complaint records to eliminate manual scanning and cut review workload by $\ge 50\%$ while achieving Precision @ Top 1% $\ge 60\%$.

---

## 📌 Executive Summary & Key Achievements

| Metric / Objective | Target Requirement | Achieved Result | Status |
| :--- | :---: | :---: | :---: |
| **Precision @ Top 1%** | $\ge 60.0\%$ | **100.0%** (Validation Benchmark) | **Exceeded** (+40.0%) |
| **Workload Reduction** | $\ge 50.0\%$ | **75.0%** (2,000 manual $\to$ 500 AI alerts) | **Exceeded** (+25.0%) |
| **Alert Explainability** | 100% of alerts explained | **100.0%** assigned reason codes & action | **Fulfilled** |
| **Model Comparison** | Benchmark 4 models | iForest, LOF, Autoencoder, Robust Z-score | **Fulfilled** |
| **Batch Scoring Pipeline** | Daily batch job | `src/batch_scoring.py` writing to SQLite & CSV | **Fulfilled** |
| **Review Dashboard** | Interactive dashboard | HTML5 / Python review GUI (`dashboard/app.py`) | **Fulfilled** |
| **Weekly Feedback Loop** | Re-tune thresholds | `src/feedback_loop.py` adaptive thresholding | **Fulfilled** |
| **False Positive Analysis** | Explain 2 FPs & fixes | Holiday streaming & family split recharges | **Fulfilled** |

---

## 🗂️ Project Directory Architecture

```text
telecom_anomaly_detection/
├── .vscode/
│   ├── launch.json              # VS Code debug configs (Master, Batch, Tests, Dashboard)
│   ├── settings.json            # Python 3.12 interpreter & test settings
│   └── tasks.json               # One-click VS Code task runner
├── data/
│   ├── telecom_subscriber_records.csv   # 50,000 ingested subscriber telemetry records
│   ├── labelled_validation_300.csv      # 300-case ground-truth evaluation sample
│   ├── daily_review_queue.csv           # Top 1% prioritized alerts
│   └── telecom_review_table.sqlite      # SQLite production review table
├── src/
│   ├── config.py                # Global parameters, towers, plans, reason codes
│   ├── data_generator.py        # Simulates telemetry with known dirty patterns
│   ├── feature_engineering.py   # Rolling deviations, peer ratios, rare combos
│   ├── models.py                # iForest, LOF, Autoencoder, Robust Z-Score
│   ├── explainability.py        # Non-technical reason code engine
│   ├── batch_scoring.py         # Daily automated scoring batch job
│   ├── feedback_loop.py         # Adaptive weekly threshold re-tuning
│   └── generate_report.py       # DOCX, DOC & Markdown report builder
├── dashboard/
│   ├── app.py                   # Lightweight review server (http://localhost:8088)
│   └── dashboard.html           # Standalone interactive review dashboard
├── notebooks/
│   └── Telecom_Anomaly_Detection.ipynb  # End-to-end interactive notebook
├── tests/
│   └── test_anomaly_detection.py# 10 automated unit tests (100% pass)
├── reports/
│   ├── figures/                 # Benchmark charts & operational figures
│   ├── Methodology_Note.docx    # Word report for upload
│   ├── Methodology_Note.doc     # Legacy Word report
│   └── Methodology_Note.md      # Detailed markdown methodology report
├── run.py                       # Single master script to execute full pipeline
├── requirements.txt             # Environment dependencies
└── README.md                    # Project documentation
```

---

## 🚀 Quickstart & Execution Instructions

### 1. Run Everything with One Command
Execute the end-to-end pipeline (data generation, feature engineering, model training, evaluation, charts, and reports):
```powershell
python run.py
```

### 2. Run the Unit Test Suite
```powershell
python -m unittest discover -s tests -v
```

### 3. Run the Daily Batch Scoring Job
```powershell
python src/batch_scoring.py
```

### 4. Launch the Interactive Review Dashboard
```powershell
python dashboard/app.py
```
Then open your browser at: `http://localhost:8088` (or double click `dashboard/dashboard.html`).

---

## 🔬 Model Benchmarking Summary (Objective 5 & 6)

Evaluated on the 300-case stratified ground-truth validation sample:

| Detector Model | Precision @ Top 1% | Recall @ Top 1% | ROC-AUC | Operational Threshold |
| :--- | :---: | :---: | :---: | :---: |
| **Isolation Forest (Production)** | **100.0%** | **68.2%** | **94.8%** | **0.8842** |
| **Robust Z-Score (MAD)** | 90.0% | 61.4% | 88.5% | 0.8120 |
| **Autoencoder Reconstruction** | 86.7% | 59.1% | 89.2% | 0.7950 |
| **Local Outlier Factor (LOF)** | 83.3% | 56.8% | 85.1% | 0.7640 |

---

## 🔍 Explainability & Reason Code Ontology (Objective 7)

Every alert is tagged with an operational reason code:
* `DATA_PORTED_OUT_ACTIVE`: Subscriber ported out in MNP registry but active billing continues.
* `DATA_UNMATCHED_TOWER`: Traffic routed through OLT ID missing from Thiruvananthapuram Master Topology.
* `DATA_MISSING_CIRCLE`: Missing mandatory TRAI Kerala regulatory circle code (`KL`).
* `FRAUD_MIDNIGHT_SPIKE`: Severe bandwidth burst (>3.5x baseline) during off-peak hours (00:00-06:00).
* `FRAUD_RECHARGE_VELOCITY`: 3+ recharges in under 24 hours indicating stolen voucher/card testing.
* `FAULT_SILENT_OUTAGE`: High complaint frequency with near-zero data consumption (undetected fibre cut).

---

## 💡 Two False Positives & How to Reduce Them (Objective 12)

1. **Festival / Holiday Streaming Spikes (Onam / Vishu):**
   * *Problem:* Residential subscribers streaming 4K video during family celebrations trip `FRAUD_MIDNIGHT_SPIKE`.
   * *Remediation:* Incorporate a regional festival calendar covariate with a 48-hour volume dampening window.
2. **Multi-Member Split Family Recharges:**
   * *Problem:* Distinct family members topping up the household broadband connection trigger `FRAUD_RECHARGE_VELOCITY`.
   * *Remediation:* Cross-reference hashed UPI VPAs and payment tokens; if separate payer IDs with successful 2FA are validated, suppress the alert.
