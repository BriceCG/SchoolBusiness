from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolTeacher(models.Model):
    _name = 'school.teacher'
    _description = "Teacher"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _inherits = {'res.partner': 'partner_id'}
    _order = 'name'

    partner_id = fields.Many2one(
        'res.partner', string="Contact", required=True, ondelete='restrict', auto_join=True,
        copy=False, index=True,
        help="Contact of the teacher. A new contact is created when none is selected.")
    teacher_number = fields.Char(
        string="Teacher Number", required=True, copy=False, readonly=True,
        default=lambda self: _('New'))
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string="Company", default=lambda self: self.env.company, required=True)
    user_id = fields.Many2one(
        'res.users', string="Related User", copy=False,
        help="User account used by the teacher to log in.")

    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
    ], string="Gender")
    date_of_birth = fields.Date(string="Date of Birth")
    hire_date = fields.Date(string="Hire Date", default=fields.Date.context_today)
    qualification = fields.Char(string="Qualification", help="Highest degree or certification.")
    state = fields.Selection([
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('left', 'Left'),
    ], string="Status", default='active', required=True, tracking=True)

    subject_ids = fields.Many2many(
        'school.subject', 'school_teacher_subject_rel', 'teacher_id', 'subject_id',
        string="Subjects")
    level_ids = fields.Many2many(
        'school.level', 'school_teacher_level_rel', 'teacher_id', 'level_id',
        string="Levels")
    classroom_ids = fields.Many2many(
        'school.classroom', 'school_teacher_classroom_rel', 'teacher_id', 'classroom_id',
        string="Classrooms")
    classroom_count = fields.Integer(string="Classrooms", compute='_compute_counts')
    grade_count = fields.Integer(string="Grades Entered", compute='_compute_counts')
    notes = fields.Text(string="Internal Notes")

    _sql_constraints = [
        ('teacher_number_unique', 'unique(teacher_number)', "The teacher number must be unique."),
        ('partner_unique', 'unique(partner_id)', "This contact is already a teacher."),
    ]

    @api.depends('classroom_ids', 'user_id')
    def _compute_counts(self):
        grade_counts = {}
        if self.user_id:
            grade_counts = {
                user.id: count for user, count in self.env['school.grade']._read_group(
                    [('teacher_id', 'in', self.user_id.ids)], ['teacher_id'], ['__count'])}
        for rec in self:
            rec.classroom_count = len(rec.classroom_ids)
            rec.grade_count = grade_counts.get(rec.user_id.id, 0)

    @api.constrains('date_of_birth', 'hire_date')
    def _check_dates(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.date_of_birth and rec.date_of_birth >= today:
                raise ValidationError(_("The date of birth must be in the past."))
            if rec.date_of_birth and rec.hire_date and rec.hire_date <= rec.date_of_birth:
                raise ValidationError(_("The hire date must be after the date of birth."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('teacher_number', _('New')) == _('New'):
                vals['teacher_number'] = (
                    self.env['ir.sequence'].next_by_code('school.teacher') or _('New'))
        return super().create(vals_list)

    def action_view_partner(self):
        self.ensure_one()
        return {
            'name': _("Contact"),
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'res_id': self.partner_id.id,
        }

    def action_view_classrooms(self):
        self.ensure_one()
        return {
            'name': _("Classrooms"),
            'type': 'ir.actions.act_window',
            'res_model': 'school.classroom',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.classroom_ids.ids)],
        }

    def action_view_grades(self):
        self.ensure_one()
        return {
            'name': _("Grades"),
            'type': 'ir.actions.act_window',
            'res_model': 'school.grade',
            'view_mode': 'list,form',
            'domain': [('teacher_id', '=', self.user_id.id)],
        }

    def action_set_on_leave(self):
        self.write({'state': 'on_leave'})

    def action_leave(self):
        self.write({'state': 'left'})

    def action_reactivate(self):
        self.write({'state': 'active'})
