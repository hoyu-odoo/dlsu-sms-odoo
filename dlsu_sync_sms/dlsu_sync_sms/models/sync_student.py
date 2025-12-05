# -*- coding: utf-8 -*-
"""
DLSU SMS Integration - Student Synchronization Module

This module handles the synchronization of student data between the DLSU
Student Management System (SMS) and Odoo. It provides methods to fetch and
sync student records based on various criteria.

Key features:
- Batch processing with configurable limits
- Date-based synchronization
- ID-based and search-based retrieval
- Automatic creation and update of student records
"""

from odoo import models, fields, api
import requests
import xml.etree.ElementTree as ET
import xmltodict
import logging
from datetime import datetime
import pytz

_logger = logging.getLogger(__name__)

class Student(models.Model):
    """
    Model representing a student record synchronized from SMS.

    This model stores enrolled student information retrieved from the SMS system.
    Each student has a unique stud_id that serves as the primary identifier.
    """
    _name = 'sms.student'
    _description = 'SMS Student Record'
    _rec_name = 'stud_id'
    _order = 'date_created desc'

    stud_id = fields.Char('Student ID', index=True, required=True,
                         help='Unique student identifier from SMS')
    lname = fields.Char('Last Name', help='Student last name')
    fname = fields.Char('First Name', help='Student first name')
    mname = fields.Char('Middle Name', help='Student middle name')
    suffix = fields.Char('Suffix', help='Name suffix (Jr., Sr., etc.)')
    gender = fields.Char('Gender', help='Student gender (M/F)')
    date_created = fields.Datetime('Date Created', help='Record creation date in SMS')
    date_modified = fields.Datetime('Date Modified', help='Last modification date in SMS')

class SyncSMSSettingStudent(models.Model):
    """
    Extended settings model for student synchronization.

    Inherits from sync.sms.settings and adds student-specific
    synchronization parameters and methods.
    """
    _inherit = 'sync.sms.settings'

    # Synchronization Parameters
    student_date_from = fields.Date('Date From', help='Start date for date range sync')
    student_date_to = fields.Date('Date To', help='End date for date range sync')
    stud_id = fields.Integer('Student ID', help='Specific student ID to sync')
    student_search = fields.Char('Search', help='Search string for student lookup')

    def sync_student_view_by_date_created(self):
        """
        Synchronize students based on creation date range.

        Fetches students created between student_date_from and student_date_to.
        Processes up to 1000 records per sync to prevent timeout issues.
        Creates new records or updates existing ones based on stud_id.

        The method uses the SOAP endpoint: StudentViewByDateCreated
        """
        for rec in self:
            url = f"http://{rec.host}/fms/odoosync/student.asmx"


            datecreatedfrom = rec.student_date_from.strftime('%Y-%m-%d')
            datecreatedto = rec.student_date_to.strftime('%Y-%m-%d')

            payload = f"""
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <StudentViewByDateCreated xmlns="http://FMS.dlsud.edu.ph/">
                    <_datecreatedfrom>{datecreatedfrom}</_datecreatedfrom>
                    <_datecreatedto>{datecreatedto}</_datecreatedto>
                    </StudentViewByDateCreated>
                </soap:Body>
                </soap:Envelope>
            """

            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': '"http://FMS.dlsud.edu.ph/StudentViewByDateCreated"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')

            # Convert XML content to dictionary
            response_dict = xmltodict.parse(xml_content)

            # Access the 'DT' element within 'DocumentElement'
            dt_element = response_dict['soap:Envelope']['soap:Body']['StudentViewByDateCreatedResponse']['StudentViewByDateCreatedResult']['diffgr:diffgram']['DocumentElement']['DT']

            # Check if 'DT' is a list, if not, convert it to a list
            if not isinstance(dt_element, list):
                dt_element = [dt_element]

            # Process up to 1000 records to prevent timeout
            count = 0

            # Iterate through the list of students
            for dt in dt_element:
                if count >= 1000:
                    _logger.info("Reached 1000 record limit, stopping sync")
                    break

                student_id = dt['StudID']
                exist = self.env['sms.student'].search([('stud_id', '=', student_id)])

                if not exist:
                    student = {
                        'stud_id': student_id,
                        'lname': dt['LName'],
                        'fname': dt['FName'],
                        'mname': dt.get('MName') or None,
                        'suffix': dt.get('Suffix') or None,
                        'gender': dt.get('Gender') or None,
                        'date_created': self.convert_date_format(dt.get('DateCreated', None)),  # Convert date format
                        'date_modified': self.convert_date_format(dt.get('DateModified', None)),  # Convert date format
                    }
                    self.env['sms.student'].create(student)
                    count += 1

                else:
                    # Update existing student record
                    student = {
                        'lname': dt['LName'],
                        'fname': dt['FName'],
                        'mname': dt.get('MName') or None,
                        'suffix': dt.get('Suffix') or None,
                        'gender': dt.get('Gender') or None,
                        'date_created': self.convert_date_format(dt.get('DateCreated', None)),  # Convert date format
                        'date_modified': self.convert_date_format(dt.get('DateModified', None)),  # Convert date format
                    }
                    exist.write(student)

    
    def sync_student_view_by_date_modified(self):
        for rec in self:
            soap = """
                POST /odoows/student.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/StudentViewByDateModified"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <StudentViewByDateModified xmlns="http://FMS.dlsud.edu.ph/">
                    <_datemodifiedfrom>dateTime</_datemodifiedfrom>
                    <_datemodifiedto>dateTime</_datemodifiedto>
                    </StudentViewByDateModified>
                </soap:Body>
                </soap:Envelope>
            """

            # url = f"http://{rec.host}/odoows/student.asmx"
            url = f"http://{rec.host}/fms/odoosync/student.asmx"

            datemodifiedfrom = rec.student_date_from.strftime('%Y-%m-%d')
            datemodifiedto = rec.student_date_to.strftime('%Y-%m-%d')

            payload = f""" 
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <StudentViewByDateModified xmlns="http://FMS.dlsud.edu.ph/">
                    <_datemodifiedfrom>{datemodifiedfrom}</_datemodifiedfrom>
                    <_datemodifiedto>{datemodifiedto}</_datemodifiedto>
                    </StudentViewByDateModified>
                </soap:Body>
                </soap:Envelope>
            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/StudentViewByDateModified"',
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')

            # Convert XML content to dictionary
            response_dict = xmltodict.parse(xml_content)

            # Access the 'DT' element within 'DocumentElement'
            dt_element = response_dict['soap:Envelope']['soap:Body']['StudentViewByDateModifiedResponse']['StudentViewByDateModifiedResult']['diffgr:diffgram']['DocumentElement']['DT']

            # Check if 'DT' is a list, if not, convert it to a list
            if not isinstance(dt_element, list):
                dt_element = [dt_element]

            # Iterate through the list of student
            if len(dt_element) > 0:
                for dt in dt_element:
                    student = {
                        'stud_id': dt['StudID'],
                        'lname': dt['LName'],
                        'fname': dt['FName'],
                        'mname': dt['MName'],
                        'suffix': dt['Suffix'],
                        'gender': dt['Gender'],
                        'date_created': self.convert_date_format(dt.get('DateCreated', None)),  # Convert date format
                        'date_modified': self.convert_date_format(dt.get('DateModified', None)),  # Convert date format
                    }

                    exist = self.env['sms.student'].search([('stud_id', '=', student['stud_id'])])
                    if not exist:
                        self.env['sms.student'].create(student)
                    else:
                        exist.write(student)

    def sync_student_view_by_id(self):
        for rec in self:

            soap = """ 
                POST /odoows/student.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: text/xml; charset=utf-8
                Content-Length: length
                SOAPAction: "http://FMS.dlsud.edu.ph/StudentViewByID"

                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <StudentViewByID xmlns="http://FMS.dlsud.edu.ph/">
                    <_id>int</_id>
                    </StudentViewByID>
                </soap:Body>
                </soap:Envelope>
            """

            # url = f"http://{rec.host}/odoows/student.asmx"
            url = f"http://{rec.host}/fms/odoosync/student.asmx"

            payload = f"""
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <StudentViewByID xmlns="http://FMS.dlsud.edu.ph/">
                    <_id>{rec.stud_id}</_id>
                    </StudentViewByID>
                </soap:Body>
                </soap:Envelope>

            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/StudentViewByID"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            # Convert XML content to dictionary
            response_dict = xmltodict.parse(xml_content)

            # Access the 'DT' element within 'DocumentElement'
            dt_element = response_dict['soap:Envelope']['soap:Body']['StudentViewByIDResponse']['StudentViewByIDResult']['diffgr:diffgram']['DocumentElement']['DT']

            # Check if 'DT' is a list, if not, convert it to a list
            if not isinstance(dt_element, list):
                dt_element = [dt_element]

            # Iterate through the list of student
            if len(dt_element) > 0:
                for dt in dt_element:
                    student = {
                        'stud_id': dt['StudID'],
                        'lname': dt['LName'],
                        'fname': dt['FName'],
                        'mname': dt['MName'],
                        'suffix': dt['Suffix'],
                        'gender': dt['Gender'],
                        'date_created': self.convert_date_format(dt.get('DateCreated', None)),  # Convert date format
                        'date_modified': self.convert_date_format(dt.get('DateModified', None)),  # Convert date format
                    }

                    exist = self.env['sms.student'].search([('stud_id', '=', student['stud_id'])])
                    if not exist:
                        self.env['sms.student'].create(student)
                    else:
                        exist.write(student)

    def sync_student_view_search(self):
        for rec in self:

            soap = """ 
                POST /odoows/student.asmx HTTP/1.1
                Host: 127.0.0.1
                Content-Type: application/soap+xml; charset=utf-8
                Content-Length: length

                <?xml version="1.0" encoding="utf-8"?>
                <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                <soap12:Body>
                    <StudentViewSearch xmlns="http://FMS.dlsud.edu.ph/">
                    <_search>string</_search>
                    </StudentViewSearch>
                </soap12:Body>
                </soap12:Envelope>
            """

            # url = f"http://{rec.host}/odoows/student.asmx"
            url = f"http://{rec.host}/fms/odoosync/student.asmx"

            payload = f"""
                <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                <soap12:Body>
                    <StudentViewSearch xmlns="http://FMS.dlsud.edu.ph/">
                    <_search>{rec.student_search}</_search>
                    </StudentViewSearch>
                </soap12:Body>
                </soap12:Envelope>
            """

            headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://FMS.dlsud.edu.ph/StudentViewSearch"'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            xml_content = response.content.decode('utf-8')
            # Convert XML content to dictionary
            response_dict = xmltodict.parse(xml_content)

             # Access the 'DT' element within 'DocumentElement'
            dt_element = response_dict['soap:Envelope']['soap:Body']['StudentViewSearchResponse']['StudentViewSearchResult']['diffgr:diffgram']['DocumentElement']['DT']

            # Check if 'DT' is a list, if not, convert it to a list
            if not isinstance(dt_element, list):
                dt_element = [dt_element]

            # Iterate through the list of student
            if len(dt_element) > 0:
                for dt in dt_element:
                    student = {
                        'stud_id': dt['StudID'],
                        'lname': dt['LName'],
                        'fname': dt['FName'],
                        'mname': dt['MName'],
                        'suffix': dt['Suffix'],
                        'gender': dt['Gender'],
                        'date_created': self.convert_date_format(dt.get('DateCreated', None)),  # Convert date format
                        'date_modified': self.convert_date_format(dt.get('DateModified', None)),  # Convert date format
                    }

                    exist = self.env['sms.student'].search([('stud_id', '=', student['stud_id'])])
                    if not exist:
                        self.env['sms.student'].create(student)
                    else:
                        exist.write(student)