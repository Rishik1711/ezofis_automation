#!/usr/bin/env bash

# Update package list and install transport tools
apt-get update
ACCEPT_EULA=Y apt-get install -y curl gnupg apt-transport-https

# Add Microsoft's package repo
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list

# Update again with new MS repo and install the driver
apt-get update
ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc
