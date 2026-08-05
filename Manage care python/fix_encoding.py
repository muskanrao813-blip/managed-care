#!/usr/bin/env python3
"""
Fix Unicode encoding issues in Python scripts
Replaces smart quotes and em-dashes with ASCII equivalents
PRESERVES ALL LOGIC - only fixes character encoding
"""

import os
import re

# Map of problematic Unicode chars to ASCII replacements
REPLACEMENTS = {
    '“': '"',  # Left double quote
    '”': '"',  # Right double quote
    '‘': "'",  # Left single quote
    '’': "'",  # Right single quote
    '–': '-',  # En dash
    '—': '-',  # Em dash
    '‑': '-',  # Non-breaking hyphen
    '‒': '-',  # Figure dash
    '―': '-',  # Horizontal bar
}

scripts = [
    "01_raw_data_program_allocation.py",
    "02_comparison_retest_analysis.py",
    "03b_device_eligibility_2026.py",
    "04_claude_analysis.py"
]

def fix_file(filepath):
    """Fix encoding in a single file"""
    try:
        # Read with UTF-8
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Track if changed
        original = content

        # Replace each problematic character
        for bad, good in REPLACEMENTS.items():
            content = content.replace(bad, good)

        # Write back
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        changed = content != original
        return True, changed

    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    print("=" * 60)
    print("Fixing Unicode encoding in scripts...")
    print("=" * 60)

    for script in scripts:
        filepath = os.path.join(os.getcwd(), script)
        if os.path.exists(filepath):
            success, result = fix_file(filepath)
            if success:
                status = "FIXED" if result else "OK (no changes)"
                print(f"[{status}] {script}")
            else:
                print(f"[ERROR] {script}: {result}")
        else:
            print(f"[SKIP] {script} not found")

    print("=" * 60)
    print("Done! Scripts are now clean.")
    print("=" * 60)
