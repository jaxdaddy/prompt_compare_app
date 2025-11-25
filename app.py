import os
import shutil
import sqlite3
import textstat
import time
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
import PyPDF2
import re
import requests
import yaml
import argparse
from bs4 import BeautifulSoup
from pdf_generator import generate_pdf
from summary_evaluator import evaluate_summary_text
from summary_evaluator import evaluate_summary_text
try:
    from sentence_transformers import SentenceTransformer, util
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("Warning: sentence-transformers not available. Cosine similarity will be mocked.")

from pdf_merger import main as merge_pdfs_main

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
DB_NAME = "prompt_compare.db"
# Default debug mode can be overridden via command line flag
DEBUG_MODE = os.getenv("DEBUG", "False") == "True"
PROMPTS_FILE = "prompts.yaml"

# --- MAIN APPLICATION ---
def main():
    """Main function to run the application workflow."""
    # Parse command line arguments for debug flag
    parser = argparse.ArgumentParser(description="Prompt Compare Application")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode (limit ticker processing)")
    args = parser.parse_args()
    # Override DEBUG_MODE if flag is provided
    global DEBUG_MODE
    if args.debug:
        DEBUG_MODE = True
        print("Debug mode enabled via command line flag.")

    print("Starting Prompt Compare application...")

    # 1. Project Setup
    # Configure Gemini API
    try:
        genai.configure(api_key=API_KEY)
        print("Gemini API configured successfully.")
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")
        return

    # Load Prompts Configuration
    try:
        with open(PROMPTS_FILE, 'r') as f:
            config = yaml.safe_load(f)
        print(f"Loaded configuration from {PROMPTS_FILE}")
    except Exception as e:
        print(f"Error loading prompts configuration: {e}")
        return

    # 5. Database Setup
    print("Initializing database...")
    initialize_database()

    files_directory = "files/"
    
    # Iterate through each file type defined in the configuration
    for file_type_key, file_type_config in config.get('file_types', {}).items():
        print(f"\n--- Processing File Type: {file_type_key} ---")
        
        file_pattern = file_type_config.get('pattern')
        prompts = file_type_config.get('prompts', [])
        
        if not file_pattern or not prompts:
            print(f"Skipping {file_type_key}: Missing pattern or prompts.")
            continue

        # 2. File Parsing (Generalized)
        newest_file = None
        newest_date = None

        for filename in sorted(os.listdir(files_directory)):
            # Skip directories such as the completed folder
            if os.path.isdir(os.path.join(files_directory, filename)):
                continue
            match = re.match(file_pattern, filename)
            if match:
                file_date_str = match.group(1)
                try:
                    file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()
                    if newest_date is None or file_date > newest_date:
                        newest_date = file_date
                        newest_file = os.path.join(files_directory, filename)
                except ValueError:
                    continue

        if newest_file is None:
            print(f"No files found matching pattern {file_pattern} in {files_directory}")
            continue

        if newest_date:
            date_str = newest_date.strftime("%Y%m%d")
        else:
            date_str = datetime.now().strftime("%Y%m%d")

        source_file_path = newest_file
        print(f"Selected newest file: {source_file_path}")
        print(f"Parsing file: {source_file_path}")
        
        # Assuming PDF for now based on current logic, could be generalized further
        source_content = read_pdf(source_file_path)
        if not source_content:
            continue

        tickers = extract_tickers(source_content)
        if not tickers:
            print("Could not extract tickers. Skipping.")
            continue
        
        print(f"Extracted tickers: {tickers}")

        # 3. News Collection
        print("Fetching financial news...")
        news_summary_path = fetch_financial_news(tickers, date_str)
        if not news_summary_path:
            print("Could not fetch news. Creating placeholder news file.")
            news_summary_path = f"output/news_summary_{date_str}.txt"
            with open(news_summary_path, "w", encoding="utf-8") as f:
                f.write("No financial news available for this period.")
        
        print(f"News summary saved to: {news_summary_path}")

        # 4. Summary Generation & Metrics
        primer_file_path = "files/options_primer.pdf"
        primer_content = read_pdf(primer_file_path) # Read once
        
        generated_summaries = []
        
        for prompt_config in prompts:
            prompt_name = prompt_config.get('name')
            prompt_template_path = prompt_config.get('template')
            
            if not prompt_name or not prompt_template_path:
                continue

            # Load prompt from file
            if os.path.exists(prompt_template_path):
                print(f"Using prompt file: {prompt_template_path}")
                try:
                    with open(prompt_template_path, 'r', encoding='utf-8') as f:
                        prompt_template = f.read()
                except Exception as e:
                    print(f"Error reading prompt file {prompt_template_path}: {e}")
                    continue
            else:
                print(f"Warning: Prompt file '{prompt_template_path}' not found. Treating as inline template.")
                prompt_template = prompt_template_path
                
            print(f"Generating summary for prompt: {prompt_name}...")
            
            # Read news summary content
            with open(news_summary_path, "r", encoding="utf-8") as f:
                news_summary_content = f.read()

            summary_text = generate_summary_from_prompt(prompt_template, source_content, primer_content, news_summary_content)
            
            safe_name = prompt_name.replace(" ", "_").replace("/", "-")
            summary_filename = f"output/summary_{file_type_key}_{safe_name}_{date_str}.txt"
            
            with open(summary_filename, "w", encoding="utf-8") as f:
                f.write(summary_text)
            
            print(f"Summary saved to: {summary_filename}")
            
            # Generate PDF
            summary_pdf = summary_filename.replace(".txt", ".pdf")
            generate_pdf(summary_filename, summary_pdf)

            # 6. Metric Calculation
            print(f"Calculating metrics for {prompt_name}...")
            metrics = calculate_metrics(summary_filename, prompt_name, news_summary_path)
            
            generated_summaries.append({
                "path": summary_filename,
                "metrics": metrics,
                "name": prompt_name
            })

        # 7. Store Results
        print("Storing results in database...")
        store_results(source_file_path, primer_file_path, news_summary_path, generated_summaries)
        # Move processed file to completed directory
        completed_dir = os.path.join(files_directory, "completed")
        os.makedirs(completed_dir, exist_ok=True)
        shutil.move(source_file_path, os.path.join(completed_dir, os.path.basename(source_file_path)))

    # 8. Reporting
    print("Generating report...")
    generate_report()

    # PDF Merger might need adjustment or removal if it strictly expects A/B
    # For now, we'll comment it out or leave it if it's generic enough, 
    # but the original code hardcoded summary_B. 
    # Let's skip it to avoid errors until it's generalized.
    # print("Merging PDFs...")
    # merge_pdfs_main()

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
                metric_alignment_score INTEGER,
                metric_alignment_note TEXT,
                data_relevance_score INTEGER,
                data_relevance_note TEXT,
                primer_consistency_score INTEGER,
                primer_consistency_note TEXT,
                structure_score INTEGER,
                structure_note TEXT,
                clarity_score INTEGER,
                clarity_note TEXT,
                writing_quality_score INTEGER,
                writing_quality_note TEXT,
                composite_score REAL,
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

def fetch_financial_news(tickers, date_str):
    """Fetches financial news for a list of tickers using NewsAPI and saves it to a file."""
    
    if not NEWSAPI_KEY:
        print("Error: NEWSAPI_KEY not found in .env file.")
        return None

    all_news = ""
    
    # Respect debug mode: limit to two tickers to avoid exhausting NewsAPI calls
    if DEBUG_MODE:
        tickers = tickers[:2]
        print(f"Debug mode active: limiting news fetching to first {len(tickers)} tickers.")
    
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
    file_path = f"output/news_summary_{date_str}.txt"
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(all_news)
        return file_path
    except Exception as e:
        print(f"Error saving news summary to file: {e}")
        return None

def generate_summary_from_prompt(prompt, cor_content, primer_content, news_summary):
    """Generates a summary for a single prompt using the Gemini API."""
    # print(f"Generating summary for prompt: {prompt[:50]}...")
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

        # New evaluation metrics
        print(f"  -> Calculating new evaluation metrics...")
        eval_metrics = evaluate_summary_text(summary_content)

        return {
            "summary_type": summary_type,
            "reading_level": reading_level,
            "word_count": word_count,
            "relevance_justification": relevance_justification,
            "llm_relevance_score": llm_relevance_score,
            "cosine_similarity_score": cosine_similarity_score,
            "final_relevance_score": final_relevance_score,
            "metric_alignment_score": eval_metrics["relevance"]["Metric Alignment"][0],
            "metric_alignment_note": eval_metrics["relevance"]["Metric Alignment"][1],
            "data_relevance_score": eval_metrics["relevance"]["Data Relevance"][0],
            "data_relevance_note": eval_metrics["relevance"]["Data Relevance"][1],
            "primer_consistency_score": eval_metrics["relevance"]["Primer Consistency"][0],
            "primer_consistency_note": eval_metrics["relevance"]["Primer Consistency"][1],
            "structure_score": eval_metrics["readability"]["Structure"][0],
            "structure_note": eval_metrics["readability"]["Structure"][1],
            "clarity_score": eval_metrics["readability"]["Clarity"][0],
            "clarity_note": eval_metrics["readability"]["Clarity"][1],
            "writing_quality_score": eval_metrics["readability"]["Writing Quality"][0],
            "writing_quality_note": eval_metrics["readability"]["Writing Quality"][1],
            "composite_score": eval_metrics["composite_score"]
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
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        return 0.5 # Mock value
        
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = model.encode([text1, text2])
    return util.pytorch_cos_sim(embeddings[0], embeddings[1]).item()

def store_results(cor_file_path, primer_file_path, news_summary_path, generated_summaries):
    """Stores artifacts and metrics in the database."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Insert a new run
        cursor.execute("INSERT INTO runs (cor_file_id) VALUES (?)", (os.path.basename(cor_file_path),))
        run_id = cursor.lastrowid

        # Insert common artifacts
        common_artifacts = [
            (run_id, os.path.basename(cor_file_path), cor_file_path),
            (run_id, os.path.basename(primer_file_path), primer_file_path),
            (run_id, os.path.basename(news_summary_path), news_summary_path),
        ]
        cursor.executemany("INSERT INTO artifacts (run_id, file_name, file_path) VALUES (?, ?, ?)", common_artifacts)

        # Insert summary artifacts and metrics
        metrics_data = []
        for item in generated_summaries:
            summary_path = item['path']
            metrics = item['metrics']
            
            # Insert summary artifact
            cursor.execute("INSERT INTO artifacts (run_id, file_name, file_path) VALUES (?, ?, ?)", 
                           (run_id, os.path.basename(summary_path), summary_path))
            
            # Prepare metrics data
            metrics_data.append((
                run_id, metrics['summary_type'], metrics['reading_level'], metrics['word_count'], 
                metrics['relevance_justification'], metrics['llm_relevance_score'], metrics['cosine_similarity_score'], 
                metrics['final_relevance_score'], metrics['metric_alignment_score'], metrics['metric_alignment_note'],
                metrics['data_relevance_score'], metrics['data_relevance_note'], metrics['primer_consistency_score'],
                metrics['primer_consistency_note'], metrics['structure_score'], metrics['structure_note'],
                metrics['clarity_score'], metrics['clarity_note'], metrics['writing_quality_score'],
                metrics['writing_quality_note'], metrics['composite_score']
            ))

        cursor.executemany("""
            INSERT INTO metrics (
                run_id, summary_type, reading_level, word_count, relevance_justification, 
                llm_relevance_score, cosine_similarity_score, final_relevance_score, 
                metric_alignment_score, metric_alignment_note, data_relevance_score, data_relevance_note, 
                primer_consistency_score, primer_consistency_note, structure_score, structure_note, 
                clarity_score, clarity_note, writing_quality_score, writing_quality_note, composite_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, metrics_data)

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
            report += f"Run ID: {run[0]}, Date: {run[1]}, COR File: {run[2]}\n"
            
            cursor.execute("SELECT * FROM metrics WHERE run_id = ?", (run_id,))
            metrics = cursor.fetchall()
            for metric in metrics:
                report += f"  - Summary {metric[2]}: Reading Level={metric[3]}, Word Count={metric[4]}, Final Relevance={metric[8]:.2f}, Composite Score={metric[21]:.2f}\n"
                report += f"    LLM Justification: {metric[5]}\n"
                report += f"    LLM Score: {metric[6]}, Cosine Similarity: {metric[7]}\n"
                report += f"    Metric Alignment: {metric[9]}/5 ({metric[10]})\n"
                report += f"    Data Relevance: {metric[11]}/5 ({metric[12]})\n"
                report += f"    Primer Consistency: {metric[13]}/5 ({metric[14]})\n"
                report += f"    Structure: {metric[15]}/5 ({metric[16]})\n"
                report += f"    Clarity: {metric[17]}/5 ({metric[18]})\n"
                report += f"    Writing Quality: {metric[19]}/5 ({metric[20]})\n"
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