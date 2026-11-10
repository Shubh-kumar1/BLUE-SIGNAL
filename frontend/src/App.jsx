import React, { lazy, Suspense } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import ClickSpark from './components/ClickSpark'
import ProtectedRoute from './components/ProtectedRoute'

const Home = lazy(() => import('./pages/Home'))
const AuthPage = lazy(() => import('./pages/AuthPage'))
const CitizenFeed = lazy(() => import('./pages/CitizenFeed'))
const HomeFeed = lazy(() => import('./pages/HomeFeed'))
const UserProfile = lazy(() => import('./pages/UserProfile'))
const AuthorityDashboard = lazy(() => import('./pages/AuthorityDashboard'))

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
          <Suspense fallback={<div role="status">Loading page...</div>}>
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
          </Suspense>
        </div>
      </ClickSpark>
    </Router>
  )
}

export default App
