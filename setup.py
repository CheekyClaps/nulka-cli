from setuptools import find_packages, setup

# Read the contents of the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="nulka-cli",
    version="1.0.0",
    description="Enterprise Multi-Agent Simulated Workspace with local LLMs and a Self-Learning Feedback Loop.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="NulkaCLI Team",
    url="https://github.com/cheekyclaps/nulka-cli",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "nulka_cli": ["config/*.yaml", "config/agents/*.md"],
    },
    install_requires=[
        "crewai==0.11.2",
        "langchain==0.1.20",
        "langchain-community==0.0.38",
        "docstring-parser>=0.16",
        "pydantic>=2.0",
        "rich>=13.0",
        "textual>=0.80.0",
        "prompt_toolkit>=3.0",
        "pyyaml",
        "python-dotenv",
        "requests",
        "ddgs",
        "beautifulsoup4"
    ],
    entry_points={
        "console_scripts": [
            "nulka=nulka_cli.main:main",
            "nulka-cli=nulka_cli.main:main",
            "nulka_cli=nulka_cli.main:main",
        ],
    },
    python_requires=">=3.10",
    keywords="ai, agents, crewai, ollama, llm, gemini, cli, multi-agent, autonomous, self-learning, developer tools, oracle",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
