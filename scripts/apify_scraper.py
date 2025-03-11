#!/usr/bin/env python
"""
Apify LinkedIn Job Scraper

This module integrates with Apify's LinkedIn Jobs Scraper to fetch job listings
based on the criteria defined in the configuration file. It handles API authentication,
job scraping, and saving results.
"""

import os
import sys
import json
import time
import datetime
import requests
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import asyncio

# Import configuration
from config import (
    COUNTRIES, JOB_ROLES, JOB_TYPES, EXPERIENCE_LEVELS, REMOTE_SETTINGS, RECENT_JOBS_ONLY,
    TIME_FILTER, MAX_JOBS_PER_SEARCH, TOTAL_TARGET_JOBS,
    RESULTS_DIR, LOGS_DIR
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "apify_scraper.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("apify_scraper")

def get_timestamp() -> str:
    """Generate a timestamp for file names."""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def create_search_configs(
    countries: List[str],
    job_roles: Dict[str, List[str]],
    jobs_per_search: int,
    job_types: Optional[List[str]] = None,
    experience_levels: Optional[List[str]] = None,
    remote_settings: Optional[List[str]] = None,
    recent_jobs_only: bool = False,
    time_filter: str = ""
) -> List[Dict[str, Any]]:
    """
    Create LinkedIn job search configurations for all combinations of parameters.
    
    Args:
        countries: List of countries to search in
        job_roles: Dictionary mapping categories to lists of job roles
        jobs_per_search: Maximum number of jobs to fetch per search
        job_types: List of job types (e.g., "full-time", "part-time")
        experience_levels: List of experience levels
        remote_settings: List of remote work settings
        recent_jobs_only: Whether to only include recent jobs
        time_filter: Time filter for job listings
    
    Returns:
        List of dictionaries containing search parameters and metadata
    """
    search_configs = []
    
    for country in countries:
        for category, roles in job_roles.items():
            for role in roles:
                # Build search parameters dictionary
                search_params = {
                    "country": country,
                    "category": category,
                    "role": role,
                    "keywords": role,
                    "location": country,
                    "jobs_per_search": jobs_per_search
                }
                
                # Add optional parameters if provided
                if job_types:
                    search_params["job_types"] = job_types
                
                if experience_levels:
                    search_params["experience_levels"] = experience_levels
                
                if remote_settings:
                    search_params["remote_settings"] = remote_settings
                
                search_params["recent_jobs_only"] = recent_jobs_only
                
                if time_filter:
                    search_params["time_filter"] = time_filter
                
                search_configs.append(search_params)
    
    logger.info(f"Created {len(search_configs)} search configurations")
    return search_configs

def save_search_configs(configs: List[Dict[str, Any]]) -> str:
    """
    Save search configurations to a JSON file.
    
    Args:
        configs: List of search configuration dictionaries
        
    Returns:
        Path to the saved file
    """
    os.makedirs(os.path.dirname(RESULTS_DIR), exist_ok=True)
    
    timestamp = get_timestamp()
    filename = f"search_configs_{timestamp}.json"
    filepath = os.path.join(RESULTS_DIR, filename)
    
    with open(filepath, 'w') as f:
        json.dump(configs, f, indent=2)
    
    logger.info(f"Saved {len(configs)} search configurations to {filepath}")
    return filepath

async def run_apify_linkedin_scraper(api_key: str, search_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Run the Apify LinkedIn Jobs Scraper using their API.
    
    Args:
        api_key: Apify API key
        search_configs: List of search configuration dictionaries
        
    Returns:
        Dictionary containing results and metadata
    """
    # Generate URLs for each search configuration
    urls = []
    for config in search_configs:
        # Build LinkedIn search URL with all parameters
        base_url = "https://www.linkedin.com/jobs/search/"
        params = []
        
        # Add keywords
        if "keywords" in config:
            keywords = config["keywords"].replace(" ", "%20")
            params.append(f"keywords={keywords}")
        
        # Add location
        if "location" in config:
            location = config["location"].replace(" ", "%20")
            params.append(f"location={location}")
        
        # Add job types filter
        if "job_types" in config and config["job_types"]:
            # LinkedIn job type codes:
            # F = Full-time, P = Part-time, C = Contract, T = Temporary, 
            # V = Volunteer, I = Internship, O = Other
            type_codes = {
                "full-time": "F",
                "part-time": "P",
                "contract": "C",
                "temporary": "T",
                "volunteer": "V",
                "internship": "I",
                "other": "O"
            }
            filter_values = [type_codes.get(t.lower(), "F") for t in config["job_types"] if t.lower() in type_codes]
            if filter_values:
                job_types_param = ",".join([f"f_JT={code}" for code in filter_values])
                params.append(job_types_param)
        
        # Add experience levels filter
        if "experience_levels" in config and config["experience_levels"]:
            # LinkedIn experience level codes:
            # 1 = Internship, 2 = Entry level, 3 = Associate, 4 = Mid-Senior level, 5 = Director, 6 = Executive
            exp_codes = {
                "internship": "1",
                "entry": "2",
                "associate": "3",
                "mid-senior": "4",
                "director": "5",
                "executive": "6"
            }
            filter_values = [exp_codes.get(e.lower(), "4") for e in config["experience_levels"] if e.lower() in exp_codes]
            if filter_values:
                exp_levels_param = ",".join([f"f_E={code}" for code in filter_values])
                params.append(exp_levels_param)
        
        # Add remote settings filter
        if "remote_settings" in config and config["remote_settings"]:
            # LinkedIn remote codes: 1 = On-site, 2 = Remote, 3 = Hybrid
            remote_codes = {
                "on-site": "1",
                "remote": "2",
                "hybrid": "3"
            }
            filter_values = [remote_codes.get(r.lower(), "1") for r in config["remote_settings"] if r.lower() in remote_codes]
            if filter_values:
                remote_param = ",".join([f"f_WT={code}" for code in filter_values])
                params.append(remote_param)
        
        # Add time filter
        if "time_filter" in config and config["time_filter"]:
            params.append(f"f_TPR={config['time_filter']}")
        
        # Add recent jobs filter
        if config.get("recent_jobs_only", False):
            params.append("f_TPR=r2592000")  # Last 30 days
        
        # Construct the final URL
        url = base_url
        if params:
            url += "?" + "&".join(params)
        
        urls.append(url)
        config["url"] = url  # Store the URL in the config for reference
    
    # Calculate jobs per URL to meet the total target
    urls_count = len(urls)
    if urls_count > 0:
        jobs_per_url = min(MAX_JOBS_PER_SEARCH, max(20, TOTAL_TARGET_JOBS // urls_count))
    else:
        jobs_per_url = MAX_JOBS_PER_SEARCH
    
    # Process in smaller batches to avoid overwhelming the API
    BATCH_SIZE = 5  # Process 5 URLs at a time
    total_batches = (urls_count + BATCH_SIZE - 1) // BATCH_SIZE
    
    logger.info(f"Running Apify LinkedIn Jobs Scraper with {urls_count} URLs in {total_batches} batches")
    logger.info(f"Requesting {jobs_per_url} jobs per URL (target total: {TOTAL_TARGET_JOBS})")
    
    all_results = []
    metadata = {
        "batches": [],
        "urls_count": urls_count,
        "jobs_per_url": jobs_per_url,
        "successful_batches": 0,
        "failed_batches": 0,
        "total_jobs": 0
    }
    
    # Process URLs in batches
    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, urls_count)
        batch_urls = urls[start_idx:end_idx]
        
        logger.info(f"Processing batch {batch_num + 1}/{total_batches} with {len(batch_urls)} URLs")
        
        # Set up the Actor input for this batch
        # Ensure we request at least 100 jobs per URL to meet the minimum requirement of the Apify actor
        min_jobs_per_url = max(100, jobs_per_url)
        run_input = {
            "urls": batch_urls,
            "count": min_jobs_per_url,
            "scrapeCompany": True,
            # Debug mode turned off for production
            "debugLog": False
        }
        logger.info(f"Requesting {min_jobs_per_url} jobs per URL to meet the minimum 100 records requirement")
        
        batch_metadata = {
            "batch_num": batch_num + 1,
            "urls": batch_urls,
            "jobs_per_url": jobs_per_url,
            "start_time": datetime.datetime.now().isoformat(),
            "end_time": None,
            "success": False,
            "job_count": 0,
            "error": None
        }
        
        try:
            # Start the Actor run
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            # Start the Actor run
            start_url = "https://api.apify.com/v2/acts/curious_coder~linkedin-jobs-scraper/runs?waitForFinish=60"
            
            # The curious_coder/linkedin-jobs-scraper actor expects the input directly, not in a runInput object
            response = requests.post(
                start_url,
                headers=headers,
                json=run_input
            )
            response.raise_for_status()
            run_info = response.json()
            run_id = run_info.get("data", {}).get("id")
            
            if not run_id:
                raise ValueError(f"Failed to get run ID from response: {run_info}")
            
            logger.info(f"Started Apify run with ID: {run_id}")
            
            # Wait for the run to finish
            max_wait_time = 300  # 5 minutes
            wait_time = 0
            check_interval = 10  # seconds
            
            while wait_time < max_wait_time:
                # Check run status
                status_url = f"https://api.apify.com/v2/actor-runs/{run_id}"
                status_response = requests.get(status_url, headers=headers)
                status_response.raise_for_status()
                
                status_data = status_response.json()
                run_status = status_data.get("data", {}).get("status")
                
                logger.info(f"Run status: {run_status}")
                
                if run_status in ["SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"]:
                    break
                
                # Wait before checking again
                await asyncio.sleep(check_interval)
                wait_time += check_interval
            
            # Get the results
            if run_status == "SUCCEEDED":
                dataset_url = f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items?format=json"
                dataset_response = requests.get(dataset_url, headers=headers)
                dataset_response.raise_for_status()
                
                batch_results = dataset_response.json()
                
                job_count = len(batch_results)
                all_results.extend(batch_results)
                
                batch_metadata["success"] = True
                batch_metadata["job_count"] = job_count
                batch_metadata["end_time"] = datetime.datetime.now().isoformat()
                
                metadata["successful_batches"] += 1
                metadata["total_jobs"] += job_count
                
                logger.info(f"Successfully processed batch {batch_num + 1} with {job_count} jobs")
                
            else:
                error_msg = f"Run failed or timed out: {run_status}"
                logger.error(error_msg)
                
                batch_metadata["success"] = False
                batch_metadata["error"] = error_msg
                batch_metadata["end_time"] = datetime.datetime.now().isoformat()
                
                metadata["failed_batches"] += 1
        
        except Exception as e:
            error_msg = f"Error processing batch {batch_num + 1}: {str(e)}"
            logger.error(error_msg)
            
            batch_metadata["success"] = False
            batch_metadata["error"] = error_msg
            batch_metadata["end_time"] = datetime.datetime.now().isoformat()
            
            metadata["failed_batches"] += 1
        
        metadata["batches"].append(batch_metadata)
        
        # Add a delay between batches to avoid rate limiting
        if batch_num < total_batches - 1:
            delay = 5  # seconds
            logger.info(f"Waiting {delay} seconds before next batch...")
            await asyncio.sleep(delay)
    
    # Compile final results
    results = {
        "metadata": metadata,
        "jobs": all_results
    }
    
    return results

def save_results(results: Dict[str, Any], search_configs: List[Dict[str, Any]]) -> str:
    """
    Save scraping results and metadata to a file.
    
    Args:
        results: Dictionary containing scraping results
        search_configs: Original search configurations
        
    Returns:
        Path to the saved results file
    """
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    timestamp = get_timestamp()
    filename = f"linkedin_jobs_results_{timestamp}.json"
    filepath = os.path.join(RESULTS_DIR, filename)
    
    # Combine results with search configurations
    output = {
        "timestamp": timestamp,
        "search_configs": search_configs,
        "results": results
    }
    
    with open(filepath, 'w') as f:
        json.dump(output, f, indent=2)
    
    job_count = len(results.get("jobs", []))
    logger.info(f"Saved {job_count} job results to {filepath}")
    
    return filepath

async def main():
    """Main execution function."""
    logger.info("Starting LinkedIn job scraping process")
    
    # Ensure necessary directories exist
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    # Get Apify API key from environment or prompt
    api_key = os.environ.get("APIFY_API_KEY")
    if not api_key:
        api_key = input("Please enter your Apify API key: ")
        if not api_key:
            logger.error("No Apify API key provided")
            sys.exit(1)
    
    # Create search configurations with flexible parameters
    search_configs = create_search_configs(
        countries=COUNTRIES,
        job_roles=JOB_ROLES,
        jobs_per_search=MAX_JOBS_PER_SEARCH,
        job_types=JOB_TYPES,
        experience_levels=EXPERIENCE_LEVELS,
        remote_settings=REMOTE_SETTINGS,
        recent_jobs_only=RECENT_JOBS_ONLY,
        time_filter=TIME_FILTER
    )
    config_file = save_search_configs(search_configs)
    
    # Run the Apify scraper
    logger.info("Running Apify LinkedIn Jobs Scraper")
    results = await run_apify_linkedin_scraper(api_key, search_configs)
    
    # Save the results
    results_file = save_results(results, search_configs)
    
    logger.info(f"Scraping process completed. Results saved to {results_file}")
    
    job_count = len(results.get("jobs", []))
    logger.info(f"Total jobs scraped: {job_count}")
    
    return results_file

if __name__ == "__main__":
    asyncio.run(main())
