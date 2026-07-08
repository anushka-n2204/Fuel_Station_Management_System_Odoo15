from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class FuelPurchase(models.Model):
    """Fuel procurement record — orders placed with suppliers.

    Workflow:  draft  →  confirmed  →  delivered  →  invoiced

    On the *Deliver* action:
    - Tank current_stock is incremented by the ordered quantity.
    - State changes to 'delivered'.
    - A placeholder move_id field is available for Phase 4 vendor-bill creation.
    """

    _name = 'fuel.purchase'
    _description = 'Fuel Purchase'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name desc'

    # ── Identity ──────────────────────────────────────────────────────────────

    name = fields.Char(
        string='Purchase Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )

    # ── Parties ───────────────────────────────────────────────────────────────

    supplier_id = fields.Many2one(
        comodel_name='res.partner',
        string='Supplier',
        required=True,
        ondelete='restrict',
        domain=[('supplier_rank', '>', 0)],
        tracking=True,
    )

    # ── Dates ─────────────────────────────────────────────────────────────────

    date = fields.Date(
        string='Order Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    delivery_date = fields.Date(
        string='Expected Delivery',
        tracking=True,
    )
    actual_delivery_date = fields.Date(
        string='Actual Delivery Date',
        readonly=True,
        copy=False,
    )

    # ── Fuel & tank ───────────────────────────────────────────────────────────

    tank_id = fields.Many2one(
        comodel_name='fuel.tank',
        string='Destination Tank',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    fuel_type_id = fields.Many2one(
        comodel_name='fuel.type',
        string='Fuel Type',
        related='tank_id.fuel_type_id',
        store=True,
        readonly=True,
    )

    # ── Quantities & pricing ──────────────────────────────────────────────────

    quantity = fields.Float(
        string='Quantity (Litres)',
        digits=(10, 2),
        required=True,
    )
    price_per_litre = fields.Float(
        string='Purchase Price / Litre',
        digits=(10, 3),
        required=True,
        help='Purchase cost per litre from this supplier — not the retail price.',
    )
    total_cost = fields.Float(
        string='Total Cost',
        compute='_compute_total_cost',
        store=True,
        digits=(10, 2),
    )

    @api.depends('quantity', 'price_per_litre')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = rec.quantity * rec.price_per_litre

    # ── State ─────────────────────────────────────────────────────────────────

    state = fields.Selection(
        string='Status',
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('delivered', 'Delivered'),
            ('invoiced', 'Invoiced'),
        ],
        default='draft',
        required=True,
        copy=False,
        tracking=True,
    )

    # ── Accounting (Phase 4) ──────────────────────────────────────────────────

    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Vendor Bill',
        readonly=True,
        copy=False,
        help='Vendor bill created on delivery — populated in Phase 4.',
    )

    notes = fields.Text(string='Notes')

    # ── Workflow actions ──────────────────────────────────────────────────────

    def action_confirm(self):
        """Draft → Confirmed."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError('Only a Draft purchase can be confirmed.')
            if rec.name == 'New':
                rec.name = (
                    self.env['ir.sequence'].next_by_code('fuel.purchase') or 'New'
                )
            rec.state = 'confirmed'

    def action_deliver(self):
        """Confirmed → Delivered.

        Increments the destination tank's current_stock by the ordered quantity.
        """
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError('Only a Confirmed purchase can be marked as delivered.')

            # Guard: overfill check
            tank = rec.tank_id
            new_stock = tank.current_stock + rec.quantity
            if new_stock > tank.capacity:
                raise UserError(
                    f'Delivery of {rec.quantity:.2f} L would overfill tank '
                    f'"{tank.name}" (current stock: {tank.current_stock:.2f} L, '
                    f'capacity: {tank.capacity:.2f} L).'
                )

            tank.current_stock = new_stock
            rec.write({
                'actual_delivery_date': fields.Date.context_today(self),
                'state': 'delivered',
            })

    def action_mark_invoiced(self):
        """Delivered → Invoiced (manual step until Phase 4 auto-creates the bill)."""
        for rec in self:
            if rec.state != 'delivered':
                raise UserError('Only a Delivered purchase can be marked as invoiced.')
            rec.state = 'invoiced'

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains('quantity')
    def _check_quantity(self):
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError('Quantity must be greater than zero.')

    @api.constrains('price_per_litre')
    def _check_price(self):
        for rec in self:
            if rec.price_per_litre <= 0:
                raise ValidationError('Purchase price per litre must be greater than zero.')

    @api.constrains('delivery_date', 'date')
    def _check_delivery_date(self):
        for rec in self:
            if rec.delivery_date and rec.delivery_date < rec.date:
                raise ValidationError(
                    'Expected delivery date cannot be earlier than the order date.'
                )
