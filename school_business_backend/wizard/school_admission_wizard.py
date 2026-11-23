from odoo import _, fields, models
from odoo.exceptions import UserError


class SchoolAdmissionScheduleWizard(models.TransientModel):
    _name = 'school.admission.schedule.wizard'
    _description = "Schedule Admission Step Wizard"

    admission_id = fields.Many2one(
        'school.admission', string="Admission Request", required=True, readonly=True)
    student_name = fields.Char(related='admission_id.student_name', readonly=True)
    wizard_type = fields.Selection([
        ('interview', 'Interview'),
        ('exam', 'Entrance Exam'),
    ], string="Type", required=True)
    interview_date = fields.Date(string="Interview Date")
    interview_start_time = fields.Float(string="Interview Start Time")
    interview_end_time = fields.Float(string="Interview End Time")
    exam_date = fields.Date(string="Entrance Exam Date")
    exam_start_time = fields.Float(string="Exam Start Time")
    exam_end_time = fields.Float(string="Exam End Time")

    def action_confirm(self):
        self.ensure_one()
        if self.wizard_type == 'interview':
            if not self.interview_date:
                raise UserError(_("Please enter the interview date."))
            if not self.interview_start_time or not self.interview_end_time:
                raise UserError(_("Please enter the interview start and end time."))
            self.admission_id.action_set_interview(
                self.interview_date, self.interview_start_time, self.interview_end_time)
        else:
            if not self.exam_date:
                raise UserError(_("Please enter the exam date."))
            if not self.exam_start_time or not self.exam_end_time:
                raise UserError(_("Please enter the exam start and end time."))
            self.admission_id.action_set_exam(
                self.exam_date, self.exam_start_time, self.exam_end_time)
        return {'type': 'ir.actions.act_window_close'}
