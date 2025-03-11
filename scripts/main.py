#!/usr/bin/env python
"""
LinkedIn Job Search and Analysis - Main Script

This script orchestrates the entire LinkedIn job search and analysis process:
1. Fetching job listings from LinkedIn using Apify
2. Analyzing job listings against the candidate's CV using Claude
3. Saving analysis results to Google Sheets
4. Scheduling regular execution

To run manually: python scripts/main.py
For scheduled execution: Use cron or Task Scheduler
"""

import os
import sys
import json
import asyncio
import logging
import argparse
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import from other modules
from config import (
    COUNTRIES, JOB_ROLES, JOB_TYPES, EXPERIENCE_LEVELS, REMOTE_SETTINGS, RECENT_JOBS_ONLY,
    MAX_JOBS_PER_SEARCH, CV_FILE_PATH, TIME_FILTER, MATCH_SCORE_THRESHOLD,
    LOGS_DIR, DATA_DIR, RESULTS_DIR, MAX_JOBS_TO_ANALYZE, LLM_MODEL, LLM_PROVIDER
)
from apify_scraper import create_search_configs, run_apify_linkedin_scraper
from cv_parser import parse_markdown_cv, format_cv_for_prompt
from llm_analyzer import analyze_jobs_batch, extract_best_matches, run_analysis
from sheets_integration import save_analyzed_jobs_to_sheet, create_sheet_if_not_exists
from job_database import (
    initialize_database, add_jobs_to_database, filter_new_jobs,
    mark_jobs_as_processed, record_scraping_run, get_recent_job_stats
)

# Create necessary directories
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "main.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("main")

# Initialize job database
initialize_database()


def load_config_profile(profile_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Load a configuration profile from the profiles directory.
    
    Args:
        profile_name: Name of the profile to load (without .yaml extension)
        
    Returns:
        Dictionary with configuration parameters
    """
    if not profile_name:
        return {}
        
    profile_path = Path(DATA_DIR) / "profiles" / f"{profile_name}.yaml"
    
    if not profile_path.exists():
        logger.warning(f"Profile '{profile_name}' not found at {profile_path}")
        return {}
        
    try:
        with open(profile_path, 'r', encoding='utf-8') as f:
            profile_data = yaml.safe_load(f)
            logger.info(f"Loaded configuration profile: {profile_name}")
            return profile_data or {}
    except Exception as e:
        logger.error(f"Error loading profile '{profile_name}': {str(e)}")
        return {}


def save_config_profile(profile_name: str, config_data: Dict[str, Any]) -> bool:
    """
    Save a configuration profile to the profiles directory.
    
    Args:
        profile_name: Name of the profile (without .yaml extension)
        config_data: Configuration data to save
        
    Returns:
        True if the profile was saved successfully, False otherwise
    """
    profile_dir = Path(DATA_DIR) / "profiles"
    profile_dir.mkdir(exist_ok=True, parents=True)
    
    profile_path = profile_dir / f"{profile_name}.yaml"
    
    try:
        with open(profile_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Saved configuration profile: {profile_name}")
            return True
    except Exception as e:
        logger.error(f"Error saving profile '{profile_name}': {str(e)}")
        return False


async def main(skip_scraping=False, skip_sheets=False, config_overrides=None, profile_name=None):
    """
    Main function to run the entire LinkedIn job search and analysis process.
    
    Args:
        skip_scraping: If True, use the most recent scraped data instead of fetching new data
    """
    logger.info("Starting LinkedIn job search and analysis process")
    start_time = datetime.now()
    
    # Load configuration profile if specified
    profile_config = {}
    if profile_name:
        profile_config = load_config_profile(profile_name)
        
    # Apply configuration overrides from profile and command-line arguments
    config = {
        "countries": COUNTRIES,
        "job_roles": JOB_ROLES,
        "job_types": JOB_TYPES,
        "experience_levels": EXPERIENCE_LEVELS,
        "remote_settings": REMOTE_SETTINGS,
        "recent_jobs_only": RECENT_JOBS_ONLY,
        "max_jobs_per_search": MAX_JOBS_PER_SEARCH,
        "max_jobs_to_analyze": MAX_JOBS_TO_ANALYZE,
        "cv_file_path": CV_FILE_PATH,
        "time_filter": TIME_FILTER,
        "match_score_threshold": MATCH_SCORE_THRESHOLD
    }
    
    # Apply profile configuration
    if profile_config:
        config.update(profile_config)
    
    # Apply command-line overrides
    if config_overrides:
        config.update(config_overrides)
        
    logger.info(f"Using configuration with {len(config['countries'])} countries and {sum(len(roles) for roles in config['job_roles'].values())} job roles")
    
    # Step 1: Ensure Google Sheet exists (if not skipped)
    if not skip_sheets:
        logger.info("Step 1: Ensuring Google Sheet exists")
        sheet_exists = create_sheet_if_not_exists()
        if not sheet_exists:
            logger.error("Failed to create or verify Google Sheet. Check credentials.")
            logger.info("Continuing without Google Sheets integration...")
            skip_sheets = True
    else:
        logger.info("Skipping Google Sheets integration as requested")
    
    # Step 2: Scrape jobs from LinkedIn using Apify
    if not skip_scraping:
        logger.info("Step 2: Scraping jobs from LinkedIn using Apify")
        try:
            # Get API key from environment
            api_key = os.environ.get("APIFY_API_KEY")
            if not api_key:
                logger.error("APIFY_API_KEY not found in environment variables")
                return
            
            # Create search configurations
            search_configs = create_search_configs(
                countries=config["countries"],
                job_roles=config["job_roles"],
                jobs_per_search=config["max_jobs_per_search"],
                job_types=config["job_types"],
                experience_levels=config["experience_levels"],
                remote_settings=config["remote_settings"],
                recent_jobs_only=config["recent_jobs_only"],
                time_filter=config["time_filter"]
            )
            
            # Run Apify scraper
            scrape_result = await run_apify_linkedin_scraper(api_key, search_configs)
            
            if 'error' in scrape_result:
                logger.error(f"Apify scraping failed: {scrape_result['error']}")
                return
            
            all_jobs = scrape_result['jobs']
            logger.info(f"Successfully scraped {len(all_jobs)} jobs from LinkedIn")
            
            # Filter out jobs that we've already processed to save API costs
            new_jobs = filter_new_jobs(all_jobs)
            logger.info(f"Found {len(new_jobs)} new jobs that haven't been processed before")
            
            # Add all jobs to database (new ones will be added, existing ones updated)
            db_result = add_jobs_to_database(all_jobs)
            logger.info(f"Added {db_result['new']} new jobs to database, updated {db_result['updated']} existing jobs")
            
            # Record this scraping run in the database
            run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            record_scraping_run(run_id, search_configs[0], len(all_jobs), db_result['new'])
            
            # Save all scraped jobs to file (including duplicates for record keeping)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            jobs_file_path = os.path.join(DATA_DIR, f"jobs_{timestamp}.json")
            
            with open(jobs_file_path, 'w', encoding='utf-8') as f:
                json.dump({'timestamp': timestamp, 'jobs': all_jobs}, f, indent=2, ensure_ascii=False)
                
            # Use only new jobs for analysis to save on API costs
            if new_jobs:
                jobs_data = new_jobs
                logger.info(f"Will analyze {len(jobs_data)} new jobs to save API costs")
            else:
                # If no new jobs, use a subset of all jobs (based on most recent)
                # This ensures we still run analysis even if we've seen all jobs before
                max_jobs = min(config["max_jobs_to_analyze"], len(all_jobs))
                jobs_data = all_jobs[:max_jobs]
                logger.info(f"No new jobs found, will analyze {len(jobs_data)} recent jobs")
                
            logger.info(f"Saved scraped jobs to: {jobs_file_path}")
            
        except Exception as e:
            logger.error(f"Error during job scraping: {str(e)}")
            return
    else:
        logger.info("Skipping job scraping, using most recent data")
        # Find the most recent jobs file
        data_dir = Path(DATA_DIR)
        job_files = list(data_dir.glob("jobs_*.json"))
        job_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not job_files:
            logger.error("No job files found. Run without --skip-scraping flag first.")
            return
            
        jobs_file_path = str(job_files[0])
        logger.info(f"Using most recent jobs file: {jobs_file_path}")
        
        # Load the jobs data
        with open(jobs_file_path, 'r', encoding='utf-8') as f:
            jobs_data = json.load(f).get('jobs', [])
            
        logger.info(f"Loaded {len(jobs_data)} jobs from file")
    
    # Step 3: Parse the CV
    logger.info("Step 3: Parsing the CV")
    try:
        cv_data = parse_markdown_cv(CV_FILE_PATH)
        cv_text = format_cv_for_prompt(cv_data)
        logger.info(f"Successfully parsed CV from {CV_FILE_PATH}")
    except Exception as e:
        logger.error(f"Error parsing CV: {str(e)}")
        return
    
    # Step 4: Analyze jobs against CV
    logger.info("Step 4: Analyzing jobs against CV")
    try:
        # Create output directory for analysis results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(RESULTS_DIR) / f"analysis_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Analyze jobs in batch
        # Limit the number of jobs to analyze if specified
        if config["max_jobs_to_analyze"] and len(jobs_data) > config["max_jobs_to_analyze"]:
            logger.info(f"Limiting analysis to {config['max_jobs_to_analyze']} jobs (out of {len(jobs_data)})")
            jobs_data = jobs_data[:config["max_jobs_to_analyze"]]
            
        analysis_results = await analyze_jobs_batch(jobs_data, config["cv_file_path"])
        
        # Extract best matches based on the configured threshold
        best_matches = extract_best_matches(analysis_results, threshold=config["match_score_threshold"])
        
        logger.info(f"Analysis complete. Found {len(best_matches)} matching jobs.")
        
        # Save to file
        summary_file = output_dir / "summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total_jobs': len(jobs_data),
                'analyzed_jobs': len(analysis_results),
                'matching_jobs': len(best_matches),
                'matching_job_ids': [job.get('job_id') for job in best_matches]
            }, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"Error during job analysis: {str(e)}")
        return
    
    # Step 5: Save results to Google Sheets (if not skipped)
    if not skip_sheets:
        logger.info("Step 5: Saving results to Google Sheets")
        try:
            saved = save_analyzed_jobs_to_sheet(best_matches, force_update=config_overrides.get('force_update', False))
            if saved:
                logger.info("Successfully saved job analysis results to Google Sheets")
            else:
                logger.error("Failed to save job analysis results to Google Sheets")
        except Exception as e:
            logger.error(f"Error saving to Google Sheets: {str(e)}")
    else:
        logger.info("Skipping saving to Google Sheets as requested")
    
    # Completion summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds() / 60  # in minutes
    logger.info(f"LinkedIn job search and analysis process completed in {duration:.2f} minutes")
    logger.info(f"Processed {len(jobs_data)} jobs, analyzed {len(analysis_results)}, found {len(best_matches)} matches")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkedIn Job Search and Analysis")
    
    # Core execution options
    parser.add_argument("--skip-scraping", action="store_true", help="Skip job scraping and use most recent data")
    parser.add_argument("--skip-sheets", action="store_true", help="Skip Google Sheets integration")
    parser.add_argument("--force-update", action="store_true", help="Force update existing entries in Google Sheets")
    parser.add_argument("--profile", type=str, help="Use a saved configuration profile")
    parser.add_argument("--save-profile", type=str, help="Save the current configuration as a profile")
    
    # Search configuration options
    parser.add_argument("--countries", type=str, nargs="*", help="Countries to search for jobs")
    parser.add_argument("--job-roles", type=str, nargs="*", help="Job roles to search for")
    parser.add_argument("--job-types", type=str, nargs="*", help="Job types (e.g., 'full-time', 'part-time')")
    parser.add_argument("--experience", type=str, nargs="*", help="Experience levels")
    parser.add_argument("--remote", type=str, nargs="*", help="Remote work settings")
    parser.add_argument("--recent-only", action="store_true", help="Only include recent jobs")
    parser.add_argument("--time-filter", type=str, help="Time filter for job listings (e.g., 'r2592000' for 30 days)")
    
    # Analysis configuration options
    parser.add_argument("--cv-file", type=str, help="Path to the CV markdown file")
    parser.add_argument("--max-jobs", type=int, help="Maximum number of jobs to scrape per search (minimum 100 required by Apify API)")
    parser.add_argument("--max-analyze", type=int, help="Maximum number of jobs to analyze with LLM")
    parser.add_argument("--match-threshold", type=float, help="Minimum match score threshold (0-10)")
    parser.add_argument("--llm-model", type=str, choices=["claude-3-opus-20240229", "anthropic/claude-3-sonnet:20240229"], 
                        help="LLM model to use for analysis")
    parser.add_argument("--llm-provider", type=str, choices=["anthropic", "openrouter"],
                        help="Provider for the LLM API")
    
    args = parser.parse_args()
    
    # Process command-line overrides
    config_overrides = {}
    if args.countries:
        config_overrides["countries"] = args.countries
    if args.job_roles:
        # Convert flat list to dictionary with a single "Custom" category
        config_overrides["job_roles"] = {"Custom": args.job_roles}
    if args.job_types:
        config_overrides["job_types"] = args.job_types
    if args.experience:
        config_overrides["experience_levels"] = args.experience
    if args.remote:
        config_overrides["remote_settings"] = args.remote
    if args.recent_only:
        config_overrides["recent_jobs_only"] = True
    if args.time_filter:
        config_overrides["time_filter"] = args.time_filter
    if args.cv_file:
        config_overrides["cv_file_path"] = args.cv_file
    if args.max_jobs:
        # Ensure we're requesting at least 100 jobs per search (Apify actor requirement)
        config_overrides["max_jobs_per_search"] = max(100, args.max_jobs)
    else:
        # Default to 100 if not specified
        config_overrides["max_jobs_per_search"] = 100
    if args.max_analyze:
        config_overrides["max_jobs_to_analyze"] = args.max_analyze
    if args.force_update:
        config_overrides["force_update"] = True
    if args.match_threshold is not None:
        config_overrides["match_score_threshold"] = args.match_threshold
    if args.llm_model:
        config_overrides["llm_model"] = args.llm_model
    if args.llm_provider:
        config_overrides["llm_provider"] = args.llm_provider
    
    try:
        # Run the main process
        result = asyncio.run(main(
            skip_scraping=args.skip_scraping,
            config_overrides=config_overrides,
            profile_name=args.profile
        ))
        
        # Save profile if requested
        if args.save_profile and config_overrides:
            # Load the profile first if it exists
            existing_profile = load_config_profile(args.save_profile) or {}
            # Update with new overrides
            existing_profile.update(config_overrides)
            # Save the updated profile
            save_config_profile(args.save_profile, existing_profile)
            
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
