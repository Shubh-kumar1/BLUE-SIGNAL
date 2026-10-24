import React, { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { API_BASE_URL } from '../api/api'
import {
  AUTH_REQUEST_TIMEOUT_MS,
  getAuthErrorMessage,
  parseAuthResponse,
  runAuthSubmission
} from '../utils/auth'
import '../styles/AuthPage.css'

function AuthPage() {
  const navigate = useNavigate()
  
  // Citizen form state
  const [citizenMode, setCitizenMode] = useState('login') // 'login' or 'signup'
  const [citizenData, setCitizenData] = useState({
    username: '',
    email: '',
    password: '',
    full_name: '',
    location: ''
  })
  
  // Authority form state
  const [authorityMode, setAuthorityMode] = useState('login')
  const [authorityData, setAuthorityData] = useState({
    username: '',
    email: '',
    password: '',
    organization: '',
    official_email: ''
  })
  
  const [loading, setLoading] = useState({ citizen: false, authority: false })
  const [errors, setErrors] = useState({ citizen: '', authority: '' })
  const citizenSubmissionLock = useRef(false)
  const authoritySubmissionLock = useRef(false)

  // Citizen handlers
  const handleCitizenChange = (e) => {
    setCitizenData({ ...citizenData, [e.target.name]: e.target.value })
    setErrors((current) => ({ ...current, citizen: '' }))
  }

  const handleCitizenSubmit = async (e) => {
    e.preventDefault()
    if (!e.currentTarget.checkValidity()) {
      e.currentTarget.reportValidity()
      return
    }
    setErrors((current) => ({ ...current, citizen: '' }))

    let accountCreated = false
    try {
      await runAuthSubmission(citizenSubmissionLock, (isLoading) => {
        setLoading((current) => ({ ...current, citizen: isLoading }))
      }, async () => {
        if (citizenMode === 'signup') {
          await axios.post(`${API_BASE_URL}/api/auth/register`, {
            ...citizenData,
            role: 'citizen'
          }, { timeout: AUTH_REQUEST_TIMEOUT_MS })
          accountCreated = true
        }

        const response = await axios.post(`${API_BASE_URL}/api/auth/login`, {
          username: citizenData.username,
          password: citizenData.password
        }, { timeout: AUTH_REQUEST_TIMEOUT_MS })
        const authData = parseAuthResponse(response, 'citizen')

        try {
          localStorage.setItem('token', authData.token)
          localStorage.setItem('user', JSON.stringify(authData.user))
        } catch (storageError) {
          const error = new Error('Could not save session')
          error.code = 'SESSION_STORAGE_FAILED'
          throw error
        }
        navigate('/report')
      })
    } catch (err) {
      setErrors((current) => ({
        ...current,
        citizen: getAuthErrorMessage(err, accountCreated)
      }))
    }
  }

  // Authority handlers
  const handleAuthorityChange = (e) => {
    setAuthorityData({ ...authorityData, [e.target.name]: e.target.value })
    setErrors((current) => ({ ...current, authority: '' }))
  }

  const handleAuthoritySubmit = async (e) => {
    e.preventDefault()
    if (!e.currentTarget.checkValidity()) {
      e.currentTarget.reportValidity()
      return
    }
    setErrors((current) => ({ ...current, authority: '' }))

    let accountCreated = false
    try {
      await runAuthSubmission(authoritySubmissionLock, (isLoading) => {
        setLoading((current) => ({ ...current, authority: isLoading }))
      }, async () => {
        if (authorityMode === 'signup') {
          await axios.post(`${API_BASE_URL}/api/auth/register`, {
            username: authorityData.username,
            email: authorityData.official_email || authorityData.email,
            password: authorityData.password,
            full_name: authorityData.organization,
            role: 'authority'
          }, { timeout: AUTH_REQUEST_TIMEOUT_MS })
          accountCreated = true
        }

        const response = await axios.post(`${API_BASE_URL}/api/auth/login`, {
          username: authorityData.username,
          password: authorityData.password
        }, { timeout: AUTH_REQUEST_TIMEOUT_MS })
        const authData = parseAuthResponse(response, 'authority')

        try {
          localStorage.setItem('token', authData.token)
          localStorage.setItem('user', JSON.stringify(authData.user))
        } catch (storageError) {
          const error = new Error('Could not save session')
          error.code = 'SESSION_STORAGE_FAILED'
          throw error
        }
        navigate('/dashboard')
      })
    } catch (err) {
      setErrors((current) => ({
        ...current,
        authority: getAuthErrorMessage(err, accountCreated)
      }))
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-split-container">
        {/* Citizen Portal - Left Side */}
        <div className="auth-panel citizen-panel">
          <div className="auth-panel-content">
            <div className="panel-header">
              <div className="panel-icon">[Icon]</div>
              <h2 className="panel-title">Citizen Portal</h2>
              <p className="panel-subtitle">Submit flood reports and help your city stay safe</p>
            </div>

            {errors.citizen && <div className="error-message" role="alert" aria-live="assertive">{errors.citizen}</div>}

            <div className="mode-toggle">
              <button
                className={citizenMode === 'login' ? 'active' : ''}
                onClick={() => {
                  setCitizenMode('login')
                  setErrors((current) => ({ ...current, citizen: '' }))
                }}
                disabled={loading.citizen}
              >
                Login
              </button>
              <button
                className={citizenMode === 'signup' ? 'active' : ''}
                onClick={() => {
                  setCitizenMode('signup')
                  setErrors((current) => ({ ...current, citizen: '' }))
                }}
                disabled={loading.citizen}
              >
                Signup
              </button>
            </div>

            <form onSubmit={handleCitizenSubmit} className="auth-form">
              {citizenMode === 'signup' && (
                <div className="form-group">
                  <label>Full Name</label>
                  <input
                    type="text"
                    name="full_name"
                    value={citizenData.full_name}
                    onChange={handleCitizenChange}
                    placeholder="John Doe"
                    required={citizenMode === 'signup'}
                  />
                </div>
              )}

              <div className="form-group">
                <label>Username</label>
                <input
                  type="text"
                  name="username"
                  value={citizenData.username}
                  onChange={handleCitizenChange}
                  placeholder="johndoe"
                  required
                />
              </div>

              {citizenMode === 'signup' && (
                <div className="form-group">
                  <label>Email</label>
                  <input
                    type="email"
                    name="email"
                    value={citizenData.email}
                    onChange={handleCitizenChange}
                    placeholder="john@example.com"
                    required={citizenMode === 'signup'}
                  />
                </div>
              )}

              <div className="form-group">
                <label>Password</label>
                <input
                  type="password"
                  name="password"
                  value={citizenData.password}
                  onChange={handleCitizenChange}
                  placeholder="••••••••"
                  required
                  minLength="6"
                />
              </div>

              {citizenMode === 'signup' && (
                <div className="form-group">
                  <label>Location (Optional)</label>
                  <input
                    type="text"
                    name="location"
                    value={citizenData.location}
                    onChange={handleCitizenChange}
                    placeholder="Mumbai, Maharashtra"
                  />
                </div>
              )}

              <button type="submit" className="submit-btn" disabled={loading.citizen}>
                {loading.citizen ? (
                  <><span className="spinner"></span> {citizenMode === 'login' ? 'Logging in...' : 'Creating account...'}</>
                ) : (
                  citizenMode === 'login' ? 'Login as Citizen' : 'Create Citizen Account'
                )}
              </button>
            </form>

            <div className="panel-footer">
              <p className="info-text">
                Report floods in your area<br/>
                Upload photos and videos<br/>
                Help authorities respond faster
              </p>
            </div>
          </div>
        </div>

        {/* Authority Portal - Right Side */}
        <div className="auth-panel authority-panel">
          <div className="auth-panel-content">
            <div className="panel-header">
              <div className="panel-icon">[Icon]</div>
              <h2 className="panel-title">Authority Portal</h2>
              <p className="panel-subtitle">Monitor verified flood alerts and take timely action</p>
            </div>

            {errors.authority && <div className="error-message" role="alert" aria-live="assertive">{errors.authority}</div>}

            <div className="mode-toggle">
              <button
                className={authorityMode === 'login' ? 'active' : ''}
                onClick={() => {
                  setAuthorityMode('login')
                  setErrors((current) => ({ ...current, authority: '' }))
                }}
                disabled={loading.authority}
              >
                Login
              </button>
              <button
                className={authorityMode === 'signup' ? 'active' : ''}
                onClick={() => {
                  setAuthorityMode('signup')
                  setErrors((current) => ({ ...current, authority: '' }))
                }}
                disabled={loading.authority}
              >
                Signup
              </button>
            </div>

            <form onSubmit={handleAuthoritySubmit} className="auth-form">
              {authorityMode === 'signup' && (
                <div className="form-group">
                  <label>Organization Name</label>
                  <input
                    type="text"
                    name="organization"
                    value={authorityData.organization}
                    onChange={handleAuthorityChange}
                    placeholder="Municipal Corporation"
                    required={authorityMode === 'signup'}
                  />
                </div>
              )}

              <div className="form-group">
                <label>Username</label>
                <input
                  type="text"
                  name="username"
                  value={authorityData.username}
                  onChange={handleAuthorityChange}
                  placeholder="admin_mumbai"
                  required
                />
              </div>

              {authorityMode === 'signup' && (
                <div className="form-group">
                  <label>Official Email</label>
                  <input
                    type="email"
                    name="official_email"
                    value={authorityData.official_email}
                    onChange={handleAuthorityChange}
                    placeholder="admin@municipal.gov.in"
                    required={authorityMode === 'signup'}
                  />
                </div>
              )}

              <div className="form-group">
                <label>Password</label>
                <input
                  type="password"
                  name="password"
                  value={authorityData.password}
                  onChange={handleAuthorityChange}
                  placeholder="••••••••"
                  required
                  minLength="6"
                />
              </div>

              <button type="submit" className="submit-btn" disabled={loading.authority}>
                {loading.authority ? (
                  <><span className="spinner"></span> {authorityMode === 'login' ? 'Logging in...' : 'Creating account...'}</>
                ) : (
                  authorityMode === 'login' ? 'Login as Authority' : 'Register Authority Account'
                )}
              </button>
            </form>

            <div className="panel-footer">
              <p className="info-text">
                🔸 Access live flood hotspot map<br/>
                🔸 View verified citizen reports<br/>
                🔸 Download structured data logs
              </p>
            </div>

            {authorityMode === 'login' && (
              <div className="demo-credentials">
                <p className="demo-title">Demo Account:</p>
                <p>Username: <code>admin</code> | Password: <code>admin123</code></p>
                <button
                  type="button"
                  className="demo-fill-btn"
                  onClick={() => {
                    setAuthorityData((current) => ({
                      ...current,
                      username: 'admin',
                      password: 'admin123'
                    }))
                    setErrors((current) => ({ ...current, authority: '' }))
                  }}
                >
                  Fill demo credentials
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Back to Home Link */}
      <div className="back-to-home">
        <button onClick={() => navigate('/')} className="back-btn">
          ← Back to Home
        </button>
      </div>
    </div>
  )
}

export default AuthPage
