# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

from osv import osv, fields

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    def _have_analytic_distribution(self, cr, uid, ids, name, arg, context={}):
        """
        If invoice have an analytic distribution, return True, else return False
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for inv in self.browse(cr, uid, ids, context=context):
            res[inv.id] = False
            if inv.analytic_distribution_id:
                res[inv.id] = True
        return res

    _columns = {
        'have_analytic_distribution': fields.function(_have_analytic_distribution, method=True, type='boolean', string='Have an analytic distribution?'),
    }

    def copy(self, cr, uid, id, default={}, context={}):
        """
        Copy global distribution and give it to new invoice
        """
        if not context:
            context = {}
        inv = self.browse(cr, uid, [id], context=context)[0]
        new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, inv.analytic_distribution_id.id, {}, context=context)
        if new_distrib_id:
            default.update({'analytic_distribution_id': new_distrib_id})
        return super(account_invoice, self).copy(cr, uid, id, default, context)

account_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
