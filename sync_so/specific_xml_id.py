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
    
    def update_xml_id_register(self, cr, uid, res_id, context):
        """
        Reupdate the xml_id of the register once the button Open got clicked. Because in draft state the period can be modified,
        the xml_id is no more relevant to the register. After openning the register, the period is readonly, xml_id is thus safe
        """
        bank = self.browse(cr, uid, res_id) # search the fake xml_id
        model_data_obj = self.pool.get('ir.model.data')
        data_ids = model_data_obj.search(cr, uid, [('model', '=', self._name), ('res_id', '=', res_id), ('module', '=', 'sd')], limit=1, context=context)
        xml_id = self.get_unique_xml_name(cr, uid, False, self._table, res_id)
        model_data_obj.write(cr, uid, data_ids, {'name': xml_id}, context=context)
        return True

    def button_open_bank(self, cr, uid, ids, context=None):
        res = super(bank_statement, self).button_open_bank(cr, uid, ids, context=context)
        self.update_xml_id_register(cr, uid, ids[0], context)
        return res
    
    def button_open_cheque(self, cr, uid, ids, context=None):
        res = super(bank_statement, self).button_open_cheque(cr, uid, ids, context=context)
        self.update_xml_id_register(cr, uid, ids[0], context)
        return res

    def button_open_cash(self, cr, uid, ids, context=None):
        """
        The update of xml_id may be done when opening the register 
        --> set the value of xml_id based on the period as period is no more modifiable
        """
        res = super(bank_statement, self).button_open_cash(cr, uid, ids, context=context)
        self.update_xml_id_register(cr, uid, ids[0], context)
        return res
    
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

class product_product(osv.osv):
    
    _inherit = 'product.product'
    
    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        product = self.browse(cr, uid, res_id)
        if product.id:
            # the xml_id is based on the id because at the creation of a product we don't have product_code
            return str(product.id) + table_name
    
product_product()

class hq_entries(osv.osv):
    
    _inherit = 'hq.entries'
    
    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        if dest_field == 'cost_center_id':
            cost_center_data = self.read(cr, uid, ids, [dest_field], context=context)
            res = []
            for data in cost_center_data:
                if data['cost_center_id']:
                    cost_center_name = data['cost_center_id'][1][:3]
                    instance_ids = self.pool.get('msf.instance').search(cr, uid, [('cost_center_id', 'like', cost_center_name), ('level', '=', 'coordo')], context=context)
                    if instance_ids:
                        instance_data = self.pool.get('msf.instance').read(cr, uid, instance_ids[0], ['name'], context=context)
                        res.append(instance_data['name'])
                    else:
                        res.append(False)
                else:
                    res.append(False)
            return res
        return super(hq_entries, self).get_destination_name(cr, uid, ids, dest_field, context=context)

hq_entries()
