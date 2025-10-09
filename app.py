import os
import sqlite3
import textstat
import time
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
import PyPDF2
import re
import requests
from bs4 import BeautifulSoup
from pdf_generator import generate_pdf
from sentence_transformers import SentenceTransformer, util

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
DB_NAME = "prompt_compare.db"
DEBUG_MODE = os.getenv("DEBUG") == "True"

# --- MAIN APPLICATION ---
def main():
    """Main function to run the application workflow."""
    print("Starting Prompt Compare application...")

    # 1. Project Setup
    # Configure Gemini API
    try:
        genai.configure(api_key=API_KEY)
        print("Gemini API configured successfully.")
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")
        return

    # 5. Database Setup
    print("Initializing database...")
    initialize_database()

    # 2. COR Parsing
    files_directory = "files/"
    cor_file_pattern = r"COR_Movers_(\d{4}-\d{2}-\d{2})\.pdf"
    
    newest_file = None
    newest_date = None

    for filename in os.listdir(files_directory):
        match = re.match(cor_file_pattern, filename)
        if match:
            file_date_str = match.group(1)
            file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()
            
            if newest_date is None or file_date > newest_date:
                newest_date = file_date
                newest_file = os.path.join(files_directory, filename)

    if newest_file is None:
        print(f"Error: No COR_Movers_YYYY-MM-DD.pdf files found in {files_directory}")
        return

    cor_file_path = newest_file
    print(f"Automatically selected newest COR file: {cor_file_path}")
    print(f"Parsing COR file: {cor_file_path}")
    cor_content = read_pdf(cor_file_path)
    if not cor_content:
        return

    tickers = extract_tickers(cor_content)
    if not tickers:
        print("Could not extract tickers. Exiting.")
        return
    
    print(f"Extracted tickers: {tickers}")

    # 3. News Collection
    print("Fetching financial news...")
    news_summary_path = fetch_financial_news(tickers)
    if not news_summary_path:
        print("Could not fetch news. Exiting.")
        return
    
    print(f"News summary saved to: {news_summary_path}")

    # 4. Summary Generation
    print("Generating summaries...")
    primer_file_path = "files/options_primer.pdf"
    summary_a_path, summary_b_path = generate_summaries(cor_content, primer_file_path, news_summary_path)
    if not summary_a_path or not summary_b_path:
        print("Could not generate summaries. Exiting.")
        return
    
    print(f"Summary A saved to: {summary_a_path}")
    print(f"Summary B saved to: {summary_b_path}")

    # Generate PDF summaries
    print("Generating PDF summaries...")
    summary_a_pdf = os.path.join("output/", "summary_A.pdf")
    summary_b_pdf = os.path.join("output/", "summary_B.pdf")
    generate_pdf(summary_a_path, summary_a_pdf)
    generate_pdf(summary_b_path, summary_b_pdf)

    # 6. Metric Calculation
    print("Calculating metrics...")
    metrics_a = calculate_metrics(summary_a_path, "A", news_summary_path)
    metrics_b = calculate_metrics(summary_b_path, "B", news_summary_path)

    print(f"Metrics for Summary A: {metrics_a}")
    print(f"Metrics for Summary B: {metrics_b}")

    # 7. Store Results
    print("Storing results in database...")
    store_results(cor_file_path, primer_file_path, news_summary_path, summary_a_path, summary_b_path, metrics_a, metrics_b)

    # 8. Reporting
    print("Generating report...")
    generate_report()

    print("Application finished.")

# --- HELPER FUNCTIONS ---

def initialize_database():
    """Initializes the SQLite database and creates tables if they don't exist."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Create runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cor_file_id TEXT
            )
        """)

        # Create artifacts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                file_name TEXT,
                file_path TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(id)
            )
        """)

        # Create metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                summary_type TEXT,
                reading_level REAL,
                word_count INTEGER,
                relevance_justification TEXT,
                llm_relevance_score REAL,
                cosine_similarity_score REAL,
                final_relevance_score REAL,
                FOREIGN KEY(run_id) REFERENCES runs(id)
            )
        """)

        conn.commit()
        conn.close()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")

def read_pdf(file_path):
    """Reads the text content from a PDF file."""
    try:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            content = ""
            for page in reader.pages:
                content += page.extract_text()
            return content
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except Exception as e:
        print(f"Error reading PDF file: {e}")
        return None

def extract_tickers(pdf_content):
    """Extracts stock tickers from text content using the Gemini API."""
    print("Extracting tickers using Gemini API...")
    try:
        model = genai.GenerativeModel('gemini-pro-latest')
        response = model.generate_content(f"Extract the stock ticker symbols from this text. Return them as a comma-separated list: {pdf_content}")
        # Simple parsing, assuming the model returns a comma-separated string.
        tickers = [ticker.strip() for ticker in response.text.split(',')]
        return tickers
    except Exception as e:
        print(f"Error calling Gemini API for ticker extraction: {e}")
        return None

def fetch_financial_news(tickers):
    """Fetches financial news for a list of tickers using NewsAPI and saves it to a file."""
    
    if not NEWSAPI_KEY:
        print("Error: NEWSAPI_KEY not found in .env file.")
        return None

    all_news = ""
    
    if DEBUG_MODE:
        tickers = tickers[:2] # Limit to 2 tickers in debug mode
    
    for ticker in tickers:
        print(f"Fetching news for {ticker} using NewsAPI...")
        try:
            newsapi_url = f"https://newsapi.org/v2/everything?q={ticker} financial news&language=en&pageSize=3&apiKey={NEWSAPI_KEY}"
            response = requests.get(newsapi_url)
            data = response.json()

            if data['status'] == 'ok' and data['articles']:
                print(f"  -> Found {len(data['articles'])} articles for {ticker}")
                for article in data['articles']:
                    all_news += f"\n\n--- NEWS FOR {ticker} ---\n"
                    all_news += f"Title: {article['title']}\n"
                    all_news += f"Source: {article['source']['name']}\n"
                    all_news += f"Description: {article['description']}\n"
                    all_news += f"URL: {article['url']}\n"
            elif data.get('code') == 'apiKeyInvalid':
                print("Error: Invalid NewsAPI key.")
                return None
            else:
                print(f"  -> No news found for {ticker} from NewsAPI.")
        except Exception as e:
            print(f"  -> Error fetching news for {ticker} from NewsAPI: {e}")
        time.sleep(1) # Small delay for API calls

    if not all_news:
        return None

    # Save the aggregated news to a file
    date_str = datetime.now().strftime("%m%d%Y")
    file_path = f"output/news_summary_{date_str}.txt"
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(all_news)
        return file_path
    except Exception as e:
        print(f"Error saving news summary to file: {e}")
        return None

def generate_summaries(cor_content, primer_path, news_summary_path):
    """Generates summaries for two prompt sets and saves them to files."""
    try:
        primer_content = read_pdf(primer_path)
        if not primer_content:
            print("Could not read primer file.")
            return None, None

        with open(news_summary_path, "r", encoding="utf-8") as f:
            news_summary = f.read()

        with open("files/prompt_set_a.txt", "r", encoding="utf-8") as f:
            prompts_a = f.read().split("\n\n")
        
        with open("files/prompt_set_b.txt", "r", encoding="utf-8") as f:
            prompts_b = f.read().split("\n\n")

        summary_a = ""
        for prompt in prompts_a:
            if prompt.strip():
                summary_a += generate_summary_from_prompt(prompt, cor_content, primer_content, news_summary)
                summary_a += "\n\n---\n\n"

        summary_b = ""
        for prompt in prompts_b:
            if prompt.strip():
                summary_b += generate_summary_from_prompt(prompt, cor_content, primer_content, news_summary)
                summary_b += "\n\n---\n\n"

        summary_a_path = "output/summary_A.txt"
        summary_b_path = "output/summary_B.txt"

        with open(summary_a_path, "w", encoding="utf-8") as f:
            f.write(summary_a)
        
        with open(summary_b_path, "w", encoding="utf-8") as f:
            f.write(summary_b)

        return summary_a_path, summary_b_path

    except Exception as e:
        print(f"Error generating summaries: {e}")
        return None, None

def generate_summary_from_prompt(prompt, cor_content, primer_content, news_summary):
    """Generates a summary for a single prompt using the Gemini API."""
    print(f"Generating summary for prompt: {prompt[:50]}...")
    try:
        model = genai.GenerativeModel('gemini-pro-latest')
        response = model.generate_content(f"{prompt}\n\nCOR Content:\n{cor_content}\n\nPrimer Content:\n{primer_content}\n\nNews Summary:\n{news_summary}")
        return response.text
    except Exception as e:
        print(f"Error calling Gemini API for summary generation: {e}")
        return "Error generating summary."

def calculate_metrics(summary_path, summary_type, news_summary_path):
    """Calculates all metrics for a given summary."""
    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            summary_content = f.read()
        
        with open(news_summary_path, "r", encoding="utf-8") as f:
            news_summary_content = f.read()

        print(f"  -> Calculating reading level...")
        reading_level = get_reading_level(summary_content)
        print(f"  -> Calculating word count...")
        word_count = get_word_count(summary_content)
        print(f"  -> Calculating relevance ranking...")
        relevance_justification, llm_relevance_score = get_relevance_ranking(summary_content, news_summary_content)
        print(f"  -> Calculating cosine similarity...")
        cosine_similarity_score = get_cosine_similarity(summary_content, news_summary_content)

        # Combine scores (e.g., 60% LLM, 40% cosine similarity)
        final_relevance_score = (llm_relevance_score * 0.6) + (cosine_similarity_score * 4) # Scale cosine to be out of 10

        return {
            "summary_type": summary_type,
            "reading_level": reading_level,
            "word_count": word_count,
            "relevance_justification": relevance_justification,
            "llm_relevance_score": llm_relevance_score,
            "cosine_similarity_score": cosine_similarity_score,
            "final_relevance_score": final_relevance_score
        }
    except Exception as e:
        print(f"Error calculating metrics: {e}")
        return None

def get_reading_level(text):
    """Calculates the reading level of a text."""
    return textstat.flesch_reading_ease(text)

def get_word_count(text):
    """Calculates the word count of a text."""
    return len(text.split())

def get_relevance_ranking(summary, news_summary):
    """Gets a relevance ranking from the Gemini API."""
    print(f"Getting relevance ranking for summary...")
    try:
        model = genai.GenerativeModel('gemini-pro-latest')
        prompt = f"First, provide a brief, bulleted justification explaining why the summary is relevant to the news articles. Then, provide a relevance score from 1 to 10. Format your response as: \n\nJustification:\n- [Justification point 1]\n- [Justification point 2]\n\nScore: [score] \n\nSummary:\n{summary}\n\nNews Articles:\n{news_summary}"
        response = model.generate_content(prompt)
        
        # Parse the response
        justification = response.text.split("Score:")[0].replace("Justification:", "").strip()
        score = float(response.text.split("Score:")[1].strip())
        return justification, score
    except Exception as e:
        print(f"Error calling Gemini API for relevance ranking: {e}")
        return "Error generating justification.", 0.0

def get_cosine_similarity(text1, text2):
    """Calculates the cosine similarity between two texts."""
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = model.encode([text1, text2])
    return util.pytorch_cos_sim(embeddings[0], embeddings[1]).item()

def store_results(cor_file_path, primer_file_path, news_summary_path, summary_a_path, summary_b_path, metrics_a, metrics_b):
    """Stores artifacts and metrics in the database."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Insert a new run
        cursor.execute("INSERT INTO runs (cor_file_id) VALUES (?)", (os.path.basename(cor_file_path),))
        run_id = cursor.lastrowid

        # Insert artifacts
        artifacts = [
            (run_id, os.path.basename(cor_file_path), cor_file_path),
            (run_id, os.path.basename(primer_file_path), primer_file_path),
            (run_id, os.path.basename(news_summary_path), news_summary_path),
            (run_id, os.path.basename(summary_a_path), summary_a_path),
            (run_id, os.path.basename(summary_b_path), summary_b_path)
        ]
        cursor.executemany("INSERT INTO artifacts (run_id, file_name, file_path) VALUES (?, ?, ?)", artifacts)

        # Insert metrics
        metrics = [
            (run_id, metrics_a['summary_type'], metrics_a['reading_level'], metrics_a['word_count'], metrics_a['relevance_justification'], metrics_a['llm_relevance_score'], metrics_a['cosine_similarity_score'], metrics_a['final_relevance_score']),
            (run_id, metrics_b['summary_type'], metrics_b['reading_level'], metrics_b['word_count'], metrics_b['relevance_justification'], metrics_b['llm_relevance_score'], metrics_b['cosine_similarity_score'], metrics_b['final_relevance_score'])
        ]
        cursor.executemany("INSERT INTO metrics (run_id, summary_type, reading_level, word_count, relevance_justification, llm_relevance_score, cosine_similarity_score, final_relevance_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", metrics)

        conn.commit()
        conn.close()
        print("Results stored successfully.")
    except Exception as e:
        print(f"Error storing results: {e}")

def generate_report():
    """Generates a report from the last 5 runs in the database."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 5")
        runs = cursor.fetchall()

        report = "--- LATEST 5 RUNS ---\n\n"
        for run in runs:
            run_id = run[0]
            report += f"Run ID: {run_id}, Date: {run[1]}, COR File: {run[2]}\n"
            
            cursor.execute("SELECT * FROM metrics WHERE run_id = ?", (run_id,))
            metrics = cursor.fetchall()
            for metric in metrics:
                report += f"  - Summary {metric[2]}: Reading Level={metric[3]}, Word Count={metric[4]}, Final Relevance={metric[8]:.2f}\n"
                report += f"    LLM Justification: {metric[5]}\n"
                report += f"    LLM Score: {metric[6]}, Cosine Similarity: {metric[7]}\n"
            report += "\n"

        print(report)
        
        report_path = "output/report.txt"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report saved to {report_path}")

        conn.close()
    except Exception as e:
        print(f"Error generating report: {e}")

if __name__ == "__main__":
    main()