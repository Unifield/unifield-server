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

from osv import osv
from osv import fields

from tools.translate import _


def all_files_under(path):
    """
    Iterates through all files that are under the given path.
    :param path: Path on which we want to iterate
    """
    for cur_path, dirnames, filenames in os.walk(path):
        for filename in filenames:
            yield os.path.join(cur_path, filename)


def move_to_process_path(file, src_path, dest_path):
    """
    Move the file `file` from `src_path` to `dest_path`
    :param file: Name of the file to move
    :param src_path: Source folder
    :param dest_path: Destination folder
    :return: return True
    """
    srcname = os.path.join(src_path, file)
    renamed = os.path.join(dest_path, '%s_%s' % (time.strftime('%Y%m%d_%H%M%S'), file))
    shutil.move(srcname, renamed)
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
            readonly=True,
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
    }

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
        if context is None:
            context = []

        if isinstance(ids, (int, long)):
            ids = [ids]

        for job in self.browse(cr, uid, ids, context=context):
            nb_rejected = 0
            nb_processed = 0
            start_time = time.strftime('%Y-%m-%d %H:%M:%S')
            no_file = False
            md5 = None
            error = None
            try:
                oldest_file = min(all_files_under(job.import_id.src_path), key=os.path.getmtime)
                md5 = hashlib.md5(open(oldest_file)).hexdigest()
            except ValueError:
                no_file = True

            if no_file:
                error = _('No file to import in %s !') % job.import_id.src_path
            elif md5 and self.search(cr, uid, [('import_id', '=', job.import_id.id), ('file_sum', '=', md5)], limit=1, order='NO_ORDER', context=context):
                error = _('A file with same checksum has been already imported !')

            if error:
                self.write(cr, uid, [job.id], {
                    'filename': False,
                    'start_time': start_time,
                    'end_time': False,
                    'nb_processed_records': 0,
                    'nb_rejected_records': 0,
                    'comment': error,
                }, context=context)
                continue

            # Process import
            try:
                processed, rejected, headers = getattr(
                    self.pool.get(job.import_id.function_id.model_id.model),
                    job.import_id.function_id.method_to_call
                )(cr, uid, oldest_file)
                if processed:
                    nb_processed = self.generate_file_report(cr, uid, job, processed, headers)

                if rejected:
                    nb_rejected = self.generate_file_report(cr, uid, job, rejected, headers, rejected=True)

                filename = os.path.split(oldest_file)[1]
                move_to_process_path(filename, job.import_id.src_path, job.import_id.dest_path)

                self.write(cr, uid, [job.id], {
                    'filename': filename,
                    'start_time': start_time,
                    'end_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'nb_processed_records': nb_processed,
                    'nb_rejected_records': nb_rejected,
                }, context=context)
            except Exception as e:
                self.write(cr, uid, [job.id], {
                    'filename': False,
                    'start_time': start_time,
                    'end_time': False,
                    'nb_processed_records': 0,
                    'nb_rejected_records': 0,
                    'comment': str(e),
                }, context=context)

        return True

    def generate_file_report(self, cr, uid, job_brw, data_lines, headers, rejected=False):
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

        with open(pth_filename, 'wb') as csvfile:
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

        csvfile = open(pth_filename, 'r')
        att_obj.create(cr, uid, {
            'name': filename,
            'datas_fname': filename,
            'description': '%s Lines' % (rejected and _('Rejected') or _('Processed')),
            'res_model': 'automated.import.job',
            'res_id': job_brw.id,
            'datas': base64.encodestring(csvfile.read())
        })

        return len(data_lines)

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
