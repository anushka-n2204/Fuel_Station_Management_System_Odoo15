# pyrefly: ignore [missing-import]
from odoo import api, fields, models
# pyrefly: ignore [missing-import]
from odoo.exceptions import ValidationError


class FuelShiftLine(models.Model):
    """One line per nozzle per shift.

    Records the opening meter (auto-populated when the shift opens) and the
    closing meter (entered by the employee when closing the shift).  Litres
    sold and revenue are computed from these two values.
    """

    _name = 'fuel.shift.line'
    _description = 'Fuel Shift Line'
    _order = 'shift_id, nozzle_id'

    # ── Core relations ────────────────────────────────────────────────────────

    shift_id = fields.Many2one(
        comodel_name='fuel.shift',
        string='Shift',
        required=True,
        ondelete='cascade',
        index=True,
    )
    nozzle_id = fields.Many2one(
        comodel_name='fuel.nozzle',
        string='Nozzle',
        required=True,
        ondelete='restrict',
    )

    # ── Related / convenience fields ──────────────────────────────────────────

    fuel_type_id = fields.Many2one(
        comodel_name='fuel.type',
        string='Fuel Type',
        related='nozzle_id.fuel_type_id',
        store=True,
        readonly=True,
    )
    pump_id = fields.Many2one(
        comodel_name='fuel.pump',
        string='Pump',
        related='nozzle_id.pump_id',
        store=True,
        readonly=True,
    )

    # ── Meter readings ────────────────────────────────────────────────────────

    opening_meter = fields.Float(
        string='Opening Meter',
        digits=(12, 2),
        required=True,
        help='Cumulative meter reading at the start of this shift. '
             'Auto-copied from the nozzle\'s current_meter when the shift opens.',
    )
    closing_meter = fields.Float(
        string='Closing Meter',
        digits=(12, 2),
        default=0.0,
        help='Cumulative meter reading at the end of this shift. '
             'Entered by the employee before closing.',
    )

    # ── Price snapshot ────────────────────────────────────────────────────────

    price_per_litre = fields.Float(
        string='Price / Litre',
        digits=(10, 3),
        required=True,
        help='Snapshot of the fuel type\'s selling price at the time the shift '
             'was opened.  Stored so that price changes do not alter historical '
             'revenue figures.',
    )

    # ── Computed sales figures ────────────────────────────────────────────────

    litres_sold = fields.Float(
        string='Litres Sold',
        compute='_compute_sales',
        store=True,
        digits=(10, 2),
    )
    revenue = fields.Float(
        string='Revenue',
        compute='_compute_sales',
        store=True,
        digits=(10, 2),
    )

    @api.depends('opening_meter', 'closing_meter', 'price_per_litre')
    def _compute_sales(self):
        for line in self:
            diff = max(line.closing_meter - line.opening_meter, 0.0)
            line.litres_sold = diff
            line.revenue = diff * line.price_per_litre

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains('opening_meter', 'closing_meter')
    def _check_meters(self):
        for line in self:
            if line.opening_meter < 0:
                raise ValidationError(
                    f'Opening meter on nozzle "{line.nozzle_id.name}" '
                    'cannot be negative.'
                )
            # Closing meter is only validated once the shift is being closed;
            # during data entry it may still be 0.
            if line.closing_meter and line.closing_meter < line.opening_meter:
                raise ValidationError(
                    f'Closing meter ({line.closing_meter:.2f}) on nozzle '
                    f'"{line.nozzle_id.name}" must be ≥ opening meter '
                    f'({line.opening_meter:.2f}).'
                )

    _sql_constraints = [
        (
            'nozzle_shift_unique',
            'UNIQUE(shift_id, nozzle_id)',
            'A nozzle can only appear once per shift.',
        ),
    ]
