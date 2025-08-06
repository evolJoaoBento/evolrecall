#!/usr/bin/env python3
"""
OpenRecall Simple Optimized Reprocessor

Focuses on the biggest performance gains with minimal complexity:
1. Concurrent processing with thread pools
2. Batch database operations 
3. Smart filtering and caching
4. Reduced timeouts and better error handling

Much simpler than the async version but should give 80% of the benefits.
"""

import sqlite3
import os
import base64
import requests
import json
from PIL import Image
import io
import numpy as np
from typing import Optional, List, Tuple, Dict, Set
import time
import argparse
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from dataclasses import dataclass
import pickle
from functools import lru_cache
import logging

# Configuration
DB_PATH = r"C:\Users\joaoo\openrecall\recall.db"
SCREENSHOTS_PATH = r"C:\Users\joaoo\openrecall\screenshots"
VISION_MODEL = "llava:7b"
INTERPRETATION_MODEL = "llama3.1:8b"
OLLAMA_URL = "http://localhost:11434/api/generate"

# Simple optimization settings
MAX_WORKERS = 4           # Number of concurrent threads
BATCH_SIZE = 20           # Database batch size
CHECKPOINT_INTERVAL = 100 # Save progress every N entries
CACHE_FILE = "simple_processing_cache.pkl"

# Reduced timeouts to prevent hanging
VISION_TIMEOUT = 30
LLM_TIMEOUT = 20
CONNECTION_TIMEOUT = 5

# Setup logging without Unicode characters
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("simple_reprocessor.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ProcessingResult:
    entry_id: int
    success: bool
    enhanced_text: Optional[str] = None
    embedding: Optional[np.ndarray] = None
    error: Optional[str] = None
    processing_time: float = 0.0
    had_screenshot: bool = False

class SimpleProcessingCache:
    """Simple cache for processed entries"""
    def __init__(self, cache_file: str = CACHE_FILE):
        self.cache_file = cache_file
        self.processed_ids: Set[int] = set()
        self.lock = threading.Lock()
        self.load_cache()
    
    def load_cache(self):
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'rb') as f:
                    self.processed_ids = pickle.load(f)
                logger.info(f"Loaded {len(self.processed_ids)} processed IDs from cache")
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            self.processed_ids = set()
    
    def save_cache(self):
        try:
            with self.lock:
                with open(self.cache_file, 'wb') as f:
                    pickle.dump(self.processed_ids, f)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def is_processed(self, entry_id: int) -> bool:
        with self.lock:
            return entry_id in self.processed_ids
    
    def mark_processed(self, entry_id: int):
        with self.lock:
            self.processed_ids.add(entry_id)

class SimpleOptimizedProcessor:
    def __init__(self):
        self.cache = SimpleProcessingCache()
        self.embedding_model = None
        self.session_local = threading.local()
        self._load_embedding_model()
    
    def _load_embedding_model(self):
        """Load embedding model once"""
        try:
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("[OK] Embedding model loaded")
        except ImportError:
            logger.warning("sentence-transformers not available, using dummy embeddings")
            self.embedding_model = None
    
    def get_requests_session(self):
        """Get thread-local requests session"""
        if not hasattr(self.session_local, 'session'):
            self.session_local.session = requests.Session()
            self.session_local.session.headers.update({'Content-Type': 'application/json'})
        return self.session_local.session
    
    @lru_cache(maxsize=1000)
    def clean_ocr_text(self, raw_text: str) -> str:
        """Clean OCR text (cached)"""
        if not raw_text:
            return ""
        
        # Simple cleaning - same as original
        text = re.sub(r'[^\w\s\-.,!?;:()"\'/]', ' ', raw_text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'(\w)\1{3,}', r'\1\1', text)
        
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
        return cleaned[:1000]
    
    def is_already_refined(self, text: str) -> bool:
        """Quick check if already refined"""
        if not text:
            return False
        
        text_lower = text.lower()
        indicators = [
            "enhanced description:",
            "activity/task:",
            "the user is working",
            "**activity",
        ]
        
        return any(indicator in text_lower for indicator in indicators)
    
    @lru_cache(maxsize=500)
    def find_screenshot_file(self, timestamp: int) -> Optional[str]:
        """Find screenshot file (cached)"""
        candidates = [
            f"{timestamp}.webp", f"{timestamp}.jpg", f"{timestamp}.png",
            f"{timestamp}.jpeg", f"{timestamp}_0.webp", f"{timestamp}_0.jpg",
        ]
        
        for candidate in candidates:
            path = os.path.join(SCREENSHOTS_PATH, candidate)
            if os.path.exists(path):
                return path
        return None
    
    def get_vision_description(self, screenshot_path: str) -> Optional[str]:
        """Get vision description with shorter timeout"""
        if not os.path.exists(screenshot_path):
            return None
        
        try:
            # Load and convert image
            img = Image.open(screenshot_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            if img.width > 1024 or img.height > 1024:
                img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='JPEG', quality=85)
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            
            session = self.get_requests_session()
            response = session.post(OLLAMA_URL, 
                json={
                    "model": VISION_MODEL,
                    "prompt": "Describe this screenshot briefly. What application is shown and what is the user doing?",
                    "images": [img_base64],
                    "stream": False
                },
                timeout=VISION_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                description = result.get('response', '').strip()
                return description if description else None
            else:
                return None
                
        except Exception:
            return None
    
    def get_llm_interpretation(self, vision_text: Optional[str], ocr_text: str, 
                              app_name: str, title: str) -> Optional[str]:
        """Get LLM interpretation with shorter timeout and simpler prompt"""
        
        # Simpler, shorter prompt to reduce processing time
        if vision_text:
            prompt = f"""Combine this information into a clear description:

App: {app_name}
Visual: {vision_text}
Text: {ocr_text}

Create a concise description of what the user is doing:"""
        else:
            prompt = f"""Create a clear description:

App: {app_name}
Content: {ocr_text}

Describe what the user is doing:"""
        
        try:
            session = self.get_requests_session()
            response = session.post(OLLAMA_URL,
                json={
                    "model": INTERPRETATION_MODEL,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=LLM_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                interpretation = result.get('response', '').strip()
                return interpretation if interpretation else None
            else:
                return None
                
        except Exception:
            return None
    
    def process_single_entry(self, entry_data: Tuple[int, str, int, str, str]) -> ProcessingResult:
        """Process a single entry"""
        start_time = time.time()
        entry_id, current_text, timestamp, app_name, title = entry_data
        
        try:
            # Find screenshot
            screenshot_path = self.find_screenshot_file(timestamp)
            had_screenshot = screenshot_path is not None
            
            # Clean OCR text
            cleaned_ocr = self.clean_ocr_text(current_text)
            
            # Get vision description (if screenshot exists)
            vision_text = None
            if screenshot_path:
                vision_text = self.get_vision_description(screenshot_path)
            
            # Get LLM interpretation
            enhanced_text = self.get_llm_interpretation(vision_text, cleaned_ocr, app_name, title)
            
            # Fallback if LLM fails
            if not enhanced_text:
                if vision_text:
                    enhanced_text = vision_text
                else:
                    enhanced_text = cleaned_ocr
            
            processing_time = time.time() - start_time
            
            return ProcessingResult(
                entry_id=entry_id,
                success=True,
                enhanced_text=enhanced_text,
                processing_time=processing_time,
                had_screenshot=had_screenshot
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            return ProcessingResult(
                entry_id=entry_id,
                success=False,
                error=str(e),
                processing_time=processing_time
            )
    
    def get_embedding_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings in batch"""
        if self.embedding_model:
            embeddings = self.embedding_model.encode(texts)
            return [emb.astype(np.float32) for emb in embeddings]
        else:
            return [np.random.rand(384).astype(np.float32) for _ in texts]
    
    def update_database_batch(self, results: List[ProcessingResult], dry_run: bool = False) -> int:
        """Update database in batch"""
        if dry_run:
            return len([r for r in results if r.success])
        
        successful_results = [r for r in results if r.success and r.enhanced_text]
        if not successful_results:
            return 0
        
        # Generate embeddings in batch
        texts = [r.enhanced_text for r in successful_results]
        embeddings = self.get_embedding_batch(texts)
        
        # Update database
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                update_data = []
                
                for result, embedding in zip(successful_results, embeddings):
                    embedding_bytes = embedding.tobytes()
                    update_data.append((result.enhanced_text, embedding_bytes, result.entry_id))
                
                cursor.executemany(
                    "UPDATE entries SET text = ?, embedding = ? WHERE id = ?",
                    update_data
                )
                conn.commit()
                
                # Mark as processed in cache
                for result in successful_results:
                    self.cache.mark_processed(result.entry_id)
                
                return len(successful_results)
                
        except sqlite3.Error as e:
            logger.error(f"Database batch update error: {e}")
            return 0
    
    def get_entries_to_process(self, force_reprocess: bool = False) -> List[Tuple[int, str, int, str, str]]:
        """Get entries that need processing"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, text, timestamp, app, title FROM entries ORDER BY timestamp DESC")
                all_entries = cursor.fetchall()
            
            if force_reprocess:
                return all_entries
            
            # Filter entries
            filtered_entries = []
            for entry in all_entries:
                entry_id, current_text, timestamp, app_name, title = entry
                
                if self.cache.is_processed(entry_id):
                    continue
                
                if self.is_already_refined(current_text):
                    self.cache.mark_processed(entry_id)
                    continue
                
                filtered_entries.append(entry)
            
            logger.info(f"Filtered {len(filtered_entries)} entries for processing (from {len(all_entries)} total)")
            return filtered_entries
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return []
    
    def run_processing(self, dry_run: bool = False, limit: Optional[int] = None, 
                      force_reprocess: bool = False):
        """Main processing with thread pool"""
        logger.info("Starting simple optimized reprocessing...")
        
        # Test Ollama connection
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=CONNECTION_TIMEOUT)
            if response.status_code != 200:
                logger.error("Cannot connect to Ollama. Make sure it's running.")
                return
            logger.info("[OK] Ollama connection successful")
        except Exception as e:
            logger.error(f"Error connecting to Ollama: {e}")
            return
        
        # Get entries to process
        entries = self.get_entries_to_process(force_reprocess)
        if limit:
            entries = entries[:limit]
        
        if not entries:
            logger.info("No entries to process")
            return
        
        logger.info(f"Processing {len(entries)} entries with {MAX_WORKERS} workers")
        
        total_updated = 0
        total_errors = 0
        start_time = time.time()
        
        # Process with thread pool
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all tasks
            future_to_entry = {executor.submit(self.process_single_entry, entry): entry for entry in entries}
            
            completed = 0
            results_batch = []
            
            for future in as_completed(future_to_entry):
                try:
                    result = future.result()
                    results_batch.append(result)
                    completed += 1
                    
                    # Log progress every 50 entries
                    if completed % 50 == 0:
                        logger.info(f"Progress: {completed}/{len(entries)} entries processed")
                    
                    # Process batch when full
                    if len(results_batch) >= BATCH_SIZE:
                        updated_count = self.update_database_batch(results_batch, dry_run)
                        total_updated += updated_count
                        
                        error_count = len([r for r in results_batch if not r.success])
                        total_errors += error_count
                        
                        # Show batch stats
                        avg_time = np.mean([r.processing_time for r in results_batch])
                        screenshot_count = len([r for r in results_batch if r.had_screenshot])
                        logger.info(f"Batch: {updated_count} updated, {error_count} errors, {avg_time:.1f}s avg, {screenshot_count} had screenshots")
                        
                        results_batch = []
                    
                    # Save checkpoint
                    if completed % CHECKPOINT_INTERVAL == 0:
                        self.cache.save_cache()
                        logger.info(f"Checkpoint saved at {completed} entries")
                        
                except Exception as e:
                    logger.error(f"Error processing entry: {e}")
                    total_errors += 1
            
            # Process final batch
            if results_batch:
                updated_count = self.update_database_batch(results_batch, dry_run)
                total_updated += updated_count
                error_count = len([r for r in results_batch if not r.success])
                total_errors += error_count
        
        # Final results
        total_time = time.time() - start_time
        logger.info("=" * 60)
        logger.info("FINAL SUMMARY:")
        logger.info(f"Total processed: {len(entries)}")
        logger.info(f"Successfully updated: {total_updated}")
        logger.info(f"Errors: {total_errors}")
        logger.info(f"Total time: {total_time:.1f}s")
        logger.info(f"Avg time per entry: {total_time/len(entries):.2f}s")
        logger.info("=" * 60)
        
        # Save final cache
        self.cache.save_cache()

def main():
    parser = argparse.ArgumentParser(description="Simple optimized reprocessor")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without making changes")
    parser.add_argument("--limit", type=int, help="Limit number of entries to process")
    parser.add_argument("--force", action="store_true", help="Reprocess all entries")
    parser.add_argument("--clear-cache", action="store_true", help="Clear processing cache")
    
    args = parser.parse_args()
    
    # Verify paths
    if not os.path.exists(DB_PATH):
        logger.error(f"Database not found at {DB_PATH}")
        return
    
    if not os.path.exists(SCREENSHOTS_PATH):
        logger.error(f"Screenshots directory not found at {SCREENSHOTS_PATH}")
        return
    
    # Clear cache if requested
    if args.clear_cache:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            logger.info("Processing cache cleared")
    
    # Run processing
    processor = SimpleOptimizedProcessor()
    processor.run_processing(
        dry_run=args.dry_run,
        limit=args.limit,
        force_reprocess=args.force
    )

if __name__ == "__main__":
    main()