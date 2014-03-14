#!/usr/bin/env python
# -*- coding: utf8 -*-
from unifield_test import UnifieldTest

class FinanceTest(UnifieldTest):

    def __init__(self, *args, **kwargs):
        '''
        Include some finance data in the database.
        Include/create them only if they have not been already created.
        To know this, we use the key: "finance_test_class"
        '''
        super(FinanceTest, self).__init__(*args, **kwargs)
        keyword = 'finance_test_class'
        for database_name in self.db:
            database = self.db.get(database_name)
            # If no one, create a test account
            if not self.is_keyword_present(database, keyword):
                pass
#                # Write the fact that the data have been loaded
#                database.get(self.test_module_obj_name).create({'name': keyword, 'active': True})
            else:
                print "%s exists!" % (keyword)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
