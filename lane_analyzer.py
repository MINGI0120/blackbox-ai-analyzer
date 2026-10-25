from collections import deque
import math

import cv2
import numpy as np


class LaneAnalyzer:
    """블랙박스 영상의 차선 기하와 도로 구조 단서를 누적 분석한다.

    이 모듈은 색상 마스크, 에지, 선분 기하와 시간축 일관성을 결합한다.
    한 프레임의 선 하나만으로 차로 변경을 단정하지 않는다.
    """

    def __init__(self, analysis_width=1280, history_size=45):
        self.analysis_width = max(640, int(analysis_width))
        self.frame_count = 0
        self.frames_with_both_lanes = 0
        self.frames_with_any_lane = 0
        self.left_detected_frames = 0
        self.right_detected_frames = 0
        self.horizontal_pattern_frames = 0
        self.offset_history = []
        self.nearest_line_history = deque(maxlen=history_size)
        self.confidence_history = deque(maxlen=history_size)
        self.width_history = deque(maxlen=history_size)
        self.lane_crossing_events = []
        self.last_crossing_frame = -10_000
        self.best_frame_confidence = 0
        self.latest = self._empty_frame_result()

    @staticmethod
    def _empty_frame_result():
        return {
            "left_line": None,
            "right_line": None,
            "lane_polygon": None,
            "lane_center_x": None,
            "camera_offset_ratio": None,
            "nearest_line_ratio": None,
            "horizontal_score": 0.0,
            "confidence": 0,
        }

    @staticmethod
    def _weighted_average(values, weights):
        if not values:
            return None
        weight_sum = sum(weights)
        if weight_sum <= 0:
            return sum(values) / len(values)
        return sum(v * w for v, w in zip(values, weights)) / weight_sum

    def _prepare(self, frame):
        height, width = frame.shape[:2]
        scale = min(1.0, self.analysis_width / max(width, 1))
        if scale < 1.0:
            small = cv2.resize(
                frame,
                (int(width * scale), int(height * scale)),
                interpolation=cv2.INTER_AREA,
            )
        else:
            small = frame.copy()
        return small, scale

    @staticmethod
    def _line_at_y(line, y):
        x1, y1, x2, y2 = line
        delta_y = y2 - y1
        if abs(delta_y) < 1e-6:
            return None
        return x1 + (y - y1) * (x2 - x1) / delta_y

    def _fit_boundary(self, candidates, y_top, y_bottom, frame_width):
        if not candidates:
            return None

        bottom_values = []
        top_values = []
        weights = []
        for line, length in candidates:
            bottom_x = self._line_at_y(line, y_bottom)
            top_x = self._line_at_y(line, y_top)
            if bottom_x is None or top_x is None:
                continue
            if not (-0.3 * frame_width <= bottom_x <= 1.3 * frame_width):
                continue
            bottom_values.append(bottom_x)
            top_values.append(top_x)
            weights.append(length)

        if not bottom_values:
            return None

        median_bottom = float(np.median(bottom_values))
        deviations = np.abs(np.asarray(bottom_values) - median_bottom)
        limit = max(frame_width * 0.07, float(np.median(deviations)) * 2.5)
        keep = [index for index, value in enumerate(deviations) if value <= limit]
        if not keep:
            return None

        bottom_x = self._weighted_average(
            [bottom_values[index] for index in keep],
            [weights[index] for index in keep],
        )
        top_x = self._weighted_average(
            [top_values[index] for index in keep],
            [weights[index] for index in keep],
        )
        support = min(1.0, sum(weights[index] for index in keep) / (frame_width * 0.9))
        return {
            "points": (
                (int(round(top_x)), int(y_top)),
                (int(round(bottom_x)), int(y_bottom)),
            ),
            "support": support,
            "bottom_x": float(bottom_x),
            "top_x": float(top_x),
        }

    def update(self, frame):
        self.frame_count += 1
        small, scale = self._prepare(frame)
        height, width = small.shape[:2]
        y_top = int(height * 0.48)
        y_bottom = int(height * 0.90)
        center_x = width / 2.0

        hls = cv2.cvtColor(small, cv2.COLOR_BGR2HLS)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        white_mask = cv2.inRange(hls, (0, 145, 0), (180, 255, 125))
        yellow_mask = cv2.inRange(hsv, (12, 55, 85), (42, 255, 255))
        color_mask = cv2.bitwise_or(white_mask, yellow_mask)

        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(gray, 55, 155)
        combined = cv2.bitwise_or(edges, color_mask)

        roi_mask = np.zeros_like(combined)
        polygon = np.array([[
            (int(width * 0.03), y_bottom),
            (int(width * 0.30), y_top),
            (int(width * 0.70), y_top),
            (int(width * 0.97), y_bottom),
        ]], dtype=np.int32)
        cv2.fillPoly(roi_mask, polygon, 255)
        roi = cv2.bitwise_and(combined, roi_mask)

        lines = cv2.HoughLinesP(
            roi,
            1,
            np.pi / 180,
            threshold=max(35, int(width * 0.035)),
            minLineLength=max(30, int(width * 0.035)),
            maxLineGap=max(25, int(width * 0.025)),
        )

        left_candidates = []
        right_candidates = []
        horizontal_length = 0.0
        horizontal_y_positions = []
        diagonal_length = 0.0
        nearest_candidates = []

        for raw_line in lines if lines is not None else []:
            coordinates = np.asarray(raw_line).reshape(-1)
            if coordinates.size != 4:
                continue
            x1, y1, x2, y2 = map(float, coordinates)
            dx = x2 - x1
            dy = y2 - y1
            length = math.hypot(dx, dy)
            if length <= 0:
                continue
            slope = dy / dx if abs(dx) > 1e-6 else math.copysign(99.0, dy)

            if abs(slope) <= 0.12 and length >= width * 0.28:
                sample_count = max(12, int(length / 12))
                sample_x = np.linspace(x1, x2, sample_count).astype(int)
                sample_y = np.linspace(y1, y2, sample_count).astype(int)
                sample_x = np.clip(sample_x, 0, width - 1)
                sample_y = np.clip(sample_y, 0, height - 1)
                color_support = float(
                    np.count_nonzero(color_mask[sample_y, sample_x])
                ) / sample_count
                midpoint_y = (y1 + y2) / 2.0
                if color_support >= 0.55 and midpoint_y >= height * 0.58:
                    horizontal_length += length
                    horizontal_y_positions.append(midpoint_y)
                continue
            if abs(slope) < 0.30 or abs(slope) > 8.0:
                continue

            line = (x1, y1, x2, y2)
            bottom_x = self._line_at_y(line, y_bottom)
            if bottom_x is None:
                continue
            diagonal_length += length
            nearest_candidates.append(bottom_x)
            if width * 0.03 <= bottom_x < center_x - width * 0.015:
                left_candidates.append((line, length))
            elif center_x + width * 0.015 < bottom_x <= width * 0.97:
                right_candidates.append((line, length))

        left = self._fit_boundary(left_candidates, y_top, y_bottom, width)
        right = self._fit_boundary(right_candidates, y_top, y_bottom, width)

        self.left_detected_frames += int(left is not None)
        self.right_detected_frames += int(right is not None)
        self.frames_with_any_lane += int(left is not None or right is not None)
        self.frames_with_both_lanes += int(left is not None and right is not None)

        lane_center_x = None
        lane_width = None
        offset_ratio = None
        lane_polygon = None
        support = 0.0

        if left is not None and right is not None:
            lane_width = right["bottom_x"] - left["bottom_x"]
            plausible_width = width * 0.20 <= lane_width <= width * 0.95
            if plausible_width:
                lane_center_x = (left["bottom_x"] + right["bottom_x"]) / 2.0
                offset_ratio = (center_x - lane_center_x) / lane_width
                self.offset_history.append(offset_ratio)
                self.width_history.append(lane_width / width)
                lane_polygon = np.array([
                    left["points"][0],
                    left["points"][1],
                    right["points"][1],
                    right["points"][0],
                ], dtype=np.int32)
                support = (left["support"] + right["support"]) / 2.0
            else:
                left = None
                right = None
        elif left is not None:
            support = left["support"] * 0.55
        elif right is not None:
            support = right["support"] * 0.55

        nearest_ratio = None
        fitted_bottoms = [
            boundary["bottom_x"]
            for boundary in (left, right)
            if boundary is not None
        ]
        if fitted_bottoms:
            nearest_x = min(fitted_bottoms, key=lambda x: abs(x - center_x))
            normalizer = lane_width if lane_width and lane_width > 0 else width * 0.40
            nearest_ratio = (nearest_x - center_x) / normalizer
            self.nearest_line_history.append(nearest_ratio)

        horizontal_clusters = []
        for y_position in sorted(horizontal_y_positions):
            if (
                not horizontal_clusters
                or y_position - horizontal_clusters[-1] >= height * 0.018
            ):
                horizontal_clusters.append(y_position)
        horizontal_score = (
            min(1.0, len(horizontal_clusters) / 4.0)
            if horizontal_length >= width * 0.45
            else 0.0
        )
        if len(horizontal_clusters) >= 3 and horizontal_score >= 0.70:
            self.horizontal_pattern_frames += 1

        confidence = int(min(100, round(25 + support * 58))) if support > 0 else 0
        if left is not None and right is not None:
            confidence = min(100, confidence + 12)
        self.confidence_history.append(confidence)
        self.best_frame_confidence = max(self.best_frame_confidence, confidence)

        def restore_line(boundary):
            if boundary is None:
                return None
            return tuple(
                (int(round(x / scale)), int(round(y / scale)))
                for x, y in boundary["points"]
            )

        restored_polygon = None
        if lane_polygon is not None:
            restored_polygon = np.rint(lane_polygon / scale).astype(np.int32)

        self.latest = {
            "left_line": restore_line(left),
            "right_line": restore_line(right),
            "lane_polygon": restored_polygon,
            "lane_center_x": lane_center_x / scale if lane_center_x is not None else None,
            "camera_offset_ratio": offset_ratio,
            "nearest_line_ratio": nearest_ratio,
            "horizontal_score": round(horizontal_score, 3),
            "confidence": confidence,
        }
        return self.latest

    @staticmethod
    def draw_overlay(frame, frame_result):
        output = frame.copy()
        polygon = frame_result.get("lane_polygon")
        if polygon is not None:
            tint = output.copy()
            cv2.fillPoly(tint, [polygon], (40, 150, 40))
            output = cv2.addWeighted(output, 0.82, tint, 0.18, 0)

        for key, color in (("left_line", (255, 210, 40)), ("right_line", (255, 210, 40))):
            line = frame_result.get(key)
            if line is not None:
                cv2.line(output, line[0], line[1], color, 7, cv2.LINE_AA)

        center_x = frame_result.get("lane_center_x")
        if center_x is not None:
            height = output.shape[0]
            cv2.line(
                output,
                (int(center_x), int(height * 0.78)),
                (int(center_x), int(height * 0.91)),
                (0, 255, 255),
                4,
                cv2.LINE_AA,
            )

        cv2.putText(
            output,
            f"LANE {frame_result.get('confidence', 0)}%",
            (20, 88),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 210, 40),
            3,
            cv2.LINE_AA,
        )
        return output

    def get_result(self):
        if self.frame_count == 0:
            return {
                "status": "not_analyzed",
                "confidence": 0,
                "road_structure": "판단 불가",
                "reason": "분석한 프레임이 없습니다.",
            }

        any_rate = self.frames_with_any_lane / self.frame_count
        both_rate = self.frames_with_both_lanes / self.frame_count
        horizontal_rate = self.horizontal_pattern_frames / self.frame_count
        median_offset = (
            float(np.median(self.offset_history))
            if self.offset_history else None
        )
        offset_range = (
            float(max(self.offset_history) - min(self.offset_history))
            if len(self.offset_history) >= 4 else 0.0
        )

        smoothed_offsets = []
        if len(self.offset_history) >= 12:
            values = np.asarray(self.offset_history, dtype=np.float32)
            for index in range(3, len(values) - 3):
                smoothed_offsets.append(float(np.median(values[index - 3:index + 4])))

        crossing_indices = []
        lookback = 10
        for index in range(lookback, len(smoothed_offsets)):
            shifted = abs(smoothed_offsets[index] - smoothed_offsets[index - lookback])
            cooldown_ok = not crossing_indices or index - crossing_indices[-1] >= 25
            if shifted >= 0.45 and cooldown_ok:
                crossing_indices.append(index)
        if len(smoothed_offsets) >= 30 and not crossing_indices:
            section = max(8, len(smoothed_offsets) // 5)
            start_offset = float(np.median(smoothed_offsets[:section]))
            end_offset = float(np.median(smoothed_offsets[-section:]))
            if abs(end_offset - start_offset) >= 0.30:
                crossing_indices.append(len(smoothed_offsets) // 2)
        self.lane_crossing_events = crossing_indices

        if 0.04 <= horizontal_rate <= 0.55:
            intersection_probability = int(min(85, round(horizontal_rate * 180)))
        elif horizontal_rate > 0.55:
            # 화면 대부분에서 지속되는 수평선은 보닛·와이퍼·영상 자막일
            # 가능성이 커서 교차로 증거로 사용하지 않는다.
            intersection_probability = 20
        else:
            intersection_probability = int(round(horizontal_rate * 180))
        lane_change_detected = len(crossing_indices) > 0

        if intersection_probability >= 60:
            road_structure = "교차로·정지선·횡단보도 구간 가능성"
        elif both_rate >= 0.35:
            road_structure = "양쪽 차선이 확인되는 일반 차로"
        elif any_rate >= 0.25:
            road_structure = "일부 차선만 확인되는 도로"
        else:
            road_structure = "차선 구조 판단 불가"

        confidence = int(min(95, round(35 + any_rate * 20 + both_rate * 45)))
        if any_rate < 0.12:
            confidence = min(confidence, 35)

        reasons = [
            f"전체 {self.frame_count}프레임 중 차선 단서가 "
            f"{self.frames_with_any_lane}프레임({any_rate * 100:.1f}%)에서 확인됐습니다."
        ]
        if self.frames_with_both_lanes:
            reasons.append(
                f"좌우 차선이 함께 잡힌 프레임은 "
                f"{self.frames_with_both_lanes}개({both_rate * 100:.1f}%)입니다."
            )
        if lane_change_detected:
            reasons.append(
                f"차로 중심에 대한 블랙박스 차량의 상대 위치가 차선 변경 "
                f"수준으로 이동한 구간이 {len(self.lane_crossing_events)}회 확인됐습니다."
            )
        else:
            reasons.append("연속 프레임에서 명확한 차선선 통과는 확인되지 않았습니다.")
        if intersection_probability >= 40:
            reasons.append(
                "진행 방향과 수평인 노면선이 반복되어 정지선·횡단보도·교차로 가능성을 반영했습니다."
            )

        return {
            "status": "ok" if any_rate >= 0.12 else "insufficient",
            "backend": "temporal_lane_geometry",
            "confidence": confidence,
            "frames_analyzed": self.frame_count,
            "frames_with_lane": self.frames_with_any_lane,
            "detection_rate": round(any_rate * 100, 1),
            "both_lane_rate": round(both_rate * 100, 1),
            "left_detection_rate": round(self.left_detected_frames / self.frame_count * 100, 1),
            "right_detection_rate": round(self.right_detected_frames / self.frame_count * 100, 1),
            "road_structure": road_structure,
            "intersection_probability": intersection_probability,
            "lane_change_detected": lane_change_detected,
            "lane_crossing_count": len(crossing_indices),
            "lane_crossing_frames": list(crossing_indices),
            "median_camera_offset_ratio": (
                round(median_offset, 3) if median_offset is not None else None
            ),
            "offset_range": round(offset_range, 3),
            "reason": " ".join(reasons),
        }
