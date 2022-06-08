# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import datetime
from osv import fields, osv
from tools.translate import _

CONTRACT_CODE_LENGTH = 24
CONTRACT_NAME_LENGTH = 64


class financing_contract_funding_pool_line(osv.osv):
    _name = "financing.contract.funding.pool.line"
    _description = "Funding pool line"
    _rec_name = 'contract_id'

    _columns = {
        'contract_id': fields.many2one('financing.contract.format', 'Contract', required=True),
        'funding_pool_id': fields.many2one('account.analytic.account', 'Funding pool name', required=True),
        'funded': fields.boolean('Earmarked'),
        'total_project': fields.boolean('Total project'),
        'instance_id': fields.many2one('msf.instance','Proprietary Instance'),
    }

    _defaults = {
        'funded': False,
        'total_project': True,
    }

    def check_fp(self, cr, uid, ids, context=None):
        """
        See all other funding pool lines and check that the FP is not used yet.
        If used, raise an error.
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        for line in self.browse(cr, uid, ids):
            fp_id = line.funding_pool_id.id
            # Search other lines
            other_same_fp_ids = self.search(cr, uid, [('contract_id', '=', line.contract_id.id), ('id', '!=', line.id), ('funding_pool_id', '=', fp_id)])
            if other_same_fp_ids:
                raise osv.except_osv(_('Error'), _('This FP is already in use: %s') % (line.funding_pool_id.name))
        return True

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        analytic_acc_obj = self.pool.get('account.analytic.account')
        format_obj = self.pool.get('financing.contract.format')
        contract_obj = self.pool.get('financing.contract.contract')
        # US-113: Check if the call is from sync update
        if context.get('sync_update_execution') and vals.get('contract_id', False):
            # US-113: and if there is any financing contract existed for this format, if no, then ignore this call
            exist = contract_obj.search_exists(cr, uid, [('format_id', '=', vals['contract_id'])])
            if not exist:
                return None
            # new fp from sync: request new quad generation
            cr.execute('''update financing_contract_contract set quad_gen_date=NULL where format_id = %s''', (vals['contract_id'],))

        result = super(financing_contract_funding_pool_line, self).create(cr, uid, vals, context=context)
        # when a new funding pool is added to contract, then add all of the cost centers to the cost center tab, unless
        # the cost center is already there. No action is taken when a cost center is deleted

        #US-345: the following block cannot be executed in the sync context, because it would then reset all costcenters from the funding pools!
        # making that the deleted costcenters from the sender were not taken into account
        if not context.get('sync_update_execution') and vals.get('contract_id') and vals.get('funding_pool_id'):
            # get the Cost Centers linked to the Funding Pool
            fp_cc_ids = [c.id for c in analytic_acc_obj.get_cc_linked_to_fp(cr, uid, vals['funding_pool_id'], context=context)]

            # get the format instance
            cc_rows = format_obj.browse(cr, uid, vals['contract_id'], context=context).cost_center_ids
            cc_ids = []
            for cc in cc_rows:
                cc_ids.append(cc.id)

            # append the ccs from the fp only if not already there
            cc_ids = list(set(cc_ids).union(fp_cc_ids))
            # replace the associated cc list -NOT WORKING
            format_obj.write(cr, uid, vals['contract_id'],{'cost_center_ids':[(6,0,cc_ids)]}, context=context)
        # UFTP-121: Check that FP is not used yet.
        self.check_fp(cr, uid, result)
        return result

    def write(self, cr, uid, ids, vals, context=None):
        """
        Check that no previous funding pool account is used yet.
        """
        if not ids:
            return True

        if isinstance(ids, int):
            ids = [ids]

        if context is None:
            context = {}

        # US-180: Check if it comes from the sync update, and if any contract
        if context.get('sync_update_execution') and vals.get('contract_id', False):
            # Check if this format line belongs to any financing contract/format
            ctr_obj = self.pool.get('financing.contract.contract')
            exist = ctr_obj.search_exists(cr, uid, [('format_id', '=', vals['contract_id'])])
            if not exist:
                return True
            if vals.get('funding_pool_id') and self.search_exists(cr, uid, [('id', 'in', ids), ('funding_pool_id', '!=', vals['funding_pool_id'])]):
                # sync, change of FP in existing line, request quad generation
                cr.execute('''update financing_contract_contract set quad_gen_date=NULL where format_id = %s''', (vals['contract_id'],))

        res = super(financing_contract_funding_pool_line, self).write(cr, uid, ids, vals, context=context)
        self.check_fp(cr, uid, ids)
        return res


financing_contract_funding_pool_line()

class financing_contract_contract(osv.osv):

    _name = "financing.contract.contract"
    _inherits = {"financing.contract.format": "format_id"}
    _trace = True
    _order = 'id desc'

    def contract_open_proxy(self, cr, uid, ids, context=None):
        # utp-1030/7: check grant amount when going on in workflow
        return self._check_grant_amount_proxy(cr, uid, ids,
                                              'contract_open', context=context)

    def contract_reopen_proxy(self, cr, uid, ids, context=None):
        """
        Sets the contract state from Soft-Closed BACK to Open (no check needed)
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        for contract in self.read(cr, uid, ids, ['state'], context=context):
            if contract.get('state', '') == 'soft_closed':
                self.write(cr, uid, contract['id'], {'state': 'open'}, context=context)
        return True

    def contract_open(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {
            'state': 'open',
            'open_date': datetime.date.today().strftime('%Y-%m-%d'),
            'soft_closed_date': None,
        })
        return True

    def search_draft_or_temp_posted(self, cr, uid, ids, context=None):
        """
        Search all draft/temp posted register lines that have an analytic distribution in which funding pool lines have an analytic account set to those given in contract.
        """
        res = []
        for c in self.browse(cr, uid, ids):
            # Search draft posted statement lines
            fp_ids = [x and x.funding_pool_id and x.funding_pool_id.id for x in c.funding_pool_ids]
            if fp_ids:
                sql = """SELECT absl.statement_id
                FROM account_bank_statement_line AS absl, funding_pool_distribution_line AS fp
                WHERE distribution_id = analytic_distribution_id
                AND fp.analytic_id in %s
                AND absl.id in (
                    SELECT st.id
                    FROM account_bank_statement_line st
                        LEFT JOIN account_bank_statement_line_move_rel rel ON rel.move_id = st.id
                        LEFT JOIN account_move am ON am.id = rel.statement_id
                    WHERE (rel.statement_id is null OR am.state != 'posted')
                    ORDER BY st.id
                ) GROUP BY absl.statement_id"""
                cr.execute(sql, (tuple(fp_ids),))
                sql_res = cr.fetchall()
                if sql_res:
                    res += [x and x[0] for x in sql_res]
        return res

    def contract_soft_closed_proxy(self, cr, uid, ids, context=None):
        # utp-1030/7: check grant amount when going on in workflow
        return self._check_grant_amount_proxy(cr, uid, ids,
                                              'contract_soft_closed', context=context)

    def contract_soft_closed(self, cr, uid, ids, *args):
        """
        If some draft/temp posted register lines that have an analytic distribution in which funding pool lines have an analytic account set to those given in contract, then raise an error.
        Otherwise set contract as soft closed.
        """
        # Search draft/temp posted register lines
        if isinstance(ids, int):
            ids = [ids]
        for cont in self.read(cr, uid, ids, ['funding_pool_ids']):
            if not cont['funding_pool_ids']:
                raise osv.except_osv(_('Error'), _("This contract can not be soft-closed because it is not linked to any funding pool."))
        register_ids = self.search_draft_or_temp_posted(cr, uid, ids)
        if register_ids:
            msg= ''
            for i, st in enumerate(self.pool.get('account.bank.statement').browse(cr, uid, register_ids)):
                if i > 0:
                    msg += ' - '
                msg += st.name or ''
            raise osv.except_osv(_('Error'), _("There are still expenses linked to contract's funding pools not hard-posted in registers: %s") % (msg,))
        # Normal behaviour (change contract ' state)
        self.write(cr, uid, ids, {
            'state': 'soft_closed',
            'soft_closed_date': datetime.date.today().strftime('%Y-%m-%d'),
        })
        return True

    def contract_hard_closed_proxy(self, cr, uid, ids, context=None):
        # utp-1030/7: check grant amount when going on in workflow
        return self._check_grant_amount_proxy(cr, uid, ids,
                                              'contract_hard_closed', context=context)

    def contract_hard_closed(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {
            'state': 'hard_closed',
            'hard_closed_date': datetime.date.today().strftime('%Y-%m-%d'),
        })
        return True

    def add_general_domain(self, cr, uid, domain, browse_format_id, reporting_type, context=None):
        format_line_obj = self.pool.get('financing.contract.format.line')
        general_domain = format_line_obj._get_general_domain(cr, uid, browse_format_id, reporting_type, context=context)
        # UTP-1063: Don't use MSF Private Funds anymore
        try:
            fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
        except Exception:
            fp_id = 0

        #US-385: Move the funding pool and cost center outside the loop, put them at header of the domain
        temp_domain = []
        cc_domain = eval(general_domain['cost_center_domain'])
        date_domain = eval(general_domain['date_domain'])
        if general_domain.get('funding_pool_domain', False):
            temp_domain = ['&', '&'] + [cc_domain] + [eval(general_domain['funding_pool_domain'])] + date_domain

        res = [('account_id', '!=', fp_id)]
        if domain:
            res = ['&'] + res + domain

        if temp_domain:
            res = ['&'] + temp_domain + res
        return res

    def get_contract_domain(self, cr, uid, browse_contract, reporting_type=None, context=None):
        # Values to be set
        if reporting_type is None:
            reporting_type = browse_contract.reporting_type

        analytic_domain = False
        isFirst = True

        format_line_obj = self.pool.get('financing.contract.format.line')

        # parse parent lines (either value or sum of children's values)
        for line in browse_contract.actual_line_ids:
            if not line.parent_id:
                # Calculate the all the children lines account domain
                temp = format_line_obj._get_analytic_domain(cr, uid, line, reporting_type, isFirst, context=context)
                if analytic_domain:
                    if temp: # US-385: Added this check, otherwise there will be a extra "|" causing error!
                        # if there exist already previous view, just add an OR operator
                        analytic_domain = ['|'] + analytic_domain + temp
                else:
                    # first time
                    analytic_domain = temp

        return self.add_general_domain(cr, uid, analytic_domain, browse_contract.format_id, reporting_type, context)

    def _get_overhead_amount(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
            Method to compute the overhead amount
        """
        res = {}
        for budget in self.browse(cr, uid, ids, context=context):
            # default value
            res[budget.id] = 0.0
            if budget.overhead_type == 'cost_percentage':
                res[budget.id] = round(budget.grant_amount * budget.overhead_percentage / (100.0 + budget.overhead_percentage))
            elif budget.overhead_type == 'grant_percentage':
                res[budget.id] = round(budget.grant_amount * budget.overhead_percentage / 100.0)
        return res

    def __get_instance_level(self, cr, uid, context=None):
        """
        get instance level (from connected user)
        @return (instance id, instance level) or (False, False)
        @rtype tuple(id, str)
        """
        # get company instance
        user = self.pool.get('res.users').browse(cr, uid, [uid],
                                                 context=context)[0]
        if user and user.company_id and user.company_id.instance_id:
            instance_level = (user.company_id.instance_id.id,
                              user.company_id.instance_id.level, )
        else:
            instance_level = (False, False, )
        return instance_level

    def _get_instance_level(self, cr, uid, ids, field_name=None, arg=None,
                            context=None):
        """ get instance level (from connected user) """
        if not ids:
            return {}
        instance_level = self.__get_instance_level(cr, uid, context=context)[1]
        return dict((id, instance_level) for id in ids)

    _columns = {
        'name': fields.char('Financing contract name', size=CONTRACT_NAME_LENGTH, required=True),
        'code': fields.char('Financing contract code', size=CONTRACT_CODE_LENGTH, required=True),
        'donor_id': fields.many2one('financing.contract.donor', 'Donor', required=True, domain="[('active', '=', True)]"),
        'donor_grant_reference': fields.char('Donor grant reference', size=64),
        'hq_grant_reference': fields.char('HQ grant reference', size=64),
        'grant_amount': fields.float('Grant amount', required=True),
        'overhead_amount': fields.function(_get_overhead_amount, method=True, store=False, string="Overhead amount", type="float", readonly=True),
        'reporting_currency': fields.many2one('res.currency', 'Reporting currency', required=True),
        'notes': fields.text('Notes'),
        'open_date': fields.date('Open date'),
        'soft_closed_date': fields.date('Soft-closed date'),
        'hard_closed_date': fields.date('Hard-closed date'),
        'state': fields.selection([('draft','Draft'),
                                   ('open','Open'),
                                   ('soft_closed', 'Soft-closed'),
                                   ('hard_closed', 'Hard-closed')], 'State'),
        'currency_table_id': fields.many2one('res.currency.table', 'Currency Table'),
        'instance_id': fields.many2one('msf.instance','Proprietary Instance', required=True),
        # Define for _inherits
        'format_id': fields.many2one('financing.contract.format', 'Format',
                                     ondelete="cascade", required=True),
        'fp_added_flag': fields.boolean('Flag when new FP is added'),
        'instance_level': fields.function(_get_instance_level, method=True, string="Current instance level", type="char", readonly=True),  # UFTP-343
        'quad_gen_date': fields.datetime('Date of last generation of quad'),
    }

    _defaults = {
        'state': 'draft',
        'fp_added_flag': False,
        'reporting_currency': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
    }

    def _check_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for contract in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('|'),('name', '=ilike', contract.name),('code', '=ilike', contract.code)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    _constraints = [
        (_check_unicity, 'You cannot have the same code or name between contracts!', ['code', 'name']),
    ]

    def copy(self, cr, uid, id, default=None, context=None, done_list=[], local=False):
        contract = self.browse(cr, uid, id, context=context)
        code = contract['code'] or ''
        name = contract['name'] or ''
        if not default:
            default = {}
        default = default.copy()
        suffix = "(copy)"
        default['code'] = "%s%s" % (code[:CONTRACT_CODE_LENGTH - len(suffix)], suffix)
        default['name'] = "%s%s" % (name[:CONTRACT_NAME_LENGTH - len(suffix)], suffix)
        # Copy lines manually but remove CCs and FPs
        default['funding_pool_ids'] = []
        default['cost_center_ids'] = []
        default['actual_line_ids'] = []
        copy_id = super(financing_contract_contract, self).copy(cr, uid, id, default, context=context)
        copy = self.browse(cr, uid, copy_id, context=context)
        self.pool.get('financing.contract.format').copy_format_lines(cr, uid, contract.format_id.id, copy.format_id.id, context=context)
        return copy_id


    def onchange_donor_id(self, cr, uid, ids, donor_id, format_id, actual_line_ids, context=None):
        res = {}
        if donor_id:
            donor = self.pool.get('financing.contract.donor').browse(cr, uid, donor_id, context=context)
            if donor.format_id:
                source_format = donor.format_id
                format_vals = {
                    'format_name': source_format.format_name,
                    'reporting_type': source_format.reporting_type,
                    'overhead_type': source_format.overhead_type,
                    'overhead_percentage': source_format.overhead_percentage,
                    'reporting_currency': donor.reporting_currency.id,
                }
                res = {'value': format_vals}

        return res

    def onchange_currency_table(self, cr, uid, ids, currency_table_id, reporting_currency_id, context=None):
        values = {'reporting_currency': False}
        if reporting_currency_id:
            # it can be a currency from another table
            reporting_currency = self.pool.get('res.currency').browse(cr, uid, reporting_currency_id, context=context)
            # Search if the currency is in the table, and active
            if reporting_currency.reference_currency_id:
                currency_results = self.pool.get('res.currency').search(cr, uid, [('reference_currency_id', '=', reporting_currency.reference_currency_id.id),
                                                                                  ('currency_table_id', '=', currency_table_id),
                                                                                  ('active', '=', True)], context=context)
            else:
                currency_results = self.pool.get('res.currency').search(cr, uid, [('reference_currency_id', '=', reporting_currency_id),
                                                                                  ('currency_table_id', '=', currency_table_id),
                                                                                  ('active', '=', True)], context=context)
            if len(currency_results) > 0:
                # it's here, we keep the currency
                values['reporting_currency'] = reporting_currency_id
        # Restrain domain to selected table (or None if none selected
        domains = {'reporting_currency': [('currency_table_id', '=', currency_table_id)]}
        return {'value': values, 'domain': domains}

    def onchange_date(self, cr, uid, ids, eligibility_from_date, eligibility_to_date):
        """ This function will be called on the change of dates of the financing contract"""
        if eligibility_from_date and eligibility_to_date:
            if eligibility_from_date >= eligibility_to_date:
                warning = {
                    'title': _('Error'),
                    'message': _("The 'Eligibility Date From' should be sooner than the 'Eligibility Date To'.")
                }
                return {'warning': warning}
        return {}

    def create_reporting_line(self, cr, uid, browse_contract, browse_format_line, parent_report_line_id=None, context=None):
        format_line_obj = self.pool.get('financing.contract.format.line')
        reporting_line_obj = self.pool.get('financing.contract.donor.reporting.line')
        analytic_domain = format_line_obj._get_analytic_domain(cr,
                                                               uid,
                                                               browse_format_line,
                                                               browse_contract.reporting_type,
                                                               True,
                                                               context=context)
        analytic_domain = self.pool.get('financing.contract.contract').add_general_domain(cr, uid, analytic_domain, browse_format_line.format_id, browse_contract.reporting_type, context)
        vals = {'name': browse_format_line.name,
                'code': browse_format_line.code,
                'line_type': browse_format_line.line_type,
                'allocated_budget': round(browse_format_line.allocated_budget),
                'project_budget': round(browse_format_line.project_budget),
                'allocated_real': round(browse_format_line.allocated_real),
                'project_real': round(browse_format_line.project_real),

                'project_balance': round(browse_format_line.project_budget) -  round(browse_format_line.project_real),
                'allocated_balance': round(browse_format_line.allocated_budget) - round(browse_format_line.allocated_real),

                'analytic_domain': analytic_domain,
                'parent_id': parent_report_line_id}
        reporting_line_id = reporting_line_obj.create(cr,
                                                      uid,
                                                      vals,
                                                      context=context)
        # create child lines
        for child_line in browse_format_line.child_ids:
            self.create_reporting_line(cr, uid, browse_contract, child_line, reporting_line_id, context=context)
        return reporting_line_id

    def menu_interactive_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        # we update the context with the contract reporting type
        contract = self.browse(cr, uid, ids[0], context=context)
        context.update({'reporting_currency': contract.reporting_currency.id,
                        'reporting_type': contract.reporting_type,
                        'currency_table_id': contract.currency_table_id.id,
                        'active_id': ids[0],
                        'active_ids': ids,
                        'display_fp': True})
        ## INFO: display_fp in context permits to display Funding Pool column and its attached cost center.
        reporting_line_obj = self.pool.get('financing.contract.donor.reporting.line')
        # Create reporting lines
        # Contract line first (we'll fill it later)
        contract_line_id = reporting_line_obj.create(cr,
                                                     uid,
                                                     vals = {'name': contract.name,
                                                             'code': contract.code,
                                                             'line_type': 'view'},
                                                     context=context)

        # Values to be set
        allocated_budget = 0
        project_budget = 0
        allocated_real = 0
        project_real = 0
        project_balance = 0
        allocated_balance = 0

        # create "real" lines
        for line in contract.actual_line_ids:
            if not line.parent_id:
                # UTP-853: self.create_reporting_line rounds each line
                # (int value) so we add a round for sums equivalence
                allocated_budget += round(line.allocated_budget)
                project_budget += round(line.project_budget)
                allocated_real += round(line.allocated_real)
                project_real += round(line.project_real)
                self.create_reporting_line(cr, uid, contract, line, contract_line_id, context=context)

        # Refresh contract line with general infos
        analytic_domain = self.get_contract_domain(cr, uid, contract, context=context)

        allocated_balance  = allocated_budget - allocated_real
        project_balance= project_budget - project_real

        contract_values = {'allocated_budget': allocated_budget,
                           'project_budget': project_budget,
                           'allocated_real': allocated_real,
                           'project_real': project_real,

                           'allocated_balance': allocated_balance,
                           'project_balance': project_balance,

                           'analytic_domain': analytic_domain}
        reporting_line_obj.write(cr, uid, [contract_line_id], vals=contract_values, context=context)

        # retrieve the corresponding_view
        model_data_obj = self.pool.get('ir.model.data')
        view_id = False
        view_ids = model_data_obj.search(cr, uid,
                                         [('module', '=', 'financing_contract'),
                                          ('name', '=', 'view_donor_reporting_line_tree_%s' % str(contract.reporting_type))],
                                         offset=0, limit=1)
        if len(view_ids) > 0:
            view_id = model_data_obj.browse(cr, uid, view_ids[0]).res_id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'financing.contract.donor.reporting.line',
            'view_type': 'tree',
            'view_id': [view_id],
            'target': 'current',
            'domain': [('id', '=', contract_line_id)],
            'context': context
        }


    def allocated_expenses_report(self, cr, uid, ids, context=None):
        """
        Check if contract gives some FP. If not raise an error.
        Otherwise launch the report.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        for contract in self.browse(cr, uid, ids, context=context):
            if not contract.format_id.funding_pool_ids:
                raise osv.except_osv(_('Error'), _('No FP selected in the financing contract: %s') % (contract.name or ''))
        # We launch the report
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'financing.allocated.expenses.2',
            'datas': {'ids': ids},
            'context': context,
        }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        res = super(financing_contract_contract, self).default_get(cr, uid,
                                                                   fields, context=context, from_web=from_web)

        instance_id, instance_level = self.__get_instance_level(cr, uid,
                                                                context=context)
        res['instance_level'] = instance_level
        if instance_level and instance_level == 'coordo':
            """
            UFTP-343
            - coordo level: we can only pick 'this' instance so instance
                is set in create and instance is readonly
            - hq: instance can be modified and picked from coordo instances
            - project: no right to create a financial contract at all,
                so keep instance readonly and empty to prevent any creation
                (in case of right issue)
            """
            res['instance_id'] = instance_id
        return res

    def create(self, cr, uid, vals, context=None):
        # Do not copy lines from the Donor on create if coming from the sync server
        if context is None:
            context = {}

        result = super(financing_contract_contract, self).create(cr, uid, vals, context=context)
        if not context.get('sync_update_execution'):
            contract = self.browse(cr, uid, result, context=context)
            if contract.donor_id and contract.donor_id.format_id and contract.format_id:
                self.pool.get('financing.contract.format').copy_format_lines(cr, uid, contract.donor_id.format_id.id, contract.format_id.id, context=context)
        return result


    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}

        if 'donor_id' in vals:
            donor = self.pool.get('financing.contract.donor').browse(cr, uid, vals['donor_id'], context=context)
            for contract in self.browse(cr, uid, ids, context=context):
                if contract.donor_id and contract.format_id and vals['donor_id'] != contract.donor_id.id:
                    self.pool.get('financing.contract.format').copy_format_lines(cr, uid, donor.format_id.id, contract.format_id.id, context=context)

        if 'funding_pool_ids' in vals: # When the FP is added into the contract, then set this flag into the database
            vals['fp_added_flag'] = True

        # check if the flag has been set TRUE in the previous save
        fp_added_flag = self.browse(cr, uid, ids[0], context=context).fp_added_flag
        if 'format_id' in vals and fp_added_flag: # if the flag is TRUE, and there is a format
            format_obj = self.pool.get('financing.contract.format')
            f_value = format_obj.browse(cr, uid, vals['format_id'], context=context)

            # if there is some FP in this contract format, then perform the "recovery" of cost center ids, if not just use the one from the form
            if f_value.funding_pool_ids:
                cc_rows = f_value.cost_center_ids # retrieve all the cc stored previously in the DB
                cc_ids = []
                for cc in cc_rows:
                    cc_ids.append(cc.id)
                vals['cost_center_ids'] = [(6,0,cc_ids)] # this will be used at final value of cc list to this contract

        # US-113: Populate the instance_id down to format, format line and also funding pool line
        instance_id = vals.get('instance_id', False)
        if not instance_id:
            # US-330: If the prop instance is not in vals, still check in the FC
            instance_id =  self.browse(cr,uid,ids,context=context)[0].instance_id
            if instance_id:
                instance_id = instance_id.id
        if instance_id:
            vals['hidden_instance_id'] = instance_id

        res = super(financing_contract_contract, self).write(cr, uid, ids, vals, context=context)
        if fp_added_flag: # if the previous save has been recovered thanks to the flag set to True, then reset it back to False
            cr.execute('''update financing_contract_contract set fp_added_flag = 'f' where id = %s''', (ids[0],))

        format =  self.browse(cr,uid,ids,context=context)[0].format_id

        if not context.get('sync_update_execution'):
            earmarked_funding_pools = [x.funded for x in format.funding_pool_ids]
            if not any(earmarked_funding_pools) and format.reporting_type == 'allocated':
                raise osv.except_osv(_('Error'), _("At least one funding pool should be defined as earmarked in the funding pool list of this financing contract."))


        # filter current assignments and re-write entries if necessary
        format_obj = self.pool.get('financing.contract.format')
        format_line_obj = self.pool.get('financing.contract.format.line')
        format_browse = format_obj.browse(cr, uid, format.id, context=context)
        fcfpl_line_obj = self.pool.get('financing.contract.funding.pool.line')

        for format_line in format_browse.actual_line_ids:
            list_to_update = {}
            if instance_id:
                if not format_line.instance_id or format_line.instance_id.id != instance_id:
                    list_to_update['instance_id'] = instance_id
            if len(list_to_update) > 0:
                format_line_obj.write(cr, uid, format_line.id, list_to_update, context=context)

        # populate the instance_id to the funding pool lines
        if instance_id:
            for fpid in format.funding_pool_ids:
                list_to_update = {}
                if not fpid.instance_id or fpid.instance_id.id != instance_id:
                    list_to_update['instance_id'] = instance_id
                if len(list_to_update) > 0:
                    fcfpl_line_obj.write(cr, uid, fpid.id, list_to_update, context=context)

        return res

    def change_contract_state(self, cr, uid, ids, signal, context=None):
        """
        Changes the contract state:
        - from Draft to Open (signal contract_open)
        - from Open to Soft-closed (signal contract_soft_closed)
        - from Soft-closed to Hard-closed (signal contract_hard_closed)
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        for contract in self.read(cr, uid, ids, ['state'], context=context):
            state = contract.get('state', '')
            if state == 'draft' and signal == 'contract_open':
                self.contract_open(cr, uid, contract['id'])
            elif state == 'open' and signal == 'contract_soft_closed':
                self.contract_soft_closed(cr, uid, contract['id'])
            elif state == 'soft_closed' and signal == 'contract_hard_closed':
                self.contract_hard_closed(cr, uid, contract['id'])

    def _check_grant_amount_proxy(self, cr, uid, ids, signal, context=None):
        if isinstance(ids, int):
            ids = [ids]
        check_action = self._check_grant_amount(cr, uid, ids, signal,
                                                context=context)
        if check_action:
            return check_action
        self.change_contract_state(cr, uid, ids, signal, context=context)
        return True

    def _check_grant_amount(self, cr, uid, ids, signal, context=None):
        """
        UTP-1030/7: display a warning wizard if funded budget <> grant amount
        except for "Total project only"
        :return action to forward or False to let default behaviour
        :rtype dict/False
        """
        if not ids:
            return False
        if isinstance(ids, int):
            ids = [ids]
        if len(ids) != 1:
            return False  # only warn from form (1 id)

        self_br = self.browse(cr, uid, ids[0], context=context)
        if not self_br.reporting_type or self_br.reporting_type == 'project':
            return False  # no warn for "Total project only"

        # proceed check
        funded_budget = 0.0
        for rl in self_br.actual_line_ids:
            if rl.line_type != 'view': #US-385: Exclude the view line in the calculation
                funded_budget += rl.allocated_budget
        if funded_budget != self_br.grant_amount:
            if context is None:
                context = {}
            warn_msg = _("WARNING: 'Grant' amount is not equal to "
                         "'Funded - Budget'.\nGrant: %.2f\nFunded Budget: %.2f")
            context['financing_contract_warning'] = {
                'text': warn_msg % (self_br.grant_amount, funded_budget, ),
                'signal': signal,
                'res_id': ids[0],
            }
            view_id = self.pool.get('ir.model.data').get_object_reference(cr,
                                                                          uid, 'financing_contract',
                                                                          'view_financing_contract_contract_warning_form')[1]
            return {
                'name': 'Financing Contract Warning',
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.financing.contract.contract.warning',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [view_id],
                'target': 'new',
                'context': context,
            }

        return False

    # US-113: unlink all relevant objects of this FC, because it's not automatic and would left orphan data, also impact to the sync
    def unlink(self, cr, uid, ids, context=None):
        format_obj = self.pool.get('financing.contract.format')
        format_line_obj = self.pool.get('financing.contract.format.line')
        fcfpl_line_obj = self.pool.get('financing.contract.funding.pool.line')

        format_to_del = []
        for fcc in self.browse(cr,uid,ids,context=context):
            format_to_del.append(fcc.format_id.id)
            for format_line in fcc.format_id.actual_line_ids:
                format_line_obj.unlink(cr, uid, format_line.id, context)

            for fpid in fcc.format_id.funding_pool_ids:
                fcfpl_line_obj.unlink(cr, uid, fpid.id, context)

        # the FC itself
        res = super(financing_contract_contract, self).unlink(cr, uid, ids, context)

        # then finally the format line attached to this FC
        if format_to_del:
            format_obj.unlink(cr, uid, format_to_del, context)

        return res

financing_contract_contract()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
