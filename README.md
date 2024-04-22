# DynDNS Server Porkbun

This fork is basd on the project https://github.com/poettig/HostingDE-DynDNS and implements the same functionality but uses the Porkbun API and also incorporates the code of the Porkbun project https://github.com/porkbundomains/porkbun-dynamic-dns-python/tree/main.

This is a server that accepts GET requests with specific query parameters and interfaces with the Porkbun [DNS API](https://porkbun.com/api/json/v3/documentation) in order to update DNS records with regularly changing IP addresses automatically.

## Running
Install requirements from [requirements.txt](requirements.txt) either directly for the user or in a venv.
```
pip install -r requirements.txt
```

Execute with python, optionally with a different config path.
```
python3 dyndns.py
python3 dyndns.py -c /path/to/config.toml
```

An template for the config file is given in [config.toml.template](config.toml.template).

Instead of binding to an IP and port, technically there is an implementation for unix sockets.
However, this was never tested - use at your own risk.
The config variable for this is `bind_socket`.

#### Help output
```
> python3 dyndns.py -h
usage: dyndns.py [-h] [-c CONFIG]

DynDNS server providing an interface for updates via generic URL

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Config file for the DynDNS server. Defaults to 'config.toml' in the current working directory.
```

## Request Format
The format of the necessary GET request is
```
GET /dyndns?domain=<domain>&ipv4=<ipv4_address>&ipv6=<ipv6_address>&ttl=<ttl>
```

The query parameters are

| parameter | required            | value                                                                              |
|-----------|---------------------|------------------------------------------------------------------------------------|
| domain    | yes                 | The domain to update.                                                              |
| ipv4      | one of [ipv4, ipv6] | The IPv4 for the A record of the domain. Must exist in the DNS zone already.       |
| ipv6      | one of [ipv4, ipv6] | The IPv6 for the AAAA record of the domain. Must exist in the DNS zone already.    |
| ttl       | no                  | The TTL of the record. If not given, a default value from the config file is used. |

## nginx Snippet

Location snippet for the default config

```
	location /<YOUR ENDPOINT> {
			# with this line, nginx relays the request to the Porkbun DynDNS Server
			proxy_pass http://localhost:5354/dyndns;
			proxy_set_header Host            $host;
	}
```

## Security Considerations
* This application is not written to run with SSL and does not provide any authentication. Using a reverse proxy for transport encryption and authentication is expected.
* Records are only updated, never created. This is to prevent this server from creating arbitrary DNS records.
* Additionally, you can provide a list of allowed domains in the config. This prevents editing different records from the ones you want for DynDNS via a simple GET request.
* For the Porkbun API, you need to enable the API access for the used domain in the web interface.
