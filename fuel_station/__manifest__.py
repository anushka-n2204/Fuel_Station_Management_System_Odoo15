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
        # Security — must come first
        'security/ir.model.access.csv',

        # Views
        'views/fuel_type_views.xml',
        'views/fuel_tank_views.xml',
        'views/fuel_pump_views.xml',
        'views/fuel_nozzle_views.xml',
        'views/fuel_shift_views.xml',
        'views/fuel_sale_views.xml',
        'views/fuel_purchase_views.xml',
        'views/menu.xml',

        # Reports
        'report/shift_report.xml',
        'report/daily_sales_report.xml',
        'report/tank_level_report.xml',

        # Website
        'website/templates/home.xml',
        'website/templates/about.xml',
        'website/templates/fuel_prices.xml',
        'website/templates/contact.xml',
        'website/templates/fleet_register.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'fuel_station/static/src/css/fuel_station.css',
        ],
        'website.assets_frontend': [
            'fuel_station/static/src/css/fuel_station.css',
        ],
    },

    'application': True,
    'installable': True,
    'auto_install': False,
}
