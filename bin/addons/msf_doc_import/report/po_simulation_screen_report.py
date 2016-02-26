# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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

import time
import pooler

from report import report_sxw

class po_simulation_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(po_simulation_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'addr_to_str': self._get_addr_to_str,
        })

    def _get_addr_to_str(self, addr):
       pool = pooler.get_pool(self.cr.dbname)
       return pool.get('res.partner.address').name_get(self.cr, self.uid, [addr.id])[0][1]

report_sxw.report_sxw('report.po.simulation.screen', 'wizard.import.po.simulation.screen', 'addons/msf_doc_import/report/po_simulation_screen_report.rml', parser=po_simulation_report, header=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
