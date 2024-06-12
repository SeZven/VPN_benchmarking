import os
import shutil
import signal
import subprocess

import click

import src.helpers as helpers
import src.messages as messages
from src.vpns.VPN import VPN

key_path = "ovpn-keys"
config_path = "/etc/openvpn"  # Path to OpenVPN configuration directory

class OpenVPN(VPN):
    """
    Implements the OpenVPN, a widely-used VPN protocol.
    """
    process = None

    def __init__(self, role) -> None:
        """
        Calls VPN's __init__. Additionally, sets the OpenVPN interface name to 'tun0' and the address of the server to '10.8.0.1'.
        :param role: role of the host
        """
        super().__init__(role)
        self.interface_name = "tun0"
        self.server_address = "10.8.0.1"

    def open(self) -> bool:
        """
        Opens the OpenVPN. Will stay open after completion. Can be closed with the close method.
        :return: True for success, False otherwise
        """
        messages.print_log("Preparing...")
        self.__clean_up()  # Close existing OpenVPN processes

        messages.print_log("Starting OpenVPN process...")
        if self.role == "server":
            self.process = self.__start_openvpn_server()
        elif self.role == "client":
            self.process = self.__start_openvpn_client()
        else:
            raise Exception("Unexpected role")

        if not self.process:  # Process was not opened correctly
            return False

        messages.print_log("OpenVPN connection established.")
        return True

    def close(self) -> bool:
        """
        Closes the OpenVPN after cleanup.
        :return: True for success
        """
        self.__clean_up()
        messages.print_log("OpenVPN connection closed.")
        return True

    def generate_keys(self) -> bool:
        """
        Generates the necessary keys for OpenVPN. Uses EasyRSA to generate keys.
        :return: True for success, False otherwise
        """
        messages.print_log(f"Generating OpenVPN key set for {self.role}...")

        # Create directory if not existent
        if not os.path.exists(key_path):
            try:
                os.mkdir(key_path)
            except Exception as err:
                messages.print_err("Something went wrong when creating the key directory.")
                print(f"{err=}")
                return False

        # If key directories exist, ask for overwriting, otherwise keep old keys.
        if os.path.exists(os.path.join(key_path, f"{self.role}.crt")) or os.path.exists(os.path.join(key_path, f"{self.role}.key")):
            messages.print_warn("The keys already exist.")
            if click.confirm("Overwrite existing keys and generate new keys?"):
                shutil.rmtree(key_path, ignore_errors=False, onerror=None)
                os.mkdir(key_path)
            else:
                return True

        try:
            subprocess.check_output(["easyrsa", "gen-req", self.role, "nopass"], cwd=key_path, stderr=subprocess.PIPE)
            subprocess.check_output(["easyrsa", "sign-req", "client" if self.role == "client" else "server", self.role], cwd=key_path, stderr=subprocess.PIPE)
            messages.print_log(f"Generated keys for the {self.role}.")
            return True
        except Exception as err:
            messages.print_err("Unable to generate keys: Ensure EasyRSA is installed and configured correctly.")
            print(f"{err=}")
            return False

    def share_pubkeys(self, remote_path) -> bool:
        """
        Sends the generated public keys to the other host.
        :param remote_path: path in which the key directory exists on the remote host
        :return: True for success, False otherwise
        """
        if self.role == "server":
            messages.print_log("Sending public keys to the client...")
            remote_user = self.hosts.client_user
            remote_address = self.hosts.client_address
        elif self.role == "client":
            messages.print_log("Sending public keys to the server... ")
            remote_user = self.hosts.server_user
            remote_address = self.hosts.server_address
        else:
            return False

        try:
            cert_file = f"{self.role}.crt"
            key_file = f"{self.role}.key"
            success = helpers.send_file_to_host(os.path.join(key_path, cert_file), remote_user, remote_address, os.path.join(remote_path, key_path)) and \
                      helpers.send_file_to_host(os.path.join(key_path, key_file), remote_user, remote_address, os.path.join(remote_path, key_path))
            if not success:
                return False
        except Exception as err:
            messages.print_err("Keys do not exist. Generate new keys with 'main.py'.")
            print(f"{err=}")
            return False

        messages.print_log("Sent public keys.")
        return True

    def __start_openvpn_server(self):
        """
        Starts the OpenVPN server process.
        :return: process object
        """
        messages.print_log("Starting OpenVPN server...")

        try:
            process = subprocess.Popen(
                [
                    "sudo",
                    "openvpn",
                    "--config",
                    os.path.join(config_path, "server.conf")
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as err:
            messages.print_err("OpenVPN server start was not successful!")
            print(f"{err=}")
            self.__clean_up()
            return None

        return process

    def __start_openvpn_client(self):
        """
        Starts the OpenVPN client process.
        :return: process object
        """
        messages.print_log("Starting OpenVPN client...")

        try:
            process = subprocess.Popen(
                [
                    "sudo",
                    "openvpn",
                    "--config",
                    os.path.join(config_path, "client.conf")
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as err:
            messages.print_err("OpenVPN client start was not successful!")
            print(f"{err=}")
            self.__clean_up()
            return None

        return process

    def __clean_up(self):
        """
        Terminates all running OpenVPN processes.
        """
        if self.process:
            self.process.kill()

        try:
            for line in os.popen("ps ax | grep openvpn | grep -v grep"):
                fields = line.split()
                if "main.py" not in line:
                    pid = fields[0]
                    os.kill(int(pid), signal.SIGKILL)
        except Exception as err:  # no OpenVPN processes running
            return
