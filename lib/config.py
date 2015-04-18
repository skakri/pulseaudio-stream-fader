import os
import sys
import shutil
import configparser
from xdg import BaseDirectory

PULSEAUDIO_PATH = '/org/pulseaudio/core1'
PROGRAM_NAME = 'pulseaudio-stream-fader'
CONFIG_VERSION = 1

config_dir = os.path.join(BaseDirectory.xdg_config_home, PROGRAM_NAME)

if not os.path.isdir(config_dir):
    os.mkdir(config_dir)
    print(
        'LOG:',
        'Created configuration directory in "' + config_dir + '".',
        file=sys.stdout
    )

config_file = os.path.join(config_dir, PROGRAM_NAME + '.ini')

config_parser = configparser.RawConfigParser()
if not os.path.isfile(config_file):
    shutil.copy2(PROGRAM_NAME + '.sample.ini', config_file)
    print(
        'LOG:',
        'Created basic configuration in "' + config_file + '".',
        file=sys.stdout
    )

config_parser.read(config_file)
if CONFIG_VERSION is not int(
    config_parser.get('main', 'config_version', fallback=0)
):
    print(
        'ERROR:',
        'Mismatching config version. Please merge with ' + PROGRAM_NAME +
        '.sample.ini or remove "' + config_file + '".',
        file=sys.stderr
    )
    sys.exit(1)
