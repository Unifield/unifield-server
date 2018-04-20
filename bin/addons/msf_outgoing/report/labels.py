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

class labels(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(labels, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'range': range,
            'get_pack_weight': self.get_pack_weight,
        })

    def get_pack_weight(self, stock_picking, pack_num):
        '''
        Return weight of the given pack
        stock.picking.pack_family_memory_ids => pack.family.memory.ppl_id
        '''
        res_pack = self.pool.get('pack.family.memory').search(self.cr, self.uid, [
            ('ppl_id', '=', stock_picking.id),
            ('from_pack', '<=', pack_num),
            ('to_pack', '>=', pack_num),
        ])
        weight = 0.0
        if res_pack:
            res_pack = self.pool.get('pack.family.memory').browse(self.cr, self.uid, res_pack[0])
            weight = res_pack.weight

        return str(weight)



    def set_context(self, objects, data, ids, report_type=None):
        '''
        opening check
        '''
        for obj in objects:
            if obj.subtype != 'ppl' or obj.state != 'done':
                raise osv.except_osv(_('Warning !'), _('Labels are only available for completed Pre-Packing List Objects!'))

        return super(labels, self).set_context(objects, data, ids, report_type=report_type)

report_sxw.report_sxw('report.labels', 'stock.picking', 'addons/msf_outgoing/report/labels.rml', parser=labels, header=False)
