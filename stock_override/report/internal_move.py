# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF 
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
import pooler

class internal_move(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(internal_move, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'get_selec': self.get_selection,
            'get_lines': self._get_lines,
        })

    def get_selection(self, o, field):
        """
        Retourne le libellé d'un champ sélection
        """
        sel = self.pool.get(o._name).fields_get(self.cr, self.uid, [field])
        res = dict(sel[field]['selection']).get(getattr(o,field),getattr(o,field))
        name = '%s,%s' % (o._name, field)
        tr_ids = self.pool.get('ir.translation').search(self.cr, self.uid, [('type', '=', 'selection'), ('name', '=', name),('src', '=', res)])
        if tr_ids:
            return self.pool.get('ir.translation').read(self.cr, self.uid, tr_ids, ['value'])[0]['value']
        else:
            return res

    def _get_lines(self, picking):
        if not picking or not picking.move_lines:
            return []
        return [l for l in picking.move_lines if l.state and l.state != 'cancel']

report_sxw.report_sxw('report.internal.move','stock.picking','addons/stock_override/report/internal_move.rml',parser=internal_move, header=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
