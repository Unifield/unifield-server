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

$.ctrlshift = function(key, callback, args) {
    $(document).keydown(function(e) {
        if(!args) args=[]; // IE barks when args is null
        if((e.keyCode == key.charCodeAt(0) || e.keyCode == key) && e.ctrlKey && e.shiftKey) {
            e.preventDefault();  // override the browser shortcut keys
            callback.apply(this, args);
            return false;
        }
    });
};

fake_click = function(button) {
    if($(button).parents('div:hidden').length == 0){
        if (button.hasAttribute('onclick')) {
            button.onclick();
        }
        else {
            $(button).trigger('click');
        }
    }
};

//Save the current object
$.ctrlshift('S', function() {
    var saved = false;
    $('.oe_form_button_save_line').each(function() {
        if($(this).parents('div:hidden').length == 0){
            fake_click(this);
            saved = true;  // if a line is under edition, save only this line, not the whole object
        }
    });
    $('.oe_form_button_save_close').each(function() {
        if(!saved && $(this).parents('div:hidden').length == 0){
            fake_click(this);
            saved = true;
        }
    });
    $('.oe_form_button_save').each(function() {
        if (! saved) {
            fake_click(this);
        }
    });
});

//Save & Edit the current object
$.ctrlshift('E', function() {
    $('.oe_form_button_save_edit').each(function() {
        fake_click(this);
    });
    $('.oe_form_button_edit').each(function() {
        fake_click(this);
    });
});

//Delete the current object
$.ctrlshift('46', function() {
    $('.oe_form_button_delete').each(function() {
        fake_click(this);
    });
});

//Cancel the modifiactions
$.ctrlshift('Z', function() {
    $('.oe_form_button_cancel').each(function() {
        fake_click(this);
    });
});

//New object
$.ctrlshift('C', function() {
    $('.oe_form_button_create').each(function() {
        fake_click(this);
    });
    $('.oe_form_button_save_create').each(function() {
        fake_click(this);
    });
});

//Duplicate the current object
$.ctrlshift('D', function() {
    $('.oe_form_button_duplicate').each(function() {
        fake_click(this);
    });
});

//Search (enter)
$.ctrlshift('13', function() {
    $('.oe_form_button_search').each(function() {
        fake_click(this);
    });
});

//Clear search
$.ctrlshift('R', function() {
    $('.oe_form_button_clear').each(function() {
        fake_click(this);
    });
});

//First object (arrow up)
$.ctrlshift('38', function(event) {
    $('.oe_button_pager[action="first"]').each(function() {
        fake_click(this);
    });
});

//Previous object (arrow right)
$.ctrlshift('37', function() {
    $('.oe_button_pager[action="previous"]').each(function() {
        fake_click(this);
    });
});

//Next object (arrow left)
$.ctrlshift('39', function() {
    $('.oe_button_pager[action="next"]').each(function() {
        fake_click(this);
    });
});

//Last object (arrow down)
$.ctrlshift('40', function() {
    $('.oe_button_pager[action="last"]').each(function() {
        fake_click(this);
    });
});

//Close ('Q')
$.ctrlshift('Q', function() {
    $('.oe_form_button_close').each(function() {
        fake_click(this);
    });
});
