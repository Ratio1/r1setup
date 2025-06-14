# CLI Update Fix

## Problem
The CLI update mechanism was failing with a 404 error when trying to download the `r1setup` file from GitHub releases. This happened because the GitHub releases only contained the packaged tar.gz files, not the individual script files that the update mechanism expected.

## Solution

### 1. Enhanced Update Mechanism
The `r1setup` script now includes comprehensive update functionality with fallback URLs. The update process will:

1. **Download CLI files**: First try GitHub release assets, fall back to raw content if needed
2. **Update CLI scripts**: Install new `r1setup`, `ver.py`, and `update.py` files
3. **Update Ansible collection**: Automatically update the `ratio1.multi_node_launcher` collection from Ansible Galaxy
4. **Verify installation**: Ensure the new CLI works before completing the update

This ensures both the CLI and Ansible components stay synchronized and compatible.

### 2. GitHub Actions Workflows

#### Automatic Release (`.github/workflows/release.yml`)
Triggers when a new version tag is pushed (e.g., `v1.1.14`):
- Creates a GitHub release
- Uploads CLI script files (`r1setup`, `ver.py`, `update.py`)
- Uploads the packaged collection tar.gz file

#### Manual Release (`.github/workflows/manual-release.yml`)
**Manually triggerable from GitHub UI** with the following inputs:
- **Version**: Version number (e.g., `1.1.15`)
- **Release Name**: Custom release name (optional)
- **Release Notes**: Custom release notes (optional)
- **Pre-release**: Mark as pre-release (checkbox)
- **Create Tag**: Create git tag if it doesn't exist (checkbox)

**How to use the Manual Release:**
1. Go to your GitHub repository
2. Click **Actions** tab
3. Select **Manual Release Creation** workflow
4. Click **Run workflow**
5. Fill in the version and other details
6. Click **Run workflow**

The manual workflow will:
- Validate version format
- Update version numbers in `ver.py` and `r1setup`
- Create git tag (if requested)
- Create GitHub release with all files
- Provide a detailed summary

### 3. Manual Fix Script
For existing releases that are missing the script files, you can use the `scripts/upload_release_assets.py` script to upload them manually:

```bash
# Set your GitHub personal access token
export GITHUB_TOKEN=your_token_here

# Run the upload script
python scripts/upload_release_assets.py
```

## Testing the Fix

After applying these changes, the CLI update should work properly:

1. The fallback mechanism ensures immediate functionality
2. Future releases will automatically include the required files
3. Existing releases can be fixed with the manual upload script

## Files Changed

- `mnl_factory/scripts/r1setup` - Enhanced with fallback URL mechanism
- `.github/workflows/release.yml` - New automated release workflow
- `scripts/upload_release_assets.py` - Manual fix script for existing releases

## How It Works

The enhanced update mechanism works as follows:

1. **Version Check**: Downloads the latest version info from the main branch
2. **Primary Download**: Attempts to download files from GitHub release assets
3. **Fallback Download**: If primary fails, automatically tries raw GitHub content
4. **CLI Installation**: Backs up current files and installs the new CLI version
5. **Collection Update**: Updates the Ansible collection using `ansible-galaxy`
6. **Validation**: Verifies the new installation works before completing

### Collection Update Process

When updating the CLI, the system also updates the Ansible collection:

```bash
ansible-galaxy collection install ratio1.multi_node_launcher \
  --collections-path ~/.ratio1/ansible_config/collections \
  --force --upgrade
```

This ensures that:
- Playbooks and roles are kept up-to-date
- CLI and Ansible components remain compatible
- Bug fixes and improvements in both components are synchronized
- The deployment functionality works with the latest features

The fallback URLs ensure that updates will work even if:
- GitHub releases are missing the individual files
- There are temporary issues with the release assets
- The repository structure changes

This provides a robust update mechanism that can handle various failure scenarios gracefully. 