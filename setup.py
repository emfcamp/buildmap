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
        "jinja2",
        "gunicorn",
        "sqlalchemy <2.0",
        "shapely",
        "pyyaml",
        "argparse",
        "psycopg2",
        "toml",
        "pydotplus",
        "mergedeep==1.3.4",
        "pint==0.18",
        "reportlab",
        "pylabels",
        "requests==2.32.0",
    ],
    entry_points={"console_scripts": {"buildmap=buildmap.main:run"}},
)
