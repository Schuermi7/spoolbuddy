/**
 * NFC Card UI - Main screen NFC/Scale card management
 * Shows a popup when NFC tag is detected
 */

#include "ui_nfc_card.h"
#include "screens.h"
#include "lvgl.h"
#include <stdio.h>
#include <string.h>
#include "esp_log.h"

static const char *TAG = "ui_nfc_card";

// External Rust FFI functions - NFC
extern bool nfc_is_initialized(void);
extern bool nfc_tag_present(void);
extern uint8_t nfc_get_uid_hex(uint8_t *buf, uint8_t buf_len);

// Decoded tag data (Rust FFI on ESP32, mock on simulator)
extern const char* nfc_get_tag_vendor(void);
extern const char* nfc_get_tag_material(void);
extern const char* nfc_get_tag_color_name(void);
extern uint32_t nfc_get_tag_color_rgba(void);

// External Rust FFI functions - Scale
extern float scale_get_weight(void);
extern bool scale_is_initialized(void);
extern bool scale_is_stable(void);

// Screen navigation
extern enum ScreensEnum pendingScreen;

// Static state
static bool last_tag_present = false;
static uint8_t popup_tag_uid[32] = {0};  // UID of tag that opened the popup
static bool popup_user_closed = false;    // User manually closed the popup

// Weight display stabilization (hysteresis)
static float last_displayed_weight = 0.0f;
static bool weight_initialized = false;

// Popup elements
static lv_obj_t *tag_popup = NULL;
static lv_obj_t *popup_tag_label = NULL;
static lv_obj_t *popup_weight_label = NULL;

// Button click handlers
static void popup_close_handler(lv_event_t *e) {
    (void)e;
    popup_user_closed = true;  // Remember user closed it
    if (tag_popup) {
        lv_obj_delete(tag_popup);
        tag_popup = NULL;
        popup_tag_label = NULL;
        popup_weight_label = NULL;
    }
}

static void configure_ams_click_handler(lv_event_t *e) {
    (void)e;
    // Close popup first
    popup_close_handler(NULL);
    // Navigate to scan_result screen (Encode Tag)
    pendingScreen = SCREEN_ID_SCAN_RESULT;
}

static void add_spool_click_handler(lv_event_t *e) {
    (void)e;
    // TODO: Navigate to add spool screen or show dialog
    printf("[ui_nfc_card] Add Spool clicked - not yet implemented\n");
}

// Close popup if open
static void close_popup(void) {
    if (tag_popup) {
        lv_obj_delete(tag_popup);
        tag_popup = NULL;
        popup_tag_label = NULL;
        popup_weight_label = NULL;
    }
}

// Spool images (from assets)
extern const lv_image_dsc_t img_spool_clean;
extern const lv_image_dsc_t img_spool_fill;

// Material subtype
extern const char* nfc_get_tag_material_subtype(void);

// Create the tag detected popup - matches simulator layout
static void create_tag_popup(void) {
    if (tag_popup) return;  // Already open

    ESP_LOGI(TAG, "Creating tag popup");

    // Get tag UID and store it
    uint8_t uid_str[32];
    nfc_get_uid_hex(uid_str, sizeof(uid_str));
    strncpy((char*)popup_tag_uid, (char*)uid_str, sizeof(popup_tag_uid) - 1);
    popup_tag_uid[sizeof(popup_tag_uid) - 1] = '\0';

    // Get weight
    float weight = scale_get_weight();
    bool scale_ok = scale_is_initialized();

    // Get tag data
    const char *vendor = nfc_get_tag_vendor();
    const char *material = nfc_get_tag_material();
    const char *color_name = nfc_get_tag_color_name();
    uint32_t color_rgba = nfc_get_tag_color_rgba();

    ESP_LOGI(TAG, "Tag data: uid=%s, vendor=%s, material=%s, color=%s, rgba=0x%08lX",
             uid_str, vendor ? vendor : "NULL", material ? material : "NULL",
             color_name ? color_name : "NULL", (unsigned long)color_rgba);

    // Create modal background (semi-transparent overlay)
    tag_popup = lv_obj_create(lv_layer_top());
    lv_obj_set_size(tag_popup, 800, 480);
    lv_obj_set_pos(tag_popup, 0, 0);
    lv_obj_set_style_bg_color(tag_popup, lv_color_hex(0x000000), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(tag_popup, 180, LV_PART_MAIN);
    lv_obj_set_style_border_width(tag_popup, 0, LV_PART_MAIN);
    lv_obj_clear_flag(tag_popup, LV_OBJ_FLAG_SCROLLABLE);

    // Click on background closes popup
    lv_obj_add_event_cb(tag_popup, popup_close_handler, LV_EVENT_CLICKED, NULL);

    // Create popup card (centered) - larger to fit 2x2 buttons
    lv_obj_t *card = lv_obj_create(tag_popup);
    lv_obj_set_size(card, 450, 300);
    lv_obj_center(card);
    lv_obj_set_style_bg_color(card, lv_color_hex(0x1a1a1a), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(card, 255, LV_PART_MAIN);
    lv_obj_set_style_border_color(card, lv_color_hex(0x4CAF50), LV_PART_MAIN);
    lv_obj_set_style_border_width(card, 2, LV_PART_MAIN);
    lv_obj_set_style_radius(card, 12, LV_PART_MAIN);
    lv_obj_set_style_pad_all(card, 20, LV_PART_MAIN);
    lv_obj_clear_flag(card, LV_OBJ_FLAG_SCROLLABLE);

    // Prevent clicks on card from closing popup
    lv_obj_add_flag(card, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(card, NULL, LV_EVENT_CLICKED, NULL);  // Absorb click

    // Title
    lv_obj_t *title = lv_label_create(card);
    lv_label_set_text(title, "NFC Tag Detected");
    lv_obj_set_style_text_font(title, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_set_style_text_color(title, lv_color_hex(0x4CAF50), LV_PART_MAIN);
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 0);

    // Container for spool icon + details (centered)
    lv_obj_t *content_container = lv_obj_create(card);
    lv_obj_set_size(content_container, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_align(content_container, LV_ALIGN_TOP_MID, 0, 35);
    lv_obj_set_style_bg_opa(content_container, 0, LV_PART_MAIN);
    lv_obj_set_style_border_width(content_container, 0, LV_PART_MAIN);
    lv_obj_set_style_pad_all(content_container, 0, LV_PART_MAIN);
    lv_obj_clear_flag(content_container, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_flex_flow(content_container, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(content_container, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(content_container, 15, LV_PART_MAIN);

    // Spool image container (for layered images)
    lv_obj_t *spool_container = lv_obj_create(content_container);
    lv_obj_set_size(spool_container, 50, 60);
    lv_obj_set_style_bg_opa(spool_container, 0, LV_PART_MAIN);
    lv_obj_set_style_border_width(spool_container, 0, LV_PART_MAIN);
    lv_obj_set_style_pad_all(spool_container, 0, LV_PART_MAIN);
    lv_obj_clear_flag(spool_container, LV_OBJ_FLAG_SCROLLABLE);

    // Spool outline first (underneath)
    lv_obj_t *spool_outline = lv_image_create(spool_container);
    lv_image_set_src(spool_outline, &img_spool_clean);
    lv_image_set_scale(spool_outline, 300);
    lv_obj_set_pos(spool_outline, 0, 0);

    // Color fill on top
    lv_obj_t *spool_fill = lv_image_create(spool_container);
    lv_image_set_src(spool_fill, &img_spool_fill);
    lv_image_set_scale(spool_fill, 300);
    lv_obj_set_pos(spool_fill, 0, 0);

    // Color the inlet with filament color
    uint8_t r = (color_rgba >> 24) & 0xFF;
    uint8_t g = (color_rgba >> 16) & 0xFF;
    uint8_t b = (color_rgba >> 8) & 0xFF;
    uint32_t color_hex = (r << 16) | (g << 8) | b;
    if (color_rgba != 0) {
        lv_obj_set_style_image_recolor(spool_fill, lv_color_hex(color_hex), 0);
        lv_obj_set_style_image_recolor_opa(spool_fill, 255, 0);
    } else {
        lv_obj_set_style_image_recolor(spool_fill, lv_color_hex(0x808080), 0);
        lv_obj_set_style_image_recolor_opa(spool_fill, 255, 0);
    }

    // Spool details container (for label/value pairs)
    lv_obj_t *details_container = lv_obj_create(content_container);
    lv_obj_set_size(details_container, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_style_bg_opa(details_container, 0, 0);
    lv_obj_set_style_border_width(details_container, 0, 0);
    lv_obj_set_style_pad_all(details_container, 0, 0);
    lv_obj_clear_flag(details_container, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_flex_flow(details_container, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(details_container, 4, 0);

    // Helper macro to create label/value rows
    #define CREATE_DETAIL_ROW(label_text, value_text) do { \
        lv_obj_t *row = lv_obj_create(details_container); \
        lv_obj_set_size(row, LV_SIZE_CONTENT, LV_SIZE_CONTENT); \
        lv_obj_set_style_bg_opa(row, 0, 0); \
        lv_obj_set_style_border_width(row, 0, 0); \
        lv_obj_set_style_pad_all(row, 0, 0); \
        lv_obj_clear_flag(row, LV_OBJ_FLAG_SCROLLABLE); \
        lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW); \
        lv_obj_set_style_pad_column(row, 4, 0); \
        lv_obj_t *lbl = lv_label_create(row); \
        lv_label_set_text(lbl, label_text); \
        lv_obj_set_style_text_font(lbl, &lv_font_montserrat_14, 0); \
        lv_obj_set_style_text_color(lbl, lv_color_hex(0x888888), 0); \
        lv_obj_t *val = lv_label_create(row); \
        lv_label_set_text(val, value_text); \
        lv_obj_set_style_text_font(val, &lv_font_montserrat_14, 0); \
        lv_obj_set_style_text_color(val, lv_color_hex(0xfafafa), 0); \
    } while(0)

    char weight_str[32];
    if (scale_ok) {
        int weight_int = (int)weight;
        if (weight_int < 0) weight_int = 0;
        snprintf(weight_str, sizeof(weight_str), "%dg", weight_int);
    } else {
        snprintf(weight_str, sizeof(weight_str), "N/A");
    }

    CREATE_DETAIL_ROW("Tag:", (const char*)uid_str);
    CREATE_DETAIL_ROW("Vendor:", (vendor && vendor[0]) ? vendor : "Unknown");
    CREATE_DETAIL_ROW("Material:", (material && material[0]) ? material : "Unknown");
    CREATE_DETAIL_ROW("Color:", (color_name && color_name[0]) ? color_name : "Unknown");
    CREATE_DETAIL_ROW("Weight:", weight_str);

    #undef CREATE_DETAIL_ROW

    // No longer need dynamic weight updates
    popup_tag_label = NULL;
    popup_weight_label = NULL;

    // Check if this is an unknown tag
    bool is_unknown_tag = (vendor && strcmp(vendor, "Unknown") == 0);

    // Show hint for unknown tags
    if (is_unknown_tag) {
        lv_obj_t *hint_label = lv_label_create(card);
        lv_label_set_text(hint_label, LV_SYMBOL_WARNING " Add to inventory, then edit in web UI");
        lv_obj_set_style_text_font(hint_label, &lv_font_montserrat_12, LV_PART_MAIN);
        lv_obj_set_style_text_color(hint_label, lv_color_hex(0xFFAA00), LV_PART_MAIN);
        lv_obj_align(hint_label, LV_ALIGN_BOTTOM_MID, 0, -105);
    }

    // Buttons container - 2x2 grid layout
    lv_obj_t *btn_container = lv_obj_create(card);
    lv_obj_set_size(btn_container, LV_PCT(100), 100);  // 2 rows
    lv_obj_align(btn_container, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_obj_set_style_bg_opa(btn_container, 0, LV_PART_MAIN);
    lv_obj_set_style_border_width(btn_container, 0, LV_PART_MAIN);
    lv_obj_set_style_pad_all(btn_container, 0, LV_PART_MAIN);
    lv_obj_clear_flag(btn_container, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_flex_flow(btn_container, LV_FLEX_FLOW_ROW_WRAP);
    lv_obj_set_flex_align(btn_container, LV_FLEX_ALIGN_SPACE_EVENLY, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_row(btn_container, 8, LV_PART_MAIN);

    int btn_width = 180;

    // "Add Spool" button
    lv_obj_t *btn_add = lv_btn_create(btn_container);
    lv_obj_set_size(btn_add, btn_width, 42);
    lv_obj_set_style_bg_color(btn_add, lv_color_hex(0x2D5A27), LV_PART_MAIN);
    lv_obj_set_style_radius(btn_add, 8, LV_PART_MAIN);
    lv_obj_add_event_cb(btn_add, add_spool_click_handler, LV_EVENT_CLICKED, NULL);

    lv_obj_t *add_label = lv_label_create(btn_add);
    lv_label_set_text(add_label, "Add Spool");
    lv_obj_set_style_text_font(add_label, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_style_text_color(add_label, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
    lv_obj_center(add_label);

    // "Link to Spool" button (disabled for now - backend not implemented)
    lv_obj_t *btn_link = lv_btn_create(btn_container);
    lv_obj_set_size(btn_link, btn_width, 42);
    lv_obj_set_style_bg_color(btn_link, lv_color_hex(0x444444), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(btn_link, 128, LV_PART_MAIN);
    lv_obj_set_style_radius(btn_link, 8, LV_PART_MAIN);
    lv_obj_clear_flag(btn_link, LV_OBJ_FLAG_CLICKABLE);

    lv_obj_t *link_label = lv_label_create(btn_link);
    lv_label_set_text(link_label, "Link to Spool");
    lv_obj_set_style_text_font(link_label, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_style_text_color(link_label, lv_color_hex(0x888888), LV_PART_MAIN);
    lv_obj_center(link_label);

    // "Config AMS" button
    lv_obj_t *btn_ams = lv_btn_create(btn_container);
    lv_obj_set_size(btn_ams, btn_width, 42);
    lv_obj_set_style_bg_color(btn_ams, lv_color_hex(0x1E88E5), LV_PART_MAIN);
    lv_obj_set_style_radius(btn_ams, 8, LV_PART_MAIN);
    lv_obj_add_event_cb(btn_ams, configure_ams_click_handler, LV_EVENT_CLICKED, NULL);

    lv_obj_t *ams_label = lv_label_create(btn_ams);
    lv_label_set_text(ams_label, "Config AMS");
    lv_obj_set_style_text_font(ams_label, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_style_text_color(ams_label, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
    lv_obj_center(ams_label);

    // "Close" button
    lv_obj_t *btn_close = lv_btn_create(btn_container);
    lv_obj_set_size(btn_close, btn_width, 42);
    lv_obj_set_style_bg_color(btn_close, lv_color_hex(0x666666), LV_PART_MAIN);
    lv_obj_set_style_radius(btn_close, 8, LV_PART_MAIN);
    lv_obj_add_event_cb(btn_close, popup_close_handler, LV_EVENT_CLICKED, NULL);

    lv_obj_t *close_label = lv_label_create(btn_close);
    lv_label_set_text(close_label, "Close");
    lv_obj_set_style_text_font(close_label, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_style_text_color(close_label, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
    lv_obj_center(close_label);

    ESP_LOGI(TAG, "Tag popup created successfully");
}

// Update weight display in popup if open
static void update_popup_weight(void) {
    if (!popup_weight_label) return;

    float weight = scale_get_weight();
    bool scale_ok = scale_is_initialized();

    char weight_text[64];
    if (scale_ok) {
        int weight_int = (int)weight;
        if (weight_int < 0) weight_int = 0;
        snprintf(weight_text, sizeof(weight_text), "Weight: %dg", weight_int);
    } else {
        snprintf(weight_text, sizeof(weight_text), "Weight: N/A (scale not ready)");
    }
    lv_label_set_text(popup_weight_label, weight_text);
}

void ui_nfc_card_init(void) {
    last_tag_present = false;
    popup_user_closed = false;
    memset(popup_tag_uid, 0, sizeof(popup_tag_uid));
    close_popup();
}

void ui_nfc_card_cleanup(void) {
    close_popup();
    last_tag_present = false;
    popup_user_closed = false;
    memset(popup_tag_uid, 0, sizeof(popup_tag_uid));
}

void ui_nfc_card_update(void) {
    if (!nfc_is_initialized()) {
        ESP_LOGD(TAG, "NFC not initialized, skipping update");
        return;
    }

    bool tag_present = nfc_tag_present();

    // Get current tag UID
    uint8_t current_uid[32] = {0};
    if (tag_present) {
        nfc_get_uid_hex(current_uid, sizeof(current_uid));
    }

    // Log state changes
    if (tag_present != last_tag_present) {
        ESP_LOGI(TAG, "Tag state changed: present=%d, uid=%s, popup=%p, user_closed=%d",
                 tag_present, current_uid, (void*)tag_popup, popup_user_closed);
    }

    // Tag detected
    if (tag_present) {
        // Check if this is a different tag than the one that opened the popup
        bool is_different_tag = (strcmp((char*)current_uid, (char*)popup_tag_uid) != 0);

        if (!tag_popup) {
            // No popup open - check if we should open one
            if (!popup_user_closed || is_different_tag) {
                // Open popup for new tag or if user hasn't closed this one
                ESP_LOGI(TAG, "Opening popup: user_closed=%d, is_different_tag=%d", popup_user_closed, is_different_tag);
                popup_user_closed = false;  // Reset for new tag
                create_tag_popup();
                ESP_LOGI(TAG, "Popup created: %p", (void*)tag_popup);
            } else {
                ESP_LOGD(TAG, "Not opening popup: user_closed=%d, is_different_tag=%d", popup_user_closed, is_different_tag);
            }
        } else if (is_different_tag && popup_tag_uid[0] != '\0') {
            // Different tag detected while popup is open - update popup for new tag
            ESP_LOGI(TAG, "Different tag detected, recreating popup");
            close_popup();
            popup_user_closed = false;
            create_tag_popup();
        } else {
            // Same tag still present - just update weight
            update_popup_weight();
        }
    } else {
        // Tag removed - reset user_closed flag so next tag will show popup
        // But DON'T close the popup - let user close it manually
        if (last_tag_present && !tag_present) {
            // Tag just removed - reset for next tag detection
            ESP_LOGI(TAG, "Tag removed, resetting user_closed flag");
            popup_user_closed = false;
        }
    }

    last_tag_present = tag_present;

    // Always update scale status label on main screen (shows current weight)
    // Uses 10g hysteresis to reduce visual bouncing
    if (objects.main_screen_nfc_scale_scale_label) {
        if (scale_is_initialized()) {
            float weight = scale_get_weight();

            // Apply 10g hysteresis - only update if change > 10g or first reading
            float diff = weight - last_displayed_weight;
            if (diff < 0) diff = -diff;  // abs

            if (!weight_initialized || diff >= 10.0f) {
                last_displayed_weight = weight;
                weight_initialized = true;

                char weight_str[16];
                snprintf(weight_str, sizeof(weight_str), "%.0fg", weight);  // Round to whole grams
                lv_label_set_text(objects.main_screen_nfc_scale_scale_label, weight_str);
            }
            lv_obj_set_style_text_color(objects.main_screen_nfc_scale_scale_label,
                lv_color_hex(0xFF00FF00), LV_PART_MAIN);
        } else {
            lv_label_set_text(objects.main_screen_nfc_scale_scale_label, "N/A");
            lv_obj_set_style_text_color(objects.main_screen_nfc_scale_scale_label,
                lv_color_hex(0xFFFF6600), LV_PART_MAIN);
        }
    }

    // NFC status always shows "Ready"
    if (objects.main_screen_nfc_scale_nfc_label) {
        lv_label_set_text(objects.main_screen_nfc_scale_nfc_label, "Ready");
    }
}
