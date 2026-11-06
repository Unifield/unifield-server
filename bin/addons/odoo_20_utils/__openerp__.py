# ruff: noqa: B018
# pylint: disable=C8101,C8102,C8103,C8106,C8112
{
    "name": "Odoo 18 Utils",
    "version": "1.0",
    "author": "TeMPO Consulting",
    "category": "Others",
    "description": """
        Utils to help with a migration to Odoo 20
    """,
    "website": "http://unifield.msf.org",
    "depends": [
        "msf_profile",
    ],
    "update_xml": [
        "model_columns_view.xml",
    ],
    "installable": True,
    "active": False,
}
