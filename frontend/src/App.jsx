import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend);

const formatTime = (seconds) => {
  if (seconds === 0) return '0s';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
};

const capitalize = (value) => (value ? value.charAt(0).toUpperCase() + value.slice(1) : '-');

function App() {
  const [frame, setFrame] = useState(null);
  const [emotion, setEmotion] = useState('neutral');
  const [activity, setActivity] = useState('idle');
  const [stress, setStress] = useState(0);
  const [patientMode, setPatientMode] = useState(false);
  const [patientMoving, setPatientMoving] = useState(false);
  const [activityDurations, setActivityDurations] = useState({});
  const [stressHistory, setStressHistory] = useState([]);
  const [rgb, setRgb] = useState('#00ff00');

  const chartData = useMemo(() => ({
    labels: stressHistory.map((item) => item.time),
    datasets: [
      {
        label: 'Stress Score',
        data: stressHistory.map((item) => item.stress),
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.2)',
        fill: true,
        tension: 0.4,
      },
    ],
  }), [stressHistory]);

  const chartOptions = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
    },
    scales: {
      y: {
        beginAtZero: true,
        max: 100,
        grid: { color: 'rgba(255, 255, 255, 0.1)' },
        ticks: { color: '#94a3b8' },
      },
      x: {
        grid: { display: false },
        ticks: { color: '#94a3b8', maxTicksLimit: 6 },
      },
    },
  }), []);

  const fetchFrame = useCallback(async () => {
    try {
      const res = await fetch('/api/frame');
      const data = await res.json();
      if (data.frame) {
        setFrame(`data:image/jpeg;base64,${data.frame}`);
      }
    } catch (err) {
      console.warn('Backend unavailable for frame');
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch('/api/stats');
      const data = await res.json();
      setEmotion(capitalize(data.emotion));
      setActivity(capitalize(data.activity));
      setStress(data.stress ?? 0);
      setPatientMode(!!data.patient_mode);
      setPatientMoving(!!data.patient_moving);
      setActivityDurations(data.activity_durations ?? {});
      setStressHistory(data.stress_history ?? []);
    } catch (err) {
      console.error('Error fetching stats', err);
    }
  }, []);

  useEffect(() => {
    const frameInterval = setInterval(fetchFrame, 150);
    const statsInterval = setInterval(fetchStats, 1000);
    fetchFrame();
    fetchStats();

    return () => {
      clearInterval(frameInterval);
      clearInterval(statsInterval);
    };
  }, [fetchFrame, fetchStats]);

  const toggleMode = async () => {
    const newMode = !patientMode;
    setPatientMode(newMode);
    try {
      await fetch('/api/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient_mode: newMode }),
      });
    } catch (err) {
      console.error('Failed to toggle mode', err);
    }
  };

  const sendColor = async () => {
    const r = parseInt(rgb.substring(1, 3), 16);
    const g = parseInt(rgb.substring(3, 5), 16);
    const b = parseInt(rgb.substring(5, 7), 16);
    try {
      await fetch('/api/rgb', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ r, g, b }),
      });
      alert(`Sent Custom Color: R:${r} G:${g} B:${b}`);
    } catch (err) {
      console.error('Failed to send RGB', err);
    }
  };

  const autoColor = async () => {
    try {
      await fetch('/api/rgb', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto: true }),
      });
      alert('Restored Auto AI LED Colors!');
    } catch (err) {
      console.error('Failed to set auto color', err);
    }
  };

  return (
    <div className="min-h-screen px-4 py-6 bg-bg text-slate-100">
      <header className="mx-auto mb-6 max-w-6xl rounded-2xl border border-white/10 bg-glass px-6 py-5 backdrop-blur-xl shadow-lg">
        <h1 className="text-center text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-sky-400 to-emerald-300">
          AI Emotion & Activity Monitor
        </h1>
        <p className="text-center text-sm text-slate-400">Real-time mental wellness tracking interface</p>
      </header>

      <div className="mx-auto grid max-w-6xl gap-5 lg:grid-cols-[1fr_360px]">
        <main className="rounded-2xl border border-white/10 bg-glass p-4 shadow-glass">
          <div className={`${patientMode && patientMoving ? 'block' : 'hidden'} mb-4 rounded-xl border border-rose-400/20 bg-rose-500/20 p-4 text-center text-rose-100`}>⚠️ PATIENT MOVING - ATTENTION REQUIRED ⚠️</div>
          <div className="space-y-4">
            <img className="h-[420px] w-full rounded-xl border-2 border-white/10 object-cover bg-black" src={frame ?? ''} alt="AI camera feed" />
            <button
              onClick={toggleMode}
              className={`w-full rounded-lg px-4 py-2 font-bold transition ${patientMode ? 'bg-rose-500 hover:bg-rose-400' : 'bg-sky-500 hover:bg-sky-400'}`}>
              {patientMode ? 'Switch to Normal Mode' : 'Switch to Patient Mode'}
            </button>
          </div>
        </main>

        <aside className="rounded-2xl border border-white/10 bg-glass p-4 shadow-glass">
          <div className="grid grid-cols-2 gap-3 mb-5">
            <div className="rounded-xl border border-white/10 p-3">
              <div className="text-xs uppercase tracking-wide text-slate-400">Current Emotion</div>
              <div className="text-2xl font-bold text-sky-400">{emotion}</div>
            </div>
            <div className="rounded-xl border border-white/10 p-3">
              <div className="text-xs uppercase tracking-wide text-slate-400">Current Activity</div>
              <div className="text-2xl font-bold text-emerald-300">{activity}</div>
            </div>
          </div>

          <div className="rounded-xl border border-white/10 p-3 mb-5">
            <div className="flex items-center justify-between text-sm text-slate-400">Stress Level <span className="font-bold">{stress}%</span></div>
            <div className="mt-2 h-3 overflow-hidden rounded-full bg-white/10">
              <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 via-amber-400 to-rose-500 transition-all" style={{ width: `${stress}%` }} />
            </div>
          </div>

          <div className="mb-4 text-lg font-semibold border-b border-white/10 pb-2">Stress History (60s)</div>
          <div className="mb-5 h-40">
            <Line data={chartData} options={chartOptions} />
          </div>

          <div className="mb-4 text-lg font-semibold border-b border-white/10 pb-2">Activity Durations</div>
          <div className="mb-5 max-h-40 overflow-auto text-sm">
            <table className="w-full text-left">
              <thead>
                <tr className="text-slate-400">
                  <th className="pb-2">Activity</th>
                  <th className="pb-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(activityDurations)
                  .sort((a, b) => b[1] - a[1])
                  .filter(([, value]) => value > 0)
                  .map(([key, value]) => (
                    <tr key={key} className="border-t border-white/10">
                      <td className="py-1 capitalize">{key}</td>
                      <td className="py-1">{formatTime(value)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>

          <div className="mb-4 text-lg font-semibold border-b border-white/10 pb-2">Arduino Override</div>
          <div className="flex items-center gap-2">
            <input type="color" className="h-10 w-10 rounded-full border-2 border-white/20 bg-transparent" value={rgb} onChange={(e) => setRgb(e.target.value)} />
            <button onClick={sendColor} className="rounded-lg bg-sky-500 px-3 py-2 text-sm font-bold text-white hover:bg-sky-400">Set Custom RGB Color</button>
            <button onClick={autoColor} className="rounded-lg bg-emerald-500 px-3 py-2 text-sm font-bold text-white hover:bg-emerald-400">Auto AI Color</button>
          </div>
        </aside>
      </div>
    </div>
  );
}

export default App;
