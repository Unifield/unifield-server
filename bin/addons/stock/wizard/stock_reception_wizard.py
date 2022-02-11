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
    ('donation_exp', _('Donation before expiry')),
    ('donation_st', _('Standard donation')),
    ('loan', _('Loan')),
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
        'reason_type_id': fields.many2one('stock.reason.type', string='Reason type'),
        'partner_id': fields.many2one('res.partner', string='Partner', help="The partner you want have the IN data"),
        'order_category': fields.selection(ORDER_CATEGORY, string='Order Category'),
        'order_type': fields.selection(ORDER_TYPES_SELECTION, string='Order Type'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Product Main Type'),
        'location_dest_id': fields.many2one('stock.location', 'Reception Destination', select=True,
                                            help="Location where the system will stock the finished products."),
        'final_dest_id': fields.many2one('stock.location', 'Final Dest. Location', select=True,
                                          help="Location where the stock will be at the end of the flow."),
        'final_partner_id': fields.many2one('res.partner', 'Final Dest. Partner', select=True,
                                             help="Partner where the stock will be at at the end of the flow."),
    }

    _defaults = {
        'report_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self, cr, uid, ids, c={}: self.pool.get('res.users').browse(cr, uid, uid).company_id.id,
    }

    def get_values(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        '''
        move_obj = self.pool.get('stock.move')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        model_obj = self.pool.get('ir.model.data')
        cross_docking_id = model_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        for wizard in self.browse(cr, uid, ids, context=context):
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
                sql_cond['start_date'] = wizard.end_date

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
                # TODO
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
                sql_append.append('tmpl.nomen_manda_0 = %(lnomen_manda_0)s')
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
                        p.type = 'in' and
                        '''
                    if sql_append:
                        sql = '%s and %s' % (sql, ' and '.join(sql_append))
                    sql = '%s order by m.id' % (sql, )
                    sql_cond.update({'final_dest': f_dest_id.id, 'cross_doc': cross_docking_id})
                    print cr.mogrify(sql, sql_cond)
                    cr.execute(sql, sql_cond)
                    move_ids = [x[0] for x in cr.fetchall()] # TODO
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
                    ) as sql
                    order by id''' % (sql1, sql2)
                    sql_cond.update({'final_dest': f_dest_id.id, 'cross_doc': cross_docking_id})
                    print cr.mogrify(sql, sql_cond)
                    cr.execute(sql, sql_cond)
                    move_ids = [x[0] for x in cr.fetchall()] # TODO


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
                        (so.id is null or so.procurement_request)
                    '''
                    if sql_append:
                        sql = '%s and %s' % (sql, ' and '.join(sql_append))
                    sql = '%s order by m.id' % (sql, )
                    sql_cond.update({'customer_name': wizard.final_partner_id.name})
                    print cr.mogrify(sql, sql_cond)
                    cr.execute(sql, sql_cond)
                    move_ids = [x[0] for x in cr.fetchall()] # TODO
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
                        p.type = 'in'
                    '''
                    if sql_append:
                        sql = '%s and %s' % (sql, ' and '.join(sql_append))
                    sql = '%s order by m.id' % (sql, )
                    sql_cond.update({'customer_id': wizard.final_partner_id.id})
                    print cr.mogrify(sql, sql_cond)
                    cr.execute(sql, sql_cond)
                    move_ids = [x[0] for x in cr.fetchall()] # TODO



            else:
                move_ids = move_obj.search(cr, uid, move_domain, order='id', context=context)

            print len(move_ids)
            if not move_ids:
                raise osv.except_osv(
                    _('Error'),
                    _('No data found with these parameters'),
                )

            self.write(cr, uid, [wizard.id], {'moves_ids': move_ids}, context=context)

        return True

    def print_excel(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        and print the report in Excel format.
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        self.get_values(cr, uid, ids, context=context)

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
