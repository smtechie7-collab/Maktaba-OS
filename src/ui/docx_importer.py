import os
import re

try:
    import docx
except ImportError:
    docx = None

def parse_import(text: str, metadata: dict) -> list:
    """
    Maktaba-OS Plugin: Microsoft Word (.docx) Parser
    Extracts paragraphs from binary Docx files and auto-maps them using Maktaba's Unicode heuristics.
    """
    file_path = metadata.get("file_path")
    
    if not file_path or not os.path.exists(file_path):
        raise ValueError("No valid Docx file provided. Please select a .docx file using the 'Browse File' button.")
        
    if not file_path.lower().endswith(".docx"):
        raise ValueError(f"Invalid file format. Expected .docx, got: {file_path}")
        
    if docx is None:
        raise ImportError("The 'python-docx' library is required to parse Word documents. Please run 'pip install python-docx'.")

    doc = docx.Document(file_path)
    blocks = []
    
    for para in doc.paragraphs:
        txt = para.text.strip()
        if not txt:
            continue
            
        block_data = {
            "ar": "", "ur": "", "guj": "", "en": "", 
            "reference": "", "metadata": metadata
        }
        
        # Smart language detection heuristic
        if re.search(r'[\u0a80-\u0aff]', txt):
            block_data["guj"] = txt
        elif re.search(r'^[a-zA-Z0-9\s.,!?\'"-]+$', txt):
            block_data["en"] = txt
        elif re.search(r'[\u0600-\u06ff]', txt):
            block_data["ar"] = txt
        else:
            block_data["ar"] = txt # Fallback
            
        blocks.append(block_data)
        
    return blocks