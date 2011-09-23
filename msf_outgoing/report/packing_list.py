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

from report import report_sxw

class packing_list(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(packing_list, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'get_selection': self.get_selection,
        })
        
    def get_selection(self, o, field):
        """
        Returns the fields.selection label
        """
        sel = self.pool.get(o._name).fields_get(self.cr, self.uid, [field])
        res = dict(sel[field]['selection']).get(getattr(o,field),getattr(o,field))
        name = '%s,%s' % (o._name, field)
        tr_ids = self.pool.get('ir.translation').search(self.cr, self.uid, [('type', '=', 'selection'), ('name', '=', name),('src', '=', res)])
        if tr_ids:
            return self.pool.get('ir.translation').read(self.cr, self.uid, tr_ids, ['value'])[0]['value']
        else:
            return res

report_sxw.report_sxw('report.packing.list', 'shipment', 'addons/msf_outgoing/report/packing_list.rml', parser=packing_list, header="external")

