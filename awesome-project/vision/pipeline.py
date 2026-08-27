import sys
import os
import cv2
import time

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from vision.publisher import VisionTelemetryPublisher
except ImportError:
    from publisher import VisionTelemetryPublisher

from ultralytics import YOLO

def resolve_video_path(custom_path: str = None):
    if custom_path and os.path.exists(custom_path):
        return custom_path
    if len(sys.argv) > 1:
        return sys.argv[1]
    
    candidates = [
        "test_traffic.mp4",
        "traffic.mp4",
        "sample_intersection.mp4",
        os.path.join(ROOT_DIR, "test_traffic.mp4"),
        os.path.join(ROOT_DIR, "traffic.mp4")
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return "test_traffic.mp4"

def run_yolo_stream(video_path: str = None, intersection_id: str = "INT-001"):
    video_path = resolve_video_path(video_path)
    model = YOLO("yolov8n.pt")  # Downloads lightweight YOLOv8 nano model
    publisher = VisionTelemetryPublisher(api_url="http://127.0.0.1:8000/api/v1/telemetry/ingest")
    cap = cv2.VideoCapture(video_path)


    lanes = ["n_t_0", "n_t_1", "s_t_0", "s_t_1", "e_t_0", "e_t_1", "w_t_0", "w_t_1"]

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Track vehicles across frames
            results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
            boxes = results[0].boxes

            # Count detected vehicles (class 2: car, 5: bus, 7: truck)
            count = sum(1 for b in boxes if int(b.cls[0]) in [2, 5, 7]) if boxes is not None else 0

            # Build payload for the 8 lanes matching SUMO
            lanes_payload = []
            for lane in lanes:
                lane_count = max(1, count // len(lanes))
                lanes_payload.append({
                    "lane_id": lane,
                    "vehicle_count": lane_count,
                    "average_speed": max(15.0, 50.0 - lane_count * 2.0),
                    "queue_length": float(lane_count * 4.5),
                    "occupancy": min(1.0, lane_count / 15.0)
                })

            # Post telemetry to backend
            publisher.publish_frame_metrics(intersection_id, lanes_payload)
            time.sleep(1.0)
    finally:
        cap.release()
        publisher.close()

if __name__ == "__main__":
    run_yolo_stream()