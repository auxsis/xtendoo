from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    lot_id = fields.Many2one(
        'stock.production.lot', 'Lot', copy=False)
    first_selection = fields.Boolean(
        comodel_name='sale.order.line',
        string="firstSelection",
        default=False
    )

    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        self.first_selection=True
        super(SaleOrderLine, self).product_id_change()
        self.lot_id = False

    @api.onchange('product_id')
    def _onchange_product_id_set_lot_domain(self):
        available_lot_ids = []
        if self.order_id.warehouse_id and self.product_id:
            location = self.order_id.warehouse_id.lot_stock_id
            quants = self.env['stock.quant'].read_group([
                ('product_id', '=', self.product_id.id),
                ('location_id', 'child_of', location.id),
                ('quantity', '>', 0),
                ('lot_id', '!=', False),
            ], ['lot_id'], 'lot_id')
            available_lot_ids = [quant['lot_id'][0] for quant in quants]
        self.lot_id = False
        return {
            'domain': {'lot_id': [('id', 'in', available_lot_ids)]}
        }

    @api.onchange('product_uom_qty','lot_id','product_uom')
    def _onchage_quantity_or_lot(self):
        if self.first_selection !=True:
            if self.product_id:
                if self.product_id.tracking == 'lot':
                    if not self.lot_id:
                        raise UserError(_("Debe selecionar un Lote"))
                    if not self.lot_id.product_qty:
                        raise UserError(_("No hay suficiente stock para este lote"))   
                    if self.lot_id.product_qty < self.product_uom_qty:
                        raise UserError(_("No hay suficiente stock para este lote"))
                    if self.lot_id.product_qty < (self.product_uom_qty * self.product_uom.factor_inv):
                        raise UserError(_("No hay suficiente stock para este lote"))
            self.first_selection=False


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def get_move_from_line(self, line):
        move = self.env['stock.move']
        # i create this counter to check lot's univocity on move line
        lot_count = 0
        for p in line.order_id.picking_ids:
            for m in p.move_lines:
                move_line_id = m.move_line_ids.filtered(
                    lambda line: line.lot_id)
                if move_line_id and line.lot_id == move_line_id[:1].lot_id:
                    move = m
                    lot_count += 1
                    # if counter is 0 or > 1 means that something goes wrong
                    if lot_count != 1:
                        raise UserError(_('Can\'t retrieve lot on stock'))
        return move

    @api.model
    def _check_move_state(self, line):
        if line.lot_id:
            move = self.get_move_from_line(line)
            if move.state == 'confirmed':
                move._action_assign()
                move.refresh()
            if move.state != 'assigned':
                raise UserError(_('Can\'t reserve products for lot %s') %
                                line.lot_id.name)
        return True

    @api.multi
    def action_confirm(self):
        res = super(SaleOrder, self.with_context(sol_lot_id=True))\
            .action_confirm()
        for line in self.order_line:
            if not line.lot_id and line.product_id.tracking == 'lot':
                raise UserError(
                        _('You can\'t store this line %s with empty lot') %
                        line.product_id.name
                        )
            if line.lot_id:
                unreserved_moves = line.move_ids.filtered(
                    lambda move: move.product_uom_qty !=
                    move.reserved_availability
                )
                if unreserved_moves:
                    raise UserError(
                        _('Can\'t reserve products for lot %s')
                        % line.lot_id.name
                    )
            self._check_move_state(line)
        return res
