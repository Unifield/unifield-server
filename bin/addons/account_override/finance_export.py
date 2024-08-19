#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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

from osv import osv
from tools.translate import _
import csv
from io import BytesIO
import pooler
import zipfile
from tempfile import NamedTemporaryFile
import os
from hashlib import md5
from string import Template

class finance_archive():
    """
    SQLREQUESTS DICTIONNARY
     - key: name of the SQL request
     - value: the SQL request to use

    PROCESS REQUESTS LIST: list of dict containing info to process some SQL requests
    Dict:
     - [optional] headers: list of headers that should appears in the CSV file
     - filename: the name of the result filename in the future ZIP file
     - key: the name of the key in SQLREQUESTS DICTIONNARY to have the right SQL request
     - [optional] query_params: data to use to complete SQL requests
     - [optional] query_tpl_context: dict data to use to complete SQL requests with templating like $var
     - [optional] function: name of the function to postprocess data (example: to change selection field into a human readable text)
     - [optional] fnct_params: params that would used on the given function
     - [optional] delete_columns: list of columns to delete before writing files into result
     - [optional] id (need 'object'): number of the column that contains the ID of the element. Column number begin from 0. Note that you should adapt your SQL request to add the ID of lines.
     - [optional] object (need 'id'): name of the object in the system. For an example: 'account.bank.statement'.
    TIP & TRICKS:
     + More than 1 request in 1 file: just use same filename for each request you want to be in the same file.
     + If you cannot do a SQL request to create the content of the file, do a simple request (with key) and add a postprocess function that returns the result you want
     + Do not repeat headers if you use the same filename for more than 1 request. This avoid having multiple lines as headers.
    """

    def __init__(self, sql, process, context=None):
        if context is None:
            context = {}
        self.context = context
        self.sqlrequests = sql
        self.processrequests = process
        if 'background_id' in context:
            self.bg_id = context['background_id']
        else:
            self.bg_id = None

    def line_to_utf8(self, line):
        """
        Change all elements of this line to UTF-8
        """
        newline = []
        if not line:
            return []
        for element in line:
            if isinstance(line, bytes):
                newline.append(str(element,'utf8'))
            else:
                newline.append(element)
        return newline

    def delete_x_column(self, line, columns=[]):
        """
        Take numbers in 'columns' list and delete them from given line.
        Begin from 0.
        """
        if not line:
            return []
        if not columns:
            return line
        # Create a list of all elements from line except those given in columns
        newline = []
        for element in sorted([x for x in range(len(line)) if x not in columns]):
            newline.append(line[element])
        return newline

    def get_selection(self, cr, model, field):
        """
        Return a list of all selection from a field in a given model.
        """
        pool = pooler.get_pool(cr.dbname)
        data = pool.get(model).fields_get(cr, 1, [field])
        return dict(data[field]['selection'])

    def get_hash(self, cr, uid, ids, model):
        """
        Create a concatenation of:
          - dbname
          - ids
          - model
        Then create a md5
        """
        return self._get_hash(cr, uid, ids, model)

    @staticmethod
    def _get_hash(cr, uid, ids, model):
        """
        Create a concatenation of:
          - dbname
          - ids
          - model
        Then create a md5
        """
        # Prepare some values
        md5sum = md5()
        is_list = False
        if not ids or not model:
            return ''
        if not isinstance(ids, (str, list)):
            return ''
        if isinstance(ids, list):
            is_list = True
            res_ids = ids
        # preapre some values
        name = cr.dbname
        if not is_list:
            ids = sorted(ids.split(','))
            # We have this: ['2', '4', '6', '8']
            # And we want this: [2, 4, 6, 8]
            # So we do some process on this list
            res_ids = [int(x) for x in ids]
        md5sum.update(bytes(','.join([name, model, str(res_ids)]), 'utf8'))
        return md5sum.hexdigest()

    def postprocess_selection_columns(self, cr, uid, data, changes, column_deletion=False):
        """
        This method takes each line from data and change some columns regarding "changes" variable.
        'changes' should be a list containing some tuples. A tuple is composed of:
         - a model (example: res.partner)
         - the selection field in which retrieve all real values (example: partner_type)
         - the column number in the data lines from which you want to change the value (begin from 0)
        """
        # Checks
        if not changes:
            return data
        # Prepare some values
        new_data = []
        # Fetch selections
        changes_values = {}
        for change in changes:
            model = change[0]
            field = change[1]
            changes_values[change] = self.get_selection(cr, model, field)
        # Browse each line to replace partner type by it's human readable value (selection)
        # partner_type is the 3rd column
        for line in data:
            tmp_line = list(line)
            # Delete some columns if needed
            if column_deletion:
                tmp_line = self.delete_x_column(list(line), column_deletion)
            for change in changes:
                column = change[2]
                # use line value to search into changes_values[change] (the list of selection) the right value
                tmp_line[column] = changes_values[change][tmp_line[column]]
            new_data.append(self.line_to_utf8(tmp_line))
        return new_data

    def _execute_query(self, cr, fileparams, select=None, ocb_vi_cond='', insert_numbering=False):
        # fetch data with given sql query
        sql = self.sqlrequests[fileparams['key']]
        if select is not None:
            sql = '%s %s' % (select, sql)
        if fileparams.get('query_tpl_context', False):
            sql = Template(sql).safe_substitute(
                fileparams.get('query_tpl_context'))

        if select is not None:
            sql = sql.replace('#OCB_VI_COND#',  ocb_vi_cond)
        if insert_numbering:
            sql = "INSERT INTO ocb_vi_export_number (entry_sequence, move_line_id, analytic_line_id, period_id) (%s)" % sql


        if fileparams.get('query_params', False):
            cr.execute(sql, fileparams['query_params'])
        elif fileparams.get('dict_query_params', False):
            cr.execute(sql, fileparams['dict_query_params'])
        else:
            cr.execute(sql)

    def archive(self, cr, uid):
        """
        Create an archive with sqlrequests params and processrequests params.
        """
        # open buffer for result zipfile
        zip_buffer = BytesIO()
        # Prepare some values
        pool = pooler.get_pool(cr.dbname)

        # List is composed of a tuple containing:
        # - filename
        # - key of sqlrequests dict to fetch its SQL request
        files = {}

        if self.bg_id:
            bg_report_obj = pool.get('memory.background.report')
        else:
            bg_report_obj = None

        request_count = 0

        for fileparams in self.processrequests:
            if not fileparams.get('filename', False):
                raise osv.except_osv(_('Error'), _('Filename param is missing!'))
            if not fileparams.get('key', False):
                raise osv.except_osv(_('Error'), _('Key param is missing!'))
            # temporary file (process filename to display datetime data instead of %(year)s chars)
            filename = pool.get('ir.sequence')._process(cr, uid, fileparams['filename'] or '') or fileparams['filename']
            if filename not in files:
                tmp_file = NamedTemporaryFile('w+', delete=False, newline='')
            else:
                tmp_file = files[filename]

            if fileparams.get('select_1') and self.context.get('poc_export') and pool.get('res.company')._get_instance_level(cr, uid) == 'section':
                # trigger ocb_numbering only at HQ level
                ocb_vi_cond = 'AND ocb_vi.id is NULL'
                if fileparams.get('numbering_cond'):
                    ocb_vi_cond = ' %s AND %s ' % (ocb_vi_cond, fileparams.get('numbering_cond'))
                self._execute_query(cr, fileparams, select=fileparams['select_1'], ocb_vi_cond=ocb_vi_cond, insert_numbering=True)
                # create unique id on move_id, period_id
                cr.execute("INSERT INTO ocb_vi_je_period_number (entry_sequence, period_id) (SELECT distinct entry_sequence, period_id from ocb_vi_export_number WHERE move_number IS NULL) ON CONFLICT DO NOTHING")

                # update move_number values
                cr.execute("""UPDATE ocb_vi_export_number set move_number=je_number.id
                    FROM
                        ocb_vi_je_period_number je_number
                    WHERE
                        ocb_vi_export_number.move_number is null and
                        ocb_vi_export_number.entry_sequence = je_number.entry_sequence and
                        ocb_vi_export_number.period_id = je_number.period_id
                """)

                cr.execute("""UPDATE ocb_vi_export_number set line_number = num.rn
                    FROM
                    (
                        SELECT row_number() over (partition by move_number order by line_number nulls last, analytic_line_id nulls first, move_line_id) AS rn, id
                        FROM ocb_vi_export_number
                    ) AS num
                    WHERE ocb_vi_export_number.id = num.id and line_number is null;
                """)

                dbname = 'OCBHQ' # cr.dbname
                cr.execute("""UPDATE ocb_vi_export_number set coda_identifier=MD5(%s||',account.move.line,['||move_line_id||']')
                    where
                        coda_identifier is null and
                        analytic_line_id is null
                """, (dbname, ))

                cr.execute("""UPDATE ocb_vi_export_number set coda_identifier=MD5(%s||',account.analytic.line,['||analytic_line_id||']')
                    where
                        coda_identifier is null and
                        analytic_line_id is not null
                """, (dbname, ))


            if fileparams.get('select_2'):
                self._execute_query(cr, fileparams, select=fileparams['select_2'])
            else:
                self._execute_query(cr, fileparams)


            sqlres = cr.fetchall()
            # Fetch ID column and mark lines as exported
            if fileparams.get('id', None) != None:
                if not fileparams.get('object', False):
                    raise osv.except_osv(_('Error'), _('object param is missing to use ID one.'))
                # prepare needed values
                object_name = fileparams['object']
                pool = pooler.get_pool(cr.dbname)
                tablename = pool.get(object_name)._table
                if not tablename:
                    raise osv.except_osv(_('Error'), _("Table name not found for the given object: %s") % (fileparams['object'],))
                key_column_number = fileparams['id']
                # get ids from previous request
                ids = [x and x[key_column_number] or 0 for x in sqlres]
                # mark lines as exported
                if ids:
                    update_request = 'UPDATE ' + tablename + ' SET exported=\'t\' WHERE id in %s'  # not_a_user_entry
                    try:
                        cr.execute(update_request, (tuple(ids),))
                    except Exception as e:
                        raise osv.except_osv(_('Error'), _('An error occurred: %s') % (e ,))
            without_headers = []
            # Check if a function is given. If yes, use it.
            # If not, transform lines into UTF-8. Note that postprocess method should transform lines into UTF-8 ones.
            if fileparams.get('function', False):
                fnct = getattr(self, fileparams['function'], False)
                delete_columns = fileparams.get('delete_columns', False)
                # If the function has some params, use them.
                if fnct and fileparams.get('fnct_params', False):
                    without_headers = fnct(cr, uid, sqlres, fileparams['fnct_params'], column_deletion=delete_columns)
                elif fnct:
                    without_headers = fnct(cr, uid, sqlres, column_deletion=delete_columns)
            else:
                # Change to UTF-8 all unicode elements
                for line in sqlres:
                    # Delete useless columns if needed
                    if fileparams.get('delete_columns', False):
                        line = self.delete_x_column(line, fileparams['delete_columns'])
                    without_headers.append(self.line_to_utf8(line))
            result = without_headers
            if fileparams.get('headers', False):
                headers = [fileparams['headers']]
                for line in result:
                    headers.append(line)
                result = headers
            # Write result in a CSV writer then close it.
            writer = csv.writer(tmp_file, quoting=csv.QUOTE_ALL)
            writer.writerows(result)
            # Only add a link to the temporary file if not in "files" dict
            if filename not in files:
                files[filename] = tmp_file

            if bg_report_obj:
                request_count += 1
                percent = request_count / float(len(self.processrequests) + 1)  # add 1
                # to the total because task is not finish at the end of the for
                # loop, there is some ZIP work to do
                bg_report_obj.update_percent(cr, uid, [self.bg_id], percent)

        # WRITE RESULT INTO AN ARCHIVE
        # Create a ZIP file
        out_zipfile = zipfile.ZipFile(zip_buffer, "w")
        for filename in files:
            tmpfile = files[filename]
            # close temporary file
            tmpfile.close()
            # write content into zipfile
            out_zipfile.write(tmpfile.name, filename, zipfile.ZIP_DEFLATED)
            # unlink temporary file
            os.unlink(tmpfile.name)
        # close zip
        out_zipfile.close()
        out = zip_buffer.getvalue()
        # Return result
        return (out, 'zip')


def log_vi_exported(self, cr, uid, report_name, obj_id, file_name):
    """
    Stores a message in the res.logs when the VI report is exported, with the related filename and DB name. This message isn't
    displayed in the interface, its main goal is to be able to check that the DB IDs have been generated from the right database.
    """
    self.log(cr, uid, obj_id,
             _('A report "%s" has been generated under the name "%s" from the database "%s".') % (report_name, file_name, cr.dbname),
             read=True)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
