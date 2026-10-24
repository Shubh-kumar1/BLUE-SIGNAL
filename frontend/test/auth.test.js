import assert from 'node:assert/strict'
import test from 'node:test'
import {
  AUTH_REQUEST_TIMEOUT_MS,
  getAuthErrorMessage,
  parseAuthResponse,
  runAuthSubmission
} from '../src/utils/auth.js'

test('auth requests use a bounded 15-second timeout', () => {
  assert.equal(AUTH_REQUEST_TIMEOUT_MS, 15000)
})

test('maps invalid credentials without exposing raw response bodies', () => {
  assert.equal(
    getAuthErrorMessage({ response: { status: 401, data: '<html>internal error</html>' } }),
    'Invalid username or password. Please check your details and try again.'
  )
})

test('maps duplicate signup and validation responses', () => {
  assert.equal(
    getAuthErrorMessage({ response: { status: 409, data: { error: 'Email already exists' } } }),
    'Email already exists'
  )
  assert.equal(
    getAuthErrorMessage({ response: { status: 400, data: {} } }),
    'Please check the information you entered and try again.'
  )
})

test('validates auth response shape and rejects a wrong portal role', () => {
  const authResponse = {
    data: {
      token: 'test-token',
      user: { role: 'citizen' }
    }
  }
  assert.equal(parseAuthResponse(authResponse, 'citizen'), authResponse.data)
  assert.throws(
    () => parseAuthResponse({ data: '<html>not JSON</html>' }, 'citizen'),
    { code: 'INVALID_AUTH_RESPONSE' }
  )
  assert.throws(
    () => parseAuthResponse({ data: { token: 'test-token', user: { role: 'authority' } } }, 'citizen'),
    { code: 'AUTH_ROLE_MISMATCH' }
  )
})

test('explains timeouts, network failures, and post-registration sign-in failures', () => {
  assert.match(getAuthErrorMessage({ code: 'ECONNABORTED' }), /timed out/)
  assert.match(getAuthErrorMessage({ code: 'ERR_NETWORK' }), /Unable to reach/)
  assert.match(getAuthErrorMessage({ code: 'ERR_NETWORK' }, true), /account was created/)
})

test('clears loading and releases the lock after success and failure', async () => {
  const lock = { current: false }
  const loading = []

  assert.equal(await runAuthSubmission(lock, (value) => loading.push(value), async () => {}), true)
  assert.deepEqual(loading, [true, false])
  assert.equal(lock.current, false)

  await assert.rejects(
    runAuthSubmission(lock, (value) => loading.push(value), async () => {
      throw new Error('request failed')
    }),
    /request failed/
  )
  assert.deepEqual(loading, [true, false, true, false])
  assert.equal(lock.current, false)

  await assert.rejects(
    runAuthSubmission(lock, (value) => loading.push(value), async () => {
      const timeout = new Error('timeout')
      timeout.code = 'ECONNABORTED'
      throw timeout
    }),
    { code: 'ECONNABORTED' }
  )
  assert.deepEqual(loading, [true, false, true, false, true, false])
  assert.equal(lock.current, false)
})

test('ignores duplicate submissions until the active request finishes', async () => {
  const lock = { current: false }
  const loading = []
  let releaseFirst
  let firstActionCalls = 0
  let duplicateActionCalls = 0
  const active = runAuthSubmission(lock, (value) => loading.push(value), () => {
    firstActionCalls += 1
    return new Promise((resolve) => {
      releaseFirst = resolve
    })
  })

  const duplicate = await runAuthSubmission(lock, (value) => loading.push(value), async () => {
    duplicateActionCalls += 1
  })
  assert.equal(duplicate, false)
  assert.equal(firstActionCalls, 1)
  assert.equal(duplicateActionCalls, 0)
  assert.deepEqual(loading, [true])

  releaseFirst()
  assert.equal(await active, true)
  assert.deepEqual(loading, [true, false])
  assert.equal(lock.current, false)
})
