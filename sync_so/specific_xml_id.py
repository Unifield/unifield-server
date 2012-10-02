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
        xml_id = 'bank_statement_' + (bank.instance_id.code or 'noinstance') + '_' + (bank.name or 'nobank')
        if bank and bank.state == 'draft':
            # !!!!! This xml_id is only for temporary, it will be reupdated when the register got opened!
            # Because if the period of the register can be modified, then the xml_id get lost, the mapping is no more valid!!!!
            xml_id += '_' + str(res_id) 
        return xml_id + '_' + unique_journal
    
    
    def button_open(self, cr, uid, ids, context=None):
        """
        The update of xml_id may be done when opening the register 
        --> set the value of xml_id based on the period as period is no more modifiable
        """
        if not ids:
            return False
        res_id = ids[0]

        # call the super class to do the job as usual
        super(bank_statement, self).button_open(cr, uid, ids, context=context)
        
        bank = self.browse(cr, uid, res_id)
        # search the fake xml_id
        model_data_obj = self.pool.get('ir.model.data')
        data_ids = model_data_obj.search(cr, uid, [('model', '=', self._name), ('res_id', '=', res_id), ('module', '=', 'sd')], limit=1, context=context) 
    
        unique_journal = (bank.journal_id.code or 'nojournal') + '_' + (bank.period_id.name or 'noperiod')
        xml_id = 'bank_statement_' + (bank.instance_id.code or 'noinstance') + '_' + (bank.name or 'nobank') + '_' + unique_journal
        model_data_obj.write(cr, uid, data_ids, {'name': xml_id}, context=context)
        return True
    
    
    def write(self, cr, uid, ids, vals, context=None):
        """
        special method: update the CORRECT xml_id of the register when it got opened (remove the db ID created in draft state)
        
        """
        if not ids:
            return False
        res_id = ids[0]

        # get the old state            
        old_state = self.browse(cr, uid, res_id).state
        # call the super class to do the job as usual
        super(bank_statement, self).write(cr, uid, ids, vals, context=context)
        
        bank = self.browse(cr, uid, res_id)
        
        # state change from draft to open ---> update the correct xml_id with "period" which will not be modifiable anymore!
        if bank.state == 'open' and bank.state != old_state:
            # search the fake xml_id
            model_data_obj = self.pool.get('ir.model.data')
            data_ids = model_data_obj.search(cr, uid, [('model', '=', self._name), ('res_id', '=', res_id), ('module', '=', 'sd')], limit=1, context=context) 
        
            unique_journal = (bank.journal_id.code or 'nojournal') + '_' + (bank.period_id.name or 'noperiod')
            xml_id = 'bank_statement_' + (bank.instance_id.code or 'noinstance') + '_' + (bank.name or 'nobank') + '_' + unique_journal
            model_data_obj.write(cr, uid, data_ids, {'name': xml_id}, context=context)
        return True
    
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
