from pdf_generator import generate_pdf
import os

text_content = """COR Daily Report - 2025-11-24

Market Overview
The market showed strong resilience today despite initial volatility. Tech stocks led the rally, while energy lagged.

Top Headlines
1. Tech Giants (AAPL, MSFT) Surge on Earnings Beat
2. Federal Reserve Signals Rate Pause
3. Global Supply Chain Issues Ease

Risk Factors
- Geopolitical tensions remain high.
- Inflation data due next week.
"""

# Write temp text file
with open("temp_daily.txt", "w") as f:
    f.write(text_content)

# Generate PDF in files/
output_pdf = "files/COR_Daily_2025-11-24.pdf"
generate_pdf("temp_daily.txt", output_pdf)

# Clean up
os.remove("temp_daily.txt")
print(f"Created {output_pdf}")
