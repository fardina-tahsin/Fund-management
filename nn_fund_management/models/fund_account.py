from odoo import models, fields

class FundAccount(models.Model):
    _name = 'fund.account'
    _description = 'Fund Account'

    name = fields.Char(string='Account Name', required=True)