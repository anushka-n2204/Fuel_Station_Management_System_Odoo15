from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FuelExpense(models.Model):
    """Per-shift operating expense.

    Tracks costs such as electricity, staff salary advance, cash float
    shortages, maintenance, and any other station costs that are attributed
    to a specific shift.

    The parent shift's total_expenses and net_cash fields are recomputed
    whenever an expense record is created, updated, or deleted.
    """

    _name = 'fuel.expense'
    _description = 'Fuel Shift Expense'
    _order = 'shift_id, date desc'

    # ── Parent shift ──────────────────────────────────────────────────────────

    shift_id = fields.Many2one(
        comodel_name='fuel.shift',
        string='Shift',
        required=True,
        ondelete='cascade',
        index=True,
    )

    # ── Expense details ───────────────────────────────────────────────────────

    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
    )
    expense_type = fields.Selection(
        string='Expense Type',
        selection=[
            ('electricity', 'Electricity'),
            ('salary', 'Salary / Advance'),
            ('cash', 'Cash Float'),
            ('maintenance', 'Maintenance'),
            ('other', 'Other'),
        ],
        required=True,
        default='other',
    )
    description = fields.Char(
        string='Description',
        help='Short description of the expense, e.g. "Generator fuel top-up".',
    )
    amount = fields.Float(
        string='Amount',
        digits=(10, 2),
        required=True,
    )

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError('Expense amount must be greater than zero.')
