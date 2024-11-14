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

import time


class ir_followup_location_wizard(osv.osv_memory):
    _name = 'ir.followup.location.wizard'
    _rec_name = 'report_date'
    _order = 'report_date desc'

    _columns = {
        'report_date': fields.datetime(
            string='Date of the demand',
            readonly=True,
        ),
        'company_id': fields.many2one(
            'res.company',
            string='Company',
            readonly=True,
        ),
        'start_date': fields.date(
            string='Start date',
        ),
        'end_date': fields.date(
            string='End date',
        ),
        'state': fields.selection(
            selection=[
                ('draft', 'Draft'),
                ('in_progress', 'In Progress'),
                ('done', 'Done'),
            ],
            string='Status',
            readonly=True,
        ),
        'location_id': fields.many2one(
            'stock.location',
            string='Location',
            help="The requested Internal Location",
        ),
        'order_ids': fields.text(string='Orders', readonly=True),
        'order_id': fields.many2one('sale.order', string='Order Ref.'),
        # States
        'draft_ok': fields.boolean(string='Draft'),
        'validated_ok': fields.boolean(string='Validated'),
        'sourced_ok': fields.boolean(string='Sourced'),
        'confirmed_ok': fields.boolean(string='Confirmed'),
        'closed_ok': fields.boolean(string='Closed'),
        'cancel_ok': fields.boolean(string='Cancelled'),
        # Categories
        'medical_ok': fields.boolean(string='Medical'),
        'logistic_ok': fields.boolean(string='Logistic'),
        'service_ok': fields.boolean(string='Service'),
        'transport_ok': fields.boolean(string='Transport'),
        'other_ok': fields.boolean(string='Other'),

        'only_bo': fields.boolean(string='Pending order lines only (PDF)'),
        'include_notes_ok': fields.boolean(string='Include order lines note (PDF)'),
        'msl_non_conform': fields.boolean('MSL/MML Non Conforming'),
    }

    _defaults = {
        'report_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self, cr, uid, ids, c={}: self.pool.get('res.users').browse(cr, uid, uid).company_id.id,
        'only_bo': lambda *a: False,
    }

    def get_line_ids_non_msl(self, cr, uid, order_id, context=None):
        sql_param = {
            'instance_id': self.pool.get('res.company')._get_instance_id(cr, uid),
            'order_id' : order_id
        }

        # MML
        cr.execute('''
        select
            sol.id
        from
            sale_order_line sol
            left join sale_order so on so.id = sol.order_id
            left join product_product p on p.id = sol.product_id
            left join product_template tmpl on tmpl.id = p.product_tmpl_id
            left join product_international_status creator on creator.id = p.international_status
            left join product_nomenclature nom on tmpl.nomen_manda_0 = nom.id
            left join product_project_rel p_rel on p.id = p_rel.product_id
            left join product_country_rel c_rel on p_rel is null and c_rel.product_id = p.id
            left join unidata_project up1 on up1.id = p_rel.unidata_project_id or up1.country_id = c_rel.unidata_country_id
        where
            sol.order_id = %(order_id)s
            and nom.name='MED'
            and nom.level = 0
            and creator.code = 'unidata'
            and sol.state not in ('cancel', 'cancel_r')
        group by sol.id
        HAVING
            (
                bool_and(coalesce(oc_validation,'f'))='f'
                or
                not ARRAY[%(instance_id)s]<@array_agg(up1.instance_id)
                and
                count(up1.instance_id)>0
             )
        order by sol.line_number
        ''', sql_param) # not_a_user_entry
        ids = set([x[0] for x in cr.fetchall()])

        cr.execute('''
        select
            sol.id
        from
            sale_order_line sol
            left join sale_order so on so.id = sol.order_id
            left join product_product p on p.id = sol.product_id
            left join product_template tmpl on tmpl.id = p.product_tmpl_id
            left join product_international_status creator on creator.id = p.international_status
            left join product_nomenclature nom on tmpl.nomen_manda_0 = nom.id
            left join unidata_project on unidata_project.instance_id = %(instance_id)s
            left join product_msl_rel msl_rel on msl_rel.product_id = p.id and msl_rel.creation_date is not null and unidata_project.id = msl_rel.msl_id
        where
            sol.order_id = %(order_id)s
            and nom.name='MED'
            and nom.level = 0
            and creator.code = 'unidata'
            and sol.state not in ('cancel', 'cancel_r')
        group by sol.id
        having
            count(unidata_project.uf_active ='t' OR NULL)>0 and count(msl_rel.product_id is NULL or NULL)>0
        ''', sql_param) # not_a_user_entry
        ids.update([x[0] for x in cr.fetchall()])
        return sorted(list(ids))

    def _get_state_domain(self, wizard):
        '''
        Return a list of states on which the IR should be filtered

        :param wizard: A browse_record of the sale.followup.multi.wizard object

        :return: A list of states
        '''
        state_domain = []

        if wizard.draft_ok:
            state_domain.extend(['draft', 'draft_p'])

        if wizard.validated_ok:
            state_domain.extend(['validated', 'validated_p'])

        if wizard.sourced_ok:
            state_domain.extend(['sourced', 'sourced_p'])

        if wizard.confirmed_ok:
            state_domain.extend(['confirmed', 'confirmed_p'])

        if wizard.closed_ok:
            state_domain.append('done')

        if wizard.cancel_ok:
            state_domain.append('cancel')

        return state_domain

    def _get_category_domain(self, wizard):
        '''
        Return a list of categories on which the FO should be filtered
        '''
        category_domain = []

        if wizard.medical_ok:
            category_domain.append('medical')

        if wizard.logistic_ok:
            category_domain.append('logistic')

        if wizard.service_ok:
            category_domain.append('service')

        if wizard.transport_ok:
            category_domain.append('transport')

        if wizard.other_ok:
            category_domain.append('other')

        return category_domain

    def get_values(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        '''
        ir_obj = self.pool.get('sale.order')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        for wizard in self.browse(cr, uid, ids, context=context):
            ir_domain = []
            ir_domain.append(('procurement_request', '=', 't'))

            if wizard.msl_non_conform:
                state_domain = self._get_state_domain(wizard)
                category_domain = self._get_category_domain(wizard)
                sql_param = {'instance_id': self.pool.get('res.company')._get_instance_id(cr, uid)}
                sql_cond = ["nom.name='MED'", "nom.level = 0", "so.procurement_request = 't'", "creator.code = 'unidata'"]
                if wizard.order_id:
                    sql_param['order_id'] = wizard.order_id.id
                    sql_cond.append(' so.id = %(order_id)s ')
                if wizard.location_id:
                    sql_param['location_id'] = wizard.location_id.id
                    sql_cond.append(' so.location_requestor_id = %(location_id)s ')
                if wizard.start_date:
                    sql_param['start_date'] = wizard.start_date
                    sql_cond.append(' so.date_order >= %(start_date)s ')
                if wizard.end_date:
                    sql_param['end_date'] = wizard.end_date
                    sql_cond.append(' so.date_order <= %(end_date)s ')
                if state_domain:
                    sql_param['state'] = tuple(state_domain)
                    sql_cond.append(' so.state in %(state)s ')
                if category_domain:
                    sql_param['categ'] = tuple(category_domain)
                    sql_cond.append(' so.categ in %(categ)s ')

                # MML
                cr.execute('''
                select
                    distinct(sol.order_id)
                from
                    sale_order so
                    left join sale_order_line sol on sol.order_id = so.id and sol.state not in ('cancel', 'cancel_r')
                    left join product_product p on p.id = sol.product_id
                    left join product_template tmpl on tmpl.id = p.product_tmpl_id
                    left join product_international_status creator on creator.id = p.international_status
                    left join product_nomenclature nom on tmpl.nomen_manda_0 = nom.id
                    left join product_project_rel p_rel on p.id = p_rel.product_id
                    left join product_country_rel c_rel on p_rel is null and c_rel.product_id = p.id
                    left join unidata_project up1 on up1.id = p_rel.unidata_project_id or up1.country_id = c_rel.unidata_country_id
                where
                    ''' + ' and '.join(sql_cond) + '''
                group by sol.id
                HAVING
                    (
                        bool_and(coalesce(oc_validation,'f'))='f'
                        or
                        not ARRAY[%(instance_id)s]<@array_agg(up1.instance_id)
                        and
                        count(up1.instance_id)>0
                     )
                ''', sql_param)  # not_a_user_entry
                ir_ids = set([x[0] for x in cr.fetchall()])

                # MSL
                cr.execute('''
                    select
                        so.id
                    from
                    sale_order so
                    left join sale_order_line sol on sol.order_id = so.id and sol.state not in ('cancel', 'cancel_r')
                    left join product_product p on p.id = sol.product_id
                    left join product_template tmpl on tmpl.id = p.product_tmpl_id
                    left join product_international_status creator on creator.id = p.international_status
                    left join product_nomenclature nom on tmpl.nomen_manda_0 = nom.id
                    left join unidata_project on unidata_project.instance_id = %(instance_id)s
                    left join product_msl_rel msl_rel on msl_rel.product_id = p.id and msl_rel.creation_date is not null and unidata_project.id = msl_rel.msl_id
                    where
                        ''' +  ' and '.join(sql_cond) + '''
                    group by so.id
                    having
                    count(unidata_project.uf_active ='t' OR NULL)>0 and count(msl_rel.product_id is NULL or NULL)>0
                ''', sql_param) # not_a_user_entry
                ir_ids.update([x[0] for x in cr.fetchall()])
                ir_ids = sorted(list(ir_ids), reverse=1)

            elif wizard.order_id:
                ir_ids = [wizard.order_id.id]
            else:
                state_domain = self._get_state_domain(wizard)
                category_domain = self._get_category_domain(wizard)

                if wizard.location_id:
                    ir_domain.append(('location_requestor_id', '=', wizard.location_id.id))

                if wizard.start_date:
                    ir_domain.append(('date_order', '>=', wizard.start_date))

                if wizard.end_date:
                    ir_domain.append(('date_order', '<=', wizard.end_date))

                if state_domain:
                    ir_domain.append(('state', 'in', tuple(state_domain)))

                if category_domain:
                    ir_domain.append(('categ', 'in', tuple(category_domain)))

                ir_ids = ir_obj.search(cr, uid, ir_domain, context=context)

                if not ir_ids:
                    raise osv.except_osv(
                        _('Error'),
                        _('No data found with these parameters'),
                    )

            self.write(cr, uid, [wizard.id], {'order_ids': ir_ids}, context=context)

        return True

    def print_excel(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        and print the report in Excel format.
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        self.get_values(cr, uid, ids, context=context)

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': 'IR followup',
            'report_name': 'ir.follow.up.location.report_xls',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        data = {'ids': ids, 'context': context}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'ir.follow.up.location.report_xls',
            'datas': data,
            'context': context,
        }

    def print_pdf(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        and print the report in PDF format
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        self.get_values(cr, uid, ids, context=context)

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': 'IR followup',
            'report_name': 'ir.follow.up.location.report_pdf',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 20

        data = {'ids': ids, 'context': context, 'is_rml': True}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'ir.follow.up.location.report_pdf',
            'datas': data,
            'context': context,
        }

    def onchange(self, cr, uid, ids, location_id=False, order_id=False):
        '''
        If the location is changed, check if the order is to this location
        '''
        so_obj = self.pool.get('sale.order')

        res = {}

        if location_id and order_id:
            so_ids = so_obj.search(cr, uid, [
                ('id', '=', order_id),
                ('location_requestor_id', '=', location_id),
                ('procurement_request', '=', 't'),
            ], count=True)
            if not so_ids:
                res['value'] = {'order_id': False}
                res['warning'] = {
                    'title': _('Warning'),
                    'message': _('The location of the selected order doesn\'t \
                            match with the selected location. The selected order has been reset\n'),
                }

        elif location_id:
            res['domain'] = {'order_id': [('location_requestor_id', '=', location_id), ('procurement_request', '=', 't')]}
        else:
            res['domain'] = {'order_id': [('procurement_request', '=', 't')]}

        return res


ir_followup_location_wizard()
