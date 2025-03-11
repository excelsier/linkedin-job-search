#!/usr/bin/env python
"""
Setup script for LinkedIn Job Search and Analysis project.
This script verifies the environment setup and dependencies.
"""
import os
import sys
import logging
import importlib
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("setup")

# Project directories
PROJECT_ROOT = Path(__file__).parent.absolute()
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
RESULTS_DIR = PROJECT_ROOT / "results"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# Required files
CV_FILE = DATA_DIR / "cv.md"
ENV_FILE = PROJECT_ROOT / ".env"
CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"

# Required environment variables
REQUIRED_ENV_VARS = ["APIFY_API_KEY", "ANTHROPIC_API_KEY"]

# Required Python packages
REQUIRED_PACKAGES = [
    "requests", "anthropic", "google-api-python-client", 
    "google-auth-httplib2", "google-auth-oauthlib",
    "pandas", "beautifulsoup4", "markdownify", "html2text",
    "aiohttp", "asyncio", "apscheduler", "python-dotenv", "tqdm", "pyyaml"
]


def check_python_version():
    """Check if Python version is 3.8 or higher."""
    logger.info(f"Python version: {sys.version}")
    if sys.version_info < (3, 8):
        logger.error("Python 3.8 or higher is required")
        return False
    return True


def check_directories():
    """Ensure all required directories exist."""
    dirs = [DATA_DIR, LOGS_DIR, RESULTS_DIR]
    for directory in dirs:
        if not directory.exists():
            logger.warning(f"Creating directory: {directory}")
            directory.mkdir(parents=True, exist_ok=True)
        else:
            logger.info(f"Directory exists: {directory}")
    return True


def check_required_files():
    """Check if required files exist."""
    missing_files = []
    
    # Check CV file
    if not CV_FILE.exists():
        if (DATA_DIR / "cv_template.md").exists():
            logger.warning(f"CV file not found. Please copy and customize the template:")
            logger.warning(f"cp {DATA_DIR / 'cv_template.md'} {CV_FILE}")
        else:
            logger.error(f"CV template not found at {DATA_DIR / 'cv_template.md'}")
        missing_files.append("CV file")
    
    # Check .env file
    if not ENV_FILE.exists():
        if (PROJECT_ROOT / ".env.template").exists():
            logger.warning(f"Environment file not found. Please copy and customize the template:")
            logger.warning(f"cp {PROJECT_ROOT / '.env.template'} {ENV_FILE}")
        else:
            logger.error(f".env template not found")
        missing_files.append(".env file")
    
    # Check Google credentials
    if not CREDENTIALS_FILE.exists():
        if (PROJECT_ROOT / "credentials_template.json").exists():
            logger.warning(f"Google credentials not found. Please create credentials.json from the template.")
        else:
            logger.error(f"credentials template not found")
        missing_files.append("Google credentials")
    
    if missing_files:
        logger.warning(f"Missing required files: {', '.join(missing_files)}")
        return False
    
    logger.info("All required files present")
    return True


def check_env_variables():
    """Check if required environment variables are set."""
    # Try to load from .env if it exists
    try:
        if ENV_FILE.exists():
            import dotenv
            dotenv.load_dotenv(ENV_FILE)
            logger.info("Loaded environment variables from .env file")
    except ImportError:
        logger.warning("python-dotenv not installed, skipping .env file loading")
    
    missing_vars = []
    for var in REQUIRED_ENV_VARS:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.warning(f"Missing environment variables: {', '.join(missing_vars)}")
        logger.warning("Please set these variables in your environment or in the .env file")
        return False
    
    logger.info("All required environment variables are set")
    return True


def check_package_dependencies():
    """Check if required packages are installed."""
    missing_packages = []
    for package in REQUIRED_PACKAGES:
        base_package = package.split("[")[0]  # Handle packages with extras
        try:
            # Try multiple methods to check if package is installed
            try:
                importlib.import_module(base_package)
            except ImportError:
                # Some packages use different import names
                if base_package == 'beautifulsoup4':
                    importlib.import_module('bs4')
                elif base_package == 'google-api-python-client':
                    importlib.import_module('googleapiclient')
                elif base_package == 'google-auth-httplib2':
                    # This package doesn't have a direct module import
                    subprocess.check_call([sys.executable, '-m', 'pip', 'show', base_package], 
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                elif base_package == 'google-auth-oauthlib':
                    importlib.import_module('google_auth_oauthlib')
                else:
                    raise ImportError(f"Could not import {base_package}")
        except (ImportError, subprocess.CalledProcessError):
            missing_packages.append(package)
    
    if missing_packages:
        logger.warning(f"Missing required packages: {', '.join(missing_packages)}")
        logger.warning("Please install them using: pip install -r requirements.txt")
        return False
    
    logger.info("All required packages are installed")
    return True


def verify_api_access():
    """Verify API access where possible without making actual API calls."""
    # This is a lightweight check without making actual API calls
    
    # Check Apify API key format
    apify_key = os.environ.get("APIFY_API_KEY", "")
    if not apify_key.startswith("apify_api_"):
        logger.warning("APIFY_API_KEY appears to be in incorrect format")
    else:
        logger.info("APIFY_API_KEY format looks correct")
    
    # Check Anthropic API key format
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not anthropic_key.startswith("sk-ant-"):
        logger.warning("ANTHROPIC_API_KEY appears to be in incorrect format")
    else:
        logger.info("ANTHROPIC_API_KEY format looks correct")
    
    # Check Google credentials without actually authenticating
    if CREDENTIALS_FILE.exists():
        import json
        try:
            with open(CREDENTIALS_FILE) as f:
                creds = json.load(f)
            if "client_email" in creds and "private_key" in creds:
                logger.info("Google credentials file appears valid")
            else:
                logger.warning("Google credentials file may be incomplete")
        except json.JSONDecodeError:
            logger.error("Google credentials file is not valid JSON")
    
    return True


def main():
    """Run all checks and verify environment setup."""
    logger.info("Starting LinkedIn Job Search environment verification")
    
    checks = [
        ("Python version", check_python_version),
        ("Project directories", check_directories),
        ("Required files", check_required_files),
        ("Environment variables", check_env_variables),
        ("Package dependencies", check_package_dependencies),
        ("API access verification", verify_api_access)
    ]
    
    all_passed = True
    for name, check_func in checks:
        logger.info(f"Checking {name}...")
        try:
            if not check_func():
                all_passed = False
                logger.warning(f"Check failed: {name}")
            else:
                logger.info(f"Check passed: {name}")
        except Exception as e:
            all_passed = False
            logger.error(f"Error during {name} check: {str(e)}")
    
    if all_passed:
        logger.info("✅ All checks passed! Environment is ready for LinkedIn Job Search")
    else:
        logger.warning("⚠️ Some checks failed. Please address the issues above before proceeding.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
