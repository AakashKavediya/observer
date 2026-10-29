"""
observer_engine.camera
Threaded OpenCV webcam capture module.
Supports Windows DirectShow (cv2.CAP_DSHOW), 15 FPS pacing, downscaling to 640x480,
instant hardware release on pause, and detection of blocked/unplugged cameras.
"""

import sys
import time
import threading
from typing import Optional, Tuple, Callable, Dict, Any
import cv2
import numpy as np
from observer_engine.config import CameraConfig


class CameraCapture:
    def __init__(
        self,
        config: CameraConfig = CameraConfig(),
        status_callback: Optional[Callable[[str, float], None]] = None,
    ):
        self.config = config
        self.status_callback = status_callback
        self.running = False
        self.paused = False
        self.thread: Optional[threading.Thread] = None

        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_timestamp: float = 0.0

        self.cap: Optional[cv2.VideoCapture] = None
        self.fps_measured: float = 0.0
        self._frame_count: int = 0
        self._fps_timer: float = time.time()
        self.total_frames_captured: int = 0
        self.latest_brightness: float = 0.0
        self.current_status: str = "off"

    def _notify_status(self, status: str, fps: float = 0.0) -> None:
        self.current_status = status
        if self.status_callback:
            self.status_callback(status, fps)

    def get_diagnostics(self) -> Dict[str, Any]:
        """Returns live hardware capture diagnostics."""
        return {
            "device_index": self.config.device_index,
            "status": self.current_status,
            "fps_measured": round(self.fps_measured, 1),
            "target_fps": self.config.target_fps,
            "frame_width": self.config.frame_width,
            "frame_height": self.config.frame_height,
            "total_frames_captured": self.total_frames_captured,
            "latest_brightness": round(self.latest_brightness, 1),
            "is_opened": (self.cap is not None and self.cap.isOpened()),
        }

    def _open_camera(self) -> bool:
        self._notify_status("starting", 0.0)

        # On Windows, prefer DirectShow for fast startup and low latency
        backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY

        cap = cv2.VideoCapture(self.config.device_index, backend)
        if not cap.isOpened():
            # Retry with default backend
            cap = cv2.VideoCapture(self.config.device_index)

        if not cap.isOpened():
            self._notify_status("unplugged", 0.0)
            return False

        # Set capture properties
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.frame_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.frame_height)
        cap.set(cv2.CAP_PROP_FPS, self.config.target_fps)

        # Warm-up grab to confirm OS permissions and stream validity
        ret, frame = cap.read()
        if not ret or frame is None:
            cap.release()
            self._notify_status("blocked", 0.0)
            return False

        self.cap = cap
        self._frame_count = 0
        self._fps_timer = time.time()
        self._notify_status("on", self.config.target_fps)
        return True

    def _release_camera(self) -> None:
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    def start(self) -> bool:
        if self.running:
            return True

        self.running = True
        self.paused = False
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        return True

    def pause(self) -> None:
        """Instantly releases the physical webcam hardware on pause."""
        self.paused = True
        self._release_camera()
        self._notify_status("off", 0.0)

    def resume(self) -> None:
        """Re-opens the camera hardware."""
        self.paused = False

    def stop(self) -> None:
        self.running = False
        self.paused = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self._release_camera()
        self._notify_status("off", 0.0)

    def _capture_loop(self) -> None:
        target_frame_time = 1.0 / self.config.target_fps

        while self.running:
            if self.paused:
                time.sleep(0.1)
                continue

            if self.cap is None:
                if not self._open_camera():
                    # Camera unavailable or blocked; wait before retrying
                    time.sleep(2.0)
                    continue

            start_t = time.time()
            ret, frame = self.cap.read()

            if not ret or frame is None:
                # Device lost or unplugged during capture
                self._release_camera()
                self._notify_status("unplugged", 0.0)
                time.sleep(1.0)
                continue

            now = time.time()

            # Ensure 640x480 downscaling
            h, w = frame.shape[:2]
            if w != self.config.frame_width or h != self.config.frame_height:
                frame = cv2.resize(
                    frame,
                    (self.config.frame_width, self.config.frame_height),
                    interpolation=cv2.INTER_AREA,
                )

            # Thread-safe update of latest frame (drops older frames automatically)
            with self._lock:
                self._latest_frame = frame
                self._latest_timestamp = now

            self.total_frames_captured += 1
            if self.total_frames_captured % 15 == 0:
                self.latest_brightness = float(frame.mean())

            # Measure real FPS
            self._frame_count += 1
            elapsed = now - self._fps_timer
            if elapsed >= 1.0:
                self.fps_measured = self._frame_count / elapsed
                self._frame_count = 0
                self._fps_timer = now
                self._notify_status("on", self.fps_measured)

            # Pace loop to target ~15 FPS to conserve CPU and thermals
            processing_time = time.time() - start_t
            sleep_needed = target_frame_time - processing_time
            if sleep_needed > 0.001:
                time.sleep(sleep_needed)

    def get_latest_frame(self) -> Tuple[Optional[np.ndarray], float]:
        """Returns the most recent video frame and its capture timestamp."""
        with self._lock:
            if self._latest_frame is None:
                return None, 0.0
            # Return copy to ensure ephemeral frame safety
            return self._latest_frame.copy(), self._latest_timestamp
