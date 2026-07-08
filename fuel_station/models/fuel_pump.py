# pyrefly: ignore [missing-import]
from odoo import fields, models


class FuelPump(models.Model):
    _name = 'fuel.pump'
    _description = 'Fuel Pump'
    _order = 'name asc'

    name = fields.Char(
        string='Pump Name',
        required=True,
    )
    tank_id = fields.Many2one(
        comodel_name='fuel.tank',
        string='Fuel Tank',
        required=True,
        ondelete='restrict',
        help='The underground tank that feeds this pump.',
    )
    location = fields.Char(
        string='Location',
        help='Physical position of this pump within the station (e.g. "Island 1 – North").',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )

    # Reverse relation — nozzles declare pump_id as Many2one
    nozzle_ids = fields.One2many(
        comodel_name='fuel.nozzle',
        inverse_name='pump_id',
        string='Nozzles',
    )

    # Convenience related field — shortcut to the tank's fuel type
    fuel_type_id = fields.Many2one(
        comodel_name='fuel.type',
        string='Fuel Type',
        related='tank_id.fuel_type_id',
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'A pump with this name already exists.'),
    ]

    def name_get(self):
        """Display as 'Pump 1 (Petrol)' in dropdowns."""
        result = []
        for rec in self:
            fuel = rec.fuel_type_id.name or ''
            result.append((rec.id, f'{rec.name} ({fuel})'))
        return result
