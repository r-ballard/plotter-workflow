import logging
from argparse import Namespace
from types import SimpleNamespace

import pytest
import serial
import serial_session

from scripts import send_hpgl


class ProbeSerial:
    def __init__(self, *, failure=None):
        self.closed = False
        self.discarded = False
        self.failure = failure

    def reset_output_buffer(self):
        if self.failure:
            raise self.failure
        self.discarded = True

    def close(self):
        self.closed = True

    def write(self, data):
        pytest.fail("Recovery transmitted bytes")


def ports(monkeypatch):
    monkeypatch.setattr(
        serial_session.list_ports,
        "comports",
        lambda: (
            SimpleNamespace(device="COM4", description="FTDI", hwid="USB SERIAL=abcd"),
            SimpleNamespace(device="COM9", description="Other", hwid="USB SERIAL=other"),
        ),
    )


def test_recovery_rescans_opens_only_selected_port_and_sends_nothing(monkeypatch, caplog):
    ports(monkeypatch)
    opened = []
    connection = ProbeSerial()

    def open_port(**kwargs):
        opened.append(kwargs)
        return connection

    monkeypatch.setattr(serial_session.serial, "Serial", open_port)
    with caplog.at_level(logging.INFO):
        serial_session.recover_port("COM4")
    assert len(opened) == 1 and opened[0]["port"] == "COM4"
    assert opened[0]["baudrate"] == 9600 and opened[0]["xonxoff"] is True
    assert connection.discarded and connection.closed
    assert "No HP-GL sent" in caplog.text
    assert "buffer" in caplog.text


def test_missing_port_is_not_replaced_with_another_adapter(monkeypatch):
    ports(monkeypatch)
    monkeypatch.setattr(serial_session.serial, "Serial", lambda **kw: pytest.fail("opened"))
    with pytest.raises(ValueError, match="COM5.*not detected"):
        serial_session.recover_port("COM5")


def test_recovery_discard_error_still_closes_and_does_not_claim_success(monkeypatch, caplog):
    ports(monkeypatch)
    connection = ProbeSerial(failure=serial.SerialException("purge fault"))
    monkeypatch.setattr(serial_session.serial, "Serial", lambda **kw: connection)
    with caplog.at_level(logging.INFO), pytest.raises(serial.SerialException, match="purge fault"):
        serial_session.recover_port("COM4")
    assert connection.closed
    assert "reopened and released" not in caplog.text


def args(**updates):
    result = dict(recover_port="COM4", hpgl=None, port=None, list_ports=False, verbose=False)
    result.update(updates)
    return Namespace(**result)


def test_recovery_cli_bypasses_artwork_path_and_preflight_without_transmitting(monkeypatch):
    monkeypatch.setattr(send_hpgl, "parse_args", args)
    called = []
    monkeypatch.setattr(send_hpgl, "recover_port", lambda port: called.append(port))
    monkeypatch.setattr(send_hpgl, "send_file", lambda *a, **kw: pytest.fail("sent"))
    monkeypatch.setattr(send_hpgl, "run_job_preflight", lambda *a, **kw: pytest.fail("preflight"))
    assert send_hpgl.main() == 0
    assert called == ["COM4"]


@pytest.mark.parametrize(
    "updates", [dict(hpgl="drawing.hpgl"), dict(port="COM4"), dict(list_ports=True)]
)
def test_recovery_rejects_send_or_listing_arguments(monkeypatch, updates):
    monkeypatch.setattr(send_hpgl, "parse_args", lambda: args(**updates))
    monkeypatch.setattr(send_hpgl, "recover_port", lambda *a: pytest.fail("recovered"))
    assert send_hpgl.main() == 2


@pytest.mark.parametrize(
    "error,status", [(serial.SerialException("port busy"), 1), (KeyboardInterrupt(), 130)]
)
def test_recovery_cli_faults_have_nonzero_status(monkeypatch, error, status):
    monkeypatch.setattr(send_hpgl, "parse_args", args)

    def fail(port):
        raise error

    monkeypatch.setattr(send_hpgl, "recover_port", fail)
    assert send_hpgl.main() == status
