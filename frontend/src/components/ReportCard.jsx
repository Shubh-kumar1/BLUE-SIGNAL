import React from 'react'
import { formatDate, getUrgencyColor, getHazardIcon } from '../utils/helpers'
import '../styles/ReportCard.css'

function ReportCard({ report }) {
  const urgencyColor = getUrgencyColor(report.urgency)
  const hazardIcon = getHazardIcon(report.hazard_type)
  const formattedDate = formatDate(report.timestamp)

  return (
    <div className="report-card">
      <div className="report-card-header">
        <span 
          className={`urgency-badge urgency-${report.urgency?.toLowerCase().replace(' ', '-')}`}
          style={{ backgroundColor: urgencyColor }}
        >
          {report.urgency?.toUpperCase()}
        </span>
        {report.urgency === 'Urgent Panic' && (
          <span className="urgent-indicator">URGENT</span>
        )}
      </div>

      <div className="hazard-type">
        <span className="hazard-icon">{hazardIcon}</span>
        <span className="hazard-name">{report.hazard_type}</span>
      </div>

      <h3 className="report-title">{report.title}</h3>
      
      <div className="report-location">
        📍 {report.location}
        {report.coordinates && (
          <span className="coordinates">
            ({report.coordinates.latitude.toFixed(4)}, {report.coordinates.longitude.toFixed(4)})
          </span>
        )}
      </div>

      <p className="report-description">{report.description}</p>

      <div className="report-metadata">
        <div className="metadata-item">
          <span className="metadata-label">Affected:</span>
          <span className="metadata-value">{report.affected_people} people</span>
        </div>
        <div className="metadata-item">
          <span className="metadata-label">Confidence:</span>
          <span className="metadata-value">{(report.confidence_score * 100).toFixed(0)}%</span>
        </div>
        <div className="metadata-item">
          <span className="metadata-label">Sources:</span>
          <span className="metadata-value">{report.sources_count} reports</span>
        </div>
      </div>

      {report.image_classification && (
        <div className="image-classification">
          <span className="classification-label">📷 Image Classification:</span>
          <span className="classification-value">
            {report.image_classification.type} ({(report.image_classification.confidence * 100).toFixed(0)}%)
          </span>
        </div>
      )}

      <div className="report-footer">
        <span className={`status-badge status-${report.status}`}>
          {report.status?.toUpperCase()}
        </span>
        <span className="report-timestamp">⏰ {formattedDate}</span>
      </div>

      {report.verified && (
        <div className="verified-badge">✓ {report.verification_status || 'Verified'}</div>
      )}
    </div>
  )
}

export default ReportCard

