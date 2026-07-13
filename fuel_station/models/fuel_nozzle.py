# pyrefly: ignore [missing-import]
from odoo import api, fields, models
# pyrefly: ignore [missing-import]
from odoo.exceptions import ValidationError


class FuelNozzle(models.Model):
    _name = 'fuel.nozzle'
    _description = 'Fuel Nozzle'
    _order = 'pump_id, name asc'

    name = fields.Char(
        string='Nozzle Name',
        required=True,
        help='Identifier for this nozzle, e.g. "Nozzle A1", "Nozzle B2".',
    )
    pump_id = fields.Many2one(
        comodel_name='fuel.pump',
        string='Pump',
        required=True,
        ondelete='restrict',
    )
    fuel_type_id = fields.Many2one(
        comodel_name='fuel.type',
        string='Fuel Type',
        required=True,
        ondelete='restrict',
        help='Fuel type dispensed by this nozzle. May differ from the pump\'s tank for multi-product pumps.',
    )
    current_meter = fields.Float(
        string='Current Meter Reading',
        digits=(12, 2),
        default=0.0,
        help='Cumulative odometer-style reading. Updated at the close of each shift.',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )

    # Related convenience fields for display
    pump_location = fields.Char(
        string='Pump Location',
        related='pump_id.location',
        readonly=True,
        store=False,
    )

    # ── Constraints ──────────────────────────────────────────────────────────

    @api.constrains('current_meter')
    def _check_meter(self):
        for nozzle in self:
            if nozzle.current_meter < 0:
                raise ValidationError(
                    f'Meter reading for "{nozzle.name}" cannot be negative.'
                )

    _sql_constraints = [
        ('name_pump_unique', 'UNIQUE(name, pump_id)', 'Nozzle names must be unique per pump.'),
    ]

    def write(self, vals):
        if 'current_meter' in vals and not self.env.context.get('allow_nozzle_meter_update'):
            raise ValidationError(
                'The current meter reading of a nozzle can only be updated '
                'automatically by closing a shift.'
            )
        return super(FuelNozzle, self).write(vals)

    def name_get(self):
        """Display as 'Nozzle A1 – Pump 1' in dropdowns."""
        result = []
        for rec in self:
            pump = rec.pump_id.name or ''
            result.append((rec.id, f'{rec.name} – {pump}'))
        return result
