# -*- coding: utf-8 -*-
#
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
#

import tools
import time
import threading

from report import report_sxw
from osv import fields, osv
from decimal_precision import decimal_precision as dp
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _
from service.web_services import report_spool


class report_stock_move(osv.osv):
    _name = "report.stock.move"
    _rec_name = 'location_id'
    _description = "Moves Statistics"
    _auto = False

    def _get_order_information(self, cr, uid, ids, fields_name, arg, context=None):
        '''
        Returns information about the order linked to the stock move
        '''
        res = {}

        for report in self.browse(cr, uid, ids, context=context):
            move = report.move
            res[report.id] = {'order_priority': False,
                              'order_category': False,
                              'order_type': False}
            order = False

            if move.purchase_line_id and move.purchase_line_id.id:
                order = move.purchase_line_id.order_id
            elif move.sale_line_id and move.sale_line_id.id:
                order = move.sale_line_id.order_id

            if order:
                res[report.id] = {}
                if 'order_priority' in fields_name:
                    res[report.id]['order_priority'] = order.priority
                if 'order_category' in fields_name:
                    res[report.id]['order_category'] = order.categ
                if 'order_type' in fields_name:
                    res[report.id]['order_type'] = order.order_type

        return res

    _columns = {
        'date': fields.date('Date', readonly=True),
        'year': fields.char('Year', size=4, readonly=True),
        'day': fields.char('Day', size=128, readonly=True),
        'month': fields.selection([('01', 'January'), ('02', 'February'), ('03', 'March'), ('04', 'April'),
                                   ('05', 'May'), ('06', 'June'), ('07', 'July'), ('08', 'August'), ('09', 'September'),
                                   ('10', 'October'), ('11', 'November'), ('12', 'December')], 'Month', readonly=True),
        'partner_id': fields.many2one('res.partner', 'Partner', readonly=True),
        'product_id': fields.many2one('product.product', 'Product', readonly=True),
        'product_uom': fields.many2one('product.uom', 'UoM', readonly=True),
        'company_id': fields.many2one('res.company', 'Company', readonly=True),
        'picking_id': fields.many2one('stock.picking', 'Reference', readonly=True),
        'type': fields.selection([('out', 'Sending Goods'), ('in', 'Getting Goods'), ('internal', 'Internal'), ('other', 'Others')], 'Shipping Type', required=True, select=True, help="Shipping type specify, goods coming in or going out."),
        'location_id': fields.many2one('stock.location', 'Source Location', readonly=True, select=True, help="Sets a location if you produce at a fixed location. This can be a partner location if you subcontract the manufacturing operations."),
        'location_dest_id': fields.many2one('stock.location', 'Dest. Location', readonly=True, select=True, help="Location where the system will stock the finished products."),
        'state': fields.selection([('draft', 'Draft'), ('waiting', 'Waiting'), ('confirmed', 'Not Available'), ('assigned', 'Available'), ('done', 'Closed'), ('cancel', 'Cancelled')], 'State', readonly=True, select=True),
        'product_qty': fields.float('Quantity', readonly=True, related_uom='product_uom'),
        'categ_id': fields.many2one('product.nomenclature', 'Family', ),
        'product_qty_in': fields.float('In Qty', readonly=True, related_uom='product_uom'),
        'product_qty_out': fields.float('Out Qty', readonly=True, related_uom='product_uom'),
        'value': fields.float('Total Value', required=True),
        'day_diff2': fields.float('Lag (Days)', readonly=True, digits_compute=dp.get_precision('Shipping Delay'), group_operator="avg"),
        'day_diff1': fields.float('Planned Lead Time (Days)', readonly=True, digits_compute=dp.get_precision('Shipping Delay'), group_operator="avg"),
        'day_diff': fields.float('Execution Lead Time (Days)', readonly=True, digits_compute=dp.get_precision('Shipping Delay'), group_operator="avg"),
        'stock_journal': fields.many2one('stock.journal', 'Stock Journal', select=True),
        'order_type': fields.function(_get_order_information, method=True, string='Order Type', type='selection',
                                      selection=[('regular', 'Regular'), ('donation_exp', 'Donation before expiry'),
                                                 ('donation_st', 'Standard donation'), ('loan', 'Loan'),
                                                 ('in_kind', 'In Kind Donation'), ('purchase_list', 'Purchase List'),
                                                 ('direct', 'Direct Purchase Order')], multi='move_order'),
        'comment': fields.char(size=128, string='Comment'),
        'prodlot_id': fields.many2one('stock.production.lot', 'Batch', states={'done': [('readonly', True)]}, help="Batch number is used to put a serial number on the production", select=True),
        'tracking_id': fields.many2one('stock.tracking', 'Pack', select=True, states={'done': [('readonly', True)]}, help="Logistical shipping unit: pallet, box, pack ..."),
        'origin': fields.related('picking_id', 'origin', type='char', size=512, relation="stock.picking", string="Origin", store=True),
        'move': fields.many2one('stock.move', string='Move'),
        'reason_type_id': fields.many2one('stock.reason.type', string='Reason type'),
        'currency_id': fields.many2one('res.currency', string='Currency'),
        'product_code': fields.related('product_id', 'default_code', type='char', string='Product Code'),
        'product_name': fields.related('product_id', 'name', type='char', string='Product Name'),
        'expiry_date': fields.related('prodlot_id', 'life_date', type='date', string='Expiry Date'),
    }

    def init(self, cr):
        tools.drop_view_if_exists(cr, 'report_stock_move')
        cr.execute("""
            CREATE OR REPLACE view report_stock_move AS (
                SELECT
                        min(sm_id) as id,
                        date_trunc('day',al.dp) as date,
                        al.curr_year as year,
                        al.curr_month as month,
                        al.curr_day as day,
                        al.curr_day_diff as day_diff,
                        al.curr_day_diff1 as day_diff1,
                        al.curr_day_diff2 as day_diff2,
                        al.location_id as location_id,
                        al.picking_id as picking_id,
                        al.company_id as company_id,
                        al.location_dest_id as location_dest_id,
                        al.product_qty,
                        al.out_qty as product_qty_out,
                        al.in_qty as product_qty_in,
                        al.partner_id as partner_id,
                        al.product_id as product_id,
                        al.state as state ,
                        al.product_uom as product_uom,
                        al.categ_id as categ_id,
                        al.sm_id as move,
                        al.tracking_id as tracking_id,
                        al.comment as comment,
                        al.prodlot_id as prodlot_id,
                        al.origin as origin,
                        al.reason_type_id as reason_type_id,
                        coalesce(al.type, 'other') as type,
                        al.stock_journal as stock_journal,
                        sum(al.in_value - al.out_value) as value,
                        1 as currency_id
                    FROM (SELECT
                        CASE WHEN sp.type in ('out') THEN
                            sum((sm.product_qty / pu.factor) * u.factor)
                            ELSE 0.0
                            END AS out_qty,
                        CASE WHEN sp.type in ('in') THEN
                            sum((sm.product_qty / pu.factor) * u.factor)
                            ELSE 0.0
                            END AS in_qty,
                        CASE WHEN sp.type in ('out') THEN
                            sum((sm.product_qty / pu.factor) * u.factor) * pt.standard_price
                            ELSE 0.0
                            END AS out_value,
                        CASE WHEN sp.type in ('in') THEN
                            sum((sm.product_qty / pu.factor) * u.factor) * pt.standard_price
                            ELSE 0.0
                            END AS in_value,
                        min(sm.id) as sm_id,
                        sm.date as dp,
                        to_char(date_trunc('day',sm.date), 'YYYY') as curr_year,
                        to_char(date_trunc('day',sm.date), 'MM') as curr_month,
                        to_char(date_trunc('day',sm.date), 'YYYY-MM-DD') as curr_day,
                        avg(date(sm.date)-date(sm.create_date)) as curr_day_diff,
                        avg(date(sm.date_expected)-date(sm.create_date)) as curr_day_diff1,
                        avg(date(sm.date)-date(sm.date_expected)) as curr_day_diff2,
                        sm.location_id as location_id,
                        sm.location_dest_id as location_dest_id,
                        sm.prodlot_id as prodlot_id,
                        sm.comment as comment,
                        sm.tracking_id as tracking_id,
                        CASE
                          WHEN sp.type in ('out') THEN
                            sum((-sm.product_qty / pu.factor) * u.factor)
                          WHEN sp.type in ('in') THEN
                            sum((sm.product_qty / pu.factor) * u.factor)
                          ELSE 0.0
                          END AS product_qty,
                        pt.nomen_manda_2 as categ_id,
                        sp.partner_id2 as partner_id,
                        sm.product_id as product_id,
                        sm.origin as origin,
                        sm.reason_type_id as reason_type_id,
                        sm.picking_id as picking_id,
                            sm.company_id as company_id,
                            sm.state as state,
                            pt.uom_id as product_uom,
                            sp.type as type,
                            sp.stock_journal_id AS stock_journal
                    FROM
                        stock_move sm
                        LEFT JOIN stock_picking sp ON (sm.picking_id=sp.id)
                        LEFT JOIN product_product pp ON (sm.product_id=pp.id)
                        LEFT JOIN product_uom pu ON (sm.product_uom=pu.id)
                        LEFT JOIN product_template pt ON (pp.product_tmpl_id=pt.id)
                        LEFT JOIN product_uom u ON (pt.uom_id = u.id)
                        LEFT JOIN stock_location sl ON (sm.location_id = sl.id)

                    GROUP BY
                        sm.id,sp.type, sm.date,sp.partner_id2,
                        sm.product_id,sm.state,pt.uom_id,sm.date_expected, sm.origin,
                        sm.product_id,pt.standard_price, sm.picking_id, sm.product_qty, sm.prodlot_id, sm.comment, sm.tracking_id,
                        sm.company_id,sm.product_qty, sm.location_id,sm.location_dest_id,pu.factor,pt.nomen_manda_2, sp.stock_journal_id, sm.reason_type_id)
                    AS al

                    GROUP BY
                        al.out_qty,al.in_qty,al.curr_year,al.curr_month,
                        al.curr_day,al.curr_day_diff,al.curr_day_diff1,al.curr_day_diff2,al.dp,al.location_id,al.location_dest_id,
                        al.partner_id,al.product_id,al.state,al.product_uom, al.sm_id, al.origin,
                        al.picking_id,al.company_id,al.type,al.product_qty, al.categ_id, al.stock_journal, al.tracking_id, al.comment, al.prodlot_id, al.reason_type_id
               )
        """)

    def read(self, cr, uid, ids, fields=None, context=None, load='_classic_read'):
        if context is None:
            context = {}
        if fields is None:
            fields = []
        context['with_expiry'] = 1
        return super(report_stock_move, self).read(cr, uid, ids, fields, context, load)

    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False):
        '''
        Add functional currency on all lines
        '''
        res = super(report_stock_move, self).read_group(cr, uid, domain, fields, groupby, offset, limit, context, orderby)
        if self._name == 'report.stock.move':
            for data in res:
                # If no information to display, don't display the currency
                if not '__count' in data or data['__count'] != 0:
                    currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id
                    data.update({'currency_id': (currency.id, currency.name)})

                product_id = 'product_id' in data and data['product_id'] and data['product_id'][0] or False
                if data.get('__domain'):
                    for x in data.get('__domain'):
                        if x[0] == 'product_id':
                            product_id = x[2]

                if isinstance(product_id, str):
                    product_id = self.pool.get('product.product').search(cr, uid, [('default_code', '=', product_id)], context=context)
                    if product_id:
                        product_id = product_id[0]
                if product_id:
                    uom = self.pool.get('product.product').browse(cr, uid, product_id, context=context).uom_id
                    data.update({'product_uom': (uom.id, uom.name)})

                if not product_id and 'product_qty' in data:
                    data.update({'product_qty': '', 'product_uom': False})
                if not product_id and 'product_qty_in' in data:
                    data.update({'product_qty_in': '', 'product_uom': False})
                if not product_id and 'product_qty_out' in data:
                    data.update({'product_qty_out': '', 'product_uom': False})
        return res

report_stock_move()


class export_report_stock_move(osv.osv):
    _name = 'export.report.stock.move'

    def _get_has_locations(self, cr, uid, ids, field, arg, context=None):
        '''
        Return True if the report has a location
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        for report in self.browse(cr, uid, ids, fields_to_fetch=['location_ids'], context=context):
            res[report.id] = report.location_ids and True or False

        return res

    _columns = {
        'company_id': fields.many2one(
            'res.company',
            string='DB/Instance name',
            readonly=True,
        ),
        'name': fields.datetime(
            string='Generated on',
            readonly=True,
        ),
        'partner_id': fields.many2one(
            'res.partner',
            string='Specific partner',
            help="""If a partner is choosen, only stock moves that comes
from/to this partner will be shown.""",
        ),
        'reason_type_ids': fields.many2many(
            'stock.reason.type',
            'report_stock_move_reason_type_rel',
            'report_id',
            'reason_type_id',
            string='Specific reason types',
            help="""Only stock moves that have one of these reason types will
be shown on the report""",
        ),
        'product_id': fields.many2one(
            'product.product',
            string='Specific product',
            help="""If a product is choosen, only stock moves that move this
product will be shown.""",
        ),
        'prodlot_id': fields.many2one(
            'stock.production.lot',
            string='Specific batch',
        ),
        'expiry_date': fields.date(
            string='Specific expiry date',
        ),
        'location_ids': fields.many2many(
            'stock.location',
            'report_stock_move_location_rel',
            'report_id',
            'location_id',
            string='Specific location(s)',
            help="If a location is choosen, only stock moves that comes from/to this location will be shown.",
            domain=['|', ('active', '=', True), ('active', '=', False)],
        ),
        'has_locations': fields.function(_get_has_locations, method=True, type='boolean', string='Report has locations', store=True, readonly=True),
        'product_list_id': fields.many2one(
            'product.list',
            string='Specific product list',
        ),
        'only_standard_loc': fields.boolean('Only display standard stock location(s)'),
        'date_from': fields.date(
            string='From',
        ),
        'date_to': fields.date(
            string='To',
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
        'exported_file': fields.binary(
            string='Exported file',
        ),
        'file_name': fields.char(
            size=128,
            string='Filename',
            readonly=True,
        ),
    }

    _defaults = {
        'state': 'draft',
        'company_id': lambda s, cr, uid, c: s.pool.get('res.company')._company_default_get(cr, uid, 'export.report.stock.move', context=c),
        'only_standard_loc': True,
    }

    _order = 'id desc'

    def update(self, cr, uid, ids, context=None):
        return {}

    def generate_report(self, cr, uid, ids, context=None):
        """
        Select the good lines on the report.stock.move table
        """
        rsm_obj = self.pool.get('stock.move')
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        loc_usage = ['supplier', 'customer', 'internal', 'inventory', 'procurement', 'production']
        for report in self.browse(cr, uid, ids, context=context):
            domain = [
                ('location_id.usage', 'in', loc_usage),
                ('location_dest_id.usage', 'in', loc_usage),
                ('state', '=', 'done'),
                ('product_qty', '!=', 0),
            ]
            if report.partner_id:
                domain.append(('partner_id', '=', report.partner_id.id))
            if report.product_id:
                domain.append(('product_id', '=', report.product_id.id))
            if report.prodlot_id:
                domain.append(('prodlot_id', '=', report.prodlot_id.id))
            if report.expiry_date:
                domain.append(('prodlot_id.life_date', '=', report.expiry_date))
            if report.date_from:
                domain.append(('date', '>=', report.date_from))
            if report.date_to:
                domain.append(('date', '<=', report.date_to))

            rt_ids = []
            for rt in report.reason_type_ids:
                rt_ids.append(rt.id)
            if rt_ids:
                domain.append(('reason_type_id', 'in', rt_ids))

            loc_ids = [l.id for l in report.location_ids]
            selected_locs = False
            non_standard_loc_ids = []
            if loc_ids:
                selected_locs = True
                domain.extend(['|', ('location_id', 'in', loc_ids), ('location_dest_id', 'in', loc_ids)])
                context['location'] = loc_ids
            else:
                if report.only_standard_loc:
                    # Input
                    non_standard_loc_ids.append(data_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_input')[1])
                    # Cross Docking
                    non_standard_loc_ids.append(data_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1])
                    # Packing
                    non_standard_loc_ids.append(data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'stock_location_packing')[1])
                    # Shipment
                    non_standard_loc_ids.append(data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'stock_location_dispatch')[1])
                    # Distribution
                    non_standard_loc_ids.append(data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'stock_location_distribution')[1])
                    # Quarantine (analyze)
                    non_standard_loc_ids.append(data_obj.get_object_reference(cr, uid, 'stock_override', 'stock_location_quarantine_analyze')[1])
                    # Quarantine (before scap)
                    non_standard_loc_ids.append(data_obj.get_object_reference(cr, uid, 'stock_override', 'stock_location_quarantine_scrap')[1])

                    domain.extend(['|', ('location_id', 'not in', non_standard_loc_ids), ('location_dest_id', 'not in', non_standard_loc_ids)])

            context['domain'] = domain
            context['active_test'] = False
            rsm_ids = rsm_obj.search(cr, uid, domain, order='product_id, date', context=context)
            context['active_test'] = True
            self.write(cr, uid, [report.id], {
                'name': time.strftime('%Y-%m-%d %H:%M:%S'),
                'state': 'in_progress',
            })

            datas = {
                'ids': [report.id],
                'moves': rsm_ids,
                'selected_locs': selected_locs,
            }

            cr.commit()
            new_thread = threading.Thread(
                target=self.generate_report_bkg,
                args=(cr, uid, report.id, datas, context)
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
                    'stock_override', 'export_report_stock_move_info_view')[1]
                res['view_id'] = [view_id]

            return res

        raise osv.except_osv(
            _('Error'),
            _('No stock moves found for these parameters')
        )

    def generate_report_bkg(self, cr, uid, ids, datas, context=None):
        """
        Generate the report in background
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        import pooler
        new_cr = pooler.get_db(cr.dbname).cursor()

        rp_spool = report_spool()
        result = rp_spool.exp_report(cr.dbname, uid, 'stock.move.xls', ids, datas, context)
        file_res = {'state': False}
        while not file_res.get('state'):
            file_res = rp_spool.exp_report_get(cr.dbname, uid, result)
            time.sleep(0.5)
        attachment = self.pool.get('ir.attachment')
        attachment.create(new_cr, uid, {
            'name': 'in_out_report_%s.xls' % time.strftime('%Y_%m_%d_%H_%M'),
            'datas_fname': 'in_out_report_%s.xls' % time.strftime('%Y_%m_%d_%H_%M'),
            'description': 'IN & OUT Report',
            'res_model': 'export.report.stock.move',
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

        prodlot = self.pool.get('stock.production.lot'). \
            browse(cr, uid, prodlot_id)
        return {
            'value': {
                'product_id': prodlot.product_id.id,
                'expiry_date': prodlot.life_date,
            },
        }

    def onchange_location_ids(self, cr, uid, ids, location_ids):
        """
        Disable the checkbox if there are locations selected
        """
        if location_ids != [(6, 0, [])]:
            return {
                'value': {
                    'only_standard_loc': False,
                    'has_locations': True,
                },
            }
        else:
            return {
                'value': {
                    'has_locations': False,
                },
            }

    def create(self, cr, uid, vals, context=None):
        """
        Call onchange_prodlot() if a prodlot is specified
        """
        if vals.get('prodlot_id'):
            vals.update(self.onchange_prodlot(cr, uid, False, vals.get('prodlot_id')))

        if vals.get('location_ids') and vals['location_ids'] != [(6, 0, [])]:
            vals['only_standard_loc'] = False

        return super(export_report_stock_move, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Call onchange_prodlot() if a prodlot is specified
        """
        if not ids:
            return True
        if vals.get('prodlot_id'):
            vals.update(self.onchange_prodlot(cr, uid, ids, vals.get('prodlot_id')))

        if vals.get('location_ids') and vals['location_ids'] != [(6, 0, [])]:
            vals['only_standard_loc'] = False

        return super(export_report_stock_move, self).write(cr, uid, ids, vals, context=context)


export_report_stock_move()


class parser_report_stock_move_xls(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(parser_report_stock_move_xls, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getLines': self.getLines,
        })

    def getLines(self, currency_id):
        prod_obj = self.pool.get('product.product')
        curr_obj = self.pool.get('res.currency')
        loc_obj = self.pool.get('stock.location')
        data_obj = self.pool.get('ir.model.data')
        res = []
        company_id = self.pool.get('res.users').browse(
            self.cr, self.uid, self.uid).company_id.partner_id.id

        def get_src_dest(m, f='location_id'):
            if m[f].usage in ('supplier', 'customer') and m.picking_id and m.picking_id.partner_id and m.picking_id.partner_id.id != company_id:
                return m.picking_id.partner_id.name
            else:
                return m[f].name

        if not self.datas['selected_locs']:
            inst_full_view_id = data_obj.get_object_reference(self.cr, self.uid, 'stock', 'stock_location_locations')[1]
            loc_domain = [('location_id', 'child_of', inst_full_view_id), ('active', 'in', ['t', 'f'])]
            location_ids = loc_obj.search(self.cr, self.uid, loc_domain, context=self.localcontext)
            self.localcontext.update({'location': location_ids})
        self.localcontext['compute_child'] = False
        for move in self.pool.get('stock.move').browse(self.cr, self.uid, self.datas['moves'], context=self.localcontext):
            move_date = move.date or False
            # Get stock
            ctx = self.localcontext.copy()
            ctx.update({'to_date': move_date})
            prod_stock = prod_obj.read(self.cr, self.uid, move.product_id.id, ['qty_available'], context=ctx)['qty_available']
            prod_stock_bn = 0
            if move.prodlot_id:
                ctx.update({'prodlot_id': move.prodlot_id.id or False})
                prod_stock_bn = prod_obj.read(self.cr, self.uid, move.product_id.id, ['qty_available'], context=ctx)['qty_available']

            # Get Unit Price at date
            prod_price = move.price_unit or 0
            if not prod_price:
                if move_date:
                    self.cr.execute("""SELECT distinct on (product_id) product_id, old_standard_price
                                FROM standard_price_track_changes
                                WHERE product_id = %s AND change_date >= %s
                                ORDER BY product_id, change_date ASC
                                """, (move.product_id.id, move_date))
                    for x in self.cr.fetchall():
                        prod_price = x[1]
                if not prod_price:
                    prod_price = move.product_id.standard_price
            if move.price_currency_id.id != currency_id:
                prod_price = curr_obj.compute(self.cr, self.uid, move.price_currency_id.id, currency_id,
                                              prod_price, round=False, context=ctx)

            res.append({
                'product_code': move.product_id.default_code,
                'product_name': move.product_id.name,
                'uom': move.product_uom.name,
                'date_done': move_date,
                'need_batch': move.product_id.batch_management,
                'batch': move.prodlot_id and move.prodlot_id.name or '',
                'expiry_date': move.prodlot_id and move.prodlot_id.life_date or False,
                'qty': move.product_qty,
                'unit_price': prod_price,
                'move_value': move.product_qty * prod_price,
                'prod_stock_bn': move.prodlot_id and prod_stock_bn or 0,
                'prod_stock': prod_stock,
                'source': get_src_dest(move, 'location_id'),
                'destination': get_src_dest(move, 'location_dest_id'),
                'reason_type': move.reason_type_id and move.reason_type_id.complete_name or '',
                'doc_ref': move.picking_id and move.picking_id.name or move.name or '',
            })

        return res


class report_stock_move_xls(SpreadsheetReport):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(report_stock_move_xls, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(report_stock_move_xls, self).create(cr, uid, ids, data, context=context)
        return (a[0], 'xls')


report_stock_move_xls('report.stock.move.xls', 'export.report.stock.move', 'addons/stock_override/report/report_stock_move_xls.mako', parser=parser_report_stock_move_xls, header='internal')
