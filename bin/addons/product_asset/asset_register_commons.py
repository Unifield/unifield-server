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

    def get_asset_ad(self, asset):
        asset_ad = ''
        ads = []
        if asset.analytic_distribution_id and asset.analytic_distribution_id.funding_pool_lines:
            for fp_line in asset.analytic_distribution_id.funding_pool_lines:
                cc_code = fp_line.cost_center_id.code
                dest_code = fp_line.destination_id.code
                fp_code = fp_line.analytic_id.code
                percentage = str(fp_line.percentage)
                line_ad = '; '.join([cc_code, dest_code, fp_code, percentage])
                ads.append(line_ad)
            asset_ad = ' / '.join(ads)
        return asset_ad

    def format_asset_state(self, state, context=None):
        if context is None:
            context = {}
        states = {
            'draft': _('Draft'),
            'open': _('Open'),
            'running': _('Active'),
            'depreciated': _('Fully Depreciated'),
            'disposed': _('Disposed')}
        return states.get(state, '')

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
        date = datetime.now().strftime("%d-%m-%Y %H:%M")
        current_period_id = period_obj.find(cr, uid)[0]
        current_period = current_period_id and period_obj.browse(cr, uid, current_period_id, context=context).name or ''


        filename = '_'.join(('Fixed Assets Register', prop_instance, datetime.now().strftime("%Y%m%d")))

        row_headers = [
            (_('Asset code')),
            (_('Capitalization Entry sequence')),
            (_('Capitalization Period')),
            (_('Product code')),
            (_('Product Description')),
            (_('Serial Number')),
            (_('Instance creator')),
            (_('Instance of use')),
            (_('Analytic distribution')),
            (_('Asset type')),
            (_('Useful life')),
            (_('Booking Currency')),
            (_('Initial Value Booking Curr.')),
            (_('Accumulated Depr. Booking Curr.')),
            (_('Remaining net value Booking Currency')),
            (_('Remaining net value Func. Currency')),
            (_('Fixed Asset Status')),
            (_('External Asset ID')),
        ]

        asset_fields = ['name', 'move_line_id', 'prod_int_code', 'prod_int_name', 'serial_nb', 'instance_id',
                        'used_instance_id', 'analytic_distribution_id', 'asset_type_id', 'useful_life_id',
                        'invo_currency', 'invo_value', 'depreciation_amount', 'disposal_amount', 'state',
                        'external_asset_id']

        draft_asset_ids = asset_obj.search(cr, uid, [('state', '=', 'draft')], context=context)
        open_asset_ids = asset_obj.search(cr, uid, [('state', '=', 'open')], context=context)
        active_asset_ids = asset_obj.search(cr, uid, [('state', '=', 'running')], context=context)
        depreciated_asset_ids = asset_obj.search(cr, uid, [('state', '=', 'depreciated')], context=context)
        disposed_asset_ids = asset_obj.search(cr, uid, [('state', '=', 'disposed')], context=context)
        sorted_asset_ids = [*draft_asset_ids, *open_asset_ids, *active_asset_ids, *depreciated_asset_ids, *disposed_asset_ids]

        data = {
            'sorted_asset_ids': sorted_asset_ids or [],
            'model': 'product.asset',
            'context': context,
            'filename': filename,
            'prop_instance': prop_instance,
            'headers': row_headers,
            'asset_fields': asset_fields,
            'func_currency': func_currency,
            'func_currency_id': func_currency_id,
            'report_date': date,
            'current_period': current_period,
            'current_period_id': current_period_id,
        }
        return data

asset_register_commons()
