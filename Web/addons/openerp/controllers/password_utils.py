import openobject
import formencode


class ReplaceField(openobject.widgets.PasswordField):
    params = {
        'autocomplete': 'Autocomplete field',
    }
    autocomplete = 'off'
    replace_for = False

    def __init__(self, *arg, **kwargs):
        self.replace_for = kwargs['name']
        kwargs['name'] = 'show_%s' % kwargs['name']
        kwargs.setdefault('attrs', {}).update({
            'onkeydown': 'if (event.keyCode == 13) replace_pass_submit()',
            'class': 'requiredfield',
        })
        super(ReplaceField, self).__init__(*arg, **kwargs)


class DBForm(openobject.widgets.Form):
    strip_name = True
    display_string = False
    display_description = False

    def __init__(self, *args, **kw):
        super(DBForm, self).__init__(*args, **kw)

        to_add = []

        for field in self.fields:
            if isinstance(field, ReplaceField):
                to_add.append(
                    openobject.widgets.HiddenField(
                        name=field.replace_for,
                        attrs={'autocomplete': 'off'}
                    )
                )
                self.replace_password_fields[field.name] = field.replace_for

        if to_add:
            self.hidden_fields += to_add

        if self.validator is openobject.validators.DefaultValidator:
            self.validator = openobject.validators.Schema()

        for f in self.fields:
            self.validator.add_field(f.name, f.validator)

        for add in to_add:
            self.validator.add_field(add.name, formencode.validators.NotEmpty())