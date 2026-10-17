import re

from setuptools import setup, find_packages

# The version lives in src/yardage_hub/__init__.py; bump it there
with open("src/yardage_hub/__init__.py", encoding="utf-8") as f:
    version = re.search(r'^__version__ = "([^"]+)"', f.read(), re.M).group(1)

setup(
    name="yardage_hub",
    version=version,
    description="Python client for the yardage-hub golf course API",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="lukhed",
    author_email="lukhed.mail@gmail.com",
    url="https://github.com/lukhed/yardage-hub-python",
    project_urls={
        "Homepage": "https://lukeheide.com/sports/yardage-hub",
        "Documentation": "https://lukeheide.com/sports/yardage-hub/docs",
    },
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.9",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[],
)
