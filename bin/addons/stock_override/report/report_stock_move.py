# -*- coding: utf-8 -*-

import tools
import time
import threading
import uuid
import logging
from osv import fields, osv
from decimal_precision import decimal_precision as dp
from tools.translate import _
import pooler
import datetime

from xlwt import Workbook, easyxf, Borders
import tempfile
import base64


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
        'location_name': fields.char(string='Source Location', type='char', size=64),
        'location_dest_id': fields.many2one('stock.location', 'Dest. Location', readonly=True, select=True, help="Location where the system will stock the finished products."),
        'location_dest_name': fields.char(string='Dest. Location', type='char', size=64),
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
        'origin': fields.related('picking_id', 'origin', type='char', size=512, relation="stock.picking", string="Origin", store=True, write_relate=False),
        'move': fields.many2one('stock.move', string='Move'),
        'reason_type_id': fields.many2one('stock.reason.type', string='Reason type'),
        'currency_id': fields.many2one('res.currency', string='Currency'),
        'product_code': fields.related('product_id', 'default_code', type='char', string='Product Code', write_relate=False),
        'product_name': fields.related('product_id', 'name', type='char', string='Product Name', write_relate=False),
        'expiry_date': fields.related('prodlot_id', 'life_date', type='date', string='Expiry Date', write_relate=False),
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
                        al.location_name as location_name,
                        al.picking_id as picking_id,
                        al.company_id as company_id,
                        al.location_dest_id as location_dest_id,
                        al.location_dest_name as location_dest_name,
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
                            sp.stock_journal_id AS stock_journal,
                        sl.name as location_name,
                        sld.name as location_dest_name
                    FROM
                        stock_move sm
                        LEFT JOIN stock_picking sp ON (sm.picking_id=sp.id)
                        LEFT JOIN product_product pp ON (sm.product_id=pp.id)
                        LEFT JOIN product_uom pu ON (sm.product_uom=pu.id)
                        LEFT JOIN product_template pt ON (pp.product_tmpl_id=pt.id)
                        LEFT JOIN product_uom u ON (pt.uom_id = u.id)
                        LEFT JOIN stock_location sl ON (sm.location_id = sl.id)
                        LEFT JOIN stock_location sld ON (sm.location_dest_id = sld.id)

                    GROUP BY
                        sm.id,sp.type, sm.date,sp.partner_id2,
                        sm.product_id,sm.state,pt.uom_id,sm.date_expected, sm.origin,
                        sm.product_id,pt.standard_price, sm.picking_id, sm.product_qty, sm.prodlot_id, sm.comment, sm.tracking_id,
                        sm.company_id,sm.product_qty, sm.location_id,sm.location_dest_id,pu.factor,pt.nomen_manda_2, sp.stock_journal_id, 
                        sm.reason_type_id, sl.name, sld.name)
                    AS al

                    GROUP BY
                        al.out_qty,al.in_qty,al.curr_year,al.curr_month,
                        al.curr_day,al.curr_day_diff,al.curr_day_diff1,al.curr_day_diff2,al.dp,al.location_id,al.location_dest_id,al.location_name,al.location_dest_name,
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

    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False, count=False):
        '''
        Add functional currency on all lines
        '''
        res = super(report_stock_move, self).read_group(cr, uid, domain, fields, groupby, offset, limit, context, orderby, count=count)
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


class export_report_stock_move_progress(osv.osv_memory):
    _name = 'export.report.stock.move.progress'
    _columns = {
        'name': fields.many2one('export.report.stock.move', 'Report'),
        'progress': fields.char('Nb lines', size=256),
        'uuid': fields.char('uuid', size=256),
    }

    def create(self, cr, uid, vals, context=None):
        vals['uuid'] = str(uuid.uuid4())
        osv._recorded_psql_pid.set(vals['uuid'], cr._cnx.get_backend_pid())
        return super(export_report_stock_move_progress, self).create(cr, uid, vals, context)

export_report_stock_move_progress()

class export_report_stock_move(osv.osv):
    _name = 'export.report.stock.move'

    def kill_request(self, cr, uid, ids, context=None):
        pg_ids = self.pool.get('export.report.stock.move.progress').search(cr, uid, [('name', 'in', ids)])
        if pg_ids:
            for x in self.pool.get('export.report.stock.move.progress').read(cr, uid, pg_ids, ['uuid']):
                osv._recorded_psql_pid.kill(cr, x['uuid'])
        self.write(cr, uid, ids, {'state': 'cancel', 'error': _('Request cancelled by user')})
        return True

    def _get_progress(self, cr, uid, ids, field, arg, context=None):
        ret = {}
        for id in ids:
            ret[id] = False
        pg_ids = self.pool.get('export.report.stock.move.progress').search(cr, uid, [('name', 'in', ids)])
        if pg_ids:
            for x in self.pool.get('export.report.stock.move.progress').read(cr, uid, pg_ids, ['name', 'progress']):
                ret[x['name']] = x['progress']
        return ret

    def _get_has_locations(self, cr, uid, ids, field, arg, context=None):
        '''
        Return True if the report has a location
        '''
        if isinstance(ids, int):
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
        'progress': fields.function(_get_progress, method=True, type='char', string='Progress', store=False),
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
                ('error', 'Error'),
                ('cancel', 'Cancel'),
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
        'error': fields.text('Error', readonly=1),
    }

    _defaults = {
        'state': 'draft',
        'company_id': lambda s, cr, uid, c: s.pool.get('res.company')._company_default_get(cr, uid, 'export.report.stock.move', context=c),
        'only_standard_loc': True,
        'name': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
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

        if isinstance(ids, int):
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
            if report.product_list_id:
                p_ids = self.pool.get('product.product').search(cr, uid, [('list_ids', '=', report.product_list_id.id)])
                domain.append(('product_id', 'in', p_ids))
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
                    # Expired / Damaged / For Scrap
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
            new_thread.join(6.0)

            res = {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_id': report.id,
                'context': context,
                'target': 'same',
            }
            if new_thread.is_alive():
                view_id = data_obj.get_object_reference(
                    cr, uid,
                    'stock_override', 'export_report_stock_move_info_view')[1]
                res['view_id'] = [view_id]

            return res

        raise osv.except_osv(
            _('Error'),
            _('No stock moves found for these parameters')
        )

    def getLines(self, cr, uid, datas, currency_id, context=None):
        if context is None:
            context = {}

        PARTNER_TYPES = {
            'internal': _('Internal'),
            'section': _('Inter-section'),
            'external': _('External'),
            'esc': _('ESC'),
            'intermission': _('Intermission'),
        }

        ORDER_TYPES = {
            'regular': _('Regular'),
            'donation_exp': _('Donation before expiry'),
            'donation_st': _('Standard donation'),
            'loan': _('Loan'),
            'in_kind': _('In Kind Donation'),
            'purchase_list': _('Purchase List'),
            'direct': _('Direct Purchase Order'),
        }

        ORDER_CATEGORIES = {
            'medical': _('Medical'),
            'log': _('Logistic'),
            'service': _('Service'),
            'transport': _('Transport'),
            'other': _('Other'),
        }

        _logger = logging.getLogger('in.out.report')
        prod_obj = self.pool.get('product.product')
        curr_obj = self.pool.get('res.currency')
        loc_obj = self.pool.get('stock.location')
        data_obj = self.pool.get('ir.model.data')
        rate_cache = {}

        if not datas['moves']:
            return
        if not datas['selected_locs']:
            inst_full_view_id = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_locations')[1]
            loc_domain = [('location_id', 'child_of', inst_full_view_id), ('active', 'in', ['t', 'f'])]
            location_ids = loc_obj.search(cr, uid, loc_domain, context=context)
            context.update({'location': location_ids})
        context['compute_child'] = False
        nb_lines = len(datas['moves'])
        _logger.info('Report started on %d lines' % nb_lines)

        lang_ctx = {'lang': context.get('lang', 'en_MF')}
        reason_ids = self.pool.get('stock.reason.type').search(cr, uid, [])
        reason_info = {}
        for x in self.pool.get('stock.reason.type').read(cr, uid, reason_ids, ['complete_name'], context=lang_ctx):
            reason_info[x['id']] = x['complete_name']

        all_loc_ids = loc_obj.search(cr, uid, [('active', 'in', ['t', 'f'])])
        location_info = {}
        for x in loc_obj.read(cr, uid, all_loc_ids, ['name'], context=lang_ctx):
            location_info[x['id']] = x['name']

        new_cr = pooler.get_db(cr.dbname).cursor()
        try:
            ave_price_list = {}
            new_cr.execute("""
                SELECT distinct on (m.id) m.id, new_standard_price FROM stock_move m
                LEFT JOIN standard_price_track_changes tc on tc.product_id = m.product_id AND tc.change_date >= m.date
                WHERE m.id IN %s
                ORDER BY m.id, change_date ASC
            """, (tuple(datas['moves']),))
            for move_d in new_cr.fetchall():
                ave_price_list[move_d[0]] = move_d[1]

            new_cr.execute('''select
                    m.id as move_id, 
                    m.product_id as product_id,
                    m.prodlot_id as prodlot_id,
                    m.product_qty as product_qty,
                    t.uom_id as prod_uom,
                    m.name as move_name,
                    p.default_code as default_code,
                    p.batch_management as batch_management,
                    COALESCE(trans.value, t.name) as product_name,
                    m.price_unit as price_unit,
                    m.price_currency_id as price_currency_id,
                    p.currency_id as product_currency_id,
                    pick.name as pick_name,
                    m.date as date,
                    uom.name as uom_name,
                    nom.name as nom_name,
                    t.standard_price as standard_price,
                    m.location_id as location_src_id,
                    m.location_dest_id as location_dest_id,
                    par.name as partner_name,
                    par.partner_type as partner_type,
                    m.reason_type_id as reason_type_id,
                    lot.name as lot_name,
                    lot.life_date as life_date,
                    COALESCE(pick.origin, m.origin) as origin,
                    pi.ref as pi_name,
                    m.comment,
                    case when m.sale_line_id is not null and not so.procurement_request then so.order_type when m.purchase_line_id is not null then po.order_type end as order_type,
                    case when m.sale_line_id is not null then so.categ when m.purchase_line_id is not null then po.categ end as order_category,
                    case when pick.subtype not in ('ppl', 'packing') then null when so.procurement_request then %s else pl.currency_id end as bug_pl
                from
                    stock_move m
                    inner join product_uom uom on uom.id = m.product_uom
                    inner join product_product p on p.id = m.product_id
                    inner join product_template t on t.id = p.product_tmpl_id
                    left join stock_picking pick on m.picking_id = pick.id
                    left join stock_production_lot lot on lot.id = m.prodlot_id
                    left join ir_translation trans on trans.name='product.template,name' and trans.res_id=t.id and trans.lang=%s
                    left join sale_order_line sol on m.sale_line_id = sol.id
                    left join sale_order so on sol.order_id = so.id
                    left join purchase_order_line pol on m.purchase_line_id = pol.id
                    left join purchase_order po on pol.order_id = po.id
                    left join product_pricelist pl on so.pricelist_id = pl.id
                    left join product_nomenclature nom on nom.id = t.nomen_manda_0
                    left join res_partner par on par.id = m.partner_id
                    left join physical_inventory_discrepancy pi_discr on pi_discr.move_id = m.id
                    left join physical_inventory pi on pi.id = pi_discr.inventory_id
                where
                    m.id in %s
                order by p.default_code, m.date asc, lot.name
            ''', (currency_id, lang_ctx.get('lang'), tuple(datas['moves'])))
            # do not change order by or stock level computation will be wrong

            start_time = time.time()
            nb_done = 0
            bn_stock_cache = {}
            prod_stock_cache = {}
            while rows := new_cr.dictfetchmany(600):
                for move in rows:
                    nb_done += 1
                    if nb_done % 300 == 0:
                        _logger.info('%d/%d %s seconds' % (nb_done, nb_lines, time.time() - start_time))
                        if context.get('progress_id'):
                            self.pool.get('export.report.stock.move.progress').write(cr, uid, context.get('progress_id'), {'progress': '%d / %d' % (nb_done, nb_lines)})
                        start_time = time.time()
                    move_date = move['date'] or False
                    # Get stock
                    ctx = context.copy()
                    prod_stock_bn = _('NA')
                    prod_stock = 0
                    ctx.update({'to_date': move_date, 'prodlot_id': False, 'from_strict_date': prod_stock_cache.get(move['product_id'], {}).get('to_date', False)})

                    if ctx['to_date'] != ctx['from_strict_date']:
                        prod_stock = prod_obj.read(cr, uid, move['product_id'], ['qty_available'], context=ctx)['qty_available']
                        if move['product_id'] in prod_stock_cache:
                            prod_stock += prod_stock_cache[move['product_id']]['stock']
                        prod_stock_cache[move['product_id']] = {'to_date': move_date, 'stock': prod_stock}
                    else:
                        prod_stock = prod_stock_cache[move['product_id']]['stock']

                    if move['prodlot_id']:
                        ctx.update({'prodlot_id': move['prodlot_id'], 'from_strict_date': bn_stock_cache.get(move['prodlot_id'], {}).get('to_date', False)})
                        if ctx['to_date'] != ctx['from_strict_date']:
                            prod_stock_bn = prod_obj.read(cr, uid, move['product_id'], ['qty_available'], context=ctx)['qty_available']
                            if move['prodlot_id'] in bn_stock_cache:
                                prod_stock_bn += bn_stock_cache[move['prodlot_id']]['stock']
                            bn_stock_cache[move['prodlot_id']] = {'to_date': move_date, 'stock': prod_stock_bn}
                        else:
                            prod_stock_bn = bn_stock_cache[move['prodlot_id']]['stock']

                    # Get Unit Price at date
                    prod_price = move['price_unit'] or 0
                    if not prod_price:
                        if move_date:
                            cr.execute("""SELECT old_standard_price
                                        FROM standard_price_track_changes
                                        WHERE product_id = %s AND change_date >= %s
                                        ORDER BY change_date ASC
                                        LIMIT 1
                                        """, (move['product_id'], move_date))
                            for x in cr.fetchall():
                                prod_price = x[0]
                        if not prod_price:
                            prod_price = move['standard_price']
                    elif move_date:
                        move_currency = move['bug_pl'] or move['price_currency_id']
                        if move_currency and move_currency != currency_id:
                            first_day = time.strftime('%Y-%m-01', time.strptime(move_date, '%Y-%m-%d %H:%M:%S'))
                            rate_key = '%s-%s' % (move_currency, first_day)
                            if rate_key not in rate_cache:
                                rate_cache[rate_key] = curr_obj.read(cr, uid, move_currency, ['rate'], {'currency_date': first_day})['rate'] or 1
                            prod_price = prod_price/rate_cache[rate_key]

                    # Get average price
                    func_ave_price = ave_price_list.get(move['move_id'], False) or move['standard_price']
                    if currency_id != move['product_currency_id']:
                        func_ave_price = curr_obj.compute(cr, uid, move['product_currency_id'], currency_id,
                                                          func_ave_price, round=False, context=self.localcontext)

                    yield [
                        move['default_code'],
                        move['product_name'],
                        move['uom_name'],
                        move['nom_name'],
                        move_date and datetime.datetime.strptime(move_date, '%Y-%m-%d %H:%M:%S') or '',
                        move['lot_name'] or '',
                        move['life_date'] and datetime.datetime.strptime(move['life_date'], '%Y-%m-%d'),
                        move['product_qty'],
                        prod_price,
                        move['product_qty'] * prod_price,
                        func_ave_price,
                        move['product_qty'] * func_ave_price,
                        prod_stock_bn,
                        prod_stock,
                        location_info.get(move['location_src_id']),
                        location_info.get(move['location_dest_id']),
                        move['partner_name'],
                        PARTNER_TYPES.get(move['partner_type']) or '',
                        reason_info.get(move['reason_type_id']) or '',
                        move['pi_name'] or move['pick_name'] or move['move_name'] or '',
                        move['pi_name'] and move['move_name'] or move['origin'] or '',
                        move['comment'] or '',
                        ORDER_TYPES.get(move['order_type']) or '',
                        ORDER_CATEGORIES.get(move['order_category']) or '',
                    ]

            return
        finally:
            new_cr.commit()
            new_cr.close(True)

    def generate_report_bkg(self, cr, uid, ids, datas, context=None):
        """
        Generate the report in background
        """
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        new_cr = pooler.get_db(cr.dbname).cursor()
        try:
            context['progress_id'] = self.pool.get('export.report.stock.move.progress').create(new_cr, uid, {'name': ids[0]})
            context['report_id'] = ids[0]

            borders = Borders()
            borders.left = Borders.THIN
            borders.right = Borders.THIN
            borders.top = Borders.THIN
            borders.bottom = Borders.THIN

            top_header1 = easyxf("""
                    font: height 200;
                    font: name Calibri;
                    pattern: pattern solid, fore_colour gray25;
                    align: wrap on, vert center, horiz center;
            """)
            top_header2 = easyxf("""
                    font: height 200;
                    font: name Calibri;
                    pattern: pattern solid, fore_colour tan;
                    align: wrap on, vert center, horiz center;
            """)
            header_style = easyxf("""
                    font: height 200;
                    font: name Calibri;
                    pattern: pattern solid, fore_colour gray25;
                    align: wrap on, vert center, horiz center;
                """)
            header_style.borders = borders

            header2_date_style = easyxf("""
                    font: height 200;
                    font: name Calibri;
                    pattern: pattern solid, fore_colour tan;
                    align: wrap on, vert center, horiz center;
                """, num_format_str='dd/mm/yyyy')

            header2_date_time_style = easyxf("""
                    font: height 200;
                    font: name Calibri;
                    pattern: pattern solid, fore_colour tan;
                    align: wrap on, vert center, horiz center;
                """, num_format_str='dd/mm/yyyy h:mm')

            row_style = easyxf("""
                    font: height 200;
                    font: name Calibri;
                    align: wrap on, vert center, horiz center;
                """)
            row_style.borders = borders

            row_left_style = easyxf("""
                font: height 200;
                font: name Calibri;
                align: wrap on, vert center, horiz left;
            """)
            row_left_style.borders = borders

            date_time_format = easyxf(
                """
                    font: height 200;
                    font: name Calibri;
                    align: wrap on, vert center, horiz center;
                """, num_format_str='dd/mm/yyyy h:mm')
            date_time_format.borders = borders

            date_format = easyxf(
                """
                    font: height 200;
                    font: name Calibri;
                    align: wrap on, vert center, horiz center;
                """, num_format_str='dd/mm/yyyy')
            date_format.borders = borders

            book = Workbook()
            sheet = book.add_sheet(_('IN & OUT Report'))
            sheet.row_default_height = 10*20

            report = self.browse(cr, uid, ids[0], context=context)
            currency = report.company_id.currency_id
            header = [
                (_('DB/instance name'), report.company_id.name or '', ''),
                (_('Generated on'), report.name and datetime.datetime.strptime(report.name, '%Y-%m-%d %H:%M:%S') or '', header2_date_time_style),
                (_('From'), report.date_from and datetime.datetime.strptime(report.date_from, '%Y-%m-%d') or '', header2_date_style),
                (_('To'), report.date_to and datetime.datetime.strptime(report.date_to, '%Y-%m-%d') or '', header2_date_style),
                (_('Specific partner'), report.partner_id and report.partner_id.name or '', ''),
                (_('Specific location(s)'), report.location_ids and ' ; '.join([l.name for l in report.location_ids]) or '', ''),
                (_('Specific product list'), report.product_list_id and report.product_list_id.name or '', ''),
                (_('Specific product'), report.product_id and report.product_id.default_code or '', ''),
                (_('Specific batch'), report.prodlot_id and report.prodlot_id.name or '', ''),
                (_('Specific expiry date'), report.expiry_date and datetime.datetime.strptime(report.expiry_date, '%Y-%m-%d') or '', header2_date_style),
                (_('Only display standard stock location(s)'), report.only_standard_loc and _('Yes') or _('No'), ''),
                (_('Specific reason types'), report.reason_type_ids and ' ; '.join([r.complete_name for r in report.reason_type_ids]) or '', '')
            ]
            row_count = 0
            #sheet.write_merge(2, 2, begin, max_size, instance_dict[inst_id], style=header_styles[i])
            for col_name, col_value, style in header:
                sheet.write_merge(row_count, row_count, 0, 1, col_name, top_header1)
                if not style:
                    style = top_header2

                sheet.write_merge(row_count, row_count, 2, 4, col_value, style)
                row_count += 1

            row_count += 1
            pos = 0
            headers = [(_('Product Code'), '', 25), (_('Product Description'), '', 70), (_('UoM'), '', 11),  (_('Product Main Type'), '', 11),  (_('Stock Move Date'), date_time_format,20), (_('Batch'), '',30), (_('Exp Date'), date_format, 11), (_('Quantity'), '', 10), (_('Unit Price (%s)') % (currency.name,), '', 10), (_('Movement value (%s)') % (currency.name,) , '', 10), (_('Ave. Cost Price Value (%s)') % (currency.name,), '', 10), (_('Ave. Price Movement value (%s)') % (currency.name,) , '', 10), (_('BN stock after movement (instance)'), '', 10), (_('Total stock after movement (instance)'), '', 10),  (_('Source'), '', 40), (_('Destination'), '', 40), (_('Partner'), '', 30), (_('Partner Type'), '', 15), (_('Reason Type'), '', 30), (_('Document Ref.'), '', 40), (_('Origin'), '', 70), (_('Line Comment'), '', 60), (_('Order Type'), '', 15), (_('Order Category'), '', 11)]

            for header_row, col_type, size in headers:
                sheet.col(pos).width = size * 256
                sheet.write(row_count, pos, header_row, header_style)
                pos += 1

            sheet.set_horz_split_pos(row_count+1)
            sheet.panes_frozen = True
            sheet.remove_splits = True
            sheet.row(row_count).height_mismatch = True
            sheet.row(row_count).height = 45*20
            for data_list in self.getLines(new_cr, uid, datas, currency.id, context):
                row_count += 1
                col_count = 0
                for value in data_list:
                    if value and headers[col_count][1]:
                        style = headers[col_count][1]
                    else:
                        if col_count == 18:  # Change style on Origin column
                            style = row_left_style
                        else:
                            style = row_style
                    sheet.write(row_count, col_count, value, style)
                    col_count += 1
                #sheet.row(row_count).height = 60*20

            export_file = tempfile.NamedTemporaryFile(delete=False)
            file_name = export_file.name
            book.save(export_file)
            export_file.close()

            attachment = self.pool.get('ir.attachment')
            attachment.create(new_cr, uid, {
                'name': 'in_out_report_%s.xls' % time.strftime('%Y_%m_%d_%H_%M'),
                'datas_fname': 'in_out_report_%s.xls' % time.strftime('%Y_%m_%d_%H_%M'),
                'description': 'IN & OUT Report',
                'res_model': 'export.report.stock.move',
                'res_id': ids[0],
                'datas': base64.b64encode(open(file_name, 'rb').read()),
            })
            self.write(new_cr, uid, ids, {'state': 'ready'}, context=context)
        except Exception as e:
            new_cr.rollback()
            if context.get('report_id'):
                self.pool.get('export.report.stock.move').write(new_cr, uid, context['report_id'], {'state': 'error', 'error': str(e)})
            raise
        finally:
            if context.get('progress_id'):
                self.pool.get('export.report.stock.move.progress').unlink(new_cr, uid, [context['progress_id']])
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

