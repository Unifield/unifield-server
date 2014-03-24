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
from account_override import ACCOUNT_RESTRICTED_AREA

class res_partner(osv.osv):
    _name = "res.partner"
    _inherit = "res.partner"

    def _search_property_account(self, cr, uid, obj, name, args, context=None):
        """
        Search account that are used
        NB:
        # Search the default account in ir_property (which have "property_account_payable in fields_id and res_id is null
        #        select res_id, value_reference from ir_property where fields_id in (1218,1221) and res_id is null
        # Search elements that have a particular account_id
        # 1218 = select id from ir_model_fields where model = 'res.partner' and name = 'property_account_payable';
        # 1221 = select id from ir_model_fields where model = 'res.partner' and name = 'property_account_receivable';
        # select res_id, value_reference from ir_property where fields_id in (1218,1221) and res_id like 'res.partner%' group by res_id, value_reference;
        """
        # Test how many arguments we have
        if not len(args):
            return []

        # We just support '=' operator
        if args[0][1] not in ['=',]:
            raise osv.except_osv(_('Warning'), _('This filter is not implemented yet!'))

        # Prepare some values
        res = []
        field = args[0][0]
        field_ids = self.pool.get('ir.model.fields').search(cr, uid, [('model', '=', 'res.partner'),
            ('name', '=', field)], context=context)
        # Prepare sql queries
        if len(field_ids) > 1:
            field_ids_str = '('
            for i in field_ids:
                string = "%s," % str(i)
                field_ids_str += string
            field_ids_str += ')'
            # sql query for particulars partner
            sql = "SELECT res_id, value_reference FROM ir_property WHERE fields_id in %s AND res_id LIKE 'res.partner%%' \
                GROUP BY res_id, \value_reference" % field_ids_str
            # sql query for default property_account_* field
            sql2 = "SELECT res_id, value_reference FROM ir_property WHERE fields_id in %s AND res_id is NULL \
                GROUP BY res_id, value_reference" % field_ids_str
        else:
            # sql query for particulars partner
            sql = "SELECT res_id, value_reference FROM ir_property WHERE fields_id = %s AND res_id LIKE 'res.partner%%' \
                GROUP BY res_id, value_reference" % str(field_ids[0])
            # sql query for default property_account_* field
            sql2 = "SELECT res_id, value_reference FROM ir_property WHERE fields_id = %s AND res_id is NULL \
                GROUP BY res_id, value_reference" % str(field_ids[0])
        cr.execute(sql)
        res_elements = cr.fetchall()
        # Prepare all partners that have a particular account
        partner_with_particular_account = []
        # then all partners without any filter
        all_partner_ids = self.pool.get('res.partner').search(cr, uid, [], context=context, order='id')
        for el in res_elements:
            # el is a tuple
            partner = el[0].split(",")
            account = el[1].split(",")
            # Add this ID in the list that give all partner with a particular account (necessary for those we have a default account)
            partner_with_particular_account.append(int(partner[1]))
            if str(account[0]) == 'account.account' and str(account[1]) == str(args[0][2]):
                res.append(partner[1])
        # Search default account for all partner
        cr.execute(sql2)
        res_def_elements = cr.fetchall()
        def_elements = []
        # Make a list of default account
        for el in res_def_elements:
            data = el[0]
            data_account = el[1].split(",")
            if not data and data_account[0] == 'account.account':
                def_elements.append(data_account[1])
        # Add others partner if they are not in partner_with_particular_account (already treated)
        if str(args[0][2]) in def_elements:
            for partner_id in all_partner_ids:
                if partner_id not in (partner_with_particular_account):
                    res.append(partner_id)
        return [('id', 'in', res)]

    _columns = {
        'property_account_payable': fields.property(
            'account.account',
            type='many2one',
            relation='account.account',
            string="Account Payable",
            method=True,
            view_load=True,
            domain=ACCOUNT_RESTRICTED_AREA['partner_payable'],
            help="This account will be used instead of the default one as the payable account for the current partner",
            required=True,
            fnct_search=_search_property_account),
        'property_account_receivable': fields.property(
            'account.account',
            type='many2one',
            relation='account.account',
            string="Account Receivable",
            method=True,
            view_load=True,
            domain=ACCOUNT_RESTRICTED_AREA['partner_receivable'],
            help="This account will be used instead of the default one as the receivable account for the current partner",
            required=True,
            fnct_search=_search_property_account),
    }

res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
