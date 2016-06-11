"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import locale
import logging
import pkgutil
import platform
import traceback
import threading
import subprocess
from Queue import Queue

# set locale - this is necessary for curses and *maybe* for clipboard handling
# there's only one locale setting so best to do it all upfront here
# NOTE that this affects str.upper() etc.
locale.setlocale(locale.LC_ALL, '')

from .version import __version__
from . import ansipipe
from . import basic
from .basic import signals
from . import state
from . import config


def main():
    """Initialise and perform requested operations."""
    try:
        with config.TemporaryDirectory(prefix='pcbasic-') as temp_dir:
            # get settings and prepare logging
            settings = config.Settings(temp_dir)
            command = settings.get_command()
            if command == 'version':
                # print version and exit
                show_version(settings)
            elif command == 'help':
                # print usage and exit
                show_usage()
            elif command == 'convert':
                # convert and exit
                convert(settings)
            elif settings.get_interface():
                # start an interpreter session with interface
                launch_session(settings)
            else:
                # start an interpreter session with standard i/o
                run_session(**settings.get_launch_parameters())
    except:
        # without this except clause we seem to be dropping exceptions
        # probably due to the sys.stdout.close() hack below
        logging.error('Unhandled exception\n%s', traceback.format_exc())
    finally:
        # avoid sys.excepthook errors when piping output
        # http://stackoverflow.com/questions/7955138/addressing-sys-excepthook-error-in-bash-script
        try:
            sys.stdout.close()
        except:
            pass
        try:
            sys.stderr.close()
        except:
            pass

def show_usage():
    """Show usage description."""
    sys.stdout.write(pkgutil.get_data(__name__, 'USAGE.txt'))

def show_version(settings):
    """Show version with optional debugging details."""
    sys.stdout.write(__version__ + '\n')
    if settings.get('debug'):
        show_platform_info()

def show_platform_info():
    """Show information about operating system and installed modules."""
    logging.info('\nPLATFORM')
    logging.info('os: %s %s %s', platform.system(), platform.processor(), platform.version())
    logging.info('python: %s %s', sys.version.replace('\n',''), ' '.join(platform.architecture()))
    logging.info('\nMODULES')
    # try numpy before pygame to avoid strange ImportError on FreeBSD
    modules = ('numpy', 'win32api', 'sdl2', 'pygame', 'curses', 'pexpect', 'serial', 'parallel')
    for module in modules:
        try:
            m = __import__(module)
        except ImportError:
            logging.info('%s: --', module)
        else:
            for version_attr in ('__version__', 'version', 'VERSION'):
                try:
                    version = getattr(m, version_attr)
                    logging.info('%s: %s', module, version)
                    break
                except AttributeError:
                    pass
            else:
                logging.info('available\n')
    if platform.system() != 'Windows':
        logging.info('\nEXTERNAL TOOLS')
        tools = ('lpr', 'paps', 'beep', 'xclip', 'xsel', 'pbcopy', 'pbpaste')
        for tool in tools:
            try:
                location = subprocess.check_output('command -v %s' % tool, shell=True).replace('\n','')
                logging.info('%s: %s', tool, location)
            except Exception as e:
                logging.info('%s: --', tool)

def convert(settings):
    """Perform file format conversion."""
    mode, name_in, name_out = settings.get_converter_parameters()
    session = basic.Session(**settings.get_session_parameters())
    try:
        session.load_program(name_in, rebuild_dict=False)
        session.save_program(name_out, filetype=mode)
    except basic.RunError as e:
        logging.error(e.message)

def launch_session(settings):
    """Start an interactive interpreter session."""
    from . import interface
    # initialise queues
    input_queue = Queue()
    video_queue = Queue()
    tone_queues = [Queue(), Queue(), Queue(), Queue()]
    message_queue = Queue()
    queues = (input_queue, video_queue, tone_queues, message_queue)
    # launch the BASIC thread
    thread = threading.Thread(
                target=run_session,
                args=(queues,), kwargs=settings.get_launch_parameters())
    thread.start()
    try:
        interface.run(
                settings.get_interface(),
                settings.get_video_parameters(), settings.get_audio_parameters(), *queues)
    except interface.InitFailed:
        logging.error('Failed to initialise interface.')
    finally:
        input_queue.put(signals.Event(signals.KEYB_QUIT))
        thread.join()

def run_session(queues=(), resume=False, state_file=None, wait=False,
                prog=None, commands=(), **session_params):
    """Run an interactive BASIC session."""
    if resume:
        session = state.zunpickle(state_file).attach(*queues)
    else:
        session = basic.Session(*queues, **session_params)
    with session:
        try:
            if prog:
                session.load_program(prog)
            for cmd in commands:
                session.execute(cmd)
            session.interact()
        except basic.Exit:
            # SYSTEM called during launch
            pass
        finally:
            state.zpickle(session, state_file)
            if wait:
                session.pause('Press a key to close window')



if __name__ == "__main__":
    main()
