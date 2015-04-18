import dbus
import os

DBUS_INTERFACE = 'org.freedesktop.DBus.Properties'
PULSEAUDIO_DBUS_SOCKET = '/run/pulse/dbus-socket'


def get_bus_address():
    srv_addr = os.environ.get('PULSE_DBUS_SERVER')
    if not srv_addr and os.access(PULSEAUDIO_DBUS_SOCKET, os.R_OK | os.W_OK):
        srv_addr = 'unix:path=' + PULSEAUDIO_DBUS_SOCKET
    if not srv_addr:
        srv_addr = dbus.SessionBus().get_object(
            'org.PulseAudio1',  # DBus interface.
            '/org/pulseaudio/server_lookup1'  # DBus object path.
        ).Get(
            'org.PulseAudio.ServerLookup1',
            'Address',
            dbus_interface=DBUS_INTERFACE
        )
    return srv_addr


def get_bus(srv_addr=None):
    while not srv_addr:
        try:
            srv_addr = get_bus_address()
        except dbus.exceptions.DBusException as err:
            if srv_addr is False or err.get_dbus_name() != 'org.freedesktop.DBus.Error.ServiceUnknown':
                raise
            srv_addr = False  # Avoid endless loop.
    return dbus.connection.Connection(srv_addr)
