export interface LabBucket {
  label: string;
  outcomeValue: 0 | 1 | 2 | 3;
  low: number;
  high: number;
}

const INF = Infinity;

const HbA1c: LabBucket[] = [
  { label: 'Normal_NC', outcomeValue: 0, low: -INF, high: 5.70 },
  { label: 'Borderline', outcomeValue: 1, low: 5.71, high: 6.40 },
  { label: 'High', outcomeValue: 2, low: 6.41, high: 12.00 },
  { label: 'SevHigh', outcomeValue: 3, low: 12.01, high: INF },
];

const TSH_MALE: LabBucket[] = [
  { label: 'SevLow', outcomeValue: 3, low: -INF, high: 0.05 },
  { label: 'Low', outcomeValue: 3, low: 0.06, high: 0.30 },
  { label: 'BordLow', outcomeValue: 1, low: 0.31, high: 0.38 },
  { label: 'Normal', outcomeValue: 0, low: 0.39, high: 5.33 },
  { label: 'BordHigh', outcomeValue: 1, low: 5.34, high: 5.50 },
  { label: 'High', outcomeValue: 2, low: 5.51, high: 30.00 },
  { label: 'SevHigh', outcomeValue: 3, low: 30.01, high: INF },
];

const TSH_FEMALE: LabBucket[] = [
  { label: 'SevLow', outcomeValue: 3, low: -INF, high: 0.05 },
  { label: 'Low', outcomeValue: 3, low: 0.06, high: 0.20 },
  { label: 'BordLow', outcomeValue: 1, low: 0.21, high: 0.27 },
  { label: 'Normal', outcomeValue: 0, low: 0.28, high: 4.20 },
  { label: 'BordHigh', outcomeValue: 1, low: 4.21, high: 5.00 },
  { label: 'High', outcomeValue: 2, low: 5.01, high: 30.00 },
  { label: 'SevHigh', outcomeValue: 3, low: 30.01, high: INF },
];

const T3_MALE: LabBucket[] = [
  { label: 'SevLow', outcomeValue: 3, low: -INF, high: 29.99 },
  { label: 'Low', outcomeValue: 3, low: 30, high: 80 },
  { label: 'BordLow', outcomeValue: 1, low: 80.01, high: 87 },
  { label: 'Normal', outcomeValue: 0, low: 87.01, high: 178 },
  { label: 'BordHigh', outcomeValue: 1, low: 178.01, high: 190 },
  { label: 'High', outcomeValue: 2, low: 190.01, high: 300 },
  { label: 'SevHigh', outcomeValue: 3, low: 300.01, high: INF },
];

const T3_FEMALE: LabBucket[] = [
  { label: 'SevLow', outcomeValue: 3, low: -INF, high: 29.99 },
  { label: 'Low', outcomeValue: 3, low: 30, high: 80 },
  { label: 'BordLow', outcomeValue: 1, low: 80.01, high: 84.6 },
  { label: 'Normal', outcomeValue: 0, low: 84.61, high: 202 },
  { label: 'BordHigh', outcomeValue: 1, low: 202.01, high: 210 },
  { label: 'High', outcomeValue: 2, low: 210.01, high: 300 },
  { label: 'SevHigh', outcomeValue: 3, low: 300.01, high: INF },
];

const T4_MALE: LabBucket[] = [
  { label: 'SevLow', outcomeValue: 3, low: -INF, high: 2.00 },
  { label: 'Low', outcomeValue: 3, low: 2.01, high: 4.50 },
  { label: 'BordLow', outcomeValue: 1, low: 4.51, high: 5.48 },
  { label: 'Normal', outcomeValue: 0, low: 5.49, high: 14.28 },
  { label: 'BordHigh', outcomeValue: 1, low: 14.29, high: 15.00 },
  { label: 'High', outcomeValue: 2, low: 15.01, high: 100 },
  { label: 'SevHigh', outcomeValue: 3, low: 100.01, high: INF },
];

const T4_FEMALE: LabBucket[] = [
  { label: 'SevLow', outcomeValue: 3, low: -INF, high: 2.00 },
  { label: 'Low', outcomeValue: 3, low: 2.01, high: 4.50 },
  { label: 'BordLow', outcomeValue: 1, low: 4.51, high: 5.12 },
  { label: 'Normal', outcomeValue: 0, low: 5.13, high: 14.06 },
  { label: 'BordHigh', outcomeValue: 1, low: 14.07, high: 15.00 },
  { label: 'High', outcomeValue: 2, low: 15.01, high: 100 },
  { label: 'SevHigh', outcomeValue: 3, low: 100.01, high: INF },
];

const Albumin: LabBucket[] = [
  { label: 'SevLow', outcomeValue: 3, low: -INF, high: 0.50 },
  { label: 'Low', outcomeValue: 2, low: 0.51, high: 3.00 },
  { label: 'BordLow', outcomeValue: 1, low: 3.01, high: 3.50 },
  { label: 'Normal', outcomeValue: 0, low: 3.51, high: INF },
];

const ALP: LabBucket[] = [
  { label: 'NC', outcomeValue: 0, low: -INF, high: 29.99 },
  { label: 'Normal', outcomeValue: 0, low: 30, high: 120 },
  { label: 'Borderline', outcomeValue: 1, low: 120.01, high: 130 },
  { label: 'High', outcomeValue: 2, low: 130.01, high: 500 },
  { label: 'SevHigh', outcomeValue: 3, low: 500.01, high: INF },
];

const BilirubinDirect: LabBucket[] = [
  { label: 'Normal', outcomeValue: 0, low: -INF, high: 0.20 },
  { label: 'Borderline', outcomeValue: 1, low: 0.21, high: 0.80 },
  { label: 'High', outcomeValue: 2, low: 0.81, high: 5.00 },
  { label: 'SevHigh', outcomeValue: 3, low: 5.01, high: INF },
];

const BilirubinTotal: LabBucket[] = [
  { label: 'NC', outcomeValue: 0, low: -INF, high: 0.20 },
  { label: 'Normal', outcomeValue: 0, low: 0.21, high: 1.20 },
  { label: 'Borderline', outcomeValue: 1, low: 1.21, high: 1.50 },
  { label: 'High', outcomeValue: 2, low: 1.51, high: 5.00 },
  { label: 'SevHigh', outcomeValue: 3, low: 5.01, high: INF },
];

const GGTP_MALE: LabBucket[] = [
  { label: 'NC', outcomeValue: 0, low: -INF, high: 11.99 },
  { label: 'Normal', outcomeValue: 0, low: 12, high: 55 },
  { label: 'Borderline', outcomeValue: 1, low: 55.01, high: 65 },
  { label: 'High', outcomeValue: 2, low: 65.01, high: 200 },
  { label: 'SevHigh', outcomeValue: 3, low: 200.01, high: INF },
];

const GGTP_FEMALE: LabBucket[] = [
  { label: 'NC', outcomeValue: 0, low: -INF, high: 8.99 },
  { label: 'Normal', outcomeValue: 0, low: 9, high: 38 },
  { label: 'Borderline', outcomeValue: 1, low: 38.01, high: 45 },
  { label: 'High', outcomeValue: 2, low: 45.01, high: 150 },
  { label: 'SevHigh', outcomeValue: 3, low: 150.01, high: INF },
];

const SGOT_MALE: LabBucket[] = [
  { label: 'NC', outcomeValue: 0, low: -INF, high: 4.99 },
  { label: 'Normal', outcomeValue: 0, low: 5, high: 50 },
  { label: 'Borderline', outcomeValue: 1, low: 50.01, high: 60 },
  { label: 'High', outcomeValue: 2, low: 60.01, high: 150 },
  { label: 'SevHigh', outcomeValue: 3, low: 150.01, high: INF },
];

const SGOT_FEMALE: LabBucket[] = [
  { label: 'NC', outcomeValue: 0, low: -INF, high: 4.99 },
  { label: 'Normal', outcomeValue: 0, low: 5, high: 35 },
  { label: 'Borderline', outcomeValue: 1, low: 35.01, high: 40 },
  { label: 'High', outcomeValue: 2, low: 40.01, high: 150 },
  { label: 'SevHigh', outcomeValue: 3, low: 150.01, high: INF },
];

const SGPT_MALE: LabBucket[] = [
  { label: 'Normal', outcomeValue: 0, low: -INF, high: 50 },
  { label: 'Borderline', outcomeValue: 1, low: 50.01, high: 60 },
  { label: 'High', outcomeValue: 2, low: 60.01, high: 150 },
  { label: 'SevHigh', outcomeValue: 3, low: 150.01, high: INF },
];

const SGPT_FEMALE: LabBucket[] = [
  { label: 'Normal', outcomeValue: 0, low: -INF, high: 35 },
  { label: 'Borderline', outcomeValue: 1, low: 35.01, high: 45 },
  { label: 'High', outcomeValue: 2, low: 45.01, high: 150 },
  { label: 'SevHigh', outcomeValue: 3, low: 150.01, high: INF },
];

const BUN: LabBucket[] = [
  { label: 'NC', outcomeValue: 0, low: -INF, high: 8 },
  { label: 'Normal', outcomeValue: 0, low: 8.01, high: 23 },
  { label: 'Borderline', outcomeValue: 1, low: 23.01, high: 30 },
  { label: 'High', outcomeValue: 2, low: 30.01, high: 100 },
  { label: 'SevHigh', outcomeValue: 3, low: 100.01, high: INF },
];

const Creatinine_MALE: LabBucket[] = [
  { label: 'NC', outcomeValue: 0, low: -INF, high: 0.72 },
  { label: 'Normal', outcomeValue: 0, low: 0.73, high: 1.18 },
  { label: 'Borderline', outcomeValue: 1, low: 1.19, high: 1.40 },
  { label: 'High', outcomeValue: 2, low: 1.41, high: 2.00 },
  { label: 'SevHigh', outcomeValue: 3, low: 2.01, high: INF },
];

const Creatinine_FEMALE: LabBucket[] = [
  { label: 'NC', outcomeValue: 0, low: -INF, high: 0.55 },
  { label: 'Normal', outcomeValue: 0, low: 0.56, high: 1.02 },
  { label: 'Borderline', outcomeValue: 1, low: 1.03, high: 1.40 },
  { label: 'High', outcomeValue: 2, low: 1.41, high: 2.00 },
  { label: 'SevHigh', outcomeValue: 3, low: 2.01, high: INF },
];

const Urea: LabBucket[] = [
  { label: 'NC', outcomeValue: 0, low: -INF, high: 17 },
  { label: 'Normal', outcomeValue: 0, low: 17.01, high: 43 },
  { label: 'Borderline', outcomeValue: 1, low: 43.01, high: 50 },
  { label: 'High', outcomeValue: 2, low: 50.01, high: 150 },
  { label: 'SevHigh', outcomeValue: 3, low: 150.01, high: INF },
];

const UricAcid_MALE: LabBucket[] = [
  { label: 'NC', outcomeValue: 0, low: -INF, high: 3.5 },
  { label: 'Normal', outcomeValue: 0, low: 3.51, high: 7.20 },
  { label: 'Borderline', outcomeValue: 1, low: 7.21, high: 8.00 },
  { label: 'High', outcomeValue: 2, low: 8.01, high: 20.00 },
  { label: 'SevHigh', outcomeValue: 3, low: 20.01, high: INF },
];

const UricAcid_FEMALE: LabBucket[] = [
  { label: 'NC', outcomeValue: 0, low: -INF, high: 2.6 },
  { label: 'Normal', outcomeValue: 0, low: 2.61, high: 6.00 },
  { label: 'Borderline', outcomeValue: 1, low: 6.01, high: 6.50 },
  { label: 'High', outcomeValue: 2, low: 6.51, high: 20.00 },
  { label: 'SevHigh', outcomeValue: 3, low: 20.01, high: INF },
];

const BUNCreatRatio: LabBucket[] = [
  { label: 'SevLow', outcomeValue: 3, low: -INF, high: 5.0 },
  { label: 'Low', outcomeValue: 2, low: 5.01, high: 10.00 },
  { label: 'Normal', outcomeValue: 0, low: 10.01, high: 20 },
  { label: 'NC', outcomeValue: 0, low: 20.01, high: INF },
];

const TotalCholesterol: LabBucket[] = [
  { label: 'Normal', outcomeValue: 0, low: -INF, high: 200 },
  { label: 'Borderline', outcomeValue: 1, low: 200.01, high: 239 },
  { label: 'High', outcomeValue: 2, low: 239.01, high: 400 },
  { label: 'SevHigh', outcomeValue: 3, low: 400.01, high: INF },
];

const HDL: LabBucket[] = [
  { label: 'SevLow', outcomeValue: 3, low: -INF, high: 15 },
  { label: 'Low', outcomeValue: 2, low: 15.01, high: 38 },
  { label: 'BordLow', outcomeValue: 1, low: 38.01, high: 40 },
  { label: 'Normal', outcomeValue: 0, low: 40.01, high: 60 },
  { label: 'NC', outcomeValue: 0, low: 60.01, high: INF },
];

const LDL: LabBucket[] = [
  { label: 'Normal', outcomeValue: 0, low: -INF, high: 100 },
  { label: 'Borderline', outcomeValue: 1, low: 100.01, high: 159 },
  { label: 'High', outcomeValue: 2, low: 159.01, high: 400 },
  { label: 'SevHigh', outcomeValue: 3, low: 400.01, high: INF },
];

const NonHDL: LabBucket[] = [
  { label: 'Normal', outcomeValue: 0, low: -INF, high: 130 },
  { label: 'Borderline', outcomeValue: 1, low: 130.01, high: 189 },
  { label: 'High', outcomeValue: 2, low: 189.01, high: 400 },
  { label: 'SevHigh', outcomeValue: 3, low: 400.01, high: INF },
];

const Triglycerides: LabBucket[] = [
  { label: 'Normal', outcomeValue: 0, low: -INF, high: 150 },
  { label: 'Borderline', outcomeValue: 1, low: 150.01, high: 199 },
  { label: 'High', outcomeValue: 2, low: 199.01, high: 400 },
  { label: 'SevHigh', outcomeValue: 3, low: 400.01, high: INF },
];

export const CLASSIFY_RANGES: Record<string, LabBucket[]> = {
  HbA1c_MALE: HbA1c,
  HbA1c_FEMALE: HbA1c,
  HbA1c_OTHER: HbA1c,
  TSH_MALE: TSH_MALE,
  TSH_FEMALE: TSH_FEMALE,
  TSH_OTHER: TSH_FEMALE,
  T3_MALE: T3_MALE,
  T3_FEMALE: T3_FEMALE,
  T3_OTHER: T3_FEMALE,
  T4_MALE: T4_MALE,
  T4_FEMALE: T4_FEMALE,
  T4_OTHER: T4_FEMALE,
  Albumin_MALE: Albumin,
  Albumin_FEMALE: Albumin,
  Albumin_OTHER: Albumin,
  ALP_MALE: ALP,
  ALP_FEMALE: ALP,
  ALP_OTHER: ALP,
  BilirubinDirect_MALE: BilirubinDirect,
  BilirubinDirect_FEMALE: BilirubinDirect,
  BilirubinDirect_OTHER: BilirubinDirect,
  BilirubinTotal_MALE: BilirubinTotal,
  BilirubinTotal_FEMALE: BilirubinTotal,
  BilirubinTotal_OTHER: BilirubinTotal,
  GGTP_MALE: GGTP_MALE,
  GGTP_FEMALE: GGTP_FEMALE,
  GGTP_OTHER: GGTP_FEMALE,
  SGOT_MALE: SGOT_MALE,
  SGOT_FEMALE: SGOT_FEMALE,
  SGOT_OTHER: SGOT_FEMALE,
  SGPT_MALE: SGPT_MALE,
  SGPT_FEMALE: SGPT_FEMALE,
  SGPT_OTHER: SGPT_FEMALE,
  BUN_MALE: BUN,
  BUN_FEMALE: BUN,
  BUN_OTHER: BUN,
  Creatinine_MALE: Creatinine_MALE,
  Creatinine_FEMALE: Creatinine_FEMALE,
  Creatinine_OTHER: Creatinine_FEMALE,
  Urea_MALE: Urea,
  Urea_FEMALE: Urea,
  Urea_OTHER: Urea,
  UricAcid_MALE: UricAcid_MALE,
  UricAcid_FEMALE: UricAcid_FEMALE,
  UricAcid_OTHER: UricAcid_FEMALE,
  BUNCreatRatio_MALE: BUNCreatRatio,
  BUNCreatRatio_FEMALE: BUNCreatRatio,
  BUNCreatRatio_OTHER: BUNCreatRatio,
  TotalCholesterol_MALE: TotalCholesterol,
  TotalCholesterol_FEMALE: TotalCholesterol,
  TotalCholesterol_OTHER: TotalCholesterol,
  HDL_MALE: HDL,
  HDL_FEMALE: HDL,
  HDL_OTHER: HDL,
  LDL_MALE: LDL,
  LDL_FEMALE: LDL,
  LDL_OTHER: LDL,
  NonHDL_MALE: NonHDL,
  NonHDL_FEMALE: NonHDL,
  NonHDL_OTHER: NonHDL,
  Triglycerides_MALE: Triglycerides,
  Triglycerides_FEMALE: Triglycerides,
  Triglycerides_OTHER: Triglycerides,
};
