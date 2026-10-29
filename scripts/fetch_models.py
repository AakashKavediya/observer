#!/usr/bin/env python3
"""
scripts/fetch_models.py
Downloads the official MediaPipe Face Landmarker float16 model once at build time.
Verifies the SHA-256 hash to ensure integrity.
Runtime NEVER makes network requests or downloads models.
"""

import hashlib
import os
import sys
import urllib.request

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
EXPECTED_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
TARGET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine", "models")
TARGET_FILE = os.path.join(TARGET_DIR, "face_landmarker.task")


def calculate_sha256(filepath: str) -> str:
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def fetch_model():
    os.makedirs(TARGET_DIR, exist_ok=True)
    if os.path.exists(TARGET_FILE):
        current_hash = calculate_sha256(TARGET_FILE)
        if current_hash == EXPECTED_SHA256:
            print(f"[OK] Model already exists with verified SHA-256: {TARGET_FILE}")
            return True
        print(f"[WARN] Existing model hash mismatch ({current_hash} != {EXPECTED_SHA256}). Re-downloading...")

    print(f"Downloading MediaPipe Face Landmarker from {MODEL_URL}...")
    try:
        temp_file = TARGET_FILE + ".tmp"
        urllib.request.urlretrieve(MODEL_URL, temp_file)
        downloaded_hash = calculate_sha256(temp_file)
        if downloaded_hash != EXPECTED_SHA256:
            os.remove(temp_file)
            print(f"[ERROR] SHA-256 hash mismatch! Expected {EXPECTED_SHA256}, got {downloaded_hash}", file=sys.stderr)
            sys.exit(1)

        os.replace(temp_file, TARGET_FILE)
        print(f"[SUCCESS] Downloaded and verified model: {TARGET_FILE} ({os.path.getsize(TARGET_FILE)} bytes)")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to download model: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    fetch_model()
