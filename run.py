import argparse
import requests
import re
from typing import List, Dict

def get_torchvision_matrix(url: str = "https://raw.githubusercontent.com/pytorch/vision/refs/heads/main/README.md") -> Dict[str, str]:
    """
    Fetch and parse the Torch and TorchVision compatibility matrix from the README file.
    Includes older versions listed under the `<details>` section.
    Returns a dictionary mapping Torch versions to TorchVision versions.
    """
    response = requests.get(url)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch data from {url}")

    content = response.text

    # Find the compatibility table sections, including older versions
    table_pattern = re.compile(
        r"\| `torch` \s*\| `torchvision` \s*\| Python \s*\|.*?\n((?:\|.*?\n)+)",  # Main table
        re.DOTALL
    )
    older_versions_pattern = re.compile(
        r"<details>.*?\| `torch` \s*\| `torchvision` \s*\| Python \s*\|.*?\n((?:\|.*?\n)+).*?</details>",
        re.DOTALL
    )

    # Match main table
    main_match = table_pattern.search(content)
    older_versions_match = older_versions_pattern.search(content)

    if not main_match:
        raise ValueError("TorchVision compatibility table not found in the README.")

    # Extract both sections
    main_table_content = main_match.group(1)
    older_table_content = older_versions_match.group(1) if older_versions_match else ""

    # Combine main and older sections
    combined_table_content = f"{main_table_content}\n{older_table_content}"

    # Parse the combined table rows into a dictionary
    compatibility = {}
    for row in combined_table_content.strip().split("\n"):
        columns = [col.strip(" `") for col in row.split("|")[1:-1]]  # Strip ` and whitespace
        if len(columns) >= 2:  # Ensure valid data row
            torch_version, torchvision_version = columns[:2]
            # Skip invalid torch versions
            try:
                float(torch_version)  # Validates if torch_version is a number
            except ValueError:
                continue  # Skip non-numeric versions
            compatibility[torch_version] = torchvision_version

    return compatibility

def fetch_whl_list(url: str = "https://download.pytorch.org/whl/torch_stable.html") -> List[str]:
    """
    Fetch and parse the list of wheel files from PyTorch's stable wheel index.
    """
    response = requests.get(url)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch data from {url}")

    html_content = response.text

    # Extract all .whl links (ignoring directory hierarchy)
    wheel_files = re.findall(r'href=".*?(torch[\w\.\-\+%]+\.whl)"', html_content)
    return wheel_files


def parse_wheel_file(wheel_file: str) -> Dict[str, str]:
    """
    Extract details from a wheel filename, handling a variety of build variants.
    """
    match = re.search(
        r"(?P<package>torch(?:audio|vision|tensorrt|rec|tune)?)"
        r"-(?P<version>[\d\.]+)"
        r"(?:%2B(?P<build_variant>[\w\.]+))?"
        r"-cp(?P<py_major>\d)(?P<py_minor>\d+)"
        r"-cp\d+"
        r"-[\w_\.]+\.whl",
        wheel_file
    )
    if match:
        return {
            "package": match.group("package"),
            "version": match.group("version"),
            "build_variant": match.group("build_variant") or "none",
            "python_version": f"{match.group('py_major')}.{match.group('py_minor')}",
        }
    return {}


def find_compatible_whl_files(python_version: str, cuda_version: str = None, build_variant: str = None) -> List[Dict[str, str]]:
    """
    Find compatible wheel files for the given Python version, CUDA version, and optional build variant.
    """
    wheel_files = fetch_whl_list()
    compatible_files = []

    for wheel_file in wheel_files:
        details = parse_wheel_file(wheel_file)
        if details:
            # Match Python version
            if details["python_version"] != python_version:
                continue

            # Match CUDA version if provided
            if cuda_version and cuda_version not in details["build_variant"]:
                continue

            # Match specific build variant if provided
            if build_variant and details["build_variant"] != build_variant:
                continue

            compatible_files.append(details)

    return compatible_files


def deduplicate_files(file_list: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Remove duplicates from the list of files based on 'package', 'version', and 'build_variant'.
    """
    seen = set()
    unique_files = []
    for file in file_list:
        identifier = (file['package'], file['version'], file['build_variant'])
        if identifier not in seen:
            seen.add(identifier)
            unique_files.append(file)
    return unique_files


def interactive_mode():
    python_version = input("Enter your Python version (e.g., 3.10): ").strip()
    cuda_version = input("Enter your CUDA version (e.g., 121 for CUDA 12.1) or leave blank for any: ").strip() or None
    build_variant = input("Enter build variant (e.g., cpu, cu121) or leave blank for any: ").strip() or None

    compatible_files = find_compatible_whl_files(python_version, cuda_version, build_variant)
    deduplicated_files = deduplicate_files(compatible_files)

    if deduplicated_files:
        print(f"Compatible wheel files for Python {python_version}, CUDA {cuda_version or 'any'}, and variant {build_variant or 'any'}:")
        for file in deduplicated_files:
            print(f"  - {file['package']} version: {file['version']} (build: {file['build_variant']})")
    else:
        print(f"No compatible wheel files found for Python {python_version}, CUDA {cuda_version or 'any'}, and variant {build_variant or 'any'}.")


def main():
    parser = argparse.ArgumentParser(description="PyTorch Version Selector")
    parser.add_argument("-i", "--interactive", action="store_true", help="Launch interactive mode")
    parser.add_argument("-p", "--python", type=str, help="Specify Python version (e.g., 3.10)")
    parser.add_argument("-c", "--cuda", type=str, help="Specify CUDA version (e.g., 121 for CUDA 12.1)")
    parser.add_argument("-b", "--build", type=str, help="Specify build variant (e.g., cpu, cu121)")

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
    elif args.python:
        try:
            # Fetch compatibility matrix for TorchVision
            torchvision_matrix = get_torchvision_matrix()

            # Find compatible Torch versions
            compatible_files = find_compatible_whl_files(args.python, args.cuda, args.build)
            deduplicated_files = deduplicate_files(compatible_files)

            if deduplicated_files:
                print(f"Compatible versions for Python {args.python}, CUDA {args.cuda or 'any'}, and variant {args.build or 'any'}:\n")
                for file in deduplicated_files:
                    if file["package"] == "torch":
                        #print(f"  - torch version: {file['version']} (build: {file['build_variant']})")
                        print(f"\ntorch=={file['version']}+{file['build_variant']}")
                        #print(f"     - torchaudio version: {file['version']} (build: {file['build_variant']})")
                        print(f"     torchaudio=={file['version']}+{file['build_variant']}")

                        # Match TorchVision versions (using the compatibility matrix)
                        torch_major = '.'.join(file['version'].split('.')[:2])  # Extract major and minor version of Torch
                        torch_minor = file['version'].split('.')[-1]  # Extract the minor release of Torch
                        
                        if torch_major in torchvision_matrix:
                            torchvision_major = torchvision_matrix[torch_major]
                            # Construct the TorchVision version using TorchVision's major version and Torch's minor release
                            torchvision_version = f"{torchvision_major}.{torch_minor}"
                            #print(f"        - torchvision version: {torchvision_version} (build: {file['build_variant']})")
                            print(f"     torchvision=={torchvision_version}+{file['build_variant']}")
                        else:
                            print("     - No matching torchvision version found.")
            else:
                print(f"No compatible wheel files found for Python {args.python}, CUDA {args.cuda or 'any'}, and variant {args.build or 'any'}.")
        except Exception as e:
            print(f"An error occurred: {e}")
    else:
        parser.print_help()



if __name__ == "__main__":
    main()
