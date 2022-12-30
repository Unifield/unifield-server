# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 TeMPO Consulting, MSF
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

from osv import fields
from osv import osv

from tools.translate import _


class res_partner(osv.osv):
    """
    Override the res_partner class to add some feature
    from Order Sourcing Tool
    """
    _name = 'res.partner'
    _inherit = 'res.partner'

    def _get_available_for_dpo(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return for each partner if he's available for DPO selection
        '''
        res = {}
        company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.partner_id.id

        for partner in self.browse(cr, uid, ids, context=context):
            res[partner.id] = False
            if partner.supplier and partner.id != company_id and partner.partner_type in ('external', 'esc'):
                res[partner.id] = True

        return res

    def _src_available_for_dpo(self, cr, uid, obj, name, args, context=None):
        '''
        Returns all partners according to args
        '''
        res = []
        for arg in args:
            if len(arg) > 2 and arg[0] == 'available_for_dpo':
                if arg[1] != '=':
                    raise osv.except_osv(_('Error'), _('Bad operator'))
                elif arg[2] == 'dpo':
                    company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.partner_id.id
                    res.append(('id', '!=', company_id))
                    res.append(('partner_type', 'in', ('external', 'esc')))
                    res.append(('supplier', '=', True))

        return res

    def _get_fake(self, cr, uid, ids, fields, arg, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        result = {}
        for l_id in ids:
            result[l_id] = True
        return result

    def _get_source_domain(self, cr, uid, sol_ids, context=None):
        if isinstance(sol_ids, (int, long)):
            sol_ids = [sol_ids]

        remove_ids = set()
        allowed_types_set = set(['external', 'esc', 'internal', 'section', 'intermission'])

        for sol in self.pool.get('sale.order.line').browse(cr, uid, sol_ids, fields_to_fetch=['order_id', 'original_instance']):
            remove_ids.add(sol.order_id.partner_id.id)
            if not sol.order_id.procurement_request:
                types_allowed = ['external', 'esc']
                if sol.order_id.partner_type in ['esc', 'external']:
                    types_allowed.extend(['internal', 'section', 'intermission'])
                elif not sol.original_instance or sol.original_instance == sol.order_id.partner_id.name:
                    types_allowed.extend(['internal', 'section', 'intermission'])
                allowed_types_set.intersection_update(set(types_allowed))
        return [('id', 'not in', list(remove_ids)), ('partner_type', 'in', list(allowed_types_set))]

    def _check_partner_type(self, cr, uid, obj, name, args, context=None):
        if context is None:
            context = {}
        active_id = context.get('active_id', False)
        if isinstance(active_id, (int, long)):
            active_id = [active_id]
        if not args:
            return []
        newargs = []
        for arg in args:
            if arg[0] == 'check_partner':
                if arg[1] != '=' or not isinstance(arg[2], (int, long)):
                    raise osv.except_osv(_('Error'), _('Filter check_partner different than (arg[0], =, id) not implemented.'))
                if arg[2]:
                    newargs += self._get_source_domain(cr, uid, arg[2], context=context)
            else:
                newargs.append(args)
        return newargs

    def _check_partner_type_rfq(self, cr, uid, obj, name, args, context=None):
        if not args:
            return []
        newargs = []
        for arg in args:
            if arg[0] == 'check_partner_rfq':
                if arg[1] != '=' or not isinstance(arg[2], (int, long)):
                    raise osv.except_osv(_('Error'), _('Filter check_partner_rfq different than (arg[0], =, id) not implemented.'))
                if arg[2]:
                    tender = self.pool.get('tender').browse(cr, uid, arg[2])
                    if tender.sale_order_id:
                        newargs.append(('partner_type', 'in', ['external', 'esc']))
            else:
                newargs.append(args)
        return newargs

    def _check_partner_type_ir(self, cr, uid, obj, name, args, context=None):
        if context is None:
            context = {}
        active_ids = context.get('active_ids', False)
        if isinstance(active_ids, (int, long)):
            active_ids = [active_ids]
        if not args:
            return []
        newargs = []
        for arg in args:
            if arg[0] == 'check_partner_ir':
                if arg[1] != '=':
                    raise osv.except_osv(_('Error'), _('Filter check_partner_ir different than (arg[0], =, id) not implemented.'))
                if arg[2]:
                    if active_ids:
                        sol = self.pool.get('sale.order.line').browse(cr, uid, active_ids)[0]
                        if not context.get('product_id', False) and sol.order_id.procurement_request:
                            newargs.append(('partner_type', 'in', ['internal', 'section', 'intermission', 'esc']))
            else:
                newargs.append(args)
        return newargs

    def _check_partner_type_po(self, cr, uid, obj, name, args, context=None):
        """
        Create a domain on the field partner_id on the view id="purchase_move_buttons"
        """
        if context is None:
            context = {}
        if not args:
            return []
        newargs = []

        for arg in args:
            if arg[0] == 'check_partner_po':
                if arg[1] != '=' \
                   or arg[2]['order_type'] not in ['regular', 'donation_exp', 'donation_st', 'loan', 'in_kind', 'purchase_list', 'direct']\
                   or not isinstance(arg[2]['partner_id'], (int, long)):
                    raise osv.except_osv(_('Error'), _('Filter check_partner_po different than (arg[0], =, %s) not implemented.') % arg[2])
                order_type = arg[2]['order_type']
                split_po = arg[2]['split_po']
                if split_po:
                    newargs.append(('split_po', '=', 'yes'))
                # Added by UF-1660 to filter partners
                # do nothing on partner_type for loan
                p_list = []
                if order_type == 'loan':
                    p_list = ['internal', 'intermission', 'section', 'external']
                elif order_type in ['direct', 'in_kind']:
                    p_list = ['esc', 'external']
                elif order_type in ['donation_st', 'donation_exp']:
                    p_list = ['internal', 'intermission', 'section']
                elif order_type in ['purchase_list']:
                    p_list = ['external']
                # show all supplier for non taken cases
                else:
                    pass
                if p_list:
                    newargs.append(('partner_type', 'in', p_list))
            else:
                newargs.append(args)
        return newargs

    def _src_contains_fo(self, cr, uid, obj, name, args, context=None):
        res = []
        for arg in args:
            if arg[0] == 'line_contains_fo':
                if type(arg[2]) == type(list()):
                    res += self._get_source_domain(cr, uid, arg[2][0][2], context=context)
        return res

    _columns = {
        'available_for_dpo': fields.function(_get_available_for_dpo, fnct_search=_src_available_for_dpo,
                                             method=True, type='boolean', string='Available for DPO', store=False),
        'check_partner': fields.function(_get_fake, method=True, type='boolean', string='Check Partner Type', fnct_search=_check_partner_type),
        'check_partner_rfq': fields.function(_get_fake, method=True, type='boolean', string='Check Partner Type', fnct_search=_check_partner_type_rfq),
        'check_partner_ir': fields.function(_get_fake, method=True, type='boolean', string='Check Partner Type On IR', fnct_search=_check_partner_type_ir),
        'check_partner_po': fields.function(_get_fake, method=True, type='boolean', string='Check Partner Type On PO', fnct_search=_check_partner_type_po),
        'line_contains_fo': fields.function(_get_fake, fnct_search=_src_contains_fo, method=True, string='Lines contains FO', type='boolean', store=False),
    }

res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
