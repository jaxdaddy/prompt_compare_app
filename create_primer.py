from pdf_generator import generate_pdf
import os

text_content = """Options Primer - Placeholder

This is a placeholder document for the Options Primer.
It contains basic information about options trading concepts.

1. Call Options
2. Put Options
3. Greeks (Delta, Gamma, Theta, Vega)
4. Volatility

Please replace this file with the actual Options Primer content.
"""

# Write temp text file
with open("temp_primer.txt", "w") as f:
    f.write(text_content)

# Generate PDF in files/
output_pdf = "files/options_primer.pdf"
generate_pdf("temp_primer.txt", output_pdf)

# Clean up
os.remove("temp_primer.txt")
print(f"Created {output_pdf}")
