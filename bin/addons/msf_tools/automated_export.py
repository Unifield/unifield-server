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

from osv import osv
from osv import fields

from tools.translate import _
from ftplib import FTP


class automated_export(osv.osv):
    _name = 'automated.export'

    def _check_paths(self, cr, uid, ids, context=None):
        """
        Check if given paths are accessible and make checks that src path is not same path as report or dest path.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of automated.export on which checks are made
        :param context: Context of the call
        :return: Return True or raise an error
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for imp_brw in self.browse(cr, uid, ids, context=context):
            for path in [('dest_path', 'w', 'ftp_dest_ok'), ('dest_path_failure', 'w', 'ftp_dest_fail_ok'), ('report_path', 'w', 'ftp_report_ok')]:
                if imp_brw[path[0]] and path[2] and not imp_brw[path[2]]:
                    self.path_is_accessible(imp_brw[path[0]], path[1])

            if imp_brw.active and not (imp_brw.dest_path and imp_brw.dest_path_failure and imp_brw.report_path):
                raise osv.except_osv(
                    _('Error'),
                    _('Before activation, the different paths should be set.')
                )

        return True

    _columns = {
        'name': fields.char(
            size=128,
            string='Name',
            required=True,
        ),
        'dest_path': fields.char(
            size=512,
            string='Destination Path',
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
            'automated.export.function',
            string='Functionality',
            required=True,
        ),
        'export_format': fields.selection(
            selection=[
                ('excel', 'Excel'),
                ('xml', 'XML'),
            ],
            string='Export format',
            required=True,
        ),
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
            help="""Defines the priority of the automated export processing because some of them needs other data
to export well some data (e.g: Product Categories needs Product nomenclatures)."""
        ),
        'ftp_ok': fields.boolean(string='Enable FTP server', help='Enable FTP server if you want to read or write from a remote FTP server'),
        'ftp_url': fields.char(string='FTP server address', size=256),
        'ftp_port': fields.char(string='FTP server port', size=56),
        'ftp_login': fields.char(string='FTP login', size=256),
        'ftp_password': fields.char(string='FTP password', size=256),
        'ftp_dest_ok': fields.boolean(string='on FTP server', help='Is given path is located on FTP server ?'),
        'ftp_dest_fail_ok': fields.boolean(string='on FTP server', help='Is given path is located on FTP server ?'),
        'ftp_report_ok': fields.boolean(string='on FTP server', help='Is given path is located on FTP server ?'),
    }

    _defaults = {
        'interval': lambda *a: 1,
        'interval_unit': lambda *a: 'hours',
        'active': lambda *a: False,
        'priority': lambda *a: 10,
    }

    _sql_constraints = [
        (
            'export_name_uniq',
            'unique(name)',
            _('Another Automated export with same name already exists (maybe inactive). Automated export name must be unique. Please select an other name.'),
        ),
        (
            'export_function_id_uniq',
            'unique(function_id)',
            _('Another Automated export with same functionality already exists (maybe inactive). Only one automated export must be created for a '\
              'same functionality. Please select an other functionality.'),
        ),
        (
            'export_positive_interval',
            'CHECK(interval >= 0)',
            _('Interval number cannot be negative !'),
        ),
    ]

    _constraints = [
        (_check_paths, _('There is a problem with paths'), ['active', 'dest_path', 'report_path', 'dest_path_failure']),
    ]

    def onchange_ftp_ok(self, cr, uid, ids, ftp_ok, context=None):
        if context is None:
            context = {}
        if ftp_ok == False:
            return {'value': {'ftp_dest_ok': False, 'ftp_dest_fail_ok': False, 'ftp_report_ok': False}}
        return {}

    def ftp_test_connection(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        for obj in self.browse(cr, uid, ids, context=context):
            ftp = FTP()
            try:
                ftp.connect(host=obj.ftp_url, port=obj.ftp_port or 0) # '220 (vsFTPd 3.0.2)'
            except:
                raise osv.except_osv(_('Error'), _('Not able to connect to FTP server at location %s') % obj.ftp_url)
            try:
                ftp.login(user=obj.ftp_login, passwd=obj.ftp_password) # '230 Login successful.'
            except:
                raise osv.except_osv(_('Error'), _('Unable to connect with given login and password'))

        if not context.get('no_raise_if_ok'):
            raise osv.except_osv(_('Info'), _('Connection succeeded'))

        return ftp

    def job_in_progress(self, cr, uid, ids, context=None):
        """
        Check if there is job in progress for this automated export.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of automated.export on which the test is made
        :param context: Context of the call
        :return: Return True if there are jobs in progress
        """
        job_progress_obj = self.pool.get('automated.export.job.progress')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Use uid=1 to avoid return of only osv.memory that belongs to the current user
        return job_progress_obj.search(cr, 1, [('export_id', 'in', ids)], limit=1, context=context)

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

    def run_job_manually(self, cr, uid, ids, context=None, params=None):
        """
        Create a new job with automated export parameters and display a view
        to add a file to export. Then, run it if user clicks on Run or delete
        it if user clicks on Cancel
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of automated.export that must be ran
        :param context: Context of the call
        :param params: Manual parameters in case of manual customized run
        :return: An action to go to the view of automated.export.job to add a file to export
        """
        job_obj = self.pool.get('automated.export.job')
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if params is None:
            params = {}

        for export_brw in self.browse(cr, uid, ids, context=context):
            if not export_brw.dest_path or not export_brw.report_path or not export_brw.dest_path_failure:
                raise osv.except_osv(
                    _('Error'),
                    _('You should define all paths before run manually this job !'),
                )
            params = {
                'export_id': export_brw.id,
                'state': 'draft',
            }
            job_id = job_obj.create(cr, uid, params, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': job_obj._name,
            'res_id': job_id,
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [data_obj.get_object_reference(cr, uid, 'msf_tools', 'automated_export_job_file_view')[1]],
            'target': 'new',
            'context': context,
        }


    def run_job(self, cr, uid, ids, context=None, params=None):
        """
        Create a new job with automated export parameters and run it
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of automated.export that must be ran
        :param context: Context of the call
        :param params: Manual parameters in case of manual customized run
        :return: An action to go to the view of automated.export.job
        """
        job_obj = self.pool.get('automated.export.job')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if params is None:
            params = {}

        for export_id in ids:
            dest_path = self.read(cr, uid, export_id, ['dest_path'])['dest_path']
            params = {
                'export_id': export_id,
                'state': 'in_progress',
            }
            job_id = job_obj.create(cr, uid, params, context=context)
            cr.commit()
            res = job_obj.process_export(cr, uid, [job_id], context=context)
            cr.commit()

        return res

    def _generate_ir_cron(self, export_brw):
        """
        Returns the values for the ir.cron to create according to automated.export values
        :param export_brw: automated.export browse_record
        :return: A dictionary with values for ir.cron
        """
        # If no interval defined, stop the scheduled action
        numbercall = -1
        if not export_brw.interval:
            numbercall = 0

        return {
            'name': _('[Automated export] %s') % export_brw.name,
            'user_id': 1,
            'active': export_brw.active,
            'interval_number': export_brw.interval,
            'interval_type': export_brw.interval_unit,
            'numbercall': numbercall,
            'nextcall': export_brw.start_time or time.strftime('%Y-%m-%d %H:%M:%S'),
            'model': self._name,
            'function': 'run_job',
            'args': '(%s,)' % export_brw.id,
            'priority': export_brw.priority,
        }

    def create(self, cr, uid, vals, context=None):
        """
        Create the automated.export record.
        Make some checks (uniqueness of name, uniqueness of functionality...)
        Create an ir_cron record and linked it to the new automated.export
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param vals: Values for the new automated.export record
        :param context: Context of the call
        :return: The ID of the new automated.export created record
        """
        cron_obj = self.pool.get('ir.cron')

        if context is None:
            context = {}

        # Call the super create
        new_id = super(automated_export, self).create(cr, uid, vals, context=context)

        # Generate new ir.cron
        export_brw = self.browse(cr, uid, new_id, context=context)
        cron_id = cron_obj.create(cr, uid, self._generate_ir_cron(export_brw), context=context)
        self.write(cr, uid, [new_id], {'cron_id': cron_id}, context=context)

        return new_id

    def write(self, cr, uid, ids, vals, context=None):
        """
        Make some checks on new values (uniqueness of name, uniqueness of functionality...)
        Update the ir_cron
        Write new values on existing automated.export records
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of automated.export records to write
        :param vals: Values for the new automated.export record
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
                    'ftp_dest_ok': False,
                    'ftp_dest_fail_ok': False,
                    'ftp_report_ok': False,
                })

        res = super(automated_export, self).write(cr, uid, ids, vals, context=context)

        for export_brw in self.browse(cr, uid, ids, context=context):
            cron_vals = self._generate_ir_cron(export_brw)
            if export_brw.cron_id:
                cron_obj.write(cr, uid, [export_brw.cron_id.id], cron_vals, context=context)
            elif not vals.get('cron_id', False):
                cron_id = cron_obj.create(cr, uid, cron_vals, context=context)
                self.write(cr, uid, [export_brw.id], {'cron_id': cron_id}, context=context)

        return res

    def unlink(self, cr, uid, ids, context=None):
        """
        Delete the associated ir_cron
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of automated.export ID to remove
        :param context: Context of the call
        :return: True
        """
        cron_obj = self.pool.get('ir.cron')
        job_obj = self.pool.get('automated.export.job')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if job_obj.search(cr, uid, [('export_id', 'in', ids)], limit=1, order='NO_ORDER', context=context):
            raise osv.except_osv(
                _('Error'),
                _('Please delete the automated export jobs that are linked to the Automatic export you try to delete!'),
            )

        for export_brw in self.browse(cr, uid, ids, context=context):
            if export_brw.cron_id:
                cron_obj.unlink(cr, uid, [export_brw.cron_id.id], context=context)

        return super(automated_export, self).unlink(cr, uid, ids, context=context)


    def copy(self, cr, uid, ids, new_vals=None, context=None):
        raise osv.except_osv(
            _('Error'),
            _('Copy is not allowed for Automated exports!'),
        )

    def active_export(self, cr, uid, ids, context=None):
        """
        Make the automated.export as active
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of automated.export to activate
        :param context: Context of the call
        :return: True
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        return self.write(cr, uid, ids, {'active': True}, context=context)

    def deactive_export(self, cr, uid, ids, context=None):
        """
        Make the automated.export as inactive
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of automated.export to activate
        :param context: Context of the call
        :return: True
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        return self.write(cr, uid, ids, {'active': False}, context=context)

automated_export()
