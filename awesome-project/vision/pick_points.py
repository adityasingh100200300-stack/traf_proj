import sys
import os
import json
import cv2
import numpy as np
from ultralytics import YOLO

# 8 Inflow lanes defined in SUMO single-intersection.net.xml
SUMO_LANES = [
    ("n_t_0", "North Approach - Lane 0 (Outer/Right)"),
    ("n_t_1", "North Approach - Lane 1 (Inner/Left)"),
    ("s_t_0", "South Approach - Lane 0 (Outer/Right)"),
    ("s_t_1", "South Approach - Lane 1 (Inner/Left)"),
    ("e_t_0", "East Approach  - Lane 0 (Outer/Right)"),
    ("e_t_1", "East Approach  - Lane 1 (Inner/Left)"),
    ("w_t_0", "West Approach  - Lane 0 (Outer/Right)"),
    ("w_t_1", "West Approach  - Lane 1 (Inner/Left)")
]

LANE_COLORS = [
    (46, 204, 113),   # Emerald Green (n_t_0)
    (39, 174, 96),    # Forest Green (n_t_1)
    (52, 152, 219),   # Sky Blue (s_t_0)
    (41, 128, 185),   # Deep Blue (s_t_1)
    (243, 156, 18),   # Amber/Orange (e_t_0)
    (230, 126, 34),   # Dark Orange (e_t_1)
    (155, 89, 182),   # Purple (w_t_0)
    (142, 68, 173)    # Dark Violet (w_t_1)
]

def resolve_video_path():
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        return sys.argv[1]
    
    candidates = [
        "test_traffic.mp4",
        "traffic.mp4",
        "vision/test_traffic.mp4",
        "vision/traffic.mp4",
        os.path.join(os.path.dirname(__file__), "..", "test_traffic.mp4"),
        os.path.join(os.path.dirname(__file__), "test_traffic.mp4")
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return "test_traffic.mp4"

VIDEO_PATH = resolve_video_path()
DISPLAY_SIZE = (960, 540)
JSON_OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "lanes_config.json")

if not os.path.exists(VIDEO_PATH):
    print(f"[!] Error: Video file '{VIDEO_PATH}' was not found.")
    exit(1)

cap = cv2.VideoCapture(VIDEO_PATH)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
current_frame_pos = 0

# Load existing polygons if available
completed_lanes = {}
if os.path.exists(JSON_OUTPUT_PATH):
    try:
        with open(JSON_OUTPUT_PATH, "r") as f:
            data = json.load(f)
            for k, v in data.items():
                if len(v) == 4:
                    completed_lanes[k] = [tuple(p) for p in v]
        print(f"[*] Preloaded {len(completed_lanes)} existing lane polygons from {JSON_OUTPUT_PATH}")
    except Exception as e:
        print(f"[!] Warning: Could not parse {JSON_OUTPUT_PATH}: {e}")

# If no polygons loaded, initialize with defaults
if not completed_lanes:
    default_polys = {
        "n_t_0": [(268, 177), (12, 283), (4, 369), (285, 271)],
        "n_t_1": [(284, 280), (5, 377), (5, 529), (329, 532)],
        "s_t_0": [(582, 534), (734, 410), (892, 533), (792, 536)],
        "s_t_1": [(743, 393), (919, 533), (952, 447), (805, 318)],
        "e_t_0": [(771, 234), (813, 105), (786, 87), (702, 162)],
        "e_t_1": [(693, 156), (777, 80), (744, 54), (626, 107)],
        "w_t_0": [(530, 100), (419, 47), (384, 58), (473, 119)],
        "w_t_1": [(457, 123), (375, 60), (326, 75), (345, 146)],
    }
    completed_lanes = default_polys

current_points = []
selected_lane_idx = 0
mouse_x, mouse_y = 0, 0
show_detections = True
detector = None

def get_current_frame(pos):
    cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
    ok, frame = cap.read()
    if ok and frame is not None:
        return cv2.resize(frame, DISPLAY_SIZE)
    return np.zeros((DISPLAY_SIZE[1], DISPLAY_SIZE[0], 3), dtype=np.uint8)

base_frame = get_current_frame(current_frame_pos)
detection_boxes = []

def run_detector_on_frame(frame):
    global detector
    if detector is None:
        try:
            detector = YOLO("yolov8s.pt")
        except Exception:
            return []
    try:
        res = detector(frame, verbose=False)[0]
        boxes = []
        for b in res.boxes:
            if int(b.cls[0]) in [2, 3, 5, 7] and float(b.conf[0]) > 0.3:
                boxes.append(list(map(int, b.xyxy[0])))
        return boxes
    except Exception:
        return []

detection_boxes = run_detector_on_frame(base_frame)

def redraw():
    canvas = base_frame.copy()
    
    # 1. Draw detection boxes if enabled
    if show_detections:
        for (x1, y1, x2, y2) in detection_boxes:
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 255, 255), 1)

    # 2. Draw all existing lanes
    for idx, (lid, desc) in enumerate(SUMO_LANES):
        if lid in completed_lanes and lid != SUMO_LANES[selected_lane_idx][0]:
            pts = completed_lanes[lid]
            poly = np.array(pts, dtype=np.int32)
            color = LANE_COLORS[idx % len(LANE_COLORS)]
            
            overlay = canvas.copy()
            cv2.fillPoly(overlay, [poly], color)
            cv2.addWeighted(overlay, 0.20, canvas, 0.80, 0, canvas)
            cv2.polylines(canvas, [poly], isClosed=True, color=color, thickness=2)
            
            cx, cy = int(np.mean([p[0] for p in pts])), int(np.mean([p[1] for p in pts]))
            cv2.putText(canvas, lid, (cx - 18, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)

    # 3. Draw currently selected lane
    curr_lid, curr_desc = SUMO_LANES[selected_lane_idx]
    active_color = (0, 0, 255) # Red for active editing
    
    if len(current_points) > 0:
        # Draw user's new clicks
        for i, (x, y) in enumerate(current_points):
            cv2.circle(canvas, (x, y), 5, (0, 255, 0), -1)
            cv2.putText(canvas, str(i + 1), (x + 8, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 2)
        if len(current_points) > 1:
            cv2.polylines(canvas, [np.array(current_points, dtype=np.int32)], isClosed=False, color=(0, 255, 0), thickness=2)
    elif curr_lid in completed_lanes:
        # Draw existing polygon for currently selected lane highlighted
        pts = completed_lanes[curr_lid]
        poly = np.array(pts, dtype=np.int32)
        overlay = canvas.copy()
        cv2.fillPoly(overlay, [poly], (0, 0, 255))
        cv2.addWeighted(overlay, 0.35, canvas, 0.65, 0, canvas)
        cv2.polylines(canvas, [poly], isClosed=True, color=(0, 0, 255), thickness=3)
        for i, (x, y) in enumerate(pts):
            cv2.circle(canvas, (x, y), 5, (0, 255, 255), -1)
            cv2.putText(canvas, str(i + 1), (x + 8, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2)
        cx, cy = int(np.mean([p[0] for p in pts])), int(np.mean([p[1] for p in pts]))
        cv2.putText(canvas, f"EDITING: {curr_lid}", (cx - 30, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 2)

    # 4. Top Header Banner
    cv2.rectangle(canvas, (0, 0), (DISPLAY_SIZE[0], 52), (15, 23, 42), -1)
    cv2.line(canvas, (0, 52), (DISPLAY_SIZE[0], 52), (51, 65, 85), 1)

    pts_status = f"Point {len(current_points)}/4" if current_points else ("4 points saved (Click to re-mark)" if curr_lid in completed_lanes else "Click 4 corners")
    status_text = f"[{selected_lane_idx + 1}/8] ACTIVE: {curr_lid} ({curr_desc}) - {pts_status}"
    sub_text = "Left-Click: Mark point | 1-8: Switch Lane | 'r': Reset lane | 'u': Undo | 'n'/'p': Frame +/- | 's': Save | 'q': Exit"

    cv2.putText(canvas, status_text, (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 255, 255), 1)
    cv2.putText(canvas, sub_text, (12, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (148, 163, 184), 1)

    # 5. Bottom Status Bar (Cursor Coordinates & Frame)
    cv2.rectangle(canvas, (0, DISPLAY_SIZE[1] - 24), (DISPLAY_SIZE[0], DISPLAY_SIZE[1]), (15, 23, 42), -1)
    cv2.line(canvas, (0, DISPLAY_SIZE[1] - 24), (DISPLAY_SIZE[0], DISPLAY_SIZE[1] - 24), (51, 65, 85), 1)
    bot_info = f"Cursor: ({mouse_x}, {mouse_y}) | Frame: {current_frame_pos}/{total_frames} | 'v': Toggle AI Boxes ({'ON' if show_detections else 'OFF'})"
    cv2.putText(canvas, bot_info, (12, DISPLAY_SIZE[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (203, 213, 225), 1)

    cv2.imshow("SUMO 8-Lane Polygon Calibration", canvas)

def click_event(event, x, y, flags, param):
    global current_points, selected_lane_idx, mouse_x, mouse_y
    mouse_x, mouse_y = x, y
    if event == cv2.EVENT_MOUSEMOVE:
        redraw()
    elif event == cv2.EVENT_LBUTTONDOWN and selected_lane_idx < len(SUMO_LANES):
        current_points.append((x, y))
        curr_lid = SUMO_LANES[selected_lane_idx][0]
        print(f"[{curr_lid}] Point {len(current_points)}/4 -> ({x}, {y})")

        if len(current_points) == 4:
            completed_lanes[curr_lid] = list(current_points)
            print(f"[✓] Saved 4 points for '{curr_lid}': {completed_lanes[curr_lid]}")
            current_points = []
            save_config_file()
            # Move to next lane automatically
            selected_lane_idx = (selected_lane_idx + 1) % len(SUMO_LANES)
            print(f"--> Next lane to edit: {SUMO_LANES[selected_lane_idx][0]}")
        redraw()

def save_config_file():
    with open(JSON_OUTPUT_PATH, "w") as f:
        json.dump(completed_lanes, f, indent=2)
    print(f"[*] Synced configuration to: {JSON_OUTPUT_PATH}")

cv2.namedWindow("SUMO 8-Lane Polygon Calibration", cv2.WINDOW_NORMAL)
cv2.resizeWindow("SUMO 8-Lane Polygon Calibration", *DISPLAY_SIZE)
cv2.setMouseCallback("SUMO 8-Lane Polygon Calibration", click_event)
redraw()

print("=" * 70)
print(f"[*] SUMO 8-Lane Interactive Calibration & Review")
print(f"[*] Source Video: {VIDEO_PATH}")
print(f"[*] Keys:")
print(f"    • 1 to 8   : Select and jump directly to lane (1:n_t_0, 2:n_t_1, 3:s_t_0, ...)")
print(f"    • Left-Click: Click 4 corner points for active lane")
print(f"    • 'u' / 'z' : Undo last point")
print(f"    • 'r'       : Reset active lane points")
print(f"    • 'n' / 'p' : Seek video forward / backward by 50 frames")
print(f"    • 'v'       : Toggle YOLO vehicle detection boxes")
print(f"    • 's' / 'q' : Save and Exit")
print("=" * 70)

while True:
    key = cv2.waitKey(25) & 0xFF
    if ord("1") <= key <= ord("8"):
        selected_lane_idx = key - ord("1")
        current_points = []
        print(f"[*] Jumped to lane: {SUMO_LANES[selected_lane_idx][0]} ({SUMO_LANES[selected_lane_idx][1]})")
        redraw()
    elif key == ord("u") or key == ord("z"):
        if current_points:
            p = current_points.pop()
            print(f"[*] Undid point ({p[0]}, {p[1]})")
        redraw()
    elif key == ord("r"):
        current_points = []
        curr_lid = SUMO_LANES[selected_lane_idx][0]
        completed_lanes.pop(curr_lid, None)
        save_config_file()
        print(f"[*] Reset points for '{curr_lid}'. Click 4 points to redefine.")
        redraw()
    elif key == ord("n"): # Next frame
        current_frame_pos = min(total_frames - 1, current_frame_pos + 50)
        base_frame = get_current_frame(current_frame_pos)
        if show_detections:
            detection_boxes = run_detector_on_frame(base_frame)
        redraw()
    elif key == ord("p"): # Prev frame
        current_frame_pos = max(0, current_frame_pos - 50)
        base_frame = get_current_frame(current_frame_pos)
        if show_detections:
            detection_boxes = run_detector_on_frame(base_frame)
        redraw()
    elif key == ord("v"): # Toggle detections
        show_detections = not show_detections
        if show_detections:
            detection_boxes = run_detector_on_frame(base_frame)
        redraw()
    elif key == ord("s") or key == ord("q"):
        save_config_file()
        print("[*] Saved and exited.")
        break

cap.release()
cv2.destroyAllWindows()