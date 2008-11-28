# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2008 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import time, os
import netsvc
import pooler,tools
import sys
import report

def graph_get(cr, uid, graph, offer_id):
    import pydot
    offer_obj = pooler.get_pool(cr.dbname).get('dm.offer')
    offer = offer_obj.browse(cr, uid, offer_id)[0]
    nodes = {}
    for step in offer.step_ids:
        args = {}

        # Get user language
        usr_obj = pooler.get_pool(cr.dbname).get('res.users')
        user = usr_obj.browse(cr, uid, [uid])[0]
        user_lang = user.context_lang

        trans_obj =  pooler.get_pool(cr.dbname).get('ir.translation')
        res_trans = trans_obj._get_ids(cr, uid, 'dm.offer.step.type,code', 'model',
                           user_lang or 'en_US',[step.type.id])
        print "res_trans : ",res_trans
        type_code = res_trans[step.type.id] or step.type.code
        print "type_code : ",type_code

        args['label'] = type_code
        graph.add_node(pydot.Node(step.id, **args))

    for step in offer.step_ids:
        for transition in step.outgoing_transition_ids:
#            tr_cond_trans = trans_obj._get_ids(cr, uid, 'dm.offer.transition,condition', 'model',
#                                       user_lang or 'en_US',[step.type.id])

#            tr_condition = 
#            tr_condition = 
#            tr_delay_unit =

            trargs = {
#                'label': transition.condition + ' - ' + transition.media_id.name  + '\\n' + str(transition.delay) + ' days'
                'label': transition.condition + ' - ' + transition.media_id.name  + '\\n' + str(transition.delay) + ' days'
            }
            if step.split_mode=='and':
                trargs['arrowtail']='box'
            elif step.split_mode=='or':
                trargs['arrowtail']='inv'
            elif step.split_mode=='xor':
                trargs['arrowtail']='inv'
            graph.add_edge(pydot.Edge( str(transition.step_from.id) ,str(transition.step_to.id), fontsize=10, **trargs))
    return True



class report_graph_instance(object):
    def __init__(self, cr, uid, ids, data):
        logger = netsvc.Logger()
        try:
            import pydot
        except Exception,e:
            logger.notifyChannel('workflow', netsvc.LOG_WARNING,
                    'Import Error for pydot, you will not be able to render workflows\n'
                    'Consider Installing PyDot or dependencies: http://dkbza.org/pydot.html')
            raise e
        offer_id = ids
        self.done = False

        offer = pooler.get_pool(cr.dbname).get('dm.offer').browse(cr, uid, offer_id)[0].name

        graph = pydot.Dot(fontsize=16, label=offer)
        graph.set('size', '10.7,7.3')
        graph.set('center', '1')
        graph.set('ratio', 'auto')
        graph.set('rotate', '90')
        graph.set('rankdir', 'LR')
        graph_get(cr, uid, graph, offer_id)

        ps_string = graph.create_ps(prog='dot')
        if os.name == "nt":
            prog = 'ps2pdf.bat'
        else:
            prog = 'ps2pdf'
        args = (prog, '-', '-')
        try:
            input, output = tools.exec_command_pipe(*args)
        except:
            return
        input.write(ps_string)
        input.close()
        self.result = output.read()
        output.close()
        self.done = True

    def is_done(self):
        return self.done

    def get(self):
        if self.done:
            return self.result
        else:
            return None

class report_graph(report.interface.report_int):
    def __init__(self, name, table):
        report.interface.report_int.__init__(self, name)
        self.table = table

    def result(self):
        if self.obj.is_done():
            return (True, self.obj.get(), 'pdf')
        else:
            return (False, False, False)

    def create(self, cr, uid, ids, data, context={}):
        self.obj = report_graph_instance(cr, uid, ids, data)
        return (self.obj.get(), 'pdf')

report_graph('report.dm.offer.graph', 'dm.offer')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

