# pyrefly: ignore [missing-import]
from odoo import api, fields, models
# pyrefly: ignore [missing-import]
from odoo.exceptions import ValidationError


class FuelTank(models.Model):
    _name = 'fuel.tank'
    _description = 'Fuel Tank'
    _order = 'name asc'

    name = fields.Char(
        string='Tank Name',
        required=True,
    )
    fuel_type_id = fields.Many2one(
        comodel_name='fuel.type',
        string='Fuel Type',
        required=True,
        ondelete='restrict',
    )
    capacity = fields.Float(
        string='Capacity (Litres)',
        required=True,
        digits=(10, 2),
        help='Maximum volume this tank can hold in litres.',
    )
    current_stock = fields.Float(
        string='Current Stock (Litres)',
        digits=(10, 2),
        default=0.0,
        help='Updated automatically when a fuel purchase is delivered.',
    )
    min_level = fields.Float(
        string='Minimum Level (Litres)',
        digits=(10, 2),
        default=0.0,
        help='Low-stock threshold. A warning is shown when stock drops below this level.',
    )
    location = fields.Char(
        string='Location',
        help='Physical location of this tank within the station.',
    )
    stock_percentage = fields.Float(
        string='Stock %',
        compute='_compute_stock_percentage',
        store=True,
        digits=(5, 1),
        help='Current stock as a percentage of total capacity.',
    )
    stock_status = fields.Selection(
        string='Status',
        compute='_compute_stock_percentage',
        store=True,
        selection=[
            ('ok', 'OK'),
            ('low', 'Low'),
            ('critical', 'Critical'),
            ('overfull', 'Overfull'),
        ],
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )

    # ── Computed fields ──────────────────────────────────────────────────────

    @api.depends('current_stock', 'capacity', 'min_level')
    def _compute_stock_percentage(self):
        for tank in self:
            if tank.capacity and tank.capacity > 0:
                pct = (tank.current_stock / tank.capacity) * 100.0
                tank.stock_percentage = pct
                if tank.current_stock < 0:
                    tank.stock_status = 'critical'
                elif tank.current_stock < tank.min_level:
                    tank.stock_status = 'low'
                elif tank.current_stock > tank.capacity:
                    tank.stock_status = 'overfull'
                else:
                    tank.stock_status = 'ok'
            else:
                tank.stock_percentage = 0.0
                tank.stock_status = 'critical'

    # ── Constraints ──────────────────────────────────────────────────────────

    @api.constrains('capacity')
    def _check_capacity(self):
        for tank in self:
            if tank.capacity <= 0:
                raise ValidationError('Tank capacity must be greater than zero.')

    @api.constrains('min_level', 'capacity')
    def _check_min_level(self):
        for tank in self:
            if tank.min_level < 0:
                raise ValidationError('Minimum level cannot be negative.')
            if tank.min_level > tank.capacity:
                raise ValidationError('Minimum level cannot exceed tank capacity.')

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'A tank with this name already exists.'),
    ]

    def name_get(self):
        """Display as 'Tank A — Petrol (PET)' in dropdowns."""
        result = []
        for rec in self:
            fuel = rec.fuel_type_id.code or ''
            result.append((rec.id, f'{rec.name} — {fuel}'))
        return result
