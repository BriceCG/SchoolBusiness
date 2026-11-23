from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

WEEKDAYS = [
    ('0', "Monday"),
    ('1', "Tuesday"),
    ('2', "Wednesday"),
    ('3', "Thursday"),
    ('4', "Friday"),
    ('5', "Saturday"),
    ('6', "Sunday"),
]


def _format_time(value):
    hours, minutes = divmod(round(value * 60), 60)
    return '%02d:%02d' % (hours, minutes)


class SchoolTimetableSlot(models.Model):
    _name = 'school.timetable.slot'
    _description = "Timetable Slot"
    _order = 'level_id, classroom_id, weekday, start_time, id'

    level_id = fields.Many2one(
        'school.level', string="Level", required=True, index=True, ondelete='restrict',
        compute='_compute_level_id', store=True, readonly=False, precompute=True,
        help="Level of the timetable. The lesson is given to all the classrooms of the level "
             "unless a classroom is selected.")
    classroom_id = fields.Many2one(
        'school.classroom', string="Classroom", ondelete='cascade', index=True,
        domain="[('level_id', '=', level_id)]",
        help="Leave empty for a lesson given to the whole level.")
    school_year_id = fields.Many2one(
        'school.year', string="School Year", required=True, index=True,
        compute='_compute_school_year_id', store=True, readonly=False, precompute=True)
    company_id = fields.Many2one(
        'res.company', string="Company", required=True, index=True,
        compute='_compute_company_id', store=True, readonly=False, precompute=True)
    weekday = fields.Selection(WEEKDAYS, string="Day", required=True, default='0')
    start_time = fields.Float(string="Start", required=True, default=8.0)
    end_time = fields.Float(string="End", required=True, default=9.0)
    subject_id = fields.Many2one('school.subject', string="Subject", required=True)
    teacher_id = fields.Many2one(
        'school.teacher', string="Teacher", domain="[('state', '!=', 'left')]")
    room = fields.Char(string="Room", help="Room where the lesson takes place, if different "
                                           "from the location of the classroom.")
    active = fields.Boolean(default=True)
    name = fields.Char(string="Slot", compute='_compute_name')

    # Calendar support: the lessons repeat every week, so the datetimes are not stored. They are
    # computed on the week displayed by the calendar view (see `search_read`).
    start_datetime = fields.Datetime(
        string="Start Date", compute='_compute_datetimes', inverse='_inverse_datetimes',
        search='_search_datetimes')
    stop_datetime = fields.Datetime(
        string="End Date", compute='_compute_datetimes', inverse='_inverse_datetimes',
        search='_search_datetimes')

    @api.depends('classroom_id')
    def _compute_level_id(self):
        for rec in self:
            if rec.classroom_id:
                rec.level_id = rec.classroom_id.level_id

    @api.depends('classroom_id')
    def _compute_school_year_id(self):
        for rec in self:
            rec.school_year_id = (
                rec.classroom_id.school_year_id or rec.school_year_id
                or self.env.company.current_school_year_id)

    @api.depends('classroom_id')
    def _compute_company_id(self):
        for rec in self:
            rec.company_id = rec.classroom_id.company_id or rec.company_id or self.env.company

    def _get_user_tz(self):
        return pytz.timezone(self.env.user.tz or self.env.context.get('tz') or 'UTC')

    @api.depends('weekday', 'start_time', 'end_time')
    @api.depends_context('timetable_range_start', 'tz', 'uid')
    def _compute_datetimes(self):
        tz = self._get_user_tz()
        range_start = self.env.context.get('timetable_range_start')
        if range_start:
            first_day = pytz.utc.localize(
                fields.Datetime.from_string(range_start)).astimezone(tz).date()
        else:
            first_day = datetime.now(tz).date()
        for rec in self:
            if not rec.weekday:
                rec.start_datetime = rec.stop_datetime = False
                continue
            day = first_day + timedelta(days=(int(rec.weekday) - first_day.weekday()) % 7)
            midnight = datetime.combine(day, time.min)
            for field, hours in (('start_datetime', rec.start_time), ('stop_datetime', rec.end_time)):
                local = tz.localize(midnight + timedelta(hours=hours))
                rec[field] = local.astimezone(pytz.utc).replace(tzinfo=None)

    def _search_datetimes(self, operator, value):
        # The range sent by the calendar only selects the displayed week: every lesson is
        # repeated weekly, so no lesson is filtered out.
        return [(1, '=', 1)]

    def _datetimes_to_slot_values(self, start, stop):
        """Return the weekday and times matching two UTC datetimes of the calendar."""
        tz = self._get_user_tz()
        local_start = pytz.utc.localize(start).astimezone(tz)
        local_stop = pytz.utc.localize(stop).astimezone(tz)
        end_time = local_stop.hour + local_stop.minute / 60.0
        if local_stop.date() > local_start.date():
            end_time = 24.0
        return {
            'weekday': str(local_start.weekday()),
            'start_time': local_start.hour + local_start.minute / 60.0,
            'end_time': end_time,
        }

    def _inverse_datetimes(self):
        for rec in self:
            if rec.start_datetime and rec.stop_datetime:
                rec.write(rec._datetimes_to_slot_values(rec.start_datetime, rec.stop_datetime))

    @api.onchange('start_datetime', 'stop_datetime')
    def _onchange_datetimes(self):
        if self.start_datetime and self.stop_datetime:
            for key, value in self._datetimes_to_slot_values(
                    self.start_datetime, self.stop_datetime).items():
                self[key] = value

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None, **kwargs):
        # Keep the start of the range requested by the calendar to place the weekly lessons
        # on the displayed week.
        for leaf in domain or []:
            if isinstance(leaf, (list, tuple)) and len(leaf) == 3                     and leaf[0] == 'stop_datetime' and leaf[1] == '>=':
                self = self.with_context(timetable_range_start=leaf[2])
                break
        return super().search_read(
            domain=domain, fields=fields, offset=offset, limit=limit, order=order, **kwargs)

    @api.depends('level_id', 'classroom_id', 'weekday', 'start_time', 'end_time', 'subject_id')
    def _compute_name(self):
        days = dict(WEEKDAYS)
        for rec in self:
            rec.name = "%s - %s %s-%s - %s" % (
                rec.classroom_id.name or rec.level_id.name or '', days.get(rec.weekday, ''),
                _format_time(rec.start_time), _format_time(rec.end_time),
                rec.subject_id.name or '')

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for rec in self:
            if not (0.0 <= rec.start_time < 24.0 and 0.0 < rec.end_time <= 24.0):
                raise ValidationError(_("The times must be between 00:00 and 24:00."))
            if rec.end_time <= rec.start_time:
                raise ValidationError(_("The end time must be after the start time."))

    def _overlap_domain(self):
        self.ensure_one()
        return [
            ('id', '!=', self.id),
            ('weekday', '=', self.weekday),
            ('start_time', '<', self.end_time),
            ('end_time', '>', self.start_time),
        ]

    @api.constrains('level_id', 'classroom_id')
    def _check_classroom_level(self):
        for rec in self:
            if rec.classroom_id and rec.classroom_id.level_id != rec.level_id:
                raise ValidationError(_(
                    "The classroom %(room)s does not belong to the level %(level)s.",
                    room=rec.classroom_id.name, level=rec.level_id.name))

    @api.constrains('level_id', 'classroom_id', 'teacher_id', 'weekday', 'start_time', 'end_time')
    def _check_overlap(self):
        for rec in self:
            # A lesson of a classroom clashes with the lessons of this classroom and with the
            # lessons given to the whole level; a lesson of the whole level clashes with all
            # the lessons of the level.
            domain = rec._overlap_domain() + [('level_id', '=', rec.level_id.id)]
            if rec.classroom_id:
                domain += ['|', ('classroom_id', '=', rec.classroom_id.id),
                           ('classroom_id', '=', False)]
            clash = self.search(domain, limit=1)
            if clash:
                raise ValidationError(_(
                    "The timetable of %(room)s already has a lesson of %(subject)s on %(day)s "
                    "from %(start)s to %(end)s.",
                    room=rec.classroom_id.name or rec.level_id.name, subject=clash.subject_id.name,
                    day=dict(WEEKDAYS)[clash.weekday], start=_format_time(clash.start_time),
                    end=_format_time(clash.end_time)))
            if rec.teacher_id:
                clash = self.search(rec._overlap_domain() + [
                    ('teacher_id', '=', rec.teacher_id.id),
                    ('school_year_id', '=', rec.school_year_id.id),
                ], limit=1)
                if clash:
                    raise ValidationError(_(
                        "The teacher %(teacher)s already teaches in %(room)s on %(day)s "
                        "from %(start)s to %(end)s.",
                        teacher=rec.teacher_id.name,
                        room=clash.classroom_id.name or clash.level_id.name,
                        day=dict(WEEKDAYS)[clash.weekday], start=_format_time(clash.start_time),
                        end=_format_time(clash.end_time)))
