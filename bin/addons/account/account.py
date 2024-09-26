# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from operator import itemgetter
from . import DEFAULT_JOURNALS

import netsvc
import pooler
from osv import fields, osv
import decimal_precision as dp
from tools.translate import _
from tools.misc import get_fake
from lxml import etree


def check_cycle(self, cr, uid, ids, context=None):
    """ climbs the ``self._table.parent_id`` chains for 100 levels or
    until it can't find any more parent(s)

    Returns true if it runs out of parents (no cycle), false if
    it can recurse 100 times without ending all chains
    """
    level = 100
    while len(ids):
        cr.execute('''
            SELECT DISTINCT parent_id
            FROM %s
            WHERE id IN %%s
            AND parent_id IS NOT NULL''' % self._table, (tuple(ids),))  # not_a_user_entry
        ids = list(map(itemgetter(0), cr.fetchall()))
        if not level:
            return False
        level -= 1
    return True

class account_payment_term(osv.osv):
    _name = "account.payment.term"
    _description = "Payment Term"
    _columns = {
        'name': fields.char('Payment Term', size=64, translate=True, required=True),
        'active': fields.boolean('Active', help="If the active field is set to False, it will allow you to hide the payment term without removing it."),
        'note': fields.text('Description', translate=True),
        'line_ids': fields.one2many('account.payment.term.line', 'payment_id', 'Terms'),
    }
    _defaults = {
        'active': 1,
    }
    _order = "name"

    def compute(self, cr, uid, id, value, date_ref=False, context=None):
        if not date_ref:
            date_ref = datetime.now().strftime('%Y-%m-%d')
        pt = self.browse(cr, uid, id, context=context)
        amount = value
        result = []
        obj_precision = self.pool.get('decimal.precision')
        for line in pt.line_ids:
            prec = obj_precision.precision_get(cr, uid, 'Account')
            if line.value == 'fixed':
                amt = round(line.value_amount, prec)
            elif line.value == 'procent':
                amt = round(value * line.value_amount, prec)
            elif line.value == 'balance':
                amt = round(amount, prec)
            if amt:
                next_date = (datetime.strptime(date_ref, '%Y-%m-%d') + relativedelta(days=line.days))
                if line.days2 < 0:
                    next_first_date = next_date + relativedelta(day=1,months=1) #Getting 1st of next month
                    next_date = next_first_date + relativedelta(days=line.days2)
                if line.days2 > 0:
                    next_date += relativedelta(day=line.days2, months=1)
                result.append( (next_date.strftime('%Y-%m-%d'), amt) )
                amount -= amt
        return result

account_payment_term()

class account_payment_term_line(osv.osv):
    _name = "account.payment.term.line"
    _description = "Payment Term Line"
    _columns = {
        'name': fields.char('Line Name', size=32, required=True),
        'sequence': fields.integer('Sequence', required=True, help="The sequence field is used to order the payment term lines from the lowest sequences to the higher ones"),
        'value': fields.selection([('procent', 'Percent'),
                                   ('balance', 'Balance'),
                                   ('fixed', 'Fixed Amount')], 'Valuation',
                                  required=True, help="""Select here the kind of valuation related to this payment term line. Note that you should have your last line with the type 'Balance' to ensure that the whole amount will be threated."""),

        'value_amount': fields.float('Value Amount', help="For Value percent enter % ratio between 0-1."),
        'days': fields.integer('Number of Days', required=True, help="Number of days to add before computation of the day of month." \
                               "If Date=15/01, Number of Days=22, Day of Month=-1, then the due date is 28/02."),
        'days2': fields.integer('Day of the Month', required=True, help="Day of the month, set -1 for the last day of the current month. If it's positive, it gives the day of the next month. Set 0 for net days (otherwise it's based on the beginning of the month)."),
        'payment_id': fields.many2one('account.payment.term', 'Payment Term', required=True, select=True),
    }
    _defaults = {
        'value': 'balance',
        'sequence': 5,
        'days2': 0,
    }
    _order = "sequence"

    def _check_percent(self, cr, uid, ids, context=None):
        obj = self.browse(cr, uid, ids[0], context=context)
        if obj.value == 'procent' and ( obj.value_amount < 0.0 or obj.value_amount > 1.0):
            return False
        return True

    _constraints = [
        (_check_percent, 'Percentages for Payment Term Line must be between 0 and 1, Example: 0.02 for 2% ', ['value_amount']),
    ]

account_payment_term_line()

class account_account_type(osv.osv):
    _name = "account.account.type"
    _description = "Account Type"
    _columns = {
        'name': fields.char('Acc. Type Name', size=64, required=True),
        'code': fields.char('Code', size=32, required=True),
        'close_method': fields.selection([('none', 'None'), ('balance', 'Balance'), ('detail', 'Detail'), ('unreconciled', 'Unreconciled')], 'Deferral Method', required=True, help="""Set here the method that will be used to generate the end of year journal entries for all the accounts of this type.

 'None' means that nothing will be done.
 'Balance' will generally be used for cash accounts.
 'Detail' will copy each existing journal item of the previous year, even the reconciled ones.
 'Unreconciled' will copy only the journal items that were unreconciled on the first day of the new fiscal year."""),
        'sign': fields.selection([(-1, 'Negative'), (1, 'Positive')], 'Sign on Reports', required=True, help='Allows you to change the sign of the balance amount displayed in the reports, so that you can see positive figures instead of negative ones in expenses accounts.'),
        'report_type':fields.selection([
            ('none','/'),
            ('income','Profit & Loss (Income Accounts)'),
            ('expense','Profit & Loss (Expense Accounts)'),
            ('asset','Balance Sheet (Assets Accounts)'),
            ('liability','Balance Sheet (Liability Accounts)')
        ],'P&L / BS Category', select=True, readonly=False, help="According value related accounts will be display on respective reports (Balance Sheet Profit & Loss Account)", required=True),
        'note': fields.text('Description'),
    }
    _defaults = {
        'close_method': 'none',
        'sign': 1,
        'report_type': 'none',
    }
    _order = "code"

account_account_type()


#----------------------------------------------------------
# Accounts
#----------------------------------------------------------

class account_tax(osv.osv):
    _name = 'account.tax'
account_tax()

class account_account(osv.osv):
    _order = "parent_left"
    _parent_order = "code"
    _name = "account.account"
    _description = "Account"
    _parent_store = True
    logger = netsvc.Logger()

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        if context is None:
            context = {}
        pos = 0

        while pos < len(args):

            if args[pos][0] == 'code' and args[pos][1] in ('like', 'ilike') and args[pos][2]:
                args[pos] = ('code', '=like', str(args[pos][2].replace('%', ''))+'%')
            if args[pos][0] == 'journal_id':
                if not args[pos][2]:
                    del args[pos]
                    continue
                jour = self.pool.get('account.journal').browse(cr, uid, args[pos][2], context=context)
                if (not (jour.account_control_ids or jour.type_control_ids)) or not args[pos][2]:
                    args[pos] = ('type','not in',('consolidation','view'))
                    continue
                ids3 = [x.id for x in jour.type_control_ids]
                ids1 = super(account_account, self).search(cr, uid, [('user_type', 'in', ids3)])
                ids1 += [x.id for x in jour.account_control_ids]
                args[pos] = ('id', 'in', ids1)
            pos += 1

        if context and 'consolidate_children' in context: #add consolidated children of accounts
            ids = super(account_account, self).search(cr, uid, args, offset, limit,
                                                      order, context=context, count=count)
            for consolidate_child in self.browse(cr, uid, context['account_id'], context=context).child_consol_ids:
                ids.append(consolidate_child.id)
            return ids

        return super(account_account, self).search(cr, uid, args, offset, limit,
                                                   order, context=context, count=count)

    def _get_children_and_consol(self, cr, uid, ids, context=None):
        #this function search for all the children and all consolidated children (recursively) of the given account ids
        if context is None:
            context={}

        display_only_checked_account = context.get('display_only_checked_account', False)
        # in case of report do not get the account that should not been displayed
        if display_only_checked_account:
            # get the 'MSF Chart of Accounts'
            msf_coa = self.search(cr, uid, [('parent_id','=', False)], context=context)

            # get the level 1 accounts that should be displayed in reports
            level_1_account_ids = self.search(cr, uid,
                                              [('parent_id', '=',msf_coa),
                                               ('display_in_reports','=',True)],
                                              context=context)

            ids2 = msf_coa + self.search(cr, uid, [('parent_id', 'child_of',
                                                    level_1_account_ids)], context=context)
        else:
            ids2 = self.search(cr, uid, [('parent_id', 'child_of', ids)], context=context)
        ids3 = []
        for account in self.browse(cr, uid, ids2, context=context):
            for child in account.child_consol_ids:
                ids3.append(child.id)
        if ids3:
            ids3 = self._get_children_and_consol(cr, uid, ids3, context=context)
        return ids2 + ids3

    def _get_company_currency(self, cr, uid, ids, field_name, arg, context=None):
        result = {}
        for rec in self.browse(cr, uid, ids, context=context):
            result[rec.id] = (rec.company_id.currency_id.id,rec.company_id.currency_id.symbol)
        return result

    def _get_child_ids(self, cr, uid, ids, field_name, arg, context=None):
        result = {}
        for record in self.browse(cr, uid, ids, context=context):
            if record.child_parent_ids:
                result[record.id] = [x.id for x in record.child_parent_ids]
            else:
                result[record.id] = []

            if record.child_consol_ids:
                for acc in record.child_consol_ids:
                    if acc.id not in result[record.id]:
                        result[record.id].append(acc.id)

        return result

    def _get_level(self, cr, uid, ids, field_name, arg, context=None):
        res={}
        accounts = self.browse(cr, uid, ids, context=context)
        for account in accounts:
            level = 0
            if account.parent_id:
                obj = self.browse(cr, uid, account.parent_id.id)
                level = obj.level + 1
            res[account.id] = level
        return res

    def _get_child_of_coa(self, cr, uid, ids, field_name, args, context=None):
        """
        Return the direct child of Chart Of Account account
        """
        if context is None:
            context = {}
        res = {}
        msf_coa = self.search(cr, uid, [('parent_id','=', False)], context=context)
        if msf_coa:
            id_list = self.search(cr, uid, [('parent_id', 'in', msf_coa),
                                            ('id', 'in', ids)], context=context)
            for account_id in ids:
                res[account_id]=account_id in id_list
            return res
        else:
            raise osv.except_osv(_('Error'), _('Operation not implemented!'))

    def _search_asset_for_product(self, cr, uid, obj, name, args, context=None):
        if context is None:
            context = {}
        if not args or not args[0] or not args[0][2] or not args[0][2][0]:
            return []

        if not args[0][2][1]:
            return [('id', '=', 0)]
        prod = self.pool.get('product.product').browse(cr, uid, args[0][2][1], fields_to_fetch=['categ_id'], context=context)
        return [('id', '=', prod.categ_id and prod.categ_id.asset_bs_account_id and prod.categ_id.asset_bs_account_id.id or 0)]

    _columns = {
        'name': fields.char('Name', size=128, required=True, select=True),
        'currency_id': fields.many2one('res.currency', 'Secondary Currency', help="Forces all moves for this account to have this secondary currency."),
        'code': fields.char('Code', size=64, required=True, select=1),
        'type': fields.selection([
            ('view', 'View'),
            ('other', 'Regular'),
            ('receivable', 'Receivable'),
            ('payable', 'Payable'),
            ('liquidity','Liquidity'),
            ('consolidation', 'Consolidation'),
            ('closed', 'Closed'),
        ], 'Internal Type', required=True, select=1, help="This type is used to differentiate types with "\
            "special effects in OpenERP: view can not have entries, consolidation are accounts that "\
            "can have children accounts for multi-company consolidations, payable/receivable are for "\
            "partners accounts (for debit/credit computations), closed for depreciated accounts."),
        'user_type': fields.many2one('account.account.type', 'Account Type', required=True,
                                     help="These types are defined according to your country. The type contains more information "\
                                     "about the account and its specificities."),
        'parent_id': fields.many2one('account.account', 'Parent', ondelete='cascade', domain=[('type','=','view')]),
        'child_parent_ids': fields.one2many('account.account','parent_id','Children'),
        'child_consol_ids': fields.many2many('account.account', 'account_account_consol_rel', 'child_id', 'parent_id', 'Consolidated Children'),
        'child_id': fields.function(_get_child_ids, method=True, type='many2many', relation="account.account", string="Child Accounts"),
        'reconcile': fields.boolean('Reconcile', help="Check this if the user is allowed to reconcile entries in this account."),
        'reconciliation_debit_account_id': fields.many2one('account.account', 'Default Debit Account for Reconciliation',
                                                           domain=[('type', '!=', 'view'),
                                                                   ('type_for_register', '!=', 'donation'),
                                                                   '|',
                                                                   ('user_type_code', '=', 'income'),
                                                                   '&', ('user_type_code', '=', 'expense'), ('user_type.report_type', '!=', 'none'),  # exclude Extra-accounting expenses
                                                                   ]),
        'reconciliation_credit_account_id': fields.many2one('account.account', 'Default Credit Account for Reconciliation',
                                                            domain=[('type', '!=', 'view'),
                                                                    ('type_for_register', '!=', 'donation'),
                                                                    '|',
                                                                    ('user_type_code', '=', 'income'),
                                                                    '&', ('user_type_code', '=', 'expense'), ('user_type.report_type', '!=', 'none'),  # exclude Extra-accounting expenses
                                                                    ]),
        'prevent_multi_curr_rec': fields.boolean('Prevent Reconciliation with different currencies'),
        'shortcut': fields.char('Shortcut', size=12),
        'tax_ids': fields.many2many('account.tax', 'account_account_tax_default_rel',
                                    'account_id', 'tax_id', 'Default Taxes'),
        'note': fields.char('Note', size=160),
        'company_currency_id': fields.function(_get_company_currency, method=True, type='many2one', relation='res.currency', string='Company Currency'),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'active': fields.boolean('Active', select=2, help="If the active field is set to False, it will allow you to hide the account without removing it."),

        'parent_left': fields.integer('Parent Left', select=1),
        'parent_right': fields.integer('Parent Right', select=1),
        'currency_mode': fields.selection([('current', 'At Date'), ('average', 'Average Rate')], 'Outgoing Currencies Rate',
                                          help=
                                          'This will select how the current currency rate for outgoing transactions is computed. '\
                                          'In most countries the legal method is "average" but only a few software systems are able to '\
                                          'manage this. So if you import from another software system you may have to use the rate at date. ' \
                                          'Incoming transactions always use the rate at date.', \
                                          required=True),
        'level': fields.function(_get_level, string='Level', method=True, store=True, type='integer'),
        'is_child_of_coa': fields.function(_get_child_of_coa, method=True, type='boolean', string='Is child of CoA', help="Check if the current account is a direct child of Chart Of Account account."),
        'asset_for_product': fields.function(get_fake, method=True, type='boolean', string='Filter account for asset', fnct_search=_search_asset_for_product),
    }

    _defaults = {
        'type': 'view',
        'reconcile': False,
        'prevent_multi_curr_rec': False,
        'active': True,
        'currency_mode': 'current',
        'company_id': lambda s,cr,uid,c: s.pool.get('res.company')._company_default_get(cr, uid, 'account.account', context=c),
    }

    def _check_recursion(self, cr, uid, ids, context=None):
        obj_self = self.browse(cr, uid, ids[0], context=context)
        p_id = obj_self.parent_id and obj_self.parent_id.id
        if (obj_self in obj_self.child_consol_ids) or (p_id and (p_id is obj_self.id)):
            return False
        while(ids):
            cr.execute('SELECT DISTINCT child_id '\
                       'FROM account_account_consol_rel '\
                       'WHERE parent_id IN %s', (tuple(ids),))
            child_ids = list(map(itemgetter(0), cr.fetchall()))
            c_ids = child_ids
            if (p_id and (p_id in c_ids)) or (obj_self.id in c_ids):
                return False
            while len(c_ids):
                s_ids = self.search(cr, uid, [('parent_id', 'in', c_ids)])
                if p_id and (p_id in s_ids):
                    return False
                c_ids = s_ids
            ids = child_ids
        return True

    def _check_type(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        accounts = self.browse(cr, uid, ids, context=context)
        for account in accounts:
            if account.child_id and account.type not in ('view', 'consolidation'):
                return False
        return True

    _constraints = [
        (_check_recursion, 'Error ! You can not create recursive accounts.', ['parent_id']),
        (_check_type, 'Configuration Error! \nYou cannot define children to an account with internal type different of "View"! ', ['type']),
    ]
    _sql_constraints = [
        ('code_company_uniq', 'unique (code,company_id)', 'The code of the account must be unique per company !')
    ]
    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        args = args[:]
        ids = []
        try:
            if name and str(name).startswith('partner:'):
                part_id = int(name.split(':')[1])
                part = self.pool.get('res.partner').browse(cr, user, part_id, context=context)
                args += [('id', 'in', (part.property_account_payable.id, part.property_account_receivable.id))]
                name = False
            if name and str(name).startswith('type:'):
                type = name.split(':')[1]
                args += [('type', '=', type)]
                name = False
        except:
            pass
        if name:
            ids = self.search(cr, user, [('code', '=like', name+"%")]+args, limit=limit, context=context)
            if not ids:
                ids = self.search(cr, user, [('shortcut', '=', name)]+ args, limit=limit, context=context)
            if not ids:
                ids = self.search(cr, user, [('name', operator, name)]+ args, limit=limit, context=context)
            if not ids and len(name.split()) >= 2:
                #Separating code and name of account for searching
                operand1,operand2 = name.split(' ',1) #name can contain spaces e.g. OpenERP S.A.
                ids = self.search(cr, user, [('code', operator, operand1), ('name', operator, operand2)]+ args, limit=limit, context=context)
        else:
            ids = self.search(cr, user, args, context=context, limit=limit)
        return self.name_get(cr, user, ids, context=context)

    def copy(self, cr, uid, id, default={}, context=None, done_list=[], local=False):
        account = self.browse(cr, uid, id, context=context)
        new_child_ids = []
        if not default:
            default = {}
        default = default.copy()
        default['code'] = (account['code'] or '') + '(copy)'
        if not local:
            done_list = []
        if account.id in done_list:
            return False
        done_list.append(account.id)
        if account:
            for child in account.child_id:
                child_ids = self.copy(cr, uid, child.id, default, context=context, done_list=done_list, local=True)
                if child_ids:
                    new_child_ids.append(child_ids)
            default['child_parent_ids'] = [(6, 0, new_child_ids)]
        else:
            default['child_parent_ids'] = False
        return super(account_account, self).copy(cr, uid, id, default, context=context)

    def _check_moves(self, cr, uid, ids, method, context=None):
        line_obj = self.pool.get('account.move.line')
        account_ids = self.search(cr, uid, [('id', 'child_of', ids)])

        if line_obj.search(cr, uid, [('account_id', 'in', account_ids)]):
            if method == 'write':
                raise osv.except_osv(_('Error !'), _('You cannot deactivate an account that contains account moves.'))
            elif method == 'unlink':
                raise osv.except_osv(_('Error !'), _('You cannot remove an account which has account entries!. '))
        #Checking whether the account is set as a property to any Partner or not
        value = 'account.account,' + str(ids[0])
        partner_prop_acc = self.pool.get('ir.property').search(cr, uid, [('value_reference','=',value)], context=context)
        if partner_prop_acc:
            raise osv.except_osv(_('Warning !'), _('You cannot remove/deactivate an account which is set as a property to any Partner.'))
        return True

    def _check_allow_type_change(self, cr, uid, ids, new_type, context=None):
        group1 = ['payable', 'receivable', 'other']
        group2 = ['consolidation','view']
        line_obj = self.pool.get('account.move.line')
        for account in self.browse(cr, uid, ids, context=context):
            old_type = account.type
            account_ids = self.search(cr, uid, [('id', 'child_of', [account.id])])
            if line_obj.search(cr, uid, [('account_id', 'in', account_ids)]):
                #Check for 'Closed' type
                if old_type == 'closed' and new_type !='closed':
                    raise osv.except_osv(_('Warning !'), _("You cannot change the type of account from 'Closed' to any other type which contains account entries!"))
                #Check for change From group1 to group2 and vice versa
                if (old_type in group1 and new_type in group2) or (old_type in group2 and new_type in group1):
                    raise osv.except_osv(_('Warning !'), _("You cannot change the type of account from '%s' to '%s' type as it contains account entries!") % (old_type,new_type,))
        return True

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if context is None:
            context = {}

        # Dont allow changing the company_id when account_move_line already exist
        if 'company_id' in vals:
            move_lines = self.pool.get('account.move.line').search(cr, uid, [('account_id', 'in', ids)])
            if move_lines:
                # Allow the write if the value is the same
                for i in [i['company_id'][0] for i in self.read(cr,uid,ids,['company_id'])]:
                    if vals['company_id']!=i:
                        raise osv.except_osv(_('Warning !'), _('You cannot modify Company of account as its related record exist in Entry Lines'))
        if 'active' in vals and not vals['active']:
            self._check_moves(cr, uid, ids, "write", context=context)
        if 'type' in list(vals.keys()):
            self._check_allow_type_change(cr, uid, ids, vals['type'], context=context)
        return super(account_account, self).write(cr, uid, ids, vals, context=context)

    def unlink(self, cr, uid, ids, context=None):
        self._check_moves(cr, uid, ids, "unlink", context=context)
        return super(account_account, self).unlink(cr, uid, ids, context=context)

    def onchange_reconcile(self, cr, uid, ids, reconcile, context=None):
        """
        Unticks "Prevent Reconciliation with different currencies" when "Reconcile" is unticked
        """
        res = {}
        if not reconcile:
            res['value'] = {'prevent_multi_curr_rec': False}
        return res

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Displays specific views when G/L accounts are selected from a Funding Pool, a Financing Contract or a Donor
        """
        if context is None:
            context = {}
        ir_model_obj = self.pool.get('ir.model.data')

        if context.get('from_fp') or context.get('from_grant_management'):
            view = False
            module = 'account'
            if view_type == 'search':
                search_view_name = context.get('from_grant_management') and 'view_account_contract_search' or 'view_account_fp_search'
                view = ir_model_obj.get_object_reference(cr, uid, module, search_view_name)
            elif view_type == 'tree':
                view = ir_model_obj.get_object_reference(cr, uid, module, 'view_account_fp_tree')
            if view:
                view_id = view[1]
        fvg = super(account_account, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'search' and context.get('display_hq_system_accounts'):
            arch = etree.fromstring(fvg['arch'])
            for field in arch.xpath('//group[@name="mapping_value"]'):
                field.set('invisible', '0')
            fvg['arch'] = etree.tostring(arch, encoding='unicode')

        if view_type == 'form' and self.pool.get('res.company')._get_instance_oc(cr, uid) == 'ocp':
            found = False
            view_xml = etree.fromstring(fvg['arch'])
            for field in view_xml.xpath('//field[@name="expat_restriction"]'):
                found = True
                field.set('invisible', "0")
            if found:
                fvg['arch'] = etree.tostring(view_xml, encoding='unicode')
        return fvg


account_account()

class account_journal_view(osv.osv):
    _name = "account.journal.view"
    _description = "Journal View"
    _columns = {
        'name': fields.char('Journal View', size=64, required=True),
        'columns_id': fields.one2many('account.journal.column', 'view_id', 'Columns')
    }
    _order = "name"

account_journal_view()


class account_journal_column(osv.osv):

    def _col_get(self, cr, user, context=None):
        result = []
        cols = self.pool.get('account.move.line')._columns
        for col in cols:
            if col in ('period_id', 'journal_id'):
                continue
            result.append( (col, cols[col].string) )
        result.sort()
        return result

    _name = "account.journal.column"
    _description = "Journal Column"
    _columns = {
        'name': fields.char('Column Name', size=64, required=True),
        'field': fields.selection(_col_get, 'Field Name', method=True, required=True, size=32),
        'view_id': fields.many2one('account.journal.view', 'Journal View', select=True),
        'sequence': fields.integer('Sequence', help="Gives the sequence order to journal column.", readonly=True),
        'required': fields.boolean('Required'),
        'readonly': fields.boolean('Readonly'),
    }
    _order = "view_id, sequence"

account_journal_column()

class account_journal(osv.osv):
    _name = "account.journal"
    _description = "Journal"

    def _get_false(self, cr, uid, ids, *a, **b):
        """
        Returns False for all ids (cf. only the search method is used for the field)
        """
        return {}.fromkeys(ids, False)

    def _search_inv_doc_type(self, cr, uid, obj, name, args, context=None):
        """
        Returns a domain (based on the context) to get all journals matching with the doc type of the selected invoice.

        Note: this method is currently not used for IVO and IVI which use a fake_journal_id forced to INT instead of the regular journal_id.
        """
        if context is None:
            context = {}
        if not args:
            return []
        doc_type = context.get('doc_type', '')
        if doc_type == 'str':
            journal_types = ['sale']
        elif doc_type in ('isi', 'isr'):
            journal_types = ['purchase']
        elif doc_type == 'donation':
            journal_types = ['inkind', 'extra']
        else:
            journals = {
                'out_invoice': 'sale',
                'in_invoice': 'purchase',
                'out_refund': 'sale_refund',
                'in_refund': 'purchase_refund',
            }
            journal_types = [journals.get(context.get('type', ''), 'purchase')]
        journal_dom = [('type', 'in', journal_types), ('is_current_instance', '=', True)]
        if doc_type in ('isi', 'isr'):
            journal_dom.append(('code', '=', 'ISI'))
        else:
            journal_dom.append(('code', '!=', 'ISI'))
        return journal_dom

    def _get_is_default(self, cr, uid, ids, name, arg, context=None):
        """
        Returns a dict with key = id of the journal,
        and value = True if the journal belongs to the list of journals imported by default in new instances, False otherwise
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        for j in self.browse(cr, uid, ids, fields_to_fetch=['code', 'type'], context=context):
            res[j.id] = (j.code, j.type) in DEFAULT_JOURNALS
        return res

    def _get_current_id(self, cr, uid, ids, field_name, args, context=None):
        """
        Returns a dict with key = value = current DB id.

        current_id is an internal field used to make the "Active" checkbox read-only at first creation (= without DB id),
        so that new journals are always created as Active, and for new Liquidity journals registers are always created.
        """
        res = {}
        for i in ids:
            res[i] = i
        return res

    _columns = {
        'name': fields.char('Journal Name', size=64, required=True),
        'code': fields.char('Code', size=5, required=True, help="The code will be used to generate the numbers of the journal entries of this journal."),
        'type': fields.selection([('sale', 'Sale'),('sale_refund','Sale Refund'), ('purchase', 'Purchase'), ('purchase_refund','Purchase Refund'), ('cash', 'Cash'), ('bank', 'Bank and Cheques'), ('general', 'General'), ('situation', 'Opening/Closing Situation')], 'Type', size=32, required=True, select=1,
                                 help="Select 'Sale' for Sale journal to be used at the time of making invoice."\
                                 " Select 'Purchase' for Purchase Journal to be used at the time of approving purchase order."\
                                 " Select 'Cash' to be used at the time of making payment."\
                                 " Select 'General' for miscellaneous operations."\
                                 " Select 'Opening/Closing Situation' to be used at the time of new fiscal year creation or end of year entries generation."),
        'refund_journal': fields.boolean('Refund Journal', help='Fill this if the journal is to be used for refunds of invoices.'),
        'type_control_ids': fields.many2many('account.account.type', 'account_journal_type_rel', 'journal_id','type_id', 'Type Controls', domain=[('code','<>','view'), ('code', '<>', 'closed')]),
        'account_control_ids': fields.many2many('account.account', 'account_account_type_rel', 'journal_id','account_id', 'Account', domain=[('type','<>','view'), ('type', '<>', 'closed')]),
        'view_id': fields.many2one('account.journal.view', 'Display Mode', required=True, help="Gives the view used when writing or browsing entries in this journal. The view tells OpenERP which fields should be visible, required or readonly and in which order. You can create your own view for a faster encoding in each journal."),
        'default_credit_account_id': fields.many2one('account.account', 'Default Credit Account', domain="[('type','!=','view')]", help="It acts as a default account for credit amount"),
        'default_debit_account_id': fields.many2one('account.account', 'Default Debit Account', domain="[('type','!=','view')]", help="It acts as a default account for debit amount"),
        'centralisation': fields.boolean('Centralised counterpart', help="Check this box to determine that each entry of this journal won't create a new counterpart but will share the same counterpart. This is used in fiscal year closing."),
        'update_posted': fields.boolean('Allow Cancelling Entries', help="Check this box if you want to allow the cancellation the entries related to this journal or of the invoice related to this journal"),
        'group_invoice_lines': fields.boolean('Group Invoice Lines', help="If this box is checked, the system will try to group the accounting lines when generating them from invoices."),
        'sequence_id': fields.many2one('ir.sequence', 'Entry Sequence', help="This field contains the informatin related to the numbering of the journal entries of this journal.", required=True),
        'user_id': fields.many2one('res.users', 'User', help="The user responsible for this journal"),
        'groups_id': fields.many2many('res.groups', 'account_journal_group_rel', 'journal_id', 'group_id', 'Groups'),
        'currency': fields.many2one('res.currency', 'Currency', help='The currency used to enter statement'),
        'entry_posted': fields.boolean('Skip \'Draft\' State for Manual Entries', help='Check this box if you don\'t want new journal entries to pass through the \'draft\' state and instead goes directly to the \'posted state\' without any manual validation. \nNote that journal entries that are automatically created by the system are always skipping that state.'),
        'company_id': fields.many2one('res.company', 'Company', required=True, select=1, help="Company related to this journal"),
        'allow_date':fields.boolean('Check Date not in the Period', help= 'If set to True then do not accept the entry if the entry date is not into the period dates'),
        'bank_account_number': fields.char('Bank Account Number', size=128, required=False),
        'bank_account_name': fields.char('Bank Account Name', size=256, required=False),
        'bank_swift_code': fields.char('Swift Code', size=32, required=False),
        'bank_address': fields.text('Address', required=False),
        'inv_doc_type': fields.function(_get_false, method=True, type='boolean', string='Document Type', store=False,
                                        fnct_search=_search_inv_doc_type),
        'is_active': fields.boolean('Active'),
        'inactivation_date': fields.date('Inactivation date', readonly=True),
        'is_default': fields.function(_get_is_default, method=True, type='boolean', string='Default Journal',
                                      store=True, help="Journals created by default in new instances"),
        'current_id': fields.function(_get_current_id, method=True, type='integer', string="DB Id (used by the UI)",
                                      store=False, internal=True),
    }

    _defaults = {
        'user_id': lambda self, cr, uid, context: uid,
        'company_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.id,
        'is_active': True,
    }

    _order = 'code, id'

    def _check_default_journal(self, cr, uid, ids, context=None):
        """
        Prevents the inactivation of the journals imported by default in new instances.
        """
        for j in self.browse(cr, uid, ids, fields_to_fetch=['is_active', 'is_default']):
            if not j.is_active and j.is_default:
                return False
        return True

    _constraints = [
        (_check_default_journal, "The journals imported by default at instance creation can't be inactivated.", ['is_active']),
    ]

    def copy(self, cr, uid, id, default={}, context=None, done_list=[], local=False):
        journal = self.browse(cr, uid, id, context=context)
        if not default:
            default = {}
        default = default.copy()
        default['code'] = (journal['code'] or '') + '(copy)'
        default['name'] = (journal['name'] or '') + '(copy)'
        default['is_active'] = True
        return super(account_journal, self).copy(cr, uid, id, default, context=context)

    def _check_journal_constraints(self, cr, uid, journal_ids, context=None):
        """
        Checks the consistency of the journal created if not in a context of synchro
        Raises a warning if one required condition isn't met.
        """
        if context is None:
            context = {}
        if isinstance(journal_ids, int):
            journal_ids = [journal_ids]
        res_obj = self.pool.get('res.users')
        if not context.get('sync_update_execution'):
            fields_list = ['type', 'analytic_journal_id', 'default_debit_account_id', 'default_credit_account_id',
                           'bank_journal_id', 'code', 'currency', 'instance_id']
            for journal in self.browse(cr, uid, journal_ids, fields_to_fetch=fields_list, context=context):
                journal_type = journal.type or ''
                journal_code = journal.code or ''
                currency_id = None
                # check on analytic journal
                if journal_type not in ['situation', 'stock', 'system']:
                    if not journal.analytic_journal_id:
                        raise osv.except_osv(_('Warning'),
                                             _('The Analytic Journal is mandatory for the journal %s.') % journal_code)
                # check on default debit/credit accounts
                if journal_type in ['bank', 'cash', 'cheque', 'cur_adj']:
                    if not journal.default_debit_account_id or not journal.default_credit_account_id:
                        raise osv.except_osv(_('Warning'),
                                             _('Default Debit and Credit Accounts are mandatory for the journal %s.') % journal_code)
                # check on currency
                if journal_type in ['bank', 'cash', 'cheque']:
                    currency_id = journal.currency and journal.currency.id or False
                    if not currency_id:
                        raise osv.except_osv(_('Warning'),
                                             _('The currency is mandatory for the journal %s.') % journal_code)
                if context.get('curr_check', False) and not journal.currency.active:  # The chosen currency must be active
                    raise osv.except_osv(_('Warning'), _('Currency is inactive.'))
                # check on corresponding bank journal for a cheque journal
                if journal_type == 'cheque':
                    if not journal.bank_journal_id:
                        raise osv.except_osv(_('Warning'),
                                             _('The corresponding Bank Journal is mandatory for the journal %s.') % journal_code)
                    else:
                        bank_currency = journal.bank_journal_id.currency
                        bank_currency_id = bank_currency and bank_currency.id or False
                        if not bank_currency_id or currency_id != bank_currency_id:
                            raise osv.except_osv(_('Warning'),
                                                 _('The Corresponding Bank Journal must have the same currency as the journal %s.') % journal_code)

                # check on Proprietary Instance at import time
                if context.get('from_import_data', False):
                    company = res_obj.browse(cr, uid, uid, fields_to_fetch=['company_id'], context=context).company_id
                    current_instance_id = company.instance_id and company.instance_id.id

                    if journal.instance_id.id != current_instance_id:
                        raise osv.except_osv(_('Warning'),
                                             _('The current instance should be used as Proprietary Instance for the journal %s.') % journal_code)

    def _remove_unnecessary_links(self, cr, uid, vals, journal_id=None, context=None):
        """
        Remove the irrelevant links from the dict vals. Ex: create a Cheque journal, and then change its type
        to Purchase => the link to the Corresponding bank journal should be removed.
        """
        if context is None:
            context = {}
        if not context.get('sync_update_execution'):
            journal_type = ''
            if 'type' in vals:
                journal_type = vals.get('type', '')
            elif journal_id:
                journal_type = self.browse(cr, uid, journal_id, fields_to_fetch=['type'], context=context).type or ''
            if journal_type != 'cheque':
                vals['bank_journal_id'] = False
            if journal_type != 'bank':
                vals.update({'bank_account_name': '',
                             'bank_account_number': '',
                             'bank_swift_code': '',
                             'bank_address': '',
                             })

    def _check_journal_inactivation(self, cr, uid, ids, vals, context=None):
        """
        Raises an error in case the journal is being inactivated while it is not allowed:
        - for all liquidity journals: not all registers have been closed, or not all manual journal entries have been posted.
        - for bank and cash journals only: the balance of the last register is not zero.
        - for bank journals: the inactivation of a bank journal must be conditioned to the inactivation of the related cheque journal.
        - for non-liquidity journals: not all entries have been posted, some invoices are still Draft, or some Recurring Plans are not Done.

        Note: there is a Python constraint preventing the inactivation of the journals imported by default at instance creation.
        """
        if context is None:
            context = {}
        reg_obj = self.pool.get('account.bank.statement')
        am_obj = self.pool.get('account.move')
        inv_obj = self.pool.get('account.invoice')
        rec_model_obj = self.pool.get('account.model')
        rec_plan_obj = self.pool.get('account.subscription')
        if 'is_active' in vals and not vals['is_active']:
            for journal in self.browse(cr, uid, ids, fields_to_fetch=['type', 'code', 'is_active'], context=context):
                if not journal.is_active:  # skip the checks if the journal is already inactive
                    continue
                if journal.type in ['bank', 'cheque', 'cash']:  # liquidity journals
                    if reg_obj.search_exist(cr, uid, [('journal_id', '=', journal.id), ('state', '!=', 'confirm')], context=context):
                        raise osv.except_osv(_('Error'),
                                             _("Please close the registers linked to the journal %s before inactivating it.") % journal.code)
                    if am_obj.search_exist(cr, uid,
                                           [('journal_id', '=', journal.id), ('status', '=', 'manu'), ('state', '!=', 'posted')],
                                           context=context):
                        raise osv.except_osv(_('Error'),
                                             _("Please post all the manual Journal Entries on the journal %s before inactivating it.") %
                                             journal.code)
                    if journal.type in ['bank', 'cash']:
                        last_reg_sql = """
                            SELECT reg.id
                            FROM account_bank_statement reg
                            INNER JOIN account_period p ON reg.period_id = p.id
                            INNER JOIN account_journal j ON reg.journal_id = j.id
                            WHERE j.id = %s
                            ORDER BY p.date_start DESC LIMIT 1
                        """
                        cr.execute(last_reg_sql, (journal.id,))
                        last_reg_id = cr.fetchone()

                        if last_reg_id:
                            balance_end = reg_obj.browse(cr, uid, last_reg_id[0], fields_to_fetch=['balance_end']).balance_end or 0.0
                            if abs(balance_end) > 10**-3:
                                raise osv.except_osv(_('Error'),
                                                     _("The journal %s cannot be inactivated because the balance of the "
                                                       "last register is not zero.") % journal.code)
                    if journal.type == 'bank' and not context.get('sync_update_execution'):
                        related_chq_id = self.search(cr, uid, [('bank_journal_id', '=', journal.id),
                                                               ('is_active', '=', 't')], context=context)
                        if related_chq_id:
                            chq_journal = self.browse(cr, uid, related_chq_id[0], context=context)
                            raise osv.except_osv(_('Error'), _("The bank journal %s cannot be inactivated because the "
                                                               "related cheque journal %s is still active.") % (journal.code, chq_journal.code))

                else:  # non-liquidity journals
                    if am_obj.search_exist(cr, uid, [('journal_id', '=', journal.id), ('state', '!=', 'posted')], context=context):
                        raise osv.except_osv(_('Error'),
                                             _("All entries booked on %s must be posted before inactivating the journal.") % journal.code)
                    if inv_obj.search_exist(cr, uid, [('journal_id', '=', journal.id), ('state', '=', 'draft')], context=context):
                        raise osv.except_osv(_('Error'),
                                             _("The journal %s cannot be inactivated because there are still some invoices "
                                               "in Draft state on this journal.") % journal.code)
                    rec_model_ids = rec_model_obj.search(cr, uid, [('journal_id', '=', journal.id)], order='NO_ORDER', context=context)
                    if rec_model_ids and rec_plan_obj.search_exist(cr, uid,
                                                                   [('model_id', 'in', rec_model_ids), ('state', '!=', 'done')],
                                                                   context=context):
                        raise osv.except_osv(_('Error'),
                                             _("The journal %s cannot be inactivated because a Recurring Plan which is not Done "
                                               "uses a Recurring Model with this journal.") % journal.code)
        return True

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if context is None:
            context = {}
        if 'code' in vals and vals['code']:
            code = vals['code'].strip()
            vals.update({'code': code})
        if 'name' in vals and vals['name']:
            name = vals['name'].strip()
            vals.update({'name': name})
        for journal in self.browse(cr, uid, ids, context=context):
            if 'company_id' in vals and journal.company_id.id != vals['company_id']:
                move_lines = self.pool.get('account.move.line').search(cr, uid, [('journal_id', 'in', ids)])
                if move_lines:
                    raise osv.except_osv(_('Warning !'), _('You cannot modify company of this journal as its related record exist in Entry Lines'))
            if not journal.is_current_instance and not journal.is_coordo_editable \
                    and not context.get('sync_update_execution'):
                raise osv.except_osv(_('Warning'), _("You can't edit a Journal that doesn't belong to the current instance."))
            self._remove_unnecessary_links(cr, uid, vals, journal_id=journal.id, context=context)
            if 'is_active' in vals and not vals['is_active'] and (not context.get('sync_update_execution') or not vals.get('inactivation_date')):
                if not journal.inactivation_date:
                    vals.update({'inactivation_date': datetime.today().date()})
                else:
                    cr.execute("SELECT date(max(coalesce(write_date, create_date))) FROM account_move WHERE journal_id=%s", (journal.id, ))
                    last_entry = cr.fetchone()
                    if last_entry and last_entry[0] and last_entry[0] > journal.inactivation_date:
                        vals.update({'inactivation_date': datetime.today().date()})
        self._check_journal_inactivation(cr, uid, ids, vals, context=context)
        ret = super(account_journal, self).write(cr, uid, ids, vals, context=context)
        if vals.get('currency', False):
            context.update({'curr_check': True})
        self._check_journal_constraints(cr, uid, ids, context=context)
        return ret

    def create_sequence(self, cr, uid, vals, context=None):
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = vals['name']
        code = vals['code'].lower()

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'active': True,
            'prefix': '',
            'padding': 4,
            'number_increment': 1
        }
        return seq_pool.create(cr, uid, seq)

    def create(self, cr, uid, vals, context=None):
        if not 'sequence_id' in vals or not vals['sequence_id']:
            vals.update({'sequence_id': self.create_sequence(cr, uid, vals, context)})
        if 'code' in vals and vals['code']:
            code = vals['code'].strip()
            vals.update({'code': code})
        if 'name' in vals and vals['name']:
            name = vals['name'].strip()
            vals.update({'name': name})
        self._remove_unnecessary_links(cr, uid, vals, context=context)
        journal_id = super(account_journal, self).create(cr, uid, vals, context)
        if vals.get('currency', False):
            context.update({'curr_check': True})
        self._check_journal_constraints(cr, uid, [journal_id], context=context)
        return journal_id

    def name_get(self, cr, user, ids, context=None):
        """
        Returns a list of tupples containing id, name.
        result format: {[(id, name), (id, name), ...]}

        @param cr: A database cursor
        @param user: ID of the user currently logged in
        @param ids: list of ids for which name should be read
        @param context: context arguments, like lang, time zone

        @return: Returns a list of tupples containing id, name
        """
        result = self.browse(cr, user, ids, context=context)
        res = []
        for rs in result:
            name = rs.name
            if rs.currency:
                name = "%s (%s)" % (rs.name, rs.currency.name)
            res += [(rs.id, name)]
        return res

    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if context is None:
            context = {}
        ids = []
        if context.get('journal_type', False):
            args += [('type','=',context.get('journal_type'))]
        if name:
            ids = self.search(cr, user, [('code', 'ilike', name)]+ args, limit=limit, context=context)
        if not ids:
            ids = self.search(cr, user, [('name', 'ilike', name)]+ args, limit=limit, context=context)#fix it ilike should be replace with operator

        return self.name_get(cr, user, ids, context=context)

    def onchange_type(self, cr, uid, ids, type, currency, context=None):
        obj_data = self.pool.get('ir.model.data')
        user_pool = self.pool.get('res.users')

        type_map = {
            'sale':'account_sp_journal_view',
            'sale_refund':'account_sp_refund_journal_view',
            'purchase':'account_sp_journal_view',
            'purchase_refund':'account_sp_refund_journal_view',
            'cash':'account_journal_bank_view',
            'bank':'account_journal_bank_view',
            'general':'account_journal_view',
            'situation':'account_journal_view'
        }

        res = {}

        view_id = type_map.get(type, 'account_journal_view')

        user = user_pool.browse(cr, uid, uid)
        if type in ('cash', 'bank') and currency and user.company_id.currency_id.id != currency:
            view_id = 'account_journal_bank_view_multi'
        data_id = obj_data.search(cr, uid, [('model','=','account.journal.view'), ('name','=',view_id)])
        data = obj_data.browse(cr, uid, data_id[0], context=context)

        res.update({
            'centralisation':type == 'situation',
            'view_id':data.res_id,
        })

        return {
            'value':res
        }

account_journal()

class account_fiscalyear(osv.osv):
    _name = "account.fiscalyear"
    _description = "Fiscal Year"
    _columns = {
        'name': fields.char('Fiscal Year', size=64, required=True),
        'code': fields.char('Code', size=6, required=True),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'date_start': fields.date('Start Date', required=True),
        'date_stop': fields.date('End Date', required=True),
        'period_ids': fields.one2many('account.period', 'fiscalyear_id', 'Periods'),
        'state': fields.selection([('draft','Open'), ('done','Closed')], 'State', readonly=True),
    }
    _defaults = {
        'state': 'draft',
        'company_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.id,
    }
    _order = "date_start DESC"

    def _check_fiscal_year(self, cr, uid, ids, context=None):
        current_fiscal_yr = self.browse(cr, uid, ids, context=context)[0]
        obj_fiscal_ids = self.search(cr, uid, [('company_id', '=', current_fiscal_yr.company_id.id)], context=context)
        obj_fiscal_ids.remove(ids[0])
        data_fiscal_yr = self.browse(cr, uid, obj_fiscal_ids, context=context)

        for old_fy in data_fiscal_yr:
            if old_fy.company_id.id == current_fiscal_yr['company_id'].id:
                # Condition to check if the current fiscal year falls in between any previously defined fiscal year
                if old_fy.date_start <= current_fiscal_yr['date_start'] <= old_fy.date_stop or \
                        old_fy.date_start <= current_fiscal_yr['date_stop'] <= old_fy.date_stop:
                    return False
        return True

    def _check_duration(self, cr, uid, ids, context=None):
        obj_fy = self.browse(cr, uid, ids[0], context=context)
        if obj_fy.date_stop < obj_fy.date_start:
            return False
        return True

    _constraints = [
        (_check_duration, 'Error! The duration of the Fiscal Year is invalid. ', ['date_stop']),
        (_check_fiscal_year, 'Error! You cannot define overlapping fiscal years',['date_start', 'date_stop'])
    ]

    def create_period3(self,cr, uid, ids, context=None):
        return self.create_period(cr, uid, ids, context, 3)

    def create_period(self,cr, uid, ids, context=None, interval=1):
        period_obj = self.pool.get('account.period')
        for fy in self.browse(cr, uid, ids, context=context):
            ds = datetime.datetime.strptime(fy.date_start, '%Y-%m-%d')
            i = 0
            while ds.strftime('%Y-%m-%d')<fy.date_stop:
                i += 1
                de = ds + relativedelta(months=interval, days=-1)

                if de.strftime('%Y-%m-%d')>fy.date_stop:
                    de = datetime.datetime.strptime(fy.date_stop, '%Y-%m-%d')

                period_obj.create(cr, uid, {
                    'name': ds.strftime('%b %Y'),
                    'code': ds.strftime('%b %Y'),
                    'date_start': ds.strftime('%Y-%m-%d'),
                    'date_stop': de.strftime('%Y-%m-%d'),
                    'fiscalyear_id': fy.id,
                    'special': False,
                    'number': i,
                })
                ds = ds + relativedelta(months=interval)

            ds = datetime.datetime.strptime(fy.date_stop, '%Y-%m-%d')
            for period_nb in (13, 14, 15):
                period_obj.create(cr, uid, {
                    'name': 'Period %d %d' % (period_nb, ds.year),
                    'code': 'Period %d %d' % (period_nb, ds.year),
                    'date_start': '%d-12-01' % (ds.year),
                    'date_stop': '%d-12-31' % (ds.year),
                    'fiscalyear_id': fy.id,
                    'special': True,
                    'number': period_nb,
                })
        # create extra period 16
        self.pool.get('account.year.end.closing').create_periods(cr, uid, fy.id, periods_to_create=[16], context=context)
        return True


    def find(self, cr, uid, dt=None, exception=True, context=None):
        if not dt:
            dt = time.strftime('%Y-%m-%d')
        ids = self.search(cr, uid, [('date_start', '<=', dt), ('date_stop', '>=', dt)])
        if not ids:
            if exception:
                raise osv.except_osv(_('Error !'), _('No fiscal year defined for this date !\nPlease create one.'))
            else:
                return False
        return ids[0]

    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=80):
        if args is None:
            args = []
        if context is None:
            context = {}
        ids = []
        if name:
            ids = self.search(cr, user, [('code', 'ilike', name)]+ args, limit=limit)
        if not ids:
            ids = self.search(cr, user, [('name', operator, name)]+ args, limit=limit)
        return self.name_get(cr, user, ids, context=context)

    def _get_normal_period_from_to(self, cr, uid, _id, context=None):
        start_period = False
        end_period = False

        cr.execute('''
            SELECT x.id FROM (
                (SELECT p.id, p.date_start as date
                   FROM account_period p
                   LEFT JOIN account_fiscalyear f ON (p.fiscalyear_id = f.id)
                   WHERE f.id = %(fy_id)s and number != 0
                   ORDER BY p.date_start ASC
                   LIMIT 1
                )
            UNION ALL
                (SELECT p.id, p.date_stop as date
                   FROM account_period p
                   LEFT JOIN account_fiscalyear f ON (p.fiscalyear_id = f.id)
                   WHERE f.id = %(fy_id)s and number != 0
                   AND p.date_start < NOW()
                   ORDER BY p.date_stop DESC, p.number DESC
                   LIMIT 1
                )
            ) AS x ORDER BY date
        ''', {'fy_id': _id})

        periods =  [i[0] for i in cr.fetchall()]
        if periods and len(periods) > 1:
            start_period = periods[0]
            end_period = periods[1]
        return {'period_from': start_period, 'period_to': end_period}

account_fiscalyear()

class account_period(osv.osv):
    _name = "account.period"
    _description = "Account period"

    def _get_false(self, cr, uid, ids, *a, **b):
        """
        Returns False for all ids (cf. only the search method is used for the field)
        """
        return {}.fromkeys(ids, False)

    def _search_period_visible(self, cr, uid, obj, name, args, context=None):
        """
        Returns a domain with the periods to display, based on args looking like:
        [('period_visible', '=', [fiscalyear_id, instance_id, all_missions])]
        """
        if context is None:
            context = {}
        period_dom = []
        if args:
            if len(args[0]) < 3 or args[0][1] != '=' or not isinstance(args[0][2], list) or len(args[0][2]) < 3:
                raise osv.except_osv(_('Error'), _('Filter not implemented.'))
            fy_id = args[0][2][0]
            inst_id = args[0][2][1]
            all_missions = args[0][2][2]
            if all_missions:
                period_dom = [('number', '!=', 16), ('fiscalyear_id', '=', fy_id), ('state', '!=', 'created')]
            else:
                period_dom = [('number', '!=', 16), ('child_mission_closed', '=', [inst_id, fy_id])]
        return period_dom

    _columns = {
        'name': fields.char('Period Name', size=64, required=True),
        'code': fields.char('Code', size=24),
        'special': fields.boolean('Opening/Closing Period', size=12,
                                  help="These periods can overlap."),
        'date_start': fields.date('Start of Period', required=True, states={'done':[('readonly',True)]}),
        'date_stop': fields.date('End of Period', required=True, states={'done':[('readonly',True)]}),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal Year', required=True, states={'done':[('readonly',True)]}, select=True),
        'state': fields.selection([('draft','Open'), ('done','Closed')], 'State', readonly=True,
                                  help='When monthly periods are created. The state is \'Draft\'. At the end of monthly period it is in \'Done\' state.'),
        'company_id': fields.related('fiscalyear_id', 'company_id', type='many2one', relation='res.company',
                                     string='Company', store=True, readonly=True),
        'period_visible': fields.function(_get_false, method=True, type='boolean', string='Display the period', store=False,
                                          fnct_search=_search_period_visible),
    }

    _defaults = {
        'state': 'draft',
    }

    def _check_duration(self,cr,uid,ids,context=None):
        obj_period = self.browse(cr, uid, ids[0], context=context)
        if obj_period.date_stop < obj_period.date_start:
            return False
        return True

    def _check_year_limit(self,cr,uid,ids,context=None):
        for obj_period in self.browse(cr, uid, ids, context=context):
            if obj_period.special:
                continue

            if obj_period.fiscalyear_id.date_stop < obj_period.date_stop or \
               obj_period.fiscalyear_id.date_stop < obj_period.date_start or \
               obj_period.fiscalyear_id.date_start > obj_period.date_start or \
               obj_period.fiscalyear_id.date_start > obj_period.date_stop:
                return False

            pids = self.search(cr, uid, [('date_stop','>=',obj_period.date_start),('date_start','<=',obj_period.date_stop),('special','=',False),('id','<>',obj_period.id)])
            for period in self.browse(cr, uid, pids):
                if period.fiscalyear_id.company_id.id==obj_period.fiscalyear_id.company_id.id:
                    return False
        return True

    _constraints = [
        (_check_duration, 'Error ! The duration of the Period(s) is/are invalid. ', ['date_stop']),
        (_check_year_limit, 'Invalid period ! Some periods overlap or the date period is not in the scope of the fiscal year. ', ['date_stop'])
    ]

    def next(self, cr, uid, period, step, context=None):
        ids = self.search(cr, uid, [('date_start','>',period.date_start)], order='date_start, number')
        if len(ids)>=step:
            return ids[step-1]
        return False

    def find(self, cr, uid, dt=None, context=None):
        """
        Gets the period(s) in which the dt is included, whatever the period state and including special December periods
        (note that Periods 0 with active = False are by default excluded)
        """
        if not dt:
            dt = time.strftime('%Y-%m-%d')
        ids = self.search(cr, uid, [('date_start', '<=', dt), ('date_stop', '>=', dt)], order='date_start, number')
        if not ids:
            raise osv.except_osv(_('Error !'), _('No period defined for this date: %s !\nPlease create a fiscal year.')%dt)
        return ids

    def action_draft(self, cr, uid, ids, *args):
        mode = 'draft'
        for id in ids:
            cr.execute('update account_journal_period set state=%s where period_id=%s', (mode, id))
            cr.execute('update account_period set state=%s where id=%s', (mode, id))
        return True

    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=100):
        if args is None:
            args = []
        if context is None:
            context = {}
        ids = []
        if name:
            ids = self.search(cr, user, [('code','ilike',name)]+ args, limit=limit, context=context)
        if not ids:
            ids = self.search(cr, user, [('name',operator,name)]+ args, limit=limit, context=context)
        return self.name_get(cr, user, ids, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if 'company_id' in vals:
            move_lines = self.pool.get('account.move.line').search(cr, uid, [('period_id', 'in', ids)])
            if move_lines:
                raise osv.except_osv(_('Warning !'), _('You cannot modify company of this period as its related record exist in Entry Lines'))
        return super(account_period, self).write(cr, uid, ids, vals, context=context)

    def build_ctx_periods(self, cr, uid, period_from_id, period_to_id):
        if not period_from_id and not period_to_id:
            return False
        company1_id = False
        company2_id = False
        period_date_start = False
        period_date_stop = False

        if period_from_id:
            period_from = self.browse(cr, uid, period_from_id)
            period_date_start = period_from.date_start
            company1_id = period_from.company_id.id
        if period_to_id:
            period_to = self.browse(cr, uid, period_to_id)
            period_date_stop = period_to.date_stop
            company2_id = period_to.company_id.id

        if company1_id and company2_id and company1_id != company2_id:
            raise osv.except_osv(_('Error'),
                                 _('You should have chosen periods that belongs to the same company'))
        if period_date_start and period_date_stop \
                and period_date_start > period_date_stop:
            raise osv.except_osv(_('Error'),
                                 _('Start period should be smaller then End period'))

        if not company1_id:
            company1_id = company2_id
        domain = [ ('company_id', '=', company1_id), ]
        if period_date_start:
            domain += [ ('date_start', '>=', period_date_start), ]
        if period_date_stop:
            domain += [ ('date_stop', '<=', period_date_stop), ]
        search_result = self.search(cr, uid, domain, order='date_start, number, id')

        # start_date and stop_date is not enough to select a period as more
        # than one have the same start/stop_date (Dec, periods 13, 14, 15 & 16)
        # if Dec 2016 is selected for period_from AND period_to, then only this
        # period should be returned.
        if period_from_id and period_from_id in search_result:
            from_index = search_result.index(period_from_id)
            search_result = search_result[from_index:]
        if period_to_id and period_to_id in search_result:
            to_index = search_result.index(period_to_id)
            if len(search_result) >= to_index+1:
                search_result = search_result[:to_index+1]
        return search_result

account_period()

class account_journal_period(osv.osv):
    _name = "account.journal.period"
    _description = "Journal Period"

    def _icon_get(self, cr, uid, ids, field_name, arg=None, context=None):
        result = {}.fromkeys(ids, 'STOCK_NEW')
        for r in self.read(cr, uid, ids, ['state']):
            result[r['id']] = {
                'draft': 'STOCK_NEW',
                'printed': 'STOCK_PRINT_PREVIEW',
                'done': 'STOCK_DIALOG_AUTHENTICATION',
            }.get(r['state'], 'STOCK_NEW')
        return result

    _columns = {
        'name': fields.char('Journal-Period Name', size=64, required=True),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True, ondelete="cascade"),
        'period_id': fields.many2one('account.period', 'Period', required=True, ondelete="cascade"),
        'icon': fields.function(_icon_get, method=True, string='Icon', type='char', size=32),
        'active': fields.boolean('Active', required=True, help="If the active field is set to False, it will allow you to hide the journal period without removing it."),
        'state': fields.selection([('draft','Draft'), ('printed','Printed'), ('done','Done')], 'State', required=True, readonly=True,
                                  help='When journal period is created. The state is \'Draft\'. If a report is printed it comes to \'Printed\' state. When all transactions are done, it comes in \'Done\' state.'),
        'fiscalyear_id': fields.related('period_id', 'fiscalyear_id', string='Fiscal Year', type='many2one', relation='account.fiscalyear', write_relate=False),
        'company_id': fields.related('journal_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True)
    }

    def _check(self, cr, uid, ids, context=None):
        for obj in self.browse(cr, uid, ids, context=context):
            cr.execute('select * from account_move_line where journal_id=%s and period_id=%s limit 1', (obj.journal_id.id, obj.period_id.id))
            res = cr.fetchall()
            if res:
                raise osv.except_osv(_('Error !'), _('You can not modify/delete a journal with entries for this period !'))
        return True

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        self._check(cr, uid, ids, context=context)
        return super(account_journal_period, self).write(cr, uid, ids, vals, context=context)

    def create(self, cr, uid, vals, context=None):
        period_id=vals.get('period_id',False)
        if period_id:
            period = self.pool.get('account.period').browse(cr, uid, period_id, context=context)
            # If the period is not open, the move line/account journal period are not created.
            if period.state == 'created':
                raise osv.except_osv(_('Error !'), _('Period \'%s\' is not open!') % (period.name,))
            elif period.state != 'done':
                vals['state'] = 'draft'
            else:
                vals['state'] = 'done'
        return super(account_journal_period, self).create(cr, uid, vals, context)

    def unlink(self, cr, uid, ids, context=None):
        self._check(cr, uid, ids, context=context)
        return super(account_journal_period, self).unlink(cr, uid, ids, context=context)

    _defaults = {
        'state': 'draft',
        'active': True,
    }
    _order = "period_id"

account_journal_period()

class account_fiscalyear(osv.osv):
    _inherit = "account.fiscalyear"
    _description = "Fiscal Year"
    _columns = {
        'end_journal_period_id':fields.many2one('account.journal.period','End of Year Entries Journal', readonly=True),
    }

    def copy(self, cr, uid, id, default={}, context=None):
        default.update({
            'period_ids': [],
            'end_journal_period_id': False
        })
        return super(account_fiscalyear, self).copy(cr, uid, id, default=default, context=context)

account_fiscalyear()
#----------------------------------------------------------
# Entries
#----------------------------------------------------------
class account_move(osv.osv):
    _name = "account.move"
    _description = "Account Entry"
    _order = 'id desc'

    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=80):
        """
        Returns a list of tupples containing id, name, as internally it is called {def name_get}
        result format: {[(id, name), (id, name), ...]}

        @param cr: A database cursor
        @param user: ID of the user currently logged in
        @param name: name to search
        @param args: other arguments
        @param operator: default operator is 'ilike', it can be changed
        @param context: context arguments, like lang, time zone
        @param limit: Returns first 'n' ids of complete result, default is 80.

        @return: Returns a list of tuples containing id and name
        """

        if not args:
            args = []
        ids = []
        if name:
            ids += self.search(cr, user, [('name', operator, name)]+args, limit=limit, context=context)

        if not ids and name and type(name) == int:
            ids += self.search(cr, user, [('id','=',name)]+args, limit=limit, context=context)

        if not ids and args:
            ids += self.search(cr, user, args, limit=limit, context=context)

        return self.name_get(cr, user, ids, context=context)

    def _get_period(self, cr, uid, context=None):
        periods = self.pool.get('account.period').find(cr, uid)
        if periods:
            return periods[0]
        return False

    def _amount_compute(self, cr, uid, ids, name, args, context, where =''):
        if not ids: return {}
        cr.execute( 'SELECT move_id, SUM(debit) '\
                    'FROM account_move_line '\
                    'WHERE move_id IN %s '\
                    'GROUP BY move_id', (tuple(ids),))
        result = dict(cr.fetchall())
        for id in ids:
            result.setdefault(id, 0.0)
        return result

    def _search_amount(self, cr, uid, obj, name, args, context):
        ids = set()
        for cond in args:
            amount = cond[2]
            if isinstance(cond[2],(list,tuple)):
                if cond[1] in ['in','not in']:
                    amount = tuple(cond[2])
                else:
                    continue
            else:
                if cond[1] in ['=like', 'like', 'not like', 'ilike', 'not ilike', 'in', 'not in', 'child_of']:
                    continue

            cr.execute("select move_id from account_move_line group by move_id having sum(debit) %s %%s" % (cond[1]),(amount,))  # ignore_sql_check
            res_ids = set(id[0] for id in cr.fetchall())
            ids = ids and (ids & res_ids) or res_ids
        if ids:
            return [('id','in',tuple(ids))]
        else:
            return [('id', '=', '0')]

    _columns = {
        'name': fields.char('Number', size=64, required=True, select=1),
        'ref': fields.char('Reference', size=64),
        'period_id': fields.many2one('account.period', 'Period', required=True, states={'posted':[('readonly',True)]}, select=1),
        'fiscalyear_id': fields.related('period_id', 'fiscalyear_id', type='many2one', relation='account.fiscalyear',
                                        string='Fiscal Year', store=False, write_relate=False),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True, states={'posted':[('readonly',True)]}, select=1),
        'state': fields.selection([('draft','Unposted'), ('posted','Posted')], 'State', required=True, readonly=True,
                                  help='All manually created new journal entry are usually in the state \'Unposted\', but you can set the option to skip that state on the related journal. In that case, they will be behave as journal entries automatically created by the system on document validation (invoices, bank statements...) and will be created in \'Posted\' state.'),
        'line_id': fields.one2many('account.move.line', 'move_id', 'Entries', states={'posted':[('readonly',True)]}),
        'to_check': fields.boolean('To Review', help='Check this box if you are unsure of that journal entry and if you want to note it as \'to be reviewed\' by an accounting expert.'),
        'partner_id': fields.related('line_id', 'partner_id', type="many2one", relation="res.partner", string="Partner", store=True, write_relate=False),
        'amount': fields.function(_amount_compute, method=True, string='Amount', digits_compute=dp.get_precision('Account'), type='float', fnct_search=_search_amount),
        'date': fields.date('Date', required=True, states={'posted':[('readonly',True)]}, select=True),
        'narration':fields.text('Narration'),
        'company_id': fields.related('journal_id','company_id',type='many2one',relation='res.company',string='Company', store=True, readonly=True),
        'asset_id': fields.many2one('product.asset', 'Asset', readonly=1, ondelete='restrict'),
    }
    _defaults = {
        'name': '/',
        'state': 'draft',
        'period_id': _get_period,
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        'company_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.id,
    }

    def _check_centralisation(self, cursor, user, ids, context=None):
        for move in self.browse(cursor, user, ids, context=context):
            if move.journal_id.centralisation:
                move_ids = self.search(cursor, user, [
                    ('period_id', '=', move.period_id.id),
                    ('journal_id', '=', move.journal_id.id),
                ])
                if len(move_ids) > 1:
                    return False
        return True

    def _check_period_journal(self, cursor, user, ids, context=None):
        for move in self.browse(cursor, user, ids, context=context):
            for line in move.line_id:
                if line.period_id.id != move.period_id.id:
                    return False
                if line.journal_id.id != move.journal_id.id:
                    return False
        return True

    _constraints = [
        (_check_centralisation,
            'You cannot create more than one move per period on centralized journal',
            ['journal_id']),
        (_check_period_journal,
            'You cannot create entries on different periods/journals in the same move',
            ['line_id']),
    ]

    def post(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        invoice = context.get('invoice', False)
        valid_moves = self.validate(cr, uid, ids, context)

        if not valid_moves:
            # Changed by UF-1470 from Unifield
            #            raise osv.except_osv(_('Integrity Error !'), _('You cannot validate a non-balanced entry !\nMake sure you have configured Payment Term properly !\nIt should contain atleast one Payment Term Line with type "Balance" !'))
            raise osv.except_osv(_('Integrity Error!'), _('You cannot validate a non-balanced entry ! All lines should have a “Valid” state to validate the entry.'))
        obj_sequence = self.pool.get('ir.sequence')
        asset_ids_to_check = []
        for move in self.browse(cr, uid, valid_moves, fields_to_fetch=['name', 'journal_id', 'period_id', 'asset_id'], context=context):
            if move.name =='/':
                new_name = False
                journal = move.journal_id

                if invoice and invoice.internal_number:
                    new_name = invoice.internal_number
                else:
                    if journal.sequence_id:
                        c = {'fiscalyear_id': move.period_id.fiscalyear_id.id}
                        new_name = obj_sequence.get_id(cr, uid, journal.sequence_id.id, context=c)
                    else:
                        raise osv.except_osv(_('Error'), _('No sequence defined on the journal !'))

                if new_name:
                    self.write(cr, uid, [move.id], {'name':new_name})

            if move.asset_id:
                asset_ids_to_check.append(move.asset_id.id)

        a = super(account_move, self).write(cr, uid, valid_moves,
                                            {'state':'posted'})

        if asset_ids_to_check:
            self.pool.get('product.asset').test_and_set_done(cr, uid, asset_ids_to_check, context=context)
        return a

    def button_validate(self, cursor, user, ids, context=None):
        for move in self.browse(cursor, user, ids, context=context):
            top = None
            for line in move.line_id:
                account = line.account_id
                while account:
                    account2 = account
                    account = account.parent_id
                if not top:
                    top = account2.id
                elif top!=account2.id:
                    raise osv.except_osv(_('Error !'), _('You cannot validate a Journal Entry unless all journal items are in same chart of accounts !'))
        return self.post(cursor, user, ids, context=context)

    def button_cancel(self, cr, uid, ids, context=None):
        for line in self.browse(cr, uid, ids, context=context):
            if not line.journal_id.update_posted:
                raise osv.except_osv(_('Error !'), _('You can not modify a posted entry of this journal !\nYou should set the journal to allow cancelling entries if you want to do that.'))
        if ids:
            cr.execute('UPDATE account_move '\
                       'SET state=%s '\
                       'WHERE id IN %s', ('draft', tuple(ids),))
        return True

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if context is None:
            context = {}
        c = context.copy()
        c['novalidate'] = True
        result = super(account_move, self).write(cr, uid, ids, vals, c)
        self.validate(cr, uid, ids, context=context)
        return result

    #
    # TODO: Check if period is closed !
    #
    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if 'line_id' in vals and context.get('copy'):
            for l in vals['line_id']:
                if not l[0]:
                    l[2].update({
                        'reconcile_id':False,
                        'reconcil_partial_id':False,
                        'analytic_lines':False,
                        'invoice':False,
                        'ref':False,
                        'balance':False,
                        'account_tax_id':False,
                    })

            if 'journal_id' in vals and vals.get('journal_id', False):
                for l in vals['line_id']:
                    if not l[0]:
                        l[2]['journal_id'] = vals['journal_id']
                context['journal_id'] = vals['journal_id']
            if 'period_id' in vals:
                for l in vals['line_id']:
                    if not l[0]:
                        l[2]['period_id'] = vals['period_id']
                context['period_id'] = vals['period_id']
            else:
                default_period = self._get_period(cr, uid, context)
                for l in vals['line_id']:
                    if not l[0]:
                        l[2]['period_id'] = default_period
                context['period_id'] = default_period

        if 'line_id' in vals:
            c = context.copy()
            c['novalidate'] = True
            result = super(account_move, self).create(cr, uid, vals, c)
            self.validate(cr, uid, [result], context)
        else:
            result = super(account_move, self).create(cr, uid, vals, context)
        return result

    def copy(self, cr, uid, id, default={}, context=None):
        if context is None:
            context = {}
        default.update({
            'state':'draft',
            'name':'/',
            'asset_id': False,
        })
        context.update({
            'copy':True
        })
        return super(account_move, self).copy(cr, uid, id, default, context)

    def _track_liquidity_entries(self, cr, uid, move, context=None):
        """
        Create an "account.bank.statement.line.deleted"
        to keep track of the deleted manual entries that were booked on Liquidity Journals
        """
        if context is None:
            context = {}
        reg_obj = self.pool.get('account.bank.statement')
        deleted_regline_obj = self.pool.get('account.bank.statement.line.deleted')
        period_obj = self.pool.get('account.period')
        is_liquidity = move.journal_id.type in ['bank', 'cheque', 'cash']
        if is_liquidity and move.status == 'manu' and not context.get('sync_update_execution', False):
            period_ids = period_obj.get_period_from_date(cr, uid, move.date, context=context)  # exclude special periods by default
            if period_ids:
                reg_domain = [('journal_id', '=', move.journal_id.id), ('period_id', '=', period_ids[0])]
                reg_ids = reg_obj.search(cr, uid, reg_domain, context=context, order='NO_ORDER', limit=1)
                if reg_ids:
                    vals = {
                        'statement_id': reg_ids[0],
                        'sequence': move.name,
                        'instance_id': move.instance_id and move.instance_id.id or False,
                    }
                    deleted_regline_obj.create(cr, uid, vals, context=context)

    def unlink(self, cr, uid, ids, context=None, check=True):
        if context is None:
            context = {}
        toremove = []
        obj_move_line = self.pool.get('account.move.line')
        for move in self.browse(cr, uid, ids, context=context):
            if move['state'] != 'draft':
                raise osv.except_osv(_('UserError'),
                                     _('You can not delete posted movement: "%s"!') % \
                                     move['name'])
            line_ids = [x.id for x in move.line_id]
            context['journal_id'] = move.journal_id.id
            context['period_id'] = move.period_id.id
            obj_move_line._update_check(cr, uid, line_ids, context)
            obj_move_line.unlink(cr, uid, line_ids, context=context, check=check) #ITWG-84: Pass also the check flag to the call
            self._track_liquidity_entries(cr, uid, move, context=context)
            toremove.append(move.id)
        result = super(account_move, self).unlink(cr, uid, toremove, context)
        return result

    def _centralise(self, cr, uid, move, mode, context=None):
        assert mode in ('debit', 'credit'), 'Invalid Mode' #to prevent sql injection
        currency_obj = self.pool.get('res.currency')
        move_line_obj = self.pool.get('account.move.line')
        if context is None:
            context = {}

        if mode=='credit':
            account_id = move.journal_id.default_debit_account_id.id
            mode2 = 'debit'
            if not account_id:
                raise osv.except_osv(_('UserError'),
                                     _('There is no default default debit account defined \n' \
                                       'on journal "%s"') % move.journal_id.name)
        else:
            account_id = move.journal_id.default_credit_account_id.id
            mode2 = 'credit'
            if not account_id:
                raise osv.except_osv(_('UserError'),
                                     _('There is no default default credit account defined \n' \
                                       'on journal "%s"') % move.journal_id.name)

        # find the first line of this move with the current mode
        # or create it if it doesn't exist
        cr.execute('select id from account_move_line where move_id=%s and centralisation=%s limit 1', (move.id, mode))
        res = cr.fetchone()
        if res:
            line_id = res[0]
        else:
            context.update({'journal_id': move.journal_id.id, 'period_id': move.period_id.id})
            line_id = move_line_obj.create(cr, uid, {
                'name': _(mode.capitalize()+' Centralisation'),
                'centralisation': mode,
                'account_id': account_id,
                'move_id': move.id,
                'journal_id': move.journal_id.id,
                'period_id': move.period_id.id,
                'date': move.period_id.date_stop,
                'debit': 0.0,
                'credit': 0.0,
            }, context)

        # find the first line of this move with the other mode
        # so that we can exclude it from our calculation
        cr.execute('select id from account_move_line where move_id=%s and centralisation=%s limit 1', (move.id, mode2))
        res = cr.fetchone()
        if res:
            line_id2 = res[0]
        else:
            line_id2 = 0

        cr.execute('SELECT SUM(%s) FROM account_move_line WHERE move_id=%%s AND id!=%%s' % (mode,), (move.id, line_id2))  # not_a_user_entry
        result = cr.fetchone()[0] or 0.0
        cr.execute('update account_move_line set '+mode2+'=%s where id=%s', (result, line_id))  # not_a_user_entry

        #adjust also the amount in currency if needed
        cr.execute("select currency_id, sum(amount_currency) as amount_currency from account_move_line where move_id = %s and currency_id is not null group by currency_id", (move.id,))
        for row in cr.dictfetchall():
            currency_id = currency_obj.browse(cr, uid, row['currency_id'], context=context)
            if not currency_obj.is_zero(cr, uid, currency_id, row['amount_currency']):
                amount_currency = row['amount_currency'] * -1
                account_id = amount_currency > 0 and move.journal_id.default_debit_account_id.id or move.journal_id.default_credit_account_id.id
                cr.execute('select id from account_move_line where move_id=%s and centralisation=\'currency\' and currency_id = %s limit 1', (move.id, row['currency_id']))
                res = cr.fetchone()
                if res:
                    cr.execute('update account_move_line set amount_currency=%s , account_id=%s where id=%s', (amount_currency, account_id, res[0]))
                else:
                    context.update({'journal_id': move.journal_id.id, 'period_id': move.period_id.id})
                    line_id = move_line_obj.create(cr, uid, {
                        'name': _('Currency Adjustment'),
                        'centralisation': 'currency',
                        'account_id': account_id,
                        'move_id': move.id,
                        'journal_id': move.journal_id.id,
                        'period_id': move.period_id.id,
                        'date': move.period_id.date_stop,
                        'debit': 0.0,
                        'credit': 0.0,
                        'currency_id': row['currency_id'],
                        'amount_currency': amount_currency,
                    }, context)

        return True

    def _hook_check_move_line(self, cr, uid, move_line, context=None):
        """
        Check date on move line. Should be the same as Journal Entry (account.move)
        """
        if not context:
            context = {}
        if not move_line:
            return False
        if move_line.date != move_line.move_id.date:
            raise osv.except_osv(_('Error'), _("Journal item does not have same posting date (%s) as journal entry (%s).") % (move_line.date, move_line.move_id.date))
        return True

    #
    # Validate a balanced move. If it is a centralised journal, create a move.
    #
    def validate(self, cr, uid, ids, context=None):
        if context and ('__last_update' in context):
            del context['__last_update']

        if context is None:
            context = {}

        valid_moves = [] #Maintains a list of moves which can be responsible to create analytic entries
        obj_analytic_line = self.pool.get('account.analytic.line')
        obj_move_line = self.pool.get('account.move.line')
        if ids:
            cr.execute('select id from account_move_line where move_id in %s for update', (tuple(ids),))
        for move in self.browse(cr, uid, ids, context):
            # Unlink old analytic lines on move_lines
            # UTP-803: condition on context added, if this context is set analytic lines won't be created,
            # so we don't delete it neither.
            # this use case happens in the pull sync,
            # when the account_bank_statement_line has a modification date > to the associated account_move and
            # if the associated account_move was previously synced.
            if move.journal_id.type == 'system':
                # US-822: consider system journal JE always valid (bypass)
                valid_moves.append(move)
                continue
            if not context.get('do_not_create_analytic_line') or not context.get('sync_update_execution'):
                for obj_line in move.line_id:
                    for obj in obj_line.analytic_lines:
                        obj_analytic_line.unlink(cr,uid,obj.id)

            journal = move.journal_id
            amount = 0
            amount_currency = 0
            line_ids = []
            line_draft_ids = []
            company_id = None
            for line in move.line_id:
                # Hook to check line
                self._hook_check_move_line(cr, uid, line, context=context)
                amount += line.debit - line.credit
                amount_currency += line.debit_currency or 0.0 - line.credit_currency or 0.0
                line_ids.append(line.id)
                if line.state=='draft':
                    line_draft_ids.append(line.id)

                if not company_id:
                    company_id = line.account_id.company_id.id
                if not company_id == line.account_id.company_id.id:
                    raise osv.except_osv(_('Error'), _("Couldn't create move between different companies"))

                if line.account_id.currency_id and line.currency_id:
                    if line.account_id.currency_id.id != line.currency_id.id and (line.account_id.currency_id.id != line.account_id.company_id.currency_id.id):
                        raise osv.except_osv(_('Error'), _("""Couldn't create move with currency different from the secondary currency of the account "%s - %s". Clear the secondary currency field of the account definition if you want to accept all currencies.""") % (line.account_id.code, line.account_id.name))

                if context.get('from_web_menu') and not line.name:
                    raise osv.except_osv(_('Error'), _('The Description is missing for one of the lines.'))

            # When clicking on "Save" for a MANUAL Journal Entry:
            # - Check that the period is open.
            # - IF there are JI, check that there are at least 2 lines
            # and that the entry is balanced using the booking amounts
            aml_duplication = '__copy_data_seen' in context and 'account.move.line' in context['__copy_data_seen'] or False
            if context.get('from_web_menu', False) \
                    and context.get('journal_id', False) and not context.get('button', False) \
                    and not context.get('copy') and not aml_duplication:
                if move.period_id and move.period_id.state != 'draft':
                    raise osv.except_osv(_('Warning'), _("You can't save entries in a non-open period: %s") % (move.period_id.name))
                if move.line_id:
                    if len(move.line_id) < 2:
                        raise osv.except_osv(_('Warning'), _('The entry must have at least two lines.'))
                    elif abs(amount_currency) > 10 ** -4:
                        raise osv.except_osv(_('Warning'), _('The entry must be balanced.'))

            # (US-1709) For a manual entry check that it's balanced using the booking amounts
            # For the other entries keep using the functional amounts
            if move.status == 'manu':
                entry_balanced = abs(amount_currency) < 10 ** -4 or False
            else:
                entry_balanced = abs(amount) < 10 ** -4 or False
            if entry_balanced:
                # If the move is balanced
                # Add to the list of valid moves
                # (analytic lines will be created later for valid moves)
                valid_moves.append(move)

                # Check whether the move lines are confirmed

                if not line_draft_ids:
                    continue
                # Update the move lines (set them as valid)

                obj_move_line.write(cr, uid, line_draft_ids, {
                    'journal_id': move.journal_id.id,
                    'period_id': move.period_id.id,
                    'state': 'valid'
                }, context, check=False)

                account = {}
                account2 = {}

                if journal.type in ('purchase','sale'):
                    for line in move.line_id:
                        code = amount = 0
                        key = (line.account_id.id, line.tax_code_id.id)
                        if key in account2:
                            code = account2[key][0]
                            amount = account2[key][1] * (line.debit + line.credit)
                        elif line.account_id.id in account:
                            code = account[line.account_id.id][0]
                            amount = account[line.account_id.id][1] * (line.debit + line.credit)
                        if (code or amount) and not (line.tax_code_id or line.tax_amount):
                            obj_move_line.write(cr, uid, [line.id], {
                                'tax_code_id': code,
                                'tax_amount': amount
                            }, context, check=False)
            elif journal.centralisation:
                # If the move is not balanced, it must be centralised...

                # Add to the list of valid moves
                # (analytic lines will be created later for valid moves)
                valid_moves.append(move)

                #
                # Update the move lines (set them as valid)
                #
                self._centralise(cr, uid, move, 'debit', context=context)
                self._centralise(cr, uid, move, 'credit', context=context)
                obj_move_line.write(cr, uid, line_draft_ids, {
                    'state': 'valid'
                }, context, check=False)
            else:
                # We can't validate it (it's unbalanced)
                # Setting the lines as draft
                obj_move_line.write(cr, uid, line_ids, {
                    'journal_id': move.journal_id.id,
                    'period_id': move.period_id.id,
                    'state': 'draft'
                }, context, check=False)
        # Create analytic lines for the valid moves
        for record in valid_moves:
            obj_move_line.create_analytic_lines(cr, uid, [line.id for line in record.line_id], context)

        valid_moves = [move.id for move in valid_moves]
        if valid_moves:
            # copy ad from account_move_line to asset line
            # case of AD copied from header to line on posting
            cr.execute('''update product_asset_line al
                set analytic_distribution_id = ml.analytic_distribution_id
                from account_move_line ml
                where
                    ml.asset_line_id = al.id
                    and (al.analytic_distribution_id!=ml.analytic_distribution_id or al.analytic_distribution_id is null)
                    and ml.analytic_distribution_id is not null
                    and ml.move_id in %s
            ''', (tuple(valid_moves),))
        return len(valid_moves) > 0 and valid_moves or False

    # US-852: At the end of each sync execution of the create move line, make a quick check if any other move lines of the same move were invalid
    # due to the missing of this move line? If yes, just set them to valid.
    def validate_sync(self, cr, uid, move_ids, context=None):
        if context is None:
            context = {}
        if not (context.get('sync_update_execution', False)) or not move_ids:
            return

        if isinstance(move_ids, int):
            move_ids = [move_ids]

        move_line_obj = self.pool.get('account.move.line')
        for move in self.browse(cr, uid, move_ids, context):
            if move.journal_id.type == 'system':
                continue

            amount = 0
            line_draft_ids = []
            for line in move.line_id:
                # Hook to check line
                amount += line.debit - line.credit
                if line.state=='draft':
                    line_draft_ids.append(line.id)

            if line_draft_ids:
                if abs(amount) < 10 ** -4:
                    move_line_obj.write(cr, uid, line_draft_ids, {'state': 'valid'}, context, check=False)
                elif move.journal_id.centralisation:
                    move_line_obj.write(cr, uid, line_draft_ids, {'state': 'valid'}, context, check=False)
        return True
account_move()

class account_move_reconcile(osv.osv):
    _name = "account.move.reconcile"
    _description = "Account Reconciliation"
    _columns = {
        'name': fields.char('Name', size=64, required=True, select=1),
        'type': fields.char('Type', size=16, required=True),
        'line_id': fields.one2many('account.move.line', 'reconcile_id', 'Entry Lines'),
        'line_partial_ids': fields.one2many('account.move.line', 'reconcile_partial_id', 'Partial Entry lines'),
        'create_date': fields.date('Creation date', readonly=True),
    }
    _defaults = {
        'name': lambda self,cr,uid,ctx={}: self.pool.get('ir.sequence').get(cr, uid, 'account.reconcile') or '/',
    }


account_move_reconcile()

#----------------------------------------------------------
# Tax
#----------------------------------------------------------
"""
a documenter
child_depend: la taxe depend des taxes filles
"""
class account_tax_code(osv.osv):
    """
    A code for the tax object.

    This code is used for some tax declarations.
    """
    def _sum(self, cr, uid, ids, name, args, context, where ='', where_params=()):
        parent_ids = tuple(self.search(cr, uid, [('parent_id', 'child_of', ids)]))
        if context.get('based_on', 'invoices') == 'payments':
            cr.execute('''
                SELECT line.tax_code_id, sum(line.tax_amount)
                FROM account_move_line AS line,
                     account_move AS move
                     LEFT JOIN account_invoice invoice ON
                        (invoice.move_id = move.id)
                WHERE line.tax_code_id IN %%s %s
                    AND move.id = line.move_id
                    AND ((invoice.state = 'paid')
                        OR (invoice.id IS NULL))
                GROUP BY line.tax_code_id''' % where,
                       (parent_ids,) + where_params) # not_a_user_entry
        else:
            cr.execute('''
                SELECT line.tax_code_id, sum(line.tax_amount)
                FROM account_move_line AS line,
                account_move AS move
                WHERE line.tax_code_id IN %%s %s
                AND move.id = line.move_id
                GROUP BY line.tax_code_id''' % where,
                       (parent_ids,) + where_params) # not_a_user_entry
        res = dict(cr.fetchall())
        res2 = {}
        obj_precision = self.pool.get('decimal.precision')
        for record in self.browse(cr, uid, ids, context=context):
            def _rec_get(record):
                amount = res.get(record.id, 0.0)
                for rec in record.child_ids:
                    amount += _rec_get(rec) * rec.sign
                return amount
            res2[record.id] = round(_rec_get(record), obj_precision.precision_get(cr, uid, 'Account'))
        return res2

    def _sum_year(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        move_state = ('posted', )
        if context.get('state', 'all') == 'all':
            move_state = ('draft', 'posted', )
        if context.get('fiscalyear_id', False):
            fiscalyear_id = context['fiscalyear_id']
        else:
            fiscalyear_id = self.pool.get('account.fiscalyear').find(cr, uid, exception=False)
        where = ''
        where_params = ()
        if fiscalyear_id:
            pids = [str(x.id) for x in self.pool.get('account.fiscalyear').browse(cr, uid, fiscalyear_id).period_ids]
            if pids:
                where = ' AND line.period_id IN %s AND move.state IN %s '
                where_params = (tuple(pids), move_state)
        return self._sum(cr, uid, ids, name, args, context,
                         where=where, where_params=where_params)

    def _sum_period(self, cr, uid, ids, name, args, context):
        if context is None:
            context = {}
        move_state = ('posted', )
        if context.get('state', False) == 'all':
            move_state = ('draft', 'posted', )
        if context.get('period_id', False):
            period_id = context['period_id']
        else:
            period_id = self.pool.get('account.period').find(cr, uid)
            if not period_id:
                return dict.fromkeys(ids, 0.0)
            period_id = period_id[0]
        return self._sum(cr, uid, ids, name, args, context,
                         where=' AND line.period_id=%s AND move.state IN %s', where_params=(period_id, move_state))

    _name = 'account.tax.code'
    _description = 'Tax Code'
    _rec_name = 'code'
    _columns = {
        'name': fields.char('Tax Case Name', size=64, required=True, translate=True),
        'code': fields.char('Case Code', size=64),
        'info': fields.text('Description'),
        'sum': fields.function(_sum_year, method=True, string="Year Sum"),
        'sum_period': fields.function(_sum_period, method=True, string="Period Sum"),
        'parent_id': fields.many2one('account.tax.code', 'Parent Code', select=True),
        'child_ids': fields.one2many('account.tax.code', 'parent_id', 'Child Codes'),
        'line_ids': fields.one2many('account.move.line', 'tax_code_id', 'Lines'),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'sign': fields.float('Coefficent for parent', required=True, help='You can specify here the coefficient that will be used when consolidating the amount of this case into its parent. For example, set 1/-1 if you want to add/substract it.'),
        'notprintable':fields.boolean("Not Printable in Invoice", help="Check this box if you don't want any VAT related to this Tax Code to appear on invoices"),
    }

    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=80):
        if not args:
            args = []
        if context is None:
            context = {}
        ids = self.search(cr, user, ['|',('name',operator,name),('code',operator,name)] + args, limit=limit, context=context)
        return self.name_get(cr, user, ids, context)

    def name_get(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]
        if not ids:
            return []
        if isinstance(ids, int):
            ids = [ids]
        reads = self.read(cr, uid, ids, ['name','code'], context, load='_classic_write')
        return [(x['id'], (x['code'] and (x['code'] + ' - ') or '') + x['name']) \
                for x in reads]

    def _default_company(self, cr, uid, context=None):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if user.company_id:
            return user.company_id.id
        return self.pool.get('res.company').search(cr, uid, [('parent_id', '=', False)])[0]
    _defaults = {
        'company_id': _default_company,
        'sign': 1.0,
        'notprintable': False,
    }

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default.update({'line_ids': [], 'register_line_id': False})
        return super(account_tax_code, self).copy(cr, uid, id, default, context)

    _check_recursion = check_cycle
    _constraints = [
        (_check_recursion, 'Error ! You can not create recursive accounts.', ['parent_id'])
    ]
    _order = 'code'

account_tax_code()

class account_tax(osv.osv):
    """
    A tax object.

    Type: percent, fixed, none, code
        PERCENT: tax = price * amount
        FIXED: tax = price + amount
        NONE: no tax line
        CODE: execute python code. localcontext = {'price_unit':pu, 'address':address_object}
            return result in the context
            Ex: result=round(price_unit*0.21,4)
    """

    def get_precision_tax():
        def change_digit_tax(cr, **kwargs):
            # modify the initial function so we can gather other customized fields
            if kwargs.get('computation', False):
                return pooler.get_pool(cr.dbname).get('decimal.precision').computation_get(cr, 1, 'Account')

            res = pooler.get_pool(cr.dbname).get('decimal.precision').precision_get(cr, 1, 'Account')
            return (16, res+2)
        return change_digit_tax

    _name = 'account.tax'
    _description = 'Tax'
    _trace = True
    _columns = {
        'name': fields.char('Tax Name', size=64, required=True, translate=True, help="This name will be displayed on reports"),
        'sequence': fields.integer('Sequence', required=True, help="The sequence field is used to order the tax lines from the lowest sequences to the higher ones. The order is important if you have a tax with several tax children. In this case, the evaluation order is important."),
        'amount': fields.float('Amount', required=True, digits_compute=get_precision_tax(), help="For taxes of type percentage, enter % ratio between -1 and 1, Example: 0.02 for 2% "),
        'active': fields.boolean('Active', help="If the active field is set to False, it will allow you to hide the tax without removing it."),
        'type': fields.selection([('percent','Percentage'), ('fixed','Fixed Amount')], 'Tax Type', required=True, help="The computation method for the tax amount."),
        'applicable_type': fields.selection([('true','Always')], 'Applicability', required=True, readonly=True, help="Always applicable."),
        'domain':fields.char('Domain', size=32, help="This field is only used if you develop your own module allowing developers to create specific taxes in a custom domain."),
        'account_collected_id':fields.many2one('account.account', 'Invoice Tax Account'),
        'account_paid_id':fields.many2one('account.account', 'Refund Tax Account'),
        'parent_id':fields.many2one('account.tax', 'Parent Tax Account', select=True),
        'child_ids':fields.one2many('account.tax', 'parent_id', 'Child Tax Accounts'),
        'child_depend':fields.boolean('Tax on Children', help="Set if the tax computation is based on the computation of child taxes rather than on the total amount."),
        'partner_id': fields.many2one('res.partner', 'Partner',
                                      domain=[('partner_type', '=', 'external'), ('active', '=', True)],
                                      ondelete='restrict'),
        'python_compute':fields.text('Python Code'), # deprecated
        'python_compute_inv':fields.text('Python Code (reverse)'), # deprecated
        'python_applicable':fields.text('Python Code'), # deprecated
        #
        # Fields used for the VAT declaration
        #
        'base_code_id': fields.many2one('account.tax.code', 'Account Base Code', help="Use this code for the VAT declaration."),
        'tax_code_id': fields.many2one('account.tax.code', 'Account Tax Code', help="Use this code for the VAT declaration."),
        'base_sign': fields.float('Base Code Sign', help="Usually 1 or -1."),
        'tax_sign': fields.float('Tax Code Sign', help="Usually 1 or -1."),

        # Same fields for refund invoices

        'ref_base_code_id': fields.many2one('account.tax.code', 'Refund Base Code', help="Use this code for the VAT declaration."),
        'ref_tax_code_id': fields.many2one('account.tax.code', 'Refund Tax Code', help="Use this code for the VAT declaration."),
        'ref_base_sign': fields.float('Base Code Sign', help="Usually 1 or -1."),
        'ref_tax_sign': fields.float('Tax Code Sign', help="Usually 1 or -1."),
        'include_base_amount': fields.boolean('Included in base amount', help="Indicates if the amount of tax must be included in the base amount for the computation of the next taxes"),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'description': fields.char('Tax Code',size=32),
        'price_include': fields.boolean('Tax Included in Price', help="Check this if the price you use on the product and invoices includes this tax."),
        'type_tax_use': fields.selection([('sale','Sale'),('purchase','Purchase'),('all','All')], 'Tax Application', required=True)

    }

    def _check_percent(self, cr, uid, ids, context=None):
        obj = self.browse(cr, uid, ids[0], context=context)
        if obj.type == 'percent' and abs(obj.amount) > 1.0:
            return False
        return True

    _constraints = [
        (_check_percent, 'For taxes of type percentage, enter % ratio between -1 and 1, Example: 0.02 for 2% ', ['amount']),
    ]

    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=80):
        """
        Returns a list of tupples containing id, name, as internally it is called {def name_get}
        result format: {[(id, name), (id, name), ...]}

        @param cr: A database cursor
        @param user: ID of the user currently logged in
        @param name: name to search
        @param args: other arguments
        @param operator: default operator is 'ilike', it can be changed
        @param context: context arguments, like lang, time zone
        @param limit: Returns first 'n' ids of complete result, default is 80.

        @return: Returns a list of tupples containing id and name
        """
        if not args:
            args = []
        if context is None:
            context = {}
        ids = []
        if name:
            ids = self.search(cr, user, [('description', '=', name)] + args, limit=limit, context=context)
            if not ids:
                ids = self.search(cr, user, [('name', operator, name)] + args, limit=limit, context=context)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context or {})
        return self.name_get(cr, user, ids, context=context)

    def _check_tax_partner(self, cr, uid, vals, context=None):
        """
        Raises an error in case the partner selected for the tax isn't allowed
        """
        if context is None:
            context = {}
        partner_obj = self.pool.get('res.partner')
        if vals.get('partner_id'):
            partner = partner_obj.browse(cr, uid, vals['partner_id'], fields_to_fetch=['active', 'partner_type', 'name'], context=context)
            if not partner.active or partner.partner_type != 'external':
                raise osv.except_osv(_('Error'),
                                     _("You can't link the tax to the Partner %s: only active external partners are allowed.") % partner.name)

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        self._check_tax_partner(cr, uid, vals, context=context)
        return super(account_tax, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        self._check_tax_partner(cr, uid, vals, context=context)
        return super(account_tax, self).write(cr, uid, ids, vals, context=context)

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        journal_pool = self.pool.get('account.journal')

        if context and 'type' in context:
            if context.get('type') in ('out_invoice','out_refund'):
                args += [('type_tax_use','in',['sale','all'])]
            elif context.get('type') in ('in_invoice','in_refund'):
                args += [('type_tax_use','in',['purchase','all'])]

        if context and 'journal_id' in context:
            journal = journal_pool.browse(cr, uid, context.get('journal_id'))
            if journal.type in ('sale', 'purchase'):
                args += [('type_tax_use','in',[journal.type,'all'])]

        return super(account_tax, self).search(cr, uid, args, offset, limit,
                                               order, context, count)

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        res = []
        for record in self.read(cr, uid, ids, ['description','name'], context=context):
            name = record['description'] and record['description'] or record['name']
            res.append((record['id'],name ))
        return res

    def _default_company(self, cr, uid, context=None):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if user.company_id:
            return user.company_id.id
        return self.pool.get('res.company').search(cr, uid, [('parent_id', '=', False)])[0]

    _defaults = {
        'applicable_type': 'true',
        'type': 'percent',
        'amount': 0,
        'price_include': 0,
        'active': 1,
        'type_tax_use': 'all',
        'sequence': 1,
        'ref_tax_sign': 1,
        'ref_base_sign': 1,
        'tax_sign': 1,
        'base_sign': 1,
        'include_base_amount': False,
        'company_id': _default_company,
    }
    _order = 'sequence'

    def _applicable(self, cr, uid, taxes, price_unit, address_id=None, product=None, partner=None):
        res = []
        for tax in taxes:
            res.append(tax)
        return res

    def _unit_compute(self, cr, uid, taxes, price_unit, address_id=None, product=None, partner=None, quantity=0):
        taxes = self._applicable(cr, uid, taxes, price_unit, address_id, product, partner)
        res = []
        cur_price_unit=price_unit
        for tax in taxes:
            # we compute the amount for the current tax object and append it to the result
            description = "%s%s%s" % (tax.name, partner and ' - ' or '', partner and partner.name or '')  # tax name and INVOICE partner name
            data = {'id':tax.id,
                    'name': description,
                    'account_collected_id':tax.account_collected_id.id,
                    'account_paid_id':tax.account_paid_id.id,
                    'base_code_id': tax.base_code_id.id,
                    'ref_base_code_id': tax.ref_base_code_id.id,
                    'sequence': tax.sequence,
                    'base_sign': tax.base_sign,
                    'tax_sign': tax.tax_sign,
                    'ref_base_sign': tax.ref_base_sign,
                    'ref_tax_sign': tax.ref_tax_sign,
                    'price_unit': cur_price_unit,
                    'tax_code_id': tax.tax_code_id.id,
                    'ref_tax_code_id': tax.ref_tax_code_id.id,
                    }
            res.append(data)
            if tax.type=='percent':
                amount = cur_price_unit * tax.amount
                data['amount'] = amount

            elif tax.type=='fixed':
                data['amount'] = tax.amount
                data['tax_amount']=quantity

            amount2 = data.get('amount', 0.0)
            if tax.child_ids:
                if tax.child_depend:
                    latest = res.pop()
                amount = amount2
                child_tax = self._unit_compute(cr, uid, tax.child_ids, amount, address_id, product, partner, quantity)
                res.extend(child_tax)
                if tax.child_depend:
                    for r in res:
                        for name in ('base','ref_base'):
                            if latest[name+'_code_id'] and latest[name+'_sign'] and not r[name+'_code_id']:
                                r[name+'_code_id'] = latest[name+'_code_id']
                                r[name+'_sign'] = latest[name+'_sign']
                                r['price_unit'] = latest['price_unit']
                                latest[name+'_code_id'] = False
                        for name in ('tax','ref_tax'):
                            if latest[name+'_code_id'] and latest[name+'_sign'] and not r[name+'_code_id']:
                                r[name+'_code_id'] = latest[name+'_code_id']
                                r[name+'_sign'] = latest[name+'_sign']
                                r['amount'] = data['amount']
                                latest[name+'_code_id'] = False
            if tax.include_base_amount:
                cur_price_unit+=amount2
        return res

    def compute_all(self, cr, uid, taxes, price_unit, quantity, address_id=None, product=None, partner=None):
        """
        RETURN: {
                'total': 0.0,                # Total without taxes
                'total_included: 0.0,        # Total with taxes
                'taxes': []                  # List of taxes, see compute for the format
            }
        """
        precision = self.pool.get('decimal.precision').precision_get(cr, uid, 'Account')
        totalin = totalex = round(price_unit * quantity, precision)
        tin = []
        tex = []
        for tax in taxes:
            if tax.price_include:
                tin.append(tax)
            else:
                tex.append(tax)
        tin = self.compute_inv(cr, uid, tin, price_unit, quantity, address_id=address_id, product=product, partner=partner)
        for r in tin:
            totalex -= r.get('amount', 0.0)
        totlex_qty = 0.0
        try:
            totlex_qty=totalex/quantity
        except:
            pass
        tex = self._compute(cr, uid, tex, totlex_qty, quantity, address_id=address_id, product=product, partner=partner)
        for r in tex:
            totalin += r.get('amount', 0.0)
        return {
            'total': totalex,
            'total_included': totalin,
            'taxes': tin + tex
        }

    def compute(self, cr, uid, taxes, price_unit, quantity, address_id=None, product=None, partner=None):
        logger = netsvc.Logger()
        logger.notifyChannel("warning", netsvc.LOG_WARNING,
                             "Deprecated, use compute_all(...)['taxes'] instead of compute(...) to manage prices with tax included")
        return self._compute(cr, uid, taxes, price_unit, quantity, address_id, product, partner)

    def _compute(self, cr, uid, taxes, price_unit, quantity, address_id=None, product=None, partner=None):
        """
        Compute tax values for given PRICE_UNIT, QUANTITY and a buyer/seller ADDRESS_ID.

        RETURN:
            [ tax ]
            tax = {'name':'', 'amount':0.0, 'account_collected_id':1, 'account_paid_id':2}
            one tax for each tax id in IDS and their children
        """
        res = self._unit_compute(cr, uid, taxes, price_unit, address_id, product, partner, quantity)
        total = 0.0
        precision_pool = self.pool.get('decimal.precision')
        for r in res:
            r['amount'] = round(r.get('amount', 0.0) * quantity, precision_pool.precision_get(cr, uid, 'Account'))
            total += r['amount']
        return res

    def _unit_compute_inv(self, cr, uid, taxes, price_unit, address_id=None, product=None, partner=None):
        taxes = self._applicable(cr, uid, taxes, price_unit, address_id, product, partner)
        res = []
        taxes.reverse()
        cur_price_unit = price_unit

        tax_parent_tot = 0.0
        for tax in taxes:
            if (tax.type=='percent') and not tax.include_base_amount:
                tax_parent_tot += tax.amount

        for tax in taxes:
            if (tax.type=='fixed') and not tax.include_base_amount:
                cur_price_unit -= tax.amount

        for tax in taxes:
            if tax.type=='percent':
                if tax.include_base_amount:
                    amount = cur_price_unit - (cur_price_unit / (1 + tax.amount))
                else:
                    amount = (cur_price_unit / (1 + tax_parent_tot)) * tax.amount

            elif tax.type=='fixed':
                amount = tax.amount

            if tax.include_base_amount:
                cur_price_unit -= amount
                todo = 0
            else:
                todo = 1
            description = "%s%s%s" % (tax.name, partner and ' - ' or '', partner and partner.name or '')  # tax name and INVOICE partner name
            res.append({
                'id': tax.id,
                'todo': todo,
                'name': description,
                'amount': amount,
                'account_collected_id': tax.account_collected_id.id,
                'account_paid_id': tax.account_paid_id.id,
                'base_code_id': tax.base_code_id.id,
                'ref_base_code_id': tax.ref_base_code_id.id,
                'sequence': tax.sequence,
                'base_sign': tax.base_sign,
                'tax_sign': tax.tax_sign,
                'ref_base_sign': tax.ref_base_sign,
                'ref_tax_sign': tax.ref_tax_sign,
                'price_unit': cur_price_unit,
                'tax_code_id': tax.tax_code_id.id,
                'ref_tax_code_id': tax.ref_tax_code_id.id,
            })
            if tax.child_ids:
                if tax.child_depend:
                    del res[-1]
                    amount = price_unit

            parent_tax = self._unit_compute_inv(cr, uid, tax.child_ids, amount, address_id, product, partner)
            res.extend(parent_tax)

        total = 0.0
        for r in res:
            if r['todo']:
                total += r['amount']
        for r in res:
            r['price_unit'] -= total
            r['todo'] = 0
        return res

    def compute_inv(self, cr, uid, taxes, price_unit, quantity, address_id=None, product=None, partner=None):
        """
        Compute tax values for given PRICE_UNIT, QUANTITY and a buyer/seller ADDRESS_ID.
        Price Unit is a VAT included price

        RETURN:
            [ tax ]
            tax = {'name':'', 'amount':0.0, 'account_collected_id':1, 'account_paid_id':2}
            one tax for each tax id in IDS and their children
        """
        res = self._unit_compute_inv(cr, uid, taxes, price_unit, address_id, product, partner=partner)
        total = 0.0
        obj_precision = self.pool.get('decimal.precision')
        for r in res:
            prec = obj_precision.precision_get(cr, uid, 'Account')
            r['amount'] = round(r['amount'] * quantity, prec)
            total += r['amount']
        return res

    def unlink(self, cr, uid, ids, context=None):
        """
        Prevents deletion in case the tax object is still referenced elsewhere
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        product_obj = self.pool.get('product.template')
        acc_obj = self.pool.get('account.account')
        acc_inv_obj = self.pool.get('account.invoice.line')
        acc_inv_tax_obj = self.pool.get('account.invoice.tax')
        purch_obj = self.pool.get('purchase.order.line')
        sale_obj = self.pool.get('sale.order.line')
        if product_obj.search_exists(cr, uid, ['|', ('taxes_id', 'in', ids), ('supplier_taxes_id', 'in', ids)], context=context) or \
                acc_obj.search_exists(cr, uid, [('tax_ids', 'in', ids)], context=context) or \
                acc_inv_obj.search_exists(cr, uid, [('invoice_line_tax_id', 'in', ids)], context=context) or \
                acc_inv_tax_obj.search_exists(cr, uid, [('account_tax_id', 'in', ids)], context=context) or \
                purch_obj.search_exists(cr, uid, [('taxes_id', 'in', ids)], context=context) or \
                sale_obj.search_exists(cr, uid, [('tax_id', 'in', ids)], context=context):
            raise osv.except_osv(_('Warning'), _("You are trying to delete a tax record that is still referenced!"))
        else:
            return super(account_tax, self).unlink(cr, uid, ids, context=context)


account_tax()


# ---------------------------------------------------------
# Account Entries Models
# ---------------------------------------------------------

class account_model(osv.osv):
    _name = "account.model"
    _description = "Account Model"
    _columns = {
        'name': fields.char('Model Name', size=64, required=True, help="This is a model for recurring accounting entries"),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True),
        'company_id': fields.related('journal_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True),
        'lines_id': fields.one2many('account.model.line', 'model_id', 'Model Entries'),
        'legend': fields.text('Legend', readonly=True, size=100),
    }

    _defaults = {
        'legend': lambda self, cr, uid, context:_('You can specify year, month and date in the name of the model using the following labels:\n\n%(year)s: To Specify Year \n%(month)s: To Specify Month \n%(date)s: Current Date\n\ne.g. My model on %(date)s'),
    }

account_model()

class account_model_line(osv.osv):
    _name = "account.model.line"
    _description = "Account Model Entries"
    _columns = {
        'name': fields.char('Description', size=64, required=True),
        'sequence': fields.integer('Sequence', required=True, help="The sequence field is used to order the resources from lower sequences to higher ones"),
        'quantity': fields.float('Quantity', digits_compute=dp.get_precision('Account'), help="The optional quantity on entries"),
        'debit': fields.float('Debit', digits_compute=dp.get_precision('Account')),
        'credit': fields.float('Credit', digits_compute=dp.get_precision('Account')),
        'account_id': fields.many2one('account.account', 'Account', required=True, ondelete="cascade"),
        'analytic_account_id': fields.many2one('account.analytic.account', 'Analytic Account', ondelete="cascade"),
        'model_id': fields.many2one('account.model', 'Model', required=True, ondelete="cascade", select=True),
        'amount_currency': fields.float('Amount Currency', help="The amount expressed in an optional other currency."),
        'currency_id': fields.many2one('res.currency', 'Currency'),
        'partner_id': fields.many2one('res.partner', 'Partner'),
        'date_maturity': fields.selection([('today','Date of the day'), ('partner','Partner Payment Term')], 'Maturity date', help="The maturity date of the generated entries for this model. You can choose between the creation date or the creation date of the entries plus the partner payment terms."),
    }
    _order = 'sequence'
    _sql_constraints = [
        ('credit_debit1', 'CHECK (credit*debit=0)',  'Wrong credit or debit value in model (Credit Or Debit Must Be "0")!'),
        ('credit_debit2', 'CHECK (credit+debit>=0)', 'Wrong credit or debit value in model (Credit + Debit Must Be greater "0")!'),
    ]
account_model_line()

# ---------------------------------------------------------
# Account Subscription
# ---------------------------------------------------------


class account_subscription(osv.osv):
    _name = "account.subscription"
    _description = "Account Subscription"

    def _get_has_unposted_entries(self, cr, uid, ids, name, arg, context=None):
        """
        Returns a dict with key = id of the subscription,
        and value = True if an unposted JE is linked to one of the subscription lines, False otherwise
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        for sub in self.browse(cr, uid, ids, fields_to_fetch=['lines_id'], context=context):
            res[sub.id] = False
            for subline in sub.lines_id:
                if subline.move_id and subline.move_id.state == 'draft':  # draft = Unposted state
                    res[sub.id] = True
                    break
        return res

    def _is_frozen_model(self, cr, uid, ids, name, arg, context=None):
        """
        Returns True for the Recurring Plans for which the model field should be frozen, i.e. readonly:
        - if journal entries have been generated, posted or not
        - if the model already selected is in Done state (note that Done models aren't selectable, so the model would
          have been selected BEFORE it becomes Done).
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        for plan in self.browse(cr, uid, ids, fields_to_fetch=['model_id', 'lines_id'], context=context):
            res[plan.id] = False
            if plan.model_id.state == 'done':
                res[plan.id] = True
            else:
                for line in plan.lines_id:
                    if line.move_id:
                        res[plan.id] = True
                        break
        return res

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'ref': fields.char('Reference', size=64),
        'model_id': fields.many2one('account.model', 'Model', required=True),

        'date_start': fields.date('Start Date', required=True),
        'period_total': fields.integer('Number of Periods', required=True),
        'period_nbr': fields.integer('Repeat', required=True,
                                     help="This field will determine how often entries will be generated: if the period type is 'month' and the repeat '2' then entries will be generated every 2 months"),
        'period_type': fields.selection([('day','days'),('month','month'),('year','year')], 'Period Type', required=True),
        'state': fields.selection([('draft','Draft'),('running','Running'),('done','Done')], 'State', required=True, readonly=True),

        'lines_id': fields.one2many('account.subscription.line', 'subscription_id', 'Subscription Lines'),
        'has_unposted_entries': fields.function(_get_has_unposted_entries, method=True, type='boolean',
                                                store=False, string='Has unposted entries'),
        'frozen_model': fields.function(_is_frozen_model, method=True, type='boolean', store=False, string='Frozen model'),
    }
    _defaults = {
        'date_start': lambda *a: time.strftime('%Y-%m-%d'),
        'period_type': 'month',
        'period_total': 0,
        'period_nbr': 1,
        'state': 'draft',
    }

    _order = 'date_start desc, id desc'

    def _check_repeat_value(self, cr, uid, ids, context=None):
        """
        Prevents negative frequency
        """
        for plan in self.read(cr, uid, ids, ['period_nbr']):
            if plan['period_nbr'] < 1:
                return False
        return True

    def _check_plan_name_unicity(self, cr, uid, ids, context=None):
        """
        Prevents having 2 rec. plans using the same name
        """
        for plan in self.read(cr, uid, ids, ['name']):
            if self.search_exist(cr, uid, [('name', '=', plan['name']), ('id', '!=', plan['id'])]):
                raise osv.except_osv(_('Error'),
                                     _('It is not possible to have several Recurring Plans with the same name: %s.') % plan['name'])
        return True

    _constraints = [
        (_check_repeat_value, 'The value in the field "Repeat" must be greater than 0!', ['period_nbr']),
        (_check_plan_name_unicity, 'It is not possible to have several Recurring Plans with the same name.', ['name']),
    ]

    def copy(self, cr, uid, acc_sub_id, default=None, context=None):
        """
        Account Subscription duplication:
        - block the process if the model uses an inactive journal
        - block the process if the model has been set to Done as it shouldn't be used in any plans created afterwards
        - don't copy the link with subscription lines
        - add " (copy)" after the name
        """
        if context is None:
            context = {}
        sub_copied = self.browse(cr, uid, acc_sub_id, fields_to_fetch=['name', 'model_id'], context=context)
        if not sub_copied.model_id.journal_id.is_active:
            raise osv.except_osv(_('Warning'), _("You cannot duplicate a Recurring Plan with a model on an inactive journal (%s).") %
                                 sub_copied.model_id.journal_id.code)
        if sub_copied.model_id.state == 'done':
            raise osv.except_osv(_('Warning'), _('You cannot duplicate a Recurring Plan with a Done model.'))
        suffix = ' (copy)'
        name = '%s%s' % (sub_copied.name[:64 - len(suffix)], suffix)
        if default is None:
            default = {}
        default.update({
            'lines_id': [],
            'name': name,
        })
        return super(account_subscription, self).copy(cr, uid, acc_sub_id, default, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Edition of the Recurring Plans. If the model has been changed, triggers the recomputation of the state of the previous model used.

        UC: use the model X in one plan. Compute Rec. entries => the plans and models are Running.
        Select another model in the plan => model X must be set back to Draft.
        """
        if not ids:
            return True
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}
        rec_model_obj = self.pool.get('account.model')
        models_to_check = set()
        for rec_plan in self.browse(cr, uid, ids, fields_to_fetch=['model_id'], context=context):
            previous_model_id = rec_plan.model_id.id
            if 'model_id' in vals and vals['model_id'] != previous_model_id:
                models_to_check.add(previous_model_id)
        res = super(account_subscription, self).write(cr, uid, ids, vals, context=context)
        if models_to_check:
            # check model states after the plan states have been updated
            rec_model_obj._store_set_values(cr, uid, list(models_to_check), ['state'], context)
        return res

    def unlink(self, cr, uid, ids, context=None):
        """
        Prevents deletion in case the subscription lines have already been computed
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        sub_lines_obj = self.pool.get('account.subscription.line')
        if sub_lines_obj.search_exist(cr, uid, [('subscription_id', 'in', ids)], context=context):
            raise osv.except_osv(_('Warning'), _('You cannot delete a Recurring Plan if Subscription lines have already been computed.'))
        return super(account_subscription, self).unlink(cr, uid, ids, context=context)

    def update_plan_state(self, cr, uid, subscription_id, context=None):
        """
        Updates the Recurring Plan state with the following rules:
        - no lines computed = Draft
        - lines computed but not all lines posted = Running
        - all lines posted = Done
        """
        if context is None:
            context = {}
        sub = self.browse(cr, uid, subscription_id, fields_to_fetch=['lines_id'], context=context)
        if not sub.lines_id:
            state = 'draft'
        else:
            running = False
            for sub_line in sub.lines_id:
                if not sub_line.move_id or sub_line.move_id.state != 'posted':
                    running = True
                    break
            if running:
                state = 'running'
            else:
                state = 'done'
        self.write(cr, uid, subscription_id, {'state': state}, context=context)

    def remove_line(self, cr, uid, ids, context=None):
        toremove = []
        for sub in self.browse(cr, uid, ids, context=context):
            for line in sub.lines_id:
                if not line.move_id:
                    toremove.append(line.id)
        if toremove:
            self.pool.get('account.subscription.line').unlink(cr, uid, toremove)
        return False

    def delete_unposted(self, cr, uid, ids, context=None):
        """
        This method:
        - searches for the unposted Journal Entries linked to the account subscription(s)
        - deletes the unposted JEs, and the related JIs and AJIs
        """
        if context is None:
            context = {}
        je_obj = self.pool.get('account.move')
        je_to_delete_ids = []
        for sub in self.browse(cr, uid, ids, fields_to_fetch=['lines_id'], context=context):
            for subline in sub.lines_id:
                if subline.move_id and subline.move_id.state == 'draft':  # draft = Unposted state
                    je_to_delete_ids.append(subline.move_id.id)
        if je_to_delete_ids:
            je_obj.unlink(cr, uid, je_to_delete_ids, context=context)  # also deletes JIs / AJIs
        return True

    def get_dates_to_create(self, cr, uid, subscription_id, context=None):
        """
        Return the list of dates for which new Subscription Lines have to be created (i.e. don't exist yet) for the Subscription in param
        """
        if context is None:
            context = {}
        sub = self.browse(cr, uid, subscription_id, context=context)
        ds = sub.date_start
        date_list = []
        # get all the dates for which a subscription line has to be created
        for i in range(sub.period_total):
            date_list.append(ds)
            if sub.period_type == 'day':
                ds = (datetime.strptime(ds, '%Y-%m-%d') + relativedelta(days=sub.period_nbr)).strftime('%Y-%m-%d')
            if sub.period_type == 'month':
                ds = (datetime.strptime(ds, '%Y-%m-%d') + relativedelta(months=sub.period_nbr)).strftime('%Y-%m-%d')
            if sub.period_type == 'year':
                ds = (datetime.strptime(ds, '%Y-%m-%d') + relativedelta(years=sub.period_nbr)).strftime('%Y-%m-%d')
        # remove the dates from already existing subscription lines
        existing_sub_lines = sub.lines_id or []
        existing_dates = [l.date for l in existing_sub_lines]
        dates_to_create = [d for d in date_list if d not in existing_dates]
        return dates_to_create

    def compute(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        for sub in self.browse(cr, uid, ids, context=context):
            if sub.state == 'running':
                # first remove existing lines without JE
                self.remove_line(cr, uid, ids, context=context)
            if sub.model_id and sub.model_id.has_any_bad_ad_line_exp_in:
                # UFTP-103: block compute if recurring model has line with
                # expense/income accounts with invalid AD
                raise osv.except_osv(
                    _('Warning !'),
                    _("Compute cancelled. Please review analytic allocation for lines with expense or income accounts.")
                )
            # create the subscription lines if they don't exist yet
            dates_to_create = self.get_dates_to_create(cr, uid, sub.id, context=context)
            for date_sub in dates_to_create:
                self.pool.get('account.subscription.line').create(cr, uid, {
                    'date': date_sub,
                    'subscription_id': sub.id,
                })
            self.update_plan_state(cr, uid, sub.id, context=context)
        return True
account_subscription()

class account_subscription_line(osv.osv):
    _name = "account.subscription.line"
    _description = "Account Subscription Line"
    _columns = {
        'subscription_id': fields.many2one('account.subscription', 'Subscription', required=True, select=True),
        'date': fields.date('Date', required=True),
        'move_id': fields.many2one('account.move', 'Entry'),
    }
    _order = 'date, id'

    def move_create(self, cr, uid, ids, context=None):
        all_moves = []
        obj_model = self.pool.get('account.model')
        for line in self.browse(cr, uid, ids, context=context):
            datas = {
                'date': line.date,
                'ref': line.subscription_id.ref or '',
            }
            move_ids = obj_model.generate(cr, uid, [line.subscription_id.model_id.id], datas, context)
            self.write(cr, uid, [line.id], {'move_id':move_ids[0]})
            all_moves.extend(move_ids)
        return all_moves

    _rec_name = 'date'
account_subscription_line()

#  ---------------------------------------------------------------
#   Account Templates: Account, Tax, Tax Code and chart. + Wizard
#  ---------------------------------------------------------------


class account_bank_accounts_wizard(osv.osv_memory):
    _name = 'account.bank.accounts.wizard'

    _columns = {
        'acc_name': fields.char('Account Name.', size=64, required=True),
        'currency_id': fields.many2one('res.currency', 'Currency'),
        'account_type': fields.selection([('cash','Cash'),('check','Check'),('bank','Bank')], 'Type', size=32),
    }
    _defaults = {
        'currency_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
    }

account_bank_accounts_wizard()

class journal_change_account(osv.osv_memory):
    _name = 'journal.change.account'

    def _get_journal(self, cr, uid, context=None):
        if context is None:
            context = {}
        return context.get('active_id', False)

    def _get_journal_type(self, cr, uid, context=None):
        if context is None:
            context = {}
        if context.get('active_id', False):
            return self.pool.get('account.journal').read(cr, uid, context['active_id'], ['type'], context=context)['type']
        return False

    def _get_instance(self, cr, uid, context=None):
        if context is None:
            context = {}
        ids = context.get('active_ids', False)
        if ids and len(ids) == 1:
            return self.pool.get('account.journal').read(cr, uid, ids[0], ['is_current_instance'], context=context)['is_current_instance']
        return False

    def _get_credit_account(self, cr, uid, context=None):
        if context is None:
            context = {}
        ids = context.get('active_ids', False)
        if ids and len(ids) == 1:
            return self.pool.get('account.journal').read(cr, uid, ids[0], ['default_credit_account_id'], context=context)['default_credit_account_id']
        return []

    def _get_debit_account(self, cr, uid, context=None):
        if context is None:
            context = {}
        ids = context.get('active_ids', False)
        if ids and len(ids) == 1:
            return self.pool.get('account.journal').read(cr, uid, ids[0], ['default_debit_account_id'], context=context)['default_debit_account_id']
        return []


    _columns = {
        'journal_id': fields.many2one('account.journal', string="Current journal"),
        'journal_type': fields.char("Current Journal Type", size=32),
        'debit_account_id': fields.many2one('account.account', 'Debit account'),
        'credit_account_id': fields.many2one('account.account', 'Credit account'),
        'is_current_instance': fields.boolean('Is current instance?'),

    }
    _defaults = {
        'journal_id': _get_journal,
        'journal_type': _get_journal_type,
        'debit_account_id': _get_debit_account,
        'credit_account_id': _get_credit_account,
        'is_current_instance': _get_instance,
    }

    def journal_change_account(self, cr, uid, ids, context=None):
        '''
        US-11269: Modify the default debit or credit account of the journal
        '''
        if context is None:
            context = {}
        journ_obj = self.pool.get('account.journal')
        active_ids = context.get('active_ids', False)
        if active_ids:
            debit_id = self.read(cr, uid, ids, ['debit_account_id'])[0]['debit_account_id']
            credit_id = self.read(cr, uid, ids, ['credit_account_id'])[0]['credit_account_id']
            if debit_id:
                journ_obj.write(cr, uid, active_ids, {'default_debit_account_id': debit_id}, context=context)
            if credit_id:
                journ_obj.write(cr, uid, active_ids, {'default_credit_account_id': credit_id}, context=context)
        return {'type': 'ir.actions.act_window_close'}


journal_change_account()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
