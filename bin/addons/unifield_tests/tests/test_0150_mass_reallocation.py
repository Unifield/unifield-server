#!/usr/bin/env python
# -*- coding: utf8 -*-

from finance import FinanceTest
from time import strftime

class MassReallocationTest(FinanceTest):

    def test_010_fp_changes(self):
        '''
        Create analytic lines then reallocate them on another destination axis.
        '''
        # Prepare some values
        # TODO: To remove when fixed
        return
        db = self.p1
        ana_obj = db.get('account.analytic.line')
        ana_acc_obj = db.get('account.analytic.account')
        wiz_obj = db.get('mass.reallocation.wizard')
        # Create a move that will generate some analytic lines
        move_id, expense_id, counterpart_id = self.create_journal_entry(db)
        # Fetch analytic line and launch a mass reallocation wizard on it
        analytic_ids = ana_obj.search([('move_id', '=', expense_id)])
        if isinstance(analytic_ids, (int, long)):
            analytic_ids = [analytic_ids]
        self.assert_(analytic_ids != False, "No analytic line found to check Mass Reallocation.")
        # Search CC2
        cc2_ids = ana_acc_obj.search([('code', '=', 'SUP')])
        if isinstance(cc2_ids, (int, long)):
            cc2_ids = [cc2_ids]
        # Create Mass reallocation wizard
        wiz_id = wiz_obj.create({'account_id': cc2_ids[0], 'date': strftime('%Y-%m-%d'), 'line_ids': [(6, 0, analytic_ids)]}, {'active_ids': analytic_ids})
        # Should give a result like this:
        # {
        #   'name': 'Verification Result',
        #   'view_type': 'form',
        #   'res_model': 'mass.reallocation.verification.wizard', 
        #   'view_mode': 'form',
        #   'context': {},
        #   'type': 'ir.actions.act_window',
        #   'res_id': [1],
        #   'target': 'new'
        # }
        next_wiz_info = wiz_obj.button_validate([wiz_id])
        # Do some check on result
        self.assert_(next_wiz_info.get('res_model', False) == 'mass.reallocation.verification.wizard', "Wrong return after mass reallocation validation.")
        self.assert_(next_wiz_info.get('res_id', False) != False, "No ID for the next wizard.")
        next_wiz_id = next_wiz_info.get('res_id')
        next_wiz_obj = db.get('mass.reallocation.verification.wizard')
        next_wiz_obj.button_validate(next_wiz_id)
        # Check that analytic line have changed with new destination
        line = ana_obj.browse(analytic_ids[0])
        self.assert_(line.destination_id.code == 'SUP', "Analytic line have wrong DESTINATION: %s (should be SUP)" % (line.destination_id.code))
        self.assert_(line.account_id.code == 'PF', "Analytic line have wrong FP: %s (should be PF)" % (line.account_id.code))

def get_test_class():
    '''Return the class to use for tests'''
    return MassReallocationTest

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
