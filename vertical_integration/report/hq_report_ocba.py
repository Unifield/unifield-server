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

import datetime
import csv
import StringIO
import pooler
import zipfile
from tempfile import NamedTemporaryFile
import os
from osv import osv
from tools.translate import _

from report import report_sxw


class hq_report_ocba(report_sxw.report_sxw):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def _enc(self, st):
        if isinstance(st, unicode):
            return st.encode('utf8')
        return st

    def translate_country(self, cr, uid, pool, browse_instance, context={}):
        mapping_obj = pool.get('country.export.mapping')
        if browse_instance:
            mapping_ids = mapping_obj.search(cr, uid, [('instance_id', '=', browse_instance.id)], context=context)
            if len(mapping_ids) > 0:
                mapping = mapping_obj.browse(cr, uid, mapping_ids[0], context=context)
                return mapping.mapping_value
        return "0"

    def _generate_files(self, integration_ref, file_data):
        """
        :return zip buffer
        """
        zip_buffer = StringIO.StringIO()
        out_zipfile = zipfile.ZipFile(zip_buffer, "w")
        tmp_fds = []
        file_prefix = integration_ref and (integration_ref + '_') or ''

        # fill zip file
        for f in file_data:
            tmp_fd = NamedTemporaryFile('w+b', delete=False)
            tmp_fds.append(tmp_fd)
            writer = csv.writer(tmp_fd, quoting=csv.QUOTE_ALL)

            for line in file_data[f]['data']:
                writer.writerow(map(self._enc, line))
            tmp_fd.close()

            out_zipfile.write(tmp_fd.name,
                "%s%s" % (file_prefix, file_data[f]['file_name'], ),
                zipfile.ZIP_DEFLATED
            )
        out_zipfile.close()

        # delete temporary files
        for fd in tmp_fds:
            os.unlink(fd.name)

        return zip_buffer

    def _mark_exported_entries(self, cr, uid, move_line_ids, analytic_line_ids):
        if move_line_ids:
            cr.execute(
                "UPDATE account_move_line SET exported='t' WHERE id in %s",
                (tuple(move_line_ids), )
            )

        if analytic_line_ids:
            cr.execute(
                "UPDATE account_analytic_line SET exported='t' WHERE id in %s",
                (tuple(analytic_line_ids), )
            )

    def create(self, cr, uid, ids, data, context=None):
        file_data = {
            'entries': { 'file_name': 'entries', 'data': [], },
            'fc': { 'file_name': 'contracts', 'data': [], },
        }

        pool = pooler.get_pool(cr.dbname)
        move_line_ids = []
        analytic_line_ids = []

        # get wizard form values
        period = pool.get('account.period').browse(cr, uid,
            data['form']['period_id'])
        integration_ref = ''
        if len(data['form']['instance_ids']) > 0:
            parent_instance = pool.get('msf.instance').browse(cr, uid,
                data['form']['instance_ids'][0], context=context)
            if parent_instance:
                if period and period.date_start:
                    integration_ref = parent_instance.code[:2] \
                        + period.date_start[5:7]

        # generate export data
        file_data['entries']['data'].append(['foo', 'bar', ])
        file_data['fc']['data'].append(['grant', 'foobar', ])

        # generate zip result and post processing
        zip_buffer = self._generate_files(integration_ref, file_data)
        self._mark_exported_entries(cr, uid, move_line_ids, analytic_line_ids)
        return (zip_buffer.getvalue(), 'zip')

hq_report_ocba('report.hq.ocba', 'account.move.line', False, parser=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
