from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class FundAllocation(models.Model):
    _name = 'fund.allocation'
    _description = 'Fund Allocation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(
        string='Request Number', readonly=True,
        copy=False, default=lambda self: _('New')
    )

    fund_account_id = fields.Many2one(
        'fund.account', string='Fund Account',
        required=True, tracking=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='fund_account_id.currency_id',
        store=True
    )

    amount = fields.Monetary(
        string='Amount', required=True,
        currency_field='currency_id', tracking=True
    )

    purpose = fields.Text(string='Purpose', required=True)
    
    request_date = fields.Date(
        string='Request Date',
        default=fields.Date.context_today, required=True
    )

    requested_by = fields.Many2one(
        'res.users', string='Requested By',
        default=lambda self: self.env.user, required=True
    )

    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company, required=True
    )

    attachment = fields.Binary(string='Attachment')
    attachment_name = fields.Char(string='Attachment Name')

    # Either project OR expense head - not both
    project_id = fields.Many2one(
        'fund.project', string='Project', tracking=True
    )

    expense_head_id = fields.Many2one(
        'fund.expense.head', string='Expense Head', tracking=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('gm_approved', 'GM Approved'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Approval fields
    gm_approver_id = fields.Many2one(
        'res.users', string='GM Approver'
    )

    md_approver_id = fields.Many2one(
        'res.users', string='MD Approver'
    )

    gm_approval_date = fields.Datetime(string='GM Approval Date')
    md_approval_date = fields.Datetime(string='MD Approval Date')
    gm_comment = fields.Text(string='GM Comment')
    md_comment = fields.Text(string='MD Comment')

    # Approval history
    approval_history_ids = fields.One2many(
        'fund.approval.history', 'allocation_id',
        string='Approval History'
    )

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'fund.allocation'
            ) or _('New')
        return super().create(vals)

    @api.constrains('project_id', 'expense_head_id')
    def _check_project_or_expense(self):
        for rec in self:
            if rec.project_id and rec.expense_head_id:
                raise ValidationError(
                    _('An allocation must use either a Project or an Expense Head, not both.')
                )
            if not rec.project_id and not rec.expense_head_id:
                raise ValidationError(
                    _('An allocation must have either a Project or an Expense Head.')
                )

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Amount must be greater than zero.'))

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft allocations can be submitted.'))

            # Check available unassigned balance
            if rec.amount > rec.fund_account_id.unassigned_balance:
                raise ValidationError(
                    _('Insufficient unassigned balance. Available: %s, Requested: %s')
                    % (rec.fund_account_id.unassigned_balance, rec.amount)
                )

            rec.write({'state': 'submitted'})

            # Log approval history
            self.env['fund.approval.history'].create({
                'allocation_id': rec.id,
                'action': 'submitted',
                'user_id': self.env.user.id,
                'date': fields.Datetime.now(),
                'comment': 'Allocation submitted for approval.',
            })

            # Trigger balance recompute - money goes on hold
            rec.fund_account_id._compute_balances()

    def action_gm_approve(self):
        if not self.env.user.has_group('nn_fund_management.group_fund_gm'):
            raise UserError(_('Only GM Approvers can perform this action.'))
        
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Only submitted allocations can be GM approved.'))

            rec.write({
                'state': 'gm_approved',
                'gm_approver_id': self.env.user.id,
                'gm_approval_date': fields.Datetime.now(),
            })

            self.env['fund.approval.history'].create({
                'allocation_id': rec.id,
                'action': 'gm_approved',
                'user_id': self.env.user.id,
                'date': fields.Datetime.now(),
                'comment': rec.gm_comment or 'Approved by GM.',
            })

    def action_md_approve(self):
        if not self.env.user.has_group('nn_fund_management.group_fund_md'):
            raise UserError(_('Only MD Approvers can perform this action.'))

        for rec in self:
            if rec.state != 'gm_approved':
                raise UserError(_('GM must approve before MD approval.'))

            rec.write({
                'state': 'approved',
                'md_approver_id': self.env.user.id,
                'md_approval_date': fields.Datetime.now(),
            })

            self.env['fund.approval.history'].create({
                'allocation_id': rec.id,
                'action': 'approved',
                'user_id': self.env.user.id,
                'date': fields.Datetime.now(),
                'comment': rec.md_comment or 'Approved by MD.',
            })

            # Money moves from hold to project/expense head
            rec.fund_account_id._compute_balances()
            if rec.project_id:
                rec.project_id._compute_balances()
            if rec.expense_head_id:
                rec.expense_head_id._compute_balances()

    def action_reject(self):
        for rec in self:
            if rec.state not in ('submitted', 'gm_approved'):
                raise UserError(_('Only submitted or GM approved allocations can be rejected.'))

            rec.write({'state': 'rejected'})

            self.env['fund.approval.history'].create({
                'allocation_id': rec.id,
                'action': 'rejected',
                'user_id': self.env.user.id,
                'date': fields.Datetime.now(),
                'comment': 'Allocation rejected.',
            })

            # Money returns to unassigned balance
            rec.fund_account_id._compute_balances()

    def action_cancel(self):
        for rec in self:
            if rec.state in ('approved',):
                raise UserError(
                    _('Approved allocations cannot be cancelled directly.')
                )
            rec.write({'state': 'cancelled'})

            self.env['fund.approval.history'].create({
                'allocation_id': rec.id,
                'action': 'cancelled',
                'user_id': self.env.user.id,
                'date': fields.Datetime.now(),
                'comment': 'Allocation cancelled.',
            })

            rec.fund_account_id._compute_balances()

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ('rejected', 'cancelled'):
                raise UserError(
                    _('Only rejected or cancelled allocations can be reset to draft.')
                )
            rec.write({'state': 'draft'})


class FundApprovalHistory(models.Model):
    _name = 'fund.approval.history'
    _description = 'Fund Approval History'
    _order = 'date desc'

    allocation_id = fields.Many2one(
        'fund.allocation', string='Allocation', ondelete='cascade'
    )
    
    user_id = fields.Many2one(
        'res.users', string='User', required=True
    )

    action = fields.Selection([
        ('submitted', 'Submitted'),
        ('gm_approved', 'GM Approved'),
        ('approved', 'MD Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Action', required=True)

    date = fields.Datetime(string='Date', required=True)
    comment = fields.Text(string='Comment')