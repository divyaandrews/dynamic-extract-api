from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re
import json
from typing import Any, Dict, Optional, List
from datetime import datetime

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
    schema: Dict[str, str]

# --- SMART EXTRACTION FUNCTIONS ---

def smart_extract_string(text: str, field_name: str) -> Optional[str]:
    """Smart string extraction for any field"""
    
    # Pattern 1: field_name: value
    pattern1 = rf'{field_name}[:.\s]+([^\n,.;]+)'
    match = re.search(pattern1, text, re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        if len(value) > 1:
            return value
    
    # Pattern 2: value is the field_name
    pattern2 = rf'([^\n,.;]+)\s+{field_name}'
    match = re.search(pattern2, text, re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        if len(value) > 1:
            return value
    
    # Pattern 3: Common values for specific fields
    common_values = {
        'property_type': r'(\d+BHK\s+(?:flat|apartment|house|villa))',
        'status': r'(available|sold|rented|listed)',
        'type': r'(residential|commercial|industrial)',
    }
    
    if field_name in common_values:
        match = re.search(common_values[field_name], text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None

def smart_extract_number(text: str, field_name: str, is_float: bool = False) -> Optional[Any]:
    """Smart number extraction (integer or float)"""
    
    # Pattern 1: field_name: number
    pattern1 = rf'{field_name}[:.\s]+([\d,]+\.?\d*)'
    match = re.search(pattern1, text, re.IGNORECASE)
    if match:
        try:
            num_str = match.group(1).replace(',', '')
            return float(num_str) if is_float else int(float(num_str))
        except:
            pass
    
    # Pattern 2: number is the field_name
    pattern2 = rf'([\d,]+\.?\d*)\s+{field_name}'
    match = re.search(pattern2, text, re.IGNORECASE)
    if match:
        try:
            num_str = match.group(1).replace(',', '')
            return float(num_str) if is_float else int(float(num_str))
        except:
            pass
    
    # Pattern 3: Just find any number
    numbers = re.findall(r'([\d,]+\.?\d*)', text)
    for num in numbers:
        try:
            clean_num = num.replace(',', '')
            if is_float:
                return float(clean_num)
            else:
                return int(float(clean_num))
        except:
            continue
    
    return None

def smart_extract_date(text: str, field_name: str) -> Optional[str]:
    """Smart date extraction with ISO format"""
    
    date_patterns = [
        # YYYY-MM-DD
        (r'(\d{4}-\d{2}-\d{2})', '%Y-%m-%d'),
        # DD/MM/YYYY or MM/DD/YYYY
        (r'(\d{2}/\d{2}/\d{4})', None),
        # DD Month YYYY
        (r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})', None),
        # Month DD, YYYY
        (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{4})', None),
        # DD-Month-YYYY
        (r'(\d{1,2})-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-(\d{4})', None),
    ]
    
    for pattern, date_format in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                if date_format:
                    dt = datetime.strptime(match.group(1), date_format)
                else:
                    # Handle various formats
                    groups = match.groups()
                    if len(groups) == 3:
                        if groups[0].isdigit():  # Day first
                            day = int(groups[0])
                            month_str = groups[1]
                            year = int(groups[2])
                        else:  # Month first
                            month_str = groups[0]
                            day = int(groups[1])
                            year = int(groups[2])
                        
                        month_map = {
                            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4,
                            'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8,
                            'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
                        }
                        month = month_map.get(month_str, 1)
                        dt = datetime(year, month, day)
                    else:
                        continue
                
                return dt.strftime('%Y-%m-%d')
            except:
                continue
    
    return None

def smart_extract_boolean(text: str, field_name: str) -> Optional[bool]:
    """Smart boolean extraction"""
    true_patterns = [
        rf'{field_name}[:.\s]+(True|true|Yes|yes|Y|y|1|true)',
        r'(True|true|Yes|yes|Y|y|1)'
    ]
    false_patterns = [
        rf'{field_name}[:.\s]+(False|false|No|no|N|n|0|false)',
        r'(False|false|No|no|N|n|0)'
    ]
    
    for pattern in true_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    for pattern in false_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return False
    
    return None

def smart_extract_array(text: str, field_name: str, item_type: str) -> Optional[List]:
    """Smart array extraction"""
    
    patterns = [
        rf'{field_name}[:.\s]+([^\n]+)',
        r'\[([^\]]+)\]',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            items = [item.strip() for item in match.group(1).split(',') if item.strip()]
            
            if item_type == 'string':
                return [str(item) for item in items]
            elif item_type == 'integer':
                try:
                    return [int(item) for item in items]
                except:
                    continue
            elif item_type == 'float':
                try:
                    return [float(item) for item in items]
                except:
                    continue
    
    return None

# --- MAIN EXTRACTION FUNCTION ---
def extract_field(text: str, field_name: str, field_type: str) -> Any:
    """Main extraction function that dispatches to specific extractors"""
    
    # Handle array types
    if field_type.startswith('array['):
        item_type = field_type[6:-1]  # Extract type inside array[]
        return smart_extract_array(text, field_name, item_type)
    
    # Handle single types
    if field_type == 'string':
        return smart_extract_string(text, field_name)
    elif field_type == 'integer':
        return smart_extract_number(text, field_name, is_float=False)
    elif field_type == 'float':
        return smart_extract_number(text, field_name, is_float=True)
    elif field_type == 'boolean':
        return smart_extract_boolean(text, field_name)
    elif field_type == 'date':
        return smart_extract_date(text, field_name)
    
    return None

# --- THE MAIN ENDPOINT ---
@app.post("/dynamic-extract")
async def dynamic_extract(request: DynamicExtractRequest):
    text = request.text
    schema = request.schema
    
    result = {}
    
    for field_name, field_type in schema.items():
        # Extract the value
        value = extract_field(text, field_name, field_type)
        
        # If value is None, keep it as None (JSON null)
        result[field_name] = value
    
    return result

# --- HOMEPAGE ---
@app.get("/")
async def root():
    return {
        "message": "Dynamic Schema Extraction API",
        "endpoint": "POST /dynamic-extract",
        "supported_types": ["string", "integer", "float", "boolean", "date", "array[string]", "array[integer]"],
        "example": {
            "text": "Rahul bought 3 notebooks for Rs. 240 on 12 June 2026 from Alpha Store.",
            "schema": {
                "customer_name": "string",
                "quantity": "integer",
                "amount": "float",
                "purchase_date": "date"
            }
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)