#!/usr/bin/env python3
"""
Version management for Ratio1 Multi-Node Launcher CLI
"""

__VER__ = '1.1.014'


def get_version():
    """Get the current version"""
    return __VER__


def update_pyproject_toml():
    """Update version in pyproject.toml"""
    try:
        with open("pyproject.toml", "rt") as fd:
            new_lines = []
            lines = fd.readlines()
            for line in lines:
                if line.strip().startswith("version") and "=" in line:
                    line = f'version = "{__VER__}"\n'
                new_lines.append(line)

        with open("pyproject.toml", "wt") as fd:
            fd.writelines(new_lines)
        
        print(f"✅ Updated pyproject.toml to version {__VER__}")
        return True
    except FileNotFoundError:
        print("⚠️  pyproject.toml not found")
        return False
    except Exception as e:
        print(f"❌ Error updating pyproject.toml: {e}")
        return False


def update_r1setup_fallback():
    """Update the fallback version in r1setup script"""
    try:
        with open("r1setup", "rt") as fd:
            content = fd.read()
        
        # Update the fallback version line
        import re
        pattern = r'CLI_VERSION = "[^"]*"'
        replacement = f'CLI_VERSION = "{__VER__}"'
        
        new_content = re.sub(pattern, replacement, content)
        
        if new_content != content:
            with open("r1setup", "wt") as fd:
                fd.write(new_content)
            print(f"✅ Updated r1setup fallback version to {__VER__}")
            return True
        else:
            print("ℹ️  r1setup fallback version already up to date")
            return True
    except FileNotFoundError:
        print("⚠️  r1setup script not found")
        return False
    except Exception as e:
        print(f"❌ Error updating r1setup: {e}")
        return False


def update_all():
    """Update version in all relevant files"""
    print(f"🔄 Updating all files to version {__VER__}")
    
    success = True
    success &= update_pyproject_toml()
    success &= update_r1setup_fallback()
    
    if success:
        print(f"✅ All files updated to version {__VER__}")
    else:
        print("❌ Some files failed to update")
    
    return success


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--version" or sys.argv[1] == "-v":
            print(__VER__)
        elif sys.argv[1] == "--update-all":
            update_all()
        else:
            print("Usage:")
            print("  python ver.py            - Update pyproject.toml (default)")
            print("  python ver.py --version  - Show version")
            print("  python ver.py --update-all - Update all files")
    else:
        # Default behavior: update pyproject.toml
        update_pyproject_toml()
