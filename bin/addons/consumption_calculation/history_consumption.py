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
from mx.DateTime import DateFrom, RelativeDateTime
from lxml import etree
from tools.translate import _
import logging

import time

HIST_STATUS = [('draft', 'Draft'), ('in_progress', 'In Progress'), ('ready', 'Ready')]

class product_history_consumption(osv.osv):
    _name = 'product.history.consumption'
    _rec_name = 'location_id'
    _order = 'id desc'

    def _get_status(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the same status as status
        '''
        res = {}

        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = obj.status

        return res

    _columns = {
        'date_from': fields.date(string='From date'),
        'date_to': fields.date(string='To date'),
        'month_ids': fields.one2many('product.history.consumption.month', 'history_id', string='Months'),
        'consumption_type': fields.selection([('rac', 'Real Average Consumption'), ('amc', 'Average Monthly Consumption')],
                                             string='Consumption type'),
        'location_id': fields.many2one('stock.location', string='Location', domain="[('usage', '=', 'internal')]"),
        'sublist_id': fields.many2one('product.list', string='List/Sublist', ondelete='set null'),
        'nomen_id': fields.many2one('product.nomenclature', string='Products\' nomenclature level', ondelete='set null'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type', ondelete='set null'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group', ondelete='set null'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family', ondelete='set null'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root', ondelete='set null'),
        'requestor_id': fields.many2one('res.users', string='Requestor'),
        'requestor_date': fields.datetime(string='Date of the demand'),
        'fake_status': fields.function(_get_status, method=True, type='selection', selection=HIST_STATUS, readonly=True, string='Status'),
        'status': fields.selection(HIST_STATUS, string='Status'),
    }

    _defaults = {
        'date_to': lambda *a: (DateFrom(time.strftime('%Y-%m-%d')) + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d'),
        'requestor_id': lambda obj, cr, uid, c: uid,
        'requestor_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'status': 'draft',
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
            if current_date > (DateFrom(date_to) + RelativeDateTime(months=1, day=1, days=-1)):
                return {'warning': {'title': _('Error'),
                                    'message':  _('The \'To Date\' should be greater than \'From Date\'')}}
            # For all months in the period
            while current_date <= (DateFrom(date_to) + RelativeDateTime(months=1, day=1, days=-1)):
                search_ids = month_obj.search(cr, uid, [('name', '=', current_date.strftime('%m/%Y')), ('history_id', 'in', ids)], context=context)
                # If the month is in the period and not in the list, create it
                if not search_ids:
                    #                    month_id = month_obj.create(cr, uid, {'name': current_date.strftime('%m/%Y'),
                    #                                                          'date_from': current_date.strftime('%Y-%m-%d'),
                    #                                                          'date_to': (current_date + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d'),
                    #                                                          'history_id': ids[0]}, context=context)
                    #                    res['value']['month_ids'].append(month_id)
                    res['value']['month_ids'].append({'name': current_date.strftime('%m/%Y'),
                                                      'date_from': current_date.strftime('%Y-%m-%d'),
                                                      'date_to': (current_date + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d')})
                else:
                    res['value']['month_ids'].extend(search_ids)
                current_date = current_date + RelativeDateTime(months=1)
        else:
            res['value'] = {'month_ids': []}

        # Delete all months out of the period
        del_months = []
        for month_id in month_obj.search(cr, uid, [('history_id', 'in', ids)], context=context):
            if month_id not in res['value']['month_ids']:
                del_months.append(month_id)
        if del_months:
            month_obj.unlink(cr, uid, del_months, context=context)

        return res


    def get_data(self, cr, uid, ids, context=None):
        '''
        Get parameters of the report
        '''
        if not context:
            context = {}

        obj = self.browse(cr, uid, ids[0],
                          fields_to_fetch=['consumption_type',
                                           'location_id',
                                           'id',
                                           'nomen_manda_0',
                                           'sublist_id'],
                          context=context)
        product_ids = []

        # Update the locations in context
        if obj.consumption_type == 'rac':
            location_ids = []
            if obj.location_id:
                location_ids = self.pool.get('stock.location').search(cr, uid, [('location_id', 'child_of', obj.location_id.id), ('usage', '=', 'internal')], context=context)
            context.update({'location_id': location_ids})

        months = self.pool.get('product.history.consumption.month').search(cr, uid, [('history_id', '=', obj.id)], order='date_from asc', context=context)

        if not months:
            raise osv.except_osv(_('Error'), _('You have to choose at least one month for consumption history'))

        if obj.nomen_manda_0:
            for report in self.browse(cr, uid, ids, context=context):
                product_ids = []
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

        if obj.sublist_id:
            context.update({'search_default_list_ids': obj.sublist_id.id})
            for line in obj.sublist_id.product_ids:
                product_ids.append(line.name.id)

        domain = [('id', 'in', product_ids)]

        if not obj.nomen_manda_0 and not obj.sublist_id:
            domain = []

        new_context = context.copy()
        new_context.update({'months': [], 'amc': obj.consumption_type == 'amc' and 'AMC' or 'RAC', 'obj_id': obj.id, 'history_cons': True, 'need_thread': True})

        # For each month, compute the RAC
        for month in self.pool.get('product.history.consumption.month').browse(cr, uid, months, context=context):
            new_context['months'].append({'date_from': month.date_from, 'date_to': month.date_to})


        return product_ids, domain, new_context

    def create_lines(self, cr, uid, ids, context=None):
        '''
        Create one line by product for the period
        '''
        if not context:
            context = {}

        product_ids, domain, new_context = self.get_data(cr, uid, ids, context=context)

        if not product_ids:
            product_ids = self.pool.get('product.product').search(cr, uid, [], context=new_context)

        import threading
        self.write(cr, uid, ids, {'status': 'in_progress'}, context=context)
        cr.commit()
        new_thread = threading.Thread(target=self._create_lines, args=(cr, uid, ids, product_ids, new_context))
        new_thread.start()
        new_thread.join(10.0)
        if new_thread.isAlive():
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'history_consumption_waiting_view')[1]
            return {'type': 'ir.actions.act_window',
                    'res_model': 'product.history.consumption',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_id': ids[0],
                    'view_id': [view_id],
                    'context': new_context,
                    'target': 'same'}

        return self.open_report(cr, uid, ids, context=new_context)

    def _create_lines(self, cr, uid, ids, product_ids, context=None):
        '''
        Create lines in background
        '''
        import pooler
        new_cr = pooler.get_db(cr.dbname).cursor()

        res = self.browse(cr, uid, ids[0], context=context)
        if res.consumption_type == 'rac':
            cr.execute('''
            SELECT distinct(product_id)
            FROM real_average_consumption_line
            WHERE move_id IS NOT NULL
            ''')
        else:
            cr.execute('''
              SELECT distinct(s.product_id)
              FROM stock_move s
                LEFT JOIN stock_location l ON l.id = s.location_id OR l.id = s.location_dest_id
              WHERE l.usage in ('customer', 'internal')
            ''')
        product_ids = [x[0] for x in cr.fetchall()]

        # split ids into slices to not read a lot record in the same time (memory)
        ids_len = len(product_ids)
        slice_len = 500
        if ids_len > slice_len:
            slice_count = ids_len / slice_len
            if ids_len % slice_len:
                slice_count = slice_count + 1
            # http://www.garyrobinson.net/2008/04/splitting-a-pyt.html
            slices = [product_ids[i::slice_count] for i in range(slice_count)]
        else:
            slices = [product_ids]

        for slice_ids in slices:
            try:
                self.pool.get('product.product').read(new_cr, uid, slice_ids, ['average'], context=context)
            except Exception:
                logging.getLogger('history.consumption').warn('Exception in read average', exc_info=True)
                new_cr.rollback()

        self.write(new_cr, uid, ids, {'status': 'ready'}, context=context)

        new_cr.commit()
        new_cr.close(True)

        return

    def open_report(self, cr, uid, ids, context=None):
        '''
        Open the report
        '''
        if context is None:
            context = {}

        product_ids, domain, new_context = self.get_data(cr, uid, ids, context=context)
        if new_context is None:
            new_context = {}
        new_context['search_default_average'] = 1  # UTP-501 positive Av.AMC/Av.RAC filter set to on by default

        return {'type': 'ir.actions.act_window',
                'res_model': 'product.product',
                'domain': domain,
                'view_type': 'form',
                'view_mode': 'tree,form',
                'context': new_context,
                'target': 'dummy'}

    def unlink(self, cr, uid, ids, context=None):
        '''
        Remove the data saved in DB
        '''
        hist_obj = self.pool.get('product.history.consumption.product')
        for cons in self.browse(cr, uid, ids, context=context):
            hist_ids = hist_obj.search(cr, uid, [('consumption_id', '=', cons.id)], context=context)
            hist_obj.unlink(cr, uid, hist_ids, context=context)
        return super(product_history_consumption, self).unlink(cr, uid, ids, context=context)

    def in_progress(self, cr, uid, ids, context=None):
        '''
        Return dummy
        '''
        return self.go_to_list(cr, uid, ids, context=context)

    def go_to_list(self, cr, uid, ids, context=None):
        '''
        Returns to the list of reports
        '''
        return {'type': 'ir.actions.act_window',
                'res_model': 'product.history.consumption',
                'view_mode': 'tree,form',
                'view_type': 'form',
                'target': 'dummy',
                'context': context}

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
        if not ids:
            return True
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

class product_history_consumption_month(osv.osv):
    _name = 'product.history.consumption.month'
    _order = 'name, date_from, date_to'

    _columns = {
        'name': fields.char(size=64, string='Month'),
        'date_from': fields.date(string='Date from'),
        'date_to': fields.date(string='Date to'),
        'history_id': fields.many2one('product.history.consumption', string='History', ondelete='cascade'),
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
        fields_sort = {}
        sort_iter2 = 0
        default_code_index = False
        remove_default_code = False
        history_cons_in_context = context.get('history_cons', False)

        # Add fictive fields
        if history_cons_in_context:
            months = context.get('months', [])
            del context['history_cons']
            if context.get('amc', False) and 'average' in fields_to_export:
                history_fields.append('average')

            if 'default_code' not in fields_to_export:
                fields_to_export.append('default_code')
                remove_default_code = True

            for month in months:
                field_name = DateFrom(month.get('date_from')).strftime('%m_%Y')
                if field_name in fields_to_export:
                    history_fields.append(field_name)

            # Prepare normal fields to export to avoid error on export data with fictive fields
            to_export_iter = 0
            for f in fields_to_export:
                if f not in history_fields:
                    new_fields_to_export.append(f)
                    if f == 'default_code':
                        default_code_index = to_export_iter
                    to_export_iter += 1

                # We save the order of the fields to read them in the good order
                fields_sort.update({sort_iter2: f})
                sort_iter2 += 1
        else:
            new_fields_to_export = fields_to_export

        res = super(product_product, self).export_data(cr, uid, ids, new_fields_to_export, context=context)

        # Set the fields in the good order
        if history_cons_in_context:
            context['history_cons'] = True
            new_data = []
            for r in res['datas']:
                new_r = []
                product_id = self.search(cr, uid, [('default_code', '=', r[default_code_index])], context=context)
                datas = {}
                if product_id:
                    datas = self.read(cr, uid, product_id, history_fields + ['default_code', 'id'], context=context)[0]

                iter_r = 0
                for j in range(sort_iter2):
                    f = fields_sort[j]

                    if f == 'default_code' and remove_default_code:
                        continue

                    if f in history_fields:
                        new_r.append(str(datas.get(f, 0.00)))
                    else:
                        new_r.append(r[iter_r])
                        iter_r += 1
                new_data.append(new_r)

            res['datas'] = new_data

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
                line_view += """<field name="%s" />""" % DateFrom(month).strftime('%m_%Y')

            line_view += "</tree>"

            if res['type'] == 'tree':
                res['arch'] = line_view
        elif context.get('history_cons', False) and view_type == 'search':
            # Hard method !!!!!!
            # Remove the Group by group from the product view
            xml_view = etree.fromstring(res['arch'])
            for element in xml_view.iter("group"):
                if element.get('string', '') == 'Group by...':
                    xml_view.remove(element)
            res['arch'] = etree.tostring(xml_view)

            # UTP-501 Positive AMC filter
            xml_view = etree.fromstring(res['arch'])
            new_separator = """<separator orientation="vertical" />"""
            separator_node = etree.fromstring(new_separator)
            xml_view.insert(0, separator_node)
            product_ids = self.pool.get('product.history.consumption').get_data(cr, uid, [context.get('obj_id')], context=context)[0]
            product_ids = self.pool.get('product.product').search(cr, uid, [('id', 'in', product_ids), ('average', '>', 0)], context=context)
            new_filter = """<filter string="Av.%s &gt; 0" name="average" icon="terp-accessories-archiver-minus" domain="[('id', 'in', %s)]" />""" % (context.get('amc', 'AMC'), product_ids)
            # generate new xml form$
            filter_node = etree.fromstring(new_filter)
            xml_view.insert(0, filter_node)
            res['arch'] = etree.tostring(xml_view)

        return res

    def fields_get(self, cr, uid, fields=None, context=None):
        if not context:
            context = {}

        res = super(product_product, self).fields_get(cr, uid, fields, context=context)

        if context.get('history_cons', False):
            months = context.get('months', [])

            for month in months:
                res.update({DateFrom(month.get('date_from')).strftime('%m_%Y'): {'digits': (16,2),
                                                                                 'selectable': True,
                                                                                 'type': 'float',
                                                                                 'string': '%s' % DateFrom(month.get('date_from')).strftime('%m/%Y')}})

            if context.get('amc', False):
                res.update({'average': {'digits': (16,2),
                                        'selectable': True,
                                        'type': 'float',
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
                    field_name = DateFrom(month.get('date_from')).strftime('%m_%Y')
                    cons_context = {'from_date': month.get('date_from'), 'to_date': month.get('date_to'), 'location_id': context.get('location_id')}
                    consumption = 0.00
                    cons_prod_domain = [('name', '=', field_name),
                                        ('product_id', '=', r['id']),
                                        ('consumption_id', '=', obj_id)]
                    if context.get('amc') == 'AMC':
                        cons_prod_domain.append(('cons_type', '=', 'amc'))
                        cons_id = cons_prod_obj.search(cr, uid, cons_prod_domain, order='NO_ORDER', limit=1, context=context)
                        if cons_id:
                            consumption = cons_prod_obj.browse(cr, uid, cons_id[0], context=context).value
                        else:
                            consumption = self.pool.get('product.product').compute_amc(cr, uid, r['id'], context=cons_context) or 0.00
                            cons_prod_obj.create(cr, uid, {'name': field_name,
                                                           'product_id': r['id'],
                                                           'consumption_id': obj_id,
                                                           'cons_type': 'amc',
                                                           'value': consumption}, context=context)
                    else:
                        cons_prod_domain.append(('cons_type', '=', 'fmc'))
                        cons_id = cons_prod_obj.search(cr, uid, cons_prod_domain, order='NO_ORDER', limit=1, context=context)
                        if cons_id:
                            consumption = cons_prod_obj.browse(cr, uid, cons_id[0], context=context).value
                        else:
                            consumption = self.pool.get('product.product').browse(cr, uid, r['id'], context=cons_context).monthly_consumption or 0.00
                            cons_prod_obj.create(cr, uid, {'name': field_name,
                                                           'product_id': r['id'],
                                                           'consumption_id': obj_id,
                                                           'cons_type': 'fmc',
                                                           'value': consumption}, context=context)
                    total_consumption += consumption
                    # Update the value for the month
                    r.update({field_name: consumption})

                # Update the average field
                cons_prod_domain = [('name', '=', 'average'),
                                    ('product_id', '=', r['id']),
                                    ('consumption_id', '=', obj_id),
                                    ('cons_type', '=', context.get('amc') == 'AMC' and 'amc' or 'fmc')]
                r.update({'average': round(total_consumption/float(len(context.get('months'))),2)})
                cons_id = cons_prod_obj.search(cr, uid, cons_prod_domain, order='NO_ORDER', limit=1, context=context)
                if cons_id:
                    cons_prod_obj.write(cr, uid, cons_id, {'value': r['average']}, context=context)
                else:
                    cons_prod_obj.create(cr, uid, {'name': 'average',
                                                   'product_id': r['id'],
                                                   'consumption_id': obj_id,
                                                   'cons_type': context.get('amc') == 'AMC' and 'amc' or 'fmc',
                                                   'value': r['average']}, context=context)
        else:
            res = super(product_product, self).read(cr, uid, ids, vals, context=context, load=load)

        return res

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        '''
        Update the search method to sort by fictive fields if needed
        '''
        if not context:
            context = {}

        average_domain = False
        if context.get('history_cons', False):
            """UTP-501 'average' filter (filter button generated in fields_view_get)
            if found, grab it, and remove it
            (bc 'average' field is unknown in super(product_product, self))
            """
            new_args = []
            for a in args:
                if len(a) == 3 and a[0] == 'average':
                    average_domain = a
                else:
                    new_args.append(a)
            args = new_args

        hist_obj = self.pool.get('product.history.consumption.product')

        res = super(product_product, self).search(cr, uid, args, offset, limit,
                                                  order, context, count)

        if context.get('history_cons', False) and context.get('obj_id', False):
            if order and order != 'NO_ORDER' or average_domain:
                hist_domain = [('consumption_id', '=', context.get('obj_id'))]
                if context.get('amc') == 'AMC':
                    hist_domain.append(('cons_type', '=', 'amc'))
                else:
                    hist_domain.append(('cons_type', '=', 'fmc'))

            if average_domain:
                # UTP-501 'average' filter
                hist_domain += [
                    ('name', '=', 'average'),
                    ('value', average_domain[1], average_domain[2])
                ]

            if order and order != 'NO_ORDER':
                # sorting with or without average_domain
                for order_part in order.split(','):
                    order_split = order_part.strip().split(' ')
                    order_field = order_split[0]
                    order_direction = order_split[1].strip() if len(order_split) == 2 else ''
                    if order_field != 'id' and order_field not in self._columns and order_field not in self._inherit_fields:
                        hist_domain.append(('name', '=', order_field))
                        hist_ids = hist_obj.search(cr, uid, hist_domain, offset=offset, limit=limit, order='value %s' % order_direction, context=context)
                        res = list(x['product_id'][0] for x in hist_obj.read(cr, uid, hist_ids, ['product_id'], context=context))
                        break
            elif average_domain:
                # UTP-501 'average' filter without sorting
                hist_ids = hist_obj.search(cr, uid, hist_domain, offset=offset,
                                           limit=limit, order=order,
                                           context=context)
                res = [x['product_id'][0] for x in hist_obj.read(cr, uid, hist_ids, ['product_id'], context=context)]

        return res

product_product()


class product_history_consumption_product(osv.osv):
    _name = 'product.history.consumption.product'

    _columns = {
        'consumption_id': fields.many2one('product.history.consumption', string='Consumption id', select=1, ondelete='cascade'),
        'product_id': fields.many2one('product.product', string='Product', select=1),
        'name': fields.char(size=64, string='Name', select=1),
        'value': fields.float(digits=(16,2), string='Value'),
        'cons_type': fields.selection([('amc', 'AMC'), ('fmc', 'FMC')], string='Consumption type', select=1),
    }

    def read(self, cr, uid, ids, fields, context=None, load='_classic_read'):
        '''
        Return the result in the same order as given in ids
        '''
        res = super(product_history_consumption_product, self).read(cr, uid, ids, fields, context=context, load=load)

        res_final = [None]*len(ids)
        for r in res:
            r_index = ids.index(r['id'])
            res_final[r_index] = r

        return res_final

product_history_consumption_product()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
