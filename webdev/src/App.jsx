import React, { useState,  useRef, useEffect } from "react";
import { MapContainer, TileLayer, useMap, LayerGroup, Rectangle } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const bounds = [
  [-32, 115.5],  // Southwest corner (lat, lon)
  [-31.25, 116.5],  // Northeast corner (lat, lon)
];

// Generate 10-step green to red colors with increasing red intensity
function generateColorSteps() {
  const steps = 10;
  const colors = [];

  for (let i = 0; i < steps; i++) {
    // red increases linearly from 0 to 255
    const red = Math.floor((255 / (steps - 1)) * i);
    // green decreases slightly from 128 to 60 (keeps some green)
    const green = Math.floor(128 - (68 / (steps - 1)) * i);
    const blue = 0; // keep blue at zero
    const alpha = 0.8;

    colors.push(`rgba(${red},${green},${blue},${alpha})`);
  }

  return colors;
}

const colorSteps = generateColorSteps();

function getDistance(i1, j1, i2, j2) {
  return Math.sqrt((i1 - i2) ** 2 + (j1 - j2) ** 2);
}

function GridOverlay({ show }) {
  if (!show) return null;

  const rows = 100;
  const cols = 100;
  const latStep = (bounds[1][0] - bounds[0][0]) / rows;
  const lngStep = (bounds[1][1] - bounds[0][1]) / cols;

  const numHotspots = 5;
  const hotspots = [];
  for (let h = 0; h < numHotspots; h++) {
    hotspots.push({
      i: Math.floor(Math.random() * rows),
      j: Math.floor(Math.random() * cols),
    });
  }

  const maxRadius = 10; // hotspot influence radius

  const grid = [];
  for (let i = 0; i < rows; i++) {
    for (let j = 0; j < cols; j++) {
      // Find min distance to any hotspot
      let minDist = Infinity;
      for (const hs of hotspots) {
        const dist = getDistance(i, j, hs.i, hs.j);
        if (dist < minDist) minDist = dist;
      }

      // Calculate intensity index: 0 = no movement (green), 9 = max movement (red)
      let intensity = 0;
      if (minDist <= maxRadius) {
        // intensity goes from 9 (close) down to 0 (far)
        intensity = Math.floor(((maxRadius - minDist) / maxRadius) * (colorSteps.length - 1));
      }

      const fillColor = colorSteps[intensity];

      const southWest = [bounds[0][0] + i * latStep, bounds[0][1] + j * lngStep];
      const northEast = [bounds[0][0] + (i + 1) * latStep, bounds[0][1] + (j + 1) * lngStep];

      grid.push(
        <Rectangle
          key={`${i}-${j}`}
          bounds={[southWest, northEast]}
          pathOptions={{ color: "white", weight: 0.3, fillColor, fillOpacity: 0.5 }}
        />
      );
    }
  }

  return <LayerGroup>{grid}</LayerGroup>;
}


function ChangeView({ center, zoom }) {
  const map = useMap();
  const initial = useRef(true);

  useEffect(() => {
    if (initial.current) {
      map.setView(center, zoom);
      initial.current = false;
    } else {
      map.setZoom(zoom);
    }
  }, [center, zoom, map]);

  return null;
}

export default function App() {
  const [zoom, setZoom] = useState(12);
  const [showGrid, setShowGrid] = useState(false);

  return (
    <div style={{ display: "flex", height: "100vh", width: "100vw", overflow: "hidden" }}>
      
      {/* Left sidebar 30% */}
      <div
        style={{
          width: "30%",
          backgroundColor: "#f5f5f5",
          padding: "10px",
          boxSizing: "border-box",
          overflowY: "auto",
          color: "#000", // set all text black by default here
        }}
      >
        <h2 style={{ color: "#000" }}>Controls</h2>

        <div
          style={{
            height: "60px",
            backgroundColor: "#ddd",
            marginBottom: "10px",
            padding: "8px",
            boxSizing: "border-box",
          }}
        >
          <strong>Filter</strong>
          <p style={{ margin: "4px 0 0" }}>
            Select and filter seismic data based on date, magnitude, or station.
          </p>
        </div>

        <div
          style={{
            height: "60px",
            backgroundColor: "#ddd",
            marginBottom: "10px",
            padding: "8px",
            boxSizing: "border-box",
          }}
        >
          <strong>Station List</strong>
          <p style={{ margin: "4px 0 0" }}>
            Browse and select stations from the available seismic network.
          </p>
        </div>

        <div
          style={{
            height: "60px",
            backgroundColor: "#ddd",
            marginBottom: "10px",
            padding: "8px",
            boxSizing: "border-box",
          }}
        >
          <strong>Settings</strong>
          <p style={{ margin: "4px 0 0" }}>
            Adjust preferences, update refresh rates, and configure alerts.
          </p>
        </div>

        <div
          style={{
            height: "120px",
            backgroundColor: "#ddd",
            marginTop: "20px",
            padding: "8px",
            boxSizing: "border-box",
          }}
        >
          <strong>Data Stream Graph</strong>
          <p style={{ margin: "4px 0 0" }}>
            This section will display real-time graphs for selected station data streams.
          </p>
        </div>

        <div
          style={{
            height: "120px",
            backgroundColor: "#ddd",
            marginTop: "10px",
            padding: "8px",
            boxSizing: "border-box",
          }}
        >
          <strong>Notifications</strong>
          <p style={{ margin: "4px 0 0" }}>
            Alerts and system messages related to seismic activity and system status.
          </p>
        </div>
      </div>


      {/* Right side 60% */}
      <div
        style={{
          width: "60%",
          padding: "10px",
          boxSizing: "border-box",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          height: "100%",
        }}
      >
        {/* Map container 80% height of right section */}
        <div style={{ width: "80%", height: "80%", aspectRatio: "1 / 1" }}>
          <MapContainer
            center={[-31.95, 115.86]}
            zoom={zoom}
            style={{ height: "100%", width: "100%" }}
            scrollWheelZoom={false}
          >
            <ChangeView center={[-31.95, 115.86]} zoom={zoom} />
            <TileLayer
              attribution="&copy; OpenStreetMap contributors"
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <GridOverlay show={showGrid} />
          </MapContainer>
        </div>

        {/* Zoom slider */}
        <input
          type="range"
          min={1}
          max={18}
          value={zoom}
          onChange={(e) => setZoom(Number(e.target.value))}
          style={{ width: "100%", marginTop: "10px" }}
        />

        {/* Time slider (no functionality) */}
        <input
          type="range"
          min={0}
          max={100}
          defaultValue={50}
          style={{ width: "100%", marginTop: "10px" }}
        />

        {/* Buttons row */}
        <div
          style={{
            marginTop: "10px",
            display: "flex",
            justifyContent: "space-between",
            width: "100%",
          }}
        >
          <button style={{ flex: 1, marginRight: "5px" }}>Button 1</button>
          <button style={{ flex: 1, marginRight: "5px" }}>Button 2</button>
          <button style={{ flex: 1 }} onClick={() => setShowGrid(!showGrid)}>
            Toggle Grid Overlay
          </button>
        </div>
      </div>

      {/* Remaining 10% empty space */}
      <div style={{ width: "10%" }}></div>
    </div>
  );
}
