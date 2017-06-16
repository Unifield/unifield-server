# -*- coding:utf-8 -*-

from osv import osv, fields
from tools.translate import _
import netsvc
from . import SALE_ORDER_STATE_SELECTION



class sale_order_line(osv.osv):
    _name = "sale.order.line"
    _inherit = "sale.order.line"


    def _get_destination_ok(self, cr, uid, lines, context):
        dest_ok = False
        for line in lines:
            dest_ok = line.account_4_distribution and line.account_4_distribution.destination_ids or False
            if not dest_ok:
                raise osv.except_osv(_('Error'), _('No destination found for this line: %s.') % (line.name or '',))
        return dest_ok
        

    def analytic_distribution_checks(self, cr, uid, ids, context=None):
        """
        Check analytic distribution for each sale order line (except if we come from YAML tests)
        Get a default analytic distribution if intermission.
        Change analytic distribution if intermission.
        """
        # Objects
        ana_obj = self.pool.get('analytic.distribution')
        data_obj = self.pool.get('ir.model.data')
        acc_obj = self.pool.get('account.account')
        sol_obj = self.pool.get('sale.order.line')
        distrib_line_obj = self.pool.get('cost.center.distribution.line')

        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for line in self.browse(cr, uid, ids, context=context):
            """
            UFTP-336: Do not check AD on FO lines if the lines are
                      created on a tender or a RfQ.
                      The AD must be added on the PO line and update the
                      AD at FO line at PO confirmation.
            """
            so = line.order_id
            if line.created_by_tender or line.created_by_rfq:
                continue
            # Search intermission
            intermission_cc = data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project_intermission')
            # Check distribution presence
            l_ana_dist_id = line.analytic_distribution_id and line.analytic_distribution_id.id
            o_ana_dist_id = so.analytic_distribution_id and so.analytic_distribution_id.id
            distrib_id = l_ana_dist_id or o_ana_dist_id or False

            #US-830 : Remove the definition of a default AD for the inter-mission FO is no AD is defined
            if not distrib_id and not so.from_yml_test and not so.order_type in ('loan', 'donation_st', 'donation_exp'):
                raise osv.except_osv(
                    _('Warning'),
                    _('Analytic distribution is mandatory for this line: %s!') % (line.name or '',),
                )

            # Check distribution state
            if distrib_id and line.analytic_distribution_state != 'valid' and not so.from_yml_test:
                # Raise an error if no analytic distribution on line and NONE on header (because no possibility to change anything)
                if (not line.analytic_distribution_id or line.analytic_distribution_state == 'none') and \
                   not so.analytic_distribution_id:
                    # We don't raise an error for these types
                    if so.order_type not in ('loan', 'donation_st', 'donation_exp'):
                        raise osv.except_osv(
                            _('Warning'),
                            _('Analytic distribution is mandatory for this line: %s') % (line.name or '',),
                        )
                    else:
                        continue

                # Change distribution to be valid if needed by using those from header
                id_ad = ana_obj.create(cr, uid, {}, context=context)
                # Get the CC lines of the FO line if any, or the ones of the order
                cc_lines = line.analytic_distribution_id and line.analytic_distribution_id.cost_center_lines
                cc_lines = cc_lines or so.analytic_distribution_id.cost_center_lines
                for x in cc_lines:
                    # fetch compatible destinations then use one of them:
                    # - destination if compatible
                    # - else default destination of given account
                    bro_dests = self._get_destination_ok(cr, uid, [line], context=context)
                    if x.destination_id in bro_dests:
                        bro_dest_ok = x.destination_id
                    else:
                        bro_dest_ok = line.account_4_distribution.default_destination_id
                    # Copy cost center line to the new distribution
                    distrib_line_obj.copy(cr, uid, x.id, {'distribution_id': id_ad, 'destination_id': bro_dest_ok.id}, context=context)
                    # Write new distribution and link it to the line
                    sol_obj.write(cr, uid, [line.id], {'analytic_distribution_id': id_ad}, context=context)
                # UFTP-277: Check funding pool lines if missing
                ana_obj.create_funding_pool_lines(cr, uid, [id_ad], context=context)

        return True


    def action_validate(self, cr, uid, ids, context=None):
        '''
        Workflow method called when validating the sale.order.line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # check analytic distribution before validating the line:
        self.analytic_distribution_checks(cr, uid, ids, context=context)

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


