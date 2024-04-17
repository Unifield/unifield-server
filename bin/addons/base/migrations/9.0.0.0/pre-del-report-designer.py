def migrate(cr, version):
    if not cr.table_exists('ir_module_module'):
        return

    cr.execute("delete from ir_ui_menu where id in (select res_id from ir_model_data where name='base_report_designer_menu_action_report_designer_wizard')")
    cr.execute("delete from ir_act_window where id in (select res_id from ir_model_data where name in ('base_report_designer_action_view_base_report_sxw', 'base_report_designer_action_report_designer_installer', 'base_report_designer_action_report_designer_wizard'))")
    cr.execute("update ir_module_module set state='uninstalled' where name ='base_report_designer'")
    return True

