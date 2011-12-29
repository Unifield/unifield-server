ORDER_PRIORITY = [('emergency', 'Emergency'), 
                  ('normal', 'Normal'), 
                  ('priority', 'Priority'),]

ORDER_CATEGORY = [('medical', 'Medical'), 
                  ('log', 'Logistic'), 
                  ('service', 'Service'), 
                  ('other', 'Other')]

SALE_ORDER_STATE_SELECTION = [('procurement', 'Internal Supply Requirement'),
                              ('draft', 'Quotation'),
                              ('waiting_date', 'Waiting Schedule'),
                              ('manual', 'Manual In Progress'),
                              ('progress', 'In Progress'),
                              ('shipping_except', 'Shipping Exception'),
                              ('invoice_except', 'Invoice Exception'),
                              ('done', 'Done'),
                              ('cancel', 'Cancelled'),
                              ]

import sale
import report
