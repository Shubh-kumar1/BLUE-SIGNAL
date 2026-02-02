import axios from 'axios'

const api = axios.create({
  baseURL: 'http://127.0.0.1:5000/api',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use(
  (config) => {
    console.log(`[API Request] ${config.method.toUpperCase()} ${config.url}`)
    return config
  },
  (error) => {
    console.error('[API Request Error]', error)
    return Promise.reject(error)
  }
)

api.interceptors.response.use(
  (response) => {
    console.log(`[API Response] ${response.status} ${response.config.url}`)
    return response.data
  },
  (error) => {
    console.error('[API Response Error]', error.response?.data || error.message)
    
    if (error.response) {
      const message = error.response.data?.error || error.response.data?.message || error.response.statusText
      throw new Error(message)
    } else if (error.request) {
      throw new Error('No response from server. Please check if the backend is running.')
    } else {
      throw new Error(error.message)
    }
  }
)

/**
 * Fetch hazard reports from the backend
 * @param {string} hazardType - Optional hazard type filter
 * @param {string} urgency - Optional urgency filter (Urgent Panic, Alert Caution, Safe Normal)
 * @param {string} location - Optional location filter
 * @param {boolean} verifiedOnly - Show only verified reports
 * @returns {Promise} Promise resolving to reports data
 */
export const fetchReports = async (hazardType = '', urgency = '', location = '', verifiedOnly = false) => {
  const params = {}
  if (hazardType) params.hazard_type = hazardType
  if (urgency) params.urgency = urgency
  if (location) params.location = location
  if (verifiedOnly) params.verified_only = verifiedOnly
  
  return await api.get('/reports', { params })
}

/**
 * Classify text for urgency and hazard type
 * @param {string} text - Text to classify
 * @returns {Promise} Promise resolving to classification results
 */
export const classifyText = async (text) => {
  return await api.post('/classify/text', { text })
}

/**
 * Classify image for ocean disaster type
 * @param {string} imagePath - Path to image file
 * @returns {Promise} Promise resolving to image classification
 */
export const classifyImage = async (imagePath) => {
  return await api.post('/classify/image', { image_path: imagePath })
}

/**
 * Process complete citizen report with verification
 * @param {Object} reportData - Citizen report data
 * @returns {Promise} Promise resolving to processed report
 */
export const processCitizenReport = async (reportData) => {
  return await api.post('/process-citizen-report', reportData)
}

/**
 * Health check endpoint
 * @returns {Promise} Promise resolving to health status
 */
export const healthCheck = async () => {
  return await api.get('/health')
}

/**
 * Get summary statistics for all reports
 * @returns {Promise} Promise resolving to statistics
 */
export const getStatistics = async () => {
  const data = await fetchReports()
  const reports = data.reports || []
  
  return {
    total: reports.length,
    urgentPanic: reports.filter(r => r.urgency === 'Urgent Panic').length,
    alertCaution: reports.filter(r => r.urgency === 'Alert Caution').length,
    safeNormal: reports.filter(r => r.urgency === 'Safe Normal').length,
    verified: reports.filter(r => r.verified).length,
    totalAffected: reports.reduce((sum, r) => sum + (r.affected_people || 0), 0),
  }
}

/**
 * Debug verification process
 * @param {string} citizenText - Citizen report text
 * @param {string} socialText - Social media text
 * @returns {Promise} Promise resolving to verification debug data
 */
export const debugVerification = async (citizenText, socialText) => {
  return await api.post('/debug/verification', {
    citizen_text: citizenText,
    social_text: socialText
  })
}

export default api

