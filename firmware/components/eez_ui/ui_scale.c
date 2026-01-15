// =============================================================================
// ui_scale.c - Scale Settings Screen Handlers
// =============================================================================
// NOTE: Scale screen has been removed from the new EEZ design.
// These functions are stubbed out for compatibility.
// =============================================================================

#include "ui_internal.h"
#include "screens.h"
#include <stdio.h>

// =============================================================================
// Scale Functions (Rust FFI on ESP32, stubs on simulator)
// =============================================================================

#ifdef ESP_PLATFORM
// ESP32: External Rust FFI functions (from scale_manager.rs)
extern float scale_get_weight(void);
extern int32_t scale_get_raw(void);
extern bool scale_is_initialized(void);
extern bool scale_is_stable(void);
extern int32_t scale_tare(void);
extern int32_t scale_calibrate(float known_weight_grams);
extern int32_t scale_get_tare_offset(void);
#else
// Simulator: Scale functions that read from backend (which gets from ESP32 device)
// Forward declare backend functions to avoid header conflicts
extern float backend_get_scale_weight(void);
extern bool backend_is_scale_stable(void);
extern int backend_scale_tare(void);
extern int backend_scale_calibrate(float known_weight_grams);

float scale_get_weight(void) {
    // Get weight from backend (which comes from real ESP32 device)
    return backend_get_scale_weight();
}
int32_t scale_get_raw(void) {
    // Approximate raw value from backend weight
    return (int32_t)(backend_get_scale_weight() * 100);
}
bool scale_is_initialized(void) { return true; }
bool scale_is_stable(void) { return backend_is_scale_stable(); }
int32_t scale_tare(void) {
    // Send tare command to ESP32 via backend
    printf("[scale] Sending tare command to ESP32...\n");
    return backend_scale_tare();
}
int32_t scale_calibrate(float known_weight_grams) {
    // Send calibrate command to ESP32 via backend
    printf("[scale] Sending calibrate command to ESP32 (known weight: %.1f g)...\n", known_weight_grams);
    return backend_scale_calibrate(known_weight_grams);
}
int32_t scale_get_tare_offset(void) { return 0; }  // Tare offset is managed by ESP32

// Simulator control functions (kept for compatibility, but now no-op)
void sim_set_scale_weight(float weight) { (void)weight; }
void sim_set_scale_initialized(bool initialized) { (void)initialized; }
void sim_set_scale_stable(bool stable) { (void)stable; }
float sim_get_scale_weight(void) { return backend_get_scale_weight(); }
#endif

// =============================================================================
// UI Update Functions (stubbed - no scale screen in new design)
// =============================================================================

void update_scale_ui(void) {
    // No scale screen in new EEZ design - nothing to update
}

// =============================================================================
// Wire Functions (stubbed - no scale screen in new design)
// =============================================================================

void wire_scale_buttons(void) {
    // No scale screen in new EEZ design - nothing to wire
}
