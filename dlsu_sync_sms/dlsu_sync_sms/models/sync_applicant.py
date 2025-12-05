# -*- coding: utf-8 -*-
"""
DLSU SMS Integration - Applicant Synchronization Module

This module handles the synchronization of applicant data between the DLSU
Student Management System (SMS) and Odoo. It provides methods to fetch and
sync applicant records based on various criteria:

- By date created
- By date modified
- By applicant ID
- By search string

The module maintains a local copy of applicant records in Odoo for use in
admissions and enrollment processes.
"""

from odoo import models, fields, api
import requests
import xml.etree.ElementTree as ET
import xmltodict
import logging
from datetime import datetime
import pytz

_logger = logging.getLogger(__name__)


class Applicant(models.Model):
    """
    Model representing an applicant record synchronized from SMS.

    This model stores applicant information retrieved from the SMS system.
    Each applicant has a unique applicant_id that serves as the primary
    identifier for synchronization purposes.
    """
    _name = 'sms.applicant'
    _description = 'SMS Applicant Record'
    _rec_name = 'applicant_id'
    _order = 'date_created desc'

    applicant_id = fields.Char('Applicant ID', index=True, required=True,
                              help='Unique identifier from SMS system')
    lname = fields.Char('Last Name', help='Applicant last name')
    fname = fields.Char('First Name', help='Applicant first name')
    mname = fields.Char('Middle Name', help='Applicant middle name')
    suffix = fields.Char('Suffix', help='Name suffix (Jr., Sr., etc.)')
    date_created = fields.Datetime('Date Created', help='Record creation date in SMS')
    date_modified = fields.Datetime('Date Modified', help='Last modification date in SMS')
    student_id = fields.Char('Student ID', help='Assigned student ID if enrolled')


class SyncSMSSettingApplicant(models.Model):
    """
    Extended settings model for applicant synchronization.

    Inherits from sync.sms.settings and adds applicant-specific
    synchronization parameters and methods.
    """
    _inherit = 'sync.sms.settings'

    # Synchronization Parameters
    applicant_date_from = fields.Date('Date From', help='Start date for date range sync')
    applicant_date_to = fields.Date('Date To', help='End date for date range sync')
    applicant_id = fields.Integer('Applicant ID', help='Specific applicant ID to sync')
    applicant_search = fields.Char('Search', help='Search string for applicant lookup')



    def sync_applicant_view_by_date_created(self):
        """
        Synchronize applicants based on creation date range.

        Fetches all applicants created between applicant_date_from and
        applicant_date_to from the SMS system. Creates new records or
        updates existing ones based on applicant_id.

        The method uses the SOAP endpoint: ApplicantViewByDateCreated
        """
        for rec in self:
            url = f"http://{rec.host}/fms/odoosync/applicant.asmx"
            

            datecreatedfrom = rec.applicant_date_from.strftime('%Y-%m-%d')
            datecreatedto = rec.applicant_date_to.strftime('%Y-%m-%d')

            payload = f"""
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ApplicantViewByDateCreated xmlns="http://FMS.dlsud.edu.ph/">
      <_datecreatedfrom>{datecreatedfrom}</_datecreatedfrom>
      <_datecreatedto>{datecreatedto}</_datecreatedto>
    </ApplicantViewByDateCreated>
  </soap:Body>
</soap:Envelope>
    """
            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/ApplicantViewByDateCreated"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            # Convert XML content to dictionary
            response_dict = xmltodict.parse(xml_content)

            # Access the 'DT' element within 'DocumentElement'
            dt_element = response_dict['soap:Envelope']['soap:Body']['ApplicantViewByDateCreatedResponse']['ApplicantViewByDateCreatedResult']['diffgr:diffgram']['DocumentElement']['DT']

            # Check if 'DT' is a list, if not, convert it to a list
            if not isinstance(dt_element, list):
                dt_element = [dt_element]

            # Iterate through the list of applicants
            if len(dt_element) > 0:
                for dt in dt_element:
                    applicant = {
                        'applicant_id': dt['ApplicantID'],
                        'lname': dt['Lname'],
                        'fname': dt['Fname'],
                        'mname': dt['Mname'],
                        'suffix': dt['Suffix'],
                        'date_created': self.convert_date_format(dt.get('DateCreated', None)),  # Convert date format
                        'date_modified': self.convert_date_format(dt.get('DateModified', None)),  # Convert date format
                        'student_id': dt.get('StudentID', None)
                    }

                    exist = self.env['sms.applicant'].search([('applicant_id', '=', applicant['applicant_id'])])
                    if not exist:
                        self.env['sms.applicant'].create(applicant)
                    else:
                        exist.write(applicant)


    def sync_applicant_view_by_date_modified(self):
        """
        Synchronize applicants based on modification date range.

        Fetches all applicants modified between applicant_date_from and
        applicant_date_to from the SMS system. Updates existing records
        or creates new ones if they don't exist.

        The method uses the SOAP endpoint: ApplicantViewByDateModified
        """
        for rec in self:

            soap = """
POST /odoows/applicant.asmx HTTP/1.1
Host: 127.0.0.1
Content-Type: text/xml; charset=utf-8
Content-Length: length
SOAPAction: "http://FMS.dlsud.edu.ph/ApplicantViewByDateModified"

<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ApplicantViewByDateModified xmlns="http://FMS.dlsud.edu.ph/">
      <_datemodifiedfrom>dateTime</_datemodifiedfrom>
      <_datemodifiedto>dateTime</_datemodifiedto>
    </ApplicantViewByDateModified>
  </soap:Body>
</soap:Envelope>
"""
    
            # url = f"http://{rec.host}/odoows/applicant.asmx"
            url = f"http://{rec.host}/fms/odoosync/applicant.asmx"

            datemodifiedfrom = rec.applicant_date_from.strftime('%Y-%m-%d')
            datemodifiedto = rec.applicant_date_to.strftime('%Y-%m-%d')

            payload = f"""
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
<soap:Body>
    <ApplicantViewByDateModified xmlns="http://FMS.dlsud.edu.ph/">
    <_datemodifiedfrom>{datemodifiedfrom}</_datemodifiedfrom>
    <_datemodifiedto>{datemodifiedto}</_datemodifiedto>
    </ApplicantViewByDateModified>
</soap:Body>
</soap:Envelope>
    """
            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/ApplicantViewByDateModified"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            # Convert XML content to dictionary
            response_dict = xmltodict.parse(xml_content)

            # Access the 'DT' element within 'DocumentElement'
            dt_element = response_dict['soap:Envelope']['soap:Body']['ApplicantViewByDateModifiedResponse']['ApplicantViewByDateModifiedResult']['diffgr:diffgram']['DocumentElement']['DT']

            # Check if 'DT' is a list, if not, convert it to a list
            if not isinstance(dt_element, list):
                dt_element = [dt_element]

            # Iterate through the list of applicants
            if len(dt_element) > 0:
                for dt in dt_element:
                    applicant = {
                        'applicant_id': dt['ApplicantID'],
                        'lname': dt['Lname'],
                        'fname': dt['Fname'],
                        'mname': dt['Mname'],
                        'suffix': dt['Suffix'],
                        'date_created': self.convert_date_format(dt.get('DateCreated', None)),  # Convert date format
                        'date_modified': self.convert_date_format(dt.get('DateModified', None)),  # Convert date format
                        'student_id': dt.get('StudentID', None)
                    }

                    exist = self.env['sms.applicant'].search([('applicant_id', '=', applicant['applicant_id'])])
                    if not exist:
                        self.env['sms.applicant'].create(applicant)
                    else:
                        exist.write(applicant)

                    
    def sync_applicant_view_by_id(self):
        """
        Synchronize a specific applicant by ID.

        Fetches a single applicant record from SMS using the applicant_id
        field. Useful for updating specific applicant records on demand.

        The method uses the SOAP endpoint: ApplicantViewByID
        """
        for rec in self:

            soap = """
POST /odoows/applicant.asmx HTTP/1.1
Host: 127.0.0.1
Content-Type: text/xml; charset=utf-8
Content-Length: length
SOAPAction: "http://FMS.dlsud.edu.ph/ApplicantViewByID"

<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ApplicantViewByID xmlns="http://FMS.dlsud.edu.ph/">
      <_applicantid>int</_applicantid>
    </ApplicantViewByID>
  </soap:Body>
</soap:Envelope>
"""
    
            # url = f"http://{rec.host}/odoows/applicant.asmx"
            url = f"http://{rec.host}/fms/odoosync/applicant.asmx"

            payload = f"""
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
<soap:Body>
    <ApplicantViewByID xmlns="http://FMS.dlsud.edu.ph/">
    <_applicantid>{rec.applicant_id}</_applicantid>
    </ApplicantViewByID>
</soap:Body>

</soap:Envelope>
    """
            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/ApplicantViewByID"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            # Convert XML content to dictionary
            response_dict = xmltodict.parse(xml_content)

            # Access the 'DT' element within 'DocumentElement'
            dt_element = response_dict['soap:Envelope']['soap:Body']['ApplicantViewByIDResponse']['ApplicantViewByIDResult']['diffgr:diffgram']['DocumentElement']['DT']

            # Check if 'DT' is a list, if not, convert it to a list
            if not isinstance(dt_element, list):
                dt_element = [dt_element]

            # Iterate through the list of applicants
            if len(dt_element) > 0:
                for dt in dt_element:
                    applicant = {
                        'applicant_id': dt['ApplicantID'],
                        'lname': dt['Lname'],
                        'fname': dt['Fname'],
                        'mname': dt['Mname'],
                        'suffix': dt['Suffix'],
                        'date_created': self.convert_date_format(dt.get('DateCreated', None)),  # Convert date format
                        'date_modified': self.convert_date_format(dt.get('DateModified', None)),  # Convert date format
                        'student_id': dt.get('StudentID', None)
                    }

                    exist = self.env['sms.applicant'].search([('applicant_id', '=', applicant['applicant_id'])])
                    if not exist:
                        self.env['sms.applicant'].create(applicant)
                    else:
                        exist.write(applicant)

    def sync_applicant_view_search(self):
        """
        Search and synchronize applicants by text search.

        Searches for applicants in SMS using the applicant_search field
        as the search criteria. Can search across name fields.

        The method uses the SOAP endpoint: ApplicantViewSearch
        """
        for rec in self:

            soap = """
POST /odoows/applicant.asmx HTTP/1.1
Host: 127.0.0.1
Content-Type: text/xml; charset=utf-8
Content-Length: length
SOAPAction: "http://FMS.dlsud.edu.ph/ApplicantViewSearch"

<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ApplicantViewSearch xmlns="http://FMS.dlsud.edu.ph/">
      <_search>string</_search>
    </ApplicantViewSearch>
  </soap:Body>
</soap:Envelope>
"""
    
            # url = f"http://{rec.host}/odoows/applicant.asmx"
            url = f"http://{rec.host}/fms/odoosync/applicant.asmx"

            payload = f"""
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
<soap:Body>
    <ApplicantViewSearch xmlns="http://FMS.dlsud.edu.ph/">
    <_search>{rec.applicant_search}</_search>
    </ApplicantViewSearch>
</soap:Body>

</soap:Envelope>
    """
            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/ApplicantViewSearch"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            # Convert XML content to dictionary
            response_dict = xmltodict.parse(xml_content)

            # Access the 'DT' element within 'DocumentElement'
            dt_element = response_dict['soap:Envelope']['soap:Body']['ApplicantViewSearchResponse']['ApplicantViewSearchResult']['diffgr:diffgram']['DocumentElement']['DT']

            # Check if 'DT' is a list, if not, convert it to a list
            if not isinstance(dt_element, list):
                dt_element = [dt_element]

            # Iterate through the list of applicants
            if len(dt_element) > 0:
                for dt in dt_element:
                    applicant = {
                        'applicant_id': dt['ApplicantID'],
                        'lname': dt['Lname'],
                        'fname': dt['Fname'],
                        'mname': dt['Mname'],
                        'suffix': dt['Suffix'],
                        'date_created': self.convert_date_format(dt.get('DateCreated', None)),  # Convert date format
                        'date_modified': self.convert_date_format(dt.get('DateModified', None)),  # Convert date format
                        'student_id': dt.get('StudentID', None)
                    }

                    exist = self.env['sms.applicant'].search([('applicant_id', '=', applicant['applicant_id'])])
                    if not exist:
                        self.env['sms.applicant'].create(applicant)
                    else:
                        exist.write(applicant)

    