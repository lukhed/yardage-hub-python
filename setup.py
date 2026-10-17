from setuptools import setup, find_packages

setup(
    name="yardage_hub",
    version="0.1.0",
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
