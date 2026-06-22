from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class FundTransfer(models.Model):
    _name = 'fund.transfer'
    _description = 'Fund Transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(
        string='Transfer Number', readonly=True,
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

    amount = fields.Monetary(
        string='Amount', required=True,
        currency_field='currency_id', tracking=True
    )

    reason = fields.Text(string='Reason', required=True)
    
    request_date = fields.Date(
        string='Request Date',
        default=fields.Date.context_today, required=True
    )

    requested_by = fields.Many2one(
        'res.users', string='Requested By',
        default=lambda self: self.env.user, required=True
    )

    # Source - either project or expense head
    source_project_id = fields.Many2one(
        'fund.project', string='Source Project', tracking=True
    )

    source_expense_head_id = fields.Many2one(
        'fund.expense.head', string='Source Expense Head', tracking=True
    )

    # Destination - either project or expense head
    dest_project_id = fields.Many2one(
        'fund.project', string='Destination Project', tracking=True
    )

    dest_expense_head_id = fields.Many2one(
        'fund.expense.head', string='Destination Expense Head', tracking=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('gm_approved', 'GM Approved'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    gm_approver_id = fields.Many2one('res.users', string='GM Approver')
    md_approver_id = fields.Many2one('res.users', string='MD Approver')
    gm_approval_date = fields.Datetime(string='GM Approval Date')
    md_approval_date = fields.Datetime(string='MD Approval Date')
    gm_comment = fields.Text(string='GM Comment')
    md_comment = fields.Text(string='MD Comment')

    approval_history_ids = fields.One2many(
        'fund.transfer.history', 'transfer_id',
        string='Approval History'
    )

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'fund.transfer'
            ) or _('New')
        return super().create(vals)

    def _get_source(self):
        self.ensure_one()
        return self.source_project_id or self.source_expense_head_id

    def _get_destination(self):
        self.ensure_one()
        return self.dest_project_id or self.dest_expense_head_id

    @api.constrains(
        'source_project_id', 'source_expense_head_id',
        'dest_project_id', 'dest_expense_head_id'
    )

    def _check_source_destination(self):
        for rec in self:
            # Must have exactly one source
            if rec.source_project_id and rec.source_expense_head_id:
                raise ValidationError(_('Select either a source project or source expense head, not both.'))
            if not rec.source_project_id and not rec.source_expense_head_id:
                raise ValidationError(_('Must have a source project or expense head.'))

            # Must have exactly one destination
            if rec.dest_project_id and rec.dest_expense_head_id:
                raise ValidationError(_('Select either a destination project or destination expense head, not both.'))
            if not rec.dest_project_id and not rec.dest_expense_head_id:
                raise ValidationError(_('Must have a destination project or expense head.'))

            # Source and destination cannot be the same
            if (rec.source_project_id and
                    rec.source_project_id == rec.dest_project_id):
                raise ValidationError(_('Source and destination cannot be the same project.'))
            if (rec.source_expense_head_id and
                    rec.source_expense_head_id == rec.dest_expense_head_id):
                raise ValidationError(_('Source and destination cannot be the same expense head.'))

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Transfer amount must be greater than zero.'))

    def _log_audit(self, action, previous_state, new_state, comment=''):
        self.env['fund.audit.log'].create({
            'name': self.name,
            'user_id': self.env.user.id,
            'action': action,
            'previous_state': previous_state,
            'new_state': new_state,
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'project_id': self.source_project_id.id if self.source_project_id else False,
            'expense_head_id': self.source_expense_head_id.id if self.source_expense_head_id else False,
            'comment': comment,
            'model_name': 'Fund Transfer',
            'record_id': self.id,
            'record_ref': self.name,
        })
    
    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft transfers can be submitted.'))

            source = rec._get_source()
            if not source:
                raise ValidationError(_('Please select a source.'))

            if rec.amount > source.available_balance:
                raise ValidationError(
                    _('Insufficient source balance. Available: %s, Requested: %s')
                    % (source.available_balance, rec.amount)
                )
            
            rec._log_audit('Submitted', 'draft', 'submitted')

            rec.write({'state': 'submitted'})

            self.env['fund.transfer.history'].create({
                'transfer_id': rec.id,
                'action': 'submitted',
                'user_id': self.env.user.id,
                'comment': 'Transfer submitted for approval.',
            })

            # Put on transfer hold
            source._compute_balances()

    def action_gm_approve(self):
        if not self.env.user.has_group('nn_fund_management.group_fund_gm'):
            raise UserError(_('Only GM Approvers can perform this action.'))
        
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Only submitted transfers can be GM approved.'))

            rec._log_audit('GM Approved', 'submitted', 'gm_approved')

            rec.write({
                'state': 'gm_approved',
                'gm_approver_id': self.env.user.id,
                'gm_approval_date': fields.Datetime.now(),
            })

            self.env['fund.transfer.history'].create({
                'transfer_id': rec.id,
                'action': 'gm_approved',
                'user_id': self.env.user.id,
                'comment': rec.gm_comment or 'Approved by GM.',
            })

    def action_md_approve(self):
        if not self.env.user.has_group('nn_fund_management.group_fund_md'):
            raise UserError(_('Only MD Approvers can perform this action.'))
        
        for rec in self:
            if rec.state != 'gm_approved':
                raise UserError(_('GM must approve before MD.'))

            rec._log_audit('MD Approved', 'gm_approved', 'approved')

            rec.write({
                'state': 'approved',
                'md_approver_id': self.env.user.id,
                'md_approval_date': fields.Datetime.now(),
            })

            self.env['fund.transfer.history'].create({
                'transfer_id': rec.id,
                'action': 'approved',
                'user_id': self.env.user.id,
                'comment': rec.md_comment or 'Approved by MD.',
            })

            # Move money from source to destination
            source = rec._get_source()
            dest = rec._get_destination()
            if source:
                source._compute_balances()
            if dest:
                dest._compute_balances()

    def action_reject(self):
        for rec in self:
            if rec.state not in ('submitted', 'gm_approved'):
                raise UserError(_('Only submitted or GM approved transfers can be rejected.'))

            rec._log_audit('Rejected', rec.state, 'rejected')

            rec.write({'state': 'rejected'})

            self.env['fund.transfer.history'].create({
                'transfer_id': rec.id,
                'action': 'rejected',
                'user_id': self.env.user.id,
                'comment': 'Transfer rejected.',
            })

            # Return to source
            source = rec._get_source()
            if source:
                source._compute_balances()

    def action_cancel(self):
        for rec in self:
            if rec.state == 'approved':
                raise UserError(_('Approved transfers cannot be cancelled.'))

            rec._log_audit('Cancelled', rec.state, 'cancelled')

            rec.write({'state': 'cancelled'})

            self.env['fund.transfer.history'].create({
                'transfer_id': rec.id,
                'action': 'cancelled',
                'user_id': self.env.user.id,
                'comment': 'Transfer cancelled.',
            })

            source = rec._get_source()
            if source:
                source._compute_balances()

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ('rejected', 'cancelled'):
                raise UserError(_('Only rejected or cancelled transfers can be reset.'))
            
            rec._log_audit('Reset to Draft', rec.state, 'draft')
            
            rec.write({'state': 'draft'})

    def unlink(self):
        for rec in self:
            if rec.state not in ('draft', 'cancelled'):
                raise UserError(
                    _('You cannot delete a confirmed record. Please cancel it first.')
                )
        return super().unlink()


class FundTransferHistory(models.Model):
    _name = 'fund.transfer.history'
    _description = 'Fund Transfer History'
    _order = 'id desc'

    transfer_id = fields.Many2one(
        'fund.transfer', string='Transfer', ondelete='cascade'
    )

    user_id = fields.Many2one('res.users', string='User', required=True)
    
    action = fields.Selection([
        ('submitted', 'Submitted'),
        ('gm_approved', 'GM Approved'),
        ('approved', 'MD Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Action', required=True)
    
    comment = fields.Text(string='Comment')