import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import '../styles/Home.css'

function Home() {
  const navigate = useNavigate()

  console.log('Home component rendering...')

  return (
    <div className="home">
      {/* Hero Section */}
      <section id="hero" className="hero">
        <div className="hero-content">
          <h1 className="hero-title">
            Real-Time Flood Monitoring
          </h1>
          <span className="hero-subtitle">Powered by AI</span>
          <p className="hero-description">
            BlueSignal aggregates and validates citizen reports from social media 
            to provide authorities with real-time, location-based flood intelligence.
          </p>
          <div className="hero-actions">
            <button onClick={() => navigate('/auth')} className="button button-primary">
              Get Started
            </button>
            <button onClick={() => document.getElementById('about').scrollIntoView()} className="button button-secondary">
              Learn More
            </button>
          </div>
        </div>
        <div className="hero-image">
          <div className="hero-visual">
            <div className="pulse-circle"></div>
            <div className="data-point"></div>
            <div className="data-point"></div>
            <div className="data-point"></div>
          </div>
        </div>
      </section>

      {/* About Us Section */}
      <section id="about" className="about-section">
        <div className="section-content">
          <h2 className="section-title">About BlueSignal</h2>
          <p className="about-description">
            BlueSignal is an AI-driven flood response platform that empowers communities 
            to respond faster and more effectively to flood emergencies. By combining citizen 
            reports with advanced machine learning, we provide authorities with verified, 
            real-time intelligence for rapid emergency response.
          </p>
          <div className="about-features">
            <div className="about-feature">
              <div className="feature-icon-placeholder">[Icon]</div>
              <h3>Real-Time Monitoring</h3>
              <p>Continuous monitoring of flood conditions across multiple data sources</p>
            </div>
            <div className="about-feature">
              <div className="feature-icon-placeholder">[Icon]</div>
              <h3>AI Verification</h3>
              <p>Advanced algorithms validate reports and filter misinformation</p>
            </div>
            <div className="about-feature">
              <div className="feature-icon-placeholder">[Icon]</div>
              <h3>Community Driven</h3>
              <p>Citizen participation creates comprehensive flood intelligence</p>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="how-it-works-section">
        <div className="section-content">
          <h2 className="section-title">How It Works</h2>
          <div className="steps-grid">
            <div className="step-card">
              <div className="step-number">1</div>
              <div className="step-icon-placeholder">[Icon]</div>
              <h3>Citizens Report</h3>
              <p>Community members submit real-time flood reports with photos, videos, and location data</p>
            </div>
            <div className="step-card">
              <div className="step-number">2</div>
              <div className="step-icon-placeholder">[Icon]</div>
              <h3>AI Verification</h3>
              <p>Advanced AI algorithms cross-reference reports with social media and weather data</p>
            </div>
            <div className="step-card">
              <div className="step-number">3</div>
              <div className="step-icon-placeholder">[Icon]</div>
              <h3>Authority Response</h3>
              <p>Government agencies receive structured intelligence for emergency coordination</p>
            </div>
          </div>
        </div>
      </section>

      {/* Call to Action */}
      <section className="cta">
        <h2 className="cta-title">Join the Movement</h2>
        <p className="cta-description">
          Be part of a community-driven platform that's revolutionizing flood response 
          through AI and citizen participation.
        </p>
        <button onClick={() => navigate('/auth')} className="button button-primary">
          Get Started Today
        </button>
      </section>
    </div>
  )
}

export default Home

