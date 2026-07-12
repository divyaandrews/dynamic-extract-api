from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import re
from datetime import datetime
from typing import Any, Dict, Optional

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REQUEST/RESPONSE MODELS ---
class DynamicExtractRequest(BaseModel):
    text: str
    schema: Dict[str, str]  # field_name -> type

class DynamicExtractResponse(BaseModel):
    pass  # Dynamic, will be created per request

# --- EXTRACTION FUNCTIONS ---
def extract_integer(text: str, field_name: str) -> Optional[int]:
    """Extract an integer from text"""
    patterns = [
        rf'{field_name}[:.\s]+(\d+)',
        rf'(\d+)\s+{field_name}',
        r'(\d+)',  # Fallback: just find any number
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except:
                continue
    return None

def extract_float(text: str, field_name: str) -> Optional[float]:
    """Extract a float from text"""
    patterns = [
        rf'{field_name}[:.\s]+([\d,]+\.?\d*)',
        r'([\d,]+\.\d{2})',
        r'([\d,]+\.?\d*)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                amount_str = match.group(1).replace(',', '')
                return float(amount_str)
            except:
                continue
    return None

def extract_string(text: str, field_name: str) -> Optional[str]:
    """Extract a string from text"""
    patterns = [
        rf'{field_name}[:.\s]+([^\n,]+)',
        r'([A-Za-z][A-Za-z\s]+)',  # Any word-like text
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if len(value) > 1:
                return value
    return None

def extract_boolean(text: str, field_name: str) -> Optional[bool]:
    """Extract a boolean from text"""
    if re.search(rf'{field_name}[:.\s]+(True|true|Yes|yes|1)', text):
        return True
    if re.search(rf'{field_name}[:.\s]+(False|false|No|no|0)', text):
        return False
    return None

def extract_date(text: str, field_name: str) -> Optional[str]:
    """Extract and convert date to ISO format"""
    date_patterns = [
        (r'(\d{4}-\d{2}-\d{2})', '%Y-%m-%d'),
        (r'(\d{2}/\d{2}/\d{4})', '%m/%d/%Y'),
        (r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})', '%d %b %Y'),
        (r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})', '%d %B %Y'),
        (r'(\d{1,2})(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})', None),  # "3rd March 2026"
    ]
    
    for pattern, date_format in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                if date_format:
                    dt = datetime.strptime(match.group(1), date_format)
                else:
                    # Handle "3rd March 2026" format
                    day = re.search(r'(\d{1,2})', match.group(1))
                    month = match.group(2)
                    year = match.group(3)
                    if day and month and year:
                        dt = datetime.strptime(f"{day.group(1)} {month} {year}", "%d %B %Y")
                return dt.strftime('%Y-%m-%d')
            except:
                continue
    return None

def extract_array(text: str, field_name: str, item_type: str) -> Optional[list]:
    """Extract an array from text"""
    # Look for patterns like: "items: A, B, C" or "[A, B, C]"
    patterns = [
        rf'{field_name}[:.\s]+([^\n]+)',
        r'\[([^\]]+)\]',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            items = [item.strip() for item in match.group(1).split(',')]
            if item_type == "string":
                return [str(item) for item in items if item]
            elif item_type == "integer":
                try:
                    return [int(item) for item in items if item]
                except:
                    continue
    return None

# --- MAIN EXTRACTION FUNCTION ---
def extract_field(text: str, field_name: str, field_type: str) -> Any:
    """Extract a field based on its type"""
    
    # Handle array types
    if field_type.startswith('array['):
        item_type = field_type[6:-1]  # Extract type inside array[type]
        return extract_array(text, field_name, item_type)
    
    # Handle single types
    type_handlers = {
        'string': extract_string,
        'integer': extract_integer,
        'float': extract_float,
        'boolean': extract_boolean,
        'date': extract_date,
    }
    
    handler = type_handlers.get(field_type)
    if handler:
        return handler(text, field_name)
    
    return None

# --- MAIN ENDPOINT ---
@app.post("/dynamic-extract")
async def dynamic_extract(request: DynamicExtractRequest):
    text = request.text
    schema = request.schema
    
    result = {}
    
    for field_name, field_type in schema.items():
        # Extract the field
        value = extract_field(text, field_name, field_type)
        
        # Type conversion for numeric values
        if field_type == 'integer' and isinstance(value, float):
            value = int(value)
        elif field_type == 'float' and isinstance(value, int):
            value = float(value)
        
        result[field_name] = value
    
    return result

# --- HOMEPAGE ---
@app.get("/")
async def root():
    return {
        "message": "Dynamic Schema Extraction API",
        "endpoint": "POST /dynamic-extract",
        "supported_types": ["string", "integer", "float", "boolean", "date", "array[string]", "array[integer]"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)