from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class FundRequisition(models.Model):
    _name = 'fund.requisition'
    _description = 'Fund Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(
        string='Requisition Number', readonly=True,
        copy=False, default=lambda self: _('New')
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company, required=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    project_id = fields.Many2one(
        'fund.project', string='Project', tracking=True
    )
    expense_head_id = fields.Many2one(
        'fund.expense.head', string='Expense Head', tracking=True
    )
    amount = fields.Monetary(
        string='Requested Amount', required=True,
        currency_field='currency_id', tracking=True
    )
    purpose = fields.Text(string='Purpose', required=True)
    request_date = fields.Date(
        string='Request Date',
        default=fields.Date.context_today, required=True
    )
    required_date = fields.Date(string='Required Date')
    requested_by = fields.Many2one(
        'res.users', string='Requested By',
        default=lambda self: self.env.user, required=True
    )
    attachment = fields.Binary(string='Supporting Attachment')
    attachment_name = fields.Char(string='Attachment Name')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('gm_approved', 'GM Approved'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True)

    gm_approver_id = fields.Many2one('res.users', string='GM Approver')
    md_approver_id = fields.Many2one('res.users', string='MD Approver')
    gm_approval_date = fields.Datetime(string='GM Approval Date')
    md_approval_date = fields.Datetime(string='MD Approval Date')
    gm_comment = fields.Text(string='GM Comment')
    md_comment = fields.Text(string='MD Comment')

    billed_amount = fields.Monetary(
        string='Billed Amount',
        default=0.0,
        currency_field='currency_id'
    )
    remaining_billable = fields.Monetary(
        string='Remaining Billable Amount',
        compute='_compute_remaining',
        store=True,
        currency_field='currency_id'
    )

    approval_history_ids = fields.One2many(
        'fund.requisition.history', 'requisition_id',
        string='Approval History'
    )

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'fund.requisition'
            ) or _('New')
        return super().create(vals)

    @api.depends('amount', 'billed_amount')
    def _compute_remaining(self):
        for rec in self:
            rec.remaining_billable = rec.amount - rec.billed_amount

    @api.constrains('project_id', 'expense_head_id')
    def _check_project_or_expense(self):
        for rec in self:
            if rec.project_id and rec.expense_head_id:
                raise ValidationError(
                    _('Use either a Project or Expense Head, not both.')
                )
            if not rec.project_id and not rec.expense_head_id:
                raise ValidationError(
                    _('Must have either a Project or Expense Head.')
                )

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Amount must be greater than zero.'))

    def _get_source(self):
        self.ensure_one()
        return self.project_id or self.expense_head_id

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft requisitions can be submitted.'))
            source = rec._get_source()
            if rec.amount > source.available_balance:
                raise ValidationError(
                    _('Insufficient balance. Available: %s, Requested: %s')
                    % (source.available_balance, rec.amount)
                )
            rec.write({'state': 'submitted'})
            self.env['fund.requisition.history'].create({
                'requisition_id': rec.id,
                'action': 'submitted',
                'user_id': self.env.user.id,
                'comment': 'Requisition submitted.',
            })
            source._compute_balances()

    def action_gm_approve(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Only submitted requisitions can be GM approved.'))
            rec.write({
                'state': 'gm_approved',
                'gm_approver_id': self.env.user.id,
                'gm_approval_date': fields.Datetime.now(),
            })
            self.env['fund.requisition.history'].create({
                'requisition_id': rec.id,
                'action': 'gm_approved',
                'user_id': self.env.user.id,
                'comment': rec.gm_comment or 'Approved by GM.',
            })

    def action_md_approve(self):
        for rec in self:
            if rec.state != 'gm_approved':
                raise UserError(_('GM must approve before MD.'))
            rec.write({
                'state': 'approved',
                'md_approver_id': self.env.user.id,
                'md_approval_date': fields.Datetime.now(),
            })
            self.env['fund.requisition.history'].create({
                'requisition_id': rec.id,
                'action': 'approved',
                'user_id': self.env.user.id,
                'comment': rec.md_comment or 'Approved by MD.',
            })
            source = rec._get_source()
            if source:
                source._compute_balances()

    def action_reject(self):
        for rec in self:
            if rec.state not in ('submitted', 'gm_approved'):
                raise UserError(_('Only submitted or GM approved can be rejected.'))
            rec.write({'state': 'rejected'})
            self.env['fund.requisition.history'].create({
                'requisition_id': rec.id,
                'action': 'rejected',
                'user_id': self.env.user.id,
                'comment': 'Requisition rejected.',
            })
            source = rec._get_source()
            if source:
                source._compute_balances()

    def action_cancel(self):
        for rec in self:
            if rec.state == 'approved' and rec.billed_amount > 0:
                raise UserError(_('Cannot cancel a requisition with existing bills.'))
            rec.write({'state': 'cancelled'})
            self.env['fund.requisition.history'].create({
                'requisition_id': rec.id,
                'action': 'cancelled',
                'user_id': self.env.user.id,
                'comment': 'Requisition cancelled.',
            })
            source = rec._get_source()
            if source:
                source._compute_balances()

    def action_close(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Only approved requisitions can be closed.'))
            rec.write({'state': 'closed'})

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ('rejected', 'cancelled'):
                raise UserError(_('Only rejected or cancelled can be reset.'))
            rec.write({'state': 'draft'})


class FundRequisitionHistory(models.Model):
    _name = 'fund.requisition.history'
    _description = 'Requisition Approval History'
    _order = 'id desc'

    requisition_id = fields.Many2one(
        'fund.requisition', string='Requisition', ondelete='cascade'
    )
    user_id = fields.Many2one('res.users', string='User', required=True)
    action = fields.Selection([
        ('submitted', 'Submitted'),
        ('gm_approved', 'GM Approved'),
        ('approved', 'MD Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('closed', 'Closed'),
    ], string='Action', required=True)
    comment = fields.Text(string='Comment')