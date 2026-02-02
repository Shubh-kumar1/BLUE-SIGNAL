import React, { useState, useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import '../styles/Navbar.css'

function Navbar() {
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [user, setUser] = useState(null)
  const location = useLocation()
  const navigate = useNavigate()
  
  useEffect(() => {
    const userData = localStorage.getItem('user')
    if (userData) {
      setUser(JSON.parse(userData))
    }
  }, [location])
  
  const handleNavClick = (sectionId) => {
    setIsMenuOpen(false)
    if (sectionId.startsWith('#')) {
      const element = document.getElementById(sectionId.substring(1))
      if (element) {
        element.scrollIntoView({ behavior: 'smooth' })
      }
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setUser(null)
    navigate('/')
  }

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <Link to="/" className="navbar-logo">
          <img 
            src="/bluesignal-bg.png" 
            alt="BlueSignal Logo" 
            className="navbar-logo-img"
          />
          <span className="navbar-logo-text">BlueSignal</span>
        </Link>

        <button 
          className="navbar-toggle"
          onClick={() => setIsMenuOpen(!isMenuOpen)}
          aria-label="Toggle menu"
        >
          <span className="navbar-toggle-icon"></span>
          <span className="navbar-toggle-icon"></span>
          <span className="navbar-toggle-icon"></span>
        </button>

        <ul className={`navbar-menu ${isMenuOpen ? 'active' : ''}`}>
          <li className="navbar-item">
            <button 
              onClick={() => handleNavClick('#hero')}
              className="navbar-link"
            >
              Home
            </button>
          </li>
          <li className="navbar-item">
            <button 
              onClick={() => handleNavClick('#about')}
              className="navbar-link"
            >
              About Us
            </button>
          </li>
          <li className="navbar-item">
            <button 
              onClick={() => handleNavClick('#how-it-works')}
              className="navbar-link"
            >
              How It Works
            </button>
          </li>
          
          {user ? (
            <>
              <li className="navbar-item">
                <Link 
                  to="/feed" 
                  className="navbar-link"
                  onClick={() => setIsMenuOpen(false)}
                >
                  Feed
                </Link>
              </li>
              <li className="navbar-item">
                <Link 
                  to="/report" 
                  className="navbar-link"
                  onClick={() => setIsMenuOpen(false)}
                >
                  Report
                </Link>
              </li>
              <li className="navbar-item">
                <span className="navbar-welcome">
                  Welcome, <strong>{user.role === 'citizen' ? 'Citizen' : 'Authority'} {user.username}</strong>
                </span>
              </li>
              <li className="navbar-item">
                <button 
                  onClick={handleLogout}
                  className="navbar-link navbar-link-logout"
                >
                  Logout
                </button>
              </li>
            </>
          ) : (
            <li className="navbar-item">
              <Link 
                to="/auth" 
                className="navbar-link navbar-link-login"
                onClick={() => setIsMenuOpen(false)}
              >
                Login/Signup
              </Link>
            </li>
          )}
        </ul>
      </div>
    </nav>
  )
}

export default Navbar

