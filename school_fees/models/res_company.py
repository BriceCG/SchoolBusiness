from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    school_fee_product_id = fields.Many2one(
        'product.product', string="Tuition Product", domain="[('type', '=', 'service')]",
        help="Product used on the tuition invoices (it gives the income account and the taxes).")
    school_default_installments = fields.Integer(
        string="Default Number of Payments", default=1,
        help="Number of payments proposed by default for a new student. "
             "It can be changed on each student.")

    school_reminder_enabled = fields.Boolean(string="Overdue Reminders")
    school_reminder_days = fields.Integer(
        string="Days After Due Date", default=5,
        help="A tuition invoice is reminded when it is overdue for at least this number of days.")
    school_reminder_max = fields.Integer(
        string="Number of Reminders", default=3,
        help="Maximum number of reminders sent for the same invoice.")
    school_reminder_interval_days = fields.Integer(
        string="Days Between Reminders", default=7,
        help="Minimum number of days between two reminders of the same invoice.")
    school_reminder_auto = fields.Boolean(
        string="Send Automatically",
        help="The reminders are sent every day without any manual action.")

    _sql_constraints = [
        ('school_reminder_days_positive', 'check(school_reminder_days >= 0)',
         "The number of days after the due date cannot be negative."),
        ('school_reminder_max_positive', 'check(school_reminder_max >= 1)',
         "The number of reminders must be strictly positive."),
        ('school_reminder_interval_positive', 'check(school_reminder_interval_days >= 1)',
         "The number of days between two reminders must be strictly positive."),
        ('school_default_installments_positive', 'check(school_default_installments > 0)',
         "The number of payments must be strictly positive."),
    ]
