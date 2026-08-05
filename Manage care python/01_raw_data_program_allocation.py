# Imports
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
import sqlparse
import urllib
from db_layer import save_dataframe


#  CAMP YEAR CONFIG 
# "2025"  fiscal year Apr 2025Mar 2026  |  product codes: BFLPL*
# "2026"  fiscal year Apr 2026present   |  product codes: BPC*
SELECTED_CAMP_YEAR = "2026"

CAMP_CONFIG = {
    "2024": {
        "codes_sql": "'BFLPL01','BFLPL02','BFLPL03','BFLPLH01','BFLPLH02','BFLPLH03','BFLPL04'",
        "date_from": "2024-02",
        "date_to":   "2024-07",
    },
    "2025": {
        "codes_sql": "'BPC01','BPC02','BPC03','BFLPURE01','BFLPURE02'",
        "date_from": "2025-04",
        "date_to":   "2026-03",
    },
    "2026": {
        "codes_sql": "'BPC01','BPC02','BPC03'",
        "date_from": "2026-04",
        "date_to":   None,
    },
}

_cfg        = CAMP_CONFIG[SELECTED_CAMP_YEAR]
_codes_sql  = _cfg["codes_sql"]
_date_from  = _cfg["date_from"]
_date_to    = _cfg["date_to"]
# Build date filter SQL  upper bound only added when present (2025 fiscal year)
_date_lower = f"substring(cast(d.\"created_at\" as VARCHAR),1,7) >= '{_date_from}'"
_date_upper = (f"and substring(cast(d.\"created_at\" as VARCHAR),1,7) <= '{_date_to}'"
               if _date_to else "")


# Trino Credentials & Environment
from config import TRINO_HOST, TRINO_USER, TRINO_PASSWORD
trinoUser = TRINO_USER
trinoPass = TRINO_PASSWORD
env = 'Prod'


# Trino Query Function

def trino_query(query: str, retry: int = 0):
    """Connect to Trino deployment using SQLAlchemy and run query

    Args:
        query: SQL query to execute
        retry: Number of retry attempts on failure
    Returns:
        df (DataFrame): Dataframe of the queried result
        message (str): Status message
    """
    try:
        if trinoPass is None:
            print("ERR", "Trino pass is being called as None!!")

        if trinoUser is None:
            print("ERR", "Trino user is being called as None!!")

        trinoPassUpdated = urllib.parse.quote_plus(str(trinoPass))

        connection_url = (
            f"trino://{trinoUser}:{trinoPassUpdated}@trino-prod.healthrx.co.in:443/systemxhttp_scheme=https"
            if env == 'Prod'
            else f"trino://{trinoUser}:{trinoPassUpdated}@trino-dev.healthrx.co.in:443/systemxhttp_scheme=https"
        )

        engine = create_engine(connection_url, connect_args={"verify": False})

        with engine.begin() as con:
            df = pd.read_sql(text(query), con)

        engine.dispose()

        return df, "Ran successfully. This shouldn't be printed."

    except Exception as e:
        print("ERR", f"Failed while executing Trino query: {e}")
        print("ERR", query)

        if retry > 0:
            print("INF", "Attempting to rerun query --")
            return trino_query(query, retry=retry - 1)

        else:
            return None, str(e)


# Camp Data Query  fiscal year driven by SELECTED_CAMP_YEAR

print(f"\n[Camp Year: {SELECTED_CAMP_YEAR}] Codes: {_codes_sql} | Period: {_date_from} to {_date_to or 'present'}")

df, err = trino_query(query=f"""

select distinct
d.mobile_number_hash,
d.order_id,
a.product_code,
d.phr_id,
d.created_at,
substring(cast(d."created_at" as VARCHAR),1,7) as MT,
b.loinc_id,
b.test_name,
b.value,
b.units,
b.provider,
d.gender,
1 as rnk

FROM deltalake.dl_standard_customermart.f_claim a

left join deltalake.dl_central_hrxlabs.customers d
on a.orderid = d.order_id

left join deltalake.dl_central_health_vault.phr_lab_parsed_data_parsed_data_results_readings b
on a.orderid = b.transaction_id

where 1=1
and a.product_code in ({_codes_sql})
and b.transaction_id is not null
and d.report_url is not null
and d.mobile_number_hash is not null
and b.loinc_id is not null
and {_date_lower}
{_date_upper}

union all

select * from
(
select distinct
d.mobile_number_hash,
d.order_id,
a.product_code,
d.phr_id,
d.created_at,
substring(cast(d."created_at" as VARCHAR),1,7) as MT,
p.loinc_id,
p.test_name,
p.value,
p.report_unit as units,
p.provider_name as provider,
d.gender,

row_number() over(
partition by d.order_id,p.loinc_id
order by d.created_at desc
) as rnk

FROM deltalake.dl_standard_customermart.f_claim a

left join deltalake.dl_central_hrxlabs.customers d
on a.orderid = d.order_id

left join deltalake.dl_central_health_vault.phr_lab_parsed_data_parsed_data_results_readings b
on a.orderid = b.transaction_id

left join deltalake.dl_standard_hdimart.labs_severity_model_p01_consolidated p
on p.transaction_id = a.orderid

where 1=1
and a.product_code in ({_codes_sql})
and d.report_url is not null
and d.mobile_number_hash is not null
AND b.transaction_id IS null
and p.loinc_id is not null
and {_date_lower}
{_date_upper}

)x1

where rnk = 1

""")


# 
# Section 2 : Loading Lookups
# 

lkp_r = pd.read_excel(
    "d:\\OneDrive - Bajaj Finserv Health Limited\\Documents\\manage care\\manage care python\\Final_BFL_Lookup_THR 5.xlsx",
    sheet_name='Redcliffe'
)

lkp_t = pd.read_excel(
    "d:\\OneDrive - Bajaj Finserv Health Limited\\Documents\\manage care\\manage care python\\Final_BFL_Lookup_THR 5.xlsx",
    sheet_name='Thyrocare'
)

lkp_h = pd.read_excel(
   "d:\\OneDrive - Bajaj Finserv Health Limited\\Documents\\manage care\\manage care python\\Final_BFL_Lookup_THR 5.xlsx",
    sheet_name='Healthians'
)

lkp_a = pd.read_excel(
   "d:\\OneDrive - Bajaj Finserv Health Limited\\Documents\\manage care\\manage care python\\Final_BFL_Lookup_THR 5.xlsx",
    sheet_name='Apollo'
)

lkp_j = pd.read_excel(
    "d:\\OneDrive - Bajaj Finserv Health Limited\\Documents\\manage care\\manage care python\\Final_BFL_Lookup_THR 5.xlsx",
    sheet_name='Jehangir'
)


# Standardizing Column Names

standard_columns = [
    'impact',
    'test_name',
    'cos',
    'loinc_id',
    'inclusion_considered_for_plan_stamping',
    'value',
    'gender',
    'lower_bound',
    'upper_bound',
    'operator',
    'lower_bound.1',
    'upper_bound.1',
    'outcome',
    'outcome_value',
    'units'
]

lkp_r.columns = standard_columns
lkp_t.columns = standard_columns
lkp_h.columns = standard_columns
lkp_a.columns = standard_columns
lkp_j.columns = standard_columns


# Selecting Required Columns

required_columns = [
    'impact',
    'test_name',
    'cos',
    'loinc_id',
    'value',
    'gender',
    'operator',
    'lower_bound.1',
    'upper_bound.1',
    'outcome',
    'outcome_value',
    'units'
]

lkp_r = lkp_r[required_columns]
lkp_t = lkp_t[required_columns]
lkp_h = lkp_h[required_columns]
lkp_a = lkp_h[required_columns]
lkp_j = lkp_h[required_columns]


# Renaming Lookup Columns

rename_columns = {
    'impact': 'impact',
    'test_name': 'lkp_test_name',
    'cos': 'cos',
    'loinc_id': 'loinc_id',
    'value': 'lkp_value',
    'gender': 'lkp_gender',
    'operator': 'operator',
    'lower_bound.1': 'lower_bound',
    'upper_bound.1': 'upper_bound',
    'outcome': 'outcome',
    'outcome_value': 'outcome_value',
    'units': 'lkp_units'
}

lkp_r.rename(columns=rename_columns, inplace=True)
lkp_t.rename(columns=rename_columns, inplace=True)
lkp_h.rename(columns=rename_columns, inplace=True)
lkp_a.rename(columns=rename_columns, inplace=True)
lkp_j.rename(columns=rename_columns, inplace=True)


# 
# Section 3 : Running Lookups to Map Outcome
# 

df_r = df[
    ~df['provider'].isin([
        "{'name': 'Healthians'}",
        "{'name': 'Thyrocare'}",
        "{'name': 'Thyrocare Technologies Limited'}",
        "Apollo Health and Lifestyle Limited",
        "Jehangir Hospital"
    ])
]

df_t = df[
    df['provider'].isin([
        "{'name': 'Thyrocare'}",
        "{'name': 'Thyrocare Technologies Limited'}"
    ])
]

df_h = df[df['provider'] == "{'name': 'Healthians'}"]

df_a = df[df['provider'] == "Apollo Health and Lifestyle Limited"]

df_j = df[df['provider'] == "Jehangir Hospital"]


# Merging Provider Data with Lookups

df_merged_r = df_r.merge(
    lkp_r,
    left_on=['loinc_id', 'gender'],
    right_on=['loinc_id', 'lkp_gender'],
    how='inner'
)

df_merged_t = df_t.merge(
    lkp_t,
    left_on=['loinc_id', 'gender'],
    right_on=['loinc_id', 'lkp_gender'],
    how='inner'
)

df_merged_h = df_h.merge(
    lkp_h,
    left_on=['loinc_id', 'gender'],
    right_on=['loinc_id', 'lkp_gender'],
    how='inner'
)

df_merged_a = df_a.merge(
    lkp_a,
    left_on=['loinc_id', 'gender'],
    right_on=['loinc_id', 'lkp_gender'],
    how='inner'
)

df_merged_j = df_j.merge(
    lkp_j,
    left_on=['loinc_id', 'gender'],
    right_on=['loinc_id', 'lkp_gender'],
    how='inner'
)


# Combining All Provider Data

df_merged = pd.concat(
    [
        df_merged_r,
        df_merged_t,
        df_merged_h,
        df_merged_a,
        df_merged_j
    ],
    ignore_index=True
)


# Converting Numeric Columns

df_merged['value'] = pd.to_numeric(
    df_merged['value'],
    errors='coerce'
)

df_merged['lower_bound'] = pd.to_numeric(
    df_merged['lower_bound'],
    errors='coerce'
)

df_merged['upper_bound'] = pd.to_numeric(
    df_merged['upper_bound'],
    errors='coerce'
)


# Filtering Valid Outcome Ranges

df_filtered = df_merged[
    df_merged['value'].notna() &
    df_merged['lower_bound'].notna() &
    df_merged['upper_bound'].notna() &
    (df_merged['value'] >= df_merged['lower_bound']) &
    (df_merged['value'] <= df_merged['upper_bound'])
]


# Keeping Latest Test Result per User

df_filtered_latest = (
    df_filtered
    .sort_values(by='created_at', ascending=False)
    .drop_duplicates(
        subset=['mobile_number_hash', 'loinc_id'],
        keep='first'
    )
    .sort_values(
        by=['mobile_number_hash', 'test_name']
    )
)


# 
# Section 4 : Outcome Score Calculation
# 

def calculate_updated_outcome_value(row):

    if row['outcome'] in ['Low', 'Borderline Low']:

        return (
            row['outcome_value'] +
            (
                (row['upper_bound'] - row['value']) /
                row['upper_bound']
            )
        )

    elif row['outcome'] in ['High', 'Borderline High']:

        return (
            row['outcome_value'] +
            (
                (row['value'] - row['lower_bound']) /
                row['lower_bound']
            )
        )

    else:

        return row['outcome_value']


df_filtered_latest['updated_outcome_value'] = (
    df_filtered_latest.apply(
        calculate_updated_outcome_value,
        axis=1
    )
)


# Calculating Outcome COS

df_filtered_latest.loc[:, 'Outcome_COS'] = (
    df_filtered_latest['updated_outcome_value'] *
    df_filtered_latest['cos']
)


# Filtering Positive Outcome COS

df_filtered2 = df_filtered_latest[
    df_filtered_latest['Outcome_COS'] > 0
].copy()


# 
# Section 5 : Grouped Scores on Impact Level
# 

import numpy as np

grouped = df_filtered2.groupby(['mobile_number_hash', 'impact']).agg(
    total_score=('Outcome_COS', 'sum'),
    num_tests=('Outcome_COS', 'count'),
    first_camp_date=('created_at', 'min'),
).reset_index()
# Normalise to YYYY-MM string for dashboard date filtering
grouped['first_camp_date'] = pd.to_datetime(grouped['first_camp_date'], errors='coerce').dt.strftime('%Y-%m')

grouped['normalized_score'] = grouped['total_score'] / np.log1p(grouped['num_tests'])

grouped['scaled_score'] = grouped.groupby('impact')['normalized_score'].transform(
    lambda x: 100 - (x / x.max()) * 100
)

top_impact_per_user = (
    grouped.sort_values(['mobile_number_hash', 'normalized_score'], ascending=[True, False])
           .drop_duplicates('mobile_number_hash', keep='first')
)


# 
# OUTPUT
# output_dir points to ./data/ next to this script
# so the dashboard can read the CSVs automatically.
# 

import os

output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(output_dir, exist_ok=True)

#  Output 1: RAW DATA 
# df_filtered_latest = one row per user  loinc_id (test)
# Columns: mobile_number_hash, order_id, product_code, phr_id, created_at, MT,
#          loinc_id, test_name, value, units, provider, gender, rnk,
#          impact, lkp_test_name, cos, operator, lower_bound, upper_bound,
#          outcome, outcome_value, lkp_units,
#          updated_outcome_value, Outcome_COS
df_filtered_latest.to_csv(
    os.path.join(output_dir, "managed_care_raw_data.csv"),
    index=False
)
print(f" Saved managed_care_raw_data.csv  {len(df_filtered_latest):,} rows "
      f"({df_filtered_latest['mobile_number_hash'].nunique():,} users  tests)")

#  Output 2: GROUPED IMPACT SCORES 
# Save year-specific file + merge all years into master
impact_year_file = os.path.join(output_dir, f"managed_care_impact_scores_{SELECTED_CAMP_YEAR}.csv")
grouped.to_csv(impact_year_file, index=False)
print(f" Saved managed_care_impact_scores_{SELECTED_CAMP_YEAR}.csv  {len(grouped):,} rows")

_impact_dfs = []
for _yr in ["2025", "2026"]:
    _yf = os.path.join(output_dir, f"managed_care_impact_scores_{_yr}.csv")
    if os.path.exists(_yf):
        _impact_dfs.append(pd.read_csv(_yf, low_memory=False))
if _impact_dfs:
    import pandas as _pd_merge
    pd.concat(_impact_dfs, ignore_index=True).to_csv(
        os.path.join(output_dir, "managed_care_impact_scores.csv"), index=False
    )
    print(f" Saved managed_care_impact_scores.csv (master  all camp years)")

#  Output 3: PROGRAM ALLOCATION 
# Save year-specific file + merge all years into master
alloc_year_file = os.path.join(output_dir, f"managed_care_program_allocation_{SELECTED_CAMP_YEAR}.csv")
top_impact_per_user.to_csv(alloc_year_file, index=False)
print(f"[DEBUG] About to save {len(top_impact_per_user)} rows to database...")
save_dataframe(top_impact_per_user, "programme_allocation", if_exists="replace")
print(f" Saved managed_care_program_allocation_{SELECTED_CAMP_YEAR}.csv  {len(top_impact_per_user):,} users")

_alloc_dfs = []
for _yr in ["2025", "2026"]:
    _yf = os.path.join(output_dir, f"managed_care_program_allocation_{_yr}.csv")
    if os.path.exists(_yf):
        _alloc_dfs.append(pd.read_csv(_yf, low_memory=False))
if _alloc_dfs:
    pd.concat(_alloc_dfs, ignore_index=True).to_csv(
        os.path.join(output_dir, "managed_care_program_allocation.csv"), index=False
    )
    print(f" Saved managed_care_program_allocation.csv (master  all camp years  {sum(len(d) for d in _alloc_dfs):,} users)")


















