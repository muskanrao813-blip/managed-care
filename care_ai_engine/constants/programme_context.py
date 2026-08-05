"""
Programme-level constants injected into every agent system prompt.
Single source of truth — change here, reflects everywhere.
"""

PROGRAMME_CONTEXT = {
    "DIABETES": {
        "product_codes":    ["VYTAL0126", "VYTAL0626"],
        "specialist":       "Diabetologist / GP",
        "primary_biomarker":"HbA1c",
        "biomarkers": {
            "HbA1c":   {"unit": "%",     "normal": "<5.7", "moderate": "5.7-6.4", "high": "6.5-8", "very_high": ">8"},
            "Glucose":  {"unit": "mg/dL", "normal": "<100", "high": "100-125",    "very_high": ">=126"},
        },
        "escalation_thresholds": {"HbA1c_delta": 1.0},
        "devices": {
            "MODERATE":  "Glucometer",
            "HIGH":      "Glucometer",
            "VERY_HIGH": "CGM",
        },
        "dietary_focus":    "Low glycemic index, 5 small meals, reduce refined carbs, increase fibre",
        "high_risk_foods":  ["white rice", "refined sugar", "fruit juice", "maida", "sweets", "cold drinks"],
        "lifestyle_priority": ["physical activity", "weight management", "smoking cessation"],
        "user_language":    "sugar levels",
        "hba1c_target":     7.0,
        "ai_model_unlock":  ["HIGH", "VERY_HIGH"],
    }
}

BENEFIT_CAPS = {
    "MODERATE": {
        "doctor":           6,
        "dietician":        6,
        "lab_discount":     0.10,
        "pharma_discount":  0.10,
        "gym":              "Online Fitness only",
        "mental_wellness":  False,
        "quit_smoking":     False,
    },
    "HIGH": {
        "doctor":           8,
        "dietician":        8,
        "lab_discount":     0.15,
        "pharma_discount":  0.15,
        "gym":              "12 sessions + Online Fitness",
        "mental_wellness":  True,
        "quit_smoking":     True,
    },
    "VERY_HIGH": {
        "doctor":           99,   # unlimited — operationally 1/month
        "dietician":        99,
        "lab_discount":     0.20,
        "pharma_discount":  0.20,
        "gym":              "24 sessions + Online Fitness",
        "mental_wellness":  True,
        "quit_smoking":     True,
    },
}

DEVICE_CAPS       = {"CGM": 100, "Glucometer": 100, "BP_Monitor": 100, "Weighing_Scale": 100}
LIFESTYLE_CAPS    = {"Metabolic_Assessment": 200, "Stress_Assessment": 100, "Alcohol_Assessment": 100}
FOMO_THRESHOLD    = 0.30   # trigger FOMO nudge when slots < 30% remaining

# Clinical schedule cadence (days since enrolment)
CLINICAL_CADENCE = {
    "VERY_HIGH": {"first_doctor": 30, "first_diet": 1,  "first_lab": 90},
    "HIGH":      {"first_doctor": 30, "first_diet": 1,  "first_lab": 90},
    "MODERATE":  {"first_doctor": 45, "first_diet": -1, "first_lab": 180},
    # -1 for first_diet means: schedule AFTER first doctor consultation
}

# HbA1c band classification (matches PROGRAMME_CONTEXT biomarkers)
def classify_hba1c(value: float) -> str:
    if value < 5.7:   return "Normal"
    if value < 6.5:   return "Moderate"
    if value <= 8.0:  return "High"
    return "Very High"

# Derive cohort from product code
PRODUCT_TO_COHORT = {
    "VYTAL0126": "HIGH",
    "VYTAL0626": "VERY_HIGH",
}
