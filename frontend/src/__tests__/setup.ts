import '@testing-library/jest-dom'
import { cleanup } from '@testing-library/preact'
import { afterEach, beforeAll, afterAll, vi } from 'vitest'
import { setupServer } from 'msw/node'
import { handlers } from './mocks/handlers'

// Set up MSW server for mocking API calls
export const server = setupServer(...handlers)

// Silence console.log for WebSocket connection messages during tests
const originalConsoleLog = console.log
const originalConsoleError = console.error

console.log = (...args: unknown[]) => {
  const message = args[0]
  if (typeof message === 'string' && (
    message.includes('WebSocket') ||
    message.includes('Connecting to') ||
    message.includes('reconnecting')
  )) {
    return // Silence WebSocket logs
  }
  originalConsoleLog(...args)
}

// Silence expected error messages from error handling tests
console.error = (...args: unknown[]) => {
  const message = args[0]
  if (typeof message === 'string' && (
    message.includes('Failed to configure slot') ||
    message.includes('Failed to re-read slot') ||
    message.includes('Failed to load spools')
  )) {
    return // Silence expected error handling test messages
  }
  originalConsoleError(...args)
}

// Start server before all tests
beforeAll(() => {
  server.listen({ onUnhandledRequest: 'bypass' })
})

// Reset handlers after each test
afterEach(() => {
  server.resetHandlers()
  cleanup()
})

// Clean up after all tests
afterAll(() => {
  server.close()
})

// Mock window.matchMedia for tests
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
}
Object.defineProperty(window, 'localStorage', { value: localStorageMock })

// Mock WebSocket with full interface to avoid MSW interceptor errors
class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  readyState = MockWebSocket.OPEN
  url: string
  protocol = ''
  extensions = ''
  bufferedAmount = 0
  binaryType: BinaryType = 'blob'

  onopen: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null

  private _listeners: Map<string, Set<EventListener>> = new Map()

  constructor(url: string, _protocols?: string | string[]) {
    this.url = url
    setTimeout(() => {
      if (this.onopen) this.onopen(new Event('open'))
    }, 0)
  }

  addEventListener(type: string, listener: EventListener) {
    if (!this._listeners.has(type)) {
      this._listeners.set(type, new Set())
    }
    this._listeners.get(type)!.add(listener)
  }

  removeEventListener(type: string, listener: EventListener) {
    this._listeners.get(type)?.delete(listener)
  }

  dispatchEvent(event: Event): boolean {
    const listeners = this._listeners.get(event.type)
    if (listeners) {
      listeners.forEach(listener => listener(event))
    }
    return true
  }

  send(_data: string | ArrayBuffer | Blob | ArrayBufferView) {}

  close(_code?: number, _reason?: string) {
    this.readyState = MockWebSocket.CLOSED
    if (this.onclose) this.onclose(new CloseEvent('close'))
  }
}

vi.stubGlobal('WebSocket', MockWebSocket)

// Mock ResizeObserver
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal('ResizeObserver', MockResizeObserver)

// Mock IntersectionObserver
class MockIntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)

// Mock window.scrollTo
Object.defineProperty(window, 'scrollTo', {
  value: vi.fn(),
  writable: true,
})
