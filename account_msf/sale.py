#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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
from tools.translate import _

class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'

    def wkf_validated(self, cr, uid, ids, context=None):
        """
        Change all analytic lines by a CC-intermission.
        If none, give default analytic line.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Analytic distribution verification
        ana_obj = self.pool.get('analytic.distribution')
        for so in self.browse(cr, uid, ids, context=context):
            if not so.from_yml_test and so.partner_id.partner_type == 'intermission':
                for line in so.order_line:
                    # check distribution presence
                    distrib_id = (line.analytic_distribution_id and line.analytic_distribution_id.id) or (so.analytic_distribution_id and so.analytic_distribution_id.id) or False
                    # Search intermission
                    intermission_cc = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 
                        'analytic_account_project_intermission')
                    if not distrib_id:
                        # Search product account_id
                        a = False
                        if line.product_id:
                            a = line.product_id.product_tmpl_id.property_account_income.id
                            if not a:
                                a = line.product_id.categ_id.property_account_income_categ.id
                            if not a:
                                raise osv.except_osv(_('Error !'),
                                        _('There is no income account defined ' \
                                                'for this product: "%s" (id:%d)') % \
                                                (line.product_id.name, line.product_id.id,))
                        else:
                            prop = self.pool.get('ir.property').get(cr, uid,
                                    'property_account_income_categ', 'product.category',
                                    context=context)
                            a = prop and prop.id or False
                        # Search default destination_id
                        destination_id = self.pool.get('account.account').read(cr, uid, a, ['default_destination_id']).get('default_destination_id', False)
                        ana_id = ana_obj.create(cr, uid, {'sale_order_ids': [(4,so.id)], 
                            'cost_center_lines': [(0, 0, {'destination_id': destination_id, 'analytic_id': intermission_cc[1] , 'percentage':'100', 'currency_id': so.currency_id.id})]})
                    else:
                        # Change CC lines
                        for cc_line in ana_obj.browse(cr, uid, distrib_id).cost_center_lines:
                            self.pool.get('cost.center.distribution.line').write(cr, uid, cc_line.id, {'analytic_id': intermission_cc[1]})
        # Default behaviour
        res = super(sale_order, self).wkf_validated(cr, uid, ids, context=context)
        return res

sale_order()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
