# -*- encoding: utf-8 -*-
from osv import osv, fields, orm
import pooler
import xmlrpclib
import tools
import base64
import email
from tools.translate import _

def _lang_get(self, cr, uid, context={}):
    obj = self.pool.get('res.lang')
    ids = obj.search(cr, uid, [])
    res = obj.read(cr, uid, ids, ['code', 'name'], context)
    res = [(r['code'], r['name']) for r in res]
    return res + [(False, '')]

class ecommerce_partner(osv.osv):
    
    _description='ecommerce partner'
    _name = "ecommerce.partner"
    _order = "name"
    _columns = {
        'name': fields.char('Name', size=128, required=True, select=True),
        'last_name': fields.char('Last Name', size=128, required=True, select=True),
        'lang': fields.selection(_lang_get, 'Language', size=5),
        'company_name':fields.char('Company Name',size=64),
        'active': fields.boolean('Active'),
        'address': fields.one2many('ecommerce.partner.address', 'partner_id', 'Contacts'),
        'category_ids': fields.many2many('res.partner.category', 'ecommerce_partner_category_rel', 'partner_id', 'category_id', 'Categories'),
    }
    _defaults = {
        'active': lambda *a: 1,
    }
  
    def copy(self, cr, uid, id, default=None, context={}):
        name = self.read(cr, uid, [id], ['name'])[0]['name']
        default.update({'name': name+' (copy)'})
        return super(res_partner, self).copy(cr, uid, id, default, context)
       
    def name_search(self, cr, uid, name, args=None, operator='ilike', context=None, limit=80):
        if not args:
            args=[]
        if not context:
            context={}
        if name:
            ids = self.search(cr, uid, [('ref', '=', name)] + args, limit=limit, context=context)
            if not ids:
                ids = self.search(cr, uid, [('name', operator, name)] + args, limit=limit, context=context)
        else:
            ids = self.search(cr, uid, args, limit=limit, context=context)
        return self.name_get(cr, uid, ids, context)
    
    def address_get(self, cr, uid, ids, adr_pref=['default']):
        cr.execute('select type,id from ecommerce_partner_address where partner_id in ('+','.join(map(str,ids))+')')
        res = cr.fetchall()
        adr = dict(res)
               
        if res:
            default_address = adr.get('default', res[0][1])
        else:
            default_address = False
        result = {}
        for a in adr_pref:
            result[a] = adr.get(a, default_address)
      
        return result
    
    def delivery_grid(self, cr, uid, shop_id, adr_dict, context={}):

        delivery_grid_ids = []
        res_add = self.pool.get('ecommerce.partner.address')

        if(adr_dict['type'] == 'delivery'):
                address_delivery = adr_dict['type']
                add_id = adr_dict['address_id']
                 
        if (not adr_dict['type']=='delivery') and (adr_dict['type'] == 'default'):
                address_delivery = adr_dict['type']
                add_id = adr_dict['address_id']
              
        delivery_carrier = self.pool.get('delivery.carrier')
        delivery_ecommerce_car = self.pool.get('ecommerce.shop').browse(cr, uid, [shop_id])
        for i in delivery_ecommerce_car[0].delivery_ids:
            delivery_grid_ids.append(i.id)

        grid_id = self.grid_get(cr, uid, delivery_grid_ids, add_id,{}, from_web=True)       
        get_data = delivery_carrier.read(cr, uid, grid_id, ['name'], context)
        return get_data

    def grid_get(self, cr, uid, ids, contact_id, context={}, from_web=False):
      
        add_grid_list = []
        if from_web:
            contact = self.pool.get('ecommerce.partner.address').browse(cr, uid, [contact_id])[0]
            delivery_carrier = self.pool.get('delivery.carrier')
            
            if ids:
                for carrier in self.pool.get('delivery.carrier').browse(cr, uid, ids):
                 
                    for grid in carrier.grids_id:
                        
                        get_id = lambda x: x.id
                        country_ids = map(get_id, grid.country_ids)
                        state_ids = map(get_id, grid.state_ids)
                       
                        if country_ids and not contact.country_id.id in country_ids:
                            continue
                        if state_ids and not contact.state_id.id in state_ids:
                            continue
                        if grid.zip_from and (contact.zip or '')< grid.zip_from:
                            continue
                        if grid.zip_to and (contact.zip or '')> grid.zip_to:
                            continue
                        
                        add_grid_list.append(grid.id)
                    
                return add_grid_list
            
        else:    
            contact = self.pool.get('res.partner.address').browse(cr, uid, [contact_id])[0]
            for carrier in self.browse(cr, uid, ids):
                for grid in carrier.grids_id:
                    get_id = lambda x: x.id
                    country_ids = map(get_id, grid.country_ids)
                    state_ids = map(get_id, grid.state_ids)
                    if country_ids and not contact.country_id.id in country_ids:
                        continue
                    if state_ids and not contact.state_id.id in state_ids:
                        continue
                    if grid.zip_from and (contact.zip or '')< grid.zip_from:
                        continue
                    if grid.zip_to and (contact.zip or '')> grid.zip_to:
                        continue
                    return grid.id
            return False
  
        
    def delivery_get_price(self, cr, uid, grid_id, product_list, context):
         
            prd_list_ids = []
            taxes_list_ids = []
            total = 0
            weight = 0
            volume = 0
            final_tax_amt = 0
           
            tax_obj = self.pool.get('account.tax')
            for prd_ids in product_list:
                prd_list_ids.append(prd_ids['id']) 
            for prd in product_list:
                p = self.pool.get('product.product').browse(cr, uid, prd['id'])
                sub_total = round(prd['price'] * prd['quantity'])
                if not prd:
                    continue
                total  += sub_total or 0.0
                weight += (p.product_tmpl_id.weight or 0.0) * prd['quantity']
                volume += (p.product_tmpl_id.volume or 0.0) * prd['quantity']
              
                if p.taxes_id:
                    for tax in tax_obj.compute(cr, uid,p.taxes_id, prd['price'], prd['quantity'], product=prd['id']):
                        final_tax_amt += tax['amount']
                    
            get_ship_price = self.get_price_from_picking_ecommerce(cr, uid, grid_id, total, weight, volume, context)
          
            return dict(get_ship_price=get_ship_price,final_tax_amt=final_tax_amt)
   
           
    def _price_unit_default(self, cr, uid, tax_id_list, prd_list,  context={}):
        if 'check_total' in context:
            t = context['check_total']
            for l in context.get('invoice_line', {}):
                if len(l) >= 3 and l[2]:
                    tax_obj = self.pool.get('account.tax')
                    p = l[2].get('price_unit', 0) * (1-l[2].get('discount', 0)/100.0)
                    t = t - (p * l[2].get('quantity'))
                    taxes = l[2].get('invoice_line_tax_id')
                    if len(taxes[0]) >= 3 and taxes[0][2]:
                        taxes=tax_obj.browse(cr, uid, taxes[0][2])
                        for tax in tax_obj.compute(cr, uid, taxes, p,l[2].get('quantity'), context.get('address_invoice_id', False), l[2].get('product_id', False), context.get('partner_id', False)):
                            t = t - tax['amount']
            return t
        return 0
    
    def get_price_from_picking_ecommerce(self, cr, uid, id, total, weight, volume, context={}):
        
        grid = self.pool.get('delivery.grid')
        grid_get = grid.browse(cr, uid, int(id))
        price = 0.0
        ok = False

        for line in grid_get.line_ids:
            price_dict = {'price': total, 'volume':volume, 'weight': weight, 'wv':volume*weight}
            test = eval(line.type+line.operator+str(line.max_value), price_dict)
            
            if test:
                if line.price_type=='variable':
                    price = line.list_price * price_dict[line.variable_factor]
                else:
                    price = line.list_price
                ok = True
                break
        if not ok:
            raise except_osv(_('No price avaible !'), _('No line matched this order in the choosed delivery grids !'))
       
        return price   
    
    def ecom_send_email(self, cr, uid, mail_to, subject, body, attachment=None, context = {}):
    
        import smtplib
        from email.MIMEText import MIMEText
        from email.MIMEBase import MIMEBase
        from email.MIMEMultipart import MIMEMultipart
        from email.Header import Header
        from email.Utils import formatdate, COMMASPACE
        from email import Encoders
        
        try:
            mail_from= 'priteshmodi.eiffel@yahoo.co.in'
            
            s = smtplib.SMTP()
          
            s.debuglevel = 5
            s.connect('smtp.mail.yahoo.co.in','587')
            s.login('priteshmodi.eiffel', '123456')
            outer = MIMEMultipart()
            outer['Subject'] = 'Invoice:'
            outer['To'] = mail_to
            outer['From'] = "noreply"
            outer.preamble = 'You will not see this in a MIME-aware mail reader.\n'
          
            msg = MIMEText(body or '', _charset='utf-8')
         
            if(attachment == None):
                
                msg['Subject'] = Header(subject.decode('utf8'), 'utf-8')
                msg['From'] = "noreply"
                s.sendmail(mail_from, mail_to,  msg.as_string());
                
            else:
                
                msg.set_payload(attachment)
                Encoders.encode_base64(msg);
                msg.add_header('Content-Disposition', 'attachment', filename='invoice.pdf');
               
                outer.attach(msg);
                outer.attach(MIMEText(body));

                composed = outer.as_string();
                s.sendmail(mail_from, mail_to, composed);
                
            s.close();
        
        except Exception, e:
            import logging
            logging.getLogger().error(str(e))
        
        return True 
        
ecommerce_partner()

class ecommerce_partner_address(osv.osv):
    _description="ecommerce partner address"
    _rec_name = "username"
    _name="ecommerce.partner.address"
    _columns={
        'username':fields.char('Contact Name',size=128,select=True,required=True),
        'partner_id': fields.many2one('ecommerce.partner', 'Partner', required=True, ondelete='cascade', select=True),
        'type': fields.selection( [ ('default','Default'),('invoice','Invoice'), ('delivery','Delivery'), ('contact','Contact'), ('other','Other') ],'Address Type'),
        'street': fields.char('Street', size=128),
        'street2': fields.char('Street2', size=128),
        'zip': fields.char('Zip', change_default=True, size=24),
        'city': fields.char('City', size=128),
        'state_id': fields.many2one("res.country.state", 'State', domain="[('country_id','=',country_id)]"),
        'country_id': fields.many2one('res.country', 'Country'),
        'email': fields.char('E-Mail', size=64),
        'phone': fields.char('Phone', size=64),
        'fax': fields.char('Fax', size=64),
        'mobile': fields.char('Mobile', size=64),
            }

ecommerce_partner_address()



