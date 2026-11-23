from odoo import models


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    def _action_send_mail(self, auto_commit=False):
        result = super()._action_send_mail(auto_commit=auto_commit)
        if self.env.context.get('school_fee_reminder') and self.model == 'account.move':
            # the reminder has been sent from the composer: count it
            for wizard in self:
                self.env['account.move'].browse(wizard._evaluate_res_ids())._school_reminder_record()
        return result
