#!/usr/bin/python
import os
import sys
import dbus
import functools
from io import open
from time import sleep
from lib.bus import get_bus
import signal
from lib.config import PULSEAUDIO_PATH
from lib.fader import PulseAudioStreamFader


signal.signal(signal.SIGUSR1, signal.SIG_IGN)
fd_out, fd_in = os.pipe()
core_pid = os.getpid()
child_pid = os.fork()

if not child_pid:
    # Stream changes monitoring subprocess thread.

    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib

    os.close(fd_out)
    pipe = open(fd_in, 'wb', buffering=0)
    pipe.write(b'\n')  # Wait for main process to get ready.

    DBusGMainLoop(set_as_default=True)
    loop = GLib.MainLoop()
    signal.signal(signal.SIGUSR1, lambda sig, frm: loop.quit())

    def notify(path, op):
        try:
            os.kill(core_pid, signal.SIGUSR1)
            pipe.write('{} {}\n'.format(op, path).encode('utf-8'))
        except:
            loop.quit()

    while True:
        bus = get_bus()
        core = bus.get_object(object_path=PULSEAUDIO_PATH)
        for sig_name, sig_handler in (
            ('NewPlaybackStream', functools.partial(notify, op='+')),
            ('PlaybackStreamRemoved', functools.partial(notify, op='-'))
        ):
            bus.add_signal_receiver(sig_handler, sig_name)
            core.ListenForSignal('org.PulseAudio.Core1.{}'.format(sig_name), dbus.Array(signature='o'))

        loop.run()

    raise RuntimeError('Child code broke out of the loop.')

else:
    os.close(fd_in)
    pipe = open(fd_out, 'rb', buffering=0)


if __name__ == '__main__':
    fader = PulseAudioStreamFader(pipe=pipe, child_pid=child_pid)

    while True:
        if os.waitpid(child_pid, os.WNOHANG)[0]:
            sys.exit(1)

        while fader.updates:
            fader.update()
        if not fader:
            fader.refresh()

        sleep(1)

        if fader.updates:
            continue
