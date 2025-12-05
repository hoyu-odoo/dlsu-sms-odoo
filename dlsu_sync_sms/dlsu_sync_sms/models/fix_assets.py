# -*- coding: utf-8 -*-
"""
DLSU SMS Integration - Fixed Assets Management Module

This module provides utilities for managing fixed assets synchronization
and bulk operations on asset records. It includes methods for:

- Resetting closed assets back to draft
- Disposing of assets in bulk
- Reversing asset depreciation entries
- Updating account analytic data on asset lines
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

_logger = logging.getLogger(__name__)

class SyncSMSSettingFA(models.Model):
    """
    Extension of SMS settings for fixed assets operations.

    Provides bulk operations for managing fixed assets and their
    associated accounting entries.
    """
    _inherit = 'sync.sms.settings'

    asset_id_list = fields.Text(help="List of asset IDs (one per line) for bulk operations")
    account_id_list = fields.Text(help="List of account codes (one per line) for bulk updates")

    def reset_closed_assets_to_draft(self):
        """
        Reset closed assets back to draft state.

        This method:
        1. Cancels all journal entries linked to the asset
        2. Removes asset references from the journal entries
        3. Sets the asset back to draft state
        """
        for rec in self:
            list_of_asset_id = [asset_id.strip() for asset_id in rec.asset_id_list.split('\n') if asset_id.strip().isdigit()]

            for asset_id in list_of_asset_id:
                account_assets = self.env['account.asset'].search([('id', '=', int(asset_id))])

                for asset in account_assets:
                    if asset.state == 'close':
                        _logger.info(f"Resetting closed asset to draft: {asset.name} (ID: {asset.id})")
                        # Cancel all account moves linked to this asset
                        moves = self.env['account.move'].search([('asset_id', '=', asset.id)])
                        for move in moves:
                            if move:
                                move.jv_button_cancel()
                                move.button_draft()
                                move.write({'asset_id': False})

                        # Set asset back to draft state
                        asset.set_to_draft()
        self.env.cr.commit()

    def dispose_draft_assets(self):
        """
        Process draft assets through disposal workflow.

        This method:
        1. Validates draft assets (sets to running state)
        2. Initiates disposal process
        3. Creates and posts disposal journal entries
        """
        for rec in self:
            list_of_asset_id = [asset_id.strip() for asset_id in rec.asset_id_list.split('\n') if asset_id.strip().isdigit()]

            for asset_id in list_of_asset_id:
                account_assets = self.env['account.asset'].search([('id', '=', int(asset_id))])

                for asset in account_assets:
                    _logger.info(f"Processing asset for disposal: {asset.name} (ID: {asset.id})")
                    if asset.state == 'draft':
                        # Validate asset (draft to running)
                        asset.validate()
                        # Initiate close/disposal process
                        asset.action_set_to_close()

                        # Create and confirm asset disposal
                        wizard = self.env['account.asset.sell'].create({
                            'asset_id': asset.id,
                            'action': 'dispose',
                        })
                        wizard.do_action()

                        # Find the newly created account move
                        new_moves = self.env['account.move'].search([
                            ('asset_id', '=', asset.id),
                            ('state', '=', 'draft')
                        ])

                        # Submit the disposal journal entry for approval
                        new_moves.jv_action_submit()
        self.env.cr.commit()

    def reverse_open_assets_to_draft(self):
        """
        Reverse open assets back to draft state.

        This method:
        1. Finds and cancels all depreciation journal entries
        2. Cancels any reversal entries
        3. Unlinks entries from the asset
        4. Sets asset back to draft state
        """
        for rec in self:
            list_of_asset_id = [asset_id.strip() for asset_id in rec.asset_id_list.split('\n') if asset_id.strip().isdigit()]

            for asset_id in list_of_asset_id:
                account_assets = self.env['account.asset'].search([('id', '=', int(asset_id))])

                for asset in account_assets:
                    if asset.state == 'open':
                        _logger.info(f"Reversing open asset to draft: {asset.name} (ID: {asset.id})")
                        asset.set_to_draft()

                        # Find all posted depreciation entries
                        moves = self.env['account.move'].search([('asset_id', '=', asset.id), ('state', '=', 'posted')])

                        for move in moves:
                            # Find any reversal entries
                            reversals = self.env['account.move'].search([('ref', 'ilike', "Reversal of: " + move.name)])

                            # Cancel reversal entries
                            for reversal in reversals:
                                reversal.button_draft()
                                reversal.button_cancel()

                            # Cancel the original depreciation entry
                            move.button_draft()
                            move.button_cancel()

                            # Remove asset reference from all related entries
                            (move + reversals).write({'asset_id': False})

        self.env.cr.commit()

    def validate_draft_assets(self):
        """
        Validate draft assets and compute depreciation.

        This method:
        1. Computes depreciation board for draft assets
        2. Validates assets to set them to running state
        """
        for rec in self:
            list_of_asset_id = [asset_id.strip() for asset_id in rec.asset_id_list.split('\n') if asset_id.strip().isdigit()]

            for asset_id in list_of_asset_id:
                account_assets = self.env['account.asset'].search([('id', '=', int(asset_id))])

                for asset in account_assets:
                    _logger.info(f"Validating draft asset: {asset.name} (ID: {asset.id})")
                    if asset.state == 'draft':
                        asset.compute_depreciation_board()
                        asset.validate()

        self.env.cr.commit()


    def update_analytic_data_bulk(self):
        """
        Update account analytic data on journal entry lines.

        This method updates fund accounts, analytic accounts, and tags
        on journal entry lines based on their account configuration.

        Returns:
            dict: Action to display notification with update summary
        """
        summary = []

        for rec in self:
            list_of_account_id = [account_id.strip() for account_id in rec.account_id_list.split('\n') if account_id.strip().isdigit()]

            for account_code in list_of_account_id:
                accounts = self.env['account.account'].search([('code', '=', int(account_code))])

                for account in accounts:
                    account_lines = self.env['account.move.line'].search([('account_id', '=', account.id)])

                    for line in account_lines:
                        updates = {}

                        if not line.fund_account and account.fund_account_id:
                            updates['fund_account'] = account.fund_account_id.id

                        if not line.analytic_account_id and account.account_analytic_id:
                            updates['analytic_account_id'] = account.account_analytic_id.id

                        if not line.analytic_tag_ids and account.analytic_tag_ids:
                            updates['analytic_tag_ids'] = [(6, 0, account.analytic_tag_ids.ids)]

                        if updates:
                            line.sudo().write(updates)
                            summary.append(f"Updated Line: {line.move_name or f'ID {line.id}'}")
                            _logger.info(f"Updated journal line {line.id} with analytic data from account {account.code}")

        summary_text = "\n".join(summary) if summary else "No lines needed updating."
        if summary:
            _logger.info(f"Completed analytic data update for {len(summary)} lines")

        self.env.cr.commit()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Update Summary',
                'message': summary_text,
                'type': 'success',
                'sticky': False,
            }
        }