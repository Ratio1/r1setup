# Multi Node Launcher

Multi Node Launcher is the deployment and operations repository for `r1setup` and the `ratio1.multi_node_launcher` Ansible collection. Its purpose is to let an operator configure remote nodes, deploy the Ratio1 edge-node stack with Ansible, Docker, and systemd, and then operate those nodes through a single CLI instead of a collection of one-off scripts.

## Need, Objective, Purpose

This repository exists to solve three related problems:
- bootstrap a local control machine with a usable `r1setup` command
- manage one or more remote Linux nodes through a consistent inventory-driven workflow
- package the underlying deployment logic as an Ansible collection that can be built and published independently

In practice, the repo contains:
- a root installer, [install.sh](install.sh), that installs the CLI entrypoint
- the Ansible collection under [mnl_factory](mnl_factory)
- the main operator CLI in [mnl_factory/scripts/r1setup](mnl_factory/scripts/r1setup)

## Usability & Features

### Quickstart

Network install:
```bash
curl -sSL https://raw.githubusercontent.com/Ratio1/r1setup/refs/heads/main/install.sh | bash
```

Local install from a checked-out repo:
```bash
bash install.sh
```

Start the CLI:
```bash
r1setup
```

### Typical Workflows

Configure and deploy via the CLI:
```bash
r1setup
```

Manual Ansible workflow:
```bash
cd mnl_factory
ansible-galaxy collection install -r requirements.yml
ansible-playbook -i inventory/hosts.yml playbooks/site.yml
```

Build the collection locally:
```bash
cd mnl_factory
ansible-galaxy collection build --force
```

Run the CLI test suite:
```bash
cd mnl_factory/scripts
python3 test_r1setup.py
```

### What The CLI Provides

- node configuration and inventory management
- deployment flows for Docker, NVIDIA GPU support, and final service setup
- node status and information commands
- service customization
- SSH key management:
  - key installation and migration from password auth
  - extra public key installation
  - key-auth validation
  - optional SSH password-auth disable after successful verification

See [mnl_factory/scripts/README_r1setup.md](mnl_factory/scripts/README_r1setup.md) for CLI-specific operator guidance.

### Configuration

CLI-managed configuration lives under the current user’s home:
- `~/.ratio1/r1_setup/`: CLI state, local configs, active config metadata, local virtualenv
- `~/.ratio1/ansible_config/`: installed Ansible collection, `ansible.cfg`, collection path

Manual inventory example:
```yaml
all:
  children:
    gpu_nodes:
      hosts:
        node-a:
          ansible_host: 192.168.1.100
          ansible_user: root
          ansible_ssh_private_key_file: ~/.ssh/id_ed25519
```

Collection configuration surfaces:
- [mnl_factory/inventory/hosts.yml](mnl_factory/inventory/hosts.yml)
- [mnl_factory/group_vars](mnl_factory/group_vars)
- [mnl_factory/requirements.yml](mnl_factory/requirements.yml)

### Outputs And Artifacts

After installation:
- `r1setup` is symlinked to `/usr/local/bin/r1setup`
- scripts are stored under `~/.ratio1/r1_setup`
- the Ansible collection is installed under `~/.ratio1/ansible_config/collections`

After building the collection:
- `ansible-galaxy collection build --force` produces a `*.tar.gz` artifact in `mnl_factory/`

After a CLI release:
- GitHub release assets include the repository archive plus `r1setup`, `ver.py`, and `update.py`

### Examples

Test connectivity manually:
```bash
cd mnl_factory
ansible all -i inventory/hosts.yml -m ping
```

Run the deploy playbook manually:
```bash
cd mnl_factory
ansible-playbook -i inventory/hosts.yml playbooks/site.yml
```

Run targeted SSH tests:
```bash
cd mnl_factory/scripts
python3 -m unittest tests.test_ssh_key_manager
```

### Troubleshooting

- `r1setup` command missing after install:
  - rerun [install.sh](install.sh); on Linux the symlink step needs `sudo` for `/usr/local/bin`

- CLI release workflow did not trigger:
  - the automatic release workflow watches `mnl_factory/scripts/ver.py`
  - it only proceeds when `__VER__` changes
  - it also requires the fallback `CLI_VERSION` inside `mnl_factory/scripts/r1setup` to match

- Ansible Galaxy publish workflow did not trigger:
  - the publish workflow watches `mnl_factory/galaxy.yml`
  - it only proceeds when the `version` field changes

- SSH hardening concern:
  - disabling password authentication changes the remote machine’s sshd policy
  - test this on disposable hosts first and keep recovery keys outside the target machine

- GPU driver install issues:
  - verify Secure Boot is disabled
  - verify the host actually exposes NVIDIA hardware to the OS
  - inspect the Ansible output from the `nvidia_gpu` role for package/install failures

## Technical Details

### Architecture

The repository is split between an end-user bootstrap layer and an Ansible collection:

- root bootstrap:
  - [install.sh](install.sh) downloads CLI scripts and installs the `r1setup` command

- CLI layer:
  - [mnl_factory/scripts/r1setup](mnl_factory/scripts/r1setup) is the main interactive application
  - [mnl_factory/scripts/ver.py](mnl_factory/scripts/ver.py) is the CLI version source of truth
  - [mnl_factory/scripts/update.py](mnl_factory/scripts/update.py) supports CLI update behavior

- collection layer:
  - [mnl_factory/playbooks](mnl_factory/playbooks) contains operational playbooks
  - [mnl_factory/roles](mnl_factory/roles) contains Docker, GPU, prerequisites, and setup roles
  - [mnl_factory/galaxy.yml](mnl_factory/galaxy.yml) defines collection metadata

### Modules And Repo Map

- [mnl_factory/scripts](mnl_factory/scripts): CLI logic, prerequisite/bootstrap scripts, tests
- [mnl_factory/playbooks](mnl_factory/playbooks): deploy, service, node-info, SSH-key-management, and SSH hardening actions
- [mnl_factory/roles](mnl_factory/roles): reusable Ansible roles
- [docs](docs): dated design and operational notes
- [.github/workflows](.github/workflows): CLI release and collection publish automation

### Dependencies

Local machine prerequisites installed by [mnl_factory/scripts/1_prerequisites.sh](mnl_factory/scripts/1_prerequisites.sh):
- Python 3 and a local virtualenv
- Ansible
- `ssh`, `ssh-keygen`, `openssl`, `sshpass`
- Python packages: `pyyaml`, `typing_extensions`, `certifi`

Collection dependencies from [mnl_factory/requirements.yml](mnl_factory/requirements.yml):
- `community.docker`
- `community.general`
- `ansible.posix`

### Testing

Primary test commands:
```bash
cd mnl_factory/scripts
python3 test_r1setup.py
python3 -m unittest discover tests
python3 -m py_compile r1setup
```

The modular test package lives in [mnl_factory/scripts/tests](mnl_factory/scripts/tests). The compatibility runner in [mnl_factory/scripts/test_r1setup.py](mnl_factory/scripts/test_r1setup.py) simply discovers and runs that suite.

### Security And Operational Notes

- Password-based node configs may temporarily store SSH credentials in the managed inventory until migrated to SSH keys.
- SSH hardening is intentionally separated from SSH key migration so inventory auth changes and remote sshd policy changes are not conflated.
- The repository currently has strong unit and CLI regression coverage, but not a built-in disposable-host integration harness for end-to-end SSH daemon testing.
- `mnl_factory/build.sh` is a local helper and is not the CI-safe publishing path; GitHub Actions uses dedicated workflows instead.

### Release And Publish Automation

- CLI release workflow: [.github/workflows/release.yml](.github/workflows/release.yml)
  - triggered by `mnl_factory/scripts/ver.py`
- Ansible Galaxy publish workflow: [.github/workflows/publish-ansible-galaxy.yml](.github/workflows/publish-ansible-galaxy.yml)
  - triggered by `mnl_factory/galaxy.yml`

### Citations

- Ansible documentation, “Installing collections”: https://docs.ansible.com/ansible/latest/collections_guide/collections_installing.html
- Ansible documentation, “Developing collections / distributing collections”: https://docs.ansible.com/ansible/latest/dev_guide/developing_collections_distributing.html
- Ansible documentation, `ansible.posix.authorized_key`: https://docs.ansible.com/ansible/latest/collections/ansible/posix/authorized_key_module.html
- GitHub documentation, “Workflow syntax for GitHub Actions”: https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions
- OpenBSD manual page, `ssh-keygen(1)`: https://man.openbsd.org/ssh-keygen

## Authors

- Andrei Damian
- Vitalii Toderian

## License

MIT

## Disclaimer

This repository can modify remote SSH configuration, install Docker and NVIDIA-related packages, and deploy a long-running systemd-managed container workload. Validate changes on disposable infrastructure before rolling them into production.
