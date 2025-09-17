#!/usr/bin/env python3
"""
Setup script for imgc - Intelligent Image Compression Watcher

This file enables installation via pip and provides package metadata.
"""

from pathlib import Path
from setuptools import setup, find_packages

# Read the README file for long description
README_PATH = Path(__file__).parent / "README.md"
long_description = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else ""

# Read requirements
REQUIREMENTS_PATH = Path(__file__).parent / "requirements.txt"
requirements = []
if REQUIREMENTS_PATH.exists():
    requirements = [
        line.strip() 
        for line in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="imgc",
    version="0.1.0",
    author="imgc contributors",
    author_email="",
    description="Intelligent Image Compression Watcher - Automatically compress images when they're created",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cvele/imgc",
    project_urls={
        "Bug Reports": "https://github.com/cvele/imgc/issues",
        "Source": "https://github.com/cvele/imgc",
        "Documentation": "https://github.com/cvele/imgc#readme",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Graphics",
        "Topic :: System :: Filesystems",
        "Topic :: System :: Monitoring",
        "Topic :: Utilities",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0",
            "black",
            "coverage",
            "pyinstaller",
        ],
    },
    entry_points={
        "console_scripts": [
            "imgc=main:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords="image compression watcher filesystem monitoring jpeg png webp avif optimization",
)
