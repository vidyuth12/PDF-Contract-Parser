# PDF Contract Parser

A Python tool to extract structured information from PDF-based contracts while preserving the document's reading order.  
It automatically parses metadata, effective dates, sections, clauses, and tables into a clean, machine-readable format.

## Features
- Extracts contract metadata (title, type, effective date).
- Cleans and normalizes text (handles whitespace and smart quotes).
- Identifies and structures sections, clauses, and tables.
- Preserves document order for better readability.
- Outputs results as JSON or can be further processed with pandas.

## Installation

Clone this repository and install the dependencies:

```bash
git clone https://github.com/vidyuth12/pdf-contract-parser.git
cd pdf-contract-parser
pip install -r requirements.txt
