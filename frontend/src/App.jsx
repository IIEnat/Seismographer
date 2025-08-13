import { useEffect, useMemo, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import axios from 'axios'

export default function App() {
  const [stations, setStations] = useState([])
  const [latest, setLatest] = useState({})

  // load once
  useEffect(() => {
    axios.get('/api/stations').then(res => setStations(res.data))
  }, [])

  // poll latest readings every 3s
  useEffect(() => {
    const fetchLatest = () => axios.get('/api/readings/latest').then(res => setLatest(res.data))
    fetchLatest()
    const id = setInterval(fetchLatest, 3000)
    return () => clearInterval(id)
  }, [])

  const markers = useMemo(() => {
    const arr = []
    for (const s of stations) {
      const code = s.code
      const info = latest[code]
      const value = info?.value ?? 0
      const radius = Math.min(20, 4 + value) // quick visual mapping
      arr.push({ ...s, value, radius, ts: info?.ts })
    }
    return arr
  }, [stations, latest])

  return (
    <div style={{height:'100vh', width:'100vw'}}>
      <MapContainer center={[-25, 133]} zoom={4} style={{height:'100%', width:'100%'}}>
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                   attribution="&copy; OpenStreetMap contributors"/>
        {markers.map(m => (
          <CircleMarker key={m.code}
            center={[m.lat, m.lon]}
            radius={m.radius}
            stroke={false}
            fillOpacity={0.7}>
            <Tooltip>
              <div>
                <div><b>{m.code}</b></div>
                <div>RMS(Z): {m.value?.toFixed?.(3) ?? '—'}</div>
                <div>{m.ts || ''}</div>
              </div>
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  )
}
