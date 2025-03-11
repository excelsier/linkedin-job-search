#!/usr/bin/env python
"""
Test module for LinkedIn job extraction functionality.
This script tests the selector configuration and job extraction functionality.
"""
import os
import sys
import json
import logging
import argparse
from pathlib import Path
from bs4 import BeautifulSoup
import requests

# Add project root to Python path
project_root = Path(__file__).parent.parent.absolute()
sys.path.append(str(project_root))

# Import project modules
from scripts.selector_config import (
    JOB_DESCRIPTION_SELECTORS,
    JOB_TITLE_SELECTORS,
    COMPANY_NAME_SELECTORS,
    LOCATION_SELECTORS,
    get_job_description,
    is_valid_job_description,
    clean_job_description
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(project_root / "logs" / "job_extraction_test.log")
    ]
)
logger = logging.getLogger("job_extraction_test")

def load_test_html(file_path=None, url=None):
    """
    Load HTML content for testing from a file or URL.
    
    Args:
        file_path: Path to HTML file (optional)
        url: URL to fetch HTML from (optional)
        
    Returns:
        str: HTML content or None if loading fails
    """
    if file_path:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load HTML from file {file_path}: {str(e)}")
            return None
    
    if url:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to load HTML from URL {url}: {str(e)}")
            return None
    
    logger.error("Either file_path or url must be provided")
    return None

def test_selectors(html):
    """
    Test all selectors on the provided HTML content.
    
    Args:
        html: HTML content to test against
        
    Returns:
        dict: Results of selector testing
    """
    soup = BeautifulSoup(html, 'html.parser')
    results = {
        "job_description": [],
        "job_title": [],
        "company_name": [],
        "location": []
    }
    
    # Test job description selectors
    logger.info("Testing job description selectors...")
    for selector in JOB_DESCRIPTION_SELECTORS:
        elements = soup.select(selector)
        if elements:
            content = str(elements[0])
            is_valid = is_valid_job_description(content)
            results["job_description"].append({
                "selector": selector,
                "found": True,
                "is_valid": is_valid,
                "length": len(content),
                "preview": content[:100] + "..." if len(content) > 100 else content
            })
            logger.info(f"✅ Selector '{selector}' matched, valid: {is_valid}, length: {len(content)}")
        else:
            results["job_description"].append({
                "selector": selector,
                "found": False
            })
            logger.info(f"❌ Selector '{selector}' did not match any elements")
    
    # Test job title selectors
    logger.info("Testing job title selectors...")
    for selector in JOB_TITLE_SELECTORS:
        elements = soup.select(selector)
        if elements:
            text = elements[0].get_text(strip=True)
            results["job_title"].append({
                "selector": selector,
                "found": True,
                "text": text
            })
            logger.info(f"✅ Job title selector '{selector}' matched: {text}")
        else:
            results["job_title"].append({
                "selector": selector,
                "found": False
            })
            logger.info(f"❌ Job title selector '{selector}' did not match any elements")
    
    # Test company name selectors
    logger.info("Testing company name selectors...")
    for selector in COMPANY_NAME_SELECTORS:
        elements = soup.select(selector)
        if elements:
            text = elements[0].get_text(strip=True)
            results["company_name"].append({
                "selector": selector,
                "found": True,
                "text": text
            })
            logger.info(f"✅ Company name selector '{selector}' matched: {text}")
        else:
            results["company_name"].append({
                "selector": selector,
                "found": False
            })
            logger.info(f"❌ Company name selector '{selector}' did not match any elements")
    
    # Test location selectors
    logger.info("Testing location selectors...")
    for selector in LOCATION_SELECTORS:
        elements = soup.select(selector)
        if elements:
            text = elements[0].get_text(strip=True)
            results["location"].append({
                "selector": selector,
                "found": True,
                "text": text
            })
            logger.info(f"✅ Location selector '{selector}' matched: {text}")
        else:
            results["location"].append({
                "selector": selector,
                "found": False
            })
            logger.info(f"❌ Location selector '{selector}' did not match any elements")
    
    return results

def test_extraction_function(html):
    """
    Test the job description extraction function.
    
    Args:
        html: HTML content to test against
        
    Returns:
        dict: Extracted job data or None if extraction fails
    """
    logger.info("Testing job description extraction function...")
    job_data = get_job_description(html)
    
    if job_data:
        logger.info(f"✅ Job extraction successful:")
        logger.info(f"  Job Title: {job_data.get('job_title')}")
        logger.info(f"  Company: {job_data.get('company_name')}")
        logger.info(f"  Location: {job_data.get('location')}")
        logger.info(f"  Description Length: {len(job_data.get('description_html', ''))}")
    else:
        logger.error("❌ Job extraction failed")
    
    return job_data

def save_results(results, file_path):
    """
    Save test results to a JSON file.
    
    Args:
        results: Test results to save
        file_path: File path to save results to
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {file_path}")
    except Exception as e:
        logger.error(f"Failed to save results to {file_path}: {str(e)}")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test LinkedIn job extraction functionality.")
    
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument('--file', '-f', help='Path to HTML file for testing')
    source_group.add_argument('--url', '-u', help='URL to fetch HTML from for testing')
    
    parser.add_argument('--output', '-o', help='Path to save test results', 
                        default=str(project_root / "results" / "extraction_test_results.json"))
    
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    return parser.parse_args()

def main():
    """Run the job extraction tests."""
    args = parse_arguments()
    
    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Load HTML content
    html = load_test_html(file_path=args.file, url=args.url)
    if not html:
        logger.error("Failed to load HTML content for testing")
        return 1
    
    logger.info(f"Loaded HTML content ({len(html)} bytes)")
    
    # Run tests
    selector_results = test_selectors(html)
    extraction_results = test_extraction_function(html)
    
    # Save results
    results = {
        "selector_tests": selector_results,
        "extraction_test": extraction_results
    }
    save_results(results, args.output)
    
    # Summary
    found_desc_selectors = sum(1 for item in selector_results["job_description"] if item.get("found", False))
    found_title_selectors = sum(1 for item in selector_results["job_title"] if item.get("found", False))
    found_company_selectors = sum(1 for item in selector_results["company_name"] if item.get("found", False))
    found_location_selectors = sum(1 for item in selector_results["location"] if item.get("found", False))
    
    logger.info("\n=== Test Summary ===")
    logger.info(f"Job Description Selectors: {found_desc_selectors}/{len(JOB_DESCRIPTION_SELECTORS)} matched")
    logger.info(f"Job Title Selectors: {found_title_selectors}/{len(JOB_TITLE_SELECTORS)} matched")
    logger.info(f"Company Name Selectors: {found_company_selectors}/{len(COMPANY_NAME_SELECTORS)} matched")
    logger.info(f"Location Selectors: {found_location_selectors}/{len(LOCATION_SELECTORS)} matched")
    logger.info(f"Extraction Function: {'Successful' if extraction_results else 'Failed'}")
    
    return 0 if extraction_results and found_desc_selectors > 0 else 1

if __name__ == "__main__":
    sys.exit(main())
