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
        store=False,
        currency_field='currency_id'
    )

    available_balance = fields.Monetary(
        string='Available Balance',
        compute='_compute_balances',
        store=False,
        currency_field='currency_id'
    )

    requisition_hold = fields.Monetary(
        string='Requisition Hold',
        compute='_compute_balances',
        store=False,
        currency_field='currency_id'
    )

    transfer_hold = fields.Monetary(
        string='Transfer Hold',
        compute='_compute_balances',
        store=False,
        currency_field='currency_id'
    )

    total_spent = fields.Monetary(
        string='Total Spent',
        compute='_compute_balances',
        store=False,
        currency_field='currency_id'
    )

    incoming_transfers = fields.Monetary(
        string='Incoming Transfers',
        compute='_compute_balances',
        store=False,
        currency_field='currency_id'
    )

    outgoing_transfers = fields.Monetary(
        string='Outgoing Transfers',
        compute='_compute_balances',
        store=False,
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
        for project in self:
            # Approved allocations
            allocations = self.env['fund.allocation'].search([
                ('project_id', '=', project.id),
                ('state', '=', 'approved'),
            ])
            total_allocated = sum(allocations.mapped('amount'))

            # Requisitions on hold
            req_on_hold = self.env['fund.requisition'].search([
                ('project_id', '=', project.id),
                ('state', 'in', ('submitted', 'gm_approved')),
            ])
            requisition_hold = sum(req_on_hold.mapped('amount'))

            # Approved requisitions
            approved_reqs = self.env['fund.requisition'].search([
                ('project_id', '=', project.id),
                ('state', 'in', ('approved', 'closed')),
            ])
            total_spent = sum(approved_reqs.mapped('billed_amount'))
            approved_unspent = sum(approved_reqs.mapped('remaining_billable'))

            # Outgoing transfers on hold
            out_hold = self.env['fund.transfer'].search([
                ('source_project_id', '=', project.id),
                ('state', 'in', ('submitted', 'gm_approved')),
            ])
            transfer_hold = sum(out_hold.mapped('amount'))

            # Approved outgoing transfers
            out_approved = self.env['fund.transfer'].search([
                ('source_project_id', '=', project.id),
                ('state', '=', 'approved'),
            ])
            outgoing = sum(out_approved.mapped('amount'))

            # Approved incoming transfers
            in_approved = self.env['fund.transfer'].search([
                ('dest_project_id', '=', project.id),
                ('state', '=', 'approved'),
            ])
            incoming = sum(in_approved.mapped('amount'))

            project.total_allocated = total_allocated
            project.requisition_hold = requisition_hold
            project.transfer_hold = transfer_hold
            project.total_spent = total_spent
            project.incoming_transfers = incoming
            project.outgoing_transfers = outgoing
            
            project.available_balance = (
                total_allocated
                + incoming
                - outgoing
                - requisition_hold
                - transfer_hold
                - approved_unspent
                - total_spent
            )

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

    # Balance fields - all computed, no manual editing
    total_allocated = fields.Monetary(
        string='Total Allocated',
        compute='_compute_balances',
        store=False,
        currency_field='currency_id'
    )

    available_balance = fields.Monetary(
        string='Available Balance',
        compute='_compute_balances',
        store=False,
        currency_field='currency_id'
    )

    requisition_hold = fields.Monetary(
        string='Requisition Hold',
        compute='_compute_balances',
        store=False,
        currency_field='currency_id'
    )

    transfer_hold = fields.Monetary(
        string='Transfer Hold',
        compute='_compute_balances',
        store=False,
        currency_field='currency_id'
    )

    total_spent = fields.Monetary(
        string='Total Spent',
        compute='_compute_balances',
        store=False,
        currency_field='currency_id'
    )

    incoming_transfers = fields.Monetary(
        string='Incoming Transfers',
        compute='_compute_balances',
        store=False,
        currency_field='currency_id'
    )

    outgoing_transfers = fields.Monetary(
        string='Outgoing Transfers',
        compute='_compute_balances',
        store=False,
        currency_field='currency_id'
    )

    _sql_constraints = [
        ('code_unique', 'unique(code, company_id)', 'Expense head code must be unique per company!'),
    ]

    @api.depends()
    def _compute_balances(self):
        for head in self:
            allocations = self.env['fund.allocation'].search([
                ('expense_head_id', '=', head.id),
                ('state', '=', 'approved'),
            ])

            total_allocated = sum(allocations.mapped('amount'))

            req_on_hold = self.env['fund.requisition'].search([
                ('expense_head_id', '=', head.id),
                ('state', 'in', ('submitted', 'gm_approved')),
            ])

            requisition_hold = sum(req_on_hold.mapped('amount'))

            approved_reqs = self.env['fund.requisition'].search([
                ('expense_head_id', '=', head.id),
                ('state', 'in', ('approved', 'closed')),
            ])

            total_spent = sum(approved_reqs.mapped('billed_amount'))
            approved_unspent = sum(approved_reqs.mapped('remaining_billable'))

            out_hold = self.env['fund.transfer'].search([
                ('source_expense_head_id', '=', head.id),
                ('state', 'in', ('submitted', 'gm_approved')),
            ])

            transfer_hold = sum(out_hold.mapped('amount'))

            out_approved = self.env['fund.transfer'].search([
                ('source_expense_head_id', '=', head.id),
                ('state', '=', 'approved'),
            ])

            outgoing = sum(out_approved.mapped('amount'))

            in_approved = self.env['fund.transfer'].search([
                ('dest_expense_head_id', '=', head.id),
                ('state', '=', 'approved'),
            ])

            incoming = sum(in_approved.mapped('amount'))

            head.total_allocated = total_allocated
            head.requisition_hold = requisition_hold
            head.transfer_hold = transfer_hold
            head.total_spent = total_spent
            head.incoming_transfers = incoming
            head.outgoing_transfers = outgoing
            
            head.available_balance = (
                total_allocated
                + incoming
                - outgoing
                - requisition_hold
                - transfer_hold
                - approved_unspent
                - total_spent
            )

    @api.constrains('available_balance')
    def _check_no_negative_balance(self):
        for head in self:
            if head.available_balance < 0:
                raise ValidationError(
                    _('Available balance for expense head "%s" cannot be negative.')
                    % head.name
                )