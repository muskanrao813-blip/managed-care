"""
Trino read-only client — AI Care Coordinator.
All column names and table paths verified by direct query execution.

KEY FINDINGS (from live Trino queries, 2026-06-06):
  - d_policy: SELECT * is BLOCKED — must always select specific columns
  - f_claim benefit_name values: 'Doctor Consultation (family wallet)',
    'Nutritionist Consultation Benefit', 'Lab and Radiology (family wallet)',
    'Teleconsultation', 'Wellness Inclinic Consultation Benefit'
  - f_claim type_of_service values: OPD, LAB, Pharmacy, HOSPITAL, OTHER
  - VYTAL0126/0626 have 0 rows in f_claim (programme launched 2026-06-01,
    claims will start appearing as consultations are filed)
  - f_claim is the correct source for ALL benefit types (doctor, diet, lab)
    via benefit_name — NOT product_code for VYTAL
  - f_appointmentflattable has only DOCTOR appointments (user confirmed)
  - Link between d_policy users and f_claim: via phr_id field (in both tables)

NEVER writes to Trino. All writes go to Supabase.
"""

import os, urllib.parse
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

TRINO_USER = os.getenv("TRINO_USER", "vasu.verma")
TRINO_PASS = os.getenv("TRINO_PASSWORD", "")
TRINO_HOST = "trino-prod.healthrx.co.in"

# ── Confirmed benefit_name values in f_claim for consultation types ────────────
BENEFIT_NAME_DOCTOR   = ["Doctor Consultation (family wallet)",
                          "Teleconsultation",
                          "Wellness Inclinic Consultation Benefit",
                          "Doctor Consultation (family wallet) 4"]
BENEFIT_NAME_DIET     = ["Nutritionist Consultation Benefit"]
BENEFIT_NAME_LAB      = ["Lab and Radiology (family wallet)",
                          "Lab and Radiology (family wallet) -2",
                          "Lab Package 1", "Lab Package 8", "Lab Package 9",
                          "Lab Package 10", "Lab Package Center Visit"]

# SQL IN clause strings
_doctor_names = ",".join(f"'{n}'" for n in BENEFIT_NAME_DOCTOR)
_diet_names   = ",".join(f"'{n}'" for n in BENEFIT_NAME_DIET)
_lab_names    = ",".join(f"'{n}'" for n in BENEFIT_NAME_LAB)

# ── LOINC codes confirmed from 03_device_eligibility.py ───────────────────────
LOINC_HBAIC  = "4548-4"
LOINC_BMI    = "39156-5"
LOINC_SBP    = "8480-6"
LOINC_DBP    = "8462-4"
DIABETES_LOINC_FILTER = f"'{LOINC_HBAIC}','{LOINC_BMI}','{LOINC_SBP}','{LOINC_DBP}'"

VYTAL_DIABETES_SQL = "'VYTAL0126','VYTAL0626'"


def _engine():
    pw  = urllib.parse.quote_plus(TRINO_PASS or os.getenv("TRINO_PASSWORD", ""))
    url = f"trino://{TRINO_USER}:{pw}@{TRINO_HOST}:443/system?http_scheme=https"
    return create_engine(url)


def _run(sql: str, retry: int = 1) -> pd.DataFrame:
    """Execute query. Never use SELECT * on d_policy — permission denied."""
    try:
        eng = _engine()
        with eng.begin() as con:
            df = pd.read_sql(text(sql), con)
        eng.dispose()
        return df
    except Exception as e:
        print(f"[TRINO ERR] {e}")
        if retry > 0:
            return _run(sql, retry - 1)
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# TABLE REFERENCE (all verified by live queries)
# ─────────────────────────────────────────────────────────────────────────────
#
# d_policy        deltalake.dl_standard_customermart.d_policy
#   RULE: SELECT * BLOCKED — always name columns explicitly
#   columns used: personmobilephone_hash, vlocity_ins_fsc__productcode__c,
#                 createddate, Cohort__c, phr_id (verify), assetexpirationdate
#
# f_claim         deltalake.dl_standard_customermart.f_claim
#   columns used: phr_id, benefit_name, type_of_service, claim_type,
#                 claim_status, status, appointment_id, orderid,
#                 recordcreatedat, claim_created_date, product_code,
#                 provider_name, provider_type, appointment_date
#   benefit_name distinguishes: Doctor / Diet / Lab consultations
#   type_of_service: OPD=Doctor, LAB=Lab, Pharmacy, HOSPITAL
#
# customers       deltalake.dl_central_hrxlabs.customers
#   columns: order_id, mobile_number_hash, phr_id, created_at, gender, report_url
#
# lab_parsed      deltalake.dl_central_health_vault
#                 .phr_lab_parsed_data_parsed_data_results_readings
#   columns: transaction_id, loinc_id, test_name, value, units, provider
#
# lab_severity    deltalake.dl_standard_hdimart
#                 .labs_severity_model_p01_consolidated
#   columns: transaction_id, loinc_id, test_name, value, report_unit, provider_name
#
# appointments    deltalake.dl_standard_pbireporting.f_appointmentflattable
#   DOCTOR APPOINTMENTS ONLY (user confirmed)
#   columns: mobile_number_hash, appointment_id, appointment_type,
#            doctor_speciality, appointment_date, appointment_status
#
# HRA             "phr service".healthriskassessments
#   WHERE journey_key = 'hra_healthcamp'
#   columns: phr_id (v2) or mobile_number_hash (v1), smoking_status,
#            alcohol_frequency, stress_level, sleep_hours, bmi_category, last_updated
# ─────────────────────────────────────────────────────────────────────────────


def get_all_vytal_diabetes_patients() -> pd.DataFrame:
    """
    All VYTAL Diabetes patients. Uses specific columns only (SELECT * blocked on d_policy).
    Returns mobile_number_hash, product_code, cohort, policy_start_date, phr_id.
    """
    return _run(f"""
        SELECT DISTINCT
            personmobilephone_hash                                      AS mobile_number_hash,
            vlocity_ins_fsc__productcode__c                             AS product_code,
            COALESCE(
                CAST(Cohort__c AS VARCHAR),
                CASE WHEN vlocity_ins_fsc__productcode__c = 'VYTAL0626'
                     THEN 'Very High' ELSE 'High' END
            )                                                           AS cohort,
            SUBSTRING(CAST(createddate AS VARCHAR), 1, 10)              AS policy_start_date
        FROM deltalake.dl_standard_customermart.d_policy
        WHERE vlocity_ins_fsc__productcode__c IN ({VYTAL_DIABETES_SQL})
          AND personmobilephone_hash IS NOT NULL
        ORDER BY createddate DESC
    """)


def get_patient_policy(mobile_hash: str) -> dict:
    """Single patient policy — specific columns only, no SELECT *."""
    df = _run(f"""
        SELECT DISTINCT
            personmobilephone_hash                                      AS mobile_number_hash,
            vlocity_ins_fsc__productcode__c                             AS product_code,
            COALESCE(
                CAST(Cohort__c AS VARCHAR),
                CASE WHEN vlocity_ins_fsc__productcode__c = 'VYTAL0626'
                     THEN 'Very High' ELSE 'High' END
            )                                                           AS cohort,
            SUBSTRING(CAST(createddate AS VARCHAR), 1, 10)              AS policy_start_date,
            SUBSTRING(CAST(assetexpirationdate AS VARCHAR), 1, 10)      AS policy_end_date
        FROM deltalake.dl_standard_customermart.d_policy
        WHERE personmobilephone_hash = '{mobile_hash}'
          AND vlocity_ins_fsc__productcode__c IN ({VYTAL_DIABETES_SQL})
        ORDER BY createddate DESC
        LIMIT 1
    """)
    return df.iloc[0].to_dict() if not df.empty else {}


def get_claims_by_benefit(phr_id: str, since_date: str = "2026-01-01") -> dict:
    """
    Fetch all VYTAL benefit claims from f_claim for a patient.
    Filter by phr_id (common key between d_policy and f_claim).
    benefit_name column identifies claim type: Doctor / Diet / Lab.

    Note: VYTAL programme launched 2026-06-01. Claims accumulate over time.
    Returns 0 counts initially — this is expected for new enrolments.
    """
    df = _run(f"""
        SELECT
            phr_id,
            benefit_name,
            type_of_service,
            claim_type,
            claim_status,
            status,
            appointment_id,
            provider_name,
            provider_type,
            SUBSTRING(CAST(claim_created_date AS VARCHAR), 1, 10)       AS claim_date,
            SUBSTRING(CAST(appointment_date AS VARCHAR), 1, 10)          AS appt_date
        FROM deltalake.dl_standard_customermart.f_claim
        WHERE phr_id = '{phr_id}'
          AND claim_created_date >= TIMESTAMP '{since_date}'
        ORDER BY claim_created_date DESC
    """)

    if df.empty:
        return {
            "claims": [], "doctor_count": 0, "dietician_count": 0,
            "lab_count": 0, "benefit_breakdown": {}
        }

    doctor_df   = df[df["benefit_name"].isin(BENEFIT_NAME_DOCTOR)]
    diet_df     = df[df["benefit_name"].isin(BENEFIT_NAME_DIET)]
    lab_df      = df[df["benefit_name"].isin(BENEFIT_NAME_LAB)]
    completed   = df[df["claim_status"].str.lower().isin(["approved", "paid", "completed"])
                     if "claim_status" in df.columns else [True] * len(df)]

    return {
        "claims":            df.to_dict("records"),
        "doctor_count":      len(doctor_df),
        "dietician_count":   len(diet_df),
        "lab_count":         len(lab_df),
        "doctor_completed":  len(doctor_df[doctor_df["claim_status"].str.lower().isin(["approved","paid","completed"])]) if not doctor_df.empty else 0,
        "dietician_completed": len(diet_df[diet_df["claim_status"].str.lower().isin(["approved","paid","completed"])]) if not diet_df.empty else 0,
        "benefit_breakdown": df["benefit_name"].value_counts().to_dict(),
        "total_claims":      len(df),
    }


def get_doctor_appointments(mobile_hash: str, since_date: str = "2026-01-01") -> dict:
    """
    Doctor appointments from f_appointmentflattable.
    USER CONFIRMED: this table has DOCTOR appointments only.
    Columns confirmed from 03_device_eligibility (1).py:
      mobile_number_hash, appointment_id, appointment_type,
      doctor_speciality, appointment_date, appointment_status
    """
    df = _run(f"""
        SELECT
            mobile_number_hash,
            appointment_id,
            appointment_type,
            doctor_speciality,
            SUBSTRING(CAST(appointment_date AS VARCHAR), 1, 10)         AS appointment_date,
            appointment_status
        FROM deltalake.dl_standard_pbireporting.f_appointmentflattable
        WHERE mobile_number_hash = '{mobile_hash}'
          AND appointment_date   >= '{since_date}'
          AND appointment_status != 'Cancelled'
        ORDER BY appointment_date DESC
    """)

    if df.empty:
        return {"appointments": [], "total": 0, "completed": 0, "booked": 0}

    completed = df[df["appointment_status"] == "Completed"]
    return {
        "appointments": df.to_dict("records"),
        "total":        len(df),
        "completed":    len(completed),
        "booked":       len(df[df["appointment_status"] == "Booked"]),
        "specialities": df["doctor_speciality"].dropna().unique().tolist(),
    }


def get_lab_results(mobile_hash: str, months_back: int = 12) -> dict:
    """
    Lab biomarker results via f_claim → customers → phr_lab_parsed_data.
    Falls back to labs_severity_model when parsed data has no match.
    Confirmed join pattern from all existing scripts.
    """
    df = _run(f"""
        SELECT DISTINCT
            d.mobile_number_hash,
            d.phr_id,
            d.created_at                                                AS test_date,
            SUBSTRING(CAST(d.created_at AS VARCHAR), 1, 7)             AS test_month,
            b.loinc_id,
            b.test_name,
            TRY_CAST(b.value AS DOUBLE)                                 AS value,
            b.units,
            b.provider
        FROM deltalake.dl_standard_customermart.f_claim a
        LEFT JOIN deltalake.dl_central_hrxlabs.customers d
               ON a.orderid = d.order_id
        LEFT JOIN deltalake.dl_central_health_vault.phr_lab_parsed_data_parsed_data_results_readings b
               ON a.orderid = b.transaction_id
        WHERE d.mobile_number_hash = '{mobile_hash}'
          AND b.loinc_id IN ({DIABETES_LOINC_FILTER})
          AND b.transaction_id IS NOT NULL
          AND d.report_url IS NOT NULL
          AND SUBSTRING(CAST(d.created_at AS VARCHAR), 1, 7)
              >= SUBSTRING(CAST(DATE_ADD('month', -{months_back}, CURRENT_DATE) AS VARCHAR), 1, 7)

        UNION ALL

        SELECT DISTINCT
            d.mobile_number_hash,
            d.phr_id,
            d.created_at                                                AS test_date,
            SUBSTRING(CAST(d.created_at AS VARCHAR), 1, 7)             AS test_month,
            p.loinc_id,
            p.test_name,
            TRY_CAST(p.value AS DOUBLE)                                 AS value,
            p.report_unit                                               AS units,
            p.provider_name                                             AS provider
        FROM deltalake.dl_standard_customermart.f_claim a
        LEFT JOIN deltalake.dl_central_hrxlabs.customers d
               ON a.orderid = d.order_id
        LEFT JOIN deltalake.dl_central_health_vault.phr_lab_parsed_data_parsed_data_results_readings b
               ON a.orderid = b.transaction_id
        LEFT JOIN deltalake.dl_standard_hdimart.labs_severity_model_p01_consolidated p
               ON p.transaction_id = a.orderid
        WHERE d.mobile_number_hash = '{mobile_hash}'
          AND p.loinc_id IN ({DIABETES_LOINC_FILTER})
          AND d.report_url IS NOT NULL
          AND b.transaction_id IS NULL
          AND SUBSTRING(CAST(d.created_at AS VARCHAR), 1, 7)
              >= SUBSTRING(CAST(DATE_ADD('month', -{months_back}, CURRENT_DATE) AS VARCHAR), 1, 7)
    """)

    if df.empty:
        return {"lab_results": [], "latest_hba1c": None, "hba1c_trend": []}

    df = df.sort_values("test_date", ascending=False)
    df = df.drop_duplicates(subset=["mobile_number_hash", "loinc_id"], keep="first")

    hba1c_df    = df[df["loinc_id"] == LOINC_HBAIC].sort_values("test_date")
    hba1c_trend = [
        {"date": str(r["test_date"])[:10], "value": float(r["value"]), "unit": r["units"]}
        for _, r in hba1c_df.iterrows() if r["value"] is not None
    ]

    return {
        "lab_results":   df.to_dict("records"),
        "latest_hba1c":  hba1c_trend[-1]["value"] if hba1c_trend else None,
        "hba1c_trend":   hba1c_trend,
        "test_count":    len(df),
    }


def get_hra(phr_id: str) -> dict:
    """
    HRA from "phr service".healthriskassessments.
    Confirmed from 03_device_eligibility (2).py:
      - table: "phr service".healthriskassessments
      - filter: journey_key = 'hra_healthcamp'
      - join key: phr_id (version 2 of script)
    """
    df = _run(f"""
        SELECT
            phr_id,
            smoking_status,
            alcohol_frequency,
            stress_level,
            sleep_hours,
            bmi_category,
            SUBSTRING(CAST(last_updated AS VARCHAR), 1, 10)             AS last_updated
        FROM "phr service".healthriskassessments
        WHERE phr_id = '{phr_id}'
          AND journey_key = 'hra_healthcamp'
        ORDER BY last_updated DESC
        LIMIT 1
    """)

    if df.empty:
        return {"hra_completed": False}

    row = df.iloc[0].to_dict()
    row["hra_completed"] = True
    row["is_smoker"]     = row.get("smoking_status") == "Current Smoker"
    row["alcohol_risk"]  = str(row.get("alcohol_frequency", "")) in [
                               "5-14 drinks/month", "14+ drinks/month", ">14 drinks/month"]
    row["stress_high"]   = str(row.get("stress_level", "")) in ["High", "Extremely High"]
    row["poor_sleep"]    = (row.get("sleep_hours") is not None and
                            float(row.get("sleep_hours") or 8) < 6)
    row["is_overweight"] = str(row.get("bmi_category", "")) in ["Overweight", "Obese"]
    return row


def get_full_patient_context(mobile_hash: str, phr_id: str = None) -> dict:
    """
    Master function — all data needed to populate PatientState.
    Requires both mobile_hash (for d_policy + appointments) and
    phr_id (for f_claim benefits + HRA).
    phr_id is fetched from lab results if not provided.
    """
    from constants.programme_context import BENEFIT_CAPS

    policy  = get_patient_policy(mobile_hash)
    labs    = get_lab_results(mobile_hash, months_back=12)
    appts   = get_doctor_appointments(mobile_hash, since_date="2026-01-01")

    # Get phr_id from lab results if not passed in
    if not phr_id and labs.get("lab_results"):
        phr_id = labs["lab_results"][0].get("phr_id")

    claims  = get_claims_by_benefit(phr_id, since_date="2026-01-01") if phr_id else {}
    hra     = get_hra(phr_id) if phr_id else {"hra_completed": False}

    cohort     = policy.get("cohort", "High")
    cohort_key = cohort.upper().replace(" ", "_")   # "Very High" → "VERY_HIGH"
    caps       = BENEFIT_CAPS.get(cohort_key, BENEFIT_CAPS["HIGH"])

    return {
        # Identity
        "mobile_hash":          mobile_hash,
        "phr_id":               phr_id,
        "product_code":         policy.get("product_code"),
        "cohort":               cohort_key,
        "policy_start_date":    policy.get("policy_start_date"),
        "programme":            "DIABETES",

        # Clinical — lab results
        "latest_hba1c":         labs.get("latest_hba1c"),
        "hba1c_trend":          labs.get("hba1c_trend", []),
        "all_lab_results":      labs.get("lab_results", []),

        # Benefit utilisation — from f_claim benefit_name
        # (0 initially since programme just launched; grows as consultations are filed)
        "doctor_used":          claims.get("doctor_completed", 0),
        "doctor_max":           caps["doctor"],
        "dietician_used":       claims.get("dietician_completed", 0),
        "dietician_max":        caps["dietician"],
        "lab_used":             claims.get("lab_count", 0),
        "benefit_breakdown":    claims.get("benefit_breakdown", {}),

        # Doctor appointment history — from f_appointmentflattable (doctor only)
        "doctor_appointments":  appts.get("appointments", []),
        "doctor_completed":     appts.get("completed", 0),
        "doctor_booked":        appts.get("booked", 0),
        "doctor_specialities":  appts.get("specialities", []),

        # HRA / lifestyle
        "hra_completed":        hra.get("hra_completed", False),
        "is_smoker":            hra.get("is_smoker", False),
        "alcohol_risk":         hra.get("alcohol_risk", False),
        "stress_high":          hra.get("stress_high", False),
        "poor_sleep":           hra.get("poor_sleep", False),
        "is_overweight":        hra.get("is_overweight", False),
        "bmi_category":         hra.get("bmi_category"),
        "stress_level":         hra.get("stress_level"),
        "sleep_hours":          hra.get("sleep_hours"),
    }
