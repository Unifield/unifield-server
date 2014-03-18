#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import print_function
from unifield_test import UnifieldTest
from time import strftime

class FinanceTest(UnifieldTest):

    def __init__(self, *args, **kwargs):
        '''
        Include some finance data in the databases (except sync one).
        Include/create them only if they have not been already created.
        To know this, we use the key: "finance_test_class"
        '''
        super(FinanceTest, self).__init__(*args, **kwargs)
        keyword = 'finance_test_class'
        for database_name in self.db:
            if database_name == 'sync':
                continue
            database = self.db.get(database_name)
            # If no one, do some changes on DBs
            if not self.is_keyword_present(database, keyword):
                # 00 Open periods from january to today's one
                month = strftime('%m')
                today = strftime('%Y-%m-%d')
                fy_obj = database.get('account.fiscalyear')
                period_obj = database.get('account.period')
                # Fiscal years
                fy_ids = fy_obj.search([('date_start', '<=', today), ('date_stop', '>=', today)])
                if not fy_ids:
                    raise Exception('error', 'No fiscalyear found!')
                # Sort periods by number
                periods = period_obj.search([('fiscalyear_id', 'in', fy_ids), ('number', '<=', month), ('state', '=', 'created')], 0, 16, 'number')
                for period in periods:
                    try:
                        period_obj.action_set_state(period, {'state': 'draft'})
                    except Exception, e:
                        raise Exception('error', e)
                # Write the fact that data have been loaded
                database.get(self.test_module_obj_name).create({'name': keyword, 'active': True})
                print ("  * %s: Data loaded (%s)" % (database_name, keyword))
            else:
                print ("  * %s: Data exists (%s)" % (database_name, keyword))

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: