import base64
import io
# pyrefly: ignore [missing-import]
from odoo import api, fields, models
# pyrefly: ignore [missing-import]
from odoo.exceptions import UserError
# pyrefly: ignore [missing-import]
import xlsxwriter


class FuelReportWizard(models.TransientModel):
    """Wizard to generate Excel reports for Fuel Station operations."""

    _name = 'fuel.report.wizard'
    _description = 'Fuel Station Report Wizard'

    report_type = fields.Selection(
        string='Report Type',
        selection=[
            ('sales', 'Sales Data Report'),
            ('shifts', 'Shifts Reconciliation Summary'),
            ('purchases', 'Procurement & Deliveries'),
            ('stock', 'Current Tank Stock Status'),
        ],
        required=True,
        default='sales',
    )
    date_from = fields.Date(
        string='Start Date',
        default=fields.Date.context_today,
    )
    date_to = fields.Date(
        string='End Date',
        default=fields.Date.context_today,
    )
    excel_file = fields.Binary(
        string='Excel File',
        readonly=True,
    )
    excel_filename = fields.Char(
        string='Excel Filename',
        readonly=True,
    )

    def action_generate_excel(self):
        self.ensure_one()
        
        # Validate date range
        if self.report_type in ['sales', 'shifts', 'purchases'] and self.date_from > self.date_to:
            raise UserError('Start Date cannot be later than End Date.')

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # Format presets
        title_format = workbook.add_format({
            'bold': True, 'font_size': 16, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Arial'
        })
        subtitle_format = workbook.add_format({
            'font_size': 10, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Arial', 'italic': True
        })
        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#366092', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Arial'
        })
        cell_format = workbook.add_format({'border': 1, 'valign': 'vcenter', 'font_name': 'Arial'})
        num_format = workbook.add_format({'border': 1, 'num_format': '#,##0.00', 'align': 'right', 'font_name': 'Arial'})
        price_format = workbook.add_format({'border': 1, 'num_format': '#,##0.000', 'align': 'right', 'font_name': 'Arial'})
        date_format = workbook.add_format({'border': 1, 'num_format': 'yyyy-mm-dd', 'align': 'center', 'font_name': 'Arial'})
        
        sheet_title = dict(self._fields['report_type'].selection).get(self.report_type)
        worksheet = workbook.add_worksheet(sheet_title[:31])
        worksheet.set_row(0, 25)
        worksheet.set_row(1, 18)

        # ── SALES REPORT ──────────────────────────────────────────────────────
        if self.report_type == 'sales':
            worksheet.merge_range('A1:H1', 'FUEL SALES DATA REPORT', title_format)
            worksheet.merge_range('A2:H2', f'Period: {self.date_from} to {self.date_to}', subtitle_format)
            
            headers = [
                'Sale Ref', 'Date', 'Nozzle', 'Fuel Type', 
                'Litres Sold', 'Price/Litre', 'Payment Method', 'Subtotal'
            ]
            for col, h in enumerate(headers):
                worksheet.write(3, col, h, header_format)
            
            sales = self.env['fuel.sale'].search([
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to)
            ], order='date desc, id desc')
            
            row = 4
            for s in sales:
                worksheet.write(row, 0, s.name, cell_format)
                worksheet.write(row, 1, s.date, date_format)
                worksheet.write(row, 2, s.nozzle_id.name or '', cell_format)
                worksheet.write(row, 3, s.fuel_type_id.name or '', cell_format)
                worksheet.write(row, 4, s.litres_sold, num_format)
                worksheet.write(row, 5, s.price_per_litre, price_format)
                worksheet.write(row, 6, dict(s._fields['payment_method'].selection).get(s.payment_method) or '', cell_format)
                worksheet.write(row, 7, s.subtotal, num_format)
                row += 1
            
            # Totals
            worksheet.write(row, 3, 'Total', header_format)
            worksheet.write_formula(row, 4, f'=SUM(E5:E{row})', num_format)
            worksheet.write(row, 5, '', num_format)
            worksheet.write(row, 6, '', num_format)
            worksheet.write_formula(row, 7, f'=SUM(H5:H{row})', num_format)
            
            worksheet.set_column('A:H', 15)

        # ── SHIFTS SUMMARY REPORT ─────────────────────────────────────────────
        elif self.report_type == 'shifts':
            worksheet.merge_range('A1:L1', 'SHIFTS RECONCILIATION SUMMARY', title_format)
            worksheet.merge_range('A2:L2', f'Period: {self.date_from} to {self.date_to}', subtitle_format)
            
            headers = [
                'Shift Ref', 'Date', 'Employee', 'Total Litres', 
                'Total Revenue', 'Total Expenses', 'Expected Net Cash', 
                'Actual Cash Received', 'Difference', 'Status', 'Reconciled By'
            ]
            for col, h in enumerate(headers):
                worksheet.write(3, col, h, header_format)
            
            shifts = self.env['fuel.shift'].search([
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to)
            ], order='date desc, id desc')
            
            row = 4
            for s in shifts:
                worksheet.write(row, 0, s.name, cell_format)
                worksheet.write(row, 1, s.date, date_format)
                worksheet.write(row, 2, s.employee_id.name or '', cell_format)
                worksheet.write(row, 3, s.total_litres, num_format)
                worksheet.write(row, 4, s.total_revenue, num_format)
                worksheet.write(row, 5, s.total_expenses, num_format)
                worksheet.write(row, 6, s.net_cash, num_format)
                worksheet.write(row, 7, s.cash_received, num_format)
                worksheet.write(row, 8, s.cash_difference, num_format)
                worksheet.write(row, 9, dict(s._fields['reconciliation_status'].selection).get(s.reconciliation_status) or '', cell_format)
                worksheet.write(row, 10, s.reconciled_by_id.name or '', cell_format)
                row += 1
                
            worksheet.set_column('A:K', 16)

        # ── PROCUREMENT / PURCHASES REPORT ────────────────────────────────────
        elif self.report_type == 'purchases':
            worksheet.merge_range('A1:J1', 'FUEL PROCUREMENT REPORT', title_format)
            worksheet.merge_range('A2:J2', f'Period: {self.date_from} to {self.date_to}', subtitle_format)
            
            headers = [
                'Purchase Ref', 'Order Date', 'Supplier', 'Tank', 
                'Fuel Type', 'Quantity (L)', 'Price/Litre', 'Total Cost', 
                'Actual Delivery Date', 'Status'
            ]
            for col, h in enumerate(headers):
                worksheet.write(3, col, h, header_format)
            
            purchases = self.env['fuel.purchase'].search([
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to)
            ], order='date desc, id desc')
            
            row = 4
            for p in purchases:
                worksheet.write(row, 0, p.name, cell_format)
                worksheet.write(row, 1, p.date, date_format)
                worksheet.write(row, 2, p.supplier_id.name or '', cell_format)
                worksheet.write(row, 3, p.tank_id.name or '', cell_format)
                worksheet.write(row, 4, p.fuel_type_id.name or '', cell_format)
                worksheet.write(row, 5, p.quantity, num_format)
                worksheet.write(row, 6, p.price_per_litre, price_format)
                worksheet.write(row, 7, p.total_cost, num_format)
                worksheet.write(row, 8, p.actual_delivery_date or '', date_format)
                worksheet.write(row, 9, dict(p._fields['state'].selection).get(p.state) or '', cell_format)
                row += 1
                
            worksheet.set_column('A:J', 16)

        # ── TANK STOCK STATUS REPORT ──────────────────────────────────────────
        elif self.report_type == 'stock':
            worksheet.merge_range('A1:H1', 'CURRENT TANK STOCK STATUS', title_format)
            worksheet.merge_range('A2:H2', f'As of: {fields.Date.context_today(self)}', subtitle_format)
            
            headers = [
                'Tank Name', 'Fuel Type', 'Capacity (Litres)', 
                'Current Stock (Litres)', 'Min Level (Litres)', 
                'Stock %', 'Status', 'Location'
            ]
            for col, h in enumerate(headers):
                worksheet.write(3, col, h, header_format)
            
            tanks = self.env['fuel.tank'].search([], order='name asc')
            
            row = 4
            for t in tanks:
                worksheet.write(row, 0, t.name, cell_format)
                worksheet.write(row, 1, t.fuel_type_id.name or '', cell_format)
                worksheet.write(row, 2, t.capacity, num_format)
                worksheet.write(row, 3, t.current_stock, num_format)
                worksheet.write(row, 4, t.min_level, num_format)
                worksheet.write(row, 5, t.stock_percentage, num_format)
                worksheet.write(row, 6, dict(t._fields['stock_status'].selection).get(t.stock_status) or '', cell_format)
                worksheet.write(row, 7, t.location or '', cell_format)
                row += 1
                
            worksheet.set_column('A:H', 18)

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        output.close()

        # Filename construction
        date_str = fields.Date.context_today(self).strftime('%Y%m%d')
        filename = f"{self.report_type}_report_{date_str}.xlsx"
        
        self.write({
            'excel_file': file_data,
            'excel_filename': filename
        })
        
        # Return action to keep the wizard form open and display the download link
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
