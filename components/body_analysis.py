from __future__ import annotations

from typing import Any, Dict

import cv2
import mediapipe as mp
import numpy as np

# MediaPipe Pose indices
NOSE = 0
LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12
LEFT_ELBOW, RIGHT_ELBOW = 13, 14
LEFT_WRIST, RIGHT_WRIST = 15, 16
LEFT_HIP, RIGHT_HIP = 23, 24
LEFT_KNEE, RIGHT_KNEE = 25, 26
LEFT_ANKLE, RIGHT_ANKLE = 27, 28


def _xy(lms: Any, i: int) -> np.ndarray:
    return np.array([lms[i].x, lms[i].y], dtype=np.float32)


def _dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def _mid(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a + b) / 2.0


def _safe_div(a: float, b: float, eps: float = 1e-9) -> float:
    return float(a) / float(b + eps)


def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Angle ABC in degrees with b as vertex."""
    ba = a - b
    bc = c - b
    denom = (np.linalg.norm(ba) * np.linalg.norm(bc)) + 1e-9
    cosang = np.clip(np.dot(ba, bc) / denom, -1.0, 1.0)
    return float(np.degrees(np.arccos(cosang)))


def _slope_abs(a: np.ndarray, b: np.ndarray) -> float:
    dx = float(b[0] - a[0])
    dy = float(b[1] - a[1])
    return abs(_safe_div(dy, dx))


def extract_stylelab_features(pose_landmarks: Any) -> Dict[str, Any]:
    lms = pose_landmarks

    no = _xy(lms, NOSE)
    ls, rs = _xy(lms, LEFT_SHOULDER), _xy(lms, RIGHT_SHOULDER)
    lh, rh = _xy(lms, LEFT_HIP), _xy(lms, RIGHT_HIP)
    la, ra = _xy(lms, LEFT_ANKLE), _xy(lms, RIGHT_ANKLE)
    le, re = _xy(lms, LEFT_ELBOW), _xy(lms, RIGHT_ELBOW)
    lw, rw = _xy(lms, LEFT_WRIST), _xy(lms, RIGHT_WRIST)
    lk, rk = _xy(lms, LEFT_KNEE), _xy(lms, RIGHT_KNEE)

    shoulder_width = _dist(ls, rs)
    hip_width = _dist(lh, rh)

    shoulder_mid = _mid(ls, rs)
    hip_mid = _mid(lh, rh)
    ankle_mid = _mid(la, ra)

    # 1) body_aspect_ratio (height/width proxy)
    height_proxy = _dist(no, ankle_mid)
    width_proxy = max(shoulder_width, hip_width)
    body_aspect_ratio = _safe_div(height_proxy, width_proxy)

    # 2) torso_leg_ratio (where length lives)
    torso_len = _dist(shoulder_mid, hip_mid)
    leg_len = _dist(hip_mid, ankle_mid)
    torso_leg_ratio = _safe_div(torso_len, leg_len)

    # 3) shoulder_hip_ratio (visual weight)
    shoulder_hip_ratio = _safe_div(shoulder_width, hip_width)

    # 4) joint_softness proxy (0..1)
    left_elbow_ang = _angle(ls, le, lw)
    right_elbow_ang = _angle(rs, re, rw)
    left_knee_ang = _angle(lh, lk, la)
    right_knee_ang = _angle(rh, rk, ra)

    def norm_open(angle_deg: float) -> float:
        return float(np.clip((angle_deg - 90.0) / 90.0, 0.0, 1.0))

    angle_openness = np.mean(
        [
            norm_open(left_elbow_ang),
            norm_open(right_elbow_ang),
            norm_open(left_knee_ang),
            norm_open(right_knee_ang),
        ]
    )

    shoulder_slope = _slope_abs(ls, rs)
    hip_slope = _slope_abs(lh, rh)

    def slope_to_soft(slope: float) -> float:
        return float(np.clip(1.0 - slope, 0.0, 1.0))

    line_softness = np.mean([slope_to_soft(shoulder_slope), slope_to_soft(hip_slope)])
    joint_softness = float(np.clip(0.6 * angle_openness + 0.4 * line_softness, 0.0, 1.0))

    shoulder_hip_confident = shoulder_hip_ratio <= 1.35
    body_aspect_confident = 2.4 <= body_aspect_ratio <= 4.2
    torso_leg_confident = 0.45 <= torso_leg_ratio <= 0.75

    return {
        "body_aspect_ratio": float(np.clip(body_aspect_ratio, 2.20, 4.50)),
        "torso_leg_ratio": float(np.clip(torso_leg_ratio, 0.40, 0.85)),
        "shoulder_hip_ratio": float(np.clip(shoulder_hip_ratio, 0.70, 1.40)),
        "joint_softness": float(np.clip(joint_softness, 0.0, 1.0)),
        "raw": {
            "body_aspect_ratio": float(body_aspect_ratio),
            "torso_leg_ratio": float(torso_leg_ratio),
            "shoulder_hip_ratio": float(shoulder_hip_ratio),
            "joint_softness": float(joint_softness),
        },
        "feature_confidence": {
            "body_aspect_ratio": bool(body_aspect_confident),
            "torso_leg_ratio": bool(torso_leg_confident),
            "shoulder_hip_ratio": bool(shoulder_hip_confident),
            "joint_softness": True,
        },
    }


def _derive_signals(features: Dict[str, Any]) -> Dict[str, str]:
    body_aspect = features["body_aspect_ratio"]
    shoulder_hip = features["shoulder_hip_ratio"]
    softness = features["joint_softness"]

    if body_aspect >= 3.4:
        proportion_signal = "elongated"
    elif body_aspect <= 2.75:
        proportion_signal = "compact"
    else:
        proportion_signal = "balanced"

    if shoulder_hip >= 1.08:
        shoulder_hip_balance = "shoulder_dominant"
    elif shoulder_hip <= 0.92:
        shoulder_hip_balance = "hip_dominant"
    else:
        shoulder_hip_balance = "balanced"

    if softness >= 0.66:
        line_harmony = "fluid"
    elif softness <= 0.45:
        line_harmony = "structured"
    else:
        line_harmony = "clean"

    return {
        "proportion_signal": proportion_signal,
        "shoulder_hip_balance": shoulder_hip_balance,
        "line_harmony": line_harmony,
    }


def _estimate_confidence(landmarks: Any, feature_confidence: Dict[str, bool]) -> float:
    vis_indices = [
        LEFT_SHOULDER,
        RIGHT_SHOULDER,
        LEFT_HIP,
        RIGHT_HIP,
        LEFT_KNEE,
        RIGHT_KNEE,
        LEFT_ANKLE,
        RIGHT_ANKLE,
    ]
    vis_scores = [float(getattr(landmarks[i], "visibility", 0.0)) for i in vis_indices]
    vis_mean = sum(vis_scores) / max(len(vis_scores), 1)

    gates = list(feature_confidence.values())
    gate_score = sum(1.0 for g in gates if g) / max(len(gates), 1)

    return float(np.clip(0.65 * vis_mean + 0.35 * gate_score, 0.0, 1.0))


def analyze_body_from_image(image_bytes: bytes, width: int, height: int) -> Dict[str, Any]:
    if width <= 0 or height <= 0:
        return default_body_profile(confidence=0.25)

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        return default_body_profile(confidence=0.2)

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    try:
        with mp.solutions.pose.Pose(
            static_image_mode=True,
            model_complexity=2,
            enable_segmentation=False,
            min_detection_confidence=0.5,
        ) as pose:
            result = pose.process(img_rgb)
    except Exception:
        return default_body_profile(confidence=0.15)

    if not result.pose_landmarks:
        return default_body_profile(confidence=0.2)

    landmarks = result.pose_landmarks.landmark
    features = extract_stylelab_features(landmarks)
    signals = _derive_signals(features)
    confidence = _estimate_confidence(landmarks, features["feature_confidence"])

    return {
        "proportion_signal": signals["proportion_signal"],
        "torso_leg_ratio": features["torso_leg_ratio"],
        "shoulder_hip_balance": signals["shoulder_hip_balance"],
        "line_harmony": signals["line_harmony"],
        "confidence": round(confidence, 3),
        "features": features,
        "notes": "MediaPipe landmark-derived profile from uploaded photo.",
    }


def default_body_profile(confidence: float = 0.5) -> Dict[str, Any]:
    return {
        "proportion_signal": "balanced",
        "torso_leg_ratio": 0.65,
        "shoulder_hip_balance": "balanced",
        "line_harmony": "clean",
        "confidence": confidence,
        "notes": "Fallback profile used when no photo analysis is available.",
    }
