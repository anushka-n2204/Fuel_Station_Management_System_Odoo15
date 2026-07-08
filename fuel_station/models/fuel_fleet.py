from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FuelFleet(models.Model):
    """Fleet customer credit account.

    Corporate or regular customers (fleet operators) who receive fuel on credit
    and settle their account periodically.  Each fleet account tracks:

    - The credit limit extended to the customer.
    - The credit used (computed from unpaid fleet sales).
    - The remaining credit balance.

    When a fuel.sale record is created with payment_method = 'credit' and
    linked to this fleet account, credit_used is recomputed automatically.
    """

    _name = 'fuel.fleet'
    _description = 'Fleet Customer Account'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    # ── Identity ──────────────────────────────────────────────────────────────

    name = fields.Char(
        string='Account Name',
        required=True,
        help='Name of the fleet customer or company.',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Contact',
        ondelete='restrict',
        help='Link to the Odoo contact/company record for this fleet customer.',
    )

    # ── Vehicle details ───────────────────────────────────────────────────────

    vehicle_reg = fields.Char(
        string='Vehicle Registration',
        help='Primary vehicle registration number for this account. '
             'For multi-vehicle fleets, use the account name and add notes below.',
    )
    fuel_type_id = fields.Many2one(
        comodel_name='fuel.type',
        string='Allowed Fuel Type',
        ondelete='restrict',
        help='If set, only this fuel type can be dispensed on credit to this account.',
    )

    # ── Credit limits ─────────────────────────────────────────────────────────

    credit_limit = fields.Float(
        string='Credit Limit',
        digits=(10, 2),
        default=0.0,
        help='Maximum outstanding balance allowed for this account.',
        tracking=True,
    )
    credit_used = fields.Float(
        string='Credit Used',
        compute='_compute_credit',
        store=True,
        digits=(10, 2),
        help='Sum of all unpaid (credit) sales linked to this fleet account.',
    )
    credit_balance = fields.Float(
        string='Credit Balance',
        compute='_compute_credit',
        store=True,
        digits=(10, 2),
        help='Remaining credit available: Credit Limit − Credit Used.',
    )

    # ── Sales history ─────────────────────────────────────────────────────────

    sale_ids = fields.One2many(
        comodel_name='fuel.sale',
        inverse_name='fleet_id',
        string='Credit Sales',
        readonly=True,
    )
    sale_count = fields.Integer(
        string='Sales',
        compute='_compute_sale_count',
    )

    # ── State ─────────────────────────────────────────────────────────────────

    state = fields.Selection(
        string='Status',
        selection=[
            ('active', 'Active'),
            ('suspended', 'Suspended'),
            ('closed', 'Closed'),
        ],
        default='active',
        required=True,
        tracking=True,
    )

    notes = fields.Text(string='Notes')

    # ── Computed methods ──────────────────────────────────────────────────────

    @api.depends('sale_ids.subtotal', 'sale_ids.payment_method', 'credit_limit')
    def _compute_credit(self):
        for fleet in self:
            credit_sales = fleet.sale_ids.filtered(
                lambda s: s.payment_method == 'credit'
            )
            used = sum(credit_sales.mapped('subtotal'))
            fleet.credit_used = used
            fleet.credit_balance = fleet.credit_limit - used

    def _compute_sale_count(self):
        for fleet in self:
            fleet.sale_count = len(fleet.sale_ids)

    # ── Smart button: view sales ──────────────────────────────────────────────

    def action_view_sales(self):
        self.ensure_one()
        return {
            'name': f'Credit Sales — {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'fuel.sale',
            'view_mode': 'tree,form',
            'domain': [('fleet_id', '=', self.id)],
            'context': {
                'default_fleet_id': self.id,
                'default_payment_method': 'credit',
            },
        }

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains('credit_limit')
    def _check_credit_limit(self):
        for fleet in self:
            if fleet.credit_limit < 0:
                raise ValidationError('Credit limit cannot be negative.')

    _sql_constraints = [
        (
            'name_unique',
            'UNIQUE(name)',
            'A fleet account with this name already exists.',
        ),
    ]
