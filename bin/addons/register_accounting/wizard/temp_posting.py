#!/usr/bin/env python
#-*- encoding:utf-8 -*-

from osv import osv
from osv import fields

from tools.translate import _
from ..register_tools import open_register_view

class wizard_temp_posting(osv.osv_memory):
    _name = "wizard.temp.posting"
    _rec_name = 'register_id'

    _columns = {
        'regiter_line_ids': fields.many2many('account.bank.statement.line', 'auto_book_statement_rel', 'line_ids', 'wizard_id', 'Lines'),
        'all_lines': fields.boolean('All lines'),
        'register_id': fields.many2one('account.bank.statement', 'Register'),
        'no_register_error_lines': fields.one2many('wizard.temp.posting.line', 'wizard_id', 'Lines'),
        'has_no_register': fields.boolean('Has no register error'),
        'amount_error_lines': fields.one2many('wizard.hard.posting.line', 'wizard_id', 'Lines'),
        'has_amount_error': fields.boolean('Has amount error'),
        'posttype': fields.char('PostType', size=16, readonly=1),
    }

    def nothing_hard_selection(self, cr, uid, ids, context=None):
        return self._do_action(cr, uid, ids, 'nothing', 'hard', context)

    def post_hard_selection(self, cr, uid, ids, context=None):
        return self._do_action(cr, uid, ids, 'post', 'hard', context)

    def nothing_selection(self, cr, uid, ids, context=None):
        return self._do_action(cr, uid, ids, 'nothing', 'temp', context)

    def post_selection(self, cr, uid, ids, context=None):
        return self._do_action(cr, uid, ids, 'post', 'temp', context)

    def _do_action(self, cr, uid, ids, action, posttype, context):
        if context is None:
            context = {}
        if not context.get('button_selected_ids'):
            raise osv.except_osv(_('Warning'), _('No line selected, please tick some lines.'))
        if posttype == 'temp':
            _obj = self.pool.get('wizard.temp.posting.line')
            o2m = 'no_register_error_lines'
        else:
            _obj = self.pool.get('wizard.hard.posting.line')
            o2m = 'amount_error_lines'

        _obj.write(cr, uid, context['button_selected_ids'], {'action': 'do_nothing' if action == 'nothing' else 'post'}, context=context)
        return {'type': 'ir.actions.refresh_o2m', 'o2m_refresh': o2m, 'reset_selection': 1}


    def action_confirm_temp_posting(self, cr, uid, ids, context=None):
        """
        Temp post some statement lines
        """
        if context is None:
            context = {}
        absl_obj = self.pool.get('account.bank.statement.line')

        nb_action = self.pool.get('wizard.temp.posting.line').search(cr, uid, [('wizard_id', '=', ids[0]), ('action', '=', False)], count=True, context=context)
        nb_action += self.pool.get('wizard.hard.posting.line').search(cr, uid, [('wizard_id', '=', ids[0]), ('action', '=', False)], count=True, context=context)
        if nb_action:
            raise osv.except_osv(_('Warning'), _('Action is not defined on %d line(s). Please choose an action: post or not post.') % nb_action)


        statement_id = False
        wiz = self.browse(cr, uid, ids[0], context=context)

        if wiz.posttype == 'hard':
            states = ['draft', 'temp']
        else:
            states = ['draft']

        if wiz.all_lines:
            statement_id = wiz.register_id.id
            st_line_ids = set(absl_obj.search(cr, uid, [('statement_id', '=', wiz.register_id.id), ('state', 'in', states)], context=context))
        else:
            st_line_ids = set([x.id for x in wiz.regiter_line_ids])

        for x in wiz.no_register_error_lines + wiz.amount_error_lines:
            if x.action == 'do_nothing':
                st_line_ids.remove(x.register_line_id.id)

        tochange = []
        # Browse statement lines
        for st_line in absl_obj.read(cr,uid, list(st_line_ids), ['statement_id', 'state']):
            # Verify that the line isn't in hard state
            if not statement_id:
                statement_id = st_line['statement_id'][0]

            if st_line.get('state', False) in states:
                tochange.append(st_line.get('id'))

        if not tochange:
            raise osv.except_osv(_('Warning'), _('There is no line to post for this register.'))


        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        absl_obj.posting(cr, real_uid, tochange, wiz.posttype, force=True, context=context)
        return open_register_view(self, cr, real_uid, statement_id)

    def temp_post_all(self, cr, uid, ids, context=None):
        return self.action_confirm_temp_posting(cr, uid, ids, context=context, all_lines=True)


wizard_temp_posting()



class wizard_temp_posting_line(osv.osv_memory):
    _name = 'wizard.temp.posting.line'
    _rec_name = 'line_description'
    _order = 'register_line_id, name'

    def _get_hidden_action(self, cr, uid, ids, *a, **b):
        ret = {}
        for x in self.read(cr, uid, ids, ['action']):
            ret[x['id']] = x['action']
        return ret


    _columns = {
        'wizard_id': fields.many2one('wizard.temp.posting', 'Wizard'),
        'register_line_id': fields.many2one('account.bank.statement.line', 'Register Line', readonly=True),
        'sequence_for_reference': fields.char('Sequence', size=512, readonly=True),
        'name': fields.char('Description', size=512, readonly=True),
        'account_id': fields.many2one('account.account', 'Account', size=512, readonly=True),
        'ref': fields.char('Reference', size=512, readonly=True),
        'amount_in': fields.float('Amount In', readonly=True),
        'amount_out': fields.float('Amount Out', readonly=True),
        'third': fields.char('Third Party', size=512, readonly=True),
        'action': fields.selection([('do_nothing', 'Do Not Post'), ('post', 'Post')], 'Action', required=True, add_empty=True),
        'hidden_action': fields.function(_get_hidden_action, method=1, type='char', string='Action'),
    }

    def do_nothing(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'action': 'do_nothing'}, context=context)
        return True

    def do_post(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'action': 'post'}, context=context)
        return True

wizard_temp_posting_line()

class wizard_hard_posting_line(osv.osv_memory):
    _name = 'wizard.hard.posting.line'
    _inherit = 'wizard.temp.posting.line'

    _columns = {
        'other_ref': fields.char('Counterpart Reference', size=512, readonly=True),
        'other_in': fields.float('Counterpart Amount In', readonly=True),
        'other_out': fields.float('Counterpart Amount Out', readonly=True),
        'other_account_id': fields.many2one('account.account', 'Counterpart Account', readonly=True),
        'other_third_id': fields.many2one('account.journal', 'Counterpart Third Party', readonly=True),
    }

wizard_hard_posting_line()

