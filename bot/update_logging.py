"""
Script to replace print statements with logger calls in database.py

This script systematically replaces print() calls with appropriate logger methods
based on the emoji/message content.
"""
import re
from pathlib import Path

def get_log_level(message: str) -> str:
    """Determine appropriate log level based on message content"""
    if any(emoji in message for emoji in ['❌', '✗']):
        return 'error'
    elif any(emoji in message for emoji in ['⚠️', '⚠']):
        return 'warning'
    elif any(emoji in message for emoji in ['✅', '✓', '📥']):
        return 'info'
    elif 'debug' in message.lower():
        return 'debug'
    else:
        return 'info'

def replace_prints_in_file(filepath: Path):
    """Replace print statements with logger calls"""
    content = filepath.read_text(encoding='utf-8')
    original_content = content

    # Pattern to match print statements
    # Handles: print(f"..."), print("..."), print(f'...'), print('...')
    pattern = r'print\((f?["\'])(.*?)(["\'])\)'

    def replacer(match):
        f_prefix = match.group(1)  # 'f"', 'f'', '"', or "'"
        message = match.group(2)
        quote = match.group(3)

        # Determine log level
        level = get_log_level(message)

        # Reconstruct with logger
        if f_prefix.startswith('f'):
            return f'logger.{level}(f{quote}{message}{quote})'
        else:
            return f'logger.{level}({quote}{message}{quote})'

    # Replace all print statements
    new_content = re.sub(pattern, replacer, content)

    # Count replacements
    num_replacements = content.count('print(') - new_content.count('print(')

    if num_replacements > 0:
        filepath.write_text(new_content, encoding='utf-8')
        print(f"✓ Updated {filepath.name}: {num_replacements} print statements replaced")
        return num_replacements
    else:
        print(f"  No print statements found in {filepath.name}")
        return 0

if __name__ == '__main__':
    # Update database.py
    db_file = Path(__file__).parent / 'database.py'

    if db_file.exists():
        total = replace_prints_in_file(db_file)
        print(f"\nTotal: {total} print statements replaced with logger calls")
    else:
        print(f"Error: {db_file} not found")
