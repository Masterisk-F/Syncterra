import argparse
import json
import re
import sys
from pathlib import Path

def get_current_versions():
    versions = {}

    # Electron package.json
    electron_pkg = Path('electron/package.json')
    if electron_pkg.exists():
        with open(electron_pkg, 'r', encoding='utf-8') as f:
            data = json.load(f)
            versions['electron'] = data.get('version', 'unknown')

    # Frontend package.json
    frontend_pkg = Path('frontend/package.json')
    if frontend_pkg.exists():
        with open(frontend_pkg, 'r', encoding='utf-8') as f:
            data = json.load(f)
            versions['frontend'] = data.get('version', 'unknown')

    # pyproject.toml
    pyproject = Path('pyproject.toml')
    if pyproject.exists():
        with open(pyproject, 'r', encoding='utf-8') as f:
            content = f.read()
            match = re.search(r'^version\s*=\s*"(.*?)"', content, re.MULTILINE)
            if match:
                versions['backend'] = match.group(1)
            else:
                versions['backend'] = 'unknown'

    return versions

def update_json_version(file_path, new_version):
    path = Path(file_path)
    if not path.exists():
        print(f"Error: {file_path} not found.")
        return False

    try:
        # Read with json to preserve structure
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        old_version = data.get('version')
        data['version'] = new_version

        # Write back with formatting
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            # Add a trailing newline which json.dump might miss but is common in editors
            f.write('\n')

        print(f"Updated {file_path}: {old_version} -> {new_version}")
        return True
    except Exception as e:
        print(f"Failed to update {file_path}: {e}")
        return False

def update_toml_version(file_path, new_version):
    path = Path(file_path)
    if not path.exists():
        print(f"Error: {file_path} not found.")
        return False

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Use regex to find and replace the version line
        # Looks for: version = "0.1.0"
        pattern = r'^(version\s*=\s*)"(.*?)"'
        match = re.search(pattern, content, re.MULTILINE)

        if match:
            old_version = match.group(2)
            new_content = re.sub(pattern, f'\\1"{new_version}"', content, count=1, flags=re.MULTILINE)

            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            print(f"Updated {file_path}: {old_version} -> {new_version}")
            return True
        else:
            print(f"Could not find version string in {file_path}")
            return False

    except Exception as e:
        print(f"Failed to update {file_path}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Bump version number across all project files.')
    parser.add_argument('version', nargs='?', help='New version number (e.g. 0.1.1)')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation')

    args = parser.parse_args()

    current_versions = get_current_versions()
    print("Current versions:")
    for component, ver in current_versions.items():
        print(f"  {component}: {ver}")

    new_version = args.version

    # Interactive mode if no version argument provided
    if not new_version:
        print("\nEnter new version number (or press Ctrl+C to cancel):")
        try:
            new_version = input("> ").strip()
        except KeyboardInterrupt:
            print("\nCancelled.")
            sys.exit(0)

    if not new_version:
        print("Error: No version specified.")
        sys.exit(1)

    # Validation (simple check)
    if not re.match(r'^\d+\.\d+\.\d+(?:-[a-zA-Z0-9\.]+)?$', new_version):
        print(f"Warning: '{new_version}' might not be a valid semantic version.")
        if not args.yes:
            response = input("Continue anyway? (y/n): ").lower()
            if response != 'y':
                print("Aborted.")
                sys.exit(0)

    # Confirmation
    if not args.yes:
        print(f"\nThis will update all components to version: {new_version}")
        response = input("Are you sure? (y/n): ").lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)

    print("\nUpdating files...")
    success = True

    # Update files
    if not update_json_version('electron/package.json', new_version):
        success = False
    if not update_json_version('frontend/package.json', new_version):
        success = False
    if not update_toml_version('pyproject.toml', new_version):
        success = False

    if success:
        print(f"\nSuccessfully updated version to {new_version}")
    else:
        print("\nSome updates failed. Please check the output above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
