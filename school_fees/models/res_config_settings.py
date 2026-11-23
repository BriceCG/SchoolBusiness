from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    school_fee_product_id = fields.Many2one(
        related='company_id.school_fee_product_id', readonly=False)
    school_default_installments = fields.Integer(
        related='company_id.school_default_installments', readonly=False)
    school_reminder_enabled = fields.Boolean(
        related='company_id.school_reminder_enabled', readonly=False)
    school_reminder_days = fields.Integer(
        related='company_id.school_reminder_days', readonly=False)
    school_reminder_max = fields.Integer(
        related='company_id.school_reminder_max', readonly=False)
    school_reminder_interval_days = fields.Integer(
        related='company_id.school_reminder_interval_days', readonly=False)
    school_reminder_auto = fields.Boolean(
        related='company_id.school_reminder_auto', readonly=False)
