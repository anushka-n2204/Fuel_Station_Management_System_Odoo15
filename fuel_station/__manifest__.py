{
    'name': 'Fuel Station Management System',
    'version': '15.0.1.0.0',
    'category': 'Operations',
    'summary': 'Complete fuel station management — tanks, pumps, shifts, sales, fleet, and accounting.',
    'description': """
Fuel Station Management System
================================
Manages the full operations of a fuel station:
- Fuel types, underground tanks, pumps, and nozzles
- Shift management with meter readings
- Sales calculated automatically from meter differences
- Fuel purchases with tank stock updates
- Expenses per shift
- Fleet vehicle credit accounts
- PDF and Excel reports
- Accounting journal entries
- Odoo Website with customer portal
    """,
    'author': 'Fuel Station Dev Team',
    'website': '',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'mail',
        'account',
        'portal',
        'website',
    ],

    'data': [
        # Sequences — must come first so auto-numbering is available
        'data/sequences.xml',

        # Security — must come before views
        'security/ir.model.access.csv',

        # Views
        'views/fuel_type_views.xml',
        'views/fuel_tank_views.xml',
        'views/fuel_pump_views.xml',
        'views/fuel_nozzle_views.xml',
        'views/fuel_shift_views.xml',
        'views/fuel_sale_views.xml',
        'views/fuel_purchase_views.xml',
        'views/fuel_fleet_views.xml',
        'views/fuel_account_config_views.xml',
        'views/reports.xml',
        'views/report_templates.xml',
        'views/fuel_report_wizard_views.xml',
        'views/menu.xml',
    ],

    'application': True,
    'installable': True,
    'auto_install': False,
}
