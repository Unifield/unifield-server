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
                    cost_center_ids = self.pool.get('account.analytic.account').search(cr, uid, [('category', '=', 'OC'),
                                                                                                 ('code', '=', cost_center_name)], context=context)
                    if len(cost_center_ids) > 0:
                        target_ids = self.pool.get('account.target.costcenter').search(cr, uid, [('cost_center_id', '=', cost_center_ids[0]),
                                                                                                 ('is_target', '=', True)])
                        if len(target_ids) > 0:
                            target = self.pool.get('account.target.costcenter').browse(cr, uid, target_ids[0], context=context)
                            if target.instance_id and target.instance_id.instance:
                                res.append(target.instance_id.instance)
                            else:
                                res.append(False)
                        else:
                            res.append(False)
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
    
    def get_xml_id_from_reference(self, cr, uid, line_ref, context=None):
        if line_ref:
            (line_model, line_id) = line_ref.split(',')
            xml_ids = self.pool.get('ir.model.data').get(cr,
                                                         uid,
                                                         self.pool.get(line_model),
                                                         [line_id],
                                                         context=context)
            if len(xml_ids) > 0:
                xml_record = self.pool.get('ir.model.data').browse(cr, uid, xml_ids[0], context=context)
                return '%s.%s' % (xml_record.module, xml_record.name)
        return False

    def write_reference_to_destination(self, cr, uid, reference, reference_field, destination_name, xml_id, instance_name):
        instance_obj = self.pool.get('msf.instance')
        
        if not destination_name or not reference:
            return
        if destination_name != instance_name:
            reference_xml_id = self.get_xml_id_from_reference(cr, uid, reference, context={})
            message_data = {
                    'identifier' : 'write_%s_reference_to_%s' % (xml_id, destination_name),
                    'sent' : False,
                    'generate_message' : True,
                    'remote_call': self._name + ".message_write_reference",
                    'arguments': "[{'model' :  '%s', 'xml_id' : '%s', 'field': '%s', 'reference' : '%s'}]" % (self._name, xml_id, reference_field, reference_xml_id),
                    'destination_name': destination_name
            }
            self.pool.get("sync.client.message_to_send").create(cr, uid, message_data)
        # generate message for parent instance
        instance_ids = instance_obj.search(cr, uid, [("instance", "=", destination_name)])
        if instance_ids:
            instance_record = instance_obj.browse(cr, uid, instance_ids[0])
            parent = instance_record.parent_id and instance_record.parent_id.instance or False
            if parent:
                self.write_reference_to_destination(cr, uid, reference, reference_field, parent, xml_id, instance_name)
        
    def get_instance_name_from_cost_center(self, cr, uid, cost_center_id, context=None):
        if cost_center_id:
            target_ids = self.pool.get('account.target.costcenter').search(cr, uid, [('cost_center_id', '=', cost_center_id),
                                                                                       ('is_target', '=', True)])
            current_instance_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
            if len(target_ids) > 0:
                target = self.pool.get('account.target.costcenter').browse(cr, uid, target_ids[0], context=context)
                if target.instance_id and target.instance_id.instance:
                    return target.instance_id.instance
                
            if current_instance.parent_id and current_instance.parent_id.instance:
                # Instance has a parent
                return current_instance.parent_id.instance
            else:
                return False
        else:
            return False
    
    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        if not dest_field == 'cost_center_id':
            return super(account_analytic_line, self).get_destination_name(cr, uid, ids, dest_field, context=context)
        
        current_instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        cost_center_data = self.read(cr, uid, ids, [dest_field], context=context)
        res = []
        for data in cost_center_data:
            if data['cost_center_id']:
                cost_center = self.pool.get('account.analytic.account').browse(cr, uid, data['cost_center_id'][0], context=context)
                res.append(self.get_instance_name_from_cost_center(cr, uid, cost_center.code, context))
            elif current_instance.parent_id and current_instance.parent_id.instance:
                # Instance has a parent
                res.append(current_instance.parent_id.instance)
            else:
                res.append(False)
        return res
    
    def write(self, cr, uid, ids, vals, context=None):
        if not 'cost_center_id' in vals and not 'distrib_line_id' in vals:
            return super(account_analytic_line, self).write(cr, uid, ids, vals, context=context)

        if isinstance(ids, (long, int)):
            ids = [ids]
        
        instance_name = self.pool.get("sync.client.entity").get_entity(cr, uid, context=context).name
        xml_ids = self.pool.get('ir.model.data').get(cr, uid, self, ids, context=context)
        line_data = format_data_per_id(self.read(cr, uid, ids, ['cost_center_id'], context=context))
        for i,  xml_id_record in enumerate(self.pool.get('ir.model.data').browse(cr, uid, xml_ids, context=context)):
            xml_id = '%s.%s' % (xml_id_record.module, xml_id_record.name)
            old_cost_center_id = line_data[ids[i]]['cost_center_id'] and line_data[ids[i]]['cost_center_id'][0] or False
            
            new_cost_center_id = False
            if 'cost_center_id' in vals:
                new_cost_center_id = vals['cost_center_id']
            else:
                new_cost_center_id = old_cost_center_id
            
            old_cost_center = self.pool.get('account.analytic.account').browse(cr, uid, old_cost_center_id, context=context)
            old_destination_name = self.get_instance_name_from_cost_center(cr, uid, old_cost_center.code, context=context)
            new_cost_center = self.pool.get('account.analytic.account').browse(cr, uid, new_cost_center_id, context=context)
            new_destination_name = self.get_instance_name_from_cost_center(cr, uid, new_cost_center.code, context=context)
            
            if not old_destination_name == new_destination_name:
                # Send delete message, but not to parents of the current instance
                generate_message_for_destination(self, cr, uid, old_destination_name, xml_id, instance_name, send_to_parent_instances=False)
            elif 'distrib_line_id' in vals:
                self.write_reference_to_destination(cr, uid, vals['distrib_line_id'], 'distrib_line_id', new_destination_name, xml_id, instance_name)
            

        return super(account_analytic_line, self).write(cr, uid, ids, vals, context=context)
    
    def create(self, cr, uid, vals, context=None):
        res_id = super(account_analytic_line, self).create(cr, uid, vals, context=context)
        
        if 'distrib_line_id' in vals and 'cost_center_id' in vals and res_id:
            instance_name = self.pool.get("sync.client.entity").get_entity(cr, uid, context=context).name
            cost_center_id = vals['cost_center_id']
            xml_ids = self.pool.get('ir.model.data').get(cr, uid, self, [res_id], context=context)
            if xml_ids[0]:
                xml_id_record = self.pool.get('ir.model.data').browse(cr, uid, xml_ids, context=context)[0]
                xml_id = '%s.%s' % (xml_id_record.module, xml_id_record.name)
                cost_center = self.pool.get('account.analytic.account').browse(cr, uid, cost_center_id, context=context)
                destination_name = self.get_instance_name_from_cost_center(cr, uid, cost_center.code, context=context)
                self.write_reference_to_destination(cr, uid, vals['distrib_line_id'], 'distrib_line_id', destination_name, xml_id, instance_name)

        return res_id

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
