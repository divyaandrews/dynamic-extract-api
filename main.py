from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re
import json
from typing import Any, Dict, Optional
from datetime import datetime

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class DynamicExtractRequest(BaseModel):
    text: str
    schema: Dict[str, str]

# --- SPECIFIC EXTRACTION FOR COMMON FIELDS ---
def extract_property_type(text: str) -> Optional[str]:
    """Extract property type specifically"""
    patterns = [
        r'property_type[:.\s]+([^\n,]+)',
        r'type[:.\s]+([^\n,]+)',
        r'(\d+BHK\s+flat)',
        r'(\d+BHK)',
        r'(flat|apartment|villa|house)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None

# --- IMPROVED EXTRACTION FUNCTIONS ---
def extract_string(text: str, field_name: str) -> Optional[str]:
    """Extract a string from text for a specific field"""
    # Handle special field names
    if field_name == "property_type":
        return extract_property_type(text)
    
    patterns = [
        rf'{field_name}[:.\s]+([^\n,]+)',
        rf'{field_name}\s+is\s+([^\n,]+)',
        r'([^\n,]+)',  # Fallback - but only if we're sure
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if len(value) > 1 and len(value) < 100:
                return value
    return None

def extract_integer(text: str, field_name: str) -> Optional[int]:
    """Extract an integer from text"""
    patterns = [
        rf'{field_name}[:.\s]+(\d+)',
        r'(\d+)',
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
    ]
    
    for pattern, date_format in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                dt = datetime.strptime(match.group(1), date_format)
                return dt.strftime('%Y-%m-%d')
            except:
                continue
    return None

def extract_array(text: str, field_name: str, item_type: str) -> Optional[list]:
    """Extract an array from text"""
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
    
    if field_type.startswith('array['):
        item_type = field_type[6:-1]
        return extract_array(text, field_name, item_type)
    
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

@app.post("/dynamic-extract")
async def dynamic_extract(request: DynamicExtractRequest):
    text = request.text
    schema = request.schema
    
    result = {}
    
    for field_name, field_type in schema.items():
        value = extract_field(text, field_name, field_type)
        
        # Type conversion
        if field_type == 'integer' and isinstance(value, float):
            value = int(value)
        elif field_type == 'float' and isinstance(value, int):
            value = float(value)
        
        result[field_name] = value
    
    return result

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