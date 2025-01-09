#!/bin/bash

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status messages
print_status() {
    echo -e "${GREEN}[+]${NC} $1"
}

# Function to print error messages
print_error() {
    echo -e "${RED}[!]${NC} $1"
}

# Function to print warning messages
print_warning() {
    echo -e "${YELLOW}[*]${NC} $1"
}

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    print_error "Poetry is not installed. Please install Poetry first."
    exit 1
fi

# Create project structure
print_status "Creating project directory structure..."

# Create main directories
directories=(
    "app"
    "app/utils"
    "app/core"
    "app/services"
    "data"
    "data/resumes"
    "tests"
    "tests/unit"
    "tests/integration"
    "docs"
)

for dir in "${directories[@]}"; do
    mkdir -p "$dir"
    print_status "Created directory: $dir"
done

# Create necessary files
print_status "Creating project files..."

# Create .env file
cat > .env << EOL
# AutoApply Environment Configuration
HUGGINGFACE_API_TOKEN=your_token_here
# Add other environment variables as needed
EOL

# Create .gitignore
cat > .gitignore << EOL
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
.env
.venv
env/
venv/
ENV/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Project specific
data/user_profile.json
data/resumes/*
!data/resumes/.gitkeep

# Logs
*.log
logs/
EOL

# Create empty __init__.py files
touch app/__init__.py
touch app/utils/__init__.py
touch app/core/__init__.py
touch app/services/__init__.py
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/integration/__init__.py

# Create .gitkeep files for empty directories
touch data/resumes/.gitkeep

# Initialize pyproject.toml with Poetry
print_status "Initializing Poetry project..."

# Create pyproject.toml
cat > pyproject.toml << EOL
[tool.poetry]
name = "autoapply"
version = "0.1.0"
description = "An innovative solution for automating job applications using LinkedIn profile data"
authors = ["Your Name <your.email@example.com>"]
readme = "README.md"
packages = [{include = "app"}]

[tool.poetry.dependencies]
python = "^3.13.1"
playwright = "^1.41.1"
python-dotenv = "^1.0.0"
transformers = "^4.36.2"
pdfplumber = "^0.10.3"
jsonschema = "^4.21.1"
typer = "^0.9.0"
rich = "^13.7.0"
pydantic = "^2.5.3"
python-logstash = "^0.4.8"
structlog = "^24.1.0"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.4"
pytest-cov = "^4.1.0"
black = "^23.12.1"
isort = "^5.13.2"
mypy = "^1.8.0"
pylint = "^3.0.3"
pre-commit = "^3.6.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.poetry.scripts]
autoapply = "app.main:app"
EOL

# Initialize pre-commit configuration
cat > .pre-commit-config.yaml << EOL
repos:
-   repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
    -   id: trailing-whitespace
    -   id: end-of-file-fixer
    -   id: check-yaml
    -   id: check-added-large-files

-   repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
    -   id: black

-   repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
    -   id: isort

-   repo: https://github.com/pycqa/pylint
    rev: v3.0.3
    hooks:
    -   id: pylint
        args: [--rcfile=.pylintrc]
EOL

# Create pylint configuration
cat > .pylintrc << EOL
[MASTER]
disable=
    C0111, # missing-docstring
    C0103, # invalid-name
    C0301, # line-too-long
    W0621, # redefined-outer-name
    R0903, # too-few-public-methods
    R0913, # too-many-arguments
    R0914, # too-many-locals

[FORMAT]
max-line-length=120

[MESSAGES CONTROL]
disable=C0111,R0903
EOL

# Install dependencies using Poetry
print_status "Installing project dependencies..."
poetry install

# Initialize Git repository
print_status "Initializing Git repository..."
git init
git add .
git commit -m "Initial commit: Project structure setup"

# Install pre-commit hooks
print_status "Installing pre-commit hooks..."
poetry run pre-commit install

# Install Playwright browsers
print_status "Installing Playwright browsers..."
poetry run playwright install

print_status "Project initialization completed successfully!"
print_warning "Don't forget to update your .env file with your actual Hugging Face API token!"
print_status "You can now start developing your AutoApply project."
EOL

chmod +x init_autoapply.sh