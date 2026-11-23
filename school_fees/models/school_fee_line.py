from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class SchoolFeeLine(models.Model):
    _name = 'school.fee.line'
    _description = "Tuition Fee"
    _order = 'school_year_id desc, level_id, id'

    level_id = fields.Many2one(
        'school.level', string="Level", required=True, ondelete='cascade', index=True)
    school_year_id = fields.Many2one(
        'school.year', string="School Year", required=True, index=True,
        default=lambda self: self.env.company.current_school_year_id)
    company_id = fields.Many2one(
        'res.company', string="Company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    amount = fields.Monetary(
        string="Tuition", required=True, currency_field='currency_id',
        help="Total tuition of the school year for this level. It is split into as many "
             "payments as chosen on the student.")

    _sql_constraints = [
        ('amount_positive', 'check(amount >= 0)', "The amount cannot be negative."),
        ('fee_unique', 'unique(level_id, school_year_id, company_id)',
         "The tuition is already defined for this level and this school year."),
    ]

    def _get_due_dates(self, installments):
        """Dates of the payments, spread over the school year from its start."""
        self.ensure_one()
        year = self.school_year_id
        months = (year.date_end.year - year.date_start.year) * 12 \
            + year.date_end.month - year.date_start.month + 1
        step = max(1, months // installments)
        return [year.date_start + relativedelta(months=i * step) for i in range(installments)]

    def _get_installment_amounts(self, installments):
        """Split the tuition in ``installments`` amounts; the last one takes the rounding gap."""
        self.ensure_one()
        amount = self.currency_id.round(self.amount / installments)
        amounts = [amount] * installments
        amounts[-1] = self.currency_id.round(self.amount - amount * (installments - 1))
        return amounts

    # ------------------------------------------------------------------
    # Invoice generation
    # ------------------------------------------------------------------
    @api.model
    def _generate_invoices(self, school_year, date_until, company=None, levels=None, classrooms=None,
                           students=None):
        """Create the draft invoices of the payments due until ``date_until``.

        Payments already invoiced (invoice not cancelled) are skipped, so the method can be
        run as many times as needed. Students without payer nor contact cannot be invoiced.

        :return: the created invoices
        """
        company = company or self.env.company
        product = company.school_fee_product_id
        if not product:
            raise UserError(_("Please select the tuition product in the school settings."))
        Move = self.env['account.move'].with_company(company)

        line_domain = [('school_year_id', '=', school_year.id), ('company_id', '=', company.id)]
        student_domain = [
            ('school_year_id', '=', school_year.id),
            ('company_id', '=', company.id),
            ('state', '=', 'active'),
        ]
        if levels:
            line_domain.append(('level_id', 'in', levels.ids))
            student_domain.append(('level_id', 'in', levels.ids))
        if classrooms:
            student_domain.append(('classroom_id', 'in', classrooms.ids))
        if students:
            student_domain.append(('id', 'in', students.ids))
        lines = {line.level_id: line for line in self.search(line_domain)}
        students = self.env['school.student'].search(student_domain)
        if not lines or not students:
            return Move

        already = defaultdict(set)
        for move in Move.search_fetch([
            ('fee_line_id', 'in', [line.id for line in lines.values()]),
            ('student_id', 'in', students.ids),
            ('state', '!=', 'cancel'),
        ], ['student_id', 'fee_installment']):
            already[move.student_id.id].add(move.fee_installment)

        vals_list = []
        for student in students:
            line = lines.get(student.level_id)
            partner = student.payer_id or student.partner_id
            if not line or not partner:
                continue
            installments = student.fee_installments
            due_dates = line._get_due_dates(installments)
            amounts = line._get_installment_amounts(installments)
            for number, (due_date, amount) in enumerate(zip(due_dates, amounts), start=1):
                if due_date > date_until or number in already[student.id]:
                    continue
                vals_list.append({
                    'move_type': 'out_invoice',
                    'partner_id': partner.id,
                    'student_id': student.id,
                    'fee_line_id': line.id,
                    'fee_installment': number,
                    'invoice_date': due_date,
                    'invoice_origin': school_year.name,
                    'invoice_line_ids': [Command.create({
                        'product_id': product.id,
                        'name': _(
                            "%(fee)s - %(student)s (%(year)s) - %(number)s/%(total)s",
                            fee=product.display_name, student=student.name,
                            year=school_year.name, number=number, total=installments),
                        'quantity': 1,
                        'price_unit': amount,
                    })],
                })
        return Move.create(vals_list)

    @api.model
    def _cron_generate_invoices(self):
        today = fields.Date.context_today(self)
        companies = self.env['res.company'].search([
            ('current_school_year_id', '!=', False),
            ('school_fee_product_id', '!=', False),
        ])
        for company in companies:
            self._generate_invoices(company.current_school_year_id, today, company=company)
