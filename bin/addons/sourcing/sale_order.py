# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 TeMPO Consulting, MSF
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

from osv import fields
from osv import osv
from tools.translate import _

import netsvc


class sale_order(osv.osv):
    """
    Override the sale.order object to add some feature
    of the Order Sourcing Tool
    """
    _name = 'sale.order'
    _inherit = 'sale.order'

    _columns = {
        'sourcing_trace_ok': fields.boolean(
            string='Display sourcing logs',
        ),
        'sourcing_trace': fields.text(
            string='Sourcing logs',
            readonly=True,
        ),
    }

    # TODO: TO REFACTORE
    def do_order_confirm_method(self, cr, uid, ids, context=None):
        '''
        trigger the workflow
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # objects
        wf_service = netsvc.LocalService("workflow")
        
        for so in self.browse(cr, uid, ids, fields_to_fetch=['order_line'], context=context):
            to_source = []
            for sol in so.order_line: 
                if sol.state.startswith('validated'):
                    if sol.type == 'make_to_order' and sol.po_cft in ('po','rfq') and not sol.supplier:
                        raise osv.except_osv(_('Error'), _('Supplier is not defined for all Field Order lines. Please check the line %s') % sol.line_number)
                    to_source.append(sol.id)

            if to_source:
                self.pool.get('sale.order.line').source_line(cr, uid, [sol.id], context=context)

        return True

sale_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
