# LinkedIn Job Search and Analysis

An automated system that scrapes LinkedIn job listings, analyzes them against your CV using Claude AI, and identifies the best matches to help with your job search.

## Features

- **LinkedIn Job Scraping**: Automatically scrapes job listings from LinkedIn based on configured countries and job roles
- **Job Deduplication**: Tracks previously scraped jobs in a database to avoid duplicate scraping and reduce API costs
- **Enhanced Job Analysis**: Compares job descriptions with your CV using AI to provide comprehensive insights including:
  - Human and ATS fit scores (separate 1-10 scores for different perspectives)
  - Actionable recommendation codes (PURSUE, CONSIDER, AVOID) for quick filtering
  - Key strengths and critical gaps for each job opportunity
  - Specific CV tailoring suggestions and experience positioning guidance
  - Interview talking points and detailed rationale
- **Google Sheets Integration**: Saves analysis results to Google Sheets for easy tracking and organization with filterable columns
- **Automated Scheduling**: Runs daily to continuously find new job opportunities with intelligent tracking of already processed jobs
- **Comprehensive Logging**: Detailed logging throughout the process for monitoring and debugging

## Project Structure

```
linkedin_job_search_new/
├── data/                  # Directory for storing CV and scraped job data
│   └── cv_template.md     # Template for CV in Markdown format
├── logs/                  # Directory for log files
├── results/               # Directory for analysis results
├── scripts/               # Python scripts for each component
│   ├── apify_scraper.py   # LinkedIn job scraping via Apify
│   ├── config.py          # Configuration settings
│   ├── cv_parser.py       # CV parsing and formatting
│   ├── job_database.py    # Database for tracking and deduplicating jobs
│   ├── llm_analyzer.py    # Claude AI integration for job analysis
│   ├── main.py            # Main orchestration script
│   ├── scheduler.py       # Automated scheduling
│   └── sheets_integration.py # Google Sheets integration
├── credentials.json       # Google API credentials (you need to create this)
├── requirements.txt       # Project dependencies
└── README.md              # This file
```

## Detailed Setup Instructions

### 1. Prerequisites

- **Python 3.8+**: Ensure you have Python 3.8 or newer installed
- **API Accounts**: You'll need accounts with the following services:
  - [Apify](https://apify.com) - For LinkedIn job scraping  
  - [Anthropic](https://anthropic.com) or [OpenRouter](https://openrouter.ai) - For AI analysis
  - [Google Cloud Platform](https://console.cloud.google.com) - For Google Sheets integration

### 2. Clone the Repository

```bash
git clone https://github.com/excelsier/linkedin-job-search.git
cd linkedin-job-search
```

### 3. Set Up Python Environment

Create and activate a virtual environment:

```bash
# Create virtual environment
python -m venv venv

# Activate on macOS/Linux
source venv/bin/activate

# Activate on Windows (Command Prompt)
venv\Scripts\activate

# Activate on Windows (PowerShell)
.\venv\Scripts\Activate.ps1
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Create Required Directories

Ensure these directories exist (they should be created automatically when running the app, but it's good to check):

```bash
mkdir -p data logs results
```

### 6. Set Up Your CV/Resume

1. Copy the CV template to create your own:
   ```bash
   cp data/cv_template.md data/cv.md
   ```

2. Edit `data/cv.md` with your own information:
   - Personal information (name, contact, summary)
   - Skills and expertise
   - Work experience
   - Education
   - Projects and achievements

### 7. API Credentials Setup

#### 7.1 Create Environment Variables File

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your API keys and settings:

```
# API Keys
APIFY_API_KEY=your_apify_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Google API configuration
GOOGLE_APPLICATION_CREDENTIALS=./credentials.json
```

#### 7.2 Apify API Key

1. Create an [Apify](https://apify.com) account if you don't have one
2. Go to Account Settings → Integrations → API
3. Copy your API key to the `.env` file

#### 7.3 LLM API Keys

Choose one of these options:

**Option A: Anthropic Claude (recommended for best quality)**
1. Sign up for [Anthropic API access](https://console.anthropic.com/)
2. Get your API key and set it in the `.env` file

**Option B: OpenRouter for Sonnet 3.7 (more affordable option)**
1. Create an [OpenRouter](https://openrouter.ai) account
2. Generate an API key and set it in the `.env` file

#### 7.4 Google Sheets API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the Google Sheets API and Google Drive API
4. Go to APIs & Services → Credentials
5. Create OAuth 2.0 Client ID credentials
   - Application type: Desktop application
   - Download the JSON file
6. Save the downloaded JSON as `credentials.json` in the project root

### 8. Configure the Application

Edit `scripts/config.py` to customize your job search parameters:

- Target countries
- Job roles and titles
- Experience levels
- Remote work preferences
- LLM model selection
- Schedule settings

### 9. Run the Verification Script

Verify everything is set up correctly:

```bash
python scripts/verify_setup.py
```

This will check that:
- All required directories exist
- Environment variables are set
- API keys are valid
- CV file exists and is properly formatted

### Usage

#### Running Manually

Run the main script to execute the entire process once:

```
python scripts/main.py
```

Options:
- `--skip-scraping`: Skip job scraping and use the most recent scraped data
- `--profile <name>`: Use a saved configuration profile
- `--save-profile <name>`: Save the current configuration as a profile

##### Search Configuration Options:
- `--countries`: Space-separated list of countries to search for jobs
- `--job-roles`: Space-separated list of job roles to search for
- `--job-types`: Job types (e.g., 'full-time', 'part-time', 'contract')
- `--experience`: Experience levels (e.g., 'entry', 'mid-senior', 'director')
- `--remote`: Remote work settings (e.g., 'on-site', 'remote', 'hybrid')
- `--recent-only`: Only include recent jobs
- `--time-filter`: Time filter for job listings (e.g., 'r2592000' for 30 days)

##### Analysis Configuration Options:
- `--cv-file`: Path to the CV markdown file
- `--max-jobs`: Maximum number of jobs to scrape per search
- `--max-analyze`: Maximum number of jobs to analyze with LLM
- `--match-threshold`: Minimum match score threshold (0-10)

#### Scheduled Execution

Start the scheduler to run the process according to the schedule in config.py:

```
python scripts/scheduler.py
```

Options:
- `--run-now`: Run immediately and then start the scheduler
- `--stats`: Display job database statistics

#### Individual Components

You can also run individual components separately for testing:

- Job scraping:
  ```
  python scripts/apify_scraper.py
  ```

- Job analysis with Claude:
  ```
  python scripts/llm_analyzer.py path/to/jobs.json
  ```

- Google Sheets integration:
  ```
  python scripts/sheets_integration.py
  ```

## Configuration

Edit `scripts/config.py` to customize the behavior of the system:

### Job Search Configuration

```python
# Target countries
COUNTRIES = ["Poland", "Portugal", "Spain", "France", "Germany", "United Kingdom"]

# Job roles by category
JOB_ROLES = {
    "Product Leadership": ["Senior Product Manager", "Director of Product"],
    "Strategic Operations": ["Director of Operations", "Chief of Staff"]
}

# Maximum jobs per search query
MAX_JOBS_PER_SEARCH = 30
```

### Analysis Configuration

```python
# Available LLM models
# - "claude-3-opus-20240229" - Claude 3 Opus (direct Anthropic API)
# - "anthropic/claude-3-sonnet:20240229" - Sonnet 3.7 (via OpenRouter)
LLM_MODEL = "claude-3-opus-20240229"
LLM_PROVIDER = "anthropic"  # Options: "anthropic", "openrouter"

# Maximum jobs to analyze (to control API costs)
MAX_JOBS_TO_ANALYZE = 50

# Minimum match score threshold (0-10 scale)
MATCH_SCORE_THRESHOLD = 7.0
```

### Schedule Configuration

```python
# Run daily at 8 AM (cron format)
RUN_SCHEDULE = "0 8 * * *"
```

## How It Works

1. **Job Scraping**: The system uses Apify's LinkedIn Jobs Scraper to collect job listings based on configured countries and job roles. Results are saved to JSON files.

2. **Job Deduplication**: The system tracks all scraped jobs in an SQLite database to prevent duplicate processing:
   - Each job is uniquely identified by its LinkedIn job ID
   - Previously processed jobs are filtered out during daily runs to reduce API costs
   - Database maintains job metadata such as first seen date, processing status, and more

3. **CV Parsing**: Your Markdown CV is parsed to extract key information for the LLM prompt.

4. **Job Analysis**: Claude AI analyzes each job against your CV, generating:
   - Match score (0-10)
   - Detailed analysis of strengths and gaps
   - Suggestions for tailoring your CV
   - Summary of overall fit

4. **Results Storage**: Analysis results are:
   - Saved locally as JSON files
   - Appended to a Google Sheet (avoiding duplicates)
   - Filtered by minimum match score threshold

5. **Automation**: The scheduler runs the process daily to continuously find new opportunities.

### Using Different LLM Models

The system supports different LLM models for job analysis:

```bash
# Use Claude Opus (default)
python scripts/main.py --llm-model "claude-3-opus-20240229" --llm-provider "anthropic"

# Use Sonnet 3.7 via OpenRouter
python scripts/main.py --llm-model "anthropic/claude-3-sonnet:20240229" --llm-provider "openrouter"
```

Notes:
- The OpenRouter API key (starting with `sk-or-`) is automatically detected and used appropriately
- Different models may provide slightly different analysis styles and match scores

## Extending the Project

### Configuration Profiles

You can save frequently used configurations as profiles:

```bash
# Save a configuration profile
python scripts/main.py --countries "United States" "Canada" --job-roles "Software Engineer" "Data Scientist" --save-profile tech_jobs_us_ca

# Use a saved profile
python scripts/main.py --profile tech_jobs_us_ca

# Combine profile with additional overrides
python scripts/main.py --profile tech_jobs_us_ca --recent-only --match-threshold 8.0
```

Profiles are stored as YAML files in the `data/profiles/` directory and can be edited manually if needed.

### Adding New Job Search Parameters

Edit `scripts/config.py` to add new countries or job roles:

```python
COUNTRIES = ["United States", "Canada", "United Kingdom"]
JOB_ROLES = {
    "Data Science": ["Data Scientist", "Machine Learning Engineer"],
    "Software Development": ["Software Engineer", "Backend Developer"]
}
```

Or use command-line arguments for one-time changes:

```bash
python scripts/main.py --countries "United States" "Canada" --job-roles "Software Engineer" "Product Manager"
```

### Customizing Analysis Criteria

Modify the prompt template in `scripts/llm_analyzer.py` to change how jobs are analyzed.

Adjust the match threshold via config.py or command-line:

```bash
# Only show jobs with match score of 8.0 or higher
python scripts/main.py --match-threshold 8.0
```

### Fine-tuning Job Search Filters

Use LinkedIn's search filters to narrow down job results:

```bash
# Search for remote full-time director-level positions
python scripts/main.py --job-types "full-time" --experience "director" --remote "remote"

# Search for recent jobs posted in the last 24 hours
python scripts/main.py --time-filter "r86400"
```

Time filter options:
- Past 24 hours: `r86400`
- Past Week: `r604800`
- Past Month: `r2592000`
- Any Time: "" (empty string)

### Adding New Features

The modular architecture makes it easy to add new features:
- Email notifications for high-scoring matches
- Automated CV tailoring based on suggestions
- Web dashboard for visualizing results

## Troubleshooting

### Common Issues

- **API Key Errors**: Ensure environment variables are set correctly for APIFY_API_KEY and ANTHROPIC_API_KEY
- **Google Sheets Auth Errors**: Verify credentials.json is valid and has the correct permissions
- **Missing CV Error**: Ensure cv.md exists in the data directory and is properly formatted

### Logs

Check log files in the `logs/` directory for detailed error information:
- `apify_scraper.log`: Job scraping logs
- `llm_analyzer.log`: Claude API and analysis logs
- `sheets_integration.log`: Google Sheets integration logs
- `main.log`: Overall process logs
- `scheduler.log`: Scheduler logs

## Enhanced Job Analysis Features

The system provides a comprehensive job analysis format that helps you make informed decisions about which positions to apply for. Key features include:

### Dual Perspective Scoring
- **Human Fit Score (1-10)**: Evaluates how well your background matches the job from a human recruiter's perspective
- **ATS Fit Score (1-10)**: Estimates how well your CV would pass through Applicant Tracking Systems based on keyword matching

### Actionable Recommendations
- **Recommendation Codes**: Each job receives a standardized classification (PURSUE, CONSIDER, AVOID, REVIEW)
- **Recommendation Details**: Detailed reasoning behind the recommendation to help with decision making

### Strengths and Gaps Analysis
- **Key Strengths**: Identifies your strongest qualifications for the specific position
- **Critical Gaps**: Highlights potential areas where your experience may not match the requirements

### Application Guidance
- **CV Tailoring Suggestions**: Specific recommendations for customizing your CV for each job
- **Experience Positioning**: Strategic advice on how to frame your experience for maximum impact
- **Interview Talking Points**: Key topics to emphasize during interviews

### Google Sheets Integration
- All analysis fields are presented in a structured format in Google Sheets
- Filterable columns allow for easy sorting and prioritization of opportunities
- Separate columns for recommendation codes enable quick filtering of top prospects

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Here's how you can contribute:

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add some amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

### Development Guidelines

- Add tests for new features
- Update documentation for changes
- Follow the existing code style
- Keep commits focused and atomic

## Acknowledgements

- [Apify](https://apify.com) - For the LinkedIn Jobs Scraper
- [Anthropic](https://anthropic.com) - For Claude AI models
- [OpenRouter](https://openrouter.ai) - For alternative LLM access
- [Google Sheets API](https://developers.google.com/sheets/api) - For results storage and visualization

## Acknowledgments

- [Apify](https://apify.com/) for the LinkedIn Jobs Scraper
- [Anthropic](https://www.anthropic.com/) for the Claude AI API
- [Google](https://developers.google.com/sheets/api) for the Google Sheets API
