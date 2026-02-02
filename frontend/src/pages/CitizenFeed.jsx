import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import '../styles/CitizenFeed.css'

function CitizenFeed() {
  const navigate = useNavigate()
  const [user, setUser] = useState(null)
  const [posts, setPosts] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [formData, setFormData] = useState({ title: '', description: '', latitude: '', longitude: '' })
  const [imageFile, setImageFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    const token = localStorage.getItem('token')
    const userData = JSON.parse(localStorage.getItem('user') || '{}')
    if (!token || userData.role !== 'citizen') {
      navigate('/auth')
      return
    }
    setUser(userData)
    loadFeed()
    const interval = setInterval(loadFeed, 5000)
    return () => clearInterval(interval)
  }, [navigate])

  const loadFeed = async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await axios.get('http://127.0.0.1:5000/api/auth/citizen/posts', {
        headers: { Authorization: `Bearer ${token}` }
      })
      setPosts(response.data.posts || [])
    } catch (err) {
      console.error(err)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setUploading(true)
    setMessage('')
    try {
      const token = localStorage.getItem('token')
      const fd = new FormData()
      fd.append('title', formData.title)
      fd.append('description', formData.description)
      if (formData.latitude) fd.append('latitude', String(parseFloat(formData.latitude)))
      if (formData.longitude) fd.append('longitude', String(parseFloat(formData.longitude)))
      fd.append('location_name', 'Current Location')
      if (imageFile) fd.append('image', imageFile)

      const response = await axios.post('http://127.0.0.1:5000/api/auth/citizen/posts', fd, {
        headers: { 
          Authorization: `Bearer ${token}`
        }
      })
      
      console.log('Response:', response.data)
      setMessage('Report submitted successfully! AI is processing your report.')
      setFormData({ title: '', description: '', latitude: '', longitude: '' })
      setImageFile(null)
      setShowModal(false)
      
      // Redirect to feed after successful submission
      setTimeout(() => {
        navigate('/feed')
      }, 2000)
      
    } catch (err) {
      console.error('Submission error:', err)
      setMessage('Failed to submit report: ' + (err.response?.data?.error || 'Unknown error'))
    } finally {
      setUploading(false)
    }
  }

  const handleLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition((pos) => {
        setFormData(prev => ({
          ...prev,
          latitude: pos.coords.latitude.toFixed(6),
          longitude: pos.coords.longitude.toFixed(6)
        }))
        setMessage('Location captured')
      })
    }
  }

  return (
    <div className="citizen-page">
      <div className="header">
        <h1>FLOOD REPORTS</h1>
        <div>
          <button onClick={() => navigate('/feed')} className="btn btn-secondary">VIEW COMMUNITY FEED</button>
          <button onClick={() => setShowModal(true)} className="btn">SUBMIT REPORT</button>
          <button onClick={() => { localStorage.clear(); navigate('/auth') }} className="btn-secondary">LOGOUT</button>
        </div>
      </div>

      {message && <div className="message">{message}</div>}

      <div className="posts">
        {posts.length === 0 ? (
          <p className="empty">No reports yet</p>
        ) : (
          posts.map(post => (
            <div key={post.id} className="card">
              <div className="card-header">
                <h2>{post.title}</h2>
                <span className={`status ${post.status}`}>{post.status.toUpperCase()}</span>
              </div>
              <p>{post.description}</p>
              <div className="meta">
                <span>{post.location_name || 'No location'}</span>
                <span>{new Date(post.created_at).toLocaleString()}</span>
              </div>
            </div>
          ))
        )}
      </div>

      {showModal && (
        <div className="modal" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h2>NEW REPORT</h2>
            <form onSubmit={handleSubmit}>
              <input type="text" placeholder="TITLE" value={formData.title} onChange={e => setFormData({...formData, title: e.target.value})} required />
              <textarea placeholder="DESCRIPTION" value={formData.description} onChange={e => setFormData({...formData, description: e.target.value})} required></textarea>
              <div className="row">
                <input type="number" step="any" placeholder="LATITUDE" value={formData.latitude} onChange={e => setFormData({...formData, latitude: e.target.value})} />
                <input type="number" step="any" placeholder="LONGITUDE" value={formData.longitude} onChange={e => setFormData({...formData, longitude: e.target.value})} />
              </div>
              <input type="file" accept="image/*" onChange={e => setImageFile(e.target.files?.[0] || null)} />
              <button type="button" onClick={handleLocation} className="btn-secondary">USE MY LOCATION</button>
              <div className="actions">
                <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">CANCEL</button>
                <button type="submit" disabled={uploading} className="btn">{uploading ? 'SUBMITTING...' : 'SUBMIT'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default CitizenFeed
