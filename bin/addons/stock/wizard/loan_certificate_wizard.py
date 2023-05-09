#!/usr/bin/env python
#-*- encoding:utf-8 -*-

from osv import osv
from osv import fields
from tools.translate import _


class loan_certificate_wizard(osv.osv_memory):
    _name = 'loan.certificate.wizard'

    def _get_default_loan_return(self, cr, uid, context=None):
        loan_return_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves',
                                                                             'reason_type_loan_return')[1]
        pick = False
        if context.get('active_id'):
            pick = self.pool.get('stock.picking').read(cr, uid, context['active_id'], ['reason_type_id'], context=context)
        return pick and pick['reason_type_id'][0] == loan_return_id or False

    _columns = {
        'display_value': fields.boolean(string='Display total value', help='Tick to display the Total Value in the report'),
        'loan_return': fields.boolean(string='Is Loan Return'),
    }

    _defaults = {
        'display_values': False,
        'loan_return': _get_default_loan_return,
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Prevent the use of the report if the document (IN or OUT) does not have the Loan or Loan Return Reason Type
        """
        if context is None:
            context = {}
        data_obj = self.pool.get('ir.model.data')
        loan_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan')[1]
        loan_return_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan_return')[1]

        if not context.get('picking_type') or context['picking_type'] not in ['incoming_shipment', 'delivery_order']:
            raise osv.except_osv(_('Error'), _('You can only use this Report for INs and OUTs'))
        if context.get('active_id'):
            pick = self.pool.get('stock.picking').read(cr, uid, context['active_id'], ['reason_type_id'], context=context)
            if pick['reason_type_id'][0] not in [loan_id, loan_return_id]:
                raise osv.except_osv(_('Error'), _('You can not use this Report if the document does not have the Loan or Loan Return Reason Type'))
        else:
            raise osv.except_osv(_('Error'), _('No active ID'))

        return super(loan_certificate_wizard, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)

    def create_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        for wiz in self.browse(cr, uid, ids, context=context):
            data = {
                'ids': [context.get('active_id')],
                'model': 'stock_picking',
                'display_value': wiz.display_value,
                'context': context,
            }
            report_name = 'loan.certificate'
            if wiz.loan_return:
                report_name = 'loan.return.certificate'
            return {
                'type': 'ir.actions.report.xml',
                'report_name': report_name,
                'datas': data,
            }
        return {'type': 'ir.actions.act_window_close'}


loan_certificate_wizard()


class ship_loan_certificate_wizard(osv.osv_memory):
    _name = 'ship.loan.certificate.wizard'

    def _get_ship_id(self, cr, uid, context=None):
        ship = context.get('active_id') and self.pool.get('shipment').browse(cr, uid, context['active_id'],
                                                                             fields_to_fetch=['id'], context=context)
        return ship and ship.id or False

    def _get_has_loan(self, cr, uid, context=None):
        ship = context.get('active_id') and self.pool.get('shipment').browse(cr, uid, context['active_id'],
                                                                             fields_to_fetch=['has_loan'], context=context)
        return ship and ship.has_loan or False

    def _get_has_ret_loan(self, cr, uid, context=None):
        ship = context.get('active_id') and self.pool.get('shipment').browse(cr, uid, context['active_id'],
                                                                             fields_to_fetch=['has_ret_loan'], context=context)
        return ship and ship.has_ret_loan or False

    _columns = {
        'display_value': fields.boolean(string='Display total value', help='Tick to display the Total Value in the report'),
        'ship_id': fields.many2one('shipment', string='Shipment'),
        'has_loan': fields.boolean(string='Has Loan Pack(s)'),
        'has_ret_loan': fields.boolean(string='Has Loan Return Pack(s)'),
    }

    _defaults = {
        'display_value': False,
        'ship_id': _get_ship_id,
        'has_loan': _get_has_loan,
        'has_ret_loan': _get_has_ret_loan,
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Prevent the use of the report if the SHIP does not contain a PPL with the Loan or Loan Return Reason Type
        """
        if context is None:
            context = {}

        if context.get('active_id'):
            ftf = ['backshipment_id', 'has_loan', 'has_ret_loan']
            ship = self.pool.get('shipment').browse(cr, uid, context['active_id'], fields_to_fetch=ftf, context=context)
            if not ship.backshipment_id:
                raise osv.except_osv(_('Warning !'), _('Loan Certificate is only available for Shipment Objects (not draft)!'))
            if not ship.has_loan and not ship.has_ret_loan:
                raise osv.except_osv(_('Error'), _('You can not use this Report if the Shipment does not contain at least a Pack with the Loan or Loan Return Reason Type'))
        else:
            raise osv.except_osv(_('Error'), _('No active ID'))

        return super(ship_loan_certificate_wizard, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)

    def create_return_report(self, cr, uid, ids, context=None):
        return self.create_report(cr, uid, ids, context=context, loan_return=True)

    def create_report(self, cr, uid, ids, context=None, loan_return=False):
        if context is None:
            context = {}

        data_obj = self.pool.get('ir.model.data')
        loan_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan')[1]
        loan_return_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan_return')[1]

        for wiz in self.browse(cr, uid, ids, context=context):
            report_name = 'ship.loan.certificate'
            value = 0.00
            loan_id_to_check = loan_id
            if loan_return:
                report_name = 'ship.loan.return.certificate'
                loan_id_to_check = loan_return_id
            if wiz.display_value:
                for pack in wiz.ship_id.pack_family_memory_ids:
                    if pack.ppl_id.reason_type_id.id == loan_id_to_check:
                        for move in pack.move_lines:
                            move_price = move.price_unit or move.product_id.standard_price or 0.00
                            if move.price_currency_id.id != wiz.ship_id.currency_id.id:
                                move_price = self.pool.get('res.currency').\
                                    compute(cr, uid, move.price_currency_id.id, wiz.ship_id.currency_id.id,
                                            move_price, round=False, context=context)
                            value += move.product_qty * move_price
            data = {
                'ids': [wiz.ship_id.id],
                'model': 'shipment',
                'loan_id': loan_id,
                'loan_return_id': loan_return_id,
                'display_value': wiz.display_value,
                'value': value,
                'context': context,
            }

            return {
                'type': 'ir.actions.report.xml',
                'report_name': report_name,
                'datas': data,
            }
        return {'type': 'ir.actions.act_window_close'}


ship_loan_certificate_wizard()
