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

class packing_list(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(packing_list, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getPackingList': self._get_packing_list,
        })

    def _get_packing_list(self, shipment):
        '''
        Return a list of PPL with, for each of them, the list of pack family
        that are linked.

        :param shipment: browse_record of a shipment

        :return: A list of tuples with the pre-packing list as first element and
                 the list of linked pack-family as second element
        :rtype: list
        '''
        res = {}
        i = 0
        nb_pack = len(shipment.pack_family_memory_ids)
        for pf in shipment.pack_family_memory_ids:
            i += 1
            res.setdefault(pf.ppl_id.name, {
                'ppl': pf.ppl_id,
                'pf': [],
                'last': False,
            })
            res[pf.ppl_id.name]['pf'].append(pf)

        sort_keys = sorted(res.keys())

        result = []
        for key in sort_keys:
            result.append(res.get(key))

        result[-1]['last'] = True

        return result

    def set_context(self, objects, data, ids, report_type=None):
        '''
        opening check
        '''
        #for obj in objects:
            #if not obj.backshipment_id:
                #raise osv.except_osv(_('Warning !'), _('Packing List is only available for Shipment Objects (not draft)!'))

        return super(packing_list, self).set_context(objects, data, ids, report_type=report_type)

report_sxw.report_sxw('report.packing.list', 'shipment', 'addons/msf_outgoing/report/packing_list.rml', parser=packing_list, header="external")
