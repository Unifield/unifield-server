#-*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 TeMPO Consulting, MSF. All Rights Reserved
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
import base64
from tools.translate import _
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
from msf_doc_import.wizard import ACCOUNT_INVOICE_COLUMNS_HEADER_FOR_IMPORT as columns_header_for_account_line_import
from msf_doc_import.wizard import ACCOUNT_INVOICE_COLUMNS_FOR_IMPORT as columns_for_account_line_import
from msf_doc_import import GENERIC_MESSAGE

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    _columns = {
        'supplier_reference': fields.char('Supplier reference', size=128),
        'picking_id': fields.many2one('stock.picking', string="Picking"),
        'purchase_ids': fields.many2many('purchase.order', 'purchase_invoice_rel', 'invoice_id', 'purchase_id', 'Purchase Order',
                                         help="Purchase Order from which invoice have been generated"),
        'main_purchase_id': fields.many2one('purchase.order', 'Purchase Order (invoiced "From Order") that generates this SI', select=1),
    }

    def wizard_import_si_line(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        context.update({'active_id': ids[0]})
        columns = columns_for_account_line_import

        columns_header = [(_(f[0]), f[1]) for f in columns_header_for_account_line_import]
        default_template = SpreadsheetCreator(_('Template of import'), columns_header, [])
        imported_file = base64.encodestring(default_template.get_xml(default_filters=['decode.utf8']))
        view_name = context.get('_terp_view_name', 'Import Lines')
        filename_template = _('%s_template.xls') % _(view_name).replace(' ', '_')
        export_id = self.pool.get('wizard.import.invoice.line').create(cr, uid,
                                                                       {
                                                                           'file': imported_file,
                                                                           'filename_template': filename_template,
                                                                           'invoice_id': ids[0],
                                                                           'message': """%s %s""" % (_(GENERIC_MESSAGE), ', '.join([_(f) for f in columns]),),
                                                                           'state': 'draft',
                                                                       },
                                                                       context)
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.invoice.line',
                'res_id': export_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'same',
                'context': context,
                }

account_invoice()

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    _columns = {
        'order_line_id': fields.many2one('purchase.order.line', string="Purchase Order Line", readonly=True,
                                         help="Purchase Order Line from which this invoice line has been generated (when coming from a purchase order)."),
    }

account_invoice_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
