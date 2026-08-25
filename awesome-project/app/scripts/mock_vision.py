import time
import random
import datetime
import httpx

API_URL = "http://127.0.0.1:8000/api/v1/telemetry/ingest"
INTERSECTION_ID = "INT-001"

LANES = ["north_straight", "north_left", "south_straight", "east_straight", "west_straight"]

PATTERNS = {
    "low": {"count_range": (1, 5), "speed_range": (40.0, 50.0), "queue_range": (0.0, 2.0), "occ_range": (0.05, 0.15)},
    "normal": {"count_range": (6, 15), "speed_range": (28.0, 42.0), "queue_range": (2.0, 8.0), "occ_range": (0.20, 0.45)},
    "rush_hour": {"count_range": (20, 40), "speed_range": (10.0, 25.0), "queue_range": (12.0, 30.0), "occ_range": (0.60, 0.85)},
    "heavy_congestion": {"count_range": (40, 60), "speed_range": (2.0, 10.0), "queue_range": (30.0, 50.0), "occ_range": (0.85, 0.98)},
}

def generate_lane_data(lane_id: str, mode: str) -> dict:
    cfg = PATTERNS.get(mode, PATTERNS["normal"])
    
    # Introduce random fluctuations
    count = random.randint(*cfg["count_range"])
    speed = round(random.uniform(*cfg["speed_range"]), 1)
    queue = round(random.uniform(*cfg["queue_range"]), 1)
    occupancy = round(random.uniform(*cfg["occ_range"]), 2)

    return {
        "lane_id": lane_id,
        "vehicle_count": count,
        "average_speed": speed,
        "queue_length": queue,
        "occupancy": min(occupancy, 1.0),
        "vehicle_classes": {
            "car": int(count * 0.75),
            "bus": int(count * 0.15),
            "truck": int(count * 0.10)
        }
    }

def run_simulation():
    print(f"[*] Starting Mock Vision Generator targeting: {API_URL}")
    print("[*] Simulating modes: Low -> Normal -> Rush Hour -> Congestion -> Normal")

    sequence = [
        ("low", 3),
        ("normal", 4),
        ("rush_hour", 4),
        ("heavy_congestion", 4),
        ("normal", 3)
    ]

    with httpx.Client(timeout=5.0) as client:
        for mode, iterations in sequence:
            print(f"\n--- [MODE: {mode.upper()}] ---")
            for i in range(iterations):
                lanes_payload = [generate_lane_data(lane, mode) for lane in LANES]
                payload = {
                    "intersection_id": INTERSECTION_ID,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "lanes": lanes_payload
                }

                try:
                    response = client.post(API_URL, json=payload)
                    if response.status_code == 200:
                        data = response.json()
                        print(f"[{i+1}/{iterations}] Sent -> Status: {data['status']} | Congestion Score: {data['congestion_score']}%")
                    else:
                        print(f"[!] Ingestion failed [{response.status_code}]: {response.text}")
                except Exception as e:
                    print(f"[!] Could not connect to API: {e}")

                time.sleep(1.5)

if __name__ == "__main__":
    run_simulation()