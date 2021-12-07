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
from mx.DateTime import DateFrom, RelativeDateTime, now
from lxml import etree
from tools.translate import _
from tools.misc import to_xml, get_traceback
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta

import time

HIST_STATUS = [('draft', 'Draft'), ('in_progress', 'In Progress'), ('ready', 'Ready'), ('error', 'Error')]

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

    def _get_txt_loc(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for x in self.browse(cr, uid, ids, fields_to_fetch=['consumption_type', 'location_id', 'location_dest_id', 'src_location_ids', 'dest_location_ids'], context=context):
            if x.consumption_type == 'rac':
                res[x.id] = {'txt_source': x.location_id.name, 'txt_destination': x.location_dest_id.name}
            elif x.consumption_type == 'rr-amc':
                res[x.id] = {'txt_source': ', '.join([loc.name for loc in x.src_location_ids or []]), 'txt_destination': ', '.join([loc.name for loc in x.dest_location_ids or []]), 'disable_adjusted_rr_amc': bool(x.dest_location_ids)}
            else:
                res[x.id] = {'txt_source': False, 'txt_destination': False}
        return res
    _columns = {
        'hidden_date_from': fields.date(string='Used to set a default month on date from'),
        'date_from': fields.date(string='From date'),
        'date_to': fields.date(string='To date'),
        'month_ids': fields.one2many('product.history.consumption.month', 'history_id', string='Months'),
        'consumption_type': fields.selection([('rac', 'Real Average Consumption'), ('amc', 'Average Monthly Consumption'), ('rr-amc', 'RR-AMC')],
                                             string='Consumption type'),
        'remove_negative_amc': fields.boolean('Remove Negative AMCs'),
        'adjusted_rr_amc': fields.boolean('Adjusted RR-AMC'),
        'location_id': fields.many2one('stock.location', string='Source Location', domain="[('usage', '=', 'internal')]"),
        'location_dest_id': fields.many2one('stock.location', string='Destination Location', domain="[('usage', '=', 'customer')]"),
        'src_location_ids': fields.many2many('stock.location', 'src_location_hist_consumption_rel',  'histo_id', 'location_id', 'Source', domain="[('usage', '=', 'internal'), ('from_histo', '=', dest_location_ids), '|', ('location_category', '!=', 'transition'), ('cross_docking_location_ok', '=', True)]"),
        'dest_location_ids': fields.many2many('stock.location', 'dest_location_hist_consumption_rel',  'histo_id', 'location_id', 'Destination', domain="[('usage', 'in', ['internal', 'customer']), ('from_histo', '=', src_location_ids), ('location_category', '!=', 'transition')]", context={'dest_location': True}),
        'txt_source': fields.function(_get_txt_loc, type='char', method=1, string='Source', multi='get_txt'),
        'txt_destination': fields.function(_get_txt_loc, type='char', method=1, string='Destination', multi='get_txt'),
        'disable_adjusted_rr_amc': fields.function(_get_txt_loc, type='boolean', method=1, string='Disable adjusted_rr_amc', multi='get_txt'),
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
        'error_msg': fields.text('Error'),
    }

    _defaults = {
        'hidden_date_from': lambda *a: (now() + RelativeDateTime(months=-1, day=1)).strftime('%Y-%m-%d'),
        'date_to': lambda *a: (now() + RelativeDateTime(day=1, days=-1)).strftime('%Y-%m-%d'),
        'requestor_id': lambda obj, cr, uid, c: uid,
        'requestor_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'status': 'draft',
        'adjusted_rr_amc': False,
    }

    def copy_data(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}

        new_default = super(product_history_consumption, self).copy_data(cr, uid, id, default, context=context)
        for remove in ['requestor_id', 'requestor_date', 'status']:
            if remove not in default and remove in new_default:
                del(new_default[remove])

        return new_default

    def reset_to_draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'status': 'draft', 'error_msg': False}, context=context)
        return True

    def change_dest_location_ids(self, cr, uid, ids, dest, context=None):
        if not dest or not isinstance(dest, list) or not dest[0] or not isinstance(dest[0], tuple) or len(dest[0]) != 3 or not dest[0][2]:
            return {'value': {'disable_adjusted_rr_amc': False}}
        return {'value': {'disable_adjusted_rr_amc': True, 'adjusted_rr_amc': False}}

    def clean_remove_negative_amc(self, cr, uid, vals, context=None):
        if vals:
            if vals.get('consumption_type') == 'rac':
                vals['remove_negative_amc'] = False
            if 'consumption_type' in vals and vals.get('consumption_type') != 'rr-amc':
                vals['adjusted_rr_amc'] = False
            elif 'dest_location_ids' in vals and vals['dest_location_ids'] != [(6, 0, [])]:
                vals['adjusted_rr_amc'] = False

    def create(self, cr, uid, vals, context=None):
        self.clean_remove_negative_amc(cr, uid, vals, context)
        return super(product_history_consumption, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True

        if vals.get('status') == 'draft' and vals.get('consumption_type'):
            # click on the report button in draft mode, must lock the fields
            if self.search_exists(cr, uid, [('id', 'in', ids), ('status', 'not in', ['draft', 'error'])], context=context):
                return True

        self.clean_remove_negative_amc(cr, uid, vals, context)

        if vals.get('sublist_id',False):
            vals.update({'nomen_manda_0':False,'nomen_manda_1':False,'nomen_manda_2':False,'nomen_manda_3':False})
        if vals.get('nomen_manda_0',False):
            vals.update({'sublist_id':False})
        if vals.get('nomen_manda_1',False):
            vals.update({'sublist_id':False})
        return super(product_history_consumption, self).write(cr, uid, ids, vals, context=context)

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
                    if ids:
                        new_month = month_obj.create(cr, uid, {
                            'history_id': ids[0],
                            'name': current_date.strftime('%m/%Y'),
                            'date_from': current_date.strftime('%Y-%m-%d'),
                            'date_to': (current_date + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d')
                        }, context=context)
                        res['value']['month_ids'].append(new_month)
                    else:
                        # new record not saved
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

    def get_months(self, cr, uid, ids, context=None):
        months = self.pool.get('product.history.consumption.month').search(cr, uid, [('history_id', '=', ids[0])], order='date_from asc', context=context)
        if not months:
            raise osv.except_osv(_('Error'), _('You have to choose at least one month for consumption history'))

        list_months = []
        # For each month, compute the RAC
        for month in self.pool.get('product.history.consumption.month').browse(cr, uid, months, context=context):
            list_months.append({'date_from': month.date_from, 'date_to': month.date_to})

        return list_months

    def get_data(self, cr, uid, ids, context=None):
        '''
        Get parameters of the report
        '''
        if not context:
            context = {}

        obj = self.browse(cr, uid, ids[0],
                          fields_to_fetch=['consumption_type',
                                           'location_id',
                                           'location_dest_id',
                                           'id',
                                           'remove_negative_amc',
                                           'nomen_manda_0',
                                           'sublist_id'],
                          context=context)

        domain = []
        # Update the locations in context
        if obj.consumption_type == 'rac':
            location_ids = []
            if obj.location_id:
                location_ids = self.pool.get('stock.location').search(cr, uid, [('location_id', 'child_of', obj.location_id.id), ('usage', '=', 'internal')], context=context)
            context.update({'location_id': location_ids})
            if obj.location_dest_id:
                context.update({'location_dest_id': obj.location_dest_id.id})

        if obj.nomen_manda_0:
            for report in self.browse(cr, uid, ids, context=context):
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
                    domain.append((field, '=', nom))

        if obj.sublist_id:
            domain.append(('in_product_list', '=', obj.sublist_id.id))

        new_context = context.copy()
        ctx_type = {
            'amc': 'AMC',
            'rr-amc': 'RR-AMC',
        }
        new_context.update({'amc': ctx_type.get(obj.consumption_type, 'RAC'), 'obj_id': obj.id, 'history_cons': True, 'need_thread': True})
        if obj.consumption_type in ('amc', 'rr-amc') and obj.remove_negative_amc:
            new_context['remove_negative_amc'] = True

        return domain, new_context

    def return_waiting_screen(self, cr, uid, ids, context=None):
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'history_consumption_waiting_view')[1]
        return {'type': 'ir.actions.act_window',
                'res_model': 'product.history.consumption',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'view_id': [view_id],
                'context': context,
                'target': 'same'
                }

    def generate_lines(self, cr, uid, ids, context=None):
        if self.search_exists(cr, uid, [('id', 'in', ids), ('status', '=', 'ready')], context=context):
            return True
        if self.search_exists(cr, uid, [('id', 'in', ids), ('status', '=', 'in_progress')], context=context):
            return False

        domain, new_context = self.get_data(cr, uid, ids, context=context)
        import threading
        self.write(cr, uid, ids, {'status': 'in_progress'}, context=context)
        cr.commit()
        new_thread = threading.Thread(target=self._create_lines, args=(cr.dbname, uid, ids, domain, new_context))
        new_thread.start()
        new_thread.join(10.0)
        if new_thread.isAlive():
            return False
        return True

    def create_lines(self, cr, uid, ids, context=None):
        '''
        Create one line by product for the period
        '''
        if not context:
            context = {}

        ready = self.generate_lines(cr, uid, ids, context=context)
        if ready:
            return self.open_report(cr, uid, ids, context=context)
        return self.return_waiting_screen(cr, uid, ids, context=context)


    def _create_lines(self, dbname, uid, ids, domain, context=None):
        '''
        Create lines in background
        '''
        import pooler
        cr = pooler.get_db(dbname).cursor()

        try:
            prod_obj = self.pool.get('product.product')
            cons_prod_obj = self.pool.get('product.history.consumption.product')

            res = self.browse(cr, uid, ids[0], context=context)
            if res.consumption_type == 'rac':
                if res.location_dest_id:
                    cr.execute('''
                    SELECT distinct(r.product_id)
                    FROM real_average_consumption_line r, stock_move m
                    WHERE r.move_id = m.id and m.location_dest_id = %s
                    ''', (res.location_dest_id.id,))
                else:
                    cr.execute('''
                    SELECT distinct(product_id)
                    FROM real_average_consumption_line
                    WHERE move_id IS NOT NULL
                    ''')
            elif res.consumption_type == 'amc' or (not res.src_location_ids and not res.dest_location_ids):
                cr.execute('''
                  SELECT distinct(s.product_id)
                  FROM stock_move s
                    LEFT JOIN stock_location l ON l.id = s.location_id OR l.id = s.location_dest_id
                  WHERE l.usage in ('customer', 'internal')
                ''')
            else:
                context['histo_src_location_ids'] = [x.id for x in res.src_location_ids]
                context['histo_dest_location_ids'] = [x.id for x in res.dest_location_ids]
                if not context['histo_dest_location_ids'] and res.adjusted_rr_amc:
                    context['adjusted_rr_amc'] = True

                cr.execute('''
                    SELECT distinct(s.product_id)
                    FROM stock_move s
                    WHERE
                        location_id in %s or location_dest_id in %s
                ''', (tuple(context['histo_src_location_ids'] or [0]), tuple(context['histo_dest_location_ids'] or [0])))

            product_ids = [x[0] for x in cr.fetchall()]

            if res.consumption_type == 'rr-amc' and res.adjusted_rr_amc and res.src_location_ids:
                cr.execute('''
                    select distinct(line.product_id)
                    from product_stock_out_line line, product_stock_out st
                     where
                            line.stock_out_id = st.id and
                            st.state = 'closed' and
                            st.adjusted_amc = 't' and
                            st.location_id in %(location)s and
                            (from_date, to_date) OVERLAPS (%(from)s, %(to)s) and
                            coalesce(line.qty_missed, 0) > 0
                    ''', {'location': tuple([x.id for x in res.src_location_ids]), 'from': res.date_from, 'to': res.date_to})
                product_ids += [x[0] for x in cr.fetchall()]

            if domain:
                product_ids = prod_obj.search(cr, uid, domain + [('id', 'in', product_ids)], context=context)

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

            all_months = self.get_months(cr, uid, [res.id], context=context)
            context['from_date'] = res.date_from
            context['to_date'] = res.date_to
            for slice_ids in slices:
                if res.consumption_type in ('amc', 'rr-amc'):
                    avg, month_amc = self.pool.get('product.product').compute_amc(cr, uid, slice_ids, context=context, compute_amc_by_month=True, remove_negative_amc=res.remove_negative_amc, rounding=False)
                    for product in slice_ids:
                        cons_prod_obj.create(cr, uid, {
                            'name': 'average',
                            'product_id': product,
                            'consumption_id': res.id,
                            'cons_type': res.consumption_type,
                            'value': avg.get(product, 0)}, context=context)

                        for month in all_months:
                            month_dt = datetime.strptime(month.get('date_from'), '%Y-%m-%d')
                            cons_prod_obj.create(cr, uid, {
                                'name': month_dt.strftime('%m_%Y'),
                                'product_id': product,
                                'consumption_id': res.id,
                                'cons_type': res.consumption_type,
                                'value': month_amc.get(product, {}).get(month_dt.strftime('%Y-%m'), 0)}, context=context)
                else:
                    total_by_prod = {}
                    cons_context = {
                        'location_id': res.location_id.id,
                        'location_dest_id': res.location_dest_id.id,
                    }
                    nb_months = 0
                    for month in all_months:
                        cons_context['from_date'] = month.get('date_from')
                        cons_context['to_date'] = month.get('date_to')

                        dt_to_date = min(datetime.now(), datetime.strptime(month.get('date_to'), '%Y-%m-%d'))
                        nb_of_days = (dt_to_date + relativedelta(months=1, day=1, days=-1)).day
                        if dt_to_date.day == nb_of_days:
                            nb_months += 1
                        else:
                            nb_months += dt_to_date.day/float(nb_of_days)

                        month_dt = datetime.strptime(month.get('date_from'), '%Y-%m-%d').strftime('%m_%Y')

                        for product in self.pool.get('product.product').browse(cr, uid, slice_ids, fields_to_fetch=['monthly_consumption'], context=cons_context):
                            total_by_prod.setdefault(product.id, 0)
                            total_by_prod[product.id] += product.monthly_consumption or 0
                            cons_prod_obj.create(cr, uid, {
                                'name': month_dt,
                                'product_id': product.id,
                                'consumption_id': res.id,
                                'cons_type': 'fmc',
                                'value': product.monthly_consumption or 0}, context=context)
                    for product in slice_ids:
                        cons_prod_obj.create(cr, uid, {
                            'name': 'average',
                            'product_id': product,
                            'consumption_id': res.id,
                            'cons_type': 'fmc',
                            'value': round(total_by_prod.get(product,0)/float(nb_months), 2)}, context=context)



            self.write(cr, uid, ids, {'status': 'ready'}, context=context)

        except Exception as e:
            logging.getLogger('history.consumption').warn('Exception in read average', exc_info=True)
            cr.rollback()
            self.write(cr, uid, ids, {'status': 'error', 'error_msg':  get_traceback(e)}, context=context)

        cr.commit()
        cr.close(True)

        return

    def open_report(self, cr, uid, ids, context=None):
        '''
        Open the report
        '''
        if context is None:
            context = {}

        domain, new_context = self.get_data(cr, uid, ids, context=context)
        if new_context is None:
            new_context = {}
        new_context['search_default_average'] = 1  # UTP-501 positive Av.AMC/Av.RAC filter set to on by default
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'product_history_consumption_tree_view')[1]

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'domain': domain,
            'view_type': 'form',
            'view_mode': 'tree,form',
            'context': new_context,
            'target': 'dummy',
            'view_id': [view_id],
        }

    def report_amc_no_negative(self, cr, uid, ids, context=None):
        return self.report_amc_with_negative(cr, uid, ids, context=context)

    def report_amc_with_negative(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        ready = self.generate_lines(cr, uid, ids, context=context)
        if ready:
            return {
                'type': 'ir.actions.report.xml',
                'report_name': 'report_historical_consumption_xlsx',
                'context': context,
            }
        return self.return_waiting_screen(cr, uid, ids, context=context)

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
            months = self.pool.get('product.history.consumption').get_months(cr, uid, [context['obj_id']], context=context)
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
            line_view = """<tree string="%s" hide_new_button="1">
                   <field name="default_code"/>
                   <field name="name" />""" % (to_xml(_('Historical consumption')),)

            if context.get('amc', False):
                line_view += """<field name="average" />"""

            months = self.pool.get('product.history.consumption').get_months(cr, uid, [context['obj_id']], context=context)
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
            histo = self.pool.get('product.history.consumption').browse(cr, uid, context['obj_id'], context=context)
            # Remove the Group by group from the product view
            xml_view = etree.fromstring(res['arch'])
            for element in xml_view.iter("group"):
                if element.get('name', '') == 'group_by':
                    xml_view.remove(element)

            # UTP-501 Positive AMC filter
            new_separator = """<separator orientation="vertical" />"""
            separator_node = etree.fromstring(new_separator)
            xml_view.insert(0, separator_node)
            new_filter = """<filter string="%s%s &gt; 0" name="average" icon="terp-accessories-archiver-minus" domain="[('average', '>', 0)]" />""" % (_('Av.'), _(context.get('amc', 'AMC')))

            # generate new xml form
            filter_node = etree.fromstring(new_filter)
            xml_view.insert(0, filter_node)

            # display filters on tree view
            filter_info = []
            if histo.adjusted_rr_amc:
                filter_info.append(_('Adjusted'))
            filter_info.append({'amc': _('AMC'), 'rr-amc': _('RR-AMC'), 'rac': _('RAC')}.get(histo.consumption_type, ''))
            if histo.remove_negative_amc:
                filter_info.append(_('(Negative figures set to zero)'))

            list_infos = ['%s: %s' % (_('Type'), ' '.join(filter_info))]
            if histo.txt_source:
                list_infos.append('%s: %s' % (_('Source'), histo.txt_source))
            if histo.txt_destination:
                list_infos.append('%s: %s' % (_('Destination'), histo.txt_destination))
            if histo.sublist_id:
                list_infos.append('%s: %s' % (_('List'), histo.sublist_id.name))
            nomen_list = []
            for title, nomen in [(_('Main'), histo.nomen_manda_0), (_('Group'), histo.nomen_manda_1), (_('Family'), histo.nomen_manda_2), (_('Root'), histo.nomen_manda_3)]:
                if nomen:
                    nomen_list.append('%s: %s' % (title, nomen.name))
            if nomen_list:
                list_infos.append(', '.join(nomen_list))
            html_node = "<group> <html>"
            for list_info in list_infos:
                html_node += '<h3>%s</h3>' % to_xml(list_info)

            html_node += "</html></group>"
            if html_node:
                xml_view.append(etree.fromstring(html_node))


            res['arch'] = etree.tostring(xml_view)
        return res

    def fields_get(self, cr, uid, fields=None, context=None, with_uom_rounding=False):
        if not context:
            context = {}

        res = super(product_product, self).fields_get(cr, uid, fields, context=context)

        if context.get('history_cons', False):
            months = self.pool.get('product.history.consumption').get_months(cr, uid, [context['obj_id']], context=context)
            histo_data = self.pool.get('product.history.consumption').read(cr, uid, context['obj_id'], ['adjusted_rr_amc'], context)
            for month in months:
                res.update({DateFrom(month.get('date_from')).strftime('%m_%Y'): {'digits': (16,2),
                                                                                 'selectable': True,
                                                                                 'type': 'float',
                                                                                 'string': '%s' % DateFrom(month.get('date_from')).strftime('%m/%Y')}})

            if context.get('amc', False):
                label = _('Av.')
                if histo_data['adjusted_rr_amc']:
                    label = _('Adj Av.')
                res.update({'average': {'digits': (16,2),
                                        'selectable': True,
                                        'type': 'float',
                                        'string': '%s %s' % (label, _(context.get('amc','AMC')))}
                            })

        return res

    def read(self, cr, uid, ids, vals=None, context=None, load='_classic_read'):
        '''
        Set value for each month
        '''
        cons_prod_obj = self.pool.get('product.history.consumption.product')

        if context is None:
            context = {}

        res = super(product_product, self).read(cr, uid, ids, vals, context=context, load=load)

        if not context.get('history_cons', False):
            return res

        if 'average' not in vals:
            return res

        if not context.get('amc'):
            raise osv.except_osv(_('Error'), _('No Consumption type has been choosen !'))

        if not context.get('obj_id'):
            raise osv.except_osv(_('Error'), _('No history consumption report found !'))

        obj_id = context.get('obj_id')

        prod_data = dict((x['id'], x) for x in res)

        cons_prod_domain = [
            ('product_id', 'in', ids),
            ('consumption_id', '=', obj_id)
        ]

        if context.get('amc') == 'AMC':
            cons_prod_domain.append(('cons_type', '=', 'amc'))
        elif context.get('amc') == 'RR-AMC':
            cons_prod_domain.append(('cons_type', '=', 'rr-amc'))
        else:
            cons_prod_domain.append(('cons_type', '=', 'fmc'))

        cons_ids = cons_prod_obj.search(cr, uid, cons_prod_domain, order='NO_ORDER', context=context)
        for cons_data in cons_prod_obj.browse(cr, uid, cons_ids, fields_to_fetch=['name', 'value','product_id'], context=context):
            prod_data[cons_data.product_id.id][cons_data.name] = cons_data.value

        ret = []
        for r in res:
            ret.append(prod_data[r['id']])
        return ret

product_product()


class product_history_consumption_product(osv.osv):
    _name = 'product.history.consumption.product'

    _columns = {
        'consumption_id': fields.many2one('product.history.consumption', string='Consumption id', select=1, ondelete='cascade'),
        'product_id': fields.many2one('product.product', string='Product', select=1),
        'name': fields.char(size=64, string='Name', select=1),
        'value': fields.float(digits=(16,2), string='Value'),
        'cons_type': fields.selection([('amc', 'AMC'), ('fmc', 'FMC'), ('rr-amc', 'RR-AMC')], string='Consumption type', select=1),
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
