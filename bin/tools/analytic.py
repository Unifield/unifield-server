#!/usr/bin/env python
# -*- coding: utf-8 -*-

from osv import osv
from tools.translate import _


def get_analytic_state(self, cr, uid, ids, name, args, context=None):
    """
    Get state of distribution:
     - if compatible with the line, then "valid"
     - all other case are "invalid"
    """
    if isinstance(ids, int):
        ids = [ids]
    # Prepare some values
    res = {}
    ad_obj = self.pool.get('analytic.distribution')
    dest_cc_link_obj = self.pool.get('dest.cc.link')
    # Search MSF Private Fund element, because it's valid with all accounts
    try:
        fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution',
                                                                    'analytic_account_msf_private_funds')[1]
    except ValueError:
        fp_id = 0
    # Browse all given lines to check analytic distribution validity
    ## TO CHECK:
    # A/ if no CC
    # B/ if FP = MSF Private FUND
    # C/ (account/DEST) in FP except B
    # D/ CC in FP except when B
    # E/ DEST in list of available DEST in ACCOUNT
    # F/ Check posting date with cost center and destination if exists
    # G/ Check document date with funding pool
    # H/ Check Cost Center / Destination compatibility
    ## CASES where FP is filled in (or not) and/or DEST is filled in (or not).
    ## CC is mandatory, so always available:
    # 1/ no FP, no DEST => Distro = valid
    # 2/ FP, no DEST => Check D except B
    # 3/ no FP, DEST => Check E
    # 4/ FP, DEST => Check C, D except B, E
    ##
    account_dest_map = {}
    cc_active_map = {}
    dest_active_map = {}
    fp_active_map = {}
    cc_dest_date_map = {}
    fp_dest_map = {}
    fp_acc_dest_map = {}
    fp_cc_map = {}
    cc_dest_map = {}

    is_hq_entries = False
    is_payroll = False
    for line in self.browse(cr, uid, ids, context=context):
        if self._name == 'hq.entries':
            fp_analytic = line['analytic_id']
            is_hq_entries = True
        elif self._name == 'hr.payroll.msf':
            fp_analytic = line['funding_pool_id']
            is_payroll = True
        else:
            raise osv.except_osv(_('Error'), _('Model not found'))

        res[line.id] = 'valid' # by default
        #### SOME CASE WHERE DISTRO IS OK
        # if it's neither an expense nor an income account, the AD is valid
        if line.account_id and not line.account_id.is_analytic_addicted:
            continue
        # Date checks
        # F Check
        if line.cost_center_id:
            key = (line.cost_center_id.id, line.date)
            if key not in cc_active_map:
                cc = self.pool.get('account.analytic.account').browse(cr, uid, line.cost_center_id.id, fields_to_fetch=['filter_active', 'code'], context={'date': line.date})
                cc_active_map[key] = cc and cc.filter_active is not False
            if not cc_active_map[key]:
                res[line.id] = 'invalid'
                continue
        if line.destination_id:
            key = (line.destination_id.id, line.date)
            if key not in dest_active_map:
                dest = self.pool.get('account.analytic.account').browse(cr, uid, line.destination_id.id, fields_to_fetch=['filter_active', 'code'], context={'date': line.date})
                dest_active_map[key] = dest and dest.filter_active is not False
            if not dest_active_map[key]:
                res[line.id] = 'invalid'
                continue
        if line.destination_id and line.cost_center_id and line.date:
            key = (line.destination_id.id, line.cost_center_id.id, line.date)
            if key not in cc_dest_date_map:
                cc_dest_date_map[key] = not dest_cc_link_obj.is_inactive_dcl(cr, uid, line.destination_id.id, line.cost_center_id.id, line.date, context=context)
            if not cc_dest_date_map[key]:
                res[line.id] = 'invalid'
                continue
        # G Check
        if fp_analytic:
            key = (fp_analytic.id, line.document_date)
            if key not in fp_active_map:
                fp = self.pool.get('account.analytic.account').browse(cr, uid, fp_analytic.id, fields_to_fetch=['filter_active', 'code'], context={'date': line.document_date})
                fp_active_map[key] = fp and fp.filter_active is not False
            if not fp_active_map[key]:
                res[line.id] = 'invalid'
                continue
        if is_hq_entries:
            # if just a cost center, it's also valid! (CASE 1/)
            if not fp_analytic and not line.destination_id:
                continue
            # if FP is MSF Private Fund and no destination_id, then all is OK.
            if fp_analytic and fp_analytic.id == fp_id and not line.destination_id:
                continue
        if is_payroll:
            # if just a cost center, it's also invalid (since US-10228)
            if line.cost_center_id and not fp_analytic and not line.destination_id:
                res[line.id] = 'invalid'
                continue
            # if FP is MSF Private Fund and no destination_id, it's also invalid (since US-10228).
            if fp_analytic and fp_analytic == fp_id and not line.destination_id:
                res[line.id] = 'invalid'
                continue

        #### END OF CASES
        if not line.cost_center_id:
            res[line.id] = 'invalid'
            continue
        if fp_analytic and not line.destination_id: # CASE 2/
            key = (fp_analytic.id, line.cost_center_id.id)
            if key not in fp_dest_map:
                fp_dest_map[key] = ad_obj.check_fp_cc_compatibility(cr, uid, fp_analytic.id, line.cost_center_id.id, context=context)
            # D Check, except B check
            if not fp_dest_map[key]:
                res[line.id] = 'invalid'
                continue
        elif not fp_analytic and line.destination_id: # CASE 3/
            # E Check
            key = (line.destination_id.id, line.account_id.id)
            if key not in account_dest_map:
                account_dest_map[key] =  ad_obj.check_gl_account_destination_compatibility(cr, uid, line.account_id.id, line.destination_id.id)
            if not account_dest_map[key]:
                res[line.id] = 'invalid'
                continue
        else: # CASE 4/
            # C Check, except B
            key = (fp_analytic.id, line.account_id.id, line.destination_id.id)
            if key not in fp_acc_dest_map:
                fp_acc_dest_map[key] = ad_obj.check_fp_acc_dest_compatibility(cr, uid, fp_analytic.id, line.account_id.id, line.destination_id.id, context=context)
            if not fp_acc_dest_map[key]:
                res[line.id] = 'invalid'
                continue
            # D Check, except B check
            key = (fp_analytic.id, line.cost_center_id.id)
            if key not in fp_cc_map:
                fp_cc_map[key] = ad_obj.check_fp_cc_compatibility(cr, uid, fp_analytic.id, line.cost_center_id.id, context=context)
            if not fp_cc_map[key]:
                res[line.id] = 'invalid'
                continue
            # E Check
            key = (line.destination_id.id, line.account_id.id)
            if key not in account_dest_map:
                account_dest_map[key] =  ad_obj.check_gl_account_destination_compatibility(cr, uid, line.account_id.id, line.destination_id.id)
            if not account_dest_map[key]:
                res[line.id] = 'invalid'
                continue
        # H check
        if line.destination_id and line.cost_center_id:
            key = (line.destination_id, line.cost_center_id)
            if key not in cc_dest_map:
                cc_dest_map[key] = ad_obj.check_dest_cc_compatibility(cr, uid, line.destination_id.id, line.cost_center_id.id, context=context)
            if not cc_dest_map[key]:
                res[line.id] = 'invalid'
    return res

