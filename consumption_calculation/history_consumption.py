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
from lxml import etree
from tools.translate import _

import time


class product_history_consumption(osv.osv_memory):
    _name = 'product.history.consumption'

    _columns = {
        'date_from': fields.date(string='From date', required=True),
        'date_to': fields.date(string='To date', required=True),
        'month_ids': fields.one2many('product.history.consumption.month', 'history_id', string='Months'),
        'consumption_type': fields.selection([('rac', 'Real Average Consumption'), ('amc', 'Average Monthly Consumption')],
                                             string='Consumption type', required=True),
        'location_id': fields.many2one('stock.location', string='Location', domain="[('usage', '=', 'internal')]"),
        'sublist_id': fields.many2one('product.list', string='List/Sublist'),
        'nomen_id': fields.many2one('product.nomenclature', string='Products\' nomenclature level'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root'),
    }

    _defaults = {
        'date_to': lambda *a: (DateFrom(time.strftime('%Y-%m-%d')) + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d'),
    }

    def open_history_consumption(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        new_id = self.create(cr, uid, {}, context=context)
        return {'type': 'ir.actions.act_window',
                'res_model': 'product.history.consumption',
                'res_id': new_id,
                'context': {'active_id': new_id, 'active_ids': [new_id], 'withnum': 1},
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'dummy'}

    def date_change(self, cr, uid, ids, date_from, date_to, context=None):
        '''
        Add the list of months in the defined period
        '''
        if not context:
            context = {}
        res = {'value': {}}
        month_obj = self.pool.get('product.history.consumption.month')
        
        if date_from:
            date_from = (DateFrom(date_from) + RelativeDateTime(day=1)).strftime('%Y-%m-%d')
            res['value'].update({'date_from': date_from})
        if date_to:
            date_to = (DateFrom(date_to) + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d')
            res['value'].update({'date_to': date_to})

        # If a period is defined
        if date_from and date_to:
            res['value'].update({'month_ids': []})
            current_date = DateFrom(date_from) + RelativeDateTime(day=1)
            # For all months in the period
            while current_date <= (DateFrom(date_to) + RelativeDateTime(months=1, day=1, days=-1)):
                search_ids = month_obj.search(cr, uid, [('name', '=', current_date.strftime('%m/%Y')), ('history_id', 'in', ids)], context=context)
                # If the month is in the period and not in the list, create it
                if not search_ids:
                    month_id = month_obj.create(cr, uid, {'name': current_date.strftime('%m/%Y'),
                                                          'date_from': current_date.strftime('%Y-%m-%d'),
                                                          'date_to': (current_date + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d'),
                                                          'history_id': ids[0]}, context=context)
                    res['value']['month_ids'].append(month_id)
                else:
                    res['value']['month_ids'].extend(search_ids)
                current_date = current_date + RelativeDateTime(months=1)
        else:
            res['value'] = {'month_ids': [False]}

        # Delete all months out of the period
        del_months = []
        for month_id in month_obj.search(cr, uid, [('history_id', 'in', ids)], context=context):
            if month_id not in res['value']['month_ids']:
                del_months.append(month_id)
        if del_months:
            month_obj.unlink(cr, uid, del_months, context=context)

        return res


    def create_lines(self, cr, uid, ids, context=None):
        '''
        Create one line by product for the period
        '''
        if not context:
            context = {}

        obj = self.browse(cr, uid, ids[0], context=context)
        products = []
        product_ids = []

        # Update the locations in context
        if obj.consumption_type == 'rac':
            location_ids = []
            if obj.location_id:
                location_ids = self.pool.get('stock.location').search(cr, uid, [('location_id', 'child_of', obj.location_id.id), ('usage', '=', 'internal')], context=context)
            context.update({'location_id': location_ids})

        months = self.pool.get('product.history.consumption.month').search(cr, uid, [('history_id', '=', obj.id)], order='date_from asc', context=context)
        nb_months = len(months)
        total_consumption = {}

        if obj.nomen_manda_0:
            for report in self.browse(cr, uid, ids, context=context):
                product_ids = []
                products = []
    
                nom = False
                # Get all products for the defined nomenclature
                if report.nomen_manda_3:
                    nom = report.nomen_manda_3.id
                    field = 'nomen_manda_3'
                elif report.nomen_manda_2:
                    nom = report.nomen_manda_2.id
                    field = 'nomen_manda_2'
                elif report.nomen_manda_1:
                    nom = report.nomen_manda_1.id
                    field = 'nomen_manda_1'
                elif report.nomen_manda_0:
                    nom = report.nomen_manda_0.id
                    field = 'nomen_manda_0'
                if nom:
                    product_ids.extend(self.pool.get('product.product').search(cr, uid, [(field, '=', nom)], context=context))
                    
            for product in self.pool.get('product.product').browse(cr, uid, product_ids, context=context):
                # Check if the product is not already on the report
                if product.id not in products:
                    batch_mandatory = product.batch_management or product.perishable
                    date_mandatory = not product.batch_management and product.perishable
                    self.pool.get('product.product').write(cr, uid, ids, {'name': product.id,})

        if obj.sublist_id:
            context.update({'search_default_list_ids': obj.sublist_id.id})
            for line in obj.sublist_id.product_ids:
                product_ids.append(line.name.id)

        domain = [('id', 'in', product_ids)]

        if not obj.nomen_manda_0 and not obj.sublist_id:
            domain = []

        new_context = context.copy()
        new_context.update({'months': [], 'amc': obj.consumption_type == 'amc' and 'AMC' or 'RAC', 'obj_id': obj.id, 'history_cons': True})

        # For each month, compute the RAC
        for month in self.pool.get('product.history.consumption.month').browse(cr, uid, months, context=context):
            new_context['months'].append({'date_from': month.date_from, 'date_to': month.date_to})


        return {'type': 'ir.actions.act_window',
                'res_model': 'product.product',
                'domain': domain,
                'view_type': 'form',
                'view_mode': 'tree,form',
                'context': new_context,
                'target': 'dummy'}

##############################################################################################################################
# The code below aims to enable filtering products regarding their nomenclature.
# NB: the difference with the other same kind of product filters (with nomenclature and sublist) is that here we are dealing with osv_memory
##############################################################################################################################
    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        res = self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, 0, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False, context={'withnum': 1})
        return res

    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field, context={'withnum': 1})

    def write(self, cr, uid, ids, vals, context=None):
        if vals.get('sublist_id',False):
            vals.update({'nomen_manda_0':False,'nomen_manda_1':False,'nomen_manda_2':False,'nomen_manda_3':False})
        if vals.get('nomen_manda_0',False):
            vals.update({'sublist_id':False})
        if vals.get('nomen_manda_1',False):
            vals.update({'sublist_id':False})
        ret = super(product_history_consumption, self).write(cr, uid, ids, vals, context=context)
        return ret
##############################################################################
# END of the definition of the product filters and nomenclatures
##############################################################################

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


class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'

    def export_data(self, cr, uid, ids, fields_to_export, context=None):
        '''
        Override the export_data function to add fictive fields
        '''
        if not context:
            context = {}

        history_fields = []
        new_fields_to_export = []
        history_fields_sort = {}
        sort_iter = 0

        # Add fictive fields
        if context.get('history_cons', False):
            months = context.get('months', [])
            
            if context.get('amc', False) and 'average' in fields_to_export:
                history_fields.append('average')

            for month in months:
                field_name = DateFrom(month.get('date_from')).strftime('%m-%Y')
                if field_name in fields_to_export:
                    history_fields.append(field_name)

        # Prepare normal fields to export to avoid error on export data with fictive fields
        for f in fields_to_export:
            if f not in history_fields:
                new_fields_to_export.append(f)
            else:
                # We save the order of the fictive fields to read them in the good order
                history_fields_sort.update({sort_iter: f})
                sort_iter += 1

        res = super(product_product, self).export_data(cr, uid, ids, new_fields_to_export, context=dict(context, history_cons=False))

        # Set the fictive fields in the good order
        if context.get('history_cons', False):
            for r in res['datas']:
                product_id = self.search(cr, uid, [('default_code', '=', r[0])], context=context)
                datas = {}
                if product_id:
                    datas = self.read(cr, uid, product_id, history_fields + ['default_code', 'id'], context=context)[0]
                for i, f in history_fields_sort.iteritems():
                    r.append(str(datas.get(f, 0.00)))
        
        return res

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if not context:
           context = {}
        
        ctx = context.copy()
        if 'location' in context and type(context.get('location')) == type([]):
            ctx.update({'location': context.get('location')[0]})
        res = super(product_product, self).fields_view_get(cr, uid, view_id, view_type, context=ctx, toolbar=toolbar, submenu=submenu)

        if context.get('history_cons', False) and view_type == 'tree':
            line_view = """<tree string="Historical consumption">
                   <field name="default_code"/>
                   <field name="name" />"""

            if context.get('amc', False):
                line_view += """<field name="average" />"""

            months = context.get('months', [])
            tmp_months = []
            for month in months:
                tmp_months.append(DateFrom(month.get('date_from')).strftime('%Y-%m'))

            tmp_months.sort()

            for month in tmp_months:
                line_view += """<field name="%s" />""" % DateFrom(month).strftime('%m-%Y')

            line_view += "</tree>"

            if res['type'] == 'tree':
                res['arch'] = line_view
        elif context.get('history_cons', False) and view_type == 'search':
            # Hard method !!!!!!
            # Remove the Group by group from the product view
            xml_view = etree.fromstring(res['arch'])
            for element in xml_view.iter("group"):
                if element.get('string', '') == 'Group by...':
                    xml_view.remove(element)
            res['arch'] = etree.tostring(xml_view)

        return res

    def fields_get(self, cr, uid, fields=None, context=None):
        if not context:
            context = {}

        res = super(product_product, self).fields_get(cr, uid, fields, context=context)
        
        if context.get('history_cons', False):
            months = context.get('months', [])

            for month in months:
                res.update({DateFrom(month.get('date_from')).strftime('%m-%Y'): {'digits': (16,2),
                                                                                 'selectable': True,
                                                                                 'type': 'float',
                                                                                 'sortable': False,
                                                                                 'string': '%s' % DateFrom(month.get('date_from')).strftime('%m/%Y')}})

            if context.get('amc', False):
                res.update({'average': {'digits': (16,2),
                                        'selectable': True,
                                        'type': 'float',
                                        'sortable': False,
                                        'string': 'Av. %s' %context.get('amc')}})

        return res

    def read(self, cr, uid, ids, vals=None, context=None, load='_classic_read'):
        '''
        Set value for each month
        '''
        cons_prod_obj = self.pool.get('product.history.consumption.product')

        if context is None:
            context = {}
        if context.get('history_cons', False):
            res = super(product_product, self).read(cr, uid, ids, vals, context=context, load=load)

            if 'average' not in vals:
                return res

            if not context.get('amc'):
                raise osv.except_osv(_('Error'), _('No Consumption type has been choosen !'))

            if not context.get('obj_id'):
                raise osv.except_osv(_('Error'), _('No history consumption report found !'))

            if not context.get('months') or len(context.get('months')) == 0:
                raise osv.except_osv(_('Error'), _('No months found !'))

            obj_id = context.get('obj_id')

            for r in res:
                total_consumption = 0.00
                for month in context.get('months'):
                    field_name = DateFrom(month.get('date_from')).strftime('%m-%Y')
                    cons_context = {'from_date': month.get('date_from'), 'to_date': month.get('date_to'), 'location_id': context.get('location_id')}
                    consumption = 0.00
                    cons_prod_domain = [('name', '=', field_name),
                                        ('product_id', '=', r['id']),
                                        ('consumption_id', '=', obj_id)]
                    if context.get('amc') == 'AMC':
                        cons_prod_domain.append(('cons_type', '=', 'amc'))
                        cons_id = cons_prod_obj.search(cr, uid, cons_prod_domain, context=context)
                        if cons_id:
                            consumption = cons_prod_obj.browse(cr, uid, cons_id[0], context=context).value
                        else:
                            consumption = self.pool.get('product.product').compute_amc(cr, uid, r['id'], context=cons_context)
                            cons_prod_obj.create(cr, uid, {'name': field_name,
                                                           'product_id': r['id'],
                                                           'consumption_id': obj_id,
                                                           'cons_type': 'amc',
                                                           'value': consumption}, context=context)
                    else:
                        cons_prod_domain.append(('cons_type', '=', 'fmc'))
                        cons_id = cons_prod_obj.search(cr, uid, cons_prod_domain, context=context)
                        if cons_id:
                            consumption = cons_prod_obj.browse(cr, uid, cons_id[0], context=context).value
                        else:
                            consumption = self.pool.get('product.product').browse(cr, uid, r['id'], context=cons_context).monthly_consumption
                            cons_prod_obj.create(cr, uid, {'name': field_name,
                                                           'product_id': r['id'],
                                                           'consumption_id': obj_id,
                                                           'cons_type': 'fmc',
                                                           'value': consumption}, context=context)
                    total_consumption += consumption
                    # Update the value for the month
                    r.update({field_name: consumption})

                # Update the average field
                r.update({'average': round(total_consumption/float(len(context.get('months'))),2)})
        else:
            res = super(product_product, self).read(cr, uid, ids, vals, context=context, load=load)

        return res

product_product()


class product_history_consumption_product(osv.osv_memory):
    _name = 'product.history.consumption.product'

    _columns = {
        'consumption_id': fields.many2one('product.history.consumption', string='Consumption id'),
        'product_id': fields.many2one('product.product', string='Product'),
        'name': fields.char(size=64, string='Name'),
        'value': fields.char(size=64, string='Value'),
        'cons_type': fields.selection([('amc', 'AMC'), ('fmc', 'FMC')], string='Consumption type'),
    }

product_history_consumption_product()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
