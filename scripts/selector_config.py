"""
Selector Configuration Module for LinkedIn Job Search and Analysis

This module centralizes all CSS selectors used for job extraction from LinkedIn.
It organizes selectors by priority and provides validation functions to ensure
extracted content is job-related.

Development Rules:
1. Selectors are organized in priority order (primary selectors first, then fallbacks)
2. Each selector is documented with its purpose and target element
3. Validation functions confirm that extracted content is job-related
4. Content cleaning functions remove unwanted HTML and formatting
"""

import re
import logging
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ==========================================
# LinkedIn Job Description Selectors
# ==========================================

# Primary selectors (in order of priority)
JOB_DESCRIPTION_PRIMARY_SELECTORS = [
    # Main content container for job descriptions in newer LinkedIn formats
    ".description__text",
    
    # Used for expandable job content sections across different LinkedIn layouts
    ".show-more-less-html__markup",
    
    # Newer LinkedIn job card format introduced in recent UI updates
    ".job-details-jobs-unified-top-card__job-description",
    
    # Standard job description container used in most job listings
    ".job-description__content"
]

# Fallback selectors (used if primary selectors don't match)
JOB_DESCRIPTION_FALLBACK_SELECTORS = [
    # ID-based selector for job detail container (highly specific)
    "#job-details",
    
    # General layout container for job postings (less specific)
    ".job-view-layout",
    
    # Alternative description container format seen in some job listings
    ".jobs-description__content",
    
    # HTML content box in job listings (very generic)
    ".jobs-box__html-content"
]

# Combined selectors in priority order
JOB_DESCRIPTION_SELECTORS = JOB_DESCRIPTION_PRIMARY_SELECTORS + JOB_DESCRIPTION_FALLBACK_SELECTORS

# ==========================================
# LinkedIn Job Header Selectors
# ==========================================

# Selectors for job title elements
JOB_TITLE_SELECTORS = [
    ".job-details-jobs-unified-top-card__job-title",
    ".jobs-unified-top-card__job-title",
    ".jobs-details-top-card__job-title",
    "h1.jobs-title"
]

# Selectors for company name elements
COMPANY_NAME_SELECTORS = [
    ".job-details-jobs-unified-top-card__company-name",
    ".jobs-unified-top-card__company-name",
    ".jobs-details-top-card__company-info a",
    ".jobs-details-top-card__company-url"
]

# Selectors for job location elements
LOCATION_SELECTORS = [
    ".job-details-jobs-unified-top-card__bullet",
    ".jobs-unified-top-card__bullet",
    ".jobs-details-top-card__bullet",
    ".jobs-details-top-card__workplace-type"
]

# ==========================================
# Content Validation Functions
# ==========================================

def is_valid_job_description(content: str) -> bool:
    """
    Validate that extracted content is likely a job description.
    
    Args:
        content: The HTML or text content to validate
        
    Returns:
        bool: True if content appears to be a valid job description
    """
    if not content or len(content.strip()) < 50:
        logger.debug("Content too short to be a valid job description")
        return False
    
    # Check for common job description keywords
    job_related_keywords = [
        'responsibilities', 'requirements', 'qualifications', 
        'experience', 'skills', 'about the role', 'about the job',
        'what you\'ll do', 'what we\'re looking for'
    ]
    
    content_lower = content.lower()
    keyword_matches = [keyword for keyword in job_related_keywords if keyword in content_lower]
    
    if len(keyword_matches) < 2:
        logger.debug(f"Content lacks job description keywords. Found only: {keyword_matches}")
        return False
    
    # Verify content has some structure (paragraphs, lists)
    if '<p>' not in content and '<li>' not in content and '<br' not in content:
        logger.debug("Content lacks HTML structure expected in job descriptions")
        return False
    
    return True

# ==========================================
# Content Cleaning Functions
# ==========================================

def clean_job_description(html_content: str) -> str:
    """
    Clean job description HTML content by removing unwanted elements and formatting.
    
    Args:
        html_content: The HTML content to clean
        
    Returns:
        str: Cleaned HTML content
    """
    if not html_content:
        return ""
    
    # Parse HTML content
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style elements
    for element in soup(['script', 'style', 'iframe', 'noscript']):
        element.decompose()
    
    # Remove hidden elements
    for element in soup.find_all(style=lambda value: value and 'display:none' in value.replace(' ', '')):
        element.decompose()
    
    for element in soup.find_all(class_=lambda value: value and any(c in value for c in ['hidden', 'visually-hidden'])):
        element.decompose()
    
    # Remove empty paragraphs and divs
    for tag in soup.find_all(['p', 'div']):
        if not tag.get_text(strip=True) and not tag.find_all(['img', 'svg']):
            tag.decompose()
    
    # Clean up whitespace
    html = str(soup)
    html = re.sub(r'\n\s*\n', '\n\n', html)  # Remove extra line breaks
    html = re.sub(r'[ \t]+', ' ', html)      # Replace multiple spaces with a single space
    
    return html

# ==========================================
# Extraction Helper Functions
# ==========================================

def extract_with_selectors(html: str, selectors: List[str]) -> Optional[str]:
    """
    Extract content from HTML using a list of selectors in priority order.
    
    Args:
        html: The HTML content to parse
        selectors: List of CSS selectors in priority order
        
    Returns:
        Optional[str]: Extracted HTML content or None if no matching elements found
    """
    if not html:
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Try each selector in order of priority
    for selector in selectors:
        elements = soup.select(selector)
        if elements:
            logger.debug(f"Found matching element with selector: {selector}")
            # Return HTML content of the first matching element
            return str(elements[0])
    
    logger.debug(f"No matching elements found for selectors: {selectors}")
    return None

def get_job_description(html: str) -> Optional[Dict[str, Any]]:
    """
    Extract job description from HTML content using configured selectors.
    
    Args:
        html: The HTML content of the job page
        
    Returns:
        Optional[Dict[str, Any]]: Dictionary with job description data or None if extraction fails
    """
    # Extract the job description using selectors in priority order
    description_html = extract_with_selectors(html, JOB_DESCRIPTION_SELECTORS)
    
    if not description_html:
        logger.warning("Failed to extract job description from HTML")
        return None
    
    # Clean the job description HTML
    cleaned_html = clean_job_description(description_html)
    
    # Validate the description content
    if not is_valid_job_description(cleaned_html):
        logger.warning("Extracted content does not appear to be a valid job description")
        return None
    
    # Extract job title
    job_title_element = extract_with_selectors(html, JOB_TITLE_SELECTORS)
    job_title = BeautifulSoup(job_title_element, 'html.parser').get_text(strip=True) if job_title_element else None
    
    # Extract company name
    company_element = extract_with_selectors(html, COMPANY_NAME_SELECTORS)
    company_name = BeautifulSoup(company_element, 'html.parser').get_text(strip=True) if company_element else None
    
    # Extract location
    location_element = extract_with_selectors(html, LOCATION_SELECTORS)
    location = BeautifulSoup(location_element, 'html.parser').get_text(strip=True) if location_element else None
    
    return {
        "job_title": job_title,
        "company_name": company_name,
        "location": location,
        "description_html": cleaned_html,
        "description_text": BeautifulSoup(cleaned_html, 'html.parser').get_text('\n', strip=True)
    }
