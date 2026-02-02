import React, { useEffect, useRef } from 'react'
import '../styles/FloodMap.css'

function FloodMap({ reports = [] }) {
  const mapRef = useRef(null)
  const mapInstanceRef = useRef(null)

  useEffect(() => {
    if (!mapInstanceRef.current && mapRef.current) {
      const map = L.map(mapRef.current).setView([20.5937, 78.9629], 5)

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map)

      mapInstanceRef.current = map
    }

    if (mapInstanceRef.current && reports.length > 0) {
      mapInstanceRef.current.eachLayer((layer) => {
        if (layer instanceof L.Marker) {
          mapInstanceRef.current.removeLayer(layer)
        }
      })

      reports.forEach((report) => {
        if (report.coordinates) {
          const { latitude, longitude } = report.coordinates

          const iconColor = getMarkerColor(report.urgency)
          const customIcon = L.divIcon({
            className: 'custom-marker',
            html: `<div style="background-color: ${iconColor}; width: 24px; height: 24px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12],
          })

          const marker = L.marker([latitude, longitude], { icon: customIcon }).addTo(
            mapInstanceRef.current
          )

          marker.bindPopup(`
            <div style="font-family: 'Roboto Mono', monospace; min-width: 200px;">
              <h3 style="margin: 0 0 8px 0; font-size: 14px; font-weight: 600;">${report.title}</h3>
              <p style="margin: 4px 0; font-size: 12px;"><strong>Type:</strong> ${report.hazard_type || report.flood_type || 'Unknown'}</p>
              <p style="margin: 4px 0; font-size: 12px;"><strong>Urgency:</strong> ${report.urgency}</p>
              <p style="margin: 4px 0; font-size: 12px;"><strong>Location:</strong> ${report.location}</p>
              <p style="margin: 4px 0; font-size: 12px;"><strong>Affected:</strong> ${report.affected_people} people</p>
              ${report.verified ? '<p style="margin: 4px 0; font-size: 12px; color: #10b981;"><strong>✓ Verified</strong></p>' : ''}
            </div>
          `)
        }
      })
    }

    return () => {}
  }, [reports])

  const getMarkerColor = (urgency) => {
    const urgencyColors = {
      'Severe Flooding': '#EF4444',
      'Urgent Panic': '#EF4444',
      'Moderate Waterlogging': '#F59E0B',
      'Alert Caution': '#F59E0B',
      'Mild Alert': '#60A5FA',
      'Safe Normal': '#10B981',
      'Safe': '#10B981',
    }
    return urgencyColors[urgency] || '#6B7280'
  }

  return (
    <div className="flood-map-container">
      <div className="map-header">
        <h3 className="map-title">🗺️ Live Flood Map</h3>
        <p className="map-subtitle">Real-time verified flood reports across regions</p>
      </div>
      <div ref={mapRef} className="leaflet-map" id="flood-map"></div>
      <div className="map-legend">
        <div className="legend-item">
          <span className="legend-marker" style={{ backgroundColor: '#EF4444' }}></span>
          <span className="legend-label">Severe Flooding</span>
        </div>
        <div className="legend-item">
          <span className="legend-marker" style={{ backgroundColor: '#F59E0B' }}></span>
          <span className="legend-label">Moderate Waterlogging</span>
        </div>
        <div className="legend-item">
          <span className="legend-marker" style={{ backgroundColor: '#60A5FA' }}></span>
          <span className="legend-label">Mild Alert</span>
        </div>
        <div className="legend-item">
          <span className="legend-marker" style={{ backgroundColor: '#10B981' }}></span>
          <span className="legend-label">Safe</span>
        </div>
      </div>
    </div>
  )
}

export default FloodMap

