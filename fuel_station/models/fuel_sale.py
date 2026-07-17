# pyrefly: ignore [missing-import]
from odoo import api, fields, models
# pyrefly: ignore [missing-import]
from odoo.exceptions import UserError, ValidationError


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

    # ── Accounting ────────────────────────────────────────────────────────────

    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Journal Entry',
        readonly=True,
        copy=False,
        help='Auto-created journal entry when the sale is recorded.',
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

    # ── Accounting: Journal Entry Creation ────────────────────────────────────

    def action_create_journal_entry(self):
        """Create a journal entry for this fuel sale.

        Debit: Receivable account (cash/card → default receivable;
               credit → fleet partner's receivable)
        Credit: Fuel income account

        Called automatically from fuel.shift → action_close_shift().
        """
        AccountMove = self.env['account.move']
        config = self.env['fuel.account.config']._get_config()
        config._check_sale_config()

        for sale in self:
            if sale.move_id:
                continue  # already has a journal entry

            if sale.subtotal <= 0:
                continue  # no revenue to record

            # Determine the debit account
            if sale.payment_method == 'credit' and sale.fleet_id.partner_id:
                # Fleet credit → use fleet partner's receivable
                debit_account = (
                    sale.fleet_id.partner_id.property_account_receivable_id
                    or config.receivable_account_id
                )
            else:
                debit_account = config.receivable_account_id

            # Build the journal entry
            move_vals = {
                'journal_id': config.journal_id.id,
                'date': sale.date,
                'ref': f'{sale.name} — {sale.fuel_type_id.name}',
                'line_ids': [
                    (0, 0, {
                        'name': f'Fuel Sale {sale.name} — '
                                f'{sale.litres_sold:.2f}L {sale.fuel_type_id.name}',
                        'account_id': debit_account.id,
                        'debit': sale.subtotal,
                        'credit': 0.0,
                        'partner_id': (
                            sale.fleet_id.partner_id.id
                            if sale.payment_method == 'credit' and sale.fleet_id.partner_id
                            else False
                        ),
                    }),
                    (0, 0, {
                        'name': f'Fuel Sale {sale.name} — '
                                f'{sale.litres_sold:.2f}L {sale.fuel_type_id.name}',
                        'account_id': config.income_account_id.id,
                        'debit': 0.0,
                        'credit': sale.subtotal,
                    }),
                ],
            }

            move = AccountMove.create(move_vals)
            move.action_post()
            sale.move_id = move

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains('litres_sold')
    def _check_litres(self):
        for sale in self:
            if sale.litres_sold < 0:
                raise ValidationError('Litres sold cannot be negative.')

    @api.constrains('payment_method', 'fleet_id')
    def _check_fleet_credit(self):
        for sale in self:
            if sale.payment_method == 'credit' and not sale.fleet_id:
                raise ValidationError(
                    'A fleet account must be selected for credit sales.'
                )

    @api.constrains('payment_method', 'fleet_id', 'fuel_type_id', 'litres_sold', 'price_per_litre')
    def _check_fleet_constraints(self):
        """Validate fleet account status, allowed fuel type, and credit limit."""
        for sale in self:
            if sale.payment_method != 'credit' or not sale.fleet_id:
                continue

            fleet = sale.fleet_id

            # 1. Fleet must be active
            if fleet.state != 'active':
                raise ValidationError(
                    f'Fleet account "{fleet.name}" is {fleet.state} and cannot '
                    f'receive credit fuel sales.'
                )

            # 2. Fuel type must be allowed (if fleet restricts it)
            if fleet.fuel_type_id and fleet.fuel_type_id != sale.fuel_type_id:
                raise ValidationError(
                    f'Fleet account "{fleet.name}" is only allowed to use '
                    f'"{fleet.fuel_type_id.name}". '
                    f'Cannot record a sale of "{sale.fuel_type_id.name}".'
                )

            # 3. Credit limit must not be exceeded
            # Credit used is recomputed from sale_ids; for a new sale we must
            # compute the prospective total manually.
            existing_credit = sum(
                s.subtotal
                for s in fleet.sale_ids
                if s.payment_method == 'credit' and s.id != sale.id
            )
            this_subtotal = sale.litres_sold * sale.price_per_litre
            prospective_used = existing_credit + this_subtotal
            if fleet.credit_limit and prospective_used > fleet.credit_limit:
                raise ValidationError(
                    f'This sale of {this_subtotal:.2f} would exceed the credit limit '
                    f'of fleet account "{fleet.name}". '
                    f'Current used: {existing_credit:.2f}, Limit: {fleet.credit_limit:.2f}.'
                )
