#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013 TeMPO Consulting, MSF. All Rights Reserved
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
from tools.translate import _
from time import strftime

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    def _have_been_corrected(self, cr, uid, ids, name, args, context=None):
        """
        Return True if ALL elements are OK:
         - a journal items is linked to this invoice line
         - the journal items is linked to an analytic line that have been reallocated
        """
        if context is None:
            context = {}
        res = {}

        def has_ana_reallocated(move):
            for ml in move.move_lines or []:
                for al in ml.analytic_lines or []:
                    if al.is_reallocated:
                        return True
            return False

        for il in self.browse(cr, uid, ids, context=context):
            res[il.id] = has_ana_reallocated(il)
        return res

    _columns = {
        'is_corrected': fields.function(_have_been_corrected, method=True, string="Have been corrected?", type='boolean', 
            readonly=True, help="This informs system if this item have been corrected in analytic lines. Criteria: the invoice line is linked to a journal items that have analytic item which is reallocated.", 
            store=False),
    }

    _defaults = {
        'is_corrected': lambda *a: False,
    }

    def button_open_analytic_lines(self, cr, uid, ids, context=None):
        """
        Return analytic lines linked to this invoice line.
        First we takes all journal items that are linked to this invoice line.
        Then for all journal items, we take all analytic journal items.
        Finally we display the result for "button_open_analytic_corrections" of analytic lines
        """
        # Some checks
        if not context:
            context = {}
        # Prepare some values
        al_ids = []
        # Browse give invoice lines
        for il in self.browse(cr, uid, ids, context=context):
            if il.move_lines:
                for ml in il.move_lines:
                    if ml.analytic_lines:
                        al_ids += [x.id for x in ml.analytic_lines]
        return self.pool.get('account.analytic.line').button_open_analytic_corrections(cr, uid, al_ids, context=context)

account_invoice_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
