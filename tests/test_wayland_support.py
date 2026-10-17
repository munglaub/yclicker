import asyncio
import os
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

from dbus_next import Message, MessageType, Variant

from wayland_support import (
    GlobalShortcutPortal,
    ToggleIpcServer,
    WaylandInput,
    request_running_toggle,
)


class WaylandInputTests(unittest.TestCase):
    def test_sends_mouse_and_keyboard_events(self):
        writes = []
        syncs = []

        class FakeUInput:
            def __init__(self, events, name):
                self.events = events
                self.name = name

            def write(self, event_type, code, value):
                writes.append((event_type, code, value))

            def syn(self):
                syncs.append(True)

            def close(self):
                pass

        ecodes = types.SimpleNamespace(EV_KEY=1, BTN_LEFT=272, KEY_R=19)
        fake_evdev = types.ModuleType("evdev")
        fake_evdev.UInput = FakeUInput
        fake_evdev.ecodes = ecodes

        with patch.dict("sys.modules", {"evdev": fake_evdev}):
            backend = WaylandInput()
            backend.click_left()
            backend.press_r()

        self.assertEqual(
            writes,
            [(1, 272, 1), (1, 272, 0), (1, 19, 1), (1, 19, 0)],
        )
        self.assertEqual(len(syncs), 4)


class GlobalShortcutPortalTests(unittest.TestCase):
    def test_registers_host_application_id_with_portal(self):
        portal = GlobalShortcutPortal()
        messages = []

        class FakeBus:
            async def call(self, message):
                messages.append(message)
                return types.SimpleNamespace(message_type=MessageType.METHOD_RETURN)

        portal._bus = FakeBus()

        asyncio.run(portal._register_application())

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].interface, "org.freedesktop.host.portal.Registry")
        self.assertEqual(messages[0].member, "Register")
        self.assertEqual(messages[0].signature, "sa{sv}")
        self.assertEqual(messages[0].body, ["yclicker", {}])

    def test_stop_after_worker_loop_closed_is_safe(self):
        portal = GlobalShortcutPortal()
        portal._loop = asyncio.new_event_loop()
        portal._loop.close()
        portal._stop_event = asyncio.Event()

        portal.stop()

        self.assertTrue(portal._stop_requested)

    def test_bind_shortcuts_arguments_match_dbus_signature(self):
        Message(
            destination="org.freedesktop.portal.Desktop",
            path="/org/freedesktop/portal/desktop",
            interface="org.freedesktop.portal.GlobalShortcuts",
            member="BindShortcuts",
            signature="oa(sa{sv})sa{sv}",
            body=[
                "/org/freedesktop/portal/desktop/session/test/session_test",
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
                {"handle_token": Variant("s", "test_token")},
            ],
        )

    def test_reports_portal_bound_trigger(self):
        result = GlobalShortcutPortal._trigger_description(
            {
                "shortcuts": Variant(
                    "a(sa{sv})",
                    [["toggle", {"trigger_description": Variant("s", "F8")}]],
                )
            }
        )

        self.assertEqual(result, "F8")

    def test_matches_portal_response_to_request_path(self):
        portal = GlobalShortcutPortal()
        portal._loop = asyncio.new_event_loop()
        request_path = "/org/freedesktop/portal/desktop/request/1_42/test_token"

        class FakeBus:
            unique_name = ":1.42"

            async def call(self, message):
                self.assert_message = message
                portal._handle_message(
                    types.SimpleNamespace(
                        message_type=MessageType.SIGNAL,
                        interface=portal.request_interface,
                        member="Response",
                        path=request_path,
                        body=[0, {"session_handle": "session-path"}],
                    )
                )
                return types.SimpleNamespace(body=[request_path])

        portal._bus = FakeBus()
        portal._pending_requests = {}

        try:
            result = portal._loop.run_until_complete(
                portal._request(
                    "CreateSession",
                    {"handle_token": Variant("s", "test_token")},
                    signature="a{sv}",
                )
            )
        finally:
            portal._loop.close()

        self.assertEqual(result, (request_path, {"session_handle": "session-path"}))
        self.assertEqual(portal._bus.assert_message.member, "CreateSession")

    def test_cancelled_portal_request_is_not_success(self):
        portal = GlobalShortcutPortal()
        portal._loop = asyncio.new_event_loop()
        request_path = "/org/freedesktop/portal/desktop/request/1_42/cancel_token"

        class FakeBus:
            unique_name = ":1.42"

            async def call(self, message):
                portal._handle_message(
                    types.SimpleNamespace(
                        message_type=MessageType.SIGNAL,
                        interface=portal.request_interface,
                        member="Response",
                        path=request_path,
                        body=[1, {}],
                    )
                )
                return types.SimpleNamespace(body=[request_path])

        portal._bus = FakeBus()
        portal._pending_requests = {}

        try:
            result = portal._loop.run_until_complete(
                portal._request(
                    "CreateSession",
                    {"handle_token": Variant("s", "cancel_token")},
                    signature="a{sv}",
                )
            )
        finally:
            portal._loop.close()

        self.assertEqual(result, (None, {}))

    def test_activated_f8_requests_toggle(self):
        portal = GlobalShortcutPortal()
        toggles = []
        portal.toggle_requested.connect(lambda: toggles.append(True))

        for shortcut_id in ("toggle", "other"):
            portal._handle_message(
                types.SimpleNamespace(
                    message_type=MessageType.SIGNAL,
                    interface=portal.shortcuts_interface,
                    member="Activated",
                    body=["/session", shortcut_id, 0, {}],
                )
            )

        self.assertEqual(toggles, [True])

    def test_create_session_uses_session_handle_from_request_response(self):
        portal = GlobalShortcutPortal()
        session_path = "/org/freedesktop/portal/desktop/session/test"
        request_path = "/org/freedesktop/portal/desktop/request/1_42/create"
        request = unittest.mock.AsyncMock(
            return_value=(request_path, {"session_handle": Variant("o", session_path)})
        )
        portal._request = request

        result = asyncio.run(portal._create_session("create"))

        self.assertEqual(result.value, session_path)
        request.assert_awaited_once_with(
            "CreateSession",
            {
                "handle_token": Variant("s", "create"),
                "session_handle_token": Variant("s", "session_create"),
            },
            signature="a{sv}",
        )


class ToggleIpcTests(unittest.TestCase):
    def test_external_command_toggles_running_instance(self):
        with tempfile.TemporaryDirectory() as runtime_dir, patch.dict(
            os.environ, {"XDG_RUNTIME_DIR": runtime_dir}
        ):
            toggled = threading.Event()
            server = ToggleIpcServer(toggled.set)
            server.start()
            try:
                self.assertTrue(request_running_toggle())
                self.assertTrue(toggled.wait(1))
            finally:
                server.close()

    def test_returns_false_without_running_instance(self):
        with tempfile.TemporaryDirectory() as runtime_dir, patch.dict(
            os.environ, {"XDG_RUNTIME_DIR": runtime_dir}
        ):
            self.assertFalse(request_running_toggle())


if __name__ == "__main__":
    unittest.main()