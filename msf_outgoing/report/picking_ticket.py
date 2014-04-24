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
from osv import osv
from tools.translate import _
from report import report_sxw

class picking_ticket(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(picking_ticket, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'self': self,
            'cr': cr,
            'uid': uid,
            'getWarningMessage': self.get_warning,
        })

    def get_warning(self, picking):
        kc = ''
        dg = ''
        and_msg = ''

        for m in picking.move_lines:
            if m.kc_check:
                kc = 'heat sensitive'
            if m.dg_check:
                dg = 'dangerous goods'
            if kc and dg:
                and_msg = ' and '
                break

        if kc or dg:
            return _('You are about to pick %s%s%s products, please refer to the appropriate procedures') % (kc, and_msg, dg)

        return False
        
    def set_context(self, objects, data, ids, report_type=None):
        '''
        opening check
        '''
        for obj in objects:
            if obj.subtype != 'picking':
                raise osv.except_osv(_('Warning !'), _('Picking Ticket is only available for Picking Ticket Objects!'))
        
        return super(picking_ticket, self).set_context(objects, data, ids, report_type=report_type)

report_sxw.report_sxw('report.picking.ticket', 'stock.picking', 'addons/msf_outgoing/report/picking_ticket.rml', parser=picking_ticket, header=False)
