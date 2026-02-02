import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import '../styles/AuthorityDashboard.css'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

function AuthorityDashboard() {
  const navigate = useNavigate()
  const [user, setUser] = useState(null)
  const [reports, setReports] = useState([])
  const [selectedReport, setSelectedReport] = useState(null)
  const mapContainerRef = useRef(null)
  const mapRef = useRef(null)
  const markersRef = useRef([])
  const eventSourceRef = useRef(null)

  useEffect(() => {
    const token = localStorage.getItem('token')
    const userData = JSON.parse(localStorage.getItem('user') || '{}')
    if (!token || userData.role !== 'authority') {
      navigate('/auth')
      return
    }
    setUser(userData)

    ;(async () => {
      try {
        const res = await axios.get('http://127.0.0.1:5000/api/auth/authority/hotspots', {
          headers: { Authorization: `Bearer ${token}` }
        })
        setReports(res.data.hotspots || [])
      } catch (e) {
        console.error(e)
      }
    })()

    try {
      const es = new EventSource(`http://127.0.0.1:5000/api/auth/authority/hotspots/stream?token=${encodeURIComponent(token)}`)
      eventSourceRef.current = es
      es.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data)
          if (msg.type === 'snapshot' && Array.isArray(msg.data)) {
            setReports(msg.data)
          } else if (msg.type === 'hotspot' && msg.data) {
            setReports(prev => {
              const exists = prev.some(r => r.id === msg.data.id)
              if (exists) return prev.map(r => (r.id === msg.data.id ? msg.data : r))
              return [msg.data, ...prev]
            })
          }
        } catch (err) {
          console.error('SSE parse error', err)
        }
      }
      es.onerror = (e) => {
        console.warn('SSE error', e)
      }
    } catch (e) {
      console.error('SSE init error', e)
    }

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [navigate])

  const loadData = async () => {}

  useEffect(() => {
    if (mapRef.current || !mapContainerRef.current) return

    const indiaBounds = [
      [68.0, 6.0],   // SW
      [97.5, 35.8]   // NE
    ]

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: 'https://demotiles.maplibre.org/style.json',
      center: [78.9629, 20.5937], // India centroid
      zoom: 4,
      maxBounds: indiaBounds
    })

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right')
    map.fitBounds(indiaBounds, { padding: 40, duration: 0 })

    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!mapRef.current) return

    markersRef.current.forEach(m => m.remove())
    markersRef.current = []

    reports
      .filter(r => typeof r.longitude === 'number' && typeof r.latitude === 'number')
      .forEach(r => {
        const el = document.createElement('div')
        el.style.width = '12px'
        el.style.height = '12px'
        el.style.borderRadius = '50%'
        el.style.background = '#C62828' // red hotspot
        el.style.border = '2px solid #FFFCEF'
        el.style.boxShadow = '0 0 0 2px rgba(198,40,40,0.25)'

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([r.longitude, r.latitude])
          .setPopup(new maplibregl.Popup({ offset: 12 }).setHTML(
            `<div style="font-family: 'Roboto Mono', monospace; color:#1a1a1a">`
            + `<div style="font-weight:700;margin-bottom:6px">${r.title || 'Report'}</div>`
            + `<div style="font-size:12px;opacity:0.8">${r.location_name || ''}</div>`
            + `</div>`
          ))
          .addTo(mapRef.current)

        el.addEventListener('click', () => setSelectedReport(r))

        markersRef.current.push(marker)
      })
  }, [reports])

  return (
    <div className="authority-page">
      <div className="header">
        <h1>AUTHORITY DASHBOARD</h1>
        <div>
          <button onClick={() => {
            const token = localStorage.getItem('token')
            if (!token) return
            window.open(`http://127.0.0.1:5000/api/auth/authority/reports/export?format=json&token=${encodeURIComponent(token)}`,'_blank')
          }} className="btn" style={{ marginRight: 16 }}>DOWNLOAD JSON</button>
          <button onClick={() => {
            const token = localStorage.getItem('token')
            if (!token) return
            window.open(`http://127.0.0.1:5000/api/auth/authority/reports/export?format=csv&token=${encodeURIComponent(token)}`,'_blank')
          }} className="btn" style={{ marginRight: 16 }}>DOWNLOAD CSV</button>
          <button onClick={() => { localStorage.clear(); navigate('/auth') }} className="btn">LOGOUT</button>
        </div>
      </div>

      <div className="main">
        <div className="map-container">
          <div ref={mapContainerRef} className="map" />
        </div>

        <div className="side-panel">
          {selectedReport ? (
            <div className="report-details">
              <h2>{selectedReport.title}</h2>
              <div className="section">
                <h3>LOCATION</h3>
                <p>{selectedReport.location_name || 'Unknown'}</p>
              </div>
              <div className="section">
                <h3>URGENCY</h3>
                <p>{selectedReport.urgency_level}</p>
              </div>
              <div className="section">
                <h3>TYPE</h3>
                <p>{selectedReport.flood_type}</p>
              </div>
              <div className="section">
                <h3>SUMMARY</h3>
                <p>{selectedReport.ai_summary || 'No summary'}</p>
              </div>
              <div className="section">
                <h3>DESCRIPTION</h3>
                <p>{selectedReport.description}</p>
              </div>
              <button onClick={() => setSelectedReport(null)} className="btn">CLOSE</button>
            </div>
          ) : (
            <div className="no-selection">
              <p>Click a location on the map to view details</p>
            </div>
          )}
        </div>
      </div>

      <div className="stats">
        <div className="stat">
          <div className="stat-value">{reports.length}</div>
          <div className="stat-label">TOTAL</div>
        </div>
        <div className="stat">
          <div className="stat-value">{reports.filter(r => r.status === 'verified').length}</div>
          <div className="stat-label">ACTIVE</div>
        </div>
      </div>
    </div>
  )
}

export default AuthorityDashboard
