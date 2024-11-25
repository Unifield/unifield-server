////////////////////////////////////////////////////////////////////////////////
//
// Copyright (C) 2007-TODAY OpenERP SA. All Rights Reserved.
//
// $Id$
//
// Developed by OpenERP (http://openerp.com) and Axelor (http://axelor.com).
//
// The OpenERP web client is distributed under the "OpenERP Public License".
// It's based on Mozilla Public License Version (MPL) 1.1 with following 
// restrictions:
//
// -   All names, links and logos of OpenERP must be kept as in original
//     distribution without any changes in all software screens, especially
//     in start-up page and the software header, even if the application
//     source code has been changed or updated or code has been added.
//
// You can see the MPL licence at: http://www.mozilla.org/MPL/MPL-1.1.html
//
////////////////////////////////////////////////////////////////////////////////

function form_hookContextMenu(){
    if (!openobject.dom.get('_terp_list')) {
        MochiKit.Signal.connect(window.document, 'oncontextmenu', on_context_menu);
    }
}

function form_hookStateChange() {
    var fields = {};

    jQuery('td.item[states], td.label[states], div.tabbertab[states]').each(function() {
        var $this = jQuery(this);
        var widget = $this.attr('widget');
        var prefix = widget.slice(0, widget.lastIndexOf('/')+1) || '';

        // convert states from Python serialization to JS/JSON
        var states = eval(
                '(' + $this.attr('states')
                      .replace(/u'/g, "'")
                      .replace(/True/g, '1')
                      .replace(/False/g, '0') + ')');

        var state = openobject.dom.get(prefix + 'state') || openobject.dom.get(prefix + 'x_state');
        if (state) {
            fields[state.id] = state;
            var $state = jQuery(state).bind('onStateChange', MochiKit.Base.partial(form_onStateChange, this, widget, states));
            $state.change(function (){
                jQuery(this).trigger('onStateChange');
            });
        }
    });
    
    for(var field in fields) {
        jQuery(field).trigger('onStateChange');
    }
}

function list_hookStateChange(list_name) {
    var fields = {};
    var list_fields_with_states = [ 'table[id='+list_name+'_grid] input.[states]',
				    'table[id='+list_name+'_grid] selection.[states]' ].join(', ');
    jQuery(list_fields_with_states).each(function() {
        var $this = jQuery(this);
        var attrs = $this.attr('attrs') || '{}';
        var widget = $this.attr('widget') || '';
        var container = this;
        var prefix = widget.slice(0, widget.lastIndexOf('/')+1) || '';

        // convert states from Python serialization to JS/JSON
        var states = eval(
                '(' + $this.attr('states')
                      .replace(/u'/g, "'")
                      .replace(/True/g, '1')
                      .replace(/False/g, '0') + ')');

        var state = form_find_field_in_context(prefix, 'state', $this);
        if (!state || !state.length) {
            state = form_find_field_in_context(prefix, 'x_state', $this);
        }

        if (state && state.length) {
            var $state = state.bind('onStateChange', MochiKit.Base.partial(form_onStateChange, container, this, states));
            $state.change(function (){
                jQuery(this).trigger('onStateChange');
            });
            state.trigger('onStateChange');
        }

    });
}

function form_onStateChange(container, widget, states, evt) {
    var src;
    if(evt.src)
        src = evt.src();
    else
        src = evt.target;

    var value = typeof(src.value) == "undefined" ? getNodeAttribute(src, 'value') || src.innerHTML : src.value;
    var $field = jQuery(idSelector(widget));

    if (MochiKit.Base.isArrayLike(states)) {
        form_setVisible(container, widget, findIdentical(states, value) > -1);
        return;
    }

    var has_readonly = false;
    var has_required = false;

    for(var a in states) {
        a = states[a];
        has_readonly = has_readonly || typeof(a.readonly) != "undefined";
        has_required = has_required || typeof(a.required) != "undefined";
    }

    var attr = states[value];
    if (has_readonly) {
    	if (attr) {
        	form_setReadonly(container, widget, attr['readonly']);
    	}
    	else {
        	form_setReadonly(container, widget, parseInt($field.attr('fld_readonly')));
    	}
    }
    if (has_required) {
    	if (attr) {
        	form_setRequired(container, widget, attr['required']);
    	}
        else {
        	form_setRequired(container, widget, parseInt($field.attr('required')));
        }
    }
}



// Convert string describing a python structure (made of dict/lists) to a 
// javascript object
function python_to_javascript(string) {

    // Convert Python statement into its equivalent in JavaScript.
    string = string.replace(/\(/g, '[');
    string = string.replace(/\)/g, ']');
    string = string.replace(/True/g, '1');
    string = string.replace(/False/g, '0');
    string = string.replace(/\buid\b/g, window.USER_ID);

    // Convert string to a javascript object
    try {
        return eval('(' + string + ')');
    } catch(e){
        window.console && console.warn("Parsing failure for : ");
        window.console && console.warn('(' + string + ')');
        return "";
    }
}

//
// This function browse every element/widget which has an "attrs" attribute.
//
// 'attrs' typically contains something like { 'readonly' : [('state', 'not in', ['draft', 'validated'])]}
// and is generally defined in the XML view.
//
// For each of these elements, it finds the related fields ('state' in the
// example) and create an "onAttrChange" binding, such that when these fields 
// change and trigger an "onAttrChange" event, the new value is correctly 
// propagated back to the element/widget according to what "attrs" describes
// (e.g. readonly turned on/off).
//
// Then, an initial 'onAttrChange' event is called for each related field found.
//
// Warning : this function won't erase previous binding, so *calling it multiple
// time on the same page will duplicated bindings!*
//
//
function form_hookAttrChange($items) {
    
    // We'll keep track of each fields for which we added an onAttrChange
    // binding
    var fields_with_onAttrChange = new Set();

    // By default, select every HTML element with an "attrs" attribute
    if(typeof options === "undefined") {
        $items = jQuery('[attrs]');
    }

    // For each of them...
    $items.each(function(){
        // Add the proper onAttrChange bindings on their related fields
        var related_fields = form_addAttrChangeBindings(this);
        // Keep track of the fields for which we added the onAttrChange
        for (var field of related_fields) {
            fields_with_onAttrChange.add(field);
        }
    });

    // For each field for which we defined a binding, trigger it
    for (var field of fields_with_onAttrChange) {
        jQuery(idSelector(field)).trigger('onAttrChange');
    }
}

function form_addAttrChangeBindings(elem) {

    var $elem = jQuery(elem);
    var related_fields = new Set();

    // Get the 'attrs' attribute and convert it to a javascript object
    // Silently return the conversion fails...
    var attrs = $elem.attr('attrs') || '{}';
    attrs = python_to_javascript(attrs);
    if (attrs == "") {
        window.console && console.warn("Failed to parse 'attrs' for " + elem.id); 
        return related_fields; 
    }

    // Get the widget name
    var widgetName = $elem.attr('widget') || '';
    var prefix = widgetName.slice(0, widgetName.lastIndexOf('/')+1) || '';
    var cache_values = {};

    // For each property in attrs... (e.g. readonly, invisible, ..)
    for (var attr in attrs) {
        var exprs = attrs[attr];

        // If there's no expression associated (e.g. readonly: {} (?))
        // Don't create any 'onAttrChange' binding (there's no field to
        // bind to), just apply it
        if (exprs == ''){
            form_onAttrChange(elem, widgetName, attr, exprs, $elem, cache_values);
            continue;
        }

        // (check if field appears more then once in the expr for this specific
        // property)
        var already_connected_fields = new Set(); 

        // Otherwise, exprs is a list of expressions like :
        //   'state', 'not in', ['draft', 'validated']
        //   'shipped', '=', 1 
        forEach(exprs, function(expr){

            // If the relation is just a number, e.g. {'invisible': [1]}
            // Don't create any 'onAttrChange' binding (there's no field
            // to bind to), just apply it
            if (typeof(expr) == "number") {
                return form_onAttrChange(elem, widgetName, attr, expr, $elem, cache_values);
            }

            // Otherwise, get the name of the related field and the 
            // corresponding object in the DOM
            var name = prefix + expr[0];
            var related_field = openobject.dom.get(name);
            // If we did really found the related field and we
            // did not already connected this item to this field
            if (related_field && !already_connected_fields.has(related_field.id)) {
                // Keep track of this field
                related_fields.add(related_field.id);
                already_connected_fields.add(related_field.id);

                // events disconnected during hook_onStateChange,
                // don't redisconnect or may break onStateChange
                // 
                // Create a binding between this field and the current item/widget : 
                // field.trigger('onAttrChange') will then trigger form_onAttrChange(..., widget, ...)
                //
                var $related_field = jQuery(related_field).bind('onAttrChange', partial(form_onAttrChange, elem, widgetName, attr, exprs, $elem, {}));
                $related_field.change(partial(form_onAttrChange, elem, widgetName, attr, exprs, $elem, {}));
            }
        });
    }

    return related_fields;
}


function list_hookAttrChange(list_name) {

    // check if an editor exists
    var editor_exists = $(".editors").length;
   
    // Loop on list elements which have an 'attrs' attribute 
    var listgrids = jQuery('table[id='+list_name+'_grid] [attrs]');
    for (var i = 0 ; i < listgrids.length ; i++)
    {
        var elem = listgrids[i];
        var $this = jQuery(elem);
        var attrs = $this.attr('attrs') || '{}';
        var widget = $this.attr('widget') || '';
        var container = elem;
        var prefix = widget.slice(0, widget.lastIndexOf('/')+1) || '';

        // Convert Python statement into it's equivalent in JavaScript.
        attrs = attrs.replace(/\(/g, '[');
        attrs = attrs.replace(/\)/g, ']');
        attrs = attrs.replace(/True/g, '1');
        attrs = attrs.replace(/False/g, '0');
        attrs = attrs.replace(/\buid\b/g, window.USER_ID);

        try {
            attrs = eval('(' + attrs + ')');
        } catch(e){
            continue;
        }

        var cache_values = {};

        var row_is_editable = editor_exists && $this.parents('tr.grid-row').is('.editors');
        for (var attr in attrs) {
            if (!row_is_editable && attr != 'invisible') {
                // when row is not in editable mode we only care about invisible attributes
                // as others attrs (readonly, required) won't have any effects.
                continue;
            }
            if (attrs[attr] == '') {
                return form_onAttrChange(container, widget, attr, attrs[attr], $this, cache_values);
            }
            forEach(attrs[attr], function(n) {

                if (typeof(n) == "number") { // {'invisible': [1]}
                    return form_onAttrChange(container, widget, attr, n, $this, cache_values);
                }
                var name = prefix + n[0];
                var field = openobject.dom.get(name);
                if (row_is_editable) {
                    var $field = jQuery(field).bind('onAttrChange', partial(form_onAttrChange, container, widget, attr, attrs[attr], $this, {}));
                    $field.change(partial(form_onAttrChange, container, widget, attr, attrs[attr], $this, {}));
                }
                return form_onAttrChange(container, widget, attr, attrs[attr], $this, cache_values);
            });
        }
    };
}

function form_onAttrChange(container, widgetName, attr, expr, elem, cache_values) {
    var cache_values = cache_values || {};

    var prefix = widgetName.slice(0, widgetName.lastIndexOf('/') + 1);
    var widget = openobject.dom.get(widgetName) || elem;

    var result = form_evalExpr(prefix, expr, elem, cache_values);

    switch (attr) {
        case 'readonly':
            var editable = openobject.dom.get(prefix + '_terp_editable');
            if (widget.type != 'button' && editable && (editable.value == 0 || editable.value == 'False')) {
                // We are in 'non-editable' mode, so we force readonly = True
                // whatever readonly attrs result
                result = true;
            }
            form_setReadonly(container, widget, result);
            break;
        case 'required': form_setRequired(container, widget, result);
            break;
        case 'invisible': form_setVisible(container, widget, !result);
            break;
        case 'notselectable': form_setNotSelectable(container, widget, result);
            break;
        default:
    }
}

function ret_cache_if_available(cache, key, func_eval)
{
    if(cache[key] == undefined){
        val = func_eval()
        cache[key] = val;
        return val;
    }else{
        return cache[key];
    }
}

function form_find_field_in_context(prefix, field, ref_elem, cache_values) {
    // try to find field in the context of reference element (ref_elem)
    var elem = null;

    var key_cache = 'bigcache_' + prefix + '_' + field;

    return ret_cache_if_available(cache_values, key_cache, function(){

        var parents_grid = ret_cache_if_available(cache_values, 'closest_table.grid', function(){
            return ref_elem.closest('table.grid');
        });

        if (parents_grid.length) {

            var parent = ret_cache_if_available(cache_values, 'tr.grid-row', function(){
                return ref_elem.closest('tr.grid-row');
            });

            elem = parent.find(idSelector(prefix + field));

            if (!elem || !elem.length) {
                var parent_selector = '[name='+prefix + field +']';
                elem = parent.find(parent_selector);
            }

            if (!elem || !elem.length) {
                // try getting with _terp_listfields/TABLE_ID/FIELD_NAME
                var parent_table_id = parents_grid[0].id;
                if (parent_table_id && parent_table_id.match('_grid$')) {
                    parent_table_id = parent_table_id.slice(0, parent_table_id.length - 5);
                }
                if (parent_table_id == '_terp_list') {
                    // in case list name if '_terp_list' this means we're not inside a o2m/m2m fields,
                    // and we no need need to prefix with parent_table_id name
                    parent_table_id = ''
                } else {
                    parent_table_id = parent_table_id + '/'
                }
                var parent_relative_fieldname = '[name=_terp_listfields/' + parent_table_id + prefix + field + ']';
                elem = parent.find(parent_relative_fieldname);
            }
        }
        if (!elem || !elem.length) {
            elem = jQuery(idSelector(prefix + field));
        }
        cache_values[key_cache] = elem;
        return elem;
    });
}


function form_evalExpr(prefix, expr, ref_elem, cache_values) {

    // the stack contains future that can be evaluated when it's required
    var stack = [];
    for (var i = 0; i < expr.length; i++) {

        var ex = expr[i];
        var op = ex[1];

        // it's an operator, we don't need to find its value in the page
        if (ex.length==1) {

            function val_gen(ret_val){
                return function(){
                    return ret_val;
                }
            }


            stack.push(val_gen(ex[0]));
            continue;
        }

        // create a future in order to evaluate it only if required
        function fetch_value(_op, _prefix, ex_0, ex_2, ref_elem){

            return function(){
                var elem = form_find_field_in_context(_prefix, ex_0, ref_elem, cache_values);

                if (!elem || !elem.length) {
                    return null;
                }
                var val = ex_2;

                var elem_value;
                if(elem.is(':input')) {
                    elem_value = elem.val();
                } else {
                    elem_value = elem.attr('value') || elem.text();
                }

                switch (_op.toLowerCase()) {
                    case '=':
                    case '==':
                        return elem_value == val;
                    case '!=':
                    case '<>':
                        return elem_value != val;
                    case '<':
                        return elem_value < val;
                    case '>':
                        return elem_value > val;
                    case '<=':
                        return elem_value <= val;
                    case '>=':
                        return elem_value >= val;
                    case 'in':
                        return MochiKit.Base.findIdentical(val, elem_value) > -1;
                    case 'not in':
                        return MochiKit.Base.findIdentical(val, elem_value) == -1;
                }

                return null;
            };
        };

        stack.push(fetch_value(op, prefix, ex[0], ex[2], ref_elem));
    }

    ret = true;
    position = 0;

    while(ret && position < stack.length){
        result = eval_stackNew(stack, position, false)

        ret = result.value;
        position = result.next;
    }

    return ret;
}

function eval_stackNew(stack, i, fuzzy) {

    if(stack.length <= i){
        return {value: true, next: i+1};
    }else{
        value = stack[i]()

        if(value === null){
            return eval_stackNew(stack, i+1, fuzzy);
        }else if(value === false || value === true){
            return {value: value, next: i+1};
        }else if(value === '|'){
            var val1 = eval_stackNew(stack, i+1, false)
            var val2 = eval_stackNew(stack, val1.next, false)
            return {value: val1.value || val2.value, next: val2.next};
        }else if(value === '&'){
        
            if(fuzzy){
                var val1 = eval_stackNew(stack, i+1, true)
                if(!val1.value)
                    return {value: false, next: undefined};
                else
                    return {value: eval_stackNew(stack, val1.next, true), next: undefined};
            }else{
                var val1 = eval_stackNew(stack, i+1, false)
                var val2 = eval_stackNew(stack, val1.next, false)
                return {value: val1.value && val2.value, next: val2.next};
            }

        }
    }
}

function form_setReadonly(container, fieldName, readonly) {
    var $field = typeof(fieldName) == "string" ? jQuery(idSelector(fieldName)) : jQuery(fieldName);

    if (!$field.length) {
        return;
    }

    var kind = $field.attr('kind');
    var field_id = $field.attr('id');
    var field_name = $field.attr('name');
    var type = $field.attr('type');
    var ro_by_trans = $field.attr('ro_by_trans');

   var changed_by_trans = false;
    if (!readonly && ro_by_trans) {
        readonly = true;
        changed_by_trans = true;
    }
    
    if (type == 'hidden' && kind == 'reference') {
        form_setReadonly(container, openobject.dom.get(field_id + '_text'), readonly);
        form_setReadonly(container, openobject.dom.get(field_id + '_reference'), readonly);
        return;
    }

    if (kind == 'boolean') {
        if ( field_id == '_terp_listfields/is_asset') {
            var boolean_field = jQuery(idSelector(field_id+'_checkbox_'));
        } else {
            var boolean_field = jQuery('input#'+field_id+'_checkbox_');
        }
        boolean_field.attr({'disabled':readonly, 'readOnly': readonly});
    }

    if (!kind &&
            jQuery(idSelector(field_id + '_id')) &&
            jQuery(idSelector(field_id + '_set')) &&
            jQuery(idSelector(field_id + '_id')).attr('kind') == "many2many") {
         Many2Many(field_id).setReadonly(readonly);
        return;
    }

    if (!type && $field.hasClass('item-group')) {
        jQuery($field).find(':input')
            .toggleClass('readonlyfield', readonly)
            .attr({'disabled': readonly, 'readOnly': readonly});
        return;
    }
    $field.attr({'disabled':readonly, 'readOnly': readonly});
    ro_f = jQuery(idSelector(field_id+'_ro'))
    if (readonly) {
        if ((type == 'button')) {
            $field.css("cursor", "default");
        } else {
            $field.removeAttr('href');
        }
        $field.toggleClass('readonlyfield', type != 'button');
        if ($field.attr('translatable') == "1" && !changed_by_trans) {
            $('#'+field_id+'_translatable').hide();

        }
        if (ro_f.length) {
            $field.hide();
            ro_f.show();
            if (type == 'select-one') {
                ro_f.html($field.children("option:selected").html());
            } else {
                ro_f.html($field.val());
            }
        }
    } else {
        $field.removeClass('readonlyfield');
        $field.css('color', '');
        if (ro_f.length) {
            $field.show();
            ro_f.hide();
        }
    }
    if (type == 'hidden' && kind == 'many2one') {
        ManyToOne(field_id).setReadonly(readonly);
    }

    if (!kind && (jQuery(idSelector(field_id+'_btn_')).length || jQuery(idSelector('_o2m_'+field_id)).length)) { // one2many
        if (isNaN(readonly))
        {
            readonly = parseInt(jQuery(idSelector('_o2m_'+field_id)).attr("fld_readonly"));
        }

        // Convert input to boolean...
        // (careful : sometimes readonly already is a boolean ... )
        if (readonly == 1) { readonly = true;  }
        if (readonly == 0) { readonly = false; }

        // Get current readonly status
        var current_readonly = jQuery('table.one2many[id$="'+field_id+'"]')[0].classList.contains("m2o_readonly");
        
        // Update only if different
        if (current_readonly != readonly)
        {
            new One2Many(field_id).setReadonly(readonly);
        }
        return;
    }

    if (kind == 'date' || kind == 'datetime' || kind == 'time') {
        jQuery(idSelector(field_name+'_trigger')).toggle(!readonly);
    }
}

function form_setRequired(container, field, required) {
    
    if (!field) {
        field = container;
    }
    var editable = getElement('_terp_editable').value;

    var $field = jQuery(idSelector(field));
    if (editable == 'True' && required) {
        $field.toggleClass('requiredfield', required);
    }
    else {
    	$field.removeClass('requiredfield');
    }
    var field_id = $field.attr('id');
    if(required && field_id != 'ext_cu_text' && field_id != 'partner_id2_text') {
        $field.removeClass('readonlyfield');
    }
    $field.removeClass('errorfield');

    var kind = $field.attr('kind');
    
    if (field.type == 'hidden' && kind == 'many2one') {
        form_setRequired(container, openobject.dom.get(field.name + '_text'), required);
    } else if (field.type == 'hidden' && kind == 'reference') {
        form_setRequired(container, openobject.dom.get(field.name + '_reference'), required);
        form_setRequired(container, openobject.dom.get(field.name + '_text'), required);
    }
}

function form_setVisible(container, field, visible) {
    var $container = jQuery(container);
    if ($container.hasClass('notebook-page')) { // notebook page?
    
        var nb = container.parentNode.parentNode.notebook;

        if (!nb)  {
           MochiKit.Async.callLater(0, form_setVisible, container, field, visible);
           return;
        }

        var i = findIdentical(nb.pages, container);

        if (visible) {
            nb.show(i, false);
        } else {
            nb.hide(i);
        }

    } else {

        try {
            var $label = $container.prev('td.label');
            $container.toggle(visible);
            if ($label.length) {
                $label.toggle(visible);
            }
        }catch(e){}
    }
}

function form_setNotSelectable(container, field, notSelectable) {
    var editable = getElement('_terp_editable').value;
    if (editable == 'True' && notSelectable) {
        // find the checkboxes used to select lines
        var selectors = field.getElementsByClassName('grid-record-selector');
        for (var i = 0; i < selectors.length; i++) {
            selectors[i].style.visibility = 'hidden';
        }
    }
}

jQuery(document).ready(function(){
    form_hookContextMenu();
    form_hookStateChange();
    form_hookAttrChange();
});
