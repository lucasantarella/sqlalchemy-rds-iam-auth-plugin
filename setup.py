from setuptools import find_packages, setup

setup(
    name="sqlalchemy-rds-iam",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    entry_points={
        "sqlalchemy.plugins": ["rds_iam = sqlalchemy_rds_iam.plugin:RDSIAMAuthPlugin"]
    },
    # ... other setup parameters
)
