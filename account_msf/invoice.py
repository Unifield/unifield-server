#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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
import re
from lxml import etree
from time import strftime

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    def _get_have_donation_certificate(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        If this invoice have a stock picking in which there is a Certificate of Donation, return True. Otherwise return False.
        """
        res = {}
        for i in self.browse(cr, uid, ids):
            res[i.id] = False
            if i.picking_id:
                a_ids = self.pool.get('ir.attachment').search(cr, uid, [('res_model', '=', 'stock.picking'), ('res_id', '=', i.picking_id.id), ('description', '=', 'Certificate of Donation')])
                if a_ids:
                    res[i.id] = True
        return res

    _columns = {
        'picking_id': fields.many2one('stock.picking', string="Picking"),
        'have_donation_certificate': fields.function(_get_have_donation_certificate, method=True, type='boolean', string="Have a Certificate of donation?"),
    }

    def button_donation_certificate(self, cr, uid, ids, context=None):
        """
        """
        for inv in self.browse(cr, uid, ids):
            pick_id = inv.picking_id and inv.picking_id.id or ''
            domain = "[('res_model', '=', 'stock.picking'), ('res_id', '=', " + str(pick_id) + "), ('description', '=', 'Certificate of Donation')]"
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_msf', 'view_attachment_tree_2')
            view_id = view_id and view_id[1] or False
            search_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_msf', 'view_attachment_search_2')
            search_view_id = search_view_id and search_view_id[1] or False
            return {
                'name': "Certificate of Donation",
                'type': 'ir.actions.act_window',
                'res_model': 'ir.attachment',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': [view_id],
                'search_view_id': search_view_id,
                'domain': domain,
                'context': context,
                'target': 'current',
            }
        return False

account_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
