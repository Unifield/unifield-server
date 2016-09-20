# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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
from tools.translate import _

class analytic_account(osv.osv):
    _name = "account.analytic.account"
    _inherit = "account.analytic.account"

    def _get_fake(self, cr, uid, ids, name, args, context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            res[id] = False
        return res

    def _get_is_instance_registered(self, cr, uid, obj, name, args,
        context=None):
        res = []
        if not len(args):
            return res
        if len(args) != 1:
            msg = _("Domain %s not suported") % (str(args), )
            raise osv.except_osv(_('Error'), msg)
        if args[0][1] != '=':
            msg = _("Operator '%s' not suported") % (args[0][1], )
            raise osv.except_osv(_('Error'), msg)

        # get coordos already registered CCs and exclude them
        atc_obj = self.pool.get('account.target.costcenter')
        atc_ids = atc_obj.search(cr, uid, [
                ('instance_id.level', '=', 'coordo'),
            ], context=context)

        if atc_ids:
            cc_ids = list(set([
                    atc_rec.cost_center_id.id \
                        for atc_rec in atc_obj.browse(cr, uid, atc_ids,
                        context=context)
                ]))
            res =  [ ('id', 'not in', cc_ids), ]

        return res

    _columns = {
        # is CC already registered from Coordo 'Add Cost Centers' button ?
        'is_instance_registered': fields.function(
            _get_fake,
            fnct_search=_get_is_instance_registered,
            method=True, type='boolean', readonly=True,
            string="System period ?"
        ),
    }

analytic_account()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
