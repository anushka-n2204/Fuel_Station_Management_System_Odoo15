# pyrefly: ignore [missing-import]
from odoo import api, fields, models
# pyrefly: ignore [missing-import]
from odoo.exceptions import UserError, ValidationError


class FuelPurchase(models.Model):
    """Fuel procurement record — orders placed with suppliers.

    Workflow:  draft  →  confirmed  →  delivered  →  invoiced

    On the *Deliver* action:
    - Tank current_stock is incremented by the ordered quantity.
    - A draft vendor bill is auto-created via ``action_create_vendor_bill()``.
    - State changes to 'delivered'.

    On the *Post Bill* action:
    - The linked vendor bill is posted.
    - State changes to 'invoiced'.
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

    # ── Accounting ────────────────────────────────────────────────────────────

    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Vendor Bill',
        readonly=True,
        copy=False,
        help='Draft vendor bill auto-created when fuel is delivered.',
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

        Increments the destination tank's current_stock by the ordered quantity
        and auto-creates a draft vendor bill.
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

            # Auto-create vendor bill
            try:
                rec.action_create_vendor_bill()
            except UserError:
                # Accounting not configured — log in chatter, don't block delivery
                rec.message_post(
                    body='⚠️ Vendor bill was NOT created — accounting settings '
                         'are not fully configured. Go to Fuel Station → '
                         'Configuration → Accounting Settings to set up '
                         'purchase accounting.',
                    message_type='notification',
                )

    def action_mark_invoiced(self):
        """Delivered → Invoiced.

        Posts the linked vendor bill (if it exists and is in draft).
        """
        for rec in self:
            if rec.state != 'delivered':
                raise UserError('Only a Delivered purchase can be marked as invoiced.')
            if not rec.move_id:
                raise UserError('No vendor bill is linked to this purchase. Please create a vendor bill first.')
            if rec.move_id.state == 'draft':
                rec.move_id.action_post()
            rec.state = 'invoiced'

    # ── Accounting: Vendor Bill Creation ──────────────────────────────────────

    def action_create_vendor_bill(self):
        """Create a draft vendor bill for this fuel purchase.

        Uses the purchase journal and expense account from fuel.account.config.
        Called automatically from action_deliver().
        """
        AccountMove = self.env['account.move']
        config = self.env['fuel.account.config']._get_config()
        config._check_purchase_config()

        for rec in self:
            if rec.move_id:
                continue  # already has a vendor bill

            move_vals = {
                'move_type': 'in_invoice',
                'journal_id': config.purchase_journal_id.id,
                'partner_id': rec.supplier_id.id,
                'invoice_date': rec.actual_delivery_date or rec.date,
                'ref': f'{rec.name} — {rec.fuel_type_id.name}',
                'invoice_line_ids': [
                    (0, 0, {
                        'name': f'Fuel Purchase — {rec.quantity:.2f}L '
                                f'{rec.fuel_type_id.name}',
                        'account_id': config.expense_account_id.id,
                        'quantity': rec.quantity,
                        'price_unit': rec.price_per_litre,
                    }),
                ],
            }

            move = AccountMove.create(move_vals)
            rec.move_id = move

    # ── Smart button: View Vendor Bill ────────────────────────────────────────

    def action_view_bill(self):
        """Open the linked vendor bill."""
        self.ensure_one()
        if not self.move_id:
            raise UserError('No vendor bill is linked to this purchase.')
        return {
            'name': f'Vendor Bill — {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

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
