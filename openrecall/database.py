import sqlite3
from collections import namedtuple
import numpy as np
from typing import Any, List, Optional, Tuple
import re
import requests
import json
import base64
import os
import io
from PIL import Image

# ADD THIS LINE:
from openrecall.nlp import get_embedding

from openrecall.config import db_path

# Define the structure of a database entry using namedtuple
Entry = namedtuple("Entry", ["id", "app", "title", "text", "timestamp", "embedding"])


def create_db() -> None:
    """
    Creates the SQLite database and the 'entries' table if they don't exist.

    The table schema includes columns for an auto-incrementing ID, application name,
    window title, extracted text, timestamp, and text embedding.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS entries (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       app TEXT,
                       title TEXT,
                       text TEXT,
                       timestamp INTEGER UNIQUE,
                       embedding BLOB
                   )"""
            )
            # Add index on timestamp for faster lookups
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_timestamp ON entries (timestamp)"
            )
            conn.commit()
    except sqlite3.Error as e:
        print(f"Database error during table creation: {e}")


def get_all_entries() -> List[Entry]:
    """
    Retrieves all entries from the database.

    Returns:
        List[Entry]: A list of all entries as Entry namedtuples.
                     Returns an empty list if the table is empty or an error occurs.
    """
    entries: List[Entry] = []
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row  # Return rows as dictionary-like objects
            cursor = conn.cursor()
            cursor.execute("SELECT id, app, title, text, timestamp, embedding FROM entries ORDER BY timestamp DESC")
            results = cursor.fetchall()
            for row in results:
                # Deserialize the embedding blob back into a NumPy array
                embedding = np.frombuffer(row["embedding"], dtype=np.float32) # Assuming float32, adjust if needed
                entries.append(
                    Entry(
                        id=row["id"],
                        app=row["app"],
                        title=row["title"],
                        text=row["text"],
                        timestamp=row["timestamp"],
                        embedding=embedding,
                    )
                )
    except sqlite3.Error as e:
        print(f"Database error while fetching all entries: {e}")
    return entries


def get_timestamps() -> List[int]:
    """
    Retrieves all timestamps from the database, ordered descending.

    Returns:
        List[int]: A list of all timestamps.
                   Returns an empty list if the table is empty or an error occurs.
    """
    timestamps: List[int] = []
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # Use the index for potentially faster retrieval
            cursor.execute("SELECT timestamp FROM entries ORDER BY timestamp DESC")
            results = cursor.fetchall()
            timestamps = [result[0] for result in results]
    except sqlite3.Error as e:
        print(f"Database error while fetching timestamps: {e}")
    return timestamps

def clean_ocr_text(raw_text: str) -> str:
    """Clean up garbage OCR text"""
    if not raw_text:
        return ""
    
    # Remove OCR artifacts
    text = re.sub(r'[^\w\s\-.,!?;:()"\'/]', ' ', raw_text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'(\w)\1{3,}', r'\1\1', text)
    
    # Filter words
    words = text.split()
    cleaned_words = []
    
    for word in words:
        if len(word) < 2 or len(word) > 25:
            continue
        if word.isdigit() and len(word) > 10:
            continue
        if not any(c.isalpha() for c in word):
            continue
        cleaned_words.append(word)
    
    cleaned = ' '.join(cleaned_words).strip()
    return cleaned[:2000]


def is_text_low_quality(text: str) -> bool:
    """Check if text is too poor quality"""
    if not text or len(text) < 10:
        return True
    
    words = text.split()
    if len(words) < 3:
        return True
    
    letters = sum(1 for c in text if c.isalpha())
    letter_ratio = letters / len(text) if text else 0
    
    if letter_ratio < 0.3:
        return True
    
    short_words = sum(1 for word in words if len(word) <= 2)
    if short_words / len(words) > 0.7:
        return True
    
    return False


def get_vision_description(timestamp: int) -> Optional[str]:
    """Get vision model description via Ollama with improved image handling"""
    from openrecall.config import screenshots_path  # Import here to avoid circular imports
    
    # Find the screenshot file
    screenshot_path = os.path.join(screenshots_path, f"{timestamp}.webp")
    if not os.path.exists(screenshot_path):
        for ext in ['jpg', 'png', 'jpeg']:
            alt_path = os.path.join(screenshots_path, f"{timestamp}.{ext}")
            if os.path.exists(alt_path):
                screenshot_path = alt_path
                break
    
    if not os.path.exists(screenshot_path):
        return None
    
    try:
        # Convert image to compatible format and resize
        img = Image.open(screenshot_path)
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize if too large (vision models work better with smaller images)
        if img.width > 1024 or img.height > 1024:
            img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        
        # Convert to bytes as JPEG
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG', quality=85)
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
        
        # Call Ollama with llava:7b (more stable than 13b)
        response = requests.post('http://localhost:11434/api/generate', 
            json={
                "model": "llava:7b",
                "prompt": "Describe this screenshot concisely. What app/website is shown? What is the user doing? Any important text visible?",
                "images": [img_base64],
                "stream": False
            },
            timeout=60  # Increased timeout for vision processing
        )
        
        if response.status_code == 200:
            result = response.json()
            description = result.get('response', '').strip()
            if description:
                print(f"Vision model success: {description[:100]}...")
                return description
            
    except Exception as e:
        print(f"Vision model error: {e}")
        return None
    
    return None


def combine_text_sources(ocr_text: str, vision_text: str) -> str:
    """Combine OCR and vision descriptions"""
    if not ocr_text and not vision_text:
        return ""
    if not ocr_text:
        return vision_text
    if not vision_text:
        return ocr_text
    
    if len(ocr_text) > 50:
        return f"{ocr_text}\n\nContext: {vision_text}"
    else:
        return f"{vision_text}\n\nText: {ocr_text}"

# In database.py - REPLACE your enhanced insert_entry function
def insert_entry(
    raw_text: str, 
    timestamp: int, 
    embedding: np.ndarray, 
    app: str, 
    title: str
) -> Optional[int]:
    """Enhanced version that ALWAYS tries vision model first"""
    
    # Always try vision model first
    vision_description = get_vision_description(timestamp)
    
    if vision_description:
        # Use vision model output as primary text
        final_text = vision_description
        print(f"Using vision model description: {final_text[:100]}...")
    else:
        # Fallback to cleaned OCR if vision model fails
        final_text = clean_ocr_text(raw_text)
        print(f"Vision model failed, using OCR: {final_text[:100]}...")
    
    # Generate new embedding from the final text
    if final_text:
        final_embedding = get_embedding(final_text)
    else:
        final_embedding = embedding  # Use original if no text at all
    
    # Store with vision model text
    embedding_bytes = final_embedding.astype(np.float32).tobytes()
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO entries (text, timestamp, embedding, app, title)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(timestamp) DO NOTHING""",
                (final_text, timestamp, embedding_bytes, app, title)
            )
            conn.commit()
            return cursor.lastrowid if cursor.rowcount > 0 else None
    except sqlite3.Error as e:
        print(f"Database error during insertion: {e}")
        return None