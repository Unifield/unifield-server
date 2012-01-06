#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

class account_invoice_refund(osv.osv_memory):
    _name = 'account.invoice.refund'
    _inherit = 'account.invoice.refund'

    def _hook_fields_for_modify_refund(self, cr, uid, *args):
        """
        Add analytic_distribution_id field in result
        """
        res = super(account_invoice_refund, self)._hook_fields_for_modify_refund(cr, uid, args)
        res.append('analytic_distribution_id')
        return res

    def _hook_fields_m2o_for_modify_refund(self, cr, uid, *args):
        """
        Add analytic_distribution_id field in result
        """
        res = super(account_invoice_refund, self)._hook_fields_m2o_for_modify_refund(cr, uid, args)
        res.append('analytic_distribution_id')
        return res

#####
## _hook_create_invoice was developed for "SP2, Unifield project, MSF" in order not to generate engagement lines.
## But @ SP3, engagement lines differs. That's why this method is useless @ SP3 and have spawned/generated some modification in 
## analytic_distribution_invoice/invoice.py.
###
#    def _hook_create_invoice(self, cr, uid, data, *args):
#        """
#        Change analytical distribution to have a copy and create invoice without invoice lines then create invoice lines in order not to lose 
#        analytical distribution on each line
#        """
#        if not data:
#            return False
#        # Prepare some values
#        lines = []
#        # Change analytic distribution (make a copy)
#        if data.get('analytic_distribution_id'):
#            data['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid, data['analytic_distribution_id'], 
#                {'global_distribution': True}) or False
#        # Retrieve invoice lines if exists
#        if 'invoice_line' in data:
#            lines = [x[2] for x in data.get('invoice_line')]
#            data['invoice_line'] = False
#        # Create invoice
#        res = self.pool.get('account.invoice').create(cr, uid, data)
#        # Create invoice lines
#        if res and lines:
#            for line in lines:
#                if line.get('new_distribution_id'):
#                    line['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid, line.get('new_distribution_id'), 
#                        {'global_distribution': False}) or False
#                line.update({'invoice_id': res})
#                self.pool.get('account.invoice.line').create(cr, uid, line)
#        return res

account_invoice_refund()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
