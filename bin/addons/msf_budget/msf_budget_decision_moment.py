# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields, osv


class msf_budget_decision_moment(osv.osv):
    _name = "msf.budget.decision.moment"
    _order = '"order"'

    def _check_order(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for moment in self.browse(cr, uid, ids, context=context):
            if moment.order < 1:
                return False
            else:
                bad_ids = self.search(cr, uid, [('order', '=', moment.order)])
                if len(bad_ids) and len(bad_ids) > 1:
                    return False
        return True

    def _check_name(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for moment in self.browse(cr, uid, ids, context=context):
            if moment.name == '':
                return False
            else:
                bad_ids = self.search(cr, uid, [('name', '=', moment.name)])
                if len(bad_ids) and len(bad_ids) > 1:
                    return False
        return True

    _columns = {
        'name': fields.char('Decision Moment', size=32, required=True),
        'order': fields.integer('Order', required=True),
    }

    _constraints = [
        (_check_order, 'Order must be unique and bigger than 1!', ['order']),
        (_check_name, 'Name must be unique!', ['name'])
    ]

    def fields_view_get(self, cr, uid, view_id=None, view_type='form',
                        context=None, toolbar=False, submenu=False):
        """
        Override the tree view to hide some buttons according to the instance
        to which the user belongs.
        """
        if context is None:
            context = {}
        res = super(msf_budget_decision_moment, self).fields_view_get(
            cr, uid, view_id, view_type, context, toolbar, submenu)
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if user.company_id and user.company_id.instance_id:
            instance_level = user.company_id.instance_id.current_instance_level
            # Full access for HQ instances
            if instance_level != 'section':
                if 'hide_new_button="PROP_INSTANCE_HIDE_BUTTON"' in res['arch']:
                    res['arch'] = res['arch'].replace(
                        'hide_duplicate_button="PROP_INSTANCE_HIDE_BUTTON"',
                        'hide_duplicate_button="1"')
                    res['arch'] = res['arch'].replace(
                        'hide_delete_button="PROP_INSTANCE_HIDE_BUTTON"',
                        'hide_delete_button="1"')
                    res['arch'] = res['arch'].replace(
                        'hide_new_button="PROP_INSTANCE_HIDE_BUTTON"',
                        'hide_new_button="1" noteditable="1" notselectable="0"')
            # Restricted access for other instances
            else:
                if res['type'] == 'form' \
                        and 'hide_new_button="PROP_INSTANCE_HIDE_BUTTON"' in res['arch']:
                    res['arch'] = res['arch'].replace(
                        'hide_duplicate_button="PROP_INSTANCE_HIDE_BUTTON"', '')
                    res['arch'] = res['arch'].replace(
                        'hide_delete_button="PROP_INSTANCE_HIDE_BUTTON"', '')
                    res['arch'] = res['arch'].replace(
                        'hide_new_button="PROP_INSTANCE_HIDE_BUTTON"', '')
        return res

msf_budget_decision_moment()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
