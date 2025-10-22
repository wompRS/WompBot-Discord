#!/usr/bin/env python3
"""
Normalize series logo filenames.

This script renames all logo files in the series_logos directory to a
consistent naming convention:
- Lowercase
- Spaces and dashes replaced with underscores
- Special characters removed
- Multiple underscores consolidated to single underscore
"""

import os
import re
from pathlib import Path


def normalize_filename(filename: str) -> str:
    """
    Normalize a filename.

    Args:
        filename: Original filename (with extension)

    Returns:
        Normalized filename
    """
    # Split into name and extension
    name, ext = os.path.splitext(filename)

    # Lowercase
    name = name.lower()

    # Replace spaces and dashes with underscores
    name = name.replace(' ', '_').replace('-', '_')

    # Remove special characters (keep only alphanumeric and underscores)
    name = re.sub(r'[^a-z0-9_]', '_', name)

    # Consolidate multiple underscores
    name = re.sub(r'_+', '_', name)

    # Remove leading/trailing underscores
    name = name.strip('_')

    return f"{name}{ext.lower()}"


def main():
    """Normalize all series logo filenames."""
    logos_dir = Path(__file__).parent / 'series_logos'

    if not logos_dir.exists():
        print(f"Series logos directory not found: {logos_dir}")
        return

    print(f"Normalizing filenames in: {logos_dir}")
    print("=" * 70)

    renamed_count = 0

    for file_path in logos_dir.iterdir():
        if not file_path.is_file():
            continue

        old_name = file_path.name
        new_name = normalize_filename(old_name)

        if old_name != new_name:
            new_path = file_path.parent / new_name

            # Check if target already exists
            if new_path.exists():
                print(f"⚠️  Target exists: {old_name} -> {new_name}")
                continue

            file_path.rename(new_path)
            print(f"✅ {old_name} -> {new_name}")
            renamed_count += 1
        else:
            print(f"   {old_name} (no change)")

    print("=" * 70)
    print(f"Renamed {renamed_count} files")


if __name__ == '__main__':
    main()
