# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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


import time
from osv import fields
from osv import osv
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from service.web_services import report_spool
from tools.translate import _



class export_report_stopped_products(osv.osv):

	_name = 'export.report.stopped.products'

	_columns = {
		'name': fields.datetime(string='Generated On', readonly=True),
		'state': fields.selection(
			[('draft', 'Draft'),
			('in_progress', 'In Progress'),
			('ready', 'Ready')],
			string='State',
			readonly=True,
		),
	}

	_defaults = {
		'state': lambda *a: 'draft',
	}


	def generate_report(self, cr, uid, ids, context=None):
		'''
		Generate a report of stopped products
		Method is called by button on XML view (form)
		'''
		attachment_obj = self.pool.get('ir.attachment')
		prod_obj = self.pool.get('product.product')

		res = {}
		for report in self.browse(cr, uid, ids, context=context):
			# get ids of all products :
			product_ids = prod_obj.search(cr, uid, [], context=context)
			if not product_ids:
				continue

			# state of report is in progress :
			self.write(cr, uid, [report.id], {
				'name': time.strftime('%Y-%m-%d %H:%M:%S'), 
				'state': 'in_progress'
			}, context=context)


			datas = {
				'ids': [report.id],
				'lines': product_ids,
			}

			# export datas :
			report_name = "stopped.products.xls"
			attachment_name = "stopped_products_report_%s.xls" % time.strftime('%d-%m-%Y_%Hh%M')
			rp_spool = report_spool()
			res_export = rp_spool.exp_report(cr.dbname, uid, report_name, ids, datas, context)
			file_res = {'state': False}
			while not file_res.get('state'):
				file_res = rp_spool.exp_report_get(cr.dbname, uid, res_export)
				time.sleep(0.5)

			# attach report to the right panel :
			attachment_obj.create(cr, uid, {
				'name': attachment_name,
				'datas_fname': attachment_name,
				'description': "Stopped products",
				'res_model': 'export.report.stopped.products',
				'res_id': ids[0],
				'datas': file_res.get('result'),
			}, context=context)

			# state is now 'ready' :
			self.write(cr, uid, ids, {'state': 'ready'}, context= context)

			res = {
			    'type': 'ir.actions.act_window',
			    'res_model': self._name,
			    'view_type': 'form',
			    'view_mode': 'form,tree',
			    'res_id': report.id,
			    'context': context,
			    'target': 'same',
			}

		if not res:
			raise osv.except_osv(
				_('Error'),
				_("Nothing to generate")
			)

		return res



export_report_stopped_products()




class parser_report_stopped_products_xls(report_sxw.rml_parse):
	'''
	To parse our mako template for stopped products
	'''
	def __init__(self, cr, uid, name, context=None):
		super(parser_report_stopped_products_xls, self).__init__(cr, uid, name, context=context)

		# localcontext allows you to call methods inside mako file :
		self.localcontext.update({
			'time': time,
		})




class report_stopped_products_xls(SpreadsheetReport):

	def __init(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
		super(report_stopped_products_xls, self).__init__(
			name,
			table,
			rml=rml,
			parser=parser,
			header=header,
			store=store
		)

		def create(self, cr, uid, ids, data, context=None):
			a = super(report_stopped_products_xls, self).create(cr, uid, ids, data, context=context)
			return (a[0], 'xls')



report_stopped_products_xls(
	'report.stopped.products.xls',
	'export.report.stopped.products',
	'addons/msf_tools/report/report_stopped_products_xls.mako',
	parser=parser_report_stopped_products_xls,
	header='internal',
)
