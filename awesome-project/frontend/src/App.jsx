import React, { useState, useEffect, useRef, useMemo } from "react";
import { 
  Activity, 
  Zap, 
  Car, 
  Timer, 
  Radio, 
  RefreshCw,
  ArrowDown,
  ArrowRight,
  Sparkles,
  Navigation,
  Gauge,
  Compass,
  Layers,
  ChevronRight,
  Video,
  AlertTriangle,
  ShieldCheck
} from "lucide-react";

export default function TrafficControlDashboard() {
  const [telemetry, setTelemetry] = useState({});
  const [activePhase, setActivePhase] = useState("north_south");
  const [targetPhase, setTargetPhase] = useState(null);
  const transitionTimeout = useRef(null);

  const triggerPhaseChange = (newPhase) => {
    if (newPhase === activePhase || newPhase === targetPhase) return;
    if (transitionTimeout.current) clearTimeout(transitionTimeout.current);
    setTargetPhase(newPhase);
    transitionTimeout.current = setTimeout(() => {
      setActivePhase(newPhase);
      setTargetPhase(null);
      transitionTimeout.current = null;
    }, 3000); // 3-second yellow transition
  };
  const [congestion, setCongestion] = useState(0);
  const [wsConnected, setWsConnected] = useState(false);
  const [selectedAlgorithm, setSelectedAlgorithm] = useState("rl");
  const [optimizing, setOptimizing] = useState(false);
  const [cycleLength, setCycleLength] = useState(60);
  const [autoOptimize, setAutoOptimize] = useState(true);
  const [decisionCountdown, setDecisionCountdown] = useState(10);
  const [phaseElapsed, setPhaseElapsed] = useState(0);
  const [phaseHistory, setPhaseHistory] = useState([]);
  const [videoTiming, setVideoTiming] = useState({ frame: 0, timeSec: 0, totalSec: 300, timestamp: "00:00 / 05:00" });
  const [failsafeActive, setFailsafeActive] = useState(false);
  const [failsafeMsg, setFailsafeMsg] = useState("");
  const [feedStatus, setFeedStatus] = useState("ACTIVE");

  const socketRef = useRef(null);

  const selectedAlgoRef = useRef(selectedAlgorithm);
  selectedAlgoRef.current = selectedAlgorithm;

  // Reset phase elapsed timer when phase changes
  useEffect(() => {
    setPhaseElapsed(0);
  }, [activePhase]);

  // 1. Initial State Fetch & WebSocket Live Stream Connection
  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/v1/intersections/INT-001/status")
      .then(res => res.json())
      .then(data => {
        if (data.active_phase) {
          setActivePhase(data.active_phase);
          setTargetPhase(null);
        }
        if (data.congestion_score !== undefined) setCongestion(data.congestion_score);
        if (data.cycle_length) setCycleLength(data.cycle_length);
        if (data.lanes && Object.keys(data.lanes).length > 0) setTelemetry(data.lanes);
        if (data.failsafe_active !== undefined) setFailsafeActive(data.failsafe_active);
        if (data.feed_status) setFeedStatus(data.feed_status);
      })
      .catch(err => console.debug("Initial status fetch skipped:", err));

    const connectWs = () => {
      const socket = new WebSocket("ws://127.0.0.1:8000/ws/traffic-stream/INT-001");
      socketRef.current = socket;

      socket.onopen = () => setWsConnected(true);
      socket.onclose = () => {
        setWsConnected(false);
        setTimeout(connectWs, 2000);
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "phase_override") {
            if (data.active_phase) triggerPhaseChange(data.active_phase);
            setPhaseHistory(prev => [`[${new Date().toLocaleTimeString()}] Phase -> ${data.active_phase.toUpperCase()} (${data.algorithm || "AI"})`, ...prev.slice(0, 4)]);
          } else if (data.traffic) {
            setTelemetry(data.traffic);
            setCongestion(data.congestion_score || 0);
            if (data.active_phase) triggerPhaseChange(data.active_phase);
            if (typeof data.frame_number === "number" && data.frame_number > 0) {
              setVideoTiming(prev => ({
                frame: data.frame_number,
                timeSec: data.video_time_seconds !== undefined && data.video_time_seconds !== null ? data.video_time_seconds : prev.timeSec,
                totalSec: data.total_duration_seconds !== undefined && data.total_duration_seconds !== null ? data.total_duration_seconds : prev.totalSec,
                timestamp: data.video_timestamp || prev.timestamp
              }));
            }
            if (data.feed_status) setFeedStatus(data.feed_status);
            if (data.failsafe_active !== undefined) {
              setFailsafeActive(data.failsafe_active);
              if (data.failsafe_message) setFailsafeMsg(data.failsafe_message);
            }
          }
        } catch (err) {
          console.error("Failed to parse incoming WebSocket message", err);
        }
      };
    };

    connectWs();
    return () => socketRef.current?.close();
  }, []);

  // 2. Trigger Signal Optimization (with 3.5s timeout safety)
  const handleOptimize = async () => {
    setOptimizing(true);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3500);

    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/signals/INT-001/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ algorithm: selectedAlgoRef.current }),
        signal: controller.signal
      });
      clearTimeout(timeoutId);
      if (res.ok) {
        const data = await res.json();
        if (data.next_phase) {
          triggerPhaseChange(data.next_phase);
          setPhaseHistory(prev => [`[${new Date().toLocaleTimeString()}] ${data.algorithm.toUpperCase()} -> ${data.next_phase.toUpperCase()} (${data.cycle_length}s)`, ...prev.slice(0, 4)]);
        }
        if (data.cycle_length) setCycleLength(data.cycle_length);
      }
    } catch (err) {
      console.debug("Optimization cycle non-blocking catch:", err);
    } finally {
      clearTimeout(timeoutId);
      setOptimizing(false);
    }
  };

  // 3. Autonomous Controller Master Loop (Always ticks continuously without pausing)
  useEffect(() => {
    const interval = setInterval(() => {
      setPhaseElapsed(prev => prev + 1);

      // Smooth real-time advance of the video playback timecounter
      setVideoTiming(prev => {
        if (failsafeActive || prev.timeSec >= prev.totalSec || prev.totalSec <= 0) return prev;
        const nextSec = prev.timeSec + 1;
        const cur_m = String(Math.floor(nextSec / 60)).padStart(2, '0');
        const cur_s = String(nextSec % 60).padStart(2, '0');
        const tot_m = String(Math.floor(prev.totalSec / 60)).padStart(2, '0');
        const tot_s = String(prev.totalSec % 60).padStart(2, '0');
        return {
          ...prev,
          timeSec: nextSec,
          frame: prev.frame + 10,
          timestamp: `${cur_m}:${cur_s} / ${tot_m}:${tot_s}`
        };
      });

      if (failsafeActive) {
        setDecisionCountdown(prev => {
          if (prev <= 1) {
            setActivePhase(p => {
              const next = p === "north_south" ? "east_west" : "north_south";
              setPhaseHistory(hist => [`[${new Date().toLocaleTimeString()}] Standard NEMA Fallback -> ${next.toUpperCase()} (30s)`, ...hist.slice(0, 4)]);
              return next;
            });
            return 30;
          }
          return prev - 1;
        });
      } else if (autoOptimize) {
        setDecisionCountdown(prev => {
          if (prev <= 1) {
            handleOptimize();
            return 10;
          }
          return prev - 1;
        });
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [autoOptimize, failsafeActive]);

  // 4. Manual Phase Override
  const handleManualPhaseOverride = async (phaseName) => {
    try {
      await fetch("http://127.0.0.1:8000/api/v1/signals/INT-001/override-phase", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phase: phaseName })
      });
      triggerPhaseChange(phaseName);
      setPhaseHistory(prev => [`[${new Date().toLocaleTimeString()}] Operator -> ${phaseName.toUpperCase()}`, ...prev.slice(0, 4)]);
    } catch (err) {
      console.error("Phase override failed:", err);
    }
  };

  const getPhaseStatus = (phaseGroup) => {
    if (phaseGroup === activePhase) {
      return targetPhase !== null ? "yellow" : "green";
    }
    return "red";
  };
  const nsStatus = getPhaseStatus("north_south");
  const ewStatus = getPhaseStatus("east_west");

  const getPhaseText = (status) => {
    if (status === "yellow") return "🟡 YELLOW";
    if (status === "green") return "🟢 GREEN";
    return "🔴 RED";
  };

  const getPhaseClass = (status) => {
    if (status === "yellow") return 'bg-yellow-500 text-slate-950 border border-yellow-400';
    if (status === "green") return 'bg-emerald-500 text-slate-950 border border-emerald-400';
    return 'bg-red-500/20 text-red-400 border border-red-500/40';
  };
  
  const getPhaseContainerClass = (status) => {
    if (status === "yellow") return 'bg-yellow-950/70 border-yellow-500/80 shadow-yellow-950/50';
    if (status === "green") return 'bg-emerald-950/70 border-emerald-500/80 shadow-emerald-950/50';
    return 'bg-slate-950/90 border-slate-800';
  };

  // 4 Approach Aggregations (8 SUMO Inflow Lanes)
  const approaches = useMemo(() => {
    const getLane = (id) => telemetry[id] || { vehicles: 0, queue: 0, speed: 0, occupancy: 0, classes: {} };

    const n_0 = getLane("n_t_0");
    const n_1 = getLane("n_t_1");
    const s_0 = getLane("s_t_0");
    const s_1 = getLane("s_t_1");
    const e_0 = getLane("e_t_0");
    const e_1 = getLane("e_t_1");
    const w_0 = getLane("w_t_0");
    const w_1 = getLane("w_t_1");

    return {
      north: {
        name: "North Corridor (n_t)",
        direction: "Inflow from North (Southbound)",
        phaseGroup: "north_south",
        status: nsStatus,
        lanes: [
          { id: "n_t_0", name: "Lane 0 (Thru)", data: n_0 },
          { id: "n_t_1", name: "Lane 1 (Left Turn)", data: n_1 }
        ],
        totalVehicles: (n_0.vehicles || 0) + (n_1.vehicles || 0),
        maxQueue: Math.max(n_0.queue || 0, n_1.queue || 0),
        avgSpeed: ((n_0.speed || 0) + (n_1.speed || 0)) / 2 || 0
      },
      south: {
        name: "South Corridor (s_t)",
        direction: "Inflow from South (Northbound)",
        phaseGroup: "north_south",
        status: nsStatus,
        lanes: [
          { id: "s_t_0", name: "Lane 0 (Thru)", data: s_0 },
          { id: "s_t_1", name: "Lane 1 (Left Turn)", data: s_1 }
        ],
        totalVehicles: (s_0.vehicles || 0) + (s_1.vehicles || 0),
        maxQueue: Math.max(s_0.queue || 0, s_1.queue || 0),
        avgSpeed: ((s_0.speed || 0) + (s_1.speed || 0)) / 2 || 0
      },
      east: {
        name: "East Corridor (e_t)",
        direction: "Inflow from East (Westbound)",
        phaseGroup: "east_west",
        status: ewStatus,
        lanes: [
          { id: "e_t_0", name: "Lane 0 (Thru)", data: e_0 },
          { id: "e_t_1", name: "Lane 1 (Left Turn)", data: e_1 }
        ],
        totalVehicles: (e_0.vehicles || 0) + (e_1.vehicles || 0),
        maxQueue: Math.max(e_0.queue || 0, e_1.queue || 0),
        avgSpeed: ((e_0.speed || 0) + (e_1.speed || 0)) / 2 || 0
      },
      west: {
        name: "West Corridor (w_t)",
        direction: "Inflow from West (Eastbound)",
        phaseGroup: "east_west",
        status: ewStatus,
        lanes: [
          { id: "w_t_0", name: "Lane 0 (Thru)", data: w_0 },
          { id: "w_t_1", name: "Lane 1 (Left Turn)", data: w_1 }
        ],
        totalVehicles: (w_0.vehicles || 0) + (w_1.vehicles || 0),
        maxQueue: Math.max(w_0.queue || 0, w_1.queue || 0),
        avgSpeed: ((w_0.speed || 0) + (w_1.speed || 0)) / 2 || 0
      }
    };
  }, [telemetry, nsStatus, ewStatus]);

  const nsTotalDemand = approaches.north.totalVehicles + approaches.south.totalVehicles;
  const ewTotalDemand = approaches.east.totalVehicles + approaches.west.totalVehicles;
  const totalIntersectionVehicles = nsTotalDemand + ewTotalDemand;

  const getCongestionBadge = (score) => {
    if (score > 70) return { bg: "bg-red-500/20 text-red-400 border-red-500/30", label: "High Density" };
    if (score > 40) return { bg: "bg-amber-500/20 text-amber-400 border-amber-500/30", label: "Moderate Flow" };
    return { bg: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30", label: "Optimal Flow" };
  };

  const badge = getCongestionBadge(congestion);

  return (
    <div className="min-h-screen bg-[#060813] text-slate-100 p-4 md:p-6 font-sans">
      
      {/* HEADER SECTION */}
      <header className="mb-5 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-slate-900/60 p-4 rounded-2xl border border-slate-800/90 shadow-2xl backdrop-blur-md">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-indigo-600/20 border border-indigo-500/40 rounded-xl text-indigo-400">
              <Activity className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl md:text-2xl font-black tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                  AUTONOMOUS TRAFFIC TWIN
                </h1>
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">
                  INT-001
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Real-Time Computer Vision & Exact 8-Lane 4-Way Crossroad Simulation
              </p>
            </div>
          </div>
        </div>

        {/* Live Status Indicators */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Live Camera Recording Timecounter Badge */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border font-mono text-xs shadow-lg transition-all ${
            failsafeActive 
              ? 'bg-amber-950/50 border-amber-500/50 text-amber-300'
              : 'bg-slate-950 border-slate-800 text-slate-300'
          }`}>
            <span className={`w-2 h-2 rounded-full ${failsafeActive ? 'bg-amber-400 animate-ping' : 'bg-red-500 animate-pulse'}`}></span>
            <span className="font-bold">{failsafeActive ? "⚠️ CAM-01 FAILSAFE" : "🔴 REC CAM-01"}</span>
            <span className="text-slate-500">|</span>
            <span className="text-white font-black">{videoTiming.timestamp}</span>
            <span className="text-[10px] text-slate-400">({videoTiming.frame}f)</span>
          </div>

          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-mono shadow-lg ${
            wsConnected 
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' 
              : 'bg-red-500/10 border-red-500/30 text-red-400'
          }`}>
            <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-emerald-400 animate-ping' : 'bg-red-400'}`} />
            {wsConnected ? "TELEMETRY LIVE" : "DISCONNECTED"}
          </div>
        </div>
      </header>

      {/* HIGH-TECH CCTV CAMERA FEED OFFLINE / FAILSAFE OVERLAY BANNER */}
      {failsafeActive && (
        <div className="mb-5 p-4 rounded-2xl bg-gradient-to-r from-red-950/80 via-slate-950 to-amber-950/80 border-2 border-amber-500/70 shadow-2xl shadow-amber-950/50 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 relative overflow-hidden backdrop-blur-md">
          <div className="absolute inset-0 bg-[radial-gradient(#f59e0b15_1px,transparent_1px)] [background-size:16px_16px] pointer-events-none opacity-50" />
          
          <div className="flex items-center gap-3.5 z-10">
            <div className="p-2.5 rounded-xl bg-amber-500/20 border border-amber-500/40 text-amber-400 shrink-0 animate-pulse">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-red-500/30 border border-red-500/50 text-red-300 font-mono text-[10px] font-black uppercase tracking-widest">
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
                  CCTV FEED OFFLINE
                </span>
                <strong className="text-amber-300 text-xs md:text-sm font-black uppercase tracking-wider">
                  VIDEO STREAM COMPLETED (05:00) — FAIL-SAFE SAFETY ENGAGED
                </strong>
              </div>
              <p className="text-xs text-slate-300 mt-1 font-mono leading-relaxed">
                {failsafeMsg || "Camera stream reached 5:00 min end. System autonomously engaged standard fixed-time NEMA safety cycles (30s NS / 30s EW)."}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0 z-10 font-mono">
            <div className="p-2 rounded-xl bg-slate-900/90 border border-slate-800 text-right">
              <span className="text-[10px] text-slate-400 uppercase block">Next Safe Phase</span>
              <strong className="text-amber-400 text-sm font-black">{decisionCountdown}s</strong>
            </div>
            <div className="p-2 rounded-xl bg-slate-900/90 border border-amber-500/30 text-right">
              <span className="text-[10px] text-slate-400 uppercase block">Fail-Safe Protocol</span>
              <strong className="text-emerald-400 text-xs font-bold">NEMA Fixed-Time</strong>
            </div>
          </div>
        </div>
      )}

      {/* MAIN 2D TOPOLOGY & OPTIMIZER GRID */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5 items-start">
        
        {/* LEFT: 2D DIGITAL TWIN TOPOLOGY (7 Cols) */}
        <div className="xl:col-span-7 bg-slate-900/60 border border-slate-800/90 rounded-2xl p-4 md:p-5 shadow-2xl backdrop-blur-md flex flex-col justify-between">
          <div className="flex justify-between items-center mb-2">
            <div className="flex items-center gap-2">
              <Compass className="w-5 h-5 text-indigo-400" />
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200">
                2D Physical Crossroad Digital Twin
              </h2>
            </div>
            <div className="flex items-center gap-2 font-mono text-[11px]">
              <span className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-300">
                Feed: <strong className="text-emerald-400">{videoTiming.timestamp}</strong>
              </span>
              <span className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-300">
                Standing: <strong className="text-white">{totalIntersectionVehicles}</strong>
              </span>
            </div>
          </div>

          {/* Video Playback Progress Bar */}
          <div className="w-full bg-slate-950 h-1.5 rounded-full overflow-hidden border border-slate-800/80 mb-2">
            <div 
              className="h-full bg-gradient-to-r from-indigo-500 via-cyan-400 to-emerald-400 transition-all duration-300"
              style={{ width: `${Math.min(100, Math.max(0, (videoTiming.timeSec / (videoTiming.totalSec || 1)) * 100))}%` }}
            />
          </div>

          {/* SVG/CANVAS ROAD SCHEMATIC WITH NON-OVERLAPPING 4-CORNER PLACEMENT */}
          <div className="relative w-full aspect-square max-h-[460px] mx-auto bg-[#02040b] rounded-2xl border border-slate-800 p-2 flex items-center justify-center overflow-hidden my-2 shadow-inner">
            
            {/* Asphalt Crossroad Background */}
            <div className="absolute inset-0 flex items-center justify-center">
              {/* Vertical Road (North - South) */}
              <div className="absolute h-full w-40 bg-[#0f172a] border-x-2 border-slate-700 flex justify-between px-2">
                <div className="h-full border-r border-dashed border-amber-500/40 w-1/2" />
                <div className="h-full border-l border-dashed border-slate-700 w-1/2" />
              </div>
              {/* Horizontal Road (East - West) */}
              <div className="absolute w-full h-40 bg-[#0f172a] border-y-2 border-slate-700 flex flex-col justify-between py-2">
                <div className="w-full border-b border-dashed border-amber-500/40 h-1/2" />
                <div className="w-full border-t border-dashed border-slate-700 h-1/2" />
              </div>
            </div>

            {/* 1. TOP-LEFT: NORTH INFLOW (n_t) - Left side of North Lane */}
            <div className={`absolute top-3 left-3 md:left-4 w-32 flex flex-col items-center p-2.5 rounded-xl border transition-all z-20 shadow-xl ${getPhaseContainerClass(nsStatus)}`}>
              <div className="flex items-center justify-between w-full mb-1.5">
                <span className="text-[11px] font-black font-mono text-slate-200">NORTH</span>
                <span className={`text-[9px] font-bold font-mono px-1.5 py-0.5 rounded ${getPhaseClass(nsStatus)}`}>
                  {getPhaseText(nsStatus)}
                </span>
              </div>
              <div className="w-full text-center p-1.5 rounded bg-slate-900/90 border border-slate-800">
                <strong className="text-white text-xs font-mono">{approaches.north.totalVehicles} vehicles</strong>
              </div>
            </div>

            {/* 2. TOP-RIGHT: EAST INFLOW (e_t) - Top side of East Lane */}
            <div className={`absolute top-3 right-3 md:right-4 w-32 flex flex-col items-center p-2.5 rounded-xl border transition-all z-20 shadow-xl ${getPhaseContainerClass(ewStatus)}`}>
              <div className="flex items-center justify-between w-full mb-1.5">
                <span className={`text-[9px] font-bold font-mono px-1.5 py-0.5 rounded ${getPhaseClass(ewStatus)}`}>
                  {getPhaseText(ewStatus)}
                </span>
                <span className="text-[11px] font-black font-mono text-slate-200">EAST</span>
              </div>
              <div className="w-full text-center p-1.5 rounded bg-slate-900/90 border border-slate-800">
                <strong className="text-white text-xs font-mono">{approaches.east.totalVehicles} vehicles</strong>
              </div>
            </div>

            {/* 3. BOTTOM-RIGHT: SOUTH INFLOW (s_t) - Right side of South Lane */}
            <div className={`absolute bottom-3 right-3 md:right-4 w-32 flex flex-col items-center p-2.5 rounded-xl border transition-all z-20 shadow-xl ${getPhaseContainerClass(nsStatus)}`}>
              <div className="w-full text-center p-1.5 rounded bg-slate-900/90 border border-slate-800 mb-1.5">
                <strong className="text-white text-xs font-mono">{approaches.south.totalVehicles} vehicles</strong>
              </div>
              <div className="flex items-center justify-between w-full">
                <span className={`text-[9px] font-bold font-mono px-1.5 py-0.5 rounded ${getPhaseClass(nsStatus)}`}>
                  {getPhaseText(nsStatus)}
                </span>
                <span className="text-[11px] font-black font-mono text-slate-200">SOUTH</span>
              </div>
            </div>

            {/* 4. BOTTOM-LEFT: WEST INFLOW (w_t) - Bottom side of West Lane */}
            <div className={`absolute bottom-3 left-3 md:left-4 w-32 flex flex-col items-center p-2.5 rounded-xl border transition-all z-20 shadow-xl ${getPhaseContainerClass(ewStatus)}`}>
              <div className="w-full text-center p-1.5 rounded bg-slate-900/90 border border-slate-800 mb-1.5">
                <strong className="text-white text-xs font-mono">{approaches.west.totalVehicles} vehicles</strong>
              </div>
              <div className="flex items-center justify-between w-full">
                <span className="text-[11px] font-black font-mono text-slate-200">WEST</span>
                <span className={`text-[9px] font-bold font-mono px-1.5 py-0.5 rounded ${getPhaseClass(ewStatus)}`}>
                  {getPhaseText(ewStatus)}
                </span>
              </div>
            </div>

            {/* CENTRAL JUNCTION HUB */}
            <div className="relative w-28 h-28 rounded-2xl flex flex-col items-center justify-center border-2 transition-all duration-300 z-30 shadow-2xl bg-slate-950 border-indigo-500/60 shadow-indigo-950">
              {activePhase === "north_south" ? (
                <div className={`flex flex-col items-center justify-center ${targetPhase ? 'text-yellow-400' : 'text-emerald-400'} animate-pulse`}>
                  <ArrowDown className="w-7 h-7" />
                  <span className="text-[10px] font-black font-mono tracking-wider mt-1">N-S {targetPhase ? 'YELLOW' : 'OPEN'}</span>
                  <span className="text-[8px] font-mono text-slate-400">E-W STOPPED</span>
                </div>
              ) : (
                <div className={`flex flex-col items-center justify-center ${targetPhase ? 'text-yellow-400' : 'text-emerald-400'} animate-pulse`}>
                  <ArrowRight className="w-7 h-7" />
                  <span className="text-[10px] font-black font-mono tracking-wider mt-1">E-W {targetPhase ? 'YELLOW' : 'OPEN'}</span>
                  <span className="text-[8px] font-mono text-slate-400">N-S STOPPED</span>
                </div>
              )}
            </div>

          </div>

          {/* MANUAL OVERRIDE BAR */}
          <div className="grid grid-cols-2 gap-3 mt-3">
            <button
              onClick={() => handleManualPhaseOverride("north_south")}
              className={`p-2.5 rounded-xl border text-xs font-bold font-mono transition flex items-center justify-center gap-2 cursor-pointer ${
                nsStatus === "green" 
                  ? 'bg-emerald-500 text-slate-950 border-emerald-400 shadow-lg shadow-emerald-950'
                  : nsStatus === "yellow"
                  ? 'bg-yellow-500 text-slate-950 border-yellow-400 shadow-lg shadow-yellow-950'
                  : 'bg-slate-950 hover:bg-slate-900 text-slate-300 border-slate-800'
              }`}
            >
              <span>{nsStatus === "red" ? "🟢 Switch N-S" : nsStatus === "yellow" ? "🟡 Yellow (N-S)" : "🟢 Phase: N-S Green"}</span>
            </button>
            <button
              onClick={() => handleManualPhaseOverride("east_west")}
              className={`p-2.5 rounded-xl font-mono text-xs font-bold flex items-center justify-center gap-2 transition cursor-pointer border ${
                ewStatus === "green" 
                  ? 'bg-emerald-500 text-slate-950 border-emerald-400 shadow-lg shadow-emerald-950' 
                  : ewStatus === "yellow"
                  ? 'bg-yellow-500 text-slate-950 border-yellow-400 shadow-lg shadow-yellow-950'
                  : 'bg-slate-950 hover:bg-slate-900 text-slate-300 border-slate-800'
              }`}
            >
              <span>{ewStatus === "red" ? "🟢 Switch E-W" : ewStatus === "yellow" ? "🟡 Yellow (E-W)" : "🟢 Phase: E-W Green"}</span>
            </button>
          </div>
        </div>

        {/* RIGHT: AI DECISION ENGINE + FLOW COMPARISON (5 Cols) */}
        <div className="xl:col-span-5 flex flex-col gap-5">
          
          {/* AI Decision Card */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900/90 to-indigo-950/40 border border-indigo-500/30 shadow-xl">
            <div className="flex justify-between items-center mb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-indigo-400" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-indigo-200">
                  Autonomous AI Decision Engine
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-[10px] px-2.5 py-0.5 rounded font-mono font-bold flex items-center gap-1 border ${
                  autoOptimize 
                    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40' 
                    : 'bg-amber-500/20 text-amber-400 border-amber-500/40'
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${autoOptimize ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`}></span>
                  {autoOptimize ? "AUTONOMOUS MODE" : "MANUAL CONTROL"}
                </span>
              </div>
            </div>

            {/* Countdown & Phase Elapsed Ticker */}
            <div className="grid grid-cols-2 gap-2 my-3 p-2.5 rounded-xl bg-slate-950/80 border border-slate-800 text-center font-mono">
              <div>
                <span className="text-[10px] text-slate-500 block uppercase font-bold">Next AI Decision</span>
                <span className="text-sm font-black text-indigo-300">
                  {autoOptimize ? `${decisionCountdown}s` : "Paused"}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-slate-500 block uppercase font-bold">Active Green Time</span>
                <span className="text-sm font-black text-emerald-400">{phaseElapsed}s</span>
              </div>
            </div>

            {/* Algorithm Selector */}
            <div className="mb-3">
              <label className="text-[10px] text-slate-400 uppercase font-bold block mb-1">Signal Optimization Model:</label>
              <select 
                value={selectedAlgorithm} 
                onChange={(e) => setSelectedAlgorithm(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 text-slate-200 text-xs font-mono rounded-lg px-2.5 py-1.5 focus:border-indigo-500 outline-none"
              >
                <option value="rl">DQN Deep Reinforcement Learning (Trained Policy)</option>
                <option value="queue_based">Dynamic Queue Pressure Allocation</option>
                <option value="webster">Webster Delay Minimization Formulation</option>
              </select>
            </div>

            {/* Demand Bar Comparison */}
            <div className="mt-3 space-y-2">
              <div>
                <div className="flex justify-between text-xs font-mono mb-1">
                  <span className="text-slate-400">North-South Demand ({nsTotalDemand} veh)</span>
                  <span className="text-emerald-400 font-bold">{Math.round((nsTotalDemand / (totalIntersectionVehicles || 1)) * 100)}%</span>
                </div>
                <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden border border-slate-800">
                  <div 
                    className="h-full bg-emerald-500 transition-all duration-500" 
                    style={{ width: `${(nsTotalDemand / (totalIntersectionVehicles || 1)) * 100}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-mono mb-1">
                  <span className="text-slate-400">East-West Demand ({ewTotalDemand} veh)</span>
                  <span className="text-cyan-400 font-bold">{Math.round((ewTotalDemand / (totalIntersectionVehicles || 1)) * 100)}%</span>
                </div>
                <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden border border-slate-800">
                  <div 
                    className="h-full bg-cyan-500 transition-all duration-500" 
                    style={{ width: `${(ewTotalDemand / (totalIntersectionVehicles || 1)) * 100}%` }}
                  />
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between">
              <button
                onClick={() => setAutoOptimize(prev => !prev)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold font-mono transition cursor-pointer border ${
                  autoOptimize 
                    ? 'bg-amber-500/10 text-amber-400 border-amber-500/30 hover:bg-amber-500/20' 
                    : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20'
                }`}
              >
                {autoOptimize ? "⏸️ Pause Auto" : "▶️ Resume Auto"}
              </button>
              <button
                onClick={handleOptimize}
                disabled={optimizing}
                className="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/30 flex items-center gap-1.5 transition cursor-pointer"
              >
                <RefreshCw className={`w-3 h-3 ${optimizing ? 'animate-spin' : ''}`} />
                {optimizing ? "Optimizing..." : "Trigger Now"}
              </button>
            </div>
          </div>

          {/* Congestion Gauge & Controller Settings */}
          <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/90 shadow-xl flex-1 flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-center mb-3">
                <div className="flex items-center gap-2">
                  <Gauge className="w-4 h-4 text-amber-400" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                    Junction Saturation & Safety Limits
                  </h3>
                </div>
                <span className={`text-xs px-2.5 py-0.5 rounded-full border ${badge.bg}`}>
                  {badge.label}
                </span>
              </div>

              <div className="mt-2">
                <div className="flex justify-between text-xs font-mono mb-1.5">
                  <span className="text-slate-400">Congestion Severity Score</span>
                  <strong className="text-white">{congestion}%</strong>
                </div>
                <div className="w-full bg-slate-950 h-3 rounded-full overflow-hidden border border-slate-800">
                  <div 
                    className={`h-full transition-all duration-500 ${
                      congestion > 65 ? 'bg-red-500' : congestion > 35 ? 'bg-amber-500' : 'bg-emerald-500'
                    }`}
                    style={{ width: `${Math.min(100, Math.max(0, congestion))}%` }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 mt-4 text-[11px] font-mono text-slate-400">
                <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800">
                  <span className="text-slate-500 block text-[10px]">Min Green Time</span>
                  <strong className="text-slate-200">10 Seconds</strong>
                </div>
                <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800">
                  <span className="text-slate-500 block text-[10px]">Max Green Time</span>
                  <strong className="text-slate-200">60 Seconds</strong>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800/80">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1.5">
                Controller Action Log:
              </span>
              <div className="space-y-1">
                {phaseHistory.length > 0 ? (
                  phaseHistory.map((h, i) => (
                    <div key={i} className="text-[11px] font-mono text-slate-400 flex items-center gap-1.5">
                      <ChevronRight className="w-3 h-3 text-indigo-400 shrink-0" />
                      <span>{h}</span>
                    </div>
                  ))
                ) : (
                  <div className="text-[11px] font-mono text-slate-500 italic">
                    Controller running in automated steady-state.
                  </div>
                )}
              </div>
            </div>
          </div>

        </div>
      </div>

      {/* 3. RAW TELEMETRY DATA TABLE */}
      <div className="mt-5 p-5 rounded-2xl bg-slate-900/60 border border-slate-800/90 shadow-xl overflow-hidden">
        <div className="flex items-center gap-2 mb-4">
          <Layers className="w-4 h-4 text-slate-400" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">Live 8-Lane Telemetry Feed</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono text-slate-300">
            <thead className="bg-slate-950/80 text-slate-500 uppercase">
              <tr>
                <th className="px-4 py-2 border-b border-slate-800">Lane ID</th>
                <th className="px-4 py-2 border-b border-slate-800">Approach</th>
                <th className="px-4 py-2 border-b border-slate-800">Vehicle Count</th>
                <th className="px-4 py-2 border-b border-slate-800">Queue Length (m)</th>
                <th className="px-4 py-2 border-b border-slate-800">Avg Speed (km/h)</th>
                <th className="px-4 py-2 border-b border-slate-800">Occupancy</th>
              </tr>
            </thead>
            <tbody>
              {Object.values(approaches).flatMap(app => 
                app.lanes.map(lane => {
                  const vehCount = lane.data.vehicles ?? lane.data.vehicle_count ?? 0;
                  const queueM = lane.data.queue ?? lane.data.queue_length ?? 0;
                  const speedKmh = lane.data.speed ?? lane.data.average_speed ?? 0;
                  const occ = lane.data.occupancy ?? 0;

                  return (
                    <tr key={lane.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                      <td className="px-4 py-2 font-bold text-slate-200">{lane.id}</td>
                      <td className="px-4 py-2 text-slate-400">{app.name.split(' ')[0]}</td>
                      <td className="px-4 py-2 text-indigo-300 font-bold">{vehCount}</td>
                      <td className="px-4 py-2 text-amber-300">{Number(queueM).toFixed(1)}m</td>
                      <td className="px-4 py-2 text-emerald-300">{Number(speedKmh).toFixed(1)}</td>
                      <td className="px-4 py-2 text-cyan-300">{(Number(occ) * 100).toFixed(1)}%</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}