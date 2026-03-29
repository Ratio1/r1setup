#!/usr/bin/env python3
"""
E2E dry migration test driver using pexpect.
Flow: config creation -> register target -> plan migration ->
      execute migration -> verify -> rollback cleanup.

Source node is configured manually (not via discovery) since the edge_node
service is already running on the source machine.
"""
import pexpect
import sys
import os
import time
import re

ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\[[\d;]*m')
def clean(s):
    return ANSI_RE.sub('', s or '')

def banner(msg):
    print(f"\n{'='*70}\n  {msg}\n{'='*70}")

def run_test():
    env = os.environ.copy()
    env['R1SETUP_NO_CLEAR'] = '1'
    env['R1SETUP_SKIP_AUTO_UPDATE'] = '1'
    env['R1SETUP_NO_VENV'] = '1'

    banner("E2E MIGRATION DRY TEST")
    print("  Source: ubuntu@51.83.248.38 (dr1-v100s-1)")
    print("  Target: vitalii@35.228.69.214")

    c = pexpect.spawn(
        'bash /home/vi/work/ratio1/repos/multi_node_launcher/scripts/run_r1setup_repo_local.sh --reset',
        encoding='utf-8', timeout=120, env=env, dimensions=(60, 200)
    )
    c.logfile_read = sys.stdout

    def ws(pattern, response, timeout=120):
        c.expect(pattern, timeout=timeout)
        time.sleep(0.2)
        c.sendline(response)

    def screen(t=3):
        try:
            c.expect(pexpect.TIMEOUT, timeout=t)
        except:
            pass
        return clean(c.before)

    # ================================================================
    banner("PHASE 1: Create config with source node")
    # ================================================================
    ws(r'Select option', '1')                         # Create first config
    ws(r'configuration name', 'e2e-migration-test')
    ws(r'Select network environment', '1')            # mainnet
    ws(r'How many nodes', '1')
    ws(r'Enter name for node', 'source-node')
    ws(r'Enter host', '51.83.248.38')
    ws(r'Enter SSH username', 'ubuntu')
    ws(r'Select authentication', '2')                 # SSH Key
    ws(r'Enter path to SSH private key', '')
    ws(r'sudo password', '')
    ws(r'Confirm this configuration', 'y')
    ws(r'Would you like to deploy now', 'n')
    ws(r'Press Enter', '')

    banner("PHASE 1 COMPLETE")

    # ================================================================
    banner("PHASE 2: Register target machine")
    # ================================================================
    ws(r'Select option', '1')    # Configuration Menu
    ws(r'Select option', '5')    # Register Machine
    ws(r'Enter machine label', 'target-g1')
    ws(r'Select topology mode', '1')
    ws(r'Enter host', '35.228.69.214')
    ws(r'Enter SSH username', 'vitalii')
    ws(r'Select authentication', '2')
    ws(r'Enter path to SSH private key', '')
    ws(r'sudo password', '')
    ws(r'Confirm this configuration', 'y')
    ws(r'Probe machine specs', 'Y')
    ws(r'Discover existing.*\(y/n\)', 'n', timeout=60)
    ws(r'Press Enter', '')

    banner("PHASE 2 COMPLETE")

    # ================================================================
    banner("PHASE 3: Fleet Summary")
    # ================================================================
    ws(r'Select option', '6')  # Fleet Summary
    time.sleep(2)
    content = screen(3)
    print(f"\n--- FLEET SUMMARY ---")
    for line in content.split('\n'):
        if line.strip():
            print(f"  | {line}")
    print(f"--- END ---\n")
    ws(r'Press Enter', '')

    banner("PHASE 3 COMPLETE")

    # ================================================================
    banner("PHASE 4: Plan migration source-node -> target-g1")
    # ================================================================
    ws(r'Select option', '0')   # Back to main
    ws(r'Select option', '2')   # Deployment Menu
    ws(r'Select option', '4')   # Plan Migration

    # Select source instance (only 1 available)
    ws(r'Select instance', '1', timeout=30)

    # Confirm source machine
    ws(r'\(Y/n\)', '', timeout=30)  # default Y

    # Select target machine (only 1 valid target)
    ws(r'Select target machine', '1', timeout=30)

    # Naming policy
    ws(r'Select.*naming|naming.*policy|[Pp]reserve.*[Nn]ormalize', '1', timeout=30)

    # Plan review and save - handle all prompts
    for attempt in range(15):
        try:
            idx = c.expect([
                r'Select option.*:',                       # Back at menu
                r'Press Enter',
                r'\([yY]/[nN]\)',                          # Any y/n variant
            ], timeout=60)
            if idx == 0:
                break
            elif idx == 1:
                c.sendline('')
            elif idx == 2:
                c.sendline('y')
        except pexpect.TIMEOUT:
            print(f"\n>>> Timeout during plan save")
            print(screen())
            break

    banner("PHASE 4 COMPLETE - Migration planned")

    # ================================================================
    banner("PHASE 5: Execute migration (this will take a while - archive/transfer/extract)")
    # ================================================================
    c.sendline('5')  # Execute Migration (already at menu prompt)

    for attempt in range(50):
        try:
            idx = c.expect([
                r'Select option.*:',                       # Menu
                r'Press Enter',
                r'\([yY]/[nN]\)',
            ], timeout=600)
            ctx = clean(c.before)
            if idx == 0:
                print(f"\n>>> Back at Deployment Menu")
                break
            elif idx == 1:
                c.sendline('')
            elif idx == 2:
                c.sendline('y')
        except pexpect.TIMEOUT:
            print(f"\n>>> Timeout during execution")
            content = screen(5)
            print(f"\nScreen:\n{content[-600:]}")
            break

    banner("PHASE 5 COMPLETE")

    # ================================================================
    banner("PHASE 6: Check deployment status")
    # ================================================================
    c.sendline('9')  # Deployment Status
    time.sleep(2)

    for attempt in range(5):
        try:
            idx = c.expect([r'Select option', r'Press Enter'], timeout=15)
            ctx = clean(c.before)
            print(f"\n--- STATUS ---")
            for line in ctx.split('\n')[-25:]:
                if line.strip():
                    print(f"  | {line}")
            print(f"--- END ---\n")
            if idx == 0:
                break
            c.sendline('')
        except:
            break

    banner("PHASE 6 COMPLETE")

    # ================================================================
    banner("PHASE 7: Rollback (restore source, clean target)")
    # ================================================================
    c.sendline('6')  # Rollback Migration

    for attempt in range(30):
        try:
            idx = c.expect([
                r'Select option.*:',
                r'Press Enter',
                r'\(y/n\)',
                r'\(Y/n\)',
            ], timeout=300)
            ctx = clean(c.before)
            if idx == 0:
                print(f"\n>>> At menu after rollback")
                # Print final context
                for line in ctx.split('\n')[-15:]:
                    if line.strip():
                        print(f"  | {line}")
                break
            elif idx == 1:
                c.sendline('')
            elif idx in (2, 3):
                c.sendline('y')
        except pexpect.TIMEOUT:
            print(f"\n>>> Timeout during rollback")
            content = screen(5)
            print(f"\nScreen:\n{content[-600:]}")
            break

    banner("PHASE 7 COMPLETE")

    # ================================================================
    banner("PHASE 8: Final status and exit")
    # ================================================================
    c.sendline('9')  # Deployment Status
    time.sleep(2)
    for attempt in range(5):
        try:
            idx = c.expect([r'Select option', r'Press Enter'], timeout=15)
            ctx = clean(c.before)
            print(f"\n--- FINAL STATUS ---")
            for line in ctx.split('\n')[-25:]:
                if line.strip():
                    print(f"  | {line}")
            print(f"--- END ---\n")
            if idx == 0:
                break
            c.sendline('')
        except:
            break

    # Exit
    for _ in range(5):
        c.sendline('0')
        time.sleep(0.3)
    try:
        c.expect(pexpect.EOF, timeout=10)
    except:
        pass

    banner("E2E MIGRATION DRY TEST COMPLETE")


if __name__ == '__main__':
    run_test()
