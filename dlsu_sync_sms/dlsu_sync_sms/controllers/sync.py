from odoo import http, tools
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class SyncURL(http.Controller):
    """Controller for SMS synchronization endpoints"""
    @http.route('/create_invoice_adjustment', type='http' ,auth='public', csrf=False)
    def create_invoice_adjustment(self, redirect=None, **kw):
        """Create invoice adjustment for a customer via HTTP endpoint"""

        customer_id = '' # 199802320
        invoice_id = '' # 1

        if 'customer_id' in kw:
            customer_id = kw['customer_id']
            
        try:
            portal_sync = http.request.env['sync.sms.settings'].sudo().search([], limit=1)
            cust_id = customer_id


            portal_sync.create_ajustment_partner(cust_id)


            vals = {
                'status': 'Fetch Success',
            }

            json_vals = json.dumps(vals)
            return  json_vals
            
        except Exception as e:
            vals = {
                    'status': 'Fetch Failed (Check API Connection if ever )',
            }

            json_vals = json.dumps(vals)
            return  json_vals

    @http.route('/create_invoice_assessment', type='http' ,auth='public', csrf=False)
    def create_invoice_assessment(self, redirect=None, **kw):

        customer_id = '' # 199802320
        invoice_id = '' # 1

        if 'customer_id' in kw:
            customer_id = kw['customer_id']
            partner =  http.request.env['res.partner'].sudo().search([('customer_id','=', int(customer_id))])

        if 'invoice_id' in kw:
            invoice_id = kw['invoice_id']
            

        try:
            portal_sync = http.request.env['sync.sms.settings'].sudo().search([], limit=1)
            cust_id = portal_sync.customer_id 
            cust_id = customer_id

            inv_id = portal_sync.invoice_id
            inv_id = invoice_id


        
            portal_sync.sync_invoice_detail_view_by_customer_id(cust_id)
            portal_sync.sync_invoice_pay_view_by_customer_id(cust_id)

            portal_sync.create_assessment_invoices_by_invoice_id(inv_id)
            portal_sync.create_ajustment_partner(cust_id)



            vals = {
                'status': 'Fetch Success',
            }

            json_vals = json.dumps(vals)
            return  json_vals
            
        except Exception as e:
            vals = {
                    'status': 'Fetch Failed (Check API Connection if ever )',
            }

            json_vals = json.dumps(vals)
            return  json_vals
        
        
    @http.route('/master_sync_assessment', type='http' ,auth='public', csrf=False)
    def master_sync_assement(self, redirect=None, **kw):

        customer_id = '' # 199802320
        invoice_id = '' # 1

        if 'customer_id' in kw:
            customer_id = kw['customer_id']
            # partner =  http.request.env['res.partner'].sudo().search([('customer_id','=', int(customer_id))])

        if 'invoice_id' in kw:
            invoice_id = kw['invoice_id']
            

        try:
            portal_sync = http.request.env['sync.sms.settings'].sudo().search([], limit=1)
            # cust_id = portal_sync.customer_id 
            cust_id = customer_id

            inv_id = invoice_id


        

            portal_sync.sync_invoice_detail_view_by_invoice_id(inv_id)
            request.env.cr.commit()

            portal_sync.sync_invoice_pay_view_by_invoice_id(inv_id)
            request.env.cr.commit()
            portal_sync.sync_create_customer_v3(cust_id)
            request.env.cr.commit()


            portal_sync.create_ajustment_partner_v2(cust_id)
            request.env.cr.commit()

            vals = {
                'status': 'Fetch Success',
            }

            json_vals = json.dumps(vals)
            return  json_vals
            
        except Exception as e:
            vals = {
                    'status': 'Fetch Failed (Check API Connection if ever )',
            }

            json_vals = json.dumps(vals)
            return  json_vals
        
    @http.route('/master_sync_application', type='http' ,auth='public', csrf=False)
    def master_sync_application(self, redirect=None, **kw):

        customer_id = '' # 202400232188
        invoice_id = '' # 1022

        if 'customer_id' in kw:
            customer_id = kw['customer_id']
            # partner =  http.request.env['res.partner'].sudo().search([('customer_id','=', int(customer_id))])
        
        if 'invoice_id' in kw:
            invoice_id = kw['invoice_id']

            
        try:
            portal_sync = http.request.env['sync.sms.settings'].sudo().search([], limit=1)
            cust_id = portal_sync.customer_id 
            cust_id = customer_id

            inv_id = portal_sync.invoice_id
            inv_id = invoice_id

            portal_sync.sync_invoice_detail_view_by_invoice_id(inv_id)
            request.env.cr.commit()
            portal_sync.sync_invoice_pay_view_by_invoice_id(inv_id)
            request.env.cr.commit()

            # CUSTOMER CREATION 
            # if not partner:
            # portal_sync.sync_create_customer_v2(cust_id)
            portal_sync.sync_create_customer_v3(cust_id)
            request.env.cr.commit()

            portal_sync.create_application_invoices_by_invoice_id(inv_id)
            request.env.cr.commit()

            portal_sync.sync_create_reservation(inv_id)
            request.env.cr.commit()

            portal_sync.invoice_sync_back_odoo_v2(inv_id)
            request.env.cr.commit()

            vals = {
                'status': 'Fetch Success',
            }

            json_vals = json.dumps(vals)
            return  json_vals
            
        except Exception as e:
            vals = {
                    'status': 'Fetch Failed (Check API Connection if ever )',
            }

            json_vals = json.dumps(vals)
            return  json_vals


    @http.route('/master_create_assessment', type='http' ,auth='public', csrf=False)
    def master_create_assement(self, redirect=None, **kw):

        customer_id = '' # 199802320
        invoice_id = '' # 1

        if 'customer_id' in kw:
            customer_id = kw['customer_id']
            # partner =  http.request.env['res.partner'].sudo().search([('customer_id','=', int(customer_id))])

        if 'invoice_id' in kw:
            invoice_id = kw['invoice_id']
            

        try:
            portal_sync = http.request.env['sync.sms.settings'].sudo().search([], limit=1)
            cust_id = customer_id
            inv_id = invoice_id

            # if not partner: 
            # portal_sync.sync_create_customer_v2(cust_id)
            portal_sync.sync_create_customer_v3(cust_id)
            request.env.cr.commit()

            portal_sync.create_assessment_invoices_by_invoice_id(inv_id)
            request.env.cr.commit()

            portal_sync.create_ajustment_partner_v2(cust_id)
            request.env.cr.commit()

            portal_sync.invoice_sync_back_odoo_v2(inv_id)
            request.env.cr.commit()
            

            vals = {
                'status': 'Fetch Success',
            }

            json_vals = json.dumps(vals)
            return  json_vals
            
        except Exception as e:
            vals = {
                    'status': 'Fetch Failed (No Created Invoice)',
            }

            json_vals = json.dumps(vals)
            return  json_vals
        
    @http.route('/master_create_assessment_v2', type='http' ,auth='public', csrf=False)
    def master_create_assessment_v2(self, redirect=None, **kw):

        customer_id = '' # 199802320
        invoice_id = '' # 1

        if 'customer_id' in kw:
            customer_id = kw['customer_id']
            # partner =  http.request.env['res.partner'].sudo().search([('customer_id','=', int(customer_id))])

        if 'invoice_id' in kw:
            invoice_id = kw['invoice_id']
            

        try:
            portal_sync = http.request.env['sync.sms.settings'].sudo().search([], limit=1)
            cust_id = customer_id
            inv_id = invoice_id

            # if not partner: 
            # portal_sync.sync_create_customer_v2(cust_id)
            portal_sync.sync_create_customer_v3(cust_id)
            request.env.cr.commit()

            portal_sync.create_assessment_invoices_by_invoice_id_v2(inv_id)
            request.env.cr.commit()

            portal_sync.create_ajustment_partner_v2(cust_id)
            request.env.cr.commit()

            portal_sync.invoice_sync_back_odoo_v2(inv_id)
            request.env.cr.commit()
            

            vals = {
                'status': 'Fetch Success',
            }

            json_vals = json.dumps(vals)
            return  json_vals
            
        except Exception as e:
            vals = {
                    'status': 'Fetch Failed (No Created Invoice)',
            }

            json_vals = json.dumps(vals)
            return  json_vals
        
    @http.route('/master_create_application', type='http' ,auth='public', csrf=False)
    def master_create_application(self, redirect=None, **kw):

        customer_id = '' # 202400232188
        invoice_id = '' # 1022

        if 'customer_id' in kw:
            customer_id = kw['customer_id']
            # partner =  http.request.env['res.partner'].sudo().search([('customer_id','=', int(customer_id))])
        
        if 'invoice_id' in kw:
            invoice_id = kw['invoice_id']

            
        try:
            portal_sync = http.request.env['sync.sms.settings'].sudo().search([], limit=1)
            cust_id = portal_sync.customer_id 
            cust_id = customer_id

            inv_id = portal_sync.invoice_id
            inv_id = invoice_id

            # CUSTOMER CREATION 
            # if not partner:
            # portal_sync.sync_create_customer_v2(cust_id)
            portal_sync.sync_create_customer_v3(cust_id)
            request.env.cr.commit()

            portal_sync.create_application_invoices_by_invoice_id(inv_id)
            request.env.cr.commit()

            portal_sync.sync_create_reservation(inv_id)
            request.env.cr.commit()

            portal_sync.invoice_sync_back_odoo_v2(inv_id)
            request.env.cr.commit()

            vals = {
                'status': 'Fetch Success',
            }

            json_vals = json.dumps(vals)
            return  json_vals
            
        except Exception as e:
            vals = {
                    'status': 'Fetch Failed (Check API Connection if ever )',
            }

            json_vals = json.dumps(vals)
            return  json_vals
        
    
    @http.route('/master_create_reservation', type='http' ,auth='public', csrf=False)
    def master_create_reservation(self, redirect=None, **kw):

        customer_id = '' # 202400232188
        invoice_id = '' # 1022

        if 'customer_id' in kw:
            customer_id = kw['customer_id']
        
        if 'invoice_id' in kw:
            invoice_id = kw['invoice_id']

            
        try:
            portal_sync = http.request.env['sync.sms.settings'].sudo().search([], limit=1)
            cust_id = portal_sync.customer_id 
            cust_id = customer_id

            inv_id = portal_sync.invoice_id
            inv_id = invoice_id

            portal_sync.sync_invoice_detail_view_by_invoice_id(inv_id)
            request.env.cr.commit()
            portal_sync.sync_invoice_pay_view_by_invoice_id(inv_id)
            request.env.cr.commit()

            # CUSTOMER CREATION 
            # portal_sync.sync_create_customer_v2(cust_id)
            portal_sync.sync_create_customer_v3(cust_id)
            request.env.cr.commit()

            portal_sync.sync_create_reservation(inv_id)
            request.env.cr.commit()

            portal_sync.invoice_sync_back_odoo_v2(inv_id)
            request.env.cr.commit()


            vals = {
                'status': 'Fetch Success',
            }

            json_vals = json.dumps(vals)
            return  json_vals
            
        except Exception as e:
            vals = {
                    'status': 'Fetch Failed (Check API Connection if ever )',
            }

            json_vals = json.dumps(vals)
            return  json_vals
       

    @http.route('/catch_all', type='http' ,auth='public', csrf=False)
    def catch_all(self, redirect=None, **kw):

        customer_id = '' # 202400232188
        invoice_id = '' # 1022

        if 'customer_id' in kw:
            customer_id = kw['customer_id']
        
        if 'invoice_id' in kw:
            invoice_id = kw['invoice_id']

            
        try:
            portal_sync = http.request.env['sync.sms.settings'].sudo().search([], limit=1)
            cust_id = portal_sync.customer_id 
            cust_id = customer_id

            inv_id = portal_sync.invoice_id
            inv_id = invoice_id

            portal_sync.sync_invoice_detail_view_by_invoice_id(inv_id)
            request.env.cr.commit()
            portal_sync.sync_invoice_pay_view_by_invoice_id(inv_id)
            request.env.cr.commit()

            # CUSTOMER CREATION 
            portal_sync.sync_create_customer_for_portal(cust_id)
            request.env.cr.commit()

            portal_sync.catch_all_invoices_by_invoice_id(inv_id)
            request.env.cr.commit()

            # portal_sync.invoice_sync_back_odoo_v2(inv_id)
            portal_sync.sync_create_customer_v3(cust_id)
            request.env.cr.commit()
            


            vals = {
                'status': 'Fetch Success',
            }

            json_vals = json.dumps(vals)
            return  json_vals
            
        except Exception as e:
            _logger.error('Error in catch_all method: %s', e)
            
            vals = {
                    'status': 'Fetch Failed (Check API Connection if ever )',
            }

            json_vals = json.dumps(vals)
            return  json_vals