import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/preact'
import userEvent from '@testing-library/user-event'
import { ConfigureAmsSlotModal } from '../../components/ConfigureAmsSlotModal'
import { mockCalibrations, mockSlicerPresets, mockSettingDetail } from '../mocks/data'
import { server } from '../setup'
import { http, HttpResponse } from 'msw'

// Mock slot info for testing
const defaultSlotInfo = {
  amsId: 0,
  trayId: 0,
  trayCount: 4,
  trayType: 'PLA',
  trayColor: 'FF0000FF',
  traySubBrands: 'Bambu PLA Basic',
  trayInfoIdx: 'GFSL05',
}

// Default props for the modal
const defaultProps = {
  isOpen: true,
  onClose: vi.fn(),
  printerSerial: '00M09A123456789',
  slotInfo: defaultSlotInfo,
  calibrations: mockCalibrations,
  currentKValue: 0.025,
  onSuccess: vi.fn(),
}

describe('ConfigureAmsSlotModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders modal when open', async () => {
      render(<ConfigureAmsSlotModal {...defaultProps} />)

      expect(screen.getByText('Configure AMS Slot')).toBeInTheDocument()
    })

    it('does not render when closed', () => {
      render(<ConfigureAmsSlotModal {...defaultProps} isOpen={false} />)

      expect(screen.queryByText('Configure AMS Slot')).not.toBeInTheDocument()
    })

    it('displays slot info correctly', async () => {
      render(<ConfigureAmsSlotModal {...defaultProps} />)

      // Should show AMS label and slot number
      expect(screen.getByText(/AMS-A Slot 1/)).toBeInTheDocument()
      // Should show current tray type
      expect(screen.getByText('(PLA)')).toBeInTheDocument()
    })

    it('displays correct AMS label for HT AMS', async () => {
      const htSlotInfo = {
        ...defaultSlotInfo,
        amsId: 128,
        trayCount: 1,
      }
      render(<ConfigureAmsSlotModal {...defaultProps} slotInfo={htSlotInfo} />)

      expect(screen.getByText(/HT-A Slot 1/)).toBeInTheDocument()
    })

    it('displays external slot label', async () => {
      const externalSlotInfo = {
        ...defaultSlotInfo,
        amsId: 255,
        trayCount: 1,
      }
      render(<ConfigureAmsSlotModal {...defaultProps} slotInfo={externalSlotInfo} />)

      expect(screen.getByText(/External Slot 1/)).toBeInTheDocument()
    })
  })

  describe('Preset Loading', () => {
    it('fetches filament presets on open', async () => {
      render(<ConfigureAmsSlotModal {...defaultProps} />)

      // Wait for presets to load
      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })
    })

    it('shows loading spinner while fetching presets', async () => {
      // Delay the response to see the loading state
      server.use(
        http.get('/api/cloud/settings', async () => {
          await new Promise(resolve => setTimeout(resolve, 100))
          return HttpResponse.json({
            filament: mockSlicerPresets,
            printer: [],
            process: [],
          })
        })
      )

      render(<ConfigureAmsSlotModal {...defaultProps} />)

      // Should show loader initially
      expect(document.querySelector('.animate-spin')).toBeInTheDocument()

      // Wait for presets to load
      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })
    })

    it('shows message when no presets available', async () => {
      server.use(
        http.get('/api/cloud/settings', () => {
          return HttpResponse.json({
            filament: [],
            printer: [],
            process: [],
          })
        })
      )

      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText(/No cloud presets/)).toBeInTheDocument()
      })
    })
  })

  describe('Search and Filtering', () => {
    it('filters presets by search query', async () => {
      render(<ConfigureAmsSlotModal {...defaultProps} />)

      // Wait for presets to load
      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      // Type in search
      const searchInput = screen.getByPlaceholderText('Search presets...')
      await userEvent.type(searchInput, 'PETG')

      // Should show only PETG preset
      expect(screen.getByText('Generic PETG @BBL X1C')).toBeInTheDocument()
      expect(screen.queryByText('Bambu PLA Basic @BBL X1C')).not.toBeInTheDocument()
    })

    it('shows no matching presets message', async () => {
      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      const searchInput = screen.getByPlaceholderText('Search presets...')
      await userEvent.type(searchInput, 'nonexistent')

      expect(screen.getByText('No matching presets found.')).toBeInTheDocument()
    })

    it('shows custom badge for user presets', async () => {
      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('# My Custom PLA @BBL X1C')).toBeInTheDocument()
      })

      // Should have Custom badge next to user preset
      expect(screen.getByText('Custom')).toBeInTheDocument()
    })
  })

  describe('Preset Selection', () => {
    it('selecting preset updates K-profile options', async () => {
      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      // Select a preset
      fireEvent.click(screen.getByText('Bambu PLA Basic @BBL X1C'))

      // Should show matching K profiles
      await waitFor(() => {
        expect(screen.getByText(/Filtering for: Bambu PLA Basic/)).toBeInTheDocument()
      })
    })

    it('shows prompt to select filament profile when no preset selected', async () => {
      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      // Should show prompt before selecting preset
      expect(screen.getByText('Select a filament profile first')).toBeInTheDocument()
    })
  })

  describe('Color Selection', () => {
    it('displays current slot color in preview', async () => {
      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      // Color preview should use the current tray color
      const colorPreview = document.querySelector('[style*="background-color"]')
      expect(colorPreview).toBeInTheDocument()
    })

    it('updates color when quick color is clicked', async () => {
      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      // Click on Black quick color
      const blackButton = screen.getByTitle('Black')
      fireEvent.click(blackButton)

      // The button should now be highlighted (has scale-110 class)
      expect(blackButton).toHaveClass('scale-110')
    })

    it('shows extended colors when + button is clicked', async () => {
      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      // Click the + button to show more colors
      const expandButton = screen.getByTitle('Show more colors')
      fireEvent.click(expandButton)

      // Should now show extended colors
      expect(screen.getByTitle('Cyan')).toBeInTheDocument()
      expect(screen.getByTitle('Magenta')).toBeInTheDocument()
    })

    it('accepts hex color input', async () => {
      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      // Type a hex color
      const colorInput = screen.getByPlaceholderText('Color name or hex (e.g., brown, FF8800)')
      await userEvent.type(colorInput, 'FF8800')

      // Should show clear button
      expect(screen.getByTitle('Clear custom color')).toBeInTheDocument()
    })
  })

  describe('Actions', () => {
    it('configure button is disabled without preset selected', async () => {
      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      const configureButton = screen.getByRole('button', { name: /Configure Slot/ })
      expect(configureButton).toBeDisabled()
    })

    it('configure button is enabled after selecting preset', async () => {
      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      // Select a preset
      fireEvent.click(screen.getByText('Bambu PLA Basic @BBL X1C'))

      const configureButton = screen.getByRole('button', { name: /Configure Slot/ })
      expect(configureButton).not.toBeDisabled()
    })

    it('re-read button triggers RFID read request', async () => {
      let rereadCalled = false
      server.use(
        http.post('/api/printers/:serial/ams/:amsId/tray/:trayId/reset', () => {
          rereadCalled = true
          return HttpResponse.json({ status: 'ok' })
        })
      )

      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      const rereadButton = screen.getByRole('button', { name: /Re-read/ })
      fireEvent.click(rereadButton)

      await waitFor(() => {
        expect(rereadCalled).toBe(true)
      })
    })

    it('reset button clears slot', async () => {
      let clearCalled = false
      server.use(
        http.post('/api/printers/:serial/ams/:amsId/tray/:trayId/filament', async ({ request }) => {
          const body = await request.json() as Record<string, unknown>
          if (body.tray_info_idx === '' && body.tray_type === '') {
            clearCalled = true
          }
          return HttpResponse.json({ status: 'ok' })
        })
      )

      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      const resetButton = screen.getByRole('button', { name: /Reset/ })
      fireEvent.click(resetButton)

      await waitFor(() => {
        expect(clearCalled).toBe(true)
      })
    })

    it('cancel button closes modal', async () => {
      const onClose = vi.fn()
      render(<ConfigureAmsSlotModal {...defaultProps} onClose={onClose} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      const cancelButton = screen.getByRole('button', { name: 'Cancel' })
      fireEvent.click(cancelButton)

      expect(onClose).toHaveBeenCalled()
    })

    it('escape key closes modal', async () => {
      const onClose = vi.fn()
      render(<ConfigureAmsSlotModal {...defaultProps} onClose={onClose} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      fireEvent.keyDown(document, { key: 'Escape' })

      expect(onClose).toHaveBeenCalled()
    })

    it('backdrop click closes modal', async () => {
      const onClose = vi.fn()
      render(<ConfigureAmsSlotModal {...defaultProps} onClose={onClose} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      // Click on backdrop
      const backdrop = document.querySelector('.bg-black\\/60')
      if (backdrop) {
        fireEvent.click(backdrop)
      }

      expect(onClose).toHaveBeenCalled()
    })
  })

  describe('Configuration Flow', () => {
    it('sends correct payload when configuring slot', async () => {
      let filamentPayload: Record<string, unknown> | null = null
      let calibrationPayload: Record<string, unknown> | null = null

      server.use(
        http.post('/api/printers/:serial/ams/:amsId/tray/:trayId/filament', async ({ request }) => {
          filamentPayload = await request.json() as Record<string, unknown>
          return HttpResponse.json({ status: 'ok' })
        }),
        http.post('/api/printers/:serial/ams/:amsId/tray/:trayId/calibration', async ({ request }) => {
          calibrationPayload = await request.json() as Record<string, unknown>
          return HttpResponse.json({ status: 'ok' })
        })
      )

      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      // Select preset
      fireEvent.click(screen.getByText('Bambu PLA Basic @BBL X1C'))

      // Wait for selection to register
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Configure Slot/ })).not.toBeDisabled()
      })

      // Configure
      fireEvent.click(screen.getByRole('button', { name: /Configure Slot/ }))

      await waitFor(() => {
        expect(filamentPayload).not.toBeNull()
      })

      // Verify filament payload
      expect(filamentPayload).toMatchObject({
        tray_info_idx: expect.any(String),
        tray_type: 'PLA',
        setting_id: 'GFSL05_07',
      })

      // Verify calibration payload
      expect(calibrationPayload).toMatchObject({
        cali_idx: expect.any(Number),
      })
    })

    it('shows success overlay after configuration', async () => {
      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      // Select preset
      fireEvent.click(screen.getByText('Bambu PLA Basic @BBL X1C'))

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Configure Slot/ })).not.toBeDisabled()
      })

      // Configure
      fireEvent.click(screen.getByRole('button', { name: /Configure Slot/ }))

      // Should show success overlay
      await waitFor(() => {
        expect(screen.getByText('Slot Configured!')).toBeInTheDocument()
      })
    })

    it('calls onSuccess callback after configuration', async () => {
      const onSuccess = vi.fn()
      render(<ConfigureAmsSlotModal {...defaultProps} onSuccess={onSuccess} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      // Select preset
      fireEvent.click(screen.getByText('Bambu PLA Basic @BBL X1C'))

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Configure Slot/ })).not.toBeDisabled()
      })

      // Configure
      fireEvent.click(screen.getByRole('button', { name: /Configure Slot/ }))

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalled()
      })
    })

    it('fetches filament_id for user presets from cloud', async () => {
      let settingDetailCalled = false
      server.use(
        http.get('/api/cloud/settings/:settingId', ({ params }) => {
          if (params.settingId === 'custom-pla-001') {
            settingDetailCalled = true
            return HttpResponse.json(mockSettingDetail)
          }
          return HttpResponse.json({ setting_id: params.settingId })
        })
      )

      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('# My Custom PLA @BBL X1C')).toBeInTheDocument()
      })

      // Select user preset
      fireEvent.click(screen.getByText('# My Custom PLA @BBL X1C'))

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Configure Slot/ })).not.toBeDisabled()
      })

      // Configure
      fireEvent.click(screen.getByRole('button', { name: /Configure Slot/ }))

      await waitFor(() => {
        expect(settingDetailCalled).toBe(true)
      })
    })
  })

  describe('Error Handling', () => {
    it('displays error message on configuration failure', async () => {
      server.use(
        http.post('/api/printers/:serial/ams/:amsId/tray/:trayId/filament', () => {
          return new HttpResponse('Printer not connected', { status: 503 })
        })
      )

      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      // Select preset
      fireEvent.click(screen.getByText('Bambu PLA Basic @BBL X1C'))

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Configure Slot/ })).not.toBeDisabled()
      })

      // Configure
      fireEvent.click(screen.getByRole('button', { name: /Configure Slot/ }))

      // Should show error
      await waitFor(() => {
        expect(screen.getByText(/Printer not connected/)).toBeInTheDocument()
      })
    })

    it('displays error message on re-read failure', async () => {
      server.use(
        http.post('/api/printers/:serial/ams/:amsId/tray/:trayId/reset', () => {
          return new HttpResponse('RFID read failed', { status: 500 })
        })
      )

      render(<ConfigureAmsSlotModal {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByText('Bambu PLA Basic @BBL X1C')).toBeInTheDocument()
      })

      const rereadButton = screen.getByRole('button', { name: /Re-read/ })
      fireEvent.click(rereadButton)

      await waitFor(() => {
        expect(screen.getByText(/RFID read failed/)).toBeInTheDocument()
      })
    })
  })
})
