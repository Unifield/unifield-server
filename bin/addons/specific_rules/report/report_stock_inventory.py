# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
import threading
import datetime

from osv import osv
from osv import fields
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _
from service.web_services import report_spool

from datetime import datetime
from dateutil.relativedelta import relativedelta


IN_LAST_X_MONTHS = tuple([("%s" % i, _("%s months") % str(i)) for i in range(1, 13)])


class export_report_stock_inventory(osv.osv):
    _name = 'export.report.stock.inventory'
    _order = 'id desc'

    _columns = {
        'company_id': fields.many2one(
            'res.company',
            string='DB/Instance name',
            readonly=True,
        ),
        'name': fields.datetime(
            string='Report Generation date',
            readonly=True,
        ),
        'stock_level_date': fields.date(
            string='Stock Level date',
        ),
        'product_id': fields.many2one(
            'product.product',
            string='Specific product',
            help="""If a product is choosen, only quantities of this product
will be shown.""",
        ),
        'prodlot_id': fields.many2one(
            'stock.production.lot',
            string='Specific Batch number',
        ),
        'product_list_id': fields.many2one(
            'product.list',
            string='Specific Product list',
        ),
        'expiry_date': fields.date(
            string='Specific expiry date',
        ),
        'location_id': fields.many2one(
            'stock.location',
            string='Specific location',
            help="""If a location is choosen, only product quantities in this
location will be shown.""",
            required=False,
        ),
        'state': fields.selection(
            selection=[
                ('draft', 'Draft'),
                ('in_progress', 'In Progress'),
                ('ready', 'Ready'),
            ],
            string='State',
            readonly=True,
        ),
        'display_0': fields.boolean(
            string='Include products with stock <= 0 with movements in the last months'
        ),
        'in_last_x_months': fields.selection(
            IN_LAST_X_MONTHS,
            'In the last',
        ),
    }

    _defaults = {
        'state': lambda *a: 'draft',
        'company_id': lambda s,cr,uid,c: s.pool.get('res.company').\
        _company_default_get(
            cr, uid, 'export.report.stock.inventory', context=c),
    }

    def onchange_sl_date(self, cr, uid, ids, sl_date=False):
        if sl_date and sl_date > str(datetime.now().date()):
            return {'value': {'stock_level_date': False}}
        else:
            return {'value': {'stock_level_date': sl_date}}

    def update(self, cr, uid, ids, context=None):
        return {}

    def generate_report_all_locations(self, cr, uid, ids, context=None):
        """
        Launch the generation of a report with the inventory of each products on each locations
        @param cr: Cursor to the database
        @param uid: ID of the res.users that calls this method
        @param ids: List of ID of export wizard
        @param context: Context of the call
        @return: An action to the view with a waiting message
        """
        return self.generate_report(cr, uid, ids, context=context, all_locations=True)

    def generate_report(self, cr, uid, ids, context=None, all_locations=False):
        """
        Select the good lines on the report.stock.inventory table
        """
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        for report in self.browse(cr, uid, ids, context=context):
            self.write(cr, uid, [report.id], {
                'name': time.strftime('%Y-%m-%d %H:%M:%S'),
                'state': 'in_progress',
            })

            cr.commit()
            new_thread = threading.Thread(
                target=self.generate_report_bkg,
                args=(cr, uid, report.id, context, all_locations)
            )
            new_thread.start()
            new_thread.join(30.0)

            res = {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_id': report.id,
                'context': context,
                'target': 'same',
            }
            if new_thread.isAlive():
                view_id = data_obj.get_object_reference(
                    cr, uid,
                    'specific_rules',
                    'export_report_stock_inventory_info_view')[1]
                res['view_id'] = [view_id]

            return res

        raise osv.except_osv(
            _('Error'),
            _('No inventory lines found for these parameters'),
        )

    def generate_report_bkg(self, cr, uid, ids, context=None, all_locations=False):
        """
        Generate the report in background
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        import pooler
        new_cr = pooler.get_db(cr.dbname).cursor()

        report_name = 'stock.inventory.xls'
        attachment_name = 'stock_inventory_location_view_%s.xls'
        if all_locations:
            report_name = 'stock.inventory.all.locations.xls'
            attachment_name = 'stock_inventory_global_view_%s.xls'

        rp_spool = report_spool()
        result = rp_spool.\
            exp_report(
                cr.dbname, uid,
                report_name, ids, {'report_id': ids[0]}, context)

        file_res = {'state': False}
        while not file_res.get('state'):
            file_res = rp_spool.exp_report_get(new_cr.dbname, uid, result)
            time.sleep(0.5)
        attachment = self.pool.get('ir.attachment')
        attachment.create(new_cr, uid, {
            'name': attachment_name % (
                time.strftime('%Y_%m_%d_%H_%M')),
            'datas_fname': attachment_name % (
                time.strftime('%Y_%m_%d_%H_%M')),
            'description': 'Stock inventory',
            'res_model': 'export.report.stock.inventory',
            'res_id': ids[0],
            'datas': file_res.get('result'),
        })
        self.write(new_cr, uid, ids, {'state': 'ready'}, context=context)

        new_cr.commit()
        new_cr.close(True)

        return True

    def onchange_prodlot(self, cr, uid, ids, prodlot_id):
        """
        Change the product when change the prodlot
        """
        if not prodlot_id:
            return {
                'value': {
                    'product_id': False,
                    'expiry_date': False,
                },
            }

        prodlot = self.pool.get('stock.production.lot').\
            browse(cr, uid, prodlot_id)
        return {
            'value': {
                'product_id': prodlot.product_id.id,
                'expiry_date': prodlot.life_date,
            },
        }

    def create(self, cr, uid, vals, context=None):
        """
        Call onchange_prodlot if a lot is defined
        """
        if vals.get('prodlot_id'):
            vals.update(
                self.onchange_prodlot(
                    cr, uid, False, vals.get('prodlot_id')
                ).get('value', {})
            )

        return super(export_report_stock_inventory, self).\
            create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Call onchange_prodlot if a lot is defined
        """
        if not ids:
            return True
        if vals.get('prodlot_id'):
            vals.update(
                self.onchange_prodlot(
                    cr, uid, ids, vals.get('prodlot_id')
                ).get('value', {})
            )

        return super(export_report_stock_inventory, self).\
            write(cr, uid, ids, vals, context=context)

export_report_stock_inventory()


class parser_report_stock_inventory_xls(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(parser_report_stock_inventory_xls, self).\
            __init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getLines': self.getLines,
            'getLocations': self.getLocations,
        })

    def getLocations(self):
        loc_obj = self.pool.get('stock.location')
        location_ids = loc_obj.search(
            self.cr,
            self.uid,
            [('usage', '=', 'internal')],
            context=self.localcontext
        )
        return loc_obj.browse(self.cr, self.uid, location_ids, context=self.localcontext)

    def getLines(self):
        res = {}
        report_id = self.datas.get('report_id')

        report = self.pool.get('export.report.stock.inventory').browse(self.cr, self.uid, report_id, context=self.localcontext)

        with_zero = False
        values = {'state': 'done'}
        cond = ['state=%(state)s']

        having = "having sum(product_qty) != 0"
        full_prod_list = []

        cond.append('location_id in %(location_ids)s')
        if report.location_id:
            values['location_ids'] = (report.location_id.id,)
        else:
            values['location_ids'] = tuple(self.pool.get('stock.location').search(self.cr, self.uid, [('usage', '=', 'internal')]))

        if report.product_id:
            cond.append('product_id in %(product_ids)s')
            values['product_ids'] = (report.product_id.id,)
            with_zero = True
        elif report.product_list_id:
            cond.append('product_id in %(product_ids)s')
            full_prod_list = self.pool.get('product.product').search(self.cr, self.uid, [('list_ids', '=', report.product_list_id.id)], context=self.localcontext)
            values['product_ids'] = tuple(full_prod_list)
            with_zero = True

        if report.prodlot_id:
            cond.append('prodlot_id=%(prodlot_id)s')
            values['prodlot_id'] = report.prodlot_id.id
            with_zero = True

        if report.expiry_date:
            cond.append('expired_date=%(expiry_date)s')
            values['expiry_date'] = report.expiry_date
            with_zero = True

        if report.stock_level_date:
            cond.append('date<%(stock_level_date)s')
            values['stock_level_date'] = '%s 23:59:59' % report.stock_level_date

        if (not report.product_id or not report.product_list_id or not report.prodlot_id or not report.expiry_date) \
                and report.display_0:
            with_zero = True
            to_date = datetime.now()
            if report.stock_level_date:
                to_date = datetime.strptime(values['stock_level_date'], '%Y-%m-%d %H:%M:%S')
            from_date = (to_date + relativedelta(months=-int(report.in_last_x_months))).strftime('%Y-%m-%d 00:00:00')

            self.cr.execute("""select distinct(product_id) from stock_move 
                where state='done' and (location_id in %s or location_dest_id in %s) and date >= %s and date <= %s""",
                            (values['location_ids'], values['location_ids'], from_date, to_date))
            for x in self.cr.fetchall():
                full_prod_list.append(x[0])

        if with_zero:
            having = ""

        self.cr.execute("""select sum(product_qty), product_id, expired_date, prodlot_id, location_id
            from report_stock_inventory
            where
                """+' and '.join(cond)+"""
            group by product_id, expired_date, uom_id, prodlot_id, location_id
            """ + having, values)

        all_product_ids = {}
        all_bn_ids = {}
        bn_data = {}
        product_data = {}
        # fetch data with db id: for uom, product, bn ...
        for line in self.cr.fetchall():
            all_product_ids[line[1]] = True
            all_bn_ids[line[3]] = True

            res.setdefault(line[1], {'sum_qty': 0, 'lines': {}})
            res[line[1]]['sum_qty'] += line[0]

            if line[3] not in res[line[1]]['lines']:
                res[line[1]]['lines'][line[3]] = {
                    'qty': 0,
                    'batch_id': line[3],
                    'expiry_date': line[2] or '',
                    'location_ids': {},
                }
            res[line[1]]['lines'][line[3]]['qty'] += line[0]
            res[line[1]]['lines'][line[3]]['location_ids'].setdefault(line[4], 0.00)
            res[line[1]]['lines'][line[3]]['location_ids'][line[4]] += line[0]

        # fetch bn and product data
        for bn in self.pool.get('stock.production.lot').read(self.cr, self.uid, all_bn_ids.keys(), ['name'], context=self.localcontext):
            bn_data[bn['id']] = bn['name']

        if full_prod_list:
            product_ids_to_fetch = list(set(list(values.get('product_ids', []))+all_product_ids.keys()+full_prod_list))
        else:
            product_ids_to_fetch = all_product_ids.keys()

        cost_price_at_date = {}
        if report.stock_level_date and product_ids_to_fetch:
            self.cr.execute("""select distinct on (product_id) product_id, new_standard_price
                from standard_price_track_changes
                where
                    product_id in %s and
                    create_date <= %s
                order by product_id, create_date desc""", (tuple(product_ids_to_fetch), values['stock_level_date']))

            for x in self.cr.fetchall():
                cost_price_at_date[x[0]] = x[1]

        for product in self.pool.get('product.product').browse(self.cr, self.uid, product_ids_to_fetch, fields_to_fetch=['default_code', 'uom_id', 'name', 'standard_price'], context=self.localcontext):
            product_data[product.id] = product
            if product.id not in res:
                res[product.id] = {
                    'sum_qty': 0,
                    'lines': {
                        '': {
                            'qty': 0,
                            'batch_id': False,
                            'expiry_date': '',
                            'location_ids': {}
                        }
                    }
                }

        # replace db id by name, code
        final_result = {}
        total_value = 0
        nb_items = 0
        for product_id in res:
            product_code = product_data[product_id].default_code
            cost_price = cost_price_at_date.get(product_id, product_data[product_id].standard_price)
            final_result[product_code] = {
                'sum_qty': res[product_id]['sum_qty'],
                'product_code': product_code,
                'product_name': product_data[product_id].name,
                'uom': product_data[product_id].uom_id.name,
                'sum_value':  cost_price * res[product_id]['sum_qty'],
                'with_product_list': with_zero,
                'lines': {},
            }
            total_value += final_result[product_code]['sum_value']
            if res[product_id]['sum_qty'] > 0:
                nb_items += 1
            for batch_id in res[product_id]['lines']:
                final_result[product_code]['lines'][batch_id] = {
                    'batch': bn_data.get(batch_id, ''),
                    'expiry_date': res[product_id]['lines'][batch_id]['expiry_date'],
                    'qty': res[product_id]['lines'][batch_id]['qty'],
                    'value': cost_price * res[product_id]['lines'][batch_id]['qty'],
                    'location_ids': res[product_id]['lines'][batch_id]['location_ids'],
                }

        fres = []
        for k in sorted(final_result.keys()):
            fres.append(final_result[k])

        return total_value, nb_items, fres


class report_stock_inventory_xls(SpreadsheetReport):

    def __init(self, name, table, rml=False, parser=report_sxw.rml_parse,
               header='external', store=False):
        super(report_stock_inventory_xls, self).__init__(
            name,
            table,
            rml=rml,
            parser=parser,
            header=header,
            store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(report_stock_inventory_xls, self).create(
            cr, uid, ids, data, context=context)
        return (a[0], 'xls')


report_stock_inventory_xls(
    'report.stock.inventory.xls',
    'export.report.stock.inventory',
    'addons/specific_rules/report/report_stock_inventory_xls.mako',
    parser=parser_report_stock_inventory_xls,
    header='internal',
)

report_stock_inventory_xls(
    'report.stock.inventory.all.locations.xls',
    'export.report.stock.inventory',
    'addons/specific_rules/report/report_stock_inventory_all_locations_xls.mako',
    parser=parser_report_stock_inventory_xls,
    header='internal',
)
