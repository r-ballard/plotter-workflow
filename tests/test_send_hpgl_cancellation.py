import logging
import threading
import time
from argparse import Namespace
from types import SimpleNamespace

import pytest
import serial

from scripts import send_hpgl


class FakeSerial:
    def __init__(self, block="write", *, failure=None, support_cancel=True):
        self.block = block
        self.failure = failure
        self.support_cancel = support_cancel
        self.entered = threading.Event()
        self.release = threading.Event()
        self.closed = threading.Event()
        self.calls = []

    def reset_output_buffer(self):
        self.calls.append("discard")

    def write(self, chunk):
        self.calls.append("write")
        if self.failure:
            raise self.failure
        if self.block == "write":
            self.entered.set()
            assert self.release.wait(2), "test write was not cancelled"
            return 0
        return min(2, len(chunk))

    def flush(self):
        self.calls.append("flush")
        if self.block == "flush":
            self.entered.set()
            assert self.release.wait(2), "test drain was not cancelled"

    def cancel_write(self):
        self.calls.append("cancel")
        if not self.support_cancel:
            raise NotImplementedError
        self.release.set()

    def close(self):
        self.calls.append("close")
        self.release.set()
        self.closed.set()


@pytest.fixture
def hpgl(tmp_path):
    p = tmp_path / "plot.hpgl"
    p.write_bytes(b"IN;SP1;PU0,0;PD10,10;PU;")
    return p


@pytest.mark.parametrize("phase", ["write", "flush", "delay"])
def test_cancellation_releases_port_discards_queue_and_never_completes(
    monkeypatch,
    hpgl,
    caplog,
    phase,
):
    cancellation = send_hpgl.Cancellation()
    connection = FakeSerial(phase)
    monkeypatch.setattr(send_hpgl.serial, "Serial", lambda **kw: connection)

    def cancel():
        if phase == "delay":
            while "write" not in connection.calls:
                time.sleep(0.001)
        else:
            assert connection.entered.wait(1)
        cancellation.request()

    requester = threading.Thread(target=cancel)
    requester.start()
    start = time.monotonic()
    with caplog.at_level(logging.INFO), pytest.raises(send_hpgl.TransmissionCancelled) as exc:
        send_hpgl.send_file(
            "COM4",
            hpgl,
            chunk_size=4,
            inter_chunk_delay=30 if phase == "delay" else 0,
            cancellation=cancellation,
            interactive=False,
        )
    requester.join(1)
    assert time.monotonic() - start < 1
    assert connection.closed.is_set()
    assert connection.calls.index("cancel") < connection.calls.index("close")
    assert connection.calls.count("discard") >= 2
    assert exc.value.total == hpgl.stat().st_size
    assert 0 <= exc.value.sent <= exc.value.total
    assert "Transmission complete" not in caplog.text


def test_short_writes_are_retried_and_progress_is_truthful(monkeypatch, hpgl, caplog):
    connection = FakeSerial(None)
    monkeypatch.setattr(send_hpgl.serial, "Serial", lambda **kw: connection)
    with caplog.at_level(logging.INFO):
        send_hpgl.send_file("COM4", hpgl, chunk_size=4, interactive=False)
    assert connection.closed.is_set()
    assert connection.calls.count("write") > hpgl.stat().st_size / 4
    assert f"Transmission complete: {hpgl.stat().st_size} bytes" in caplog.text


def test_unsupported_cancel_write_falls_back_to_close(monkeypatch, hpgl):
    connection = FakeSerial("write", support_cancel=False)
    monkeypatch.setattr(send_hpgl.serial, "Serial", lambda **kw: connection)
    ctrl = send_hpgl.Cancellation()
    timer = threading.Timer(0.05, ctrl.request)
    timer.start()
    with pytest.raises(send_hpgl.TransmissionCancelled):
        send_hpgl.send_file("COM4", hpgl, cancellation=ctrl, interactive=False)
    timer.join()
    assert connection.closed.is_set()


def test_write_errors_close_and_discard(monkeypatch, hpgl):
    connection = FakeSerial(None, failure=serial.SerialException("fault"))
    monkeypatch.setattr(send_hpgl.serial, "Serial", lambda **kw: connection)
    with pytest.raises(serial.SerialException, match="fault"):
        send_hpgl.send_file("COM4", hpgl, interactive=False)
    assert connection.closed.is_set()
    assert connection.calls.count("discard") >= 2


def test_pre_cancelled_sender_never_opens_port(monkeypatch, hpgl):
    ctrl = send_hpgl.Cancellation()
    ctrl.request()
    monkeypatch.setattr(send_hpgl.serial, "Serial", lambda **kw: pytest.fail("port opened"))
    with pytest.raises(send_hpgl.TransmissionCancelled):
        send_hpgl.send_file("COM4", hpgl, cancellation=ctrl, interactive=False)


def test_main_cancellation_returns_130_and_does_not_log_success(monkeypatch, hpgl, caplog):
    monkeypatch.setattr(
        send_hpgl,
        "parse_args",
        lambda: Namespace(
            list_ports=False,
            port="COM4",
            hpgl=hpgl,
            chunk_size=4,
            inter_chunk_delay=0,
            allow_unvalidated_job=True,
            pen_plan=None,
            allow_unplanned_multipen=False,
            confirm_pen_plan=False,
            verbose=False,
        ),
    )

    def cancelled(*args, **kwargs):
        raise send_hpgl.TransmissionCancelled(4, hpgl.stat().st_size)

    monkeypatch.setattr(send_hpgl, "send_file", cancelled)
    with caplog.at_level(logging.INFO):
        assert send_hpgl.main() == 130
    assert "4/" in caplog.text
    assert "Transmission complete" not in caplog.text


@pytest.mark.parametrize("key", ["q", "Q", "\x1b", "ctrl+c"])
def test_operator_keys_and_ctrl_c_cancel_blocked_write(monkeypatch, hpgl, key):
    connection = FakeSerial("write")
    monkeypatch.setattr(send_hpgl.serial, "Serial", lambda **kw: connection)

    def requested(self):
        if not connection.entered.is_set():
            return False
        if key == "ctrl+c":
            raise KeyboardInterrupt
        return key.lower() == "q" or key == "\x1b"

    monkeypatch.setattr(send_hpgl.CancelKeys, "requested", requested)
    with pytest.raises(send_hpgl.TransmissionCancelled):
        send_hpgl.send_file("COM4", hpgl)
    assert connection.closed.is_set()


def test_cleanup_failure_does_not_hide_cancellation(monkeypatch, hpgl, caplog):
    connection = FakeSerial("write")

    def bad_close():
        connection.release.set()
        raise serial.SerialException("close failed")

    connection.close = bad_close
    monkeypatch.setattr(send_hpgl.serial, "Serial", lambda **kw: connection)
    ctrl = send_hpgl.Cancellation()
    timer = threading.Timer(0.05, ctrl.request)
    timer.start()
    with caplog.at_level(logging.WARNING), pytest.raises(send_hpgl.TransmissionCancelled):
        send_hpgl.send_file("COM4", hpgl, cancellation=ctrl, interactive=False)
    timer.join()
    assert "close failed" in caplog.text


def test_queued_cancel_key_prevents_fast_transmission(monkeypatch, hpgl, caplog):
    connection = FakeSerial(None)
    monkeypatch.setattr(send_hpgl.serial, "Serial", lambda **kw: connection)
    monkeypatch.setattr(send_hpgl.CancelKeys, "requested", lambda self: True)
    with caplog.at_level(logging.INFO), pytest.raises(send_hpgl.TransmissionCancelled):
        send_hpgl.send_file("COM4", hpgl)
    assert "write" not in connection.calls
    assert "Transmission complete" not in caplog.text


def test_cancellation_during_close_still_exits_cancelled(monkeypatch, hpgl, caplog):
    connection = FakeSerial(None)
    ctrl = send_hpgl.Cancellation()
    close = connection.close

    def request_on_close():
        ctrl.request()
        close()

    connection.close = request_on_close
    monkeypatch.setattr(send_hpgl.serial, "Serial", lambda **kw: connection)
    with caplog.at_level(logging.INFO), pytest.raises(send_hpgl.TransmissionCancelled):
        send_hpgl.send_file("COM4", hpgl, cancellation=ctrl, interactive=False)
    assert "Transmission complete" not in caplog.text


def test_windows_extended_key_scan_codes_are_not_literal_cancel_keys(monkeypatch):
    import sys

    import serial_session

    keys = iter(("\xe0", "Q", "q", "\x1b"))
    read = []

    def getwch():
        key = next(keys)
        read.append(key)
        return key

    monkeypatch.setattr(serial_session, "os", SimpleNamespace(name="nt"))
    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(kbhit=lambda: True, getwch=getwch))
    handler = serial_session.CancelKeys(False)
    handler.enabled = True
    assert handler.requested() is False  # Page Down's Q scan code is consumed.
    assert read == ["\xe0", "Q"]
    assert handler.requested() is True  # Literal q.
    assert handler.requested() is True  # Literal Escape.
