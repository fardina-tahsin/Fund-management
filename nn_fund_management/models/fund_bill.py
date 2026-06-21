from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class FundBill(models.Model):
    _name = 'fund.bill'
    _description = 'Fund Bill'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(
        string='Bill Number', readonly=True,
        copy=False, default=lambda self: _('New')
    )
    
    requisition_id = fields.Many2one(
        'fund.requisition', string='Requisition',
        required=True, tracking=True,
        domain=[('state', '=', 'approved')]
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='requisition_id.currency_id',
        store=True
    )

    project_id = fields.Many2one(
        'fund.project', string='Project',
        related='requisition_id.project_id',
        store=True
    )

    expense_head_id = fields.Many2one(
        'fund.expense.head', string='Expense Head',
        related='requisition_id.expense_head_id',
        store=True
    )

    amount = fields.Monetary(
        string='Bill Amount', required=True,
        currency_field='currency_id', tracking=True
    )

    bill_date = fields.Date(
        string='Bill Date',
        default=fields.Date.context_today, required=True
    )

    description = fields.Text(string='Description')
    vendor = fields.Char(string='Vendor/Payee')
    attachment = fields.Binary(string='Attachment')
    attachment_name = fields.Char(string='Attachment Name')
    
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'fund.bill'
            ) or _('New')
        return super().create(vals)

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Bill amount must be greater than zero.'))

    @api.constrains('requisition_id', 'amount')
    def _check_requisition_balance(self):
        for rec in self:
            if rec.state == 'cancelled':
                continue
            req = rec.requisition_id
            if req.state != 'approved':
                raise ValidationError(
                    _('Bills can only be created against approved requisitions.')
                )
            # Calculate remaining excluding current bill
            other_bills = req.mapped('bill_ids').filtered(
                lambda b: b.id != rec.id and b.state == 'posted'
            )
            already_billed = sum(other_bills.mapped('amount'))
            if rec.amount > (req.amount - already_billed):
                raise ValidationError(
                    _('Bill amount (%(bill)s) exceeds remaining billable amount (%(remaining)s).')
                    % {
                        'bill': rec.amount,
                        'remaining': req.amount - already_billed
                    }
                )

    def action_post(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft bills can be posted.'))

            req = rec.requisition_id
            if req.state != 'approved':
                raise UserError(_('The linked requisition must be approved.'))

            # Check remaining billable
            if rec.amount > req.remaining_billable:
                raise ValidationError(
                    _('Bill amount %(bill)s exceeds remaining billable %(remaining)s.')
                    % {'bill': rec.amount, 'remaining': req.remaining_billable}
                )

            rec.write({'state': 'posted'})

            # Update requisition billed amount
            req.billed_amount += rec.amount

            # Update project/expense head spent amount
            source = req.project_id or req.expense_head_id
            if source:
                source._compute_balances()

    def action_cancel(self):
        for rec in self:
            if rec.state == 'cancelled':
                raise UserError(_('Bill is already cancelled.'))

            was_posted = rec.state == 'posted'
            rec.write({'state': 'cancelled'})

            if was_posted:
                # Return amount to requisition
                req = rec.requisition_id
                req.billed_amount -= rec.amount

                # Update balances
                source = req.project_id or req.expense_head_id
                if source:
                    source._compute_balances()

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_('Only cancelled bills can be reset to draft.'))
            rec.write({'state': 'draft'})