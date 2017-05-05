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
from osv import osv
from tools.translate import _

class stock_picking_test(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(stock_picking_test, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'self': self,
            'cr': cr,
            'uid': uid,
        })
        
        
    def set_context(self, objects, data, ids, report_type = None):
        '''
        
        '''
        for obj in objects:
            if obj.subtype != 'ppl':
                raise osv.except_osv(_('Warning !'), _('Pre-Packing List is only available for Pre-Packing Objects!'))
        
        
        return super(stock_picking_test, self).set_context(objects, data, ids, report_type)
report_sxw.report_sxw('report.stock.picking.test', 'stock.picking', 'addons/msf_outgoing/report/stock_picking_test.rml', parser=stock_picking_test, header="external")

