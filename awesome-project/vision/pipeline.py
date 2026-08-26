import cv2
import time
from ultralytics import YOLO
from vision.publisher import VisionTelemetryPublisher

def run_yolo_stream(video_path: str = "sample_intersection.mp4", intersection_id: str = "INT-001"):
    model = YOLO("yolov8n.pt")  # Downloads lightweight YOLOv8 nano model
    publisher = VisionTelemetryPublisher(api_url="http://127.0.0.1:8000/api/v1/telemetry/ingest")
    cap = cv2.VideoCapture(video_path)

    lanes = ["n_t_0", "n_t_1", "s_t_0", "s_t_1", "e_t_0", "e_t_1", "w_t_0", "w_t_1"]

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

    cap.release()

if __name__ == "__main__":
    run_yolo_stream()