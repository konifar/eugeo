// Copyright 2026 konifar
// SPDX-License-Identifier: GPL-2.0-or-later

#include "quantum.h"

// LED1 (red, PC4) = Caps Lock via keyboard.json indicators.
// LED2 (green, PC3) = any layer above the base layer is active.
#define LAYER_LED C3

void keyboard_pre_init_kb(void) {
    gpio_set_pin_output(LAYER_LED);
    gpio_write_pin_low(LAYER_LED);
    keyboard_pre_init_user();
}

layer_state_t layer_state_set_kb(layer_state_t state) {
    state = layer_state_set_user(state);
    gpio_write_pin(LAYER_LED, get_highest_layer(state) > 0);
    return state;
}
