from osv import osv, fields, orm
import pooler
import logging

class wkf_witm_trans(osv.osv):
    """
    Create an openerp model to represent the wkf_witm_trans table so it can be synchronised
    with the sync engine [UF-2330].
    """
    _name = 'workflow.witm_trans'
    _table = 'wkf_witm_trans'
    _columns = {
        'inst_id': fields.many2one('workflow.instance', string='Workflow Instance'),
        'trans_id': fields.many2one('workflow.transition', string='Workflow Transition'),
    }
    
    def _id_column_missing(self, cr):
        """
        Returns True if the id column is missing from the wkf_witm_trans table
        indicating that this is the first time this module has been installed
        """
        cr.execute("""\
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name=%s AND column_name='id';""", [self._table])
        
        return not cr.fetchone()
    
    def generate_sd_refs(self, cr, uid, mode, context={}):
        """
        Set in __openerp__.py functions section to be called after object pool is fully loaded.
        If this is the first time this module is installed (wkf_witm_trans.id column missing)
        this script will generate an sd ref for each record for this object 
        """ 
        if self._id_column_missing(cr):
            all_ids = self.search(cr, 1, [])
            self.get_sd_ref(cr, 1, all_ids)
        
    def create(self, cr, uid, data, context=None):
        """
        Generate SD REF on creation
        """
        new_id = super(wkf_witm_trans, self).create(cr, uid, data, context=context)
        self.get_sd_ref(cr, 1, [new_id])
        return new_id

    def init(self, cr):
        """ 
        On server startup create sd refs for all existing records, and create (if doesn't exist already) 
        wkf_witm_trans.id column and wkf_witm_trans_id_seq table
        """
        if self._id_column_missing(cr):
            
            logging.getLogger(self._name).info("Migrate %s table to OpenERP model table (UF-2330)" % self._table)
            cr.execute("""\
                -- Create column id
                ALTER TABLE "public"."%(table)s" ADD COLUMN "id" INTEGER;
                CREATE SEQUENCE "public"."%(table)s_id_seq";
                UPDATE %(table)s SET id = nextval('"public"."%(table)s_id_seq"');
                ALTER TABLE "public"."%(table)s"
                ALTER COLUMN "id" SET DEFAULT nextval('"public"."%(table)s_id_seq"');
                ALTER TABLE "public"."%(table)s"
                ALTER COLUMN "id" SET NOT NULL;
                ALTER TABLE "public"."%(table)s" ADD UNIQUE ("id");
                ALTER TABLE "public"."%(table)s" DROP CONSTRAINT "%(table)s_id_key" RESTRICT;
                ALTER TABLE "public"."%(table)s" ADD PRIMARY KEY ("id");""" % {'table':self._table})
    
wkf_witm_trans()
