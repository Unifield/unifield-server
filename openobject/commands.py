import os
import sys
import time
import subprocess
import threading
from optparse import OptionParser
import logging

import cherrypy
from cherrypy.lib.reprconf import Parser

import openobject
import openobject.release
import openobject.paths
from openobject.i18n import _

class ConfigurationError(Exception):
    pass

DISTRIBUTION_CONFIG = os.path.join('doc', 'openerp-web.cfg')
FROZEN_DISTRIBUTION_CONFIG = os.path.join('conf', 'openerp-web.cfg')
OVERRIDE_CONFIG = os.path.join('conf', 'openerp-web-oc.cfg')
def get_config_override_file():
    if os.name == 'nt':
        configfile = os.path.join(openobject.paths.root(), OVERRIDE_CONFIG)
        if os.path.exists(configfile):
            return configfile

    return False

def get_config_file():
    if os.name == 'nt':
        configfile = os.path.join(openobject.paths.root(), FROZEN_DISTRIBUTION_CONFIG)
        if not os.path.exists(configfile):
            configfile = os.path.join(openobject.paths.root(), DISTRIBUTION_CONFIG)
    else:
        setupdir = os.path.dirname(os.path.dirname(__file__))
        isdevdir = os.path.isfile(os.path.join(setupdir, 'setup.py'))
        configfile = '/etc/openerp-web.cfg'
        if isdevdir or not os.path.exists(configfile):
            configfile = os.path.join(setupdir, DISTRIBUTION_CONFIG)
    return configfile

def start():
    import babel.localedata
    if not os.path.exists(babel.localedata._dirname):
        # try to use the one py2exe uses, without a dash on the end
        n = os.path.join(os.path.dirname(babel.localedata._dirname),
                         "localedata")
        babel.localedata._dirname = n

    parser = OptionParser(version="%s" % (openobject.release.version))
    parser.add_option("-c", "--config", metavar="FILE", dest="config",
                      help="configuration file", default=get_config_file())
    parser.add_option("--config-override", metavar="FILE", dest="config_override",
                      help="override configuration file", default=get_config_override_file())
    parser.add_option("-a", "--address", help="host address, overrides server.socket_host")
    parser.add_option("-p", "--port", help="port number, overrides server.socket_port")
    parser.add_option("--openerp-host", dest="openerp_host", help="overrides openerp.server.host")
    parser.add_option("--openerp-port", dest="openerp_port", help="overrides openerp.server.port")
    parser.add_option("--openerp-protocol", dest="openerp_protocol", help="overrides openerp.server.protocol")
    parser.add_option("--no-static", dest="static",
                      action="store_false", default=True,
                      help="Disables serving static files through CherryPy")
    options, args = parser.parse_args(sys.argv)

    if not os.path.exists(options.config):
        raise ConfigurationError(_("Could not find configuration file: %s") %
                                 options.config)

    error_config = False
    app_config = Parser().dict_from_file(options.config)
    if options.config_override:
        try:
            over_config = Parser().dict_from_file(options.config_override)
            for section, value in list(over_config.items()):
                app_config.setdefault(section, {}).update(value)
        except Exception:
            pass
    if 'engine.timeout_monitor.on' in app_config.get('global', {}):
        del app_config['global']['engine.timeout_monitor.on']
    openobject.configure(app_config)

    if error_config:
        cherrypy.log('Unable to parse %s\nError: %s' % (options.config_override, error_config), "ERROR")
        raise ConfigurationError(_("Unable to parse: %s") %
                                 options.config_override)

    if options.static:
        openobject.enable_static_paths()

    if not cherrypy.config.get('tools.sessions.locking'):
        cherrypy.config['tools.sessions.locking'] = 'explicit'
    # Try to start revprox now so that we know what default to set for
    # port number (revprox ok? port = 18061)
    if options.port is None:
        options.port = cherrypy.config.get('server.socket_port', 8061)
    if revprox(options.port):
        options.port = 18061
        options.address = '127.0.0.1'
        cherrypy.config['tools.proxy.on'] = True

    if options.address:
        cherrypy.config['server.socket_host'] = options.address
    if options.port:
        try:
            cherrypy.config['server.socket_port'] = int(options.port)
        except:
            pass
    port = cherrypy.config.get('server.socket_port')

    if not isinstance(port, int) or port < 1 or port > 65535:
        cherrypy.log('Wrong configuration socket_port: %s' % (port,), "ERROR")
        raise ConfigurationError(_("Wrong configuration socket_port: %s") %
                                 port)
    if options.openerp_host:
        cherrypy.config['openerp.server.host'] = options.openerp_host
    if options.openerp_port:
        try:
            cherrypy.config['openerp.server.port'] = int(options.openerp_port)
        except:
            pass
    if options.openerp_protocol in ['http', 'https', 'socket']:
        cherrypy.config['openerp.server.protocol'] = options.openerp_protocol

    if sys.platform == 'win32':
        from cherrypy.process.win32 import ConsoleCtrlHandler
        class ConsoleCtrlHandlerWeb(ConsoleCtrlHandler):
            def handle(self, event):
                """Handle console control events (like Ctrl-C)."""
                # 'First to return True stops the calls'
                return 1
        cherrypy.engine.console_control_handler = ConsoleCtrlHandlerWeb(cherrypy.engine)

    if hasattr(cherrypy.engine, "signal_handler"):
        cherrypy.engine.signal_handler.subscribe()
    if hasattr(cherrypy.engine, "console_control_handler"):
        cherrypy.engine.console_control_handler.subscribe()

    cherrypy.engine.start()
    openobject.pooler.get_pool()
    cherrypy.engine.block()

def stop():
    cherrypy.engine.exit()

# Try to start the reverse proxy. If anything goes wrong, return
# False. Launch a thread which monitors it's output, copying it to
# cherrypy.log, and kills the server if revproxy dies.
def revprox(redir_port):
    ctx = "REVPROX"

    https_name = cherrypy.config.get('server.https_name')
    if not https_name:
        cherrypy.log("server.https_name is not set, not running the reverse proxy", ctx)
        return False

    rbin = 'revprox'
    if sys.platform == 'win32':
        rbin += '.exe'
    rbin = os.path.abspath(openobject.paths.root('revprox', rbin))
    if not os.path.exists(rbin):
        cherrypy.log("%s does not exist, not running the reverse proxy." % rbin, ctx)
        return False

    cmd = [ rbin, '-server', https_name, '-redir', str(redir_port) ]
    if cherrypy.config.get('server.https_port'):
        cmd += ['-listen-port', str(cherrypy.config.get('server.https_port'))]

    to_reopen = []
    # close log files, so Popen doens't keep an opened descriptor
    # the log file rotation will not be locked
    # close_fds=True can't be used on Win with stderr and stdout
    for log in (cherrypy.log.error_log, cherrypy.log.access_log):
        for h in log.handlers:
            if isinstance(h, logging.FileHandler):
                h.acquire()
                h.stream.close()
                to_reopen.append(h)


    proc = subprocess.Popen(cmd,
                            stderr=subprocess.STDOUT,  # Merge stdout and stderr
                            stdout=subprocess.PIPE)

    for h in to_reopen:
        h.stream = open(h.baseFilename, h.mode)
        h.release()

    ok = False
    while not ok:
        line = proc.stdout.readline()
        if line:
            line = str(line, 'utf8').strip().split(" ", 2)
            cherrypy.log(line[-1], ctx)
            if line[-1] == 'Startup OK.':
                ok = True
        else:
            # Process exited
            break

    if not ok:
        cherrypy.log("reverse proxy exited without starting up", ctx)
        return False

    # It started correctly. So arrange that it's logs are copied
    # and that it is killed on shutdown.

    def logRead(proc):
        while True:
            line = proc.stdout.readline()
            if line:
                line = str(line, 'utf8').split(" ", 2)
                cherrypy.log(line[-1].strip(), ctx)
            else:
                break
        rc = proc.wait()
        cherrypy.log("reverse proxy exited (rc=%d)." % rc, ctx)
        if rc != 0:
            # revprox exited with an error, so tell cherrypy to exit too.
            # We will be restarted by the system (see setup.nsi: "sc failure...")
            cherrypy.engine.stop()
            # However, if it gets stuck on "Bus STOPPED", use exit to be sure
            time.sleep(5)
            os._exit(1)
        return

    thread = threading.Thread(target=logRead, args=[proc])
    thread.start()

    # A callback to register on stop, for killing revprox.
    def _cb(p):
        cherrypy.log("stopping", ctx)
        try:
            p.terminate()
        except OSError:
            # Probably "no such process", which is ok.
            pass

    cherrypy.engine.subscribe('stop', lambda p=proc: _cb(p))
    return True

