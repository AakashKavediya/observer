"""
observer_engine.landmarks
Wraps MediaPipe Face Landmarker (Task API) with iris tracking and blendshapes enabled.
Loads exclusively from the bundled engine/models/face_landmarker.task model.
Zero downloads at runtime. Tracks the single largest face in frame.
Frames are discarded immediately following landmark extraction.
"""

import os
import sys
import time
from typing import Optional, List, Dict, Any, Tuple
import numpy as np
import cv2

try:
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import (
        FaceLandmarker,
        FaceLandmarkerOptions,
        FaceLandmarkerResult,
        RunningMode,
    )
    _MEDIAPIPE_AVAILABLE = True
except Exception as e:
    _MEDIAPIPE_AVAILABLE = False
    _MEDIAPIPE_IMPORT_ERROR = str(e)


class FaceLandmarksResult:
    def __init__(
        self,
        landmarks: np.ndarray,  # Shape (478, 3) normalized x, y, z
        blendshapes: Dict[str, float],
        box_area: float,
    ):
        self.landmarks = landmarks
        self.blendshapes = blendshapes
        self.box_area = box_area


class FaceLandmarkerWrapper:
    def __init__(self, model_path: Optional[str] = None):
        if not _MEDIAPIPE_AVAILABLE:
            raise RuntimeError(
                f"MediaPipe vision package is unavailable: {_MEDIAPIPE_IMPORT_ERROR}"
            )

        self.model_path = model_path or self._resolve_model_path()
        if not os.path.isfile(self.model_path):
            raise FileNotFoundError(
                f"Face Landmarker model not found at: {self.model_path}. "
                "Run 'python scripts/fetch_models.py' once at build time to verify."
            )

        # Initialize MediaPipe Task FaceLandmarker in IMAGE mode with robust confidence thresholds
        base_options = BaseOptions(model_asset_path=self.model_path)
        options = FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=RunningMode.IMAGE,
            num_faces=3,  # Detect up to 3 so we can select the largest foreground face
            min_face_detection_confidence=0.30,
            min_face_presence_confidence=0.30,
            min_tracking_confidence=0.30,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=False,
        )
        self.detector = FaceLandmarker.create_from_options(options)

        # Diagnostics counters
        self.total_inferences: int = 0
        self.successful_detections: int = 0
        self.last_inference_ts: float = 0.0
        self.last_detection_ts: float = 0.0
        self.last_landmark_count: int = 0
        self.last_error: str = ""

    def get_diagnostics(self) -> Dict[str, Any]:
        """Returns real diagnostic metadata about the model inference status."""
        rate = (
            (self.successful_detections / self.total_inferences * 100.0)
            if self.total_inferences > 0
            else 0.0
        )
        return {
            "model_initialized": (self.detector is not None),
            "model_path": self.model_path,
            "total_inferences": self.total_inferences,
            "successful_detections": self.successful_detections,
            "detection_rate_pct": round(rate, 1),
            "last_inference_ts": self.last_inference_ts,
            "last_detection_ts": self.last_detection_ts,
            "last_landmark_count": self.last_landmark_count,
            "last_error": self.last_error,
        }

    @staticmethod
    def _resolve_model_path() -> str:
        """Finds the bundled face_landmarker.task model relative to engine directory."""
        candidates = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "face_landmarker.task"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "face_landmarker.task"),
            os.path.join("engine", "models", "face_landmarker.task"),
            os.path.join("models", "face_landmarker.task"),
        ]
        for path in candidates:
            if os.path.isfile(path):
                return os.path.abspath(path)
        return candidates[0]

    def process_frame(self, frame_bgr: np.ndarray) -> Optional[FaceLandmarksResult]:
        """
        Extracts 478 face mesh landmarks + iris and blendshapes from an input BGR frame.
        Identifies and tracks the largest face by bounding box area.
        Frame is ephemeral: callers must not retain frame references.
        """
        if frame_bgr is None or frame_bgr.size == 0 or self.detector is None:
            self.last_landmark_count = 0
            return None

        self.total_inferences += 1
        self.last_inference_ts = time.time()

        try:
            # Convert BGR to RGB for MediaPipe, ensuring contiguous memory layout
            rgb = np.ascontiguousarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            detection_result: FaceLandmarkerResult = self.detector.detect(mp_image)
        except Exception as e:
            self.last_error = str(e)
            self.last_landmark_count = 0
            return None

        if not detection_result or not detection_result.face_landmarks:
            self.last_landmark_count = 0
            return None

        # Pick the largest face in frame by normalized bounding box area
        best_idx = 0
        max_area = -1.0

        for idx, face_landmarks in enumerate(detection_result.face_landmarks):
            xs = [lm.x for lm in face_landmarks]
            ys = [lm.y for lm in face_landmarks]
            area = (max(xs) - min(xs)) * (max(ys) - min(ys))
            if area > max_area:
                max_area = area
                best_idx = idx

        target_landmarks = detection_result.face_landmarks[best_idx]
        landmarks_array = np.array(
            [[lm.x, lm.y, lm.z] for lm in target_landmarks], dtype=np.float32
        )

        # Update diagnostic counters
        self.successful_detections += 1
        self.last_detection_ts = self.last_inference_ts
        self.last_landmark_count = len(landmarks_array)

        # Extract blendshapes dictionary
        blendshapes_dict: Dict[str, float] = {}
        if (
            detection_result.face_blendshapes
            and len(detection_result.face_blendshapes) > best_idx
        ):
            for category in detection_result.face_blendshapes[best_idx]:
                blendshapes_dict[category.category_name] = float(category.score)

        return FaceLandmarksResult(
            landmarks=landmarks_array,
            blendshapes=blendshapes_dict,
            box_area=max_area,
        )

    def close(self) -> None:
        if self.detector:
            try:
                self.detector.close()
            except Exception:
                pass
            self.detector = None
