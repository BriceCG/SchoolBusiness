import io

import xlsxwriter

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SchoolGradeExportWizard(models.TransientModel):
    _name = 'school.grade.export.wizard'
    _description = "Report Card"

    student_id = fields.Many2one('school.student', string="Student", required=True)
    school_year_id = fields.Many2one(
        'school.year', string="School Year", required=True,
        default=lambda self: self.env.company.current_school_year_id)
    period_type = fields.Selection(related='student_id.company_id.school_period_type')
    period_id = fields.Many2one(
        'school.period', string="Period",
        domain="[('period_type', '=', period_type)]",
        help="Leave empty to export all the periods of the school year.")

    export_format = fields.Selection([
        ('pdf', 'PDF'),
        ('xlsx', 'Excel'),
    ], string="Format", required=True, default='pdf')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        student = self.env['school.student'].browse(
            res.get('student_id') or self.env.context.get('default_student_id'))
        if student.school_year_id:
            res['school_year_id'] = student.school_year_id.id
        return res

    def _get_grades(self):
        self.ensure_one()
        domain = [
            ('student_id', '=', self.student_id.id),
            ('academic_year', '=', self.school_year_id.name),
        ]
        if self.period_id:
            domain.append(('period_id', '=', self.period_id.id))
        return self.env['school.grade'].search(
            domain, order='period_id, subject_id, date, id')

    def _get_report_data(self):
        """Return, for each period, the subjects with their grades and averages (/20)."""
        self.ensure_one()
        grades = self._get_grades()
        periods = []
        for period in grades.period_id.sorted(lambda p: (p.sequence, p.id)):
            subjects = []
            weighted_total = total_coef = 0.0
            period_grades = grades.filtered(lambda g: g.period_id == period)
            for subject in period_grades.subject_id.sorted(lambda s: (s.sequence, s.id)):
                subject_grades = period_grades.filtered(lambda g: g.subject_id == subject)
                average = sum(subject_grades.mapped('score_on_20')) / len(subject_grades)
                weighted_total += average * subject.coefficient
                total_coef += subject.coefficient
                subjects.append({
                    'subject': subject,
                    'grades': subject_grades,
                    'average': average,
                    'coefficient': subject.coefficient,
                    'weighted': average * subject.coefficient,
                })
            periods.append({
                'period': period,
                'subjects': subjects,
                'average': weighted_total / total_coef if total_coef else 0.0,
                'weighted_total': weighted_total,
                'total_coef': total_coef,
            })
        return periods

    def _get_report_filename(self):
        self.ensure_one()
        return "%s - %s - %s" % (_("Report Card"), self.student_id.name, self.school_year_id.name)

    def action_export(self):
        self.ensure_one()
        if not self._get_grades():
            raise UserError(_("There is no grade to export for this selection."))
        if self.export_format == 'xlsx':
            return {
                'type': 'ir.actions.act_url',
                'url': '/school/grade_export/%s' % self.id,
                'target': 'self',
            }
        return self.env.ref(
            'school_business_backend.action_report_school_report_card').report_action(self)

    def _get_xlsx(self):
        """Return the (content, filename) of the Excel report card."""
        self.ensure_one()
        grades = self._get_grades()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet(_("Report Card")[:31])
        title = workbook.add_format({'bold': True, 'font_size': 14})
        bold = workbook.add_format({'bold': True})
        header = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
        cell = workbook.add_format({'border': 1})
        number = workbook.add_format({'border': 1, 'num_format': '0.00'})
        date_fmt = workbook.add_format({'border': 1, 'num_format': 'yyyy-mm-dd'})
        total = workbook.add_format(
            {'bold': True, 'border': 1, 'num_format': '0.00', 'bg_color': '#F2F2F2'})
        total_label = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#F2F2F2'})

        student = self.student_id
        sheet.write(0, 0, _("Grades of %s", student.name), title)
        sheet.write(1, 0, _("Student Number"), bold)
        sheet.write(1, 1, student.matricule or '')
        sheet.write(2, 0, _("School Year"), bold)
        sheet.write(2, 1, self.school_year_id.name)
        sheet.write(3, 0, _("Period"), bold)
        sheet.write(3, 1, self.period_id.name or _("All periods"))

        columns = [
            _("Period"), _("Subject"), _("Evaluation"), _("Date"), _("Score"),
            _("Out of"), _("Score (/20)"), _("Coefficient"), _("Comment"),
        ]
        row = 5
        for col, label in enumerate(columns):
            sheet.write(row, col, label, header)
        evaluation_labels = dict(grades._fields['evaluation_type']._description_selection(self.env))
        for grade in grades:
            row += 1
            sheet.write(row, 0, grade.period_id.name, cell)
            sheet.write(row, 1, grade.subject_id.name, cell)
            sheet.write(row, 2, evaluation_labels.get(grade.evaluation_type, ''), cell)
            sheet.write_datetime(row, 3, fields.Datetime.to_datetime(grade.date), date_fmt)
            sheet.write_number(row, 4, grade.score, number)
            sheet.write_number(row, 5, grade.max_score, number)
            sheet.write_number(row, 6, grade.score_on_20, number)
            sheet.write_number(row, 7, grade.subject_id.coefficient, number)
            sheet.write(row, 8, grade.comment or '', cell)

        # Averages per subject and per period
        row += 2
        for block in self._get_report_data():
            sheet.write(row, 0, block['period'].name, bold)
            row += 1
            for col, label in enumerate(
                    [_("Subject"), _("Average (/20)"), _("Coefficient"), _("Average x Coefficient")]):
                sheet.write(row, col, label, header)
            for line in block['subjects']:
                row += 1
                sheet.write(row, 0, line['subject'].name, cell)
                sheet.write_number(row, 1, line['average'], number)
                sheet.write_number(row, 2, line['coefficient'], number)
                sheet.write_number(row, 3, line['weighted'], number)
            row += 1
            sheet.write(row, 0, _("Total"), total_label)
            sheet.write(row, 1, '', total_label)
            sheet.write_number(row, 2, block['total_coef'], total)
            sheet.write_number(row, 3, block['weighted_total'], total)
            row += 1
            sheet.write(row, 0, _("General average"), total_label)
            sheet.write_number(row, 1, block['average'], total)
            row += 2

        sheet.set_column(0, 1, 18)
        sheet.set_column(2, 7, 16)
        sheet.set_column(8, 8, 35)
        workbook.close()

        filename = "%s_%s%s.xlsx" % (
            student.matricule or student.name, self.school_year_id.name,
            "_%s" % self.period_id.name if self.period_id else '')
        return output.getvalue(), filename
