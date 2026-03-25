import base64
from io import BytesIO
from typing import List, Optional
from pdf2image import convert_from_path
from PIL import Image

import hashlib
import json
import os
from test_platform.core.document_processing.document_reader import read_document, is_supported
from test_platform.core.document_processing.vision_analyzer import VisionAnalyzer, MockVisionAnalyzer
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
import time
import logging

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
CORE_LOGIC_VERSION = "v1.0"  # 当转图逻辑、质量参数变更时，更新此版本号以失效旧缓存

def _process_single_image(image, max_width):
    """Helper function to resize and encode a single image."""
    try:
        if image.width > max_width:
            aspect_ratio = image.height / image.width
            new_height = int(max_width * aspect_ratio)
            image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        buffered = BytesIO()
        image.save(buffered, format="JPEG", quality=95)
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"Error processing image: {e}")
        return None

def convert_pdf_to_base64_images(pdf_path: str, max_pages: int = 10, max_width: int = 2048) -> List[str]:
    """
    Convert PDF pages to base64 encoded JPEG images with caching, parallel processing, and memory-safe chunking.
    """
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)

    # 1. 组合缓存 Key (包含版本号以实现逻辑级别失效)
    file_hash = hashlib.md5(open(pdf_path, 'rb').read()).hexdigest()
    cache_key = f"{file_hash}_{CORE_LOGIC_VERSION}_{max_pages}_{max_width}.json"
    cache_path = os.path.join(CACHE_DIR, cache_key)

    if os.path.exists(cache_path):
        logger.info(f"📊 [Cache Hit] PDF Processor: {cache_key}")
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Cache load failed for {cache_path}: {e}")
            # If cache load fails, proceed to re-generate
    
    logger.info(f"📊 [Cache Miss] PDF Processor: {cache_key}")
    start_time = time.time()

    try:
        base64_images = []
        
        # Determine total pages to process
        # We can't easily get total pages without opening it, but we can iterate until no images return
        # Or just rely on max_pages if set.
        # Ideally, we should know the PDF page count, but pdf2image checks bounds.
        
        chunk_size = 5 # Process 5 pages at a time to keep RAM low
        current_page = 1
        total_limit = max_pages if max_pages > 0 else float('inf')
        
        print(f"📄 Converting PDF pages (Chunked Parallel)...")
        
        while current_page <= total_limit:
            # Calculate last page for this chunk
            chunk_last = min(current_page + chunk_size - 1, total_limit)
            if isinstance(total_limit, float): # unlimited
                 chunk_last = current_page + chunk_size - 1
            
            # Load chunk
            # print(f"  Processing pages {current_page}-{chunk_last}...")
            chunk_images = convert_from_path(pdf_path, first_page=current_page, last_page=chunk_last)
            
            if not chunk_images:
                break
                
            # Process chunk in parallel
            with ThreadPoolExecutor() as executor:
                process_func = partial(_process_single_image, max_width=max_width)
                results = executor.map(process_func, chunk_images)
                for res in results:
                    if res:
                        base64_images.append(res)
            
            # Update counters
            pages_read = len(chunk_images)
            current_page += pages_read
            
            # If we read fewer pages than requested, we reached the end
            if pages_read < chunk_size:
                break
                
            # Explicitly cleanup
            del chunk_images

        # 4. Save to Cache
        if base64_images:
            with open(cache_path, 'w') as f:
                json.dump(base64_images, f)
            logger.info(f"💾 Saved to cache: {cache_path}")
            
        # 7. Final Statistics
        total_time = time.time() - start_time
        if base64_images:
            logger.info(f"📊 [Performance] PDF processed {len(base64_images)} pages in {total_time:.2f}s (Avg: {total_time/len(base64_images):.2f}s/page)")
        else:
            logger.info(f"📊 [Performance] PDF processed 0 pages in {total_time:.2f}s")
        
        return base64_images
    except Exception as e:
        print(f"Error converting PDF to images: {e}")
        return []

if __name__ == "__main__":
    # Test
    # sys.argv[1] would be the pdf path
    import sys
    if len(sys.argv) > 1:
        res = convert_pdf_to_base64_images(sys.argv[1])
        print(f"Converted {len(res)} pages.")
