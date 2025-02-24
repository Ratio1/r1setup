# multi_node_launcher

## Usage Instructions

To set up your environment and deploy the necessary configurations, follow these steps:

1. **Clone the Repository**
   First, clone the repository to your local machine using the following command:
   ```bash
   git clone https://github.com/Ratio1/multi-node-launcher.git
   cd multi-node-launcher
   ```

2. **Pull the Latest Changes**
   If you already have the repository cloned, ensure you have the latest changes by running:
   ```bash
   git pull origin main
   ```

3. **Specify Your Machines in the Inventory**
   Edit the `inventory/hosts.yml` file to specify the machines you want to configure. You can add your GPU nodes under the `gpu_nodes` section. Here’s an example of how to format the entries:
   ```yaml
   all:
     children:
       gpu_nodes:
         hosts:
           your-gpu-node:
             ansible_host: <your_machine_ip>
             ansible_user: <your_username>
             ansible_ssh_private_key_file: ~/.ssh/id_rsa
   ```

4. **Run the Setup Script**
   Execute the `run_setup.sh` script to start the setup process. This script will install the necessary dependencies, configure your machines, and run the Ansible playbooks:
   ```bash
   cd mnl_factory
   sudo ./run_setup.sh
   ```

5. **Follow the Prompts**
   During the execution of the script, you may be prompted to confirm certain actions. Follow the on-screen instructions to proceed with the installation.

6. **Verify the Installation**
   After the setup is complete, you can verify the installation by SSHing into your machine and checking the installed services:
   ```bash
   ssh <your_username>@<your_machine_ip>
   docker --version
   nvidia-smi
   ```

7. **Troubleshooting**
   If you encounter any issues, refer to the troubleshooting section in the README for common problems and their solutions.

By following these steps, you should be able to successfully set up your environment and deploy the necessary configurations for your GPU nodes.



curl -sSL https://raw.githubusercontent.com/YourUsername/multi-node-launcher/main/install.sh | sudo bash
