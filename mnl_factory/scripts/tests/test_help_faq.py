#!/usr/bin/env python3
"""Tests for the in-CLI Help & FAQ menu."""

import unittest
from unittest.mock import MagicMock, patch

from tests.support import r1setup


def _make_app():
    app = r1setup.R1Setup.__new__(r1setup.R1Setup)
    app.config_manager = MagicMock()
    app.config_manager.active_config = {}
    app.print_header = MagicMock()
    app.print_section = MagicMock()
    app.print_colored = MagicMock()
    app.wait_for_enter = MagicMock()
    return app


def _rendered_text(app) -> str:
    return " ".join(str(call.args[0]) for call in app.print_colored.call_args_list if call.args)


class TestHelpFaqMenu(unittest.TestCase):
    def test_main_menu_renders_help_option(self):
        app = _make_app()
        app._load_active_config = MagicMock()
        app.check_hosts_config = MagicMock(return_value=False)
        app.has_active_config_shell = MagicMock(return_value=False)
        app.load_configuration = MagicMock()
        app.get_mnl_app_env = MagicMock(return_value=None)
        app._get_deployment_display_state = MagicMock(return_value={'main_menu_text': 'not deployed'})
        app._get_suggested_action = MagicMock(return_value=('', ''))

        app.show_main_menu()

        rendered = _rendered_text(app)
        self.assertIn("8) Help & FAQ", rendered)
        self.assertIn("For concepts, open 8) Help & FAQ", rendered)

    def test_main_loop_dispatches_help_without_active_config(self):
        app = _make_app()
        app.check_ansible_installation = MagicMock(return_value=True)
        app._auto_update_check = MagicMock()
        app.migrate_legacy_ssh_metadata = MagicMock()
        app.ensure_active_configuration = MagicMock(return_value=True)
        app.check_hosts_config = MagicMock(return_value=False)
        app._offer_startup_service_update = MagicMock()
        app.show_main_menu = MagicMock()
        app.get_input = MagicMock(side_effect=['8', '0'])
        app.help_faq_menu = MagicMock()

        with patch.object(r1setup.sys, 'argv', ['r1setup']):
            app.run()

        app.help_faq_menu.assert_called_once()
        rendered = _rendered_text(app)
        self.assertNotIn("No active configuration.", rendered)

    def test_invalid_main_menu_choice_mentions_0_to_8(self):
        app = _make_app()
        app.check_ansible_installation = MagicMock(return_value=True)
        app._auto_update_check = MagicMock()
        app.migrate_legacy_ssh_metadata = MagicMock()
        app.ensure_active_configuration = MagicMock(return_value=True)
        app.check_hosts_config = MagicMock(return_value=False)
        app._offer_startup_service_update = MagicMock()
        app.show_main_menu = MagicMock()
        app.get_input = MagicMock(side_effect=['9', '0'])
        app.help_faq_menu = MagicMock()

        with patch.object(r1setup.sys, 'argv', ['r1setup']):
            app.run()

        rendered = _rendered_text(app)
        self.assertIn("Invalid option. Valid choices are 0-8.", rendered)

    def test_first_run_no_config_path_can_open_help(self):
        app = _make_app()
        app._ensure_hosts_yml_linked = MagicMock()
        app.has_active_config_shell = MagicMock(return_value=False)
        app._restore_active_configuration_if_possible = MagicMock(return_value=False)
        app._list_available_configs = MagicMock(return_value=[])
        app.get_input = MagicMock(side_effect=['3', '0'])
        app.help_faq_menu = MagicMock()
        app._create_machine_first_configuration = MagicMock()
        app._import_configuration = MagicMock()

        result = app.ensure_active_configuration()

        self.assertFalse(result)
        app.help_faq_menu.assert_called_once()
        app._create_machine_first_configuration.assert_not_called()
        app._import_configuration.assert_not_called()

    def test_multiple_saved_configs_path_can_open_help(self):
        app = _make_app()
        app._ensure_hosts_yml_linked = MagicMock()
        app.has_active_config_shell = MagicMock(return_value=False)
        app._restore_active_configuration_if_possible = MagicMock(return_value=False)
        app._list_available_configs = MagicMock(return_value=[
            ('prod.yml', {
                'environment': 'mainnet',
                'nodes_count': 1,
                'machines_count': 1,
                'created_at': '2026-01-01T00:00:00',
                'deployment_status': 'never_deployed',
            }),
            ('test.yml', {
                'environment': 'testnet',
                'nodes_count': 0,
                'machines_count': 1,
                'created_at': '2026-01-02T00:00:00',
                'deployment_status': 'never_deployed',
            }),
        ])
        app.get_input = MagicMock(side_effect=['4', '0'])
        app.help_faq_menu = MagicMock()
        app._create_machine_first_configuration = MagicMock()
        app._import_configuration = MagicMock()
        app._load_config_by_name = MagicMock()

        result = app.ensure_active_configuration()

        self.assertFalse(result)
        app.help_faq_menu.assert_called_once()
        app._create_machine_first_configuration.assert_not_called()
        app._import_configuration.assert_not_called()
        app._load_config_by_name.assert_not_called()

    def test_help_menu_renders_all_topics(self):
        app = _make_app()
        app.get_input = MagicMock(return_value='0')

        app.help_faq_menu()

        rendered = _rendered_text(app)
        for topic in r1setup.R1Setup.HELP_FAQ_TOPICS:
            self.assertIn(topic['title'], rendered)
        self.assertIn("0) Back", rendered)

    def test_migration_help_contains_target_rule(self):
        app = _make_app()
        migration_index = next(
            index
            for index, topic in enumerate(r1setup.R1Setup.HELP_FAQ_TOPICS, start=1)
            if topic['title'] == 'Migration Workflow'
        )
        app.get_input = MagicMock(side_effect=[str(migration_index), '0'])

        app.help_faq_menu()

        rendered = _rendered_text(app)
        self.assertIn("Register Machine", rendered)
        self.assertIn("do not Add Node", rendered)
        self.assertIn("Execute Migration moves", rendered)
        app.wait_for_enter.assert_called_once()

    def test_invalid_help_topic_mentions_valid_range(self):
        app = _make_app()
        topic_count = len(r1setup.R1Setup.HELP_FAQ_TOPICS)
        app.get_input = MagicMock(side_effect=[str(topic_count + 1), '0'])

        app.help_faq_menu()

        rendered = _rendered_text(app)
        self.assertIn(f"Invalid option. Valid choices are 0-{topic_count}.", rendered)
        app.wait_for_enter.assert_called_once()


if __name__ == '__main__':
    unittest.main()
