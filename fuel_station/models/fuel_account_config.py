# pyrefly: ignore [missing-import]
from odoo import api, fields, models
# pyrefly: ignore [missing-import]
from odoo.exceptions import UserError


class FuelAccountConfig(models.Model):
    """Singleton accounting configuration for the Fuel Station module.

    Stores the default journals and accounts used when auto-creating
    journal entries (fuel sales) and vendor bills (fuel purchases).

    Only one record should exist; the ``_get_config()`` class method
    returns it (creating it on first access).
    """

    _name = 'fuel.account.config'
    _description = 'Fuel Station Accounting Settings'

    name = fields.Char(
        string='Name',
        default='Fuel Station Accounting Settings',
        readonly=True,
    )

    # ── Sales accounting ─────────────────────────────────────────────────────

    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Sales Journal',
        domain=[('type', '=', 'sale')],
        help='Journal used for fuel sale journal entries.',
    )
    income_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Fuel Income Account',
        help='Revenue account credited when a fuel sale is recorded. '
             'E.g. "Fuel Sales Revenue".',
    )
    receivable_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Default Receivable Account',
        help='Account debited for cash and card fuel sales. '
             'For fleet credit sales the partner receivable is used instead.',
    )

    # ── Purchase accounting ──────────────────────────────────────────────────

    purchase_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Purchase Journal',
        domain=[('type', '=', 'purchase')],
        help='Journal used for fuel purchase vendor bills.',
    )
    expense_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Fuel Expense / COGS Account',
        help='Cost account for fuel purchases (Cost of Goods Sold). '
             'Debited on the vendor bill line.',
    )
    payable_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Default Payable Account',
        help="Supplier payable account. If left empty the supplier partner's "
             "default payable is used.",
    )

    # ── Singleton accessor ───────────────────────────────────────────────────

    @api.model
    def _get_config(self):
        """Return the singleton config record, creating it if needed."""
        config = self.search([], limit=1)
        if not config:
            config = self.create({'name': 'Fuel Station Accounting Settings'})
        return config

    def action_open_config(self):
        """Menu action — opens the singleton form."""
        config = self._get_config()
        return {
            'name': 'Fuel Station Accounting Settings',
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': config.id,
            'view_mode': 'form',
            'target': 'inline',
        }

    # ── Validation helpers ───────────────────────────────────────────────────

    def _check_sale_config(self):
        """Raise UserError if sales accounting is not fully configured."""
        if not self.journal_id or not self.income_account_id or not self.receivable_account_id:
            raise UserError(
                'Fuel Station accounting is not fully configured.\n\n'
                'Please go to Fuel Station → Configuration → Accounting Settings '
                'and set the Sales Journal, Fuel Income Account, and '
                'Default Receivable Account.'
            )

    def _check_purchase_config(self):
        """Raise UserError if purchase accounting is not fully configured."""
        if not self.purchase_journal_id or not self.expense_account_id:
            raise UserError(
                'Fuel Station accounting is not fully configured.\n\n'
                'Please go to Fuel Station → Configuration → Accounting Settings '
                'and set the Purchase Journal and Fuel Expense / COGS Account.'
            )
