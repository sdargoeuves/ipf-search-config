"""
General Python3 script for IP Fabric's API to get the list of available configuration files and searches the specific input strings in it, prints the output.

2022-08 - Version 2.0
using ipfabric SDK
WARNING: you should make sure the SDK version matches your version of IP Fabric

"""

import copy
# Built-in/Generic Imports
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from ipfabric import IPFClient
from ipfabric.tools import DeviceConfigs

try:
    from rich import print
except ImportError:
    None

# Get Current Path
CURRENT_PATH = Path(os.path.realpath(os.path.dirname(sys.argv[0]))).resolve()
# testing only: CURRENT_PATH = Path(os.path.realpath(os.path.curdir)).resolve()
# Load environment variables
load_dotenv(os.path.join(CURRENT_PATH, ".env"), override=True)

# Setting static parameters
IPF_TOKEN = os.getenv("IPF_TOKEN", "f1b0f57a2921b127d7d481740437cd39")
IPF_URL = os.getenv("IPF_URL", "https://ipfabric.local/")
# If IPF_VERIFY is False, the request will accept any TLS certificate presented by the server
IPF_VERIFY = (os.getenv("IPF_VERIFY", "False")=="True")
# Whether to download only sanitized configuration files (files without passwords)
SANITIZED = (os.getenv("IPF_SANITIZED_CONFIG", "False")=="True")
# Other static parameters
SNAPSHOT_ID = os.getenv("IPF_SNAPSHOT", "$last")

DEVICES_FILTER = {"hostname": ["like", "L38EXR"]}
# INPUT data is the list of commands we want to search for in the configuration
# 'ref': is an optional field
# 'section': specifies in which section we should look for this command
INPUT_DATA = [
    {"ref": "1.1", "match": "session-timeout", "section": "line con 0"},
    {"ref": "1.2", "match": "session-timeout", "section": "line vty"},
    {"ref": "2.1", "match": "exec-timeout", "section": "line con 0"},
    {"ref": "2.2", "match": "exec-timeout", "section": "line vty"},
    # {"ref": "3.1","match": "aaa new-model"},
    # {"ref": "4.1","match": "aaa authentication login"},
]


def createConfigDict(config_list):
    """A function to return object of only last config files out of list of configuration files.
    config_list : list of objects
    """
    return_dict = {}
    print("\n  GENERATING configuration item objects")
    for conf in config_list:
        if conf["hostname"] not in return_dict:
            return_dict[conf["hostname"]] = {
                "hash": conf["hash"],
                "hostname": conf["hostname"],
                "lastChangeAt": time.ctime(conf["lastChangeAt"] / 1000),
            }
    return return_dict


def downloadConfig(configs, input_hostnames: list):
    return_list = []
    print("\n  DOWNLOADING latest configuration files:")
    for host in input_hostnames:
        # Get the latest config
        if dev_config := configs.get_configuration(device=host):
            print(".", end="")
            return_list.append(
                {
                    **{
                        "hash": dev_config.config_hash,
                        "hostname": dev_config.hostname,
                        "lastChangeAt": dev_config.last_change,
                        "text": dev_config.text,
                    },
                }
            )
        else:
            print(f"##WARNING## conf not found for '{host}'")
    return return_list


def searchConfig(input_strings, config_list):
    """A function to search for a specific list of string within the list of configuration files.
    Attributes:
    ----------
    input_strings: list of strings
        the list of strings to search for
    config_list: list of objects
        object items containing hostnames, config files, ..
    """
    print("\n  SEARCHING configuration files:")
    result = []
    for conf in config_list:
        for input_string in input_strings:
            # create a deepcopy to edit the item without affecting input_strings
            item = copy.deepcopy(input_string)
            if "section" in item.keys():
                pattern = f'(^{item["section"]}.*$[\n\r]*(?:^\s.*$[\n\r]*)*)'
                regex = re.compile(pattern, re.MULTILINE)
                if section := regex.search(conf["text"]):
                    present_in_conf = "YES" if item["match"] in section[0] else "NO"
                else:
                    present_in_conf = "NO"
            elif item["match"] in conf["text"]:
                present_in_conf = "YES"
            else:
                present_in_conf = "NO"
            item["hostname"] = conf["hostname"]
            item["configured"] = present_in_conf
            result.append(item)

    return result


def create_csv_pd(data_frame: pd.DataFrame, filename: Optional[str] = None):
    """
    Function to create CSV based on list of dictionaries
    """
    # Check if hostname has been specify when calling the function
    if filename is None or filename == "":
        csv_filename = f"{time.strftime('%Y%m%d%H%M%S')}.csv"
    else:
        csv_filename = f"{time.strftime('%Y%m%d%H%M%S')}-{filename}.csv"
    data_frame.to_csv(csv_filename, index=False)

    if os.path.isfile(csv_filename):
        print(f"##INFO## CSV file has been created: '{os.path.realpath(csv_filename)}'")


def format_list_df(data_list: List):
    """
    Change a list of dictionnaries with the host info, to a Dataframe.
    'convert_dtypes()' is used to ensure integer are correctly interpreted
    """
    data_frame = pd.DataFrame(data_list).convert_dtypes()
    # 'None' and '' values are replaced by NaN
    data_frame = data_frame.fillna(np.nan).replace("", np.nan)
    # Move 'hostname' as the 1st column
    if "hostname" in data_frame.columns:
        data_frame.insert(0, "hostname", data_frame.pop("hostname"))
    return data_frame


def main():
    # Getting data from IP Fabric and printing output
    ipf_client = IPFClient(
        base_url=IPF_URL,
        token=IPF_TOKEN,
        snapshot_id=SNAPSHOT_ID,
        verify=IPF_VERIFY,
    )

    configs = DeviceConfigs(ipf_client)
    # Download configuration files for specific hostnames
    input_hostnames = [
        host["hostname"]
        for host in ipf_client.inventory.devices.all(filters=DEVICES_FILTER)
    ]
    config_list = downloadConfig(configs, input_hostnames)

    # Search for specific strings in the configuration files
    result = searchConfig(INPUT_DATA, config_list)
    # print(result)

    df = format_list_df(result)
    create_csv_pd(df, "config_compliance")


if __name__ == "__main__":
    print("\n STARTING API script...")
    main()
    print("\n ENDING API script with success...")
