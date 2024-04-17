#!/usr/bin/env python

import psycopg2
import sys
import csv

if len(sys.argv) < 3:
    print('%s dbname oc' % sys.argv[0])
    sys.exit(1)

dbname = sys.argv[1]
oc = sys.argv[2]

if oc not in ('OCP', 'OCA', 'OCG', 'OCB'):
    print('OC unknown')
    sys.exit(1)

db_host = '127.0.0.1'

conn = psycopg2.connect(database=dbname)
cr = conn.cursor()

line_number = 1

values_mapping = {
    'Yes': 't',
    'Kit/Module': 'kit',
    'Make to Order': 'make_to_order',
    'Service with Reception': 'service_recep',
    '': '',
}
with open('ud_default_value.csv', 'r', newline='') as f:
    c = csv.reader(f, quotechar='"', delimiter=',')
    for line in c:
        line_number += 1
        if not line or line[1] != oc:
            continue
        nomen = line[3][5:].strip()
        all_nom = nomen.split('|')
        level = 1
        parent_id = False
        error = False

        if line[4] not in values_mapping:
            print('Line number %s, value %s not found' % (line_number, line[4]))
            break
        for nom in all_nom:
            nom = nom.strip()[0:63]
            if nom:
                cond = ''
                params = [nom.strip(), level]
                if parent_id:
                    cond = ' and n.parent_id in %s'
                    params.append(tuple(parent_id))
                    params[0] = '%%%s' % nom

                cr.execute("""
                    select
                        n.id
                    from
                        product_nomenclature n
                    left join ir_translation t on t.lang='en_MF' and t.name='product.nomenclature,name' and t.res_id = n.id
                    where
                        coalesce(t.value, n.name) like %s and
                        n.level=%s
                    """+cond, tuple(params)) # not_a_user_entry
                if not cr.rowcount:
                    print(all_nom)
                    print(str(cr.mogrify("""
                        select
                            n.id
                        from
                            product_nomenclature n
                        left join ir_translation t on t.lang='en_MF' and t.name='product.nomenclature,name' and t.res_id = n.id
                        where
                            coalesce(t.value, n.name) like %s and
                            n.level=%s 
                        """+cond, tuple(params)), 'utf8'))
                    print('Line number %s, nomen %s not found' % (line_number, nom))
                    error = True
                    break
                parent_id = [x[0] for x in cr.fetchall()]
                level += 1
        if error:
            continue
        for n_id in parent_id:
            print(str(cr.mogrify("insert into unidata_default_product_value (field, value, nomenclature) values (%s, %s, %s);", (line[2], n_id, values_mapping[line[4]])), 'utf8'))
