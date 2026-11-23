from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolStudent(models.Model):
    _name = 'school.student'
    _description = "Student"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string="Student Name", required=True, tracking=True)
    matricule = fields.Char(
        string="Student Number", required=True, copy=False, readonly=True,
        default=lambda self: _('New'))
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string="Company", default=lambda self: self.env.company, required=True)
    photo = fields.Image(string="Photo")
    partner_id = fields.Many2one('res.partner', string="Contact", copy=False)
    user_id = fields.Many2one('res.users', string="Portal User", copy=False)
    admission_id = fields.Many2one(
        'school.admission', string="Admission Request", readonly=True, copy=False)

    # Identity
    date_of_birth = fields.Date(string="Date of Birth")
    place_of_birth = fields.Char(string="Place of Birth")
    age = fields.Integer(string="Age", compute='_compute_age')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
    ], string="Gender")
    nationality_id = fields.Many2one('res.country', string="Nationality")
    email = fields.Char(string="Email")
    phone = fields.Char(string="Phone")

    # Parent / guardian
    parent_name = fields.Char(string="Parent/Guardian Name")
    parent_phone = fields.Char(string="Parent Phone")
    parent_email = fields.Char(string="Parent Email")

    # Schooling
    level_id = fields.Many2one('school.level', string="Level", required=True, tracking=True)
    classroom_id = fields.Many2one(
        'school.classroom', string="Classroom", tracking=True,
        domain="[('level_id', '=', level_id)]")
    school_year_id = fields.Many2one(
        'school.year', string="School Year", required=True, index=True, tracking=True,
        default=lambda self: self.env.company.current_school_year_id,
        domain="[('state', '=', 'open')]")
    academic_year = fields.Char(
        string="Academic Year", related='school_year_id.name', store=True)
    state = fields.Selection([
        ('active', 'Active'),
        ('graduated', 'Graduated'),
        ('left', 'Left'),
    ], string="Status", default='active', required=True, tracking=True)

    # Grades
    grade_ids = fields.One2many('school.grade', 'student_id', string="Grades")
    grade_count = fields.Integer(string="Grades", compute='_compute_grade_count')
    average_grade = fields.Float(
        string="Average (/20)", compute='_compute_average_grade', digits=(16, 2),
        help="Average of the grades of the current academic year, on a scale of 20 and "
             "weighted by the coefficient of each subject.")

    _sql_constraints = [
        ('matricule_unique', 'unique(matricule)', "The student number must be unique."),
    ]

    @api.depends('date_of_birth')
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.date_of_birth:
                rec.age = today.year - rec.date_of_birth.year - (
                    (today.month, today.day) < (rec.date_of_birth.month, rec.date_of_birth.day)
                )
            else:
                rec.age = 0

    @api.depends('grade_ids')
    def _compute_grade_count(self):
        counts = dict(self.env['school.grade']._read_group(
            [('student_id', 'in', self.ids)], ['student_id'], ['__count']))
        for rec in self:
            rec.grade_count = counts.get(rec, 0)

    @api.depends('grade_ids.score_on_20', 'grade_ids.academic_year',
                 'grade_ids.subject_id.coefficient', 'academic_year')
    def _compute_average_grade(self):
        for rec in self:
            grades = rec.grade_ids.filtered(lambda g: g.academic_year == rec.academic_year)
            total_coef = sum(grades.mapped('subject_id.coefficient'))
            rec.average_grade = (
                sum(g.score_on_20 * g.subject_id.coefficient for g in grades) / total_coef
                if total_coef else 0.0
            )

    @api.constrains('classroom_id', 'level_id', 'state')
    def _check_classroom(self):
        for rec in self:
            room = rec.classroom_id
            if not room:
                continue
            if room.level_id != rec.level_id:
                raise ValidationError(_(
                    "The classroom %(room)s belongs to the level %(room_level)s, "
                    "not %(level)s.",
                    room=room.name, room_level=room.level_id.name, level=rec.level_id.name))
            if rec.state == 'active' and room.available_seats < 0:
                raise ValidationError(_(
                    "The classroom %(room)s is full (capacity: %(capacity)s).",
                    room=room.name, capacity=room.capacity))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('matricule', _('New')) == _('New'):
                vals['matricule'] = self.env['ir.sequence'].next_by_code('school.student') or _('New')
        return super().create(vals_list)

    def action_view_grades(self):
        self.ensure_one()
        return {
            'name': _("Grades"),
            'type': 'ir.actions.act_window',
            'res_model': 'school.grade',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }

    def action_print_report_card(self):
        self.ensure_one()
        return {
            'name': _("Report Card"),
            'type': 'ir.actions.act_window',
            'res_model': 'school.grade.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_student_id': self.id},
        }

    def action_graduate(self):
        self.write({'state': 'graduated'})

    def action_leave(self):
        self.write({'state': 'left'})

    def action_reactivate(self):
        self.write({'state': 'active'})
