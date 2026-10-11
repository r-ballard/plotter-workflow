"""Host-side serial cancellation and nonblocking terminal cancel keys."""

from __future__ import annotations

import logging
import os
import sys
import threading

LOG = logging.getLogger("dpx3300.sender")


class Cancellation:
    """A caller-owned cancellation token; safe to request from another thread."""

    def __init__(self) -> None:
        self.event = threading.Event()

    def request(self) -> None:
        self.event.set()


class TransmissionCancelled(Exception):
    def __init__(self, sent: int, total: int) -> None:
        self.sent, self.total = sent, total
        super().__init__(
            f"Transmission cancelled: {sent}/{total} bytes reported written by the serial driver. "
            "An in-flight write may have sent additional bytes; device receipt is not confirmed."
        )


def discard_and_close(connection) -> None:
    """Abort a write, purge host output, and release ownership even after a fault."""
    try:
        try:
            connection.cancel_write()
        except (AttributeError, NotImplementedError, OSError, ValueError) as error:
            LOG.debug("Write cancellation unavailable: %s", error)
        try:
            connection.reset_output_buffer()
        except (OSError, ValueError) as error:
            LOG.warning("Could not discard host serial output: %s", error)
    finally:
        try:
            connection.close()
        except (OSError, ValueError) as error:
            LOG.error("Could not close serial port; port release is unconfirmed: %s", error)


class CancelKeys:
    """Read Q/Escape without Enter on a terminal; restore POSIX terminal state."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled and sys.stdin.isatty()
        self.original = None
        self.fd = None

    def __enter__(self):
        if self.enabled and os.name != "nt":
            import termios
            import tty

            self.fd = sys.stdin.fileno()
            self.original = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self

    def requested(self) -> bool:
        if not self.enabled:
            return False
        if os.name == "nt":
            import msvcrt

            if not msvcrt.kbhit():
                return False
            key = msvcrt.getwch()
            if key in ("\x00", "\xe0"):
                msvcrt.getwch()  # Consume the extended scan code, not a literal key.
                return False
        else:
            import select

            if not select.select([self.fd], [], [], 0)[0]:
                return False
            # Avoid TextIOWrapper read-ahead buffering leaving later keys invisible to select.
            key = os.read(self.fd, 1).decode(errors="replace")
        return key.lower() == "q" or key in ("\x1b", "\x03")

    def __exit__(self, *args):
        if self.original is not None:
            import termios

            termios.tcsetattr(self.fd, termios.TCSANOW, self.original)
