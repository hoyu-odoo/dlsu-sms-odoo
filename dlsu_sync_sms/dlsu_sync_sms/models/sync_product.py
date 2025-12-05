# -*- coding: utf-8 -*-
from odoo import models, fields, api
import requests
import xml.etree.ElementTree as ET
import xmltodict
import logging
from datetime import datetime
import pytz  # Import the pytz library to handle timezones
import requests
from odoo.exceptions import except_orm, Warning, RedirectWarning, UserError, ValidationError


_logger = logging.getLogger(__name__)

class ProductSuccessWizard(models.TransientModel):
    _name = 'product.success.wizard'
    _description = 'Product Success Sync'

    message = fields.Text(string='Message', readonly=True)

    def action_ok(self):
        return {'type': 'ir.actions.act_window_close'}
    

class SMSResProduct(models.Model):
    _inherit = 'product.template'

    def update_products(self):
        """Update products from SMS system via SOAP API"""
        for rec in self:
            settings = self.env['sync.sms.settings'].search([('default', '=', True)], limit=1)
            if not settings:
                raise Exception('No default settings found.')
            
            soap="""
                POST /odoows/product.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/ProductUpdate"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <ProductUpdate xmlns="http://FMS.dlsud.edu.ph/">
                    <_user>string</_user>
                    <_prodid>int</_prodid>
                    <_prodname>string</_prodname>
                    <_proddesc>string</_proddesc>
                    <_prodtypeid>int</_prodtypeid>
                    <_prodcode>string</_prodcode>
                    <_accountcode>string</_accountcode>
                    <_accountcodedesc>string</_accountcodedesc>
                    <_defanalyticacctcode>string</_defanalyticacctcode>
                    <_defanalytictag>string</_defanalytictag>
                    <_deffundacct>string</_deffundacct>
                    </ProductUpdate>
                </soap:Body>
                </soap:Envelope>
            """

            url = f"http://{settings[0].host}/fms/odoosync/product.asmx"
            tag = (', '.join(rec.analytic_tag_ids.mapped('name')) if rec.analytic_tag_ids else 'None')

            payload = f"""
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <ProductUpdate xmlns="http://FMS.dlsud.edu.ph/">
                    <_user>{str(rec.env.user.name)}</_user>
                    <_prodid>{int(rec.prod_id)}</_prodid>
                    <_prodname>{str(rec.default_code)}</_prodname>
                    <_proddesc>{str(rec.name)}</_proddesc>
                    <_prodtypeid>{int(rec.prod_type_id)}</_prodtypeid>
                    <_prodcode>{str(rec.name)}</_prodcode>
                    <_accountcode>{str(rec.property_account_income_id.code)}</_accountcode>
                    <_accountcodedesc>{str(rec.property_account_income_id.name)}</_accountcodedesc>
                    <_defanalyticacctcode>{str(rec.account_analytic_id.code)}</_defanalyticacctcode>
                    <_defanalytictag>{str(tag)}</_defanalytictag>
                    <_deffundacct>{str(rec.fund_account_id.name)}</_deffundacct>
                    </ProductUpdate>
                </soap:Body>
                </soap:Envelope>
            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/ProductUpdate"',
            'Connection': 'keep-alive',
            }

            try:
                response = requests.request("POST", url, headers=headers, data=payload)
                xml_content = response.content

                if response.status_code == 200:
                    rec.env['product.success.wizard'].create({'message': 'Sync successful.'}).action_ok()
                    return {
                        'view_mode': 'form',
                        'res_model': 'product.success.wizard',
                        'type': 'ir.actions.act_window',
                        'target': 'new',
                    }

                else:
                    raise UserWarning(f"Sync failed: {response.status_code} - {response.reason}")
                
            except Exception as e:
                raise UserWarning(f"Sync failed: {str(e)}")

    def create_products(self):
        for rec in self:
            settings = self.env['sync.sms.settings'].search([('default', '=', True)], limit=1)
            if not settings:
                raise Exception('No default settings found.')
            
            soap="""
                POST /odoows/product.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/ProductInsert"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <ProductInsert xmlns="http://FMS.dlsud.edu.ph/">
                    <_user>string</_user>
                    <_prodname>string</_prodname>
                    <_proddesc>string</_proddesc>
                    <_prodtypeid>int</_prodtypeid>
                    <_prodcode>string</_prodcode>
                    <_accountcode>string</_accountcode>
                    <_accountcodedesc>string</_accountcodedesc>
                    <_defanalyticacctcode>string</_defanalyticacctcode>
                    <_defanalytictag>string</_defanalytictag>
                    <_deffundacct>string</_deffundacct>
                    </ProductInsert>
                </soap:Body>
                </soap:Envelope>
            """

            # url = f"http://{settings[0].host}/odoows/product.asmx"

            url = f"http://{settings[0].host}/fms/odoosync/product.asmx"

            payload = f"""
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <ProductInsert xmlns="http://FMS.dlsud.edu.ph/">
                    <_user>{str(rec.env.user.name)}</_user>
                    <_prodname>{str(rec.default_code)}</_prodname>
                    <_proddesc>{str(rec.name)}</_proddesc>
                    <_prodtypeid>{int(rec.prod_type_id)}</_prodtypeid>
                    <_prodcode>{str(rec.name)}</_prodcode>
                    <_accountcode>{str(rec.property_account_income_id.code)}</_accountcode>
                    <_accountcodedesc>{str(rec.property_account_income_id.name)}</_accountcodedesc>
                    <_defanalyticacctcode>{str(rec.account_analytic_id.code)}</_defanalyticacctcode>
                    <_defanalytictag>{str(', '.join(rec.analytic_tag_ids.mapped('name')) if rec.analytic_tag_ids else '')}</_defanalytictag>
                    <_deffundacct>{str(rec.fund_account_id.name)}</_deffundacct>
                    </ProductInsert>
                </soap:Body>
                </soap:Envelope>
            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/ProductInsert"',
            'Connection': 'keep-alive',
            }

            try:
                response = requests.request("POST", url, headers=headers, data=payload)
                xml_content = response.content

                if response.status_code == 200:
                    rec.env['product.success.wizard'].create({'message': 'Sync successful.'}).action_ok()
                    return {
                        'view_mode': 'form',
                        'res_model': 'product.success.wizard',
                        'type': 'ir.actions.act_window',
                        'target': 'new',
                    }

                else:
                    raise UserWarning(f"Sync failed: {response.status_code} - {response.reason}")
        
            except Exception as e:
                raise UserWarning(f"Sync failed: {str(e)}")


class SMSProduct(models.Model):
    _name = 'sms.product'
    _description = 'Product'

    diffgr_id = fields.Char('Diffgr ID')
    row_order = fields.Char('Row Order')
    prod_id = fields.Char('Product ID')
    prod_name = fields.Char('Product Name')
    prod_desc = fields.Char('Product Description')
    prod_type_id = fields.Char('Product Type ID')
    prod_type_desc = fields.Char('Product Type Description')
    account_code = fields.Char('Account Code')
    date_created = fields.Datetime('Date Created')
    date_modified = fields.Datetime('Date Modified')

    def update_sms_product(self):
        for rec in self:
            settings = self.env['sync.sms.settings'].search([('default', '=', True)], limit=1)
            if not settings:
                raise Exception('No default settings found.')
            
            soap="""
                POST /odoows/product.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/ProductUpdate"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <ProductUpdate xmlns="http://FMS.dlsud.edu.ph/">
                    <_prodid>int</_prodid>
                    <_prodname>string</_prodname>
                    <_proddesc>string</_proddesc>
                    <_prodtypeid>int</_prodtypeid>
                    <_prodcode>string</_prodcode>
                    <_accountcode>string</_accountcode>
                    </ProductUpdate>
                </soap:Body>
                </soap:Envelope>
            """

            # url = f"http://{settings[0].host}/odoows/product.asmx"
            url = f"http://{settings[0].host}/fms/odoosync/product.asmx"

            payload = f"""
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                                xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                                xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>

                    <ProductUpdate xmlns="http://FMS.dlsud.edu.ph/">
                    <_prodid>{rec.prod_id}</_prodid>
                    <_prodname>{rec.default_code}</_prodname>
                    <_proddesc>{rec.prod_desc}</_proddesc>
                    <_prodtypeid>{rec.prod_type_id}</_prodtypeid>
                    <_accountcode>{rec.account_code}</_accountcode>
                    </ProductUpdate>
                </soap:Body>
                </soap:Envelope>
            """
            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/ProductUpdate"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            # Convert XML content to dictionary 
            response_dict = xmltodict.parse(xml_content)

    

class SyncSMSSettingProduct(models.Model):
    _inherit = 'sync.sms.settings'

    product_date_from = fields.Date('Date From')
    product_date_to = fields.Date('Date To')
    prod_id = fields.Integer('Product ID')
    prod_type_id = fields.Integer('Product Type ID')
    product_search = fields.Char('Search')
    product_type_search = fields.Char('Search')



    def parse_date(self, date_str):
        if date_str:
            try:
                soap_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%f%z')
            except ValueError:
                soap_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S%z')
            return soap_date
        return None
        




    def sync_product_view_by_date_created(self):
        for rec in self:
    
            soap = """
                POST /odoows/product.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/ProductViewByDateCreated"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <ProductViewByDateCreated xmlns="http://FMS.dlsud.edu.ph/">
                    <_datecreatedfrom>dateTime</_datecreatedfrom>
                    <_datecreatedto>dateTime</_datecreatedto>
                    </ProductViewByDateCreated>
                </soap:Body>
                </soap:Envelope>
            """


            url = f"http://{rec.host}/fms/odoosync/product.asmx"

            datecreatedfrom = rec.product_date_from.strftime('%Y-%m-%d')
            datecreatedto = rec.product_date_to.strftime('%Y-%m-%d')

            payload = f"""
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                                xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                                xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>

                    <ProductViewByDateCreated xmlns="http://FMS.dlsud.edu.ph/">
                    <_datecreatedfrom>{datecreatedfrom}</_datecreatedfrom>
                    <_datecreatedto>{datecreatedto}</_datecreatedto>
                    </ProductViewByDateCreated>
                </soap:Body>
                </soap:Envelope>
            """
            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/ProductViewByDateCreated"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            response_dict = xmltodict.parse(xml_content)


            dt_element = response_dict['soap:Envelope']['soap:Body']['ProductViewByDateCreatedResponse']['ProductViewByDateCreatedResult']['diffgr:diffgram']['DocumentElement']['DT']

            if not isinstance(dt_element, list):
                dt_element = [dt_element]


            if len(dt_element) > 0:
                for dt in dt_element:
                    vals = {
                        'diffgr_id': dt['@diffgr:id'],
                        'row_order': dt['@msdata:rowOrder'],
                        'prod_id': dt['ProdID'],
                        'prod_name': dt['ProdName'],
                        'prod_desc': dt['ProdDesc'],
                        'prod_type_id': dt['ProdTypeID'],
                        'account_code': dt['AccountCode'],
                        'date_created': self.convert_date_format(dt.get('DateCreated', None)),  # Convert date format
                        'date_modified': self.convert_date_format(dt.get('DateModified', None)),  # Convert date format
                    }

                    exist = self.env['sms.product'].search([('prod_id', '=', vals['prod_id'])])
                    if not exist:
                        self.env['sms.product'].create(vals)
                    else:
                        exist.write(vals)

    def sync_product_view_by_modified(self):
        for rec in self:
    
            soap = """
                POST /odoows/product.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/ProductViewByDateModified"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <ProductViewByDateModified xmlns="http://FMS.dlsud.edu.ph/">
                    <_datemodifiedfrom>dateTime</_datemodifiedfrom>
                    <_datemodifiedto>dateTime</_datemodifiedto>
                    </ProductViewByDateModified>
                </soap:Body>
                </soap:Envelope>
            """

            url = f"http://{rec.host}/fms/odoosync/product.asmx"

            datecreatedfrom = rec.product_date_from.strftime('%Y-%m-%d')
            datecreatedto = rec.product_date_to.strftime('%Y-%m-%d')

            payload = f"""
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <ProductViewByDateModified xmlns="http://FMS.dlsud.edu.ph/">
                    <_datemodifiedfrom>{datecreatedfrom}</_datemodifiedfrom>
                    <_datemodifiedto>{datecreatedto}</_datemodifiedto>
                    </ProductViewByDateModified>
                </soap:Body>
                </soap:Envelope>
            """
            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/ProductViewByDateModified"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            response_dict = xmltodict.parse(xml_content)

            dt_element = response_dict['soap:Envelope']['soap:Body']['ProductViewByDateModifiedResponse']['ProductViewByDateModifiedResult']['diffgr:diffgram']['DocumentElement']['DT']

            if not isinstance(dt_element, list):
                dt_element = [dt_element]


            if len(dt_element) > 0:
                for dt in dt_element:
                    product = {
                        'diffgr_id': dt['@diffgr:id'],
                        'row_order': dt['@msdata:rowOrder'],
                        'prod_id': dt['ProdID'],
                        'prod_name': dt['ProdName'],
                        'prod_desc': dt['ProdDesc'],
                        'prod_type_id': dt['ProdTypeID'],
                        'account_code': dt['AccountCode'],
                        'date_created': self.convert_date_format(dt.get('DateCreated', None)),  # Convert date format
                        'date_modified': self.convert_date_format(dt.get('DateModified', None)),  # Convert date format
                    }

                    exist = self.env['sms.product'].search([('prod_id', '=', product['prod_id'])])
                    if not exist:
                        self.env['sms.product'].create(product)
                    else:
                        exist.write(product)

    def sync_product_view_by_prod_id(self):
        for rec in self:
    
            soap = """
                POST /odoows/product.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: application/soap+xml; charset=utf-8
                Content-Length: length

                <?xml version="1.0" encoding="utf-8"?>
                <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                <soap12:Body>
                    <ProductViewByProdID xmlns="http://FMS.dlsud.edu.ph/">
                    <_prodid>int</_prodid>
                    </ProductViewByProdID>
                </soap12:Body>
                </soap12:Envelope>
            """

            url = f"http://{rec.host}/fms/odoosync/product.asmx"

            payload = f"""
                <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                <soap12:Body>
                    <ProductViewByProdID xmlns="http://FMS.dlsud.edu.ph/">
                    <_prodid>{rec.prod_id}</_prodid>
                    </ProductViewByProdID>
                </soap12:Body>
                </soap12:Envelope>
            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/ProductViewByProdID"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            response_dict = xmltodict.parse(xml_content)

            dt_element = response_dict['soap:Envelope']['soap:Body']['ProductViewByProdIDResponse']['ProductViewByProdIDResult']['diffgr:diffgram']['DocumentElement']['DT']

            if not isinstance(dt_element, list):
                dt_element = [dt_element]


            if len(dt_element) > 0:
                for dt in dt_element:
                    product = {
                        'diffgr_id': dt['@diffgr:id'],
                        'row_order': dt['@msdata:rowOrder'],
                        'prod_id': dt['ProdID'],
                        'prod_name': dt['ProdName'],
                        'prod_desc': dt['ProdDesc'],
                        'prod_type_id': dt['ProdTypeID'],
                        'account_code': dt['AccountCode'],
                        'date_created': self.convert_date_format(dt.get('DateCreated', None)),  # Convert date format
                        'date_modified': self.convert_date_format(dt.get('DateModified', None)),  # Convert date format
                    }

                    exist = self.env['sms.product'].search([('prod_id', '=', product['prod_id'])])
                    if not exist:
                        self.env['sms.product'].create(product)
                    else:
                        exist.write(product)
    
    def sync_product_view_by_prod_type_id(self):
        for rec in self:
    
            soap = """
                POST /odoows/product.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/ProductViewByProdTypeID"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <ProductViewByProdTypeID xmlns="http://FMS.dlsud.edu.ph/">
                    <_prodtypeid>int</_prodtypeid>
                    </ProductViewByProdTypeID>
                </soap:Body>
                </soap:Envelope>
            """

            url = f"http://{rec.host}/fms/odoosync/product.asmx"

            payload = f"""
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <ProductViewByProdTypeID xmlns="http://FMS.dlsud.edu.ph/">
                    <_prodtypeid>{rec.prod_type_id}</_prodtypeid>
                    </ProductViewByProdTypeID>
                </soap:Body>
                </soap:Envelope>
            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/ProductViewByProdTypeID"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            response_dict = xmltodict.parse(xml_content)

            dt_element = response_dict['soap:Envelope']['soap:Body']['ProductViewByProdTypeIDResponse']['ProductViewByProdTypeIDResult']['diffgr:diffgram']['DocumentElement']['DT']

            if not isinstance(dt_element, list):
                dt_element = [dt_element]


            if len(dt_element) > 0:
                for dt in dt_element:
                    product = {
                        'diffgr_id': dt['@diffgr:id'],
                        'row_order': dt['@msdata:rowOrder'],
                        'prod_id': dt['ProdID'],
                        'prod_name': dt['ProdName'],
                        'prod_desc': dt['ProdDesc'],
                        'prod_type_id': dt['ProdTypeID'],
                        'account_code': dt['AccountCode'],
                        'date_created': self.convert_date_format(dt.get('DateCreated', None)),  # Convert date format
                        'date_modified': self.convert_date_format(dt.get('DateModified', None)),  # Convert date format
                    }

                    exist = self.env['sms.product'].search([('prod_id', '=', product['prod_id'])])
                    if not exist:
                        self.env['sms.product'].create(product)
                    else:
                        exist.write(product)
    
    def sync_product_view_by_search(self):
        for rec in self:
    
            soap = """
                POST /odoows/product.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/ProductViewSearch"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <ProductViewSearch xmlns="http://FMS.dlsud.edu.ph/">
                    <_search>string</_search>
                    </ProductViewSearch>
                </soap:Body>
                </soap:Envelope>
            """

            url = f"http://{rec.host}/fms/odoosync/product.asmx"

            payload = f"""
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <ProductViewSearch xmlns="http://FMS.dlsud.edu.ph/">
                    <_search>{rec.product_search}</_search>
                    </ProductViewSearch>
                </soap:Body>
                </soap:Envelope>
            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/ProductViewSearch"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            response_dict = xmltodict.parse(xml_content)

            dt_element = response_dict['soap:Envelope']['soap:Body']['ProductViewSearchResponse']['ProductViewSearchResult']['diffgr:diffgram']['DocumentElement']['DT']

            if not isinstance(dt_element, list):
                dt_element = [dt_element]


            if len(dt_element) > 0:
                for dt in dt_element:
                    product = {
                        'diffgr_id': dt['@diffgr:id'],
                        'row_order': dt['@msdata:rowOrder'],
                        'prod_id': dt['ProdID'],
                        'prod_name': dt['ProdName'],
                        'prod_desc': dt['ProdDesc'],
                        'prod_type_id': dt['ProdTypeID'],
                        'prod_type_desc': dt['prodtypedesc'],
                        'account_code': dt['AccountCode'],
                        'date_created': self.convert_date_format(dt.get('DateCreated', None)),  # Convert date format
                        'date_modified': self.convert_date_format(dt.get('DateModified', None)),  # Convert date format
                    }

                    exist = self.env['sms.product'].search([('prod_id', '=', product['prod_id'])])
                    if not exist:
                        self.env['sms.product'].create(product)
                    else:
                        exist.write(product)

    def sync_product_type_view_by_search(self):
        for rec in self:
    
            soap = """
                POST /odoows/product.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/ProductTypeViewSearch"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <ProductTypeViewSearch xmlns="http://FMS.dlsud.edu.ph/">
                    <_search>string</_search>
                    </ProductTypeViewSearch>
                </soap:Body>
                </soap:Envelope>
            """

            url = f"http://{rec.host}/fms/odoosync/product.asmx"

            payload = f"""
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <ProductTypeViewSearch xmlns="http://FMS.dlsud.edu.ph/">
                    <_search>{rec.product_type_search}</_search>
                    </ProductTypeViewSearch>
                </soap:Body>
                </soap:Envelope>
            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/ProductTypeViewSearch"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            response_dict = xmltodict.parse(xml_content)

            dt_element = response_dict['soap:Envelope']['soap:Body']['ProductTypeViewSearchResponse']['ProductTypeViewSearchResult']['diffgr:diffgram']['DocumentElement']['DT']

            if not isinstance(dt_element, list):
                dt_element = [dt_element]


            if len(dt_element) > 0:
                for dt in dt_element:
                    product = {
                        'diffgr_id': dt['@diffgr:id'],
                        'row_order': dt['@msdata:rowOrder'],
                        'prod_type_id': dt['ProdTypeID'],
                        'prod_type_desc': dt['ProdTypeDesc'],
                    }

                    exist = self.env['sms.product'].search([('prod_type_id', '=', product['prod_type_id'])])
                    if not exist:
                        self.env['sms.product'].create(product)
                    else:
                        exist.write(product)

    # def sync_product_insert(self):
    #     for rec in self:
    
    #         soap = """
    #             POST /odoows/product.asmx HTTP/1.1
    #             Host: 127.0.0.1
    #             Content-Type: text/xml; charset=utf-8
    #             Content-Length: length
    #             SOAPAction: "http://FMS.dlsud.edu.ph/ProductInsert"

    #             <?xml version="1.0" encoding="utf-8"?>
    #             <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    #             <soap:Body>
    #                 <ProductInsert xmlns="http://FMS.dlsud.edu.ph/">
    #                 <_prodname>string</_prodname>
    #                 <_proddesc>string</_proddesc>
    #                 <_prodtypeid>int</_prodtypeid>
    #                 <_prodcode>string</_prodcode>
    #                 <_accountcode>string</_accountcode>
    #                 </ProductInsert>
    #             </soap:Body>
    #             </soap:Envelope>
    #         """



            


