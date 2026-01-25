import fitz  # PyMuPDF
from statistics import median, mean

def extract_text_from_pdf(filepath: str) -> str:
    """
    Extracts text from a PDF file with structural awareness.
    Identifies titles (larger font), body text (normal font), and footnotes (smaller font).
    Returns formatted text with markers for Claude to understand the structure.
    """
    doc = fitz.open(filepath)
    
    # First pass: collect all font sizes to determine thresholds
    all_font_sizes = []
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        size = span["size"]
                        if size > 0:
                            all_font_sizes.append(size)
    
    if not all_font_sizes:
        # Fallback to simple extraction if no font info
        doc.close()
        doc = fitz.open(filepath)
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    
    # Calculate thresholds
    median_size = median(all_font_sizes)
    # Titles are typically 20%+ larger than body text
    title_threshold = median_size * 1.2
    # Footnotes are typically 80% or less of body text
    footnote_threshold = median_size * 0.85
    
    # Second pass: extract with structure markers
    structured_text = []
    
    for page_num, page in enumerate(doc):
        page_height = page.rect.height
        blocks = page.get_text("dict")["blocks"]
        
        for block in blocks:
            if "lines" not in block:
                continue
                
            block_text = []
            block_type = "body"  # default
            avg_font_size = 0
            span_count = 0
            
            # Get vertical position (y coordinate)
            block_y = block.get("bbox", [0, 0, 0, 0])[1]  # top y coordinate
            is_bottom_of_page = block_y > page_height * 0.85
            
            for line in block["lines"]:
                line_text = ""
                for span in line["spans"]:
                    line_text += span["text"]
                    avg_font_size += span["size"]
                    span_count += 1
                block_text.append(line_text)
            
            if span_count > 0:
                avg_font_size /= span_count
            
            # Determine block type
            if avg_font_size >= title_threshold:
                block_type = "title"
            elif avg_font_size <= footnote_threshold or is_bottom_of_page:
                block_type = "footnote"
            else:
                block_type = "body"
            
            # Format the block with markers
            text_content = " ".join(block_text).strip()
            if not text_content:
                continue
                
            if block_type == "title":
                structured_text.append(f"\n## {text_content}\n")
            elif block_type == "footnote":
                structured_text.append(f"[Note: {text_content}]")
            else:
                structured_text.append(text_content)
    
    doc.close()
    return "\n".join(structured_text)


def extract_text_simple(filepath: str) -> str:
    """Simple text extraction fallback."""
    doc = fitz.open(filepath)
    text = ""
    for page in doc:
        text += page.get_text()
    return text
