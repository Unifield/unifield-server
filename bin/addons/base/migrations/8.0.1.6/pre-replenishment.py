
def migrate(cr, version):
    if not cr.table_exists('ir_module_module'):
        return

    cr.execute("update ir_module_module set state='uninstalled' where name in ('threshold_value', 'procurement_report')")
    if cr.column_exists('wkf_transition', 'sequence'):
        cr.execute("update wkf_transition set sequence = id where act_to in (select id from wkf_activity where wkf_id = (select id from wkf where name='procurement.order.basic'))")
    cr.execute("delete from ir_ui_menu where id in (select res_id from ir_model_data where module in ('threshold_value', 'procurement_report') and model='ir.ui.menu')")
    return True
