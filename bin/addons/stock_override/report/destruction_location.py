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

class destruction_location(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(destruction_location, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'process': self.process,
            '_get_project': self._get_project,
        })
        return

    def process(self, selected_moves):
        # get the list of location with destruction type
        loc_obj = self.pool.get('stock.location')
        destruction_loc_ids = loc_obj.search(self.cr, self.uid, [('name', '=', 'Destruction')])

        result = []
        for move in selected_moves:
            # then add only the selected move with destination location in destruction locations
            if move.location_dest_id and move.location_dest_id.id in destruction_loc_ids: 
                result.append(move.id)
        
        stock_move_obj = pooler.get_pool(self.cr.dbname).get('stock.move')
        data = stock_move_obj._get_destruction_products(self.cr,self.uid, result)
        return data

    def _get_project(self):
        return self.cr.dbname
    
report_sxw.report_sxw('report.destruction.location','stock.move','addons/stock_override/report/destruction_location.rml',parser=destruction_location, header=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
