from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .school_period import PERIOD_TYPES


class SchoolGrade(models.Model):
    _name = 'school.grade'
    _description = "Grade"
    _order = 'date desc, id desc'

    student_id = fields.Many2one(
        'school.student', string="Student", required=True, ondelete='cascade', index=True)
    subject_id = fields.Many2one('school.subject', string="Subject", required=True, index=True)
    classroom_id = fields.Many2one(
        'school.classroom', string="Classroom", related='student_id.classroom_id', store=True)
    company_id = fields.Many2one(
        'res.company', string="Company", related='student_id.company_id', store=True)
    academic_year = fields.Char(
        string="Academic Year", compute='_compute_academic_year', store=True, readonly=False,
        required=True)
    period_type = fields.Selection(PERIOD_TYPES, string="Period Type", compute='_compute_period_type')
    period_id = fields.Many2one(
        'school.period', string="Period", required=True, index=True,
        domain="[('period_type', '=', period_type)]")
    evaluation_type = fields.Selection([
        ('test', 'Test'),
        ('homework', 'Homework'),
        ('exam', 'Exam'),
        ('oral', 'Oral'),
    ], string="Evaluation", required=True, default='test')
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)
    score = fields.Float(string="Score", required=True, digits=(16, 2))
    max_score = fields.Float(string="Out of", required=True, default=20.0, digits=(16, 2))
    score_on_20 = fields.Float(
        string="Score (/20)", compute='_compute_score_on_20', store=True, digits=(16, 2))
    teacher_id = fields.Many2one(
        'res.users', string="Teacher", default=lambda self: self.env.user)
    comment = fields.Text(string="Comment")

    _sql_constraints = [
        ('max_score_positive', 'check(max_score > 0)', "The maximum score must be strictly positive."),
        ('score_positive', 'check(score >= 0)', "The score cannot be negative."),
    ]

    @api.depends('company_id')
    def _compute_period_type(self):
        default_type = self.env.company.school_period_type
        for rec in self:
            rec.period_type = rec.company_id.school_period_type or default_type

    @api.depends('student_id.academic_year')
    def _compute_academic_year(self):
        for rec in self:
            rec.academic_year = rec.student_id.academic_year or rec.academic_year

    @api.depends('score', 'max_score')
    def _compute_score_on_20(self):
        for rec in self:
            rec.score_on_20 = rec.score * 20.0 / rec.max_score if rec.max_score else 0.0

    @api.constrains('score', 'max_score')
    def _check_score(self):
        for rec in self:
            if rec.score > rec.max_score:
                raise ValidationError(_("The score cannot be higher than the maximum score."))
