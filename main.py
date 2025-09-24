# Vidyuth Sridhar
# No LLM integration was done in this file.


import argparse
import json
import re
import fitz 
from datetime import datetime
import pandas as pd

class PDFContractParser:
    """
    Parses a PDF contract to extract structured information such as metadata,
    effective date, and a breakdown of sections, clauses, and tables, preserving
    the document's original reading order.
    """

    def __init__(self, pdf_path):
        """
        Initializes the parser with the path to the PDF document.

        Args:
            pdf_path (str): The file path to the input PDF.
        """
        self.pdf_path = pdf_path
        self.doc = None
        self.metadata = {
            "title": None,
            "contract_type": "General Agreement",
            "effective_date": None,
            "preamble": "",
            "sections": []
        }
        self.table_bboxes = {}  # Dictionary to store table bounding boxes by page number

    def _clean_text(self, text):
        """
        Normalizes whitespace, removes leading/trailing spaces, and handles
        specific Unicode characters.

        Args:
            text (str): The text to clean.

        Returns:
            str: The cleaned text.
        """
        # Replace common smart quotes with standard quotes
        text = text.replace('\u201c', '"').replace('\u201d', '"').replace('“', '"').replace('”', '"').replace('\\"', '"').replace("\"", "")
        # Normalize all whitespace to a single space
        return re.sub(r'\s+', ' ', text).strip()

    def _extract_header_metadata(self):
        """
        Extracts the title and contract type from the document's first page.
        """
        try:
            first_page = self.doc[0]
            page_width = first_page.rect.width
            page_height = first_page.rect.height
            # Define a clip area for the top quarter of the page
            title_area = fitz.Rect(0, 0, page_width, page_height / 4)
            full_text_dict = first_page.get_text("dict", clip=title_area)
            
            if full_text_dict['blocks']:
                for block in full_text_dict['blocks']:
                    if 'lines' in block:
                        for line in block['lines']:
                            line_text = self._clean_text("".join([span['text'] for span in line['spans']]))
                            if line_text:
                                self.metadata["title"] = line_text
                                break
                    if self.metadata["title"]:
                        break
            
            if self.metadata["title"]:
                title_upper = self.metadata["title"].upper()
                if "OPEN SOURCE" in title_upper:
                    self.metadata["contract_type"] = "Open Source Agreement"
                elif "LICENSE" in title_upper:
                    self.metadata["contract_type"] = "License Agreement"
                elif "NON-DISCLOSURE" in title_upper:
                    self.metadata["contract_type"] = "Non-Disclosure Agreement"
                elif "SERVICE" in title_upper:
                    self.metadata["contract_type"] = "Service Agreement"
                elif "EMPLOYMENT" in title_upper:
                    self.metadata["contract_type"] = "Employment Contract"
                elif "SALES" in title_upper:
                    self.metadata["contract_type"] = "Sales Agreement"
                elif "LEASE" in title_upper:
                    self.metadata["contract_type"] = "Lease Agreement"
                elif "CONSULTING" in title_upper:
                    self.metadata["contract_type"] = "Consulting Agreement"
                elif "CONSTRUCTION" in title_upper:
                    self.metadata["contract_type"] = "Construction Contract"
        
        except Exception as e:
            print(f"Error extracting header metadata: {e}")

    def _extract_effective_date(self):
        """
        Extracts the effective date from the first page of the document.
        """
        try:
            first_page = self.doc[0]
            full_text = self._clean_text(first_page.get_text())
            
            # Regex to match common date formats
            date_pattern = re.compile(
                r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},\s+\d{4}\b|\b\d{4}-\d{2}-\d{2}\b|\b\d{4}\.\d{2}\.\d{2}\b',
                re.IGNORECASE
            )
            date_match = date_pattern.search(full_text)
            
            if date_match:
                date_str = date_match.group(0)
                date_obj = None
                try:
                    date_obj = datetime.strptime(date_str, '%B %d, %Y')
                except ValueError:
                    try:
                        date_obj = datetime.strptime(date_str, '%b %d, %Y')
                    except ValueError:
                        try:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        except ValueError:
                            try:
                                date_obj = datetime.strptime(date_str, '%Y.%m.%d')
                            except ValueError:
                                pass
                
                if date_obj:
                    self.metadata["effective_date"] = date_obj.strftime('%Y-%m-%d')
                
        except Exception as e:
            print(f"Error extracting effective date: {e}")

    def _is_block_in_table(self, block_bbox, page_number):
        """
        Checks if a given text block's bounding box intersects with any table
        bounding box on the same page.
        """
        if page_number in self.table_bboxes:
            block_rect = fitz.Rect(block_bbox)
            for table_rect in self.table_bboxes[page_number]:
                if block_rect.intersects(table_rect):
                    return True
        return False
        
    def _extract_content(self):
        """
        Extracts all sections and clauses from the entire document, skipping
        any text that falls within a table's bounding box. Tables are nested inside clauses.
        """
        preamble_text = ""
        current_section = None
        is_in_section = False
        footer_text_seen = set()
        
        # Regex patterns for various formats
        #section_re = re.compile(r'^\s*(\d+\.?)\s*(.+)?$')
        section_re = re.compile(r'^\s*([IVXLCDM]+\s*|(?:\d+(?:\.\d+)*)\.?)\s*(.+)?$', re.IGNORECASE)
        clause_re = re.compile(r'^\s*([a-zA-Z]\.|\d+\.\d+\.?|\(\w+\))\s*(.+)?$')
        divider_re = re.compile(r'^\s*_{2,}\s*(.+)?$')
        
        # Flag to skip the very first block, assumed to be the title
        skip_first_block = True

        for page in self.doc:
            page_items = []
            
            # Extract tables and their bounding boxes
            page_tables = page.find_tables()
            if page_tables.tables:
                self.table_bboxes[page.number] = [fitz.Rect(table.bbox) for table in page_tables.tables]
                for table in page_tables.tables:
                    page_items.append({"type": "table", "content": table, "bbox": table.bbox})
            
            # Extract text blocks
            page_text_blocks = page.get_text("dict")['blocks']
            for block in page_text_blocks:
                page_items.append({"type": "text", "content": block, "bbox": block['bbox']})
            
            # Sort items by their vertical position to ensure reading order
            page_items.sort(key=lambda item: item['bbox'][1])
            
            # Define footer area and extract its text
            footer_height = 100
            page_height = page.rect.height
            footer_blocks = page.get_text("dict", clip=fitz.Rect(0, page_height - footer_height, page.rect.width, page_height))['blocks']
            footer_text = " ".join("".join(span['text'] for line in block['lines'] for span in line['spans']) for block in footer_blocks)
            cleaned_footer_text = self._clean_text(footer_text)
            
            if cleaned_footer_text and cleaned_footer_text not in footer_text_seen:
                preamble_text += " " + cleaned_footer_text
                footer_text_seen.add(cleaned_footer_text)
            
            for item in page_items:
                if skip_first_block:
                    skip_first_block = False
                    continue

                if item["type"] == "table":
                    if not current_section:
                        # Create a placeholder section for tables if none exists
                        current_section = {
                            "number": None,
                            "title": None,
                            "clauses": []
                        }
                        is_in_section = True
                        
                    df = item["content"].to_pandas()
                    if df is not None:
                        table_json = json.loads(df.to_json(orient="split"))
                        current_section["clauses"].append({
                            "text": None,
                            "label": None,
                            "index": len(current_section["clauses"]),
                            "table_data": table_json
                        })
                    continue  # Skip to the next item

                # Process text blocks, skipping if in footer or in a table
                block = item["content"]
                if block.get('bbox')[1] > page_height - footer_height or self._is_block_in_table(block.get('bbox'), page.number):
                    continue
                
                block_text = "".join([span['text'] for line in block['lines'] for span in line['spans']])
                
                if 'lines' not in block or not block['lines']:
                    continue

                first_line = block['lines'][0]
                first_span = first_line['spans'][0]
                
                is_bold = bool(first_span['flags'] & 16)
                has_capital = any(c.isupper() for c in first_span['text'])
                
                section_match = section_re.match(block_text)
                clause_match = clause_re.match(block_text)
                divider_match = divider_re.match(block_text)
                
                # --- State Machine Logic ---
                if section_match:
                    if current_section:
                        self.metadata["sections"].append(current_section)
                    
                    is_in_section = True
                    number = section_match.group(1).strip()
                    title = self._clean_text(section_match.group(2))
                    
                    current_section = {
                        "number": number,
                        "title": title,
                        "clauses": []
                    }
                
                elif not is_in_section and clause_match:
                    if current_section:
                         self.metadata["sections"].append(current_section)

                    is_in_section = True
                    label = self._clean_text(clause_match.group(1))
                    title = self._clean_text(clause_match.group(2)) if clause_match.group(2) else ""

                    current_section = {
                        "number": label,
                        "title": title,
                        "clauses": []
                    }
                
                elif divider_match:
                    if current_section:
                        self.metadata["sections"].append(current_section)
                    
                    is_in_section = True
                    title = self._clean_text(divider_match.group(1))
                    
                    current_section = {
                        "number": "",
                        "title": title,
                        "clauses": []
                    }
                    
                elif is_in_section and current_section and (clause_match or (is_bold and has_capital)):
                    if clause_match:
                        label = self._clean_text(clause_match.group(1))
                        clause_text = self._clean_text(clause_match.group(2)) if clause_match.group(2) else ""
                    else:
                        label = self._clean_text(first_span['text'])
                        label = re.sub(r'^["“”]+|["“”]+$', '', label)
                        remaining_text = "".join([span['text'] for span in first_line['spans'][1:]])
                        clause_text = self._clean_text(remaining_text)

                    if current_section:
                        current_section["clauses"].append({
                            "text": clause_text,
                            "label": label,
                            "index": len(current_section["clauses"])
                        })
                    
                elif not is_in_section:
                    preamble_text += " " + self._clean_text(block_text)
                
                elif is_in_section and current_section:
                    if not current_section["clauses"]:
                        # This is the start of the first clause, immediately following the section title
                        current_section["clauses"].append({
                            "text": self._clean_text(block_text),
                            "label": "",
                            "index": 0
                        })
                    elif "table_data" in current_section["clauses"][-1]:
                        # Do nothing if the last item was a table
                        continue
                    else:
                        # Append to the last clause
                        last_clause = current_section["clauses"][-1]
                        last_clause["text"] += " " + self._clean_text(block_text)


        if current_section:
            self.metadata["sections"].append(current_section)

        self.metadata["preamble"] = self._clean_text(preamble_text)
    
    def parse_document(self):
        """
        Orchestrates the parsing process.

        Returns:
            dict: The complete structured data of the document.
        """
        try:
            self.doc = fitz.open(self.pdf_path)
            
            self._extract_header_metadata()
            self._extract_effective_date()
            self._extract_content()
            
            return self.metadata
            
        except FileNotFoundError:
            print(f"Error: The file '{self.pdf_path}' was not found.")
            return None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None
        finally:
            if self.doc:
                self.doc.close()

def main():
    parser = argparse.ArgumentParser(description="Parses a contract PDF and outputs a structured JSON.")
    parser.add_argument("input_pdf", help="Path to the input PDF file.")
    parser.add_argument("output_json", help="Path to the output JSON file.")
    
    args = parser.parse_args()
    
    parser = PDFContractParser(args.input_pdf)
    final_output = parser.parse_document()
    
    if final_output:
        try:
            with open(args.output_json, 'w', encoding='utf-8') as f:
                json.dump(final_output, f, indent=2, ensure_ascii=False)
            
            print(f"Successfully parsed the document and saved to '{args.output_json}'.")
        except Exception as e:
            print(f"An error occurred while saving the JSON file: {e}")

if __name__ == "__main__":
    main()
