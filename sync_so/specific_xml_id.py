'''
Created on 15 mai 2012

@author: openerp
'''

from osv import osv
from osv import fields

# Note:
#
#     * Only the required fields need a " or 'no...' " next to their use.
#     * Beware to check that many2one fields exists before using their property
#

class fiscal_year(osv.osv):
    
    _inherit = 'account.fiscalyear'
    
    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        fiscalyear = self.browse(cr, uid, res_id)
        return fiscalyear.code
    
fiscal_year()

class account_journal(osv.osv):
    
    _inherit = 'account.journal'
    
    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        journal = self.browse(cr, uid, res_id)
        return 'journal_' + (journal.instance_id.code or 'noinstance') + "_" + (journal.code or 'nocode') + "_" + (journal.name or 'noname')
    
account_journal()

class bank_statement(osv.osv):
    
    _inherit = 'account.bank.statement'
    
    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        bank = self.browse(cr, uid, res_id)
        # to be unique, the journal xml_id must include also the period, otherwise no same name journal cannot be inserted for different periods! 
        unique_journal = (bank.journal_id.code or 'nojournal') + '_' + (bank.period_id.name or 'noperiod')
        return 'bank_statement_' + (bank.instance_id.code or 'noinstance') + '_' + (bank.name or 'nobank') + '_' + unique_journal 
    
bank_statement()

class account_period_sync(osv.osv):
    
    _inherit = "account.period"
    
    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        period = self.browse(cr, uid, res_id)
        return period.fiscalyear_id.code + "/" + period.name + "_" + period.date_start
    
account_period_sync()

class res_currency_sync(osv.osv):
    
    _inherit = 'res.currency'
    
    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        currency = self.browse(cr, uid, res_id)
        table_name = currency.currency_table_id and currency.currency_table_id.name or ''
        return currency.name + table_name
    
res_currency_sync()
