# -*- coding: utf-8 -*-
"""
DLSU SMS Integration - Synchronization Logging Module

This module provides logging and tracking functionality for SMS-Odoo synchronization.
It maintains a log of all invoice synchronization attempts and provides methods to:

- Track synchronization status of invoices
- Handle enrollment assessments and admission-related invoices
- Sync invoice data back to SMS after processing in Odoo
- Generate and process synchronization logs in batches
- Support automated synchronization via cron jobs
"""

from odoo import models, fields, api
import requests
import xml.etree.ElementTree as ET
import xmltodict
import logging
from datetime import datetime
import pytz
from odoo.exceptions import except_orm, Warning, RedirectWarning, UserError, ValidationError

_logger = logging.getLogger(__name__)


class SyncInvoiceLog(models.Model):
    """
    Model to track invoice synchronization between SMS and Odoo.

    Maintains a log of all invoices that need to be synchronized,
    tracks their status, and provides methods to process them.
    """
    _name = 'dlsu.sync.logs'
    _description = 'SMS-Odoo Synchronization Log'
    _rec_name = 'name'
    _order = 'create_date desc'

    name = fields.Char('Invoice Ref')
    invoice_type = fields.Char('Invoice Type')
    partner_name = fields.Char('Student')
    customer_id = fields.Char('Customer ID')
    invoice_id = fields.Char('Invoice ID')
    invoice_amount = fields.Float('Invoice Amount')
    invoice_name = fields.Char('Invoice Name')
    is_sms = fields.Boolean('Is from SMS?', default=False)
    status = fields.Selection([('sync','Synced'),('not_sync','Not Yet Sync')], string='Status', default='not_sync')
    active = fields.Boolean(string='Active', default=False)

    def invoice_sync_back_odoo(self):
        """
        Synchronize invoice data back to SMS after processing in Odoo.

        Sends the Odoo invoice details (ID, amount) back to SMS via SOAP
        to maintain data consistency between systems.
        """
        for rec in self:

            sync_sms = self.env['sync.sms.settings'].search([],limit=1)

            # url = f"http://127.0.0.1/odoows/invoice.asmx"
            url = f"http://{sync_sms.host}/fms/odoosync/invoice.asmx"

            current_user = self.env.user.partner_id.name
            payload = f"""
            <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <InvoiceSyncBack xmlns="http://FMS.dlsud.edu.ph/">
                    <_user>{current_user}</_user>
                    <_invoiceid>{rec.invoice_id}</_invoiceid>
                    <_fmsinvoiceid>{rec.invoice_name}</_fmsinvoiceid>
                    <_fmstotalamount>{rec.invoice_amount}</_fmstotalamount>
                    </InvoiceSyncBack>
                </soap:Body>
                </soap:Envelope>
            """


            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/InvoiceSyncBack"'
            }
            try:
                response = requests.request("POST", url, headers=headers, data=payload)
                xml_content = response.content
                except Exception as e:
                raise UserError(e)

    def sync_invoice_log_cron(self):
        """
        Cron job method to process pending synchronization logs.

        Processes up to 5 pending logs per execution to avoid timeout.
        Called automatically by Odoo scheduler.
        """
        logs = self.search([('status','=','not_sync')],  limit=5)
        for rec in logs:
            if logs:
                rec.action_sync_log()

    def action_sync_log(self):
        """
        Process a synchronization log entry.

        Based on the invoice type, triggers the appropriate endpoint
        to create assessments or applications in Odoo, then syncs
        the result back to SMS.
        """
        for rec in self:
            invoice =  rec.invoice_id
            customer = rec.customer_id

            if rec.invoice_type == 'ENROLLMENT ASSESSMENT':
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                try:
                    complete_url = f"{base_url}/master_create_assessment?invoice_id={invoice}&customer_id={customer}"

                    payload = {
                        'invoice_id': invoice,
                        'customer_id': customer
                    }

                    response = requests.post(complete_url, data=payload)
                    response.raise_for_status()
                    rec.status = 'sync'
                    self.env.cr.commit()
        
                    logs = self.env['dlsu.sync.logs'].search([('customer_id','=',customer), ('invoice_id','=',invoice)],limit = 1)
                    account_move = self.env['account.move'].search([('invoice_ref_no', '=', logs.name),('is_first_payment','=',True)], limit = 1)

                    logs.update({'invoice_name': account_move.name, 'invoice_amount': account_move.amount_total})

                    rec.invoice_sync_back_odoo()
                    self.env.cr.commit()

                except requests.exceptions.RequestException as e:
                    _logger.error(f'Request failed: {e}')

            #     base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            #     try:
            #         complete_url = f"{base_url}/master_create_application?invoice_id={invoice}&customer_id={customer}"

            #         payload = {
            #             'invoice_id': invoice,
            #             'customer_id': customer
            #         }

            #         response = requests.post(complete_url, data=payload)
            #         response.raise_for_status()
            #         rec.status = 'sync'

            #         self.env.cr.commit()

            #         logs = self.env['dlsu.sync.logs'].search([('customer_id','=',customer), ('invoice_id','=',invoice)],limit = 1)
            #         account_move = self.env['account.move'].search([('invoice_ref_no', '=', logs.name),('is_first_payment','=',True)], limit = 1)

            #         logs.update({'invoice_name': account_move.name, 'invoice_amount': account_move.amount_total})

            #         rec.invoice_sync_back_odoo()
            #         self.env.cr.commit()

            #     except requests.exceptions.RequestException as e:
            # else:
            #     base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            #     try:
            #         complete_url = f"{base_url}/catch_all?invoice_id={invoice}&customer_id={customer}"

            #         payload = {
            #             'invoice_id': invoice,
            #             'customer_id': customer
            #         }

            #         response = requests.post(complete_url, data=payload)
            #         response.raise_for_status()
            #         rec.status = 'sync'

            #         self.env.cr.commit()

            #         logs = self.env['dlsu.sync.logs'].search([('customer_id','=',customer), ('invoice_id','=',invoice)],limit = 1)
            #         account_move = self.env['account.move'].search([('invoice_ref_no', '=', logs.name),('is_first_payment','=',True)], limit = 1)

            #         logs.update({'invoice_name': account_move.name, 'invoice_amount': account_move.amount_total})

            #         rec.invoice_sync_back_odoo()
            #         self.env.cr.commit()

                # except requests.exceptions.RequestException as e:


class SyncSMSLogs(models.Model):
    """
    Extended settings model for log generation functionality.
    """
    _inherit = 'sync.sms.settings'

    def generate_log(self):
        """
        Generate synchronization logs from unsynced SMS invoices.

        Queries SMS invoice table for unsynced enrollment and admission
        invoices, then creates log entries for processing. Processes
        records in batches of 100 to optimize performance.
        """

        sms_query = """
            SELECT 
            customer_id,
            invoice_id,
            invoice_ref_no,
            inv_type_desc,
            customer_name

            FROM sms_invoice

            WHERE is_sync = False
            AND inv_type_desc IN ('ENROLLMENT ASSESSMENT', 'ADMISSION ENTRANCE EXAM', 'ADMISSION FEE', 'ADMISSION APPLICATION', 'ADMISSION OTHER PROCESS')
            GROUP BY customer_id, invoice_id, invoice_ref_no, inv_type_desc, customer_name
        """
        self._cr.execute(sms_query)
        result = self._cr.fetchall()

        batch_size = 100  # Specify the desired batch size
        total_records = len(result)
        
        # Process in batches
        for batch_start in range(0, total_records, batch_size):
            
            batch = result[batch_start:batch_start + batch_size]  # Get the current batch

            for data in batch:
                vals = {
                    'name': data[2],
                    'partner_name': data[4],
                    'invoice_type': data[3],
                    'customer_id': data[0],
                    'invoice_id': data[1],
                    'status': 'not_sync',
                    'is_sms': True,
                    'active': True,
                }

                sync_log = self.env['dlsu.sync.logs']
                existing_log = sync_log.search([
                    ('customer_id', '=', data[0]),
                    ('invoice_id', '=', data[1]),
                    ('name', '=', data[2]),
                    ('is_sms', '=', True),
                ])

                if not existing_log:
                    sync_log.create(vals)

            
            sms_query = """
                SELECT 
                customer_id,
                invoice_id,
                invoice_ref_no,
                inv_type_desc,
                customer_name

                FROM sms_invoice

                WHERE is_sync = False
                AND inv_type_desc IN ('ENROLLMENT ASSESSMENT', 'ADMISSION ENTRANCE EXAM', 'ADMISSION FEE', 'ADMISSION APPLICATION', 'ADMISSION OTHER PROCESS')
                GROUP BY customer_id, invoice_id, invoice_ref_no, inv_type_desc, customer_name
            """
            self._cr.execute(sms_query)
            result = self._cr.fetchall()

            _logger.info(f'Processed batch from {batch_start} to {min(batch_start + batch_size, total_records)}')


    def sync_logs_cron(self):
        """
        Cron job to generate synchronization logs.

        Automatically generates logs for unsynced invoices.
        Called by Odoo scheduler.
        """
        logs = self.search([])
        for rec in logs:
            if logs:
                rec.generate_log()


    
    
