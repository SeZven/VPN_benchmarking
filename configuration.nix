{ config, pkgs, ... }:

{
  imports = [ <nixpkgs/nixos/modules/installer/virtualbox-demo.nix> ];

environment.systemPackages = [
	pkgs.xfce.mousepad
	pkgs.python3
	pkgs.wireguard-tools
	pkgs.openvpn
	pkgs.openssh
	pkgs.virtualenv
	pkgs.easyrsa
];

# ipv4 address for server or client	
networking.interfaces.enp0s8.ipv4.addresses = [ {
	address = "192.168.1.2";
	prefixLength = 24;
} ];

#networking.interfaces.eth0.ipv4.addresses = [ {
#	address = "192.168.1.2";
#	prefixLength = 24;
#} ];


# Enable the OpenSSH daemon.
services.openssh.enable = true;

networking.firewall = {
  	allowedTCPPorts = [ 80 ];
  	allowedUDPPorts = [ 1194 ];
};

}
