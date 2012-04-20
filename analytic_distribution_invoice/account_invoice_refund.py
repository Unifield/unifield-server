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

account_invoice_refund()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
