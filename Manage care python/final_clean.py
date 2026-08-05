#!/usr/bin/env python3
"""
Final comprehensive cleanup of encoding issues
"""

import re

files = [
    "01_raw_data_program_allocation.py",
    "02_comparison_retest_analysis.py",
    "03b_device_eligibility_2026.py",
    "04_claude_analysis.py"
]

for filepath in files:
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    # Remove lines that are just Unicode gibberish (comment lines)
    lines = content.split('\n')
    cleaned = []

    for line in lines:
        # Skip lines that are entirely Unicode box-drawing or gibberish
        if re.match(r'^\s*#\s*[?"??"?"âãÃ-]+\s*$', line):
            continue
        # Skip orphaned f-string continuations
        if re.match(r'^\s+f"[^"]*\$', line):
            continue
        cleaned.append(line)

    content = '\n'.join(cleaned)

    # Replace Unicode dashes and arrows with ASCII
    replacements = {
        '?': '-',
        '?': '-',
        '?': '-',
        '?': '-',
        '?': '-',
        '?': '',
        '?': '',
        '?': '',
        '?': '',
        '?': '',
        '?': '->',
        '?': 'x',
        '?': '',
    }

    for bad, good in replacements.items():
        content = content.replace(bad, good)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"[OK] {filepath}")
