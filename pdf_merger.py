import os
import re
from datetime import datetime
from PyPDF2 import PdfMerger

def merge_pdfs(source_pdfs, output_path):
    """Merges a list of PDF files into a single PDF."""
    merger = PdfMerger()
    for pdf in source_pdfs:
        merger.append(pdf)
    merger.write(output_path)
    merger.close()

def main():
    """Finds the newest source PDFs, merges them, and saves the output."""
    try:
        # 1. Find the newest cor_movers file
        files_directory = "files/"
        cor_file_pattern = r"COR_Movers_(\d{4}-\d{2}-\d{2})\.pdf"
        newest_cor_file = None
        newest_cor_date = None

        for filename in os.listdir(files_directory):
            match = re.match(cor_file_pattern, filename)
            if match:
                file_date_str = match.group(1)
                file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()
                
                if newest_cor_date is None or file_date > newest_cor_date:
                    newest_cor_date = file_date
                    newest_cor_file = os.path.join(files_directory, filename)

        if newest_cor_file is None:
            print(f"Error: No COR_Movers_YYYY-MM-DD.pdf files found in {files_directory}")
            return

        # 2. Find the newest summary_B file
        output_directory = "output/"
        summary_b_pattern = r"summary_B_(\d{8})\.pdf"
        newest_summary_b_file = None
        newest_summary_b_date = None

        for filename in os.listdir(output_directory):
            match = re.match(summary_b_pattern, filename)
            if match:
                file_date_str = match.group(1)
                file_date = datetime.strptime(file_date_str, "%Y%m%d").date()

                if newest_summary_b_date is None or file_date > newest_summary_b_date:
                    newest_summary_b_date = file_date
                    newest_summary_b_file = os.path.join(output_directory, filename)
        
        if newest_summary_b_file is None:
            print(f"Error: No summary_B_yyyymmdd.pdf files found in {output_directory}")
            return

        source_files = [newest_cor_file, newest_summary_b_file]

        # 3. Construct the output filename
        output_date_str = newest_cor_date.strftime("%Y%m%d")
        output_file = f"output/cor_movers_and_analysis_{output_date_str}.pdf"
        
        # 4. Merge the files
        merge_pdfs(source_files, output_file)

        # 5. Print a confirmation message
        full_output_path = os.path.abspath(output_file)
        print(f"Successfully merged PDFs into: {full_output_path}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()