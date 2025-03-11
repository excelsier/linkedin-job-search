#!/usr/bin/env python
"""
LinkedIn Job Search - Sample Configurations

This script demonstrates how to use the LinkedIn job search system with different configuration profiles.
It provides example commands and configurations for various job search scenarios.
"""

import argparse
import subprocess
import os
import yaml
from pathlib import Path

# Ensure necessary directory exists
DATA_DIR = Path(__file__).parent.parent / "data"
PROFILES_DIR = DATA_DIR / "profiles"
os.makedirs(PROFILES_DIR, exist_ok=True)

# Example configuration profiles
EXAMPLE_PROFILES = {
    "tech_jobs_usa": {
        "countries": ["United States"],
        "job_roles": {
            "Software Development": ["Software Engineer", "Backend Developer", "Frontend Developer"]
        },
        "job_types": ["full-time"],
        "experience_levels": ["mid-senior"],
        "remote_settings": ["remote", "hybrid"],
        "recent_jobs_only": True,
        "max_jobs_per_search": 30,
        "max_jobs_to_analyze": 20,
        "match_score_threshold": 7.5
    },
    
    "data_science_europe": {
        "countries": ["Germany", "France", "Netherlands", "United Kingdom"],
        "job_roles": {
            "Data Science": ["Data Scientist", "ML Engineer", "Data Analyst"],
            "AI Research": ["Research Scientist", "AI Researcher"]
        },
        "job_types": ["full-time", "contract"],
        "experience_levels": ["mid-senior", "director"],
        "remote_settings": ["remote"],
        "recent_jobs_only": True,
        "time_filter": "r604800",  # Last week
        "max_jobs_per_search": 25,
        "max_jobs_to_analyze": 25,
        "match_score_threshold": 7.0
    },
    
    "product_management_global": {
        "countries": ["United States", "United Kingdom", "Canada", "Australia", "Germany"],
        "job_roles": {
            "Product": ["Product Manager", "Senior Product Manager", "Director of Product"]
        },
        "job_types": ["full-time"],
        "experience_levels": ["mid-senior", "director"],
        "remote_settings": ["remote", "hybrid", "on-site"],
        "time_filter": "r2592000",  # Last 30 days
        "max_jobs_per_search": 40,
        "max_jobs_to_analyze": 30,
        "match_score_threshold": 8.0
    }
}

def save_example_profiles():
    """Save example profiles to the profiles directory"""
    for name, config in EXAMPLE_PROFILES.items():
        profile_path = PROFILES_DIR / f"{name}.yaml"
        with open(profile_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False)
        print(f"Saved example profile: {name}")

def show_example_commands():
    """Show example commands using the profiles and command-line arguments"""
    print("\n=== Example Commands ===\n")
    
    print("1. Using a profile:")
    print("   python scripts/main.py --profile tech_jobs_usa")
    
    print("\n2. Using command-line arguments:")
    print("   python scripts/main.py --countries \"United States\" \"Canada\" --job-roles \"Software Engineer\" \"Data Scientist\" --job-types \"full-time\" --remote \"remote\" --experience \"mid-senior\"")
    
    print("\n3. Creating a custom profile:")
    print("   python scripts/main.py --countries \"United Kingdom\" --job-roles \"Product Designer\" \"UX Researcher\" --job-types \"full-time\" \"contract\" --save-profile design_jobs_uk")
    
    print("\n4. Running with a profile and overriding specific parameters:")
    print("   python scripts/main.py --profile data_science_europe --match-threshold 8.0 --recent-only")
    
    print("\n5. Skip scraping and analyze most recent data with stricter threshold:")
    print("   python scripts/main.py --skip-scraping --match-threshold 8.5")
    
    print("\n6. Searching for recent entry-level positions:")
    print("   python scripts/main.py --experience \"entry\" \"associate\" --time-filter \"r86400\"")
    
    print("\n=== LinkedIn Time Filter Options ===")
    print("- Past 24 hours: r86400")
    print("- Past Week: r604800")
    print("- Past Month: r2592000")
    print("- Any Time: \"\"")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkedIn Job Search - Sample Configurations")
    parser.add_argument("--save-profiles", action="store_true", help="Save example profiles")
    parser.add_argument("--run-example", type=int, help="Run example command (1-6)")
    
    args = parser.parse_args()
    
    if args.save_profiles:
        save_example_profiles()
    
    if args.run_example:
        if args.run_example == 1:
            subprocess.run(["python", "scripts/main.py", "--profile", "tech_jobs_usa"])
        elif args.run_example == 2:
            subprocess.run(["python", "scripts/main.py", "--countries", "United States", "Canada", 
                          "--job-roles", "Software Engineer", "Data Scientist", 
                          "--job-types", "full-time", "--remote", "remote", 
                          "--experience", "mid-senior"])
        elif args.run_example == 3:
            subprocess.run(["python", "scripts/main.py", "--countries", "United Kingdom", 
                          "--job-roles", "Product Designer", "UX Researcher", 
                          "--job-types", "full-time", "contract", 
                          "--save-profile", "design_jobs_uk"])
        elif args.run_example == 4:
            subprocess.run(["python", "scripts/main.py", "--profile", "data_science_europe", 
                          "--match-threshold", "8.0", "--recent-only"])
        elif args.run_example == 5:
            subprocess.run(["python", "scripts/main.py", "--skip-scraping", "--match-threshold", "8.5"])
        elif args.run_example == 6:
            subprocess.run(["python", "scripts/main.py", "--experience", "entry", "associate", 
                          "--time-filter", "r86400"])
        else:
            print(f"Example {args.run_example} not found. Choose 1-6.")
    
    # Show example commands
    show_example_commands()
