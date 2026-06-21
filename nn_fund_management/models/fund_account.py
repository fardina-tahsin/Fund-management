from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class FundAccount(models.Model):
    _name = 'fund.account'
    _description = 'Fund Account'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Account Name', required=True, copy=False, tracking=True)
    code = fields.Char(string='Account Code', required=True, copy=False)
    
    account_type = fields.Selection([
        ('bank', 'Bank'),
        ('cash', 'Cash'),
        ('other', 'Other'),
    ], string='Account Type', default='bank', required=True)
    
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id
    )

    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company
    )

    description = fields.Text(string='Description')

    incoming_fund_ids = fields.One2many(
        'fund.incoming', 'fund_account_id', string='Incoming Funds'
    )

    total_received = fields.Monetary(
        string='Total Received',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )

    unassigned_balance = fields.Monetary(
        string='Unassigned Balance',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )

    on_hold_balance = fields.Monetary(
        string='On Hold Balance',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )

    assigned_balance = fields.Monetary(
        string='Assigned Balance',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Account Name must be unique!'),
        ('code_unique', 'unique(code)', 'Account Code must be unique!'),
    ]
    
    @api.depends(
    'incoming_fund_ids.amount',
    'incoming_fund_ids.state',
    )

    def _compute_balances(self):
        for account in self:
            # Total confirmed incoming funds
            confirmed = account.incoming_fund_ids.filtered(
                lambda f: f.state == 'confirmed'
            )
            total_received = sum(confirmed.mapped('amount'))

            # Allocations on hold (submitted or gm_approved)
            allocations_on_hold = self.env['fund.allocation'].search([
                ('fund_account_id', '=', account.id),
                ('state', 'in', ('submitted', 'gm_approved')),
            ])
            on_hold = sum(allocations_on_hold.mapped('amount'))

            # Approved allocations (assigned to projects/expense heads)
            allocations_approved = self.env['fund.allocation'].search([
                ('fund_account_id', '=', account.id),
                ('state', '=', 'approved'),
            ])
            assigned = sum(allocations_approved.mapped('amount'))

            account.total_received = total_received
            account.on_hold_balance = on_hold
            account.assigned_balance = assigned
            account.unassigned_balance = total_received - on_hold - assigned


class IncomingFund(models.Model):
    _name = 'fund.incoming'
    _description = 'Incoming Fund Transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New')
    )

    fund_account_id = fields.Many2one(
        'fund.account', string='Fund Account',
        required=True, ondelete='restrict', tracking=True
    )

    currency_id = fields.Many2one(
        'res.currency', related='fund_account_id.currency_id',
        store=True, string='Currency'
    )

    amount = fields.Monetary(
        string='Amount', required=True,
        currency_field='currency_id', tracking=True
    )

    transaction_date = fields.Date(
        string='Transaction Date', required=True,
        default=fields.Date.context_today, tracking=True
    )

    transaction_reference = fields.Char(
        string='Transaction Reference', required=True, copy=False,
        tracking=True
    )

    sender = fields.Char(string='Sender/Source', tracking=True)
    description = fields.Text(string='Description')
    attachment = fields.Binary(string='Attachment')
    attachment_name = fields.Char(string='Attachment Name')
    
    company_id = fields.Many2one(
        'res.company', string='Company',
        required=True, default=lambda self: self.env.company
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    _sql_constraints = [
        (
            'unique_transaction_reference_per_account',
            'unique(fund_account_id, transaction_reference)',
            'Transaction reference must be unique per fund account!'
        ),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'fund.incoming.transaction'
            ) or _('New')
        return super().create(vals)

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Amount must be greater than zero.'))

    def action_confirm(self):
        if not self.env.user.has_group('nn_fund_management.group_fund_finance'):
            raise UserError(_('Only Finance Users can confirm incoming funds.'))
        
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_('Only draft records can be confirmed.'))
            rec.write({'state': 'confirmed'})
            rec.fund_account_id._compute_balances()

    def action_cancel(self):
        for rec in self:
            if rec.state == 'confirmed':
                raise ValidationError(
                    _('Confirmed records cannot be cancelled directly. Please contact an administrator.')
                )
            rec.write({'state': 'cancelled'})
            rec.fund_account_id._compute_balances()

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise ValidationError(_('Only cancelled records can be reset to draft.'))
            rec.write({'state': 'draft'})