# pyrefly: ignore [missing-import]
from odoo.tests.common import TransactionCase
# pyrefly: ignore [missing-import]
from odoo.exceptions import ValidationError, UserError
# pyrefly: ignore [missing-import]
from odoo import fields


class TestFuelStation(TransactionCase):
    """Integration test suite for the Fuel Station operations and safety constraints.

    Covers shift workflows, nozzle meters, tank stock changes, fleet limits,
    and cash reconciliation.
    """

    def setUp(self):
        super(TestFuelStation, self).setUp()

        # 1. Create a Fuel Type
        self.fuel_type = self.env['fuel.type'].create({
            'name': 'Test Petrol',
            'code': 'TP95',
            'price_per_litre': 100.0,
        })

        # 2. Create a Tank
        self.tank = self.env['fuel.tank'].create({
            'name': 'Test Tank',
            'fuel_type_id': self.fuel_type.id,
            'capacity': 10000.0,
            'current_stock': 5000.0,
            'min_level': 1000.0,
        })

        # 3. Create a Pump
        self.pump = self.env['fuel.pump'].create({
            'name': 'Test Pump',
        })

        # 4. Create a Nozzle
        self.nozzle = self.env['fuel.nozzle'].create({
            'name': 'Test Nozzle',
            'pump_id': self.pump.id,
            'fuel_type_id': self.fuel_type.id,
            'current_meter': 1000.0,
        })

        # 5. Create a Partner and Fleet Account
        self.partner = self.env['res.partner'].create({
            'name': 'Test Logistics LLC',
        })
        self.fleet = self.env['fuel.fleet'].create({
            'name': 'Test Fleet',
            'partner_id': self.partner.id,
            'credit_limit': 10000.0,
            'state': 'active',
        })

        # Set employee
        self.employee = self.env['res.users'].create({
            'name': 'Shift Operator',
            'login': 'operator1',
            'email': 'operator@test.com',
        })

    def test_01_shift_workflow(self):
        """Test a complete shift workflow: open, record meter readings, close, lock."""
        # Create draft shift
        shift = self.env['fuel.shift'].create({
            'employee_id': self.employee.id,
            'date': fields.Date.context_today(self),
        })
        self.assertEqual(shift.state, 'draft')

        # Open shift
        shift.action_open_shift()
        self.assertEqual(shift.state, 'open')
        self.assertEqual(len(shift.shift_line_ids), 1)
        self.assertEqual(shift.shift_line_ids[0].opening_meter, 1000.0)
        self.assertEqual(shift.shift_line_ids[0].price_per_litre, 100.0)

        # Try closing without meter readings - should raise UserError
        with self.assertRaises(UserError):
            shift.action_close_shift()

        # Try recording negative or rollback closing meter - should raise ValidationError
        with self.assertRaises(ValidationError):
            shift.shift_line_ids[0].write({'closing_meter': 900.0})

        # Record valid meter reading (dispense 50 Litres)
        shift.shift_line_ids[0].write({'closing_meter': 1050.0})
        self.assertEqual(shift.shift_line_ids[0].litres_sold, 50.0)
        self.assertEqual(shift.shift_line_ids[0].revenue, 5000.0)

        # Close shift
        shift.action_close_shift()
        self.assertEqual(shift.state, 'closed')

        # Verify nozzle cumulative meter updated
        self.assertEqual(self.nozzle.current_meter, 1050.0)

        # Verify tank stock depleted
        self.assertEqual(self.tank.current_stock, 4950.0)

        # Verify sales record automatically created
        self.assertEqual(len(shift.sale_ids), 1)
        sale = shift.sale_ids[0]
        self.assertEqual(sale.litres_sold, 50.0)
        self.assertEqual(sale.subtotal, 5000.0)

        # Try locking without actual cash received input - should raise UserError
        with self.assertRaises(UserError):
            shift.action_lock_shift()

        # Record actual cash received (Balanced)
        shift.write({'cash_received': 5000.0})
        self.assertEqual(shift.reconciliation_status, 'reconciled')
        self.assertEqual(shift.cash_difference, 0.0)

        # Lock shift
        shift.action_lock_shift()
        self.assertEqual(shift.state, 'locked')
        self.assertEqual(shift.reconciled_by_id, self.env.user)

    def test_02_fleet_constraints(self):
        """Test fleet limits: active validation, type restrictions, credit overrun."""
        # 1. Allowed fuel type validation
        self.fleet.write({'fuel_type_id': self.fuel_type.id})
        other_fuel = self.env['fuel.type'].create({
            'name': 'Other Fuel',
            'code': 'OTH',
            'price_per_litre': 80.0,
        })

        # Trying to record credit sale with disallowed fuel type should raise ValidationError
        with self.assertRaises(ValidationError):
            self.env['fuel.sale'].create({
                'fleet_id': self.fleet.id,
                'fuel_type_id': other_fuel.id,
                'payment_method': 'credit',
                'litres_sold': 10.0,
                'price_per_litre': 80.0,
            })

        # 2. Status validation: suspended account
        self.fleet.write({'state': 'suspended'})
        with self.assertRaises(ValidationError):
            self.env['fuel.sale'].create({
                'fleet_id': self.fleet.id,
                'fuel_type_id': self.fuel_type.id,
                'payment_method': 'credit',
                'litres_sold': 10.0,
                'price_per_litre': 100.0,
            })
        self.fleet.write({'state': 'active'})

        # 3. Credit limit overrun validation
        # Self fleet credit limit is 10,000. Trying to record sale of 10,100 (101 Litres) should fail.
        with self.assertRaises(ValidationError):
            self.env['fuel.sale'].create({
                'fleet_id': self.fleet.id,
                'fuel_type_id': self.fuel_type.id,
                'payment_method': 'credit',
                'litres_sold': 101.0,
                'price_per_litre': 100.0,
            })

    def test_03_purchase_and_stock_replenishment(self):
        """Test fuel purchases: PO confirmation, delivery stock updates, overfill checks, and vendor bills."""
        supplier = self.env['res.partner'].create({
            'name': 'Global Oil Corp',
            'supplier_rank': 1,
        })

        # 1. Create draft purchase
        purchase = self.env['fuel.purchase'].create({
            'supplier_id': supplier.id,
            'tank_id': self.tank.id,
            'quantity': 1000.0,
            'price_per_litre': 80.0,
        })
        self.assertEqual(purchase.state, 'draft')
        self.assertEqual(purchase.total_cost, 80000.0)

        # 2. Confirm purchase
        purchase.action_confirm()
        self.assertEqual(purchase.state, 'confirmed')

        # 3. Try to deliver too much causing overfill (capacity = 10000, current = 5000)
        overfill_purchase = self.env['fuel.purchase'].create({
            'supplier_id': supplier.id,
            'tank_id': self.tank.id,
            'quantity': 6000.0,
            'price_per_litre': 80.0,
        })
        overfill_purchase.action_confirm()
        with self.assertRaises(UserError):
            overfill_purchase.action_deliver()

        # 4. Deliver valid amount
        initial_stock = self.tank.current_stock
        purchase.action_deliver()
        self.assertEqual(purchase.state, 'delivered')
        self.assertEqual(self.tank.current_stock, initial_stock + 1000.0)

        # 5. Create vendor bill
        purchase.action_create_vendor_bill()
        self.assertEqual(purchase.state, 'invoiced')
        self.assertTrue(purchase.move_id)
        self.assertEqual(purchase.move_id.move_type, 'in_invoice')

    def test_04_tank_stock_warning_and_cron(self):
        """Test stock warnings and the low-stock alert cron method."""
        # Setup: company email to receive alert
        self.env.company.email = 'manager@fuelstation.com'

        # Current stock is 5000. Capacity = 10000. Min level = 1000. Status should be OK.
        self.assertEqual(self.tank.stock_status, 'ok')

        # Drop stock below min_level (e.g. to 800)
        self.tank.current_stock = 800.0
        self.tank._compute_stock_percentage()
        self.assertEqual(self.tank.stock_status, 'low')

        # Drop stock below 0
        self.tank.current_stock = -100.0
        self.tank._compute_stock_percentage()
        self.assertEqual(self.tank.stock_status, 'critical')

        # Run cron alert when tank is low
        self.tank.current_stock = 500.0
        self.tank._compute_stock_percentage()

        # Clear existing mails
        self.env['mail.mail'].search([]).unlink()

        # Call cron method
        self.env['fuel.tank']._cron_low_stock_alert()

        # Check that mail has been created
        mails = self.env['mail.mail'].search([])
        self.assertEqual(len(mails), 1)
        self.assertIn('Low Stock Alert', mails[0].body_html)
        self.assertIn('Test Tank', mails[0].body_html)

