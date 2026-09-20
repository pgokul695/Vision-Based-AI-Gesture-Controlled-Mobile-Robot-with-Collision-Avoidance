/**
 * @file trick_sequencer.cpp
 * @brief Fun trick sequencer implementation.
 */

#include "motion/trick_sequencer.h"

static bool g_trick_active = false;
static uint32_t g_trick_start_ms = 0;

void trick_sequencer_init(void) {
    g_trick_active = false;
    g_trick_start_ms = 0;
}

void trick_sequencer_trigger(uint32_t now_ms) {
    if (!g_trick_active) {
        g_trick_active = true;
        g_trick_start_ms = now_ms;
    }
}

void trick_sequencer_abort(void) {
    g_trick_active = false;
}

void trick_sequencer_update(uint32_t now_ms) {
    if (g_trick_active) {
        if (now_ms - g_trick_start_ms >= TRICK_DURATION_MS) {
            g_trick_active = false;
        }
    }
}

bool isTrickActive(void) {
    return g_trick_active;
}

bool trick_sequencer_is_active(void) {
    return g_trick_active;
}

MotionCommand trick_sequencer_get_command(void) {
    MotionCommand cmd;
    cmd.linear = TRICK_SPIN_LINEAR;
    cmd.angular = TRICK_SPIN_ANGULAR;
    return cmd;
}
