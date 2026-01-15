/**
 * SpoolBuddy Display Driver for CrowPanel Advance 7.0"
 * 800x480 RGB LCD with GT911 touch controller
 * Uses LVGL 9.x
 */

#ifndef DISPLAY_DRIVER_H
#define DISPLAY_DRIVER_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Initialize the display, touch, and LVGL
 * This must be called before any LVGL operations
 *
 * @return 0 on success, negative on error
 */
int display_init(void);

/**
 * Run LVGL timer handler
 * Call this periodically (every 5-10ms) from the main loop
 */
void display_tick(void);

/**
 * Get elapsed time in milliseconds
 * Used for LVGL tick
 */
uint32_t display_get_tick_ms(void);

/**
 * Set backlight brightness (0-100%)
 * Uses I2C to STC8H1K28 at address 0x30
 */
void display_set_backlight_hw(uint8_t brightness_percent);

#ifdef __cplusplus
}
#endif

#endif /* DISPLAY_DRIVER_H */
