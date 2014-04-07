# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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
from tools.translate import _

import base64
import StringIO
import csv

class wizard_import_mapping(osv.osv_memory):
    _name = "wizard.import.mapping"

    _columns = {
        'import_file': fields.binary("CSV File", required=True),
    }

    def import_account_mappings(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        account_obj = self.pool.get('account.account')
        instance_obj = self.pool.get('msf.instance')
        # using the "active model" variable to determine which mapping is uploaded
        if 'active_model' in context:
            mapping_obj = self.pool.get(context['active_model'])
        else:
            raise osv.except_osv(_('Error'), _('The object to be imported is undertermined!'))

        # Delete previous lines
        mapping_ids = mapping_obj.search(cr, uid, [], context=context)
        mapping_obj.unlink(cr, uid, mapping_ids, context=context)

        for wizard in self.browse(cr, uid, ids, context=context):
            import_file = base64.decodestring(wizard.import_file)
            import_string = StringIO.StringIO(import_file)
            import_data = list(csv.reader(import_string, quoting=csv.QUOTE_ALL, delimiter=','))

            if context['active_model'] == 'account.export.mapping':
                for line in import_data[1:]:
                    if len(line) == 2:
                        account_ids = account_obj.search(cr, uid, [('code', '=', line[0])], context=context)
                        if len(account_ids) > 0:
                            mapping_obj.create(cr, uid, {'account_id': account_ids[0],
                                                         'mapping_value': line[1]}, context=context)
                        else:
                            raise osv.except_osv(_('Error'), _('The account code %s is not in the database!') % line[0])
                            break
            elif context['active_model'] == 'country.export.mapping':
                for line in import_data[1:]:
                    if len(line) == 2:
                        instance_ids = instance_obj.search(cr, uid, [('code', '=', line[0])], context=context)
                        if len(instance_ids) > 0:
                            mapping_obj.create(cr, uid, {'instance_id': instance_ids[0],
                                                         'mapping_value': line[1]}, context=context)
                        else:
                            raise osv.except_osv(_('Error'), _('The instance code %s is not in the database!') % line[0])
                            break

        return {'type': 'ir.actions.act_window_close'}

wizard_import_mapping()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
