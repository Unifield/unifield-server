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
import csv
import time
import base64
import tempfile

from osv import osv
from osv import fields

from tools.translate import _
import logging


class automated_export_job(osv.osv):
    _name = 'automated.export.job'
    logger = logging.getLogger('automated.export.job')
    def _get_name(self, cr, uid, ids, field_name, args, context=None):
        """
        Build the name of the job by using the function_id and the date and time
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this issue
        :param ids: List of ID of automated.export.job to compute name
        :param field_name: The name of the field to compute (here: name)
        :param args: Additional parameters
        :param context: Context of the call
        :return: A dictionnary with automated.export.job ID as key and computed name as value
        """
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        res = {}
        for job in self.browse(cr, uid, ids, context=context):
            res[job.id] = '%s - %s' % (job.export_id.function_id.name, job.start_time or _('Not started'))

        return res

    _columns = {
        'name': fields.function(
            _get_name,
            method=True,
            type='char',
            size=128,
            string='Name',
            store=True,
        ),
        'export_id': fields.many2one(
            'automated.export',
            string='Automated export',
            required=True,
            readonly=True,
        ),
        'start_time': fields.datetime(
            string='Start time',
            readonly=True,
        ),
        'end_time': fields.datetime(
            string='End time',
            readonly=True,
        ),
        'nb_processed_records': fields.integer(
            string='# of processed records',
            readonly=True,
        ),
        'nb_rejected_records': fields.integer(
            string='# of rejected records',
            readonly=True,
        ),
        'comment': fields.text(
            string='Comment',
            readonly=True,
        ),
        'state': fields.selection(
            selection=[
                ('draft', 'Draft'),
                ('in_progress', 'In progress'),
                ('done', 'Done'),
                ('error', 'Exception'),
            ],
            string='State',
            readonly=True,
            required=True,
        ),
        'disable_generation': fields.boolean('Do not generate reports, push only to remote'),
        'filenames': fields.text(string='Files Names', readonly=1),
    }

    _defaults = {
        'state': lambda *a: 'draft',
        'disable_generation': False,
    }

    _order = 'id desc'

    def process_export(self, cr, uid, ids, context=None):
        """
        First, browse the source path, then select the oldest file and run export on this file.
        After the processing of export, generate a report and move the processed file to the
        processed folder.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of automated.export.job to process
        :param context: Context of the call
        :return: True
        """
        if context is None:
            context = []

        if isinstance(ids, int):
            ids = [ids]

        for job in self.browse(cr, uid, ids, context=context):
            nb_rejected = 0
            nb_processed = 0
            start_time = time.strftime('%Y-%m-%d %H:%M:%S')

            ftp_connec = None
            sftp = None
            try:
                context.update({'no_raise_if_ok': True})
                if job.export_id.ftp_ok and job.export_id.ftp_protocol == 'ftp':
                    ftp_connec = self.pool.get('automated.export').ftp_test_connection(cr, uid, job.export_id.id, context=context)
                elif job.export_id.ftp_ok and job.export_id.ftp_protocol == 'sftp':
                    sftp = self.pool.get('automated.export').sftp_test_connection(cr, uid, job.export_id.id, context=context)
                context.pop('no_raise_if_ok')
                # Process export
                error_message, filenames = [], []
                state = 'done'

                if job.export_id.function_id.model_id.model != 'wizard.hq.report.oca':
                    processed, rejected, headers, filenames = getattr(
                        self.pool.get(job.export_id.function_id.model_id.model),
                        job.export_id.function_id.method_to_call
                    )(cr, uid, job.export_id, context=context)

                    if context.get('po_not_found'):
                        error_message.append(_('No PO to export !'))

                    if processed:
                        nb_processed = self.generate_file_report(cr, uid, job, processed, headers, ftp_connec=ftp_connec, sftp=sftp)

                    if rejected:
                        nb_rejected = self.generate_file_report(cr, uid, job, rejected, headers, rejected=True, ftp_connec=ftp_connec, sftp=sftp)
                        state = 'error'
                        for resjected_line in rejected:
                            line_message = _('Line %s: ') % resjected_line[0]
                            line_message += resjected_line[2]
                            error_message.append(line_message)
                else:
                    nb_processed, nb_rejected, error_message = getattr(
                        self.pool.get(job.export_id.function_id.model_id.model),
                        job.export_id.function_id.method_to_call
                    )(cr, uid, job.export_id, remote_con=ftp_connec or sftp, disable_generation=job.disable_generation, context=context)
                    if nb_rejected:
                        state = 'error'

                self.write(cr, uid, [job.id], {
                    'start_time': start_time,
                    'end_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'nb_processed_records': nb_processed,
                    'nb_rejected_records': nb_rejected,
                    'comment': '\n'.join(error_message),
                    'state': state,
                    'filenames': filenames and '; '.join(filenames) or '',
                }, context=context)
            except Exception as e:
                self.logger.error('Unable to process export Job %s (%s)' % (job.id, job.name), exc_info=True)
                self.write(cr, uid, [job.id], {
                    'start_time': start_time,
                    'end_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'nb_processed_records': 0,
                    'nb_rejected_records': 0,
                    'comment': str(e),
                    'state': 'error',
                    'filenames': '',
                }, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': ids[0],
            'view_type': 'form',
            'view_mode': 'form,tree',
            'target': 'current',
            'context': context,
        }


    def generate_file_report(self, cr, uid, job_brw, data_lines, headers, rejected=False, ftp_connec=None, sftp=None):
        """
        Create a csv file that contains the processed lines and put this csv file
        on the report_path directory and attach it to the automated.export.job.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param job_brw: browse_record of the automated.export.job that need a report
        :param data_lines: List of tuple containing the line index and the line data
        :param headers: List of field names in the file
        :param rejected: If true, the data_lines tuple is composed of 3 members, else, composed of 2 members
        :return: # of lines in file
        """
        att_obj = self.pool.get('ir.attachment')

        filename = '%s_%s_%s.csv' % (
            time.strftime('%Y%m%d_%H%M%S'),
            job_brw.export_id.function_id.model_id.model,
            rejected and 'rejected' or 'processed'
        )
        pth_filename = os.path.join(job_brw.export_id.report_path, filename)
        delimiter = ','
        quotechar = '"'
        on_ftp = job_brw.export_id.ftp_report_ok
        assert not on_ftp or (on_ftp and ftp_connec) or (on_ftp and sftp), _('FTP connection issue')

        csvfile = tempfile.NamedTemporaryFile(mode='w', delete=False, newline='') if on_ftp else open(pth_filename, 'w', newline='')
        if on_ftp:
            temp_path = csvfile.name
        spamwriter = csv.writer(csvfile, delimiter=delimiter, quotechar=quotechar, quoting=csv.QUOTE_MINIMAL)
        headers_row = headers
        if rejected:
            headers_row += [_('Error')]
        spamwriter.writerow(headers_row)
        for pl in data_lines:
            pl_row = pl[1]
            if rejected:
                pl_row += [pl[2]]
            spamwriter.writerow(pl_row)
        csvfile.close()

        if on_ftp and job_brw.export_id.ftp_protocol == 'ftp':
            with open(temp_path, 'rb') as temp_file:
                rep = ftp_connec.storbinary('STOR %s' % pth_filename, temp_file)
                if not rep.startswith('2'):
                    raise osv.except_osv(_('Error'), _('Unable to write report on FTP server'))
        elif on_ftp and job_brw.export_id.ftp_protocol == 'sftp':
            try:
                with sftp.cd(job_brw.export_id.report_path):
                    sftp.put(temp_path, filename, preserve_mtime=True)
            except:
                raise osv.except_osv(_('Error'), _('Unable to write report on SFTP server'))

        csvfile = open(on_ftp and temp_path or pth_filename, 'rb')
        att_obj.create(cr, uid, {
            'name': filename,
            'datas_fname': filename,
            'description': '%s Lines' % (rejected and _('Rejected') or _('Processed')),
            'res_model': 'automated.export.job',
            'res_id': job_brw.id,
            'datas': str(base64.b64encode(csvfile.read()), 'utf8')
        })

        return len(data_lines)

    def send_file(self, cr, uid, export_obj, remote_con, filename, destination_path, delete=False, context=None):
        if export_obj.ftp_protocol == 'sftp':
            with remote_con.cd(destination_path):
                remote_con.put(filename)
        else:
            with open(filename, 'rb') as temp_file:
                rep = remote_con.storbinary('STOR %s' % os.path.join(destination_path, os.path.basename(filename)), temp_file)
                if not rep.startswith('2'):
                    raise osv.except_osv(_('Error'), _('Unable to write file on FTP server'))
        if delete:
            os.unlink(filename)
        return True


    def cancel_file_export(self, cr, uid, ids, context=None):
        """
        Delete the automated.export.job and close the wizard.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of automated.export.job to delete
        :param context: Context of the call
        :return: The action to close the wizard
        """
        self.unlink(cr, uid, ids, context=context)
        return {'type': 'ir.actions.act_window_close'}

automated_export_job()


class automated_export_job_progress(osv.osv_memory):
    _name = 'automated.export.job.progress'

    _columns = {
        'job_id': fields.many2one(
            'automated.export.job',
            string='Export job',
            required=True,
        ),
        'export_id': fields.related(
            'automated.export',
            string='Export',
            write_relate=False,
        ),
    }

automated_export_job_progress()
