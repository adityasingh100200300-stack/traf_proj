import sys
import os
import time
import json
import argparse
import cv2
import numpy as np
from ultralytics import YOLO

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# 8 Inflow lanes defined in SUMO single-intersection.net.xml
SUMO_LANES = {
    "n_t_0": "North (Outer)",
    "n_t_1": "North (Inner)",
    "s_t_0": "South (Outer)",
    "s_t_1": "South (Inner)",
    "e_t_0": "East (Outer)",
    "e_t_1": "East (Inner)",
    "w_t_0": "West (Outer)",
    "w_t_1": "West (Inner)"
}

LANE_COLORS = {
    "n_t_0": (46, 204, 113),   # Emerald Green
    "n_t_1": (39, 174, 96),    # Forest Green
    "s_t_0": (52, 152, 219),   # Sky Blue
    "s_t_1": (41, 128, 185),   # Deep Blue
    "e_t_0": (243, 156, 18),   # Amber/Orange
    "e_t_1": (230, 126, 34),   # Dark Orange
    "w_t_0": (155, 89, 182),   # Purple
    "w_t_1": (142, 68, 173)    # Dark Violet
}

CLASS_COLORS = {
    "car": (0, 255, 127),      # Spring Green
    "bus": (255, 215, 0),      # Gold
    "truck": (0, 191, 255),    # Deep Sky Blue
    "motorcycle": (255, 105, 180), # Pink
    "bicycle": (135, 206, 250)
}

LANES_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "lanes_config.json")

def load_lane_polygons():
    if os.path.exists(LANES_CONFIG_PATH):
        try:
            with open(LANES_CONFIG_PATH, "r") as f:
                data = json.load(f)
                return {k: np.array(v, dtype=np.int32) for k, v in data.items()}
        except Exception as e:
            print(f"[!] Warning: Failed to parse {LANES_CONFIG_PATH}: {e}")
    # Default calibrated coordinates
    return {
        "n_t_0": np.array([(268, 177), (12, 283), (4, 369), (285, 271)], dtype=np.int32),
        "n_t_1": np.array([(284, 280), (5, 377), (5, 529), (329, 532)], dtype=np.int32),
        "s_t_0": np.array([(582, 534), (734, 410), (892, 533), (792, 536)], dtype=np.int32),
        "s_t_1": np.array([(743, 393), (919, 533), (952, 447), (805, 318)], dtype=np.int32),
        "e_t_0": np.array([(771, 234), (813, 105), (786, 87), (702, 162)], dtype=np.int32),
        "e_t_1": np.array([(693, 156), (777, 80), (744, 54), (626, 107)], dtype=np.int32),
        "w_t_0": np.array([(530, 100), (419, 47), (384, 58), (473, 119)], dtype=np.int32),
        "w_t_1": np.array([(457, 123), (375, 60), (326, 75), (345, 146)], dtype=np.int32),
    }

def point_in_lane(x, y, lanes_dict):
    for name, poly in lanes_dict.items():
        if cv2.pointPolygonTest(poly, (float(x), float(y)), False) >= 0:
            return name
    return None

def render_annotated_video(
    input_video: str = "test_traffic.mp4",
    output_video: str = "annotated_traffic.mp4",
    max_frames: int = None,
    display_width: int = 960,
    display_height: int = 540
):
    if not os.path.exists(input_video):
        input_video = os.path.join(ROOT_DIR, input_video)
    if not os.path.exists(input_video):
        print(f"[!] Error: Video file '{input_video}' not found.")
        return False

    cap = cv2.VideoCapture(input_video)
    total_src_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    if max_frames:
        total_render_frames = min(total_src_frames, max_frames)
    else:
        total_render_frames = total_src_frames

    print("=" * 70)
    print(f"[*] RENDER ANNOTATED TRAFFIC VIDEO")
    print(f"[*] Input Source   : {input_video} ({total_src_frames} frames @ {fps:.1f} FPS)")
    print(f"[*] Output Target  : {output_video} ({display_width}x{display_height})")
    print(f"[*] Target Frames  : {total_render_frames}")
    print("=" * 70)

    model = YOLO("yolov8s.pt")
    lanes = load_lane_polygons()

    # Video writer setup
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_video, fourcc, fps, (display_width, display_height))

    # Also prepare frontend public destination
    frontend_public_dest = os.path.join(ROOT_DIR, "frontend", "public", "annotated_traffic.mp4")
    out_public = None
    if os.path.exists(os.path.dirname(frontend_public_dest)):
        out_public = cv2.VideoWriter(frontend_public_dest, fourcc, fps, (display_width, display_height))

    prev_positions = {}
    frame_idx = 0
    start_time = time.time()

    try:
        while cap.isOpened() and frame_idx < total_render_frames:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            frame_idx += 1
            frame = cv2.resize(frame, (display_width, display_height))
            overlay = frame.copy()
            now = time.time()

            # 1. Draw Lane Polygons on overlay
            lane_vehicle_counts = {k: 0 for k in lanes}
            for name, poly in lanes.items():
                color = LANE_COLORS.get(name, (0, 255, 0))
                cv2.fillPoly(overlay, [poly], color)
                cv2.polylines(frame, [poly], True, color, 2)
                centroid = np.mean(poly, axis=0).astype(int)
                cv2.putText(frame, name, (centroid[0] - 20, centroid[1]),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 2)

            # Apply semi-transparent lane fill
            cv2.addWeighted(overlay, 0.22, frame, 0.78, 0, frame)

            # 2. Run YOLO Tracking
            results = model.track(frame, persist=True, tracker="bytetrack.yaml", conf=0.32, verbose=False)[0]

            active_detected_count = 0
            if results.boxes is not None and results.boxes.id is not None:
                for box, track_id in zip(results.boxes, results.boxes.id):
                    cls_id = int(box.cls[0])
                    label = model.names[cls_id]
                    if label not in ("car", "bus", "truck", "motorcycle"):
                        continue

                    active_detected_count += 1
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    tid = int(track_id)

                    # Determine lane
                    matched_lane = point_in_lane(cx, cy, lanes)
                    if matched_lane:
                        lane_vehicle_counts[matched_lane] += 1

                    # Speed Estimation
                    speed_kmh = 0.0
                    if tid in prev_positions:
                        px, py, pt = prev_positions[tid]
                        dt = now - pt
                        if dt > 0:
                            dist_px = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
                            speed_mps = (dist_px / 20.0) / dt
                            speed_kmh = min(90.0, speed_mps * 3.6)
                    prev_positions[tid] = (cx, cy, now)

                    # Bounding Box Color based on vehicle class
                    box_color = CLASS_COLORS.get(label, (0, 255, 127))

                    # 3. Draw Vehicle Bounding Box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)

                    # Centroid marker
                    cv2.circle(frame, (cx, cy), 3, (0, 0, 255), -1)

                    # Label Tag Background
                    tag = f"#{tid} {label.upper()} {conf:.2f}"
                    if speed_kmh > 3.0:
                        tag += f" | {speed_kmh:.0f}km/h"
                    if matched_lane:
                        tag += f" [{matched_lane}]"

                    (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
                    cv2.rectangle(frame, (x1, max(0, y1 - 18)), (x1 + tw + 6, max(18, y1)), (15, 23, 42), -1)
                    cv2.rectangle(frame, (x1, max(0, y1 - 18)), (x1 + tw + 6, max(18, y1)), box_color, 1)
                    cv2.putText(frame, tag, (x1 + 3, max(13, y1 - 4)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)

            # 4. Top Telemetry HUD Header
            cv2.rectangle(frame, (0, 0), (display_width, 42), (10, 15, 30), -1)
            cv2.line(frame, (0, 42), (display_width, 42), (51, 65, 85), 1)

            hud_title = "ADAPTIVE TRAFFIC MANAGEMENT CENTER | INT-001"
            cv2.putText(frame, hud_title, (12, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)

            hud_stats = f"Frame: {frame_idx:04d}/{total_render_frames} | Active Vehicles: {active_detected_count:>2} | 8 Lanes Monitored"
            cv2.putText(frame, hud_stats, (12, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (148, 163, 184), 1)

            # Write Frame to Video Files
            out.write(frame)
            if out_public:
                out_public.write(frame)

            # Progress log every 100 frames
            if frame_idx % 100 == 0 or frame_idx == total_render_frames:
                elapsed = time.time() - start_time
                fps_render = frame_idx / max(0.001, elapsed)
                pct = (frame_idx / total_render_frames) * 100
                print(f"[Render Progress] {frame_idx:>4}/{total_render_frames} ({pct:>5.1f}%) | Speed: {fps_render:.1f} FPS | Elapsed: {elapsed:.1f}s", flush=True)

    except KeyboardInterrupt:
        print("\n[*] Rendering stopped early by user.")
    finally:
        cap.release()
        out.release()
        if out_public:
            out_public.release()
        print("\n" + "=" * 70)
        print(f"[✓] Annotated video generated successfully:")
        print(f"    • Root output    : {os.path.abspath(output_video)}")
        if out_public:
            print(f"    • Frontend player: {os.path.abspath(frontend_public_dest)}")
        print("=" * 70)
        return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render Annotated Video with Vehicle Bounding Boxes and SUMO Lanes")
    parser.add_argument("video", nargs="?", default="test_traffic.mp4", help="Path to input traffic video")
    parser.add_argument("--output", default="annotated_traffic.mp4", help="Output annotated MP4 file name")
    parser.add_argument("--frames", type=int, default=None, help="Maximum number of frames to render (default: all)")
    args = parser.parse_args()

    render_annotated_video(
        input_video=args.video,
        output_video=args.output,
        max_frames=args.frames
    )
