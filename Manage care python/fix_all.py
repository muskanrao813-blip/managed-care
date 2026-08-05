#!/usr/bin/env python3
"""
Fix all encoding issues in scripts
- Remove problematic print statements and their continuations
- Keep all business logic intact
"""

import re

scripts = [
    "01_raw_data_program_allocation.py",
    "02_comparison_retest_analysis.py",
    "03b_device_eligibility_2026.py",
    "04_claude_analysis.py"
]

def fix_script(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by lines to process
    lines = content.split('\n')
    fixed_lines = []
    skip_until_close = False
    paren_depth = 0

    for i, line in enumerate(lines):
        # If we're in a multi-line print, skip until we find the closing paren
        if skip_until_close:
            paren_depth += line.count('(') - line.count(')')
            if paren_depth <= 0:
                skip_until_close = False
            continue

        # Check if this line has non-ASCII in a print statement
        if 'print(' in line:
            try:
                line.encode('ascii')
                fixed_lines.append(line)
            except UnicodeEncodeError:
                # Count parens to handle multi-line prints
                paren_depth = line.count('(') - line.count(')')
                if paren_depth > 0:
                    skip_until_close = True
                # Add pass with proper indent
                indent = len(line) - len(line.lstrip())
                fixed_lines.append(' ' * indent + 'pass')
        else:
            # Check for non-ASCII characters in any line
            try:
                line.encode('ascii')
                fixed_lines.append(line)
            except UnicodeEncodeError:
                # Replace problematic comments with ASCII
                fixed_lines.append(line.encode('ascii', 'replace').decode('ascii'))

    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(fixed_lines))
    return True

if __name__ == "__main__":
    for script in scripts:
        try:
            if fix_script(script):
                print(f"[OK] {script}")
        except Exception as e:
            print(f"[ERROR] {script}: {e}")
