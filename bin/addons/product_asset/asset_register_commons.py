#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) TeMPO Consulting (<http://www.tempo-consulting.fr/>), MSF.
#    All Rigts Reserved
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

from osv import osv
from osv import fields
import time
from tools.translate import _
from datetime import datetime

class asset_register_commons(osv.osv):
    _name = 'asset.register.commons'

    def get_asset_register_data(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        asset_obj = self.pool.get('product.asset')
        period_obj = self.pool.get('account.period')
        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        prop_instance = company and company.name or ''
        func_currency = company and company.currency_id.name or ''
        func_currency_id = company and company.currency_id.id
        date = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        current_period_id = period_obj.find(cr, uid)[0]
        current_period = current_period_id and period_obj.browse(cr, uid, current_period_id, context=context).name or ''

        filename = '_'.join(('Fixed Assets Register', prop_instance, datetime.now().strftime("%Y%m%d")))

        draft_asset_ids = asset_obj.search(cr, uid, [('state', '=', 'draft')], context=context)
        open_asset_ids = asset_obj.search(cr, uid, [('state', '=', 'open')], context=context)
        active_asset_ids = asset_obj.search(cr, uid, [('state', '=', 'running')], context=context)
        depreciated_asset_ids = asset_obj.search(cr, uid, [('state', '=', 'depreciated')], context=context)
        disposed_asset_ids = asset_obj.search(cr, uid, [('state', '=', 'disposed')], context=context)

        data = {
            'draft_asset_ids': draft_asset_ids or [],
            'open_asset_ids': open_asset_ids or [],
            'active_asset_ids': active_asset_ids or [],
            'depreciated_asset_ids': depreciated_asset_ids or [],
            'disposed_asset_ids': disposed_asset_ids or [],
            'model': 'product.asset',
            'context': context,
            'filename': filename,
            'prop_instance': prop_instance,
            'func_currency': func_currency,
            'func_currency_id': func_currency_id,
            'report_date': date,
            'current_period': current_period,
            'current_period_id': current_period_id,
        }
        return data

asset_register_commons()
