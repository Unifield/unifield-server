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


COMPATS = {
    'regular':       ['internal', 'intermission', 'section', 'external', 'esc'],
    'donation_st':   ['internal', 'intermission', 'section'],
    'loan':          ['internal', 'intermission', 'section', 'external'],
    'loan_return':   ['internal', 'intermission', 'section', 'external'],
    'donation_exp':  ['internal', 'intermission', 'section'],
    'in_kind':       ['external', 'esc'],
    'direct':        ['external', 'esc'],
    'purchase_list': ['external'],
}


class purchase_order(osv.osv):
    """
    override for workflow modification
    """
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    _columns = {
        'customer_id': fields.many2one('res.partner', string='Customer', domain=[('customer', '=', True)]),
        'unique_fo_id': fields.many2one(
            'sale.order',
            string='Unique FO',
            readonly=True,
            help="""This field is used to have only one PO for a specific FO/IR 
if the supplier 'Order creation method' is set to 'Requirements by Order'.""",
        ),
        'unique_rule_type': fields.char(
            size=128,
            string='Unique Replenishment rule type',
            readonly=True,
            help="""This field is used to have only one PO by replenishment
rules if the supplier 'Order creation method' is set to 'Requirements by Order.'
""",
        ),
        'po_from_rr': fields.boolean(
            string='PO from replenishment rules',
            readonly=True,
        ),
        'related_sourcing_id': fields.many2one(
            'related.sourcing',
            string='Sourcing group',
            readonly=True,
        ),
    }

    _defaults = {
        'po_from_rr': False,
    }

    def create(self, cr, uid, vals, context=None):
        '''
        override for debugging purpose
        '''
        return super(purchase_order, self).create(cr, uid, vals, context)

    def _check_order_type_and_partner(self, cr, uid, ids, context=None):
        """
        Check order type and partner type compatibilities.
        """
        # Browse PO
        for po in self.browse(cr, uid, ids):
            if po.order_type not in COMPATS or po.partner_id.partner_type not in COMPATS[po.order_type]:
                return False
        return True

    def update_source_document(self, cr, uid, ids, source_document_id, context=None):
        '''
        update the field 'source document' of the purchase.order
        @param source_document_id: id of source sale.order to add in fields purchase.order.origin
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        # get the source document name:
        source_doc_name = self.pool.get('sale.order').browse(cr, uid, source_document_id, fields_to_fetch=['name'], context=context).name
        if not source_doc_name:
            return False
        source_doc_name = source_doc_name.strip()

        # udpate origin field:
        for po in self.browse(cr, uid, ids, context=context):
            if not po.origin :
                self.write(cr, uid, [po.id], {'origin': '%s' % source_doc_name}, context=context)
            elif po.origin.find(source_doc_name.strip()) == -1:
                self.write(cr, uid, [po.id], {'origin': '%s:%s' % (po.origin, source_doc_name)}, context=context)

        return True


    _constraints = [
        (
            _check_order_type_and_partner,
            "Partner type and order type are incompatible! Please change either order type or partner.",
            ['order_type', 'partner_id'],
        ),
    ]

purchase_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
