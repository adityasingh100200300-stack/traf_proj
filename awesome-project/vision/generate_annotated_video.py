import os
import cv2
import numpy as np
import json
import time
from ultralytics import YOLO
import gc
import torch

def get_video_path():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidates = [
        os.path.join(root_dir, "test_traffic.mp4"),
        os.path.join(root_dir, "traffic.mp4"),
        os.path.join(os.path.dirname(__file__), "test_traffic.mp4"),
        os.path.join(os.path.dirname(__file__), "traffic.mp4")
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return None

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
    return {}

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

def main():
    video_path = get_video_path()
    if not video_path:
        print("[!] No traffic.mp4 or test_traffic.mp4 found in vision/")
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[!] Failed to open {video_path}")
        return

    # Original Video Properties
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # We will output at a fixed size matching the lanes calibration 
    display_size = (960, 540)
    
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "annotated_traffic.mp4"))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(out_path, fourcc, fps, display_size)
    print(f"[*] Starting video generation: {out_path} ({total_frames} frames)")

    model = YOLO("yolov8n.pt")
    lanes = load_lane_polygons()
    
    frame_num = 0
    start_time = time.time()

    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            break
            
        frame_num += 1
        frame = cv2.resize(frame, display_size)
        
        # Track objects
        results = model.track(frame, persist=True, tracker="bytetrack.yaml", conf=0.25, verbose=False)[0]
        
        lane_counts = {name: 0 for name in lanes}
        boxes = results.boxes
        if boxes is not None and len(boxes) > 0:
            for box in boxes:
                cls_id = int(box.cls[0])
                label = model.names[cls_id]
                if label not in ("car", "bus", "truck", "motorcycle", "bicycle"):
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0])
                lane, cx, cy = box_in_lane(x1, y1, x2, y2, lanes)
                
                if lane:
                    lane_counts[lane] += 1
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, lane, (x1, max(15, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                else:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 1)
        
        # Draw lanes and counts
        for name, poly in lanes.items():
            count = lane_counts[name]
            color = (0, 0, 255) if count > 5 else (0, 255, 255) if count > 0 else (255, 200, 0)
            cv2.polylines(frame, [poly], True, color, 2)
            centroid = np.mean(poly, axis=0).astype(int)
            
            # Draw a dark background for text to be visible
            txt = f"{name}: {count}"
            (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            cv2.rectangle(frame, (centroid[0] - 5, centroid[1] - th - 5), (centroid[0] + tw + 5, centroid[1] + 5), (0, 0, 0), -1)
            cv2.putText(frame, txt, (centroid[0], centroid[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # Timestamp and Frame number
        cur_m, cur_s = divmod(int(frame_num / fps), 60)
        tot_m, tot_s = divmod(int(total_frames / fps), 60)
        video_ts = f"{cur_m:02d}:{cur_s:02d} / {tot_m:02d}:{tot_s:02d} | Frame {frame_num}/{total_frames}"
        cv2.rectangle(frame, (0, 0), (400, 30), (0, 0, 0), -1)
        cv2.putText(frame, video_ts, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        out.write(frame)
        
        if frame_num % 60 == 0:
            gc.collect()
            if torch and torch.cuda.is_available():
                torch.cuda.empty_cache()
            
        if frame_num % 100 == 0:
            elapsed = time.time() - start_time
            fps_proc = frame_num / elapsed
            print(f"[*] Processed {frame_num}/{total_frames} frames ({fps_proc:.1f} fps) | Time: {video_ts}")
            
    cap.release()
    out.release()
    print(f"\n[*] Annotated video successfully saved to: {out_path}")

if __name__ == "__main__":
    main()
