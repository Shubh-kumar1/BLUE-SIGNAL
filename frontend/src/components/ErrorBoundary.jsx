import React from 'react'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('Frontend Error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ 
          padding: '40px', 
          backgroundColor: '#659BB9', 
          color: '#FFFCEF', 
          fontFamily: 'Roboto Mono, monospace',
          minHeight: '100vh'
        }}>
          <h1>Frontend Error</h1>
          <p>Something went wrong:</p>
          <pre style={{ backgroundColor: 'rgba(255,255,255,0.1)', padding: '20px', borderRadius: '8px' }}>
            {this.state.error?.toString()}
          </pre>
          <button 
            onClick={() => window.location.reload()} 
            style={{
              backgroundColor: '#FFFCEF',
              color: '#659BB9',
              border: 'none',
              padding: '12px 24px',
              borderRadius: '8px',
              cursor: 'pointer',
              marginTop: '20px'
            }}
          >
            Reload Page
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
