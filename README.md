

# Linux development
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-linux.txt

# Wayland
yclicker uses the desktop GlobalShortcuts portal for the global F8 shortcut and
uinput for mouse clicks and the optional R key. The desktop portal must be
available, and the current user must have write access to /dev/uinput. If the
input device cannot be opened, check that the uinput kernel module is loaded
and configure device permissions for your distribution; yclicker does not
request root access itself.

If the desktop does not provide the GlobalShortcuts portal, configure a global
F8 shortcut in the desktop settings to run `yclicker --toggle`. This forwards
the toggle to the running instance. When running from source, use
`/path/to/.venv/bin/python /path/to/main.py --toggle` as the shortcut command.

On KDE, if the KDE portal backend is installed but the GlobalShortcuts portal
is unavailable, select KDE for this portal by creating
`~/.config/xdg-desktop-portal/kde-portals.conf` with:

```ini
[preferred]
org.freedesktop.impl.portal.GlobalShortcuts=kde
```

Restart `xdg-desktop-portal` or log in again afterward. If the portal is still
unavailable, the clicker continues to work and F8 can use the manual KDE
shortcut above. The window status shows the portal error details.

The portal may ask the user to confirm or choose the shortcut. If that is
unavailable, yclicker displays the desktop-shortcut fallback status in its
window.

For a Linux PyInstaller build, install PyInstaller and build from the spec. It
includes the dynamically loaded Wayland backend and its DBus dependencies:

```sh
pip install pyinstaller
pyinstaller yclicker.spec
```

Run the focused backend tests with `python -m unittest discover -s tests -v`.






## Fehlerbehebung für Wayland

Falls die Wayland-Unterstützung nicht korrekt funktioniert und der Status auf "Fehler" springt, prüfe bitte folgende Punkte:

### 1. Berechtigungen für `/dev/uinput`
Die Simulation von Eingaben erfordert Zugriff auf das `uinput`-Modul.
*   **Problem:** Die Anwendung hat keine Berechtigung, `/dev/uinput` zu öffnen.
*   **Lösung:** Stelle sicher, dass dein Benutzer Mitglied der Gruppe ist, die Zugriff auf dieses Gerät hat (oft `input`). Du kannst dies mit folgendem Befehl versuchen:
    ```bash
    sudo usermod -aG input $USER
    ```
    *Hinweis: Du musst dich danach einmal aus- und wieder einloggen, damit die Gruppenänderung wirksam wird.*

### 2. Fehlende Python-Pakete
Stelle sicher, dass alle notwendigen Bibliotheken installiert sind.
*   **Lösung:** Installiere die benötigten Pakete über pip:
    ```bash
    pip install evdev dbus-next
    ```

### 3. XDG Desktop Portals
Für die Erkennung globaler Hotkeys unter Wayland benötigt die Anwendung die entsprechenden Portale.
*   **Problem:** Das Portal für globale Shortcuts ist nicht installiert oder nicht aktiv.
*   **Lösung:** Installiere das passende Portal für deinen Desktop (z. B. `xdg-desktop-portal-gnome`, `xdg-desktop-portal-wlr` oder `xdg-desktop-portal-kde`).

### 4. XDG_RUNTIME_DIR
Die Anwendung benötigt eine korrekt gesetzte `XDG_RUNTIME_DIR`-Variable, um den internen IPC-Server zu starten.
*   **Prüfung:** Gib im Terminal `echo $XDG_RUNTIME_DIR` ein. Wenn keine Ausgabe erscheint, ist die Umgebungsvariable nicht gesetzt.

