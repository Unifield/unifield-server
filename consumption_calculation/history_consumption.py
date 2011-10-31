# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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
from mx.DateTime import *

import time


class product_history_consumption(osv.osv_memory):
    _name = 'product.history.consumption'

    _columns = {
        'date_from': fields.date(string='From date', required=True),
        'date_to': fields.date(string='To date', required=True),
        'month_ids': fields.one2many('product.history.consumption.month', 'history_id', string='Months'),
        'consumption_type': fields.selection([('rac', 'Real Average Consumption'), ('amc', 'Average Monthly Consumption')],
                                             string='Consumption type', required=True),
        'location_id': fields.many2one('stock.location', string='Location'),
        'sublist_id': fields.many2one('product.list', string='List/Sublist'),
        'nomen_id': fields.many2one('product.nomenclature', string='Products\' nomenclature level'),
    }

    _defaults = {
        'date_to': lambda *a: time.strftime('%Y-%m-%d'),
    }

    def open_history_consumption(self, cr, uid, ids, context={}):
        if not context:
            context = {}
        new_id = self.create(cr, uid, {}, context=context)
        return {'type': 'ir.actions.act_window',
                'res_model': 'product.history.consumption',
                'res_id': new_id,
                'context': context,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'dummy'}

    def date_change(self, cr, uid, ids, date_from, date_to, context={}):
        '''
        Add the list of months in the defined period
        '''
        if not context:
            context = {}
        res = {}
        month_obj = self.pool.get('product.history.consumption.month')

        # If a period is defined
        if date_from and date_to:
            res['value'] = {'month_ids': []}
            current_date = DateFrom(date_from) + RelativeDateTime(day=1)
            # For all months in the period
            while current_date <= (DateFrom(date_to) + RelativeDateTime(months=1, day=1, days=-1)):
                search_ids = month_obj.search(cr, uid, [('name', '=', current_date.strftime('%m/%Y')), ('history_id', 'in', ids)], context=context)
                # If the month is in the period and not in the list, create it
                if not search_ids:
                    month_id = month_obj.create(cr, uid, {'name': current_date.strftime('%m/%Y'),
                                                          'date_from': current_date.strftime('%Y-%m-%d'),
                                                          'date_to': (current_date + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d'),
                                                          'history_id': ids[0]})
                    res['value']['month_ids'].append(month_id)
                else:
                    res['value']['month_ids'].extend(search_ids)
                current_date = current_date + RelativeDateTime(months=1)

        # Delete all months out of the period
        del_months = []
        for month_id in month_obj.search(cr, uid, [('history_id', 'in', ids)], context=context):
            if month_id not in res['value']['month_ids']:
                del_months.append(month_id)
        if del_months:
            month_obj.unlink(cr, uid, del_months, context=context)

        return res


    def create_lines(self, cr, uid, ids, context={}):
        '''
        Create one line by product for the period
        '''
        if not context:
            context = {}

        obj = self.browse(cr, uid, ids[0], context=context)
        new_context = context.copy()
        new_context.update({'months': [], 'amc': obj.consumption_type == 'amc', 'obj_id': obj.id})
        products = []
        product_ids = []
        if obj.consumption_type == 'rac':
            context.update({'location_id': obj.location_id and obj.location_id.id or False})
        months = self.pool.get('product.history.consumption.month').search(cr, uid, [('history_id', '=', obj.id)], order='name', context=context)
        nb_months = len(months)
        total_consumption = {}

        if not obj.nomen_id and not obj.sublist_id:
            product_ids = self.pool.get('product.product').search(cr, uid, [], context=context)

        if obj.nomen_id:
            nomen_id = obj.nomen_id.id
            nomen = self.pool.get('product.nomenclature').browse(cr, uid, nomen_id, context=context)
            if nomen.type == 'mandatory':
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [('nomen_manda_0', '=', nomen_id)], context=context))
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [('nomen_manda_1', '=', nomen_id)], context=context))
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [('nomen_manda_2', '=', nomen_id)], context=context))
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [('nomen_manda_3', '=', nomen_id)], context=context))
            else:
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [('nomen_sub_0', '=', nomen_id)], context=context))
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [('nomen_sub_1', '=', nomen_id)], context=context))
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [('nomen_sub_2', '=', nomen_id)], context=context))
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [('nomen_sub_3', '=', nomen_id)], context=context))
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [('nomen_sub_4', '=', nomen_id)], context=context))
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [('nomen_sub_5', '=', nomen_id)], context=context))
        if obj.sublist_id:
            for line in obj.sublist_id.product_ids:
                product_ids.append(line.name.id)

        # For each month, compute the RAC
        for month in self.pool.get('product.history.consumption.month').browse(cr, uid, months, context=context):
            new_context['months'].append(month.name)
            month_context = context.copy()
            month_context.update({'from_date': month.date_from, 'to_date': month.date_to})
            if obj.consumption_type == 'rac':
                month_context.update({'location': obj.location_id and obj.location_id.id or False})
            # For each product, compute the data for all months
            for product in self.pool.get('product.product').browse(cr, uid, product_ids, context=month_context):
                if product.id not in products:
                    self.pool.get('product.history.consumption.line').create(cr, uid, {'unique_id': obj.id, 
                                                                                       'product_id': product.id,
                                                                                       'fmc_value': product.reviewed_consumption}, context=context)
                    products.append(product.id)

                if product.id not in total_consumption:
                    total_consumption.update({product.id: 0.00})

                if obj.consumption_type == 'rac':
                    monthly_consumption = product.monthly_consumption
                elif obj.consumption_type == 'amc':
                    monthly_consumption = self.pool.get('product.product').compute_amc(cr, uid, product.id, context=month_context)
                else:
                    monthly_consumption = 0.00

                total_consumption[product.id] =  total_consumption[product.id] + monthly_consumption
                # Create a value for this month and this product
                self.pool.get('product.history.consumption.data').create(cr, uid, {'product_id': product.id,
                                                                                   'name': month.name,
                                                                                   'unique_id': obj.id,
                                                                                   'value': monthly_consumption}, context=context)

        if obj.consumption_type == 'amc':
            for product in self.pool.get('product.product').browse(cr, uid, products, context=month_context):
                self.pool.get('product.history.consumption.data').create(cr, uid, {'product_id': product.id,
                                                                                   'name': 'average',
                                                                                   'unique_id': obj.id,
                                                                                   'value': float(total_consumption[product.id])/float(nb_months)})


        return {'type': 'ir.actions.act_window',
                'res_model': 'product.history.consumption.line',
                'domain': [('unique_id', '=', obj.id)],
                'view_type': 'form',
                'view_mode': 'tree',
                'context': new_context,
                'target': 'dummy'}

product_history_consumption()


class product_history_consumption_month(osv.osv_memory):
    _name = 'product.history.consumption.month'
    _order = 'name, date_from, date_to'

    _columns = {
        'name': fields.char(size=64, string='Month'),
        'date_from': fields.date(string='Date from'),
        'date_to': fields.date(string='Date to'),
        'history_id': fields.many2one('product.history.consumption', string='History'),
    }

product_history_consumption_month()


class product_history_consumption_line(osv.osv_memory):
    _name = 'product.history.consumption.line'

    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'fmc_value': fields.float(string='FMC'),
        'unique_id': fields.integer(string='Unique ID', required=True),
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context={}, toolbar=False, submenu=False):
        if not context:
           context={}

        res = super(product_history_consumption_line, self).fields_view_get(cr, uid, view_id, view_type, context=context)

        line_view = """<tree string="Historical consumption">
               <field name="product_id"/>
               <field name="fmc_value"/>"""

        months = context.get('months', [])

        for month in months:
            line_view += """<field name="%s" />""" % month

        if context.get('amc', False):
            line_view += """<field name="average" />"""

        line_view += "</tree>"

        if res['type'] == 'tree':
            res['arch'] = line_view

        return res

    def fields_get(self, cr, uid, fields=None, context={}):
        if not context:
            context = {}

        res = super(product_history_consumption_line, self).fields_get(cr, uid, fields, context)
        months = context.get('months', [])

        for month in months:
            res.update({month: {'digits': (16,2),
                               'selectable': True,
                               'type': 'float',
                               'string': '%s' % month}})

        if context.get('amc', False):
            res.update({'average': {'digits': (16,2),
                                    'selectable': True,
                                    'type': 'float',
                                    'string': 'Average'}})

        return res

    def read(self, cr, uid, ids, vals, context={}, load='_classic_read'):
        '''
        Set value for each month
        '''
        data_obj = self.pool.get('product.history.consumption.data')
        vals.append('unique_id')
        res = super(product_history_consumption_line, self).read(cr, uid, ids, vals, context=context, load=load)
        
        obj_id = context.get('obj_id', False)

        for r in res:
            if not obj_id and 'unique_id' in r:
                obj_id = r['unique_id']

            data_ids = data_obj.search(cr, uid, [('product_id', '=', r['product_id']), ('unique_id', '=', obj_id)], context=context)
            for data in data_obj.browse(cr, uid, data_ids, context=context):
                r.update({data.name: data.value})

        return res

product_history_consumption_line()


class product_history_consumption_data(osv.osv_memory):
    _name = 'product.history.consumption.data'

    _columns = {
        'name': fields.char(size=64, string='Name', required=True),
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'value': fields.float(digits=(16,2), string='Value', required=True),
        'unique_id': fields.integer(string='Unique ID', required=True),
    }

product_history_consumption_data()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
