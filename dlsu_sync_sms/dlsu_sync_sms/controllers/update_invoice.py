from odoo import http, tools
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class UpdateURL(http.Controller):
    """Controller for invoice update endpoints"""
    @http.route('/update_assessment', type='http' ,auth='public', csrf=False)
    def update_assessment(self, redirect=None, **kw):
        """Update assessment invoice via HTTP endpoint"""
        invoice_id = ''

        if 'invoice_id' in kw:
            invoice_id = kw['invoice_id']
            move =  http.request.env['account.move'].sudo().search([('id','=', int(invoice_id)), ('is_first_payment','=', True)])

            try:
                if move:
                    portal_sync = http.request.env['sync.sms.settings'].sudo().search([], limit=1)
                    portal_sync.api_paid_invoice_id = move.id

                    portal_sync.get_odoo_invoice()
                    portal_sync.post_invoice_by_odoo()

                    vals = {
                        'status': 'Fetch Success',
                    }

                    json_vals = json.dumps(vals)
                    return  json_vals
            except Exception as e:
                vals = {
                    'status': (f"Fetch Failed: (No Invoice Found){e}"),
                        
                }

                json_vals = json.dumps(vals)
                return  json_vals
        else:
            vals = {
                'status': 'Fetch Failed',
            }
            json_vals = json.dumps(vals)
            return  json_vals
            
    @http.route('/update_special_treatment', type='http' ,auth='public', csrf=False)
    def update_special_treatment(self, redirect=None, **kw):
        invoice_id = ''

        if 'invoice_id' in kw:
            invoice_id = kw['invoice_id']
            move =  http.request.env['account.move'].sudo().search([('id','=', int(invoice_id))])

            try:
                if move:
                    portal_sync = http.request.env['sync.sms.settings'].sudo().search([], limit=1)
                    portal_sync.api_paid_invoice_id = move.id
                
                    portal_sync.get_odoo_invoice()
                    portal_sync.api_user_id = http.request.env.user.id

                    portal_sync.post_invoice_by_odoo()

                    vals = {
                        'status': 'Fetch Success',
                    }

                    json_vals = json.dumps(vals)
                    return  json_vals

            except Exception as e:
                vals = {
                    'status': (f"Fetch Failed: (No Invoice Found) {e}"),
                }

                json_vals = json.dumps(vals)
                return  json_vals
        else:
            vals = {
                'status': 'Fetch Failed',
            }
            json_vals = json.dumps(vals)
            return  json_vals
