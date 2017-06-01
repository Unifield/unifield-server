/*##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (c) 2010-2012 Elico Corp. All Rights Reserved.
#    Author: Yannick Gouin <yannick.gouin@elico-corp.com>
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
*/


/* some keys cannot be overriden, for example
* "There is no way to override CTRL-N, CTRL-T, or CTRL-W in Google Chrome since
* version 4 of Chrome (shipped in 2010)."
*/

$.ctrl = function(key, callback, args) {
    $(document).keydown(function(e) {
        if(!args) args=[]; // IE barks when args is null
        if((e.keyCode == key.charCodeAt(0) || e.keyCode == key) && e.ctrlKey) {
            e.preventDefault();  // override the browser shortcut keys
            callback.apply(this, args);
            return false;
        }
    });
};

//Save the current object
$.ctrl('S', function() {
    var saved = false;
    $('.oe_form_button_save_line').each(function() {
        if($(this).parents('div:hidden').length == 0){
            $(this).trigger('click');
            saved = true;  // if a line is under edition, save only this line, not the whole object
        }
    });
    $('.oe_form_button_save_close').each(function() {
        if(!saved && $(this).parents('div:hidden').length == 0){
            $(this).trigger('click');
            saved = true;
        }
    });
    $('.oe_form_button_save').each(function() {
        if(!saved && $(this).parents('div:hidden').length == 0){
            $(this).trigger('click');
        }
    });
});

//Save & Edit the current object
$.ctrl('E', function() {
    $('.oe_form_button_save_edit').each(function() {
        if($(this).parents('div:hidden').length == 0){
            $(this).trigger('click');
        }
    });
    $('.oe_form_button_edit').each(function() {
        if($(this).parents('div:hidden').length == 0){
            $(this).trigger('click');
        }
    });
});

//Delete the current object
$.ctrl('46', function() {
    $('.oe_form_button_delete').each(function() {
        if($(this).parents('div:hidden').length == 0){
            $(this).trigger('click');
        }
    });
});

//Cancel the modifiactions
$.ctrl('Z', function() {
    $('.oe_form_button_cancel').each(function() {
        if($(this).parents('div:hidden').length == 0){
            $(this).trigger('click');
        }
    });
});

//New object
$.ctrl('C', function() {
    $('.oe_form_button_create').each(function() {
        if($(this).parents('div:hidden').length == 0){
            $(this).trigger('click');
        }
    });
    $('.oe_form_button_save_create').each(function() {
        if($(this).parents('div:hidden').length == 0){
            $(this).trigger('click');
        }
    });
});

//Duplicate the current object
$.ctrl('D', function() {
    $('.oe_form_button_duplicate').each(function() {
        if($(this).parents('div:hidden').length == 0){
            $(this).trigger('click');
        }
    });
});

//Search (enter)
$.ctrl('13', function() {
    $('.oe_form_button_search').each(function() {
        if($(this).parents('div:hidden').length == 0){
            $(this).trigger('click');
        }
    });
});

//Clear search
$.ctrl('R', function() {
    $('.oe_form_button_clear').each(function() {
        if($(this).parents('div:hidden').length == 0){
            $(this).trigger('click');
        }
    });
});

//First object (arrow up)
$.ctrl('38', function(event) {
    $('.oe_button_pager[action="first"]').each(function() {
        if($(this).parents('div:hidden').length == 0){
            $(this).trigger('click');
        }
    });
});

//Previous object (arrow right)
$.ctrl('37', function() {
    $('.oe_button_pager[action="previous"]').each(function() {
        if($(this).parents('div:hidden').length == 0){
            $(this).trigger('click');
        }
    });
});

//Next object (arrow left)
$.ctrl('39', function() {
    $('.oe_button_pager[action="next"]').each(function() {
        if($(this).parents('div:hidden').length == 0){
            $(this).trigger('click');
        }
    });
});

//Last object (arrow down)
$.ctrl('40', function() {
    $('.oe_button_pager[action="last"]').each(function() {
        if($(this).parents('div:hidden').length == 0){
            $(this).trigger('click');
        }
    });
});


//Close (escape)
$.ctrl('27', function() {
    $('.oe_form_button_close').each(function() {
        if($(this).parents('div:hidden').length == 0){
            $(this).trigger('click');
        }
    });
});
