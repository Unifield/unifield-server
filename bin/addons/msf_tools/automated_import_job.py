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
import shutil
import base64
import hashlib
import tools
import tempfile

from osv import osv
from osv import fields

from tools.translate import _
from StringIO import StringIO


def all_files_under(path, startswith=False):
    """
    Iterates through all files that are under the given path.
    :param path: Path on which we want to iterate
    """
    res = []
    for cur_path, dirnames, filenames in os.walk(path):
        if startswith:
            filenames = [fn for fn in filenames if fn.startswith(startswith)]
        res.extend([os.path.join(cur_path, fn) for fn in filenames])
        break # don't parse children
    return res

def get_oldest_filename(job, ftp_connec=None):
    '''
    Get the oldest file in local or on FTP server
    '''
    if not job.import_id.ftp_source_ok:
        return min(all_files_under(job.import_id.src_path, job.import_id.function_id.startswith), key=os.path.getmtime)
    else:
        files = []
        ftp_connec.dir(job.import_id.src_path, files.append)
        file_names = []
        for file in files:
            if file.startswith('d'): # directory
                continue
            if job.import_id.function_id.startswith and not file.split(' ')[-1].startswith(job.import_id.function_id.startswith):
                continue
            file_names.append( os.path.join(job.import_id.src_path, file.split(' ')[-1]) )
        res = []
        for file in file_names:
            dt = ftp_connec.sendcmd('MDTM %s' % file).split(' ')[-1]
            dt = time.strptime(dt, '%Y%m%d%H%M%S') # '20180228170748'
            res.append((dt, file))
        return min(res, key=lambda x:x[1])[1] if res else False


def get_file_content(file, from_ftp=False, ftp_connec=None):
    '''
    get file content from local of FTP
    If ftp_connec is given then we try to retrieve line from FTP server
    '''
    def add_line(line):
        ch.write('%s\n' % line)
    if not from_ftp:
        return open(file).read()
    else:
        ch = StringIO()
        ftp_connec.retrlines('RETR %s' % file, add_line)
        return ch.getvalue()


def move_to_process_path(import_brw, ftp_connec, file, success):
    """
    Move the file `file` from `src_path` to `dest_path`
    :return: return True
    """
    srcname = os.path.join(import_brw.src_path, file)
    destname = os.path.join(import_brw.dest_path if success else import_brw.dest_path_failure, '%s_%s' % (time.strftime('%Y%m%d_%H%M%S'), file))

    dest_on_ftp = import_brw.ftp_dest_ok if success else import_brw.ftp_dest_fail_ok

    if import_brw.ftp_source_ok and dest_on_ftp:
        # from FTP to FTP
        rep = ftp_connec.rename(srcname, destname)
        if not rep.startswith('2'):
            raise osv.except_osv(_('Error'), ('Unable to move file to destination location on FTP server'))
    elif not import_brw.ftp_source_ok and dest_on_ftp:
        # from local to FTP
        rep = ftp_connec.storbinary('STOR %s' % destname, open(srcname, 'rb'))
        if not rep.startswith('2'):
            raise osv.except_osv(_('Error'), ('Unable to move local file to destination location on FTP server'))
        else:
            os.remove(srcname)
    elif import_brw.ftp_source_ok and not dest_on_ftp:
        # from FTP to local
        rep = ''
        with open(destname, 'wb') as f:
            def write_callback(data):
                f.write(data)
            rep = ftp_connec.retrbinary('RETR %s' % srcname, write_callback)
        if not rep.startswith('2'):
            raise osv.except_osv(_('Error'), ('Unable to move remote file to local destination location on FTP server'))
        else:
            rep2 = ftp_connec.delete(srcname)
            if not rep2.startswith('2'):
                raise osv.except_osv(_('Error'), ('Unable to remove remote file on FTP server'))
    else:
        # from local to local
        shutil.move(srcname, destname)

    return True


class automated_import_job(osv.osv):
    _name = 'automated.import.job'

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
    }

    _order = 'id desc'

    def process_import(self, cr, uid, ids, context=None):
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
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = []

        if isinstance(ids, (int, long)):
            ids = [ids]

        for job in self.browse(cr, uid, ids, context=context):
            nb_rejected = 0
            nb_processed = 0
            start_time = time.strftime('%Y-%m-%d %H:%M:%S')
            no_file = False
            md5 = False
            error = None
            data64 = None
            filename = False

            ftp_connec = None
            if job.import_id.ftp_ok:
                context.update({'no_raise_if_ok': True})
                ftp_connec = self.pool.get('automated.import').ftp_test_connection(cr, uid, job.import_id.id, context=context)

            try:
                for path in [('src_path', 'r', 'ftp_source_ok'), ('dest_path', 'w', 'ftp_dest_ok'), ('dest_path_failure', 'w', 'ftp_dest_fail_ok'), ('report_path', 'w', 'ftp_report_ok')]:
                    if path[2] and not job.import_id[path[2]]:
                        import_obj.path_is_accessible(job.import_id[path[0]], path[1])
            except osv.except_osv as e:
                error = tools.ustr(e)
                # In case of manual processing, raise the error
                if job.file_to_import:
                    raise e

            if not job.file_to_import:
                try:
                    oldest_file = get_oldest_filename(job, ftp_connec)
                    if not oldest_file:
                        raise ValueError()
                    filename = os.path.split(oldest_file)[1]
                    md5 = hashlib.md5(get_file_content(oldest_file, job.import_id.ftp_source_ok, ftp_connec)).hexdigest()
                    data64 = base64.encodestring(get_file_content(oldest_file, job.import_id.ftp_source_ok, ftp_connec))
                except ValueError:
                    no_file = True

                if not error:
                    if no_file:
                        error = _('No file to import in %s !') % job.import_id.src_path
                    elif md5 and self.search_exist(cr, uid, [('import_id', '=', job.import_id.id), ('file_sum', '=', md5)], context=context):
                        error = _('A file with same checksum has been already imported !')
                        move_to_process_path(job.import_id, ftp_connec, filename, success=False)
                        self.infolog(cr, uid, _('%s :: Import file moved to destination path') % job.import_id.name)

                if error:
                    self.infolog(cr, uid, '%s :: %s' % (job.import_id.name , error))
                    self.write(cr, uid, [job.id], {
                        'filename': filename,
                        'file_to_import': data64,
                        'start_time': start_time,
                        'end_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'nb_processed_records': 0,
                        'nb_rejected_records': 0,
                        'comment': error,
                        'file_sum': md5,
                        'state': 'error',
                    }, context=context)
                    continue
            else: # file to import given
                if job.import_id.ftp_source_ok:
                    raise osv.except_osv(_('Error'), _('You cannot manually select a file to import if given source path is set on FTP server'))
                oldest_file = open(os.path.join(job.import_id.src_path, job.filename), 'wb+')
                oldest_file.write(base64.decodestring(job.file_to_import))
                oldest_file.close()
                md5 = hashlib.md5(job.file_to_import).hexdigest()

                if job.file_sum != md5:
                    if self.search_exist(cr, uid, [('file_sum', '=', md5), ('id', '!=', job.id)], context=context):
                        self.write(cr, uid, [job.id], {'file_sum': md5}, context=context)
                        return {
                            'type': 'ir.actions.act_window',
                            'res_model': self._name,
                            'res_id': ids[0],
                            'view_type': 'form',
                            'view_mode': 'form,tree',
                            'target': 'new',
                            'view_id': [data_obj.get_object_reference(cr, uid, 'msf_tools', 'automated_import_job_file_view')[1]],
                            'context': context,
                        }

                oldest_file = os.path.join(job.import_id.src_path, job.filename)
                filename = job.filename
                data64 = base64.encodestring(job.file_to_import)

            # Process import
            error_message = []
            state = 'done'
            try:
                if job.import_id.ftp_source_ok:
                    prefix = '%s_' % filename.split('.')[0]
                    suffix = '.xls' if self.pool.get('stock.picking').get_import_filetype(cr, uid, filename) == 'excel' else '.xml' 
                    temp_file = tempfile.NamedTemporaryFile(delete=False, prefix=prefix, suffix=suffix)
                    ftp_connec.retrbinary('RETR %s' % oldest_file, temp_file.write)
                    temp_file.close()
                    oldest_file = temp_file.name
                processed, rejected, headers = getattr(
                    self.pool.get(job.import_id.function_id.model_id.model),
                    job.import_id.function_id.method_to_call
                )(cr, uid, oldest_file)
                if processed:
                    nb_processed = self.generate_file_report(cr, uid, job, processed, headers, ftp_connec=ftp_connec)

                if rejected:
                    nb_rejected = self.generate_file_report(cr, uid, job, rejected, headers, rejected=True, ftp_connec=ftp_connec)
                    state = 'error'
                    for resjected_line in rejected:
                        line_message = _('Line %s: ' % resjected_line[0])
                        line_message += resjected_line[2]
                        error_message.append(line_message)
                self.infolog(cr, uid, _('%s :: Import job done with %s processed and %s rejected') % (job.import_id.name, len(processed), len(rejected)))

                self.write(cr, uid, [job.id], {
                    'filename': filename,
                    'start_time': start_time,
                    'end_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'nb_processed_records': nb_processed,
                    'nb_rejected_records': nb_rejected,
                    'comment': '\n'.join(error_message),
                    'file_sum': md5,
                    'file_to_import': data64,
                    'state': state,
                }, context=context)
                is_success = True if not rejected else False
                move_to_process_path(job.import_id, ftp_connec, filename, success=is_success)
                self.infolog(cr, uid, _('%s :: Import file moved to destination path') % job.import_id.name)
            except Exception as e:
                self.infolog(cr, uid, '%s :: %s' % (job.import_id.name, str(e)))
                self.write(cr, uid, [job.id], {
                    'filename': False,
                    'start_time': start_time,
                    'end_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'nb_processed_records': 0,
                    'nb_rejected_records': 0,
                    'comment': str(e),
                    'file_sum': md5,
                    'file_to_import': data64,
                    'state': 'error',
                }, context=context)
                move_to_process_path(job.import_id, ftp_connec, filename, success=False)
                self.infolog(cr, uid, _('%s :: Import file moved to destination path') % job.import_id.name)

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': ids[0],
            'view_type': 'form',
            'view_mode': 'form,tree',
            'target': 'current',
            'context': context,
        }


    def generate_file_report(self, cr, uid, job_brw, data_lines, headers, rejected=False, ftp_connec=None):
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
        pth_filename = os.path.join(job_brw.import_id.report_path, filename)
        delimiter = ','
        quotechar = '"'
        on_ftp = job_brw.import_id.ftp_report_ok
        assert not on_ftp or (on_ftp and ftp_connec), _('FTP connection issue')

        csvfile = tempfile.NamedTemporaryFile(mode='wb', delete=False) if on_ftp else open(pth_filename, 'wb')
        if on_ftp:
            temp_path = csvfile.name
        spamwriter = csv.writer(csvfile, delimiter=delimiter, quotechar=quotechar, quoting=csv.QUOTE_MINIMAL)
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

        if on_ftp:
            with open(temp_path, 'rb') as temp_file:
                rep = ftp_connec.storbinary('STOR %s' % pth_filename, temp_file)
                if not rep.startswith('2'):
                    raise osv.except_osv(_('Error'), ('Unable to move local file to destination location on FTP server'))

        csvfile = open(on_ftp and temp_path or pth_filename, 'r')
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
        ),
    }

automated_import_job_progress()
