pulseaudio-stream-fader
-----------------------

PulseAudio stream fader. Automatically fades-pauses/unpauses-fades streams based upon user rules.


Installation
------------

Just symlink the script to wherever is convenient (~/bin or /usr/local/bin), do a "chmod +x" on it, run.
Example:
`ln -s $(pwd)/pulseaudio-stream-fader.py /usr/local/bin/pulseaudio-stream-fader`

Make sure you have `load-module module-dbus-protocol` line in `/etc/pulse/default.pa` (or `/etc/pulse/system.pa`, if 
system-wide daemon is used), especially on Ubuntu, where it seem to be disabled by default.


Requirements
============

* Python 3
* dbus-python
* PyGObject
* PulseAudio 1.0+


Usage
-----

Run the script. There's no configuration yet, pulseaudio-stream-fader listens to chrome/chromium stream events and
pauses/unpauses spotify.


Bugs
----

Chromium may start a stream if google search results contain word definition.
Long term solution would be to monitor stream VU levels.


Thanks to
---------

Loosely based upon [pulseaudio-mixer-cli](https://github.com/mk-fg/pulseaudio-mixer-cli/).

Idea borrowed from [mute.fm](http://www.mute.fm/). Check them out if you need Windows solution.
