# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2010 OpenERP s.a. (<http://openerp.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

"""
Miscelleanous tools used by OpenERP.
"""

import inspect
import subprocess
import logging
import os
import re
import smtplib
import socket
import sys
import threading

import time
import warnings
import zipfile
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formatdate, COMMASPACE
from email import encoders
from itertools import islice
from lxml import etree
from .which import which
from threading import local
import math
from functools import reduce
from functools import cmp_to_key
import hashlib
from . import sql

try:
    from html2text import html2text
except ImportError:
    html2text = None

import netsvc
from .config import config
from .lru import LRU
from xml.sax.saxutils import escape

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


_logger = logging.getLogger('tools')

# List of etree._Element subclasses that we choose to ignore when parsing XML.
# We include the *Base ones just in case, currently they seem to be subclasses of the _* ones.
SKIPPED_ELEMENT_TYPES = (etree._Comment, etree._ProcessingInstruction, etree.CommentBase, etree.PIBase)

rsync_lock = threading.RLock()

def _(d):
    # just here to export the month when trans. file is generated
    return d
month_abbr = ['', _('Jan'), _('Feb'), _('Mar'), _('Apr'), _('May'), _('Jun'), _('Jul'), _('Aug'), _('Sep'), _('Oct'), _('Nov'), _('Dec')]

# initialize a database with base/base.sql
def init_db(cr):
    import addons
    f = addons.get_module_resource('base', 'base.sql')
    base_sql_file = file_open(f)
    try:
        cr.execute(base_sql_file.read())
        cr.commit()
    finally:
        base_sql_file.close()

    for i in addons.get_modules():
        mod_path = addons.get_module_path(i)
        if not mod_path:
            continue

        info = addons.load_information_from_description_file(i)

        if not info:
            continue
        categs = info.get('category', 'Uncategorized').split('/')
        p_id = None
        while categs:
            if p_id is not None:
                cr.execute('SELECT id \
                           FROM ir_module_category \
                           WHERE name=%s AND parent_id=%s', (categs[0], p_id))
            else:
                cr.execute('SELECT id \
                           FROM ir_module_category \
                           WHERE name=%s AND parent_id IS NULL', (categs[0],))
            c_id = cr.fetchone()
            if not c_id:
                cr.execute('INSERT INTO ir_module_category \
                        (name, parent_id) \
                        VALUES (%s, %s) RETURNING id', (categs[0], p_id))
                c_id = cr.fetchone()[0]
            else:
                c_id = c_id[0]
            p_id = c_id
            categs = categs[1:]

        active = info.get('active', False)
        installable = info.get('installable', True)
        if installable:
            if active:
                state = 'to install'
            else:
                state = 'uninstalled'
        else:
            state = 'uninstallable'
        cr.execute('INSERT INTO ir_module_module \
                (author, website, name, shortdesc, description, \
                    category_id, state, certificate, web, license) \
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id', (
            info.get('author', ''),
            info.get('website', ''), i, info.get('name', False),
            info.get('description', ''), p_id, state, info.get('certificate') or None,
            info.get('web') or False,
            info.get('license') or 'AGPL-3'))
        id = cr.fetchone()[0]
        cr.execute('INSERT INTO ir_model_data \
            (name,model,module, res_id, noupdate) VALUES (%s,%s,%s,%s,%s)', (
            'module_meta_information', 'ir.module.module', i, id, True))
        dependencies = info.get('depends', [])
        for d in dependencies:
            cr.execute('INSERT INTO ir_module_module_dependency \
                    (module_id,name) VALUES (%s, %s)', (id, d))
        cr.commit()

def find_in_path(name):
    try:
        return which(name)
    except IOError:
        return None

def _set_env_pg(remove=False):
    if config['db_password']:
        if not remove and not os.environ.get('PGPASSWORD', ''):
            os.environ['PGPASSWORD'] = config['db_password']
        if remove and os.environ.get('PGPASSWORD'):
            os.environ['PGPASSWORD'] = ''

def path_to_cygwin(path):
    new_path = re.sub(r'^(.):', '/cygdrive/\\1', path).replace('\\', '/')
    if not new_path.endswith('/'):
        new_path = '%s/' % new_path
    return new_path

def force_wal_generation(cr, wal_path):

    if sql.is_pg14(cr):
        cr.execute('select * from pg_walfile_name_offset(pg_switch_wal())')
    else:
        cr.execute('select * from pg_xlogfile_name_offset(pg_switch_xlog())')

    file_name, offset = cr.fetchone()
    _logger.warn('WAL generation forced %s %s' % (file_name, offset))
    if not offset or not file_name:
        return True
    zip_new_wal = os.path.join(wal_path, '%s.7z' % file_name)
    wait = 0
    while True:
        if os.path.exists(zip_new_wal):
            return True
        wait += 1
        if wait > 30:
            _logger.warn('7z Wal %s not found' % zip_new_wal)
            return False
        time.sleep(2)

def sent_to_remote(local_path, config_dir=False, remote_user=False, remote_host=False, remote_dir=False):

    exe_dir = os.path.join(os.path.normcase(os.path.abspath(config['root_path'])), 'rsync')
    sync = os.path.join(exe_dir, 'rsync.exe')
    ssh = os.path.join(exe_dir, 'ssh.exe')

    if not remote_user:
        remote_user = 'backup'

    if not remote_host:
        remote_host = '51.91.31.142'

    if not config_dir:
        config_dir = os.path.join(os.path.normcase(os.path.abspath(config['root_path'])), '..', '..', 'SSH_CONFIG')
    sshconfig = os.path.join(config_dir, 'config')

    for to_check in [sshconfig, sync, ssh]:
        if not os.path.exists(to_check):
            raise Exception("%s not found" % (to_check,))

    if not os.path.isdir(local_path):
        raise Exception("Local path %s not found" % (local_path,))


    remote_path = '%s/' % remote_dir
    try:
        with rsync_lock:
            command = [sync, '--remove-source-files', '--partial-dir=.rsync-partial', '-a', '-e', '"%s" -F "%s"'%(ssh, sshconfig), '--include=*/', '--include=*7z', '--exclude=*', path_to_cygwin(local_path), "%s@%s:%s" % (remote_user, remote_host, remote_path)]
            _logger.info(' '.join(command))
            subprocess.check_output(command, stderr=subprocess.STDOUT)
            _logger.info('Rsync ends')
            return True
    except subprocess.CalledProcessError as e:
        _logger.error('rsync %s' % e.output)
        raise Exception(e.output)
    except Exception as e:
        raise e

def pg_basebackup(db_name, wal_dir, is_pg14=False):
    if not os.path.isdir(wal_dir):
        raise Exception("Destination directory %s not found" % (wal_dir,))
    dest_dir = os.path.join(wal_dir, 'base')
    if not os.path.isdir(dest_dir):
        os.makedirs(dest_dir)
    try:
        _logger.info('pg_basebackup %s to %s' % (db_name, dest_dir))
        _set_env_pg()
        pg_basebackup = find_pg_tool('pg_basebackup')
        if not pg_basebackup:
            raise Exception("Couldn't find %s" % pg_basebackup)

        if is_pg14:
            cmd = [pg_basebackup, '--format=t', '-X', 'n', '--no-manifest', '-D', dest_dir]
        else:
            cmd = [pg_basebackup, '--format=t', '-D', dest_dir]

        if config['db_user']:
            cmd.append('--username=' + config['db_user'])
        if config['db_host']:
            cmd.append('--host=' + config['db_host'])
        if config['db_port']:
            cmd.append('--port=' + str(config['db_port']))

        szexe = os.path.join(os.path.normcase(os.path.abspath(config['root_path'])), 'rsync' , '7za.exe')
        if not os.path.exists(szexe):
            raise Exception('7za.exe not found')

        subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        _logger.info('pg_basebackup done')
        base_path = os.path.join(dest_dir, 'base.tar')
        if not os.path.exists(base_path):
            raise Exception('%s not found' % base_path)
        command_7z = [szexe, '-sdel', '-bd', '-bso0', '-w%s'%dest_dir, 'a', '%s.7z' % base_path, base_path]
        _logger.info(' '.join(command_7z))
        subprocess.check_output(command_7z, stderr=subprocess.STDOUT)
        _logger.info('7z done')
        return True
    except subprocess.CalledProcessError as e:
        _logger.error('pg_base %s' % e.output)
        raise Exception(e.output)
    except Exception as e:
        raise e
    finally:
        _set_env_pg(remove=True)

def pg_dump(db_name, outfile=False):
    try:
        _logger.info('Dump %s to %s' % (db_name, outfile or 'memory'))
        _set_env_pg()
        cmd = ['pg_dump', '--format=c', '--no-owner']
        if outfile:
            cmd += ['-f', outfile]
        if config['db_user']:
            cmd.append('--username=' + config['db_user'])
        if config['db_host']:
            cmd.append('--host=' + config['db_host'])
        if config['db_port']:
            cmd.append('--port=' + str(config['db_port']))
        cmd.append(db_name)
        if outfile:
            res = exec_pg_command(*tuple(cmd))
            if res != 0:
                error_txt = 'pg_dump return code %s, outfile: %s' % (res, outfile)
                _logger.error(error_txt)
                raise Exception(error_txt)
        else:
            # TODO: current pg_dump method do not return the same type of
            # variable depending of outfile, if outfile, it return an int, else
            # a tuple, this make this method unreliable
            stdin, stdout = exec_pg_command_pipe(*tuple(cmd))
            stdin.close()
            data = stdout.read()
            error = stdout.close()
            res = (data, error)
    except Exception:
        _logger.error('Dump', exc_info=1)
        if outfile:
            try:
                os.remove(outfile)
                open('%s.KO' % outfile, 'a').close()
            except:
                pass
            res = -1
    finally:
        _set_env_pg(remove=True)
        return res

def find_pg_tool(name):
    path = None
    if config['pg_path'] and config['pg_path'] != 'None':
        path = config['pg_path']
    try:
        return which(name, path=path)
    except IOError:
        return None


def exec_pg_command(name, *args):
    prog = find_pg_tool(name)
    if not prog:
        raise Exception('Couldn\'t find %s' % name)
    args2 = (prog,) + args

    return subprocess.call(args2)

def exec_pg_command_pipe(name, *args):
    prog = find_pg_tool(name)
    if not prog:
        raise Exception('Couldn\'t find %s' % name)
    # on win32, passing close_fds=True is not compatible
    # with redirecting std[in/err/out]
    pop = subprocess.Popen((prog,) + args, bufsize= -1,
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           close_fds=(os.name=="posix"))
    return (pop.stdin, pop.stdout)

def exec_command_pipe(name, *args):
    prog = find_in_path(name)
    if not prog:
        raise Exception('Couldn\'t find %s' % name)
    # on win32, passing close_fds=True is not compatible
    # with redirecting std[in/err/out]
    pop = subprocess.Popen((prog,) + args, bufsize= -1,
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           close_fds=(os.name=="posix"))
    return (pop.stdin, pop.stdout)

#----------------------------------------------------------
# File paths
#----------------------------------------------------------
#file_path_root = os.getcwd()
#file_path_addons = os.path.join(file_path_root, 'addons')

def file_open(name, mode="r", subdir='addons', pathinfo=False):
    """Open a file from the OpenERP root, using a subdir folder.

    >>> file_open('hr/report/timesheer.xsl')
    >>> file_open('addons/hr/report/timesheet.xsl')
    >>> file_open('../../base/report/rml_template.xsl', subdir='addons/hr/report', pathinfo=True)

    @param name: name of the file
    @param mode: file open mode
    @param subdir: subdirectory
    @param pathinfo: if True returns tupple (fileobject, filepath)

    @return: fileobject if pathinfo is False else (fileobject, filepath)
    """
    import addons
    adps = addons.ad_paths
    rtp = os.path.normcase(os.path.abspath(config['root_path']))

    if name.replace(os.path.sep, '/').startswith('addons/'):
        subdir = 'addons'
        name = name[7:]

    # First try to locate in addons_path
    if subdir:
        subdir2 = subdir
        if subdir2.replace(os.path.sep, '/').startswith('addons/'):
            subdir2 = subdir2[7:]

        subdir2 = (subdir2 != 'addons' or None) and subdir2

        for adp in adps:
            try:
                if subdir2:
                    fn = os.path.join(adp, subdir2, name)
                else:
                    fn = os.path.join(adp, name)
                fn = os.path.normpath(fn)
                fo = file_open(fn, mode=mode, subdir=None, pathinfo=pathinfo)
                if pathinfo:
                    return fo, fn
                return fo
            except IOError:
                pass

    if subdir:
        name = os.path.join(rtp, subdir, name)
    else:
        name = os.path.join(rtp, name)

    name = os.path.normpath(name)

    # Check for a zipfile in the path
    head = name
    zipname = False
    name2 = False
    while True:
        head, tail = os.path.split(head)
        if not tail:
            break
        if zipname:
            zipname = os.path.join(tail, zipname)
        else:
            zipname = tail
        if zipfile.is_zipfile(head+'.zip'):
            from io import StringIO
            zfile = zipfile.ZipFile(head+'.zip')
            try:
                fo = StringIO()
                fo.write(zfile.read(os.path.join(
                    os.path.basename(head), zipname).replace(
                        os.sep, '/')))
                fo.seek(0)
                if pathinfo:
                    return fo, name
                return fo
            except Exception:
                name2 = os.path.normpath(os.path.join(head + '.zip', zipname))
                pass
    for i in (name2, name):
        if i and os.path.isfile(i):
            fo = open(i, mode)
            if pathinfo:
                return fo, i
            return fo
    if os.path.splitext(name)[1] == '.rml':
        raise IOError('Report %s doesn\'t exist or deleted : ' %str(name))
    raise IOError('File not found : %s' % name)


#----------------------------------------------------------
# iterables
#----------------------------------------------------------
def flatten(plist):
    """Flatten a list of elements into a uniqu list
    Author: Christophe Simonis (christophe@tinyerp.com)

    Examples:
    >>> flatten(['a'])
    ['a']
    >>> flatten('b')
    ['b']
    >>> flatten( [] )
    []
    >>> flatten( [[], [[]]] )
    []
    >>> flatten( [[['a','b'], 'c'], 'd', ['e', [], 'f']] )
    ['a', 'b', 'c', 'd', 'e', 'f']
    >>> t = (1,2,(3,), [4, 5, [6, [7], (8, 9), ([10, 11, (12, 13)]), [14, [], (15,)], []]])
    >>> flatten(t)
    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    """

    r = []
    for e in plist:
        if isinstance(e, (list, tuple)):
            for _e in flatten(e):
                r.append(_e)
        else:
            r.append(e)
    return r

def reverse_enumerate(l):
    """Like enumerate but in the other sens
    >>> a = ['a', 'b', 'c']
    >>> it = reverse_enumerate(a)
    >>> it.next()
    (2, 'c')
    >>> it.next()
    (1, 'b')
    >>> it.next()
    (0, 'a')
    >>> it.next()
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    StopIteration
    """
    return zip(range(len(l)-1, -1, -1), reversed(l))

#----------------------------------------------------------
# Emails
#----------------------------------------------------------
email_re = re.compile(r"""
    ([a-zA-Z][\w\.-]*[a-zA-Z0-9]     # username part
    @                                # mandatory @ sign
    [a-zA-Z0-9][\w\.-]*              # domain must start with a letter ... Ged> why do we include a 0-9 then?
     \.
     [a-z]{2,3}                      # TLD
    )
    """, re.VERBOSE)
res_re = re.compile(r"\[([0-9]+)\]", re.UNICODE)
command_re = re.compile("^Set-([a-z]+) *: *(.+)$", re.I + re.UNICODE)
reference_re = re.compile("<.*-openobject-(\\d+)@(.*)>", re.UNICODE)

priorities = {
    '1': '1 (Highest)',
    '2': '2 (High)',
    '3': '3 (Normal)',
    '4': '4 (Low)',
    '5': '5 (Lowest)',
}

def html2plaintext(html, body_id=None, encoding='utf-8'):
    ## (c) Fry-IT, www.fry-it.com, 2007
    ## <peter@fry-it.com>
    ## download here: http://www.peterbe.com/plog/html2plaintext


    """ from an HTML text, convert the HTML to plain text.
    If @body_id is provided then this is the tag where the
    body (not necessarily <body>) starts.
    """

    html = ustr(html)

    from lxml.etree import tostring
    try:
        from lxml.html.soupparser import fromstring
        kwargs = {}
    except ImportError:
        _logger.debug('tools.misc.html2plaintext: cannot use BeautifulSoup, fallback to lxml.etree.HTMLParser')
        from lxml.etree import fromstring, HTMLParser
        kwargs = dict(parser=HTMLParser())

    tree = fromstring(html, **kwargs)

    if body_id is not None:
        source = tree.xpath('//*[@id=%s]'%(body_id,))
    else:
        source = tree.xpath('//body')
    if len(source):
        tree = source[0]

    url_index = []
    i = 0
    for link in tree.findall('.//a'):
        url = link.get('href')
        if url:
            i += 1
            link.tag = 'span'
            link.text = '%s [%s]' % (link.text, i)
            url_index.append(url)

    html = ustr(tostring(tree, encoding=encoding))

    html = html.replace('<strong>','*').replace('</strong>','*')
    html = html.replace('<b>','*').replace('</b>','*')
    html = html.replace('<h3>','*').replace('</h3>','*')
    html = html.replace('<h2>','**').replace('</h2>','**')
    html = html.replace('<h1>','**').replace('</h1>','**')
    html = html.replace('<em>','/').replace('</em>','/')
    html = html.replace('<tr>', '\n')
    html = html.replace('</p>', '\n')
    html = re.sub('<br\s*/?>', '\n', html)
    html = re.sub('<.*?>', ' ', html)
    html = html.replace(' ' * 2, ' ')

    # strip all lines
    html = '\n'.join([x.strip() for x in html.splitlines()])
    html = html.replace('\n' * 2, '\n')

    for i, url in enumerate(url_index):
        if i == 0:
            html += '\n\n'
        html += ustr('[%s] %s\n') % (i+1, url)

    return html

def generate_tracking_message_id(openobject_id):
    """Returns a string that can be used in the Message-ID RFC822 header field so we
       can track the replies related to a given object thanks to the "In-Reply-To" or
       "References" fields that Mail User Agents will set.
    """
    return "<%s-openobject-%s@%s>" % (time.time(), openobject_id, socket.gethostname())

def _email_send(smtp_from, smtp_to_list, message, openobject_id=None, ssl=False, debug=False):
    """Low-level method to send directly a Message through the configured smtp server.
        :param smtp_from: RFC-822 envelope FROM (not displayed to recipient)
        :param smtp_to_list: RFC-822 envelope RCPT_TOs (not displayed to recipient)
        :param message: an email.message.Message to send
        :param debug: True if messages should be output to stderr before being sent,
                      and smtplib.SMTP put into debug mode.
        :return: True if the mail was delivered successfully to the smtp,
                 else False (+ exception logged)
    """
    class WriteToLogger(object):
        def __init__(self):
            self.logger = netsvc.Logger()

        def write(self, s):
            self.logger.notifyChannel('email_send', netsvc.LOG_DEBUG, s)

    if openobject_id:
        message['Message-Id'] = generate_tracking_message_id(openobject_id)

    try:
        smtp_server = config['smtp_server']

        if smtp_server.startswith('maildir:/'):
            from mailbox import Maildir
            maildir_path = smtp_server[8:]
            mdir = Maildir(maildir_path,factory=None, create = True)
            mdir.add(message.as_string(True))
            return True

        oldstderr = smtplib.stderr
        if not ssl: ssl = config.get('smtp_ssl', False)
        s = smtplib.SMTP()
        try:
            # in case of debug, the messages are printed to stderr.
            if debug:
                smtplib.stderr = WriteToLogger()

            s.set_debuglevel(int(bool(debug)))  # 0 or 1
            s.connect(smtp_server, config['smtp_port'])
            if ssl:
                s.ehlo()
                s.starttls()
                s.ehlo()

            if config['smtp_user'] or config['smtp_password']:
                s.login(config['smtp_user'], config['smtp_password'])

            s.sendmail(smtp_from, smtp_to_list, message.as_string())
        finally:
            try:
                s.quit()
                if debug:
                    smtplib.stderr = oldstderr
            except Exception:
                # ignored, just a consequence of the previous exception
                pass

    except Exception:
        _logger.error('could not deliver email', exc_info=True)
        return False

    return True


def email_send(email_from, email_to, subject, body, email_cc=None, email_bcc=None, reply_to=False,
               attach=None, openobject_id=False, ssl=False, debug=False, subtype='plain', x_headers=None, priority='3'):

    """Send an email.

    Arguments:

    `email_from`: A string used to fill the `From` header, if falsy,
                  config['email_from'] is used instead.  Also used for
                  the `Reply-To` header if `reply_to` is not provided

    `email_to`: a sequence of addresses to send the mail to.
    """
    if x_headers is None:
        x_headers = {}


    if not (email_from or config['email_from']):
        raise ValueError("Sending an email requires either providing a sender "
                         "address or having configured one")

    if not email_from: email_from = config.get('email_from', False)
    email_from = ustr(email_from).encode('utf-8')

    if not email_cc: email_cc = []
    if not email_bcc: email_bcc = []
    if not body: body = ''

    email_body = ustr(body).encode('utf-8')
    email_text = MIMEText(email_body or '',_subtype=subtype,_charset='utf-8')

    msg = MIMEMultipart()

    msg['Subject'] = Header(ustr(subject), 'utf-8')
    msg['From'] = email_from
    del msg['Reply-To']
    if reply_to:
        msg['Reply-To'] = reply_to
    else:
        msg['Reply-To'] = msg['From']
    msg['To'] = COMMASPACE.join(email_to)
    if email_cc:
        msg['Cc'] = COMMASPACE.join(email_cc)
    if email_bcc:
        msg['Bcc'] = COMMASPACE.join(email_bcc)
    msg['Date'] = formatdate(localtime=True)

    msg['X-Priority'] = priorities.get(priority, '3 (Normal)')

    # Add dynamic X Header
    for key, value in x_headers.items():
        msg['%s' % key] = str(value)

    if html2text and subtype == 'html':
        text = html2text(email_body.decode('utf-8')).encode('utf-8')
        alternative_part = MIMEMultipart(_subtype="alternative")
        alternative_part.attach(MIMEText(text, _charset='utf-8', _subtype='plain'))
        alternative_part.attach(email_text)
        msg.attach(alternative_part)
    else:
        msg.attach(email_text)

    if attach:
        for (fname,fcontent) in attach:
            part = MIMEBase('application', "octet-stream")
            part.set_payload( fcontent )
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename="%s"' % (fname,))
            msg.attach(part)

    return _email_send(email_from, flatten([email_to, email_cc, email_bcc]), msg, openobject_id=openobject_id, ssl=ssl, debug=debug)

#----------------------------------------------------------
# SMS
#----------------------------------------------------------
# text must be latin-1 encoded
def sms_send(user, password, api_id, text, to):
    import urllib.request, urllib.parse, urllib.error
    url = "http://api.urlsms.com/SendSMS.aspx"
    #url = "http://196.7.150.220/http/sendmsg"
    params = urllib.parse.urlencode({'UserID': user, 'Password': password, 'SenderID': api_id, 'MsgText': text, 'RecipientMobileNo':to})
    urllib.request.urlopen(url+"?"+params)
    # FIXME: Use the logger if there is an error
    return True

#---------------------------------------------------------
# Class that stores an updateable string (used in wizards)
#---------------------------------------------------------
class UpdateableStr(local):

    def __init__(self, string=''):
        self.string = string

    def __str__(self):
        return str(self.string)

    def __repr__(self):
        return str(self.string)

    def __bool__(self):
        return bool(self.string)


class UpdateableDict(local):
    '''Stores an updateable dict to use in wizards'''

    def __init__(self, dict=None):
        if dict is None:
            dict = {}
        self.dict = dict

    def __str__(self):
        return str(self.dict)

    def __repr__(self):
        return str(self.dict)

    def clear(self):
        return self.dict.clear()

    def keys(self):
        return list(self.dict.keys())

    def __setitem__(self, i, y):
        self.dict.__setitem__(i, y)

    def __getitem__(self, i):
        return self.dict.__getitem__(i)

    def copy(self):
        return self.dict.copy()

    def iteritems(self):
        return iter(self.dict.items())

    def iterkeys(self):
        return iter(self.dict.keys())

    def itervalues(self):
        return iter(self.dict.values())

    def pop(self, k, d=None):
        return self.dict.pop(k, d)

    def popitem(self):
        return self.dict.popitem()

    def setdefault(self, k, d=None):
        return self.dict.setdefault(k, d)

    def update(self, E, **F):
        return self.dict.update(E, F)

    def values(self):
        return list(self.dict.values())

    def get(self, k, d=None):
        return self.dict.get(k, d)

    def has_key(self, k):
        return k in self.dict

    def items(self):
        return list(self.dict.items())

    def __cmp__(self, y):
        return self.dict.__cmp__(y)

    def __contains__(self, k):
        return self.dict.__contains__(k)

    def __delitem__(self, y):
        return self.dict.__delitem__(y)

    def __eq__(self, y):
        return self.dict.__eq__(y)

    def __ge__(self, y):
        return self.dict.__ge__(y)

    def __gt__(self, y):
        return self.dict.__gt__(y)

    def __hash__(self):
        return self.dict.__hash__()

    def __iter__(self):
        return self.dict.__iter__()

    def __le__(self, y):
        return self.dict.__le__(y)

    def __len__(self):
        return self.dict.__len__()

    def __lt__(self, y):
        return self.dict.__lt__(y)

    def __ne__(self, y):
        return self.dict.__ne__(y)


# Don't use ! Use res.currency.round()
class currency(float):

    def __init__(self, value, accuracy=2, rounding=None):
        if rounding is None:
            rounding=10**-accuracy
        self.rounding=rounding
        self.accuracy=accuracy

    def __new__(cls, value, accuracy=2, rounding=None):
        return float.__new__(cls, round(value, accuracy))

    #def __str__(self):
    #   display_value = int(self*(10**(-self.accuracy))/self.rounding)*self.rounding/(10**(-self.accuracy))
    #   return str(display_value)


def is_hashable(h):
    try:
        hash(h)
        return True
    except TypeError:
        return False

def _generate_keys(multi, dbname, kwargs2, reset_fields=None):
    """
    Generate keys depending of the arguments and the mutli value
    """

    if reset_fields is None:
        reset_fields = []
    def to_tuple(d):
        pairs = list(d.items())
        pairs.sort(key=lambda k_v: '%s'%k_v[0])
        for i, (k, v) in enumerate(pairs):
            if isinstance(v, dict):
                pairs[i] = (k, to_tuple(v))
            if isinstance(v, (list, set)):
                pairs[i] = (k, tuple(v))
            elif not is_hashable(v):
                pairs[i] = (k, repr(v))
        return tuple(pairs)

    if not multi:
        key = (('dbname', dbname),) + to_tuple(kwargs2)
        yield key, None
    else:
        multis = kwargs2[multi][:]
        for id in multis:
            kwargs2[multi] = (id,)
            for reset_field in reset_fields:
                kwargs2[reset_field] = None
            key = (('dbname', dbname),) + to_tuple(kwargs2)
            yield key, id

class cache(object):
    """
    Use it as a decorator of the function you plan to cache
    Timeout: 0 = no timeout, otherwise in seconds
    """

    __caches = []

    def __init__(self, timeout=None, skiparg=2, multi=None, size=8192):
        assert skiparg >= 2 # at least self and cr
        if timeout is None:
            self.timeout = config['cache_timeout']
        else:
            self.timeout = timeout
        self.skiparg = skiparg
        self.multi = multi
        self.lasttime = time.time()
        self.cache = LRU(size)      # TODO take size from config
        self.fun = None
        cache.__caches.append(self)

    def _unify_args(self, *args, **kwargs):
        # Update named arguments with positional argument values (without self and cr)
        kwargs2 = self.fun_default_values.copy()
        kwargs2.update(kwargs)
        kwargs2.update(dict(list(zip(self.fun_arg_names, args[self.skiparg-2:]))))
        return kwargs2

    def clear(self, dbname, *args, **kwargs):
        """clear the cache for database dbname
            if *args and **kwargs are both empty, clear all the keys related to this database
        """
        if not args and not kwargs:
            self.cache.del_map(lambda key: key[0][1] == dbname)
        else:
            kwargs2 = self._unify_args(*args, **kwargs)
            generated_keys = [x for x, y in _generate_keys(self.multi, dbname, kwargs2)]
            self.cache.del_map(lambda key: key in generated_keys)

    @classmethod
    def clean_caches_for_db(cls, dbname):
        for c in cls.__caches:
            c.clear(dbname)

    def __call__(self, fn):
        if self.fun is not None:
            raise Exception("Can not use a cache instance on more than one function")
        self.fun = fn

        argspec = inspect.getargspec(fn)
        self.fun_arg_names = argspec[0][self.skiparg:]
        self.fun_default_values = {}
        if argspec[3]:
            self.fun_default_values = dict(list(zip(self.fun_arg_names[-len(argspec[3]):], argspec[3])))

        def cached_result(self2, cr, *args, **kwargs):
            if time.time()-int(self.timeout) > self.lasttime:
                self.lasttime = time.time()
                t = time.time()-int(self.timeout)
                self.cache.del_map(lambda key: self.cache[key][1] < t)

            kwargs2 = self._unify_args(*args, **kwargs)

            result = {}
            notincache = {}
            for key, id in _generate_keys(self.multi, cr.dbname, kwargs2):
                cache_value = self.cache.get(key)
                if cache_value is not None:
                    result[id] = cache_value[0]
                else:
                    notincache[id] = key

            if notincache:
                if self.multi:
                    kwargs2[self.multi] = list(notincache.keys())

                result2 = fn(self2, cr, *args[:self.skiparg-2], **kwargs2)
                if not self.multi:
                    key = notincache[None]
                    self.cache[key] = (result2, time.time())
                    result[None] = result2
                else:
                    for id in result2:
                        key = notincache[id]
                        self.cache[key] = (result2[id], time.time())
                    result.update(result2)

            if not self.multi:
                return result[None]
            return result

        cached_result.clear_cache = self.clear
        return cached_result

class read_cache(object):
    """
    Use it as a decorator of the function you plan to cache
    Timeout: 0 = no timeout, otherwise in seconds
    """

    __caches = []

    def __init__(self, prefetch=None, context=None, timeout=None, size=8192):
        if prefetch is None:
            prefetch = []
        if context is None:
            context = []
        if timeout is None:
            self.timeout = config['cache_timeout']
        else:
            self.timeout = timeout
        self.lasttime = time.time()
        self.cache = LRU(size)
        self.fun = None
        self._context = context
        read_cache.__caches.append(self)

    @classmethod
    def clean_caches_for_db(cls, dbname):
        for c in cls.__caches:
            c.clear(dbname)

    def _unify_args(self, *args, **kwargs):
        # Update named arguments with positional argument values (without self and cr)
        kwargs2 = self.fun_default_values.copy()
        kwargs2.update(kwargs)
        kwargs2.update(dict(list(zip(self.fun_arg_names, args))))
        return kwargs2

    def clear(self, dbname):

        """clear the cache for database dbname
        """
        self.cache.del_map(lambda key: key[0][1] == dbname)

    def split_order_by_clause(self, order_by):
        # we have to take into account the order whenever we fetch data
        #  otherwise we won't be able to sort the result set
        order_by = (order_by or '').strip()
        if not order_by:
            return []
        else:
            ret = []
            fields = order_by.split(',')
            for field in fields:
                field = field.strip().split()
                if len(field) == 1 or (len(field) == 2 and field[1].lower() == 'asc'):
                    ret.append((True, field[0]))
                elif len(field) == 2 and field[1].lower() == 'desc':
                    ret.append((False, field[0]))
            return ret

    def sort_orderby(self, clause, rows):
        def key_compare(row1, row2):
            for asc, field in clause:
                f1 = row1[field]
                f2 = row2[field]
                ret = (f1 > f2) - (f1 < f2)  # cmp
                if ret != 0:
                    return ret if asc else -ret
            return 0
        return sorted(rows, key=cmp_to_key(key_compare))

    def filter_dict(self, keys_to_remove, rowset):
        ret = []

        for row in rowset:
            new_row = dict(**row)
            for field in keys_to_remove:
                if field in new_row and field != 'id':
                    new_row.pop(field)
            ret.append(new_row)

        return ret

    def __call__(self, fn):
        if self.fun is not None:
            raise Exception("Can not use a cache instance on more than one function")
        self.fun = fn

        argspec = inspect.getargspec(fn)
        # get rid of self and the database cursor
        self.fun_arg_names = argspec[0][2:]
        self.fun_default_values = {}
        if argspec[3]:
            self.fun_default_values = dict(list(zip(self.fun_arg_names[-len(argspec[3]):], argspec[3])))

        self._sort = None

        def cached_result(self2, cr, *args, **kwargs):
            if time.time()-int(self.timeout) > self.lasttime:
                self.lasttime = time.time()
                t = time.time()-int(self.timeout)
                self.cache.del_map(lambda key: self.cache[key][1] < t)

            if self._sort is None:
                order_by = self2._parent_order or self2._order
                self._sort = order_by_clauses = self.split_order_by_clause(order_by)
            else:
                order_by_clauses = self._sort

            kwargs2 = self._unify_args(*args, **kwargs)

            # we have to keep in mind the fields that have to be returned
            #  they will be erased when generating the key in the cache
            if kwargs2['fields_to_read']:
                fields_to_read = kwargs2['fields_to_read']
            else:
                fields_to_read = list(self2._columns.keys())

            # if no field is required => we return all the fields
            fields_pre = [f for f in fields_to_read if
                          f == self2.CONCURRENCY_CHECK_FIELD
                          or (f in self2._columns and getattr(self2._columns[f], '_classic_write'))
                          ] + list(self2._inherits.values())

            include_sort = False
            fields_to_query = set(fields_to_read)
            # we have to keep track of the fields that are used for sorting but
            #  are not asked by the caller. We'll have to remove them in the returned
            #  resultset.
            fields_to_remove = set([])
            if fields_pre:
                include_sort = True

                fields_to_add = [x[1] for x in order_by_clauses]

                for field_to_add in fields_to_add:
                    if field_to_add not in fields_to_query:
                        fields_to_remove.add(field_to_add)
                        fields_to_query.add(field_to_add)
            else:
                ordered_ids = {}
                for position, given_id in enumerate(kwargs2['ids']):
                    ordered_ids[given_id] = position

            previous_context = kwargs2['context']

            # we have to check if we discard some values from the context
            simplified_context = {}
            for key, value in previous_context.items():
                if key in self._context:
                    simplified_context[key] = value

            # we have to remove from the context what doesn't impact the results
            kwargs2['context'] = simplified_context

            result = []
            notincache = {}
            for key, id in _generate_keys('ids', cr.dbname, kwargs2, ['fields_to_read']):
                cache_value = self.cache.get(key)
                if cache_value is not None:
                    # we have to find if we have all the required fields in the cache
                    fields_already_in_the_cache = list(cache_value[0].keys())
                    if set(fields_to_query).issubset(set(fields_already_in_the_cache)):
                        # all the values are already in the cache, we don't
                        #  have to ask the DB for more information
                        row = {'id': int(id)}
                        for field in fields_to_query:
                            row[field] = cache_value[0][field]
                        result.append(row)
                    else:
                        # we have to look for the new values
                        #  we fetch all of them (not optimal since some fields
                        #  could already exist)
                        notincache[int(id)] = key
                else:
                    notincache[int(id)] = key

            if notincache:
                kwargs2['ids'] = list(notincache.keys())

                kwargs2['fields_to_read'] = fields_to_query
                kwargs2['context'] = previous_context

                result2 = fn(self2, cr, **kwargs2)

                # we have to add the new rows in the resultset
                for id, value in [(x['id'], x) for x in result2]:
                    key = notincache[int(id)]
                    cache_value = self.cache.get(key)
                    if cache_value is not None:
                        value_in_cache, t = cache_value
                    else:
                        value_in_cache, t = {}, time.time()

                    for field in fields_to_query:
                        # sometimes we don't get the column we ask to fetch...
                        #  (it happens with inherit_id for ir_action_window)
                        if field in value:
                            value_in_cache[field] = value[field]
                    value_in_cache['id'] = int(id)

                    self.cache[key] = (value_in_cache, t)

                    result.append(value)

            if include_sort:
                return self.filter_dict(fields_to_remove, self.sort_orderby(order_by_clauses, result))
            else:
                # id we don't sort, we have to use the same order as the given IDs, otherwise
                #  the search won't be sorted in the right order (they use only IDs at some points)
                result.sort(key=lambda x : ordered_ids[x['id']])

                return result

        cached_result.clear_cache = self.clear
        return cached_result

def to_xml(s):
    return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def get_encodings(hint_encoding='utf-8'):
    fallbacks = {
        'latin1': 'latin9',
        'iso-8859-1': 'iso8859-15',
        'cp1252': '1252',
    }
    if hint_encoding:
        yield hint_encoding
        if hint_encoding.lower() in fallbacks:
            yield fallbacks[hint_encoding.lower()]

    # some defaults (also taking care of pure ASCII)
    for charset in ['utf8','latin1']:
        if not (hint_encoding) or (charset.lower() != hint_encoding.lower()):
            yield charset

    from locale import getpreferredencoding
    prefenc = getpreferredencoding()
    if prefenc and prefenc.lower() != 'utf-8':
        yield prefenc
        prefenc = fallbacks.get(prefenc.lower())
        if prefenc:
            yield prefenc


def ustr(value, hint_encoding='utf8'):
    """This method is similar to the builtin `str` method, except
       it will return unicode() string.

    @param value: the value to convert
    @param hint_encoding: an optional encoding that was detected
                          upstream and should be tried first to
                          decode ``value``.

    @rtype: unicode
    @return: unicode string
    """
    if isinstance(value, Exception):
        return '%s' % value

    if isinstance(value, str):
        return value

    if isinstance(value, bytes):
        return str(value, hint_encoding)

    try:
        return str(value)
    except Exception:
        raise UnicodeError('unable to convert %r' % (value,))

    #for ln in get_encodings(hint_encoding):
    #    try:
    #        return str(value, ln)
    #    except Exception:
    #        pass
    #raise UnicodeError('unable to convert %r' % (value,))


def exception_to_unicode(e):
    if hasattr(e, 'args'):
        return "\n".join((ustr(a) for a in e.args))
    try:
        return ustr(e)
    except Exception:
        return "Unknown message"



def get_iso_codes(lang):
    if lang.find('_') != -1:
        if lang.split('_')[0] == lang.split('_')[1].lower():
            lang = lang.split('_')[0]
    return lang

def get_languages():
    # The codes below are those from Launchpad's Rosetta, with the exception
    # of some trivial codes where the Launchpad code is xx and we have xx_XX.
    languages={
        'ab_RU': 'Abkhazian / аҧсуа',
        'ar_AR': 'Arabic / الْعَرَبيّة',
        'bg_BG': 'Bulgarian / български език',
        'bs_BS': 'Bosnian / bosanski jezik',
        'ca_ES': 'Catalan / Català',
        'cs_CZ': 'Czech / Čeština',
        'da_DK': 'Danish / Dansk',
        'de_DE': 'German / Deutsch',
        'el_GR': 'Greek / Ελληνικά',
        'en_CA': 'English (CA)',
        'en_GB': 'English (UK)',
        'en_US': 'English (US)',
        'es_AR': 'Spanish (AR) / Español (AR)',
        'es_BO': 'Spanish (BO) / Español (BO)',
        'es_CL': 'Spanish (CL) / Español (CL)',
        'es_CO': 'Spanish (CO) / Español (CO)',
        'es_CR': 'Spanish (CR) / Español (CR)',
        'es_DO': 'Spanish (DO) / Español (DO)',
        'es_EC': 'Spanish (EC) / Español (EC)',
        'es_ES': 'Spanish / Español',
        'es_GT': 'Spanish (GT) / Español (GT)',
        'es_HN': 'Spanish (HN) / Español (HN)',
        'es_MX': 'Spanish (MX) / Español (MX)',
        'es_NI': 'Spanish (NI) / Español (NI)',
        'es_PA': 'Spanish (PA) / Español (PA)',
        'es_PE': 'Spanish (PE) / Español (PE)',
        'es_PR': 'Spanish (PR) / Español (PR)',
        'es_PY': 'Spanish (PY) / Español (PY)',
        'es_SV': 'Spanish (SV) / Español (SV)',
        'es_UY': 'Spanish (UY) / Español (UY)',
        'es_VE': 'Spanish (VE) / Español (VE)',
        'et_EE': 'Estonian / Eesti keel',
        'fa_IR': 'Persian / فارس',
        'fi_FI': 'Finnish / Suomi',
        'fr_BE': 'French (BE) / Français (BE)',
        'fr_CH': 'French (CH) / Français (CH)',
        'fr_FR': 'French / Français',
        'gl_ES': 'Galician / Galego',
        'gu_IN': 'Gujarati / ગુજરાતી',
        'he_IL': 'Hebrew / עִבְרִי',
        'hi_IN': 'Hindi / हिंदी',
        'hr_HR': 'Croatian / hrvatski jezik',
        'hu_HU': 'Hungarian / Magyar',
        'id_ID': 'Indonesian / Bahasa Indonesia',
        'it_IT': 'Italian / Italiano',
        'iu_CA': 'Inuktitut / ᐃᓄᒃᑎᑐᑦ',
        'ja_JP': 'Japanese / 日本語',
        'ko_KP': 'Korean (KP) / 한국어 (KP)',
        'ko_KR': 'Korean (KR) / 한국어 (KR)',
        'lt_LT': 'Lithuanian / Lietuvių kalba',
        'lv_LV': 'Latvian / latviešu valoda',
        'ml_IN': 'Malayalam / മലയാളം',
        'mn_MN': 'Mongolian / монгол',
        'nb_NO': 'Norwegian Bokmål / Norsk bokmål',
        'nl_NL': 'Dutch / Nederlands',
        'nl_BE': 'Flemish (BE) / Vlaams (BE)',
        'oc_FR': 'Occitan (FR, post 1500) / Occitan',
        'pl_PL': 'Polish / Język polski',
        'pt_BR': 'Portugese (BR) / Português (BR)',
        'pt_PT': 'Portugese / Português',
        'ro_RO': 'Romanian / română',
        'ru_RU': 'Russian / русский язык',
        'si_LK': 'Sinhalese / සිංහල',
        'sl_SI': 'Slovenian / slovenščina',
        'sk_SK': 'Slovak / Slovenský jazyk',
        'sq_AL': 'Albanian / Shqip',
        'sr_RS': 'Serbian (Cyrillic) / српски',
        'sr@latin': 'Serbian (Latin) / srpski',
        'sv_SE': 'Swedish / svenska',
        'te_IN': 'Telugu / తెలుగు',
        'tr_TR': 'Turkish / Türkçe',
        'vi_VN': 'Vietnamese / Tiếng Việt',
        'uk_UA': 'Ukrainian / українська',
        'ur_PK': 'Urdu / اردو',
        'zh_CN': 'Chinese (CN) / 简体中文',
        'zh_HK': 'Chinese (HK)',
        'zh_TW': 'Chinese (TW) / 正體字',
        'th_TH': 'Thai / ภาษาไทย',
        'tlh_TLH': 'Klingon',
    }
    return languages

def scan_languages():
    # Now it will take all languages from get languages function without filter it with base module languages
    lang_dict = get_languages()
    ret = [(lang, lang_dict.get(lang, lang)) for lang in list(lang_dict)]
    ret.sort(key=lambda k:k[1])
    return ret


def get_user_companies(cr, user):
    def _get_company_children(cr, ids):
        if not ids:
            return []
        cr.execute('SELECT id FROM res_company WHERE parent_id IN %s', (tuple(ids),))
        res = [x[0] for x in cr.fetchall()]
        res.extend(_get_company_children(cr, res))
        return res
    cr.execute('SELECT company_id FROM res_users WHERE id=%s', (user,))
    user_comp = cr.fetchone()[0]
    if not user_comp:
        return []
    return [user_comp] + _get_company_children(cr, [user_comp])

def mod10r(number):
    """
    Input number : account or invoice number
    Output return: the same number completed with the recursive mod10
    key
    """
    codec=[0,9,4,6,8,2,7,1,3,5]
    report = 0
    result=""
    for digit in number:
        result += digit
        if digit.isdigit():
            report = codec[ (int(digit) + report) % 10 ]
    return result + str((10 - report) % 10)

def human_size(data):
    """
    Return the size in a human readable format
    """
    units = ('Bytes', 'KB', 'MB', 'GB', 'TB')
    if isinstance(data, (str, bytes)):
        size = float(len(data))
    elif isinstance(data, int):
        size = float(data)
    elif isinstance(data, float):
        size = data
    else:
        return '0 Bytes'
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size = size / 1024
        unit_index += 1
    return "%0.2f %s" % (size, units[unit_index])

def logged(f):
    from tools.func import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        from pprint import pformat

        vector = ['Call -> function: %r' % f]
        for i, arg in enumerate(args):
            vector.append('  arg %02d: %s' % (i, pformat(arg)))
        for key, value in list(kwargs.items()):
            vector.append('  kwarg %10s: %s' % (key, pformat(value)))

        timeb4 = time.time()
        res = f(*args, **kwargs)

        vector.append('  result: %s' % pformat(res))
        vector.append('  time delta: %s' % (time.time() - timeb4))
        netsvc.Logger().notifyChannel('logged', netsvc.LOG_DEBUG, '\n'.join(vector))
        return res

    return wrapper

class profile(object):
    def __init__(self, fname=None):
        self.fname = fname

    def __call__(self, f):
        from tools.func import wraps

        @wraps(f)
        def wrapper(*args, **kwargs):
            class profile_wrapper(object):
                def __init__(self):
                    self.result = None
                def __call__(self):
                    self.result = f(*args, **kwargs)
            pw = profile_wrapper()
            import cProfile
            fname = self.fname or ("%s.cprof" % (f.__name__,))
            cProfile.runctx('pw()', globals(), locals(), filename=fname)
            return pw.result

        return wrapper

def debug(what):
    """
        This method allow you to debug your code without print
        Example:
        >>> def func_foo(bar)
        ...     baz = bar
        ...     debug(baz)
        ...     qnx = (baz, bar)
        ...     debug(qnx)
        ...
        >>> func_foo(42)

        This will output on the logger:

            [Wed Dec 25 00:00:00 2008] DEBUG:func_foo:baz = 42
            [Wed Dec 25 00:00:00 2008] DEBUG:func_foo:qnx = (42, 42)

        To view the DEBUG lines in the logger you must start the server with the option
            --log-level=debug

    """
    warnings.warn("The tools.debug() method is deprecated, please use logging.",
                  DeprecationWarning, stacklevel=2)
    from inspect import stack
    from pprint import pformat
    st = stack()[1]
    param = re.split("debug *\((.+)\)", st[4][0].strip())[1].strip()
    while param.count(')') > param.count('('): param = param[:param.rfind(')')]
    what = pformat(what)
    if param != what:
        what = "%s = %s" % (param, what)
    logging.getLogger(st[3]).debug(what)


__icons_list = ['STOCK_ABOUT', 'STOCK_ADD', 'STOCK_APPLY', 'STOCK_BOLD',
                'STOCK_CANCEL', 'STOCK_CDROM', 'STOCK_CLEAR', 'STOCK_CLOSE', 'STOCK_COLOR_PICKER',
                'STOCK_CONNECT', 'STOCK_CONVERT', 'STOCK_COPY', 'STOCK_CUT', 'STOCK_DELETE',
                'STOCK_DIALOG_AUTHENTICATION', 'STOCK_DIALOG_ERROR', 'STOCK_DIALOG_INFO',
                'STOCK_DIALOG_QUESTION', 'STOCK_DIALOG_WARNING', 'STOCK_DIRECTORY', 'STOCK_DISCONNECT',
                'STOCK_DND', 'STOCK_DND_MULTIPLE', 'STOCK_EDIT', 'STOCK_EXECUTE', 'STOCK_FILE',
                'STOCK_FIND', 'STOCK_FIND_AND_REPLACE', 'STOCK_FLOPPY', 'STOCK_GOTO_BOTTOM',
                'STOCK_GOTO_FIRST', 'STOCK_GOTO_LAST', 'STOCK_GOTO_TOP', 'STOCK_GO_BACK',
                'STOCK_GO_DOWN', 'STOCK_GO_FORWARD', 'STOCK_GO_UP', 'STOCK_HARDDISK',
                'STOCK_HELP', 'STOCK_HOME', 'STOCK_INDENT', 'STOCK_INDEX', 'STOCK_ITALIC',
                'STOCK_JUMP_TO', 'STOCK_JUSTIFY_CENTER', 'STOCK_JUSTIFY_FILL',
                'STOCK_JUSTIFY_LEFT', 'STOCK_JUSTIFY_RIGHT', 'STOCK_MEDIA_FORWARD',
                'STOCK_MEDIA_NEXT', 'STOCK_MEDIA_PAUSE', 'STOCK_MEDIA_PLAY',
                'STOCK_MEDIA_PREVIOUS', 'STOCK_MEDIA_RECORD', 'STOCK_MEDIA_REWIND',
                'STOCK_MEDIA_STOP', 'STOCK_MISSING_IMAGE', 'STOCK_NETWORK', 'STOCK_NEW',
                'STOCK_NO', 'STOCK_OK', 'STOCK_OPEN', 'STOCK_PASTE', 'STOCK_PREFERENCES',
                'STOCK_PRINT', 'STOCK_PRINT_PREVIEW', 'STOCK_PROPERTIES', 'STOCK_QUIT',
                'STOCK_REDO', 'STOCK_REFRESH', 'STOCK_REMOVE', 'STOCK_REVERT_TO_SAVED',
                'STOCK_SAVE', 'STOCK_SAVE_AS', 'STOCK_SELECT_COLOR', 'STOCK_SELECT_FONT',
                'STOCK_SORT_ASCENDING', 'STOCK_SORT_DESCENDING', 'STOCK_SPELL_CHECK',
                'STOCK_STOP', 'STOCK_STRIKETHROUGH', 'STOCK_UNDELETE', 'STOCK_UNDERLINE',
                'STOCK_UNDO', 'STOCK_UNINDENT', 'STOCK_YES', 'STOCK_ZOOM_100',
                'STOCK_ZOOM_FIT', 'STOCK_ZOOM_IN', 'STOCK_ZOOM_OUT',
                'terp-account', 'terp-crm', 'terp-mrp', 'terp-product', 'terp-purchase',
                'terp-sale', 'terp-tools', 'terp-administration', 'terp-hr', 'terp-partner',
                'terp-project', 'terp-report', 'terp-stock', 'terp-calendar', 'terp-graph',
                'terp-check','terp-go-month','terp-go-year','terp-go-today','terp-document-new','terp-camera_test',
                'terp-emblem-important','terp-gtk-media-pause','terp-gtk-stop','terp-gnome-cpu-frequency-applet+',
                'terp-dialog-close','terp-gtk-jump-to-rtl','terp-gtk-jump-to-ltr','terp-accessories-archiver',
                'terp-stock_align_left_24','terp-stock_effects-object-colorize','terp-go-home','terp-gtk-go-back-rtl',
                'terp-gtk-go-back-ltr','terp-personal','terp-personal-','terp-personal+','terp-accessories-archiver-minus',
                'terp-accessories-archiver+','terp-stock_symbol-selection','terp-call-start','terp-dolar',
                'terp-face-plain','terp-folder-blue','terp-folder-green','terp-folder-orange','terp-folder-yellow',
                'terp-gdu-smart-failing','terp-go-week','terp-gtk-select-all','terp-locked','terp-mail-forward',
                'terp-mail-message-new','terp-mail-replied','terp-rating-rated','terp-stage','terp-stock_format-scientific',
                'terp-dolar_ok!','terp-idea','terp-stock_format-default','terp-mail-','terp-mail_delete'
                ]

def icons(*a, **kw):
    global __icons_list
    return [(x, x) for x in __icons_list ]

def extract_zip_file(zip_file, outdirectory):
    zf = zipfile.ZipFile(zip_file, 'r')
    out = outdirectory
    for path in zf.namelist():
        tgt = os.path.join(out, path)
        tgtdir = os.path.dirname(tgt)
        if not os.path.exists(tgtdir):
            os.makedirs(tgtdir)

        if not tgt.endswith(os.sep):
            fp = open(tgt, 'wb')
            fp.write(zf.read(path))
            fp.close()
    zf.close()

def detect_ip_addr():
    """Try a very crude method to figure out a valid external
       IP or hostname for the current machine. Don't rely on this
       for binding to an interface, but it could be used as basis
       for constructing a remote URL to the server.
    """
    def _detect_ip_addr():
        from array import array
        from struct import pack, unpack

        try:
            import fcntl
        except ImportError:
            fcntl = None

        ip_addr = None

        if not fcntl: # not UNIX:
            host = socket.gethostname()
            ip_addr = socket.gethostbyname(host)
        else: # UNIX:
            # get all interfaces:
            nbytes = 128 * 32
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            names = array('B', '\0' * nbytes)
            #print 'names: ', names
            outbytes = unpack('iL', fcntl.ioctl( s.fileno(), 0x8912, pack('iL', nbytes, names.buffer_info()[0])))[0]
            namestr = names.tostring()

            # try 64 bit kernel:
            for i in range(0, outbytes, 40):
                name = namestr[i:i+16].split('\0', 1)[0]
                if name != 'lo':
                    ip_addr = socket.inet_ntoa(namestr[i+20:i+24])
                    break

            # try 32 bit kernel:
            if ip_addr is None:
                ifaces = [_f for _f in [namestr[i:i+32].split('\0', 1)[0] for i in range(0, outbytes, 32)] if _f]

                for ifname in [iface for iface in ifaces if iface != 'lo']:
                    ip_addr = socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915, pack('256s', ifname[:15]))[20:24])
                    break

        return ip_addr or 'localhost'

    try:
        ip_addr = _detect_ip_addr()
    except Exception:
        ip_addr = 'localhost'
    return ip_addr

# RATIONALE BEHIND TIMESTAMP CALCULATIONS AND TIMEZONE MANAGEMENT:
#  The server side never does any timestamp calculation, always
#  sends them in a naive (timezone agnostic) format supposed to be
#  expressed within the server timezone, and expects the clients to
#  provide timestamps in the server timezone as well.
#  It stores all timestamps in the database in naive format as well,
#  which also expresses the time in the server timezone.
#  For this reason the server makes its timezone name available via the
#  common/timezone_get() rpc method, which clients need to read
#  to know the appropriate time offset to use when reading/writing
#  times.
def get_win32_timezone():
    """Attempt to return the "standard name" of the current timezone on a win32 system.
       @return: the standard name of the current win32 timezone, or False if it cannot be found.
    """
    res = False
    if (sys.platform == "win32"):
        try:
            import winreg
            hklm = winreg.ConnectRegistry(None,winreg.HKEY_LOCAL_MACHINE)
            current_tz_key = winreg.OpenKey(hklm, r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation", 0,winreg.KEY_ALL_ACCESS)
            res = str(winreg.QueryValueEx(current_tz_key,"StandardName")[0])  # [0] is value, [1] is type code
            winreg.CloseKey(current_tz_key)
            winreg.CloseKey(hklm)
        except Exception:
            pass
    return res

def detect_server_timezone():
    """Attempt to detect the timezone to use on the server side.
       Defaults to UTC if no working timezone can be found.
       @return: the timezone identifier as expected by pytz.timezone.
    """
    try:
        import pytz
    except Exception:
        netsvc.Logger().notifyChannel("detect_server_timezone", netsvc.LOG_WARNING,
                                      "Python pytz module is not available. Timezone will be set to UTC by default.")
        return 'UTC'

    # Option 1: the configuration option (did not exist before, so no backwards compatibility issue)
    # Option 2: to be backwards compatible with 5.0 or earlier, the value from time.tzname[0], but only if it is known to pytz
    # Option 3: the environment variable TZ
    sources = [ (config['timezone'], 'OpenERP configuration'),
                (time.tzname[0], 'time.tzname'),
                (os.environ.get('TZ',False),'TZ environment variable'), ]
    # Option 4: OS-specific: /etc/timezone on Unix
    if (os.path.exists("/etc/timezone")):
        tz_value = False
        try:
            f = open("/etc/timezone")
            tz_value = f.read(128).strip()
        except Exception:
            pass
        finally:
            f.close()
        sources.append((tz_value,"/etc/timezone file"))
    # Option 5: timezone info from registry on Win32
    if (sys.platform == "win32"):
        # Timezone info is stored in windows registry.
        # However this is not likely to work very well as the standard name
        # of timezones in windows is rarely something that is known to pytz.
        # But that's ok, it is always possible to use a config option to set
        # it explicitly.
        sources.append((get_win32_timezone(),"Windows Registry"))

    for (value,source) in sources:
        if value:
            try:
                tz = pytz.timezone(value)
                netsvc.Logger().notifyChannel("detect_server_timezone", netsvc.LOG_INFO,
                                              "Using timezone %s obtained from %s." % (tz.zone,source))
                return value
            except pytz.UnknownTimeZoneError:
                netsvc.Logger().notifyChannel("detect_server_timezone", netsvc.LOG_WARNING,
                                              "The timezone specified in %s (%s) is invalid, ignoring it." % (source,value))

    netsvc.Logger().notifyChannel("detect_server_timezone", netsvc.LOG_WARNING,
                                  "No valid timezone could be detected, using default UTC timezone. You can specify it explicitly with option 'timezone' in the server configuration.")
    return 'UTC'

def get_server_timezone():
    # timezone detection is safe in multithread, so lazy init is ok here
    if (not config['timezone']):
        config['timezone'] = detect_server_timezone()
    return config['timezone']


DEFAULT_SERVER_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_SERVER_TIME_FORMAT = "%H:%M:%S"
DEFAULT_SERVER_DATETIME_FORMAT = "%s %s" % (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_TIME_FORMAT)

# Python's strftime supports only the format directives
# that are available on the platform's libc, so in order to
# be cross-platform we map to the directives required by
# the C standard (1989 version), always available on platforms
# with a C standard implementation.
DATETIME_FORMATS_MAP = {
    '%C': '', # century
    '%D': '%m/%d/%Y', # modified %y->%Y
    '%e': '%d',
    '%E': '', # special modifier
    '%F': '%Y-%m-%d',
    '%g': '%Y', # modified %y->%Y
    '%G': '%Y',
    '%h': '%b',
    '%k': '%H',
    '%l': '%I',
    '%n': '\n',
    '%O': '', # special modifier
    '%P': '%p',
    '%R': '%H:%M',
    '%r': '%I:%M:%S %p',
    '%s': '', #num of seconds since epoch
    '%T': '%H:%M:%S',
    '%t': ' ', # tab
    '%u': ' %w',
    '%V': '%W',
    '%y': '%Y', # Even if %y works, it's ambiguous, so we should use %Y
    '%+': '%Y-%m-%d %H:%M:%S',

    # %Z is a special case that causes 2 problems at least:
    #  - the timezone names we use (in res_user.context_tz) come
    #    from pytz, but not all these names are recognized by
    #    strptime(), so we cannot convert in both directions
    #    when such a timezone is selected and %Z is in the format
    #  - %Z is replaced by an empty string in strftime() when
    #    there is not tzinfo in a datetime value (e.g when the user
    #    did not pick a context_tz). The resulting string does not
    #    parse back if the format requires %Z.
    # As a consequence, we strip it completely from format strings.
    # The user can always have a look at the context_tz in
    # preferences to check the timezone.
    '%z': '',
    '%Z': '',
}

def server_to_local_timestamp(src_tstamp_str, src_format, dst_format, dst_tz_name,
                              tz_offset=True, ignore_unparsable_time=True):
    """
    Convert a source timestamp string into a destination timestamp string, attempting to apply the
    correct offset if both the server and local timezone are recognized, or no
    offset at all if they aren't or if tz_offset is false (i.e. assuming they are both in the same TZ).

    WARNING: This method is here to allow formatting dates correctly for inclusion in strings where
             the client would not be able to format/offset it correctly. DO NOT use it for returning
             date fields directly, these are supposed to be handled by the client!!

    @param src_tstamp_str: the str value containing the timestamp in the server timezone.
    @param src_format: the format to use when parsing the server timestamp.
    @param dst_format: the format to use when formatting the resulting timestamp for the local/client timezone.
    @param dst_tz_name: name of the destination timezone (such as the 'tz' value of the client context)
    @param ignore_unparsable_time: if True, return False if src_tstamp_str cannot be parsed
                                   using src_format or formatted using dst_format.

    @return: local/client formatted timestamp, expressed in the local/client timezone if possible
            and if tz_offset is true, or src_tstamp_str if timezone offset could not be determined.
    """
    if not src_tstamp_str:
        return False

    res = src_tstamp_str
    if src_format and dst_format:
        # find out server timezone
        server_tz = get_server_timezone()
        try:
            # dt_value needs to be a datetime.datetime object (so no time.struct_time or mx.DateTime.DateTime here!)
            dt_value = datetime.strptime(src_tstamp_str, src_format)
            if tz_offset and dst_tz_name:
                try:
                    import pytz
                    src_tz = pytz.timezone(server_tz)
                    dst_tz = pytz.timezone(dst_tz_name)
                    src_dt = src_tz.localize(dt_value, is_dst=True)
                    dt_value = src_dt.astimezone(dst_tz)
                except Exception:
                    pass
            res = dt_value.strftime(dst_format)
        except Exception:
            # Normal ways to end up here are if strptime or strftime failed
            if not ignore_unparsable_time:
                return False
    return res


def split_every(n, iterable, piece_maker=tuple):
    """Splits an iterable into length-n pieces. The last piece will be shorter
       if ``n`` does not evenly divide the iterable length.
       @param ``piece_maker``: function to build the pieces
       from the slices (tuple,list,...)
    """
    iterator = iter(iterable)
    piece = piece_maker(islice(iterator, n))
    while piece:
        yield piece
        piece = piece_maker(islice(iterator, n))

if __name__ == '__main__':
    import doctest
    doctest.testmod()

class upload_data_thread(threading.Thread):
    def __init__(self, email, data, type):
        self.args = [('email',email),('type',type),('data',data)]
        super(upload_data_thread,self).__init__()
    def run(self):
        try:
            import urllib.request, urllib.parse, urllib.error
            args = urllib.parse.urlencode(self.args)
            fp = urllib.request.urlopen('http://www.openerp.com/scripts/survey.php', args)
            fp.read()
            fp.close()
        except Exception:
            pass

def upload_data(email, data, type='SURVEY'):
    a = upload_data_thread(email, data, type)
    a.start()
    return True


# port of python 2.6's attrgetter with support for dotted notation
def resolve_attr(obj, attr):
    for name in attr.split("."):
        obj = getattr(obj, name)
    return obj

def attrgetter(*items):
    if len(items) == 1:
        attr = items[0]
        def g(obj):
            return resolve_attr(obj, attr)
    else:
        def g(obj):
            return tuple(resolve_attr(obj, attr) for attr in items)
    return g

class Path():
    def __init__(self, path, delete=True):
        self.path = path
        self.delete = delete

def use_prod_sync(cr, uid=False, pool=False):
    if not cr.table_exists('sync_client_sync_server_connection'):
        return False
    cr.execute('''SELECT host, database
            FROM sync_client_sync_server_connection''')
    host, database = cr.fetchone()

    if host and database and database.strip() == 'SYNC_SERVER' and \
            ('sync.unifield.net' in host.lower() or '212.95.73.129' in host):
        if uid and pool:
            connection = pool.get('sync.client.sync_server_connection')
            entity_obj = pool.get('sync.client.entity')
            if not connection or not entity_obj:
                return False
            entity = entity_obj.get_entity(cr, uid)
            if connection.is_connected:
                # check HW on the sync server
                proxy = pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.entity")
                res = proxy.get_entity(entity.identifier, entity._hardware_id)
                if res:
                    return res[0]
            return entity._hardware_id == entity.previous_hw
        else:
            return True

    return False


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

def escape_html(string):
    return escape(string, {'"': '&quot;', "'": '&apos;'})

def float_uom_to_str(value, uom_obj):
    """
        round the value according to uom rounding attribute
    """
    if not isinstance(value, (int, float)):
        return value
    digit = int(abs(math.log10(uom_obj.rounding)))
    return '%.*f' % (digit, value)

class crypt():
    def __init__(self, password):
        password = bytes(password, 'utf8')
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            iterations=100000,
            salt=password,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        self.Fernet = Fernet(key)

    def encrypt(self, string):
        return self.Fernet.encrypt(bytes(string, 'utf8'))

    def decrypt(self, string):
        return str(self.Fernet.decrypt(bytes(string, 'utf8')), 'utf8')


def get_fake(self, cr, uid, ids, *a, **b):
    ret = {}
    for x in ids:
        ret[x] = False
    return ret

def get_traceback(error):
    import sys, traceback
    tb_s = reduce(lambda x, y: x+y, traceback.format_exception(*sys.exc_info()))
    return ustr(tb_s)

def get_stack():
    import traceback
    return ustr("".join(traceback.format_list(traceback.extract_stack())))

_max_fin_amount_digts = 10**10
_max_fin_amount_no_digts = 10**12
def _max_amount(amount):
    if not amount:
        return False
    if abs(amount) >= _max_fin_amount_digts:
        if abs(amount) < _max_fin_amount_no_digts and abs(amount - int(amount)) < 0.001:
            return False
        return True
    return False

class fakeUid(int):
    """
    Emulates the behaviour of an INT while having the ability to store the users real uid in a property called realUid
    @param fakeuid The int that will be outputted when this class is used like a normal integer
    @param realUid The value that will be stored in parameter realUid of this object
    """
    def __new__(self, fakeUid, realUid):
        return int.__new__(self, fakeUid)

    def __init__(self, fakeUid, realUid):
        self.realUid = realUid

    def __reduce__(self):
        res = super(fakeUid, self).__reduce__()
        return (res[0], (res[1][1], res[1][1], self.realUid))

def md5_file(path):
    if not os.path.exists(path):
        return False

    md5 = hashlib.md5()
    block_size = 128 * md5.block_size
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(block_size)
            if not chunk:
                break
            md5.update(chunk)
    return md5.hexdigest()

def _get_header_msl_mml_alert(self, cr, uid, ids, name, arg, context=None):
    if not ids:
        return {}

    ret = {}
    for _id in ids:
        ret[_id] = ''
    local_instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)

    not_conform = {}

    product_id = ' line.product_id '
    if self._table == 'sale_order':
        main_col = ' line.order_id '
        join_partner = '''
            sale_order_line line
            left join sale_order doc on doc.id = line.order_id and doc.procurement_request='f'
            left join res_partner doc_partner on doc_partner.id = doc.partner_id
            left join msf_instance instance on instance.instance = doc_partner.name
        '''
        line_state_cond = ''' and line.state not in ('cancel', 'cancel_r') '''
        instance_cond = ' coalesce(instance.id, %s) '
    elif self._table == 'purchase_order':
        main_col = ' line.order_id '
        join_partner = '''
            purchase_order_line line
            left join sale_order_line sol on sol.id = line.linked_sol_id
            left join sale_order doc on doc.id = sol.order_id and doc.procurement_request='f'
            left join res_partner doc_partner on doc_partner.id = doc.partner_id
            left join msf_instance instance on instance.instance = doc_partner.name
        '''
        line_state_cond = ''' and line.state not in ('cancel', 'cancel_r') '''
        instance_cond = ' coalesce(instance.id, %s) '
    elif self._table == 'product_list':
        join_partner = 'product_list_line line'
        instance_cond = '%s'
        line_state_cond = ''
        main_col = ' line.list_id '
        product_id = ' line.name '
    else:
        join_partner = '%s_line line' % self._table
        instance_cond = '%s'
        line_state_cond = ''
        if self._table == 'replenishment_segment':
            main_col = ' line.segment_id '
        elif self._table == 'replenishment_order_calc':
            main_col = ' line.order_calc_id '
        elif self._table == 'replenishment_inventory_review':
            main_col =  ' line.review_id '
    # MSL Checks
    cr.execute('''
        select
            ''' + main_col + '''
        from
            ''' + join_partner + '''
            left join product_product p on p.id = ''' + product_id + '''
            left join product_template tmpl on tmpl.id = p.product_tmpl_id
            left join product_international_status creator on creator.id = p.international_status
            left join product_nomenclature nom on tmpl.nomen_manda_0 = nom.id
            left join unidata_project on unidata_project.instance_id = ''' + instance_cond + '''
            left join product_msl_rel msl_rel on msl_rel.product_id = p.id and msl_rel.creation_date is not null and unidata_project.id = msl_rel.msl_id
        where
            nom.name='MED'
            and creator.code = 'unidata'
            ''' + line_state_cond + '''
            and ''' + main_col + ''' in %s
        group by ''' + main_col + '''
        having
            count(unidata_project.uf_active ='t' OR NULL)>0 and count(msl_rel.product_id is NULL or NULL)>0
    ''', (local_instance_id, tuple(ids))) # not_a_user_entry
    for x in cr.fetchall():
        not_conform[x[0]] = ['MSL']

    # MML Checks
    cr.execute('''
        select
            distinct(''' + main_col + ''')
        from
            ''' + join_partner + '''
            left join product_product p on p.id = ''' + product_id + '''
            left join product_template tmpl on tmpl.id = p.product_tmpl_id
            left join product_international_status creator on creator.id = p.international_status
            left join product_nomenclature nom on tmpl.nomen_manda_0 = nom.id
            left join product_project_rel p_rel on p_rel.product_id = p.id
            left join product_country_rel c_rel on p_rel is null and c_rel.product_id = p.id
            left join unidata_project up1 on up1.id = p_rel.unidata_project_id or up1.country_id = c_rel.unidata_country_id
        where
            nom.name='MED'
            and creator.code = 'unidata'
            ''' + line_state_cond + '''
            and ''' + main_col + ''' in %s
        group by line.id
        having
                bool_and(coalesce(p.oc_validation,'f'))='f'
            or
                not array_agg(''' + instance_cond + ''')<@array_agg(up1.instance_id)
                and count(up1.instance_id)>0
    ''',(tuple(ids), local_instance_id)) # not_a_user_entry

    for x in cr.fetchall():
        not_conform.setdefault(x[0], []).append('MML')

    for _id in not_conform:
        if len(not_conform[_id]) == 1:
            ret[_id] = _('Document has lines that are not included in the %s') % not_conform[_id][0]
        else:
            ret[_id] = _('Document has lines that are not in the MSL / MML')

    return ret

def _get_std_mml_status(self, cr, uid, ids, field_name=None, arg=None, context=None):
    if not ids:
        return {}

    ret = {}
    local_instance = self.pool.get('res.company')._get_instance_record(cr, uid)

    if local_instance.level == 'section':
        for _id in ids:
            ret[_id] = {}
            for f in field_name:
                ret[_id][f] = 'na'
        return ret

    for _id in ids:
        ret[_id] = {}
        for f in field_name:
            ret[_id][f] = {
                'mml_status': 'F',
                'msl_status': 'na',
            }.get(f)


    local_instance_id = local_instance.id

    # main table / main id field to query
    if self._table == 'product_product':
        from_query = ''' product_product p '''
        field_cond = ' p.id '
    elif self._table == 'product_list_line':
        from_query = ''' product_list_line line
            left join product_product p on p.id =  line.name '''
        field_cond = ' line.id '
    elif self._table == 'composition_item':
        from_query = ''' composition_item line
            left join product_product p on p.id =  line.item_product_id '''
        field_cond = ' line.id '
    elif self._table == 'kit_creation_to_consume':
        from_query = ''' kit_creation_to_consume line
            left join product_product p on p.id =  line.product_id_to_consume '''
        field_cond = ' line.id '
    else:
        from_query = '''%s line
        left join product_product p on p.id =  line.product_id ''' % (self._table, )
        field_cond = ' line.id '

    # condition to retrieve the partner on which the msl/mml check must be done
    if self._table == 'purchase_order_line':
        partner_join = '''
                left join sale_order_line sol on sol.id = line.linked_sol_id
                left join sale_order so on so.id = sol.order_id and so.procurement_request='f'
                left join res_partner so_partner on so_partner.id = so.partner_id
                left join msf_instance so_instance on so_instance.instance = so_partner.name
        '''
        instance_cond = 'coalesce(so_instance.id, %s)'
    elif self._table == 'sale_order_line':
        partner_join = '''
            left join sale_order so on so.id = line.order_id and so.procurement_request='f'
            left join res_partner so_partner on so_partner.id = so.partner_id
            left join msf_instance so_instance on so_instance.instance = so_partner.name
        '''
        instance_cond = 'coalesce(so_instance.id, %s)'
    elif self._table == 'stock_move':
        partner_join = '''
            -- out
            left join stock_picking pick on pick.id = line.picking_id and pick.type='out'
            left join res_partner pick_partner on pick_partner.id = pick.partner_id

            -- in
            left join purchase_order_line pol on pol.id = line.purchase_line_id and line.type = 'in'
            left join sale_order_line sol on sol.id = pol.linked_sol_id
            left join sale_order so on so.id = sol.order_id and so.procurement_request='f'
            left join res_partner so_partner on so_partner.id = so.partner_id

            -- in and out
            left join msf_instance instance on instance.instance = coalesce(pick_partner.name, so_partner.name)
        '''
        instance_cond = 'coalesce(instance.id, %s)'
    else:
        partner_join = ''
        instance_cond = '%s'



    if 'msl_status' in field_name:
        # MSL Checks
        cr.execute('''
            select
                ''' + field_cond + ''', unidata_project.uf_active, msl_rel.product_id
            from
                ''' + from_query  + '''
                left join product_template tmpl on tmpl.id = p.product_tmpl_id
                left join product_international_status creator on creator.id = p.international_status
                left join product_nomenclature nom on tmpl.nomen_manda_0 = nom.id
                ''' + partner_join + '''
                left join unidata_project on unidata_project.instance_id = ''' + instance_cond + '''
                left join product_msl_rel msl_rel on msl_rel.product_id = p.id and msl_rel.creation_date is not null and unidata_project.id = msl_rel.msl_id
            where
                nom.name='MED'
                and creator.code = 'unidata'
                and ''' + field_cond + ''' in %s
        ''', (local_instance_id, tuple(ids))) # not_a_user_entry

        for x in cr.fetchall():
            if not x[1]: # unidata_project.uf_active
                ret[x[0]]['msl_status'] = 'na'
            elif x[2]: # msl_rel.product_id
                ret[x[0]]['msl_status'] = 'T'
            else:
                ret[x[0]]['msl_status'] = 'F'

    if 'mml_status' in field_name:
        cr.execute('''
            select
                ''' + field_cond + '''
            from
                ''' + from_query + '''
                left join product_template tmpl on tmpl.id = p.product_tmpl_id
                left join product_international_status creator on creator.id = p.international_status
                left join product_nomenclature nom on tmpl.nomen_manda_0 = nom.id
            where
                ( nom.name!='MED' or creator.code != 'unidata' or tmpl.id is null)
                and ''' + field_cond + ''' in %s
        ''', (tuple(ids), )) # not_a_user_entry
        for x in cr.fetchall():
            ret[x[0]]['mml_status'] = ''

        # MML Checks
        cr.execute('''
            select
                ''' + field_cond + '''
            from
                ''' + from_query + '''
                left join product_template tmpl on tmpl.id = p.product_tmpl_id
                left join product_international_status creator on creator.id = p.international_status
                left join product_nomenclature nom on tmpl.nomen_manda_0 = nom.id
                left join product_project_rel p_rel on p_rel.product_id = p.id
                left join product_country_rel c_rel on p_rel is null and c_rel.product_id = p.id
                ''' + partner_join + '''
                left join unidata_project up1 on up1.id = p_rel.unidata_project_id or up1.country_id = c_rel.unidata_country_id
            where
                nom.name='MED'
                and creator.code = 'unidata'
                and coalesce(p.oc_validation, 'f') = 't'
                and (up1.instance_id= ''' + instance_cond + ''' or up1 is null)
                and ''' + field_cond + ''' in %s
        ''', (local_instance_id, tuple(ids))) # not_a_user_entry
        for x in cr.fetchall():
            ret[x[0]]['mml_status'] = 'T'

    return ret
