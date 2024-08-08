# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2011 MSF, TeMPO Consulting
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


class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'

    def _get_fake(self, cr, uid, ids, fields, arg, context=None):
        """
        Fake method for 'check_partner_so' field.
        """
        if isinstance(ids, int):
            ids = [ids]
        result = {}
        for id in ids:
            result[id] = False
        return result

    def _check_partner_type_so(self, cr, uid, obj, name, args, context=None):
        """
        Create a domain on the field partner_id
        """
        if context is None:
            context = {}
        if not args:
            return []
        newargs = []
        for arg in args:
            if arg[0] == 'check_partner_so':
                if arg[1] != '=' \
                        or arg[2]['order_type'] not in ['regular', 'donation_prog', 'donation_exp', 'donation_st', 'loan', 'loan_return', 'in_kind', 'purchase_list', 'direct']\
                        or not isinstance(arg[2]['partner_id'], int):
                    raise osv.except_osv(_('Error'), _('Filter check_partner_so different than (arg[0], =, %s) not implemented.') % arg[2])
                order_type = arg[2]['order_type']
                p_list = []
                if order_type in ['regular']:
                    p_list = ['internal', 'intermission', 'external', 'esc'] # UTP-953: Cannot create an FO regular for Intersection due to the Push Flow sync
                elif order_type in ['donation_prog']:
                    p_list = ['external']
                elif order_type in ['donation_st', 'loan', 'loan_return', 'donation_exp']:
                    p_list = ['internal', 'intermission', 'section', 'external']
                elif order_type in ['direct', 'in_kind']:
                    p_list = ['internal', 'intermission', 'section', 'esc', 'external']
                # show all supplier for non taken cases
                else:
                    pass
                if p_list:
                    newargs.append(('partner_type', 'in', p_list))
            else:
                newargs.append(args)
        return newargs

    def _search_partner_not_int(self, cr, uid, obj, name, args, context=None):
        dom = []
        for arg in args:
            if not isinstance(arg[2], dict) or not arg[2].get('ids') or not arg[2].get('ids')[0]:
                return dom
            if arg[2]['type'] == 'po':
                for po in self.pool.get('purchase.order').browse(cr, uid, arg[2]['ids'], context=context):
                    if po.po_from_fo:
                        dom.append(('partner_type', 'not in', ['internal','section','intermission']))
            else:
                for tender in self.pool.get('tender').browse(cr, uid, arg[2]['ids'], context=context):
                    if tender.tender_from_fo:
                        dom.append(('partner_type', 'not in', ['internal','section','intermission']))
        return dom

    _columns = {
        'check_partner_so': fields.function(_get_fake, method=True, type='boolean', string='Check Partner Type On SO', fnct_search=_check_partner_type_so),
        'partner_not_int': fields.function(_get_fake, method=True, type='boolean', string='Is PO/Tender from FO ?', fnct_search=_search_partner_not_int),
    }


res_partner()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
