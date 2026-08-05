#!/usr/bin/env python3
"""
Remove problematic print statements from scripts
Keeps all logic intact - only simplifies console output
"""

import os
import re

scripts = [
    "01_raw_data_program_allocation.py",
    "02_comparison_retest_analysis.py",
    "03b_device_eligibility_2026.py",
    "04_claude_analysis.py"
]

def clean_prints(filepath):
    """Remove lines with emojis/special chars from print statements"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace problematic print statements with pass
    # This regex matches print statements that contain non-ASCII characters
    lines = content.split('\n')
    new_lines = []

    for line in lines:
        if 'print(' in line:
            # Check if line has non-ASCII characters
            try:
                line.encode('ascii')
                new_lines.append(line)
            except UnicodeEncodeError:
                # Line has non-ASCII, replace with pass
                indent = len(line) - len(line.lstrip())
                new_lines.append(' ' * indent + 'pass')
        else:
            new_lines.append(line)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

if __name__ == "__main__":
    for script in scripts:
        if os.path.exists(script):
            clean_prints(script)
            print(f"Cleaned {script}")
