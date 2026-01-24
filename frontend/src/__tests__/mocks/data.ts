import { CalibrationProfile, SlicerPreset, Spool, Printer } from '../../lib/api'
import { AmsUnit, AmsTray, PrinterState } from '../../lib/websocket'

/**
 * Mock spool data for testing
 */
export const mockSpools: Spool[] = [
  {
    id: 'spool-1',
    spool_number: 1,
    tag_id: null,
    material: 'PLA',
    subtype: 'Basic',
    color_name: 'Black',
    rgba: '#000000FF',
    brand: 'Bambu Lab',
    label_weight: 1000,
    core_weight: 250,
    weight_new: 1000,
    weight_current: 850,
    slicer_filament: 'GFSL05',
    slicer_filament_name: 'Bambu PLA Basic',
    location: null,
    note: null,
    added_time: null,
    encode_time: null,
    added_full: false,
    consumed_since_add: 150,
    consumed_since_weight: 50,
    weight_used: 0,
    data_origin: null,
    tag_type: null,
    ext_has_k: false,
    archived_at: null,
    created_at: 1702000000,
    updated_at: 1702000000,
    last_used_time: null,
  },
  {
    id: 'spool-2',
    spool_number: 2,
    tag_id: 'ABC123==',
    material: 'PETG',
    subtype: 'Basic',
    color_name: 'Red',
    rgba: '#FF0000FF',
    brand: 'Generic',
    label_weight: 1000,
    core_weight: 250,
    weight_new: 1000,
    weight_current: 1000,
    slicer_filament: null,
    slicer_filament_name: null,
    location: 'X1 Carbon',
    note: 'Test spool',
    added_time: null,
    encode_time: null,
    added_full: true,
    consumed_since_add: 0,
    consumed_since_weight: 0,
    weight_used: 0,
    data_origin: null,
    tag_type: null,
    ext_has_k: true,
    archived_at: null,
    created_at: 1702100000,
    updated_at: 1702100000,
    last_used_time: null,
  },
]

/**
 * Mock printer data for testing
 */
export const mockPrinters: Printer[] = [
  {
    serial: '00M09A123456789',
    name: 'X1 Carbon',
    model: 'X1C',
    ip_address: '192.168.1.100',
    access_code: '12345678',
    last_seen: 1702000000,
    config: null,
    auto_connect: true,
    connected: true,
  },
  {
    serial: '00M09A987654321',
    name: 'P1S',
    model: 'P1S',
    ip_address: '192.168.1.101',
    access_code: '87654321',
    last_seen: 1702000000,
    config: null,
    auto_connect: false,
    connected: false,
  },
]

/**
 * Mock AMS tray data
 */
export const mockAmsTrays: AmsTray[] = [
  {
    ams_id: 0,
    tray_id: 0,
    tray_type: 'PLA',
    tray_color: 'FF0000FF',
    tray_info_idx: 'GFSL05',
    k_value: 0.025,
    nozzle_temp_min: 190,
    nozzle_temp_max: 230,
    remain: 80,
  },
  {
    ams_id: 0,
    tray_id: 1,
    tray_type: 'PETG',
    tray_color: '00FF00FF',
    tray_info_idx: 'GFPG99',
    k_value: 0.035,
    nozzle_temp_min: 220,
    nozzle_temp_max: 260,
    remain: 50,
  },
  {
    ams_id: 0,
    tray_id: 2,
    tray_type: null,
    tray_color: null,
    tray_info_idx: null,
    k_value: null,
    nozzle_temp_min: null,
    nozzle_temp_max: null,
    remain: null,
  },
  {
    ams_id: 0,
    tray_id: 3,
    tray_type: 'ABS',
    tray_color: '0000FFFF',
    tray_info_idx: 'GFSA00',
    k_value: 0.040,
    nozzle_temp_min: 240,
    nozzle_temp_max: 280,
    remain: 20,
  },
]

/**
 * Mock AMS unit (regular 4-slot AMS)
 */
export const mockAmsUnit: AmsUnit = {
  id: 0,
  humidity: 35,
  temperature: 25.5,
  extruder: null,
  trays: mockAmsTrays,
}

/**
 * Mock HT AMS unit (single slot)
 */
export const mockHtAmsUnit: AmsUnit = {
  id: 128,
  humidity: 30,
  temperature: 24.0,
  extruder: 1,
  trays: [{
    ams_id: 128,
    tray_id: 0,
    tray_type: 'PLA-CF',
    tray_color: '808080FF',
    tray_info_idx: 'GFPC00',
    k_value: 0.028,
    nozzle_temp_min: 220,
    nozzle_temp_max: 260,
    remain: 65,
  }],
}

/**
 * Mock dual-nozzle AMS units (for H2D)
 */
export const mockDualNozzleAmsUnits: AmsUnit[] = [
  {
    id: 0,
    humidity: 35,
    temperature: 25.5,
    extruder: 0, // Right nozzle
    trays: mockAmsTrays,
  },
  {
    ...mockHtAmsUnit,
    extruder: 1, // Left nozzle
  },
]

/**
 * Mock printer state
 */
export const mockPrinterState: PrinterState = {
  gcode_state: 'RUNNING',
  print_progress: 45,
  layer_num: 50,
  total_layer_num: 200,
  subtask_name: 'test_print.gcode',
  mc_remaining_time: 45,
  gcode_file: '/sdcard/test_print.gcode',
  ams_units: [mockAmsUnit],
  vt_tray: null,
  tray_now: 0,
  tray_now_left: null,
  tray_now_right: null,
  active_extruder: null,
  tray_reading_bits: null,
  nozzle_count: 1,
}

/**
 * Mock printer state for dual-nozzle printer
 */
export const mockDualNozzlePrinterState: PrinterState = {
  gcode_state: 'RUNNING',
  print_progress: 60,
  layer_num: 80,
  total_layer_num: 200,
  subtask_name: 'multicolor_print.gcode',
  mc_remaining_time: 30,
  gcode_file: '/sdcard/multicolor_print.gcode',
  ams_units: mockDualNozzleAmsUnits,
  vt_tray: null,
  tray_now: null,
  tray_now_left: 16, // HT slot for left nozzle
  tray_now_right: 0, // AMS A slot 1 for right nozzle
  active_extruder: 0,
  tray_reading_bits: null,
  nozzle_count: 2,
}

/**
 * Mock calibration profiles
 */
export const mockCalibrations: CalibrationProfile[] = [
  {
    cali_idx: 42,
    filament_id: 'GFSL05',
    k_value: 0.025,
    name: 'Bambu PLA Basic',
    nozzle_diameter: '0.4',
    extruder_id: 0,
    setting_id: 'GFSL05_07',
  },
  {
    cali_idx: 43,
    filament_id: 'GFSL05',
    k_value: 0.025,
    name: 'Bambu PLA Basic',
    nozzle_diameter: '0.4',
    extruder_id: 1,
    setting_id: 'GFSL05_07',
  },
  {
    cali_idx: 44,
    filament_id: 'GFPG99',
    k_value: 0.035,
    name: 'Generic PETG',
    nozzle_diameter: '0.4',
    extruder_id: 0,
    setting_id: 'GFPG99_01',
  },
  {
    cali_idx: 45,
    filament_id: 'GFSA00',
    k_value: 0.040,
    name: 'Bambu ABS',
    nozzle_diameter: '0.4',
    extruder_id: 0,
    setting_id: 'GFSA00_05',
  },
]

/**
 * Mock slicer presets (filament profiles)
 */
export const mockSlicerPresets: SlicerPreset[] = [
  {
    setting_id: 'GFSL05_07',
    name: 'Bambu PLA Basic @BBL X1C',
    type: 'filament',
    version: '01.09.00.06',
    user_id: null,
    is_custom: false,
  },
  {
    setting_id: 'GFPG99_01',
    name: 'Generic PETG @BBL X1C',
    type: 'filament',
    version: '01.09.00.06',
    user_id: null,
    is_custom: false,
  },
  {
    setting_id: 'GFSA00_05',
    name: 'Bambu ABS @BBL X1C',
    type: 'filament',
    version: '01.09.00.06',
    user_id: null,
    is_custom: false,
  },
  {
    setting_id: 'custom-pla-001',
    name: '# My Custom PLA @BBL X1C',
    type: 'filament',
    version: '01.09.00.06',
    user_id: 'user123',
    is_custom: true,
  },
]

/**
 * Mock setting detail (for user presets)
 */
export const mockSettingDetail = {
  setting_id: 'custom-pla-001',
  name: 'My Custom PLA @BBL X1C',
  filament_id: 'GFSL05',
  base_id: 'GFSL05_07',
}

/**
 * Mock cloud status
 */
export const mockCloudStatus = {
  is_authenticated: false,
  email: null,
}

/**
 * Mock authenticated cloud status
 */
export const mockAuthenticatedCloudStatus = {
  is_authenticated: true,
  email: 'test@example.com',
}

/**
 * Mock version info
 */
export const mockVersionInfo = {
  version: '0.1.0',
  git_commit: 'abc1234',
  git_branch: 'main',
}

/**
 * Mock update check (no update available)
 */
export const mockUpdateCheck = {
  current_version: '0.1.0',
  latest_version: '0.1.0',
  update_available: false,
  release_notes: null,
  release_url: null,
  published_at: null,
  error: null,
}

/**
 * Mock device status
 */
export const mockDeviceStatus = {
  connected: false,
  last_weight: null,
  weight_stable: false,
  current_tag_id: null,
}

/**
 * Mock connected device status
 */
export const mockConnectedDeviceStatus = {
  connected: true,
  last_weight: 850.5,
  weight_stable: true,
  current_tag_id: 'ABC123==',
}
