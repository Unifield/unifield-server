# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2020 TeMPO Consulting, MSF
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


class fo_follow_up_finance_wizard(osv.osv_memory):
    _name = 'fo.follow.up.finance.wizard'

    _columns = {
        'start_date': fields.date(string='Start date'),
        'end_date': fields.date(string='End date'),
        'partner_ids': fields.many2many('res.partner', 'fo_follow_up_wizard_partner_rel', 'wizard_id', 'partner_id', 'Partners'),
        'order_id': fields.many2one('sale.order', string='Order Ref.'),
        'order_ids': fields.text(string='Orders', readonly=True),  # don't use many2many to avoid memory usage issue
    }

    def get_values(self, cr, uid, ids, context=None):
        """
        Retrieves the data according to the values in the wizard
        """
        fo_obj = self.pool.get('sale.order')
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for wizard in self.browse(cr, uid, ids, context=context):
            # TODO: change this to SQL
            fo_domain = []
            if wizard.start_date:
                fo_domain.append(('date_order', '>=', wizard.start_date))
            if wizard.end_date:
                fo_domain.append(('date_order', '<=', wizard.end_date))
            if wizard.partner_ids:
                fo_domain.append(('partner_id', 'in', [p.id for p in wizard.partner_ids]))
            if wizard.order_id:
                fo_domain.append(('id', '=', wizard.order_id.id))
            fo_ids = fo_obj.search(cr, uid, fo_domain, context=context)
            if not fo_ids:
                raise osv.except_osv(
                    _('Error'),
                    _('No data found with these parameters'),
                )
            # TODO: refactoring
            cr.execute("""SELECT COUNT(id) FROM sale_order_line WHERE order_id IN %s""", (tuple(fo_ids),))
            nb_lines = 0
            for x in cr.fetchall():
                nb_lines = x[0]
            # maximum number of lines
            # Note: the parameter "FOLLOWUP_MAX_LINE" is also used for the FO Follow-up per client.
            config_line = self.pool.get('ir.config_parameter').get_param(cr, 1, 'FO_FOLLOWUP_MAX_LINE')
            if config_line:
                max_line = int(config_line)
            else:
                max_line = 5000
            if nb_lines > max_line:
                raise osv.except_osv(_('Error'), _('The requested report is too heavy to generate: requested %d lines, '
                                                   'maximum allowed %d. Please apply further filters so that report can be generated.') %
                                     (nb_lines, max_line))
            self.write(cr, uid, [wizard.id], {'order_ids': fo_ids}, context=context)
        return True

    def print_excel(self, cr, uid, ids, context=None):
        """
        Prints the report in Excel format.
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.get_values(cr, uid, ids, context=context)
        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': 'FO Follow-up Finance',
            'report_name': 'fo.follow.up.finance',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        data = {}
        wiz = self.browse(cr, uid, ids[0], context=context)
        data['form'] = {'start_date': wiz.start_date or False,
                        'end_date': wiz.end_date or False,
                        'partner_ids': wiz.partner_ids or [],
                        'order_id': wiz.order_id or False,
                       }
        data['context'] = context
        # data = {'ids': ids, 'context': context}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'fo.follow.up.finance',
            'datas': data,
            'context': context,
        }


fo_follow_up_finance_wizard()
