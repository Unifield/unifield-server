'''
Created on 15 mai 2012

@author: openerp
'''

from osv import osv
from osv import fields
from product_nomenclature.product_nomenclature import RANDOM_XMLID_CODE_PREFIX
import time
import netsvc
from tools.translate import _

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
    return "_".join([str(x) for x in [_f for _f in args if _f]]).replace('.', '').replace(',', '_')

class res_groups(osv.osv):
    _inherit = 'res.groups'

    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        group_name = self.browse(cr, uid, res_id, fields_to_fetch=['name']).name
        return get_valid_xml_name('res_groups', group_name)

res_groups()

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


class ir_actions_act_window(osv.osv):
    _inherit = 'ir.actions.act_window'

    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        model_data_obj = self.pool.get('ir.model.data')
        sdref_ids = model_data_obj.search(cr, uid, [('model','=',self._name),('res_id','=',res_id),('module','!=','sd')])
        if not sdref_ids:
            return super(ir_actions_act_window, self).get_unique_xml_name(cr, uid, uuid, table_name, res_id)
        origin_xmlid = model_data_obj.read(cr, uid, sdref_ids[0], ['module', 'name'])
        return get_valid_xml_name(origin_xmlid['module'], origin_xmlid['name'])

    def _get_is_remote_wh(self, cr, uid, ids, field_name, args, context=None):
        return {}.fromkeys(ids, False)

    def _search_is_remote_wh(self, cr, uid, obj, name, args, context=None):
        if not args:
            return []
        rarg = []
        for arg in args:
            if arg[1] != '=':
                raise osv.except_osv('Error', 'Filter on is_remote_wh not implemented')
            model_data_obj = self.pool.get('ir.model.data')
            mod_ids = model_data_obj.search(cr, uid, [('model', '=', obj._name), ('module', '=', 'sync_remote_warehouse')])
            ids = []
            for m in model_data_obj.read(cr, uid, mod_ids, ['res_id']):
                ids.append(m['res_id'])
            value = arg[2] not in (False, 'f', 'False')
            rarg.append(('id', value and 'in' or 'not in', ids))
        return rarg

    _columns = {
        'is_remote_wh': fields.function(_get_is_remote_wh, type='boolean', string="From RW module", fnct_search=_search_is_remote_wh, method=True),
    }
ir_actions_act_window()


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

    def get_target_id(self, cr, uid, cost_center_id, context=None):
        """
        Returns the id of the target CC linked to the cost_center_id, or to its parent if there isn't any.
        """
        if context is None:
            context = {}
        target_ids = []
        if cost_center_id:
            analytic_cc_obj = self.pool.get('account.analytic.account')
            target_cc_obj = self.pool.get('account.target.costcenter')
            target_ids = target_cc_obj.search(cr, uid,
                                              [('cost_center_id', '=', cost_center_id), ('is_target', '=', True)],
                                              context=context)
            if not target_ids:
                cc = analytic_cc_obj.browse(cr, uid, cost_center_id, fields_to_fetch=['parent_id'], context=context)
                if cc and cc.parent_id:
                    target_ids = target_cc_obj.search(cr, uid,
                                                      [('cost_center_id', '=', cc.parent_id.id), ('is_target', '=', True)],
                                                      context=context)
        return target_ids and target_ids[0] or False

    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        """
        Gets the instances to which the HQ entries should sync.
        For each HQ entry:
        1) Search for the instance:
           - to which the CC used in the entry is targeted to
           - if there isn't any, to which the PARENT CC is targeted to
           - if not (CC is IM targeted) -> send to HQ
        2) The entry will sync to the coordo of the corresponding mission if any or HQ
        """
        if context is None:
            context = {}
        target_cc_obj = self.pool.get('account.target.costcenter')
        if dest_field == 'cost_center_id':
            res = dict.fromkeys(ids, False)
            current_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
            for line_data in self.browse(cr, uid, ids, context=context):
                if line_data.cost_center_id:
                    targeted_instance = False
                    target_id = self.get_target_id(cr, uid, line_data.cost_center_id.id, context=context)
                    if target_id:
                        target = target_cc_obj.browse(cr, uid, target_id, fields_to_fetch=['instance_id'], context=context)
                        if target.instance_id.level == 'coordo':
                            targeted_instance = target.instance_id
                        elif target.instance_id.level == 'project':
                            targeted_instance = target.instance_id.parent_id or False
                    if not target_id and current_instance and current_instance.parent_id:
                        # CC is intermission targeted / send to HQ
                        targeted_instance = current_instance.parent_id

                    if targeted_instance:
                        res[line_data.id] = targeted_instance.instance
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
                            project_instances = []
                            for project in instance.child_ids:
                                if project.state == 'active':
                                    project_instances.append(project.instance)
                            if project_instances:
                                # OC updates sent to project are also retrieved by coordo
                                res_data = project_instances
                        # if it is a project instance, send it to its active siblings as well
                        elif instance.level == 'project' and instance.parent_id:
                            for project in instance.parent_id.child_ids:
                                if project != instance and project.state == 'active':
                                    res_data.append(project.instance)
                        res[target_line.id] = res_data
            return res
        return super(account_target_costcenter, self).get_destination_name(cr, uid, ids, dest_field, context=context)

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        res_id = super(account_target_costcenter, self).create(cr, uid, vals, context=context)
        # create lines in instance's children
        if 'instance_id' in vals:
            instance = self.pool.get('msf.instance').browse(cr, uid, vals['instance_id'], context=context)
            current_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
            if instance.state == 'active' and current_instance.level == 'section':
                # "touch" cost center if instance is active (to sync to new targets)
                self.pool.get('account.analytic.account').synchronize(cr, uid, [vals['cost_center_id']], context=context)
        return res_id

    def unlink(self, cr, uid, ids, context=None):
        ''' target CC deletion: set the inactivation date on CC '''

        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        if context.get('sync_update_execution'):
            to_inactivate = []
            now = time.strftime('%Y-%m-%d')
            current_instance_id = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id'], context=context).company_id.instance_id.id
            search_target = self.search(cr, uid, [('id', 'in', ids), ('instance_id', '=', current_instance_id)], context=context)
            for cc in self.browse(cr, uid, search_target, fields_to_fetch=['cost_center_id', 'instance_id'], context=context):
                if cc.cost_center_id and (not cc.cost_center_id.date or cc.cost_center_id.date > now):
                    to_inactivate.append(cc.cost_center_id.id)
            if to_inactivate:
                self.pool.get('account.analytic.account').write(cr, uid, to_inactivate, {'date': now}, context=context)

        return super(account_target_costcenter, self).unlink(cr, uid, ids, context)

account_target_costcenter()

class account_analytic_account(osv.osv):

    _inherit = 'account.analytic.account'

    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        # get all active project instance with the cost center in one of its target lines
        if dest_field == 'category':
            if isinstance(ids, int):
                ids = [ids]
            res = dict.fromkeys(ids, False)
            for account_id in ids:
                cr.execute("select instance_id from account_target_costcenter where cost_center_id = %s", (account_id,))
                instance_ids = [x[0] for x in cr.fetchall()]
                if len(instance_ids) > 0:
                    res_temp = []
                    for instance_id in instance_ids:
                        cr.execute("select instance from msf_instance where id = %s and state = 'active'", (instance_id,))
                        result = cr.fetchone()
                        if result:
                            res_temp.append(result[0])
                    res[account_id] = res_temp
            return res

        # UFTP-2: Get the children of the given instance and create manually sync updates for them, only when it is Coordo
        if dest_field == 'instance_id':
            ## Check if it is *funding pool* and created at HQ
            return self.get_coordo_and_project_dest(cr, uid, ids, dest_field, context)

        return super(account_analytic_account, self).get_destination_name(cr, uid, ids, dest_field, context=context)

    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        account = self.read(cr, uid, res_id, ['code', 'name', 'category'])
        if account and account['code'] in ('OC', 'cc-intermission', 'FUNDING',
                                           'FREE1', 'FREE2', 'PF', 'DEST',
                                           'OPS', 'SUP', 'NAT', 'EXP'):
            # specific account created on each instances by xml data file, should have the same xmlid
            return get_valid_xml_name(account['category'], account['code'], account['name'])
        return super(account_analytic_account, self).get_unique_xml_name(cr, uid, uuid, table_name, res_id)

account_analytic_account()

class dest_cc_link(osv.osv):
    _inherit = 'dest.cc.link'

    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        '''
            same destination as CC
        '''
        if not ids:
            return []

        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}
        res = dict.fromkeys(ids, False)
        mapping = {}
        uniq_cc_ids = {}
        inst_obj = self.pool.get('msf.instance')
        for dest_cc_link in self.browse(cr, uid, ids, fields_to_fetch=['cc_id'], context=context):
            mapping[dest_cc_link.id] = dest_cc_link.cc_id.id
            uniq_cc_ids[dest_cc_link.cc_id.id] = True
        cc_destination = self.pool.get('account.analytic.account').get_destination_name(cr, uid, uniq_cc_ids.keys(), 'category', context)
        for dest_cc_link_id in mapping:
            inst_list = cc_destination.get(mapping[dest_cc_link_id], [])
            # create a new list from which the coordos with active projects are excluded
            # (no need to generate an update for them as they will pull those from their projects)
            new_inst_list = []
            if inst_list:
                inst_ids = inst_obj.search(cr, uid, [('instance', 'in', inst_list)], order='NO_ORDER', context=context)
                for inst in inst_obj.browse(cr, uid, inst_ids, fields_to_fetch=['level', 'instance'], context=context):
                    if inst.level != 'coordo':
                        new_inst_list.append(inst.instance)
                    elif not inst_obj.search_exist(cr, uid, [('parent_id', '=', inst.id), ('state', '=', 'active')], context=context):
                        new_inst_list.append(inst.instance)
            res[dest_cc_link_id] = new_inst_list

        return res

dest_cc_link()

#US-113: Sync only to the mission with attached prop instance
class financing_contract_contract(osv.osv):
    _inherit = 'financing.contract.contract'

    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        # BKLG-34: Get the children of the given instance and create manually sync updates for them, only when it is Coordo
        if dest_field == 'instance_id':
            return self.get_coordo_and_project_dest(cr, uid, ids, dest_field, context)

        return super(financing_contract_contract, self).get_destination_name(cr, uid, ids, dest_field, context=context)

financing_contract_contract()

#US-113: Sync only to the mission with attached prop instance
class financing_contract_funding_pool_line(osv.osv):

    _inherit = 'financing.contract.funding.pool.line'

    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        # BKLG-34: Get the children of the given instance and create manually sync updates for them, only when it is Coordo
        if dest_field == 'instance_id':
            return self.get_coordo_and_project_dest(cr, uid, ids, dest_field, context)

        return super(financing_contract_funding_pool_line, self).get_destination_name(cr, uid, ids, dest_field, context=context)

financing_contract_funding_pool_line()

#US-113: Sync only to the mission with attached prop instance
class financing_contract_format(osv.osv):

    _inherit = 'financing.contract.format'

    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        # BKLG-34: Get the children of the given instance and create manually sync updates for them, only when it is Coordo
        if dest_field == 'hidden_instance_id':
            return self.get_coordo_and_project_dest(cr, uid, ids, dest_field, context)

        return super(financing_contract_format, self).get_destination_name(cr, uid, ids, dest_field, context=context)

financing_contract_format()

#US-113: Sync only to the mission with attached prop instance
class financing_contract_format_line(osv.osv):
    _inherit = 'financing.contract.format.line'
    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        # BKLG-34: Get the children of the given instance and create manually sync updates for them, only when it is Coordo
        if dest_field == 'instance_id':
            return self.get_coordo_and_project_dest(cr, uid, ids, dest_field, context)

        return super(financing_contract_format_line, self).get_destination_name(cr, uid, ids, dest_field, context=context)

financing_contract_format_line()

class msf_instance(osv.osv):

    _inherit = 'msf.instance'

    def _synchronize_cc_related_fields(self, cr, uid, instance, context=None):
        """
        "Touch" the CC, Target CC, and Dest CC Links linked to the instance, in order to include them in the next synchro.
        For Target CC (unique by CC/Inst) those from the parent instance and from other projects are also re-sent if applicable.
        """
        if context is None:
            context = {}
        target_ids = [x.id for x in instance.target_cost_center_ids]
        self.pool.get('account.target.costcenter').synchronize(cr, uid, target_ids, context=context)
        cost_center_ids = [x.cost_center_id.id for x in instance.target_cost_center_ids]
        self.pool.get('account.analytic.account').synchronize(cr, uid, cost_center_ids, context=context)
        if cost_center_ids:
            dcl_ids = self.pool.get('dest.cc.link').search(cr, uid, [('cc_id', 'in', cost_center_ids)], order='NO_ORDER', context=context)
            self.pool.get('dest.cc.link').sql_synchronize(cr, dcl_ids, field='cc_id')
        if instance.parent_id and instance.parent_id.target_cost_center_ids and instance.level == 'project':
            parent_target_ids = [x.id for x in instance.parent_id.target_cost_center_ids]
            self.pool.get('account.target.costcenter').synchronize(cr, uid, parent_target_ids, context=context)
            if instance.parent_id.child_ids:
                sibling_target_ids = []
                for sibling in instance.parent_id.child_ids:
                    if sibling != instance and sibling.state == 'active':
                        sibling_target_ids += [x.id for x in sibling.target_cost_center_ids]
                self.pool.get('account.target.costcenter').synchronize(cr, uid, sibling_target_ids, context=context)
        return True

    def create(self, cr, uid, vals, context=None):
        res_id = super(msf_instance, self).create(cr, uid, vals, context=context)
        current_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
        if 'state' in vals and 'parent_id' in vals and vals['state'] == 'active' and current_instance.level == 'section':
            instance = self.browse(cr, uid, res_id, context=context)
            self._synchronize_cc_related_fields(cr, uid, instance, context=context)
        return res_id

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if isinstance(ids, int):
            ids = [ids]

        if context is None:
            context = {}

        changed_state_ids = []

        if context.get('sync_update_execution') and vals.get('state') in ['active', 'inactive']:
            if vals.get('state') == 'inactive' and self._has_undisposed_assets(cr, uid, ids, context=context):
                raise osv.except_osv(_('Error'), _('The instance cannot be decommissioned yet, it still owns undisposed assets.'))
            changed_state_ids = self.search(cr, uid, [('id', 'in', ids), ('state', '!=', vals['state'])], context=context)

        current_instance = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
        if 'state' in vals and vals['state'] == 'active' and current_instance.level == 'section':
            for instance in self.browse(cr, uid, ids, context=context):
                if instance.state != 'active':
                    # only for now-activated instances (first push)
                    self._synchronize_cc_related_fields(cr, uid, instance, context=context)
                    if instance.level == 'project' and instance.parent_id:
                        self.pool.get('sync.trigger.something.target.lower').create(cr, uid, {'name': 'sync_fp', 'destination': instance.parent_id.instance}, context={})

        res = super(msf_instance, self).write(cr, uid, ids, vals, context=context)
        if changed_state_ids:
            partner_obj = self.pool.get('res.partner')
            for instance in self.browse(cr, uid, changed_state_ids, fields_to_fetch=['instance'], context=context):
                active = vals['state'] == 'active'
                p_id = partner_obj.search(cr, uid, [('partner_type', '=', 'internal'), ('name', '=', instance.instance), ('active', '!=', active)], context=context)
                if p_id:
                    partner_obj.write(cr, uid, p_id, {'active': active}, context={})  # empty context: in sync ctx active field is disabled

        return res

    def _has_undisposed_assets(self, cr, uid, ids, context=None):
        if not ids:
            return False
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}
        asset_obj = self.pool.get('product.asset')
        return asset_obj.search_exists(cr, uid, [('used_instance_id', 'in', ids), ('state', '!=', 'disposed')], context=context)

msf_instance()

class account_analytic_line(osv.osv):

    _inherit = 'account.analytic.line'

    _columns = {
        'correction_date': fields.datetime('Correction Date'), # UF-2343: Add timestamp when making the correction, to be synced
    }

    def get_browse_instance_name_from_cost_center(self, cr, uid, cost_center_id, context=None):
        if cost_center_id:
            target_ids = self.pool.get('account.target.costcenter').search(cr, uid, [('cost_center_id', '=', cost_center_id),
                                                                                     ('is_target', '=', True)])
            current_instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
            if len(target_ids) > 0:
                target = self.pool.get('account.target.costcenter').browse(cr, uid, target_ids[0], context=context)
                if target.instance_id and target.instance_id.instance:
                    return target.instance_id

            if current_instance.parent_id and current_instance.parent_id.instance:
                # Instance has a parent
                return current_instance.parent_id
            else:
                return False
        else:
            return False

    def get_instance_name_from_cost_center(self, cr, uid, cost_center_id, context=None):
        browse_instance = self.get_browse_instance_name_from_cost_center(cr, uid, cost_center_id, context=context)
        if browse_instance:
            return browse_instance.instance
        return browse_instance

    def get_lower_instance_name(self, cr, uid, browse_inst1, browse_inst2, context=None):
        if browse_inst1.id == browse_inst2.id:
            return browse_inst1.instance
        if browse_inst1.level == browse_inst2.level:
            # same level so no parentality
            return [browse_inst1.instance, browse_inst2.instance]
        if browse_inst1.level == 'project' and browse_inst2.level in ('coordo', 'mission') or \
                browse_inst1.level == 'coordo' and browse_inst2.level == 'mission':
            lower = browse_inst1
            upper = browse_inst2
        else:
            lower = browse_inst2
            upper = browse_inst1

        if lower.parent_id and lower.parent_id.id == upper.id or lower.parent_id.parent_id and lower.parent_id.parent_id.id == upper.id:
            return lower.instance
        return [browse_inst1.instance, browse_inst2.instance]
    def get_instance_level_from_cost_center(self, cr, uid, cost_center_id, context=None):
        if cost_center_id:
            target_ids = self.pool.get('account.target.costcenter').search(cr, uid, [('cost_center_id', '=', cost_center_id),
                                                                                     ('is_target', '=', True)])
            current_instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
            if len(target_ids) > 0:
                target = self.pool.get('account.target.costcenter').browse(cr, uid, target_ids[0], context=context)
                if target.instance_id and target.instance_id.level:
                    return target.instance_id.level

            if current_instance.parent_id and current_instance.parent_id.level:
                # Instance has a parent
                return current_instance.parent_id.level
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
            browse_instance = False
            if line_data.cost_center_id:
                browse_instance = self.get_browse_instance_name_from_cost_center(cr, uid, line_data.cost_center_id.id, context)
                if browse_instance:
                    res[line_data.id] = browse_instance.instance
            elif current_instance.parent_id and current_instance.parent_id.instance:
                # Instance has a parent
                browse_instance = current_instance.parent_id
                res[line_data.id] = current_instance.parent_id.instance

            # UFTP-382/BKLG-24: sync the line associated to a register line to the register owner and to the target CC
            # UF-450: send also the AJI to the journal owner
            if line_data and line_data.move_id and line_data.move_id.journal_id and line_data.move_id.journal_id.instance_id and line_data.move_id.journal_id.instance_id.id != current_instance.id:
                if res[line_data.id]:
                    if not browse_instance:
                        raise osv.except_osv('Error', "Cost center %s must have 'Is Target' set" % (line_data.cost_center_id.code, ))
                    res[line_data.id] = self.get_lower_instance_name(cr, uid, browse_instance, line_data.move_id.journal_id.instance_id, context=context)
                else:
                    res[line_data.id] = line_data.move_id.journal_id.instance_id.instance
        return res

    # Generate delete message for AJI at Project
    def generate_delete_message_at_project(self, cr, uid, ids, vals, context):
        if context is None:
            context = {}

        if context.get('sync_update_execution'):
            # US-450: no delete msg on a sync context
            return False

        # NEED REFACTORING FOR THIS METHOD, if the action write on Analytic.line happens often!
        msg_to_send_obj = self.pool.get("sync.client.message_to_send")
        instance = self.pool.get("sync.client.entity").get_entity(cr, uid, context=context)
        msf_instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        line_data = self.read(cr, uid, ids, ['cost_center_id'], context=context)
        line_data = dict((data['id'], data) for data in line_data)
        now = fields.datetime.now()

        for id in ids:
            old_cost_center_id = line_data[id]['cost_center_id'] and line_data[id]['cost_center_id'][0] or False
            new_cost_center_id = False
            xml_id = self.get_sd_ref(cr, uid, id, context=context)
            if 'cost_center_id' in vals:
                new_cost_center_id = vals['cost_center_id']
            else:
                new_cost_center_id = old_cost_center_id

            ''' UTP-1128: If the correction is made with the following usecase, do not generate anything:
                If the correction is to replace the cost center of the current instance, say P1 to the cc of P2, the deletion
                must not be generated for P1, because if it got generated, this deletion will be spread up to Coordo, then resync
                back to P1 making that P1 deletes also the line with cost center of P2 <--- this is wrong as stated in the ticket
            '''

            if new_cost_center_id != old_cost_center_id:
                old_destination_name = self.get_instance_name_from_cost_center(cr, uid, old_cost_center_id, context=context)
                new_destination_name = self.get_instance_name_from_cost_center(cr, uid, new_cost_center_id, context=context)
                if old_destination_name != new_destination_name and old_destination_name != instance.name:
                    is_parent = False
                    parent = msf_instance.parent_id
                    while parent:
                        if parent.instance == old_destination_name:
                            is_parent = True
                            break
                        parent = parent.parent_id

                    if not is_parent:
                        this = self.browse(cr, uid, id, context=context)
                        journal_instance = this.move_id and this.move_id.journal_id and this.move_id.journal_id.instance_id and this.move_id.journal_id.instance_id.instance
                        if journal_instance and journal_instance != old_destination_name:
                            # we have sent a orphean AJI to old_destination_name: delete it
                            message_data = {'identifier':'delete_%s_to_%s' % (xml_id, old_destination_name),
                                            'sent':False,
                                            'generate_message':True,
                                            'remote_call':self._name + ".message_unlink_analytic_line",
                                            'arguments':"[{'model' :  '%s', 'xml_id' : '%s', 'correction_date' : '%s'}]" % (self._name, xml_id, now),
                                            'destination_name':old_destination_name}
                            msg_to_send_obj.create(cr, uid, message_data)



                # Check if the new code center belongs to a project that has *previously* a delete message for the same AJI created but not sent
                # -> remove that delete message from the queue
                new_destination_level = self.get_instance_level_from_cost_center(cr, uid, new_cost_center_id, context=context)
                if new_destination_level == 'project': # Only concern Project (other level has no delete message)
                    new_destination_name = self.get_instance_name_from_cost_center(cr, uid, new_cost_center_id, context=context)
                    if new_destination_name and xml_id:
                        identifier = 'delete_%s_to_%s' % (xml_id, new_destination_name)
                        exist_ids = msg_to_send_obj.search(cr, uid,
                                                           [('identifier', '=', identifier), ('sent', '=',
                                                                                              False)], order='NO_ORDER')
                        if exist_ids:
                            msg_to_send_obj.unlink(cr, uid, exist_ids, context=context) # delete this unsent delete-message


    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if context is None:
            context = {}
        if not 'cost_center_id' in vals:
            return super(account_analytic_line, self).write(cr, uid, ids, vals, context=context)

        if isinstance(ids, int):
            ids = [ids]

        # Only set the correction date if data not come from sync
        if not context.get('sync_update_execution', False):
            vals['correction_date'] = fields.datetime.now() # This timestamp is used for the write, but need to set BEFORE
        # call to generate delete message if the cost center is removed from a project
        self.generate_delete_message_at_project(cr, uid, ids, vals, context)
        return super(account_analytic_line, self).write(cr, uid, ids, vals, context=context)

account_analytic_line()

class account_move_line(osv.osv):
    _inherit = 'account.move.line'

    def write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
        """
            deprecated method: kept only to manage in-pipe updates during UF14.0 -> UF15.0
        """
        if not ids:
            return True
        if context is None:
            context = {}

        # if unreconcile linked to paid/close invoice, then reopen SI
        invoice_reopen = []
        if context.get('sync_update_execution') and 'reconcile_id' in vals and not vals['reconcile_id']:
            move_lines = self.browse(cr, uid, ids, fields_to_fetch=['invoice', 'reconcile_id'], context=context)
            invoice_reopen = [line.invoice.id for line in move_lines if line.reconcile_id and line.invoice and line.invoice.state in ['paid','inv_close']]

        res = super(account_move_line, self).write(cr, uid, ids, vals, context=context, check=check, update_check=update_check)
        # Do workflow if line is coming from sync, is now reconciled and it has an unpaid invoice
        if context.get('sync_update_execution', False) and 'reconcile_id' in vals and vals['reconcile_id']:
            invoice_ids = []
            line_list = self.browse(cr, uid, ids, fields_to_fetch=['invoice'], context=context)
            invoice_ids = [line.invoice.id for line in line_list if
                           line.invoice and line.invoice.state not in ('paid','inv_close')]
            if self.pool.get('account.invoice').test_paid(cr, uid, invoice_ids):
                self.pool.get('account.invoice').confirm_paid(cr, uid, invoice_ids)

        if invoice_reopen:
            netsvc.LocalService("workflow").trg_validate(uid, 'account.invoice', invoice_reopen, 'open_test', cr)

        return res

account_move_line()

class funding_pool_distribution_line(osv.osv):
    _inherit = 'funding.pool.distribution.line'

    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        if not dest_field == 'cost_center_id':
            return super(funding_pool_distribution_line, self).get_destination_name(cr, uid, ids, dest_field, context=context)

        current_instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        ana_obj = self.pool.get('account.analytic.line')
        res = dict.fromkeys(ids, False)
        for line_id in ids:
            line_data = self.browse(cr, uid, line_id, context=context)
            browse_instance = False
            if line_data.cost_center_id:
                browse_instance = ana_obj.get_browse_instance_name_from_cost_center(cr, uid, line_data.cost_center_id.id, context)
                if browse_instance:
                    res[line_id] = browse_instance.instance
            elif current_instance.parent_id and current_instance.parent_id.instance:
                # Instance has a parent
                browse_instance = current_instance.parent_id
                res[line_id] = current_instance.parent_id.instance
            # UFTP-382: sync down the distrib line associated to the register line
            if line_data.distribution_id and line_data.distribution_id.register_line_ids:
                for stat_line in line_data.distribution_id.register_line_ids:
                    if current_instance.id != stat_line.statement_id.instance_id.id:
                        res[line_id] = stat_line.statement_id.instance_id.instance
            # UFTP-382: sync down the distrib line associated to the project register move line
            elif line_data.distribution_id and line_data.distribution_id.move_line_ids:
                for move_line in line_data.distribution_id.move_line_ids:
                    if move_line.statement_id and move_line.statement_id.instance_id.id != current_instance.id:
                        res[line_id] = move_line.statement_id.instance_id.instance
            elif line_data.distribution_id and line_data.distribution_id.purchase_line_ids:
                for pol in line_data.distribution_id.purchase_line_ids:
                    if pol.order_id.partner_id.partner_type == 'internal' and pol.order_id.partner_id.name != res[line_id]:
                        res[line_id] = pol.order_id.partner_id.name
            elif line_data.distribution_id and line_data.distribution_id.sale_order_line_ids:
                for sol in line_data.distribution_id.sale_order_line_ids:
                    if sol.order_id.partner_id.partner_type == 'internal' and sol.order_id.partner_id.name != res[line_id]:
                        res[line_id] = sol.order_id.partner_id.name

            # US-450: also sent fp.line to related G/L journal instance
            if line_data.distribution_id and line_data.distribution_id.move_line_ids:
                for move_line in line_data.distribution_id.move_line_ids:
                    if move_line.journal_id:
                        inst = move_line.journal_id and move_line.journal_id.instance_id
                        if not browse_instance:
                            raise osv.except_osv('Error', "Cost center %s must have 'Is Target' set" % (line_data.cost_center_id.code, ))
                        if inst and inst.id != current_instance.id and inst.instance != res[line_id]:
                            res[line_id] = ana_obj.get_lower_instance_name(cr, uid, browse_instance, inst, context=context)
                        break
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
        product = self.read(cr, uid, res_id, ['xmlid_code'])
        if product['xmlid_code'] and not product['xmlid_code'].startswith(RANDOM_XMLID_CODE_PREFIX):
            return get_valid_xml_name('product', product['xmlid_code'])

        return super(product_product, self).get_unique_xml_name(cr, uid, uuid, table_name, res_id)

    # UF-2254: Treat the case of product with empty or XXX for default_code
    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if not ids:
            return True
        res = super(product_product, self).write(cr, uid, ids, vals, context=context)
        if isinstance(ids, int):
            ids = [ids]
        res_id = ids[0]

        prod = self.read(cr, uid, res_id, ['default_code'], context=context)['default_code']
        if prod is not None and prod != 'XXX': # normal case, do nothing
            return res

        # if the default_code is empty or XXX, rebuild the xmlid
        model_data_obj = self.pool.get('ir.model.data')
        sdref_ids = model_data_obj.search(cr, uid,
                                          [('model','=',self._name),('res_id','=',res_id),('module','=','sd')],
                                          order='NO_ORDER')
        if not sdref_ids: # xmlid not exist in ir model data -> create new
            identifier = self.pool.get('sync.client.entity')._get_entity(cr).identifier
            name = self.get_unique_xml_name(cr, uid, identifier, self._table, res_id)
            model_data_obj.create(cr, uid, {
                'noupdate' : False, # don't set to True otherwise import won't work
                'module' : 'sd',
                'last_modification' : fields.datetime.now(),
                'model' : self._name,
                'res_id' : res_id,
                'version' : 1,
                'name' : name,
            }, context=context)
        else:
            if prod == 'XXX': # if the system created automatically the xmlid in ir_model_data, just delete it!
                model_data_obj.unlink(cr, uid, sdref_ids,context=context)

        return res

    def unlink(self, cr, uid, ids, context=None):
        try:
            res = super(product_product, self).unlink(cr, uid, ids, context=context)
        except AttributeError as e:
            """
            UFTP-208: when deleting a Temporary product (default_code 'XXX')
            comming from GUI duplication, we dive into get_unique_xml_name
            an AttributeError is raised:
                AttributeError: 'Field xmlid_code not found in browse_record(product.product, ID)'

            => browse does not cache for a 'Temporary' Product in get_unique_xml_name...
            => so we intercept this exception
            """
            tolerated_error = "'Field xmlid_code not found in browse_record(product.product,"
            if str(e).startswith(tolerated_error):
                """
                this exception is not raised when deleting a 'regular' product
                """
                return True
            raise e  # default behavior: raise any other AttributeError exception
        return res

product_product()

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
        if bar.type == 'action' and bar.xmlname:
            button_name = bar.xmlname
        else:
            button_name = bar.name
        return get_valid_xml_name('BAR', view_xml_id[bar.view_id.id], button_name)

    def _get_is_remote_wh(self, cr, uid, ids, field_name, args, context=None):
        return {}.fromkeys(ids, False)

    def _search_is_remote_wh(self, cr, uid, obj, name, args, context=None):
        if not args:
            return []
        rarg = []
        for arg in args:
            if arg[1] != '=':
                raise osv.except_osv('Error', 'Filter on is_remote_wh not implemented')
            model_data_obj = self.pool.get('ir.model.data')
            mod_ids = model_data_obj.search(cr, uid, [('model', '=', obj._name), ('name', '=like', 'BAR_sync_remote_warehouse%')])
            ids = []
            for m in model_data_obj.read(cr, uid, mod_ids, ['res_id']):
                ids.append(m['res_id'])
            value = arg[2] not in (False, 'f', 'False')
            rarg.append(('id', value and 'in' or 'not in', ids))
        return rarg

    _columns = {
        'is_remote_wh': fields.function(_get_is_remote_wh, type='boolean', string="From RW module", fnct_search=_search_is_remote_wh, method=True),
    }

button_access_rule()

class hr_employee(osv.osv):
    _inherit = 'hr.employee'

    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        r = self.read(cr, uid, [res_id],
                      ['employee_type', 'identification_id'])[0]
        if r['employee_type'] and r['employee_type'] == 'ex' and \
                r['identification_id']:
            return get_valid_xml_name('employee', r['identification_id'])
        else:
            return super(hr_employee, self).get_unique_xml_name(cr, uid, uuid,
                                                                table_name, res_id)

    def create(self, cr, uid, vals, context=None):
        if not context:
            context = {}

        if context.get('sync_update_execution') and vals.get('employee_type') == 'ex':
            vals['active'] = False

        return super(hr_employee, self).create(cr, uid, vals, context)


    def unlink(self, cr, uid, ids, context=None):
        super(hr_employee, self).unlink(cr, uid, ids, context)
        if isinstance(ids, int):
            ids = [ids]
        cr.execute("delete from ir_model_data where model=%s and res_id in %s", (self._name, tuple(ids)))
        return True

hr_employee()

class hr_payment_method(osv.osv):
    _inherit = 'hr.payment.method'

    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        r = self.read(cr, uid, [res_id], ['name'])[0]
        return get_valid_xml_name('hr_payment_method', r['name'])

hr_payment_method()

class product_asset(osv.osv):
    _inherit = 'product.asset'

    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        if dest_field != 'used_instance_id':
            return super(product_asset, self).get_destination_name(cr, uid, ids, dest_field, context=context)

        if not ids:
            return {}

        res = {}
        for _id in ids:
            res[_id] = []
        cr.execute('''
            select asset.id, array_agg(distinct((i.instance)))
                from product_asset asset
                left join asset_owner_instance_rel rel on rel.asset_id = asset.id
                left join msf_instance i on i.id = rel.instance_id or i.id = asset.used_instance_id
            where
                asset.id in %s and
                i.level = 'project'
            group by asset.id
        ''', (tuple(ids), ))
        for x in cr.fetchall():
            res[x[0]] = x[1]

        return res

product_asset()

"""
class product_asset_line(osv.osv):
    _inherit = 'product.asset.line'

    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        if dest_field != 'used_instance_id':
            return super(product_asset_line, self).get_destination_name(cr, uid, ids, dest_field, context=context)

        if not ids:
            return {}

        res = {}
        for _id in ids:
            res[_id] = []
        cr.execute('''
            select asset_line.id, array_agg(distinct((i.instance)))
                from product_asset_line asset_line
                left join product_asset asset on asset.id = asset_line.asset_id
                left join asset_owner_instance_rel rel on rel.asset_id = asset.id
                left join msf_instance i on i.id = rel.instance_id or i.id = asset.used_instance_id
            where
                asset_line.id in %s and
                i.level = 'project'
            group by asset_line.id
        ''', (tuple(ids), ))
        for x in cr.fetchall():
            res[x[0]] = x[1]
        return res
"""
