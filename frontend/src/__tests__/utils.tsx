import { render, RenderOptions } from '@testing-library/preact'
import { ComponentChildren, ComponentChild } from 'preact'
import { Router } from 'wouter-preact'
import { WebSocketProvider } from '../lib/websocket'

/**
 * AllProviders wrapper for testing components that need:
 * - WebSocket context
 * - Router context
 */
export function AllProviders({ children }: { children: ComponentChildren }) {
  return (
    <WebSocketProvider>
      <Router>
        {children}
      </Router>
    </WebSocketProvider>
  )
}

/**
 * Render helper that wraps the component with all necessary providers
 */
export function renderWithProviders(
  ui: ComponentChild,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  return render(ui, { wrapper: AllProviders, ...options })
}

/**
 * Wait for all pending promises to resolve
 */
export function flushPromises(): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, 0))
}

/**
 * Wait for a condition to be true with timeout
 */
export async function waitFor(
  condition: () => boolean,
  timeoutMs = 1000
): Promise<void> {
  const startTime = Date.now()
  while (!condition() && Date.now() - startTime < timeoutMs) {
    await flushPromises()
  }
  if (!condition()) {
    throw new Error('waitFor timeout')
  }
}
