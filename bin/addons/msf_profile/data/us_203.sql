update ir_model_data set last_modification=now() , touched='[''name'']' where module='sd' and model='financing.contract.donor';
update ir_model_data set last_modification=now() , touched='[''name'']' where module='sd' and model='financing.contract.format.line';
update ir_model_data set last_modification=now() , touched='[''format_name'']' where module='sd' and model='financing.contract.format';
