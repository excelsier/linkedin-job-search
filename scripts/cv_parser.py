#!/usr/bin/env python
"""
CV Parser Module

This module handles parsing a Markdown-formatted CV file and preparing the content
for use in LLM prompts. It extracts key sections such as summary, skills, and experience.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

# Import config for logging directory
from config import LOGS_DIR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "cv_parser.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("cv_parser")

def parse_markdown_cv(file_path: str) -> Dict[str, str]:
    """
    Parse a Markdown CV file into a dictionary with sections as keys.
    
    Args:
        file_path: Path to the CV Markdown file
        
    Returns:
        Dictionary with CV sections as keys and content as values
    """
    logger.info(f"Parsing CV from {file_path}")
    
    if not os.path.exists(file_path):
        logger.error(f"CV file not found: {file_path}")
        return {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        cv_data = {}
        current_section = None
        current_subsection = None
        
        for line in lines:
            # Handle main sections (# Section)
            if line.startswith('# '):
                current_section = line[2:].strip()
                current_subsection = None
                cv_data[current_section] = ""
            
            # Handle subsections (## Subsection)
            elif line.startswith('## '):
                if current_section:
                    current_subsection = line[3:].strip()
                    if current_section not in cv_data:
                        cv_data[current_section] = ""
                    if current_subsection not in cv_data:
                        cv_data[current_subsection] = ""
            
            # Add content to current section or subsection
            elif current_section:
                if current_subsection:
                    if current_subsection in cv_data:
                        cv_data[current_subsection] += line
                    else:
                        cv_data[current_subsection] = line
                else:
                    cv_data[current_section] += line
        
        # Clean up the content (remove trailing whitespace)
        for key in cv_data:
            cv_data[key] = cv_data[key].strip()
        
        logger.info(f"Successfully parsed CV with {len(cv_data)} sections")
        return cv_data
    
    except Exception as e:
        logger.error(f"Error parsing CV: {str(e)}")
        return {}

def format_cv_for_prompt(cv_data: Dict[str, str], max_length: int = 4000) -> str:
    """
    Format CV data for inclusion in an LLM prompt.
    
    Args:
        cv_data: Dictionary with CV sections
        max_length: Maximum length of the formatted CV (to avoid token limits)
        
    Returns:
        Formatted CV text
    """
    prompt_parts = []
    
    # Add key sections in a specific order of importance
    priority_sections = ["Summary", "Skills", "Experience", "Education", "Projects"]
    
    for section in priority_sections:
        if section in cv_data and cv_data[section]:
            if section == "Skills":
                # Format skills as a comma-separated list
                skills = [skill.strip('- ').strip() for skill in cv_data[section].split('\n') if skill.strip()]
                prompt_parts.append(f"{section}:\n{', '.join(skills)}")
            else:
                prompt_parts.append(f"{section}:\n{cv_data[section]}")
    
    # Add any remaining sections not in the priority list
    for section, content in cv_data.items():
        if section not in priority_sections and content:
            prompt_parts.append(f"{section}:\n{content}")
    
    # Join all parts with double newlines
    formatted_cv = "\n\n".join(prompt_parts)
    
    # Trim if exceeding max length
    if len(formatted_cv) > max_length:
        logger.warning(f"CV content exceeds max length ({len(formatted_cv)} > {max_length}), trimming...")
        formatted_cv = formatted_cv[:max_length] + "...\n[Content truncated due to length]"
    
    return formatted_cv

def extract_skills(cv_data: Dict[str, str]) -> List[str]:
    """
    Extract a list of skills from the CV data.
    
    Args:
        cv_data: Dictionary with CV sections
        
    Returns:
        List of skills
    """
    skills = []
    
    if "Skills" in cv_data:
        # Extract skills from bullet points or comma-separated lists
        skill_text = cv_data["Skills"]
        
        # Try to extract from bullet points first
        bullet_skills = [line.strip('- ').strip() for line in skill_text.split('\n') if line.strip().startswith('-')]
        
        if bullet_skills:
            skills.extend(bullet_skills)
        else:
            # If no bullet points, try comma separation
            comma_skills = [skill.strip() for skill in skill_text.split(',') if skill.strip()]
            skills.extend(comma_skills)
    
    return skills

def extract_experience_summary(cv_data: Dict[str, str], max_items: int = 3) -> str:
    """
    Create a concise summary of the most recent experience.
    
    Args:
        cv_data: Dictionary with CV sections
        max_items: Maximum number of experience items to include
        
    Returns:
        Summarized experience text
    """
    if "Experience" not in cv_data:
        return ""
    
    experience_text = cv_data["Experience"]
    experience_items = experience_text.split('\n\n')
    
    # Take only the most recent experiences
    recent_experiences = experience_items[:max_items]
    
    return '\n\n'.join(recent_experiences)

if __name__ == "__main__":
    # Test the parser with a sample CV
    import sys
    from config import CV_FILE_PATH
    
    if len(sys.argv) > 1:
        cv_path = sys.argv[1]
    else:
        cv_path = CV_FILE_PATH
    
    cv_data = parse_markdown_cv(cv_path)
    formatted_cv = format_cv_for_prompt(cv_data)
    
    print("\n=== Formatted CV ===\n")
    print(formatted_cv)
    
    print("\n=== Skills ===\n")
    skills = extract_skills(cv_data)
    print(", ".join(skills))
