{
    'name': "NN Fund Management",
    'summary': "Comprehensive fund management system",
    'version': '17.0.1.0.0',
    'author': "Fardina Tahsin",
    'category': 'Accounting/Fund Management',
    'depends': ['base', 'mail'],
    
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/fund_account_views.xml',
        'views/project_expense_views.xml',
    ],

    'installable': True,
    'application': True,
}

