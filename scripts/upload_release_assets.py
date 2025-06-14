#!/usr/bin/env python3
"""
Script to upload CLI files to existing GitHub releases
This will fix the 404 error by uploading the missing files to releases
"""

import os
import sys
import requests
import json
from pathlib import Path

# Configuration
GITHUB_API_URL = "https://api.github.com"
REPO_OWNER = "Ratio1"
REPO_NAME = "multi-node-launcher"
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

# Files to upload
FILES_TO_UPLOAD = [
    {
        'local_path': 'mnl_factory/scripts/r1setup',
        'asset_name': 'r1setup',
        'content_type': 'application/octet-stream'
    },
    {
        'local_path': 'mnl_factory/scripts/ver.py',
        'asset_name': 'ver.py',
        'content_type': 'text/x-python'
    },
    {
        'local_path': 'mnl_factory/scripts/update.py',
        'asset_name': 'update.py',
        'content_type': 'text/x-python'
    }
]

def get_releases():
    """Get all releases from the repository"""
    url = f"{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/releases"
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching releases: {response.status_code}")
        print(response.text)
        return []

def upload_asset_to_release(release_id, upload_url, file_info):
    """Upload a file asset to a release"""
    local_path = Path(file_info['local_path'])
    
    if not local_path.exists():
        print(f"⚠️  File not found: {local_path}")
        return False
    
    # Prepare upload URL
    upload_url = upload_url.replace('{?name,label}', f"?name={file_info['asset_name']}")
    
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Content-Type': file_info['content_type']
    }
    
    print(f"  Uploading {file_info['asset_name']}...")
    
    with open(local_path, 'rb') as f:
        response = requests.post(upload_url, headers=headers, data=f)
    
    if response.status_code == 201:
        print(f"  ✅ Uploaded {file_info['asset_name']}")
        return True
    else:
        print(f"  ❌ Failed to upload {file_info['asset_name']}: {response.status_code}")
        print(f"     {response.text}")
        return False

def check_asset_exists(assets, asset_name):
    """Check if an asset already exists in the release"""
    return any(asset['name'] == asset_name for asset in assets)

def main():
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN environment variable not set")
        print("Please set your GitHub personal access token:")
        print("export GITHUB_TOKEN=your_token_here")
        sys.exit(1)
    
    print("🚀 Uploading CLI files to GitHub releases...")
    
    # Get all releases
    releases = get_releases()
    if not releases:
        print("❌ No releases found or error fetching releases")
        sys.exit(1)
    
    # Filter for version releases (v1.1.x)
    version_releases = [r for r in releases if r['tag_name'].startswith('v1.1.')]
    
    if not version_releases:
        print("❌ No v1.1.x releases found")
        sys.exit(1)
    
    print(f"Found {len(version_releases)} version releases")
    
    # Upload files to each release
    for release in version_releases:
        tag_name = release['tag_name']
        print(f"\n📦 Processing release {tag_name}...")
        
        # Check existing assets
        existing_assets = release.get('assets', [])
        
        uploaded_count = 0
        for file_info in FILES_TO_UPLOAD:
            if check_asset_exists(existing_assets, file_info['asset_name']):
                print(f"  ⏭️  {file_info['asset_name']} already exists, skipping")
                continue
            
            success = upload_asset_to_release(
                release['id'],
                release['upload_url'],
                file_info
            )
            
            if success:
                uploaded_count += 1
        
        if uploaded_count > 0:
            print(f"  ✅ Uploaded {uploaded_count} files to {tag_name}")
        else:
            print(f"  ℹ️  No new files uploaded to {tag_name}")
    
    print("\n🎉 Upload process completed!")
    print("The CLI update mechanism should now work properly.")

if __name__ == "__main__":
    main() 