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
{
    'name': 'MSF Budget Management',
    'version': '1.0',
    'category': 'Generic Modules/Accounting',
    'author': 'MSF, TeMPO Consulting',
    'developer': 'Matthieu Dietrich',
    'depends': ['res_currency_tables',"msf_audittrail","msf_instance"],
    'description': '''
        Budget view
    ''',
    'init_xml': [],
    'update_xml': [
        'security/ir.model.access.csv',
        'msf_budget_sequence.xml',
        'msf_budget_report.xml',
        'wizard/wizard_budget_monthly.xml',
        'msf_budget_view.xml',
        'msf_budget_workflow.xml',
        'data/msf_budget_decision_moment_data.xml',
        'wizard/wizard_budget_criteria_export_view.xml',
        'wizard/wizard_actual_export_view.xml',
        'wizard/wizard_budget_summary.xml',
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
    #    'certificate': 'certificate',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
