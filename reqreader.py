import argparse
import re
import requests
from packaging.specifiers import SpecifierSet
from packaging.version import Version
from typing import List, Tuple, Dict, Set


def read_requirements(file_path: str) -> List[Tuple[str, str]]:
    """Read a requirements.txt file and parse package names and versions."""
    with open(file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()
    packages = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([a-zA-Z0-9_\-]+)==([a-zA-Z0-9._\-]+)$", line)
        if match:
            packages.append((match.group(1), match.group(2)))
    return packages


def fetch_metadata_from_pypi(package: str, version: str) -> Dict:
    """Fetch package metadata from the PyPI JSON API."""
    url = f"https://pypi.org/pypi/{package}/{version}/json"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Failed to fetch metadata for {package}=={version}: {e}")
        return {}


def extract_requires_python(metadata: Dict) -> str:
    """Extract Requires-Python from the PyPI metadata."""
    return metadata.get("info", {}).get("requires_python", "")


def parse_python_versions(specifiers: List[SpecifierSet]) -> Set[str]:
    """Parse and refine Python versions based on specifiers."""
    valid_versions = {f"{major}.{minor}" for major in range(3, 12) for minor in range(0, 14)}
    for spec in specifiers:
        valid_versions = {ver for ver in valid_versions if Version(ver) in spec}
    return valid_versions

def determine_compatible_python_versions(requirements_file: str):
    """Determine compatible Python versions based on requirements."""
    packages = read_requirements(requirements_file)
    specifiers = []

    for package, version in packages:
        metadata = fetch_metadata_from_pypi(package, version)
        requires_python = extract_requires_python(metadata)
        if requires_python:
            print(f"{package}=={version} requires Python: {requires_python}")
            specifiers.append(SpecifierSet(requires_python))
        else:
            print(f"No Requires-Python found for {package}=={version}")

    compatible_versions = parse_python_versions(specifiers)
    if compatible_versions:
        sorted_versions = sorted(compatible_versions, key=Version)  # Semantic sorting
        print(f"Compatible Python versions: {sorted_versions}")
    else:
        print("Could not determine compatible Python versions. Check manually.")


def main():
    """Main function to handle command-line arguments."""
    parser = argparse.ArgumentParser(description="Determine compatible Python versions from a requirements.txt file.")
    parser.add_argument(
        "requirements_file",
        nargs="?",
        default="requirements.txt",
        help="Path to the requirements.txt file (default: requirements.txt)",
    )
    args = parser.parse_args()
    determine_compatible_python_versions(args.requirements_file)


if __name__ == "__main__":
    main()