# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2015 TeMPO Consulting, MSF.
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

import datetime
import time

from osv import osv
from osv import fields


class unconsistent_stock_report(osv.osv):
    _name = 'unconsistent.stock.report'

    _columns = {
        'name': fields.datetime(
            string='Name',
        ),
        'line_ids': fields.one2many(
            'unconsistent.stock.report.line',
            'report_id',
            string='Lines',
        ),
    }

    _defaults = {
        'name': lambda *a: time.strftime('%Y-%m-%d'),
    }

    def _get_unconsistent_prodlots(self, cr, uid, bm='f', perishable='f', context=None):
        """
        Returns a list of ID of stock.production.lot that aren't consistent
        :param cr: Cursor to the database
        :param uid: ID of the user that calls the method
        :param bm: Batch management value of the product
        :param perishable: Perishable value of the product
        :param context: Context of the call
        :return: A dictionnary with values to create unconsistent_stock_report_line
        """
        if bm == 't':
            extra_where = 'AND spl.type = \'internal\''
        elif perishable == 't':
            extra_where = 'AND spl.type != \'internal\''
        else:
            extra_where = 'AND srp.prodlot_id IS NOT NULL'

        request = '''
            SELECT
                srp.product_id AS product_id,
                srp.prodlot_id AS prodlot_id,
                spl.life_date AS expiry_date,
                SUM(srp.qty) AS quantity,
                srp.location_id AS location_id
            FROM
                stock_report_prodlots srp
              LEFT JOIN
                product_product pp
              ON pp.id = srp.product_id
              LEFT JOIN
                stock_production_lot spl
              ON spl.id = srp.prodlot_id
              LEFT JOIN
                stock_location sl
              ON sl.id = srp.location_id
            WHERE
                pp.batch_management = %%s
                AND
                pp.perishable = %%s
                AND
                sl.usage = 'internal'
                %s
            GROUP BY
                srp.prodlot_id, srp.location_id, srp.product_id, spl.life_date
        ''' % extra_where  # not_a_user_entry
        cr.execute(request, (bm, perishable))

        for r in cr.dictfetchall():
            if r['quantity'] > 0.00:
                yield r

        return

    def _get_unconsistent_non_managed_stock(self, cr, uid, context=None):
        """
        Search the list of production lots in stock that are unconsistent
        :param cr: Cursor to the database
        :param uid: ID of the user that calls the method
        :param bm: Batch management value of the product
        :param perishable: Perishable value of the product
        :param context: Context of the call
        :return: A dictionnary with values to create unconsistent_stock_report_line
        """
        request = '''
            SELECT
                rsi.product_id AS product_id,
                NULL AS prodlot_id,
                NULL AS expiry_date,
                SUM(rsi.product_qty) AS quantity,
                rsi.location_id AS location_id
            FROM
                report_stock_inventory rsi
              LEFT JOIN
                product_product pp
              ON pp.id = rsi.product_id
            WHERE
                pp.perishable = 't'
                AND
                rsi.location_type = 'internal'
                AND
                rsi.state = 'done'
                AND
                rsi.prodlot_id IS NULL
            GROUP BY
                rsi.prodlot_id, rsi.location_id, rsi.product_id, expiry_date
        '''
        cr.execute(request)

        for r in cr.dictfetchall():
            if r['quantity'] > 0.00:
                yield r

        return

    def _get_unconsistent_moves(self, cr, uid, bm='f', perishable='t', context=None):
        """
        Search the stock.move that aren't not consistent with product parameters
        :param cr: Cursor to the database
        :param uid: ID of the user that calls the method
        :param context: Context of the call
        :return: A dictionnary with values to create unconsistent_stock_report_line
        """
        if bm == 't':
            extra_where = ' AND (sm.prodlot_id IS NULL OR spl.type = \'internal\')'
        elif perishable == 't':
            extra_where = ' AND (sm.prodlot_id IS NULL OR spl.type != \'internal\')'
        else:
            extra_where = ' AND sm.prodlot_id IS NOT NULL'

        request = '''
            SELECT
                sm.product_id AS product_id,
                sm.product_qty AS quantity,
                sm.prodlot_id AS prodlot_id,
                sm.expired_date AS expiry_date,
                sm.location_id AS location_id,
                CASE
                    WHEN sp.subtype = 'packing' AND sp.backorder_id IS NOT NULL
                    THEN ship.name
                    ELSE sp.name
                END AS document_number
            FROM
                stock_move sm
              LEFT JOIN
                product_product pp
              ON pp.id = sm.product_id
              LEFT JOIN
                stock_production_lot spl
              ON spl.id = sm.prodlot_id
              LEFT JOIN
                stock_picking sp
              ON sp.id = sm.picking_id
              LEFT JOIN
                shipment ship
              ON ship.id = sp.shipment_id
            WHERE
                sm.kit_creation_id_stock_move IS NULL
              AND
                sm.state NOT IN ('cancel', 'done')
              AND
                sm.picking_id IS NOT NULL
              AND
                sp.type != 'in'
              AND
                (
                    (sp.subtype = 'packing' AND sp.state IN ('draft', 'assigned'))
                  OR
                    (sp.subtype != 'packing' AND sp.state NOT IN ('cancel', 'done') AND sm.state = 'assigned')
                )
              AND
                pp.batch_management = %%s
              AND
                pp.perishable = %%s
                %s
        ''' % extra_where  # not_a_user_entry
        cr.execute(request, (bm, perishable))

        for r in cr.dictfetchall():
            if r['quantity'] > 0.00:
                yield r

        return

    def _get_unconsistent_upil(self, cr, uid, model='stock_inventory', context=None):
        """
        Search the list of stock.inventory.line that are unconsistent with product parameters
        :param cr: Cursor to the database
        :param uid: ID of the user that calls the method
        :param context: Context of the call
        :return: A dictionnary with values to create unconsistent_stock_report_line
        """
        if model == 'stock_inventory':
            name = 'Phy. Inv.'
        else:
            name = 'Ini. Stock'

        request = '''
            SELECT
                sil.product_id AS product_id,
                sil.prod_lot_id AS prodlot_id,
                sil.expiry_date AS expiry_date,
                SUM(sil.product_qty) AS quantity,
                '%s ' || si.name AS document_number,
                sil.location_id AS location_id
            FROM
                %s_line sil
              LEFT JOIN
                %s si
              ON si.id = sil.inventory_id
              LEFT JOIN
                product_product pp
              ON pp.id = sil.product_id
              LEFT JOIN
                stock_location sl
              ON sl.id = sil.location_id
              LEFT JOIN
                stock_production_lot spl
              ON spl.id = sil.prod_lot_id
            WHERE
                sl.usage = 'internal'
                AND
                si.state NOT IN ('draft', 'done', 'cancel')
                AND
                (
                    (pp.perishable AND NOT pp.batch_management AND (sil.expiry_date IS NULL OR spl.type != 'internal'))
                    OR
                    (pp.batch_management AND (sil.prod_lot_id IS NULL OR spl.type = 'internal'))
                    OR
                    (
                        NOT (pp.batch_management OR pp.perishable)
                        AND
                        (
                            sil.prod_lot_id IS NOT NULL
                            OR
                            sil.expiry_date IS NOT NULL
                        )
                    )
                )
            GROUP BY
                sil.product_id, sil.prod_lot_id, sil.expiry_date, sil.location_id, document_number
        ''' % (name, model, model)  # not_a_user_entry
        cr.execute(request)

        for r in cr.dictfetchall():
            if r['quantity'] > 0.00:
                yield r

        return

    def _get_unconsistent_ucrl(self, cr, uid, context=None):
        """
        Search the list of real.average.consumption.line that are unconsistent with product parameters
        :param cr: Cursor to the database
        :param uid: ID of the user that calls the method
        :param context: Context of the call
        :return: A dictionnary with values to create unconsistent_stock_report_line
        """
        request = '''
            SELECT
                racl.product_id AS product_id,
                racl.prodlot_id AS prodlot_id,
                racl.expiry_date AS expiry_date,
                SUM(racl.product_qty) AS quantity,
                'Cons. report ' || rac.name AS document_number,
                rac.cons_location_id AS location_id
            FROM
                real_average_consumption_line racl
              LEFT JOIN
                real_average_consumption rac
              ON rac.id = racl.rac_id
              LEFT JOIN
                product_product pp
              ON pp.id = racl.product_id
              LEFT JOIN
                stock_location sl
              ON sl.id = rac.cons_location_id
              LEFT JOIN
                stock_production_lot spl
              ON spl.id = racl.prodlot_id
            WHERE
                sl.usage = 'internal'
                AND
                rac.state NOT IN ('done', 'cancel')
                AND
                (
                    (pp.perishable AND not pp.batch_management AND (racl.expiry_date IS NULL OR spl.type != 'internal'))
                    OR
                    (pp.batch_management AND (racl.prodlot_id IS NULL OR spl.type = 'internal'))
                    OR
                    (
                        NOT (pp.batch_management OR pp.perishable)
                        AND
                        (
                            racl.prodlot_id IS NOT NULL
                            OR
                            racl.expiry_date IS NOT NULL
                        )
                    )
                )
            GROUP BY
                racl.product_id, racl.prodlot_id, racl.expiry_date, rac.cons_location_id, document_number
        '''
        cr.execute(request)

        for r in cr.dictfetchall():
            if r['quantity'] > 0.00:
                yield r

        return

    def _get_unconsistent_ukol(self, cr, uid, context=None):
        """
        Search the list of stock.move that are unconsistent with product parameters
        :param cr: Cursor to the database
        :param uid: ID of the user that calls the method
        :param context: Context of the call
        :return: A dictionnary with values to create unconsistent_stock_report_line
        """
        request = '''
            SELECT
                sm.product_id AS product_id,
                sm.prodlot_id AS prodlot_id,
                sm.expired_date AS expiry_date,
                SUM(sm.product_qty) AS quantity,
                'Kitting Order ' || ko.name AS document_number,
                sm.location_id AS location_id
            FROM
                stock_move sm
              LEFT JOIN
                kit_creation ko
              ON ko.id = sm.kit_creation_id_stock_move
              LEFT JOIN
                product_product pp
              ON pp.id = sm.product_id
              LEFT JOIN
                stock_location sl
              ON sl.id = sm.location_id
              LEFT JOIN
                stock_production_lot spl
              ON spl.id = sm.prodlot_id
            WHERE
                sl.usage = 'internal'
                AND
                ko.state NOT IN ('done', 'cancel')
                AND
                (
                    (pp.perishable AND NOT pp.batch_management AND (sm.expired_date IS NULL OR spl.type != 'internal'))
                    OR
                    (pp.batch_management AND (sm.prodlot_id IS NULL OR spl.type = 'internal'))
                    OR
                    (
                        NOT (pp.batch_management OR pp.perishable)
                        AND
                        (
                            sm.prodlot_id IS NOT NULL
                            OR
                            sm.expired_date IS NOT NULL
                        )
                    )
                )
            GROUP BY
                sm.product_id, sm.prodlot_id, sm.expired_date, sm.location_id, document_number
        '''
        cr.execute(request)

        for r in cr.dictfetchall():
            if r['quantity'] > 0.00:
                yield r

        return

    def _get_unconsistent_ucsm(self, cr, uid, context=None):
        """
        Search the list of claim.stock.move that are unconsistent with product parameters
        :param cr: Cursor to the database
        :param uid: ID of the user that calls the method
        :param context: Context of the call
        :return: A dictionnary with values to create unconsistent_stock_report_line
        """
        request = '''
            SELECT
                cpl.product_id_claim_product_line AS product_id,
                cpl.lot_id_claim_product_line AS prodlot_id,
                cpl.expiry_date_claim_product_line AS expiry_date,
                SUM(cpl.qty_claim_product_line) AS quantity,
                'Claim ' || rc.name AS document_number
            FROM
                claim_product_line cpl
              LEFT JOIN
                return_claim rc
              ON rc.id = cpl.claim_id_claim_product_line
              LEFT JOIN
                product_product pp
              ON pp.id = cpl.product_id_claim_product_line
              LEFT JOIN
                stock_production_lot spl
              ON spl.id = cpl.lot_id_claim_product_line
            WHERE
                (
                    (pp.perishable AND NOT pp.batch_management AND (cpl.expiry_date_claim_product_line IS NULL OR spl.type != 'internal'))
                    OR
                    (pp.batch_management AND (cpl.lot_id_claim_product_line IS NULL OR spl.type = 'internal'))
                    OR
                    (pp.batch_management IS NULL AND cpl.lot_id_claim_product_line IS NOT NULL)
                    OR
                    (pp.perishable IS NULL AND cpl.expiry_date_claim_product_line IS NOT NULL)
                )
            GROUP BY
                cpl.product_id_claim_product_line, cpl.lot_id_claim_product_line, cpl.expiry_date_claim_product_line, document_number
        '''
        cr.execute(request)

        for r in cr.dictfetchall():
            if r['quantity'] > 0.00:
                yield r

        return

    def generate_report(self, cr, uid, ids, context=None):
        """
        Generate the report. Call the different methods to find unconsistent data and put them in the report.
        :param cr: Cursor to the database
        :param uid: ID of the user that calls the method
        :param context: Context of the call
        :return: The ID of the new report
        """
        usrl_obj = self.pool.get('unconsistent.stock.report.line')

        if context is None:
            context = {}

        # Remove last report
        #self.unlink(cr, uid, self.search(cr, uid, [], context=context), context=context)

        def create_usrl(vals):
            vals['report_id'] = ids[0]
            usrl_obj.create(cr, uid, vals, context=context)

        # UN-CONSISTENT PRODLOTS
        # Get the un-consistent stock for non tracked products
        for ulot in self._get_unconsistent_prodlots(cr, uid, bm='f', perishable='f', context=context):
            create_usrl(ulot)

        # Get the un-consistent stock for products that are now ED/BM but without batch
        for ulot in self._get_unconsistent_non_managed_stock(cr, uid, context=context):
            create_usrl(ulot)

        # Get the un-consistent stock for ED products
        for ulot in self._get_unconsistent_prodlots(cr, uid, bm='f', perishable='t', context=context):
            create_usrl(ulot)

        # Get the un-consistent stock for batch managed products
        for ulot in self._get_unconsistent_prodlots(cr, uid, bm='t', perishable='t', context=context):
            create_usrl(ulot)

        # UN-CONSISTENT STOCK MOVES
        # Get the un-consistent stock moves for non tracked products
        for usm in self._get_unconsistent_moves(cr, uid, bm='f', perishable='f', context=context):
            create_usrl(usm)

        # Get the un-consistent stock moves for ED products
        for usm in self._get_unconsistent_moves(cr, uid, bm='f', perishable='t', context=context):
            create_usrl(usm)

        # Get the un-consistent stock moves for batch managed products
        for usm in self._get_unconsistent_moves(cr, uid, bm='t', perishable='t', context=context):
            create_usrl(usm)

        # Get the un-consistent physical inventory lines
        for upil in self._get_unconsistent_upil(cr, uid, model='stock_inventory', context=context):
            create_usrl(upil)

        # Get the un-consistent initial stock inventory lines
        for upil in self._get_unconsistent_upil(cr, uid, model='initial_stock_inventory', context=context):
            create_usrl(upil)

        # Get the un-consistent consumption report lines
        for ucrl in self._get_unconsistent_ucrl(cr, uid, context=context):
            create_usrl(ucrl)

        # Get the un-consistent kitting order lines
        for ukol in self._get_unconsistent_ukol(cr, uid, context=context):
            create_usrl(ukol)

        # Get the un-consistent claim moves
        for ucsm in self._get_unconsistent_ucsm(cr, uid, context=context):
            create_usrl(ucsm)

        '''
        Retrieve the data and print the report in Excel format.
        '''
        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': 'Unconsistent stock report',
            'report_name': 'unconsistent.stock.report_xls',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 20

        company = self.pool.get('res.users').browse(cr, uid, uid).company_id
        if company and company.instance_id:
            instance_code = ' ' + company.instance_id.instance
        else:
            instance_code = ''
        current_date = datetime.datetime.today().strftime('%Y_%m_%d_%H_%M')
        filename = 'Unconsistent stock report %s %s' % (instance_code, current_date)
        data = {'ids': ids, 'context': context, 'target_filename': filename}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'unconsistent.stock.report_xls',
            'datas': data,
            'context': context,
        }

    def delete_unused_lines(self, cr, uid, ids, context=None):
        """
        Remove the unconsistent.stock.report.line and unconsistent.stock.report
        with age larger than 2 days.
        """
        if not ids:
            ids = []

        max_age = datetime.datetime.now() - datetime.timedelta(days=2)
        report_ids = self.search(cr, uid, [
            ('name', '<', max_age.strftime('%Y-%m-%d %H:%M:%S')),
        ], context=context)

        self.unlink(cr, uid, report_ids, context=context)

        return True

unconsistent_stock_report()


class unconsistent_stock_report_line(osv.osv):
    _name = 'unconsistent.stock.report.line'
    _order = 'report_id, product_code, prodlot_id, location_name, document_number desc'

    _columns = {
        'report_id': fields.many2one(
            'unconsistent.stock.report',
            string='Report',
            required=True,
            ondelete='cascade',
            select=1,
        ),
        'product_id': fields.many2one(
            'product.product',
            string='Product',
            required=True,
            ondelete='cascade',
        ),
        'product_code': fields.related(
            'product_id',
            'default_code',
            string='Product Code',
            type='char',
            size=128,
            readonly=True,
            store=True,
        ),
        'product_name': fields.related(
            'product_id',
            'name',
            string='Product Name',
            type='char',
            size=512,
            readonly=True,
            store=True,
        ),
        'product_bn': fields.related(
            'product_id',
            'batch_management',
            string='BN management',
            type='boolean',
            readonly=True,
            store=True,
        ),
        'product_ed': fields.related(
            'product_id',
            'perishable',
            string='ED management',
            type='boolean',
            readonly=True,
            store=True,
        ),
        'prodlot_id': fields.many2one(
            'stock.production.lot',
            string='BN',
            readonly=True,
            ondelete='cascade',
        ),
        'prodlot_name': fields.related(
            'prodlot_id',
            'name',
            string='BN',
            type='char',
            size=64,
            readonly=True,
            store=True,
        ),
        'expiry_date': fields.related(
            'prodlot_id',
            'life_date',
            type='date',
            string='ED',
            readonly=True,
            store=True,
        ),
        'quantity': fields.float(
            digits=(16,2),
            string='Qty',
            readonly=True,
        ),
        'location_id': fields.many2one(
            'stock.location',
            string='Location',
            readonly=True,
            ondelete='cascade',
        ),
        'location_name': fields.related(
            'location_id',
            'name',
            type='char',
            size=128,
            string='Location',
            readonly=True,
            store=True,
        ),
        'document_number': fields.char(
            size=128,
            string='Document name',
            readonly=True,
        )
    }

unconsistent_stock_report_line()
