#!/usr/bin/env python3
"""
Reproducible ICD-10-CM data fetcher from CMS.
Downloads the official 2024 ICD-10-CM codes from cms.gov.
"""

import urllib.request
import zipfile
import xml.etree.ElementTree as ET
import csv
from pathlib import Path
import hashlib
import sys

# Official CMS URL for 2024 ICD-10-CM
CMS_URL = "https://www.cms.gov/files/zip/2024-code-tables-tabular-and-index.zip"
EXPECTED_SHA256 = None  # Will be calculated on first download

def download_cms_data(output_dir="raw_data"):
    """Download ICD-10-CM data from CMS."""
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    zip_path = output_dir / "2024-ICD-10-CM.zip"

    # Download if not exists
    if not zip_path.exists():
        print(f"Downloading ICD-10-CM from CMS...")
        print(f"URL: {CMS_URL}")

        with urllib.request.urlopen(CMS_URL) as response:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(zip_path, 'wb') as f:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\rDownloading: {progress:.1f}%", end='')

        print(f"\n✓ Downloaded to {zip_path}")
    else:
        print(f"✓ Using cached {zip_path}")

    # Calculate SHA256 for reproducibility
    with open(zip_path, 'rb') as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    print(f"SHA256: {sha256}")

    return zip_path

def extract_xml(zip_path, output_dir="raw_data"):
    """Extract the tabular XML from the zip file."""
    output_dir = Path(output_dir)
    xml_file = "icd10cm_tabular_2024.xml"
    xml_path = output_dir / xml_file

    if not xml_path.exists():
        print(f"Extracting {xml_file}...")
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extract(xml_file, output_dir)
        print(f"✓ Extracted to {xml_path}")
    else:
        print(f"✓ Using cached {xml_path}")

    return xml_path

def parse_icd10_xml(xml_path):
    """Parse the ICD-10-CM XML and extract all codes."""
    print(f"Parsing {xml_path}...")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    codes = []

    # The structure is: chapter -> section -> diag (diagnosis)
    for chapter in root.findall('.//chapter'):
        chapter_name = chapter.find('name').text if chapter.find('name') is not None else ""

        for section in chapter.findall('.//section'):
            section_name = section.find('desc').text if section.find('desc') is not None else ""

            # Find all diagnosis codes in this section
            for diag in section.findall('.//diag'):
                code = diag.find('name').text if diag.find('name') is not None else ""
                desc = diag.find('desc').text if diag.find('desc') is not None else ""

                if code and desc:
                    # Clean up description
                    desc = desc.strip()

                    # Determine category from chapter/section
                    category = chapter_name if chapter_name else section_name
                    if category:
                        category = category[:50]  # Truncate long categories

                    codes.append({
                        'code': code,
                        'description': desc,
                        'category': category,
                        'country': 'US',  # ICD-10-CM is US variant
                        'source': 'CMS'
                    })

    print(f"✓ Parsed {len(codes)} ICD-10-CM codes")
    return codes

def save_to_csv(codes, output_file="data/icd10_cms_catalog.csv"):
    """Save codes to CSV."""
    output_path = Path(output_file)
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['code', 'description', 'category', 'country', 'source']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for code in codes:
            writer.writerow(code)

    print(f"✓ Saved {len(codes)} codes to {output_path}")

    # Print statistics
    categories = {}
    for code in codes:
        letter = code['code'][0] if code['code'] else '?'
        categories[letter] = categories.get(letter, 0) + 1

    print(f"\nCode distribution by category:")
    for letter in sorted(categories.keys()):
        print(f"  {letter}: {categories[letter]:,} codes")

    return output_path

def main():
    """Main function for reproducible data fetching."""
    print("="*60)
    print("ICD-10-CM Data Fetcher (CMS)")
    print("="*60)

    # Download
    zip_path = download_cms_data()

    # Extract
    xml_path = extract_xml(zip_path)

    # Parse
    codes = parse_icd10_xml(xml_path)

    if not codes:
        print("ERROR: No codes parsed!", file=sys.stderr)
        return 1

    # Save
    csv_path = save_to_csv(codes)

    print(f"\n✓ Successfully fetched {len(codes):,} ICD-10-CM codes")
    print(f"✓ Data saved to {csv_path}")
    print(f"\nTo import into database:")
    print(f"  python3 -c \"from db_manager import MedicalCodingDB; db = MedicalCodingDB(); db.import_catalog('{csv_path}')\"")

    return 0

if __name__ == "__main__":
    sys.exit(main())