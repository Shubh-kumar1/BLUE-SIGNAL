import React from 'react'
import { Navigate } from 'react-router-dom'

function ProtectedRoute({ children, requiredRole }) {
  const token = localStorage.getItem('token')
  const user = JSON.parse(localStorage.getItem('user') || '{}')

  // Not logged in
  if (!token) {
    return <Navigate to="/auth" replace />
  }

  // Logged in but wrong role
  if (requiredRole && user.role !== requiredRole) {
    return <Navigate to="/" replace />
  }

  return children
}

export default ProtectedRoute

