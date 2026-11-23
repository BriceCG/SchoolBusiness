from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    school_period_type = fields.Selection(
        related='company_id.school_period_type', readonly=False)
    current_school_year_id = fields.Many2one(
        related='company_id.current_school_year_id', readonly=False)

    def action_close_school_year(self):
        self.ensure_one()
        year = self.current_school_year_id
        if not year:
            return False
        # The current year is replaced first, otherwise it cannot be closed.
        self.company_id.current_school_year_id = False
        year.action_close()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
