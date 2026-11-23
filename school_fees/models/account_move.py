from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


class AccountMove(models.Model):
    _inherit = 'account.move'

    student_id = fields.Many2one(
        'school.student', string="Student", index='btree_not_null', copy=False, tracking=True,
        help="Student concerned by this invoice (school fees).")
    fee_line_id = fields.Many2one(
        'school.fee.line', string="Tuition Fee", index='btree_not_null', copy=False,
        ondelete='set null')
    fee_installment = fields.Integer(string="Installment", copy=False)
    school_reminder_count = fields.Integer(
        string="Reminders Sent", copy=False, readonly=True, default=0)
    school_reminder_last_date = fields.Date(
        string="Last Reminder", copy=False, readonly=True)
    school_reminder_max = fields.Integer(
        string="Max Reminders", related='company_id.school_reminder_max')
    school_reminder_due = fields.Boolean(
        string="To Remind", compute='_compute_school_reminder_due',
        search='_search_school_reminder_due')
    school_days_overdue = fields.Integer(
        string="Days Overdue", compute='_compute_school_days_overdue')
    school_partner_email = fields.Char(related='partner_id.email', string="Payer E-mail")

    @api.onchange('student_id')
    def _onchange_student_id(self):
        student = self.student_id
        if student and self.is_sale_document():
            self.partner_id = student.payer_id or student.partner_id or self.partner_id

    # ------------------------------------------------------------------
    # Overdue reminders
    # ------------------------------------------------------------------

    @api.model
    def _school_reminder_domain(self, company):
        """Domain of the tuition invoices of the company that must be reminded today."""
        today = fields.Date.context_today(self)
        return [
            ('company_id', '=', company.id),
            ('move_type', '=', 'out_invoice'),
            ('student_id', '!=', False),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('invoice_date_due', '<=', today - timedelta(days=company.school_reminder_days)),
            '|', ('school_reminder_count', '=', False),
            ('school_reminder_count', '<', company.school_reminder_max),
            '|', ('school_reminder_last_date', '=', False),
            ('school_reminder_last_date', '<=',
             today - timedelta(days=company.school_reminder_interval_days)),
        ]

    @api.model
    def _school_reminder_full_domain(self, companies):
        domains = [
            self._school_reminder_domain(company)
            for company in companies if company.school_reminder_enabled]
        if not domains:
            return [('id', '=', 0)]
        return expression.OR(domains)

    @api.depends('company_id', 'state', 'payment_state', 'invoice_date_due',
                 'school_reminder_count', 'school_reminder_last_date')
    def _compute_school_reminder_due(self):
        for company, moves in self.grouped('company_id').items():
            due = moves.browse()
            if company.school_reminder_enabled:
                due = moves.filtered_domain(self._school_reminder_domain(company))
            for move in moves:
                move.school_reminder_due = move in due

    def _search_school_reminder_due(self, operator, value):
        domain = self._school_reminder_full_domain(self.env.companies)
        if (operator == '=') == bool(value):
            return domain
        return ['!'] + expression.normalize_domain(domain)

    @api.depends('invoice_date_due')
    def _compute_school_days_overdue(self):
        today = fields.Date.context_today(self)
        for move in self:
            due = move.invoice_date_due
            move.school_days_overdue = (today - due).days if due and due < today else 0

    def _send_school_reminder(self):
        """Send the reminder e-mail of the invoice to its payer and record it."""
        self.ensure_one()
        if not self.partner_id.email:
            raise UserError(_(
                "The payer %(partner)s of invoice %(invoice)s has no e-mail address.",
                partner=self.partner_id.display_name, invoice=self.name))
        template = self.env.ref('school_fees.mail_template_school_fee_reminder')
        self.message_post_with_source(
            template,
            email_layout_xmlid='mail.mail_notification_light',
            subtype_xmlid='mail.mt_comment',
        )
        self._school_reminder_record()

    def _school_reminder_record(self):
        self.write({
            'school_reminder_count': self.school_reminder_count + 1,
            'school_reminder_last_date': fields.Date.context_today(self),
        })

    def _send_school_reminders_safe(self):
        """Send the reminders, skipping the invoices that cannot be reminded."""
        sent = failed = 0
        for move in self:
            try:
                with self.env.cr.savepoint():
                    move._send_school_reminder()
                sent += 1
            except UserError:
                failed += 1
        return sent, failed

    def action_send_school_reminder(self):
        """Open the mail composer on the reminder of one invoice (button on each line)."""
        self.ensure_one()
        template = self.env.ref('school_fees.mail_template_school_fee_reminder')
        return {
            'name': _("Send the Reminder"),
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_model': self._name,
                'default_res_ids': self.ids,
                'default_template_id': template.id,
                'default_composition_mode': 'comment',
                'default_email_layout_xmlid': 'mail.mail_notification_light',
                'school_fee_reminder': True,
                'force_email': True,
            },
        }

    def action_send_all_school_reminders(self):
        """Send the reminders of all the invoices to remind (whatever the selection)."""
        moves = self.search(self._school_reminder_full_domain(self.env.companies))
        sent, failed = moves._send_school_reminders_safe()
        return self._school_reminder_notification(sent, failed)

    @api.model
    def _school_reminder_notification(self, sent, failed):
        message = _("%s reminder(s) sent.", sent)
        if failed:
            message += " " + _("%s invoice(s) skipped (payer without e-mail).", failed)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning' if failed else 'success',
                'message': message,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    @api.model
    def _cron_send_school_reminders(self):
        companies = self.env['res.company'].search([
            ('school_reminder_enabled', '=', True), ('school_reminder_auto', '=', True)])
        for company in companies:
            moves = self.with_company(company).search(self._school_reminder_domain(company))
            moves._send_school_reminders_safe()
