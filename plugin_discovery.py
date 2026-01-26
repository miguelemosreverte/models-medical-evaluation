#!/usr/bin/env python3
"""
Plugin discovery and testing utility for medical coding plugins.
"""

import os
import sys
import importlib.util
import argparse
from pathlib import Path

def discover_plugins(plugins_dir="plugins"):
    """Discover all available plugins by scanning the plugins directory."""
    plugins = []
    plugins_path = Path(plugins_dir)

    if not plugins_path.exists():
        print(f"Plugins directory '{plugins_dir}' not found")
        return plugins

    # Look for both old-style (*_plugin.py) and new clean plugins (*.py)
    for plugin_file in plugins_path.glob("*.py"):
        # Skip __init__.py and non-plugin files
        if plugin_file.name.startswith('__'):
            continue

        plugin_name = plugin_file.stem  # Remove .py extension

        try:
            # Load the module
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find the plugin class (should end with 'Plugin')
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    attr_name.endswith('Plugin') and
                    attr_name != 'ExperimentPlugin' and
                    attr_name != 'MedicalCodingPlugin'):

                    plugins.append({
                        'name': plugin_name,
                        'file': plugin_file,
                        'class': attr,
                        'module': module
                    })
                    break
        except Exception as e:
            print(f"Error loading plugin {plugin_file}: {e}")

    return plugins

def list_plugins():
    """List all available plugins."""
    plugins = discover_plugins()

    if not plugins:
        print("No plugins found in the plugins directory.")
        return

    print("Available plugins:")
    print("=" * 50)

    for plugin in plugins:
        try:
            # Try to get plugin info
            plugin_class = plugin['class']

            # Create a temporary instance to get name and version
            # We'll use a mock db for this
            class MockDB:
                def __init__(self):
                    self.conn = None

            try:
                instance = plugin_class(MockDB())
                name = getattr(instance, 'name', plugin['name'])
                version = getattr(instance, 'version', 'unknown')
                print(f"  {plugin['name']}")
                print(f"    Name: {name}")
                print(f"    Version: {version}")
                print(f"    File: {plugin['file']}")
                print()
            except:
                print(f"  {plugin['name']}")
                print(f"    File: {plugin['file']}")
                print(f"    (Could not instantiate)")
                print()

        except Exception as e:
            print(f"  {plugin['name']} - Error: {e}")

def test_plugin(plugin_name, description=None):
    """Test a specific plugin by name."""
    plugins = discover_plugins()

    # Find the plugin
    target_plugin = None
    for plugin in plugins:
        if plugin_name in plugin['name'] or plugin_name in plugin['file'].name:
            target_plugin = plugin
            break

    if not target_plugin:
        print(f"Plugin '{plugin_name}' not found.")
        print("Available plugins:")
        for p in plugins:
            print(f"  - {p['name']}")
        return

    print(f"Testing plugin: {target_plugin['name']}")
    print(f"File: {target_plugin['file']}")

    try:
        # Initialize the plugin
        from db_manager import MedicalCodingDB
        db = MedicalCodingDB('medical_coding.db')

        plugin_class = target_plugin['class']
        plugin = plugin_class(db, {'max_items': 5})

        print(f"Plugin initialized: {plugin.name} v{plugin.version}")

        # Test with a description using standard interface
        test_description = description or "Patient presents with fever and dry cough for 3 days"

        # All plugins use standard interface: {'code': str, 'description': str}
        import time
        unique_code = f"TEST_{int(time.time())}"
        test_item = {
            'code': unique_code,
            'description': test_description
        }

        print(f"\nTesting with: {test_description}")
        print("Using standard interface: {'code': id, 'description': description}")

        result = plugin.process_item(test_item)

        print(f"Success: {result.success}")
        print(f"Response time: {result.response_time:.2f}s")

        if hasattr(result, 'result_data') and result.result_data:
            predicted_codes = result.result_data.get('predicted_codes', [])
            print(f"Predicted codes: {predicted_codes}")
        elif hasattr(result, 'result_data'):
            print(f"Result data: {result.result_data}")

    except Exception as e:
        print(f"Error testing plugin: {e}")
        import traceback
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description='Plugin discovery and testing utility')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # List command
    list_parser = subparsers.add_parser('list', help='List all available plugins')

    # Test command
    test_parser = subparsers.add_parser('test', help='Test a specific plugin')
    test_parser.add_argument('plugin', help='Plugin name to test')
    test_parser.add_argument('--description', help='Medical description to test with')

    args = parser.parse_args()

    if args.command == 'list':
        list_plugins()
    elif args.command == 'test':
        test_plugin(args.plugin, args.description)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()