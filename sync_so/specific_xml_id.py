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

# !! Please always use this method before returning an xml_name
#    It will automatically convert arguments to strings, remove False args
#    and finally remove all dots (unexpected dots appears when the system
#    language is not english)
def get_valid_xml_name(*args):
    return u"_".join(map(lambda x: unicode(x), filter(None, args))).replace('.', '')

class fiscal_year(osv.osv):
    
    _inherit = 'account.fiscalyear'
    
    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        fiscalyear = self.browse(cr, uid, res_id)
        return get_valid_xml_name(fiscalyear.code)
    
fiscal_year()

class account_journal(osv.osv):
    
    _inherit = 'account.journal'
    
    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        journal = self.browse(cr, uid, res_id)
        return get_valid_xml_name('journal', (journal.instance_id.code or 'noinstance'), (journal.code or 'nocode'), (journal.name or 'noname'))
    
account_journal()

class bank_statement(osv.osv):
    
    _inherit = 'account.bank.statement'
    
    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        bank = self.browse(cr, uid, res_id)
        # to be unique, the journal xml_id must include also the period, otherwise no same name journal cannot be inserted for different periods! 
        unique_journal = (bank.journal_id.code or 'nojournal') + '_' + (bank.period_id.name or 'noperiod')
        return get_valid_xml_name('bank_statement', (bank.instance_id.code or 'noinstance'), (bank.name or 'nobank'), unique_journal)
    
    def update_xml_id_register(self, cr, uid, res_id, context):
        """
        Reupdate the xml_id of the register once the button Open got clicked. Because in draft state the period can be modified,
        the xml_id is no more relevant to the register. After openning the register, the period is readonly, xml_id is thus safe
        """
        bank = self.browse(cr, uid, res_id) # search the fake xml_id
        model_data_obj = self.pool.get('ir.model.data')
        
        # This one is to get the prefix of the bank_statement for retrieval of the correct xml_id       
        prefix = get_valid_xml_name('bank_statement', (bank.instance_id.code or 'noinstance'), (bank.name or 'nobank'))
        
        data_ids = model_data_obj.search(cr, uid, [('model', '=', self._name), ('res_id', '=', res_id), ('name', 'like', prefix), ('module', '=', 'sd')], limit=1, context=context)
        xml_id = self.get_unique_xml_name(cr, uid, False, self._table, res_id)
        
        existing_xml_id = False
        if data_ids:
            existing_xml_id = model_data_obj.read(cr, uid, data_ids[0], ['name'])['name']
        if xml_id != existing_xml_id:
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
        return get_valid_xml_name(period.fiscalyear_id.code+"/"+period.name, period.date_start)
    
account_period_sync()

class res_currency_sync(osv.osv):
    
    _inherit = 'res.currency'
    
    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        currency = self.browse(cr, uid, res_id)
        return get_valid_xml_name(currency.name, (currency.currency_table_id and currency.currency_table_id.name))
    
res_currency_sync()


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
                        instance_data = self.pool.get('msf.instance').read(cr, uid, instance_ids[0], ['instance'], context=context)
                        res.append(instance_data['instance'])
                    else:
                        res.append(False)
                else:
                    res.append(False)
            return res
        return super(hq_entries, self).get_destination_name(cr, uid, ids, dest_field, context=context)

hq_entries()

from sync_common.common import format_data_per_id 
from sync_client.ir_model_data import generate_message_for_destination


class account_analytic_line(osv.osv):
    
    _inherit = 'account.analytic.line'
    _delete_owner_field = 'cost_center_id'
    
    def get_instance_name_from_cost_center(self, cr, uid, cost_center_id, context=None):
        instance_ids = self.pool.get('msf.instance').search(cr, uid, [('cost_center_id', '=', cost_center_id)], context=context)
        if instance_ids:
            instance_data = self.pool.get('msf.instance').read(cr, uid, instance_ids[0], ['instance'], context=context)
            return instance_data['instance']
        else:
            return False
    
    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        if not dest_field == 'cost_center_id':
            return super(account_analytic_line, self).get_destination_name(cr, uid, ids, dest_field, context=context)
        
        cost_center_data = self.read(cr, uid, ids, [dest_field], context=context)
        res = []
        for data in cost_center_data:
            if data['cost_center_id']:
                cost_center_id = data['cost_center_id'][0]
                print cost_center_id
                res.append(self.get_instance_name_from_cost_center(cr, uid, cost_center_id, context))
            else:
                res.append(False)
        return res
        
account_analytic_line()

class product_product(osv.osv):
    _inherit = 'product.product'

    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        product = self.browse(cr, uid, res_id)
        return get_valid_xml_name('product', product.default_code) if product.default_code else \
               super(product_product, self).get_unique_xml_name(cr, uid, uuid, table_name, res_id)

    def write(self, cr, uid, ids, vals, context=None):
        list_ids = []
        if 'default_code' in vals:
            list_ids = (ids if hasattr(ids, '__iter__') else [ids])
            browse_list = self.browse(cr, uid, list_ids, context=context)
            browse_list = filter(lambda x:x.default_code != vals['default_code'], browse_list)
            list_ids = [x.id for x in browse_list]
        res = super(product_product, self).write(cr, uid, ids, vals, context=context)
        if list_ids:
            entity_uuid = self.pool.get('sync.client.entity').get_entity(cr, uid, context=context).identifier
            model_data = self.pool.get('ir.model.data')
            data_ids = model_data.search(cr, uid, [('module','=','sd'),('model','=',self._name),('res_id','in',list_ids)], context=context)
            model_data.unlink(cr, uid, data_ids)
            now = fields.datetime.now()
            for id in list_ids:
                xml_name = self.get_unique_xml_name(cr, uid, entity_uuid, self._table, id)
                model_data.create(cr, uid, {
                    'module' : 'sd',
                    'noupdate' : False, # don't set to True otherwise import won't work
                    'name' : xml_name,
                    'model' : self._name,
                    'res_id' : id,
                    'last_modification' : now,
                })
        return res
        

product_product()
