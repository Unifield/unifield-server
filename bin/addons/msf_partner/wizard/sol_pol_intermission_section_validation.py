# -*- coding: utf-8 -*-

from osv import osv, fields
import netsvc
from tools.translate import _


class sol_pol_intermission_section_validation_wizard(osv.osv_memory):
    _name = 'sol.pol.intermission.section.validation.wizard'

    _columns = {
        'sol_ids': fields.many2many('sale.order.line', 'sol_inter_vali_wiz_rel', 'wiz_id', 'sol_id', string='FO lines'),
        'pol_ids': fields.many2many('purchase.order.line', 'pol_inter_vali_wiz_rel', 'wiz_id', 'pol_id', string='PO lines'),
        'source': fields.selection([('sale', 'FO'), ('purchase', 'PO')], 'Source of the wizard generation', required=True),
        'partner_type': fields.selection([('intermission', 'Intermission'), ('section', 'Inter-section')], 'Partner Type of the document that generated the wizard', required=True),
        'message': fields.text('Message'),
    }

    def validate(self, cr, uid, ids, context=None):
        '''
        Validate the FO/PO lines given to the wizard
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        wiz = self.browse(cr, uid, ids[0], context=context)
        wf_service = netsvc.LocalService("workflow")
        if wiz.source == 'sale':
            wf_service.trg_validate(uid, 'sale.order.line', [x.id for x in wiz.sol_ids], 'validated', cr)
        elif wiz.source == 'purchase':
            wf_service.trg_validate(uid, 'purchase.order.line', [x.id for x in wiz.pol_ids], 'validated', cr)
        else:
            raise osv.except_osv(_('Error !'), _("An unexpected error happened during the line(s)' validation please refresh the page to retry"))

        return {'type': 'ir.actions.act_window_close'}


sol_pol_intermission_section_validation_wizard()
