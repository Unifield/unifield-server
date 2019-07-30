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


##############################################################################
#
#    This class is a common place for special treatment of cases that happen only
#    when running with the synchronisation module
#
##############################################################################

from osv import osv
from tools.translate import _
from sync_common import xmlid_to_sdref


class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _inherit = 'account.analytic.line'

    def create(self, cr, uid, vals, context=None):
        if not context:
            context = {}

        # Check if the create request comes from the sync data and from some specific trigger
        # for example: the create/write of account.move, account.move.line from sync data must not
        # create this object, because this object is sync-ed on a separate rule
        # otherwise duplicate entries will be created and these entries will be messed up in the later update
        if 'do_not_create_analytic_line' in context:
            if context.get('sync_update_execution'):
                return False
            del context['do_not_create_analytic_line']

        # UF-2479: Block the creation of an AJI if the given period is not open, in sync context
        if context.get('sync_update_execution') and 'date' in vals:
            period_ids = self.pool.get('account.period').get_period_from_date(cr, uid, vals['date'])
            if not period_ids:
                raise osv.except_osv(_('Warning'), _('No period found for the given date: %s') % (vals['date'] or ''))
            period = self.pool.get('account.period').browse(cr, uid, period_ids)[0]

            # US-292: Allow the creation of an AJI if the given period is not open, in sync context
            if period and period.state == 'created' and not vals.get('from_commitment_line', False):
                raise osv.except_osv(_('Error !'), _('Period \'%s\' of the given date %s is not open! No AJI is created') % (period.name, vals['date'] or ''))

        # continue the create request if it comes from a normal requester
        return super(account_analytic_line, self).create(cr, uid, vals, context=context)

account_analytic_line()

class account_move(osv.osv):
    _name = 'account.move'
    _inherit = 'account.move'

    def create(self, cr, uid, vals, context=None):
        if not context:
            context = {}

        # indicate to the account.analytic.line not to create such an object to avoid duplication
        context['do_not_create_analytic_line'] = True
        return super(account_move, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if not ids or not vals:
            return True
        if not context:
            context = {}

        # indicate to the account.analytic.line not to create such an object to avoid duplication
        context['do_not_create_analytic_line'] = True

        return super(account_move, self).write(cr, uid, ids, vals, context=context)

account_move()


class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'

    def create(self, cr, uid, vals, context=None, check=True):
        if not context:
            context = {}

        # indicate to the account.analytic.line not to create such an object to avoid duplication
#        context['do_not_create_analytic_line'] = True

        sync_check = check
        if context.get('sync_update_execution', False):
            sync_check = False

        return super(account_move_line, self).create(cr, uid, vals, context=context, check=sync_check)

    def write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
        if not ids:
            return True
        # UTP-632: re-add write(), but only for the check variable
        if not context:
            context = {}

        sync_check = check
        if context.get('sync_update_execution', False):
            sync_check = False

        return super(account_move_line, self).write(cr, uid, ids, vals, context=context, check=sync_check, update_check=update_check)

    def _hook_call_update_check(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        field_to_check = {'account_id': 'm2o', 'journal_id': 'm2o', 'period_id': 'm2o', 'move_id': 'm2o', 'debit': 'float', 'credit': 'float', 'date': 'date'}
        done = {}
        if not context.get('sync_update_execution'):
            return super(account_move_line, self)._hook_call_update_check(cr, uid, ids, vals, context)

        # rewrite update_check, to raise error *only if values to write and values in DB differ*
        for l in self.browse(cr, uid, ids):
            for f,typ in field_to_check.iteritems():
                if f in vals:
                    to_write_val = l[f]
                    if typ == 'm2o' and l[f]:
                        to_write_val = l[f].id
                    diff_val = vals[f] != to_write_val
                    if typ == 'float' and l[f] and vals[f]:
                        diff_val = abs(vals[f] - l[f]) > 10**-4
                    if diff_val and l.move_id.state <> 'draft' and l.state <> 'draft' and (not l.journal_id.entry_posted):
                        # US-14: do not raised but remove the data
                        if f in ('debit', 'credit'):
                            del vals[f]
                        else:
                            raise osv.except_osv(_('Error !'), _('You can not do this modification on a confirmed entry ! Please note that you can just change some non important fields !'))
                    elif diff_val and l.reconcile_id:
                        # US-14
                        if f in ('debit', 'credit'):
                            del vals[f]
                        else:
                            raise osv.except_osv(_('Error !'), _('You can not do this modification on a reconciled entry ! Please note that you can just change some non important fields !'))
            t = (l.journal_id.id, l.period_id.id)
            if t not in done:
                if not self._update_journal_check(cr, uid, l.journal_id.id,
                                                  l.period_id.id, context=context, raise_hq_closed=False):
                    # US 1214: HQ closed check more field not updated
                    self._hook_call_update_check_hq_closed_rec(cr, uid, l,
                                                               vals, context=context)
                done[t] = True

    def _hook_call_update_check_hq_closed_rec(self, cr, uid, ji_rec, vals,
                                              context=None):
        # US 1214: HQ closed tolerate update under certains conditions only
        # Enable the sync on account.move.line field only if they are not : Dates / Journal / Sequence / Description / Reference / all field amounts / Third party / Currency / State
        # http://jira.unifield.org/browse/US-1214?focusedCommentId=47237&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-47237
        # US-4963: allow changes on employee_id

        # => get field by field diff
        fields_to_check = [
            ('credit', 'float'),
            ('credit_currency', 'float'),
            ('currency_id', 'id'),
            ('date', False),
            ('debit', 'float'),
            ('debit_currency', 'float'),
            ('document_date', False),
            ('journal_id', 'id'),
            ('move_id', 'id'),
            ('partner_id', 'id'),
            ('period_id', 'id'),
            ('ref', False),
            ('state', False),
            ('transfer_journal_id', 'id'),
            ('transfer_amount', 'float'),
        ]

        for f, t in fields_to_check:
            has_diff = False
            if f in vals:
                if not hasattr(ji_rec, f):
                    continue
                rec_val = getattr(ji_rec, f)
                val = vals[f]

                # US-1737 consider False and '' equal
                if not val and not rec_val:
                    continue

                if t == 'id':
                    if rec_val:
                        has_diff = not val or val != rec_val.id
                    else:
                        has_diff = True if val else False
                elif t == 'float':
                    has_diff = abs((val or 0.) - (rec_val or 0.)) > 10**-4
                else:
                    has_diff = val != rec_val

            if has_diff:
                raise osv.except_osv(_('Error !'),
                                     _('You can not modify entries in a HQ closed journal. Field: %s, db value: %s, update value: %s') % (f, rec_val, val))

account_move_line()

class ir_model_data(osv.osv):
    _inherit = 'ir.model.data'
    _name = 'ir.model.data'

    def _query_from_sync(self, cr, uid, source, obj, xmlid, fields, value, context=None):
        if context is None:
            context = {}
        if not context.get('sync_message_execution'):
            raise osv.except_osv(_('Error !'), _("Can't execute this method"))

        pool_obj = self.pool.get(obj)
        if not pool_obj:
            raise osv.except_osv(_('Error !'), _('Object %s not found') % obj)

        obj_id = pool_obj.find_sd_ref(cr, uid, xmlid_to_sdref(xmlid))
        if not obj_id:
            raise osv.except_osv(_('Error !'), _('Target object %s not found') % xmlid)

        all_fields = pool_obj.fields_get(cr, uid, context=context)
        value_to_write = []
        to_replace = []
        for i, field in enumerate(fields):
            if all_fields[field]['type'] in ('one2many', 'many2many'):
                raise osv.except_osv(_('Error !'), _('Field %s: type %s not supported') % (field, all_fields[field]['type']))
            elif all_fields[field]['type'] == 'many2one':
                to_replace.append('%s')
                if value[i] and value[i] != 'NULL':
                    rel_id = self.pool.get(all_fields[field]['relation']).find_sd_ref(cr, uid, xmlid_to_sdref(value[i]))
                    if not rel_id:
                        raise osv.except_osv(_('Error !'), _('Field %s, xmlid %s not found') % (field, value[i]))
                    value_to_write.append(rel_id)
                else:
                    value_to_write.append('NULL')
            else:
                to_replace.append('%s')
                value_to_write.append(value[i])

        value_to_write.append(obj_id)
        cr.execute('UPDATE '+pool_obj._table+' SET ('+','.join(fields)+') = ('+','.join(to_replace)+') WHERE id=%s', tuple(value_to_write))  # not_a_user_entry
        return True


ir_model_data()


class sync_ir_translation(osv.osv):
    _name = 'ir.translation'
    _inherit = 'ir.translation'

    def _get_reset_cache_at_sync(self, cr, uid, context=None):
        self._get_source.clear_cache(cr.dbname)
        self._get_ids.clear_cache(cr.dbname)
        return True

sync_ir_translation()
