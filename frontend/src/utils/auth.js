export const AUTH_REQUEST_TIMEOUT_MS = 15000

export const getAuthErrorMessage = (error, accountCreated = false) => {
  if (error?.code === 'AUTH_ROLE_MISMATCH') {
    return error.message
  }

  if (error?.code === 'INVALID_AUTH_RESPONSE') {
    return accountCreated
      ? 'Your account was created, but the server returned an invalid sign-in response. Please log in with your new account.'
      : 'The server returned an invalid authentication response. Please try again.'
  }

  if (error?.code === 'SESSION_STORAGE_FAILED') {
    return accountCreated
      ? 'Your account was created, but your browser could not save the login session. Check browser storage and log in again.'
      : 'Your browser could not save the login session. Check your browser storage settings and try again.'
  }

  if (error?.code === 'ECONNABORTED' || error?.code === 'ETIMEDOUT') {
    return accountCreated
      ? 'Your account was created, but automatic sign-in timed out. Please log in with your new account.'
      : 'The request timed out. The server may be starting up; please try again.'
  }

  const status = error?.response?.status
  const responseBody = error?.response?.data
  const serverMessage = responseBody && typeof responseBody === 'object'
    ? responseBody.error || responseBody.message
    : null

  if (status === 409) {
    return accountCreated
      ? 'Your account was created, but automatic sign-in failed. Please log in with your new account.'
      : serverMessage || 'An account already exists with that username or email.'
  }

  if (status === 401) {
    return accountCreated
      ? 'Your account was created, but automatic sign-in failed. Please log in with your new account.'
      : 'Invalid username or password. Please check your details and try again.'
  }

  if (status === 400) {
    return serverMessage || 'Please check the information you entered and try again.'
  }

  if (status >= 500) {
    return accountCreated
      ? 'Your account was created, but automatic sign-in failed because of a server error. Please log in with your new account.'
      : 'The server could not complete your request. Please try again shortly.'
  }

  if (status) {
    return serverMessage || 'The request could not be completed. Please try again.'
  }

  return accountCreated
    ? 'Your account was created, but automatic sign-in failed. Please log in with your new account.'
    : 'Unable to reach the server. Check your connection and try again.'
}

export const parseAuthResponse = (response, expectedRole) => {
  const data = response?.data
  if (
    !data ||
    typeof data !== 'object' ||
    Array.isArray(data) ||
    typeof data.token !== 'string' ||
    !data.token ||
    !data.user ||
    typeof data.user !== 'object' ||
    Array.isArray(data.user)
  ) {
    const error = new Error('Invalid authentication response')
    error.code = 'INVALID_AUTH_RESPONSE'
    throw error
  }

  if (data.user.role !== expectedRole) {
    const portal = expectedRole === 'citizen' ? 'Authority' : 'Citizen'
    const error = new Error(`This account belongs to the ${portal} Portal. Please log in there.`)
    error.code = 'AUTH_ROLE_MISMATCH'
    throw error
  }

  return data
}

export const runAuthSubmission = async (lock, setLoading, action) => {
  if (lock.current) return false

  lock.current = true
  try {
    setLoading(true)
    await action()
    return true
  } finally {
    lock.current = false
    setLoading(false)
  }
}
