import { useEffect, useMemo, useRef, useState } from 'react'
import { MapContainer, TileLayer, Marker, Popup, useMap, Pane, CircleMarker } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const GINGIN_CENTER: L.LatLngExpression = [-31.35, 115.90]
const GINGIN_ZOOM = 13

const STATIONS = [
  { id: 'WAR1', latlng: L.latLng(-31.345, 115.905) },
  { id: 'WAR2', latlng: L.latLng(-31.355, 115.895) },
]

const rndVal = () => +(Math.random() * 6 - 3).toFixed(2)
const lerp = (a: number, b: number, t: number) => a + (b - a) * t
const clamp01 = (x: number) => Math.max(0, Math.min(1, x))

function SetView({ coords, zoom }: { coords: L.LatLngExpression; zoom: number }) {
  const map = useMap()
  useEffect(() => { map.setView(coords, zoom) }, [map, coords, zoom])
  return null
}

/* ---------- GREEN HEAT OVERLAY ---------- */
function GreenHeatOverlay({
  stationValsRef, stationPts, visible,
}: { stationValsRef: React.MutableRefObject<number[]>, stationPts: L.LatLng[], visible: boolean }) {
  const map = useMap()
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  // attach canvas to overlayPane
  useEffect(() => {
    if (!visible) return
    const pane = map.getPanes().overlayPane
    const canvas = document.createElement('canvas')
    canvas.style.position = 'absolute'
    canvas.style.top = '0'
    canvas.style.left = '0'
    canvas.style.pointerEvents = 'none'
    pane.appendChild(canvas)
    canvasRef.current = canvas

    const cleanup = () => {
      if (canvas.parentElement) canvas.parentElement.removeChild(canvas)
      canvasRef.current = null
    }
    return cleanup
  }, [visible, map])

  // color ramp: -3 (red) → 0 (yellow) → +3 (green)
  const valToRGB = (v: number) => {
    const x = Math.max(-3, Math.min(3, v))
    if (x < 0) {
      const t = (x + 3) / 3
      return [255, Math.round(255 * t), 0]        // red→yellow
    } else {
      const t = x / 3
      return [Math.round(255 * (1 - t)), 255, 0]  // yellow→green
    }
  }

  // draw
  useEffect(() => {
    if (!visible) return
    let raf = 0

    const resize = () => {
      const c = canvasRef.current; if (!c) return
      const { x: w, y: h } = map.getSize()
      c.width = w
      c.height = h
      c.style.width = `${w}px`
      c.style.height = `${h}px`
    }

    const draw = () => {
      const c = canvasRef.current; if (!c) return
      const ctx = c.getContext('2d'); if (!ctx) return
      const { x: w, y: h } = map.getSize()
      const cell = 8 // smaller cell = sharper
      ctx.clearRect(0, 0, w, h)

      const sPx = stationPts.map(p => map.latLngToContainerPoint(p))
      const sVals = stationValsRef.current
      const power = 2
      const eps = 1e-4
      const alpha = 0.55 // fixed opacity so it’s visible

      for (let y = 0; y < h; y += cell) {
        for (let x = 0; x < w; x += cell) {
          let num = 0, den = 0
          for (let i = 0; i < sPx.length; i++) {
            const dx = x - sPx[i].x, dy = y - sPx[i].y
            const d = Math.sqrt(dx*dx + dy*dy) + eps
            const wgt = 1 / Math.pow(d, power)
            num += (sVals[i] ?? 0) * wgt
            den += wgt
          }
          const val = den ? num / den : 0
          const [r,g,b] = valToRGB(val)
          ctx.fillStyle = `rgba(${r},${g},${b},${alpha})`
          ctx.fillRect(x, y, cell, cell)
        }
      }
    }

    const tick = () => { resize(); draw(); raf = requestAnimationFrame(tick) }
    raf = requestAnimationFrame(tick)

    const sync = () => { resize(); draw() }
    map.on('move', sync)
    map.on('zoom', sync)
    window.addEventListener('resize', sync)

    return () => {
      cancelAnimationFrame(raf)
      map.off('move', sync)
      map.off('zoom', sync)
      window.removeEventListener('resize', sync)
    }
  }, [visible, map, stationPts, stationValsRef])

  return null
}


/* ---------- PINS ---------- */
function StationPins({
  stationValsRef, visible,
}: { stationValsRef: React.MutableRefObject<number[]>, visible: boolean }) {
  const [, force] = useState(0)
  useEffect(() => {
    if (!visible) return
    const id = setInterval(() => force(v => (v + 1) % 1_000_000), 200)
    return () => clearInterval(id)
  }, [visible])

  if (!visible) return null
  const [v1, v2] = stationValsRef.current
  return (
    <>
      <Marker position={STATIONS[0].latlng}>
        <Popup><b>{STATIONS[0].id}</b><br />{v1.toFixed(2)}</Popup>
      </Marker>
      <Marker position={STATIONS[1].latlng}>
        <Popup><b>{STATIONS[1].id}</b><br />{v2.toFixed(2)}</Popup>
      </Marker>
    </>
  )
}

/* --- value [-3..3] → colour --- */
function valueToColor(v: number): string {
  const val = Math.max(-3, Math.min(3, v))
  if (val < 0) {
    const t = (val + 3) / 3
    return `rgb(255,${Math.round(255 * t)},0)`   // red→yellow
  } else {
    const t = val / 3
    return `rgb(${Math.round(255 * (1 - t))},255,0)` // yellow→green
  }
}

/* ---------- COLOURED CIRCLES ---------- */
function StationPulse({
  stationValsRef, visible,
}: { stationValsRef: React.MutableRefObject<number[]>, visible: boolean }) {
  const circleRefs = useRef<(L.CircleMarker | null)[]>([])
  useEffect(() => {
    if (!visible) return
    let raf = 0
    const animate = () => {
      const vals = stationValsRef.current
      for (let i = 0; i < circleRefs.current.length; i++) {
        const c = circleRefs.current[i]; if (!c) continue
        const col = valueToColor(vals[i] ?? 0)
        c.setStyle({ fillColor: col, color: col })
      }
      raf = requestAnimationFrame(animate)
    }
    raf = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(raf)
  }, [visible, stationValsRef])

  if (!visible) return null
  return (
    <>
      {STATIONS.map((s, i) => (
        <CircleMarker
          key={s.id}
          center={s.latlng}
          radius={30}
          pathOptions={{ color: '#000', weight: 2, fillColor: '#ff0', fillOpacity: 0.6 }}
          ref={(inst) => (circleRefs.current[i] = inst as unknown as L.CircleMarker)}
        />
      ))}
    </>
  )
}

/* ---------- Settings panel ---------- */
type TabKeyUI = 'Live View' | 'Station View' | 'Playback'
function SettingsPanel() {
  const [tab, setTab] = useState<TabKeyUI>('Live View')
  const stations = useMemo(() => Array.from({ length: 28 }, (_, i) => `WAR${i + 1}`), [])

  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [waveform,git rm app/src/renderer/src/App.tsx
 setWaveform] = useState<number[]>([]);
  const [duration, setDuration] = useState<number>(0);
  const [playbackTime, setPlaybackTime] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // File upload: send to Python backend for parsing
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      setUploadedFile(file);
      // Send file to backend
      try {
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch('http://localhost:8000/parse-miniseed', {
          method: 'POST',
          body: formData
        });
        if (!res.ok) throw new Error('Backend error');
        const data = await res.json();
        setWaveform(data.samples || []);
        setDuration(data.duration || 0);
      } catch (err) {
        console.error('Backend parse error:', err);
        setWaveform([]);
        setDuration(0);
      }
    }
  };

  // Playback logic (simulate audio)
  useEffect(() => {
    let raf: number;
    if (isPlaying && waveform.length > 0) {
      const start = performance.now() - playbackTime * 1000;
      const tick = () => {
        const elapsed = (performance.now() - start) / 1000;
        if (elapsed < duration) {
          setPlaybackTime(elapsed);
          raf = requestAnimationFrame(tick);
        } else {
          setPlaybackTime(duration);
          setIsPlaying(false);
        }
      };
      raf = requestAnimationFrame(tick);
      return () => cancelAnimationFrame(raf);
    }
  }, [isPlaying, waveform, duration]);

  const handlePlay = () => {
    setIsPlaying(true);
  };
  const handlePause = () => {
    setIsPlaying(false);
  };
  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPlaybackTime(Number(e.target.value));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: 12, gap: 12 }}>
      <div style={{ display: 'flex', gap: 8 }}>
        {(['Live View', 'Station View', 'Playback'] as TabKeyUI[]).map(k => (
          <button
            key={k}
            onClick={() => setTab(k)}
            style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid #e5e7eb',
                     background: tab === k ? '#111' : '#fff', color: tab === k ? '#fff' : '#111', cursor: 'pointer' }}
          >{k}</button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: 'auto', paddingRight: 4 }}>
        {tab === 'Live View' && (
          <div style={{ display: 'grid', gap: 12 }}>
            <label style={{ display: 'grid', gap: 6 }}>
              <span>Network</span>
              <input value="GG" readOnly style={{ padding: 8, borderRadius: 8, border: '1px solid #d1d5db', background: '#f5f5f5' }} />
            </label>
            <label style={{ display: 'grid', gap: 6 }}>
              <span>Sample Rate (Hz)</span>
              <input value="250" readOnly style={{ padding: 8, borderRadius: 8, border: '1px solid #d1d5db', background: '#f5f5f5' }} />
            </label>
            <div style={{ display: 'grid', gap: 6 }}>
              <span>Stations</span>
              <div style={{ border: '1px solid #d1d5db', borderRadius: 8, height: 260, overflow: 'auto', padding: 8, background: '#fff' }}>
                <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 6 }}>
                  {stations.map(s => (
                    <li key={s} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <input type="checkbox" /><span>{s}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <small style={{ color: '#6b7280' }}>
                Replace with backend data via IPC (e.g. <code>window.api.getStations()</code>).
              </small>
            </div>
          </div>
        )}
        {tab === 'Station View' && <div style={{ color: '#6b7280' }}>Station View settings placeholder.</div>}
        {tab === 'Playback' && (
          <div style={{ color: '#6b7280', display: 'flex', flexDirection: 'column', gap: 12 }}>
            <label style={{ display: 'grid', gap: 6 }}>
              <span>Upload MiniSEED file</span>
              <input type="file" accept=".mseed,.miniseed" onChange={handleFileChange} />
            </label>
            {uploadedFile && (
              <div style={{ color: '#333', fontSize: 14 }}>
                Selected file: {uploadedFile.name}
              </div>
            )}
            {waveform.length > 0 && (
              <>
                <div style={{ width: '100%', height: 120, background: '#fff', border: '1px solid #d1d5db', borderRadius: 8, overflow: 'hidden', position: 'relative' }}>
                  <canvas
                    width={400}
                    height={100}
                    style={{ width: '100%', height: '100%' }}
                    ref={el => {
                      if (!el) return;
                      const ctx = el.getContext('2d');
                      if (!ctx) return;
                      ctx.clearRect(0, 0, el.width, el.height);
                      ctx.strokeStyle = '#007bff';
                      ctx.beginPath();
                      const len = waveform.length;
                      for (let i = 0; i < el.width; i++) {
                        const idx = Math.floor(i / el.width * len);
                        const y = (waveform[idx] ?? 0);
                        const normY = 50 - y / 100; // scale for demo
                        if (i === 0) ctx.moveTo(i, normY);
                        else ctx.lineTo(i, normY);
                      }
                      ctx.stroke();
                      // Playback position
                      ctx.strokeStyle = '#ff0000';
                      ctx.beginPath();
                      const px = Math.floor(playbackTime / duration * el.width);
                      ctx.moveTo(px, 0);
                      ctx.lineTo(px, el.height);
                      ctx.stroke();
                    }}
                  />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <button onClick={handlePlay} disabled={isPlaying} style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid #d1d5db' }}>Play</button>
                  <button onClick={handlePause} disabled={!isPlaying} style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid #d1d5db' }}>Pause</button>
                  <input type="range" min={0} max={duration} step={0.01} value={playbackTime} onChange={handleSeek} style={{ flex: 1 }} />
                  <span>{playbackTime.toFixed(2)} / {duration.toFixed(2)} s</span>
                </div>
              </>
            )}
            {waveform.length === 0 && <div>Playback and visualization coming soon.</div>}
          </div>
        )}
      </div>
    </div>
  )
}

/* ---------- Main App (now calls Python once) ---------- */
export default function App() {
  const [mode, setMode] = useState<'pin' | 'overlay'>('pin')
  const [pyStatus, setPyStatus] = useState<string>('idle')
  const stationValsRef = useRef<number[]>([0, 0])

  // 250 Hz local stream
  useEffect(() => {
    const id = setInterval(() => { stationValsRef.current = [rndVal(), rndVal()] }, 1000)
    return () => clearInterval(id)
  }, [])

  // Call Python once on mount; seed the stream if JSON.value present
  useEffect(() => {
    (async () => {
      try {
        const s = await window.api.getData()
        console.log('PY OUT:', s)
        setPyStatus(s)
        try {
          const j = JSON.parse(s)
          if (typeof j.value === 'number') {
            stationValsRef.current = [j.value, -j.value]
          }
        } catch { /* ignore non-JSON */ }
      } catch (e: any) {
        console.error('PY ERR:', e)
        setPyStatus('ERR: ' + (e?.message || e))
      }
    })()
  }, [])

  return (
    <div style={{ height: '100vh', display: 'flex' }}>
      <div style={{ width: '30%', minWidth: 280, borderRight: '1px solid #e5e7eb', background: '#fafafa' }}>
        <SettingsPanel />
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 12, gap: 12, minWidth: 0 }}>
        {/* tiny status line */}
        <div style={{ fontSize: 12, color: '#6b7280' }}>Python: {pyStatus.slice(0, 120)}</div>

        <div style={{ position: 'relative', width: '100%', flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 0 }}>
          <div style={{ width: '100%', height: '100%', maxHeight: '100%', aspectRatio: '1 / 1' }}>
            <MapContainer style={{ width: '100%', height: '100%' }}>
              <SetView coords={GINGIN_CENTER} zoom={GINGIN_ZOOM} />
              <TileLayer {...{ url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', attribution: '&copy; OpenStreetMap contributors' }} />
              {/* Pin mode */}
              <StationPins stationValsRef={stationValsRef} visible={mode === 'pin'} />
              <StationPulse stationValsRef={stationValsRef} visible={mode === 'pin'} />
              {/* Overlay mode */}
              <GreenHeatOverlay stationValsRef={stationValsRef} stationPts={STATIONS.map(s => s.latlng)} visible={mode === 'overlay'} />
            </MapContainer>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button
            style={{ flex: 1, padding: '12px 0', borderRadius: 10, border: '1px solid #d1d5db' }}
            onClick={() => setMode(m => (m === 'pin' ? 'overlay' : 'pin'))}
          >
            {mode === 'pin' ? 'Toggle Overlay View' : 'Toggle Pin View'}
          </button>
          <button
            style={{ flex: 1, padding: '12px 0', borderRadius: 10, border: '1px solid #d1d5db' }}
            onClick={async () => {
              // quick manual fetch button if you want it
              try {
                const s = await window.api.getData()
                console.log('PY OUT (manual):', s)
                setPyStatus(s)
              } catch (e: any) {
                setPyStatus('ERR: ' + (e?.message || e))
              }
            }}
          >
            Fetch Python (For testing)
          </button>
          <button style={{ flex: 1, padding: '12px 0', borderRadius: 10, border: '1px solid #d1d5db' }}>Playback</button>
        </div>
      </div>
    </div>
  )
}
