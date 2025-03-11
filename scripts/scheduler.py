#!/usr/bin/env python
"""
Scheduler Module

This module handles the scheduling of the LinkedIn job search and analysis process
using a cron-like scheduler (APScheduler).
"""

import os
import sys
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Import from other modules
from config import RUN_SCHEDULE, LOGS_DIR
from main import main as run_main_process
from job_database import get_recent_job_stats

# Configure logging
os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "scheduler.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("scheduler")


def scheduled_job():
    """Function to run the main process as a scheduled job."""
    logger.info(f"Running scheduled job at {datetime.now().isoformat()}")
    try:
        # Get database stats before running
        stats_before = get_recent_job_stats(days=7)
        logger.info(f"Current job database contains {stats_before['total_jobs']} total jobs, {stats_before['new_jobs_last_days']} new in last week")
        
        # Run the main process with new scraping
        asyncio.run(run_main_process(skip_scraping=False))
        
        # Get stats after running to show what changed
        stats_after = get_recent_job_stats(days=7)
        new_jobs_added = stats_after['total_jobs'] - stats_before['total_jobs']
        logger.info(f"Job complete: added {new_jobs_added} new jobs to database")
        logger.info(f"Database now contains {stats_after['total_jobs']} total jobs, {stats_after['processed_jobs']} have been analyzed")
        
        logger.info("Scheduled job completed successfully")
    except Exception as e:
        logger.error(f"Error in scheduled job: {str(e)}")


def start_scheduler():
    """Start the scheduler with the configured schedule."""
    scheduler = BlockingScheduler()
    
    # Parse the cron schedule
    cron_parts = RUN_SCHEDULE.split()
    if len(cron_parts) != 5:
        logger.error(f"Invalid cron schedule format: {RUN_SCHEDULE}")
        return
    
    minute, hour, day, month, day_of_week = cron_parts
    
    # Add the job with a cron trigger
    scheduler.add_job(
        scheduled_job,
        CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week
        ),
        id='linkedin_job_search',
        name='LinkedIn Job Search and Analysis',
        replace_existing=True
    )
    
    # Log next run time
    job = scheduler.get_job('linkedin_job_search')
    next_run = job.next_run_time
    logger.info(f"Scheduler started. Next run scheduled for: {next_run}")
    
    try:
        # Run the scheduler
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Error in scheduler: {str(e)}")


if __name__ == "__main__":
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--run-now":
            logger.info("Running job immediately")
            scheduled_job()
        elif sys.argv[1] == "--stats":
            # Show database stats
            stats = get_recent_job_stats()
            print(f"\nJob Database Statistics:")
            print(f"Total jobs tracked: {stats['total_jobs']}")
            print(f"New jobs in last {stats['time_period_days']} days: {stats['new_jobs_last_days']}")
            print(f"Processed jobs: {stats['processed_jobs']}")
            print(f"Scraping runs in last {stats['time_period_days']} days: {stats['scraping_runs_last_days']}")
    else:
        # Start the scheduler
        logger.info(f"Starting scheduler with schedule: {RUN_SCHEDULE}")
        start_scheduler()
