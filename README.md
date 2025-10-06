# Prompt Compare Application

This application compares two different prompts for generating financial news summaries and evaluates them based on several metrics.

## Usage

1.  Place your COR metric file, primer file, and prompt set files in the `files/` directory.
2.  Create a `.env` file and add your Gemini API key: `GEMINI_API_KEY=your_api_key_here`. You will also need an Alpha Vantage API key. Get a free key from [https://www.alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key) and add it to your `.env` file: `ALPHA_VANTAGE_API_KEY=your_api_key_here`.
3.  Install the required dependencies: `pip install -r requirements.txt`
4.  Run the application: `python app.py`
