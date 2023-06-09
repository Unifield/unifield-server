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
        'register_id': fields.many2one('Register'),
        'no_register_error_lines': fields.one2many('wizard.temp.posting.line', 'wizard_id', 'Lines'),
        'has_no_register': fields.boolean('Has no register error'),
    }

    def nothing_selection(self, cr, uid, ids, context=None):
        return self._do_action(cr, uid, ids, 'nothing', context)

    def post_selection(self, cr, uid, ids, context=None):
        return self._do_action(cr, uid, ids, 'post', context)

    def _do_action(self, cr, uid, ids, action, context):
        if context is None:
            context = {}
        if not context.get('button_selected_ids'):
            raise osv.except_osv(_('Warning'), _('No line selected, please tick some lines.'))
        self.pool.get('wizard.temp.posting.line').write(cr, uid, context['button_selected_ids'], {'action': 'do_nothing' if action == 'nothing' else 'post'}, context=context)
        return True


    def action_confirm_temp_posting(self, cr, uid, ids, context=None, all_lines=False):
        """
        Temp post some statement lines
        """
        if context is None:
            context = {}
        absl_obj = self.pool.get('account.bank.statement.line')
        # note: active_ids must be in context also for Temp Post "ALL", or that would mean that there is no line to post in the reg. anyway
        if context.get('active_ids'):
            # Retrieve statement line ids
            st_line_ids = context.get('active_ids')
            if isinstance(st_line_ids, (int, long)):
                st_line_ids = [st_line_ids]
            if all_lines:  # get ALL the register lines to temp-post for this register
                reg_id = absl_obj.browse(cr, uid, st_line_ids[0], fields_to_fetch=['statement_id'], context=context).statement_id.id
                if reg_id == context.get('register_id'):  # out of security compare with the register_id in param.
                    st_line_ids = absl_obj.search(cr, uid,
                                                  [('statement_id', '=', reg_id), ('state', '=', 'draft')],
                                                  context=context)
                    if not st_line_ids:
                        # UC: either lines have been temp posted since the display of the temp posting page,
                        # or the action is performed from the Register Lines View although there are no more Draft lines
                        raise osv.except_osv(_('Warning'), _('There are no more lines to temp post for this register. '
                                                             'Please refresh the page.'))
                else:
                    raise osv.except_osv(_('Warning'), _('Impossible to retrieve automatically the lines to temp post for this register. '
                                                         'Please select them manually and click on "Temp Posting".'))
            # Prepare some values
            tochange = []
            # Browse statement lines
            for st_line in absl_obj.read(cr,uid, st_line_ids, ['statement_id', 'state']):
                # Verify that the line isn't in hard state
                if st_line.get('state', False) == 'draft':
                    tochange.append(st_line.get('id'))
            real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
            absl_obj.posting(cr, real_uid, tochange, 'temp', context=context)
            return open_register_view(self, cr, real_uid, st_line.get('statement_id')[0])
        elif all_lines:
            raise osv.except_osv(_('Warning'), _('There are no lines to temp post for this register.'))
        else:
            raise osv.except_osv(_('Warning'), _('You have to select some lines before using this wizard.'))

    def temp_post_all(self, cr, uid, ids, context=None):
        return self.action_confirm_temp_posting(cr, uid, ids, context=context, all_lines=True)


wizard_temp_posting()



class wizard_temp_posting_line(osv.osv_memory):
    _name = 'wizard.temp.posting.line'
    _rec_name = 'line_description'
    _order = 'register_line_id, name'
    _columns = {
        'wizard_id': fields.many2one('wizard.temp.posting', 'Wizard'),
        'register_line_id': fields.many2one('account.bank.statement.line', 'Register Line', readonly=True),
        'sequence_for_reference': fields.char('Sequence', size=512, readonly=True),
        'name': fields.char('Description', size=512, readonly=True),
        'ref': fields.char('Reference', size=512, readonly=True),
        'account_id': fields.many2one('account.account', 'Account', size=512, readonly=True),
        'amount_in': fields.float('Amount In', readonly=True),
        'amount_out': fields.float('Amount Out', readonly=True),
        'third': fields.char('Third Party', size=512, readonly=True),
        'action': fields.selection([('do_nothing', 'Do Not Post'), ('post', 'Post')], 'Action', required=True, add_empty=True),
    }

wizard_temp_posting_line()
