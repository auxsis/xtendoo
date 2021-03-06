# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp

import logging
_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    bar_qty = fields.Float(
        string='Bar Quantity',
        digits=dp.get_precision('Product Unit of Measure')
    )

    @api.onchange('bar_qty')
    def onchange_bar_qty(self):
        for record in self:
            if record.bar_qty != 0 and record.product_id.weight != 0:
                record.product_uom_qty = record.bar_qty * record.product_id.weight

    @api.onchange('product_uom_qty')
    def onchange_product_uom_qty(self):
        for record in self:
            if record.product_uom_qty == 0 or record.product_id.weight == 0:
                record.bar_qty = 0
            else:
                record.bar_qty = record.product_uom_qty / record.product_id.weight
