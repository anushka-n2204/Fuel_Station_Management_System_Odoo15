from odoo import api, fields, models


class FuelSale(models.Model):
    """Individual fuel sale record.

    Created automatically when a shift is closed (one record per shift line).
    Can also be created manually for walk-in cash/card sales if needed.

    Fleet credit sales link to a fuel.fleet account; the credit_used on that
    account is computed from unpaid fleet sales.
    """

    _name = 'fuel.sale'
    _description = 'Fuel Sale'
    _inherit = ['mail.thread']
    _order = 'date desc, name desc'

    # ── Identity ──────────────────────────────────────────────────────────────

    name = fields.Char(
        string='Sale Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )

    # ── Core relations ────────────────────────────────────────────────────────

    shift_id = fields.Many2one(
        comodel_name='fuel.shift',
        string='Shift',
        ondelete='restrict',
        index=True,
        tracking=True,
    )
    date = fields.Date(
        string='Sale Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    nozzle_id = fields.Many2one(
        comodel_name='fuel.nozzle',
        string='Nozzle',
        ondelete='restrict',
    )
    fuel_type_id = fields.Many2one(
        comodel_name='fuel.type',
        string='Fuel Type',
        required=True,
        ondelete='restrict',
        tracking=True,
    )

    # ── Quantities & price ────────────────────────────────────────────────────

    litres_sold = fields.Float(
        string='Litres Sold',
        digits=(10, 2),
        required=True,
    )
    price_per_litre = fields.Float(
        string='Price / Litre',
        digits=(10, 3),
        required=True,
        help='Price snapshot at the time of the shift — historical value, '
             'not recalculated if fuel prices change later.',
    )
    subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True,
        digits=(10, 2),
    )

    @api.depends('litres_sold', 'price_per_litre')
    def _compute_subtotal(self):
        for sale in self:
            sale.subtotal = sale.litres_sold * sale.price_per_litre

    # ── Payment ───────────────────────────────────────────────────────────────

    payment_method = fields.Selection(
        string='Payment Method',
        selection=[
            ('cash', 'Cash'),
            ('card', 'Card'),
            ('credit', 'Fleet Credit'),
        ],
        default='cash',
        required=True,
        tracking=True,
    )
    fleet_id = fields.Many2one(
        comodel_name='fuel.fleet',
        string='Fleet Account',
        ondelete='restrict',
        help='Populated only for fleet credit sales.',
    )

    # ── Accounting (Phase 4) ──────────────────────────────────────────────────

    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Journal Entry',
        readonly=True,
        copy=False,
        help='Auto-created journal entry (populated in Phase 4 accounting '
             'integration).',
    )

    # ── Sequence assignment ───────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('fuel.sale') or 'New'
                )
        return super().create(vals_list)

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains('litres_sold')
    def _check_litres(self):
        for sale in self:
            if sale.litres_sold < 0:
                from odoo.exceptions import ValidationError
                raise ValidationError('Litres sold cannot be negative.')

    @api.constrains('payment_method', 'fleet_id')
    def _check_fleet_credit(self):
        for sale in self:
            if sale.payment_method == 'credit' and not sale.fleet_id:
                from odoo.exceptions import ValidationError
                raise ValidationError(
                    'A fleet account must be selected for credit sales.'
                )
