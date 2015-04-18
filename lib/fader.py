#!/usr/bin/python
import os
import re
import sys
import dbus
import errno
import signal
import functools
from time import sleep
from lib.bus import get_bus
from lib.bus import DBUS_INTERFACE
from collections import deque
from lib.exceptions import VolumeException
from lib.config import PULSEAUDIO_PATH


def no_op():
    pass


class PulseAudioStreamFader(dict):
    updates = deque()

    def __init__(self, pipe, child_pid):
        try:
            self.bus = get_bus()
            print('LOG:', 'Connected to PulseAudio DBus socket.', file=sys.stdout)
        except dbus.exceptions.DBusException as err:
            error_message = err
            exit_code = 1
            if hasattr(err, '_dbus_error_name') and err._dbus_error_name == 'org.freedesktop.DBus.Error.FileNotFound':
                error_message = 'Cannot connect to PulseAudio DBus socket. Is it running?\n' \
                                'You may need to start it via "pactl load-module module-dbus-protocol".'
                exit_code = errno.ECONNREFUSED
            print('ERROR:', error_message, file=sys.stderr)
            sys.exit(exit_code)

        self.pipe = pipe
        self.child_pid = child_pid
        self.unmute_vol = 0.5
        super(PulseAudioStreamFader, self).__init__()
        self.refresh(soft=False)
        signal.signal(signal.SIGUSR1, self.update_handler)
        self.pipe.readline()  # Unblock child.

    def re_exec(self):
        try:
            os.kill(self.child_pid, signal.SIGKILL)  # Prevent it sending USR1 to new process.
        except OSError:
            pass
        try:
            os.execv(__file__, sys.argv)
        except OSError:
            os.execvp('python', ['python', __file__] + sys.argv[1:])

    @staticmethod
    def _dbus_dec(prop):
        return str(bytes(bytearray((_ for _ in prop if _))), 'utf-8', 'ignore')

    def _get_name(self, props):
        return self._dbus_dec(props['application.name'])

    def get_stream(self, expression=None, path=None):
        """

        :param expression:
        :param path:
        :return:
        """
        object_status = False
        object_identifier = None
        object_type = None
        object_reference = None

        def match_rule(*_):
            return False
        if expression:
            match_rule = lambda name, obj_type, obj: bool(re.match(expression, name, re.I))
        if path:
            match_rule = lambda name, obj_type, obj: obj.object_path == path

        for name, (obj_type, obj) in self.items():
            if match_rule(name, obj_type, obj):
                object_status = True
                object_identifier = name
                object_type = obj_type
                object_reference = obj

        return object_status, object_identifier, object_type, object_reference

    def add(self, path, interface):
        stream = self.bus.get_object(object_path=path)
        stream_props = dict(stream.Get('org.PulseAudio.Core1.{}'.format(interface), 'PropertyList'))
        name = self._get_name(stream_props)

        self[name] = interface, stream

        if self.get_stream(expression='chrom')[0]:
            target, identifier, _, _ = self.get_stream(expression='spotify')
            if target:
                self.fade_volume(identifier, 0)

                try:
                    spotify_core = dbus.SessionBus().get_object('com.spotify.qt', '/org/mpris/MediaPlayer2')
                    interface = dbus.Interface(spotify_core, 'org.mpris.MediaPlayer2.Player')
                    getattr(interface, 'Pause', no_op)()
                except dbus.exceptions.DBusException:
                    print('Couldn\'t connect to Spotify.')
        return name

    def remove(self, path):
        if self.get_stream(expression='chrom')[0]:
            target, identifier, _, _ = self.get_stream(expression='spotify')
            if target:
                try:
                    spotify_core = dbus.SessionBus().get_object('com.spotify.qt', '/org/mpris/MediaPlayer2')
                    interface = dbus.Interface(spotify_core, 'org.mpris.MediaPlayer2.Player')
                    getattr(interface, 'Play', no_op)()
                except dbus.exceptions.DBusException:
                    print('Couldn\'t connect to Spotify.')

                self.fade_volume(identifier, 1)

        status, name, _, _ = self.get_stream(path=path)
        if status:
            del self[name]

    def refresh(self, soft=True):
        if not soft:
            self.clear()
        try:
            stream_names = set(
                self.add(path, 'Stream') for path in
                self.bus.get_object(object_path=PULSEAUDIO_PATH)
                    .Get('org.PulseAudio.Core1', 'PlaybackStreams', dbus_interface=DBUS_INTERFACE))
        except dbus.exceptions.DBusException:  # bus is probably abandoned
            if soft:
                self.refresh(soft=False)
            else:
                raise
        else:
            if not soft:
                os.kill(self.child_pid, signal.SIGUSR1)  # break glib loop to reacquire the bus
            else:
                # self.remove checks are not needed here
                for name in stream_names.difference(self):
                    del self[name]

    def update(self, *_):
        while self.updates:
            action, path = self.updates.popleft()
            {
                '+': functools.partial(self.add, interface='Stream'),
                '-': self.remove,
            }[action](path)

    def update_handler(self, *_):
        try:
            self.updates.append(self.pipe.readline().decode('utf-8').strip().split(' ', 1))
        except IOError:
            self.re_exec()  # Child died.

    def get_volume(self, item, raw=False):
        try:
            interface, obj = self[item]
            val = obj.Get('org.PulseAudio.Core1.{}'.format(interface), 'Volume')
        except KeyError:
            raise VolumeException
        val = tuple(min(val / 2 ** 16, 1.0) for val in val)
        return (sum(val) / len(val)) if not raw else val  # average of channels

    def set_volume(self, item, val):
        # all channels to the same level
        val = [max(0, min(1, val))] * len(self.get_volume(item, raw=True))

        val_dbus = list(dbus.UInt32(round(val * 2 ** 16)) for val in val)
        try:
            interface, obj = self[item]
            obj.Set('org.PulseAudio.Core1.{}'.format(interface), 'Volume', val_dbus, dbus_interface=DBUS_INTERFACE)
        except KeyError:
            raise VolumeException

    def fade_volume(self, item, target_vol, frames=300, frame_length=0.001):
        start_vol = self.get_volume(item)
        if target_vol == 0:
            self.unmute_vol = start_vol
        if target_vol == 1:
            start_vol = 0
            target_vol = self.unmute_vol


        for frame in range(0, frames):
            progress = frame / frames
            cur_vol = target_vol * progress
            if start_vol > target_vol:
                progress = (frames - frame) / frames
                cur_vol = start_vol * progress
            self.set_volume(item, cur_vol)
            sleep(frame_length)

    def __del__(self):
        try:
            os.kill(self.child_pid, signal.SIGTERM)
        except OSError:
            pass
