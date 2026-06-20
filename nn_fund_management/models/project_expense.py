from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FundProject(models.Model):
    _name = 'fund.project'
    _description = 'Fund Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Project Name', required=True, tracking=True)
    code = fields.Char(string='Project Code', required=True)
    description = fields.Text(string='Description')
    company_id = fields.Many2one(
        'res.company', string='Company',
        required=True, default=lambda self: self.env.company
    )
    active = fields.Boolean(default=True)

    # Balance fields — all computed, no manual editing
    total_allocated = fields.Monetary(
        string='Total Allocated',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )
    available_balance = fields.Monetary(
        string='Available Balance',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )
    requisition_hold = fields.Monetary(
        string='Requisition Hold',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )
    transfer_hold = fields.Monetary(
        string='Transfer Hold',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )
    total_spent = fields.Monetary(
        string='Total Spent',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )
    incoming_transfers = fields.Monetary(
        string='Incoming Transfers',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )
    outgoing_transfers = fields.Monetary(
        string='Outgoing Transfers',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    _sql_constraints = [
        ('code_unique', 'unique(code, company_id)', 'Project code must be unique per company!'),
    ]

    @api.depends()
    def _compute_balances(self):
        # Placeholder — will be fully implemented
        # when allocation, requisition and transfer models are added
        for project in self:
            project.total_allocated = 0.0
            project.available_balance = 0.0
            project.requisition_hold = 0.0
            project.transfer_hold = 0.0
            project.total_spent = 0.0
            project.incoming_transfers = 0.0
            project.outgoing_transfers = 0.0

    @api.constrains(
        'available_balance', 'requisition_hold', 'transfer_hold'
    )
    def _check_no_negative_balance(self):
        for project in self:
            if project.available_balance < 0:
                raise ValidationError(
                    _('Available balance for project "%s" cannot be negative.')
                    % project.name
                )


class FundExpenseHead(models.Model):
    _name = 'fund.expense.head'
    _description = 'Fund Expense Head'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Expense Head', required=True, tracking=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Text(string='Description')
    company_id = fields.Many2one(
        'res.company', string='Company',
        required=True, default=lambda self: self.env.company
    )
    active = fields.Boolean(default=True)

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    # Balance fields — all computed, no manual editing
    total_allocated = fields.Monetary(
        string='Total Allocated',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )
    available_balance = fields.Monetary(
        string='Available Balance',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )
    requisition_hold = fields.Monetary(
        string='Requisition Hold',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )
    transfer_hold = fields.Monetary(
        string='Transfer Hold',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )
    total_spent = fields.Monetary(
        string='Total Spent',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )
    incoming_transfers = fields.Monetary(
        string='Incoming Transfers',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )
    outgoing_transfers = fields.Monetary(
        string='Outgoing Transfers',
        compute='_compute_balances',
        store=True,
        currency_field='currency_id'
    )

    _sql_constraints = [
        ('code_unique', 'unique(code, company_id)', 'Expense head code must be unique per company!'),
    ]

    @api.depends()
    def _compute_balances(self):
        for head in self:
            head.total_allocated = 0.0
            head.available_balance = 0.0
            head.requisition_hold = 0.0
            head.transfer_hold = 0.0
            head.total_spent = 0.0
            head.incoming_transfers = 0.0
            head.outgoing_transfers = 0.0

    @api.constrains('available_balance')
    def _check_no_negative_balance(self):
        for head in self:
            if head.available_balance < 0:
                raise ValidationError(
                    _('Available balance for expense head "%s" cannot be negative.')
                    % head.name
                )