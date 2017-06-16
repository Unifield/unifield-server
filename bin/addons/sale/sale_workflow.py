# -*- coding:utf-8 -*-

from osv import osv, fields
from tools.translate import _
import netsvc
from . import SALE_ORDER_STATE_SELECTION



class sale_order_line(osv.osv):
    _name = "sale.order.line"
    _inherit = "sale.order.line"

    def wkf_validated(self, cr, uid, ids, context=None):
        return True


    def action_validate(self, cr, uid, ids, context=None):
        '''
        Workflow method called when validating the sale.order.line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for sol in self.browse(cr, uid, ids, context=context):
            # check analytic distribution before validating the line:
            if not sol.analytic_distribution_id and not sol.order_id.analytic_distribution_id:
                raise osv.except_osv(
                    _('Error'),
                    _('You cannot validate lines without analytic distribution')
                )
            elif not sol.analytic_distribution_id: # we copy and pull header AD in the line:
                new_ad = self.pool.get('analytic.distribution').copy(cr, uid, sol.order_id.analytic_distribution_id.id, context=context)
                self.write(cr, uid, sol.id, {'analytic_distribution_id': new_ad}, context=context)

        return self.write(cr, uid, ids, {'state': 'validated'}, context=context)

    def action_draft(self, cr ,uid, ids, context=None):
        '''
        Workflow method called when trying to reset draft the sale.order.line
        '''
        if context is None:
            context = {}
            
        return self.write(cr, uid, ids, {'state': 'draft'}, context=context)

sale_order_line()



class sale_order(osv.osv):
    _name = "sale.order"
    _inherit = "sale.order"

    def validate_lines(self, cr, uid, ids, context=None):
        """
        Force SO lines validation and update SO state
        """
        if context is None:
            context = {}
            
        for so in self.browse(cr, uid, ids, context=context):
            self.pool.get('sale.order.line').action_validate(cr, uid, [sol.id for sol in so.order_line], context=context)

        self.write(cr, uid, ids, {'state': 'validated'}, context=context)

        return True

    def wkf_validated(self, cr, uid, ids, context=None):
        """
        Try to validate sale order lines
        """
        return True

    def wkf_split(self, cr, uid, ids, context=None):
        return True

    def wkf_split_done(self, cr, uid, ids, context=None):
        return True

    def test_validated(self, cr, uid, ids, context=None):
        """
        Workflow method that test if SO can get 'validated' state
        """
        if context is None:
            context = {}
            
        print "FO: test_validated"
        for so in self.browse(cr, uid, ids, context=context):
            if not so.order_line:
                return False
            for sol in so.order_line:
                if sol.state == 'draft':
                    return False
        return True

    def test_sourced(self, cr, uid, ids, context=None):
        """
        Workflow method that test if SO can get 'sourced' state
        """
        if context is None:
            context = {}
            
        print "FO: test_sourced"
        for so in self.browse(cr, uid, ids, context=context):
            if not so.order_line:
                return False
            for sol in so.order_line:
                if sol.state in ('draft', 'validated'):
                    return False
        return True
        
    def test_confirmed(self, cr, uid, ids, context=None):
        """
        Workflow method that test if SO can get 'confirmed' state
        """
        if context is None:
            context = {}
            
        print "FO: test_confirmed"
        for so in self.browse(cr, uid, ids, context=context):
            if not so.order_line:
                return False
            for sol in so.order_line:
                if sol.state in ('draft', 'validated', 'sourced'):
                    return False
        return True
        
    def test_done(self, cr, uid, ids, context=None):
        """
        Workflow method that test if SO can get 'done' state
        """
        if context is None:
            context = {}
            
        print "FO: test_done"
        for so in self.browse(cr, uid, ids, context=context):
            if not so.order_line:
                return False
            for sol in so.order_line:
                if sol.state in ('draft', 'validated', 'sourced', 'confirmed'):
                    return False
        return True
        
    def test_cancel(self, cr, uid, ids, context=None):
        """
        Workflow method that test if SO can get 'cancel' state
        """
        if context is None:
            context = {}
            
        print "FO: test_cancel"
        for so in self.browse(cr, uid, ids, context=context):
            if not so.order_line:
                return False
            for sol in so.order_line:
                if sol.state != 'cancel':
                    return False
        return True


sale_order()


