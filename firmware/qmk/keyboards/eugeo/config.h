// Copyright 2026 konifar
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

// HC-49 crystals can take longer to start than the Pico's ABM8; give the XOSC more time.
#define PICO_XOSC_STARTUP_DELAY_MULTIPLIER 64
