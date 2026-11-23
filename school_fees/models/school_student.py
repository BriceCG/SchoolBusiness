from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SchoolStudent(models.Model):
    _inherit = 'school.student'

    payer_id = fields.Many2one(
        'res.partner', string="Payer", tracking=True,
        help="Parent or guardian who pays the school fees. The invoices are addressed to "
             "this contact (or to the student contact when empty).")
    fee_installments = fields.Integer(
        string="Number of Payments", required=True, tracking=True,
        default=lambda self: self.env.company.school_default_installments or 1,
        help="Number of payments chosen to pay the tuition of the school year. "
             "One invoice is created for each payment.")
    invoice_ids = fields.One2many(
        'account.move', 'student_id', string="Invoices",
        domain=[('move_type', '=', 'out_invoice')])
    invoice_count = fields.Integer(string="Invoices", compute='_compute_invoice_amounts')
    currency_id = fields.Many2one(related='company_id.currency_id')
    amount_invoiced = fields.Monetary(
        string="Total Invoiced", compute='_compute_invoice_amounts', currency_field='currency_id',
        help="Total of the invoices of the student, including the draft ones.")
    amount_due = fields.Monetary(
        string="Amount Due", compute='_compute_invoice_amounts', currency_field='currency_id',
        help="Remaining amount to pay on the validated invoices.")

    @api.constrains('fee_installments', 'school_year_id')
    def _check_fee_installments(self):
        for rec in self:
            year = rec.school_year_id
            if rec.fee_installments < 1:
                raise ValidationError(_("The number of payments must be strictly positive."))
            if year.date_start and year.date_end:
                months = (year.date_end.year - year.date_start.year) * 12                     + year.date_end.month - year.date_start.month + 1
                if rec.fee_installments > months:
                    raise ValidationError(_(
                        "The number of payments cannot exceed the number of months of the "
                        "school year (%s).", months))

    def write(self, vals):
        if 'fee_installments' in vals:
            for rec in self.filtered(lambda s: s.fee_installments != vals['fee_installments']):
                if rec.invoice_ids.filtered(lambda m: m.fee_line_id and m.state != 'cancel'):
                    raise UserError(_(
                        "The tuition of %s is already invoiced. Cancel the invoices before "
                        "changing the number of payments.", rec.name))
        return super().write(vals)

    @api.depends('invoice_ids.state', 'invoice_ids.amount_total_signed',
                 'invoice_ids.amount_residual_signed')
    def _compute_invoice_amounts(self):
        for rec in self:
            invoices = rec.invoice_ids.filtered(lambda m: m.state != 'cancel')
            rec.invoice_count = len(invoices)
            rec.amount_invoiced = sum(invoices.mapped('amount_total_signed'))
            rec.amount_due = sum(
                invoices.filtered(lambda m: m.state == 'posted').mapped('amount_residual_signed'))

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'name': _("Invoices"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('account.view_out_invoice_tree').id, 'list'),
                (self.env.ref('account.view_move_form').id, 'form'),
            ],
            'domain': [('student_id', '=', self.id), ('move_type', '=', 'out_invoice')],
            'context': {
                'default_move_type': 'out_invoice',
                'default_student_id': self.id,
                'default_partner_id': (self.payer_id or self.partner_id).id,
            },
        }

    def action_generate_invoices(self):
        """Create the draft invoices of the due installments for these students."""
        today = fields.Date.context_today(self)
        FeeLine = self.env['school.fee.line']
        moves = self.env['account.move']
        for (year, company), students in self.grouped(
                lambda s: (s.school_year_id, s.company_id)).items():
            moves |= FeeLine._generate_invoices(year, today, company=company, students=students)
        if not moves:
            raise UserError(_(
                "There is no invoice to create. Check that the tuition fees are defined on the "
                "level of the student for this school year, and that the student has a payer or a "
                "contact and is not already invoiced."))
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
