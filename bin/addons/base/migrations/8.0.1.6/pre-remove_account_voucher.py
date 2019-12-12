
def migrate(cr, version):
    if not cr.table_exists('ir_module_module'):
        return

    cr.execute("update ir_module_module set state='uninstalled' where name in ('threshold_value', 'procurement_report')")
    cr.execute("update wkf_transition set sequence = id where act_to in (select id from wkf_activity where wkf_id = (select id from wkf where name='procurement.order.basic'))")
    return True
