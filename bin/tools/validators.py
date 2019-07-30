
from tools.translate import _
import re
import formencode.validators


# (Taken from unifield-web/addons/openerp/validators.py)
class Email(formencode.validators.Email):
    if_empty = False

    domainRE = re.compile(r'''
        (^(?:[a-z0-9][a-z0-9\-]{0,62}\.)+ # (sub)domain - alpha followed by 62max chars (63 total)
        [a-z]{2,}[\s,.]*$)*                     # TLD
    ''', re.I | re.VERBOSE)

    def _from_python(self, value, state):
        return value or ''

    def validate_python(self, value, state):
        if '<' in value and '>' in value:
            value = value[value.index('<') + 1:value.index('>')]
        super(Email, self).validate_python(value, state)



def validate_email(email):
    """
    Test if a given email is valid

    Returns (True, None) if valid,
    otherwise returns (False, <the error>)
    """

    try:
        Email().validate_python(email, None)
        return (True, None)
    except Exception as e:
        return (False, str(e))



# Let some FormEncode strings goes into message catalog.
__email_messages = {
    'empty': _('Please enter an email address'),
    'noAt': _('An email address must contain a single @'),
    'badUsername': _('The username portion of the email address is invalid (the portion before the @: %(username)s)'),
    'badDomain': _('The domain portion of the email address is invalid (the portion after the @: %(domain)s)'),
}

