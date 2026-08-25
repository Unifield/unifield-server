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
            'getMissingPack': self.getMissingPack,
        })

    def getMissingPack(self, stock_picking):
        if not stock_picking.pack_family_memory_ids:
            return []
        missing = []
        if stock_picking.pack_family_memory_ids[0].from_pack != 1:
            if stock_picking.pack_family_memory_ids[0].from_pack == 2:
                missing.append('1')
            else:
                missing.append('1 - %s' % (stock_picking.pack_family_memory_ids[0].from_pack - 1))
        max_pack = len(stock_picking.pack_family_memory_ids)
        index = 1
        while index < max_pack:
            if stock_picking.pack_family_memory_ids[index].from_pack != stock_picking.pack_family_memory_ids[index-1].to_pack + 1:
                missing_from = stock_picking.pack_family_memory_ids[index-1].to_pack + 1
                missing_to = stock_picking.pack_family_memory_ids[index].from_pack - 1
                if missing_to == missing_from:
                    missing.append('%s'%missing_to)
                else:
                    missing.append('%s - %s' % (missing_from, missing_to))
            index += 1

        return missing

    def set_context(self, objects, data, ids, report_type=None):
        '''
        opening check
        '''
        for obj in objects:
            if obj.subtype != 'ppl' or obj.state != 'done':
                raise osv.except_osv(_('Warning !'), _('Labels are only available for completed Pre-Packing List Objects!'))

        return super(labels, self).set_context(objects, data, ids, report_type=report_type)

report_sxw.report_sxw('report.labels', 'stock.picking', 'addons/msf_outgoing/report/labels.rml', parser=labels, header=False)
