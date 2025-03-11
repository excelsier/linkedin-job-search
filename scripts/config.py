"""
Configuration file for LinkedIn job scraping and analysis project.
Contains key parameters for the scraper, LLM analysis, and Google Sheets integration.
"""

import os
from pathlib import Path

# Project directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
RESULTS_DIR = os.path.join(BASE_DIR, "results")

# CV Configuration
CV_FILE_PATH = os.path.join(DATA_DIR, "cv.md")

# Apify Scraper Configuration
COUNTRIES = ["Poland", "Portugal", "Spain", "France", "Germany", "United Kingdom"]
JOB_ROLES = {
    "Product Leadership": ["Senior Product Manager", "Director of Product"],
    "Strategic Operations": ["Director of Operations", "Chief of Staff"]
}

# Job filtering settings
JOB_TYPES = ["full-time"]  # Options: "full-time", "part-time", "contract", "temporary", "volunteer", "internship"
EXPERIENCE_LEVELS = ["mid-senior", "director"]  # Options: "internship", "entry", "associate", "mid-senior", "director", "executive"
REMOTE_SETTINGS = ["on-site", "remote", "hybrid"]  # Options: "on-site", "remote", "hybrid"
RECENT_JOBS_ONLY = True  # Only include jobs posted recently

MAX_JOBS_PER_SEARCH = 30
TOTAL_TARGET_JOBS = 200

# LLM Analysis Configuration
# Available models:
# - "claude-3-opus-20240229" - Claude 3 Opus (Anthropic)
# - "anthropic/claude-3-sonnet:20240229" - Sonnet 3.7 (via OpenRouter)
LLM_MODEL = "claude-3-opus-20240229"
LLM_PROVIDER = "anthropic"  # Options: "anthropic", "openrouter"
MAX_JOBS_TO_ANALYZE = 50  # Limit to avoid excessive API costs
MATCH_SCORE_THRESHOLD = 7.0  # Minimum score (out of 10) for jobs to be considered good matches

# Google Sheets Configuration
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "1W0M7ckok7FjLnCkdWD9jbrehdIR-adCupPS8ZX3XkSI")  # Use the ID from .env or the most recent one
GOOGLE_SHEET_RANGE = "Job Matches!A2:G"
GOOGLE_CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials", "google_credentials.json")

# Automation Configuration
RUN_SCHEDULE = "0 8 * * *"  # Run daily at 8 AM (cron format)

# LinkedIn search settings
# LinkedIn time filter options:
# - Past 24 hours: r86400
# - Past Week: r604800
# - Past Month: r2592000
# - Any Time: ""
TIME_FILTER = "r2592000"  # Last 30 days
