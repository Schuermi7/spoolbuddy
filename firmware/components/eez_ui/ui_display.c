// =============================================================================
// ui_display.c - Display Settings Screen Handlers
// =============================================================================
// Handles display brightness and screen timeout settings.
// =============================================================================

#include "ui_internal.h"
#include "screens.h"
#include <stdio.h>
#include <string.h>

// Value labels created programmatically
static lv_obj_t *brightness_value_label = NULL;
static lv_obj_t *timeout_value_label = NULL;

// =============================================================================
// Display Functions (Rust FFI on ESP32, stubs on simulator)
// =============================================================================

#ifdef ESP_PLATFORM
// ESP32: External Rust FFI functions
extern void display_set_brightness(uint8_t brightness);
extern uint8_t display_get_brightness(void);
extern void display_set_timeout(uint16_t timeout_seconds);
extern uint16_t display_get_timeout(void);
#else
// Simulator: Mock display functions with controllable state
static uint8_t mock_brightness = 80;        // 0-100%
static uint16_t mock_timeout = 300;         // seconds (5 minutes default)

void display_set_brightness(uint8_t brightness) {
    mock_brightness = brightness > 100 ? 100 : brightness;
    printf("[display] Brightness set to %d%%\n", mock_brightness);
}

uint8_t display_get_brightness(void) {
    return mock_brightness;
}

void display_set_timeout(uint16_t timeout_seconds) {
    mock_timeout = timeout_seconds;
    printf("[display] Screen timeout set to %d seconds\n", mock_timeout);
}

uint16_t display_get_timeout(void) {
    return mock_timeout;
}
#endif

// =============================================================================
// Value Label Update Helpers
// =============================================================================

static void update_brightness_value(uint8_t brightness) {
    if (brightness_value_label) {
        char buf[16];
        snprintf(buf, sizeof(buf), "%d%%", brightness);
        lv_label_set_text(brightness_value_label, buf);
    }
}

static void update_timeout_value(uint16_t timeout_sec) {
    if (timeout_value_label) {
        char buf[16];
        if (timeout_sec == 0) {
            lv_label_set_text(timeout_value_label, "Never");
        } else if (timeout_sec < 60) {
            snprintf(buf, sizeof(buf), "%ds", timeout_sec);
            lv_label_set_text(timeout_value_label, buf);
        } else {
            int minutes = timeout_sec / 60;
            int seconds = timeout_sec % 60;
            if (seconds == 0) {
                snprintf(buf, sizeof(buf), "%dm", minutes);
            } else {
                snprintf(buf, sizeof(buf), "%dm %ds", minutes, seconds);
            }
            lv_label_set_text(timeout_value_label, buf);
        }
    }
}

// =============================================================================
// Slider Event Handlers
// =============================================================================

static void brightness_slider_handler(lv_event_t *e) {
    lv_obj_t *slider = lv_event_get_target(e);
    int32_t value = lv_slider_get_value(slider);
    display_set_brightness((uint8_t)value);
    update_brightness_value((uint8_t)value);
}

static void timeout_slider_handler(lv_event_t *e) {
    lv_obj_t *slider = lv_event_get_target(e);
    int32_t value = lv_slider_get_value(slider);
    display_set_timeout((uint16_t)value);
    update_timeout_value((uint16_t)value);
}

// =============================================================================
// UI Update Functions
// =============================================================================

void update_display_ui(void) {
    // Update resolution value
    if (objects.settings_display_screen_content_panel_label_resolution_value) {
        lv_label_set_text(objects.settings_display_screen_content_panel_label_resolution_value, "800x480");
    }

    // Update panel value
    if (objects.settings_display_screen_content_panel_label_panel_value) {
        lv_label_set_text(objects.settings_display_screen_content_panel_label_panel_value, "7.0\" IPS LCD");
    }

    // Set slider values to current settings
    if (objects.settings_display_screen_content_panel_label_brightness_slider) {
        lv_slider_set_value(objects.settings_display_screen_content_panel_label_brightness_slider,
                           display_get_brightness(), LV_ANIM_OFF);
    }

    if (objects.settings_display_screen_content_panel_label_timeout_slider) {
        lv_slider_set_value(objects.settings_display_screen_content_panel_label_timeout_slider,
                           display_get_timeout(), LV_ANIM_OFF);
    }
}

// =============================================================================
// Wire Functions
// =============================================================================

void wire_display_buttons(void) {
    // Reset value labels (they get deleted with screen)
    brightness_value_label = NULL;
    timeout_value_label = NULL;

    // Configure brightness slider
    if (objects.settings_display_screen_content_panel_label_brightness_slider) {
        lv_obj_t *slider = objects.settings_display_screen_content_panel_label_brightness_slider;

        // Set range 10-100 (don't allow fully off)
        lv_slider_set_range(slider, 10, 100);

        // Set current value
        lv_slider_set_value(slider, display_get_brightness(), LV_ANIM_OFF);

        // Add value change handler
        lv_obj_add_event_cb(slider, brightness_slider_handler, LV_EVENT_VALUE_CHANGED, NULL);

        // Style the slider
        lv_obj_set_style_bg_color(slider, lv_color_hex(0x333333), LV_PART_MAIN);
        lv_obj_set_style_bg_color(slider, lv_color_hex(0x00ff00), LV_PART_INDICATOR);
        lv_obj_set_style_bg_color(slider, lv_color_hex(0x00ff00), LV_PART_KNOB);

        // Create value label next to slider
        lv_obj_t *parent = lv_obj_get_parent(slider);
        brightness_value_label = lv_label_create(parent);
        lv_obj_set_style_text_font(brightness_value_label, &lv_font_montserrat_16, LV_PART_MAIN);
        lv_obj_set_style_text_color(brightness_value_label, lv_color_hex(0xffffff), LV_PART_MAIN);
        lv_obj_align_to(brightness_value_label, slider, LV_ALIGN_OUT_RIGHT_MID, 15, 0);
        update_brightness_value(display_get_brightness());
    }

    // Configure timeout slider
    if (objects.settings_display_screen_content_panel_label_timeout_slider) {
        lv_obj_t *slider = objects.settings_display_screen_content_panel_label_timeout_slider;

        // Set range 0-900 seconds (0 = never, max 15 minutes)
        lv_slider_set_range(slider, 0, 900);

        // Set current value
        lv_slider_set_value(slider, display_get_timeout(), LV_ANIM_OFF);

        // Add value change handler
        lv_obj_add_event_cb(slider, timeout_slider_handler, LV_EVENT_VALUE_CHANGED, NULL);

        // Style the slider
        lv_obj_set_style_bg_color(slider, lv_color_hex(0x333333), LV_PART_MAIN);
        lv_obj_set_style_bg_color(slider, lv_color_hex(0x00ff00), LV_PART_INDICATOR);
        lv_obj_set_style_bg_color(slider, lv_color_hex(0x00ff00), LV_PART_KNOB);

        // Create value label next to slider
        lv_obj_t *parent = lv_obj_get_parent(slider);
        timeout_value_label = lv_label_create(parent);
        lv_obj_set_style_text_font(timeout_value_label, &lv_font_montserrat_16, LV_PART_MAIN);
        lv_obj_set_style_text_color(timeout_value_label, lv_color_hex(0xffffff), LV_PART_MAIN);
        lv_obj_align_to(timeout_value_label, slider, LV_ALIGN_OUT_RIGHT_MID, 15, 0);
        update_timeout_value(display_get_timeout());
    }

    // Update display info
    update_display_ui();
}
