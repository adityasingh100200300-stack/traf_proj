import time
import random
import datetime
import httpx

API_URL = "http://127.0.0.1:8000/api/v1/telemetry/ingest"
INTERSECTION_ID = "INT-001"
LANES = ["n_t_0", "n_t_1", "s_t_0", "s_t_1", "e_t_0", "e_t_1", "w_t_0", "w_t_1"]

def get_mock_frame(surge_ns: bool = True):
    lanes_data = []
    for lane in LANES:
        is_ns = lane.startswith("n_") or lane.startswith("s_")
        
        if is_ns and surge_ns:
            # Heavy North-South queue
            count = random.randint(18, 30)
            speed = round(random.uniform(8.0, 18.0), 1)
            queue = round(count * 1.6, 1)
            occ = round(min(count / 30.0, 0.95), 2)
        else:
            # Light traffic
            count = random.randint(2, 6)
            speed = round(random.uniform(35.0, 48.0), 1)
            queue = round(random.uniform(0.0, 4.0), 1)
            occ = round(random.uniform(0.05, 0.20), 2)

        lanes_data.append({
            "lane_id": lane,
            "vehicle_count": count,
            "average_speed": speed,
            "queue_length": queue,
            "occupancy": occ,
            "vehicle_classes": {"car": int(count * 0.8), "truck": max(0, int(count * 0.2))}
        })
    
    return {
        "intersection_id": INTERSECTION_ID,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "lanes": lanes_data
    }

def start_stream():
    print(f"[*] Streaming mock telemetry to {API_URL} (Press CTRL+C to stop)")
    with httpx.Client(timeout=5.0) as client:
        step = 0
        while True:
            step += 1
            # Alternate surge between North-South and East-West every 10 steps
            surge_north_south = (step % 20) < 10
            payload = get_mock_frame(surge_ns=surge_north_south)
            
            try:
                res = client.post(API_URL, json=payload)
                data = res.json()
                active_surge = "North-South" if surge_north_south else "East-West"
                print(f"[Step {step:03d}] Surge: {active_surge:<11} | Congestion: {data.get('congestion_score', 0):>5.1f}% | Ingestion: {data.get('status')}")
            except Exception as e:
                print(f"[!] Stream error: {e}")
            
            time.sleep(1.5)

if __name__ == "__main__":
    start_stream()