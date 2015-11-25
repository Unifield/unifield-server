# -*- coding: utf-8 -*-

from osv import fields
from osv import osv

from time import strftime
from time import strptime


class ocba_export_wizard(osv.osv_memory):
    _name = "ocba.export.wizard"

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Top proprietary instance', required=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal year', required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True),
        'selection': fields.selection([('unexported', 'Not yet exported'), ('all', 'All lines')], string="Select", required=True),
    }

    _defaults = {
        'fiscalyear_id': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, strftime('%Y-%m-%d'), context=c),
        'selection': lambda *a: 'unexported',
    }

    def button_export(self, cr, uid, ids, context=None):
        """
        Launch a report to generate the ZIP file.
        """
        # Prepare some values
        wizard = self.browse(cr, uid, ids[0], context=context)
        data = {}
        # add parameters
        data['form'] = {}
        if wizard.instance_id:
            # Get projects below instance
            data['form'].update({'instance_id': wizard.instance_id.id,})
            data['form'].update({'instance_ids': [wizard.instance_id.id] + [x.id for x in wizard.instance_id.child_ids]})
        period_name = ''
        if wizard.period_id:
            data['form'].update({'period_id': wizard.period_id.id})
            period_name = strftime('%Y%m', strptime(wizard.period_id.date_start, '%Y-%m-%d'))
        if wizard.fiscalyear_id:
            data['form'].update({'fiscalyear_id': wizard.fiscalyear_id.id})
        data['form'].update({'selection': wizard.selection})

        data['target_filename_suffix'] = "%s_%s_%s" % (
            wizard.instance_id and wizard.instance_id.code or '',  # instance code
            wizard.period_id and wizard.period_id.date_start.replace('-', '')[:6] or '',  # period date
            strftime('%y%m%d%H%M%S'),  # timestamp of extractions
        )
        data['target_filename'] = data['target_filename_suffix']
        if not data['target_filename'].startswith('OCBA'):
            data['target_filename'] = 'OCBA_' + data['target_filename']

        return {'type': 'ir.actions.report.xml', 'report_name': 'hq.ocba', 'datas': data}

ocba_export_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
