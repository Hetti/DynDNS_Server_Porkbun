import argparse
import logging
import typing
import sys

import cherrypy
import requests
import toml
import json

class DNSAPIException(Exception):
    def __init__(self, error_code: int, error_data: typing.Union[str, dict]):
        self.error_code = error_code
        self.error_data = error_data

    def __str__(self):
        return f"{self.error_code} - {self.error_data}"

class PorkbunDNSAPIClient:
    def __init__(self, config):
        self.base_url = config["endpoint"]
        self.apikey = config["apikey"]
        self.secretapikey = config["secretapikey"]
        self.default_ttl = config["default_ttl"]

    def getRootDomain(self, full_domain: str) -> str:
        root_domain = '.'.join(full_domain.split('.')[-2:])
        return root_domain

    def getSubDomain(self, full_domain: str) -> str:
        sub_domain = '.'.join(full_domain.split('.')[:-2])
        return sub_domain

    def getRecords(self, domain: str): #grab all the records so we know which ones to update. Also checks to make sure we've got the right domain
        api_header = {
            "secretapikey": self.secretapikey,
            "apikey": self.apikey
        }
        
        print(f"Getting records for {domain}")
        allRecords = json.loads(requests.post(self.base_url + '/dns/retrieve/' + domain, data = json.dumps(api_header)).text)
        # print(allRecords)
        if allRecords["status"] == "ERROR":
            print('Error getting domain. Check to make sure you specified the correct domain, and that API access has been switched on for this domain.');
            sys.exit()
        return(allRecords)

    def updateRecord(self, records: str, record_type: str, record_name: str, root_domain: str,  record_data: str, record_ttl: str):
        api_header = {
            "secretapikey": self.secretapikey,
            "apikey": self.apikey,
            "name": self.getSubDomain(record_name),
            "type": record_type,
            "content": record_data,
            "ttl": record_ttl
        }

        updateRecord = {}
        updateRecord["status"] = "ERROR"
        updateRecord['message'] = "Something is already broken..."

        for i in records["records"]:
            if i["name"]==record_name and i["type"] == record_type:
                print(f"Editing {i['type']} record of {record_name}")
                updateRecord = json.loads(requests.post(self.base_url + '/dns/edit/' + root_domain + '/' + i["id"], data = json.dumps(api_header)).text)

            if updateRecord["status"] == "ERROR":
                raise DNSAPIException(500, updateRecord['message'])

        return(updateRecord)

    def update_resource_record(self, record_name: str, record_type: str, record_data: str, record_ttl: int = None):
        record_ttl = record_ttl if record_ttl and record_ttl >= 60 else self.default_ttl
        root_domain = self.getRootDomain(record_name)
        records = self.getRecords(root_domain)
        result = {}
        # loop through records and check if the records are already present
        for i in records["records"]:
            if i["name"] == record_name and i["type"] == record_type and i["content"] == record_data:
                result["status"] = "SUCCESS"
                return result
        
        result = self.updateRecord(records,record_type, record_name, root_domain, record_data, record_ttl)

        return result
class Root:
    def __init__(self, dns_client: PorkbunDNSAPIClient, allowed_domains: typing.Union[bool, list]):
        if allowed_domains and not isinstance(allowed_domains, list):
            raise ValueError("allowed_domains has to be a list or False to allow all domains.")

        self.allowed_domains = allowed_domains
        self.dns_client = dns_client

    @cherrypy.expose
    @cherrypy.tools.params()  # Auto-cast query parameters according to type annotations
    def dyndns(self, domain: str = None, ipv4: str = None, ipv6: str = None, ttl: int = None):
        if not domain:
            cherrypy.response.status = 400
            return "DynDNS target domain missing."

        if self.allowed_domains and domain not in self.allowed_domains:
            cherrypy.response.status = 403
            return "Requested DynDNS domain ist not on the allowlist."

        results = []

        def update_wrapper(record_type, record_data):
            try:
                result = self.dns_client.update_resource_record(domain, record_type, record_data, ttl)
                logging.info(
                    f"Successfully updated {record_type} record for {domain}:"
                    f" {record_data}, TTL {ttl if ttl else '<default>'}"
                )
                results.append(f"Successfully updated {record_type} record for {domain} to {record_data}")
            except DNSAPIException as e:
                logging.error(
                    f"Failed to update {record_type} record for {domain}"
                    f" with address {record_data} and TTL {ttl if ttl else '<default>'}: {e}"
                )
                results.append(f"Failed to update {record_type} record: {e}")
                cherrypy.response.status = 400

        if not ipv4 and not ipv6:
            logging.error(f"Update request for {domain} received, but neither a v4 nor a v6 address given.")
            cherrypy.response.status = 400
            return "Neither a v4 nor a v6 address given."

        if ipv4:
            update_wrapper("A", ipv4)

        if ipv6:
            update_wrapper("AAAA", ipv6)

        cherrypy.response.headers['Content-Type'] = 'text/plain'
        return "\n".join(results)

def main():
    parser = argparse.ArgumentParser(
        description="DynDNS server providing an interface for updates via generic URL"
    )
    parser.add_argument(
        "-c", "--config",
        default="config.toml",
        help="Config file for the DynDNS server. Defaults to 'config.toml' in the current working directory."
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)8s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    with open(args.config, "r") as fh:
        config = toml.load(fh)

    cherrypy.config.update({"global": {"environment": "production"}})
    cherrypy.log.screen = True

    if "bind_socket" in config:
        cherrypy.server.socket_file = config["main"]["bind_socket"]
    else:
        cherrypy.server.socket_host = config["main"]["bind_host"]
        cherrypy.server.socket_port = config["main"]["bind_port"]

    allowed_domains = config["main"]["allowed_domains"]
    porkbun_dns_api_client = PorkbunDNSAPIClient(config["porkbun_dns_api"])
    root = Root(porkbun_dns_api_client, allowed_domains)

    cherrypy.quickstart(root)

if __name__ == "__main__":
    main()
