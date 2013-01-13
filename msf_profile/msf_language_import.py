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

import tools
import base64
from tempfile import TemporaryFile
from osv import osv, fields
import csv
import psycopg2

class msf_language_import(osv.osv_memory):
    """ Language Import """

    _name = "msf.language.import"
    _description = "Language Import"
    _inherit = "ir.wizard.screen"

    _columns = {
        'name': fields.char('Language Name',size=64 , required=True),
        'code': fields.char('Code (eg:en__US)',size=5 , required=True),
        'data': fields.binary('File', required=True),
    }

    def import_msf_lang(self, cr, uid, ids, context):
        """
        This method is for importing the data translation in MSF 
        """

        import_data = self.browse(cr, uid, ids)[0]
        fileobj = TemporaryFile('w+')
        fileobj.write(base64.decodestring(import_data.data))

        fileobj.seek(0)
        first_line = fileobj.readline()
        reader = csv.reader(fileobj, delimiter=",",quotechar='"')
        for row in reader:
            '''
            There are some open question, which mostly a bug of OpenERP, as what happens if there are several lines in the ir_translation that have the same pair
            (src, name) but different res_id? in this case there would be absolutely wrong update, as the system will pick the first text only
            '''
            cr.execute("SELECT src, xml_id, name, res_id, module, type FROM ir_translation WHERE name = %s and src =%s", (row[1], row[2]))
            for res in cr.fetchall():
                # import only one translation for each text provided
                cr.execute(''' INSERT INTO ir_translation (src, xml_id, name, res_id, module, type, value, lang) values
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                ''' , (res[0], res[1], res[2], res[3], res[4], res[5], row[3], import_data.code))
                break

        return {}

msf_language_import()
