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

        # FIXME: do process here

        # WRITE RESULT INTO SOME FILES AND ARCHIVE ALL
        # open buffer
        zip_buffer = StringIO.StringIO()
        # create 2 files into
        first_fileobj = NamedTemporaryFile('w+b', delete=False)
        second_fileobj = NamedTemporaryFile('w+b', delete=False)
        # open a CSV writer for 1st file. Write into then close it.
        writer = csv.writer(first_fileobj, quoting=csv.QUOTE_ALL)
        writer.writerow("Something")
        first_fileobj.close()
        # open a CSV writer for the 2nd file. Write into then close it.
        writer = csv.writer(second_fileobj, quoting=csv.QUOTE_ALL)
        writer.writerow("Else")
        second_fileobj.close()
        # Create a ZIP file
        out_zipfile = zipfile.ZipFile(zip_buffer, "w")
        # include first file into with "FILENAME.csv"
        out_zipfile.write(first_fileobj.name, "FILENAME1.csv", zipfile.ZIP_DEFLATED)
        out_zipfile.write(second_fileobj.name, "FILENAME2.csv", zipfile.ZIP_DEFLATED)
        # close zip
        out_zipfile.close()
        out = zip_buffer.getvalue()
        # unlink 1st and 2nd file
        os.unlink(first_fileobj.name)
        os.unlink(second_fileobj.name)
        # Return result
        return (out, 'zip')

hq_report_ocb('report.hq.ocb', 'account.move.line', False, parser=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
