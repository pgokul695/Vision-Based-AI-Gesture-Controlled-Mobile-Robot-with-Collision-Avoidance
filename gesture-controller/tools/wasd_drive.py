#!/usr/bin/env python3
"""WASD Console Motor Test Tool.

Reads keyboard inputs via both terminal raw mode (Wayland & console compatible)
and pynput.keyboard.Listener to generate and transmit MotionPackets over UDP
to test the 4WD mobile robot drivetrain.
"""

import argparse
import select
import sys
import threading
import time
from pathlib import Path

# Add repository root and gesture-controller/src to Python path
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from network.udp_sender import UdpSender


def compute_motion_command(held_keys: set) -> tuple[int, int]:
    """Computes (linear, angular) from the current set of held keys.

    Held-key mappings:
      W -> linear = +80
      S -> linear = -80
      A -> angular = -60
      D -> angular = +60

    Combinations:
      W + D -> linear = +80, angular = +60
      Opposing keys cancel out (e.g. W + S -> 0, A + D -> 0)
      No relevant keys -> (0, 0)
    """
    linear = 0
    angular = 0

    has_w = 'w' in held_keys
    has_s = 's' in held_keys
    has_a = 'a' in held_keys
    has_d = 'd' in held_keys

    if has_w and not has_s:
        linear = 80
    elif has_s and not has_w:
        linear = -80

    if has_a and not has_d:
        angular = -60
    elif has_d and not has_a:
        angular = 60

    return linear, angular


class WasdController:
    """Manages keyboard event listener and ~20Hz UDP packet dispatch loop."""

    # Key repeat hold timeout: if no new key character arrives within 350ms,
    # the key is treated as released (for terminal auto-repeat input under Wayland/Linux).
    HOLD_TIMEOUT_SEC = 0.35

    def __init__(self, host: str = "127.0.0.1", port: int = 5005, rate_hz: float = 20.0):
        self.host = host
        self.port = port
        self.rate_hz = rate_hz
        self.interval = 1.0 / rate_hz
        self.held_keys: set[str] = set()
        self.key_timestamps: dict[str, float] = {}
        self.running: bool = True
        self.lock = threading.Lock()
        self.sender = UdpSender(host=host, port=port)
        self._old_termios = None

    def register_key_down(self, char: str):
        """Records a key press and updates its liveness timestamp."""
        c = char.lower()
        now = time.time()
        with self.lock:
            if c in ('w', 'a', 's', 'd'):
                self.held_keys.add(c)
                self.key_timestamps[c] = now
            elif c == ' ':  # Space: emergency stop / release all
                self.held_keys.clear()
                self.key_timestamps.clear()
            elif c == 'q':
                self.running = False

    def register_key_up(self, char: str):
        """Records an explicit key release (from pynput if available)."""
        c = char.lower()
        with self.lock:
            self.held_keys.discard(c)
            self.key_timestamps.pop(c, None)

    def prune_stale_keys(self):
        """Releases keys whose repeat events have stopped exceeding the hold timeout."""
        now = time.time()
        with self.lock:
            expired = [k for k, ts in self.key_timestamps.items() if now - ts > self.HOLD_TIMEOUT_SEC]
            for k in expired:
                self.held_keys.discard(k)
                del self.key_timestamps[k]

    def on_press(self, key):
        """pynput callback on key press."""
        from pynput import keyboard

        try:
            if hasattr(key, 'char') and key.char:
                self.register_key_down(key.char)
        except AttributeError:
            pass

        if key == keyboard.Key.esc:
            self.running = False
            return False

    def on_release(self, key):
        """pynput callback on key release."""
        try:
            if hasattr(key, 'char') and key.char:
                self.register_key_up(key.char)
        except AttributeError:
            pass

    def _terminal_input_thread(self):
        """Reads stdin in raw non-blocking mode to support native Wayland terminals."""
        while self.running:
            try:
                r, _, _ = select.select([sys.stdin], [], [], 0.05)
                if r:
                    ch = sys.stdin.read(1)
                    if not ch:
                        continue
                    if ch in ('\x1b', 'q', 'Q', '\x03'):  # Esc, q, Ctrl+C
                        self.running = False
                        break
                    self.register_key_down(ch)
            except Exception:
                break

    def run(self):
        """Runs keyboard listeners and ~20Hz packet transmission loop."""
        self.sender.start()
        print("============================================================")
        print("  WASD Console Motor Controller (Dual Parallel L298N)")
        print(f"  Target: {self.host}:{self.port} at {self.rate_hz:.1f} Hz (~{int(self.interval*1000)}ms interval)")
        print("------------------------------------------------------------")
        print("  Controls (Hold to drive, release to stop):")
        print("    [W]       : Forward  (+80% lin)")
        print("    [S]       : Reverse  (-80% lin)")
        print("    [A]       : Turn L   (-60% ang)")
        print("    [D]       : Turn R   (+60% ang)")
        print("    [W+D]/etc : Arc turn (+80% lin, +60% ang)")
        print("    [Space]   : Immediate Stop")
        print("    Release   : Coast / Stop (0, 0)")
        print("    [Q] / Esc : Send final zero packet & Exit cleanly")
        print("============================================================\n")

        # 1. Start pynput listener (works on X11 / evdev)
        pynput_listener = None
        try:
            from pynput import keyboard
            pynput_listener = keyboard.Listener(
                on_press=self.on_press,
                on_release=self.on_release,
            )
            pynput_listener.start()
        except Exception as e:
            pass

        # 2. Set up raw terminal stdin reader (guaranteed to capture keys in Wayland terminals)
        term_thread = None
        if sys.stdin.isatty():
            try:
                import termios
                self._old_termios = termios.tcgetattr(sys.stdin)
                new_settings = termios.tcgetattr(sys.stdin)
                # Disable canonical mode and echo so keys are received immediately without Enter
                new_settings[3] = new_settings[3] & ~termios.ECHO & ~termios.ICANON
                new_settings[6][termios.VMIN] = 0
                new_settings[6][termios.VTIME] = 0
                termios.tcsetattr(sys.stdin, termios.TCSANOW, new_settings)

                term_thread = threading.Thread(target=self._terminal_input_thread, daemon=True)
                term_thread.start()
            except Exception:
                pass

        try:
            while self.running:
                loop_start = time.perf_counter()

                # Prune keys that are no longer being held
                self.prune_stale_keys()

                with self.lock:
                    current_held = set(self.held_keys)

                linear, angular = compute_motion_command(current_held)
                self.sender.send(linear=linear, angular=angular)

                held_display = "".join(sorted(k.upper() for k in current_held)) or "NONE"
                print(
                    f"\r[WASD] Held: [{held_display:4s}] | Lin: {linear:+4d}% | Ang: {angular:+4d}% | Target: {self.host}:{self.port}   ",
                    end="",
                    flush=True,
                )

                elapsed = time.perf_counter() - loop_start
                sleep_time = self.interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n[WASD] Interrupted by user (Ctrl+C).")
        finally:
            print("\n[WASD] Shutting down... Sending stop command.")
            self.running = False

            # Restore terminal settings
            if self._old_termios and sys.stdin.isatty():
                try:
                    import termios
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_termios)
                except Exception:
                    pass

            if pynput_listener:
                try:
                    pynput_listener.stop()
                except Exception:
                    pass

            try:
                # Send zero packet multiple times to prevent packet loss
                for _ in range(3):
                    self.sender.send(linear=0, angular=0)
                    time.sleep(0.01)
            except Exception as err:
                print(f"[WARN] Error dispatching final stop packet: {err}")
            finally:
                self.sender.close()
            print("[WASD] Motors halted. UDP socket closed.")


def main():
    parser = argparse.ArgumentParser(description="WASD Console Motor Driver Tool for ESP32 Robot")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Target ESP32 IP address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5005, help="Target UDP port (default: 5005)")
    parser.add_argument("--rate", type=float, default=20.0, help="Transmission rate in Hz (default: 20.0)")
    args = parser.parse_args()

    controller = WasdController(host=args.host, port=args.port, rate_hz=args.rate)
    controller.run()


if __name__ == "__main__":
    main()
