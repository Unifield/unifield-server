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


class sale_followup_multi_wizard(osv.osv_memory):
    _name = 'sale.followup.multi.wizard'
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
        'partner_id': fields.many2one(
            'res.partner',
            string='Partner',
            help="The partner you want have the FO",
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
        'order_ids': fields.text(
            string='Orders',
            readonly=True
        ),
        #'order_ids': fields.many2many(
        #    'sale.order',
        #    'followup_per_client_rel',
        #    'report_id',
        #    'order_id',
        #    string='Orders',
        #),
        'order_id': fields.many2one(
            'sale.order',
            string='Order Ref.',
        ),
        'draft_ok': fields.boolean(
            string='Draft',
        ),
        'validated_ok': fields.boolean(
            string='Validated',
        ),
        'sourced_ok': fields.boolean(
            string='Sourced',
        ),
        'confirmed_ok': fields.boolean(
            string='Confirmed',
        ),
        'closed_ok': fields.boolean(
            string='Closed',
        ),
        'cancel_ok': fields.boolean(
            string='Cancelled',
        ),
        'only_bo': fields.boolean(
            string='Pending order lines only (PDF)',
        ),
        'include_notes_ok': fields.boolean(
            string='Include order lines note (PDF)',
        )
    }

    _defaults = {
        'report_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self, cr, uid, ids, c={}: self.pool.get('res.users').browse(cr, uid, uid).company_id.id,
        'only_bo': lambda *a: False,
    }

    def _get_state_domain(self, wizard):
        '''
        Return a list of states on which the FO should be filtered

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

    def _check_max_line_number(self, cr, fo_ids):
        """
        Blocks report generation with an error message in case there are too many FO lines to handle.
        """
        cr.execute("""SELECT COUNT(id) FROM sale_order_line WHERE order_id IN %s""", (tuple(fo_ids),))
        nb_lines = 0
        for x in cr.fetchall():
            nb_lines = x[0]
        # Parameter to define the maximum number of lines. For a custom number:
        # "INSERT INTO ir_config_parameter (key, value) VALUES ('FO_FOLLOWUP_MAX_LINE', 'chosen_number');"
        # Or update the existing one
        config_line = self.pool.get('ir.config_parameter').get_param(cr, 1, 'FO_FOLLOWUP_MAX_LINE')
        if config_line:
            max_line = int(config_line)
        else:
            max_line = 5000
        if nb_lines > max_line:
            raise osv.except_osv(_('Error'), _('The requested report is too heavy to generate: requested %d lines, maximum allowed %d. '
                                               'Please apply further filters so that report can be generated.') % (nb_lines, max_line))

    def get_values(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        '''
        fo_obj = self.pool.get('sale.order')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for wizard in self.browse(cr, uid, ids, context=context):
            if wizard.order_id:
                fo_ids = [wizard.order_id.id]
            else:
                fo_domain = []
                state_domain = self._get_state_domain(wizard)

                if wizard.partner_id:
                    fo_domain.append(('partner_id', '=', wizard.partner_id.id))

                if wizard.start_date:
                    fo_domain.append(('date_order', '>=', wizard.start_date))

                if wizard.end_date:
                    fo_domain.append(('date_order', '<=', wizard.end_date))

                if state_domain:
                    fo_domain.append(('state', 'in', tuple(state_domain)))

                fo_ids = fo_obj.search(cr, uid, fo_domain, context=context)

                if not fo_ids:
                    raise osv.except_osv(
                        _('Error'),
                        _('No data found with these parameters'),
                    )

                self._check_max_line_number(cr, fo_ids)

            self.write(cr, uid, [wizard.id], {'order_ids': fo_ids}, context=context)

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
            'file_name': 'FO followup',
            'report_name': 'sales.follow.up.multi.report_xls',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        data = {'ids': ids, 'context': context}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'sales.follow.up.multi.report_xls',
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

        if isinstance(ids, (int, long)):
            ids = [ids]

        self.get_values(cr, uid, ids, context=context)

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': 'FO followup',
            'report_name': 'sales.follow.up.multi.report_pdf',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        data = {'ids': ids, 'context': context}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'sales.follow.up.multi.report_pdf',
            'datas': data,
            'context': context,
        }

    def partner_onchange(self, cr, uid, ids, partner_id=False, order_id=False):
        '''
        If the partner is changed, check if the order is to this partner
        '''
        so_obj = self.pool.get('sale.order')

        res = {}

        if partner_id and order_id:
            so_ids = so_obj.search(cr, uid, [
                ('id', '=', order_id),
                ('partner_id', '=', partner_id),
            ], count=True)
            if not so_ids:
                res['value'] = {'order_id': False}
                res['warning'] = {
                    'title': _('Warning'),
                    'message': _('The partner of the selected order doesn\'t \
match with the selected partner. The selected order has been reset'),
                }

        return res

sale_followup_multi_wizard()
