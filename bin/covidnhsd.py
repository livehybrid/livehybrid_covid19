import sys, logging, os, time, re,json,hashlib
import xml.dom.minidom
from pprint import pprint
from lxml import html
import requests
import base64
import csv
import md5
from StringIO import StringIO


SPLUNK_HOME = os.environ.get("SPLUNK_HOME")

SPLUNK_PORT = 8089

import requests, json
from splunklib.client import connect
from splunklib.client import Service

# prints XML stream
def print_xml_stream(s,source):
    print "<stream><event unbroken=\"1\"><source>%s</source><data>%s</data><done/></event></stream>" % (source, encodeXMLText(s))

#set up logging
logging.root
logging.root.setLevel(logging.WARNING)
formatter = logging.Formatter('%(levelname)s %(message)s')
#with zero args , should go to STD ERR
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logging.root.addHandler(handler)


SCHEME = """<scheme>
    <title>Covid-19 NHS Digital</title>
    <description>Poll for NHS Digital Covid-19 data</description>
    <use_external_validation>true</use_external_validation>
    <streaming_mode>xml</streaming_mode>
    <use_single_instance>false</use_single_instance>

    <endpoint>
        <args>
            <arg name="name">
                <title>Covid input name</title>
                <description>Name of this input</description>
            </arg>
            <arg name="http_proxy">
                <title>HTTP Proxy Address</title>
                <description>HTTP Proxy Address</description>
                <required_on_edit>false</required_on_edit>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="https_proxy">
                <title>HTTPs Proxy Address</title>
                <description>HTTPs Proxy Address</description>
                <required_on_edit>false</required_on_edit>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="section">
                <title>Data Section</title>
                <description>Which of the 4 datasets to pull? nhs111/pathways</description>
                <required_on_edit>false</required_on_edit>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="polling_interval">
                <title>Polling Interval</title>
                <description>Interval time in seconds to poll the endpoint</description>
                <required_on_edit>false</required_on_edit>
                <required_on_create>false</required_on_create>
            </arg>
        </args>
    </endpoint>
</scheme>
"""

def do_validate():
    config = get_validation_config()
    #TODO
    #if error , print_validation_error & sys.exit(2)

def do_run():

    config = get_input_config()

    #setup some globals
    server_uri = config.get("server_uri")
    global SPLUNK_PORT
    global STANZA
    global SESSION_TOKEN
    SPLUNK_PORT = server_uri[18:]
    STANZA = config.get("name")
    SESSION_TOKEN = config.get("session_key")

    SECTION = config.get("section")


    #params
    request_timeout = int(config.get("request_timeout", 30))
    polling_interval = int(config.get("polling_interval", 300))
    http_proxy = config.get("http_proxy")
    https_proxy = config.get("https_proxy")
    proxies = {}

    if not http_proxy is None:
        proxies["http"] = http_proxy
    if not https_proxy is None:
        proxies["https"] = https_proxy


    checkpoint_dir = config.get("checkpoint_dir")

    req_args = {"verify" : True , "timeout" : float(request_timeout)}

    if proxies:
        req_args["proxies"] = proxies


    page = requests.get('https://digital.nhs.uk/data-and-information/publications/statistical/mi-potential-covid-19-symptoms-reported-through-nhs-pathways-and-111-online/latest', params=req_args)
    page_dom = html.fromstring(page.content)
    urls = {}
    urls['pathways'] = page_dom.xpath('//a[@title="NHS Pathways Potential COVID-19 Open Data"]')[0].attrib['href']
    urls['nhs111'] = page_dom.xpath('//a[@title="111 Online Potential COVID-19 Open Data"]')[0].attrib['href']
    urls['meta'] = page_dom.xpath('//a[@title="NHS Pathways and 111 Online Potential COVID-19 Open Data Descriptions"]')[0].attrib['href']
    urls['description'] = page_dom.xpath('//a[@title="NHS Pathways and 111 Online Potential COVID-19 Meta Data"]')[0].attrib['href']

    try:
        while True:

            resp = requests.get(url=urls[SECTION], params=req_args)

            if not load_checkpoint(config, urls[SECTION]):
                c = StringIO()
                c.write(resp.content)
                c.seek(0)
                reader = csv.DictReader(c)
                for record in reader:
                    empty_keys = [k for k,v in record.iteritems() if not v]
                    #Tidy some fields
                    for k in empty_keys:
                        del record[k]
                    logging.warning(record)
                    print(record)
                    print_xml_stream(json.dumps(record,ensure_ascii=False),SECTION)
                #handle_output(content,daily_report.name)
                logging.warning("Logging file={}".format(urls[SECTION]))
                save_checkpoint(config, urls[SECTION])

            logging.warning("Finished - Waiting for internal")
            time.sleep(float(polling_interval))

    except RuntimeError, e:
        logging.error("Looks like an error: %s" % str(e))
        sys.exit(2)

def save_checkpoint(config, url):
    chk_file = get_encoded_file_path(config, url)
    # just create an empty file name
    logging.info("Checkpointing url=%s file=%s", url, chk_file)
    f = open(chk_file, "w")
    f.close()

def load_checkpoint(config, url):
    chk_file = get_encoded_file_path(config, url)
    # try to open this file
    try:
        open(chk_file, "r").close()
    except:
        # assume that this means the checkpoint is not there
        return False
    return True

def get_encoded_file_path(config, url):
    # encode the URL (simply to make the file name recognizable)
    name = "covid"
    for i in range(len(url)):
        if url[i].isalnum():
            name += url[i]
        else:
            name += "_"

    # MD5 the URL
    m = md5.new()
    m.update(url)
    name += "_" + m.hexdigest()

    return os.path.join(config["checkpoint_dir"], name)


def dictParameterToStringFormat(parameter):

    if parameter:
        return ''.join('{}={},'.format(key, val) for key, val in parameter.items())[:-1]
    else:
        return None


def handle_output(output, source):

    try:
        print_xml_stream(output, source)
        sys.stdout.flush()
    except RuntimeError, e:
        logging.error("Looks like an error handle the response output: %s" % str(e))

# prints validation error data to be consumed by Splunk
def print_validation_error(s):
    print "<error><message>%s</message></error>" % encodeXMLText(s)

# prints XML stream
def print_xml_single_instance_mode(s):
    print "<stream><event><data>%s</data></event></stream>" % encodeXMLText(s)

# prints simple stream
def print_simple(s):
    print "%s\n" % s

def encodeXMLText(text):
    text = text.replace("&", "&amp;")
    text = text.replace("\"", "&quot;")
    text = text.replace("'", "&apos;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text

def usage():
    print "usage: %s [--scheme|--validate-arguments]"
    logging.error("Incorrect Program Usage")
    sys.exit(2)

def do_scheme():
    print SCHEME

#read XML configuration passed from splunkd, need to refactor to support single instance mode
def get_input_config():
    config = {}

    try:
        # read everything from stdin
        config_str = sys.stdin.read()

        # parse the config XML
        doc = xml.dom.minidom.parseString(config_str)
        root = doc.documentElement

        session_key_node = root.getElementsByTagName("session_key")[0]
        if session_key_node and session_key_node.firstChild and session_key_node.firstChild.nodeType == session_key_node.firstChild.TEXT_NODE:
            data = session_key_node.firstChild.data
            config["session_key"] = data

        server_uri_node = root.getElementsByTagName("server_uri")[0]
        if server_uri_node and server_uri_node.firstChild and server_uri_node.firstChild.nodeType == server_uri_node.firstChild.TEXT_NODE:
            data = server_uri_node.firstChild.data
            config["server_uri"] = data

        conf_node = root.getElementsByTagName("configuration")[0]
        if conf_node:
            logging.debug("XML: found configuration")
            stanza = conf_node.getElementsByTagName("stanza")[0]
            if stanza:
                stanza_name = stanza.getAttribute("name")
                if stanza_name:
                    logging.debug("XML: found stanza " + stanza_name)
                    config["name"] = stanza_name

                    params = stanza.getElementsByTagName("param")
                    for param in params:
                        param_name = param.getAttribute("name")
                        logging.debug("XML: found param '%s'" % param_name)
                        if param_name and param.firstChild and \
                           param.firstChild.nodeType == param.firstChild.TEXT_NODE:
                            data = param.firstChild.data
                            config[param_name] = data
                            logging.debug("XML: '%s' -> '%s'" % (param_name, data))

        checkpnt_node = root.getElementsByTagName("checkpoint_dir")[0]
        if checkpnt_node and checkpnt_node.firstChild and \
           checkpnt_node.firstChild.nodeType == checkpnt_node.firstChild.TEXT_NODE:
            config["checkpoint_dir"] = checkpnt_node.firstChild.data

        if not config:
            raise Exception, "Invalid configuration received from Splunk."


    except Exception, e:
        raise Exception, "Error getting Splunk configuration via STDIN: %s" % str(e)

    return config

#read XML configuration passed from splunkd, need to refactor to support single instance mode
def get_validation_config():
    val_data = {}

    # read everything from stdin
    val_str = sys.stdin.read()

    # parse the validation XML
    doc = xml.dom.minidom.parseString(val_str)
    root = doc.documentElement

    logging.debug("XML: found items")
    item_node = root.getElementsByTagName("item")[0]
    if item_node:
        logging.debug("XML: found item")

        name = item_node.getAttribute("name")
        val_data["stanza"] = name

        params_node = item_node.getElementsByTagName("param")
        for param in params_node:
            name = param.getAttribute("name")
            logging.debug("Found param %s" % name)
            if name and param.firstChild and \
               param.firstChild.nodeType == param.firstChild.TEXT_NODE:
                val_data[name] = param.firstChild.data

    return val_data

if __name__ == '__main__':

    if len(sys.argv) > 1:
        if sys.argv[1] == "--scheme":
            do_scheme()
        elif sys.argv[1] == "--validate-arguments":
            do_validate()
        else:
            usage()
    else:
        do_run()

    sys.exit(0)

