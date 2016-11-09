SALE_ORDER_STATE_SELECTION = [('draft', 'Draft'),
                              ('waiting_date', 'Waiting Schedule'),
                              ('validated', 'Validated'),
                              ('sourced', 'Sourced'),
                              ('manual', 'Confirmed'),
                              ('progress', 'Confirmed'),
                              ('shipping_except', 'Shipping Exception'),
                              ('invoice_except', 'Invoice Exception'),
                              ('split_so', 'Split'),
                              ('done', 'Closed'),
                              ('cancel', 'Cancelled'),
                              ('rw', 'RW'),
                              ]

SALE_ORDER_LINE_STATE_SELECTION = [('draft', 'Draft'),
                                   ('sourced', 'Sourced'),
                                   ('confirmed', 'Confirmed'),
                                   ('done', 'Done'),
                                   ('cancel', 'Cancelled'),
                                   ('exception', 'Exception'),
                                   ]

SALE_ORDER_SPLIT_SELECTION = [('original_sale_order', 'Original'),
                              ('esc_split_sale_order', '1'), # ESC
                              ('stock_split_sale_order', '2'), # from Stock
                              ('local_purchase_split_sale_order', '3')] # Local Purchase

import sale
import report
import wizard
import res_partner
