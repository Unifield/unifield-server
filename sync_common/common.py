from osv import osv

class common():
    MODELS_TO_IGNORE=[
        'ir.%',
        r'/^sync[_.]client\./',
        r'/^sync[_.]server\./',
        'res.widget',
        #'res.currency'
    ]

    MODELS_TO_IGNORE_OLD=[
                        'ir.actions.wizard',
                        'ir.actions.act_window.view',
                        'ir.report.custom',
                        'ir.ui.menu',
                        'ir.actions.act_window.view',
                        'ir.actions.wizard',
                        'ir.report.custom',
                        'ir.ui.menu',
                        'ir.ui.view',
                        'ir.sequence',
                        'ir.actions.url',
                        'ir.values',
                        'ir.report.custom.fields',
                        'ir.cron',
                        'ir.actions.report.xml',
                        'ir.property',
                        'ir.actions.todo',
                        'ir.sequence.type',
                        'ir.actions.act_window',
                        'ir.module.module',
                        'ir.ui.view',
                        'ir.module.repository',
                        'ir.model',
                        'ir.model.data',
                        'ir.model.fields',
                        'ir.model.access',
                        'ir.ui.view_sc', 
                        'ir.config_parameter',
                        
                        'sync.client.rule',
                        'sync.client.push.data.information',  
                        'sync.client.update_to_send', 
                        'sync.client.update_received', 
                        'sync.client.entity',         
                        'sync.client.sync_server_connection', 
                        'sync.client.message_rule',
                        'sync.client.message_to_send',
                        'sync.client.message_received',
                        'sync.client.message_sync',  
                        'sync.client.write_info',
                        
                        'res.widget',
                        
                        #'res.currency'
                      ]

    XML_ID_TO_IGNORE = [
                    'main_partner',
                    'main_address',
                    'main_company', 
                        ]

    def compile_models_to_ignore(self):
        MODELS_TO_IGNORE_PATTERNS = []
        MODELS_TO_IGNORE_REGEXPS = []
        MODELS_TO_IGNORE_IS = []
        for model in self.MODELS_TO_IGNORE:
            if model[0] == '/' and model[-1] == '/':
                MODELS_TO_IGNORE_REGEXPS.append(model[1:-1])
            elif model.find('%') >= 0 or model.find('_') >= 0:
                MODELS_TO_IGNORE_PATTERNS.append(model)
            else:
                MODELS_TO_IGNORE_IS.append(model)
        self.MODELS_TO_IGNORE = [('model','not in',MODELS_TO_IGNORE_IS)]
        self.MODELS_TO_IGNORE.extend([('model','not like',pattern) for pattern in MODELS_TO_IGNORE_PATTERNS])
        self.MODELS_TO_IGNORE.extend([('model','!~',regexp) for regexp in MODELS_TO_IGNORE_REGEXPS])

common().compile_models_to_ignore()

class rules_checks(osv.osv):

    def syntax(self, expr, result=None):
        try: result=eval(expr or 'None')
        except: return False
        else: return True

    def fields(self, cr, uid, model, fields, context=None):
        """
            @return  : the list of unknown fields or unautorized field
        """
        bad_field = []
        fields_ref = self.pool.get(model).fields_get(cr, uid, context=context)
        for field in fields:
            if field == "id":
                continue
            if '.id' in field:
                bad_field.append(field)
                continue
            
            part = field.split('/')
            if len(part) > 2 or (len(part) == 2 and part[1] != 'id') or not fields_ref.get(part[0]):
                bad_field.append(field)
        
        return bad_field

    def conflict(self, cr, uid, update, context=None):
        values = eval(update.values)
        fields = eval(update.fields)
        xml_id = values[fields.index('id')]
        ir_data = self.pool.get('ir.model.data').get_ir_record(cr, uid, xml_id, context=context)
        if not ir_data: #no ir.model.data => no record in db => no conflict
            return False
        if not ir_data.sync_date: #never synced => conflict
            return True
        if not ir_data.last_modification: #never modified not possible but just in case
            return False
        if ir_data.sync_date < ir_data.last_modification: #modify after synchro conflict
            return True
        if update.version <= ir_data.version: #not a higher version conflict
            return True
        return False
 
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

