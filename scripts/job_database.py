#!/usr/bin/env python
"""
Job Database Module

This module provides functionality for tracking and deduplicating job listings
to avoid reprocessing the same jobs when running the scraper daily.
"""

import os
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set

from config import DATA_DIR, LOGS_DIR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "job_database.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("job_database")

# Database path
DB_PATH = os.path.join(DATA_DIR, "jobs.db")


def initialize_database() -> None:
    """Initialize the SQLite database for job tracking if it doesn't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create jobs table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY,
        title TEXT,
        company TEXT,
        location TEXT,
        first_seen_date TEXT,
        last_checked_date TEXT,
        is_processed INTEGER DEFAULT 0
    )
    ''')
    
    # Create job_scraping_history table for tracking scraping runs
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS scraping_history (
        run_id TEXT PRIMARY KEY,
        timestamp TEXT,
        search_config TEXT,
        job_count INTEGER,
        new_job_count INTEGER
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Job database initialized")


def get_known_job_ids() -> Set[str]:
    """
    Get a set of all job IDs that are already in the database.
    
    Returns:
        Set of job IDs as strings
    """
    initialize_database()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT job_id FROM jobs")
    job_ids = {row[0] for row in cursor.fetchall()}
    
    conn.close()
    return job_ids


def add_jobs_to_database(jobs: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Add new jobs to the database and update existing ones.
    
    Args:
        jobs: List of job dictionaries with at least job_id, title, company, and location
        
    Returns:
        Dictionary with counts of new and updated jobs
    """
    initialize_database()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    new_count = 0
    updated_count = 0
    
    for job in jobs:
        job_id = str(job.get("job_id", ""))
        if not job_id:
            continue
            
        # Check if job already exists
        cursor.execute("SELECT job_id FROM jobs WHERE job_id = ?", (job_id,))
        exists = cursor.fetchone() is not None
        
        if exists:
            # Update last checked date
            cursor.execute(
                "UPDATE jobs SET last_checked_date = ? WHERE job_id = ?",
                (current_date, job_id)
            )
            updated_count += 1
        else:
            # Insert new job
            cursor.execute(
                "INSERT INTO jobs (job_id, title, company, location, first_seen_date, last_checked_date) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("location", ""),
                    current_date,
                    current_date
                )
            )
            new_count += 1
    
    conn.commit()
    conn.close()
    
    logger.info(f"Added {new_count} new jobs and updated {updated_count} existing jobs in database")
    return {"new": new_count, "updated": updated_count}


def mark_jobs_as_processed(job_ids: List[str]) -> int:
    """
    Mark jobs as processed in the database.
    
    Args:
        job_ids: List of job IDs to mark as processed
        
    Returns:
        Number of jobs marked as processed
    """
    if not job_ids:
        return 0
        
    initialize_database()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Use parameterized query with a tuple for multiple job_ids
    placeholders = ", ".join(["?"] * len(job_ids))
    cursor.execute(
        f"UPDATE jobs SET is_processed = 1 WHERE job_id IN ({placeholders})",
        tuple(job_ids)
    )
    
    count = cursor.rowcount
    conn.commit()
    conn.close()
    
    logger.info(f"Marked {count} jobs as processed")
    return count


def filter_new_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter out jobs that are already in the database.
    
    Args:
        jobs: List of job dictionaries with job_id
        
    Returns:
        List of jobs that are not already in the database
    """
    known_job_ids = get_known_job_ids()
    
    # Filter out jobs that are already in the database
    new_jobs = [job for job in jobs if str(job.get("job_id", "")) not in known_job_ids]
    
    logger.info(f"Filtered {len(jobs)} total jobs to {len(new_jobs)} new jobs")
    return new_jobs


def record_scraping_run(run_id: str, search_config: Dict[str, Any], job_count: int, new_job_count: int) -> None:
    """
    Record a scraping run in the database.
    
    Args:
        run_id: Unique identifier for the run
        search_config: Search configuration used for the run
        job_count: Total number of jobs fetched
        new_job_count: Number of new jobs added
    """
    initialize_database()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    timestamp = datetime.now().isoformat()
    
    cursor.execute(
        "INSERT INTO scraping_history (run_id, timestamp, search_config, job_count, new_job_count) VALUES (?, ?, ?, ?, ?)",
        (run_id, timestamp, json.dumps(search_config), job_count, new_job_count)
    )
    
    conn.commit()
    conn.close()
    
    logger.info(f"Recorded scraping run {run_id} with {job_count} total jobs and {new_job_count} new jobs")


def get_recent_job_stats(days: int = 7) -> Dict[str, Any]:
    """
    Get statistics about jobs scraped in the last specified number of days.
    
    Args:
        days: Number of days to look back
        
    Returns:
        Dictionary with statistics
    """
    initialize_database()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Calculate date threshold
    threshold_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Get total jobs
    cursor.execute("SELECT COUNT(*) FROM jobs")
    total_jobs = cursor.fetchone()[0]
    
    # Get new jobs in time period
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE first_seen_date >= ?", (threshold_date,))
    new_jobs = cursor.fetchone()[0]
    
    # Get processed jobs
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE is_processed = 1")
    processed_jobs = cursor.fetchone()[0]
    
    # Get scraping runs in time period
    cursor.execute("SELECT COUNT(*) FROM scraping_history WHERE timestamp >= ?", (threshold_date,))
    scraping_runs = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total_jobs": total_jobs,
        "new_jobs_last_days": new_jobs,
        "processed_jobs": processed_jobs,
        "scraping_runs_last_days": scraping_runs,
        "time_period_days": days
    }


if __name__ == "__main__":
    # Initialize the database when run directly
    initialize_database()
    
    # Print current statistics
    stats = get_recent_job_stats()
    print(f"Job Database Statistics:")
    print(f"Total jobs tracked: {stats['total_jobs']}")
    print(f"New jobs in last {stats['time_period_days']} days: {stats['new_jobs_last_days']}")
    print(f"Processed jobs: {stats['processed_jobs']}")
    print(f"Scraping runs in last {stats['time_period_days']} days: {stats['scraping_runs_last_days']}")
