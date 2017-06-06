# -*- coding:utf-8 -*-

from osv import osv

class sale_order(osv.osv):
    _name = "sale.order"
    _inherit = "sale.order"

    def wkf_validated(self, cr, uid, ids, context=None):
        '''
        Try to validate sale order lines
        '''
        return True

    def wkf_split(self, cr, uid, ids, context=None):
        return True

    def wkf_split_done(self, cr, uid, ids, context=None):
        return True


class sale_order_line(osv.osv):
    _name = "sale.order.line"
    _inherit = "sale.order.line"

    def wkf_validated(self, cr, uid, ids, context=None):
        return True