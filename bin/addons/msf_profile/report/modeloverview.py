# -*- coding: utf-8 -*-

from report import report_sxw
from osv import fields
import tools

class modeloverview(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(modeloverview, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'listmodules': self.listmodules,
            'getdb': self.getdb,
            'get_sql_constraints': self.get_sql_constraints,
            'get_constraints': self.get_constraints,
            'has_sql_constraints': self.has_sql_constraints,
            'has_constraints': self.has_constraints,
            'gethelp': self.gethelp,
            'getdefault': self.getdefault,
            'isfun': self.isfun,
            'getsortedfields': self.getsortedfields,
            'setlinkname': self.setlinkname,
            'makelink': self.makelink,
            'makeselcomment': self.makeselcomment,
            'is_inherits': self.is_inherits,
            'get_inherits': self.get_inherits,
            "set_bold": self.set_bold,
        })
        self.num = 4
        self.modulepos = {}

    def set_bold(self, field):
        tag = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
        if not field.required:
            return ('%sspan'%tag,{})
        return ('%sspan'%tag,{'%sstyle-name'%tag: 'parabold'})


    def setlinkname(self, name):
        tag = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
        tagxlink = "{http://www.w3.org/1999/xlink}"
        return ('%sa'%tag, {'%shref'%tagxlink: '#%s'%(name)})

    def makelink(self, model):
        tag = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
        if not self.modulepos.get(model.model):
            return ('%snamed-range'%tag, {})
        return ('%snamed-range'%tag, {
                '%sname'%tag: model.model,
                '%sbase-cell-address'%tag: '$Feuille1.$A$%s'%(self.modulepos.get(model.model)),
                '%scell-range-address'%tag: '$Feuille1.$A$%s'%(self.modulepos.get(model.model)),
                })

    def getsortedfields(self, fields):
        if not fields:
            self.num += 3
            return []

        self.modulepos[fields[0].model_id.model] = self.num
        self.num += len(fields)+3

        return sorted(fields, cmp=lambda x,y: cmp(x.name, y.name))

    def makeselcomment(self, field):
        if field.ttype not in ('selection', 'reference'):
            return []
        ret = []
        col = self.pool.get(field.model_id.model)._columns.get(field.name)
        selec = self.getcall(col.selection, self.pool.get(field.model_id.model))
        if selec == "??":
            selec=[('??','??')]
        for elem in selec:
            ret.append(u"%s → %s"%(tools.ustr(elem[0]), tools.ustr(elem[1])))
        return ret

    def isfun(self, model, field):
        obj_col = self.pool.get(model)._columns.get(field)
        if not obj_col or not obj_col._properties:
            return False
        if isinstance(obj_col, fields.related):
            return "related"
        attr = []
        if obj_col._fnct_search:
            attr.append("with search")
        if obj_col.store:
            if isinstance(obj_col.store, dict):
                attr.append("store=trigger")
            else:
                attr.append("store=True")
        if obj_col._fnct_inv:
            attr.append("with fnct_inv")
        return "function %s"%(", ".join(attr), )


    def getdefault(self, model, field):
        dflt = self.pool.get(model)._defaults.get(field.name)
        if not dflt:
            return False
        if field.ttype == 'binary':
            return '...'
        value = self.getcall(dflt, self.pool.get(model))
        if field.ttype == 'text' and value and len(value) > 100:
            return value[0:100]+'...'
        return value


    def gethelp(self,model,field):
        obj_col = self.pool.get(model)._columns.get(field,object)
        if hasattr(obj_col,'help'):
            return getattr(obj_col, 'help')
        return ""

    def listmodules(self):
        obj = self.pool.get('ir.module.module')
        ids = obj.search(self.cr, self.uid, [('state', 'in', ['installed', 'to upgrade', 'to install'])])
        ret = []
        for m in obj.read(self.cr, self.uid, ids, ['name']):
            ret.append(m['name'])
        self.num += len(ret)
        return ret

    def is_inherits(self,obj):
        modobj = self.pool.get(obj)
        return hasattr(modobj, '_inherits') and modobj._inherits

    def get_inherits(self,obj):
        modobj = self.pool.get(obj)
        if not hasattr(modobj, '_inherits') or not modobj._inherits:
            return []
        ret = modobj._inherits.items()
        self.num += len(ret)+1
        return ret

    def has_constraints(self, obj):
        modobj = self.pool.get(obj)
        if not hasattr(modobj, '_constraints') or not modobj._constraints:
            return False
        return True

    def has_sql_constraints(self, obj):
        modobj = self.pool.get(obj)
        if not hasattr(modobj, '_sql_constraints') or not modobj._sql_constraints:
            return False
        return True

    def get_constraints(self, obj):
        modobj = self.pool.get(obj)
        if not hasattr(modobj, '_constraints'):
            return []
        ret = []
        for const in  modobj._constraints:
            ret.append("%s : %s"%(const[0].func_name,self.getcall(const[1], modobj)))
        if ret:
            self.num += len(ret)+1
        return ret

    def get_sql_constraints(self, obj):
        modobj = self.pool.get(obj)
        if not hasattr(modobj, '_sql_constraints'):
            return []
        ret = []
        for const in  modobj._sql_constraints:
            ret.append("%s : %s"%(const[1],self.getcall(const[2], modobj)))
        if ret:
            self.num += len(ret)+1
        return ret

    def getcall(self,c, obj):
        if callable(c):
            try:
                return c(obj, self.cr, self.uid, [])
            except:
                return "??"
        return c

    def getdb(self):
        return self.cr.dbname

report_sxw.report_sxw('report.msf_profile.overview_ods2','ir.model','addons/msf_profile/report/modeloverview.ods',parser=modeloverview,header=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
