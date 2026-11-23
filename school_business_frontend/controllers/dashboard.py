from collections import defaultdict
from datetime import datetime, timedelta

import pytz

from odoo import _, fields, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


def _format_duration(minutes):
    hours, minutes = divmod(int(round(minutes)), 60)
    if hours and minutes:
        return '%d h %02d' % (hours, minutes)
    return '%d h' % hours if hours else '%d min' % minutes


def _format_hour(value):
    hours, minutes = divmod(int(round(value * 60)), 60)
    return '%02d:%02d' % (hours, minutes)


def _get_student_slots(student):
    """Return the timetable slots of the student (classroom lessons and whole level lessons)."""
    Slot = request.env['school.timetable.slot'].sudo()
    if not student.level_id:
        return Slot
    return Slot.search([
        ('level_id', '=', student.level_id.id),
        ('school_year_id', '=', student.school_year_id.id),
        '|', ('classroom_id', '=', student.classroom_id.id), ('classroom_id', '=', False),
    ])


def get_week_timetable(student):
    """Return the lessons of the week of the student, day by day (days without lesson skipped)."""
    slots = _get_student_slots(student)
    if not slots:
        return []
    tz = pytz.timezone(request.env.user.tz or 'UTC')
    now = datetime.now(tz)
    now_hour = now.hour + now.minute / 60.0
    days = dict(slots._fields['weekday']._description_selection(request.env))
    week = []
    for key in sorted(days):
        day_slots = slots.filtered(lambda s: s.weekday == key).sorted(lambda s: s.start_time)
        if not day_slots:
            continue
        is_today = key == str(now.weekday())
        week.append({
            'label': days[key],
            'is_today': is_today,
            'lessons': [{
                'slot': slot,
                'start': _format_hour(slot.start_time),
                'end': _format_hour(slot.end_time),
                'duration': _format_duration((slot.end_time - slot.start_time) * 60),
                'room': slot.room or slot.classroom_id.location or student.classroom_id.location,
                'is_now': is_today and slot.start_time <= now_hour < slot.end_time,
            } for slot in day_slots],
        })
    return week


def get_current_lesson(student):
    """Return the lesson the student has now, else the next one, else False.

    The lessons are the ones of the level of the student (classroom lessons and lessons given to
    the whole level) for the school year of the student. The result is a dict with the status
    (`now` or `next`), the slot and its display values.
    """
    slots = _get_student_slots(student)
    if not slots:
        return False
    Slot = slots
    tz = pytz.timezone(request.env.user.tz or 'UTC')
    now = datetime.now(tz)
    now_hour = now.hour + now.minute / 60.0
    days = dict(Slot._fields['weekday']._description_selection(request.env))

    for offset in range(8):
        day = now + timedelta(days=offset)
        day_slots = slots.filtered(lambda s: s.weekday == str(day.weekday())).sorted(
            lambda s: s.start_time)
        for slot in day_slots:
            if offset == 0:
                if slot.end_time <= now_hour:
                    continue
                status = 'now' if slot.start_time <= now_hour else 'next'
            else:
                status = 'next'
            remaining = (slot.end_time - now_hour) * 60 if status == 'now' else 0
            duration = (slot.end_time - slot.start_time) * 60
            return {
                'status': status,
                'slot': slot,
                'day': _('Today') if offset == 0 else (
                    _('Tomorrow') if offset == 1 else days.get(slot.weekday)),
                'start': _format_hour(slot.start_time),
                'end': _format_hour(slot.end_time),
                'duration': _format_duration(duration),
                'remaining': _format_duration(remaining) if remaining else '',
                'progress': int(max(0, min(100, (duration - remaining) * 100 / duration)))
                if status == 'now' and duration else 0,
                'room': slot.room or slot.classroom_id.location or student.classroom_id.location,
            }
    return False


class SchoolStudentPortal(CustomerPortal):
    """Replace "My Account" by a student home page (grades and invoices) for students."""

    @http.route()
    def home(self, **kw):
        student = SchoolStudentDashboard._get_student()
        if not student:
            return super().home(**kw)
        return request.render(
            'school_business_frontend.student_home', self._student_home_values(student))

    @staticmethod
    def _student_home_values(student):
        today = fields.Date.context_today(student)
        grades = student.grade_ids.filtered(
            lambda g: g.academic_year == student.academic_year)[:5]
        invoices = request.env['account.move'].sudo().search([
            ('student_id', '=', student.id), ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
        ], order='invoice_date_due desc, id desc')
        rows = []
        for inv in invoices:
            unpaid = inv.payment_state in ('not_paid', 'partial')
            rows.append({
                'invoice': inv,
                'unpaid': unpaid,
                'overdue': bool(unpaid and inv.invoice_date_due and inv.invoice_date_due < today),
                'view_url': inv.get_portal_url(),
                'pdf_url': inv.get_portal_url(report_type='pdf', download=True),
            })
        due_rows = [r for r in rows if r['unpaid']]
        next_due = min(
            (r['invoice'].invoice_date_due for r in due_rows if r['invoice'].invoice_date_due),
            default=False)
        return {
            'student': student,
            'average': student.average_grade,
            'recent_grades': grades,
            'invoice_rows': rows[:8],
            'amount_due': sum(r['invoice'].amount_residual for r in due_rows),
            'currency': student.company_id.currency_id,
            'next_due': next_due,
            'overdue_count': len([r for r in rows if r['overdue']]),
            'current_lesson': get_current_lesson(student),
            'week_timetable': get_week_timetable(student),
            'page_name': 'student_home',
        }


class SchoolStudentDashboard(http.Controller):

    @staticmethod
    def _get_student():
        """Return the student record of the logged-in user, or an empty recordset.

        The user must be linked to a student, either through the portal user
        (`user_id`) or through the contact (`partner_id`) of the student.
        """
        user = request.env.user
        Student = request.env['school.student'].sudo()
        if user._is_public():
            return Student
        return Student.search([
            '|', ('user_id', '=', user.id), ('partner_id', '=', user.partner_id.id),
            ('active', '=', True),
        ], limit=1)

    @staticmethod
    def _mention(score):
        if score >= 16:
            return 'excellent', 'success'
        if score >= 14:
            return 'good', 'success'
        if score >= 10:
            return 'fair', 'warning'
        return 'weak', 'danger'

    @http.route('/my/student', type='http', auth='user', website=True, sitemap=False)
    def student_dashboard(self, year=None, period=None, **kw):
        student = self._get_student()
        if not student:
            return request.render('school_business_frontend.student_dashboard_forbidden',
                                  status=403)

        grades = student.grade_ids.sorted(lambda g: (g.date, g.id), reverse=True)
        years = sorted(set(grades.mapped('academic_year')) | {student.academic_year}, reverse=True)
        selected_year = year if year in years else student.academic_year
        year_grades = grades.filtered(lambda g: g.academic_year == selected_year)

        periods = year_grades.mapped('period_id').sorted(lambda p: (p.sequence, p.id))
        selected_period = int(period) if (period or '').isdigit() \
            and int(period) in periods.ids else 0
        shown = year_grades.filtered(lambda g: g.period_id.id == selected_period) \
            if selected_period else year_grades

        # Per-subject averages (mean of the scores /20), weighted overall by coefficient.
        by_subject = defaultdict(lambda: request.env['school.grade'].sudo())
        for grade in shown:
            by_subject[grade.subject_id] |= grade
        subjects = []
        total_coef = weighted = 0.0
        for subject, subject_grades in by_subject.items():
            scores = subject_grades.mapped('score_on_20')
            average = sum(scores) / len(scores)
            label, color = self._mention(average)
            subjects.append({
                'subject': subject,
                'average': average,
                'count': len(scores),
                'best': max(scores),
                'coefficient': subject.coefficient,
                'color': color,
            })
            total_coef += subject.coefficient
            weighted += average * subject.coefficient
        subjects.sort(key=lambda s: (-s['average'], s['subject'].name))
        overall = weighted / total_coef if total_coef else 0.0
        label, color = self._mention(overall)

        return request.render('school_business_frontend.student_dashboard', {
            'student': student,
            'grades': shown,
            'subjects': subjects,
            'overall': overall,
            'overall_color': color,
            'overall_label': label,
            'best_subject': subjects[0] if subjects else False,
            'years': years,
            'selected_year': selected_year,
            'periods': periods,
            'selected_period': selected_period,
            'evaluation_labels': dict(request.env['school.grade']._fields['evaluation_type']._description_selection(request.env)),
            'current_lesson': get_current_lesson(student),
            'week_timetable': get_week_timetable(student),
            'page_name': 'student_dashboard',
        })
