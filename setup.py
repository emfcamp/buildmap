from setuptools import setup
from codecs import open

with open("README.md") as f:
    long_description = f.read()

setup(
    name="buildmap",
    version="2.0",
    description="A GIS workflow pipeline for designing festivals",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="GPL",
    author="Russ Garrett",
    author_email="russ@garrett.co.uk",
    url="https://github.com/emfcamp/buildmap",
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    keywords="gis postgis",
    python_requires=">=3.5",
    packages=["buildmap", "buildmap.exporter", "buildmap.plugins"],
    install_requires=[
        "gunicorn",
        "sqlalchemy",
        "shapely",
        "pyyaml",
        "argparse",
        "psycopg2",
        "toml",
        "pydotplus",
        "pint"
    ],
    entry_points={"console_scripts": {"buildmap=buildmap.main:run"}},
)
