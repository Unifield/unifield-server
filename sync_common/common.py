from osv import osv
import tools
import logging
import StringIO
import traceback

MODELS_TO_IGNORE=[
        'ir.%',
        'sync_client.%',
        'sync_server.%',
        'res.widget%',
        'base%',
        'board%',
        'workflow%',
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

def compile_models_to_ignore():
    global MODELS_TO_IGNORE
    MODELS_TO_IGNORE_PATTERNS = []
    MODELS_TO_IGNORE_REGEXPS = []
    MODELS_TO_IGNORE_IS = []
    for model in MODELS_TO_IGNORE:
        if model[0] == '/' and model[-1] == '/':
            MODELS_TO_IGNORE_REGEXPS.append(model[1:-1])
        elif model.find('%') >= 0 or model.find('_') >= 0:
            MODELS_TO_IGNORE_PATTERNS.append(model)
        else:
            MODELS_TO_IGNORE_IS.append(model)
    MODELS_TO_IGNORE = [('model','not in',MODELS_TO_IGNORE_IS)]
    MODELS_TO_IGNORE.extend([('model','not like',pattern) for pattern in MODELS_TO_IGNORE_PATTERNS])
    MODELS_TO_IGNORE.extend([('model','!~',regexp) for regexp in MODELS_TO_IGNORE_REGEXPS])

compile_models_to_ignore()

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
def eval_poc_domain(obj, cr, uid, domain, context=None):
    if not context:
        context = {}
    
    domain_new = []
    for tp in domain:
        if isinstance(tp, tuple):
            if len(tp) != 3:
                raise osv.except_osv(_('Domain malformed : ' + tools.ustr(domain)), _('Error') )
            if isinstance(tp[2], tuple) and len(tp[2]) == 3 and isinstance(tp[2][0], basestring) and isinstance(tp[2][1], basestring) and isinstance(tp[2][2], list):
                model  = tp[2][0]
                sub_domain = tp[2][2]
                field = tp[2][1]
                sub_obj = obj.pool.get(model)
                ids_list = eval_poc_domain(sub_obj, cr, uid, sub_domain)
                if ids_list:
                    new_ids = []
                    data = sub_obj.read(cr, uid, ids_list, [field], context=context)
                    for d in data:
                        if isinstance(d[field], list):
                            new_ids.extend(d[field])
                        elif isinstance(d[field], tuple):
                            new_ids.append(d[field][0])
                        else:
                            new_ids.append(d[field])
                    ids_list = new_ids
                domain_new.append((tp[0], tp[1], ids_list))
            else:
                domain_new.append(tp)
        else:
            domain_new.append(tp)
    return obj.search(cr, uid, domain_new, context=context)

class check_common(osv.osv):
    _name = 'sync.check_common'
    
    def _check_domain(self, cr, uid, rec, context=None):
        error = False
        message = "* Domain syntax... "
        try:
            domain = eval(rec.domain)
            obj = self.pool.get(rec.model_id)
            eval_poc_domain(obj, cr, uid, domain, context=None)
        except:
            message += "failed!\n"
            error = True
        else:
            message += "pass.\n"
        finally:
            if error: message += "Example: ['|', ('name', 'like', 'external_'), ('supplier', '=', True)]\n"
        return (message, error)
    
    def _check_fields(self, cr, uid, rec, title="", context=None):
        message = title
        error = False
        try:
            included_fields = eval(rec.included_fields)
            for field in included_fields:
                base_field = field.split('/')[0]
                if not isinstance(field, str): raise TypeError
                model_ids = self._get_all_model_ids(cr, uid, rec.model_id)
                if not len(self.pool.get('ir.model.fields').search(cr, uid, [('model_id','in', model_ids),('name','=',base_field)], context=context)): raise KeyError
        except TypeError:
            message += "failed (Fields list should be a list of string)!\n"
            error = True
        except KeyError:
            message += "failed (Field %s doesn't exist for the selected model/object)!\n" % base_field
            error = True
        except:
            message += "failed! (Syntax Error : not a python expression) \n"
            error = True
        else:
            message += "pass.\n"
        finally:
            if error: message += "Example: ['name', 'order_line/product_id/id', 'order_line/product_id/name', 'order_line/product_uom_qty']\n"
            
        return (message, error)
    
    def _check_arguments(self, cr, uid, rec, title="", context=None):
        message = title
        error = False
        try:
            field_error = False
            arguments = eval(rec.arguments)
            for field in arguments:
                base_field = field.split('/')[0]
                if not isinstance(field, str): raise TypeError
                model_ids = self._get_all_model_ids(cr, uid, rec.model_id)
                if not len(self.pool.get('ir.model.fields').search(cr, uid,  [('model_id','in', model_ids),('name','=',base_field)], context=context)): 
                    field_error = field
                    raise KeyError
        except TypeError:
            message += "failed (Fields list should be a list of string)!\n"
            error = True
        except KeyError:
            message += "failed (Field %s doesn't exist for the selected model/object)!\n" % field_error
            error = True
        except:
            message += "failed! (Syntax Error : not a python expression) \n"
            error = True
        else:
            message += "pass.\n"
        finally:
            if error: message += "Example: ['name', 'order_line/product_id/id', 'order_line/product_id/name', 'order_line/product_uom_qty']\n"
            
        return (message, error)
    
    def _check_forced_values(self, cr, uid, rec, context=None):
        error = False
        message = "* Forced values syntax... "
        try:
            forced_value = eval(rec.forced_values or '{}')
            if not isinstance(forced_value, dict): raise TypeError
        except TypeError:
            message += "failed (Forced values should be a dictionnary)!\n"
            error = True
        except:
            message += "failed! (Syntax error) \n"
            error = True
        else:
            message += "pass.\n"
        finally:
            if error: message += "Example: {'field_name' : 'str_value', 'field_name' : 10, 'field_name' : True}\n"
            
        return (message, error)
    
    def _check_fallback_values(self, cr, uid, rec, context=None):
        error = False
        message = "* Fallback values syntax... "
        try:
            fallback_value = eval(rec.fallback_values or '{}')
            if not isinstance(fallback_value, dict): raise TypeError
        except TypeError:
            message += "failed (Fallback values should be a dictionnary)!\n"
            error = True
        except:
            message += "failed!\n"
            error = True
        else:
            message += "pass.\n"
        finally:
            if error: message += "Example: {'field_name/id' : 'sd.xml_id'}\n"
            # Sequence is unique
        return (message, error)

    def _check_owner_field(self, cr, uid, rec, context=None):
        if rec.direction != 'bi-private': return ('', False)
        error = False
        message = "* Owner field existence... "
        try:
            fields = []
            ir_model_fields = self.pool.get('ir.model.fields')
            model_ids = self._get_all_model_ids(cr, uid, rec.model_id)
            fields_ids = ir_model_fields.search(cr, uid, [('model_id','in', model_ids)], context=context)
            fields = ir_model_fields.browse(cr, uid, fields_ids, context=context)
            fields = [x.name for x in fields]
            if not rec.owner_field in fields: raise KeyError
        except:
            message += "failed!\n"
            message += "Please choose one of these: %s\n" % (", ".join(fields),)
            error = True
        try:
            if rec.owner_field not in eval(rec.included_fields): raise KeyError
        except:
            message += "failed!\n"
            message += "The owner field must be present in the included fields!\n"
            error = True
        if not error:
            message += "pass.\n"
        return (message, error)


    
    def _get_all_model_ids(self, cr, uid, model_name):
        def recur_get_model(model, res):
            ids = self.pool.get('ir.model').search(cr, uid, [('model','=',model._name)])
            res.extend(ids)
            for parent in model._inherits.keys():
                new_model = self.pool.get(parent)
                recur_get_model(new_model, res)
            return res
           
        model = self.pool.get(model_name)
        return recur_get_model(model, [])
            
check_common()
def _handle_error(e):
    try:
        msg = list(e)
        if e[-1] != "\n": 
            e.append("\n")
        return "".join(e)
    except: 
        return str(e) + "\n"

def c_log_error(e, logger):
    tb = StringIO.StringIO()
    traceback.print_exc(file=tb)
    error =  _handle_error(e) + tb.getvalue() 
    logger.error(error)
    return error

