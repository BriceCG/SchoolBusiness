from markupsafe import Markup

from odoo import _, models
from odoo.exceptions import UserError


class SchoolAdmission(models.Model):
    _name = 'school.admission'
    _inherit = ['school.admission', 'portal.mixin']

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = '/admission/%s/edit' % rec.id

    def _get_form_link(self):
        """Return the public URL, protected by the access token, to complete the request."""
        self.ensure_one()
        return '%s/admission/%s/edit?token=%s' % (
            self.get_base_url(), self.id, self._portal_ensure_token())

    def _send_form_link_email(self):
        self.ensure_one()
        rec, translate = self._translate_for_partner()
        link = Markup('<a href="%s">%s</a>') % (
            rec._get_form_link(), translate("Complete my admission request"))
        subject = translate("Admission Request %(ref)s: Please Complete Your File", ref=rec.name)
        greeting = translate("Dear %(student)s,", student=rec.student_name)
        invitation = translate(
            "Please follow the link below to complete your admission request %(ref)s "
            "and upload your application document.", ref=rec.name)
        closing = Markup("%s<br/>%s") % (translate("Best regards,"), rec.company_id.name or '')
        rec._notify_partner(subject, [greeting, invitation, link, closing])

    def action_enroll(self):
        res = super().action_enroll()
        self.partner_id.sudo().write({'is_student': True})
        return res

    def action_send_form_link(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("The form link can only be sent for a new admission request."))
            if not rec.student_email or not rec.partner_id:
                raise UserError(_(
                    "Please set the student email on admission request %(ref)s before sending the link.",
                    ref=rec.name))
        for rec in self:
            rec._send_form_link_email()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("The form link has been sent."),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
