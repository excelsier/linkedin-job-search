#!/usr/bin/env python
"""
Google Sheets Integration Module

This module handles the integration with Google Sheets to store job analysis results
and prevent duplicates.
"""

import os
import json
import logging
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import Flow

# Import from other modules
from config import (
    GOOGLE_SHEET_ID, GOOGLE_SHEET_RANGE, GOOGLE_CREDENTIALS_FILE,
    LOGS_DIR, RESULTS_DIR
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "sheets_integration.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("sheets_integration")

# Define the scopes for the Google Sheets API
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def update_sheet_headers() -> bool:
    """
    Update the Google Sheet headers to ensure all columns exist.
    
    Returns:
        True if headers were updated successfully, False otherwise
    """
    try:
        # Build the Sheets API client
        service = create_sheets_service()
        if not service:
            return False
            
        sheet = service.spreadsheets()
        
        # Define the current complete header row with enhanced analysis fields
        header = [
            'Timestamp', 'Job Title', 'Company', 'Match Score', 
            'Summary', 'Recommendation Code', 'Recommendation Details', 'URL', 'Job ID', 'Location', 'Seniority Level',
            'Employment Type', 'Job Function', 'Industries', 'Posted Date',
            'Company Website', 'Company LinkedIn', 'Salary',
            'Human Fit Score', 'ATS Fit Score', 'Key Strengths', 'Critical Gaps',
            'CV Tailoring', 'Experience Positioning', 'Talking Points',
            'Description'
        ]
        
        # Update header row
        sheet.values().update(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=GOOGLE_SHEET_RANGE.split('!')[0] + '!A1',
            valueInputOption='RAW',
            body={'values': [header]}
        ).execute()
        
        logger.info(f"Updated header row in Google Sheet with all columns")
        return True
    except Exception as e:
        logger.error(f"Error updating sheet headers: {str(e)}")
        return False


def get_credentials() -> Optional[Credentials]:
    """
    Get credentials for Google Sheets API, using OAuth client flow.
    
    Returns:
        Google API credentials or None if credentials could not be obtained
    """
    try:
        # Check for token.json (previously stored credentials)
        token_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'token.json')
        if os.path.exists(token_path):
            logger.info(f"Using existing OAuth token from: {token_path}")
            return UserCredentials.from_authorized_user_info(
                json.load(open(token_path)), scopes=SCOPES
            )

        # No existing token, need to generate one using the credentials file
        if os.path.exists(GOOGLE_CREDENTIALS_FILE):
            logger.info(f"Starting OAuth flow with client credentials from: {GOOGLE_CREDENTIALS_FILE}")
            flow = Flow.from_client_secrets_file(
                GOOGLE_CREDENTIALS_FILE,
                scopes=SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob'  # For command-line auth
            )
            
            # Generate auth URL for user to visit
            auth_url, _ = flow.authorization_url(prompt='consent')
            logger.info(f"Please visit this URL to authorize access: {auth_url}")
            print(f"\n\nPlease visit this URL to authorize access: {auth_url}")
            print("\nAfter authorization, you'll get an authorization code. Enter that here:")
            code = input("Authorization code: ").strip()
            
            # Exchange auth code for tokens
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # Save credentials for future use
            with open(token_path, 'w') as token:
                token.write(credentials.to_json())
            logger.info(f"OAuth credentials saved to: {token_path}")
            
            return credentials
        
        # Check if they're trying to use API key - show clear error message
        api_key = os.environ.get("GOOGLE_API_KEY")
        if api_key:
            logger.error("API keys are not supported for creating/updating Google Sheets. OAuth credentials required.")
            print("\nError: API keys cannot be used to create or update Google Sheets. OAuth credentials are required.")
            return None
            
        logger.error("No client credentials file found at: {}".format(GOOGLE_CREDENTIALS_FILE))
        print(f"\nError: No OAuth client credentials file found at: {GOOGLE_CREDENTIALS_FILE}")
        return None
        
    except Exception as e:
        logger.error(f"Error getting Google credentials: {str(e)}")
        return None


def get_existing_job_data(sheet_id: str, sheet_range: str) -> Dict[str, Dict]:
    """
    Get existing job data from the Google Sheet, indexed by job ID.
    
    Args:
        sheet_id: Google Sheet ID
        sheet_range: Sheet range (e.g., 'Sheet1!A2:G')
        
    Returns:
        Dictionary mapping job IDs to row indices and data
    """
    try:
        # Build the Sheets API client
        service = create_sheets_service()
        if not service:
            return {}
            
        sheet = service.spreadsheets()
        
        # Get the current contents of the sheet
        result = sheet.values().get(
            spreadsheetId=sheet_id,
            range=sheet_range
        ).execute()
        
        values = result.get('values', [])
        
        # Create a dictionary mapping job IDs to row indices and data
        job_data = {}
        for i, row in enumerate(values):
            if len(row) >= 7:  # Ensure row has at least 7 columns (job ID is column 7)
                job_id = row[6]
                job_data[job_id] = {
                    'row_index': i,  # 0-based index of the row in the sheet
                    'data': row      # Full row data
                }
                
        logger.info(f"Found {len(job_data)} existing job entries in Google Sheet")
        return job_data
        
    except Exception as e:
        logger.error(f"Error getting existing job data from Google Sheet: {str(e)}")
        return {}


def append_to_sheet(sheet_id: str, sheet_range: str, values: List[List[Any]], force_update: bool = False) -> bool:
    """
    Append rows to the Google Sheet, avoiding duplicates. Can optionally update existing rows.
    
    Args:
        sheet_id: Google Sheet ID
        sheet_range: Sheet range (e.g., 'Sheet1!A2:G')
        values: List of rows to append
        force_update: If True, update existing entries instead of skipping them
        
    Returns:
        True if append was successful, False otherwise
    """
    try:
        if not values:
            logger.warning("No values to append to Google Sheet")
            return True
        
        # Build the Sheets API client
        service = create_sheets_service()
        if not service:
            return False
        sheet = service.spreadsheets()
        
        # Get existing job data
        existing_job_data = get_existing_job_data(sheet_id, sheet_range)
        
        # Track updates and new entries
        filtered_values = []  # New entries to append
        updates = []          # Existing entries to update
        
        base_range = sheet_range.split('!')[0]  # Get sheet name without range
        
        for row in values:
            if len(row) >= 7:  # Ensure row has job ID
                job_id = row[6]
                
                if job_id in existing_job_data:
                    if force_update:
                        # Queue for update - format A1 notation for the range
                        row_index = existing_job_data[job_id]['row_index'] + 2  # +2 because 1-based and header row
                        update_range = f"{base_range}!A{row_index}"
                        updates.append({
                            'range': update_range,
                            'values': [row]
                        })
                else:
                    # New entry, queue for append
                    filtered_values.append(row)
        
        # Process updates if needed
        if force_update and updates:
            body = {
                'valueInputOption': 'RAW',
                'data': updates
            }
            sheet.values().batchUpdate(
                spreadsheetId=sheet_id,
                body=body
            ).execute()
            logger.info(f"Updated {len(updates)} existing job entries in Google Sheet")
        
        # Append new entries if any
        if filtered_values:
            body = {
                'values': filtered_values
            }
            sheet.values().append(
                spreadsheetId=sheet_id,
                range=sheet_range,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            logger.info(f"Appended {len(filtered_values)} new job entries to Google Sheet")
        elif not updates:
            logger.info("No new job entries to append (all are duplicates)")
            
        return True
        
    except Exception as e:
        logger.error(f"Error appending to Google Sheet: {str(e)}")
        return False


def save_analyzed_jobs_to_sheet(analysis_results: List[Dict[str, Any]], force_update: bool = False) -> bool:
    """
    Save the analyzed jobs to Google Sheets.
    
    Args:
        analysis_results: List of job analysis results
        force_update: If True, update existing entries instead of skipping them
        
    Returns:
        True if successful, False otherwise
    """
    # First ensure headers are up to date - this will add any missing columns
    update_sheet_headers()
    try:
        # Format the analysis results for Google Sheets
        sheet_rows = []
        for job in analysis_results:
            # Format: [Timestamp, Job Title, Company, Match Score, Summary, Recommendation Code, Recommendation Details, etc.]
            row = [
                job.get('timestamp', datetime.now().isoformat()),
                job.get('job_title', ''),
                job.get('company', ''),
                job.get('match_score', 0),
                job.get('summary', ''),
                job.get('recommendation_code', 'REVIEW'),
                job.get('recommendation', ''),
                job.get('job_url', ''),
                job.get('job_id', ''),
                job.get('location', ''),
                job.get('seniority_level', ''),
                job.get('employment_type', ''),
                job.get('job_function', ''),
                job.get('industries', ''),
                job.get('posted_at', ''),
                job.get('company_website', ''),
                job.get('company_linkedin', ''),
                job.get('salary', ''),
                job.get('human_fit', 0),
                job.get('ats_fit', 0),
                job.get('key_strengths', ''),
                job.get('critical_gaps', ''),
                job.get('cv_tailoring', ''),
                job.get('experience_positioning', ''),
                job.get('talking_points', ''),
                job.get('description', '')
            ]
            sheet_rows.append(row)
        
        # Append to Google Sheet, with option to force update existing entries
        success = append_to_sheet(GOOGLE_SHEET_ID, GOOGLE_SHEET_RANGE, sheet_rows, force_update=force_update)
        
        if success:
            logger.info("Successfully saved job analysis results to Google Sheet")
        else:
            logger.error("Failed to save job analysis results to Google Sheet")
        
        # Save a local copy as well
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        df = pd.DataFrame(
            sheet_rows, 
            columns=['Timestamp', 'Job Title', 'Company', 'Match Score', 'Summary', 'Recommendation Code', 'Recommendation Details', 'URL', 'Job ID',
                    'Location', 'Seniority Level', 'Employment Type', 'Job Function', 'Industries',
                    'Posted Date', 'Company Website', 'Company LinkedIn', 'Salary',
                    'Human Fit Score', 'ATS Fit Score', 'Key Strengths', 'Critical Gaps',
                    'CV Tailoring', 'Experience Positioning', 'Talking Points',
                    'Description']
        )
        
        os.makedirs(RESULTS_DIR, exist_ok=True)
        csv_path = os.path.join(RESULTS_DIR, f"job_analysis_{timestamp}.csv")
        df.to_csv(csv_path, index=False)
        logger.info(f"Saved local copy of job analysis results to: {csv_path}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error saving analyzed jobs to sheet: {str(e)}")
        return False


def create_sheets_service():
    """
    Create and return a Google Sheets API service instance.
    Uses OAuth credentials for full access to read/write/create Google Sheets.
    
    Returns:
        Google Sheets API service instance or None if creation failed
    """
    try:
        # Get OAuth credentials - this will trigger the OAuth flow if needed
        credentials = get_credentials()
        if credentials:
            logger.info("Creating sheets service with OAuth credentials")
            return build('sheets', 'v4', credentials=credentials)
        
        # If no credentials are available, show clear error message
        logger.error("OAuth credentials required for Google Sheets API operations")
        print("\nError: OAuth credentials are required to access Google Sheets.")
        print("Please run the script again and follow the authorization instructions.")
        return None
    except Exception as e:
        logger.error(f"Error creating Google Sheets service: {str(e)}")
        return None


def create_sheet_if_not_exists() -> bool:
    """
    Create the Google Sheet and set up the header row if it doesn't exist.
    
    Returns:
        True if successful or sheet already exists, False otherwise
    """
    try:
        # Build the Sheets API client
        service = create_sheets_service()
        if not service:
            return False
        sheet = service.spreadsheets()
        
        # First check if we have a non-empty GOOGLE_SHEET_ID from environment or config
        if GOOGLE_SHEET_ID:
            try:
                # Try to access the sheet with the current ID
                sheet.get(spreadsheetId=GOOGLE_SHEET_ID).execute()
                logger.info(f"Google Sheet {GOOGLE_SHEET_ID} exists and is accessible")
                
                # Check if header row exists
                result = sheet.values().get(
                    spreadsheetId=GOOGLE_SHEET_ID,
                    range=GOOGLE_SHEET_RANGE.split('!')[0] + '!A1:Q1'  # Get all header columns (A-Q for 17 columns)
                ).execute()
                
                values = result.get('values', [])
                
                # Add header row if it doesn't exist
                if not values:
                    header = [
                        'Timestamp', 'Job Title', 'Company', 'Match Score', 
                        'Summary', 'URL', 'Job ID', 'Location', 'Seniority Level',
                        'Employment Type', 'Job Function', 'Industries', 'Posted Date',
                        'Company Website', 'Company LinkedIn', 'Salary', 'Description'
                    ]
                    
                    sheet.values().update(
                        spreadsheetId=GOOGLE_SHEET_ID,
                        range=GOOGLE_SHEET_RANGE.split('!')[0] + '!A1',
                        valueInputOption='RAW',
                        body={'values': [header]}
                    ).execute()
                    
                    logger.info(f"Added header row to existing Google Sheet")
                else:
                    # Always update headers to ensure all columns are present
                    update_sheet_headers()
                
                return True
            except Exception as e:
                logger.warning(f"Could not access Google Sheet {GOOGLE_SHEET_ID}: {str(e)}")
                # Continue to create a new sheet only if the current ID is invalid
                pass
        
        # Only create a new sheet if we don't have a valid sheet ID
        # Sheet doesn't exist or ID is invalid, create a new one
        body = {
            'properties': {
                'title': 'LinkedIn Job Analysis'
            },
            'sheets': [
                {
                    'properties': {
                        'title': 'Job Matches',
                        'gridProperties': {
                            'rowCount': 1000,
                            'columnCount': 15
                        }
                    }
                }
            ]
        }
        
        spreadsheet = service.spreadsheets().create(body=body).execute()
        new_sheet_id = spreadsheet.get('spreadsheetId')
        
        logger.info(f"Created new Google Sheet with ID: {new_sheet_id}")
        
        # Set the header row
        header = [
            'Timestamp', 'Job Title', 'Company', 'Match Score', 
            'Summary', 'URL', 'Job ID', 'Location', 'Seniority Level',
            'Employment Type', 'Job Function', 'Industries', 'Posted Date',
            'Company Website', 'Company LinkedIn', 'Salary', 'Description'
        ]
        
        sheet.values().update(
            spreadsheetId=new_sheet_id,
            range='Job Matches!A1',
            valueInputOption='RAW',
            body={'values': [header]}
        ).execute()
        
        logger.info(f"You need to update GOOGLE_SHEET_ID in config.py to: {new_sheet_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating Google Sheet: {str(e)}")
        return False


if __name__ == "__main__":
    # This allows the module to be run directly for testing
    print("Testing Google Sheets integration...")
    create_sheet_if_not_exists()
    
    # Test with sample data
    sample_results = [
        {
            'job_id': 'test_job_1',
            'job_title': 'Test Job 1',
            'company': 'Test Company',
            'match_score': 8.5,
            'summary': 'This is a test job summary',
            'job_url': 'https://linkedin.com/jobs/1',
            'timestamp': datetime.now().isoformat()
        },
        {
            'job_id': 'test_job_2',
            'job_title': 'Test Job 2',
            'company': 'Another Company',
            'match_score': 7.2,
            'summary': 'Another test job summary',
            'job_url': 'https://linkedin.com/jobs/2',
            'timestamp': datetime.now().isoformat()
        }
    ]
    
    success = save_analyzed_jobs_to_sheet(sample_results)
    print(f"Test {'successful' if success else 'failed'}")
