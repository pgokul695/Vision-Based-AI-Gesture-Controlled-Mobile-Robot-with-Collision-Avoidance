/**
 * @file test_collision_filter.cpp
 * @brief Unit tests for collision filter safety arbitration rules.
 *
 * Verifies:
 * 1. Failsafe timeout (> 400 ms packet age) forces (0, 0).
 * 2. E-Stop flag bit forces (0, 0).
 * 3. Front IR obstacle suppresses forward linear drive.
 * 4. Front Ultrasonic obstacle triggers proportional speed slowdown and hard stop.
 * 5. Side IR obstacles prevent turning toward blocked direction.
 * 6. Rear IR obstacle suppresses reverse drive.
 * 7. Nominal clear conditions pass raw commanded velocities untouched.
 */

#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "motion_packet.h"
#include "motion/collision_filter.h"

static void test_clear_path_nominal() {
    printf("Running test_clear_path_nominal...\n");
    collision_filter_init(NULL);

    MotionPacket cmd = { MOTION_PACKET_MAGIC, MOTION_PACKET_VERSION, 1, 80, 40, 0, {0, 0, 0} };
    UltrasonicArrayReadings us = {
        { 100.0f, 1000, true },
        { 100.0f, 1000, true },
        { 100.0f, 1000, true }
    };
    IRReadings ir = { false, false, false, false, false, 1000 };
    SafeMotionOutput out;

    collision_filter_process(&cmd, 50, &us, &ir, 1000, &out);

    assert(out.linear == 80);
    assert(out.angular == 40);
    assert(!out.timeout_active);
    assert(!out.estop_active);
    assert(!out.front_blocked);
    printf("  PASSED\n");
}

static void test_failsafe_timeout() {
    printf("Running test_failsafe_timeout...\n");
    collision_filter_init(NULL);

    MotionPacket cmd = { MOTION_PACKET_MAGIC, MOTION_PACKET_VERSION, 2, 70, 20, 0, {0, 0, 0} };
    SafeMotionOutput out;

    // Packet age 401ms (> 400ms threshold)
    collision_filter_process(&cmd, 401, NULL, NULL, 1000, &out);

    assert(out.linear == 0);
    assert(out.angular == 0);
    assert(out.timeout_active);
    printf("  PASSED\n");
}

static void test_estop_flag() {
    printf("Running test_estop_flag...\n");
    collision_filter_init(NULL);

    MotionPacket cmd = {
        MOTION_PACKET_MAGIC,
        MOTION_PACKET_VERSION,
        3, 100, 50,
        MOTION_FLAG_ESTOP,
        {0, 0, 0}
    };
    SafeMotionOutput out;

    collision_filter_process(&cmd, 20, NULL, NULL, 1000, &out);

    assert(out.linear == 0);
    assert(out.angular == 0);
    assert(out.estop_active);
    printf("  PASSED\n");
}

static void test_front_ir_hard_stop() {
    printf("Running test_front_ir_hard_stop...\n");
    collision_filter_init(NULL);

    MotionPacket cmd = { MOTION_PACKET_MAGIC, MOTION_PACKET_VERSION, 4, 60, 0, 0, {0, 0, 0} };
    IRReadings ir = { true, false, false, false, false, 1000 }; // Front-left triggered
    SafeMotionOutput out;

    collision_filter_process(&cmd, 20, NULL, &ir, 1000, &out);

    assert(out.linear == 0);
    assert(out.front_blocked);

    // Reversing when front is blocked should still be allowed
    cmd.linear = -50;
    collision_filter_process(&cmd, 20, NULL, &ir, 1000, &out);
    assert(out.linear == -50);
    printf("  PASSED\n");
}

static void test_front_ultrasonic_slowdown_and_stop() {
    printf("Running test_front_ultrasonic_slowdown_and_stop...\n");
    collision_filter_init(NULL);

    MotionPacket cmd = { MOTION_PACKET_MAGIC, MOTION_PACKET_VERSION, 5, 100, 0, 0, {0, 0, 0} };
    UltrasonicArrayReadings us = {
        { 100.0f, 1000, true },
        { 27.5f, 1000, true }, // Center sensor midway between 15cm and 40cm
        { 100.0f, 1000, true }
    };
    SafeMotionOutput out;

    // Midway distance: scale = (27.5 - 15) / (40 - 15) = 12.5 / 25 = 0.5
    collision_filter_process(&cmd, 20, &us, NULL, 1000, &out);
    assert(out.linear == 50);
    assert(out.front_blocked);

    // Closer than 15cm -> complete stop
    us.center.distance_cm = 12.0f;
    collision_filter_process(&cmd, 20, &us, NULL, 1000, &out);
    assert(out.linear == 0);
    assert(out.front_blocked);
    printf("  PASSED\n");
}

static void test_side_and_rear_ir_gates() {
    printf("Running test_side_and_rear_ir_gates...\n");
    collision_filter_init(NULL);

    // Left turn commanded, side-left IR tripped -> angular must be zeroed
    MotionPacket cmd_left = { MOTION_PACKET_MAGIC, MOTION_PACKET_VERSION, 6, 0, -50, 0, {0, 0, 0} };
    IRReadings ir_left = { false, false, true, false, false, 1000 };
    SafeMotionOutput out;

    collision_filter_process(&cmd_left, 20, NULL, &ir_left, 1000, &out);
    assert(out.angular == 0);
    assert(out.side_left_blocked);

    // Right turn commanded, side-right IR tripped -> angular must be zeroed
    MotionPacket cmd_right = { MOTION_PACKET_MAGIC, MOTION_PACKET_VERSION, 7, 0, 50, 0, {0, 0, 0} };
    IRReadings ir_right = { false, false, false, true, false, 1000 };

    collision_filter_process(&cmd_right, 20, NULL, &ir_right, 1000, &out);
    assert(out.angular == 0);
    assert(out.side_right_blocked);

    // Reverse commanded, rear IR tripped -> reverse linear must be zeroed
    MotionPacket cmd_reverse = { MOTION_PACKET_MAGIC, MOTION_PACKET_VERSION, 8, -60, 0, 0, {0, 0, 0} };
    IRReadings ir_rear = { false, false, false, false, true, 1000 };

    collision_filter_process(&cmd_reverse, 20, NULL, &ir_rear, 1000, &out);
    assert(out.linear == 0);
    assert(out.rear_blocked);
    printf("  PASSED\n");
}

int main() {
    printf("=== Starting Collision Filter Test Suite ===\n");
    test_clear_path_nominal();
    test_failsafe_timeout();
    test_estop_flag();
    test_front_ir_hard_stop();
    test_front_ultrasonic_slowdown_and_stop();
    test_side_and_rear_ir_gates();
    printf("=== All Collision Filter Tests Passed! ===\n");
    return 0;
}
