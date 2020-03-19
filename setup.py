#!/usr/bin/env python
# coding: UTF-8

import os

from setuptools import find_packages, setup

here = os.path.abspath(os.path.dirname(__file__))

with open("README.md", "r", encoding="utf-8") as f:
    readme = f.read()

about = {}
with open(
    os.path.join(here, "annofabcli", "__version__.py"), "r", encoding="utf-8"
) as f:
    exec(f.read(), about)

setup(
    name="annofabcli",
    version=about["__version__"],
    description="Utility Command Line Interface for AnnoFab",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="yuji38kwmt",
    author_email="yuji38kwmt@gmail.com",
    maintainer="yuji38kwmt",
    license="MIT",
    keywords="annofab api cli",
    url="https://github.com/kurusugawa-computer/annofab-cli",
    install_requires=[
        "annofabapi>=0.29.5",
        "requests",
        "pillow",
        "pyyaml",
        "dictdiffer",
        "more-itertools",
        "jmespath",
        "pyquery",
        "pandas>=1.0.3",
        "isodate",
        "bokeh>=1.4,<2.0", # holoviewsが2.0.0に対応されるまでバージョンを固定化する
        "holoviews>=1.12.7",
    ],
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Utilities",
        "Operating System :: OS Independent",
    ],
    packages=find_packages(exclude=["tests"]),
    package_data={"annofabcli": ["data/logging.yaml", "py.typed"]},
    entry_points={"console_scripts": ["annofabcli=annofabcli.__main__:main"],},
)
