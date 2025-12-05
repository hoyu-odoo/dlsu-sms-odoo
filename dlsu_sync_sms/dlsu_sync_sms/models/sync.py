# -*- coding: utf-8 -*-
"""
DLSU SMS Integration Module - Core Synchronization Settings

This module provides the core configuration model for synchronizing data between
Odoo and the DLSU Student Management System (SMS) via SOAP web services.

The integration supports:
- Applicant data synchronization
- Student information management
- Product/fee synchronization
- Invoice generation and updates
- Payment reconciliation

All communications use SOAP protocol with XML payloads.
"""

from odoo import models, fields, api
import requests
import xml.etree.ElementTree as ET
import xmltodict
import logging
from datetime import datetime
import pytz

_logger = logging.getLogger(__name__)


class SyncSMSSettings(models.Model):
    """
    Core configuration model for SMS synchronization settings.

    This model stores the connection parameters and provides utility methods
    for all SMS sync operations. It serves as the base model that other
    sync models inherit from.

    Attributes:
        name: Configuration name for identification
        host: SMS web service host URL/IP
        port: Service port number (default: 80)
        user: Authentication username (if required)
        password: Authentication password (if required)
        default: Flag to mark this as the default configuration
    """
    _name = 'sync.sms.settings'
    _description = 'SMS Synchronization Settings'

    # Connection Configuration
    name = fields.Char('Name', required=True, help='Configuration identifier')
    host = fields.Char('Host', required=True, help='SMS web service host address')
    port = fields.Integer('Port', default=80, help='Service port number')
    user = fields.Char('User', help='Authentication username')
    password = fields.Char('Password', help='Authentication password')
    default = fields.Boolean('Default', help='Use as default configuration')


    def convert_date_format(self, date_str):
        """
        Convert SOAP date format to Odoo datetime format.

        Handles multiple SOAP date formats:
        - With milliseconds: YYYY-MM-DDTHH:MM:SS.fff+ZZZZ
        - Without milliseconds: YYYY-MM-DDTHH:MM:SS+ZZZZ

        Args:
            date_str: Date string from SOAP response

        Returns:
            str: Odoo-formatted datetime string (UTC) or None if parsing fails
        """
        if not isinstance(date_str, str) or not date_str:
            return None

        try:
            # Try parsing with milliseconds first
            soap_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%f%z')
        except ValueError:
            try:
                # Fallback to parsing without milliseconds
                soap_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S%z')
            except ValueError:
                _logger.warning(f"Unable to parse date: {date_str}")
                return None

        # Convert to UTC and format for Odoo
        odoo_date = soap_date.astimezone(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S')
        return odoo_date




    def sync_test(self):
        """
        Test method to verify SMS web service connectivity.

        Performs a test search for applicants with 'mendez' as the search term.
        This method is used to validate the connection settings and ensure
        the SOAP service is responding correctly.

        The test will:
        1. Build a SOAP request to search for applicants
        2. Send the request to the configured SMS endpoint
        3. Parse the XML response
        4. Extract applicant data (but not save to database)

        Raises:
            Exception: If connection fails or response is invalid
        """
        for rec in self:
            url = f"http://{rec.host}/fms/odoosync/applicant.asmx"

            payload = """
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <ApplicantViewSearch xmlns="http://FMS.dlsud.edu.ph/">
        <_search>mendez</_search>
        </ApplicantViewSearch>
    </soap:Body>
    </soap:Envelope>
    """
            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/ApplicantViewSearch"'
            }

            try:
                response = requests.request("POST", url, headers=headers, data=payload)
                xml_content = response.content.decode('utf-8')
                response_dict = xmltodict.parse(xml_content)

                # Navigate to the data element in SOAP response
                dt_element = response_dict['soap:Envelope']['soap:Body']['ApplicantViewSearchResponse']['ApplicantViewSearchResult']['diffgr:diffgram']['DocumentElement']['DT']

                # Ensure dt_element is a list for consistent processing
                if not isinstance(dt_element, list):
                    dt_element = [dt_element]

                # Extract applicant data for validation
                applicant_list = []
                for dt in dt_element:
                    applicant = {
                        'ApplicantID': dt['ApplicantID'],
                        'Lname': dt['Lname'],
                        'Fname': dt['Fname'],
                        'Mname': dt['Mname'],
                        'Suffix': dt['Suffix'],
                        'DateCreated': dt.get('DateCreated', None),
                        'StudentID': dt.get('StudentID', None)
                    }
                    applicant_list.append(applicant)

                _logger.info(f"Test successful: Found {len(applicant_list)} applicants")

            except Exception as e:
                _logger.error(f"SMS connection test failed: {str(e)}")
                raise



