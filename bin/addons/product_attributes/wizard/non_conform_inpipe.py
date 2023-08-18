# -*- coding: utf-8 -*-

from osv import osv
from osv import fields


class non_conform_inpipe(osv.osv_memory):
    _name = 'non.conform.inpipe'

    _columns = {
        'name': fields.char('Report Name', size=128),
        'include_pipe': fields.boolean('Include in-pipe quantity'),
    }



    def print_excel(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        and print the report in Excel format.
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        wiz = self.browse(cr, uid, ids[0], context=context)

        return {
            'type': 'ir.actions.report.xml',
            'report_name': wiz.name,
            'context': context,
        }

non_conform_inpipe()
