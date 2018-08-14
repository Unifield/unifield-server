# -*- coding: utf-8 -*-

from osv import osv, fields
import csv
from mx import DateTime
from tempfile import TemporaryFile
import time
import base64
import threading
import pooler
import logging

class import_analytic_lines(osv.osv_memory):
    _name = 'data_finance.import_lines'
    _description = 'Import Analytic Lines'

    _columns = {
        'state': fields.selection([('draft', 'Draft'), ('temp','Temp'), ('hard', 'Hard')], 'Register Line State', required=True),
        'date_format': fields.selection([('%d/%m/%Y', 'd/m/Y')], 'Date Format', required=True),
        'relative': fields.boolean('Dates relative to 01/01 ?'),
        'file': fields.binary('File', required=True),
        'config_logo': fields.binary('Image', readonly='1'),
    }

    def _get_image(self, cr, uid, context=None):
        return self.pool.get('ir.wizard.screen')._get_image(cr, uid)

    _defaults = {
        'relative': lambda *a: True,
        'config_logo': _get_image,
        'date_format': lambda *a: 'd/m/Y',
        'state': lambda *a: 'temp',
    }

    def _import(self, dbname, uid, ids, context=None):
        if not context:
            context = {}
        cr = pooler.get_db(dbname).cursor()

        curr_obj = self.pool.get('res.currency')
        journal_obj = self.pool.get('account.journal')
        account_obj = self.pool.get('account.account')
        data_obj = self.pool.get('ir.model.data')
        period_obj = self.pool.get('account.period')
        reg_obj = self.pool.get('account.bank.statement')

        parent_account = data_obj.get_object_reference(cr, uid, 'msf_chart_of_account', '535')[1]
        type_cash = data_obj.get_object_reference(cr, uid, 'account','account_type_cash_moves')[1]
        anal_bank = data_obj.get_object_reference(cr, uid, 'msf_chart_of_account', 'bank_analytic_journal')[1]

        obj = self.read(cr, uid, ids[0])
        fileobj = TemporaryFile('w+')
        fileobj.write(base64.decodestring(obj['file']))
        fileobj.seek(0)

        reader = csv.reader(fileobj, quotechar='"', delimiter=',')

        curr_name = {}
        journal = {}

        row = reader.next()
        max_date = False
        error = []
        total = 1
        for row in reader:
            total+= 1
            curr_name[row[1]] = True
            try:
                date = DateTime.strptime(row[6], obj['date_format'])
            except ValueError:
                error.append('Line %s, error in date %s'%(total, row[6]))
                continue
            if not max_date or date > max_date:
                max_date = date

        if obj['relative']:
            max_date = max_date+DateTime.RelativeDateTime(months=DateTime.now().month-1)

        if max_date.year != DateTime.now().year:
            create_period_obj = self.pool.get('account.period.create')
            new_fy = create_period_obj.create(cr, uid, {'fiscalyear': 'next'}, context=context)
            create_period_obj.account_period_create_periods(cr, uid, new_fy, context={})


        for curr in curr_name:
            curr_id = curr_obj.search(cr, uid, [('name', '=like', curr), ('active', 'in', ['t', 'f'])])
            if curr_id:
                curr_name[curr] = curr_id[0]
                curr_data = curr_obj.read(cr, uid, curr_id[0], ['active', 'rate'])
                data = {}
                if not curr_data['rate']:
                    if curr == 'MMK':
                        rate = 8.15416
                    else:
                        rate = 1.34
                    data['rate_ids'] = [(0, 0, {'name': time.strftime('%Y-01-01'), 'rate': rate})]
                if not curr_data['active']:
                    data['active'] = True
                if data:
                    curr_obj.write(cr, uid, curr_id[0], data)
            else:
                error.append("Currency %s does not exist"%(curr,))

            jids = journal_obj.search(cr, uid, [('currency', '=', curr_id[0]),
                                                ('type', '=', 'bank'),
                                                ('is_current_instance', '=', True)])
            if not jids:
                cr.execute('SELECT max(code) from account_account where parent_id=%s', (parent_account,))

                code = int(cr.fetchone()[0])+1
                acc_id = account_obj.create(cr, uid, {
                    'code': code,
                    'name': 'Bank in %s'%(curr,),
                    'parent_id': parent_account,
                    'type': 'liquidity',
                    'user_type': type_cash,
                    'activation_date': time.strftime('%Y-01-01'),
                })

                jid = journal_obj.create(cr, uid, {
                    'code': 'BNK-%s-1'%(curr,),
                    'name': 'Bank %s'%(curr,),
                    'type': 'bank',
                    'currency': curr_id[0],
                    'analytic_journal_id': anal_bank,
                    'default_debit_account_id': acc_id,
                    'default_credit_account_id': acc_id,
                })
                journal[curr] = jid
            else:
                journal[curr] = jids[0]

        creation_obj = self.pool.get('wizard.register.creation')

        creation_obj = self.pool.get('wizard.register.creation')

        jan = DateTime.now()+DateTime.RelativeDateTime(month=1, day=1)
        while jan.strftime('%Y-%m-%d') <= max_date.strftime('%Y-%m-%d'):
            period = period_obj.search(cr, uid, [('date_start', '=', jan.strftime('%Y-%m-%d'))])
            if period_obj.read(cr, uid, period[0], ['state'])['state'] == 'created':
                period_obj.action_set_state(cr, uid, period, context={'state': 'draft'})
            try:
                creation_id = creation_obj.create(cr, uid, {'period_id': period[0]}, context=context)
                creation_obj.button_confirm_period(cr, uid, [creation_id])
            except osv.except_osv:
                pass
            else:
                creation_obj.button_create_registers(cr, uid, [creation_id])

            jan += DateTime.RelativeDateTime(months=1)

        fileobj.seek(0)
        reader = csv.reader(fileobj, quotechar='"', delimiter=',')
        row = reader.next()

        register_id = {}
        cc = {}
        fp = {}
        gl_acc = {}
        analytic_obj = self.pool.get('account.analytic.account')
        st_line_obj = self.pool.get('account.bank.statement.line')
        distri_obj = self.pool.get('analytic.distribution')
        i = 0
        created_line = []
        for row in reader:
            if row[1] not in curr_name:
                continue
            if i%101 == 0:
                logging.getLogger('import analytic').info('Item: %s/%s'%(i,total))
            try:
                date = DateTime.strptime(row[6], obj['date_format'])
            except ValueError:
                continue
            if obj['relative']:
                date += DateTime.RelativeDateTime(months=DateTime.now().month-1)
            key_reg = '%s-%s'%(row[1], date.strftime('%m-%Y'))
            if key_reg not in register_id:
                p_ids = period_obj.search(cr, uid, [('date_start', '=', date.strftime('%Y-%m-01'))])
                reg_id = reg_obj.search(cr, uid, [('journal_id', '=', journal[row[1]]), ('period_id', '=', p_ids[0])])
                if not reg_id:
                    logging.getLogger('import analytic').info("No register: journal: %s, period: %s, date: %s"%(journal[row[1]], p_ids[0], date.strftime('%Y-%m-01')))
                    continue
                register_id[key_reg] = reg_id[0]
                reg_data = reg_obj.read(cr, uid, reg_id[0], ['state', 'prev_reg_id'])
                if reg_data['state'] == 'draft':
                    if not reg_data['prev_reg_id']:
                        reg_obj.write(cr, uid, reg_data['id'], {'balance_start': 44.56})
                    reg_obj.open_register(cr, uid, reg_data['id'])

            if row[2] not in cc:
                acc_id = analytic_obj.search(cr, uid, [('category', '=', 'OC'), ('code', '=like', row[2])])
                cc[row[2]] = acc_id[0]
            if row[3] not in fp:
                acc_id = analytic_obj.search(cr, uid, [('category', '=', 'FUNDING'), ('code', '=like', row[3])])
                fp[row[3]] = acc_id[0]
            account = row[4].split(' ')[0]
            if account not in gl_acc:
                acc_id = account_obj.search(cr, uid, [('code','=like',account)])
                gl_acc[account] = acc_id[0]

            distri_id = distri_obj.create(cr, uid, {
                'cost_center_lines': [(0, 0, {'analytic_id': cc[row[2]],'percentage': 100, 'currency_id': curr_name[row[1]]})],
                'funding_pool_lines': [(0, 0, {'analytic_id': fp[row[3]], 'percentage': 100, 'cost_center_id': cc[row[2]], 'currency_id': curr_name[row[1]]})],
            })
            st_line_id = st_line_obj.create(cr, uid, {
                'statement_id': register_id[key_reg],
                'date': date,
                'name': row[7],
                'amount': row[0].replace(',','.'),
                'account_id': gl_acc[account],
                'analytic_distribution_id': distri_id,
            })
            i+=1
            created_line.append(st_line_id)
            if len(created_line) == 100 and obj['state'] in ('temp', 'hard'):
                st_line_obj.posting(cr, uid, created_line, obj['state'])
                created_line = []


        if created_line and obj['state'] in ('temp', 'hard'):
            st_line_obj.posting(cr, uid, created_line, obj['state'])

        summary = '''Analytic lines Import Summary:
Nb register lines: %s
'''%(i,)
        if error:
            summary += '''\nError:
   %s'''%("\n   ".join(error))

        request_obj = self.pool.get('res.request')
        req_id = request_obj.create(cr, uid, {
            'name': 'Analytic lines Import',
            'act_from': uid,
            'act_to': uid,
            'body': summary
        })
        request_obj.request_send(cr, uid, [req_id])
        cr.commit()
        cr.close(True)

    def import_csv(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        new_id = self.pool.get('data_finance.import_lines.result').create(cr, uid, {}, context=context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'data_finance.import_lines.result',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': new_id,
            'target': 'new',
        }

import_analytic_lines()

class import_analytic_lines_result(osv.osv_memory):
    _name = 'data_finance.import_lines.result'
    _description = 'Import Analytic Lines Result'

    _columns = {
        'config_logo': fields.binary('Image', readonly='1'),
    }

    def _get_image(self, cr, uid, context=None):
        return self.pool.get('ir.wizard.screen')._get_image(cr, uid)

    _defaults = {
        'config_logo': _get_image,
    }

    def ok(self, cr, *a, **b):
        return {'type': 'ir.actions.act_window_close'}
import_analytic_lines_result()
