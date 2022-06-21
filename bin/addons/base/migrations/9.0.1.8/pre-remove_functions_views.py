def migrate(cr, version):
    # serial / id from int4 to int8: delete all views and functions

    for x in [
        'account_destination_summary',
        'account_entries_report',
        'account_invoice_report',
        'analytic_entries_report',
        'documents_done_wizard',
        'finance_sync_query',
        'financing_contract_account_quadruplet_old',
        'financing_contract_account_quadruplet_view',
        'international_transport_cost_report',
        'ir_model_access_empty',
        'local_transport_cost_report',
        'pack_family_memory',
        'procurement_request_sourcing_document2',
        'purchase_order_line_allocation_report',
        'purchase_report',
        'replenishment_product_list',
        'report_account_receivable',
        'report_account_sales',
        'report_account_type_sales',
        'report_aged_receivable',
        'report_batch_recall',
        'report_invoice_created',
        'report_stock_inventory',
        'report_stock_lines_date',
        'report_stock_move',
        'res_log_report',
        'sale_report',
        'stock_report_prodlots',
        'stock_report_prodlots_virtual',
        'stock_report_tracklots',
        'stock_reserved_products',
        'sale_receipt_report',
        'threshold_value_rules_report',
        'auto_supply_rules_report',
        'min_max_rules_report',
        'order_cycle_rules_report',
        'procurement_rules_report',
    ]:
        cr.execute('drop view if exists %s' % x) # not_a_user_entry

    for x in [
        'create_ir_model_data(id integer)',
        'get_ref_uom(product integer)',
        'stock_qty(qty numeric, from_uom integer, to_uom integer)',
        'update_ir_model_data(id integer)',
        'update_stock_level() CASCADE'
    ]:
        cr.execute('drop function if exists %s' % x) # not_a_user_entry

    for table, col in [
            ('wkf_instance', 'uid'),
            ('wkf_witm_trans', 'trans_id'),
            ('wkf_witm_trans', 'inst_id'),
            ('wkf_logs', 'res_id'),
            ('wkf_logs', 'uid'),
            ('wkf_logs', 'act_id'),

    ]:
        cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" type int8' % (table, col)) # not_a_user_entry
    return True

