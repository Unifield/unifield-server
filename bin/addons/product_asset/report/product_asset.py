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

class order(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(order, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'get_product_name': self._get_product_name,
            'get_type': self._get_type,
            'get_value': self._get_value,
        })
        
    def _get_product_name(self, asset):
        pname = ''
        if asset and asset.product_id:
            pname = self.pool.get('product.product').name_get(self.cr,
                                                              self.uid,
                                           [asset.product_id.id])[0][1]
        return pname
        
    def _get_type(self, asset):
        ptype = ''
        if asset and asset.asset_type_id:
            ptype = asset.asset_type_id.name
            if ptype:
                ptype = '(' + ptype + ')'
        return ptype
        
    def _get_value(self, asset):
        return str(asset.invo_value) + ' ' + asset.invo_currency.name

report_sxw.report_sxw('report.product.asset', 'product.asset', 'addons/product_asset/report/product_asset.rml', parser=order, header="external")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

