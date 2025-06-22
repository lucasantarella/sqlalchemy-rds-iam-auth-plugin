#!/usr/bin/env python3
"""
Local publishing script for sqlalchemy-rds-iam package.

This script helps with local development and testing of the package publishing process.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd, check=True):
    """Run a shell command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=check)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result


def clean_dist():
    """Clean the dist directory."""
    print("Cleaning dist directory...")
    dist_dir = Path("dist")
    if dist_dir.exists():
        for file in dist_dir.glob("*"):
            file.unlink()
        dist_dir.rmdir()


def build_package():
    """Build the package."""
    print("Building package...")
    run_command([sys.executable, "-m", "build"])


def check_package():
    """Check the built package."""
    print("Checking package...")
    run_command(["twine", "check", "dist/*"])


def publish_test():
    """Publish to Test PyPI."""
    print("Publishing to Test PyPI...")
    run_command(["twine", "upload", "--repository", "testpypi", "dist/*"])


def publish_pypi():
    """Publish to PyPI."""
    print("Publishing to PyPI...")
    response = input("Are you sure you want to publish to PyPI? (yes/no): ")
    if response.lower() != "yes":
        print("Cancelled.")
        return

    run_command(["twine", "upload", "dist/*"])


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Package publishing helper")
    parser.add_argument(
        "action",
        choices=["clean", "build", "check", "test", "publish", "all"],
        help="Action to perform",
    )

    args = parser.parse_args()

    try:
        if args.action == "clean":
            clean_dist()
        elif args.action == "build":
            build_package()
        elif args.action == "check":
            check_package()
        elif args.action == "test":
            publish_test()
        elif args.action == "publish":
            publish_pypi()
        elif args.action == "all":
            clean_dist()
            build_package()
            check_package()
            print("\nPackage built and checked successfully!")
            print("Run 'python scripts/publish.py test' to publish to Test PyPI")
            print("Run 'python scripts/publish.py publish' to publish to PyPI")

        print("✓ Action completed successfully!")

    except subprocess.CalledProcessError as e:
        print(f"✗ Command failed with exit code {e.returncode}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n✗ Cancelled by user")
        sys.exit(1)


if __name__ == "__main__":
    main()
