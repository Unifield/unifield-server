#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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
import time

class analytic_distribution_wizard(osv.osv_memory):
    _inherit = 'analytic.distribution.wizard'

    _columns = {
        'date': fields.date(string="Date", help="This date is taken from analytic distribution corrections"),
        'state': fields.selection([('draft', 'Draft'), ('cc', 'Cost Center only'), ('dispatch', 'All other elements'), ('done', 'Done'), 
            ('correction', 'Correction')], string="State", required=True, readonly=True),
    }

    _defaults = {
        'state': lambda *a: 'draft',
        'date': lambda *a: time.strftime('%Y-%m-%d'),
    }

    def button_cancel(self, cr, uid, ids, context={}):
        """
        Close wizard and return on another wizard if 'from' and 'wiz_id' are in context
        """
        # Some verifications
        if not context:
            context = {}
        if 'from' in context and 'wiz_id' in context:
            wizard_name = context.get('from')
            wizard_id = context.get('wiz_id')
            return {
                'type': 'ir.actions.act_window',
                'res_model': wizard_name,
                'target': 'new',
                'view_mode': 'form,tree',
                'view_type': 'form',
                'res_id': wizard_id,
                'context': context,
            }
        return super(analytic_distribution_wizard, self).button_cancel(cr, uid, ids, context=context)

    def button_confirm(self, cr, uid, ids, context={}):
        """
        Change wizard state in order to use normal method
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Change wizard state if current is 'correction'
        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.state == 'correction':
                self.write(cr, uid, ids, {'state': 'dispatch'}, context=context)
        # Get default method
        res = super(analytic_distribution_wizard, self).button_confirm(cr, uid, ids, context=context)
        if 'from' in context and 'wiz_id' in context:
            for wiz in self.browse(cr, uid, ids, context=context):
                distrib = wiz.distribution_id
                # update date and source date for all distribution lines
                for el in ['cost_center_lines', 'funding_pool_lines', 'free_1_lines', 'free_2_lines']:
                    for line in getattr(distrib, el):
                        self.pool.get(line._name).write(cr, uid, [line.id], {'date': wiz.date, 'source_date': wiz.date}, context=context)
                # update analytic lines
                self.update_analytic_lines(cr, uid, ids, context=context)
        return res

analytic_distribution_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
