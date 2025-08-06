import os
import time
from typing import List, Tuple

import mss
import numpy as np
from PIL import Image

from openrecall.config import screenshots_path, args
from openrecall.database import insert_entry
from openrecall.nlp import get_embedding
from openrecall.ocr import extract_text_from_image
from openrecall.utils import (
    get_active_app_name,
    get_active_window_title,
    is_user_active,
)

# Import the recording controller
from openrecall.recording_controller import recording_controller

def mean_structured_similarity_index(
    img1: np.ndarray, img2: np.ndarray, L: int = 255
) -> float:
    """Calculates the Mean Structural Similarity Index (MSSIM) between two images."""
    K1, K2 = 0.01, 0.03
    C1, C2 = (K1 * L) ** 2, (K2 * L) ** 2

    def rgb2gray(img: np.ndarray) -> np.ndarray:
        """Converts an RGB image to grayscale."""
        return 0.2989 * img[..., 0] + 0.5870 * img[..., 1] + 0.1140 * img[..., 2]

    img1_gray: np.ndarray = rgb2gray(img1)
    img2_gray: np.ndarray = rgb2gray(img2)
    mu1: float = np.mean(img1_gray)
    mu2: float = np.mean(img2_gray)
    sigma1_sq = np.var(img1_gray)
    sigma2_sq = np.var(img2_gray)
    sigma12 = np.mean((img1_gray - mu1) * (img2_gray - mu2))
    ssim_index = ((2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)) / (
        (mu1**2 + mu2**2 + C1) * (sigma1_sq + sigma2_sq + C2)
    )
    return ssim_index

def is_similar(
    img1: np.ndarray, img2: np.ndarray, similarity_threshold: float = 0.9
) -> bool:
    """Checks if two images are similar based on MSSIM."""
    similarity: float = mean_structured_similarity_index(img1, img2)
    return similarity >= similarity_threshold

def take_screenshots() -> List[np.ndarray]:
    """Takes screenshots of all connected monitors or just the primary one."""
    screenshots: List[np.ndarray] = []
    with mss.mss() as sct:
        monitor_indices = range(1, len(sct.monitors))
        if args.primary_monitor_only:
            monitor_indices = [1]

        for i in monitor_indices:
            if i < len(sct.monitors):
                monitor_info = sct.monitors[i]
                sct_img = sct.grab(monitor_info)
                screenshot = np.array(sct_img)[:, :, [2, 1, 0]]
                screenshots.append(screenshot)
            else:
                print(f"Warning: Monitor index {i} out of bounds. Skipping.")
    return screenshots

def record_screenshots_thread():
    """
    MAIN RECORDING LOOP with pause/resume support
    """
    import os
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    print("[SCREENSHOT THREAD] Starting with pause/resume support")
    last_screenshots = None

    while True:
        try:
            # === CRITICAL PAUSE CHECK ===
            if recording_controller.is_paused:
                print("[SCREENSHOT THREAD] *** PAUSED - WAITING ***")
                if not recording_controller.wait_if_paused():
                    print("[SCREENSHOT THREAD] Stop signal received, exiting")
                    break
                print("[SCREENSHOT THREAD] *** RESUMED ***")
                continue

            # === STOP CHECK ===
            if not recording_controller.should_record():
                print("[SCREENSHOT THREAD] Should not record, waiting...")
                time.sleep(1)
                continue

            # === USER ACTIVITY CHECK ===
            if not is_user_active():
                print("[SCREENSHOT THREAD] User inactive, waiting...")
                time.sleep(3)
                continue

            # === TAKE SCREENSHOTS ===
            print("[SCREENSHOT THREAD] Taking screenshots...")
            screenshots = take_screenshots()

            if last_screenshots is None or len(last_screenshots) != len(screenshots):
                print("[SCREENSHOT THREAD] Initializing screenshot comparison")
                last_screenshots = screenshots
                time.sleep(3)
                continue

            # === PROCESS SCREENSHOTS ===
            for i, screenshot in enumerate(screenshots):
                # Check pause state before each screenshot
                if recording_controller.is_paused:
                    print("[SCREENSHOT THREAD] Paused during processing, breaking")
                    break
                    
                if i < len(last_screenshots):
                    last_screenshot = last_screenshots[i]

                    if not is_similar(screenshot, last_screenshot):
                        print(f"[SCREENSHOT THREAD] Screenshot {i} changed, processing...")
                        last_screenshots[i] = screenshot
                        
                        # Save image
                        image = Image.fromarray(screenshot)
                        timestamp = int(time.time())
                        filename = f"{timestamp}_{i}.webp"
                        filepath = os.path.join(screenshots_path, filename)
                        image.save(filepath, format="webp", lossless=True)
                        
                        # Extract text and save to database
                        text: str = extract_text_from_image(screenshot)
                        if text.strip():
                            embedding: np.ndarray = get_embedding(text)
                            active_app_name: str = get_active_app_name() or "Unknown App"
                            active_window_title: str = get_active_window_title() or "Unknown Title"
                            insert_entry(text, timestamp, embedding, active_app_name, active_window_title)
                            print(f"[SCREENSHOT THREAD] Processed screenshot for {active_app_name}")
                    else:
                        print(f"[SCREENSHOT THREAD] Screenshot {i} unchanged, skipping")

            # Wait before next iteration
            time.sleep(3)

        except Exception as e:
            print(f"[SCREENSHOT THREAD] ERROR: {e}")
            time.sleep(5)

    print("[SCREENSHOT THREAD] Exiting")
