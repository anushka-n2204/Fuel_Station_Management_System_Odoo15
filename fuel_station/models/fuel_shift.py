from odoo import api, fields, models  # pyrefly: ignore [missing-import]
from odoo.exceptions import UserError, ValidationError  # pyrefly: ignore [missing-import]


class FuelShift(models.Model):
    """Employee shift — the central operations record for a fuel station.

    Workflow:  draft  →  open  →  closed  →  locked

    *  draft   : Created, nozzle lines auto-populated, but meters not yet recorded.
    *  open    : Shift is live; opening meters have been confirmed.
    *  closed  : Employee has entered closing meters; fuel.sale records have
                 been created and tank stock has been decremented.
    *  locked  : Manager has locked the record; no further edits allowed.
    """

    _name = 'fuel.shift'
    _description = 'Fuel Shift'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name desc'

    # ── Identity ──────────────────────────────────────────────────────────────

    name = fields.Char(
        string='Shift Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        help='Auto-generated sequence once the shift is opened.',
    )
    employee_id = fields.Many2one(
        comodel_name='res.users',
        string='Employee',
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    date = fields.Date(
        string='Shift Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )

    # ── Timestamps ────────────────────────────────────────────────────────────

    opening_time = fields.Datetime(
        string='Opening Time',
        readonly=True,
        copy=False,
    )
    closing_time = fields.Datetime(
        string='Closing Time',
        readonly=True,
        copy=False,
    )

    # ── State ─────────────────────────────────────────────────────────────────

    state = fields.Selection(
        string='Status',
        selection=[
            ('draft', 'Draft'),
            ('open', 'Open'),
            ('closed', 'Closed'),
            ('locked', 'Locked'),
        ],
        default='draft',
        required=True,
        copy=False,
        tracking=True,
    )

    # ── Lines ─────────────────────────────────────────────────────────────────

    shift_line_ids = fields.One2many(
        comodel_name='fuel.shift.line',
        inverse_name='shift_id',
        string='Nozzle Readings',
        copy=False,
    )
    expense_ids = fields.One2many(
        comodel_name='fuel.expense',
        inverse_name='shift_id',
        string='Expenses',
        copy=False,
    )
    sale_ids = fields.One2many(
        comodel_name='fuel.sale',
        inverse_name='shift_id',
        string='Sales',
        readonly=True,
        copy=False,
    )

    # ── Computed totals ───────────────────────────────────────────────────────

    total_litres = fields.Float(
        string='Total Litres',
        compute='_compute_totals',
        store=True,
        digits=(10, 2),
    )
    total_revenue = fields.Float(
        string='Total Revenue',
        compute='_compute_totals',
        store=True,
        digits=(10, 2),
    )
    total_expenses = fields.Float(
        string='Total Expenses',
        compute='_compute_totals',
        store=True,
        digits=(10, 2),
    )
    net_cash = fields.Float(
        string='Net Cash',
        compute='_compute_totals',
        store=True,
        digits=(10, 2),
        help='Total Revenue minus Total Expenses for this shift.',
    )
    sale_count = fields.Integer(
        string='Sales',
        compute='_compute_sale_count',
    )

    # ── Reconciliation & Manager Approval ─────────────────────────────────────
    cash_received = fields.Float(
        string='Cash Received',
        digits=(10, 2),
        default=0.0,
        tracking=True,
    )
    cash_difference = fields.Float(
        string='Cash Difference',
        compute='_compute_reconciliation',
        store=True,
        digits=(10, 2),
    )
    reconciliation_status = fields.Selection(
        string='Reconciliation Status',
        selection=[
            ('unreconciled', 'Unreconciled'),
            ('reconciled', 'Reconciled'),
        ],
        compute='_compute_reconciliation',
        store=True,
        default='unreconciled',
    )
    reconciled_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Reconciled By',
        readonly=True,
    )

    notes = fields.Text(
        string='Manager Notes',
    )

    # ── Computed methods ──────────────────────────────────────────────────────

    @api.depends('shift_line_ids.litres_sold', 'shift_line_ids.revenue',
                 'expense_ids.amount')
    def _compute_totals(self):
        for shift in self:
            shift.total_litres = sum(shift.shift_line_ids.mapped('litres_sold'))
            shift.total_revenue = sum(shift.shift_line_ids.mapped('revenue'))
            shift.total_expenses = sum(shift.expense_ids.mapped('amount'))
            shift.net_cash = shift.total_revenue - shift.total_expenses

    def _compute_sale_count(self):
        for shift in self:
            shift.sale_count = len(shift.sale_ids)

    @api.depends('net_cash', 'cash_received')
    def _compute_reconciliation(self):
        for shift in self:
            if shift.cash_received > 0:
                shift.cash_difference = shift.net_cash - shift.cash_received
                shift.reconciliation_status = 'reconciled'
            else:
                shift.cash_difference = shift.net_cash
                shift.reconciliation_status = 'unreconciled'

    # ── Action: Open Shift ────────────────────────────────────────────────────

    def action_open_shift(self):
        """Transition draft → open.

        Steps:
        1. Assign a sequence number.
        2. Auto-populate shift lines from all active nozzles (if not already present).
        3. Snapshot opening meter and price per litre from each nozzle / fuel type.
        4. Record opening_time.
        """
        for shift in self:
            if shift.state != 'draft':
                raise UserError('Only a Draft shift can be opened.')

            # 1. Assign sequence
            if shift.name == 'New':
                shift.name = self.env['ir.sequence'].next_by_code('fuel.shift') or 'New'

            # 2. Auto-populate nozzle lines (all active nozzles not already added)
            existing_nozzle_ids = shift.shift_line_ids.mapped('nozzle_id').ids
            active_nozzles = self.env['fuel.nozzle'].search([
                ('active', '=', True),
                ('id', 'not in', existing_nozzle_ids),
            ])
            lines_to_create = []
            for nozzle in active_nozzles:
                lines_to_create.append({
                    'shift_id': shift.id,
                    'nozzle_id': nozzle.id,
                    'opening_meter': nozzle.current_meter,
                    'price_per_litre': nozzle.fuel_type_id.price_per_litre,
                })
            if lines_to_create:
                self.env['fuel.shift.line'].create(lines_to_create)

            # 3. Record timestamp and set state
            shift.write({
                'opening_time': fields.Datetime.now(),
                'state': 'open',
            })

    # ── Action: Close Shift ───────────────────────────────────────────────────

    def action_close_shift(self):
        """Transition open → closed.

        Steps:
        1. Validate all closing meters are entered and ≥ opening meters.
        2. Create one fuel.sale record per shift line.
        3. Decrement tank stock for each nozzle's parent tank.
        4. Update each nozzle's current_meter to the closing value.
        5. Record closing_time.
        """
        FuelSale = self.env['fuel.sale']

        for shift in self:
            if shift.state != 'open':
                raise UserError('Only an Open shift can be closed.')

            # 1. Validate closing meters
            for line in shift.shift_line_ids:
                if not line.closing_meter:
                    raise UserError(
                        f'Please enter the closing meter for nozzle '
                        f'"{line.nozzle_id.name}" before closing the shift.'
                    )
                if line.closing_meter < line.opening_meter:
                    raise UserError(
                        f'Closing meter ({line.closing_meter:.2f}) for nozzle '
                        f'"{line.nozzle_id.name}" cannot be less than the '
                        f'opening meter ({line.opening_meter:.2f}).'
                    )

            # 2. Pre-validate stock sufficiency across ALL lines before any write.
            #    Accumulate total litres demanded per tank so that multi-nozzle
            #    tanks (several nozzles drawing from the same tank) are checked
            #    as a whole, not line-by-line.
            tank_demand = {}  # {tank_id: total_litres_demanded}
            for line in shift.shift_line_ids:
                litres = line.closing_meter - line.opening_meter
                tank = line.nozzle_id.pump_id.tank_id
                if tank:
                    tank_demand[tank] = tank_demand.get(tank, 0.0) + litres

            for tank, demanded in tank_demand.items():
                if demanded > tank.current_stock:
                    raise UserError(
                        f'Cannot close shift: tank "{tank.name}" has only '
                        f'{tank.current_stock:.2f} L available but '
                        f'{demanded:.2f} L were dispensed through its nozzles. '
                        f'Please verify the meter readings or replenish the tank '
                        f'before closing.'
                    )

            # 3 & 4 & 5. All tanks have sufficient stock — apply writes.
            for line in shift.shift_line_ids:
                litres = line.closing_meter - line.opening_meter

                # Create sale record
                FuelSale.create({
                    'shift_id': shift.id,
                    'date': shift.date,
                    'nozzle_id': line.nozzle_id.id,
                    'fuel_type_id': line.fuel_type_id.id,
                    'litres_sold': litres,
                    'price_per_litre': line.price_per_litre,
                    'payment_method': 'cash',
                })

                # Decrement tank stock via the nozzle → pump → tank chain
                tank = line.nozzle_id.pump_id.tank_id
                if tank:
                    tank.current_stock -= litres

                # Update nozzle current meter (bypass read-only restriction in write)
                line.nozzle_id.with_context(allow_nozzle_meter_update=True).write({
                    'current_meter': line.closing_meter
                })

            # 5. Record timestamp and set state
            shift.write({
                'closing_time': fields.Datetime.now(),
                'state': 'closed',
            })

    # ── Action: Lock Shift ────────────────────────────────────────────────────

    def action_lock_shift(self):
        """Transition closed → locked (manager approval)."""
        for shift in self:
            if shift.state != 'closed':
                raise UserError('Only a Closed shift can be locked.')
            if not shift.cash_received or shift.cash_received <= 0:
                raise UserError(
                    'Please record the actual cash received before locking the shift.'
                )
            shift.write({
                'state': 'locked',
                'reconciled_by_id': self.env.user.id,
            })

    # ── Action: View Sales ────────────────────────────────────────────────────

    def action_view_sales(self):
        """Open the list of fuel.sale records for this shift."""
        self.ensure_one()
        return {
            'name': f'Sales — {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'fuel.sale',
            'view_mode': 'tree,form',
            'domain': [('shift_id', '=', self.id)],
            'context': {'default_shift_id': self.id},
        }

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains('date')
    def _check_date(self):
        for shift in self:
            if not shift.date:
                raise ValidationError('Shift date is required.')
