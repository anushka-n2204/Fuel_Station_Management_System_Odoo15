from odoo import fields, models


class FuelType(models.Model):
    _name = 'fuel.type'
    _description = 'Fuel Type'
    _order = 'name asc'

    name = fields.Char(
        string='Fuel Type',
        required=True,
    )
    code = fields.Char(
        string='Code',
        required=True,
        size=10,
        help='Short unique code, e.g. PET, DIE, PRE',
    )
    price_per_litre = fields.Float(
        string='Price per Litre',
        required=True,
        digits=(10, 3),
        help='Selling price per litre — used in sale calculations and the website fuel prices page.',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Uncheck to archive this fuel type without deleting it.',
    )

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'A fuel type with this code already exists.'),
        ('name_unique', 'UNIQUE(name)', 'A fuel type with this name already exists.'),
        ('price_positive', 'CHECK(price_per_litre >= 0)', 'Price per litre must be zero or positive.'),
    ]

    def name_get(self):
        """Display as 'Petrol (PET)' in Many2one dropdowns."""
        result = []
        for rec in self:
            result.append((rec.id, f'{rec.name} ({rec.code})'))
        return result
