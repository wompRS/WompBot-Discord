"""
Logo matcher utility for finding car manufacturer and series logos.

This module provides functionality to match iRacing car names to manufacturer logos
and series names to series logos.
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict
import re


class LogoMatcher:
    """Matches car names to manufacturer logos and series names to series logos."""

    def __init__(self, assets_dir: str = None):
        """
        Initialize the LogoMatcher.

        Args:
            assets_dir: Path to assets directory (defaults to bot/assets)
        """
        if assets_dir is None:
            # Default to bot/assets relative to this file
            assets_dir = Path(__file__).parent / 'assets'

        self.assets_dir = Path(assets_dir)
        self.car_logos_dir = self.assets_dir / 'car_logos_raw' / 'logos'
        self.series_logos_dir = self.assets_dir / 'series_logos'

        # Load car logos data
        self.car_logos_data = self._load_car_logos_data()

        # Create lookup dictionaries
        self.name_to_slug = {}
        self.slug_to_data = {}

        if self.car_logos_data:
            for logo_entry in self.car_logos_data:
                name = logo_entry.get('name', '').lower()
                slug = logo_entry.get('slug', '')

                self.name_to_slug[name] = slug
                self.slug_to_data[slug] = logo_entry

    def _load_car_logos_data(self) -> Optional[list]:
        """Load the car logos data.json file."""
        data_file = self.car_logos_dir / 'data.json'

        if not data_file.exists():
            print(f"⚠️ Car logos data.json not found at {data_file}")
            return None

        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading car logos data: {e}")
            return None

    def extract_manufacturer(self, car_name: str) -> str:
        """
        Extract manufacturer name from iRacing car name.

        Examples:
            "Mercedes-AMG GT3 2020" -> "mercedes-benz"
            "BMW M4 GT3" -> "bmw"
            "Porsche 911 GT3 R" -> "porsche"
            "Ferrari 488 GT3 Evo 2020" -> "ferrari"
            "McLaren 720S GT3" -> "mclaren"

        Args:
            car_name: Full iRacing car name

        Returns:
            Manufacturer slug (lowercase, dash-separated)
        """
        # Common manufacturer mappings for iRacing cars
        manufacturer_map = {
            'mercedes': 'mercedes-benz',
            'merc': 'mercedes-benz',
            'amg': 'mercedes-benz',
            'alfa romeo': 'alfa-romeo',
            'alfa': 'alfa-romeo',
            'aston martin': 'aston-martin',
            'aston': 'aston-martin',
            'land rover': 'land-rover',
            'rolls royce': 'rolls-royce',
            'rolls-royce': 'rolls-royce',
            'vw': 'volkswagen',
        }

        # Split on spaces and dashes
        parts = re.split(r'[\s\-]+', car_name.lower())

        if not parts:
            return car_name.lower()

        # Check for multi-word manufacturers first
        if len(parts) >= 2:
            two_word = f"{parts[0]} {parts[1]}"
            if two_word in manufacturer_map:
                return manufacturer_map[two_word]

            # Check with dash
            two_word_dash = f"{parts[0]}-{parts[1]}"
            if two_word_dash in self.name_to_slug:
                return two_word_dash

        # Single word manufacturer
        manufacturer = parts[0]

        # Apply manufacturer map
        if manufacturer in manufacturer_map:
            return manufacturer_map[manufacturer]

        return manufacturer

    def get_car_logo(self, car_name: str, size: str = 'optimized') -> Optional[Path]:
        """
        Get the path to a car manufacturer logo.

        Args:
            car_name: iRacing car name (e.g., "Mercedes-AMG GT3 2020")
            size: Logo size - 'optimized', 'thumb', or 'original'

        Returns:
            Path to logo file, or None if not found
        """
        manufacturer = self.extract_manufacturer(car_name)

        # Try to find the manufacturer in our data
        slug = self.name_to_slug.get(manufacturer, manufacturer)

        # Check if logo file exists
        logo_path = self.car_logos_dir / size / f"{slug}.png"

        if logo_path.exists():
            return logo_path

        # If not found, try with just the first part before any dash
        if '-' in slug:
            base_slug = slug.split('-')[0]
            logo_path = self.car_logos_dir / size / f"{base_slug}.png"
            if logo_path.exists():
                return logo_path

        # Debug output (can be removed later)
        # print(f"⚠️ Logo not found for {car_name} (manufacturer: {manufacturer}, slug: {slug})")
        return None

    def get_series_logo(self, series_name: str) -> Optional[Path]:
        """
        Get the path to a series logo.

        The series logo files should be named based on the series name with:
        - Lowercase
        - Spaces and special characters replaced with underscores
        - Common extensions: .png, .jpg, .jpeg, .svg

        Examples:
            "GT3 Challenge Fixed by Fanatec" -> "gt3_challenge_fixed_by_fanatec.png"
            "Formula 3.5" -> "formula_3_5.png"

        Args:
            series_name: iRacing series name

        Returns:
            Path to logo file, or None if not found
        """
        if not self.series_logos_dir.exists():
            return None

        # Normalize series name to filename
        # Convert to lowercase, replace spaces and special chars with underscores
        filename = re.sub(r'[^\w\s-]', '_', series_name.lower())
        filename = re.sub(r'[\s-]+', '_', filename)
        filename = re.sub(r'_+', '_', filename)  # Remove duplicate underscores
        filename = filename.strip('_')

        # Try common extensions
        for ext in ['.png', '.jpg', '.jpeg', '.svg', '.webp']:
            logo_path = self.series_logos_dir / f"{filename}{ext}"
            if logo_path.exists():
                return logo_path

        # Try without cleaning special chars (in case files are named differently)
        simple_filename = series_name.lower().replace(' ', '_')
        for ext in ['.png', '.jpg', '.jpeg', '.svg', '.webp']:
            logo_path = self.series_logos_dir / f"{simple_filename}{ext}"
            if logo_path.exists():
                return logo_path

        # Debug output (can be removed later)
        # print(f"⚠️ Series logo not found for {series_name} (tried: {filename})")
        return None

    def list_available_series_logos(self) -> list:
        """
        List all available series logo files.

        Returns:
            List of series logo file paths
        """
        if not self.series_logos_dir.exists():
            return []

        logos = []
        for ext in ['*.png', '*.jpg', '*.jpeg', '*.svg', '*.webp']:
            logos.extend(self.series_logos_dir.glob(ext))

        return sorted(logos)

    def test_car_matches(self, car_names: list) -> Dict[str, str]:
        """
        Test which car names can be matched to logos.

        Args:
            car_names: List of iRacing car names

        Returns:
            Dictionary of car_name -> logo_status
        """
        results = {}

        for car_name in car_names:
            logo = self.get_car_logo(car_name)
            if logo:
                results[car_name] = f"✅ {logo.name}"
            else:
                manufacturer = self.extract_manufacturer(car_name)
                results[car_name] = f"❌ Not found (manufacturer: {manufacturer})"

        return results


# Convenience functions for easy imports
def get_car_logo(car_name: str, size: str = 'optimized') -> Optional[Path]:
    """
    Get the path to a car manufacturer logo.

    Args:
        car_name: iRacing car name
        size: Logo size - 'optimized', 'thumb', or 'original'

    Returns:
        Path to logo file, or None if not found
    """
    matcher = LogoMatcher()
    return matcher.get_car_logo(car_name, size)


def get_series_logo(series_name: str) -> Optional[Path]:
    """
    Get the path to a series logo.

    Args:
        series_name: iRacing series name

    Returns:
        Path to logo file, or None if not found
    """
    matcher = LogoMatcher()
    return matcher.get_series_logo(series_name)


if __name__ == '__main__':
    # Test the matcher
    matcher = LogoMatcher()

    print("=" * 70)
    print("TESTING CAR LOGO MATCHES")
    print("=" * 70)

    test_cars = [
        "Mercedes-AMG GT3 2020",
        "BMW M4 GT3",
        "Porsche 911 GT3 R",
        "Ferrari 488 GT3 Evo 2020",
        "McLaren 720S GT3",
        "Audi R8 LMS GT3 Evo II",
        "Lamborghini Huracán GT3 EVO",
        "Ford Mustang GT3",
        "Chevrolet Corvette C8.R GTE",
        "Acura ARX-06 GTP"
    ]

    results = matcher.test_car_matches(test_cars)
    for car, status in results.items():
        print(f"{car:45} -> {status}")

    print("\n" + "=" * 70)
    print("AVAILABLE SERIES LOGOS")
    print("=" * 70)

    series_logos = matcher.list_available_series_logos()
    if series_logos:
        for logo in series_logos:
            print(f"  - {logo.name}")
    else:
        print("  No series logos found in", matcher.series_logos_dir)
        print("  Please copy series logos to this directory.")
