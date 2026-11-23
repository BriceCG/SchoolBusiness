from odoo import _, api, fields, models


class SchoolClassroom(models.Model):
    _name = 'school.classroom'
    _description = "Classroom"
    _order = 'level_id, name'

    name = fields.Char(string="Classroom", required=True)
    code = fields.Char(string="Code")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string="Company", default=lambda self: self.env.company, required=True)
    level_id = fields.Many2one('school.level', string="Level", required=True)
    school_year_id = fields.Many2one(
        'school.year', string="School Year", required=True, index=True,
        default=lambda self: self.env.company.current_school_year_id,
        domain="[('state', '=', 'open')]")
    academic_year = fields.Char(
        string="Academic Year", related='school_year_id.name', store=True)
    capacity = fields.Integer(string="Capacity", default=30, required=True)
    location = fields.Char(string="Location", help="Building, floor, room number...")
    student_ids = fields.One2many('school.student', 'classroom_id', string="Students")
    student_count = fields.Integer(string="Students", compute='_compute_student_count')
    available_seats = fields.Integer(string="Available Seats", compute='_compute_student_count')
    notes = fields.Text(string="Notes")

    _sql_constraints = [
        ('capacity_positive', 'check(capacity > 0)', "The capacity must be strictly positive."),
        ('name_year_company_unique', 'unique(name, academic_year, company_id)',
         "A classroom with this name already exists for this academic year."),
    ]

    @api.depends('student_ids', 'student_ids.state', 'capacity')
    def _compute_student_count(self):
        for room in self:
            count = len(room.student_ids.filtered(lambda s: s.state == 'active'))
            room.student_count = count
            room.available_seats = room.capacity - count

    def action_view_students(self):
        self.ensure_one()
        return {
            'name': _("Students"),
            'type': 'ir.actions.act_window',
            'res_model': 'school.student',
            'view_mode': 'calendar,list,form',
            'domain': [('classroom_id', '=', self.id)],
            'context': {'default_classroom_id': self.id, 'default_level_id': self.level_id.id},
        }

    timetable_slot_ids = fields.One2many(
        'school.timetable.slot', 'classroom_id', string="Timetable")
    timetable_slot_count = fields.Integer(
        string="Lessons", compute='_compute_timetable_slot_count')

    @api.depends('timetable_slot_ids')
    def _compute_timetable_slot_count(self):
        counts = dict(self.env['school.timetable.slot']._read_group(
            [('classroom_id', 'in', self.ids)], ['classroom_id'], ['__count']))
        for room in self:
            room.timetable_slot_count = counts.get(room, 0)

    def _get_timetable_days(self):
        """Return the lessons of the classroom grouped by day: [(day label, slots)]."""
        self.ensure_one()
        from .school_timetable import WEEKDAYS
        slots = self.env['school.timetable.slot'].search([
            ('level_id', '=', self.level_id.id),
            ('school_year_id', '=', self.school_year_id.id),
            '|', ('classroom_id', '=', self.id), ('classroom_id', '=', False),
        ]).sorted(lambda s: (s.weekday, s.start_time))
        return [
            (label, slots.filtered(lambda s, key=key: s.weekday == key))
            for key, label in WEEKDAYS
            if slots.filtered(lambda s, key=key: s.weekday == key)
        ]

    def action_view_timetable(self):
        self.ensure_one()
        return {
            'name': _("Timetable"),
            'type': 'ir.actions.act_window',
            'res_model': 'school.timetable.slot',
            'view_mode': 'list,form',
            'context': {
                'default_classroom_id': self.id,
                'default_level_id': self.level_id.id,
                'search_default_classroom_id': self.id,
            },
        }

    def action_print_timetable(self):
        return self.env.ref('school_business_backend.action_report_school_timetable').report_action(self)
