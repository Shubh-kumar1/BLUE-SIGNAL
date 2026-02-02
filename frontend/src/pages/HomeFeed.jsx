import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import '../styles/HomeFeed.css'

function HomeFeed() {
  const navigate = useNavigate()
  const [user, setUser] = useState(null)
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(true)
  const [userVotes, setUserVotes] = useState({})
  const esRef = useRef(null)

  useEffect(() => {
    const token = localStorage.getItem('token')
    const userData = JSON.parse(localStorage.getItem('user') || '{}')
    if (!token || userData.role !== 'citizen') {
      navigate('/auth')
      return
    }
    setUser(userData)
    loadPosts()
    // SSE subscription for real-time updates
    try {
      const es = new EventSource(`http://127.0.0.1:5000/api/posts/stream?token=${encodeURIComponent(token)}`)
      esRef.current = es
      es.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data)
          if (msg.type === 'snapshot' && Array.isArray(msg.data)) {
            setPosts(msg.data)
          } else if (msg.type === 'post' && msg.data) {
            setPosts(prev => {
              const exists = prev.some(p => p.id === msg.data.id)
              if (exists) return prev.map(p => (p.id === msg.data.id ? msg.data : p))
              return [msg.data, ...prev]
            })
          }
        } catch {}
      }
      es.onerror = () => {}
    } catch {}
    return () => {
      if (esRef.current) esRef.current.close()
    }
  }, [navigate])

  const loadPosts = async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await axios.get('http://127.0.0.1:5000/api/posts', {
        headers: { Authorization: `Bearer ${token}` }
      })
      setPosts(response.data.posts || [])
    } catch (err) {
      console.error('Error loading posts:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleVote = async (postId, voteType) => {
    try {
      const token = localStorage.getItem('token')
      await axios.post(`http://127.0.0.1:5000/api/posts/${postId}/vote`, 
        { vote_type: voteType },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      
      // Update local state
      setUserVotes(prev => ({
        ...prev,
        [postId]: voteType
      }))
      
      // Reload posts to get updated vote counts
      loadPosts()
    } catch (err) {
      console.error('Error voting:', err)
      if (err.response?.data?.error) {
        alert(err.response.data.error)
      }
    }
  }

  const handleUserClick = (username) => {
    navigate(`/profile/${username}`)
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    navigate('/')
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

  if (loading) {
    return (
      <div className="home-feed">
        <div className="loading">Loading flood reports...</div>
      </div>
    )
  }

  return (
    <div className="home-feed">
      {/* Minimal Header for Citizens */}
      <div className="citizen-header">
        <h1 className="header-title">Flood Reports</h1>
        <div className="header-actions">
          <button onClick={() => navigate('/report')} className="header-btn report-btn">
            Submit Report
          </button>
          <button onClick={() => navigate(`/profile/${user.username}`)} className="header-btn profile-btn">
            My Profile
          </button>
          <button onClick={handleLogout} className="header-btn logout-btn">
            Logout
          </button>
        </div>
      </div>

      <div className="posts-container">
        {posts.map(post => (
          <div key={post.id} className="post-card">
            <div className="post-votes">
              <button 
                className={`vote-btn upvote ${userVotes[post.id] === 'up' ? 'active' : ''}`}
                onClick={() => handleVote(post.id, 'up')}
                disabled={post.user_id === user.id}
              >
                ▲
              </button>
              <span className="vote-count">{post.upvotes - post.downvotes}</span>
              <button 
                className={`vote-btn downvote ${userVotes[post.id] === 'down' ? 'active' : ''}`}
                onClick={() => handleVote(post.id, 'down')}
                disabled={post.user_id === user.id}
              >
                ▼
              </button>
            </div>

            <div className="post-content">
              <div className="post-header">
                <span 
                  className="username"
                  style={{ color: post.authenticity_score < 0 ? '#F44336' : '#FFFCEF' }}
                  onClick={() => handleUserClick(post.username)}
                >
                  u/{post.username}
                </span>
                <span 
                  className="authenticity-score"
                  style={{ color: getScoreColor(post.authenticity_score) }}
                >
                  {post.authenticity_score > 0 ? '+' : ''}{post.authenticity_score}
                </span>
                <span className="post-time">{formatTime(post.created_at)}</span>
              </div>

              <h3 className="post-title">{post.title}</h3>
              <p className="post-description">{post.description}</p>
              
              {post.location_name && (
                <div className="post-location">
                  📍 {post.location_name}
                </div>
              )}

              <div className="post-stats">
                <span className="status">{post.status}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {posts.length === 0 && (
        <div className="empty-feed">
          <p>No flood reports yet. Be the first to report!</p>
        </div>
      )}
    </div>
  )
}

export default HomeFeed
