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

from osv import fields, osv
from analytic_distribution.destination_tools import many2many_sorted
from account_override import ACCOUNT_RESTRICTED_AREA
from tools.safe_eval import safe_eval

class financing_contract_format_line(osv.osv):

    _name = "financing.contract.format.line"

    def _auto_init(self, cr, context=None):
        table_name = 'financing_contract_actual_account_quadruplets'
        cr.execute("SELECT relname FROM pg_class WHERE relkind IN ('r','v') AND relname=%s", (table_name, ))
        table_exists = cr.rowcount

        if not table_exists:
            cr.execute('''
        CREATE TABLE financing_contract_actual_account_quadruplets (
            actual_line_id integer NOT NULL,
            account_quadruplet_id integer NOT NULL
        )'''
                       )
        super(financing_contract_format_line, self)._auto_init(cr, context)
        if not table_exists:
            cr.execute('''
            ALTER TABLE ONLY financing_contract_actual_account_quadruplets
                ADD CONSTRAINT financing_contract_actual_account_quadruplet_actual_line_id_key UNIQUE (actual_line_id, account_quadruplet_id)
            ''')
            cr.execute('''CREATE INDEX financing_contract_actual_account_quadruplets_account_quadruple ON financing_contract_actual_account_quadruplets USING btree (account_quadruplet_id)''')
            cr.execute('''CREATE INDEX financing_contract_actual_account_quadruplets_actual_line_id_in ON financing_contract_actual_account_quadruplets USING btree (actual_line_id)''')
            cr.execute('''
            ALTER TABLE ONLY financing_contract_actual_account_quadruplets
                ADD CONSTRAINT financing_contract_actual_account_quadruple_actual_line_id_fkey FOREIGN KEY (actual_line_id) REFERENCES financing_contract_format_line(id) ON DELETE CASCADE
            ''')
    def _create_domain(self, header, element_list):
        domain = "('" + header + "', 'in', ["
        if len(element_list) > 0:
            for element in element_list:
                domain += str(element.id)
                domain += ', '
            domain = domain[:-2]
        domain += "])"
        return domain

    # get list of accounts for duplet format lines
    def _create_account_couple_domain(self, account_destination_list):
        """
        Returns the domain corresponding to the list of acc/dest in param.
        """
        dom = []
        if not account_destination_list:
            return dom
        first = True
        for account_dest in account_destination_list:
            dom += ['&', ('general_account_id', '=', account_dest.account_id.id), ('destination_id', '=', account_dest.destination_id.id)]
            if not first:
                dom.insert(0, '|')
            else:
                first = False
        return dom

    # get list of accounts for quadruplet format lines
    def _create_account_quadruplet_domain(self, account_quadruplet_list, funding_pool_ids=None):
        """
        Returns the domain corresponding to the list of quadruplets in param.
        """
        dom = []
        if not account_quadruplet_list:
            return dom
        if funding_pool_ids is None:
            funding_pool_ids = []
        first = True
        for quad in account_quadruplet_list:
            if quad.funding_pool_id.id in funding_pool_ids:
                dom += ['&',
                        '&',
                        '&',
                        ('general_account_id', '=', quad.account_id.id),
                        ('destination_id', '=', quad.account_destination_id.id),
                        ('cost_center_id', '=', quad.cost_center_id.id),
                        ('account_id', '=', quad.funding_pool_id.id)]
                if not first:
                    dom.insert(0, '|')
                else:
                    first = False
        return dom

    def _get_number_of_childs(self, cr, uid, ids, field_name=None, arg=None, context=None):
        # Verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
            #account_quadruplet_domain = ['&',('funding_pool_id', 'in', (36,40))]
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = line.child_ids and len(line.child_ids) or 0
        return res

    def _get_parent_ids(self, cr, uid, ids, context=None):
        res = []
        for line in self.browse(cr, uid, ids, context=context):
            if line.parent_id:
                res.append(line.parent_id.id)
        return res

    def _get_total_costs(self, cr, uid, browse_overhead_line, field_name=None, context=None):
        # since this is only called from the overhead line, the domain is
        # "all children, except the overhead lines"
        result = 0.0
        total_line_ids = [line.id for line in browse_overhead_line.format_id.actual_line_ids if line.line_type in ['actual', 'consumption']]
        total_costs = {}
        if field_name and field_name in ('allocated_budget', 'project_budget'):
            total_costs = self._get_budget_amount(cr, uid, total_line_ids, field_name, context=context)
        else:
            total_costs = self._get_actual_amount(cr, uid, total_line_ids, field_name, context=context)
        for total_cost in list(total_costs.values()):
            result += total_cost
        return result

    def button_delete_all_quads(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'account_quadruplet_ids':[(6, 0, [])]}, context=context )
        return True

    def button_delete_all_couples(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'account_destination_ids':[(6, 0, [])]}, context=context )
        return True

    def button_remove_all_accounts(self, cr, uid, ids, context=None):
        """
        Removes all G/L accounts selected in the Reporting lines wizard
        """
        self.write(cr, uid, ids, {'reporting_account_ids': [(6, 0, [])]}, context=context)
        return True

    # Get the list of accounts for both duplet and quadruplet
    def _get_accounts_couple_and_quadruplets(self, browse_line):
        """
        Returns a dict with a list of browse records for acc/dest, quadruplets and "accounts only"
        """
        account_destination_result = []
        account_quadruplet_result = []
        account_gl_result = []
        if browse_line.line_type != 'view':
            if browse_line.is_quadruplet:
                account_quadruplet_result = [account_quadruplet for account_quadruplet in browse_line.account_quadruplet_ids]
            elif browse_line.reporting_select_accounts_only:
                # this syntax's goal is to get a list of browse records instead of a browse_record_list
                account_gl_result = [a for a in browse_line.reporting_account_ids]
            else:
                account_destination_result = [account_destination for account_destination in browse_line.account_destination_ids]
        else:
            for child_line in browse_line.child_ids:
                temp = self._get_accounts_couple_and_quadruplets(child_line)
                account_destination_result += temp['account_destination_list']
                account_quadruplet_result += temp['account_quadruplet_list']
                account_gl_result += temp['account_gl_list']
        return {
            'account_destination_list': account_destination_result,
            'account_quadruplet_list': account_quadruplet_result,
            'account_gl_list': account_gl_result,
        }

    def _get_general_domain(self, cr, uid, browse_format, domain_type, context=None):
        # Method to get the domain (allocated or project) of a line

        date_domain = "[('document_date', '>=', '"
        date_domain += browse_format.eligibility_from_date
        date_domain += "'), ('document_date', '<=', '"
        date_domain += browse_format.eligibility_to_date
        date_domain += "')]"

        gen_domain = {}
        gen_domain['date_domain'] = date_domain

        cost_center_domain = self._create_domain('cost_center_id', browse_format.cost_center_ids)
        gen_domain['cost_center_domain'] = cost_center_domain


        # note: even though reporting should be from quadruplets and couples, an additional verification against funding pools
        # and cost centers is required. This is because a user could follow this sequence -
        # 1. add a funding pool to the contract
        # 2. create quads based on it
        # 3. remove the funding pool
        # 4. The quad reporting line still refers to the removed FP.
        #

        # Funding pools
        funding_pool_ids = []
        if domain_type == 'allocated':
            funding_pool_ids = [funding_pool_line.funding_pool_id for funding_pool_line in browse_format.funding_pool_ids if funding_pool_line.funded]
        else:
            funding_pool_ids = [funding_pool_line.funding_pool_id for funding_pool_line in browse_format.funding_pool_ids]

        if funding_pool_ids:
            # remove 'FP' funding pool from the list if it exists.
            fp_ids = self.pool.get('account.analytic.account').search(cr, uid, ['&',('category','=','FUNDING'),('code','=','FP')], context=None)
            funding_pool_ids = [x for x in funding_pool_ids if x not in fp_ids]
            funding_pool_domain = self._create_domain('account_id', funding_pool_ids)
            gen_domain['funding_pool_domain'] = funding_pool_domain
        else:
            gen_domain['funding_pool_domain'] = "('account_id', 'in', [])"

        gen_domain['funding_pool_ids'] = [x.id for x in funding_pool_ids]
        return gen_domain


    def _get_analytic_domain(self, cr, uid, browse_line, domain_type, isFirst=True, context=None):
        if browse_line.line_type in ('consumption', 'overhead'):
            # No domain for this case
            return []
        else:
            # last domain: get only non-corrected lines.
            non_corrected_domain = [('is_reallocated', '=', False),('is_reversal', '=', False)]
            format = browse_line.format_id
            if format.eligibility_from_date and format.eligibility_to_date:
                #### DUY US-385: MOVE THIS TO OUTSIDE OF THE ALL THE LOOPS
                general_domain = self._get_general_domain(cr, uid, format, domain_type, context=context)
                accounts_criteria = ['&', '&', ] + non_corrected_domain
                acc_domains = []

                # Account + destination domain
                account_destination_quadruplet_ids = self._get_accounts_couple_and_quadruplets(browse_line)
                account_couple_domain = self._create_account_couple_domain(account_destination_quadruplet_ids['account_destination_list'])
                if account_couple_domain:
                    acc_domains += [account_couple_domain]
                # get the criteria for accounts of quadruplet mode
                account_quadruplet_domain = self._create_account_quadruplet_domain(account_destination_quadruplet_ids['account_quadruplet_list'], general_domain['funding_pool_ids'])
                if account_quadruplet_domain:
                    acc_domains += [account_quadruplet_domain]
                # "Accounts Only" Domain
                account_only_domain = []
                if account_destination_quadruplet_ids['account_gl_list']:
                    acc_ids = [a.id for a in account_destination_quadruplet_ids['account_gl_list']]
                    account_only_domain = [('general_account_id', 'in', acc_ids)]
                if account_only_domain:
                    acc_domains += [account_only_domain]

                # note: it's possible to have more than one domain in case several lines are grouped into a view
                if len(acc_domains) == 1:
                    accounts_criteria += acc_domains[0]
                elif len(acc_domains) == 2:
                    accounts_criteria += ['|'] + acc_domains[0] + acc_domains[1]
                elif len(acc_domains) == 3:
                    accounts_criteria += ['|'] + ['|'] + acc_domains[0] + acc_domains[1] + acc_domains[2]
                else:
                    return [('id', '=', -1)]

                return accounts_criteria
            else:
                return []

    def _is_overhead_present(self, cr, uid, ids, context={}):
        for line in self.browse(cr, uid, ids, context=context):
            if line.line_type == 'overhead':
                return True
            elif line.line_type == 'view':
                if self._is_overhead_present(cr, uid, [x.id for x in line.child_ids], context=context):
                    return True
        return False

    def _get_actual_line_ids(self, cr, uid, ids, context={}):
        actual_line_ids = set()
        for line in self.browse(cr, uid, ids, context=context):
            if line.line_type == 'view':
                actual_line_ids.update(self._get_actual_line_ids(cr, uid, [x.id for x in line.child_ids], context=context))
            elif line.line_type in ['actual', 'consumption']:
                actual_line_ids.add(line.id)
        return list(actual_line_ids)

    def _get_view_amount(self, browse_line, total_costs, retrieved_lines):
        if browse_line.line_type == 'view':
            sum = 0.0
            for child_line in browse_line.child_ids:
                if child_line.id not in retrieved_lines:
                    self._get_view_amount(child_line, total_costs, retrieved_lines)
                sum += retrieved_lines[child_line.id]
            retrieved_lines[browse_line.id] = sum
        elif browse_line.line_type == 'overhead':
            if browse_line.overhead_type == 'cost_percentage':
                # percentage of all costs (sum of all 2nd-level lines, except overhead)
                retrieved_lines[browse_line.id] = round(total_costs * browse_line.overhead_percentage / 100.0)
            elif browse_line.overhead_type == 'grant_percentage':
                # percentage of all costs (sum of all 2nd-level lines, except overhead)
                retrieved_lines[browse_line.id] = round(total_costs * browse_line.overhead_percentage / (100.0 - browse_line.overhead_percentage))


    def _get_budget_amount(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
            Method to compute the allocated budget/amounts, depending on the information in the line
        """
        res = {}
        # 1st step: get the real list of actual lines to compute
        actual_line_ids = []
        overhead = self._is_overhead_present(cr, uid, ids, context=context)
        if overhead and len(ids) > 0:
            line_for_format = self.browse(cr, uid, ids[0], context=context)
            actual_line_ids = [line.id for line in line_for_format.format_id.actual_line_ids if line.line_type in ['actual', 'consumption']]
        else:
            actual_line_ids = self._get_actual_line_ids(cr, uid, ids, context=context)

        # 2nd step: retrieve values for all actual lines above
        for line in self.browse(cr, uid, actual_line_ids, context=context):
            # default value
            res[line.id] = 0.0
            if line.line_type:
                if line.line_type in ('actual', 'consumption'):
                    # Value is set by the user, just return it
                    if field_name == 'allocated_budget':
                        res[line.id] = line.allocated_budget_value
                    elif field_name == 'project_budget':
                        res[line.id] = line.project_budget_value

        # 3rd step: compute all remaining lines from the retrieved results
        total_budget_costs = 0.0
        if overhead:
            total_budget_costs = sum(res.values())
        for line in self.browse(cr, uid, [id for id in ids if id not in actual_line_ids], context=context):
            if line.id not in res:
                self._get_view_amount(line, total_budget_costs, res)

        return res

    def _get_actual_amount(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
            Method to compute the allocated budget/amounts, depending on the information in the line
        """
        res = {}
        bg_obj = self.pool.get('memory.background.report')
        # 1st step: get the real list of actual lines to compute
        actual_line_ids = []
        overhead = self._is_overhead_present(cr, uid, ids, context=context)
        if overhead and len(ids) > 0:
            line_for_format = self.browse(cr, uid, ids[0], context=context)
            actual_line_ids = [line.id for line in line_for_format.format_id.actual_line_ids if line.line_type in ['actual', 'consumption']]
        else:
            actual_line_ids = self._get_actual_line_ids(cr, uid, ids, context=context)

        # 2nd step: retrieve values for all actual lines above
        nb_lines = len(actual_line_ids)
        if field_name == 'allocated_real':
            # for the 'allocated_real' lines: update the % of the process (cf report run in BG) from 20 to 50%
            before = 0.20
            after = 0.50
        else:
            # for the 'project_real' lines: update the % from 50 to 80%
            before = 0.50
            after = 0.80
        current_line_position = 0
        for line in self.browse(cr, uid, actual_line_ids, context=context):
            current_line_position += 1
            # default value
            res[line.id] = 0.0
            if line.line_type:
                if line.line_type == 'consumption':
                    # Value is set by the user, just return it
                    if field_name == 'allocated_real':
                        res[line.id] = line.allocated_real_value
                    elif field_name == 'project_real':
                        res[line.id] = line.project_real_value
                elif line.line_type == 'actual':
                    # sum of analytic lines, determined by the domain
                    analytic_domain = []
                    report_type = ''
                    if field_name == 'project_real':
                        analytic_domain = self._get_analytic_domain(cr, uid, line, 'project', True, context=context)
                        report_type = 'project'
                    elif field_name == 'allocated_real':
                        analytic_domain = self._get_analytic_domain(cr, uid, line, 'allocated', True, context=context)
                        report_type = 'allocated'
                    if analytic_domain:
                        analytic_domain = self.pool.get('financing.contract.contract').add_general_domain(cr, uid, analytic_domain, line.format_id, report_type, context)
                    # selection of analytic lines
                    if 'reporting_currency' in context:  # TODO Why do we only get analytic lines if reporting_currency in context
                        analytic_line_obj = self.pool.get('account.analytic.line')
                        analytic_lines = analytic_line_obj.search(cr, uid, analytic_domain ,context=context)
                        # list of analytic journal_ids which are in the engagement journals
                        exclude_journal_ids = self.pool.get('account.analytic.journal').search(cr, uid, [('type','=','engagement')])
                        exclude_line_ids = []
                        for analytic_line in analytic_line_obj.browse(cr, uid, analytic_lines, context=None):
                            if analytic_line.journal_id.id in exclude_journal_ids:
                                exclude_line_ids.append(analytic_line.id)
                        analytic_lines = [x for x in analytic_lines if x not in exclude_line_ids]
                        real_sum = 0.0
                        currency_table = None
                        if 'currency_table_id' in context:
                            currency_table = context['currency_table_id']
                        for analytic_line in analytic_line_obj.browse(cr, uid, analytic_lines, context=context):
                            # this Financing Contract report is based on doc. date
                            date_context = {'currency_date': analytic_line.document_date,
                                            'currency_table_id': currency_table}
                            real_sum += self.pool.get('res.currency').compute(cr,
                                                                              uid,
                                                                              analytic_line.currency_id.id,
                                                                              context['reporting_currency'],
                                                                              analytic_line.amount_currency or 0.0,
                                                                              round=False,
                                                                              context=date_context)
                        # Invert the result from the lines (positive for out, negative for in)
                        real_sum = -real_sum
                        res[line.id] = real_sum
            bg_obj.compute_percent(cr, uid, current_line_position, nb_lines, before=before, after=after, refresh_rate=1, context=context)

        # 3rd step: compute all remaining lines from the retrieved results
        total_actual_costs = 0.0
        if overhead:
            total_actual_costs = sum(res.values())
        for line in self.browse(cr, uid, [id for id in ids if id not in actual_line_ids], context=context):
            if line.id not in res:
                self._get_view_amount(line, total_actual_costs, res)

        return res

    def _get_quadruplet_sync_list(self, cr, uid, ids, field_name=None, arg=None, context=None):
        tmp_quad = {}
        link_ids = set()
        aa_ids = set()

        for line in self.browse(cr, uid, ids, fields_to_fetch=['account_quadruplet_ids'], context=context):
            for quad in line.account_quadruplet_ids:
                link_ids.add(quad.account_destination_link_id.id)
                aa_ids.add(quad.funding_pool_id.id)
                aa_ids.add(quad.cost_center_id.id)
                tmp_quad.setdefault(line.id, []).append([quad.account_destination_link_id.id, quad.funding_pool_id.id, quad.cost_center_id.id])

        if link_ids:
            link_sdref = self.pool.get('account.destination.link').get_sd_ref(cr, uid, list(link_ids), context=context)
        if aa_ids:
            aa_sdref = self.pool.get('account.analytic.account').get_sd_ref(cr, uid, list(aa_ids), context=context)

        ret = {}
        for _id in ids:
            ret[_id] = []
            for quad_list in tmp_quad.get(_id, []):
                ret[_id].append([link_sdref.get(quad_list[0]), aa_sdref.get(quad_list[1]), aa_sdref.get(quad_list[2])])
            ret[_id] = '%s' % ret[_id]
        return ret


    def _set_quadruplet_sync_list(self, cr, uid, id, name, value, arg, context):
        quad_obj = self.pool.get('financing.contract.account.quadruplet')

        value_list = safe_eval(value)
        link_ids = set()
        aa_ids = set()

        cr.execute('delete from financing_contract_actual_account_quadruplets where actual_line_id = %s', (id, ))
        for data in value_list:
            link_ids.add(data[0])
            aa_ids.add(data[1])
            aa_ids.add(data[2])

        if link_ids:
            link_sdref = self.pool.get('account.destination.link').find_sd_ref(cr, uid, list(link_ids), context=context)
        if aa_ids:
            aa_sdref = self.pool.get('account.analytic.account').find_sd_ref(cr, uid, list(aa_ids), context=context)

        for data in value_list:
            quad_id = quad_obj.search(cr, uid, [('account_destination_link_id', '=', link_sdref.get(data[0])), ('funding_pool_id', '=', aa_sdref.get(data[1])), ('cost_center_id', '=', aa_sdref.get(data[2]))], context=context)
            if not quad_id:
                cr.execute('''INSERT INTO financing_contract_account_quadruplet (account_destination_name, account_id, cost_center_id, disabled, account_destination_link_id, funding_pool_id, account_destination_id) (select
                    account_destination_name, account_id, cost_center_id, disabled, account_destination_link_id, funding_pool_id, account_destination_id
                    from
                        financing_contract_account_quadruplet_view
                    where
                        account_destination_link_id = %s and
                        funding_pool_id = %s and
                        cost_center_id = %s
                ) RETURNING id
                ''', (link_sdref.get(data[0]), aa_sdref.get(data[1]), aa_sdref.get(data[2])))
                quad_id = cr.fetchone()
                if not quad_id:
                    # combination is now invalid so it can't be retrieved from financing_contract_account_quadruplet_view
                    cr.execute('''INSERT INTO financing_contract_account_quadruplet (account_destination_name, account_id, cost_center_id, disabled, account_destination_link_id, funding_pool_id, account_destination_id) (select
                           name, account_id, %(cost_center_id)s, 't', id, %(funding_pool_id)s, destination_id
                           from
                              account_destination_link
                           where
                              id = %(destination_link_id)s
                        ) RETURNING id
                    ''', {'cost_center_id': aa_sdref.get(data[2]), 'funding_pool_id': aa_sdref.get(data[1]), 'destination_link_id': link_sdref.get(data[0])})
                    quad_id = cr.fetchone()

            cr.execute('insert into financing_contract_actual_account_quadruplets (actual_line_id, account_quadruplet_id) values (%s, %s)', (id, quad_id[0]))

        return True

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Code', size=16, required=True),
        'format_id': fields.many2one('financing.contract.format', 'Format'),
        'is_quadruplet': fields.boolean('Input CC/FP at line level?'),
        'account_destination_ids': many2many_sorted('account.destination.link', 'financing_contract_actual_account_destinations', 'actual_line_id', 'account_destination_id', string='Accounts/Destinations', domain=ACCOUNT_RESTRICTED_AREA['contract_reporting_lines']),
        'account_quadruplet_ids': fields.many2many('financing.contract.account.quadruplet', 'financing_contract_actual_account_quadruplets', 'actual_line_id', 'account_quadruplet_id', string='Accounts/Destinations/Funding Pools/Cost Centres', order_by='account_destination_name asc, funding_pool_id asc, cost_center_id asc, id'),
        'parent_id': fields.many2one('financing.contract.format.line', 'Parent line'),
        'child_ids': fields.one2many('financing.contract.format.line', 'parent_id', 'Child lines'),
        'line_type': fields.selection([('view','View'),
                                       ('actual','Actual'),
                                       ('consumption','Consumption'),
                                       ('overhead','Overhead')], 'Line type', required=True),
        'overhead_type': fields.selection([('cost_percentage','Percentage of direct costs'),
                                           ('grant_percentage','Percentage of grant')], 'Overhead calculation mode'),
        'allocated_budget_value': fields.float('Budget allocated amount (value)'),
        'project_budget_value': fields.float('Budget project amount (value)'),
        'allocated_real_value': fields.float('Real allocated amount (value)'),
        'project_real_value': fields.float('Real project amount (value)'),
        'overhead_percentage': fields.float('Overhead percentage'),

        'allocated_budget': fields.function(_get_budget_amount, method=True, store=False, string="Funded - Budget", type="float", readonly=True),
        'project_budget': fields.function(_get_budget_amount, method=True, store=False, string="Total project - Budget", type="float", readonly=True),

        'allocated_real': fields.function(_get_actual_amount, method=True, store=False, string="Funded - Actuals", type="float", readonly=True),
        'project_real': fields.function(_get_actual_amount, method=True, store=False, string="Total project - Actuals", type="float", readonly=True),
        'quadruplet_update': fields.text('Internal Use Only (deprecated - kept to manage old sync update)'),
        'quadruplet_sync_list': fields.function(_get_quadruplet_sync_list, method=True, string='Used to sync quad', type='text', fnct_inv=_set_quadruplet_sync_list),
        'instance_id': fields.many2one('msf.instance','Proprietary Instance'),
        'reporting_select_accounts_only': fields.boolean(string="Select Accounts Only"),
        'reporting_account_ids': fields.many2many('account.account', 'contract_format_line_account_rel', 'format_line_id', 'account_id',
                                                  string='G/L Accounts',
                                                  domain="[('type', '!=', 'view'),"
                                                         " ('is_analytic_addicted', '=', True),"
                                                         " ('active', 'in', ['t', 'f'])]",
                                                  order_by='code'),
    }



    _defaults = {
        'is_quadruplet': False,
        'reporting_select_accounts_only': False,
        'line_type': 'actual',
        'overhead_type': 'cost_percentage',
        'parent_id': lambda *a: False
    }

    _order = 'code asc'

    # UF-2311: Calculate the quadruplet value before writing or creating the format line
    def calculate_quadruplet(self, cr, uid, vals, context):
        if context is None:
            context = {}
        # UC "Account/Dest." selection when...
        # ...either no boxes are ticked
        if 'is_quadruplet' in vals and 'reporting_select_accounts_only' in vals and \
                not vals['is_quadruplet'] and not vals['reporting_select_accounts_only']:
            acc_dest_selected = True
        # ...or "Select Accounts Only" isn't ticked in the Donors where no quadruplets are handled
        elif context.get('donor_id') and 'reporting_select_accounts_only' in vals and not vals['reporting_select_accounts_only']:
            acc_dest_selected = True
        else:
            acc_dest_selected = False
        # View Line Type = no items selected
        if 'line_type' in vals and vals['line_type'] == 'view':
            vals['allocated_amount'] = 0.0
            vals['project_amount'] = 0.0
            vals['account_destination_ids'] = [(6, 0, [])]
            vals['account_quadruplet_ids'] = [(6, 0, [])]
            vals['quadruplet_update'] = ''
            vals['reporting_account_ids'] = [(6, 0, [])]
            vals['is_quadruplet'] = False
            vals['reporting_select_accounts_only'] = False
        # "Input CC/FP at line level" = quadruplets selected
        elif vals.get('is_quadruplet'):
            # reset the acc/dest and G/L accounts which might have been selected before ticking the box "Input CC/FP at line level"
            vals['account_destination_ids'] = [(6, 0, [])]
            vals['reporting_account_ids'] = [(6, 0, [])]
            if context.get('sync_update_execution') and vals.get('quadruplet_update', False) and 'quadruplet_sync_list' not in vals:
                # old sync update received
                quadrup_str = vals['quadruplet_update']
                quads_list = list(map(int, quadrup_str.split(',')))
                vals['account_quadruplet_ids'] = [(6, 0, self.pool.get('financing.contract.account.quadruplet').migrate_old_quad(cr, uid, quads_list))]
        # "Select Accounts Only" = only G/L accounts selected: reset the acc/dest and quadruplets
        elif vals.get('reporting_select_accounts_only'):
            vals['account_destination_ids'] = [(6, 0, [])]
            vals['account_quadruplet_ids'] = [(6, 0, [])]
            vals['quadruplet_update'] = ''
        # Accounts/Destinations selected: reset the G/L accounts and quadruplets
        elif acc_dest_selected:
            vals['reporting_account_ids'] = [(6, 0, [])]
            vals['account_quadruplet_ids'] = [(6, 0, [])]
            vals['quadruplet_update'] = ''
        return True


    def create(self, cr, uid, vals, context=None):
        if not context:
            context = {}

        # calculate the quadruplet combination
        self.calculate_quadruplet(cr, uid, vals, context)
        return super(financing_contract_format_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        # US-180: Check if it comes from the sync update
        if context.get('sync_update_execution') and vals.get('format_id', False):
            # US-180: and if the financing contract of the contract format does not exist, then just ignore this update
            exist = self.pool.get('financing.contract.contract').search_exists(cr, uid, [('format_id', '=', vals['format_id'])])
            if not exist:
                exist = self.pool.get('financing.contract.donor').search_exists(cr, uid, [('format_id', '=', vals['format_id'])])
            if not exist: # No contract found for this format line
                return True

        # calculate the quadruplet combination
        self.calculate_quadruplet(cr, uid, vals, context)
        return super(financing_contract_format_line, self).write(cr, uid, ids, vals, context=context)

    def copy_format_line(self, cr, uid, browse_source_line, destination_format_id, parent_id=None, context=None):
        if destination_format_id:
            format_line_vals = {
                'name': browse_source_line.name,
                'code': browse_source_line.code,
                'format_id': destination_format_id,
                'parent_id': parent_id,
                'line_type': browse_source_line.line_type,
                'account_quadruplet_ids': [(6, 0, [])],
                'reporting_select_accounts_only': browse_source_line.reporting_select_accounts_only,
            }
            account_destination_ids = [account_destination.id for account_destination in browse_source_line.account_destination_ids]
            format_line_vals['account_destination_ids'] = [(6, 0, account_destination_ids)]
            # copy the list of "Accounts Only"
            gl_account_ids = [a.id for a in browse_source_line.reporting_account_ids]
            format_line_vals['reporting_account_ids'] = [(6, 0, gl_account_ids)]
            parent_line_id = self.pool.get('financing.contract.format.line').create(cr, uid, format_line_vals, context=context)
            for child_line in browse_source_line.child_ids:
                self.copy_format_line(cr, uid, child_line, destination_format_id, parent_line_id, context=context)
        return

    def on_change_is_quadruplet(self, cr, uid, ids, is_quadruplet, context=None):
        """
        Ticking "Input CC/FP at line level?" automatically unticks "Select Accounts Only"
        """
        res = {}
        if is_quadruplet:
            res['value'] = {'reporting_select_accounts_only': False, }
        return res

    def on_change_reporting_select_accounts_only(self, cr, uid, ids, reporting_select_accounts_only, context=None):
        """
        Ticking "Select Accounts Only" automatically unticks "Input CC/FP at line level?"
        """
        res = {}
        if reporting_select_accounts_only:
            res['value'] = {'is_quadruplet': False, }
        return res

    def read(self, cr, uid, ids, f, context=None, load='_classic_read'):
        """
            open Reporting lines with quad: quad combination must be refreshed to display lines in red if combination is now invalid
        """
        if context is None:
            context = {}
        if ids and f and 'account_quadruplet_ids' in f and (len(f) > 1 or context.get('report_fromfile')):
            # len(f) > 1 or context.get('report_fromfile') : to not trigger quad update only in pop up Reporting lines view or in PDF where red color is needed
            _ids = ids
            if isinstance(_ids, int):
                _ids = [ids]

            cr.execute("""
                select distinct(c.id) from
                    financing_contract_format_line fl,
                    financing_contract_contract c,
                    financing_contract_actual_account_quadruplets quad
                where
                    c.format_id = fl.format_id and
                    fl.id in %s and
                    fl.is_quadruplet='t' and
                    quad.actual_line_id = fl.id
                """, (tuple(_ids),))
            for x in cr.fetchall():
                self.pool.get('financing.contract.account.quadruplet').gen_quadruplet(cr, uid, context={'contract_id': x[0]})

        return super(financing_contract_format_line, self).read(cr, uid, ids, f, context=context, load=load)

financing_contract_format_line()


class financing_contract_format(osv.osv):

    _name = "financing.contract.format"
    _inherit = "financing.contract.format"

    _columns = {
        'actual_line_ids': fields.one2many('financing.contract.format.line', 'format_id', 'Actual lines')
    }

    def copy_format_lines(self, cr, uid, source_id, destination_id, context=None):
        # remove all old report lines
        destination_obj = self.browse(cr, uid, destination_id, context=context)
        for to_remove_line in destination_obj.actual_line_ids:
            self.pool.get('financing.contract.format.line').unlink(cr, uid, to_remove_line.id, context=context)
        source_obj = self.browse(cr, uid, source_id, context=context)
        # Method to copy a format
        # copy format lines
        for source_line in source_obj.actual_line_ids:
            if not source_line.parent_id:
                self.pool.get('financing.contract.format.line').copy_format_line(cr,
                                                                                 uid,
                                                                                 source_line,
                                                                                 destination_id,
                                                                                 parent_id=None,
                                                                                 context=context)
        return

financing_contract_format()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
