"""
Telecom Anomaly Detection System - Global Configuration
Provider: Ananthapuri FibreNet (Thiruvananthapuram, Kerala)
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
FIGURES_DIR = os.path.join(REPORTS_DIR, "figures")
DB_PATH = os.path.join(DATA_DIR, "telecom_review_table.sqlite")

# Known Thiruvananthapuram OLT / Tower Master IDs
VALID_TOWERS = [
    "TRV-KAZH-01",  # Kazhakkoottam / Technopark Phase 1
    "TRV-THAM-02",  # Thampanoor Central
    "TRV-PATT-03",  # Pattom
    "TRV-KOWD-04",  # Kowdiar
    "TRV-TECH-05",  # Technopark Phase 3
    "TRV-VELL-06",  # Vellayambalam
    "TRV-PALY-07",  # Palayam
    "TRV-STAT-08",  # Statue / Secretariat
    "TRV-PERO-09",  # Peroorkada
    "TRV-VIZH-10",  # Vizhinjam Harbour
]

VALID_CIRCLE_CODES = ["KL", "KL-TRV"]

BROADBAND_PLANS = {
    "Fibre_Basic_50M": {"speed_mbps": 50, "monthly_quota_gb": 1000, "price_inr": 499},
    "Fibre_Value_100M": {"speed_mbps": 100, "monthly_quota_gb": 2000, "price_inr": 799},
    "Fibre_Super_300M": {"speed_mbps": 300, "monthly_quota_gb": 3500, "price_inr": 1199},
    "Fibre_Biz_1G": {"speed_mbps": 1000, "monthly_quota_gb": 8000, "price_inr": 2999},
}

# Reason Code Definitions for Non-Technical Reviewers
REASON_CODES = {
    "DATA_PORTED_OUT_ACTIVE": {
        "title": "Ported-Out Active Subscriber",
        "description": "Subscriber is recorded as Ported-Out in MNP registry but active data sessions / billing continue.",
        "category": "Data Corruption / Fraud",
        "priority": "HIGH",
    },
    "DATA_UNMATCHED_TOWER": {
        "title": "Unmatched OLT / Tower Identifier",
        "description": "Traffic routed through OLT ID missing from the Thiruvananthapuram Master Topology List.",
        "category": "Network Topology Error",
        "priority": "HIGH",
    },
    "DATA_MISSING_CIRCLE": {
        "title": "Missing Regulatory Circle Code",
        "description": "Recharge or subscriber transaction missing mandatory Kerala circle code ('KL').",
        "category": "Data Quality / Compliance",
        "priority": "MEDIUM",
    },
    "FRAUD_MIDNIGHT_SPIKE": {
        "title": "Midnight Heavy Bandwidth Burst",
        "description": "Disproportionate off-peak traffic burst (>3.5x rolling baseline) indicating unauthorized proxy/commercial redistribution.",
        "category": "Revenue Assurance",
        "priority": "HIGH",
    },
    "FRAUD_RECHARGE_VELOCITY": {
        "title": "High-Frequency Recharge Velocity",
        "description": "Multiple successive recharges within a 24-hour window, typical of stolen voucher/card testing.",
        "category": "Payment Fraud",
        "priority": "HIGH",
    },
    "FAULT_SILENT_OUTAGE": {
        "title": "Silent Fibre Fault / Unresolved Outage",
        "description": "Subscribers with repeated complaint tickets but near-zero downstream data consumption.",
        "category": "Customer Care / Outage",
        "priority": "MEDIUM",
    },
    "ANOMALY_PEER_OUTLIER": {
        "title": "Cohort Behavioral Outlier",
        "description": "Multidimensional outlier exceeding 99th percentile of plan-cohort feature distribution.",
        "category": "Behavioral Anomaly",
        "priority": "LOW",
    },
}

# Target Contamination & Operational Thresholds
CONTAMINATION_TARGET = 0.015  # 1.5% expected anomaly rate
TOP_1_PERCENT_TARGET = 0.010   # Top 1% priority queue
PRECISION_TARGET = 0.60        # >= 60% Precision at Top 1%
