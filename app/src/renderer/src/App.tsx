// Currently this is the main renderer file for the Seismographer app.
// Built with react-leaflet for mapping and IPC for communication with the main process.

import { useEffect, useMemo, useRef, useState } from 'react'
import { MapContainer, TileLayer, Marker, Popup, useMap, CircleMarker } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

/* ---------- IPC types (match your preload) ---------- */
declare global {
  interface Window {
    api: {
      on: (ch: string, cb: (...args: any[]) => void) => void
      off?: (ch: string, cb: (...args: any[]) => void) => void
      invoke: (ch: string, ...args: any[]) => Promise<any>
      getData: () => Promise<string>
    }
  }
}

/* ---------- Types matching /live and /wave ---------- */
type LiveStation = { id: string; lat: number; lon: number; rms: number; last: string | null }
type LivePayload = { updated: string; interval_ms: number; stations: LiveStation[] }
type WavePayload = { id: string; t0_iso: string; fs: number; values: number[]; sec_key: number }

/* ---------- Map setup ---------- */
const CENTER: L.LatLngExpression = [-31.35, 115.90]
const ZOOM = 12

function SetView({ coords, zoom }: { coords: L.LatLngExpression; zoom: number }) {
  const map = useMap()
  useEffect(() => { map.setView(coords, zoom) }, [map, coords, zoom])
  return null
}

/* --- value [-3..3] → colour (still works fine for wider ranges by clamping) --- */
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

/* ---------- GREEN HEAT OVERLAY (IDW on a canvas) ---------- */
function GreenHeatOverlay({
  pts, vals, visible,
}: { pts: L.LatLng[]; vals: number[]; visible: boolean }) {
  const map = useMap()
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

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
    return () => { canvas.remove(); canvasRef.current = null }
  }, [visible, map])

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

  useEffect(() => {
    if (!visible) return
    let raf = 0
    const resize = () => {
      const c = canvasRef.current; if (!c) return
      const { x: w, y: h } = map.getSize()
      c.width = w; c.height = h
      c.style.width = `${w}px`; c.style.height = `${h}px`
    }
    const draw = () => {
      const c = canvasRef.current; if (!c) return
      const ctx = c.getContext('2d'); if (!ctx) return
      const { x: w, y: h } = map.getSize()
      const cell = 8
      ctx.clearRect(0, 0, w, h)
      const sPx = pts.map(p => map.latLngToContainerPoint(p))
      const power = 2
      const eps = 1e-4
      const alpha = 0.55
      for (let y = 0; y < h; y += cell) {
        for (let x = 0; x < w; x += cell) {
          let num = 0, den = 0
          for (let i = 0; i < sPx.length; i++) {
            const dx = x - sPx[i].x, dy = y - sPx[i].y
            const d = Math.sqrt(dx*dx + dy*dy) + eps
            const wgt = 1 / Math.pow(d, power)
            num += (vals[i] ?? 0) * wgt
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
    map.on('move zoom', sync)
    window.addEventListener('resize', sync)
    return () => {
      cancelAnimationFrame(raf)
      map.off('move zoom', sync)
      window.removeEventListener('resize', sync)
    }
  }, [visible, map, pts, vals])

  return null
}

/* ---------- Pins + Pulses driven by live RMS ---------- */
function StationPins({
  stations, values, onWave,
}: {
  stations: { id: string; latlng: L.LatLng }[]
  values: Record<string, number>
  onWave: (id: string) => void
}) {
  return (
    <>
      {stations.map((s) => {
        const v = values[s.id] ?? 0
        return (
          <Marker key={s.id} position={s.latlng}>
            <Popup>
              <b>{s.id}</b><br />
              RMS: {v.toFixed(2)}<br />
              <button onClick={() => onWave(s.id)} style={{ marginTop: 6 }}>Fetch 1s waveform</button>
            </Popup>
          </Marker>
        )
      })}
    </>
  )
}

function StationPulse({
  stations, values, visible,
}: {
  stations: { id: string; latlng: L.LatLng }[]
  values: Record<string, number>
  visible: boolean
}) {
  const circleRefs = useRef<(L.CircleMarker | null)[]>([])
  useEffect(() => {
    if (!visible) return
    let raf = 0
    const animate = () => {
      stations.forEach((s, i) => {
        const c = circleRefs.current[i]; if (!c) return
        const col = valueToColor(values[s.id] ?? 0)
        c.setStyle({ fillColor: col, color: col })
      })
      raf = requestAnimationFrame(animate)
    }
    raf = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(raf)
  }, [visible, stations, values])

  if (!visible) return null
  return (
    <>
      {stations.map((s, i) => (
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

/* ---------- Settings panel (reads from live) ---------- */
function SettingsPanel({ stationIds }: { stationIds: string[] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: 12, gap: 12 }}>
      <div style={{ display: 'flex', gap: 8 }}>
        {['Live View'].map(k => (
          <button key={k}
                  style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid #e5e7eb', background: '#111', color: '#fff' }}>
            {k}
          </button>
        ))}
      </div>
      <div style={{ flex: 1, overflow: 'auto', paddingRight: 4 }}>
        <div style={{ display: 'grid', gap: 12 }}>
          <label style={{ display: 'grid', gap: 6 }}>
            <span>Network</span>
            <input value="XX" readOnly style={{ padding: 8, borderRadius: 8, border: '1px solid #d1d5db', background: '#f5f5f5' }} />
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span>Sample Rate (Hz)</span>
            <input value="250" readOnly style={{ padding: 8, borderRadius: 8, border: '1px solid #d1d5db', background: '#f5f5f5' }} />
          </label>
          <div style={{ display: 'grid', gap: 6 }}>
            <span>Stations</span>
            <div style={{ border: '1px solid #d1d5db', borderRadius: 8, height: 260, overflow: 'auto', padding: 8, background: '#fff' }}>
              <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 6 }}>
                {stationIds.map(s => (
                  <li key={s} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <input type="checkbox" defaultChecked readOnly /><span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
            <small style={{ color: '#6b7280' }}>
              Live list comes from Python receiver via IPC.
            </small>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ---------- Main App (wired to IPC bridge) ---------- */
export default function App() {
  const [mode, setMode] = useState<'pin' | 'overlay'>('pin')
  const [updatedIso, setUpdatedIso] = useState<string>('—')
  const [stations, setStations] = useState<{ id: string; latlng: L.LatLng }[]>([])
  const valuesRef = useRef<Record<string, number>>({})
  const [, force] = useState(0) // cheap re-render ticker for pulses

  // subscribe to 'receiver:live' push
  const handler = (payload: LivePayload) => {
    setUpdatedIso(payload.updated)
    const nextStations = payload.stations.map(s => ({ id: s.id, latlng: L.latLng(s.lat, s.lon) }))
    setStations(nextStations)

    const nextVals: Record<string, number> = {}
    for (const s of payload.stations) nextVals[s.id] = s.rms ?? 0
    valuesRef.current = nextVals
    force(v => (v + 1) % 1_000_000)
  }

  useEffect(() => {
    const off = window.api.on('receiver:live', handler)
    return () => off?.()
  }, [])

  // on-demand waveform fetch for a marker
  const fetchWave = async (id: string) => {
    try {
      const pkt = (await window.api.invoke('receiver:wave', id)) as WavePayload
      console.log('wave', id, pkt.fs, pkt.values.length, pkt.t0_iso)
      // hook: you could show a modal/mini-plot here
    } catch (e) {
      console.error('wave error', e)
    }
  }

  const pts = useMemo(() => stations.map(s => s.latlng), [stations])
  const valsArray = useMemo(() => stations.map(s => valuesRef.current[s.id] ?? 0), [stations])

  return (
    <div style={{ height: '100vh', display: 'flex' }}>
      <div style={{ width: '30%', minWidth: 280, borderRight: '1px solid #e5e7eb', background: '#fafafa' }}>
        <SettingsPanel stationIds={stations.map(s => s.id)} />
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 12, gap: 12, minWidth: 0 }}>
        <div style={{ fontSize: 12, color: '#6b7280' }}>
          Live updated: {updatedIso}
        </div>

        <div style={{ position: 'relative', width: '100%', flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 0 }}>
          <div style={{ width: '100%', height: '100%', maxHeight: '100%', aspectRatio: '1 / 1' }}>
            <MapContainer style={{ width: '100%', height: '100%' }}>
              <SetView coords={CENTER} zoom={ZOOM} />
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                         attribution="&copy; OpenStreetMap contributors" />
              {mode === 'pin' && (
                <>
                  <StationPins stations={stations} values={valuesRef.current} onWave={fetchWave} />
                  <StationPulse stations={stations} values={valuesRef.current} visible />
                </>
              )}
              {mode === 'overlay' && (
                <GreenHeatOverlay pts={pts} vals={valsArray} visible />
              )}
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
              // quick test: request a /wave for the first station if present
              const first = stations[0]?.id
              if (first) await fetchWave(first)
            }}
          >
            Fetch Wave (first)
          </button>
        </div>
      </div>
    </div>
  )
}
