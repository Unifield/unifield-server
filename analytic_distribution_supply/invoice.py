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
from osv import fields

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    _columns = {
        'order_line_id': fields.many2one('purchase.order.line', string="Purchase Order Line", readonly=True, 
            help="Purchase Order Line from which this invoice line has been generated (when coming from a purchase order)."),
    }

account_invoice_line()

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    _columns = {
        'purchase_ids': fields.many2many('purchase.order', 'purchase_invoice_rel', 'invoice_id', 'purchase_id', 'Purchase Order', 
            help="Purchase Order from which invoice have been generated"),
    }

    def fetch_analytic_distribution(self, cr, uid, ids, context={}):
        """
        Recover distribution from purchase order. If a commitment is attached to purchase order, then retrieve analytic distribution from commitment voucher.
        NB: This method only works because there is a link between purchase and invoice.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        invl_obj = self.pool.get('account.invoice.line')
        ana_obj = self.pool.get('analytic.distribution')
        # Browse all invoices
        for inv in self.browse(cr, uid, ids, context=context):
            # Set analytic distribution from purchase order to invoice
            for po in inv.purchase_ids:
                # First set invoice global distribution
                if not inv.analytic_distribution_id and po.analytic_distribution_id:
                    new_distrib_id = ana_obj.copy(cr, uid, po.analytic_distribution_id.id, {})
                    if not new_distrib_id:
                        raise osv.except_osv(_('Error'), _('An error occured for analytic distribution copy for invoice.'))
                    # create default funding pool lines
                    ana_obj.create_funding_pool_lines(cr, uid, [new_distrib_id])
                    self.pool.get('account.invoice').write(cr, uid, [inv.id], {'analytic_distribution_id': new_distrib_id,})
                # Then set distribution on invoice line regarding purchase order line distribution
                for invl in inv.invoice_line:
                    if invl.order_line_id and invl.order_line_id.analytic_distribution_id and not invl.analytic_distribution_id:
                        new_invl_distrib_id = ana_obj.copy(cr, uid, invl.order_line_id.analytic_distribution_id.id, {})
                        if not new_invl_distrib_id:
                            raise osv.except_osv(_('Error'), _('An error occured for analytic distribution copy for invoice.'))
                        # create default funding pool lines
                        ana_obj.create_funding_pool_lines(cr, uid, [new_invl_distrib_id])
                        invl_obj.write(cr, uid, [invl.id], {'analytic_distribution_id': new_invl_distrib_id})
        return True

account_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
