"""Setup script for GalacticCIC."""

from setuptools import setup, find_packages

setup(
    name="galactic-cic",
    version="1.0.0",
    description="Combat Information Center TUI for OpenClaw operations monitoring",
    author="SpaceTrucker2196",
    license="MIT",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
    install_requires=[
        "textual>=0.47.0",
        "rich>=13.0.0",
    ],
    extras_require={
        "dev": [
            "behave",
            "flake8",
        ],
    },
    entry_points={
        "console_scripts": [
            "galactic_cic=galactic_cic.app:main",
            "galactic-cic=galactic_cic.app:main",
        ],
    },
)
