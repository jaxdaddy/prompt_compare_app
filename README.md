# Prompt Compare Application

This application compares two different prompts for generating financial news summaries and evaluates them based on several metrics.

## Usage

1.  Place your COR metric file (e.g., `COR_Movers_YYYY-MM-DD.pdf`), primer file (`options_primer.pdf`), and prompt set files (`prompt_set_a.txt`, `prompt_set_b.txt`) in the `files/` directory.

2.  **API Keys:**
    *   Create a `.env` file in the project root.
    *   Add your Gemini API key: `GEMINI_API_KEY=your_gemini_api_key_here` (Get it from [Google AI Studio](https://aistudio.google.com/)).
    *   For non-debug mode, you will also need an Alpha Vantage API key. Get a free key from [https://www.alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key) and add it to your `.env` file: `ALPHA_VANTAGE_API_KEY=your_alphavantage_api_key_here`.

3.  Install the required dependencies: `pip install -r requirements.txt`

4.  Run the application: `python app.py`

## Features

*   **Automatic COR File Selection:** The application automatically identifies and selects the newest `COR_Movers_YYYY-MM-DD.pdf` file from the `files/` directory for processing.

*   **Improved Relevance Ranking:** The relevance of generated summaries is now calculated using a combination of:
    *   **LLM Relevance Score:** A qualitative score (1-10) and justification provided by the Gemini LLM.
    *   **Cosine Similarity:** A quantitative measure of semantic similarity between the summary and the news articles, calculated using `sentence-transformers`.
    *   A final combined relevance score is derived from these two metrics.

*   **Debug Mode:**
    *   When `DEBUG_MODE = True` in `.env`, the application will use NewsAPI to fetch news for a limited number of tickers. This allows for testing the application pipeline without hitting external API rate limits or requiring a valid Alpha Vantage API key.
    *   When `DEBUG_MODE = False`, the application attempts to fetch real financial news using the Alpha Vantage API. Be aware of Alpha Vantage's free tier rate limits (typically 25 requests per day).

## Output

Upon successful execution of `app.py`, the application will generate the following files in the `output/` directory:

*   `news_summary_YYYYMMDD.txt`: Aggregated financial news content.
*   `summary_A.txt`: Summaries generated using Prompt Set A.
*   `summary_B.txt`: Summaries generated using Prompt Set B.
*   `summary_A.pdf`: Styled PDF document for Summary A.
*   `summary_B.pdf`: Styled PDF document for Summary B.
*   `output/report.txt`: The final report with the metrics from the last 5 runs.
*   `prompt_compare.db`: An SQLite database storing all run artifacts and metrics.