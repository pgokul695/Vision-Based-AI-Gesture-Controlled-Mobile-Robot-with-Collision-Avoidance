/**
 * @file trick_sequencer.h
 * @brief Fun trick sequencer executing canned motion sequences safely.
 */

#ifndef TRICK_SEQUENCER_H
#define TRICK_SEQUENCER_H

#include <stdint.h>
#include <stdbool.h>
#include "motion/collision_filter.h"

#ifdef __cplusplus
extern "C" {
#endif

#define TRICK_DURATION_MS   1500  // 1.5 second canned spin
#define TRICK_SPIN_LINEAR   0
#define TRICK_SPIN_ANGULAR  80

/**
 * @brief Initializes the trick sequencer.
 */
void trick_sequencer_init(void);

/**
 * @brief Triggers the fun trick sequence.
 * @param now_ms System time in milliseconds.
 */
void trick_sequencer_trigger(uint32_t now_ms);

/**
 * @brief Immediately aborts an active trick (e.g. on E-STOP).
 */
void trick_sequencer_abort(void);

/**
 * @brief Updates trick countdown timer. Called on every control loop cycle.
 * @param now_ms System time in milliseconds.
 */
void trick_sequencer_update(uint32_t now_ms);

/**
 * @brief Checks if a trick is currently active.
 */
bool isTrickActive(void);
bool trick_sequencer_is_active(void);

/**
 * @brief Retrieves the canned MotionCommand to dispatch while trick is active.
 */
MotionCommand trick_sequencer_get_command(void);

#ifdef __cplusplus
}
#endif

#endif // TRICK_SEQUENCER_H
