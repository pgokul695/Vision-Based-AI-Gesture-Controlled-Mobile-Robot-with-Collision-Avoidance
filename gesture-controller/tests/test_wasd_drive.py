"""Unit tests for WASD console drive tool."""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure repo root and gesture-controller/tools are in sys.path
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

tools_dir = Path(__file__).resolve().parent.parent / "tools"
if str(tools_dir) not in sys.path:
    sys.path.insert(0, str(tools_dir))

from wasd_drive import compute_motion_command, WasdController


def test_compute_motion_command_neutral():
    """Empty or irrelevant keys must yield (0, 0)."""
    assert compute_motion_command(set()) == (0, 0)
    assert compute_motion_command({'x', 'z', 'shift'}) == (0, 0)


def test_compute_motion_command_cardinal():
    """Test standard single-key driving."""
    assert compute_motion_command({'w'}) == (80, 0)
    assert compute_motion_command({'s'}) == (-80, 0)
    assert compute_motion_command({'a'}) == (0, -60)
    assert compute_motion_command({'d'}) == (0, 60)


def test_compute_motion_command_chords():
    """Test multi-key combinations for smooth arcing turns."""
    assert compute_motion_command({'w', 'd'}) == (80, 60)
    assert compute_motion_command({'w', 'a'}) == (80, -60)
    assert compute_motion_command({'s', 'd'}) == (-80, 60)
    assert compute_motion_command({'s', 'a'}) == (-80, -60)


def test_compute_motion_command_opposing_keys_cancel():
    """Opposing directions held simultaneously should cancel cleanly to zero."""
    assert compute_motion_command({'w', 's'}) == (0, 0)
    assert compute_motion_command({'a', 'd'}) == (0, 0)
    assert compute_motion_command({'w', 's', 'd'}) == (0, 60)
    assert compute_motion_command({'w', 'a', 'd'}) == (80, 0)
    assert compute_motion_command({'w', 's', 'a', 'd'}) == (0, 0)


def test_wasd_controller_key_callbacks():
    """Test key press and release state management in WasdController."""
    controller = WasdController(host="127.0.0.1", port=5005, rate_hz=20.0)

    class DummyKey:
        def __init__(self, char):
            self.char = char

    # Press 'W' and 'D'
    controller.on_press(DummyKey('w'))
    assert controller.held_keys == {'w'}
    controller.on_press(DummyKey('d'))
    assert controller.held_keys == {'w', 'd'}

    # Release 'W'
    controller.on_release(DummyKey('w'))
    assert controller.held_keys == {'d'}

    # Press 'Q' to quit
    assert controller.running is True
    controller.on_press(DummyKey('q'))
    assert controller.running is False


def test_wasd_controller_terminal_raw_mode_and_prune():
    """Test terminal raw mode character inputs and timeout auto-release."""
    controller = WasdController(host="127.0.0.1", port=5005, rate_hz=20.0)

    # Key down via terminal char
    controller.register_key_down('w')
    assert 'w' in controller.held_keys

    # Simulate time passing beyond hold timeout
    controller.key_timestamps['w'] = time.time() - 0.5
    controller.prune_stale_keys()
    assert 'w' not in controller.held_keys

    # Space key immediate stop
    controller.register_key_down('w')
    controller.register_key_down('d')
    assert controller.held_keys == {'w', 'd'}
    controller.register_key_down(' ')
    assert len(controller.held_keys) == 0


def test_wasd_controller_send_packet():
    """Test UDP transmission through WasdController."""
    with patch("wasd_drive.UdpSender") as mock_sender_cls:
        mock_sender = MagicMock()
        mock_sender_cls.return_value = mock_sender

        controller = WasdController(host="127.0.0.1", port=5005, rate_hz=20.0)
        controller.sender = mock_sender

        class DummyKey:
            def __init__(self, char):
                self.char = char

        controller.on_press(DummyKey('w'))
        linear, angular = compute_motion_command(controller.held_keys)
        controller.sender.send(linear=linear, angular=angular)

        mock_sender.send.assert_called_with(linear=80, angular=0)
