#!/usr/bin/env python
"""
LLM Job Analyzer Module

This module analyzes job listings against a candidate's CV using the Claude API
to generate match scores and recommendations for CV tailoring.
"""

# Load environment variables first, before any other imports
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load the .env file
dotenv_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / '.env'
load_dotenv(dotenv_path=dotenv_path)

# Now import the rest of the modules
import json
import time
import logging
import re
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
import anthropic

# Import from other modules
from config import (
    LLM_MODEL, LLM_PROVIDER, MAX_JOBS_TO_ANALYZE, MATCH_SCORE_THRESHOLD,
    RESULTS_DIR, LOGS_DIR, DATA_DIR, CV_FILE_PATH
)
from cv_parser import parse_markdown_cv, format_cv_for_prompt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "llm_analyzer.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("llm_analyzer")

# Prompt management for job analysis
import json
from pathlib import Path

def load_prompt_template(prompt_name="job_analysis", prompt_dir=None):
    """
    Load a prompt template from a JSON file.
    
    Args:
        prompt_name (str): Name of the prompt file without extension
        prompt_dir (str, optional): Directory containing prompt templates
        
    Returns:
        str: The prompt template text
    """
    if prompt_dir is None:
        prompt_dir = os.path.join(DATA_DIR, "prompts")
    
    prompt_path = os.path.join(prompt_dir, f"{prompt_name}.json")
    
    try:
        with open(prompt_path, 'r') as f:
            prompt_data = json.load(f)
            return prompt_data.get("template", "")
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {prompt_path}")
        # Return a default template string if file not found
        return """
        Human: Analyze how well this job matches the candidate's CV.        
        
        Here's the candidate's CV:
        
        {candidate_cv}
        
        Here's the job description:
        
        {job_description}
        Assistant: 
        """
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in prompt file: {prompt_path}")
        return ""

# Default prompt template
def get_job_analysis_prompt(prompt_name="job_analysis", custom_prompt=None):
    """
    Get the job analysis prompt, either from a custom prompt or loaded from file.
    
    Args:
        prompt_name (str): Name of the prompt template to load
        custom_prompt (str, optional): Custom prompt to use instead of loaded template
        
    Returns:
        str: The prompt template
    """
    if custom_prompt:
        return custom_prompt
    else:
        return load_prompt_template(prompt_name)


def call_claude_api(prompt: str) -> str:
    """
    Call the Anthropic Claude API with the given prompt.
    Uses OpenRouter API if using an OpenRouter API key (sk-or- prefix).
    
    Args:
        prompt: The prompt to send to the Claude API
        
    Returns:
        The text response from Claude
    """
    try:
        # Get API key from environment variables
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("ANTHROPIC_API_KEY not found in environment variables")
            return ""
        
        # Check if using OpenRouter API (key starts with sk-or-)
        if api_key.startswith("sk-or-"):
            # Using OpenRouter API for Claude
            import requests
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            # Determine which model to use with OpenRouter - always use the proper format
            # OpenRouter expects model IDs in the format 'provider/model_name'
            if LLM_PROVIDER == "openrouter":
                if LLM_MODEL == "claude-3-opus-20240229":
                    openrouter_model = "anthropic/claude-3-opus:20240229"
                elif LLM_MODEL == "anthropic/claude-3-sonnet:20240229":
                    openrouter_model = "anthropic/claude-3-sonnet:20240229"
                else:
                    # Default to Sonnet if the model ID format is unknown
                    openrouter_model = "anthropic/claude-3-sonnet:20240229"
                    logger.warning(f"Unknown model ID format: {LLM_MODEL}, defaulting to Sonnet 3.7")
            else:
                # This shouldn't be reached as we're in the OpenRouter API path, but just in case
                openrouter_model = "anthropic/claude-3-sonnet:20240229"
                
            payload = {
                "model": openrouter_model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 4000
            }
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                response_data = response.json()
                response_text = response_data["choices"][0]["message"]["content"]
                logger.info("Successfully received response from OpenRouter API")
                return response_text
            else:
                logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
                return f"Error: API returned status code {response.status_code}"
        else:
            # Using direct Anthropic API
            client = anthropic.Anthropic(api_key=api_key)
            
            # Call the API
            response = client.messages.create(
                model=LLM_MODEL,
                max_tokens=4000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract the text from the response
            response_text = response.content[0].text
            logger.info("Successfully received response from Claude API")
            return response_text
    
    except Exception as e:
        logger.error(f"Error calling Claude API: {str(e)}")
        return f"Error: {str(e)}"


def extract_response_sections(response_text: str) -> Dict[str, str]:
    """
    Extract structured sections from the LLM response.
    
    Args:
        response_text: The raw response from the LLM
        
    Returns:
        Dictionary with extracted sections from the enhanced job analysis
    """
    sections = {}
    
    # Extract main score (for backward compatibility)
    score_match = re.search(r'<score>(\d+(?:\.\d+)?)</score>', response_text)
    if score_match:
        try:
            score = float(score_match.group(1))
            sections['score'] = score
        except ValueError:
            sections['score'] = 0.0
    else:
        sections['score'] = 0.0
    
    # Extract human fit score
    human_fit_match = re.search(r'<human_fit>\s*(.+?)\s*</human_fit>', response_text, re.DOTALL)
    if human_fit_match:
        content = human_fit_match.group(1).strip()
        # Try to extract the numeric score from the text
        score_in_text = re.search(r'(\d+(?:\.\d+)?)', content)
        if score_in_text:
            try:
                sections['human_fit'] = float(score_in_text.group(1))
            except ValueError:
                sections['human_fit'] = 0.0
        else:
            sections['human_fit'] = 0.0
        sections['human_fit_text'] = content
    else:
        sections['human_fit'] = 0.0
        sections['human_fit_text'] = ""
    
    # Extract ATS fit score
    ats_fit_match = re.search(r'<ats_fit>\s*(.+?)\s*</ats_fit>', response_text, re.DOTALL)
    if ats_fit_match:
        content = ats_fit_match.group(1).strip()
        # Try to extract the numeric score from the text
        score_in_text = re.search(r'(\d+(?:\.\d+)?)', content)
        if score_in_text:
            try:
                sections['ats_fit'] = float(score_in_text.group(1))
            except ValueError:
                sections['ats_fit'] = 0.0
        else:
            sections['ats_fit'] = 0.0
        sections['ats_fit_text'] = content
    else:
        sections['ats_fit'] = 0.0
        sections['ats_fit_text'] = ""
    
    # Extract key strengths
    key_strengths_match = re.search(r'<key_strengths>\s*(.+?)\s*</key_strengths>', response_text, re.DOTALL)
    if key_strengths_match:
        sections['key_strengths'] = key_strengths_match.group(1).strip()
    else:
        sections['key_strengths'] = ""
    
    # Extract critical gaps
    critical_gaps_match = re.search(r'<critical_gaps>\s*(.+?)\s*</critical_gaps>', response_text, re.DOTALL)
    if critical_gaps_match:
        sections['critical_gaps'] = critical_gaps_match.group(1).strip()
    else:
        sections['critical_gaps'] = ""
    
    # Extract CV tailoring
    cv_tailoring_match = re.search(r'<cv_tailoring>\s*(.+?)\s*</cv_tailoring>', response_text, re.DOTALL)
    if cv_tailoring_match:
        sections['cv_tailoring'] = cv_tailoring_match.group(1).strip()
    else:
        sections['cv_tailoring'] = ""
    
    # Extract experience positioning
    experience_positioning_match = re.search(r'<experience_positioning>\s*(.+?)\s*</experience_positioning>', response_text, re.DOTALL)
    if experience_positioning_match:
        sections['experience_positioning'] = experience_positioning_match.group(1).strip()
    else:
        sections['experience_positioning'] = ""
    
    # Extract talking points
    talking_points_match = re.search(r'<talking_points>\s*(.+?)\s*</talking_points>', response_text, re.DOTALL)
    if talking_points_match:
        sections['talking_points'] = talking_points_match.group(1).strip()
    else:
        sections['talking_points'] = ""
    
    # Extract recommendation
    recommendation_match = re.search(r'<recommendation>\s*(.+?)\s*</recommendation>', response_text, re.DOTALL)
    if recommendation_match:
        recommendation_text = recommendation_match.group(1).strip()
        sections['recommendation'] = recommendation_text
        
        # Extract recommendation code (PURSUE, CONSIDER, AVOID)
        if recommendation_text.upper().startswith('PURSUE'):
            sections['recommendation_code'] = 'PURSUE'
        elif recommendation_text.upper().startswith('CONSIDER'):
            sections['recommendation_code'] = 'CONSIDER'
        elif recommendation_text.upper().startswith('AVOID'):
            sections['recommendation_code'] = 'AVOID'
        else:
            # Try to find these keywords anywhere in the text
            if 'PURSUE' in recommendation_text.upper():
                sections['recommendation_code'] = 'PURSUE'
            elif 'CONSIDER' in recommendation_text.upper():
                sections['recommendation_code'] = 'CONSIDER'
            elif 'AVOID' in recommendation_text.upper():
                sections['recommendation_code'] = 'AVOID'
            else:
                sections['recommendation_code'] = 'REVIEW'
    else:
        sections['recommendation'] = ""
        sections['recommendation_code'] = "REVIEW"
    
    # Extract summary
    summary_match = re.search(r'<summary>\s*(.+?)\s*</summary>', response_text, re.DOTALL)
    if summary_match:
        sections['summary'] = summary_match.group(1).strip()
    else:
        sections['summary'] = ""
    
    return sections


def prefilter_jobs(jobs: List[Dict[str, Any]], max_jobs: int = MAX_JOBS_TO_ANALYZE) -> List[Dict[str, Any]]:
    """
    Prefilter jobs to select the most promising ones for detailed LLM analysis.
    
    Args:
        jobs: List of job dictionaries from the Apify scraper
        max_jobs: Maximum number of jobs to analyze (to control API costs)
        
    Returns:
        Filtered list of jobs for LLM analysis
    """
    logger.info(f"Prefiltering {len(jobs)} jobs to select top {max_jobs} for analysis")
    
    # Apply basic filtering criteria
    filtered_jobs = []
    
    for job in jobs:
        # Skip jobs without descriptions
        if not job.get('descriptionText'):
            logger.debug(f"Skipping job with no description: {job.get('title', 'No title')}")
            continue
        
        # Calculate a basic relevance score based on job title and description
        # This is a placeholder for more sophisticated scoring in the future
        relevance_score = 1  # Set a default non-zero score to ensure jobs get selected
        
        # Additional filtering logic could be added here, such as:
        # - Keyword matching based on the CV's skills and experience
        # - Role title matching
        # - Company reputation or industry relevance
        # - Location preference matching
        
        job['relevance_score'] = relevance_score
        filtered_jobs.append(job)
    
    # Sort by relevance score and limit to max_jobs
    filtered_jobs.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
    
    # Always return at least some jobs if available, even if relevance scores are all the same
    result = filtered_jobs[:max_jobs]
    
    logger.info(f"Selected {len(result)} jobs for LLM analysis")
    return result


async def analyze_job(job: Dict[str, Any], cv_text: str, output_dir: Path, prompt_name: str = "job_analysis") -> Dict[str, Any]:
    """
    Analyze a single job against the candidate's CV using the LLM.
    
    Args:
        job: Job dictionary from the Apify scraper
        cv_text: Formatted CV text for the prompt
        output_dir: Directory to save analysis results
        prompt_name: Name of the prompt template to use
        
    Returns:
        Dictionary with analysis results
    """
    job_title = job.get('title', 'Unknown Title')
    company = job.get('companyName', 'Unknown Company')
    job_id = job.get('id', str(int(time.time())))
    logger.info(f"Analyzing job: {job_title} at {company} (ID: {job_id}) using prompt: {prompt_name}")
    
    # Prepare job description and clean it if necessary
    job_description = job.get('descriptionText', '')
    if not job_description:
        logger.warning(f"Job {job_id} has no description, skipping analysis")
        return None
    
    # Get prompt template and format it
    prompt_template = get_job_analysis_prompt(prompt_name)
    prompt = prompt_template.format(
        candidate_cv=cv_text,
        job_description=job_description
    )
    
    # Call LLM API
    response_text = call_claude_api(prompt)
    if not response_text or response_text.startswith("Error"):
        logger.error(f"Failed to get analysis for job {job_id}")
        return None
    
    # Extract structured data from response
    extracted = extract_response_sections(response_text)
    match_score = extracted.get('score', 0.0)
    
    # Create results dictionary with all job data
    result = {
        # Basic job info
        'job_id': job_id,
        'job_title': job_title,
        'company': company,
        'match_score': match_score,
        
        # Enhanced analysis results
        'human_fit': extracted.get('human_fit', 0.0),
        'human_fit_text': extracted.get('human_fit_text', ''),
        'ats_fit': extracted.get('ats_fit', 0.0),
        'ats_fit_text': extracted.get('ats_fit_text', ''),
        'key_strengths': extracted.get('key_strengths', ''),
        'critical_gaps': extracted.get('critical_gaps', ''),
        'cv_tailoring': extracted.get('cv_tailoring', ''),
        'experience_positioning': extracted.get('experience_positioning', ''),
        'talking_points': extracted.get('talking_points', ''),
        'recommendation': extracted.get('recommendation', ''),
        'recommendation_code': extracted.get('recommendation_code', 'REVIEW'),
        'summary': extracted.get('summary', ''),
        'response_text': response_text,
        
        # Use the correct 'link' field for job URL
        'job_url': job.get('link', ''),
        'timestamp': datetime.now().isoformat(),
        
        # Additional job data
        'location': job.get('location', ''),
        'seniority_level': job.get('seniorityLevel', ''),
        'employment_type': job.get('employmentType', ''),
        'job_function': job.get('jobFunction', ''),
        'industries': job.get('industries', ''),
        'posted_at': job.get('postedAt', ''),
        'company_website': job.get('companyWebsite', ''),
        'company_linkedin': job.get('companyLinkedinUrl', ''),
        'description': job.get('descriptionText', ''),
        'salary': ', '.join(salary for salary in job.get('salaryInfo', []) if salary)
    }
    
    # Save detailed analysis to file
    os.makedirs(output_dir, exist_ok=True)
    analysis_file = output_dir / f"job_{job_id}_analysis.json"
    
    with open(analysis_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Job {job_id} analysis complete. Match score: {match_score}/10")
    return result


async def analyze_jobs_batch(jobs: List[Dict[str, Any]], cv_file_path: str = CV_FILE_PATH, 
                       prompt_name: str = "job_analysis", csv_output_file: str = None) -> List[Dict[str, Any]]:
    """
    Analyze a batch of jobs against the candidate's CV using the LLM in parallel.
    
    Args:
        jobs: List of job dictionaries from the Apify scraper
        cv_file_path: Path to the Markdown CV file
        prompt_name: Name of the prompt template to use
        csv_output_file: Path to CSV file for incremental results output
        
    Returns:
        List of dictionaries with analysis results
    """
    logger.info(f"Starting analysis of {len(jobs)} jobs using prompt: {prompt_name}")
    
    # Create output directory for analysis results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(RESULTS_DIR) / f"analysis_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Load and format CV
    try:
        cv_data = parse_markdown_cv(cv_file_path)
        cv_text = format_cv_for_prompt(cv_data)
        logger.info(f"Successfully parsed CV from {cv_file_path}")
    except Exception as e:
        logger.error(f"Failed to parse CV: {str(e)}")
        return []
    
    # Prefilter jobs to select the most promising ones
    filtered_jobs = prefilter_jobs(jobs)
    
    # Create the CSV file and write headers if specified
    csv_lock = asyncio.Lock()  # Lock for thread-safe CSV writing
    if csv_output_file:
        with open(csv_output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Job Title', 'Company', 'Location', 'Match Score', 'Human Fit', 'ATS Fit',
                'Key Strengths', 'Critical Gaps', 'Recommendation Code', 'Recommendation', 'URL'
            ])
        logger.info(f"Created CSV output file: {csv_output_file}")
    
    # Define a callback function to write results to CSV as they complete
    async def process_completed_job(task):
        result = await task
        if not result:
            return None
        
        # Write to CSV if file is specified and match score meets threshold
        if csv_output_file and result.get('match_score', 0) >= MATCH_SCORE_THRESHOLD:
            async with csv_lock:  # Ensure thread-safe file writing
                with open(csv_output_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        result.get('job_title', ''),
                        result.get('company', ''),
                        result.get('location', ''),
                        result.get('match_score', 0),
                        result.get('human_fit', 0),
                        result.get('ats_fit', 0),
                        result.get('key_strengths', ''),
                        result.get('critical_gaps', ''),
                        result.get('recommendation_code', ''),
                        result.get('recommendation', ''),
                        result.get('url', '')
                    ])
                    logger.info(f"Added job {result.get('job_id')} to CSV with match score: {result.get('match_score')}/10")
        
        return result
    
    # Create analysis tasks
    tasks = []
    for job in filtered_jobs:
        task = analyze_job(job, cv_text, output_dir, prompt_name)
        tasks.append(task)
    
    # Process tasks as they complete and write incremental results
    pending = [asyncio.create_task(process_completed_job(task)) for task in tasks]
    results = []
    
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            result = task.result()
            if result:
                results.append(result)
    
    # Save aggregate results
    aggregate_file = output_dir / "aggregate_results.json"
    with open(aggregate_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total_jobs_analyzed': len(results),
            'results': results
        }, f, indent=2, ensure_ascii=False)
    
    # Sort results by match score (descending)
    results.sort(key=lambda x: x.get('match_score', 0), reverse=True)
    
    logger.info(f"Job analysis complete. Analyzed {len(results)} jobs.")
    return results


def extract_best_matches(analysis_results: List[Dict[str, Any]], 
                         threshold: float = MATCH_SCORE_THRESHOLD) -> List[Dict[str, Any]]:
    """
    Extract the best job matches based on match score.
    
    Args:
        analysis_results: List of job analysis results
        threshold: Minimum match score to consider (0-10 scale)
        
    Returns:
        List of best matching jobs above the threshold
    """
    best_matches = [job for job in analysis_results if job.get('match_score', 0) >= threshold]
    return best_matches


def format_for_sheets(job_analysis: Dict[str, Any]) -> List[Any]:
    """
    Format a job analysis result for Google Sheets.
    
    Args:
        job_analysis: Dictionary with job analysis results
        
    Returns:
        List with values formatted for a Google Sheets row
    """
    # Format: [Timestamp, Job Title, Company, Match Score, Summary, URL, Job ID]
    return [
        job_analysis.get('timestamp', ''),
        job_analysis.get('job_title', ''),
        job_analysis.get('company', ''),
        job_analysis.get('match_score', 0),
        job_analysis.get('summary', ''),
        job_analysis.get('job_url', ''),
        job_analysis.get('job_id', '')
    ]


async def run_analysis(jobs_file_path: str, cv_file_path: str = CV_FILE_PATH, 
                    prompt_name: str = "job_analysis", csv_output_file: str = None) -> Dict[str, Any]:
    """
    Main function to run the entire job analysis process.
    
    Args:
        jobs_file_path: Path to the JSON file with scraped jobs
        cv_file_path: Path to the Markdown CV file
        prompt_name: Name of the prompt template to use
        csv_output_file: Path to CSV output file for incremental results
        
    Returns:
        Dictionary with analysis summary and results
    """
    start_time = time.time()
    logger.info(f"Starting job analysis process using prompt: {prompt_name}")
    
    # Load scraped jobs
    try:
        with open(jobs_file_path, 'r', encoding='utf-8') as f:
            jobs_data = json.load(f)
            jobs = jobs_data.get('jobs', [])
        logger.info(f"Loaded {len(jobs)} jobs from {jobs_file_path}")
    except Exception as e:
        logger.error(f"Failed to load jobs data: {str(e)}")
        return {'error': str(e)}
    
    # If no CSV file is specified, create one with timestamp
    if not csv_output_file:
        csv_output_file = os.path.join(RESULTS_DIR, f"job_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    
    # Analyze jobs with incremental CSV output
    analysis_results = await analyze_jobs_batch(jobs, cv_file_path, prompt_name, csv_output_file)
    
    # Extract best matches
    best_matches = extract_best_matches(analysis_results)
    
    # Prepare data for Google Sheets
    sheets_data = [format_for_sheets(job) for job in best_matches]
    
    # Prepare summary
    summary = {
        'total_jobs': len(jobs),
        'jobs_analyzed': len(analysis_results),
        'matching_jobs': len(best_matches),
        'runtime_seconds': round(time.time() - start_time, 2),
        'timestamp': datetime.now().isoformat(),
        'best_matches': best_matches,
        'sheets_data': sheets_data,
        'csv_output_file': csv_output_file
    }
    
    logger.info(f"Analysis complete. Found {len(best_matches)} matching jobs above threshold.")
    return summary


async def run_analysis(jobs_file_path: str, cv_file_path: str = CV_FILE_PATH, 
                    prompt_name: str = "job_analysis", csv_output_file: str = None,
                    update_sheets: bool = True) -> Dict[str, Any]:
    """
    Main function to run the entire job analysis process.
    
    Args:
        jobs_file_path: Path to the JSON file with scraped jobs
        cv_file_path: Path to the Markdown CV file
        prompt_name: Name of the prompt template to use
        csv_output_file: Path to CSV output file for incremental results
        update_sheets: Whether to update Google Sheets with the results
        
    Returns:
        Dictionary with analysis summary and results
    """
    start_time = time.time()
    logger.info(f"Starting job analysis process using prompt: {prompt_name}")
    
    # Load scraped jobs
    try:
        with open(jobs_file_path, 'r', encoding='utf-8') as f:
            jobs_data = json.load(f)
            jobs = jobs_data.get('jobs', [])
        logger.info(f"Loaded {len(jobs)} jobs from {jobs_file_path}")
    except Exception as e:
        logger.error(f"Failed to load jobs data: {str(e)}")
        return {'error': str(e)}
    
    # If no CSV file is specified, create one with timestamp
    if not csv_output_file:
        csv_output_file = os.path.join(RESULTS_DIR, f"job_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    
    # Analyze jobs with incremental CSV output
    analysis_results = await analyze_jobs_batch(jobs, cv_file_path, prompt_name, csv_output_file)
    
    # Extract best matches
    best_matches = extract_best_matches(analysis_results)
    
    # Prepare data for Google Sheets
    sheets_data = [format_for_sheets(job) for job in best_matches]
    
    # Update Google Sheets if enabled
    sheets_updated = False
    if update_sheets and best_matches:
        try:
            # Import here to avoid circular imports
            from sheets_integration import save_analyzed_jobs_to_sheet
            sheets_updated = save_analyzed_jobs_to_sheet(best_matches)
            if sheets_updated:
                logger.info(f"Successfully updated Google Sheets with {len(best_matches)} job matches")
            else:
                logger.warning("Failed to update Google Sheets")
        except Exception as e:
            logger.error(f"Error updating Google Sheets: {str(e)}")
    
    # Prepare summary
    summary = {
        'total_jobs': len(jobs),
        'jobs_analyzed': len(analysis_results),
        'matching_jobs': len(best_matches),
        'runtime_seconds': round(time.time() - start_time, 2),
        'timestamp': datetime.now().isoformat(),
        'best_matches': best_matches,
        'sheets_data': sheets_data,
        'csv_output_file': csv_output_file,
        'sheets_updated': sheets_updated
    }
    
    logger.info(f"Analysis complete. Found {len(best_matches)} matching jobs above threshold.")
    return summary


if __name__ == "__main__":
    # This allows the module to be run directly for testing
    import argparse
    import csv
    
    parser = argparse.ArgumentParser(description='Analyze job listings against a candidate CV')
    
    # Add default argument for jobs file (positional or auto-detected)
    parser.add_argument('--jobs', dest='jobs_file', help='Path to the jobs JSON file')
    
    # Add optional arguments
    parser.add_argument('--cv', dest='cv_file', default=CV_FILE_PATH, 
                        help=f'Path to the Markdown CV file (default: {CV_FILE_PATH})')
    
    parser.add_argument('--prompt', dest='prompt_name', default='job_analysis', 
                        choices=['job_analysis', 'job_analysis_enhanced'],
                        help='Prompt template to use for analysis (default: job_analysis)')
    
    parser.add_argument('--output', dest='output_file',
                        help='Path to CSV output file (default: auto-generated with timestamp)')
    
    parser.add_argument('--no-sheets', dest='update_sheets', action='store_false',
                        help='Disable Google Sheets integration')
    
    args = parser.parse_args()
    
    # Auto-detect jobs file if not specified
    if not args.jobs_file:
        # Use the most recent jobs file if not specified
        data_dir = Path(DATA_DIR)
        job_files = list(data_dir.glob("jobs_*.json"))
        job_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        if not job_files:
            logger.error("No job files found")
            sys.exit(1)
        jobs_file_path = str(job_files[0])
        logger.info(f"Auto-detected jobs file: {jobs_file_path}")
    else:
        jobs_file_path = args.jobs_file
    
    # Auto-generate output file if not specified
    if not args.output_file:
        args.output_file = os.path.join(RESULTS_DIR, f"job_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    
    logger.info(f"Using jobs file: {jobs_file_path} with prompt template: {args.prompt_name}")
    logger.info(f"Results will be written incrementally to: {args.output_file}")
    if args.update_sheets:
        logger.info("Google Sheets integration is enabled")
    else:
        logger.info("Google Sheets integration is disabled")
    
    # Run the analysis with incremental CSV output
    results = asyncio.run(run_analysis(jobs_file_path, args.cv_file, args.prompt_name, 
                                    args.output_file, args.update_sheets))
    
    logger.info(f"Analysis complete. Results saved to: {args.output_file}")
    if results.get('sheets_updated'):
        logger.info("Results also saved to Google Sheets")
