"""Hand tracking and discrete gesture recognition using MediaPipe Tasks GestureRecognizer."""

from dataclasses import dataclass
from pathlib import Path
import time
from typing import List, Optional, Tuple, Union

# Default path to gesture_recognizer.task
DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parent.parent.parent / "models" / "gesture_recognizer.task"
)


@dataclass
class HandTrackingResult:
    """Detection output containing normalized hand landmarks and classified gesture."""

    landmarks: Optional[List[Tuple[float, float, float]]] = None  # 21 normalized landmarks (x, y, z)
    gesture: Optional[str] = None                                # e.g. "Open_Palm", "Closed_Fist"
    gesture_confidence: float = 0.0                              # Confidence score [0.0, 1.0]


class HandTracker:
    """Wraps MediaPipe Tasks GestureRecognizer in VIDEO running mode."""

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        num_hands: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        """Initializes the MediaPipe GestureRecognizer.

        Raises:
            FileNotFoundError: If the .task model file does not exist at model_path.
            ImportError: If mediapipe is not installed.
        """
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self.num_hands = num_hands
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence

        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"MediaPipe GestureRecognizer model file not found at: {self.model_path}\n"
                "Please download the official model task file using:\n"
                "  mkdir -p gesture-controller/models\n"
                "  curl -L -o gesture-controller/models/gesture_recognizer.task \\\n"
                "    https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task\n"
                f"and place it at '{self.model_path}'."
            )

        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
        except ImportError as e:
            raise ImportError(
                "mediapipe is required to run HandTracker. Install it via 'pip install mediapipe'."
            ) from e

        base_options = python.BaseOptions(model_asset_path=str(self.model_path))
        options = vision.GestureRecognizerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=self.num_hands,
            min_hand_detection_confidence=self.min_detection_confidence,
            min_tracking_confidence=self.min_tracking_confidence,
        )
        self._mp = mp
        self._recognizer = vision.GestureRecognizer.create_from_options(options)

    def process(self, frame_rgb, timestamp_ms: Optional[int] = None) -> HandTrackingResult:
        """Processes an RGB frame using recognize_for_video.

        Args:
            frame_rgb: NumPy array containing RGB video frame (uint8).
            timestamp_ms: Millisecond timestamp for the frame. Must be monotonically increasing.

        Returns:
            HandTrackingResult with landmarks, classified gesture, and confidence.
        """
        if self._recognizer is None:
            raise RuntimeError("HandTracker has been closed.")

        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)

        mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=frame_rgb)
        result = self._recognizer.recognize_for_video(mp_image, timestamp_ms)

        landmarks: Optional[List[Tuple[float, float, float]]] = None
        gesture_name: Optional[str] = None
        confidence: float = 0.0

        if result.hand_landmarks and len(result.hand_landmarks) > 0:
            first_hand = result.hand_landmarks[0]
            landmarks = [(float(lm.x), float(lm.y), float(lm.z)) for lm in first_hand]

        if result.gestures and len(result.gestures) > 0:
            first_gesture_list = result.gestures[0]
            if len(first_gesture_list) > 0:
                top_gesture = first_gesture_list[0]
                gesture_name = top_gesture.category_name
                confidence = float(top_gesture.score)

        return HandTrackingResult(
            landmarks=landmarks,
            gesture=gesture_name,
            gesture_confidence=confidence,
        )

    def close(self) -> None:
        """Closes the underlying MediaPipe recognizer."""
        if hasattr(self, "_recognizer") and self._recognizer is not None:
            self._recognizer.close()
            self._recognizer = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
