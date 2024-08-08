# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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
from tools.translate import _
from order_types import ORDER_CATEGORY

import time

ORDER_TYPES_SELECTION = [
    ('regular', _('Regular')),
    ('donation_exp', _('Donation to prevent losses')),
    ('donation_st', _('Standard donation')),
    ('loan', _('Loan')),
    ('loan_return', _('Loan Return')),
    ('in_kind', _('In Kind Donation')),
    ('purchase_list', _('Purchase List')),
    ('direct', _('Direct Purchase Order')),
]


class stock_reception_wizard(osv.osv_memory):
    _name = 'stock.reception.wizard'
    _rec_name = 'report_date'

    _columns = {
        'report_date': fields.datetime(string='Date of the demand', readonly=True),
        'company_id': fields.many2one('res.company', string='Company', readonly=True),
        'moves_ids': fields.text(string='Moves', readonly=True),
        'start_date': fields.date(string='Actual Receipt Date from'),
        'end_date': fields.date(string='Actual Receipt Date to'),
        'nb': fields.integer('number of moves'),
        'reason_type_id': fields.many2one('stock.reason.type', string='Reason type'),
        'partner_id': fields.many2one('res.partner', string='Partner', help="The partner you want have the IN data"),
        'order_category': fields.selection(ORDER_CATEGORY, string='Order Category'),
        'order_type': fields.selection(ORDER_TYPES_SELECTION, string='Order Type'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Product Main Type'),
        'location_dest_id': fields.many2one('stock.location', 'Reception Destination', select=True,
                                            help="Location where the system will stock the finished products.", domain=['|', '|', '|', '|', ('usage', '=', 'internal'), ('service_location', '=', True), ('non_stockable_ok', '=', True), ('cross_docking_location_ok', '=', True), ('virtual_ok', '=', True)]),
        'final_dest_id': fields.many2one('stock.location', 'Final Dest. Location', select=True,
                                         help="Location where the stock will be at the end of the flow.", domain="['&', ('input_ok', '=', False), '&', ('usage', 'in', ['internal', 'customer']), '|', ('location_category', '!=', 'other'), ('usage', '!=', 'customer')]"),
        # remove Other Customer and MSF Customer
        'final_partner_id': fields.many2one('res.partner', 'Final Dest. Partner', select=True,
                                            help="Partner where the stock will be at at the end of the flow.", domain="['|', ('customer', '=', True), ('id', '=', company_id)]"),
    }

    _defaults = {
        'report_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self, cr, uid, ids, c={}: self.pool.get('res.users').browse(cr, uid, uid).company_id.id,
    }

    def onchange_final_dest_id(self, cr, uid, ids, final_dest_id, context=None):
        if context is None:
            context = {}

        res = {}
        if final_dest_id:
            res.update({'value': {'final_partner_id': False}})

        return res

    def onchange_final_partner_id(self, cr, uid, ids, final_partner_id, context=None):
        if context is None:
            context = {}

        res = {}
        if final_partner_id:
            res.update({'value': {'final_dest_id': False}})

        return res

    def get_values(self, cr, uid, _id, min_id=0, max_size=None, count=None, context=None):
        '''
        Retrieve the data according to values in wizard
        '''
        move_obj = self.pool.get('stock.move')

        if context is None:
            context = {}

        model_obj = self.pool.get('ir.model.data')
        cross_docking_id = model_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        loan_rt_id = model_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan')[1]
        loan_ret_rt_id = model_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan_return')[1]

        sql = False
        wizard = self.browse(cr, uid, _id, context=context)
        move_domain = [
            ('type', '=', 'in'),
            ('picking_id.state', '=', 'done'),
            ('state', '=', 'done'),
        ]
        sql_append = []
        sql_cond = {}
        if wizard.start_date:
            move_domain.append(('picking_id.date_done', '>=', wizard.start_date))
            sql_append.append('p.date_done >= %(start_date)s')
            sql_cond['start_date'] = wizard.start_date

        if wizard.end_date:
            move_domain.append(('picking_id.date_done', '<=', wizard.end_date))
            sql_append.append('p.date_done <= %(end_date)s')
            sql_cond['end_date'] = wizard.end_date

        if wizard.reason_type_id:
            move_domain.append(('reason_type_id', '=', wizard.reason_type_id.id))
            sql_append.append('m.reason_type_id = %(reason_type_id)s')
            sql_cond['reason_type_id'] = wizard.reason_type_id.id

        if wizard.partner_id:
            move_domain.append(('picking_id.partner_id', '=', wizard.partner_id.id))
            sql_append.append('p.partner_id = %(partner_id)s')
            sql_cond['partner_id'] = wizard.partner_id.id

        if wizard.order_category:
            move_domain.append(('picking_id.order_category', '=', wizard.order_category))
            sql_append.append('p.order_category = %(order_category)s')
            sql_cond['order_category'] = wizard.order_category

        inner_join_po = ''
        if wizard.order_type:
            move_domain.extend((('purchase_line_id', '!=', False), ('purchase_line_id.order_id.order_type', '=', wizard.order_type)))
            inner_join_po = '''
                inner join purchase_order_line pol on pol.id = m.purchase_line_id
                inner join purchase_order po on po.id = m.purchase_line_id
            '''
            sql_append.append('po.order_type = %(order_type)s')
            sql_cond['order_type'] = wizard.order_type

        inner_join_product = ''
        if wizard.nomen_manda_0:
            move_domain.append(('product_id.nomen_manda_0', '=', wizard.nomen_manda_0.id))
            sql_append.append('tmpl.nomen_manda_0 = %(nomen_manda_0)s')
            sql_cond['nomen_manda_0'] = wizard.nomen_manda_0.id
            inner_join_product = '''
                inner join product_product prod on m.product_id = prod.id
                inner join product_template tmpl on prod.product_tmpl_id = tmpl.id
            '''


        if wizard.location_dest_id:
            move_domain.append(('location_dest_id', '=', wizard.location_dest_id.id))
            sql_append.append('m.location_dest_id = %(location_dest_id)s')
            sql_cond['location_dest_id'] = wizard.location_dest_id.id

        if wizard.final_dest_id:
            f_dest_id = wizard.final_dest_id
            if f_dest_id.usage == 'customer' and f_dest_id.location_category == 'consumption_unit':
                # EXT CU from IR to Cross Dock
                sql = '''select distinct(m.id)
                    from
                        stock_move m
                        inner join stock_picking p on m.picking_id = p.id
                        inner join purchase_order_line pol on m.purchase_line_id = pol.id
                        inner join purchase_order po on pol.order_id = po.id
                        inner join sale_order_line sol on pol.linked_sol_id = sol.id
                        inner join sale_order so on sol.order_id = so.id
                    ''' + inner_join_product + '''
                where
                    m.location_dest_id = %(cross_doc)s and
                    so.location_requestor_id = %(final_dest)s and
                    m.state = 'done' and
                    p.type = 'in'
                    '''
                if sql_append:
                    sql = '%s and %s' % (sql, ' and '.join(sql_append))
                sql_cond.update({'final_dest': f_dest_id.id, 'cross_doc': cross_docking_id})
            elif f_dest_id.cross_docking_location_ok:
                sql = '''select distinct(m.id) as id
                    from
                        stock_move m
                        inner join stock_picking p on m.picking_id = p.id
                    ''' + inner_join_product + '''
                        left join purchase_order_line pol on m.purchase_line_id = pol.id
                        left join purchase_order po on pol.order_id = po.id
                        left join sale_order_line sol on pol.linked_sol_id = sol.id
                        left join sale_order so on so.id = sol.order_id
                        left join stock_location requestor on requestor.id = so.location_requestor_id
                        left join stock_move dest_id on dest_id.id = m.move_dest_id 
                where
                    (
                        m.location_dest_id = %(final_dest)s and (sol.id is null or requestor.usage != 'customer') or
                        dest_id.location_dest_id = %(final_dest)s and dest_id.state = 'done' and (sol.id is null or requestor.usage != 'customer') or
                        requestor.usage = 'customer' and m.location_dest_id != %(final_dest)s and dest_id.state='done' and dest_id.location_dest_id = %(final_dest)s
                    ) and
                    m.state = 'done' and
                    p.type = 'in' 
                '''
                if sql_append:
                    sql = '%s and %s' % (sql, ' and '.join(sql_append))
                sql_cond.update({'final_dest': f_dest_id.id})
            else:
                #elif f_dest_id.usage == 'internal' and f_dest_id.location_category == 'consumption_unit':
                # Internal CU: In FS + IR
                # Internal localation: In FS + IR + PO FS


                # direct location
                sql1 = '''select distinct(m.id) as id
                    from
                        stock_move m
                        inner join stock_picking p on m.picking_id = p.id
                    ''' + inner_join_product + inner_join_po + '''
                where
                    m.location_dest_id = %(final_dest)s and
                    m.state = 'done' and
                    p.type = 'in'
                '''

                # chained location
                sql2 = '''select distinct(m.id) as id
                    from stock_move m
                    inner join stock_picking p on m.picking_id = p.id
                    inner join stock_move int_move on m.move_dest_id = int_move.id
                    ''' + inner_join_product + inner_join_po + '''
                where
                    int_move.location_dest_id = %(final_dest)s and
                    m.picking_id = p.id and
                    m.state = 'done' and
                    p.type = 'in' and
                    int_move.state = 'done'
                '''

                if sql_append:
                    sql1 = '%s and %s' % (sql1, ' and '.join(sql_append))
                    sql2 = '%s and %s' % (sql2, ' and '.join(sql_append))

                sql = '''select distinct(id) from (
                    (%s)
                    UNION
                    (%s)
                ) as m
                where 't' = 't'
                ''' % (sql1, sql2)
                sql_cond.update({'final_dest': f_dest_id.id, 'cross_doc': cross_docking_id})


        elif wizard.final_partner_id:
            if wizard.final_partner_id.id == self.pool.get('res.users').company_get(cr, uid, uid):
                # instance itself : FO is empty or linked to IR
                sql = '''select m.id
                    from
                        stock_move m
                        inner join stock_picking p on m.picking_id = p.id
                ''' + inner_join_product + '''
                        left join purchase_order_line pol on m.purchase_line_id = pol.id
                        left join purchase_order po on po.id = pol.order_id
                        left join sale_order_line sol on pol.linked_sol_id = sol.id
                        left join sale_order so on sol.order_id = so.id
                where
                    m.state = 'done' and
                    p.type = 'in' and
                    (so.id is null or so.procurement_request or m.reason_type_id in %(loan_rt_ids)s)
                '''
                if sql_append:
                    sql = '%s and %s' % (sql, ' and '.join(sql_append))

                # loan added due to the bug fixed by US-6630 (previous data not fixed)
                sql_cond.update({'customer_name': wizard.final_partner_id.name, 'loan_rt_ids': tuple([loan_rt_id, loan_ret_rt_id])})
            else:
                # check fo / exclude loan ? exclude cancel pol
                sql = '''select m.id
                    from
                        stock_move m
                        inner join stock_picking p on m.picking_id = p.id
                        inner join purchase_order_line pol on m.purchase_line_id = pol.id
                        inner join purchase_order po on po.id = pol.order_id
                        inner join sale_order_line sol on pol.linked_sol_id = sol.id
                        inner join sale_order so on sol.order_id = so.id
                ''' + inner_join_product + '''
                where
                    so.partner_id = %(customer_id)s and
                    m.state = 'done' and
                    p.type = 'in' and
                    m.reason_type_id not in %(loan_rt_ids)s
                '''
                if sql_append:
                    sql = '%s and %s' % (sql, ' and '.join(sql_append))
                sql_cond.update({'customer_id': wizard.final_partner_id.id, 'loan_rt_ids': tuple([loan_rt_id, loan_ret_rt_id])})


        if sql:
            if max_size:
                sql ='%s and m.id>%s order by m.id limit %d' % (sql, min_id, max_size)
            cr.execute(sql, sql_cond)
            if count:
                return cr.rowcount
            return [x[0] for x in cr.fetchall()]
        else:
            if max_size:
                move_domain.append(('id', '>', min_id))
            if count:
                return move_obj.search(cr, uid, move_domain, count=True, context=context)
            return move_obj.search(cr, uid, move_domain, order='id', limit=max_size, context=context)

        return []

    def print_excel(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        and print the report in Excel format.
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        temp_ids = self.get_values(cr, uid, ids[0], min_id=0, max_size=None, count=True, context=context)
        if not temp_ids:
            raise osv.except_osv(
                _('Error'),
                _('No data found with these parameters'),
            )

        self.write(cr, uid, ids[0], {'nb': temp_ids}, context=context)
        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': _('Receptions Report'),
            'report_name': 'stock.reception.report_xls',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        data = {'ids': ids, 'context': context}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'stock.reception.report_xls',
            'datas': data,
            'context': context,
        }


stock_reception_wizard()
