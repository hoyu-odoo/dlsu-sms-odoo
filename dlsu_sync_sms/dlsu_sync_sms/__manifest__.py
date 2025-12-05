# -*- coding: utf-8 -*-
{

	'name': 'DLSU-Dasma Sync SMS',
	'version': '1.0',
	'category': 'Toolkit Custom',
	'summary': 'Standard Sync SMS Module of Toolkit',
	'description': """

		Standard Sync SMS Module of Toolkit
		
	""",
	'author': 'Toolkt Inc',
	'depends': [
		'base',
        'dlsu_school',
        'product',
        'account',
        'stock'
	],
	'data': [
		'security/security.xml',
		'security/ir.model.access.csv',
		'views/menu.xml',
		'views/sync_v2.xml',
		'views/sms_applicant.xml',
		'views/sms_product.xml',
        'views/sms_student.xml',
        'views/sms_invoice.xml',
        'views/partners.xml',
		# 'views/sequence.xml',
		# 'views/configuration.xml',
		# 'reports/reports.xml',
        'views/account_payment.xml',
        'views/sync_log.xml',

	],
	'installable': True,

}
