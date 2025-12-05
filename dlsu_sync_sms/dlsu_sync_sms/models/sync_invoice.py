# -*- coding: utf-8 -*-
"""
DLSU SMS Integration - Invoice Synchronization Module

This module handles the synchronization of invoice data between the DLSU
Student Management System (SMS) and Odoo. It manages:

- Invoice header information
- Invoice line items and details
- Payment schedules and due dates
- Invoice adjustments and voids
- Customer information linked to invoices

The module creates corresponding account moves in Odoo based on SMS invoices.
"""

from odoo import models, fields, api
import requests
import xml.etree.ElementTree as ET
import xmltodict
import logging
from datetime import datetime, date
import pytz
from odoo.exceptions import except_orm, Warning, RedirectWarning, UserError, ValidationError
import json
import xmlrpc.client

_logger = logging.getLogger(__name__)

class Invoice(models.Model):
    """
    Model representing an invoice synchronized from SMS.

    This model stores comprehensive invoice information including:
    - Header data (invoice number, date, customer)
    - Line item details (products, quantities, amounts)
    - Payment terms and schedules
    - Adjustment and void information
    """
    _name = 'sms.invoice'
    _description = 'SMS Invoice Record'
    _rec_name = 'invoice_ref_no'
    _order = 'invoice_date desc'

    diffgr_id = fields.Char('Diffgr ID')
    row_order = fields.Char('Row Order')

    invoice_id = fields.Char('Invoice ID')
    invoice_date = fields.Datetime('Invoice Date')
    invoice_ref_no = fields.Char('Invoice Ref No.')
    inv_type = fields.Char('Inv Type')
    inv_type_desc = fields.Char('Inv Type Desc')
    customer_type = fields.Char('Customer Type')
    customer_id = fields.Char('Customer ID')
    customer_ref_id = fields.Char('Customer Ref ID')
    customer_name = fields.Char('Customer Name')
    pay_term = fields.Char('Payment Term')
    total_amount = fields.Float('Total Amount')
    adjusted = fields.Boolean('Adjusted')
    void = fields.Boolean('Void')
    l_name = fields.Char('Last Name')
    f_name = fields.Char('First Name')
    m_name = fields.Char('Middle Name')
    suffix = fields.Char('Suffix')
    void_date = fields.Datetime('Void Date')
    void_remarks = fields.Text('Void Remarks')
    invoice_adj_id = fields.Integer('Invoice Adjustment ID')
    invoice_adj_no = fields.Integer('Invoice Adjustment No.')
    adjust_date = fields.Datetime('Adjustment Date')
    total_adj_amount = fields.Float('Total Adjustment Amount')
    adj_remarks = fields.Text('Adjustment Remarks')
    invoice_det_id = fields.Integer('Invoice Detail ID')
    inv_det_adj_id = fields.Integer('Invoice Detail Adjustment ID')
    prod_id = fields.Integer('Product ID')
    prod_code = fields.Char('Product Code')
    prod_desc = fields.Char('Product Description')
    account_code = fields.Char('Account Code')
    unit_price = fields.Float('Unit Price')
    qty = fields.Integer('Quantity')
    amount = fields.Float('Amount')

    invoice_pay_id = fields.Char('Invoice Pay ID')
    invoice_pay_no = fields.Char('Invoice Pay No.')

    amount_due = fields.Float('Amount Due')
    due_date = fields.Datetime('Due Date')
    due_date2 = fields.Datetime('Due Date 2')
    due_date3 = fields.Datetime('Due Date 3')
    due_date4 = fields.Datetime('Due Date 3')
    post_date = fields.Datetime('Post Date')

    due_percent = fields.Integer('Due Percent')
    remarks = fields.Char('Remarks')

    due_percent2 = fields.Integer('Due Percent 2')
    remarks2 = fields.Char('Remarks 2')

    due_percent3 = fields.Integer('Due Percent 3')
    remarks3 = fields.Char('Remarks 3')

    due_percent4 = fields.Integer('Due Percent 4')
    remarks4 = fields.Char('Remarks 4')

    course = fields.Char('Course')
    year_level = fields.Char('Year Level')
    school_year = fields.Char('S.Y.')
    term =  fields.Char('term')
    # Added by jari cruz asof may 12 2024
    is_adjustment_created =  fields.Boolean(string='Is Adjustment Created', default=False)
    is_sync =  fields.Boolean(string='Is Sync', default=False)

    sms_email = fields.Char('SMS Email')

    def action_sync_false(self):
        for rec in self:
            rec.is_sync = False
    
    def action_adjusment_false(self):
        for rec in self:
            rec.is_adjustment_created = False

    def action_trans1(self):
        for rec in self:
            rec.invoice_adj_no = 1


class SyncSMSSettingInvoice(models.Model):
    _inherit = 'sync.sms.settings'

    invoice_id = fields.Integer('Invoice ID')
    customer_id = fields.Char('Customer ID')
    invoice_pay_id = fields.Char('Invoice Pay ID')
    invoice_ref_no = fields.Char('Invoice Ref No.')

    invoice_date_from = fields.Date('Date From')
    invoice_date_to = fields.Date('Date To')

    api_invoice_pay_id = fields.Integer('Invoice Pay ID')
    api_remarks =  fields.Char('Remarks')
    api_paid_amount = fields.Float('Paid Amount')
    api_paid_invoice_id = fields.Many2one('account.move', string='Odoo Invoice', store=True)
    api_user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)

    sms_create_stud_id = fields.Char('Student ID')

    sched_invoice_date_from = fields.Date('Date From')
    sched_invoice_date_to = fields.Date('Date To')

    customer_id_list = fields.Text()

    def adjust_invoice_rounding_errors(self):
        """
        Adjust invoice amounts to fix rounding errors.

        Subtracts 0.01 from invoice totals and adjusts related line items
        to correct penny rounding discrepancies in the accounting system.
        """
        _logger.info('Adjusting invoice rounding errors')
        for rec in self:
            list_of_customer_id = [customers for customers in rec.customer_id_list.split('\n')]
            for customer in list_of_customer_id:
                # SQL queries to execute
                sql_queries = [
                    f"""
                    UPDATE account_move
                    SET 
                        amount_untaxed = amount_untaxed - 0.01,
                        amount_total = amount_total - 0.01,
                        amount_residual = amount_residual - 0.01,
                        amount_untaxed_signed = amount_untaxed_signed - 0.01,
                        amount_total_signed = amount_total_signed - 0.01,
                        amount_total_in_currency_signed = amount_total_in_currency_signed - 0.01,
                        amount_residual_signed = amount_residual_signed - 0.1

                    WHERE id = (
                        SELECT id
                        FROM account_move
                        WHERE invoice_ref_no IN ('{customer}')
                        ORDER BY id DESC
                        LIMIT 1
                    );
                    """,
                    f"""
                    UPDATE account_move_line
                    SET 
                        price_unit = price_unit + 0.01,
                        price_subtotal = price_subtotal + 0.01,
                        price_total = price_total + 0.01,
                        debit = debit - 0.01,
                        balance = balance - 0.01,
                        amount_currency = amount_currency - 0.01
                    WHERE id = (
                        SELECT id 
                        FROM account_move_line
                        WHERE move_id = (
                            SELECT id
                            FROM account_move
                            WHERE invoice_ref_no IN ('{customer}')
                            ORDER BY id DESC
                            LIMIT 1
                        )
                        ORDER BY id DESC
                        LIMIT 1
                    );
                    """,
                    f"""
                    UPDATE account_move_line
                    SET 
                        price_unit = price_unit - 0.01,
                        price_subtotal = price_subtotal - 0.01,
                        price_total = price_total - 0.01,
                        credit = credit - 0.01,
                        balance = balance + 0.01,
                        amount_currency = amount_currency + 0.01
                    WHERE id = (
                        SELECT id 
                        FROM account_move_line
                        WHERE move_id = (
                            SELECT id
                            FROM account_move
                            WHERE invoice_ref_no IN ('{customer}')
                            ORDER BY id DESC
                            LIMIT 1
                        )
                        ORDER BY id ASC
                        LIMIT 1
                    );
                    """
                ]

                # Execute each query
                for query in sql_queries:
                    self.env.cr.execute(query)

                # Commit the transaction to apply changes
                self.env.cr.commit()

            move = self.env['account.move'].search([('invoice_ref_no', '=', customer)], order="id desc", limit=1)
            # Recompute necessary fields
            if move:
                move.line_ids._compute_amount_residual()  # Ensure amounts are recalculated
                move.message_post(body = ('Minus One button was triggered'))
                

    def reverse_rounding_adjustment(self):
        """
        Reverse rounding error adjustments on invoices.

        Adds 0.01 to invoice totals and adjusts related line items
        to reverse previous rounding corrections.
        """
        _logger.info('Reversing rounding error adjustments')
        for rec in self:
            list_of_customer_id = [customers for customers in rec.customer_id_list.split('\n')]
            for customer in list_of_customer_id:
                # SQL queries to execute
                sql_queries = [
                    f"""
                    UPDATE account_move
                    SET 
                        amount_untaxed = amount_untaxed + 0.01,
                        amount_total = amount_total + 0.01,
                        amount_residual = amount_residual + 0.01,
                        amount_untaxed_signed = amount_untaxed_signed + 0.01,
                        amount_total_signed = amount_total_signed + 0.01,
                        amount_total_in_currency_signed = amount_total_in_currency_signed + 0.01,
                        amount_residual_signed = amount_residual_signed + 0.1

                    WHERE id = (
                        SELECT id
                        FROM account_move
                        WHERE invoice_ref_no IN ('{customer}')
                        ORDER BY id DESC
                        LIMIT 1
                    );
                    """,
                    f"""
                    UPDATE account_move_line
                    SET 
                        price_unit = price_unit - 0.01,
                        price_subtotal = price_subtotal - 0.01,
                        price_total = price_total - 0.01,
                        debit = debit + 0.01,
                        balance = balance + 0.01,
                        amount_currency = amount_currency + 0.01
                    WHERE id = (
                        SELECT id 
                        FROM account_move_line
                        WHERE move_id = (
                            SELECT id
                            FROM account_move
                            WHERE invoice_ref_no IN ('{customer}')
                            ORDER BY id DESC
                            LIMIT 1
                        )
                        ORDER BY id DESC
                        LIMIT 1
                    );
                    """,
                    f"""
                    UPDATE account_move_line
                    SET 
                        price_unit = price_unit + 0.01,
                        price_subtotal = price_subtotal + 0.01,
                        price_total = price_total + 0.01,
                        credit = credit + 0.01,
                        balance = balance - 0.01,
                        amount_currency = amount_currency - 0.01
                    WHERE id = (
                        SELECT id 
                        FROM account_move_line
                        WHERE move_id = (
                            SELECT id
                            FROM account_move
                            WHERE invoice_ref_no IN ('{customer}')
                            ORDER BY id DESC
                            LIMIT 1
                        )
                        ORDER BY id ASC
                        LIMIT 1
                    );
                    """
                ]

                # Execute each query
                for query in sql_queries:
                    self.env.cr.execute(query)
                    
                # Commit the transaction to apply changes
                self.env.cr.commit()

            move = self.env['account.move'].search([('invoice_ref_no', '=', customer)], order="id desc", limit=1)
            # Recompute necessary fields
            if move:
                move.line_ids._compute_amount_residual()  # Ensure amounts are recalculated
                move.message_post(body = ('Plus One button was triggered'))
                
        
        
        


    def process_assessment_invoices(self):
        for rec in self:

            list_of_customer_id = [customers for customers in rec.customer_id_list.split('\n')]

            for customer in list_of_customer_id:
                list_of_invoice_id = [invoices for invoices in customer.split(' ')]

                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                try:
                    complete_url = f"{base_url}/master_sync_assessment?invoice_id={list_of_invoice_id[1]}&customer_id={list_of_invoice_id[0]}"
                    _logger.debug('Making request to: %s (master_sync_assessment)', complete_url)

                    payload = {
                        'invoice_id': list_of_invoice_id[1],
                        'customer_id': list_of_invoice_id[0],
                    }
                    response = requests.post(complete_url, data=payload)
                    response.raise_for_status()
                    self.env.cr.commit()
                    _logger.info('Request successful: %s', response.text)

                    complete_url_v2 = f"{base_url}/master_create_assessment_v2?invoice_id={list_of_invoice_id[1]}&customer_id={list_of_invoice_id[0]}"
                    _logger.debug('Making request to: %s (master_create_assessment)', complete_url_v2)

                    payload_v2 = {
                        'invoice_id': list_of_invoice_id[1],
                        'customer_id': list_of_invoice_id[0],
                    }

                    response_v2 = requests.post(complete_url_v2, data=payload_v2)
                    response_v2.raise_for_status()
                    self.env.cr.commit()
                    _logger.info('Request successful: %s', response_v2.text)

                    

                except requests.exceptions.RequestException as e:
                    _logger.error('Request failed: %s', e)

    def create_assessment_invoices(self):
        for rec in self:

            list_of_customer_id = [customers for customers in rec.customer_id_list.split('\n')]

            for customer in list_of_customer_id:
                list_of_invoice_id = [invoices for invoices in customer.split(' ')]

                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                try:

                    complete_url_v2 = f"{base_url}/master_create_assessment_v2?invoice_id={list_of_invoice_id[1]}&customer_id={list_of_invoice_id[0]}"

                    payload_v2 = {
                        'invoice_id': list_of_invoice_id[1],
                        'customer_id': list_of_invoice_id[0],
                    }

                    response_v2 = requests.post(complete_url_v2, data=payload_v2)
                    response_v2.raise_for_status()
                    self.env.cr.commit()

                    

                except requests.exceptions.RequestException as e:
                    _logger.error('Request failed: %s', e)


    def repost_assessment_invoices(self):
        for rec in self:

            list_of_customer_id = [customers for customers in rec.customer_id_list.split('\n')]

            for customer in list_of_customer_id:
                sms_partner = self.env['res.partner'].search([('customer_id','=',int(customer))])

                partner_query = """
                SELECT
                    customer_id,
                    invoice_id,
                    invoice_ref_no

                    FROM
                    sms_invoice

                    WHERE inv_type_desc = 'ENROLLMENT ASSESSMENT'
                    and customer_id = '%s'

                    GROUP BY
                    customer_id,
                    invoice_id,
                    invoice_ref_no
                
                """%(sms_partner.customer_id)
                self._cr.execute(partner_query)
                result = self._cr.fetchall()

                for data in result:

                    invoices = self.env['account.move'].search([('invoice_ref_no','=',data[2])])
                    invoices.cancel_all()
                    self.env.cr.commit()
                
                sms_partner.resync_customer_invoice()
                self.env.cr.commit()

    
    def process_admission_invoices(self):
        for rec in self:
            list_of_customer_id = [customers for customers in rec.customer_id_list.split('\n')]

            for customer in list_of_customer_id:
                list_of_invoice_id = [invoices for invoices in customer.split(' ')]

                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                try:
                    complete_url = f"{base_url}/master_sync_application?invoice_id={list_of_invoice_id[1]}&customer_id={list_of_invoice_id[0]}"

                    payload = {
                        'invoice_id': list_of_invoice_id[1],
                        'customer_id': list_of_invoice_id[0],
                    }

                    response = requests.post(complete_url, data=payload)
                    response.raise_for_status()
                    self.env.cr.commit()


                except requests.exceptions.RequestException as e:
                    _logger.error('Request failed: %s', e)

        
    def process_other_invoices(self):
        for rec in self:
            list_of_customer_id = [customers for customers in rec.customer_id_list.split('\n')]

            for customer in list_of_customer_id:
                list_of_invoice_id = [invoices for invoices in customer.split(' ')]

                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                try:
                    complete_url = f"{base_url}/catch_all?invoice_id={list_of_invoice_id[1]}&customer_id={list_of_invoice_id[0]}"

                    payload = {
                        'invoice_id': list_of_invoice_id[1],
                        'customer_id': list_of_invoice_id[0],
                    }

                    'Running_catch_all')
                    response = requests.post(complete_url, data=payload)
                    response.raise_for_status()
                    self.env.cr.commit()

                    complete_url_v2 = f"{base_url}/catch_all?invoice_id={list_of_invoice_id[1]}&customer_id={list_of_invoice_id[0]}"
                    complete_url_v2, 'master_catch_all')

                    payload_v2 = {
                        'invoice_id': list_of_invoice_id[1],
                        'customer_id': list_of_invoice_id[0],
                    }

                    response_v2 = requests.post(complete_url_v2, data=payload_v2)
                    response_v2.raise_for_status()
                    self.env.cr.commit()

                except requests.exceptions.RequestException as e:
                    _logger.error('Request failed: %s', e)


    def cron_scheduled_invoice_sync(self):
        scheduled_invoice_sms = self.env['sync.sms.settings'].search([],limit=1)
        scheduled_invoice_sms.scheduled_invoice_sync_v3()
        self.env.cr.commit()


    def scheduled_invoice_sync(self):
        for rec in self:
            'scheduled_invoice_sync')

            if not rec.sched_invoice_date_from and not rec.sched_invoice_date_to:
                rec.invoice_date_from = datetime.now().strftime('%Y-%m-%d')
                rec.invoice_date_to = datetime.now().strftime('%Y-%m-%d')
                'if')
            else:
                rec.invoice_date_from = rec.sched_invoice_date_from.strftime('%Y-%m-%d')
                rec.invoice_date_to = rec.sched_invoice_date_to.strftime('%Y-%m-%d')
                'else')

            rec.sync_invoice_detail_view_by_date_created()
            rec.sync_invoice_pay_view_by_date_created()
            self.env.cr.commit()

    def scheduled_invoice_sync_v2(self):
        for rec in self:

            if not rec.sched_invoice_date_from and not rec.sched_invoice_date_to:
                rec.invoice_date_from = datetime.now().strftime('%Y-%m-%d')
                rec.invoice_date_to = datetime.now().strftime('%Y-%m-%d')
                'ifv2')
            else:
                rec.invoice_date_from = rec.sched_invoice_date_from.strftime('%Y-%m-%d')
                rec.invoice_date_to = rec.sched_invoice_date_to.strftime('%Y-%m-%d')
                'elsev2')

            sms_invoice = rec.env['sms.invoice'].search([
                ('create_date', '>=',  rec.invoice_date_from),
                ('create_date', '<=',  rec.invoice_date_to),
                ('is_sync', '!=', True)
            ]).mapped('invoice_id')
            invoices = list(set(sms_invoice))

            sms_customer = rec.env['sms.invoice'].search([
                ('create_date', '>=',  rec.invoice_date_from),
                ('create_date', '<=',  rec.invoice_date_to),
                ('is_sync', '!=', True)
            ]).mapped('customer_id')
            customers = list(set(sms_customer))

            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

            try:
                for invoice_id, customer_id in zip(invoices, customers):
                    complete_url = f"{base_url}/master_sync_assessment?invoice_id={invoice_id}&customer_id={customer_id}"
                    complete_url, 'complete_url')

                    data = {
                        'invoice_id': invoice_id,
                        'customer_id': customer_id,
                    }

                    # Make the HTTP request
                    'Running')
                    response = requests.post(complete_url, data=data) 
                    response.raise_for_status() 

                    sms_sync = rec.env['sms.invoice'].search([
                    ('invoice_id', '>=',  invoice_id),
                    ('customer_id', '<=',  customer_id)])
                    if invoice_id  and customer_id:
                        sms_sync.is_sync = True

                    self.env.cr.commit()

            except requests.exceptions.RequestException as e:
                _logger.error('Request failed: %s', e)


    def scheduled_invoice_sync_v3(self):
        for rec in self:

            if not rec.sched_invoice_date_from and not rec.sched_invoice_date_to:
                rec.sched_invoice_date_from = datetime.now().strftime('%Y-%m-%d')
                rec.sched_invoice_date_to = datetime.now().strftime('%Y-%m-%d')
                'ifv3')
            else:
                rec.sched_invoice_date_from = rec.sched_invoice_date_from.strftime('%Y-%m-%d')
                rec.sched_invoice_date_to = rec.sched_invoice_date_to.strftime('%Y-%m-%d')
                'elsev3')

            query = """ 
                SELECT
                customer_id,
                invoice_id,
                invoice_ref_no

                FROM sms_invoice

                WHERE inv_type_desc = 'ENROLLMENT ASSESSMENT'
                AND create_date BETWEEN (timestamp '%s 00:00:00' - interval '8 hours') AND (timestamp '%s 23:59:59' + interval '8 hours')
                AND is_sync = FALSE

                GROUP BY
                customer_id,
                invoice_id,
                invoice_ref_no;

            """%(rec.sched_invoice_date_from, rec.sched_invoice_date_to)
            self._cr.execute(query)
            result = self._cr.fetchall()

            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            try:
                for data in result:
                    if len(data) != 3:
                        "Unexpected data length:", len(data), "data:", data)
                        continue

                    customer_id, invoice_id, invoice_ref_no = data
                    complete_url = f"{base_url}/master_sync_assessment?invoice_id={invoice_id}&customer_id={customer_id}"
                    complete_url, 'complete_urlv2')

                    payload = {
                        'invoice_id': invoice_id,
                        'customer_id': customer_id,
                    }

                    'Running')
                    response = requests.post(complete_url, data=payload)
                    response.raise_for_status()

                    self.env.cr.commit()

            except requests.exceptions.RequestException as e:
                _logger.error('Request failed: %s', e)
 

    def sync_all_by_customer_id(self):
        for rec in self:
            rec.sync_invoice_detail_view_by_customer_id()
            rec.sync_invoice_pay_view_by_customer_id()
            self.env.cr.commit()
            
        
    def sync_all_by_invoice_id(self):
        for rec in self:
            rec.sync_invoice_detail_view_by_invoice_id()
            rec.sync_invoice_pay_view_by_invoice_id()
            self.env.cr.commit()
    
    def sync_all_by_invoice_created(self):
        for rec in self:
            rec.sync_invoice_detail_view_by_date_created()
            rec.sync_invoice_pay_view_by_date_created()
            self.env.cr.commit()

    def sync_invoice_detail_view_by_date_created(self):
        'sync_invoice_detail_view_by_date_created')
        for rec in self:

            soap = """
                POST /odoows/invoice.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/InvoiceDetailViewByDateCreated"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <InvoiceDetailViewByDateCreated xmlns="http://FMS.dlsud.edu.ph/">
                    <_datecreatedfrom>dateTime</_datecreatedfrom>
                    <_datecreatedto>dateTime</_datecreatedto>
                    </InvoiceDetailViewByDateCreated>
                </soap:Body>
                </soap:Envelope>
            """

            url = f"http://{rec.host}/fms/odoosync/invoice.asmx"

            datecreatedfrom = rec.invoice_date_from.strftime('%Y-%m-%d')
            datecreatedto = rec.invoice_date_to.strftime('%Y-%m-%d')

            rec.invoice_date_to, rec.invoice_date_from, 'invoice_date_to_from')

            payload = f"""
            <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <InvoiceDetailViewByDateCreated xmlns="http://FMS.dlsud.edu.ph/">
                <_datecreatedfrom>{datecreatedfrom}</_datecreatedfrom>
                <_datecreatedto>{datecreatedto}</_datecreatedto>
                </InvoiceDetailViewByDateCreated>
            </soap:Body>
            </soap:Envelope>
            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/InvoiceDetailViewByDateCreated"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')

            # Convert XML content to dictionary
            response_dict = xmltodict.parse(xml_content)
            response_dict)

            # Access the 'DT' element within 'DocumentElement'
            diffgram = response_dict['soap:Envelope']['soap:Body']['InvoiceDetailViewByDateCreatedResponse']['InvoiceDetailViewByDateCreatedResult']['diffgr:diffgram']
            dt_element = diffgram.get('DocumentElement')
            dt_value = []

            if dt_element:
                dt_value = dt_element.get('DT')
            else:
                pass
            
            # Check if 'DT' is a list, if not, convert it to a list
            if not isinstance(dt_value, list):
                dt_value = [dt_value]

            if len(dt_value) > 0:
                for dt in dt_value:
                    invoice = {
                        'diffgr_id': dt['@diffgr:id'],
                        'row_order': dt['@msdata:rowOrder'],

                        'invoice_id': dt['InvoiceID'],
                        'invoice_pay_id': dt['invoicepayid']if 'invoicepayid' in dt else None,
                        'invoice_adj_id': dt['invoiceadjid'] if 'invoiceadjid' in dt else None,
                        'invoice_det_id': dt['invoicedetid'] if 'invoicedetid' in dt else None,
                        'inv_det_adj_id': dt['invdetadjid'] if 'invdetadjid' in dt else None,

                        'customer_id': dt['CustomerID'] if 'CustomerID' in dt else None,
                        'customer_ref_id': dt['CustomerRefID']if 'CustomerRefID' in dt else None,
                        'prod_id': dt['prodid'] if 'prodid' in dt else None,

                        'customer_type': dt['CustomerType'] if 'CustomerType' in dt else None,
                        'customer_name': dt['CustomerName'] if 'CustomerName' in dt else None,
                        'l_name': dt['LName']if 'LName' in dt else None,
                        'f_name': dt['FName']if 'FName' in dt else None,
                        'm_name': dt['Mname']if 'Mname' in dt else None,
                        'suffix': dt['Suffix']if 'Suffix' in dt else None,

                        'invoice_date': self.convert_date_format(dt.get('InvoiceDate', None)),
                        'invoice_pay_no': dt['invoicepayno']if 'invoicepayno' in dt else None,
                        'invoice_ref_no': dt['InvoiceRefNo'] if 'InvoiceRefNo' in dt else None,
                        'inv_type': dt['InvType'] if 'InvType' in dt else None,
                        'inv_type_desc': dt['InvTypeDesc'] if 'InvTypeDesc' in dt else None,
                        'pay_term': dt['PayTerm'] if 'PayTerm' in dt else None,

                        'course': dt['progcode'] if 'progcode' in dt else None,
                        'year_level': dt['yrlvl'] if 'yrlvl' in dt else None,
                        'school_year': dt['sy'] if 'sy' in dt else None,
                        'term': dt['term'] if 'term' in dt else None,

                        # DUE PERCENT

                        'amount_due': dt['amountdue']if 'amountdue' in dt else None,
                        'qty': int(dt['qty']) if 'qty' in dt else None,
                        'unit_price': float(dt['unitprice']) if 'unitprice' in dt else None,
                        'amount': float(dt['amount']) if 'amount' in dt else None,
                        'total_amount': float(dt['TotalAmount']) if 'TotalAmount' in dt else None,

                        'account_code': dt['accountcode'] if 'accountcode' in dt else None,
                        'prod_code': dt['prodcode'] if 'prodcode' in dt else None,
                        'prod_desc': dt['proddesc'] if 'proddesc' in dt else None,

                        'adjusted': dt['Adjusted'].lower() == 'true',
                        'void': dt['Void'].lower() == 'true',
                        'void_date': self.convert_date_format(dt.get('voiddate', None)) if 'voiddate' in dt else None,
                        'void_remarks': dt['voidremarks'] if 'voidremarks' in dt else None,

                        'invoice_adj_no': dt['invoiceadjno'] if 'invoiceadjno' in dt else None,
                        'adjust_date': self.convert_date_format(dt.get('adjustdate', None)) if 'adjustdate' in dt else None,
                        'total_adj_amount': float(dt['totaladjamount']) if 'totaladjamount' in dt else None,
                        'adj_remarks': dt['adjremarks'] if 'adjremarks' in dt else None,
                        
                    }

                    exist = self.env['sms.invoice'].search([('invoice_id', '=', invoice['invoice_id']), ('invoice_det_id', '=', invoice['invoice_det_id'])])
                    exist1 = self.env['sms.invoice'].search([('invoice_id', '=', invoice['invoice_id']), ('inv_det_adj_id', '=', invoice['inv_det_adj_id'])])
                    if not exist and not exist1:
                        self.env['sms.invoice'].create(invoice)
                        self.env.cr.commit()
                    else:
                        break

    def sync_invoice_pay_view_by_date_created(self):
        for rec in self:

            soap = """
                POST /odoows/invoice.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/InvoicePayViewByDateCreated"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <InvoicePayViewByDateCreated xmlns="http://FMS.dlsud.edu.ph/">
                    <_datecreatedfrom>dateTime</_datecreatedfrom>
                    <_datecreatedto>dateTime</_datecreatedto>
                    </InvoicePayViewByDateCreated>
                </soap:Body>
                </soap:Envelope>
            """

            url = f"http://{rec.host}/fms/odoosync/invoice.asmx"


            datecreatedfrom = rec.invoice_date_from.strftime('%Y-%m-%d')
            datecreatedto = rec.invoice_date_to.strftime('%Y-%m-%d')

            payload = f"""
            <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <InvoicePayViewByDateCreated xmlns="http://FMS.dlsud.edu.ph/">
                <_datecreatedfrom>{datecreatedfrom}</_datecreatedfrom>
                <_datecreatedto>{datecreatedto}</_datecreatedto>
                </InvoicePayViewByDateCreated>
            </soap:Body>
            </soap:Envelope>
            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/InvoicePayViewByDateCreated"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')

            # Convert XML content to dictionary
            response_dict = xmltodict.parse(xml_content)
            response_dict)

            dt_element = response_dict['soap:Envelope']['soap:Body']['InvoicePayViewByDateCreatedResponse']['InvoicePayViewByDateCreatedResult']['diffgr:diffgram']['DocumentElement']['DT']

            # Check if 'DT' is a list, if not, convert it to a list
            if not isinstance(dt_element, list):
                dt_element = [dt_element]

            new_dt = dt_element[0]
            duepercent = {}
            remarks = {}
            invoice_id = {}
            due_date = {}

            default_value_for_missing_key = None

            if len(dt_element) > 0:
                for index, dt in enumerate(dt_element):

                    duepercent[index] = dt.get('duepercent', default_value_for_missing_key)
                    remarks[index] = dt.get('remarks', default_value_for_missing_key)
                    invoice_id[index] = dt.get('invoicepayid', default_value_for_missing_key)
                    due_date[index] = dt.get('duedate', default_value_for_missing_key)
                
                new_dt['duepercent'] = duepercent
                new_dt['remarks'] = remarks
                new_dt['invoicepayid'] = invoice_id
                new_dt['duedate'] = due_date
                dts = new_dt
                invoice_pay_id = '({},{},{})'

                # due_date_converted = self.convert_date_format(dts['duedate']) if 'duedate' in dts else None

                # dd = dts['duedate'].get(0)
                # date_due = self.convert_date_format(dd)

                # dd2 = dts['duedate'].get(1)
                # date_due2 = self.convert_date_format(dd2)

                # dd3 = dts['duedate'].get(2)
                # date_due3 = self.convert_date_format(dd3)

                # invoice = {
                #     'diffgr_id': dt['@diffgr:id'],
                #     'row_order': dt['@msdata:rowOrder'],

                #     'invoice_id': dt['InvoiceID'],
                #     'invoice_pay_id': invoice_pay_id.format(dts['invoicepayid'].get(0) if 'invoicepayid' in dts else None,dts['invoicepayid'].get(1) if 'invoicepayid' in dts else None,dts['invoicepayid'].get(2) if 'invoicepayid' in dts else None),

                #     'due_percent': dts['duepercent'].get(0) if 'duepercent' in dts else None,
                #     'due_percent2': dts['duepercent'].get(1) if 'duepercent' in dts else None,
                #     'due_percent3': dts['duepercent'].get(2) if 'duepercent' in dts else None,
                #     'remarks': dts['remarks'].get(0) if 'remarks' in dts else None,
                #     'remarks2': dts['remarks'].get(1) if 'remarks' in dts else None,
                #     'remarks3': dts['remarks'].get(2) if 'remarks' in dts else None,
                #     'due_date': date_due if date_due else None,
                #     'due_date2': date_due2 if date_due2 else None,
                #     'due_date3': date_due3 if date_due3 else None,

                #     'post_date': self.convert_date_format(dt.get('postdate', None)),   
                # }

                dd = dts['duedate'].get(0)
                date_due = self.convert_date_format(dd)

                dd2 = dts['duedate'].get(1)
                date_due2 = self.convert_date_format(dd2)

                dd3 = dts['duedate'].get(2)
                date_due3 = self.convert_date_format(dd3)

                dd4 = dts['duedate'].get(3)
                date_due4 = self.convert_date_format(dd4)

                invoice = {
                    'diffgr_id': dt['@diffgr:id'],
                    'row_order': dt['@msdata:rowOrder'],

                    'invoice_id': dt['InvoiceID'],
                    'invoice_pay_id': invoice_pay_id.format(dts['invoicepayid'].get(0) if 'invoicepayid' in dts else None,dts['invoicepayid'].get(1) if 'invoicepayid' in dts else None,dts['invoicepayid'].get(2) if 'invoicepayid' in dts else None,dts['invoicepayid'].get(3) if 'invoicepayid' in dts else None),

                    'due_percent': dts['duepercent'].get(0) if 'duepercent' in dts else None,
                    'due_percent2': dts['duepercent'].get(1) if 'duepercent' in dts else None,
                    'due_percent3': dts['duepercent'].get(2) if 'duepercent' in dts else None,
                    'due_percent4': dts['duepercent'].get(3) if 'duepercent' in dts else None,
                    'remarks': dts['remarks'].get(0) if 'remarks' in dts else None,
                    'remarks2': dts['remarks'].get(1) if 'remarks' in dts else None,
                    'remarks3': dts['remarks'].get(2) if 'remarks' in dts else None,
                    'remarks4': dts['remarks'].get(3) if 'remarks' in dts else None,
                    'due_date': date_due if date_due else None,
                    'due_date2': date_due2 if date_due2 else None,
                    'due_date3': date_due3 if date_due3 else None,
                    'due_date4': date_due4 if date_due4 else None,

                    'post_date': self.convert_date_format(dt.get('postdate', None)),   
                }


                exist = self.env['sms.invoice'].search([('invoice_id', '=', invoice['invoice_id'])])
                if not exist:
                    self.env['sms.invoice'].create(invoice)
                    self.env.cr.commit()
                else:
                    break
                
    def sync_invoice_detail_view_by_customer_id(self, cust_id=None):

        for rec in self:
            soap = """  
                POST /odoows/invoice.asmx HTTP/1.1
                Host: 127.0.0.1 
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/InvoiceDetailViewByCustomerID"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <InvoiceDetailViewByCustomerID xmlns="http://FMS.dlsud.edu.ph/">
                    <_customerid>string</_customerid>
                    </InvoiceDetailViewByCustomerID>
                </soap:Body>
                </soap:Envelope>
            """

            url = f"http://{rec.host}/fms/odoosync/invoice.asmx"

            payload = f"""
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <InvoiceDetailViewByCustomerID xmlns="http://FMS.dlsud.edu.ph/">
                    <_customerid>{cust_id if cust_id else rec.customer_id}</_customerid>
                    </InvoiceDetailViewByCustomerID>
                </soap:Body>
                </soap:Envelope>

            """
            payload)

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/InvoiceDetailViewByCustomerID"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            # Convert XML content to dictionary
            response_dict = xmltodict.parse(xml_content)
            xml_content)
            
            diffgram = response_dict['soap:Envelope']['soap:Body']['InvoiceDetailViewByCustomerIDResponse']['InvoiceDetailViewByCustomerIDResult']['diffgr:diffgram']
            dt_element = diffgram.get('DocumentElement')
            dt_value = []

            if dt_element:
                dt_value = dt_element.get('DT')
            else:
                pass
        

            # Check if 'DT' is a list, if not, convert it to a list
            if not isinstance(dt_value, list):
                dt_value = [dt_value]

            if len(dt_value) > 0:
                for dt in dt_value:
                    invoice = {
                        'diffgr_id': dt['@diffgr:id'],
                        'row_order': dt['@msdata:rowOrder'],

                        'invoice_id': dt['InvoiceID'],
                        'invoice_pay_id': dt['invoicepayid']if 'invoicepayid' in dt else None,
                        'invoice_adj_id': dt['invoiceadjid'] if 'invoiceadjid' in dt else None,
                        'invoice_det_id': dt['invoicedetid'] if 'invoicedetid' in dt else None,
                        'inv_det_adj_id': dt['invdetadjid'] if 'invdetadjid' in dt else None,

                        'customer_id': dt['CustomerID'] if 'CustomerID' in dt else None,
                        'customer_ref_id': dt['CustomerRefID']if 'CustomerRefID' in dt else None,
                        'prod_id': dt['prodid'] if 'prodid' in dt else None,

                        'customer_type': dt['CustomerType'] if 'CustomerType' in dt else None,
                        'customer_name': dt['CustomerName'] if 'CustomerName' in dt else None,
                        'l_name': dt['LName']if 'LName' in dt else None,
                        'f_name': dt['FName']if 'FName' in dt else None,
                        'm_name': dt['Mname']if 'Mname' in dt else None,
                        'suffix': dt['Suffix']if 'Suffix' in dt else None,

                        'invoice_date': self.convert_date_format(dt.get('InvoiceDate', None)),
                        'invoice_pay_no': dt['invoicepayno']if 'invoicepayno' in dt else None,
                        'invoice_ref_no': dt['InvoiceRefNo'] if 'InvoiceRefNo' in dt else None,
                        'inv_type': dt['InvType'] if 'InvType' in dt else None,
                        'inv_type_desc': dt['InvTypeDesc'] if 'InvTypeDesc' in dt else None,
                        'pay_term': dt['PayTerm'] if 'PayTerm' in dt else None,

                        'course': dt['progcode'] if 'progcode' in dt else None,
                        'year_level': dt['yrlvl'] if 'yrlvl' in dt else None,
                        'school_year': dt['sy'] if 'sy' in dt else None,
                        'term': dt['term'] if 'term' in dt else None,

                        # DUE PERCENT

                        'amount_due': dt['amountdue']if 'amountdue' in dt else None,
                        'qty': int(dt['qty']) if 'qty' in dt else None,
                        'unit_price': float(dt['unitprice']) if 'unitprice' in dt else None,
                        'amount': float(dt['amount']) if 'amount' in dt else None,
                        'total_amount': float(dt['TotalAmount']) if 'TotalAmount' in dt else None,

                        'account_code': dt['accountcode'] if 'accountcode' in dt else None,
                        'prod_code': dt['prodcode'] if 'prodcode' in dt else None,
                        'prod_desc': dt['proddesc'] if 'proddesc' in dt else None,

                        'adjusted': dt['Adjusted'].lower() == 'true',
                        'void': dt['Void'].lower() == 'true',
                        'void_date': self.convert_date_format(dt.get('voiddate', None)) if 'voiddate' in dt else None,
                        'void_remarks': dt['voidremarks'] if 'voidremarks' in dt else None,

                        'invoice_adj_no': dt['invoiceadjno'] if 'invoiceadjno' in dt else None,
                        'adjust_date': self.convert_date_format(dt.get('adjustdate', None)) if 'adjustdate' in dt else None,
                        'total_adj_amount': float(dt['totaladjamount']) if 'totaladjamount' in dt else None,
                        'adj_remarks': dt['adjremarks'] if 'adjremarks' in dt else None,
                        
                    }

                    exist = self.env['sms.invoice'].search([('invoice_id', '=', invoice['invoice_id']), ('invoice_det_id', '=', invoice['invoice_det_id'])])
                    exist1 = self.env['sms.invoice'].search([('invoice_id', '=', invoice['invoice_id']), ('inv_det_adj_id', '=', invoice['inv_det_adj_id'])])
                    if not exist and not exist1:
                        self.env['sms.invoice'].create(invoice)
                        self.env.cr.commit()
                    else:
                        break


                    # sms_customer = self.env['sms.invoice'].search([('customer_id', '=', invoice['invoice_det_id'])])

    def sync_invoice_detail_view_by_invoice_id(self, inv_id=None):

        for rec in self:

            soap = """
                POST /odoows/invoice.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: application/soap+xml; charset=utf-8
                Content-Length: length

                <?xml version="1.0" encoding="utf-8"?>
                <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                <soap12:Body>
                    <InvoiceDetailViewByInvoiceID xmlns="http://FMS.dlsud.edu.ph/">
                    <_invoiceid>int</_invoiceid>
                    </InvoiceDetailViewByInvoiceID>
                </soap12:Body>
                </soap12:Envelope>
            """

            url = f"http://{rec.host}/fms/odoosync/invoice.asmx"

            payload = f"""
                <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                    <soap12:Body>
                        <InvoiceDetailViewByInvoiceID xmlns="http://FMS.dlsud.edu.ph/">
                        <_invoiceid>{inv_id if inv_id else rec.invoice_id}</_invoiceid>
                        </InvoiceDetailViewByInvoiceID>
                    </soap12:Body>
                </soap12:Envelope>
            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/InvoiceDetailViewByInvoiceID"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            # Convert XML content to dictionary
            response_dict = xmltodict.parse(xml_content)
            response_dict)

            dt_element = response_dict['soap:Envelope']['soap:Body']['InvoiceDetailViewByInvoiceIDResponse']['InvoiceDetailViewByInvoiceIDResult']['diffgr:diffgram']['DocumentElement']['DT']

            # Check if 'DT' is a list, if not, convert it to a list
            if not isinstance(dt_element, list):
                dt_element = [dt_element]

            if len(dt_element) > 0:
                for dt in dt_element:
                    invoice = {
                        'diffgr_id': dt['@diffgr:id'],
                        'row_order': dt['@msdata:rowOrder'],

                        'invoice_id': dt['InvoiceID'],
                        'invoice_pay_id': dt['invoicepayid']if 'invoicepayid' in dt else None,
                        'invoice_adj_id': dt['invoiceadjid'] if 'invoiceadjid' in dt else None,
                        'invoice_det_id': dt['invoicedetid'] if 'invoicedetid' in dt else None,
                        'inv_det_adj_id': dt['invdetadjid'] if 'invdetadjid' in dt else None,

                        'customer_id': dt['CustomerID'] if 'CustomerID' in dt else None,
                        'customer_ref_id': dt['CustomerRefID']if 'CustomerRefID' in dt else None,
                        'prod_id': dt['prodid'] if 'prodid' in dt else None,

                        'customer_type': dt['CustomerType'] if 'CustomerType' in dt else None,
                        'customer_name': dt['CustomerName'] if 'CustomerName' in dt else None,
                        'l_name': dt['LName']if 'LName' in dt else None,
                        'f_name': dt['FName']if 'FName' in dt else None,
                        'm_name': dt['Mname']if 'Mname' in dt else None,
                        'suffix': dt['Suffix']if 'Suffix' in dt else None,

                        'invoice_date': self.convert_date_format(dt.get('InvoiceDate', None)),
                        'invoice_pay_no': dt['invoicepayno']if 'invoicepayno' in dt else None,
                        'invoice_ref_no': dt['InvoiceRefNo'] if 'InvoiceRefNo' in dt else None,
                        'inv_type': dt['InvType'] if 'InvType' in dt else None,
                        'inv_type_desc': dt['InvTypeDesc'] if 'InvTypeDesc' in dt else None,
                        'pay_term': dt['PayTerm'] if 'PayTerm' in dt else None,

                        'course': dt['progcode'] if 'progcode' in dt else None,
                        'year_level': dt['yrlvl'] if 'yrlvl' in dt else None,
                        'school_year': dt['sy'] if 'sy' in dt else None,
                        'term': dt['term'] if 'term' in dt else None,

                        # DUE PERCENT

                        'amount_due': dt['amountdue']if 'amountdue' in dt else None,
                        'qty': int(dt['qty']) if 'qty' in dt else None,
                        'unit_price': float(dt['unitprice']) if 'unitprice' in dt else None,
                        'amount': float(dt['amount']) if 'amount' in dt else None,
                        'total_amount': float(dt['TotalAmount']) if 'TotalAmount' in dt else None,

                        'account_code': dt['accountcode'] if 'accountcode' in dt else None,
                        'prod_code': dt['prodcode'] if 'prodcode' in dt else None,
                        'prod_desc': dt['proddesc'] if 'proddesc' in dt else None,

                        'adjusted': dt['Adjusted'].lower() == 'true',
                        'void': dt['Void'].lower() == 'true',
                        'void_date': self.convert_date_format(dt.get('voiddate', None)) if 'voiddate' in dt else None,
                        'void_remarks': dt['voidremarks'] if 'voidremarks' in dt else None,

                        'invoice_adj_no': dt['invoiceadjno'] if 'invoiceadjno' in dt else None,
                        'adjust_date': self.convert_date_format(dt.get('adjustdate', None)) if 'adjustdate' in dt else None,
                        'total_adj_amount': float(dt['totaladjamount']) if 'totaladjamount' in dt else None,
                        'adj_remarks': dt['adjremarks'] if 'adjremarks' in dt else None,

                        'sms_email': dt['Email'] if 'Email' in dt else None,
                        
                    }

                    exist = self.env['sms.invoice'].search([('invoice_id', '=', invoice['invoice_id']), ('invoice_det_id', '=', invoice['invoice_det_id'])])
                    exist1 = self.env['sms.invoice'].search([('invoice_id', '=', invoice['invoice_id']), ('inv_det_adj_id', '=', invoice['inv_det_adj_id'])])
                    if not exist and not exist1:
                        self.env['sms.invoice'].create(invoice)
                        self.env.cr.commit()
                    else:
                        exist.write(invoice)
                        self.env.cr.commit()
                        
                        exist1.write(invoice)
                        self.env.cr.commit()

    def sync_invoice_pay_view_by_customer_id(self, cust_id=None):

        for rec in self:

            soap = """
                POST /odoows/invoice.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/InvoicePayViewByCustomerID"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <InvoicePayViewByCustomerID xmlns="http://FMS.dlsud.edu.ph/">
                    <_customerid>string</_customerid>
                    </InvoicePayViewByCustomerID>
                </soap:Body>
                </soap:Envelope>
            """

            url = f"http://{rec.host}/fms/odoosync/invoice.asmx"

            payload = f"""
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <InvoicePayViewByCustomerID xmlns="http://FMS.dlsud.edu.ph/">
                    <_customerid>{cust_id if cust_id else rec.customer_id}</_customerid>
                    </InvoicePayViewByCustomerID>
                </soap:Body>
                </soap:Envelope>
            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/InvoicePayViewByCustomerID"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            # Convert XML content to dictionary
            response_dict = xmltodict.parse(xml_content)
            response_dict)

            dt_element = response_dict['soap:Envelope']['soap:Body']['InvoicePayViewByCustomerIDResponse']['InvoicePayViewByCustomerIDResult']['diffgr:diffgram']['DocumentElement']['DT']

            # Check if 'DT' is a list, if not, convert it to a list
            if not isinstance(dt_element, list):
                dt_element = [dt_element]

            new_dt = dt_element[0]
            duepercent = {}
            remarks = {}
            invoice_id = {}
            due_date = {}

            if len(dt_element) > 0:
                for index, dt in enumerate(dt_element):
                    duepercent[index] = dt['duepercent']
                    remarks[index] = dt['remarks']
                    invoice_id[index] = dt['invoicepayid']
                    due_date[index] = dt['duedate']
                
                new_dt['duepercent'] = duepercent
                new_dt['remarks'] = remarks
                new_dt['invoicepayid'] = invoice_id
                new_dt['duedate'] = due_date
                dts = new_dt
                invoice_pay_id = '({},{},{},{})'

                # due_date_converted = self.convert_date_format(dts['duedate']) if 'duedate' in dts else None

                dd = dts['duedate'].get(0)
                date_due = self.convert_date_format(dd)

                dd2 = dts['duedate'].get(1)
                date_due2 = self.convert_date_format(dd2)

                dd3 = dts['duedate'].get(2)
                date_due3 = self.convert_date_format(dd3)

                dd4 = dts['duedate'].get(3)
                date_due4 = self.convert_date_format(dd4)

                invoice = {
                    'diffgr_id': dt['@diffgr:id'],
                    'row_order': dt['@msdata:rowOrder'],

                    'invoice_id': dt['InvoiceID'],
                    'invoice_pay_id': invoice_pay_id.format(
                        dts['invoicepayid'].get(0) if 'invoicepayid' in dts else None,
                        dts['invoicepayid'].get(1) if 'invoicepayid' in dts else None,
                        dts['invoicepayid'].get(2) if 'invoicepayid' in dts else None,
                        dts['invoicepayid'].get(3) if 'invoicepayid' in dts else None),

                    'due_percent': dts['duepercent'].get(0) if 'duepercent' in dts else None,
                    'due_percent2': dts['duepercent'].get(1) if 'duepercent' in dts else None,
                    'due_percent3': dts['duepercent'].get(2) if 'duepercent' in dts else None,
                    'due_percent4': dts['duepercent'].get(3) if 'duepercent' in dts else None,
                    'remarks': dts['remarks'].get(0) if 'remarks' in dts else None,
                    'remarks2': dts['remarks'].get(1) if 'remarks' in dts else None,
                    'remarks3': dts['remarks'].get(2) if 'remarks' in dts else None,
                    'remarks4': dts['remarks'].get(3) if 'remarks' in dts else None,
                    'due_date': date_due if date_due else None,
                    'due_date2': date_due2 if date_due2 else None,
                    'due_date3': date_due3 if date_due3 else None,
                    'due_date4': date_due4 if date_due4 else None,

                    'post_date': self.convert_date_format(dt.get('postdate', None)),   
                }


                exist = self.env['sms.invoice'].search([('invoice_id', '=', invoice['invoice_id'])])
                if not exist:
                    self.env['sms.invoice'].create(invoice)
                    self.env.cr.commit()
                else:
                    break

    def sync_invoice_pay_view_by_invoice_id(self, inv_id=None):

        for rec in self:

            soap = """
                POST /odoows/invoice.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/InvoicePayViewByInvoiceID"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <InvoicePayViewByInvoiceID xmlns="http://FMS.dlsud.edu.ph/">
                    <_invoiceid>int</_invoiceid>
                    </InvoicePayViewByInvoiceID>
                </soap:Body>
                </soap:Envelope>
            """

            url = f"http://{rec.host}/fms/odoosync/invoice.asmx"

            payload = f"""
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <InvoicePayViewByInvoiceID xmlns="http://FMS.dlsud.edu.ph/">
                    <_invoiceid>{inv_id if inv_id else rec.invoice_id}</_invoiceid>
                    </InvoicePayViewByInvoiceID>
                </soap:Body>
                </soap:Envelope>
            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/InvoicePayViewByInvoiceID"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            # Convert XML content to dictionary
            response_dict = xmltodict.parse(xml_content)
            response_dict)

            dt_element = response_dict['soap:Envelope']['soap:Body']['InvoicePayViewByInvoiceIDResponse']['InvoicePayViewByInvoiceIDResult']['diffgr:diffgram']['DocumentElement']['DT']

            # Check if 'DT' is a list, if not, convert it to a list
            if not isinstance(dt_element, list):
                dt_element = [dt_element]

            new_dt = dt_element[0]
            duepercent = {}
            remarks = {}
            invoice_id = {}
            due_date = {}

            if len(dt_element) > 0:
                for index, dt in enumerate(dt_element):
                    duepercent[index] = dt['duepercent']
                    remarks[index] = dt['remarks']
                    invoice_id[index] = dt['invoicepayid']
                    due_date[index] = dt['duedate']
                
                new_dt['duepercent'] = duepercent
                new_dt['remarks'] = remarks
                new_dt['invoicepayid'] = invoice_id
                new_dt['duedate'] = due_date
                dts = new_dt
                invoice_pay_id = '({},{},{},{})'

                # due_date_converted = self.convert_date_format(dts['duedate']) if 'duedate' in dts else None

                dd = dts['duedate'].get(0)
                date_due = self.convert_date_format(dd)

                dd2 = dts['duedate'].get(1)
                date_due2 = self.convert_date_format(dd2)

                dd3 = dts['duedate'].get(2)
                date_due3 = self.convert_date_format(dd3)

                dd4 = dts['duedate'].get(3)
                date_due4 = self.convert_date_format(dd4)

                invoice = {
                    'diffgr_id': dt['@diffgr:id'],
                    'row_order': dt['@msdata:rowOrder'],

                    'invoice_id': dt['InvoiceID'],
                    'invoice_pay_id': invoice_pay_id.format(
                        dts['invoicepayid'].get(0) if 'invoicepayid' in dts else None,
                        dts['invoicepayid'].get(1) if 'invoicepayid' in dts else None,
                        dts['invoicepayid'].get(2) if 'invoicepayid' in dts else None,
                        dts['invoicepayid'].get(3) if 'invoicepayid' in dts else None),

                    'due_percent': dts['duepercent'].get(0) if 'duepercent' in dts else None,
                    'due_percent2': dts['duepercent'].get(1) if 'duepercent' in dts else None,
                    'due_percent3': dts['duepercent'].get(2) if 'duepercent' in dts else None,
                    'due_percent4': dts['duepercent'].get(3) if 'duepercent' in dts else None,
                    'remarks': dts['remarks'].get(0) if 'remarks' in dts else None,
                    'remarks2': dts['remarks'].get(1) if 'remarks' in dts else None,
                    'remarks3': dts['remarks'].get(2) if 'remarks' in dts else None,
                    'remarks4': dts['remarks'].get(3) if 'remarks' in dts else None,
                    'due_date': date_due if date_due else None,
                    'due_date2': date_due2 if date_due2 else None,
                    'due_date3': date_due3 if date_due3 else None,
                    'due_date4': date_due4 if date_due4 else None,

                    'post_date': self.convert_date_format(dt.get('postdate', None)),   
                }


                exist = self.env['sms.invoice'].search([('invoice_id', '=', invoice['invoice_id'])])
                if not exist:
                    self.env['sms.invoice'].create(invoice)
                    self.env.cr.commit()
                else:
                    exist.write(invoice)
                    self.env.cr.commit()

    def sync_invoice_pay_view_by_invoice_pay_id(self):

        for rec in self:

            soap = """
                POST /odoows/invoice.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: application/soap+xml; charset=utf-8
                Content-Length: length

                <?xml version="1.0" encoding="utf-8"?>
                <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                <soap12:Body>
                    <InvoicePayViewByInvoicePayID xmlns="http://FMS.dlsud.edu.ph/">
                    <_invoicepayid>int</_invoicepayid>
                    </InvoicePayViewByInvoicePayID>
                </soap12:Body>
                </soap12:Envelope>
            """

            url = f"http://{rec.host}/fms/odoosync/invoice.asmx"

            payload = f"""
                <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                <soap12:Body>
                    <InvoicePayViewByInvoicePayID xmlns="http://FMS.dlsud.edu.ph/">
                    <_invoicepayid>{rec.invoice_pay_id}</_invoicepayid>
                    </InvoicePayViewByInvoicePayID>
                </soap12:Body>
                </soap12:Envelope>
            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/InvoicePayViewByInvoicePayID"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            # Convert XML content to dictionary
            response_dict = xmltodict.parse(xml_content)
            response_dict)

            dt_element = response_dict['soap:Envelope']['soap:Body']['InvoicePayViewByInvoicePayIDResponse']['InvoicePayViewByInvoicePayIDResult']['diffgr:diffgram']['DocumentElement']['DT']

            # Check if 'DT' is a list, if not, convert it to a list
            if not isinstance(dt_element, list):
                dt_element = [dt_element]

            new_dt = dt_element[0]
            duepercent = {}
            remarks = {}
            invoice_id = {}
            due_date = {}

            if len(dt_element) > 0:
                for index, dt in enumerate(dt_element):
                    duepercent[index] = dt['duepercent']
                    remarks[index] = dt['remarks']
                    invoice_id[index] = dt['invoicepayid']
                    due_date[index] = dt['duedate']
                
                new_dt['duepercent'] = duepercent
                new_dt['remarks'] = remarks
                new_dt['invoicepayid'] = invoice_id
                new_dt['duedate'] = due_date
                dts = new_dt
                invoice_pay_id = '({},{},{})'

                # due_date_converted = self.convert_date_format(dts['duedate']) if 'duedate' in dts else None

                dd = dts['duedate'].get(0)
                date_due = self.convert_date_format(dd)

                dd2 = dts['duedate'].get(1)
                date_due2 = self.convert_date_format(dd2)

                dd3 = dts['duedate'].get(2)
                date_due3 = self.convert_date_format(dd3)

                dd4 = dts['duedate'].get(3)
                date_due4 = self.convert_date_format(dd4)

                invoice = {
                    'diffgr_id': dt['@diffgr:id'],
                    'row_order': dt['@msdata:rowOrder'],

                    'invoice_id': dt['InvoiceID'],
                    'invoice_pay_id': invoice_pay_id.format(dts['invoicepayid'].get(0) if 'invoicepayid' in dts else None,dts['invoicepayid'].get(1) if 'invoicepayid' in dts else None,dts['invoicepayid'].get(2) if 'invoicepayid' in dts else None,dts['invoicepayid'].get(3) if 'invoicepayid' in dts else None),

                    'due_percent': dts['duepercent'].get(0) if 'duepercent' in dts else None,
                    'due_percent2': dts['duepercent'].get(1) if 'duepercent' in dts else None,
                    'due_percent3': dts['duepercent'].get(2) if 'duepercent' in dts else None,
                    'due_percent4': dts['duepercent'].get(3) if 'duepercent' in dts else None,
                    'remarks': dts['remarks'].get(0) if 'remarks' in dts else None,
                    'remarks2': dts['remarks'].get(1) if 'remarks' in dts else None,
                    'remarks3': dts['remarks'].get(2) if 'remarks' in dts else None,
                    'remarks4': dts['remarks'].get(3) if 'remarks' in dts else None,
                    'due_date': date_due if date_due else None,
                    'due_date2': date_due2 if date_due2 else None,
                    'due_date3': date_due3 if date_due3 else None,
                    'due_date4': date_due4 if date_due4 else None,

                    'post_date': self.convert_date_format(dt.get('postdate', None)),   
                }


                exist = self.env['sms.invoice'].search([('invoice_id', '=', invoice['invoice_id'])])
                if not exist:
                    self.env['sms.invoice'].create(invoice)
                else:
                    exist.write(invoice)
    
    def sync_invoice_detail_view_by_invoice_ref_no(self):

        for rec in self:

            soap = """
                POST /odoows/invoice.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: application/soap+xml; charset=utf-8
                Content-Length: length

                <?xml version="1.0" encoding="utf-8"?>
                <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                <soap12:Body>
                    <InvoiceDetailViewByInvoiceRefNo xmlns="http://FMS.dlsud.edu.ph/">
                    <_invoicerefno>string</_invoicerefno>
                    </InvoiceDetailViewByInvoiceRefNo>
                </soap12:Body>
                </soap12:Envelope>
            """

            url = f"http://{rec.host}/fms/odoosync/invoice.asmx"

            payload = f"""
                <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                <soap12:Body>
                    <InvoiceDetailViewByInvoiceRefNo xmlns="http://FMS.dlsud.edu.ph/">
                    <_invoicerefno>{rec.invoice_ref_no}</_invoicerefno>
                    </InvoiceDetailViewByInvoiceRefNo>
                </soap12:Body>
                </soap12:Envelope>
            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/InvoiceDetailViewByInvoiceRefNo"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            # Convert XML content to dictionary
            response_dict = xmltodict.parse(xml_content)
            response_dict)

            dt_element = response_dict['soap:Envelope']['soap:Body']['InvoiceDetailViewByInvoiceRefNoDResponse']['InvoiceDetailViewByInvoiceRefNoResult']['diffgr:diffgram']['DocumentElement']['DT']

            # Check if 'DT' is a list, if not, convert it to a list
            if not isinstance(dt_element, list):
                dt_element = [dt_element]

            if len(dt_element) > 0:
                for dt in dt_element:
                    invoice = {
                        'diffgr_id': dt['@diffgr:id'],
                        'row_order': dt['@msdata:rowOrder'],
                        'invoice_id': dt['InvoiceID'],
                        'invoice_date': self.convert_date_format(dt.get('InvoiceDate', None)), 
                        'invoice_ref_no': dt['InvoiceRefNo'] if 'InvoiceRefNo' in dt else None,
                        'inv_type': dt['InvType'] if 'InvType' in dt else None,
                        'inv_type_desc': dt['InvTypeDesc'] if 'InvTypeDesc' in dt else None,
                        'customer_type': dt['CustomerType'] if 'CustomerType' in dt else None,
                        'customer_id': dt['CustomerID'] if 'CustomerID' in dt else None,
                        'customer_ref_id': dt['CustomerRefID']if 'CustomerRefID' in dt else None,
                        'customer_name': dt['CustomerName'] if 'CustomerName' in dt else None,
                        'pay_term': dt['PayTerm'] if 'PayTerm' in dt else None,
                        'total_amount': float(dt['TotalAmount']) if 'TotalAmount' in dt else None,
                        'adjusted': dt['Adjusted'].lower() == 'true',
                        'void': dt['Void'].lower() == 'true',
                        'l_name': dt['LName']if 'LName' in dt else None,
                        'f_name': dt['FName']if 'FName' in dt else None,
                        'm_name': dt['Mname']if 'Mname' in dt else None,
                        'suffix': dt['Suffix']if 'Suffix' in dt else None,
                        'amount_due': float(dt['amountdue']) if 'amountdue' in dt else None,
                        'due_date': self.convert_date_format(dt.get('duedate', None)), 
                        'post_date': self.convert_date_format(dt.get('postdate', None)), 
                        'invoice_pay_id': dt['invoicepayid']if 'invoicepayid' in dt else None,
                        'invoice_pay_no': dt['invoicepayno']if 'invoicepayno' in dt else None,
                        'void_date': self.convert_date_format(dt.get('voiddate', None)) if 'voiddate' in dt else None,
                        'void_remarks': dt['voidremarks'] if 'voidremarks' in dt else None,
                        'invoice_adj_id': dt['invoiceadjid'] if 'invoiceadjid' in dt else None,
                        'invoice_adj_no': dt['invoiceadjno'] if 'invoiceadjno' in dt else None,
                        'adjust_date': self.convert_date_format(dt.get('adjustdate', None)) if 'adjustdate' in dt else None,
                        'total_adj_amount': float(dt['totaladjamount']) if 'totaladjamount' in dt else None,
                        'adj_remarks': dt['adjremarks'] if 'adjremarks' in dt else None,
                        'invoice_det_id': dt['invoicedetid'] if 'invoicedetid' in dt else None,
                        'inv_det_adj_id': dt['invdetadjid'] if 'invdetadjid' in dt else None,
                        'prod_id': dt['prodid'] if 'prodid' in dt else None,
                        'prod_code': dt['prodcode'] if 'prodcode' in dt else None,
                        'prod_desc': dt['proddesc'] if 'proddesc' in dt else None,
                        'account_code': dt['accountcode'] if 'accountcode' in dt else None,
                        'unit_price': float(dt['unitprice']) if 'unitprice' in dt else None,
                        'qty': int(dt['qty']) if 'qty' in dt else None,
                        'amount': float(dt['amount']) if 'amount' in dt else None,
                        'remarks': dt['remarks'] if 'remarks' in dt else None,
                    }

                    exist = self.env['sms.invoice'].search([('invoice_id', '=', invoice['invoice_id']), ('invoice_det_id', '=', invoice['invoice_det_id'])])
                    exist1 = self.env['sms.invoice'].search([('invoice_id', '=', invoice['invoice_id']), ('inv_det_adj_id', '=', invoice['inv_det_adj_id'])])
                    if not exist and not exist1:
                        self.env['sms.invoice'].create(invoice)
                    else:
                        pass
 
    def sync_invoice_pay_view_by_invoice_ref_no(self):

        for rec in self:

            soap = """
                POST /odoows/invoice.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: application/soap+xml; charset=utf-8
                Content-Length: length

                <?xml version="1.0" encoding="utf-8"?>
                <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                <soap12:Body>
                    <InvoicePayViewByInvoiceRefNo xmlns="http://FMS.dlsud.edu.ph/">
                    <_invoicerefno>string</_invoicerefno>
                    </InvoicePayViewByInvoiceRefNo>
                </soap12:Body>
                </soap12:Envelope>
            """

            url = f"http://{rec.host}/fms/odoosync/invoice.asmx"

            payload = f"""
                <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                <soap12:Body>
                    <InvoicePayViewByInvoiceRefNo xmlns="http://FMS.dlsud.edu.ph/">
                    <_invoicerefno>{rec.invoice_ref_no}</_invoicerefno>
                    </InvoicePayViewByInvoiceRefNo>
                </soap12:Body>
                </soap12:Envelope>
            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/InvoicePayViewByInvoiceRefNo"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            # Convert XML content to dictionary
            response_dict = xmltodict.parse(xml_content)
            response_dict)

            dt_element = response_dict['soap:Envelope']['soap:Body']['InvoicePayViewByInvoiceRefNoResponse']['InvoicePayViewByInvoiceRefNoResult']['diffgr:diffgram']['DocumentElement']['DT']

            # Check if 'DT' is a list, if not, convert it to a list
            if not isinstance(dt_element, list):
                dt_element = [dt_element]

            if len(dt_element) > 0:
                for dt in dt_element:
                    invoice = {
                        'diffgr_id': dt['@diffgr:id'],
                        'row_order': dt['@msdata:rowOrder'],
                        'invoice_id': dt['InvoiceID'],
                        'invoice_date': self.convert_date_format(dt.get('InvoiceDate', None)), 
                        'invoice_ref_no': dt['InvoiceRefNo'] if 'InvoiceRefNo' in dt else None,
                        'inv_type': dt['InvType'] if 'InvType' in dt else None,
                        'inv_type_desc': dt['InvTypeDesc'] if 'InvTypeDesc' in dt else None,
                        'customer_type': dt['CustomerType'] if 'CustomerType' in dt else None,
                        'customer_id': dt['CustomerID'] if 'CustomerID' in dt else None,
                        'customer_ref_id': dt['CustomerRefID']if 'CustomerRefID' in dt else None,
                        'customer_name': dt['CustomerName'] if 'CustomerName' in dt else None,
                        'pay_term': dt['PayTerm'] if 'PayTerm' in dt else None,
                        'total_amount': float(dt['TotalAmount']) if 'TotalAmount' in dt else None,
                        'adjusted': dt['Adjusted'].lower() == 'true',
                        'void': dt['Void'].lower() == 'true',
                        'l_name': dt['LName']if 'LName' in dt else None,
                        'f_name': dt['FName']if 'FName' in dt else None,
                        'm_name': dt['Mname']if 'Mname' in dt else None,
                        'suffix': dt['Suffix']if 'Suffix' in dt else None,
                        'amount_due': float(dt['amountdue']) if 'amountdue' in dt else None,
                        'due_date': self.convert_date_format(dt.get('duedate', None)), 
                        'post_date': self.convert_date_format(dt.get('postdate', None)), 
                        'invoice_pay_id': dt['invoicepayid']if 'invoicepayid' in dt else None,
                        'invoice_pay_no': dt['invoicepayno']if 'invoicepayno' in dt else None,
                        'void_date': self.convert_date_format(dt.get('voiddate', None)) if 'voiddate' in dt else None,
                        'void_remarks': dt['voidremarks'] if 'voidremarks' in dt else None,
                        'invoice_adj_id': dt['invoiceadjid'] if 'invoiceadjid' in dt else None,
                        'invoice_adj_no': dt['invoiceadjno'] if 'invoiceadjno' in dt else None,
                        'adjust_date': self.convert_date_format(dt.get('adjustdate', None)) if 'adjustdate' in dt else None,
                        'total_adj_amount': float(dt['totaladjamount']) if 'totaladjamount' in dt else None,
                        'adj_remarks': dt['adjremarks'] if 'adjremarks' in dt else None,
                        'invoice_det_id': dt['invoicedetid'] if 'invoicedetid' in dt else None,
                        'inv_det_adj_id': dt['invdetadjid'] if 'invdetadjid' in dt else None,
                        'prod_id': dt['prodid'] if 'prodid' in dt else None,
                        'prod_code': dt['prodcode'] if 'prodcode' in dt else None,
                        'prod_desc': dt['proddesc'] if 'proddesc' in dt else None,
                        'account_code': dt['accountcode'] if 'accountcode' in dt else None,
                        'unit_price': float(dt['unitprice']) if 'unitprice' in dt else None,
                        'qty': int(dt['qty']) if 'qty' in dt else None,
                        'amount': float(dt['amount']) if 'amount' in dt else None,
                        'remarks': dt['remarks'] if 'remarks' in dt else None,
                    }

                    exist = self.env['sms.invoice'].search([('invoice_id', '=', invoice['invoice_id']), ('invoice_det_id', '=', invoice['invoice_det_id'])])
                    exist1 = self.env['sms.invoice'].search([('invoice_id', '=', invoice['invoice_id']), ('inv_det_adj_id', '=', invoice['inv_det_adj_id'])])
                    if not exist and not exist1:
                        self.env['sms.invoice'].create(invoice)
                    else:
                        pass

    def post_invoice_by_odoo(self):
        for rec in self:

            soap = """
                POST /odoows/invoice.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/InvoicePayPost"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <InvoicePayPost xmlns="http://FMS.dlsud.edu.ph/">
                    <_user>string</_user>
                    <_invoicepayid>long</_invoicepayid>
                    <_remarks>string</_remarks>
                    <_paidamount>decimal</_paidamount>
                    <_paidinvoice>string</_paidinvoice>
                    </InvoicePayPost>
                </soap:Body>
                </soap:Envelope>
            """

            url = f"http://{rec.host}/fms/odoosync/invoice.asmx"

            # datecreatedfrom = rec.invoice_date_from.strftime('%Y-%m-%d')
            # datecreatedto = rec.invoice_date_to.strftime('%Y-%m-%d')

            payload = f"""
            <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <InvoicePayPost xmlns="http://FMS.dlsud.edu.ph/">
                <_user>{rec.api_user_id.name}</_user>
                <_invoicepayid>{rec.api_invoice_pay_id}</_invoicepayid>
                <_remarks>{rec.api_remarks}</_remarks>
                <_paidamount>{round(rec.api_paid_amount,2)}</_paidamount>
                <_paidinvoice>{rec.api_paid_invoice_id.name}</_paidinvoice>
                </InvoicePayPost>
            </soap:Body>
            </soap:Envelope>
            """

            _logger.debug('Sync Back to Edata payload: %s', payload)

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/InvoicePayPost"'
            }
            try:
                response = requests.request("POST", url, headers=headers, data=payload)
                xml_content = response.content
                xml_content)
            except Exception as e:
                raise UserError(e)


    def invoice_sync_back_odoo_v2(self, inv_id=None):
        for rec in self:
            _logger.info('Starting invoice_sync_back_odoo_v2 process')
            soap = """
                POST /odoows/invoice.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/InvoiceSyncBack"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <InvoiceSyncBack xmlns="http://FMS.dlsud.edu.ph/">
                    <_user>string</_user>
                    <_invoiceid>long</_invoiceid>
                    <_fmsinvoiceid>string</_fmsinvoiceid>
                    <_fmstotalamount>decimal</_fmstotalamount>
                    </InvoiceSyncBack>
                </soap:Body>
                </soap:Envelope>
            """
            sync_sms = self.env['sync.sms.settings'].search([],limit=1)

            url = f"http://{sync_sms.host}/fms/odoosync/invoice.asmx"

            current_user = self.env.user.partner_id.name
            sync_sms = self.env['sms.invoice'].search([('invoice_id','=',inv_id)],limit=1)
            # account_move = self.env['account.move'].search([('invoice_id','=',inv_id)],limit=1)

            payload = f"""
            <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <InvoiceSyncBack xmlns="http://FMS.dlsud.edu.ph/">
                    <_user>{current_user}</_user>
                    <_invoiceid>{sync_sms.invoice_id}</_invoiceid>
                    <_fmsinvoiceid>{sync_sms.invoice_id}</_fmsinvoiceid>
                    <_fmstotalamount>{sync_sms.total_amount}</_fmstotalamount>
                    </InvoiceSyncBack>
                </soap:Body>
                </soap:Envelope>
            """

            _logger.debug('Payload: %s', payload)

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/InvoiceSyncBack"'
            }
            try:
                response = requests.request("POST", url, headers=headers, data=payload)
                xml_content = response.content
                xml_content)
            except Exception as e:
                raise UserError(e)

    @api.onchange('api_paid_invoice_id')
    def get_odoo_invoice(self):
        for rec in self:
            move = self.env['account.move'].search([('id','=', rec.api_paid_invoice_id.id)])
            if move:
                reamrks =  (move.state + ', ' + move.payment_state)
                rec.api_remarks = reamrks
                rec.api_paid_amount = float(move.amount_total) - float(move.amount_residual)
                rec.api_invoice_pay_id = int(move.inv_pay_id)
                rec.api_user_id = rec.env.user
            else:
                rec.api_remarks = None
                rec.api_paid_amount = 0.0
                rec.api_invoice_pay_id = None
                rec.api_user_id = None

    def post_payment_by_odoo(self,user_name=False,invoice_pay_id=False,remarks=False,paid_amount=False,odoo_invoice_id=False):
        for rec in self:

            soap = """
                POST /odoows/invoice.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/InvoicePayPost"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <InvoicePayPost xmlns="http://FMS.dlsud.edu.ph/">
                    <_user>string</_user>
                    <_invoicepayid>long</_invoicepayid>
                    <_remarks>string</_remarks>
                    <_paidamount>decimal</_paidamount>
                    <_paidinvoice>string</_paidinvoice>
                    </InvoicePayPost>
                </soap:Body>
                </soap:Envelope>
            """

            url = f"http://{rec.host}/fms/odoosync/invoice.asmx"

            # datecreatedfrom = rec.invoice_date_from.strftime('%Y-%m-%d')
            # datecreatedto = rec.invoice_date_to.strftime('%Y-%m-%d')

            payload = f"""
            <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <InvoicePayPost xmlns="http://FMS.dlsud.edu.ph/">
                <_user>{user_name}</_user>
                <_invoicepayid>{invoice_pay_id}</_invoicepayid>
                <_remarks>{remarks}</_remarks>
                <_paidamount>{round(paid_amount,2)}</_paidamount>
                <_paidinvoice>{odoo_invoice_id}</_paidinvoice>
                </InvoicePayPost>
            </soap:Body>
            </soap:Envelope>
            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/InvoicePayPost"'
            }
            try:
                response = requests.request("POST", url, headers=headers, data=payload)
                xml_content = response.content
                xml_content)
            except Exception as e:
                raise UserError(e)

class StudentEndingBalance(models.Model):
    _inherit = 'res.partner'

    def post_ending_balance_by_odoo(self):
        'ENDING BALANCE')
        for rec in self:

            soap = """
                POST /odoows/student.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/StudentEndBalInsert"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <StudentEndBalInsert xmlns="http://FMS.dlsud.edu.ph/">
                    <_user>string</_user>
                    <_id>string</_id>
                    <_refid>string</_refid>
                    <_name>string</_name>
                    <_endbalamount>decimal</_endbalamount>
                    <_dateasof>dateTime</_dateasof>
                    <_remarks>string</_remarks>
                    </StudentEndBalInsert>
                </soap:Body>
                </soap:Envelope>
            """
            sync_sms = self.env['sync.sms.settings'].search([],limit=1)
            date = datetime.now().strftime('%Y-%m-%d')

            # url = f"http://{sync_sms.host}/odoows/student.asmx"
            url = f"http://{sync_sms.host}/fms/odoosync/student.asmx"
            

            payload = f"""
            <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
            <soap12:Body>
                <StudentEndBalInsert xmlns="http://FMS.dlsud.edu.ph/">
                <_user>{rec.env.user.name}</_user>
                <_id>{rec.customer_id}</_id>
                <_refid>{rec.id}</_refid>
                <_name>{rec.name}</_name>
                <_endbalamount>{rec.credit}</_endbalamount>
                <_dateasof>{date}</_dateasof>
                <_remarks>{'Ending Balance'}</_remarks>
                </StudentEndBalInsert>
            </soap12:Body>
            </soap12:Envelope>
            """

            payload)

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/StudentEndBalInsert"',
            'Connection': 'keep-alive',
            }
            try:
                response = requests.request("POST", url, headers=headers, data=payload)
                xml_content = response.content
                xml_content)
            except Exception as e:
                raise UserError(e)
            
    def post_ending_balance_list_by_odoo(self):
        'ENDING LIST BALANCE')
        store = []
        
        for rec in self:

            soap = """
                POST /odoows/student.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/StudentEndBalInsertBatch"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <StudentEndBalInsertBatch xmlns="http://FMS.dlsud.edu.ph/">
                    <_user>string</_user>
                    <_json>string</_json>
                    </StudentEndBalInsertBatch>
                </soap:Body>
                </soap:Envelope
            """
            sync_sms = self.env['sync.sms.settings'].search([],limit=1)
            date = datetime.now().strftime('%Y-%m-%d')

            # url = f"http://{sync_sms.host}/odoows/student.asmx"
            url = f"http://{sync_sms.host}/fms/odoosync/student.asmx"

            vals = {
                'ID': rec.customer_id,
                'RefOD': rec.id,
                'Name': rec.name,
                'EndBalAmount': rec.credit,
                'DateAsOf': date,
                'Remarks': 'Ending Balnce'
            }

            store.append(vals)
            json_vals = json.dumps(store)

        payload = f"""
        <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
        <soap12:Body>
            <StudentEndBalInsertBatch xmlns="http://FMS.dlsud.edu.ph/">
            <_user>{rec.env.user.name}</_user>
            <_json>{json_vals}</_json>
            </StudentEndBalInsertBatch>
        </soap12:Body>
        </soap12:Envelope>
        """

        payload)

        headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': '"http://FMS.dlsud.edu.ph/StudentEndBalInsertBatch"',
        'Connection': 'keep-alive',
        }

        try:
            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content
            xml_content)
        except Exception as e:
            raise UserError(e)

    def sync_partners_to_portal_manual(self):
        active_ids = self.env.context.get('active_ids', [])
        _logger.debug('Active IDs: %s', active_ids)
        query = """
            SELECT id, customer_id 
            FROM res_partner 
            WHERE is_customer_portal = False 
            AND id in %s
            
        """ %(str(active_ids).replace("[","(").replace("]",")"))
        self._cr.execute(query)
        partners = self.env.cr.fetchall()  # Fetch all matching records

        if not partners:
            return

        # Fetch XML-RPC configuration parameters  
        config_params = self.env['ir.config_parameter'].sudo()
        source_url = config_params.get_param('xml.rpc.remote.url')
        source_db = config_params.get_param('xml.rpc.remote.db')
        source_username = config_params.get_param('xml.rpc.remote.username')
        source_password = config_params.get_param('xml.rpc.remote.password')

        # Authenticate with XML-RPC  
        source_common = xmlrpc.client.ServerProxy(f'{source_url}/xmlrpc/2/common')
        source_uid = source_common.authenticate(source_db, source_username, source_password, {})

        source_models = xmlrpc.client.ServerProxy(f'{source_url}/xmlrpc/2/object')

        partner_ids = []
        for partner_id, customer_id in partners:
            if customer_id:
                data = source_models.execute_kw(source_db, source_uid, source_password, 
                                                'res.company', 'sync_user', [False, partner_id], {})
                partner_ids.append(partner_id)

        if partner_ids:
            # Update the selected records in a single SQL query
            query = """
                UPDATE res_partner 
                SET is_customer_portal = True 
                WHERE id IN %s
            """
            self.env.cr.execute(query, (tuple(partner_ids),))
            self.env.cr.commit()  # Ensure changes are saved immediately
class CancelAllInvoices(models.Model):
    _inherit = 'account.move'

    def cancel_all(self):
        for rec in self:
            # rec.state = 'cancel'
            rec.invoice_ref_no = 'VOID'
            rec.is_adjusted = False
            rec.is_first_payment = False
            rec.adjustment_no = 'VOID'
            rec.cancellation_remarks = 'CANCELLED/VOID'
            rec.invoice_ref_no = 'VOID'
            rec.button_draft()
            rec.button_cancel()

