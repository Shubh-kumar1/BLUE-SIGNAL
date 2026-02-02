import React, { useState, useEffect } from 'react'
import { fetchReports } from '../api/api'
import ReportCard from './ReportCard'
import '../styles/Dashboard.css'

function Dashboard() {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState({ 
    hazardType: '', 
    urgency: '', 
    location: '',
    verifiedOnly: false
  })
  const [stats, setStats] = useState({
    total: 0,
    urgentPanic: 0,
    alertCaution: 0,
    safeNormal: 0,
    verified: 0
  })

  useEffect(() => {
    loadReports()
  }, [filter])

  const loadReports = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const data = await fetchReports(
        filter.hazardType, 
        filter.urgency, 
        filter.location,
        filter.verifiedOnly
      )
      setReports(data.reports || [])
      
      // Calculate statistics
      const reportsList = data.reports || []
      const total = reportsList.length
      const urgentPanic = reportsList.filter(r => r.urgency === 'Urgent Panic').length
      const alertCaution = reportsList.filter(r => r.urgency === 'Alert Caution').length
      const safeNormal = reportsList.filter(r => r.urgency === 'Safe Normal').length
      const verified = reportsList.filter(r => r.verified).length
      
      setStats({ total, urgentPanic, alertCaution, safeNormal, verified })
    } catch (err) {
      setError(err.message || 'Failed to load reports')
      console.error('Error loading reports:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleFilterChange = (e) => {
    const { name, value, type, checked } = e.target
    setFilter(prev => ({ 
      ...prev, 
      [name]: type === 'checkbox' ? checked : value 
    }))
  }

  const clearFilters = () => {
    setFilter({ hazardType: '', urgency: '', location: '', verifiedOnly: false })
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2 className="dashboard-title">Ocean Hazard Reports Dashboard</h2>
        <button className="refresh-button" onClick={loadReports}>
          🔄 Refresh
        </button>
      </div>

      {/* Statistics Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{stats.total}</div>
          <div className="stat-label">Total Reports</div>
        </div>
        <div className="stat-card urgent">
          <div className="stat-value">{stats.urgentPanic}</div>
          <div className="stat-label">Urgent Panic</div>
        </div>
        <div className="stat-card alert">
          <div className="stat-value">{stats.alertCaution}</div>
          <div className="stat-label">Alert Caution</div>
        </div>
        <div className="stat-card verified">
          <div className="stat-value">{stats.verified}</div>
          <div className="stat-label">Verified</div>
        </div>
      </div>

      {/* Filters */}
      <div className="dashboard-filters">
        <select 
          name="hazardType" 
          value={filter.hazardType} 
          onChange={handleFilterChange}
          className="filter-select"
        >
          <option value="">All Hazard Types</option>
          <option value="Tsunami">Tsunami</option>
          <option value="Cyclone/Storm Surge">Cyclone/Storm Surge</option>
          <option value="Coastal Flooding">Coastal Flooding</option>
          <option value="High Waves/Rough Sea">High Waves/Rough Sea</option>
          <option value="Rip Current">Rip Current</option>
          <option value="Oil Spill/Pollution">Oil Spill/Pollution</option>
          <option value="Coastal Erosion/Landslide">Coastal Erosion/Landslide</option>
          <option value="Marine Accident/Rescue Needed">Marine Accident/Rescue Needed</option>
          <option value="Sea Water Intrusion">Sea Water Intrusion</option>
        </select>

        <select 
          name="urgency" 
          value={filter.urgency} 
          onChange={handleFilterChange}
          className="filter-select"
        >
          <option value="">All Urgency Levels</option>
          <option value="Urgent Panic">Urgent Panic</option>
          <option value="Alert Caution">Alert Caution</option>
          <option value="Safe Normal">Safe Normal</option>
        </select>

        <input
          type="text"
          name="location"
          placeholder="Filter by location..."
          value={filter.location}
          onChange={handleFilterChange}
          className="filter-input"
        />

        <label className="checkbox-filter">
          <input
            type="checkbox"
            name="verifiedOnly"
            checked={filter.verifiedOnly}
            onChange={handleFilterChange}
          />
          <span>Verified Only</span>
        </label>

        {(filter.hazardType || filter.urgency || filter.location || filter.verifiedOnly) && (
          <button onClick={clearFilters} className="clear-filters-button">
            Clear Filters
          </button>
        )}
      </div>

      {/* Reports List */}
      <div className="reports-container">
        {loading && (
          <div className="loading">
            <div className="spinner"></div>
            <p>Loading reports...</p>
          </div>
        )}

        {error && (
          <div className="error-message">
            <p>⚠️ {error}</p>
            <button onClick={loadReports}>Try Again</button>
          </div>
        )}

        {!loading && !error && reports.length === 0 && (
          <div className="no-reports">
            <p>No reports found matching your criteria.</p>
          </div>
        )}

        {!loading && !error && reports.length > 0 && (
          <div className="reports-grid">
            {reports.map((report) => (
              <ReportCard key={report.id} report={report} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default Dashboard

