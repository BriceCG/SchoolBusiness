from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    param = env['ir.config_parameter'].sudo()
    product_id = param.get_param('school_fees.migrate_product_id')
    if product_id:
        product = env['product.product'].browse(int(product_id)).exists()
        if product:
            env['res.company'].search([('school_fee_product_id', '=', False)]).write(
                {'school_fee_product_id': product.id})
        param.set_param('school_fees.migrate_product_id', False)
