from odoo import _, fields, models
from odoo.exceptions import UserError


class SchoolFeeInvoiceWizard(models.TransientModel):
    _name = 'school.fee.invoice.wizard'
    _description = "Generate Tuition Invoices"

    school_year_id = fields.Many2one(
        'school.year', string="School Year", required=True,
        default=lambda self: self.env.company.current_school_year_id)
    level_ids = fields.Many2many(
        'school.level', string="Levels", help="Leave empty to invoice all the levels.")
    classroom_ids = fields.Many2many(
        'school.classroom', string="Classrooms", domain="[('school_year_id', '=', school_year_id)]",
        help="Leave empty to invoice all the classrooms.")
    date_until = fields.Date(
        string="Installments Due Until", required=True, default=fields.Date.context_today,
        help="All the installments due until this date, and not invoiced yet, are invoiced.")

    def action_generate(self):
        self.ensure_one()
        moves = self.env['school.fee.line']._generate_invoices(
            self.school_year_id, self.date_until,
            levels=self.level_ids, classrooms=self.classroom_ids)
        if not moves:
            raise UserError(_(
                "There is no invoice to create. Check that the tuition fees are defined on the "
                "levels for this school year, and that the students have a payer or a contact."))
        return {
            'name': _("Generated Invoices"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('account.view_out_invoice_tree').id, 'list'),
                (self.env.ref('account.view_move_form').id, 'form'),
            ],
            'domain': [('id', 'in', moves.ids)],
            'context': {'default_move_type': 'out_invoice'},
        }
