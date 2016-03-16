#-*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 TeMPO Consulting, MSF. All Rights Reserved
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

from osv import osv
from osv import fields
from tools.translate import _


class AccountDrillNode(object):
    """
    account amounts consolidated node
    """
    def __init__(self, drill, parent=None, level=0, account_id=False):
        super(AccountDrillNode, self).__init__()
        # set during maping
        self.drill = drill

        self.parent = parent
        self.childs = []
        self.level = level
        self.account_id = account_id

        # set during map/reduce
        self.data = {}
        self.zero_bal = False

        # set during next_node() calls
        self.code = ''
        self.name = ''
        self.obj = None

    def get_currencies(self):
        if not self.data:
            return []
        return [ c for c in self.data.keys() if c != '*' ]

    def output(self):
        """
        output node infos for debug purposes
        """
        indent = ' ' * self.level if self.level > 2 else ''
        print "%s%d\n" % (indent, self.account_id, )
        for c in self.childs:
            c.output()

    def is_move_level(self):
        return self.level == self.drill._move_level

class AccountDrill(object):
    """
    account amounts consolidated tree
    refer to "account.drill" model (at end of file) for a tree build example
    """
    _move_level = 4  # level of account journaling move lines

    # move lines base query
    _sql = '''SELECT sum(debit), sum(credit),
        sum(debit_currency), sum(credit_currency),
        max(c.name)
        FROM account_move_line l
        JOIN account_move am ON (am.id = l.move_id)
        JOIN res_currency c ON (c.id = l.currency_id)
        JOIN account_journal j on (l.journal_id=j.id)
        JOIN account_account a on (a.id=l.account_id)
        JOIN account_account_type at on (at.id=a.user_type)
        WHERE l.account_id = %s{reconcile}{options}{query}
        GROUP BY l.currency_id'''

    # initial balance move lines base query (from IB journal period 0)
    _sql_ib = '''SELECT  sum(debit), sum(credit),
        sum(debit_currency), sum(credit_currency),
        max(c.name)
        FROM account_move_line l
        JOIN account_move am ON (am.id = l.move_id)
        JOIN res_currency c ON (c.id = l.currency_id)
        LEFT JOIN account_period per ON (per.id = l.period_id)
        WHERE l.account_id = %s and per.number = 0{query}
        GROUP BY l.currency_id'''

    def __init__(self, pool, cr, uid, query, query_ib, move_states=[],
        include_accounts=False, account_report_types=False,
        with_balance_only=False, reconcile_filter='', context=None):
        super(AccountDrill, self).__init__()
        self.pool = pool
        self.cr = cr
        self.uid = uid
        self.context = context
        if self.context is None:
            self.context = {}
        self.model = self.pool.get('account.account')

        # passed params
        self.query = query or ''
        self.query_ib = query_ib or ''
        self.move_states = move_states or [ 'draft', 'posted', ]
        self.include_accounts = include_accounts
        self.with_balance_only = with_balance_only
        self.reconcile_filter = reconcile_filter

        # nodes
        self.root = None
        self.nodes_flat = []
        self.nodes_by_id = {}  # flat nodes by account_id
        self.nodes_by_level = {}  # flat nodes by level
        self._next_node_index = 0  # current node index used by next_node()

        # JI base query: constructed via _sql
        self.sql = self._sql
        self.sql = self.sql.replace('{reconcile}', self.reconcile_filter)
        if account_report_types:
            report_types = [ "'%s'" % (rt, ) for rt in account_report_types ]
            options = " AND (at.report_type in (%s)" % (
                ','.join(report_types), )
            if 'asset' in account_report_types \
                or 'liability' in account_report_types:
                # US-227 include tax account for BS accounts selection
                options += " OR at.code = 'tax'"
            options += ')'
        else:
            options = ''
        self.sql = self.sql.replace('{options}', options)

    def output(self):
        """
        output node infos for debug purposes
        """
        self.root.output()
    
    def map(self):
        """
        build tree and compute move lines level amounts per currency
        """
        root_id = self._search([
            ('parent_id', '=', False),
            ('level', '=', 0),
        ])
        root_id = root_id and root_id[0] or False
        if not root_id:
            return

        self.root = self._create_node(parent=None, level=0, account_id=root_id)
        self._map_dive(self.root, 1)
        self.nodes_count = len(self.nodes_flat)

    def reduce(self):
        """
        from move lines level, consolidate, up level to up level, the view
        accounts amounts
        """
        fields = [ 'debit', 'credit', 'debit_ccy', 'credit_ccy', ]

        level = self._move_level
        while level > 0:
            nodes = self.nodes_by_level[level]
            for n in nodes:
                if level == self._move_level:
                    if self.with_balance_only:
                        bal = n.data.get('*', {}).get('debit', 0.) \
                            - n.data.get('*', {}).get('credit', 0.)
                        if bal == 0.:
                            # JI level:
                            # with only balance filter: do not agregate account
                            # debit/credit with a zero balance
                            n.zero_bal = True
                            continue

                parent = n.parent
                if parent:
                    for ccy in n.data:
                        if not ccy in parent.data:
                            parent.data[ccy] = {}
                            for f in fields:
                                parent.data[ccy][f] = 0.
                        for f in fields:
                            parent.data[ccy][f] += n.data[ccy].get(f, 0.)
            level -= 1  # upper level (upper level by uper level)

        # uncomment to explore reduced nodes
        """for id in self.nodes_by_id.keys():
            node = self.nodes_by_id[id]
            pa = node.parent and node.parent.account_id or ''
            print "\n", '-'*10, 'id', id, ' / parent', pa
            print node.data"""

    def _map_dive(self, parent, level):
        if level > self._move_level:
            return

        domain = [
            ('parent_id', '=', parent.account_id),
            ('level', '=', level),
        ]
        child_ids = self._search(domain)
        if child_ids:
            for id in child_ids:
                if not self.include_accounts or id in self.include_accounts:
                    node = self._create_node(parent=parent, level=level,
                        account_id=id)
                    self._map_dive(node, level + 1)

    def _create_node(self, parent=None, level=0, account_id=False):
        """
        create a new node, if of move line level, compute amounts to
        consolidate up later with reduce()
        """
        def prepare_sql(sql, sub_query, node):
            # MEMO: be aware that _query_get append an account_id in sub_query
            # clause due to 'chart_account_id' in context
            res = sql
            if sub_query:
                sub_query = ' AND ' + sub_query
            return res.replace('{query}', sub_query) % (str(node.account_id), )

        def register_sql_result(cr, node, append=False):
            keys = [ 'debit', 'credit', 'debit_ccy', 'credit_ccy', ]

            # defaults 0 amounts
            ccy_name = '*'
            if ccy_name not in node.data:
                node.data[ccy_name] = {}
                for k in keys:
                    node.data[ccy_name][k] = 0.

            if cr.rowcount:
                total_debit = 0.
                total_credit = 0.

                for debit, credit, debit_ccy, credit_ccy, ccy_name \
                    in cr.fetchall():
                    if not append or ccy_name not in node.data:
                        node.data[ccy_name] = {}
                        for k in keys:
                            node.data[ccy_name][k] = 0.

                    node.data[ccy_name]['debit'] += float(debit)
                    node.data[ccy_name]['credit'] += float(credit)
                    node.data[ccy_name]['debit_ccy'] += float(debit_ccy)
                    node.data[ccy_name]['credit_ccy'] += float(credit_ccy)
                    total_debit += float(debit)
                    total_credit += float(credit)

                # total functional all currencies
                node.data['*']['debit'] += total_debit
                node.data['*']['credit'] += total_credit

        node = AccountDrillNode(self, parent=parent, level=level,
            account_id=account_id)
        self.nodes_flat.append(node)
        self.nodes_by_id[account_id] = node
        if level not in self.nodes_by_level:
            self.nodes_by_level[level] = []
        self.nodes_by_level[level].append(node)
        if parent:
            parent.childs.append(node)

        if level == self._move_level:
            # breakdown func/booking per ccy
            
            # regular query
            sql = prepare_sql(self.sql, self.query, node)
            self.cr.execute(sql, (account_id, tuple(self.move_states), ))
            register_sql_result(self.cr, node)
                
            # initial balance
            if self.query_ib:
                sql = prepare_sql(self._sql_ib, self.query_ib, node)
                self.cr.execute(sql, (account_id, ))
                register_sql_result(self.cr, node, append=True)

        return node

    def _search(self, domain):
        return self.model.search(self.cr, self.uid, domain,
            context=self.context)

    def next_node(self):
        if self._next_node_index >= self.nodes_count:
            return None
        node = self.nodes_flat[self._next_node_index]
        if not node.name:
            node.obj = self.model.browse(self.cr, self.uid, node.account_id,
                self.context)
            node.code = node.obj.code
            node.name = "%s %s" % (node.code, node.obj.name, )

        self._next_node_index += 1
        return node


class account_drill(osv.osv):
    _name = "account.drill"
    _auto = False

    def build_tree(self, cr, uid, query, query_ib, move_states=[],
        include_accounts=False, account_report_types=False,
        with_balance_only=False, reconcile_filter='',
        context=None):
        """
        build account amounts consolidated tree
        using query for where clause for regular move lines
        and query_ib for initial balance
        (pass it False if no ib to compute => no 01/01/FY in date selection)
        :param include_accounts: account explicit filter (ids list)
        :type include_accounts: list/False
        :param account_report_types: report type list between
            'income', 'expense', 'asset', 'liability'
        :type account_report_types: list/False
        :param with_balance_only: report only accounts with a <> 0 balance
            (amounts will not be agregated: no debit/credit sum of regular
            accounts with a balance to zero)
        """
        ac = AccountDrill(self.pool, cr, uid, query, query_ib,
            move_states=move_states,
            include_accounts=include_accounts,
            account_report_types=account_report_types,
            with_balance_only=with_balance_only,
            reconcile_filter=reconcile_filter,
            context=context)
        ac.map()
        ac.reduce()
        return ac

account_drill()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
