import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'
import '../styles/UserProfile.css'

function UserProfile() {
  const { username } = useParams()
  const navigate = useNavigate()
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [currentUser, setCurrentUser] = useState(null)

  useEffect(() => {
    const token = localStorage.getItem('token')
    const userData = JSON.parse(localStorage.getItem('user') || '{}')
    if (!token || userData.role !== 'citizen') {
      navigate('/auth')
      return
    }
    setCurrentUser(userData)
    loadUserProfile()
  }, [username, navigate])

  const loadUserProfile = async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await axios.get(`http://127.0.0.1:5000/api/users/${username}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setUser(response.data.user)
    } catch (err) {
      console.error('Error loading profile:', err)
      if (err.response?.status === 404) {
        navigate('/feed')
      }
    } finally {
      setLoading(false)
    }
  }

  const formatTime = (timestamp) => {
    const date = new Date(timestamp)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getScoreColor = (score) => {
    if (score > 0) return '#4CAF50' // Green
    if (score < 0) return '#F44336' // Red
    return '#FFFCEF' // Neutral
  }

  const getScoreLabel = (score) => {
    if (score > 10) return 'Highly Trusted'
    if (score > 0) return 'Trusted'
    if (score === 0) return 'Neutral'
    if (score > -10) return 'Questionable'
    return 'Untrusted'
  }

  if (loading) {
    return (
      <div className="user-profile">
        <div className="loading">Loading profile...</div>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="user-profile">
        <div className="error">User not found</div>
      </div>
    )
  }

  const totalUpvotes = user.posts?.reduce((sum, post) => sum + post.upvotes, 0) || 0
  const totalDownvotes = user.posts?.reduce((sum, post) => sum + post.downvotes, 0) || 0
  const netScore = totalUpvotes - totalDownvotes

  return (
    <div className="user-profile">
      <div className="profile-header">
        <div className="profile-info">
          <h1 className="username" style={{ color: user.authenticity_score < 0 ? '#F44336' : '#FFFCEF' }}>
            u/{user.username}
          </h1>
          <p className="full-name">{user.full_name}</p>
          <div className="profile-stats">
            <div className="stat">
              <span className="stat-label">Authenticity Score</span>
              <span 
                className="stat-value"
                style={{ color: getScoreColor(user.authenticity_score) }}
              >
                {user.authenticity_score > 0 ? '+' : ''}{user.authenticity_score}
              </span>
              <span 
                className="stat-label"
                style={{ color: getScoreColor(user.authenticity_score) }}
              >
                {getScoreLabel(user.authenticity_score)}
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">Total Posts</span>
              <span className="stat-value">{user.posts?.length || 0}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Net Score</span>
              <span 
                className="stat-value"
                style={{ color: getScoreColor(netScore) }}
              >
                {netScore > 0 ? '+' : ''}{netScore}
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">Member Since</span>
              <span className="stat-value">{formatTime(user.created_at)}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="profile-content">
        <div className="posts-section">
          <h2>Posts by u/{user.username}</h2>
          
          {user.posts && user.posts.length > 0 ? (
            <div className="user-posts">
              {user.posts.map(post => (
                <div key={post.id} className="post-item">
                  <div className="post-header">
                    <h3 className="post-title">{post.title}</h3>
                    <span className="post-time">{formatTime(post.created_at)}</span>
                  </div>
                  <p className="post-description">{post.description}</p>
                  {post.location_name && (
                    <div className="post-location">📍 {post.location_name}</div>
                  )}
                  <div className="post-stats">
                    <span className="upvotes">👍 {post.upvotes}</span>
                    <span className="downvotes">👎 {post.downvotes}</span>
                    <span className="net-score">
                      Score: {post.upvotes - post.downvotes}
                    </span>
                    <span className="status">{post.status}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="no-posts">
              <p>No posts yet</p>
            </div>
          )}
        </div>
      </div>

      <div className="profile-footer">
        <button 
          className="back-btn"
          onClick={() => navigate('/feed')}
        >
          ← Back to Feed
        </button>
      </div>
    </div>
  )
}

export default UserProfile
