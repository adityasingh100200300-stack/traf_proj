import React, { useState, useEffect, useRef } from "react";
import { 
  ShieldAlert, 
  Activity, 
  Zap, 
  Car, 
  Timer, 
  AlertTriangle, 
  Radio, 
  CheckCircle2, 
  RefreshCw 
} from "lucide-react";

export default function TrafficControlDashboard() {
  const [telemetry, setTelemetry] = useState({});
  const [activePhase, setActivePhase] = useState("north_south");
  const [congestion, setCongestion] = useState(0);
  const [emergencyActive, setEmergencyActive] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [selectedAlgorithm, setSelectedAlgorithm] = useState("queue_based");
  const [optimizing, setOptimizing] = useState(false);
  const [cycleLength, setCycleLength] = useState(60);

  const socketRef = useRef(null);

  // 1. WebSocket Live Stream Connection
  useEffect(() => {
    const connectWs = () => {
      const socket = new WebSocket("ws://127.0.0.1:8000/ws/traffic-stream/INT-001");
      socketRef.current = socket;

      socket.onopen = () => setWsConnected(true);
      socket.onclose = () => {
        setWsConnected(false);
        setTimeout(connectWs, 3000); // Reconnect loop
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "emergency_override") {
            setEmergencyActive(data.active);
            if (data.override_phase) setActivePhase(data.override_phase);
          } else if (data.traffic) {
            setTelemetry(data.traffic);
            setCongestion(data.congestion_score || 0);
          }
        } catch (err) {
          console.error("Failed to parse incoming WebSocket message", err);
        }
      };
    };

    connectWs();
    return () => socketRef.current?.close();
  }, []);

  // 2. Trigger Signal Optimization
  const handleOptimize = async () => {
    setOptimizing(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/signals/INT-001/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ algorithm: selectedAlgorithm })
      });
      const data = await res.json();
      if (data.next_phase) setActivePhase(data.next_phase);
      if (data.cycle_length) setCycleLength(data.cycle_length);
    } catch (err) {
      console.error("Optimization failed:", err);
    } finally {
      setOptimizing(false);
    }
  };

  // 3. Emergency Vehicle Priority Trigger
  const handleEmergencyDispatch = async () => {
    try {
      await fetch("http://127.0.0.1:8000/api/v1/emergency/corridor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vehicle_id: "AMB-911",
          vehicle_type: "ambulance",
          current_position: [12.9700, 77.5946],
          route_coordinates: [[12.9700, 77.5946], [12.9750, 77.5946]],
          priority_level: 1
        })
      });
    } catch (err) {
      console.error("Emergency dispatch failed:", err);
    }
  };

  const getCongestionBadge = (score) => {
    if (score > 70) return { bg: "bg-red-500/20 text-red-400 border-red-500/30", label: "Critical Bottleneck" };
    if (score > 40) return { bg: "bg-amber-500/20 text-amber-400 border-amber-500/30", label: "Moderate Density" };
    return { bg: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30", label: "Free Flow" };
  };

  const badge = getCongestionBadge(congestion);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 font-sans">
      {/* Header */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center pb-6 border-b border-slate-800 gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">Adaptive Traffic Management Center</h1>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-mono">
              INT-001 (Central Junction)
            </span>
          </div>
          <p className="text-slate-400 text-sm mt-1">Real-time edge telemetry, dynamic signal scheduling & digital twin synchronization</p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-slate-900 border border-slate-800 text-xs">
            <span className={`h-2 w-2 rounded-full ${wsConnected ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
            <span className="text-slate-300 font-mono">{wsConnected ? "STREAM LIVE" : "DISCONNECTED"}</span>
          </div>

          <button
            onClick={handleEmergencyDispatch}
            className={`flex items-center gap-2 px-4 py-2 rounded-md font-semibold text-sm transition shadow-lg ${
              emergencyActive 
                ? 'bg-red-600 hover:bg-red-700 text-white animate-pulse' 
                : 'bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30'
            }`}
          >
            <ShieldAlert className="w-4 h-4" />
            {emergencyActive ? "Corridor Priority Locked" : "Dispatch Emergency Vehicle"}
          </button>
        </div>
      </header>

      {/* Emergency Alert Banner */}
      {emergencyActive && (
        <div className="mt-6 p-4 rounded-lg bg-red-950/50 border border-red-500/50 flex items-center justify-between animate-fade-in">
          <div className="flex items-center gap-3">
            <AlertTriangle className="text-red-400 w-5 h-5 animate-bounce" />
            <div>
              <p className="font-semibold text-red-200 text-sm">Emergency Vehicle Green Corridor Active</p>
              <p className="text-xs text-red-400">AMB-911 approaching. Signals overridden to force continuous green along transit vector.</p>
            </div>
          </div>
          <span className="text-xs font-mono bg-red-900/60 px-2 py-1 rounded border border-red-700 text-red-200 uppercase">
            Priority Lockout: {activePhase}
          </span>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
        
        {/* Signal & Congestion Overview Card */}
        <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-xl flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                <Radio className="w-4 h-4 text-indigo-400" /> Active Signal State
              </h2>
              <span className={`text-xs px-2.5 py-1 rounded-full border ${badge.bg}`}>
                {badge.label}
              </span>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between items-center p-3 rounded-lg bg-slate-950 border border-slate-800/80">
                <span className="text-sm text-slate-300">North-South Approach</span>
                <span className={`px-3 py-1 rounded text-xs font-bold font-mono tracking-wider ${
                  activePhase === "north_south" 
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40" 
                    : "bg-red-500/20 text-red-400 border border-red-500/40"
                }`}>
                  {activePhase === "north_south" ? "🟢 GREEN" : "🔴 RED"}
                </span>
              </div>

              <div className="flex justify-between items-center p-3 rounded-lg bg-slate-950 border border-slate-800/80">
                <span className="text-sm text-slate-300">East-West Approach</span>
                <span className={`px-3 py-1 rounded text-xs font-bold font-mono tracking-wider ${
                  activePhase === "east_west" 
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40" 
                    : "bg-red-500/20 text-red-400 border border-red-500/40"
                }`}>
                  {activePhase === "east_west" ? "🟢 GREEN" : "🔴 RED"}
                </span>
              </div>
            </div>

            <div className="mt-6">
              <div className="flex justify-between text-xs mb-1.5">
                <span className="text-slate-400">Congestion Severity Index</span>
                <span className="font-mono font-bold">{congestion}%</span>
              </div>
              <div className="w-full bg-slate-950 h-2.5 rounded-full overflow-hidden border border-slate-800">
                <div 
                  className={`h-full transition-all duration-500 ${
                    congestion > 70 ? 'bg-red-500' : congestion > 40 ? 'bg-amber-500' : 'bg-emerald-500'
                  }`}
                  style={{ width: `${Math.min(100, Math.max(0, congestion))}%` }}
                />
              </div>
            </div>
          </div>

          <div className="pt-6 border-t border-slate-800/60 mt-6 flex justify-between items-center text-xs text-slate-400">
            <span>Cycle Length: <strong className="text-slate-200 font-mono">{cycleLength}s</strong></span>
            <span>Controller: <strong className="text-slate-200 uppercase">{selectedAlgorithm}</strong></span>
          </div>
        </div>

        {/* Optimizer Control Card */}
        <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-xl flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-400" /> Optimization Engine
              </h2>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Dynamically computes green splits based on real-time lane queue density and critical flow ratios.
            </p>

            <div className="mt-4 space-y-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Active Optimization Model</label>
                <select 
                  value={selectedAlgorithm}
                  onChange={(e) => setSelectedAlgorithm(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-md p-2 text-xs font-mono focus:outline-none focus:border-indigo-500 text-slate-200"
                >
                  <option value="queue_based">Queue-Density Proportional Allocation</option>
                  <option value="webster">Webster's Method (Critical Flow Saturation)</option>
                  <option value="rl">Deep Q-Network (Trained DQN Policy)</option>
                </select>
              </div>

              <button
                onClick={handleOptimize}
                disabled={optimizing}
                className="w-full py-2.5 px-4 rounded-md bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-medium text-xs flex items-center justify-center gap-2 transition"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${optimizing ? 'animate-spin' : ''}`} />
                {optimizing ? "Evaluating Phase Timings..." : "Trigger Manual Optimization"}
              </button>
            </div>
          </div>

          <div className="p-3 bg-slate-950 rounded-lg border border-slate-800/80 text-xs text-slate-400 flex items-center gap-2 mt-4">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>Safety constraints active: Min Green 10s, Max Green 60s.</span>
          </div>
        </div>

        {/* 2D Intersection Layout Diagram */}
        <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-xl flex flex-col items-center justify-center relative min-h-[260px]">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 absolute top-4 left-4">
            Topology Schema
          </h2>

          <div className="relative w-48 h-48 border border-slate-800 rounded-lg flex items-center justify-center bg-slate-950">
            {/* North */}
            <div className="absolute top-1 flex flex-col items-center">
              <span className="text-[10px] text-slate-400 font-mono">NORTH (n_t)</span>
              <span className={`h-2 w-6 rounded ${activePhase === "north_south" ? 'bg-emerald-500' : 'bg-red-500'}`} />
            </div>

            {/* South */}
            <div className="absolute bottom-1 flex flex-col items-center">
              <span className={`h-2 w-6 rounded ${activePhase === "north_south" ? 'bg-emerald-500' : 'bg-red-500'}`} />
              <span className="text-[10px] text-slate-400 font-mono">SOUTH (s_t)</span>
            </div>

            {/* West */}
            <div className="absolute left-1 flex items-center gap-1">
              <span className="text-[10px] text-slate-400 font-mono rotate-90">WEST</span>
              <span className={`w-2 h-6 rounded ${activePhase === "east_west" ? 'bg-emerald-500' : 'bg-red-500'}`} />
            </div>

            {/* East */}
            <div className="absolute right-1 flex items-center gap-1">
              <span className={`w-2 h-6 rounded ${activePhase === "east_west" ? 'bg-emerald-500' : 'bg-red-500'}`} />
              <span className="text-[10px] text-slate-400 font-mono -rotate-90">EAST</span>
            </div>

            <div className="text-xs font-mono font-bold text-slate-600">JCT 't'</div>
          </div>
        </div>
      </div>

      {/* Lane Telemetry Feed Grid */}
      <div className="mt-6 bg-slate-900/60 border border-slate-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
          <Car className="w-4 h-4 text-emerald-400" /> Real-Time Inflow Telemetry
        </h2>

        {Object.keys(telemetry).length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(telemetry).map(([lane, data]) => (
              <div key={lane} className="p-3 bg-slate-950 border border-slate-800/80 rounded-lg">
                <div className="flex justify-between items-center mb-2">
                  <span className="font-mono text-xs text-indigo-400 font-bold">{lane}</span>
                  <span className="text-[10px] text-slate-500 font-mono">{data.speed} km/h</span>
                </div>
                <div className="text-lg font-bold text-slate-100 font-mono">
                  {data.vehicles} <span className="text-xs text-slate-500 font-normal">vehicles</span>
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  Queue: <span className="text-slate-200 font-mono font-semibold">{data.queue}m</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-slate-500 text-xs font-mono">
            Waiting for YOLO video ingestion or mock stream data...
          </div>
        )}
      </div>
    </div>
  );
}