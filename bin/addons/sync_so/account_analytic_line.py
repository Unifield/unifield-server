import time
import datetime

from dateutil.relativedelta import relativedelta
from os.path import join as opj
from operator import itemgetter

from account import installer

from tools.translate import _
from osv import fields, osv
import netsvc
import tools


class account_installer(osv.osv_memory):
    _inherit = 'account.installer'
    _name = 'account.installer'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        res = super(account_installer, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        configured_cmp = []
        unconfigured_cmp = []
        cmp_select = []
        company_ids = self.pool.get('res.company').search(cr, uid, [], context=context)
        
        # !!!!Remove the following statements, because if the account attached to the default company has been synchronized from another instance, the the company
        # will not be shown in the configurator form!
        
        #display in the widget selection of companies, only the companies that haven't been configured yet (but don't care about the demo chart of accounts)
        #cr.execute("SELECT company_id FROM account_account WHERE active = 't' AND account_account.parent_id IS NULL AND name != %s", ("Chart For Automated Tests",))
        #configured_cmp = [r[0] for r in cr.fetchall()]
        #unconfigured_cmp = list(set(company_ids)-set(configured_cmp))

        unconfigured_cmp = company_ids
        
        for field in res['fields']:
           if field == 'company_id':
               res['fields'][field]['domain'] = [('id','in',unconfigured_cmp)]
               res['fields'][field]['selection'] = [('', '')]
               if unconfigured_cmp:
                   cmp_select = [(line.id, line.name) for line in self.pool.get('res.company').browse(cr, uid, unconfigured_cmp)]
                   res['fields'][field]['selection'] = cmp_select
        return res
    
account_installer()  

