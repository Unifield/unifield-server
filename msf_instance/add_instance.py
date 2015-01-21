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

from osv import fields, osv

class account_analytic_journal(osv.osv):
    _name = 'account.analytic.journal'
    _inherit = 'account.analytic.journal'

    def _get_current_instance(self, cr, uid, ids, name, args, context=None):
        """
        Get True if the journal was created by this instance.
        NOT TO BE SYNCHRONIZED!!!
        """
        res = {}
        current_instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.id
        for journal in self.browse(cr, uid, ids, context=context):
            res[journal.id] = (current_instance_id == journal.instance_id.id)
        return res

    _columns = {
        'name': fields.char('Journal Name', size=64, required=True, translate=True),
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
        'is_current_instance': fields.function(_get_current_instance, type='boolean', method=True, readonly=True, store=True, string="Current Instance", help="Is this journal from my instance?")
    }

    _defaults = {
        'instance_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.instance_id.id,
    }

    def _check_engagement_count(self, cr, uid, ids, context=None):
        """
        Check that no more than one engagement journal exists for one instance
        """
        if not context:
            context={}
        instance_ids = self.pool.get('msf.instance').search(cr, uid, [], context=context)
        for instance_id in instance_ids:
            # UTP-827: exception: another engagement journal, ENGI, may exist
            eng_ids = self.search(cr, uid, [('type', '=', 'engagement'), ('instance_id', '=', instance_id), ('code', '!=', 'ENGI')])
            if len(eng_ids) and len(eng_ids) > 1:
                return False
        return True

    _constraints = [
        (_check_engagement_count, 'You cannot have more than one engagement journal per instance!', ['type', 'instance_id']),
    ]

account_analytic_journal()

class account_journal(osv.osv):
    _name = 'account.journal'
    _inherit = 'account.journal'

    def _get_current_instance(self, cr, uid, ids, name, args, context=None):
        """
        Get True if the journal was created by this instance.
        NOT TO BE SYNCHRONIZED!!!
        """
        res = {}
        current_instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.id
        for journal in self.browse(cr, uid, ids, context=context):
            res[journal.id] = (current_instance_id == journal.instance_id.id)
        return res

    _columns = {
        'name': fields.char('Journal Name', size=64, required=True, translate=True),
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
        'is_current_instance': fields.function(_get_current_instance, type='boolean', method=True, readonly=True, store=True, string="Current Instance", help="Is this journal from my instance?")
    }

    _defaults = {
        'instance_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.instance_id.id,
    }

    _sql_constraints = [
        ('code_company_uniq', 'unique (code, company_id, instance_id)', 'The code of the journal must be unique per company and instance !'),
        ('name_company_uniq', 'unique (name, company_id, instance_id)', 'The name of the journal must be unique per company and instance !'),
    ]

    # SP-72: in order to always get an analytic journal with the same instance,
    # the create and write check and replace with the "good" journal if necessary.
    def create(self, cr, uid, vals, context=None):
        analytic_obj = self.pool.get('account.analytic.journal')
        if vals.get('type') and vals.get('type') not in ['situation', 'stock'] and vals.get('analytic_journal_id'):
            analytic_journal = analytic_obj.browse(cr, uid, vals['analytic_journal_id'], context=context)

            instance_id = False
            if 'instance_id' in vals:
                instance_id = vals['instance_id']
            else:
                instance_id = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.instance_id.id

            if analytic_journal and \
               analytic_journal.name and \
               analytic_journal.instance_id and \
               analytic_journal.instance_id.id != instance_id:
                # replace the journal with the one with the same name, and the wanted instance
                new_journal_ids = analytic_obj.search(cr, uid, [('name','=', analytic_journal.name),
                                                                ('instance_id','=',instance_id)], context=context)
                if len(new_journal_ids) > 0:
                    vals['analytic_journal_id'] = new_journal_ids[0]
        return super(account_journal, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        analytic_obj = self.pool.get('account.analytic.journal')
        if vals.get('type') and vals.get('type') not in ['situation', 'stock'] and vals.get('analytic_journal_id'):
            analytic_journal = analytic_obj.browse(cr, uid, vals['analytic_journal_id'], context=context)

            instance_id = False
            if 'instance_id' in vals:
                instance_id = vals['instance_id']
            else:
                instance_id = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.instance_id.id

            if analytic_journal and \
               analytic_journal.name and \
               analytic_journal.instance_id and \
               analytic_journal.instance_id.id != instance_id:
                # replace the journal with the one with the same name, and the wanted instance
                new_journal_ids = analytic_obj.search(cr, uid, [('name','=', analytic_journal.name),
                                                                ('instance_id','=',instance_id)], context=context)
                if len(new_journal_ids) > 0:
                    vals['analytic_journal_id'] = new_journal_ids[0]
        return super(account_journal, self).write(cr, uid, ids, vals, context=context)

account_journal()

class account_analytic_journal_fake(osv.osv):
    """ Workaround class used in account.analytic.line search view, because context is lost in m2o search view """
    _inherit = 'account.analytic.journal'
    _name = 'account.analytic.journal.fake'
    _table = 'account_analytic_journal'

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []

        ret = []
        for journal in self.read(cr, uid, ids, ['code', 'instance_id']):
            ret.append((journal['id'], '%s / %s'%(journal['instance_id'] and journal['instance_id'][1] or '', journal['code'])))

        return ret

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        return self.pool.get('account.analytic.journal').fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)

account_analytic_journal_fake()

class account_journal_fake(osv.osv):
    """ Workaround class used in account.move search view, because context is lost in m2o search view """

    _inherit = 'account.journal'
    _name = 'account.journal.fake'
    _table = 'account_journal'

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []

        ret = []
        for journal in self.read(cr, uid, ids, ['code', 'instance_id']):
            ret.append((journal['id'], '%s / %s'%(journal['instance_id'] and journal['instance_id'][1] or '', journal['code'])))

        return ret

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        return self.pool.get('account.journal').fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)

account_journal_fake()

def _get_journal_id_fake(self, cr, uid, ids, field_name, args, context=None):
    res = {}
    if not ids:
        return res
    for i in self.read(cr, uid, ids, ['journal_id']):
        res[i['id']] = i['journal_id']
    return res

def _search_journal_id_fake(self, cr, uid, obj, name, args, context=None):
    res = []
    for arg in args:
        if arg[0] == 'journal_id_fake':
            res.append(('journal_id', arg[1], arg[2]))
        else:
            res.append(arg)
    return res

class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _inherit = 'account.analytic.line'

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
        'journal_id_fake': fields.function(_get_journal_id_fake, method=True, string='Journal', type='many2one', relation='account.analytic.journal.fake', fnct_search=_search_journal_id_fake)
    }

    def onchange_filter_journal(self, cr, uid, ids, instance_id, journal_id, context=None):
        value = {}
        dom = []
        if instance_id:
            dom = [('instance_id', '=', instance_id)]
            if journal_id and not self.pool.get('account.analytic.journal').search(cr, uid, [('id', '=', journal_id), ('instance_id', '=', instance_id)]):
                    value['journal_id_fake'] = False

        return {'domain': {'journal_id_fake': dom}, 'value': value}

    def create(self, cr, uid, vals, context=None):
        if 'journal_id' in vals:
            journal = self.pool.get('account.analytic.journal').read(cr, uid, vals['journal_id'], ['instance_id'], context=context)
            vals['instance_id'] = journal.get('instance_id')[0]
        return super(account_analytic_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if 'journal_id' in vals:
            journal = self.pool.get('account.analytic.journal').read(cr, uid, vals['journal_id'], ['instance_id'], context=context)
            vals['instance_id'] = journal.get('instance_id')[0]
        return super(account_analytic_line, self).write(cr, uid, ids, vals, context=context)

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        """
        Filtering regarding context
        """
        if not context:
            context = {}
        if context.get('instance_ids'):
            instance_ids = context.get('instance_ids')
            if isinstance(instance_ids, (int, long)):
                instance_ids = [instance_ids]
            args.append(('instance_id', 'in', instance_ids))
        return super(account_analytic_line, self).search(cr, uid, args, offset, limit, order, context=context, count=count)

account_analytic_line()

class account_move(osv.osv):
    _name = 'account.move'
    _inherit = 'account.move'

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
        'journal_id_fake': fields.function(_get_journal_id_fake, method=True, string='Journal', type='many2one', relation='account.journal.fake', fnct_search=_search_journal_id_fake)
    }

    def onchange_filter_journal(self, cr, uid, ids, instance_id, journal_id, context=None):
        value = {}
        dom = []
        if instance_id:
            dom = [('instance_id', '=', instance_id)]
            if journal_id and not self.pool.get('account.journal').search(cr, uid, [('id', '=', journal_id), ('instance_id', '=', instance_id)]):
                    value['journal_id_fake'] = False

        return {'domain': {'journal_id_fake': dom}, 'value': value}

    def create(self, cr, uid, vals, context=None):
        if 'journal_id' in vals:
            journal = self.pool.get('account.journal').read(cr, uid, vals['journal_id'], ['instance_id'], context=context)
            vals['instance_id'] = journal.get('instance_id', [False])[0]
        return super(account_move, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if 'journal_id' in vals:
            journal = self.pool.get('account.journal').read(cr, uid, vals['journal_id'], ['instance_id'], context=context)
            vals['instance_id'] = journal.get('instance_id', [False])[0]
        return super(account_move, self).write(cr, uid, ids, vals, context=context)

    def onchange_journal_id(self, cr, uid, ids, journal_id=False, context=None):
        """
        Change msf instance @journal_id change
        """
        res = super(account_move, self).onchange_journal_id(cr, uid, ids, journal_id, context)
        if journal_id:
            journal_data = self.pool.get('account.journal').read(cr, uid, [journal_id], ['instance_id'])
            if journal_data and journal_data[0] and journal_data[0].get('instance_id', False):
                if 'value' not in res:
                    res['value'] = {}
                res['value'].update({'instance_id': journal_data[0].get('instance_id')})
        return res

account_move()

class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
        'journal_id_fake': fields.function(_get_journal_id_fake, method=True, string='Journal', type='many2one', relation='account.journal.fake', fnct_search=_search_journal_id_fake)
    }

    def onchange_filter_journal(self, cr, uid, ids, instance_id, journal_id, context=None):
        return self.pool.get('account.move').onchange_filter_journal(cr, uid, ids, instance_id, journal_id, context)

    def create(self, cr, uid, vals, context=None, check=True):
        if 'journal_id' in vals:
            journal = self.pool.get('account.journal').read(cr, uid, vals['journal_id'], ['instance_id'], context=context)
            vals['instance_id'] = journal.get('instance_id')[0]
        return super(account_move_line, self).create(cr, uid, vals, context=context, check=check)

    def write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
        if 'journal_id' in vals:
            journal = self.pool.get('account.journal').read(cr, uid, vals['journal_id'], ['instance_id'], context=context)
            vals['instance_id'] = journal.get('instance_id')[0]
        return super(account_move_line, self).write(cr, uid, ids, vals, context=context, check=check, update_check=update_check)

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        """
        Filtering regarding context
        """
        if not context:
            context = {}
        if context.get('instance_ids'):
            instance_ids = context.get('instance_ids')
            if isinstance(instance_ids, (int, long)):
                instance_ids = [instance_ids]
            args.append(('instance_id', 'in', instance_ids))
        return super(account_move_line, self).search(cr, uid, args, offset, limit, order, context=context, count=count)

account_move_line()

class account_move_reconcile(osv.osv):
    _name = 'account.move.reconcile'
    _inherit = 'account.move.reconcile'

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }

    _defaults = {
        'instance_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.instance_id.id,
    }

account_move_reconcile()

class account_bank_statement(osv.osv):
    _name = 'account.bank.statement'
    _inherit = 'account.bank.statement'

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }

    def create(self, cr, uid, vals, context=None):
        if 'journal_id' in vals:
            journal = self.pool.get('account.journal').read(cr, uid, vals['journal_id'], ['instance_id'], context=context)
            vals['instance_id'] = journal.get('instance_id')[0]
        return super(account_bank_statement, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if 'journal_id' in vals:
            journal = self.pool.get('account.journal').read(cr, uid, vals['journal_id'], ['instance_id'], context=context)
            vals['instance_id'] = journal.get('instance_id')[0]
        return super(account_bank_statement, self).write(cr, uid, ids, vals, context=context)

account_bank_statement()

class account_bank_statement_line(osv.osv):
    _name = 'account.bank.statement.line'
    _inherit = 'account.bank.statement.line'

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }

    def create(self, cr, uid, vals, context=None):
        if 'statement_id' in vals:
            register = self.pool.get('account.bank.statement').read(cr, uid, vals['statement_id'], ['instance_id'], context=context)
            vals['instance_id'] = register.get('instance_id')[0]
        return super(account_bank_statement_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if 'statement_id' in vals:
            register = self.pool.get('account.bank.statement').read(cr, uid, vals['statement_id'], ['instance_id'], context=context)
            vals['instance_id'] = register.get('instance_id')[0]

        # UTP-1100: Add explicit the value of partner/employee if they are sent by sync with False but removed by the sync engine!
        # THIS IS A BUG OF SYNC CORE!
        if context and context.get('sync_update_execution', False) and context.get('fields', False):
            fields =  context.get('fields')
            if 'partner_txt' in fields and 'partner_txt' not in vals:
                vals['partner_txt'] = False
            if 'partner_id/id' in fields and 'partner_id' not in vals:
                vals['partner_id'] = False
            if 'partner_id2/id' in fields and 'partner_id2' not in vals:
                vals['partner_id2'] = False
            if 'employee_id/id' in fields and 'employee_id' not in vals:
                vals['employee_id'] = False
            if 'ref' in fields and 'ref' not in vals:
                vals['ref'] = False  # UTP-1097
        return super(account_bank_statement_line, self).write(cr, uid, ids, vals, context=context)

account_bank_statement_line()

class account_cashbox_line(osv.osv):
    _name = 'account.cashbox.line'
    _inherit = 'account.cashbox.line'

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }

    def create(self, cr, uid, vals, context=None):
        if 'starting_id' in vals:
            register = self.pool.get('account.bank.statement').read(cr, uid, vals['starting_id'], ['instance_id'], context=context)
            vals['instance_id'] = register.get('instance_id')[0]
        elif 'ending_id' in vals:
            register = self.pool.get('account.bank.statement').read(cr, uid, vals['ending_id'], ['instance_id'], context=context)
            vals['instance_id'] = register.get('instance_id')[0]
        return super(account_cashbox_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if 'starting_id' in vals:
            register = self.pool.get('account.bank.statement').read(cr, uid, vals['starting_id'], ['instance_id'], context=context)
            vals['instance_id'] = register.get('instance_id')[0]
        elif 'ending_id' in vals:
            register = self.pool.get('account.bank.statement').read(cr, uid, vals['ending_id'], ['instance_id'], context=context)
            vals['instance_id'] = register.get('instance_id')[0]
        return super(account_cashbox_line, self).write(cr, uid, ids, vals, context=context)

account_cashbox_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
