# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import csv
import StringIO
import pooler
import zipfile
from tempfile import NamedTemporaryFile
import os

from report import report_sxw

class hq_report_ocb(report_sxw.report_sxw):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def get_selection(self, cr, model, field):
        """
        Return a list of all selection from a field in a given model.
        """
        pool = pooler.get_pool(cr.dbname)
        data = pool.get(model).fields_get(cr, 1, [field])
        return dict(data[field]['selection'])

    def postprocess_selection_columns(self, cr, data, changes):
        """
        This method takes each line from data and change some columns regarding "changes" variable.
        'changes' should be a list containing some tuples. A tuple is composed of:
         - a model (example: res.partner)
         - the selection field in which retrieve all real values (example: partner_type)
         - the column number in the data lines from which you want to change the value
        """
        # Checks
        if not changes:
            return data
        # Prepare some values
        pool = pooler.get_pool(cr.dbname)
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
            for change in changes:
                column = change[2]
                # use line value to search into changes_values[change] (the list of selection) the right value
                tmp_line[column] = changes_values[change][tmp_line[column]]
            new_data.append(tmp_line)
        return new_data

    def create(self, cr, uid, ids, data, context=None):
        """
        Create a kind of report and return its content.
        The content is composed of:
         - 3rd parties list (partners)
         - Employees list
         - Journals
         - Cost Centers
         - FX Rates
         - Liquidity balances
         - Financing Contracts
         - Raw data (a kind of synthesis of funding pool analytic lines)
        """
        # Checks
        if context is None:
            context = {}
        # Prepare some values
        pool = pooler.get_pool(cr.dbname)
        # open buffer for result zipfile
        zip_buffer = StringIO.StringIO()

        # SQLREQUESTS DICTIONNARY
        # - key: name of the SQL request
        # - value: the SQL request to use
        sqlrequests = {
            'partner': """
                SELECT name, ref, partner_type, CASE WHEN active='t' THEN 'True' WHEN active='f' THEN 'False' END AS active
                FROM res_partner;
                """,
            'employee': """
                SELECT r.name, e.identification_id, r.active, e.employee_type
                FROM hr_employee AS e, resource_resource AS r
                WHERE e.resource_id = r.id;
                """,
            'journal': """
                SELECT i.name, j.code, j.name, j.type
                FROM account_journal AS j, msf_instance AS i
                WHERE j.instance_id = i.id;
                """,
        }

        # PROCESS REQUESTS LIST: list of tuples containing info to process some SQL requests
        # Tuple:
        # - first the name of the result filename in the future ZIP file
        # - then name of the key in SQLREQUESTS DICTIONNARY to have the right SQL request
        # - [optional] data to use to complete SQL requests
        # - [optional] function name to postprocess data
        processrequests = [
            ('partners.csv', 'partner', False, 'postprocess_selection_columns', [('res.partner', 'partner_type', 2)]),
            ('employee.csv', 'employee'),
            ('journals.csv', 'journal', False, 'postprocess_selection_columns', [('account.journal', 'type', 3)]),
        ]

        # List is composed of a tuple containing:
        # - filename
        # - key of sqlrequests dict to fetch its SQL request
        files = []
        for fileparams in processrequests:
            # temporary file
            filename = fileparams[0]
            tmp_file = NamedTemporaryFile('w+b', delete=False)

            # FIXME: create a query params!
            # fetch data with given sql query
            sql = sqlrequests[fileparams[1]]
            cr.execute(sql)
            fileres = cr.fetchall()
            # Check if postprocess method exists. If yes, use it
            if len(fileparams) > 3:
                fnct = getattr(self, fileparams[3], False)
                # If a 4th params appears, add it to the method call, otherwise do a simple call
                if fnct and len(fileparams) > 4:
                    fileres = fnct(cr, fileres, fileparams[4])
                elif fnct:
                    fileres = fnct(cr, fileres)
            # Write result in a CSV writer then close it.
            writer = csv.writer(tmp_file, quoting=csv.QUOTE_ALL)
            writer.writerows(fileres)
            tmp_file.close()
            files.append((tmp_file.name, filename))

        # WRITE RESULT INTO AN ARCHIVE
        # Create a ZIP file
        out_zipfile = zipfile.ZipFile(zip_buffer, "w")
        for tmp_filename, filename in files:
            out_zipfile.write(tmp_filename, filename, zipfile.ZIP_DEFLATED)
            # unlink file
            os.unlink(tmp_filename)
        # close zip
        out_zipfile.close()
        out = zip_buffer.getvalue()
        # Return result
        return (out, 'zip')

hq_report_ocb('report.hq.ocb', 'account.move.line', False, parser=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
