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
import hashlib
import tools
import tempfile
import logging
import traceback
import threading
import pooler

from osv import osv
from osv import fields

from tools.translate import _
from mission_stock.mission_stock import UnicodeWriter

from threading import RLock


class automated_import_job(osv.osv):
    _name = 'automated.import.job'
    _order = 'id desc'

    _processing = {}
    _lock = RLock()
    def _get_name(self, cr, uid, ids, field_name, args, context=None):
        """
        Build the name of the job by using the function_id and the date and time
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this issue
        :param ids: List of ID of automated.import.job to compute name
        :param field_name: The name of the field to compute (here: name)
        :param args: Additional parameters
        :param context: Context of the call
        :return: A dictionnary with automated.import.job ID as key and computed name as value
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for job in self.browse(cr, uid, ids, context=context):
            res[job.id] = '%s - %s' % (job.import_id.function_id.name, job.start_time or _('Not started'))

        return res

    def is_processing_filename(self, filename):
        with self._lock:
            if filename not in self._processing:
                self._processing[filename] = True
                return False
            logging.getLogger('automated.import').info(_('Ignore already processing %s') % filename)
            return True

    def end_processing_filename(self, filename):
        with self._lock:
            try:
                del(self._processing[filename])
            except KeyError:
                pass


    _columns = {
        'name': fields.function(
            _get_name,
            method=True,
            type='char',
            size=128,
            string='Name',
            store=True,
        ),
        'import_id': fields.many2one(
            'automated.import',
            string='Automated import',
            required=True,
            readonly=True,
        ),
        'file_to_import': fields.binary(
            string='File to import',
        ),
        'filename': fields.char(
            size=128,
            string='Name of the file to import',
        ),
        'file_sum': fields.char(
            string='Check sum',
            size=256,
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
    }

    _defaults = {
        'state': lambda *a: 'draft',
        'start_time': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }


    def manual_process_import(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        wiz = self.browse(cr, uid, ids[0], fields_to_fetch=['import_id', 'file_to_import', 'file_sum'], context=context)
        if wiz.file_to_import:
            if wiz.import_id.ftp_source_ok:
                raise osv.except_osv(_('Error'), _('You cannot manually select a file to import if given source path is set on FTP server'))
            md5 = hashlib.md5(wiz.file_to_import).hexdigest()
            if wiz.file_sum != md5:
                if self.search_exists(cr, uid, [('file_sum', '=', md5), ('id', '!=', ids[0])], context=context):
                    self.write(cr, uid, [ids[0]], {'file_sum': md5}, context=context)
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': self._name,
                        'res_id': ids[0],
                        'view_type': 'form',
                        'view_mode': 'form,tree',
                        'target': 'new',
                        'view_id': [self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_tools', 'automated_import_job_file_view')[1]],
                        'context': context,
                    }
        self.write(cr, uid, ids[0], {'state': 'in_progress'}, context=context)
        # Background import
        ctx_import = None
        if wiz.import_id.function_id.method_to_call == 'auto_import_destination':
            ctx_import = {'lang': context.get('lang')}

        thread = threading.Thread(target=self.process_import_bg, args=(cr.dbname, uid, wiz.import_id.id, ids[0], ctx_import))
        thread.start()

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': ids[0],
            'view_type': 'form',
            'view_mode': 'form,tree',
            'target': 'current',
            'context': context,
        }

    def process_import_bg(self, dbname, uid, import_id, started_job_id, context):
        try:
            cr = pooler.get_db(dbname).cursor()
            self.process_import(cr, uid, import_id, started_job_id=started_job_id, context=context)
            cr.commit()
        except Exception, e:
            cr.rollback()
            self.write(cr, uid, [started_job_id], {
                'filename': False,
                'end_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'nb_processed_records': 0,
                'nb_rejected_records': 0,
                'comment': tools.misc.get_traceback(e),
                'state': 'error',
            }, context=context)

        finally:
            cr.commit()
            cr.close(True)

    def process_import(self, cr, uid, import_id, started_job_id=False, context=None):
        """
        First, browse the source path, then select the oldest file and run import on this file.
        After the processing of import, generate a report and move the processed file to the
        processed folder.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of automated.import.job to process
        :param context: Context of the call
        :return: True
        """
        import_obj = self.pool.get('automated.import')

        if context is None:
            context = {}

        if isinstance(import_id, (int, long)):
            import_id = [import_id]
        import_data = import_obj.browse(cr, uid, import_id[0], context=context)
        no_file = False
        already_done = []
        job_id = False
        remote = False
        while not no_file:
            nb_rejected = 0
            nb_processed = 0
            if started_job_id:
                job_id = started_job_id
                prev_job_id = False
            else:
                prev_job_id = job_id
                job_id = self.create(cr, uid, {'import_id': import_data.id, 'state': 'in_progress'}, context=context)
                cr.commit() # keep trace of the job in case of error
            job = self.browse(cr, uid, job_id, context=context)
            started_job_id = False
            md5 = False
            error = None
            non_blocking_error = None
            data64 = None
            filename = False
            oldest_file = False
            context.update({'auto_import_ok': True})
            try:
                remote = self.pool.get('automated.import')._connect(cr, uid, import_data.id, context=context)
            except Exception, e:
                if job.id:
                    if isinstance(e, osv.except_osv):
                        msg = e.value
                    else:
                        msg = e
                    self.write(cr, uid, job_id, {'state': 'error', 'end_time': time.strftime('%Y-%m-%d %H:%M:%S'), 'comment': tools.ustr(msg)}, context=context)
                    cr.commit()
                raise

            try:
                for path in [('src_path', 'r', 'ftp_source_ok'), ('dest_path', 'w', 'ftp_dest_ok'), ('dest_path_failure', 'w', 'ftp_dest_fail_ok'), ('report_path', 'w', 'ftp_report_ok')]:
                    if path[2] and not import_data[path[2]]:
                        import_obj.path_is_accessible(import_data[path[0]], path[1])
            except osv.except_osv as e:
                error = tools.ustr(e)
                # In case of manual processing, raise the error
                if job.file_to_import:
                    raise e

            try:
                oldest_file = False
                orig_file_name = False
                if not job.file_to_import:
                    try:
                        oldest_file = remote.get_oldest_filename(job.import_id.function_id.startswith, already_done, is_processing_filename=self.is_processing_filename)
                        orig_file_name = oldest_file
                        already_done.append(oldest_file)
                        if not oldest_file:
                            raise ValueError()
                        filename = os.path.split(oldest_file)[1]
                        file_content = remote.get_file_content(oldest_file)
                        md5 = hashlib.md5(file_content).hexdigest()
                        data64 = base64.encodestring(file_content)
                    except ValueError:
                        no_file = True
                    except Exception as e:
                        error = tools.ustr(traceback.format_exc())

                    if not error:
                        if no_file:
                            if not prev_job_id:
                                error = _('No file to import in %s !') % import_data.src_path
                            else:
                                # files already processed in previous loop: delete the in_progress job
                                self.unlink(cr, 1, [job_id], context=context)
                                job_id = prev_job_id
                                break

                        elif md5 and self.search_exist(cr, uid, [('import_id', '=', import_data.id), ('file_sum', '=', md5)], context=context):
                            non_blocking_error = _('A file with same checksum has been already imported !')
                            remote.move_to_process_path(filename, success=False)
                            self.infolog(cr, uid, _('%s :: Import file (%s) moved to destination path') % (import_data.name, filename))

                    if error or non_blocking_error:
                        self.infolog(cr, uid, '%s :: %s' % (import_data.name, error or non_blocking_error))
                        self.write(cr, uid, [job.id], {
                            'filename': filename,
                            'file_to_import': data64,
                            'end_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'nb_processed_records': 0,
                            'nb_rejected_records': 0,
                            'comment': error or non_blocking_error,
                            'file_sum': md5,
                            'state': 'done' if no_file else 'error',
                        }, context=context)
                        if error:
                            no_file = True
                        continue
                else: # file to import given
                    no_file = True
                    md5 = hashlib.md5(job.file_to_import).hexdigest()
                    clean_filename = job.filename and job.filename.replace('C:\\fakepath\\', '')
                    oldest_file = os.path.join(job.import_id.src_path, clean_filename)
                    oldest_file_desc = open(oldest_file, 'wb+')
                    oldest_file_desc.write(base64.decodestring(job.file_to_import))
                    oldest_file_desc.close()

                    filename = clean_filename
                    data64 = base64.encodestring(job.file_to_import)

                # Process import
                error_message = []
                state = 'done'
                try:
                    if import_data.ftp_source_ok:
                        tmp_dest_file = os.path.join(tempfile.gettempdir(), remote.connection.remove_special_chars(filename))
                        remote.connection.get(oldest_file, tmp_dest_file)
                        oldest_file = tmp_dest_file

                    processed, rejected, headers = getattr(
                        self.pool.get(import_data.function_id.model_id.model),
                        import_data.function_id.method_to_call
                    )(cr, uid, oldest_file, context=context)
                    if processed:
                        nb_processed += self.generate_file_report(cr, uid, job, processed, headers, remote=remote)

                    if rejected:
                        nb_rejected = nb_processed  # US-7624 If one row is not correct, all processed rows are rejected
                        self.generate_file_report(cr, uid, job, rejected, headers, remote=remote, rejected=True)
                        state = 'error'
                        for resjected_line in rejected:
                            line_message = ''
                            if resjected_line[0]:
                                line_message = _('Line %s: ') % resjected_line[0]
                            line_message += resjected_line[2]
                            error_message.append(line_message)

                        if import_data.function_id.method_to_call == 'auto_import_destination':
                            error_message.append(_("no data will be imported until all the error messages are corrected"))
                            tools.cache.clean_caches_for_db(cr.dbname)
                            tools.read_cache.clean_caches_for_db(cr.dbname)


                    if context.get('rejected_confirmation'):
                        nb_rejected += context.get('rejected_confirmation')
                        state = 'error'

                    self.infolog(cr, uid, _('%s :: Import job done with %s records processed and %s rejected') % (import_data.name, len(processed), nb_rejected))

                    if import_data.function_id.model_id.model == 'purchase.order':
                        po_id = context.get('po_id', False) or self.pool.get('purchase.order').get_po_id_from_file(cr, uid, oldest_file, context=context) or False
                        if po_id and (nb_processed or nb_rejected):
                            po_name = self.pool.get('purchase.order').read(cr, uid, po_id, ['name'], context=context)['name']
                            nb_total_pol = self.pool.get('purchase.order.line').search(cr, uid, [('order_id', '=', po_id)], count=True, context=context)
                            msg = _('%s: ') % po_name
                            if nb_processed:
                                msg += _('%s out of %s lines have been updated') % (nb_processed, nb_total_pol)
                                if nb_rejected:
                                    msg += _(' and ')
                            if nb_rejected:
                                msg += _('%s out of %s lines have been rejected') % (nb_rejected, nb_total_pol)
                            if nb_processed or nb_rejected:
                                self.pool.get('purchase.order').log(cr, uid, po_id, msg)

                    if context.get('job_comment'):
                        for msg_dict in context['job_comment']:
                            self.pool.get(msg_dict['res_model']).log(cr, uid, msg_dict['res_id'], msg_dict['msg'])
                            error_message.append(msg_dict['msg'])

                    self.write(cr, uid, [job.id], {
                        'filename': filename,
                        'end_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'nb_processed_records': nb_processed,
                        'nb_rejected_records': nb_rejected,
                        'comment': '\n'.join(error_message),
                        'file_sum': md5,
                        'file_to_import': data64,
                        'state': state,
                    }, context=context)
                    is_success = True if not rejected else False
                    remote.move_to_process_path(filename, success=is_success)
                    self.infolog(cr, uid, _('%s :: Import file (%s) moved to destination path') % (import_data.name, filename))
                    cr.commit()
                except Exception as e:
                    cr.rollback()
                    if isinstance(e, osv.except_osv):
                        trace_b = e.value
                    else:
                        trace_b = tools.ustr(traceback.format_exc())
                    self.infolog(cr, uid, '%s :: %s' % (import_data.name, trace_b))
                    self.write(cr, uid, [job.id], {
                        'filename': False,
                        'end_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'nb_processed_records': 0,
                        'nb_rejected_records': 0,
                        'comment': trace_b,
                        'file_sum': md5,
                        'file_to_import': data64,
                        'state': 'error',
                    }, context=context)
                    remote.move_to_process_path(filename, success=False)
                    self.infolog(cr, uid, _('%s :: Import file (%s) moved to destination path') % (import_data.name, filename))
            finally:
                if orig_file_name:
                    self.end_processing_filename(orig_file_name)

        if remote:
            remote.disconnect()
        return True

    def generate_file_report(self, cr, uid, job_brw, data_lines, headers, remote, rejected=False):
        """
        Create a csv file that contains the processed lines and put this csv file
        on the report_path directory and attach it to the automated.import.job.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param job_brw: browse_record of the automated.import.job that need a report
        :param data_lines: List of tuple containing the line index and the line data
        :param headers: List of field names in the file
        :param rejected: If true, the data_lines tuple is composed of 3 members, else, composed of 2 members
        :return: # of lines in file
        """
        att_obj = self.pool.get('ir.attachment')

        filename = '%s_%s_%s.csv' % (
            time.strftime('%Y%m%d_%H%M%S'),
            job_brw.import_id.function_id.model_id.model,
            rejected and 'rejected' or 'processed'
        )
        delimiter = ','
        quotechar = '"'

        report_file_name = remote.get_report_file_name(filename)
        self.infolog(cr, uid, _('Writing file report at %s') % report_file_name)
        csvfile = open(report_file_name, 'wb')
        spamwriter = UnicodeWriter(csvfile, delimiter=delimiter, quotechar=quotechar, quoting=csv.QUOTE_MINIMAL)
        headers_row = [_('Line number')] + headers
        if rejected:
            headers_row += [_('Error')]
        spamwriter.writerow(headers_row)
        for pl in data_lines:
            pl_row = [pl[0]] + pl[1]
            if rejected:
                pl_row += [pl[2]]
            spamwriter.writerow(pl_row)
        csvfile.close()

        remote.push_report(report_file_name, filename)

        csvfile = open(report_file_name, 'r')
        att_obj.create(cr, uid, {
            'name': filename,
            'datas_fname': filename,
            'description': '%s Lines' % (rejected and _('Rejected') or _('Processed')),
            'res_model': 'automated.import.job',
            'res_id': job_brw.id,
            'datas': base64.encodestring(csvfile.read())
        })

        return len(data_lines)

    def cancel_file_import(self, cr, uid, ids, context=None):
        """
        Delete the automated.import.job and close the wizard.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of automated.import.job to delete
        :param context: Context of the call
        :return: The action to close the wizard
        """
        self.unlink(cr, uid, ids, context=context)
        return {'type': 'ir.actions.act_window_close'}

automated_import_job()


class automated_import_job_progress(osv.osv_memory):
    _name = 'automated.import.job.progress'

    _columns = {
        'job_id': fields.many2one(
            'automated.import.job',
            string='Import job',
            required=True,
        ),
        'import_id': fields.related(
            'automated.import',
            string='Import',
            write_relate=False,
        ),
    }

automated_import_job_progress()
