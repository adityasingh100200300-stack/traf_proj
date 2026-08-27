import asyncio
import json
import os
import sys
import time
from datetime import datetime
import httpx
import websockets

API_URL = "http://127.0.0.1:8000/api/v1"
WS_URL = "ws://127.0.0.1:8000/ws/traffic-stream/INT-001"

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
BG_DARK = "\033[48;5;234m"
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"

# In-memory dashboard state
state = {
    "connected": False,
    "last_update": "Never",
    "congestion": 0.0,
    "active_phase": "north_south",
    "emergency_active": False,
    "emergency_info": "",
    "algorithm": "rl_dqn",
    "cycle_length": 60,
    "traffic": {
        "n_t_0": {"vehicles": 0, "speed": 0.0, "queue": 0.0, "occupancy": 0.0},
        "n_t_1": {"vehicles": 0, "speed": 0.0, "queue": 0.0, "occupancy": 0.0},
        "s_t_0": {"vehicles": 0, "speed": 0.0, "queue": 0.0, "occupancy": 0.0},
        "s_t_1": {"vehicles": 0, "speed": 0.0, "queue": 0.0, "occupancy": 0.0},
        "e_t_0": {"vehicles": 0, "speed": 0.0, "queue": 0.0, "occupancy": 0.0},
        "e_t_1": {"vehicles": 0, "speed": 0.0, "queue": 0.0, "occupancy": 0.0},
        "w_t_0": {"vehicles": 0, "speed": 0.0, "queue": 0.0, "occupancy": 0.0},
        "w_t_1": {"vehicles": 0, "speed": 0.0, "queue": 0.0, "occupancy": 0.0},
    },
    "event_logs": []
}

def log_event(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    state["event_logs"].append(f"[{timestamp}] {msg}")
    if len(state["event_logs"]) > 5:
        state["event_logs"].pop(0)

def render_bar(val: float, max_val: float = 50.0, length: int = 10, color: str = GREEN) -> str:
    filled = int(min(max(val / max_val, 0.0), 1.0) * length)
    empty = length - filled
    return f"{color}{'█' * filled}{DIM}{'░' * empty}{RESET}"

def render_dashboard():
    # Move cursor to home and clear
    output = ["\033[H"]
    
    # 1. Header Banner
    conn_badge = f"{GREEN}● LIVE STREAM{RESET}" if state["connected"] else f"{RED}○ RECONNECTING{RESET}"
    emg_banner = f" {BG_RED}{WHITE}{BOLD} 🚨 EMERGENCY GREEN CORRIDOR ACTIVE 🚨 {RESET}" if state["emergency_active"] else ""
    
    output.append(f"{CYAN}╔══════════════════════════════════════════════════════════════════════════════════════════════╗{RESET}")
    output.append(f"{CYAN}║{RESET} {BOLD}🚦 ADAPTIVE TRAFFIC MANAGEMENT CENTER (TUI){RESET} {DIM}[INT-001]{RESET}         Status: {conn_badge} {emg_banner}{' ' * max(0, 10 - len(emg_banner))}{CYAN}║{RESET}")
    output.append(f"{CYAN}╠══════════════════════════════════════════════════════════════════════════════════════════════╣{RESET}")
    
    # Congestion Gauge
    cong = state["congestion"]
    c_color = RED if cong > 60 else YELLOW if cong > 30 else GREEN
    c_label = "CRITICAL" if cong > 60 else "MODERATE" if cong > 30 else "OPTIMAL"
    gauge_bar = render_bar(cong, max_val=100.0, length=24, color=c_color)
    
    output.append(f"{CYAN}║{RESET} Congestion Index: [{gauge_bar}] {c_color}{BOLD}{cong:>5.1f}%{RESET} ({c_color}{c_label}{RESET}) │ Active Policy: {MAGENTA}{BOLD}{state['algorithm'].upper()}{RESET} │ Cycle: {YELLOW}{state['cycle_length']}s{RESET} {CYAN}║{RESET}")
    output.append(f"{CYAN}╠══════════════════════════════════════╦═══════════════════════════════════════════════════════╣{RESET}")
    
    # 2. Main 2-Column Section: Topology (Left) | 8-Lane Telemetry (Right)
    ns_is_green = state["active_phase"] == "north_south"
    ns_signal = f"{GREEN}{BOLD}🟢 GREEN{RESET}" if ns_is_green else f"{RED}{BOLD}🔴 RED  {RESET}"
    ew_signal = f"{RED}{BOLD}🔴 RED  {RESET}" if ns_is_green else f"{GREEN}{BOLD}🟢 GREEN{RESET}"

    # Lane rows for right column
    t = state["traffic"]
    def format_lane_row(lid: str) -> str:
        d = t.get(lid, {"vehicles": 0, "speed": 0.0, "queue": 0.0, "occupancy": 0.0})
        v = d.get("vehicles", 0)
        s = d.get("speed", 0.0)
        q = d.get("queue", 0.0)
        s_col = GREEN if s >= 35 else YELLOW if s >= 20 else RED
        q_bar = render_bar(q, max_val=40.0, length=8, color=RED if q > 25 else YELLOW if q > 10 else GREEN)
        return f"{WHITE}{lid:<6}{RESET}│ {v:>2} veh │ {s_col}{s:>4.1f} km/h{RESET} │ [{q_bar}] {q:>4.1f}m"

    r0 = format_lane_row("n_t_0")
    r1 = format_lane_row("n_t_1")
    r2 = format_lane_row("s_t_0")
    r3 = format_lane_row("s_t_1")
    r4 = format_lane_row("e_t_0")
    r5 = format_lane_row("e_t_1")
    r6 = format_lane_row("w_t_0")
    r7 = format_lane_row("w_t_1")

    output.append(f"{CYAN}║{RESET} {BOLD}2D TOPOLOGY & ACTIVE LIGHTS{RESET}          {CYAN}║{RESET} {BOLD}LIVE 8-LANE TELEMETRY (SUMO / YOLO VIDEO){RESET}         {CYAN}║{RESET}")
    output.append(f"{CYAN}║{RESET}           NORTH APPROACH             {CYAN}║{RESET} LANE  │ COUNT  │ SPEED      │ QUEUE BAR (m)       {CYAN}║{RESET}")
    output.append(f"{CYAN}║{RESET}              [{ns_signal}]              {CYAN}║{RESET} ──────┼────────┼────────────┼──────────────────── {CYAN}║{RESET}")
    output.append(f"{CYAN}║{RESET}                  ││                  {CYAN}║{RESET} {r0} {CYAN}║{RESET}")
    output.append(f"{CYAN}║{RESET}                  ││                  {CYAN}║{RESET} {r1} {CYAN}║{RESET}")
    output.append(f"{CYAN}║{RESET}  WEST            ││             EAST {CYAN}║{RESET} {r2} {CYAN}║{RESET}")
    output.append(f"{CYAN}║{RESET} [{ew_signal}] ───────┼┼─────── [{ew_signal}] {CYAN}║{RESET} {r3} {CYAN}║{RESET}")
    output.append(f"{CYAN}║{RESET} (w_t_0/1)        ││        (e_t_0/1) {CYAN}║{RESET} {r4} {CYAN}║{RESET}")
    output.append(f"{CYAN}║{RESET}                  ││                  {CYAN}║{RESET} {r5} {CYAN}║{RESET}")
    output.append(f"{CYAN}║{RESET}                  ││                  {CYAN}║{RESET} {r6} {CYAN}║{RESET}")
    output.append(f"{CYAN}║{RESET}              [{ns_signal}]              {CYAN}║{RESET} {r7} {CYAN}║{RESET}")
    output.append(f"{CYAN}║{RESET}           SOUTH APPROACH             {CYAN}║{RESET}                                                     {CYAN}║{RESET}")
    output.append(f"{CYAN}╠══════════════════════════════════════╩═══════════════════════════════════════════════════════╣{RESET}")
    
    # 3. Event Log
    output.append(f"{CYAN}║{RESET} {BOLD}RECENT TELEMETRY & OPTIMIZER EVENTS:{RESET}{' ' * 57}{CYAN}║{RESET}")
    for log in state["event_logs"][-3:]:
        output.append(f"{CYAN}║{RESET}  {DIM}•{RESET} {log:<87} {CYAN}║{RESET}")
    while len(state["event_logs"]) < 3:
        output.append(f"{CYAN}║{RESET}  {DIM}• Waiting for simulation / video telemetry frames...{RESET}{' ' * 40}{CYAN}║{RESET}")
        
    output.append(f"{CYAN}╚══════════════════════════════════════════════════════════════════════════════════════════════╝{RESET}")
    output.append(f"{DIM}Commands: Run simulation in other tab: [python run_sumo_rl.py] or [python vision/lane_mapper.py]{RESET}")
    output.append(f"{DIM}Press CTRL+C to exit TUI dashboard.{RESET}")

    sys.stdout.write("\n".join(output) + "\n")
    sys.stdout.flush()

async def ws_listener():
    while True:
        try:
            async with websockets.connect(WS_URL) as ws:
                state["connected"] = True
                log_event("Connected to live telemetry WebSocket stream.")
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    msg_type = data.get("type", "traffic_update")
                    
                    if msg_type == "emergency_override":
                        state["emergency_active"] = data.get("active", True)
                        state["active_phase"] = data.get("override_phase", state["active_phase"])
                        log_event(f"EMERGENCY: Priority Green locked on [{state['active_phase']}]")
                    elif msg_type == "emergency_clear":
                        state["emergency_active"] = False
                        log_event("EMERGENCY: Priority corridor cleared.")
                    elif "traffic" in data:
                        state["traffic"].update(data["traffic"])
                        state["congestion"] = data.get("congestion_score", state["congestion"])
                        if "active_phase" in data:
                            state["active_phase"] = data["active_phase"]
                        log_event(f"Frame Ingest: {len(data['traffic'])} lanes | Congestion: {state['congestion']:.1f}%")
        except Exception as e:
            state["connected"] = False
            await asyncio.sleep(2.0)

async def tui_loop():
    # Clear screen on start
    os.system("cls" if os.name == "nt" else "clear")
    while True:
        render_dashboard()
        await asyncio.sleep(0.5)

async def main():
    log_event("Initializing ITMS TUI Dashboard...")
    await asyncio.gather(
        ws_listener(),
        tui_loop()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] TUI Dashboard closed.")
