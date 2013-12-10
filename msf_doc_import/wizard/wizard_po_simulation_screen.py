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

from osv import osv
from osv import fields

from msf_order_date import TRANSPORT_TYPE


class wizard_import_po_simulation_screen(osv.osv_memory):
    _name = 'wizard.import.po.simulation.screen'

    def _get_po_lines(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the number of lines in the PO
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for wiz in self.browse(cr, uid, ids, context=context):
            res[wiz.id] = 0
            if wiz.order_id:
                res[wiz.id] = len(wiz.order_id.order_line)

        return res

    def _get_import_lines(self,cr, uid, ids, field_name, args, context=None):
        '''
        Return the number of lines after the import
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for wiz in self.browse(cr, uid, ids, context=context):
            res[wiz.id] = 0
            if wiz.state == 'done':
                res[wiz.id] = len(wiz.line_ids)

        return res


    _columns = {
        'order_id': fields.many2one('purchase.order', string='Order',
                                    required=True,
                                    readonly=True),
        'message': fields.text(string='Import message',
                               readonly=True),
        'state': fields.selection([('draft', 'Draft'),
                                   ('in_progress', 'In Progress'),
                                   ('done', 'Done')], 
                                   string='State',
                                   readonly=True),
        # File information
        'file_to_import': fields.binary(string='File to import'),
        'filename': fields.char(size=64, string='Filename'),
        'error_file': fields.binary(string='File with errors'),
        'error_filename': fields.char(size=64, string='Lines with errors'),
        'nb_file_lines': fields.integer(string='Total of file lines',
                                        readonly=True),
        'nb_treated_lines': fields.integer(string='Nb treated lines',
                                           readonly=True),
        'percent_completed': fields.float(string='Percent completed',
                                          readonly=True),
        'import_error_ok': fields.boolean(string='Error at import'),
        # PO Header information
        'in_creation_date': fields.related('order_id', 'date_order',
                                           type='date',
                                           string='Creation date',
                                           readonly=True),
        'in_supplier_ref': fields.related('order_id', 'partner_ref',
                                          type='char',
                                          string='Supplier Reference',
                                          readonly=True),
        'in_dest_addr': fields.related('order_id', 'dest_address_id',
                                       type='many2one',
                                       relation='res.partner.address',
                                       string='Destination Address',
                                       readonly=True),
        'in_transport_mode': fields.related('order_id', 'transport_type',
                                            type='selection',
                                            selection=TRANSPORT_TYPE,
                                            string='Transport mode',
                                            readonly=True),
        'in_notes': fields.related('order_id', 'notes', type='text', 
                                   string='Header notes', readonly=True),
        'in_currency': fields.related('order_id', 'pricelist_id',
                                      type='relation',
                                      relation='product.pricelist',
                                      string='Currency',
                                      readonly=True),
        'in_amount_untaxed': fields.related('order_id', 'amount_untaxed',
                                            string='Untaxed Amount',
                                            readonly=True),
        'in_amount_tax': fields.related('order_id', 'amount_tax',
                                        string='Taxes',
                                        readonly=True),
        'in_amount_total': fields.related('order_id', 'amount_total',
                                          string='Total',
                                          readonly=True),
        'in_transport_cost': fields.related('order_id', 'transport_cost',
                                            string='Transport mt',
                                            readonly=True),
        'in_total_price_include_transport': fields.related('order_id', 'total_price_include_transport',
                                                           string='Total incl. transport',
                                                           readonly=True),
        'nb_po_lines': fields.function(_get_po_lines, method=True, type='integer',
                                       string='Nb PO lines', readonly=True),
        # Import fiels
        'imp_supplier_ref': fields.char(size=256, string='Supplier Ref', 
                                        readonly=True),
        'imp_transport_mode': fields.selection(selection=TRANSPORT_TYPE,
                                               string='Transport mode',
                                               readonly=True),
        'imp_message_esc': fields.text(string='Message ESC Header',
                                       readonly=True),
        'imp_amount_untaxed': fields.float(digits=(16,2),
                                           string='Untaxed Amount',
                                           readonly=True),
        'imp_amount_total': fields.float(digits=(16,2),
                                         string='Total Amount',
                                         readonly=True),
        'imp_total_price_include_transport': fields.float(digits=(16,2),
                                                          string='Total incl. transport',
                                                          readonly=True),
        'amount_discrepancy': fields.float(digits=(16,2),
                                           string='Discrepancy',
                                           readonly=True),
        'imp_nb_po_lines': fields.function(_get_import_lines, methode=True,
                                           type='integer', string='Nb Import lines',
                                           readonly=True),
    }

    '''
    Action buttons
    '''
    def return_to_po(self, cr, uid, ids, context=None):
        '''
        Go back to PO
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.read(cr, uid, ids, ['order_id'], context=context):
            order_id = wiz['order_id']
            return {'type': 'ir.actions.act_window',
                    'res_model': 'purchase.order',
                    'view_type': 'form',
                    'view_mode': 'form, tree',
                    'target': 'crush',
                    'res_id': order_id,
                    'context': context,
                    }

wizard_import_po_simulation_screen()
