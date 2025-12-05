# -*- coding: utf-8 -*-
"""
DLSU SMS Integration - API Controllers

This module provides HTTP API endpoints for external systems to interact
with Odoo data related to SMS synchronization. It includes endpoints for:

- Invoice data retrieval (headers and line items)
- Customer information
- Product information
- Portal user creation from SMS data

All endpoints return JSON-formatted responses and support public authentication
for integration with external systems.
"""

from odoo import http, fields
from odoo.http import request, Response
import werkzeug
from werkzeug import url_encode
from odoo import _, SUPERUSER_ID
from odoo.tools import config
import base64
import requests
import json
import pprint
from datetime import date, timedelta, datetime


class ApiInvoice(http.Controller):
    """
    Controller providing API endpoints for invoice and related data access.
    """

    @http.route(['/api_first_invoice'], type='http', auth='public', csrf=False)
    def api_first_invoice(self, redirect=None, **kw):
        """
        Retrieve all first payment invoices with complete details.

        Returns invoice headers and line items for all invoices marked
        as first payment. Used for initial payment processing.

        Returns:
            JSON response with invoice data including line items
        """

        move_obj = request.env['account.move']

        moves = move_obj.sudo().search([('is_first_payment','=', True)])

        if not moves:
            vals = {
                'status': 'fetch failed',
            }

            json_vals = json.dumps(vals)
            return  json_vals

        def serialize_date(date_obj):
            return date_obj.strftime('%Y-%m-%d') if date_obj else None

        vals = {
            'status': 'fetch success',
            'data': [{
                'id': move.id,
                'partner_id': move.partner_id.id,

                'name': move.name,
                'partner': move.partner_id.name,
                'invoice_type_desc': move.inv_type_desc,
                'invoice_date': serialize_date(move.invoice_date),
                'invoice_date_due': serialize_date(move.invoice_date_due), 
                'course': move.course,
                'year': move.year,
                'school_year': move.school_year,
                'term': move.term,
                'amount_residual': move.amount_residual,
                'amount_total': move.amount_total,
                'move_type': move.move_type,
                'state': move.state,

                'move_lines': [{
                    'invoice_id': line.move_id.id,
                    'product_id': line.product_id.id,
                    'product_name': line.product_id.name,
                    'quantity': line.quantity,
                    'price_unit': line.price_unit,
                } for line in move.invoice_line_ids]

            } for move in moves]
        }
        json_vals = json.dumps(vals)
        return json_vals
    
    @http.route(['/api_invoice'], type='http', auth='public', csrf=False)
    def api_invoice(self, redirect=None, **kw):
        """
        Retrieve all first payment invoice headers.

        Returns invoice header information without line items.
        More lightweight than api_first_invoice.

        Returns:
            JSON response with invoice header data
        """

        move_obj = request.env['account.move']

        moves = move_obj.sudo().search([('is_first_payment','=', True)])

        if not moves:
            vals = {
                'status': 'fetch failed',
            }

            json_vals = json.dumps(vals)
            return  json_vals

        def serialize_date(date_obj):
            return date_obj.strftime('%Y-%m-%d') if date_obj else None

        vals = {
            'status': 'fetch success',
            'data': [{
                'id': move.id,
                'partner_id': move.partner_id.id,

                'name': move.name,
                'partner': move.partner_id.name,
                'invoice_type_desc': move.inv_type_desc,
                'invoice_date': serialize_date(move.invoice_date),
                'invoice_date_due': serialize_date(move.invoice_date_due), 
                'course': move.course,
                'year': move.year,
                'school_year': move.school_year,
                'term': move.term,
                'amount_residual': move.amount_residual,
                'amount_total': move.amount_total,
                'move_type': move.move_type,
                'state': move.state,
            } for move in moves]
        }
        json_vals = json.dumps(vals)
        return json_vals
    
    @http.route(['/api_invoice_line'], type='http', auth='public', csrf=False)
    def api_invoice_line(self, redirect=None, **kw):
        """
        Retrieve invoice line items only.

        Returns line item details for all first payment invoices.

        Returns:
            JSON response with invoice line items grouped by invoice
        """

        move_obj = request.env['account.move']

        moves = move_obj.sudo().search([('is_first_payment','=', True)])

        if not moves:
            vals = {
                'status': 'fetch failed',
            }

            json_vals = json.dumps(vals)
            return  json_vals

        def serialize_date(date_obj):
            return date_obj.strftime('%Y-%m-%d') if date_obj else None

        vals = {
            'status': 'fetch success',
            'data': [{

                'move_lines': [{
                    'invoice_id': line.move_id.id,
                    'product_id': line.product_id.id,
                    'quantity': line.quantity,
                    'price_unit': line.price_unit,
                } for line in move.invoice_line_ids]

            } for move in moves]
        }
        json_vals = json.dumps(vals)
        return json_vals
    
    @http.route(['/api_customer'], type='http', auth='public', csrf=False)
    def api_customer(self, redirect=None, **kw):
        """
        Retrieve customer information from invoices.

        Returns customer data associated with first payment invoices.

        Returns:
            JSON response with customer IDs and names
        """

        move_obj = request.env['account.move']

        moves = move_obj.sudo().search([('is_first_payment','=', True)])

        if not moves:
            vals = {
                'status': 'fetch failed',
            }

            json_vals = json.dumps(vals)
            return  json_vals

        vals = {
            'status': 'fetch success',
            'data': [{
                'id': move.id,
                'partner_id': move.partner_id.id,
                'partner': move.partner_id.name,
            } for move in moves]
        }
        json_vals = json.dumps(vals)
        return json_vals
    
    @http.route(['/api_product'], type='http', auth='public', csrf=False)
    def api_product(self, redirect=None, **kw):
        """
        Retrieve product information from invoice lines.

        Returns unique products used in first payment invoices.

        Returns:
            JSON response with product IDs and names
        """

        move_obj = request.env['account.move']

        moves = move_obj.sudo().search([('is_first_payment','=', True)])

        if not moves:
            vals = {
                'status': 'fetch failed',
            }

            json_vals = json.dumps(vals)
            return  json_vals


        vals = {
            'status': 'fetch success',
            'data': [{
                'id': move.id,

                'move_lines': [{
                    'product_id': line.product_id.id,
                    'product_name': line.product_id.name,
                } for line in move.invoice_line_ids]

            } for move in moves]
        }
        json_vals = json.dumps(vals)
        return json_vals
    

    @http.route('/portal/creation', type='http' ,auth='public', csrf=False)
    def portal_user_creation(self, redirect=None, **kw):
        """
        Create portal user for a customer from SMS data.

        Parameters:
            customer_id: SMS customer ID to create portal user for

        Returns:
            JSON response indicating success or failure
        """
        customer_id = ''

        if 'customer_id' in kw:
            customer_id = kw['customer_id']

        try:
            portal_sync = http.request.env['sync.sms.settings'].sudo().search([], limit=1)
            cust_id = portal_sync.customer_id 
            cust_id = customer_id

            portal_sync.sync_create_customer_for_portal(cust_id)
            request.env.cr.commit()

            vals = {
                # 'status': 'Fetch Success, User Created'
                'status': f'Fetch Success, User Created : "{cust_id if cust_id else None}"'
            }

            json_vals = json.dumps(vals)
            return  json_vals
        
        except Exception as e:
            vals = {
                    'status': 'Fetch Failed (Check API Connection if ever )',
            }
            json_vals = json.dumps(vals)
            return  json_vals

    @http.route(['/master_customer'], type='http', auth='public', csrf=False)
    def master_customer(self, **kw):
        """
        Retrieve customer master data with pagination support.

        Parameters:
            customer_id: (optional) Specific customer ID to retrieve
            page: Page number for pagination (default: 1)
            per_page: Records per page (default: 20)

        Returns:
            JSON response with customer data and pagination info
        """
        customer_id = kw.get('customer_id')
        page = int(kw.get('page', 1))  # Default to page 1
        per_page = int(kw.get('per_page', 20))  # Default to 20 records per page
        offset = (page - 1) * per_page

        partner_obj = request.env['res.partner'].sudo()

        # If customer_id is provided, search for a specific customer
        if customer_id:
            partners = partner_obj.search([('customer_id', '=', customer_id)])
        else:
            partners = partner_obj.search([], offset=offset, limit=per_page)
            total_count = partner_obj.search_count([])  # Get total records count

        if not partners:
            return http.Response(
                json.dumps({'status': 'fetch failed'}),
                content_type='application/json',
                status=404
            )

        vals = {
            'status': 'fetch success',
            'total_count': total_count if not customer_id else 1,  # Only provide total_count if listing all
            'page': page,
            'per_page': per_page,
            'data': [{
                'id': partner.id,
                'name': partner.name,
                'customer_id': partner.customer_id,
                'course': partner.course,
            } for partner in partners]
        }

        return http.Response(json.dumps(vals, indent=4), content_type='application/json')
