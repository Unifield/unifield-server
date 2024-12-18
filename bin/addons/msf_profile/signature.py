# -*- coding: utf-8 -*-

from osv import osv


class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'signature.object']


purchase_order()


class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = ['sale.order', 'signature.object']


sale_order()


class stock_picking(osv.osv):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'signature.object']


stock_picking()


class account_bank_statement(osv.osv):
    _name = 'account.bank.statement'
    _inherit = ['account.bank.statement', 'signature.object']


account_bank_statement()


class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = ['account.invoice', 'signature.object']


account_invoice()


class PhysicalInventory(osv.osv):
    _name = 'physical.inventory'
    _inherit = ['physical.inventory', 'signature.object']


PhysicalInventory()

