/**
 * Utility helper functions for BlueSignal frontend
 */

/**
 * Format ISO timestamp to human-readable format
 * @param {string} timestamp - ISO format timestamp
 * @returns {string} Formatted date string
 */
export const formatDate = (timestamp) => {
  if (!timestamp) return 'N/A'
  
  try {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)
    
    // Show relative time for recent reports
    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`
    
    // For older reports, show full date
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch (error) {
    console.error('Error formatting date:', error)
    return 'Invalid date'
  }
}

/**
 * Get color code for urgency level
 * @param {string} urgency - Urgency level (Urgent Panic, Alert Caution, Safe Normal)
 * @returns {string} Hex color code
 */
export const getUrgencyColor = (urgency) => {
  const colors = {
    'urgent panic': '#dc2626',    // Red
    'alert caution': '#f59e0b',   // Orange
    'safe normal': '#10b981',     // Green
  }
  return colors[urgency?.toLowerCase()] || '#6b7280' // Gray as fallback
}

/**
 * Get placeholder text for hazard type
 * @param {string} hazardType - Hazard type
 * @returns {string} Placeholder text
 */
export const getHazardIcon = (hazardType) => {
  const icons = {
    'Tsunami': '[Wave Icon]',
    'Cyclone/Storm Surge': '[Storm Icon]',
    'Coastal Flooding': '[Water Icon]',
    'High Waves/Rough Sea': '[Wave Icon]',
    'Rip Current': '[Current Icon]',
    'Oil Spill/Pollution': '[Pollution Icon]',
    'Coastal Erosion/Landslide': '[Erosion Icon]',
    'Marine Accident/Rescue Needed': '[Rescue Icon]',
    'Sea Water Intrusion': '[Intrusion Icon]',
    'Other/Unknown Hazard': '[Warning Icon]'
  }
  return icons[hazardType] || '[Warning Icon]'
}

/**
 * Format large numbers with K/M suffixes
 * @param {number} num - Number to format
 * @returns {string} Formatted number string
 */
export const formatNumber = (num) => {
  if (!num) return '0'
  
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(1)}M`
  } else if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}K`
  }
  return num.toString()
}

/**
 * Format coordinates for display
 * @param {number} lat - Latitude
 * @param {number} lng - Longitude
 * @param {number} precision - Decimal places
 * @returns {string} Formatted coordinates
 */
export const formatCoordinates = (lat, lng, precision = 4) => {
  if (lat === undefined || lng === undefined) return 'N/A'
  return `${lat.toFixed(precision)}°N, ${lng.toFixed(precision)}°E`
}

/**
 * Truncate text to specified length
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} Truncated text
 */
export const truncateText = (text, maxLength = 100) => {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

/**
 * Calculate confidence level label
 * @param {number} score - Confidence score (0-1)
 * @returns {string} Confidence level label
 */
export const getConfidenceLevel = (score) => {
  if (score >= 0.9) return 'Very High'
  if (score >= 0.75) return 'High'
  if (score >= 0.6) return 'Medium'
  if (score >= 0.4) return 'Low'
  return 'Very Low'
}

/**
 * Sort reports by priority (urgency + timestamp)
 * @param {Array} reports - Array of reports
 * @returns {Array} Sorted reports
 */
export const sortReportsByPriority = (reports) => {
  const urgencyOrder = { 'Urgent Panic': 0, 'Alert Caution': 1, 'Safe Normal': 2 }
  
  return [...reports].sort((a, b) => {
    // First sort by urgency
    const urgencyDiff = urgencyOrder[a.urgency] - urgencyOrder[b.urgency]
    if (urgencyDiff !== 0) return urgencyDiff
    
    // Then sort by timestamp (newest first)
    return new Date(b.timestamp) - new Date(a.timestamp)
  })
}

/**
 * Filter reports by search query
 * @param {Array} reports - Array of reports
 * @param {string} query - Search query
 * @returns {Array} Filtered reports
 */
export const filterReports = (reports, query) => {
  if (!query || !query.trim()) return reports
  
  const searchTerm = query.toLowerCase().trim()
  
  return reports.filter(report => 
    report.title?.toLowerCase().includes(searchTerm) ||
    report.description?.toLowerCase().includes(searchTerm) ||
    report.location?.toLowerCase().includes(searchTerm)
  )
}

/**
 * Validate if backend is reachable
 * @returns {Promise<boolean>} True if backend is reachable
 */
export const checkBackendConnection = async () => {
  try {
    const response = await fetch('http://127.0.0.1:5000/api/health')
    return response.ok
  } catch (error) {
    return false
  }
}

/**
 * Debounce function for search/filter inputs
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
export const debounce = (func, wait = 300) => {
  let timeout
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout)
      func(...args)
    }
    clearTimeout(timeout)
    timeout = setTimeout(later, wait)
  }
}

/**
 * Get status badge color
 * @param {string} status - Report status
 * @returns {string} Color code
 */
export const getStatusColor = (status) => {
  const colors = {
    active: '#ef4444',
    monitoring: '#f59e0b',
    resolving: '#10b981',
    resolved: '#6b7280',
  }
  return colors[status?.toLowerCase()] || '#6b7280'
}

/**
 * Export data as JSON file
 * @param {any} data - Data to export
 * @param {string} filename - Output filename
 */
export const exportToJSON = (data, filename = 'reports.json') => {
  const json = JSON.stringify(data, null, 2)
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

