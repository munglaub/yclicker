import asyncio
import os
import secrets
import socket
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal


class WaylandInput:
    def __init__(self):
        try:
            from evdev import UInput, ecodes
        except ImportError as error:
            raise RuntimeError("Wayland input requires the Python package evdev.") from error

        self.ecodes = ecodes
        try:
            self.device = UInput(
                {
                    ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.KEY_R],
                },
                name="yclicker",
            )
        except OSError as error:
            raise RuntimeError(
                "Wayland input could not open /dev/uinput. "
                "Check that the uinput kernel module is loaded and your user has access to it."
            ) from error

    def click_left(self):
        self.device.write(self.ecodes.EV_KEY, self.ecodes.BTN_LEFT, 1)
        self.device.syn()
        self.device.write(self.ecodes.EV_KEY, self.ecodes.BTN_LEFT, 0)
        self.device.syn()

    def press_r(self):
        self.device.write(self.ecodes.EV_KEY, self.ecodes.KEY_R, 1)
        self.device.syn()
        self.device.write(self.ecodes.EV_KEY, self.ecodes.KEY_R, 0)
        self.device.syn()

    def close(self):
        self.device.close()


class GlobalShortcutPortal(QObject):
    toggle_requested = Signal()
    status_changed = Signal(str)

    service = "org.freedesktop.portal.Desktop"
    portal_path = "/org/freedesktop/portal/desktop"
    shortcuts_interface = "org.freedesktop.portal.GlobalShortcuts"
    registry_interface = "org.freedesktop.host.portal.Registry"
    request_interface = "org.freedesktop.portal.Request"
    session_interface = "org.freedesktop.portal.Session"
    application_id = "yclicker"

    def __init__(self):
        super().__init__()
        self._loop = None
        self._stop_event = None
        self._session = None
        self._bus = None
        self._stop_requested = False

    def start(self):
        threading.Thread(target=self._run, daemon=True, name="yclicker-shortcut").start()

    def stop(self):
        self._stop_requested = True
        if (
            self._loop is not None
            and not self._loop.is_closed()
            and self._stop_event is not None
        ):
            self._loop.call_soon_threadsafe(self._stop_event.set)

    def _run(self):
        try:
            asyncio.run(self._run_portal())
        except Exception:
            self.status_changed.emit("Error")
        finally:
            if self._bus is not None:
                self._bus.disconnect()
                self._bus = None

    async def _run_portal(self):
        from dbus_next import Variant
        from dbus_next.aio import MessageBus
        from dbus_next.constants import BusType

        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        if self._stop_requested:
            self._stop_event.set()
        self._pending_requests = {}
        self._bus = await MessageBus(bus_type=BusType.SESSION).connect()
        self._bus.add_message_handler(self._handle_message)

        await self._register_application()

        token = secrets.token_hex(8)
        session_handle = await self._create_session(token)
        if not session_handle:
            raise RuntimeError("The portal did not create a shortcut session.")
        self._session = session_handle.value if hasattr(session_handle, "value") else session_handle

        token = secrets.token_hex(8)
        bind_path, results = await self._request(
            "BindShortcuts",
            self._session,
            [
                [
                    "toggle",
                    {
                        "description": Variant("s", "Start or stop yclicker"),
                        "preferred_trigger": Variant("s", "F8"),
                    },
                ]
            ],
            "",
            {"handle_token": Variant("s", token)},
            signature="oa(sa{sv})sa{sv}",
        )
        if bind_path is None:
            raise RuntimeError("The portal did not confirm the F8 shortcut.")

        self._trigger_description(results)
        self.status_changed.emit("Wayland")
        try:
            await self._stop_event.wait()
        finally:
            await self._close_session()

    async def _register_application(self):
        from dbus_next import Message
        from dbus_next.constants import MessageType

        msg = Message(
            destination=self.service,
            path=self.portal_path,
            interface=self.registry_interface,
            member="Register",
            signature="sa{sv}",
            body=[self.application_id, {}],
        )
        reply = await self._bus.call(msg)
        if getattr(reply, "message_type", None) != MessageType.ERROR:
            return

        error_name = getattr(reply, "error_name", "org.freedesktop.DBus.Error.Failed")
        error_message = reply.body[0] if reply.body else ""
        if "Connection already associated with an application ID" in error_message:
            return
        raise RuntimeError(f"Portal app ID registration failed: {error_name}: {error_message}")

    async def _create_session(self, token):
        from dbus_next import Variant

        _, results = await self._request(
            "CreateSession",
            {
                "handle_token": Variant("s", token),
                "session_handle_token": Variant("s", f"session_{token}"),
            },
            signature="a{sv}",
        )
        session_handle = results.get("session_handle")
        if session_handle is None:
            raise RuntimeError("The portal did not return a shortcut session.")
        return session_handle

    @staticmethod
    def _trigger_description(results):
        shortcuts = results.get("shortcuts")
        if shortcuts is not None:
            shortcuts = shortcuts.value
        for shortcut_id, options in shortcuts or []:
            if shortcut_id == "toggle":
                trigger = options.get("trigger_description")
                if trigger is not None:
                    return trigger.value
        raise RuntimeError("The portal did not bind a global shortcut for yclicker.")

    async def _request(self, method_name, *arguments, signature=None):
        from dbus_next import Message
        from dbus_next.constants import MessageType

        request_token = arguments[-1]["handle_token"].value
        sender = self._bus.unique_name.lstrip(":").replace(".", "_") if self._bus.unique_name else "self"
        request_path = f"/org/freedesktop/portal/desktop/request/{sender}/{request_token}"
        future = self._loop.create_future()
        self._pending_requests[request_path] = future

        msg = Message(
            destination=self.service,
            path=self.portal_path,
            interface=self.shortcuts_interface,
            member=method_name,
            signature=signature,
            body=list(arguments),
        )
        reply = await self._bus.call(msg)
        if getattr(reply, "message_type", None) == MessageType.ERROR:
            error_name = getattr(reply, "error_name", "org.freedesktop.DBus.Error.Failed")
            raise RuntimeError(f"Portal-Fehler bei {method_name}: {error_name}")
        if not reply.body:
            return None, {}
        returned_path = reply.body[0]
        if returned_path != request_path:
            self._pending_requests[returned_path] = future

        response, results = await asyncio.wait_for(future, timeout=90)
        if response != 0:
            return None, results
        return returned_path, results

    async def _close_session(self):
        if not self._session:
            return
        from dbus_next import Message

        msg = Message(
            destination=self.service,
            path=self._session,
            interface=self.session_interface,
            member="Close",
            signature="",
            body=[],
        )
        try:
            await self._bus.call(msg)
        except Exception:
            pass

    def _handle_message(self, message):
        from dbus_next import MessageType

        if (
            message.message_type == MessageType.SIGNAL
            and message.interface == self.request_interface
            and message.member == "Response"
        ):
            future = self._pending_requests.pop(message.path, None)
            if future is not None and not future.done():
                future.set_result((message.body[0], message.body[1]))

        if (
            message.message_type == MessageType.SIGNAL
            and message.interface == self.shortcuts_interface
            and message.member == "Activated"
        ):
            session_handle, shortcut_id, timestamp, options = message.body
            if shortcut_id == "toggle":
                self.toggle_requested.emit()


def _socket_path():
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime_dir:
        raise RuntimeError("XDG_RUNTIME_DIR is not set; the F8 shortcut fallback is unavailable.")
    return Path(runtime_dir) / f"yclicker-{os.getuid()}.sock"


def request_running_toggle():
    try:
        path = _socket_path()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(1)
            client.connect(str(path))
            client.sendall(b"toggle\n")
        return True
    except (OSError, RuntimeError):
        return False


class ToggleIpcServer:
    def __init__(self, callback):
        self.path = _socket_path()
        self.callback = callback
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.thread = None

    def start(self):
        try:
            self.server.bind(str(self.path))
        except OSError:
            self.server.close()
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                probe.connect(str(self.path))
            except OSError:
                try:
                    self.path.unlink()
                except FileNotFoundError:
                    pass
                self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    self.server.bind(str(self.path))
                except OSError as error:
                    self.server.close()
                    raise RuntimeError("Could not create the F8 fallback socket.") from error
            else:
                raise RuntimeError(
                    "Could not start the yclicker F8 fallback. "
                    "Check whether another instance is already running."
                )
            finally:
                probe.close()
        os.chmod(self.path, 0o600)
        self.server.listen(4)
        self.server.settimeout(0.5)
        self.thread = threading.Thread(target=self._serve, daemon=True, name="yclicker-toggle-ipc")
        self.thread.start()

    def _serve(self):
        while self.server.fileno() >= 0:
            try:
                connection, _ = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with connection:
                if connection.recv(32).strip() == b"toggle":
                    self.callback()

    def close(self):
        self.server.close()
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass