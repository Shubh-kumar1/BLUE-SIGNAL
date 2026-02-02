import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import ClickSpark from './components/ClickSpark'
import Home from './pages/Home'
import AuthPage from './pages/AuthPage'
import CitizenFeed from './pages/CitizenFeed'
import HomeFeed from './pages/HomeFeed'
import UserProfile from './pages/UserProfile'
import AuthorityDashboard from './pages/AuthorityDashboard'
import ProtectedRoute from './components/ProtectedRoute'

function App() {
  return (
    <Router>
      <ClickSpark
        sparkColor='#FFFCEF'
        sparkSize={8}
        sparkRadius={20}
        sparkCount={6}
        duration={500}
      >
        <div className="app">
          <Routes>
            {/* Public Routes with Navbar */}
            <Route path="/" element={<><Navbar /><Home /></>} />
            
            {/* Auth Route (Split Screen Login/Signup) */}
            <Route path="/auth" element={<AuthPage />} />
            
            {/* Protected Routes - Citizen (No Navbar) */}
            <Route 
              path="/report" 
              element={
                <ProtectedRoute requiredRole="citizen">
                  <CitizenFeed />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/feed" 
              element={
                <ProtectedRoute requiredRole="citizen">
                  <HomeFeed />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/profile/:username" 
              element={
                <ProtectedRoute requiredRole="citizen">
                  <UserProfile />
                </ProtectedRoute>
              } 
            />
            
            {/* Protected Routes - Authority */}
            <Route 
              path="/dashboard" 
              element={
                <ProtectedRoute requiredRole="authority">
                  <AuthorityDashboard />
                </ProtectedRoute>
              } 
            />
          </Routes>
        </div>
      </ClickSpark>
    </Router>
  )
}

export default App

