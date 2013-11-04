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

class product_pricelist(osv.osv):
    
    _inherit = 'product.pricelist'
    
    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        pricelist = self.browse(cr, uid, res_id)
        return get_valid_xml_name(pricelist.name, pricelist.type)
    
product_pricelist()

class hq_entries(osv.osv):
    
    _inherit = 'hq.entries'
    
    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        if dest_field == 'cost_center_id':
            res = dict.fromkeys(ids, False)
            for line_data in self.browse(cr, uid, ids, context=context):
                if line_data.cost_center_id:
                    cost_center_name = line_data.cost_center_id and \
                                       line_data.cost_center_id.code and \
                                       line_data.cost_center_id.code[:3] or ""
                    cost_center_ids = self.pool.get('account.analytic.account').search(cr, uid, [('category', '=', 'OC'),
                                                                                                 ('code', '=', cost_center_name)], context=context)
                    if len(cost_center_ids) > 0:
                        target_ids = self.pool.get('account.target.costcenter').search(cr, uid, [('cost_center_id', '=', cost_center_ids[0]),
                                                                                                 ('is_target', '=', True)])
                        if len(target_ids) > 0:
                            target = self.pool.get('account.target.costcenter').browse(cr, uid, target_ids[0], context=context)
                            if target.instance_id and target.instance_id.instance:
                                res[line_data.id] = target.instance_id.instance
            return res
        return super(hq_entries, self).get_destination_name(cr, uid, ids, dest_field, context=context)

hq_entries()


class account_target_costcenter(osv.osv):
    
    _inherit = 'account.target.costcenter'
    
    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        if dest_field == 'instance_id':
            res = dict.fromkeys(ids, False)
            for target_line in self.browse(cr, uid, ids, context=context):
                if target_line.instance_id:
                    instance = target_line.instance_id
                    if instance.state == 'active':
                        res_data = [instance.instance]
                        # if it is a coordo instance, send it to its active projects as well
                        if instance.level == 'coordo':
                            for project in instance.child_ids:
                                if project.state == 'active':
                                    res_data.append(project.instance)
                        # if it is a project instance, send it to its active siblings as well
                        elif instance.level == 'project' and instance.parent_id:
                            for project in instance.parent_id.child_ids:
                                if project != instance and project.state == 'active':
                                    res_data.append(project.instance)
                        res[target_line.id] = res_data
            return res
        return super(account_target_costcenter, self).get_destination_name(cr, uid, ids, dest_field, context=context)
    
    def create(self, cr, uid, vals, context={}):
        res_id = super(account_target_costcenter, self).create(cr, uid, vals, context=context)
        # create lines in instance's children
        if 'instance_id' in vals:
            instance = self.pool.get('msf.instance').browse(cr, uid, vals['instance_id'], context=context)
            current_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
            if instance.state == 'active' and current_instance.level == 'section':
                # "touch" cost center if instance is active (to sync to new targets)
                self.pool.get('account.analytic.account').synchronize(cr, uid, [vals['cost_center_id']], context=context)
        return res_id

account_target_costcenter()

class account_analytic_account(osv.osv):
    
    _inherit = 'account.analytic.account'
    
    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        # get all active project instance with the cost center in one of its target lines 
        if dest_field == 'category':
            if isinstance(ids, (long, int)):
                ids = [ids]
            res = dict.fromkeys(ids, False)
            for id in ids:
                cr.execute("select instance_id from account_target_costcenter where cost_center_id = %s" % (id))
                instance_ids = [x[0] for x in cr.fetchall()]
                if len(instance_ids) > 0:
                    res_temp = []
                    for instance_id in instance_ids:
                        cr.execute("select instance from msf_instance where id = %s and state = 'active'" % (instance_id))
                        result = cr.fetchone()
                        if result:
                            res_temp.append(result[0])
                    res[id] = res_temp
            return res
        
        return super(account_analytic_account, self).get_destination_name(cr, uid, ids, dest_field, context=context)

    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        account = self.browse(cr, uid, res_id)
        return get_valid_xml_name(account.category, account.code, account.name)
 
account_analytic_account()

class msf_instance(osv.osv):
    
    _inherit = 'msf.instance'
    
    def create(self, cr, uid, vals, context=None):
        res_id = super(msf_instance, self).create(cr, uid, vals, context=context)
        current_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
        if 'state' in vals and 'parent_id' in vals and vals['state'] == 'active' and current_instance.level == 'section':
            instance = self.browse(cr, uid, res_id, context=context)
            # touch cost centers and account_Target_cc lines in order to sync them
            target_ids = [x.id for x in instance.target_cost_center_ids]
            self.pool.get('account.target.costcenter').synchronize(cr, uid, target_ids, context=context)
            
            cost_center_ids = [x.cost_center_id.id for x in instance.target_cost_center_ids]
            self.pool.get('account.analytic.account').synchronize(cr, uid, cost_center_ids, context=context)
                
            # also touch parent instance and lines from parent, since those were already sent to other instances
            if instance.parent_id and instance.parent_id.target_cost_center_ids and instance.level == 'project':
                parent_target_ids = [x.id for x in instance.parent_id.target_cost_center_ids]
                self.pool.get('account.target.costcenter').synchronize(cr, uid, parent_target_ids, context=context)
                # also also, re-send other projects' lines
                if instance.parent_id.child_ids:
                    sibling_target_ids = []
                    for sibling in instance.parent_id.child_ids:
                        if sibling != instance and sibling.state == 'active':
                            sibling_target_ids += [x.id for x in sibling.target_cost_center_ids]
                    self.pool.get('account.target.costcenter').synchronize(cr, uid, sibling_target_ids, context=context)
        
        return res_id

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        current_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
        if 'state' in vals and vals['state'] == 'active' and current_instance.level == 'section':
            for instance in self.browse(cr, uid, ids, context=context):
                if instance.state != 'active':
                    # only for now-activated instances (first push)
                    # touch cost centers and account_Target_cc lines in order to sync them
                    target_ids = [x.id for x in instance.target_cost_center_ids]
                    self.pool.get('account.target.costcenter').synchronize(cr, uid, target_ids, context=context)
                    
                    cost_center_ids = [x.cost_center_id.id for x in instance.target_cost_center_ids]
                    self.pool.get('account.analytic.account').synchronize(cr, uid, cost_center_ids, context=context)
                        
                    # also touch parent instance and lines from parent, since those were already sent to other instances
                    if instance.parent_id and instance.parent_id.target_cost_center_ids and instance.level == 'project':
                        parent_target_ids = [x.id for x in instance.parent_id.target_cost_center_ids]
                        self.pool.get('account.target.costcenter').synchronize(cr, uid, parent_target_ids, context=context)
                        # also also, re-send other projects' lines
                        if instance.parent_id.child_ids:
                            sibling_target_ids = []
                            for sibling in instance.parent_id.child_ids:
                                if sibling != instance and sibling.state == 'active':
                                    sibling_target_ids += [x.id for x in sibling.target_cost_center_ids]
                            self.pool.get('account.target.costcenter').synchronize(cr, uid, sibling_target_ids, context=context)
                        
        return super(msf_instance, self).write(cr, uid, ids, vals, context=context)

msf_instance()

class account_analytic_line(osv.osv):
    
    _inherit = 'account.analytic.line'
        
    def get_instance_name_from_cost_center(self, cr, uid, cost_center_id, context=None):
        if cost_center_id:
            target_ids = self.pool.get('account.target.costcenter').search(cr, uid, [('cost_center_id', '=', cost_center_id),
                                                                                     ('is_target', '=', True)])
            current_instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
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
        res = dict.fromkeys(ids, False)
        for line_data in self.browse(cr, uid, ids, context=context):
            if line_data.cost_center_id:
                res[line_data.id] = self.get_instance_name_from_cost_center(cr, uid, line_data.cost_center_id.id, context)
            elif current_instance.parent_id and current_instance.parent_id.instance:
                # Instance has a parent
                res[line_data.id] = current_instance.parent_id.instance
        return res
    
    def write(self, cr, uid, ids, vals, context=None):
        if not 'cost_center_id' in vals:
            return super(account_analytic_line, self).write(cr, uid, ids, vals, context=context)

        if isinstance(ids, (long, int)):
            ids = [ids]
        
        instance_name = self.pool.get("sync.client.entity").get_entity(cr, uid, context=context).name
        xml_ids = self.pool.get('ir.model.data').get(cr, uid, self, ids, context=context)
        line_data = self.read(cr, uid, ids, ['cost_center_id'], context=context)
        line_data = dict((data['id'], data) for data in line_data)
        for i,  xml_id_record in enumerate(self.pool.get('ir.model.data').browse(cr, uid, xml_ids, context=context)):
            xml_id = '%s.%s' % (xml_id_record.module, xml_id_record.name)
            old_cost_center_id = line_data[ids[i]]['cost_center_id'] and line_data[ids[i]]['cost_center_id'][0] or False
            
            new_cost_center_id = False
            if 'cost_center_id' in vals:
                new_cost_center_id = vals['cost_center_id']
            else:
                new_cost_center_id = old_cost_center_id
            
            old_destination_name = self.get_instance_name_from_cost_center(cr, uid, old_cost_center_id, context=context)
            new_destination_name = self.get_instance_name_from_cost_center(cr, uid, new_cost_center_id, context=context)
            
            if not old_destination_name == new_destination_name:
                # Send delete message, but not to parents of the current instance
                self.generate_message_for_destination(cr, uid, old_destination_name, xml_id, instance_name, send_to_parent_instances=False)
            

        return super(account_analytic_line, self).write(cr, uid, ids, vals, context=context)

account_analytic_line()

class funding_pool_distribution_line(osv.osv):
    _inherit = 'funding.pool.distribution.line'
    
    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        if not dest_field == 'cost_center_id':
            return super(funding_pool_distribution_line, self).get_destination_name(cr, uid, ids, dest_field, context=context)
        
        current_instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        res = dict.fromkeys(ids, False)
        for line_id in ids:
            line_data = self.browse(cr, uid, line_id, context=context)
            if line_data.cost_center_id:
                res[line_id] = self.pool.get('account.analytic.line').get_instance_name_from_cost_center(cr, uid, line_data.cost_center_id.id, context)
            elif current_instance.parent_id and current_instance.parent_id.instance:
                # Instance has a parent
                res[line_id] = current_instance.parent_id.instance
        return res
    
funding_pool_distribution_line()

class cost_center_distribution_line(osv.osv):
    _inherit = 'cost.center.distribution.line'
    
    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        if not dest_field == 'analytic_id':
            return super(cost_center_distribution_line, self).get_destination_name(cr, uid, ids, dest_field, context=context)
        
        current_instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        res = dict.fromkeys(ids, False)
        for line_id in ids:
            line_data = self.browse(cr, uid, line_id, context=context)
            if line_data.analytic_id:
                res[line_id] = self.pool.get('account.analytic.line').get_instance_name_from_cost_center(cr, uid, line_data.analytic_id.id, context)
            elif current_instance.parent_id and current_instance.parent_id.instance:
                # Instance has a parent
                res[line_id] = current_instance.parent_id.instance
        return res
    
cost_center_distribution_line()

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

class product_asset(osv.osv):
    
    _inherit = "product.asset"
    
    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        asset = self.browse(cr, uid, res_id)
        return get_valid_xml_name('product_asset', (asset.instance_id.code or 'noinstance'), (asset.name or 'noname'))
    
product_asset()

class batch_number(osv.osv):
    _inherit = "stock.production.lot"
    
    #UF-1617: unique xml id for batch number with instance id
    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        batch = self.browse(cr, uid, res_id)
        return get_valid_xml_name('batch_numer', (batch.instance_id.code or 'noinstance'), (batch.name or 'noname'))
    
batch_number()

class ir_model_access(osv.osv):
    """
    UF-2146 To allow synchronisation of ir.model.access, must have same sd ref across all instances
    """
    _inherit = "ir.model.access"
    
    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        ima = self.browse(cr, uid, res_id)
        return get_valid_xml_name(
                  'ir_model_access', 
                  self.pool.get('ir.model').get_sd_ref(cr, uid, ima.model_id.id),
                  ima.name
                )
    
ir_model_access()

class ir_model(osv.osv):
    """
    UF-2146 sd ref for ir.model to be included in sd ref of ir.model.access
    """
    _inherit = 'ir.model'
    
    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        model = self.browse(cr, uid, res_id)
        return get_valid_xml_name('ir_model', model.model)

ir_model()

class button_access_rule(osv.osv):
    """
    Generate an xml ID like BAR_$view-xml-id_$button-name
    so rules can be synchronized between instances after being generated at each instance
    """
    _inherit = 'msf_button_access_rights.button_access_rule'

    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        bar = self.browse(cr, uid, res_id)
        view_xml_id = self.pool.get('ir.ui.view').get_xml_id(cr, 1, [bar.view_id.id])
        return get_valid_xml_name('BAR', view_xml_id[bar.view_id.id], bar.name)

button_access_rule()
