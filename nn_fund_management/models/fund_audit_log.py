from odoo import models, fields


class FundAuditLog(models.Model):
    _name = 'fund.audit.log'
    _description = 'Fund Audit Log'
    _order = 'create_date desc'

    name = fields.Char(string='Reference', required=True)
    
    user_id = fields.Many2one(
        'res.users', string='User', required=True,
        default=lambda self: self.env.user
    )

    action = fields.Char(string='Action', required=True)
    previous_state = fields.Char(string='Previous Status')
    new_state = fields.Char(string='New Status')
    
    amount = fields.Monetary(
        string='Amount', currency_field='currency_id'
    )

    currency_id = fields.Many2one('res.currency')
    
    fund_account_id = fields.Many2one(
        'fund.account', string='Fund Account'
    )

    project_id = fields.Many2one(
        'fund.project', string='Project'
    )
    expense_head_id = fields.Many2one(
        'fund.expense.head', string='Expense Head'
    )
    
    comment = fields.Text(string='Comment')
    model_name = fields.Char(string='Document Type')
    record_id = fields.Integer(string='Record ID')
    record_ref = fields.Char(string='Record Reference')