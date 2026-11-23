from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date


class SchoolAdmission(models.Model):
    _name = 'school.admission'
    _description = "Admission Request"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'application_date desc, id desc'


    name = fields.Char(
        string="Reference", required=True, copy=False, readonly=True,
        default=lambda self: _('New'))
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string="Company", default=lambda self: self.env.company, required=True)
    responsible_id = fields.Many2one(
        'res.users', string="Responsible", default=lambda self: self.env.user, tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string="Contact", readonly=True, copy=False)
    partner_is_existing = fields.Boolean(
        string="Linked to Existing Contact", readonly=True, copy=False,
        help="The contact was already in the database, so it is not updated from this request.")
    user_id = fields.Many2one(
        'res.users', string="Portal User", readonly=True, copy=False)
    student_id = fields.Many2one(
        'school.student', string="Student", readonly=True, copy=False)

    # Student information
    student_name = fields.Char(string="Student Name", required=True, tracking=True)
    student_email = fields.Char(string="Student Email")
    date_of_birth = fields.Date(string="Date of Birth")
    place_of_birth = fields.Char(string="Place of Birth")
    age = fields.Integer(string="Age", compute='_compute_age')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
    ], string="Gender")
    nationality_id = fields.Many2one('res.country', string="Nationality")
    photo = fields.Image(string="Photo")

    # Address
    street = fields.Char(string="Street")
    street2 = fields.Char(string="Street2")
    city = fields.Char(string="City")
    zip = fields.Char(string="ZIP")
    state_id = fields.Many2one('res.country.state', string="State")
    country_id = fields.Many2one('res.country', string="Country")

    # Parent / guardian
    parent_name = fields.Char(string="Parent/Guardian Name", required=True, tracking=True)
    parent_relationship = fields.Selection([
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('guardian', 'Legal Guardian'),
    ], string="Relationship", default='father')
    parent_phone = fields.Char(string="Parent Phone", required=True)
    parent_email = fields.Char(string="Parent Email")

    # Requested schooling
    level_id = fields.Many2one('school.level', string="Requested Level", required=True, tracking=True)
    school_year_id = fields.Many2one(
        'school.year', string="School Year", required=True, index=True,
        default=lambda self: self.env.company.current_school_year_id,
        domain="[('state', '=', 'open')]")
    academic_year = fields.Char(
        string="Academic Year", related='school_year_id.name', store=True)
    previous_school = fields.Char(string="Previous School")
    previous_level = fields.Char(string="Previous Level")

    # Documents
    application_document = fields.Binary(string="Application Document", attachment=True)
    application_document_filename = fields.Char(string="Application Document Filename")

    # Follow-up
    application_date = fields.Date(
        string="Application Date", default=fields.Date.context_today, required=True)
    interview_date = fields.Date(string="Interview Date")
    interview_start_time = fields.Float(string="Interview Start Time")
    interview_end_time = fields.Float(string="Interview End Time")
    exam_date = fields.Date(string="Entrance Exam Date")
    exam_start_time = fields.Float(string="Exam Start Time")
    exam_end_time = fields.Float(string="Exam End Time")
    exam_score = fields.Float(string="Exam Score")
    refusal_reason = fields.Text(string="Refusal Reason")
    notes = fields.Text(string="Internal Notes")

    state = fields.Selection([
        ('draft', 'New'),
        ('submitted', 'Application Submitted'),
        ('interview', 'Interview'),
        ('exam', "Entrance Exam"),
        ('accepted', 'Accepted'),
        ('enrolled', 'Enrolled'),
        ('refused', 'Refused'),
    ], string="Stage", default='draft', required=True, tracking=True, copy=False,
        group_expand='_expand_states')

    @api.model
    def _expand_states(self, states, domain):
        return [key for key, _label in self._fields['state'].selection]

    @api.constrains('student_email')
    def _check_student_email_unique(self):
        for rec in self:
            email = (rec.student_email or '').strip()
            if not email:
                continue
            duplicate = self.with_context(active_test=False).search([
                ('id', '!=', rec.id),
                ('student_email', '=ilike', email),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    "The email %(email)s is already used by admission request %(ref)s.",
                    email=email, ref=duplicate.name,
                ))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_accepted_or_enrolled(self):
        for rec in self:
            if rec.state in ('accepted', 'enrolled'):
                raise UserError(_(
                    "You cannot delete the admission request %(ref)s because it is already "
                    "accepted or enrolled.", ref=rec.name))

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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('school.admission') or _('New')
        records = super().create(vals_list)
        for rec in records:
            partner = rec._find_existing_partner()
            if partner:
                rec.partner_is_existing = True
            else:
                partner = self.env['res.partner'].create(rec._prepare_partner_vals())
            rec.partner_id = partner
            rec.message_subscribe(partner_ids=partner.ids)
        return records

    def write(self, vals):
        res = super().write(vals)
        partner_fields = {
            'student_name', 'student_email', 'parent_phone',
            'street', 'street2', 'city', 'zip', 'state_id', 'country_id',
        }
        if partner_fields & vals.keys():
            for rec in self:
                if rec.partner_id and not rec.partner_is_existing:
                    rec.partner_id.write(rec._prepare_partner_vals())
        return res

    def _find_existing_partner(self):
        """Return the contact already using the student email, if any."""
        self.ensure_one()
        email = (self.student_email or '').strip()
        if not email:
            return self.env['res.partner']
        return self.env['res.partner'].search([('email', '=ilike', email)], limit=1)

    def _prepare_partner_vals(self):
        self.ensure_one()
        return {
            'name': self.student_name,
            'phone': self.parent_phone,
            'email': self.student_email,
            'street': self.street,
            'street2': self.street2,
            'city': self.city,
            'zip': self.zip,
            'state_id': self.state_id.id,
            'country_id': self.country_id.id,
        }

    def _translate_for_partner(self):
        """Return (rec, translate) bound to the contact's language rather than the
        acting user's, since a logged message is stored as-is and never re-translated
        per viewer."""
        self.ensure_one()
        lang = self.partner_id.lang or self.env.lang or 'en_US'
        rec = self.with_context(lang=lang)
        return rec, rec.env._

    def _notify_partner(self, subject, paragraphs):
        self.ensure_one()
        if not self.partner_id:
            return
        body = Markup("").join(Markup("<p>%s</p>") % paragraph for paragraph in paragraphs)
        self.message_post(
            body=body,
            subject=subject,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            partner_ids=self.partner_id.ids,
        )

    def _send_admission_confirmation_email(self):
        self.ensure_one()
        if not self.partner_id:
            return
        rec, translate = self._translate_for_partner()
        subject = translate("Admission Request %(ref)s Received", ref=rec.name)
        greeting = translate("Dear %(student)s,", student=rec.student_name)
        confirmation = translate(
            "We confirm that your admission request %(ref)s for %(level)s (%(year)s) has "
            "been successfully received.",
            ref=rec.name,
            level=rec.level_id.name or '',
            year=rec.academic_year or '',
        )
        followup = translate("Our admissions team will review your file and contact you for the next steps.")
        closing = Markup("%s<br/>%s") % (translate("Best regards,"), rec.company_id.name or '')
        rec._notify_partner(subject, [greeting, confirmation, followup, closing])

    @staticmethod
    def _format_float_time(value):
        hours = int(value)
        minutes = round((value - hours) * 60)
        if minutes == 60:
            hours += 1
            minutes = 0
        return "%02d:%02d" % (hours, minutes)

    def _schedule_interview_activity(self):
        self.ensure_one()
        if not self.responsible_id:
            return
        summary = _("Interview with %(student)s") % {'student': self.student_name}
        note = _(
            "Interview scheduled on %(date)s from %(start)s to %(end)s for admission "
            "request %(ref)s."
        ) % {
            'date': format_date(self.env, self.interview_date),
            'start': self._format_float_time(self.interview_start_time),
            'end': self._format_float_time(self.interview_end_time),
            'ref': self.name,
        }
        self.activity_schedule(
            'school_business_backend.mail_activity_type_interview',
            date_deadline=self.interview_date,
            summary=summary,
            note=note,
            user_id=self.responsible_id.id,
        )

    def _send_interview_scheduled_email(self):
        self.ensure_one()
        if not self.partner_id:
            return
        rec, translate = self._translate_for_partner()
        subject = translate("Interview Scheduled: %(ref)s", ref=rec.name)
        greeting = translate("Dear %(student)s,", student=rec.student_name)
        interview_info = translate(
            "Your interview for admission request %(ref)s is scheduled on %(date)s from "
            "%(start)s to %(end)s.",
            ref=rec.name,
            date=format_date(rec.env, rec.interview_date),
            start=rec._format_float_time(rec.interview_start_time),
            end=rec._format_float_time(rec.interview_end_time),
        )
        reminder = translate("Please arrive a few minutes before the scheduled time.")
        closing = Markup("%s<br/>%s") % (translate("Best regards,"), rec.company_id.name or '')
        rec._notify_partner(subject, [greeting, interview_info, reminder, closing])

    def action_set_interview(self, interview_date, start_time, end_time):
        self.ensure_one()
        self.write({
            'interview_date': interview_date,
            'interview_start_time': start_time,
            'interview_end_time': end_time,
            'state': 'interview',
        })
        self._schedule_interview_activity()
        self._send_interview_scheduled_email()

    def _schedule_exam_activity(self):
        self.ensure_one()
        if not self.responsible_id:
            return
        summary = _("Entrance exam with %(student)s") % {'student': self.student_name}
        note = _(
            "Entrance exam scheduled on %(date)s from %(start)s to %(end)s for admission "
            "request %(ref)s."
        ) % {
            'date': format_date(self.env, self.exam_date),
            'start': self._format_float_time(self.exam_start_time),
            'end': self._format_float_time(self.exam_end_time),
            'ref': self.name,
        }
        self.activity_schedule(
            'school_business_backend.mail_activity_type_exam',
            date_deadline=self.exam_date,
            summary=summary,
            note=note,
            user_id=self.responsible_id.id,
        )

    def _send_exam_scheduled_email(self):
        self.ensure_one()
        if not self.partner_id:
            return
        rec, translate = self._translate_for_partner()
        subject = translate("Entrance Exam Scheduled: %(ref)s", ref=rec.name)
        greeting = translate("Dear %(student)s,", student=rec.student_name)
        exam_info = translate(
            "Your entrance exam for admission request %(ref)s is scheduled on %(date)s "
            "from %(start)s to %(end)s.",
            ref=rec.name,
            date=format_date(rec.env, rec.exam_date),
            start=rec._format_float_time(rec.exam_start_time),
            end=rec._format_float_time(rec.exam_end_time),
        )
        reminder = translate("Please arrive a few minutes before the scheduled time.")
        closing = Markup("%s<br/>%s") % (translate("Best regards,"), rec.company_id.name or '')
        rec._notify_partner(subject, [greeting, exam_info, reminder, closing])

    def _send_acceptance_email(self):
        self.ensure_one()
        if not self.partner_id:
            return
        rec, translate = self._translate_for_partner()
        subject = translate("Admission Request %(ref)s Accepted", ref=rec.name)
        greeting = translate("Dear %(student)s,", student=rec.student_name)
        acceptance_info = translate(
            "We are pleased to inform you that your admission request %(ref)s for "
            "%(level)s (%(year)s) has been accepted.",
            ref=rec.name,
            level=rec.level_id.name or '',
            year=rec.academic_year or '',
        )
        followup = translate("Please contact our admissions team to finalize your enrollment.")
        closing = Markup("%s<br/>%s") % (translate("Best regards,"), rec.company_id.name or '')
        rec._notify_partner(subject, [greeting, acceptance_info, followup, closing])

    def _send_refusal_email(self):
        self.ensure_one()
        if not self.partner_id:
            return
        rec, translate = self._translate_for_partner()
        subject = translate("Admission Request %(ref)s Update", ref=rec.name)
        greeting = translate("Dear %(student)s,", student=rec.student_name)
        refusal_info = translate(
            "We regret to inform you that your admission request %(ref)s for %(level)s "
            "(%(year)s) has not been accepted.",
            ref=rec.name,
            level=rec.level_id.name or '',
            year=rec.academic_year or '',
        )
        followup = translate("Please contact our admissions team if you have any questions.")
        closing = Markup("%s<br/>%s") % (translate("Best regards,"), rec.company_id.name or '')
        rec._notify_partner(subject, [greeting, refusal_info, followup, closing])

    def action_set_exam(self, exam_date, start_time, end_time):
        self.ensure_one()
        self.write({
            'exam_date': exam_date,
            'exam_start_time': start_time,
            'exam_end_time': end_time,
            'state': 'exam',
        })
        self._schedule_exam_activity()
        self._send_exam_scheduled_email()

    # Admission stages
    def action_submit(self):
        for rec in self:
            if not rec.application_document:
                raise UserError(_("Please attach the application document before submitting the file."))
        self.write({'state': 'submitted'})
        for rec in self:
            rec._send_admission_confirmation_email()

    def action_schedule_interview(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Schedule Interview"),
            'res_model': 'school.admission.schedule.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_admission_id': self.id, 'default_wizard_type': 'interview'},
        }

    def action_schedule_exam(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Schedule Exam"),
            'res_model': 'school.admission.schedule.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_admission_id': self.id, 'default_wizard_type': 'exam'},
        }

    def action_accept(self):
        self.write({'state': 'accepted'})
        for rec in self:
            rec._send_acceptance_email()

    def _create_portal_user(self):
        """Create (or reuse) the portal user of the student; the signup invitation
        email is sent by auth_signup when the user is created."""
        self.ensure_one()
        if self.user_id:
            return self.user_id
        login = (self.student_email or '').strip()
        if not login:
            raise UserError(_("Please set the student email before enrolling: it is used as portal login."))
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        user = Users.search([('login', '=', login), ('company_id', '=', self.company_id.id)], limit=1)
        if not user:
            user = Users.create({
                'name': self.student_name,
                'login': login,
                'email': login,
                'partner_id': self.partner_id.id,
                'company_id': self.company_id.id,
                'company_ids': [(6, 0, self.company_id.ids)],
                'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
            })
        self.user_id = user
        return user

    def _prepare_student_vals(self):
        self.ensure_one()
        return {
            'name': self.student_name,
            'photo': self.photo,
            'company_id': self.company_id.id,
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id,
            'admission_id': self.id,
            'date_of_birth': self.date_of_birth,
            'place_of_birth': self.place_of_birth,
            'gender': self.gender,
            'nationality_id': self.nationality_id.id,
            'email': self.student_email,
            'phone': self.parent_phone,
            'parent_name': self.parent_name,
            'parent_phone': self.parent_phone,
            'parent_email': self.parent_email,
            'level_id': self.level_id.id,
            'school_year_id': self.school_year_id.id,
        }

    def _create_student(self):
        self.ensure_one()
        if not self.student_id:
            self.student_id = self.env['school.student'].create(self._prepare_student_vals())
        return self.student_id

    def action_enroll(self):
        for rec in self:
            rec._create_portal_user()
            rec._create_student()
        self.write({'state': 'enrolled'})

    def action_refuse(self):
        self.write({'state': 'refused'})
        for rec in self:
            rec._send_refusal_email()

    def action_reset_draft(self):
        self.write({'state': 'draft'})
