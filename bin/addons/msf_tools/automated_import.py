# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2016 TeMPO Consulting, MSF
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

import os
import time
import pysftp

from osv import osv
from msf_field_access_rights import osv_override
from osv import fields

from tools.translate import _
from tools import config
from ftplib import FTP

import logging
import shutil
import re
import posixpath
from StringIO import StringIO
import tempfile


class RemoteInterface():
    port = 0
    url = False
    username = False
    password = False

    def __init__(self, **data):
        if data.get('ftp_port'):
            self.port = int(data['ftp_port'])
        self.url = data.get('ftp_url')
        self.username = data.get('ftp_login')
        self.password = data.get('ftp_password')
        self.connection_type = data.get('ftp_ok') and data.get('ftp_protocol')

    def remove_special_chars(self, filename):
        if os.name == 'nt' and filename:
            return re.sub(r'[\\/:*?"<>|]', '_', filename)
        return filename

    def disconnect(self):
        return True

class RemoteSFTP(RemoteInterface):
    sftp = False

    def connect(self):
        try:
            cnopts = pysftp.CnOpts()
            cnopts.hostkeys = None
            self.sftp = pysftp.Connection(self.url, username=self.username, password=self.password, cnopts=cnopts)
            self.sftp._transport.set_keepalive(15)
        except:
            raise Exception(_('No able to connect to SFTP server at location %s') % (self.url, ))

    def list_files(self, path, startswith, already=None):
        if already is None:
            already = []
        res = []
        with self.sftp.cd(path):
            for fileattr in self.sftp.listdir_attr():
                if self.sftp.isfile(fileattr.filename):
                    if startswith and not fileattr.filename.startswith(startswith):
                        continue
                    posix_name = posixpath.join(path, fileattr.filename)
                    if posix_name not in already:
                        res.append((fileattr.st_mtime, posix_name))
        return res

    def get_file_content(self, path):
        tmp_file_path = os.path.join(tempfile.gettempdir(), self.remove_special_chars(os.path.basename(path)))
        self.sftp.get(path, tmp_file_path)
        with open(tmp_file_path, 'r') as fich:
            return fich.read()

    def rename(self, src_file_name, dest_file_name):
        self.sftp.rename(src_file_name, dest_file_name)
        return True

    def push(self, local_name, remote_name):
        self.sftp.put(local_name, remote_name)

    def get(self, remote_name, dest_name, delete=False):
        self.sftp.get(remote_name, dest_name, preserve_mtime=True)
        if delete:
            self.sftp.remove(remote_name)

    def disconnect(self):
        try:
            self.sftp.close()
        except:
            pass

class RemoteFTP(RemoteInterface):
    ftp = False

    def connect(self):
        self.ftp = FTP()
        try:
            self.ftp.connect(host=self.url, port=self.port)
        except:
            raise Exception(_('Not able to connect to FTP server at location %s') % (self.url, ))

        try:
            self.ftp.login(user=self.username, passwd=self.password)
        except:
            raise Exception(_('Unable to connect with given login and password'))

        return True

    def list_files(self, path, startswith, already=None):
        if already is None:
            already = []
        res = []
        files = []
        self.ftp.dir(path, files.append)
        file_names = []
        for file in files:
            if file.startswith('d'): # directory
                continue
            if startswith and not file.split(' ')[-1].startswith(startswith):
                continue
            file_names.append( posixpath.join(path, file.split(' ')[-1]) )
        for file in file_names:
            if file not in already:
                dt = self.ftp.sendcmd('MDTM %s' % file).split(' ')[-1]
                dt = time.strptime(dt, '%Y%m%d%H%M%S') # '20180228170748'
                res.append((dt, file))
        return res


    def get_file_content(self, path):
        def add_line(line):
            ch.write('%s\n' % line)

        ch = StringIO()
        self.ftp.retrlines('RETR %s' % path, add_line)
        return ch.getvalue()

    def rename(self, src_file_name, dest_file_name):
        rep = self.ftp.rename(src_file_name, dest_file_name)
        if not rep.startswith('2'):
            raise osv.except_osv(_('Error'), ('Unable to move file to destination location on FTP server'))
        return True

    def push(self, local_name, remote_name):
        rep = self.ftp.storbinary('STOR %s' % remote_name, open(local_name, 'rb'))
        if not rep.startswith('2'):
            raise osv.except_osv(_('Error'), ('Unable to move local file to destination location on FTP server'))
        return True

    def get(self, remote_name, dest_name, delete=False):
        with open(dest_name, 'wb') as f:
            def write_callback(data):
                f.write(data)
            rep = self.ftp.retrbinary('RETR %s' % remote_name, write_callback)
        if not rep.startswith('2'):
            raise osv.except_osv(_('Error'), ('Unable to move remote file to local destination location on FTP server'))

        if delete:
            rep = self.ftp.delete(remote_name)
            if not rep.startswith('2'):
                raise osv.except_osv(_('Error'), ('Unable to remove remote file on FTP server'))
        return True

    def disconnect(self):
        try:
            self.ftp.quit()
        except:
            pass

class Local(RemoteInterface):

    def list_files(self, path, startswith, already=None):
        """
        Iterates through all files that are under the given path.
        :param path: Path on which we want to iterate
        """
        if already is None:
            already = []

        for cur_path, dirnames, filenames in os.walk(path):
            if startswith:
                filenames = [fn for fn in filenames if fn.startswith(startswith)]
            res = []
            for fn in filenames:
                full_name = os.path.join(cur_path, fn)
                if full_name not in already:
                    res.append((os.stat(full_name).st_ctime, full_name))
            return res
        return []

    def get_file_content(self, path):
        return open(file).read()

class Remote():
    connection_type = False
    connection = False
    local_connection = False
    uid = False
    cr = False
    source = False
    source_is_remote = False
    path_success = False
    path_succes_is_remote = False
    path_failure = False
    path_failure_is_remote = False
    path_report = False
    path_report_is_remote = False

    def __init__(self, cr, uid, **data):
        protocol = data.get('ftp_protocol')
        self.cr = cr
        self.uid = uid
        if data.get('ftp_ok') and protocol == 'ftp':
            self.connection = RemoteFTP(**data)
            self._name = 'FTP Connection'
            self.connection_type = protocol
        elif data.get('ftp_ok') and protocol == 'sftp':
            self.connection = RemoteSFTP(**data)
            self._name = 'SFTP Connection'
            self.connection_type = protocol
        else:
            self.connection = Local(**{})
            self.local_connection = self.connection
            self._name = 'Local Connection'

        self.source = data.get('src_path')
        self.source_is_remote = data.get('ftp_source_ok')
        self.path_success = data.get('dest_path')
        self.path_succes_is_remote = data.get('ftp_dest_ok')
        self.path_failure = data.get('dest_path_failure')
        self.path_failure_is_remote = data.get('ftp_dest_fail_ok')
        self.path_report = data.get('report_path')
        self.path_report_is_remote = data.get('ftp_report_ok')

    def infolog(self, message):
        osv_override.infolog(self, self.cr, self.uid, message)

    def test_connection(self):
        if not self.connection_type:
            return True
        try:
            self.connection.connect()
        except Exception, e:
            self.infolog(e.message)
            raise osv.except_osv(_('Error'), e.message)

        self.infolog(_('FTP connection succeeded'))
        return True

    def get_oldest_filename(self, startwith, already=None, is_processing_filename=False):
        '''
        Get the oldest file in local or on FTP server
        '''
        if already is None:
            already = []
        logging.getLogger('automated.import').info(_('Getting the oldest file at location %s') % self.source)

        if not self.source_is_remote:
            if not self.local_connection:
                self.local_connection = Local(**{})
            res = self.local_connection.list_files(self.source, startwith, already)
        else:
            res = self.connection.list_files(self.source, startwith, already)

        for x in sorted(res, key=lambda x:x[0]):
            if not is_processing_filename or not is_processing_filename(x[1]):
                return x[1]
        return False

    def get_file_content(self, path):
        logging.getLogger('automated.import').info(_('Reading %s content') % file)
        if not self.source_is_remote:
            if not self.local_connection:
                self.local_connection = Local(**{})
            return self.local_connection.get_file_content(path)
        return self.connection.get_file_content(path)

    def move_to_process_path(self, filename, success):
        """
        Move the file `file` from `src_path` to `dest_path`
        :return: return True
        """


        if success:
            dest_path = self.path_success
            dest_is_remote = self.path_succes_is_remote
        else:
            dest_path = self.path_failure
            dest_is_remote = self.path_failure_is_remote

        logging.getLogger('automated.import').info(_('Moving %s to %s') % (filename, dest_path))

        if self.source_is_remote and dest_is_remote:
            # from remote to remote (rename)
            src_file_name = posixpath.join(self.source, filename)
            dest_file_name = posixpath.join(dest_path, '%s_%s' % (time.strftime('%Y%m%d_%H%M%S'), filename))
            self.connection.rename(src_file_name, dest_file_name)
        elif not self.source_is_remote and dest_is_remote:
            # from local to remote
            local_file = os.path.join(self.source, filename)
            remote_file = posixpath.join(dest_path, '%s_%s' % (time.strftime('%Y%m%d_%H%M%S'), filename))
            self.connection.push(local_file, remote_file)
            os.remove(local_file)
        elif self.source_is_remote and not dest_is_remote:
            # from remote to local
            src_file_name = posixpath.join(self.source, filename)
            destfile = os.path.join(dest_path, '%s_%s' % (time.strftime('%Y%m%d_%H%M%S'), self.connection.remove_special_chars(filename)))
            self.connection.get(src_file_name, destfile, delete=True)
        else:
            # from local to local
            src_file_name = os.path.join(self.source, filename)
            destfile = os.path.join(dest_path, '%s_%s' % (time.strftime('%Y%m%d_%H%M%S'), self.connection.remove_special_chars(filename)))
            shutil.move(src_file_name, destfile)

        return True

    def get_report_file_name(self, filename):
        if self.path_report_is_remote:
            tmp = tempfile.NamedTemporaryFile(mode='wb', delete=False)
            tmp.close()
            return tmp.name

        return os.path.join(self.path_report, filename)

    def push_report(self, localname, filename):
        if self.path_report_is_remote:
            self.connection.push(localname, posixpath.join(self.path_report, filename))
        return True

    def disconnect(self):
        self.connection.disconnect()

class automated_import(osv.osv):
    _name = 'automated.import'
    _order = 'name, id'

    def _auto_init(self, cr, context=None):
        res = super(automated_import, self)._auto_init(cr, context)
        # migration delete old constraint
        cr.drop_constraint_if_exists('automated_import', 'automated_import_import_function_id_uniq')
        cr.execute("SELECT indexname FROM pg_indexes WHERE indexname = 'automated_import_function_id_partner_id_uniq'")
        if not cr.fetchone():
            cr.execute("CREATE UNIQUE INDEX automated_import_function_id_partner_id_uniq ON automated_import (function_id, coalesce(partner_id, 0))")
        return res

    def _check_paths(self, cr, uid, ids, context=None):
        """
        Check if given paths are accessible and make checks that src path is not same path as report or dest path.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of automated.import on which checks are made
        :param context: Context of the call
        :return: Return True or raise an error
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for imp_brw in self.browse(cr, uid, ids, context=context):
            for path in [('src_path', 'r', 'ftp_source_ok'), ('dest_path', 'w', 'ftp_dest_ok'), ('dest_path_failure', 'w', 'ftp_dest_fail_ok'), ('report_path', 'w', 'ftp_report_ok')]:
                if imp_brw[path[0]] and path[2] and not imp_brw[path[2]]:
                    self.path_is_accessible(imp_brw[path[0]], path[1])

            if imp_brw.src_path:
                if imp_brw.src_path == imp_brw.dest_path or imp_brw.src_path == imp_brw.dest_path_failure:
                    raise osv.except_osv(
                        _('Error'),
                        _('You cannot have same directory for \'Source Path\' and \'Destination Path\''),
                    )
                if imp_brw.src_path == imp_brw.report_path:
                    raise osv.except_osv(
                        _('Error'),
                        _('You cannot have same directory for \'Source Path\' and \'Report Path\''),
                    )
            if imp_brw.active and not (imp_brw.src_path and imp_brw.dest_path and imp_brw.dest_path_failure and imp_brw.report_path):
                raise osv.except_osv(
                    _('Error'),
                    _('Before activation, the different paths should be set.')
                )

        return True

    def _check_unicity(self, cr, uid, ids, context=None):
        '''
            if the function_id allows multiple then the server / src_path must be unique
            if not multiple: then function_id must be unique
        '''

        error = []
        cr.execute('''
            select function.name
                from automated_import import, automated_import_function function
            where
                function.id = import.function_id and
                coalesce(function.multiple, 'f') = 'f'
            group by function.name
            having(count(*) > 1)
        ''')
        for x in cr.fetchall():
            error.append(_('Another Automated import with same functionality "%s" already exists (maybe inactive). Only one automated import must be created for a '\
                           'same functionality. Please select an other functionality.') % x[0])

        cr.execute('''
            select function.name
                from automated_import import, automated_import_function function
            where
                function.id = import.function_id and
                coalesce(function.multiple, 'f') = 't' and
                coalesce(src_path, '') != ''
            group by function.name, src_path, ftp_url
            having(count(*) > 1)
        ''')
        for x in cr.fetchall():
            error.append(_('Another Automated import with same functionality "%s", same server and same source already exists (maybe inactive).') % x[0])

        if error:
            raise osv.except_osv(_('Warning'), "\n".join(error))

        return True

    def _get_isadmin(self, cr, uid, ids, *a, **b):
        ret = {}
        for _id in ids:
            ret[_id] = uid == 1
        return ret

    _columns = {
        'name': fields.char(
            size=128,
            string='Name',
            required=True,
        ),
        'src_path': fields.char(
            size=512,
            string='Source Path',
        ),
        'dest_path': fields.char(
            size=512,
            string='Destination Path (success)',
        ),
        'dest_path_failure': fields.char(
            size=512,
            string='Destination Path (failure)',
        ),
        'report_path': fields.char(
            size=512,
            string='Report Path',
        ),
        'start_time': fields.datetime(
            string='Date and time of first planned execution',
        ),
        'interval': fields.integer(
            string='Interval number',
        ),
        'interval_unit': fields.selection(
            selection=[
                ('minutes', 'Minutes'),
                ('hours', 'Hours'),
                ('work_days', 'Work Days'),
                ('days', 'Days'),
                ('weeks', 'Weeks'),
                ('months', 'Months'),
            ],
            string='Interval Unit',
        ),
        'function_id': fields.many2one(
            'automated.import.function',
            string='Functionality',
            required=True,
        ),
        'multiple': fields.related('function_id', 'multiple', string='Multiple', type='boolean', write_relate=False),
        'active': fields.boolean(
            string='Active',
            readonly=True,
        ),
        'cron_id': fields.many2one(
            'ir.cron',
            string='Associated cron job',
            readonly=True,
        ),
        'priority': fields.integer(
            string='Priority',
            required=True,
            help="""Defines the priority of the automated import processing because some of them needs other data
to import well some data (e.g: Product Categories needs Product nomenclatures)."""
        ),
        'ftp_ok': fields.boolean(string='Enable remote server', help='Enable remote server if you want to read or write from a remote server'),
        'ftp_protocol': fields.selection([('ftp', 'FTP'), ('sftp','SFTP'), ('onedrive', 'OneDrive')], string='Protocol', required=True),
        'ftp_url': fields.char(string='Remote server address', size=256),
        'ftp_port': fields.char(string='Remote server port', size=56),
        'ftp_login': fields.char(string='Remote login', size=256),
        'ftp_password': fields.char(string='Remote password', size=256),
        'ftp_source_ok': fields.boolean(string='on remote server', help='Is given path is located on remote server ?'),
        'ftp_dest_ok': fields.boolean(string='on remote server', help='Is given path is located on remote server ?'),
        'ftp_dest_fail_ok': fields.boolean(string='on remote server', help='Is given path is located on remote server ?'),
        'ftp_report_ok': fields.boolean(string='on remote server', help='Is given path is located on remote server ?'),
        'is_admin': fields.function(_get_isadmin, method=True, type='boolean', string='Is Admin'),
        'partner_id': fields.many2one('res.partner', 'Partner', domain=[('partner_type', '=', 'esc')]),
    }

    _defaults = {
        'interval': lambda *a: 1,
        'interval_unit': lambda *a: 'hours',
        'active': lambda *a: False,
        'priority': lambda *a: 10,
        'ftp_protocol': lambda *a: 'ftp',
        'is_admin': lambda obj, cr, uid, c: uid == 1,
    }

    _sql_constraints = [
        (
            'import_name_uniq',
            'unique(name)',
            _('Another Automated import with same name already exists (maybe inactive). Automated import name must be unique. Please select an other name.'),
        ),
        (
            'function_id_partner_id_uniq',
            '',
            _('Another Automated import with same function / same partner already exists (maybe inactive).'),
        ),
        (
            'import_positive_interval',
            'CHECK(interval >= 0)',
            _('Interval number cannot be negative !'),
        ),
    ]

    _constraints = [
        (_check_paths, _('There is a problem with paths'), ['active', 'src_path', 'dest_path', 'report_path', 'dest_path_failure']),
        (_check_unicity, _('There is a problem with paths'), []),
    ]

    def change_function_id(self, cr, uid, ids, function_id, context=None):
        multiple = False
        value = {}
        if function_id:
            instance_level = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id'],
                                                               context=context).company_id.instance_id.level
            prod_func_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_tools', 'auto_import_fnct_product')[1]
            if instance_level == 'project' and function_id == prod_func_id:
                return {
                    'value': {'function_id': False},
                    'warning': {'title': _('Error'), 'message': _("You can not select 'Import Products' on a Project instance")}
                }
            fct_data = self.pool.get('automated.import.function').browse(cr, uid, function_id, context=context)
            multiple = fct_data.multiple
            if not multiple:
                value['partner_id'] = False
        value['multiple'] = multiple
        return {'value': value}

    def onchange_ftp_ok(self, cr, uid, ids, ftp_ok, context=None):
        if context is None:
            context = {}
        if ftp_ok == False:
            return {'value': {'ftp_source_ok': False, 'ftp_dest_ok': False, 'ftp_dest_fail_ok': False, 'ftp_report_ok': False}}
        return {}



    def _connect(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        data = self.read(cr, uid, ids[0], context=context)
        remote = Remote(cr, uid, **data)
        remote.test_connection()
        return remote


    def ftp_test_connection(self, cr, uid, ids, context=None):
        self._connect(cr, uid, ids, context=context).disconnect()
        raise osv.except_osv(_('Info'), _('Connection succeeded'))

    def job_in_progress(self, cr, uid, ids, context=None):
        """
        Check if there is job in progress for this automated import.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of automated.import on which the test is made
        :param context: Context of the call
        :return: Return True if there are jobs in progress
        """
        job_progress_obj = self.pool.get('automated.import.job.progress')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Use uid=1 to avoid return of only osv.memory that belongs to the current user
        return job_progress_obj.search(cr, 1, [('import_id', 'in', ids)], limit=1, context=context)

    def path_is_accessible(self, path, mode='r'):
        """
        Returns if the given path is accessible in the given mode
        :param path: Local path to test
        :param mode: Mode to test (can be 'r' for read, 'w' for write)
        :return: True if the path is accessible or the error if not
        """
        msg = None
        if not os.access(path, os.F_OK):
            msg = _('Path \'%s\' doesn\'t exist!') % path
        elif 'r' in mode and not os.access(path, os.R_OK):
            msg =  _('Read is not allowed on \'%s\'!') % path
        elif 'w' in mode and not os.access(path, os.W_OK):
            msg = _('Write is not allowed on \'%s\'!') % path

        if msg:
            raise osv.except_osv(_('Error'), msg)

        return True

    def local_autoconfig(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]

        main_path = os.path.join(config.get('root_path'), 'vi_auto_import')
        write_me = {'ftp_source_ok': False, 'ftp_dest_ok': False, 'ftp_dest_fail_ok': False, 'ftp_report_ok': False, 'ftp_ok': False, 'active': True, 'interval_unit': 'months', 'interval': 12}

        prefix = ''
        for job in self.browse(cr, uid, ids, fields_to_fetch=['name', 'function_id'], context=context):
            if job.function_id.multiple:
                num = self.search(cr, uid, [('function_id', '=', job.function_id.id), ('active', 'in', ['t', 'f'])], count=True, context=context)
                if num > 1:
                    prefix = num
            self.log(cr, uid, job.id, 'Auto configuration done on job %s' % job.name)

        for directory in ['src_path', 'dest_path', 'dest_path_failure', 'report_path']:
            target = os.path.join(main_path, '%s%s' % (directory, prefix))
            write_me[directory] = target
            if not os.path.exists(target):
                os.makedirs(target)
        self.write(cr, uid, ids, write_me, context=context)
        return True


    def run_job_manually(self, cr, uid, ids, context=None, params=None):
        """
        Create a new job with automated import parameters and display a view
        to add a file to import. Then, run it if user clicks on Run or delete
        it if user clicks on Cancel
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of automated.import that must be ran
        :param context: Context of the call
        :param params: Manual parameters in case of manual customized run
        :return: An action to go to the view of automated.import.job to add a file to import
        """
        job_obj = self.pool.get('automated.import.job')
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if params is None:
            params = {}

        for import_brw in self.browse(cr, uid, ids, context=context):
            if not import_brw.src_path or not import_brw.dest_path or not import_brw.report_path or not import_brw.dest_path_failure:
                raise osv.except_osv(
                    _('Error'),
                    _('You should define all paths before run manually this job !'),
                )
            params = {
                'import_id': import_brw.id,
                'state': 'draft',
            }
            job_id = job_obj.create(cr, uid, params, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': job_obj._name,
            'res_id': job_id,
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [data_obj.get_object_reference(cr, uid, 'msf_tools', 'automated_import_job_file_view')[1]],
            'target': 'new',
            'context': context,
        }


    def run_job(self, cr, uid, ids, context=None, params=None):
        """
        Create a new job with automated import parameters and run it
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of automated.import that must be ran
        :param context: Context of the call
        :param params: Manual parameters in case of manual customized run
        :return: An action to go to the view of automated.import.job
        """
        job_obj = self.pool.get('automated.import.job')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if params is None:
            params = {}

        for import_id in ids:
            params = {
                'import_id': import_id,
                'state': 'in_progress',
            }
            job_id = job_obj.create(cr, uid, params, context=context)
            self.infolog(cr, uid, _('%s :: New import job created') % self.read(cr, uid, import_id, ['name'])['name'])
            cr.commit()
            res = job_obj.process_import(cr, uid, import_id, job_id, context=context)
            cr.commit()

        return res


    def _generate_ir_cron(self, import_brw):
        """
        Returns the values for the ir.cron to create according to automated.import values
        :param import_brw: automated.import browse_record
        :return: A dictionary with values for ir.cron
        """
        # If no interval defined, stop the scheduled action
        numbercall = -1
        if not import_brw.interval:
            numbercall = 0

        return {
            'name': _('[Automated import] %s') % import_brw.name,
            'user_id': 1,
            'active': import_brw.active,
            'interval_number': import_brw.interval,
            'interval_type': import_brw.interval_unit,
            'numbercall': numbercall,
            'nextcall': import_brw.start_time or time.strftime('%Y-%m-%d %H:%M:%S'),
            'model': self._name,
            'function': 'run_job',
            'args': '(%s,)' % import_brw.id,
            'priority': import_brw.priority,
        }

    def create(self, cr, uid, vals, context=None):
        """
        Create the automated.import record.
        Make some checks (uniqueness of name, uniqueness of functionality...)
        Create an ir_cron record and linked it to the new automated.import
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param vals: Values for the new automated.import record
        :param context: Context of the call
        :return: The ID of the new automated.import created record
        """
        cron_obj = self.pool.get('ir.cron')

        if context is None:
            context = {}

        # Call the super create
        new_id = super(automated_import, self).create(cr, uid, vals, context=context)

        # Generate new ir.cron
        import_brw = self.browse(cr, uid, new_id, context=context)
        cron_id = cron_obj.create(cr, uid, self._generate_ir_cron(import_brw), context=context)
        to_write = {'cron_id': cron_id}
        if import_brw.active:
            to_write['start_time'] = False
        self.write(cr, uid, [new_id], to_write, context=context)

        return new_id

    def write(self, cr, uid, ids, vals, context=None):
        """
        Make some checks on new values (uniqueness of name, uniqueness of functionality...)
        Update the ir_cron
        Write new values on existing automated.import records
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of automated.import records to write
        :param vals: Values for the new automated.import record
        :param context: Context of the call
        :return: True
        """
        if not ids:
            return True
        cron_obj = self.pool.get('ir.cron')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if 'ftp_ok' in vals:
            if vals['ftp_ok'] == False:
                vals.update({
                    'ftp_source_ok': False,
                    'ftp_dest_ok': False,
                    'ftp_dest_fail_ok': False,
                    'ftp_report_ok': False,
                })

        res = super(automated_import, self).write(cr, uid, ids, vals, context=context)

        for import_brw in self.browse(cr, uid, ids, context=context):
            cron_vals = self._generate_ir_cron(import_brw)
            if import_brw.cron_id:
                if not import_brw.start_time and 'nextcall' in cron_vals:
                    del(cron_vals['nextcall'])
                cron_obj.write(cr, uid, [import_brw.cron_id.id], cron_vals, context=context)
            elif not vals.get('cron_id', False):
                cron_id = cron_obj.create(cr, uid, cron_vals, context=context)
                self.write(cr, uid, [import_brw.id], {'cron_id': cron_id}, context=context)

        if import_brw.active and import_brw.start_time:
            super(automated_import, self).write(cr, uid, ids, {'start_time': False}, context=context)

        return res

    def unlink(self, cr, uid, ids, context=None):
        """
        Delete the associated ir_cron
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of automated.import ID to remove
        :param context: Context of the call
        :return: True
        """
        cron_obj = self.pool.get('ir.cron')
        job_obj = self.pool.get('automated.import.job')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if job_obj.search(cr, uid, [('import_id', 'in', ids)], limit=1, order='NO_ORDER', context=context):
            raise osv.except_osv(
                _('Error'),
                _('Please delete the automated import jobs that are linked to the Automatic import you try to delete!'),
            )

        for import_brw in self.browse(cr, uid, ids, context=context):
            if import_brw.cron_id:
                cron_obj.unlink(cr, uid, [import_brw.cron_id.id], context=context)

        return super(automated_import, self).unlink(cr, uid, ids, context=context)

    def copy(self, cr, uid, import_id, new_vals=None, context=None):
        """
        Display an error on copy as copy is not allowed on automated.import
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param import_id: ID of the automated.import to copy
        :param new_vals: Default values for the new automated.import record
        :param context: Context of the call
        :return: The ID of the new automated.import record
        """
        raise osv.except_osv(
            _('Error'),
            _('Copy is not allowed for Automated imports!'),
        )

    def active_import(self, cr, uid, ids, context=None):
        """
        Make the automated.import as active
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of automated.import to activate
        :param context: Context of the call
        :return: True
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        return self.write(cr, uid, ids, {'active': True}, context=context)

    def deactive_import(self, cr, uid, ids, context=None):
        """
        Make the automated.import as inactive
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of automated.import to activate
        :param context: Context of the call
        :return: True
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        return self.write(cr, uid, ids, {'active': False}, context=context)

automated_import()
