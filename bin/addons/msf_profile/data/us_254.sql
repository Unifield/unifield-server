delete from account_analytic_line where id in (select res_id from ir_model_data where module='sd' and name='c2ee5ce1-cbc3-11e4-bc03-28d24497557a/account_analytic_line/768');
delete from account_move_line where id in (select res_id from ir_model_data where module='sd' and name='c2ee5ce1-cbc3-11e4-bc03-28d24497557a/account_move_line/1133');
delete from account_move_line where id in (select res_id from ir_model_data where module='sd' and name='c2ee5ce1-cbc3-11e4-bc03-28d24497557a/account_move_line/1134');
