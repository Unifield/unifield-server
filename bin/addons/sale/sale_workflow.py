# -*- coding:utf-8 -*-

from osv import osv, fields
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
            
        wf_service = netsvc.LocalService('workflow')

        res = self.write(cr, uid, ids, {'state': 'validated'}, context=context)

        for so_id in set([sol.order_id.id for sol in self.browse(cr, uid, ids, context=context)]):
            wf_service.trg_write(uid, 'sale.order', so_id, cr)

        return res

    def action_draft(self, cr ,uid, ids, context=None):
        '''
        Workflow method called when trying to reset draft the sale.order.line
        '''
        if context is None:
            context = {}
            
        wf_service = netsvc.LocalService('workflow')

        res = self.write(cr, uid, ids, {'state': 'draft'}, context=context)

        for so_id in set([sol.order_id.id for sol in self.browse(cr, uid, ids, context=context)]):
            wf_service.trg_write(uid, 'sale.order', so_id, cr)

        return res

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
            
        wf_service = netsvc.LocalService('workflow')

        for so in self.browse(cr, uid, ids, context=context):
            self.pool.get('sale.order.line').write(cr, uid, [sol.id for sol in so.order_line], {'state': 'validated'}, context=context)
            self.write(cr, uid, ids, {'state': 'validated'}, context=context)

        return True

    def get_less_advanced_sol_state(self, cr, uid, ids, context=None):
        """
        Get the less advanced state of the sale order lines
        Used to compute sale order state
        """
        if context is None:
            context = {}
            
        for so in self.browse(cr, uid, ids, context=context):
            sol_states = [line.state for line in so.order_line]
            if all([state == 'cancel' for state in sol_states]):
                return 'cancel'
            elif 'draft' in sol_states:
                return 'draft'
            elif 'validated' in sol_states:
                return 'validated'
            elif 'sourced' in sol_states:
                return 'sourced'
            elif 'confirmed' in sol_states:
                return 'confirmed'
            elif 'done' in sol_states:
                return 'done'
        return None

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


