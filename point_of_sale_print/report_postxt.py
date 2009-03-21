# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2009 P. Christeas. All Rights Reserved
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields, osv
from string import Template
# import netsvc

class report_postxt(osv.osv):
    # no.. _inherit = "ir.actions.report.custom"
    _name = 'ir.actions.report.postxt'
    _columns = {
        'name': fields.char('Report Name', size=64, required=True, translate=True),
        'type': fields.char('Report Type', size=32, required=True),
        'model':fields.char('Object', size=64, required=True),
        'usage': fields.char('Action Usage', size=32),
        'multi': fields.boolean('On multiple doc.', help="If set to true, the action will not be displayed on the right toolbar of a form view."),
        'groups_id': fields.many2many('res.groups', 'res_groups_report_rel', 'uid', 'gid', 'Groups'),
	'printer': fields.char('Printer', size=50, help="Preferred printer for this report. Useful for server-side printing."),
	'copies': fields.integer('Copies', help="Default number of copies."),
	'txt_content': fields.text('Content of report in text'),
        }
    
    _defaults = {
        'multi': lambda *a: False,
        'type': lambda *a: 'ir.actions.report.postxt',
	'copies': lambda  *a: 1
    }
    
    def pprint(self, cr,uid, report , data, context):
	"""This should print the report using the dictionary in data
		"""
	str_report= self._do_report(report['txt_content'],data)
	print "Report:\n",str_report ,"\n\n"
	if (report['printer']):
		print "Should print this at ", report['printer']
	pass
    
    def _do_report(self, report, dict):
	sections= {}
	main_section = None
	dict2= dict
	if report.startswith('$\\'):
		cur_sec='';
		for line in report.splitlines(True):
			if line.startswith('$\\'):
				#current line
				cur_args=line[2:].strip().split(' ')
				cur_sec=cur_args[0]
				if len(cur_sec):
					sections[cur_sec]= ''
				else:
					main_section=''
				#TODO: process args[1..]
			else:
				if len(cur_sec):
					sections[cur_sec]+=line.decode('string_escape')
				else:
					main_section +=line.decode('string_escape')
		
	else:
		main_section = report.decode('string_escape')
	
	dict2.update(sections)
	return Template(main_section).substitute(dict2)



report_postxt()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: