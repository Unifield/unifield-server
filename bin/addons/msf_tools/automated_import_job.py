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
import logging
import posixpath
import traceback
import threading
import pooler

from osv import osv
from osv import fields

from tools.translate import _
from io import StringIO

from threading import RLock
import re

def all_files_under(path, startswith=False, already=None):
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



def get_file_content(file, from_ftp=False, ftp_connec=None, sftp=None):
    '''
    get file content from local of FTP
    If ftp_connec is given then we try to retrieve line from FTP server
    '''
    def add_line(line):
        ch.write('%s\n' % line)
    logging.getLogger('automated.import').info(_('Reading %s content') % file)
    if not from_ftp:
        return open(file).read()
    elif ftp_connec:
        ch = StringIO()
        ftp_connec.retrlines('RETR %s' % file, add_line)
        return ch.getvalue()
    elif sftp:
        tmp_file_path = os.path.join(tempfile.gettempdir(), remove_special_chars(os.path.basename(file)))
        sftp.get(file, tmp_file_path)
        with open(tmp_file_path, 'r') as fich:
            return fich.read()
    return False

def remove_special_chars(filename):
    if os.name == 'nt' and filename:
        return re.sub(r'[\\/:*?"<>|]', '_', filename)

    return filename

def move_to_process_path(import_brw, ftp_connec, sftp, file, success):
    """
    Move the file `file` from `src_path` to `dest_path`
    :return: return True
    """
    if not import_brw.ftp_source_ok:
        srcname = os.path.join(import_brw.src_path, file)
    else:
        srcname = posixpath.join(import_brw.src_path, file)

    dest_on_ftp = import_brw.ftp_dest_ok if success else import_brw.ftp_dest_fail_ok
    if dest_on_ftp:
        destname = posixpath.join(import_brw.dest_path if success else import_brw.dest_path_failure, '%s_%s' % (time.strftime('%Y%m%d_%H%M%S'), file))
    else:
        destname = os.path.join(import_brw.dest_path if success else import_brw.dest_path_failure, '%s_%s' % (time.strftime('%Y%m%d_%H%M%S'), remove_special_chars(file)))

    logging.getLogger('automated.import').info(_('Moving %s to %s') % (srcname, destname))


    ############################################## FTP #########################################################
    if import_brw.ftp_source_ok and dest_on_ftp and import_brw.ftp_protocol == 'ftp':
        # from FTP to FTP
        rep = ftp_connec.rename(srcname, destname)
        if not rep.startswith('2'):
            raise osv.except_osv(_('Error'), ('Unable to move file to destination location on FTP server'))
    elif not import_brw.ftp_source_ok and dest_on_ftp and import_brw.ftp_protocol == 'ftp':
        # from local to FTP
        rep = ftp_connec.storbinary('STOR %s' % destname, open(srcname, 'rb'))
        if not rep.startswith('2'):
            raise osv.except_osv(_('Error'), ('Unable to move local file to destination location on FTP server'))
        else:
            os.remove(srcname)
    elif import_brw.ftp_source_ok and not dest_on_ftp and import_brw.ftp_protocol == 'ftp':
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
    ############################################## SFTP #########################################################
    elif import_brw.ftp_source_ok and dest_on_ftp and import_brw.ftp_protocol == 'sftp':
        # from FTP to FTP
        try:
            sftp.rename(srcname, destname)
        except:
            raise osv.except_osv(_('Error'), ('Unable to move file to destination location %s on SFTP server') % destname)
    elif not import_brw.ftp_source_ok and dest_on_ftp and import_brw.ftp_protocol == 'sftp':
        # from local to FTP
        try:
            sftp.put(srcname, destname)
            os.remove(srcname)
        except:
            raise osv.except_osv(_('Error'), ('Unable to move local file to destination location on SFTP server'))
    elif import_brw.ftp_source_ok and not dest_on_ftp and import_brw.ftp_protocol == 'sftp':
        # from FTP to local
        try:
            sftp.get(srcname, destname, preserve_mtime=True)
            sftp.remove(srcname)
        except:
            raise osv.except_osv(_('Error'), ('Unable to move remote file to local destination location on SFTP server'))
    ############################################### LOCAL ####################################################
    else:
        # from local to local
        shutil.move(srcname, destname)

    return True


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

        if isinstance(ids, int):
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
    }


    def get_oldest_filename(self, job, ftp_connec=None, sftp=None, already=None):
        '''
        Get the oldest file in local or on FTP server
        '''
        if already is None:
            already = []
        logging.getLogger('automated.import').info(_('Getting the oldest file at location %s') % job.import_id.src_path)

        res = []
        if not job.import_id.ftp_source_ok:
            res = all_files_under(job.import_id.src_path, job.import_id.function_id.startswith, already)
        elif job.import_id.ftp_protocol == 'ftp':
            files = []
            ftp_connec.dir(job.import_id.src_path, files.append)
            file_names = []
            for file in files:
                if file.startswith('d'): # directory
                    continue
                if job.import_id.function_id.startswith and not file.split(' ')[-1].startswith(job.import_id.function_id.startswith):
                    continue
                file_names.append( posixpath.join(job.import_id.src_path, file.split(' ')[-1]) )
            for file in file_names:
                if file not in already:
                    dt = ftp_connec.sendcmd('MDTM %s' % file).split(' ')[-1]
                    dt = time.strptime(dt, '%Y%m%d%H%M%S') # '20180228170748'
                    res.append((dt, file))

        elif job.import_id.ftp_protocol == 'sftp':
            with sftp.cd(job.import_id.src_path):
                for fileattr in sftp.listdir_attr():
                    if sftp.isfile(fileattr.filename):
                        if job.import_id.function_id.startswith and not fileattr.filename.startswith(job.import_id.function_id.startswith):
                            continue
                        posix_name = posixpath.join(job.import_id.src_path, fileattr.filename)
                        if posix_name not in already:
                            res.append((fileattr.st_mtime, posix_name))
        for x in sorted(res, key=lambda x:x[0]):
            if not self.is_processing_filename(x[1]):
                return x[1]
        return False

    def manual_process_import(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]
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
        self.write(cr, uid, ids[0], {'start_time': time.strftime('%Y-%m-%d %H:%M:%S'), 'state': 'in_progress'}, context=context)
        # Background import
        thread = threading.Thread(target=self.process_import_bg, args=(cr.dbname, uid, wiz.import_id.id, ids[0], None))
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
        except Exception as e:
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

        if isinstance(import_id, int):
            import_id = [import_id]

        import_data = import_obj.browse(cr, uid, import_id[0], context=context)
        no_file = False
        already_done = []
        job_id = False
        while not no_file:
            start_time = time.strftime('%Y-%m-%d %H:%M:%S')
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
            data64 = None
            filename = False
            oldest_file = False
            ftp_connec = None
            sftp = None
            context.update({'no_raise_if_ok': True, 'auto_import_ok': True})
            try:
                if import_data.ftp_ok and import_data.ftp_protocol == 'ftp':
                    ftp_connec = self.pool.get('automated.import').ftp_test_connection(cr, uid, import_data.id, context=context)
                elif import_data.ftp_ok and import_data.ftp_protocol == 'sftp':
                    sftp = self.pool.get('automated.import').sftp_test_connection(cr, uid, import_data.id, context=context)
            except Exception as e:
                if job.id:
                    if isinstance(e, osv.except_osv):
                        msg = e.value
                    else:
                        msg = e
                    self.write(cr, uid, job_id, {'state': 'error', 'end_time': time.strftime('%Y-%m-%d %H:%M:%S'), 'start_time': start_time, 'comment': tools.ustr(msg)}, context=context)
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
                        oldest_file = self.get_oldest_filename(job, ftp_connec, sftp, already_done)
                        orig_file_name = oldest_file
                        already_done.append(oldest_file)
                        if not oldest_file:
                            raise ValueError()
                        filename = os.path.split(oldest_file)[1]
                        file_content = get_file_content(oldest_file, import_data.ftp_source_ok, ftp_connec, sftp)
                        bytes_content = bytes(file_content, 'utf8')
                        md5 = hashlib.md5(bytes_content).hexdigest()
                        data64 = base64.b64encode(bytes_content)
                    except ValueError:
                        no_file = True
                    except Exception:
                        no_file = True
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
                            error = _('A file with same checksum has been already imported !')
                            move_to_process_path(import_data, ftp_connec, sftp, filename, success=False)
                            self.infolog(cr, uid, _('%s :: Import file (%s) moved to destination path') % (import_data.name, filename))

                    if error:
                        self.infolog(cr, uid, '%s :: %s' % (import_data.name , error))
                        self.write(cr, uid, [job.id], {
                            'filename': filename,
                            'file_to_import': data64,
                            'start_time': start_time,
                            'end_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'nb_processed_records': 0,
                            'nb_rejected_records': 0,
                            'comment': error,
                            'file_sum': md5,
                            'state': 'done' if no_file else 'error',
                        }, context=context)
                        no_file = True
                        continue
                else: # file to import given
                    no_file = True
                    md5 = hashlib.md5(job.file_to_import).hexdigest()
                    oldest_file = os.path.join(job.import_id.src_path, job.filename)

                    oldest_file_desc = open(os.path.join(job.import_id.src_path, job.filename), 'wb+')
                    oldest_file_desc.write(base64.b64decode(job.file_to_import))
                    oldest_file_desc.close()

                    filename = job.filename
                    data64 = base64.b64encode(job.file_to_import)

                # Process import
                error_message = []
                state = 'done'
                try:
                    if import_data.ftp_source_ok and import_data.ftp_protocol == 'ftp':
                        prefix = '%s_' % filename.split('.')[0]
                        suffix = '.xls' if self.pool.get('stock.picking').get_import_filetype(cr, uid, filename) == 'excel' else '.xml'
                        temp_file = tempfile.NamedTemporaryFile(delete=False, prefix=prefix, suffix=suffix)
                        ftp_connec.retrbinary('RETR %s' % oldest_file, temp_file.write)
                        temp_file.close()
                        oldest_file = temp_file.name
                    elif import_data.ftp_source_ok and import_data.ftp_protocol == 'sftp':
                        tmp_dest_path = os.path.join(tempfile.gettempdir(), remove_special_chars(filename))
                        sftp.get(oldest_file, tmp_dest_path)
                        oldest_file = tmp_dest_path

                    processed, rejected, headers = getattr(
                        self.pool.get(import_data.function_id.model_id.model),
                        import_data.function_id.method_to_call
                    )(cr, uid, oldest_file, context=context)
                    if processed:
                        nb_processed += self.generate_file_report(cr, uid, job, processed, headers, ftp_connec=ftp_connec, sftp=sftp)

                    if rejected:
                        nb_rejected += self.generate_file_report(cr, uid, job, rejected, headers, rejected=True, ftp_connec=ftp_connec, sftp=sftp)
                        state = 'error'
                        for resjected_line in rejected:
                            line_message = ''
                            if resjected_line[0]:
                                line_message = _('Line %s: ') % resjected_line[0]
                            line_message += resjected_line[2]
                            error_message.append(line_message)

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
                    move_to_process_path(import_data, ftp_connec, sftp, filename, success=is_success)
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
                        'start_time': start_time,
                        'end_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'nb_processed_records': 0,
                        'nb_rejected_records': 0,
                        'comment': trace_b,
                        'file_sum': md5,
                        'file_to_import': data64,
                        'state': 'error',
                    }, context=context)
                    move_to_process_path(import_data, ftp_connec, sftp, filename, success=False)
                    self.infolog(cr, uid, _('%s :: Import file (%s) moved to destination path') % (import_data.name, filename))
            finally:
                if orig_file_name:
                    self.end_processing_filename(orig_file_name)

        return True

    def generate_file_report(self, cr, uid, job_brw, data_lines, headers, rejected=False, ftp_connec=None, sftp=None):
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
        on_ftp = job_brw.import_id.ftp_report_ok
        assert not on_ftp or (on_ftp and ftp_connec) or (on_ftp and sftp), _('FTP connection issue')

        if on_ftp:
            pth_filename = posixpath.join(job_brw.import_id.report_path, filename)
        else:
            pth_filename = os.path.join(job_brw.import_id.report_path, filename)

        self.infolog(cr, uid, _('Writing file report at %s') % pth_filename)
        csvfile = tempfile.NamedTemporaryFile(mode='w', delete=False) if on_ftp else open(pth_filename, 'w')
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

        if on_ftp and job_brw.import_id.ftp_protocol == 'ftp':
            with open(temp_path, 'r') as temp_file:
                rep = ftp_connec.storbinary('STOR %s' % pth_filename, temp_file)
                if not rep.startswith('2'):
                    raise osv.except_osv(_('Error'), _('Unable to write report on FTP server'))
        elif on_ftp and job_brw.import_id.ftp_protocol == 'sftp':
            try:
                with sftp.cd(job_brw.import_id.report_path):
                    sftp.put(temp_path, filename, preserve_mtime=True)
            except:
                raise osv.except_osv(_('Error'), _('Unable to write report on SFTP server'))

        csvfile = open(on_ftp and temp_path or pth_filename, 'r')
        att_obj.create(cr, uid, {
            'name': filename,
            'datas_fname': filename,
            'description': '%s Lines' % (rejected and _('Rejected') or _('Processed')),
            'res_model': 'automated.import.job',
            'res_id': job_brw.id,
            'datas': base64.b64encode(bytes(csvfile.read(), 'utf8'))
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
