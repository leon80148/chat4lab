"""
診所AI查詢系統安裝配置
"""

from setuptools import setup, find_packages
import os

# 讀取README檔案作為長描述
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

# 讀取requirements.txt
def read_requirements():
    requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    if os.path.exists(requirements_path):
        with open(requirements_path, 'r', encoding='utf-8') as f:
            requirements = []
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    requirements.append(line)
            return requirements
    return []

setup(
    name="clinic-ai-query",
    version="1.0.0",
    author="Leon Lu",
    author_email="leon80148@gmail.com",
    description="診所AI查詢系統 - 基於本地LLM的診所資料庫智能查詢系統",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/leon80148/chat4lab",
    project_urls={
        "Bug Tracker": "https://github.com/leon80148/chat4lab/issues",
        "Documentation": "https://github.com/leon80148/chat4lab/blob/main/docs/",
        "Source Code": "https://github.com/leon80148/chat4lab",
    },
    packages=find_packages(include=['src', 'src.*']),
    package_dir={'': '.'},
    include_package_data=True,
    package_data={
        'config': ['*.yaml', 'prompts/*.txt', 'prompts/*.yaml'],
        'scripts': ['*.py', '*.sh'],
        'data': ['sample/*'],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Healthcare Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: Database",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
    ],
    python_requires=">=3.9",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
            "isort>=5.12.0",
            "pre-commit>=3.0.0",
            "bandit>=1.7.5",
            "safety>=2.3.0",
        ],
        "docker": [
            "docker-compose>=1.29.0",
        ],
        "docs": [
            "mkdocs>=1.4.0",
            "mkdocs-material>=8.0.0",
            "mkdocs-mermaid2-plugin>=0.6.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "clinic-ai=src.app:main",
            "clinic-ai-setup=scripts.setup_db:main",
            "clinic-ai-health=scripts.health_check:main",
        ],
    },
    keywords=[
        "clinic", "medical", "AI", "LLM", "database", "query", 
        "healthcare", "streamlit", "ollama", "gemma", "dbf"
    ],
    license="MIT",
    zip_safe=False,
)