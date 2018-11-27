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

import tools
import netsvc

from osv import osv
from osv import fields
from tools.translate import _

REAL_MODEL_LIST = [('sale.order', 'Sale Order'),
                   ('purchase.order', 'Purchase Order'),
                   ('internal.request', 'Internal Request'),
                   ('rfq', 'Request for Quotation'),
                   ('tender', 'Tender')]


class documents_done_wizard(osv.osv):
    _name = 'documents.done.wizard'
    _description = 'Documents not \'Done\''
    _auto = False

    def _get_selection(self, cr, uid, context=None):
        states = []
        if not context:
            context = {}

        for model in context.get('models', ['sale.order', 'purchase.order', 'tender']):
            sel = self.pool.get(model).fields_get(cr, uid, ['state'])
            res = sel['state']['selection']
            if model == 'purchase.order':
                res = self.pool.get(model).fields_get(cr, uid, ['rfq_state'])['rfq_state']['selection'] + res
                
            for st in res:
                if not 'db_value' in context:
                    if (st[1], st[1]) not in states and st[0] not in ('done', 'cancel'):
                        states.append((st[1], st[1]))
                else:
                    if (st[0], st[1]) not in states and st[0] not in ('done', 'cancel'):
                        states.append((st[0], st[1]))


        return states

    def _get_model_from_state(self, cr, uid, state, context=None):
        '''
        Returns the model which have the value of state in the selection field 'state'.
        '''
        if not context:
            context = {}

        models = []
        states = []

        for model in context.get('models', ['sale.order', 'purchase.order', 'tender']):
            sel = self.pool.get(model).fields_get(cr, uid, ['state'])
            for st in sel['state']['selection']:
                if st[1] == state:
                    models.append(model)
                    states.append(st[0])

        return models, states

    def _get_state(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the good value according to the doc type
        '''
        res = {}
        if context is None:
            context = {}

        for doc in self.browse(cr, uid, ids, context=context):
            field = 'rfq_state' if doc.model == 'rfq' else 'state'
            state_str = self.pool.get('ir.model.fields').get_selection(cr, uid, doc.real_model, field, doc.state, context=context)
            res[doc.id] = state_str

        return res

    def _search_state(self, cr, uid, obj, name, args, context=None):
        '''
        Returns all documents according to state
        '''
        ids = []

        for arg in args:
            if arg[0] == 'display_state':
                docs, db_values = self._get_model_from_state(cr, uid, arg[2])
                ids = self.pool.get('documents.done.wizard').search(cr, uid, [('real_model', 'in', docs), ('state', 'in', db_values)], context=context)

        return [('id', 'in', ids)]

    def _get_related_stock_moves(self, cr, uid, order, field, context=None):
        '''
        Returns all stock moves related to an order (sale.order/purchase.order)
        '''
        line_ids = []
        for line in order.order_line:
            line_ids.append(line.id)

        if order._name == 'sale.order' and order.procurement_request:
            return self.pool.get('stock.move').search(cr, uid, [('state', 'not in', ['cancel', 'done']), (field, 'in', line_ids)], context=context)
        return self.pool.get('stock.move').search(cr, uid, [('state', 'not in', ['cancel', 'done']), (field, 'in', line_ids), ('type', '!=', 'internal')], context=context)

    def _get_problem_sale_order(self, cr, uid, order, context=None):
        '''
        Check if all stock moves, all procurement orders, all purchase orders
        and all stock picking generated from the sale order is closed or canceled
        '''
        if not context:
            context = {}
        move_ids = self._get_related_stock_moves(cr, uid, order, 'sale_line_id', context=context)
        proc_ids = []
        po_ids = []
        tender_ids = []
        invoice_ids = []
        for line in order.order_line:
            pol_id = self.pool.get('purchase.order.line').search(cr, uid, [('linked_sol_id', '=', line.id)], context=context)
            po_line = self.pool.get('purchase.order.line').browse(cr, uid, pol_id[0], context=context) if pol_id else False
            # Check PO
            if po_line and not po_line.state.startswith(('cancel', 'done')):
                po_ids.append(po_line.order_id.id)

        # Check loan counterpart
        if order.loan_id and order.loan_id.state not in ('cancel', 'done'):
            po_ids.append(order.loan_id.id)

        if context.get('count', False):
            return move_ids or proc_ids or po_ids or tender_ids or invoice_ids or False
        else:
            return move_ids, proc_ids, po_ids, tender_ids, invoice_ids

    def _get_problem_purchase_order(self, cr, uid, order, context=None):
        '''
        Check if all stock moves, all invoices
        and all stock picking generated from the purchase order is closed or canceled
        '''
        if not context:
            context = {}
        move_ids = self._get_related_stock_moves(cr, uid, order, 'purchase_line_id', context=context)
        so_ids = []
        invoice_ids = []
        if order.loan_id and order.loan_id.state not in ('cancel', 'done'):
            so_ids.append(order.loan_id.id)

        if context.get('count', False):
            return move_ids or so_ids or invoice_ids or False
        else:
            return move_ids, so_ids, invoice_ids

    def _get_problem_tender(self, cr, uid, order, context=None):
        '''
        Check if all request for quotations and all purchase orders
        generated from the tender is closed or canceled
        '''
        if not context:
            context = {}
        po_ids = self.pool.get('purchase.order').search(cr, uid, [('state', 'not in', ['cancel', 'done']), ('tender_id', '=', order.id)], context=context)
        if context.get('count', False):
            return po_ids or False
        else:
            return po_ids

    def _get_problem(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns True if at least one doc stop the manually done processe
        '''
        if not context:
            context = {}
        res = {}
        c = context.copy()
        c.update({'count': True})
        for doc in self.browse(cr, uid, ids, context=context):
            order = self.pool.get(doc.real_model).browse(cr, uid, doc.res_id, context=context)
            if doc.real_model == 'sale.order':
                res[doc.id] = self._get_problem_sale_order(cr, uid, order, context=c) and True or False
            elif doc.real_model == 'purchase.order':
                res[doc.id] = self._get_problem_purchase_order(cr, uid, order, context=c) and True or False
            elif doc.real_model == 'tender':
                res[doc.id] = self._get_problem_tender(cr, uid, order, context=c) and True or False
            else:
                res[doc.id] = False

        return res

    _columns = {
        'name': fields.char(size=256, string='Name', readonly=True),
        'res_id': fields.integer(string='Res. Id'),
        'real_model': fields.char(size=64, string='Real model'),
        'model': fields.selection(REAL_MODEL_LIST, string='Doc. Type', readonly=True),
        'creation_date': fields.date(string='Creation date', readonly=True),
        'expected_date': fields.date(string='Expected date', readonly=True),
        'partner_id': fields.many2one('res.partner', string='Partner', readonly=True),
        'problem': fields.function(_get_problem, string='Problem', required=True, method=True, store=False,
                                   type='boolean', readonly=True),
        'state': fields.char(size=64, string='State', readonly=True),
        'display_state': fields.function(_get_state, fnct_search=_search_state, type='selection', selection=_get_selection,
                                         method=True, store=False, readonly=True, string='State'),
        'requestor': fields.many2one('res.users', string='Creator', readonly=True),
    }

    def _get_model_name(self, model):
        '''
        Returns the readable model name
        '''
        for model_name in REAL_MODEL_LIST:
            if model_name[0] == model:
                return model_name[1]

        return 'Undefined'

    def _add_stock_move_pb(self, cr, uid, problem_id, moves, context=None):
        '''
        Add a line for each moves
        '''
        if not context:
            context = {}
        line_obj = self.pool.get('documents.done.problem.line')
        picking_ids = []
        for move in self.pool.get('stock.move').browse(cr, uid, moves, context=context):
            if move.picking_id and (move.type != 'out' or move.picking_id.converted_to_standard or move.picking_id.subtype == 'picking') and move.picking_id.id not in picking_ids:
                picking_ids.append(move.picking_id.id)
                doc_type = 'Internal move'
                if move.type == 'out':
                    doc_type = 'Delivery Order'
                elif move.type == 'in':
                    doc_type = 'Incoming Shipment'
                line_obj.create(cr, uid, {'problem_id': problem_id,
                                          'doc_name': move.picking_id.name,
                                          'doc_state': move.picking_id.state,
                                          'doc_model': 'stock.picking',
                                          'doc_id': move.picking_id.id,
                                          'doc_type': doc_type}, context=context)
            elif not move.picking_id:
                line_obj.create(cr, uid, {'problem_id': problem_id,
                                          'doc_name': move.name,
                                          'doc_state': move.state,
                                          'doc_model': 'stock.move',
                                          'doc_id': move.id,
                                          'doc_type': 'Stock move'}, context=context)
        return

    def _add_purchase_order(self, cr, uid, problem_id, po_ids, context=None):
        '''
        Add line for each PO/RfQ
        '''
        if not context:
            context = {}
        line_obj = self.pool.get('documents.done.problem.line')
        for order in self.pool.get('purchase.order').browse(cr, uid, po_ids, context=context):
            line_obj.create(cr, uid, {'problem_id': problem_id,
                                      'doc_name': order.name,
                                      'doc_state': order.state,
                                      'doc_model': 'purchase.order',
                                      'doc_id': order.id,
                                      'doc_type': order.rfq_ok and 'Request for Quotation' or 'Purchase Order'}, context=context)
        return

    def go_to_problems(self, cr, uid, ids, context=None):
        '''
        Returns a wizard with all documents posing a problem
        '''
        if not context:
            context = {}
        pb_obj = self.pool.get('documents.done.problem')
        pb_line_obj = self.pool.get('documents.done.problem.line')

        for wiz in self.browse(cr, uid, ids, context=context):

            if not wiz.problem:
                context.update({'direct_cancel': True})
                return self.cancel_line(cr, uid, [wiz.id], all_doc=True, context=context)

            pick_ids = []
            order = False
            move_ids = []
            proc_ids = []
            po_ids = []
            so_ids = []
            tender_ids = []
            invoice_ids = []
            doc = self.pool.get(wiz.real_model).browse(cr, uid, wiz.res_id, context=context)
            pb_id = pb_obj.create(cr, uid, {'wizard_id': wiz.id,
                                            'doc_name': doc.name}, context=context)

            # For sales orders and procurement request
            if wiz.real_model == 'sale.order':
                order = self.pool.get('sale.order').browse(cr, uid, wiz.res_id, context=context)
                move_ids, proc_ids, po_ids, tender_ids, invoice_ids = self._get_problem_sale_order(cr, uid, order, context=context)
            elif wiz.real_model == 'purchase.order':
                order = self.pool.get('purchase.order').browse(cr, uid, wiz.res_id, context=context)
                move_ids, so_ids, invoice_ids = self._get_problem_purchase_order(cr, uid, order, context=context)
            elif wiz.real_model == 'tender':
                order = self.pool.get('tender').browse(cr, uid, wiz.res_id, context=context)
                po_ids = self._get_problem_tender(cr, uid, order, context=context)

            # Remove duplicate
            pick_ids = list(set(pick_ids))
            move_ids = list(set(move_ids))
            proc_ids = list(set(proc_ids))
            po_ids = list(set(po_ids))
            so_ids = list(set(so_ids))
            tender_ids = list(set(tender_ids))
            invoice_ids = list(set(invoice_ids))

            # Process all stock moves
            self._add_stock_move_pb(cr, uid, pb_id, move_ids, context=context)
            # Process all PO/RfQ
            self._add_purchase_order(cr, uid, pb_id, po_ids, context=context)
            # Process all tenders
            for tender in self.pool.get('tender').browse(cr, uid, tender_ids, context=context):
                pb_line_obj.create(cr, uid, {'problem_id': pb_id,
                                             'doc_name': tender.name,
                                             'doc_state': tender.state,
                                             'doc_model': 'tender',
                                             'doc_id': tender.id,
                                             'doc_type': 'Tender'}, context=context)
            # Search all procurement orders attached to the sale order
            for proc in self.pool.get('procurement.order').browse(cr, uid, proc_ids, context=context):
                pb_line_obj.create(cr, uid, {'problem_id': pb_id,
                                             'doc_name': proc.name,
                                             'doc_state': proc.state,
                                             'doc_model': 'procurement.order',
                                             'doc_id': proc.id,
                                             'doc_type': 'Procurement Order'}, context=context)

            # Process all invoices
            for inv in self.pool.get('account.invoice').browse(cr, uid, invoice_ids, context=context):
                pb_line_obj.create(cr, uid, {'problem_id': pb_id,
                                             'doc_name': inv.number or inv.name,
                                             'doc_state': inv.state,
                                             'doc_model': 'account.invoice',
                                             'doc_id': inv.id,
                                             'doc_type': 'Invoice'}, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'documents.done.problem',
                'view_mode': 'form',
                'view_type': 'form',
                'context': context,
                'res_id': pb_id,
                'target': 'popup'}


    def cancel_line(self, cr, uid, ids, all_doc=True, context=None):
        '''
        Set the document to done state
        '''
        pb_obj = self.pool.get('documents.done.problem')
        if not context:
            context = {}

        for doc in self.browse(cr, uid, ids, context=context):
            if self.pool.get(doc.real_model).browse(cr, uid, doc.res_id, context=context).state not in ('cancel', 'done'):
                self.pool.get(doc.real_model).set_manually_done(cr, uid, doc.res_id, all_doc=all_doc, context=context)
                if all_doc:
                    if doc.real_model == 'sale.order' and self.pool.get(doc.real_model).read(cr, uid, doc.res_id, ['procurement_request'])['procurement_request']:
                        proc_view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'procurement_request', 'procurement_request_form_view')
                        context.update({'view_id': proc_view and proc_view[1] or False})
                        self.pool.get(doc.real_model).log(cr, uid, doc.res_id, _('The Internal request \'%s\' has been closed.')%(doc.name), context=context)
                    else:
                        self.pool.get(doc.real_model).log(cr, uid, doc.res_id, _('The %s \'%s\' has been closed.')%(self._get_model_name(doc.real_model), doc.name), context=context)
                    pb_ids = pb_obj.search(cr, uid, [('wizard_id', '=', doc.id)], context=context)
                    pb_obj.done_all_documents(cr, uid, pb_ids, all_doc=all_doc, context=context)

        if not context.get('direct_cancel', False):
            return {'type': 'ir.actions.act_window_close'}
        else:
            return True

    def init(self, cr):
        '''
        Create the view
        '''
        tools.drop_view_if_exists(cr, 'documents_done_wizard')
        cr.execute("""CREATE OR REPLACE VIEW documents_done_wizard AS (
                SELECT
                    row_number() OVER(ORDER BY name) AS id,
                    dnd.name,
                    dnd.res_id,
                    dnd.real_model,
                    dnd.model,
                    dnd.state,
                    dnd.creation_date,
                    dnd.expected_date,
                    dnd.partner_id,
                    dnd.requestor
                FROM
                    ((SELECT
                        so.name AS name,
                        so.id AS res_id,
                        'sale.order' AS real_model,
                        'sale.order' AS model,
                        so.state AS state,
                        so.date_order AS creation_date,
                        so.delivery_requested_date AS expected_date,
                        so.partner_id,
                        so.create_uid AS requestor
                    FROM
                        sale_order so
                    WHERE
                        state NOT IN ('draft', 'done', 'cancel')
                      AND
                        procurement_request = False)
                UNION
                    (SELECT
                        ir.name AS name,
                        ir.id AS res_id,
                        'sale.order' AS real_model,
                        'internal.request' AS model,
                        ir.state AS state,
                        ir.date_order AS creation_date,
                        ir.delivery_requested_date AS expected_date,
                        NULL AS partner_id,
                        ir.create_uid AS requestor
                    FROM
                        sale_order ir
                    WHERE
                        state NOT IN ('draft', 'done', 'cancel')
                      AND
                        procurement_request = True)
                UNION
                    (SELECT
                        po.name AS name,
                        po.id AS res_id,
                        'purchase.order' AS real_model,
                        'purchase.order' AS model,
                        po.state AS state,
                        po.date_order AS creation_date,
                        po.delivery_requested_date AS expected_date,
                        po.partner_id AS partner_id,
                        po.create_uid AS requestor
                    FROM
                        purchase_order po
                    WHERE
                        state NOT IN ('draft', 'done', 'cancel', 'split')
                      AND
                        rfq_ok = False)
                UNION
                    (SELECT
                        rfq.name AS name,
                        rfq.id AS res_id,
                        'purchase.order' AS real_model,
                        'rfq' AS model,
                        rfq.state AS state,
                        rfq.date_order AS creation_date,
                        rfq.delivery_requested_date AS expected_date,
                        rfq.partner_id AS partner_id,
                        rfq.create_uid AS requestor
                    FROM
                        purchase_order rfq
                    WHERE
                        state NOT IN ('draft', 'done', 'cancel')
                      AND
                        rfq_ok = True)
                UNION
                    (SELECT
                        t.name AS name,
                        t.id AS res_id,
                        'tender' AS real_model,
                        'tender' AS model,
                        t.state AS state,
                        t.creation_date AS creation_date,
                        t.requested_date AS expected_date,
                        NULL AS partner_id,
                        t.create_uid AS requestor
                    FROM
                        tender t
                    WHERE
                        state NOT IN ('draft', 'done', 'cancel'))) AS dnd
        );""")

documents_done_wizard()

class documents_done_problem(osv.osv_memory):
    _name = 'documents.done.problem'

    def _get_errors(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns True if at least one problem is found
        '''
        if not context:
            context = {}
        res = {}

        for doc in self.browse(cr, uid, ids, context=context):
            res[doc.id] = False
            if doc.pb_lines:
                res[doc.id] = True

        return res

    _columns = {
        'wizard_id': fields.many2one('documents.done.wizard', string='Wizard'),
        'doc_name': fields.char(size=64, string='Document'),
        'errors': fields.function(_get_errors, method=True, store=False, string='Errors', type='boolean', readonly=True),
        'pb_lines': fields.one2many('documents.done.problem.line', 'problem_id', string='Lines'),
    }

    def done_all_documents(self, cr, uid, ids, all_doc=True, context=None):
        '''
        For all documents, check the state of the doc and send the signal
        of 'manually_done' if needed
        '''
        if not context:
            context = {}
        wf_service = netsvc.LocalService("workflow")
        for wiz in self.browse(cr, uid, ids, context=context):
            for line in wiz.pb_lines:
                if line.doc_model == 'account.invoice':
                    invoice_state = self.pool.get('account.invoice').browse(cr, uid, line.doc_id, context=context).state
                    if invoice_state == 'draft':
                        wf_service.trg_validate(uid, line.doc_model, line.doc_id, 'invoice_cancel', cr)
#                    elif invoice_state not in ('cancel', 'paid'):
#                        raise osv.except_osv(_('Error'), _('You cannot set the SO to \'Closed\' because the following invoices are not Cancelled or Paid : %s') % ([map(x.name + '/') for x in error_inv_ids]))
                elif line.doc_model == 'tender':
                    self.pool.get('tender').set_manually_done(cr, uid, [line.doc_id], context=context)
                elif self.pool.get(line.doc_model).browse(cr, uid, line.doc_id, context=context).state not in ('cancel', 'done'):
                    self.pool.get(line.doc_model).set_manually_done(cr, uid, line.doc_id, all_doc=all_doc, context=context)

#            return self.pool.get('documents.done.wizard').go_to_problems(cr, uid, [wiz.wizard_id.id], context=context)

#        return {'type': 'ir.actions.act_window',
#                'res_model': 'documents.done.wizard',
#                'view_type': 'form',
#                'view_mode': 'tree',
#                'context': context,
#                'target': 'crush'}

    def cancel_document(self, cr, uid, ids, context=None):
        '''
        Cancel the document
        '''
        if not context:
            context = {}
        wf_service = netsvc.LocalService("workflow")

        for wiz in self.browse(cr, uid, ids, context=context):
            res = self.pool.get('documents.done.wizard').cancel_line(cr, uid, [wiz.wizard_id.id], all_doc=True, context=context)

            # cancel associated document:
            for wiz_line in wiz.pb_lines:
                if wiz_line.doc_model in ('purchase.order', 'sale.order', 'tender'):
                    for order in self.pool.get(wiz_line.doc_model).browse(cr, uid, [wiz_line.doc_id], context=context):
                        for line in order.order_line:
                            wf_service.trg_validate(uid, line._name, line.id, 'cancel', cr)

        return res

documents_done_problem()

class documents_done_problem_line(osv.osv_memory):
    _name = 'documents.done.problem.line'

    def _get_state(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Return the state of the related doc
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            sel = self.pool.get(line.doc_model).fields_get(cr, uid, ['state'])
            res_state = dict(sel['state']['selection']).get(line.doc_state, line.doc_state)
            name = '%s,state' % line.doc_model
            tr_ids = self.pool.get('ir.translation').search(cr, uid, [('type', '=', 'selection'), ('name', '=', name),('src', '=', res_state)])
            if tr_ids and self.pool.get('ir.translation').read(cr, uid, tr_ids, ['value'])[0]['value']:
                res[line.id] = self.pool.get('ir.translation').read(cr, uid, tr_ids, ['value'])[0]['value']
            else:
                res[line.id] = res_state

        return res

    _columns = {
        'problem_id': fields.many2one('documents.done.problem', string='Problem'),
        'doc_name': fields.char(size='64', string='Reference'),
        'doc_state': fields.char(size=64, string='DB state'),
        'doc_state_str': fields.function(_get_state, method=True, string='State', type='char', readonly=True),
        'doc_type': fields.char(size=64, string='Doc. Type'),
        'doc_model': fields.char(size=64, string='Doc. Model'),
        'doc_id': fields.integer(string='Doc. Id'),
    }

    def go_to_doc(self, cr, uid, ids, context=None):
        '''
        Open the form of the related doc
        '''
        if not context:
            context = {}
        for item in self.browse(cr, uid, ids, context=context):
            return {'type': 'ir.actions.act_window',
                    'res_model': item.doc_model,
                    'name': item.doc_type,
                    'view_type': 'form',
                    'view_mode': 'form',
                    'context': context,
                    'res_id': item.doc_id,}

documents_done_problem_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
