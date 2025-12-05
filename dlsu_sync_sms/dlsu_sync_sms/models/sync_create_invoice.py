# -*- coding: utf-8 -*-
from odoo import models, fields, api
import requests
import xml.etree.ElementTree as ET
import xmltodict
import logging
from datetime import date, datetime, timedelta
import pytz  # Import the pytz library to handle timezones
import xmlrpc.client


_logger = logging.getLogger(__name__)

class ProductAccountCheckWizard(models.TransientModel):
    _name = 'product.account.check.wizard'
    _description = 'Product Account Check Wizard'

    product_names = fields.Text(string='Products Without Account', readonly=True)

    @api.model
    def default_get(self, fields):
        res = super(ProductAccountCheckWizard, self).default_get(fields)
        product_names = self._context.get('product_names', False)
        if product_names:
            res.update({'product_names': product_names})
        return res
    
    def action_ok(self):
        return {'type': 'ir.actions.act_window_close'}

class CreateReference(models.Model):
    _inherit = 'account.move'

    invoice_ref_no = fields.Char('Invoice Reference No.')
    inv_type_desc = fields.Char('Invoice Type Description')

   
    course = fields.Char('Course')
    year = fields.Char('Year')
    school_year = fields.Char('School Year')
    term = fields.Char('Term')

    invoice_category = fields.Selection(selection=[
		('subsidized','SUBSIDIZED'),
		('passed_one','PASSED-ON'),
		], string="Invoice Category", tracking=True)

    adjustment_no = fields.Char('Adjustment No.')
    is_student = fields.Boolean('is Student', related='partner_id.is_student', store=True)

class CreateCustomerId(models.Model):
    _inherit = 'res.partner'

    customer_id = fields.Char('Customer ID', tracking=True)
    is_customer_portal = fields.Boolean('is Portal Customer', default=False, tracking=True, store=True)

class DLSUDCustomAccountPayment(models.Model):
    _inherit = 'account.payment'

    customer_id = fields.Char(
        related="partner_id.customer_id", 
        string="Customer ID", 
        store=False  # Not stored to avoid redundancy
    )


class CreateProduct(models.Model):
    _inherit = 'product.template'

    prod_id = fields.Integer('Product ID')
    prod_type_id = fields.Integer('Product Type ID')

 
class SyncCreateInvoices(models.Model):
    _inherit = 'sync.sms.settings'

    def sync_create_aplicant_sms(self):
        _logger.info('Processing applicant records')

        ar = self.env['account.account'].search([('code', '=', '1020101000')], limit=1)
        ap = self.env['account.account'].search([('code', '=', '2010101000')], limit=1)

        for rec in self:

            sms_applicant = rec.env['sms.applicant'].search([])
            data = sms_applicant.read(['applicant_id', 'student_id'])

            student_ids = [item['student_id'] for item in data if 'student_id' in item]


            unique_student_ids = list(set(student_ids))

            applicant_ids = [item['applicant_id'] for item in data if 'applicant_id' in item]
            unique_applicant_ids = list(set(applicant_ids))



            combined_ids = [cid for cid in unique_applicant_ids + unique_student_ids if cid]

            existing_partner_student_ids = rec.env['res.partner'].search([('customer_id', 'in', combined_ids)])
            existing_ids_set = set(existing_partner_student_ids.mapped('customer_id'))


            new_student_ids = [sid for sid in unique_student_ids if sid not in existing_ids_set]



            created_count = 0
            for student_id in unique_applicant_ids:
                if created_count >= 1000:
                    break

                student_record = sms_applicant.filtered(lambda c: c.applicant_id == student_id)[0] if sms_applicant.filtered(lambda c: c.applicant_id == student_id) else sms_applicant.filtered(lambda c: c.student_id == student_id)[0]

                # Check if the student ID or applicant ID already exists in the partner records
                if student_record.applicant_id in existing_ids_set or student_record.student_id in existing_ids_set:
                    continue 


                vals ={
                    'name': (student_record.lname + ', ' + student_record.fname).upper(),
                    'active': True,

                    'is_po_vendor': False,
                    'state': 'done',

                    'supplier_rank': 0,
                    'customer_rank': 1,

                    'property_account_receivable_id': ar.id,
                    'property_account_payable_id': ap.id,
                }
                if student_record.student_id and student_record.applicant_id:
                    vals['customer_id'] = student_record.applicant_id
                    vals['is_student'] = True
                    vals['is_applicant'] = True
                    vals['student_id'] =  student_record.student_id
                    vals['applicant_id'] = student_record.applicant_id
                
                elif student_record.student_id and not student_record.applicant_id:
                    vals['customer_id'] = student_record.student_id
                    vals['is_student'] = True
                    vals['is_applicant'] = False
                    vals['student_id'] = student_record.student_id
                    vals['applicant_id'] = None

                elif not student_record.student_id and student_record.applicant_id:
                    vals['customer_id'] = student_record.applicant_id
                    vals['is_student'] = False
                    vals['is_applicant'] = True
                    vals['student_id'] = None
                    vals['applicant_id'] = student_record.applicant_id

                partner = rec.env['res.partner'].create(vals)

                created_count += 1


    def sync_create_student(self, stud_id=None):
        for rec in self:

            stud_id = rec.sms_create_stud_id
            cust_id = stud_id

            if not stud_id:
                sms_student = rec.env['sms.student'].search([])
                student_ids = sms_student.mapped('stud_id')
                unique_student_ids = list(set(student_ids))


                existing_partner_student_ids = rec.env['res.partner'].search([('customer_id', 'in', unique_student_ids)])
                existing_ids_set = set(existing_partner_student_ids.mapped('customer_id'))

                new_student_ids = [sid for sid in unique_student_ids if sid not in existing_ids_set]

                created_count = 0
                for student_id in new_student_ids:
                    if created_count >= 500:
                        break

                    student_record = sms_student.filtered(lambda c: c.stud_id == student_id)[0]

                    vals ={
                        'name': (student_record.lname + ', ' + student_record.fname).upper(),
                        'customer_id': student_record.stud_id,
                        'active': True,

                        'student_id': student_record.stud_id or None,

                        'is_po_vendor': False,
                        'is_student': True,
                        'is_applicant': False,
                        'state': 'done',

                        'supplier_rank': 0,
                        'customer_rank': 1,

                    
                    }

                
                    partner = rec.env['res.partner'].create(vals)
                    created_count += 1
                    self.env.cr.commit()
            else:
                rec.sync_create_customer_v2(cust_id)
                rec.sync_create_student_v2()
                

    def sync_create_student_v2(self, stud_id=None):
        for rec in self:
            stud_id = rec.sms_create_stud_id
            sms_student = rec.env['sms.student'].search([('stud_id', '=', stud_id)])
            student_ids = sms_student.mapped('stud_id')

            for student_id in student_ids:
                student_records = sms_student.filtered(lambda c: c.stud_id == student_id)

                student_record = student_records[0]
                vals = {
                    'name': (student_record.lname + ', ' + student_record.fname).upper(),
                    'customer_id': student_record.stud_id,
                    'active': True,
                    'student_id': student_record.stud_id or None,
                    'is_po_vendor': False,
                    'is_student': True,
                    'is_applicant': False,
                    'state': 'done',
                    'supplier_rank': 0,
                    'customer_rank': 1,
                }

                partner_customer = rec.env['res.partner'].search([('customer_id', '=', stud_id)])

                if not partner_customer:
                    partner = rec.env['res.partner'].create(vals)
                    self.env.cr.commit()
                else:
                    partner_customer.write(vals)

   
    def sync_create_customer(self, cust_id=None):
        ar = self.env['account.account'].search([('code', '=', '1020101000')], limit=1)
        ap = self.env['account.account'].search([('code', '=', '2010101000')], limit=1)

        for rec in self:
            sms_customers = rec.env['sms.invoice'].search([])
            customer_ids = sms_customers.mapped('customer_id')
            unique_customer_ids = list(set(customer_ids))

            for customer_id in unique_customer_ids:
                if cust_id:
                    customer_record = sms_customers.filtered(lambda c: c.customer_id == cust_id)[0]
                else:
                    customer_record = sms_customers.filtered(lambda c: c.customer_id == customer_id)[0]

                sms_applicant = rec.env['sms.applicant'].search([('student_id', '=', customer_record.customer_id)])

                student = False
                applicant = False

                if customer_record.customer_type == 'STUDENT':
                    student = True
                else:
                    applicant = True

                vals = {
                    'name': (customer_record.customer_name),
                    'customer_id': customer_record.customer_id,
                    'active': True,

                    'student_id': (sms_applicant.student_id if sms_applicant.student_id else customer_record.customer_id) or None,
                    'applicant_id': (sms_applicant.applicant_id if sms_applicant.applicant_id else customer_record.customer_id) or None,

                    'is_po_vendor': False,
                    'is_student': student,
                    'is_applicant': applicant,
                    'state': 'done',

                    'supplier_rank': 0,
                    'customer_rank': 1,

                    'property_account_receivable_id': ar.id,
                    'property_account_payable_id': ap.id,

                    'course': customer_record.course or None,
                    'year_level': customer_record.year_level or None,

                }


                partner_customer = rec.env['res.partner'].search([('customer_id', '=', customer_record.customer_id)])

                if not partner_customer:
                    partner = rec.env['res.partner'].create(vals)
                    self.env.cr.commit()
                else:
                    partner_customer.write(vals)

    def sync_create_customer_v2(self, cust_id=None):
        _logger.info('Starting sync_create_customer_v2 process')
        ar = self.env['account.account'].search([('code', '=', '1020101000')], limit=1)
        ap = self.env['account.account'].search([('code', '=', '2010101000')], limit=1)

        for rec in self:
            if cust_id:

                domain = [('customer_id', '=', cust_id)]

                # Check if at least one record exists with an email
                has_email = rec.env['sms.invoice'].search_count([('customer_id', '=', cust_id), ('sms_email', '!=', False)]) > 0

                # Add the email filter only if there is at least one record with an email
                if has_email:
                    domain.append(('sms_email', '!=', False))

                sms_customers = rec.env['sms.invoice'].search(domain, order="id desc", limit=1)

                customer_ids = sms_customers.mapped('customer_id')
                unique_customer_ids = list(set(customer_ids))
            else:
                sms_customers = rec.env['sms.invoice'].search([])
                customer_ids = sms_customers.mapped('customer_id')
                unique_customer_ids = list(set(customer_ids))

            for customer_id in unique_customer_ids:
                customer_record = sms_customers.filtered(lambda c: c.customer_id == customer_id)[0]

                vals = {
                    'name': (customer_record.customer_name),
                    'customer_id': customer_record.customer_id,
                    'active': True,

                    'student_id': (customer_record.customer_ref_id if customer_record.customer_ref_id else customer_record.customer_id) or None,
                    'applicant_id': ( customer_record.customer_id) or None,

                    'is_po_vendor': False,
                    'is_student': True,
                    'is_applicant': True,
                    'state': 'done',

                    'supplier_rank': 0,
                    'customer_rank': 1,

                    'property_account_receivable_id': ar.id,
                    'property_account_payable_id': ap.id,

                    'course': customer_record.course or None,
                    'year_level': customer_record.year_level or None,

                    'email': customer_record.sms_email or None,

                }
                _logger.debug('Processing customer record ID: %s', customer_record.id)
                _logger.debug('Customer values: %s', vals)

                partner_customer = rec.env['res.partner'].search([('customer_id', '=', customer_record.customer_id)], limit=1)

                if not partner_customer:
                    _logger.debug('Creating new partner for customer')
                    partner = rec.env['res.partner'].create(vals)
                    self.env.cr.commit()
                else:
                    _logger.debug('Partner already exists for customer')
                    _logger.debug('Customer SMS email: %s', customer_record.sms_email)
                    partner_customer.update({
                        'student_id': customer_record.customer_ref_id if customer_record.customer_ref_id else customer_record.customer_id,
                        'email': customer_record.sms_email or None
                    })

    def sync_create_customer_v3(self, cust_id=None):
        _logger.info('Starting sync_create_customer_v3 process')
        ar = self.env['account.account'].search([('code', '=', '1020101000')], limit=1)
        ap = self.env['account.account'].search([('code', '=', '2010101000')], limit=1)

        for rec in self:
            if cust_id:
                domain = [('customer_id', '=', cust_id)]

                # Check if at least one record exists with an email
                has_email = rec.env['sms.invoice'].search_count([('customer_id', '=', cust_id), ('sms_email', '!=', False)]) > 0
                has_student_id = rec.env['sms.invoice'].search_count([('customer_id', '=', cust_id), ('customer_ref_id', '!=', False)]) > 0

                # Add the email filter only if there is at least one record with an email
                if has_email:
                    domain.append(('sms_email', '!=', False))
                if has_student_id:
                    domain.append(('customer_ref_id', '!=', False))

                sms_customers = rec.env['sms.invoice'].search(domain, limit=1)

                customer_ids = sms_customers.mapped('customer_id')
                unique_customer_ids = list(set(customer_ids))
            else:
                sms_customers = rec.env['sms.invoice'].search([])
                customer_ids = sms_customers.mapped('customer_id')
                unique_customer_ids = list(set(customer_ids))

            for customer_id in unique_customer_ids:
                customer_record = sms_customers.filtered(lambda c: c.customer_id == customer_id)[0]


                vals = {
                    'name': (customer_record.customer_name),
                    'customer_id': customer_record.customer_id,
                    'active': True,

                    'student_id': (customer_record.customer_ref_id if customer_record.customer_ref_id else customer_record.customer_id) or None,
                    'applicant_id': ( customer_record.customer_id) or None,

                    'is_po_vendor': False,
                    'is_student': True,
                    'is_applicant': True,
                    'state': 'done',

                    'supplier_rank': 0,
                    'customer_rank': 1,

                    'property_account_receivable_id': ar.id,
                    'property_account_payable_id': ap.id,

                    'course': customer_record.course or None,
                    'year_level': customer_record.year_level or None,

                    'email': customer_record.sms_email or None,

                }
                _logger.debug('Processing customer record ID: %s', customer_record.id)

                partner_customer = rec.env['res.partner'].search([('customer_id', '=', customer_record.customer_id)], limit=1)

                if not partner_customer:
                    partner = rec.env['res.partner'].create(vals)
                    self.env.cr.commit()
                else:
                    partner_customer.update({
                        'student_id': customer_record.customer_ref_id if customer_record.customer_ref_id else customer_record.customer_id,
                        'email': customer_record.sms_email or None
                    })


    def sync_create_customer_for_portal(self, cust_id=None):
        _logger.info('Starting sync_create_customer_for_portal process')
        ar = self.env['account.account'].search([('code', '=', '1020101000')], limit=1)
        ap = self.env['account.account'].search([('code', '=', '2010101000')], limit=1)

        for rec in self:
            if cust_id:
                sms_customers = rec.env['sms.invoice'].search([('customer_id', '=', cust_id)])
                unique_customer_ids = list(set(sms_customers.mapped('customer_id')))

                if sms_customers:
                    _logger.debug('Found unique customer IDs: %s', unique_customer_ids)
                else:
                    _logger.debug('No SMS customers found, searching for existing partners')
                    partners = rec.env['res.partner'].search([('customer_id', '=', cust_id)], limit=1)
                    unique_partner_ids = list(set(partners.mapped('customer_id')))

            for customer_id in (unique_customer_ids if sms_customers else unique_partner_ids):
                if sms_customers:
                    customer_record = sms_customers.filtered(lambda c: c.customer_id == customer_id)
                    customer_name = customer_record[0].customer_name if customer_record else ''
                    course = customer_record[0].course if customer_record else ''
                else:
                    partner_record = rec.env['res.partner'].search([('customer_id', '=', customer_id)], limit=1)
                    customer_name = partner_record.name if partner_record else ''
                    course = partner_record.course if partner_record else ''

                vals = {
                    'name': customer_name,
                    'customer_id': customer_id,
                    'active': True,
                    'is_po_vendor': False,
                    'is_student': False,
                    'is_applicant': False,
                    'state': 'done',
                    'supplier_rank': 0,
                    'customer_rank': 1,
                    'property_account_receivable_id': ar.id,
                    'property_account_payable_id': ap.id,
                    'course': course,
                }
                _logger.debug('Partner values: %s', vals)


                partner_customer = rec.env['res.partner'].search([('customer_id', '=', customer_id)], limit=1)

                if not partner_customer:
                    _logger.debug('Creating new partner for portal access')
                    partner = rec.env['res.partner'].create(vals)
                    self.env.cr.commit()

                    # CREATION OF USER IN THE PORTAL
                    rec.create_customer_for_portal(cust_id)
                    self.env.cr.commit()
                else:
                    partner_customer.update({'customer_id' : (customer_id if customer_name else customer_id) or None})
                    self.env.cr.commit()

                    # CREATION OF USER IN THE PORTAL
                    _logger.debug('Partner already exists, updating portal access')
                    rec.create_customer_for_portal(cust_id)
                    self.env.cr.commit()
    
    def create_customer_for_portal(self, customer_id=None):
        for rec in self:
            partner_customer = rec.env['res.partner'].search([('customer_id', '=', customer_id)], limit=1)

            source_url = self.env['ir.config_parameter'].sudo().get_param('xml.rpc.remote.url')
            source_db = self.env['ir.config_parameter'].sudo().get_param('xml.rpc.remote.db')
            source_username = self.env['ir.config_parameter'].sudo().get_param('xml.rpc.remote.username')
            source_password = self.env['ir.config_parameter'].sudo().get_param('xml.rpc.remote.password')

            source_common = xmlrpc.client.ServerProxy(f'{source_url}/xmlrpc/2/common')
            source_uid = source_common.authenticate(source_db, source_username, source_password, {})

            domain = []
            source_models = xmlrpc.client.ServerProxy(f'{source_url}/xmlrpc/2/object')
            data = source_models.execute_kw(source_db, source_uid, source_password, 'res.company', 'sync_user', [False,partner_customer.id], {})

    def sync_customer_for_portal_cron(self):
        for rec in self.search([]):
            rec.create_customer_for_portal_cron()


    def create_customer_for_portal_cron(self):
        self.env.cr.execute("""
            SELECT id, customer_id 
            FROM res_partner 
            WHERE is_customer_portal = False 
            AND customer_id is not null
            LIMIT 100
        """)
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


                        

    def sync_create_products(self):
        sms_products = self.env['sms.product'].search([])
        unique_product_ids = sms_products.mapped('prod_id')
        products_without_account = []

        product_templates = self.env['product.template'].search([('prod_id', 'in', unique_product_ids)])
        product_template_dict = {template.prod_id: template for template in product_templates}

        for prod_id in unique_product_ids:
            product_template = product_template_dict.get(prod_id)           
            product_record = sms_products.filtered(lambda c: c.prod_id == prod_id).ensure_one()
            product_temp = self.env['product.template'].search([('prod_id', '=', product_record.prod_id)])
            account = self.env['account.account'].search([('code', '=', product_record.account_code)])

            if account:
                vals = {
                    'property_account_income_id': account.id,
                    'name': product_record.prod_desc,
                    'default_code': product_record.prod_name,
                    'description': product_record.prod_desc,
                    'detailed_type': 'service',
                    'type': 'service',
                    'sale_ok': True,
                    'purchase_ok': True,
                    'uom_id': 26,
                    'purchase_method': 'receive',
                    'prod_id': int(product_record.prod_id),
                    'prod_type_id': int(product_record.prod_type_id),
                    'active': True,
                }

                if not product_temp:
                    prod = self.env['product.template'].create(vals)
                else:
                    product_temp.write(vals)
                    
            if not account:
                products_without_account.append(product_record.prod_name)


        if products_without_account:
            action = {
                'name': 'Products Without Account',
                'type': 'ir.actions.act_window',
                'res_model': 'product.account.check.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'product_names': '\n'.join(products_without_account),
                }
            }

            
            return action
    
    def sync_create_application_invoices(self):
        # sms_customers = self.env['sms.invoice'].search([('inv_type_desc', '=', 'ADMISSION ENTRANCE EXAM')])
        sms_customers = self.env['sms.invoice'].search([('inv_type_desc', '=', 'ADMISSION FEE')])
        invoice_ids = sms_customers.mapped('invoice_id')
        unique_invoice_ids = list(set(invoice_ids))

        for invoice_id in unique_invoice_ids:
            invoice_record = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)[0]
            line_ids = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)

            partner_customer = self.env['res.partner'].search([('customer_id', '=', invoice_record.customer_id)])

            invoice_lines = []
            for line in line_ids:
                product_temp = self.env['product.template'].search([('prod_id', '=', line.prod_id)])
                product = self.env['product.product'].search([('product_tmpl_id', '=', product_temp.id)])

                invoice_line = {
                    'product_id': product.id,
                    'quantity': line.qty,
                    'product_uom_id': product_temp.uom_id.id,
                    'price_unit': line.unit_price,
                }
                invoice_lines.append((0, 0, invoice_line))

            invoice = {
                'partner_id': partner_customer.id,
                'invoice_ref_no': invoice_record.invoice_ref_no,
                'inv_type_desc': invoice_record.inv_type_desc,
                'invoice_date': invoice_record.invoice_date,
                'invoice_date_due': invoice_record.due_date,
                'move_type': 'out_invoice',
                'state': 'draft',

                'invoice_line_ids': invoice_lines,
                'course': invoice_record.course,
                'year': invoice_record.year_level,
                'school_year': invoice_record.school_year,
                'term': invoice_record.term,
                'is_adjusted': False,
            }


            account = self.env['account.move'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no)])

            if not account:
                inv = self.env['account.move'].create(invoice)
                inv.action_post()
            else:
                pass
            
    def sync_create_application(self):
        # sms_customers = self.env['sms.invoice'].search([('inv_type_desc', '=', 'ADMISSION ENTRANCE EXAM')])
        sms_customers = self.env['sms.invoice'].search([('inv_type_desc', '=', 'ADMISSION FEE')])
        invoice_ids = sms_customers.mapped('invoice_id')
        unique_invoice_ids = list(set(invoice_ids))

        for invoice_id in unique_invoice_ids:
            invoice_records = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)
            line_ids = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)


            invoice_ids = []  # Reset invoice_ids for each invoice_record
            for invoice_record in invoice_records:
                
                for line in line_ids:
                    invoice = self.env['account.move'].search([('invoice_ref_no', '=', line.invoice_ref_no)])[0]

                    invoice_line = {
                        'name': invoice.name,
                        'date': invoice.invoice_date,
                        'amount': invoice.amount_total,
                        'status': invoice.state,
                    }
                    invoice_ids.append((0, 0, invoice_line))

                    existing_record = self.env['school.application'].search([('partner_id', '=', invoice.partner_id.id)])

                # Move outside the inner loop
                vals = {
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'account_id': None,
                    'last_name': invoice_record.l_name,
                    'partner_id': invoice.partner_id.id,
                    'first_name': invoice_record.f_name,
                    'middle_name': invoice_record.m_name,
                    'suffix': invoice_record.suffix,
                    'transaction_id': invoice_record.inv_type,
                    'shool_year': invoice_record.school_year,
                    'semester': invoice_record.term,
                    'year_level': invoice_record.year_level,
                    'course': invoice_record.course,
                    'wbas_create_date': None,
                    'payment_terms': invoice_record.pay_term,
                    'invoice_ids': invoice_ids  # Assign the correct invoice_ids list here
                }


                if not existing_record:
                    self.env['school.application'].create(vals)
                else:
                    existing_invoice_names = set(existing_record.mapped('invoice_ids.name'))
                    new_lines = [line for line in invoice_ids if line[2]['name'] not in existing_invoice_names]
                    if new_lines:
                        existing_record.write({'invoice_ids': existing_record.invoice_ids + new_lines})
                        # existing_record.write({'invoice_ids': [(0, 0, line_data) for line_data in new_lines]})

                    else:
                        _logger.debug('No new lines to write for record: %s', existing_record)

    def sync_create_reservation(self, inv_id=None):

        sms_customers = self.env['sms.invoice'].search([('inv_type_desc', '=', 'ADMISSION CONFIRMATION'),  ('invoice_id', '=', inv_id)])
        if sms_customers:

            detail_ids = []
            for customer in sms_customers:

                inv_pays = ''
                if [customer.invoice_pay_id][0]:
                    inv_pays = ([customer.invoice_pay_id][0].strip('()').split(','))

                detail_line = {
                    'date': customer.invoice_date.strftime('%Y-%m-%d'),
                    'details': customer.prod_desc,
                    'amount': customer.amount,
                    'status': 'draft'
                }
                detail_ids.append((0, 0, detail_line))

                partner = self.env['res.partner'].search([('customer_id', '=', customer.customer_id)])

            vals = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'account_id': None,
                'last_name': customer.l_name,
                'partner_id': partner.id,
                'first_name': customer.f_name,
                'middle_name': customer.m_name,
                'suffix': customer.suffix,
                'transaction_ref': customer.invoice_ref_no,
                'shool_year': customer.school_year,
                'semester': customer.term,
                'year_level': customer.year_level,
                'course': customer.course,
                'wbas_create_date': None,
                'detail_ids': detail_ids,
                'invoice_pay_id': inv_pays[0] or None,
            }


            existing_record = self.env['school.reservation'].search([('transaction_ref', '=', customer.invoice_ref_no)])

            if not existing_record:
                reservation = self.env['school.reservation'].create(vals)
            else:
                pass

    def sync_create_reservation_invoices(self):
        _logger.info('Processing reservation invoices')

    def sync_create_assessment_invoices(self):
        try:
            sms_customers = self.env['sms.invoice'].search([('inv_type_desc', '=', 'ENROLLMENT ASSESSMENT')])
            invoice_ids = sms_customers.mapped('invoice_id')
            unique_invoice_ids = list(set(invoice_ids))

            # Initialize a counter for created records
            created_records = 0
            
            for invoice_id in unique_invoice_ids:
                invoice_record = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)[0]
                line_ids = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)

                account_move = self.env['account.move'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no), ('move_type','=','out_invoice')])
                if account_move:
                    # Skip this invoice_id as invoices have already been created for it
                    continue

                partner_customer = self.env['res.partner'].search([('customer_id', '=', invoice_record.customer_id)])

                # Determine the pay term
                pay_term = int(invoice_record.pay_term)
                first_pay = ''
                inv_pays = ''
                # Calculate the split percentages based on the pay term
                if pay_term == 4:
                    split_percentages = [
                        invoice_record.due_percent / 100,
                        invoice_record.due_percent2 / 100,
                        invoice_record.due_percent3 / 100,
                        invoice_record.due_percent4 / 100,
                    ]
                    due_dates = [
                        invoice_record.due_date,
                        invoice_record.due_date2,
                        invoice_record.due_date3,
                        invoice_record.due_date4,
                    ]
                    first_pay = [True, False, False, False]
                    if [invoice_record.invoice_pay_id][0]:
                        inv_pays = ([invoice_record.invoice_pay_id][0].strip('()').split(','))
                    remarks = ['First Payment', None, None, None]
                
                elif pay_term == 3:
                    split_percentages = [
                        invoice_record.due_percent / 100,
                        invoice_record.due_percent2 / 100,
                        invoice_record.due_percent3 / 100
                    ]
                    due_dates = [
                        invoice_record.due_date,
                        invoice_record.due_date2,
                        invoice_record.due_date3
                    ]
                    first_pay = [True, False, False]
                    if [invoice_record.invoice_pay_id][0]:
                        inv_pays = ([invoice_record.invoice_pay_id][0].strip('()').split(','))
                    remarks = ['First Payment', None, None]

                elif pay_term == 2:
                    split_percentages = [
                        invoice_record.due_percent / 100,
                        invoice_record.due_percent2 / 100
                    ]
                    due_dates = [
                        invoice_record.due_date,
                        invoice_record.due_date2
                    ]
                    first_pay = [True, False]
                    if [invoice_record.invoice_pay_id][0]:
                        inv_pays = ([invoice_record.invoice_pay_id][0].strip('()').split(','))
                    remarks = ['First Payment', None]

                elif pay_term == 1:
                    split_percentages = [1.0]
                    due_dates = [invoice_record.due_date]
                    first_pay = [True]
                    if [invoice_record.invoice_pay_id][0]:
                        inv_pays = ([invoice_record.invoice_pay_id][0].strip('()').split(','))
                    remarks = ['First Payment']
                else:
                    split_percentages = [1.0]
                    due_dates = [invoice_record.due_date]
                    first_pay = [True]
                    if [invoice_record.invoice_pay_id][0]:
                        inv_pays = ([invoice_record.invoice_pay_id][0].strip('()').split(','))
                    remarks = ['First Payment']

                total_quantity = sum(line.qty for line in line_ids)

                for index, (percentage, due_date) in enumerate(zip(split_percentages, due_dates)):
                    
                    price_unit = 0
                    invoice_lines = []
                    for line in line_ids:
                        if line.invoice_adj_id == 0:
                            product_temp = self.env['product.template'].search([('prod_id', '=', line.prod_id)])
                            product = self.env['product.product'].search([('product_tmpl_id', '=', product_temp.id)])

                            # if index == len(split_percentages) - 1:
                            #     # Last index: calculate price unit differently
                            #     price_unit = line.unit_price - (line.unit_price * ((invoice_record.due_percent + invoice_record.due_percent3) / 100))

                            # elif invoice_record.due_percent == 50:
                            #     price_unit = line.unit_price - (line.unit_price * ((invoice_record.due_percent2) / 100))

                            # elif invoice_record.due_percent == 100:
                            #     price_unit = line.unit_price * percentage
                            
                            # else:
                            #     # Normal calculation for other indices
                            #     price_unit = line.unit_price * percentage


                            if index == len(split_percentages) - 1:
                                if pay_term == 1:
                                    price_unit = line.unit_price * percentage

                                elif pay_term == 2:
                                    price_unit = line.unit_price - (line.unit_price * ((invoice_record.due_percent2) / 100))

                                elif pay_term == 3:
                                    price_unit = line.unit_price - (line.unit_price * ((invoice_record.due_percent + invoice_record.due_percent3) / 100))

                                elif pay_term == 4:
                                    price_unit = line.unit_price - (line.unit_price * ((invoice_record.due_percent + invoice_record.due_percent2 + invoice_record.due_percent4) / 100))
                            else:
                                price_unit = line.unit_price * percentage
                            

                            invoice_line = {
                                'product_id': product.id,
                                'quantity': line.qty,
                                'product_uom_id': product_temp.uom_id.id,
                                'price_unit': price_unit
                            }

                            invoice_lines.append((0, 0, invoice_line))

                        invoice_record.is_sync = True

                    if not invoice_lines:
                        # Skip creating the invoice if no invoice lines meet the condition
                        continue

                    # Set the invoice year based on the invoice date or use the current year
                    invoice_year = invoice_record.invoice_date.year if invoice_record.invoice_date else datetime.now().year
                    # Get the next number from the custom sequence
                    next_invoice_number = self.env['ir.sequence'].next_by_code('invoice_sequence')
                    # Modify the name by appending the invoice year
                    if next_invoice_number:
                        next_invoice_number = f'INV/{invoice_year}/{next_invoice_number.split("/")[-1]}'

                    invoice = {
                        'partner_id': partner_customer.id,
                        'invoice_ref_no': invoice_record.invoice_ref_no,
                        'inv_type_desc': invoice_record.inv_type_desc,
                        'invoice_date': invoice_record.invoice_date,
                        'invoice_date_due': due_date,
                        'move_type': 'out_invoice',
                        'state': 'draft',
                        # 'name': next_invoice_number,
                        'invoice_line_ids': invoice_lines,
                        'is_from_sync': True,
                        'is_first_payment': first_pay[index] or False,
                        'inv_pay_id': inv_pays[index] or None,
                        'student_id': invoice_record.customer_id if (invoice_record.customer_type == 'STUDENT') else None,
                        'applicant_id': invoice_record.customer_id if (invoice_record.customer_type == 'APPLICANT') else None,
                        'api_remarks': remarks[index] or None,

                        'course': invoice_record.course,
                        'year': invoice_record.year_level,
                        'school_year': invoice_record.school_year,
                        'term': invoice_record.term,
                        'is_adjusted': False,
                    }

                    inv = self.env['account.move'].create(invoice)
                    inv.action_post()

                    # Increment the created records counter
                    created_records += 1

                    # Check if the limit has been reached
                    if created_records >= 100:
                        break

                # Check if the limit has been reached after each invoice iteration
                if created_records >= 100:
                    break

        except Exception as error:
            _logger.error('Error in sync_create_assessment_invoices: %s', error)
                
    def sync_create_assetments(self):

        sms_customers = self.env['sms.invoice'].search([('inv_type_desc', '=', 'ENROLLMENT ASSESSMENT')])
        invoice_ids = sms_customers.mapped('invoice_id')
        unique_invoice_ids = list(set(invoice_ids))

        for invoice_id in unique_invoice_ids:
            invoice_record = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)[0]


            invoice_ids = []
            invoices = self.env['account.move'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no)])

            for invoice in invoices:  

                                invoice_line = {
                    'name': invoice.name,
                    'date': invoice.invoice_date,
                    'details': invoice.invoice_ref_no,
                    'amount': invoice.amount_total,
                    'status': invoice.state,
                }
                partner_id = invoice.partner_id.id
                invoice_ids.append((0, 0, invoice_line))


            vals = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'account_id': None,
                'last_name': invoice_record.l_name,
                'partner_id': partner_id,
                'first_name': invoice_record.f_name,
                'middle_name': invoice_record.m_name,
                'suffix': invoice_record.suffix,
                'transaction_id': invoice_record.inv_type,
                'transaction_ref': invoice_record.invoice_ref_no,
                'shool_year': invoice_record.school_year,
                'semester': invoice_record.term,
                'year_level': invoice_record.year_level,
                'course': invoice_record.course,
                'wbas_create_date': None,
                'payment_terms': invoice_record.pay_term,
                'invoice_ids': invoice_ids,
            }


            existing_record = self.env['school.assessment'].search([('transaction_ref', '=', invoice_record.invoice_ref_no)])

            if not existing_record:
                                self.env['school.assessment'].create(vals)
            else:
                self.env['school.assessment'].write(vals)

    def sync_create_all(self):
        self.sync_create_application_invoices()
        self.sync_create_application()

        self.sync_create_assessment_invoices()
        self.sync_create_assetments()

        self.sync_create_reservation_invoices()
        self.sync_create_reservation()

    def sync_all_applicant(self):
        for rec in self:
            rec.sync_create_customer()
            rec.sync_create_application_invoices()
            rec.sync_create_application()

    def sync_all_assessment(self):
        for rec in self:
            rec.sync_create_customer()
            rec.sync_create_assessment_invoices()
            rec.sync_create_assetments()


    def sync_all_reservation(self):
        for rec in self:
            rec.sync_create_customer()
            rec.sync_create_reservation_invoices()
            rec.sync_create_reservation()

            
    def create_ajustment(self):
        
        
        try:
            sms_customers = self.env['sms.invoice'].search([('inv_type_desc', '=', 'ENROLLMENT ASSESSMENT'),('is_adjustment_created', '=', False)])
            invoice_ids = sms_customers.mapped('invoice_id')
            unique_invoice_ids = list(set(invoice_ids))
            
            created_records = 0
            inv = False
            cred = False

            for invoice_id in unique_invoice_ids:
                sms_invoice_max_adj_no = self.env['sms.invoice'].search([('invoice_id','=',invoice_id)], order='invoice_adj_no desc', limit=1).invoice_adj_no
                for adjustment_no in range(sms_invoice_max_adj_no):
                    if created_records >= 100:
                        break

                    adjustment_no += 1

                    invoice_record = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)[0]
                    line_ids = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)

                    # Create sets to store the values from each loop
                    adjustment_set = set()
                    invoice_set = set()
                    
                    count_invoice_lines = 0
                    adjusted_lines_count = {}

                    for line in line_ids:
                        line.is_adjustment_created = True
                        if line.invoice_adj_no == adjustment_no:
 
                            # Store the values from the first loop in the adjustment_set
                            for adjustment in line_ids:

                                if adjustment.invoice_adj_id != 0 and adjustment.invoice_adj_no == line.invoice_adj_no:
                                    adjustment_set.add((adjustment.prod_id, 
                                                        adjustment.invoice_ref_no, 
                                                        adjustment.amount, 
                                                        adjustment.invoice_id,
                                                        ))

                            # Store the values from the second loop in the invoice_set
                            for invoice in line_ids:
                                if line.invoice_adj_no == 1:
                                    if invoice.invoice_adj_id == 0:
                                        invoice_set.add((invoice.prod_id, 
                                                        invoice.invoice_ref_no, 
                                                        invoice.amount, 
                                                        invoice.invoice_id,
                                                        ))
                                        
                                elif line.invoice_adj_no > 1:
                                    if invoice.invoice_adj_id != 0 and invoice.invoice_adj_no == (adjustment_no-1):
                                        invoice_set.add((invoice.prod_id, 
                                                            invoice.invoice_ref_no, 
                                                            invoice.amount, 
                                                            invoice.invoice_id,
                                                            ))
                            count_invoice_lines += 1

                        else:

                            if line.invoice_adj_no in adjusted_lines_count:
                                adjusted_lines_count[line.invoice_adj_no] += 1
                            else:
                                adjusted_lines_count[line.invoice_adj_no] = 1
                            
                                    
                    # Find the unmatched data by subtracting one set from the other
                    unmatched_data = (adjustment_set - invoice_set)
                    unmatched_data2 = (invoice_set - adjustment_set) 

                    data = list({'prod_id': item[0],
                                'invoice_ref_no': item[1],
                                'amount': item[2],
                                'invoice_id,': item[3],
                                } 
                                for item in unmatched_data)
                    
                    data2 = list({'prod_id': item[0],
                                'invoice_ref_no': item[1],
                                'amount': item[2],
                                'invoice_id,': item[3],
                                } 
                                for item in unmatched_data2)

                    for adj_no, count in adjusted_lines_count.items():
                        if count > count_invoice_lines:
                            # Compare and subtract amounts if conditions are met
                            for item1 in data:
                                found_equal_prod_id = False
                                for item2 in data2:
                                    if item1['prod_id'] == item2['prod_id']:
                                        found_equal_prod_id = True
                                        if item2['amount'] < item1['amount']:
                                            item2['amount'] = (item1['amount'] - item2['amount'])

                                        elif item2['amount'] > item1['amount']:
                                            item2['amount'] = (item2['amount'] - item1['amount'])

                                        break
                                if not found_equal_prod_id:
                                    data2.append(item1)

                        elif count < count_invoice_lines:
                            # Compare and subtract amounts if conditions are met
                            for item1 in data:
                                found_equal_prod_id = False
                                for item2 in data2:
                                    if item1['prod_id'] == item2['prod_id']:
                                        found_equal_prod_id = True
                                        if item2['amount'] > item1['amount']:
                                            item2['amount'] = (item2['amount'] - item1['amount'])

                                        elif item2['amount'] < item1['amount']:
                                            item2['amount'] = (item1['amount'] - item2['amount'])
                                            
                                        break
                                if not found_equal_prod_id:
                                    item1_copy = item1.copy()  # Create a copy to avoid modifying the original item1
                                    item1_copy['amount'] = -item1_copy['amount']  # Make the amount negative
                                    data2.append(item1_copy)
                                    # data2.append(item1)

                        elif count == count_invoice_lines:
                            # Compare and subtract amounts if conditions are met
                            for item1 in data:
                                found_equal_prod_id = False
                                for item2 in data2:
                                    if item1['prod_id'] == item2['prod_id']:
                                        found_equal_prod_id = True
                                        if item2['amount'] < item1['amount']:
                                            item2['amount'] = (item1['amount'] - item2['amount'])

                                        elif item2['amount'] > item1['amount']:
                                            item2['amount'] = (item2['amount'] - item1['amount'])

                                        break
                                if not found_equal_prod_id:
                                    data2.append(item1)

                        else:
        
                            for item1 in data:
                                found_equal_prod_id = False
                                for item2 in data2:
                                    if item1['prod_id'] == item2['prod_id']:
                                        found_equal_prod_id = True
                                        if item2['amount'] < item1['amount']:
                                            item2['amount'] = (item1['amount'] - item2['amount'])

                                        elif item2['amount'] > item1['amount']:
                                            item2['amount'] = (item2['amount'] - item1['amount'])

                                        else:
                                            item2['amount'] = (item2['amount'] - item1['amount'])
                                        break

                                if not found_equal_prod_id:
                                    data2.append(item1)

                    sms_data = self.env['sms.invoice'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no), ('invoice_adj_no', '=', adjustment_no)], limit=1)
                    sms_adjustment_date = self.env['sms.invoice'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no),  ('invoice_adj_no', '=', adjustment_no), ('adjust_date', '=', True)], limit=1)
                    partner_customer = self.env['res.partner'].search([('customer_id', '=', invoice_record.customer_id)])

                    if invoice_record.total_amount > sms_data.total_adj_amount:
                        credit_lines = []
                        for item in data2:
                            product_temp = self.env['product.template'].search([('prod_id', '=', int(item['prod_id']))])
                            product = self.env['product.product'].search([('product_tmpl_id', '=', product_temp.id)])

                            credit_line = {
                                'product_id': product.id,
                                'quantity': 1,
                                'product_uom_id': product_temp.uom_id.id,
                                'price_unit': round(item['amount'], 2),
                            }
                            credit_lines.append((0, 0, credit_line))
 

                        if not credit_lines:
                            # Skip creating the invoice if no invoice lines meet the condition
                            continue

                        credit = {
                            'partner_id': partner_customer.id,
                            'invoice_ref_no': invoice_record.invoice_ref_no,
                            'inv_type_desc': invoice_record.inv_type_desc,
                            'invoice_date': sms_adjustment_date.invoice_date or invoice_record.invoice_date,
                            'invoice_date_due': invoice_record.due_date2 or invoice_record.due_date,
                            'move_type': 'out_refund',
                            'state': 'draft',
                            # 'name': next_invoice_number,
                            'invoice_line_ids': credit_lines,

                            'course': invoice_record.course,
                            'year': invoice_record.year_level,
                            'school_year': invoice_record.school_year,
                            'term': invoice_record.term,
                            'is_adjusted': True,
                        }

                        cred = self.env['account.move'].create(credit)
                        cred.action_post()

                        invoice_to_reconcile = self.env['account.move'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no), ('invoice_date_due','=', invoice_record.due_date2), ('is_adjusted','=',False)])
                        
                        if invoice_to_reconcile:
                            (cred + invoice_to_reconcile).line_ids.filtered(lambda line: line.account_id.reconcile).reconcile()

                        created_records += 1

                        invoice_record.is_sync = True

                    else:
                        invoice_lines = []
                        for item in data2:

                            product_temp = self.env['product.template'].search([('prod_id', '=', int(item['prod_id']))])
                            product = self.env['product.product'].search([('product_tmpl_id', '=', product_temp.id)])

                            invoice_line = {
                                'product_id': product.id,
                                'quantity': 1,
                                'product_uom_id': product_temp.uom_id.id,
                                'price_unit': abs(round(item['amount'], 2)),
                            }
                            invoice_lines.append((0, 0, invoice_line))
 

                        if not invoice_lines:
                            # Skip creating the invoice if no invoice lines meet the condition
                            continue
                        
                        invoice = {
                            'partner_id': partner_customer.id,
                            'invoice_ref_no': invoice_record.invoice_ref_no,
                            'inv_type_desc': invoice_record.inv_type_desc,
                            'invoice_date': sms_adjustment_date.invoice_date or invoice_record.invoice_date, 
                            'invoice_date_due': invoice_record.due_date2 or invoice_record.due_date,
                            'move_type': 'out_invoice',
                            'state': 'draft',
                            # 'name': next_invoice_number,
                            'invoice_line_ids': invoice_lines,

                            'course': invoice_record.course,
                            'year': invoice_record.year_level,
                            'school_year': invoice_record.school_year,
                            'term': invoice_record.term,
                            'is_adjusted': True,
                        }
                        
                        inv = self.env['account.move'].create(invoice)
                        inv.action_post()
                        

                        created_records += 1

                        invoice_record.is_sync = True
                        self.env.cr.commit()

        except Exception as error:
            _logger.error('Error in sync_create_assessment_invoices: %s', error)

    
    def create_ajustment_partner(self, cust_id=None):
        
        
        try:
            sms_customers = self.env['sms.invoice'].search([('inv_type_desc', '=', 'ENROLLMENT ASSESSMENT'),('is_adjustment_created', '=', False), ('customer_id','=', int(cust_id))])
            invoice_ids = sms_customers.mapped('invoice_id')
            unique_invoice_ids = list(set(invoice_ids))
            
            created_records = 0
            inv = False
            cred = False

            for invoice_id in unique_invoice_ids:
                sms_invoice_max_adj_no = self.env['sms.invoice'].search([('invoice_id','=',invoice_id)], order='invoice_adj_no desc', limit=1).invoice_adj_no
                for adjustment_no in range(sms_invoice_max_adj_no):
                    if created_records >= 100:
                        break

                    adjustment_no += 1

                    invoice_record = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)[0]
                    line_ids = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)

                    # Create sets to store the values from each loop
                    adjustment_set = set()
                    invoice_set = set()
                    
                    count_invoice_lines = 0
                    adjusted_lines_count = {}

                    for line in line_ids:
                        line.is_adjustment_created = True
                        if line.invoice_adj_no == adjustment_no:
 
                            # Store the values from the first loop in the adjustment_set
                            for adjustment in line_ids:

                                if adjustment.invoice_adj_id != 0 and adjustment.invoice_adj_no == line.invoice_adj_no:
                                    adjustment_set.add((adjustment.prod_id, 
                                                        adjustment.invoice_ref_no, 
                                                        adjustment.amount, 
                                                        adjustment.invoice_id,
                                                        ))

                            # Store the values from the second loop in the invoice_set
                            for invoice in line_ids:
                                if line.invoice_adj_no == 1:
                                    if invoice.invoice_adj_id == 0:
                                        invoice_set.add((invoice.prod_id, 
                                                        invoice.invoice_ref_no, 
                                                        invoice.amount, 
                                                        invoice.invoice_id,
                                                        ))
                                        
                                elif line.invoice_adj_no > 1:
                                    if invoice.invoice_adj_id != 0 and invoice.invoice_adj_no == (adjustment_no-1):
                                        invoice_set.add((invoice.prod_id, 
                                                            invoice.invoice_ref_no, 
                                                            invoice.amount, 
                                                            invoice.invoice_id,
                                                            ))
                            count_invoice_lines += 1

                        else:

                            if line.invoice_adj_no in adjusted_lines_count:
                                adjusted_lines_count[line.invoice_adj_no] += 1
                            else:
                                adjusted_lines_count[line.invoice_adj_no] = 1
                            
                                    
                    # Find the unmatched data by subtracting one set from the other
                    unmatched_data = (adjustment_set - invoice_set)
                    unmatched_data2 = (invoice_set - adjustment_set) 

                    data = list({'prod_id': item[0],
                                'invoice_ref_no': item[1],
                                'amount': item[2],
                                'invoice_id,': item[3],
                                } 
                                for item in unmatched_data)
                    
                    data2 = list({'prod_id': item[0],
                                'invoice_ref_no': item[1],
                                'amount': item[2],
                                'invoice_id,': item[3],
                                } 
                                for item in unmatched_data2)

                    for adj_no, count in adjusted_lines_count.items():
                        if count > count_invoice_lines:
                            # Compare and subtract amounts if conditions are met
                            for item1 in data:
                                found_equal_prod_id = False
                                for item2 in data2:
                                    if item1['prod_id'] == item2['prod_id']:
                                        found_equal_prod_id = True
                                        if item2['amount'] < item1['amount']:
                                            item2['amount'] = (item1['amount'] - item2['amount'])

                                        elif item2['amount'] > item1['amount']:
                                            item2['amount'] = (item2['amount'] - item1['amount'])

                                        break
                                if not found_equal_prod_id:
                                    data2.append(item1)

                        elif count < count_invoice_lines:
                            # Compare and subtract amounts if conditions are met
                            for item1 in data:
                                found_equal_prod_id = False
                                for item2 in data2:
                                    if item1['prod_id'] == item2['prod_id']:
                                        found_equal_prod_id = True
                                        if item2['amount'] > item1['amount']:
                                            item2['amount'] = (item2['amount'] - item1['amount'])

                                        elif item2['amount'] < item1['amount']:
                                            item2['amount'] = (item1['amount'] - item2['amount'])
                                            
                                        break
                                if not found_equal_prod_id:
                                    item1_copy = item1.copy()  # Create a copy to avoid modifying the original item1
                                    item1_copy['amount'] = -item1_copy['amount']  # Make the amount negative
                                    data2.append(item1_copy)
                                    # data2.append(item1)

                        elif count == count_invoice_lines:
                            # Compare and subtract amounts if conditions are met
                            for item1 in data:
                                found_equal_prod_id = False
                                for item2 in data2:
                                    if item1['prod_id'] == item2['prod_id']:
                                        found_equal_prod_id = True
                                        if item2['amount'] < item1['amount']:
                                            item2['amount'] = (item1['amount'] - item2['amount'])

                                        elif item2['amount'] > item1['amount']:
                                            item2['amount'] = (item2['amount'] - item1['amount'])

                                        break
                                if not found_equal_prod_id:
                                    data2.append(item1)

                        else:
        
                            for item1 in data:
                                found_equal_prod_id = False
                                for item2 in data2:
                                    if item1['prod_id'] == item2['prod_id']:
                                        found_equal_prod_id = True
                                        if item2['amount'] < item1['amount']:
                                            item2['amount'] = (item1['amount'] - item2['amount'])

                                        elif item2['amount'] > item1['amount']:
                                            item2['amount'] = (item2['amount'] - item1['amount'])

                                        else:
                                            item2['amount'] = (item2['amount'] - item1['amount'])
                                        break

                                if not found_equal_prod_id:
                                    data2.append(item1)
                    
                    sms_data = self.env['sms.invoice'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no), ('invoice_adj_no', '=', adjustment_no)], limit=1)
                    sms_adjustment_date = self.env['sms.invoice'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no),  ('invoice_adj_no', '=', adjustment_no), ('adjust_date', '!=', False)], limit=1)
                    partner_customer = self.env['res.partner'].search([('customer_id', '=', invoice_record.customer_id)])

                    if invoice_record.total_amount > sms_data.total_adj_amount:
                        credit_lines = []
                        for item in data2:
                            product_temp = self.env['product.template'].search([('prod_id', '=', int(item['prod_id']))])
                            product = self.env['product.product'].search([('product_tmpl_id', '=', product_temp.id)])

                            credit_line = {
                                'product_id': product.id,
                                'quantity': 1,
                                'product_uom_id': product_temp.uom_id.id,
                                'price_unit': round(item['amount'], 2),
                            }
                            credit_lines.append((0, 0, credit_line))
 

                        if not credit_lines:
                            # Skip creating the invoice if no invoice lines meet the condition
                            continue

                        credit = {
                            'partner_id': partner_customer.id,
                            'invoice_ref_no': invoice_record.invoice_ref_no,
                            'inv_type_desc': invoice_record.inv_type_desc,
                            'invoice_date': sms_adjustment_date.adjust_date or invoice_record.invoice_date,
                            'invoice_date_due': invoice_record.due_date2 or invoice_record.due_date,
                            'move_type': 'out_refund',
                            'state': 'draft',
                            # 'name': next_invoice_number,
                            'invoice_line_ids': credit_lines,

                            'course': invoice_record.course,
                            'year': invoice_record.year_level,
                            'school_year': invoice_record.school_year,
                            'term': invoice_record.term,
                            'is_adjusted': True,
                        }

                        cred = self.env['account.move'].create(credit)
                        cred.action_post()

                        invoice_to_reconcile = self.env['account.move'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no), ('invoice_date_due','=', invoice_record.due_date2), ('is_adjusted','=',False)])
                        
                        if invoice_to_reconcile:
                            (cred + invoice_to_reconcile).line_ids.filtered(lambda line: line.account_id.reconcile).reconcile()

                        created_records += 1

                        invoice_record.is_sync = True

                    else:
                        invoice_lines = []
                        for item in data2:

                            product_temp = self.env['product.template'].search([('prod_id', '=', int(item['prod_id']))])
                            product = self.env['product.product'].search([('product_tmpl_id', '=', product_temp.id)])

                            invoice_line = {
                                'product_id': product.id,
                                'quantity': 1,
                                'product_uom_id': product_temp.uom_id.id,
                                'price_unit': abs(round(item['amount'], 2)),
                            }
                            invoice_lines.append((0, 0, invoice_line))
 

                        if not invoice_lines:
                            # Skip creating the invoice if no invoice lines meet the condition
                            continue
                        
                        invoice = {
                            'partner_id': partner_customer.id,
                            'invoice_ref_no': invoice_record.invoice_ref_no,
                            'inv_type_desc': invoice_record.inv_type_desc,
                            'invoice_date': sms_adjustment_date.invoice_date or invoice_record.invoice_date, 
                            'invoice_date_due': invoice_record.due_date2 or invoice_record.due_date,
                            'move_type': 'out_invoice',
                            'state': 'draft',
                            # 'name': next_invoice_number,
                            'invoice_line_ids': invoice_lines,

                            'course': invoice_record.course,
                            'year': invoice_record.year_level,
                            'school_year': invoice_record.school_year,
                            'term': invoice_record.term,
                            'is_adjusted': True,
                        }
                        
                        inv = self.env['account.move'].create(invoice)
                        inv.action_post()
                        

                        created_records += 1

                        invoice_record.is_sync = True
                        self.env.cr.commit()

        except Exception as error:
            _logger.error('Error in sync_create_assessment_invoices: %s', error)

    def create_ajustment_partner_v2(self, cust_id=None):
        
        
        try:
            sms_customers = self.env['sms.invoice'].search([('inv_type_desc', '=', 'ENROLLMENT ASSESSMENT'),('is_adjustment_created', '=', False), ('customer_id','=', int(cust_id))])
            invoice_ids = sms_customers.mapped('invoice_id')
            unique_invoice_ids = list(set(invoice_ids))
            
            created_records = 0
            inv = False
            cred = False

            for invoice_id in unique_invoice_ids:
                sms_invoice_max_adj_no = self.env['sms.invoice'].search([('invoice_id','=',invoice_id)], order='invoice_adj_no desc', limit=1).invoice_adj_no
                for adjustment_no in range(sms_invoice_max_adj_no):
                    if created_records >= 170:
                        break

                    adjustment_no += 1

                    invoice_record = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)[0]
                    line_ids = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)

                    # Create sets to store the values from each loop
                    adjustment_set = set()
                    invoice_set = set()
                    
                    count_invoice_lines = 0
                    adjusted_lines_count = {}

                    for line in line_ids:
                        # line.is_adjustment_created = True
                        line.is_sync = True
                        if line.invoice_adj_no == adjustment_no:
 
                            # Store the values from the first loop in the adjustment_set
                            for adjustment in line_ids:

                                if adjustment.invoice_adj_id != 0 and adjustment.invoice_adj_no == line.invoice_adj_no:
                                    adjustment_set.add((adjustment.prod_id, 
                                                        adjustment.invoice_ref_no, 
                                                        adjustment.amount, 
                                                        adjustment.invoice_id,
                                                        ))

                            # Store the values from the second loop in the invoice_set
                            for invoice in line_ids:
                                if line.invoice_adj_no == 1:
                                    if invoice.invoice_adj_id == 0:
                                        invoice_set.add((invoice.prod_id, 
                                                        invoice.invoice_ref_no, 
                                                        invoice.amount, 
                                                        invoice.invoice_id,
                                                        ))
                                        
                                elif line.invoice_adj_no > 1:
                                    if invoice.invoice_adj_id != 0 and invoice.invoice_adj_no == (adjustment_no-1):
                                        invoice_set.add((invoice.prod_id, 
                                                            invoice.invoice_ref_no, 
                                                            invoice.amount, 
                                                            invoice.invoice_id,
                                                            ))
                            count_invoice_lines += 1

                        else:

                            if line.invoice_adj_no in adjusted_lines_count:
                                adjusted_lines_count[line.invoice_adj_no] += 1
                            else:
                                adjusted_lines_count[line.invoice_adj_no] = 1
                            
                                    
                    # Find the unmatched data by subtracting one set from the other
                    unmatched_data = (adjustment_set - invoice_set)
                    unmatched_data2 = (invoice_set - adjustment_set) 

                    data = list({'prod_id': item[0],
                                'invoice_ref_no': item[1],
                                'amount': -item[2],
                                'invoice_id,': item[3],
                                } 
                                for item in unmatched_data)
                    
                    data2 = list({'prod_id': item[0],
                                'invoice_ref_no': item[1],
                                'amount': item[2],
                                'invoice_id,': item[3],
                                } 
                                for item in unmatched_data2)
                    
                    sms_data = self.env['sms.invoice'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no), ('invoice_adj_no', '=', adjustment_no)], limit=1)
                    sms_datav2 = self.env['sms.invoice'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no), ('invoice_adj_no', '=', adjustment_no-1)], limit=1)
                    sms_adjustment_date = self.env['sms.invoice'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no),  ('invoice_adj_no', '=', adjustment_no), ('adjust_date', '!=', False)], limit=1)
                    partner_customer = self.env['res.partner'].search([('customer_id', '=', invoice_record.customer_id)])

                    
                    initial_amount = 0
                    # if (adjustment_no-1) == 0:
                    if sms_datav2.total_adj_amount == 0.0 and (adjustment_no-1) != 0:
                        initial_amount = sms_datav2.total_adj_amount
                    elif sms_datav2.total_adj_amount == 0.0:
                        initial_amount = sms_datav2.total_amount
                    else:
                        initial_amount = sms_datav2.total_adj_amount

                    # # Process the data and data2 based on prod_id
                    # for adj_no, count in adjusted_lines_count.items():
                        
                    for x in data:
                        found_equal_prod_id = False
                        for y in data2:
                            if x['prod_id'] == y['prod_id']:
                                found_equal_prod_id = True
                                # Adjust the amounts based on comparison
                                # if x['amount'] < 0:  # x is negative
                                #     y['amount'] = y['amount'] - abs(x['amount'])  # Add the positive value of x
                                # else:  # x should not be positive here
                                #     y['amount'] = y['amount'] - abs(x['amount'])  # Subtract the positive value of x

                                if  abs(x['amount']) > y['amount']: 
                                    y['amount'] = y['amount'] + x['amount']
                                else:  # x should not be positive here
                                    y['amount'] = y['amount'] - abs(x['amount']) 

                                break
                        if not found_equal_prod_id:
                            data2.append(x)


                    # Update amounts in data and data2 based on the matching criteria
                    if initial_amount >= sms_data.total_adj_amount:
                        credit_lines = []

                        for item in data2:
                            product_temp = self.env['product.template'].search([('prod_id', '=', int(item['prod_id']))])
                            product = self.env['product.product'].search([('product_tmpl_id', '=', product_temp.id)])

                            # price_unit = -round(item['amount'], 2) if is_total_negative else round(item['amount'], 2)

                            credit_line = {
                                'product_id': product.id,
                                'quantity': 1,
                                'product_uom_id': product_temp.uom_id.id,
                                'price_unit': round(item['amount'], 2),
                            }
                            credit_lines.append((0, 0, credit_line))
 

                        if not credit_lines:
                            # Skip creating the invoice if no invoice lines meet the condition
                            continue

                        credit = {
                            'partner_id': partner_customer.id,
                            'invoice_ref_no': invoice_record.invoice_ref_no,
                            'inv_type_desc': invoice_record.inv_type_desc,
                            'invoice_date': sms_adjustment_date.adjust_date or invoice_record.invoice_date,
                            'invoice_date_due': invoice_record.due_date2 or invoice_record.due_date,
                            'move_type': 'out_refund',
                            'state': 'draft',
                            # 'name': next_invoice_number,
                            'invoice_line_ids': credit_lines,

                            'course': invoice_record.course,
                            'year': invoice_record.year_level,
                            'school_year': invoice_record.school_year,
                            'term': invoice_record.term,
                            'is_adjusted': True,
                            'adjustment_no': adjustment_no,
                            'invoice_category': 'subsidized',
                        }

                        account_move = self.env['account.move'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no),('adjustment_no', '=', adjustment_no)])
                        if account_move:
                            continue

                        cred = self.env['account.move'].create(credit)
                        cred.action_post()

                        invoice_to_reconcile = self.env['account.move'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no), ('is_adjusted','=',False)])
                        
                        if invoice_to_reconcile:
                            # (cred + invoice_to_reconcile).line_ids.filtered(lambda line: line.account_id.reconcile).reconcile()

                            # Sort the invoices by due date in descending order (latest due date first)
                            invoices_sorted = invoice_to_reconcile.sorted(key=lambda inv: inv.invoice_date_due, reverse=False)

                            remaining_credit = cred.amount_total

                            for invoice in invoices_sorted:
                                                                if remaining_credit <= 0:
                                    break
                                
                                # Calculate the amount to reconcile for the current invoice
                                amount_to_reconcile = min(remaining_credit, invoice.amount_residual)

                                # Filter lines that can be reconciled
                                lines_to_reconcile = (cred + invoice).line_ids.filtered(lambda line: line.account_id.reconcile and line.amount_residual != 0)

                                # Check if there's something to reconcile
                                if lines_to_reconcile:
                                    # Perform reconciliation (system will handle the partial/full reconciliation automatically)
                                    lines_to_reconcile.reconcile()

                                # Deduct the reconciled amount from the remaining credit
                                remaining_credit -= amount_to_reconcile

                        created_records += 1
                        # invoice_record.is_sync = True

                    else:
                        invoice_lines = []
                        for item in data2:

                            product_temp = self.env['product.template'].search([('prod_id', '=', int(item['prod_id']))])
                            product = self.env['product.product'].search([('product_tmpl_id', '=', product_temp.id)])

                            invoice_line = {
                                'product_id': product.id,
                                'quantity': 1,
                                'product_uom_id': product_temp.uom_id.id,
                                'price_unit': round(item['amount']*-1, 2),
                            }
                            invoice_lines.append((0, 0, invoice_line))
 

                        if not invoice_lines:
                            # Skip creating the invoice if no invoice lines meet the condition
                            continue
                        
                        invoice = {
                            'partner_id': partner_customer.id,
                            'invoice_ref_no': invoice_record.invoice_ref_no,
                            'inv_type_desc': invoice_record.inv_type_desc,
                            'invoice_date': sms_adjustment_date.invoice_date or invoice_record.invoice_date, 
                            'invoice_date_due': invoice_record.due_date2 or invoice_record.due_date,
                            'move_type': 'out_invoice',
                            'state': 'draft',
                            # 'name': next_invoice_number,
                            'invoice_line_ids': invoice_lines,

                            'course': invoice_record.course,
                            'year': invoice_record.year_level,
                            'school_year': invoice_record.school_year,
                            'term': invoice_record.term,
                            'is_adjusted': True,
                            'adjustment_no': adjustment_no,
                            'invoice_category': 'subsidized',
                        }

                        account_move = self.env['account.move'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no),('adjustment_no', '=', adjustment_no)])
                        if account_move:
                            continue
                        
                        inv = self.env['account.move'].create(invoice)
                        inv.action_post()
                        

                        created_records += 1

                        # invoice_record.is_sync = True
                        self.env.cr.commit()

        except Exception as error:
            _logger.error('Error in sync_create_assessment_invoices: %s', error)

    def create_assessment_invoices_by_invoice_id(self, inv_id=None):
        try:
            sms_customers = self.env['sms.invoice'].search([('inv_type_desc', '=', 'ENROLLMENT ASSESSMENT'), ('invoice_id','=',inv_id), ('is_sync','=',False)])
            invoice_ids = sms_customers.mapped('invoice_id')
            unique_invoice_ids = list(set(invoice_ids))

            # total_amount = 0

            for invoice_id in unique_invoice_ids:
                invoice_record = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)[0]
                line_ids = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)

                # account_move = self.env['account.move'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no)])
                # if account_move:
                #     continue

                partner_customer = self.env['res.partner'].search([('customer_id', '=', invoice_record.customer_id)])
                pay_term = int(invoice_record.pay_term)

                first_pay = ''
                inv_pays = ''
                if pay_term == 4:
                    split_percentages = [
                        invoice_record.due_percent / 100,
                        invoice_record.due_percent2 / 100,
                        invoice_record.due_percent3 / 100,
                        invoice_record.due_percent4 / 100,
                    ]
                    due_dates = [
                        invoice_record.due_date,
                        invoice_record.due_date2,
                        invoice_record.due_date3,
                        invoice_record.due_date4,
                    ]
                    first_pay = [True, False, False, False]
                    if [invoice_record.invoice_pay_id][0]:
                        inv_pays = ([invoice_record.invoice_pay_id][0].strip('()').split(','))
                    remarks = ['First Payment', None, None, None]
                
                elif pay_term == 3:
                    split_percentages = [
                        invoice_record.due_percent / 100,
                        invoice_record.due_percent2 / 100,
                        invoice_record.due_percent3 / 100
                    ]
                    due_dates = [
                        invoice_record.due_date,
                        invoice_record.due_date2,
                        invoice_record.due_date3
                    ]
                    first_pay = [True, False, False]
                    if [invoice_record.invoice_pay_id][0]:
                        inv_pays = ([invoice_record.invoice_pay_id][0].strip('()').split(','))
                    remarks = ['First Payment', None, None]

                elif pay_term == 2:
                    split_percentages = [
                        invoice_record.due_percent / 100,
                        invoice_record.due_percent2 / 100
                    ]
                    due_dates = [
                        invoice_record.due_date,
                        invoice_record.due_date2
                    ]
                    first_pay = [True, False]
                    if [invoice_record.invoice_pay_id][0]:
                        inv_pays = ([invoice_record.invoice_pay_id][0].strip('()').split(','))
                    remarks = ['First Payment', None]

                elif pay_term == 1:
                    split_percentages = [1.0]
                    due_dates = [invoice_record.due_date]
                    first_pay = [True]
                    if [invoice_record.invoice_pay_id][0]:
                        inv_pays = ([invoice_record.invoice_pay_id][0].strip('()').split(','))
                    remarks = ['First Payment']
                    

                else:
                    split_percentages = [1.0]
                    due_dates = [invoice_record.due_date]
                    first_pay = [True]
                    if [invoice_record.invoice_pay_id][0]:
                        inv_pays = ([invoice_record.invoice_pay_id][0].strip('()').split(','))
                    remarks = ['First Payment']

                total_quantity = sum(line.qty for line in line_ids)


                for index, (percentage, due_date) in enumerate(zip(split_percentages, due_dates)):
                    invoice_lines = []

                    price_unit = 0
                    final_price_unit = 0
                    total_price = 0
                    for line in line_ids:
                        if line.invoice_adj_id == 0:
                            product_temp = self.env['product.template'].search([('prod_id', '=', line.prod_id)])
                            product = self.env['product.product'].search([('product_tmpl_id', '=', product_temp.id)])

                            if index == len(split_percentages) - 1:
                                if pay_term == 1:
                                    price_unit = line.unit_price * percentage

                                elif pay_term == 2:
                                    # price_unit = line.unit_price - (line.unit_price * ((invoice_record.due_percent2) / 100))
                                    final_price_unit = round(line.unit_price * invoice_record.due_percent / 100, 2)
                                    price_unit = line.unit_price - final_price_unit

                                elif pay_term == 3:
                                    final_price_unit = round(line.unit_price * invoice_record.due_percent / 100, 2) + round(line.unit_price * invoice_record.due_percent2 / 100, 2)
                                    price_unit = line.unit_price - final_price_unit

                                elif pay_term == 4:
                                    # price_unit = line.unit_price - (line.unit_price * ((invoice_record.due_percent + invoice_record.due_percent2 + invoice_record.due_percent3) / 100))
                                    final_price_unit = round(line.unit_price * invoice_record.due_percent / 100, 2) + round(line.unit_price * invoice_record.due_percent2 / 100, 2) +  round(line.unit_price * invoice_record.due_percent3 / 100, 2)
                                    price_unit = line.unit_price - final_price_unit

                                # else:
                                #     final_price_unit += price_unit
                                
                            else:
                                price_unit = round(line.unit_price * percentage,2)
                                
                            total_price += price_unit
                                
                            invoice_line = {
                                'product_id': product.id,
                                'quantity': line.qty,
                                'product_uom_id': product_temp.uom_id.id,
                                'price_unit': price_unit
                            }

                            invoice_lines.append((0, 0, invoice_line))

                            line.is_sync = True

                    if not invoice_lines:
                        continue


                    invoice = {
                        'partner_id': partner_customer.id,
                        'invoice_ref_no': invoice_record.invoice_ref_no,
                        'inv_type_desc': invoice_record.inv_type_desc,
                        'invoice_date': invoice_record.invoice_date,
                        'invoice_date_due': due_date + timedelta(hours=8),
                        # 'invoice_date_due': due_date,
                        'move_type': 'out_invoice',
                        'state': 'draft',
                        'invoice_line_ids': invoice_lines,
                        'is_first_payment': first_pay[index] or False,
                        'is_from_sync': True,
                        'inv_pay_id': inv_pays[index] or None,
                        'student_id': invoice_record.customer_id if (invoice_record.customer_type == 'STUDENT') else None,
                        'applicant_id': invoice_record.customer_id if (invoice_record.customer_type == 'APPLICANT') else None,
                        'api_remarks': remarks[index],

                        'course': invoice_record.course,
                        'year': invoice_record.year_level,
                        'school_year': invoice_record.school_year,
                        'term': invoice_record.term,
                        'is_adjusted': False,
                        'invoice_category': 'subsidized',
                    }

                    existing_account = self.env['account.move'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no),('inv_pay_id', '=', inv_pays[index])])
                    
                    existing_account_v2 = self.env['account.move'].search([
                        ('inv_type_desc', '=', 'ENROLLMENT ASSESSMENT'), 
                        ('state','=','posted'),
                        ('customer_id','=',invoice_record.customer_id),
                        ('invoice_date','=',invoice_record.invoice_date),
                        ('invoice_date_due','=',due_date),
                        ])
                    
                    # if existing_account and existing_account.create_date.strftime('%Y-%m-%d') == fields.Date.today().strftime('%Y-%m-%d'):
                    if existing_account and existing_account_v2.create_date.strftime('%Y-%m-%d') == fields.Date.today().strftime('%Y-%m-%d'):
                        continue

                    inv = self.env['account.move'].create(invoice)
                    inv.action_post()

                    # account_move = self.env['account.move'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no),('inv_pay_id', '=', inv_pays[index])])

                    # logs = self.env['dlsu.sync.logs'].search([('name','=',invoice_record.invoice_ref_no)],limit = 1).update({'invoice_name': account_move.name, 'invoice_amount': account_move.amount_total})
                    
                    self.env.cr.commit()

                    # total_amount += total_price

                    

        except Exception as error:
            _logger.error('Error in sync_create_assessment_invoices: %s', error)

    def create_assessment_invoices_by_invoice_id_v2(self, inv_id=None):
        try:
            sms_customers = self.env['sms.invoice'].search([('inv_type_desc', '=', 'ENROLLMENT ASSESSMENT'), ('invoice_id','=',inv_id), ('is_sync','=',False)])
            invoice_ids = sms_customers.mapped('invoice_id')
            unique_invoice_ids = list(set(invoice_ids))

            for invoice_id in unique_invoice_ids:
                invoice_record = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)[0]
                line_ids = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)

                partner_customer = self.env['res.partner'].search([('customer_id', '=', invoice_record.customer_id)])
                pay_term = int(invoice_record.pay_term)

                first_pay = ''
                inv_pays = ''
                if pay_term == 4:
                    split_percentages = [
                        invoice_record.due_percent / 100,
                        invoice_record.due_percent2 / 100,
                        invoice_record.due_percent3 / 100,
                        invoice_record.due_percent4 / 100,
                    ]
                    due_dates = [
                        invoice_record.due_date,
                        invoice_record.due_date2,
                        invoice_record.due_date3,
                        invoice_record.due_date4,
                    ]
                    first_pay = [True, False, False, False]
                    if [invoice_record.invoice_pay_id][0]:
                        inv_pays = ([invoice_record.invoice_pay_id][0].strip('()').split(','))
                    remarks = ['First Payment', None, None, None]
                
                elif pay_term == 3:
                    split_percentages = [
                        invoice_record.due_percent / 100,
                        invoice_record.due_percent2 / 100,
                        invoice_record.due_percent3 / 100
                    ]
                    due_dates = [
                        invoice_record.due_date,
                        invoice_record.due_date2,
                        invoice_record.due_date3
                    ]
                    first_pay = [True, False, False]
                    if [invoice_record.invoice_pay_id][0]:
                        inv_pays = ([invoice_record.invoice_pay_id][0].strip('()').split(','))
                    remarks = ['First Payment', None, None]

                elif pay_term == 2:
                    split_percentages = [
                        invoice_record.due_percent / 100,
                        invoice_record.due_percent2 / 100
                    ]
                    due_dates = [
                        invoice_record.due_date,
                        invoice_record.due_date2
                    ]
                    first_pay = [True, False]
                    if [invoice_record.invoice_pay_id][0]:
                        inv_pays = ([invoice_record.invoice_pay_id][0].strip('()').split(','))
                    remarks = ['First Payment', None]

                elif pay_term == 1:
                    split_percentages = [1.0]
                    due_dates = [invoice_record.due_date]
                    first_pay = [True]
                    if [invoice_record.invoice_pay_id][0]:
                        inv_pays = ([invoice_record.invoice_pay_id][0].strip('()').split(','))
                    remarks = ['First Payment']
                    

                else:
                    split_percentages = [1.0]
                    due_dates = [invoice_record.due_date]
                    first_pay = [True]
                    if [invoice_record.invoice_pay_id][0]:
                        inv_pays = ([invoice_record.invoice_pay_id][0].strip('()').split(','))
                    remarks = ['First Payment']

                total_quantity = sum(line.qty for line in line_ids)

                for index, (percentage, due_date) in enumerate(zip(split_percentages, due_dates)):
                    invoice_lines = []

                    price_unit = 0
                    final_price_unit = 0
                    total_price = 0
                    for line in line_ids:
                        if line.invoice_adj_id == 0:
                            product_temp = self.env['product.template'].search([('prod_id', '=', line.prod_id)])
                            product = self.env['product.product'].search([('product_tmpl_id', '=', product_temp.id)])

                            if index == len(split_percentages) - 1:
                                if pay_term == 1:
                                    price_unit = line.unit_price * percentage

                                elif pay_term == 2:
                                    final_price_unit = round(line.unit_price * invoice_record.due_percent / 100, 2)
                                    price_unit = line.unit_price - final_price_unit

                                elif pay_term == 3:
                                    final_price_unit = round(line.unit_price * invoice_record.due_percent / 100, 2) + round(line.unit_price * invoice_record.due_percent2 / 100, 2)
                                    price_unit = line.unit_price - final_price_unit

                                elif pay_term == 4:
                                    final_price_unit = round(line.unit_price * invoice_record.due_percent / 100, 2) + round(line.unit_price * invoice_record.due_percent2 / 100, 2) +  round(line.unit_price * invoice_record.due_percent3 / 100, 2)
                                    price_unit = line.unit_price - final_price_unit
                                
                            else:
                                price_unit = round(line.unit_price * percentage,2)

                            total_price += price_unit
                                
                            invoice_line = {
                                'product_id': product.id,
                                'quantity': line.qty,
                                'product_uom_id': product_temp.uom_id.id,
                                'price_unit': price_unit
                            }

                            invoice_lines.append((0, 0, invoice_line))
                            line.is_sync = True

                    if not invoice_lines:
                        continue

                    invoice = {
                        'partner_id': partner_customer.id,
                        'invoice_ref_no': invoice_record.invoice_ref_no,
                        'inv_type_desc': invoice_record.inv_type_desc,
                        'invoice_date': invoice_record.invoice_date,
                        'invoice_date_due': due_date + timedelta(hours=8),
                        'move_type': 'out_invoice',
                        'state': 'draft',
                        'invoice_line_ids': invoice_lines,
                        'is_first_payment': first_pay[index] or False,
                        'is_from_sync': True,
                        'inv_pay_id': inv_pays[index] or None,
                        'student_id': invoice_record.customer_id if (invoice_record.customer_type == 'STUDENT') else None,
                        'applicant_id': invoice_record.customer_id if (invoice_record.customer_type == 'APPLICANT') else None,
                        'api_remarks': remarks[index],

                        'course': invoice_record.course,
                        'year': invoice_record.year_level,
                        'school_year': invoice_record.school_year,
                        'term': invoice_record.term,
                        'is_adjusted': False,
                        'invoice_category': 'subsidized',
                    }

                    existing_account = self.env['account.move'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no),('inv_pay_id', '=', inv_pays[index])])
                    _logger.debug('Existing account found: %s', existing_account)
                    if not existing_account:
                        # continue
                                    inv = self.env['account.move'].create(invoice)
                                                inv.action_post()

                        self.env.cr.commit()
                    else:
                        pass

        except Exception as error:
            _logger.error('Error in sync_create_assessment_invoices: %s', error)
    
    def create_application_invoices_by_invoice_id(self, inv_id=None):
        # sms_customers = self.env['sms.invoice'].search([('inv_type_desc', '=', 'ADMISSION ENTRANCE EXAM'),('invoice_id','=',inv_id)])
        sms_customers = self.env['sms.invoice'].search([('inv_type_desc', 'in', ('ADMISSION FEE', 'ADMISSION ENTRANCE EXAM', 'ADMISSION APPLICATION', 'ADMISSION OTHER PROCESS',)), ('invoice_id','=',inv_id), ('is_sync','=',False)])

        _logger.info('SMS Customers: %s', sms_customers)

        invoice_ids = sms_customers.mapped('invoice_id')
        unique_invoice_ids = list(set(invoice_ids))

        for invoice_id in unique_invoice_ids:
            invoice_record = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)[0]
            line_ids = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)

            partner_customer = self.env['res.partner'].search([('customer_id', '=', invoice_record.customer_id)])

            inv_pays = ''
            if [invoice_record.invoice_pay_id][0]:
                inv_pays = ([invoice_record.invoice_pay_id][0].strip('()').split(','))
            
            invoice_lines = []
            for line in line_ids:
                product_temp = self.env['product.template'].search([('prod_id', '=', line.prod_id)])
                product = self.env['product.product'].search([('product_tmpl_id', '=', product_temp.id)])

                invoice_line = {
                    'product_id': product.id,
                    'quantity': line.qty,
                    'product_uom_id': product_temp.uom_id.id,
                    'price_unit': line.unit_price,
                }
                invoice_lines.append((0, 0, invoice_line))

                line.is_sync = True

            invoice = {
                'partner_id': partner_customer.id,
                'invoice_ref_no': invoice_record.invoice_ref_no,
                'inv_type_desc': invoice_record.inv_type_desc,
                'invoice_date': invoice_record.invoice_date,
                'invoice_date_due': invoice_record.due_date,
                'move_type': 'out_invoice',
                'state': 'draft',
                'invoice_line_ids': invoice_lines,

                'course': invoice_record.course or None,
                'year': invoice_record.year_level or None,
                'school_year': invoice_record.school_year or None,
                'term': invoice_record.term or None,
                'is_adjusted': False,
                'is_first_payment': True,
                'is_from_sync': True,
                'inv_pay_id': inv_pays[0] or None,
                'invoice_category': 'passed_one',
            }
            
            account = self.env['account.move'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no)])
            existing_account = self.env['account.move'].search([
                ('inv_type_desc', 'in', ('ADMISSION FEE', 'ADMISSION ENTRANCE EXAM', 'ADMISSION APPLICATION', 'ADMISSION OTHER PROCESS',)), 
                ('state','=','posted'),
                ('customer_id','=',invoice_record.customer_id),
                ('amount_total','=',invoice_record.total_amount),
                ('invoice_date','=',invoice_record.invoice_date),
                ])
                        _logger.info('existing_account: %s', existing_account)

            if not account and not existing_account:

            # if not account:
                inv = self.env['account.move'].create(invoice)
                inv.action_post()

                # logs = self.env['dlsu.sync.logs'].search([('name','=',invoice_record.invoice_ref_no)],limit = 1).update({'invoice_name': account.name, 'invoice_amount': account.amount_total})
            else:
                pass

    def catch_all_invoices_by_invoice_id(self, inv_id=None):
                if inv_id:
            sms_customers = self.env['sms.invoice'].search([('invoice_id','=',inv_id), ('is_sync','=',False)])
            invoice_ids = sms_customers.mapped('invoice_id')
            unique_invoice_ids = list(set(invoice_ids))

            for invoice_id in unique_invoice_ids:
                invoice_record = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)[0]
                line_ids = sms_customers.filtered(lambda c: c.invoice_id == invoice_id)

                partner_customer = self.env['res.partner'].search([('customer_id', '=', invoice_record.customer_id)])

                inv_pays = ''
                if [invoice_record.invoice_pay_id][0]:
                    inv_pays = ([invoice_record.invoice_pay_id][0].strip('()').split(','))
                else:
                    inv_pays = None

                invoice_lines = []
                for line in line_ids:
                    product_temp = self.env['product.template'].search([('prod_id', '=', line.prod_id)])
                    product = self.env['product.product'].search([('product_tmpl_id', '=', product_temp.id)])

                    invoice_line = {
                        'product_id': product.id,
                        'quantity': line.qty,
                        'product_uom_id': product_temp.uom_id.id,
                        'price_unit': line.unit_price,
                    }
                    invoice_lines.append((0, 0, invoice_line))

                    line.is_sync = True

                sms_invoice = {
                    'partner_id': partner_customer.id,
                    'invoice_ref_no': invoice_record.invoice_ref_no,
                    'inv_type_desc': invoice_record.inv_type_desc,
                    'invoice_date': invoice_record.invoice_date,
                    'invoice_date_due': invoice_record.due_date,
                    'move_type': 'out_invoice',
                    'state': 'draft',
                    'is_first_payment': True,

                    'course': invoice_record.course or None,
                    'year': invoice_record.year_level or None,
                    'school_year': invoice_record.school_year or None,
                    'term': invoice_record.term or None,
                    'is_adjusted': False,
                    'is_first_payment': True,
                    'is_from_sync': True,
                    'inv_pay_id': inv_pays[0] or None,
                    'invoice_category': 'passed_one',

                    'invoice_line_ids': invoice_lines,
                }
                
                account = self.env['account.move'].search([('invoice_ref_no', '=', invoice_record.invoice_ref_no)])
                # existing_account = self.env['account.move'].search([
                #     ('inv_type_desc', '=', 'ENROLLMENT ASSESSMENT'), 
                #     ('state','=','posted'),
                #     ('customer_id','=',invoice_record.customer_id),
                #     ('amount_total','=',invoice_record.total_amount),
                #     ('invoice_date','=',invoice_record.invoice_date),
                #     ])

                
                # if not account and not existing_account:

                if not account:
                    inv = self.env['account.move'].create(sms_invoice)
                    inv.action_post()
                else:
                    pass
    


    def sync_rpc_create_user_portal(self, partner_id=None):
        for rec in self:
            # Source Odoo Database
                        source_url = self.env['ir.config_parameter'].sudo().get_param('xml.rpc.remote.url')
            source_db = self.env['ir.config_parameter'].sudo().get_param('xml.rpc.remote.db')
            source_username = self.env['ir.config_parameter'].sudo().get_param('xml.rpc.remote.username')
            source_password = self.env['ir.config_parameter'].sudo().get_param('xml.rpc.remote.password')

            source_common = xmlrpc.client.ServerProxy(f'{source_url}/xmlrpc/2/common')
            source_uid = source_common.authenticate(source_db, source_username, source_password, {})

            domain = []
            #Retrieve
            source_models = xmlrpc.client.ServerProxy(f'{source_url}/xmlrpc/2/object')
            data = source_models.execute_kw(source_db, source_uid, source_password, 'res.company', 'sync_user', [False,partner_id], {})
        