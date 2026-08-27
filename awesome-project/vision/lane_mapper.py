import sys
import os
import time
import json
import argparse
import gc
import cv2
import numpy as np

try:
    import torch
except ImportError:
    torch = None

# Ensure project root is on sys.path for direct script execution
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from vision.publisher import VisionTelemetryPublisher
except ImportError:
    from publisher import VisionTelemetryPublisher

from ultralytics import YOLO

def resolve_video_path(input_path: str = None):
    if input_path:
        if os.path.exists(input_path):
            return os.path.abspath(input_path)
        root_relative = os.path.join(ROOT_DIR, input_path)
        if os.path.exists(root_relative):
            return os.path.abspath(root_relative)
    
    candidates = [
        "test_traffic.mp4",
        "traffic.mp4",
        os.path.join(ROOT_DIR, "test_traffic.mp4"),
        os.path.join(ROOT_DIR, "traffic.mp4"),
        os.path.join(os.path.dirname(__file__), "test_traffic.mp4"),
        os.path.join(os.path.dirname(__file__), "traffic.mp4")
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return "test_traffic.mp4"

# Calibrated 8 SUMO lane polygons
DEFAULT_LANES = {
    "n_t_0": np.array([(268, 177), (12, 283), (4, 369), (285, 271)], dtype=np.int32),
    "n_t_1": np.array([(284, 280), (5, 377), (5, 529), (329, 532)], dtype=np.int32),
    "s_t_0": np.array([(582, 534), (734, 410), (892, 533), (792, 536)], dtype=np.int32),
    "s_t_1": np.array([(743, 393), (919, 533), (952, 447), (805, 318)], dtype=np.int32),
    "e_t_0": np.array([(771, 234), (813, 105), (786, 87), (702, 162)], dtype=np.int32),
    "e_t_1": np.array([(693, 156), (777, 80), (744, 54), (626, 107)], dtype=np.int32),
    "w_t_0": np.array([(530, 100), (419, 47), (384, 58), (473, 119)], dtype=np.int32),
    "w_t_1": np.array([(457, 123), (375, 60), (326, 75), (345, 146)], dtype=np.int32),
}

LANES_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "lanes_config.json")

def load_lane_polygons():
    if os.path.exists(LANES_CONFIG_PATH):
        try:
            with open(LANES_CONFIG_PATH, "r") as f:
                data = json.load(f)
                loaded = {k: np.array(v, dtype=np.int32) for k, v in data.items()}
                print(f"[*] Loaded calibrated lane polygons from: {LANES_CONFIG_PATH}")
                return loaded
        except Exception as e:
            print(f"[!] Warning: Failed to parse {LANES_CONFIG_PATH}: {e}")
    return DEFAULT_LANES

def point_in_lane(x, y, lanes_dict):
    for name, poly in lanes_dict.items():
        if cv2.pointPolygonTest(poly, (float(x), float(y)), False) >= 0:
            return name
    return None

def box_in_lane(x1, y1, x2, y2, lanes_dict):
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    pts = [
        (cx, cy),           # center
        (cx, y2),           # bottom center (tires)
        (cx, y1),           # top center
        (cx, (cy + y2)//2)  # lower middle
    ]
    for pt in pts:
        lane = point_in_lane(pt[0], pt[1], lanes_dict)
        if lane:
            return lane, cx, cy
    return None, cx, cy

def lane_area(poly):
    return cv2.contourArea(poly)

def run_lane_mapper(video_path: str = None, headless: bool = True, loop: bool = True):
    resolved_path = resolve_video_path(video_path)
    if not os.path.exists(resolved_path):
        print(f"[!] Error: Video file '{resolved_path}' was not found.")
        print(f"[i] Place 'test_traffic.mp4' in project root or specify: python vision/lane_mapper.py <path_to_video.mp4>")
        return False

    display_size = (960, 540)
    pixels_per_meter = 20.0
    intersection_id = "INT-001"
    lanes = load_lane_polygons()

    print("=" * 70)
    print(f"[*] Starting YOLOv8 Vehicle Tracker on: {resolved_path}")
    print(f"[*] Mode: {'HEADLESS (Terminal Only)' if headless else 'GUI (OpenCV Window)'} | Loop: {loop}")
    print(f"[*] Streaming live telemetry to: http://127.0.0.1:8000/api/v1/telemetry/ingest")
    print("=" * 70)

    model = YOLO("yolov8s.pt")
    publisher = VisionTelemetryPublisher(api_url="http://127.0.0.1:8000/api/v1/telemetry/ingest")
    cap = cv2.VideoCapture(resolved_path)

    if not headless:
        cv2.namedWindow("Traffic Vision Analytics", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Traffic Vision Analytics", display_size[0], display_size[1])

    prev_positions = {}
    frame_num = 0

    try:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok or frame is None:
                if loop:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    print("[*] Video reached end -> Looping back to start.")
                    continue
                else:
                    break

            frame_num += 1
            now = time.time()

            frame = cv2.resize(frame, display_size)
            # Lowered confidence slightly to catch vehicles at the edge or farther away
            results = model.track(frame, persist=True, tracker="bytetrack.yaml", conf=0.25, verbose=False)[0]

            lane_data = {
                name: {"vehicle_count": 0, "classes": {}, "speeds": [], "covered_area": 0.0}
                for name in lanes
            }

            boxes = results.boxes
            if boxes is not None and len(boxes) > 0:
                track_ids = boxes.id.int().cpu().tolist() if boxes.id is not None else [-1] * len(boxes)
                for box, tid in zip(boxes, track_ids):
                    cls_id = int(box.cls[0])
                    label = model.names[cls_id]
                    if label not in ("car", "bus", "truck", "motorcycle", "bicycle"):
                        continue

                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    
                    # Check if any key point of the vehicle box is inside a lane polygon
                    lane, cx, cy = box_in_lane(x1, y1, x2, y2, lanes)
                    if not lane:
                        continue

                    lane_data[lane]["vehicle_count"] += 1
                    lane_data[lane]["classes"][label] = lane_data[lane]["classes"].get(label, 0) + 1
                    lane_data[lane]["covered_area"] += (x2 - x1) * (y2 - y1)

                    if tid != -1 and tid in prev_positions:
                        px, py, pt = prev_positions[tid]
                        dt = now - pt
                        if 0.01 < dt < 2.0:
                            dist_px = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
                            dist_m = dist_px / pixels_per_meter
                            speed_mps = dist_m / dt
                            speed_kmh = speed_mps * 3.6
                            if speed_kmh < 120.0:
                                lane_data[lane]["speeds"].append(speed_kmh)

                    if tid != -1:
                        prev_positions[tid] = (cx, cy, now)

                    if not headless:
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            # Prune old track positions every 60 frames and collect garbage
            if frame_num % 60 == 0:
                prev_positions = {k: v for k, v in prev_positions.items() if (now - v[2]) < 5.0}
                gc.collect()
                if torch and torch.cuda.is_available():
                    torch.cuda.empty_cache()

            # Publish telemetry to FastAPI backend every 6 frames (~2-3 updates per second)
            if frame_num % 6 == 0:
                lanes_payload = []
                for name, poly in lanes.items():
                    d = lane_data[name]
                    avg_speed = sum(d["speeds"]) / len(d["speeds"]) if d["speeds"] else 0.0
                    area = lane_area(poly)
                    occupancy = min(d["covered_area"] / area, 1.0) if area > 0 else 0.0
                    queue_length_m = d["vehicle_count"] * 5.0

                    lanes_payload.append({
                        "lane_id": name,
                        "vehicle_count": d["vehicle_count"],
                        "average_speed": round(avg_speed, 1),
                        "queue_length": round(queue_length_m, 1),
                        "occupancy": round(occupancy, 2),
                        "vehicle_classes": d["classes"]
                    })

                # Video timing metadata
                fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 3000
                video_time_sec = frame_num / fps
                total_duration_sec = total_frames / fps
                cur_m, cur_s = divmod(int(video_time_sec), 60)
                tot_m, tot_s = divmod(int(total_duration_sec), 60)
                video_ts = f"{cur_m:02d}:{cur_s:02d} / {tot_m:02d}:{tot_s:02d}"

                published = publisher.publish_frame_metrics(
                    intersection_id=intersection_id, 
                    lanes=lanes_payload,
                    frame_number=frame_num,
                    video_time_seconds=video_time_sec,
                    total_duration_seconds=total_duration_sec,
                    video_timestamp=video_ts
                )
                total_veh = sum(d["vehicle_count"] for d in lane_data.values())
                active_lanes = sum(1 for d in lane_data.values() if d["vehicle_count"] > 0)
                status_str = "Ingested [200 OK]" if published else "Publish Failed"
                print(f"[Frame {frame_num:05d} | {video_ts}] Active: {active_lanes}/8 | Veh: {total_veh:>2} | API: {status_str}", flush=True)

            if not headless:
                # Draw lane overlays
                for name, poly in lanes.items():
                    v_count = lane_data[name]["vehicle_count"]
                    color = (0, 0, 255) if v_count > 5 else (0, 255, 255) if v_count > 0 else (255, 200, 0)
                    cv2.polylines(frame, [poly], True, color, 2)
                    centroid = np.mean(poly, axis=0).astype(int)
                    cv2.putText(frame, f"{name}: {v_count}", (centroid[0] - 20, centroid[1]),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

                cv2.imshow("Traffic Vision Analytics", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except (KeyboardInterrupt, SystemError):
        print("\n[*] Processing stopped by user.", flush=True)
    except Exception as e:
        print(f"\n[!] Error during video stream: {e}", flush=True)
    finally:
        # If feed ended, send a failsafe packet engaging standard fixed-time traffic light protocol
        try:
            lanes_payload = [
                {
                    "lane_id": name,
                    "vehicle_count": 0,
                    "average_speed": 0.0,
                    "queue_length": 0.0,
                    "occupancy": 0.0,
                    "vehicle_classes": {}
                }
                for name in lanes
            ]
            publisher.publish_frame_metrics(
                intersection_id=intersection_id,
                lanes=lanes_payload,
                frame_number=frame_num,
                video_time_seconds=300.0,
                total_duration_seconds=300.0,
                video_timestamp="05:00 / 05:00",
                feed_status="OFFLINE",
                failsafe_active=True,
                failsafe_message="Camera video feed ended. Autonomous Fallback: Standard Fixed-Time NEMA Signal Protocol Active."
            )
            print("\n" + "=" * 70)
            print("[*] VIDEO FEED COMPLETED (5:00 min playback reached).")
            print("[⚠️] CAMERA FEED OFFLINE -> FAILSAFE ENGAGED")
            print("[*] Broadcasting: Standard Fixed-Time Traffic Light Protocols Enabled.")
            print("=" * 70, flush=True)
        except Exception as e:
            print(f"[!] Warning: Could not publish failsafe packet: {e}", flush=True)

        cap.release()
        publisher.close()
        if not headless:
            cv2.destroyAllWindows()
        gc.collect()
        if torch and torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("[*] Vision processing session closed.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run YOLO Lane Mapper on Traffic Video")
    parser.add_argument("video", nargs="?", default=None, help="Path to traffic video (default: test_traffic.mp4)")
    parser.add_argument("--gui", action="store_true", help="Show visual OpenCV window (default is headless terminal)")
    parser.add_argument("--loop", action="store_true", help="Loop video continuously when it finishes (default: stop at 5 min)")
    args = parser.parse_args()

    run_lane_mapper(
        video_path=args.video,
        headless=not args.gui,
        loop=args.loop
    )