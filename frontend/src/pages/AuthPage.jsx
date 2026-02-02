import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
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

  // Citizen handlers
  const handleCitizenChange = (e) => {
    setCitizenData({ ...citizenData, [e.target.name]: e.target.value })
  }

  const handleCitizenSubmit = async (e) => {
    e.preventDefault()
    setLoading({ ...loading, citizen: true })
    setErrors({ ...errors, citizen: '' })

    try {
      console.log('Citizen form data:', citizenData)
      console.log('Citizen mode:', citizenMode)
      
      if (citizenMode === 'signup') {
        console.log('Attempting citizen registration...')
        const registerData = {
          ...citizenData,
          role: 'citizen'
        }
        console.log('Registration data:', registerData)
        
        const registerResponse = await axios.post('http://127.0.0.1:5000/api/auth/register', registerData)
        console.log('Registration response:', registerResponse.data)
      }
      
      console.log('Attempting citizen login...')
      const response = await axios.post('http://127.0.0.1:5000/api/auth/login', {
        username: citizenData.username,
        password: citizenData.password
      })
      console.log('Login response:', response.data)

      if (response.data.token) {
        localStorage.setItem('token', response.data.token)
        localStorage.setItem('user', JSON.stringify(response.data.user))
        navigate('/report')
      }
    } catch (err) {
      console.error('Citizen auth error:', err)
      console.error('Error response:', err.response?.data)
      setErrors({ ...errors, citizen: err.response?.data?.error || 'Authentication failed' })
    } finally {
      setLoading({ ...loading, citizen: false })
    }
  }

  // Authority handlers
  const handleAuthorityChange = (e) => {
    setAuthorityData({ ...authorityData, [e.target.name]: e.target.value })
  }

  const handleAuthoritySubmit = async (e) => {
    e.preventDefault()
    setLoading({ ...loading, authority: true })
    setErrors({ ...errors, authority: '' })

    try {
      if (authorityMode === 'signup') {
        await axios.post('http://127.0.0.1:5000/api/auth/register', {
          username: authorityData.username,
          email: authorityData.official_email || authorityData.email,
          password: authorityData.password,
          full_name: authorityData.organization,
          role: 'authority'
        })
      }
      
      const response = await axios.post('http://127.0.0.1:5000/api/auth/login', {
        username: authorityData.username,
        password: authorityData.password
      })

      if (response.data.token) {
        localStorage.setItem('token', response.data.token)
        localStorage.setItem('user', JSON.stringify(response.data.user))
        navigate('/dashboard')
      }
    } catch (err) {
      setErrors({ ...errors, authority: err.response?.data?.error || 'Authentication failed' })
    } finally {
      setLoading({ ...loading, authority: false })
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

            {errors.citizen && <div className="error-message">{errors.citizen}</div>}

            <div className="mode-toggle">
              <button
                className={citizenMode === 'login' ? 'active' : ''}
                onClick={() => setCitizenMode('login')}
              >
                Login
              </button>
              <button
                className={citizenMode === 'signup' ? 'active' : ''}
                onClick={() => setCitizenMode('signup')}
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
                  <>
                    <span className="spinner"></span> Processing...
                  </>
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

            {errors.authority && <div className="error-message">{errors.authority}</div>}

            <div className="mode-toggle">
              <button
                className={authorityMode === 'login' ? 'active' : ''}
                onClick={() => setAuthorityMode('login')}
              >
                Login
              </button>
              <button
                className={authorityMode === 'signup' ? 'active' : ''}
                onClick={() => setAuthorityMode('signup')}
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
                  <>
                    <span className="spinner"></span> Processing...
                  </>
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

