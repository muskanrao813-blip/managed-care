# Dashboard: Start Server & Test Data Loading

## Quick Start (3 Steps)

### Step 1: Start the Dashboard Server
```bash
cd "D:\OneDrive - Bajaj Finserv Health Limited\Documents\manage care\Manage care python"
python run_dashboard.py
```

Output should show:
```
Starting server on http://localhost:8000
Press Ctrl+C to stop
```

### Step 2: Open in Browser
```
http://localhost:8000/managed_care_dashboard_final.html
```

### Step 3: Wait for Data to Load (10-15 seconds)
You should see:
- ✅ GREEN "LIVE" badge (top right) - means data loaded successfully
- ❌ If you see "DEMO MODE" badge - data didn't load, try "↻ Reload Data" button

---

## What Numbers Should You See?

### Top Row - Overview KPIs

| KPI | Expected Value |
|-----|-----------------|
| Total Camp Reports | ~10,485 (2026 camps) |
| Enrolled & Attended Camp | 2,058 (PURELIFE continued) |
| Programme Improvement Rate | ~26.8% |
| Zero Appointment Users | ~6,056 |

### Cohort Analysis Section

| Cohort | Expected Value |
|--------|-----------------|
| Very High Risk | 2,396 |
| High Risk | 2,802 |
| Moderate Risk | 869 |

---

## Troubleshooting

### Issue: "DEMO MODE" Badge Instead of "LIVE"
**Problem**: CSV files not found  
**Solution**: 
1. Click "↻ Reload Data" button
2. Check browser console (F12 → Console tab)
3. Look for error messages like "404 not found"

### Issue: Numbers Still Show Dashes (—)
**Problem**: Data loaded but not rendering  
**Solution**:
1. Hard refresh: **Ctrl+Shift+R** (not just Ctrl+R)
2. Close browser completely
3. Clear browser cache: **Ctrl+Shift+Delete**
4. Reopen dashboard

### Issue: Server Won't Start
**Problem**: Port 8000 already in use  
**Solution**:
```bash
# Find process using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID with actual number)
taskkill /PID <PID> /F

# Restart server
python run_dashboard.py
```

---

## Data Flow Verification

### How Data Loads
1. Page loads → calls `reloadData()` function
2. `detectDataFolder()` finds `./Data/` folder
3. All CSV files load via PapaParse (JavaScript CSV parser)
4. DATA object gets populated
5. `renderAll()` runs → displays numbers

### Files Required
```
✅ Data/managed_care_program_allocation.csv (5.6M)
✅ Data/managed_care_impact_scores.csv (12M)
✅ Data/managed_care_comparison.csv (9.5M)
✅ Data/managed_care_device_eligibility.csv (1.6M)
✅ Data/managed_care_policy_data.csv (2.1M)
✅ Data/managed_care_camp_monthly.csv (389B)
✅ Data/managed_care_appt_utilization.csv (1.9M)
✅ Data/managed_care_device_delivered_2025.csv (57K)
✅ Data/managed_care_device_impact_2025.csv (121B)
✅ Data/managed_care_device_eligibility_2026.csv (1.6M)
✅ Data/managed_care_benefit_assignments_2026.csv (90B)
✅ Data/managed_care_engagement_effect.csv (364B)
✅ Data/managed_care_hra_stats.csv (86B)
✅ Data/claude_insights.json (9.6K)
```

All files confirmed present in Data/ folder ✅

---

## Console Check

Press **F12** to open browser console. You should see:
```
Data folder found: ./Data/
CSVs loaded · ✅ allocation · ✅ comparison · ✅ device · ✅ impact · ...
```

No red error messages - only yellow warnings are OK.

---

## Date Filter Test

1. Look at top right of dashboard - you should see "From" and "To" month selectors
2. Current should be: **From: 2026-04, To: 2027-05** (2026 year)
3. Change From to: **2025-06** and To to: **2026-05**
4. Watch the numbers change - very high cohort should drop to ~1,600 (2025 numbers)
5. Change back to 2026-04 / 2027-05
6. Numbers should return to 2,396 very high cohort

---

## Expected Console Output

```
Data folder found: ./Data/
reloadData: START
CSV Parse complete: allocation (40216 rows)
CSV Parse complete: impact (77438 rows) 
CSV Parse complete: comparison (14898 rows)
CSV Parse complete: policy_data (16456 rows)
CSV Parse complete: device (31416 rows)
...
renderAll: START rendering 8 sections
renderOverview: Enrolled = 2058
renderCohorts: Cohorts = {Very High: 2396, High: 2802, Moderate: 869}
renderAll: COMPLETE
```

---

## Success Criteria

✅ Page loads without freezing  
✅ GREEN "LIVE" badge appears  
✅ All KPI boxes show numbers (not dashes)  
✅ Cohort numbers match expected:
   - Very High: 2,396
   - High: 2,802  
   - Moderate: 869
✅ Date filter works - numbers change when dates change  
✅ No red errors in console (F12)  

---

## Next Steps If Numbers Still Don't Show

1. **Send screenshot** of what you see with F12 console open
2. **Note the error messages** (if any) in red
3. **Check if badge says** "LIVE" or "DEMO MODE"
4. I'll diagnose based on error message

---

## Quick Reference Commands

| Action | Command |
|--------|---------|
| Start server | `python run_dashboard.py` |
| Stop server | Ctrl+C in terminal |
| Hard refresh | Ctrl+Shift+R |
| Clear cache | Ctrl+Shift+Delete |
| Open console | F12 |
| Check port | `netstat -ano \| findstr :8000` |

---

**The dashboard is ready - just start the server and open in browser! 🎯**
