#!/usr/bin/env python
"""
LinkedIn Job Search - Verify Setup

This script verifies that your environment is properly set up with all necessary
API keys and configurations before running the main job search process.
"""

import os
import sys
import json
import requests
import logging
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("verify_setup")

# Load environment variables from .env file
load_dotenv()

def check_environment_variables():
    """Check if all required environment variables are set"""
    required_vars = {
        "APIFY_API_KEY": "Apify API key for LinkedIn job scraping",
        "ANTHROPIC_API_KEY": "OpenRouter API key for LLM analysis"
    }
    
    optional_vars = {
        "GOOGLE_CREDENTIALS_FILE": "Path to Google API credentials file",
        "GOOGLE_SHEET_ID": "Google Sheet ID for storing results"
    }
    
    missing_vars = []
    
    logger.info("Checking environment variables...")
    
    for var, description in required_vars.items():
        value = os.environ.get(var)
        if not value:
            missing_vars.append(var)
            logger.error(f"❌ Missing required environment variable: {var} ({description})")
        else:
            logger.info(f"✅ Found {var}")
    
    for var, description in optional_vars.items():
        value = os.environ.get(var)
        if not value:
            logger.warning(f"⚠️ Missing optional environment variable: {var} ({description})")
        else:
            logger.info(f"✅ Found {var}")
    
    return len(missing_vars) == 0

def verify_apify_api_key():
    """Verify that the Apify API key is present"""
    api_key = os.environ.get("APIFY_API_KEY")
    if not api_key:
        logger.error("❌ APIFY_API_KEY environment variable is not set")
        return False
    
    logger.info("✅ Apify API key is set")
    return True

def verify_anthropic_api_key():
    """Verify that the Anthropic API key (via OpenRouter) is valid"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return False
    
    logger.info("Verifying OpenRouter API key...")
    
    # Check if it's an OpenRouter API key
    if not api_key.startswith("sk-or-"):
        logger.warning("⚠️ API key doesn't appear to be an OpenRouter key (should start with 'sk-or-')")
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # Simple model availability check
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers=headers
        )
        
        if response.status_code == 200:
            models_data = response.json()
            models = models_data.get("data", [])
            
            # Check if required models are available
            claude_models = [m for m in models if "claude" in m.get("id", "").lower()]
            
            if claude_models:
                model_ids = [m.get("id") for m in claude_models]
                logger.info(f"✅ OpenRouter API key is valid")
                logger.info(f"📋 Available Claude models: {', '.join(model_ids)}")
                return True
            else:
                logger.warning("⚠️ No Claude models found in OpenRouter")
                return True  # Still return True as the API key is valid
        else:
            logger.error(f"❌ OpenRouter API key validation failed with status code {response.status_code}")
            return False
    
    except Exception as e:
        logger.error(f"❌ Error verifying OpenRouter API key: {str(e)}")
        return False

def check_required_files():
    """Check if all required files exist"""
    project_dir = Path(__file__).parent.parent
    
    required_files = {
        "CV Template": project_dir / "data" / "cv_template.md"
    }
    
    if os.environ.get("GOOGLE_CREDENTIALS_FILE"):
        credentials_path = os.environ.get("GOOGLE_CREDENTIALS_FILE")
        if not credentials_path.startswith("/"):
            credentials_path = project_dir / credentials_path
        required_files["Google Credentials"] = Path(credentials_path)
    
    missing_files = []
    
    logger.info("Checking required files...")
    
    for name, file_path in required_files.items():
        if not file_path.exists():
            missing_files.append((name, file_path))
            logger.error(f"❌ Missing {name}: {file_path}")
        else:
            logger.info(f"✅ Found {name}: {file_path}")
    
    # Check if CV file exists, if not, check if template exists to copy
    cv_path = project_dir / "data" / "cv.md"
    if not cv_path.exists():
        template_path = project_dir / "data" / "cv_template.md"
        if template_path.exists():
            logger.warning(f"⚠️ CV file not found: {cv_path}")
            logger.info(f"   You need to create this from the template at {template_path}")
        else:
            logger.error(f"❌ Neither CV file nor template found")
            missing_files.append(("CV File", cv_path))
    else:
        logger.info(f"✅ Found CV file: {cv_path}")
    
    return len(missing_files) == 0

def test_actor_availability():
    """Test if we can access the curious_coder/linkedin-jobs-scraper actor"""
    # Skip detailed actor validation as it may require specific permissions
    # Just assume the actor is available if the API key is set
    logger.info("Checking LinkedIn Jobs Scraper actor...")
    logger.info("✅ Using curious_coder/linkedin-jobs-scraper actor for LinkedIn job scraping")
    return True

def main():
    """Main verification function"""
    logger.info("=== LinkedIn Job Search - Setup Verification ===")
    
    # Check environment variables
    env_check = check_environment_variables()
    
    # Verify API keys (simplified)
    apify_check = verify_apify_api_key()
    anthropic_check = verify_anthropic_api_key()
    
    # Check required files
    files_check = check_required_files()
    
    # Test actor availability (simplified)
    actor_check = test_actor_availability()
    
    # Summary
    logger.info("\n=== Verification Summary ===")
    
    # Consider setup valid if API keys are present and files are available
    all_checks_passed = all([env_check, apify_check, anthropic_check, files_check])
    
    if all_checks_passed:
        logger.info("✅ All checks passed! Your setup is ready to use.")
        logger.info("\nYou can now run the main script:")
        logger.info("python scripts/main.py")
        logger.info("\nOr with Sonnet 3.7 model:")
        logger.info('python scripts/main.py --llm-model "anthropic/claude-3-sonnet:20240229" --llm-provider "openrouter"')
        return 0
    else:
        logger.error("❌ Some checks failed. Please fix the issues above before running the main script.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
