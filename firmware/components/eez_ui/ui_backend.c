/**
 * @file ui_backend.c
 * @brief Backend server communication UI integration
 *
 * Updates UI elements with printer status from the SpoolBuddy backend server.
 * Called periodically from ui_tick() to refresh displayed data.
 */

#include "ui_internal.h"
#include "screens.h"
#include <lvgl.h>
#include <stdio.h>
#include <string.h>

// Update counter for rate limiting UI updates
static int backend_update_counter = 0;
// Track previous screen to detect navigation
static int previous_screen = -1;
// Flag to update more frequently when data is stale
static bool needs_data_refresh = true;
// Last displayed time (to avoid redundant updates)
static int last_time_hhmm = -1;
// Last printer count for dropdown update tracking
static int last_printer_count = -1;
// Cover image state
static bool cover_displayed = false;
static lv_image_dsc_t cover_img_dsc;

// Forward declarations
static void update_main_screen_backend_status(BackendStatus *status);
static void update_clock_displays(void);
static void update_printer_dropdowns(BackendStatus *status);
static void update_cover_image(void);
static void update_ams_display(void);

/**
 * @brief Update UI elements with backend printer status
 *
 * This function is called periodically from ui_tick() to refresh the UI
 * with the latest printer status from the backend server.
 */
void update_backend_ui(void) {
    // Get current screen ID
    int screen_id = currentScreen + 1;  // Convert to ScreensEnum (1-based)

    // Force immediate update when navigating to main screen
    bool force_update = (screen_id == SCREEN_ID_MAIN && previous_screen != screen_id);
    if (force_update) {
        needs_data_refresh = true;
    }
    previous_screen = screen_id;

    // Rate limiting:
    // - Every 20 ticks (~100ms) when waiting for data
    // - Every 100 ticks (~500ms) when we have data
    int rate_limit = needs_data_refresh ? 20 : 100;
    if (!force_update && ++backend_update_counter < rate_limit) {
        return;
    }
    backend_update_counter = 0;

    // Get backend connection status
    BackendStatus status;
    backend_get_status(&status);

    // Check if we got valid data
    if (status.state == 2 && status.printer_count > 0) {
        needs_data_refresh = false;
    }

    // Update based on current screen
    if (screen_id == SCREEN_ID_MAIN) {
        update_main_screen_backend_status(&status);
        update_cover_image();
    }

    // Update clock on all screens
    update_clock_displays();

    // Update printer dropdowns
    update_printer_dropdowns(&status);
}

/**
 * @brief Format remaining time as human-readable string
 */
static void format_remaining_time(char *buf, size_t buf_size, uint16_t minutes) {
    if (minutes >= 60) {
        int hours = minutes / 60;
        int mins = minutes % 60;
        if (mins > 0) {
            snprintf(buf, buf_size, "%dh %dm left", hours, mins);
        } else {
            snprintf(buf, buf_size, "%dh left", hours);
        }
    } else if (minutes > 0) {
        snprintf(buf, buf_size, "%dm left", minutes);
    } else {
        buf[0] = '\0';  // Empty string
    }
}

/**
 * @brief Update the main screen with backend status
 */
static void update_main_screen_backend_status(BackendStatus *status) {
    char buf[64];

    // Check if main screen objects exist
    if (!objects.main) {
        return;
    }

    // Update printer labels if we have printer data
    if (status->state == 2 && status->printer_count > 0) {
        BackendPrinterInfo printer;

        // Update first printer info
        if (backend_get_printer(0, &printer) == 0) {
            // printer_label = Printer name
            if (objects.printer_label) {
                lv_label_set_text(objects.printer_label,
                    printer.name[0] ? printer.name : printer.serial);
            }

            // printer_label_1 = Status (RUNNING 88%, IDLE, Offline)
            if (objects.printer_label_1) {
                if (printer.connected) {
                    if (printer.print_progress > 0) {
                        snprintf(buf, sizeof(buf), "%s %d%%",
                                 printer.gcode_state[0] ? printer.gcode_state : "Unknown",
                                 printer.print_progress);
                    } else {
                        snprintf(buf, sizeof(buf), "%s",
                                 printer.gcode_state[0] ? printer.gcode_state : "Idle");
                    }
                } else {
                    snprintf(buf, sizeof(buf), "Offline");
                }
                lv_label_set_text(objects.printer_label_1, buf);
            }

            // printer_label_2 = File name (subtask_name)
            if (objects.printer_label_2) {
                if (printer.connected && printer.subtask_name[0]) {
                    lv_label_set_text(objects.printer_label_2, printer.subtask_name);
                } else {
                    lv_label_set_text(objects.printer_label_2, "");
                }
            }

            // obj49 = Time remaining (inline with filename at y=62)
            if (objects.obj49) {
                if (printer.connected && printer.remaining_time_min > 0) {
                    format_remaining_time(buf, sizeof(buf), printer.remaining_time_min);
                    lv_label_set_text(objects.obj49, buf);
                } else {
                    lv_label_set_text(objects.obj49, "");
                }
            }
        }
    } else if (status->state != 2) {
        // Not connected to backend server
        if (objects.printer_label) {
            lv_label_set_text(objects.printer_label, "No Server");
        }
        if (objects.printer_label_1) {
            lv_label_set_text(objects.printer_label_1, "Offline");
        }
        if (objects.printer_label_2) {
            lv_label_set_text(objects.printer_label_2, "");
        }
        if (objects.obj49) {
            lv_label_set_text(objects.obj49, "");
        }
    }
}

/**
 * @brief Update clock displays on all screens
 */
static void update_clock_displays(void) {
    int time_hhmm = time_get_hhmm();

    // Only update if time changed or first valid time
    if (time_hhmm < 0 || time_hhmm == last_time_hhmm) {
        return;
    }
    last_time_hhmm = time_hhmm;

    int hour = (time_hhmm >> 8) & 0xFF;
    int minute = time_hhmm & 0xFF;

    char time_str[8];
    snprintf(time_str, sizeof(time_str), "%02d:%02d", hour, minute);

    // Update clock on all screens that have one
    // Main screen
    if (objects.clock) {
        lv_label_set_text(objects.clock, time_str);
    }
    // Settings screens
    if (objects.clock_s) {
        lv_label_set_text(objects.clock_s, time_str);
    }
    if (objects.clock_sd) {
        lv_label_set_text(objects.clock_sd, time_str);
    }
    if (objects.clock_sd_wifi) {
        lv_label_set_text(objects.clock_sd_wifi, time_str);
    }
    if (objects.clock_sd_mqtt) {
        lv_label_set_text(objects.clock_sd_mqtt, time_str);
    }
    if (objects.clock_sd_nfc) {
        lv_label_set_text(objects.clock_sd_nfc, time_str);
    }
    if (objects.clock_sd_scale) {
        lv_label_set_text(objects.clock_sd_scale, time_str);
    }
    if (objects.clock_sd_display) {
        lv_label_set_text(objects.clock_sd_display, time_str);
    }
    if (objects.clock_sd_about) {
        lv_label_set_text(objects.clock_sd_about, time_str);
    }
    if (objects.clock_sd_update) {
        lv_label_set_text(objects.clock_sd_update, time_str);
    }
    if (objects.clock_sd_reset) {
        lv_label_set_text(objects.clock_sd_reset, time_str);
    }
    if (objects.clock_sd_printer_add) {
        lv_label_set_text(objects.clock_sd_printer_add, time_str);
    }
    if (objects.clock_sd_printer_add_1) {
        lv_label_set_text(objects.clock_sd_printer_add_1, time_str);
    }
    // Other screens
    if (objects.clock_2) {
        lv_label_set_text(objects.clock_2, time_str);
    }
    if (objects.clock_3) {
        lv_label_set_text(objects.clock_3, time_str);
    }
    if (objects.clock_4) {
        lv_label_set_text(objects.clock_4, time_str);
    }
}

/**
 * @brief Helper to set dropdown options on a dropdown object
 */
static void set_dropdown_options(lv_obj_t *dropdown, const char *options) {
    if (dropdown) {
        lv_dropdown_set_options(dropdown, options);
    }
}

/**
 * @brief Update printer selection dropdowns with connected printers
 */
static void update_printer_dropdowns(BackendStatus *status) {
    // Only update when printer count changes
    if (status->printer_count == last_printer_count) {
        return;
    }
    last_printer_count = status->printer_count;

    // Build options string with connected printer names
    char options[256] = "";
    int pos = 0;

    for (int i = 0; i < status->printer_count && i < 8; i++) {
        BackendPrinterInfo printer;
        if (backend_get_printer(i, &printer) == 0 && printer.connected) {
            if (pos > 0) {
                options[pos++] = '\n';
            }
            const char *name = printer.name[0] ? printer.name : printer.serial;
            int len = strlen(name);
            if (pos + len < sizeof(options) - 1) {
                strcpy(&options[pos], name);
                pos += len;
            }
        }
    }

    // If no connected printers, show placeholder
    if (pos == 0) {
        strcpy(options, "No Printers");
    }

    // Update all printer select dropdowns
    set_dropdown_options(objects.printer_select, options);
    set_dropdown_options(objects.printer_select_2, options);
    set_dropdown_options(objects.printer_select_3, options);
    set_dropdown_options(objects.printer_select_4, options);
    set_dropdown_options(objects.printer_select_s, options);
    set_dropdown_options(objects.printer_select_sd, options);
    set_dropdown_options(objects.printer_select_sd_wifi, options);
    set_dropdown_options(objects.printer_select_sd_mqtt, options);
    set_dropdown_options(objects.printer_select_sd_nfc, options);
    set_dropdown_options(objects.printer_select_sd_scale, options);
    set_dropdown_options(objects.printer_select_sd_display, options);
    set_dropdown_options(objects.printer_select_sd_about, options);
    set_dropdown_options(objects.printer_select_sd_update, options);
    set_dropdown_options(objects.printer_select_sd_reset, options);
    set_dropdown_options(objects.printer_select_sd_printer_add, options);
    set_dropdown_options(objects.printer_select_sd_printer_add_1, options);
}

// Cover image dimensions (must match backend COVER_SIZE and placeholder image)
#define COVER_WIDTH 100
#define COVER_HEIGHT 100

/**
 * @brief Update cover image from downloaded raw RGB565 data
 */
static void update_cover_image(void) {
    if (!objects.print_cover) {
        return;
    }

    if (backend_has_cover()) {
        if (!cover_displayed) {
            // Get cover data from Rust (raw RGB565 pixels)
            uint32_t size = 0;
            const uint8_t *data = backend_get_cover_data(&size);

            // Verify size matches expected RGB565 data (70x70x2 = 9800 bytes)
            uint32_t expected_size = COVER_WIDTH * COVER_HEIGHT * 2;
            if (data && size == expected_size) {
                // Set up image descriptor for raw RGB565 data
                memset(&cover_img_dsc, 0, sizeof(cover_img_dsc));
                cover_img_dsc.header.magic = LV_IMAGE_HEADER_MAGIC;
                cover_img_dsc.header.cf = LV_COLOR_FORMAT_RGB565;
                cover_img_dsc.header.w = COVER_WIDTH;
                cover_img_dsc.header.h = COVER_HEIGHT;
                cover_img_dsc.header.stride = COVER_WIDTH * 2;  // RGB565 = 2 bytes per pixel
                cover_img_dsc.data_size = size;
                cover_img_dsc.data = data;

                // Set the image source
                lv_image_set_src(objects.print_cover, &cover_img_dsc);

                // Set scale to 256 (100% / 1:1) - override the default 100 scale
                lv_image_set_scale(objects.print_cover, 256);

                // Make fully opaque when showing cover
                lv_obj_set_style_opa(objects.print_cover, 255, LV_PART_MAIN | LV_STATE_DEFAULT);

                cover_displayed = true;
            }
        }
    } else {
        if (cover_displayed) {
            // No cover available, revert to placeholder
            extern const lv_image_dsc_t img_filament_spool;
            lv_image_set_src(objects.print_cover, &img_filament_spool);

            // Restore original scale (100 = ~39% for 100x100 -> ~39x39 display)
            lv_image_set_scale(objects.print_cover, 100);

            // Semi-transparent for placeholder
            lv_obj_set_style_opa(objects.print_cover, 128, LV_PART_MAIN | LV_STATE_DEFAULT);

            cover_displayed = false;
        }
    }
}
