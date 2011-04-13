#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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
from operator import itemgetter
from register_tools import _get_third_parties
from register_tools import _set_third_parties

class account_move_line(osv.osv):
    _name = "account.move.line"
    _inherit = "account.move.line"

    _columns = {
        'register_id': fields.many2one("account.account", "Register"),
        'employee_id': fields.many2one("hr.employee", "Employee"),
        'partner_type': fields.function(_get_third_parties, fnct_inv=_set_third_parties, type='reference', method=True, 
            string="Third Parties", selection=[('res.partner', 'Partner'), ('hr.employee', 'Employee'), ('account.bank.statement', 'Register')]),
        'partner_type_mandatory': fields.boolean('Third Party Mandatory'),
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Correct fields in order to have partner_type instead of partner_id
        """
        # @@@override@ account.account_move_line.fields_view_get()
        journal_pool = self.pool.get('account.journal')
        if context is None:
            context = {}
        result = super(osv.osv, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type != 'tree':
            #Remove the toolbar from the form view
            if view_type == 'form':
                if result.get('toolbar', False):
                    result['toolbar']['action'] = []
            #Restrict the list of journal view in search view
            if view_type == 'search' and result['fields'].get('journal_id', False):
                result['fields']['journal_id']['selection'] = journal_pool.name_search(cr, uid, '', [], context=context)
                ctx = context.copy()
                #we add the refunds journal in the selection field of journal
                if context.get('journal_type', False) == 'sale':
                    ctx.update({'journal_type': 'sale_refund'})
                    result['fields']['journal_id']['selection'] += journal_pool.name_search(cr, uid, '', [], context=ctx)
                elif context.get('journal_type', False) == 'purchase':
                    ctx.update({'journal_type': 'purchase_refund'})
                    result['fields']['journal_id']['selection'] += journal_pool.name_search(cr, uid, '', [], context=ctx)
            return result
        if context.get('view_mode', False):
            return result
        fld = []
        fields = {}
        flds = []
        title = _("Accounting Entries") #self.view_header_get(cr, uid, view_id, view_type, context)
        xml = '''<?xml version="1.0"?>\n<tree string="%s" editable="top" refresh="5" on_write="on_create_write" colors="red:state==\'draft\';black:state==\'valid\'">\n\t''' % (title)

        ids = journal_pool.search(cr, uid, [])
        journals = journal_pool.browse(cr, uid, ids, context=context)
        all_journal = [None]
        common_fields = {}
        total = len(journals)
        for journal in journals:
            all_journal.append(journal.id)
            for field in journal.view_id.columns_id:
                if not field.field in fields:
                    fields[field.field] = [journal.id]
                    fld.append((field.field, field.sequence, field.name))
                    flds.append(field.field)
                    common_fields[field.field] = 1
                else:
                    fields.get(field.field).append(journal.id)
                    common_fields[field.field] = common_fields[field.field] + 1
        fld.append(('period_id', 3, _('Period')))
        fld.append(('journal_id', 10, _('Journal')))
        flds.append('period_id')
        flds.append('journal_id')
        # Add 2 fields : partner_type and partner_type_mandatory
        fld.append(('partner_type', 4, _('Third Parties')))
        fld.append(('partner_type_mandatory', 5, _('Third Parties Mandatory')))
        flds.append('partner_type')
        flds.append('partner_type_mandatory')
        fields['partner_type'] = all_journal
        fields['partner_type_mandatory'] = all_journal
        # end of add
        fields['period_id'] = all_journal
        fields['journal_id'] = all_journal
        fld = sorted(fld, key=itemgetter(1))
        widths = {
            'statement_id': 50,
            'state': 60,
            'tax_code_id': 50,
            'move_id': 40,
        }
        for field_it in fld:
            field = field_it[0]
            if common_fields.get(field) == total:
                fields.get(field).append(None)
#            if field=='state':
#                state = 'colors="red:state==\'draft\'"'
            attrs = []
            if field == 'debit':
                attrs.append('sum = "%s"' % _("Total debit"))

            elif field == 'credit':
                attrs.append('sum = "%s"' % _("Total credit"))

            elif field == 'move_id':
                attrs.append('required = "False"')

            elif field == 'account_tax_id':
                attrs.append('domain="[(\'parent_id\', \'=\' ,False)]"')
                attrs.append("context=\"{'journal_id': journal_id}\"")

            elif field == 'account_id' and journal.id:
                # Change the domain in order to have third parties fields instead of partner_id field
#                attrs.append('domain="[(\'journal_id\', \'=\', '+str(journal.id)+'),(\'type\',\'&lt;&gt;\',\'view\'), (\'type\',\'&lt;&gt;\',\'closed\')]" on_change="onchange_account_id(account_id, partner_id)"')
                attrs.append('domain="[(\'journal_id\', \'=\', '+str(journal.id)+'),(\'type\',\'&lt;&gt;\',\'view\'), (\'type\',\'&lt;&gt;\',\'closed\')]" on_change="onchange_account_id(account_id, partner_type)"')
                # end of add

            elif field == 'partner_id':
                attrs.append('on_change="onchange_partner_id(move_id, partner_id, account_id, debit, credit, date, journal_id)"')

            elif field == 'journal_id':
                attrs.append("context=\"{'journal_id': journal_id}\"")

            elif field == 'statement_id':
                attrs.append("domain=\"[('state', '!=', 'confirm'),('journal_id.type', '=', 'bank')]\"")

            elif field == 'date':
                attrs.append('on_change="onchange_date(date)"')

            elif field == 'analytic_account_id':
                attrs.append('''groups="analytic.group_analytic_accounting"''') # Currently it is not working due to framework problem may be ..

            if field in ('amount_currency', 'currency_id'):
                attrs.append('on_change="onchange_currency(account_id, amount_currency, currency_id, date, journal_id)"')
                attrs.append('''attrs="{'readonly': [('state', '=', 'valid')]}"''')

            if field in widths:
                attrs.append('width="'+str(widths[field])+'"')

            if field in ('journal_id',):
                attrs.append("invisible=\"context.get('journal_id', False)\"")
            elif field in ('period_id',):
                attrs.append("invisible=\"context.get('period_id', False)\"")
            # Do partner_id field and partner_type_mandatory field to be invisible and partner_type to be visible
            elif field in ('partner_id',):
                attrs.append("invisible=\"1\"")
            elif field in ('partner_type',):
                attrs.append("on_change=\"onchange_partner_type(partner_type, credit, debit)\" invisible=\"0\" \
                    attrs=\"{'required': [('partner_type_mandatory', '=', True)]}\"")
            elif field in ('partner_type_mandatory',):
                attrs.append("invisible=\"1\"")
            # end of add
            else:
                attrs.append("invisible=\"context.get('visible_id') not in %s\"" % (fields.get(field)))
            xml += '''<field name="%s" %s/>\n''' % (field,' '.join(attrs))

        xml += '''</tree>'''
        result['arch'] = xml
        result['fields'] = self.fields_get(cr, uid, flds, context)
        return result
        # @@@end

    def onchange_account_id(self, cr, uid, ids, account_id=False, third_party=False):
        """
        Update some values and do this if a partner_id is given
        """
        # @@@override account.account_move_line.onchange_account_id
        account_obj = self.pool.get('account.account')
        partner_obj = self.pool.get('res.partner')
        fiscal_pos_obj = self.pool.get('account.fiscal.position')
        val = {}
        # Add partner_id variable in order to the function to works
        partner_id = False
        if third_party:
            third_vals = third_party.split(",")
            if third_vals[0] == "res.partner":
                partner_id = third_vals[1]
        # end of add
        if account_id:
            res = account_obj.browse(cr, uid, account_id)
            tax_ids = res.tax_ids
            if tax_ids and partner_id:
                part = partner_obj.browse(cr, uid, partner_id)
                tax_id = fiscal_pos_obj.map_tax(cr, uid, part and part.property_account_position or False, tax_ids)[0]
            else:
                tax_id = tax_ids and tax_ids[0].id or False
            val['account_tax_id'] = tax_id
        # @@@end

        # Prepare some values
        acc_obj = self.pool.get('account.account')
        third_type = [('res.partner', 'Partner')]
        third_required = False
        third_selection = 'res.partner,0'
        domain = {'partner_type': []}
        # if an account is given, then attempting to change third_type and information about the third required
        if account_id:
            account = acc_obj.browse(cr, uid, [account_id])[0]
            acc_type = account.type_for_register
            # if the account is a payable account, then we change the domain
            if acc_type == 'partner':
                if account.type == "payable":
                    domain = {'partner_type': [('property_account_payable', '=', account_id)]}
                elif account.type == "receivable":
                    domain = {'partner_type': [('property_account_receivable', '=', account_id)]}

            if acc_type == 'transfer':
                third_type = [('account.bank.statement', 'Register')]
                third_required = True
                third_selection = 'account.bank.statement,0'
                domain = {'partner_type': [('state', '=', 'open')]}
            elif acc_type == 'advance':
                third_type = [('hr.employee', 'Employee')]
                third_required = True
                third_selection = 'hr.employee,0'
        val.update({'partner_type_mandatory': third_required, 'partner_type': {'options': third_type, 'selection': third_selection}})
        return {'value': val, 'domain': domain}

    def onchange_partner_type(self, cr, uid, ids, partner_type=None, credit=None, debit=None, context={}):
        """
        Give the right account_id according partner_type and third parties choosed
        """
        return self.pool.get('account.bank.statement.line').onchange_partner_type(cr, uid, ids, partner_type, credit, debit, context=context)

account_move_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
