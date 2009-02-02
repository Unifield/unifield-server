
from turbogears import expose
from turbogears import controllers

import cherrypy
import urllib

from erpcomparator import rpc
from erpcomparator import common

class Graph(controllers.Controller):
    
    @expose(template="erpcomparator.subcontrollers.templates.graph")
    def index(self, **kw):
        
        proxy_factor = rpc.RPCProxy('comparison.factor')
        
        view_factor_id = kw.get('view_id', [])
        parent_name = kw.get('parent_name')
        
        sel_factor_id = []
        if parent_name:
            parent_name = parent_name.replace('@', '&')
            sel_factor_id = proxy_factor.search([('name', '=', parent_name)])
        
        proxy_item = rpc.RPCProxy('comparison.item')
        item_ids = proxy_item.search([])
        
        res = proxy_item.read(item_ids, ['name'])
        titles = []
        factors = []
        
        summary = {}
        parent_child = []
        
        for r in res:
            title = {}
            title['name'] = r['name']
            title['id'] = r['id']
            titles += [title]
        
        selected_fact = None
        
        if view_factor_id:
            factors = proxy_factor.search([('id', '=', [view_factor_id])])
        else:
            factors = proxy_factor.search([('parent_id', '=', False)])
        
        parents = proxy_factor.read(factors, ['id', 'name'])
        
        for pch in parents:
            fact = proxy_factor.search([('id', '=', [pch['id']])])
            parent_child += proxy_factor.read(fact, ['child_ids'])
        
        all_child = []
        
        for ch in parent_child:
            pname = proxy_factor.read(ch['id'], ['name'])
            if ch.get('child_ids'):
                for c in ch['child_ids']:
                    child = {}
                    level2 = proxy_factor.read(c, ['name'])
                    child['name'] = pname.get('name') + '/' + level2.get('name')
                    child['id'] = level2.get('id')
                    all_child += [child]
                
        return dict(titles=titles, parents=parents, all_child=all_child, selected_fact=selected_fact)

    @expose('json')
    def radar(self, **kw):
        
        item_ids = kw.get('ids')
        item_ids = item_ids and eval(str(item_ids))
        
        parent_name = kw.get('factor_name')
        parent_name = parent_name.replace('@', '&')
        
        proxy_factor = rpc.RPCProxy('comparison.factor')
        
        child_name = []
        child_ids = []
        
        if parent_name == 'Summary':
            list = proxy_factor.search([('parent_id', '=', False)])
            ch_ids = proxy_factor.read(list, ['name'])
            
            for ch in ch_ids:
                cname = {}                
                cname['name'] = ch['name'][:18]
                                
                child_ids += [ch['id']]
                child_name += [cname]
        else :
            if '/' in parent_name:
                parent_name = parent_name.rsplit('/')[1]
            parent_list = proxy_factor.search([('name', '=', parent_name)])
            
            child_ids = proxy_factor.read(parent_list, ['child_ids'])
            child_ids = child_ids[0].get('child_ids')
            child_list = proxy_factor.read(child_ids, ['name'])
            
            for ch in child_list:
                cname = {}
                cname['name'] = ch['name'][:18]
                child_name += [cname]
        
        elem = []
        elements = {}
        elements["elements"] = [] #Required
        elements["title"] = {}   #Optional
        elements["radar_axis"] = {} #Required
        elements["tooltip"] = {} #Depend On Choice
        elements["bg_colour"] = "#ffffff" #Optional
        
        ChartColors = ['#c4a000', '#ce5c00', '#8f5902', '#4e9a06', '#204a87', '#5c3566', '#a40000', '#babdb6', '#2e3436'];
        proxy_item = rpc.RPCProxy('comparison.item')
        item_name = proxy_item.read(item_ids, ['name'])
        
        proxy_res = rpc.RPCProxy('comparison.factor.result')
        rids = proxy_res.search([('factor_id', 'in', child_ids)])            
        factor_res = proxy_res.read(rids)
        
        value = []
        
        for item in item_name:
            val = []
            for factor in factor_res:
                if factor.get('item_id')[1] == item['name']:
                    val += [factor.get('result')/10.0]
            
            value += [val]
        
        for n, j in enumerate(item_name):
            
            if n%2==0:
                elem.append({'type': 'line_hollow', 
                             "values": value[n],
                             "halo_size": 2,
                             "width": 1,
                             "dot-size": 2,
                             "colour": ChartColors[n],
                             "text": str(j['name']),
                             "font-size": 12,
                             "loop": True})
            else:
                elem.append({"type": "line_dot",
                              "values": value[n],
                              "halo_size": 2,
                              "width": 1,
                              "dot-size": 2,
                              "colour": ChartColors[n],
                              "text": str(j['name']),
                              "font-size": 12,
                              "loop": True})
                
            elements["elements"] = elem
        
        elements["title"] = {"text": parent_name, "style": "{font-size: 15px; color: #50284A; text-align: left; font-weight: bold;}"}
        elements["radar_axis"] = {
                                  "max":10,
                                  "colour": "#DAD5E0",
                                  "grid-colour":"#DAD5E0",
                                  "labels": {
                                             "labels": [],
                                             "colour": "#9F819F"
                                             },
                                  "spoke-labels": {
                                                   "labels": [ch['name'] for ch in child_name],
                                                   "colour": "#5c3566"
                                                   }
                                  }
       
#        elements["tooltip"] = {"mouse": 1}
        elements["bgcolor"] = "#ffffff"
        
        return elements