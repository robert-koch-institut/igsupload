from setuptools import setup, find_packages

setup(
    name="igsupload",
    version="1.0.0",
    description="Automated upload of sequencing data (FASTQ/FASTQ.GZIP) to the DEMIS portal (RKI) for the IGS.",
    python_requires=">=3.13",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True, 
    install_requires=[
        "typer>=0.16",
        "requests>=2.32.4",
        "python-dotenv>=1.1.1",
    ],
    extras_require={
        "dev": [
            "pytest>=8",
            "pytest-cov>=5",
            "pytest-mock>=3.14.1"
        ],
    },
    entry_points={
        "console_scripts": [
            "igsupload = igsupload.main:app",
        ],
    },
)
