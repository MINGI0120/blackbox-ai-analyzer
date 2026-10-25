import math

import cv2
import numpy as np


class EgoMotionAnalyzer:
    def __init__(self, sample_interval=3, analysis_width=640):
        self.sample_interval = max(1, sample_interval)
        self.analysis_width = max(320, analysis_width)
        self.frame_index = 0
        self.previous_gray = None
        self.horizontal_shifts = []
        self.forward_expansions = []
        self.valid_pair_count = 0
        self.feature_count = 0

    def _prepare_gray(self, frame):
        height, width = frame.shape[:2]
        scale = self.analysis_width / max(width, 1)
        resized_height = max(180, int(height * scale))
        resized = cv2.resize(
            frame,
            (self.analysis_width, resized_height),
            interpolation=cv2.INTER_AREA,
        )
        return cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    def _feature_mask(self, gray):
        height, width = gray.shape
        mask = np.zeros_like(gray)
        top = int(height * 0.10)
        bottom = int(height * 0.76)
        side = int(width * 0.03)
        mask[top:bottom, side:width - side] = 255
        return mask

    def update(self, frame):
        self.frame_index += 1

        if self.frame_index % self.sample_interval != 0:
            return

        current_gray = self._prepare_gray(frame)

        if self.previous_gray is None:
            self.previous_gray = current_gray
            return

        mask = self._feature_mask(self.previous_gray)
        previous_points = cv2.goodFeaturesToTrack(
            self.previous_gray,
            maxCorners=350,
            qualityLevel=0.01,
            minDistance=8,
            blockSize=7,
            mask=mask,
        )

        if previous_points is None or len(previous_points) < 20:
            self.previous_gray = current_gray
            return

        current_points, status, errors = cv2.calcOpticalFlowPyrLK(
            self.previous_gray,
            current_gray,
            previous_points,
            None,
            winSize=(21, 21),
            maxLevel=3,
            criteria=(
                cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
                30,
                0.01,
            ),
        )

        if current_points is None or status is None:
            self.previous_gray = current_gray
            return

        status = status.reshape(-1).astype(bool)
        if errors is not None:
            status &= errors.reshape(-1) < 35

        old_points = previous_points.reshape(-1, 2)[status]
        new_points = current_points.reshape(-1, 2)[status]

        if len(old_points) < 15:
            self.previous_gray = current_gray
            return

        _, inliers = cv2.estimateAffinePartial2D(
            old_points,
            new_points,
            method=cv2.RANSAC,
            ransacReprojThreshold=3.0,
            maxIters=1500,
            confidence=0.98,
        )

        if inliers is not None:
            inlier_mask = inliers.reshape(-1).astype(bool)
            if np.count_nonzero(inlier_mask) >= 12:
                old_points = old_points[inlier_mask]
                new_points = new_points[inlier_mask]

        flows = new_points - old_points
        frame_height, frame_width = current_gray.shape
        horizontal_shift = float(np.median(flows[:, 0])) / frame_width

        center = np.array(
            [frame_width / 2.0, frame_height / 2.0],
            dtype=np.float32,
        )
        radial_vectors = old_points - center
        radial_lengths = np.linalg.norm(radial_vectors, axis=1)
        valid_radial = radial_lengths > 12

        forward_expansion = 0.0
        if np.count_nonzero(valid_radial) >= 10:
            radial_units = (
                radial_vectors[valid_radial]
                / radial_lengths[valid_radial, None]
            )
            radial_flow = np.sum(
                flows[valid_radial] * radial_units,
                axis=1,
            )
            diagonal = math.hypot(frame_width, frame_height)
            forward_expansion = float(np.median(radial_flow)) / diagonal

        self.horizontal_shifts.append(
            float(np.clip(horizontal_shift, -0.08, 0.08))
        )
        self.forward_expansions.append(
            float(np.clip(forward_expansion, -0.04, 0.04))
        )
        self.valid_pair_count += 1
        self.feature_count += len(old_points)
        self.previous_gray = current_gray

    def get_result(self):
        if self.valid_pair_count < 5:
            return {
                "maneuver": "unknown",
                "title": "차량 움직임 판단 불가",
                "confidence": 0,
                "reason": "배경 특징점이 충분히 추적되지 않았습니다.",
                "valid_pairs": self.valid_pair_count,
                "cumulative_pan": 0.0,
                "consistency": 0.0,
            }

        shifts = np.asarray(self.horizontal_shifts, dtype=np.float32)
        cumulative_pan = float(np.sum(shifts))
        absolute_pan = abs(cumulative_pan)
        mean_absolute_shift = float(np.mean(np.abs(shifts)))

        meaningful = np.abs(shifts) >= 0.0015
        meaningful_count = int(np.count_nonzero(meaningful))
        dominant_sign = 1 if cumulative_pan >= 0 else -1

        if meaningful_count > 0:
            consistent_count = int(
                np.count_nonzero(np.sign(shifts[meaningful]) == dominant_sign)
            )
            consistency = consistent_count / meaningful_count
        else:
            consistency = 0.0

        # 배경이 오른쪽으로 흐르면 카메라 차량은 왼쪽으로 회전한 것으로 본다.
        turn_direction = "left" if cumulative_pan > 0 else "right"
        korean_direction = "좌측" if turn_direction == "left" else "우측"

        if absolute_pan >= 0.34 and consistency >= 0.58:
            maneuver = "u_turn"
            confidence = min(
                92,
                int(62 + absolute_pan * 55 + consistency * 12),
            )
            title = f"{korean_direction} 유턴 가능성"
            reason = (
                f"배경이 한 방향으로 누적 {absolute_pan:.2f} 화면 폭만큼 "
                f"이동했고 방향 일관성은 {consistency * 100:.1f}%입니다."
            )
        elif absolute_pan >= 0.13 and consistency >= 0.55:
            maneuver = turn_direction
            confidence = min(
                86,
                int(55 + absolute_pan * 70 + consistency * 10),
            )
            title = f"{korean_direction} 회전 가능성"
            reason = (
                f"배경의 누적 수평 이동량이 {absolute_pan:.2f} 화면 폭으로 "
                "회전 움직임이 확인됐습니다."
            )
        else:
            maneuver = "straight"
            confidence = max(
                45,
                min(82, int(78 - absolute_pan * 90 + consistency * 4)),
            )
            title = "직진 또는 완만한 진행 가능성"
            reason = (
                f"배경의 누적 수평 이동량이 {absolute_pan:.2f} 화면 폭으로 "
                "뚜렷한 회전 증거가 부족합니다."
            )

        return {
            "maneuver": maneuver,
            "title": title,
            "confidence": confidence,
            "reason": reason,
            "valid_pairs": self.valid_pair_count,
            "average_features": round(
                self.feature_count / max(self.valid_pair_count, 1),
                1,
            ),
            "cumulative_pan": round(cumulative_pan, 4),
            "mean_absolute_shift": round(mean_absolute_shift, 4),
            "consistency": round(consistency, 3),
            "forward_expansion": round(
                float(np.mean(self.forward_expansions)),
                4,
            ),
        }


def analyze_video_ego_motion(video_path, sample_interval=3):
    capture = cv2.VideoCapture(video_path)
    analyzer = EgoMotionAnalyzer(sample_interval=sample_interval)

    while True:
        success, frame = capture.read()
        if not success:
            break
        analyzer.update(frame)

    capture.release()
    return analyzer.get_result()
